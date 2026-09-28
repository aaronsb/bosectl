// Exception types for BMAP protocol errors.
//
// All derive from std::runtime_error, so callers that catch
// std::runtime_error or std::exception keep working.
#pragma once

#include <cstdint>
#include <stdexcept>
#include <string>

namespace bmap {

/// The device answered with an ERROR, or the reply was invalid or empty.
/// Mirrors BmapDeviceError (Python) and BmapError::Device (Rust).
class device_error : public std::runtime_error {
public:
    explicit device_error(const std::string& message, uint8_t code = 0)
        : std::runtime_error(message), code_(code) {}
    uint8_t code() const noexcept { return code_; }

private:
    uint8_t code_;
};

/// The connected device does not have the requested feature.
/// Mirrors BmapError::Unsupported (Rust).
class unsupported_error : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

/// A response carried a different address than the request.
///
/// Seen after the headset drops and reconnects: responses queued before the
/// drop are still in the socket, so each read returns the previous request's
/// answer. Reopen the connection to clear it. Mirrors BmapDesyncError
/// (Python) and BmapError::Desync (Rust).
class desync_error : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

} // namespace bmap
