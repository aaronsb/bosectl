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
from ..constants import PROMPTS
from ..types import ModeConfig

RFCOMM_CHANNEL = 9


def parse_mode_config_47(payload):
    """Parse ModeConfig STATUS (47 bytes) — QuietComfort Headphones.

    One byte shorter than the QC Ultra 2's 48-byte STATUS, which matters:
    parse_mode_config_48 falls through to its 40-byte SETGET-echo branch and
    reads the name from offset 3 instead of 6, yielding "\\x01\\x01\\x01Focus"
    and breaking `switch <name>`.

    The header and name sit at the same offsets as the 48-byte layout:

        [0]     modeIndex
        [1:3]   voicePrompt
        [3:6]   flags: [3]=editable, [4]=configured, [5]=unknown
        [6:38]  modeName (32 bytes)
        [42]    cncLevel — 0 for Quiet, 10 for Aware, matching the 48-byte
                layout. Reported for completeness; this device rejects CNC
                writes with FuncNotSupp, so it is not actionable.

    The remaining tail bytes are left undecoded. Only four slots were
    available to compare, and they disagree about where the trailing fields
    sit (the stock profiles carry a 0x09 at [41] that the presets do not),
    so guessing offsets here would invent values. spatial is reported as 0
    because this device has no spatial audio at all.
    """
    if len(payload) < 6:
        return None

    prompt_b1, prompt_b2 = payload[1], payload[2]
    return ModeConfig(
        mode_idx=payload[0],
        prompt=PROMPTS.get((prompt_b1, prompt_b2), "(%d,%d)" % (prompt_b1, prompt_b2)),
        prompt_bytes=(prompt_b1, prompt_b2),
        name=payload[6:38].split(b"\x00", 1)[0].decode("utf-8", errors="replace"),
        cnc_level=payload[42] if len(payload) > 42 else 0,
        auto_cnc=False,
        spatial=0,
        wind_block=False,
        anc_toggle=False,
        editable=bool(payload[3]),
        configured=bool(payload[4]),
        flags="%02x %02x %02x" % (payload[3], payload[4], payload[5]),
        raw=payload,
    )

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

FEATURES["mode_config"] = dict(FEATURES["mode_config"], parser=parse_mode_config_47)

# ── Modes ────────────────────────────────────────────────────────────────────
# Only slots 0 and 1 are fixed presets. The QC Ultra 2's "immersion" and
# "cinema" are spatial-audio modes this device does not have — slots 2 and 3
# are ordinary user profiles (named "Focus" and "Walk" out of the box) and
# are reached by name via `switch`, not by a preset alias.

PRESET_MODES = {
    "quiet": qc_ultra2.PRESET_MODES["quiet"],
    "aware": qc_ultra2.PRESET_MODES["aware"],
}

MODE_BY_IDX = {m["idx"]: name for name, m in PRESET_MODES.items()}
EDITABLE_SLOTS = qc_ultra2.EDITABLE_SLOTS
STATUS_OFFSETS = qc_ultra2.STATUS_OFFSETS
