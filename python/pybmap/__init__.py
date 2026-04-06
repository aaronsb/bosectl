"""pybmap — Control Bluetooth audio devices over the BMAP protocol.

Usage:
    import pybmap

    with pybmap.connect() as dev:
        print(dev.battery())
        dev.set_cnc(8)
        dev.set_eq(3, 0, -2)
        dev.set_mode("quiet")

    # Explicit MAC and device type:
    with pybmap.connect(mac="68:F2:1F:XX:XX:XX", device_type="qc_ultra2") as dev:
        ...
"""

from .connection import BmapConnection
from .transport import RfcommTransport
from .discovery import find_bmap_device
from .devices import DEVICES, get_device
from .errors import (
    BmapError, BmapConnectionError, BmapAuthError,
    BmapDeviceError, BmapTimeoutError, BmapNotFoundError,
)
from .types import DeviceStatus, ModeConfig, EqBand, ButtonMapping, BmapResponse
from .protocol import bmap_packet, parse_response, parse_all_responses

__version__ = "0.1.0"


def connect(mac=None, device_type=None):
    """Connect to a BMAP device.

    Args:
        mac: Bluetooth MAC address. Auto-detected if None.
        device_type: Device type string (e.g. "qc_ultra2", "qc35").
                     Defaults to "qc_ultra2" if not specified.

    Returns:
        BmapConnection context manager.

    Raises:
        BmapNotFoundError: If no device is found.
        BmapConnectionError: If the connection fails.
    """
    if mac is None:
        mac = find_bmap_device()
        if mac is None:
            raise BmapNotFoundError(
                "No BMAP device found. Pair via bluetoothctl, "
                "or pass mac= explicitly."
            )

    if device_type is None:
        device_type = "qc_ultra2"

    device = get_device(device_type)
    channel = getattr(device, "RFCOMM_CHANNEL", 2)
    transport = RfcommTransport(mac, channel=channel)
    transport.connect()
    return BmapConnection(transport, device)
