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
| [31.6]   | ModeConfig | Returns all mode configs as STATUS messages |
| [31.9]   | Reset      | Accepts START (InvalidData with empty payload) |

#### Unauthenticated START in Other Blocks
| Function | Name    | Status | Notes |
|----------|---------|--------|-------|
| [7.1]    | Control.GetAll | PROCESSING | Triggers control state dump |
| [7.4]    | Control.Power  | **RESULT** | **0=power off, 1=power on** |
| [4.1]    | DevMgmt.Connect | InvalidData | Needs device MAC — may initiate BT connection |
| [4.8]    | DevMgmt.PairingMode | **RESULT** | **0x01=enable, 0x00=disable** |
| [5.3]    | AudioMgmt.Control | InvalidData | Needs payload — likely play/pause/skip |
| [18.19]  | ValidatedDeviceIdentityKeypair | PROCESSING | Accepts public key for auth flow |

#### AudioModes SETGET — Full Config Control (No Auth!)

**BREAKTHROUGH #2:** SETGET on AudioModes block 31 is completely unauthenticated.
Preset modes (0-4) are firmware-locked (return Runtime error 8), but custom mode
slots (5-10) accept full configuration changes via SETGET. Combined with
CurrentMode START to switch to the custom mode, this gives us **complete control
over CNC level, spatial audio, wind block, and ANC** — all without any auth.

| Function | Operator | Status | Notes |
|----------|----------|--------|-------|
| [31.6] ModeConfig | SETGET | **WORKS on modes 5-10** | Full config: CNC, spatial, wind, ANC |
| [31.6] ModeConfig | SET | Error 5 (auth) | SET is auth-gated, but SETGET isn't |
| [31.8] Favorites | SETGET | **WORKS** | Set favorite mode indices |
| [31.8] Favorites | SET | Error 5 (auth) | |
| [31.4] DefaultMode | SETGET | Timeout (may work) | Set power-on mode |
| [31.4] DefaultMode | SET | Error 5 (auth) | |
| [31.3] CurrentMode | SETGET | Error 5 (auth) | But START works for switching |

##### ModeConfig SETGET Payload Format (40 bytes)

Built by `FBlockAudioModesKt.createAudioModesConfigSetGetPayload()`:
```
Offset  Size  Field              Values
0       1     modeIndex          5-10 (custom slots only)
1-2     2     voicePrompt        (byte1, byte2) — see AudioModesPrompt enum
3-34    32    modeName           UTF-8, null-padded to 32 bytes
35      1     cncLevel           0-10 (noise cancellation intensity)
36      1     autoCNCEnabled     0=off, 1=on
37      1     spatialAudioType   0=off, 1=fixedToRoom, 2=fixedToHead
38      1     windBlockEnabled   0=off, 1=on
39      1     ancToggleEnabled   0=off, 1=on
```

##### ModeConfig STATUS Response Format (48 bytes)

The firmware adds 3 flag bytes and extra config fields:
```
Offset  Size  Field              Notes
0       1     modeIndex
1-2     2     voicePrompt
3-5     3     flags              [3]=isUserEditable, [4]=isConfigured, [5]=?
6-37    32    modeName
38-39   2     ?                  Always 0 for custom modes
40-41   2     ?                  Mode-type specific (0x1d for custom modes)
42      1     cncLevel           0-10
43      1     autoCNCEnabled
44      1     spatialAudioType   0=off, 1=room, 2=head
45      1     windBlockEnabled
46      1     ?
47      1     ancToggleEnabled
```

Preset modes have flags[3]=0x00 (locked); custom/user modes have flags[3]=0x01 (writable).

| Mode  | Name       | Editable | Configured | Notes |
|-------|------------|----------|------------|-------|
| 0     | Quiet      | No       | No         | Firmware preset |
| 1     | Aware      | No       | No         | Firmware preset |
| 2     | Immersion  | No       | No         | Firmware preset |
| 3     | Cinema     | No       | No         | Firmware preset |
| 4     | Home       | **Yes**  | Yes        | User-created in app |
| 5-10  | None/Custom| **Yes**  | No         | Empty slots, fully configurable |

Mode 4 (Home) is editable because it was created by the user via the app.
Modes 5-10 are empty slots that accept full configuration.
The cloud auth the app uses is likely for syncing profiles across devices,
not for writing to the headphone firmware — SETGET bypasses it entirely.

##### Usage Pattern
```python
# 1. Configure custom mode slot 5
payload = [5, 0, 0]                    # mode 5, prompt NONE
payload += encode_name("Custom")       # 32-byte name
payload += [7, 0, 2, 1, 1]            # cnc=7, autoCNC=off, spatial=head, wind=on, anc=on
send(bmap_packet(31, 6, OP_SETGET, payload))

# 2. Switch to mode 5
send(bmap_packet(31, 3, OP_START, [5, 0]))

# Result: headphones now at CNC=7 with head-tracked spatial audio
```

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

### Writing — Settings Block SETGET (Also Unauthenticated!)

**BREAKTHROUGH #3:** The SETGET operator on the Settings block [1.x] is ALSO
unauthenticated! SET and START are auth-gated (error 5), but SETGET bypasses auth.

#### Settings SETGET Summary

All of these use `[1, FUNC, 0x02, LEN, ...PAYLOAD]` (block 1, operator SETGET):

| Func | Name           | Payload (SETGET)              | Notes |
|------|----------------|-------------------------------|-------|
| [1.2]  | ProductName  | UTF-8 string (no flag byte)  | Free-form device name |
| [1.3]  | VoicePrompts | 1 byte: (enabled<<5)\|lang   | See language table below |
| [1.5]  | CNC          | —                            | **AUTH REQUIRED** (use [31.6] instead) |
| [1.7]  | EQ/Range     | 2 bytes: [value, bandId]     | value=-10..+10, band=0/1/2 |
| [1.9]  | Buttons      | 3 bytes: [btnId, evt, mode]  | See button tables below |
| [1.10] | Multipoint   | 1 byte: 0=off, 1=on         | |
| [1.11] | Sidetone     | 2 bytes: [persist, mode]     | mode: 0=off,1=high,2=med,3=low |
| [1.24] | AutoPlayPause| 1 byte: 0=off, 1=on         | Pause on ear removal |
| [1.27] | AutoAnswer   | 1 byte: 0=off, 1=on         | Auto-answer calls |

#### EQ Details [1.7]
```
SETGET payload: [VALUE, BAND_ID]
  - VALUE: -10 to +10 as signed byte (0xf6 to 0x0a)
  - BAND_ID: 0=Bass, 1=Mid, 2=Treble

GET response: 3× 4-byte groups [min, max, current, bandId]
  - e.g. f60a0500 f60a0001 f60af702 = bass=+5, mid=0, treble=-9
```

#### Voice Prompt Languages [1.3]
| ID | Language | ID | Language |
|----|----------|----|-----------| 
| 0  | UK English | 12 | Hebrew |
| 1  | US English | 13 | Turkish |
| 2  | French     | 14 | Dutch |
| 3  | Italian    | 15 | Japanese |
| 4  | German     | 16 | Cantonese |
| 5  | EU Spanish | 17 | Arabic |
| 6  | MX Spanish | 18 | Swedish |
| 7  | BR Portuguese | 19 | Danish |
| 8  | Mandarin   | 20 | Norwegian |
| 9  | Korean     | 21 | Finnish |
| 10 | Russian    | 22 | Hindi |
| 11 | Polish     | | |

#### Button Remapping [1.9]

##### GET Response Format (7+ bytes)
```
[0]   buttonId          — which physical button
[1]   buttonEventType   — what gesture triggers it
[2]   configuredAction  — current assigned action
[3:7] supportedMask     — bitmask of supported ActionButtonMode values
[7:]  unavailableMask   — bitmask of unavailable modes (optional)
```

##### SETGET Payload (3 bytes)
```
[buttonId, buttonEventType, newActionMode]
```

##### Button IDs (ConfigurableButtonId)
| ID   | Name |
|------|------|
| 0x00 | DistalCnc (CNC button) |
| 0x01 | Reserved |
| 0x02 | VPA (voice assistant) |
| 0x03 | RightShortcut |
| 0x04 | LeftShortcut |
| 0x80 | Shortcut (QC Ultra 2 programmable button) |

##### Button Event Types
| ID | Gesture |
|----|---------|
| 0  | Reserved |
| 1  | Rising edge |
| 2  | Falling edge |
| 3  | Short press |
| 4  | Single press |
| 5  | Press and hold |
| 6  | Double press |
| 7  | Double press and hold |
| 8  | Triple press |
| 9  | Long press |
| 10 | Very long press |
| 11 | Very very long press |
| 12 | Very very very long press |

##### Action Button Modes
| ID | Action | ID | Action |
|----|--------|----|--------|
| 0  | NotConfigured | 11 | TrackBack |
| 1  | VPA (voice assistant) | 12 | FetchNotifications |
| 2  | ANC cycle | 13 | WindMode |
| 3  | BatteryLevel | 14 | Disabled |
| 4  | PlayPause | 15 | ClientInteraction |
| 5  | IncreaseCNC | 16 | SpotifyGo |
| 6  | DecreaseCNC | 17 | ModesCarousel |
| 7  | ToggleWakeWord | 19 | SpatialAudioMode |
| 8  | SwitchDevice | 20 | LineInSwitch |
| 9  | ConversationMode | 21 | Linking |
| 10 | TrackForward | | |

##### Current Config (QC Ultra 2)
```
Button 0x80 (Shortcut), long_press → Disabled
Supported actions: SwitchDevice, TrackBack, unknown(22), unknown(25)
Raw: 80090e00094002
```

**Note:** Button remapping via SETGET is confirmed to accept payloads (tested echo-back)
but has not been tested with actual mode changes yet. The supported action bitmask
indicates only a few actions are available for this button/event combo.
To remap: `bose raw "01 09 02 03 80 09 08"` (Shortcut, long_press → SwitchDevice)

## What Requires Authentication (Blocked)

SET and START operators on most blocks return error 5 (OpNotSupp) without
completing cloud-mediated ECDH authentication. **However, SETGET is often
unauthenticated** — Bose only gated SET and START.

Confirmed auth-blocked (SET/START only):
- Settings.ProductName [1.2] — device name (SET blocked, SETGET untested)
- Settings.Multipoint [1.10] — multipoint toggle
- Settings.StandbyTimer [1.4] — auto-off timer
- AudioManagement.Control [5.3] — play/pause/skip (SET/START blocked)

Confirmed SETGET works without auth:
- Settings.EQ [1.7] — **full equalizer control** (-10 to +10, 3 bands)
- AudioModes.ModeConfig [31.6] — **CNC, spatial, wind, ANC** on custom modes
- AudioModes.Favorites [31.8] — favorite mode selection

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
- ~~Crack ModeConfig SETGET payload format~~ **DONE** — full CNC/spatial/wind/ANC control
- Crack the cloud auth to unlock SET/SETGET on Settings block (EQ, device name)
- Try USB-C connection for different attack surface
- Explore [31.9] AudioModes Reset — factory reset individual modes?
- Explore [5.3] AudioManagement Control — play/pause/skip payload format
- Build a system tray widget / PipeWire integration
- Investigate firmware downgrade via bose-dfu over USB
- Map the unknown bytes [40-41] in ModeConfig STATUS (mode-type specific config?)
