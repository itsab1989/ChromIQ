"""4.3.25, the owner's second round of FD-9 feedback, F11 (Knut's finding):
a built-in preset made for another instrument, loaded while the FD-9 (or the
CR30) is chosen, switches the instrument as it does from the i1Pro, instead
of being laid out as an FD-9 chart with the preset's stale page count and
its helper markers drawn over the preview.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import pytest


@pytest.fixture
def tab(qapp, qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(t)
    t._switch_mode("manual")
    built = []
    monkeypatch.setattr(t, "_generate_from_ti1",
                        lambda *a, **k: built.append(a) or True)
    t._built = built
    return t


def _choose(tab, inst):
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData(inst))
    tab._refresh_manual_command_preview()


def _key(fragment):
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
    return next(k for k in KNUT_PRESETS_BY_KEY if fragment in k)


def _pick(tab, key):
    cb = tab._preset_combo
    i = cb.findData(key)
    assert i >= 0, key
    cb.blockSignals(True)
    cb.setCurrentIndex(i)
    cb.blockSignals(False)
    tab._on_preset_selected(i)
    tab._refresh_manual_command_preview()


@pytest.mark.parametrize("start", ["FD9", "CR30", "i1"])
def test_knuts_sequence_a_colormunki_preset_switches_the_instrument(
        tab, start, monkeypatch):
    """Manual, the FD-9 (or the CR30, or the i1Pro for comparison), then
    "★ ColorMunki · A4-2142p-7pages-…": the chart is the ColorMunki's."""
    from PyQt6.QtWidgets import QDialog
    import ui.tabs.tab_chart as TC
    monkeypatch.setattr(TC.QDialog, "exec",
                        lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr("ui.dialogs.name_prompt.ask_for_project_name",
                        lambda *a, **k: "F11-Knut")
    _choose(tab, start)
    assert tab._manual_get("printtarg", "-i", "") == start
    _pick(tab, _key("cm_a4_2142p_7pages"))
    assert tab._built, "the preset was applied"
    assert tab._manual_get("printtarg", "-i", "") == "CM"
    panel = tab._manual_layout_panel
    if tab._manual_panel_lays_out():
        assert panel.instr.currentData() == "CM"


def test_every_builtin_names_an_instrument_or_keeps_the_chosen_one(tab):
    from ui.tabs.tab_chart import (BUILTIN_PRESET_KEYS, MUNKI_TARGEN,
                                   TC918_PRESET_KEY)
    for key in sorted(BUILTIN_PRESET_KEYS | set(MUNKI_TARGEN)):
        inst = tab._builtin_preset_instrument(key)
        if key == TC918_PRESET_KEY:
            assert inst is None
        else:
            assert inst in ("i1", "p3", "CM", "SS", "CR30"), key


@pytest.mark.slow          # every bundled patch set laid out for the FD-9
def test_every_builtin_loaded_on_the_fd9_leaves_a_chart_the_fd9_can_read(
        tab, tmp_path):
    """Every built-in preset loaded while the FD-9 is chosen: either the
    instrument moved to the preset's (and nothing FD-9 is built), or, for a
    preset that keeps the chosen instrument (TC9.18), the FD-9 chart of its
    patch set passes the detector check on every page (F4), with and without
    the clip border."""
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import BUILTIN_PRESET_KEYS, TC918_PRESET_KEY
    from workflow.fd9.chart import build_chart
    kept = []
    for key in sorted(BUILTIN_PRESET_KEYS | {TC918_PRESET_KEY}):
        from ui.tabs.tab_chart import DISABLED_BUILTIN_PRESET_KEYS
        if key in DISABLED_BUILTIN_PRESET_KEYS:
            continue
        _choose(tab, "FD9")
        tab._leave_engine_only_for_builtin(key)
        inst = tab._builtin_preset_instrument(key)
        now = tab._manual_get("printtarg", "-i", "")
        if inst is None:
            assert now == "FD9"
            kept.append(key)
        else:
            assert now == inst, key
            assert tab._manual_layout_panel.instr.currentData() == inst, key
    assert kept
    # …and whatever patch set a preset brings, the FD-9's own layout of it
    # is a chart the FD-9 finds on every page: `build_chart` runs the
    # detector check (F4) and refuses otherwise.
    assets = sorted({tab._builtin_ti1_asset(k) for k in BUILTIN_PRESET_KEYS
                     | {TC918_PRESET_KEY}} - {None})
    built = 0
    for n, asset in enumerate(assets):
        path = resource_path(asset)
        if not path.is_file():
            continue
        # With the clip border on, the label is printed too: everything
        # ChromIQ adds is on the sheet at once.
        r = build_chart(path, tmp_path / f"k{n}", paper="A4", dpi=72,
                        clip_border=True, sheet_project="P", sheet_run="1")
        assert r.tiff_paths
        built += 1
    assert built >= 10


def test_a_greyed_pages_box_shows_the_fd9_charts_own_page_count(tab):
    _choose(tab, "FD9")
    panel = tab._manual_layout_panel
    panel.set_pages(7)
    panel.set_pages_enabled(False)
    tab._show_fd9_page_count(["p1.tif", "p2.tif", "p3.tif"])
    assert panel.get_pages() == 3
    panel.set_pages_enabled(True)
    tab._show_fd9_page_count(["p1.tif"])
    assert panel.get_pages() == 3            # a live box is the person's


def test_the_preview_draws_no_helper_markers_over_an_fd9_chart(tab, tmp_path):
    import json
    from workflow.layout_engine.presets import LayoutRecipe
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    rec = LayoutRecipe(instrument="FD9", paper="A4", helper_markers=True)
    ti2.with_suffix(".channels.json").write_text(json.dumps(
        {"layout": {"engine": "chromiq", "recipe": rec.to_dict()}}), encoding="utf-8")
    tab._margin_tiffs = [tmp_path / "c.tif"]
    tab._margin_ti2 = ti2
    _choose(tab, "FD9")
    assert tab._helper_marker_lines_frac() is None
