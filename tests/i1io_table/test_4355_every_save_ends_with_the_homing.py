"""2026-11-21: EVERY SAVE OF A TABLE SITTING ENDS WITH THE HOMING (proven on a real table).

The table owner's ChromIQ 4.3.54 sitting of 21 Nov 2026 (19:25, guidance off): a complete page
(528 of 528 read), Save, then NO homing: the arm was left at (-1317, 3185), held, the table in
its aiming mode, and the next START refused it (a0 540000). The cause: the run already held a
measurement, so the job's own Save was refused (run_has_a_measurement_already); the window's
replace path archived the earlier file and called save() directly, and that result never
carried what follows the end of a page, so the window closed the session, which sends nothing.

The fix: ONE decision of what follows the end of a page (``TableJob._after_end``), carried by
every ending result: end(), its save / discard, and save() / discard() called directly. Here every
save path, guided and not: the first measurement, a replace (the person agreed at START), a
partial save, a resume (continue), a discard, the last page of several; each ends with
i1Profiler's end of a job s0 p0 i1 s0 f0 f4 f4 p0 (R19), the arm at rest and the mode off.
"""
from __future__ import annotations

import shutil

import pytest

from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_ending import SECOND, _end, job_on, project
from tests.i1io_table.test_job_reading import read_page, ready_to_read, small_sheet
from tests.i1io_table.test_window import settings  # noqa: F401  (the fixture)
from workflow.i1io.table import job as J

C = J.Confirm
#: i1Profiler's end of a job (R19 513.6-517.6) and ChromIQ's reading at rest
END_OF_JOB = [";s022", ";p025", ";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]
GUIDED = pytest.mark.parametrize("guided", [True, False], ids=["guided", "guidance-off"])


def _job(run, tmp_path, guided, **kw):
    job, sim, helper, p = job_on(run, tmp_path, **kw)
    job.guided = guided
    job.consent_version = 4
    job.calibration_place_preference = "table tile"
    return job, sim, helper, p


def _home_follows(job, sim, p, res):
    """What the window does with a result that carries next == ["home"]: the homing, its own
    GO (or, with the guidance off after a complete page, its countdown). Returns the lines."""
    assert "home" in (res.detail.get("next") or []), res.detail.get("next")
    n = len(sim.received)
    r = p.drive(job.home())
    assert r.ok, (r.reason, r.detail)
    sent = sim.received[n:]
    assert sent[-len(END_OF_JOB):] == END_OF_JOB, sent
    assert job.at_rest() and not job._table.mode_on and sim.mode == "00"
    assert sim.violations == []
    return sent


@GUIDED
def test_the_first_measurement(tmp_path, guided):
    _proj, run = project(tmp_path)
    job, sim, _h, p = _job(run, tmp_path, guided)
    ready_to_read(job, p)
    read_page(job, p)
    r, st = _end(job, p, "save") if guided else (p.drive(job.end()), None)
    assert r.ok and r.detail["ending"] == "saved"
    _home_follows(job, sim, p, r)


@GUIDED
def test_a_replace_the_person_agreed_to_ends_with_the_homing(tmp_path, guided):
    """THE BUG: the run holds a measurement; the job's Save is refused; the window archives the
    earlier file and calls save() directly (ui/i1io_table_window.py, _on_refused)."""
    _proj, run = project(tmp_path)
    job, sim, _h, p = _job(run, tmp_path, guided)
    ready_to_read(job, p)
    read_page(job, p)
    shutil.copyfile(run.chart_ti2, run.measurement_ti3)       # the earlier measurement
    r = p.drive(job.end()) if not guided else _end(job, p, "save")[0]
    assert r.kind == J.Kind.REFUSED and r.reason == "run_has_a_measurement_already"
    # book-keeping, not a fault: the sitting does not turn guided for it
    assert job.turned_guided is None and job._fault_seen is None
    # the window's archive, then its direct save()
    (run.dir / "old").mkdir(exist_ok=True)
    run.measurement_ti3.replace(run.dir / "old" / run.measurement_ti3.name)
    s = job.save()
    assert s.ok and s.detail["next"] == ["home"]
    sent = _home_follows(job, sim, p, s)
    if not guided:
        # the complete page with the guidance off: the countdown, no question
        assert [c["for"] for c in job.countdowns][-1:] == ["home"]
    assert sent[0] == ";s022"


@GUIDED
def test_a_partial_save(tmp_path, guided):
    _proj, run = project(tmp_path)
    job, sim, _h, p = _job(run, tmp_path, guided)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    r, _st = _end(job, p, "save")
    assert r.ok and r.detail["measurement"]["state"] == "partial"
    _home_follows(job, sim, p, r)


@GUIDED
def test_a_direct_save_and_a_direct_discard_carry_the_homing(tmp_path, guided):
    for what in ("save", "discard"):
        _proj, run = project(tmp_path / what)
        job, sim, _h, p = _job(run, tmp_path / what, guided)
        ready_to_read(job, p)
        read_page(job, p)
        r = getattr(job, what)()
        assert r.ok and r.detail["next"] == ["home"], (what, r.detail)
        _home_follows(job, sim, p, r)


def test_a_discard_at_the_ending(tmp_path):
    _proj, run = project(tmp_path)
    job, sim, _h, p = _job(run, tmp_path, True)
    ready_to_read(job, p)
    read_page(job, p)
    r, _st = _end(job, p, "discard")
    assert r.ok and r.detail["ending"] == "discarded"
    _home_follows(job, sim, p, r)


def test_continue_a_partial_measurement(tmp_path):
    _proj, run = project(tmp_path)
    sheet = small_sheet([4, 4, 4])
    job, sim, _h, p = job_on(run, tmp_path / "a", {C.ROW_FAILED: "skip"}, sheet=sheet,
                             faults={"read_loc": {"1-0": "dies"}})
    ready_to_read(job, p)
    read_page(job, p)
    r, _st = _end(job, p, "save")
    assert r.detail["measurement"]["state"] == "partial"
    _home_follows(job, sim, p, r)
    job.close()
    job2, sim2, _h2, p2 = job_on(run, tmp_path / "b", sheet=sheet, stamp=SECOND)
    assert job2.set_options(["-p", "-r"]).detail["resume_unread"] == 1
    ready_to_read(job2, p2)
    read_page(job2, p2)
    r2, st2 = _end(job2, p2, "save")
    assert st2["state"] == "complete" and r2.ok
    _home_follows(job2, sim2, p2, r2)


def test_the_last_page_of_several(tmp_path):
    _proj, run = project(tmp_path)
    from tests.i1io_table.test_4350_refine_aims_every_page import _two_pages
    sheet = _two_pages()
    job, sim, _h, p = job_on(run, tmp_path, sheet=sheet)
    ready_to_read(job, p)
    read_page(job, p)
    assert p.drive(job.home()).ok                       # the window's page done: home first
    assert p.drive(job.next_page()).ok
    assert p.drive(job.align()).ok
    rows = read_page(job, p)
    r, st = _end(job, p, "save")
    assert st is not None, (r.kind, r.reason, r.detail, [(x.kind, x.reason) for x in rows],
                            job.page)
    assert st["state"] == "complete" and r.ok
    _home_follows(job, sim, p, r)


# ---- the window: the replace path, every answer --------------------------------------------------
@pytest.mark.parametrize("guided", [True, False], ids=["guided", "guidance-off"])
def test_the_window_replace_path_brings_the_arm_home(qtbot, monkeypatch, tmp_path, settings,
                                                     guided):
    from tests.i1io_table.test_fix10_review10 import _archive_spy
    from tests.i1io_table.test_window import open_window, project as wproject
    sheet = small_sheet()
    _proj, run = wproject(tmp_path, sheet)
    run.measurement_ti3.write_text("CTI3\nKEEP ME\n", encoding="ascii")
    archive, moved = _archive_spy(run)
    win, sim, _r, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, sheet=sheet, run=run, replace_agreed=True,
        archive=archive, guided=guided)
    if guided:
        p.drive_until("end_of_session")
        p.press("Save and stop")
    p.drive_until(("home_at_end", "done"))
    if p.page() == "home_at_end":
        p.press("Bring the arm home, my hands are away")
    p.drive_until(("done",))
    assert len(moved) == 1
    job = win.job
    assert job.ended == "saved"
    assert sim.sim.received[-len(END_OF_JOB):] == END_OF_JOB
    assert job.at_rest() and not job._table.mode_on
    assert sim.sim.violations == []
