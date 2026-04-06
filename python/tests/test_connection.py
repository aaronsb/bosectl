"""Tests for BmapConnection using a mock transport."""

import pytest
from pybmap.connection import BmapConnection
from pybmap.protocol import bmap_packet
from pybmap.constants import OP_GET, OP_STATUS, OP_RESULT, OP_ERROR
from pybmap.errors import BmapError, BmapAuthError, BmapDeviceError
from pybmap.devices import qc_ultra2


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
