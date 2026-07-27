"""#131 (Knut, 2026-07-27): a resume must not announce "All stripes read".

He finished a chart, went to Build Profile, came back, ticked *Refine / resume
existing measurement* and pressed Start Measurement — and the completion window
appeared at once, before he had re-read a single strip. It appears because that
is the literal truth: on a resume the chart IS complete, so chartread says so
the moment it offers the strip menu. Saying it there is useless and alarming —
it is the *finished* window, offering to move on, put in front of somebody who
has just sat down to refine one strip. Worse, taking its "Re-read Stripes" way
out left him looking at a preview with nothing on it.

During a resume the announcement now waits until something has actually been
read. A normal run is unaffected.
"""
from __future__ import annotations

import json

import pytest

from workflow.measure_manager import MeasureManager, MeasureParams


class _Runner:
    def __init__(self):
        self.sent = []

    def write_stdin(self, data):
        self.sent.append(data)

    def __getattr__(self, _name):
        return lambda *a, **k: None


@pytest.fixture
def manager():
    return MeasureManager(_Runner())


def _arm(manager, *, resume: bool, engine: bool) -> list:
    manager._is_resume = resume
    manager._read_something = False
    manager._engine_active = engine
    seen = []
    manager.all_stripes_done.connect(lambda: seen.append(True))
    return seen


READY_ALL_DONE = json.dumps({"event": "strip_ready", "strip": "A",
                             "all_done": True})
STRIP_READ = json.dumps({"event": "strip_read", "strip": "A", "patches": []})
# chartread's own words, which is what the console path matches.
CONSOLE_ALL_DONE = "All rows read"
CONSOLE_STRIP_OK = "Strip read OK"


# ---- the engine path -------------------------------------------------------
def test_a_resume_says_nothing_before_anything_is_read(manager):
    seen = _arm(manager, resume=True, engine=True)

    manager._handle_engine_line(READY_ALL_DONE, lambda _s: None)

    assert seen == [], "the completion window must not open on arrival"


def test_a_resume_announces_it_once_a_strip_has_been_read(manager):
    seen = _arm(manager, resume=True, engine=True)

    manager._handle_engine_line(STRIP_READ, lambda _s: None)
    manager._handle_engine_line(READY_ALL_DONE, lambda _s: None)

    assert seen == [True], "after a real re-read it is genuine news"


def test_a_normal_run_is_untouched(manager):
    seen = _arm(manager, resume=False, engine=True)

    manager._handle_engine_line(READY_ALL_DONE, lambda _s: None)

    assert seen == [True]


# ---- stock chartread -------------------------------------------------------
def test_stock_chartread_follows_the_same_rule(manager):
    seen = _arm(manager, resume=True, engine=False)

    manager._handle_line(CONSOLE_ALL_DONE, lambda _s: None)
    assert seen == []

    manager._handle_line(CONSOLE_STRIP_OK, lambda _s: None)
    manager._handle_line(CONSOLE_ALL_DONE, lambda _s: None)
    assert seen == [True]


def test_a_normal_stock_run_still_announces_it(manager):
    seen = _arm(manager, resume=False, engine=False)
    manager._handle_line(CONSOLE_ALL_DONE, lambda _s: None)
    assert seen == [True]


# ---- the flag is per session ----------------------------------------------
def test_starting_a_measurement_forgets_the_previous_one(manager, tmp_path):
    """Otherwise the second resume in one sitting would behave like the first
    had already read something."""
    manager._read_something = True
    ti1 = tmp_path / "c.ti1"
    ti1.write_text("CTI1")
    try:
        manager.start(MeasureParams(ti1_path=ti1, instrument="1", resume=True),
                      on_line=lambda _s: None, on_finish=lambda _c: None)
    except Exception:      # noqa: BLE001 — no ArgyllCMS here; the reset is what matters
        pass
    assert manager._read_something is False
