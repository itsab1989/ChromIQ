"""THE i1iO's "AIMING CROSSES" IN MANUAL AND GUIDED (Beta).

The owner, 2026-11-13: Guided gets the option too; in Manual it stands where
"Print helper markers" stands (an i1iO chart prints no helper markers);
"all options must be savable as defaults and as part of a preset". Held here:

* Manual: the box and its (i) take the helper markers' slot while the i1iO is
  chosen, the margins follow it (the paper the crosses held goes to
  patches), the recipe carries it, and leaving the i1iO puts everything back;
* Guided: the box on the instrument's own option line, the patch count and
  the build follow it, its row and Save as Defaults keep it across a restart;
* presets: a recipe round trip keeps it, a preset of another instrument
  leaves it alone, and margins below the i1iO's minimum are raised.
"""
from __future__ import annotations

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


def _tab(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return TabChart(ArgyllRunner(s), FileManager(s), s), s


@pytest.fixture
def chart_tab(qapp, tmp_path):
    t, _s = _tab(tmp_path)
    yield t
    t.close()
    t.deleteLater()


def _panel_on_i1io(tab):
    tab._init_manual_layout_panel()
    panel = tab._manual_layout_panel
    panel.instr.setCurrentIndex(panel.instr.findData("IO2"))
    return panel


def test_manual_the_box_takes_the_helper_markers_slot(chart_tab):
    panel = chart_tab._manual_layout_panel or None
    chart_tab._init_manual_layout_panel()
    panel = chart_tab._manual_layout_panel
    grid = panel._hm_grid
    grp = panel._helper_markers_grp
    title = grp.title()
    # the same grid cells as "Print helper markers" and its (i)
    assert grid.itemAtPosition(0, 0) is not None
    idx_cb = grid.indexOf(panel.i1io_crosses_cb)
    idx_hm = grid.indexOf(panel.helper_markers_cb)
    assert grid.getItemPosition(idx_cb)[:2] == grid.getItemPosition(idx_hm)[:2]
    idx_tip = grid.indexOf(panel._i1io_crosses_tip)
    assert grid.getItemPosition(idx_tip)[:2] == (0, 2)
    assert not panel.i1io_crosses_cb.isVisibleTo(grp)
    panel.instr.setCurrentIndex(panel.instr.findData("IO2"))
    assert panel.i1io_crosses_cb.isVisibleTo(grp)
    assert panel.i1io_crosses_cb.isEnabled()
    assert panel._i1io_crosses_tip.isVisibleTo(grp)
    assert not panel.helper_markers_cb.isVisibleTo(grp)
    assert all(not w.isVisibleTo(grp) for row in panel._hm_rows for w in row)
    assert grp.title() == "Aiming marks"
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    assert grp.title() == title
    assert panel.helper_markers_cb.isVisibleTo(grp)
    assert not panel.i1io_crosses_cb.isVisibleTo(grp)


def test_manual_the_margins_and_the_recipe_follow_the_box(chart_tab):
    from workflow.i1io import chart
    panel = _panel_on_i1io(chart_tab)
    assert panel.margins["r"].value() == 15.0
    assert chart.capacity(panel.get_recipe().build_kwargs(), True) == 528
    panel.i1io_crosses_cb.setChecked(False)
    assert panel.margins["r"].minimum() == 5.0
    assert panel.margins["r"].value() == 5.0
    r = panel.get_recipe()
    assert r.i1io_crosses is False and r.margin_right == 5.0
    kw = r.build_kwargs()
    assert kw["i1io_crosses"] is False
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm("A4")
    assert geometry.patches_per_sheet(
        instruments.geom_from_build_kwargs(kw), w, h) == 552
    # back on: the crosses' band again
    panel.i1io_crosses_cb.setChecked(True)
    assert panel.margins["r"].value() == 15.0
    assert panel.get_recipe().i1io_crosses is True
    assert "i1io_crosses" not in panel.get_recipe().build_kwargs()


def test_manual_leaving_and_coming_back_restores_the_layout(chart_tab):
    panel = chart_tab._manual_layout_panel or None
    chart_tab._init_manual_layout_panel()
    panel = chart_tab._manual_layout_panel
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    before = {k: b.value() for k, b in panel.margins.items()}
    panel.instr.setCurrentIndex(panel.instr.findData("IO2"))
    panel.i1io_crosses_cb.setChecked(False)
    io = {k: b.value() for k, b in panel.margins.items()}
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    assert {k: b.value() for k, b in panel.margins.items()} == before
    panel.instr.setCurrentIndex(panel.instr.findData("IO2"))
    assert panel.i1io_crosses_cb.isChecked() is False
    assert {k: b.value() for k, b in panel.margins.items()} == io


def test_a_recipe_and_a_preset_keep_the_answer(chart_tab):
    from workflow.layout_engine.presets import LayoutRecipe
    panel = _panel_on_i1io(chart_tab)
    panel.i1io_crosses_cb.setChecked(False)
    d = panel.get_recipe().to_dict()
    assert d["i1io_crosses"] is False
    # a fresh panel state, then the preset
    panel.i1io_crosses_cb.setChecked(True)
    panel.set_recipe(LayoutRecipe.from_dict(d))
    assert panel.i1io_crosses_cb.isChecked() is False
    assert panel.margins["r"].value() == 5.0
    # build kwargs round trip (a chart's stored kwargs)
    r2 = LayoutRecipe.from_build_kwargs(LayoutRecipe.from_dict(d)
                                        .build_kwargs())
    assert r2.i1io_crosses is False
    # every other recipe writes exactly what it did
    i1 = LayoutRecipe(instrument="i1").to_dict()
    assert "i1io_crosses" not in i1
    assert "i1io_crosses" not in LayoutRecipe(instrument="i1").build_kwargs()


def test_a_preset_of_another_instrument_never_leaks_into_the_i1io(chart_tab):
    """Margins of an i1Pro preset loaded for the i1iO are raised to the
    i1iO's minimum (the existing rule), with the crosses and without."""
    from dataclasses import replace
    from workflow.layout_engine.presets import LayoutRecipe
    panel = _panel_on_i1io(chart_tab)
    small = replace(LayoutRecipe(instrument="IO2", paper="A4"),
                    margin_top=2.0, margin_right=2.0, margin_bottom=2.0,
                    margin_left=2.0, use_instrument_margins=False)
    panel.set_recipe(small)
    r = panel.get_recipe()
    assert (r.margin_right, r.margin_left) == (15.0, 16.0)
    panel.set_recipe(replace(small, i1io_crosses=False))
    r = panel.get_recipe()
    assert (r.margin_right, r.margin_left) == (5.0, 16.0)
    # an i1Pro preset: the crosses box keeps its own answer for the i1iO
    panel.set_recipe(LayoutRecipe(instrument="i1", paper="A4"))
    assert panel.get_recipe().instrument == "i1"
    assert panel.get_recipe().i1io_crosses is True


def test_guided_shows_the_box_for_the_i1io_only(chart_tab):
    tab = chart_tab
    assert tab._i1io_aim_check.text() == "Aiming crosses"
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("i1"))
    assert not tab._i1io_aim_check.isVisibleTo(tab)
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("IO2"))
    tab._update_dd_visibility()
    assert tab._i1io_aim_check.isVisibleTo(tab)
    assert tab._i1io_aim_tooltip.isVisibleTo(tab)
    assert tab._i1io_aim_check.isChecked()


def test_guided_the_count_and_the_build_follow_the_box(chart_tab):
    tab = chart_tab
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("IO2"))
    p = tab._collect_guided()
    assert p.i1io_crosses is True
    assert tab._creator._engine_total_patches(p) == 528
    tab._i1io_aim_check.setChecked(False)
    p = tab._collect_guided()
    assert p.i1io_crosses is False
    assert tab._creator._engine_total_patches(p) == 552
    assert tab._creator._engine_build_kwargs(p)["i1io_crosses"] is False
    from workflow.layout_engine import geometry, papers
    w, h = papers.dimensions_mm("A4")
    geom = tab._engine_geom("IO2", "A4", dd=False, td=False, eff_lb=True,
                            nsl=False, pscale=1.0, margin=6.0, guided=True)
    assert geometry.patches_per_sheet(geom, w, h) == 552
    # the run's Guided row keeps it, and gives it back
    row = tab._shared_get("guided")
    assert row["i1io_crosses"] is False
    tab._i1io_aim_check.setChecked(True)
    tab._shared_set("guided", "i1io_crosses", row["i1io_crosses"])
    assert tab._i1io_aim_check.isChecked() is False
    # other instruments' rows are as they were
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("i1"))
    assert "i1io_crosses" not in tab._shared_get("guided")


def test_guided_save_as_defaults_survives_a_restart(qapp, tmp_path):
    tab, s = _tab(tmp_path)
    try:
        tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("IO2"))
        tab._i1io_aim_check.setChecked(False)
        tab._on_save_defaults()
        assert s.get("chart_i1io_crosses", True) is False
        tab._i1io_aim_check.setChecked(True)
        tab._restore_defaults_impl()
        assert tab._i1io_aim_check.isChecked() is False
    finally:
        tab.close()
        tab.deleteLater()
    again, s2 = _tab(tmp_path)
    try:
        again._restore_defaults_impl()
        assert again._i1io_aim_check.isChecked() is False
        assert again._instr_combo.currentData() == "IO2"
    finally:
        again.close()
        again.deleteLater()


def test_with_the_beta_off_the_saved_answer_is_kept_and_not_used(qapp,
                                                                  tmp_path):
    from workflow.i1io import support
    tab, s = _tab(tmp_path)
    try:
        tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("IO2"))
        tab._i1io_aim_check.setChecked(False)
        tab._on_save_defaults()
    finally:
        tab.close()
        tab.deleteLater()
    support.set_enabled_for_this_process(False)
    off, s2 = _tab(tmp_path)
    try:
        assert getattr(off, "_i1io_aim_check", None) is None
        off._restore_defaults_impl()
        off._instr_combo.setCurrentIndex(off._instr_combo.findData("i1"))
        off._on_save_defaults()
        # untouched by a save with the Beta off
        assert s2.get("chart_i1io_crosses", True) is False
    finally:
        off.close()
        off.deleteLater()
    support.set_enabled_for_this_process(True)
    back, _s3 = _tab(tmp_path)
    try:
        back._instr_combo.setCurrentIndex(back._instr_combo.findData("IO2"))
        back._restore_defaults_impl()
        assert back._i1io_aim_check.isChecked() is False
    finally:
        back.close()
        back.deleteLater()


def test_the_guided_help_is_live(chart_tab):
    tab = chart_tab
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("IO2"))
    src = tab._guided_i1io_crosses_source()
    from ui.dialogs.layout_options_panel import i1io_crosses_help
    kw = src.pop("kw")
    text = i1io_crosses_help(kw, **src)
    assert "528 patches with the crosses, 552 without them" in text
    assert "A1" in text


def test_manual_save_as_defaults_keeps_every_i1io_option(qapp, tmp_path):
    """Every i1iO option Manual exposes survives Save as Defaults and a
    restart: paper, patch size, spacers, both gaps, the labels and their
    size, the margins and the crosses."""
    tab, s = _tab(tmp_path)
    try:
        tab._switch_mode("manual")
        panel = _panel_on_i1io(tab)
        panel.paper.setCurrentIndex(panel.paper.findData("Letter"))
        panel.patch_y.setValue(12.0)
        panel.patch_x.setValue(9.0)
        panel.spacer_mode.setCurrentIndex(panel.spacer_mode.findData("bw"))
        panel.strip_gap.setValue(1.0)
        panel.inter_patch.setValue(1.5)
        panel.show_indicators.setChecked(False)
        panel.i1io_crosses_cb.setChecked(False)
        panel.margins["t"].setValue(20.0)
        want = panel.get_recipe()
        assert (want.paper, want.patch_h_mm, want.patch_w_mm,
                want.spacer_mode, want.strip_gap_mm, want.inter_patch_mm,
                want.show_strip_indicators, want.i1io_crosses,
                want.margin_top, want.margin_right) == (
            "Letter", 12.0, 9.0, "bw", 1.0, 1.5, False, False, 20.0, 5.0)
        tab._on_save_defaults()
    finally:
        tab.close()
        tab.deleteLater()
    again, _s = _tab(tmp_path)
    try:
        again._switch_mode("manual")
        again._restore_defaults_impl()
        again._init_manual_layout_panel()
        got = again._manual_layout_panel.get_recipe()
        for field in ("instrument", "paper", "patch_w_mm", "patch_h_mm",
                      "spacer_mode", "strip_gap_mm", "inter_patch_mm",
                      "show_strip_indicators", "i1io_crosses", "margin_top",
                      "margin_right", "margin_bottom", "margin_left"):
            assert getattr(got, field) == getattr(want, field), field
    finally:
        again.close()
        again.deleteLater()
