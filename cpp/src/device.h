// Device configuration and parser types.
#pragma once

#include <array>
#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <vector>

#include "protocol.h"

namespace bmap {

struct Addr {
    uint8_t fblock;
    uint8_t func;
};

struct DeviceInfo {
    std::string name;
    std::string codename;
    std::string platform;
};

struct PresetMode {
    uint8_t idx;
    std::string description;
};

struct ModeConfig {
    uint8_t mode_idx;
    std::string name;
    uint8_t cnc_level;
    uint8_t spatial;
    bool wind_block;
    bool anc_toggle;
    bool editable;
    bool configured;
    uint8_t prompt_b1;
    uint8_t prompt_b2;
};

struct EqBand {
    uint8_t band_id;
    std::string name;
    int8_t current;
    int8_t min_val;
    int8_t max_val;
};

struct ButtonMapping {
    uint8_t button_id;
    std::string button_name;
    uint8_t event;
    std::string event_name;
    uint8_t action;
    std::string action_name;
};

struct DeviceStatus {
    uint8_t battery;
    std::string mode;
    uint8_t mode_idx;
    uint8_t cnc_level;
    uint8_t cnc_max;
    std::vector<EqBand> eq;
    std::string name;
    std::string firmware;
    std::string sidetone;
    bool multipoint;
    bool auto_pause;
    bool prompts_enabled;
    std::string prompts_language;
};

using ModeConfigParser = std::function<std::optional<ModeConfig>(const std::vector<uint8_t>&)>;

struct DeviceConfig {
    DeviceInfo info;
    /// RFCOMM channel for BMAP (2 for newer devices, 8 for QC35).
    uint8_t rfcomm_channel = 2;
    std::optional<Addr> battery;
    std::optional<Addr> firmware;
    std::optional<Addr> product_name;
    std::optional<Addr> voice_prompts;
    std::optional<Addr> cnc;
    std::optional<Addr> eq;
    std::optional<Addr> buttons;
    std::optional<Addr> multipoint;
    std::optional<Addr> sidetone;
    std::optional<Addr> auto_pause;
    std::optional<Addr> auto_answer;
    std::optional<Addr> pairing;
    std::optional<Addr> power;
    std::optional<Addr> get_all_modes;
    std::optional<Addr> current_mode;
    std::optional<Addr> mode_config;
    std::optional<Addr> favorites;
    std::vector<std::pair<std::string, PresetMode>> preset_modes;
    std::vector<uint8_t> editable_slots;
    ModeConfigParser parse_mode_config;
};

// ── Shared Parsers ──────────────────────────────────────────────────────────

inline uint8_t parse_battery(const std::vector<uint8_t>& p) {
    return p.empty() ? 0 : p[0];
}

inline std::string parse_firmware(const std::vector<uint8_t>& p) {
    return {p.begin(), p.end()};
}

inline std::string parse_product_name(const std::vector<uint8_t>& p) {
    return p.size() > 1 ? std::string(p.begin() + 1, p.end()) : "";
}

inline std::pair<uint8_t, uint8_t> parse_cnc(const std::vector<uint8_t>& p) {
    if (p.size() >= 3) return {p[1], static_cast<uint8_t>(p[0] - 1)};
    return {0, 10};
}

inline std::vector<EqBand> parse_eq(const std::vector<uint8_t>& p) {
    const char* names[] = {"Bass", "Mid", "Treble"};
    std::vector<EqBand> bands;
    for (size_t i = 0; i + 3 < p.size(); i += 4) {
        EqBand b;
        b.min_val = static_cast<int8_t>(p[i]);
        b.max_val = static_cast<int8_t>(p[i + 1]);
        b.current = static_cast<int8_t>(p[i + 2]);
        b.band_id = p[i + 3];
        b.name = (b.band_id < 3) ? names[b.band_id] : "Unknown";
        bands.push_back(std::move(b));
    }
    return bands;
}

inline bool parse_multipoint(const std::vector<uint8_t>& p) {
    return !p.empty() && (p[0] & 0x02) != 0;
}

inline bool parse_bool(const std::vector<uint8_t>& p) {
    return !p.empty() && p[0] != 0;
}

inline std::string parse_sidetone(const std::vector<uint8_t>& p) {
    if (p.size() >= 2) {
        switch (p[1]) {
            case 0: return "off";
            case 1: return "high";
            case 2: return "medium";
            case 3: return "low";
        }
    }
    return "off";
}

inline std::pair<bool, std::string> parse_voice_prompts(const std::vector<uint8_t>& p) {
    if (p.empty()) return {false, "Unknown"};
    bool enabled = ((p[0] >> 5) & 1) != 0;
    uint8_t lang = p[0] & 0x1F;
    const char* lang_names[] = {
        "UK English", "US English", "French", "Italian", "German",
        "EU Spanish", "MX Spanish", "BR Portuguese", "Mandarin",
        "Korean", "Russian", "Polish", "Hebrew", "Turkish",
        "Dutch", "Japanese", "Cantonese", "Arabic", "Swedish",
        "Danish", "Norwegian", "Finnish", "Hindi",
    };
    std::string lang_name = (lang < 23) ? lang_names[lang] : "Unknown";
    return {enabled, lang_name};
}

inline std::optional<ButtonMapping> parse_buttons(const std::vector<uint8_t>& p) {
    if (p.size() < 3) return std::nullopt;
    ButtonMapping btn;
    btn.button_id = p[0];
    btn.event = p[1];
    btn.action = p[2];

    auto btn_name = [](uint8_t id) -> std::string {
        switch (id) {
            case 0: return "DistalCnc"; case 2: return "Vpa";
            case 3: return "RightShortcut"; case 4: return "LeftShortcut";
            case 128: return "Shortcut"; default: return "Unknown";
        }
    };
    auto evt_name = [](uint8_t e) -> std::string {
        switch (e) {
            case 3: return "short_press"; case 4: return "single_press";
            case 5: return "press_and_hold"; case 6: return "double_press";
            case 8: return "triple_press"; case 9: return "long_press";
            case 10: return "very_long_press"; default: return "unknown";
        }
    };
    auto act_name = [](uint8_t a) -> std::string {
        switch (a) {
            case 0: return "NotConfigured"; case 1: return "VPA";
            case 2: return "ANC"; case 4: return "PlayPause";
            case 8: return "SwitchDevice"; case 11: return "TrackBack";
            case 14: return "Disabled"; case 17: return "ModesCarousel";
            default: return "Unknown";
        }
    };

    btn.button_name = btn_name(btn.button_id);
    btn.event_name = evt_name(btn.event);
    btn.action_name = act_name(btn.action);
    return btn;
}

// ── QC Ultra 2 Mode Config Parser ───────────────────────────────────────────

inline std::optional<ModeConfig> parse_mode_config_qc_ultra2(const std::vector<uint8_t>& p) {
    if (p.size() < 6) return std::nullopt;

    ModeConfig mc;
    mc.mode_idx = p[0];
    mc.prompt_b1 = p[1];
    mc.prompt_b2 = p[2];

    if (p.size() >= 48) {
        mc.editable = p[3] != 0;
        mc.configured = p[4] != 0;
        auto name_end = std::find(p.data() + 6, p.data() + 38, '\0');
        mc.name = std::string(reinterpret_cast<const char*>(p.data() + 6),
                              reinterpret_cast<const char*>(name_end));
        mc.cnc_level = p[42];
        mc.spatial = p[44];
        mc.wind_block = p[45] != 0;
        mc.anc_toggle = p[47] != 0;
        return mc;
    } else if (p.size() >= 40) {
        mc.editable = true;
        mc.configured = true;
        auto name_end = std::find(p.data() + 3, p.data() + 35, '\0');
        mc.name = std::string(reinterpret_cast<const char*>(p.data() + 3),
                              reinterpret_cast<const char*>(name_end));
        mc.cnc_level = p[35];
        mc.spatial = p[37];
        mc.wind_block = p[38] != 0;
        mc.anc_toggle = p[39] != 0;
        return mc;
    }
    return std::nullopt;
}

// ── Mode Config Builder ─────────────────────────────────────────────────────

inline std::vector<uint8_t> build_mode_config_40(
    uint8_t mode_idx, const std::string& name, uint8_t cnc_level, uint8_t spatial,
    bool wind_block, bool anc_toggle, uint8_t prompt_b1 = 0, uint8_t prompt_b2 = 0)
{
    std::vector<uint8_t> payload;
    payload.reserve(40);
    payload.push_back(mode_idx);
    payload.push_back(prompt_b1);
    payload.push_back(prompt_b2);
    auto encoded = encode_mode_name(name);
    payload.insert(payload.end(), encoded.begin(), encoded.end());
    payload.push_back(cnc_level);
    payload.push_back(0); // auto_cnc
    payload.push_back(spatial);
    payload.push_back(wind_block ? 1 : 0);
    payload.push_back(anc_toggle ? 1 : 0);
    return payload;
}

} // namespace bmap
