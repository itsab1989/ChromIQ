"""The strip-letter notice must not work out which control binds by ARITHMETIC.

Beta 19 taught the top-edge notice to fire in "Prioritise patch size", which it
never could before, and it chose between its three wordings like this::

    if anchor_mm is not None:
        a = float(anchor_mm)
        if abs(a - reserve) > EPS_MM:        # <-- a guess, not a fact
            held = LABEL_HELD_BY_TOP_MARGIN
            from_markers = False
        reserve = a

*reserve* is what the check works out of "T" and the ruler markers; *anchor_mm*
is where `geometry.placement` really puts the band. In "Prioritise chart area"
that anchor is ``reserve + the layout's strip-indicator gap + the chart offset
Y``, so a non-zero value in either of those two ordinary boxes is a difference
-- and the panel then printed the patch-first message in the layout where "T"
is exactly what holds the letters.

**DRIVEN ON SCREEN, i1Pro / A4 / "Prioritise chart area" / top margin 10 mm /
Strip-indicator gap 3 mm**, with "T" walked down and the chart regenerated each
time (`~/Desktop/ChromIQ-beta18-proof/beta19-round-1/p2.json`, window
photographs `window/P2-T8.png` and `window/P2-T2.png`):

| "T" | what the panel said |
|---|---|
| 8 | *"With “Prioritise patch size” they are held **11.0** mm from the paper edge by the top margin itself … 5.2 mm of every letter is on the first row of patches … “T” … does not move them in this layout."* |
| 6 | the same sentence, **9.0** mm, 3.2 mm on the patches |
| 4 | the same sentence, **7.0** mm, 1.2 mm on the patches |
| 2 | **no notice at all** |

Its own numbers moved with "T" three times running while the sentence denied
that "T" does anything, and lowering "T" is what cleared it. The same thing
happens with the chart offset Y instead of the gap (`p1.json`, `P1-C`).

So the question "does the renderer hang this band from the top margin?" is
asked of the LAYOUT, once, in `geometry.strip_label_band_is_margin_anchored`,
beside the `if` in `placement` that decides it. B8-241.
"""
from __future__ import annotations

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import text_edge_fit as tef                       # noqa: E402
from workflow.layout_engine import geometry, instruments        # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe         # noqa: E402

_PAPER = (210.0, 297.0)


def _geom(**kw):
    r = LayoutRecipe()
    r.instrument, r.paper, r.dpi = "i1", "A4", 300
    r.use_instrument_margins = False
    r.margin_top = r.margin_bottom = r.margin_left = r.margin_right = 12.0
    r.text_edge_top_mm = 8.0
    for k, v in kw.items():
        setattr(r, k, v)
    return instruments.geom_from_build_kwargs(r.build_kwargs())


# --------------------------------------------------- the layout is asked once
@pytest.mark.parametrize("gap", (0.0, 3.0))
@pytest.mark.parametrize("offy", (0.0, 3.0))
def test_area_first_is_never_called_prioritise_patch_size(gap, offy):
    """The driven state, with both of the two boxes that shift the anchor.

    MUTATION: put the ``abs(a - reserve) > EPS_MM`` inference back into
    `strip_label_overlap` and this goes red for three of the four cases.
    """
    g = _geom(layout_mode="area_first", strip_indicator_gap_mm=gap,
              offset_y_mm=offy)
    assert not geometry.strip_label_band_is_margin_anchored(g), (
        '"Prioritise chart area" was reported as margin-anchored')
    hit = tef.strip_label_overlap(
        10.0, 8.0, 5.0, 0.0,
        gap_mm=float(getattr(g, "strip_indicator_gap", 0.0) or 0.0),
        anchor_mm=geometry.strip_label_leader_top_mm(g),
        margin_anchored=geometry.strip_label_band_is_margin_anchored(g),
        ink_reach_mm=float(g.label_ink_reach_mm),
        tol_mm=tef.edge_tolerance_mm(300))
    assert hit is not None, "the driven state warned on screen and does not here"
    assert hit.binding != tef.LABEL_HELD_BY_TOP_MARGIN, (
        f"gap {gap}, chart offset Y {offy}: the panel would tell the reader "
        f'that "T" does not move the strip letters, in the layout where "T" '
        f"is what holds them")


def test_patch_first_still_names_the_top_margin():
    """The other half: the fix must not take B8-236's new notice away again."""
    g = _geom(layout_mode="patch_first", strip_label_offset_mm=14.0)
    assert geometry.strip_label_band_is_margin_anchored(g)
    hit = tef.strip_label_overlap(
        12.0, 8.0, max(0.0, float(g.label_ink_bottom_mm) - 14.0), 14.0,
        anchor_mm=geometry.strip_label_leader_top_mm(g),
        margin_anchored=geometry.strip_label_band_is_margin_anchored(g),
        ink_reach_mm=float(g.label_ink_reach_mm),
        tol_mm=tef.edge_tolerance_mm(300))
    assert hit is not None and hit.binding == tef.LABEL_HELD_BY_TOP_MARGIN
    assert not hit.from_markers


def test_the_helper_mirrors_the_branch_placement_takes():
    """`strip_label_band_is_margin_anchored` and `strip_label_leader_top_mm`
    have to agree about which of `placement`'s two branches ran.

    MUTATION: return `bool(g.margins_are_law)` from the helper and this goes
    red for both modes.
    """
    for mode in ("area_first", "patch_first"):
        g = _geom(layout_mode=mode, strip_indicator_gap_mm=3.0)
        anchored = geometry.strip_label_band_is_margin_anchored(g)
        top = geometry.strip_label_leader_top_mm(g)
        expect = (float(g.margin_t) + float(g.offset_y)) if anchored else (
            max(0.0, geometry.strip_label_reserve_mm(g)
                + float(g.strip_indicator_gap)) + float(g.offset_y))
        assert top == pytest.approx(expect, abs=1e-9), (
            f"{mode}: the two halves disagree about which branch ran")


def test_the_markers_keep_their_own_wording_behind_an_anchor():
    """An anchor must not swallow the marker/text-edge distinction either.

    With the ruler markers reaching further in than "T", the message names the
    markers; beta 19's inference forced `from_markers` False whenever the
    anchor differed at all, so a gap of 3 mm sent a marker-bound collision to
    the "lower “T”" wording.
    """
    hit = tef.strip_label_overlap(6.0, 1.0, 7.0, 0.0, True, 4.0, 2.0,
                                  gap_mm=3.0, anchor_mm=10.0)
    assert hit is not None
    assert hit.binding == tef.LABEL_HELD_BY_MARKERS, hit.binding
    assert hit.from_markers


def test_an_anchor_does_not_count_the_gap_twice():
    """`reaches_mm` falls back to ``reserve + gap + offset + band`` when no ink
    reach is known, and the anchor already CARRIES the gap.

    MUTATION: keep passing `gap_mm` through when an anchor is given and this
    goes red by exactly the gap.
    """
    hit = tef.strip_label_overlap(6.0, 4.0, 5.0, 0.0, gap_mm=3.0,
                                  anchor_mm=7.0)
    assert hit is not None
    assert hit.reaches_mm == pytest.approx(12.0), (
        "the strip-indicator gap was counted once in the anchor and once "
        "again in the reach")


def test_the_panel_asks_the_layout_and_not_the_numbers():
    """The tab's own helper is wired to the geometry, and the source no longer
    carries the inference it replaced."""
    import inspect
    from ui.tabs import tab_chart
    src = inspect.getsource(tab_chart._label_is_margin_anchored)
    assert "strip_label_band_is_margin_anchored" in src
    call = inspect.getsource(tab_chart.TabChart._engine_text_notes)
    assert "margin_anchored=_label_is_margin_anchored(geom)" in call, (
        "the call site no longer tells `strip_label_overlap` which layout "
        "this is, so it is back to guessing from two numbers")
    law = inspect.getsource(tef.strip_label_overlap)
    assert "abs(a - reserve)" not in law, (
        "the arithmetic guess is back in `strip_label_overlap`")
