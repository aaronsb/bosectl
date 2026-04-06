// Tests for BmapConnection with a mock transport.
#include "test_common.h"

#include <map>
#include <memory>
#include <utility>

#include "../src/connection.h"
#include "../src/devices.h"

using namespace bmap;

class MockTransport : public Transport {
public:
    std::map<std::pair<uint8_t,uint8_t>, std::vector<uint8_t>> responses;

    void add(uint8_t fblock, uint8_t func, uint8_t op, std::vector<uint8_t> payload) {
        std::vector<uint8_t> resp = {fblock, func, op, static_cast<uint8_t>(payload.size())};
        resp.insert(resp.end(), payload.begin(), payload.end());
        responses[{fblock, func}] = resp;
    }

    std::vector<uint8_t> send_recv(const std::vector<uint8_t>& packet) override {
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

TEST(qc35_no_eq) {
    auto t = std::make_unique<MockTransport>();
    BmapConnection dev(std::move(t), qc35());
    ASSERT_FALSE(dev.has_feature("eq"));
    ASSERT_FALSE(dev.has_feature("mode_config"));
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
