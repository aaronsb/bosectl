// Tests for BmapConnection with a mock transport.
#include "test_common.h"

#include <map>
#include <memory>
#include <utility>

#include "../src/connection.h"
#include "../src/devices.h"
#include "../src/bmap.h"

using namespace bmap;

class MockTransport : public Transport {
public:
    std::map<std::pair<uint8_t,uint8_t>, std::vector<uint8_t>> responses;
    std::vector<std::vector<uint8_t>> sent;

    void add(uint8_t fblock, uint8_t func, uint8_t op, std::vector<uint8_t> payload) {
        std::vector<uint8_t> resp = {fblock, func, op, static_cast<uint8_t>(payload.size())};
        resp.insert(resp.end(), payload.begin(), payload.end());
        responses[{fblock, func}] = resp;
    }

    std::vector<uint8_t> send_recv(const std::vector<uint8_t>& packet) override {
        sent.push_back(packet);
        auto key = std::make_pair(packet[0], packet[1]);
        auto it = responses.find(key);
        if (it != responses.end()) return it->second;
        return {packet[0], packet[1], 0x04, 1, 4}; // FuncNotSupp error
    }

    std::vector<uint8_t> send_recv_drain(const std::vector<uint8_t>& packet) override {
        return send_recv(packet);
    }
};

static std::unique_ptr<BmapConnection> mock_qc_ultra2() {
    auto t = std::make_unique<MockTransport>();
    t->add(2, 2, 0x03, {80, 0xff, 0xff, 0x00});
    t->add(0, 5, 0x03, {'8','.','2','.','2','0','+','g','3','4','c','f','0','2','9'});
    t->add(1, 2, 0x03, {0x00, 'F','a','r','g','o'});
    t->add(1, 5, 0x03, {0x0b, 0x07, 0x03});
    t->add(1, 7, 0x03, {0xf6,0x0a,0x03,0x00, 0xf6,0x0a,0xfe,0x01, 0xf6,0x0a,0xfa,0x02});
    t->add(1, 10, 0x03, {0x07});
    t->add(1, 11, 0x03, {0x01, 0x02, 0x0f});
    t->add(1, 24, 0x03, {0x01});
    t->add(1, 27, 0x03, {0x01});
    t->add(1, 3, 0x03, {0x21,0,0,0x81,2,0,0});
    t->add(31, 3, 0x03, {0x00});
    t->add(1, 9, 0x03, {0x80,0x09,0x0e,0x00,0x09,0x40,0x02});
    return std::make_unique<BmapConnection>(std::move(t), qc_ultra2());
}

TEST(battery) { ASSERT_EQ(mock_qc_ultra2()->battery(), 80); }

TEST(battery_empty_response) {
    auto raw = new MockTransport();
    raw->add(2, 2, 0x03, {});
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    bool threw = false;
    try { dev.battery(); }
    catch (const std::runtime_error& error) {
        threw = std::string(error.what()).find("Empty battery response") != std::string::npos;
    }
    ASSERT_TRUE(threw);
}

TEST(battery_invalid_response) {
    auto raw = new MockTransport();
    raw->responses[{2, 2}] = {2, 2, 0x08, 0};
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    bool threw = false;
    try { dev.battery(); }
    catch (const std::runtime_error& error) {
        threw = std::string(error.what()).find("Invalid or empty response") != std::string::npos;
    }
    ASSERT_TRUE(threw);
}

TEST(battery_readings) {
    auto raw = new MockTransport();
    raw->add(2, 2, 0x03, {
        0x50,0xff,0xff,0x03, 0x3c,0xff,0xff,0x01,
        0x3c,0xff,0xff,0x02, 0x46,0xff,0xff,0x04,
    });
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2_earbuds());
    auto battery = dev.battery_status();
    ASSERT_EQ(battery.readings.size(), 4u);
    ASSERT_EQ(battery.readings[0].component_id, 3);
    ASSERT_EQ(battery.readings[0].level, 80);
    ASSERT_EQ(battery.readings[3].component_id, 4);
    ASSERT_EQ(dev.config().battery_components.size(), 3u);
    ASSERT_EQ(battery.aggregate, 70);
    ASSERT_EQ(raw->sent.size(), 1u);
}

TEST(battery_missing_aggregate_component) {
    auto raw = new MockTransport();
    raw->add(2, 2, 0x03, {
        0x3c,0xff,0xff,0x01, 0x3c,0xff,0xff,0x02,
        0x50,0xff,0xff,0x03,
    });
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2_earbuds());
    bool threw = false;
    try { dev.battery(); }
    catch (const std::runtime_error& error) {
        threw = std::string(error.what()).find("aggregate component 4") != std::string::npos;
    }
    ASSERT_TRUE(threw);
}

TEST(status_uses_one_battery_response) {
    auto raw = new MockTransport();
    raw->add(2, 2, 0x03, {
        0x50,0xff,0xff,0x03, 0x3c,0xff,0xff,0x01,
        0x46,0xff,0xff,0x04, 0x3c,0xff,0xff,0x02,
    });
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2_earbuds());
    auto status = dev.status();
    ASSERT_EQ(status.battery, 70);
    ASSERT_EQ(status.battery_readings.size(), 4u);
    size_t battery_requests = 0;
    for (const auto& packet : raw->sent) {
        if (packet.size() >= 2 && packet[0] == 2 && packet[1] == 2) battery_requests++;
    }
    ASSERT_EQ(battery_requests, 1u);
}

TEST(qc_ultra2_earbuds_config) {
    auto config = qc_ultra2_earbuds();
    ASSERT_EQ(config.info.codename, "edith");
    ASSERT_EQ(config.info.name, "Bose QuietComfort Ultra Earbuds (2nd Gen)");
    ASSERT_EQ(config.battery_components.size(), 3u);
    ASSERT_EQ(config.battery_components[0].second, "Right");
    ASSERT_EQ(config.battery_components[1].second, "Left");
    ASSERT_EQ(config.battery_components[2].second, "Case");
    ASSERT_EQ(*config.battery_aggregate_id, 4);
    ASSERT_EQ(config.preset_modes.size(), 4u);
}
TEST(firmware) { ASSERT_EQ(mock_qc_ultra2()->firmware(), "8.2.20+g34cf029"); }
TEST(device_name) { ASSERT_EQ(mock_qc_ultra2()->name(), "Fargo"); }

TEST(cnc) {
    auto [cur, max] = mock_qc_ultra2()->cnc();
    ASSERT_EQ(cur, 7); ASSERT_EQ(max, 10);
}

TEST(eq) {
    auto bands = mock_qc_ultra2()->eq();
    ASSERT_EQ(bands.size(), 3u);
    ASSERT_EQ(bands[0].current, 3);
    ASSERT_EQ(bands[1].current, -2);
}

TEST(multipoint) { ASSERT_TRUE(mock_qc_ultra2()->multipoint()); }
TEST(sidetone) { ASSERT_EQ(mock_qc_ultra2()->sidetone(), "medium"); }
TEST(auto_pause) { ASSERT_TRUE(mock_qc_ultra2()->auto_pause()); }
TEST(mode_quiet) { ASSERT_EQ(mock_qc_ultra2()->mode(), "quiet"); }
TEST(mode_idx_zero) { ASSERT_EQ(mock_qc_ultra2()->mode_idx(), 0); }

TEST(buttons) {
    auto btn = mock_qc_ultra2()->buttons();
    ASSERT_TRUE(btn.has_value());
    ASSERT_EQ(btn->button_name, "Shortcut");
    ASSERT_EQ(btn->event_name, "long_press");
}

TEST(status_full) {
    auto s = mock_qc_ultra2()->status();
    ASSERT_EQ(s.battery, 80);
    ASSERT_EQ(s.mode, "quiet");
    ASSERT_EQ(s.cnc_level, 7);
    ASSERT_EQ(s.name, "Fargo");
    ASSERT_TRUE(s.multipoint);
}

TEST(has_feature_battery) { ASSERT_TRUE(mock_qc_ultra2()->has_feature("battery")); }
TEST(has_feature_eq) { ASSERT_TRUE(mock_qc_ultra2()->has_feature("eq")); }
TEST(has_feature_missing) { ASSERT_FALSE(mock_qc_ultra2()->has_feature("nonexistent")); }

TEST(explicit_mac_requires_device_type) {
    bool threw = false;
    try { bmap::detail::validate_device_override("00:11:22:33:44:55", ""); }
    catch (const std::invalid_argument& error) {
        threw = std::string(error.what()).find("device_type is required") != std::string::npos;
    }
    ASSERT_TRUE(threw);
}

TEST(qc35_no_eq) {
    auto t = std::make_unique<MockTransport>();
    BmapConnection dev(std::move(t), qc35());
    ASSERT_FALSE(dev.has_feature("eq"));
    ASSERT_FALSE(dev.has_feature("mode_config"));
}

TEST(prince_has_eq) {
    auto t = std::make_unique<MockTransport>();
    BmapConnection dev(std::move(t), qc_prince());
    ASSERT_TRUE(dev.has_feature("eq"));
}

TEST(set_name_rejects_long_name) {
    bool threw = false;
    try { mock_qc_ultra2()->set_name(std::string(32, 'x')); }
    catch (const std::invalid_argument&) { threw = true; }
    ASSERT_TRUE(threw);
}

TEST(bmap_packet_rejects_oversized_payload) {
    bool threw = false;
    try { bmap_packet(1, 2, Operator::SetGet, std::vector<uint8_t>(256, 0)); }
    catch (const std::length_error&) { threw = true; }
    ASSERT_TRUE(threw);
}

TEST(unsupported_feature_throws) {
    auto t = std::make_unique<MockTransport>();
    BmapConnection dev(std::move(t), qc35());
    bool threw = false;
    try { dev.eq(); } catch (const std::runtime_error& e) {
        threw = true;
        ASSERT_TRUE(std::string(e.what()).find("not supported") != std::string::npos);
    }
    ASSERT_TRUE(threw);
}

TEST(error_response_throws) {
    auto t = std::make_unique<MockTransport>();
    t->add(1, 5, 0x04, {5}); // ERROR: auth
    BmapConnection dev(std::move(t), qc_ultra2());
    bool threw = false;
    try { dev.cnc(); } catch (const std::runtime_error& e) {
        threw = true;
        ASSERT_TRUE(std::string(e.what()).find("auth") != std::string::npos);
    }
    ASSERT_TRUE(threw);
}

TEST(qc_earbuds_set_cnc_uses_direct_setget) {
    auto raw = new MockTransport();
    raw->add(1, 5, 0x03, {0x0b, 0x04, 0x01});
    MockTransport* view = raw;
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_earbuds());

    dev.set_cnc(4);

    std::vector<uint8_t> expect = {1, 5, 0x02, 2, 4, 1};
    ASSERT_TRUE(view->sent.back() == expect);
}

TEST(qc45_set_cnc_writes_39_byte_mode_config) {
    std::vector<uint8_t> music = {
        0x03,0x00,0x00,0x01,0x01,0x00,0x4d,0x75,0x73,0x69,0x63,0x00,0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x05,0x00,0x00,0x00,0x00,
    };
    auto raw = new MockTransport();
    raw->add(31, 3, 0x03, {3});
    std::vector<uint8_t> get_all = {31, 6, 0x03, static_cast<uint8_t>(music.size())};
    get_all.insert(get_all.end(), music.begin(), music.end());
    raw->responses[{31, 1}] = get_all;
    raw->add(31, 6, 0x03, music);
    MockTransport* view = raw;
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc45());

    dev.set_cnc(7);

    auto last = view->sent.back();
    ASSERT_EQ(last[3], 39);
    ASSERT_EQ(last[4], 3);
    ASSERT_EQ(last[4 + 35], 7);
}

TEST(prince_set_wind_uses_mode_config_fallback) {
    std::vector<uint8_t> music = {
        0x03,0x00,0x0c,0x01,0x01,0x00,0x4d,0x75,0x73,0x69,0x63,0x00,0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x09,0x05,0x00,0x00,0x00,0x00,
    };
    auto raw = new MockTransport();
    raw->add(31, 3, 0x03, {3});
    std::vector<uint8_t> get_all = {31, 6, 0x03, static_cast<uint8_t>(music.size())};
    get_all.insert(get_all.end(), music.begin(), music.end());
    raw->responses[{31, 1}] = get_all;
    raw->add(31, 6, 0x03, music);
    MockTransport* view = raw;
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_prince());

    dev.set_wind(true);

    auto last = view->sent.back();
    ASSERT_EQ(last[0], 31);
    ASSERT_EQ(last[1], 6);
    ASSERT_EQ(last[2], 0x02);
    ASSERT_EQ(last[3], 39);
    ASSERT_EQ(last[4], 3);
    ASSERT_EQ(last[4 + 35], 5);
    ASSERT_EQ(last[4 + 38], 1);
}

TEST(prince_set_anc_rejects_missing_toggle) {
    auto t = std::make_unique<MockTransport>();
    BmapConnection dev(std::move(t), qc_prince());
    bool threw = false;
    try { dev.set_anc(false); } catch (const std::runtime_error& e) {
        threw = true;
        ASSERT_TRUE(std::string(e.what()).find("ANC") != std::string::npos);
    }
    ASSERT_TRUE(threw);
}
