"""Three alignments for the two bottom lines, and the ink proves each one.

Knut, 2026-09-14. He asked for left-alignment first::

    for the sake of beauty, I find it better that the two bottom text type (in
    Sheet text frame) should be left-aligned against the patch area left
    margin, instead of centred against available horizontal space.

and came back the same hour with all three, and a control to pick between
them::

    1. Left margin (default): this is the new option mentioned above, where any
       of the two bottom text types are left adjusted against the left margin.
    2. Centre of available space: This is the alignment type already in the
       design on beta 13.
    3. Centre between left and right margin: This type is new, where the centre
       alignment is set between the patch area left margin and right margin.

    Leave side-limit detection as it is designed. Depending on the set
    alignment of text, a long text may trigger a warning on either sides, or
    only one side.

**THE BOUNDS DO NOT MOVE.** `text_edge_fit.bottom_text_bounds_mm` is his own
case table from comment 5651269930 plus the margin clause he confirmed on
2026-09-13, and none of it changes here. What changes is where a line STARTS
between them, and therefore how much of the paper it can use.

Every placement claim below is measured on a rendered A4, by differencing two
sheets whose geometry is pinned (`chart_text=" "` on the off-pass keeps
`nlines` at 1 and draws nothing) with the seed fixed, so the difference is the
line's own ink and nothing else. Three earlier probes on this project produced
confident wrong numbers by skipping one of those two precautions.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from workflow import text_edge_fit as tef                      # noqa: E402

from tests.test_the_top_and_bottom_edges_keep_off_the_helper_markers import (  # noqa: E402
    _moved, _recipe, _render)

#: Ten narrow characters: short enough that all three alignments fit, so the
#: three answers differ by PLACEMENT and not by clipping.
SHORT = "IIIIIIIIII"
#: The asymmetric page that separates his two centres. With 25 mm on the left
#: and 8 mm on the right, the patch area's midpoint is 113.5 mm while the two
#: bounds put theirs at 105.0. On the symmetric default they coincide, so a
#: test written there cannot tell them apart.
LEFT_MM, RIGHT_MM = 25.0, 8.0


def _band(align, **kw):
    r = _recipe(chart_text=SHORT, chart_text_size_mm=3.2,
                chart_text_align=align, margin_left=LEFT_MM,
                margin_right=RIGHT_MM, **kw)
    return _moved(_render(r, chart_text_align=align)[0],
                  _render(r, chart_text=" ", chart_text_align=align)[0])


# ----------------------------------------------------------- the arithmetic
def test_his_three_names_are_the_three_keys():
    assert tef.BOTTOM_TEXT_ALIGNMENTS == ("left_margin", "available",
                                          "between_margins")
    assert tef.BOTTOM_TEXT_ALIGN_DEFAULT == "left_margin", (
        "he wrote “Left margin (default)”")


def test_the_patch_area_centre_is_between_the_margins_not_the_paper():
    """*"the centre alignment is set between the patch area left margin and
    right margin"* — so on 25/8 it is 113.5, not the paper's 105.

    MUTATION: return `paper_w / 2` and this goes red.
    """
    assert tef.bottom_text_centre_mm(210.0, 25.0, 8.0) == pytest.approx(113.5)
    assert tef.bottom_text_centre_mm(210.0, 12.0, 12.0) == pytest.approx(105.0)


def test_the_room_is_what_that_alignment_leaves():
    """*"Depending on the set alignment of text, a long text may trigger a
    warning on either sides, or only one side."*

    On 210 mm with a 12 mm left margin and a 30 mm right one, the bounds are
    (4, 206) in all three cases. Left-aligned the line starts at 12 and has
    206 - 12. Centred on the bounds it has the whole 202.

    Centred on the PATCH AREA it also has 202 here, and that is the part an
    adversary round had to measure to get right. The patch area's midpoint is
    96, LEFT of the bounds' own midpoint of 105, so a line wide enough to reach
    the left bound stops being centred at all: `bottom_text_start_mm` anchors
    it at the bound, exactly as the centred renderer always did with an
    over-long line. It is therefore not too wide to print, and the first
    version of this rule, `2 x min(centre - left, right - centre)`, called
    184 mm the limit and warned about ink that was entirely on the paper.

    MUTATION: drop the `align` branch and every row here collapses to one
    number; restore `2 x min(...)` and the third row goes back to 184.
    """
    got = {a: tef.bottom_text_room_mm(210.0, 4.0, margin_left_mm=12.0,
                                      margin_right_mm=30.0, align=a)
           for a in tef.BOTTOM_TEXT_ALIGNMENTS}
    assert got["left_margin"] == pytest.approx(194.0)
    assert got["available"] == pytest.approx(202.0)
    assert got["between_margins"] == pytest.approx(202.0)
    # …AND THE OTHER SIDE OF THE SAME RULE. Swap the margins and the patch
    # area's midpoint moves to 114, RIGHT of 105, so the line never clamps and
    # the near bound binds twice: 2 x (206 - 114).
    assert tef.bottom_text_room_mm(
        210.0, 4.0, margin_left_mm=30.0, margin_right_mm=12.0,
        align="between_margins") == pytest.approx(184.0)


def test_a_centred_line_is_never_called_too_wide_while_it_fits():
    """The check and the placement have to be the same rule, or the panel
    reports their disagreement as a number.

    Longhand, over a grid of geometries: for every width the room says fits,
    place the line the way `bottom_text_start_mm` really places it and confirm
    the far end is inside the right bound; for the first width the room
    refuses, confirm it is not.

    MUTATION: put `2 x min(centre - left, right - centre)` back and this goes
    red on the first left-heavy patch area, because a width it refuses fits.
    """
    for ml, mr in ((12.0, 30.0), (30.0, 12.0), (12.0, 12.0), (3.0, 60.0),
                   (60.0, 3.0), (0.0, 0.0)):
        for align in tef.BOTTOM_TEXT_ALIGNMENTS:
            lo, hi = tef.bottom_text_bounds_mm(
                210.0, 4.0, margin_left_mm=ml, margin_right_mm=mr)
            room = tef.bottom_text_room_mm(
                210.0, 4.0, margin_left_mm=ml, margin_right_mm=mr, align=align)
            anchor = tef.bottom_text_anchor_mm(
                210.0, 4.0, margin_left_mm=ml, margin_right_mm=mr)
            centre = tef.bottom_text_centre_mm(210.0, ml, mr)
            where = lambda w: tef.bottom_text_start_mm(   # noqa: E731
                w, lo, hi, align=align, anchor_mm=anchor, centre_mm=centre)
            assert where(room) + room <= hi + 0.001, (
                f"{align} {ml}/{mr}: a line of {room:.2f} mm is called a fit "
                f"and is drawn from {where(room):.2f} past the {hi:.2f} bound")
            over = room + 0.5
            assert where(over) + over > hi, (
                f"{align} {ml}/{mr}: a line of {over:.2f} mm is called an "
                f"overflow and is drawn from {where(over):.2f}, ending at "
                f"{where(over) + over:.2f}, inside the {hi:.2f} bound")


def test_the_bounds_are_the_same_two_whatever_the_alignment():
    """His *"Leave side-limit detection as it is designed"*, held literally:
    `bottom_text_bounds_mm` has no alignment argument at all, so no alignment
    can move a side limit."""
    import inspect
    sig = inspect.signature(tef.bottom_text_bounds_mm)
    assert "align" not in sig.parameters


def test_a_line_never_starts_inside_the_left_bound():
    """Both centred modes ask for that as soon as the line is wider than the
    room, and the bound is a limit on all four sides everywhere else here. It
    is also what the centred renderer already did before there was a choice:
    *"A line too wide for the bounds stays anchored at the left one."*

    Left-alignment is not in that clause, and must not be: its line starts at
    the anchor whatever its length, because there is nowhere else for it to
    start and the anchor is already at or right of the bound.

    MUTATION: return the raw `start` and the two centred rows go red.
    """
    for a in ("available", "between_margins"):
        got = tef.bottom_text_start_mm(400.0, 4.0, 206.0, align=a,
                                       anchor_mm=12.0, centre_mm=105.0)
        assert got == pytest.approx(4.0), a
    assert tef.bottom_text_start_mm(400.0, 4.0, 206.0, align="left_margin",
                                    anchor_mm=12.0, centre_mm=105.0) \
        == pytest.approx(12.0)


# ------------------------------------------------------------- the ink
def test_left_margin_starts_both_lines_at_the_margin():
    band = _band("left_margin")
    assert band is not None
    assert band[2] == pytest.approx(LEFT_MM, abs=0.6), (
        f"the line runs {band[2]:.2f} to {band[3]:.2f} mm; his first option "
        f"starts it at the {LEFT_MM:g} mm left margin")


def test_centre_of_available_space_is_the_beta_13_placement():
    """His option 2, *"the alignment type already in the design on beta 13"*:
    the midpoint of `bottom_text_bounds_mm`, which on this sheet is 105.0."""
    # THE NUMBER IS WRITTEN OUT, not asked of the function the renderer uses.
    # A4 at "Clip" 4.0 with no border and no markers bounds the line at 4.0 and
    # 206.0, so its centre is 105.0. Asking `bottom_text_bounds_mm` here would
    # let a mutation move the renderer and the expectation together.
    assert tef.bottom_text_bounds_mm(210.0, 4.0) == (4.0, 206.0)
    band = _band("available")
    assert band is not None
    mid = (band[2] + band[3]) / 2.0
    assert mid == pytest.approx(105.0, abs=0.6), (
        f"the line is centred on {mid:.2f} mm and the two bounds put the "
        f"centre at 105.0 mm")


def test_centre_between_the_margins_is_a_different_centre():
    """His option 3, and the reason the sheet under test is asymmetric: on
    25/8 the patch area's midpoint is 113.5 mm, 8.5 mm right of the other
    centre, so the two centred modes cannot pass for each other."""
    band = _band("between_margins")
    assert band is not None
    mid = (band[2] + band[3]) / 2.0
    # 25 mm left, 8 mm right on a 210 mm sheet: (25 + 202) / 2 = 113.5.
    # WRITTEN OUT, not taken from `bottom_text_centre_mm`, which is the
    # function the renderer asks: mutate that to return the paper's own centre
    # and the ink and an expectation taken from it would move together, and
    # only a literal notices.
    assert mid == pytest.approx(113.5, abs=0.6), (
        f"the line is centred on {mid:.2f} mm and the patch area's midpoint "
        f"is 113.5 mm")
    assert abs(mid - 105.0) > 4.0, (
        "this sheet cannot tell his two centres apart, so the test proves "
        "nothing")


def test_the_two_bottom_lines_follow_the_same_rule():
    """*"any of the two bottom text types"* — the custom Sheet text and the
    layout summary. Measured one at a time, so `nlines` is 1 in every render
    and the geometry cannot move underneath the measurement."""
    for align in tef.BOTTOM_TEXT_ALIGNMENTS:
        r = _recipe(chart_text_size_mm=3.2, chart_text_align=align,
                    margin_left=LEFT_MM, margin_right=RIGHT_MM)
        blank = _render(r, chart_text=" ", stamp_text="",
                        chart_text_align=align)[0]
        text = _moved(_render(r, chart_text=SHORT, stamp_text="",
                              chart_text_align=align)[0], blank)
        stamp = _moved(_render(r, chart_text=SHORT, stamp_text=SHORT,
                               chart_text_align=align)[0],
                       _render(r, chart_text=SHORT, stamp_text="",
                               chart_text_align=align)[0])
        assert text is not None and stamp is not None, align
        assert text[2] == pytest.approx(stamp[2], abs=0.6), (
            f"on {align} the sheet text starts at {text[2]:.2f} mm and the "
            f"layout stamp at {stamp[2]:.2f} mm; both follow one rule")


# -------------------------------------------- the panel and the sheet agree
def test_the_renderer_and_the_panel_ask_the_same_function():
    """One rule for the ink and for the warning, or the warning is noise."""
    import ast
    import inspect
    import textwrap
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine import raster

    tree = ast.parse(textwrap.dedent(inspect.getsource(raster.render_pages)))
    names = {n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "bottom_text_start_mm" in names, \
        "the renderer places the line with arithmetic of its own again"
    assert "bottom_text_room_mm" in names, \
        "the shrink loop measures its room with arithmetic of its own again"
    src = inspect.getsource(TabChart._engine_text_notes)
    assert "align=" in src and "chart_text_align" in src, \
        "the panel's width warning does not know which alignment is set"


# ------------------------------------------------------ it survives storage
def test_the_alignment_travels_through_every_door():
    """Knut: *"The new alignment parameter must be added in the list of
    parameters so that it is saved/remembered or loaded in all cases."*

    The four doors a recipe goes through: the meta.json round-trip, the engine
    build kwargs and their inverse, and a plain dict of the kind the built-in
    presets are written as.
    """
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe()
    r.chart_text_align = "between_margins"
    assert LayoutRecipe.from_dict(r.to_dict()).chart_text_align \
        == "between_margins"
    kw = r.build_kwargs()
    assert kw["chart_text_align"] == "between_margins"
    assert LayoutRecipe.from_build_kwargs(kw).chart_text_align \
        == "between_margins"
    # …and a recipe written before the option existed gets HIS default rather
    # than an empty string that the renderer would have to guess about.
    assert LayoutRecipe.from_dict({"instrument": "i1"}).chart_text_align \
        == tef.BOTTOM_TEXT_ALIGN_DEFAULT
    assert LayoutRecipe.from_build_kwargs({"draw_indicators": True}) \
        .chart_text_align == tef.BOTTOM_TEXT_ALIGN_DEFAULT


def test_the_engine_actually_receives_it():
    """`build_chart` is the door between the recipe and the raster, and a
    parameter that stops at it is a parameter that does nothing."""
    import inspect
    from workflow.layout_engine import chart, raster
    assert "chart_text_align" in inspect.signature(chart.build_chart).parameters
    assert "chart_text_align" in inspect.signature(raster.render_pages).parameters
    src = inspect.getsource(chart.build_chart)
    assert "chart_text_align=chart_text_align" in src, \
        "build_chart accepts the alignment and does not pass it on"
