"""Device registry for BMAP-capable devices."""

from . import qc_ultra2
from . import qc_ultra2_earbuds
from . import qc35
from . import qc_prince
from . import qc_earbuds
from . import qc45
from . import ultra_open
from . import nc700

# Registry of supported devices keyed by type string.
DEVICES = {
    "qc_ultra2": qc_ultra2,
    "qc_ultra2_earbuds": qc_ultra2_earbuds,
    "qc35": qc35,
    "qc_prince": qc_prince,
    "qc_earbuds": qc_earbuds,
    "qc45": qc45,
    "ultra_open": ultra_open,
    "nc700": nc700,
}

# Product ID -> device type (for auto-detection after connecting).
PRODUCT_IDS = {
    0x4082: "qc_ultra2",
    0x4083: "qc_ultra2",  # QuietComfort Headphones (2nd Gen) — same BMAP layout as wolverine
    0x4062: "qc_ultra2_earbuds",
    0x4075: "qc_prince",
    0x402F: "qc_earbuds",
    0x4039: "qc45",
    0x4068: "ultra_open",
    0x4024: "nc700",
    # TODO: add QC35 product ID once verified
}


def get_device(device_type):
    """Look up a device module by type string.

    Returns:
        Device module with FEATURES, PRESET_MODES, etc.

    Raises:
        BmapError: If the device type is not supported.
    """
    from ..errors import BmapError
    if device_type not in DEVICES:
        raise BmapError(
            "Unknown device type '%s'. Supported: %s" % (
                device_type, ", ".join(sorted(DEVICES.keys()))
            )
        )
    return DEVICES[device_type]


def detect_device_type(product_id):
    """Determine device type from a BMAP product ID.

    Returns:
        Device type string, or None if unknown.
    """
    return PRODUCT_IDS.get(product_id)
