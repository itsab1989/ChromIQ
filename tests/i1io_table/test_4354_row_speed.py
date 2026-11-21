# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.54: "Row speed", the person's factor on the speed of an i1iO table row read as a strip.

The owner (2026-11-21): "could you also make an option in the beta section that allows to
increase or decrease the speed within a certain frame by a factor? that way the user could
figure out best speed himself."

Pinned here: 1.00 is 4.3.53 exactly (the same plan, line and cut); the speed is ChromIQ's own
times the factor, kept inside the frame of the row speeds i1Profiler was recorded using (40 to
168 mm/s), never the dual row's 132; the speed sent is the speed planned; a row faster than the
border rule allows is cut with the border shrunk just enough and the logs say so; slower rows
keep the rule's border (never below 0.5 mm); and, documented as a number for the safety brief,
how wrong a 10 mm patch can come out at factor 2.00 when the motion start is off by the measured
spread (synthetic passes as in test_4353_fix2_cut_at_speed)."""
from __future__ import annotations

import pytest

from tests.i1io_table import test_4353_fix2_cut_at_speed as T
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import lines as cl
from workflow.i1io.table import scan as sc
from workflow.i1io.table import spot as sp


def _base_speed(patch_mm):
    for v in sp.speeds_to_try(patch_mm + 1.0):
        p = T._row(patch_mm, 1.0, v)
        f = sp.strip_windows_ok(p)
        if f is not None and f >= sp.STRIP_MIN_READINGS and p.N <= sp.STRIP_N_MAX:
            return v
    return None


def _factored(patch_mm, factor, n=18):
    """What apply_speed_factor does to ChromIQ's own plan of a synthetic row (the same steps,
    on the synthetic row instead of a sheet)."""
    base = _base_speed(patch_mm)
    plan = T._row(patch_mm, 1.0, base, n=n)

    def one(_sheet, _page, _index, _al, v, _fy, cap_y=None):
        return T._row(patch_mm, 1.0, v, n=n)
    orig, orig_check = sp._one_strip, sc.check_plan
    sp._one_strip = one
    sc.check_plan = lambda *a, **k: None      # the synthetic row lies outside the table's area
    try:
        return base, sp.apply_speed_factor(plan, factor, None, 0, 0, None, None, None)
    finally:
        sp._one_strip, sc.check_plan = orig, orig_check


# ---- the frame ---------------------------------------------------------------------------------

def test_the_frame_is_the_recorded_row_speeds():
    assert geo.ROW_SPEED_FRAME == (min(geo.RECORDED_M2_SPEEDS), max(geo.RECORDED_M2_SPEEDS))
    assert geo.ROW_SPEED_FRAME == (40, 168)
    assert not geo.row_speed_ok(132) and geo.row_speed_ok(132, dual=True)
    assert not geo.row_speed_ok(39) and not geo.row_speed_ok(169) and geo.row_speed_ok(100)


@pytest.mark.parametrize("factor", [0.5, 0.55, 0.75, 1.05, 1.5, 1.95, 2.0])
@pytest.mark.parametrize("base", sorted(set(sp.STRIP_SPEEDS)))
def test_a_factored_speed_never_leaves_the_frame(base, factor):
    v = sp.factored_speed(base, factor)
    assert 40 <= v <= 168 and v != 132 and geo.row_speed_ok(v)


@pytest.mark.parametrize("factor", [0.5, 2.0])
@pytest.mark.parametrize("patch_mm", [8.0, 8.9, 9.5, 10.0, 10.5, 11.0, 12.0, 13.0, 14.0, 16.0, 20.0])
def test_every_patch_length_at_both_ends_of_the_factor(patch_mm, factor):
    base, p = _factored(patch_mm, factor)
    assert 40 <= p.speed <= 168 and p.speed != 132
    # the speed sent is the speed planned, in the recorded m2 form, through the wire gate
    line = geo.m2_line(0, 2000, p.speed)        # a point inside the area (the row is synthetic)
    cid, x, y, v = geo.decode_xyv(line)
    assert (cid, v) == ("m2", p.speed) and cl.classify(line)[0] == "m2"
    # every patch keeps the minimum of clean readings with the border it is cut with
    assert sp.strip_windows_ok(p) >= sp.STRIP_MIN_READINGS
    if factor < 1:
        assert p.edge_mm is None and sc.plan_edge_mm(p) >= 0.5


# ---- 1.00 is 4.3.53 ------------------------------------------------------------------------------

@pytest.mark.parametrize("patch_mm", [8.0, 10.0, 12.0, 14.0])
def test_factor_one_is_the_released_plan_and_cut(patch_mm):
    base, p = _factored(patch_mm, 1.0)
    ref = T._row(patch_mm, 1.0, base)
    assert (p.speed, p.N, p.T, p.A, p.end) == (ref.speed, ref.N, ref.T, ref.A, ref.end)
    assert p.edge_mm is None and geo.m2_line(0, 2000, p.speed) == geo.m2_line(0, 2000, base)
    rows = T.stream(ref, patch_mm)
    assert sc.cut_by_position(p, rows) == sc.cut_by_position(ref, rows)
    assert sc.plan_edge_mm(p) == sc.strip_edge_mm(base)
    assert sp.is_factor_one(1.0) and sp.clean_factor(None) == 1.0


def test_the_two_copies_of_the_factors_grid_agree():
    from core import i1io_row_speed as rs
    assert (rs.DEFAULT, rs.RANGE, rs.STEP, rs.SETTING) == (
        sp.ROW_SPEED_FACTOR_DEFAULT, sp.ROW_SPEED_FACTOR_RANGE, sp.ROW_SPEED_FACTOR_STEP,
        "i1io_table_row_speed_factor")
    for raw in (None, "x", 0.1, 0.52, 1.0, 1.37, 1.95, 2.4, float("nan")):
        assert rs.clean(raw) == sp.clean_factor(raw)


def test_the_stored_factor_is_kept_on_its_grid_and_range():
    assert sp.clean_factor("1.37") == 1.35 and sp.clean_factor(3) == 2.0
    assert sp.clean_factor(0.1) == 0.5 and sp.clean_factor("x") == 1.0
    assert sp.clean_factor(float("nan")) == 1.0


# ---- faster than the border rule allows ------------------------------------------------------------

def test_a_row_faster_than_the_rule_allows_is_cut_with_a_shrunk_border_and_logged():
    base, p = _factored(10.0, 2.0)
    assert base == 88 and p.speed == 168
    rule = sc.strip_edge_mm(168)
    assert p.edge_mm is not None and p.edge_mm < rule
    # shrunk JUST enough: 0.01 mm more and a patch would have too few clean readings
    wider = sc.windows(p, sc.MOTION_START_AFTER_LAMP_S, p.N, edge_mm=p.edge_mm + 0.01)
    assert min(b - a for a, b in wider) < sp.STRIP_MIN_READINGS
    line = sp.speed_log_line(p)
    assert (f"read faster than the safe border allows (factor 2.00): border {p.edge_mm:.2f} mm "
            f"in place of {rule:.2f} mm") in line
    # the cut uses that border, and every check on the readings stays active
    rows = T.stream(p, 10.0)
    _vals, info = sc.cut_by_position(p, rows)
    assert info["edge_mm"] == pytest.approx(p.edge_mm)


def test_a_retry_keeps_the_border(monkeypatch):
    """job.py re-plans a row read again: the border goes with it."""
    import inspect
    from workflow.i1io.table import job as J
    src = inspect.getsource(J.TableJob)
    assert "scan_plan.edge_mm = _edge" in src


def test_slower_keeps_the_rules_border_never_below_half_a_millimetre():
    base, p = _factored(10.0, 0.5)
    assert p.speed == 44 and p.edge_mm is None
    assert sc.plan_edge_mm(p) == pytest.approx(max(0.5, 44 * 0.018))


# ---- the risk at 2.00, as a number for the safety brief ---------------------------------------------

#: the worst dE00 a 10 mm patch (ChromIQ's own, 1 mm spacer) was cut with at factor 2.00 (168
#: mm/s, border 1.08 mm in place of 3.02) over motion starts off by -18..+18 ms in 1 ms steps,
#: the cuts the existing checks still accepted (work folder speed/worst_case.json)
WORST_DE00_10MM_AT_2 = 8.62


def _worst_at_two(tmp_path, tag):
    base, p = _factored(10.0, 2.0)
    worst, refused = 0.0, 0
    for ms in range(-18, 19):
        d = tmp_path / f"{tag}{ms + 18}"
        d.mkdir()
        cut = T._cut(p, T.stream(p, 10.0, ms / 1000.0), d)
        if not cut.ok:
            refused += 1
            continue
        worst = max(worst, float(T._errors(p, cut).max()))
    return worst, refused


def test_the_risk_at_factor_two_for_a_10_mm_patch_is_documented(tmp_path, monkeypatch):
    """WITHOUT the row placement check (4.3.54, placement.py: the developer switch off) the
    released checks accept cuts at factor 2.00 with a patch 8.62 dE00 off: the risk the factor's
    help text warns about."""
    from workflow.i1io.table import placement as pl
    monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", False)
    worst, refused = _worst_at_two(tmp_path, "off")
    assert worst == pytest.approx(WORST_DE00_10MM_AT_2, abs=0.05)
    assert refused > 0, "the uniformity and reading checks still refuse some"
    # and at 1.00 the same patch length is right whatever the shift (4.3.53's own test)
    base1, p1 = _factored(10.0, 1.0)
    for ms in (-18, 0, 18):
        d = tmp_path / f"one{ms + 18}"
        d.mkdir()
        cut = T._cut(p1, T.stream(p1, 10.0, ms / 1000.0), d)
        assert not cut.ok or T._errors(p1, cut).max() <= T.DE_TOL


def test_the_row_placement_check_closes_the_risk_at_factor_two(tmp_path):
    """4.3.54: WITH the row placement check (the default) the same 37 cuts at factor 2.00 are
    either refused or right: no accepted patch beyond DE_TOL (the veto applies at every
    factor; it can only refuse, so the values it lets through are the released cut's)."""
    worst, refused = _worst_at_two(tmp_path, "on")
    assert worst <= T.DE_TOL, worst
    assert refused > 0


# ---- the window passes the factor to the job --------------------------------------------------------

def test_the_window_reads_the_setting():
    from ui import i1io_table_window as W

    class S(dict):
        def get(self, k, d=None):
            return super().get(k, d)
    assert W.row_speed_factor(S()) == 1.0
    assert W.row_speed_factor(S({W.ROW_SPEED_KEY: 1.95})) == 1.95
    assert W.row_speed_factor(S({W.ROW_SPEED_KEY: 9})) == 2.0
    import inspect
    assert "self.job.row_speed_factor = row_speed_factor(self._settings)" in \
        inspect.getsource(W.TableMeasureWindow)
