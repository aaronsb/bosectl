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
    c.power = Addr{7, 4};
    c.get_all_modes = Addr{31, 1};
    c.current_mode = Addr{31, 3};
    c.mode_config = Addr{31, 6};
    c.favorites = Addr{31, 8};
    c.preset_modes = {
        {"quiet",     {0, "Quiet — full ANC"}},
        {"aware",     {1, "Aware — transparency"}},
        {"immersion", {2, "Immersion — spatial audio, head tracking"}},
        {"cinema",    {3, "Cinema — spatial audio, fixed stage"}},
    };
    c.editable_slots = {4, 5, 6, 7, 8, 9, 10};
    c.parse_mode_config = parse_mode_config_qc_ultra2;
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

inline std::optional<DeviceConfig> get_device(const std::string& name) {
    if (name == "qc_ultra2") return qc_ultra2();
    if (name == "qc35") return qc35();
    return std::nullopt;
}

} // namespace bmap
