"""Auto-detect paired BMAP devices via bluetoothctl (Linux)."""

import re
import subprocess

from .catalog import BMAP_UUID, lookup_device


def find_bmap_device():
    """Auto-detect a paired, connected BMAP-capable Bluetooth device.

    Prioritizes connected devices over paired-but-disconnected ones.
    Returns (mac, device_type) tuple, or (None, None) if not found.
    """
    candidates = _scan_paired_devices()

    # Prefer connected devices
    for mac, device_type, connected in candidates:
        if connected:
            return (mac, device_type)

    # Fall back to first paired BMAP device
    for mac, device_type, connected in candidates:
        return (mac, device_type)

    return (None, None)


def _scan_paired_devices():
    """Scan paired Bluetooth devices for BMAP-capable headphones.

    Returns list of (mac, device_type, is_connected) tuples.
    """
    candidates = []
    try:
        result = subprocess.run(
            ["bluetoothctl", "devices", "Paired"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split(None, 2)
            if len(parts) < 2:
                continue
            mac = parts[1]
            info = subprocess.run(
                ["bluetoothctl", "info", mac],
                capture_output=True, text=True, timeout=3,
            )
            info_text = info.stdout

            # Must be an audio device with the BMAP UUID
            is_audio = ("audio-headset" in info_text or "audio-headphones" in info_text)
            has_bmap = BMAP_UUID in info_text
            if not (is_audio and has_bmap):
                continue

            connected = "Connected: yes" in info_text

            # Determine device type from Modalias product ID
            device_type = _detect_device_type(info_text)

            candidates.append((mac, device_type, connected))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return candidates


def _detect_device_type(info_text):
    """Extract device type from bluetoothctl info output via catalog lookup.

    Parses Modalias (bluetooth:vXXXXpYYYYdZZZZ) to get the product ID,
    then looks it up in the device catalog.

    Falls back to "qc_ultra2" if the product ID is unknown.
    """
    match = re.search(r"Modalias:\s*bluetooth:v[0-9A-Fa-f]{4}p([0-9A-Fa-f]{4})", info_text)
    if match:
        product_id = int(match.group(1), 16)
        entry = lookup_device(product_id)
        if entry and entry.config:
            return entry.config
    return "qc_ultra2"  # default for unknown BMAP devices
