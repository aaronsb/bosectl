// Bose device catalog — known BMAP-capable devices.
// Sourced from the decompiled Bose Music APK (BoseProductId.java enum).
// The enum's `value` field is the product ID reported over Bluetooth
// Modalias; verified against WOLVERINE (0x4082) and EDITH (0x4062).
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace bmap {

/// All Bose USB devices share this vendor ID.
constexpr uint16_t BOSE_USB_VID = 0x05A7;

/// BMAP Bluetooth service UUID (SDP record).
constexpr const char* BMAP_UUID = "00000000-deca-fade-deca-deafdecacaff";

enum class Category { Headphones, Earbuds, Speaker };

struct BoseDevice {
    uint16_t product_id;
    const char* codename;
    const char* name;
    Category category;
    const char* config;  // nullptr if not yet supported
};

/// All known BMAP-capable Bose devices.
inline const std::vector<BoseDevice>& catalog() {
    static const std::vector<BoseDevice> devices = {
        // Headphones
        {0x400C, "wolfcastle", "QuietComfort 35",                         Category::Headphones, "qc35"},
        {0x4015, "stetson",    "Hearphones",                              Category::Headphones, nullptr},
        {0x4020, "baywolf",    "QuietComfort 35 II",                      Category::Headphones, "qc35"},
        {0x4021, "atlas",      "ProFlight",                               Category::Headphones, nullptr},
        {0x4024, "goodyear",   "Noise Cancelling Headphones 700",         Category::Headphones, nullptr},
        {0x402B, "beanie",     "Hearphones II",                           Category::Headphones, nullptr},
        {0x4039, "duran",      "QuietComfort 45",                         Category::Headphones, nullptr},
        {0x4066, "lonestarr",  "QuietComfort Ultra Headphones",           Category::Headphones, nullptr},
        {0x4075, "prince",     "QuietComfort Headphones",                 Category::Headphones, nullptr},
        {0x4082, "wolverine",  "QuietComfort Ultra Headphones (2nd Gen)", Category::Headphones, "qc_ultra2"},
        // Earbuds
        {0x4012, "ice",        "SoundSport",                              Category::Earbuds, nullptr},
        {0x4013, "flurry",     "SoundSport Pulse",                        Category::Earbuds, nullptr},
        {0x4014, "powder",     "QuietControl 30",                         Category::Earbuds, nullptr},
        {0x4018, "levi",       "SoundSport Free",                         Category::Earbuds, nullptr},
        {0x402C, "celine",     "Frames",                                  Category::Earbuds, nullptr},
        {0x402D, "revel",      "Sport Earbuds",                           Category::Earbuds, nullptr},
        {0x402F, "lando",      "QuietComfort Earbuds",                    Category::Earbuds, nullptr},
        {0x403A, "gwen",       "Sport Open Earbuds",                      Category::Earbuds, nullptr},
        {0x404C, "celine_ii",  "Frames (2nd Gen)",                        Category::Earbuds, nullptr},
        {0x4060, "olivia",     "Frames Tempo",                            Category::Earbuds, nullptr},
        {0x4061, "vedder",     "Frames",                                  Category::Earbuds, nullptr},
        {0x4062, "edith",      "QuietComfort Ultra Earbuds (2nd Gen)",    Category::Earbuds, "qc_ultra2"},
        {0x4064, "smalls",     "QuietComfort Earbuds II",                 Category::Earbuds, nullptr},
        {0x4068, "serena",     "Ultra Open Earbuds",                      Category::Earbuds, nullptr},
        {0x4072, "scotty",     "QuietComfort Ultra Earbuds",              Category::Earbuds, nullptr},
        // Speakers
        {0x400A, "isaac",      "AE2 SoundLink",                           Category::Speaker, nullptr},
        {0x400D, "foreman",    "SoundLink Color II",                      Category::Speaker, nullptr},
        {0x4010, "folgers",    "SoundLink Revolve",                       Category::Speaker, nullptr},
        {0x4011, "harvey",     "SoundLink Revolve+",                      Category::Speaker, nullptr},
        {0x4017, "kleos",      "SoundWear",                               Category::Speaker, nullptr},
        {0x4022, "minnow",     "SoundLink Micro",                         Category::Speaker, nullptr},
        {0x4085, "troy",       "SoundLink Plus",                          Category::Speaker, nullptr},
        {0xA211, "chibi",      "S1 Pro",                                  Category::Speaker, nullptr},
        {0xBC58, "billie",     "SoundLink Micro 2",                       Category::Speaker, nullptr},
        {0xBC59, "phelps",     "SoundLink Flex",                          Category::Speaker, nullptr},
        {0xBC60, "phelps_ii",  "SoundLink Flex (2nd Gen)",                Category::Speaker, nullptr},
        {0xBC61, "mathers",    "SoundLink Flex 2",                        Category::Speaker, nullptr},
        {0xBC63, "stan",       "SoundLink Flex SE 2",                     Category::Speaker, nullptr},
    };
    return devices;
}

/// Look up a Bose device by product ID.
inline const BoseDevice* lookup_device(uint16_t product_id) {
    for (auto& d : catalog()) {
        if (d.product_id == product_id) return &d;
    }
    return nullptr;
}

/// All devices with active library support.
inline std::vector<const BoseDevice*> supported_devices() {
    std::vector<const BoseDevice*> result;
    for (auto& d : catalog()) {
        if (d.config) result.push_back(&d);
    }
    return result;
}

/// Check if a product ID has an active library implementation.
inline bool is_supported(uint16_t product_id) {
    auto* d = lookup_device(product_id);
    return d && d->config;
}

/// Get USB vendor/product ID pair for a known device.
inline std::optional<std::pair<uint16_t, uint16_t>> usb_ids(uint16_t product_id) {
    if (lookup_device(product_id))
        return std::make_pair(BOSE_USB_VID, product_id);
    return std::nullopt;
}

/// Generate a Bluetooth Modalias string for a known device.
inline std::optional<std::string> modalias(uint16_t product_id) {
    if (lookup_device(product_id)) {
        char buf[40];
        snprintf(buf, sizeof(buf), "bluetooth:v%04Xp%04Xd0000", BOSE_USB_VID, product_id);
        return std::string(buf);
    }
    return std::nullopt;
}

} // namespace bmap
