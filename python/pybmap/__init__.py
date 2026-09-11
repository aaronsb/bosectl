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
    BmapDeviceError, BmapTimeoutError, BmapNotFoundError, BmapDesyncError,
)
from .types import DeviceStatus, ModeConfig, EqBand, ButtonMapping, BmapResponse
from .protocol import bmap_packet, parse_response, parse_all_responses
from .constants import OP_STATUS

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
    transport = _open_transport(mac, channel, device)
    return BmapConnection(transport, device)


# RFCOMM channels BMAP has been observed on. The channel a unit exposes can
# vary with firmware and with which profiles bluetoothd has already claimed,
# so the device's configured channel is a first guess rather than a fact.
FALLBACK_CHANNELS = (2, 8, 9)


def _open_transport(mac, channel, device):
    """Connect on the configured channel, then probe fallbacks.

    A socket that accepts the connection is not proof of BMAP — several
    channels accept and stay silent — so each candidate is confirmed with a
    firmware GET [0.5] before it is returned.
    """
    init = getattr(device, "INIT_PACKET", None)
    candidates = [channel] + [c for c in FALLBACK_CHANNELS if c != channel]
    first_error = None
    for i, ch in enumerate(candidates):
        transport = RfcommTransport(mac, channel=ch)
        try:
            transport.connect()
        except BmapConnectionError as e:
            first_error = first_error or e
            continue
        if i == 0:
            # Configured channel connected: trust it, send init if needed.
            if init:
                fblock, func = init
                transport.send_recv(bmap_packet(fblock, func, 1))  # GET
            return transport
        if _speaks_bmap(transport, init):
            return transport
        transport.close()
    raise BmapConnectionError(
        "No BMAP channel found on %s (tried %s): %s"
        % (mac, ", ".join(str(c) for c in candidates), first_error)
    )


def _speaks_bmap(transport, init):
    """Send a firmware GET and return True on any parseable BMAP reply."""
    try:
        if init:
            fblock, func = init
            transport.send_recv(bmap_packet(fblock, func, 1))
        data = transport.send_recv(bmap_packet(0, 5, 1))  # GET firmware
    except BmapError:
        return False
    resp = parse_response(data)
    # Any 4+ byte reply parses; a real BMAP peer echoes the address we asked.
    return (resp is not None and resp.fblock == 0 and resp.func == 5
            and resp.op == OP_STATUS)
