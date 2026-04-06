// bmapctl — Minimal CLI for controlling BMAP devices (C++ version).

#include <cstdlib>
#include <iostream>
#include <string>

#include "bmap.h"

using namespace bmap;

static void usage() {
    std::cout << "bmapctl — Control BMAP Bluetooth audio devices\n\n"
              << "Usage: bmapctl <command> [args...]\n\n"
              << "  status              Show all settings\n"
              << "  battery             Battery percentage\n"
              << "  current             Current mode name\n"
              << "  quiet/aware/...     Switch audio mode\n"
              << "  cnc [0-10]          Show/set noise cancellation level\n"
              << "  eq [B M T]          Show/set EQ (-10 to +10)\n"
              << "  name [TEXT]         Show/set device name\n"
              << "  sidetone [MODE]     Show/set sidetone (off/low/medium/high)\n"
              << "  multipoint [on|off] Toggle multipoint\n"
              << "  autopause [on|off]  Toggle auto play/pause\n"
              << "  prompts             Show voice prompt status\n"
              << "  buttons             Show button mapping\n"
              << "  pair                Enter pairing mode\n"
              << "  off                 Power off\n\n"
              << "Environment:\n"
              << "  BMAP_MAC=XX:XX:XX:XX:XX:XX   Device MAC\n"
              << "  BMAP_DEVICE=qc_ultra2         Device type\n";
}

static bool is_on(const std::string& s) {
    return s == "on" || s == "1" || s == "true" || s == "yes";
}

int main(int argc, char** argv) {
    if (argc < 2) { usage(); return 1; }

    std::string cmd = argv[1];
    if (cmd == "help" || cmd == "-h" || cmd == "--help") { usage(); return 0; }

    // Resolve MAC and device type
    const char* mac_env = std::getenv("BMAP_MAC");
    const char* dev_env = std::getenv("BMAP_DEVICE");
    std::string device_type = dev_env ? dev_env : "qc_ultra2";

    std::string mac;
    if (mac_env) {
        mac = mac_env;
    } else {
        auto detected = find_bmap_device();
        if (!detected) {
            std::cerr << "No BMAP device found. Set BMAP_MAC or pair via bluetoothctl.\n";
            return 1;
        }
        mac = *detected;
    }

    auto config = get_device(device_type);
    if (!config) {
        std::cerr << "Unknown device type: " << device_type << "\n";
        return 1;
    }

    std::unique_ptr<Transport> transport;
    try {
        transport = std::make_unique<RfcommTransport>(mac);
    } catch (const std::exception& e) {
        std::cerr << "Connection failed: " << e.what() << "\n"
                  << "Is Bluetooth on? Are the headphones paired and connected?\n";
        return 1;
    }

    BmapConnection dev(std::move(transport), std::move(*config));

    try {
        if (cmd == "status") {
            auto s = dev.status();
            std::string bar;
            for (int i = 0; i < s.cnc_level; i++) bar += "\xe2\x96\x88";
            for (int i = s.cnc_level; i < s.cnc_max; i++) bar += "\xe2\x96\x91";

            std::cout << "  Battery      " << (int)s.battery << "%\n"
                      << "  Mode         " << s.mode << "\n"
                      << "  CNC          " << bar << " " << (int)s.cnc_level << "/" << (int)s.cnc_max << "\n";
            if (!s.eq.empty()) {
                std::cout << "  EQ           ";
                for (size_t i = 0; i < s.eq.size(); i++) {
                    if (i) std::cout << "/";
                    int v = s.eq[i].current;
                    if (v > 0) std::cout << "+";
                    std::cout << v;
                }
                std::cout << " (bass/mid/treble)\n";
            }
            std::cout << "  Name         " << s.name << "\n"
                      << "  FW           " << s.firmware << "\n"
                      << "  Sidetone     " << s.sidetone << "\n"
                      << "  Multipoint   " << (s.multipoint ? "on" : "off") << "\n"
                      << "  AutoPause    " << (s.auto_pause ? "on" : "off") << "\n"
                      << "  Prompts      " << (s.prompts_enabled ? "on" : "off")
                      << " (" << s.prompts_language << ")\n";

        } else if (cmd == "battery") {
            std::cout << (int)dev.battery() << "\n";
        } else if (cmd == "current") {
            std::cout << dev.mode() << "\n";
        } else if (cmd == "quiet" || cmd == "aware" || cmd == "immersion" || cmd == "cinema") {
            dev.set_mode(cmd);
            std::cout << "OK: " << cmd << "\n";
        } else if (cmd == "cnc") {
            if (argc > 2) {
                // set_cnc not implemented yet in C++ CLI
                std::cerr << "CNC set not yet implemented in C++ CLI\n";
            } else {
                auto [cur, max] = dev.cnc();
                std::cout << (int)cur << "/" << (int)max << "\n";
            }
        } else if (cmd == "eq") {
            if (argc >= 5) {
                dev.set_eq(std::atoi(argv[2]), std::atoi(argv[3]), std::atoi(argv[4]));
                std::cout << "EQ: " << argv[2] << "/" << argv[3] << "/" << argv[4] << "\n";
            } else {
                auto bands = dev.eq();
                for (auto& b : bands) {
                    printf("%-6s: %+d\n", b.name.c_str(), b.current);
                }
            }
        } else if (cmd == "name") {
            if (argc > 2) {
                std::string new_name;
                for (int i = 2; i < argc; i++) {
                    if (i > 2) new_name += " ";
                    new_name += argv[i];
                }
                dev.set_name(new_name);
            }
            std::cout << dev.name() << "\n";
        } else if (cmd == "sidetone") {
            if (argc > 2) dev.set_sidetone(argv[2]);
            std::cout << dev.sidetone() << "\n";
        } else if (cmd == "multipoint") {
            if (argc > 2) dev.set_multipoint(is_on(argv[2]));
            std::cout << (dev.multipoint() ? "on" : "off") << "\n";
        } else if (cmd == "autopause") {
            if (argc > 2) dev.set_auto_pause(is_on(argv[2]));
            std::cout << (dev.auto_pause() ? "on" : "off") << "\n";
        } else if (cmd == "prompts") {
            auto [on, lang] = dev.prompts();
            std::cout << (on ? "on" : "off") << " (" << lang << ")\n";
        } else if (cmd == "buttons") {
            auto btn = dev.buttons();
            if (btn) {
                std::cout << "Button:  " << btn->button_name << " (0x"
                          << std::hex << (int)btn->button_id << std::dec << ")\n"
                          << "Event:   " << btn->event_name << "\n"
                          << "Action:  " << btn->action_name << "\n";
            }
        } else if (cmd == "pair") {
            dev.pair();
            std::cout << "Pairing mode enabled\n";
        } else if (cmd == "off") {
            dev.power_off();
            std::cout << "Powering off\n";
        } else {
            std::cerr << "Unknown command: " << cmd << "\n";
            return 1;
        }
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
