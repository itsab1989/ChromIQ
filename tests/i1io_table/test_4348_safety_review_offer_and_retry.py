"""Independent safety review of 4.3.48 (the homing after a stop, "The arm is out", the second move
to a patch beside its target): the planted faults that only ONE test caught get more.

Each test below pins one refusal on its own, so a single widened condition in
``TableJob._home_after_stop_why`` or ``_move_to`` is caught where it is, not only by a test that
happens to reach it first. The two ``xfail(strict=True)`` tests document what the review asks for
and the branch does not do yet; they turn red (XPASS) once it is done, and are then made plain.
"""
from __future__ import annotations

import pytest

from tests.i1io_table.test_4348_an_arrival_beside_is_moved_to_once_more import (
    _computed_m0, _ready)
from tests.i1io_table.test_4348_the_arm_home_without_i1profiler import (
    HOMING, OUT_HELD, _stopped_at_the_homing)
from tests.i1io_table.test_job_reading import job_for
from workflow.i1io.table import caps as cp
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl


def _refused_and_silent(job, sim, why):
    n = len(sim.received)
    assert job.way_back() != J.WayBack.HOME_AFTER_STOP
    assert job._after_end() != {"next": ["home_after_stop"]}
    res = job.home_after_stop()
    assert (res.kind, res.reason) == (J.Kind.REFUSED, why), (res.kind, res.reason)
    assert sim.received[n:] == []


# ---- item 1: every condition refuses on its own -----------------------------------------------
@pytest.mark.parametrize("state", ["free", "unknown", "held but mode on"])
def test_an_arm_that_is_not_held_is_never_offered_the_homing(tmp_path, state):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    assert job.way_back() == J.WayBack.HOME_AFTER_STOP          # the plain case offers it
    d = job._table
    if state == "free":
        d.arm_free, d.mode_on = True, True
    elif state == "unknown":
        d.arm_free = None
    else:
        d.mode_on = True
    _refused_and_silent(job, sim, "arm_not_held")


def test_ctrl_c_after_the_stop_withdraws_the_offer(tmp_path):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    job.cancel()
    _refused_and_silent(job, sim, "stopped_by_person")
    # and the table module would refuse to open the sending again
    with pytest.raises(tbl.Doubt):
        job._table.reopen_for_homing(job._table.closed_reason, cp.HOME)


@pytest.mark.parametrize("pending", ["motion unconfirmed", "scan move pending"])
def test_a_movement_that_may_be_unfinished_withdraws_the_offer(tmp_path, pending):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    d = job._table
    if pending == "motion unconfirmed":
        d.motion_unconfirmed = True
    else:
        d.last_move = ("scan move", None)
    _refused_and_silent(job, sim, "movement_may_be_unfinished")
    if pending == "motion unconfirmed":
        with pytest.raises(tbl.Doubt):
            d.reopen_for_homing(d.closed_reason, cp.HOME)


def test_a_line_answered_after_the_place_check_withdraws_the_offer(tmp_path):
    """The reading the offer is judged from must be the last line the table answered."""
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    job._table.lines_sent += 1
    _refused_and_silent(job, sim, "no_fresh_position_reading")


def test_the_go_is_asked_even_when_a_go_was_given_on_this_page(tmp_path):
    """The homing after a stop always asks its own hands-off GO first: not once per page."""
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    job._go_page, job._hands_off_due = job.page, False
    n, asked = len(sim.received), len(p.asked)
    res = p.drive(job.home_after_stop())
    assert res.ok, (res.kind, res.reason)
    assert [a[1] for a in p.asked[asked:]] == [J.Confirm.GO]
    assert sim.received[n:] == HOMING


def test_a_stop_pressed_before_bring_home_still_asks_the_go(tmp_path):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD,
                                            script={J.Confirm.GO: "back"})
    job.stop_at_next_pause()
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.reason == "person_chose_back" and sim.received[n:] == []


@pytest.mark.xfail(strict=True, reason="safety review 448 MUST-1: a place check that reads the "
                                       "arm out AFTER a homing of this sitting (the park, the "
                                       "start-up) is a homing that did not reach rest: no offer")
@pytest.mark.parametrize("before", ["park", "start_up"])
def test_no_offer_when_the_arm_reads_out_after_a_homing_of_this_sitting(tmp_path, before):
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    assert job.set_options(["-N"]).ok
    if before == "start_up":
        sim.cold = True
    assert p.drive(job.open()).ok
    assert p.drive(getattr(job, before)()).ok
    assert job._table.motions_sent > 0
    sim.pos = list(OUT_HELD)          # the homing reported done, yet the arm reads out
    r = p.drive(job.align())
    assert job._table.closed_reason.startswith("right before the homing")
    assert r.way_back != J.WayBack.HOME_AFTER_STOP
    assert job._home_after_stop_why() is not None


@pytest.mark.xfail(strict=True, reason="safety review 448 SHOULD-1: the job itself (not only the "
                                       "window) refuses the start-up after the person said the "
                                       "arm is out")
def test_the_job_refuses_the_start_up_after_arm_out(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: "arm out"},
                                       real_table=False)
    sim.cold = True
    assert p.drive(job.open()).ok
    n = len(sim.received)
    res = job.start_up()
    assert res.kind == J.Kind.REFUSED and sim.received[n:] == []


# ---- item 2 --------------------------------------------------------------------------------------
def _land_beside_by(sim, which, dx, dy):
    from tests.i1io_table.test_4348_an_arrival_beside_is_moved_to_once_more import _land_beside
    return _land_beside(sim, which, dx, dy)


@pytest.mark.parametrize("off", [(11, 0), (0, -11), (15, 15), (0, 40), (-60, 0)])
def test_an_arrival_beyond_1_mm_is_never_moved_to_again(tmp_path, off):
    job, sim, p, seen = _ready(tmp_path)
    _land_beside_by(sim, (2,), *off)
    n = len(sim.received)
    r = p.drive(job.read_row())
    moves = [ln for ln in sim.received[n:] if _computed_m0(ln)]
    assert job.beside_retries == []
    assert len(moves) == 2 and len(set(moves)) == 2, moves      # no second move to patch 2
    assert r.kind == J.Kind.STOPPED and job._table.closed_reason is not None


def test_no_reading_is_taken_after_a_second_move_that_also_stops_beside(tmp_path):
    from tests.i1io_table.test_4347_fix2_arrivals_and_aiming_again import _arrive_beside
    job, sim, p, seen = _ready(tmp_path, {J.Confirm.ROW_FAILED: "skip"})
    _arrive_beside(sim, 2, 0, 8, reads=4)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "skipped"
    # patch 1 read, patch 2 not: no reading was taken with the arm beside the target
    assert len(job.beside_retries) == 1
    assert r.detail["read"] == 1 and job._last_block["data"]["spot_readings"] == 1
    failed = [d for c, d in seen if c == J.Confirm.ROW_FAILED]
    assert failed[0]["why"] == "arrived_beside_the_target_again"


def test_the_caps_carry_exactly_two_retries_per_row_attempt():
    n = 33
    base = (4 * n + 4, n)
    assert cp.spot_row_step(n) == (base[0] + 2 * 3, base[1] + 2 * 1) == (142, 35)
    for rows in ((33,) * 30, (24,) * 22, (33,)):
        with_r = cp.page_caps(rows)
        saved = cp.BESIDE_RETRIES_PER_ROW
        try:
            cp.BESIDE_RETRIES_PER_ROW = 0
            without = cp.page_caps(rows)
        finally:
            cp.BESIDE_RETRIES_PER_ROW = saved
        k = len(rows) + cp.ALLOWANCE_ROWS
        assert (with_r[0] - without[0], with_r[1] - without[1]) == (k * 2 * 3, k * 2 * 1)
