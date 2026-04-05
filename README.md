# bosectl — Control Bose QC Ultra 2 from Linux

![bosectl CLI](docs/media/screenshot.png)

Control your Bose QC Ultra 2 headphones directly over Bluetooth — no Bose app,
no Bose account, no cloud, no phone required.

This is a reverse-engineered implementation of the Bose BMAP protocol that gives
you full control over noise cancellation, EQ, spatial audio, device settings, and
more. Everything runs over a local Bluetooth RFCOMM connection to the headphones.

## What you can do

```
$ ./bosectl status
Battery:    70%
Mode:       quiet
CNC:        7/10
EQ:         +3/+0/-2
Name:       Fargo
FW:         8.2.20+g34cf029
Sidetone:   medium
Multipoint: on
AutoPause:  on
Prompts:    off (US English)

$ ./bosectl cnc 8          # Set noise cancellation level (0-10)
$ ./bosectl eq 5 0 -3      # Set EQ: bass=+5, mid=0, treble=-3
$ ./bosectl spatial head    # Spatial audio with head tracking
$ ./bosectl quiet           # Switch to Quiet (full ANC) mode
$ ./bosectl name "My Cans"  # Rename your headphones (any UTF-8 string)
```

### Full command list

| Command | Description |
|---------|-------------|
| `quiet` `aware` `immersion` `cinema` `home` | Switch audio mode |
| `cnc <0-10>` | Set noise cancellation level |
| `eq <bass> <mid> <treble>` | Set EQ (-10 to +10 each) |
| `eq flat` | Reset EQ to 0/0/0 |
| `spatial <off\|room\|head>` | Spatial audio mode |
| `name [text]` | Get/set device name |
| `sidetone <off\|low\|medium\|high>` | Sidetone level |
| `multipoint <on\|off>` | Toggle multipoint connection |
| `autopause <on\|off>` | Auto play/pause on ear removal |
| `autoanswer <on\|off>` | Auto-answer incoming calls |
| `prompts <on\|off>` | Toggle voice prompts |
| `pair` | Enter Bluetooth pairing mode |
| `off` | Power off headphones |
| `status` | Show all current settings |
| `battery` | Battery percentage (just the number) |
| `current` | Current mode name (just the word) |
| `buttons` | Show button mapping |
| `dump` | Dump all AudioModes state |
| `raw <hex>` | Send raw BMAP packet |

## Requirements

- Linux with BlueZ (Bluetooth stack)
- Python 3 (no external dependencies)
- Bose QC Ultra 2 paired via `bluetoothctl`

## Setup

1. Pair your headphones normally via `bluetoothctl`:
   ```
   bluetoothctl
   > scan on
   > pair XX:XX:XX:XX:XX:XX
   > trust XX:XX:XX:XX:XX:XX
   > connect XX:XX:XX:XX:XX:XX
   ```

2. Edit the `BOSE_MAC` variable in `bose` to match your headphones' MAC address.

3. Run:
   ```
   chmod +x bose
   ./bosectl status
   ```

No Bose app installation, Bose account, or internet connection needed.

## How it works

Bose headphones speak a protocol called **BMAP** (Bose Messaging and Protocol)
over Bluetooth SPP/RFCOMM channel 2. Every setting — ANC mode, EQ, device name,
button mapping — is read and written via BMAP packets.

### BMAP packet format

```
[fblock_id, function_id, flags, payload_length, ...payload]

flags byte: (device_id << 6) | (port_num << 4) | (operator & 0x0F)
```

The protocol is organized into **function blocks** (groups of related features)
and **operators** (what you want to do):

| Operator | ID | Description |
|----------|----|-------------|
| SET | 0 | Write a value (persistent) |
| GET | 1 | Read a value |
| SETGET | 2 | Write + read back |
| STATUS | 3 | Unsolicited state notification |
| ERROR | 4 | Error response |
| START | 5 | Trigger an action |
| RESULT | 6 | Action completed |

### The authentication gap

Bose protects write operations behind cloud-mediated ECDH P-384 authentication.
When the app wants to change a setting, the headphones issue a challenge, the app
forwards it to Bose's cloud servers (`nadc.data.api.bose.io`), Bose signs it, and
the app relays the response back. Only then do the headphones accept SET commands.

**But Bose didn't gate every operator.** Through protocol analysis, we found three
gaps in the authentication policy:

1. **START on AudioModes (block 31) is unauthenticated.** This is the operator
   the app uses for real-time mode switching. It lets us switch between Quiet,
   Aware, Immersion, Cinema, and custom modes instantly.

2. **SETGET on AudioModes is unauthenticated.** While SET requires auth, SETGET
   (write-and-read-back) does not. Custom mode slots (indices 5-10) accept full
   configuration: CNC level, spatial audio, wind block, ANC toggle, and mode name.
   Preset modes (0-3) are firmware-locked regardless of auth.

3. **SETGET on Settings (block 1) is unauthenticated.** The entire Settings block
   — EQ, device name, sidetone, multipoint, auto play/pause, button mapping — accepts
   SETGET without auth. Only CNC level [1.5] on the Settings block requires auth
   (but we bypass that through AudioModes).

The net result: everything the Bose app can do, we can do without the app.

## How we found this

### Bluetooth exploration

We connected to the headphones over RFCOMM and probed all channels (1-30).
Channel 2 responded with BMAP protocol data. We enumerated all function blocks
and functions by sending GET requests and observing which ones returned STATUS
vs ERROR responses.

### Traffic interception

To understand what the app sends when you toggle a setting, we captured Bluetooth
traffic via Android's HCI snoop log and `btsnoop`. We wrote `bmap-capture.py` to
automate before/after snapshots — it reads every known function, waits while you
change a setting in the app, reads again, and diffs. The `captures/` directory
contains the raw data from these sessions.

### Cloud API analysis

We intercepted the app's HTTPS traffic to understand the authentication flow. The
app communicates with `nadc.data.api.bose.io` using QUIC/HTTP3 (falling back to
HTTPS) and performs an ECDH key exchange signed by Bose's servers. The headphones
won't accept SET commands without this cloud signature.

The breakthrough came when we noticed the app could still toggle ANC modes even
with the cloud API DNS-hijacked. Diffing all BMAP traffic before and after revealed
that the app was using START on block 31 (AudioModes), not SET on block 1
(Settings). The START operator had no authentication check.

### Systematic operator testing

Once we understood the auth gap on START, we systematically tested every operator
on every function. This revealed that SETGET was also unauthenticated on both the
AudioModes and Settings blocks — a much larger hole than just START.

## Protocol reference

Full protocol documentation is in [NOTES.md](NOTES.md), including:
- Complete function block map (blocks 0-31)
- All Settings functions and their payload formats
- ModeConfig SETGET payload structure (40 bytes)
- Button remapping protocol (IDs, events, action modes)
- Voice prompt language codes
- Authentication system details (ECDH P-384, cloud endpoints)
- BMAP error codes

## Compatibility

Tested on:
- **Bose QC Ultra 2 HP** (codename "wolverine", QCC-384 platform)
- Firmware 8.2.20

The BMAP protocol is shared across Bose's Bluetooth product line. Other models
(QC 45, QC Ultra Earbuds, NC 700, etc.) likely use similar function blocks with
the same authentication gaps, but the specific function IDs and payload formats
may differ.

## Tools included

| File | Description |
|------|-------------|
| `bosectl` | CLI tool for controlling headphones |
| `bmap-capture.py` | Interactive capture tool — snapshots all BMAP state before/after a setting change |
| `captures/` | Raw capture data from setting toggle experiments |
| `NOTES.md` | Full protocol documentation and reverse engineering notes |

## License

MIT
