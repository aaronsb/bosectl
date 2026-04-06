"""Tests for QC Ultra 2 device configuration."""

from pybmap.devices import qc_ultra2, DEVICES, get_device


class TestDeviceRegistry:
    def test_qc_ultra2_registered(self):
        assert "qc_ultra2" in DEVICES

    def test_qc35_registered(self):
        assert "qc35" in DEVICES

    def test_get_device(self):
        dev = get_device("qc_ultra2")
        assert dev is qc_ultra2

    def test_unknown_device(self):
        from pybmap.errors import BmapError
        try:
            get_device("nonexistent")
            assert False, "Should have raised BmapError"
        except BmapError:
            pass


class TestQCUltra2Config:
    def test_has_device_info(self):
        assert qc_ultra2.DEVICE_INFO["name"] == "Bose QC Ultra Headphones 2"
        assert qc_ultra2.DEVICE_INFO["product_id"] == 0x4082

    def test_has_all_features(self):
        expected = [
            "battery", "firmware", "product_name", "voice_prompts",
            "cnc", "eq", "buttons", "multipoint", "sidetone",
            "auto_pause", "auto_answer", "pairing", "power",
            "get_all_modes", "current_mode", "mode_config", "favorites",
        ]
        for feat in expected:
            assert feat in qc_ultra2.FEATURES, "Missing feature: %s" % feat

    def test_feature_has_addr(self):
        for name, feat in qc_ultra2.FEATURES.items():
            assert "addr" in feat, "Feature '%s' missing addr" % name
            fblock, func = feat["addr"]
            assert isinstance(fblock, int)
            assert isinstance(func, int)

    def test_preset_modes(self):
        assert "quiet" in qc_ultra2.PRESET_MODES
        assert "aware" in qc_ultra2.PRESET_MODES
        assert qc_ultra2.PRESET_MODES["quiet"]["idx"] == 0
        assert qc_ultra2.PRESET_MODES["aware"]["idx"] == 1

    def test_mode_by_idx(self):
        assert qc_ultra2.MODE_BY_IDX[0] == "quiet"
        assert qc_ultra2.MODE_BY_IDX[1] == "aware"

    def test_editable_slots(self):
        assert 4 in qc_ultra2.EDITABLE_SLOTS
        assert 10 in qc_ultra2.EDITABLE_SLOTS
        assert 0 not in qc_ultra2.EDITABLE_SLOTS
        assert 3 not in qc_ultra2.EDITABLE_SLOTS

    def test_status_offsets(self):
        offsets = qc_ultra2.STATUS_OFFSETS
        assert offsets["cnc_level"] == 42
        assert offsets["spatial"] == 44
        assert offsets["anc_toggle"] == 47

    def test_mode_config_has_parser_and_builder(self):
        mc = qc_ultra2.FEATURES["mode_config"]
        assert mc["parser"] is not None
        assert mc["builder"] is not None


class TestQC35Config:
    def test_has_device_info(self):
        from pybmap.devices import qc35
        assert "QC" in qc35.DEVICE_INFO["name"] or "Quiet" in qc35.DEVICE_INFO["name"]

    def test_no_eq(self):
        from pybmap.devices import qc35
        assert "eq" not in qc35.FEATURES

    def test_no_spatial(self):
        from pybmap.devices import qc35
        assert "spatial" not in qc35.FEATURES

    def test_has_battery(self):
        from pybmap.devices import qc35
        assert "battery" in qc35.FEATURES

    def test_no_editable_slots(self):
        from pybmap.devices import qc35
        assert len(qc35.EDITABLE_SLOTS) == 0

    def test_buttons_has_builder(self):
        from pybmap.devices import qc35
        assert qc35.FEATURES["buttons"].get("builder") is not None
