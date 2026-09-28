// BMAP protocol library — C++ implementation
// See docs/protocol.md for the protocol specification.
#pragma once

#include "errors.h"
#include "protocol.h"
#include "transport.h"
#include "device.h"
#include "devices.h"
#include "connection.h"
#include "discovery.h"
#include "catalog.h"

#include <cerrno>
#include <chrono>
#include <functional>
#include <iterator>
#include <thread>

namespace bmap {

/// RFCOMM channels BMAP has been observed on. The channel a unit exposes can
/// vary with firmware and with which profiles bluetoothd has already claimed,
/// so the device's configured channel is a first guess rather than a fact.
inline constexpr uint8_t FALLBACK_CHANNELS[] = {2, 8, 9};

/// Backoff before each retry of a channel that answered EBUSY or
/// ECONNREFUSED: the headset is still tearing down the previous RFCOMM link,
/// or has not re-listened on the channel yet. The same channel is retried
/// after each delay before the probe moves on. ECONNREFUSED is retried only on
/// the configured channel: a fallback that refuses is usually just not a BMAP
/// channel. Linux only; the macOS transport's errors carry no errno.
inline constexpr std::chrono::milliseconds RETRY_DELAYS[] = {
    std::chrono::milliseconds(500),
    std::chrono::milliseconds(1000),
    std::chrono::milliseconds(2000),
};

inline constexpr const char* BUSY_MESSAGE =
    "Headphones busy (another connection is still closing); try again in a few seconds";

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

using OpenChannel = std::function<std::unique_ptr<Transport>(uint8_t)>;
using SleepFor = std::function<void(std::chrono::milliseconds)>;

inline bool is_retryable(int error_number, bool configured) {
    return error_number == EBUSY || (configured && error_number == ECONNREFUSED);
}

/// Open `channel`, retrying EBUSY (and ECONNREFUSED on the configured
/// channel) after each of RETRY_DELAYS. Rethrows the last failure.
inline std::unique_ptr<Transport> connect_with_retry(uint8_t channel,
                                                     bool configured,
                                                     const OpenChannel& open,
                                                     const SleepFor& sleep) {
    for (size_t retry = 0;; ++retry) {
        try {
            return open(channel);
        } catch (const connect_error& e) {
            if (!is_retryable(e.error_number(), configured) || retry >= std::size(RETRY_DELAYS)) throw;
        }
        sleep(RETRY_DELAYS[retry]);
    }
}

/// Connect on the configured channel, then probe fallbacks.
///
/// A socket that accepts the connection is not proof of BMAP — several
/// channels accept and stay silent — so each fallback is confirmed with a
/// firmware GET [0.5] before it is returned.
///
/// Each channel is retried on EBUSY (the configured one also on ECONNREFUSED)
/// before the probe moves on. A configured channel still busy after its
/// retries throws busy_error at once: the headset is there, so probing other
/// channels would only add delay. A fallback still busy at the end is
/// reported the same way rather than "no channel found". `open` and `sleep`
/// are injectable for tests.
inline std::unique_ptr<Transport> probe_channels(const std::string& mac,
                                                 const DeviceConfig& config,
                                                 const OpenChannel& open,
                                                 const SleepFor& sleep) {
    std::vector<uint8_t> candidates{config.rfcomm_channel};
    for (uint8_t c : FALLBACK_CHANNELS) {
        if (c != config.rfcomm_channel) candidates.push_back(c);
    }
    std::string first_error;
    std::string busy;
    std::string tried;

    for (size_t i = 0; i < candidates.size(); ++i) {
        if (i) tried += ", ";
        tried += std::to_string(candidates[i]);
        std::unique_ptr<Transport> transport;
        try {
            transport = connect_with_retry(candidates[i], i == 0, open, sleep);
        } catch (const connect_error& e) {
            if (first_error.empty()) first_error = e.what();
            if (busy.empty() && e.error_number() == EBUSY) {
                busy = e.what();
                if (i == 0) break;
            }
            continue;
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

    if (!busy.empty()) {
        throw busy_error(std::string(BUSY_MESSAGE) + " (" + mac + ", tried " +
                             tried + "): " + busy,
                         EBUSY);
    }
    throw std::runtime_error("No BMAP channel found on " + mac +
                             " (tried " + tried + "): " + first_error);
}

inline std::unique_ptr<Transport> open_transport(const std::string& mac,
                                                 const DeviceConfig& config) {
    return probe_channels(
        mac, config,
        [&mac](uint8_t ch) { return std::make_unique<RfcommTransport>(mac, ch); },
        [](std::chrono::milliseconds d) { std::this_thread::sleep_for(d); });
}

} // namespace detail

/// Follow-up hint for a failed connect(), or nullptr when the failure is a
/// caller setup mistake (std::invalid_argument) or a busy headset
/// (busy_error) rather than a Bluetooth issue.
inline const char* connection_hint(const std::exception& error) {
    if (dynamic_cast<const std::invalid_argument*>(&error)) return nullptr;
    if (dynamic_cast<const busy_error*>(&error)) return nullptr;
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
