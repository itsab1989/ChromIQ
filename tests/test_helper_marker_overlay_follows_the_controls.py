"""The preview overlay must follow the ruler-marker controls (#152, #158).

The dashes are printed on the sheet, but they are also drawn over the chart in
the preview so the two distances can be judged while they are being nudged.
That overlay reads the controls directly — and when #158 moved those controls
from the preview panel into the Manual layout panel, the overlay kept calling
the old ones. The failure was invisible: a broad ``except`` turned the
AttributeError into "no dashes", which is exactly the symptom Knut reported for
#152 (*"Enabling 'Show helper markers…' checkbox does nothing. No markers become
visible in preview."*).

An on-screen driver found it; these tests keep it found.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from core.resource_path import resource_path  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab_with_chart(qapp, tmp_path):
    """A real engine-built chart loaded into the tab, as after Generate Chart."""
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import KNUT_PRESETS, TabChart
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._switch_mode("manual")

    preset = next(p for p in KNUT_PRESETS if p.slug.startswith("cm_a4_204p"))
    out = tmp_path / "chart"
    res, _ = build_from_recipe(resource_path(preset.ti1_asset), out,
                               LayoutRecipe.from_dict(preset.layout_recipe))
    tab._margin_tiffs = list(res.tiff_paths)
    tab._margin_ti2 = Path(res.ti2_path)
    # The overlay reads the chart's OWN recorded layout, which the tab's build
    # path writes beside the .ti2 (chart_creator._printtarg_done). build_from_recipe
    # doesn't, so write the same sidecar here — without it the overlay correctly
    # declines, and this fixture would prove nothing.
    import json
    Path(res.ti2_path).with_suffix(".channels.json").write_text(json.dumps({
        "layout": {                       # the shape from_channels_json expects
            "engine": "chromiq",
            "recipe": LayoutRecipe.from_dict(preset.layout_recipe).to_dict(),
            "seed": res.seed,
        }}), encoding="utf-8")
    return tab


def test_ticking_the_box_produces_overlay_lines(tab_with_chart):
    tab = tab_with_chart
    lp = tab._manual_layout_panel
    lp.helper_markers_cb.setChecked(False)
    assert tab._helper_marker_lines_frac() is None

    lp.helper_markers_cb.setChecked(True)
    lines = tab._helper_marker_lines_frac()
    assert lines, "ticking the box drew no dashes over the chart"
    # page fractions, so every coordinate is inside the sheet
    for x0, y0, x1, y1 in lines:
        assert 0.0 <= x0 <= 1.0 and 0.0 <= y0 <= 1.0
        assert 0.0 <= x1 <= 1.0 and 0.0 <= y1 <= 1.0


def test_the_overlay_honours_markers_per_patch(tab_with_chart):
    """The preview must not disagree with what will be printed."""
    tab = tab_with_chart
    lp = tab._manual_layout_panel
    lp.helper_markers_cb.setChecked(True)
    lp.helper_marker_per_patch.setValue(3)
    three = len(tab._helper_marker_lines_frac() or [])
    lp.helper_marker_per_patch.setValue(5)
    five = len(tab._helper_marker_lines_frac() or [])
    assert five > three, (
        f"raising the count added no dashes to the overlay ({three} -> {five})")


def test_the_overlay_follows_the_distances(tab_with_chart):
    tab = tab_with_chart
    lp = tab._manual_layout_panel
    lp.helper_markers_cb.setChecked(True)
    lp.helper_marker_edge.setValue(2.0)
    near = tab._helper_marker_lines_frac()
    lp.helper_marker_edge.setValue(8.0)
    far = tab._helper_marker_lines_frac()
    assert near and far and near != far, "moving the dashes did not move the overlay"


def test_nothing_reads_the_removed_preview_control(tab_with_chart):
    """The panel under the preview no longer owns these controls, and no code
    may reach for them — that AttributeError was swallowed once already."""
    mp = tab_with_chart._margin_panel
    for gone in ("helper_markers", "set_helper_markers",
                 "set_helper_markers_supported", "helper_markers_changed"):
        assert not hasattr(mp, gone), f"{gone} still on the preview panel"
