"""BMAP protocol constants shared across all devices."""

# Operators — each BMAP packet carries one of these.
OP_SET = 0         # Write a value (auth required on most blocks)
OP_GET = 1         # Read a value (no auth)
OP_SETGET = 2      # Write + read back (no auth on many blocks)
OP_STATUS = 3      # Unsolicited state notification from device
OP_ERROR = 4       # Error response
OP_START = 5       # Trigger an action
OP_RESULT = 6      # Action completed successfully
OP_PROCESSING = 7  # Async operation in progress

OP_NAMES = {
    0: "SET", 1: "GET", 2: "SETGET", 3: "STATUS", 4: "ERROR",
    5: "START", 6: "RESULT", 7: "PROCESSING",
}

# Error codes returned in ERROR (op 4) responses.
ERROR_NAMES = {
    0: "Unknown", 1: "Length", 2: "Chksum", 3: "FblockNotSupp",
    4: "FuncNotSupp", 5: "OpNotSupp(auth)", 6: "InvalidData",
    7: "DataUnavail", 8: "Runtime", 9: "Timeout", 10: "InvalidState",
    15: "InvalidTransition",
    20: "InsecureTransport",
}

# Voice prompt identifiers — (byte1, byte2) -> name.
PROMPTS = {
    (0, 0): "NONE", (0, 1): "QUIET", (0, 2): "AWARE", (0, 3): "TRANSPARENT",
    (0, 4): "TRANSPARENCY", (0, 5): "MASKING", (0, 6): "COMFORT",
    (0, 7): "COMMUTE", (0, 8): "OUTDOOR", (0, 9): "WORKOUT", (0, 10): "HOME",
    (0, 11): "WORK", (0, 12): "MUSIC", (0, 13): "FOCUS", (0, 14): "RELAX",
    (0, 15): "FLIGHT", (0, 16): "AIRPORT", (0, 17): "DRIVING",
    (0, 18): "TRAINING", (0, 19): "GYM", (0, 20): "RUN", (0, 21): "WALK",
    (0, 22): "HIKE", (0, 23): "TALK", (0, 24): "CALL", (0, 25): "WHISPER",
    (0, 26): "HEARING", (0, 27): "LEARN", (0, 28): "PODCAST",
    (0, 29): "AUDIOBOOK", (0, 30): "CALM", (0, 31): "SLEEP",
    (0, 32): "MEDITATE", (0, 33): "YOGA", (0, 34): "IMMERSION",
    (0, 35): "STEREO", (0, 36): "CINEMA",
}

PROMPT_BY_NAME = {v.lower(): k for k, v in PROMPTS.items()}

# Spatial audio modes.
SPATIAL_NAMES = {0: "off", 1: "room", 2: "head"}
SPATIAL_VALUES = {"off": 0, "room": 1, "head": 2}

# Sidetone levels.
SIDETONE_NAMES = {0: "off", 1: "high", 2: "medium", 3: "low"}
SIDETONE_VALUES = {"off": 0, "high": 1, "medium": 2, "med": 2, "low": 3}

# Voice prompt languages.
VOICE_LANGUAGES = {
    0: "UK English", 1: "US English", 2: "French", 3: "Italian", 4: "German",
    5: "EU Spanish", 6: "MX Spanish", 7: "BR Portuguese", 8: "Mandarin",
    9: "Korean", 10: "Russian", 11: "Polish", 12: "Hebrew", 13: "Turkish",
    14: "Dutch", 15: "Japanese", 16: "Cantonese", 17: "Arabic", 18: "Swedish",
    19: "Danish", 20: "Norwegian", 21: "Finnish", 22: "Hindi",
}

# Button identifiers.
BUTTON_IDS = {
    0: "DistalCnc", 1: "Reserved", 2: "Vpa", 3: "RightShortcut",
    4: "LeftShortcut", 16: "Action", 128: "Shortcut",
}

# Button event types.
BUTTON_EVENTS = {
    0: "reserved", 1: "rising_edge", 2: "falling_edge", 3: "short_press",
    4: "single_press", 5: "press_and_hold", 6: "double_press",
    7: "double_press_hold", 8: "triple_press", 9: "long_press",
    10: "very_long_press", 11: "very_very_long_press",
    12: "very_very_very_long_press",
}

# Button action modes.
ACTION_MODES = {
    0: "NotConfigured", 1: "VPA", 2: "ANC", 3: "BatteryLevel",
    4: "PlayPause", 5: "IncreaseCNC", 6: "DecreaseCNC", 7: "ToggleWakeWord",
    8: "SwitchDevice", 9: "ConversationMode", 10: "TrackForward",
    11: "TrackBack", 12: "FetchNotifications", 13: "WindMode", 14: "Disabled",
    15: "ClientInteraction", 16: "SpotifyGo", 17: "ModesCarousel",
    19: "SpatialAudioMode", 20: "LineInSwitch", 21: "Linking",
}
