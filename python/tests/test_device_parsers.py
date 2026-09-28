"""Tests for device-specific parsers using real captured data."""

from pathlib import Path

import pytest

from pybmap.devices.parsers import (
    parse_battery, parse_firmware, parse_product_name, parse_cnc,
    parse_battery_readings,
    parse_eq, parse_buttons, parse_multipoint, parse_bool,
    parse_sidetone, parse_voice_prompts,
    parse_mode_config_48, parse_mode_config_47,
    build_mode_config_40, build_mode_config_39,
    build_eq_band, build_toggle, build_sidetone, build_voice_prompts,
    build_buttons,
)
from pybmap.types import ModeConfig, EqBand, ButtonMapping


EDITH_BATTERY_CAPTURE = Path(
    __file__
).parents[2] / "fixtures/packets/qc-ultra2-earbuds/battery-status.hex"


# ── Test data from real QC Ultra 2 captures ──────────────────────────────────
# These hex values come from fixtures/packets/qc-ultra-2/ capture files.

class TestParseBattery:
    def test_from_capture(self):
        # "2.2": "50ffff00" — battery STATUS payload
        payload = bytes.fromhex("50ffff00")
        assert parse_battery(payload) == 0x50  # 80%

    def test_empty(self):
        assert parse_battery(bytes()) is None


class TestParseBatteryReadings:
    def test_multi_component_capture(self):
        payload = bytes.fromhex(EDITH_BATTERY_CAPTURE.read_text().strip())
        readings = parse_battery_readings(payload)
        assert [(r.component_id, r.level) for r in readings] == [
            (1, 60), (2, 60), (4, 60), (3, 80)
        ]

    def test_rejects_incomplete_record(self):
        with pytest.raises(ValueError, match="Malformed battery response"):
            parse_battery_readings(bytes.fromhex("50ffff"))

    def test_rejects_duplicate_component(self):
        with pytest.raises(ValueError, match="Duplicate battery component 1"):
            parse_battery_readings(bytes.fromhex("3cffff0150ffff01"))

    def test_preserves_shuffled_component_ids(self):
        payload = bytes.fromhex("50ffff0332ffff0946ffff043cffff013cffff02")
        readings = parse_battery_readings(payload)
        assert [(r.component_id, r.level) for r in readings] == [
            (3, 80), (9, 50), (4, 70), (1, 60), (2, 60)
        ]


class TestParseFirmware:
    def test_from_capture(self):
        # "0.5": "382e322e32302b6733346366303239"
        payload = bytes.fromhex("382e322e32302b6733346366303239")
        assert parse_firmware(payload) == "8.2.20+g34cf029"


class TestParseProductName:
    def test_from_capture(self):
        # "1.2": "00466172676f"
        payload = bytes.fromhex("00466172676f")
        assert parse_product_name(payload) == "Fargo"


class TestParseCNC:
    def test_from_capture(self):
        # "1.5": "0b0003"
        payload = bytes.fromhex("0b0003")
        current, maximum = parse_cnc(payload)
        assert current == 0  # CNC level 0
        assert maximum == 10  # max is 0x0b - 1 = 10

    def test_short(self):
        assert parse_cnc(bytes()) == (0, 10)


class TestParseEQ:
    def test_from_capture(self):
        # "1.7": "f60a0000f60afe01f60afa02"
        # Three 4-byte bands: [min, max, current, band_id]
        payload = bytes.fromhex("f60a0000f60afe01f60afa02")
        bands = parse_eq(payload)
        assert len(bands) == 3

        # Band 0 (bass): min=0xf6(-10), max=0x0a(10), cur=0x00(0)
        assert bands[0].band_id == 0
        assert bands[0].name == "Bass"
        assert bands[0].current == 0
        assert bands[0].min_val == -10
        assert bands[0].max_val == 10

        # Band 1 (mid): cur=0xfe(-2)
        assert bands[1].band_id == 1
        assert bands[1].name == "Mid"
        assert bands[1].current == -2

        # Band 2 (treble): cur=0xfa(-6)
        assert bands[2].band_id == 2
        assert bands[2].name == "Treble"
        assert bands[2].current == -6


class TestParseButtons:
    def test_from_capture(self):
        # "1.9": "80090e00094002"
        payload = bytes.fromhex("80090e00094002")
        btn = parse_buttons(payload)
        assert btn is not None
        assert btn.button_id == 0x80
        assert btn.button_name == "Shortcut"
        assert btn.event == 9
        assert btn.event_name == "long_press"
        assert btn.action == 14
        assert btn.action_name == "Disabled"

    def test_qc35_action_button(self):
        # Real QC35 capture: button 0x10 (Action), single_press, VPA
        payload = bytes.fromhex("10040107")
        btn = parse_buttons(payload)
        assert btn.button_id == 0x10
        assert btn.button_name == "Action"
        assert btn.event == 4
        assert btn.event_name == "single_press"
        assert btn.action == 1
        assert btn.action_name == "VPA"
        assert "VPA" in btn.supported_actions
        assert "ANC" in btn.supported_actions

    def test_too_short(self):
        assert parse_buttons(bytes([0x80])) is None


class TestBuildButtons:
    def test_by_int(self):
        payload = build_buttons(0x10, 4, 2)
        assert payload == bytes([0x10, 0x04, 0x02])

    def test_by_name(self):
        payload = build_buttons("Action", "single_press", "ANC")
        assert payload == bytes([0x10, 0x04, 0x02])

    def test_mixed(self):
        payload = build_buttons(0x80, "long_press", "Disabled")
        assert payload == bytes([0x80, 0x09, 0x0E])

    def test_unknown_button_raises(self):
        try:
            build_buttons("Nonexistent", 4, 2)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_unknown_event_raises(self):
        try:
            build_buttons(0x10, "fake_event", 2)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_unknown_action_raises(self):
        try:
            build_buttons(0x10, 4, "FakeAction")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_roundtrip(self):
        """Build a payload, parse it back."""
        payload = build_buttons("Action", "single_press", "ANC")
        # Simulate a device response (3 bytes + supported actions bitmask)
        response = payload + bytes([0x07])  # supported: NotConfigured, VPA, ANC
        btn = parse_buttons(response)
        assert btn.button_name == "Action"
        assert btn.event_name == "single_press"
        assert btn.action_name == "ANC"


class TestParseMultipoint:
    def test_from_capture(self):
        # "1.10": "07" — bit 1 set (0x02), multipoint on
        payload = bytes.fromhex("07")
        assert parse_multipoint(payload) is True

    def test_disabled(self):
        assert parse_multipoint(bytes([0x01])) is False  # bit 1 not set

    def test_empty(self):
        assert parse_multipoint(bytes()) is False


class TestParseBool:
    def test_true(self):
        assert parse_bool(bytes([0x01])) is True

    def test_false(self):
        assert parse_bool(bytes([0x00])) is False

    def test_empty(self):
        assert parse_bool(bytes()) is False


class TestParseSidetone:
    def test_from_capture(self):
        # "1.11": "01020f" — byte 1 = 0x02 = medium
        payload = bytes.fromhex("01020f")
        assert parse_sidetone(payload) == 2  # medium


class TestParseVoicePrompts:
    def test_from_capture(self):
        # "1.3": "41000081020000"
        # Byte 0: 0x41 = 0b01000001 → bit6=1, bit5=0, bits4-0=0x01 (US English)
        # Voice prompts enabled flag is at bit 5 per the original RE.
        # 0x41 has bit 6 set but not bit 5, suggesting prompts were off
        # at capture time (bit 6 may be a different flag).
        payload = bytes.fromhex("41000081020000")
        enabled, lang = parse_voice_prompts(payload)
        assert enabled is False  # bit 5 not set in 0x41
        assert lang == 1  # US English

    def test_enabled(self):
        # 0x21 = 0b00100001 → bit5=1 (enabled), lang=1 (US English)
        payload = bytes([0x21])
        enabled, lang = parse_voice_prompts(payload)
        assert enabled is True
        assert lang == 1

    def test_disabled(self):
        enabled, lang = parse_voice_prompts(bytes([0x01]))
        assert enabled is False
        assert lang == 1


# ── ModeConfig Tests ─────────────────────────────────────────────────────────

class TestBuildModeConfig:
    def test_payload_length(self):
        payload = build_mode_config_40(5, "Custom")
        assert len(payload) == 40

    def test_fields(self):
        payload = build_mode_config_40(
            mode_idx=5, name="Test", cnc_level=7,
            spatial=2, wind_block=1, anc_toggle=1,
            prompt_b1=0, prompt_b2=1,
        )
        assert payload[0] == 5      # mode index
        assert payload[1] == 0      # prompt b1
        assert payload[2] == 1      # prompt b2
        assert payload[3:7] == b"Test"  # start of name
        assert payload[35] == 7     # cnc
        assert payload[36] == 0     # auto_cnc (False)
        assert payload[37] == 2     # spatial (head)
        assert payload[38] == 1     # wind_block
        assert payload[39] == 1     # anc_toggle

    def test_roundtrip_40(self):
        """Build a 40-byte payload, parse it back."""
        payload = build_mode_config_40(
            mode_idx=5, name="MyMode", cnc_level=8,
            spatial=1, wind_block=1, anc_toggle=1,
        )
        config = parse_mode_config_48(payload)
        assert config is not None
        assert config.mode_idx == 5
        assert config.name == "MyMode"
        assert config.cnc_level == 8
        assert config.spatial == 1
        assert config.wind_block is True
        assert config.anc_toggle is True

    def test_prince_payload_length(self):
        payload = build_mode_config_39(
            mode_idx=3, name="Music", cnc_level=5,
            spatial=0, wind_block=1, prompt_b1=0, prompt_b2=12,
        )
        assert len(payload) == 39
        assert payload[0] == 3
        assert payload[1] == 0
        assert payload[2] == 12
        assert payload[3:8] == b"Music"
        assert payload[35] == 5
        assert payload[36] == 0
        assert payload[37] == 0
        assert payload[38] == 1

    def test_prince_roundtrip_39(self):
        payload = build_mode_config_39(
            mode_idx=2, name="Commute", cnc_level=0,
            spatial=0, wind_block=1, prompt_b1=0, prompt_b2=7,
        )
        config = parse_mode_config_47(payload)
        assert config is not None
        assert config.mode_idx == 2
        assert config.name == "Commute"
        assert config.cnc_level == 0
        assert config.wind_block is True
        assert config.anc_toggle is False


class TestParseModeConfig48:
    def test_too_short(self):
        assert parse_mode_config_48(bytes([0, 0, 0])) is None

    def test_minimal(self):
        # 6 bytes: just enough for mode_idx + prompt + flags (no full parse)
        payload = bytes([5, 0, 0, 1, 0, 0])
        config = parse_mode_config_48(payload)
        assert config is not None
        assert config.mode_idx == 5


class TestParseModeConfig47:
    def test_from_prince_music_capture(self):
        payload = bytes.fromhex(
            "03000c0101004d757369630000000000000000000000000000000000"
            "00000000000000000000000000090500000000"
        )
        config = parse_mode_config_47(payload)
        assert config is not None
        assert config.mode_idx == 3
        assert config.prompt_bytes == (0, 12)
        assert config.name == "Music"
        assert config.editable is True
        assert config.configured is True
        assert config.cnc_level == 5
        assert config.auto_cnc is False
        assert config.spatial == 0
        assert config.wind_block is False
        assert config.anc_toggle is False

    def test_from_prince_commute_capture(self):
        payload = bytes.fromhex(
            "020007010100436f6d6d757465000000000000000000000000000000"
            "00000000000000000000000000090000000001"
        )
        config = parse_mode_config_47(payload)
        assert config is not None
        assert config.mode_idx == 2
        assert config.prompt_bytes == (0, 7)
        assert config.name == "Commute"
        assert config.cnc_level == 0
        assert config.wind_block is True


# ── Builder Tests ────────────────────────────────────────────────────────────

class TestBuilders:
    def test_eq_band(self):
        payload = build_eq_band(3, 0)  # bass +3
        assert payload == bytes([3, 0])

    def test_eq_band_negative(self):
        payload = build_eq_band(-3, 1)  # mid -3
        assert payload == bytes([0xFD, 1])  # -3 as unsigned byte

    def test_toggle_on(self):
        assert build_toggle(True) == bytes([1])

    def test_toggle_off(self):
        assert build_toggle(False) == bytes([0])

    def test_sidetone(self):
        payload = build_sidetone(2)  # medium
        assert payload == bytes([1, 2])  # persist=1, level=2

    def test_voice_prompts_on(self):
        payload = build_voice_prompts(True, 1)  # US English, on
        assert payload == bytes([0x21])  # bit5=1, lang=1

    def test_voice_prompts_off(self):
        payload = build_voice_prompts(False, 1)  # US English, off
        assert payload == bytes([0x01])  # bit5=0, lang=1
