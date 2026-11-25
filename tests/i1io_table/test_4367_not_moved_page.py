"""The page of a strip row that could not be read says what the arm really did.

On a real table (4.3.66) a strip refused before any move, with the arm free, was shown with "The
arm is held where the strip move ended". The job now says whether the attempt sent a move and
holds the arm ("moved"); the window picks the page by that, never by the reason's name.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import test_dual_table as DT
from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.test_roundB_strip import _job, _ready
from workflow import measurement_messages as M
from workflow.i1io.table import job as J


def _ask(p):
    return [d for _s, c, d, _n, _m in p.asked if c == J.Confirm.ROW_FAILED_STRIP]


def _strip(tmp_path, **kw):
    job, sim, helper, run, p = _job(tmp_path, sheet=small_sheet(),
                                    script={J.Confirm.ROW_FAILED_STRIP: "stop"}, **kw)
    _ready(job, p)
    return job, sim, helper, p


def test_a_row_refused_with_the_free_arm_has_not_moved(tmp_path):
    job, sim, helper, p = _strip(tmp_path)
    assert job._table.arm_free is True
    sim.c_faults["c4_byte"] = 0xFF
    n = len(sim.received)
    p.drive(job.read_row())
    assert _ask(p)[0]["moved"] is False
    assert not [ln for ln in sim.received[n:] if ln.startswith((";m", ";i"))]


def test_a_row_refused_with_the_held_arm_has_not_moved_either(tmp_path):
    """After a read row the motors hold the arm; the next row's refusal moved nothing."""
    job, sim, helper, p = _strip(tmp_path)
    assert p.drive(job.read_row()).ok and job._table.arm_free is False
    sim.c_faults["c4_byte"] = 0xFF
    p.drive(job.read_row())
    assert _ask(p)[0]["moved"] is False


def test_the_same_reason_after_a_move_keeps_the_old_page(tmp_path, monkeypatch):
    """Not by the reason's name: a clean failure after the move to the row start moved the arm."""
    job, sim, helper, p = _strip(tmp_path)
    from workflow.i1io.table import scan as sc
    real = sc.run_row

    def late(table, inst, plan, *a, **k):
        inst.arm = lambda *a, **k: {"event": "tscan_armed", "ready": False}
        return real(table, inst, plan, *a, **k)
    monkeypatch.setattr(sc, "run_row", late)
    p.drive(job.read_row())
    d = _ask(p)[0]
    assert d["why"] == "strip_instrument_not_ready" and d["moved"] is True


def test_a_dual_row_refused_before_its_uv_pass_moved(tmp_path):
    job, sim, helper, run, p = DT._job(tmp_path)
    p.script[J.Confirm.ROW_FAILED_STRIP] = "stop"
    answers = iter([0xBC, 0xFF] + [0xFF] * 9)
    sim.c_faults["c4_byte"] = lambda: next(answers)
    DT._ready(job, p)
    p.drive(job.read_row())
    d = _ask(p)[0]
    assert d["moved"] is True and d["m0_kept"] is True


def test_a_dual_row_read_again_and_refused_has_not_moved_the_second_time(tmp_path):
    """The real sitting: the lamp pass moved and was kept, "again" was refused before any move."""
    job, sim, helper, run, p = DT._job(tmp_path)
    tries = iter(["again", "stop"])

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED_STRIP:
            person.script[J.Confirm.ROW_FAILED_STRIP] = next(tries)
    p.on_ask = on_ask
    answers = iter([0xBC] + [0xFF] * 9)
    sim.c_faults["c4_byte"] = lambda: next(answers)
    DT._ready(job, p)
    p.drive(job.read_row())
    assert [d["moved"] for d in _ask(p)] == [True, False]


def test_the_two_pages_say_what_happened():
    held = M.M_I1IO_DRIVE_ROW_FAILED_STRIP.render(row=1, page=1, why="x")[1]
    still = M.M_I1IO_DRIVE_ROW_FAILED_STRIP_NOT_MOVED.render(row=1, page=1, why="x")[1]
    assert held.startswith("The arm is held where the strip move ended.")
    assert still.startswith("ChromIQ did not move the arm this time.")
    assert "held" not in still and "take your hands away" in still.split("\n\n")[0]
    for body in (held, still):
        assert [ln[5:16] for ln in body.split("\n") if "•" in ln] == [
            "Read it aga", "Read it pat", "Skip it: th", "End this st"]
    assert "choose another answer" in still and "hardly help" not in still
    assert "says what to do, please do that first" in still      # a hand on the free arm is cured so


def test_a_logged_c4_answer_sends_no_line(tmp_path):
    """Safety review NOTE 5: a row whose c4 is written to the logs sends exactly the lines of a
    row whose c4 is not."""
    lines = []
    for byte in (0xBA, 0xBE):
        job, sim, helper, p = _strip(tmp_path / f"{byte:02X}")
        sim.c_faults["c4_byte"] = byte
        n = len(sim.received)
        assert p.drive(job.read_row()).ok
        lines.append(sim.received[n:])
    assert lines[0] == lines[1]
