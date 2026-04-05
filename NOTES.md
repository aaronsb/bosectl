# Bose QC Ultra 2 — Reverse Engineering Notes

## TL;DR

**We can control the headphones from Linux without the Bose app, Bose account, or cloud.**

The AudioModes function block (block 31) accepts the `START` operator without
authentication. This lets us switch ANC modes, read battery, read all device info,
and more — all over a direct Bluetooth RFCOMM connection.

Bose locked down SET/SETGET operators behind cloud-mediated ECDH authentication,
but left the START operator on AudioModes wide open. This is the same operator
the app uses to change modes in real time.

## Device Info
- Product: Bose QC Ultra 2 HP (codename "wolverine")
- Platform: OTG-QCC-384 (Qualcomm QCC chipset)
- Firmware: 8.2.20+g34cf029
- BT MAC: 68:F2:1F:XX:XX:XX
- Serial: 085958TXXXXXXXXXX
- Custom name: "Fargo"
- Product ID: 0x4082, Variant: 0x01

## BMAP Protocol
- Version: 1.1.0
- Transport: Bluetooth SPP over RFCOMM channel 2
- Packet format: `[fblock_id, function_id, flags, payload_length, ...payload]`
- Flags byte: `(device_id << 6) | (port_num << 4) | (operator & 0x0F)`
- Operators: SET=0, GET=1, SET_GET=2, STATUS=3, ERROR=4, START=5, RESULT=6, PROCESSING=7

## What Works Without Authentication

### Reading (GET operator — all blocks)
Everything can be read without auth:
- Battery level, firmware version, serial number, product name
- Current ANC mode, EQ settings, connected devices
- All device info across all function blocks

### Writing — AudioModes (Block 31, START operator)

**This is the breakthrough.** The START operator on block 31 is unauthenticated.

#### Changing ANC/Audio Mode
```
Packet: [31, 3, 0x05, 2, MODE_INDEX, VOICE_PROMPT]
  - Block 31 (AudioModes), Function 3 (CurrentMode), Operator START (5)
  - MODE_INDEX: which mode to activate (see table below)
  - VOICE_PROMPT: 0=silent, 1=play voice prompt
  - Response: RESULT with the new mode index on success
```

#### Available Audio Modes
| Index | Name       | Description                    | Config byte |
|-------|------------|--------------------------------|-------------|
| 0     | Quiet      | Full active noise cancellation | 0x01        |
| 1     | Aware      | Transparency / passthrough     | 0x02        |
| 2     | Immersion  | Spatial audio immersive        | 0x22        |
| 3     | Cinema     | Spatial audio cinema           | 0x24        |
| 4     | Home       | Custom home profile            | 0x0a        |
| 5     | None       | Empty/custom slot              | 0x00        |
| 6     | None       | Empty/custom slot              | 0x00        |
| 7     | None       | Empty/custom slot              | 0x00        |

#### Other Unauthenticated START Commands (Block 31)
| Function | Name       | Notes |
|----------|------------|-------|
| [31.1]   | GetAll     | Returns PROCESSING — triggers full state dump |
| [31.3]   | CurrentMode| **Mode switching — confirmed working** |
| [31.6]   | ModeConfig | Returns PROCESSING — may allow config changes |
| [31.9]   | Reset      | Accepts START (InvalidData with empty payload) |

#### Unauthenticated START in Other Blocks
| Function | Name    | Notes |
|----------|---------|-------|
| [7.4]    | Power   | Accepts START (InvalidData — needs correct payload) |
| [18.19]  | ValidatedDeviceIdentityKeypair | Accepts public key, returns PROCESSING |

### Mode Config Details (raw data)
```
Mode 0 (Quiet):     000001000001 "Quiet"     ...00000001
Mode 1 (Aware):     0100020000014 "Aware"    ...020a0000000001
Mode 2 (Immersion): 020022000001 "Immersion" ...0002000001
Mode 3 (Cinema):    0300240000004 "Cinema"   ...0001000001
Mode 4 (Home):      04000a010100 "Home"      ...1d000000010001
Mode 5 (None):      0500000100004 "None"     ...1d0a0000010001
Mode 6 (None):      0600000100004 "None"     ...1d0a0000010001
Mode 7 (None):      0700000100004 "None"     ...1d0a0000010001
```

## What Requires Authentication (Blocked)

SET and SET_GET operators on most blocks return error 5 (OpNotSupp) without
completing cloud-mediated ECDH authentication. This includes:

- Settings.CNC [1.5] — fine-grained noise cancellation level (0-10 steps)
- Settings.ANR [1.6] — ANC level
- Settings.EQ [1.7] — equalizer adjustment
- Settings.ProductName [1.2] — device name
- Settings.Multipoint [1.10] — multipoint toggle
- Settings.StandbyTimer [1.4] — auto-off timer
- All other Settings block SET/SETGET operations

## RFCOMM Channels
| Channel | Purpose |
|---------|---------|
| 1 | SPP (connection refused) |
| 2 | **BMAP control** — primary protocol channel |
| 8 | Refused |
| 14 | Status beacon (sends `ff5502...` periodically) |
| 22 | Diagnostic/log stream (not BMAP, dumps data regardless of input) |
| 24 | Silent (purpose unknown) |

## Function Block Map
| Block | Name              | Functions found |
|-------|-------------------|-----------------|
| 0     | ProductInfo       | 0,1,2,3,5,6,7,12,15,17,23 |
| 1     | Settings          | 0,2,3,5,7,9,10,11,12,24,27 |
| 2     | Status            | 0,2,5,16,21 |
| 3     | FirmwareUpdate    | 0,1,4,6,7,15,16 |
| 4     | DeviceManagement  | 0,1,4,8,9,14,18 |
| 5     | AudioManagement   | 0,1,3,4,5,7,13,17 |
| 6     | CallManagement    | 0 |
| 7     | Control           | 0,1,4 |
| 8     | Debug             | 7,8 |
| 9     | Notification      | 0,2 |
| 18    | Authentication    | 0,1,9,11,12,13,24 |
| 31    | AudioModes        | 0,2,3,4,8,10,11 |

## Settings Functions (Block 1)
| Func | Name             | Read value | Notes |
|------|------------------|------------|-------|
| 0    | FblockInfo       | "1.1.0"    | |
| 2    | ProductName      | "Fargo"    | |
| 3    | VoicePrompts     | 41000081020000 | |
| 5    | CNC              | 0b0003     | [numSteps=11, step=0, flags=3] |
| 7    | RangeControl/EQ  | f60a0000f60a0001f60a0002 | 3-band EQ, all at 0 |
| 9    | Buttons          | 80090e00094002 | |
| 10   | Multipoint       | 07         | |
| 11   | Sidetone         | 01020f     | |
| 12   | SetupComplete    | 01         | |
| 24   | AutoPlayPause    | 01         | |
| 27   | AutoAnswer       | 01         | |

## Status Functions (Block 2)
| Func | Name            | Read value | Decoded |
|------|-----------------|------------|---------|
| 2    | BatteryLevel    | 50ffff00   | 0x50 = 80% battery |

## CNC (Noise Cancellation) Details
- Read: GET [1.5] returns `[numSteps, currentStep, flags]`
  - numSteps: total steps (11 on this device = 0-10)
  - currentStep: current level (0=min, 10=max)
  - flags: bit0=isEnabled, bit1=!userEnableDisable
- Write: SetGet [1.5] with payload `[step, enabled?1:0]`
  - **Requires authentication** — returns OpNotSupp error 5 without auth

## EQ Details
- 3-band equalizer stored in [1.7]
- Format: 3x 4-byte groups `[f60a, VALUE, BAND_INDEX]`
- Values are signed bytes (f7=-9, 00=center, 0a=+10)
- Band 0=Bass, 1=Mid, 2=Treble

## Authentication System (Block 18)

### Overview
Cloud-mediated ECDH P-384 challenge-response. The headphones require a signature
from Bose's cloud servers (`nadc.data.api.bose.io`) before granting SET/SETGET
privileges. The app acts as a proxy between headphones and cloud.

### Auth Capabilities (from [18.1] bitmask `0339083e07`)
Supported: FblockInfo, GetAll, CondensedChallenge, OtpKeyType, ProductName,
PlatformName, ValidatedDeviceIdentityKeypair, PropagateProductIrk,
NoTokenChallenge, ProductToCloudChallenge, ProductToCloudChallengeVerifyResponse,
CloudToProductChallenge, GoogleFeatureKeys, GoogleFeatureKeyData

### Auth Device Info
- Device ECDH public key at [18.9]: P-384 PEM format
- Product name [18.12]: "wolverine"
- Platform [18.13]: "OTG-QCC-384"
- OTP key type [18.11]: 3
- Product IRK [18.24]: `3713b952XXXXXXXXXXXXXXXXXXXXXXXX`

### Hypothesized Auth Flow
1. App generates ephemeral ECDH keypair
2. [18.19] START → App sends public key → headphones return PROCESSING
3. [18.27] START → Headphones generate challenge → app forwards to Bose cloud
4. Bose cloud signs the challenge
5. [18.28] → App sends cloud response back to headphones
6. [18.29] → Cloud-to-product verification
7. Headphones grant SET/SETGET privileges for this session

### Cloud API
- Primary API: `nadc.data.api.bose.io` (uses QUIC/HTTP3, falls back to HTTPS)
- Identity: `id.api.bose.io/id-idp-mgr-core/`
- Services: `services.api.bose.io` (Apigee gateway)
- Config: `nadc-config.data.api.bose.io`
- Firmware: `ota.cdn.bose.io`, `updates-framingham-prod.smartproducts.bose.io`
- API key system called "Galapagos" — key fetched from remote config
- App has certificate pinning — rejects user-installed CA certs

### Why Auth Bypass Works
Bose protected SET (operator 0) and SET_GET (operator 2) behind cloud auth.
But START (operator 5) on the AudioModes block was left unprotected. The app
uses START to change modes in real time (it's the "instant switch" path).
SET_GET is used for persistent config changes. This distinction means we can
control the headphones in real time but can't change saved configuration.

## BMAP Error Codes
| Code | Name             | Description |
|------|------------------|-------------|
| 0    | Unknown          | Unknown error |
| 1    | Length           | Invalid length |
| 2    | Chksum           | Invalid checksum |
| 3    | FblockNotSupp    | Function block not supported |
| 4    | FuncNotSupp      | Function not supported |
| 5    | OpNotSupp        | Operator not supported (needs auth) |
| 6    | InvalidData      | Data values incorrect |
| 7    | DataUnavailable  | Requested data not available |
| 8    | Runtime          | Temporary read/write failure |
| 9    | Timeout          | Timeout |
| 10   | InvalidState     | Not applicable to current state |
| 20   | InsecureTransport| Packet on insecure transport |

## APK Info
- Package: com.bose.bosemusic (v12.1.6)
- Decompiled with jadx to apk/decompiled/
- Key classes:
  - `com.bose.bmap.messages.enums.spec.BmapFunctionBlock` — block IDs
  - `com.bose.bmap.messages.enums.spec.BmapFunction` — function IDs
  - `com.bose.bmap.messages.enums.spec.BmapOperator` — operator IDs
  - `com.bose.bmap.messages.packets.AudioModesCurrentModeStartPacket` — mode switch
  - `com.bose.bmap.messages.packets.SettingsCncSetGetPacket` — CNC control
  - `com.bose.bmap.service.SppConnectionManager` — SPP UUID: 00001101-...
  - `com.bose.bmap.messages.models.settings.CncLevel` — CNC response parser
  - `com.bose.bmap.messages.responses.SettingsCncResponse` — CNC payload format
  - `defpackage/FD1.java` — auth challenge payload serializer
  - `defpackage/C9274fE.java` — AuthenticationManager
  - `com.bose.bmap.utils.encryption.ECDH` — secp256r1 key generation
  - `com.bose.bmap.model.factories.AuthenticationPackets` — auth error codes & capabilities bitmask

## Tools
- `bmap-capture.py` — Interactive setting change capture tool
- `captures/` — Captured setting toggle data (8 captures)
- `apk/` — Decompiled Bose Music APK
- `snoop/` — Network captures and bugreports

## Quick Reference: Control Headphones from Linux

```python
import socket

BOSE_MAC = "68:F2:1F:XX:XX:XX"
sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
sock.settimeout(2)
sock.connect((BOSE_MAC, 2))

# Switch to Quiet (full ANC): mode=0
sock.send(bytes([31, 3, 0x05, 2, 0, 0]))

# Switch to Aware (transparency): mode=1
sock.send(bytes([31, 3, 0x05, 2, 1, 0]))

# Switch to Immersion: mode=2
sock.send(bytes([31, 3, 0x05, 2, 2, 0]))

# Read battery level
sock.send(bytes([2, 2, 0x01, 0x00]))
resp = sock.recv(4096)
battery_pct = resp[4]  # hex value, e.g. 0x50 = 80%

# Read current mode
sock.send(bytes([31, 3, 0x01, 0x00]))
resp = sock.recv(4096)
current_mode = resp[4]  # 0=Quiet, 1=Aware, 2=Immersion, etc.
```

## Future Work
- Crack the cloud auth to unlock SET/SETGET (EQ, fine ANC levels, device name)
- Try USB-C connection for different attack surface
- Explore [31.6] ModeConfig START — may allow editing mode parameters
- Explore [31.9] AudioModes Reset
- Explore [7.4] Control.Power START — power off from Linux?
- Build a proper CLI tool / system tray widget
- Investigate firmware downgrade via bose-dfu over USB
