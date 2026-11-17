//! Auto-detect paired BMAP devices via bluetoothctl (Linux).

use std::process::Command;

use crate::catalog::{self, BMAP_UUID};

/// A discovered BMAP device.
#[derive(Debug, Clone)]
pub struct DiscoveredDevice {
    pub mac: String,
    pub device_type: String,
    pub connected: bool,
}

/// Auto-detect a paired, connected BMAP-capable Bluetooth device.
///
/// Prioritizes connected devices. Returns (mac, device_type), or None.
pub fn find_bmap_device() -> Option<(String, String)> {
    let candidates = scan_paired_devices();

    // Prefer connected
    for d in &candidates {
        if d.connected {
            return Some((d.mac.clone(), d.device_type.clone()));
        }
    }
    // Fall back to first paired
    candidates.first().map(|d| (d.mac.clone(), d.device_type.clone()))
}

/// Scan all paired Bluetooth devices for BMAP-capable headphones.
pub fn scan_paired_devices() -> Vec<DiscoveredDevice> {
    let mut candidates = Vec::new();
    let output = match Command::new("bluetoothctl")
        .args(["devices", "Paired"])
        .output()
    {
        Ok(o) => String::from_utf8_lossy(&o.stdout).into_owned(),
        Err(_) => return candidates,
    };

    for line in output.lines() {
        let parts: Vec<&str> = line.splitn(3, ' ').collect();
        if parts.len() < 2 {
            continue;
        }
        let mac = parts[1];
        if !is_mac(mac) {
            continue;
        }

        let info = match Command::new("bluetoothctl")
            .args(["info", mac])
            .output()
        {
            Ok(o) => String::from_utf8_lossy(&o.stdout).into_owned(),
            Err(_) => continue,
        };

        let is_audio = info.contains("audio-headset") || info.contains("audio-headphones");
        let has_bmap = info.contains(BMAP_UUID);
        if !(is_audio && has_bmap) {
            continue;
        }

        let connected = info.contains("Connected: yes");
        let device_type = detect_device_type(&info);

        candidates.push(DiscoveredDevice {
            mac: mac.to_string(),
            device_type,
            connected,
        });
    }
    candidates
}

/// Detect device type from Modalias product ID via catalog lookup.
fn detect_device_type(info: &str) -> String {
    // Modalias format: bluetooth:vXXXXpYYYYdZZZZ
    for line in info.lines() {
        let trimmed = line.trim();
        if let Some(rest) = trimmed.strip_prefix("Modalias:") {
            let rest = rest.trim();
            if let Some(bt_rest) = rest.strip_prefix("bluetooth:v") {
                if bt_rest.len() >= 9 {
                    let after_vendor = &bt_rest[4..];
                    if after_vendor.starts_with('p') {
                        let id_str = &after_vendor[1..5];
                        if let Ok(product_id) = u16::from_str_radix(id_str, 16) {
                            if let Some(dev) = catalog::lookup_device(product_id) {
                                if let Some(config) = dev.config {
                                    return config.to_string();
                                }
                            }
                            return "qc_ultra2".to_string();
                        }
                    }
                }
            }
        }
    }
    "qc_ultra2".to_string()
}

/// Literal `xx:xx:xx:xx:xx:xx` check; mirrors the Python and C++ discovery guards.
fn is_mac(s: &str) -> bool {
    let b = s.as_bytes();
    b.len() == 17
        && b.iter().enumerate().all(|(i, &c)| {
            if i % 3 == 2 { c == b':' } else { c.is_ascii_hexdigit() }
        })
}

#[cfg(test)]
mod tests {
    #[allow(unused_imports)]
    use super::*;

    #[test]
    fn test_is_mac() {
        assert!(is_mac("AA:bb:CC:dd:EE:ff"));
        assert!(!is_mac("AA:bb:CC:dd:EE:f"));
        assert!(!is_mac("AA:bb:CC:dd:EE:ff;rm"));
        assert!(!is_mac("AA-bb-CC-dd-EE-ff"));
    }

    // Modalias line as reported for a NC 700 in issue #48.
    #[cfg(target_os = "linux")]
    #[test]
    fn test_nc700_modalias_detected() {
        let info = "Name: LE-NC 700\n\tModalias: bluetooth:v009Ep4024d0182\n";
        assert_eq!(detect_device_type(info), "nc700");
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn test_macos_discovery_returns_none() {
        let dev = find_bmap_device();
        assert!(dev.is_none());
    }
}
