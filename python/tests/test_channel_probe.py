"""Tests for RFCOMM channel fallback in pybmap.connect()."""

import pytest

import pybmap
from pybmap.constants import OP_STATUS, OP_PROCESSING, OP_ERROR
from pybmap.errors import (
    BmapConnectionError, BmapTimeoutError, BmapDeviceError,
    BmapInvalidArgError,
)
from pybmap.devices import qc_prince
from tests.test_connection import MockTransport


class FakeTransportFactory:
    """Stands in for RfcommTransport; per-channel behaviour is scripted."""

    def __init__(self, behaviour):
        # channel -> "busy" | "silent" | "bmap"
        self.behaviour = behaviour
        self.attempts = []
        self.closed = []

    def __call__(self, mac, channel=2, timeout=3.0):
        factory = self
        kind = self.behaviour.get(channel, "busy")

        class T(MockTransport):
            def __init__(t):
                super().__init__()
                t.channel = channel
                if kind == "bmap":
                    t.add_response(0, 5, OP_STATUS, b"1.0.6-80+f5f219b")

            def connect(t):
                factory.attempts.append(channel)
                if kind == "busy":
                    raise BmapConnectionError("[Errno 16] Device or resource busy")

            def send_recv(t, packet, drain=False):
                if kind == "silent":
                    raise BmapTimeoutError("No response from device")
                if kind == "chatty":
                    return b"ERROR\r\n"  # an HFP AG answering garbage
                return super().send_recv(packet, drain)

            def close(t):
                factory.closed.append(channel)
                super().close()

        return T()


@pytest.fixture
def patch_transport(monkeypatch):
    def apply(behaviour):
        factory = FakeTransportFactory(behaviour)
        monkeypatch.setattr(pybmap, "RfcommTransport", factory)
        return factory
    return apply


def test_configured_channel_used_without_probe(patch_transport):
    f = patch_transport({8: "bmap"})
    dev = pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_prince")
    assert f.attempts == [8]
    assert dev._transport.channel == 8
    assert dev._transport.sent == []  # no probe GET on the configured channel


def test_busy_configured_channel_falls_through_to_bmap_channel(patch_transport):
    f = patch_transport({8: "busy", 2: "silent", 9: "bmap"})
    dev = pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_prince")
    assert f.attempts == [8, 2, 9]
    assert f.closed == [2]  # silent channel released
    assert dev._transport.channel == 9


def test_non_bmap_reply_is_not_accepted(patch_transport):
    f = patch_transport({8: "busy", 2: "chatty", 9: "bmap"})
    dev = pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_prince")
    assert f.closed == [2]
    assert dev._transport.channel == 9


def test_all_channels_fail_reports_first_error(patch_transport):
    patch_transport({})
    with pytest.raises(BmapConnectionError) as ei:
        pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_prince")
    assert "tried 8, 2, 9" in str(ei.value)
    assert "resource busy" in str(ei.value)


def test_fallback_order_skips_duplicate_of_configured(patch_transport):
    f = patch_transport({2: "busy", 8: "busy", 9: "busy"})
    with pytest.raises(BmapConnectionError):
        pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_ultra2")
    assert f.attempts == [2, 8, 9]


@pytest.mark.parametrize("device_type", [None, ""])
def test_explicit_mac_requires_device_type(patch_transport, device_type):
    f = patch_transport({2: "bmap"})
    with pytest.raises(BmapInvalidArgError, match="device_type is required"):
        pybmap.connect(mac="00:11:22:33:44:55", device_type=device_type)
    assert f.attempts == []


def test_empty_mac_uses_discovery(patch_transport, monkeypatch):
    f = patch_transport({2: "bmap"})
    monkeypatch.setattr(
        pybmap, "find_bmap_device",
        lambda: ("00:11:22:33:44:55", "qc_ultra2"),
    )
    dev = pybmap.connect(mac="")
    dev.close()
    assert f.attempts == [2]


class TestModeSwitchAck:
    def _dev(self, op):
        t = MockTransport()
        t.add_response(31, 3, op, b"")
        return pybmap.BmapConnection(t, qc_prince)

    def test_processing_ack_is_success(self):
        self._dev(OP_PROCESSING).set_mode("quiet")

    def test_error_still_raises(self):
        with pytest.raises(BmapDeviceError):
            self._dev(OP_ERROR).set_mode("quiet")
