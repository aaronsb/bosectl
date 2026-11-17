# Conformance

bosectl's Python, Rust and C++ libraries must do the same thing with the same bytes. The conformance harness checks that. One runner plays the headphones' side of every case through each implementation, and judges every packet the library sends and every result it returns. A difference between the languages, or between a language and the evidence, fails the run.

```sh
make conformance                       # build the adapters, judge all three
python3 -I conformance/run.py --adapter python="python/.venv/bin/python -m pybmap.replay" qc-ultra2-eq
```

The runner exits 0 when every verdict holds, 1 on a failure, and 2 when it refuses to run: a malformed case or divergence entry, or an adapter that will not start. Lines an adapter prints after a case's last result fail the case.

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
| `call METHOD [ARG ...]` | A library call, as INTERFACE.md lists them, with exactly the arguments it takes. |
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
2. Run it with `--selftest`. The self-test changes each expectation in the case, in turn: each `send` line's last byte, each `send` to `send-drain` and back, and each `result`. It runs every change on an adapter that passes the case and requires the case to fail each time, which shows that every line is actually checked. A case that no adapter passes cannot be self-tested, and fails.
3. A case that fails on an implementation is a finding. Fix the implementation, or record the case in `divergences.tsv` with the issue that owns the fix. Never change a case so an implementation passes. A case changes only when its evidence was wrong, and the commit says what the new evidence is.

## Describe

For each device in `devices.list`, the runner asks every adapter to `describe` the device config and requires them all to print the same lines. A difference shows as `-` and `+` lines against the version most adapters agree on.

## Known divergences

`divergences.tsv` lists the differences that an open issue owns, one per line, separated by tabs:

```
KIND      NAME                       ADAPTER  ISSUE  WANT                                  NOTE
case      qc45-set-anc-unsupported   python   #56    5: send 1f030100                      Python writes the ANC byte ...
describe  qc35                       python   #56    -anc-toggle 0; +anc-toggle 1          Python leaves SUPPORTS_ANC_TOGGLE unset ...
```

KIND is `case` or `describe`, and ADAPTER is `python`, `rust` or `cpp`; the runner refuses any other name, here and in `--adapter`. WANT is the exact failure the entry excuses. For a case it is the case line where the adapter went wrong and the line it printed there. For a describe it is the adapter's difference from the reference, as `-` and `+` lines. A failure that matches WANT prints as `known` and does not fail the run; any other failure of the same case still fails, so an entry cannot hide a second bug or a dead adapter.

The list cannot go stale. An entry whose case passes, or whose describe agrees, fails the run until the line is removed. An entry the run never reached fails too, unless the run left it out on purpose: its adapter was not given, its case was not asked for, or a single adapter had nothing to compare. An entry that names a case or device that does not exist stops the runner.

For `describe`, adapters with a known divergence for that device don't vote. With one voter left, its view is the reference; with more, the reference is the view a strict majority of them print, and without one the runner fails and prints every view.

An adapter that crashes fails its case even after a mismatch an entry excuses, so an entry never hides a crash.
