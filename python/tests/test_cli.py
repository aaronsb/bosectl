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
