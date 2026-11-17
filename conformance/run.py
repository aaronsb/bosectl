#!/usr/bin/env python3
"""Conformance runner for bosectl's three implementations.

Plays each case under conformance/cases/ through every adapter given on the
command line, acting as the headphones: it answers each packet an adapter's
library sends with the bytes the case gives, and judges every line the
adapter prints. It then asks each adapter to describe every device in
devices.list and requires them all to agree.

The runner uses only Python's standard library and never imports pybmap, so
it judges the Python implementation from the outside, as it judges Rust and
C++. INTERFACE.md is the contract with the adapters; README.md describes the
cases.

Exit status: 0 when every verdict holds, 1 on a failure, 2 when the runner
refuses to run (a malformed case, an adapter that will not start).
"""

import argparse
import os
import queue
import re
import shlex
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPLY_TIMEOUT = 10.0

ANSWER_FORMS = [
    re.compile(r"^ready$"),
    re.compile(r"^send [0-9a-f]+$"),
    re.compile(r"^send-drain [0-9a-f]+$"),
    re.compile(r"^ok( .*)?$"),
    re.compile(r"^err (unsupported|invalid-arg|timeout|desync|unknown-device|unknown-request)$"),
    re.compile(r"^err device-error (\d+|-)$"),
    re.compile(r"^err other( .*)?$"),
]
DESCRIBE_FORMS = [
    re.compile(r"^channel \d+$"),
    re.compile(r"^init (\d+\.\d+|-)$"),
    re.compile(r"^notifications ([0-9a-f]+|-)$"),
    re.compile(r"^feature [a-z_0-9]+ \d+\.\d+$"),
    re.compile(r"^read-only \d+\.\d+$"),
    re.compile(r"^status-supported-only [01]$"),
    re.compile(r"^anc-toggle [01]$"),
    re.compile(r"^editable-slots (-|\d+( \d+)*)$"),
    re.compile(r"^preset [a-z_0-9]+ \d+$"),
]


class Refusal(Exception):
    """The runner cannot run: exit 2."""


class Mismatch(Exception):
    """An adapter's line differs from the case: the case fails."""


# ── Cases ────────────────────────────────────────────────────────────────────

def hexnorm(text):
    """Lowercase hex with spaces removed; refuses anything else."""
    h = text.replace(" ", "").lower()
    if not re.fullmatch(r"[0-9a-f]*", h) or len(h) % 2:
        raise ValueError("not hex bytes: %r" % text)
    return h


class Step:
    """One line of a case: what the runner writes, or what it expects."""

    def __init__(self, kind, text, lineno):
        self.kind = kind      # request | expect | answer
        self.text = text
        self.lineno = lineno


def load_case(path):
    """Read a case file into (header, steps). Raises Refusal when malformed."""
    header, steps = {}, []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            m = re.match(r"^# (spec|source): (.+)$", line)
            if m:
                header[m.group(1)] = m.group(2)
                continue
            if line.startswith("#"):
                continue
            word, _, rest = line.partition(" ")
            try:
                if word in ("device", "call"):
                    steps.append(Step("request", line, lineno))
                elif word in ("send", "send-drain"):
                    steps.append(Step("expect", "%s %s" % (word, hexnorm(rest)), lineno))
                elif word == "recv":
                    steps.append(Step("answer", ("recv " + hexnorm(rest)).rstrip(), lineno))
                elif word == "timeout" and not rest:
                    steps.append(Step("answer", "timeout", lineno))
                elif word == "result" and re.match(r"^(ok|err)\b", rest):
                    steps.append(Step("expect", rest, lineno))
                else:
                    raise ValueError("unknown line")
            except ValueError as e:
                raise Refusal("%s:%d: %s: %s" % (path, lineno, e, line))
    for key in ("spec", "source"):
        if key not in header:
            raise Refusal("%s: missing the '# %s:' header line" % (path, key))
    if not steps or not steps[0].text.startswith("device "):
        raise Refusal("%s: the first command must be 'device NAME'" % path)
    return header, steps


# ── Adapters ─────────────────────────────────────────────────────────────────

class Adapter:
    """One running adapter process, spoken to a line at a time."""

    def __init__(self, name, command):
        self.name = name
        try:
            self.proc = subprocess.Popen(
                shlex.split(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1)
        except OSError as e:
            raise Refusal("adapter %s does not start (%s): %s" % (name, command, e))
        # A thread moves each stdout line onto a queue, so a read can wait
        # with a timeout without losing lines the pipe has already buffered.
        self.lines = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.lines.put(line.rstrip("\n"))
        self.lines.put(None)

    def write(self, line):
        try:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            raise Mismatch("adapter exited before reading %r" % line)

    def read(self):
        try:
            line = self.lines.get(timeout=REPLY_TIMEOUT)
        except queue.Empty:
            raise Mismatch("adapter printed nothing for %.0f s" % REPLY_TIMEOUT)
        if line is None:
            raise Mismatch("adapter exited (status %s)" % self.proc.wait())
        return line

    def close(self):
        """Close stdin and return (exit status, stderr text)."""
        try:
            self.proc.stdin.close()
        except BrokenPipeError:
            pass
        try:
            self.proc.wait(timeout=REPLY_TIMEOUT)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        err = self.proc.stderr.read()
        return self.proc.returncode, err


def check_form(line, forms, what):
    if not any(f.match(line) for f in forms):
        raise Mismatch("malformed %s line: %r" % (what, line))


def play(adapter, steps):
    """Play one case's steps through a running adapter. Raises Mismatch."""
    i = 0
    while i < len(steps):
        step = steps[i]
        if step.kind != "request":
            raise Mismatch("line %d: the adapter was not asked anything before %r"
                           % (step.lineno, step.text))
        adapter.write(step.text)
        i += 1
        if step.text.startswith("device "):
            got = adapter.read()
            check_form(got, ANSWER_FORMS, "answer")
            if got != "ready":
                raise Mismatch("line %d: expected 'ready', got %r" % (step.lineno, got))
            continue
        # A call: the adapter's lines must follow the case's expectations
        # until its result, and each send is answered from the case.
        while True:
            got = adapter.read()
            check_form(got, ANSWER_FORMS, "answer")
            if i >= len(steps) or steps[i].kind != "expect":
                raise Mismatch("line %d: the case expects nothing more, got %r"
                               % (steps[i - 1].lineno, got))
            want = steps[i]
            if got != want.text:
                raise Mismatch("line %d: expected %r, got %r" % (want.lineno, want.text, got))
            i += 1
            if not got.startswith("send"):
                break  # the call's result
            if i >= len(steps) or steps[i].kind != "answer":
                raise Mismatch("line %d: the case gives no answer to %r" % (want.lineno, got))
            adapter.write(steps[i].text)
            i += 1


def run_case(name, command, steps):
    """Return None on a pass, or the failure text."""
    adapter = Adapter(name, command)
    try:
        play(adapter, steps)
    except Mismatch as e:
        _, err = adapter.close()
        return str(e) + (("\n      stderr: " + err.strip().replace("\n", "\n      stderr: ")) if err.strip() else "")
    status, err = adapter.close()
    if status != 0:
        return "adapter exited %d: %s" % (status, err.strip())
    return None


def describe(name, command, device):
    """Return the sorted describe lines, or raise Mismatch."""
    adapter = Adapter(name, command)
    try:
        adapter.write("device " + device)
        got = adapter.read()
        if got != "ready":
            raise Mismatch("expected 'ready', got %r" % got)
        adapter.write("describe")
        lines = []
        while True:
            got = adapter.read()
            if got == "end":
                break
            check_form(got, DESCRIBE_FORMS, "describe")
            lines.append(got)
        return sorted(lines)
    finally:
        adapter.close()


# ── Known divergences ────────────────────────────────────────────────────────

def load_divergences(path):
    """KIND NAME ADAPTER ISSUE NOTE, tab-separated; returns {(kind, name, adapter): note}."""
    known = {}
    if not os.path.exists(path):
        return known
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5 or parts[0] not in ("case", "describe") or not parts[3].startswith("#"):
                raise Refusal("%s:%d: expected KIND NAME ADAPTER #ISSUE NOTE, tab-separated" % (path, lineno))
            known[tuple(parts[:3])] = "%s %s" % (parts[3], parts[4])
    return known


# ── Main ─────────────────────────────────────────────────────────────────────

def mutate(steps):
    """Yield (label, steps) with one expectation changed, for the self-test."""
    for k, step in enumerate(steps):
        if step.kind == "expect":
            if step.text.startswith("send"):
                word, h = step.text.split(" ")
                bad = h[:-2] + ("00" if h[-2:] != "00" else "01")
                text = "%s %s" % (word, bad)
            else:
                text = "ok __mutated__" if step.text != "ok __mutated__" else "ok"
            changed = list(steps)
            changed[k] = Step("expect", text, step.lineno)
            yield "line %d" % step.lineno, changed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--adapter", action="append", default=[], metavar="NAME=COMMAND",
                    help="an adapter to judge; give one per implementation")
    ap.add_argument("--cases", default=os.path.join(HERE, "cases"))
    ap.add_argument("--selftest", action="store_true",
                    help="also check that a changed expectation in each case fails")
    ap.add_argument("only", nargs="*", help="case names to run (default: all)")
    args = ap.parse_args()

    adapters = []
    for spec in args.adapter:
        name, sep, command = spec.partition("=")
        if not sep or not name or not command:
            raise Refusal("--adapter takes NAME=COMMAND, got %r" % spec)
        adapters.append((name, command))
    if not adapters:
        raise Refusal("give at least one --adapter NAME=COMMAND")

    known = load_divergences(os.path.join(HERE, "divergences.tsv"))
    seen_known = set()
    failures = 0

    names = sorted(f[:-5] for f in os.listdir(args.cases) if f.endswith(".case"))
    if args.only:
        missing = set(args.only) - set(names)
        if missing:
            raise Refusal("no such case: %s" % ", ".join(sorted(missing)))
        names = [n for n in names if n in args.only]
    cases = {n: load_case(os.path.join(args.cases, n + ".case")) for n in names}

    print("cases: %d, adapters: %s" % (len(cases), ", ".join(a for a, _ in adapters)))
    for case in names:
        _, steps = cases[case]
        for name, command in adapters:
            failure = run_case(name, command, steps)
            key = ("case", case, name)
            if key in known:
                seen_known.add(key)
                if failure:
                    print("known  %-40s %-7s %s" % (case, name, known[key]))
                else:
                    print("FAIL   %-40s %-7s passes now; remove its line from divergences.tsv" % (case, name))
                    failures += 1
            elif failure:
                print("FAIL   %-40s %-7s %s" % (case, name, failure))
                failures += 1
            else:
                print("ok     %-40s %s" % (case, name))

    if args.selftest:
        name, command = adapters[0]
        for case in names:
            for label, changed in mutate(cases[case][1]):
                if run_case(name, command, changed) is None:
                    print("FAIL   selftest %s %s: the case still passes with this expectation changed" % (case, label))
                    failures += 1
        print("selftest: every changed expectation checked against %s" % name)

    devices_path = os.path.join(HERE, "devices.list")
    with open(devices_path, encoding="utf-8") as f:
        devices = [d.strip() for d in f if d.strip() and not d.startswith("#")]
    for device in devices:
        views = {}
        for name, command in adapters:
            try:
                views[name] = describe(name, command, device)
            except Mismatch as e:
                print("FAIL   describe %-31s %-7s %s" % (device, name, e))
                failures += 1
        if len(views) < 2:
            continue
        # Compare every adapter with the one most others agree with.
        groups = {}
        for name, lines in views.items():
            groups.setdefault(tuple(lines), []).append(name)
        reference = max(groups, key=lambda view: len(groups[view]))
        for name, lines in views.items():
            key = ("describe", device, name)
            differs = tuple(lines) != reference
            if key in known:
                seen_known.add(key)
                if differs:
                    print("known  describe %-31s %-7s %s" % (device, name, known[key]))
                else:
                    print("FAIL   describe %-31s %-7s agrees now; remove its line from divergences.tsv" % (device, name))
                    failures += 1
            elif differs:
                extra = sorted(set(lines) - set(reference))
                lacks = sorted(set(reference) - set(lines))
                print("FAIL   describe %-31s %-7s differs from %s:" % (device, name, ", ".join(groups[reference])))
                for line in lacks:
                    print("         - %s" % line)
                for line in extra:
                    print("         + %s" % line)
                failures += 1
        if all(tuple(v) == reference for v in views.values()):
            print("ok     describe %s" % device)

    for key, note in sorted(known.items()):
        if key not in seen_known and (key[0] != "case" or key[1] in cases):
            print("FAIL   divergences.tsv names %s %s %s, which the run did not reach" % key)
            failures += 1

    if "pybmap" in sys.modules:
        raise Refusal("the runner imported pybmap; it must judge every implementation from outside")
    print("%s: %d failure(s)" % ("FAIL" if failures else "PASS", failures))
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refusal as e:
        print("refused: %s" % e, file=sys.stderr)
        sys.exit(2)
