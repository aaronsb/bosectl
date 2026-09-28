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

import errno
import time

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
    BmapDeviceError, BmapTimeoutError, BmapNotFoundError, BmapInvalidArgError,
    BmapDesyncError, BmapBusyError,
)
from .types import (
    BatteryReading, BatteryStatus, BmapResponse, ButtonMapping, DeviceStatus,
    EqBand, ModeConfig,
)
from .protocol import bmap_packet, parse_response, parse_all_responses
from .constants import OP_STATUS

__version__ = "0.4.1"


def connect(mac=None, device_type=None):
    """Connect to a BMAP device.

    Args:
        mac: Bluetooth MAC address. Auto-detected if None.
        device_type: Device type string (e.g. "qc_ultra2", "qc35").
                     Required when mac is specified; auto-detected otherwise.

    Returns:
        BmapConnection context manager.

    Raises:
        BmapNotFoundError: If no device is found.
        BmapConnectionError: If the connection fails.
    """
    mac = mac or None
    device_type = device_type or None

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
    elif device_type is None:
        raise BmapInvalidArgError("device_type is required when mac is specified")

    device = get_device(device_type)
    channel = getattr(device, "RFCOMM_CHANNEL", 2)
    transport = _open_transport(mac, channel, device)
    return BmapConnection(transport, device)


# RFCOMM channels BMAP has been observed on. The channel a unit exposes can
# vary with firmware and with which profiles bluetoothd has already claimed,
# so the device's configured channel is a first guess rather than a fact.
FALLBACK_CHANNELS = (2, 8, 9)


# Connect errors that mean "not right now" rather than "not here": the
# headset is still tearing down the previous RFCOMM link (EBUSY) or has not
# yet re-listened on the channel (ECONNREFUSED). The same channel is retried
# after each delay before the probe moves on. ECONNREFUSED is retried only on
# the configured channel: a fallback that refuses is usually just not a BMAP
# channel. Linux only; the macOS transport's errors carry no errno.
RETRYABLE_ERRNOS = frozenset({errno.EBUSY, errno.ECONNREFUSED})
FALLBACK_RETRYABLE_ERRNOS = frozenset({errno.EBUSY})
RETRY_DELAYS = (0.5, 1.0, 2.0)

# Indirection so tests can replace the backoff without actually sleeping.
_sleep = time.sleep

BUSY_MESSAGE = ("Headphones busy (another connection is still closing); "
                "try again in a few seconds")


def _connect_with_retry(mac, ch, retryable):
    """Open ``ch``, retrying errnos in ``retryable`` with backoff.

    Returns the connected transport; raises the last BmapConnectionError.
    """
    for delay in RETRY_DELAYS + (None,):
        transport = RfcommTransport(mac, channel=ch)
        try:
            transport.connect()
            return transport
        except BmapConnectionError as e:
            if delay is None or getattr(e, "errno", None) not in retryable:
                raise
        _sleep(delay)


def _open_transport(mac, channel, device):
    """Connect on the configured channel, then probe fallbacks.

    A socket that accepts the connection is not proof of BMAP — several
    channels accept and stay silent — so each candidate is confirmed with a
    firmware GET [0.5] before it is returned.

    Each channel is retried on EBUSY (the configured one also on
    ECONNREFUSED, see RETRY_DELAYS) before the probe moves on. A configured
    channel still busy after its retries raises BmapBusyError at once: the
    headset is there, so probing other channels would only add delay. A
    fallback still busy at the end is reported the same way rather than
    "no channel found".
    """
    init = getattr(device, "INIT_PACKET", None)
    candidates = [channel] + [c for c in FALLBACK_CHANNELS if c != channel]
    first_error = None
    busy_error = None
    tried = []
    for i, ch in enumerate(candidates):
        tried.append(str(ch))
        try:
            transport = _connect_with_retry(
                mac, ch, RETRYABLE_ERRNOS if i == 0 else FALLBACK_RETRYABLE_ERRNOS)
        except BmapConnectionError as e:
            first_error = first_error or e
            if busy_error is None and getattr(e, "errno", None) == errno.EBUSY:
                busy_error = e
                if i == 0:
                    break
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
    tried = ", ".join(tried)
    if busy_error is not None:
        raise BmapBusyError(
            "%s (%s, tried %s): %s" % (BUSY_MESSAGE, mac, tried, busy_error),
            errno=errno.EBUSY,
        )
    raise BmapConnectionError(
        "No BMAP channel found on %s (tried %s): %s"
        % (mac, tried, first_error)
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
