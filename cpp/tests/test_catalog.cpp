// Tests for Bose device catalog.
#include "test_common.h"
#include "../src/catalog.h"

using namespace bmap;

TEST(catalog_lookup_known) {
    auto* dev = lookup_device(0x4082);
    ASSERT_TRUE(dev != nullptr);
    ASSERT_EQ(std::string(dev->codename), std::string("wolverine"));
    ASSERT_TRUE(dev->config != nullptr);
    ASSERT_EQ(std::string(dev->config), std::string("qc_ultra2"));
}

TEST(catalog_lookup_qc35) {
    auto* dev = lookup_device(0x4020);
    ASSERT_TRUE(dev != nullptr);
    ASSERT_EQ(std::string(dev->codename), std::string("baywolf"));
    ASSERT_EQ(std::string(dev->config), std::string("qc35"));
}

TEST(catalog_lookup_qc35_original) {
    auto* dev = lookup_device(0x400C);
    ASSERT_TRUE(dev != nullptr);
    ASSERT_EQ(std::string(dev->codename), std::string("wolfcastle"));
    ASSERT_TRUE(dev->config != nullptr);
    ASSERT_EQ(std::string(dev->config), std::string("qc35"));
}

TEST(catalog_lookup_qc_ultra2_earbuds) {
    auto* dev = lookup_device(0x4062);
    ASSERT_TRUE(dev != nullptr);
    ASSERT_EQ(std::string(dev->codename), std::string("edith"));
    ASSERT_TRUE(dev->config != nullptr);
    ASSERT_EQ(std::string(dev->config), std::string("qc_ultra2"));
}

TEST(catalog_lookup_unknown) {
    ASSERT_TRUE(lookup_device(0xFFFF) == nullptr);
}

TEST(catalog_is_supported) {
    ASSERT_TRUE(is_supported(0x4082));
    ASSERT_TRUE(is_supported(0x4020));
    ASSERT_FALSE(is_supported(0x4024));  // NCH 700, no config
    ASSERT_FALSE(is_supported(0xFFFF));
}

TEST(catalog_supported_devices) {
    auto devs = supported_devices();
    ASSERT_TRUE(devs.size() >= 4u);  // wolfcastle, baywolf, edith, wolverine
    for (auto* d : devs) {
        ASSERT_TRUE(d->config != nullptr);
    }
}

TEST(catalog_usb_ids) {
    auto ids = usb_ids(0x4082);
    ASSERT_TRUE(ids.has_value());
    ASSERT_EQ(ids->first, BOSE_USB_VID);
    ASSERT_EQ(ids->second, static_cast<uint16_t>(0x4082));
    ASSERT_FALSE(usb_ids(0xFFFF).has_value());
}

TEST(catalog_modalias) {
    auto m = modalias(0x4082);
    ASSERT_TRUE(m.has_value());
    ASSERT_EQ(*m, std::string("bluetooth:v05A7p4082d0000"));
    ASSERT_FALSE(modalias(0xFFFF).has_value());
}
