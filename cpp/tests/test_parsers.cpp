// Tests for shared device parsers using real captured data.
#include "test_common.h"
#include "../src/device.h"

using namespace bmap;

TEST(parse_battery_from_capture) {
    ASSERT_EQ(parse_battery({0x50, 0xff, 0xff, 0x00}), 0x50);
}

TEST(parse_battery_empty) {
    ASSERT_EQ(parse_battery({}), 0);
}

TEST(parse_battery_readings) {
    auto readings = parse_battery_readings(decode_hex_fixture(
        "../../fixtures/packets/qc-ultra2-earbuds/battery-status.hex"));
    ASSERT_EQ(readings.size(), 4u);
    ASSERT_EQ(readings[0].component_id, 1);
    ASSERT_EQ(readings[0].level, 60);
    ASSERT_EQ(readings[3].component_id, 3);
    ASSERT_EQ(readings[3].level, 80);
    auto shuffled = parse_battery_readings({
        0x50,0xff,0xff,0x03, 0x46,0xff,0xff,0x04,
        0x32,0xff,0xff,0x09, 0x3c,0xff,0xff,0x01,
        0x3c,0xff,0xff,0x02,
    });
    ASSERT_EQ(shuffled.size(), 5u);
    ASSERT_EQ(shuffled[0].component_id, 3);
    ASSERT_EQ(shuffled[1].component_id, 4);
    ASSERT_EQ(shuffled[2].component_id, 9);
    bool threw = false;
    try { parse_battery_readings({0x50, 0xff}); }
    catch (const std::invalid_argument&) { threw = true; }
    ASSERT_TRUE(threw);
    threw = false;
    try { parse_battery_readings({
        0x3c,0xff,0xff,0x01, 0x50,0xff,0xff,0x01}); }
    catch (const std::invalid_argument&) { threw = true; }
    ASSERT_TRUE(threw);
}

TEST(parse_firmware_from_capture) {
    std::vector<uint8_t> p = {'8','.','2','.','2','0','+','g','3','4','c','f','0','2','9'};
    ASSERT_EQ(parse_firmware(p), "8.2.20+g34cf029");
}

TEST(parse_product_name_from_capture) {
    ASSERT_EQ(parse_product_name({0x00, 'F', 'a', 'r', 'g', 'o'}), "Fargo");
}

TEST(parse_cnc_from_capture) {
    auto [cur, max] = parse_cnc({0x0b, 0x07, 0x03});
    ASSERT_EQ(cur, 7);
    ASSERT_EQ(max, 10);
}

TEST(parse_eq_from_capture) {
    auto bands = parse_eq({0xf6,0x0a,0x03,0x00, 0xf6,0x0a,0xfe,0x01, 0xf6,0x0a,0xfa,0x02});
    ASSERT_EQ(bands.size(), 3u);
    ASSERT_EQ(bands[0].name, "Bass");
    ASSERT_EQ(bands[0].current, 3);
    ASSERT_EQ(bands[1].current, -2);
    ASSERT_EQ(bands[2].current, -6);
}

TEST(parse_multipoint_on) {
    ASSERT_TRUE(parse_multipoint({0x07}));
}

TEST(parse_multipoint_off) {
    ASSERT_FALSE(parse_multipoint({0x01}));
}

TEST(parse_sidetone_medium) {
    ASSERT_EQ(parse_sidetone({0x01, 0x02, 0x0f}), "medium");
}

TEST(parse_buttons_from_capture) {
    auto btn = parse_buttons({0x80, 0x09, 0x0e, 0x00, 0x09, 0x40, 0x02});
    ASSERT_TRUE(btn.has_value());
    ASSERT_EQ(btn->button_name, "Shortcut");
    ASSERT_EQ(btn->event_name, "long_press");
    ASSERT_EQ(btn->action_name, "Disabled");
}

TEST(build_mode_config_40_length) {
    auto p = build_mode_config_40(5, "Custom", 7, 2, true, true);
    ASSERT_EQ(p.size(), 40u);
    ASSERT_EQ(p[0], 5);
    ASSERT_EQ(p[35], 7);   // cnc
    ASSERT_EQ(p[37], 2);   // spatial
    ASSERT_EQ(p[38], 1);   // wind
    ASSERT_EQ(p[39], 1);   // anc
}

TEST(build_mode_config_39_length) {
    auto p = build_mode_config_39(3, "Music", 5, 0, true, false, 0, 12);
    ASSERT_EQ(p.size(), 39u);
    ASSERT_EQ(p[0], 3);
    ASSERT_EQ(p[1], 0);
    ASSERT_EQ(p[2], 12);
    ASSERT_EQ(std::string(p.begin() + 3, p.begin() + 8), "Music");
    ASSERT_EQ(p[35], 5);
    ASSERT_EQ(p[38], 1);
}

TEST(parse_voice_prompts_disabled) {
    auto [on, lang] = parse_voice_prompts({0x01});
    ASSERT_FALSE(on);
    ASSERT_EQ(lang, "US English");
}

TEST(parse_voice_prompts_enabled) {
    auto [on, lang] = parse_voice_prompts({0x21});
    ASSERT_TRUE(on);
    ASSERT_EQ(lang, "US English");
}

TEST(mode_config_roundtrip_40) {
    auto payload = build_mode_config_40(5, "MyMode", 8, 1, true, true, 0, 1);
    ASSERT_EQ(payload.size(), 40u);
    auto mc = parse_mode_config_qc_ultra2(payload);
    ASSERT_TRUE(mc.has_value());
    ASSERT_EQ(mc->mode_idx, 5);
    ASSERT_EQ(mc->name, "MyMode");
    ASSERT_EQ(mc->cnc_level, 8);
    ASSERT_EQ(mc->spatial, 1u);
    ASSERT_TRUE(mc->wind_block);
    ASSERT_TRUE(mc->anc_toggle);
}

TEST(mode_config_too_short) {
    auto mc = parse_mode_config_qc_ultra2({0, 0, 0});
    ASSERT_FALSE(mc.has_value());
}

TEST(mode_config_prince_capture) {
    std::vector<uint8_t> payload = {
        0x03,0x00,0x0c,0x01,0x01,0x00,0x4d,0x75,0x73,0x69,0x63,0x00,0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x09,0x05,0x00,0x00,0x00,0x00,
    };
    auto mc = parse_mode_config_prince(payload);
    ASSERT_TRUE(mc.has_value());
    ASSERT_EQ(mc->mode_idx, 3);
    ASSERT_EQ(mc->prompt_b2, 12);
    ASSERT_EQ(mc->name, "Music");
    ASSERT_EQ(mc->cnc_level, 5);
    ASSERT_FALSE(mc->wind_block);
    ASSERT_FALSE(mc->anc_toggle);
}
