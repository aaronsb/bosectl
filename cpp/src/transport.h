// RFCOMM Bluetooth socket transport for BMAP devices.
#pragma once

#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace bmap {

// Transport interface — can be mocked for testing.
class Transport {
public:
    virtual ~Transport() = default;
    virtual std::vector<uint8_t> send_recv(const std::vector<uint8_t>& packet) = 0;
    virtual std::vector<uint8_t> send_recv_drain(const std::vector<uint8_t>& packet) = 0;
};

// Real RFCOMM Bluetooth transport.
class RfcommTransport : public Transport {
public:
    static constexpr uint8_t BMAP_CHANNEL = 2;

    RfcommTransport(const std::string& mac, uint8_t channel = BMAP_CHANNEL);
    ~RfcommTransport();

    // Non-copyable
    RfcommTransport(const RfcommTransport&) = delete;
    RfcommTransport& operator=(const RfcommTransport&) = delete;

    std::vector<uint8_t> send_recv(const std::vector<uint8_t>& packet) override;
    std::vector<uint8_t> send_recv_drain(const std::vector<uint8_t>& packet) override;

private:
    std::vector<uint8_t> send_recv_inner(const std::vector<uint8_t>& packet, bool drain);
    void set_recv_timeout(int ms);
    int fd_ = -1;
};

} // namespace bmap
