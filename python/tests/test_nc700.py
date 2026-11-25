"""Tests for the Noise Cancelling Headphones 700 configuration.

Payloads are real replies from a 700 on firmware 1.8.2-11524+e0f7590.
"""

import sys

import pytest

import pybmap
from pybmap.catalog import CATALOG
from pybmap.connection import BmapConnection
from pybmap.errors import BmapError
from pybmap.constants import OP_STATUS
from pybmap.devices import nc700, parsers, qc35, qc_earbuds, ultra_open, DEVICES, PRODUCT_IDS
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

    def test_buttons_remap_writes_button_event_action(self):
        transport = MockTransport()
        transport.add_response(1, 9, OP_STATUS, bytes.fromhex("8005070001208800000080"))
        btn = BmapConnection(transport, nc700).set_buttons(0x80, 5, "ToggleWakeWord")
        assert transport.sent == [bmap_packet(1, 9, 2, bytes([0x80, 5, 7]))]
        assert btn.action_name == "ToggleWakeWord"

    def test_status_shows_supported_settings_only(self):
        assert nc700.STATUS_SUPPORTED_ONLY is True

    def test_multipoint_on(self):
        assert parsers.parse_multipoint(bytes([0x03])) is True


class TestNC700Writes:
    def test_set_cnc_sends_setget_1_5(self):
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0501"))
        BmapConnection(transport, nc700).set_cnc(5)
        assert transport.sent == [bmap_packet(1, 5, 1), bmap_packet(1, 5, 2, bytes([5, 1]))]

    def test_set_cnc_with_anc_off_keeps_anc_off(self):
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0200"))
        BmapConnection(transport, nc700).set_cnc(4)
        assert transport.sent == [
            bmap_packet(1, 5, 1),
            bmap_packet(1, 5, 2, bytes([4, 1])),  # on: recalls the preset
            bmap_packet(1, 5, 2, bytes([4, 1])),  # the step, while on
            bmap_packet(1, 5, 2, bytes([4, 0])),  # off again
        ]

    def test_anc_state_is_the_cnc_enabled_byte(self):
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0300"))
        settings = BmapConnection(transport, nc700).audio_settings()
        assert (settings.cnc_level, settings.anc_toggle) == (3, False)

    def test_anc_state_masks_flags_bit_0(self):
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0502"))
        assert BmapConnection(transport, nc700).audio_settings().anc_toggle is False

    @pytest.mark.parametrize("enabled, flag", [(True, 1), (False, 0)])
    def test_set_anc_writes_current_step_and_flag(self, enabled, flag):
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0301"))
        BmapConnection(transport, nc700).set_anc(enabled)
        assert transport.sent == [bmap_packet(1, 5, 1), bmap_packet(1, 5, 2, bytes([3, flag]))]

    def test_set_anc_on_from_off_keeps_the_step(self):
        # On hardware, [4, 1] with ANC off answered 0b 03 01: switching on
        # recalled preset 0 (step 3) instead of step 4.
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0400"))
        BmapConnection(transport, nc700).set_anc(True)
        assert transport.sent == [
            bmap_packet(1, 5, 1),
            bmap_packet(1, 5, 2, bytes([4, 1])),  # on: recalls the preset
            bmap_packet(1, 5, 2, bytes([4, 1])),  # the step, while on
        ]

    def test_set_anc_off_from_off_writes_once(self):
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0400"))
        BmapConnection(transport, nc700).set_anc(False)
        assert transport.sent == [bmap_packet(1, 5, 1), bmap_packet(1, 5, 2, bytes([4, 0]))]

    def test_set_cnc_presets_with_anc_on_selects_current_step(self):
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0501"))
        transport.add_response(1, 15, OP_STATUS, bytes.fromhex("0100050a"))
        BmapConnection(transport, nc700).set_cnc_presets(0, 5, 10)
        assert transport.sent == [
            bmap_packet(1, 5, 1),
            bmap_packet(1, 15, 2, bytes([1, 0, 5, 10])),
            bmap_packet(1, 5, 2, bytes([5, 1])),
        ]

    def test_set_cnc_presets_restores_anc_off_when_the_write_fails(self):
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0200"))
        # no [1.15] response: the mock answers ERROR FuncNotSupp
        with pytest.raises(BmapError):
            BmapConnection(transport, nc700).set_cnc_presets(0, 5, 10)
        assert transport.sent[-2:] == [
            bmap_packet(1, 5, 2, bytes([2, 1])),
            bmap_packet(1, 5, 2, bytes([2, 0])),
        ]

    def test_set_cnc_presets_reports_the_write_error_when_restoring_fails(self):
        class FailingSetGet(MockTransport):
            def send_recv(self, packet, drain=False):
                if packet[:3] == bytes([1, 5, 2]):  # every [1.5] SETGET fails
                    self.sent.append(packet)
                    return bytes([1, 5, 4, 1, 6])  # ERROR InvalidData
                return super().send_recv(packet, drain)

        transport = FailingSetGet()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0501"))
        # no [1.15] response: the mock answers ERROR FuncNotSupp (4)
        with pytest.raises(BmapError) as raised:
            BmapConnection(transport, nc700).set_cnc_presets(0, 5, 10)
        assert raised.value.error_code == 4
        assert transport.sent[-1] == bmap_packet(1, 5, 2, bytes([5, 1]))

    def test_set_cnc_presets_restores_anc_off_on_ctrl_c(self):
        class Interrupted(MockTransport):
            def send_recv(self, packet, drain=False):
                if packet[:2] == bytes([1, 15]):
                    raise KeyboardInterrupt
                return super().send_recv(packet, drain)

        transport = Interrupted()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0200"))
        with pytest.raises(KeyboardInterrupt):
            BmapConnection(transport, nc700).set_cnc_presets(0, 5, 10)
        assert transport.sent[-2:] == [
            bmap_packet(1, 5, 2, bytes([2, 1])),
            bmap_packet(1, 5, 2, bytes([2, 0])),
        ]

    def test_set_cnc_presets_refuses_out_of_range_before_sending(self):
        transport = MockTransport()
        with pytest.raises(ValueError):
            BmapConnection(transport, nc700).set_cnc_presets(0, 5, 11)
        assert transport.sent == []

    def test_cnc_presets_and_persist_read(self):
        transport = MockTransport()
        transport.add_response(1, 15, OP_STATUS, bytes.fromhex("00030409"))
        transport.add_response(1, 14, OP_STATUS, bytes.fromhex("00"))
        dev = BmapConnection(transport, nc700)
        assert dev.cnc_presets() == [3, 4, 9]
        assert dev.cnc_persist() is False

    def test_set_cnc_persist(self):
        transport = MockTransport()
        transport.add_response(1, 14, OP_STATUS, bytes.fromhex("01"))
        BmapConnection(transport, nc700).set_cnc_persist(True)
        assert transport.sent == [bmap_packet(1, 14, 2, bytes([1]))]

    @pytest.mark.parametrize("write", [
        lambda dev: dev.set_name("Desk"),
        lambda dev: dev.set_multipoint(True),
        lambda dev: dev.set_sidetone("low"),
    ], ids=["name", "multipoint", "sidetone"])
    def test_unchecked_writes_are_refused_before_sending(self, write):
        transport = MockTransport()
        with pytest.raises(BmapError, match="does not write it yet"):
            write(BmapConnection(transport, nc700))
        assert transport.sent == []

    def test_set_cnc_presets_refuses_read_only_before_sending(self, monkeypatch):
        features = dict(nc700.FEATURES)
        features["cnc_presets"] = dict(features["cnc_presets"], read_only=True)
        monkeypatch.setattr(nc700, "FEATURES", features)
        transport = MockTransport()
        transport.add_response(1, 5, OP_STATUS, bytes.fromhex("0b0200"))
        with pytest.raises(BmapError, match="does not write it yet"):
            BmapConnection(transport, nc700).set_cnc_presets(0, 5, 10)
        assert transport.sent == []


class TestAncInCncStaysOnTheNC700:
    """Devices without ANC_IN_CNC keep their ModeConfig path for ANC."""

    @pytest.mark.parametrize("device", [ultra_open, qc35, qc_earbuds],
                             ids=["ultra_open", "qc35", "qc_earbuds"])
    @pytest.mark.parametrize("call", [
        lambda dev: dev.set_anc(True),
        lambda dev: dev.audio_settings(),
    ], ids=["set_anc", "audio_settings"])
    def test_other_devices_do_not_read_cnc_for_anc(self, device, call):
        transport = MockTransport()
        with pytest.raises(BmapError) as raised:
            call(BmapConnection(transport, device))
        assert "'cnc'" not in str(raised.value)
        assert bmap_packet(1, 5, 1) not in transport.sent


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
