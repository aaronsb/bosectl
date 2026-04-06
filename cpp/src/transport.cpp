// RFCOMM transport implementation using raw Linux Bluetooth sockets.
#include "transport.h"

#include <bluetooth/bluetooth.h>
#include <bluetooth/rfcomm.h>
#include <cerrno>
#include <cstring>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>

namespace bmap {

static void parse_mac(const std::string& mac, bdaddr_t& addr) {
    if (str2ba(mac.c_str(), &addr) < 0) {
        throw std::runtime_error("Invalid MAC address: " + mac);
    }
}

static void set_timeout(int fd, int opt, int ms) {
    struct timeval tv;
    tv.tv_sec = ms / 1000;
    tv.tv_usec = (ms % 1000) * 1000;
    if (setsockopt(fd, SOL_SOCKET, opt, &tv, sizeof(tv)) < 0) {
        throw std::runtime_error(std::string("setsockopt failed: ") + strerror(errno));
    }
}

RfcommTransport::RfcommTransport(const std::string& mac, uint8_t channel) {
    fd_ = socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM);
    if (fd_ < 0) {
        throw std::runtime_error(std::string("Failed to create socket: ") + strerror(errno));
    }

    set_timeout(fd_, SO_SNDTIMEO, 3000);

    struct sockaddr_rc addr{};
    addr.rc_family = AF_BLUETOOTH;
    parse_mac(mac, addr.rc_bdaddr);
    addr.rc_channel = channel;

    if (connect(fd_, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) < 0) {
        ::close(fd_);
        fd_ = -1;
        throw std::runtime_error("Failed to connect to " + mac + ": " + strerror(errno));
    }

    set_timeout(fd_, SO_RCVTIMEO, 3000);
}

RfcommTransport::~RfcommTransport() {
    if (fd_ >= 0) ::close(fd_);
}

std::vector<uint8_t> RfcommTransport::send_recv(const std::vector<uint8_t>& packet) {
    return send_recv_inner(packet, false);
}

std::vector<uint8_t> RfcommTransport::send_recv_drain(const std::vector<uint8_t>& packet) {
    return send_recv_inner(packet, true);
}

std::vector<uint8_t> RfcommTransport::send_recv_inner(const std::vector<uint8_t>& packet, bool drain) {
    // Send
    ssize_t sent = ::send(fd_, packet.data(), packet.size(), 0);
    if (sent < 0) {
        throw std::runtime_error(std::string("Send failed: ") + strerror(errno));
    }

    // Protocol-required delay for device processing.
    std::this_thread::sleep_for(std::chrono::milliseconds(200));

    // Receive
    uint8_t buf[4096];
    ssize_t n = ::recv(fd_, buf, sizeof(buf), 0);
    if (n <= 0) {
        throw std::runtime_error(std::string("No response: ") + strerror(errno));
    }
    std::vector<uint8_t> data(buf, buf + n);

    if (drain) {
        set_recv_timeout(500);
        while (true) {
            n = ::recv(fd_, buf, sizeof(buf), 0);
            if (n <= 0) break;
            data.insert(data.end(), buf, buf + n);
        }
        set_recv_timeout(3000);
    }

    return data;
}

void RfcommTransport::set_recv_timeout(int ms) {
    // Best-effort for drain loop.
    struct timeval tv;
    tv.tv_sec = ms / 1000;
    tv.tv_usec = (ms % 1000) * 1000;
    setsockopt(fd_, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
}

} // namespace bmap
