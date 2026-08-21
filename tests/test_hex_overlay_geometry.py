"""Hexagonal charts: the ink lands on the paper, and the overlay lands on the ink.

Four faults, all in the same family — code that compensates for the hexagon's
±¼-width row stagger, or for its apex overhang, in a place that already had it:

* the overhang reserve (``hxeh``/``hxew``) was computed from ``pscale`` and never
  revisited when ``patch_w``/``patch_h`` set the size directly;
* ``placement()`` centred the block on the SLOTS while the apexes overshoot both
  ends, so the whole overhang landed at the bottom — inside the bottom margin,
  and off the sheet entirely at large patches with a small border;
* ``margin_inspector`` added the stagger that ``patch_rects_px`` already records;
* ``_apply_hex_stagger`` did the same to the patch boxes the Measure tab loads,
  so the patch-by-patch ring and the click target sat a quarter-patch off every
  hexagon (seen on screen: the ring between two patches).

The last two were correct when written. ``patch_rects_px`` began recording the
stagger on 2026-08-13 and turned both into double-counts.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import geometry, instruments  # noqa: E402

A4 = (210.0, 297.0)


def _hex_geom(w_mm: float, border: float = 6.0):
    return instruments.build("SS", pscale=w_mm / 7.0, hflag=True, border=border)


# ---------------------------------------------------------------------------
# the ink lands on the paper
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("w_mm", [7.0, 12.0, 16.0, 20.0, 30.0, 40.0])
@pytest.mark.parametrize("border", [0.0, 2.0, 6.0, 10.0])
def test_hexagon_ink_stays_on_the_paper(w_mm, border):
    """Nothing asserted this at all, which is how the bottom apex came to hang
    5.11 mm off a 40 mm chart with no border. The apexes overshoot the slot
    block by hxeh at BOTH ends; the page has to hold all of it."""
    g = _hex_geom(w_mm, border)
    per = geometry.patches_per_sheet(g, *A4)
    if not per:
        pytest.skip(f"{w_mm} mm does not fit this page")
    lay = geometry.compute(g, *A4, per)
    pl = geometry.placement(g, *A4, lay)
    top = pl.y0_first - g.hxeh
    bottom = pl.y0_first + lay.pprow * (g.plen + g.pspa) - g.pspa + g.hxeh
    assert top >= 0.0, f"the top apex is {-top:.2f} mm off the sheet"
    assert bottom <= A4[1], f"the bottom apex is {bottom - A4[1]:.2f} mm off the sheet"


@pytest.mark.parametrize("w_mm", [12.0, 20.0, 30.0])
@pytest.mark.parametrize("border", [2.0, 6.0])
def test_the_apex_overhang_is_shared_top_and_bottom(w_mm, border):
    """It used to be centred on the slots, so both apexes' worth of overhang
    fell below the block: at 20 mm with a 2 mm border the lower apex sat
    0.66 mm from the page edge, inside the margin the user asked for."""
    g = _hex_geom(w_mm, border)
    per = geometry.patches_per_sheet(g, *A4)
    lay = geometry.compute(g, *A4, per)
    pl = geometry.placement(g, *A4, lay)
    bottom_clear = A4[1] - (pl.y0_first + lay.pprow * (g.plen + g.pspa)
                            - g.pspa + g.hxeh)
    assert bottom_clear >= border - 0.01, (
        f"the bottom apex leaves {bottom_clear:.2f} mm, less than the "
        f"{border:.0f} mm margin asked for")


def test_a_square_spectroscan_chart_is_unaffected():
    """The counterweight: no apexes, so nothing to share."""
    g = instruments.build("SS", pscale=12 / 7.0, hflag=False, border=6.0)
    assert g.hxeh == 0.0
    per = geometry.patches_per_sheet(g, *A4)
    lay = geometry.compute(g, *A4, per)
    pl = geometry.placement(g, *A4, lay)
    assert pl.y0_first >= 6.0


# ---------------------------------------------------------------------------
# the overlay lands on the ink
# ---------------------------------------------------------------------------
def _build_hex_chart(tmp_path, w_mm=12.0, n=120):
    """A real engine-built hex chart, with the sidecar the app reads."""
    from workflow.layout_engine import chart as le_chart
    ti1 = tmp_path / "p.ti1"
    lines = ["CTI1", "", 'DESCRIPTOR "x"', 'ORIGINATOR "x"', 'KEYWORD "SAMPLE_LOC"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    lines += [f"{i+1} 78.0 78.0 78.0 40 45 50" for i in range(n)]
    lines += ["END_DATA", ""]
    ti1.write_text("\n".join(lines))
    stem = tmp_path / "Chart"
    le_chart.build_chart(ti1, stem, instrument="SS", hflag=True,
                         pscale=w_mm / 7.0, paper="A4", border=6.0, dpi=200,
                         randomize=False)
    strips = json.loads(stem.with_suffix(".strips.json").read_text())
    (tmp_path / "Chart.channels.json").write_text(json.dumps({
        "ink_channels": ["r", "g", "b"],
        "layout": {"engine": "chromiq", "dpi": 200, "paper_mm": list(A4),
                   "patches": strips["patches"],
                   "recipe": {"instrument": "SS", "hflag": True}}}))
    return stem, strips["patches"]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("w_mm", [10.0, 12.0, 20.0])
def test_the_loaded_boxes_are_the_recorded_boxes(qapp, tmp_path, w_mm):
    """The Measure tab shifted every loaded box by ±¼ width to "match the drawn
    hexagon", because the recorded boxes used to hold only the slot x. They have
    held the drawn position since 2026-08-13, so the shift moved the ring and
    the click target off the patch they name — on every row of every hex chart.
    """
    stem, recorded = _build_hex_chart(tmp_path, w_mm)
    from ui.tabs.tab_measure import patch_boxes_from_sidecar
    boxes = patch_boxes_from_sidecar(stem.with_suffix(".ti2"), 1)[0]
    assert boxes, "no boxes were loaded at all"
    on_page = {r["loc"]: r for r in recorded if r["page"] == 0}
    assert set(boxes) == set(on_page)
    off = [(loc, boxes[loc].x() - on_page[loc]["x"]) for loc in on_page
           if boxes[loc].x() != on_page[loc]["x"]
           or boxes[loc].y() != on_page[loc]["y"]]
    assert not off, f"{len(off)} boxes moved, e.g. {off[:3]}"


def test_a_non_hex_chart_is_not_shifted_either(qapp, tmp_path):
    """The shift was gated on the chart being hexagonal; keep the guarantee for
    the other layouts explicit so a future 'fix' cannot reintroduce it there."""
    from workflow.layout_engine import chart as le_chart
    from ui.tabs.tab_measure import patch_boxes_from_sidecar
    ti1 = tmp_path / "p.ti1"
    lines = ["CTI1", "", 'DESCRIPTOR "x"', 'ORIGINATOR "x"', 'KEYWORD "SAMPLE_LOC"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             "NUMBER_OF_SETS 60", "BEGIN_DATA"]
    lines += [f"{i+1} 78.0 78.0 78.0 40 45 50" for i in range(60)]
    lines += ["END_DATA", ""]
    ti1.write_text("\n".join(lines))
    stem = tmp_path / "Flat"
    le_chart.build_chart(ti1, stem, instrument="i1", paper="A4", border=6.0,
                         dpi=200, randomize=False)
    strips = json.loads(stem.with_suffix(".strips.json").read_text())
    (tmp_path / "Flat.channels.json").write_text(json.dumps({
        "ink_channels": ["r", "g", "b"],
        "layout": {"engine": "chromiq", "dpi": 200, "paper_mm": list(A4),
                   "patches": strips["patches"], "recipe": {"instrument": "i1"}}}))
    boxes = patch_boxes_from_sidecar(stem.with_suffix(".ti2"), 1)[0]
    rec = {r["loc"]: r for r in strips["patches"] if r["page"] == 0}
    assert all(boxes[loc].x() == rec[loc]["x"] for loc in rec)


def test_the_highlight_takes_the_patch_shape_on_a_hex_chart(qapp):
    """A rectangle over a hexagon covers the four corners, which belong to the
    neighbours — on the one chart type where the app is telling the user which
    patch to put the instrument on."""
    from PyQt6.QtCore import QPointF, QRect
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    box = QRect(100, 100, 96, 84)
    hexp = p._patch_hexagon(box, 1.0, 0.0, 0.0)
    # a hexagon reaches the flat sides but never the box's corners
    for corner in (box.topLeft(), box.topRight(),
                   box.bottomLeft(), box.bottomRight()):
        assert not hexp.contains(QPointF(corner)), (
            f"the ring covers {corner}, which belongs to a neighbour")
    # the centre, and the flat sides, are inside
    assert hexp.contains(QPointF(box.center()))
    # …and it does reach past the top and bottom, where the apexes are
    br = hexp.boundingRect()
    assert br.top() < box.top() and br.bottom() > box.bottom()
    assert abs(br.left() - box.left()) <= 1


def test_one_patch_per_column_is_not_mistaken_for_a_legacy_chart(qapp, tmp_path):
    """The legacy fingerprint is a column of two or more patches sharing one x.
    Counting distinct x alone called a MODERN chart legacy whenever a column
    held a single patch — real on short or roll media with a big hexagon — and
    shifted every box on it."""
    from PyQt6.QtCore import QRect
    from ui.tabs.tab_measure import _apply_hex_stagger
    import ui.tabs.tab_measure as tm

    w = 40
    pages = [{f"{chr(65+i)}1": QRect(100 + i * w, 50, w, 34) for i in range(6)}]
    before = {k: QRect(v) for k, v in pages[0].items()}
    tm.chart_is_hexagonal = lambda *_a, **_k: True          # force the hex path
    try:
        _apply_hex_stagger(tmp_path / "chart.ti2", pages)
    finally:
        import importlib
        importlib.reload(tm)
    assert pages[0] == before, "a one-patch column was treated as unstaggered"


def test_clicking_a_hexagon_selects_that_hexagon(qapp):
    """The box and the hexagon are different shapes: the box's corners lie
    outside the patch, and the apexes lie outside the box. Hit-testing the box
    meant a click on a drawn apex selected the neighbour, and a corner click
    selected a patch whose ink is not under the pointer."""
    from PyQt6.QtCore import QRect
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    b = QRect(100, 100, 96, 84)
    cx, cy = b.x() + b.width() // 2, b.y() + b.height() // 2
    assert p._in_hexagon(b, cx, cy), "the centre is not in its own patch"
    # the four box corners belong to the neighbours
    for x, y in ((b.left(), b.top()), (b.right(), b.top()),
                 (b.left(), b.bottom()), (b.right(), b.bottom())):
        assert not p._in_hexagon(b, x, y), f"corner ({x},{y}) counted as this patch"
    # the apexes stick out of the box and ARE the patch
    assert p._in_hexagon(b, cx, b.top() - b.height() // 8)
    assert p._in_hexagon(b, cx, b.bottom() + b.height() // 8)
    # the flat sides at mid-height are the patch
    assert p._in_hexagon(b, b.left() + 1, cy)
    assert p._in_hexagon(b, b.right() - 1, cy)


def _ring_profile(hexagonal: bool, tmp_path):
    """Render the highlight over a flat mid-grey image and return, for each of
    the four compass directions, (white inside, accent, white outside) in pixels.

    Rendered, not read from the source: the fault this guards is in what Qt
    puts on the screen, and a source check would have passed throughout.
    """
    import numpy as np
    from PIL import Image
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QImage
    from ui.tiff_preview import TiffPreview

    tif = tmp_path / f"flat_{int(hexagonal)}.tif"
    Image.new("RGB", (400, 400), (128, 128, 128)).save(tif)
    p = TiffPreview()
    p.resize(520, 520)
    p.load_tiff([tif])
    p.set_hex_zigzag(hexagonal)
    box = QRect(160, 160, 96, 84)
    p.show()
    p.highlight_patch(0, box)
    q = p.grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
    w, h = q.width(), q.height()
    buf = q.constBits()
    buf.setsize(q.sizeInBytes())
    a = np.frombuffer(buf, np.uint8).reshape(h, q.bytesPerLine() // 4, 4)[:, :w, :3]
    a = a[:, :, ::-1].astype(int)                      # BGR -> RGB
    p.close()
    accent = np.abs(a - np.array([31, 143, 107])).sum(axis=2) < 150
    if not accent.any():
        return {}
    ys, xs = np.where(accent)
    cy, cx = int(ys.mean()), int(xs.mean())
    # White means WHITE — not "everything that is neither accent nor patch",
    # which swept in the dark widget background and reported a 144 px halo.
    white = (a > 200).all(axis=2)
    out = {}
    import re
    for name, (dy, dx) in (("left", (0, -1)), ("right", (0, 1)),
                           ("top", (-1, 0)), ("bottom", (1, 0))):
        line = ""
        for t in range(0, 150):
            y, x = cy + dy * t, cx + dx * t
            if not (0 <= y < a.shape[0] and 0 <= x < a.shape[1]):
                break
            line += "A" if accent[y, x] else ("W" if white[y, x] else ".")
        m = re.search(r"(W*)(A+)(W*)", line)
        if m:
            out[name] = (len(m.group(1)), len(m.group(2)), len(m.group(3)))
    return out


@pytest.mark.parametrize("hexagonal", [False, True])
def test_the_ring_halo_is_even_on_every_side(qapp, tmp_path, hexagonal):
    """The white is (halo - accent)/2 on each side. At 5.0 over 2.5 that was
    1.25 logical px = 2.5 device px on a Retina screen — five device pixels to
    split between two sides, and five does not halve. One side got 3 and the
    other 2, and which side flipped with each patch's sub-pixel phase: 50 %
    variation between the hexagon's two flat sides, and the same on rectangular
    charts, where it was first spotted on screen.
    """
    prof = _ring_profile(hexagonal, tmp_path)
    assert prof, "no ring was drawn at all"
    for side, (inside, accent, outside) in prof.items():
        assert accent >= 1, f"{side}: no accent stroke"
        assert abs(inside - outside) <= 1, (
            f"{side}: {inside} px of white inside against {outside} outside "
            f"({prof})")


@pytest.mark.parametrize("dpr", [1.0, 1.5, 2.0, 3.0])
def test_the_halo_splits_into_whole_device_pixels(dpr):
    """The rule, not the numbers — and the reason a rendered test is not enough.

    The white is (halo - accent)/2 on each side. The fault is invisible at
    device pixel ratio 1, which is what an offscreen render gives, and only
    appears on a Retina screen: 5.0 over 2.5 leaves 2.5 device px per side, and
    a half pixel has to fall one way or the other.
    """
    from ui.tiff_preview import (RING_ACCENT_W, RING_ACCENT_W_SMALL,
                                 RING_HALO_W, RING_HALO_W_SMALL)
    for halo, accent in ((RING_HALO_W, RING_ACCENT_W),
                         (RING_HALO_W_SMALL, RING_ACCENT_W_SMALL)):
        side = (halo - accent) / 2.0 * dpr
        assert abs(side - round(side)) < 1e-9, (
            f"{halo} over {accent} leaves {side} device px per side "
            f"at dpr {dpr}")
        assert side >= 1.0, f"{halo}/{accent} leaves no white at dpr {dpr}"


def test_a_small_patch_gets_the_thinner_ring(qapp):
    """A 6 px halo is a third of a 7 mm patch on screen."""
    from ui.tiff_preview import (RING_HALO_W, RING_HALO_W_SMALL,
                                 RING_SMALL_PATCH_PX)
    assert RING_HALO_W_SMALL < RING_HALO_W
    assert RING_SMALL_PATCH_PX > RING_HALO_W * 2
