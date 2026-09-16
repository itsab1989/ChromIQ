"""Two rulings the design authority made on beta 19, pinned so a later round
does not quietly undo either of them.

**RULING 1 - "T" does not move the strip labels in "Prioritise patch size",
and the help text must say so.** Asked whether the geometry should change so
that it does:

    The most logical ruling is that the T parameter works the same way, however,
    since "Prioritise patch size" is based on working more closely as the
    original printtarg, I guess it is a risk to start changing that feature. I
    rule No, and the help text should mention this.

So the geometry stays as it is and the "Text distance from edge" help says which
two controls DO move them.

**RULING 3 - a pointy-top honeycomb is judged against its apex.** The notice was
found firing where the letters sit in the valleys between the apexes with
0.762 mm of clear paper under the lowest letter, and the question was whether
the check should compare against the apex or against the ink beside it:

    use the "Measured from Preview" top margin as an apex, which is the top
    margin line measured.

So the current behaviour is correct: the check takes `report.top_mm`, which
`margin_inspector` measures to the block's TOPMOST ink, and that is the apex on
that geometry. This file exists because "the warning fires on clear paper" is
exactly the shape of report that invites a later round to soften it.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402


# ------------------------------------------------------------- ruling 1
def test_the_T_help_says_it_does_not_move_them_in_patch_first():
    """The sentence he asked for, on the ⓘ of the row it is about.

    MUTATION: delete the paragraph from the "Text distance from edge" tooltip
    and this goes red.
    """
    from ui.dialogs import layout_options_panel as lop
    src = inspect.getsource(lop)
    i = src.index('tr("Text distance from edge"),')
    tip = src[i:i + 3000]
    assert "Prioritise patch size" in tip, (
        "the T help does not mention the layout where T moves nothing")
    assert "does not move the strip labels" in tip, tip[:400]
    # …and it names the two controls that DO move them, or the reader is left
    # knowing only what fails.
    assert "Label offset" in tip and "Margins (mm)" in tip, (
        "the help says what does not work without saying what does")
    # No em dash in new user-facing text.
    j = tip.index("does not move the strip labels")
    assert "—" not in tip[j - 200:j + 700]


def test_the_geometry_still_ignores_T_in_patch_first():
    """His "I rule No": the layout is NOT changed to make "T" bite.

    `geometry.strip_label_leader_top_mm` hangs the band on the top margin when
    `margins_are_law` is false, and that is what "Prioritise patch size" is.

    MUTATION: make the patch-first branch consult `strip_label_reserve_mm` and
    this goes red.
    """
    from workflow.layout_engine import geometry

    class _G:
        margins_are_law = False
        margin_t = 8.0
        offset_y = 0.0
        text_edge_top_mm = 2.0
        helper_markers = False
        helper_marker_edge_mm = 0.0
        helper_marker_len_mm = 0.0
        helper_markers_top_bottom = True
        strip_indicator_gap = 0.0

    g = _G()
    base = geometry.strip_label_leader_top_mm(g)
    for t in (0.0, 4.0, 12.0, 25.0):
        g.text_edge_top_mm = t
        assert geometry.strip_label_leader_top_mm(g) == pytest.approx(base), (
            f'"T" = {t} mm moved the band in "Prioritise patch size"; the '
            f"ruling is that it does not")
    assert base == pytest.approx(8.0), "the band no longer hangs from the margin"
    assert geometry.strip_label_band_is_margin_anchored(g) is True


# ------------------------------------------------------------- ruling 3
def test_the_top_margin_the_check_uses_is_the_measured_apex():
    """`report.top_mm`, which is measured to the topmost ink.

    On a pointy-top honeycomb the topmost ink IS an apex, so this is his
    ruling implemented: the check compares against the apex, not against the
    paper beside it.

    MUTATION: give `_patch_top` the recipe's `margin_top`, or the average of
    the apex and the flat, and this goes red.
    """
    from ui.tabs import tab_chart as tc
    body = "\n".join(
        l for l in inspect.getsource(tc.TabChart._engine_text_notes).splitlines()
        if not l.strip().startswith("#"))
    assert "_patch_top = _meas_t" in body, (
        "the strip-label check no longer judges against the measured top")
    assert '_edge("top_mm")' in body


def test_the_measured_top_is_the_blocks_topmost_ink_apex_included():
    """`margin_inspector` takes the MINIMUM y over the patch rectangles and
    then pushes it further out for the hexagon apex, so a pointy-top
    honeycomb's reported top margin is its apex line.

    MUTATION: drop the `h_px / 6.0` apex correction from
    `engine_ink_bounds_px` and this goes red.
    """
    from workflow import margin_inspector as mi
    src = inspect.getsource(mi.engine_ink_bounds_px)
    assert "y0 = min(" in src, "the top bound is no longer the topmost rect"
    assert "y0 -= h_px / 6.0" in src, (
        "the pointy-top apex is no longer added to the top bound, so the "
        "reported top margin is the flat and not the apex")
    # …and the correction is on the VERTICAL axis only for a pointy-top, which
    # is the orientation his case is about.
    i = src.index("y0 -= h_px / 6.0")
    assert "recipe_is_flat_top(rec)" in src[:i], (
        "the apex correction no longer asks which way the hexagons point")


def test_a_valley_case_is_still_reported_rather_than_softened():
    """The shape of the report that invites a later round to add slack.

    His pointy-top case fires while there is clear paper directly under the
    lowest letter, because the ink beside it is an apex that reaches higher.
    Under his ruling that is CORRECT, so the check must keep a single
    tolerance and must not gain a second, geometry-shaped one.

    MUTATION: add a hexagon-only slack term to `strip_label_overlap` and this
    goes red.
    """
    from workflow import text_edge_fit as tef
    # THE CODE, NOT THE PROSE. The comments in this function legitimately
    # discuss hexagons -- they record the sheets it was measured on. What must
    # stay out is a geometry-shaped branch in the arithmetic.
    src = inspect.getsource(tef.strip_label_overlap)
    code = "\n".join(
        l for l in src.split('"""')[-1].splitlines()
        if l.strip() and not l.strip().startswith("#")).lower()
    for word in ("hex", "apex", "valley", "honeycomb"):
        assert word not in code, (
            f"{word!r} has entered the predicate; the ruling is that the "
            f"measured top margin IS the apex, so this check needs no "
            f"geometry-shaped exception")
    # It fires on the plain inequality, tolerance and all.
    hit = tef.strip_label_overlap(13.0, 9.0, 4.0, 0.0, ink_reach_mm=4.72,
                                  anchor_mm=9.0, tol_mm=0.2)
    assert hit is not None and hit.overlap_mm == pytest.approx(0.72, abs=0.01)
