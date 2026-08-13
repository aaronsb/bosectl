"""Bose QuietComfort Headphones device configuration.

Codename "prince", product ID 0x4075.
Firmware tested: 1.0.6-80+f5f219b.

Empirically derived on real hardware, not from a protocol capture. The
device answers BMAP on RFCOMM channel 9 (not 2, which the QC Ultra 2 and
QC35 use), and it shares the QC Ultra 2 payload layouts for everything
verified below.

Verified working (GET):
    battery, firmware, product_name, voice_prompts, sidetone, multipoint,
    auto_pause, auto_answer, eq, source, buttons, current_mode

Verified working (SETGET):
    eq — set_eq(2, 0, -1) applied and read back correctly.

Rejected by firmware with FuncNotSupp (04):
    cnc  [31.10] — CNC slider is QC Ultra 2 only
    anr  [1.6]   — ANR mode is QC35 only

`cnc` is therefore omitted from FEATURES so bosectl reports it as an
unsupported feature rather than surfacing a raw device error.
"""

from . import qc_ultra2

RFCOMM_CHANNEL = 9

# ── Device Identity ──────────────────────────────────────────────────────────

DEVICE_INFO = {
    "name": "Bose QuietComfort Headphones",
    "codename": "prince",
    "platform": "OTG-QCC-384",
    "product_id": 0x4075,
    "variant": 0x01,
}

# ── Feature Map ──────────────────────────────────────────────────────────────
# Same payload layouts as the QC Ultra 2, minus the features this firmware
# rejects. Inherited by copy so upstream edits to qc_ultra2 carry over.

FEATURES = {k: v for k, v in qc_ultra2.FEATURES.items() if k != "cnc"}

PRESET_MODES = qc_ultra2.PRESET_MODES
MODE_BY_IDX = qc_ultra2.MODE_BY_IDX
EDITABLE_SLOTS = qc_ultra2.EDITABLE_SLOTS
STATUS_OFFSETS = qc_ultra2.STATUS_OFFSETS
