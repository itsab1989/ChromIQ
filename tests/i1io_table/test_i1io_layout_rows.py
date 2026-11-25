"""How far off a row may lie (the new chart layout, 25 Nov 2026), and the two notes about patch
sizes: 10 mm patches at 88 mm/s are read up to about 1.8 mm off and refused from 2.2; 8 mm ones
at 61 mm/s to about 1.0, mostly refused at 1.4 and always from 1.8. Nothing accepted is wrong. Nobody may widen the claim
without this failing. And a row whose patches are too short says so (not "too long")."""
from __future__ import annotations

import numpy as np
import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import placement_synth as S
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import ready_to_read
from tests.i1io_table.test_job_safety import shaped_sheet
from workflow.i1io.table import spot as sp

SEEDS = range(1, 7)


def _rows(tmp_path, patch, speed, dx, spacer=1.0):
    """(accepted, worst error of the accepted) of six synthetic rows *dx* mm off."""
    ok, worst = 0, 0.0
    for seed in SEEDS:
        p = S.plan(patch, speed, spacer)
        row = S.Row(p, dx_mm=dx, seed=seed, spacer_mm=spacer, lag=False)
        cut = S.write_and_cut(p, row, tmp_path / f"{patch}-{dx}-{seed}")
        if cut.ok:
            ok += 1
            worst = max(worst, float(np.max(S.errors(cut, row))))
    return ok, worst


@pytest.mark.parametrize("patch,speed,dx,want", [
    (10, 88, 0.0, "all"), (10, 88, 1.0, "all"), (10, 88, 2.2, "none"),
    (9.5, 88, 0.0, "all"), (9.5, 88, 2.2, "none"),
    (8.9, 61, 0.0, "all"), (8.9, 61, 1.8, "none"),
    (8, 61, 0.0, "all"), (8, 61, 0.5, "all"), (8, 61, 1.0, "most"),
    (8, 61, 1.4, "few"), (8, 61, 1.8, "none"), (8, 61, 2.2, "none")])
def test_how_far_off_a_row_may_lie(tmp_path, patch, speed, dx, want):
    ok, worst = _rows(tmp_path, patch, speed, dx)
    n = len(SEEDS)
    assert {"all": ok == n, "most": ok >= n / 2, "few": ok <= n / 2, "none": ok == 0}[want], (ok, worst)
    assert worst < 0.5


@pytest.mark.parametrize("patch", (8, 10))
def test_nothing_accepted_is_wrong(tmp_path, patch):
    """Whatever the shift up to 2.2 mm, what is accepted is the patch's own colour."""
    for dx in np.arange(0.0, 2.3, 0.4):
        _ok, worst = _rows(tmp_path, patch, 61 if patch == 8 else 88, float(dx))
        assert worst < 0.5, (dx, worst)


def _job(tmp_path, along):
    sheet = shaped_sheet([4, 4], along=along, across=8.0, w=210.0, h=297.0)
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=False)
    assert job.set_options(["-v", "-c", "1", "chart"]).ok
    p = H.Person(job, sim)
    ready_to_read(job, p)
    return job, sim, p


@pytest.mark.parametrize("along,why", [(5.5, "strip_row_patches_too_short"),
                                       (7.0, "strip_row_patches_too_short")])
def test_a_row_of_too_short_patches_says_so(tmp_path, along, why):
    job, sim, p = _job(tmp_path, along)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "spot"
    assert r.detail["read_patch_by_patch_because"] == why
    assert not any(ln.startswith(";m2") for ln in sim.received)


def test_8_mm_patches_are_read_as_strips_at_61(tmp_path):
    job, sim, p = _job(tmp_path, 8.0)
    plan = sp.plan_strip_row(job.sheet, 0, 0, job.alignment, job._table.front_y)
    assert plan.scan.speed == 61
    assert sp.strip_windows_ok(plan.scan) >= sp.STRIP_MIN_READINGS


# ---- the lengths the chart side says, against the reader's own planning ------

def _plans(job, along, kind):
    sheet = shaped_sheet([20, 20], along=along, across=8.0, w=210.0, h=297.0)
    f = sp.plan_dual_row if kind == "dual" else sp.plan_strip_row
    try:
        f(sheet, 0, 0, job.alignment, job._table.front_y)
        return True
    except sp.RowRefused as exc:
        return str(exc.args[0])


def test_the_lengths_a_chart_names_are_the_readers(tmp_path):
    """Copies in `table_facts` (chart code never imports the table package): from STRIP_FROM_MM a
    row is read in one movement, below it never; from DUAL_ROW_FROM_MM with both conditions, and
    not 0.4 mm below it."""
    from workflow.i1io import table_facts as F
    job, _sim, _p = _job(tmp_path, 8.0)
    a = F.STRIP_FROM_MM.value
    for k in range(0, 25):
        assert _plans(job, a + k / 10, "strip") is True, a + k / 10
    for k in range(1, 22):
        assert _plans(job, round(a - k / 10, 1), "strip") == "strip_row_patches_too_short"
    b = F.DUAL_ROW_FROM_MM.value
    for k in range(0, 10):
        assert _plans(job, b + k / 10, "dual") is True
    for k in range(4, 12):
        assert _plans(job, round(b - k / 10, 1), "dual") == "dual_row_patches_too_short"
    assert F.ROW_SPEED_FROM_MM.value == b


def test_the_window_and_the_tab_say_a_row_of_too_short_patches(qtbot):
    from types import SimpleNamespace

    from ui.i1io_table_window import reason_text
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M
    for why in ("strip_row_patches_too_short", "dual_row_patches_too_short"):
        logged = []
        fake = SimpleNamespace(_log=SimpleNamespace(appendPlainText=logged.append))
        TabMeasure._on_table_progress(fake, {"event": "strip_fallback", "why": why, "row": 3})
        assert logged == [M.strip_fallback_text(why, 3)]
        said = reason_text(why)
        assert "too short" in said and why not in said
