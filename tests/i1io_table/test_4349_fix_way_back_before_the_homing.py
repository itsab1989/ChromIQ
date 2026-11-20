"""4.3.49 fix round (independent safety review 449, MUST-1): "Bring the arm home" after the creep
met the table's front end must WORK, not only be offered.

4.3.49-4.3.51 sent the homing's i1 only where a recorded homing starts and took a held arm
further forward back along the way it came first. 4.3.52 (the project owner, 2026-11-20: "do you
really think it matters for i1profiler or the table how far out the arm is whether the app brings
it to home or not?"): i1Profiler homes a held arm directly from where it stands, so ChromIQ does
too. The tests keep the reviewer's case (his exact aims of 19 Nov 2026, a simulated front end at
Y 3140, the creep stopped at (x, 3140)) and prove the homing now goes straight home from there:
the hands-off GO, then i1Profiler's end of a job (s0 p0 i1 s0 f0 f4 f4 p0), no move before it,
at rest after it.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_4349_acceptance_his_sheet_and_wider import (CROSSES_1, CROSSES_2,
                                                                        _through_first_row)
from workflow.i1io.table import caps as cp
from workflow.i1io.table import job as J


def _stalled(tmp_path, aims=CROSSES_1, front_end=3140):
    out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), aims, front_end=front_end)
    step, kind, reason, detail = out[-1]
    assert (step, kind, reason) == ("creep", J.Kind.REFUSED, "creep_step_did_not_arrive"), out
    assert job.only_home and sim.violations == []
    return job, sim, p, detail


def _lines(sim, since):
    return [ln for ln in sim.received[since:]]


HOMING_END = [";s022", ";p025", ";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]


@pytest.mark.parametrize("aims", [CROSSES_1, CROSSES_2], ids=["round 1", "round 2"])
def test_bring_the_arm_home_after_the_creep_met_the_front_end_goes_straight_home(tmp_path, aims):
    job, sim, p, detail = _stalled(tmp_path, aims)
    stall = (sim.pos[0], sim.pos[1])
    assert stall[1] == pytest.approx(3140)
    assert job.way_back() == J.WayBack.HOME_OFFERED
    n = len(sim.received)
    k = len(p.asked)
    r = p.drive(job.home())
    assert r.kind == J.Kind.OK, (r.reason, r.detail, sim.violations)
    assert sim.violations == [], sim.violations
    assert job.at_rest() and sim.pos[1] <= 250
    # the hands-off GO is asked before anything moves, nothing else is asked (no hand pull)
    assert [(s, c, sent) for s, c, _d, sent, _m in p.asked[k:]] == [("home", J.Confirm.GO, n)]
    # the wire: i1Profiler's end of a job from where the arm stands, no move before it
    assert _lines(sim, n) == HOMING_END
    assert job.way_back_moves == []


def test_the_homing_is_never_sent_from_the_back_strip_and_a_free_arm_keeps_its_region():
    """The i1 itself: a held arm from anywhere but the back strip (4.3.52); a free arm only from
    the measuring area's raw box or near rest (a state rule: the one recorded failed homing was a
    free arm)."""
    for p in [(0, 3114), (0, 3115), (0, 3230), (0, 3400), (2507, 1429), (-1500, 2000)]:
        assert J.homing_starts_here(p, False), p
    assert not J.homing_starts_here((1058, 317), False)
    assert not J.homing_starts_here((0, 3000), True)               # a free arm: AREA_RAW only
    assert J.homing_starts_here((0, 2700), True)


def test_a_homing_from_the_front_that_fails_sends_nothing_more(tmp_path):
    job, sim, p, _d = _stalled(tmp_path)
    n = len(sim.received)
    sim.inject("status", "i1", 3)
    r = p.drive(job.home())
    assert r.kind != J.Kind.OK
    sent = sim.received[n:]
    assert sent == HOMING_END[:len(sent)] and sent.count(";i12b") == 1
    assert job.state().sending_closed
    assert job.way_back() in (J.WayBack.OPEN_I1PROFILER_ONCE, J.WayBack.SWITCH_OFF_UNFINISHED)
    before = len(sim.received)
    assert p.drive(job.home()).kind == J.Kind.REFUSED
    assert len(sim.received) == before
    assert sim.violations == []


def test_the_page_after_the_failed_way_back_says_switch_off_or_open_i1profiler():
    """What the person reads then (the window's way back after a doubt): End measurement, then
    i1Profiler once; or, with a movement that may be unfinished, the power switch."""
    from workflow import measurement_messages as M
    body = M.M_I1IO_DRIVE_STOPPED_END_FIRST.body
    assert "i1Profiler" in body and "End measurement" in body
    assert "power switch" in M.M_I1IO_DRIVE_SWITCH_OFF.body


def test_a_held_arm_on_a_front_row_goes_straight_home(tmp_path):
    """The other way into the front zone: the job read rows in front of Y 3114 and ends there.
    4.3.52: the homing goes straight home from there, with no move before it."""
    out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), CROSSES_1)
    assert all(k == J.Kind.OK for _s, k, _r, _d in out), out
    for _ in range(40):
        if not job.rows_left():
            break
        r = p.drive(job.read_row())
        assert r.kind == J.Kind.OK, (r.reason, r.detail)
    assert not job.rows_left()
    n = len(sim.received)
    r = p.drive(job.home())
    assert r.kind == J.Kind.OK, (r.reason, r.detail, sim.violations)
    assert sim.violations == [] and job.at_rest()
    assert _lines(sim, n) == HOMING_END


def test_caps_hold_the_way_back():
    """The caps keep 4.3.49's room for a way back (an upper bound only; nothing uses it now)."""
    assert cp.WAY_BACK == (3 * cp.WAY_BACK_MOVES_MAX, cp.WAY_BACK_MOVES_MAX)
    assert cp.WAY_BACK_MOVES_MAX <= 4
