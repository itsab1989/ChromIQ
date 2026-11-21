# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.53 fix round 2 (the re-review's MUST-A1): the strip row's clean border at each patch edge
grows with the speed, ONE rule for planning and cutting (scan.strip_edge_mm).

Until this fix the border was 0.5 mm whatever the speed. The motion start the cut assumes
(lamp + 0.372 s) is off by up to 16 ms on the table testers use (the 18 Nov dual rows: 1.25 to
3.25 readings; the 17 Nov 168 mm/s rows: about 13 ms early on one of the two, by the plateau
centre of a narrow cut, fix2/motion_start_fit_out.txt in the work folder). At 168 mm/s 16 ms is
2.7 mm: a 0.5 mm border lets the window run into the next spacer, and the re-review re-cut
i1Profiler's own 17 Nov rows with a patch 6.54 dE00 wrong that every check accepted.

These tests feed the cut READINGS SHAPED LIKE A REAL PASS (synthetic: the recording is private):
the arm's own move profile (scan.time_at), the 4.5 mm aperture averaged over each 5.004 ms
reading, ChromIQ's own row geometry (patch + 1 mm spacer, the spacer a contrasting colour, as
ChromIQ prints them), and a motion start shifted by the measured spread, early and late. They
assert what a person needs: the row is refused, or EVERY patch value is its patch's colour within
DE_TOL. Red before the fix (the reproduction of the 6.54 dE00 case: 168 mm/s, a 10 mm patch,
the motion 9 ms early)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from workflow.dual_scan.colour import de00_spectra
from workflow.i1io.table import scan as sc
from workflow.i1io.table import spot as sp
from workflow.i1io.table import strip as stp

#: the stated tolerance for a patch cut from a clean (uncontaminated) window
DE_TOL = 0.5
WL = list(range(380, 731, 10))


def _spec(level, tilt=0.0, bump=None):
    out = []
    for i, _w in enumerate(WL):
        v = level + tilt * (i - 17) / 17
        if bump is not None:
            c, h = bump
            v += h * math.exp(-((i - c) / 4.0) ** 2)
        out.append(min(0.95, max(0.02, v)))
    return out


#: patch colours (light, dark, saturated) and the spacer: a contrasting colour, as on ChromIQ's
#: charts, so a window that runs into a spacer shows as a wrong value
PATCHES = [_spec(0.85), _spec(0.05), _spec(0.30, 0.25), _spec(0.20, -0.15, (10, 0.5)),
           _spec(0.60, 0.0, (25, -0.4)), _spec(0.10, 0.05)]
SPACER = _spec(0.45, -0.3, (5, 0.4))


def _row(patch_mm: float, spacer_mm: float, speed: int, n: int = 18, run_mm: float = 15.0):
    pitch = patch_mm + spacer_mm
    length = 2 * run_mm + pitch * (n - 1)
    pts = [sc.Patch(str(i + 1), f"A{i + 1}", ((run_mm + i * pitch) * 10.0, 0.0),
                    half_mm=patch_mm / 2) for i in range(n)]
    return sc.plan_row("r", (0, 0), (int(round(length * 10)), 0), speed, pts)


def _colour_at(plan, x_mm, patch_mm):
    for k, q in enumerate(plan.patches):
        if abs(x_mm - q.along_mm) <= patch_mm / 2:
            return PATCHES[k % len(PATCHES)]
    return SPACER


def _position(plan, t):
    """Where the opening is t s after the motion start (the inverse of scan.time_at)."""
    if t <= 0:
        return 0.0
    lo, hi = 0.0, plan.dist / 10.0
    if t >= sc.time_at(plan, hi):
        return hi
    for _ in range(50):
        mid = (lo + hi) / 2
        if sc.time_at(plan, mid) < t:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def stream(plan, patch_mm, shift_s=0.0):
    """The readings of one pass whose motion starts *shift_s* after ChromIQ's assumed start
    (negative: early). Each reading: the aperture (4.5 mm) averaged over its 5.004 ms."""
    start = sc.MOTION_START_AFTER_LAMP_S + shift_s
    rows = []
    for i in range(plan.N):
        acc = np.zeros(len(WL))
        k = 0
        for sub in range(5):
            t = sc.FIRST_READING_AFTER_LAMP_S + (i + (sub + 0.5) / 5) * sc.READING_S - start
            x = _position(plan, t)
            for a in np.linspace(-plan.aperture_mm / 2, plan.aperture_mm / 2, 9):
                acc += np.asarray(_colour_at(plan, x + a, patch_mm))
                k += 1
        rows.append(list(acc / k))
    return rows


def _cut(plan, rows, tmp_path):
    (tmp_path / "out").mkdir(exist_ok=True)
    p = tmp_path / "out" / (plan.name + ".spec.csv")
    p.write_text("i," + ",".join(str(w) for w in WL) + "\n" + "\n".join(
        f"{i}," + ",".join(f"{v:.6f}" for v in r) for i, r in enumerate(rows)) + "\n",
        encoding="utf-8")
    return stp.cut_row(plan, str(tmp_path / "out"), {"ok": True, "got": len(rows)})


def _errors(plan, cut):
    got = [c[2] for c in cut.patches]
    want = [PATCHES[k % len(PATCHES)] for k in range(len(plan.patches))]
    return de00_spectra(np.array(got), np.array(want))


# ---- the one rule ----------------------------------------------------------------------------

def test_the_border_grows_with_the_speed_and_planning_and_cutting_use_the_same_one():
    assert sc.MOTION_START_SPREAD_S == 0.018
    for v in geo_speeds():
        assert sc.strip_edge_mm(v) == pytest.approx(max(0.5, v * 0.018))
    assert sc.strip_edge_mm(168) == pytest.approx(3.024)
    plan = _row(12.0, 1.0, 138)
    w_plan = sc.windows(plan, sc.MOTION_START_AFTER_LAMP_S, plan.N,
                        edge_mm=sc.strip_edge_mm(plan.speed))
    assert sp.strip_windows_ok(plan) == min(b - a for a, b in w_plan)
    rows = stream(plan, 12.0)
    _vals, info = sc.cut_by_position(plan, rows)
    assert info["windows"] == w_plan and info["edge_mm"] == pytest.approx(sc.strip_edge_mm(138))


def geo_speeds():
    return sp.STRIP_SPEEDS


def test_with_the_old_border_the_cut_code_is_unchanged():
    """The cut itself is 4.3.52's: given the 0.5 mm border it gives the same windows and values
    as before (windows() with its default edge)."""
    plan = _row(10.0, 1.0, 54)
    rows = stream(plan, 10.0)
    vals, info = sc.cut_by_position(plan, rows, edge_mm=0.5)
    w = sc.windows(plan, sc.MOTION_START_AFTER_LAMP_S, len(rows))
    assert info["windows"] == w
    assert vals == [sc._mean(rows[a:b]) for a, b in w]


# ---- what the planner now picks (the vendor's recorded speeds only) --------------------------

@pytest.mark.parametrize("patch_mm, want", [(8.0, 61), (8.9, 61), (9.5, 88), (10.0, 88),
                                            (10.5, 88), (11.0, 110), (12.0, 137), (13.0, 138)])
def test_each_patch_length_gets_the_fastest_recorded_speed_its_border_allows(patch_mm, want):
    plan = _row(patch_mm, 1.0, 54)
    sheet_pitch = patch_mm + 1.0
    got = None
    for v in sp.speeds_to_try(sheet_pitch):
        p = _row(patch_mm, 1.0, v)
        f = sp.strip_windows_ok(p)
        if f is not None and f >= sp.STRIP_MIN_READINGS and p.N <= sp.STRIP_N_MAX:
            got = v
            break
    assert got == want, (patch_mm, got)
    assert plan is not None and got in sp.STRIP_SPEEDS


# ---- the values: early and late motion, every recorded speed, ChromIQ's patch lengths ---------

@pytest.mark.parametrize("shift_ms", [-18, -9, 0, 9, 18])
@pytest.mark.parametrize("patch_mm", [8.0, 10.0, 12.0])
@pytest.mark.parametrize("speed", sorted(set(sp.STRIP_SPEEDS)))
def test_a_cut_patch_is_its_colour_or_the_row_is_refused(tmp_path, speed, patch_mm, shift_ms):
    """Every recorded strip speed, ChromIQ's patch lengths, the motion start off by the measured
    spread (and by half of it), both ways: refused (too few clean readings, a window not on one
    colour) or every patch within DE_TOL of its true colour. At a speed the planner would not
    pick for that patch length the cut must refuse, never deliver a wrong value."""
    plan = _row(patch_mm, 1.0, speed)
    cut = _cut(plan, stream(plan, patch_mm, shift_ms / 1000.0), tmp_path)
    if not cut.ok:
        return
    d = _errors(plan, cut)
    assert d.max() <= DE_TOL, (speed, patch_mm, shift_ms, float(d.max()))


def test_the_re_review_case_168_mm_s_10_mm_patch_motion_9_ms_early(tmp_path):
    """The 6.54 dE00 case of the re-review, synthetic: 168 mm/s, ChromIQ's 10 mm patch and 1 mm
    spacer, the motion 9 ms early. Before the fix the cut ACCEPTED it with a patch far off
    (red); now the 3.0 mm border leaves no clean reading at 168 for a 10 mm patch: refused,
    and the planner reads such a row at 88 mm/s instead."""
    plan = _row(10.0, 1.0, 168)
    cut = _cut(plan, stream(plan, 10.0, -0.009), tmp_path)
    if cut.ok:
        assert _errors(plan, cut).max() <= DE_TOL
    assert not cut.ok and cut.reason in ("strip_patch_too_few_readings",
                                         "strip_patches_outside_the_readings")


def test_a_contaminated_window_is_caught(tmp_path):
    """Forced: the cut told the old 0.5 mm border at 168 mm/s and the motion 18 ms late: the
    windows run into the spacers; the row must be refused by the uniformity check, never
    accepted with a wrong patch."""
    plan = _row(10.0, 1.0, 168)
    rows = stream(plan, 10.0, 0.018)
    vals, info = sc.cut_by_position(plan, rows, edge_mm=0.5)
    want = [PATCHES[k % len(PATCHES)] for k in range(len(plan.patches))]
    d = de00_spectra(np.array(vals), np.array(want))
    contaminated = [k for k in range(len(d)) if d[k] > DE_TOL]
    assert contaminated, "the plant must contaminate at least one window"
    assert max(info["uniformity"][k] for k in contaminated) > sp.STRIP_UNIFORMITY_MAX
