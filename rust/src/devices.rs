//! Device configurations.

use crate::device::{
    Addr, DeviceConfig, DeviceInfo, PresetMode,
    build_mode_config_39, build_mode_config_40,
    parse_mode_config_44, parse_mode_config_prince, parse_mode_config_qc_ultra2,
};

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
        battery_components: &[],
        battery_aggregate_id: None,
        battery_aggregate_sources: &[],
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
        routing: Some(Addr(4, 12)),
        source: Some(Addr(5, 1)),
        power: Some(Addr(7, 4)),
        get_all_modes: Some(Addr(31, 1)),
        current_mode: Some(Addr(31, 3)),
        mode_config: Some(Addr(31, 6)),
        favorites: Some(Addr(31, 8)),
        audio_settings: Some(Addr(31, 10)),
        preset_modes: &[
            ("quiet", PresetMode { idx: 0, description: "Quiet — full ANC" }),
            ("aware", PresetMode { idx: 1, description: "Aware — transparency" }),
            ("immersion", PresetMode { idx: 2, description: "Immersion — spatial audio, head tracking" }),
            ("cinema", PresetMode { idx: 3, description: "Cinema — spatial audio, fixed stage" }),
        ],
        editable_slots: &[4, 5, 6, 7, 8, 9, 10],
        parse_mode_config: Some(parse_mode_config_qc_ultra2),
        build_mode_config: Some(build_mode_config_40),
        supports_anc_toggle: true,
        cnc_direct_setget: false,
    }
}

/// Bose QuietComfort Ultra Earbuds 2 configuration -- edith, product ID 0x4062.
/// Shares the QC Ultra 2 protocol layout and reports separate battery cells.
pub fn qc_ultra2_earbuds() -> DeviceConfig {
    let mut c = qc_ultra2();
    c.info = DeviceInfo {
        name: "Bose QuietComfort Ultra Earbuds (2nd Gen)",
        codename: "edith",
        platform: "OTG-QCC-384",
    };
    c.battery_components = &[(1, "Right"), (2, "Left"), (3, "Case")];
    c.battery_aggregate_id = Some(4);
    c.battery_aggregate_sources = &[1, 2];
    c
}

/// Bose QuietComfort Headphones configuration -- prince, product ID 0x4075.
/// Verified against firmware 1.0.6-80+f5f219b.
/// BMAP over RFCOMM channel 8 with 47-byte ModeConfig STATUS responses.
pub fn qc_prince() -> DeviceConfig {
    DeviceConfig {
        info: DeviceInfo {
            name: "Bose QuietComfort Headphones",
            codename: "prince",
            platform: "Unknown",
        },
        rfcomm_channel: 8,
        init_packet: None,
        battery: Some(Addr(2, 2)),
        battery_components: &[],
        battery_aggregate_id: None,
        battery_aggregate_sources: &[],
        firmware: Some(Addr(0, 5)),
        product_name: Some(Addr(1, 2)),
        voice_prompts: Some(Addr(1, 3)),
        cnc: Some(Addr(1, 5)),
        eq: Some(Addr(1, 7)),
        buttons: None,
        multipoint: None,
        sidetone: None,
        auto_pause: None,
        auto_answer: None,
        anr: None,
        pairing: Some(Addr(4, 8)),
        routing: None,
        source: None,
        power: None,
        get_all_modes: Some(Addr(31, 1)),
        current_mode: Some(Addr(31, 3)),
        mode_config: Some(Addr(31, 6)),
        favorites: None,
        audio_settings: None,
        preset_modes: &[
            ("quiet", PresetMode { idx: 0, description: "Quiet - full ANC" }),
            ("aware", PresetMode { idx: 1, description: "Aware - transparency" }),
        ],
        editable_slots: &[2, 3],
        parse_mode_config: Some(parse_mode_config_prince),
        build_mode_config: Some(build_mode_config_39),
        supports_anc_toggle: false,
        cnc_direct_setget: false,
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
        battery_components: &[],
        battery_aggregate_id: None,
        battery_aggregate_sources: &[],
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
        routing: None,
        source: None,
        power: None, // block 7 not supported
        get_all_modes: None,
        current_mode: None,
        mode_config: None,
        favorites: None,
        audio_settings: None,
        preset_modes: &[
            ("high", PresetMode { idx: 0, description: "High — full noise cancellation" }),
            ("low", PresetMode { idx: 1, description: "Low — reduced noise cancellation" }),
            ("off", PresetMode { idx: 2, description: "Off — no noise cancellation" }),
        ],
        editable_slots: &[],
        parse_mode_config: None,
        build_mode_config: None,
        supports_anc_toggle: false,
        cnc_direct_setget: false,
    }
}

/// Look up a device config by name.
/// Bose QuietComfort Earbuds (1st Gen) — codename lando, firmware 2.0.7.
/// Contributed from hardware on #23. Four fixed modes; ModeConfig SETGET is
/// non-functional, so CNC is written directly to [1.5].
pub fn qc_earbuds() -> DeviceConfig {
    DeviceConfig {
        info: DeviceInfo {
            name: "Bose QC Earbuds",
            codename: "lando",
            platform: "QCC-384",
        },
        rfcomm_channel: 8,
        init_packet: None,
        battery: Some(Addr(2, 2)),
        battery_components: &[],
        battery_aggregate_id: None,
        battery_aggregate_sources: &[],
        firmware: Some(Addr(0, 5)),
        product_name: Some(Addr(1, 2)),
        voice_prompts: Some(Addr(1, 3)),
        cnc: Some(Addr(1, 5)),
        eq: Some(Addr(1, 7)),
        buttons: Some(Addr(1, 9)),
        multipoint: Some(Addr(1, 10)),
        sidetone: Some(Addr(1, 11)),
        auto_pause: None,
        auto_answer: None,
        anr: None,
        pairing: Some(Addr(4, 8)),
        routing: Some(Addr(4, 12)),
        source: Some(Addr(5, 1)),
        power: Some(Addr(7, 4)),
        get_all_modes: Some(Addr(31, 1)),
        current_mode: Some(Addr(31, 3)),
        mode_config: Some(Addr(31, 6)),
        favorites: Some(Addr(31, 8)),
        audio_settings: None,
        preset_modes: &[
            ("quiet", PresetMode { idx: 0, description: "Quiet - full ANC" }),
            ("aware", PresetMode { idx: 1, description: "Aware - transparency" }),
        ],
        editable_slots: &[],
        parse_mode_config: Some(parse_mode_config_44),
        build_mode_config: None,
        supports_anc_toggle: false,
        cnc_direct_setget: true,
    }
}

/// Bose QuietComfort 45 — codename duran, CSR8670.
/// Layout inferred from the Bose app (#21); unverified on hardware. Shares
/// the prince 47/39-byte ModeConfig format. Needs GET [0.1] before responding.
pub fn qc45() -> DeviceConfig {
    DeviceConfig {
        info: DeviceInfo {
            name: "Bose QuietComfort 45",
            codename: "duran",
            platform: "CSR8670",
        },
        rfcomm_channel: 8,
        init_packet: Some(Addr(0, 1)),
        battery: Some(Addr(2, 2)),
        battery_components: &[],
        battery_aggregate_id: None,
        battery_aggregate_sources: &[],
        firmware: Some(Addr(0, 5)),
        product_name: Some(Addr(1, 2)),
        voice_prompts: Some(Addr(1, 3)),
        cnc: Some(Addr(1, 5)),
        eq: Some(Addr(1, 7)),
        buttons: Some(Addr(1, 9)),
        multipoint: Some(Addr(1, 10)),
        sidetone: Some(Addr(1, 11)),
        auto_pause: None,
        auto_answer: None,
        anr: None,
        pairing: Some(Addr(4, 8)),
        routing: None,
        source: None,
        power: None,
        get_all_modes: Some(Addr(31, 1)),
        current_mode: Some(Addr(31, 3)),
        mode_config: Some(Addr(31, 6)),
        favorites: Some(Addr(31, 8)),
        audio_settings: None,
        preset_modes: &[
            ("quiet", PresetMode { idx: 0, description: "Quiet - full ANC" }),
            ("aware", PresetMode { idx: 1, description: "Aware - transparency" }),
        ],
        editable_slots: &[2, 3],
        parse_mode_config: Some(parse_mode_config_prince),
        build_mode_config: Some(build_mode_config_39),
        supports_anc_toggle: false,
        cnc_direct_setget: false,
    }
}

/// Bose Ultra Open Earbuds — codename serena, firmware 4.0.22+g1b923b0.
/// From the #25 device report: reads, Settings SETGET, EQ, and mode
/// switching confirmed. Open-ear, so no CNC. ModeConfig layout inferred
/// from QC Ultra; read-only until a STATUS capture fixes the SETGET format.
pub fn ultra_open() -> DeviceConfig {
    DeviceConfig {
        info: DeviceInfo {
            name: "Bose Ultra Open Earbuds",
            codename: "serena",
            platform: "QCC",
        },
        rfcomm_channel: 2,
        init_packet: None,
        battery: Some(Addr(2, 2)),
        battery_components: &[],
        battery_aggregate_id: None,
        battery_aggregate_sources: &[],
        firmware: Some(Addr(0, 5)),
        product_name: Some(Addr(1, 2)),
        voice_prompts: Some(Addr(1, 3)),
        cnc: None,
        eq: Some(Addr(1, 7)),
        buttons: None,
        multipoint: Some(Addr(1, 10)),
        sidetone: None,
        auto_pause: None,
        auto_answer: None,
        anr: None,
        pairing: Some(Addr(4, 8)),
        routing: None,
        source: Some(Addr(5, 1)),
        power: Some(Addr(7, 4)),
        get_all_modes: Some(Addr(31, 1)),
        current_mode: Some(Addr(31, 3)),
        mode_config: Some(Addr(31, 6)),
        favorites: None,
        audio_settings: None,
        preset_modes: &[],
        editable_slots: &[],
        parse_mode_config: Some(parse_mode_config_qc_ultra2),
        build_mode_config: None,
        supports_anc_toggle: false,
        cnc_direct_setget: false,
    }
}

pub fn get_device(name: &str) -> Option<DeviceConfig> {
    match name {
        "qc_ultra2" => Some(qc_ultra2()),
        "qc_ultra2_earbuds" => Some(qc_ultra2_earbuds()),
        "qc35" => Some(qc35()),
        "qc_prince" => Some(qc_prince()),
        "qc_earbuds" => Some(qc_earbuds()),
        "qc45" => Some(qc45()),
        "ultra_open" => Some(ultra_open()),
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
        assert!(dev.build_mode_config.is_some());
    }

    #[test]
    fn test_qc_prince_channel_and_mode_layout() {
        let dev = qc_prince();
        assert_eq!(dev.info.codename, "prince");
        assert_eq!(dev.rfcomm_channel, 8);
        assert!(dev.mode_config.is_some());
        assert!(dev.eq.is_some());
        assert!(dev.audio_settings.is_none());
        assert!(!dev.supports_anc_toggle);
        assert_eq!(dev.editable_slots, &[2, 3]);
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
        assert!(get_device("qc_ultra2_earbuds").is_some());
        assert!(get_device("qc35").is_some());
        assert!(get_device("qc_prince").is_some());
        assert!(get_device("qc_earbuds").is_some());
        assert!(get_device("qc45").is_some());
        assert!(get_device("ultra_open").is_some());
        assert!(get_device("nonexistent").is_none());
    }

    #[test]
    fn test_qc_ultra2_earbuds_identity_and_battery_components() {
        let dev = qc_ultra2_earbuds();
        assert_eq!(dev.info.codename, "edith");
        assert_eq!(dev.battery_components, &[(1, "Right"), (2, "Left"), (3, "Case")]);
        assert_eq!(dev.battery_aggregate_id, Some(4));
        assert_eq!(dev.battery_aggregate_sources, &[1, 2]);
        assert_eq!(dev.preset_modes.len(), 4);
        assert!(dev.audio_settings.is_some());
    }

    #[test]
    fn test_qc_earbuds_direct_cnc_no_profile_editing() {
        let dev = qc_earbuds();
        assert!(dev.cnc_direct_setget);
        assert!(dev.build_mode_config.is_none());
        assert!(dev.editable_slots.is_empty());
        assert!(dev.audio_settings.is_none());
    }

    #[test]
    fn test_qc45_shares_prince_mode_layout() {
        let dev = qc45();
        assert!(matches!(dev.init_packet, Some(Addr(0, 1))));
        assert!(dev.eq.is_some());
        assert!(!dev.supports_anc_toggle);
        assert_eq!(dev.editable_slots, &[2, 3]);
    }
}
