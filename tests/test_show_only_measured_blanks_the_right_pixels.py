"""What "Show only measured patches" may paint over, and what it may not.

Three faults were found by driving the real widget in a real window on
2026-09-17 and photographing it. All three were inherited, none had a guard in
the suite, and this file is that guard.

* **A honeycomb was blanked with a RECTANGLE spanning the unread strip's patch
  bounds.** Hexagonal columns INTERLOCK, and a strip's patch bounds already
  carry the +/- quarter-patch zigzag overhang, so the rectangle reached into
  the neighbouring column and painted white over a READ neighbour's lobes.
  Measured on a real SpectroScan honeycomb at 900x1000: a read strip drawn 68
  to 90 device pixels wide with the blanking off, 20 to 43 with it on. Basti:
  *"the colorful patches go down in a straight line although they are
  staggered"*.
* **The blank walked up into the strip labels.** Its clamp fired only
  ``if band_top < min_py``, and every chart today's layout engine builds
  records the label band BELOW the first patch top, so the clamp was inert and
  the pad above went straight into the letters: 687 to 1,415 device pixels of
  label ink turned white on six of the layouts tried.
* **The edge spacers were left showing** in a mode whose whole job is to hide
  an unread column. Basti: *"are edge spacers also hidden by this? they should
  then be i think"*.

The page here is built so that every pixel says which of those it belongs to:
the patches are the only colour, the label bar is the only black above the
grid, and the paper is white.
"""
from __future__ import annotations

import pytest
from PIL import Image
from PyQt6.QtCore import QRect

PATCH = (255, 0, 255)
EDGE_COLOUR = (0, 200, 0)          # the edge-spacer band, so it counts apart
PAGE_W, PAGE_H = 700, 900
PATCH_W, PATCH_H = 54, 60
PITCH_X, PITCH_Y = 66, 72
COLS, ROWS = 6, 9
LEFT, TOP = 70, 150
LABEL_TOP, LABEL_BOT = TOP - 26, TOP - 10     # the strip letters live here
EDGE_SPACER = 8


def _rect_boxes():
    return [QRect(LEFT + c * PITCH_X, TOP + r * PITCH_Y, PATCH_W, PATCH_H)
            for c in range(COLS) for r in range(ROWS)]


#: A REAL honeycomb ZIGZAGS, and a fixture that only offsets whole columns is
#: not one. `hexagon.stagger_dx` steps every patch +/- a quarter of the patch
#: width by its index in the strip, so consecutive patches in a strip sit half
#: a patch apart sideways and the strip walks down the page in a zigzag; the
#: column pitch is then a full patch width and the row pitch is three quarters
#: of the hexagon's height, which is what makes the hexagons TILE.
#:
#: THE FIXTURE THAT WAS HERE DID NOT TILE. It gave every patch in a strip the
#: same x and dropped alternate strips by half a row, so consecutive patches in
#: a strip overlapped each other by a third of their height: ink on top of ink,
#: which no chart has, and a blank that is right on a real chart still left
#: some of it showing. Round 8 had already been caught once by a hex fixture
#: with no interlock; this is the same lesson one layer down.
HEX_PITCH_X = PATCH_W        # column pitch = the patch width (upright hex)
HEX_PITCH_Y = PATCH_H        # row pitch = the recorded box height


def _hex_boxes(flat_top: bool = False):
    """A honeycomb laid out the way `geometry.patch_rects_px` records one.

    THE STAGGER MOVES TO THE OTHER AXIS AND THE OTHER INDEX WHEN THE SHEET IS
    TURNED, and both halves matter (`hexagon.stagger_dy`). Read off two real
    charts' sidecars, both CR30 A4 at 300 dpi:

    * upright: strips `x=475 w=142` a patch apart, patches at x=439 and 510
      alternating down the strip (+/- a quarter patch), row pitch 123 = the
      recorded box height;
    * turned: strips `x=450 w=123`, every patch in a strip at the SAME x and
      the row pitch 142 = the box height, with consecutive STRIPS offset in y.
    """
    from workflow.layout_engine import hexagon
    out = []
    for c in range(COLS):
        dy = hexagon.stagger_dy(PATCH_H, c) if flat_top else 0
        for r in range(ROWS):
            dx = 0 if flat_top else hexagon.stagger_dx(PATCH_W, r)
            out.append(QRect(int(LEFT + c * HEX_PITCH_X + dx),
                             int(TOP + r * HEX_PITCH_Y + dy),
                             PATCH_W, PATCH_H))
    return out


def _hex_strip_rects(boxes):
    """One rect per strip, ON THE STRIP'S AXIS AND ONE PATCH WIDE.

    Read off a real chart's sidecar (CR30 honeycomb, A4, 300 dpi): the strips
    are `x=475 w=142`, `x=616 w=142`, ... one patch wide and a patch apart,
    while the patches themselves sit at x=439 and x=510, sticking out by a
    quarter of a patch either side. The rect is the axis, not the span of the
    zigzag: a rect spanning the zigzag is nearly half again as wide and picks
    up the NEIGHBOURING strip's patches, which is how a fixture can make a
    correct blank look broken.
    """
    out = []
    for c in range(COLS):
        cb = boxes[c * ROWS:(c + 1) * ROWS]
        y0 = min(b.y() for b in cb)
        y1 = max(b.bottom() for b in cb)
        out.append(QRect(LEFT + c * HEX_PITCH_X, y0, PATCH_W, y1 - y0 + 1))
    return out


def _col_x(boxes):
    return sorted({b.x() for b in boxes})


def _strip_rects(boxes):
    """One rect per column, its top ON the column's first patch.

    That is what `engine_strip_rects_from_sidecar` produces for every chart
    today's layout engine builds, and it is the case the old label clamp could
    not see.
    """
    out = []
    for x in _col_x(boxes):
        cb = [b for b in boxes if b.x() == x]
        out.append(QRect(x, min(b.y() for b in cb), PATCH_W,
                         max(b.y() + b.height() for b in cb)
                         - min(b.y() for b in cb)))
    return out


def _page(tmp_path, boxes, name, edge_ink: bool = False):
    path = tmp_path / name
    if path.exists():
        return path
    im = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    px = im.load()
    for y in range(LABEL_TOP, LABEL_BOT):              # the label band, black
        for x in range(LEFT, LEFT + COLS * PITCH_X):
            px[x, y] = (0, 0, 0)
    for b in boxes:                                    # the patches, magenta
        for y in range(b.y(), b.y() + b.height()):
            for x in range(b.x(), b.x() + b.width()):
                px[x, y] = PATCH
    if edge_ink:
        # Ink in the EDGE SPACER band, the strip's own margin above its first
        # patch and below its last. On a real chart this carries the spacer's
        # printed colour; here it is a second colour so it can be counted apart
        # from the patches.
        for x0 in _col_x(boxes):
            cb = [b for b in boxes if b.x() == x0]
            hi = min(b.y() for b in cb)
            lo = max(b.y() + b.height() for b in cb)
            for y in list(range(hi - EDGE_SPACER, hi)) + \
                     list(range(lo, lo + EDGE_SPACER)):
                for x in range(x0, x0 + PATCH_W):
                    px[x, y] = EDGE_COLOUR
    im.save(path)
    return path


def _canvas(qapp, tmp_path, boxes, page_name, *, hexagonal: bool,
            blanking: bool, read_map: "dict[int, bool]", w=820, h=980,
            edge_ink: bool = False):
    from ui.tiff_preview import TiffPreview
    page = _page(tmp_path, boxes, page_name, edge_ink)
    p = TiffPreview()
    p.resize(w, h)
    p.load_tiff([page])
    qapp.processEvents()
    p.set_page_patch_boxes({0: boxes})
    p.set_hex_zigzag(hexagonal)
    p.set_edge_spacer_px(EDGE_SPACER)
    p.set_stripe_rects(_strip_rects(boxes))
    p.set_stripe_read_map(read_map)
    p.set_show_only_measured(blanking)
    p.show()
    qapp.processEvents()
    p._update_display()
    qapp.processEvents()
    pm = p._img_label.pixmap()
    img = pm.toImage() if pm is not None else None
    p.close()
    return img


def _count(img, keep):
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if keep(c.red(), c.green(), c.blue()):
                n += 1
    return n


def _coloured(r, g, b):
    return g < r - 40 and g < b - 40           # magenta in any strength


def _edge(r, g, b):
    """ANY green, not just a bright one.

    The first version of this wanted `g > r + 40`, and the row the blank
    actually leaves showing is mostly DARK, because the smooth-scaled page
    mixes the spacer with whatever lies beyond it. It read 0 while the leak was
    plainly visible in the photograph.
    """
    return g > r + 18 and g > b + 18            # the edge-spacer band


def _ink(r, g, b):
    return max(r, g, b) < 140                  # the label bar


@pytest.mark.parametrize("flat_top", [False, True])
@pytest.mark.parametrize("ring", [0, 9])
def test_a_blanked_honeycomb_does_not_reach_into_a_read_neighbour(qapp, tmp_path,
                                                                  flat_top, ring):
    """One strip read, every other one blanked. The read strip's hexagons must
    come through whole.

    Measured on a real SpectroScan honeycomb before the fix: a read strip drawn
    68 to 90 device pixels wide became 20 to 43, because its unread neighbours
    were blanked with rectangles that span their own patch bounds and those
    bounds overlap a neighbouring column. Basti: *"the colorful patches go down
    in a straight line although they are staggered"*.

    THE RING=0 CASE IS THE ONE THAT BITES. With a ring the blank stops half a
    ring short of the neighbour's ink and could not reach it whatever it did;
    on a honeycomb with no spacer the two inks TOUCH, and the fill deliberately
    overshoots by a pixel to swallow the smooth-scaling fringe, so only the
    subtraction keeps that pixel off the read patch.

    MUTATION: drop the read-neighbour subtraction and the ring=0 case goes red.
    """
    boxes = _hex_boxes(flat_top)
    read_ix = {i for i in range(len(boxes)) if i // ROWS == 2}
    page = _ink_hex_page(tmp_path, boxes, flat_top,
                         f"neighbour-{flat_top}-{ring}.tif", ring=ring,
                         read=read_ix)
    alone = {i: (i == 2) for i in range(COLS)}
    off = _hex_canvas(qapp, tmp_path, boxes, page, flat_top, alone, ring=ring,
                      blanking=False)
    on = _hex_canvas(qapp, tmp_path, boxes, page, flat_top, alone, ring=ring,
                     blanking=True)
    assert off is not None and on is not None
    whole, kept = _count(off, _read_ink), _count(on, _read_ink)
    assert kept > 0, "the read column was wiped out entirely"
    # Measured here, all four cases: 98.3 to 99.0 per cent kept with the
    # read-neighbour subtraction in place, 87.6 to 92.1 with it removed. The
    # rectangle this test was first written against left 20 to 43 pixels of a
    # 68-to-90-pixel strip, so the old 80 per cent bar could not see the
    # subtraction at all.
    assert kept >= 0.95 * whole, (
        f"the blanking ate the read column: {kept} of its {whole} pixels left")


def test_the_blank_never_rises_into_the_strip_labels(qapp, tmp_path):
    boxes = _rect_boxes()
    read = {i: False for i in range(COLS)}     # every column unread
    off = _canvas(qapp, tmp_path, boxes, "rect.tif", hexagonal=False,
                  blanking=False, read_map=read)
    on = _canvas(qapp, tmp_path, boxes, "rect.tif", hexagonal=False,
                 blanking=True, read_map=read)
    assert off is not None and on is not None
    before, after = _count(off, _ink), _count(on, _ink)
    assert after >= before * 0.95, (
        f"the blank wiped strip-label ink: {before} dark pixels before, "
        f"{after} after")


@pytest.mark.parametrize("w,h", [(700, 820), (714, 842), (728, 864),
                                 (742, 886), (756, 908), (770, 930),
                                 (784, 952), (798, 974)])
def test_an_unread_column_hides_its_edge_spacers(qapp, tmp_path, w, h):
    """Both of them, at every window size.

    Basti asked for this directly once the rest of the column was being
    covered: *"are edge spacers also hidden by this? they should then be i
    think"*, and then, on the photographs of the first fix: *"still something
    at the top here. sometimes it seemed at the bottom as well"*.

    THE SIZES ARE THE TEST. The page is drawn with `SmoothTransformation`, so
    the spacer's colour reaches about a device pixel past its own edge, and a
    blank that stops on a fraction leaves that row showing. Whether it does is
    decided by the rounding phase, which is decided by the window: measured on
    screen over eight sizes, four leaked 290 to 317 pixels and four leaked
    none, from the same chart and the same code. One size proves nothing here.

    The band is inked in its own colour, so what survives can be counted apart
    from the patches.
    """
    boxes = _rect_boxes()
    read = {i: False for i in range(COLS)}
    off = _canvas(qapp, tmp_path, boxes, "rect-edge.tif", hexagonal=False,
                  blanking=False, read_map=read, edge_ink=True, w=w, h=h)
    on = _canvas(qapp, tmp_path, boxes, "rect-edge.tif", hexagonal=False,
                 blanking=True, read_map=read, edge_ink=True, w=w, h=h)
    assert off is not None and on is not None
    assert _count(off, _edge) > 0, "the fixture drew no edge-spacer ink"
    assert _count(on, _coloured) == 0, "an unread column still shows a patch"
    left = _count(on, _edge)
    assert left == 0, (
        f"{left} pixels of the edge spacers are still showing in an unread "
        f"column at {w}x{h}, of {_count(off, _edge)}")


RING_COLOUR = (0, 220, 220)      # the printed spacer ring, so it counts apart
READ_COLOUR = (0, 0, 255)        # a read patch's ink, so a leak cannot hide in it


def _ring_ink(r, g, b):
    return g > r + 40 and b > r + 40 and abs(g - b) < 40      # cyan


def _read_ink(r, g, b):
    """STRONG blue only.

    A loose test counts the antialiased blend at every hexagon's outline, all
    over the page, and then reports a read column as eaten when what actually
    changed was one pixel of edge mixing on 54 unread patches somewhere else.
    """
    return b > 180 and r < 90 and g < 90


def _ink_hex_page(tmp_path, boxes, flat_top, name, ring=0, read=()):
    """A honeycomb page drawn the way the ENGINE draws one.

    **`hexagon.vertices` ALREADY REACHES PAST THE SLOT.** It puts the two
    apexes a sixth of the slot beyond it on each side, which is the whole of
    `HEX_HEIGHT_FACTOR`: the printed hexagon for a recorded box IS
    `vertices(box)`, and with a spacer it is that shape inset by half the ring
    (`raster._hexagon_points`, then `hexagon.inset(pts, ring / 2)`, which is
    exactly what the renderer does).

    THE FIXTURE THIS REPLACED GREW THE BOX TO 4/3 AND THEN HANDED IT TO
    `vertices`, WHICH GREW IT AGAIN: 16/9 of the slot, ink painted where no
    chart has any. It agreed with the code it was written beside because both
    made the same mistake, and it therefore demanded a blank up to 44 px too
    big, which is the hole that leaked a saw-tooth of the neighbour's ink down
    every read column (B8-326). A fixture that re-implements the code cannot
    check the code.

    With *ring* the cell is painted in the ring colour first and the ink inside
    it second, so the blank can be asked about both. Patches whose index is in
    *read* are painted in the read colour instead.
    """
    from PIL import ImageDraw
    from workflow.layout_engine import hexagon
    path = tmp_path / name
    im = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    for i, b in enumerate(boxes):
        pts = hexagon.vertices(b.x(), b.y(), b.width(), b.height(),
                               flat_top=flat_top)
        if ring:
            dr.polygon([(float(x), float(y)) for x, y in pts],
                       fill=RING_COLOUR)
            pts = hexagon.inset(pts, ring / 2.0)
        dr.polygon([(float(x), float(y)) for x, y in pts],
                   fill=READ_COLOUR if i in read else PATCH)
    im.save(path)
    return path


def _hex_canvas(qapp, tmp_path, boxes, page, flat_top, read_map, ring=0,
                blanking=True, w=820, h=980):
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    try:
        p.resize(w, h)
        p.load_tiff([page])
        qapp.processEvents()
        p.set_hex_zigzag(True, flat_top=flat_top)
        p.set_hex_ring_px(float(ring))
        p.set_page_patch_boxes({0: list(boxes)})
        p.set_stripe_rects(_hex_strip_rects(boxes))
        p.set_stripe_read_map(read_map)
        p.set_show_only_measured(blanking)
        p.show()
        qapp.processEvents()
        p._update_display()
        qapp.processEvents()
        pm = p._img_label.pixmap()
        return pm.toImage() if pm is not None else None
    finally:
        p.close()


@pytest.mark.parametrize("flat_top", [False, True])
@pytest.mark.parametrize("ring", [0, 9])
def test_a_blanked_honeycomb_hides_every_printed_pixel(qapp, tmp_path,
                                                       flat_top, ring):
    """Every strip unread, so the whole page must go blank: no patch ink and no
    printed spacer ring may survive.

    The RING is the half of this a plain hexagon really does miss, and the only
    half that was ever real. Round 9 re-measured round 8's own case on the real
    app and found the patch ink already at 0 before its fix; what the fix
    bought was the ring, 12,192 device pixels down to 294.

    MUTATION: drop the outward ring growth (fill at `inset_px=0`) and the ring
    case goes red.
    """
    boxes = _hex_boxes(flat_top)
    page = _ink_hex_page(tmp_path, boxes, flat_top,
                         f"ink-hex-{flat_top}-{ring}.tif", ring=ring)
    img = _hex_canvas(qapp, tmp_path, boxes, page, flat_top,
                      {i: False for i in range(COLS)}, ring=ring)
    assert img is not None
    left = _count(img, _coloured)
    assert left == 0, (
        f"{left} pixels of printed ink survived the blank on a "
        f"{'flat-top' if flat_top else 'pointy'} honeycomb, so a column the "
        f"user is told is hidden still shows the chart")
    if ring:
        band = _count(img, _ring_ink)
        assert band == 0, (
            f"{band} pixels of the printed spacer ring survived the blank, "
            f"which is the fine gap this mode exists to remove")


@pytest.mark.parametrize("flat_top", [False, True])
def test_a_read_column_does_not_let_its_unread_neighbours_leak(qapp, tmp_path,
                                                               flat_top):
    """B8-326, the saw-tooth. Alternate columns read; not one pixel of an
    UNREAD patch's ink may survive beside them.

    The hole the blank cuts for a read neighbour has to be that neighbour's
    printed ink and nothing more. Cut it bigger and the interlocking unread
    neighbour's ink inside the hole is never painted over: measured on the real
    app, 62,184 device pixels down one page and 126,577 on a turned chart, a
    ribbon Basti saw unaided (*"the green is bleeding into the patches that
    should be transparent but only on the right"*).

    The read patches are painted a DIFFERENT colour from the unread ones, so a
    surviving pixel cannot be argued about: magenta here is always a leak.

    MUTATION: grow the subtracted hexagon by 20 px and this goes red.
    """
    boxes = _hex_boxes(flat_top)
    read_ix = {i for i in range(len(boxes)) if (i // ROWS) % 2 == 0}
    page = _ink_hex_page(tmp_path, boxes, flat_top,
                         f"leak-hex-{flat_top}.tif", ring=9, read=read_ix)
    read_map = {i: (i % 2 == 0) for i in range(COLS)}
    img = _hex_canvas(qapp, tmp_path, boxes, page, flat_top, read_map, ring=9)
    assert img is not None
    leak = _count(img, _coloured)
    kept = _count(img, _read_ink)
    assert kept > 0, "the read columns were wiped out entirely"
    assert leak == 0, (
        f"{leak} pixels of an UNREAD patch's ink survived beside the read "
        f"columns on a {'flat-top' if flat_top else 'pointy'} honeycomb")


@pytest.mark.parametrize("flat_top", [False, True])
def test_the_blank_asks_for_each_hexagon_once_per_strip(qapp, tmp_path,
                                                        flat_top, monkeypatch):
    """B8-327, the cost, measured as SHAPE rather than as wall time.

    The blank used to build a path for every unread patch and then subtract a
    path for every read patch WITHIN REACH OF THAT PATCH, so the work was the
    product of the two: on a 3,312-patch honeycomb the repaint went from 227 ms
    to 698 ms and a resize from 1,036 to 1,512 ms (round 9, on screen). Doing
    the subtraction once for the whole strip makes it the SUM instead, and
    measured on the same chart and window the repaint came back to 282 ms.

    A stopwatch in the suite would be flaky on a loaded gate; the number of
    hexagons the blank asks for is the same fact and is exact.
    """
    from ui import tiff_preview as tp
    boxes = _hex_boxes(flat_top)
    read_ix = {i for i in range(len(boxes)) if (i // ROWS) % 2 == 0}
    page = _ink_hex_page(tmp_path, boxes, flat_top,
                         f"cost-{flat_top}.tif", ring=9, read=read_ix)
    calls = {"n": 0}
    real = tp.TiffPreview._patch_hexagon

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    p = tp.TiffPreview()
    try:
        p.resize(820, 980)
        p.load_tiff([page])
        qapp.processEvents()
        p.set_hex_zigzag(True, flat_top=flat_top)
        p.set_hex_ring_px(9.0)
        p.set_page_patch_boxes({0: list(boxes)})
        p.set_stripe_rects(_hex_strip_rects(boxes))
        p.set_stripe_read_map({i: (i % 2 == 0) for i in range(COLS)})
        p.set_show_only_measured(True)
        p.show()
        qapp.processEvents()
        p._update_display()
        qapp.processEvents()
        # COUNT ONE REPAINT, NOT THE SETUP. Showing the widget repaints it
        # several times over, so counting across all of that measures Qt's
        # scheduling rather than this code's shape.
        monkeypatch.setattr(tp.TiffPreview, "_patch_hexagon",
                            staticmethod(counting))
        p._update_display()
        qapp.processEvents()
    finally:
        p.close()
    unread = len(boxes) - len(read_ix)
    # One per unread patch, plus the read patches subtracted once per unread
    # STRIP. The product form would be `unread * read_in_reach`, which is an
    # order of magnitude more on this fixture and two on a real A3 honeycomb.
    ceiling = unread + len(read_ix) * (COLS // 2 + 1)
    assert calls["n"] <= ceiling, (
        f"the blank asked for {calls['n']} hexagons; one pass per strip is at "
        f"most {ceiling}, so it is doing the product again")


# ---------------------------------------------------------------------------
# A REAL SHEET, AT A REAL SIZE. Round 10 undid three parts of the blank with
# all 21 tests above still green, and the cause was the fixture rather than the
# tests: it paints a 700x900 page into an 820x980 widget, so the fit scale is
# 1.03 and a DEVICE-pixel margin and an IMAGE-pixel one are the same number; it
# pitches its rows a whole 60 px apart, so the unrounded slot the blank derives
# is an arithmetic no-op; and it paints no band OUTSIDE the field, which is
# where growing by the ring is the only thing that helps.
#
# This one is an A4 sheet at 300 dpi drawn into a 700-pixel-wide widget, a
# scale of 0.28, with a row pitch of 122.76 and an edge band all round.
# ---------------------------------------------------------------------------
A4_W, A4_H = 2480, 3508
SHEET_PATCH_W, SHEET_ROW_PITCH = 141, 122.76
SHEET_RING = 17.7
SHEET_COLS, SHEET_ROWS = 6, 10
SHEET_LEFT, SHEET_TOP = 440, 300
EDGE_COLOUR2 = (0, 220, 220)      # the outer band, counted as the ring is


def _sheet_boxes():
    """Boxes the way `geometry.patch_rects_px` records them on a real sheet:
    integers rounded off a pitch that is not one."""
    from workflow.layout_engine import hexagon
    out = []
    for c in range(SHEET_COLS):
        for r in range(SHEET_ROWS):
            dx = hexagon.stagger_dx(SHEET_PATCH_W, r)
            out.append(QRect(int(SHEET_LEFT + c * SHEET_PATCH_W + dx),
                             int(round(SHEET_TOP + r * SHEET_ROW_PITCH)),
                             SHEET_PATCH_W, int(round(SHEET_ROW_PITCH))))
    return out


def _sheet_strip_rects(boxes):
    out = []
    for c in range(SHEET_COLS):
        cb = boxes[c * SHEET_ROWS:(c + 1) * SHEET_ROWS]
        out.append(QRect(SHEET_LEFT + c * SHEET_PATCH_W,
                         min(b.y() for b in cb), SHEET_PATCH_W,
                         max(b.bottom() for b in cb) - min(b.y() for b in cb) + 1))
    return out


def _sheet_page(tmp_path, boxes, name):
    """The cell in the ring colour, the ink inside it, and a full band of the
    ring colour OUTSIDE the outermost cells: that band is what "Edge spacers"
    prints, and covering it is the only job the outward growth has."""
    from PIL import ImageDraw
    from workflow.layout_engine import hexagon
    path = tmp_path / name
    im = Image.new("RGB", (A4_W, A4_H), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    for b in boxes:
        pts = hexagon.vertices(b.x(), b.y(), b.width(), b.height())
        out = hexagon.inset(pts, -SHEET_RING / 2.0)          # the outer band
        dr.polygon([(float(x), float(y)) for x, y in out], fill=EDGE_COLOUR2)
    for b in boxes:
        pts = hexagon.vertices(b.x(), b.y(), b.width(), b.height())
        dr.polygon([(float(x), float(y)) for x, y in pts], fill=RING_COLOUR)
        ink = hexagon.inset(pts, SHEET_RING / 2.0)
        dr.polygon([(float(x), float(y)) for x, y in ink], fill=PATCH)
    im.save(path)
    return path


def test_a_real_sheet_at_a_real_size_is_blanked_whole(qapp, tmp_path):
    """Every printed pixel of an A4 honeycomb, drawn at the scale a window
    really draws it, with nothing read.

    MUTATIONS, each proven to land where the older fixture could not see them:
    ignore `_hex_ring_px`; make the fringe slack a fixed 3.0 image pixels
    instead of 3.0 device pixels; drop the `slot` argument.
    """
    boxes = _sheet_boxes()
    page = _sheet_page(tmp_path, boxes, "a4-sheet.tif")
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    try:
        p.resize(700, 980)                    # A4 at about 0.28
        p.load_tiff([page])
        qapp.processEvents()
        p.set_hex_zigzag(True, flat_top=False)
        p.set_hex_ring_px(SHEET_RING)
        p.set_page_patch_boxes({0: list(boxes)})
        p.set_stripe_rects(_sheet_strip_rects(boxes))
        p.set_stripe_read_map({i: False for i in range(SHEET_COLS)})
        p.set_show_only_measured(True)
        p.show()
        qapp.processEvents()
        p._update_display()
        qapp.processEvents()
        pm = p._img_label.pixmap()
        img = pm.toImage() if pm is not None else None
    finally:
        p.close()
    assert img is not None
    ink = _count(img, _coloured)
    band = _count(img, _ring_ink)
    assert ink == 0, f"{ink} pixels of printed patch ink survived the blank"
    assert band == 0, (
        f"{band} pixels of the printed ring or the outer band survived the "
        f"blank, which is what growing the fill by the ring is for")
