"""The Measure-tab highlighter reads exact strip geometry from an engine
chart's channels.json (issue #93) instead of detecting stripes from the image."""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from tests.argyll_env import argyll_tool
from ui.tabs.tab_measure import engine_strip_rects_from_sidecar


def _channels_with_layout(path: Path, *, dpi=300, **extra) -> None:
    layout = {
        "dpi": dpi, "steps_in_pass": 21,
        "strips": [
            {"page": 0, "pass": 0, "x": 100, "y": 200, "w": 50, "h": 1300},
            {"page": 0, "pass": 1, "x": 160, "y": 200, "w": 50, "h": 1300},
            {"page": 1, "pass": 0, "x": 100, "y": 200, "w": 50, "h": 900},
        ],
        "patches": [], "seed": 42,
    }
    layout.update(extra)
    path.write_text(json.dumps({"ink_channels": ["r", "g", "b"], "layout": layout}), encoding="utf-8")


def test_reads_engine_geometry(tmp_path: Path):
    sc = tmp_path / "chart.channels.json"
    _channels_with_layout(sc)
    result = engine_strip_rects_from_sidecar(sc, n_pages=2)
    assert result is not None
    per_page, counts, arrow_mode = result
    assert counts == [2, 1]
    assert per_page[0][0].x() == 100 and per_page[0][0].width() == 50
    assert per_page[1][0].height() == 900
    # legacy sidecar (no band key, no recipe) keeps the old base behaviour
    assert arrow_mode == "base"
    assert per_page[0][0].y() == 200


def test_arrow_hangs_under_label_band(tmp_path: Path):
    """Labels ON: rect grows up to the stored label-band bottom, base mode."""
    sc = tmp_path / "chart.channels.json"
    _channels_with_layout(sc, label_band_bottom_px=140)
    per_page, _counts, arrow_mode = engine_strip_rects_from_sidecar(sc, 2)
    assert arrow_mode == "base"
    r = per_page[0][0]
    assert r.y() == 140                      # anchored under the labels
    assert r.height() == 1300 + (200 - 140)  # bottom edge unchanged


def test_arrow_tip_mode_without_labels(tmp_path: Path):
    """Labels OFF: band key stored as null → tip mode, patch-top anchor."""
    sc = tmp_path / "chart.channels.json"
    _channels_with_layout(sc, label_band_bottom_px=None)
    per_page, _counts, arrow_mode = engine_strip_rects_from_sidecar(sc, 2)
    assert arrow_mode == "tip"
    assert per_page[0][0].y() == 200
    assert per_page[0][0].height() == 1300


def test_arrow_tip_mode_old_sidecar_recipe_says_off(tmp_path: Path):
    """Old sidecar without the band key but whose recipe disabled indicators."""
    sc = tmp_path / "chart.channels.json"
    _channels_with_layout(sc, recipe={"draw_indicators": False})
    _per, _counts, arrow_mode = engine_strip_rects_from_sidecar(sc, 2)
    assert arrow_mode == "tip"


def test_band_below_strip_top_is_ignored(tmp_path: Path):
    """A band bottom at/below the patch top must never shrink the rect."""
    sc = tmp_path / "chart.channels.json"
    _channels_with_layout(sc, label_band_bottom_px=250)
    per_page, _counts, arrow_mode = engine_strip_rects_from_sidecar(sc, 2)
    assert arrow_mode == "base"
    assert per_page[0][0].y() == 200 and per_page[0][0].height() == 1300


def test_none_without_layout(tmp_path: Path):
    sc = tmp_path / "chart.channels.json"
    sc.write_text(json.dumps({"ink_channels": ["r", "g", "b"]}), encoding="utf-8")  # legacy chart
    assert engine_strip_rects_from_sidecar(sc, 1) is None


def test_none_when_page_uncovered(tmp_path: Path):
    sc = tmp_path / "chart.channels.json"
    _channels_with_layout(sc)
    # only pages 0 and 1 present; asking for 3 pages → not every page covered
    assert engine_strip_rects_from_sidecar(sc, 3) is None


def test_missing_file(tmp_path: Path):
    assert engine_strip_rects_from_sidecar(tmp_path / "nope.channels.json", 1) is None


@pytest.mark.parametrize("draw_indicators", [True, False])
def test_real_engine_chart_roundtrip(tmp_path: Path, draw_indicators: bool):
    """Build a real engine chart and confirm the highlighter geometry matches."""
    targen = argyll_tool("targen")
    if targen is None:
        pytest.skip("ArgyllCMS targen not available")
    import subprocess
    from workflow.layout_engine import chart, geometry, instruments, papers
    base = tmp_path / "chart"
    subprocess.run([str(targen), "-d2", "-f120", str(base)], check=True,
                   capture_output=True)
    res = chart.build_chart(f"{base}.ti1", base, instrument="i1", paper="A4",
                            seed=1, dpi=150, draw_indicators=draw_indicators)
    sc = base.with_suffix(".channels.json")
    # channels.json doesn't exist yet (build_chart writes .strips.json); emulate
    # the chart_creator embed step for this headless path:
    strips = json.loads((base.with_suffix(".strips.json")).read_text(encoding="utf-8"))
    sc.write_text(json.dumps({"ink_channels": ["r", "g", "b"], "layout": strips}), encoding="utf-8")

    out = engine_strip_rects_from_sidecar(sc, res.layout.pages)
    assert out is not None
    per_page, counts, arrow_mode = out
    # one strip-rect per pass on the (single) page
    assert counts[0] == res.layout.passes
    patch_top = res.strip_rects[0]["y"]
    if draw_indicators:
        # arrow hangs under the rendered label band, above the patches
        assert arrow_mode == "base"
        assert strips["label_band_bottom_px"] is not None
        assert 0 < per_page[0][0].y() <= patch_top
        assert per_page[0][0].y() == strips["label_band_bottom_px"]
    else:
        assert arrow_mode == "tip"
        assert strips["label_band_bottom_px"] is None
        assert per_page[0][0].y() == patch_top
