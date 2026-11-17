# Conformance

bosectl's Python, Rust and C++ libraries must do the same thing with the same bytes. The conformance harness checks that. One runner plays the headphones' side of every case through each implementation, and judges every packet the library sends and every result it returns. A difference between the languages, or between a language and the evidence, fails the run.

```sh
make conformance                       # build the adapters, judge all three
python3 -I conformance/run.py --adapter python="python/.venv/bin/python -m pybmap.replay" qc-ultra2-eq
```

The runner exits 0 when every verdict holds, 1 on a failure, and 2 when it refuses to run, for example on a malformed case.

| Path | What it is |
|---|---|
| `INTERFACE.md` | The contract between the runner and each implementation's adapter: the line protocol, the calls, the result text, the error classes and `describe`. |
| `run.py` | The runner. It uses only Python's standard library and never imports `pybmap`, so it judges the Python implementation from the outside, as it judges Rust and C++. |
| `cases/NAME.case` | The cases, described below. |
| `devices.list` | The devices whose configs every adapter must describe identically. |
| `divergences.tsv` | Known differences, each tied to an open issue (below). |

The adapters are `python/pybmap/replay.py`, `rust/src/bin/bmap-replay.rs` and `cpp/src/replay.cpp`. Each one connects its library to the runner and holds no device knowledge of its own.

## The cases

A case is a short text file. Its header says what the case checks and where its expectations come from. Then come the requests the runner sends and the lines the adapter must print, in order:

```
# spec: GET [1.10] multipoint: bit 0 is enabled and bit 1 is supported, so 07 reads as on.
# source: captures/20260404-173258_wind-block.json, [1.10] = 07; bit layout from PR #47
device qc_ultra2
call multipoint
send 01 0a 01 00
recv 01 0a 03 01 07
result ok on
```

| Line | Meaning |
|---|---|
| `# spec: TEXT` | Required. What the case checks, in a sentence. |
| `# source: TEXT` | Required. The evidence its expectations come from (below). |
| `device NAME` | The first request: the device to build a connection for. |
| `call METHOD [ARG ...]` | A library call, as INTERFACE.md lists them. |
| `send HEX` or `send-drain HEX` | A packet the library must send next. Spaces in HEX are ignored. |
| `recv HEX`, `recv` or `timeout` | The headphones' answer to the packet above it. |
| `result ok [RESULT]` or `result err CLASS` | What the call must return. |

A call that the library must refuse before sending anything has its `result` straight after the `call`, with no `send` between them.

### Where expectations come from

A case's expectations come from evidence, never from what an implementation prints. Copying an implementation's output into a case would make that implementation the judge of the other two. The `# source:` line names the evidence:

- **A capture**: `captures/` holds snapshots of every function block's reply from real headphones. A case built from one uses those bytes exactly as captured.
- **A hardware report**: a contributor's capture or test on real headphones, cited by its PR or doc.
- **NOTES.md**: a packet layout the protocol notes record.
- **synthetic**: bytes written to exercise a path that no capture covers, such as an error reply or a timeout. Say so, and say which layout the bytes follow.

The captures keep each reply's payload but not its header. A case builds the reply as the BMAP header (block, function, operator 3 for STATUS, length) followed by the captured payload.

### Writing a case

1. Write the expectation from the evidence first, then run the case.
2. Run it with `--selftest`. The self-test changes each expectation in the case and requires the case to fail every time, which shows that every line is actually checked.
3. A case that fails on an implementation is a finding. Fix the implementation, or record the case in `divergences.tsv` with the issue that owns the fix. Never change a case so an implementation passes. A case changes only when its evidence was wrong, and the commit says what the new evidence is.

## Describe

For each device in `devices.list`, the runner asks every adapter to `describe` the device config and requires them all to print the same lines. A difference shows as `-` and `+` lines against the version most adapters agree on.

## Known divergences

`divergences.tsv` lists the differences that an open issue owns, one per line, separated by tabs:

```
KIND    NAME                       ADAPTER  ISSUE  NOTE
case    qc45-set-anc-unsupported   python   #56    Python writes the ANC byte ...
```

KIND is `case` or `describe`. A listed failure prints as `known` and does not fail the run. Each entry must still fail: once the fix lands and the case passes, the runner fails until the line is removed, so the list cannot go stale.
