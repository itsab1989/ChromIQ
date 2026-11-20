"""Safety review of 4.3.47 (independent, 18 Nov 2026), MUST-1: a computed move is never judged
from a reading taken before the last question, or before the motors last let the arm go.

Before the fix, `job._move_to` checked the path (`_free_arm_inside`, `geo.check_path`) and
computed the move's time window from `position_now`; in the creep (stage DZ) that reading was
taken BEFORE the first-visit question, whose "yes" is itself the hands-off confirmation, so the m0
followed the question with no reading in between while the arm was free. The reviewer showed a
hand moving the free arm 150 mm during that question going unnoticed (strict xfail, 042879504).

Now `_move_to` (and the creep's further steps) read the arm once more after the last question
(`TableJob._read_again_if_asked`, the recorded ``;p025``), stop before the move when the arm
moved by more than STILL_UNITS (free) or the arrival tolerance (held) and otherwise judge the
move afresh from the new reading. One test per caller of `_move_to`, and the creep's own loop.

4.3.50: the creep asks no first-visit question any more ("Go forward carefully, my hands are
away", asked in the alignment, is its hands-off confirmation and names its part of the table), so
nothing is asked between its reading and its first move: a hand on the free arm during the FRONT
question is read by the creep's own stillness pair, and the move is judged from there. The check
move to mark 3 is gone from the app; the tests' copy of it (tester_d2) still stands for a move
whose first-visit question comes after its reading, as a held patch row's does.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import must1_wire as M1
from tests.i1io_table import reader_sim as RS
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

P0 = ";p025"



@pytest.fixture(autouse=True)
def _first_time_on_new_ground(monkeypatch):
    """4.3.53 fix round (inventory A8): ground this table's reach record already holds no
    longer gets the guided first-visit question (TableJob._known_ground). The tests in this
    file are about what happens AT and AROUND a first-visit question (or compare the wire with
    tester 0.6.0, which asked it), so they keep the first time on new ground everywhere;
    tests/i1io_table/test_4353_first_visit_once.py proves the new rule."""
    from workflow.i1io.table import job as _J
    monkeypatch.setattr(_J.TableJob, "_known_ground", lambda self, p: False)

def _at_question(step, confirm, push, seen):
    """An on_ask that moves the arm by *push* the first time *step* asks *confirm* (a hand on a
    free arm; on a held arm the simulator's own position, standing for a table that moved)."""
    def on_ask(person, res):
        if res.step == step and res.confirm == confirm and "n" not in seen:
            sim = person.sim
            seen["n"] = len(sim.received)
            seen["free"] = bool(person.job._table.arm_free)
            seen["read"] = tuple(person.job._table.position_now)
            if push is not None:
                sim.pos = [sim.pos[0] + push[0], sim.pos[1] + push[1]]
            seen["arm_now"] = [int(round(sim.pos[0])), int(round(sim.pos[1]))]
        return None
    return on_ask


def _creep(push):
    """4.3.50: the hand on the free arm during the ONE front question (asked in the alignment)."""
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    seen = {}
    res, job, sim, person = H.run_steps(
        ["open", "align", "creep"], script={J.Confirm.FRONT_CHOICE: "go on"},
        on_ask=_at_question("align", J.Confirm.FRONT_CHOICE, push, seen), sheet=sheet, aims=pts,
        jitter=False)
    return res, job, sim, seen


# ---- the creep (DZ): the reviewer's case --------------------------------------------------
def test_the_creep_reads_the_free_arm_after_the_front_question_and_then_moves():
    res, job, sim, seen = _creep(None)
    assert "n" in seen and seen["free"] is True, "no front question"
    after = sim.received[seen["n"]:]
    # the creep's own stillness pair, read after the answer, then its first move
    assert after[:2] == [P0, P0] and after[2].startswith(";m0"), after[:4]
    assert res[2].ok, (res[2].step, res[2].reason)
    assert job.reads_after_question == []
    assert sim.violations == []


@pytest.mark.parametrize("push", [(300.0, -150.0), (0.0, 3.0), (-3.0, 0.0), (1500.0, 0.0)])
def test_a_free_arm_moved_during_the_front_question_is_driven_only_from_where_it_is_now(push):
    """The reviewer's case after 4.3.50: a hand moved the free arm while the front question was
    shown, then the person pressed "Go forward carefully, my hands are away". The creep reads the
    arm twice (its stillness pair) and judges its first move from THAT place: never from the
    reading taken before the question."""
    res, job, sim, seen = _creep(push)
    after = sim.received[seen["n"]:]
    assert after[:2] == [P0, P0] and after[2].startswith(";m0"), after[:3]
    creep = res[2]
    assert creep.ok, (creep.reason, creep.detail)
    # the stillness pair read the arm where the hand left it, and the move went from there
    free = [r["at"] for r in job.reach_diag["free_readings"]]
    assert free[-1] == seen["arm_now"], (free[-3:], seen["arm_now"])
    assert job.reads_after_question == []
    assert sim.violations == []


@pytest.mark.parametrize("push", [(2.0, 0.0), (0.0, -2.0), (2.0, 2.0)])
def test_a_free_arm_within_two_units_moves_and_the_move_is_judged_from_the_new_reading(push):
    res, job, sim, seen = _creep(push)
    after = sim.received[seen["n"]:]
    assert after[:2] == [P0, P0] and after[2].startswith(";m0"), after[:3]
    assert res[2].ok, (res[2].step, res[2].reason)
    assert sim.violations == []


# ---- the check move to mark 3 (D2) --------------------------------------------------------
def _check_move(push):
    seen = {}
    res, job, sim, person = H.run_steps(
        ["open", "align", "check_move", "home"],
        on_ask=_at_question("check_move", J.Confirm.FIRST_VISIT, push, seen), jitter=False)
    return res, job, sim, seen


def test_the_check_move_reads_the_arm_after_its_first_visit_question():
    res, job, sim, seen = _check_move(None)
    assert "n" in seen and seen["free"] is True
    after = sim.received[seen["n"]:]
    assert after[0] == P0 and after[1].startswith(";m0"), after[:3]
    assert res[2].ok and job.reads_after_question == [seen["n"]]


@pytest.mark.parametrize("push", [(-200.0, 400.0), (3.0, 0.0)])
def test_a_free_arm_moved_during_the_check_moves_question_is_never_driven(push):
    res, job, sim, seen = _check_move(push)
    after = sim.received[seen["n"]:]
    assert after[:1] == [P0]
    assert not any(ln.startswith(";m0") for ln in after), after
    assert res[2].reason == "free_arm_moved_while_asked"
    assert sim.violations == []


def test_every_extra_reading_follows_a_question_and_precedes_its_move():
    """The creep and the check move after it: each extra reading is the first line after a
    question the person answered, and the move it guards comes right after it."""
    res, job, sim, seen = _creep(None)
    assert res[2].ok, (res[2].step, res[2].reason)
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    job, sim, _t = H.make_job(sheet=sheet, aims=pts, jitter=False)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on"})
    for s in ("open", "align", "creep", "check_move", "home"):
        assert p.drive(H.step(job, s)).ok, s
    asked_at = {n for (_st, _c, _d, n, _m) in p.asked}
    assert job.reads_after_question
    for k in job.reads_after_question:
        assert k in asked_at, (k, sorted(asked_at))
        assert sim.received[k] == P0 and sim.received[k + 1].startswith(";m0")


# ---- the patch rows (D3) --------------------------------------------------------------------
def _held_first_visit(push, seen):
    """At the first first-visit question of a row with the arm HELD: *push* moves the simulated
    arm (a table that moved under its motors; a hand cannot push a held arm)."""
    def on_ask(person, res):
        if (res.step == "read_row" and res.confirm == J.Confirm.FIRST_VISIT and "n" not in seen
                and person.job._table.arm_free is False):
            sim = person.sim
            seen["n"] = len(sim.received)
            seen["free"] = False
            if push is not None:
                sim.pos = [sim.pos[0] + push[0], sim.pos[1] + push[1]]
        return None
    return on_ask


def test_a_held_patch_row_after_its_first_visit_question_reads_the_arm_again(tmp_path):
    """The second row: the arm is held at the last patch of the first row; the row's first-visit
    question comes after the row's reading, so the arm is read once more before the first move."""
    job, sim, helper, _run = RS.make_reading_job(tmp_path, jitter=False)
    p = H.Person(job, sim)
    for s in ("open", "calibrate", "align"):
        assert p.drive(H.step(job, s)).ok, s
    assert p.drive(job.read_row()).ok
    seen = {}
    p.on_ask = _held_first_visit(None, seen)
    while job.rows_left() and "n" not in seen:
        r = p.drive(job.read_row())
        assert r.ok, (r.reason, r.detail)
    assert seen and seen["free"] is False
    k = job.reads_after_question[-1]
    assert k == seen["n"] and sim.received[k] == P0 and sim.received[k + 1].startswith(";m0")
    assert sim.violations == []


def test_a_held_arm_that_moved_during_the_rows_question_is_not_moved(tmp_path):
    job, sim, helper, _run = RS.make_reading_job(tmp_path, jitter=False)
    p = H.Person(job, sim)
    for s in ("open", "calibrate", "align"):
        assert p.drive(H.step(job, s)).ok, s
    assert p.drive(job.read_row()).ok
    seen = {}
    p.on_ask = _held_first_visit((0.0, 6.0), seen)
    while job.rows_left() and "n" not in seen:
        r = p.drive(job.read_row())
    n = seen["n"]
    later = sim.received[n:]
    assert later[:1] == [P0]
    assert not any(ln.startswith(";m0") for ln in later), later
    assert r.reason == "arm_moved_while_asked", (r.reason, r.detail)
    assert r.state.sending_closed is False
    assert sim.violations == []


def test_a_free_patch_row_needs_no_extra_reading(tmp_path):
    """The first row after the aims: the free arm's stillness pair is read after the questions
    already (`_still(here)`), so no further reading is sent."""
    job, sim, helper, _run = RS.make_reading_job(tmp_path, jitter=False)
    p = H.Person(job, sim)
    for s in ("open", "calibrate", "align"):
        assert p.drive(H.step(job, s)).ok, s
    assert p.drive(job.read_row()).ok
    assert job.reads_after_question == []


# ---- every caller at once: the rule itself ------------------------------------------------
def _job_after_the_aims():
    job, sim, _t = H.make_job(jitter=False)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    return job, sim


def test_a_reading_before_the_last_answer_is_stale_and_one_after_it_is_not():
    job, sim = _job_after_the_aims()
    d = job._table
    d.position()
    assert not job._reading_is_stale()
    job._mark_answered()
    assert job._reading_is_stale()
    d.position()
    assert not job._reading_is_stale()


def test_a_reading_before_the_last_release_of_the_arm_is_stale():
    job, sim = _job_after_the_aims()
    d = job._table
    d.position()
    assert not job._reading_is_stale()
    d.freed_at_line = d.lines_sent          # as if f1 had just been answered
    assert job._reading_is_stale()
    d.position()
    assert not job._reading_is_stale()


def test_move_to_sends_one_reading_then_the_move_from_a_stale_reading():
    job, sim = _job_after_the_aims()
    d = job._table
    d.position()
    target = job.alignment.readings[2]
    job._mark_answered()
    job._hands_off_due = False
    from workflow.i1io.table import caps as cp
    job._step("d2", *cp.CHECK_MOVE)
    n = len(sim.received)
    gen = job._move_to(target, "a test move")
    with pytest.raises(StopIteration):
        while True:
            ask = next(gen)
            assert ask.kind == J.Confirm.FIRST_VISIT
            gen.send("yes")
    assert sim.received[n] == P0 and sim.received[n + 1].startswith(";m0")


@pytest.mark.parametrize("kind", ["unplug", "no_answer", "garbled", "refuse"])
def test_a_fault_at_the_extra_reading_never_lets_the_move_follow(tmp_path, kind):
    """4.3.50: at a HELD patch row's first-visit question (the creep asks none any more)."""
    job, sim, helper, _run = RS.make_reading_job(tmp_path, jitter=False)
    p = H.Person(job, sim)
    for s in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    assert p.drive(job.read_row()).ok
    seen = {}

    def on_ask(person, res):
        if (res.step == "read_row" and res.confirm == J.Confirm.FIRST_VISIT and "n" not in seen
                and person.job._table.arm_free is False):
            seen["n"] = len(person.sim.received)
            person.sim.inject_at(seen["n"], kind, 1.0)
        return None
    p.on_ask = on_ask
    r = None
    while job.rows_left() and "n" not in seen:
        r = p.drive(job.read_row())
    assert "n" in seen
    after = sim.received[seen["n"]:]
    assert after[:1] == [P0]
    assert not any(ln.startswith(";m0") for ln in after), after
    assert not r.ok


def test_the_base_sittings_extra_readings_are_the_pinned_ones(tmp_path):
    """The fault and cancel cases of the wire tests are shifted by these (must1_wire)."""
    from tests.i1io_table import job_reading_wire_cases as RW
    from tests.i1io_table import job_strip_wire_cases as SW
    from tests.i1io_table import job_wire_cases as WW
    _g, _r, sim = WW.job_lines(WW.cases(base_len=0)["A warm d1 d2 f"])
    assert tuple(sim.job.reads_after_question) == M1.EXTRA_IN_ALIGN_SITTING
    _g, _r, sim, _h = SW.job_run(SW.cases(base_len=0)["S C1 D1 D2 E2 F"], tmp_path / "s")
    assert tuple(sim.job.reads_after_question) == M1.EXTRA_IN_STRIP_E2_SITTING
    out = RW.job_run(RW.cases(base_len=0)["D C1 D1 D3 F"], tmp_path / "r")
    assert tuple(out[-1].job.reads_after_question) == M1.EXTRA_IN_READING_D3_SITTING


def test_the_caps_carry_exactly_the_extra_reading():
    from workflow.i1io.table import caps as cp
    assert cp.CHECK_MOVE == (6, 1)              # the tests' copy of 4.3.49's D2 (tester_d2)
    assert J.DZ_CAPS == cp.CREEP == (2 * cp.CREEP_STEPS_MAX + 8 + 1 + 1, cp.CREEP_STEPS_MAX + 1)
    assert tbl.STILL_UNITS == 2
