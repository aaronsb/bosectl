# AGENTS.md

This file tells coding agents, and the people who run them, how to work on bosectl. [CONTRIBUTING.md](CONTRIBUTING.md) sets what a contribution must show. [docs/architecture.md](docs/architecture.md) describes the layers, and [NOTES.md](NOTES.md) the protocol. This file covers the working loop: the commands that prove a change works, and how a change travels to a release.

## Who does what

| Role | Who it is |
|---|---|
| The maintainer | The human who owns bosectl and decides its direction. |
| The steering session | The main agent session the maintainer works with. It plans the work, briefs other agents and merges their branches. |
| A delegated agent | A subagent the steering session starts for one piece of work, in its own worktree. |
| A fresh reviewer | A delegated agent that did not write the change it reviews. |

## The gates

A gate is a check that must pass before a change goes to review. CI runs the same targets on Ubuntu and macOS.

```sh
make test   # Python, Rust and C++ unit tests
make lint   # Python compile check
```

When you report a gate, give its command and its result, or say why it did not run. Watch each new test fail before the change and pass after it. To show that a test catches a defect, plant the defect on a copy of the file (`cp f f.bak`, plant, test, `mv f.bak f`), never by undoing it with `git checkout`, which discards uncommitted work.

`make integration` runs the Python tests against a paired headset. It sends real commands to the maintainer's devices, so an agent runs it only when the maintainer asks.

## Keeping the three languages in sync

Python (`python/pybmap/`), Rust (`rust/src/`) and C++ (`cpp/src/`) implement the same library. A change to a device config, a parser, a builder or the connection API lands in all three in the same pull request, with tests in each. A device config is data: its addresses, RFCOMM channel, init packet and parsers. Device differences go in the config, not in branches inside the connection code.

## Evidence about hardware

A parser or device change rests on bytes a real device sent. Put those bytes in the test, or in `fixtures/` when several tests share them. Say in the pull request which device, firmware and OS the bytes came from. A change that no one has run against the hardware it affects says so under "Not verified", and the maintainer decides whether it waits for a test on that hardware.

## Branches

| Branch | What it holds |
|---|---|
| `integration` | The default branch. Reviewed work collects here. Pull requests, from contributors and from agents, target it. |
| `stage` | A release candidate: a commit of `integration` that passed CI, held still while the maintainer tests it on hardware. |
| `main` | What has been released. Packages and tags come from main. |

1. **Work starts from `integration`.** Cut a branch from it (`fix/…`, `feat/…`, `docs/…`), or a worktree for a delegated agent: `git worktree add -b feat/<topic> ../bosectl-<topic> origin/integration`.
2. **A pull request into `integration`** merges after review and green CI, with a regular merge commit, never squash or rebase. Contributor pull requests follow [the maintainer's contributor practice](CONTRIBUTING.md#the-pull-request): finish weak work on the contributor's branch rather than bouncing it, and credit them.
3. **Promote a batch to `stage`** by moving `stage` forward to a commit of `integration` whose CI passed: `git push origin <commit>:stage`. Nobody commits on `stage` directly, and it only moves forward. The maintainer tests the candidate on hardware.
4. **A defect found on `stage`** is fixed by a pull request into `integration`. Then `stage` moves forward to the commit that holds the fix.
5. **Release** with a pull request from `stage` into `main`, merged with a regular merge commit once CI passes. The version bump is part of the batch: it lands on `integration` like any other change. Then run `make release VERSION=vX.Y.Z` from a checkout of main. It tags main.
6. **After a release,** merge `main` back into `integration` so the release's merge commit is in both.

`main` and `stage` are protected: neither takes a force push, and both take only commits whose CI passed. `main` changes only through a pull request.

## Writing

- Write about bosectl in the present tense: docs, comments, commits, pull request bodies and issues. Tell history in the past tense.
- Write plain, whole sentences, as you would explain the code to a colleague. Define a protocol term the first time a page uses it, such as SETGET or a function block.
- Say each fact once, and link to the place that states it.
- Commit messages use the conventional format (`fix(python): …`, `feat(rust): …`, `docs: …`), and the body says why.

## Where to look

| For | Read |
|---|---|
| The layers and the device config model | [docs/architecture.md](docs/architecture.md) |
| BMAP packets, function blocks and operators | [NOTES.md](NOTES.md) |
| One device's byte-level report | `docs/*.md` and `docs/devices/` |
| Captured packets shared by the tests | [fixtures/README.md](fixtures/README.md) |
| Build, test and release targets | `make help` |
