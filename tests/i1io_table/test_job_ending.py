"""Build step 8, job side: the end of a table session, against a REAL project folder
(``Project.create``), both report modes.

The endings are the binding specs' own (measurement_exit_strategy.md, unified_measurement_
management.md): M-END's Save and stop / Discard and stop / Keep measuring, and M-END-EMPTY when
nothing was read; the file states are §3a's (complete / partial by location). What is new for
the table: nothing moves in an ending (the homing and Keep measuring each ask their own GO), and
a dismissed ending changes and moves nothing."""
from __future__ import annotations

import json
import shutil

import pytest

from core.file_manager import (I1IO_TABLE_DISCARDED, I1IO_TABLE_SESSION_RESULT, Project)
from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import read_page, ready_to_read, small_sheet
from tests.i1io_table.test_job_safety import moves
from workflow.i1io.table import job as J
from workflow.i1io.table import measurement as ms
from workflow.i1io.table import session_end as se
from workflow.measurement_state import Ti3State, classify

ASKING = pytest.mark.parametrize("asking", [True, False], ids=["asking", "quiet"])
SECOND = "20261117-160000"


def project(tmp_path, name="Table-Target"):
    proj = Project.create(tmp_path / name, name)
    run = proj.current_run()
    run.ensure_dir()
    return proj, run


def job_on(run, tmp_path, script=None, sheet=None, asking=False, stamp=RS.STAMP, **kw):
    sheet = sheet or small_sheet()
    job, sim, helper, _r = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                               run=run, stamp=stamp,
                                               ask_after_each_step=asking, **kw)
    return job, sim, helper, H.Person(job, sim, script)


def _end(job, p, answer):
    r = job.end()
    if r.kind != J.Kind.NEEDS:
        return r, None
    assert (r.confirm, r.choices) == (J.Confirm.END, ("save", "keep measuring", "discard"))
    return job.answer(J.Confirm.END, answer), r.detail["end_state"]


# ---- the end states ---------------------------------------------------------------------------

@ASKING
def test_a_complete_page_ends_complete_and_save_files_it_into_the_run(tmp_path, asking):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, asking=asking)
    ready_to_read(job, p)
    read_page(job, p)
    n = len(sim.received)
    r, st = _end(job, p, "save")
    assert st["state"] == "complete" and st["read"] == st["expected"] == 8
    assert st["missing"] == [] and st["arm_out"] and st["measurement_before"] == "absent"
    assert r.ok and r.detail["ending"] == "saved" and r.detail["next"] == ["home"]
    assert len(sim.received) == n                                   # nothing moved, nothing sent
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE
    assert r.detail["announce"] == run.measurement_ti3.name and r.detail["verdict"] == "keep"
    assert r.detail["added"] == 8 and r.detail["resume_next"] is False
    # the homing after Save and stop needs its own hands-off GO
    h = job.home()
    assert (h.kind, h.confirm) == (J.Kind.NEEDS, J.Confirm.GO) and len(sim.received) == n
    assert p.drive(job.answer(J.Confirm.GO, "yes")).ok
    job.close()
    summary = json.loads((run.i1io_table_session_dir(RS.STAMP) / "session_summary.json")
                         .read_text(encoding="utf-8"))
    assert summary["ending"] == "saved" and summary["accepted_readings"] == 8


@ASKING
def test_a_partial_session_names_what_is_missing_and_saves_as_partial(tmp_path, asking):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, {J.Confirm.ROW_FAILED: "skip"}, asking=asking,
                                 faults={"read_loc": {"1-2": "dies"}})
    ready_to_read(job, p)
    read_page(job, p)
    r, st = _end(job, p, "save")
    assert st["state"] == "partial"
    # row 2's reader died at its 2nd patch: its first reading was never saved, so the whole
    # row is missing, and only it
    assert st["missing"] == [{"page": 1, "rows": [{"row": 2, "patches": 4,
                                                   "locs": ["1-0", "1-1", "1-2", "1-3"]}]}]
    assert r.ok and r.detail["measurement"]["state"] == "partial"
    assert r.detail["resume_next"] is True
    facts = classify(run.measurement_ti3, run.chart_ti2)
    assert facts.state is Ti3State.PARTIAL and facts.held == 4


@ASKING
def test_nothing_read_asks_nothing_and_saves_nothing(tmp_path, asking):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, asking=asking)
    ready_to_read(job, p)
    r = job.end()
    assert r.ok and r.confirm is None and r.detail["ending"] == "nothing_read"
    assert r.detail["end_state"]["state"] == se.EMPTY
    assert not run.measurement_ti3.exists()
    assert job.end().reason == "ended_already_nothing_read"


@ASKING
def test_keep_measuring_moves_nothing_and_the_next_row_needs_go(tmp_path, asking):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, asking=asking)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    if job.report_due:
        job.answer(J.Confirm.REPORT_AFTER_STEP, "as described")
    n = len(sim.received)
    r, st = _end(job, p, "keep measuring")
    assert r.ok and r.detail["ending"] == "keep_measuring"
    assert r.detail["missing_rows"] == [{"page": 1, "row": 2, "patches": 4}]
    assert len(sim.received) == n and not run.measurement_ti3.exists()
    g = job.read_row()
    assert (g.kind, g.confirm) == (J.Kind.NEEDS, J.Confirm.GO) and len(sim.received) == n
    assert p.drive(job.answer(J.Confirm.GO, "yes")).ok
    r2, st2 = _end(job, p, "save")
    assert st2["state"] == "complete" and r2.ok


@ASKING
def test_discard_files_nothing_and_the_folder_stays_marked_and_can_be_set_aside(tmp_path,
                                                                               asking):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, asking=asking)
    ready_to_read(job, p)
    read_page(job, p)
    n = len(sim.received)
    r, st = _end(job, p, "discard")
    assert r.ok and r.detail["ending"] == "discarded" and r.detail["session_folder_kept"]
    assert len(sim.received) == n and not run.measurement_ti3.exists()
    sdir = run.i1io_table_session_dir(RS.STAMP)
    assert (sdir / I1IO_TABLE_DISCARDED).is_file() and ms.DISCARDED == I1IO_TABLE_DISCARDED
    assert any(sdir.glob("row-*/*.ti3"))                  # the raw readings stay
    assert job.save().reason == "discarded"
    job.close()
    assert run.i1io_table_discarded_sessions() == [sdir]
    files = sorted(x.relative_to(sdir) for x in sdir.rglob("*"))
    moved = se.set_aside(run, RS.STAMP)
    assert moved == run.i1io_table_session_archive_dir(RS.STAMP) == \
        run.old_dir / "i1io-table" / RS.STAMP
    assert sorted(x.relative_to(moved) for x in moved.rglob("*")) == files   # all of it moved
    assert run.i1io_table_discarded_sessions() == []


def test_only_a_discarded_session_is_ever_set_aside(tmp_path):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    assert se.set_aside(run, RS.STAMP) is None                      # interrupted: kept
    job.save()
    assert se.set_aside(run, RS.STAMP) is None                      # saved: kept
    assert run.i1io_table_session_dir(RS.STAMP).is_dir()


@ASKING
def test_a_dismissed_ending_changes_nothing_and_never_moves(tmp_path, asking):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, asking=asking)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    if job.report_due:
        job.answer(J.Confirm.REPORT_AFTER_STEP, "as described")
    n = len(sim.received)
    r = job.end()
    assert r.confirm == J.Confirm.END
    d = job.dismiss_end()
    assert d.ok and d.detail == {"ending": "dismissed"}
    assert len(sim.received) == n and not sim.moving and not run.measurement_ti3.exists()
    assert job.ended is None and job._gen is None
    assert not (run.i1io_table_session_dir(RS.STAMP) / I1IO_TABLE_DISCARDED).exists()
    # dismissing again is refused; the ending can be asked again; any move needs a GO
    assert job.dismiss_end().reason == "no_ending_open"
    g = job.read_row()
    assert g.confirm == J.Confirm.GO and len(sim.received) == n
    job.answer(J.Confirm.GO, "back")
    assert job.end().confirm == J.Confirm.END


def test_the_end_is_asked_only_between_steps(tmp_path):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    p.drive(job.open())
    r = job.calibrate()
    assert r.kind == J.Kind.NEEDS
    assert job.end().reason == "another_step_waits_for_a_confirmation"


def test_a_stop_inside_a_row_then_the_end(tmp_path):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    ready_to_read(job, p)
    helper.on_read = lambda n: job.stop_at_next_pause() if n == 2 else None
    assert p.drive(job.read_row()).reason == "stopped_between_patches"
    r, st = _end(job, p, "save")
    assert st["state"] == "partial" and st["read"] == 2 and r.ok
    assert r.detail["next"] == ["home"]


def test_after_a_lost_link_the_end_saves_and_offers_no_homing(tmp_path):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    sim.inject_at(len(sim.received) + 1, "unplug", 1.0)
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.STOPPED and r.reason == "link_lost"
    e, st = _end(job, p, "save")
    assert e.ok and e.detail["next"] == [] and st["way_back"].startswith("link_lost")


# ---- save into a real project: the app's own paths take the result unchanged ------------------

def test_the_saved_measurement_is_what_the_apps_measurement_paths_read(tmp_path):
    from workflow.measurement_report import build_report
    from workflow.run_compliance import run_context_for
    from workflow.ti3_analysis import parse_ti3
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    r, _st = _end(job, p, "save")
    ti3 = run.measurement_ti3
    assert r.ok and ti3.parent == run.dir and ti3.name == f"{run.stem}.ti3"
    data = parse_ti3(ti3)                       # what the overlay and the profile tab read
    assert data.n_patches == 8
    ctx = run_context_for(ti3)                  # what the report's limits are looked up by
    assert ctx is not None and ctx.run.dir == run.dir
    report = build_report(ti3)                  # what is saved after a measurement
    assert isinstance(report, dict) and report
    # the project loads as before, the table's folder untouched
    before = sorted(x.relative_to(run.dir) for x in run.i1io_table_dir.rglob("*"))
    loaded = Project.load(proj.root)
    lrun = loaded.current_run()
    assert lrun.measurement_ti3 == ti3 and classify(ti3, lrun.chart_ti2).state is \
        Ti3State.COMPLETE
    assert sorted(x.relative_to(run.dir) for x in run.i1io_table_dir.rglob("*")) == before


def test_save_never_replaces_a_measurement_the_run_has(tmp_path):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    shutil.copyfile(run.chart_ti2, run.measurement_ti3)       # any earlier file
    before = run.measurement_ti3.read_bytes()
    r, _st = _end(job, p, "save")
    assert r.kind == J.Kind.REFUSED and r.reason == "run_has_a_measurement_already"
    assert run.measurement_ti3.read_bytes() == before and job.ended is None


# ---- resume: a later session completes a partial measurement ---------------------------------

def test_resume_reads_only_the_missing_patches_with_caps_from_what_is_missing(tmp_path):
    proj, run = project(tmp_path)
    sheet = small_sheet([4, 4, 4])
    job, sim, helper, p = job_on(run, tmp_path / "a", {J.Confirm.ROW_FAILED: "skip"},
                                 sheet=sheet, faults={"read_loc": {"1-0": "dies"}})
    ready_to_read(job, p)
    read_page(job, p)
    assert _end(job, p, "save")[0].detail["measurement"]["state"] == "partial"
    job.close()
    full_caps = job.caps
    job2, sim2, helper2, p2 = job_on(run, tmp_path / "b", sheet=sheet, stamp=SECOND)
    assert job2.set_options(["-p", "-r"]).detail["resume_unread"] == 4
    ready_to_read(job2, p2)
    assert job2.caps.lines < full_caps.lines and job2.caps.moves < full_caps.moves
    res = read_page(job2, p2)
    assert [x.detail["status"] for x in res] == ["nothing_to_read", "read", "nothing_to_read"]
    assert helper2.reads == 4
    r, st = _end(job2, p2, "save")
    assert st["state"] == "complete" and r.ok
    assert (r.detail["verdict"], r.detail["before"], r.detail["after"], r.detail["added"]) == \
        ("keep", 8, 12, 4)
    # the partial was copied into old/ before it was replaced (§2a)
    assert r.detail["archive"] and any((run.old_dir / r.detail["archive"]).glob("*.ti3"))


def test_caps_for_missing_counts_only_the_missing():
    from workflow.i1io.table import caps as cp
    sheet = small_sheet([4, 4, 4], pages=2)
    sheet["pages"][1]["strips"] = [{**st, "patches": [{**q, "loc": "P2-" + q["loc"]}
                                                      for q in st["patches"]]}
                                   for st in sheet["pages"][1]["strips"]]
    # two missing in row 2 of page 1, one in row 3 of page 2: only those rows, those pages
    assert cp.caps_for_missing(sheet, {"1-0", "1-1", "P2-2-3"}) == \
        cp.caps_for(cp.ChartShape(((2,), (1,))))
    assert cp.caps_for_missing(sheet, set()) == cp.caps_for_sheet(sheet)


# ---- an interrupted session (a crash, a logout, a power cut) at the next START ---------------

def _interrupted(run, tmp_path, sheet=None):
    job, sim, helper, p = job_on(run, tmp_path / "first", sheet=sheet)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    return job                                   # no end, no close: the process is gone


def test_the_next_start_finds_an_interrupted_session_and_completes_it(tmp_path):
    proj, run = project(tmp_path)
    _interrupted(run, tmp_path)
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND)
    found = job.earlier_sessions()
    assert [(e["stamp"], e["state"], e["accepted"], e["pending_marker"]) for e in found] == \
        [(RS.STAMP, "interrupted", 4, False)]
    assert (found[0]["would_make"], found[0]["read"], found[0]["expected"]) == ("partial", 4, 8)
    assert not run.measurement_ti3.exists()                  # finding it filed nothing
    r = job.adopt_earlier(RS.STAMP)
    assert r.ok and (r.detail["read"], r.detail["still_missing"]) == (4, 4)
    ready_to_read(job, p)
    res = read_page(job, p)
    assert [x.detail["status"] for x in res] == ["nothing_to_read", "read"]
    e, st = _end(job, p, "save")
    assert st["state"] == "complete" and e.ok
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE
    job.close()
    assert json.loads((run.i1io_table_session_dir(SECOND) / "session_summary.json")
                      .read_text(encoding="utf-8"))["adopted"] == [RS.STAMP]


def test_the_next_start_can_discard_an_interrupted_session(tmp_path):
    proj, run = project(tmp_path)
    _interrupted(run, tmp_path)
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND)
    assert job.discard_earlier(RS.STAMP).ok
    assert job.earlier_sessions()[0]["state"] == "discarded"
    assert job.adopt_earlier(RS.STAMP).reason == "not_an_interrupted_session"
    assert run.i1io_table_session_dir(RS.STAMP).is_dir()          # kept, marked
    assert run.i1io_table_discarded_sessions() == [run.i1io_table_session_dir(RS.STAMP)]


def test_an_earlier_session_with_a_pending_marker_is_reported_and_the_open_asks(tmp_path):
    proj, run = project(tmp_path)
    _interrupted(run, tmp_path)
    run.i1io_table_pending_marker(RS.STAMP).write_text("pending\n", encoding="utf-8")
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND)
    found = job.earlier_sessions()
    assert found[0]["pending_marker"] is True and found[0]["marker_acknowledged"] is False
    r = job.open()
    assert r.confirm == J.Confirm.MARKER and sim.received == []


def test_adopting_is_refused_over_a_complete_measurement_and_after_rows_were_read(tmp_path):
    proj, run = project(tmp_path)
    _interrupted(run, tmp_path)
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND)
    ready_to_read(job, p)
    read_page(job, p)
    assert job.adopt_earlier(RS.STAMP).reason == "rows_read_already"
    _end(job, p, "save")
    job3, *_ = job_on(run, tmp_path / "third", stamp="20261117-170000")
    assert job3.adopt_earlier(RS.STAMP).reason == "run_has_a_complete_measurement"


# ---- diagnostics: what the analysis script reads ------------------------------------------------

def test_the_row_blocks_carry_the_analysis_scripts_keys(tmp_path):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    _end(job, p, "save")
    job.close()
    log = run.i1io_table_log(RS.STAMP).read_text(encoding="utf-8")
    blocks = [json.loads(ln[ln.index("{"):]) for ln in log.splitlines()
              if ln.startswith("RESULT") and '"verdict"' in ln]
    rows = [b for b in blocks if b["stage"] == "row"]
    assert len(rows) == 2
    need = {"stage", "run", "verdict", "why", "lines_before", "lines_after", "moves_before",
            "moves_after", "position_before", "position_after", "last_read", "arm_free",
            "mode_on", "movement_unconfirmed", "t_start", "t_end", "answers", "data", "folder"}
    for b in rows:
        assert need <= set(b)
        for row in b["data"]["rows"]:
            assert {"row", "kind", "why", "notes"} <= set(row)
        assert b["data"]["spot_readings"] == 4
    csv = next(run.i1io_table_session_dir(RS.STAMP).glob("row-1/*.readings.csv"))
    head = csv.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert head[7] == "Y" and head[10] == "plausible"          # the script's column numbers
    assert (run.i1io_table_session_dir(RS.STAMP) / I1IO_TABLE_SESSION_RESULT).is_file()
