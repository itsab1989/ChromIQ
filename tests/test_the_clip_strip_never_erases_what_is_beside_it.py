"""The clip strip's white background must never wipe out the sheet beside it.

THREE FAULTS FROM THE CHALLENGE ROUND OF 2026-09-13, all in the two commits
that built Knut's #182 four-edge specification, and all of them the same shape:
a rule that the round wrote down once and then computed a second time, slightly
differently, somewhere else.

**1. The compositing mask read the raw "Clip" while the rectangle read the
reserve.** `geometry.clip_area_mm` sizes the clip content's rectangle with
whichever of "Clip" and the ruler helper markers' room goes furthest in
(`text_edge_fit.geom_side_text_edge_mm`). `raster.render_page` then recomputed
the overhang for the ink-only compositing MASK from `geom.text_edge_clip_mm`
alone, so the mask was short by exactly the difference. Everything outside the
mask is pasted as the strip's OPAQUE WHITE background, and the strip's comment
says in as many words why that matters: *"a patch wiped to paper white reads as
paper and is then built into the profile"*.

Measured on screen, driving the real window, a 12 mm left band with "Clip" at
0.5 mm and the side markers at 4 + 2 mm: the geometry drew 24.63 mm of overhang,
the mask protected 18.13, and the 6.5 mm between them wiped **94,011 pixels of
the patch block** to bare paper. On the same recipe with the row indicators on,
it wiped the row numbers instead.

**2. The rectangle was built as a subtraction that can go negative.**
`clip_w - inset + over` is the same number as `max(0, clip_w - inset) + over`
while the reserve fits inside the band, and is short by `inset - clip_w` once it
does not. The overhang is measured from a floored room, so the two have to be
floored the same way. Reachable two ways: "Clip" is a 0 to 30 mm box, so 30 mm
on Knut's own 24 mm band left a 5.85 mm rectangle for text needing 11.85 and
printed 2 of its 4 lines; and with the side markers on, any band narrower than
their 7 mm reserve loses that difference. Text cut with nothing said is the
fault `text_edge_fit.clip_text_overhang_mm` records being fixed.

**3. "Lowering Clip would also do it" is false once the markers are binding.**
The reserve is the LARGER of the two, so below the markers' room winding "Clip"
down changes nothing. Measured at 4.0, 2.0, 0.5 and 0.0 mm on a 12 mm band with
the markers at 4 + 2: the clip text's ink stayed at exactly 7.37 mm from the
paper edge every time, while the panel offered "Lowering “Clip” to 0.1 mm would
also do it". That is the same remedy-that-does-not-remedy the round deleted one
branch further down, arriving by the other door.

Everything here is measured on the RENDERED PAGE, not read off a widget.
"""
from __future__ import annotations

import numpy as np

from workflow import text_edge_fit as tef
from workflow.layout_engine import geometry, instruments, presets, raster
from workflow.layout_engine.ti1_reader import ColorTarget

_PAPER_W, _PAPER_H = 210.0, 297.0
_DPI = 200

_CLIP_TEXT = ("chart identification line\n"
              "top margin note for the instrument\n"
              "bottom margin note for the strip end\n"
              "left and right margin notes for the ruler")
_LONG_CLIP_TEXT = _CLIP_TEXT + "\n" + "\n".join(
    f"extra clip line number {i} for the challenge" for i in range(1, 7))


def _target(n: int = 306) -> ColorTarget:
    return ColorTarget(color_rep="iRGB",
                       device_fields=["RGB_R", "RGB_G", "RGB_B"],
                       patches=[((50.0, 50.0, 50.0), (40.0, 45.0, 50.0))
                                for _ in range(n)])


def _recipe(**over) -> presets.LayoutRecipe:
    r = presets.LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
    r.area_method, r.area_cols, r.area_rows = "by_grid", 17, 18
    r.clip_border, r.clip_border_width_mm = True, 12.0
    r.clip_side, r.clip_content_mode = "left", "text"
    r.clip_text, r.clip_flip_180 = _LONG_CLIP_TEXT, False
    r.text_edge_clip_mm = 0.5
    r.margin_top, r.margin_right = 34.0, 6.0
    r.margin_bottom, r.margin_left = 18.0, 12.0
    r.show_row_indicators = False
    r.helper_markers = True
    r.helper_marker_edge_mm, r.helper_marker_len_mm = 4.0, 2.0
    for k, v in over.items():
        setattr(r, k, v)
    return r


def _render(r):
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
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
        helper_markers_sides=r.helper_markers_sides).images[0]


def _is_paper(img) -> np.ndarray:
    a = np.asarray(img.convert("RGB")).astype(int)
    return (a > 250).all(axis=2)


def _wiped_to_paper(r) -> int:
    """Pixels this sheet leaves bare that the same sheet without glyphs inks.

    The control keeps the band and the content MODE and drops only the text, so
    the patch block does not move and nothing but the strip's own doing is
    counted.
    """
    import dataclasses
    g, img = _render(r)
    gc, ctrl = _render(dataclasses.replace(r, clip_text=" "))
    assert abs(g.lbord - gc.lbord) < 1e-6, "the control moved the band"
    return int((_is_paper(img) & ~_is_paper(ctrl)).sum())


# --------------------------------------------------- 1. the opaque paste ----
def test_the_clip_strip_does_not_wipe_the_patches_to_paper() -> None:
    """94,011 pixels of patch block went white, and none may."""
    assert _wiped_to_paper(_recipe()) == 0


def test_the_clip_strip_does_not_wipe_the_row_numbers() -> None:
    """The same paste, one setting over, eats the numbers you read instead."""
    assert _wiped_to_paper(
        _recipe(show_row_indicators=True, margin_left=24.0,
                clip_text=_CLIP_TEXT)) == 0


def test_the_mask_and_the_rectangle_use_the_one_reserve() -> None:
    """The two answers to "how far does it overhang" must be one answer.

    Asked of the arithmetic as well as the sheet, because a renderer that
    happens to agree today is not the same as a renderer that cannot disagree.
    """
    r = _recipe()
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    zone = g.lbord + g.border
    eff = tef.geom_side_text_edge_mm(g)
    assert eff > float(g.text_edge_clip_mm) + 0.05, (
        "this recipe must have the markers, not Clip, as the binding reserve, "
        "or it proves nothing")
    lines = len(raster.clip_text_lines(r.clip_text))
    assert tef.clip_text_overhang_mm(zone, eff, lines, 0.0) > \
        tef.clip_text_overhang_mm(zone, float(g.text_edge_clip_mm),
                                  lines, 0.0) + 0.05


# -------------------------------------------- 2. the rectangle's own width --
def test_the_clip_rectangle_is_never_narrower_than_its_text() -> None:
    """"Clip" is a 0 to 30 mm box and 30 on a 24 mm band used to cut the text."""
    for clip in (0.0, 4.0, 15.0, 24.0, 30.0):
        r = _recipe(clip_border_width_mm=24.0, text_edge_clip_mm=clip,
                    helper_markers=False, clip_text=_CLIP_TEXT,
                    margin_left=40.0)
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        lines = len(raster.clip_text_lines(r.clip_text))
        need = tef.clip_text_needed_mm(lines, 0.0)
        area = geometry.clip_area_mm(g, _PAPER_H, _PAPER_W, lines, 0.0)
        assert area is not None
        assert area[2] + 0.01 >= need, (
            f'Clip {clip} mm on a 24 mm band gives the text {area[2]:.2f} mm '
            f'of rectangle for the {need:.2f} mm it needs, so it is cut')


def test_a_band_narrower_than_the_marker_reserve_still_holds_its_text() -> None:
    """The markers' 7 mm reserve on a 6.5 mm band lost half a millimetre."""
    r = _recipe(clip_border_width_mm=6.5, text_edge_clip_mm=4.0,
                clip_text=_CLIP_TEXT)
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    lines = len(raster.clip_text_lines(r.clip_text))
    need = tef.clip_text_needed_mm(lines, 0.0)
    area = geometry.clip_area_mm(g, _PAPER_H, _PAPER_W, lines, 0.0)
    assert area is not None and area[2] + 0.01 >= need


def test_a_right_hand_band_is_anchored_by_the_reserve() -> None:
    """Its OUTER edge sits at the reserve, whatever the width turns out to be.

    Written as ``paper_w - clip_w - over`` this was right only while the
    reserve fitted inside the band and slid the whole box toward the paper edge
    when it did not.
    """
    for band, clip in ((24.0, 4.0), (24.0, 30.0), (6.5, 4.0), (12.0, 4.0)):
        r = _recipe(clip_side="right", clip_border_width_mm=band,
                    text_edge_clip_mm=clip, margin_right=40.0,
                    margin_left=6.0, clip_text=_CLIP_TEXT)
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        lines = len(raster.clip_text_lines(r.clip_text))
        area = geometry.clip_area_mm(g, _PAPER_H, _PAPER_W, lines, 0.0)
        assert area is not None
        outer = _PAPER_W - (area[0] + area[2])
        want = tef.geom_side_text_edge_mm(g)
        assert abs(outer - want) < 0.01, (
            f'band {band} Clip {clip}: the box ends {outer:.2f} mm from the '
            f'right paper edge and the reserve is {want:.2f} mm')


# ------------------------------------------------ 3. the honest remedy ------
def test_lowering_clip_moves_nothing_once_the_markers_bind() -> None:
    """The premise of the message, measured in ink on four settings."""
    seen = set()
    for clip in (4.0, 2.0, 0.5, 0.0):
        r = _recipe(clip_text=_CLIP_TEXT, text_edge_clip_mm=clip)
        g, img = _render(r)
        a = np.asarray(img.convert("L"))
        hi = int(round(30.0 * _DPI / 25.4))
        cols = np.where((a[:, :hi] < 250).any(axis=0))[0]
        assert len(cols)
        seen.add(round(tef.geom_side_text_edge_mm(g), 2))
    assert seen == {7.0}, (
        f"the reserve should be pinned at the markers' 7.0 mm, got {seen}")


def test_the_panel_does_not_offer_a_clip_it_cannot_reach(qtbot) -> None:
    """No "Lowering “Clip”" sentence while the markers are what is binding."""
    from ui.tabs.tab_chart import TabChart          # noqa: PLC0415
    import inspect                                  # noqa: PLC0415
    src = inspect.getsource(TabChart._engine_text_notes)
    assert "_marker_floor_mm" in src, (
        "the remedy is offered without asking whether lowering Clip can move "
        "the reserve at all")
    i = src.index("_clip_target > 0.05")
    assert "_marker_floor_mm" in src[i:i + 160], (
        "the 'Lowering Clip' branch must be gated on the marker reserve")
