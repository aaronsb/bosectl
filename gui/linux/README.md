# Bose Control for Linux

Bose Control is a Spanish-language Tkinter interface for the Python
`bosectl` CLI. It exposes device status, listening modes, EQ, profiles and
supported headphone settings. The controls available depend on the headset.

## Run from this checkout

Install Python 3.10 or later with Tkinter and pair the headset with BlueZ.
Install `pactl` (for example, `pulseaudio-utils` on Ubuntu) to use audio
restoration. Run the launcher from this directory:

```sh
./bose-gui
```

The launcher uses `bosectl` from your PATH or the root of this checkout.
Set `BOSECTL_PATH` to the full path of another Python `bosectl` executable
if needed. Run `./install-menu.sh` to add the launcher to the desktop menu.

## Restore audio

Select **Restaurar audio** to connect a single paired Bose device whose
Bluetooth name starts with “Bose” and select its PipeWire Bluetooth output.
The headset must be on and within range.

For automatic restoration with the window closed, copy the following unit
into `~/.config/systemd/user/bose-reconnect.service`. Replace the example
path with the absolute path to `bose_gui.py`.

```ini
[Unit]
Description=Bose Control audio reconnection
After=pipewire-pulse.service

[Service]
ExecStart=/usr/bin/python3 "/absolute/path/to/bosectl/gui/linux/bose_gui.py" --watch-audio
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Enable it with `systemctl --user daemon-reload` followed by
`systemctl --user enable --now bose-reconnect.service`. Use
`systemctl --user disable --now bose-reconnect.service` to turn it off.
