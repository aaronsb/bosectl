"""Bose QC Ultra 2 device configuration.

Codename "wolverine", Qualcomm QCC-384 platform.
Firmware tested: 8.2.20+g34cf029.

This module is a pure configuration — no logic, just data. All parsing
and building is handled by shared functions in devices.parsers. If a
future device needs different payload layouts, it overrides the parser
key in its feature dict.

Auth notes:
    - GET (op 1) works on all blocks without auth.
    - SETGET (op 2) works on Settings [1.x] and AudioModes [31.x] without auth.
    - START (op 5) works on AudioModes [31.x] without auth.
    - SET (op 0) requires cloud-mediated ECDH auth on all blocks.
    - Preset modes (0-3) reject SETGET with Runtime error (firmware lock).
"""

from . import parsers

RFCOMM_CHANNEL = 2

# ── Device Identity ──────────────────────────────────────────────────────────

DEVICE_INFO = {
    "name": "Bose QC Ultra Headphones 2",
    "codename": "wolverine",
    "platform": "OTG-QCC-384",
    "product_id": 0x4082,
    "variant": 0x01,
}

# ── Feature Map ──────────────────────────────────────────────────────────────
# Each feature maps to its (fblock, func) address and the parser/builder
# functions to use. Connection.py looks up features by key name.
#
# Keys:
#   addr:    (fblock_id, function_id)
#   parser:  function(payload) -> parsed value
#   builder: function(**kwargs) -> payload bytes (for write operations)

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
        "addr": (1, 5),
        "parser": parsers.parse_cnc,
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
    "auto_pause": {
        "addr": (1, 24),
        "parser": parsers.parse_bool,
        "builder": parsers.build_toggle,
    },
    "auto_answer": {
        "addr": (1, 27),
        "parser": parsers.parse_bool,
        "builder": parsers.build_toggle,
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
    # AudioModes block (31)
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
        "parser": parsers.parse_mode_config_48,
        "builder": parsers.build_mode_config_40,
    },
    "favorites": {
        "addr": (31, 8),
    },
}

# ── Mode Configuration ───────────────────────────────────────────────────────

PRESET_MODES = {
    "quiet":     {"idx": 0, "description": "Quiet — full ANC"},
    "aware":     {"idx": 1, "description": "Aware — transparency"},
    "immersion": {"idx": 2, "description": "Immersion — spatial audio, head tracking"},
    "cinema":    {"idx": 3, "description": "Cinema — spatial audio, fixed stage"},
}

MODE_BY_IDX = {m["idx"]: name for name, m in PRESET_MODES.items()}

EDITABLE_SLOTS = list(range(4, 11))

# ── ModeConfig STATUS Field Offsets ──────────────────────────────────────────
# These are used by connection.py to read specific fields from raw STATUS
# payloads when modifying a profile in-place (without a full re-parse).

STATUS_OFFSETS = {
    "prompt_b1": 1,
    "prompt_b2": 2,
    "editable": 3,
    "configured": 4,
    "cnc_level": 42,
    "auto_cnc": 43,
    "spatial": 44,
    "wind_block": 45,
    "anc_toggle": 47,
}
