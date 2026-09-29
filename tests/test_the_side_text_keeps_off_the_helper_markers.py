"""The left and right page edges, to Knut's #182 specification of 2026-09-12.

He wrote one rule for both side edges and it had never been implemented at all:

    "The defined text-box-edge […] must be placed with its right text-box-edge
     against the right page edge, in a distance from the page edge defined by
     one of the following settings, whichever go furthest in from the page
     edge: 1. "Clip" in "Text distance from edge" parameter. Example: 4.0mm.
     OR, 2. IF "Print helper markers" and "Sides" checkboxes are both ON, under
     "Ruler helper markers" frame: "Distance from page edge" + "Marker length"
     + 1.0mm. Example: 4.0mm + 2.0mm + 1.0mm = 7.0mm."

Before this, `workflow/text_edge_fit.py` contained the word "helper" exactly
zero times, and the collision was the one he predicted as a consequence of
aligning the side text to the paper edge rather than to the patch area:

    "this has another new consequence, that the text crashes with the position
     of the helper makers defined on the page. This must now be also considered
     when placing the text towards any of the 4 page edges."

Everything here is MEASURED ON THE RENDERED PAGE — the ink, not the widget's
opinion of where it put the ink — because on this project the two have differed
more than once. The helper markers are switched off wherever the measurement is
of the TEXT, so that the dashes' own ink cannot be mistaken for it; the first
run of this measurement reported the text pinned at 4.0 mm on every setting and
that was the markers being measured, not the text.
"""
from __future__ import annotations

import numpy as np
import pytest

from workflow import text_edge_fit as tef
from workflow.layout_engine import geometry, instruments, presets, raster
from workflow.layout_engine.ti1_reader import ColorTarget

_PAPER_W, _PAPER_H = 210.0, 297.0
_DPI = 200

#: Knut's own four-line clip note, shortened but the same shape: what the
#: "ColorMunki-A4-306p-1page-Portrait" preset carries down its 24 mm band.
_CLIP_TEXT = ("chart identification line\n"
              "top margin note for the instrument\n"
              "bottom margin note for the strip end\n"
              "left and right margin notes for the ruler")


def _target(n: int = 306) -> ColorTarget:
    return ColorTarget(color_rep="iRGB",
                       device_fields=["RGB_R", "RGB_G", "RGB_B"],
                       patches=[((50.0, 50.0, 50.0), (40.0, 45.0, 50.0))
                                for _ in range(n)])


def _recipe(**over) -> presets.LayoutRecipe:
    """The preset Knut reported the fault on, as a plain recipe."""
    r = presets.LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
    r.area_method, r.area_cols, r.area_rows = "by_grid", 17, 18
    r.clip_border, r.clip_border_width_mm = True, 24.0
    r.clip_side, r.clip_content_mode = "right", "text"
    r.clip_text = _CLIP_TEXT
    r.text_edge_clip_mm = 4.0
    r.margin_top, r.margin_right = 34.0, 24.0
    r.margin_bottom, r.margin_left = 18.0, 6.0
    r.helper_markers = True
    r.helper_marker_edge_mm, r.helper_marker_len_mm = 4.0, 2.0
    for k, v in over.items():
        setattr(r, k, v)
    return r


def _geom(r):
    return instruments.geom_from_build_kwargs(r.build_kwargs())


def _render(r):
    g = _geom(r)
    lay = geometry.compute(g, _PAPER_W, _PAPER_H, 306)
    return g, raster.render_pages(
        _target(), lay, g, seed=1, randomize=False,
        paper_w_mm=_PAPER_W, paper_h_mm=_PAPER_H, dpi=_DPI,
        clip_content_mode=r.clip_content_mode, clip_text=r.clip_text,
        clip_text_font=r.clip_text_font, clip_text_size_mm=r.clip_text_size_mm,
        clip_flip_180=r.clip_flip_180,
        helper_markers=r.helper_markers,
        helper_marker_edge_mm=r.helper_marker_edge_mm,
        helper_marker_len_mm=r.helper_marker_len_mm,
        helper_markers_top_bottom=r.helper_markers_top_bottom,
        helper_markers_sides=r.helper_markers_sides)


def _text_ink_from_right_mm(img) -> float:
    """How far in from the RIGHT paper edge the clip band's ink begins.

    Only the band's own strip is looked at, so patch ink cannot answer.
    """
    a = np.asarray(img.convert("L"))
    lo = int(round((_PAPER_W - 24.0) * _DPI / 25.4))
    sub = a[:, lo:]
    cols = np.where((sub < 250).any(axis=0))[0]
    assert len(cols), "no ink at all in the clip band"
    return _PAPER_W - (lo + cols[-1]) * 25.4 / _DPI


# --------------------------------------------------------------- the fault --
def test_raising_clip_keeps_moving_the_text_all_the_way(  # noqa: D103
) -> None:
    """Knut's fault report of 2026-09-12, measured in ink.

        "Loading a preset like "ColorMunki-A4-306p-1page-Portrait…", which has
         a 4 line clip-border defined, no longer moves the clip-border text
         further away from the edge when increasing "Clip" in "Text distance
         from edge" parameter. Changing from 4 to 5mm moves the text 1 mm more
         away from the right border, but any higher settings than 5.0mm does
         not move the text at all, even though there is free space between the
         patch area right side and the clip-border text."

    The cause was `clip_content_inset_mm`'s ``min(Clip, band * 0.2)``: his band
    is 24.0 mm, a fifth of it is 4.8, and the reserve stopped there. Measured
    before the fix, with the markers off: 4.13 mm at Clip 4, 4.90 at Clip 5,
    and 4.90 at 5.5, 6, 7, 8, 10 and 15 alike.
    """
    seen = []
    for clip in (4.0, 5.0, 6.0, 8.0, 12.0, 15.0):
        _g, res = _render(_recipe(text_edge_clip_mm=clip, helper_markers=False))
        seen.append(_text_ink_from_right_mm(res.images[0]))
    # Every step must move, and by about what was asked for. The tolerance is
    # half a millimetre because a 200 dpi pixel is 0.127 mm and a glyph's own
    # side bearing is worth a few of them.
    for (c0, d0), (c1, d1) in zip(
            zip((4.0, 5.0, 6.0, 8.0, 12.0), seen),
            zip((5.0, 6.0, 8.0, 12.0, 15.0), seen[1:])):
        assert d1 - d0 == pytest.approx(c1 - c0, abs=0.5), (
            f"raising Clip from {c0} to {c1} mm moved the text "
            f"{d1 - d0:.2f} mm, not {c1 - c0:.2f}; the page-edge reserve is "
            f"capped again")
    assert seen[-1] > seen[0] + 10.0, (
        f"the text barely moved across the whole range: {seen}")


# ------------------------------------------------- the new distance rule ----
def test_the_text_box_keeps_clear_of_the_side_helper_markers() -> None:
    """His worked example: 4.0 + 2.0 + 1.0 = 7.0 mm, on the page."""
    band = 24.0
    off = geometry.clip_area_mm(_geom(_recipe(helper_markers=False)),
                                _PAPER_H, _PAPER_W)
    on = geometry.clip_area_mm(_geom(_recipe()), _PAPER_H, _PAPER_W)
    assert _PAPER_W - (off[0] + off[2]) == pytest.approx(4.0, abs=0.01), (
        "with the markers off the text-box sits at Clip")
    assert _PAPER_W - (on[0] + on[2]) == pytest.approx(7.0, abs=0.01), (
        "with the markers on it must sit at 4.0 + 2.0 + 1.0 = 7.0 mm")
    assert band > 0


def test_the_sides_checkbox_is_what_gates_it() -> None:
    """The side dashes are the only ones down this edge, so "Top/bottom" alone
    reserves nothing here."""
    sides_off = geometry.clip_area_mm(
        _geom(_recipe(helper_markers_sides=False)), _PAPER_H, _PAPER_W)
    assert _PAPER_W - (sides_off[0] + sides_off[2]) == pytest.approx(4.0,
                                                                    abs=0.01)


def test_clip_wins_when_it_is_the_one_that_reaches_further_in() -> None:
    """Whichever goes furthest in, not "the markers always win"."""
    a = geometry.clip_area_mm(_geom(_recipe(text_edge_clip_mm=12.0)),
                              _PAPER_H, _PAPER_W)
    assert _PAPER_W - (a[0] + a[2]) == pytest.approx(12.0, abs=0.01)


def test_the_text_ink_really_clears_the_marker_ink() -> None:
    """MEASURED, because the point of the rule is ink not overlapping ink.

    The side dashes run from `Distance from page edge` to that plus
    `Marker length`, so their innermost ink is at 6.0 mm here and the text may
    not start before 7.0.
    """
    r = _recipe()
    _g, res = _render(r)
    a = np.asarray(res.images[0].convert("L"))
    # A row band down the middle of the page, clear of the top/bottom combs.
    y0, y1 = int(a.shape[0] * 0.35), int(a.shape[0] * 0.65)
    lo = int(round((_PAPER_W - 24.0) * _DPI / 25.4))
    sub = a[y0:y1, lo:]
    cols = np.where((sub < 250).any(axis=0))[0]
    assert len(cols), "no ink in the clip band"
    xs_mm = sorted(_PAPER_W - (lo + c) * 25.4 / _DPI for c in cols)
    marker_inner = r.helper_marker_edge_mm + r.helper_marker_len_mm
    # Nothing may land in the millimetre of clear paper between the markers'
    # inner tip and the text, so no ink at all between 6.0 and 7.0 mm.
    in_gap = [x for x in xs_mm if marker_inner + 0.05 < x < 7.0 - 0.05]
    assert not in_gap, (
        f"ink lands in the clear millimetre the markers are owed: {in_gap[:6]}")


# -------------------------------------------------------- the height rule ---
def test_the_band_runs_between_the_top_and_bottom_reserves_one_edge_at_a_time(
) -> None:
    """Knut's case table, and the two mixed rows are the ones that changed.

    Comment 5649955254, #182, 2026-09-13, in full::

        helper markers off:                     (0+T)  and  (297 - B)
        markers on for top/bottom:
            T smaller than the marker reserve:  (0+R)  and  (297 - B)
            B smaller:                          (0+T)  and  (297 - R)
            both smaller:                       (0+R)  and  (297 - R)

    So each edge takes the larger of its own box and the markers' reach, which
    is `edge_reserve_mm`, the same rule the strip letters and the sheet text
    already keep.

    **THIS SUPERSEDES THE RULE THIS TEST USED TO PIN**, which was his earlier
    "page height minus T and minus B, OR page height minus twice the markers'
    reach, whichever is smallest". That is right when T and B fall on the same
    side of the reserve and wrong in his two mixed rows. A4 at T = 8.0, B = 4.0
    with the markers at 4.0 + 2.0 (R = 7.0) is one of them: the old rule gave
    min(285, 283) = 283 mm inset symmetrically 7.0 mm from each edge, and his
    row gives 8.0 mm down to 290.0 mm, a 282 mm band. The height moved by one
    millimetre and the ANCHOR moved by one as well, which is the half a reader
    could see: the band was centred on the middle of the sheet whatever T and B
    said.
    """
    r = _recipe(text_edge_top_mm=8.0, text_edge_mm=4.0)
    off = geometry.clip_area_mm(_geom(presets.LayoutRecipe(**{
        **{f.name: getattr(r, f.name) for f in _fields(r)},
        "helper_markers": False})), _PAPER_H, _PAPER_W)
    assert off[3] == pytest.approx(285.0, abs=0.01), (
        "with the markers off the height is the page less T and less B")
    assert off[1] == pytest.approx(8.0, abs=0.01), (
        "with the markers off the band starts at T, not at half the slack")
    on = geometry.clip_area_mm(_geom(r), _PAPER_H, _PAPER_W)
    assert on[1] == pytest.approx(8.0, abs=0.01), (
        'T is 8.0 and the markers reach 7.0, so "T" is what holds the top end')
    assert on[3] == pytest.approx(282.0, abs=0.01), (
        "B is 4.0 and the markers reach 7.0, so the markers hold the bottom "
        "end: 297 - 8 - 7 = 282")
    assert tef.side_text_band_mm(
        297.0, 12.0, 4.0) == pytest.approx((12.0, 281.0)), (
        "his own worked example, markers off: centred between 12 and 293")
    assert tef.side_text_band_mm(
        297.0, 12.0, 4.0, helper_markers=True, marker_edge_mm=4.0,
        marker_len_mm=2.0) == pytest.approx((12.0, 278.0)), (
        "the same example with the markers on: between 12 and 290")
    # The symmetric case is unchanged, which is why the old rule survived so
    # long: T = B = 4.0 under a 7.0 mm reserve is still 283.
    assert tef.page_text_height_mm(
        297.0, 4.0, 4.0, helper_markers=True, marker_edge_mm=4.0,
        marker_len_mm=2.0) == pytest.approx(283.0), "his first example"


def test_the_top_bottom_checkbox_is_what_gates_the_height() -> None:
    r = _recipe(text_edge_top_mm=8.0, text_edge_mm=4.0,
                helper_markers_top_bottom=False)
    a = geometry.clip_area_mm(_geom(r), _PAPER_H, _PAPER_W)
    assert a[3] == pytest.approx(285.0, abs=0.01)
    assert a[1] == pytest.approx(8.0, abs=0.01), (
        "with the checkbox off both ends fall back to T and B alone")


# ------------------------------------------- the left edge's row indicators -
def test_the_row_indicators_clear_the_markers_too() -> None:
    """His left-edge table crosses the row indicators with the markers.

        "the left edge of the row indicators will be aligned against the
         clip-border width, or "Clip" in "Text distance from edge", or the
         defined "Distance from page edge" + "Marker length" + 1.0mm,
         whichever is largest."
    """
    base = dict(clip_side="left", clip_border_width_mm=6.0, margin_left=6.0,
                show_row_indicators=True, text_edge_clip_mm=4.0)
    off = _geom(_recipe(helper_markers=False, **base))
    on = _geom(_recipe(**base))
    sides_off = _geom(_recipe(helper_markers_sides=False, **base))
    assert off.row_label_floor == pytest.approx(4.0, abs=0.01)
    assert sides_off.row_label_floor == pytest.approx(4.0, abs=0.01)
    assert on.row_label_floor == pytest.approx(7.0, abs=0.01), (
        "the row indicators are still floored where the markers are printed")
    # …and §R1.5 pays for it out of the left margin, never out of the labels.
    # Not exactly 3 mm: raising the margin changes the usable width, so the
    # patch pitch moves and `raster.row_label_band_mm` re-measures the widest
    # label at the new geometry. Measured here: 13.31 mm to 16.21, so 2.90.
    assert on.margin_l - off.margin_l == pytest.approx(3.0, abs=0.2), (
        f"the left margin did not carry the 3 mm the markers cost: "
        f"{off.margin_l:.2f} to {on.margin_l:.2f}")


def _fields(r):
    import dataclasses
    return dataclasses.fields(r)


# ------------------------------- the notes belong beside the clip text ------
def test_the_chart_note_uses_the_blank_paper_inside_the_clip_band(
        tmp_path) -> None:
    """Knut, #182, 2026-09-12, on where the run's Chart Notes go:

        "Currently, when Run's Chart Notes and/or "Stamp settings used on the
         chart" are used, the text is always placed outside (to the left of)
         the Clip-border width, even if that width is large enough to show free
         space between the patch area right margin and the defined
         "Clip-border content" Text. This is wrong, and the text must be placed
         as described above, to the left of the defined "Clip-border content"
         Text itself."

    Measured on his own preset before the change: the band is 24.0 mm, its four
    lines reach 20.94 mm in from the paper's right edge, so 3.06 mm of the band
    is blank paper, and the note was stamped at 24.20 to 26.36 mm, entirely
    outside the band and hard against the patch block, with that 3 mm unused.

    The note's ink is found by DIFFERENCE against the same page unstamped, so
    what is measured is the note and nothing else.
    """
    from PIL import Image
    from workflow import tiff_metadata
    from workflow.layout_engine.raster import clip_text_lines

    r = _recipe(helper_markers=False)
    g, res = _render(r)
    path = tmp_path / "note.tif"
    res.images[0].save(path, dpi=(_DPI, _DPI))
    before = np.asarray(Image.open(path).convert("L")).copy()

    band = float(g.lbord) + float(g.border)
    lines = clip_text_lines(r.clip_text)
    clip_pt = float(r.clip_text_size_mm or 0.0) * 72.0 / 25.4
    reach = tef.clip_text_reach_mm(band, r.text_edge_clip_mm, len(lines),
                                   clip_pt)
    gap = tef.CLIP_LINE_SPACING * tef.pt_to_mm(
        max(tef.text_floor_pt(clip_pt), tef.text_floor_pt(0.0)))
    assert band - reach > 1.0, (
        f"the premise failed: the {band:.1f} mm band's text reaches "
        f"{reach:.2f} mm, so there is no blank paper inside it to use")

    tiff_metadata.stamp_chart_metadata(
        [path], ["Run 1 Chart Notes, printed down the right edge"],
        text_edge_mm=r.text_edge_clip_mm, clip_band_mm=band, size_pt=0.0,
        clip_reach_mm=reach, gap_mm=gap)
    after = np.asarray(Image.open(path).convert("L"))
    cols = np.where((before != after).any(axis=0))[0]
    assert len(cols), "no note was printed at all"
    note_outer = _PAPER_W - cols[-1] * 25.4 / _DPI      # nearest the page edge

    assert note_outer < band - 0.05, (
        f"the note starts {note_outer:.2f} mm in from the paper edge, outside "
        f"the {band:.1f} mm clip band, with {band - reach:.2f} mm of blank "
        f"paper inside it going unused")
    assert note_outer >= reach - 0.5, (
        f"the note at {note_outer:.2f} mm is printed over the clip border's "
        f"own text, which reaches {reach:.2f} mm")
