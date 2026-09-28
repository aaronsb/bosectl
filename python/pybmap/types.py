"""Data types for parsed BMAP responses."""

from collections import namedtuple

# A parsed BMAP response packet.
BmapResponse = namedtuple("BmapResponse", ["fblock", "func", "op", "payload"])

# Parsed mode configuration from a ModeConfig STATUS response.
ModeConfig = namedtuple("ModeConfig", [
    "mode_idx",     # Slot index (0-10)
    "prompt",       # Voice prompt name string
    "prompt_bytes", # Raw prompt bytes (b1, b2)
    "name",         # Mode name (UTF-8 string)
    "cnc_level",    # Noise cancellation level (0-10)
    "auto_cnc",     # Auto CNC adjustment (bool)
    "spatial",      # Spatial audio: 0=off, 1=room, 2=head
    "wind_block",   # Wind noise reduction (bool)
    "anc_toggle",   # ANC toggle enable (bool)
    "editable",     # Whether this slot can be modified
    "configured",   # Whether this slot has a config
    "flags",        # Raw flag bytes (hex string)
    "raw",          # Raw payload bytes
])

# A single EQ band reading.
EqBand = namedtuple("EqBand", ["band_id", "name", "min_val", "max_val", "current"])

# A single component battery reading from a multi-battery device.
BatteryReading = namedtuple("BatteryReading", ["component_id", "level"])

# Aggregate and component readings parsed from one battery response.
BatteryStatus = namedtuple("BatteryStatus", ["aggregate", "readings"])

# Complete device status snapshot.
DeviceStatus = namedtuple("DeviceStatus", [
    "battery",
    "mode",
    "mode_idx",
    "cnc_level",
    "cnc_max",
    "eq",               # List of EqBand
    "name",
    "firmware",
    "sidetone",
    "multipoint",
    "auto_pause",
    "auto_answer",
    "prompts_enabled",
    "prompts_language",
    "battery_readings",  # List of BatteryReading from the same response
])
# Preserve positional construction of the pre-snapshot status shape.
DeviceStatus.__new__.__defaults__ = ((),)

# Current audio settings (CNC, spatial, wind, ANC) from [31.10].
AudioSettings = namedtuple("AudioSettings", [
    "cnc_level",    # 0-10
    "auto_cnc",     # bool
    "spatial",      # 0=off, 1=room, 2=head
    "wind_block",   # bool
    "anc_toggle",   # bool
])

# Audio source information.
AudioSource = namedtuple("AudioSource", [
    "source_type",  # "none", "bluetooth", or "auxiliary"
    "source_mac",   # MAC string if bluetooth, else None
])

# Button mapping entry.
ButtonMapping = namedtuple("ButtonMapping", [
    "button_id",
    "button_name",
    "event",
    "event_name",
    "action",
    "action_name",
    "supported_actions",
    "raw",
])
