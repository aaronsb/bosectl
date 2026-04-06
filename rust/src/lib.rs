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

pub use connection::BmapConnection;
pub use transport::Transport;
pub use device::{DeviceConfig, DeviceStatus, ModeConfig, EqBand, ButtonMapping};
pub use error::{BmapError, BmapResult};
pub use protocol::{Operator, BmapResponse};

/// Connect to a BMAP device over Bluetooth RFCOMM.
///
/// - `mac`: Bluetooth MAC address. Auto-detected if None.
/// - `device_type`: Device type string. Auto-detected if None.
pub fn connect(mac: Option<&str>, device_type: Option<&str>) -> BmapResult<BmapConnection<transport::RfcommTransport>> {
    let (mac, resolved_type) = match mac {
        Some(m) => (m.to_string(), device_type.unwrap_or("qc_ultra2").to_string()),
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

    let transport = transport::RfcommTransport::connect(&mac, config.rfcomm_channel)?;

    // Some devices require an init packet before responding.
    if let Some(init) = config.init_packet {
        let pkt = protocol::bmap_packet(init.0, init.1, protocol::Operator::Get, &[]);
        let _ = transport.send_recv(&pkt);
    }

    Ok(BmapConnection::new(transport, config))
}
