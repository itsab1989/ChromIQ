"""BUG C (Patch size mm) + BUG B (margin guides on later pages), 4.1.3-beta.13.

Every assertion is measured from the bundled sidecar / TIFF, never by eye.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np
import pytest

from core.resource_path import resource_path
from workflow.margin_inspector import measure_margins, _dense_run

MM = 25.4
BUNDLES = [
    "assets/charts/pharmacist/rgb/colormunki/a3/tc924/tc924",
    "assets/charts/pharmacist/rgb/colormunki/a3plus/tc918eg/tc918eg",
    "assets/charts/pharmacist/rgb/colormunki/a4/abw702/abw702",
    "assets/charts/pharmacist/rgb/colormunki/a4/tc300/tc300",
    "assets/charts/pharmacist/rgb/i1pro/a4/abw1110/abw1110",
    "assets/charts/pharmacist/rgb/i1pro/a4/extended1944/extended1944",
    "assets/charts/pharmacist/rgb/i1pro/a4/tc918eg/tc918eg",
    "assets/charts/pharmacist/rgb/i1pro/letter/extended1944/extended1944",
    "assets/charts/pharmacist/rgb/i1pro/letter/tc918eg/tc918eg",
]
EXT1944_A4 = "assets/charts/pharmacist/rgb/i1pro/a4/extended1944/extended1944"


def _layout(stem: str) -> dict:
    return json.loads(resource_path(f"{stem}.channels.json").read_text())["layout"]


def _pages(stem: str) -> list[Path]:
    p = resource_path(f"{stem}.ti1")
    return sorted(p.parent.glob(f"{p.stem}_*.tif"))


# ---------------------------------------------------------------- BUG C

def test_bugC_patch_size_uses_the_sidecars_own_dpi():
    """Patch size (mm) must divide the patch rects by layout["dpi"], not 300."""
    from ui.tabs.tab_chart import TabChart
    lay = _layout(EXT1944_A4)
    assert lay["dpi"] == 360 and "recipe" not in lay      # the shape of the trap
    ti2 = resource_path(f"{EXT1944_A4}.ti2")
    w, h = TabChart._chart_patch_size_mm(ti2)
    r0 = lay["patches"][0]
    assert w == pytest.approx(r0["w"] * MM / 360, abs=0.01)
    assert h == pytest.approx(r0["h"] * MM / 360, abs=0.01)
    assert w == pytest.approx(7.49, abs=0.02)             # Knut measured 7.48
    assert h == pytest.approx(7.76, abs=0.10)             # Knut measured 7.83


@pytest.mark.parametrize("stem", BUNDLES)
def test_bugC_every_prebuilt_bundle_reports_its_true_patch_size(stem):
    """All nine bundled presets are 360 dpi and none carries a recipe."""
    from ui.tabs.tab_chart import TabChart
    lay = _layout(stem)
    rects = lay["patches"]
    w, h = TabChart._chart_patch_size_mm(resource_path(f"{stem}.ti2"))
    assert w == pytest.approx(rects[0]["w"] * MM / lay["dpi"], abs=0.01)
    assert h == pytest.approx(rects[0]["h"] * MM / lay["dpi"], abs=0.01)


def test_bugC_sidecar_dpi_is_the_pixel_space_of_the_pages():
    """Cross-check the dpi against physical reality: page px / dpi = paper mm."""
    from PIL import Image
    lay = _layout(EXT1944_A4)
    pw_mm, ph_mm = lay["paper_mm"]
    for tif in _pages(EXT1944_A4):
        with Image.open(tif) as im:
            w_px, h_px = im.size
        assert w_px * MM / lay["dpi"] == pytest.approx(pw_mm, abs=0.15)
        assert h_px * MM / lay["dpi"] == pytest.approx(ph_mm, abs=0.15)


def test_bugC_unknown_dpi_shows_a_dash_not_a_guess(tmp_path):
    """A sidecar with rects but no dpi anywhere must report "nothing", not 300."""
    from ui.tabs.tab_chart import TabChart
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("NUMBER_OF_SETS 1\n")
    (tmp_path / "chart.channels.json").write_text(json.dumps(
        {"layout": {"engine": "derived",
                    "patches": [{"loc": "A1", "page": 0,
                                 "x": 0, "y": 0, "w": 100, "h": 100}]}}))
    assert TabChart._chart_patch_size_mm(ti2) == (0.0, 0.0)


def test_bugC_the_two_panels_agree_on_patch_width():
    """"Patch size" (sidecar) and "Patch width" (image) describe one chart."""
    from ui.tabs.tab_chart import TabChart
    for stem in BUNDLES:
        lay = _layout(stem)
        w, _h = TabChart._chart_patch_size_mm(resource_path(f"{stem}.ti2"))
        for tif in _pages(stem):
            rep = measure_margins(tif, dpi=300,
                                  ti2_path=resource_path(f"{stem}.ti2"))
            assert rep is not None and rep.strip_width_mm is not None
            assert w == pytest.approx(rep.strip_width_mm, abs=0.05), \
                f"{stem} {tif.name}: panel {w} vs inspector {rep.strip_width_mm}"


# ---------------------------------------------------------------- BUG B

@pytest.mark.parametrize("stem", BUNDLES)
def test_bugB_detected_margins_match_the_recorded_geometry_on_every_page(stem):
    """The detector must find the patch block, not the strip-label band.

    Tolerance 1.5 mm: the detector legitimately includes the edge spacer that
    the patch rects exclude (~0.8-1.2 mm).
    """
    lay = _layout(stem)
    dpi = lay["dpi"]
    _pw, ph = lay["paper_mm"]
    ti2 = resource_path(f"{stem}.ti2")
    for i, tif in enumerate(_pages(stem)):
        rects = [r for r in lay["patches"] if r["page"] == i]
        y0 = min(r["y"] for r in rects)
        y1 = max(r["y"] + r["h"] for r in rects)
        rep = measure_margins(tif, dpi=300, ti2_path=ti2)
        assert rep is not None
        assert rep.top_mm == pytest.approx(y0 * MM / dpi, abs=1.5), \
            f"{stem} page {i + 1}: top {rep.top_mm:.2f} mm"
        assert rep.bottom_mm == pytest.approx(ph - y1 * MM / dpi, abs=1.5), \
            f"{stem} page {i + 1}: bottom {rep.bottom_mm:.2f} mm"


def test_bugB_top_margin_is_the_same_on_every_page_of_one_chart():
    """Knut: page 1 says ~46 mm, pages 2-3 said 21.4 mm for the same edge."""
    stem = EXT1944_A4
    ti2 = resource_path(f"{stem}.ti2")
    tops = [measure_margins(t, dpi=300, ti2_path=ti2).top_mm
            for t in _pages(stem)]
    assert max(tops) - min(tops) < 0.5, tops


def test_bugB_strip_length_is_the_same_on_every_page_of_one_chart():
    stem = EXT1944_A4
    ti2 = resource_path(f"{stem}.ti2")
    lens = [measure_margins(t, dpi=300, ti2_path=ti2).strip_length_mm
            for t in _pages(stem)]
    assert max(lens) - min(lens) < 1.0, lens


def test_bugB_a_dense_text_band_above_the_block_is_not_the_top_edge():
    """Synthetic: 40 fully-inked rows of "label", bare paper, then the block."""
    fill = np.zeros(1000)
    fill[100:140] = 0.60        # strip labels — over the 0.5 anchor threshold
    fill[400:900] = 1.00        # the patch block
    assert _dense_run(fill) == (400, 899)


def test_bugB_a_white_spacer_row_inside_the_block_does_not_split_it():
    """printtarg omits the black separator where two patches differ enough, so
    the block can carry a ~10 px white gap. Guards the naive longest-run fix,
    which broke tc300 p1 and both tc918eg p2 by 8-13 mm at the bottom."""
    fill = np.zeros(1000)
    fill[100:140] = 0.60        # labels
    fill[400:860] = 1.00        # block
    fill[860:872] = 0.05        # a mostly-white spacer row
    fill[872:900] = 1.00        # the last patch row
    assert _dense_run(fill) == (400, 899)
