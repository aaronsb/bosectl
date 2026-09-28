# QuietComfort Headphones (`prince`, `0x4075`) Protocol Notes

These notes document captures from a Bose QuietComfort Headphones unit,
codename `prince`, product ID `0x4075`, firmware
`1.0.6-80+f5f219b`.

This is not the same catalog entry as QuietComfort 45 (`duran`, `0x4039`).
The protocol may be related, but `duran` should remain unclaimed until it is
verified on real hardware.

## Transport

`prince` exposes BMAP over Bluetooth SPP. Connecting through the standard SPP
UUID (`00001101-0000-1000-8000-00805F9B34FB`) resolves to RFCOMM channel 8 on
the tested unit. A second unit (firmware 1.0.6-80+f5f219b, BlueZ 5.85)
returned `EBUSY` on 8 and answered on 9, so the channel varies by unit or by
which profiles bluetoothd has already claimed. `connect()` handles this:
the configured channel is tried first, then 2, 8, and 9 are probed with a
firmware GET, since some channels (14, 25, 26 observed) accept the socket
without speaking BMAP.

Mode switches via `START [31.3]` are acked with `PROCESSING` (7) rather than
`RESULT` and applied asynchronously; `set_mode()` treats both as success.

Open question: the two units disagreed on sidetone (`off` vs `medium`) and
multipoint (`off` vs `on`) read from the same device seconds apart. The unit
reporting `medium` had sidetone set to medium earlier in that session, which
points at the `[1.11]`/`[1.10]` parsers' offsets being worth re-checking
against a capture.

BMAP framing is unchanged:

```
[fblock, function, flags, payload_length, ...payload]
```

The low nibble of `flags` is the operator:

| Operator | Value | Direction |
|----------|-------|-----------|
| GET | `0x01` | read |
| SETGET | `0x02` | write and read back |
| STATUS | `0x03` | response |
| ERROR | `0x04` | response |
| START | `0x05` | action |
| RESULT | `0x06` | response |

## Mode Switching

Current mode is AudioModes CurrentMode `[31.3]`.

Read current mode:

```
TX: 1f 03 01 00
RX: 1f 03 03 01 <modeIndex>
```

Switch mode:

```
TX: 1f 03 05 02 <modeIndex> <announce>
```

`announce` is `00` for silent and `01` to play the voice prompt.

Observed modes on the tested unit:

| Index | Prompt | Name | Editable | Raw CNC | Wind |
|-------|--------|------|----------|---------|------|
| 0 | `00 01` | Quiet | no | 0 | off |
| 1 | `00 02` | Aware | no | 10 | off |
| 2 | `00 07` | Commute | yes | 0 | on |
| 3 | `00 0c` | Music | yes | 0-10 observed | off/on observed |

Slots 2 and 3 are user-configured names on the tested unit, so only the slot
layout and editability should be treated as protocol facts. Do not assume the
names `Commute` and `Music` exist on every unit.

## Mode Dump

All mode configs are returned by starting AudioModes GetAll `[31.1]`:

```
TX: 1f 01 05 00
RX: one or more [31.6] STATUS packets
```

Each `[31.6]` STATUS payload is 47 bytes on `prince`:

| Offset | Size | Field |
|--------|------|-------|
| 0 | 1 | mode index |
| 1-2 | 2 | voice prompt ID |
| 3 | 1 | editable flag |
| 4 | 1 | configured flag |
| 5 | 1 | unknown flag |
| 6-37 | 32 | mode name, UTF-8, null padded |
| 38-40 | 3 | unknown |
| 41 | 1 | capability/config bits, observed `0x09` |
| 42 | 1 | raw CNC level |
| 43 | 1 | auto CNC |
| 44 | 1 | spatial audio field |
| 45 | 1 | unknown |
| 46 | 1 | wind block |

This differs from QC Ultra 2's 48-byte STATUS layout. Most importantly,
`prince` does not expose the final `ancToggle` byte at offset 47.

Example decoded tail for the tested `Music` slot:

```
... 00 00 00 09 05 00 00 00 00
            ^^ raw CNC = 5
                     ^^ wind = 0
```

## ModeConfig SETGET

`prince` writes editable mode settings with AudioModes ModeConfig `[31.6]`
SETGET. The payload is 39 bytes:

```
1f 06 02 27 <39-byte payload>
```

Payload layout:

| Offset | Size | Field |
|--------|------|-------|
| 0 | 1 | mode index |
| 1-2 | 2 | voice prompt ID |
| 3-34 | 32 | mode name, UTF-8, null padded |
| 35 | 1 | raw CNC level |
| 36 | 1 | auto CNC |
| 37 | 1 | spatial audio field |
| 38 | 1 | wind block |

The raw CNC scale is inverted from a user-facing "noise cancellation strength"
label:

| Raw CNC | Audible meaning |
|---------|-----------------|
| 0 | maximum ANC |
| 10 | most ambient/pass-through |

If a UI wants to show "ANC strength", display `10 - rawCnc`.

Captured official-app edits to the `Music` slot changed:

```
rawCnc: 10 -> 7 -> 4 -> 1 -> 0
wind:   0 -> 1 -> 0
```

These writes applied immediately when the edited slot was the current mode.

## EQ

`prince` exposes the same 3-band equalizer register as `qc45` and
`qc_ultra2`:

```
[1.7] RangeControl/EQ GET/SETGET
```

A GET returns 4-byte groups `[min, max, current, band_id]` with signed
`-10..+10` values. SETGET writes one band per packet as `[value, band_id]`
(`0` = bass, `1` = mid, `2` = treble). Verified on firmware
1.0.6-80+f5f219b: a read returned Bass +6 / Mid +5 / Treble +6, and a write
round-tripped through a subsequent read.

## Unsupported or Not Yet Verified

The tested firmware does not support QC Ultra 2's direct live settings register:

```
[31.10] AudioModesSettingsConfig SETGET -> ERROR FuncNotSupp
```

It also rejects the newer 40-byte ModeConfig payload that includes `ancToggle`:

```
[31.6] ModeConfig SETGET, 40-byte payload -> ERROR Length
```

No unauthenticated true ANC-off toggle was found:

| Attempt | Result |
|---------|--------|
| `[31.10]` AudioModesSettingsConfig | function not supported |
| `[31.6]` 40-byte ModeConfig with `ancToggle` | length error |
| `[1.6]` ANR GET | function not supported |
| `[1.5]` SettingsCnc SETGET with disable flag | rejected/auth gated |

The verified local controls are mode switching, editable-mode raw CNC level,
Wind Block, and 3-band EQ. Buttons, multipoint, power, and true ANC off
remain unverified for `prince`.
