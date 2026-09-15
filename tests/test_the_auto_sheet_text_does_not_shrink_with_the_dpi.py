"""A "Size auto" bottom line is the same size at every resolution.

The height term added to the auto-shrink loop on 2026-09-14 asked::

    sheet_text_line_mm(...) <= text_edge_fit.SHEET_TEXT_LINE_MM

`sheet_text_line_mm` measures in whole PIXELS at *dpi*, and its own floor is
``round(4.2 * dpi / 25.4)`` px read back as millimetres: **4.2333 mm at 150,
240, 300 and 360 dpi**, which is larger than the 4.2 mm it was compared with.
So at those resolutions no size could ever satisfy the term, not even the 7 pt
floor the loop stops at, and every chart with Size auto had its bottom line
shrunk all the way down however much paper was free. **300 dpi is
`LayoutRecipe`'s default.**

MEASURED on real sheets built by `build_from_recipe`, A4, Size auto, the short
text "ChromIQ" (so the WIDTH can never be what binds), 7.5 mm of clear paper
under the patches:

| dpi | before the fix | at HEAD before the height term | after the fix |
|---|---|---|---|
| 200 | 2.540 x 13.081 mm | 2.540 x 13.081 | 2.540 x 13.081 |
| 300 | **1.947 x 9.991** | 2.540 x 13.123 | 2.540 x 13.123 |

`raster.sheet_text_reserve_mm` is the band as a given dpi can express it, and
the loop compares against that.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                              # noqa: E402
import pytest                                                   # noqa: E402
from PIL import Image                                           # noqa: E402

from workflow import text_edge_fit as tef                        # noqa: E402
from workflow.layout_engine import raster                        # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TI1 = ROOT / "tests/fixtures/charts/cm_a4_480p_2pages.ti1"

#: Every resolution the four rounding cases land on, plus two that do not.
DPIS = (150, 200, 240, 300, 360, 600)


def test_the_shrink_can_always_stop():
    """At the 7 pt floor the line box must fit the reserve, at every dpi.

    If it cannot, the loop runs to the floor on every chart and "auto" is not
    auto at all. This compares two functions with each other, not a function
    with itself.

    MUTATION: return `text_edge_fit.SHEET_TEXT_LINE_MM` from
    `sheet_text_reserve_mm` and this goes red at 150, 240, 300 and 360.
    """
    floor_mm = tef.pt_to_mm(tef.AUTO_SHRINK_FLOOR_PT)
    for dpi in DPIS:
        box = raster.sheet_text_line_mm(floor_mm, "Inter", False, False, dpi)
        assert box <= raster.sheet_text_reserve_mm(dpi) + 1e-9, (
            f"at {dpi} dpi even the {tef.AUTO_SHRINK_FLOOR_PT} pt floor "
            f"({box:.4f} mm) does not fit the reserve "
            f"({raster.sheet_text_reserve_mm(dpi):.4f} mm), so Size auto "
            f"shrinks to the floor on every chart")


def test_the_reserve_is_the_band_this_dpi_can_draw():
    """A whole number of pixels, and never smaller than the 4.2 mm it stands in
    for by more than one pixel."""
    for dpi in DPIS:
        got = raster.sheet_text_reserve_mm(dpi)
        px = got * dpi / 25.4
        assert abs(px - round(px)) < 1e-6, f"{dpi}: {px} is not whole pixels"
        assert abs(got - tef.SHEET_TEXT_LINE_MM) <= 25.4 / dpi
    assert raster.sheet_text_reserve_mm(0) == raster.sheet_text_reserve_mm(300)
    assert raster.sheet_text_reserve_mm("x") == raster.sheet_text_reserve_mm(300)


def _auto_text_ink_mm(dpi: int) -> "tuple[float, float]":
    """(height, width) of the bottom line's own ink on a real rendered sheet.

    TWO RENDERS WITH THE GEOMETRY PINNED: the off-pass draws a single SPACE,
    which is truthy, so `nlines`, the bottom reserve and every patch size are
    identical and the difference is the line's ink and nothing else.
    """
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe()
    r.instrument, r.paper, r.dpi = "i1", "A4", dpi
    r.layout_mode, r.use_instrument_margins = "area_first", False
    r.margin_top = r.margin_bottom = 14.0
    r.margin_left = r.margin_right = 10.0
    r.chart_text = "ChromIQ"          # short: the width can never bind
    r.chart_text_size_mm = 0.0        # Size auto
    r.stamp_command = False

    def render(text):
        base = Path(tempfile.mkdtemp(prefix=f"autotext-{dpi}-"))
        build_from_recipe(str(TI1), str(base / "s"),
                          replace(r, chart_text=text, randomize=True,
                                  seed_fixed=True, seed=1))
        page = sorted(base.glob("s*.tif"))[0]
        return np.asarray(Image.open(page).convert("L")).astype(np.int16)

    on, off = render(r.chart_text), render(" ")
    assert on.shape == off.shape, "the geometry moved between the two renders"
    diff = np.abs(on - off) > 30
    rows = np.where(diff.any(axis=1))[0]
    cols = np.where(diff.any(axis=0))[0]
    assert rows.size and cols.size, "the bottom line drew nothing"
    return (float(rows[-1] + 1 - rows[0]) * 25.4 / dpi,
            float(cols[-1] + 1 - cols[0]) * 25.4 / dpi)


@pytest.mark.parametrize("dpi", (150, 300))
def test_the_auto_line_is_the_same_size_as_at_200_dpi(dpi):
    """The sheet itself, which is the only thing that settles it.

    MUTATION: compare against `text_edge_fit.SHEET_TEXT_LINE_MM` in the loop
    again and 300 dpi comes out 1.95 x 9.99 mm against 200 dpi's 2.54 x 13.08.
    """
    h_ref, w_ref = _auto_text_ink_mm(200)
    h, w = _auto_text_ink_mm(dpi)
    assert h == pytest.approx(h_ref, abs=0.2), (
        f"the auto bottom line is {h:.3f} mm tall at {dpi} dpi and "
        f"{h_ref:.3f} mm at 200 dpi, on the same recipe")
    assert w == pytest.approx(w_ref, abs=0.4), (
        f"the auto bottom line is {w:.3f} mm wide at {dpi} dpi and "
        f"{w_ref:.3f} mm at 200 dpi, on the same recipe")
