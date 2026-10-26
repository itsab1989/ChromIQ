"""Each ruler dash in the preview is ONE line (Knut, 2026-10-26).

    *"the helper markers have become buggy: Each line is no longer a single
    line. The example here has markers per patch equal to 2. Same happens for
    higher numbers."*

His sheet was a 200 dpi i1Pro photo card, shown near full size on a large
screen. The printed TIFF was right: every dash one solid 2 px line. The PREVIEW
draws its own black dash over each printed one (#152, so a dash can be judged
while its spin boxes are nudged), and that overlay was placed at the exact
millimetre while the ink sits on whole pixels, half a pixel right of the
millimetre for its even 2 px width. Rounded to whole screen pixels on top, the
two were up to a pixel and a half of the sheet apart: invisible while the
preview shrinks the sheet, but at about one sheet pixel per screen pixel the
printed dash showed beside the overlay's, and every second dash read as a thick
line next to a thin one. Measured on screen in the real window: 20 of 26 top
dashes doubled at 2 per patch, 122 of 158 dashes at 4 per patch; after the fix,
none in any scenario.

So the overlay is now the centre line of the very pixels the renderer inks
(`raster.helper_marker_ink_rects_px`, the rule the vector PDF already used),
and it is drawn at least as thick as that ink.

Every test here fails on 4.3.16 and passes with the fix.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

TI1 = "tests/fixtures/charts/cm_a4_480p_2pages.ti1"
DPI = 200                      # the photo cards' resolution, where he saw it
PAPER = "100x150"


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def sheet(qapp, tmp_path_factory):
    """A 200 dpi i1Pro photo card at 2 markers per patch, both edge sets on,
    with the dashes the renderer drew captured as it drew them."""
    from workflow.layout_engine import chart as le_chart, geometry
    from workflow.layout_engine import raster as raster_mod
    from workflow.layout_engine.presets import LayoutRecipe

    rec = LayoutRecipe(instrument="i1", paper=PAPER, dpi=DPI,
                       helper_markers=True, helper_marker_edge_mm=2.0,
                       helper_marker_len_mm=2.0, helper_marker_per_patch=2,
                       helper_markers_top_bottom=True, helper_markers_sides=True,
                       seed_fixed=True, seed=1)
    drawn: list[tuple] = []
    real = geometry.helper_marker_lines_mm

    def spy(*a, **kw):
        out = real(*a, **kw)
        drawn.append(tuple(out))
        return out

    tmp = tmp_path_factory.mktemp("card")
    raster_mod.geometry.helper_marker_lines_mm = spy
    try:
        res = le_chart.build_chart(TI1, tmp / "c", **rec.build_kwargs())
    finally:
        raster_mod.geometry.helper_marker_lines_mm = real
    assert drawn, "the renderer drew no markers"
    Path(res.ti2_path).with_suffix(".channels.json").write_text(json.dumps(
        {"layout": {"engine": "chromiq", "recipe": rec.to_dict(),
                    "seed": res.seed}}), encoding="utf-8")
    return {"rec": rec, "res": res, "lines_mm": list(drawn[0]),
            "tiff": Path(res.tiff_paths[0]), "tmp": tmp}


@pytest.fixture(scope="module")
def overlay(sheet):
    """What the Create Chart tab hands the preview for that sheet."""
    from PyQt6.QtCore import QSettings

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart

    s = AppSettings()
    s._qs = QSettings(str(sheet["tmp"] / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(sheet["tmp"] / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._switch_mode("manual")
    tab._margin_tiffs = [sheet["tiff"]]
    tab._margin_ti2 = Path(sheet["res"].ti2_path)
    lp = tab._manual_layout_panel
    lp.helper_markers_cb.setChecked(True)
    lp.helper_marker_edge.setValue(2.0)
    lp.helper_marker_len.setValue(2.0)
    lp.helper_marker_per_patch.setValue(2)
    lp.helper_markers_top_bottom.setChecked(True)
    lp.helper_markers_sides.setChecked(True)
    lines, pending = tab._helper_marker_lines_frac()
    ink = getattr(tab, "_helper_marker_ink_frac", None)
    return {"lines": lines, "pending": pending, "ink": ink}


def _ink(path):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert("L")) < 128


# --- 1. the shared rule is what the sheet really inks ------------------------

def test_the_ink_rectangles_are_the_pixels_on_the_sheet(sheet):
    """`helper_marker_ink_rects_px` must BE the TIFF's dashes: every pixel in
    each rectangle black, and the column/row just outside it white."""
    from workflow.layout_engine import raster

    dark = _ink(sheet["tiff"])
    H, W = dark.shape
    rects = raster.helper_marker_ink_rects_px(sheet["lines_mm"], DPI)
    assert len(rects) > 20
    checked = 0
    for x0, y0, x1, y1 in rects:
        assert dark[y0:y1, x0:x1].all(), (
            f"the rectangle {(x0, y0, x1, y1)} is not all ink on the sheet")
        vertical = (x1 - x0) < (y1 - y0)
        if vertical and 0 < x0 and x1 < W:
            mid = (y0 + y1) // 2
            assert not dark[mid, x0 - 1] and not dark[mid, x1], (
                f"the dash at x={x0}..{x1 - 1} is wider than its rectangle")
            checked += 1
        elif not vertical and 0 < y0 and y1 < H:
            mid = (x0 + x1) // 2
            assert not dark[y0 - 1, mid] and not dark[y1, mid], (
                f"the dash at y={y0}..{y1 - 1} is taller than its rectangle")
            checked += 1
    assert checked > 20


# --- 2. the overlay is centred on that ink ----------------------------------

def test_the_overlay_is_the_centre_line_of_the_printed_dash(sheet, overlay):
    """Was: the millimetre the dash was asked for, up to 1.5 sheet pixels from
    the pixels that carry it."""
    from workflow.layout_engine import raster

    assert overlay["pending"] is False
    dark = _ink(sheet["tiff"])
    H, W = dark.shape
    rects = raster.helper_marker_ink_rects_px(sheet["lines_mm"], DPI)
    assert len(overlay["lines"]) == len(rects)
    worst = 0.0
    for (fx0, fy0, fx1, fy1), (x0, y0, x1, y1) in zip(
            sorted(overlay["lines"]), sorted(
                ((rx0 + rx1) / 2 / W, ry0 / H, (rx0 + rx1) / 2 / W, ry1 / H)
                if (rx1 - rx0) < (ry1 - ry0) else
                (rx0 / W, (ry0 + ry1) / 2 / H, rx1 / W, (ry0 + ry1) / 2 / H)
                for rx0, ry0, rx1, ry1 in rects)):
        worst = max(worst, abs(fx0 - x0) * W, abs(fx1 - x1) * W,
                    abs(fy0 - y0) * H, abs(fy1 - y1) * H)
    assert worst < 1e-6, (
        f"the overlay is {worst:.2f} sheet pixels off the printed dash")


def test_the_preview_is_told_how_thick_the_ink_is(sheet, overlay):
    from workflow.layout_engine import raster

    dark = _ink(sheet["tiff"])
    H, W = dark.shape
    w = max(1, round(raster._HELPER_MARKER_W_MM * DPI / 25.4))
    assert overlay["ink"] is not None
    assert overlay["ink"][0] == pytest.approx(w / W)
    assert overlay["ink"][1] == pytest.approx(w / H)


# --- 3. on the preview's own pixels: one line per dash, at any zoom ----------

@pytest.mark.parametrize("scale", [0.6, 1.0, 1.26, 1.6, 2.2])
def test_every_dash_in_the_preview_is_one_solid_line(qapp, sheet, overlay,
                                                     scale):
    """The real widget, the real sheet, the real overlay, read off the pixels
    it paints. Across the middle of every dash there must be exactly one dark
    run, at least as wide as the printed dash is at that zoom.

    1.26 is the zoom measured in the real window where 20 of 26 dashes came
    out doubled; 0.6 is an ordinary small preview, where it never showed."""
    import numpy as np

    from ui.tiff_preview import TiffPreview

    dark = _ink(sheet["tiff"])
    H, W = dark.shape
    prev = TiffPreview()
    # The label is the image area; size it so the page is drawn at `scale`.
    prev.resize(int(W * scale) + 120, int(H * scale) + 160)
    prev.load_tiff([sheet["tiff"]])
    prev.show()
    qapp.processEvents()
    prev.set_helper_markers(overlay["lines"], pending=False, ink=overlay["ink"])
    qapp.processEvents()
    pm = prev._img_label.pixmap()
    assert pm is not None and not pm.isNull()
    img = pm.toImage()
    lw, lh = prev._img_label.width(), prev._img_label.height()
    # The canvas is centred in the label (`_repaint_label`), and
    # `_paint_geom` is where the page landed in label coordinates.
    s, ox, oy = prev._paint_geom
    sy = prev._paint_scale_y
    cx0 = (lw - img.width()) / 2
    cy0 = (lh - img.height()) / 2
    buf = img.convertToFormat(img.Format.Format_RGB32)
    ptr = buf.constBits()
    ptr.setsize(buf.sizeInBytes())
    arr = np.frombuffer(ptr, np.uint8).reshape(
        buf.height(), buf.bytesPerLine() // 4, 4)[:, :buf.width(), :3]
    lum = arr.astype(int).min(axis=2)

    ink_px = max(1, round(0.2 * DPI / 25.4))
    bad, checked = [], 0
    for fx0, fy0, fx1, fy1 in overlay["lines"]:
        vertical = abs(fx0 - fx1) < 1e-12
        if vertical:
            x = ox - cx0 + fx0 * W * s
            y = oy - cy0 + (fy0 + fy1) / 2 * H * sy
            prof = lum[int(round(y)), int(x) - 6: int(x) + 7]
        else:
            x = ox - cx0 + (fx0 + fx1) / 2 * W * s
            y = oy - cy0 + fy0 * H * sy
            prof = lum[int(y) - 6: int(y) + 7, int(round(x))]
        d = prof < 200
        runs = int(np.sum(d[1:] & ~d[:-1]) + (1 if d[0] else 0))
        width = int(d.sum())
        checked += 1
        if runs != 1 or width < ink_px * scale - 1:
            bad.append("".join("#" if v < 100 else ("+" if v < 200 else ".")
                               for v in prof))
    prev.close()
    assert checked > 20
    assert not bad, (
        f"at {scale}x, {len(bad)} of {checked} dashes are not one solid line: "
        f"{bad[:4]}")
