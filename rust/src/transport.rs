//! RFCOMM Bluetooth socket transport for BMAP devices.
//!
//! Uses raw Linux AF_BLUETOOTH sockets via libc — no external
//! Bluetooth library needed. Mirrors what Python's socket.AF_BLUETOOTH
//! does under the hood.

use std::io;
use std::os::fd::{FromRawFd, OwnedFd, AsRawFd};
use std::time::Duration;

use crate::error::{BmapError, BmapResult};

const AF_BLUETOOTH: i32 = 31;
const BTPROTO_RFCOMM: i32 = 3;

/// Upper bound on chunks discarded before a send.
const MAX_STALE_CHUNKS: usize = 64;

/// RFCOMM channel for BMAP protocol.
pub const BMAP_CHANNEL: u8 = 2;

/// Kernel sockaddr_rc structure (matches `struct sockaddr_rc` in bluetooth.h).
///
/// Note: The kernel struct is `__attribute__((packed))` at 9 bytes, but
/// `repr(C)` on x86-64 produces 10 bytes (1 byte padding after rc_channel
/// for u16 alignment). We pass `size_of::<SockaddrRc>()` to connect(),
/// and the kernel accepts both 9 and 10 for BTPROTO_RFCOMM.
#[repr(C)]
struct SockaddrRc {
    rc_family: u16,
    rc_bdaddr: [u8; 6],
    rc_channel: u8,
}

/// Parse a "AA:BB:CC:DD:EE:FF" MAC string into bytes (reversed for BlueZ).
fn parse_mac(mac: &str) -> BmapResult<[u8; 6]> {
    let parts: Vec<&str> = mac.split(':').collect();
    if parts.len() != 6 {
        return Err(BmapError::Connection(format!("Invalid MAC address: {}", mac)));
    }
    let mut addr = [0u8; 6];
    for (i, part) in parts.iter().enumerate() {
        addr[5 - i] = u8::from_str_radix(part, 16)
            .map_err(|_| BmapError::Connection(format!("Invalid MAC byte: {}", part)))?;
    }
    Ok(addr)
}

/// Transport abstraction for sending/receiving BMAP packets.
///
/// Implemented by `RfcommTransport` for real Bluetooth. Can be mocked for testing.
pub trait Transport {
    fn send_recv(&self, packet: &[u8]) -> BmapResult<Vec<u8>>;
    fn send_recv_drain(&self, packet: &[u8]) -> BmapResult<Vec<u8>>;
}

/// Raw RFCOMM Bluetooth socket transport.
pub struct RfcommTransport {
    fd: OwnedFd,
}

impl RfcommTransport {
    /// Connect to a BMAP device by MAC address and channel.
    pub fn connect(mac: &str, channel: u8) -> BmapResult<Self> {
        let bdaddr = parse_mac(mac)?;

        unsafe {
            let fd = libc::socket(AF_BLUETOOTH, libc::SOCK_STREAM, BTPROTO_RFCOMM);
            if fd < 0 {
                return Err(BmapError::Connection(format!(
                    "Failed to create socket: {}", io::Error::last_os_error()
                )));
            }
            let owned = OwnedFd::from_raw_fd(fd);

            let addr = SockaddrRc {
                rc_family: AF_BLUETOOTH as u16,
                rc_bdaddr: bdaddr,
                rc_channel: channel,
            };

            // Set connect timeout
            set_sock_timeout(owned.as_raw_fd(), libc::SO_SNDTIMEO, Duration::from_secs(3))?;

            let ret = libc::connect(
                owned.as_raw_fd(),
                &addr as *const _ as *const libc::sockaddr,
                std::mem::size_of::<SockaddrRc>() as u32,
            );
            if ret < 0 {
                return Err(BmapError::Connection(format!(
                    "Failed to connect to {}: {}", mac, io::Error::last_os_error()
                )));
            }

            // Set recv timeout
            set_sock_timeout(owned.as_raw_fd(), libc::SO_RCVTIMEO, Duration::from_secs(3))?;

            Ok(Self { fd: owned })
        }
    }

    /// Drop bytes already waiting on the socket before a new request.
    ///
    /// Late replies and unsolicited STATUS notifications would otherwise be
    /// read as the answer to the next request. Non-blocking and bounded, so
    /// a device that streams notifications cannot stall the request; a dead
    /// socket is left for the send to report.
    fn discard_pending(&self) {
        let fd = self.fd.as_raw_fd();
        let mut buf = [0u8; 4096];
        for _ in 0..MAX_STALE_CHUNKS {
            let n = unsafe {
                libc::recv(fd, buf.as_mut_ptr() as *mut libc::c_void, buf.len(),
                           libc::MSG_DONTWAIT)
            };
            if n <= 0 {
                break;
            }
        }
    }

    fn send_recv_inner(&self, packet: &[u8], drain: bool) -> BmapResult<Vec<u8>> {
        let fd = self.fd.as_raw_fd();
        self.discard_pending();

        // Send — use libc::send directly to avoid fd ownership issues.
        let sent = unsafe {
            libc::send(fd, packet.as_ptr() as *const libc::c_void, packet.len(), 0)
        };
        if sent < 0 {
            return Err(BmapError::Connection(format!(
                "Send failed: {}", io::Error::last_os_error()
            )));
        }

        // Brief delay for device to process (protocol-required).
        std::thread::sleep(Duration::from_millis(200));

        // Receive
        let mut buf = [0u8; 4096];
        let n = unsafe {
            libc::recv(fd, buf.as_mut_ptr() as *mut libc::c_void, buf.len(), 0)
        };
        if n <= 0 {
            return Err(BmapError::Timeout(format!(
                "No response: {}", io::Error::last_os_error()
            )));
        }
        let mut data = buf[..n as usize].to_vec();

        if drain {
            self.set_recv_timeout(Duration::from_millis(500));
            loop {
                let n = unsafe {
                    libc::recv(fd, buf.as_mut_ptr() as *mut libc::c_void, buf.len(), 0)
                };
                if n <= 0 {
                    break;
                }
                data.extend_from_slice(&buf[..n as usize]);
            }
            self.set_recv_timeout(Duration::from_secs(3));
        }

        Ok(data)
    }

    fn set_recv_timeout(&self, duration: Duration) {
        // Best-effort — drain loop still works if this fails.
        let _ = unsafe { set_sock_timeout(self.fd.as_raw_fd(), libc::SO_RCVTIMEO, duration) };
    }
}

/// Set a socket timeout, checking the return value.
unsafe fn set_sock_timeout(fd: i32, opt: i32, duration: Duration) -> BmapResult<()> {
    let timeout = libc::timeval {
        tv_sec: duration.as_secs() as _,
        tv_usec: duration.subsec_micros() as _,
    };
    let ret = libc::setsockopt(
        fd,
        libc::SOL_SOCKET,
        opt,
        &timeout as *const _ as *const libc::c_void,
        std::mem::size_of::<libc::timeval>() as u32,
    );
    if ret < 0 {
        return Err(BmapError::Connection(format!(
            "setsockopt failed: {}", io::Error::last_os_error()
        )));
    }
    Ok(())
}

impl Transport for RfcommTransport {
    fn send_recv(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
        self.send_recv_inner(packet, false)
    }

    fn send_recv_drain(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
        self.send_recv_inner(packet, true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_mac() {
        let addr = parse_mac("AA:BB:CC:DD:EE:FF").unwrap();
        // BlueZ stores MAC in reverse byte order
        assert_eq!(addr, [0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA]);
    }

    #[test]
    fn test_parse_mac_invalid() {
        assert!(parse_mac("not-a-mac").is_err());
        assert!(parse_mac("AA:BB:CC").is_err());
        assert!(parse_mac("GG:HH:II:JJ:KK:LL").is_err());
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn test_macos_transport_fails() {
        let res = RfcommTransport::connect("00:11:22:33:44:55", 2);
        assert!(res.is_err());
    }
}
