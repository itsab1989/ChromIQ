# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.54 release, the verification's MUST (verify_rel454.txt): the CHROMIQ_ROW_SPEED mark is
decided from EVERY row the saved measurement uses, whichever sitting read it. A sitting stopped
without Save (a crash, a power cut, a window closed) is taken over by the next START: its rows go
into the saved file, so its fast rows must mark it. A row of the taken-over sitting that the
measurement no longer uses (refused at 1.95 and read again at 1.00, or owned by a later record)
does not.
On the simulated table and the simulated helper (the reviewer's probe, made a test)."""
from __future__ import annotations

from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_ending import SECOND, _end, job_on, project
from tests.i1io_table.test_job_reading import read_page, ready_to_read, small_sheet
from tests.i1io_table.test_4354_row_placement_job import STRIP, CLEAN
from workflow import ti3_provenance as tp
from workflow.i1io.table import job as J
from workflow.i1io.table import strip as stp

OFF = {"sheet_offset_mm": 2.5, "aperture_mm": 4.5}


def _first_sitting(run, tmp_path, offset_first=False):
    """Row 1 read at 1.95 (refused once by the placement check and read again at 1.00 when
    *offset_first*), then the sitting ends without Save. Returns its own mark."""
    job, sim, helper, p = job_on(run, tmp_path / "first", sheet=small_sheet(),
                                 faults={"scan": dict(CLEAN)})
    job.row_speed_factor = 1.95
    assert job.set_options(STRIP).ok
    ready_to_read(job, p)
    if offset_first:
        n0 = len(helper.scans)
        helper.faults["scan"] = dict(OFF)
        helper.faults["scan_at"] = (n0 + 1,)

        def on_ask(person, res):
            if res.confirm == J.Confirm.ROW_FAILED_STRIP:
                assert res.detail["why"] == stp.PLACEMENT_REASON
                person.script[J.Confirm.ROW_FAILED_STRIP] = "again"
            return None
        p.on_ask = on_ask
    assert p.drive(job.read_row()).ok
    mark = job.row_speed_mark()
    job.close()
    return mark


def _second_sitting(run, tmp_path):
    """The next START takes the first sitting over at factor 1.00 and saves the page."""
    job2, sim2, helper2, p2 = job_on(run, tmp_path / "second", stamp=SECOND,
                                     faults={"scan": dict(CLEAN)})
    assert job2.adopt_earlier(RS.STAMP).ok
    assert job2.set_options(STRIP).ok           # factor 1.00
    ready_to_read(job2, p2)
    read_page(job2, p2)
    e, _st = _end(job2, p2, "save")
    assert e.ok
    mark = tp.read_row_speed(run.measurement_ti3)
    job2.close()
    return mark


def test_the_fast_rows_of_a_taken_over_sitting_keep_the_mark(tmp_path):
    proj, run = project(tmp_path)
    first = _first_sitting(run, tmp_path)
    assert first is not None and first.startswith("factor 1.95: "), first
    mark = _second_sitting(run, tmp_path)
    assert mark is not None, "the taken-over fast row's values are in the file without the mark"
    assert mark.startswith("factor 1.95: ") and "rows faster than the safe border" in mark, mark


def test_a_taken_over_fast_row_the_measurement_no_longer_uses_counts_nothing(tmp_path):
    """The ownership rule on row records (a later START cannot read an adopted row again: its
    read_row says nothing_to_read, so this is built from records): a fast row of an earlier
    sitting whose patches a later record owns adds nothing; one that still owns a patch adds
    its mark; records without "row_speed" (4.3.53, dual, patch by patch) add nothing."""
    import json
    from types import SimpleNamespace
    from workflow.i1io.table import measurement as ms

    def rec(sdir, seq, row, locs, row_speed=None, status="read"):
        d = sdir / f"row-{row}"
        d.mkdir(parents=True, exist_ok=True)
        r = {"seq": seq, "row": row, "status": status, "kind": "strip",
             "accepted": [{"loc": x} for x in locs]}
        if row_speed is not None:
            r["row_speed"] = row_speed
        (d / f"p1_row{row}_{seq}{ms.ROW_RECORD_SUFFIX}").write_text(json.dumps(r), "utf-8")

    a, b, now = tmp_path / "a", tmp_path / "b", tmp_path / "now"
    rec(a, 1, 1, ["0-0", "0-1"], [1.95, True])     # later owned by b's row 1: not used
    rec(a, 2, 2, ["1-0", "1-1"], [1.95, False])    # still used
    rec(a, 3, 3, ["2-0"])                          # 4.3.53 record: no mark
    rec(b, 1, 1, ["0-0", "0-1"], [1.0, False])
    rec(b, 2, 4, ["3-0"], [1.5, True], status="failed")   # failed: never used
    fake = SimpleNamespace(_earlier_dirs=[a, b], run=object(),
                           _session_dirs=lambda: [a, b, now])
    got = J.TableJob._taken_over_row_speed_marks(fake)
    assert sorted(got) == [(1.0, False), (1.95, False)], got


def test_a_taken_over_row_refused_fast_and_read_again_at_one_leaves_no_mark(tmp_path):
    proj, run = project(tmp_path)
    assert _first_sitting(run, tmp_path, offset_first=True) is None
    assert _second_sitting(run, tmp_path) is None
