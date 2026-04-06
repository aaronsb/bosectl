//! Auto-detect paired BMAP devices via bluetoothctl (Linux).

use std::process::Command;

/// BMAP service UUID found in SDP records.
pub const BMAP_UUID: &str = "00000000-deca-fade-deca-deafdecacaff";

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

/// Detect device type from Modalias product ID.
fn detect_device_type(info: &str) -> String {
    // Modalias format: bluetooth:vXXXXpYYYYdZZZZ
    for line in info.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("Modalias:") {
            if let Some(p_pos) = trimmed.find('p') {
                let id_str = &trimmed[p_pos + 1..p_pos + 5];
                if let Ok(product_id) = u16::from_str_radix(id_str, 16) {
                    return match product_id {
                        0x4082 => "qc_ultra2".to_string(),
                        0x4020 | 0x400C => "qc35".to_string(),
                        _ => "qc_ultra2".to_string(),
                    };
                }
            }
        }
    }
    "qc_ultra2".to_string()
}
