"""The strip-label ink probe must see "Q", because the sheet prints one.

A tester, on beta 19, on his own
`CR30-A4-450p-1page-Portrait-w11.0mm-Hexagonal-Straight` at 11 pt, top margin
13.0 mm:

    the strip labels ... hit the patch area edge at T=9,0mm, but warning message
    came at 9,5mm. ... The message says the labels reach 13.6mm down the page.
    Reducing T to 9.0mm when results in reaching 13.1mm, which is within the
    tolerance of 0.2mm set for a warning to appear. ... Thus, it is not the
    threshold that is at fault, but the measurement of the text height that is
    slightly off, so that a warning is not given.

He was right, and his own rendered sheets say by how much. Measured off the two
TIFFs he attached (`~/Desktop/ChromIQ-beta20-proof/knut-beta19/`,
`fault2-tiff-measurement.txt`), reading the black ink of each label column at
200 dpi:

| his sheet | a plain letter inks to | the **Q** inks to |
|---|---|---|
| `test-T9.0mm.tif` | 13.08 mm | **13.72 mm** |
| `testT9.5mm.tif` | 13.59 mm | **14.22 mm** |

The panel predicted 13.1 and 13.6, so it was right to the hundredth **about the
letters with no descender** and 0.64 mm short about the one with one. The patch
area starts at 13.0 mm, so at "T" 9.0 there is 0.72 mm of Q on the first row of
patches and the panel said nothing.

`raster._furniture_reserves_mm` probed the string **"W8"**, and neither glyph
descends. "Q" is the only letter in `A-Z` that does, and `permutation`'s
alphabetic labeller reaches it at the 17th strip; his chart has 18.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow.layout_engine import permutation, raster     # noqa: E402


def _ink_bottom_mm(text: str, size_mm: float, dpi: float = 200.0) -> float:
    """Where *text*'s ink ends below the ascender anchor, in millimetres."""
    from PIL import Image, ImageDraw
    mm2px = dpi / 25.4
    ind_px = max(6, round(size_mm * mm2px))
    font = raster._font(ind_px, raster.DEFAULT_INDICATOR_FONT, False, False)
    probe = Image.new("RGBA", (ind_px * 40, ind_px * 6), (0, 0, 0, 0))
    ImageDraw.Draw(probe).text((ind_px * 2, ind_px * 2), text, font=font,
                               fill=(0, 0, 0, 255), anchor="la")
    bb = probe.getbbox()
    return ((bb[3] - ind_px * 2) / mm2px) if bb else 0.0


def _geom_for(kw):
    """A real i1Pro A4 geometry carrying the extra kwargs in *kw*."""
    from workflow.layout_engine import instruments
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "i1", "A4", "area_first"
    r.show_strip_indicators = True
    return instruments.geom_from_build_kwargs(dict(r.build_kwargs(), **kw))


def _patches_for_strips(strips: int) -> int:
    """A patch count whose chart really has at least *strips* strips.

    **SEARCHED, BECAUSE THE COUNT AND THE GEOMETRY DECIDE EACH OTHER.** Two
    earlier versions of this helper guessed and both tested the wrong chart: a
    flat 500 patches gave four strips, and multiplying by a strip length
    measured at a different count gave five, so the "Q" case was quietly run on
    charts that print no Q. Area-first sizes the patches to the count, so the
    strip length moves when the count does; the only reliable way to ask for
    twenty strips is to hand the real probe a count and look at what comes back.
    """
    want = int(strips)
    n = 64
    for _ in range(14):
        kw = {"paper": "A4", "area_target_count": n}
        got = len(raster._indicator_probe_text(kw, _geom_for(kw)))
        if got >= want:
            return n
        n *= 2
    raise AssertionError(
        f"no patch count up to {n} gives {want} strips on this sheet; the "
        f"probe or the layout has changed shape")


def _probe(strips: int = 0, pattern: str = "") -> str:
    """The probe text for a chart of about *strips* strips, 0 = count unknown."""
    kw = {"paper": "A4"}
    if strips:
        kw["area_target_count"] = _patches_for_strips(strips)
    if pattern:
        kw["strip_pattern"] = pattern
    return raster._indicator_probe_text(kw, _geom_for(kw) if strips else None)


def test_the_probe_text_is_the_labellers_own_output():
    """Not a hand-picked pair of glyphs: the letters the sheet will print.

    "Q" is the seventeenth alphabetic label, so a chart with twenty strips
    prints one and a chart with eight does not. The patch count that produces
    those strip counts is asked of the layout: see `_patches_for_strips`.

    MUTATION: return "W8" from `_indicator_probe_text` and the "Q" assertion
    goes red.
    """
    big = _probe(20)          # comfortably past the seventeenth strip
    assert "Q" in big, (
        "the probe cannot see the only descender an alphabetic strip label has")
    assert big.startswith("ABC"), big
    # …and it is really the labeller's, so a pattern change cannot leave it
    # measuring letters nobody prints.
    label = permutation.make_labeller(permutation.DEFAULT_STRIP_PATTERN)
    assert big == "".join(label(n) for n in range(1, len(big) + 1))
    # A numeric pattern prints digits, none of which descend.
    numeric = _probe(20, "1-999")
    assert set(numeric) <= set("0123456789"), numeric


def test_a_chart_too_small_for_a_Q_is_not_charged_for_one():
    """**THE OTHER DIRECTION, AND IT IS THE ONE THAT COSTS MORE.**

    Over-predicting invents a red notice on a chart that is working. The first
    version of this fix walked the whole A-Z repertoire whatever the chart's
    size, and put *"0.8 mm of every letter is on the first row"* on a rendered
    sheet whose letters end 8.83 mm down with the patches at 9.0 mm.

    MUTATION: drop `_provisional_strip_count` and probe the full repertoire;
    this goes red, and so does the top-is-silent test in
    `test_text_is_never_dropped_on_any_side.py`.
    """
    small = _probe(8)         # no seventeenth strip, so no Q
    assert "Q" not in small, (
        f"an eight-strip sheet has no seventeenth strip, so it prints no Q, "
        f"and the probe measured {small!r}")


def test_an_unknown_patch_count_assumes_no_descender():
    """`LayoutRecipe.build_kwargs()` carries no count, so a geometry built from
    a recipe alone cannot know whether a Q is printed. The safe answer is the
    one that cannot invent a warning.
    """
    blind = raster._indicator_probe_text({})
    assert blind and "Q" not in blind, (
        "with no patch count the probe assumes a descender it cannot know "
        f"about, which is how a false red notice reaches a working sheet: "
        f"{blind!r}")


def test_the_probe_reaches_the_tail_that_a_W8_probe_misses():
    """The 0.64 mm his two sheets both show, in the function that predicts it.

    MUTATION: probe "W8" again and the gap collapses to zero.
    """
    size_mm = 11.0 * 25.4 / 72.0                       # his 11 pt labels
    plain = _ink_bottom_mm("W8", size_mm)
    real = _ink_bottom_mm(_probe(20), size_mm)
    assert real > plain, "the probe sees nothing deeper than a 'W8' does"
    # His sheets: 13.72 - 13.08 and 14.22 - 13.59, both 0.64 mm at 200 dpi.
    assert real - plain == pytest.approx(0.64, abs=0.06), (
        f"the probe is {real - plain:.3f} mm deeper than 'W8'; his rendered "
        f"sheets measure the Q 0.64 mm below the plain letters")


def test_the_reach_a_geometry_reports_carries_the_tail():
    """End to end: the number the panel reads off `Geom`, not just the probe.

    `label_ink_reach_mm` is what `tab_chart` hands `strip_label_overlap` as
    `ink_reach_mm`, so this is the figure his warning is computed from.

    MUTATION: drop `_indicator_probe_text(kw)` back to "W8" in
    `_furniture_reserves_mm` and this goes red.
    """
    _n = _patches_for_strips(20)
    kw = {"dpi": 200, "draw_indicators": True,
          "indicator_size_mm": 11.0 * 25.4 / 72.0,
          "indicator_font": raster.DEFAULT_INDICATOR_FONT,
          "indicator_rotation": 0, "strip_label_offset_mm": 0.0,
          # the count is what tells the probe a Q will be printed
          "paper": "A4", "area_target_count": _n}
    reach = raster._furniture_reserves_mm(
        _geom_for({"paper": "A4", "area_target_count": _n}), kw)[4]
    plain = _ink_bottom_mm("W8", kw["indicator_size_mm"], 200.0)
    assert reach > plain + 0.4, (
        f"the geometry reports the letters reach {reach:.3f} mm, which is the "
        f"em-box answer for a label with no tail ({plain:.3f} mm)")


def test_nothing_lays_a_chart_out_from_the_reach():
    """The reserve is deliberately untouched, so no sheet moves.

    `label_ink_bottom_mm` is what `geometry._top_reserve_for_a_turned_hex`
    shifts the patch block by; `label_ink_reach_mm` and `label_ink_top_mm` are
    predictions for the panel. Making the probe deeper must not move a chart.

    MUTATION: feed the new probe into `label_band` or `ink_bottom` and this
    goes red.
    """
    import inspect
    src = inspect.getsource(raster._furniture_reserves_mm)
    head = src[:src.index("if rot in (90, 270):\n            _tile = ")]
    assert "_indicator_probe_text" not in head, (
        "the label BAND or the em box is now measured from the deep probe, "
        "which moves every turned-honeycomb sheet")
