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
    cancelling, as on other models). SETGET replies only with notifications on.
    The third byte is ANC on/off: SETGET [step, 0] turns ANC off (the Bose app
    shows noise cancelling off), [step, 1] turns it back on
  - CNC presets [1.15]: GET + SETGET works: [selected index, step, step, step]
    (the levels the headphones' button cycles through, 0/5/10 by default; the
    Bose app's noise cancelling favorites). SETGET must carry all 4 bytes
    (3 bytes: ERROR Length) and switches CNC to the selected preset
  - CNC persistence [1.14]: GET + SETGET works (the Bose app's "Remember my
    last setting", 1 = on)
  - EQ [1.7]: GET + SETGET works (3-band, -10 to +10). SETGET [value, band]
    is answered with the new [1.7] state
  - Buttons [1.9]: GET + SETGET works (Shortcut, press and hold; Battery
    level, Alexa wake word, Spotify Tap and WindMode supported). SETGET
    [80 05 07] switched the Bose app's Shortcut to the wake word toggle
  - Multipoint [1.10], sidetone [1.11]: GET works
  - No AudioModes block [31] (ERROR FblockNotSupp) and no ANR [1.6] (ERROR FuncNotSupp)
"""

from . import parsers
from ..constants import ACTION_MODES

RFCOMM_CHANNEL = 8

INIT_PACKET = None

# Show only the settings this device has in `status`, instead of "off" for the rest.
STATUS_SUPPORTED_ONLY = True

# ANC on/off is the enabled byte of CNC [1.5]: [steps, step, enabled]. SETGET
# [step, 0] turns ANC off and keeps the step; the Bose app then shows noise
# cancelling as off.
SUPPORTS_ANC_TOGGLE = True

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
    # Product name, multipoint and sidetone read correctly, but no write to
    # them has been checked on a 700, so they are read-only. Once a write has
    # been checked, drop its "read_only" line and restore its builder.
    "product_name": {
        "addr": (1, 2),
        "parser": parsers.parse_product_name,
        "read_only": True,
        # "builder": lambda name: name.encode("utf-8"),
    },
    "cnc": {
        "addr": (1, 5),
        "parser": parsers.parse_cnc,
        "builder": parsers.build_cnc,
    },
    # The three CNC steps the button cycles through ("noise cancelling
    # favorites" in the Bose app): [selected index, step, step, step].
    "cnc_presets": {
        "addr": (1, 15),
    },
    # "Remember my last setting" in the Bose app: 1 = on, 0 = off.
    "cnc_persist": {
        "addr": (1, 14),
        "parser": parsers.parse_bool,
        "builder": parsers.build_toggle,
    },
    "eq": {
        "addr": (1, 7),
        "parser": parsers.parse_eq,
        "builder": parsers.build_eq_band,
    },
    "buttons": {
        "addr": (1, 9),
        "parser": parse_buttons,
        "builder": parsers.build_buttons,
    },
    "multipoint": {
        "addr": (1, 10),
        "parser": parsers.parse_multipoint,
        "read_only": True,
        # "builder": parsers.build_toggle,
    },
    "sidetone": {
        "addr": (1, 11),
        "parser": parsers.parse_sidetone,
        "read_only": True,
        # "builder": parsers.build_sidetone,
    },
}

PRESET_MODES = {}

MODE_BY_IDX = {}

EDITABLE_SLOTS = []
