// High-level BMAP device connection.
#pragma once

#include <algorithm>
#include <array>
#include <cctype>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "device.h"
#include "errors.h"
#include "protocol.h"
#include "transport.h"

namespace bmap {

/// The device name field is 32 bytes on every BMAP device seen so far.
inline constexpr size_t MAX_NAME_BYTES = 31;

namespace detail {

inline std::string trim_lower(const std::string& s) {
    auto b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return "";
    auto e = s.find_last_not_of(" \t\r\n");
    std::string out = s.substr(b, e - b + 1);
    for (auto& c : out) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return out;
}

inline bool iequals(const std::string& a, const std::string& b) {
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); i++) {
        if (std::tolower(static_cast<unsigned char>(a[i])) !=
            std::tolower(static_cast<unsigned char>(b[i]))) return false;
    }
    return true;
}

} // namespace detail

class BmapConnection {
public:
    BmapConnection(std::unique_ptr<Transport> transport, DeviceConfig config)
        : transport_(std::move(transport)), config_(std::move(config)) {}

    const DeviceConfig& config() const { return config_; }

    // ── Read Operations ─────────────────────────────────────────────────────

    uint8_t battery() {
        return battery_status().aggregate;
    }
    BatteryStatus battery_status() {
        auto payload = get(require(config_.battery, "battery"));
        if (config_.battery_aggregate_id) {
            auto readings = parse_battery_readings(payload);
            for (const auto& reading : readings) {
                if (reading.component_id == *config_.battery_aggregate_id)
                    return {reading.level, std::move(readings)};
            }
            // Aggregate missing or 0xFF: fall back to the lowest bud reading.
            std::optional<uint8_t> lowest;
            for (const auto& reading : readings) {
                const auto& sources = config_.battery_aggregate_sources;
                if (std::find(sources.begin(), sources.end(), reading.component_id) ==
                    sources.end())
                    continue;
                if (!lowest || reading.level < *lowest) lowest = reading.level;
            }
            if (lowest) return {*lowest, std::move(readings)};
            throw std::runtime_error(
                "Battery response missing aggregate component " +
                std::to_string(*config_.battery_aggregate_id));
        }
        if (payload.empty())
            throw std::runtime_error("Empty battery response");
        return {parse_battery(payload), {}};
    }
    std::vector<BatteryReading> battery_readings() {
        return battery_status().readings;
    }
    std::string firmware()                { return parse_firmware(get(require(config_.firmware, "firmware"))); }
    std::string name()                    { return parse_product_name(get(require(config_.product_name, "product_name"))); }
    std::pair<uint8_t, uint8_t> cnc()     { return parse_cnc(get(require(config_.cnc, "cnc"))); }
    std::vector<EqBand> eq()              { return parse_eq(get(require(config_.eq, "eq"))); }
    std::string sidetone()                { return parse_sidetone(get(require(config_.sidetone, "sidetone"))); }
    bool multipoint()                     { return parse_multipoint(get(require(config_.multipoint, "multipoint"))); }
    bool auto_pause()                     { return parse_bool(get(require(config_.auto_pause, "auto_pause"))); }
    bool auto_answer()                    { return parse_bool(get(require(config_.auto_answer, "auto_answer"))); }
    std::pair<bool, std::string> prompts(){ return parse_voice_prompts(get(require(config_.voice_prompts, "voice_prompts"))); }
    AudioSource source()                 { return parse_source(get(require(config_.source, "source"))); }
    std::string anr()                    { return parse_anr(get(require(config_.anr, "anr"))); }
    std::optional<ButtonMapping> buttons(){ return parse_buttons(get(require(config_.buttons, "buttons"))); }

    uint8_t mode_idx() {
        auto p = get(require(config_.current_mode, "current_mode"));
        return p.empty() ? 0 : p[0];
    }

    std::string mode() {
        return mode_name_from_idx(mode_idx());
    }

    std::vector<ModeConfig> modes() {
        auto addr = require(config_.get_all_modes, "get_all_modes");
        auto mc_addr = require(config_.mode_config, "mode_config");
        auto responses = start_drain(addr, {});
        std::vector<ModeConfig> result;
        for (auto& r : responses) {
            if (r.fblock == mc_addr.fblock && r.func == mc_addr.func &&
                r.op == Operator::Status && r.payload.size() >= 6 && config_.parse_mode_config) {
                auto mc = config_.parse_mode_config(r.payload);
                if (mc) result.push_back(std::move(*mc));
            }
        }
        return result;
    }

    bool has_feature(const std::string& name) const {
        if (name == "battery") return config_.battery.has_value();
        if (name == "firmware") return config_.firmware.has_value();
        if (name == "product_name") return config_.product_name.has_value();
        if (name == "voice_prompts") return config_.voice_prompts.has_value();
        if (name == "cnc") return config_.cnc.has_value();
        if (name == "eq") return config_.eq.has_value();
        if (name == "buttons") return config_.buttons.has_value();
        if (name == "multipoint") return config_.multipoint.has_value();
        if (name == "sidetone") return config_.sidetone.has_value();
        if (name == "auto_pause") return config_.auto_pause.has_value();
        if (name == "auto_answer") return config_.auto_answer.has_value();
        if (name == "anr") return config_.anr.has_value();
        if (name == "routing") return config_.routing.has_value();
        if (name == "source") return config_.source.has_value();
        if (name == "audio_settings") return config_.audio_settings.has_value();
        if (name == "mode_config") return config_.mode_config.has_value();
        return false;
    }

    DeviceStatus status() {
        auto idx = safe_call<uint8_t>([&]{ return mode_idx(); }, 0);
        auto mode_name = safe_call<std::string>([&]{ return mode_name_from_idx(idx); }, "");
        auto [cnc_cur, cnc_max] = safe_call<std::pair<uint8_t,uint8_t>>(
            [&]{ return cnc(); }, {0, 10});
        auto [prom_on, prom_lang] = safe_call<std::pair<bool,std::string>>(
            [&]{ return prompts(); }, {false, ""});
        auto battery_state = battery_status();

        DeviceStatus s;
        s.battery = battery_state.aggregate;
        s.battery_readings = std::move(battery_state.readings);
        s.mode = mode_name;
        s.mode_idx = idx;
        s.cnc_level = cnc_cur;
        s.cnc_max = cnc_max;
        s.eq = safe_call<std::vector<EqBand>>([&]{ return eq(); }, {});
        s.name = safe_call<std::string>([&]{ return this->name(); }, "");
        s.firmware = safe_call<std::string>([&]{ return this->firmware(); }, "");
        s.sidetone = safe_call<std::string>([&]{ return sidetone(); }, "off");
        s.multipoint = safe_call<bool>([&]{ return multipoint(); }, false);
        s.auto_pause = safe_call<bool>([&]{ return auto_pause(); }, false);
        s.prompts_enabled = prom_on;
        s.prompts_language = prom_lang;
        return s;
    }

    // ── Write Operations ────────────────────────────────────────────────────

    void set_mode(const std::string& name, bool announce = false) {
        auto addr = require(config_.current_mode, "current_mode");
        uint8_t idx = 255;
        for (auto& [n, m] : config_.preset_modes) {
            if (detail::iequals(n, name)) { idx = m.idx; break; }
        }
        if (idx == 255) {
            auto all = modes();
            for (auto& m : all) {
                if (detail::iequals(m.name, name)) { idx = m.mode_idx; break; }
            }
        }
        if (idx == 255) throw std::invalid_argument("Unknown mode: " + name);
        start(addr, {idx, static_cast<uint8_t>(announce ? 1 : 0)});
    }

    void set_cnc(uint8_t level) {
        if (level > 10) throw std::runtime_error("CNC level must be 0-10");
        if (config_.cnc_direct_setget) {
            setget(require(config_.cnc, "cnc"), {level, 1});
            return;
        }
        update_audio_settings(level, 255, 255, 255);
    }

    void set_spatial(const std::string& mode) {
        uint8_t val;
        if (mode == "off") val = 0;
        else if (mode == "room") val = 1;
        else if (mode == "head") val = 2;
        else throw std::runtime_error("Spatial: off, room, head");
        update_audio_settings(255, val, 255, 255);
    }

    void set_anc(bool enabled) {
        update_audio_settings(255, 255, 255, enabled ? 1 : 0);
    }

    void set_wind(bool enabled) {
        update_audio_settings(255, 255, enabled ? 1 : 0, 255);
    }

    // Returns (cnc, auto_cnc, spatial, wind, anc)
    std::array<uint8_t, 5> audio_settings() {
        if (config_.audio_settings) {
            auto p = get(*config_.audio_settings);
            std::array<uint8_t, 5> out = {0, 0, 0, 1, 1};
            for (size_t i = 0; i < 5 && i < p.size(); i++) out[i] = p[i];
            return out;
        }
        auto mc = current_mode_config();
        return {mc.cnc_level, 0, mc.spatial,
                static_cast<uint8_t>(mc.wind_block ? 1 : 0),
                static_cast<uint8_t>(mc.anc_toggle ? 1 : 0)};
    }

    void set_eq(int8_t bass, int8_t mid, int8_t treble) {
        auto addr = require(config_.eq, "eq");
        for (auto [band_id, val] : std::vector<std::pair<uint8_t,int8_t>>{{0,bass},{1,mid},{2,treble}}) {
            setget(addr, {static_cast<uint8_t>(val), band_id});
        }
    }

    void set_name(const std::string& new_name) {
        if (new_name.size() > MAX_NAME_BYTES) {
            throw std::invalid_argument("Name must be at most " +
                std::to_string(MAX_NAME_BYTES) + " bytes of UTF-8");
        }
        std::vector<uint8_t> payload(new_name.begin(), new_name.end());
        setget(require(config_.product_name, "product_name"), payload);
    }

    void set_multipoint(bool on) {
        setget(require(config_.multipoint, "multipoint"), {static_cast<uint8_t>(on ? 1 : 0)});
    }

    void set_auto_pause(bool on) {
        setget(require(config_.auto_pause, "auto_pause"), {static_cast<uint8_t>(on ? 1 : 0)});
    }

    void set_auto_answer(bool on) {
        setget(require(config_.auto_answer, "auto_answer"), {static_cast<uint8_t>(on ? 1 : 0)});
    }

    void set_anr(const std::string& level) {
        uint8_t val;
        if (level == "off") val = 0;
        else if (level == "high") val = 1;
        else if (level == "wind") val = 2;
        else if (level == "low") val = 3;
        else throw std::runtime_error("ANR: off, high, wind, low");
        setget(require(config_.anr, "anr"), {val});
    }

    void set_prompts(bool enabled) {
        auto addr = require(config_.voice_prompts, "voice_prompts");
        auto payload = get(addr);
        uint8_t lang = payload.empty() ? 0 : (payload[0] & 0x1F);
        uint8_t byte0 = ((enabled ? 1 : 0) << 5) | lang;
        setget(addr, {byte0});
    }

    void set_sidetone(const std::string& level) {
        uint8_t val;
        if (level == "off") val = 0;
        else if (level == "high") val = 1;
        else if (level == "medium") val = 2;
        else if (level == "low") val = 3;
        else throw std::runtime_error("Sidetone: off, low, medium, high");
        setget(require(config_.sidetone, "sidetone"), {1, val});
    }

    ButtonMapping set_buttons(uint8_t button_id, uint8_t event, uint8_t action) {
        auto addr = require(config_.buttons, "buttons");
        auto resp = setget(addr, build_buttons(button_id, event, action));
        auto result = parse_buttons(resp.payload);
        if (!result) throw device_error("Could not parse button remap response");
        return *result;
    }

    void route(const std::string& mac) {
        auto payload = build_routing(mac);
        start(require(config_.routing, "routing"), payload);
    }

    void power_off() { start(require(config_.power, "power"), {0x00}); }
    void pair()      { start(require(config_.pairing, "pairing"), {0x01}); }

    // ── Profile Management ──────────────────────────────────────────────────

    uint8_t create_profile(const std::string& name, uint8_t cnc = 0, uint8_t spatial = 0,
                           bool wind = true, bool anc = true) {
        auto all = modes();
        refuse_preset_name(name, all);
        auto slot = find_free_slot(all);
        ModeConfig mc{};
        mc.mode_idx = slot;
        mc.name = name;
        mc.cnc_level = cnc;
        mc.spatial = spatial;
        mc.wind_block = wind;
        mc.anc_toggle = anc;
        write_mode(slot, mc);
        return slot;
    }

    void delete_profile(const std::string& name) {
        auto all = modes();
        // Prefer an editable slot: a custom profile may share a preset's name,
        // and matching the preset first makes that profile undeletable.
        const ModeConfig* match = nullptr;
        for (auto& m : all) {
            if (!detail::iequals(m.name, name)) continue;
            if (m.editable) { match = &m; break; }
            if (!match) match = &m;
        }
        if (!match) throw std::invalid_argument("Profile '" + name + "' not found");
        if (!match->editable) throw std::invalid_argument("Cannot delete preset '" + name + "'");

        ModeConfig mc{};
        mc.mode_idx = match->mode_idx;
        mc.name = "None";
        write_mode(match->mode_idx, mc);
    }

    std::vector<BmapResponse> send_raw(const std::vector<uint8_t>& data) {
        auto resp = transport_->send_recv_drain(data);
        return parse_all_responses(resp);
    }

private:
    std::unique_ptr<Transport> transport_;
    DeviceConfig config_;

    static Addr require(const std::optional<Addr>& opt, const char* name) {
        if (!opt) throw std::runtime_error(std::string(name) + " not supported on this device");
        return *opt;
    }

    // Reject a response that came from a different address.
    //
    // The firmware answers in order, so after a reconnect the socket can still
    // hold responses queued before the drop and every read returns the previous
    // request's answer. Without this check the payload is handed to the wrong
    // parser and surfaces as plausible-looking data.
    void check_address(const BmapResponse& resp, Addr addr) {
        if (resp.fblock != addr.fblock || resp.func != addr.func) {
            throw desync_error(
                "Response came from [" + std::to_string(resp.fblock) + "." +
                std::to_string(resp.func) + "], expected [" +
                std::to_string(addr.fblock) + "." + std::to_string(addr.func) +
                "]. Reopen the connection.");
        }
    }

    // Validate a single reply: present, from the right address, not ERROR.
    // Every single-reply path (GET, SETGET, START) goes through here so a
    // truncated frame, a desynced socket or a device error surface the same
    // way in all of them.
    BmapResponse check_reply(const std::vector<uint8_t>& data, Addr addr) {
        auto resp = parse_response(data);
        if (!resp) throw device_error("Invalid or empty response");
        check_address(*resp, addr);
        check_error(*resp);
        return *resp;
    }

    std::vector<uint8_t> get(Addr addr) {
        auto pkt = bmap_packet(addr.fblock, addr.func, Operator::Get);
        return check_reply(transport_->send_recv(pkt), addr).payload;
    }

    BmapResponse setget(Addr addr, const std::vector<uint8_t>& payload) {
        auto pkt = bmap_packet(addr.fblock, addr.func, Operator::SetGet, payload);
        return check_reply(transport_->send_recv(pkt), addr);
    }

    BmapResponse start(Addr addr, const std::vector<uint8_t>& payload) {
        auto pkt = bmap_packet(addr.fblock, addr.func, Operator::Start, payload);
        return check_reply(transport_->send_recv(pkt), addr);
    }

    std::vector<BmapResponse> start_drain(Addr addr, const std::vector<uint8_t>& payload) {
        auto pkt = bmap_packet(addr.fblock, addr.func, Operator::Start, payload);
        auto data = transport_->send_recv_drain(pkt);
        return parse_all_responses(data);
    }

    void check_error(const BmapResponse& resp) {
        if (resp.op == Operator::Error && !resp.payload.empty()) {
            throw device_error(resp.fmt(), resp.payload[0]);
        }
    }

    std::string mode_name_from_idx(uint8_t idx) {
        for (auto& [name, preset] : config_.preset_modes) {
            if (preset.idx == idx) return name;
        }
        try {
            auto all = modes();
            for (auto& m : all) {
                if (m.mode_idx == idx) return m.name;
            }
        } catch (...) {}
        return "custom(" + std::to_string(idx) + ")";
    }

    template<typename T, typename F>
    T safe_call(F fn, T default_val) {
        try { return fn(); } catch (...) { return default_val; }
    }

    // Write audio settings via [31.10] preserving non-overridden fields.
    // Use 255 as "don't change" for any parameter.
    void update_audio_settings(uint8_t cnc, uint8_t spatial, uint8_t wind, uint8_t anc) {
        if (config_.audio_settings) {
            auto cur = get(*config_.audio_settings);
            std::vector<uint8_t> p = {0, 0, 0, 1, 1};
            for (size_t i = 0; i < 5 && i < cur.size(); i++) p[i] = cur[i];
            if (cnc != 255) p[0] = cnc;
            if (spatial != 255) p[2] = spatial;
            if (wind != 255) p[3] = wind;
            if (anc != 255) p[4] = anc;
            setget(*config_.audio_settings, p);
            return;
        }
        update_current_mode_config(cnc, spatial, wind, anc);
    }

    std::pair<uint8_t, ModeConfig> ensure_editable_profile() {
        auto all = modes();
        auto idx = safe_call<uint8_t>([&]{ return mode_idx(); }, 0);
        for (auto& m : all) {
            if (m.mode_idx == idx && m.editable) return {idx, m};
        }
        // Look for existing "Custom" profile
        for (auto& m : all) {
            if (m.name == "Custom" && m.editable) return {m.mode_idx, m};
        }
        // Create one
        auto slot = find_free_slot(all);
        auto [cnc_cur, _] = safe_call<std::pair<uint8_t,uint8_t>>(
            [&]{ return cnc(); }, {0, 10});
        ModeConfig mc{};
        mc.mode_idx = slot;
        mc.name = "Custom";
        mc.cnc_level = cnc_cur;
        mc.wind_block = true;
        mc.anc_toggle = true;
        write_mode(slot, mc);
        return {slot, mc};
    }

    // A slot is free when its name is the "None" sentinel or blank. The
    // `configured` bit is not part of the test: firmware sets it on first
    // write and never clears it, so a deleted slot keeps it and would
    // otherwise stay unusable. Same rule as the Python and Rust libraries.
    uint8_t find_free_slot(const std::vector<ModeConfig>& all) {
        for (auto slot : config_.editable_slots) {
            const ModeConfig* row = nullptr;
            for (auto& m : all) {
                if (m.mode_idx == slot) { row = &m; break; }
            }
            if (!row) return slot;
            auto name = detail::trim_lower(row->name);
            if (name.empty() || name == "none") return slot;
        }
        throw device_error("No free profile slot available");
    }

    // Refuse a custom profile name that matches a preset (any case). Mode
    // switching resolves preset names first, so a custom profile named like
    // a preset can never be selected by name.
    void refuse_preset_name(const std::string& name, const std::vector<ModeConfig>& all) {
        auto wanted = detail::trim_lower(name);
        bool is_preset = false;
        for (auto& [n, _] : config_.preset_modes) {
            if (detail::trim_lower(n) == wanted) is_preset = true;
        }
        for (auto& m : all) {
            if (!m.editable && detail::trim_lower(m.name) == wanted) is_preset = true;
        }
        if (is_preset) {
            throw std::invalid_argument(
                "'" + name + "' is a preset mode name; choose a different profile name");
        }
    }

    ModeConfig current_mode_config() {
        auto idx = mode_idx();
        auto all = modes();
        for (auto& m : all) {
            if (m.mode_idx == idx) return m;
        }
        throw std::runtime_error("Current mode config not available");
    }

    void update_current_mode_config(uint8_t cnc, uint8_t spatial, uint8_t wind, uint8_t anc) {
        if (anc != 255 && !config_.supports_anc_toggle) {
            throw std::runtime_error("ANC on/off toggle not supported on this device");
        }
        auto mc = current_mode_config();
        if (!mc.editable) {
            throw std::runtime_error("Current mode is not editable on this device: " + mc.name);
        }
        if (cnc != 255) mc.cnc_level = cnc;
        if (spatial != 255) mc.spatial = spatial;
        if (wind != 255) mc.wind_block = wind != 0;
        if (anc != 255) mc.anc_toggle = anc != 0;
        write_mode(mc.mode_idx, mc);
    }

    void write_mode(uint8_t slot, const ModeConfig& mc) {
        auto addr = require(config_.mode_config, "mode_config");
        if (!config_.build_mode_config) {
            throw std::runtime_error("Mode config builder not supported on this device");
        }
        auto payload = config_.build_mode_config(
            slot, mc.name, mc.cnc_level, mc.spatial,
            mc.wind_block, mc.anc_toggle, mc.prompt_b1, mc.prompt_b2);
        auto pkt = bmap_packet(addr.fblock, addr.func, Operator::SetGet, payload);
        auto data = transport_->send_recv_drain(pkt);
        auto responses = parse_all_responses(data);
        bool ok = false;
        for (auto& r : responses) {
            if (r.op == Operator::Status) { ok = true; break; }
        }
        if (!ok) throw std::runtime_error("Mode config write failed");
    }
};

} // namespace bmap
