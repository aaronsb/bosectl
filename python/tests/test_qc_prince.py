"""Tests for QuietComfort Headphones (prince) device configuration."""

from pybmap.devices import qc_prince, parsers, DEVICES


class TestQCPrinceConfig:
    def test_qc_prince_registered(self):
        assert "qc_prince" in DEVICES

    def test_has_device_info(self):
        assert qc_prince.DEVICE_INFO["product_id"] == 0x4075
        assert qc_prince.DEVICE_INFO["codename"] == "prince"

    def test_has_core_features(self):
        for feat in ["battery", "firmware", "product_name", "voice_prompts",
                      "cnc", "eq", "pairing"]:
            assert feat in qc_prince.FEATURES, "Missing feature: %s" % feat

    def test_rfcomm_channel_8(self):
        assert qc_prince.RFCOMM_CHANNEL == 8

    def test_eq_register_and_parsers(self):
        eq = qc_prince.FEATURES["eq"]
        assert eq["addr"] == (1, 7)
        assert eq["parser"] is parsers.parse_eq
        assert eq["builder"] is parsers.build_eq_band

    def test_eq_builder_encodes_signed_value(self):
        assert parsers.build_eq_band(-2, 0) == bytes([0xFE, 0x00])
        assert parsers.build_eq_band(3, 2) == bytes([0x03, 0x02])

    def test_no_audio_settings(self):
        assert "audio_settings" not in qc_prince.FEATURES

    def test_preset_modes(self):
        assert qc_prince.PRESET_MODES["quiet"]["idx"] == 0
        assert qc_prince.PRESET_MODES["aware"]["idx"] == 1

    def test_editable_slots(self):
        assert qc_prince.EDITABLE_SLOTS == [2, 3]
