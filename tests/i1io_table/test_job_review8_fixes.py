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


def _job_for(tmp_path, asking, script=None, rows=(4, 4, 4)):
    from tests.i1io_table.test_job_reading import job_for
    return job_for(tmp_path, script, sheet=small_sheet(list(rows)), asking=asking)


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
