"""Beta 10: an unplugged instrument no longer floods the log.

Knut's beta-8 logs (2026-10-03, 15:46 to 15:47): with the instrument unplugged
during a measurement, Argyll's USB layer printed
``icoms_usb_transaction: ReadPipeAsync failed with 0xe00002c0`` until the run was
stopped, and ChromIQ logged each one twice: some 255,000 lines in a minute,
which rotated the rest of the session out of the five log files.
``core/line_flood.py`` collapses the repeats where the output enters ChromIQ.
"""
from __future__ import annotations

import inspect
import json

import pytest

from core import line_flood
from core.argyll_runner import ArgyllRunner
from core.line_flood import RepeatGate

USB = "icoms_usb_transaction: ReadPipeAsync failed with 0xe00002c0"


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class _Proc:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def readAllStandardOutput(self):
        data = self.chunks.pop(0) if self.chunks else b""
        return type("B", (), {"data": lambda _s, d=data: d})()


@pytest.fixture
def runner():
    r = ArgyllRunner.__new__(ArgyllRunner)
    lines = []
    r.line_received = type("S", (), {"emit": lambda _s, l: lines.append(l)})()
    r._partial_json = b""
    r.lines = lines
    return r


def _replay(r, data: bytes, size: int = 4096):
    chunks = [data[i:i + size] for i in range(0, len(data), size)]
    r._process = _Proc(chunks)
    for _ in chunks:
        ArgyllRunner._on_ready_read(r)
    for line in r.__dict__["_line_gate"].flush():
        r.lines.append(line)


def test_knuts_flood_of_127500_lines_becomes_a_handful(runner):
    """The real shape: 127,500 identical lines, cut by the pipe at 4 KB
    (so most reads end mid-line), between ordinary output."""
    head = (b'{"event":"error","kind":"cal_failed","detail":"Communications '
            b'failure"}\nCalibration failed\n')
    data = head + (USB + "\n").encode() * 127_500 + b"the last line\n"
    _replay(runner, data)
    lines = runner.lines
    assert lines[0].startswith('{"event":"error"')
    assert lines[1] == "Calibration failed"
    # The first occurrence and its first repeats are shown unchanged ...
    assert lines[2:2 + line_flood.SHOW] == [USB] * line_flood.SHOW
    # ... then one summary that counts every one of the rest ...
    summaries = [ln for ln in lines if line_flood.is_summary(ln)]
    hidden = sum(int(s.split(" came ")[1].split()[0]) for s in summaries)
    assert line_flood.SHOW + hidden == 127_500
    assert summaries[0].startswith("[ChromIQ: the line shown above came ")
    assert not any("ReadPipeAsync" in s for s in summaries)   # not quoted
    # ... and nothing after the flood is lost.
    assert lines[-1] == "the last line"
    assert len(lines) < 12, lines


def test_a_flood_over_a_minute_leaves_a_line_every_five_seconds():
    clock = _Clock()
    gate = RepeatGate(clock=clock)
    out = []
    for _ in range(60 * 2000):          # 2,000 lines a second for a minute
        clock.t += 1 / 2000
        out += gate.feed(USB)
    out += gate.flush()
    summaries = [ln for ln in out if ln.startswith("[ChromIQ")]
    assert out[:line_flood.SHOW] == [USB] * line_flood.SHOW
    assert 10 <= len(summaries) <= 13, len(summaries)
    hidden = sum(int(s.split(" came ")[1].split()[0]) for s in summaries)
    assert line_flood.SHOW + hidden == 120_000


def test_the_summary_gap_stays_under_the_keystroke_watchdog():
    """The Measure tab's keystroke watchdog fires after 12 s without output;
    a flood must keep reporting while it goes on, as the raw lines did."""
    assert line_flood.SUMMARY_EVERY < 12


def test_a_line_that_comes_back_after_a_pause_is_always_shown():
    """A prompt asked again after the user pressed a key is not a flood."""
    clock = _Clock()
    gate = RepeatGate(clock=clock)
    prompt = "Place the instrument on the white reference, and hit any key"
    shown = []
    for _ in range(10):
        clock.t += line_flood.BURST_GAP + 0.5
        shown += gate.feed(prompt)
    assert shown == [prompt] * 10


def test_engine_events_are_never_collapsed():
    gate = RepeatGate(clock=_Clock())
    ev = "\x07" + json.dumps({"event": "progress", "done": 3})
    assert sum((gate.feed(ev) for _ in range(500)), []) == [ev] * 500


def test_lines_that_differ_only_in_a_number_all_pass():
    """profcheck's per-patch lines, colprof's progress: data that is parsed."""
    gate = RepeatGate(clock=_Clock())
    lines = [f"[{i}] 0.1 0.2 0.3 -> 50.0 1.0 2.0 de {i % 7}.0"
             for i in range(5000)]
    assert sum((gate.feed(ln) for ln in lines), []) == lines


def test_an_alternating_pair_is_collapsed_too():
    clock = _Clock()
    gate = RepeatGate(clock=clock)
    other = "usb_read: failed"
    out = []
    for _ in range(10_000):
        clock.t += 0.001
        out += gate.feed(USB) + gate.feed(other)
    out += gate.flush()
    assert out.count(USB) == line_flood.SHOW
    assert out.count(other) == line_flood.SHOW
    assert len(out) < 30


def test_the_disconnection_still_reaches_every_parser_unchanged(runner):
    """The windows and sounds react to the first ReadPipeAsync line, and that
    line still arrives as it did, before anything is counted."""
    import re

    from workflow import measure_manager, spot_read_manager
    data = b"Reading strip A\n" + (USB + "\n").encode() * 5000
    _replay(runner, data)
    first = runner.lines.index(USB)
    assert runner.lines[first - 1] == "Reading strip A"
    for mod in (measure_manager, spot_read_manager):
        rx: re.Pattern = mod._USB_ERROR_RE
        assert rx.search(runner.lines[first])


def test_a_prompt_without_newline_is_still_shown_at_once(runner):
    _replay(runner, b"Ready to read strip A, hit any key to continue: ")
    assert runner.lines == ["Ready to read strip A, hit any key to continue: "]


def test_every_reader_goes_through_the_gate():
    src = inspect.getsource(ArgyllRunner)
    assert "repeated output suppressed" not in src
    for name in ("_pty_reader", "_pipe_reader"):
        body = inspect.getsource(getattr(ArgyllRunner, name))
        assert "RepeatGate()" in body and "gate.flush()" in body, name
    assert "self._gated_lines(text)" in inspect.getsource(
        ArgyllRunner._on_ready_read)
    fin = inspect.getsource(ArgyllRunner._on_finished)
    assert "gate.flush()" in fin
    assert "self._line_gate = RepeatGate()" in inspect.getsource(
        ArgyllRunner.run)


# Review of beta 10 (small): the burst of a line survived the different lines
# between its repeats, so ordinary output lost lines in every normal run:
# colprof -v's blank lines and targen's "Re-seeding" (measured on the real
# tools: 3 and 2 lines hidden, each replaced by a "[ChromIQ: the line ...]"
# summary), and stock chartread's strip menu, reprinted for every 'f' of a
# quick navigation, lost its instructions and its "Press any other key to
# start:" prompt from the fifth strip on.

def _through(lines, clock=None):
    gate = RepeatGate(clock=clock or (lambda: 0.0))
    return [o for ln in lines for o in gate.feed(ln)] + gate.flush()


def test_a_line_repeated_between_new_lines_is_never_hidden():
    colprof = []
    for i in range(40):
        colprof += ["", f"Doing pass {i}", f"Max err {i}.0"]
    assert _through(colprof) == colprof
    targen = []
    for i in range(30):
        targen += [f"Added {i * 10} patches", "Re-seeding"]
    assert _through(targen) == targen


def test_a_quick_strip_navigation_shows_every_menu_and_prompt():
    menu = []
    for strip in "ABCDEFGHIJKLMNOP":
        menu += [f"Ready to read strip pass {strip}",
                 "Press 'f' to move forward, 'b' to move back, "
                 "'n' for next unread,",
                 " 'd' when done, Esc or 'q' to quit without saving.",
                 "Press any other key to start:"]
    assert _through(menu) == menu


def test_a_flood_interrupted_by_one_line_stays_collapsed():
    lines = [USB] * 1000 + ["usb: retrying"] + [USB] * 1000
    out = _through(lines)
    assert out.count(USB) == line_flood.SHOW
    assert "usb: retrying" in out
    hidden = sum(int(s.split(" came ")[1].split()[0])
                 for s in out if s.startswith("[ChromIQ"))
    assert hidden == 2000 - line_flood.SHOW


# ---- the beta-10 review's three points (2026-10-04) -----------------------------

def _patterns():
    """Every module-level regex of the modules that parse tool output: the
    runner, the workflow runners and managers, and the tabs and dialogs that
    are handed its lines."""
    import importlib
    import pkgutil
    import re as _re
    import ui.dialogs
    import ui.tabs
    import workflow
    mods = ["core.argyll_runner"]
    for pkg in (workflow, ui.tabs, ui.dialogs):
        mods += [f"{pkg.__name__}.{m.name}"
                 for m in pkgutil.iter_modules(pkg.__path__)]
    out = []
    for name in mods:
        try:
            mod = importlib.import_module(name)
        except Exception:                       # noqa: BLE001 — optional deps
            continue
        out += [(name, k, v) for k, v in vars(mod).items()
                if isinstance(v, _re.Pattern)]
    return out


#: Lines a tool may print over and over: the USB loop, chartread's prompts and
#: errors, the engine's text lines.
FLOODERS = [
    USB,
    "Instrument Access Failed: Communications failure",
    "Ready to read strip pass A",
    "Press any other key to start:",
    "Strip read failed due to misread",
    "Calibration failed with 'Communications failure' (Comms error)",
    "Error - Unexpected Patch Response",
    "Patch 12 of strip A: The instrument can't be read",
    "Are you sure ? [y/n]",
    "Spot read failed due to the sensor being in the wrong position",
]


def test_a_summary_matches_no_pattern_of_the_tool_output_parsers(qapp):
    """(a) A parser searching the lines it is handed must not count a
    summary as one more of the line it stands for, nor as anything else:
    the summary quotes nothing, and no pattern finds its own words."""
    pats = _patterns()
    assert len(pats) > 50, "the census found too few patterns to mean much"
    summaries = {line_flood.summary_line(109996),
                 line_flood.summary_line(109996, 2)}
    for line in FLOODERS:
        gate = RepeatGate(clock=lambda: 0.0)
        out = [o for _ in range(50) for o in gate.feed(line)] + gate.flush()
        assert out[:line_flood.SHOW] == [line] * line_flood.SHOW
        summaries |= set(out[line_flood.SHOW:])
    assert all(line_flood.is_summary(s) for s in summaries), summaries
    for mod, name, pat in pats:
        if pat.search("[ChromIQ: a note]"):
            continue        # punctuation alone (a file-name sanitiser)
        for summary in summaries:
            assert not pat.search(summary), (mod, name, summary)


def test_a_summary_is_plain_text():
    """(a) No invisible characters: the log stays searchable and a copy of
    it carries nothing a reader cannot see (the U+2060 joiner of the first
    beta-10 build did both)."""
    import unicodedata
    out = _through([USB] * 500 + ["Ready to read strip pass A"] * 500
                   + ["a", "b"] * 500)
    summaries = [o for o in out if line_flood.is_summary(o)]
    assert len(summaries) == 3, out
    for s in summaries:
        assert s.isascii() and s.isprintable(), repr(s)
        assert not any(unicodedata.category(c) in ("Cf", "Cc", "Zl", "Zp")
                       for c in s)


def test_two_alternating_lines_share_one_summary():
    out = _through(["a", "b"] * 500 + ["next"])
    assert out[:2 * line_flood.SHOW] == ["a", "b"] * line_flood.SHOW
    assert out[2 * line_flood.SHOW:] == [
        "[ChromIQ: the 2 lines shown above came 992 more times between "
        "them, not shown]", "next"]


def test_one_hidden_repeat_is_shown_as_itself():
    """(b) Never "came 1 more time": one hidden repeat is the line itself."""
    out = _through([USB] * (line_flood.SHOW + 1) + ["next"])
    assert out == [USB] * (line_flood.SHOW + 1) + ["next"]
    assert not any("more time" in o for o in out)


def test_the_first_summary_comes_a_full_period_into_the_flood():
    """(b) The run's first flood, minutes after the gate was made, no longer
    opens with a summary of one: the first one comes SUMMARY_EVERY in."""
    clock = _Clock()
    gate = RepeatGate(clock=clock)
    clock.t += 600.0                              # a long quiet measurement
    out = []
    for _ in range(20000):                        # 2000 lines a second
        clock.t += 0.0005
        out += gate.feed(USB)
    out += gate.flush()
    counts = [int(s.split(" came ")[1].split()[0])
              for s in out if line_flood.is_summary(s)]
    assert counts and min(counts) > 1, counts
    assert counts[0] >= 9000, counts


def test_a_flood_that_ends_in_silence_is_summed_up_on_quiet():
    """(c) The summary comes once the tool has been quiet for a burst gap,
    not when the next line arrives."""
    clock = _Clock()
    gate = RepeatGate(clock=clock)
    for _ in range(100):
        clock.t += 0.01
        gate.feed(USB)
    assert gate.pending()
    clock.t += 1.0
    assert gate.idle() == []                     # still inside the burst gap
    clock.t += line_flood.BURST_GAP
    out = gate.idle()
    assert len(out) == 1 and line_flood.is_summary(out[0])
    assert " came 96 more times" in out[0]
    assert not gate.pending() and gate.flush() == []


def test_every_reader_sums_up_on_quiet():
    """(c) The PTY and pipe readers ask the gate on every silent read, the
    QProcess path arms a quiet timer after each read and stops it before
    the run's last lines and `finished`."""
    src = inspect.getsource(ArgyllRunner._pty_reader)
    assert "gate.idle()" in src
    src = inspect.getsource(ArgyllRunner._pipe_reader)
    assert "gate.idle()" in src
    assert "self._arm_flood_quiet()" in inspect.getsource(
        ArgyllRunner._on_ready_read)
    fin = inspect.getsource(ArgyllRunner._on_finished)
    assert fin.index("self._stop_flood_quiet()") < fin.index("gate.flush()")


def test_the_quiet_timer_emits_the_summary_in_order(qapp):
    """(c) On the QProcess path: the flood, then quiet, then the summary,
    with no new line needed (a real runner: the timer calls its method)."""
    from PyQt6.QtCore import QCoreApplication, QElapsedTimer
    r = ArgyllRunner(object())
    lines = []
    r.line_received.connect(lines.append)
    r._process = _Proc([(USB + "\n").encode() * 50])
    try:
        ArgyllRunner._on_ready_read(r)
        assert lines == [USB] * line_flood.SHOW
        t = QElapsedTimer()
        t.start()
        while len(lines) == line_flood.SHOW and t.elapsed() < 8000:
            QCoreApplication.processEvents()
        assert len(lines) == line_flood.SHOW + 1, lines
        assert line_flood.is_summary(lines[-1])
        assert " came 46 more times" in lines[-1]
    finally:
        r._stop_flood_quiet()
        r._process = None


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
