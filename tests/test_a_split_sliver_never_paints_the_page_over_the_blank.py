"""B8-371 — what the split's boundary sliver is allowed to mix into a pixel.

Basti, 2026-09-18, on a photograph of the real Measure tab: *"in some cases
when there are black spacers and the only show measure patches option is active
there is a black hairline visible on the side of some patches"*, and then,
pointing at the picture: *"bottom of the blue patch black hairline and the patch
below it has a black hairline on top and bottom. of course on others it is
there as well but white which you would not see on a regular chart because
there the background is white as well"*.

He had it exactly. `TiffPreview._draw_cq_overlay` repaints the boundary pixel of
a snapped split box as ``c * split + (1 - c) * ground`` so that the chart's own
spacer keeps its width instead of losing a pixel to the overlay, and it read
that ground off the **printed page**. With "Show only measured patches" on, the
page at that pixel has already been covered by the blank, so the mix put
``1 - c`` of a black `bw` spacer back on top of the blank: one device pixel of
black, hard against the patch, on white.

WHICH edges get a sliver is decided by the rounding (only those the device-pixel
snap left uncovered), which is why the hairline appeared on some patches and not
on their neighbours; WHAT colour it is was decided by this bug. Measured on
screen, chart-mode read, `spacer_mode="bw"`, edge spacers on, 1100x1020: 4,551
device pixels changed on 20 device rows, every one of them lighter, and none
darker, on any of six layouts.

The fixture is a whole chart: six strips, nine rows, a printed spacer band
between every row and an edge-spacer band top and bottom, half the strips
carrying measured splits, and NO strip marked read — which is the state every
whole-chart and patch-by-patch read leaves the preview in (`_on_chart_measured`
and `_on_patch_measured` never touch the strip read map), and the state that put
the hairline on Basti's screen.

The assertion needs no threshold and no tolerance: the same chart is rendered
twice, once with BLACK spacers and once with WHITE ones, and nothing else
changed. The blank covers every spacer on the page, so the two pictures must
come out **pixel-identical**. Before the fix they did not.
"""
from __future__ import annotations

import pytest
from PIL import Image
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor

PAGE_W, PAGE_H = 700, 900
PATCH_W, PATCH_H = 54, 60
PITCH_X, PITCH_Y = 66, 72          # a 12 px spacer band between rows
COLS, ROWS = 6, 9
LEFT, TOP = 70, 150
EDGE_SPACER = 8

#: Both carry a 255 channel, so a sliver mixed with WHITE always has a 255 in
#: it and a sliver mixed with BLACK never can. Nothing here depends on that —
#: the test compares two pictures — but it is why a human reading the failure
#: can tell at a glance which ground a stray pixel came from.
EXPECTED = QColor(255, 230, 0)
MEASURED = QColor(0, 230, 255)
PATCH = (230, 60, 200)


def _boxes():
    return [QRect(LEFT + c * PITCH_X, TOP + r * PITCH_Y, PATCH_W, PATCH_H)
            for c in range(COLS) for r in range(ROWS)]


def _strip_rects(boxes):
    """One rect per column, its top ON the column's first patch.

    What `engine_strip_rects_from_sidecar` produces for every chart today's
    layout engine builds when the chart carries no strip indicators.
    """
    out = []
    for x in sorted({b.x() for b in boxes}):
        cb = [b for b in boxes if b.x() == x]
        out.append(QRect(x, min(b.y() for b in cb), PATCH_W,
                         max(b.y() + b.height() for b in cb)
                         - min(b.y() for b in cb)))
    return out


def _page(tmp_path, boxes, spacer, name):
    """The printed sheet: white paper, coloured patches, and a spacer band
    between every row of a column and at each end of it.

    *spacer* is a colour, or a callable taking the column index — which is how
    ONE column's spacers can be given a colour of their own so the picture says
    which column a surviving pixel came from, with no geometry to get wrong.
    """
    path = tmp_path / name
    if path.exists():
        return path
    im = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    px = im.load()
    _pick = spacer if callable(spacer) else (lambda _c: spacer)
    for _ci, x0 in enumerate(sorted({b.x() for b in boxes})):
        cb = sorted((b for b in boxes if b.x() == x0), key=lambda b: b.y())
        bands = [(cb[k].y() + cb[k].height(), cb[k + 1].y())
                 for k in range(len(cb) - 1)]
        bands.append((cb[0].y() - EDGE_SPACER, cb[0].y()))
        bands.append((cb[-1].y() + cb[-1].height(),
                      cb[-1].y() + cb[-1].height() + EDGE_SPACER))
        _col = _pick(_ci)
        for (y0, y1) in bands:
            for y in range(max(0, y0), min(PAGE_H, y1)):
                for x in range(x0, x0 + PATCH_W):
                    px[x, y] = _col
    for b in boxes:
        for y in range(b.y(), b.y() + b.height()):
            for x in range(b.x(), b.x() + b.width()):
                px[x, y] = PATCH
    im.save(path)
    return path


def _render(qapp, page, boxes, read_map, w, h, *, blanking=True,
            measured_strips=(0, 1, 2)):
    """The Measure tab's own sequence on the real widget, in its own order.

    `tab_measure` loads the chart, hands the preview its patch boxes, its strip
    rects and the engine read map, pushes the split-patch items as they arrive
    and then turns the mode on; that is exactly the order below. Nothing is
    reached into and no private drawing helper is called by hand — the picture
    comes out of the widget's own repaint.
    """
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    p.resize(w, h)
    p.load_tiff([page])
    qapp.processEvents()
    p.set_page_patch_boxes({0: boxes})
    p.set_hex_zigzag(False)
    p.set_edge_spacer_px(EDGE_SPACER)
    p.set_stripe_rects(_strip_rects(boxes))
    p.set_stripe_read_map(read_map)
    cols = sorted({b.x() for b in boxes})
    items = [(b, EXPECTED, MEASURED, False) for b in boxes
             if cols.index(b.x()) in measured_strips]
    p.set_patch_overlay(0, items)
    p.set_show_only_measured(blanking)
    p.show()
    qapp.processEvents()
    p._update_display()
    qapp.processEvents()
    pm = p._img_label.pixmap()
    img = pm.toImage() if pm is not None else None
    p.close()
    return img


def _differing(a, b):
    n = 0
    for y in range(min(a.height(), b.height())):
        for x in range(min(a.width(), b.width())):
            if a.pixelColor(x, y) != b.pixelColor(x, y):
                n += 1
    return n


def _navy(img):
    """The read strip's own spacer colour, wherever it is on the canvas."""
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            r, g, b = c.red(), c.green(), c.blue()
            if b > r + 30 and b > g + 30 and max(r, g, b) < 200:
                n += 1
    return n


#: THE SIZES ARE PART OF THE TEST. A sliver is drawn only where the device-pixel
#: snap left the boundary pixel uncovered, and whether it did is decided by the
#: rounding phase, which the window decides. Measured on screen over eight
#: sizes, the same chart and the same code leaked at five of them and at three
#: did not; one size proves nothing here.
@pytest.mark.parametrize("w,h", [(700, 820), (714, 842), (728, 864),
                                 (742, 886), (756, 908), (770, 930),
                                 (784, 952), (798, 974)])
def test_no_printed_spacer_survives_under_the_blank(qapp, tmp_path, w, h):
    """Black spacers and white spacers must paint the same picture.

    Every strip is unread, so the blank covers every spacer on the sheet; the
    measured splits are drawn on top of it. Nothing that is printed under the
    blank may reach the screen, whatever colour it was printed in.

    MUTATION, run and recorded: replace the sliver's ground with
    `self._page_colour_at(*probe)` again — the line as it shipped — and SEVEN
    of these eight sizes go red, at 1,008 / 1,104 / 1,256 / 1,314 / 1,350 /
    1,386 / 1,660 differing device pixels. The eighth, 784x952, stays green,
    because at that rounding phase the snap covers every boundary pixel and no
    sliver is drawn at all. That is the whole argument for the sweep: a guard
    written at one window size would have been the one that proves nothing.
    """
    boxes = _boxes()
    read = {i: False for i in range(COLS)}
    black = _render(qapp, _page(tmp_path, boxes, (0, 0, 0), "black.tif"),
                    boxes, read, w, h)
    white = _render(qapp, _page(tmp_path, boxes, (255, 255, 255), "white.tif"),
                    boxes, read, w, h)
    assert black is not None and white is not None
    n = _differing(black, white)
    assert n == 0, (
        f"{n} device pixels of the printed sheet reached the screen through "
        f"the blank at {w}x{h}")


def test_a_read_strip_still_shows_its_own_printed_spacers(qapp, tmp_path):
    """The other half of the rule, and the one a careless fix would break.

    A READ strip is never blanked — Knut: read strips keep their real spacers —
    so the ground under its slivers really is the printed page, and it must go
    on being read from there. A fix that simply stopped consulting the page
    would wipe a measured strip's own spacers.

    WHICH COLUMN A PIXEL CAME FROM IS PRINTED INTO THE SHEET, not worked out
    from a rectangle: the read strip's spacers are navy and every other
    column's are black, so the count needs no geometry and cannot pick up a
    neighbour. The first version of this test sliced the canvas at a guessed
    fraction of its width, caught four columns instead of one, and failed on
    correct code.
    """
    boxes = _boxes()
    read = {i: (i == 2) for i in range(COLS)}
    blk = _page(tmp_path, boxes,
                lambda c: (0, 0, 90) if c == 2 else (0, 0, 0), "navy2.tif")
    off = _render(qapp, blk, boxes, read, 756, 908, blanking=False)
    on = _render(qapp, blk, boxes, read, 756, 908, blanking=True)
    assert off is not None and on is not None
    before = _navy(off)
    after = _navy(on)
    assert before > 0, "the fixture has no printed spacer to keep"
    assert after >= before * 0.9, (
        f"the read strip lost its own spacers: {before} navy pixels with the "
        f"mode off, {after} with it on")


def test_the_blank_colour_is_what_the_sliver_mixes_in(qapp, tmp_path):
    """Named separately because it is the mechanism, not the symptom.

    `BLANK_DEBUG_COLOUR` makes the blank paint magenta instead of paper. If the
    sliver mixes with the ground it is actually sitting on, the boundary pixels
    follow the blank to magenta; if it goes on reading the page, they stay
    where they were. This is the hook the fault was finally found with, and it
    is the cheapest statement of what was wrong.
    """
    from ui import tiff_preview
    boxes = _boxes()
    read = {i: False for i in range(COLS)}
    blk = _page(tmp_path, boxes, (0, 0, 0), "black.tif")
    plain = _render(qapp, blk, boxes, read, 742, 886)
    try:
        tiff_preview.BLANK_DEBUG_COLOUR = (255, 0, 255)
        marked = _render(qapp, blk, boxes, read, 742, 886)
    finally:
        tiff_preview.BLANK_DEBUG_COLOUR = None
    assert plain is not None and marked is not None
    assert _differing(plain, marked) > 0, "the debug hook painted nothing"
    # and the hook really is off in every shipped path
    assert tiff_preview.BLANK_DEBUG_COLOUR is None


def test_the_honeycomb_branch_still_leaves_before_the_sliver():
    """`_blank_regions` is UNREACHABLE today, and this is what says so out loud.

    A honeycomb never draws a boundary sliver: the hexagonal arm of the items
    loop ends in `continue` before the sliver code, which is why every
    hexagonal case in the B8-371 sweep measured **0 device pixels changed**
    while the rectangular ones changed thousands. So the region half of
    `_under_blank` is carried but never exercised.

    Deleting it was the alternative and it is the worse one: the day somebody
    gives hexagons a sliver, the fault comes straight back and nothing would
    point at the reason. This test is the pointer. If it fails, the hexagonal
    branch has started reaching the sliver code, and `_blank_regions` is now
    load-bearing and needs a real guard of its own rather than this note.

    MUTATION, proven to land: remove the `continue` from the hexagonal arm.
    """
    import inspect
    import re

    from ui.tiff_preview import TiffPreview

    src = inspect.getsource(TiffPreview._draw_cq_overlay)
    # the hexagonal arm of the per-item loop, and the sliver code after it
    i_hex = src.index("if self._hex_zigzag:", src.index("for rect, c_exp"))
    i_sliver = src.index("_under_blank(band.center())")
    assert i_hex < i_sliver, (
        "this test assumes the hexagonal arm comes before the sliver code")
    arm = src[i_hex:i_sliver]
    assert re.search(r"^\s+continue\s*$", arm, re.M), (
        "the hexagonal arm of the overlay loop no longer leaves before the "
        "boundary sliver is drawn. `_blank_regions` has just become "
        "load-bearing: give it a driven guard of its own, because a honeycomb "
        "can now paint the page back over the blank exactly as B8-371 did")
