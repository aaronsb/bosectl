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

TEST(battery_falls_back_to_lowest_bud_without_aggregate) {
    auto raw = new MockTransport();
    raw->add(2, 2, 0x03, {
        0x3c,0xff,0xff,0x01, 0x50,0xff,0xff,0x02,
        0x28,0xff,0xff,0x03,
    });
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2_earbuds());
    // Case (3) is lower but is not a bud; right bud (1) is the lowest.
    ASSERT_EQ(dev.battery(), 60);
}

TEST(battery_rejects_response_without_valid_buds) {
    auto raw = new MockTransport();
    raw->add(2, 2, 0x03, {
        0xff,0xff,0xff,0x01, 0xff,0xff,0xff,0x02,
        0xff,0xff,0xff,0x04, 0x28,0xff,0xff,0x03,
    });
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2_earbuds());
    bool threw = false;
    try { dev.battery(); }
    catch (const std::runtime_error& error) {
        threw = std::string(error.what()).find("aggregate component 4") != std::string::npos;
    }
    ASSERT_TRUE(threw);
}

static std::vector<uint8_t> earbuds_battery_fixture() {
    return decode_hex_fixture("../../fixtures/packets/qc-ultra2-earbuds/battery-status.hex");
}

static void assert_fixture_bud_readings(const std::vector<BatteryReading>& readings) {
    ASSERT_EQ(readings.size(), 3u);
    ASSERT_EQ(readings[0].component_id, 1);
    ASSERT_EQ(readings[0].level, 60);
    ASSERT_EQ(readings[1].component_id, 2);
    ASSERT_EQ(readings[1].level, 60);
    ASSERT_EQ(readings[2].component_id, 3);
    ASSERT_EQ(readings[2].level, 80);
}

TEST(status_falls_back_when_fixture_aggregate_is_invalid) {
    auto payload = earbuds_battery_fixture();
    for (size_t i = 0; i + 3 < payload.size(); i += 4) {
        if (payload[i + 3] == 4) payload[i] = 0xff;
    }
    auto raw = new MockTransport();
    raw->add(2, 2, 0x03, payload);
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2_earbuds());
    auto status = dev.status();
    ASSERT_EQ(status.battery, 60);
    assert_fixture_bud_readings(status.battery_readings);
}

TEST(status_falls_back_when_fixture_aggregate_is_absent) {
    auto fixture = earbuds_battery_fixture();
    std::vector<uint8_t> payload;
    for (size_t i = 0; i + 3 < fixture.size(); i += 4) {
        if (fixture[i + 3] != 4) payload.insert(payload.end(), &fixture[i], &fixture[i] + 4);
    }
    auto raw = new MockTransport();
    raw->add(2, 2, 0x03, payload);
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2_earbuds());
    auto status = dev.status();
    ASSERT_EQ(status.battery, 60);
    assert_fixture_bud_readings(status.battery_readings);
}

TEST(status_rejects_battery_without_valid_readings) {
    // A failed read must not surface as a measured 0%.
    auto raw = new MockTransport();
    raw->add(2, 2, 0x03, {
        0xff,0xff,0xff,0x01, 0xff,0xff,0xff,0x02,
        0xff,0xff,0xff,0x04, 0xff,0xff,0xff,0x03,
    });
    raw->add(31, 3, 0x03, {0x01});
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2_earbuds());
    bool threw = false;
    try { dev.status(); }
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
    ASSERT_EQ(config.battery_aggregate_sources, (std::vector<uint8_t>{1, 2}));
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

TEST(connect_with_mac_requires_device_type) {
    // Real connect(): validation fails before any transport is opened.
    bool threw = false;
    try { bmap::connect("00:11:22:33:44:55", ""); }
    catch (const std::invalid_argument& error) {
        threw = std::string(error.what()).find("device_type is required") != std::string::npos;
        ASSERT_TRUE(bmap::connection_hint(error) == nullptr);
    }
    ASSERT_TRUE(threw);
    ASSERT_TRUE(bmap::connection_hint(std::runtime_error("no device")) != nullptr);
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

// ── Free slot / profile lookup / address check (mirror Python) ──────────────

// A [31.6] STATUS frame in the 47-byte prince/QC45 ModeConfig layout.
static std::vector<uint8_t> mode_frame(uint8_t idx, const std::string& name, bool editable) {
    std::vector<uint8_t> p(47, 0);
    p[0] = idx;
    p[3] = editable ? 1 : 0;
    p[4] = 1;  // configured: firmware never clears it
    std::copy(name.begin(), name.end(), p.begin() + 6);
    std::vector<uint8_t> f = {31, 6, 0x03, static_cast<uint8_t>(p.size())};
    f.insert(f.end(), p.begin(), p.end());
    return f;
}

struct Qc45Modes {
    MockTransport* raw;
    std::unique_ptr<BmapConnection> dev;

    explicit Qc45Modes(const std::vector<std::vector<uint8_t>>& frames) {
        raw = new MockTransport();
        std::vector<uint8_t> all;
        for (auto& f : frames) all.insert(all.end(), f.begin(), f.end());
        raw->responses[{31, 1}] = all;
        raw->add(31, 6, 0x03, {0});  // ModeConfig write ack
        dev = std::make_unique<BmapConnection>(std::unique_ptr<Transport>(raw), qc45());
    }

    std::vector<uint8_t> written_slots() const {
        std::vector<uint8_t> out;
        for (auto& p : raw->sent) {
            if (p.size() > 4 && p[0] == 31 && p[1] == 6 && p[2] == 0x02) out.push_back(p[4]);
        }
        return out;
    }
};

template<typename E, typename F>
static bool throws_with(F fn, const std::string& needle = "") {
    try { fn(); }
    catch (const E& e) { return std::string(e.what()).find(needle) != std::string::npos; }
    catch (...) { return false; }
    return false;
}

TEST(free_slot_cleared_slot_is_reusable) {
    Qc45Modes m({mode_frame(0, "Quiet", false), mode_frame(1, "Aware", false),
                 mode_frame(2, "None", true), mode_frame(3, "Gym", true)});
    ASSERT_EQ(m.dev->create_profile("Commute"), 2);
    ASSERT_EQ(m.written_slots(), std::vector<uint8_t>{2});
}

TEST(free_slot_blank_name_is_reusable) {
    Qc45Modes m({mode_frame(2, " ", true), mode_frame(3, "Gym", true)});
    ASSERT_EQ(m.dev->create_profile("Commute"), 2);
}

TEST(free_slot_named_slots_are_not_free) {
    Qc45Modes m({mode_frame(2, "Gym", true), mode_frame(3, "Commute", true)});
    ASSERT_TRUE(throws_with<device_error>([&]{ m.dev->create_profile("Run"); },
                                          "No free profile slot"));
    ASSERT_TRUE(m.written_slots().empty());
}

TEST(free_slot_missing_slot_is_free) {
    Qc45Modes m({mode_frame(2, "Gym", true)});
    ASSERT_EQ(m.dev->create_profile("Commute"), 3);
}

TEST(create_profile_refuses_preset_name) {
    Qc45Modes m({mode_frame(3, "Gym", true)});
    ASSERT_TRUE(throws_with<std::invalid_argument>(
        [&]{ m.dev->create_profile(" AWARE"); }, "preset"));
    ASSERT_TRUE(m.written_slots().empty());
}

TEST(profile_delete_targets_custom_not_preset) {
    Qc45Modes m({mode_frame(1, "Aware", false), mode_frame(3, "Aware", true)});
    m.dev->delete_profile("aware");
    ASSERT_EQ(m.written_slots(), std::vector<uint8_t>{3});
}

TEST(profile_preset_only_match_still_refused) {
    Qc45Modes m({mode_frame(1, "Aware", false)});
    ASSERT_TRUE(throws_with<std::invalid_argument>(
        [&]{ m.dev->delete_profile("Aware"); }, "preset"));
    ASSERT_TRUE(m.written_slots().empty());
}

TEST(profile_unknown_name_raises) {
    Qc45Modes m({mode_frame(3, "Gym", true)});
    ASSERT_TRUE(throws_with<std::invalid_argument>(
        [&]{ m.dev->delete_profile("Nope"); }, "not found"));
}

TEST(address_mismatch_raises_desync) {
    // Ask for battery [2.2], answer with firmware [0.5].
    auto raw = new MockTransport();
    raw->responses[{2, 2}] = {0, 5, 0x03, 3, '4', '.', '0'};
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    ASSERT_TRUE(throws_with<desync_error>([&]{ dev.battery(); }, "[0.5], expected [2.2]"));
}

TEST(address_match_passes) { ASSERT_EQ(mock_qc_ultra2()->battery(), 80); }

TEST(desync_is_a_runtime_error) {
    // Callers that catch std::runtime_error keep catching it.
    ASSERT_TRUE(throws_with<std::runtime_error>([]{ throw desync_error("x"); }));
}

TEST(set_eq_checks_address) {
    auto raw = new MockTransport();
    raw->responses[{1, 7}] = {2, 2, 0x03, 1, 42};
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    ASSERT_TRUE(throws_with<desync_error>([&]{ dev.set_eq(1, 2, 3); }));
}

TEST(set_eq_surfaces_device_error) {
    auto raw = new MockTransport();
    raw->add(1, 7, 0x04, {1});  // ERROR: length
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    bool ok = false;
    try { dev.set_eq(1, 2, 3); } catch (const device_error& e) { ok = e.code() == 1; }
    ASSERT_TRUE(ok);
    ASSERT_EQ(raw->sent.size(), size_t{1});
}

TEST(set_mode_checks_address) {
    auto raw = new MockTransport();
    raw->responses[{31, 3}] = {2, 2, 0x06, 0};
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    ASSERT_TRUE(throws_with<desync_error>([&]{ dev.set_mode("aware"); }));
}

TEST(empty_reply_is_device_error_on_every_path) {
    auto raw = new MockTransport();
    raw->responses[{1, 10}] = {1, 10, 0x08, 0};     // unknown op (SETGET)
    raw->responses[{31, 3}] = {31, 3, 0x06, 4, 1};  // truncated (START)
    raw->responses[{1, 7}] = {};                     // nothing (SETGET)
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    const std::string msg = "Invalid or empty response";
    ASSERT_TRUE(throws_with<device_error>([&]{ dev.set_multipoint(true); }, msg));
    ASSERT_TRUE(throws_with<device_error>([&]{ dev.set_mode("aware"); }, msg));
    ASSERT_TRUE(throws_with<device_error>([&]{ dev.set_eq(0, 0, 0); }, msg));
}

TEST(late_status_ahead_of_reply_is_skipped) {
    // prince sends STATUS [31.3] after acking START with PROCESSING.
    auto raw = new MockTransport();
    raw->responses[{2, 2}] = {31, 3, 0x03, 1, 0x01, 2, 2, 0x03, 4, 80, 0xff, 0xff, 0x00};
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    ASSERT_EQ(dev.battery(), 80);
}

TEST(only_foreign_frames_is_desync) {
    auto raw = new MockTransport();
    raw->responses[{2, 2}] = {31, 3, 0x03, 1, 0x01, 0, 5, 0x03, 1, 0x34};
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    ASSERT_TRUE(throws_with<desync_error>([&]{ dev.battery(); }, "[31.3], expected [2.2]"));
}

TEST(setget_skips_stray_frame) {
    auto raw = new MockTransport();
    raw->responses[{1, 10}] = {31, 3, 0x03, 1, 0x01, 1, 10, 0x03, 1, 0x07};
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    dev.set_multipoint(true);
}

TEST(status_does_not_swallow_desync) {
    auto raw = new MockTransport();
    raw->add(2, 2, 0x03, {80, 0xff, 0xff, 0x00});
    raw->add(31, 3, 0x03, {0x00});
    raw->responses[{1, 7}] = {0, 5, 0x03, 1, 0x34};
    BmapConnection d(std::unique_ptr<Transport>(raw), qc_ultra2());
    ASSERT_TRUE(throws_with<desync_error>([&]{ d.status(); }));
}

TEST(set_mode_accepts_processing_ack) {
    auto raw = new MockTransport();
    raw->add(31, 3, 0x07, {});  // PROCESSING: async ack (prince)
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_prince());
    dev.set_mode("quiet");
}

TEST(set_mode_accepts_result) {
    auto raw = new MockTransport();
    raw->add(31, 3, 0x06, {0x01});
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_ultra2());
    dev.set_mode("aware");
}

TEST(set_mode_rejects_unexpected_op) {
    auto raw = new MockTransport();
    raw->add(31, 3, 0x03, {0});  // STATUS where RESULT/PROCESSING expected
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc_prince());
    ASSERT_TRUE(throws_with<device_error>([&]{ dev.set_mode("quiet"); }, "Mode switch failed"));
}

TEST(unsupported_feature_is_unsupported_error) {
    auto raw = new MockTransport();
    BmapConnection dev(std::unique_ptr<Transport>(raw), qc35());
    ASSERT_TRUE(throws_with<unsupported_error>([&]{ dev.eq(); }, "not supported"));
}
