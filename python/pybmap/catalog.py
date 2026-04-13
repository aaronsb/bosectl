"""Bose device catalog — known BMAP-capable devices.

Sourced from the decompiled Bose Music APK (BoseProductId.java enum).
The enum's `value` field is the product ID reported over Bluetooth
Modalias; verified against WOLVERINE (0x4082) and EDITH (0x4062).
USB VID 0x05a7 is shared by all Bose devices.

This module is the authoritative device registry. Discovery and
connection code reference it for product ID → device type mapping.
"""

from collections import namedtuple

# All Bose USB devices share this vendor ID.
BOSE_USB_VID = 0x05A7

# BMAP Bluetooth service UUID (SDP record).
BMAP_UUID = "00000000-deca-fade-deca-deafdecacaff"

BoseDevice = namedtuple("BoseDevice", [
    "product_id",   # USB PID / Bluetooth Modalias product ID
    "codename",     # Internal Bose codename (from firmware URLs)
    "name",         # Marketing product name
    "category",     # "headphones", "earbuds", or "speaker"
    "config",       # Library config key ("qc_ultra2", "qc35") or None
])


# ── Device Catalog ──────────────────────────────────────────────────────────
# Sourced from the decompiled Bose Music APK (BoseProductId.java enum).
# The enum's `value` field is the product ID reported over Bluetooth
# Modalias; verified against WOLVERINE (0x4082) and EDITH (0x4062).
#
# Entries with config=None are recognized but not yet supported — they
# serve as a roadmap for future protocol implementations.

CATALOG = {
    # Headphones
    0x400C: BoseDevice(0x400C, "wolfcastle", "QuietComfort 35",                      "headphones", "qc35"),
    0x4015: BoseDevice(0x4015, "stetson",    "Hearphones",                           "headphones", None),
    0x4020: BoseDevice(0x4020, "baywolf",    "QuietComfort 35 II",                   "headphones", "qc35"),
    0x4021: BoseDevice(0x4021, "atlas",      "ProFlight",                            "headphones", None),
    0x4024: BoseDevice(0x4024, "goodyear",   "Noise Cancelling Headphones 700",      "headphones", None),
    0x402B: BoseDevice(0x402B, "beanie",     "Hearphones II",                        "headphones", None),
    0x4039: BoseDevice(0x4039, "duran",      "QuietComfort 45",                      "headphones", None),
    0x4066: BoseDevice(0x4066, "lonestarr",  "QuietComfort Ultra Headphones",        "headphones", None),
    0x4075: BoseDevice(0x4075, "prince",     "QuietComfort Headphones",              "headphones", None),
    0x4082: BoseDevice(0x4082, "wolverine",  "QuietComfort Ultra Headphones (2nd Gen)", "headphones", "qc_ultra2"),

    # Earbuds
    0x4012: BoseDevice(0x4012, "ice",        "SoundSport",                           "earbuds", None),
    0x4013: BoseDevice(0x4013, "flurry",     "SoundSport Pulse",                     "earbuds", None),
    0x4014: BoseDevice(0x4014, "powder",     "QuietControl 30",                      "earbuds", None),
    0x4018: BoseDevice(0x4018, "levi",       "SoundSport Free",                      "earbuds", None),
    0x402C: BoseDevice(0x402C, "celine",     "Frames",                               "earbuds", None),
    0x402D: BoseDevice(0x402D, "revel",      "Sport Earbuds",                        "earbuds", None),
    0x402F: BoseDevice(0x402F, "lando",      "QuietComfort Earbuds",                 "earbuds", None),
    0x403A: BoseDevice(0x403A, "gwen",       "Sport Open Earbuds",                   "earbuds", None),
    0x404C: BoseDevice(0x404C, "celine_ii",  "Frames (2nd Gen)",                     "earbuds", None),
    0x4060: BoseDevice(0x4060, "olivia",     "Frames Tempo",                         "earbuds", None),
    0x4061: BoseDevice(0x4061, "vedder",     "Frames",                               "earbuds", None),
    0x4062: BoseDevice(0x4062, "edith",      "QuietComfort Ultra Earbuds (2nd Gen)", "earbuds", "qc_ultra2"),
    0x4064: BoseDevice(0x4064, "smalls",     "QuietComfort Earbuds II",              "earbuds", None),
    0x4068: BoseDevice(0x4068, "serena",     "Ultra Open Earbuds",                   "earbuds", None),
    0x4072: BoseDevice(0x4072, "scotty",     "QuietComfort Ultra Earbuds",           "earbuds", None),

    # Speakers
    0x400A: BoseDevice(0x400A, "isaac",      "AE2 SoundLink",                        "speaker", None),
    0x400D: BoseDevice(0x400D, "foreman",    "SoundLink Color II",                   "speaker", None),
    0x4010: BoseDevice(0x4010, "folgers",    "SoundLink Revolve",                    "speaker", None),
    0x4011: BoseDevice(0x4011, "harvey",     "SoundLink Revolve+",                   "speaker", None),
    0x4017: BoseDevice(0x4017, "kleos",      "SoundWear",                            "speaker", None),
    0x4022: BoseDevice(0x4022, "minnow",     "SoundLink Micro",                      "speaker", None),
    0x4085: BoseDevice(0x4085, "troy",       "SoundLink Plus",                       "speaker", None),
    0xA211: BoseDevice(0xA211, "chibi",      "S1 Pro",                               "speaker", None),
    0xBC58: BoseDevice(0xBC58, "billie",     "SoundLink Micro 2",                    "speaker", None),
    0xBC59: BoseDevice(0xBC59, "phelps",     "SoundLink Flex",                       "speaker", None),
    0xBC60: BoseDevice(0xBC60, "phelps_ii",  "SoundLink Flex (2nd Gen)",             "speaker", None),
    0xBC61: BoseDevice(0xBC61, "mathers",    "SoundLink Flex 2",                     "speaker", None),
    0xBC63: BoseDevice(0xBC63, "stan",       "SoundLink Flex SE 2",                  "speaker", None),
}


def lookup_device(product_id):
    """Look up a Bose device by product ID.

    Args:
        product_id: USB PID or Bluetooth Modalias product ID (int).

    Returns:
        BoseDevice namedtuple, or None if unknown.
    """
    return CATALOG.get(product_id)


def known_devices():
    """All known BMAP-capable Bose devices.

    Returns:
        List of BoseDevice namedtuples.
    """
    return list(CATALOG.values())


def supported_devices():
    """Devices with active library support (config is not None).

    Returns:
        List of BoseDevice namedtuples.
    """
    return [d for d in CATALOG.values() if d.config is not None]


def is_supported(product_id):
    """Check if a product ID has an active library implementation.

    Args:
        product_id: USB PID or Bluetooth Modalias product ID (int).

    Returns:
        True if the device has a config implementation.
    """
    entry = CATALOG.get(product_id)
    return entry is not None and entry.config is not None


def usb_ids(product_id):
    """Get USB vendor/product ID pair for a known device.

    Args:
        product_id: Bose product ID (int).

    Returns:
        (vendor_id, product_id) tuple, or None if unknown.
    """
    if product_id in CATALOG:
        return (BOSE_USB_VID, product_id)
    return None


def modalias(product_id):
    """Generate a Bluetooth Modalias string for a known device.

    Args:
        product_id: Bose product ID (int).

    Returns:
        Modalias string like "bluetooth:v009Bp4082d0000", or None.
    """
    if product_id in CATALOG:
        return "bluetooth:v%04Xp%04Xd0000" % (BOSE_USB_VID, product_id)
    return None
