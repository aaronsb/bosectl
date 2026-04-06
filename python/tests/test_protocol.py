"""Tests for the universal BMAP protocol module."""

from pybmap.protocol import (
    bmap_packet, parse_response, parse_all_responses, fmt_response,
    encode_mode_name,
)
from pybmap.constants import OP_GET, OP_SETGET, OP_START, OP_STATUS, OP_RESULT, OP_ERROR
from pybmap.types import BmapResponse


class TestBmapPacket:
    def test_get_battery(self):
        pkt = bmap_packet(2, 2, OP_GET)
        assert pkt == bytes([0x02, 0x02, 0x01, 0x00])

    def test_start_mode_switch(self):
        pkt = bmap_packet(31, 3, OP_START, bytes([0, 0]))
        assert pkt == bytes([0x1f, 0x03, 0x05, 0x02, 0x00, 0x00])

    def test_setget_with_payload(self):
        payload = bytes([0x03, 0x00])  # EQ band
        pkt = bmap_packet(1, 7, OP_SETGET, payload)
        assert pkt[0] == 1   # fblock
        assert pkt[1] == 7   # func
        assert pkt[2] == 2   # OP_SETGET
        assert pkt[3] == 2   # payload length
        assert pkt[4:] == payload

    def test_empty_payload(self):
        pkt = bmap_packet(0, 5, OP_GET)
        assert len(pkt) == 4
        assert pkt[3] == 0  # zero-length payload

    def test_operator_masking(self):
        # Flags byte should only use lower 4 bits for operator
        pkt = bmap_packet(0, 0, 0x0F)
        assert pkt[2] == 0x0F
        pkt = bmap_packet(0, 0, 0x10)  # Overflow should be masked
        assert pkt[2] == 0x00


class TestParseResponse:
    def test_basic(self):
        data = bytes([31, 3, 0x06, 1, 0x00])  # RESULT
        resp = parse_response(data)
        assert resp is not None
        assert resp.fblock == 31
        assert resp.func == 3
        assert resp.op == 6  # OP_RESULT
        assert resp.payload == bytes([0x00])

    def test_error_response(self):
        data = bytes([1, 5, 0x04, 1, 0x05])  # ERROR: auth required
        resp = parse_response(data)
        assert resp.op == OP_ERROR
        assert resp.payload[0] == 5

    def test_too_short(self):
        assert parse_response(bytes([1, 2])) is None
        assert parse_response(bytes([1, 2, 3])) is None
        assert parse_response(bytes()) is None

    def test_status_with_payload(self):
        payload = bytes([0x50, 0xff, 0xff, 0x00])  # Battery STATUS
        data = bytes([2, 2, 0x03, len(payload)]) + payload
        resp = parse_response(data)
        assert resp.op == OP_STATUS
        assert resp.payload == payload

    def test_returns_namedtuple(self):
        data = bytes([2, 2, 0x03, 1, 0x50])
        resp = parse_response(data)
        assert isinstance(resp, BmapResponse)
        assert resp.fblock == 2


class TestParseAllResponses:
    def test_single_packet(self):
        data = bytes([31, 3, 0x06, 1, 0x00])
        responses = parse_all_responses(data)
        assert len(responses) == 1
        assert responses[0].fblock == 31

    def test_concatenated_packets(self):
        # Two packets back-to-back
        pkt1 = bytes([31, 6, 0x03, 2, 0xAA, 0xBB])
        pkt2 = bytes([31, 3, 0x06, 1, 0x00])
        data = pkt1 + pkt2
        responses = parse_all_responses(data)
        assert len(responses) == 2
        assert responses[0].func == 6
        assert responses[0].payload == bytes([0xAA, 0xBB])
        assert responses[1].func == 3
        assert responses[1].payload == bytes([0x00])

    def test_empty_data(self):
        assert parse_all_responses(bytes()) == []
        assert parse_all_responses(bytes([1, 2, 3])) == []


class TestFmtResponse:
    def test_result(self):
        resp = BmapResponse(31, 3, 6, bytes([0x00]))
        s = fmt_response(resp)
        assert "[31.3]" in s
        assert "RESULT" in s

    def test_error(self):
        resp = BmapResponse(1, 5, 4, bytes([0x05]))
        s = fmt_response(resp)
        assert "ERROR" in s
        assert "auth" in s.lower()

    def test_error_invalid_transition(self):
        resp = BmapResponse(3, 2, 4, bytes([0x0F]))
        s = fmt_response(resp)
        assert "ERROR" in s
        assert "InvalidTransition" in s

    def test_status(self):
        resp = BmapResponse(2, 2, 3, bytes([0x50]))
        s = fmt_response(resp)
        assert "STATUS" in s


class TestEncodeModeName:
    def test_basic(self):
        result = encode_mode_name("Custom")
        assert len(result) == 32
        assert result[:6] == b"Custom"
        assert result[6] == 0

    def test_empty(self):
        result = encode_mode_name("")
        assert len(result) == 32
        assert result[0] == 0

    def test_truncation(self):
        long_name = "A" * 50
        result = encode_mode_name(long_name)
        assert len(result) == 32
        assert result[31] == 0  # null terminator at end

    def test_utf8(self):
        result = encode_mode_name("Caf\u00e9")
        assert len(result) == 32
        assert result[:5] == "Caf\u00e9".encode("utf-8")
