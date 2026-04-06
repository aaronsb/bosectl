//! Device configurations.

use crate::device::{Addr, DeviceConfig, DeviceInfo, PresetMode, parse_mode_config_qc_ultra2};

/// Bose QC Ultra 2 configuration.
pub fn qc_ultra2() -> DeviceConfig {
    DeviceConfig {
        info: DeviceInfo {
            name: "Bose QC Ultra Headphones 2",
            codename: "wolverine",
            platform: "OTG-QCC-384",
        },
        rfcomm_channel: 2,
        init_packet: None,
        battery: Some(Addr(2, 2)),
        firmware: Some(Addr(0, 5)),
        product_name: Some(Addr(1, 2)),
        voice_prompts: Some(Addr(1, 3)),
        cnc: Some(Addr(1, 5)),
        eq: Some(Addr(1, 7)),
        buttons: Some(Addr(1, 9)),
        multipoint: Some(Addr(1, 10)),
        sidetone: Some(Addr(1, 11)),
        auto_pause: Some(Addr(1, 24)),
        auto_answer: Some(Addr(1, 27)),
        anr: None,
        pairing: Some(Addr(4, 8)),
        power: Some(Addr(7, 4)),
        get_all_modes: Some(Addr(31, 1)),
        current_mode: Some(Addr(31, 3)),
        mode_config: Some(Addr(31, 6)),
        favorites: Some(Addr(31, 8)),
        preset_modes: &[
            ("quiet", PresetMode { idx: 0, description: "Quiet — full ANC" }),
            ("aware", PresetMode { idx: 1, description: "Aware — transparency" }),
            ("immersion", PresetMode { idx: 2, description: "Immersion — spatial audio, head tracking" }),
            ("cinema", PresetMode { idx: 3, description: "Cinema — spatial audio, fixed stage" }),
        ],
        editable_slots: &[4, 5, 6, 7, 8, 9, 10],
        parse_mode_config: Some(parse_mode_config_qc_ultra2),
    }
}

/// Bose QC35 configuration — verified against firmware 4.8.1.
/// BMAP over RFCOMM channel 8.
/// ANR [1.6] (off/high/wind/low), buttons [1.9] (VPA/ANC remap).
/// Block 3 NC investigated: binary state toggle only, not useful.
pub fn qc35() -> DeviceConfig {
    DeviceConfig {
        info: DeviceInfo {
            name: "Bose QuietComfort 35",
            codename: "baywolf",
            platform: "CSR8670",
        },
        rfcomm_channel: 8,
        init_packet: Some(Addr(0, 1)),  // GET [0.1] required before QC35 responds
        battery: Some(Addr(2, 2)),
        firmware: Some(Addr(0, 5)),
        product_name: Some(Addr(1, 2)),
        voice_prompts: Some(Addr(1, 3)),
        cnc: None,
        eq: None,
        buttons: Some(Addr(1, 9)),
        multipoint: None, // [1.10] not supported
        sidetone: Some(Addr(1, 11)),
        auto_pause: None, // [1.24] not supported
        auto_answer: None,
        anr: Some(Addr(1, 6)),  // OFF=0, HIGH=1, WIND=2, LOW=3
        pairing: Some(Addr(4, 8)),
        power: None, // block 7 not supported
        get_all_modes: None,
        current_mode: None,
        mode_config: None,
        favorites: None,
        preset_modes: &[
            ("high", PresetMode { idx: 0, description: "High — full noise cancellation" }),
            ("low", PresetMode { idx: 1, description: "Low — reduced noise cancellation" }),
            ("off", PresetMode { idx: 2, description: "Off — no noise cancellation" }),
        ],
        editable_slots: &[],
        parse_mode_config: None,
    }
}

/// Look up a device config by name.
pub fn get_device(name: &str) -> Option<DeviceConfig> {
    match name {
        "qc_ultra2" => Some(qc_ultra2()),
        "qc35" => Some(qc35()),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_qc_ultra2_has_all_features() {
        let dev = qc_ultra2();
        assert!(dev.battery.is_some());
        assert!(dev.eq.is_some());
        assert!(dev.mode_config.is_some());
        assert_eq!(dev.preset_modes.len(), 4);
        assert_eq!(dev.editable_slots.len(), 7);
    }

    #[test]
    fn test_qc35_no_eq() {
        let dev = qc35();
        assert!(dev.eq.is_none());
        assert!(dev.mode_config.is_none());
        assert!(dev.editable_slots.is_empty());
    }

    #[test]
    fn test_get_device() {
        assert!(get_device("qc_ultra2").is_some());
        assert!(get_device("qc35").is_some());
        assert!(get_device("nonexistent").is_none());
    }
}
