//! Device configuration and parser types.
//!
//! Each device is described by a `DeviceConfig` that maps feature names
//! to function block addresses and declares which features are available.

use crate::protocol::encode_mode_name;

/// A function block address: (fblock_id, function_id).
#[derive(Debug, Clone, Copy)]
pub struct Addr(pub u8, pub u8);

/// Device identification.
#[derive(Debug, Clone)]
pub struct DeviceInfo {
    pub name: &'static str,
    pub codename: &'static str,
    pub platform: &'static str,
}

/// Preset audio mode.
#[derive(Debug, Clone)]
pub struct PresetMode {
    pub idx: u8,
    pub description: &'static str,
}

/// Parsed mode configuration.
#[derive(Debug, Clone)]
pub struct ModeConfig {
    pub mode_idx: u8,
    pub name: String,
    pub cnc_level: u8,
    pub spatial: u8,
    pub wind_block: bool,
    pub anc_toggle: bool,
    pub editable: bool,
    pub configured: bool,
    pub prompt_b1: u8,
    pub prompt_b2: u8,
}

/// Parsed EQ band.
#[derive(Debug, Clone)]
pub struct EqBand {
    pub band_id: u8,
    pub name: &'static str,
    pub current: i8,
    pub min_val: i8,
    pub max_val: i8,
}

/// Button mapping.
#[derive(Debug, Clone)]
pub struct ButtonMapping {
    pub button_id: u8,
    pub button_name: &'static str,
    pub event: u8,
    pub event_name: &'static str,
    pub action: u8,
    pub action_name: &'static str,
}

/// Full device status snapshot.
#[derive(Debug, Clone)]
pub struct DeviceStatus {
    pub battery: u8,
    pub mode: String,
    pub mode_idx: u8,
    pub cnc_level: u8,
    pub cnc_max: u8,
    pub eq: Vec<EqBand>,
    pub name: String,
    pub firmware: String,
    pub sidetone: String,
    pub multipoint: bool,
    pub auto_pause: bool,
    pub prompts_enabled: bool,
    pub prompts_language: String,
}

/// Feature addresses for a device. None means the device doesn't support it.
#[derive(Debug, Clone)]
pub struct DeviceConfig {
    pub info: DeviceInfo,
    /// RFCOMM channel for BMAP (2 for newer devices, 8 for QC35).
    pub rfcomm_channel: u8,
    /// Init packet required before device responds (Some((fblock, func)) for QC35).
    pub init_packet: Option<Addr>,
    pub battery: Option<Addr>,
    pub firmware: Option<Addr>,
    pub product_name: Option<Addr>,
    pub voice_prompts: Option<Addr>,
    pub cnc: Option<Addr>,
    pub eq: Option<Addr>,
    pub buttons: Option<Addr>,
    pub multipoint: Option<Addr>,
    pub sidetone: Option<Addr>,
    pub auto_pause: Option<Addr>,
    pub auto_answer: Option<Addr>,
    /// ANR mode address (QC35: off/high/wind/low at [1.6]).
    pub anr: Option<Addr>,
    pub pairing: Option<Addr>,
    pub power: Option<Addr>,
    pub get_all_modes: Option<Addr>,
    pub current_mode: Option<Addr>,
    pub mode_config: Option<Addr>,
    pub favorites: Option<Addr>,
    pub preset_modes: &'static [(&'static str, PresetMode)],
    pub editable_slots: &'static [u8],
    /// Device-specific ModeConfig STATUS parser. None if device has no mode config.
    pub parse_mode_config: Option<fn(&[u8]) -> Option<ModeConfig>>,
}

// ── Shared Parsers ──────────────────────────────────────────────────────────

pub fn parse_battery(payload: &[u8]) -> Option<u8> {
    payload.first().copied()
}

pub fn parse_firmware(payload: &[u8]) -> String {
    String::from_utf8_lossy(payload).into_owned()
}

pub fn parse_product_name(payload: &[u8]) -> String {
    if payload.len() > 1 {
        String::from_utf8_lossy(&payload[1..]).into_owned()
    } else {
        String::new()
    }
}

pub fn parse_cnc(payload: &[u8]) -> (u8, u8) {
    if payload.len() >= 3 {
        (payload[1], payload[0].saturating_sub(1))
    } else {
        (0, 10)
    }
}

pub fn parse_eq(payload: &[u8]) -> Vec<EqBand> {
    let names: &[&str] = &["Bass", "Mid", "Treble"];
    let mut bands = Vec::new();
    let mut i = 0;
    while i + 3 < payload.len() {
        let min_val = payload[i] as i8;
        let max_val = payload[i + 1] as i8;
        let current = payload[i + 2] as i8;
        let band_id = payload[i + 3];
        bands.push(EqBand {
            band_id,
            name: names.get(band_id as usize).copied().unwrap_or("Unknown"),
            current,
            min_val,
            max_val,
        });
        i += 4;
    }
    bands
}

pub fn parse_multipoint(payload: &[u8]) -> bool {
    payload.first().map_or(false, |b| b & 0x02 != 0)
}

pub fn parse_bool(payload: &[u8]) -> bool {
    payload.first().map_or(false, |b| *b != 0)
}

pub fn parse_sidetone(payload: &[u8]) -> &'static str {
    if payload.len() >= 2 {
        match payload[1] {
            0 => "off",
            1 => "high",
            2 => "medium",
            3 => "low",
            _ => "unknown",
        }
    } else {
        "off"
    }
}

pub fn parse_voice_prompts(payload: &[u8]) -> (bool, &'static str) {
    if let Some(&b) = payload.first() {
        let enabled = (b >> 5) & 1 != 0;
        let lang = b & 0x1F;
        let lang_name = match lang {
            0 => "UK English",
            1 => "US English",
            2 => "French",
            3 => "Italian",
            4 => "German",
            5 => "EU Spanish",
            6 => "MX Spanish",
            7 => "BR Portuguese",
            8 => "Mandarin",
            9 => "Korean",
            10 => "Russian",
            11 => "Polish",
            12 => "Hebrew",
            13 => "Turkish",
            14 => "Dutch",
            15 => "Japanese",
            16 => "Cantonese",
            17 => "Arabic",
            18 => "Swedish",
            19 => "Danish",
            20 => "Norwegian",
            21 => "Finnish",
            22 => "Hindi",
            _ => "Unknown",
        };
        (enabled, lang_name)
    } else {
        (false, "Unknown")
    }
}

pub fn parse_anr(payload: &[u8]) -> &'static str {
    match payload.first() {
        Some(0) => "off",
        Some(1) => "high",
        Some(2) => "wind",
        Some(3) => "low",
        _ => "unknown",
    }
}

pub fn parse_buttons(payload: &[u8]) -> Option<ButtonMapping> {
    if payload.len() < 3 {
        return None;
    }
    let bid = payload[0];
    let evt = payload[1];
    let action = payload[2];

    let button_name = match bid {
        0 => "DistalCnc",
        2 => "Vpa",
        3 => "RightShortcut",
        4 => "LeftShortcut",
        128 => "Shortcut",
        _ => "Unknown",
    };

    let event_name = match evt {
        3 => "short_press",
        4 => "single_press",
        5 => "press_and_hold",
        6 => "double_press",
        8 => "triple_press",
        9 => "long_press",
        10 => "very_long_press",
        _ => "unknown",
    };

    let action_name = match action {
        0 => "NotConfigured",
        1 => "VPA",
        2 => "ANC",
        4 => "PlayPause",
        8 => "SwitchDevice",
        11 => "TrackBack",
        14 => "Disabled",
        17 => "ModesCarousel",
        _ => "Unknown",
    };

    Some(ButtonMapping {
        button_id: bid,
        button_name,
        event: evt,
        event_name,
        action,
        action_name,
    })
}

/// Parse a 48-byte ModeConfig STATUS response (QC Ultra 2 / newer firmware).
///
/// STATUS offsets: CNC=42, spatial=44, wind=45, anc=47.
/// This function is passed as `parse_mode_config` in the QC Ultra 2 config.
pub fn parse_mode_config_qc_ultra2(payload: &[u8]) -> Option<ModeConfig> {
    if payload.len() < 6 {
        return None;
    }

    let mode_idx = payload[0];
    let prompt_b1 = payload[1];
    let prompt_b2 = payload[2];

    if payload.len() >= 48 {
        let editable = payload[3] != 0;
        let configured = payload[4] != 0;
        let name_bytes = &payload[6..38];
        let name_end = name_bytes.iter().position(|&b| b == 0).unwrap_or(32);
        let name = String::from_utf8_lossy(&name_bytes[..name_end]).into_owned();

        Some(ModeConfig {
            mode_idx,
            name,
            cnc_level: payload[42],
            spatial: payload[44],
            wind_block: payload[45] != 0,
            anc_toggle: payload[47] != 0,
            editable,
            configured,
            prompt_b1,
            prompt_b2,
        })
    } else if payload.len() >= 40 {
        // SETGET echo format
        let name_bytes = &payload[3..35];
        let name_end = name_bytes.iter().position(|&b| b == 0).unwrap_or(32);
        let name = String::from_utf8_lossy(&name_bytes[..name_end]).into_owned();

        Some(ModeConfig {
            mode_idx,
            name,
            cnc_level: payload[35],
            spatial: payload[37],
            wind_block: payload[38] != 0,
            anc_toggle: payload[39] != 0,
            editable: true,
            configured: true,
            prompt_b1,
            prompt_b2,
        })
    } else {
        None
    }
}

/// Build a 40-byte ModeConfig SETGET payload.
pub fn build_mode_config_40(
    mode_idx: u8, name: &str, cnc_level: u8, spatial: u8,
    wind_block: bool, anc_toggle: bool, prompt_b1: u8, prompt_b2: u8,
) -> Vec<u8> {
    let mut payload = Vec::with_capacity(40);
    payload.push(mode_idx);
    payload.push(prompt_b1);
    payload.push(prompt_b2);
    payload.extend_from_slice(&encode_mode_name(name));
    payload.push(cnc_level);
    payload.push(0); // auto_cnc
    payload.push(spatial);
    payload.push(if wind_block { 1 } else { 0 });
    payload.push(if anc_toggle { 1 } else { 0 });
    payload
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_battery() {
        assert_eq!(parse_battery(&[0x50, 0xff, 0xff, 0x00]), Some(0x50));
        assert_eq!(parse_battery(&[]), None);
    }

    #[test]
    fn test_parse_firmware() {
        let payload = b"8.2.20+g34cf029";
        assert_eq!(parse_firmware(payload), "8.2.20+g34cf029");
    }

    #[test]
    fn test_parse_product_name() {
        let payload = b"\x00Fargo";
        assert_eq!(parse_product_name(payload), "Fargo");
    }

    #[test]
    fn test_parse_cnc() {
        assert_eq!(parse_cnc(&[0x0b, 0x07, 0x03]), (7, 10));
    }

    #[test]
    fn test_parse_eq() {
        let payload = vec![0xf6, 0x0a, 0x03, 0x00, 0xf6, 0x0a, 0xfe, 0x01, 0xf6, 0x0a, 0xfa, 0x02];
        let bands = parse_eq(&payload);
        assert_eq!(bands.len(), 3);
        assert_eq!(bands[0].name, "Bass");
        assert_eq!(bands[0].current, 3);
        assert_eq!(bands[1].current, -2);
        assert_eq!(bands[2].current, -6);
    }

    #[test]
    fn test_parse_multipoint() {
        assert!(parse_multipoint(&[0x07]));
        assert!(!parse_multipoint(&[0x01]));
        assert!(!parse_multipoint(&[]));
    }

    #[test]
    fn test_parse_buttons() {
        let payload = vec![0x80, 0x09, 0x0e, 0x00, 0x09, 0x40, 0x02];
        let btn = parse_buttons(&payload).unwrap();
        assert_eq!(btn.button_name, "Shortcut");
        assert_eq!(btn.event_name, "long_press");
        assert_eq!(btn.action_name, "Disabled");
    }

    #[test]
    fn test_build_mode_config() {
        let payload = build_mode_config_40(5, "Custom", 7, 2, true, true, 0, 0);
        assert_eq!(payload.len(), 40);
        assert_eq!(payload[0], 5);
        assert_eq!(payload[35], 7);  // cnc
        assert_eq!(payload[37], 2);  // spatial
        assert_eq!(payload[38], 1);  // wind_block
        assert_eq!(payload[39], 1);  // anc_toggle
    }
}
