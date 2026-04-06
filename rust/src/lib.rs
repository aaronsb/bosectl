//! bmap — Control Bluetooth audio devices over the BMAP protocol.
//!
//! # Example
//!
//! ```no_run
//! use bmap::{connect, devices};
//!
//! let dev = connect(None, "qc_ultra2").unwrap();
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
/// - `device_type`: Device type string (e.g. "qc_ultra2").
pub fn connect(mac: Option<&str>, device_type: &str) -> BmapResult<BmapConnection<transport::RfcommTransport>> {
    let mac = match mac {
        Some(m) => m.to_string(),
        None => discovery::find_bmap_device()
            .ok_or_else(|| BmapError::NotFound(
                "No BMAP device found. Pair via bluetoothctl or pass --mac".into()
            ))?,
    };

    let config = devices::get_device(device_type)
        .ok_or_else(|| BmapError::InvalidArg(format!("Unknown device: {}", device_type)))?;

    let transport = transport::RfcommTransport::connect(&mac, config.rfcomm_channel)?;
    Ok(BmapConnection::new(transport, config))
}
