"""Safety review of 4.3.47 (independent, 18 Nov 2026): a computed move from a FREE arm is judged
from a reading taken before the last question.

`job._move_to` checks the path (`_free_arm_inside`, `geo.check_path`) and computes the move's time
window from `position_now`. In the creep (stage DZ) that reading is taken, and checked for
stillness, BEFORE the first-visit question; the "yes" to that question is itself the hands-off
confirmation, so the m0 follows it with no reading in between. The question can stay on screen
for any length of time while the arm is free (the person's hands were on it for the aims a
moment earlier). A free arm moved during that time is driven from where it really is, along a
path nobody checked.

The first test shows the gap as it is (it passes today). The second states the rule the review
asks for and is a STRICT xfail: when the job reads the arm again after the last question (and
stops if it moved), it XPASSes, the suite turns red, and the marker is to be removed with the
fix.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from workflow.i1io.table import job as J

P0 = ";p025"


def _creep_with_a_hand_at_the_first_visit_question(push=(300.0, -150.0)):
    """The recorded front-zone sheet (as test_job_safety's creep tests); while the creep's
    first-visit question is shown, a hand moves the free arm by *push*."""
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    seen = {}

    def on_ask(person, res):
        if res.step == "creep" and res.confirm == J.Confirm.FIRST_VISIT and "n" not in seen:
            sim = person.sim
            seen["n"] = len(sim.received)
            seen["free"] = bool(person.job._table.arm_free)
            seen["read"] = tuple(person.job._table.position_now)
            sim.pos = [sim.pos[0] + push[0], sim.pos[1] + push[1]]
            seen["moved_to"] = tuple(sim.pos)
        return None

    res, job, sim, person = H.run_steps(
        ["open", "align", "creep"], script={J.Confirm.FRONT_CHOICE: "go on"},
        on_ask=on_ask, sheet=sheet, aims=pts)
    return res, job, sim, seen


def test_today_the_creep_sends_its_first_move_with_no_reading_after_the_question():
    res, job, sim, seen = _creep_with_a_hand_at_the_first_visit_question()
    assert "n" in seen, "the creep asked no first-visit question (the setup changed)"
    assert seen["free"] is True
    after = sim.received[seen["n"]:]
    # the very next line after the question is the computed m0: no p0 in between
    assert after and after[0].startswith(";m0"), after[:3]


@pytest.mark.xfail(strict=True, reason="review 4.3.47 MUST-1: _move_to judges a free arm's move "
                                       "from a reading taken before the last question")
def test_a_free_arm_is_read_again_after_the_last_question_before_it_is_moved():
    res, job, sim, seen = _creep_with_a_hand_at_the_first_visit_question()
    after = sim.received[seen["n"]:]
    first_move = next(i for i, ln in enumerate(after) if ln.startswith(";m0"))
    assert P0 in after[:first_move], "no fresh reading between the question and the move"
    # and a hand-moved arm (300 units) is never driven: the creep stops before its m0
    assert not any(ln.startswith(";m0") for ln in after)
