# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.53 fix round, inventory C3: a strip row starts at the speed i1Profiler chose for its own
FIRST pass over a row of the same patch pitch (110 / 118 / 137 / 138 / 168 from the recordings),
no longer at the slowest. Fix round 2 (the re-review's MUST-A1): from there it goes down to the
fastest RECORDED speed whose clean border (scan.strip_edge_mm: speed x 18 ms, at least 0.5 mm)
still leaves 3 readings in every patch. Only recorded speeds go on the wire; the row form is the
recorded one (c4, p0, m0 @300, d1 016D, p0, m2, a3, c3)."""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import scan as sc
from workflow.i1io.table import spot as sp

#: (recorded alignment, i1Profiler's first-pass m2 line in that recording, its speed)
#: the m2 lines decode as ;m2 XXXX YYYY VVVV + checksum (geometry.decode_xyv)
RECORDED_FIRST_PASS = {
    "S2 270.8": 110,            # S2 313.032 (session 2): v 110, n 530
    "S2 3.5": 118,              # S2 116.405 ;m20497067d007684 (R14 line 116.405), v 118, n 520
    "S2 526.8": 118,            # S2 553.196: v 118, n 520
    "R1 200.3": 137,            # R1 281.68: v 137, n 520
    "R1 401.6": 138,            # R1 433.187: v 138, n 520
    "R2 427.5": 138,            # R2 476.908 / 534.265 / 591.598 / 648.868: v 138, n 520
}


def _plan(name):
    sheet, pts = H.recorded_sheet(name, 4)
    al = geo.fit_model([tuple(sc.sheet_table_mm(sheet, a["page_mm"]))
                        for a in sheet["pages"][0]["aim_points"]], pts)
    return sp.plan_strip_row(sheet, 0, 0, al, None,
                             cap_y=geo.table_cap(max(p[1] for p in pts) + 300)), sheet


def test_the_recorded_m2_line_of_r14_decodes_to_the_speed_this_table_names():
    cid, x, y, v = geo.decode_xyv(b";m20497067d007684\r")
    assert (cid, x, y, v) == ("m2", 1175, 1661, 118)


def _fastest_allowed(plan_speed_of, vendor):
    """The fastest recorded strip speed, not above the vendor's, whose clean border
    (scan.strip_edge_mm) still leaves STRIP_MIN_READINGS in every patch."""
    for v in sorted((x for x in sp.STRIP_SPEEDS if x <= vendor), reverse=True):
        f = plan_speed_of(v)
        if f is not None and f >= sp.STRIP_MIN_READINGS:
            return v
    return None


@pytest.mark.parametrize("name", sorted(RECORDED_FIRST_PASS))
def test_each_recorded_chart_starts_at_i1profilers_speed_and_is_read_as_fast_as_its_border_allows(name):
    """4.3.53 fix round 2 (the re-review's MUST-A1): the vendor's first-pass speed for the pitch
    is where the planner starts (unchanged), and the row is read at the fastest RECORDED speed
    whose clean border (speed x 18 ms, at least 0.5 mm) still leaves 3 readings in every patch.
    On the vendor's own charts (patches as long as their pitch, 8.4-9.5 mm) that is 61 or 88."""
    plan, sheet = _plan(name)
    want = RECORDED_FIRST_PASS[name]
    assert sp.vendor_speed(sp.row_pitch_mm(sheet["pages"][0]["strips"][0])) == want
    assert sp.speeds_to_try(sp.row_pitch_mm(sheet["pages"][0]["strips"][0]))[0] == want
    p0 = plan.scan
    allowed = _fastest_allowed(
        lambda v: sp.strip_windows_ok(sc.plan_row("x", p0.start, p0.end, v, p0.patches)), want)
    assert plan.kind == "strip" and plan.scan.speed == allowed, (plan.scan.speed, allowed)
    cid, _x, _y, v = geo.decode_xyv(plan.scan.m2)
    assert (cid, v) == ("m2", allowed) and allowed in geo.RECORDED_M2_SPEEDS
    cid0, *_r, v0 = geo.decode_xyv(plan.scan.m0)
    assert (cid0, v0) == ("m0", 300)                      # the recorded travel to the start


def test_chromiqs_own_10_mm_patches_are_read_at_88_and_168_needs_long_patches():
    """The volunteer's 17 Nov rows were read by i1Profiler at 168 (10.73 mm pitch); ChromIQ's own
    chart (10 mm patch, 1 mm spacer) starts there and is read at 88 mm/s, the fastest recorded
    speed whose 1.6 mm border still leaves 3 clean readings (4.3.52: 54)."""
    assert sp.vendor_speed(10.73) == 168
    sheet = H.demo_sheet()
    assert sp.row_pitch_mm(sheet["pages"][0]["strips"][0]) >= 10.73
    al = geo.fit_model([tuple(sc.sheet_table_mm(sheet, a["page_mm"]))
                        for a in sheet["pages"][0]["aim_points"]], H.demo_aims(sheet))
    plan = sp.plan_strip_row(sheet, 0, 0, al, None, cap_y=geo.table_cap(3400))
    assert plan.scan.speed == 88 and geo.decode_xyv(plan.scan.m2)[3] == 88


def test_the_vendor_rule_fits_every_recorded_first_pass_and_sends_only_recorded_speeds():
    a, b = sp.VENDOR_RULE
    for pitch, v in sp.VENDOR_FIRST_PASS:
        assert abs(a * (pitch - b) - v) < 3, (pitch, v)
    for p10 in range(60, 160):
        assert sp.vendor_speed(p10 / 10) in geo.RECORDED_M2_SPEEDS
    # never faster per millimetre of patch than i1Profiler was recorded going
    for pitch, v in sp.VENDOR_FIRST_PASS:
        assert sp.vendor_speed(pitch - 0.01) <= v


def test_the_repeat_speeds_are_tried_only_after_the_vendors_own():
    order = sp.speeds_to_try(9.6)
    assert order[0] == 138 and order[1:5] == (137, 118, 110, 88)
    assert set(order) == set(sp.STRIP_SPEEDS)


def test_the_cut_still_finds_every_patch_at_the_planned_speed():
    """ChromIQ's own cut keeps at least STRIP_MIN_READINGS (3) inside the speed's clean border
    (4.3.53 fix round 2) in every window."""
    for name in RECORDED_FIRST_PASS:
        plan, _s = _plan(name)
        assert sp.strip_windows_ok(plan.scan) >= sp.STRIP_MIN_READINGS == 3
