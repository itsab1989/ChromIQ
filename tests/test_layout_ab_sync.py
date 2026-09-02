"""Set A ↔ Set B layout sync (#92).

A chart preset stores its layout twice: Set A (the Create Chart → Manual
printtarg widgets / a chart's ``editor_layout``) and Set B (the creation
recipe's ``layout`` block, ``editor_recipe.layout``). These must never disagree.
The sync keeps Set B's *layout* in step with Set A while freezing the
generators, colour-set params, source mode and patch count.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import ti2_relayout as R  # noqa: E402
from workflow.chart_creator import ChartParams  # noqa: E402


def test_recipe_layout_from_options_maps_every_field():
    opts = R.LayoutOptions(
        spacer_mode="bw", patch_scale=1.15, spacer_scale=0.6, margin_mm=8,
        suppress_left_clip=True, no_strip_limit=True, double_density=True,
        triple_density=False, tiff_16bit=True, dpi=200,
    )
    assert R.recipe_layout_from_options(opts) == {
        "spacer_mode": "bw", "patch_scale": 1.15, "spacer_scale": 0.6,
        "margin": 8, "dpi": 200, "bit16": True,
        "L": True, "P": True, "h": True, "td": False,
    }


def test_save_editor_meta_freezes_generators_syncs_layout(tmp_path):
    """The synced recipe keeps mode / cb / sp / count, replaces only layout."""
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("", encoding="utf-8")
    spec = R.ChartSpec.new("CM", "A3")
    recipe = {
        "mode": "generate",
        "cb": {"cube": True, "skin": False},
        "sp": {"cube_n": 6, "fill_to": 1575},
        "count": 1575,
        "edges_auto": True,
        "layout": {"patch_scale": 9.99, "margin": 99},   # stale, must be replaced
    }
    opts = R.LayoutOptions(patch_scale=0.94, margin_mm=6, double_density=True,
                           no_strip_limit=True)
    R.save_editor_meta(ti2, spec, opts, "chart", recipe=recipe)
    loaded = R.load_editor_recipe(ti2)
    # Frozen design.
    assert loaded["mode"] == "generate"
    assert loaded["cb"] == {"cube": True, "skin": False}
    assert loaded["sp"] == {"cube_n": 6, "fill_to": 1575}
    assert loaded["count"] == 1575
    assert loaded["edges_auto"] is True
    # Layout replaced wholesale from the built options.
    assert loaded["layout"] == R.recipe_layout_from_options(opts)
    assert loaded["layout"]["patch_scale"] == 0.94
    assert loaded["instr"] == "CM" and loaded["paper"] == "A3"


def test_save_editor_meta_does_not_mutate_caller_recipe(tmp_path):
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("", encoding="utf-8")
    spec = R.ChartSpec.new("i1", "A4")
    recipe = {"mode": "generate", "sp": {"cube_n": 5},
              "layout": {"margin": 6}}
    before = {k: (dict(v) if isinstance(v, dict) else v) for k, v in recipe.items()}
    R.save_editor_meta(ti2, spec, R.LayoutOptions(margin_mm=12), "c", recipe=recipe)
    assert recipe == before          # caller's dict untouched (we copy)


# ---------------------------------------------------------------------------
# Manual Save Preset sync — _recipe_synced_to_manual on the tab
# ---------------------------------------------------------------------------

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _chart_tab(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    # These tests exercise the printtarg path explicitly — since 4.0.0
    # the ChromIQ layout engine is the Manual default (schema 18), so
    # the mode under test is pinned rather than inherited.
    s.set("use_chromiq_layout_engine", False)
    s.set("custom_output_path", str(tmp_path / "projects"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._switch_mode("manual")
    return tab


def test_recipe_synced_to_manual_refreshes_layout_freezes_generators(qapp, tmp_path, monkeypatch):
    tab = _chart_tab(tmp_path)
    # The Manual tab's current effective printtarg settings (Set A).
    monkeypatch.setattr(tab, "_collect_params", lambda: ChartParams(
        patch_scale=1.08, margin_mm=6, triple_density=True,
        no_strip_limit=True, disable_left_border=True, tiff_dpi=200))
    stale = {
        "mode": "generate",
        "cb": {"cube": True},
        "sp": {"cube_n": 7, "fill_to": 484},
        "count": 484,
        "layout": {"patch_scale": 0.5, "margin": 30, "td": False},  # stale
    }
    synced = tab._recipe_synced_to_manual(stale)
    # Generators / mode / count frozen.
    assert synced["mode"] == "generate"
    assert synced["cb"] == {"cube": True}
    assert synced["sp"] == {"cube_n": 7, "fill_to": 484}
    assert synced["count"] == 484
    # Layout now matches the manual widgets.
    assert synced["layout"]["patch_scale"] == 1.08
    assert synced["layout"]["margin"] == 6
    assert synced["layout"]["td"] is True
    assert synced["layout"]["P"] is True
    # Original recipe object not mutated.
    assert stale["layout"] == {"patch_scale": 0.5, "margin": 30, "td": False}
