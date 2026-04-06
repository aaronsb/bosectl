"""Device registry for BMAP-capable devices."""

from . import qc_ultra2
from . import qc35

# Registry of supported devices keyed by type string.
DEVICES = {
    "qc_ultra2": qc_ultra2,
    "qc35": qc35,
}

# Product ID -> device type (for auto-detection after connecting).
PRODUCT_IDS = {
    0x4082: "qc_ultra2",
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
