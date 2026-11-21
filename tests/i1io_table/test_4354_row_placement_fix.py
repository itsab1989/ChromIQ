"""4.3.54 fix round of the row placement check (independent review, work folder
2026-11-21_place454_review/review_place454.txt).

| the review                                                              | here                     |
|-------------------------------------------------------------------------|--------------------------|
| M1: the dual row's veto had no behavioural test (dual_rows._placement    | test_the_dual_cut_*      |
|     ignored: every focused test green)                                   |                          |
| M1: the job keeps no M0-only lamp pass after a placement refusal         | test_a_dual_row_refused_* |
| S2: six guards no test protected (each now refuses a row on its own:    | test_guard_*             |
|     the value condition, the timing bound, uniqueness, the run           |                          |
|     tolerance, 3 clean readings, every centre on a stable reading)       |                          |

Every test here was RED with its guard planted out (work folder fix_round/plants_out.txt).
Rows: tests/i1io_table/placement_synth.py (shaped like the recorded ones; the recordings stay
private). The guard tests give the check windows on each patch's TRUE clean middle, so that the
window rule cannot be what refuses; three of them (uniqueness, the timing bound, every centre on
a stable reading) make the fit's own result say what a real row would (a rival place, the best
place on the bound, a patch centre off the stable readings): those rules are backstops of each
other on real rows (the review's guards.py: removing any one alone accepted no wrong patch), so
a row refused by ONE of them alone is not something the generator produces on its own.
"""
from __future__ import annotations

import numpy as np
import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import placement_synth as S
from workflow.i1io.table import dual_rows as dl
from workflow.i1io.table import job as J
from workflow.i1io.table import placement as pl
from workflow.i1io.table import spot as sp
from workflow.i1io.table import strip as stp


def _mid3(row, i):
    c = row.clean[i]
    m = len(c) // 2
    return (int(c[m - 1]), int(c[m + 2]))


def _true_windows(row, p):
    return [_mid3(row, i) for i in range(len(p.patches))]


# ---- M1: the dual row ------------------------------------------------------------------------------

def test_the_dual_cut_refuses_a_lamp_pass_whose_window_takes_in_an_edge_reading(monkeypatch):
    """The lamp pass of a dual row at 132 mm/s, the sheet 2 mm off: the dual row's own checks
    (1.5 mm edge, one colour) accept it with a patch more than 3 dE00 off; the check refuses
    the dual cut AND the M0-only cut of the same pass, with the strip row's reason."""
    lamp = S.plan(10.0, 132)
    uv = sp.uv_pass_of(lamp)
    urows = [[0.01] * 36] * uv.N
    row = S.Row(lamp, dx_mm=2.0, seed=0)
    rows = row.readings.tolist()
    monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", False)
    off = dl.cut_dual(lamp, uv, rows, urows)
    assert off.ok
    got = np.array(off.lamp)
    assert float(np.max(S.de00_spectra(got, row.truth))) > 3.0
    assert dl.cut_lamp_only(lamp, rows).ok
    monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", True)
    on = dl.cut_dual(lamp, uv, rows, urows)
    assert (on.ok, on.reason) == (False, stp.PLACEMENT_REASON)
    assert on.info["placement"]["confirmed"] is False and on.info["loc"]
    only = dl.cut_lamp_only(lamp, rows)
    assert (only.ok, only.reason) == (False, stp.PLACEMENT_REASON)
    # and a dual row lying where it should is cut as before
    good = S.Row(lamp, seed=0).readings.tolist()
    a = dl.cut_dual(lamp, uv, good, urows)
    monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", False)
    b = dl.cut_dual(lamp, uv, good, urows)
    assert a.ok and b.ok and a.lamp == b.lamp and a.uv == b.uv


def test_a_dual_row_refused_for_placement_keeps_no_m0_only_lamp_pass(tmp_path, monkeypatch):
    """The job (simulated table, dual scan on): row 1's sheet 2.5 mm off, read through the
    4.5 mm opening. The row fails with the placement reason, and the job does NOT try to keep
    its lamp pass as M0 only (job.py's exclusion beside lamp_pass_timing_off): the question
    says nothing of M0, and no M0-only row file exists."""
    from tests.i1io_table.test_4350_dual_m1_m2_per_row import _job, _ready
    kept = []
    real = J.TableJob._keep_lamp_pass

    def spy(self, *a, **k):
        kept.append(a[-1])
        return real(self, *a, **k)
    monkeypatch.setattr(J.TableJob, "_keep_lamp_pass", spy)
    job, sim, helper, run, p, _rep = _job(
        tmp_path, faults={"scan": {"sheet_offset_mm": 2.5, "aperture_mm": 4.5}, "scan_at": 2},
        script={J.Confirm.ROW_FAILED_STRIP: "skip"})
    asked = []
    p.on_ask = lambda person, res: (asked.append(dict(res.detail))
                                    if res.confirm == J.Confirm.ROW_FAILED_STRIP else None)
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "skipped"
    assert [a["why"] for a in asked] == [stp.PLACEMENT_REASON]
    assert asked[0]["m0_kept"] is False and asked[0]["read"] == 0
    assert kept == []
    assert not list(job.diag.folder.rglob("*.strip.ti3"))
    job.close()


# ---- S2: each guard refuses a row on its own --------------------------------------------------------

def test_guard_the_value_condition():
    """A dark patch whose readings drift by up to 1.1 dE00 across it (within the dark run limit of
    1.2): its window lies inside its stable run, but on one end of it; the window's value is
    0.64 dE00 from the run's own. Refused by the value condition alone."""
    p = S.plan(10.0, 61)
    cols = S.PALETTE[np.arange(24) % len(S.PALETTE)].copy()
    cols[5] = np.full(36, 0.03)
    row = S.Row(p, seed=3, colours=cols, print_sd=0.0)
    c = row.clean[5]
    row.readings[c] *= (1 + 0.1 * np.linspace(-1, 1, len(c)))[:, None]
    w = _true_windows(row, p)
    w[5] = (int(c[1]), int(c[4]))
    r = pl.check_row(p, row.readings.tolist(), w)
    assert (r["reason"], r["patch"]) == ("value_disagrees_with_the_stable_run", "A6"), r
    assert r["value_de00"] > pl.VALUE_AGREE_DE00
    w[5] = _mid3(row, 5)                             # its middle: confirmed
    assert pl.check_row(p, row.readings.tolist(), w)["confirmed"]


def test_guard_the_run_tolerance():
    """One patch printed 3 mm further along than the others (3 mm spacers, so it overlaps
    nothing): the row fits the other 23; that patch's run lies 2.4 mm from its place. Its
    window (on its true middle) lies inside its run, with 10 clean readings: refused by the
    2 mm run tolerance alone."""
    p = S.plan(10.0, 61, spacer_mm=4.0)
    row = S.Row(p, seed=5, patch_shift={7: 3.0}, print_sd=0.0, spacer_mm=4.0)
    r = pl.check_row(p, row.readings.tolist(), _true_windows(row, p))
    assert (r["reason"], r["patch"]) == ("patch_run_away_from_its_place", "A8"), r
    assert r["off_mm"] > pl.PATCH_TOL_MM
    rec = [x for x in r["per_patch"] if x["loc"] == "A8"][0]
    assert rec["clean"] >= pl.MIN_READINGS and not rec["merged"]


def test_guard_three_clean_readings():
    """A plan whose patch A7 is only 5 mm long (half 2.5 mm) while the print is 10 mm: its run
    is long and its window inside it, but the readings within +-(half - 2.25 mm) of its centre
    are fewer than 3: refused by the clean-readings rule alone."""
    p = S.plan(10.0, 88)
    p.patches[6].half_mm = 2.5
    row = S.Row(p, seed=6, print_sd=0.0)
    r = pl.check_row(p, row.readings.tolist(), _true_windows(row, p))
    assert (r["reason"], r["patch"]) == ("patch_too_few_clean_readings", "A7"), r


def _good():
    p = S.plan(10.0, 88)
    row = S.Row(p, seed=6, print_sd=0.0)
    w = _true_windows(row, p)
    assert pl.check_row(p, row.readings.tolist(), w)["confirmed"]
    return p, row, w


def _fit_says(monkeypatch, change):
    real = pl._fit

    def fit(plan, n, depth, first_s, motion_s):
        D, E, Hh, deep, b = real(plan, n, depth, first_s, motion_s)
        return change(plan, D.copy(), E.copy(), Hh.copy(), deep.copy(), b)
    monkeypatch.setattr(pl, "_fit", fit)


def test_guard_every_centre_on_a_stable_reading(monkeypatch):
    """The fit finds one patch centre off the stable readings at its best place: not confirmed
    ("the readings do not show every patch where the timing puts it")."""
    p, row, w = _good()

    def change(plan, D, E, Hh, deep, b):
        Hh[0] = len(plan.patches) - 1
        return D, E, Hh, deep, b
    _fit_says(monkeypatch, change)
    r = pl.check_row(p, row.readings.tolist(), w)
    assert r["reason"] == "edges_do_not_place_every_patch" and r["off_patches"] == 1
    assert "1 patch" in pl.summary(r)


def test_guard_uniqueness(monkeypatch):
    """A place half a pitch away fits as well as the best one: not confirmed."""
    p, row, w = _good()

    def change(plan, D, E, Hh, deep, b):
        k = 1
        D[k] = D[0] + 0.6 * 11.0 / plan.speed            # 6.6 mm away (half a pitch: 5.5)
        Hh[k] = Hh[0]
        return D, E, Hh, deep, b
    _fit_says(monkeypatch, change)
    r = pl.check_row(p, row.readings.tolist(), w)
    assert r["reason"] == "edges_not_unique", r


@pytest.mark.parametrize("which", ["dt", "scale"])
def test_guard_the_timing_bound(monkeypatch, which):
    """The best place lies on the timing's own bound (the readings and the timing disagree):
    not confirmed, with the largest shift a patch would make, in mm."""
    p, row, w = _good()

    def change(plan, D, E, Hh, deep, b):
        if which == "dt":
            D[0] = b
        else:
            E[0] = pl.FIT_SCALE
        Hh[1:] = 0                     # no rival place: uniqueness is not what refuses it
        return D, E, Hh, deep, b
    _fit_says(monkeypatch, change)
    r = pl.check_row(p, row.readings.tolist(), w)
    assert r["reason"] == "edges_disagree_with_timing" and r["off_mm"] > 0, r
