"""Tests for the Noise Cancelling Headphones 700 configuration.

Payloads are real replies from a 700 on firmware 1.8.2-11524+e0f7590.
"""

import sys

import pytest

import pybmap
from pybmap.catalog import CATALOG
from pybmap.connection import BmapConnection
from pybmap.errors import BmapError, BmapInvalidArgError
from pybmap.constants import OP_STATUS
from pybmap.devices import nc700, parsers, DEVICES, PRODUCT_IDS
from pybmap.protocol import bmap_packet
from tests.test_channel_probe import patch_transport, sleeps  # noqa: F401 (fixtures)
from tests.test_connection import MockTransport


class TestNC700Config:
    def test_registered(self):
        assert DEVICES["nc700"] is nc700
        assert PRODUCT_IDS[0x4024] == "nc700"
        assert CATALOG[0x4024].config == "nc700"

    def test_device_info(self):
        assert nc700.DEVICE_INFO["product_id"] == 0x4024
        assert nc700.DEVICE_INFO["codename"] == "goodyear"

    def test_channel_8_without_init_packet(self):
        assert nc700.RFCOMM_CHANNEL == 8
        assert nc700.INIT_PACKET is None

    def test_no_audio_modes(self):
        assert nc700.PRESET_MODES == {}
        assert "current_mode" not in nc700.FEATURES
        assert "audio_settings" not in nc700.FEATURES

    def test_cnc_is_writable_through_1_5(self):
        cnc = nc700.FEATURES["cnc"]
        assert cnc["addr"] == (1, 5)
        assert cnc["builder"] is parsers.build_cnc

    def test_notifications_payload_matches_bose_app(self):
        assert nc700.NOTIFICATIONS == bytes.fromhex("0100050237")


class TestNC700Payloads:
    def test_battery(self):
        assert parsers.parse_battery(bytes.fromhex("4202d800")) == 66

    def test_firmware(self):
        payload = b"1.8.2-11524+e0f7590"
        assert parsers.parse_firmware(payload) == "1.8.2-11524+e0f7590"

    def test_product_name(self):
        assert parsers.parse_product_name(bytes.fromhex("004e4320373030")) == "NC 700"

    def test_cnc_step_0_of_10(self):
        assert parsers.parse_cnc(bytes.fromhex("0b0001")) == (0, 10)

    def test_eq_three_flat_bands(self):
        bands = parsers.parse_eq(bytes.fromhex("f60a0000f60a0001f60a0002"))
        assert [(b.name, b.min_val, b.max_val, b.current) for b in bands] == [
            ("Bass", -10, 10, 0), ("Mid", -10, 10, 0), ("Treble", -10, 10, 0),
        ]

    def test_buttons_supported_actions_big_endian(self):
        btn = nc700.parse_buttons(bytes.fromhex("8005030001208800000080"))
        assert btn.button_name == "Shortcut"
        assert btn.event_name == "press_and_hold"
        assert btn.action_name == "BatteryLevel"
        assert btn.supported_actions == ["BatteryLevel", "ToggleWakeWord", "WindMode", "SpotifyGo"]

    def test_status_shows_supported_settings_only(self):
        assert nc700.STATUS_SUPPORTED_ONLY is True

    def test_multipoint_on(self):
        assert parsers.parse_multipoint(bytes([0x03])) is True


class TestNC700Writes:
    def test_set_cnc_sends_setget_1_5(self):
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0501"))
        BmapConnection(transport, nc700).set_cnc(5)
        assert transport.sent == [bmap_packet(1, 5, 2, bytes([5, 1]))]

    # Writes checked on the 700 with bosectl; each reply is the 700's own.
    def test_set_name_sends_the_name(self):
        transport = MockTransport()
        transport.add_response(1, 2, OP_STATUS, b"\x00Test 700")
        BmapConnection(transport, nc700).set_name("Test 700")
        assert transport.sent == [bmap_packet(1, 2, 2, b"Test 700")]

    def test_set_eq_sends_each_band(self):
        transport = MockTransport()
        transport.add_response(1, 7, OP_STATUS, bytes.fromhex("f60a0100f60a0001f60a0002"))
        BmapConnection(transport, nc700).set_eq(1, 0, 0)
        assert transport.sent == [bmap_packet(1, 7, 2, bytes([1, 0])),
                                  bmap_packet(1, 7, 2, bytes([0, 1])),
                                  bmap_packet(1, 7, 2, bytes([0, 2]))]

    def test_set_sidetone_sends_level(self):
        transport = MockTransport()
        transport.add_response(1, 11, OP_STATUS, bytes.fromhex("01030f"))
        BmapConnection(transport, nc700).set_sidetone("low")
        assert transport.sent == [bmap_packet(1, 11, 2, bytes([1, 3]))]

    def test_multipoint_write_is_refused_before_sending(self):
        transport = MockTransport()
        with pytest.raises(BmapError, match="does not write it yet"):
            BmapConnection(transport, nc700).set_multipoint(True)
        assert transport.sent == []


class TestNC700Names:
    """The Bose app's name check. The owner of a 700 tried these in the Bose app:
    27 digits were too long, and so were 14 "é" (28 bytes).
    In a separate test, the Bose app refused a name with an emoji."""

    @pytest.mark.parametrize("name", [
        "1" * 26,
        "\u00e9" * 13,
        "User's NC-700",
        "User\u2019s NC-700",
    ], ids=["26 digits", "13 e-acute", "apostrophe", "curly apostrophe"])
    def test_accepted(self, name):
        transport = MockTransport()
        transport.add_response(1, 2, OP_STATUS, b"\x00" + name.encode("utf-8"))
        BmapConnection(transport, nc700).set_name(name)
        assert transport.sent == [bmap_packet(1, 2, 2, name.encode("utf-8"))]

    @pytest.mark.parametrize("name, problem", [
        ("1" * 27, "at most 26 bytes"),
        ("\u00e9" * 14, "at most 26 bytes"),
        ("\U0001F601", "letters, digits"),
        ("Mine!", "letters, digits"),
        ("a\tb", "letters, digits"),
        ("\u65e5\u672c", "letters, digits"),
        ("   ", "empty"),
        ("", "empty"),
    ], ids=["27 digits", "14 e-acute", "emoji", "exclamation", "tab", "outside the subset", "spaces only", "empty"])
    def test_refused_before_sending(self, name, problem):
        transport = MockTransport()
        with pytest.raises(BmapInvalidArgError, match=problem):
            BmapConnection(transport, nc700).set_name(name)
        assert transport.sent == []

    def test_other_devices_keep_31_bytes_and_any_character(self):
        from pybmap.devices import qc_ultra2
        transport = MockTransport()
        transport.add_response(1, 2, OP_STATUS, b"\x00Party! #1")
        BmapConnection(transport, qc_ultra2).set_name("Party! #1")
        assert transport.sent == [bmap_packet(1, 2, 2, b"Party! #1")]


class TestNotificationsOnConnect:
    def test_nc700_enables_notifications(self, patch_transport):  # noqa: F811
        patch_transport({8: "bmap"})
        dev = pybmap.connect(mac="00:11:22:33:44:55", device_type="nc700")
        assert dev._transport.sent == [bmap_packet(9, 2, 2, nc700.NOTIFICATIONS)]

    def test_failed_notifications_close_the_channel(self, patch_transport, monkeypatch):  # noqa: F811
        f = patch_transport({8: "bmap"})

        def fail(transport, device):
            raise BmapError("no reply to [9.2]")
        monkeypatch.setattr(pybmap, "_enable_notifications", fail)
        with pytest.raises(BmapError, match=r"\[9\.2\]"):
            pybmap.connect(mac="00:11:22:33:44:55", device_type="nc700")
        assert f.closed == [8]

    def test_other_devices_send_nothing_extra(self, patch_transport):  # noqa: F811
        patch_transport({8: "bmap"})
        dev = pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_prince")
        assert dev._transport.sent == []


@pytest.mark.skipif(sys.platform == "darwin", reason="Linux bluetoothctl discovery")
def test_discovery_detects_nc700_from_modalias():
    # Modalias line as reported for a NC 700 in issue #48.
    from pybmap.discovery import _detect_device_type
    info = "Name: LE-NC 700\n\tModalias: bluetooth:v009Ep4024d0182\n"
    assert _detect_device_type(info) == "nc700"
