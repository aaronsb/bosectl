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
from .catalog import (
    BOSE_USB_VID, BMAP_UUID, BoseDevice, CATALOG,
    lookup_device, known_devices, supported_devices, is_supported,
    usb_ids, modalias,
)
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
        detected_mac, detected_type = find_bmap_device()
        if detected_mac is None:
            raise BmapNotFoundError(
                "No connected BMAP device found. Pair and connect "
                "via bluetoothctl, or pass mac= explicitly."
            )
        mac = detected_mac
        if device_type is None:
            device_type = detected_type

    if device_type is None:
        device_type = "qc_ultra2"

    device = get_device(device_type)
    channel = getattr(device, "RFCOMM_CHANNEL", 2)
    transport = RfcommTransport(mac, channel=channel)
    transport.connect()

    # Some devices require an init packet before responding.
    init = getattr(device, "INIT_PACKET", None)
    if init:
        fblock, func = init
        transport.send_recv(bmap_packet(fblock, func, 1))  # GET

    return BmapConnection(transport, device)
