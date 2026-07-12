"""Bose QC Earbuds (1st Gen) device configuration.

Codename "lando", firmware 2.0.7.
BMAP over RFCOMM channel 8.

Key differences from QC Ultra 2 (wolverine):
  - Only 4 modes (0-3), no custom profile slots (4-10 are invalid)
  - ModeConfig [31.6] SETGET is non-functional (payload format unknown;
    echo-back fails with Length error). Custom profiles are not possible.
  - No AudioSettingsConfig [31.10] — uses direct CNC [1.5] SETGET instead
  - No AutoPlayPause, AutoAnswer (not applicable to earbuds)
  - No spatial audio or wind block settings
  - ModeConfig GET responses are 44 bytes (not 48)

Auth notes:
    - GET (op 1) works on all blocks without auth.
    - SETGET on Settings [1.x] works without auth.
    - START on AudioModes [31.x] and Control [7.x] works without auth.
    - SETGET on ModeConfig [31.6] is non-functional (Length error).
"""

from . import parsers

RFCOMM_CHANNEL = 8

DEVICE_INFO = {
    "name": "Bose QC Earbuds",
    "codename": "lando",
    "platform": "QCC-384",
    "product_id": 0x402F,
    "variant": 0x01,
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
    },
    "voice_prompts": {
        "addr": (1, 3),
        "parser": parsers.parse_voice_prompts,
        "builder": parsers.build_voice_prompts,
    },
    "cnc": {
        # Direct CNC SETGET on [1.5] — simpler than the QC Ultra 2's
        # [31.10] AudioSettingsConfig path. Payload: [level, enabled].
        "addr": (1, 5),
        "parser": parsers.parse_cnc,
        "builder": parsers.build_cnc,
    },
    "eq": {
        "addr": (1, 7),
        "parser": parsers.parse_eq,
        "builder": parsers.build_eq_band,
    },
    "buttons": {
        "addr": (1, 9),
        "parser": parsers.parse_buttons,
        "builder": parsers.build_buttons,
    },
    "multipoint": {
        "addr": (1, 10),
        "parser": parsers.parse_multipoint,
        "builder": parsers.build_toggle,
    },
    "sidetone": {
        "addr": (1, 11),
        "parser": parsers.parse_sidetone,
        "builder": parsers.build_sidetone,
    },
    "pairing": {
        "addr": (4, 8),
    },
    "routing": {
        "addr": (4, 12),
        "builder": parsers.build_routing,
    },
    "source": {
        "addr": (5, 1),
        "parser": parsers.parse_source,
    },
    "power": {
        "addr": (7, 4),
    },
    # AudioModes block (31) — mode switching works, profile editing does not
    "get_all_modes": {
        "addr": (31, 1),
    },
    "current_mode": {
        "addr": (31, 3),
    },
    "default_mode": {
        "addr": (31, 4),
    },
    "mode_config": {
        "addr": (31, 6),
        "parser": parsers.parse_mode_config_44,
        # No builder — SETGET on [31.6] is non-functional on this firmware
    },
    "favorites": {
        "addr": (31, 8),
    },
}

# ── Mode Configuration ───────────────────────────────────────────────────────
# Only 4 modes exist on this device (0-3). Modes 4+ return InvalidData error.
# ModeConfig SETGET is non-functional — custom profiles cannot be created.

PRESET_MODES = {
    "quiet": {"idx": 0, "description": "Quiet — full ANC"},
    "aware": {"idx": 1, "description": "Aware — transparency"},
}

MODE_BY_IDX = {0: "quiet", 1: "aware"}

EDITABLE_SLOTS = []  # No editable profile slots on this firmware

STATUS_OFFSETS = {}
