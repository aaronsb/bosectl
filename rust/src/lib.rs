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

use std::time::Duration;
use transport::ConnectError;

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

/// Backoff before each retry of a channel that answered EBUSY or
/// ECONNREFUSED: the headset is still tearing down the previous RFCOMM link,
/// or has not re-listened on the channel yet. The same channel is retried
/// after each delay before the probe moves on. ECONNREFUSED is retried only on
/// the configured channel: a fallback that refuses is usually just not a BMAP
/// channel. Linux only; the macOS transport's errors carry no errno.
pub const RETRY_DELAYS: [Duration; 3] = [
    Duration::from_millis(500),
    Duration::from_millis(1000),
    Duration::from_millis(2000),
];

const BUSY_MESSAGE: &str =
    "Headphones busy (another connection is still closing); try again in a few seconds";

fn is_retryable(errno: Option<i32>, configured: bool) -> bool {
    match errno {
        Some(libc::EBUSY) => true,
        Some(libc::ECONNREFUSED) => configured,
        _ => false,
    }
}

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
    probe_channels(
        mac,
        channel,
        init_packet,
        |ch| transport::RfcommTransport::try_connect(mac, ch),
        std::thread::sleep,
    )
}

/// Open `ch`, retrying EBUSY (and ECONNREFUSED on the configured channel)
/// after each of [`RETRY_DELAYS`].
fn connect_with_retry<T>(
    ch: u8,
    configured: bool,
    connect: &mut impl FnMut(u8) -> Result<T, ConnectError>,
    sleep: &mut impl FnMut(Duration),
) -> Result<T, ConnectError> {
    let mut delays = RETRY_DELAYS.iter();
    loop {
        match connect(ch) {
            Ok(t) => return Ok(t),
            Err(e) if is_retryable(e.errno, configured) => match delays.next() {
                Some(&d) => sleep(d),
                None => return Err(e),
            },
            Err(e) => return Err(e),
        }
    }
}

/// Channel probe behind [`open_transport`], with connect and sleep injected
/// so tests run without sockets or real delays.
///
/// A configured channel still busy after its retries fails at once with
/// [`BmapError::Busy`]: the headset is there, so probing other channels would
/// only add delay. A fallback still busy at the end is reported the same way
/// rather than "no channel found".
fn probe_channels<T: Transport>(
    mac: &str,
    channel: u8,
    init_packet: Option<device::Addr>,
    mut connect: impl FnMut(u8) -> Result<T, ConnectError>,
    mut sleep: impl FnMut(Duration),
) -> BmapResult<T> {
    let candidates: Vec<u8> = std::iter::once(channel)
        .chain(FALLBACK_CHANNELS.iter().copied().filter(|&c| c != channel))
        .collect();
    let mut first_error: Option<BmapError> = None;
    let mut busy_error: Option<BmapError> = None;
    let mut tried: Vec<String> = Vec::new();

    for (i, &ch) in candidates.iter().enumerate() {
        tried.push(ch.to_string());
        let transport = match connect_with_retry(ch, i == 0, &mut connect, &mut sleep) {
            Ok(t) => t,
            Err(e) => {
                if e.errno == Some(libc::EBUSY) && busy_error.is_none() {
                    busy_error = Some(e.error);
                    if i == 0 {
                        break;
                    }
                } else {
                    first_error.get_or_insert(e.error);
                }
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

    if let Some(e) = busy_error {
        // Bare transport message, without the "Connection error: " prefix,
        // so the text matches Python and C++.
        let detail = match e {
            BmapError::Connection(msg) => msg,
            other => other.to_string(),
        };
        return Err(BmapError::Busy(format!(
            "{} ({}, tried {}): {}",
            BUSY_MESSAGE, mac, tried.join(", "), detail
        )));
    }
    Err(BmapError::Connection(format!(
        "No BMAP channel found on {} (tried {}): {}",
        mac,
        tried.join(", "),
        first_error.map(|e| e.to_string()).unwrap_or_default()
    )))
}

fn send_init(transport: &impl Transport, init_packet: Option<device::Addr>) -> BmapResult<()> {
    if let Some(init) = init_packet {
        let pkt = protocol::bmap_packet(init.0, init.1, protocol::Operator::Get, &[]);
        transport.send_recv(&pkt)?;
    }
    Ok(())
}

/// Send a firmware GET and return true on any parseable BMAP reply.
fn speaks_bmap(transport: &impl Transport, init_packet: Option<device::Addr>) -> bool {
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

#[cfg(test)]
mod probe_tests {
    //! EBUSY / ECONNREFUSED backoff in the channel probe (issue #39).
    use super::*;
    use std::cell::RefCell;
    use std::collections::HashMap;

    /// Answers the firmware GET like a real BMAP peer.
    struct FakeTransport {
        channel: u8,
    }

    impl Transport for FakeTransport {
        fn send_recv(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
            Ok(vec![packet[0], packet[1], 0x03, 1, b'1'])
        }
        fn send_recv_drain(&self, packet: &[u8]) -> BmapResult<Vec<u8>> {
            self.send_recv(packet)
        }
    }

    #[derive(Clone, Copy)]
    enum Outcome {
        Up,
        Errno(i32),
    }
    use Outcome::*;

    struct Harness {
        attempts: RefCell<Vec<u8>>,
        sleeps: RefCell<Vec<Duration>>,
    }

    /// Run the probe for a device configured on channel 2. Each channel's
    /// script is consumed one entry per connect attempt; the last repeats.
    fn run(script: &[(u8, &[Outcome])]) -> (BmapResult<FakeTransport>, Harness) {
        let mut script: HashMap<u8, Vec<Outcome>> =
            script.iter().map(|(c, o)| (*c, o.to_vec())).collect();
        let h = Harness { attempts: RefCell::new(vec![]), sleeps: RefCell::new(vec![]) };
        let result = probe_channels(
            "00:11:22:33:44:55",
            2,
            None,
            |ch| {
                h.attempts.borrow_mut().push(ch);
                let outcomes = script.entry(ch).or_insert_with(|| vec![Errno(libc::EHOSTDOWN)]);
                let outcome = if outcomes.len() > 1 { outcomes.remove(0) } else { outcomes[0] };
                match outcome {
                    Up => Ok(FakeTransport { channel: ch }),
                    // Same shape as RfcommTransport::try_connect's message.
                    Errno(code) => Err(ConnectError {
                        error: BmapError::Connection(format!(
                            "Failed to connect to {}: {}",
                            "00:11:22:33:44:55",
                            std::io::Error::from_raw_os_error(code)
                        )),
                        errno: Some(code),
                    }),
                }
            },
            |d| h.sleeps.borrow_mut().push(d),
        );
        (result, h)
    }

    fn secs(v: &[f64]) -> Vec<Duration> {
        v.iter().map(|&s| Duration::from_secs_f64(s)).collect()
    }

    #[test]
    fn ebusy_twice_then_success_stays_on_channel() {
        let (res, h) = run(&[(2, &[Errno(libc::EBUSY), Errno(libc::EBUSY), Up])]);
        assert_eq!(res.unwrap().channel, 2);
        assert_eq!(*h.attempts.borrow(), vec![2, 2, 2]);
        assert_eq!(*h.sleeps.borrow(), secs(&[0.5, 1.0]));
    }

    #[test]
    fn ebusy_forever_reports_busy() {
        let busy: &[Outcome] = &[Errno(libc::EBUSY)];
        let (res, h) = run(&[(2, busy), (8, busy), (9, busy)]);
        // One try plus three retries on the configured channel, then stop.
        assert_eq!(*h.attempts.borrow(), vec![2; 4]);
        assert_eq!(*h.sleeps.borrow(), secs(&[0.5, 1.0, 2.0]));
        match res {
            Err(BmapError::Busy(msg)) => {
                assert!(msg.starts_with("Headphones busy"));
                assert!(!msg.contains("No BMAP channel found"));
                assert!(!msg.contains("Connection error: "));
                assert!(msg.contains("tried 2): Failed to connect to "));
                assert!(msg.contains("(os error 16)"));
            }
            other => panic!("expected Busy, got {:?}", other.err()),
        }
    }

    #[test]
    fn busy_configured_channel_stops_probe() {
        let (res, h) = run(&[(2, &[Errno(libc::EBUSY)]), (8, &[Up]), (9, &[Up])]);
        assert!(matches!(res, Err(BmapError::Busy(_))));
        assert_eq!(*h.attempts.borrow(), vec![2; 4]);
        assert_eq!(*h.sleeps.borrow(), secs(&[0.5, 1.0, 2.0]));
    }

    #[test]
    fn busy_fallback_reported_as_busy() {
        let (res, h) = run(&[
            (2, &[Errno(libc::EHOSTDOWN)]),
            (8, &[Errno(libc::EBUSY)]),
            (9, &[Errno(libc::EHOSTDOWN)]),
        ]);
        assert!(matches!(res, Err(BmapError::Busy(_))));
        assert_eq!(*h.attempts.borrow(), vec![2, 8, 8, 8, 8, 9]);
        assert_eq!(*h.sleeps.borrow(), secs(&[0.5, 1.0, 2.0]));
    }

    #[test]
    fn econnrefused_on_fallback_moves_on_without_sleep() {
        let (res, h) = run(&[
            (2, &[Errno(libc::EHOSTDOWN)]),
            (8, &[Errno(libc::ECONNREFUSED), Up]),
            (9, &[Up]),
        ]);
        assert_eq!(res.unwrap().channel, 9);
        assert_eq!(*h.attempts.borrow(), vec![2, 8, 9]);
        assert!(h.sleeps.borrow().is_empty());
    }

    #[test]
    fn econnrefused_then_success() {
        let (res, h) = run(&[(2, &[Errno(libc::ECONNREFUSED), Up])]);
        assert_eq!(res.unwrap().channel, 2);
        assert_eq!(*h.attempts.borrow(), vec![2, 2]);
        assert_eq!(*h.sleeps.borrow(), secs(&[0.5]));
    }

    #[test]
    fn econnrefused_forever_is_not_reported_as_busy() {
        let refused: &[Outcome] = &[Errno(libc::ECONNREFUSED)];
        let (res, h) = run(&[(2, refused), (8, refused), (9, refused)]);
        match res {
            Err(BmapError::Connection(msg)) => assert!(msg.contains("No BMAP channel found")),
            other => panic!("expected Connection, got {:?}", other.err()),
        }
        // Configured channel only; refusing fallbacks move on.
        assert_eq!(*h.sleeps.borrow(), secs(&[0.5, 1.0, 2.0]));
    }

    #[test]
    fn non_retryable_error_moves_on_without_sleep() {
        let (res, h) = run(&[(2, &[Errno(libc::EHOSTDOWN)]), (8, &[Up])]);
        assert_eq!(res.unwrap().channel, 8);
        assert_eq!(*h.attempts.borrow(), vec![2, 8]);
        assert!(h.sleeps.borrow().is_empty());
    }

    #[test]
    fn error_without_errno_is_not_retried() {
        let attempts = RefCell::new(vec![]);
        let sleeps = RefCell::new(0);
        let res: BmapResult<FakeTransport> = probe_channels(
            "00:11:22:33:44:55",
            2,
            None,
            |ch| {
                attempts.borrow_mut().push(ch);
                Err(BmapError::Connection("Invalid MAC address".into()).into())
            },
            |_| *sleeps.borrow_mut() += 1,
        );
        assert!(matches!(res, Err(BmapError::Connection(_))));
        assert_eq!(*attempts.borrow(), vec![2, 8, 9]);
        assert_eq!(*sleeps.borrow(), 0);
    }
}
