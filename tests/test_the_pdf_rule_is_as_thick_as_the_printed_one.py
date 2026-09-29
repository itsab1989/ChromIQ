"""The chart's PDF and the chart's TIFF must carry the same strip-label rule.

Create Chart's "Also export a PDF" writes a vector sheet beside the TIFF from
one display list, so the two are the SAME chart in two forms. The strip-label
underline was not: the three emitters in `raster.render_pages` wrote Pillow's
INCLUSIVE box into a display list the PDF writer reads as HALF-OPEN, so every
rule came out one pixel short in both dimensions. At any thickness that rounds
to a single pixel (0.10 mm at 300 dpi, up to 0.21 at 150) that is a height of
zero and the rule is simply absent from the PDF, on a sheet that may be the one
a RIP prints.

Measured before the fix, on a real export at 200 dpi with a 0.10 mm rule: one
zero-height rectangle in `black` mode, five in `segments`, eighteen in `cycle`.
At 0.50 mm none were invisible and all were a quarter thin (1.08 pt against the
TIFF's 1.44).

Knut asked which PDF this was, and said that if it were the Measurement Report
he would keep it as is. It is not: it is the chart itself.
"""
from __future__ import annotations

import os
import re
import zlib
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from core.resource_path import resource_path  # noqa: E402
from workflow.layout_engine.chart import build_from_recipe  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe  # noqa: E402

_DPI = 200
_PT_PER_PX = 72.0 / _DPI
_MODES = ("black", "segments", "cycle")


def _recipe(mode: str, thickness_mm: float):
    """Knut's straight-strip A4 chart with the rule turned on. His own recipe,
    so this cannot pass on a layout nobody ships."""
    import ui.tabs.tab_chart as tc
    p = next(x for x in tc.KNUT_PRESETS
             if x.slug == "cr30_a4_450p_1page_portrait_w11_0mm_hexagonal_straight")
    d = dict(p.layout_recipe)
    d.update(underline_mode=mode, underline_thickness_mm=thickness_mm,
             dpi=_DPI, export_pdf=True)
    return resource_path(p.ti1_asset), LayoutRecipe.from_dict(d)


def _filled_rects(pdf: Path):
    """Every ``x y w h re f`` in the page streams, as (w_pt, h_pt)."""
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf.read_bytes(), re.S):
        data = m.group(1)
        try:
            data = zlib.decompress(data)
        except zlib.error:
            pass
        for r in re.finditer(
                rb"([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) re f", data):
            out.append((float(r.group(3)), float(r.group(4))))
    return out


@pytest.mark.parametrize("mode", _MODES)
@pytest.mark.parametrize("thickness_mm", [0.10, 0.50])
def test_no_rule_in_the_pdf_has_no_size(tmp_path, mode, thickness_mm):
    ti1, rec = _recipe(mode, thickness_mm)
    build_from_recipe(ti1, tmp_path / "chart", rec)
    rects = _filled_rects(tmp_path / "chart.pdf")
    assert rects, "the export wrote no filled rectangles at all"
    dead = [r for r in rects if r[0] <= 0 or r[1] <= 0]
    assert not dead, (
        f"{len(dead)} of {len(rects)} rectangles cover nothing: {dead[:4]}")


@pytest.mark.parametrize("mode", _MODES)
def test_the_pdf_rule_is_exactly_as_thick_as_the_ink_on_the_tiff(tmp_path, mode):
    """Against the RENDERED PAGE, not against the arithmetic a second time.

    A one-pixel rule is the case that broke, so it is the case measured: the
    TIFF is searched for the row band the rule inked and the PDF for a
    rectangle of that height.
    """
    from PIL import Image
    import numpy as np

    ti1, rec = _recipe(mode, 0.10)
    build_from_recipe(ti1, tmp_path / "chart", rec)

    arr = np.asarray(Image.open(tmp_path / "chart.tif").convert("L"))
    inked_rows = (arr < 250).sum(axis=1)
    # The rule is a long thin horizontal run under the letters, far wider than
    # any glyph, so it is the widest single row in the label band. One pixel
    # tall by construction at this thickness.
    band_px = 1
    want_pt = band_px * _PT_PER_PX
    assert inked_rows.max() > arr.shape[1] // 4, (
        "no full-width rule was drawn on the TIFF at all")

    heights = {round(h, 4) for _w, h in _filled_rects(tmp_path / "chart.pdf")}
    assert round(want_pt, 4) in heights, (
        f"the TIFF inks a {band_px} px rule ({want_pt:.3f} pt); the PDF's "
        f"rectangle heights are {sorted(heights)[:6]}")


def test_the_converter_is_the_only_place_that_knows_the_convention():
    """A fourth emitter must not be able to pick the other convention.

    `raster._ul_geom_rect` exists because two emitters disagreed: the helper
    markers wrote half-open rows and the three underlines wrote Pillow's
    inclusive box. This fails if an underline goes back to appending its Pillow
    box directly.
    """
    import inspect

    from workflow.layout_engine import raster
    src = inspect.getsource(raster.render_pages)
    for m in re.finditer(r'\("vrect", ([^\n]*)', src):
        row = m.group(1)
        assert "_ul_geom_rect(" in row or "_rect" in row, (
            "a vrect row that names neither the converter nor the helper "
            f"markers' own rect: {row.strip()}")
