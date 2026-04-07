// Auto-detect paired BMAP devices via bluetoothctl (Linux).
#include "discovery.h"

#include <array>
#include <cstdio>
#include <memory>
#include <regex>
#include <sstream>
#include <string>
#include <vector>

namespace bmap {

static const char* BMAP_UUID = "00000000-deca-fade-deca-deafdecacaff";

static std::string exec(const std::string& cmd) {
    std::array<char, 256> buf;
    std::string result;
    std::unique_ptr<FILE, int(*)(FILE*)> pipe(popen(cmd.c_str(), "r"), pclose);
    if (!pipe) return "";
    while (fgets(buf.data(), buf.size(), pipe.get())) {
        result += buf.data();
    }
    return result;
}

// Known BMAP devices (from https://downloads.bose.com/lookup.xml):
//   0x4017 kleos    — QuietComfort 35           → qc35
//   0x4020 baywolf  — QuietComfort 35 II        → qc35
//   0x4024 goodyear — NC Headphones 700         (unsupported)
//   0x4060 olivia   — QC Earbuds II             (unsupported)
//   0x4061 vedder   — QuietComfort 45           (unsupported)
//   0x4063 edith    — Ultra Open Earbuds        (unsupported)
//   0x4075 prince   — QC Ultra Earbuds          (unsupported)
//   0x4082 wolverine — QC Ultra Headphones      → qc_ultra2
static std::string detect_device_type(const std::string& info) {
    std::regex modalias_re(R"(Modalias:\s*bluetooth:v[0-9A-Fa-f]{4}p([0-9A-Fa-f]{4}))");
    std::smatch match;
    if (std::regex_search(info, match, modalias_re)) {
        unsigned int product_id = std::stoul(match[1].str(), nullptr, 16);
        if (product_id == 0x4082) return "qc_ultra2";                  // wolverine
        if (product_id == 0x4020 || product_id == 0x4017) return "qc35"; // baywolf / kleos
    }
    return "qc_ultra2";
}

std::optional<std::pair<std::string, std::string>> find_bmap_device() {
    auto output = exec("bluetoothctl devices Paired 2>/dev/null");
    std::istringstream stream(output);
    std::string line;

    struct Candidate { std::string mac; std::string device_type; bool connected; };
    std::vector<Candidate> candidates;

    while (std::getline(stream, line)) {
        auto first_space = line.find(' ');
        if (first_space == std::string::npos) continue;
        auto second_space = line.find(' ', first_space + 1);
        if (second_space == std::string::npos) continue;
        auto mac = line.substr(first_space + 1, second_space - first_space - 1);

        auto info = exec("bluetoothctl info " + mac + " 2>/dev/null");

        bool is_audio = (info.find("audio-headset") != std::string::npos ||
                         info.find("audio-headphones") != std::string::npos);
        bool has_bmap = info.find(BMAP_UUID) != std::string::npos;
        if (!(is_audio && has_bmap)) continue;

        bool connected = info.find("Connected: yes") != std::string::npos;
        candidates.push_back({mac, detect_device_type(info), connected});
    }

    // Prefer connected devices
    for (auto& c : candidates) {
        if (c.connected) return std::make_pair(c.mac, c.device_type);
    }
    if (!candidates.empty()) {
        return std::make_pair(candidates[0].mac, candidates[0].device_type);
    }
    return std::nullopt;
}

} // namespace bmap
