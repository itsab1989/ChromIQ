# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.53 fix round: the rows review's MUST-1 and the inventory's NO REASON items that change the
job's behaviour (countdown after a person's answer; a failed patch row read once more by itself;
no limit on rows read again or on runs per page).

MUST-1 (review_rows453.txt): with the guidance off, after a person answered anything (their hand
was at the mouse, at the instrument's button, maybe at the table), the next movement is preceded
by the countdown with Stop. Movements that follow each other with nobody asked have none. Until
this fix the GO after "Row N could not be read" -> "again" / "patch by patch" was a countdown of
0 s (4.3.52 gave 3 s): the reviewer's probe, kept here as a test, showed 3.0, 3.0, 0.0."""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_4352_guidance_off import small_sheet
from ui import i1io_table_window as W
from workflow.i1io.table import job as J


def _unguided(tmp_path, faults, script=None, sheet=None):
    sheet = sheet or small_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet,
                                                aims=H.demo_aims(sheet), faults=faults)
    job.guided = False
    job.consent_version = W.CONSENT_VERSION
    job.calibration_place_preference = "table tile"
    assert job.set_options(["-v", "-c", "1", "-p", "chart"]).ok
    p = H.Person(job, sim, script or {})
    for st in ("open", "calibrate", "align"):
        r = p.drive(getattr(job, st)())
        assert r.ok, (st, r.reason)
    return job, sim, helper, p, sheet


def _loc(sheet, row, col):
    return sheet["pages"][0]["strips"][row]["patches"][col]["loc"]


# ---- MUST-1: the reviewer's probe, as a test --------------------------------------------------

@pytest.mark.parametrize("answer", ["again", "patch by patch"])
def test_the_go_after_a_persons_answer_to_a_failed_row_is_a_full_countdown(tmp_path, answer):
    """Unguided; a patch of row 2 fails every time (so the row's own re-read fails too and the
    person is asked). After "again" the arm must not move at the click: the countdown runs its
    full UNGUIDED_COUNTDOWN_S with Stop. RED before the fix (0.0 s). "patch by patch" is asked
    for strip rows only, so for a patch row the same answer is "again"."""
    sheet = small_sheet()
    answers = iter([answer if answer == "again" else "again", "skip"])
    job, sim, helper, p, _ = _unguided(tmp_path, {"read_loc": {_loc(sheet, 1, 1): "dies"}},
                                       sheet=sheet)

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED:
            person.script[J.Confirm.ROW_FAILED] = next(answers)
        return None
    p.on_ask = on_ask
    while job.rows_left():
        assert p.drive(job.read_row()).ok
    asked = [a[1] for a in p.asked]
    assert asked.count(J.Confirm.ROW_FAILED) == 2
    secs = [c["seconds"] for c in job.countdowns]
    # the align, the first row, then the GO after the person's "again": all full countdowns
    assert secs[:2] == [J.UNGUIDED_COUNTDOWN_S, J.UNGUIDED_COUNTDOWN_S], secs
    again = [c for c in job.countdowns[2:] if c["for"] == "read_row"]
    assert again and again[0]["seconds"] == J.UNGUIDED_COUNTDOWN_S, job.countdowns
    assert sim.violations == []


#: every kind a PERSON can answer in an unguided sitting (ALWAYS_ASKED, plus the questions that
#: stay asked in their own cases: the reader consent before v4, an incomplete END, the homing
#: offers), with an answer that is not itself the hands-off confirmation
PERSON_ANSWERS = sorted([(k, v) for k in J.ALWAYS_ASKED for v in J.CHOICES[k]
                         if (k, v) not in J.HANDS_OFF_ANSWERS]
                        + [(J.Confirm.READER_CONSENT, v) for v in J.CHOICES[J.Confirm.READER_CONSENT]]
                        + [(J.Confirm.END, v) for v in J.CHOICES[J.Confirm.END]])


@pytest.mark.parametrize("kind,value", PERSON_ANSWERS)
def test_after_every_answer_a_person_gives_unguided_the_next_movement_has_its_countdown(
        kind, value):
    """Every question kind an unguided sitting can show a person, every answer: the next
    countdown is the full one. Driven through the job's own answer path (a step waiting for that
    question), then the countdown the next movement would run."""
    job, sim, _t = H.make_job()
    job.guided = False
    job._countdown_owed = False                  # as after a movement with nobody asked

    def gen():
        yield J.Ask(kind, {"step": "x"})
        return {}
    job._gen, job._gen_step, job._pending = gen(), "x", None
    job._pending = job._gen.send(None)
    job.answer(kind, value)
    assert job._countdown_owed is True, (kind, value)
    job._countdown("x", J.Ask(J.Confirm.GO, {"step": "x"}))
    assert job.countdowns[-1]["seconds"] == J.UNGUIDED_COUNTDOWN_S


def test_a_window_page_a_person_answers_owes_the_countdown_too():
    job, sim, _t = H.make_job()
    job.guided = False
    job._countdown_owed = False
    job.person_answered("some_window_page", "carry on")
    job._countdown("x", J.Ask(J.Confirm.GO, {"step": "x"}))
    assert job.countdowns[-1]["seconds"] == J.UNGUIDED_COUNTDOWN_S


def test_movements_that_follow_each_other_with_nobody_asked_have_no_countdown():
    """The other half of the rule: a hands-off point reached with nobody asked since the last
    movement is cleared at once (0 s, nothing sent), as the homing at the end of a page."""
    job, sim, _t = H.make_job()
    job.guided = False
    job._countdown_owed = False
    n = len(sim.received)
    job._countdown("home", J.Ask(J.Confirm.GO, {"step": "home"}))
    assert job.countdowns[-1]["seconds"] == 0.0 and sim.received[n:] == []


# ---- inventory D5 / D6: a failed reading with the arm in place --------------------------------

def test_a_patch_row_whose_reading_failed_is_read_once_more_by_itself(tmp_path):
    """No question, no countdown, the sitting not turned guided; the same recorded lines as the
    row read the first time (a subset of 4.3.52's wire for the same answer "again", which also
    sent the countdown's nothing and the same moves)."""
    sheet = small_sheet()
    job, sim, helper, p, _ = _unguided(tmp_path, {"read_once": {_loc(sheet, 1, 1): "dies"}},
                                       sheet=sheet)
    while job.rows_left():
        r = p.drive(job.read_row())
        assert r.ok
    assert J.Confirm.ROW_FAILED not in [a[1] for a in p.asked]
    assert [w for _pg, _r, w in job.rows_reread_by_itself] == ["reader_died"]
    assert job.turned_guided is None and not job.guided_now
    assert [c["seconds"] for c in job.countdowns if c["seconds"]] == [J.UNGUIDED_COUNTDOWN_S] * 2
    m = job.measurement()
    assert m.ok and m.detail["measurement"]["state"] == "complete"
    assert sim.violations == []


def test_only_once_by_itself_then_the_person_is_asked(tmp_path):
    sheet = small_sheet()
    job, sim, helper, p, _ = _unguided(tmp_path, {"read_loc": {_loc(sheet, 1, 1): "dies"}},
                                       script={J.Confirm.ROW_FAILED: "skip"}, sheet=sheet)
    while job.rows_left():
        assert p.drive(job.read_row()).ok
    assert [a[1] for a in p.asked].count(J.Confirm.ROW_FAILED) == 1
    assert len(job.rows_reread_by_itself) == 1


def test_an_arrival_beside_its_target_is_still_a_question_not_a_silent_re_read():
    """Only a READING that failed with the arm on its patch is repeated by itself; an arrival
    beside is a table state and keeps its question (sp.READ_AGAIN_BY_ITSELF)."""
    from workflow.i1io.table import spot as sp
    assert "arrived_beside_the_target" not in sp.READ_AGAIN_BY_ITSELF
    assert not {"instrument_asks_for_calibration", "calibration_failed",
                "wrong_instrument", "reading_of_another_patch"} & set(sp.READ_AGAIN_BY_ITSELF)
