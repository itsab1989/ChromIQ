"""The fixes after review 8 (2026-11-17), each against the reviewer's probe it answers
(``review8/tree/tests/i1io_table/test_review8_probes.py``), both report modes where the mode can
matter. Simulators only: no table, no USB, no window.

| finding | what is pinned here                                                          |
|---------|------------------------------------------------------------------------------|
| B-1     | after an ending every step but the homing is refused ``session_ended``; GO   |
|         | is cleared by save() and discard(), so the homing asks it                    |
| B-2     | a folder with an unacknowledged pending marker is never set aside            |
| M-1     | a problem report (between steps, or a report other than "as described")     |
|         | clears GO: the homing asks it                                                |
| M-2     | an own-tile white clears GO (hands on the arm)                               |
| M-3     | resume / refinement reaches every page with something missing; a complete    |
|         | page is passed over and never moves                                          |
| M-4     | an adopted session that was saved is saved at the next START                 |
| S-1     | a Stop pressed between steps or at a question ends the next move before it  |
| S-2     | Discard after adopting discards the adopted session too, folders kept        |
| S-3     | adopting and options only before open(); options never undo an adoption      |
| S-4     | a crash between the run's .ti3 and session_result.json reads as saved        |
| S-5     | a disk error on Save is a refusal; the homing and the readings stay          |
| S-6     | the two planted faults that survived review 8                                |
| NOTE    | ``next`` only names a homing that can run; end() without a run; the current  |
|         | page on Keep measuring; ``filed`` false after a §3b restore                  |
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


def _job_for(tmp_path, asking, script=None, rows=(4, 4, 4), **kw):
    from tests.i1io_table.test_job_reading import job_for
    return job_for(tmp_path, script, sheet=small_sheet(list(rows)), asking=asking, **kw)


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


# ---- M-1 ------------------------------------------------------------------------------------

@ASKING
def test_m1_something_wrong_between_steps_then_the_homing_asks_go(tmp_path, asking):
    """The reviewer's P13: report_problem("something looked or sounded wrong") with no step
    waiting; the homing that is left asks GO before it moves."""
    job, sim, helper, run, p = _job_for(tmp_path, asking)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    _report(job)
    r = job.report_problem(J.PROBLEM_SOMETHING_WRONG)
    assert r.ok and r.reason == "only_the_homing_now"
    n = len(sim.received)
    h = job.home()
    assert (h.kind, h.confirm) == (J.Kind.NEEDS, J.Confirm.GO) and len(sim.received) == n
    assert job.answer(J.Confirm.GO, "yes").ok and job.at_rest()


@pytest.mark.parametrize("answer", ["something wrong", "not sure"])
def test_m1_a_report_other_than_as_described_then_the_homing_asks_go(tmp_path, answer):
    """The reviewer's P14 (asking mode): the report after a row says something was wrong."""
    job, sim, helper, run, p = _job_for(tmp_path, True)
    ready_to_read(job, p)
    p.script["report"] = None
    p.drive(job.read_row())
    assert job.report_due == "read_row"
    assert job.answer(J.Confirm.REPORT_AFTER_STEP, answer).ok
    n = len(sim.received)
    h = job.home()
    assert (h.kind, h.confirm) == (J.Kind.NEEDS, J.Confirm.GO) and len(sim.received) == n


def test_m1_restrict_to_homing_clears_go_itself():
    job = J.TableJob(small_sheet())
    job._go_page = 0
    job.restrict_to_homing("a test")
    assert job.only_home and job._go_page is None


# ---- M-2 ------------------------------------------------------------------------------------

@ASKING
def test_m2_an_own_tile_white_mid_page_then_the_next_movement_asks_go(tmp_path, asking):
    """The reviewer's P5: row 1, a white due, the homing, the own tile (hands on the arm to lift
    the i1Pro 2 out and seat it back), then align(): GO is asked before anything moves."""
    job, sim, helper, run, p = _job_for(tmp_path, asking, {J.Confirm.CAL_PLACE: "own tile"})
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    _report(job)
    job.calibration_due = True
    assert job.read_row().reason == "calibration_due"
    assert p.drive(job.home()).ok
    _report(job)
    assert p.drive(job.calibrate()).ok
    _report(job)
    assert job._go_page is None
    seen = []
    p.on_ask = lambda person, res: seen.append((res.confirm, len(moves(sim.received)))) or None
    n = len(moves(sim.received))
    assert p.drive(job.align()).ok
    before = [c for c, m in seen if m == n]
    assert before[0] == J.Confirm.GO, seen


def test_m2_a_table_tile_white_keeps_the_pages_go(tmp_path):
    """Nobody's hands are on the arm for the table's own tile: GO stays as it was."""
    job, sim, helper, run, p = _job_for(tmp_path, False)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    job.calibration_due = True
    assert job.read_row().reason == "calibration_due"     # a refusal: GO cleared (step 7)
    assert p.drive(job.home()).ok
    assert job._go_page == job.page
    assert p.drive(job.calibrate()).ok
    assert job._go_page == job.page


# ---- M-3 ------------------------------------------------------------------------------------

def _pages(n):
    """n pages of two rows of four, every location and sample id the chart's own."""
    sheet = small_sheet([4, 4], pages=n)
    for k in range(1, n):
        sheet["pages"][k]["strips"] = [
            {**st, "patches": [{**q, "loc": f"P{k + 1}-" + q["loc"],
                                "sample_id": q["sample_id"] + 8 * k} for q in st["patches"]]}
            for st in sheet["pages"][k]["strips"]]
    return sheet


#: missing on pages 1 and 3 of 3 (page 2 complete)
_MISSING_1_3 = {"0-1", "1-2", "P3-0-0", "P3-1-3"}


def _resume_job(tmp_path, page=0, asking=False):
    sheet = _pages(3)
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=asking)
    job.page = page
    p = H.Person(job, sim)
    assert job.set_options(["-p"], only_locs=_MISSING_1_3).ok
    return job, sim, helper, run, p


@ASKING
def test_m3_missing_on_pages_1_and_3_both_are_read_page_2_never_moves(tmp_path, asking):
    """The reviewer's P4 with three pages: page 3 is reached past the complete page 2, by the
    chart's own page numbers; the caps stay those of the missing patches (pages 1 and 3)."""
    from workflow.i1io.table import caps as cp
    job, sim, helper, run, p = _resume_job(tmp_path, asking=asking)
    assert job.pages_to_read() == [1, 3]
    ready_to_read(job, p)
    assert job.caps == cp.caps_for(cp.ChartShape(((1, 1), (1, 1))))
    res = read_page(job, p)
    assert [r.detail["status"] for r in res] == ["read", "read"] and helper.reads == 2
    assert p.drive(job.home()).ok
    nxt = job.next_page()
    assert nxt.ok and (nxt.detail["page"], nxt.detail["passed_over"]) == (3, [2])
    assert job.page == 2
    assert p.drive(job.align()).ok
    res = read_page(job, p)
    assert [r.detail["status"] for r in res] == ["read", "read"] and helper.reads == 4
    assert p.drive(job.home()).ok
    assert job.next_page().reason == "no_more_pages"


@pytest.mark.parametrize("page", [1, 2], ids=["page2", "page3"])
def test_m3_a_job_built_for_a_later_page_opens(tmp_path, page):
    """The reviewer's P4b: the page is checked against the CHART's pages."""
    job, sim, helper, run, p = _resume_job(tmp_path, page=page)
    r = p.drive(job.open())
    assert r.ok, r.reason


def test_m3_nothing_moves_on_a_page_with_nothing_missing(tmp_path):
    job, sim, helper, run, p = _resume_job(tmp_path, page=1)       # page 2: complete
    assert p.drive(job.open()).ok
    assert p.drive(job.calibrate()).ok                             # moves nothing anyway
    n = len(sim.received)
    for step in ("align", "creep", "check_move", "read_row"):
        r = getattr(job, step)()
        assert (r.kind, r.reason) == (J.Kind.REFUSED, "nothing_missing_on_this_page"), step
    assert len(sim.received) == n
    nxt = job.next_page()
    assert nxt.ok and nxt.detail["page"] == 3 and nxt.detail["passed_over"] == []


def test_m3_page_numbers_stay_the_charts_when_the_whole_chart_is_read(tmp_path):
    sheet = _pages(3)
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=False)
    p = H.Person(job, sim)
    assert job.pages_to_read() == [1, 2, 3]
    ready_to_read(job, p, steps=("open",))
    assert job.next_page().detail == {"page": 2, "passed_over": []}
    assert job.next_page().detail == {"page": 3, "passed_over": []}
    assert job.next_page().reason == "no_more_pages"
    job2, sim2, *_ = RS.make_reading_job(tmp_path / "b", sheet=sheet, aims=H.demo_aims(sheet))
    job2.page = 3
    assert H.Person(job2, sim2).drive(job2.open()).reason == "page_not_in_chart"


# ---- M-4 ------------------------------------------------------------------------------------

def _adopting(tmp_path, asking=False):
    proj, run = project(tmp_path)
    j1, s1, *_r = job_on(run, tmp_path / "first")
    p1 = H.Person(j1, s1)
    ready_to_read(j1, p1)
    assert p1.drive(j1.read_row()).ok          # row 1 of 2, then the process is gone
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND, asking=asking)
    assert job.adopt_earlier(RS.STAMP).ok
    return run, job, sim, helper, p


def _states_at_the_next_start(run, tmp_path):
    job3, *_ = job_on(run, tmp_path / "third", stamp="20261117-170000")
    return {e["stamp"]: e["state"] for e in job3.earlier_sessions()}


@ASKING
def test_m4_an_adopted_session_that_was_saved_is_saved_at_the_next_start(tmp_path, asking):
    """The reviewer's P3: adopt, complete, Save; the next START lists the adopted session as
    saved (by the session that saved it), never as interrupted."""
    import json
    from workflow.i1io.table import measurement as ms
    from workflow.i1io.table import session_end as se
    run, job, sim, helper, p = _adopting(tmp_path, asking)
    ready_to_read(job, p)
    read_page(job, p)
    r, st = _end(job, p, "save")
    assert r.ok and r.detail["adopted_marked_saved"] == [RS.STAMP]
    job.close()
    assert _states_at_the_next_start(run, tmp_path) == {RS.STAMP: se.SAVED, SECOND: se.SAVED}
    rec = json.loads((run.i1io_table_session_dir(RS.STAMP) / ms.SESSION_RESULT)
                     .read_text(encoding="utf-8"))
    assert rec["saved_by"] == SECOND and rec["state"] == "complete"
    assert set(rec) <= {"saved_by", "filed", "state", "verdict", "added", "restored"}


def test_m4_an_adopted_session_that_cannot_be_marked_is_named(tmp_path, monkeypatch):
    from workflow.i1io.table import session_end as se
    run, job, sim, helper, p = _adopting(tmp_path)
    ready_to_read(job, p)
    read_page(job, p)

    def disk_full(sdir, stamp, result):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(se, "mark_saved_by", disk_full)
    r, _st = _end(job, p, "save")
    assert r.ok and r.detail["adopted_marked_saved"] == []
    assert r.detail["adopted_not_marked"] == [RS.STAMP]


# ---- S-4 ------------------------------------------------------------------------------------

def _a_complete_page(tmp_path, sheet=None):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, sheet=sheet)
    ready_to_read(job, p)
    read_page(job, p)
    return run, job, sim, p


def _power_cut_at(monkeypatch, job, where):
    """KeyboardInterrupt (the process gone) at *where* of Save: "result" = the write of
    session_result.json, "filing" = the run's file itself."""
    from workflow.i1io.table import measurement as ms
    if where == "result":
        real = job.diag.write_json

        def lost(rel, data):
            if rel == ms.SESSION_RESULT:
                raise KeyboardInterrupt("power cut")
            return real(rel, data)
        monkeypatch.setattr(job.diag, "write_json", lost)
    else:
        def lost(*a, **k):
            raise KeyboardInterrupt("power cut")
        monkeypatch.setattr(ms, "file_into_run", lost)


def _save_with_a_power_cut(job):
    with pytest.raises(KeyboardInterrupt):
        job.save()


def test_s4_a_crash_after_the_runs_file_is_saved_at_the_next_start(tmp_path, monkeypatch):
    """The reviewer's P8: the run holds the measurement; the next START does not offer the
    session as interrupted, it records the result that was lost, and the session stays saved
    after the run's file changes again."""
    import json
    from workflow.i1io.table import measurement as ms
    from workflow.i1io.table import session_end as se
    run, job, sim, p = _a_complete_page(tmp_path)
    _power_cut_at(monkeypatch, job, "result")
    _save_with_a_power_cut(job)
    sdir = run.i1io_table_session_dir(RS.STAMP)
    assert run.measurement_ti3.is_file() and not (sdir / ms.SESSION_RESULT).exists()
    job2, *_ = job_on(run, tmp_path / "b", stamp=SECOND)
    found = {e["stamp"]: e for e in job2.earlier_sessions()}
    assert found[RS.STAMP]["state"] == se.SAVED
    assert json.loads((sdir / ms.SESSION_RESULT).read_text(encoding="utf-8")) == \
        {"filed": True, "result_recorded_later": True}
    assert job2.adopt_earlier(RS.STAMP).reason == "not_an_interrupted_session"
    with open(run.measurement_ti3, "a", encoding="utf-8") as fh:       # a later Save, say
        fh.write("\n")
    assert se.session_state(sdir, run.measurement_ti3) == se.SAVED


def test_s4_a_crash_before_the_runs_file_changes_is_interrupted(tmp_path, monkeypatch):
    """The other side: the filing note is there, the run's file is not: the readings were never
    saved, and the next START offers them (truthfully) as interrupted."""
    from workflow.i1io.table import measurement as ms
    from workflow.i1io.table import session_end as se
    run, job, sim, p = _a_complete_page(tmp_path)
    _power_cut_at(monkeypatch, job, "filing")
    _save_with_a_power_cut(job)
    sdir = run.i1io_table_session_dir(RS.STAMP)
    assert (sdir / ms.FILING).is_file() and not run.measurement_ti3.exists()
    job2, *_ = job_on(run, tmp_path / "b", stamp=SECOND)
    found = {e["stamp"]: e for e in job2.earlier_sessions()}
    assert found[RS.STAMP]["state"] == se.INTERRUPTED and found[RS.STAMP]["would_make"] == \
        "complete"


def test_s4_an_adopted_session_cut_off_after_filing_is_saved_too(tmp_path, monkeypatch):
    from workflow.i1io.table import session_end as se
    run, job, sim, helper, p = _adopting(tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    _power_cut_at(monkeypatch, job, "result")
    _save_with_a_power_cut(job)
    assert _states_at_the_next_start(run, tmp_path) == {RS.STAMP: se.SAVED, SECOND: se.SAVED}


def test_s4_the_filing_note_holds_a_checksum_and_a_stamp_only(tmp_path):
    import json
    from workflow.i1io.table import measurement as ms
    run, job, sim, p = _a_complete_page(tmp_path)
    assert job.save().ok
    note = json.loads((run.i1io_table_session_dir(RS.STAMP) / ms.FILING)
                      .read_text(encoding="utf-8"))
    assert set(note) == {"filing_by", "sha256"} and note["filing_by"] == RS.STAMP
    assert len(note["sha256"]) == 64


# ---- S-5 ------------------------------------------------------------------------------------

@ASKING
@pytest.mark.parametrize("where", ["filing_note", "begin", "file_into_run"])
def test_s5_a_disk_error_on_save_keeps_the_homing_and_the_readings(tmp_path, monkeypatch,
                                                                   asking, where):
    """An OSError while Save writes: a named refusal, the table still open for sending, the
    homing offered (its own GO), nothing in the run, the readings in the session folder, and
    Save may be asked again."""
    from workflow import measurement_session as msn
    from workflow.i1io.table import measurement as ms
    from workflow.i1io.table import session_end as se
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, asking=asking)
    ready_to_read(job, p)
    read_page(job, p)

    def disk_full(*a, **k):
        raise OSError(28, "No space left on device")
    target = {"filing_note": (se, "write_json_now"), "begin": (msn.MeasurementSession, "begin"),
              "file_into_run": (ms, "file_into_run")}[where]
    with monkeypatch.context() as mp:
        mp.setattr(*target, disk_full)
        n = len(sim.received)
        r, st = _end(job, p, "save")
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "measurement_not_written")
    assert r.detail["error"] == "OSError" and r.detail["readings_kept"] is True
    assert r.detail["next"] == ["home"] and not r.state.sending_closed
    assert job.ended is None and not run.measurement_ti3.exists()
    assert any(run.i1io_table_session_dir(RS.STAMP).glob("row-*/*.row.json"))
    assert len(sim.received) == n
    h = job.home()
    assert (h.kind, h.confirm) == (J.Kind.NEEDS, J.Confirm.GO) and len(sim.received) == n
    assert p.drive(job.answer(J.Confirm.GO, "yes")).ok and job.at_rest()
    r2, _st = _end(job, p, "save")                          # the disk has room again
    assert r2.ok and run.measurement_ti3.is_file()


def test_s5_a_disk_error_while_assembling_is_a_refusal_not_an_exception(tmp_path, monkeypatch):
    from workflow.i1io.table import measurement as ms
    run, job, sim, p = _a_complete_page(tmp_path)

    def disk_full(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(ms, "assemble", disk_full)
    r = job.end()
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "measurement_not_written")
    assert not r.state.sending_closed
    s = job.save()
    assert (s.kind, s.reason) == (J.Kind.REFUSED, "measurement_not_written")


# ---- NOTE: "filed" says whether the run kept the measurement --------------------------------

def test_note_a_restored_earlier_file_is_not_filed(tmp_path, monkeypatch):
    import json
    from workflow import measurement_session as msn
    from workflow.measurement_state import SessionVerdict
    from workflow.i1io.table import measurement as ms
    run, job, sim, p = _a_complete_page(tmp_path)

    def shrank(self, *, resumed, discarded=False):
        return msn.SessionOutcome(verdict=SessionVerdict.RESTORE_AND_KEEP_BOTH, before=9,
                                  after=8, restored=True)
    monkeypatch.setattr(msn.MeasurementSession, "finish", shrank)
    r = job.save()
    assert r.ok and r.detail["restored"] is True and r.detail["message_id"] == "M-TI3-SHRANK"
    rec = json.loads((run.i1io_table_session_dir(RS.STAMP) / ms.SESSION_RESULT)
                     .read_text(encoding="utf-8"))
    assert rec["filed"] is False and rec["restored"] is True


# ---- S-1 ------------------------------------------------------------------------------------

STOPPED_BEFORE = "stopped_before_the_next_move"      # J.STOPPED_BEFORE_THE_NEXT_MOVE


@ASKING
def test_s1_a_stop_pressed_at_the_ending_takes_effect_before_the_next_move(tmp_path, asking):
    """The reviewer's P6: Stop pressed while M-END is shown, then Keep measuring and the next
    row: nothing moves; the row after that asks GO and reads."""
    run, job, sim, p = _one_row(tmp_path, asking)
    assert job.end().confirm == J.Confirm.END
    job.stop_at_next_pause()
    assert job.answer(J.Confirm.END, "keep measuring").ok
    n = len(moves(sim.received))
    r = p.drive(job.read_row())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, STOPPED_BEFORE) and r.detail["by_person"]
    assert len(moves(sim.received)) == n
    g = job.read_row()
    assert g.confirm == J.Confirm.GO and len(moves(sim.received)) == n
    assert p.drive(job.answer(J.Confirm.GO, "yes")).ok


@ASKING
def test_s1_a_stop_between_steps_refuses_the_next_moving_step(tmp_path, asking):
    run, job, sim, p = _one_row(tmp_path, asking)
    job.stop_at_next_pause()
    assert job._go_page is None
    n = len(sim.received)
    r = job.read_row()
    assert (r.kind, r.reason) == (J.Kind.REFUSED, STOPPED_BEFORE) and len(sim.received) == n


@pytest.mark.parametrize("question", [J.Confirm.GO, J.Confirm.SHEET_LAID, J.Confirm.ARM_FELT,
                                      J.Confirm.AIMED])
def test_s1_a_stop_while_a_question_is_shown_ends_the_step_before_it_moves(tmp_path, question):
    """Stop pressed while the alignment waits for an answer; the answer that would let it move
    ends it instead."""
    job, sim, helper, run, p = _job_for(tmp_path, False)
    ready_to_read(job, p, steps=("open", "calibrate"))
    seen = []

    def on_ask(person, res):
        if res.confirm == question and not seen:
            seen.append(len(moves(sim.received)))
            job.stop_at_next_pause()
        return None
    p.on_ask = on_ask
    r = p.drive(job.align())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, STOPPED_BEFORE), r.reason
    assert len(moves(sim.received)) == seen[0]
    assert job._go_page is None and not job._pause_stop


def test_s1_a_stop_while_a_failed_row_asks_again_skip_stop_moves_nothing(tmp_path):
    job, sim, helper, run, p = _job_for(tmp_path, False, rows=(4, 4),
                                        faults={"read_loc": {"0-2": "dies"}})
    ready_to_read(job, p)

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED:
            person.n = len(moves(sim.received))
            job.stop_at_next_pause()
        return None
    p.on_ask = on_ask
    r = p.drive(job.read_row())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, STOPPED_BEFORE)
    assert len(moves(sim.received)) == p.n and job.rows_again.get(0, 0) == 0


def test_s1_the_homing_is_never_refused_for_a_stop_and_uses_it_up(tmp_path):
    run, job, sim, p = _one_row(tmp_path, False)
    job.stop_at_next_pause()
    h = job.home()
    assert h.confirm == J.Confirm.GO                       # the stop's effect: a fresh GO
    assert p.drive(job.answer(J.Confirm.GO, "yes")).ok and not job._pause_stop
    assert p.drive(job.align()).ok                         # nothing stale left behind


def test_s1_a_step_that_moves_nothing_leaves_the_stop_for_the_next_move(tmp_path):
    job, sim, helper, run, p = _job_for(tmp_path, False)
    ready_to_read(job, p, steps=("open",))
    job.stop_at_next_pause()
    assert p.drive(job.calibrate()).ok and job._pause_stop
    assert job.align().reason == STOPPED_BEFORE


# ---- S-2 ------------------------------------------------------------------------------------

@ASKING
def test_s2_discard_after_adopting_discards_the_adopted_session_too(tmp_path, asking):
    """The reviewer's P9 (the coordinator's decision): M-END counted the adopted readings, the
    person discards; both sessions are set to discarded, both folders stay, nothing is filed,
    and the result says which sessions were set to discarded."""
    import json
    from workflow.i1io.table import measurement as ms
    from workflow.i1io.table import session_end as se
    run, job, sim, helper, p = _adopting(tmp_path, asking)
    ready_to_read(job, p)
    read_page(job, p)
    r, st = _end(job, p, "discard")
    assert st["read"] == 8 and st["read_in_this_session"] == 4    # M-END showed both
    assert r.ok and r.detail["discarded_sessions"] == [SECOND, RS.STAMP]
    assert r.detail["session_folder_kept"] and "not_marked" not in r.detail
    assert not run.measurement_ti3.exists()
    job.close()
    assert _states_at_the_next_start(run, tmp_path) == {RS.STAMP: se.DISCARDED,
                                                        SECOND: se.DISCARDED}
    for stamp in (RS.STAMP, SECOND):
        sdir = run.i1io_table_session_dir(stamp)
        assert any(sdir.glob("row-*/*.row.json"))                 # nothing deleted
    rec = json.loads((run.i1io_table_session_dir(RS.STAMP) / ms.DISCARDED)
                     .read_text(encoding="utf-8"))
    assert rec["discarded_with"] == SECOND


def test_s2_a_folder_that_cannot_be_marked_is_named(tmp_path, monkeypatch):
    from workflow.i1io.table import session_end as se
    run, job, sim, helper, p = _adopting(tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    real = se.mark_discarded

    def full(sdir, why, by=None):
        if by is not None:
            raise OSError(28, "No space left on device")
        return real(sdir, why, by=by)
    monkeypatch.setattr(se, "mark_discarded", full)
    r, _st = _end(job, p, "discard")
    assert r.ok and r.detail["discarded_sessions"] == [SECOND]
    assert r.detail["not_marked"] == [RS.STAMP]


# ---- S-3 ------------------------------------------------------------------------------------

def test_s3_adopting_after_open_is_refused(tmp_path):
    """The reviewer's P10: the caps are derived at open(), so adopting comes before it."""
    proj, run = project(tmp_path)
    j1, s1, *_r = job_on(run, tmp_path / "first", sheet=small_sheet([4, 4, 4]))
    p1 = H.Person(j1, s1)
    ready_to_read(j1, p1)
    assert p1.drive(j1.read_row()).ok
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND,
                                 sheet=small_sheet([4, 4, 4]))
    assert p.drive(job.open()).ok
    r = job.adopt_earlier(RS.STAMP)
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "already_opened")
    assert job._earlier_dirs == [] and job.only_locs is None


def test_s3_options_after_open_are_refused(tmp_path):
    job, sim, helper, run, p = _job_for(tmp_path, False)
    assert p.drive(job.open()).ok
    r = job.set_options(["-p"], only_locs={"0-0"})
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "already_opened") and job.only_locs is None


@pytest.mark.parametrize("args", [["-p"], ["-p", "-r"], ["-p", "-N"]])
def test_s3_options_after_adopting_keep_the_adoption(tmp_path, args):
    """The reviewer's P11: the options set after an adoption never undo it (only what is still
    missing is read, the run's partial stays the base)."""
    run, job, sim, helper, p = _adopting(tmp_path)
    missing = set(job.only_locs)
    r = job.set_options(args)
    assert r.ok, r.reason
    assert job.only_locs == missing and r.detail["adopted_still_missing"] == len(missing)
    ready_to_read(job, p)
    res = read_page(job, p)
    assert [x.detail["status"] for x in res] == ["nothing_to_read", "read"]
    assert helper.reads == 4


def test_s3_a_refinement_after_adopting_reads_what_both_ask_for(tmp_path):
    run, job, sim, helper, p = _adopting(tmp_path)              # row 2 ("1-*") still missing
    assert job.set_options(["-p"], only_locs={"0-0", "1-1", "1-2"}).ok
    assert job.only_locs == {"1-1", "1-2"}


def test_s3_adopting_after_options_keeps_the_options(tmp_path):
    proj, run = project(tmp_path)
    j1, s1, *_r = job_on(run, tmp_path / "first")
    p1 = H.Person(j1, s1)
    ready_to_read(j1, p1)
    assert p1.drive(j1.read_row()).ok
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND)
    assert job.set_options(["-p"], only_locs={"0-0", "1-1"}).ok
    r = job.adopt_earlier(RS.STAMP)
    assert r.ok and job.only_locs == {"1-1"} and r.detail["still_missing"] == 1


# ---- S-6: the two planted faults that survived review 8 ------------------------------------

def test_s6_an_adopted_session_cannot_be_discarded_at_the_same_start(tmp_path):
    """Planted fault M1: discard_earlier of an ADOPTED session would drop its readings from the
    assembly while only_locs never reads them again (a silent partial)."""
    run, job, sim, helper, p = _adopting(tmp_path)
    r = job.discard_earlier(RS.STAMP)
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "adopted_already")
    assert not (run.i1io_table_session_dir(RS.STAMP) / "discarded.json").exists()
    ready_to_read(job, p)
    read_page(job, p)
    e, st = _end(job, p, "save")
    assert st["state"] == "complete" and e.ok


@pytest.mark.parametrize("existing", ["no_data_block", "empty_data", "zero_bytes"])
def test_s6_adopting_over_a_measurement_that_is_not_partial_is_refused(tmp_path, existing):
    """Planted fault M6: the run holds a measurement that is neither partial nor complete; the
    adoption itself is refused (not only the later Save)."""
    proj, run = project(tmp_path)
    j1, s1, *_r = job_on(run, tmp_path / "first")
    p1 = H.Person(j1, s1)
    ready_to_read(j1, p1)
    assert p1.drive(j1.read_row()).ok
    head = 'CTI3\n\nDESCRIPTOR "Argyll Calibration Target chart information 3"\n'
    text = {"no_data_block": head,
            "empty_data": head + ("NUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC\n"
                                  "END_DATA_FORMAT\nNUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n"),
            "zero_bytes": ""}[existing]
    run.measurement_ti3.write_text(text, encoding="utf-8")
    from workflow.measurement_state import Ti3State, classify
    assert classify(run.measurement_ti3, run.chart_ti2).state not in (Ti3State.PARTIAL,
                                                                      Ti3State.COMPLETE,
                                                                      Ti3State.ABSENT)
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND)
    r = job.adopt_earlier(RS.STAMP)
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "run_has_a_measurement_already"), r.reason
    assert job._earlier_dirs == [] and job.only_locs is None


# ---- the NOTE items -------------------------------------------------------------------------

def test_note_next_never_names_a_homing_that_would_be_refused(tmp_path):
    """The reviewer's P7 made strict: the instrument out of the arm (an own-tile calibration
    that failed after "ready"): no homing offered; offered, it can run."""
    run, job, sim, p = _one_row(tmp_path, False)
    r, _st = _end(job, p, "save")
    assert r.detail["next"] == ["home"] and job._ready("home") is None
    run2, job2, sim2, p2 = _one_row(tmp_path / "b", False)
    job2.instrument_out = True
    r2, _st = _end(job2, p2, "save")
    assert r2.detail["next"] == [] and job2._ready("home") == "instrument_not_in_the_arm"


def test_note_end_without_a_run_is_refused_not_nothing_read(tmp_path):
    job, sim, helper, run, p = _job_for(tmp_path, False, run=False)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    r = job.end()
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "no_run") and job.ended is None


def test_note_keep_measuring_names_the_current_page(tmp_path):
    run, job, sim, p = _one_row(tmp_path, False)
    r, _st = _end(job, p, "keep measuring")
    assert r.detail["current_page"] == 1
    assert {x["page"] for x in r.detail["missing_rows"]} == {1}


def test_s4_a_filed_session_reads_saved_before_anything_settles_it(tmp_path, monkeypatch):
    """Planted fault S4b (fix8): the state itself, with no earlier_sessions() call first: a
    later START's discard_earlier never marks a filed session discarded."""
    from workflow.i1io.table import measurement as ms
    from workflow.i1io.table import session_end as se
    run, job, sim, p = _a_complete_page(tmp_path)
    _power_cut_at(monkeypatch, job, "result")
    _save_with_a_power_cut(job)
    sdir = run.i1io_table_session_dir(RS.STAMP)
    assert se.session_state(sdir, run.measurement_ti3) == se.SAVED
    assert se.session_state(sdir) == se.INTERRUPTED            # without the run's file: unknown
    job2, *_ = job_on(run, tmp_path / "b", stamp=SECOND)
    assert job2.discard_earlier(RS.STAMP).reason == "not_an_interrupted_session"
    assert not (sdir / ms.DISCARDED).exists()
