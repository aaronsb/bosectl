#!/usr/bin/env python3
"""Interactive BMAP setting capture tool for Bose QC Ultra 2."""

import socket
import time
import json
import os
import re
import sys

BOSE_MAC = "68:F2:1F:XX:XX:XX"
CHANNEL = 2
CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

# All known-responding functions from our scan
FUNCTIONS = [
    (0, 0), (0, 1), (0, 2), (0, 3), (0, 5), (0, 6), (0, 7),
    (0, 12), (0, 15), (0, 17), (0, 23),
    (1, 0), (1, 2), (1, 3), (1, 5), (1, 7), (1, 9), (1, 10),
    (1, 11), (1, 12), (1, 24), (1, 27),
    (2, 0), (2, 2), (2, 5), (2, 16), (2, 21),
    (3, 0), (3, 1), (3, 4), (3, 6), (3, 7), (3, 15), (3, 16),
    (4, 0), (4, 1), (4, 4), (4, 8), (4, 9), (4, 14), (4, 18),
    (5, 0), (5, 1), (5, 3), (5, 4), (5, 5), (5, 7), (5, 13), (5, 17),
    (6, 0),
    (7, 0), (7, 1), (7, 4),
    (8, 7), (8, 8),
    (9, 0), (9, 2),
]


def connect():
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    sock.settimeout(2)
    sock.connect((BOSE_MAC, CHANNEL))
    return sock


def read_all(sock):
    """Read all known functions, return dict of (block,func) -> hex payload."""
    state = {}
    for block, func in FUNCTIONS:
        try:
            sock.send(bytes([block, func, 0x01, 0x00]))
            time.sleep(0.1)
            resp = sock.recv(4096)
            rop = resp[2] & 0x0F
            rlen = resp[3]
            payload = resp[4:4+rlen]
            if rop != 4:  # not an error
                state[(block, func)] = payload.hex()
        except socket.timeout:
            pass
        except (BrokenPipeError, ConnectionResetError, OSError):
            return state  # connection lost, return what we have
    return state


def diff_states(before, after):
    """Show what changed between two state snapshots."""
    changes = []
    all_keys = sorted(set(list(before.keys()) + list(after.keys())))
    for key in all_keys:
        b = before.get(key, "<missing>")
        a = after.get(key, "<missing>")
        if b != a:
            changes.append((key, b, a))
    return changes


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:50]


def main():
    os.makedirs(CAPTURE_DIR, exist_ok=True)

    print("=" * 60)
    print("  BMAP Setting Capture — Bose QC Ultra 2")
    print("=" * 60)
    print()

    while True:
        desc = input("\nWhat setting will you toggle? (or 'quit'): ").strip()
        if desc.lower() in ('quit', 'q', 'exit'):
            break
        if not desc:
            continue

        slug = slugify(desc)
        ts = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{ts}_{slug}.json"
        filepath = os.path.join(CAPTURE_DIR, filename)

        print(f"\nConnecting to Fargo...", end=" ", flush=True)
        try:
            sock = connect()
        except Exception as e:
            print(f"FAILED: {e}")
            print("Make sure headphones are connected and try again.")
            continue
        print("OK")

        # Read BEFORE state
        print("Reading BEFORE state...", end=" ", flush=True)
        before = read_all(sock)
        print(f"{len(before)} functions read")

        # Countdown
        print()
        duration = 15
        print(f">>> TOGGLE '{desc}' NOW — capturing for {duration}s <<<")
        snapshots = [{"t": 0, "label": "before", "state": before}]
        start = time.time()
        tick = 0
        while True:
            elapsed = time.time() - start
            remaining = duration - elapsed
            if remaining <= 0:
                break
            sec = int(remaining)
            if sec != tick:
                tick = sec
                bar = "#" * tick + "." * (duration - tick)
                print(f"\r  [{bar}] {tick:2d}s remaining  ", end="", flush=True)
            # Read a snapshot every ~3 seconds
            if elapsed > len(snapshots) * 3:
                snap = read_all(sock)
                snapshots.append({"t": round(elapsed, 1), "label": f"t+{round(elapsed)}s", "state": snap})
            time.sleep(0.2)
        print(f"\r  [{'#' * duration}] Done!                    ")

        # Read AFTER state
        print("Reading AFTER state...", end=" ", flush=True)
        after = read_all(sock)
        snapshots.append({"t": round(time.time() - start, 1), "label": "after", "state": after})
        print(f"{len(after)} functions read")

        sock.close()

        # Diff
        changes = diff_states(before, after)
        print()
        if changes:
            print(f"  CHANGES DETECTED ({len(changes)}):")
            for (block, func), b, a in changes:
                print(f"    [{block:2d}.{func:2d}]  {b}")
                print(f"    {'':8s}→ {a}")
        else:
            print("  NO CHANGES DETECTED between before/after")
            # Check intermediate snapshots for transient changes
            all_changes = set()
            for snap in snapshots[1:-1]:
                for key in snap["state"]:
                    if key in before and snap["state"][key] != before[key]:
                        all_changes.add(key)
            if all_changes:
                print(f"  (but {len(all_changes)} transient changes seen in intermediate snapshots)")

        # Save
        save_data = {
            "description": desc,
            "timestamp": ts,
            "mac": BOSE_MAC,
            "snapshots": [
                {
                    "t": s["t"],
                    "label": s["label"],
                    "state": {f"{k[0]}.{k[1]}": v for k, v in s["state"].items()},
                }
                for s in snapshots
            ],
            "changes": [
                {"func": f"[{k[0]}.{k[1]}]", "before": b, "after": a}
                for (k, b, a) in changes
            ],
        }
        with open(filepath, "w") as f:
            json.dump(save_data, f, indent=2)
        print(f"\n  Saved: {filepath}")


if __name__ == "__main__":
    main()
