use std::io;

use crate::error::{BmapError, BmapResult};

pub const BMAP_CHANNEL: u8 = 2;

pub trait Transport {
    fn send_recv(&self, packet: &[u8]) -> BmapResult<Vec<u8>>;
    fn send_recv_drain(&self, packet: &[u8]) -> BmapResult<Vec<u8>>;
}

#[derive(Debug)]
pub(crate) struct ConnectError {
    pub error: BmapError,
    pub errno: Option<i32>,
}

impl ConnectError {
    pub(crate) fn os(context: String) -> Self {
        let err = io::Error::last_os_error();
        Self {
            error: BmapError::Connection(format!("{}: {}", context, err)),
            errno: err.raw_os_error(),
        }
    }
}

impl From<BmapError> for ConnectError {
    fn from(error: BmapError) -> Self {
        Self { error, errno: None }
    }
}

#[cfg(unix)]
mod linux;
#[cfg(unix)]
pub use linux::RfcommTransport;

#[cfg(windows)]
mod windows;
#[cfg(windows)]
pub use windows::WinRfcommTransport as RfcommTransport;