# Contributing to bosectl

Contributions are welcome: fixes, new devices, protocol findings and hardware reports. You may write the code by hand, with AI coding agents, or both. bosectl itself is built by one maintainer working with agents, and every change goes through the same tests and review however it was written.

bosectl implements the same library three times, in Python, Rust and C++. [docs/architecture.md](docs/architecture.md) describes the layers they share, and [NOTES.md](NOTES.md) records what is known about the BMAP protocol.

## What judges a change

bosectl talks to headphones the maintainer mostly does not own, so a change is judged by evidence that anyone can rerun or read:

- **The unit tests**, in all three languages. `make test` runs them, and CI runs them on Ubuntu and macOS for every pull request.
- **Captured bytes.** A request and the reply a real device gave, as hex in a test or as a file under [fixtures/](fixtures/README.md). A parser is only as right as the bytes it was checked against.
- **A hardware report.** For a device's first support or a change in how bosectl drives it: the device, its firmware version, the OS, the commands you ran and what each returned. [docs/quietcomfort-headphones-prince.md](docs/quietcomfort-headphones-prince.md) is an example.

## A contribution brings its proof

- **A fix starts with a test that the defect makes fail.** Build the test from the bytes the device sent, then fix the code so the test passes. Show the test failing without the fix and passing with it.
- **A new device brings its config in all three languages,** with tests of its parsers and the hardware report behind it.
- **A protocol finding says how it was found:** what you wrote, what you read back, and which bytes moved. Diffing the reply after each write, with every other field held constant, is the usual method.
- **The three implementations stay in sync.** A change to a parser, a device config or the connection API lands in Python, Rust and C++ together. If you can only write one of them, say so in the pull request and the maintainer will port it.

## The pull request

Open the pull request against `integration`, which is the default branch. [AGENTS.md](AGENTS.md#branches) describes how work moves from `integration` to a release.

- One change per pull request.
- Run `make test` and read the whole diff yourself before you open it.
- Fill in the template. It asks for the proof above, and for:
  - **Purpose, cause, effects and value,** in your own words: what the change is for, what made it necessary, what it changes and what could break, and what it is worth to people who use bosectl.
  - **How the code was written:** by hand, by an AI agent (name the model and tool if you know them), or mixed. Nothing is turned away for how it was written.
  - **What you could not verify.** Usually that is hardware you do not have. Saying so lets the maintainer, or another owner of that device, test it.

Review will question the design and the evidence. The person who submits a change should be able to explain and defend it. A change that nobody can explain is not merged, however it was written.

The maintainer may push commits to your branch to finish a change, and will say what changed and why. Your commits stay in the history with your name on them.

## Issues

There are forms for bug reports, device reports and feature requests. A device report is useful even without code: which features work on your headphones, with the firmware version, helps the next person add support.

## Licence

Contributions are made under the MIT licence in [LICENSE](LICENSE).
