"""4.3.48: the table gets home without the vendor's software where the recordings allow it.

The owner (2026-11-19): "so there is still i1profiler involved. is there something we could do
so this would not be needed anymore?"

What the recordings of the volunteer's table show (PRIVATE analysis, the work folder):
* i1Profiler sends its homing ``i1`` from a HELD arm out on the table at the end of every job:
  s0 p0 i1 s0 f0 f4 f4: 16 homings in 9 recordings (15 at the end of a job, plus i1Profiler's
  at-open recovery from (1102, 1202)), X -1438..1179, Y 1202..2560, 2.6-3.9 s. These are 4.3.47's
  own homing lines (``_end_of_job``, plus a reading at rest).
* From a FREE arm: twice cleanly (2.36 s, 4.02 s), once answered with status 3 (2 ms after a
  button press). No homing at all starts at the alignment start (X 2507), held or free.
* No opening of a table whose arm is out is recorded, except once at (1058, 317), where i1Profiler
  did NOT home directly (two m0 at speed 200 first).

So:
* after a stop the job made at a PLACE CHECK (the arm read away from its resting place right
  before a homing), with the arm held where recorded homings start, the job offers its usual
  homing once (way back HOME_AFTER_STOP, step ``home_after_stop``), after a hands-off GO, and
  sends nothing after it;
* nothing is offered after any other stop (an answer not understood, a refusal, no answer, a
  lost link, a move that did not arrive, a slow move, a failed homing, the person's own "Send
  nothing more"), nor where no recorded homing starts (the alignment start);
* at a START the person may say "the arm is out": the job connects, reads where the arm is (one
  ``;p025``, the line a calibration's rest check sends first) and moves nothing; a held arm in
  the area is offered 4.3.47's homing (HOME_OFFERED), anything else the old advice.

4.3.52 (the owner's ruling of 2026-11-20, test_4352_start_rule_by_state.py): the START rule's
homing is i1Profiler's own start homing (s0 p0 i1 s0, plus the reading at rest) from wherever a
held arm stands but the back strip, asked INSIDE the step that found the arm; after it the
measurement goes on. The tests here keep 4.3.48's protections of the offer (the states, the
reasons, the reopening for the homing's lines only) on the page that offers it when the person
declined that question ("Not now"); the place they tested (the alignment start) is replaced by
the back strip, the one place still refused.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_job_reading import job_for
from workflow.i1io.table import caps as cp
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

OUT_HELD = [0.0, 1600.0]              # out over the bed, inside the measuring area
#: 4.3.52: the one place a held arm is not brought home from (job.in_back_strip)
BACK_STRIP = [1058.0, 317.0]
#: 4.3.52: the START rule's homing (i1Profiler's start homing + the reading at rest)
HOMING = [";s022", ";p025", ";i12b", ";s022", ";p025"]
MOVES = ("m0", "m1", "m2", "i1", "i0")


def _stopped_at_the_homing(tmp_path, pos, real_table=False, script=None, **kw):
    """START (the person ticked "at rest"), calibration skipped (-N), the arm held at *pos*:
    the alignment's own homing reads it away from rest and the sending is closed (4.3.47)."""
    job, sim, helper, run, p = job_for(tmp_path, script, real_table=real_table, **kw)
    assert job.set_options(["-N"]).ok
    sim.pos = list(pos)
    assert p.drive(job.open()).ok
    go = p.script[J.Confirm.GO]
    p.script[J.Confirm.GO] = "back"           # 4.3.52: "Not now" on the START rule's question
    r = p.drive(job.align())
    p.script[J.Confirm.GO] = go
    assert r.kind == J.Kind.STOPPED, (r.kind, r.reason)
    assert job._table.closed_reason.startswith("right before the homing: the arm reports")
    return job, sim, p, r


# ---- the offer, and what it sends ------------------------------------------------------------
@pytest.mark.parametrize("real_table", [False, True], ids=["ideal", "less ideal"])
def test_a_stop_at_the_homings_place_check_offers_the_homing_and_it_runs(tmp_path, real_table):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD, real_table)
    assert r.way_back == J.WayBack.HOME_AFTER_STOP
    assert job.end_state()["way_back"] == "home_after_stop"
    n = len(sim.received)
    asked = len(p.asked)
    res = p.drive(job.home_after_stop())
    assert res.ok, (res.kind, res.reason, res.detail)
    # the hands-off GO first, then exactly the START homing's lines, nothing else
    assert [a[1] for a in p.asked[asked:]] == [J.Confirm.GO]
    assert sim.received[n:] == HOMING
    assert tbl.REST_GUARD.contains(job._table.position_now)
    assert res.way_back == J.WayBack.NONE
    # 4.3.52: and the measurement goes on (the table is a started table at rest); the offer is
    # not made twice
    assert job._table.closed_reason is None and res.detail["goes_on"] is True
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert p.drive(job.align()).ok and sim.violations == []


def test_the_go_is_asked_before_any_line_and_back_sends_nothing(tmp_path):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD,
                                            script={J.Confirm.GO: "back"})
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.reason == "person_chose_back" and sim.received[n:] == []
    # still offered (nothing was tried)
    assert job.way_back() == J.WayBack.HOME_AFTER_STOP


def test_it_is_offered_once(tmp_path):
    """A homing after the stop that does not reach the resting place: nothing more, old advice."""
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    # the table reports the arm somewhere else after the homing
    sim.inject("status", "i1", 3)
    res = p.drive(job.home_after_stop())
    assert res.kind == J.Kind.STOPPED
    assert job.way_back() == J.WayBack.OPEN_I1PROFILER_ONCE
    n = len(sim.received)
    assert job.home_after_stop().reason == "tried_already"
    assert sim.received[n:] == []


def test_after_save_or_discard_the_ending_offers_it(tmp_path):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    assert job._after_end() == {"next": ["home_after_stop"]}


# ---- not offered ------------------------------------------------------------------------------
def test_not_from_the_back_strip(tmp_path):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, BACK_STRIP)
    assert r.way_back == J.WayBack.OPEN_I1PROFILER_ONCE
    n = len(sim.received)
    res = job.home_after_stop()
    assert res.reason == "arm_in_the_back_strip" and sim.received[n:] == []


@pytest.mark.parametrize("fault", ["garbled", "refuse", "no_answer", "unplug", "bad_checksum",
                                   "stray"])
def test_not_after_a_stop_whose_answer_was_not_understood(tmp_path, fault):
    """A fault on the p0 of that very place check: the arm's place may be anything, the table's
    state is not known: no offer, nothing sent."""
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    assert job.set_options(["-N"]).ok
    sim.pos = list(OUT_HELD)
    assert p.drive(job.open()).ok
    # the alignment's homing: s0 then p0: the fault on that p0
    sim.inject_at(len(sim.received) + 1, fault)
    r = p.drive(job.align())
    assert r.kind == J.Kind.STOPPED
    assert r.way_back != J.WayBack.HOME_AFTER_STOP
    n = len(sim.received)
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert sim.received[n:] == []


def test_not_after_the_persons_send_nothing_more(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    assert job.set_options(["-N"]).ok
    sim.pos = list(OUT_HELD)
    assert p.drive(job.open()).ok
    job.report_problem("stop now")
    assert job.way_back() != J.WayBack.HOME_AFTER_STOP
    assert job.home_after_stop().kind == J.Kind.REFUSED


def test_not_after_a_move_that_did_not_arrive(tmp_path):
    """A computed move read twice more than 1 mm off: a mechanical doubt, no offer."""
    from tests.i1io_table.test_4347_fix2_arrivals_and_aiming_again import _arrive_beside
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    sim.jitter = False
    for s in ("open", "calibrate", "align"):
        assert p.drive(H.step(job, s)).ok
    _arrive_beside(sim, 2, 0, -40, reads=2)
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.STOPPED and r.reason == "arm_not_where_expected"
    assert r.way_back == J.WayBack.OPEN_I1PROFILER_ONCE
    assert job.home_after_stop().reason == "stop_not_at_a_place_check"


def test_not_while_i1profiler_runs(tmp_path):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    job._other_program = lambda: True
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.reason == "i1profiler_running" and sim.received[n:] == []


def test_the_table_lets_only_the_homings_lines_through_after_reopening(tmp_path):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    d = job._table
    d.reopen_for_homing(d.closed_reason, cp.HOME)
    d.current_step = J._CStep("x", 5, 1)
    with pytest.raises(tbl.Doubt):
        d.c_exchange(J.geo.m0_line(0, 1700), 0, window=(0.0, 9.0), timeout=9.0)
    assert not any(ln.startswith(";m0") for ln in sim.received[-3:])
    # and it cannot be reopened a second time, nor for another reason
    with pytest.raises(tbl.Doubt):
        d.reopen_for_homing(d.closed_reason, cp.HOME)


def test_reopening_for_another_reason_is_refused(tmp_path):
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    with pytest.raises(tbl.Doubt):
        job._table.reopen_for_homing("the session is over", cp.HOME)
    assert job._table.closed_reason is not None


# ---- planted faults: the allow decision -----------------------------------------------------
@pytest.mark.parametrize("plant", ["any reason", "any place", "free arm"])
def test_planted_a_wider_offer_is_caught(tmp_path, monkeypatch, plant):
    """Each plant widens the offer; a test above must then fail. Here the plant is applied and the
    decision checked directly against the case it must refuse."""
    if plant == "any reason":
        monkeypatch.setattr(J, "HOME_AFTER_STOP_REASONS", ("",))
        job, sim, helper, run, p = job_for(tmp_path, real_table=False)
        assert job.set_options(["-N"]).ok
        sim.pos = list(OUT_HELD)
        assert p.drive(job.open()).ok
        sim.inject_at(len(sim.received) + 1, "garbled")
        p.drive(job.align())
        # the planted reason list lets an answer not understood through: the position check
        # still refuses (no reading came with it), which is the second line of defence
        assert job._home_after_stop_why() in ("no_fresh_position_reading", "arm_not_held")
    elif plant == "any place":
        job, sim, p, r = _stopped_at_the_homing(tmp_path, BACK_STRIP)
        monkeypatch.setattr(J, "in_back_strip", lambda p: False)
        assert job._home_after_stop_why() is None          # the plant shows
        monkeypatch.undo()
        assert job._home_after_stop_why() == "arm_in_the_back_strip"
    else:
        job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
        job._table.arm_free = True
        assert job._home_after_stop_why() == "arm_not_held"


# ---- the START with the arm out -------------------------------------------------------------
def test_start_with_the_arm_out_reads_it_and_brings_it_home(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: "arm out"},
                                       real_table=True)
    sim.pos = list(OUT_HELD)
    r = p.drive(job.open())
    assert r.ok and r.detail.get("arm_out") is True
    assert len(sim.received) == 11                      # the opening only
    asked = len(p.asked)
    r = p.drive(job.where_is_the_arm())
    assert r.ok and r.detail.get("brought_home") is True, (r.kind, r.reason)
    # one reading, the hands-off question, then the START rule's homing; never the usual one
    assert [a[1] for a in p.asked[asked:]] == [J.Confirm.GO]
    assert p.asked[asked][3] == 12, "nothing moved before the question"
    assert sim.received[11:] == [";p025"] + HOMING
    # then the measurement goes on as usual
    for s in ("calibrate", "align"):
        assert p.drive(H.step(job, s)).ok, s
    assert sim.violations == []


def test_start_with_the_arm_out_in_the_back_strip_offers_nothing(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: "arm out"},
                                       real_table=False)
    sim.pos = list(BACK_STRIP)
    assert p.drive(job.open()).ok
    r = p.drive(job.where_is_the_arm())
    assert r.reason == "arm_not_at_rest"
    assert r.way_back == J.WayBack.OPEN_I1PROFILER_ONCE
    n = len(sim.received)
    assert job.home().reason == "arm_in_the_back_strip" and sim.received[n:] == []


def test_start_with_the_arm_out_and_free_offers_nothing(tmp_path):
    """The mode for aiming by hand still on (f4 01 at the opening): no recording shows an opening
    in that state on a started table; the opening stops as before, nothing moves."""
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: "arm out"},
                                       real_table=False)
    sim.pos, sim.mode, sim.free_arm = list(OUT_HELD), "01", True
    r = p.drive(job.open())
    assert r.kind == J.Kind.STOPPED and r.reason == "mode_flag_unexpected"
    assert r.way_back != J.WayBack.HOME_AFTER_STOP
    assert job.home_after_stop().kind == J.Kind.REFUSED
    assert not [ln for ln in sim.received if ln[1:3] in MOVES]


def test_start_with_the_arm_out_but_at_rest_goes_on_as_usual(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: "arm out"},
                                       real_table=False)
    assert p.drive(job.open()).ok
    r = p.drive(job.where_is_the_arm())
    assert r.ok and r.detail["at_rest"] is True
    for s in ("calibrate", "align"):
        assert p.drive(H.step(job, s)).ok, s


def test_the_held_arm_out_of_the_area_is_never_offered_the_usual_homing(tmp_path):
    """4.3.47 offered HOME_OFFERED for a held arm at the alignment start, and the homing then
    refused after sending s0 p0. Now the offer says what the homing would do (4.3.52: the
    alignment start gets the START homing; the back strip is the place left)."""
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    sim.pos = list(BACK_STRIP)
    assert p.drive(job.open()).ok
    r = p.drive(job.calibrate())
    assert r.reason == "arm_not_at_rest"
    assert r.way_back == J.WayBack.OPEN_I1PROFILER_ONCE


@pytest.mark.parametrize("fault", ["no_lamp", "fire_unsent", "dies_at_fire"])
def test_not_while_a_scan_move_may_be_pending(tmp_path, fault):
    """The switch-off way stays: a scan move may still wait for the lamp."""
    from tests.i1io_table.test_roundB_strip import _job, _ready as _ready_strip
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {fault: True}, "scan_at": 2})
    _ready_strip(job, p)
    r = p.drive(job.read_row())
    assert r.way_back == J.WayBack.SWITCH_OFF_PENDING
    n = len(sim.received)
    assert job.home_after_stop().reason == "movement_may_be_unfinished"
    assert job._after_end() == {"next": []}
    assert len(sim.received) == n


def test_not_when_the_person_said_send_nothing_more_after_the_stop(tmp_path):
    """The stop itself would allow the offer; the person then chose "Send nothing more" on the
    stopped page: their word stands, nothing is offered (planted fault P7 found this missing)."""
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    assert job.way_back() == J.WayBack.HOME_AFTER_STOP
    job.report_problem("stop now")
    assert job.way_back() != J.WayBack.HOME_AFTER_STOP
    n = len(sim.received)
    assert job.home_after_stop().reason == "stopped_by_person"
    assert sim.received[n:] == []
