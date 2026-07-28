"""#131 (Knut, 2026-07-28): the to-do items, each verified rather than assumed.

His instruction: *"Analyse best solution to create, test best candidates with
on-screen testing and verify solution works, do not guess if it is implemented
and working, but verify."*

The two behavioural items were reproduced against the **real** reading engine
before being changed, and re-measured afterwards — see the reproduction scripts
described in the issue comment. What is asserted here is the rule each fix
encodes, plus the wording that goes with it.
"""
from __future__ import annotations

import inspect
import json

import pytest

from workflow.measure_manager import MeasureManager


class _Runner:
    def __init__(self): self.out = []
    def write_stdin(self, d): self.out.append(d)
    def __getattr__(self, _n): return lambda *a, **k: None


@pytest.fixture
def manager():
    m = MeasureManager(_Runner())
    m._engine_active = True
    return m


def _session(manager, all_read: bool):
    manager._handle_engine_line(json.dumps({
        "event": "session_start",
        "strips": [{"strip": s, "read": all_read} for s in "ABC"],
    }), lambda _x: None)


# ---- "All strips read" during a resume ------------------------------------
def test_a_chart_that_was_already_complete_never_announces_completion(manager):
    """Re-reading a strip of a finished chart completes nothing — it was
    complete before you started. Knut got the completion window every time he
    answered a strip window."""
    manager._is_resume = True
    _session(manager, all_read=True)
    fired = []
    manager.all_stripes_done.connect(lambda: fired.append(1))

    manager._handle_engine_line(json.dumps(
        {"event": "strip_read", "strip": "A", "patches": []}), lambda _x: None)
    manager._handle_engine_line(json.dumps(
        {"event": "strip_ready", "strip": "A", "all_done": True}), lambda _x: None)

    assert fired == []


def test_finishing_a_partly_measured_chart_still_announces_it(manager):
    """A genuine completion, and it must still be reported."""
    manager._is_resume = True
    _session(manager, all_read=False)
    fired = []
    manager.all_stripes_done.connect(lambda: fired.append(1))

    manager._handle_engine_line(json.dumps(
        {"event": "strip_read", "strip": "C", "patches": []}), lambda _x: None)
    manager._handle_engine_line(json.dumps(
        {"event": "strip_ready", "strip": "A", "all_done": True}), lambda _x: None)

    assert fired == [1]


def test_a_normal_first_measurement_is_unaffected(manager):
    manager._is_resume = False
    _session(manager, all_read=False)
    fired = []
    manager.all_stripes_done.connect(lambda: fired.append(1))
    manager._handle_engine_line(json.dumps(
        {"event": "strip_ready", "strip": "A", "all_done": True}), lambda _x: None)
    assert fired == [1]


def test_the_state_is_reset_for_each_measurement(manager, tmp_path):
    from workflow.measure_manager import MeasureParams
    manager._chart_was_complete = True
    ti1 = tmp_path / "c.ti1"; ti1.write_text("CTI1")
    try:
        manager.start(MeasureParams(ti1_path=ti1, instrument="1"),
                      on_line=lambda _s: None, on_finish=lambda _c: None)
    except Exception:      # noqa: BLE001 — no ArgyllCMS here
        pass
    assert manager._chart_was_complete is False


# ---- the failure window in patch-by-patch mode ----------------------------
def test_the_failure_window_speaks_of_patches_in_patch_mode():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_strip_error)
    assert 'tr("Patch Read Failed")' in src
    assert "The patch could not be read:" in src
    assert "Skip Patch" in src
    # "Finish Without This Patch" is gone: on the last one it did exactly what
    # Save Partial & Quit does (Knut, #131 2026-07-28).
    assert "Finish Without This Patch" not in src


def test_the_patch_mode_advice_does_not_describe_a_swipe():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_strip_error)
    i = src.index("The patch could not be read:")
    section = src[i:i + 500]
    assert "swipe" not in section.lower()
    assert "flat on the patch" in section


def test_the_speed_verdict_is_silent_in_patch_mode():
    """Its advice is about swipes, and there is no swipe to judge."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._report_failed_strip_pace)
    assert '_spot_session' in src
    clock = src.index("self._scan_started_at = None")
    guard = src.index("_spot_session")
    assert clock < guard, "the clock must still be consumed before returning"


# ---- seeing which strips you have re-read ---------------------------------
def test_the_times_panel_says_it_shows_this_session():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._refresh_pace_panel)
    assert "read in this session" in src
    assert "refining" in src
