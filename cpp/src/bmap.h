// BMAP protocol library — C++ implementation
// See docs/protocol.md for the protocol specification.
#pragma once

#include "protocol.h"
#include "transport.h"
#include "device.h"
#include "devices.h"
#include "connection.h"
#include "discovery.h"
#include "catalog.h"

namespace bmap {

/// RFCOMM channels BMAP has been observed on. The channel a unit exposes can
/// vary with firmware and with which profiles bluetoothd has already claimed,
/// so the device's configured channel is a first guess rather than a fact.
inline constexpr uint8_t FALLBACK_CHANNELS[] = {2, 8, 9};

namespace detail {

inline void validate_device_override(
    const std::string& mac_override,
    const std::string& device_type_override)
{
    if (!mac_override.empty() && device_type_override.empty()) {
        throw std::invalid_argument(
            "device_type is required when mac is specified");
    }
}

inline void send_init(Transport& transport, const DeviceConfig& config) {
    if (config.init_packet) {
        auto pkt = bmap_packet(config.init_packet->fblock,
                               config.init_packet->func, Operator::Get);
        transport.send_recv(pkt);
    }
}

/// Send a firmware GET and return true on any parseable BMAP reply.
inline bool speaks_bmap(Transport& transport, const DeviceConfig& config) {
    try {
        send_init(transport, config);
        auto data = transport.send_recv(bmap_packet(0, 5, Operator::Get));
        // Any 4+ byte reply parses; a real BMAP peer echoes the address we asked.
        auto r = parse_response(data);
        return r && r->fblock == 0 && r->func == 5 && r->op == Operator::Status;
    } catch (const std::exception&) {
        return false;
    }
}

/// Connect on the configured channel, then probe fallbacks.
///
/// A socket that accepts the connection is not proof of BMAP — several
/// channels accept and stay silent — so each fallback is confirmed with a
/// firmware GET [0.5] before it is returned.
inline std::unique_ptr<RfcommTransport> open_transport(const std::string& mac,
                                                       const DeviceConfig& config) {
    std::vector<uint8_t> candidates{config.rfcomm_channel};
    for (uint8_t c : FALLBACK_CHANNELS) {
        if (c != config.rfcomm_channel) candidates.push_back(c);
    }
    std::string first_error;

    for (size_t i = 0; i < candidates.size(); ++i) {
        std::unique_ptr<RfcommTransport> transport;
        try {
            transport = std::make_unique<RfcommTransport>(mac, candidates[i]);
        } catch (const std::exception& e) {
            if (first_error.empty()) first_error = e.what();
            continue;
        }
        if (i == 0) {
            // Configured channel connected: trust it, send init if needed.
            send_init(*transport, config);
            return transport;
        }
        if (speaks_bmap(*transport, config)) return transport;
        // transport destroyed here, closing the socket
    }

    std::string tried;
    for (size_t i = 0; i < candidates.size(); ++i) {
        if (i) tried += ", ";
        tried += std::to_string(candidates[i]);
    }
    throw std::runtime_error("No BMAP channel found on " + mac +
                             " (tried " + tried + "): " + first_error);
}

} // namespace detail

/// Follow-up hint for a failed connect(), or nullptr when the failure is a
/// caller setup mistake (std::invalid_argument) rather than a Bluetooth issue.
inline const char* connection_hint(const std::exception& error) {
    if (dynamic_cast<const std::invalid_argument*>(&error)) return nullptr;
    return "Is Bluetooth on? Are the headphones paired and connected?";
}

/// Connect to a BMAP device. Device type is resolved only during MAC discovery.
inline std::unique_ptr<BmapConnection> connect(
    const std::string& mac_override = "",
    const std::string& device_type_override = "")
{
    detail::validate_device_override(mac_override, device_type_override);
    std::string mac = mac_override;
    std::string device_type = device_type_override;

    if (mac.empty()) {
        auto detected = find_bmap_device();
        if (!detected) {
            throw std::runtime_error(
                "No connected BMAP device found. Pair and connect via bluetoothctl or pass --mac");
        }
        mac = detected->first;
        if (device_type.empty()) {
            device_type = detected->second;
        }
    }

    auto config = get_device(device_type);
    if (!config) {
        throw std::runtime_error("Unknown device type: " + device_type);
    }

    auto transport = detail::open_transport(mac, *config);
    return std::make_unique<BmapConnection>(std::move(transport), std::move(*config));
}

} // namespace bmap
