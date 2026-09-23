"""A recalculation must not stamp "not computed" over a number it can compute.

`_recalculate_run` reads each dated report off disk and re-stamps it with the
run's current limits. `stamp_verdict` judges the BLOCKS THE FILE CARRIES, and a
report saved before a block existed carries none, so every row that reads that
block is judged N-A with the reason *"this value is not in this saved report;
it was not one of the values ChromIQ kept when the report was saved"* -- and
`rewrite_report` puts that on disk, permanently, with the measurement that
answers it sitting in the same folder.

MEASURED 2026-09-22 on a report saved by the build immediately before this one,
in the branch's own demo pack: 13 recorded rows became 15, and both of ChromIQ's
two repeatability rows came out N-A with that reason. The two doors that reach
this are "Unlock this run's limits" and the Report limits window's Save, so it
is a routine act, not an exotic one.

This is the same fault `_report_needs_rebuilding` exists for, at the door that
WRITES instead of the one that reads. The cure is the same: rebuild the report
from its own measurement first. Nothing is re-graded by that -- the verdict is
stamped afterwards, from the run's current limits, exactly as before.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import workflow.measurement_report as mr                        # noqa: E402
from workflow.compliance_sets import N_A, effective_limits      # noqa: E402

#: The two rows whose blocks arrived on 2026-09-21, which is what made this
#: measurable. Any row added after a report was saved has the same shape.
NEW_ROWS = ("repeat_patches_de00_max", "repeat_measurement_de00_max")
NEW_BLOCKS = ("repeat_within_sheet", "repeat_across_sheets")


def _a_report_from_an_older_chromiq(tmp_path):
    """A real measurement, a real report, and the blocks a newer build added
    taken back out of it: exactly what beta 29 left on disk."""
    from tests.test_report_judging import _colours, _ramp, _write_ti3

    # `_write_ti3` RENAMES the file for a verification sheet, so the path it
    # returns is the one that exists.
    p = _write_ti3(tmp_path / "m.ti3", _ramp(16) + _colours(),
                   verification=True)
    rep = mr.build_report(p)
    assert all(b in rep for b in NEW_BLOCKS), \
        "the builder no longer writes these blocks, so this test proves nothing"
    for b in NEW_BLOCKS:
        rep.pop(b)
    return p, rep


def _stamp(rep):
    mr.stamp_verdict(rep, effective_limits("chromiq_default", None),
                     set_id="chromiq_default",
                     set_label="ChromIQ default (recommended)")
    return {r.get("row_id"): r for r in rep["verdict"]["rows"]}


def test_the_measured_fault_without_the_rebuild(tmp_path):
    """The state this is about, so the fix below is measured against something.

    Re-stamping the file as it stands invents an N-A for a row nobody could
    have answered, and a reason that is not true of it.
    """
    _p, rep = _a_report_from_an_older_chromiq(tmp_path)
    rows = _stamp(rep)
    for rid in NEW_ROWS:
        assert rows[rid]["word"] == N_A
        assert rows[rid]["reason"] == mr.REASON_NOT_COMPUTED


def test_rebuilding_first_answers_the_rows(tmp_path):
    """And with the rebuild the recalculation now does, the rows are answered
    or are refused for a reason about the CHART, never "it is not in the file".

    A 16-step ramp plus the colour patches repeats no device colour and has no
    earlier measurement, so the honest answers here are the chart's own reasons
    -- what must never come back is `not_computed`, which is a statement about
    ChromIQ's own record and not about the sheet.
    """
    p, rep = _a_report_from_an_older_chromiq(tmp_path)
    created = rep.get("created")
    kept = {k: rep[k] for k in ("pass_thresholds", "verdict", "compliance",
                                "report_type", "document") if k in rep}
    rep = mr.build_report(p)
    if created:
        rep["created"] = created
    rep.update(kept)
    rows = _stamp(rep)
    for rid in NEW_ROWS:
        assert rows[rid]["reason"] != mr.REASON_NOT_COMPUTED, (
            f"{rid} is still judged 'not in this saved report' after the "
            f"report was rebuilt from the measurement that answers it")
        assert rows[rid]["reason"] in (None, *mr.REPEATABILITY_REASONS), \
            rows[rid]["reason"]


def test_the_rebuild_keeps_the_reports_own_date(tmp_path):
    """A rebuild recomputes statistics. It must not re-date the document: the
    date is what the history is ordered and compared by."""
    p, rep = _a_report_from_an_older_chromiq(tmp_path)
    rep["created"] = "2026-01-05T10:00:00"
    kept = {k: rep[k] for k in ("verdict", "compliance") if k in rep}
    fresh = mr.build_report(p)
    fresh["created"] = rep["created"]
    fresh.update(kept)
    assert fresh["created"] == "2026-01-05T10:00:00"


# RETIRED BY K31 (beta 40): `test_the_window_really_rebuilds_before_it_stamps`.
# The seam it read, _recalculate_run, is removed (K31). The helper
# composition the other tests in the file pin (rebuild first, keep the date)
# is what an Update still relies on through _gather_runs.
