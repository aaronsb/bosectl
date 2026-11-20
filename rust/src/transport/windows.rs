#![cfg(windows)]

use std::time::Duration;
use serialport::SerialPort;

use crate::error::{BmapError, BmapResult};
use super::{Transport, ConnectError};

pub struct WinRfcommTransport {
    port: Box<dyn SerialPort>,
}

impl WinRfcommTransport {
    pub fn try_connect(_mac: &str, _channel: u8) -> Result<Self, ConnectError> {
        // Détection automatique du port COM Bluetooth associé aux écouteurs Bose
        let ports = serialport::available_ports().unwrap_or_default();
        
        let target_port = ports.iter().find_map(|p| {
            if p.port_name.starts_with("COM") {
                // On privilégie les ports Bluetooth ou le port COM sortant configuré
                match &p.port_type {
                    serialport::SerialPortType::BluetoothPort => Some(p.port_name.clone()),
                    _ => if p.port_name == "COM4" { Some("COM4".to_string()) } else { None },
                }
            } else {
                None
            }
        }).unwrap_or_else(|| "COM4".to_string());

        println!("[DEBUG] Connexion au port SPP Bluetooth : {}", target_port);

        let port = serialport::new(&target_port, 115_200)
            .timeout(Duration::from_millis(2000))
            .open()
            .map_err(|e| ConnectError {
                error: BmapError::Connection(format!("Impossible d'ouvrir le port {}: {}", target_port, e)),
                errno: None,
            })?;

        Ok(Self { port })
    }
}

impl Transport for WinRfcommTransport {
    fn send_recv(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
        let mut port = self.port.try_clone().map_err(|e| BmapError::Connection(e.to_string()))?;

        // Envoi du paquet BMAP
        port.write_all(packet)
            .map_err(|e| BmapError::Connection(format!("Erreur écriture SPP: {}", e)))?;
        port.flush()
            .map_err(|e| BmapError::Connection(format!("Erreur flush SPP: {}", e)))?;

        // Lecture de la reponse BMAP
        let mut buf = vec![0u8; 1024];
        let bytes_read = port.read(&mut buf)
            .map_err(|e| BmapError::Connection(format!("Erreur lecture SPP: {}", e)))?;

        buf.truncate(bytes_read);
        Ok(buf)
    }

    fn send_recv_drain(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
        self.send_recv(packet)
    }
}