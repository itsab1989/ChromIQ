"""§R9 — what the row-label walk is allowed to cost, and what it is not.

Sebastian's gate on the fix, 2026-09-20:

    *"if the guided modes chart would fit fewer patches because of this
    (especially on A4 paper) i would consider it a regression"*

and, on the lever he proposed himself:

    *"the text size reductions, if you choose them as solution, should only be
    as much as really needed to avoid overlap, not more"*.

So this file pins four things, all of them over the WHOLE Guided surface rather
than the one chart that was reported:

  * the patch count moves on nothing;
  * the reported chart's stamp stops running over the patches;
  * a chart that already had room keeps the size it had;
  * a TYPED row-label size is never touched, and area-first is never touched.

`side_stamp` is the walk's own gate and the only thing it does, so switching it
off is the pre-fix behaviour exactly.

The one thing NOT asserted here is where the ink lands: that needs a rendered
page and it is in `test_the_guided_stamp_keeps_off_the_patches.py`.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from data.patch_db import (INSTRUMENT_DEFAULT_MARGIN, I1PRO_DEFAULT_PRESET_KEY,
                           PAPER_LABELS, i1_defaults_from_preset)
from workflow import text_edge_fit
from workflow.chart_creator import ChartCreator, ChartParams
from workflow.layout_engine import geometry, instruments, papers, raster

_EDGE_MM = 4.0


def _guided_kwargs(instr: str, paper: str, hexed: bool) -> dict:
    if instr == "i1":
        margin, pscale = i1_defaults_from_preset(I1PRO_DEFAULT_PRESET_KEY)
    else:
        margin, pscale = INSTRUMENT_DEFAULT_MARGIN.get(instr, 6), 1.0
    p = ChartParams(instrument=instr, paper=paper, pages=1, margin_mm=margin,
                    patch_scale=pscale, is_manual=False, double_density=hexed,
                    disable_left_border=True)
    creator = object.__new__(ChartCreator)
    return ChartCreator._engine_build_kwargs(creator, p)


def _measure(kw: dict, paper: str) -> dict:
    geom = instruments.geom_from_build_kwargs(kw)
    w_mm, h_mm = papers.dimensions_mm(paper)
    lay = geometry.compute(geom, w_mm, h_mm, 100_000)
    gap = geometry.patch_block_right_ink_gap_mm(geom, w_mm, h_mm, lay)
    dpi = int(kw.get("dpi") or 300)
    over = text_edge_fit.chart_note_overlap(
        "right", gap, _EDGE_MM, dpi, 0.0, 0.0,
        tol_mm=text_edge_fit.edge_tolerance_mm(dpi))
    size_pt = raster.effective_row_label_size_mm(
        geom, dpi, kw.get("indicator_font") or raster.DEFAULT_INDICATOR_FONT,
        float(kw.get("indicator_size_mm") or 0.0)) * 72.0 / 25.4
    return dict(capacity=lay.patches_per_page, gap_mm=gap,
                over=over is not None, size_pt=size_pt,
                margin_l=geom.margin_l, band=geom.rlwi)


def _combos():
    for instr in ("i1", "p3", "CM", "SS", "CR30"):
        for paper in PAPER_LABELS:
            for hexed in (False, True):
                if hexed and instr not in ("CM", "SS", "CR30"):
                    continue
                yield instr, paper, hexed


ALL = list(_combos())


def test_the_whole_guided_surface_keeps_every_patch():
    """**THE GATE.** Not one of the 120 Guided combinations fits a different
    number of patches than it did.

    Measured when this was written: the walk moves the row-label size on 12 of
    them and the patch count on none. The refusal is explicit -- a rung that
    changes `patches_per_page` in EITHER direction is not committed -- because
    fewer is Sebastian's regression and more would put the Guided capacity
    estimate (`ui/tabs/tab_chart.py::_engine_capacity`, which assembles its own
    kwargs and does not know whether this chart is stamped) out of step with
    the build.
    """
    moved = []
    for instr, paper, hexed in ALL:
        kw = _guided_kwargs(instr, paper, hexed)
        before = _measure(dict(kw, side_stamp=False), paper)
        after = _measure(dict(kw, side_stamp=True), paper)
        if before["capacity"] != after["capacity"]:
            moved.append((instr, paper, hexed,
                          before["capacity"], after["capacity"]))
    assert not moved, "the patch count moved on: %r" % (moved,)


def test_the_reported_chart_still_holds_396_patches():
    """CR30 / A4 / hexagon, which is the sheet Sebastian photographed.

    396 patches, 22 per strip, 18 strips. The number is written out rather than
    compared against itself so that a change which quietly costs a strip is a
    red test and not a green one.
    """
    kw = _guided_kwargs("CR30", "A4", True)
    assert _measure(dict(kw, side_stamp=True), "A4")["capacity"] == 396


def test_no_guided_chart_lays_patches_under_its_own_stamp():
    """After the walk the app's own overlap check is silent on all 120.

    It is the app's own check, `text_edge_fit.chart_note_overlap` with
    `edge_tolerance_mm`, and not a second opinion written here: the same
    function draws Manual's red warning, so a Guided sheet that passes this is
    a sheet Manual would not complain about either.
    """
    still = [(i, p, h) for i, p, h in ALL
             if _measure(dict(_guided_kwargs(i, p, h), side_stamp=True),
                         p)["over"]]
    assert not still, "the stamp still runs over the patches on: %r" % (still,)


def test_the_unfixed_surface_really_had_the_fault():
    """Twelve combinations, so the guard above is not passing on an empty set.

    Without this, deleting the stamp from the app entirely would turn the test
    above green.
    """
    broken = [(i, p, h) for i, p, h in ALL
              if _measure(dict(_guided_kwargs(i, p, h), side_stamp=False),
                          p)["over"]]
    assert len(broken) >= 12, (
        "only %d Guided combinations show the fault the walk is for: %r"
        % (len(broken), broken))
    assert ("CR30", "A4", True) in broken


def test_only_the_charts_that_needed_it_moved():
    """Every combination that had room keeps its row-label size exactly.

    Sebastian: *"only as much as really needed to avoid overlap, not more"*.
    """
    for instr, paper, hexed in ALL:
        kw = _guided_kwargs(instr, paper, hexed)
        before = _measure(dict(kw, side_stamp=False), paper)
        after = _measure(dict(kw, side_stamp=True), paper)
        if not before["over"]:
            assert after["size_pt"] == pytest.approx(before["size_pt"]), (
                f"{instr}/{paper}/hex={hexed} had "
                f"{before['gap_mm']:.3f} mm of white paper on the right and "
                "its row labels were shrunk anyway")
            assert after["margin_l"] == pytest.approx(before["margin_l"])


def test_the_walk_stops_at_the_first_rung_that_clears():
    """One rung further up must still be short, or the walk went too far.

    Checked on every combination it moved: putting the next half-point back
    leaves the app's own overlap check firing, so nothing was spent that was
    not needed.
    """
    checked = 0
    for instr, paper, hexed in ALL:
        kw = _guided_kwargs(instr, paper, hexed)
        before = _measure(dict(kw, side_stamp=False), paper)
        after = _measure(dict(kw, side_stamp=True), paper)
        if after["size_pt"] == pytest.approx(before["size_pt"]):
            continue
        checked += 1
        one_up = text_edge_fit.pt_to_mm(after["size_pt"] + 0.5)
        probe = _measure(dict(kw, side_stamp=False,
                              indicator_size_mm=one_up), paper)
        assert probe["over"], (
            f"{instr}/{paper}/hex={hexed} settled at {after['size_pt']:.1f} pt "
            f"when {after['size_pt'] + 0.5:.1f} pt already cleared the stamp")
    assert checked >= 12


def test_a_typed_row_label_size_is_never_walked():
    """§R8's first rule, and §R9 keeps it.

    A number somebody chose is not the app's to spend; a Manual user who typed
    one keeps their size AND keeps the red warning that names their own levers.
    """
    kw = _guided_kwargs("CR30", "A4", True)
    typed = text_edge_fit.pt_to_mm(17.5)
    before = _measure(dict(kw, side_stamp=False, indicator_size_mm=typed), "A4")
    after = _measure(dict(kw, side_stamp=True, indicator_size_mm=typed), "A4")
    assert after["size_pt"] == pytest.approx(17.5)
    assert after["margin_l"] == pytest.approx(before["margin_l"])
    assert after["over"], (
        "a typed size cleared the stamp by itself, so this chart proves "
        "nothing about whether the walk left it alone")


def test_area_first_is_left_alone_because_the_lever_does_nothing_there():
    """Under "Prioritise chart area, then fit patches to it" the margins are the
    law and the block fills the box, so freeing width on the left makes the
    PATCHES wider and hands the right edge nothing.

    Measured over the whole half-point grid on the reported chart: the right
    gap stayed between 5.01 and 5.18 mm at every size from 20.0 pt down to
    7.0 pt, against a 7.06 mm reserve. This pins both halves -- that the walk
    changes nothing there, and that it would have been pointless if it had.
    """
    kw = dict(_guided_kwargs("CR30", "A4", True), layout_mode="area_first",
              area_method="by_width", area_cols=18)
    before = _measure(dict(kw, side_stamp=False), "A4")
    after = _measure(dict(kw, side_stamp=True), "A4")
    assert after["size_pt"] == pytest.approx(before["size_pt"])
    assert after["margin_l"] == pytest.approx(before["margin_l"])
    assert after["capacity"] == before["capacity"]

    gaps = []
    pt = 20.0
    while pt >= 7.0:
        gaps.append(_measure(dict(kw, side_stamp=True,
                                  indicator_size_mm=text_edge_fit.pt_to_mm(pt)),
                             "A4")["gap_mm"])
        pt -= 0.5
    assert max(gaps) - min(gaps) < 0.5, (
        "the row-label size DOES move the right gap in area-first now "
        f"(spread {max(gaps) - min(gaps):.3f} mm), so §R9's exclusion of that "
        "mode needs re-deciding")


def test_the_reserve_is_one_derivation_shared_with_the_panel():
    """`side_stamp_reserve_mm` and `chart_note_overlap` are the same sum.

    Two derivations of one reserve is how the margin inspector's copy drifted
    from the stamper's. A margin exactly equal to the reserve fits; anything
    below it, past the tolerance, does not.
    """
    for edge, band, size_pt in ((4.0, 0.0, 0.0), (4.0, 24.0, 0.0),
                                (7.0, 0.0, 9.0), (0.0, 0.0, 6.0)):
        reserve = text_edge_fit.side_stamp_reserve_mm(edge, band, size_pt)
        assert text_edge_fit.chart_note_overlap(
            "right", reserve, edge, 300, band, size_pt) is None
        assert text_edge_fit.chart_note_overlap(
            "right", reserve - 1.0, edge, 300, band, size_pt,
            tol_mm=0.0) is not None
