""""Size = auto" lowers the label rather than raising the left margin — §R8.

The design authority reported it on beta 19, loading
``CR30-A4-420p-1page-Portrait-w11.0mm-Hexagonal``:

    "If the auto-sizing of the strip and row indicators had worked (Size =
    auto) then the font size should have found a text size where the space
    left of the left margin would not have needed to be widened from 13.0mm to
    14.0mm, as the warning says. ... Since size is set to auto, I would expect
    the label text size to be found where there is no warning (as long as size
    does not go below 7pt, as usual)."

It was built, measured and then HELD for eleven days, because releasing the
left margin gives area-first a wider box to fill and three Letter hexagonal
presets then needed a sheet more than their name promises. He ruled on
2026-09-16 and removed that cost himself rather than accepting it:

    "It is more important that the feature is correct, so make the fix for the
    'Size = auto' choosing a label size that fits with the margins used."

So `raster.apply_row_label_geometry` walks an AUTOMATIC size down the
half-point grid to `text_edge_fit.AUTO_SHRINK_FLOOR_PT` and takes the first
size whose band fits the margin the recipe asked for. Three properties of that
walk are deliberate and each has a test here, because each one was wrong in
some earlier draft of it:

* a size the user TYPED is never touched (§R1.5 raises the margin for it, as
  before);
* nothing is committed unless it CLEARS, so a sheet where no size fits keeps
  its size AND its raised margin rather than losing legibility for nothing;
* the starting size is re-derived rather than read back off the geometry, so
  applying the function twice cannot ratchet the labels down.

**WHERE THE ANSWER IS KEPT.** `Geom.row_label_size_mm`, read back by
`raster.effective_row_label_size_mm`, which is the one function every reader of
the size comes through. That is what keeps the renderer, the band reservation
and the panel's own ⓘ from disagreeing about which size is on the paper.

See `docs/design/row_label_geometry.md` §R8 and `docs/beta8_open_items.md`
B8-265.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow import text_edge_fit as tef                  # noqa: E402
from workflow.layout_engine import instruments, raster     # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe    # noqa: E402

#: His own preset, by key.
HIS_PRESET = "__chromiq_knut_cr30_a4_420p_1page_portrait_w11_0mm_hexagonal__"


def _pt(geom) -> float:
    """The size "auto" settled on, in points; 0.0 when it settled on nothing."""
    mm = float(getattr(geom, "row_label_size_mm", 0.0) or 0.0)
    return mm * 72.0 / 25.4


def _geom(r):
    return instruments.geom_from_build_kwargs(r.build_kwargs())


def _his_recipe(**over):
    """His preset as it was WHEN HE REPORTED IT: left margin 13.0, size auto.

    Taken from the shipped preset and then put back into that state, because
    the same comment that ruled on this also changed the preset: it now types
    11.0 pt and asks for 14.0 mm, which is a chart the walk never runs on. The
    fault he reported still has to be pinned, so it is reconstructed here.
    """
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
    rec = dict(KNUT_PRESETS_BY_KEY[HIS_PRESET].layout_recipe)
    rec["margin_left"] = 13.0
    rec["indicator_size_mm"] = 0.0          # "auto", as he had it
    rec.update(over)
    return LayoutRecipe.from_dict(rec)


# ---------------------------------------------------------------- his case
def test_auto_settles_at_sixteen_points_on_his_own_preset():
    """The number he named, on the chart he named.

    *"reducing the font size manually to 16pt would remove the warning"* --
    and 16.0 pt is where the walk stops on its own.
    """
    g = _geom(_his_recipe())
    assert _pt(g) == pytest.approx(16.0, abs=0.01), (
        f"auto settled at {_pt(g):.2f} pt, not the 16.0 he measured")


def test_the_left_margin_he_asked_for_is_the_one_he_gets():
    """The whole point: 13.0 mm stays 13.0 mm, so the warning has nothing to
    report. Before the fix the same chart came out at 13.926 mm."""
    g = _geom(_his_recipe())
    assert float(g.margin_l) == pytest.approx(13.0, abs=0.001), (
        f"the margin went to {g.margin_l:.3f} mm")
    # AND THE BAND REALLY FITS IT, rather than the margin having been left
    # alone with a band hanging over the edge.
    floor = float(getattr(g, "row_label_floor", 0.0) or 0.0)
    assert floor + float(g.rlwi) + 1.0 <= 13.0 + 0.001


def test_the_renderer_is_told_the_size_the_band_was_reserved_for():
    """A size settled on and not passed to the renderer would draw 19 pt
    labels into a band measured for 16, which is the fault this replaces
    rather than a fix for it."""
    r = _his_recipe()
    g = _geom(r)
    kw = r.build_kwargs()
    drawn = raster.effective_row_label_size_mm(
        g, int(kw.get("dpi") or 300),
        kw.get("indicator_font") or raster.DEFAULT_INDICATOR_FONT, 0.0)
    assert drawn * 72.0 / 25.4 == pytest.approx(16.0, abs=0.01), (
        f"the renderer would draw {drawn * 72.0 / 25.4:.2f} pt")


# ------------------------------------------------- the three deliberate parts
def test_a_typed_size_is_left_exactly_where_it_was_typed():
    """§R8's first property. Capping a number somebody chose would be the app
    arguing with them, which is already this document's rule for the pitch
    cap. The margin rises for a typed size exactly as §R1.5 says."""
    g = _geom(_his_recipe(indicator_size_mm=19.0 * 25.4 / 72.0))
    assert _pt(g) == 0.0, "a typed size was walked down"
    assert float(g.margin_l) > 13.0 + 0.05, (
        f"the margin stayed at {g.margin_l:.3f} mm, so a typed size was "
        "quietly shrunk instead")


def test_nothing_is_committed_when_no_size_down_to_the_floor_fits():
    """§R8's second property, and the first implementation got it wrong.

    A clip border wider than the margin puts the FLOOR alone past it, so the
    margin has to rise whatever the type does. Walking the size down there
    costs the reader legibility and clears nothing. Measured on that draft: it
    went from 19.8 pt to 7.0 pt while `margin_l` reached 16.95 mm either way.
    """
    r = _his_recipe(clip_border=True, clip_border_width_mm=12.0,
                    clip_side="left", margin_left=12.0)
    g = _geom(r)
    floor = float(getattr(g, "row_label_floor", 0.0) or 0.0)
    assert floor >= 12.0, (
        f"the premise failed: the floor is {floor:.2f} mm, so this chart is "
        "not one where the margin must rise regardless")
    assert _pt(g) == 0.0, (
        f"auto walked to {_pt(g):.2f} pt on a chart where nothing it could "
        "reach would clear the margin")
    assert float(g.margin_l) > 12.0, "the margin had to rise here and did not"


def test_applying_the_geometry_twice_does_not_ratchet_the_label_down():
    """§R8's third property: the starting size is RE-DERIVED, not read back.

    `apply_furniture_reserves` is the only caller today, but what it returns is
    an ordinary `Geom` and nothing stops a second pass, and the first draft of
    this got it wrong in a way no on-screen run would have shown. It left the
    settled size on the geometry, so the second pass measured the band at
    16 pt, found that it already fitted, took the branch that walks nothing,
    and returned a geometry with the band still reserved for 16 pt and
    `row_label_size_mm` back at 0. `effective_row_label_size_mm` would then
    have told the renderer to draw the 19 pt automatic size into a 16 pt band.

    So the size is dropped before anything is measured, and a second pass over
    an unraised margin lands on exactly the same chart.
    """
    r = _his_recipe()
    kw = r.build_kwargs()
    once = _geom(r)
    twice = raster.apply_row_label_geometry(once, kw)
    assert _pt(twice) == pytest.approx(_pt(once), abs=0.001), (
        f"a second pass moved the size from {_pt(once):.2f} to "
        f"{_pt(twice):.2f} pt")
    assert float(twice.margin_l) == pytest.approx(float(once.margin_l), abs=0.001)
    assert float(twice.rlwi) == pytest.approx(float(once.rlwi), abs=0.001)


@pytest.mark.parametrize("margin", [5.0, 8.0, 11.0, 13.0, 16.0, 20.0, 30.0])
def test_the_band_reserved_and_the_size_drawn_always_describe_one_chart(margin):
    """THE INVARIANT THE WHOLE MECHANISM RESTS ON, at every margin.

    `rlwi` is the paper set aside for the labels and
    `effective_row_label_size_mm` is what the renderer draws in it. They are
    computed in different places and read by different callers, and if they can
    disagree then every number the panel prints about the left margin is
    describing a sheet that will not be printed. So: whatever size comes back,
    re-measuring the band AT that size must give the band that was reserved.

    Checked at a margin the walk cannot help (5 mm), ones where it settles, and
    one wide enough that it never runs, because the three take different
    branches and only one of them was ever wrong.
    """
    r = _his_recipe(margin_left=margin)
    kw = r.build_kwargs()
    g = _geom(r)
    drawn_mm = raster.effective_row_label_size_mm(
        g, int(kw.get("dpi") or 300),
        kw.get("indicator_font") or raster.DEFAULT_INDICATOR_FONT, 0.0)
    again = raster.row_label_band_mm(
        g, dpi=int(kw.get("dpi") or 300),
        indicator_font=kw.get("indicator_font") or raster.DEFAULT_INDICATOR_FONT,
        indicator_size_mm=drawn_mm,
        indicator_bold=bool(kw.get("indicator_bold")),
        indicator_italic=bool(kw.get("indicator_italic")),
        patch_pattern=kw.get("patch_pattern") or "")
    assert again == pytest.approx(float(g.rlwi), abs=0.01), (
        f"{margin} mm: the band reserves {g.rlwi:.3f} mm but the renderer "
        f"draws {drawn_mm * 72.0 / 25.4:.2f} pt, which needs {again:.3f} mm")


def test_the_walk_never_goes_below_the_floor_he_named():
    """*"as long as size does not go below 7pt, as usual"* -- his own bound,
    and it is the same `AUTO_SHRINK_FLOOR_PT` every other automatic shrink in
    the app stops at, so what this settles on is a size a user could type."""
    assert tef.AUTO_SHRINK_FLOOR_PT == 7.0
    # A margin barely above the floor: the walk runs the whole ladder and must
    # either land on something at or above 7 pt, or leave the size alone.
    for margin in (5.0, 5.5, 6.0, 6.5, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0):
        g = _geom(_his_recipe(margin_left=margin))
        got = _pt(g)
        assert got == 0.0 or got >= tef.AUTO_SHRINK_FLOOR_PT - 0.001, (
            f"a {margin} mm margin settled the label at {got:.2f} pt")


def test_every_size_it_settles_on_is_one_the_size_box_can_hold():
    """The half-point grid, which is the grid the Size boxes step by. A walk
    that settled on 15.83 pt would put a number on the sheet that the control
    meant to reproduce it cannot be set to."""
    seen = set()
    for margin in [x / 2.0 for x in range(10, 60)]:
        got = _pt(_geom(_his_recipe(margin_left=margin)))
        if got:
            seen.add(round(got, 4))
    assert seen, "no margin in the sweep made the walk settle on anything"
    for got in sorted(seen):
        assert abs(got * 2.0 - round(got * 2.0)) < 1e-6, (
            f"{got} pt is not on the half-point grid")


def test_a_shorter_margin_never_settles_on_a_larger_label():
    """Monotone, which is what makes the walk predictable to a reader who
    narrows the margin one step at a time. It is not automatic: the band is
    measured from a rendered glyph, and a rounding that went the wrong way at
    one rung would show up here and nowhere else."""
    last = None
    for margin in [x / 2.0 for x in range(24, 60)]:
        got = _pt(_geom(_his_recipe(margin_left=margin)))
        if not got:
            continue
        if last is not None:
            assert got >= last - 1e-6, (
                f"{margin} mm settled at {got} pt after a narrower margin "
                f"settled at {last} pt")
        last = got


# ----------------------------------------- the help had to stop promising one size
def test_the_two_label_sets_really_can_differ_in_size():
    """The premise of the test below, measured rather than asserted.

    Before §R8 the strip letters and the row numbers came out of the same
    automatic size on any chart with a normal row pitch. They no longer do, and
    the gap is nearly 3 pt on the very chart that was reported.
    """
    r = _his_recipe()
    kw = r.build_kwargs()
    g = _geom(r)
    font = kw.get("indicator_font") or raster.DEFAULT_INDICATOR_FONT
    strip = raster.effective_indicator_size_mm(
        g, int(kw.get("dpi") or 300), font, 0.0) * 72.0 / 25.4
    row = raster.effective_row_label_size_mm(
        g, int(kw.get("dpi") or 300), font, 0.0) * 72.0 / 25.4
    assert strip > row + 1.0, (
        f"strip letters {strip:.2f} pt, row numbers {row:.2f} pt; if these "
        "agree the help text below has nothing to correct")


def test_the_font_help_no_longer_promises_one_size_for_both():
    """A HELP TEXT THAT PROMISES ONE SIZE WHILE THE SHEET PRINTS TWO.

    The "Indicator font" ⓘ says *"Size 'auto' fits the strip letters to the
    strip width, and the row numbers follow the same size"*. Since §R8 that is
    false wherever the left margin is short: measured on the chart that was
    reported, the letters print at 19.0 pt and the numbers at 16.0. The
    sentence is not deleted, because it is still what happens on most charts;
    a paragraph is added that says when it does not.

    This is here rather than in the panel's own test file because the thing
    that made it false is the geometry above it.
    """
    import os as _os
    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    from ui.dialogs import layout_options_panel as lop
    from ui.tooltip_button import TooltipButton
    QApplication.instance() or QApplication([])
    panel = lop.LayoutOptionsPanel()
    try:
        tips = [w for w in panel._label_sub_both.findChildren(TooltipButton)
                if "indicator font" in (w._title or "").lower()]
        assert tips, "the label frame has no font ⓘ"
        body = (tips[0]._body or "").lower()
        assert "follow the same size" in body, (
            "the premise moved: this test exists to check the correction to "
            "that promise, so if the promise is gone it should be rewritten "
            "rather than passing by accident")
        assert "smaller than the strip letters" in body, (
            "the help still promises one size for both and never says that "
            "the row numbers can come out smaller")
        assert "7 pt" in body, (
            "the help does not say how far down the row numbers may be "
            "stepped, so a reader cannot predict what they will get")
        assert "half a point" in body, (
            "the help does not say the step, so the sizes it can settle on "
            "are unguessable")
        # **THE TWO FLOORS MUST NOT READ AS A CONTRADICTION.** The paragraph
        # above already says "auto" never shrinks a label below about 4 pt,
        # which is `raster.INDICATOR_MIN_LEGIBLE_MM` and a different mechanism
        # from this one. A reader who meets "4 pt" and then "7 pt" with no
        # word between them has been handed two numbers for one thing. Both
        # floors are real; the text has to say which is which.
        from workflow.layout_engine import raster as _r
        from workflow import text_edge_fit as _t
        assert _r.INDICATOR_MIN_LEGIBLE_MM * 72.0 / 25.4 < _t.AUTO_SHRINK_FLOOR_PT
        assert "4 pt" in body and "higher than" in body, (
            "the help gives a 7 pt floor and a 4 pt floor without saying that "
            "they are different limits or which one is higher")
    finally:
        panel.deleteLater()


# ------------------------------------------------- what it must NOT have done
def test_the_eight_hexagonal_presets_still_print_what_their_names_promise():
    """The reason this was held for eleven days, closed out.

    Releasing the left margin gives area-first a wider box and it fills a wider
    box with BIGGER patches, so before his preset changes three Letter charts
    spilled: 390 patches onto two pages, 780 onto three, 1170 onto four. With
    the preset changes in the same batch, every one of them is back to the
    count and the page total its own name states. Built here rather than
    predicted, because a prediction is what got this wrong the first time.
    """
    import tempfile
    from pathlib import Path
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import KNUT_PRESETS
    from workflow.layout_engine.chart import build_from_recipe

    hexes = [p for p in KNUT_PRESETS
             if "cr30_" in p.key and "Hexagonal" in p.name
             and "-Straight" not in p.name]
    assert len(hexes) == 8, f"{len(hexes)} upright hexagonal CR30 charts"
    for p in hexes:
        rec = LayoutRecipe.from_dict(p.layout_recipe)
        with tempfile.TemporaryDirectory() as td:
            res, _ = build_from_recipe(
                resource_path(p.ti1_asset), Path(td) / "chart", rec)
            assert res.layout.pages == p.pages, (
                f"{p.name} lays out on {res.layout.pages} pages")
            assert res.layout.total_patches == p.patches, (
                f"{p.name} lays out {res.layout.total_patches} patches")
            assert len(sorted(Path(td).glob("chart*.tif"))) == p.pages
