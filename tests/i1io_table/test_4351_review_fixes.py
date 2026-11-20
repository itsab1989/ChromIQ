"""4.3.51 fix round, after the independent safety review of fix/4.3.51-start (2026-11-20).

MUST-1. The reading after the START homing from the home line (``job._home_from_the_home_line``)
must find the arm at its resting place; until this round no test went red without that check,
because the simulator's homing always arrived. The simulator now has a homing that answers done
in its usual time and stops short ("short_homing", session_sim.FAULT_KINDS). With it: the job
stops with a doubt, sends nothing after that reading, offers no second homing, and the window
shows the stop page, never "The arm is at its resting place".
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_4351_one_start_rule import F1_PLUS, MOVES, _found
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl


# ---- MUST-1: a homing from the home line that reports done and stops short --------------------
@pytest.mark.parametrize("path", ["cal", "out"])
@pytest.mark.parametrize("pos", [(1098, 810), (1100, 400)])
def test_a_homing_that_stops_short_is_a_doubt_and_nothing_more_moves(tmp_path, path, pos):
    job, sim, p, r = _found(tmp_path, path, pos)
    sim.inject("short_homing", "i1")
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.kind == J.Kind.STOPPED and res.reason == "arm_not_where_expected", \
        (res.kind, res.reason, res.detail)
    # the recorded lines and the one reading after them, nothing else
    assert sim.received[n:] == F1_PLUS
    assert not tbl.REST_GUARD.contains(job._table.position_now)
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
    job, sim, p, r = _found(tmp_path, "cal", (1098, 810))
    sim.inject("short_homing", "i1", 0.25)
    p.drive(job.home_after_stop())
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
    assert p.page() == "refused"
    sim.sim.inject("short_homing", "i1")
    n = len(sim.sim.received)
    p.press("Bring the arm home")
    p.press("Go")
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
