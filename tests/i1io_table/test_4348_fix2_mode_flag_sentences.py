"""Safety review 448, SHOULD-2: the table's answer about its hand-alignment mode (f4) differs from
the recordings. 4.3.48 first showed ONE sentence for every such answer ("still in the mode for
aiming by hand ... an earlier measurement stopped while the arm was free"), which says the
opposite of the truth when the table answers 00 (motors holding) where the recordings show 01
(after f1, during the aims). Now the job says which answer came where (``mode_flag_detail``) and
the window says one sentence per case, each true."""
from __future__ import annotations

import pytest

from tests.i1io_table.test_4348_the_arm_home_without_i1profiler import OUT_HELD
from tests.i1io_table.test_job_reading import job_for
from ui import i1io_table_window as W
from workflow.i1io.table import job as J

STILL_ON = "still in the mode for aiming by hand"
SWITCHED_ON = "has switched into the mode for aiming by hand"
HOLDING = "its motors are holding the arm"
NEUTRAL = "in a way no recording shows at this point"
ALL = (STILL_ON, SWITCHED_ON, HOLDING, NEUTRAL)


def _only(text, which):
    assert which in text, text
    for other in ALL:
        if other != which:
            assert other not in text, (other, text)


def _f4_after(sim, after_cid: str, answer: str):
    """The first f4 answered after *after_cid* was received says *answer* instead."""
    orig = sim._c_execute
    st = {"armed": False, "done": False}

    def ex(line, cid, a, fault):
        out = orig(line, cid, a, fault)
        if cid == after_cid:
            st["armed"] = True
        elif cid == "f4" and st["armed"] and not st["done"]:
            st["done"] = True
            return (out[0], answer) + tuple(out[2:])
        return out
    sim._c_execute = ex
    return st


def test_on_at_the_opening_keeps_the_earlier_measurement_sentence(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READY_TO_OPEN: "arm out"},
                                       real_table=False)
    sim.pos, sim.mode, sim.free_arm = list(OUT_HELD), "01", True
    r = p.drive(job.open())
    assert r.kind == J.Kind.STOPPED and r.reason == "mode_flag_unexpected"
    assert (r.detail["mode_answer"], r.detail["mode_expected"], r.detail["at_opening"]) == \
        ("01", "00", True)
    _only(W.reason_text(r.reason, r.detail), STILL_ON)


def test_on_where_the_motors_should_hold_says_so_and_not_earlier_measurement(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    assert p.drive(job.open()).ok and p.drive(job.calibrate()).ok
    st = _f4_after(sim, "i1", "01")          # the f4 after the homing that starts the alignment
    r = p.drive(job.align())
    assert st["done"] and r.kind == J.Kind.STOPPED and r.reason == "mode_flag_unexpected"
    assert (r.detail["mode_answer"], r.detail["mode_expected"], r.detail["at_opening"]) == \
        ("01", "00", False)
    _only(W.reason_text(r.reason, r.detail), SWITCHED_ON)


def test_off_after_the_arm_was_let_go_never_says_the_mode_is_on(tmp_path):
    """The case the review found: after f1 the recordings show 01; the table answers 00. The
    sentence must not say the table is in the mode for aiming by hand."""
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    assert p.drive(job.open()).ok and p.drive(job.calibrate()).ok
    st = _f4_after(sim, "f1", "00")
    r = p.drive(job.align())
    assert st["done"] and r.kind == J.Kind.STOPPED and r.reason == "mode_flag_unexpected"
    assert (r.detail["mode_answer"], r.detail["mode_expected"]) == ("00", "01")
    text = W.reason_text(r.reason, r.detail)
    _only(text, HOLDING)
    assert "earlier measurement" not in text


@pytest.mark.parametrize("after, answer", [("i1", "02"), ("f1", "FF")])
def test_an_answer_that_is_neither_00_nor_01_is_not_called_a_mode(tmp_path, after, answer):
    """The table module does not understand such an answer at all (table_answer_unexpected): no
    sentence about the mode is shown for it."""
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    assert p.drive(job.open()).ok and p.drive(job.calibrate()).ok
    st = _f4_after(sim, after, answer)
    r = p.drive(job.align())
    assert st["done"] and r.kind == J.Kind.STOPPED and r.reason == "table_answer_unexpected"
    text = W.reason_text(r.reason, r.detail)
    assert not any(w in text for w in ALL), text


def test_without_the_detail_the_neutral_sentence():
    _only(W.reason_text("mode_flag_unexpected"), NEUTRAL)
    _only(W.reason_text("mode_flag_unexpected", {"mode_answer": "01"}), NEUTRAL)


def test_the_detail_is_read_from_the_table_modules_own_words():
    assert J.mode_flag_detail("f4 answered 00 where the recordings show 01 here", "align") == {
        "mode_answer": "00", "mode_expected": "01", "at_opening": False}
    assert J.mode_flag_detail("something else", "open") == {}
