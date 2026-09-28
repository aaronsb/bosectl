"""Bose QuietComfort Headphones (2nd Gen) device configuration.

Product ID 0x4083. Internal codename unknown at time of writing.
Verified against real hardware on firmware 8.3.0+g755f93d, BMAP 1.2.0.
MAC prefix 68:F2:1F (same family as QC Ultra 2 / wolverine).

BMAP is exposed over the vendor-specific UUID
00000000-deca-fade-deca-deafdecacaff and resolves to RFCOMM channel 2,
matching the QC Ultra 2 (wolverine, 0x4082) rather than the QC
Headphones 1st gen (prince, 0x4075) which uses channel 8.

The AudioModes block uses the same 48-byte STATUS / 40-byte SETGET
ModeConfig layout as wolverine. ANC mode switching via START [31.3]
is confirmed unauthenticated. Preset modes 0 (Quiet), 1 (Aware), and
2 (Immersion) are verified on hardware. Mode 3 (Cinema) exists in the
wolverine layout but has not been tested on this device.

Verified features:
    battery           [2.2]  GET → percentage byte
    firmware          [0.5]  GET → version string
    current_mode      [31.3] GET → mode index; START → switch mode
    audio_settings    [31.10] GET/SETGET → CNC, spatial, wind, ANC

Features inherited from the wolverine layout but not yet tested on
this hardware (marked with # unverified):
    eq, multipoint, sidetone, auto_pause, auto_answer, buttons,
    mode_config SETGET on custom slots (indices 4+)

Auth notes (same as wolverine):
    GET (op 1)    — works on all blocks without auth
    SETGET (op 2) — works on Settings [1.x] and AudioModes [31.x]
    START (op 5)  — works on AudioModes [31.x]
    SET (op 0)    — requires cloud-mediated ECDH auth
"""

from . import parsers

RFCOMM_CHANNEL = 2

# ── Device Identity ──────────────────────────────────────────────────────────

DEVICE_INFO = {
    "name": "Bose QuietComfort Headphones (2nd Gen)",
    "codename": "unknown",  # internal Bose codename not yet identified
    "platform": "Unknown",
    "product_id": 0x4083,
    "variant": 0x00,
    "bmap_version": "1.2.0",
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
    "voice_prompts": {  # unverified
        "addr": (1, 3),
        "parser": parsers.parse_voice_prompts,
        "builder": parsers.build_voice_prompts,
    },
    "cnc": {  # unverified — [31.10] audio_settings confirmed instead
        "addr": (1, 5),
        "parser": parsers.parse_cnc,
    },
    "eq": {  # unverified
        "addr": (1, 7),
        "parser": parsers.parse_eq,
        "builder": parsers.build_eq_band,
    },
    "buttons": {  # unverified
        "addr": (1, 9),
        "parser": parsers.parse_buttons,
        "builder": parsers.build_buttons,
    },
    "multipoint": {  # unverified
        "addr": (1, 10),
        "parser": parsers.parse_multipoint,
        "builder": parsers.build_toggle,
    },
    "sidetone": {  # unverified
        "addr": (1, 11),
        "parser": parsers.parse_sidetone,
        "builder": parsers.build_sidetone,
    },
    "auto_pause": {  # unverified
        "addr": (1, 24),
        "parser": parsers.parse_bool,
        "builder": parsers.build_toggle,
    },
    "auto_answer": {  # unverified
        "addr": (1, 27),
        "parser": parsers.parse_bool,
        "builder": parsers.build_toggle,
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
        "parser": parsers.parse_mode_config_48,
        "builder": parsers.build_mode_config_40,
    },
    "audio_settings": {
        "addr": (31, 10),
        "parser": parsers.parse_audio_settings,
        "builder": parsers.build_audio_settings,
    },
}

# ── Mode Configuration ───────────────────────────────────────────────────────

PRESET_MODES = {
    "quiet":     {"idx": 0, "description": "Quiet — full ANC"},
    "aware":     {"idx": 1, "description": "Aware — transparency"},
    "immersion": {"idx": 2, "description": "Immersion — spatial audio"},
    # Cinema (idx 3) exists in the wolverine layout but is unverified on this device.
}

MODE_BY_IDX = {m["idx"]: name for name, m in PRESET_MODES.items()}

EDITABLE_SLOTS = list(range(4, 11))  # unverified; assumed same as wolverine

# ── ModeConfig STATUS Field Offsets ──────────────────────────────────────────
# 48-byte STATUS layout, matching wolverine.

STATUS_OFFSETS = {
    "prompt_b1": 1,
    "prompt_b2": 2,
    "editable":  3,
    "configured": 4,
    "cnc_level": 42,
    "auto_cnc":  43,
    "spatial":   44,
    "wind_block": 45,
    "anc_toggle": 47,
}
