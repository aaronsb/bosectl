"""Tests for BmapConnection using a mock transport."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from pybmap.connection import BmapConnection
from pybmap.protocol import bmap_packet
from pybmap.constants import OP_GET, OP_SETGET, OP_STATUS, OP_RESULT, OP_ERROR
from pybmap.errors import (
    BmapError, BmapAuthError, BmapDeviceError,
    BmapDesyncError, BmapConnectionError,
)
from pybmap.devices import qc_ultra2, qc_ultra2_earbuds, qc_prince, qc45
from pybmap.types import ModeConfig


EARBUDS_BATTERY_FIXTURE = bytes.fromhex(
    (Path(__file__).parents[2]
     / "fixtures/packets/qc-ultra2-earbuds/battery-status.hex").read_text().strip()
)


class MockTransport:
    """Fake RFCOMM transport that returns canned responses."""

    def __init__(self):
        self.responses = {}  # (fblock, func) -> raw response bytes
        self.sent = []
        self.closed = False

    def add_response(self, fblock, func, op, payload):
        """Register a canned response for a given (fblock, func)."""
        self.responses[(fblock, func)] = bytes([fblock, func, op, len(payload)]) + payload

    def send_recv(self, packet, drain=False):
        self.sent.append(packet)
        fblock = packet[0]
        func = packet[1]
        key = (fblock, func)
        if key in self.responses:
            return self.responses[key]
        # Default: return an error
        return bytes([fblock, func, OP_ERROR, 1, 4])  # FuncNotSupp

    def close(self):
        self.closed = True


@pytest.fixture
def mock_dev():
    """Create a BmapConnection with a mock transport and QC Ultra 2 config."""
    transport = MockTransport()
    # Set up standard responses from real capture data
    transport.add_response(2, 2, OP_STATUS, bytes([80, 0xff, 0xff, 0x00]))  # battery 80%
    transport.add_response(0, 5, OP_STATUS, b"8.2.20+g34cf029")  # firmware
    transport.add_response(1, 2, OP_STATUS, bytes([0x00]) + b"Fargo")  # name
    transport.add_response(1, 5, OP_STATUS, bytes([0x0b, 0x07, 0x03]))  # cnc: 7/10
    transport.add_response(1, 7, OP_STATUS, bytes.fromhex("f60a0300f60afe01f60afa02"))  # eq
    transport.add_response(1, 10, OP_STATUS, bytes([0x07]))  # multipoint on
    transport.add_response(1, 11, OP_STATUS, bytes([0x01, 0x02, 0x0f]))  # sidetone medium
    transport.add_response(1, 24, OP_STATUS, bytes([0x01]))  # auto_pause on
    transport.add_response(1, 27, OP_STATUS, bytes([0x01]))  # auto_answer on
    transport.add_response(1, 3, OP_STATUS, bytes([0x21, 0, 0, 0x81, 2, 0, 0]))  # prompts on, US English
    transport.add_response(31, 3, OP_STATUS, bytes([0x00]))  # current mode: quiet (idx 0)
    transport.add_response(1, 9, OP_STATUS, bytes.fromhex("80090e00094002"))  # buttons
    return BmapConnection(transport, qc_ultra2)


class TestReadOperations:
    def test_battery(self, mock_dev):
        assert mock_dev.battery() == 80

    def test_battery_rejects_empty_response(self):
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS, b"")
        dev = BmapConnection(transport, qc_ultra2)
        with pytest.raises(BmapDeviceError, match="Empty battery response"):
            dev.battery()

    @pytest.mark.parametrize("response", [
        bytes([2, 2, OP_STATUS, 4, 80, 0xff]),
        bytes([2, 2, 0x08, 0]),
    ])
    def test_battery_rejects_invalid_frame(self, response):
        transport = MockTransport()
        transport.responses[(2, 2)] = response
        dev = BmapConnection(transport, qc_ultra2)
        with pytest.raises(BmapDeviceError, match="Invalid or empty response"):
            dev.battery()

    def test_battery_uses_configured_parser(self):
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS, bytes([80]))
        device = SimpleNamespace(
            DEVICE_INFO={"name": "Custom"},
            FEATURES={
                "battery": {
                    "addr": (2, 2),
                    "parser": lambda payload: payload[0] - 1,
                },
            },
        )
        assert BmapConnection(transport, device).battery() == 79

    def test_battery_readings(self):
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS,
                               bytes.fromhex("50ffff033cffff013cffff0246ffff04"))
        dev = BmapConnection(transport, qc_ultra2_earbuds)
        readings = dev.battery_readings()
        assert [(r.component_id, r.level) for r in readings] == [
            (3, 80), (1, 60), (2, 60), (4, 70)
        ]

    def test_battery_uses_combined_earbud_record(self):
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS,
                               bytes.fromhex("46ffff0450ffff023cffff0140ffff03"))
        dev = BmapConnection(transport, qc_ultra2_earbuds)
        assert dev.battery() == 70

    def test_battery_falls_back_to_lowest_bud_without_aggregate(self):
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS,
                               bytes.fromhex("3cffff0150ffff0228ffff03"))
        dev = BmapConnection(transport, qc_ultra2_earbuds)
        # Case (3) is lower but is not a bud; right bud (1) is the lowest.
        assert dev.battery() == 60

    def test_battery_rejects_response_without_valid_buds(self):
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS,
                               bytes.fromhex("ffffff01ffffff02ffffff0428ffff03"))
        dev = BmapConnection(transport, qc_ultra2_earbuds)
        with pytest.raises(BmapDeviceError, match="aggregate component 4"):
            dev.battery()

    def test_status_falls_back_when_fixture_aggregate_is_invalid(self):
        records = [EARBUDS_BATTERY_FIXTURE[i:i + 4]
                   for i in range(0, len(EARBUDS_BATTERY_FIXTURE), 4)]
        invalid = b"".join(b"\xff" + r[1:] if r[3] == 4 else r for r in records)
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS, invalid)
        status = BmapConnection(transport, qc_ultra2_earbuds).status()
        assert status.battery == 60
        assert [(r.component_id, r.level) for r in status.battery_readings] == [
            (1, 60), (2, 60), (3, 80)
        ]

    def test_status_falls_back_when_fixture_aggregate_is_absent(self):
        records = [EARBUDS_BATTERY_FIXTURE[i:i + 4]
                   for i in range(0, len(EARBUDS_BATTERY_FIXTURE), 4)]
        absent = b"".join(r for r in records if r[3] != 4)
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS, absent)
        status = BmapConnection(transport, qc_ultra2_earbuds).status()
        assert status.battery == 60
        assert [(r.component_id, r.level) for r in status.battery_readings] == [
            (1, 60), (2, 60), (3, 80)
        ]

    def test_status_rejects_battery_without_valid_readings(self):
        # A failed read must not surface as a measured 0%.
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS,
                               bytes.fromhex("ffffff01ffffff02ffffff04ffffff03"))
        transport.add_response(31, 3, OP_STATUS, bytes([0x01]))
        dev = BmapConnection(transport, qc_ultra2_earbuds)
        with pytest.raises(BmapDeviceError, match="aggregate component 4"):
            dev.status()

    def test_status_uses_one_battery_response(self):
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS,
                               bytes.fromhex("50ffff033cffff0146ffff043cffff02"))
        dev = BmapConnection(transport, qc_ultra2_earbuds)
        status = dev.status()
        assert status.battery == 70
        assert [(r.component_id, r.level) for r in status.battery_readings] == [
            (3, 80), (1, 60), (4, 70), (2, 60)
        ]
        assert sum(packet[:2] == bytes([2, 2]) for packet in transport.sent) == 1

    def test_firmware(self, mock_dev):
        assert mock_dev.firmware() == "8.2.20+g34cf029"

    def test_name(self, mock_dev):
        assert mock_dev.name() == "Fargo"

    def test_cnc(self, mock_dev):
        current, maximum = mock_dev.cnc()
        assert current == 7
        assert maximum == 10

    def test_eq(self, mock_dev):
        bands = mock_dev.eq()
        assert len(bands) == 3
        assert bands[0].name == "Bass"
        assert bands[0].current == 3
        assert bands[1].current == -2
        assert bands[2].current == -6

    def test_multipoint(self, mock_dev):
        assert mock_dev.multipoint() is True

    def test_sidetone(self, mock_dev):
        assert mock_dev.sidetone() == "medium"

    def test_auto_pause(self, mock_dev):
        assert mock_dev.auto_pause() is True

    def test_auto_answer(self, mock_dev):
        assert mock_dev.auto_answer() is True

    def test_prompts(self, mock_dev):
        enabled, lang = mock_dev.prompts()
        assert enabled is True
        assert lang == "US English"

    def test_mode(self, mock_dev):
        assert mock_dev.mode() == "quiet"

    def test_mode_idx(self, mock_dev):
        assert mock_dev.mode_idx() == 0

    def test_buttons(self, mock_dev):
        btn = mock_dev.buttons()
        assert btn.button_name == "Shortcut"
        assert btn.event_name == "long_press"
        assert btn.action_name == "Disabled"


class TestStatus:
    def test_returns_full_status(self, mock_dev):
        s = mock_dev.status()
        assert s.battery == 80
        assert s.battery_readings == []
        assert s.mode == "quiet"
        assert s.cnc_level == 7
        assert s.cnc_max == 10
        assert s.name == "Fargo"
        assert s.firmware == "8.2.20+g34cf029"
        assert s.sidetone == "medium"
        assert s.multipoint is True
        assert s.auto_pause is True
        assert s.prompts_enabled is True
        assert s.prompts_language == "US English"

    def test_tolerates_missing_features(self):
        """status() should not crash if a feature is unsupported."""
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS, bytes([50, 0xff, 0xff, 0x00]))
        transport.add_response(31, 3, OP_STATUS, bytes([0x01]))
        # Only battery and current_mode respond; everything else errors
        dev = BmapConnection(transport, qc_ultra2)
        s = dev.status()
        assert s.battery == 50
        assert s.mode == "aware"
        # Unsupported features get defaults
        assert s.eq == []
        assert s.name == ""
        assert s.firmware == ""


class TestPublicAPI:
    def test_device_info(self, mock_dev):
        info = mock_dev.device_info
        assert info["name"] == "Bose QC Ultra Headphones 2"

    def test_preset_modes(self, mock_dev):
        presets = mock_dev.preset_modes
        assert "quiet" in presets
        assert "aware" in presets
        assert presets["quiet"]["idx"] == 0

    def test_has_feature(self, mock_dev):
        assert mock_dev.has_feature("battery") is True
        assert mock_dev.has_feature("eq") is True
        assert mock_dev.has_feature("nonexistent") is False

    def test_context_manager(self):
        transport = MockTransport()
        transport.add_response(2, 2, OP_STATUS, bytes([70, 0xff, 0xff, 0x00]))
        with BmapConnection(transport, qc_ultra2) as dev:
            assert dev.battery() == 70
        assert transport.closed is True


class TestPrinceAudioModes:
    MUSIC_MODE = bytes.fromhex(
        "03000c0101004d757369630000000000000000000000000000000000"
        "00000000000000000000000000090500000000"
    )

    def test_audio_settings_fallback_reads_current_mode(self):
        transport = MockTransport()
        transport.add_response(31, 3, OP_STATUS, bytes([3]))
        transport.responses[(31, 1)] = (
            bytes([31, 6, OP_STATUS, len(self.MUSIC_MODE)]) + self.MUSIC_MODE
        )
        dev = BmapConnection(transport, qc_prince)

        settings = dev.audio_settings()

        assert settings.cnc_level == 5
        assert settings.wind_block is False
        assert settings.anc_toggle is False

    def test_set_wind_fallback_writes_39_byte_mode_config(self):
        transport = MockTransport()
        transport.add_response(31, 3, OP_STATUS, bytes([3]))
        transport.responses[(31, 1)] = (
            bytes([31, 6, OP_STATUS, len(self.MUSIC_MODE)]) + self.MUSIC_MODE
        )
        transport.add_response(31, 6, OP_STATUS, self.MUSIC_MODE)
        dev = BmapConnection(transport, qc_prince)

        dev.set_wind(True)

        sent = transport.sent[-1]
        assert sent[:4] == bytes([31, 6, OP_SETGET, 39])
        assert sent[4] == 3
        assert sent[4 + 35] == 5
        assert sent[4 + 38] == 1

    def test_set_anc_fallback_rejects_unsupported_toggle(self):
        transport = MockTransport()
        dev = BmapConnection(transport, qc_prince)

        with pytest.raises(BmapError, match="ANC on/off"):
            dev.set_anc(False)


class TestErrorHandling:
    def test_unsupported_feature(self, mock_dev):
        """Accessing a feature not in the device config raises BmapError."""
        with pytest.raises(BmapError, match="does not support"):
            mock_dev._get("nonexistent_feature")

    def test_auth_error(self):
        """Error code 5 raises BmapAuthError."""
        transport = MockTransport()
        transport.add_response(1, 5, OP_ERROR, bytes([5]))  # auth error
        dev = BmapConnection(transport, qc_ultra2)
        with pytest.raises(BmapAuthError):
            dev.cnc()

    def test_device_error(self):
        """Other error codes raise BmapDeviceError."""
        transport = MockTransport()
        transport.add_response(1, 5, OP_ERROR, bytes([8]))  # runtime error
        dev = BmapConnection(transport, qc_ultra2)
        with pytest.raises(BmapDeviceError) as exc_info:
            dev.cnc()
        assert exc_info.value.error_code == 8


class TestUnknownDevice:
    def test_get_device_unknown(self):
        from pybmap.devices import get_device
        with pytest.raises(BmapError, match="Unknown device type"):
            get_device("nonexistent")


class TestQc45Connection:
    """Cross the connection seam for QC45 — the gap #21's review found."""

    # 47-byte STATUS: idx 3, editable+configured, name "Music", cnc 5 at [42]
    MUSIC_MODE = (
        bytes([3, 0, 0, 1, 1, 0]) + b"Music".ljust(32, b"\x00")
        + bytes([0, 0, 0, 0, 5, 0, 0, 0, 0])
    )

    def _dev(self):
        from pybmap.devices import qc45
        transport = MockTransport()
        transport.add_response(31, 3, OP_STATUS, bytes([3]))
        transport.responses[(31, 1)] = (
            bytes([31, 6, OP_STATUS, len(self.MUSIC_MODE)]) + self.MUSIC_MODE
        )
        transport.add_response(31, 6, OP_STATUS, self.MUSIC_MODE)
        return transport, BmapConnection(transport, qc45)

    def test_set_cnc_writes_39_byte_mode_config(self):
        transport, dev = self._dev()
        dev.set_cnc(7)
        sent = transport.sent[-1]
        assert sent[:4] == bytes([31, 6, OP_SETGET, 39])
        assert sent[4] == 3          # slot
        assert sent[4 + 35] == 7     # cnc level, no anc_toggle byte follows


class TestQcEarbudsConnection:
    def test_set_cnc_uses_direct_setget(self):
        from pybmap.devices import qc_earbuds
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes([0x0b, 0x04, 0x01]))
        dev = BmapConnection(transport, qc_earbuds)
        dev.set_cnc(4)
        assert transport.sent[-1] == bytes([1, 5, OP_SETGET, 2, 4, 1])


class TestUltraOpenConnection:
    def test_no_cnc_feature_and_no_profile_editing(self):
        from pybmap.devices import ultra_open
        dev = BmapConnection(MockTransport(), ultra_open)
        assert not dev.has_feature("cnc")
        with pytest.raises(BmapError):
            dev.set_cnc(3)
        assert ultra_open.FEATURES["mode_config"].get("builder") is None

    def test_set_mode_resolves_name_from_device_when_no_presets(self):
        from pybmap.devices import ultra_open
        transport = MockTransport()
        still = bytes([1, 0, 0, 0, 1, 0]) + b"Still".ljust(32, b"\x00") + bytes(10)
        transport.responses[(31, 1)] = bytes([31, 6, OP_STATUS, len(still)]) + still
        transport.add_response(31, 3, OP_RESULT, b"")
        dev = BmapConnection(transport, ultra_open)
        dev.set_mode("still")
        assert transport.sent[-1] == bytes([31, 3, 5, 2, 1, 0])


class TestSetName:
    def test_rejects_over_31_bytes(self, mock_dev):
        with pytest.raises(ValueError, match="31 bytes"):
            mock_dev.set_name("x" * 32)

    def test_counts_utf8_bytes_not_chars(self, mock_dev):
        with pytest.raises(ValueError):
            mock_dev.set_name("é" * 16)  # 32 bytes
        mock_dev.set_name("é" * 15)      # 30 bytes, fine


class TestDiscoveryMacGuard:
    def test_regex(self):
        from pybmap.discovery import _MAC_RE
        assert _MAC_RE.match("AA:bb:CC:dd:EE:ff")
        assert not _MAC_RE.match("AA:bb:CC:dd:EE:ff;rm")
        assert not _MAC_RE.match("AA-bb-CC-dd-EE-ff")


def _mode(idx, name, editable=True, configured=True):
    """Build a ModeConfig row for slot-selection tests."""
    return ModeConfig(
        mode_idx=idx, prompt="NONE", prompt_bytes=(0, 0), name=name,
        cnc_level=0, auto_cnc=False, spatial=0, wind_block=False,
        anc_toggle=False, editable=editable, configured=configured,
        flags="", raw=b"",
    )


@pytest.fixture
def qc45_conn():
    return BmapConnection(MockTransport(), qc45)


class TestFreeSlot:
    """Firmware leaves 'configured' set after a slot is cleared."""

    def test_cleared_slot_is_reusable(self, qc45_conn):
        modes = {
            0: _mode(0, "Quiet", editable=False),
            1: _mode(1, "Aware", editable=False),
            2: _mode(2, "None", configured=True),
            3: _mode(3, "Gym"),
        }
        assert qc45_conn._find_free_slot(modes) == 2

    def test_blank_name_is_reusable(self, qc45_conn):
        modes = {2: _mode(2, "", configured=True), 3: _mode(3, "Gym")}
        assert qc45_conn._find_free_slot(modes) == 2

    def test_named_slots_are_not_free(self, qc45_conn):
        modes = {2: _mode(2, "Gym"), 3: _mode(3, "Commute")}
        assert qc45_conn._find_free_slot(modes) is None

    def test_missing_slot_is_free(self, qc45_conn):
        assert qc45_conn._find_free_slot({2: _mode(2, "Gym")}) == 3


class TestProfileLookup:
    """A custom profile may share a preset's name (issue #29)."""

    def test_prefers_editable_over_preset(self, qc45_conn, monkeypatch):
        modes = {
            1: _mode(1, "Aware", editable=False),
            3: _mode(3, "Aware", editable=True),
        }
        monkeypatch.setattr(qc45_conn, "modes", lambda: modes)
        idx, cfg = qc45_conn._find_profile("Aware")
        assert idx == 3 and cfg.editable

    def test_delete_targets_custom_not_preset(self, qc45_conn, monkeypatch):
        modes = {
            1: _mode(1, "Aware", editable=False),
            3: _mode(3, "Aware", editable=True),
        }
        monkeypatch.setattr(qc45_conn, "modes", lambda: modes)
        written = []
        monkeypatch.setattr(qc45_conn, "_write_mode",
                            lambda slot, name, **kw: written.append(slot))
        qc45_conn.delete_profile("Aware")
        assert written == [3]

    def test_preset_only_match_still_refused(self, qc45_conn, monkeypatch):
        monkeypatch.setattr(qc45_conn, "modes",
                            lambda: {1: _mode(1, "Aware", editable=False)})
        with pytest.raises(BmapError, match="preset"):
            qc45_conn.delete_profile("Aware")

    def test_unknown_name_raises(self, qc45_conn, monkeypatch):
        monkeypatch.setattr(qc45_conn, "modes", lambda: {3: _mode(3, "Gym")})
        with pytest.raises(BmapError, match="not found"):
            qc45_conn.delete_profile("Nope")


class TestResponseAddressCheck:
    """A response from the wrong address must not be parsed as the right one.

    Observed on a QC45 after the headset dropped and reconnected: the socket
    still held responses queued before the drop, so every read returned the
    previous request's answer.
    """

    def test_mismatched_address_raises(self, mock_dev):
        # Ask for battery [2.2], answer with firmware [0.5].
        mock_dev._transport.responses[(2, 2)] = (
            bytes([0, 5, OP_STATUS, 3]) + b"4.0")
        with pytest.raises(BmapDesyncError, match=r"\[0\.5\].*expected \[2\.2\]"):
            mock_dev.battery()

    def test_matching_address_passes(self, mock_dev):
        assert mock_dev.battery() == 80

    def test_setget_checks_address_too(self, mock_dev):
        mock_dev._transport.responses[(1, 7)] = (
            bytes([2, 2, OP_STATUS, 1]) + bytes([42]))
        with pytest.raises(BmapDesyncError):
            mock_dev.set_eq(1, 2, 3)

    def test_desync_is_a_connection_error(self):
        # Callers that already retry on connection loss should retry on this.
        assert issubclass(BmapDesyncError, BmapConnectionError)
