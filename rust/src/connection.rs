//! High-level BMAP device connection.

use crate::device::*;
use crate::error::{BmapError, BmapResult};
use crate::protocol::{Operator, BmapResponse, bmap_packet, parse_response, parse_all_responses};

use crate::transport::Transport;

/// High-level connection to a BMAP device.
/// The device name field is 32 bytes on every BMAP device seen so far.
pub const MAX_NAME_BYTES: usize = 31;

pub struct BmapConnection<T: Transport> {
    transport: T,
    config: DeviceConfig,
}

impl<T: Transport> BmapConnection<T> {
    /// Create a connection from a transport and device config.
    pub fn new(transport: T, config: DeviceConfig) -> Self {
        Self { transport, config }
    }

    /// Device configuration.
    pub fn config(&self) -> &DeviceConfig {
        &self.config
    }

    // ── Helpers ─────────────────────────────────────────────────────────────

    fn addr(&self, feature: Option<Addr>) -> BmapResult<Addr> {
        feature.ok_or_else(|| BmapError::Unsupported(
            format!("{} does not support this feature", self.config.info.name)
        ))
    }

    fn get(&self, addr: Addr) -> BmapResult<Vec<u8>> {
        let pkt = bmap_packet(addr.0, addr.1, Operator::Get, &[]);
        let data = self.transport.send_recv(&pkt)?;
        let resp = parse_response(&data).ok_or_else(|| BmapError::Device {
            message: "Invalid or empty response".into(),
            code: 0,
        })?;
        self.check_error(&resp)?;
        Ok(resp.payload)
    }

    fn setget(&self, addr: Addr, payload: &[u8]) -> BmapResult<BmapResponse> {
        let pkt = bmap_packet(addr.0, addr.1, Operator::SetGet, payload);
        let data = self.transport.send_recv(&pkt)?;
        let resp = parse_response(&data)
            .ok_or_else(|| BmapError::Timeout("Empty response".into()))?;
        self.check_error(&resp)?;
        Ok(resp)
    }

    fn start(&self, addr: Addr, payload: &[u8]) -> BmapResult<BmapResponse> {
        let pkt = bmap_packet(addr.0, addr.1, Operator::Start, payload);
        let data = self.transport.send_recv(&pkt)?;
        let resp = parse_response(&data)
            .ok_or_else(|| BmapError::Timeout("Empty response".into()))?;
        self.check_error(&resp)?;
        Ok(resp)
    }

    /// Send START and drain all async responses.
    pub fn start_drain(&self, addr: Addr, payload: &[u8]) -> BmapResult<Vec<BmapResponse>> {
        let pkt = bmap_packet(addr.0, addr.1, Operator::Start, payload);
        let data = self.transport.send_recv_drain(&pkt)?;
        Ok(parse_all_responses(&data))
    }

    fn check_error(&self, resp: &BmapResponse) -> BmapResult<()> {
        if resp.op == Operator::Error && !resp.payload.is_empty() {
            let code = resp.payload[0];
            if code == 5 {
                return Err(BmapError::Auth(resp.fmt()));
            }
            return Err(BmapError::Device {
                message: resp.fmt(),
                code,
            });
        }
        Ok(())
    }

    // ── Read Operations ─────────────────────────────────────────────────────

    /// Battery percentage.
    pub fn battery(&self) -> BmapResult<u8> {
        Ok(self.battery_status()?.aggregate)
    }

    /// Aggregate and component levels from one battery response.
    pub fn battery_status(&self) -> BmapResult<BatteryStatus> {
        let addr = self.addr(self.config.battery)?;
        let payload = self.get(addr)?;
        if let Some(component_id) = self.config.battery_aggregate_id {
            let readings =
                parse_battery_readings(&payload).map_err(|message| BmapError::Device {
                    message: message.into(),
                    code: 0,
                })?;
            let sources = self.config.battery_aggregate_sources;
            let aggregate = readings
                .iter()
                .find(|reading| reading.component_id == component_id)
                .map(|reading| reading.level)
                // Aggregate missing or 0xFF: fall back to the lowest bud reading.
                .or_else(|| {
                    readings
                        .iter()
                        .filter(|reading| sources.contains(&reading.component_id))
                        .map(|reading| reading.level)
                        .min()
                })
                .ok_or_else(|| BmapError::Device {
                    message: format!(
                        "Battery response missing aggregate component {}",
                        component_id
                    ),
                    code: 0,
                })?;
            Ok(BatteryStatus {
                aggregate,
                readings,
            })
        } else {
            let aggregate = parse_battery(&payload).ok_or_else(|| BmapError::Device {
                message: "Empty battery response".into(),
                code: 0,
            })?;
            Ok(BatteryStatus {
                aggregate,
                readings: Vec::new(),
            })
        }
    }

    /// Component battery readings, when the device reports multiple cells.
    pub fn battery_readings(&self) -> BmapResult<Vec<BatteryReading>> {
        Ok(self.battery_status()?.readings)
    }

    /// Firmware version string.
    pub fn firmware(&self) -> BmapResult<String> {
        let addr = self.addr(self.config.firmware)?;
        let payload = self.get(addr)?;
        Ok(parse_firmware(&payload))
    }

    /// Device Bluetooth name.
    pub fn name(&self) -> BmapResult<String> {
        let addr = self.addr(self.config.product_name)?;
        let payload = self.get(addr)?;
        Ok(parse_product_name(&payload))
    }

    /// Current audio mode index.
    pub fn mode_idx(&self) -> BmapResult<u8> {
        let addr = self.addr(self.config.current_mode)?;
        let payload = self.get(addr)?;
        payload.first().copied().ok_or_else(|| BmapError::Device {
            message: "Empty mode response".into(), code: 0,
        })
    }

    /// Current audio mode name.
    pub fn mode(&self) -> BmapResult<String> {
        let idx = self.mode_idx()?;
        Ok(self.mode_name_from_idx(idx))
    }

    /// Resolve a mode index to a name without an extra GET.
    fn mode_name_from_idx(&self, idx: u8) -> String {
        for &(name, ref preset) in self.config.preset_modes {
            if preset.idx == idx {
                return name.to_string();
            }
        }
        // Try custom profiles if modes() is available
        if let Ok(modes) = self.modes() {
            if let Some(mc) = modes.iter().find(|m| m.mode_idx == idx) {
                return mc.name.clone();
            }
        }
        format!("custom({})", idx)
    }

    /// Noise cancellation (current, max) tuple.
    pub fn cnc(&self) -> BmapResult<(u8, u8)> {
        let addr = self.addr(self.config.cnc)?;
        let payload = self.get(addr)?;
        Ok(parse_cnc(&payload))
    }

    /// EQ bands.
    pub fn eq(&self) -> BmapResult<Vec<EqBand>> {
        let addr = self.addr(self.config.eq)?;
        let payload = self.get(addr)?;
        Ok(parse_eq(&payload))
    }

    /// Sidetone level name.
    pub fn sidetone(&self) -> BmapResult<&'static str> {
        let addr = self.addr(self.config.sidetone)?;
        let payload = self.get(addr)?;
        Ok(parse_sidetone(&payload))
    }

    /// Multipoint enabled.
    pub fn multipoint(&self) -> BmapResult<bool> {
        let addr = self.addr(self.config.multipoint)?;
        let payload = self.get(addr)?;
        Ok(parse_multipoint(&payload))
    }

    /// Active Noise Reduction mode (QC35: off/high/wind/low).
    pub fn anr(&self) -> BmapResult<&'static str> {
        let addr = self.addr(self.config.anr)?;
        let payload = self.get(addr)?;
        Ok(parse_anr(&payload))
    }

    /// Active audio source (none/bluetooth/auxiliary).
    pub fn source(&self) -> BmapResult<AudioSource> {
        let addr = self.addr(self.config.source)?;
        let payload = self.get(addr)?;
        Ok(parse_source(&payload))
    }

    /// Auto play/pause enabled.
    pub fn auto_pause(&self) -> BmapResult<bool> {
        let addr = self.addr(self.config.auto_pause)?;
        let payload = self.get(addr)?;
        Ok(parse_bool(&payload))
    }

    /// Auto-answer calls enabled.
    pub fn auto_answer(&self) -> BmapResult<bool> {
        let addr = self.addr(self.config.auto_answer)?;
        let payload = self.get(addr)?;
        Ok(parse_bool(&payload))
    }

    /// Voice prompts (enabled, language_name).
    pub fn prompts(&self) -> BmapResult<(bool, &'static str)> {
        let addr = self.addr(self.config.voice_prompts)?;
        let payload = self.get(addr)?;
        Ok(parse_voice_prompts(&payload))
    }

    /// Button mapping.
    pub fn buttons(&self) -> BmapResult<ButtonMapping> {
        let addr = self.addr(self.config.buttons)?;
        let payload = self.get(addr)?;
        parse_buttons(&payload).ok_or_else(|| BmapError::Device {
            message: "Could not parse button config".into(), code: 0,
        })
    }

    /// Full device status.
    pub fn status(&self) -> BmapResult<DeviceStatus> {
        // Single GET for mode index, derive name without extra round trip.
        let (current_idx, current_name) = match self.mode_idx() {
            Ok(idx) => (idx, self.mode_name_from_idx(idx)),
            Err(_) => (0, String::new()),
        };
        let (cnc_level, cnc_max) = self.cnc().unwrap_or((0, 10));
        let (prompts_enabled, prompts_language) = self.prompts().unwrap_or((false, "Unknown"));
        let battery = self.battery_status()?;

        Ok(DeviceStatus {
            battery: battery.aggregate,
            battery_readings: battery.readings,
            mode: current_name,
            mode_idx: current_idx,
            cnc_level,
            cnc_max,
            eq: self.eq().unwrap_or_default(),
            name: self.name().unwrap_or_default(),
            firmware: self.firmware().unwrap_or_default(),
            sidetone: self.sidetone().unwrap_or("off").to_string(),
            multipoint: self.multipoint().unwrap_or(false),
            auto_pause: self.auto_pause().unwrap_or(false),
            prompts_enabled,
            prompts_language: prompts_language.to_string(),
        })
    }

    /// All mode configurations. Returns vec of ModeConfig.
    pub fn modes(&self) -> BmapResult<Vec<ModeConfig>> {
        let addr = self.addr(self.config.get_all_modes)?;
        let mc_addr = self.addr(self.config.mode_config)?;
        let parser = self.config.parse_mode_config
            .ok_or_else(|| BmapError::Unsupported("Device has no mode config parser".into()))?;
        let responses = self.start_drain(addr, &[])?;
        let mut modes = Vec::new();
        for resp in &responses {
            if resp.fblock == mc_addr.0 && resp.func == mc_addr.1
                && resp.op == Operator::Status && resp.payload.len() >= 6
            {
                if let Some(config) = parser(&resp.payload) {
                    modes.push(config);
                }
            }
        }
        Ok(modes)
    }

    /// Check if the device supports a feature.
    pub fn has_feature(&self, name: &str) -> bool {
        match name {
            "battery" => self.config.battery.is_some(),
            "firmware" => self.config.firmware.is_some(),
            "product_name" => self.config.product_name.is_some(),
            "voice_prompts" => self.config.voice_prompts.is_some(),
            "cnc" => self.config.cnc.is_some(),
            "eq" => self.config.eq.is_some(),
            "buttons" => self.config.buttons.is_some(),
            "multipoint" => self.config.multipoint.is_some(),
            "sidetone" => self.config.sidetone.is_some(),
            "auto_pause" => self.config.auto_pause.is_some(),
            "auto_answer" => self.config.auto_answer.is_some(),
            "anr" => self.config.anr.is_some(),
            "routing" => self.config.routing.is_some(),
            "source" => self.config.source.is_some(),
            "audio_settings" => self.config.audio_settings.is_some(),
            "mode_config" => self.config.mode_config.is_some(),
            _ => false,
        }
    }

    // ── Write Operations ────────────────────────────────────────────────────

    /// Switch to a mode by name (preset or custom profile).
    pub fn set_mode(&self, name: &str, announce: bool) -> BmapResult<()> {
        let addr = self.addr(self.config.current_mode)?;

        // Check presets first
        let idx = if let Some(&(_, ref m)) = self.config.preset_modes.iter()
            .find(|&&(n, _)| n.eq_ignore_ascii_case(name))
        {
            m.idx
        } else {
            // Look up custom profiles
            let modes = self.modes()?;
            modes.iter()
                .find(|m| m.name.eq_ignore_ascii_case(name))
                .map(|m| m.mode_idx)
                .ok_or_else(|| BmapError::InvalidArg(format!("Unknown mode: {}", name)))?
        };

        let pkt = bmap_packet(addr.0, addr.1, Operator::Start,
                              &[idx, if announce { 1 } else { 0 }]);
        let data = self.transport.send_recv(&pkt)?;
        let resp = parse_response(&data)
            .ok_or_else(|| BmapError::Timeout("No response".into()))?;
        self.check_error(&resp)?;
        // Some firmware (QC Headphones "prince") acks START [31.3] with
        // PROCESSING and applies the switch asynchronously.
        if !matches!(resp.op, Operator::Result | Operator::Processing) {
            return Err(BmapError::Device { message: "Mode switch failed".into(), code: 0 });
        }
        Ok(())
    }

    /// Set Active Noise Reduction mode (QC35: off/high/wind/low).
    pub fn set_anr(&self, level: &str) -> BmapResult<()> {
        let addr = self.addr(self.config.anr)?;
        let val = match level {
            "off" => 0u8,
            "high" => 1,
            "wind" => 2,
            "low" => 3,
            _ => return Err(BmapError::InvalidArg("ANR: off, high, wind, low".into())),
        };
        self.setget(addr, &[val])?;
        Ok(())
    }

    /// Set noise cancellation level (0-10).
    ///
    /// Scale is inverted: 0 = max ANC, 10 = most ambient pass-through.
    /// Only audible when ANC is on and wind block is off.
    pub fn set_cnc(&self, level: u8) -> BmapResult<()> {
        if level > 10 {
            return Err(BmapError::InvalidArg("CNC level must be 0-10".into()));
        }
        if self.config.cnc_direct_setget {
            let addr = self.addr(self.config.cnc)?;
            self.setget(addr, &[level, 1])?;
            return Ok(());
        }
        self.update_audio_settings(Some(level), None, None, None)
    }

    /// Set spatial audio mode ("off"=0, "room"=1, "head"=2).
    pub fn set_spatial(&self, mode: &str) -> BmapResult<()> {
        let spatial = match mode {
            "off" => 0u8,
            "room" => 1,
            "head" => 2,
            _ => return Err(BmapError::InvalidArg("Spatial: off, room, head".into())),
        };
        self.update_audio_settings(None, Some(spatial), None, None)
    }

    /// Toggle Active Noise Cancellation on/off.
    pub fn set_anc(&self, enabled: bool) -> BmapResult<()> {
        self.update_audio_settings(None, None, None, Some(enabled))
    }

    /// Toggle Wind Block on/off.
    pub fn set_wind(&self, enabled: bool) -> BmapResult<()> {
        self.update_audio_settings(None, None, Some(enabled), None)
    }

    /// Read current audio settings as 5-tuple: (cnc, auto_cnc, spatial, wind, anc).
    pub fn audio_settings(&self) -> BmapResult<(u8, u8, u8, u8, u8)> {
        if let Some(addr) = self.config.audio_settings {
            let p = self.get(addr)?;
            Ok((
                p.first().copied().unwrap_or(0),
                p.get(1).copied().unwrap_or(0),
                p.get(2).copied().unwrap_or(0),
                p.get(3).copied().unwrap_or(1),
                p.get(4).copied().unwrap_or(1),
            ))
        } else {
            let mc = self.current_mode_config()?;
            Ok((
                mc.cnc_level,
                0,
                mc.spatial,
                if mc.wind_block { 1 } else { 0 },
                if mc.anc_toggle { 1 } else { 0 },
            ))
        }
    }

    fn update_audio_settings(&self, cnc: Option<u8>, spatial: Option<u8>,
                              wind: Option<bool>, anc: Option<bool>) -> BmapResult<()> {
        if let Some(addr) = self.config.audio_settings {
            let cur = self.get(addr)?;
            let payload = [
                cnc.unwrap_or(cur.first().copied().unwrap_or(0)),
                cur.get(1).copied().unwrap_or(0),  // auto_cnc
                spatial.unwrap_or(cur.get(2).copied().unwrap_or(0)),
                wind.map(|b| if b { 1 } else { 0 }).unwrap_or(cur.get(3).copied().unwrap_or(1)),
                anc.map(|b| if b { 1 } else { 0 }).unwrap_or(cur.get(4).copied().unwrap_or(1)),
            ];
            self.setget(addr, &payload)?;
            Ok(())
        } else {
            self.update_current_mode_config(cnc, spatial, wind, anc)
        }
    }

    /// Toggle voice prompts. Preserves current language.
    pub fn set_prompts(&self, enabled: bool) -> BmapResult<()> {
        let addr = self.addr(self.config.voice_prompts)?;
        let payload = self.get(addr)?;
        let lang = payload.first().map_or(0, |b| b & 0x1F);
        let byte0 = ((if enabled { 1u8 } else { 0 }) << 5) | lang;
        self.setget(addr, &[byte0])?;
        Ok(())
    }

    /// Toggle auto-answer calls.
    pub fn set_auto_answer(&self, enabled: bool) -> BmapResult<()> {
        let addr = self.addr(self.config.auto_answer)?;
        self.setget(addr, &[if enabled { 1 } else { 0 }])?;
        Ok(())
    }

    /// Set EQ bands (-10 to +10 each).
    pub fn set_eq(&self, bass: i8, mid: i8, treble: i8) -> BmapResult<()> {
        for &val in &[bass, mid, treble] {
            if val < -10 || val > 10 {
                return Err(BmapError::InvalidArg("EQ values must be -10 to +10".into()));
            }
        }
        let addr = self.addr(self.config.eq)?;
        for (band_id, val) in [(0u8, bass), (1, mid), (2, treble)] {
            let payload = [val as u8, band_id];
            let pkt = bmap_packet(addr.0, addr.1, Operator::SetGet, &payload);
            self.transport.send_recv(&pkt)?;
        }
        Ok(())
    }

    /// Set device name.
    pub fn set_name(&self, name: &str) -> BmapResult<()> {
        if name.len() > MAX_NAME_BYTES {
            return Err(BmapError::InvalidArg(format!(
                "Name must be at most {} bytes of UTF-8", MAX_NAME_BYTES)));
        }
        let addr = self.addr(self.config.product_name)?;
        self.setget(addr, name.as_bytes())?;
        Ok(())
    }

    /// Toggle multipoint.
    pub fn set_multipoint(&self, enabled: bool) -> BmapResult<()> {
        let addr = self.addr(self.config.multipoint)?;
        self.setget(addr, &[if enabled { 1 } else { 0 }])?;
        Ok(())
    }

    /// Toggle auto play/pause.
    pub fn set_auto_pause(&self, enabled: bool) -> BmapResult<()> {
        let addr = self.addr(self.config.auto_pause)?;
        self.setget(addr, &[if enabled { 1 } else { 0 }])?;
        Ok(())
    }

    /// Set sidetone level.
    pub fn set_sidetone(&self, level: &str) -> BmapResult<()> {
        let addr = self.addr(self.config.sidetone)?;
        let val = match level {
            "off" => 0u8,
            "high" => 1,
            "medium" | "med" => 2,
            "low" => 3,
            _ => return Err(BmapError::InvalidArg("Sidetone: off, low, medium, high".into())),
        };
        self.setget(addr, &[1, val])?;
        Ok(())
    }

    /// Power off device.
    pub fn power_off(&self) -> BmapResult<()> {
        let addr = self.addr(self.config.power)?;
        self.start(addr, &[0x00])?;
        Ok(())
    }

    /// Remap a button action via SETGET [1.9].
    pub fn set_buttons(&self, button_id: u8, event: u8, action: u8) -> BmapResult<ButtonMapping> {
        let addr = self.addr(self.config.buttons)?;
        let payload = build_buttons(button_id, event, action);
        let resp = self.setget(addr, &payload)?;
        parse_buttons(&resp.payload).ok_or_else(|| BmapError::Device {
            message: "Could not parse button remap response".into(), code: 0,
        })
    }

    /// Switch active audio to a paired BT device by MAC address.
    pub fn route(&self, mac: &str) -> BmapResult<()> {
        let addr = self.addr(self.config.routing)?;
        let payload = build_routing(mac)
            .map_err(|e| BmapError::InvalidArg(e))?;
        self.start(addr, &payload)?;
        Ok(())
    }

    /// Enter pairing mode.
    pub fn pair(&self) -> BmapResult<()> {
        let addr = self.addr(self.config.pairing)?;
        self.start(addr, &[0x01])?;
        Ok(())
    }

    // ── Profile Management ────────────────────────────────────────────────

    /// Create a custom profile in the first available slot. Returns slot index.
    pub fn create_profile(&self, name: &str, cnc_level: u8, spatial: u8,
                          wind_block: bool, anc_toggle: bool) -> BmapResult<u8> {
        let modes = self.modes()?;
        let slot = self.find_free_slot(&modes)?;
        self.write_mode(slot, name, cnc_level, spatial, wind_block, anc_toggle, 0, 0)?;
        Ok(slot)
    }

    /// Delete a custom profile by name.
    pub fn delete_profile(&self, name: &str) -> BmapResult<()> {
        let modes = self.modes()?;
        let mc = modes.iter()
            .find(|m| m.name.eq_ignore_ascii_case(name))
            .ok_or_else(|| BmapError::InvalidArg(format!("Profile '{}' not found", name)))?;
        if !mc.editable {
            return Err(BmapError::InvalidArg(format!("Cannot delete preset '{}'", name)));
        }
        self.write_mode(mc.mode_idx, "None", 0, 0, false, false, 0, 0)?;
        Ok(())
    }

    /// Send raw bytes. Returns all responses.
    pub fn send_raw(&self, data: &[u8]) -> BmapResult<Vec<BmapResponse>> {
        let resp = self.transport.send_recv_drain(data)?;
        Ok(parse_all_responses(&resp))
    }

    // ── Internal Helpers ────────────────────────────────────────────────────

    fn find_free_slot(&self, modes: &[ModeConfig]) -> BmapResult<u8> {
        for &slot in self.config.editable_slots {
            match modes.iter().find(|m| m.mode_idx == slot) {
                Some(m) if !m.configured && m.name.eq_ignore_ascii_case("none") => return Ok(slot),
                Some(m) if !m.configured && m.name.is_empty() => return Ok(slot),
                None => return Ok(slot),
                _ => continue,
            }
        }
        Err(BmapError::Device {
            message: "No free profile slot available".into(), code: 0,
        })
    }

    fn current_mode_config(&self) -> BmapResult<ModeConfig> {
        let idx = self.mode_idx()?;
        let modes = self.modes()?;
        modes.into_iter()
            .find(|m| m.mode_idx == idx)
            .ok_or_else(|| BmapError::Device {
                message: "Current mode config not available".into(), code: 0,
            })
    }

    fn update_current_mode_config(&self, cnc: Option<u8>, spatial: Option<u8>,
                                  wind: Option<bool>, anc: Option<bool>) -> BmapResult<()> {
        if anc.is_some() && !self.config.supports_anc_toggle {
            return Err(BmapError::Unsupported(
                "Device does not expose an ANC on/off toggle".into()
            ));
        }
        let mut mc = self.current_mode_config()?;
        if !mc.editable {
            return Err(BmapError::Unsupported(
                format!("Current mode '{}' is not editable on this device", mc.name)
            ));
        }
        if let Some(v) = cnc { mc.cnc_level = v; }
        if let Some(v) = spatial { mc.spatial = v; }
        if let Some(v) = wind { mc.wind_block = v; }
        if let Some(v) = anc { mc.anc_toggle = v; }
        self.write_mode(
            mc.mode_idx, &mc.name, mc.cnc_level, mc.spatial,
            mc.wind_block, mc.anc_toggle, mc.prompt_b1, mc.prompt_b2,
        )
    }

    fn write_mode(&self, slot: u8, name: &str, cnc_level: u8, spatial: u8,
                   wind_block: bool, anc_toggle: bool, prompt_b1: u8, prompt_b2: u8)
                   -> BmapResult<()> {
        let addr = self.addr(self.config.mode_config)?;
        let builder = self.config.build_mode_config
            .ok_or_else(|| BmapError::Unsupported("Device has no mode config builder".into()))?;
        let payload = builder(
            slot, name, cnc_level, spatial, wind_block, anc_toggle, prompt_b1, prompt_b2,
        );
        let data = self.transport.send_recv_drain(
            &bmap_packet(addr.0, addr.1, Operator::SetGet, &payload)
        )?;
        let responses = parse_all_responses(&data);
        if !responses.iter().any(|r| r.op == Operator::Status) {
            return Err(BmapError::Device { message: "Mode config write failed".into(), code: 0 });
        }
        Ok(())
    }

}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::devices;
    use std::collections::HashMap;
    use std::cell::RefCell;

    /// Mock transport that returns canned responses keyed by (fblock, func).
    struct MockTransport {
        responses: HashMap<(u8, u8), Vec<u8>>,
        sent: RefCell<Vec<Vec<u8>>>,
    }

    impl MockTransport {
        fn new() -> Self {
            Self { responses: HashMap::new(), sent: RefCell::new(Vec::new()) }
        }

        fn add(&mut self, fblock: u8, func: u8, op: u8, payload: &[u8]) {
            let mut resp = vec![fblock, func, op, payload.len() as u8];
            resp.extend_from_slice(payload);
            self.responses.insert((fblock, func), resp);
        }
    }

    impl Transport for MockTransport {
        fn send_recv(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
            self.sent.borrow_mut().push(packet.to_vec());
            let key = (packet[0], packet[1]);
            self.responses.get(&key).cloned()
                .ok_or_else(|| BmapError::Device {
                    message: format!("No mock for {:?}", key), code: 4,
                })
        }

        fn send_recv_drain(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
            self.send_recv(packet)
        }
    }

    fn mock_qc_ultra2() -> BmapConnection<MockTransport> {
        let mut t = MockTransport::new();
        // Real capture data
        t.add(2, 2, 0x03, &[80, 0xff, 0xff, 0x00]);          // battery 80%
        t.add(0, 5, 0x03, b"8.2.20+g34cf029");                // firmware
        t.add(1, 2, 0x03, b"\x00Fargo");                      // name
        t.add(1, 5, 0x03, &[0x0b, 0x07, 0x03]);               // cnc 7/10
        t.add(1, 7, 0x03, &[0xf6,0x0a,0x03,0x00, 0xf6,0x0a,0xfe,0x01, 0xf6,0x0a,0xfa,0x02]); // eq
        t.add(1, 10, 0x03, &[0x07]);                           // multipoint on
        t.add(1, 11, 0x03, &[0x01, 0x02, 0x0f]);              // sidetone medium
        t.add(1, 24, 0x03, &[0x01]);                           // auto_pause on
        t.add(1, 27, 0x03, &[0x01]);                           // auto_answer on
        t.add(1, 3, 0x03, &[0x21,0,0,0x81,2,0,0]);            // prompts on, US English
        t.add(31, 3, 0x03, &[0x00]);                           // current mode: quiet
        t.add(1, 9, 0x03, &[0x80,0x09,0x0e,0x00,0x09,0x40,0x02]); // buttons
        BmapConnection::new(t, devices::qc_ultra2())
    }

    #[test]
    fn test_battery() {
        assert_eq!(mock_qc_ultra2().battery().unwrap(), 80);
    }

    #[test]
    fn test_battery_rejects_empty_response() {
        let mut t = MockTransport::new();
        t.add(2, 2, 0x03, &[]);
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        assert!(matches!(dev.battery(), Err(BmapError::Device { message, .. })
            if message.contains("Empty battery response")));
    }

    #[test]
    fn test_battery_rejects_invalid_frame() {
        let mut t = MockTransport::new();
        t.responses.insert((2, 2), vec![2, 2, 0x08, 0]);
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        assert!(matches!(dev.battery(), Err(BmapError::Device { message, .. })
            if message.contains("Invalid or empty response")));
    }

    #[test]
    fn test_battery_readings() {
        let mut t = MockTransport::new();
        t.add(2, 2, 0x03, &[
            0x50,0xff,0xff,0x03, 0x3c,0xff,0xff,0x01,
            0x3c,0xff,0xff,0x02, 0x46,0xff,0xff,0x04,
        ]);
        let dev = BmapConnection::new(t, devices::qc_ultra2_earbuds());
        let battery = dev.battery_status().unwrap();
        assert_eq!(battery.readings, vec![
            BatteryReading { component_id: 3, level: 80 },
            BatteryReading { component_id: 1, level: 60 },
            BatteryReading { component_id: 2, level: 60 },
            BatteryReading { component_id: 4, level: 70 },
        ]);
        assert_eq!(battery.aggregate, 70);
        assert_eq!(dev.transport.sent.borrow().len(), 1);
    }

    fn earbuds_battery_fixture() -> Vec<u8> {
        let text = include_str!(
            "../../fixtures/packets/qc-ultra2-earbuds/battery-status.hex"
        )
        .trim();
        (0..text.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&text[i..i + 2], 16).unwrap())
            .collect()
    }

    fn fixture_bud_readings() -> Vec<BatteryReading> {
        vec![
            BatteryReading { component_id: 1, level: 60 },
            BatteryReading { component_id: 2, level: 60 },
            BatteryReading { component_id: 3, level: 80 },
        ]
    }

    #[test]
    fn test_battery_falls_back_to_lowest_bud_without_aggregate() {
        let mut t = MockTransport::new();
        t.add(2, 2, 0x03, &[
            0x3c,0xff,0xff,0x01, 0x50,0xff,0xff,0x02,
            0x28,0xff,0xff,0x03,
        ]);
        let dev = BmapConnection::new(t, devices::qc_ultra2_earbuds());
        // Case (3) is lower but is not a bud; right bud (1) is the lowest.
        assert_eq!(dev.battery().unwrap(), 60);
    }

    #[test]
    fn test_battery_rejects_response_without_valid_buds() {
        let mut t = MockTransport::new();
        t.add(2, 2, 0x03, &[
            0xff,0xff,0xff,0x01, 0xff,0xff,0xff,0x02,
            0xff,0xff,0xff,0x04, 0x28,0xff,0xff,0x03,
        ]);
        let dev = BmapConnection::new(t, devices::qc_ultra2_earbuds());
        assert!(matches!(dev.battery(), Err(BmapError::Device { message, .. })
            if message.contains("aggregate component 4")));
    }

    #[test]
    fn test_status_falls_back_when_fixture_aggregate_is_invalid() {
        let mut payload = earbuds_battery_fixture();
        for record in payload.chunks_exact_mut(4) {
            if record[3] == 4 {
                record[0] = 0xff;
            }
        }
        let mut t = MockTransport::new();
        t.add(2, 2, 0x03, &payload);
        let status = BmapConnection::new(t, devices::qc_ultra2_earbuds()).status().unwrap();
        assert_eq!(status.battery, 60);
        assert_eq!(status.battery_readings, fixture_bud_readings());
    }

    #[test]
    fn test_status_falls_back_when_fixture_aggregate_is_absent() {
        let payload: Vec<u8> = earbuds_battery_fixture()
            .chunks_exact(4)
            .filter(|record| record[3] != 4)
            .flatten()
            .copied()
            .collect();
        let mut t = MockTransport::new();
        t.add(2, 2, 0x03, &payload);
        let status = BmapConnection::new(t, devices::qc_ultra2_earbuds()).status().unwrap();
        assert_eq!(status.battery, 60);
        assert_eq!(status.battery_readings, fixture_bud_readings());
    }

    #[test]
    fn test_status_rejects_battery_without_valid_readings() {
        // A failed read must not surface as a measured 0%.
        let mut t = MockTransport::new();
        t.add(2, 2, 0x03, &[
            0xff,0xff,0xff,0x01, 0xff,0xff,0xff,0x02,
            0xff,0xff,0xff,0x04, 0xff,0xff,0xff,0x03,
        ]);
        t.add(31, 3, 0x03, &[0x01]);
        let dev = BmapConnection::new(t, devices::qc_ultra2_earbuds());
        assert!(matches!(dev.status(), Err(BmapError::Device { message, .. })
            if message.contains("aggregate component 4")));
    }

    #[test]
    fn test_status_uses_one_battery_response() {
        let mut t = MockTransport::new();
        t.add(2, 2, 0x03, &[
            0x50,0xff,0xff,0x03, 0x3c,0xff,0xff,0x01,
            0x46,0xff,0xff,0x04, 0x3c,0xff,0xff,0x02,
        ]);
        let dev = BmapConnection::new(t, devices::qc_ultra2_earbuds());
        let status = dev.status().unwrap();
        assert_eq!(status.battery, 70);
        assert_eq!(status.battery_readings.len(), 4);
        let battery_requests = dev
            .transport
            .sent
            .borrow()
            .iter()
            .filter(|packet| packet.starts_with(&[2, 2]))
            .count();
        assert_eq!(battery_requests, 1);
    }

    #[test]
    fn test_firmware() {
        assert_eq!(mock_qc_ultra2().firmware().unwrap(), "8.2.20+g34cf029");
    }

    #[test]
    fn test_name() {
        assert_eq!(mock_qc_ultra2().name().unwrap(), "Fargo");
    }

    #[test]
    fn test_cnc() {
        let (cur, max) = mock_qc_ultra2().cnc().unwrap();
        assert_eq!(cur, 7);
        assert_eq!(max, 10);
    }

    #[test]
    fn test_eq() {
        let bands = mock_qc_ultra2().eq().unwrap();
        assert_eq!(bands.len(), 3);
        assert_eq!(bands[0].name, "Bass");
        assert_eq!(bands[0].current, 3);
        assert_eq!(bands[1].current, -2);
        assert_eq!(bands[2].current, -6);
    }

    #[test]
    fn test_multipoint() {
        assert!(mock_qc_ultra2().multipoint().unwrap());
    }

    #[test]
    fn test_sidetone() {
        assert_eq!(mock_qc_ultra2().sidetone().unwrap(), "medium");
    }

    #[test]
    fn test_auto_pause() {
        assert!(mock_qc_ultra2().auto_pause().unwrap());
    }

    #[test]
    fn test_mode() {
        assert_eq!(mock_qc_ultra2().mode().unwrap(), "quiet");
    }

    #[test]
    fn test_mode_idx() {
        assert_eq!(mock_qc_ultra2().mode_idx().unwrap(), 0);
    }

    #[test]
    fn test_buttons() {
        let btn = mock_qc_ultra2().buttons().unwrap();
        assert_eq!(btn.button_name, "Shortcut");
        assert_eq!(btn.event_name, "long_press");
        assert_eq!(btn.action_name, "Disabled");
    }

    #[test]
    fn test_status() {
        let s = mock_qc_ultra2().status().unwrap();
        assert_eq!(s.battery, 80);
        assert!(s.battery_readings.is_empty());
        assert_eq!(s.mode, "quiet");
        assert_eq!(s.cnc_level, 7);
        assert_eq!(s.cnc_max, 10);
        assert_eq!(s.name, "Fargo");
        assert_eq!(s.firmware, "8.2.20+g34cf029");
        assert_eq!(s.sidetone, "medium");
        assert!(s.multipoint);
        assert!(s.auto_pause);
    }

    #[test]
    fn test_config_access() {
        let dev = mock_qc_ultra2();
        assert_eq!(dev.config().info.name, "Bose QC Ultra Headphones 2");
        assert_eq!(dev.config().preset_modes.len(), 4);
    }

    #[test]
    fn test_unsupported_feature() {
        // QC35 has no EQ
        let t = MockTransport::new();
        let dev = BmapConnection::new(t, devices::qc35());
        assert!(dev.eq().is_err());
    }

    #[test]
    fn test_auth_error() {
        let mut t = MockTransport::new();
        t.add(1, 5, 0x04, &[5]); // ERROR: auth
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        match dev.cnc() {
            Err(BmapError::Auth(_)) => (),
            other => panic!("Expected Auth error, got {:?}", other),
        }
    }

    #[test]
    fn test_set_name_rejects_long_name() {
        let dev = BmapConnection::new(MockTransport::new(), devices::qc_ultra2());
        assert!(dev.set_name(&"x".repeat(32)).is_err());
    }

    #[test]
    fn test_device_error() {
        let mut t = MockTransport::new();
        t.add(1, 5, 0x04, &[8]); // ERROR: runtime
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        match dev.cnc() {
            Err(BmapError::Device { code, .. }) => assert_eq!(code, 8),
            other => panic!("Expected Device error, got {:?}", other),
        }
    }

    #[test]
    fn test_set_mode_accepts_processing_ack() {
        let mut t = MockTransport::new();
        t.add(31, 3, 0x07, &[]); // PROCESSING: async ack (prince)
        let dev = BmapConnection::new(t, devices::qc_prince());
        dev.set_mode("quiet", false).unwrap();
    }

    #[test]
    fn test_set_mode_rejects_unexpected_op() {
        let mut t = MockTransport::new();
        t.add(31, 3, 0x03, &[0]); // STATUS where RESULT/PROCESSING expected
        let dev = BmapConnection::new(t, devices::qc_prince());
        assert!(dev.set_mode("quiet", false).is_err());
    }

    #[test]
    fn test_status_tolerates_missing_features() {
        let mut t = MockTransport::new();
        t.add(2, 2, 0x03, &[50, 0xff, 0xff, 0x00]); // battery
        t.add(31, 3, 0x03, &[0x01]);                  // mode: aware
        // Everything else will error
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        let s = dev.status().unwrap();
        assert_eq!(s.battery, 50);
        assert_eq!(s.mode, "aware");
        assert!(s.eq.is_empty());
        assert_eq!(s.name, "");
    }

    #[test]
    fn test_has_feature() {
        let dev = mock_qc_ultra2();
        assert!(dev.has_feature("battery"));
        assert!(dev.has_feature("eq"));
        assert!(dev.has_feature("mode_config"));
        assert!(!dev.has_feature("nonexistent"));
    }

    #[test]
    fn test_has_feature_qc35() {
        let t = MockTransport::new();
        let dev = BmapConnection::new(t, devices::qc35());
        assert!(dev.has_feature("battery"));
        assert!(!dev.has_feature("eq"));
        assert!(dev.has_feature("sidetone"));  // QC35 has sidetone
        assert!(!dev.has_feature("mode_config"));
    }

    #[test]
    fn test_set_prompts() {
        let mut t = MockTransport::new();
        // GET returns current: enabled=true, lang=US English (0x21)
        t.add(1, 3, 0x03, &[0x21, 0, 0, 0x81, 2, 0, 0]);
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        // set_prompts reads current, then sends SETGET
        // Since our mock returns the same response for any op, this should succeed
        assert!(dev.set_prompts(false).is_ok());
    }

    #[test]
    fn test_set_eq() {
        let mut t = MockTransport::new();
        t.add(1, 7, 0x03, &[0xf6, 0x0a, 0x03, 0x00]); // EQ response
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        assert!(dev.set_eq(3, -2, 5).is_ok());
        // Verify 3 packets were sent (one per band)
        assert_eq!(dev.transport.sent.borrow().len(), 3);
    }

    #[test]
    fn test_set_sidetone() {
        let mut t = MockTransport::new();
        t.add(1, 11, 0x03, &[0x01, 0x02, 0x0f]);
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        assert!(dev.set_sidetone("low").is_ok());
    }

    #[test]
    fn test_set_sidetone_invalid() {
        let t = MockTransport::new();
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        assert!(dev.set_sidetone("loud").is_err());
    }

    #[test]
    fn test_set_mode_preset() {
        let mut t = MockTransport::new();
        t.add(31, 3, 0x06, &[0x01]); // RESULT for mode switch
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        assert!(dev.set_mode("aware", false).is_ok());
    }

    #[test]
    fn test_set_mode_unknown() {
        let t = MockTransport::new();
        let dev = BmapConnection::new(t, devices::qc_ultra2());
        // "nonexistent" is not a preset, and modes() will fail (no mock for get_all_modes)
        assert!(dev.set_mode("nonexistent", false).is_err());
    }

    #[test]
    fn test_prince_set_wind_uses_mode_config_fallback() {
        let music = vec![
            0x03,0x00,0x0c,0x01,0x01,0x00,0x4d,0x75,0x73,0x69,0x63,0x00,0x00,0x00,0x00,0x00,
            0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
            0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x09,0x05,0x00,0x00,0x00,0x00,
        ];
        let mut t = MockTransport::new();
        t.add(31, 3, 0x03, &[3]); // current mode: Music
        let mut get_all = vec![31, 6, 0x03, music.len() as u8];
        get_all.extend_from_slice(&music);
        t.responses.insert((31, 1), get_all);
        t.add(31, 6, 0x03, &music);
        let dev = BmapConnection::new(t, devices::qc_prince());

        assert!(dev.set_wind(true).is_ok());

        let sent = dev.transport.sent.borrow();
        let last = sent.last().unwrap();
        assert_eq!(&last[..4], &[31, 6, 0x02, 39]);
        assert_eq!(last[4], 3);
        assert_eq!(last[4 + 35], 5);
        assert_eq!(last[4 + 38], 1);
    }

    #[test]
    fn test_prince_set_anc_rejects_missing_toggle() {
        let t = MockTransport::new();
        let dev = BmapConnection::new(t, devices::qc_prince());
        assert!(dev.set_anc(false).is_err());
    }
}
