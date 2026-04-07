// Bose device catalog — known BMAP-capable devices.
// Source: https://downloads.bose.com/lookup.xml
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
        {0x4017, "kleos",     "QuietComfort 35",                 Category::Headphones, "qc35"},
        {0x4020, "baywolf",   "QuietComfort 35 II",              Category::Headphones, "qc35"},
        {0x4024, "goodyear",  "Noise Cancelling Headphones 700", Category::Headphones, nullptr},
        {0x4061, "vedder",    "QuietComfort 45",                 Category::Headphones, nullptr},
        {0x4082, "wolverine", "QuietComfort Ultra Headphones",   Category::Headphones, "qc_ultra2"},
        // Earbuds
        {0x4060, "olivia",    "QuietComfort Earbuds II",         Category::Earbuds, nullptr},
        {0x4063, "edith",     "Ultra Open Earbuds",              Category::Earbuds, nullptr},
        {0x4075, "prince",    "QuietComfort Ultra Earbuds",      Category::Earbuds, nullptr},
        // Speakers
        {0x402D, "revel",     "Home Speaker 300",                Category::Speaker, nullptr},
        {0x402F, "lando",     "Portable Home Speaker",           Category::Speaker, nullptr},
        {0x4039, "duran",     "SoundLink Flex",                  Category::Speaker, nullptr},
        {0x403A, "gwen",      "SoundLink Revolve+ II",           Category::Speaker, nullptr},
        {0x4066, "lonestarr", "SoundLink Max",                   Category::Speaker, nullptr},
        {0x4073, "scotty",    "SoundLink Flex 2nd Gen",          Category::Speaker, nullptr},
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
