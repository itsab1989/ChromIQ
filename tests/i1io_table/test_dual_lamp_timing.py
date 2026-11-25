"""SHOULD-A of the 4.3.48 re-review: the lamp pass of a DUAL row gets a timing judgement too.

In the reviewer's stress run a lamp pass 2 readings late gave M0 off by up to 2.65 dE00, 3
readings 10 dE00, and the lamp's uniformity check refused only 2 of 12; the fit was computed
and only logged. ``dual_rows.uv_timing_fit`` now judges the lamp pass's best start as well:
refused at 1.75 readings or more late (a pass truly 2 late fits at 1.75 or 2.0), or 2.5 or
more early (the five recorded lamp passes, driven
by the vendor's software, fit 0.25 to 2.25 readings early and read well), with the UV pass's
gain gate. Tuned on the volunteer's recorded rows (private): every recorded pass accepted; every
accepted shift kept M0 within 0.44 dE00 of the vendor's; every shift that cost 0.6 dE00 or more
refused. The released single-scan strip rows are NOT judged (unchanged)."""
from __future__ import annotations

import json
import random

import pytest

from tests.i1io_table import test_dual_table as T
from tests.i1io_table.test_dual_uv_timing import _plan, _sheet, _stream
from workflow.i1io.table import dual_rows as dl
from workflow.i1io.table import job as J
from workflow.i1io.table import scan as sc


def _passes(k_lamp_late=0.0, flat=False, seed=3):
    lamp, uv = _plan()
    rng = random.Random(seed)
    levels = [0.5] * 25 if flat else [0.08 + 0.8 * rng.random() for _ in range(25)]
    at = _sheet(lamp, levels)
    lr = _stream(lamp, sc.FIRST_READING_AFTER_LAMP_S,
                 sc.DUAL_LAMP_MOTION_START_S + k_lamp_late * sc.READING_S, lamp.N, at, False,
                 rng)
    ur = _stream(uv, sc.UV_FIRST_READING_AFTER_TRIGGER_S, sc.UV_MOTION_START_AFTER_TRIGGER_S,
                 uv.N, at, True, rng)
    return lamp, uv, lr, ur


@pytest.mark.parametrize("k", [0.0, 1.0, -1.0, -2.0])
def test_a_lamp_pass_near_its_assumed_start_is_accepted(k):
    lamp, uv, lr, ur = _passes(k)
    f = dl.uv_timing_fit(lamp, uv, lr, ur)
    assert f["lamp_checked"] is True and f["lamp_refuse"] is False, f
    assert f["refuse"] is False                      # the UV pass is on time
    assert abs(f["lamp"]["best_readings"] - k) <= 0.5, f
    json.dumps(f)


@pytest.mark.parametrize("k", [2.0, 3.0, 4.0, 6.0, -3.0, -4.0, -6.0])
def test_a_lamp_pass_off_is_refused(k):
    lamp, uv, lr, ur = _passes(k)
    f = dl.uv_timing_fit(lamp, uv, lr, ur)
    assert f["lamp_refuse"] is True, f
    assert f["refuse"] is False, f                   # the UV pass on its own stays accepted
    assert abs(f["lamp"]["best_readings"] - k) <= 0.5, f


@pytest.mark.parametrize("best,gain,refuse,checked", [
    (1.5, 0.05, False, True), (1.75, 0.0050, True, True), (1.75, 0.0049, False, False),
    (-2.25, 0.05, False, True), (-2.5, 0.0050, True, True), (-2.5, 0.0049, False, False),
    (0.0, 0.0, False, True),
])
def test_the_lamp_decision_is_pinned(monkeypatch, best, gain, refuse, checked):
    """Refused at 1.75 readings late or 2.5 early WITH an R squared gain of 0.005; inside,
    accepted; outside with a smaller gain not judged (never refused)."""
    lamp, uv, lr, ur = _passes(0.0)

    def fit(plan, signal, first_s, start_s):
        if plan is lamp:
            return {"best_readings": best, "best_motion_start_s": start_s,
                    "r2_best": 0.9 + gain, "r2_assumed": 0.9, "spread": 0.5}
        return {"best_readings": 0.0, "best_motion_start_s": start_s, "r2_best": 0.9,
                "r2_assumed": 0.9, "spread": 0.5}
    monkeypatch.setattr(dl, "_layout_fit", fit)
    f = dl.uv_timing_fit(lamp, uv, lr, ur)
    assert (f["lamp_refuse"], f["lamp_checked"]) == (refuse, checked), f


def test_a_lamp_row_of_one_colour_is_not_judged():
    lamp, uv, lr, ur = _passes(4.0, flat=True)
    f = dl.uv_timing_fit(lamp, uv, lr, ur)
    assert f["lamp_checked"] is False and f["lamp_refuse"] is False
    assert "hardly differ" in f["lamp_why"]


def test_the_lamp_is_judged_even_when_the_uv_pass_cannot_be():
    """The UV pass's early returns (too few readings, a flat row at 380-400 nm) never skip the
    lamp's verdict."""
    lamp, uv, lr, ur = _passes(4.0)
    flat_uv = [[0.1] * 36 for _ in ur]
    f = dl.uv_timing_fit(lamp, uv, lr, flat_uv)
    assert f["checked"] is False and f["lamp_refuse"] is True, f


def _row_record(job, name="p1_row1"):
    folder = next(iter(job.diag.folder.glob("row-*")))
    return json.loads((folder / f"{name}.row.json").read_text(encoding="utf-8"))


def test_a_dual_row_whose_lamp_pass_is_off_fails_and_is_offered_again(tmp_path, monkeypatch):
    real = dl.uv_timing_fit

    def off(*a, **k):
        f = real(*a, **k)
        return dict(f, lamp_checked=True, lamp_refuse=True)
    monkeypatch.setattr(dl, "uv_timing_fit", off)
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    res = T._until(job, job.read_row(), J.Confirm.ROW_FAILED_STRIP)
    assert res.detail["why"] == "lamp_pass_timing_off"
    # offered again: as a row, patch by patch, skipped or the step ended
    assert {"again", "patch by patch"} <= set(res.choices), res.choices
    rec = _row_record(job)
    assert rec["status"] == "failed" and rec["uv_timing"]["lamp_refuse"] is True
    folder = next(iter(job.diag.folder.glob("row-*")))
    assert not (folder / "p1_row1.dual_in.txt").exists()
    log = (job.diag.folder / "session.log").read_text(encoding="utf-8")
    assert "lamp judged True, refused True" in log


def test_a_dual_row_on_time_records_the_lamp_verdict(tmp_path):
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok, (r.reason, r.detail)
    t = _row_record(job)["uv_timing"]
    assert t["lamp_refuse"] is False and "lamp_checked" in t
    assert t["lamp_refuse_at_readings"] == {"late": 1.75, "early": 2.5}


def test_a_single_scan_strip_row_is_not_judged(tmp_path, monkeypatch):
    """The released strip rows keep their behaviour: the fit is never asked."""
    def never(*a, **k):
        raise AssertionError("a single-scan strip row was judged")
    monkeypatch.setattr(dl, "uv_timing_fit", never)
    job, sim, helper, run, p = T._job(tmp_path, dual=None)
    T._ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail.get("row_kind") == "strip", (r.reason, r.detail)


def test_the_lamp_reason_has_its_own_sentence():
    from ui import i1io_table_window as W
    t = W.reason_text("lamp_pass_timing_off")
    assert "first pass, with the lamp" in t and "1.2 mm" in t and "—" not in t
