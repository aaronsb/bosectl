"""Bose device catalog — known BMAP-capable devices.

Source: https://downloads.bose.com/lookup.xml
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
# All known BMAP-capable Bose devices. Entries with config=None are
# recognized but not yet supported — they serve as a roadmap for
# future protocol implementations.

CATALOG = {
    # Headphones
    0x4017: BoseDevice(0x4017, "kleos",     "QuietComfort 35",                "headphones", "qc35"),
    0x4020: BoseDevice(0x4020, "baywolf",   "QuietComfort 35 II",             "headphones", "qc35"),
    0x4024: BoseDevice(0x4024, "goodyear",  "Noise Cancelling Headphones 700","headphones", None),
    0x4061: BoseDevice(0x4061, "vedder",    "QuietComfort 45",                "headphones", None),
    0x4082: BoseDevice(0x4082, "wolverine", "QuietComfort Ultra Headphones",  "headphones", "qc_ultra2"),

    # Earbuds
    0x4060: BoseDevice(0x4060, "olivia",    "QuietComfort Earbuds II",        "earbuds", None),
    0x4063: BoseDevice(0x4063, "edith",     "Ultra Open Earbuds",             "earbuds", None),
    0x4075: BoseDevice(0x4075, "prince",    "QuietComfort Ultra Earbuds",     "earbuds", None),

    # Speakers
    0x402D: BoseDevice(0x402D, "revel",     "Home Speaker 300",               "speaker", None),
    0x402F: BoseDevice(0x402F, "lando",     "Portable Home Speaker",          "speaker", None),
    0x4039: BoseDevice(0x4039, "duran",     "SoundLink Flex",                 "speaker", None),
    0x403A: BoseDevice(0x403A, "gwen",      "SoundLink Revolve+ II",          "speaker", None),
    0x4066: BoseDevice(0x4066, "lonestarr", "SoundLink Max",                  "speaker", None),
    0x4073: BoseDevice(0x4073, "scotty",    "SoundLink Flex 2nd Gen",         "speaker", None),
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
