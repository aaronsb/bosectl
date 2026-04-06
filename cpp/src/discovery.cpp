// Auto-detect paired BMAP devices via bluetoothctl (Linux).
#include "discovery.h"

#include <array>
#include <cstdio>
#include <memory>
#include <sstream>
#include <string>

namespace bmap {

static std::string exec(const std::string& cmd) {
    std::array<char, 256> buf;
    std::string result;
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(cmd.c_str(), "r"), pclose);
    if (!pipe) return "";
    while (fgets(buf.data(), buf.size(), pipe.get())) {
        result += buf.data();
    }
    return result;
}

std::optional<std::string> find_bmap_device() {
    auto output = exec("bluetoothctl devices Paired 2>/dev/null");
    std::istringstream stream(output);
    std::string line;

    while (std::getline(stream, line)) {
        // Line format: "Device AA:BB:CC:DD:EE:FF Name"
        auto first_space = line.find(' ');
        if (first_space == std::string::npos) continue;
        auto second_space = line.find(' ', first_space + 1);
        if (second_space == std::string::npos) continue;
        auto mac = line.substr(first_space + 1, second_space - first_space - 1);

        auto info = exec("bluetoothctl info " + mac + " 2>/dev/null");
        if (info.find("Icon: audio-headset") != std::string::npos &&
            info.find("00000000-deca-fade-deca-deafdecacaff") != std::string::npos) {
            return mac;
        }
        // Fallback: name matching
        std::string lower_info = info;
        for (auto& c : lower_info) c = std::tolower(c);
        if (lower_info.find("bose") != std::string::npos) {
            return mac;
        }
    }
    return std::nullopt;
}

} // namespace bmap
