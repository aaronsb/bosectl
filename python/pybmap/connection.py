"""High-level BMAP device connection.

BmapConnection is the primary public API. It composes a transport with
a device configuration to provide typed read/write methods for all
supported features.

Usage:
    import pybmap
    with pybmap.connect() as dev:
        print(dev.battery())
        dev.set_cnc(8)
"""

from .constants import (
    OP_GET, OP_SETGET, OP_START, OP_STATUS, OP_RESULT, OP_ERROR,
    OP_PROCESSING, SIDETONE_NAMES, SIDETONE_VALUES, SPATIAL_VALUES,
    VOICE_LANGUAGES,
)
from .protocol import bmap_packet, parse_response, parse_all_responses, fmt_response
from .errors import BmapError, BmapAuthError, BmapDeviceError, BmapDesyncError
from .types import DeviceStatus, AudioSettings


# The device name field is 32 bytes on every BMAP device seen so far.
MAX_NAME_BYTES = 31


class BmapConnection:
    """High-level connection to a BMAP device.

    All feature methods look up addresses and parsers from the device
    config, so the same connection class works for any supported device.
    Methods for unsupported features raise BmapError.
    """

    def __init__(self, transport, device):
        """
        Args:
            transport: A connected RfcommTransport instance.
            device: A device config module (e.g., pybmap.devices.qc_ultra2).
        """
        self._transport = transport
        self._device = device

    def _feature(self, name):
        """Look up a feature config entry. Raises BmapError if unsupported."""
        features = self._device.FEATURES
        if name not in features:
            raise BmapError(
                "%s does not support '%s'" % (
                    self._device.DEVICE_INFO.get("name", "Device"), name
                )
            )
        return features[name]

    def _check_address(self, parsed, fblock, func):
        """Reject a response that came from a different address.

        The firmware answers in order, so after a reconnect the socket can
        still hold responses queued before the drop and every read returns
        the previous request's answer. Without this check the payload is
        handed to the wrong parser and surfaces as plausible-looking data.
        """
        if parsed is None:
            return None
        if (parsed.fblock, parsed.func) != (fblock, func):
            raise BmapDesyncError(
                "Response came from [%d.%d], expected [%d.%d]. "
                "Reopen the connection."
                % (parsed.fblock, parsed.func, fblock, func)
            )
        return parsed

    def _get(self, feature_name):
        """Send a GET request and return the parsed payload."""
        feat = self._feature(feature_name)
        fblock, func = feat["addr"]
        resp = self._transport.send_recv(bmap_packet(fblock, func, OP_GET))
        parsed = self._check_address(parse_response(resp), fblock, func)
        if parsed is None:
            return None
        if parsed.op == OP_ERROR:
            self._raise_error(parsed)
        parser = feat.get("parser")
        if parser:
            return parser(parsed.payload)
        return parsed.payload

    def _setget(self, feature_name, payload):
        """Send a SETGET request and return the parsed response."""
        feat = self._feature(feature_name)
        fblock, func = feat["addr"]
        resp = self._transport.send_recv(
            bmap_packet(fblock, func, OP_SETGET, payload)
        )
        parsed = self._check_address(parse_response(resp), fblock, func)
        if parsed and parsed.op == OP_ERROR:
            self._raise_error(parsed)
        return parsed

    def _start(self, feature_name, payload=b""):
        """Send a START request and return the parsed response."""
        feat = self._feature(feature_name)
        fblock, func = feat["addr"]
        resp = self._transport.send_recv(
            bmap_packet(fblock, func, OP_START, payload)
        )
        parsed = self._check_address(parse_response(resp), fblock, func)
        if parsed and parsed.op == OP_ERROR:
            self._raise_error(parsed)
        return parsed

    def _start_drain(self, feature_name, payload=b""):
        """Send a START request and drain all responses."""
        feat = self._feature(feature_name)
        fblock, func = feat["addr"]
        data = self._transport.send_recv(
            bmap_packet(fblock, func, OP_START, payload), drain=True
        )
        return parse_all_responses(data)

    def _safe_read(self, method, default):
        """Call a read method, returning default on BmapError."""
        try:
            return method()
        except BmapError:
            return default

    def _raise_error(self, parsed):
        """Raise the appropriate exception for an ERROR response."""
        from .constants import ERROR_NAMES
        if parsed.payload:
            code = parsed.payload[0]
            name = ERROR_NAMES.get(code, "error %d" % code)
            if code == 5:
                raise BmapAuthError("Authentication required: %s" % fmt_response(parsed))
            raise BmapDeviceError(
                "%s: %s" % (name, fmt_response(parsed)),
                error_code=code,
            )
        raise BmapDeviceError(fmt_response(parsed))

    # ── Read Operations ──────────────────────────────────────────────────────

    def battery(self):
        """Battery percentage (int)."""
        return self._get("battery")

    def firmware(self):
        """Firmware version string."""
        return self._get("firmware")

    def name(self):
        """Device Bluetooth name."""
        return self._get("product_name")

    def mode(self):
        """Current audio mode name (str).

        Returns preset name for known indices, or custom profile name.
        """
        idx = self.mode_idx()
        if idx is None:
            return None
        return self._mode_name_from_idx(idx)

    def mode_idx(self):
        """Current audio mode index (int)."""
        feat = self._feature("current_mode")
        fblock, func = feat["addr"]
        resp = self._transport.send_recv(bmap_packet(fblock, func, OP_GET))
        parsed = self._check_address(parse_response(resp), fblock, func)
        if parsed and parsed.payload:
            return parsed.payload[0]
        return None

    def _mode_name_from_idx(self, idx):
        """Resolve a mode index to a name without an extra GET."""
        by_idx = self._device.MODE_BY_IDX
        if idx in by_idx:
            return by_idx[idx]
        # Custom profile — need to fetch modes (one drain, not a GET)
        try:
            modes = self.modes()
            if idx in modes:
                return modes[idx].name
        except BmapError:
            pass
        return "unknown(%d)" % idx

    def cnc(self):
        """Noise cancellation (current, max) tuple."""
        return self._get("cnc")

    def eq(self):
        """EQ bands (list of EqBand)."""
        return self._get("eq")

    def sidetone(self):
        """Sidetone level name (str)."""
        raw = self._get("sidetone")
        return SIDETONE_NAMES.get(raw, "unknown(%s)" % raw)

    def multipoint(self):
        """Multipoint enabled (bool)."""
        return self._get("multipoint")

    def auto_pause(self):
        """Auto play/pause enabled (bool)."""
        return self._get("auto_pause")

    def auto_answer(self):
        """Auto-answer calls enabled (bool)."""
        return self._get("auto_answer")

    def source(self):
        """Active audio source. Returns AudioSource namedtuple.

        Queries AudioManagement [5.1] for the current source type
        (none, bluetooth, auxiliary) and associated data.
        """
        return self._get("source")

    def anr(self):
        """Active Noise Reduction mode (str: off/high/wind/low).

        Used by QC35 instead of CNC. Returns the current ANR level name.
        """
        return self._get("anr")

    def audio_settings(self):
        """Current audio settings as AudioSettings.

        Newer devices expose this directly at [31.10]. Devices such as
        QuietComfort Headphones/prince expose the same live CNC/wind fields
        through the current editable ModeConfig instead.
        """
        if self.has_feature("audio_settings"):
            return self._get("audio_settings")

        config = self._current_mode_config()
        return AudioSettings(
            cnc_level=config.cnc_level,
            auto_cnc=config.auto_cnc,
            spatial=config.spatial,
            wind_block=config.wind_block,
            anc_toggle=config.anc_toggle,
        )

    def prompts(self):
        """Voice prompts (enabled, language_name) tuple."""
        enabled, lang_id = self._get("voice_prompts")
        return (enabled, VOICE_LANGUAGES.get(lang_id, "lang%d" % lang_id))

    def buttons(self):
        """Button mapping (ButtonMapping namedtuple)."""
        return self._get("buttons")

    def modes(self):
        """All mode configurations. Returns dict of idx -> ModeConfig."""
        responses = self._start_drain("get_all_modes")
        mode_config_addr = self._feature("mode_config")["addr"]
        parser = self._feature("mode_config").get("parser")
        modes = {}
        for resp in responses:
            if (resp.fblock == mode_config_addr[0] and
                    resp.func == mode_config_addr[1] and
                    resp.op == OP_STATUS and resp.payload and
                    len(resp.payload) >= 6):
                config = parser(resp.payload) if parser else resp.payload
                if config is not None:
                    modes[config.mode_idx] = config
        return modes

    def status(self):
        """Full device status snapshot. Returns DeviceStatus namedtuple."""
        # Single GET for mode index, derive name without extra round trip.
        current_idx = self._safe_read(self.mode_idx, None)
        current_name = self._mode_name_from_idx(current_idx) if current_idx is not None else ""
        cnc_cur, cnc_max = self._safe_read(self.cnc, (0, 10))
        prompts_on, prompts_lang = self._safe_read(self.prompts, (False, ""))

        return DeviceStatus(
            battery=self.battery(),
            mode=current_name,
            mode_idx=current_idx,
            cnc_level=cnc_cur, cnc_max=cnc_max,
            eq=self._safe_read(self.eq, []),
            name=self._safe_read(self.name, ""),
            firmware=self._safe_read(self.firmware, ""),
            sidetone=self._safe_read(self.sidetone, "off"),
            multipoint=self._safe_read(self.multipoint, False),
            auto_pause=self._safe_read(self.auto_pause, False),
            auto_answer=self._safe_read(self.auto_answer, False),
            prompts_enabled=prompts_on, prompts_language=prompts_lang,
        )

    # ── Write Operations ─────────────────────────────────────────────────────

    def set_mode(self, name, announce=False):
        """Switch to a mode by name (preset or custom profile).

        Args:
            name: Mode name (e.g. "quiet", "aware", or a custom profile name).
            announce: If True, play voice prompt when switching.
        """
        preset = self._device.PRESET_MODES
        name_lower = name.lower()
        if name_lower in preset:
            idx = preset[name_lower]["idx"]
        else:
            modes = self.modes()
            found = None
            for mode_idx, config in modes.items():
                if config.name.lower() == name_lower:
                    found = mode_idx
                    break
            if found is None:
                raise BmapError("Unknown mode: %s" % name)
            idx = found

        resp = self._start("current_mode", bytes([idx, 1 if announce else 0]))
        # Some firmware (QC Headphones "prince") acks START [31.3] with
        # PROCESSING and applies the switch asynchronously.
        if resp and resp.op not in (OP_RESULT, OP_PROCESSING):
            raise BmapDeviceError("Mode switch failed: %s" % fmt_response(resp))

    def set_cnc(self, level):
        """Set noise cancellation level (0-10).

        Scale is inverted: 0 = maximum ANC (blocks most outside sounds),
        10 = most ambient pass-through. The effect is only audible when
        anc_toggle=on AND wind_block=off — wind block masks CNC changes.

        Uses direct [1.5] SETGET on devices without AudioSettingsConfig
        (QC Earbuds), or [31.10] AudioSettingsConfig on newer devices.
        """
        if not 0 <= level <= 10:
            raise ValueError("CNC level must be 0-10, got %d" % level)
        # QC Earbuds (and similar): use direct [1.5] CNC SETGET when available
        feat = self._feature("cnc")
        if feat.get("builder") and not self.has_feature("audio_settings"):
            self._setget("cnc", feat["builder"](level))
        else:
            self._update_audio_settings(cnc_level=level)

    def set_anc(self, enabled):
        """Toggle Active Noise Cancellation on/off (bool)."""
        self._update_audio_settings(anc_toggle=bool(enabled))

    def set_wind(self, enabled):
        """Toggle Wind Block on/off (bool)."""
        self._update_audio_settings(wind_block=bool(enabled))

    def set_anr(self, level):
        """Set Active Noise Reduction mode (off/high/wind/low).

        Used by QC35 instead of set_cnc().
        """
        feat = self._feature("anr")
        builder = feat.get("builder")
        self._setget("anr", builder(level))

    def set_eq(self, bass=0, mid=0, treble=0):
        """Set 3-band equalizer (-10 to +10 each)."""
        feat = self._feature("eq")
        builder = feat.get("builder")
        for band_id, val in enumerate([bass, mid, treble]):
            if not -10 <= val <= 10:
                raise ValueError("EQ value must be -10 to +10")
            payload = builder(val, band_id) if builder else bytes([val & 0xFF, band_id])
            self._setget("eq", payload)

    def set_spatial(self, mode):
        """Set spatial audio mode ("off", "room", or "head")."""
        if mode not in SPATIAL_VALUES:
            raise ValueError("Spatial mode must be off, room, or head")
        self._update_audio_settings(spatial=SPATIAL_VALUES[mode])

    def _update_audio_settings(self, **overrides):
        """Read current audio settings and write back with overrides.

        Uses AudioModesSettingsConfig [31.10] SETGET — the same register
        the Bose app writes to. Unauthenticated on QC Ultra 2+.
        """
        if not self.has_feature("audio_settings"):
            return self._update_current_mode_config(**overrides)
        settings = self._get("audio_settings")
        feat = self._feature("audio_settings")
        builder = feat["builder"]
        self._setget("audio_settings", builder(
            cnc_level=overrides.get("cnc_level", settings.cnc_level),
            spatial=overrides.get("spatial", settings.spatial),
            wind_block=overrides.get("wind_block", settings.wind_block),
            anc_toggle=overrides.get("anc_toggle", settings.anc_toggle),
        ))

    def _update_current_mode_config(self, **overrides):
        """Fallback live audio update through the current ModeConfig."""
        if not self.has_feature("mode_config"):
            raise BmapError("Device does not support direct audio settings")

        if ("anc_toggle" in overrides and
                not getattr(self._device, "SUPPORTS_ANC_TOGGLE", True)):
            raise BmapError("Device does not expose an ANC on/off toggle")

        config = self._current_mode_config()
        if not config.editable:
            raise BmapError(
                "Current mode '%s' is not editable on this device" % config.name
            )
        self._write_mode_from_config(config.mode_idx, config, **overrides)

    def set_name(self, new_name):
        """Set device Bluetooth name (UTF-8, at most MAX_NAME_BYTES bytes)."""
        data = new_name.encode("utf-8")
        if len(data) > MAX_NAME_BYTES:
            raise ValueError(
                "Name must be at most %d bytes of UTF-8" % MAX_NAME_BYTES)
        self._setget("product_name", data)

    def set_sidetone(self, level):
        """Set sidetone level ("off", "low", "medium", or "high")."""
        level_lower = level.lower()
        if level_lower not in SIDETONE_VALUES:
            raise ValueError("Sidetone must be off, low, medium, or high")
        feat = self._feature("sidetone")
        builder = feat.get("builder")
        payload = builder(SIDETONE_VALUES[level_lower])
        self._setget("sidetone", payload)

    def set_multipoint(self, enabled):
        """Toggle multipoint connection (bool)."""
        feat = self._feature("multipoint")
        builder = feat.get("builder")
        self._setget("multipoint", builder(enabled))

    def set_auto_pause(self, enabled):
        """Toggle auto play/pause on ear removal (bool)."""
        feat = self._feature("auto_pause")
        builder = feat.get("builder")
        self._setget("auto_pause", builder(enabled))

    def set_auto_answer(self, enabled):
        """Toggle auto-answer calls (bool)."""
        feat = self._feature("auto_answer")
        builder = feat.get("builder")
        self._setget("auto_answer", builder(enabled))

    def set_prompts(self, enabled):
        """Toggle voice prompts. Preserves current language setting."""
        current_enabled, lang_name = self.prompts()
        # Recover language ID from name
        lang_id = 0
        for lid, lname in VOICE_LANGUAGES.items():
            if lname == lang_name:
                lang_id = lid
                break
        feat = self._feature("voice_prompts")
        builder = feat.get("builder")
        self._setget("voice_prompts", builder(enabled, lang_id))

    def power_off(self):
        """Power off the device."""
        self._start("power", bytes([0x00]))

    def set_buttons(self, button_id, event, action):
        """Remap a button action via SETGET [1.9].

        Args:
            button_id: Button ID (int or name like "Action", "Shortcut").
            event: Event type (int or name like "single_press", "long_press").
            action: Action mode (int or name like "VPA", "ANC", "Disabled").
        """
        feat = self._feature("buttons")
        builder = feat.get("builder")
        if not builder:
            raise BmapError("Button remapping not supported on this device")
        payload = builder(button_id, event, action)
        resp = self._setget("buttons", payload)
        parser = feat.get("parser")
        if resp and parser and resp.payload:
            return parser(resp.payload)
        return resp

    def route(self, mac):
        """Switch active audio to a paired BT device by MAC address.

        Uses DeviceManagement ROUTING [4.12] START to route audio UP
        to the specified device.

        Args:
            mac: Target device MAC as "XX:XX:XX:XX:XX:XX".
        """
        feat = self._feature("routing")
        builder = feat.get("builder")
        payload = builder(mac)
        resp = self._start("routing", payload)
        if resp and resp.op == OP_ERROR:
            self._raise_error(resp)

    def pair(self):
        """Enter Bluetooth pairing mode."""
        self._start("pairing", bytes([0x01]))

    # ── Profile Management ───────────────────────────────────────────────────

    def create_profile(self, name, cnc_level=0, spatial=0,
                       wind_block=1, anc_toggle=1):
        """Create a custom profile in the first available slot.

        Returns the slot index used.
        """
        modes = self.modes()
        slot = self._find_free_slot(modes)
        if slot is None:
            raise BmapError("No free profile slot available")
        self._write_mode(slot, name, cnc_level=cnc_level, spatial=spatial,
                         wind_block=wind_block, anc_toggle=anc_toggle)
        return slot

    def update_profile(self, name, **settings):
        """Update an existing custom profile by name."""
        found = self._find_profile(name)
        if found is None:
            raise BmapError("Profile '%s' not found" % name)
        idx, config = found
        if not config.editable:
            raise BmapError("Cannot modify preset mode '%s'" % name)
        self._write_mode_from_config(idx, config, **settings)

    def _find_profile(self, name):
        """Look up a profile by name, preferring editable slots.

        A custom profile may carry the same name as a preset. Returning the
        preset first makes that custom profile impossible to edit or delete.
        """
        modes = self.modes()
        matches = [(idx, cfg) for idx, cfg in sorted(modes.items())
                   if cfg.name.lower() == name.lower()]
        for idx, cfg in matches:
            if cfg.editable:
                return (idx, cfg)
        return matches[0] if matches else None

    def delete_profile(self, name):
        """Delete a custom profile by resetting its slot."""
        found = self._find_profile(name)
        if found is None:
            raise BmapError("Profile '%s' not found" % name)
        idx, config = found
        if not config.editable:
            raise BmapError("Cannot delete preset mode '%s'" % name)
        self._write_mode(idx, "None", cnc_level=0, spatial=0,
                         wind_block=0, anc_toggle=0)

    def profiles(self):
        """List all mode profiles (presets + custom). Returns list of ModeConfig."""
        return list(self.modes().values())

    # ── Low-Level ────────────────────────────────────────────────────────────

    def send_raw(self, hex_str):
        """Send raw hex bytes as a BMAP packet. Returns list of BmapResponse."""
        data = bytes.fromhex(hex_str.replace(" ", ""))
        resp = self._transport.send_recv(data, drain=True)
        return parse_all_responses(resp)

    @property
    def device_info(self):
        """Device identification dict."""
        return self._device.DEVICE_INFO

    @property
    def preset_modes(self):
        """Preset mode definitions dict (name -> {idx, description})."""
        return self._device.PRESET_MODES

    def has_feature(self, name):
        """Check if the connected device supports a feature."""
        return name in self._device.FEATURES

    # ── Internal Helpers ─────────────────────────────────────────────────────

    def _ensure_editable_profile(self):
        """Ensure we're on an editable profile. Returns (slot_idx, ModeConfig).

        If on a preset, finds/creates a "Custom" profile and returns that.
        """
        modes = self.modes()
        current_idx = self.mode_idx()

        if current_idx in modes:
            config = modes[current_idx]
            if config.editable:
                return current_idx, config

        # On a preset — need a custom slot
        for idx, config in sorted(modes.items()):
            if config.name.lower() == "custom" and config.editable:
                return idx, config

        slot = self._find_free_slot(modes)
        if slot is None:
            raise BmapError("No free profile slot available")

        # Read current CNC to carry over
        cnc_cur = 0
        try:
            cnc_cur, _ = self.cnc()
        except BmapError:
            pass

        # Write a new "Custom" profile
        self._write_mode(slot, "Custom", cnc_level=cnc_cur)
        # Re-read to get the full config
        modes = self.modes()
        return slot, modes.get(slot)

    def _current_mode_config(self):
        """Return ModeConfig for the current mode index."""
        idx = self.mode_idx()
        modes = self.modes()
        if idx not in modes:
            raise BmapError("Current mode config not available")
        return modes[idx]

    def _find_free_slot(self, modes):
        """Find the first free editable slot.

        A slot is free when its name is the "None" sentinel or blank. The
        'configured' bit is not part of the test: firmware sets it on first
        write and never clears it, so a deleted slot keeps it and would
        otherwise stay unusable. Matches find_free_slot() in the C++ library.
        """
        for idx in self._device.EDITABLE_SLOTS:
            if idx not in modes:
                return idx
            if modes[idx].name.strip().lower() in ("none", ""):
                return idx
        return None

    def _write_mode(self, slot, name, cnc_level=0, spatial=0,
                    wind_block=1, anc_toggle=1, prompt_b1=0, prompt_b2=0):
        """Write a mode config to a slot via ModeConfig SETGET."""
        feat = self._feature("mode_config")
        builder = feat.get("builder")
        if not builder:
            raise BmapError("Device does not support mode configuration")
        payload = builder(
            mode_idx=slot, name=name, cnc_level=cnc_level,
            spatial=spatial, wind_block=wind_block, anc_toggle=anc_toggle,
            prompt_b1=prompt_b1, prompt_b2=prompt_b2,
        )
        fblock, func = feat["addr"]
        resp = self._transport.send_recv(
            bmap_packet(fblock, func, OP_SETGET, payload), drain=True
        )
        responses = parse_all_responses(resp)
        if not any(r.op == OP_STATUS for r in responses):
            raise BmapDeviceError("Mode config write failed")

    def _write_mode_from_config(self, slot, config, **overrides):
        """Write a mode config preserving existing values, with overrides."""
        if config is None:
            self._write_mode(slot, "Custom", **overrides)
            return

        kw = {
            "name": overrides.get("name", config.name),
            "cnc_level": overrides.get("cnc_level", config.cnc_level),
            "spatial": overrides.get("spatial", config.spatial),
            "wind_block": overrides.get("wind_block", config.wind_block),
            "anc_toggle": overrides.get("anc_toggle", config.anc_toggle),
            "prompt_b1": config.prompt_bytes[0],
            "prompt_b2": config.prompt_bytes[1],
        }
        self._write_mode(slot, **kw)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._transport.close()

    def close(self):
        """Close the connection."""
        self._transport.close()
