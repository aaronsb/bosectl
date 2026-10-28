# QuietComfort 45 (`duran`, `0x4039`) Protocol Notes

These notes document a Bose QuietComfort 45 unit, codename `duran`, product
ID `0x4039`, firmware `4.0.4-4360+de6a887`, platform CSR8670.

The `duran` catalog entry reuses the prince 47/39-byte ModeConfig parsers.
This report confirms the config on real hardware — all the reads, the
AudioModes layout, and mode switching — and records one discrepancy: EQ
**write** was rejected on the tested transport (macOS/IOBluetooth); see below.

## Test Environment

Unlike the Linux/BlueZ path the rest of the project targets, this unit was
exercised from **macOS** over Apple's `IOBluetooth` framework (via PyObjC),
opening an RFCOMM channel directly to the paired headphones. The byte-level
BMAP framing is identical to the BlueZ path; only the socket layer differs.

- OS: macOS (Apple Silicon)
- Transport: `IOBluetoothDevice` → `openRFCOMMChannelAsync:withChannelID:delegate:`
- Writes via `writeSync:length:`; replies collected in the channel delegate
- Device: `AC:BF:71:…`, reported `Product ID: 0x4039`, `Vendor ID: 0x009E`

## Transport

The standard SPP connection resolves to **RFCOMM channel 8**, matching the
config. `rfcommChannelOpenComplete:status:` returned status `0`, MTU 666.

The config lists an init packet (GET `[0.1]`) as required before the device
responds. On this unit every query below answered **without** the init packet
being sent first, so it appears optional on firmware 4.0.4. The config value
is left unchanged (harmless if sent); noted as a discrepancy, not a fix.

## Reads

A batch of GETs returned (concatenated) STATUS frames; decoded:

| Feature       | Addr   | Raw payload                          | Decoded |
|---------------|--------|--------------------------------------|---------|
| Firmware      | [0.5]  | `34 2e 30 2e 34 2d 34 33 36 30 …`    | `4.0.4-4360+de6a887` |
| Product name  | [1.2]  | `00 "Bose QC45"`                     | flag byte + name from byte 1 |
| Battery       | [2.2]  | `14 ff ff 00`                        | `0x14` = 20 % |
| CNC           | [1.5]  | `0b 00 03`                           | (current, max) = (0, 10) |
| EQ            | [1.7]  | `f6 0a 00 00  f6 0a 00 01  f6 0a 00 02` | 3 bands [min −10, max +10, cur, id] |
| Multipoint    | [1.10] | `07`                                 | responds |
| Sidetone      | [1.11] | `01 02 0f`                           | responds |

The battery, firmware, product-name, cnc, and eq parsers in the config all
match these payloads as-is.

## AudioModes

AudioModes GetAll `[31.1]` (START) triggered a full dump. Each ModeConfig
`[31.6]` STATUS payload is **47 bytes**, confirming the shared `prince`
layout on duran:

```
TX: 1f 01 05 00
RX: [31.1] PROCESSING
    [31.2] STATUS  02 02 00 00 00 09      (name index: 2 modes configured)
    [31.3] STATUS  00                     (current mode = Quiet)
    [31.6] STATUS  idx0 "Quiet"  47 bytes, editable flag 0, cnc 0
    [31.6] STATUS  idx1 "Aware"  47 bytes, editable flag 0, cnc 10
    [31.6] STATUS  idx2 ""       47 bytes, editable flag 1 (empty slot)
    [31.6] STATUS  idx3 ""       47 bytes, editable flag 1 (empty slot)
    [31.8] STATUS  04 03                  (favorites)
    [31.1] RESULT
```

Confirmed offsets on this unit: byte 0 = mode index, byte 3 = editable flag
(0 for the Quiet/Aware presets, 1 for slots 2-3), bytes 6-37 = UTF-8 name,
byte 42 = raw CNC (Quiet 0 = max ANC, Aware 10 = transparency). This matches
`EDITABLE_SLOTS = [2, 3]` and the preset cnc values in the config.

## Mode Switching

AudioModes CurrentMode `[31.3]`:

```
Read:   TX: 1f 03 01 00        RX: 1f 03 03 01 <modeIndex>
Switch: TX: 1f 03 05 02 <modeIndex> <announce>   (announce 00 silent, 01 voice)
```

Both directions confirmed audibly: the Aware frame produced transparency
passthrough, the Quiet frame restored full ANC.

## EQ

EQ **read** `[1.7]` works (above). EQ **write** (SETGET `[1.7]`) was rejected
on every payload shape tried from macOS/IOBluetooth, each returning a BMAP
**ERROR with code 6 (InvalidData)** and leaving the EQ unchanged at
`[0, 0, 0]`:

| Attempt                                   | Result        |
|-------------------------------------------|---------------|
| `[band_id, value]` (2-byte)               | error 6       |
| `[min, max, value, band_id]` (4-byte)     | error 6       |
| three full bands at once (12-byte)        | error 6       |

The error is InvalidData (6) rather than auth (5), so the payload format may
differ from what was tried here. The config's `eq` builder is left in place;
on this unit and firmware, callers should expect EQ writes to be rejected and
treat EQ as effectively read-only until the write format is captured.

## Unsupported or Not Yet Verified

Still not exercised on hardware in this report:

- Voice prompts `[1.3]`, buttons `[1.9]`, pairing `[4.8]`
- Sidetone / device-name **writes** (reads of sidetone confirmed above)
- ModeConfig `[31.6]` **SETGET** on editable slots 2-3 (39-byte payload)

## Summary

On this unit, `duran` is verified on hardware for the transport (channel 8),
all reads (firmware, name, battery, cnc, eq read, multipoint, sidetone), the
AudioModes GetAll/ModeConfig 47-byte layout, and mode switching `[31.3]`. One
discrepancy was recorded: EQ **write** over macOS/IOBluetooth returns error 6
on firmware 4.0.4. Writes other than mode switching were not exercised here.
