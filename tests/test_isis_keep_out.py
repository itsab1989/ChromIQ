"""Nothing ChromIQ draws on an i1iSis chart enters a zone the instrument
needs clear, for ANY combination of the chart's options (a fuzz over the
options table of PROPOSAL v2 §4).

The zones (REQUIREMENTS §4, `workflow.isis.chart.Sheet.keep_out`): the 20 mm
above the bar across the chart, the bar, the space under it (the barcode
only), the patch grid, 3 mm of white around every diamond, and the first
22 mm after the last row. Only the instrument's own marks may be there: the
bar, the barcode, the diamonds, the feed arrows beside the bar (where
i1Profiler puts them) and the dashed outline on the chart's edge.

Two levels: the plan (every item's box, in mm) over 3000 random option sets,
and the pixels of real rendered pages for a handful."""
from __future__ import annotations

import random

import pytest

from workflow.isis import chart as C

PAPERS = [(210, 297), (215.9, 279.4), (148, 210), (127, 178), (203.2, 254),
          (297, 420), (279.4, 431.8), (329, 483), (297, 210), (230, 660)]


def _random_options(rng):
    return {
        "patch_w": rng.choice([6, 6.25, 7, 8, 10, 12.5, 20]),
        "patch_h": rng.choice([6, 6.5, 7, 8, 10, 15, 20]),
        "margins": tuple(rng.choice([0, 3, 5, 10, 20]) for _ in range(4)),
        "offset_x": rng.choice([0, 0, 2.5, 10]),
        "offset_y": rng.choice([0, 0, 4, 12]),
        "max_strip": rng.choice([0, 0, 0, 60, 120]),
        "stamp_command": rng.random() < 0.3,
        C.MODEL_KEY: rng.choice(["standard", "xl"]),
        C.HEADER_KEY: rng.choice([32, 40, 56, 80]),
        C.TIGHT_KEY: rng.random() < 0.5,
        C.BARCODE_KEY: rng.random() < 0.4,
        C.TRAILER_KEY: rng.choice([25.5, 30, 60]),
        C.ARROWS_KEY: rng.random() < 0.8,
        C.OUTLINE_KEY: rng.random() < 0.8,
        C.CORNERS_KEY: rng.random() < 0.8,
        C.LETTERS_KEY: rng.choice(["top", "bottom"]),
        # the engine's own label controls (one control each, 2026-11-14)
        "draw_indicators": rng.random() < 0.5,
        "row_indicators": rng.random() < 0.5,
        "indicator_font": rng.choice(["Inter", "JetBrains Mono"]),
        "indicator_size_mm": rng.choice([0.0, 1.0, 2.5, 6.0]),
        "indicator_bold": rng.random() < 0.5,
        "indicator_italic": rng.random() < 0.5,
        "indicator_rotation": rng.choice([0, 90, 180, 270]),
        "row_indicator_rotation": rng.choice([0, 90, 180, 270]),
        "indicator_align": rng.choice(["left", "center", "right"]),
        "underline_mode": rng.choice(["off", "black", "segments", "cycle"]),
        "underline_thickness_mm": rng.choice([0.3, 1.0, 2.0]),
        "underline_gap_mm": rng.choice([0.0, 0.5, 3.0]),
        "strip_label_offset_mm": rng.choice([-20.0, 0.0, 2.0, 30.0]),
        "strip_label_offset_x_mm": rng.choice([-10.0, 0.0, 3.0, 10.0]),
        "layout_mode": rng.choice(["patch_first", "patch_first",
                                   "area_first"]),
        "area_method": rng.choice(["by_width", "by_grid"]),
        "area_cols": rng.choice([0, 10, 30]),
        "area_rows": rng.choice([0, 12, 40]),
        C.NOTES_LINES_KEY: rng.choice([(), ("Run 1 notes",),
                                       ("a" * 200, "settings line")]),
        C.BAND_KEY: rng.random() < 0.5,
        C.BAND_PLACE_KEY: rng.choice(["header", "trailer"]),
        C.BAND_HEIGHT_KEY: rng.choice([4, 12, 24, 48]),
        C.ALIGN_KEY: rng.choice(["", "top-left", "center", "bottom-right",
                                 "top-center"]),
    }


def test_no_option_combination_enters_a_keep_out_zone():
    rng = random.Random(1405)
    checked = 0
    for _ in range(3000):
        kw = _random_options(rng)
        w, h = rng.choice(PAPERS)
        N = rng.choice([1, 4, 24, 100, 957, 1617, 2900])
        kw["paper"] = f"{w}x{h}"
        try:
            _o, g, s = C.layout_for(N, w, h, {**kw, C.COUNT_KEY: N})
        except C.IsisSheetRefused:
            continue
        for page in range(min(g.P, 3)):
            items, _off = C.plan_page(s, page, name="Keep_Out_Fuzz",
                                      sheet_text="some sheet text",
                                      title="Keep_Out_Fuzz",
                                      stamp_text="ChromIQ engine · i1iSis")
            bad = C.keep_out_violations(s, items)
            assert not bad, (kw, (w, h), N, page, bad)
            # and everything lies on the paper
            for it in items:
                x, y, bw, bh = it.box
                assert x >= -1e-6 and y >= -1e-6, (it, kw)
                assert x + bw <= w + 1e-6 and y + bh <= h + 1e-6, (it, kw)
        checked += 1
    assert checked > 1500


@pytest.mark.parametrize("seed", range(6))
def test_the_rendered_pixels_keep_the_zones_clear(seed):
    """Drawn for real (100 dpi) on a white page: no ink in a keep-out zone
    except the instrument's own marks."""
    from PIL import Image
    rng = random.Random(seed)
    while True:
        kw = _random_options(rng)
        w, h = rng.choice(PAPERS[:6])
        try:
            _o, g, s = C.layout_for(rng.choice([24, 300, 957]), w, h, kw)
            break
        except C.IsisSheetRefused:
            continue
    dpi = 100
    sc = dpi / 25.4
    img = Image.new("RGB", (round(w * sc), round(h * sc)), (255, 255, 255))

    class R:
        images = [img]
        patch_geom = None
    C.draw_furniture(R, s, dpi, name="Pixel_Check", sheet_text="text",
                     title="Pixel_Check",
                     band={"mode": "text", "text": "notes", "ctx": {}})
    px = img.load()
    for name, (x, y, zw, zh) in s.keep_out():
        if name in ("bar", "diamond", "under_bar", "above_bar", "grid"):
            continue          # zones the marks themselves fill
        # the inner trailer must be white inside the chart, beside the
        # outline's 0.5 mm dashes and the diamond columns
        x0 = round((s.grid_x) * sc) + 1
        x1 = round((s.grid_x + s.grid_w) * sc) - 1
        y0 = round(y * sc) + 1
        y1 = round((y + zh) * sc) - 1
        for yy in range(y0, y1, 2):
            for xx in range(x0, x1, 3):
                assert px[xx, yy] == (255, 255, 255), (name, xx, yy, kw)
    # the 20 mm above the bar, across the grid, white
    y0 = round((s.bar_y - 20.0) * sc) + 1
    y1 = round(s.bar_y * sc) - 1
    for yy in range(y0, y1, 2):
        for xx in range(round(s.grid_x * sc) + 1,
                        round((s.grid_x + s.grid_w) * sc) - 1, 3):
            assert px[xx, yy] == (255, 255, 255), ("above_bar", xx, yy, kw)
