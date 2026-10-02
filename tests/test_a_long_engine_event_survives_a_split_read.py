"""A JSON event split across two pipe reads still arrives as ONE line.

Review P_review2_beta1, P-202-2: ``ArgyllRunner._on_ready_read`` emitted every
piece of every read as a line, so an engine event longer than one read (a
chart-mode ``chart_read``) came out as two halves, neither of which parses,
and the event was lost. Argyll's own prompts end without a newline and must
still show at once.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402


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


def _feed(r, chunks):
    r._process = _Proc(chunks)
    for _ in chunks:
        ArgyllRunner._on_ready_read(r)


def test_an_event_split_in_two_is_one_line(runner):
    event = json.dumps({"event": "chart_read", "values": list(range(4000))}).encode()
    line = b"\x07" + event + b"\n"
    _feed(runner, [b"Reading strip A\n" + line[:3000], line[3000:]])
    assert runner.lines[0] == "Reading strip A"
    assert len(runner.lines) == 2
    assert json.loads(runner.lines[1].strip("\x07"))["event"] == "chart_read"


def test_a_prompt_without_newline_shows_at_once(runner):
    _feed(runner, [b"Ready to read strip A, hit any key to continue: "])
    assert runner.lines == ["Ready to read strip A, hit any key to continue: "]


def test_a_held_fragment_is_flushed_when_the_process_ends(runner):
    _feed(runner, [b'{"event": "cut short'])
    assert runner.lines == []
    runner._process = _Proc([b""])
    runner._run_on_finish = None
    runner._run_on_line = None
    runner.finished = type("S", (), {"emit": lambda _s, c: None})()
    runner._process.readyReadStandardOutput = type("X", (), {"disconnect": lambda *_: None})()
    runner._process.finished = runner._process.readyReadStandardOutput
    ArgyllRunner._on_finished(runner, 0, None)
    assert runner.lines == ['{"event": "cut short']
