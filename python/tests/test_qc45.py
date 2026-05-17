"""Tests for QC45 device configuration."""

from pybmap.devices import qc45, parsers, DEVICES


class TestQC45Config:
    def test_qc45_registered(self):
        assert "qc45" in DEVICES

    def test_has_device_info(self):
        assert qc45.DEVICE_INFO["product_id"] == 0x4039
        assert qc45.DEVICE_INFO["codename"] == "duran"

    def test_has_core_features(self):
        for feat in ["battery", "firmware", "product_name", "voice_prompts",
                      "cnc", "eq", "buttons", "multipoint", "sidetone", "pairing"]:
            assert feat in qc45.FEATURES, "Missing feature: %s" % feat

    def test_has_audio_modes(self):
        assert "get_all_modes" in qc45.FEATURES
        assert "current_mode" in qc45.FEATURES
        assert "mode_config" in qc45.FEATURES

    def test_no_audio_settings(self):
        assert "audio_settings" not in qc45.FEATURES

    def test_no_auto_pause(self):
        assert "auto_pause" not in qc45.FEATURES

    def test_rfcomm_channel_8(self):
        assert qc45.RFCOMM_CHANNEL == 8

    def test_has_init_packet(self):
        assert qc45.INIT_PACKET == (0, 1)

    def test_eq_has_builder(self):
        assert qc45.FEATURES["eq"].get("builder") is not None

    def test_preset_modes(self):
        assert "quiet" in qc45.PRESET_MODES
        assert "aware" in qc45.PRESET_MODES
        assert qc45.PRESET_MODES["quiet"]["idx"] == 0
        assert qc45.PRESET_MODES["aware"]["idx"] == 1

    def test_editable_slots(self):
        assert 2 in qc45.EDITABLE_SLOTS
        assert 3 in qc45.EDITABLE_SLOTS
        assert 0 not in qc45.EDITABLE_SLOTS
        assert 1 not in qc45.EDITABLE_SLOTS

    def test_mode_config_has_parser_and_builder(self):
        mc = qc45.FEATURES["mode_config"]
        assert mc["parser"] is not None
        assert mc["builder"] is not None

    def test_mode_config_uses_39byte_format(self):
        assert qc45.FEATURES["mode_config"]["builder"] is parsers.build_mode_config_39
        assert qc45.FEATURES["mode_config"]["parser"] is parsers.parse_mode_config_47


class TestQC45ModeConfigParser:
    """Test the 47-byte ModeConfig STATUS parser used by QC45."""

    def _quiet_payload(self):
        return bytes.fromhex(
            "0000010000015175696574"
            "000000000000000000000000000000000000000000"
            "000000000000000000000000000000"
        )

    def _music_payload(self):
        return bytes.fromhex(
            "02000c0101014d75736963"
            "000000000000000000000000000000000000000000"
            "000000000000000000090500000000"
        )

    def test_parse_quiet_mode(self):
        # Exact payload from probe: mode 0, Quiet, cnc=0, preset
        payload = bytes.fromhex(
            "0000010000015175696574"
            "000000000000000000000000000000000000000000"
            "000000000000000000000000000000"
        )
        config = parsers.parse_mode_config_47(payload)
        assert config is not None
        assert config.mode_idx == 0
        assert config.name == "Quiet"
        assert config.editable is False
        assert config.cnc_level == 0

    def test_parse_aware_mode(self):
        # Exact payload from probe: mode 1, Aware, cnc=10, preset
        payload = bytes.fromhex(
            "0100020000014177617265"
            "000000000000000000000000000000000000000000"
            "000000000000000000000a00000000"
        )
        config = parsers.parse_mode_config_47(payload)
        assert config is not None
        assert config.mode_idx == 1
        assert config.name == "Aware"
        assert config.editable is False
        assert config.cnc_level == 10

    def test_parse_editable_music_mode(self):
        # Exact payload from probe after SETGET: mode 2, Music, cnc=3, editable
        payload = bytes.fromhex(
            "02000c0101014d75736963"
            "000000000000000000000000000000000000000000"
            "000000000000000000090300000000"
        )
        config = parsers.parse_mode_config_47(payload)
        assert config is not None
        assert config.mode_idx == 2
        assert config.name == "Music"
        assert config.editable is True
        assert config.configured is True
        assert config.cnc_level == 3

    def test_parse_setget_echo_39bytes(self):
        payload = parsers.build_mode_config_39(
            2, "Music", cnc_level=7, prompt_b1=0, prompt_b2=12,
        )
        assert len(payload) == 39
        config = parsers.parse_mode_config_47(payload)
        assert config is not None
        assert config.mode_idx == 2
        assert config.name == "Music"
        assert config.cnc_level == 7

    def test_anc_toggle_always_false(self):
        # QC45 has no ancToggle field (47 bytes vs 48)
        payload = bytes.fromhex(
            "0000010000015175696574"
            "000000000000000000000000000000000000000000"
            "000000000000000000000000000000"
        )
        config = parsers.parse_mode_config_47(payload)
        assert config.anc_toggle is False


class TestQC45ModeConfigBuilder:
    """Test the 39-byte ModeConfig SETGET builder used by QC45."""

    def test_build_39_bytes(self):
        payload = parsers.build_mode_config_39(2, "Music", cnc_level=5)
        assert len(payload) == 39

    def test_build_mode_index(self):
        payload = parsers.build_mode_config_39(3, "Test", cnc_level=7)
        assert payload[0] == 3

    def test_build_prompt_bytes(self):
        payload = parsers.build_mode_config_39(
            2, "Music", prompt_b1=0, prompt_b2=12,
        )
        assert payload[1] == 0
        assert payload[2] == 12

    def test_build_name_encoding(self):
        payload = parsers.build_mode_config_39(2, "Music")
        name = payload[3:35].split(b"\x00", 1)[0]
        assert name == b"Music"

    def test_build_cnc_level(self):
        payload = parsers.build_mode_config_39(2, "Test", cnc_level=7)
        assert payload[35] == 7

    def test_build_trailing_fields(self):
        payload = parsers.build_mode_config_39(
            2, "Test", cnc_level=5, auto_cnc=False,
            spatial=0, wind_block=False,
        )
        assert payload[36] == 0  # auto_cnc
        assert payload[37] == 0  # spatial
        assert payload[38] == 0  # wind_block

    def test_roundtrip(self):
        payload = parsers.build_mode_config_39(
            2, "Custom", cnc_level=3, prompt_b1=0, prompt_b2=12,
        )
        config = parsers.parse_mode_config_47(payload)
        assert config.mode_idx == 2
        assert config.name == "Custom"
        assert config.cnc_level == 3
