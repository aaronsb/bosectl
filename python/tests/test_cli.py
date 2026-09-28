"""Tests for user-visible CLI output."""

import pytest

from pybmap import cli
from pybmap.cli import cmd_status
from pybmap.types import BatteryReading, DeviceStatus


class StatusDevice:
    device_info = {"name": "Bose QuietComfort Ultra Earbuds (2nd Gen)"}
    battery_components = {1: "Right", 2: "Left", 3: "Case"}

    def status(self):
        return DeviceStatus(
            battery=70,
            battery_readings=[
                BatteryReading(3, 80),
                BatteryReading(4, 70),
                BatteryReading(2, 60),
                BatteryReading(1, 50),
            ],
            mode="quiet",
            mode_idx=0,
            cnc_level=0,
            cnc_max=10,
            eq=[],
            name="edith",
            firmware="1.0.0",
            sidetone="off",
            multipoint=False,
            auto_pause=True,
            auto_answer=False,
            prompts_enabled=False,
            prompts_language="US English",
        )

    def has_feature(self, _name):
        return False


def test_status_orders_known_components_and_hides_combined(capsys):
    cmd_status(StatusDevice())
    output = capsys.readouterr().out

    assert output.index("Right") < output.index("Left") < output.index("Case")
    assert "Right        50%" in output
    assert "Left         60%" in output
    assert "Case         80%" in output
    assert "Combined" not in output


def test_device_status_preserves_old_positional_shape():
    status = DeviceStatus(
        80, "quiet", 0, 7, 10, [], "Device", "1.0.0", "off",
        False, True, False, True, "English",
    )
    assert status.mode == "quiet"
    assert status.battery_readings == ()


@pytest.mark.parametrize("device_env", [None, ""])
def test_mac_without_device_type_skips_bluetooth_hint(monkeypatch, capsys, device_env):
    monkeypatch.setattr(cli.sys, "argv", ["bosectl", "status"])
    monkeypatch.setenv("BMAP_MAC", "00:11:22:33:44:55")
    monkeypatch.delenv("BOSE_MAC", raising=False)
    if device_env is None:
        monkeypatch.delenv("BMAP_DEVICE", raising=False)
    else:
        monkeypatch.setenv("BMAP_DEVICE", device_env)
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 1
    err = capsys.readouterr().err
    assert "device_type is required" in err
    assert "Is Bluetooth on?" not in err


# ── profile set / mode fallback ─────────────────────────────────────────────

from pybmap.errors import BmapDesyncError, BmapInvalidArgError  # noqa: E402
from pybmap.types import ModeConfig  # noqa: E402


def _profile(idx, name, editable=True):
    return ModeConfig(
        mode_idx=idx, prompt="NONE", prompt_bytes=(0, 0), name=name,
        cnc_level=0, auto_cnc=False, spatial=0, wind_block=False,
        anc_toggle=False, editable=editable, configured=True,
        flags="", raw=b"",
    )


class ProfileDevice:
    """Records which profile call cmd_profile_set made."""

    def __init__(self, profiles, update_error=None, create_error=None):
        self._profiles = profiles
        self._update_error = update_error
        self._create_error = create_error
        self.calls = []

    def profiles(self):
        return self._profiles

    def update_profile(self, name, rename=None, **settings):
        self.calls.append(("update", name) if rename is None else ("update", name, rename))
        if self._update_error:
            raise self._update_error

    def create_profile(self, name, **settings):
        self.calls.append(("create", name))
        if self._create_error:
            raise self._create_error
        return 3


def test_profile_set_updates_existing(capsys):
    dev = ProfileDevice([_profile(3, "Gym")])
    cli.cmd_profile_set(dev, ["gym", "cnc=4"])
    assert dev.calls == [("update", "gym")]
    assert "Updated" in capsys.readouterr().out


def test_profile_set_creates_when_not_found(capsys):
    dev = ProfileDevice([_profile(3, "Gym")])
    cli.cmd_profile_set(dev, ["Commute"])
    assert dev.calls == [("create", "Commute")]
    assert "Created (slot 3)" in capsys.readouterr().out


def test_profile_set_preset_name_does_not_create():
    # "Aware" is listed as a preset slot: the update is refused, and that
    # refusal must not turn into a duplicate custom "Aware".
    dev = ProfileDevice([_profile(1, "Aware", editable=False)],
                        update_error=cli.BmapError("Cannot modify preset mode 'Aware'"))
    with pytest.raises(cli.BmapError, match="preset"):
        cli.cmd_profile_set(dev, ["Aware"])
    assert dev.calls == [("update", "Aware")]


def test_profile_set_preset_name_refused_by_create():
    dev = ProfileDevice([], create_error=BmapInvalidArgError("'Aware' is a preset mode name"))
    with pytest.raises(BmapInvalidArgError):
        cli.cmd_profile_set(dev, ["Aware"])


def test_profile_set_desync_does_not_create():
    dev = ProfileDevice([_profile(3, "Gym")], update_error=BmapDesyncError("out of sync"))
    with pytest.raises(BmapDesyncError):
        cli.cmd_profile_set(dev, ["Gym"])
    assert dev.calls == [("update", "Gym")]


class ModeFallbackDevice:
    preset_modes = {"quiet": {"idx": 0}}

    def __init__(self, error):
        self._error = error

    def set_mode(self, name):
        raise self._error

    def close(self):
        pass


@pytest.mark.parametrize("error, expected", [
    (cli.BmapError("Unknown mode: bogus"), "Unknown command: bogus"),
    (BmapDesyncError("Response came from [0.5], expected [31.3]"), "expected [31.3]"),
])
def test_mode_fallback_only_hides_unknown_names(monkeypatch, capsys, error, expected):
    monkeypatch.setattr(cli.sys, "argv", ["bosectl", "bogus"])
    monkeypatch.setattr(cli.pybmap, "connect", lambda **kw: ModeFallbackDevice(error))
    with pytest.raises(SystemExit):
        cli.main()
    assert expected in capsys.readouterr().err


def test_profile_set_rename_reaches_update():
    dev = ProfileDevice([_profile(3, "Gym")])
    cli.cmd_profile_set(dev, ["Gym", "name=Run"])
    assert dev.calls == [("update", "Gym", "Run")]


def test_busy_connect_skips_bluetooth_hint(monkeypatch, capsys):
    from pybmap.errors import BmapBusyError
    monkeypatch.setattr(cli.sys, "argv", ["bosectl", "status"])

    def busy(**_kwargs):
        raise BmapBusyError("Headphones busy (another connection is still closing); "
                            "try again in a few seconds")
    monkeypatch.setattr(cli.pybmap, "connect", busy)
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 1
    err = capsys.readouterr().err
    assert "Headphones busy" in err
    assert "Is Bluetooth on?" not in err
