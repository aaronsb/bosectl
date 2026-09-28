"""Bose QuietComfort Headphones device configuration.

Codename "prince", product ID 0x4075.
Verified against real hardware on firmware 1.0.6-80+f5f219b.

BMAP is exposed over the standard SPP UUID and resolves to RFCOMM channel 8.
The AudioModes block is close to QC Ultra 2 but uses a shorter ModeConfig
layout: 47-byte STATUS responses and 39-byte SETGET payloads. The final
ancToggle byte present on newer 48/40-byte layouts is not supported here.
"""

from . import parsers

RFCOMM_CHANNEL = 8
SUPPORTS_ANC_TOGGLE = False

# ── Device Identity ──────────────────────────────────────────────────────────

DEVICE_INFO = {
    "name": "Bose QuietComfort Headphones",
    "codename": "prince",
    "platform": "Unknown",
    "product_id": 0x4075,
    "variant": 0x00,
}

# ── Feature Map ──────────────────────────────────────────────────────────────

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
    # 3-band EQ. Same Settings-block register as qc45/qc_ultra2/qc_earbuds;
    # verified working on prince firmware 1.0.6-80+f5f219b (range -10..+10).
    "eq": {
        "addr": (1, 7),
        "parser": parsers.parse_eq,
        "builder": parsers.build_eq_band,
    },
    "pairing": {
        "addr": (4, 8),
    },
    # AudioModes block (31)
    "get_all_modes": {
        "addr": (31, 1),
    },
    "current_mode": {
        "addr": (31, 3),
    },
    "mode_config": {
        "addr": (31, 6),
        "parser": parsers.parse_mode_config_47,
        "builder": parsers.build_mode_config_39,
    },
}

# ── Mode Configuration ───────────────────────────────────────────────────────

# The first two slots are built-in presets. Later slots are user-named modes
# on the paired device; do not assume their names are universal.
PRESET_MODES = {
    "quiet": {"idx": 0, "description": "Quiet - full ANC"},
    "aware": {"idx": 1, "description": "Aware - transparency"},
}

MODE_BY_IDX = {m["idx"]: name for name, m in PRESET_MODES.items()}

# Observed configured editable slots on the tested unit. Other firmware may
# expose different user mode names, but the 47/39-byte payload layout is the
# important protocol difference.
EDITABLE_SLOTS = [2, 3]

STATUS_OFFSETS = {
    "prompt_b1": 1,
    "prompt_b2": 2,
    "editable": 3,
    "configured": 4,
    "cnc_level": 42,
    "auto_cnc": 43,
    "spatial": 44,
    "wind_block": 46,
}
