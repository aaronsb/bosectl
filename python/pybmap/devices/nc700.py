"""Bose Noise Cancelling Headphones 700 device configuration.

Codename "goodyear", product ID 0x4024. Confirmed on hardware, firmware
1.8.2-11524+e0f7590. BMAP on RFCOMM channel 8 (the SPP record). The BMAP
UUID's own SDP record leads to a channel that only repeats a status beacon
(ff 55 02 00 ee 10) and ignores commands. No init packet is needed.

The 700 applies SETGET writes but doesn't answer them until notifications
are enabled with SETGET [9.2] (NotificationByFblock). Without it a CNC write
takes effect and then times out. NOTIFICATIONS below is sent on connect; the
payload is the one the Bose app sends: mask 0x01, then a 4-byte big-endian
bitmap of function blocks (0x00050237 = blocks 0, 1, 2, 4, 5, 9, 16, 18).

Capabilities confirmed on hardware:
  - Battery, firmware, product name: GET works
  - CNC [1.5]: GET + SETGET works without auth (11 steps; step 0 = most
    cancelling, as on other models). SETGET replies only with notifications on
  - CNC presets [1.15]: GET returns [selected index, step, step, step]
    (the levels the headphones' button cycles through, 0/5/10 by default)
  - EQ [1.7]: GET works (3-band, -10 to +10)
  - Buttons [1.9]: GET works (Shortcut, press and hold; Battery level, Alexa
    wake word, Spotify Tap and mode 13 supported). SETGET not tried
  - Multipoint [1.10], sidetone [1.11]: GET works
  - No AudioModes block [31] (ERROR BlockNotSupp) and no ANR [1.6] (ERROR FuncNotSupp)
"""

from . import parsers
from ..constants import ACTION_MODES

RFCOMM_CHANNEL = 8

INIT_PACKET = None

# Show only the settings this device has in `status`, instead of "off" for the rest.
STATUS_SUPPORTED_ONLY = True

# SETGET [9.2] payload sent on connect; see the module docstring.
NOTIFICATIONS = bytes([0x01, 0x00, 0x05, 0x02, 0x37])

DEVICE_INFO = {
    "name": "Bose Noise Cancelling Headphones 700",
    "codename": "goodyear",
    "product_id": 0x4024,
    "variant": 0x01,
}

def parse_buttons(payload):
    """parsers.parse_buttons, with the supported actions read as the Bose app reads them.

    The 700 reports supported actions as a 4-byte big-endian bitmap (the last byte
    holds actions 0-7): 00 01 20 88 = BatteryLevel, ToggleWakeWord, WindMode,
    SpotifyGo, which includes its current action.
    """
    btn = parsers.parse_buttons(payload)
    if btn is None:
        return None
    bitmap = payload[3:7]
    value = int.from_bytes(bitmap, "big")
    supported = [ACTION_MODES.get(i, "unknown(%d)" % i)
                 for i in range(1, len(bitmap) * 8) if value & (1 << i)]
    return btn._replace(supported_actions=supported)


FEATURES = {
    "battery": {
        "addr": (2, 2),
        "parser": parsers.parse_battery,
    },
    "firmware": {
        "addr": (0, 5),
        "parser": parsers.parse_firmware,
    },
    "product_name": {
        "addr": (1, 2),
        "parser": parsers.parse_product_name,
    },
    "cnc": {
        "addr": (1, 5),
        "parser": parsers.parse_cnc,
        "builder": parsers.build_cnc,
    },
    "eq": {
        "addr": (1, 7),
        "parser": parsers.parse_eq,
    },
    "buttons": {
        "addr": (1, 9),
        "parser": parse_buttons,
    },
    "multipoint": {
        "addr": (1, 10),
        "parser": parsers.parse_multipoint,
    },
    "sidetone": {
        "addr": (1, 11),
        "parser": parsers.parse_sidetone,
    },
}

PRESET_MODES = {}

MODE_BY_IDX = {}

EDITABLE_SLOTS = []
