"""After "All Strips Read" and "Re-read Individual Strips", every read moves
the reader to the next strip (Knut, #182 6154440320, 4.3.5 beta 3).

    *"After I chose to re-read strips, I clicked on strip C and started
    reading. After every time a strip was read the next strip to read focus
    arrow did not move to next strip, but I had to manually select a strip.
    The focus arrows should by default jump to the next strip, when re-reading
    or refining (without a guided help ...) a measurement that has previously
    been finished. This applies to all chart types ... but not when refine /
    resume uses the refinement strips file for guided re-measurement."*

THE CAUSE. The engine reports ``all_done`` with every read of a complete
chart. In a session that COMPLETED the chart (a fresh read, or a resume that
read the last strip) every such ``all_done`` counted as news, and news holds
the reader where it is for the completion window, which had long been shown.
The tab now tells the manager when that window has been shown
(``note_completion_shown``), and from then on a read follows the beta-4 rule
(UMM "After a read: where the reader goes next").

Measured on screen with his run 2 and the real engine's replay instrument
(beta 4 report, M5): C -> D, D -> E, E -> F; before the fix C, C, C.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measure_manager import MeasureManager          # noqa: E402

STRIPS = ["A", "B", "C", "D"]


class _Runner:
    is_running = True

    def __init__(self):
        self.sent: list[str] = []

    def write_stdin(self, data):
        self.sent.append(data)


def _gotos(runner) -> list:
    out = []
    for raw in runner.sent:
        try:
            cmd = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if cmd.get("cmd") == "goto":
            out.append(cmd.get("strip"))
    return out


def _session(*, resume: bool, guided=None):
    """A session that has just read the chart's last unread strip."""
    r = _Runner()
    m = MeasureManager(r)
    m._engine_active = True
    m._spot_mode = False
    m._is_resume = resume
    m._chart_was_complete = False
    m._read_something = True
    m._completion_shown = False
    m._session_strips = [{"strip": s, "read": True} for s in STRIPS]
    if guided:
        m._guided_strips = list(guided)
        m._guided_state = "waiting"
    return m, r


def _feed(m, *events):
    for ev in events:
        m._handle_engine_line(json.dumps(ev), lambda _s: None)


def _read(strip):
    return {"event": "strip_read", "strip": strip,
            "patches": [{"loc": strip + "1"}]}


def _ready(strip):
    return {"event": "strip_ready", "strip": strip, "read": True,
            "all_done": True}


def _done_signals(m) -> list:
    got = []
    m.all_stripes_done.connect(lambda: got.append(1))
    return got


def test_before_the_window_the_completing_read_stays_put():
    """The read that completes the chart: its window decides (unchanged)."""
    for resume in (False, True):
        m, r = _session(resume=resume)
        done = _done_signals(m)
        _feed(m, _read("D"), _ready("D"))
        assert done, "completing the chart is news"
        assert _gotos(r) == []


def test_after_the_window_each_re_read_moves_to_the_next_strip():
    """Knut's sequence: Re-read Individual Strips, click C, read C, D, E."""
    for resume in (False, True):
        m, r = _session(resume=resume)
        m.note_completion_shown()
        _feed(m, _read("B"), _ready("B"))
        assert _gotos(r) == ["C"], (resume, _gotos(r))
        _feed(m, _ready("C"), _read("C"), _ready("C"))
        assert _gotos(r) == ["C", "D"], (resume, _gotos(r))


def test_the_last_strip_still_stays():
    m, r = _session(resume=False)
    m.note_completion_shown()
    _feed(m, _read("D"), _ready("D"))
    assert _gotos(r) == []


def test_guided_refinement_keeps_its_own_order():
    """The refinement strips file chooses the strips itself."""
    m, r = _session(resume=True, guided=["B", "D"])
    m.note_completion_shown()
    _feed(m, _read("B"), _ready("B"))
    assert "C" not in _gotos(r)


def test_a_new_session_forgets_it():
    """`start` resets the flag, so the next session's completing read is
    held for its own window again."""
    import inspect
    src = inspect.getsource(MeasureManager.start)
    assert "self._completion_shown = False" in src


def test_the_tab_tells_the_manager():
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_all_stripes_done)
    assert src.count("self._note_completion_to_manager()") == 2
