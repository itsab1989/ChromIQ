"""Turning a strip letter must not make it fainter.

`5924bbbf` moved the strip labels onto a full-page RGBA overlay so the patches
drawn after them could no longer paint them out (Knut's ruling of 2026-09-13
lets the band cross the top margin, and before the overlay 39 px of every
letter was simply erased). That fix is right and it stays. What came with it,
and what this file is about, is that the overlay is ALSO a second blend, and
one of the two label routes could not survive it.

**THE TWO ROUTES ARE NOT THE SAME.** An upright label is drawn with
``ImageDraw.text``, which composites an antialiased glyph onto RGBA correctly.
A TURNED label (the Create Chart layout panel's "Rotation:" combobox, 90 / 180 /
270 degrees) is a pre-rendered RGBA tile pasted in, and ``Image.paste(src, box,
mask)`` lerps ALL FOUR channels: onto a transparent-WHITE ground it mixes the
glyph's black toward white in the RGB channels, and the end-of-page composite
then blends that lightened grey over the page a second time. Non-premultiplied
alpha applied twice, and the antialiased edge of every turned letter comes out
washed out.

Measured on the shipped CR30 A4 preset through `chart.build_chart` with the
label turned 90 degrees: **1,122 pixels of the label band differ, by up to 98
levels of 255**, always lighter -- an edge pixel that should print at 147
printed at 236, and one that should print at 11 printed at 32. Measured through
`render_pages` on the i1 geometry below: a turned letter carried **85.1 %** of
the ink of the same letter upright, and 66 of its 898 pixels did not print at
all.

**THE INVARIANT THIS ASSERTS, AND WHY IT NEEDS NO ARITHMETIC.** PIL rotates by
a multiple of 90 degrees with `transpose`, which is lossless, so a turned strip
letter is the same glyph on its side: the same pixels, in the same proportions.
It must therefore carry exactly the same amount of ink. That is a property of
the picture, not of the implementation, so it cannot be satisfied by a test
that re-implements the compositing it is checking.

The fix is in `raster.render_pages`: the turned tile is COMPOSITED into the
overlay with `Image.alpha_composite` on the tile's own rectangle, instead of
being pasted through itself as a mask. That is the "over" operator this surface
wants, it reproduces the pre-overlay `img.paste(tile, ..., tile)` exactly, and
unlike a verbatim copy it cannot erase whatever the tile's transparent margin
happens to lie over. Zero ink is lost and the upright route is byte-for-byte
unchanged.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import geometry, instruments, raster   # noqa: E402
from workflow.layout_engine.ti1_reader import ColorTarget          # noqa: E402

_DPI = 150
_W_MM, _H_MM = 210.0, 297.0


def _rgb_target(n: int) -> ColorTarget:
    patches = [((float(i * 9 % 100), float(i * 17 % 100), float(i * 5 % 100)),
                (40.0, 45.0, 50.0)) for i in range(n)]
    return ColorTarget(color_rep="iRGB",
                       device_fields=["RGB_R", "RGB_G", "RGB_B"],
                       patches=patches)


def _label_band_ink(rotation: int) -> tuple[int, int]:
    """``(ink, pixels)`` in the strip-label band, for one label rotation.

    The band is everything above the first patch row, so the patches cannot
    contribute and only the letters and their rule are counted. "Ink" is the
    sum of ``255 - level``, which is what a washed-out antialiased edge loses
    and a shifted one does not.
    """
    target = _rgb_target(120)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, _W_MM, _H_MM, 120)
    place = geometry.placement(geom, _W_MM, _H_MM, lay)
    band_rows = int(place.y_of(0) / 25.4 * _DPI)
    assert band_rows > 0, "no label band above the patches to measure"
    res = raster.render_pages(target, lay, geom, seed=7, paper_w_mm=_W_MM,
                              paper_h_mm=_H_MM, dpi=_DPI,
                              indicator_rotation=rotation)
    arr = np.asarray(res.images[0].convert("L"))[:band_rows].astype(int)
    mark = arr < 250
    return int((255 - arr[mark]).sum()), int(mark.sum())


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_a_turned_strip_letter_carries_the_same_ink_as_an_upright_one(rotation):
    upright_ink, upright_px = _label_band_ink(0)
    turned_ink, turned_px = _label_band_ink(rotation)
    assert upright_ink > 0 and upright_px > 0, "the labels drew nothing at all"
    assert (turned_ink, turned_px) == (upright_ink, upright_px), (
        f"turning the strip labels {rotation} degrees changed how much ink "
        f"they print: {turned_ink} against {upright_ink} upright "
        f"({100.0 * turned_ink / upright_ink:.1f} %), over {turned_px} pixels "
        f"against {upright_px}. A rotation by a multiple of 90 degrees is a "
        "lossless transpose, so the same glyph must print the same ink. Less "
        "ink means the turned tile is being blended into the label overlay "
        "instead of copied into it, and then blended over the page a second "
        "time: see this file's docstring, and `raster._lbl_surface`.")


def test_paste_is_the_wrong_operator_for_this_surface_and_composite_is_right():
    """The mechanism, stated once, so a future edit reads the reason.

    `paste(src, box, mask)` interpolates ALL FOUR channels toward the
    destination, which is wrong whenever the destination is not opaque: the
    glyph's black is mixed with the overlay's transparent white before the page
    ever sees it. `alpha_composite` is the "over" operator and reproduces the
    direct paste onto the page exactly.

    The second assertion is the half that matters most: it proves this test can
    still TELL the two apart. A guard that cannot fire is not a guard.
    """
    from PIL import Image
    tile = raster._indicator_tile(
        "AB", raster._font(60, "JetBrains Mono", False, False), 0, 90)
    assert any(0 < a < 255 for a in tile.split()[3].tobytes()), (
        "the tile has no antialiased edge, so this test cannot see the fault")

    page_w, page_h = tile.width + 40, tile.height + 40
    box = (20, 20)
    reg = (box[0], box[1], box[0] + tile.width, box[1] + tile.height)

    def onto_the_page(put) -> np.ndarray:
        page = Image.new("RGB", (page_w, page_h), (255, 255, 255))
        ov = Image.new("RGBA", (page_w, page_h), (255, 255, 255, 0))
        put(ov)
        page.paste(ov, (0, 0), ov)
        return np.asarray(page.convert("L")).astype(int)

    direct = Image.new("RGB", (page_w, page_h), (255, 255, 255))
    direct.paste(tile, box, tile)                     # the pre-overlay route
    truth = np.asarray(direct.convert("L")).astype(int)

    composited = onto_the_page(
        lambda ov: ov.paste(Image.alpha_composite(ov.crop(reg), tile), box))
    pasted = onto_the_page(lambda ov: ov.paste(tile, box, tile))

    assert (composited == truth).all(), (
        "compositing the tile into the overlay no longer reproduces painting "
        "it straight onto the page, so the overlay has stopped being lossless")
    assert not (pasted == truth).all(), (
        "`paste` with the tile as its own mask no longer differs from the "
        "direct paste, so this file can no longer tell the fault from the fix "
        "and the guarantee above is unguarded")
