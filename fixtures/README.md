# Test Fixtures

Language-agnostic BMAP packet captures and expected parse results.
Shared across Python, Rust, and C++ test suites.

## Structure

- `packets/<device>/` — Raw captured request/response pairs and payloads
  (`.json` snapshots or plain hexadecimal `.hex` files)
- `expected/` — Expected parse results for unit tests (JSON)

## Packet format

Each capture JSON file contains snapshots of all readable BMAP function
blocks taken before and after a specific setting change. See bmap-capture.py
for the capture tool.
