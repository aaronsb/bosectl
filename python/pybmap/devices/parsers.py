"""Shared payload parsers and builders for BMAP devices.

These functions handle common BMAP payload formats that are shared across
device generations. Device-specific formats (like ModeConfig, which has
different byte layouts per firmware) are defined in the device config's
'parsers' override dict.
"""

from ..constants import (
    PROMPTS, BUTTON_IDS, BUTTON_EVENTS, ACTION_MODES, VOICE_LANGUAGES,
    SOURCE_TYPES,
)
from ..protocol import encode_mode_name
from ..types import ModeConfig, EqBand, ButtonMapping, AudioSource


# ── Standard Parsers ─────────────────────────────────────────────────────────

def parse_battery(payload):
    """Parse battery level. Returns percentage int."""
    if payload:
        return payload[0]
    return None


def parse_firmware(payload):
    """Parse firmware version string."""
    return payload.decode("ascii", errors="replace")


def parse_product_name(payload):
    """Parse device name. First byte is a flag, name starts at byte 1."""
    return payload[1:].decode("utf-8", errors="replace")


def parse_cnc(payload):
    """Parse CNC GET response. Returns (current, max) tuple."""
    if len(payload) >= 3:
        return (payload[1], payload[0] - 1)
    return (0, 10)


def parse_eq(payload):
    """Parse EQ GET response. 4-byte groups: [min, max, current, band_id].

    Returns list of EqBand namedtuples.
    """
    band_names = {0: "Bass", 1: "Mid", 2: "Treble"}
    bands = []
    for i in range(0, len(payload), 4):
        if i + 3 >= len(payload):
            break
        min_val = payload[i]
        max_val = payload[i + 1]
        cur = payload[i + 2]
        cur_signed = cur if cur < 128 else cur - 256
        band_id = payload[i + 3]
        bands.append(EqBand(
            band_id=band_id,
            name=band_names.get(band_id, "Band%d" % band_id),
            min_val=min_val if min_val < 128 else min_val - 256,
            max_val=max_val if max_val < 128 else max_val - 256,
            current=cur_signed,
        ))
    return bands


def parse_buttons(payload):
    """Parse button config GET response. Returns ButtonMapping or None."""
    if len(payload) < 3:
        return None

    bid = payload[0]
    evt = payload[1]
    mode = payload[2]

    supported = []
    if len(payload) > 3:
        for byte_idx, b in enumerate(payload[3:7] if len(payload) >= 7 else payload[3:]):
            for bit in range(8):
                mode_id = byte_idx * 8 + bit
                if b & (1 << bit) and mode_id > 0:
                    supported.append(ACTION_MODES.get(mode_id, "unknown(%d)" % mode_id))

    return ButtonMapping(
        button_id=bid,
        button_name=BUTTON_IDS.get(bid, "0x%02x" % bid),
        event=evt,
        event_name=BUTTON_EVENTS.get(evt, str(evt)),
        action=mode,
        action_name=ACTION_MODES.get(mode, str(mode)),
        supported_actions=supported,
        raw=payload,
    )


# Reverse lookup: action name -> action ID
ACTION_BY_NAME = {v.lower(): k for k, v in ACTION_MODES.items()}


def build_buttons(button_id, event, action):
    """Build button remap SETGET payload: [buttonId, eventType, actionMode].

    Args:
        button_id: Button ID (int or name string).
        event: Event type (int or name string).
        action: Action mode (int or name string).
    """
    # Resolve button ID
    if isinstance(button_id, str):
        bid_by_name = {v.lower(): k for k, v in BUTTON_IDS.items()}
        bid = bid_by_name.get(button_id.lower())
        if bid is None:
            raise ValueError("Unknown button: %s" % button_id)
    else:
        bid = button_id

    # Resolve event type
    if isinstance(event, str):
        evt_by_name = {v.lower(): k for k, v in BUTTON_EVENTS.items()}
        evt = evt_by_name.get(event.lower())
        if evt is None:
            raise ValueError("Unknown event: %s" % event)
    else:
        evt = event

    # Resolve action mode
    if isinstance(action, str):
        act = ACTION_BY_NAME.get(action.lower())
        if act is None:
            raise ValueError("Unknown action: %s (valid: %s)"
                             % (action, ", ".join(sorted(ACTION_BY_NAME))))
    else:
        act = action

    return bytes([bid, evt, act])


def parse_multipoint(payload):
    """Parse multipoint GET. Bit 1 (0x02) = enabled."""
    if payload:
        return bool(payload[0] & 0x02)
    return False


def parse_bool(payload):
    """Parse a simple boolean GET response (byte 0)."""
    if payload:
        return bool(payload[0])
    return False


def parse_sidetone(payload):
    """Parse sidetone GET. Returns level int (byte 1)."""
    if len(payload) >= 2:
        return payload[1]
    return 0


def parse_voice_prompts(payload):
    """Parse voice prompts GET. Bit 5 = enabled, bits 4-0 = language ID.

    Returns (enabled, language_id) tuple.
    """
    if payload:
        enabled = bool((payload[0] >> 5) & 1)
        lang = payload[0] & 0x1F
        return (enabled, lang)
    return (False, 0)


ANR_NAMES = {0: "off", 1: "high", 2: "wind", 3: "low"}
ANR_VALUES = {"off": 0, "high": 1, "wind": 2, "low": 3}


def parse_anr(payload):
    """Parse ANR GET response from [1.6]. Returns level name string.

    QC35 uses ANR (Active Noise Reduction) modes instead of CNC levels.
    Payload: [anr_level, capabilities_byte].
    Values: 0=off, 1=high, 2=wind, 3=low.
    """
    if payload:
        return ANR_NAMES.get(payload[0], "unknown(%d)" % payload[0])
    return "off"


def build_anr(level_name):
    """Build ANR SETGET payload. Single byte: 0=off, 1=high, 2=wind, 3=low."""
    val = ANR_VALUES.get(level_name.lower())
    if val is None:
        raise ValueError("ANR level must be off, high, wind, or low")
    return bytes([val])


# ── Standard Builders ────────────────────────────────────────────────────────

def build_eq_band(value, band_id):
    """Build a single EQ band SETGET payload. Returns 2 bytes."""
    return bytes([value & 0xFF, band_id])


def build_toggle(enabled):
    """Build a boolean toggle SETGET payload."""
    return bytes([1 if enabled else 0])


def build_sidetone(level):
    """Build sidetone SETGET payload. [persist_flag, level]."""
    return bytes([1, level])


def build_voice_prompts(enabled, language_id):
    """Build voice prompts SETGET payload."""
    byte0 = ((1 if enabled else 0) << 5) | (language_id & 0x1F)
    return bytes([byte0])


# ── Audio Source / Routing ───────────────────────────────────────────────────

def parse_source(payload):
    """Parse AudioManagement SOURCE GET [5.1] response.

    Layout: [supported_hi, supported_lo, active_type, ...source_data]
    Source types: 0=none, 1=bluetooth (6 bytes MAC), 2=auxiliary.
    Returns AudioSource namedtuple.
    """
    if len(payload) < 3:
        return AudioSource(source_type="none", source_mac=None)
    active = payload[2]
    source_type = SOURCE_TYPES.get(active, "unknown(%d)" % active)
    mac = None
    if active == 1 and len(payload) >= 9:
        mac = ":".join("%02X" % b for b in payload[3:9])
    return AudioSource(source_type=source_type, source_mac=mac)


def build_routing(mac_str):
    """Build DeviceManagement ROUTING START [4.12] payload.

    Payload: [flags, mac0, mac1, mac2, mac3, mac4, mac5]
    flags = 0x82 (bit7=UP routing direction, bit1=device slot).
    mac_str: "XX:XX:XX:XX:XX:XX" format.
    """
    mac_bytes = bytes(int(b, 16) for b in mac_str.split(":"))
    if len(mac_bytes) != 6:
        raise ValueError("MAC must be 6 bytes (XX:XX:XX:XX:XX:XX)")
    return bytes([0x82]) + mac_bytes


# ── ModeConfig Parsers/Builders (device-specific, but share common patterns)

def parse_mode_config_48(payload):
    """Parse ModeConfig STATUS (48 bytes) — QC Ultra 2 / newer firmware.

    STATUS layout:
        [0]     modeIndex
        [1:3]   voicePrompt
        [3:6]   flags: [3]=editable, [4]=configured, [5]=unknown
        [6:38]  modeName (32 bytes)
        [38:40] unknown
        [40:42] unknown
        [42]    cncLevel
        [43]    autoCNC
        [44]    spatialAudio
        [45]    windBlock
        [46]    unknown
        [47]    ancToggle
    """
    if len(payload) < 6:
        return None

    mode_idx = payload[0]
    prompt_b1, prompt_b2 = payload[1], payload[2]
    prompt_name = PROMPTS.get((prompt_b1, prompt_b2), "(%d,%d)" % (prompt_b1, prompt_b2))

    if len(payload) >= 48:
        editable = bool(payload[3])
        configured = bool(payload[4])
        flags = "%02x %02x %02x" % (payload[3], payload[4], payload[5])
        name = payload[6:38].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        return ModeConfig(
            mode_idx=mode_idx, prompt=prompt_name,
            prompt_bytes=(prompt_b1, prompt_b2), name=name,
            cnc_level=payload[42], auto_cnc=bool(payload[43]),
            spatial=payload[44], wind_block=bool(payload[45]),
            anc_toggle=bool(payload[47]),
            editable=editable, configured=configured, flags=flags, raw=payload,
        )
    elif len(payload) >= 40:
        # SETGET echo format (no flag bytes)
        name = payload[3:35].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        return ModeConfig(
            mode_idx=mode_idx, prompt=prompt_name,
            prompt_bytes=(prompt_b1, prompt_b2), name=name,
            cnc_level=payload[35], auto_cnc=bool(payload[36]),
            spatial=payload[37], wind_block=bool(payload[38]),
            anc_toggle=bool(payload[39]),
            editable=True, configured=True, flags="", raw=payload,
        )
    else:
        name = (payload[3:35] if len(payload) >= 35 else payload[3:])
        name = name.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        return ModeConfig(
            mode_idx=mode_idx, prompt=prompt_name,
            prompt_bytes=(prompt_b1, prompt_b2), name=name,
            cnc_level=0, auto_cnc=False, spatial=0,
            wind_block=False, anc_toggle=False,
            editable=False, configured=False, flags="", raw=payload,
        )


def build_mode_config_40(mode_idx, name, cnc_level=0, auto_cnc=False,
                         spatial=0, wind_block=1, anc_toggle=1,
                         prompt_b1=0, prompt_b2=0):
    """Build 40-byte ModeConfig SETGET payload — QC Ultra 2 / newer firmware."""
    payload = bytearray()
    payload.append(mode_idx)
    payload.append(prompt_b1)
    payload.append(prompt_b2)
    payload.extend(encode_mode_name(name))
    payload.append(cnc_level)
    payload.append(1 if auto_cnc else 0)
    payload.append(spatial)
    payload.append(1 if wind_block else 0)
    payload.append(1 if anc_toggle else 0)
    return bytes(payload)
