"""The expected/measured split must cover its patch, and cover it the same way.

A tester photographed the Measure tab on 2026-09-17 and reported two things
about the split overlay: *"the 6th patch in the first strip has a tiny gap at
the bottom from the split overlay"*, and *"on some patches the diagonal line is
perfect and on other it makes a step"*.

Both came from one place. ``TiffPreview`` scales the page with
``QPixmap.scaled(..., KeepAspectRatio)``, which returns a whole number of
pixels on each axis, so the horizontal and vertical ratios are NOT the same
number. ``_draw_cq_overlay`` was handed the horizontal one and used it for y as
well, which slides the overlay grid along the page (measured on screen over six
window sizes: up to 1.37 device pixels at the foot of an A4 page). It then
snapped BOTH edges of every box, so a box's size depended on where it fell
between pixels: neighbouring patches of identical size came out 52 and 53
pixels tall, and a taller box rasterises its diagonal differently.

The measurement that found it is on screen
(``scripts/drive_b21_split_overlay_gap.py`` plus
``scripts/analyse_b21_mono_leak.py``): a page whose only colour is in the
patches, the split drawn in two greys, so any coloured pixel left is chart
showing through. 8,289 such pixels before the fix, 0 after. These tests are the
same idea inside the suite, where the page is built here and the canvas the
widget painted is read back.
"""
from __future__ import annotations

import inspect

import pytest
from PIL import Image
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor

#: The page's patches are painted in these, and nothing else on the page or in
#: the widget is: a pixel that still carries one is chart the split missed.
PATCH_A = (255, 0, 255)
PATCH_B = (0, 255, 255)
GREY_EXPECTED = QColor(96, 96, 96)
GREY_MEASURED = QColor(176, 176, 176)

PAGE_W, PAGE_H = 760, 1080
PATCH_W, PATCH_H = 60, 70
PITCH_X, PITCH_Y = 60, 84          # no gap across, a band down (as engine charts are)
COLS, ROWS = 8, 11
LEFT, TOP = 80, 90


def _boxes() -> "list[QRect]":
    return [QRect(LEFT + c * PITCH_X, TOP + r * PITCH_Y, PATCH_W, PATCH_H)
            for c in range(COLS) for r in range(ROWS)]


def _page(tmp_path):
    """A page with colour ONLY in the patches; everything else black or white."""
    path = tmp_path / "split-overlay-page.tif"
    if path.exists():
        return path
    im = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    px = im.load()
    for y in range(TOP - 8, TOP + ROWS * PITCH_Y + 8):      # the bands, black
        for x in range(LEFT, LEFT + COLS * PITCH_X):
            px[x, y] = (0, 0, 0)
    for i, b in enumerate(_boxes()):
        col = PATCH_A if i % 2 == 0 else PATCH_B
        for y in range(b.y(), b.y() + b.height()):
            for x in range(b.x(), b.x() + b.width()):
                px[x, y] = col
    im.save(path)
    return path


def _canvas(qapp, tmp_path, w: int, h: int, same_grey: bool = False,
            with_overlay: bool = True):
    from ui.tiff_preview import TiffPreview
    page = _page(tmp_path)
    p = TiffPreview()
    p.resize(w, h)
    p.load_tiff([page])
    qapp.processEvents()
    exp = GREY_MEASURED if same_grey else GREY_EXPECTED
    if with_overlay:
        p.set_patch_overlay(
            0, [(b, exp, GREY_MEASURED, False) for b in _boxes()],
            replace_page=True)
    p.show()
    qapp.processEvents()
    p._update_display()
    qapp.processEvents()
    pm = p._img_label.pixmap()
    img = pm.toImage() if pm is not None else None
    geom = (p._paint_border, pm.width(), pm.height(),
            float(p._img_label.devicePixelRatioF()))
    p.close()
    return img, geom


def _chart_pixels(img):
    """Every pixel still carrying the patches' colour, in any amount.

    Not just the ones the overlay missed completely. The page is drawn with
    `SmoothTransformation`, so a patch bleeds about a pixel past its own edge,
    and a box that covers the patch exactly still leaves a coloured hairline
    (Basti, on the photograph of the first fix: *"you can still see color from
    the patches bleeding through"*). The overlay is grey and the rest of the
    page is black or white, so anything with a magenta or cyan cast is chart.
    """
    out = []
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            r, g, b = c.red(), c.green(), c.blue()
            if max(r, g, b) - min(r, g, b) <= 20:
                continue
            if (g < r - 15 and g < b - 15) or (r < g - 15 and r < b - 15):
                out.append((x, y, (r, g, b)))
    return out


@pytest.mark.parametrize("w,h", [(520, 700), (560, 820), (620, 900),
                                 (700, 760), (900, 980), (480, 640)])
def test_no_chart_pixel_survives_under_the_split(qapp, tmp_path, w, h):
    """Every whole screen pixel of a printed patch must be covered.

    The patch's place on screen is worked out here from the IMAGE's own grid:
    the page pixmap is scaled to (canvas - 2*border) and drawn at the border,
    so source row `y` lands at `y * scaled_h / page_h`. That is deliberately
    not the overlay's arithmetic, which is the thing under test.
    """
    import math
    img, (border, cw, ch, dpr) = _canvas(qapp, tmp_path, w, h)
    assert img is not None and img.width() > 0
    bd = border * dpr
    sx = (cw - 2 * bd) / PAGE_W
    sy = (ch - 2 * bd) / PAGE_H
    leaks = []
    for b in _boxes():
        for yy in range(math.ceil(b.y() * sy + bd),
                        math.floor((b.y() + b.height()) * sy + bd)):
            for xx in range(math.ceil(b.x() * sx + bd),
                            math.floor((b.x() + b.width()) * sx + bd)):
                if not (0 <= xx < img.width() and 0 <= yy < img.height()):
                    continue
                c = img.pixelColor(xx, yy)
                r, g, bl = c.red(), c.green(), c.blue()
                if max(r, g, bl) - min(r, g, bl) > 20:
                    leaks.append((xx, yy, (r, g, bl)))
    assert not leaks, (
        f"{len(leaks)} pixels inside the printed patches are still showing "
        f"the chart through the split at {w}x{h}; first ten {leaks[:10]}")


@pytest.mark.parametrize("w,h", [(520, 700), (620, 900), (900, 980)])
def test_the_split_never_paints_over_the_spacers(qapp, tmp_path, w, h):
    """And it must not cover what is NOT a patch.

    The first attempt at the fix grew every box by a pixel so that the page's
    own smooth scaling could not bleed past it. Basti rejected it from the
    photograph: *"now you just made the overlay bigger and in turn some
    spacers got smaller and not all of them have the same size"*. The bands
    between the strips' patches are part of the chart and they are what a
    reader uses to see the grid, so the overlay follows the patch and stops.
    """
    import math
    img, (border, cw, ch, dpr) = _canvas(qapp, tmp_path, w, h)
    bd = border * dpr
    sx = (cw - 2 * bd) / PAGE_W
    sy = (ch - 2 * bd) / PAGE_H
    grey = {GREY_EXPECTED.rgb() & 0xFFFFFF, GREY_MEASURED.rgb() & 0xFFFFFF}
    painted = []
    for r in range(ROWS - 1):
        band_top = TOP + r * PITCH_Y + PATCH_H
        band_bot = TOP + (r + 1) * PITCH_Y
        for yy in range(math.ceil(band_top * sy + bd) + 1,
                        math.floor(band_bot * sy + bd) - 1):
            for xx in range(math.ceil((LEFT + 2) * sx + bd),
                            math.floor((LEFT + COLS * PITCH_X - 2) * sx + bd)):
                if not (0 <= xx < img.width() and 0 <= yy < img.height()):
                    continue
                if (img.pixelColor(xx, yy).rgb() & 0xFFFFFF) in grey:
                    painted.append((xx, yy))
    assert not painted, (
        f"the split painted over {len(painted)} pixels of the spacer bands "
        f"at {w}x{h}; first ten {painted[:10]}")


@pytest.mark.parametrize("w,h", [(520, 700), (620, 900), (900, 980)])
def test_every_box_is_the_size_of_the_patch_it_covers(qapp, tmp_path, w, h):
    """The box follows the printed patch, to within one screen pixel.

    Not "every box the same size": a patch grid with a fractional pitch lands
    on 52 screen pixels here and 53 there, and the scaled CHART does exactly
    the same thing. An overlay that insisted on one size would stop matching
    the picture it sits on. What must hold is that no box is more than a pixel
    away from its own patch, and that consecutive boxes meet.

    This is also the honest answer to the second half of the report ("on some
    patches the diagonal line is perfect and on other it makes a step"): the
    stair pattern of a corner-to-corner diagonal follows the box's height, and
    the box's height follows the chart's.
    """
    import math
    img, (border, cw, ch, dpr) = _canvas(qapp, tmp_path, w, h, same_grey=True)
    assert img is not None
    bd = border * dpr
    sy = (ch - 2 * bd) / PAGE_H
    g = GREY_MEASURED.rgb() & 0xFFFFFF

    def is_grey(x, y):
        return (img.pixelColor(x, y).rgb() & 0xFFFFFF) == g

    x = math.floor((LEFT + PATCH_W / 2) * (cw - 2 * bd) / PAGE_W + bd)
    runs, y = [], 0
    while y < img.height():
        if is_grey(x, y):
            s0 = y
            while y < img.height() and is_grey(x, y):
                y += 1
            runs.append((s0, y - s0))
        else:
            y += 1
    want = PATCH_H * sy
    tall = [r for r in runs if r[1] > want * 0.75]
    assert len(tall) == ROWS, (
        f"expected {ROWS} patch boxes down the first strip, saw "
        f"{len(tall)} runs of {[r[1] for r in tall]}")
    for start_y, length in tall:
        assert want <= length < want + 2.0 + 1e-9, (
            f"a box is {length} px tall where its patch is {want:.2f} px "
            f"at {w}x{h}: it must cover the patch and reach no further than "
            f"the two screen pixels the patch's own edges fall in")


def test_both_paint_paths_hand_the_overlay_the_pages_own_vertical_scale():
    """A single scale is the fault. Neither caller may go back to one."""
    from ui.tiff_preview import TiffPreview
    for name in ("_repaint_label", "_repaint_interactive"):
        src = inspect.getsource(getattr(TiffPreview, name))
        call = src[src.index("_draw_cq_overlay("):]
        call = call[:call.index(")\n") + 1]
        assert "height()" in call, (
            f"{name} calls _draw_cq_overlay without a vertical scale taken "
            f"from the drawn page's height:\n{call}")


def test_a_patch_box_is_never_smaller_than_the_chart_patch():
    """The arithmetic, directly: position snaps, size rounds up."""
    import math
    from ui.tiff_preview import TiffPreview
    src = inspect.getsource(TiffPreview._draw_cq_overlay)
    assert "rect.y() * sy + oy" in src, (
        "a patch's top edge must be mapped with the page's VERTICAL scale")
    assert "_dfloor(_ty)" in src and "_dceil(_byf)" in src, (
        "a patch edge with a spacer beyond it must take in the whole screen "
        "pixel the edge falls in, or the smoothly scaled chart shows along "
        "the split")
    assert "_dsnap(_ty) if" in src and "_dsnap(_byf) if" in src, (
        "a patch edge SHARED with another patch must be snapped, so the two "
        "boxes tile and neither depends on the order they are drawn in")
    assert "* s + oy" not in src, (
        "some y coordinate in the overlay is still mapped with the "
        "HORIZONTAL scale, which is the fault this file is about")
    # and the property the snapping is there for
    for dpr in (1.0, 2.0):
        for scale in (0.281741233, 0.332527207, 0.402660218, 0.6650544):
            for origin in range(0, 400):
                for size in (63, 79, 120):
                    top = origin * scale
                    bot = (origin + size) * scale
                    # a FREE edge takes in the pixel the edge falls in
                    near = math.floor(top * dpr + 1e-9)
                    far = math.ceil(bot * dpr - 1e-9)
                    assert near <= top * dpr + 1e-9
                    assert far >= bot * dpr - 1e-9
                    assert (far - near) - (bot - top) * dpr < 2.0 + 1e-9
                    # a SHARED edge is snapped, and both sides snap the same
                    a = math.floor(bot * dpr + 0.5)
                    b = math.floor((origin + size) * scale * dpr + 0.5)
                    assert a == b, (dpr, scale, origin, size)
