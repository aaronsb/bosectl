//! bmap — Control Bluetooth audio devices over the BMAP protocol.
//!
//! # Example
//!
//! ```no_run
//! use bmap::connect;
//!
//! // Auto-detect connected device
//! let dev = connect(None, None).unwrap();
//! println!("Battery: {}%", dev.battery().unwrap());
//! println!("Mode: {}", dev.mode().unwrap());
//! ```

pub mod protocol;
pub mod transport;
pub mod error;
pub mod device;
pub mod devices;
pub mod connection;
pub mod discovery;
pub mod catalog;

pub use connection::BmapConnection;
pub use transport::Transport;
pub use device::{
    BatteryReading, BatteryStatus, ButtonMapping, DeviceConfig, DeviceStatus,
    EqBand, ModeConfig,
};
pub use error::{BmapError, BmapResult};
pub use protocol::{Operator, BmapResponse};

/// Connect to a BMAP device over Bluetooth RFCOMM.
///
/// - `mac`: Bluetooth MAC address. Auto-detected if None.
/// - `device_type`: Device type string. Auto-detected only when `mac` is None.
pub fn connect(mac: Option<&str>, device_type: Option<&str>) -> BmapResult<BmapConnection<transport::RfcommTransport>> {
    let mac = mac.filter(|value| !value.is_empty());
    let device_type = device_type.filter(|value| !value.is_empty());
    let (mac, resolved_type) = match mac {
        Some(m) => {
            let dtype = device_type.ok_or_else(|| BmapError::InvalidArg(
                "device_type is required when mac is specified".into()
            ))?;
            (m.to_string(), dtype.to_string())
        }
        None => {
            let (detected_mac, detected_type) = discovery::find_bmap_device()
                .ok_or_else(|| BmapError::NotFound(
                    "No connected BMAP device found. Pair and connect via bluetoothctl or pass --mac".into()
                ))?;
            let dtype = device_type.map(|s| s.to_string()).unwrap_or(detected_type);
            (detected_mac, dtype)
        }
    };

    let config = devices::get_device(&resolved_type)
        .ok_or_else(|| BmapError::InvalidArg(format!("Unknown device: {}", resolved_type)))?;

    let transport = open_transport(&mac, config.rfcomm_channel, config.init_packet)?;
    Ok(BmapConnection::new(transport, config))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn explicit_mac_requires_device_type() {
        for device_type in [None, Some("")] {
            let result = connect(Some("00:11:22:33:44:55"), device_type);
            assert!(matches!(result, Err(BmapError::InvalidArg(message))
                if message.contains("device_type is required")));
        }
    }
}

/// RFCOMM channels BMAP has been observed on. The channel a unit exposes can
/// vary with firmware and with which profiles bluetoothd has already claimed,
/// so the device's configured channel is a first guess rather than a fact.
pub const FALLBACK_CHANNELS: [u8; 3] = [2, 8, 9];

/// Connect on the configured channel, then probe fallbacks.
///
/// A socket that accepts the connection is not proof of BMAP — several
/// channels accept and stay silent — so each fallback is confirmed with a
/// firmware GET [0.5] before it is returned.
fn open_transport(
    mac: &str,
    channel: u8,
    init_packet: Option<device::Addr>,
) -> BmapResult<transport::RfcommTransport> {
    let candidates: Vec<u8> = std::iter::once(channel)
        .chain(FALLBACK_CHANNELS.iter().copied().filter(|&c| c != channel))
        .collect();
    let mut first_error: Option<BmapError> = None;

    for (i, &ch) in candidates.iter().enumerate() {
        let transport = match transport::RfcommTransport::connect(mac, ch) {
            Ok(t) => t,
            Err(e) => {
                first_error.get_or_insert(e);
                continue;
            }
        };
        if i == 0 {
            // Configured channel connected: trust it, send init if needed.
            send_init(&transport, init_packet)?;
            return Ok(transport);
        }
        if speaks_bmap(&transport, init_packet) {
            return Ok(transport);
        }
        // transport dropped here, closing the socket
    }

    let tried: Vec<String> = candidates.iter().map(|c| c.to_string()).collect();
    Err(BmapError::Connection(format!(
        "No BMAP channel found on {} (tried {}): {}",
        mac,
        tried.join(", "),
        first_error.map(|e| e.to_string()).unwrap_or_default()
    )))
}

fn send_init(transport: &transport::RfcommTransport, init_packet: Option<device::Addr>) -> BmapResult<()> {
    if let Some(init) = init_packet {
        let pkt = protocol::bmap_packet(init.0, init.1, protocol::Operator::Get, &[]);
        transport.send_recv(&pkt)?;
    }
    Ok(())
}

/// Send a firmware GET and return true on any parseable BMAP reply.
fn speaks_bmap(transport: &transport::RfcommTransport, init_packet: Option<device::Addr>) -> bool {
    if send_init(transport, init_packet).is_err() {
        return false;
    }
    let pkt = protocol::bmap_packet(0, 5, protocol::Operator::Get, &[]);
    match transport.send_recv(&pkt) {
        // Any 4+ byte reply parses; a real BMAP peer echoes the address we asked.
        Ok(data) => matches!(
            protocol::parse_response(&data),
            Some(r) if r.fblock == 0 && r.func == 5 && r.op == protocol::Operator::Status
        ),
        Err(_) => false,
    }
}
