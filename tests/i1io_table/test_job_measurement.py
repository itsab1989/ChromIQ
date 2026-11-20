"""Build step 7: from the table job's readings to the run's measurement.

The values are the helper's own (chartread's writer, row by row); the joining is the
i1Profiler import's (match_by_name, attach_device_values_from_chart) and the states are the
app's (measurement_state.classify). A session that did not read every patch can never look
complete; nothing reaches ``Run.measurement_ti3`` except by save(); a discarded session is
never used; a later session completes a partial one."""
from __future__ import annotations

import json

from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import job_for, read_page, ready_to_read, small_sheet
from workflow.i1io.table import job as J
from workflow.i1io.table import measurement as ms
from workflow.measurement_pairing import DEVICE_FROM_CHART_KEYWORD, chart_locations
from workflow.measurement_state import Ti3State, classify, unread_locations


def _rows(path):
    from workflow.measurement_pairing import _first_table
    fields, rows = _first_table(path.read_text(encoding="utf-8"))
    return fields, [r.split() for r in rows]


def test_a_whole_page_becomes_a_complete_measurement_in_the_charts_order(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    assert not run.measurement_ti3.exists()            # nothing in the run before Save
    r = job.save()
    assert r.ok and r.detail["measurement"]["state"] == "complete"
    ti3 = run.measurement_ti3
    assert classify(ti3, run.chart_ti2).state is Ti3State.COMPLETE
    fields, rows = _rows(ti3)
    assert fields[:5] == ["SAMPLE_ID", "SAMPLE_LOC", "RGB_R", "RGB_G", "RGB_B"]
    assert [x[1].strip('"') for x in rows] == chart_locations(run.chart_ti2)
    _cf, crows = _rows(run.chart_ti2)
    # the chart's own ids and device values beside each reading (the import's own step)
    assert [x[:5] for x in rows] == [c[:5] for c in crows]
    text = ti3.read_text(encoding="utf-8")
    assert f'KEYWORD "{DEVICE_FROM_CHART_KEYWORD}"' in text
    assert 'KEYWORD "MEASUREMENT_TABLE"' in text and 'MEASUREMENT_TABLE "i1iO 2"' in text
    assert 'TARGET_INSTRUMENT "X-Rite i1 Pro 2"' in text
    assert "SPEC_380" in fields and "XYZ_Y" in fields
    # every value is the helper's: equal to what the row files say for that patch
    reader_vals = {}
    for f in run.i1io_table_session_dir(RS.STAMP).glob("row-*/p1_row*.ti3"):
        _f, rr = _rows(f)
        for x in rr:
            reader_vals[x[1]] = x[5:]
    assert all(reader_vals[x[1]] == x[5:] for x in rows)
    assert json.loads((run.i1io_table_session_dir(RS.STAMP) / "session_result.json")
                      .read_text(encoding="utf-8")) == {"filed": True, "state": "complete",
                                                        "verdict": "keep", "added": 8,
                                                        "restored": False}


def test_a_session_with_a_row_missing_never_looks_complete(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.ROW_FAILED: "skip"},
                                       faults={"read": {1: "dies_twice"}})
    ready_to_read(job, p)
    read_page(job, p)
    r = job.save()
    assert r.ok and r.detail["measurement"]["state"] == "partial"
    facts = classify(run.measurement_ti3, run.chart_ti2)
    assert facts.state is Ti3State.PARTIAL and facts.held == 4 and facts.expected == 8
    assert unread_locations(run.measurement_ti3, run.chart_ti2) == {"0-0", "0-1", "0-2", "0-3"}
    text = run.measurement_ti3.read_text(encoding="utf-8")
    assert "NUMBER_OF_SETS 4" in text


def test_a_later_session_completes_the_partial_one_reading_only_what_is_missing(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.ROW_FAILED: "skip"},
                                       faults={"read_loc": {"1-1": "dies"}})
    ready_to_read(job, p)
    read_page(job, p)
    assert job.save().detail["measurement"]["state"] == "partial"
    job.close()
    before = run.measurement_ti3.read_text(encoding="utf-8")
    # the next START on the same run: resume (-r), a fresh table and helper
    sheet = small_sheet()
    job2, sim2, helper2, _r, p2 = job_for(tmp_path / "second", sheet=sheet)
    job2.run = run
    job2._chart_ti2 = run.chart_ti2
    job2.stamp = "20261117-150000"
    from workflow.i1io.table.diagnostics import Diagnostics
    job2.diag = Diagnostics(run.i1io_table_session_dir(job2.stamp),
                            run.i1io_table_log(job2.stamp))
    r = job2.set_options(["-p", "-r"])
    # 4.3.46 fix round 2: row 2's reader died at 1-1 after reading 1-3 and 1-2, which the
    # helper had saved (after every reading): the run lacks only 1-1 and 1-0 (before: the row)
    assert r.ok and r.detail["resume_unread"] == 2
    ready_to_read(job2, p2)
    res = read_page(job2, p2)
    assert [x.detail["status"] for x in res] == ["nothing_to_read", "read"]
    assert helper2.reads == 2                       # only the two patches the run lacked
    s = job2.save()
    assert s.ok and s.detail["measurement"]["state"] == "complete"
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE
    # the first session's rows are the same lines as before (oldest, kept)
    old = {ln.split()[1]: ln for ln in before.splitlines() if ln[:1].isdigit()}
    new = {ln.split()[1]: ln for ln in run.measurement_ti3.read_text(
        encoding="utf-8").splitlines() if ln[:1].isdigit()}
    assert all(new[k] == v for k, v in old.items())


def test_resume_without_a_partial_measurement_is_refused(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    assert job.set_options(["-p", "-r"]).reason == "nothing_to_resume"


def test_discard_writes_nothing_into_the_run_and_the_readings_are_never_used(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    assert job.discard().ok
    assert not run.measurement_ti3.exists()
    assert job.save().reason == "discarded" and not run.measurement_ti3.exists()
    sdir = run.i1io_table_session_dir(RS.STAMP)
    assert (sdir / ms.DISCARDED).is_file()
    a = ms.assemble([sdir], run.chart_ti2, tmp_path / "later.ti3")
    assert a.state == "empty"


def test_save_never_replaces_a_measurement_the_run_already_has(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    run.measurement_ti3.write_text("CTI3\n", encoding="utf-8")
    r = job.save()
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "run_has_a_measurement_already")
    assert run.measurement_ti3.read_text(encoding="utf-8") == "CTI3\n"


def test_a_session_that_was_cut_off_can_be_assembled_from_its_folder_later(tmp_path):
    """The machine may log its user out mid-run: every row record and reader file is on disk
    as the row ends, so the session folder alone gives the measurement (the rows that ended)."""
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    # no save, no close: the process ends here
    a = ms.assemble([run.i1io_table_session_dir(RS.STAMP)], run.chart_ti2, tmp_path / "x.ti3")
    assert a.state == "partial" and a.read == 4


def test_a_saved_value_that_differs_from_the_reading_is_left_out(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    sdir = run.i1io_table_session_dir(RS.STAMP)
    f = next(sdir.glob("row-*/p1_row1.ti3"))
    lines = f.read_text(encoding="utf-8").splitlines()
    k = next(i for i, ln in enumerate(lines) if '"0-1"' in ln)
    parts = lines[k].split()
    parts[6] = f"{float(parts[6]) + 1.0:.6f}"            # XYZ_Y changed after the reading
    lines[k] = " ".join(parts)
    f.write_text("\n".join(lines), encoding="utf-8")
    a = ms.assemble([sdir], run.chart_ti2, tmp_path / "x.ti3")
    assert a.state == "partial" and a.read == 3
    assert a.rejected == (("0-1", "saved_value_differs_from_the_reading"),)


def test_readings_that_name_another_chart_are_refused_and_nothing_is_written(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    other = tmp_path / "other.ti2"
    other.write_text(RS.chart_ti2_text(small_sheet([2])).replace('"0-', '"X-'),
                     encoding="ascii")
    out = tmp_path / "x.ti3"
    a = ms.assemble([run.i1io_table_session_dir(RS.STAMP)], other, out)
    assert (a.state, a.reason) == ("refused", "readings_do_not_name_this_chart")
    assert not out.exists()


def test_the_options_lab_and_xyz_reach_the_measurement_as_chartread_writes_them(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    assert job.set_options(["-p", "-L"]).ok
    ready_to_read(job, p)
    read_page(job, p)
    assert job.save().ok
    fields, _rows_ = _rows(run.measurement_ti3)
    assert {"XYZ_X", "LAB_L", "SPEC_730"} <= set(fields)


def test_nothing_reaches_the_run_while_reading(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    m = job.measurement()
    assert m.ok and not run.measurement_ti3.exists()
    assert run.i1io_table_measurement(RS.STAMP).is_file()
    job.close()
    assert not run.measurement_ti3.exists()
