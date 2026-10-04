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
    summaries = [ln for ln in lines if ln.startswith("[ChromIQ: the line")]
    hidden = sum(int(s.split(" came ")[1].split()[0]) for s in summaries)
    assert line_flood.SHOW + hidden == 127_500
    assert USB in summaries[0]
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
