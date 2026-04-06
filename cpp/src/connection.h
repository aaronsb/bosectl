// High-level BMAP device connection.
#pragma once

#include <algorithm>
#include <memory>
#include <string>
#include <vector>

#include "device.h"
#include "protocol.h"
#include "transport.h"

namespace bmap {

class BmapConnection {
public:
    BmapConnection(std::unique_ptr<Transport> transport, DeviceConfig config)
        : transport_(std::move(transport)), config_(std::move(config)) {}

    const DeviceConfig& config() const { return config_; }

    // ── Read Operations ─────────────────────────────────────────────────────

    uint8_t battery()                     { return parse_battery(get(require(config_.battery, "battery"))); }
    std::string firmware()                { return parse_firmware(get(require(config_.firmware, "firmware"))); }
    std::string name()                    { return parse_product_name(get(require(config_.product_name, "product_name"))); }
    std::pair<uint8_t, uint8_t> cnc()     { return parse_cnc(get(require(config_.cnc, "cnc"))); }
    std::vector<EqBand> eq()              { return parse_eq(get(require(config_.eq, "eq"))); }
    std::string sidetone()                { return parse_sidetone(get(require(config_.sidetone, "sidetone"))); }
    bool multipoint()                     { return parse_multipoint(get(require(config_.multipoint, "multipoint"))); }
    bool auto_pause()                     { return parse_bool(get(require(config_.auto_pause, "auto_pause"))); }
    bool auto_answer()                    { return parse_bool(get(require(config_.auto_answer, "auto_answer"))); }
    std::pair<bool, std::string> prompts(){ return parse_voice_prompts(get(require(config_.voice_prompts, "voice_prompts"))); }
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
        if (name == "eq") return config_.eq.has_value();
        if (name == "cnc") return config_.cnc.has_value();
        if (name == "sidetone") return config_.sidetone.has_value();
        if (name == "multipoint") return config_.multipoint.has_value();
        if (name == "buttons") return config_.buttons.has_value();
        if (name == "mode_config") return config_.mode_config.has_value();
        if (name == "auto_pause") return config_.auto_pause.has_value();
        if (name == "auto_answer") return config_.auto_answer.has_value();
        return false;
    }

    DeviceStatus status() {
        auto idx = safe_call<uint8_t>([&]{ return mode_idx(); }, 0);
        auto mode_name = safe_call<std::string>([&]{ return mode_name_from_idx(idx); }, "");
        auto [cnc_cur, cnc_max] = safe_call<std::pair<uint8_t,uint8_t>>(
            [&]{ return cnc(); }, {0, 10});
        auto [prom_on, prom_lang] = safe_call<std::pair<bool,std::string>>(
            [&]{ return prompts(); }, {false, ""});

        DeviceStatus s;
        s.battery = battery();
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
        auto addr = *config_.current_mode;
        uint8_t idx = 255;
        for (auto& [n, m] : config_.preset_modes) {
            if (n == name) { idx = m.idx; break; }
        }
        if (idx == 255) {
            auto all = modes();
            for (auto& m : all) {
                if (m.name == name) { idx = m.mode_idx; break; }
            }
        }
        if (idx == 255) throw std::runtime_error("Unknown mode: " + name);
        start(addr, {idx, static_cast<uint8_t>(announce ? 1 : 0)});
    }

    void set_eq(int8_t bass, int8_t mid, int8_t treble) {
        auto addr = *config_.eq;
        for (auto [band_id, val] : std::vector<std::pair<uint8_t,int8_t>>{{0,bass},{1,mid},{2,treble}}) {
            transport_->send_recv(bmap_packet(addr.fblock, addr.func, Operator::SetGet,
                                              {static_cast<uint8_t>(val), band_id}));
        }
    }

    void set_name(const std::string& new_name) {
        std::vector<uint8_t> payload(new_name.begin(), new_name.end());
        setget(require(config_.product_name, "product_name"), payload);
    }

    void set_multipoint(bool on) {
        setget(require(config_.multipoint, "multipoint"), {static_cast<uint8_t>(on ? 1 : 0)});
    }

    void set_auto_pause(bool on) {
        setget(require(config_.auto_pause, "auto_pause"), {static_cast<uint8_t>(on ? 1 : 0)});
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

    void power_off() { start(require(config_.power, "power"), {0x00}); }
    void pair()      { start(require(config_.pairing, "pairing"), {0x01}); }

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

    std::vector<uint8_t> get(Addr addr) {
        auto pkt = bmap_packet(addr.fblock, addr.func, Operator::Get);
        auto data = transport_->send_recv(pkt);
        auto resp = parse_response(data);
        if (!resp) throw std::runtime_error("Empty response");
        check_error(*resp);
        return resp->payload;
    }

    void setget(Addr addr, const std::vector<uint8_t>& payload) {
        auto pkt = bmap_packet(addr.fblock, addr.func, Operator::SetGet, payload);
        auto data = transport_->send_recv(pkt);
        auto resp = parse_response(data);
        if (resp) check_error(*resp);
    }

    BmapResponse start(Addr addr, const std::vector<uint8_t>& payload) {
        auto pkt = bmap_packet(addr.fblock, addr.func, Operator::Start, payload);
        auto data = transport_->send_recv(pkt);
        auto resp = parse_response(data);
        if (!resp) throw std::runtime_error("Empty response");
        check_error(*resp);
        return *resp;
    }

    std::vector<BmapResponse> start_drain(Addr addr, const std::vector<uint8_t>& payload) {
        auto pkt = bmap_packet(addr.fblock, addr.func, Operator::Start, payload);
        auto data = transport_->send_recv_drain(pkt);
        return parse_all_responses(data);
    }

    void check_error(const BmapResponse& resp) {
        if (resp.op == Operator::Error && !resp.payload.empty()) {
            throw std::runtime_error(resp.fmt());
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
};

} // namespace bmap
