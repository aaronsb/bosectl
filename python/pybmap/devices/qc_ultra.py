"""QuietComfort Ultra Headphones (1st Gen) configuration.

Read capabilities follow willu's macOS hardware report in bosectl issue #46.
"""

from . import parsers

RFCOMM_CHANNEL = 2
STATUS_SUPPORTED_ONLY = True
SUPPORTS_ANC_TOGGLE = False

DEVICE_INFO = {
    "name": "QuietComfort Ultra Headphones",
    "codename": "lonestarr",
    "product_id": 0x4066,
}

FEATURES = {
    "battery": {"addr": (2, 2), "parser": parsers.parse_battery},
    "firmware": {"addr": (0, 5), "parser": parsers.parse_firmware},
    "product_name": {
        "addr": (1, 2),
        "parser": parsers.parse_product_name,
        "read_only": True,
    },
    "voice_prompts": {
        "addr": (1, 3),
        "parser": parsers.parse_voice_prompts,
        "read_only": True,
    },
    "cnc": {"addr": (1, 5), "parser": parsers.parse_cnc},
    "eq": {"addr": (1, 7), "parser": parsers.parse_eq, "read_only": True},
    "multipoint": {
        "addr": (1, 10),
        "parser": parsers.parse_multipoint,
        "read_only": True,
    },
    "sidetone": {"addr": (1, 11), "parser": parsers.parse_sidetone, "read_only": True},
    "source": {"addr": (5, 1), "parser": parsers.parse_source},
    "current_mode": {"addr": (31, 3)},
}

PRESET_MODES = {}
MODE_BY_IDX = {}
EDITABLE_SLOTS = []
