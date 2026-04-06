"""Bose QC35 / QC35 II device configuration.

Verified against real QC35 hardware on firmware 4.8.1.
BMAP over RFCOMM channel 8 (not channel 2 like newer devices).

Capabilities verified:
  - Battery, firmware, serial, product name: GET works
  - Device name, sidetone, voice prompts: GET + SETGET works
  - Buttons: GET works (read-only)
  - Pairing mode: START works
  - NC level [3.2]: auth-gated on firmware 4.8.1 (was open on 1.x)
  - No EQ, no spatial audio, no AudioModes block 31, no power off,
    no multipoint, no auto-pause/answer
"""

from . import parsers

RFCOMM_CHANNEL = 8

# QC35 requires a GET [0.1] init packet before it responds to anything.
INIT_PACKET = (0, 1)  # (fblock, func) — sent as GET on connect

DEVICE_INFO = {
    "name": "Bose QuietComfort 35",
    "codename": "baywolf",
    "platform": "CSR8670",
    "product_id": 0x4020,
    "variant": 0x02,
}

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
        "builder": lambda name: name.encode("utf-8"),
    },
    "voice_prompts": {
        "addr": (1, 3),
        "parser": parsers.parse_voice_prompts,
        "builder": parsers.build_voice_prompts,
    },
    "sidetone": {
        "addr": (1, 11),
        "parser": parsers.parse_sidetone,
        "builder": parsers.build_sidetone,
    },
    "buttons": {
        "addr": (1, 9),
        "parser": parsers.parse_buttons,
        "builder": parsers.build_buttons,
    },
    "pairing": {
        "addr": (4, 8),
    },
    "anr": {
        "addr": (1, 6),
        "parser": parsers.parse_anr,
        "builder": parsers.build_anr,
    },
}

PRESET_MODES = {
    "high":  {"idx": 0, "description": "High — full noise cancellation"},
    "low":   {"idx": 1, "description": "Low — reduced noise cancellation"},
    "off":   {"idx": 2, "description": "Off — no noise cancellation"},
}

MODE_BY_IDX = {m["idx"]: name for name, m in PRESET_MODES.items()}

EDITABLE_SLOTS = []

STATUS_OFFSETS = {}
