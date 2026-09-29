"""The expected/measured split must cover its patch, and cover it the same way.

A tester photographed the Measure tab on 2026-09-17 and reported two things
about the split overlay: *"the 6th patch in the first strip has a tiny gap at
the bottom from the split overlay"*, and *"on some patches the diagonal line is
perfect and on other it makes a step"*.

The gap was the fault. ``TiffPreview`` scales the page with
``QPixmap.scaled(..., KeepAspectRatio)``, which returns a whole number of
device pixels on each axis, so the horizontal and vertical ratios are NOT the
same number. ``_draw_cq_overlay`` was handed the horizontal one and used it for
y as well, which slides the overlay grid down the page: measured on screen over
six window sizes, up to 1.37 device pixels at the foot of an A4 page. Wherever
that crossed a rounding boundary the split stopped a screen pixel short of its
patch and the printed colour showed along the edge.

The step was NOT a fault, and
``test_every_box_is_the_size_of_the_patch_it_covers`` is where that is written
down: a corner-to-corner diagonal's stair pattern follows the height of its
box, the box follows the patch's height on screen, and a patch grid with a
fractional pitch lands on 52 screen pixels here and 53 there. The scaled chart
underneath does the same. An overlay that insisted on one height would stop
matching the picture it sits on.

The measurement that found it is on screen
(``scripts/drive_b21_split_overlay_gap.py`` plus
``scripts/analyse_b21_mono_leak.py``): a page whose only colour is in the
patches, the split drawn in two greys, so any coloured pixel left is chart
showing through. Like for like over six window sizes and 462 patches each:
151,383 chart-coloured pixels before the fix and 0 after, of which 37,305
carried at least half the patch's own colour and 0 after. These tests are the
same idea inside the suite, where the page is built here and the canvas the
widget painted is read back.

One of them is here because an adversary round proved the first version of the
fix wrong:
``test_the_same_patches_read_in_any_order_paint_the_same_pixels`` draws the
same patches twice and compares, which is what "draw order cannot matter"
actually means. Asserting it by reading the source does not catch a box that
grew a pixel into its neighbour.
"""
from __future__ import annotations

import inspect

import pytest
from PIL import Image
from PyQt6.QtCore import QPointF, QRect
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
    # The page's own patch grid, exactly as ui/tabs/tab_measure.py hands it
    # over. The overlay needs it to know how much room there is between two
    # patches, and with no grid it deliberately does not grow a box at all.
    p.set_page_patch_boxes({0: _boxes()})
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
        assert want - 1.0 <= length < want + 1.0 + 1e-9, (
            f"a box is {length} px tall where its patch is {want:.2f} px "
            f"at {w}x{h}: a snapped box is the patch's own size to within a "
            f"screen pixel, and the boundary pixel beyond it is repainted at "
            f"the patch's own coverage rather than filled")


@pytest.mark.parametrize("stagger", [0, 1],
                         ids=["aligned", "columns-interleaved"])
@pytest.mark.parametrize("gap_px", [0, 1, 2, 3, 14])
@pytest.mark.parametrize("w,h", [(620, 900), (1000, 880), (470, 400)])
def test_the_same_patches_read_in_any_order_paint_the_same_pixels(
        qapp, tmp_path, gap_px, w, h, stagger):
    """Draw order must not decide which patch owns a pixel.

    The overlay accumulates as strips are read, so the item list arrives in
    whatever order the person swept. If two boxes can overlap by a pixel, the
    seam between them moves with that order, and one of them is wrong.

    The case that matters is a chart whose patches are nearly, but not quite,
    touching. "Spacer size = 0.1 mm" is a real control in Create Chart, and at
    200 dpi ChromIQ's own layout engine then puts most vertical neighbours ONE
    image pixel apart. An adversary round measured that, on the first version
    of this fix, as 2,024 pixels of the window changing between two read
    orders where the build before it changed none. This is that case, in the
    suite, drawn rather than asserted about in prose.
    """
    from ui.tiff_preview import TiffPreview
    pitch = PATCH_H + gap_px
    # `stagger` drops the odd columns by a whole pitch, so that a patch of one
    # column meets a patch of the next at a CORNER and shares no extent with it
    # on either axis. That is the shape an adversary round found the rule blind
    # to, and a regular grid can never make it.
    drop = pitch if stagger else 0
    boxes = [QRect(LEFT + c * PITCH_X,
                   TOP + r * pitch + (drop if c % 2 else 0),
                   PATCH_W, PATCH_H)
             for c in range(COLS) for r in range(ROWS)]
    page = tmp_path / f"order-{gap_px}-{stagger}.tif"
    if not page.exists():
        im = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
        px = im.load()
        for i, b in enumerate(boxes):
            col = PATCH_A if i % 2 == 0 else PATCH_B
            for y in range(b.y(), min(PAGE_H, b.y() + b.height())):
                for x in range(b.x(), min(PAGE_W, b.x() + b.width())):
                    px[x, y] = col
        im.save(page)

    def render(order):
        p = TiffPreview()
        p.resize(w, h)
        p.load_tiff([page])
        qapp.processEvents()
        p.set_page_patch_boxes({0: list(boxes)})
        items = [(b, GREY_EXPECTED, GREY_MEASURED, False) for b in order]
        p.set_patch_overlay(0, items, replace_page=True)
        p.show()
        qapp.processEvents()
        p._update_display()
        qapp.processEvents()
        pm = p._img_label.pixmap()
        img = pm.toImage() if pm is not None else None
        p.close()
        return img

    natural = render(boxes)
    reverse = render(list(reversed(boxes)))
    assert natural is not None and reverse is not None
    assert natural.size() == reverse.size()
    differ = [(x, y) for y in range(natural.height())
              for x in range(natural.width())
              if natural.pixelColor(x, y) != reverse.pixelColor(x, y)]
    assert not differ, (
        f"{len(differ)} pixels change with the order the patches are drawn "
        f"in, at {w}x{h} with a {gap_px} px gap; first ten {differ[:10]}")


@pytest.mark.parametrize("flat_top", [False, True],
                         ids=["pointy", "rotated"])
@pytest.mark.parametrize("w,h", [(620, 900), (900, 1000)])
def test_a_honeycomb_reads_the_same_whatever_order_its_patches_arrive_in(
        qapp, tmp_path, flat_top, w, h):
    """The one path that was never drawn, and the one that depends on order.

    Hexagons INTERLOCK. The fill is antialiased and the seam is stroked ON the
    shared edge, so the lozenge where three apexes meet belongs to whichever
    patch was drawn last, and the patches arrive in the order the person swept.
    An adversary round measured it on the real Measure tab with a real
    SpectroScan chart: 9,356 device pixels at 1200x980 and 4,859 at 900x1000
    changed between two read orders, over 545 separate regions.

    Three earlier rounds had cleared hexagonal charts for draw order. None of
    them had switched the honeycomb on, so all three photographed the
    rectangular branch on a hexagonal chart.
    """
    from ui.tiff_preview import TiffPreview
    boxes = [QRect(LEFT + c * PATCH_W, TOP + r * PATCH_H, PATCH_W, PATCH_H)
             for c in range(COLS) for r in range(ROWS)]
    page = tmp_path / f"hex-{int(flat_top)}.tif"
    if not page.exists():
        im = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
        px = im.load()
        for i, b in enumerate(boxes):
            col = PATCH_A if i % 2 == 0 else PATCH_B
            for y in range(b.y(), min(PAGE_H, b.y() + b.height())):
                for x in range(b.x(), min(PAGE_W, b.x() + b.width())):
                    px[x, y] = col
        im.save(page)

    def render(order):
        p = TiffPreview()
        p.resize(w, h)
        p.load_tiff([page])
        qapp.processEvents()
        p.set_hex_zigzag(True, flat_top=flat_top)
        p.set_page_patch_boxes({0: list(boxes)})
        p.set_patch_overlay(
            0, [(b, GREY_EXPECTED, GREY_MEASURED, False) for b in order],
            replace_page=True)
        p.show()
        qapp.processEvents()
        p._update_display()
        qapp.processEvents()
        pm = p._img_label.pixmap()
        img = pm.toImage() if pm is not None else None
        p.close()
        return img

    a = render(boxes)
    b = render(list(reversed(boxes)))
    assert a is not None and b is not None and a.size() == b.size()
    differ = [(x, y) for y in range(a.height()) for x in range(a.width())
              if a.pixelColor(x, y) != b.pixelColor(x, y)]
    assert not differ, (
        f"{len(differ)} pixels of a honeycomb change with the order its "
        f"patches are drawn in, at {w}x{h}; first ten {differ[:10]}")


def _no_y_maps_with_the_horizontal_scale(src: str) -> None:
    """Every `<something> * s` added to `oy` is a y mapped with the x scale.

    Read as a TREE, not as a string. The string version of this check looked
    for one spelling, `"* s + oy"`, and an adversary round showed it would have
    caught none of the three real cases that reached the shipped build: two
    were written `oy + (...) * s` and the third was `v * s + oy` inside a
    method this check never read. Nineteen hits on the build before those were
    fixed, none on this one.
    """
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(src))
    bad = []

    def _mult_by_s(node) -> bool:
        return (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult)
                and any(isinstance(side, ast.Name) and side.id == "s"
                        for side in (node.left, node.right)))

    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)):
            continue
        sides = (node.left, node.right)
        if not any(isinstance(x, ast.Name) and x.id == "oy" for x in sides):
            continue
        if any(_mult_by_s(x) for x in sides):
            bad.append(ast.unparse(node))
    assert not bad, (
        "a y coordinate is mapped with the page's HORIZONTAL scale:\n  "
        + "\n  ".join(bad))


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
    assert "_dfloor(" not in src and "_dceil(" not in src, (
        "a box edge must be SNAPPED, never grown. Growing it was broken four "
        "times by adversary rounds, the last way being two patches that meet "
        "only at a corner")
    assert "_dsnap(_ty)" in src and "_dsnap(_byf)" in src, (
        "both edges are snapped, which is monotone: the boxes tile and nothing "
        "depends on the order they are drawn in")
    assert "_exposed_for_page(" in src and "_sliver(" in src, (
        "the page's own bleed past a patch edge is covered by repainting the "
        "boundary pixel on the segments that face nothing, not by growing the "
        "box, which was broken four times and cost the spacer a pixel")
    _no_y_maps_with_the_horizontal_scale(src)
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


# ---------------------------------------------------------------------------
# THE GUARDS ABOVE COULD NOT SEE THE MECHANISM THEY WERE WRITTEN FOR.
#
# An adversary round set `_seg = None`, which deletes the ENTIRE sliver the
# fix adds, and this file stayed green: 48 passed. The reason is arithmetic.
# `test_no_chart_pixel_survives_under_the_split` scans
# `range(ceil(top), floor(bottom))`, which is the whole pixels the snapped box
# already covers, so its own ceil and floor exclude the one boundary pixel the
# sliver exists for. `_chart_pixels()`, whose docstring IS this property
# ("still carrying the patches' colour, IN ANY AMOUNT ... a box that covers the
# patch exactly still leaves a coloured hairline"), was never called by
# anything.
#
# The three below are the missing half. Each is proved against the mutation it
# is named for.
# ---------------------------------------------------------------------------

#: A patch is magenta or cyan and everything else on the page is black, white
#: or grey, so the chroma of a pixel IS how much printed ink is in it. A
#: boundary pixel painted by the sliver keeps at most `c * (1 - c)` of the
#: patch, which peaks at a quarter; anything above 40 % is the hairline the
#: tester photographed.
_INK_BUDGET = 102          # 0.4 * 255


def _boundary_ink(img, boxes, border, cw, ch, dpr, page_w, page_h):
    """The worst ink left in the boundary pixels of every box.

    The FULL span, `floor(top)` to `ceil(bottom)`, which is what the older
    guards exclude.
    """
    import math
    bd = border * dpr
    sx = (cw - 2 * bd) / page_w
    sy = (ch - 2 * bd) / page_h
    worst = []
    for b in boxes:
        y0, y1 = math.floor(b.y() * sy + bd), math.ceil((b.y() + b.height()) * sy + bd)
        x0, x1 = math.floor(b.x() * sx + bd), math.ceil((b.x() + b.width()) * sx + bd)
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if not (0 <= xx < img.width() and 0 <= yy < img.height()):
                    continue
                inner = (math.ceil(b.y() * sy + bd) <= yy
                         < math.floor((b.y() + b.height()) * sy + bd)
                         and math.ceil(b.x() * sx + bd) <= xx
                         < math.floor((b.x() + b.width()) * sx + bd))
                if inner:
                    continue                 # the older guards own these
                c = img.pixelColor(xx, yy)
                r, g, bl = c.red(), c.green(), c.blue()
                chroma = max(r, g, bl) - min(r, g, bl)
                if chroma > _INK_BUDGET:
                    worst.append((xx, yy, (r, g, bl), chroma))
    return worst


@pytest.mark.parametrize("w,h", [(520, 700), (560, 820), (620, 900),
                                 (700, 760), (900, 980), (480, 640),
                                 (742, 886), (812, 996)])
def test_the_boundary_pixel_of_every_patch_is_covered_too(qapp, tmp_path, w, h):
    """MUTATION: `_seg = None` (delete the sliver) and this goes red.

    That mutation left every other test in this file green.
    """
    img, (border, cw, ch, dpr) = _canvas(qapp, tmp_path, w, h)
    assert img is not None and img.width() > 0
    left = _boundary_ink(img, _boxes(), border, cw, ch, dpr, PAGE_W, PAGE_H)
    assert not left, (
        f"{len(left)} boundary pixels still carry more than "
        f"{_INK_BUDGET / 255:.0%} of the printed patch at {w}x{h}; "
        f"worst {sorted(left, key=lambda t: -t[3])[:6]}")


#: Patches ONE image pixel apart, which `Spacer size = 0.1 mm` really produces:
#: at 200 dpi that spacer is 0.79 px and the engine records neighbours a single
#: pixel apart. `_exposed_edges` calls such an edge exposed, because it faces no
#: patch, so the sliver is drawn and its probe has one pixel of room.
TIGHT_GAP = 1


def _tight_boxes() -> "list[QRect]":
    return [QRect(LEFT + c * (PATCH_W + TIGHT_GAP),
                  TOP + r * (PATCH_H + TIGHT_GAP), PATCH_W, PATCH_H)
            for c in range(4) for r in range(6)]


def test_the_sliver_never_reads_its_spacer_colour_out_of_a_patch(qapp, tmp_path):
    """Where the sliver looks for the spacer, measured, not argued.

    The sliver repaints the boundary pixel as `c * split + (1 - c) * spacer`
    and reads the spacer from the rendered page just outside the patch. The
    first version looked ONE PIXEL TOO FAR on every side, and on a chart whose
    patches sit one image pixel apart every one of those probes landed inside
    the NEIGHBOURING PATCH: the boundary pixel was then repainted with that
    patch's ink, so the spacer vanished under saturated chart colour. An
    adversary round measured 119 of 154 top probes and 119 of 154 bottom probes
    inside a printed patch on the layout engine's own A4 at 300 dpi, and Basti
    reported the same thing from the app twice: *"for hexes the split overlay
    covers the spacers when they are active"*.

    So this records every coordinate the probe asks for and checks it against
    the patch grid. A probe inside a patch is the fault, whatever colour comes
    back.

    MUTATION: put any of the four probes back to `_rx - 2`, `_rr + 1`,
    `_ry - 2` or `_rb + 1` and this goes red.
    """
    from ui.tiff_preview import TiffPreview
    boxes = _tight_boxes()
    page = tmp_path / "tight-gap-page.tif"
    im = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    px = im.load()
    for i, b in enumerate(boxes):
        col = PATCH_A if i % 2 == 0 else PATCH_B
        for y in range(b.y(), b.y() + b.height()):
            for x in range(b.x(), b.x() + b.width()):
                px[x, y] = col
    im.save(page)

    asked: "list[tuple[int, int]]" = []
    real = TiffPreview._page_colour_at

    def spy(self, ix, iy):
        asked.append((int(ix), int(iy)))
        return real(self, ix, iy)

    p = TiffPreview()
    try:
        p._page_colour_at = spy.__get__(p, TiffPreview)
        p.resize(700, 900)
        p.load_tiff([page])
        qapp.processEvents()
        p.set_page_patch_boxes({0: list(boxes)})
        p.set_patch_overlay(
            0, [(b, GREY_EXPECTED, GREY_MEASURED, False) for b in boxes],
            replace_page=True)
        p.show()
        qapp.processEvents()
        p._update_display()
        qapp.processEvents()
    finally:
        p.close()

    assert asked, (
        "the sliver never asked the page for a spacer colour, so this test "
        "cannot see the fault it was written for")
    inside = [(x, y) for (x, y) in asked
              for b in boxes
              if b.x() <= x < b.x() + b.width()
              and b.y() <= y < b.y() + b.height()]
    assert not inside, (
        f"{len(inside)} of {len(asked)} spacer probes landed INSIDE a printed "
        f"patch, so the split repaints the boundary with a neighbour's ink "
        f"instead of the spacer's colour; first six {inside[:6]}")


#: Window widths where a patch edge lands on an EVEN integer plus a half, which
#: is the only place `round()` and `math.floor(v + 0.5)` disagree. Found by
#: sweeping 400 to 1200 against this fixture's own geometry: 444 puts 48 of the
#: 352 edges there, 486 and 494 put 16, and 410, 418 and 472 put 8.
#:
#: They are pinned because the fault is otherwise almost unreachable. An
#: adversary round swept 1,100 window widths against a real engine chart and
#: found exactly ONE that lands on the phase, and at that one width 1,143
#: device pixels carried printed ink at up to HALF strength. Six sizes chosen
#: for any other reason will not find it, which is how it shipped.
_PHASE_SIZES = [(444, 900), (486, 900), (494, 900), (410, 900),
                (418, 900), (472, 900)]


@pytest.mark.parametrize("w,h", _PHASE_SIZES)
def test_the_sliver_rounds_the_way_dsnap_does(qapp, tmp_path, w, h):
    """The boundary pixel must still be covered where the two roundings differ.

    `_dsnap` is `math.floor(v * dpr + 0.5)` and its docstring says why: Python
    rounds a half to the even side, so alternate patches would snap in opposite
    directions. The first version of `_sliver` then used the builtin `round()`
    for the same decision, two hundred lines below that docstring.

    MUTATION: put `round(dev_edge)` back in `_sliver` and this goes red.
    """
    img, (border, cw, ch, dpr) = _canvas(qapp, tmp_path, w, h)
    assert img is not None and img.width() > 0
    left = _boundary_ink(img, _boxes(), border, cw, ch, dpr, PAGE_W, PAGE_H)
    assert not left, (
        f"{len(left)} boundary pixels carry more than {_INK_BUDGET / 255:.0%} "
        f"of the printed patch at {w}x{h}, where an edge lands on an even "
        f"half; worst {sorted(left, key=lambda t: -t[3])[:6]}")


def test_the_hexagonal_split_always_strokes_its_seam():
    """The seam must be stroked, and stroked UNCONDITIONALLY.

    A hexagonal split is filled as a path and stroked with a cosmetic 1 px pen
    centred ON that path, so half the width lies outside the hexagon. That half
    is the point: it closes the sub-pixel gaps where two antialiased neighbours
    meet, and Knut reported the "separate blobs" look when it was missing.

    **THIS IS A STRUCTURAL TEST, DELIBERATELY, AND HERE IS WHY.** Round 7
    deleted the seam outright and left 667 tests green across eight files, so
    something has to guard it. But the difference it makes is only visible on a
    REAL engine chart at a real fit scale: measured there, deleting it changed
    15,708 device pixels on a tessellating honeycomb and left 139 more paper
    pixels inside a read one. A synthetic lattice in this file cannot reproduce
    it -- one was written, and it passed its own mutation, which is worse than
    having no test at all. So this asserts the shape instead, and the number
    above is where the behaviour is recorded.

    It also pins the UNCONDITIONAL part. Round 6 put a `_hex_has_ring()` in
    front of this append, meaning to spare the paper ring on a honeycomb that
    has one. Round 7 measured what that predicate actually answers: **the
    honeycomb's ORIENTATION, never its ring.** On a pointy-top chart
    `hexagon.stagger_dx` moves every patch by +/- w/4 by its index, so two
    boxes sharing an exact x are a full pitch apart and the vertical gap is
    always positive; on a flat-top chart the stagger is on y and every vertical
    gap is 0. A CR30 pointy honeycomb with NO spacer answered True and a CR30
    rotated honeycomb with a 1.5 mm ring answered False, so the rule was inert
    where it was meant to help and removed the seam where it is needed.

    The ring really is covered by the split, and the cause is B8-318: the
    recorded box is the hexagon's CELL and the printed hexagon inside it is
    smaller by the ring (CR30 A4 at 300 dpi, one box 142 px at every spacer
    width while the ink is 142 / 137 / 125 / 109 px at 0 / 0.5 / 1.5 / 3.0 mm).
    The boxes carry no trace of the ring -- they are byte-identical with the
    spacer on and off -- so a fix has to read it from the chart's recipe.

    MUTATION: wrap the append in any condition, or delete it, and this fails.
    """
    import ast
    import textwrap

    from ui.tiff_preview import TiffPreview

    src = textwrap.dedent(inspect.getsource(TiffPreview._draw_cq_overlay))
    tree = ast.parse(src)
    appends = [n for n in ast.walk(tree)
               if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute)
               and n.func.attr == "append"
               and isinstance(n.func.value, ast.Name)
               and n.func.value.id == "_seams"]
    assert appends, "the hexagonal split no longer strokes a seam at all"

    # …and none of them sits under a test of its own. The `if self._hex_zigzag`
    # branch above is not one: it is what selects the hexagonal path.
    def _guards(node, target):
        out = []
        for n in ast.walk(node):
            if isinstance(n, ast.If):
                for sub in ast.walk(n.test):
                    pass
                if any(t is target for t in ast.walk(n)):
                    out.append(n)
        return out

    hex_branch_tests = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and any(a is appends[0] for a in ast.walk(node)):
            hex_branch_tests.append(ast.dump(node.test))
    inner = [d for d in hex_branch_tests if "_hex_zigzag" not in d
             and "overlay_mode" not in d]
    assert not inner, (
        f"the seam is stroked conditionally again: {inner}. It closes the "
        f"sub-pixel gaps on every hexagonal chart, and the predicate tried "
        f"before answered the honeycomb's orientation rather than its ring")


def _hex_split_extent(qapp, tmp_path, ring_px):
    """How wide the drawn split is on a honeycomb, at a given ring."""
    from ui.tiff_preview import TiffPreview
    from workflow.layout_engine import hexagon
    boxes = [QRect(int(LEFT + c * 60 + hexagon.stagger_dx(60, r)),
                   TOP + r * 50, 60, 64)
             for c in range(4) for r in range(6)]
    path = tmp_path / f"hex-ring-extent-{ring_px}.tif"
    im = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    im.save(path)
    p = TiffPreview()
    try:
        p.resize(700, 900)
        p.load_tiff([path])
        qapp.processEvents()
        p.set_hex_zigzag(True)
        p.set_hex_ring_px(ring_px)
        p.set_page_patch_boxes({0: list(boxes)})
        p.set_patch_overlay(
            0, [(b, GREY_EXPECTED, GREY_MEASURED, False) for b in boxes],
            replace_page=True)
        p.show()
        qapp.processEvents()
        p._update_display()
        qapp.processEvents()
        pm = p._img_label.pixmap()
        img = pm.toImage()
    finally:
        p.close()
    grey = {GREY_EXPECTED.rgb() & 0xFFFFFF, GREY_MEASURED.rgb() & 0xFFFFFF}
    return sum(1 for y in range(img.height()) for x in range(img.width())
               if (img.pixelColor(x, y).rgb() & 0xFFFFFF) in grey)


def test_a_honeycombs_split_is_inset_by_its_ring(qapp, tmp_path):
    """The split follows the PRINTED hexagon, not the cell it sits in.

    A honeycomb built with a spacer takes the ring out of the patch's own area,
    so the RECORDED box does not change: measured, the boxes are byte-identical
    between `spacer_on=False` and `spacer_width=1.5`, 150 of them, in both
    orientations. Only the ink gets smaller. CR30 A4 at 300 dpi, one box at its
    centre row: 142 px at every spacer width, against ink of 142 / 137 / 125 /
    109 px at 0 / 0.5 / 1.5 / 3.0 mm.

    `_patch_hexagon` inscribes in the box, so without the inset the split is
    drawn at CELL size and the ring disappears under it. Basti, with two
    photographs of a rotated CR30 honeycomb with spacers: *"honeycombs with
    spacers. spacers get covered by split overlay"*.

    MUTATION: drop the `inset_px` argument, or ignore it, and this goes red.
    """
    none = _hex_split_extent(qapp, tmp_path, 0.0)
    ringed = _hex_split_extent(qapp, tmp_path, 18.0)
    assert none > 0, "the fixture painted no split at all"
    assert ringed < none * 0.92, (
        f"the split covers the same area with an 18 px ring as without one "
        f"({ringed} against {none}), so it is still drawn at cell size and "
        f"the printed ring is underneath it")


def test_a_tessellating_honeycomb_is_not_inset(qapp, tmp_path):
    """A chart with no spacer has no ring, and must not shrink.

    `hex_ring_px_from_sidecar` answers 0 for it, and 0 must mean "draw the
    hexagon the box describes", or every honeycomb without a spacer loses a
    ring it never had.
    """
    a = _hex_split_extent(qapp, tmp_path, 0.0)
    b = _hex_split_extent(qapp, tmp_path, 0.0)
    assert a == b


def test_the_expected_half_is_clipped_to_its_hexagon_not_intersected():
    """The split's expected half must be CLIPPED to the hexagon.

    Basti saw the fault on screen before it was measured: *"patch i 16 look
    strange i think"*, *"there is a cut in the spacer"*. On a honeycomb with a
    spacer ring, one patch in 240 had a wedge of its own expected colour
    painted on the paper ring. An adversary round measured I16 losing **140
    ring pixels, 5.81 %**, against a 240-patch mean of 1.23 % and a next-worst
    of 2.7 %, and deleting that one fill put it back to 1.95 % while all four
    neighbours stayed byte-identical.

    `QPainterPath.intersected` is boolean algebra and is NOT conditioned to
    keep its result inside either operand. The page's two scales differ, so an
    inset hexagon is irregular, and where a box rounds a pixel short the top
    apex lands on the knife edge of the bounding rect's own top. There the
    intersection rasterises past the hexagon. Measured over all 240 patches of
    that chart at the window's real scales, counting PAINTED pixels outside the
    hexagon:

    | how the half is built | patches painting outside |
    |---|---|
    | `hexp.intersected(tri)` | 3 |
    | `tri.intersected(hexp)` | 2 |
    | intersect an inflated triangle | 4 |
    | **clip to `hexp`, fill `tri`** | **0** |

    Of the 1,891 pixels the clip changes across those 240 patches, 1,850 are
    the broken patch itself; no other moves by more than two.

    **THIS IS STRUCTURAL, AND THAT IS A DELIBERATE CHOICE, NOT A SHORTCUT.**
    Two behavioural versions were written first. One built the clip inside the
    test and checked its own arithmetic, so restoring the intersection left it
    green: the fifth guard in this stream to pass its own mutation. The second
    drove the real widget, and its synthetic honeycomb put the expected colour
    where no hexagon was at all, so it failed for a reason that had nothing to
    do with the fault. The case needs a real chart at a real window scale with
    two different axis scales, which is measured in
    `~/Desktop/ChromIQ-beta21-proof/round-08-the-unchallenged-fixes/` and is
    not reproducible from a fixture in this file.

    MUTATION: put `fillPath(hexp.intersected(tri), c_exp)` back and this fails.
    """
    import ast
    import textwrap

    from ui.tiff_preview import TiffPreview

    src = textwrap.dedent(inspect.getsource(TiffPreview._draw_cq_overlay))
    tree = ast.parse(src)

    # No call anywhere in the overlay may intersect a path with the triangle
    # and fill the result: that is the operation that escapes.
    bad = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "fillPath"
                and node.args):
            a0 = node.args[0]
            if (isinstance(a0, ast.Call)
                    and isinstance(a0.func, ast.Attribute)
                    and a0.func.attr == "intersected"):
                bad.append(ast.dump(a0.func))
    assert not bad, (
        f"{len(bad)} fill(s) of a path INTERSECTION are back in the overlay. "
        f"`intersected` does not keep its result inside either operand, and on "
        f"an inset hexagon whose box rounded a pixel short it paints a wedge "
        f"of the expected colour onto the printed spacer ring: {bad}")

    # …and the expected half is clipped instead.
    clips = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "setClipPath"]
    assert clips, (
        "the expected half is no longer clipped to its hexagon, so nothing "
        "keeps it inside one")
