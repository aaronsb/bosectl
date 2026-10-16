use crate::error::BmapError;

#[derive(Debug)]
pub struct ConnectError {
    pub error: BmapError,
    pub errno: Option<i32>,
}
impl From<BmapError> for ConnectError {
    fn from(error: BmapError) -> Self {
        ConnectError {
            error,
            errno: None,
        }
    }
}
pub trait Transport {
    fn send_recv(&self, packet: &[u8]) -> crate::error::BmapResult<Vec<u8>>;
    fn send_recv_drain(&self, packet: &[u8]) -> crate::error::BmapResult<Vec<u8>>;
}

#[cfg(unix)]
pub mod linux;

#[cfg(windows)]
pub mod windows;

#[cfg(unix)]
pub use linux::WinRfcommTransport as RfcommTransport; // Ou le nom exact de ton type Linux

#[cfg(windows)]
pub use windows::WinRfcommTransport as RfcommTransport;