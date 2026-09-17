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


#: A real honeycomb's columns INTERLOCK: the pitch across is three quarters of
#: a patch, not a patch plus a gap, so column c's x-span overlaps column c+1's.
#: That overlap is the whole reason a rectangle spanning one column's patch
#: bounds can paint over its neighbour, and a fixture without it cannot see the
#: fault (this one could not, until an adversary round mutated the code and
#: watched the test stay green).
HEX_PITCH_X = 40
HEX_PITCH_Y = 60


def _hex_boxes():
    """A honeycomb: columns three quarters of a patch apart, every other one
    dropped by half a row."""
    out = []
    for c in range(COLS):
        off = HEX_PITCH_Y // 2 if c % 2 else 0
        for r in range(ROWS):
            out.append(QRect(LEFT + c * HEX_PITCH_X, TOP + off + r * HEX_PITCH_Y,
                             PATCH_W, PATCH_H))
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


def test_a_blanked_honeycomb_does_not_reach_into_a_read_neighbour(qapp, tmp_path):
    """One column read, every other one blanked. The read column's hexagons
    must come through whole.

    Measured on a real SpectroScan honeycomb before the fix: a read strip drawn
    68 to 90 device pixels wide became 20 to 43, because its unread neighbours
    were blanked with rectangles that span their own patch bounds and those
    bounds overlap a neighbouring column.
    """
    boxes = _hex_boxes()
    read = {i: (i == 2) for i in range(COLS)}
    alone = {i: (i == 2) for i in range(COLS)}
    off = _canvas(qapp, tmp_path, boxes, "hex.tif", hexagonal=True,
                  blanking=False, read_map=alone)
    on = _canvas(qapp, tmp_path, boxes, "hex.tif", hexagonal=True,
                 blanking=True, read_map=read)
    assert off is not None and on is not None
    # The colour that survives the blanking is column 2's, and only column 2's.
    kept = _count(on, _coloured)
    # What column 2 is worth on its own: the whole page's colour divided by the
    # columns that carry it.
    whole = _count(off, _coloured)
    share = whole / COLS
    assert kept > 0, "the read column was wiped out entirely"
    assert kept >= 0.80 * share, (
        f"the blanking ate the read column: {kept} coloured pixels left of "
        f"about {share:.0f}")


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


def _ink_hex_page(tmp_path, boxes, flat_top, name):
    """A honeycomb page drawn the way the ENGINE draws one.

    The recorded box is the hexagon's CELL and the ink is not the same shape:
    measured by flood-filling one hexagon on CR30 charts at three patch sizes,
    the short axis is inset by 9 px at every size and the ink's own aspect is
    4/3 (`HEX_HEIGHT_FACTOR`), so the ink reaches PAST the cell on its long
    axis. A fixture that paints ink inside the boxes cannot see the fault this
    file exists for; this one paints it where the engine does.
    """
    from PIL import ImageDraw
    from workflow.hex_support import HEX_HEIGHT_FACTOR
    from workflow.layout_engine import hexagon
    path = tmp_path / name
    im = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    for b in boxes:
        w = b.width() - 9
        h = w * HEX_HEIGHT_FACTOR
        if flat_top:
            w, h = h, b.height() - 9
        cx = b.x() + b.width() / 2.0
        cy = b.y() + b.height() / 2.0
        pts = hexagon.vertices(cx - w / 2.0, cy - h / 2.0, w, h,
                               flat_top=flat_top)
        dr.polygon([(float(x), float(y)) for x, y in pts], fill=PATCH)
    im.save(path)
    return path


@pytest.mark.parametrize("flat_top", [False, True])
def test_a_blanked_honeycomb_hides_the_ink_past_its_cells(qapp, tmp_path,
                                                          flat_top):
    """No printed ink may survive the blank, apexes included.

    Round 8 measured **8,827 device pixels** of chart ink surviving inside the
    unread columns of a full CR30 honeycomb page, against an all-white control
    of 0, and 5,910 on its ragged second page. It is not about raggedness: it
    is worse on a full page, and a rectangular ragged page is clean. Rounds 6
    and 7 missed it because they tested only rectangular charts.

    The blank covered the cell and the ink reaches past it, so the apexes
    showed. Basti reported the symptom twice: *"when only show measured patches
    is activated it seems the spacers still sometimes show a hairline"*.

    MUTATION: fill the plain cell-sized hexagon again and this goes red.
    """
    boxes = _hex_boxes()
    page = _ink_hex_page(tmp_path, boxes, flat_top, f"ink-hex-{flat_top}.tif")
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    try:
        p.resize(820, 980)
        p.load_tiff([page])
        qapp.processEvents()
        p.set_hex_zigzag(True, flat_top=flat_top)
        p.set_page_patch_boxes({0: list(boxes)})
        p.set_stripe_rects(_strip_rects(boxes))
        # EVERY strip unread, so the whole page must go blank and any ink left
        # is a leak, with no read column to argue about.
        p.set_stripe_read_map({i: False for i in range(len(_col_x(boxes)) + 2)})
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
    left = _count(img, _coloured)
    assert left == 0, (
        f"{left} pixels of printed ink survived the blank on a "
        f"{'flat-top' if flat_top else 'pointy'} honeycomb, so a column the "
        f"user is told is hidden still shows the chart")
