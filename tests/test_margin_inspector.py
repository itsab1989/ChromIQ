"""Real-render tests for the margin inspector engine.

These render actual charts with ArgyllCMS ``printtarg`` and measure the result,
so they exercise the true layout geometry rather than a synthetic stand-in.
They skip cleanly where ``printtarg`` isn't installed (CI without Argyll).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from workflow.margin_inspector import measure_margins, _patch_area_bbox


def _find_printtarg() -> str | None:
    # 1. On PATH (covers any OS where Argyll's bin dir is exported).
    p = shutil.which("printtarg")
    if p:
        return p
    # 2. The standard install locations the app itself probes, per-OS.
    from core.platform_paths import argyll_candidate_dirs
    for d in argyll_candidate_dirs():
        for name in ("printtarg", "printtarg.exe"):
            cand = d / name
            if cand.is_file():
                return str(cand)
    return None


PRINTTARG = _find_printtarg()
requires_argyll = pytest.mark.skipif(
    PRINTTARG is None, reason="ArgyllCMS printtarg not installed"
)

# A small i1Pro preset .ti1 shipped with the app — fast to render (1 page).
_TI1 = (
    Path(__file__).resolve().parent.parent
    / "assets/charts/knut/rgb/fulllayout/fls_i1pro_a4_484p_1page_portrait/chart.ti1"
)


def _render(tmp_path: Path, *args: str) -> Path:
    """Render the test .ti1 with the given extra printtarg args; return the TIF."""
    work = tmp_path / "chart.ti1"
    shutil.copy(_TI1, work)
    subprocess.run(
        [PRINTTARG, *args, "chart"],
        cwd=tmp_path, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return tmp_path / "chart.tif"


@requires_argyll
def test_full_page_tiff_margins_are_paper_edge(tmp_path):
    """-M includes the margin in the TIFF (full A4 sheet); margins are measured
    straight against the paper edge."""
    tif = _render(tmp_path, "-ii1", "-pA4", "-t300", "-P", "-L", "-M8")
    w, h = Image.open(tif).size
    assert (w, h) == (2480, 3508)            # full A4 at 300 dpi

    r = measure_margins(tif, dpi=300, ti2_path=tif.with_suffix(".ti2"))
    assert r is not None
    assert r.page_w_mm == pytest.approx(210, abs=0.5)
    assert r.page_h_mm == pytest.approx(297, abs=0.5)
    # -L suppresses the 26 mm clip border, so the left margin is just -M8.
    assert r.left_mm == pytest.approx(8, abs=1.5)
    # The strip-label side carries the larger margin (Knut's observation).
    assert r.right_mm > r.left_mm + 5
    # Top is measured to the first patch row, excluding the A/B/C label band.
    assert 10 < r.top_mm < 45
    assert 0 <= r.bottom_mm < 40
    # Estimated patch size in the reading direction is in a sane range.
    assert r.strip_width_mm is not None
    assert 6 < r.strip_width_mm < 16


@requires_argyll
def test_cropped_tiff_corrected_by_paper_size(tmp_path):
    """-m *subtracts* the margin (TIFF cropped to the imageable area); passing
    the true paper size restores the same paper-edge margins as the -M render."""
    tif = _render(tmp_path, "-ii1", "-pA4", "-t300", "-P", "-L", "-m8")
    w, h = Image.open(tif).size
    assert w < 2480 and h < 3508             # cropped: margin removed from raster

    bare = measure_margins(tif, dpi=300)                       # no paper size
    fixed = measure_margins(tif, dpi=300, paper_w_mm=210, paper_h_mm=297)
    assert bare is not None and fixed is not None
    # Without the paper size the left margin reads ~0 (patch hugs the crop edge);
    # with it, the trimmed 8 mm is added back.
    assert bare.left_mm == pytest.approx(0, abs=1.5)
    assert fixed.left_mm == pytest.approx(8, abs=1.5)
    assert fixed.page_w_mm == pytest.approx(210, abs=0.5)


@requires_argyll
def test_landscape_orientation_measured_in_tiff_frame(tmp_path):
    """Margins are reported in printtarg (TIFF) orientation — a landscape sheet
    is wider than tall and still resolves a patch area."""
    tif = _render(tmp_path, "-ii1", "-p420x297", "-t300", "-P", "-L", "-M8")
    r = measure_margins(tif, dpi=300, ti2_path=tif.with_suffix(".ti2"))
    assert r is not None
    assert r.page_w_mm > r.page_h_mm         # landscape in the TIFF
    # All margins are non-negative and the opposite pair fits inside the sheet
    # (a small patch set on a big sheet legitimately leaves a large margin).
    for v in (r.left_mm, r.right_mm, r.top_mm, r.bottom_mm):
        assert v >= 0
    assert r.left_mm + r.right_mm < r.page_w_mm
    assert r.top_mm + r.bottom_mm < r.page_h_mm


# ColorMunki double-density charts the margin readout is pinned against. They
# were Knut's "Full layout setup" built-ins until his 2026-08-16 ColorMunki
# rework replaced that family; the .ti1 files moved here, and the printtarg
# flags each preset used are spelled out below, so these tests still measure the
# very same sheets they were written against.
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "charts"
_CM_A4_480P = ("cm_a4_480p_2pages.ti1",
               ["-iCM", "-pA4", "-t300", "-h", "-a0.93", "-M6", "-P"])
_CM_A3_1575P = ("cm_a3_1575p_3pages.ti1",
                ["-iCM", "-pA3", "-t300", "-h", "-a0.94", "-M6", "-P"])


def _measure_preset(tmp_path, chart, dpi: int = 300):
    """Lay a bundled ColorMunki .ti1 out with printtarg and measure every page."""
    name, args = chart
    shutil.copy(_FIXTURES / name, tmp_path / "chart.ti1")
    subprocess.run([PRINTTARG, *args, "chart"],
                   cwd=tmp_path, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reports = [measure_margins(t, dpi=dpi, ti2_path=tmp_path / "chart.ti2")
               for t in sorted(tmp_path.glob("chart*.tif"))]
    return name, [r for r in reports if r is not None]


@requires_argyll
def test_colormunki_a4_preset_margins_not_inflated(tmp_path):
    """#83: a ColorMunki A4 2-page preset must measure small, sane margins from
    its full-page (-M) TIFF — NOT the inflated values seen when a wrong paper
    size was fed in (the bug was passing a stale A3 paper combo → +43/+61 mm)."""
    _, reports = _measure_preset(tmp_path, _CM_A4_480P)
    assert reports
    for r in reports:
        assert r.page_w_mm == pytest.approx(210, abs=1.5)
        assert r.page_h_mm == pytest.approx(297, abs=1.5)
        assert r.left_mm < 15 and r.right_mm < 25     # not the 49/56 mm bug
        assert r.top_mm < 55 and r.bottom_mm < 55     # not the 102/94 mm bug


@requires_argyll
def test_wrong_paper_size_would_inflate_but_default_does_not(tmp_path):
    """Documents the #83 fix: measuring with no paper size (trusting the -M
    full-page TIFF) gives the true margins; feeding a too-large paper size adds
    a bogus (paper − tiff)/2 offset. The tab must therefore not pass a paper
    size that may be stale."""
    preset, _ = _measure_preset(tmp_path, _CM_A4_480P)
    tif = sorted(tmp_path.glob("chart*.tif"))[0]
    good = measure_margins(tif, dpi=300)
    inflated = measure_margins(tif, dpi=300, paper_w_mm=297, paper_h_mm=420)
    assert good.left_mm < 15
    assert inflated.left_mm == pytest.approx(good.left_mm + (297 - 210) / 2, abs=1.0)


@requires_argyll
def test_strip_length_is_page_minus_top_bottom(tmp_path):
    """#87: strip length = patch-block extent in the reading direction =
    page height − top − bottom on a portrait chart."""
    _, reports = _measure_preset(tmp_path, _CM_A4_480P)
    assert reports
    for r in reports:
        assert r.strip_length_mm is not None
        assert r.strip_length_mm == pytest.approx(
            r.page_h_mm - r.top_mm - r.bottom_mm, abs=0.2)
        assert 150 < r.strip_length_mm < 260


@requires_argyll
def test_landscape_strips_still_vertical(tmp_path):
    """#87: printtarg lays strips vertically even on a landscape page, so strip
    length is the vertical extent (page height − top − bottom) and patch width
    is block width ÷ strip count — both measured in the preview frame, not
    swapped by orientation."""
    work = tmp_path / "chart.ti1"
    src = _FIXTURES / "cm_a3_1224p_2pages_landscape.ti1"
    shutil.copy(src, work)
    subprocess.run([PRINTTARG, "-iCM", "-p420x297", "-t200", "-h", "-a0.9",
                    "-M6", "-P", "chart"], cwd=tmp_path, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tif = sorted(tmp_path.glob("chart_*.tif"))[0]
    r = measure_margins(tif, dpi=200, ti2_path=tmp_path / "chart.ti2")
    assert r.page_w_mm > r.page_h_mm                      # landscape sheet
    assert r.strip_length_mm == pytest.approx(
        r.page_h_mm - r.top_mm - r.bottom_mm, abs=0.2)    # vertical extent
    assert 10 < r.strip_width_mm < 15                     # ~12.5 mm, not ~swapped


@requires_argyll
def test_patch_width_is_cross_strip_pitch(tmp_path):
    """#83: the patch-width readout is the strip pitch across the strips
    (block_w/passes on a portrait page) — a ruler measurement across a strip,
    ~12.7 mm for the ColorMunki A4 double-density chart, not the ~14 mm
    reading-direction pitch the old squareness heuristic returned."""
    _, reports = _measure_preset(tmp_path, _CM_A4_480P)
    assert reports
    for r in reports:
        assert r.strip_width_mm == pytest.approx(12.7, abs=0.6)


@requires_argyll
def test_zigzag_top_bottom_consistent_across_pages(tmp_path):
    """#91: a ColorMunki double-density (-h) chart lays strips in a zig-zag, so the
    outermost row has ~half the strips (fill ≈ 0.5). The patch-area top/bottom must
    still include those half-rows and read the same on every page, instead of
    flipping by parity (page 2 used to read a too-large top/bottom)."""
    _, reports = _measure_preset(tmp_path, _CM_A3_1575P)
    assert len(reports) >= 2
    tops = [r.top_mm for r in reports]
    bottoms = [r.bottom_mm for r in reports]
    assert max(tops) - min(tops) < 1.5, f"top varies across pages: {tops}"
    assert max(bottoms) - min(bottoms) < 1.5, f"bottom varies across pages: {bottoms}"


def test_dense_run_stops_at_white_gap_before_label():
    """#91 follow-up: the rotated strip-label / title column sits past a strip of
    bare paper on the edge. ``_dense_run`` must stop at the real patch edge, not
    reach across the white gap into that sparse band (which inflated the right
    margin / mis-placed the guide line). Runs without Argyll."""
    from workflow.margin_inspector import _dense_run
    fill = np.zeros(100)
    fill[10:60] = 0.95          # dense patch block
    fill[60] = 0.45             # one zig-zag half-cell at the edge (kept)
    # 61..69 stay white (the bare-paper gap), then a sparse label band:
    fill[70:90] = 0.15
    a, b = _dense_run(fill)
    assert (a, b) == (10, 60)   # patch edge incl. the half-cell, label excluded


def test_blank_page_returns_none(tmp_path):
    """A bare white sheet has no patch area → None (caller shows a placeholder),
    not bogus numbers. Runs without Argyll."""
    blank = tmp_path / "white.tif"
    Image.fromarray(np.full((600, 400, 3), 255, np.uint8)).save(blank, dpi=(300, 300))
    assert measure_margins(blank, dpi=300) is None
    assert _patch_area_bbox(np.full((600, 400, 3), 255, np.uint8)) is None


def test_measure_from_engine_exact_geometry(tmp_path):
    """Engine charts report EXACT margins / patch width from channels.json, so a
    Strip gap (which inflates the strip pitch) no longer corrupts the reading the
    way image detection did (#93, Knut). 300 dpi, A4, two strips of 8 mm patches
    with a wide pitch (patch 8 mm but 14 mm apart)."""
    import json
    from workflow.margin_inspector import measure_from_engine
    mm = 300 / 25.4
    def px(v):
        return round(v * mm)
    # two strips, patches 8 mm wide, 14 mm apart (pitch != width), 26 mm left clip
    rects = []
    for col, x_mm in enumerate((26.0, 40.0)):
        for row in range(5):
            rects.append({"page": 0, "x": px(x_mm), "y": px(20.0 + row * 9.0),
                          "w": px(8.0), "h": px(8.0)})
    doc = {"layout": {"engine": "chromiq", "dpi": 300, "paper_mm": [210.0, 297.0],
                      "patches": rects, "recipe": {"instrument": "i1"}}}
    sc = tmp_path / "chart.channels.json"
    sc.write_text(json.dumps(doc))
    out = measure_from_engine(sc, 0)
    assert out is not None
    report, ruler = out
    assert abs(report.left_mm - 26.0) < 0.2          # clip border, exact
    assert abs(report.strip_width_mm - 8.0) < 0.2    # patch WIDTH, not the pitch
    assert abs(report.top_mm - 20.0) < 0.2
    assert ruler == 240.0                             # i1Pro ruler for the warning


def test_measure_from_engine_hex_expands_to_tips_and_edges(tmp_path):
    """#28 (Knut): SpectroScan hexagons are drawn beyond their slots — the apex
    reaches h/6 past the slot top/bottom, the ±w/4 stagger past the left/right
    sides. So the margins (and the guides they drive) must sit at the hex tips
    (top/bottom) and flat edges (left/right), not the slot box."""
    import json
    from workflow.margin_inspector import measure_from_engine
    mm = 200 / 25.4
    def px(v):
        return round(v * mm)
    w = h = px(7.0)                                  # 7 mm hex slot
    rects = []
    for col in range(3):
        for row in range(4):
            rects.append({"page": 0, "x": px(20.0) + col * w,
                          "y": px(15.0) + row * h, "w": w, "h": h})
    # rectangular reference (no hex): margins fall on the slot box.
    base = {"layout": {"engine": "chromiq", "dpi": 200, "paper_mm": [210.0, 297.0],
                       "patches": rects, "recipe": {"instrument": "i1"}}}
    scb = tmp_path / "rect.channels.json"; scb.write_text(json.dumps(base))
    r_rect, _ = measure_from_engine(scb, 0)

    hexdoc = {"layout": {"engine": "chromiq", "dpi": 200, "paper_mm": [210.0, 297.0],
                         "patches": rects,
                         "recipe": {"instrument": "SS", "hflag": True}}}
    sch = tmp_path / "hex.channels.json"; sch.write_text(json.dumps(hexdoc))
    r_hex, _ = measure_from_engine(sch, 0)

    px2mm = 25.4 / 200
    # hex margins are SMALLER than the slot margins by exactly the overhang.
    assert abs((r_rect.left_mm - r_hex.left_mm) - (w / 4) * px2mm) < 0.05
    assert abs((r_rect.right_mm - r_hex.right_mm) - (w / 4) * px2mm) < 0.05
    assert abs((r_rect.top_mm - r_hex.top_mm) - (h / 6) * px2mm) < 0.05
    assert abs((r_rect.bottom_mm - r_hex.bottom_mm) - (h / 6) * px2mm) < 0.05


def test_measure_from_engine_skips_printtarg_charts(tmp_path):
    """A non-engine (printtarg) channels.json returns None so the caller falls
    back to image measurement (#93)."""
    import json
    from workflow.margin_inspector import measure_from_engine
    sc = tmp_path / "p.channels.json"
    sc.write_text(json.dumps({"ink_channels": ["r", "g", "b"]}))
    assert measure_from_engine(sc, 0) is None
