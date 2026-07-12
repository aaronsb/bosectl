"""Tests for QC Earbuds (1st Gen) device configuration."""

from pybmap.devices import qc_earbuds, DEVICES


class TestQCEarbudsConfig:
    def test_has_device_info(self):
        assert "QC Earbuds" in qc_earbuds.DEVICE_INFO["name"]
        assert qc_earbuds.DEVICE_INFO["product_id"] == 0x402F
        assert qc_earbuds.DEVICE_INFO["codename"] == "lando"

    def test_channel(self):
        assert qc_earbuds.RFCOMM_CHANNEL == 8

    def test_has_key_features(self):
        for feat in ["battery", "cnc", "eq", "buttons", "power",
                     "current_mode", "mode_config", "sidetone"]:
            assert feat in qc_earbuds.FEATURES, "Missing: %s" % feat

    def test_no_audio_settings(self):
        assert "audio_settings" not in qc_earbuds.FEATURES

    def test_no_anc_wind_spatial(self):
        assert "spatial" not in qc_earbuds.FEATURES

    def test_cnc_has_builder(self):
        assert qc_earbuds.FEATURES["cnc"].get("builder") is not None

    def test_no_editable_slots(self):
        assert len(qc_earbuds.EDITABLE_SLOTS) == 0

    def test_4_modes_only(self):
        # Only modes 0 (quiet) and 1 (aware) have known names.
        # Modes 2-3 exist but are unnamed/unconfigured.
        assert 0 in qc_earbuds.MODE_BY_IDX
        assert 1 in qc_earbuds.MODE_BY_IDX
        assert 4 not in qc_earbuds.MODE_BY_IDX

    def test_no_mode_config_builder(self):
        assert qc_earbuds.FEATURES["mode_config"].get("builder") is None

    def test_registered(self):
        assert "qc_earbuds" in DEVICES
