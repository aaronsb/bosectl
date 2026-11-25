"""Conformance adapter: drives pybmap for conformance/run.py.

Reads requests on stdin and answers on stdout, one line each, as
conformance/INTERFACE.md describes. The library talks to a stdio transport
instead of Bluetooth, so the runner plays the headphones' side. Run it as
``python -m pybmap.replay``.

The adapter holds no device knowledge: it maps call names to library methods
and formats what they return.
"""

import sys

from .connection import BmapConnection
from .devices import DEVICES
from .errors import (BmapAuthError, BmapDesyncError, BmapDeviceError,
                     BmapInvalidArgError, BmapTimeoutError, BmapUnsupportedError)
from .transport import RFCOMM_CHANNEL


class _Reply(Exception):
    """An answer line to print instead of a call's result."""


class StdioTransport:
    """A transport whose far end is the conformance runner.

    sends counts the packets sent, so the adapter can tell an argument the
    library refused up front from a failure after it had sent something.
    """

    sends = 0

    def send_recv(self, packet, drain=False):
        self.sends += 1
        _write("%s %s" % ("send-drain" if drain else "send", bytes(packet).hex()))
        line = sys.stdin.readline().rstrip("\n")
        if line == "timeout":
            raise BmapTimeoutError("timeout from the conformance runner")
        word, _, hex_bytes = line.partition(" ")
        if word != "recv":
            raise _Reply("err other expected recv or timeout, got %r" % line)
        return bytes.fromhex(hex_bytes)

    def close(self):
        pass


def _write(line):
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _on_off(value):
    return "on" if value else "off"


def _flag(arg):
    if arg not in ("on", "off"):
        raise BmapInvalidArgError("expected on or off, got %r" % arg)
    return arg == "on"


def _eq(bands):
    return " ".join(str(b.current) for b in sorted(bands, key=lambda b: b.band_id))


# Each getter: (library call, formatter of its result).
CALLS = {
    "battery": (lambda d: d.battery(), str),
    "firmware": (lambda d: d.firmware(), str),
    "name": (lambda d: d.name(), str),
    "cnc": (lambda d: d.cnc(), lambda r: "%d/%d" % r),
    "eq": (lambda d: d.eq(), _eq),
    "multipoint": (lambda d: d.multipoint(), _on_off),
    "sidetone": (lambda d: d.sidetone(), str),
    "auto_pause": (lambda d: d.auto_pause(), _on_off),
    "auto_answer": (lambda d: d.auto_answer(), _on_off),
    "cnc_presets": (lambda d: d.cnc_presets(), lambda r: " ".join(map(str, r))),
    "cnc_persist": (lambda d: d.cnc_persist(), _on_off),
}
# Each setter: (arguments it takes, library call).
SETTERS = {
    "set_cnc": (1, lambda d, a: d.set_cnc(int(a[0]))),
    "set_eq": (3, lambda d, a: d.set_eq(int(a[0]), int(a[1]), int(a[2]))),
    "set_name": (1, lambda d, a: d.set_name(a[0])),
    "set_multipoint": (1, lambda d, a: d.set_multipoint(_flag(a[0]))),
    "set_sidetone": (1, lambda d, a: d.set_sidetone(a[0])),
    "set_auto_pause": (1, lambda d, a: d.set_auto_pause(_flag(a[0]))),
    "set_auto_answer": (1, lambda d, a: d.set_auto_answer(_flag(a[0]))),
    "set_anc": (1, lambda d, a: d.set_anc(_flag(a[0]))),
    "set_cnc_presets": (3, lambda d, a: d.set_cnc_presets(int(a[0]), int(a[1]), int(a[2]))),
    "set_cnc_persist": (1, lambda d, a: d.set_cnc_persist(_flag(a[0]))),
}


def _error_line(error, sent):
    """Map a library error to an INTERFACE.md error class.

    sent is whether the call sent any packet: pybmap raises ValueError for a
    rejected argument, so a ValueError only counts as one when the library
    raised it before sending anything.
    """
    if isinstance(error, BmapInvalidArgError):
        return "err invalid-arg"
    if isinstance(error, ValueError) and not sent:
        return "err invalid-arg"
    if isinstance(error, BmapTimeoutError):
        return "err timeout"
    if isinstance(error, BmapDesyncError):
        return "err desync"
    if isinstance(error, BmapAuthError):
        return "err device-error 5"
    if isinstance(error, BmapDeviceError):
        code = getattr(error, "error_code", None)
        return "err device-error %s" % ("-" if code is None else code)
    if isinstance(error, BmapUnsupportedError):
        return "err unsupported"
    return "err other %s: %s" % (type(error).__name__, error)


def _call(dev, words, line):
    method = words[0]
    sends_before = dev._transport.sends
    if method == "set_name":
        args = [line.split(" ", 2)[2]] if len(words) > 1 else []
    else:
        args = words[1:]
    try:
        if method in CALLS:
            get, fmt = CALLS[method]
            return "ok " + fmt(get(dev))
        if method in SETTERS:
            count, setter = SETTERS[method]
            if len(args) != count:
                return "err invalid-arg"
            setter(dev, args)
            return "ok"
        return "err unknown-request"
    except _Reply as reply:
        return str(reply)
    except Exception as error:  # every failure becomes an error class
        return _error_line(error, dev._transport.sends > sends_before)


def _describe(device):
    feats = device.FEATURES
    lines = ["channel %d" % getattr(device, "RFCOMM_CHANNEL", RFCOMM_CHANNEL)]
    init = getattr(device, "INIT_PACKET", None)
    lines.append("init %s" % ("%d.%d" % tuple(init) if init else "-"))
    notif = getattr(device, "NOTIFICATIONS", None)
    lines.append("notifications %s" % (bytes(notif).hex() if notif else "-"))
    for name, feat in feats.items():
        lines.append("feature %s %d.%d" % ((name,) + tuple(feat["addr"])))
        if feat.get("read_only"):
            lines.append("read-only %d.%d" % tuple(feat["addr"]))
    lines.append("status-supported-only %d" % bool(getattr(device, "STATUS_SUPPORTED_ONLY", False)))
    lines.append("anc-toggle %d" % bool(getattr(device, "SUPPORTS_ANC_TOGGLE", True)))
    lines.append("anc-in-cnc %d" % bool(getattr(device, "ANC_IN_CNC", False)))
    slots = list(getattr(device, "EDITABLE_SLOTS", None) or [])
    lines.append("editable-slots %s" % (" ".join(map(str, slots)) if slots else "-"))
    for name, preset in (getattr(device, "PRESET_MODES", None) or {}).items():
        lines.append("preset %s %d" % (name, preset["idx"]))
    return lines


def main():
    dev = device = None
    for raw in sys.stdin:
        line = raw.rstrip("\n")
        words = line.split(" ")
        if words[0] == "device" and len(words) == 2:
            device = DEVICES.get(words[1])
            if device is None:
                _write("err unknown-device")
                continue
            dev = BmapConnection(StdioTransport(), device)
            _write("ready")
        elif dev is None:
            _write("err unknown-request")
        elif words[0] == "call" and len(words) > 1:
            _write(_call(dev, words[1:], line))
        elif line == "describe":
            for out in _describe(device):
                _write(out)
            _write("end")
        else:
            _write("err unknown-request")
    return 0


if __name__ == "__main__":
    sys.exit(main())
