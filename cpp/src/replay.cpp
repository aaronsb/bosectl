// Conformance adapter: drives the C++ library for conformance/run.py.
//
// Reads requests on stdin and answers on stdout, one line each, as
// conformance/INTERFACE.md describes. The library talks to a stdio transport
// instead of Bluetooth, so the runner plays the headphones' side.
//
// The adapter holds no device knowledge: it maps call names to library
// methods and formats what they return.

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "connection.h"
#include "devices.h"
#include "errors.h"

using namespace bmap;

namespace {


/// An answer line to print instead of a call's result.
struct reply_line : std::runtime_error {
    using std::runtime_error::runtime_error;
};

void write_line(const std::string& line) {
    std::cout << line << '\n' << std::flush;
}

std::string to_hex(const std::vector<uint8_t>& bytes) {
    static const char digits[] = "0123456789abcdef";
    std::string out;
    for (auto b : bytes) {
        out += digits[b >> 4];
        out += digits[b & 0x0f];
    }
    return out;
}

std::vector<uint8_t> from_hex(const std::string& hex) {
    if (hex.size() % 2) throw reply_line("err other odd-length hex from the runner");
    std::vector<uint8_t> out;
    for (size_t i = 0; i < hex.size(); i += 2)
        out.push_back(static_cast<uint8_t>(std::stoi(hex.substr(i, 2), nullptr, 16)));
    return out;
}

/// A transport whose far end is the conformance runner.
class StdioTransport : public Transport {
public:
    std::vector<uint8_t> send_recv(const std::vector<uint8_t>& packet) override {
        return exchange("send", packet);
    }
    std::vector<uint8_t> send_recv_drain(const std::vector<uint8_t>& packet) override {
        return exchange("send-drain", packet);
    }

private:
    static std::vector<uint8_t> exchange(const char* word, const std::vector<uint8_t>& packet) {
        write_line(std::string(word) + " " + to_hex(packet));
        std::string line;
        if (!std::getline(std::cin, line)) throw reply_line("err other stdin closed mid-call");
        // The C++ library has no timeout error type: RfcommTransport throws a
        // plain std::runtime_error("No response: ..."), so this does the same,
        // and the call reports `err other` until the library gains one (#56).
        if (line == "timeout") throw std::runtime_error("No response: timeout from the conformance runner");
        if (line == "recv") return {};
        if (line.rfind("recv ", 0) == 0) return from_hex(line.substr(5));
        throw reply_line("err other expected recv or timeout, got " + line);
    }
};

const char* on_off(bool value) { return value ? "on" : "off"; }

bool flag(const std::string& arg) {
    if (arg != "on" && arg != "off")
        throw std::invalid_argument("expected on or off, got " + arg);
    return arg == "on";
}

/// A decimal argument that fits the library parameter's type.
long number(const std::string& arg, long lo, long hi) {
    char* end = nullptr;
    errno = 0;
    long v = std::strtol(arg.c_str(), &end, 10);
    if (arg.empty() || *end || errno || v < lo || v > hi)
        throw std::invalid_argument("expected a number in " + std::to_string(lo) + ".." +
                                    std::to_string(hi) + ", got " + arg);
    return v;
}

std::string eq_text(std::vector<EqBand> bands) {
    std::sort(bands.begin(), bands.end(),
              [](const EqBand& a, const EqBand& b) { return a.band_id < b.band_id; });
    std::string out;
    for (const auto& b : bands) {
        if (!out.empty()) out += ' ';
        out += std::to_string(static_cast<int>(b.current));
    }
    return out;
}

using Args = std::vector<std::string>;
using Getter = std::function<std::string(BmapConnection&)>;
using Setter = std::function<void(BmapConnection&, const Args&)>;

const std::map<std::string, Getter> GETTERS = {
    {"battery",     [](BmapConnection& d) { return std::to_string(d.battery()); }},
    {"firmware",    [](BmapConnection& d) { return d.firmware(); }},
    {"name",        [](BmapConnection& d) { return d.name(); }},
    {"cnc",         [](BmapConnection& d) {
        auto [cur, max] = d.cnc();
        return std::to_string(cur) + "/" + std::to_string(max);
    }},
    {"eq",          [](BmapConnection& d) { return eq_text(d.eq()); }},
    {"multipoint",  [](BmapConnection& d) { return std::string(on_off(d.multipoint())); }},
    {"sidetone",    [](BmapConnection& d) { return d.sidetone(); }},
    {"auto_pause",  [](BmapConnection& d) { return std::string(on_off(d.auto_pause())); }},
    {"auto_answer", [](BmapConnection& d) { return std::string(on_off(d.auto_answer())); }},
    {"cnc_presets", [](BmapConnection& d) {
        auto p = d.cnc_presets();
        return std::to_string(p[0]) + " " + std::to_string(p[1]) + " " + std::to_string(p[2]);
    }},
    {"cnc_persist", [](BmapConnection& d) { return std::string(on_off(d.cnc_persist())); }},
};

// Each setter: (number of ARGs it needs, library call).
const std::map<std::string, std::pair<size_t, Setter>> SETTERS = {
    {"set_cnc", {1, [](BmapConnection& d, const Args& a) {
        d.set_cnc(static_cast<uint8_t>(number(a[0], 0, 255)));
    }}},
    {"set_eq", {3, [](BmapConnection& d, const Args& a) {
        d.set_eq(static_cast<int8_t>(number(a[0], -128, 127)),
                 static_cast<int8_t>(number(a[1], -128, 127)),
                 static_cast<int8_t>(number(a[2], -128, 127)));
    }}},
    {"set_name",        {1, [](BmapConnection& d, const Args& a) { d.set_name(a[0]); }}},
    {"set_multipoint",  {1, [](BmapConnection& d, const Args& a) { d.set_multipoint(flag(a[0])); }}},
    {"set_sidetone",    {1, [](BmapConnection& d, const Args& a) { d.set_sidetone(a[0]); }}},
    {"set_auto_pause",  {1, [](BmapConnection& d, const Args& a) { d.set_auto_pause(flag(a[0])); }}},
    {"set_auto_answer", {1, [](BmapConnection& d, const Args& a) { d.set_auto_answer(flag(a[0])); }}},
    {"set_anc",         {1, [](BmapConnection& d, const Args& a) { d.set_anc(flag(a[0])); }}},
    {"set_cnc_presets", {3, [](BmapConnection& d, const Args& a) {
        d.set_cnc_presets(static_cast<uint8_t>(number(a[0], 0, 255)),
                          static_cast<uint8_t>(number(a[1], 0, 255)),
                          static_cast<uint8_t>(number(a[2], 0, 255)));
    }}},
    {"set_cnc_persist", {1, [](BmapConnection& d, const Args& a) { d.set_cnc_persist(flag(a[0])); }}},
};

std::string one_line(std::string text) {
    std::replace(text.begin(), text.end(), '\n', ' ');
    return text;
}

/// Run one call and return its answer line, mapping library errors to the
/// INTERFACE.md error classes.
std::string call(BmapConnection& dev, const std::string& method, const Args& args) {
    try {
        if (auto g = GETTERS.find(method); g != GETTERS.end()) return "ok " + g->second(dev);
        auto s = SETTERS.find(method);
        if (s == SETTERS.end()) return "err unknown-request";
        if (args.size() != s->second.first)
            throw std::invalid_argument(method + " needs " +
                                        std::to_string(s->second.first) + " argument(s)");
        s->second.second(dev, args);
        return "ok";
    } catch (const reply_line& e) {
        return e.what();
    } catch (const unsupported_error&) {
        return "err unsupported";
    } catch (const desync_error&) {
        return "err desync";
    } catch (const device_error& e) {
        // check_error() passes an ERROR frame's code; every other
        // device_error (an empty or unparseable reply) leaves it at 0.
        return "err device-error " + std::to_string(e.code());
    } catch (const std::invalid_argument&) {
        return "err invalid-arg";
    } catch (const std::exception& e) {
        return "err other " + one_line(e.what());
    }
}

std::string addr_text(const Addr& a) {
    return std::to_string(a.fblock) + "." + std::to_string(a.func);
}

void describe(const DeviceConfig& c) {
    write_line("channel " + std::to_string(c.rfcomm_channel));
    write_line("init " + (c.init_packet ? addr_text(*c.init_packet) : std::string("-")));
    write_line("notifications " + (c.notifications.empty() ? std::string("-") : to_hex(c.notifications)));
    const std::pair<const char*, const std::optional<Addr>*> features[] = {
        {"battery", &c.battery},             {"firmware", &c.firmware},
        {"product_name", &c.product_name},   {"voice_prompts", &c.voice_prompts},
        {"cnc", &c.cnc},                     {"eq", &c.eq},
        {"buttons", &c.buttons},             {"multipoint", &c.multipoint},
        {"sidetone", &c.sidetone},           {"auto_pause", &c.auto_pause},
        {"auto_answer", &c.auto_answer},     {"anr", &c.anr},
        {"cnc_presets", &c.cnc_presets},     {"cnc_persist", &c.cnc_persist},
        {"pairing", &c.pairing},             {"routing", &c.routing},
        {"source", &c.source},               {"power", &c.power},
        {"get_all_modes", &c.get_all_modes}, {"current_mode", &c.current_mode},
        {"mode_config", &c.mode_config},     {"favorites", &c.favorites},
        {"audio_settings", &c.audio_settings},
    };
    for (const auto& [name, addr] : features)
        if (*addr) write_line(std::string("feature ") + name + " " + addr_text(**addr));
    for (const auto& a : c.read_only) write_line("read-only " + addr_text(a));
    write_line(std::string("status-supported-only ") + (c.status_supported_only ? "1" : "0"));
    write_line(std::string("anc-toggle ") + (c.supports_anc_toggle ? "1" : "0"));
    write_line(std::string("anc-in-cnc ") + (c.anc_in_cnc ? "1" : "0"));
    std::string slots;
    for (auto s : c.editable_slots) slots += " " + std::to_string(s);
    write_line("editable-slots" + (slots.empty() ? std::string(" -") : slots));
    for (const auto& [name, preset] : c.preset_modes)
        write_line("preset " + name + " " + std::to_string(preset.idx));
    write_line("end");
}

Args split(const std::string& line) {
    Args words;
    std::string word;
    std::istringstream in(line);
    while (std::getline(in, word, ' ')) words.push_back(word);
    return words;
}

} // namespace

int main() {
    std::unique_ptr<BmapConnection> dev;
    std::string line;
    while (std::getline(std::cin, line)) {
        auto words = split(line);
        if (words.size() == 2 && words[0] == "device") {
            auto config = get_device(words[1]);
            if (!config) {
                write_line("err unknown-device");
                continue;
            }
            dev = std::make_unique<BmapConnection>(std::make_unique<StdioTransport>(),
                                                   std::move(*config));
            write_line("ready");
        } else if (!dev) {
            write_line("err unknown-request");
        } else if (words.size() > 1 && words[0] == "call") {
            Args args(words.begin() + 2, words.end());
            // set_name's ARG is the rest of the line, spaces included, and may
            // be empty ("call set_name " sets an empty name).
            if (words[1] == "set_name") {
                const std::string prefix = "call set_name ";
                args = {line.size() > prefix.size() ? line.substr(prefix.size()) : std::string()};
            }
            write_line(call(*dev, words[1], args));
        } else if (line == "describe") {
            describe(dev->config());
        } else {
            write_line("err unknown-request");
        }
    }
    return 0;
}
