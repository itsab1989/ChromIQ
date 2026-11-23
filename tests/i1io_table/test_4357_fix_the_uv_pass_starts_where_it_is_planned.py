"""4.3.57 fix round (review F3): a dual row's UV pass starts where its plan says, within 0.5 mm.

Part B of 4.3.57 widened the lamp pass's end to 3 mm (``tbl.HELD_ARM_MOVED_UNITS``) and let the
UV pass start from there. Nothing puts its readings back afterwards:

* the UV pass is cut BY ITS PLAN (``scan.windows``: each patch's along-the-row place from
  ``plan.start``), and its scan move is absolute (``plan.m2``), so a start k mm off puts every
  reading k mm off along the row;
* the row placement check judges the lamp pass only (``dual_rows._placement``);
* the UV timing fit only REFUSES, and only when its R squared gain shows the shift. Measured on
  the simulator with a 4.5 mm opening (work folder, probes/probe_f3_uv_start_offset.py): starts
  0.5 to 1.5 mm off were "not judged" and their values used; 2 mm and more were refused.

So the UV start keeps 4.3.56's limit (``scan.UV_START_UNITS`` = ``scan.ARRIVAL_UNITS``, under
the 0.7 mm the project's own ``uv_pass_timing_off`` names): beyond it the UV pass fails cleanly
before its scan move, nothing more is sent, and the row keeps its lamp pass as M0 (4.3.50). No
line sent to the table changes; a refused UV pass sends fewer.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import test_dual_table as T
from workflow.i1io.table import job as J
from workflow.i1io.table import scan as sc
from workflow.i1io.table import session_table as tbl


def test_the_uv_start_limit_is_4356s_and_under_one_reading():
    assert sc.UV_START_UNITS == sc.ARRIVAL_UNITS == 5
    # one reading at the dual row's 132 mm/s, in table units (0.1 mm)
    assert sc.UV_START_UNITS < 132 * sc.READING_S * 10
    assert sc.UV_START_UNITS < tbl.HELD_ARM_MOVED_UNITS


def _lamp_end_off(tmp_path, monkeypatch, k):
    """A dual row whose lamp pass ends *k* units along X from its commanded end (the arm then
    stands there when the UV pass would start)."""
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    real = sim.lamp

    def lamp(t, dual_pass=None):
        real(t, dual_pass=dual_pass)
        if dual_pass == "lamp" and k:
            sim.pos = [sim.pos[0] + float(k), sim.pos[1]]
    monkeypatch.setattr(sim, "lamp", lamp)
    n0 = len(sim.received)
    res = T._until(job, job.read_row(), J.Confirm.ROW_FAILED_STRIP)
    return job, sim, res, sim.received[n0:]


@pytest.mark.parametrize("k", [0, 3, -3])
def test_a_lamp_end_within_half_a_millimetre_runs_the_uv_pass(tmp_path, monkeypatch, k):
    job, sim, res, lines = _lamp_end_off(tmp_path, monkeypatch, k)
    assert res.kind == J.Kind.OK, (res.kind, res.reason, res.detail)
    assert sum(1 for ln in lines if ln.startswith(";m2")) == 2      # lamp and UV pass
    assert ";d100d23a" in lines and sim.violations == []


@pytest.mark.parametrize("k", [8, 15, 30, -15, -30])
def test_a_uv_start_further_off_is_refused_before_anything_is_sent(tmp_path, monkeypatch, k):
    """0.8, 1.5 and 3 mm (either way along the row): before the fix the UV pass ran from there
    and its readings were cut as if it had started on plan. MUTATION: put the UV start limit
    back to tbl.HELD_ARM_MOVED_UNITS and the UV pass runs."""
    job, sim, res, lines = _lamp_end_off(tmp_path, monkeypatch, k)
    assert res.kind == J.Kind.NEEDS and res.confirm == J.Confirm.ROW_FAILED_STRIP, \
        (res.kind, res.reason)
    assert res.detail["why"] == "uv_pass_failed_clean", res.detail
    # the lamp pass's scan move only; no line of the UV pass (not even its zero-length m0)
    assert sum(1 for ln in lines if ln.startswith(";m2")) == 1
    assert ";d100d23a" not in lines
    assert not sim.m2_pending and sim.violations == []
    assert job._table.closed_reason is None                         # clean: it goes on
    # the row keeps its lamp pass as M0 (4.3.50), so nothing read is lost
    assert any("the lamp pass is kept as M0 only" in ln for ln in job.diag.lines)
