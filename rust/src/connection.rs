//! High-level BMAP device connection.

use crate::device::*;
use crate::error::{BmapError, BmapResult};
use crate::protocol::{Operator, BmapResponse, bmap_packet, parse_response, parse_all_responses};

use crate::transport::Transport;

/// High-level connection to a BMAP device.
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
        let resp = parse_response(&data)
            .ok_or_else(|| BmapError::Timeout("Empty response".into()))?;
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
        let addr = self.addr(self.config.battery)?;
        let payload = self.get(addr)?;
        parse_battery(&payload).ok_or_else(|| BmapError::Device {
            message: "Empty battery response".into(), code: 0,
        })
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

        Ok(DeviceStatus {
            battery: self.battery()?,
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
        if resp.op != Operator::Result {
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
    /// If on a preset mode, creates/reuses a custom profile.
    pub fn set_cnc(&self, level: u8) -> BmapResult<()> {
        if level > 10 {
            return Err(BmapError::InvalidArg("CNC level must be 0-10".into()));
        }
        let (slot, config) = self.ensure_editable_profile()?;
        self.write_mode_from_config(slot, &config, Some(level), None, None, None)?;
        let addr = self.addr(self.config.current_mode)?;
        self.start(addr, &[slot, 0])?;
        Ok(())
    }

    /// Set spatial audio mode ("off"=0, "room"=1, "head"=2).
    pub fn set_spatial(&self, mode: &str) -> BmapResult<()> {
        let spatial = match mode {
            "off" => 0u8,
            "room" => 1,
            "head" => 2,
            _ => return Err(BmapError::InvalidArg("Spatial: off, room, head".into())),
        };
        let (slot, config) = self.ensure_editable_profile()?;
        self.write_mode_from_config(slot, &config, None, Some(spatial), None, None)?;
        let addr = self.addr(self.config.current_mode)?;
        self.start(addr, &[slot, 0])?;
        Ok(())
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

    fn ensure_editable_profile(&self) -> BmapResult<(u8, ModeConfig)> {
        let modes = self.modes()?;
        let current_idx = self.mode_idx()?;

        // If current mode is editable, use it
        if let Some(config) = modes.iter().find(|m| m.mode_idx == current_idx) {
            if config.editable {
                return Ok((current_idx, config.clone()));
            }
        }

        // Look for existing "Custom" profile
        if let Some(config) = modes.iter().find(|m| m.name.eq_ignore_ascii_case("custom") && m.editable) {
            return Ok((config.mode_idx, config.clone()));
        }

        // Create a new one
        let slot = self.find_free_slot(&modes)?;
        let (cnc_cur, _) = self.cnc().unwrap_or((0, 10));
        self.write_mode(slot, "Custom", cnc_cur, 0, true, true, 0, 0)?;

        // Re-read to get the full config
        let modes = self.modes()?;
        let config = modes.iter()
            .find(|m| m.mode_idx == slot)
            .cloned()
            .ok_or_else(|| BmapError::Device {
                message: "Failed to read back custom profile".into(), code: 0,
            })?;
        Ok((slot, config))
    }

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

    fn write_mode(&self, slot: u8, name: &str, cnc_level: u8, spatial: u8,
                   wind_block: bool, anc_toggle: bool, prompt_b1: u8, prompt_b2: u8)
                   -> BmapResult<()> {
        let addr = self.addr(self.config.mode_config)?;
        let payload = build_mode_config_40(
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

    fn write_mode_from_config(&self, slot: u8, config: &ModeConfig,
                               cnc: Option<u8>, spatial: Option<u8>,
                               wind: Option<bool>, anc: Option<bool>) -> BmapResult<()> {
        self.write_mode(
            slot,
            &config.name,
            cnc.unwrap_or(config.cnc_level),
            spatial.unwrap_or(config.spatial),
            wind.unwrap_or(config.wind_block),
            anc.unwrap_or(config.anc_toggle),
            config.prompt_b1,
            config.prompt_b2,
        )
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
}
