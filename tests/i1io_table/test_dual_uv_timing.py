"""SHOULD-2 of the table safety review (2026-11-19): the UV pass's timing against the chart.

A UV pass whose motion started 2 to 4 readings away from the assumed start passed the pairing
check (the shift stays inside the clean edge, the per-patch means hardly move) and gave M2 off
by up to 2.7 dE00. ``dual_rows.uv_timing_fit`` lays the UV pass's 380-400 nm readings over the
chart's own patches for every start within +-6 readings and refuses a pass whose best start is
1 reading or more away (when the fit is sure: R squared gains at least 0.005). Tuned on the
volunteer's recorded rows (private): every recorded pass within 0.5 readings, every pass shifted
by 2 or more refused. Here: invented streams laid out by the plan's own motion model, with the
aperture's blur, and the job's wiring.
"""
from __future__ import annotations

import json
import math
import random

import pytest

from tests.i1io_table import test_dual_table as T
from workflow.i1io.table import dual_rows as dl
from workflow.i1io.table import job as J
from workflow.i1io.table import scan as sc
from workflow.i1io.table import spot as sp


def _plan(n=24, pitch_mm=10.6):
    start, end = (-1300, 1700), (-1300 + int(round((n + 1) * pitch_mm * 10)), 1700)
    pts = [sc.Patch(str(k), f"A{k + 1}", (start[0] + int(round((k + 1) * pitch_mm * 10)), 1700),
                    half_mm=pitch_mm / 2) for k in range(n)]
    lamp = sc.plan_row("r", start, end, sc.DUAL_SPEED, pts, dual=True)
    return lamp, sp.uv_pass_of(lamp)


def _sheet(lamp, levels):
    """Reflectance at a place along the lamp pass (mm), seen through the 4.5 mm aperture: each
    patch's level, the edges blurred over the aperture."""
    def at(x):
        w = lamp.aperture_mm
        acc, n = 0.0, 9
        for i in range(n):
            xx = x - w / 2 + w * (i + 0.5) / n
            v = levels[-1]
            for q, lv in zip(lamp.patches, levels):
                if abs(xx - q.along_mm) <= q.half_mm:
                    v = lv
                    break
            acc += v
        return acc / n
    return at


def _stream(plan, first_s, start_s, n, at, uv, rng):
    rows = []
    L = plan.dist / 10.0
    for j in range(n):
        t = first_s + j * sc.READING_S - start_s
        x = dl._position_at(plan, t)
        if uv:
            x = L - x                         # back along the row: lamp coordinates
        v = at(x)
        led = (0.25 * v if uv else v) * (1.0 + rng.gauss(0, 0.002))
        rows.append([led] * 3 + [v] * 33)
    return rows


def _passes(k_late=0.0, flat=False, seed=1):
    lamp, uv = _plan()
    rng = random.Random(seed)
    levels = [0.5] * 25 if flat else [0.08 + 0.8 * rng.random() for _ in range(25)]
    at = _sheet(lamp, levels)
    lr = _stream(lamp, sc.FIRST_READING_AFTER_LAMP_S, sc.MOTION_START_AFTER_LAMP_S, lamp.N,
                 at, False, rng)
    ur = _stream(uv, sc.UV_FIRST_READING_AFTER_TRIGGER_S,
                 sc.UV_MOTION_START_AFTER_TRIGGER_S + k_late * sc.READING_S, uv.N, at, True, rng)
    return lamp, uv, lr, ur


def test_a_uv_pass_on_time_is_accepted_and_its_start_is_recorded():
    lamp, uv, lr, ur = _passes(0.0)
    f = dl.uv_timing_fit(lamp, uv, lr, ur)
    assert f["checked"] is True and f["refuse"] is False, f
    assert abs(f["uv"]["best_readings"]) < 0.5
    assert abs(f["uv"]["best_motion_start_s"] - sc.UV_MOTION_START_AFTER_TRIGGER_S) < 0.003
    assert abs(f["lamp"]["best_readings"]) < 0.5
    json.dumps(f)                              # it goes into the row's record as it is


@pytest.mark.parametrize("k", [-4, -3, -2, 2, 3, 4, 6])
def test_a_uv_pass_two_or_more_readings_off_is_refused(k):
    lamp, uv, lr, ur = _passes(float(k))
    f = dl.uv_timing_fit(lamp, uv, lr, ur)
    assert f["refuse"] is True, f
    # the fit finds the start the pass really had (the value a real run reports)
    assert abs(f["uv"]["best_readings"] - k) <= 0.5, f


def test_a_row_of_one_colour_is_not_judged_and_not_refused():
    lamp, uv, lr, ur = _passes(3.0, flat=True)
    f = dl.uv_timing_fit(lamp, uv, lr, ur)
    assert f["checked"] is False and f["refuse"] is False
    assert "hardly differ" in f["why"]


def test_the_motion_model_inverts_time_at():
    lamp, _uv = _plan()
    for mm in (0.0, 0.3, 5.0, 100.0, lamp.dist / 10.0 - 0.2, lamp.dist / 10.0):
        t = sc.time_at(lamp, mm)
        assert math.isclose(dl._position_at(lamp, t), mm, abs_tol=1e-6)


# ---- the job ---------------------------------------------------------------------------------

def _row_record(job, name="p1_row1"):
    folder = next(iter(job.diag.folder.glob("row-*")))
    return json.loads((folder / f"{name}.row.json").read_text(encoding="utf-8"))


def test_the_job_records_both_best_starts_of_every_dual_row(tmp_path):
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "strip", (r.reason, r.detail)
    rec = _row_record(job)
    t = rec["uv_timing"]
    assert set(t) >= {"checked", "refuse", "uv", "lamp", "assumed_uv_motion_start_s"}
    assert t["refuse"] is False
    cut = json.loads(next(iter(job.diag.folder.glob("row-*/p1_row1.dual_cut.json")))
                     .read_text(encoding="utf-8"))
    assert cut["info"]["uv_timing"] == t
    log = (job.diag.folder / "session.log").read_text(encoding="utf-8")
    assert "best-fitting motion starts: UV" in log


def test_a_uv_pass_whose_timing_is_off_fails_the_row_and_offers_it_again(tmp_path, monkeypatch):
    real = dl.uv_timing_fit

    def off(*a, **k):
        f = real(*a, **k)
        return dict(f, checked=True, refuse=True)
    monkeypatch.setattr(dl, "uv_timing_fit", off)
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    res = T._until(job, job.read_row(), J.Confirm.ROW_FAILED_STRIP)
    assert res.detail["why"] == "uv_pass_timing_off"
    rec = _row_record(job)
    assert rec["status"] == "failed" and rec["uv_timing"]["refuse"] is True
    # nothing of it went to the helper's M1 / M2
    folder = next(iter(job.diag.folder.glob("row-*")))
    assert not (folder / "p1_row1.dual_in.txt").exists()
