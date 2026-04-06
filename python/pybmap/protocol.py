"""Universal BMAP packet encoding and decoding.

The BMAP (Bose Messaging and Protocol) framing is shared across all Bose
Bluetooth devices. This module handles packet construction and parsing
with no device-specific knowledge and no I/O.

Packet format: [fblock_id, function_id, flags, payload_length, ...payload]
Flags byte:    (device_id << 6) | (port_num << 4) | (operator & 0x0F)
"""

from .constants import OP_ERROR, OP_NAMES, ERROR_NAMES
from .types import BmapResponse


def bmap_packet(fblock, func, operator, payload=b""):
    """Build a BMAP packet from components.

    Args:
        fblock: Function block ID (0-255).
        func: Function ID within the block (0-255).
        operator: BMAP operator (OP_SET, OP_GET, etc.).
        payload: Raw payload bytes.

    Returns:
        Complete packet as bytes.
    """
    flags = operator & 0x0F
    return bytes([fblock, func, flags, len(payload)]) + payload


def parse_response(data):
    """Parse a single BMAP response from raw bytes.

    Returns:
        BmapResponse namedtuple, or None if data is too short.
    """
    if len(data) < 4:
        return None
    fblock = data[0]
    func = data[1]
    op = data[2] & 0x0F
    length = data[3]
    payload = data[4:4 + length]
    return BmapResponse(fblock, func, op, payload)


def parse_all_responses(data):
    """Parse concatenated BMAP responses into a list.

    BMAP devices may send multiple packets back-to-back (e.g., GetAll
    returns one STATUS per mode). This splits them using each packet's
    length field.

    Returns:
        List of BmapResponse namedtuples.
    """
    responses = []
    pos = 0
    while pos + 4 <= len(data):
        fblock = data[pos]
        func = data[pos + 1]
        op = data[pos + 2] & 0x0F
        length = data[pos + 3]
        if pos + 4 + length > len(data):
            break  # Truncated packet
        payload = data[pos + 4:pos + 4 + length]
        responses.append(BmapResponse(fblock, func, op, payload))
        pos += 4 + length
    return responses


def fmt_response(resp):
    """Format a BmapResponse as a human-readable string.

    Examples:
        "[31.3] RESULT: 00"
        "[1.5] ERROR: OpNotSupp(auth) (05)"
    """
    op_name = OP_NAMES.get(resp.op, "op%d" % resp.op)
    if resp.op == OP_ERROR and resp.payload:
        err_name = ERROR_NAMES.get(resp.payload[0], "err%d" % resp.payload[0])
        return "[%d.%d] %s: %s (%s)" % (resp.fblock, resp.func, op_name, err_name, resp.payload.hex())
    return "[%d.%d] %s: %s" % (resp.fblock, resp.func, op_name, resp.payload.hex())


def encode_mode_name(name):
    """Encode a mode name as a 32-byte null-terminated, null-padded array.

    The firmware stores mode names as fixed 32-byte fields. Names longer
    than 31 bytes are truncated.
    """
    name_bytes = name.encode("utf-8")
    buf = bytearray(32)
    end = min(len(name_bytes), 31)
    buf[:end] = name_bytes[:end]
    buf[end] = 0
    return bytes(buf)
