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
