"""The fixes after review 8 (2026-11-17), each against the reviewer's probe it answers
(``review8/tree/tests/i1io_table/test_review8_probes.py``), both report modes where the mode can
matter. Simulators only: no table, no USB, no window.

| finding | what is pinned here                                                          |
|---------|------------------------------------------------------------------------------|
| B-1     | after an ending every step but the homing is refused ``session_ended``; GO   |
|         | is cleared by save() and discard(), so the homing asks it                    |
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_ending import SECOND, _end, job_on, project
from tests.i1io_table.test_job_reading import read_page, ready_to_read, small_sheet
from tests.i1io_table.test_job_safety import moves
from workflow.i1io.table import job as J

ASKING = pytest.mark.parametrize("asking", [True, False], ids=["asking", "quiet"])


def _report(job):
    if job.report_due is not None:
        assert job.answer(J.Confirm.REPORT_AFTER_STEP, "as described").ok


def _one_row(tmp_path, asking, rows=(4, 4, 4)):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, sheet=small_sheet(list(rows)), asking=asking)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    _report(job)
    return run, job, sim, p


#: every step a window could call after an ending, with how it is called
_STEPS_AFTER_AN_ENDING = {
    "read_row": lambda j: j.read_row(), "read_row_1_again": lambda j: j.read_row(1),
    "align": lambda j: j.align(), "creep": lambda j: j.creep(),
    "check_move": lambda j: j.check_move(), "park": lambda j: j.park(),
    "calibrate": lambda j: j.calibrate(), "read_tile": lambda j: j.read_tile(),
    "start_up": lambda j: j.start_up(), "next_page": lambda j: j.next_page(),
    "open": lambda j: j.open(), "set_options": lambda j: j.set_options(["-p"]),
    "adopt_earlier": lambda j: j.adopt_earlier(SECOND),
    "discard_earlier": lambda j: j.discard_earlier(SECOND),
}


def _everything_but_the_homing_is_refused(job, sim, ended):
    n = len(sim.received)
    for name, call in _STEPS_AFTER_AN_ENDING.items():
        r = call(job)
        assert (r.kind, r.reason) == (J.Kind.REFUSED, J.SESSION_ENDED), (name, r.kind, r.reason)
        assert r.detail["ended"] == ended, name
        assert job._gen is None, name                 # nothing waits for a confirmation either
    assert len(sim.received) == n                     # nothing was sent, nothing moved
    h = job.home()                                    # the homing: its own hands-off GO
    assert (h.kind, h.confirm) == (J.Kind.NEEDS, J.Confirm.GO) and len(sim.received) == n
    assert job.answer(J.Confirm.GO, "yes").ok and len(moves(sim.received)) > 0


# ---- B-1 ------------------------------------------------------------------------------------

@ASKING
@pytest.mark.parametrize("how", ["save", "discard"])
def test_b1_the_public_save_or_discard_clears_go_and_ends_the_reading(tmp_path, asking, how):
    """The reviewer's P1, P1b, P1c: save()/discard() called directly (no end()), then row 2 or
    row 1 again: refused, nothing moves; the homing asks GO."""
    run, job, sim, p = _one_row(tmp_path, asking)
    assert getattr(job, how)().ok
    assert job._go_page is None
    _everything_but_the_homing_is_refused(job, sim, "saved" if how == "save" else "discarded")


@ASKING
@pytest.mark.parametrize("choice,ended", [("save", "saved"), ("discard", "discarded")])
def test_b1_after_save_and_stop_or_discard_and_stop_only_the_homing(tmp_path, asking, choice,
                                                                     ended):
    """The reviewer's P2: through end()."""
    run, job, sim, p = _one_row(tmp_path, asking)
    r, _st = _end(job, p, choice)
    assert r.ok and r.detail["next"] == ["home"]
    _everything_but_the_homing_is_refused(job, sim, ended)


@ASKING
def test_b1_after_nothing_read_no_row_is_read(tmp_path, asking):
    """The reviewer's P2b: "nothing read" ends the session too (end() would never take later
    readings: it answers ended_already_nothing_read)."""
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, asking=asking)
    ready_to_read(job, p)
    assert job.end().detail["ending"] == "nothing_read"
    _everything_but_the_homing_is_refused(job, sim, "nothing_read")


def test_b1_discard_is_refused_while_a_step_waits_for_its_go(tmp_path):
    """A GO answered after a discard would read into a discarded session: discard() waits."""
    run, job, sim, p = _one_row(tmp_path, False)
    job.end()
    assert job.answer(J.Confirm.END, "keep measuring").ok
    g = job.read_row()
    assert g.confirm == J.Confirm.GO
    d = job.discard()
    assert (d.kind, d.reason) == (J.Kind.REFUSED, "another_step_waits_for_a_confirmation")
    assert job.ended is None


def test_b1_keep_measuring_is_not_an_ending(tmp_path):
    """Keep measuring ends nothing: the next row asks GO and reads."""
    run, job, sim, p = _one_row(tmp_path, False)
    job.end()
    assert job.answer(J.Confirm.END, "keep measuring").ok
    assert job.ended is None
    assert p.drive(job.read_row()).ok


# ---- B-2 ------------------------------------------------------------------------------------

def _interrupted_with_marker(tmp_path):
    from workflow.i1io.table import session_end as se
    proj, run = project(tmp_path)
    j1, s1, *_r = job_on(run, tmp_path / "first")
    p1 = H.Person(j1, s1)
    ready_to_read(j1, p1)
    assert p1.drive(j1.read_row()).ok
    run.i1io_table_pending_marker(RS.STAMP).write_text("pending\n", encoding="utf-8")
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND)
    assert job.discard_earlier(RS.STAMP).ok
    assert se.session_state(run.i1io_table_session_dir(RS.STAMP)) == se.DISCARDED
    return run, job, sim, p


def test_b2_a_discarded_session_with_an_unacknowledged_marker_is_never_set_aside(tmp_path):
    """The reviewer's P12: the folder stays where open() finds its marker; the next START still
    asks "switched off and on" before anything is opened or sent."""
    from workflow.i1io.table import session_end as se
    run, job, sim, p = _interrupted_with_marker(tmp_path)
    sdir = run.i1io_table_session_dir(RS.STAMP)
    assert se.set_aside(run, RS.STAMP) is None
    assert sdir.is_dir() and run.i1io_table_pending_marker(RS.STAMP).is_file()
    assert not run.i1io_table_session_archive_dir(RS.STAMP).exists()
    r = job.open()
    assert r.confirm == J.Confirm.MARKER and sim.received == []


def test_b2_once_the_marker_is_acknowledged_the_folder_may_be_set_aside(tmp_path):
    from workflow.i1io.table import session_end as se
    run, job, sim, p = _interrupted_with_marker(tmp_path)
    assert p.drive(job.open()).ok                     # "switched off and on": acknowledged
    assert run.i1io_table_pending_marker(RS.STAMP).with_suffix(".acknowledged.json").is_file()
    moved = se.set_aside(run, RS.STAMP)
    assert moved == run.i1io_table_session_archive_dir(RS.STAMP) and moved.is_dir()
