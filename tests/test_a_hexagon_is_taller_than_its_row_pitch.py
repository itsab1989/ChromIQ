"""A hexagonal patch is TALLER than the slot it is drawn in, and the panel said
it was the slot.

Knut, 2026-09-06, on 4.1.5-beta.10 (register B8-80):

    "In the Chart layout information frame, the 'Patch size (mm)' has the
    correct width according to the Patch width measurement in the 'Measured
    from Preview' frame, but the height part is wrong and too small. For a
    hexagonal patch, the height top-tip to bottom-tip is always larger than the
    patch width, but the 'Patch size (mm)' says 11.3 x 9.78."

He is right. `instruments` builds a honeycomb with ``plen = pwid * sqrt(3)/2``,
which is the interlocking ROW PITCH, and `raster._hexagon_points` puts the apexes
``plen/6`` past both ends of that slot, so the patch spans ``plen * 4/3`` tip to
tip. 11.3 * sqrt(3)/2 = 9.786 (what he saw); 11.3 * 2/sqrt(3) = 13.05 (the patch).

The first test here MEASURES the drawn hexagon in a rendered raster rather than
trusting the constant, so a change to `_hexagon_points` that leaves
`HEX_HEIGHT_FACTOR` alone still turns this red.

Nothing in the layout engine may call the reporting helper: capacity and
placement are already correct on the pitch plus the reserved apex overhang
(``hxeh``), and a chart built before this existed must still come out
byte-identical. The last two tests hold that line.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from workflow.hex_support import HEX_HEIGHT_FACTOR, hex_patch_height_mm
from workflow.layout_engine import geometry, instruments, raster
from workflow.layout_engine.ti1_reader import ColorTarget

MM = 25.4
REPO = Path(__file__).resolve().parents[1]


def _target(n):
    """Every patch a DIFFERENT colour, so an interlocking neighbour can never be
    mistaken for the patch under test: hexagons in one strip are staggered by
    half a width and their apexes overlap the rows above and below, so a
    same-colour scan merges three rows into one and reports a height 3x too big
    (measured, on the first attempt at this test)."""
    return ColorTarget(
        color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
        patches=[((float((i * 37) % 100), float((i * 61) % 100),
                   float((i * 83) % 100)), (30.0, 30.0, 30.0))
                 for i in range(n)])


def _measure_drawn_hexagon(key, dpi=300.0):
    """Render a real page and read one hexagon's extent off the pixels.

    Returns ``(width_mm, height_mm, slot_w_mm, slot_h_mm)``."""
    geom = instruments.build(key, hflag=True)
    assert instruments.is_hexagonal(geom), f"{key} did not build a honeycomb"
    w_mm, h_mm = 210.0, 297.0
    lay = geometry.compute(geom, w_mm, h_mm, 96)
    # SPACERS OFF, and that is not a convenience. A SpectroScan honeycomb has
    # pspa = 0 and a CR30's default recipe sets spacer_mode="none", so this IS
    # the shipped configuration. Turn them on for a CR30 and the spacer bar,
    # drawn AFTER the patch above it and across the un-staggered slot, paints
    # over the hexagon's lower apex: measured here, the drawn patch came back
    # 12.02 mm instead of 13.89 mm, i.e. the whole 1.73 mm bottom point gone.
    # That is a separate finding (reported, not fixed here), and it must not be
    # what this test is measuring.
    res = raster.render_pages(_target(96), lay, geom, seed=1, randomize=False,
                              paper_w_mm=w_mm, paper_h_mm=h_mm, dpi=dpi,
                              spacer_mode="none")
    img = np.asarray(res.images[0])
    rects = geometry.patch_rects_px(geom, w_mm, h_mm, lay, dpi)
    # A patch well inside the sheet, so no page furniture is in the way.
    xs = sorted({r["x"] for r in rects})
    col = sorted([r for r in rects if r["x"] == xs[len(xs) // 2]],
                 key=lambda r: r["y"])
    r = col[len(col) // 2]
    cx, cy = r["x"] + r["w"] // 2, r["y"] + r["h"] // 2
    want = tuple(img[cy, cx])

    def _run(pixels, start):
        lo = hi = start
        while lo - 1 >= 0 and tuple(pixels[lo - 1]) == want:
            lo -= 1
        while hi + 1 < len(pixels) and tuple(pixels[hi + 1]) == want:
            hi += 1
        return hi - lo + 1

    drawn_h = _run(img[:, cx], cy)
    drawn_w = _run(img[cy, :], cx)
    return (drawn_w * MM / dpi, drawn_h * MM / dpi,
            r["w"] * MM / dpi, r["h"] * MM / dpi)


@pytest.mark.parametrize("key", ["SS", "CR30"])
def test_the_drawn_hexagon_is_four_thirds_of_its_slot(key):
    """MEASURED in a rendered raster, not derived from the constant."""
    drawn_w, drawn_h, slot_w, slot_h = _measure_drawn_hexagon(key)
    # One pixel at 300 dpi is 0.085 mm; allow three.
    tol = 3 * MM / 300.0
    assert drawn_w == pytest.approx(slot_w, abs=tol), (
        "a hexagon has flat vertical sides, so it is exactly as wide as its "
        f"slot: drawn {drawn_w:.3f} mm vs slot {slot_w:.3f} mm")
    assert drawn_h == pytest.approx(slot_h * HEX_HEIGHT_FACTOR, abs=tol), (
        f"{key}: the drawn hexagon is {drawn_h:.3f} mm tall, but "
        f"{slot_h:.3f} mm * {HEX_HEIGHT_FACTOR:.4f} = "
        f"{slot_h * HEX_HEIGHT_FACTOR:.3f} mm was expected")
    # And that is the regular-hexagon relation to its width, which is the form
    # Knut's own arithmetic takes (11.3 -> 13.05).
    assert drawn_h == pytest.approx(drawn_w * 2.0 / math.sqrt(3.0), abs=tol)
    # The patch is TALLER than it is wide. Knut's sentence, as an assertion.
    assert drawn_h > drawn_w


@pytest.mark.parametrize("key", ["SS", "CR30"])
def test_the_slot_is_the_row_pitch_and_is_smaller_than_the_patch(key):
    geom = instruments.build(key, hflag=True)
    assert geom.plen == pytest.approx(geom.pwid * math.sqrt(3.0) / 2.0)
    assert hex_patch_height_mm(geom.plen) == pytest.approx(
        geom.pwid * 2.0 / math.sqrt(3.0))
    assert hex_patch_height_mm(geom.plen) > geom.plen


def test_knuts_own_numbers():
    """11.3 x 9.78 was the pitch. The patch is 11.3 x 13.05."""
    assert 11.3 * math.sqrt(3.0) / 2.0 == pytest.approx(9.78, abs=0.01)
    assert hex_patch_height_mm(9.786) == pytest.approx(13.05, abs=0.01)


# ------------------------------------------------------------------ the panel

def _hex_layout(tmp_path, instrument="SS", dpi=200.0):
    """A minimal chart + `channels.json` sidecar of the shape the panel reads."""
    import json
    geom = instruments.build(instrument, hflag=True)
    lay = geometry.compute(geom, 210.0, 297.0, 96)
    rects = geometry.patch_rects_px(geom, 210.0, 297.0, lay, dpi)
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("NUMBER_OF_SETS 96\n", encoding="utf-8")
    (tmp_path / "chart.channels.json").write_text(json.dumps(
        {"layout": {"dpi": dpi, "paper_mm": [210.0, 297.0],
                    "patches": rects,
                    "recipe": {"instrument": instrument, "hflag": True}}}),
        encoding="utf-8")
    return ti2, geom, rects


def test_the_panel_feed_reports_the_patch_and_the_pitch(tmp_path):
    """The on-screen column: real height, and the slot named as the pitch."""
    from ui.tabs.tab_chart import TabChart
    ti2, geom, rects = _hex_layout(tmp_path)
    w, h, pitch = TabChart._chart_patch_size_mm(ti2)
    slot_h = rects[0]["h"] * MM / 200.0
    assert w == pytest.approx(rects[0]["w"] * MM / 200.0)
    assert pitch == pytest.approx(slot_h), "the row pitch is the slot"
    assert h == pytest.approx(slot_h * HEX_HEIGHT_FACTOR), (
        "the panel is still reporting the slot as the patch height")
    assert h > w, "a hexagon is taller than it is wide"


def test_a_square_chart_has_no_second_number(tmp_path):
    """Square patches: the slot IS the patch, and the pitch row stays away."""
    import json
    from ui.tabs.tab_chart import TabChart
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 96)
    rects = geometry.patch_rects_px(geom, 210.0, 297.0, lay, 200.0)
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("NUMBER_OF_SETS 96\n", encoding="utf-8")
    (tmp_path / "chart.channels.json").write_text(json.dumps(
        {"layout": {"dpi": 200.0, "paper_mm": [210.0, 297.0], "patches": rects,
                    "recipe": {"instrument": "i1", "hflag": False}}}),
        encoding="utf-8")
    w, h, pitch = TabChart._chart_patch_size_mm(ti2)
    assert pitch == 0.0
    assert h == pytest.approx(rects[0]["h"] * MM / 200.0), (
        "a square patch's height was scaled as if it were a hexagon")
    assert w == pytest.approx(rects[0]["w"] * MM / 200.0)


def test_the_panel_hides_the_pitch_row_for_a_square_chart(qapp):
    from ui.chart_layout_info_panel import ChartLayoutInfoPanel
    panel = ChartLayoutInfoPanel(None)
    panel.set_actual(total=96, rows=12, cols=8, pages=1,
                     patch_w=8.0, patch_h=10.0)
    assert not panel._row_names["pitch"].isVisible()
    assert panel._actual_labels["patch"].text() == "8×10"

    panel.set_actual(total=96, rows=12, cols=8, pages=1,
                     patch_w=11.3, patch_h=13.05, row_pitch=9.78)
    # A hidden child of a parent that was never shown reports False either way,
    # so ask the property Qt actually stores.
    assert not panel._row_names["pitch"].isHidden()
    assert panel._actual_labels["pitch"].text() == "9.78"
    assert panel._actual_labels["patch"].text() == "11.3×13.05"


def test_the_two_columns_of_a_honeycomb_agree(qapp, tmp_path):
    """estimate vs on screen: neither may flag the other amber on a chart that
    is the settings it was built from."""
    from ui.chart_layout_info_panel import ChartLayoutInfoPanel
    from ui.tabs.tab_chart import _panel_patch_height_mm
    ti2, geom, rects = _hex_layout(tmp_path)
    from ui.tabs.tab_chart import TabChart
    a_w, a_h, a_p = TabChart._chart_patch_size_mm(ti2)
    e_h, e_p = _panel_patch_height_mm(geom.plen, True)
    panel = ChartLayoutInfoPanel(None)
    panel.set_actual(total=96, rows=1, cols=1, pages=1,
                     patch_w=a_w, patch_h=a_h, row_pitch=a_p)
    panel.set_estimate(total=96, rows=1, cols=1, pages=1,
                       patch_w=geom.pwid, patch_h=e_h, row_pitch=e_p)
    assert a_h == pytest.approx(e_h, abs=panel._PATCH_TOL_MM * HEX_HEIGHT_FACTOR)
    assert a_p == pytest.approx(e_p, abs=panel._PATCH_TOL_MM)


# ------------------------------------------- the geometry did not move an inch

@pytest.mark.parametrize("key", ["SS", "CR30"])
def test_the_honeycomb_geometry_is_untouched(key):
    """A chart built before this change must come out byte-identical, so pin the
    numbers every drawn pixel comes from. Closed forms, not a hash: a failure
    here has to say WHICH number moved."""
    g = instruments.build(key, hflag=True)
    assert g.plen == pytest.approx(g.pwid * math.sqrt(0.75))
    assert g.hxeh == pytest.approx(g.plen / 6.0)
    assert g.hxew == pytest.approx(g.pwid / 4.0)
    lay = geometry.compute(g, 210.0, 297.0, 96)
    rects = geometry.patch_rects_px(g, 210.0, 297.0, lay, 200.0)
    # Slot rects, still: everything downstream of them expects the slot. Each
    # rect is snapped to whole pixels at its own position, so allow one pixel.
    want_w, want_h = g.pwid * 200.0 / MM, g.plen * 200.0 / MM
    for r in rects:
        assert abs(r["w"] - want_w) <= 1 and abs(r["h"] - want_h) <= 1, (
            f"the recorded patch rects are no longer the slot: {r['w']}x{r['h']} "
            f"px against {want_w:.1f}x{want_h:.1f}")


def test_no_layout_code_reports_its_way_into_the_geometry():
    """The reporting factor is display-only. If a module that LAYS CHARTS OUT
    ever imports it, a chart's pixels start depending on a number invented to
    describe them, and every chart built before that stops reproducing."""
    offenders = []
    for py in sorted((REPO / "workflow" / "layout_engine").rglob("*.py")):
        src = py.read_text(encoding="utf-8")
        if "HEX_HEIGHT_FACTOR" in src or "hex_patch_height_mm" in src:
            offenders.append(py.relative_to(REPO).as_posix())
    assert offenders == [], (
        "the layout engine now depends on the reporting helper: "
        + ", ".join(offenders))
