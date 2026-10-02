"""After a strip is read, the reader moves on to the next strip (Knut, #182
5956210745, beta 3).

    *"when resuming or re-reading a chart that previously was completed, and
    when I re-read a strip (either from the start or from the strip I
    select): the arrows on top and bottom of the preview that indicates the
    current strip being read is not moving to the next strip, so I have to
    manually click the next strip. When measurement of a strip is completed,
    the focus should jump to the next strip after the one I completed … This
    should be default behaviour, unless warning messages pop up where I am
    asked if I want to retry."*

THE ARROWS WERE RIGHT, AND THE READER REALLY WAS STILL ON THE OLD STRIP. The
preview follows `strip_ready`, and on a complete chart the engine sends
`strip_ready` for the strip it has just read: after a good read chartread
"skips to the next unread" (`incflag = 2`), a search that goes once round the
chart and stops where it began when nothing is unread. His log, every strip:

    {"event":"strip_read","strip":"A",…}
    {"event":"strip_ready","strip":"A","read":true,"all_done":true}
    send_key '{"cmd": "goto", "strip": "B"}'          ← his click, 46 s later

So ChromIQ now sends the goto itself, unless a window is asking whether to
read the strip again, or something else has already chosen the next strip.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measure_manager import MeasureManager          # noqa: E402

STRIPS = ["A", "B", "C"]


class _Runner:
    is_running = True

    def __init__(self):
        self.sent: list[str] = []

    def write_stdin(self, data):
        self.sent.append(data)


def _gotos(runner) -> list[str]:
    out = []
    for raw in runner.sent:
        try:
            cmd = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if cmd.get("cmd") == "goto":
            out.append(cmd.get("strip"))
    return out


def _session(*, complete=True, guided=None, question=None):
    """A manager mid-session on a chart whose strips are all read."""
    r = _Runner()
    m = MeasureManager(r)
    m._engine_active = True
    m._spot_mode = False
    m._is_resume = True
    m._chart_was_complete = complete
    m._session_strips = [{"strip": s, "read": complete} for s in STRIPS]
    if guided:
        m._guided_strips = list(guided)
        m._guided_state = "waiting"
    if question is not None:
        m.set_question_probe(question)
    return m, r


def _feed(m, *events):
    for ev in events:
        m._handle_engine_line(json.dumps(ev), lambda _s: None)


def _read(strip):
    return {"event": "strip_read", "strip": strip, "patches": [{"loc": strip + "1"}]}


def _ready(strip, all_done=True):
    return {"event": "strip_ready", "strip": strip, "read": True,
            "all_done": all_done}


# ---- the move itself ---------------------------------------------------------

def test_a_re_read_strip_moves_the_reader_to_the_next_strip():
    """Knut's case: re-read A on a complete chart, the engine re-arms A."""
    m, r = _session()
    _feed(m, _read("A"), _ready("A"))
    assert _gotos(r) == ["B"], (
        "after strip A was read the reader stayed on A, so the preview arrows "
        "never moved to B")


def test_each_strip_moves_on_in_turn():
    m, r = _session()
    _feed(m, _read("A"), _ready("A"), _ready("B", True),
          _read("B"), _ready("B"))
    assert _gotos(r) == ["B", "C"]


def test_the_last_strip_has_nowhere_further_to_go():
    m, r = _session()
    _feed(m, _read("C"), _ready("C"))
    assert _gotos(r) == [], "there is no strip after the last one"


def test_where_the_engine_moved_by_itself_it_is_left_alone():
    """A chart with strips unread: the engine went to the next unread."""
    m, r = _session(complete=False)
    _feed(m, _read("A"), _ready("C", all_done=False))
    assert _gotos(r) == []


def test_opening_a_session_moves_nothing():
    """The first menu of a resumed chart is not the end of a read."""
    m, r = _session()
    _feed(m, _ready("A"))
    assert _gotos(r) == []


def test_completing_the_chart_leaves_the_completion_window_alone():
    """The last unread strip read in this session: All Strips Read is news,
    and that window decides what happens next."""
    m, r = _session(complete=False)
    m._is_resume = False
    _feed(m, _read("B"), _ready("B"))
    assert _gotos(r) == []


def test_guided_refinement_keeps_its_own_navigation():
    m, r = _session(guided=["A", "C"])
    _feed(m, _read("A"), _ready("A"))
    assert _gotos(r) == ["C"], (
        "guided refinement goes to ITS next strip, and nothing else may be "
        "sent alongside it")


def test_the_last_guided_strip_ends_guided_refinement_where_it_is():
    """Guided refinement's last strip opens its own completion window; the
    strip read UNDER guided refinement must not then be moved on from."""
    m, r = _session(guided=["A"])
    _feed(m, _read("A"), _ready("A"))
    assert m._guided_state == "idle_done"
    assert _gotos(r) == []


# ---- a question window may ask for the strip again --------------------------

def test_read_it_again_sent_before_the_menu_wins():
    """A window answered 'read it again' before strip_ready was processed."""
    m, r = _session()
    _feed(m, _read("A"))
    m.goto_strip("A")                          # "Re-read" in the window
    _feed(m, _ready("A"))
    assert _gotos(r) == ["A"], "the automatic move overrode the user's re-read"


def test_the_move_waits_for_an_open_window_and_follows_keep():
    open_now = [True]
    m, r = _session(question=lambda: open_now[0])
    _feed(m, _read("A"), _ready("A"))
    assert _gotos(r) == [], "moved on while a window was asking about strip A"
    open_now[0] = False                         # "Keep it" / "Continue anyway"
    m.release_held_strip_move()
    assert _gotos(r) == ["B"]
    m.release_held_strip_move()
    assert _gotos(r) == ["B"], "released twice"


def test_the_move_waits_for_an_open_window_and_yields_to_re_read():
    open_now = [True]
    m, r = _session(question=lambda: open_now[0])
    _feed(m, _read("A"), _ready("A"))
    open_now[0] = False
    m.goto_strip("A")                           # "Re-read" sends its goto first
    m.release_held_strip_move()
    assert _gotos(r) == ["A"]


def test_a_swipe_already_started_cancels_a_held_move():
    open_now = [True]
    m, r = _session(question=lambda: open_now[0])
    _feed(m, _read("A"), _ready("A"), {"event": "scan_started"})
    open_now[0] = False
    m.release_held_strip_move()
    assert _gotos(r) == []


def test_a_click_on_another_strip_still_wins():
    m, r = _session()
    _feed(m, _read("A"), _ready("A"))
    m.goto_strip("C")                            # manual selection
    assert _gotos(r) == ["B", "C"]


# ---- the tab: arrows follow, windows hold the move -----------------------------

class _Settings:
    def __init__(self):
        self._d = {"appearance": "dark", "chartread_engine": "chromiq"}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


@pytest.fixture
def tab(qapp):
    from PyQt6.QtCore import QRect

    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    t = TabMeasure(ArgyllRunner(s), s)
    t._page_stripe_rects = [[QRect(0, i * 30, 100, 20) for i in range(3)]]
    t._strips_per_page = [3]
    mgr = t._manager
    sent: list[str] = []
    mgr._runner.write_stdin = sent.append      # instance attribute, no process
    mgr._engine_active = True
    mgr._chart_was_complete = True
    mgr._is_resume = True
    mgr._session_strips = [{"strip": x, "read": True} for x in STRIPS]
    t._sent = sent
    yield t
    t.deleteLater()


def _gotos_of(sent):
    class _R:
        pass
    r = _R()
    r.sent = sent
    return _gotos(r)


def test_the_preview_arrow_follows_the_reader_to_the_next_strip(tab, monkeypatch):
    monkeypatch.setattr(type(tab._runner), "is_running",
                        property(lambda self: True))
    _feed(tab._manager, _read("A"), _ready("A"))
    assert _gotos_of(tab._sent) == ["B"]
    _feed(tab._manager, _ready("B"))            # what the engine answers
    assert tab._preview._active_stripe == 1, "the arrows did not move to B"


@pytest.mark.parametrize("answer, expected", [("keep", ["B"]),
                                               ("reread", ["A"])])
def test_a_measurement_window_holds_the_move_until_answered(
        tab, qapp, monkeypatch, answer, expected):
    """strip_ready arrives INSIDE the window's own event loop, as it does with
    Strip Read Quickly and Strip may be misaligned."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QDialog
    monkeypatch.setattr(type(tab._runner), "is_running",
                        property(lambda self: True))
    mgr = tab._manager
    _feed(mgr, _read("A"))
    dlg = QDialog(tab)
    seen_while_open: list = []

    def _inside():
        _feed(mgr, _ready("A"))
        seen_while_open.extend(_gotos_of(tab._sent))
        dlg.accept()
    QTimer.singleShot(0, _inside)
    tab._exec_measurement_window(dlg)
    if answer == "reread":
        mgr.goto_strip("A")
    for _ in range(5):
        qapp.processEvents()
    assert seen_while_open == [], "moved on while the window was still asking"
    assert _gotos_of(tab._sent) == expected


# ---- the engine's own behaviour, measured on the real helper -----------------

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402


@pytest.mark.slow
@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_the_engine_itself_re_arms_the_strip_it_has_just_read(tmp_path):
    """Pins WHY the app has to move: the engine stays on a complete chart.

    If a future engine moves on by itself, this fails, and the app's move
    becomes a second, redundant step to remove.
    """
    targen = shutil.which("targen") or "/Applications/Argyll/bin/targen"
    if not Path(targen).exists():
        pytest.skip("Argyll targen not available")
    base = tmp_path / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-f60", str(base)],
                   check=True, capture_output=True, cwd=tmp_path, timeout=120)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=False)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay)
    s = ReplaySession(base, replay)
    try:
        labels = [x["strip"] for x in s.wait_event("session_start")["strips"]]
        assert len(labels) >= 2
        for _ in labels:                       # read the whole chart
            i = s.event_index()
            s.send(cmd="swipe")
            s.wait_event("strip_read", after=i)
            s.wait_event("strip_ready", after=i)
        i = s.event_index()
        s.send(cmd="goto", strip=labels[0])
        s.wait_event("strip_ready", after=i, strip=labels[0])
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        ev = s.wait_event("strip_ready", after=i)
        assert ev["strip"] == labels[0] and ev["all_done"] is True
        # …and the goto the app now sends arms the next strip.
        i = s.event_index()
        s.send(cmd="goto", strip=labels[1])
        assert s.wait_event("strip_ready", after=i, strip=labels[1])
    finally:
        s.proc.kill()
        s.finish()
