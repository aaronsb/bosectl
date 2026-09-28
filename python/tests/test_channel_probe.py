"""Tests for RFCOMM channel fallback in pybmap.connect()."""

import errno

import pytest

import pybmap
from pybmap.constants import OP_STATUS, OP_PROCESSING, OP_ERROR
from pybmap.errors import (
    BmapConnectionError, BmapTimeoutError, BmapDeviceError,
    BmapInvalidArgError, BmapBusyError,
)
from pybmap.devices import qc_prince
from tests.test_connection import MockTransport


# Scripted connect failures that carry an errno, as the Linux transport does.
OS_ERRORS = {
    "ebusy": errno.EBUSY,
    "refused": errno.ECONNREFUSED,
    "hostdown": errno.EHOSTDOWN,
}


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
        if isinstance(kind, list):
            # One entry per connect attempt; the last one repeats.
            kind = kind.pop(0) if len(kind) > 1 else kind[0]

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
                if kind in OS_ERRORS:
                    code = OS_ERRORS[kind]
                    raise BmapConnectionError(
                        "Failed to connect: [Errno %d] %s" % (code, errno.errorcode[code]),
                        errno=code,
                    )

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
def sleeps(monkeypatch):
    """Record backoff delays instead of sleeping."""
    calls = []
    monkeypatch.setattr(pybmap, "_sleep", calls.append)
    return calls


@pytest.fixture
def patch_transport(monkeypatch, sleeps):
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


# ── EBUSY / ECONNREFUSED backoff (issue #39) ────────────────────────────────

def test_ebusy_twice_then_success_stays_on_channel(patch_transport, sleeps):
    f = patch_transport({2: ["ebusy", "ebusy", "bmap"]})
    dev = pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_ultra2")
    assert f.attempts == [2, 2, 2]
    assert sleeps == [0.5, 1.0]
    assert dev._transport.channel == 2


def test_ebusy_forever_reports_busy(patch_transport, sleeps):
    f = patch_transport({2: ["ebusy"], 8: ["ebusy"], 9: ["ebusy"]})
    with pytest.raises(BmapBusyError) as ei:
        pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_ultra2")
    # One try plus three retries per channel, three sleeps per channel.
    assert f.attempts == [2] * 4 + [8] * 4 + [9] * 4
    assert sleeps == [0.5, 1.0, 2.0] * 3
    msg = str(ei.value)
    assert "Headphones busy" in msg
    assert "No BMAP channel found" not in msg
    assert "EBUSY" in msg  # underlying error kept for callers that match on it
    assert ei.value.errno == errno.EBUSY


def test_busy_on_configured_channel_wins_over_other_errors(patch_transport, sleeps):
    patch_transport({2: ["ebusy"], 8: ["hostdown"], 9: ["refused"]})
    with pytest.raises(BmapBusyError):
        pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_ultra2")
    assert sleeps == [0.5, 1.0, 2.0] + [0.5, 1.0, 2.0]  # channels 2 and 9


def test_econnrefused_then_success(patch_transport, sleeps):
    f = patch_transport({2: ["refused", "bmap"]})
    dev = pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_ultra2")
    assert f.attempts == [2, 2]
    assert sleeps == [0.5]
    assert dev._transport.channel == 2


def test_econnrefused_forever_is_not_reported_as_busy(patch_transport, sleeps):
    patch_transport({2: ["refused"], 8: ["refused"], 9: ["refused"]})
    with pytest.raises(BmapConnectionError) as ei:
        pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_ultra2")
    assert not isinstance(ei.value, BmapBusyError)
    assert "No BMAP channel found" in str(ei.value)
    assert sleeps == [0.5, 1.0, 2.0] * 3


def test_non_retryable_error_moves_on_without_sleep(patch_transport, sleeps):
    f = patch_transport({2: ["hostdown"], 8: ["bmap"]})
    dev = pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_ultra2")
    assert f.attempts == [2, 8]
    assert sleeps == []
    assert dev._transport.channel == 8


def test_error_without_errno_is_not_retried(patch_transport, sleeps):
    f = patch_transport({2: "busy", 8: "busy", 9: "busy"})
    with pytest.raises(BmapConnectionError) as ei:
        pybmap.connect(mac="00:11:22:33:44:55", device_type="qc_ultra2")
    assert not isinstance(ei.value, BmapBusyError)
    assert f.attempts == [2, 8, 9]
    assert sleeps == []


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
