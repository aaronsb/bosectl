// Universal BMAP packet encoding and decoding.
// Pure functions, no I/O, no device-specific knowledge.
#pragma once

#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace bmap {

enum class Operator : uint8_t {
    Set = 0, Get = 1, SetGet = 2, Status = 3,
    Error = 4, Start = 5, Result = 6, Processing = 7,
};

inline const char* operator_name(Operator op) {
    switch (op) {
        case Operator::Set:        return "SET";
        case Operator::Get:        return "GET";
        case Operator::SetGet:     return "SETGET";
        case Operator::Status:     return "STATUS";
        case Operator::Error:      return "ERROR";
        case Operator::Start:      return "START";
        case Operator::Result:     return "RESULT";
        case Operator::Processing: return "PROCESSING";
    }
    return "UNKNOWN";
}

inline const char* error_name(uint8_t code) {
    switch (code) {
        case 0:  return "Unknown";
        case 1:  return "Length";
        case 2:  return "Chksum";
        case 3:  return "FblockNotSupp";
        case 4:  return "FuncNotSupp";
        case 5:  return "OpNotSupp(auth)";
        case 6:  return "InvalidData";
        case 7:  return "DataUnavail";
        case 8:  return "Runtime";
        case 9:  return "Timeout";
        case 10: return "InvalidState";
        case 20: return "InsecureTransport";
        default: return "Unknown";
    }
}

struct BmapResponse {
    uint8_t fblock;
    uint8_t func;
    Operator op;
    std::vector<uint8_t> payload;

    std::string fmt() const {
        std::string hex;
        for (auto b : payload) {
            char buf[3];
            snprintf(buf, sizeof(buf), "%02x", b);
            hex += buf;
        }
        std::string prefix = "[" + std::to_string(fblock) + "." +
                              std::to_string(func) + "] " + operator_name(op);
        if (op == Operator::Error && !payload.empty()) {
            return prefix + ": " + error_name(payload[0]) + " (" + hex + ")";
        }
        return prefix + ": " + hex;
    }
};

inline std::vector<uint8_t> bmap_packet(uint8_t fblock, uint8_t func,
                                         Operator op, const std::vector<uint8_t>& payload = {}) {
    std::vector<uint8_t> pkt;
    pkt.reserve(4 + payload.size());
    pkt.push_back(fblock);
    pkt.push_back(func);
    pkt.push_back(static_cast<uint8_t>(op) & 0x0F);
    assert(payload.size() <= 255 && "BMAP payload exceeds single-byte length field");
    pkt.push_back(static_cast<uint8_t>(payload.size()));
    pkt.insert(pkt.end(), payload.begin(), payload.end());
    return pkt;
}

inline std::optional<BmapResponse> parse_response(const std::vector<uint8_t>& data) {
    if (data.size() < 4) return std::nullopt;
    BmapResponse resp;
    resp.fblock = data[0];
    resp.func = data[1];
    resp.op = static_cast<Operator>(data[2] & 0x0F);
    uint8_t length = data[3];
    size_t end = std::min<size_t>(4 + length, data.size());
    resp.payload.assign(data.begin() + 4, data.begin() + end);
    return resp;
}

inline std::vector<BmapResponse> parse_all_responses(const std::vector<uint8_t>& data) {
    std::vector<BmapResponse> responses;
    size_t pos = 0;
    while (pos + 4 <= data.size()) {
        BmapResponse resp;
        resp.fblock = data[pos];
        resp.func = data[pos + 1];
        resp.op = static_cast<Operator>(data[pos + 2] & 0x0F);
        uint8_t length = data[pos + 3];
        if (pos + 4 + length > data.size()) break;
        resp.payload.assign(data.begin() + pos + 4, data.begin() + pos + 4 + length);
        responses.push_back(std::move(resp));
        pos += 4 + length;
    }
    return responses;
}

inline std::array<uint8_t, 32> encode_mode_name(const std::string& name) {
    std::array<uint8_t, 32> buf{};
    size_t end = std::min(name.size(), size_t(31));
    std::copy(name.begin(), name.begin() + end, buf.begin());
    return buf;
}

} // namespace bmap
