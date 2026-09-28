// Device configurations.
#pragma once

#include "device.h"

namespace bmap {

inline DeviceConfig qc_ultra2() {
    DeviceConfig c;
    c.info = {"Bose QC Ultra Headphones 2", "wolverine", "OTG-QCC-384"};
    c.battery = Addr{2, 2};
    c.firmware = Addr{0, 5};
    c.product_name = Addr{1, 2};
    c.voice_prompts = Addr{1, 3};
    c.cnc = Addr{1, 5};
    c.eq = Addr{1, 7};
    c.buttons = Addr{1, 9};
    c.multipoint = Addr{1, 10};
    c.sidetone = Addr{1, 11};
    c.auto_pause = Addr{1, 24};
    c.auto_answer = Addr{1, 27};
    c.pairing = Addr{4, 8};
    c.routing = Addr{4, 12};
    c.source = Addr{5, 1};
    c.power = Addr{7, 4};
    c.get_all_modes = Addr{31, 1};
    c.current_mode = Addr{31, 3};
    c.mode_config = Addr{31, 6};
    c.favorites = Addr{31, 8};
    c.audio_settings = Addr{31, 10};
    c.preset_modes = {
        {"quiet",     {0, "Quiet — full ANC"}},
        {"aware",     {1, "Aware — transparency"}},
        {"immersion", {2, "Immersion — spatial audio, head tracking"}},
        {"cinema",    {3, "Cinema — spatial audio, fixed stage"}},
    };
    c.editable_slots = {4, 5, 6, 7, 8, 9, 10};
    c.parse_mode_config = parse_mode_config_qc_ultra2;
    c.build_mode_config = build_mode_config_40;
    c.supports_anc_toggle = true;
    return c;
}

/// Bose QuietComfort Ultra Earbuds 2 -- edith, product ID 0x4062.
/// Shares the QC Ultra 2 protocol layout and reports separate battery cells.
inline DeviceConfig qc_ultra2_earbuds() {
    auto c = qc_ultra2();
    c.info = {"Bose QuietComfort Ultra Earbuds (2nd Gen)", "edith", "OTG-QCC-384"};
    c.battery_components = {{1, "Right"}, {2, "Left"}, {3, "Case"}};
    c.battery_aggregate_id = 4;
    return c;
}

/// Bose QuietComfort Headphones -- prince, product ID 0x4075.
/// Verified against firmware 1.0.6-80+f5f219b. RFCOMM channel 8.
inline DeviceConfig qc_prince() {
    DeviceConfig c;
    c.info = {"Bose QuietComfort Headphones", "prince", "Unknown"};
    c.rfcomm_channel = 8;
    c.battery = Addr{2, 2};
    c.firmware = Addr{0, 5};
    c.product_name = Addr{1, 2};
    c.voice_prompts = Addr{1, 3};
    c.cnc = Addr{1, 5};
    c.eq = Addr{1, 7};
    c.pairing = Addr{4, 8};
    c.get_all_modes = Addr{31, 1};
    c.current_mode = Addr{31, 3};
    c.mode_config = Addr{31, 6};
    c.preset_modes = {
        {"quiet", {0, "Quiet - full ANC"}},
        {"aware", {1, "Aware - transparency"}},
    };
    c.editable_slots = {2, 3};
    c.parse_mode_config = parse_mode_config_prince;
    c.build_mode_config = build_mode_config_39;
    c.supports_anc_toggle = false;
    return c;
}

/// Bose QC35 — verified against firmware 4.8.1. RFCOMM channel 8.
/// ANR [1.6] (off/high/wind/low), buttons [1.9] (VPA/ANC remap).
/// Block 3 NC investigated: binary state toggle only, not useful.
inline DeviceConfig qc35() {
    DeviceConfig c;
    c.info = {"Bose QuietComfort 35", "baywolf", "CSR8670"};
    c.rfcomm_channel = 8;
    c.init_packet = Addr{0, 1};  // GET [0.1] required before QC35 responds
    c.battery = Addr{2, 2};
    c.firmware = Addr{0, 5};
    c.product_name = Addr{1, 2};
    c.voice_prompts = Addr{1, 3};
    // cnc [3.2] is auth-gated on fw 4.8.1
    c.sidetone = Addr{1, 11};
    c.buttons = Addr{1, 9};
    c.anr = Addr{1, 6};  // OFF=0, HIGH=1, WIND=2, LOW=3
    c.pairing = Addr{4, 8};
    // No: eq, multipoint, auto_pause, auto_answer, power, AudioModes block 31
    c.preset_modes = {
        {"high", {0, "High — full noise cancellation"}},
        {"low",  {1, "Low — reduced noise cancellation"}},
        {"off",  {2, "Off — no noise cancellation"}},
    };
    return c;
}

/// Bose QuietComfort Earbuds (1st Gen) — codename lando, firmware 2.0.7.
/// Contributed from hardware on #23. Four fixed modes; ModeConfig SETGET is
/// non-functional, so CNC is written directly to [1.5].
inline DeviceConfig qc_earbuds() {
    DeviceConfig c;
    c.info = {"Bose QC Earbuds", "lando", "QCC-384"};
    c.rfcomm_channel = 8;
    c.battery = Addr{2, 2};
    c.firmware = Addr{0, 5};
    c.product_name = Addr{1, 2};
    c.voice_prompts = Addr{1, 3};
    c.cnc = Addr{1, 5};
    c.eq = Addr{1, 7};
    c.buttons = Addr{1, 9};
    c.multipoint = Addr{1, 10};
    c.sidetone = Addr{1, 11};
    c.pairing = Addr{4, 8};
    c.routing = Addr{4, 12};
    c.source = Addr{5, 1};
    c.power = Addr{7, 4};
    c.get_all_modes = Addr{31, 1};
    c.current_mode = Addr{31, 3};
    c.mode_config = Addr{31, 6};
    c.favorites = Addr{31, 8};
    c.preset_modes = {
        {"quiet", {0, "Quiet - full ANC"}},
        {"aware", {1, "Aware - transparency"}},
    };
    c.parse_mode_config = parse_mode_config_44;
    c.supports_anc_toggle = false;
    c.cnc_direct_setget = true;
    return c;
}

/// Bose QuietComfort 45 — codename duran, CSR8670.
/// Layout inferred from the Bose app (#21); unverified on hardware. Shares
/// the prince 47/39-byte ModeConfig format. Needs GET [0.1] before responding.
inline DeviceConfig qc45() {
    DeviceConfig c;
    c.info = {"Bose QuietComfort 45", "duran", "CSR8670"};
    c.rfcomm_channel = 8;
    c.init_packet = Addr{0, 1};
    c.battery = Addr{2, 2};
    c.firmware = Addr{0, 5};
    c.product_name = Addr{1, 2};
    c.voice_prompts = Addr{1, 3};
    c.cnc = Addr{1, 5};
    c.eq = Addr{1, 7};
    c.buttons = Addr{1, 9};
    c.multipoint = Addr{1, 10};
    c.sidetone = Addr{1, 11};
    c.pairing = Addr{4, 8};
    c.get_all_modes = Addr{31, 1};
    c.current_mode = Addr{31, 3};
    c.mode_config = Addr{31, 6};
    c.favorites = Addr{31, 8};
    c.preset_modes = {
        {"quiet", {0, "Quiet - full ANC"}},
        {"aware", {1, "Aware - transparency"}},
    };
    c.editable_slots = {2, 3};
    c.parse_mode_config = parse_mode_config_prince;
    c.build_mode_config = build_mode_config_39;
    c.supports_anc_toggle = false;
    return c;
}

/// Bose Ultra Open Earbuds — codename serena, firmware 4.0.22+g1b923b0.
/// From the #25 device report: reads, Settings SETGET, EQ, and mode
/// switching confirmed. Open-ear, so no CNC. ModeConfig layout inferred
/// from QC Ultra; read-only until a STATUS capture fixes the SETGET format.
inline DeviceConfig ultra_open() {
    DeviceConfig c;
    c.info = {"Bose Ultra Open Earbuds", "serena", "QCC"};
    c.rfcomm_channel = 2;
    c.battery = Addr{2, 2};
    c.firmware = Addr{0, 5};
    c.product_name = Addr{1, 2};
    c.voice_prompts = Addr{1, 3};
    c.eq = Addr{1, 7};
    c.multipoint = Addr{1, 10};
    c.pairing = Addr{4, 8};
    c.source = Addr{5, 1};
    c.power = Addr{7, 4};
    c.get_all_modes = Addr{31, 1};
    c.current_mode = Addr{31, 3};
    c.mode_config = Addr{31, 6};
    c.parse_mode_config = parse_mode_config_qc_ultra2;
    c.supports_anc_toggle = false;
    return c;
}

inline std::optional<DeviceConfig> get_device(const std::string& name) {
    if (name == "qc_ultra2") return qc_ultra2();
    if (name == "qc_ultra2_earbuds") return qc_ultra2_earbuds();
    if (name == "qc35") return qc35();
    if (name == "qc_prince") return qc_prince();
    if (name == "qc_earbuds") return qc_earbuds();
    if (name == "qc45") return qc45();
    if (name == "ultra_open") return ultra_open();
    return std::nullopt;
}

} // namespace bmap
