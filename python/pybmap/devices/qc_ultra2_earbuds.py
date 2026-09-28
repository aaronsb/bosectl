"""Bose QuietComfort Ultra Earbuds (2nd Gen) device configuration.

The earbuds use the same tested BMAP feature layout as QC Ultra 2 headphones,
but report separate battery records for the left bud, right bud, and case.
"""

from .qc_ultra2 import (
    DEVICE_INFO as _HEADPHONE_INFO,
    EDITABLE_SLOTS,
    FEATURES as _HEADPHONE_FEATURES,
    MODE_BY_IDX,
    PRESET_MODES,
    RFCOMM_CHANNEL,
    STATUS_OFFSETS,
)


DEVICE_INFO = dict(_HEADPHONE_INFO)
DEVICE_INFO.update({
    "name": "Bose QuietComfort Ultra Earbuds (2nd Gen)",
    "codename": "edith",
    "product_id": 0x4062,
    "category": "earbuds",
})

# Keep the shared feature layout. Case charging is intentionally not exposed:
# BMAP [2.5] changes with earbud seating, but stayed the same across observed
# charger transitions, so it is not a reliable charging boolean.
FEATURES = dict(_HEADPHONE_FEATURES)

# Product-specific IDs: 1=right, 2=left, 3=case, 4=combined buds.
# ID 4 is the combined earbud reading and is intentionally not displayed.
BATTERY_COMPONENTS = {1: "Right", 2: "Left", 3: "Case"}
BATTERY_AGGREGATE_ID = 4
# When ID 4 is absent or 0xFF, report the lowest bud level instead.
BATTERY_AGGREGATE_SOURCES = (1, 2)
