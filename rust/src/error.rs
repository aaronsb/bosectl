//! Error types for the BMAP library.

use std::fmt;

/// Result type for BMAP operations.
pub type BmapResult<T> = Result<T, BmapError>;

/// BMAP error types.
#[derive(Debug)]
pub enum BmapError {
    /// Failed to connect to device.
    Connection(String),
    /// Device requires authentication.
    Auth(String),
    /// Device returned an error response.
    Device { message: String, code: u8 },
    /// No response from device.
    Timeout(String),
    /// No BMAP device found.
    NotFound(String),
    /// Feature not supported by this device.
    Unsupported(String),
    /// Invalid argument.
    InvalidArg(String),
    /// A response carried a different address than the request.
    Desync(String),
    /// The device kept refusing the channel as busy (EBUSY) after retries,
    /// typically because the previous connection is still closing.
    Busy(String),
}

impl fmt::Display for BmapError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Connection(msg) => write!(f, "Connection error: {}", msg),
            Self::Desync(msg) => write!(f, "Out of sync: {}", msg),
            Self::Busy(msg) => write!(f, "{}", msg),
            Self::Auth(msg) => write!(f, "Authentication required: {}", msg),
            Self::Device { message, code } => write!(f, "Device error {}: {}", code, message),
            Self::Timeout(msg) => write!(f, "Timeout: {}", msg),
            Self::NotFound(msg) => write!(f, "Not found: {}", msg),
            Self::Unsupported(msg) => write!(f, "Unsupported: {}", msg),
            Self::InvalidArg(msg) => write!(f, "Invalid argument: {}", msg),
        }
    }
}

impl std::error::Error for BmapError {}
