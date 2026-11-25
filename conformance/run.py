#!/usr/bin/env python3
"""Conformance runner for bosectl's three implementations.

Plays each case under conformance/cases/ through every adapter given on the
command line, acting as the headphones: it answers each packet an adapter's
library sends with the bytes the case gives, and judges every line the
adapter prints. It then asks each adapter to describe every device in
devices.list and requires them to agree.

The runner uses only Python's standard library and never imports pybmap, so
it judges the Python implementation from the outside, as it judges Rust and
C++. INTERFACE.md is the contract with the adapters; README.md describes the
cases and divergences.tsv.

Exit status: 0 when every verdict holds, 1 on a failure, 2 when the runner
refuses to run (a malformed case or divergence entry, an adapter that will
not start).
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
MAX_TRAILING_LINES = 100

# The implementations, by the names INTERFACE.md and divergences.tsv use.
ADAPTER_NAMES = ("python", "rust", "cpp")

# Each call's argument count, from INTERFACE.md's table; set_name takes the
# rest of the line as one argument, which may be empty.
CALL_ARGS = {
    "battery": 0, "firmware": 0, "name": 0, "cnc": 0, "eq": 0, "multipoint": 0,
    "sidetone": 0, "auto_pause": 0, "auto_answer": 0, "cnc_presets": 0, "cnc_persist": 0,
    "set_cnc": 1, "set_eq": 3, "set_multipoint": 1, "set_sidetone": 1,
    "set_auto_pause": 1, "set_auto_answer": 1, "set_anc": 1,
    "set_cnc_presets": 3, "set_cnc_persist": 1,
}

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
    re.compile(r"^anc-in-cnc [01]$"),
    re.compile(r"^editable-slots (-|\d+( \d+)*)$"),
    re.compile(r"^preset [a-z_0-9]+ \d+$"),
]


class Refusal(Exception):
    """The runner cannot run: exit 2."""


class Mismatch(Exception):
    """An adapter's output differs from the case: the case fails.

    lineno and got identify the failure, so a divergence entry can name the
    one failure it excuses. lineno is None for a failure with no case line,
    such as an adapter that exits early.
    """

    def __init__(self, message, lineno=None, got=None):
        super().__init__(message)
        self.lineno = lineno
        self.got = got

    def signature(self):
        return "%s: %s" % (self.lineno, self.got) if self.lineno is not None else None


# ── Cases ────────────────────────────────────────────────────────────────────

def hexnorm(text):
    """Lowercase hex with spaces removed; refuses anything else."""
    h = text.replace(" ", "").lower()
    if not re.fullmatch(r"[0-9a-f]*", h) or len(h) % 2:
        raise ValueError("not hex bytes: %r" % text)
    return h


class Step:
    """One line of a case.

    kind is request (device, call), send (a packet the adapter must print),
    answer (recv or timeout, written back) or result (the call's outcome).
    """

    def __init__(self, kind, text, lineno):
        self.kind = kind
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
                if word in ("device", "call") and rest:
                    steps.append(Step("request", line, lineno))
                elif word in ("send", "send-drain"):
                    steps.append(Step("send", "%s %s" % (word, hexnorm(rest)), lineno))
                elif word == "recv":
                    steps.append(Step("answer", ("recv " + hexnorm(rest)).rstrip(), lineno))
                elif word == "timeout" and not rest:
                    steps.append(Step("answer", "timeout", lineno))
                elif word == "result" and re.match(r"^(ok|err)\b", rest):
                    steps.append(Step("result", rest, lineno))
                else:
                    raise ValueError("unknown line")
            except ValueError as e:
                raise Refusal("%s:%d: %s: %s" % (path, lineno, e, line))
    for key in ("spec", "source"):
        if key not in header:
            raise Refusal("%s: missing the '# %s:' header line" % (path, key))
    check_structure(path, steps)
    return header, steps


def check_structure(path, steps):
    """A case is a device line, then calls; each call is (send answer)* result."""
    def refuse(step, why):
        raise Refusal("%s:%d: %s" % (path, step.lineno, why))
    if not steps or not steps[0].text.startswith("device "):
        raise Refusal("%s: the first command must be 'device NAME'" % path)
    if len(steps) == 1:
        raise Refusal("%s: the case makes no call" % path)
    i = 1
    while i < len(steps):
        call = steps[i]
        if call.kind != "request" or not call.text.startswith("call "):
            refuse(call, "expected a 'call' line")
        words = call.text.split(" ")
        method = words[1]
        if method != "set_name":
            if method not in CALL_ARGS:
                refuse(call, "INTERFACE.md has no call %r" % method)
            if len(words) - 2 != CALL_ARGS[method]:
                refuse(call, "%s takes %d argument(s)" % (method, CALL_ARGS[method]))
        i += 1
        while i < len(steps) and steps[i].kind == "send":
            if i + 1 >= len(steps) or steps[i + 1].kind != "answer":
                refuse(steps[i], "a send needs a recv or timeout after it")
            i += 2
        if i >= len(steps) or steps[i].kind != "result":
            refuse(steps[i - 1], "the call needs a 'result' line")
        i += 1


# ── Adapters ─────────────────────────────────────────────────────────────────

class Adapter:
    """One running adapter process, spoken to a line at a time."""

    def __init__(self, name, command):
        self.name = name
        try:
            self.proc = subprocess.Popen(
                shlex.split(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding="utf-8",
                errors="backslashreplace", bufsize=1)
        except OSError as e:
            raise Refusal("adapter %s does not start (%s): %s" % (name, command, e))
        # A thread moves each stdout line onto a queue, so a read can wait
        # with a timeout without losing lines the pipe has already buffered.
        self.lines = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        try:
            for line in self.proc.stdout:
                self.lines.put(line.rstrip("\n"))
        finally:
            self.lines.put(None)

    def write(self, line):
        try:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            raise Mismatch("adapter exited before reading %r" % line)

    def read(self):
        try:
            line = self.lines.get(timeout=REPLY_TIMEOUT)
        except queue.Empty:
            raise Mismatch("adapter printed nothing for %.0f s" % REPLY_TIMEOUT)
        if line is None:
            raise Mismatch("adapter exited (status %s)" % self.proc.wait())
        return line

    def finish(self):
        """Close stdin; return (exit status, stderr, lines printed after that)."""
        try:
            self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        extra = []
        while len(extra) < MAX_TRAILING_LINES:
            try:
                line = self.lines.get(timeout=REPLY_TIMEOUT)
            except queue.Empty:
                break
            if line is None:
                break
            extra.append(line)
        try:
            self.proc.wait(timeout=REPLY_TIMEOUT)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        return self.proc.returncode, self.proc.stderr.read(), extra


def check_form(line, forms, what):
    if not any(f.match(line) for f in forms):
        raise Mismatch("malformed %s line: %r" % (what, line), got=line)


def matches(want, got):
    """Lines match exactly, except a 'result err other', which is judged by class."""
    if want == "err other":
        return got == "err other" or got.startswith("err other ")
    return got == want


def play(adapter, steps):
    """Play one case's steps through a running adapter. Raises Mismatch."""
    adapter.write(steps[0].text)
    got = adapter.read()
    if got != "ready":
        raise Mismatch("line %d: expected 'ready', got %r" % (steps[0].lineno, got),
                       steps[0].lineno, got)
    i = 1
    while i < len(steps):
        adapter.write(steps[i].text)       # a call
        i += 1
        while True:
            want = steps[i]
            got = adapter.read()
            check_form(got, ANSWER_FORMS, "answer")
            if not matches(want.text, got):
                raise Mismatch("line %d: expected %r, got %r" % (want.lineno, want.text, got),
                               want.lineno, got)
            i += 1
            if want.kind == "result":
                break
            adapter.write(steps[i].text)   # the answer to that send
            i += 1


def run_case(name, command, steps):
    """Return None on a pass, or the Mismatch."""
    adapter = Adapter(name, command)
    failure = None
    try:
        play(adapter, steps)
    except Mismatch as e:
        failure = e
    status, err, extra = adapter.finish()
    if failure is None and extra:
        failure = Mismatch("printed after its last result: %r" % extra[0])
    if status != 0:
        # A crash fails the case even after an expected mismatch, and it has
        # no signature, so no divergence entry can excuse it.
        failure = Mismatch("adapter exited %d%s" % (
            status, " after: %s" % failure if failure else ""))
    if failure is not None and err.strip():
        failure.args = (str(failure) + "\n      stderr: " + err.strip().replace("\n", "\n      stderr: "),)
    return failure


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
    except Mismatch:
        adapter.finish()
        raise
    status, _, extra = adapter.finish()
    if extra:
        raise Mismatch("printed after 'end': %r" % extra[0])
    if status != 0:
        raise Mismatch("adapter exited %d after describe" % status)
    return sorted(lines)


# ── Known divergences ────────────────────────────────────────────────────────

class Divergence:
    """One line of divergences.tsv."""

    def __init__(self, kind, name, adapter, issue, want, note, lineno):
        self.kind, self.name, self.adapter = kind, name, adapter
        self.issue, self.want, self.note, self.lineno = issue, want, note, lineno

    def label(self):
        return "%s %s" % (self.issue, self.note)


def describe_signature(lines, reference):
    """A view's difference from the reference, as one string; empty when equal."""
    diff = ["-" + l for l in sorted(set(reference) - set(lines))]
    diff += ["+" + l for l in sorted(set(lines) - set(reference))]
    return "; ".join(diff)


def load_divergences(path, case_names, devices):
    """KIND NAME ADAPTER #ISSUE WANT NOTE, tab-separated.

    WANT is the exact failure the entry excuses: for a case, the case line
    and the line the adapter printed there ("5: send 1f030100"); for a
    describe, its difference from the reference ("-anc-toggle 0; +anc-toggle 1").
    """
    known = {}
    if not os.path.exists(path):
        return known
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            where = "%s:%d" % (path, lineno)
            if len(parts) != 6 or parts[0] not in ("case", "describe") or not parts[3].startswith("#"):
                raise Refusal("%s: expected KIND NAME ADAPTER #ISSUE WANT NOTE, tab-separated" % where)
            kind, name = parts[0], parts[1]
            if parts[2] not in ADAPTER_NAMES:
                raise Refusal("%s: adapter %r is not one of %s" % (where, parts[2], ", ".join(ADAPTER_NAMES)))
            if kind == "case" and name not in case_names:
                raise Refusal("%s: no case named %s" % (where, name))
            if kind == "describe" and name not in devices:
                raise Refusal("%s: %s is not in devices.list" % (where, name))
            key = tuple(parts[:3])
            if key in known:
                raise Refusal("%s: a second entry for %s %s %s" % ((where,) + key))
            known[key] = Divergence(*parts, lineno=lineno)
    return known


# ── Self-test ────────────────────────────────────────────────────────────────

def mutations(steps):
    """Yield (label, steps) with one expectation changed."""
    for k, step in enumerate(steps):
        if step.kind == "send":
            word, h = step.text.split(" ")
            other = "send-drain" if word == "send" else "send"
            changes = ["%s %s" % (other, h),
                       "%s %s" % (word, h[:-2] + ("00" if h[-2:] != "00" else "01"))]
        elif step.kind == "result":
            changes = ["ok __mutated__" if step.text != "ok __mutated__" else "ok"]
        else:
            continue
        for text in changes:
            changed = list(steps)
            changed[k] = Step(step.kind, text, step.lineno)
            yield "line %d changed to %r" % (step.lineno, text), changed


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--adapter", action="append", default=[], metavar="NAME=COMMAND",
                    help="an adapter to judge; give one per implementation")
    ap.add_argument("--selftest", action="store_true",
                    help="also check that a changed expectation in each case fails")
    ap.add_argument("only", nargs="*", help="case names to run (default: all)")
    args = ap.parse_args()

    adapters = []
    for spec in args.adapter:
        name, sep, command = spec.partition("=")
        if not sep or not name or not command:
            raise Refusal("--adapter takes NAME=COMMAND, got %r" % spec)
        if name not in ADAPTER_NAMES:
            raise Refusal("adapter name %r is not one of %s" % (name, ", ".join(ADAPTER_NAMES)))
        adapters.append((name, command))
    if not adapters:
        raise Refusal("give at least one --adapter NAME=COMMAND")
    adapter_names = {a for a, _ in adapters}

    cases_dir = os.path.join(HERE, "cases")
    all_names = sorted(f[:-5] for f in os.listdir(cases_dir) if f.endswith(".case"))
    with open(os.path.join(HERE, "devices.list"), encoding="utf-8") as f:
        devices = [d.strip() for d in f if d.strip() and not d.startswith("#")]
    known = load_divergences(os.path.join(HERE, "divergences.tsv"), set(all_names), set(devices))

    names = all_names
    if args.only:
        missing = set(args.only) - set(all_names)
        if missing:
            raise Refusal("no such case: %s" % ", ".join(sorted(missing)))
        names = [n for n in all_names if n in args.only]
    cases = {n: load_case(os.path.join(cases_dir, n + ".case")) for n in names}

    failures = 0
    reached = set()
    passing = {}   # case -> the first adapter that passes it

    def fail(text):
        nonlocal failures
        failures += 1
        print("FAIL   " + text)

    print("cases: %d, adapters: %s" % (len(cases), ", ".join(a for a, _ in adapters)))
    for case in names:
        steps = cases[case][1]
        for name, command in adapters:
            failure = run_case(name, command, steps)
            key = ("case", case, name)
            entry = known.get(key)
            if entry:
                reached.add(key)
                if failure is None:
                    fail("%-40s %-7s passes now; remove its line from divergences.tsv" % (case, name))
                elif failure.signature() == entry.want:
                    print("known  %-40s %-7s %s" % (case, name, entry.label()))
                else:
                    fail("%-40s %-7s %s\n         divergences.tsv excuses only %r" % (case, name, failure, entry.want))
            elif failure:
                fail("%-40s %-7s %s" % (case, name, failure))
            else:
                passing.setdefault(case, (name, command))
                print("ok     %-40s %s" % (case, name))

    if args.selftest:
        for case in names:
            if case not in passing:
                fail("selftest %s: no adapter passes this case, so its expectations cannot be checked" % case)
                continue
            name, command = passing[case]
            for label, changed in mutations(cases[case][1]):
                if run_case(name, command, changed) is None:
                    fail("selftest %s on %s: the case still passes with %s" % (case, name, label))
        print("selftest: each expectation of each case changed in turn, on an adapter that passes it")

    for device in devices:
        views = {}
        for name, command in adapters:
            try:
                views[name] = describe(name, command, device)
            except Mismatch as e:
                fail("describe %-31s %-7s %s" % (device, name, e))
        if len(views) < 2:
            continue   # one adapter has nothing to compare against
        # Adapters with a known divergence for this device do not vote. One
        # voter left is the reference; with none, nothing can judge.
        voters = {n: v for n, v in views.items() if ("describe", device, n) not in known}
        if not voters:
            fail("describe %-31s every adapter has a known divergence; nothing can judge" % device)
            continue
        groups = {}
        for name, lines in voters.items():
            groups.setdefault(tuple(lines), []).append(name)
        reference, agree = max(groups.items(), key=lambda g: len(g[1]))
        if len(voters) > 1 and len(agree) * 2 <= len(voters):
            fail("describe %-31s no majority among %s" % (device, ", ".join(sorted(voters))))
            for view, group in groups.items():
                print("         %s: %s" % ("+".join(group), describe_signature(list(view), list(reference)) or "(first view)"))
            continue
        for name, lines in views.items():
            key = ("describe", device, name)
            signature = describe_signature(lines, reference)
            entry = known.get(key)
            if entry:
                reached.add(key)
                if not signature:
                    fail("describe %-31s %-7s agrees now; remove its line from divergences.tsv" % (device, name))
                elif signature == entry.want:
                    print("known  describe %-31s %-7s %s" % (device, name, entry.label()))
                else:
                    fail("describe %-31s %-7s differs by %r\n         divergences.tsv excuses only %r"
                         % (device, name, signature, entry.want))
            elif signature:
                fail("describe %-31s %-7s differs from %s: %s" % (device, name, ", ".join(agree), signature))
        if all(not describe_signature(v, reference) for v in views.values()):
            print("ok     describe %s" % device)

    for key, entry in sorted(known.items()):
        # An entry is excused only when the run left it out: its adapter was not
        # given, its case was not asked for, or one adapter has nothing to compare.
        filtered = (entry.adapter not in adapter_names
                    or (key[0] == "case" and key[1] not in cases)
                    or (key[0] == "describe" and len(adapters) < 2))
        if key not in reached and not filtered:
            fail("divergences.tsv line %d (%s %s %s) was not reached" % ((entry.lineno,) + key))

    print("%s: %d failure(s)" % ("FAIL" if failures else "PASS", failures))
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refusal as e:
        print("refused: %s" % e, file=sys.stderr)
        sys.exit(2)
