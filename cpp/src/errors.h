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

/// Opening the RFCOMM socket failed. error_number() is the OS errno
/// (e.g. EBUSY, ECONNREFUSED), or 0 when there is none. Mirrors
/// BmapConnectionError.errno (Python).
class connect_error : public std::runtime_error {
public:
    explicit connect_error(const std::string& message, int error_number = 0)
        : std::runtime_error(message), error_number_(error_number) {}
    int error_number() const noexcept { return error_number_; }

private:
    int error_number_;
};

/// The device kept refusing the channel as busy (EBUSY) after retries,
/// typically because the previous connection is still closing. Mirrors
/// BmapBusyError (Python) and BmapError::Busy (Rust).
class busy_error : public connect_error {
public:
    busy_error(const std::string& message, int error_number)
        : connect_error(message, error_number) {}
};

} // namespace bmap
