"""4.3.49 fix round (independent safety review 449, MUST-1): "Bring the arm home" after the creep
met the table's front end must WORK, not only be offered.

The homing's i1 is sent only where a recorded homing starts (job.homing_starts_here: 4.3.48's
held region, the front zone up to Y 3114). A held arm further forward is first taken back along
the way it came, only to places computed moves of this sitting verifiably arrived at, in the
recorded form (m0 at 300, each arrival read): the last such place first, then back to the most
recent one a homing may start from. A move back that does not arrive is a doubt: nothing more is
sent, and the page says to switch the table off or open i1Profiler once.

The reviewer's case: his exact aims (19 Nov 2026, round 1), a simulated front end at Y 3230
(invented: no recording shows the real end); the creep stops at (x, 3230), "about N mm short".
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_4349_acceptance_his_sheet_and_wider import (CROSSES_1, CROSSES_2,
                                                                        _through_first_row)
from workflow.i1io.table import caps as cp
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J


def _stalled(tmp_path, aims=CROSSES_1, front_end=3230):
    out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), aims, front_end=front_end)
    step, kind, reason, detail = out[-1]
    assert (step, kind, reason) == ("creep", J.Kind.REFUSED, "creep_step_did_not_arrive"), out
    assert job.only_home and sim.violations == []
    return job, sim, p, detail


def _lines(sim, since):
    return [ln for ln in sim.received[since:]]


@pytest.mark.parametrize("aims", [CROSSES_1, CROSSES_2], ids=["round 1", "round 2"])
def test_bring_the_arm_home_after_the_creep_met_the_front_end_arrives_at_rest(tmp_path, aims):
    job, sim, p, detail = _stalled(tmp_path, aims)
    stall = (sim.pos[0], sim.pos[1])
    assert stall[1] == pytest.approx(3230)
    # the page offers the homing, and pressing it now works
    assert job.way_back() == J.WayBack.HOME_OFFERED
    n = len(sim.received)
    k = len(p.asked)
    r = p.drive(job.home())
    assert r.kind == J.Kind.OK, (r.reason, r.detail, sim.violations)
    assert sim.violations == [], sim.violations
    assert job.at_rest() and sim.pos[1] <= 250
    # the hands-off GO is asked before anything moves, nothing else is asked (no hand pull)
    assert [(s, c, sent) for s, c, _d, sent, _m in p.asked[k:]] == [("home", J.Confirm.GO, n)]
    sent = _lines(sim, n)
    # the wire, in order: the homing's own s0 p0, then the way back (m0 p0 per move), then the
    # homing's s0 p0 again and its recorded lines
    cids = [ln[1:3] for ln in sent]
    assert cids[:2] == ["s0", "p0"]
    i1 = cids.index("i1")
    assert cids[i1 - 2:i1] == ["s0", "p0"]
    moves = [ln for ln in sent[:i1] if ln[1:3] == "m0"]
    assert 1 <= len(moves) <= cp.WAY_BACK_MOVES_MAX
    targets = [geo.decode_xyv(ln.encode())[1:] for ln in moves]
    # every target is a place the creep (or the move before it) verifiably arrived at, at
    # speed 300, and the last one is where a recorded homing starts; never forward
    assert all(v == 300 for _x, _y, v in targets)
    ys = [y for _x, y, _v in targets]
    assert ys == sorted(ys, reverse=True) and ys[0] < stall[1]
    assert J.homing_starts_here(targets[-1][:2], False)
    assert not J.homing_starts_here(targets[0][:2], False)      # 3223 lies in front of 3114
    # the first move goes back to the last place the creep arrived at (5 mm steps from 2723)
    assert ys[0] == detail["front_y"]
    # the homing's i1 is sent from inside the region 4.3.48 homed from
    assert sim.pos[1] <= 250
    assert job.way_back_moves and job.way_back_moves[-1]["to"][-1] == list(targets[-1][:2])


def test_the_homing_is_never_sent_from_where_no_recorded_homing_starts(tmp_path):
    """The i1 itself: only from 4.3.48's region (plant G4 of the review: unbounded, was green)."""
    assert J.homing_starts_here((0, 3114), False)
    assert not J.homing_starts_here((0, 3115), False)
    assert not J.homing_starts_here((0, 3230), False)
    assert not J.homing_starts_here((0, 3230), False, 3273)        # the aimed cap widens nothing
    assert not J.homing_starts_here((0, 3000), True)               # a free arm: AREA_RAW only
    job, sim, p, _d = _stalled(tmp_path)
    # with no way back (nothing arrived in this sitting): refused, nothing is sent
    job.arrived = []
    job._way_back_cache = None
    n = len(sim.received)
    r = p.drive(job.home())
    assert r.kind == J.Kind.REFUSED and r.reason == "homing_not_from_here", r
    assert sim.received[n:] == []


def test_a_move_back_that_does_not_arrive_sends_nothing_more_and_says_switch_off_or_i1profiler(
        tmp_path):
    job, sim, p, _d = _stalled(tmp_path)
    n = len(sim.received)
    sim.inject_at(n + 2, "blocked")          # s0, p0, then the first move back: it stops 30 mm off
    r = p.drive(job.home())
    assert r.kind != J.Kind.OK
    sent = sim.received[n:]
    assert [ln[1:3] for ln in sent][:3] == ["s0", "p0", "m0"]
    assert "i1" not in [ln[1:3] for ln in sent]
    assert job.state().sending_closed
    # nothing more may be sent: no homing offered any more
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


def test_a_held_arm_on_a_front_row_is_brought_back_before_the_homing(tmp_path):
    """The other way into the front zone: the job read rows in front of Y 3114 and ends there.
    The homing then goes back to the most recent place in the region a homing starts from."""
    out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), CROSSES_1)
    assert all(k == J.Kind.OK for _s, k, _r, _d in out), out
    fronts = []
    for _ in range(40):
        if not job.rows_left():
            break
        r = p.drive(job.read_row())
        assert r.kind == J.Kind.OK, (r.reason, r.detail)
        fronts.append(sim.pos[1])
    assert not job.rows_left()
    assert max(fronts) > J.HELD_HOMING_AREA.ymax        # rows were read in front of Y 3114
    n = len(sim.received)
    r = p.drive(job.home())
    assert r.kind == J.Kind.OK, (r.reason, r.detail, sim.violations)
    assert sim.violations == [] and job.at_rest()
    cids = [ln[1:3] for ln in sim.received[n:]]
    i1 = cids.index("i1")
    if not J.homing_starts_here(tuple(job.way_back_moves[-1]["from"]) if job.way_back_moves
                                else (0, 0), False):
        assert "m0" in cids[:i1]


def test_caps_hold_the_way_back():
    assert cp.WAY_BACK == (3 * cp.WAY_BACK_MOVES_MAX, cp.WAY_BACK_MOVES_MAX)
    assert cp.WAY_BACK_MOVES_MAX <= 4
