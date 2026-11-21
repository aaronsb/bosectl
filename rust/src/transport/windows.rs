#![cfg(windows)]

use std::io::{ErrorKind, Read, Write};
use std::time::{Duration, Instant};
use serialport::SerialPort;

use super::{ConnectError, Transport};
use crate::error::{BmapError, BmapResult};

pub struct WinRfcommTransport {
    port: Box<dyn SerialPort>,
}

impl WinRfcommTransport {
    pub (crate) fn try_connect(_mac: &str, _channel: u8) -> Result<Self, ConnectError> {
        let target_port = Self::resolve_com_port();

        println!("[DEBUG] Connexion au port SPP Bluetooth : {}", target_port);

        let port = serialport::new(&target_port, 115_200)
            .timeout(Duration::from_millis(250))
            .open()
            .map_err(|e| ConnectError {
                error: BmapError::Connection(format!(
                    "Impossible d'ouvrir le port {}: {}",
                    target_port, e
                )),
                errno: None,
            })?;

        Ok(Self { port })
    }

    fn resolve_com_port() -> String {
        if let Ok(explicit) = std::env::var("BMAP_COM_PORT") {
            let trimmed = explicit.trim();
            if !trimmed.is_empty() {
                return trimmed.to_string();
            }
        }

        let ports = serialport::available_ports().unwrap_or_default();

        if ports.iter().any(|p| p.port_name.eq_ignore_ascii_case("COM3")) {
            return "COM3".to_string();
        }

        ports
            .iter()
            .find_map(|p| {
                if matches!(p.port_type, serialport::SerialPortType::BluetoothPort) {
                    Some(p.port_name.clone())
                } else {
                    None
                }
            })
            .unwrap_or_else(|| "COM3".to_string())
    }
}

impl Transport for WinRfcommTransport {
    fn send_recv(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
        let mut port = self
            .port
            .try_clone()
            .map_err(|e| BmapError::Connection(format!("Erreur clone port SPP: {}", e)))?;

        port.write_all(packet)
            .map_err(|e| BmapError::Connection(format!("Erreur écriture SPP: {}", e)))?;
        port.flush()
            .map_err(|e| BmapError::Connection(format!("Erreur flush SPP: {}", e)))?;

        let mut response = Vec::with_capacity(256);
        let mut chunk = [0u8; 256];
        let deadline = Instant::now() + Duration::from_millis(2000);

        loop {
            match port.read(&mut chunk) {
                Ok(0) => break,
                Ok(n) => {
                    response.extend_from_slice(&chunk[..n]);
                    // Petite pause pour capter d'éventuels octets restants de la même trame
                    std::thread::sleep(Duration::from_millis(25));
                }
                Err(ref e) if e.kind() == ErrorKind::TimedOut => {
                    if !response.is_empty() || Instant::now() >= deadline {
                        break;
                    }
                }
                Err(e) => {
                    return Err(BmapError::Connection(format!(
                        "Erreur lecture SPP: {}",
                        e
                    )));
                }
            }
        }

        if response.is_empty() {
            return Err(BmapError::Connection(
                "Aucune réponse reçue sur le port SPP (timeout)".to_string(),
            ));
        }

        Ok(response)
    }

    fn send_recv_drain(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
        self.send_recv(packet)
    }
}