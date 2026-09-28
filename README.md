# bosectl

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/aaronsb/bosectl)](https://github.com/aaronsb/bosectl/releases/latest)
[![Devices](https://img.shields.io/badge/Devices-3_supported_·_39_known-green)](docs/architecture.md#device-catalog)
[![Python 3](https://img.shields.io/badge/Python-3-3572A5.svg)](python/)
[![Rust](https://img.shields.io/badge/Rust-1.70+-DEA584.svg)](rust/)
[![C++17](https://img.shields.io/badge/C++-17-f34b7d.svg)](cpp/)
[![Platform: Linux / macOS](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS-blue.svg)](#)

**Control Bose headphones from Linux and macOS — no app, no cloud, no account.**

![bosectl CLI](docs/media/screenshot.png)

Libraries in Python, Rust, and C++ implementing the Bose BMAP protocol
over Bluetooth RFCOMM. Full control over noise cancellation, EQ, spatial
audio, button mapping, profiles, and device settings through a direct
connection to the headphones.

> **This is not an exploit.** We use the BMAP protocol's standard SETGET
> operator, which the headphones accept without authentication. No keys
> are extracted, no encryption is broken, no traffic is replayed.

## Supported Devices

| Device                      | NC Control                            | EQ     | Spatial        | Profiles              | Buttons                | Status             |
| --------------------------- | ------------------------------------- | ------ | -------------- | --------------------- | ---------------------- | ------------------ |
| **QC Ultra Headphones 2**   | CNC 0-10 slider                       | 3-band | room/head      | 7 custom slots        | Shortcut remap         | Verified           |
| **QC Ultra Earbuds 2**      | CNC 0-10 (verified)                   | inherited | modes verified | inherited           | inherited              | Battery/status/modes/CNC verified (`edith`) |
| **QuietComfort Headphones** | CNC 0-10 + Wind Block via ModeConfig  | 3-band | field observed | 2 user slots observed | —                      | Verified (`prince`) |
| **QuietComfort 35 / 35 II** | ANR off/high/wind/low                 | —      | —              | —                     | Action remap (VPA/ANC) | Verified           |
| **QuietComfort Earbuds**    | CNC 0-10 via direct SETGET            | 3-band | —              | 4 fixed modes         | Remap                  | Verified (`lando`) |
| **QuietComfort 45**         | CNC 0-10 via ModeConfig               | 3-band | —              | 2 user slots          | Remap                  | Verified (`duran`) |
| **Ultra Open Earbuds**      | — (open-ear)                          | 3-band | —              | switch only           | —                      | Partial (`serena`), from device report |

### Device Roadmap

The library includes a [device catalog](docs/architecture.md#device-catalog)
of all known BMAP-capable Bose products. These are recognized by Bluetooth
product ID but don't have tested configurations yet — contributions welcome:

| Device                          | Codename  | Category   | PID      |
| ------------------------------- | --------- | ---------- | -------- |
| Noise Cancelling Headphones 700 | goodyear  | Headphones | `0x4024` |
| QuietComfort Ultra Headphones   | lonestarr | Headphones | `0x4066` |
| QuietComfort Earbuds II         | smalls    | Earbuds    | `0x4064` |
| QuietComfort Ultra Earbuds      | scotty    | Earbuds    | `0x4072` |
| SoundLink Flex                  | phelps    | Speaker    | `0xBC59` |
| SoundLink Flex 2                | mathers   | Speaker    | `0xBC61` |

Adding a new device is usually a configuration entry; devices with different
payload layouts may need a parser/builder pair.
See [Adding a New Device](docs/architecture.md#adding-a-new-device).

## Quick Start

### Library Usage

```python
import pybmap

with pybmap.connect() as dev:
    print(dev.battery())            # 80
    print(dev.name())               # "Obsidian Countess"
    dev.set_anr("high")             # QC35: full noise cancellation
    dev.set_cnc(8)                  # CNC level 0-10 (0=max ANC)
    dev.set_eq(3, 0, -2)            # Bass +3, mid flat, treble -2
    dev.set_buttons(0x10, 4, 2)     # Remap Action button to ANC
```

```rust
use bmap::connect;

let dev = connect(None, None)?;
println!("{}%", dev.battery()?);    // 80
dev.set_anr("high")?;              // QC35
dev.set_cnc(8)?;                   // CNC level 0-10 (0=max ANC)
```

```cpp
#include "bmap.h"

auto dev = bmap::connect();
std::cout << (int)dev->battery() << "%\n";
dev->set_anr("high");              // QC35
dev->set_cnc(8);                   // CNC level 0-10 (0=max ANC)
```

### CLI Usage

```bash
# Auto-detects paired Bose device
bosectl status              # Show model, battery, mode, settings
bosectl cnc 7               # Noise cancellation level (0=max ANC)
bosectl anr high            # Noise cancellation mode (QC35)
bosectl eq 3 0 -2           # EQ: bass/mid/treble
bosectl buttons set ANC     # Remap programmable button
bosectl quiet               # Switch to Quiet mode
```

When `BMAP_MAC` (or Python CLI alias `BOSE_MAC`) is set, also set
`BMAP_DEVICE` to the matching config key. Device type is auto-detected only
when the MAC address is auto-detected.

### Device Catalog API

```python
import pybmap

# Look up any known Bose device by product ID
dev = pybmap.lookup_device(0x4082)
print(dev.name)       # "QuietComfort Ultra Headphones (2nd Gen)"
print(dev.codename)   # "wolverine"

# USB/Bluetooth identification
pybmap.usb_ids(0x4082)    # (0x05A7, 0x4082)
pybmap.modalias(0x4082)   # "bluetooth:v05A7p4082d0000"

# Check support status
pybmap.is_supported(0x4082)  # True — has tested config
pybmap.is_supported(0x4075)  # True — QuietComfort Headphones (prince)
pybmap.is_supported(0x4039)  # True — QuietComfort 45 (duran)
pybmap.supported_devices()   # [wolfcastle, baywolf, duran, prince, wolverine, lando, edith, serena]
pybmap.known_devices()       # full catalog
```

## Installation

### Prerequisites

#### Linux

- **Linux** with BlueZ (standard Bluetooth stack)
- **Bluetooth** adapter (built-in or USB)
- **Bose headphones** paired via `bluetoothctl`

#### macOS

- **macOS** 10.15+
- **Bluetooth** enabled in System Settings
- **Bose headphones** paired/connected via System Settings

### Installation (Python CLI)

Run the installer for your platform. It checks prerequisites (PyObjC on macOS, a Bluetooth-capable Python on Linux) and symlinks `bosectl` into `/usr/local/bin`:

```bash
git clone https://github.com/aaronsb/bosectl.git
cd bosectl
./linux_install.sh    # or ./macOS_install.sh
```

### From Release Binaries (Linux)

```bash
# Download from GitHub releases
curl -LO https://github.com/aaronsb/bosectl/releases/latest/download/bmapctl-rust-linux-x86_64
curl -LO https://github.com/aaronsb/bosectl/releases/latest/download/SHA256SUMS
sha256sum -c SHA256SUMS
chmod +x bmapctl-rust-linux-x86_64
sudo cp bmapctl-rust-linux-x86_64 /usr/local/bin/bmapctl
```

### From crates.io (Rust, Linux)

```bash
cargo install bose-bmap   # installs the bmapctl binary
cargo add bose-bmap       # use as a library; the import is still `use bmap::`
```

### From Source

```bash
git clone https://github.com/aaronsb/bosectl.git
cd bosectl
make test          # Run all tests (Python + Rust + C++; automatically installs macOS test deps and handles missing toolchains)
make artifacts     # Build release binaries + SHA256SUMS
```

See `make help` for all targets.

### Pairing

If your headphones aren't already paired:

```bash
bluetoothctl
> scan on
> pair XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> connect XX:XX:XX:XX:XX:XX
> exit
```

`bosectl` auto-detects paired Bose devices by their BMAP service UUID —
no MAC address configuration needed, even with renamed headphones.

## Architecture

Three libraries sharing the same layered design:

```
Application → BmapConnection → Device Config → Transport → Protocol → Bluetooth RFCOMM
```

- **Protocol** — binary BMAP packet codec
- **Transport** — RFCOMM socket with drain mode for async responses
- **Device Config** — data-only description of each headphone model (addresses, parsers, quirks)
- **BmapConnection** — typed API that dispatches to the right address/parser per device
- **Catalog** — all known Bose BMAP devices with product IDs, codenames, and USB identifiers

Device differences (RFCOMM channel, init packets, feature availability) are
expressed as config data. Devices with new payload layouts can point to
device-specific parsers and builders.

Full documentation: **[docs/architecture.md](docs/architecture.md)**

## How It Works

Bose headphones speak **BMAP** (Bose Messaging and Protocol) over
Bluetooth RFCOMM. The protocol is organized into function blocks
(groups of features) and operators (read, write, action).

The key insight: while Bose gates SET (operator 0) behind cloud-mediated
ECDH authentication, **SETGET** (operator 2) and **START** (operator 5)
are unauthenticated on the Settings and AudioModes blocks. This gives
full control over every user-facing setting.

Full protocol reference: **[NOTES.md](NOTES.md)** and
**[QuietComfort Headphones notes](docs/quietcomfort-headphones-prince.md)**.

### How We Found This

1. Connected over RFCOMM, probed all channels — channel 2 (QC Ultra 2) and 8 (QC35) responded with BMAP
2. Captured Bluetooth HCI traffic while toggling settings in the Bose app
3. DNS-hijacked the cloud API and noticed mode switching still worked — the app uses START, not SET
4. Systematically tested every operator on every function block to map the auth boundary

## Project Structure

```
├── python/pybmap/       # Python library + bosectl CLI
├── rust/src/            # Rust library + bmapctl CLI
├── cpp/src/             # C++ library + bmapctl CLI
├── docs/                # Architecture guide, device docs
├── NOTES.md             # Protocol reverse engineering notes
├── Makefile             # Build, test, release across all languages
└── fixtures/            # Captured protocol data
```

## Building & Releasing

```bash
make test                       # All tests (121 Python, 63 Rust, 54 C++)
make artifacts                  # Build + strip + SHA256SUMS in dist/
make release VERSION=v0.2.0     # Test → build → gh release create
make clean                      # Remove all build artifacts
```

## License

MIT
