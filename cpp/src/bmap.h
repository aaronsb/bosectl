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

/// Connect to a BMAP device, auto-detecting if mac/device_type are empty.
inline std::unique_ptr<BmapConnection> connect(
    const std::string& mac_override = "",
    const std::string& device_type_override = "")
{
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
    if (device_type.empty()) {
        device_type = "qc_ultra2";
    }

    auto config = get_device(device_type);
    if (!config) {
        throw std::runtime_error("Unknown device type: " + device_type);
    }

    auto transport = std::make_unique<RfcommTransport>(mac, config->rfcomm_channel);

    // Some devices require an init packet before responding.
    if (config->init_packet) {
        auto pkt = bmap_packet(config->init_packet->fblock,
                               config->init_packet->func, Operator::Get);
        transport->send_recv(pkt);
    }

    return std::make_unique<BmapConnection>(std::move(transport), std::move(*config));
}

} // namespace bmap
