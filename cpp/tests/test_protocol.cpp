// Tests for BMAP protocol encoding/decoding.
#include "test_common.h"
#include "../src/protocol.h"

using namespace bmap;

TEST(bmap_packet_get) {
    auto pkt = bmap_packet(2, 2, Operator::Get);
    ASSERT_EQ(pkt.size(), 4u);
    ASSERT_EQ(pkt[0], 0x02);
    ASSERT_EQ(pkt[1], 0x02);
    ASSERT_EQ(pkt[2], 0x01);
    ASSERT_EQ(pkt[3], 0x00);
}

TEST(bmap_packet_start) {
    auto pkt = bmap_packet(31, 3, Operator::Start, {0, 0});
    ASSERT_EQ(pkt.size(), 6u);
    ASSERT_EQ(pkt[0], 0x1f);
    ASSERT_EQ(pkt[2], 0x05);
    ASSERT_EQ(pkt[3], 0x02);
}

TEST(parse_response_basic) {
    std::vector<uint8_t> data = {31, 3, 0x06, 1, 0x00};
    auto resp = parse_response(data);
    ASSERT_TRUE(resp.has_value());
    ASSERT_EQ(resp->fblock, 31);
    ASSERT_EQ(resp->func, 3);
    ASSERT_EQ(resp->op, Operator::Result);
    ASSERT_EQ(resp->payload.size(), 1u);
}

TEST(parse_response_too_short) {
    auto resp = parse_response({1, 2});
    ASSERT_FALSE(resp.has_value());
}

TEST(parse_all_responses_two) {
    std::vector<uint8_t> data = {31, 6, 0x03, 2, 0xAA, 0xBB, 31, 3, 0x06, 1, 0x00};
    auto responses = parse_all_responses(data);
    ASSERT_EQ(responses.size(), 2u);
    ASSERT_EQ(responses[0].func, 6);
    ASSERT_EQ(responses[1].func, 3);
}

TEST(parse_all_truncated) {
    std::vector<uint8_t> data = {31, 3, 0x06, 10, 0x00, 0x01};
    auto responses = parse_all_responses(data);
    ASSERT_EQ(responses.size(), 0u);
}

TEST(encode_mode_name_basic) {
    auto buf = encode_mode_name("Custom");
    ASSERT_EQ(buf.size(), 32u);
    ASSERT_EQ(buf[0], 'C');
    ASSERT_EQ(buf[5], 'm');
    ASSERT_EQ(buf[6], 0);
}

TEST(encode_mode_name_truncation) {
    std::string long_name(50, 'A');
    auto buf = encode_mode_name(long_name);
    ASSERT_EQ(buf.size(), 32u);
    ASSERT_EQ(buf[31], 0);
}

TEST(fmt_error_response) {
    BmapResponse resp{1, 5, Operator::Error, {5}};
    auto s = resp.fmt();
    ASSERT_TRUE(s.find("ERROR") != std::string::npos);
    ASSERT_TRUE(s.find("auth") != std::string::npos);
}

TEST(fmt_error_invalid_transition) {
    BmapResponse resp{3, 2, Operator::Error, {15}};
    auto s = resp.fmt();
    ASSERT_TRUE(s.find("InvalidTransition") != std::string::npos);
}
