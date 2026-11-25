# The conformance interface

bosectl implements one library three times, in Python, Rust and C++. The conformance harness checks that the three behave the same, and that each behaves as the evidence about real headphones says it should. This document is the contract between the harness and each implementation.

The harness has two parts:

- **The runner**, `conformance/run.py`. It reads the cases, plays the headphones' side of every exchange, and judges what each implementation sends and returns. It uses only Python's standard library and never imports `pybmap`, so it judges the Python implementation from the outside, the same way it judges Rust and C++.
- **An adapter for each implementation**: `python -m pybmap.replay`, Rust's `bmap-replay` and C++'s `bmap_replay`. An adapter is a thin program that connects its library to the runner over standard input and output. It holds no device knowledge of its own: everything it prints comes from the library.

## The adapter's command line

```
ADAPTER
```

The adapter takes no arguments. It reads requests from standard input, one per line, and writes answers to standard output, one per line, flushing after each line. Standard error is free-form, and the runner shows it when a case fails. The adapter exits 0 when standard input closes.

## Requests

| Request | The adapter |
|---|---|
| `device NAME` | Builds a connection for device NAME over the stdio transport (below), without connecting, probing channels or sending an init packet. Answers `ready`, or `err unknown-device` when the library has no device of that name. |
| `call METHOD [ARG ...]` | Calls the library method (The calls). While the library talks to the headphones, the adapter relays each exchange (The stdio transport). When the call returns, it answers `ok`, `ok RESULT` or `err CLASS [DETAIL]`. |
| `describe` | Prints the device's configuration (Describe), then `end`. |

A request before `device`, or a method this document does not list, is answered `err unknown-request`.

## The stdio transport

The adapter gives its library a transport that sends nothing over Bluetooth. When the library sends a packet, the transport writes one line and waits for the runner's answer:

| The library calls | The transport writes |
|---|---|
| `send_recv(packet)` | `send HEX` |
| `send_recv_drain(packet)` (Python: `send_recv(packet, drain=True)`) | `send-drain HEX` |

HEX is the packet's bytes as lowercase hex digits with no spaces. The transport then reads one line:

| The runner writes | The transport |
|---|---|
| `recv HEX` | returns those bytes to the library. They can hold one reply, several replies back to back, or part of one. `recv` with nothing after it returns no bytes. |
| `timeout` | raises the library's timeout error. |

## The calls

Each call names the library method of the same name. ARGs are separated by single spaces, except `set_name`, whose ARG is the rest of the line and may be empty. A call with the wrong number of ARGs answers `err invalid-arg` without calling the library, and the runner refuses a case whose call has the wrong number. A RESULT is printed exactly as the table gives it.

| Call | ARGs | RESULT |
|---|---|---|
| `battery` | | the aggregate level, a decimal number |
| `firmware` | | the version text |
| `name` | | the device name |
| `cnc` | | `CURRENT/MAX` |
| `eq` | | the bass, mid and treble levels in band order, separated by spaces, such as `0 -2 -6` |
| `multipoint` | | `on` or `off` |
| `sidetone` | | `off`, `low`, `medium`, `high`, or `unknown(N)` |
| `auto_pause` | | `on` or `off` |
| `auto_answer` | | `on` or `off` |
| `cnc_presets` | | the three CNC preset steps in order, separated by spaces, such as `0 5 10` |
| `cnc_persist` | | `on` or `off` |
| `set_cnc` | `LEVEL` | none |
| `set_eq` | `BASS MID TREBLE` | none |
| `set_name` | `TEXT` | none |
| `set_multipoint` | `on` or `off` | none |
| `set_sidetone` | `off`, `low`, `medium` or `high` | none |
| `set_auto_pause` | `on` or `off` | none |
| `set_auto_answer` | `on` or `off` | none |
| `set_anc` | `on` or `off` | none |
| `set_cnc_presets` | `A B C` | none |
| `set_cnc_persist` | `on` or `off` | none |

## Errors

A call that fails answers `err CLASS`, where CLASS says what happened. The adapter maps its library's errors to these classes, and maps nothing else: a library that lacks an error type for a class, or raises the wrong one, fails the case, so the harness shows the gap instead of the adapter covering it.

| Class | When |
|---|---|
| `unsupported` | The device does not have the feature, or the library refuses the write (a read-only feature). |
| `invalid-arg` | The library rejected an argument before sending anything. An adapter also answers `invalid-arg` for an ARG it cannot pass to the library at all: a missing ARG, a word that is not a number, or a number outside the range of the library parameter's type (such as 300 for a C++ `uint8_t`). A value the parameter can hold is always passed through, so the library decides. |
| `device-error N` | The headphones answered with a BMAP error; N is its code in decimal, `5` for an authentication error. `device-error -` when the library found the reply unusable but no error code applies, such as an empty or malformed reply. |
| `timeout` | The transport timed out. |
| `desync` | The reply carried a different address than the request. |
| `other DETAIL` | Anything else. DETAIL is the error's text, for diagnosis. A case that expects `result err other` matches any DETAIL; a known divergence (README.md) pins the exact line. |

## Describe

`describe` prints one line for each fact below, in any order, then `end`. Every line is data the device config holds. An adapter prints it as its library reads it and computes nothing of its own. Behaviour, such as which path a CNC write takes, is judged by the cases. The runner sorts the lines before it compares them, and requires every adapter to print the same set for a device.

| Line | Meaning |
|---|---|
| `channel N` | The RFCOMM channel the config gives. |
| `init F.N` or `init -` | The init packet's address, or none. |
| `notifications HEX` or `notifications -` | The SETGET [9.2] payload sent on connect, or none. |
| `feature NAME F.N` | One line for each feature the config gives an address, by the feature names of the Python configs (`battery`, `cnc`, `mode_config` and so on). |
| `read-only F.N` | One line for each address whose writes the library refuses. |
| `status-supported-only 0` or `1` | Whether `status` shows only the settings the device has. |
| `anc-toggle 0` or `1` | The config's ANC-toggle flag, as the library reads it (Python's `SUPPORTS_ANC_TOGGLE`, which counts as 1 when a device module leaves it out). |
| `anc-in-cnc 0` or `1` | Whether ANC on/off is bit 0 of CNC [1.5]'s flags byte (Python's `ANC_IN_CNC`, 0 when left out). |
| `editable-slots N N ...` or `editable-slots -` | The profile slots a user may edit, in the config's order. |
| `preset NAME N` | One line for each preset mode and its index. |
