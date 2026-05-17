"""Bose QC45 device configuration.

Codename "duran", product ID 0x4039, firmware 4.0.4.
RFCOMM channel 8, requires INIT_PACKET (0,1) before responding.

Capabilities verified against real hardware:
  - Battery, firmware, serial, product name: GET works
  - Device name, sidetone, voice prompts: GET + SETGET works
  - Buttons: GET + SETGET works (Shortcut button with SwitchDevice action)
  - CNC noise cancellation [1.5]: GET-only, SETGET requires auth
  - CNC via AudioModes [31.6]: SETGET works on editable modes (39-byte payload)
      Editable modes 2-3 accept cnc_level 0-10 via ModeConfig SETGET
  - Mode switching [31.3]: START works (silent or with voice prompt)
  - EQ [1.7]: GET + SETGET works (3-band: Bass/Mid/Treble, range -10 to +10)
  - Multipoint [1.10]: GET works
  - Power state [7.4]: GET works
  - Pairing mode: START works
  - No ANR [1.6], no auto-pause [1.24], no auto-answer [1.27]
  - No AudioSettings [31.10] (FuncNotSupp — use ModeConfig [31.6] instead)
"""

from . import parsers

RFCOMM_CHANNEL = 8

INIT_PACKET = (0, 1)

DEVICE_INFO = {
    "name": "Bose QuietComfort 45",
    "codename": "duran",
    "platform": "CSR8670",
    "product_id": 0x4039,
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
        "builder": lambda name: name.encode("utf-8"),
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
    "pairing": {
        "addr": (4, 8),
    },
    # AudioModes block (31) — 39-byte SETGET, 47-byte STATUS
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
        "parser": parsers.parse_mode_config_47,
        "builder": parsers.build_mode_config_39,
    },
    "favorites": {
        "addr": (31, 8),
    },
}

PRESET_MODES = {
    "quiet": {"idx": 0, "description": "Quiet — full ANC (cnc=0)"},
    "aware": {"idx": 1, "description": "Aware — transparency (cnc=10)"},
}

MODE_BY_IDX = {m["idx"]: name for name, m in PRESET_MODES.items()}

EDITABLE_SLOTS = [2, 3]

STATUS_OFFSETS = {
    "prompt_b1": 1,
    "prompt_b2": 2,
    "editable": 3,
    "configured": 4,
    "cnc_level": 42,
    "auto_cnc": 43,
    "spatial": 44,
    "wind_block": 45,
}
