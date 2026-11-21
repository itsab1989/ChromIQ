"""4.3.54: a row the ROW PLACEMENT CHECK refuses takes the released path of a row that could not be
read (the job, the simulated table and its table-scan reader; no hardware).

The simulated sheet is read through the i1Pro 2's 4.5 mm opening and laid 2 mm further along the
row than the aims put it, for the attempts named (part_c_sim's ``sheet_offset_mm`` /
``aperture_mm``, reader_sim's ``scan_at``). On this small sheet (rows of 4 patches, 61 mm/s) the
check refuses such a row because the readings put it about 1 mm away from where the timing does
(``edges_disagree_with_timing``). Measured on the simulator's full demo sheet (work folder
sim_offset_out.txt): 2.5 mm off at the default speed the released cut accepts rows with a patch
2.74 dE00 off, and the check refuses every one; 2 mm off with the Row speed factor 1.5, 2.76
dE00, 19 of 22 rows refused.

* the refusal is a failed strip row with its true reason (``strip_placement_not_confirmed``):
  the person is asked as for any failed strip row (again / patch by patch / skip / stop), the
  row record and the detailed table log carry the numbers (which patch, by how many mm);
* read again, a row the readings confirm is accepted; refused again, patch by patch reads it;
* every finished row stays on disk; after a stop at the refused row, the next START completes
  the interrupted session by reading only the unread row, and the values equal an uninterrupted
  measurement's.
"""
from __future__ import annotations

import json

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_ending import SECOND, _end, job_on, project
from tests.i1io_table.test_job_reading import read_page, ready_to_read, small_sheet
from workflow.i1io.table import job as J
from workflow.i1io.table import measurement as ms
from workflow.i1io.table import strip as stp

STRIP = ["-v", "-c", "1", "chart"]
OFF = {"sheet_offset_mm": 2.0, "aperture_mm": 4.5}
CLEAN = {"aperture_mm": 4.5}


def _job(tmp_path, script=None, run=True, stamp=RS.STAMP):
    sheet = small_sheet()
    job, sim, helper, r = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                              ask_after_each_step=False, run=run, stamp=stamp,
                                              faults={"scan": dict(CLEAN)})
    assert job.set_options(STRIP).ok
    return job, sim, helper, r, H.Person(job, sim, script)


def _offset_on(helper, *attempts):
    """The sheet lies 2.5 mm off for the next scan readers named (1 = the next one)."""
    n0 = len(helper.scans)
    helper.faults["scan"] = dict(OFF)
    helper.faults["scan_at"] = tuple(n0 + a for a in attempts)


def _records(job):
    out = []
    for p in sorted(job.diag.folder.rglob("*" + ms.ROW_RECORD_SUFFIX)):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def _log_text(job):
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in job.diag.folder.rglob("*.log"))


def _whys(p):
    seen = []

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED_STRIP:
            seen.append(res.detail["why"])
            person.script[J.Confirm.ROW_FAILED_STRIP] = person.answers.pop(0)
        return None
    p.on_ask = on_ask
    return seen


def _spectra(path):
    from workflow.measurement_pairing import _first_table
    f, rows = _first_table(path.read_text(encoding="utf-8"))
    li = f.index("SAMPLE_LOC")
    si = [i for i, x in enumerate(f) if x.startswith("SPEC_")]
    return {r.split()[li].strip('"'): [r.split()[i] for i in si] for r in rows}


def test_the_clean_simulated_sheet_is_read_in_rows_and_confirmed(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    ready_to_read(job, p)
    rows = read_page(job, p)
    assert all(r.ok and r.detail["row_kind"] == "strip" and r.detail["attempts"] == 1
               for r in rows)
    recs = _records(job)
    assert recs and all(r["placement"]["confirmed"] for r in recs)
    log = _log_text(job)
    assert "row placement check: on (a row is accepted only when its readings confirm" in log
    assert log.count("row placement check: confirmed, every patch") == len(rows)
    job.close()


def test_a_refused_row_is_asked_about_read_again_and_then_accepted(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    ready_to_read(job, p)
    p.answers = ["again"]
    seen = _whys(p)
    _offset_on(helper, 1)
    m2_before = sum(1 for ln in sim.received if ln.startswith(";m2"))
    r = p.drive(job.read_row())
    assert seen == [stp.PLACEMENT_REASON]
    assert r.ok and r.detail["status"] == "read" and r.detail["row_kind"] == "strip"
    assert r.detail["attempts"] == 2 and job.rows_again[0] == 1
    assert sum(1 for ln in sim.received if ln.startswith(";m2")) == m2_before + 2
    first, second = _records(job)[:2]
    assert (first["status"], first["why"]) == ("failed", stp.PLACEMENT_REASON)
    assert first["accepted"] == [] and first["reader_ti3"] is None
    pc = first["placement"]
    assert pc["confirmed"] is False and pc["patch"] and pc["off_mm"] > 0.0, pc
    assert first["failed_loc"] == pc["patch"]
    assert second["status"] == "read" and second["placement"]["confirmed"] is True
    log = _log_text(job)
    assert "row placement check: NOT confirmed" in log
    assert f"patch {pc['patch']}, by {pc['off_mm']:.2f} mm" in log
    job.close()


def test_refused_twice_the_row_is_read_patch_by_patch(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    ready_to_read(job, p)
    p.answers = ["again", "patch by patch"]
    seen = _whys(p)
    _offset_on(helper, 1, 2)
    r = p.drive(job.read_row())
    assert seen == [stp.PLACEMENT_REASON, stp.PLACEMENT_REASON]
    assert r.ok and r.detail["status"] == "read" and r.detail["row_kind"] == "spot"
    assert r.detail["read_patch_by_patch_because"] == "chosen_by_you"
    job.close()


def test_the_released_values_of_an_accepted_row_are_unchanged(tmp_path, monkeypatch):
    """The same simulated sheet read with the check switched off (4.3.53) and on: the row files
    hold the same values, byte for byte (the check only vetoes)."""
    from workflow.i1io.table import placement as pl
    out = {}
    for on in (False, True):
        monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", on)
        job, sim, helper, run, p = _job(tmp_path / str(on))
        ready_to_read(job, p)
        assert all(r.ok for r in read_page(job, p))
        assert job.measurement().ok
        out[on] = _spectra(run.i1io_table_measurement(RS.STAMP))
        job.close()
    assert out[True] == out[False] and len(out[True]) == 8


@pytest.mark.parametrize("asking", [False, True], ids=["unguided_report_off", "report_on"])
def test_every_finished_row_stays_and_the_next_start_reads_only_the_unread(tmp_path, asking):
    proj, run = project(tmp_path)
    sheet = small_sheet()
    # the reference: the same sheet, nothing off, read without a stop
    _p0, run0 = project(tmp_path / "ref", "Ref")
    job0, sim0, helper0, p0 = job_on(run0, tmp_path / "ref" / "s", sheet=sheet,
                                     faults={"scan": dict(CLEAN)})
    assert job0.set_options(STRIP).ok
    ready_to_read(job0, p0)
    read_page(job0, p0)
    assert _end(job0, p0, "save")[0].ok
    want = _spectra(run0.measurement_ti3)
    job0.close()
    # row 1 read; row 2 refused by the check; the person stops there (the process then ends)
    job, sim, helper, p = job_on(run, tmp_path / "first", sheet=sheet, asking=asking,
                                 faults={"scan": dict(CLEAN)})
    assert job.set_options(STRIP).ok
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    p.answers = ["stop"]
    seen = _whys(p)
    _offset_on(helper, 1)
    r = p.drive(job.read_row())
    assert seen == [stp.PLACEMENT_REASON] and not r.ok
    # row 1 is on disk, row 2 is not
    recs = {(x["row"], x["attempt"]): x for x in _records(job)}
    assert recs[(1, 1)]["status"] == "read" and recs[(2, 1)]["status"] == "failed"
    assert len(list(job.diag.folder.rglob(recs[(1, 1)]["reader_ti3"]))) == 1
    assert recs[(2, 1)]["reader_ti3"] is None and recs[(2, 1)]["accepted"] == []
    # the next START completes it, reading only row 2
    job2, sim2, helper2, p2 = job_on(run, tmp_path / "second", stamp=SECOND,
                                     faults={"scan": dict(CLEAN)})
    found = job2.earlier_sessions()
    assert [(e["stamp"], e["state"], e["accepted"]) for e in found] == \
        [(RS.STAMP, "interrupted", 4)]
    assert job2.adopt_earlier(RS.STAMP).ok
    assert job2.set_options(STRIP).ok
    ready_to_read(job2, p2)
    res = read_page(job2, p2)
    assert [x.detail["status"] for x in res] == ["nothing_to_read", "read"]
    assert sum(1 for ln in sim2.received if ln.startswith(";m2")) == 1
    e, st = _end(job2, p2, "save")
    assert st["state"] == "complete" and e.ok
    assert _spectra(run.measurement_ti3) == want
    job2.close()
