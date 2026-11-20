"""4.3.51 fix round, after the independent safety review of fix/4.3.51-start (2026-11-20), as it
stands since 4.3.52's START rule by state (test_4352_start_rule_by_state.py).

MUST-1. The reading after the START homing must find the arm at its resting place. The simulator
has a homing that answers done in its usual time and stops short ("short_homing",
session_sim.FAULT_KINDS). With it: the job stops with a doubt, sends nothing after that reading,
offers no second homing, and the window shows the failure page, never "The arm is at its resting
place". 4.3.52: the same from EVERY place (4.3.51 had it for the home line only).

4.3.51's edges of the home line (SHOULD-1, SHOULD-3) are gone with the home line itself: since
4.3.52 the place decides nothing but the back strip beside the white tile's holder, whose edges
are pinned in test_4352_start_rule_by_state.test_the_back_strip_is_the_one_physical_place, and
re-checked right before i1 below.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_4352_start_rule_by_state import F1_PLUS, MOVES
from tests.i1io_table.test_job_reading import job_for
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl


# ---- MUST-1: a homing that reports done and stops short ----------------------------------------
@pytest.mark.parametrize("path", ["cal", "out"])
@pytest.mark.parametrize("pos", [(1098, 810), (1100, 400), (800, 800), (0, 3300)])
def test_a_homing_that_stops_short_is_a_doubt_and_nothing_more_moves(tmp_path, path, pos):
    script = {J.Confirm.READY_TO_OPEN: "arm out"} if path == "out" else None
    job, sim, helper, run, p = job_for(tmp_path, script, real_table=False)
    sim.pos = [float(pos[0]), float(pos[1])]
    assert p.drive(job.open()).ok
    sim.inject("short_homing", "i1")
    n = len(sim.received)
    res = p.drive(job.calibrate() if path == "cal" else job.where_is_the_arm())
    assert res.kind == J.Kind.STOPPED and res.reason == "arm_not_where_expected", \
        (res.kind, res.reason, res.detail)
    # the reading that found it, the recorded lines and the one reading after them, nothing else
    assert sim.received[n:] == [";p025"] + F1_PLUS
    assert not tbl.REST_GUARD.contains(job._table.position_now)
    assert job.start_homing_failed
    # nothing more moves: no second homing, no usual homing, no step that moves
    assert job.way_back() == J.WayBack.OPEN_I1PROFILER_ONCE
    m = len(sim.received)
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert job.home().kind == J.Kind.REFUSED
    for s in ("calibrate", "align"):
        p.drive(H.step(job, s))
    assert not [ln for ln in sim.received[m:] if ln[1:3] in MOVES]
    assert job._table.closed_reason is not None
    assert sim.violations == []


def test_the_simulators_short_homing_stops_on_the_way_it_came(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    sim.pos = [1098.0, 810.0]
    assert p.drive(job.open()).ok
    sim.inject("short_homing", "i1", 0.25)
    p.drive(job.calibrate())
    x, y = sim.pos
    assert 1098 <= x <= 1102 and 190 <= y <= 220      # a quarter of the way left, about Y 203


def test_the_window_says_the_truth_after_a_homing_that_stops_short(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    from tests.i1io_table.window_sim import WindowSim
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, sim=WindowSim(pos=[1098.0, 810.0]),
        asking=False)
    assert p.drive_until("ready_to_open") == "ready_to_open"
    win._tick_widgets[1].setChecked(True)
    p.press("The arm is out")
    assert p.page() == "home_at_start"
    sim.sim.inject("short_homing", "i1")
    n = len(sim.sim.received)
    p.press("Bring the arm home, my hands are away")
    p.idle()
    assert sim.sim.received[n:] == F1_PLUS
    assert "home_after_stop_done" not in win.pages_shown
    assert p.page() == "stopped", win.pages_shown[-3:]
    text = win._text.text()
    # what is true: the homing did not bring it home, and where the arm reports now
    assert "ChromIQ could not bring the arm home" in text
    x, y = (round(v) for v in sim.sim.pos)
    assert f"X {x}, Y " in text and "sends nothing more to the table" in text
    assert "ChromIQ has brought the arm home" not in text
    assert "Go on" not in p.labels() and "Bring the arm home" not in p.labels()
    m = len(sim.sim.received)
    for label in p.labels():
        if label not in ("End measurement", "Close"):
            p.press(label)
            p.idle()
            break
    assert not [ln for ln in sim.sim.received[m:] if ln[1:3] in MOVES]


# ---- the back strip is checked again right before the homing ------------------------------------
def test_the_back_strip_is_checked_again_right_before_the_homing(tmp_path):
    """Found on the home line at (1091, 400); the reading right before i1 says (1087, 400):
    within the 5-unit "arm moved" compare, but in the back strip. Refused; nothing after s0 p0."""
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.GO: "back"}, real_table=False)
    sim.pos = [1091.0, 400.0]
    assert p.drive(job.open()).ok
    r = p.drive(job.calibrate())
    assert r.reason == "person_chose_back" and job.way_back() == J.WayBack.HOME_AFTER_STOP
    sim.pos = [1087.0, 400.0]
    p.script[J.Confirm.GO] = "yes"
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert not res.ok and res.reason == "arm_in_the_back_strip", (res.kind, res.reason)
    assert sim.received[n:] == [";s022", ";p025"]


# ---- the review's other planted faults that stayed green (P12, P14) -----------------------------
@pytest.mark.parametrize("answer", ["yes", "arm out"])
def test_a_just_switched_on_table_is_refused_for_its_own_reason(tmp_path, answer):
    """P12: "table_not_started" removed from the offer's reasons stayed green, because a cold
    table never has a fresh reading (no p0 before i0), so the offer was refused anyway, for the
    wrong reason. The reason is what the app log and the page say: it is pinned here."""
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: answer},
                                       real_table=False, cold=True)
    sim.pos = [1098.0, 810.0]
    assert p.drive(job.open()).ok
    n = len(sim.received)
    res = job.home_after_stop()
    assert res.kind == J.Kind.REFUSED and res.reason == "table_not_started"
    assert sim.received[n:] == []


def test_the_fallback_timer_stops_when_the_line_is_written(qapp, qtbot, monkeypatch):
    """P14: the flush without its cancel stayed green, because the one timer is restarted at
    every queue and finds nothing held when it fires. Harmless, but the code says the timer is
    "stopped as soon as the line is written": pinned, so no timer runs for nothing."""
    from workflow.measure_manager import MeasureManager

    class _R:
        is_running = False
    m = MeasureManager(_R())
    m.END_LOG_FALLBACK_MS = 5000
    monkeypatch.setattr(m, "_log_measure_end", lambda p, c: None)
    m._queue_measure_end_log("first", 0)
    assert m._end_log_timer.isActive()
    m.flush_measure_end_log()
    assert not m._end_log_timer.isActive()


# ---- SHOULD-2: the offer's answers in one order, in the panel and in the pop-up -----------------
def test_the_start_page_shows_bring_the_arm_home_first(qtbot, monkeypatch, tmp_path,
                                                       settings):  # noqa: F811
    """After "Not now" the page that offers the homing places the confirming answer first, in
    the panel and in the pop-up."""
    from PyQt6.QtWidgets import QDialogButtonBox

    from tests.i1io_table.window_sim import WindowSim
    from ui import i1io_table_window as W
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, sim=WindowSim(pos=[1098.0, 810.0]),
        asking=False)
    assert p.drive_until("ready_to_open") == "ready_to_open"
    win._tick_widgets[1].setChecked(True)
    p.press("The arm is out")
    assert p.page() == "home_at_start"
    p.press("Not now")
    p.idle()
    assert p.page() == "refused"
    assert p.labels() == ["Bring the arm home", "End measurement"]
    R = QDialogButtonBox.ButtonRole
    assert W.answer_role("Bring the arm home") == R.AcceptRole
    assert W.answer_role("End measurement") == R.RejectRole
    assert not [ln for ln in sim.sim.received if ln[1:3] in MOVES]
