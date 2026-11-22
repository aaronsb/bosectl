#![cfg(windows)]

use std::io;
use std::mem::{size_of, zeroed};
use std::time::Duration;

use windows_sys::Win32::Devices::Bluetooth::{AF_BTH, BTHPROTO_RFCOMM, SOCKADDR_BTH};
use windows_sys::Win32::Networking::WinSock::{
    closesocket, connect, recv, send, setsockopt, socket, WSACleanup, WSAGetLastError,
    WSAStartup, INVALID_SOCKET, SOCK_STREAM, SOCKET, SOCKET_ERROR, SOL_SOCKET, SO_RCVTIMEO,
    SO_SNDTIMEO, WSADATA,
};

use super::{ConnectError, Transport};
use crate::error::{BmapError, BmapResult};

const IO_TIMEOUT_MS: u32 = 3000;
const DRAIN_TIMEOUT_MS: u32 = 500;
const MAX_STALE_CHUNKS: usize = 64;

fn parse_bth_addr(mac: &str) -> BmapResult<u64> {
    let parts: Vec<&str> = mac.split(':').collect();
    if parts.len() != 6 {
        return Err(BmapError::Connection(format!("MAC invalide : {}", mac)));
    }
    let mut addr: u64 = 0;
    for part in parts {
        let byte = u8::from_str_radix(part, 16)
            .map_err(|_| BmapError::Connection(format!("Octet MAC invalide : {}", part)))?;
        addr = (addr << 8) | (byte as u64);
    }
    Ok(addr)
}

fn wsa_err(context: String) -> ConnectError {
    let code = unsafe { WSAGetLastError() };
    ConnectError {
        error: BmapError::Connection(format!("{}: {}", context, io::Error::from_raw_os_error(code))),
        errno: Some(code),
    }
}

pub struct WinRfcommTransport {
    sock: SOCKET,
}

unsafe impl Send for WinRfcommTransport {}
unsafe impl Sync for WinRfcommTransport {}

impl Drop for WinRfcommTransport {
    fn drop(&mut self) {
        unsafe {
            if self.sock != INVALID_SOCKET {
                closesocket(self.sock);
            }
            WSACleanup();
        }
    }
}

impl WinRfcommTransport {
    pub fn connect(mac: &str, channel: u8) -> BmapResult<Self> {
        Self::try_connect(mac, channel).map_err(|e| e.error)
    }

    pub(crate) fn try_connect(mac: &str, channel: u8) -> Result<Self, ConnectError> {
        let bt_addr = parse_bth_addr(mac)?;

        unsafe {
            let mut wsa: WSADATA = zeroed();
            let ret = WSAStartup(0x0202, &mut wsa);
            if ret != 0 {
                return Err(ConnectError {
                    error: BmapError::Connection(format!(
                        "WSAStartup KO: {}",
                        io::Error::from_raw_os_error(ret)
                    )),
                    errno: Some(ret),
                });
            }

            let sock = socket(AF_BTH as i32, SOCK_STREAM as i32, BTHPROTO_RFCOMM as i32);
            if sock == INVALID_SOCKET {
                let err = wsa_err("Création socket AF_BTH impossible".into());
                WSACleanup();
                return Err(err);
            }

            let transport = Self { sock };
            set_timeout_ms(sock, SO_SNDTIMEO, IO_TIMEOUT_MS)?;
            set_timeout_ms(sock, SO_RCVTIMEO, IO_TIMEOUT_MS)?;

            let mut addr: SOCKADDR_BTH = zeroed();
            addr.addressFamily = AF_BTH;
            addr.btAddr = bt_addr;
            addr.port = channel as u32;

            if connect(
                sock,
                &addr as *const _ as *const _,
                size_of::<SOCKADDR_BTH>() as i32,
            ) == SOCKET_ERROR
            {
                return Err(wsa_err(format!("Connexion impossible à {} (ch {})", mac, channel)));
            }

            Ok(transport)
        }
    }

    fn discard_pending(&self) {
        let mut buf = [0u8; 4096];
        let _ = set_timeout_ms(self.sock, SO_RCVTIMEO, 10);
        for _ in 0..MAX_STALE_CHUNKS {
            let n = unsafe { recv(self.sock, buf.as_mut_ptr(), buf.len() as i32, 0) };
            if n <= 0 {
                break;
            }
        }
        let _ = set_timeout_ms(self.sock, SO_RCVTIMEO, IO_TIMEOUT_MS);
    }

    fn send_recv_inner(&self, packet: &[u8], drain: bool) -> BmapResult<Vec<u8>> {
        self.discard_pending();

        let sent = unsafe { send(self.sock, packet.as_ptr(), packet.len() as i32, 0) };
        if sent == SOCKET_ERROR {
            let code = unsafe { WSAGetLastError() };
            return Err(BmapError::Connection(format!(
                "Envoi KO: {}",
                io::Error::from_raw_os_error(code)
            )));
        }

        std::thread::sleep(Duration::from_millis(200));

        let mut buf = [0u8; 4096];
        let n = unsafe { recv(self.sock, buf.as_mut_ptr(), buf.len() as i32, 0) };
        if n <= 0 {
            let code = unsafe { WSAGetLastError() };
            return Err(BmapError::Timeout(format!(
                "Aucune réponse: {}",
                io::Error::from_raw_os_error(code)
            )));
        }

        let mut data = buf[..n as usize].to_vec();

        if drain {
            let _ = set_timeout_ms(self.sock, SO_RCVTIMEO, DRAIN_TIMEOUT_MS);
            loop {
                let n = unsafe { recv(self.sock, buf.as_mut_ptr(), buf.len() as i32, 0) };
                if n <= 0 {
                    break;
                }
                data.extend_from_slice(&buf[..n as usize]);
            }
            let _ = set_timeout_ms(self.sock, SO_RCVTIMEO, IO_TIMEOUT_MS);
        }

        Ok(data)
    }
}

fn set_timeout_ms(sock: SOCKET, opt: i32, ms: u32) -> BmapResult<()> {
    let ret = unsafe {
        setsockopt(
            sock,
            SOL_SOCKET,
            opt,
            &ms as *const _ as *const u8,
            size_of::<u32>() as i32,
        )
    };
    if ret == SOCKET_ERROR {
        let code = unsafe { WSAGetLastError() };
        return Err(BmapError::Connection(format!(
            "setsockopt KO: {}",
            io::Error::from_raw_os_error(code)
        )));
    }
    Ok(())
}

impl Transport for WinRfcommTransport {
    fn send_recv(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
        self.send_recv_inner(packet, false)
    }

    fn send_recv_drain(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
        self.send_recv_inner(packet, true)
    }
}