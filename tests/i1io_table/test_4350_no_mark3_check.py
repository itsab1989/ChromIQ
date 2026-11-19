"""4.3.50 (the first complete page on a real i1iO 2, 19 Nov 2026; the owner's provisional yes on
our recommendation): NO MARK-3 CHECK, in the guided and in the unguided mode.

Until 4.3.49, after every alignment the arm drove the measuring opening to the third mark's p1
reading and the window asked "Is the opening on mark 3?". Nobody can see the opening under the
instrument (the volunteer's photographs: the instrument stands on the corner and covers the
cross), i1Profiler's recordings have no such step (its third p1 is followed by the move to the
first row), and on the real page the check sent the careful 5 mm steps 9.5 mm further forward
than the patches needed, because the marks counted in the "front need".

What these tests pin:
* the job has no check move and no mark-3 question; no window answer counts as the hands-off
  confirmation any more;
* the front need is what the PLAN reads (the patch targets and the strip runs inside the
  area), never the mark readings, so the careful steps end at the frontmost target;
* no computed move goes to a mark reading;
* after the aims the first move (row 1, from the free arm, as i1Profiler's own first move is)
  waits for the hands-off GO in both modes, then reads the arm still before it moves;
* the properties that leaned on the check move hold without it: the creep's arrivals are the
  way back (the homing after a front page arrives at rest), and the table's remembered reach
  learns the frontmost target the motors arrived at.
* THE FRONT QUESTION (4.3.50 item 4): ONE question; "Go forward carefully, my hands are away" is
  the hands-off confirmation for the careful steps, so no GO and no first-visit question follow
  it before the first step.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_4349_acceptance_his_sheet_and_wider import CROSSES_1, HIS_TABLE
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import reach as rc
from workflow.i1io.table import scan as sc

GO_ON = {J.Confirm.FRONT_CHOICE: "go on"}


def _m0_targets(sim, since=0):
    return [geo.decode_xyv(ln.encode())[1:3] for ln in sim.received[since:]
            if ln[1:3] == "m0"]


def _fit(aims, sheet=None):
    sheet = sheet or H.demo_sheet()
    marks = sc.aims_of(sheet, 0)
    al = geo.fit_alignment([tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in marks],
                           aims)
    return al, J.page_fit(sheet, 0, al)


def test_the_job_has_no_check_move_and_no_window_answer_is_the_hands_off_confirmation():
    assert not hasattr(J.TableJob, "check_move")
    assert not hasattr(J.TableJob, "_check_move")
    assert "check_move" not in J.STAGE_KEY and "check_move" not in J.MOVING_STEPS
    assert "d2" not in J.MAX_RUNS
    assert J.HANDS_OFF_WINDOW_ANSWERS == frozenset()


def test_the_front_need_is_the_plan_never_the_marks():
    al, fit = _fit(CROSSES_1)
    area = geo.CAP_AREA
    plan_ys = []
    sheet = H.demo_sheet()
    for st in sheet["pages"][0]["strips"]:
        for q in st["patches"]:
            p = al.to_table(sc.sheet_table_mm(sheet, q["centre_mm"]))
            if area.contains(p):
                plan_ys.append(p[1])
        for r in st["run_mm"]:
            p = al.to_table(sc.sheet_table_mm(sheet, (st["x_mm"], r)))
            if area.contains(p):
                plan_ys.append(p[1])
    assert fit["front_need"] == max(plan_ys)
    # on this sheet the crosses lie in front of the frontmost patch: the old need was mark 2/3's
    assert max(p[1] for p in al.readings) > fit["front_need"]


def _his_page(tmp_path, ask=False, store=None):
    job, sim, helper, run = RS.make_reading_job(
        tmp_path, sheet=H.demo_sheet(), aims=CROSSES_1, ask_after_each_step=ask,
        reach_store=store if store is not None else rc.MemoryReachStore(), **HIS_TABLE)
    p = H.Person(job, sim, GO_ON)
    return job, sim, p


@pytest.mark.parametrize("ask", [False, True], ids=["unguided", "guided"])
def test_the_careful_steps_end_at_the_frontmost_target_and_no_move_goes_to_a_mark(tmp_path, ask):
    job, sim, p = _his_page(tmp_path, ask)
    for step in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, step)()).ok
    need = job.front_need
    marks = [tuple(r) for r in job.alignment.readings]
    assert need is not None and need < max(m[1] for m in marks)
    assert p.drive(job.creep()).ok
    assert job.front_reached() == need
    assert sim.front_seen <= need + 1
    r = p.drive(job.read_row())
    assert r.ok, (r.reason, r.detail)
    assert not set(_m0_targets(sim)) & set(marks)
    assert sim.violations == []


@pytest.mark.parametrize("ask", [False, True], ids=["unguided", "guided"])
def test_one_front_question_and_the_first_careful_step_follows_it(tmp_path, ask):
    job, sim, p = _his_page(tmp_path, ask)
    for step in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, step)()).ok
    k = len(p.asked)
    asked_front = [c for _s, c, _d, _n, _m in p.asked if c == J.Confirm.FRONT_CHOICE]
    assert len(asked_front) == 1
    assert "front_yes" not in J.CHOICES and not hasattr(J.Confirm, "FRONT_YES")
    assert (J.Confirm.FRONT_CHOICE, "go on") in J.HANDS_OFF_ANSWERS
    n = len(sim.received)
    assert p.drive(job.creep()).ok
    # neither a GO nor a first-visit question between the front answer and the first step
    assert [c for _s, c, _d, _n, _m in p.asked[k:]] == []
    assert len(_m0_targets(sim, n)) >= 2


def test_lay_it_further_back_still_ends_the_alignment(tmp_path):
    job, sim, helper, run = RS.make_reading_job(
        tmp_path, sheet=H.demo_sheet(), aims=CROSSES_1, ask_after_each_step=False,
        reach_store=rc.MemoryReachStore(), **HIS_TABLE)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "back"})
    for step in ("open", "calibrate"):
        assert p.drive(getattr(job, step)()).ok
    r = p.drive(job.align())
    assert r.reason == "sheet_to_be_laid_further_back" and job.alignment is None
    assert r.detail["back_mm"] == int((J.page_fit(H.demo_sheet(), 0, geo.fit_alignment(
        [tuple(sc.sheet_table_mm(H.demo_sheet(), a["page_mm"]))
         for a in sc.aims_of(H.demo_sheet(), 0)], CROSSES_1))["front_need"]
        - geo.MEASURING_AREA.ymax) / 10.0) + 1


@pytest.mark.parametrize("ask", [False, True], ids=["unguided", "guided"])
def test_row_one_from_the_free_arm_asks_the_hands_off_go_first(tmp_path, ask):
    """A sheet inside the proven area (no careful steps): after the aims, the first move is row
    1's, from the free arm, after its own hands-off GO and a stillness reading."""
    job, sim, helper, run = RS.make_reading_job(tmp_path, ask_after_each_step=ask)
    p = H.Person(job, sim)
    for step in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, step)()).ok
    assert job.front_need is None and job.state().arm_free is True
    k, n = len(p.asked), len(sim.received)
    r = p.drive(job.read_row())
    assert r.ok, (r.reason, r.detail)
    first = p.asked[k]
    assert (first[0], first[1]) == ("read_row", J.Confirm.GO) and first[3] == n
    # nothing was sent before the GO, and two readings of the free arm before its first move
    sent = [ln[1:3] for ln in sim.received[n:]]
    first_m0 = sent.index("m0")
    assert sent[:first_m0].count("p0") >= 2
    assert sim.violations == []


def test_the_way_back_and_the_reach_hold_without_the_check_move(tmp_path):
    store = rc.MemoryReachStore()
    job, sim, p = _his_page(tmp_path, store=store)
    for step in ("open", "calibrate", "align", "creep"):
        assert p.drive(getattr(job, step)()).ok
    need = job.front_need
    rows = []
    while job.rows_left():
        r = p.drive(job.read_row())
        assert r.ok, (r.reason, r.detail)
        rows.append(r)
    # the arm stands at the end of the frontmost row, in front of every recorded homing start
    assert not J.homing_starts_here(job.state().position_now, False)
    r = p.drive(job.home())
    assert r.ok, (r.reason, r.detail, sim.violations)
    assert job.at_rest() and job.way_back_moves and sim.violations == []
    # the remembered reach learned the frontmost target the motors arrived at (the careful
    # steps' last one, or a row further forward), never a mark
    assert job.reach.motor_front_y is not None and job.reach.motor_front_y >= need - 5
    assert job.reach.motor_front_y < max(r[1] for r in CROSSES_1)
