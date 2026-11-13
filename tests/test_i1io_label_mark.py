"""THE i1iO LABEL-OPTIONS MARK HAS ONE NAME AND SURVIVES EVERY PATH (review R1).

`LayoutRecipe.i1io_label_options`: True for every i1iO recipe this version
makes, False ONLY for an i1iO recipe read from disk that a version before
the label options saved (its stored dict has no mark). The second review
found the mark written as `i1io_legacy_labels` by `build_kwargs` and read as
`i1io_label_options` (default False) by `from_build_kwargs`, so every recipe
rebuilt from build kwargs (Guided's channels.json, Guided -> Manual, built-in
presets) counted as a 4.3.33 recipe: Manual showed a label style the sheet
did not print. Held here, for a modern and a legacy recipe alike, through
to_dict/from_dict, build_kwargs/from_build_kwargs, stored build kwargs, the
preset store, a chart's channels.json and a target's stored Create Chart
state, and that a legacy recipe shows, records and prints the same style.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


STYLE = dict(indicator_font="Inter", indicator_bold=True,
             underline_mode="black", indicator_align="center",
             label_style_explicit=True)


def _modern():
    from workflow.layout_engine.presets import LayoutRecipe
    return LayoutRecipe(instrument="IO2", paper="A4", **STYLE)


def _legacy():
    """An i1iO recipe as 4.3.33 stored it: no mark, another style."""
    from workflow.layout_engine.presets import LayoutRecipe
    d = _modern().to_dict()
    d.pop("i1io_label_options")
    return LayoutRecipe.from_dict(d)


def test_one_name_everywhere():
    from workflow.i1io import chart as C
    r = _modern()
    assert C.OPTIONS_KEY == "i1io_label_options"
    assert r.to_dict()[C.OPTIONS_KEY] is True
    assert r.build_kwargs()[C.OPTIONS_KEY] is True
    assert _legacy().build_kwargs()[C.OPTIONS_KEY] is False
    assert "i1io_legacy_labels" not in r.build_kwargs()


def test_what_this_version_makes_is_modern():
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    assert LayoutRecipe(instrument="IO2").i1io_label_options is True
    assert default_recipe("IO2", "A4").i1io_label_options is True
    # live build kwargs (Guided's, a built-in's) carry no mark: modern
    assert LayoutRecipe.from_build_kwargs(
        {"instrument": "IO2", "paper": "A4"}).i1io_label_options is True


@pytest.mark.parametrize("make", [_modern, _legacy])
def test_every_round_trip_keeps_the_mark(make, tmp_path):
    from workflow.layout_engine.presets import LayoutRecipe, PresetStore
    r = make()
    want = r.i1io_label_options
    assert LayoutRecipe.from_dict(r.to_dict()).i1io_label_options is want
    assert LayoutRecipe.from_build_kwargs(
        r.build_kwargs()).i1io_label_options is want
    # build kwargs stored on disk (an old channels.json shape)
    assert LayoutRecipe.from_dict(r.build_kwargs()).i1io_label_options is want
    store = PresetStore()
    store._presets["k"] = r
    back = PresetStore.from_dict(json.loads(json.dumps(store.to_dict())))
    assert back._presets["k"].i1io_label_options is want
    ch = tmp_path / "c.channels.json"
    ch.write_text(json.dumps({"layout": {"engine": "chromiq",
                                         "recipe": r.to_dict()}}),
                  encoding="utf-8")
    assert LayoutRecipe.from_channels_json(ch).i1io_label_options is want


def test_a_legacy_recipe_shows_records_and_prints_one_style():
    """What 4.3.33 printed for the controls it ignored is what the recipe
    holds once read: default patterns, no underline, Left, the line's face;
    the label face stays (4.3.33 printed the patch numbers in it)."""
    from workflow.i1io import chart as C
    r = _legacy()
    assert r.i1io_label_options is False
    assert (r.underline_mode, r.indicator_align, r.strip_pattern,
            r.chart_text_font) == ("off", "left", "A-Z, A-Z", "Inter")
    assert r.indicator_font == "Inter"
    kw = r.build_kwargs()
    assert C.label_wishes(kw) == C.Labels()
    assert C.text_style_of(kw) is None


@pytest.fixture
def chart_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    yield tab
    tab.deleteLater()


@pytest.mark.parametrize("make", [_modern, _legacy])
def test_a_targets_stored_state_keeps_the_mark(chart_tab, make):
    """The per-target Create Chart state (`_collect_ui_state` /
    `_apply_ui_state`), through JSON as meta.json holds it."""
    from PyQt6.QtWidgets import QApplication
    tab = chart_tab
    tab._switch_mode("manual")
    tab._init_manual_layout_panel()
    panel = tab._manual_layout_panel
    panel.instr.setCurrentIndex(panel.instr.findData("IO2"))
    QApplication.processEvents()
    panel.set_recipe(make())
    QApplication.processEvents()
    want = make().i1io_label_options
    state = json.loads(json.dumps(tab._collect_ui_state()))
    stored = state.get("engine_recipe") or {}
    assert stored.get("i1io_label_options") is want
    tab._apply_ui_state(state)
    QApplication.processEvents()
    assert panel.get_recipe().i1io_label_options is want
