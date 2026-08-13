"""Tests for QuietComfort Headphones ("prince") device configuration."""

from pybmap.catalog import lookup_device, is_supported
from pybmap.devices import qc_headphones, qc_ultra2, DEVICES, PRODUCT_IDS, get_device


class TestDeviceRegistry:
    def test_registered(self):
        assert "qc_headphones" in DEVICES

    def test_get_device(self):
        assert get_device("qc_headphones") is qc_headphones

    def test_product_id_mapping(self):
        assert PRODUCT_IDS[0x4075] == "qc_headphones"

    def test_catalog_entry_points_at_config(self):
        dev = lookup_device(0x4075)
        assert dev is not None
        assert dev.codename == "prince"
        assert dev.config == "qc_headphones"
        assert is_supported(0x4075)


class TestQCHeadphonesConfig:
    def test_has_device_info(self):
        assert qc_headphones.DEVICE_INFO["name"] == "Bose QuietComfort Headphones"
        assert qc_headphones.DEVICE_INFO["product_id"] == 0x4075
        assert qc_headphones.DEVICE_INFO["codename"] == "prince"

    def test_rfcomm_channel_is_nine(self):
        # This model's SDP record puts BMAP on channel 9, not the 2 that
        # the QC Ultra 2 and QC35 use.
        assert qc_headphones.RFCOMM_CHANNEL == 9

    def test_has_verified_features(self):
        expected = [
            "battery", "firmware", "product_name", "voice_prompts",
            "eq", "buttons", "multipoint", "sidetone",
            "auto_pause", "auto_answer", "current_mode", "source",
        ]
        for feat in expected:
            assert feat in qc_headphones.FEATURES, "Missing feature: %s" % feat

    def test_cnc_omitted(self):
        # Firmware 1.0.6-80 rejects CNC [31.10] with FuncNotSupp (04).
        assert "cnc" not in qc_headphones.FEATURES

    def test_feature_has_addr(self):
        for name, feat in qc_headphones.FEATURES.items():
            assert "addr" in feat, "Feature '%s' missing addr" % name
            fblock, func = feat["addr"]
            assert isinstance(fblock, int)
            assert isinstance(func, int)

    def test_shares_qc_ultra2_layouts(self):
        # Every inherited feature must be the same config object, so
        # upstream edits to qc_ultra2 carry over.
        for name, feat in qc_headphones.FEATURES.items():
            assert feat is qc_ultra2.FEATURES[name]

    def test_preset_modes(self):
        assert "quiet" in qc_headphones.PRESET_MODES
        assert "aware" in qc_headphones.PRESET_MODES
