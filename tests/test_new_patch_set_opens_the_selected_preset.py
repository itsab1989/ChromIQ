""""New Patch Set…" opens with the SELECTED preset's design (Knut, #182
5872273862).

*"Sometimes, when saving a preset and giving it a new name, after saving the
settings used for the patch set is not showing (a previous used is coming up
instead) when entering 'New Patch Set...'"*

Driven on screen (``scripts/drive_preset_save_new_patch_set.py``): the patch
set editor opens on the run's chart and took its design from the run's
meta.json, which only a build writes. An own preset is loaded when it is
chosen, not built, so choosing an older one after saving a new one opened
"New Patch Set…" with the NEWER design (cube 11 for a cube-9 preset); with no
chart on screen, with the app-wide last-used settings. And an own preset with
no design at all left the previous preset's design on the run when built.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings                          # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog           # noqa: E402

from core.argyll_runner import ArgyllRunner                 # noqa: E402
from core.settings import AppSettings                       # noqa: E402

CUBE_9 = {"mode": "generate", "cb": {"cube": True}, "sp": {"cube_n": 9},
          "instr": "i1", "paper": "A4"}
CUBE_11 = {"mode": "generate", "cb": {"cube": True}, "sp": {"cube_n": 11},
           "instr": "i1", "paper": "A4"}


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def presets_dir(tmp_path, monkeypatch):
    d = tmp_path / "presets"
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(d))
    return d


def _settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    return s


def _tab(tmp_path):
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart
    s = _settings(tmp_path)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._switch_mode("manual")
    return tab


def _choose(tab, name):
    ix = tab._preset_combo.findData(name)
    assert ix >= 0, name
    tab._preset_combo.setCurrentIndex(ix)
    tab._on_preset_selected(ix)


class _Capture:
    """Stands in for the New Patch Set window: records what it was given."""
    seen: list = []

    def __init__(self, *_a, initial_recipe=None, **_k):
        _Capture.seen.append(initial_recipe)

    def exec(self):
        return int(QDialog.DialogCode.Rejected)


def _editor(tmp_path, monkeypatch, **kw):
    from ui.dialogs import ti2_relayout_dialog as RD
    _Capture.seen = []
    monkeypatch.setattr(RD, "_NewChartDialog", _Capture)
    s = _settings(tmp_path)
    return RD.Ti2RelayoutDialog(ArgyllRunner(s), s, None, **kw)


# --- the editor ------------------------------------------------------------

def test_new_patch_set_opens_with_the_selected_preset_not_the_run(
        qapp, tmp_path, monkeypatch):
    dlg = _editor(tmp_path, monkeypatch, preset_recipe=CUBE_9)
    dlg._chart_recipe = dict(CUBE_11)     # what the run's meta.json says
    dlg._new_chart()
    assert _Capture.seen == [CUBE_9], (
        "New Patch Set… opened with the run's last build, not the preset "
        "selected in Create Chart")
    dlg.deleteLater()


def test_without_a_selected_design_the_chart_s_own_is_used(
        qapp, tmp_path, monkeypatch):
    dlg = _editor(tmp_path, monkeypatch)
    dlg._chart_recipe = dict(CUBE_11)
    dlg._new_chart()
    assert _Capture.seen == [CUBE_11]
    dlg.deleteLater()


def test_a_chart_loaded_in_the_editor_is_no_longer_the_preset_s(
        qapp, tmp_path, monkeypatch):
    from ui.dialogs import ti2_relayout_dialog as RD
    dlg = _editor(tmp_path, monkeypatch, preset_recipe=CUBE_9)
    monkeypatch.setattr(RD, "open_file_dialog",
                        lambda *a, **k: str(tmp_path / "other.ti2"))

    def load(path):
        dlg._chart_recipe = dict(CUBE_11)
        return True
    monkeypatch.setattr(dlg, "_load_chart_from", load)
    dlg._load_ti2()
    dlg._new_chart()
    assert _Capture.seen == [CUBE_11], (
        "a chart the person loaded here was shown with the preset's design")
    dlg.deleteLater()


def test_the_tools_menu_hands_the_design_through(qapp, tmp_path, monkeypatch):
    from ui.dialogs import tools_dialogs as TD
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    got = {}
    real = Ti2RelayoutDialog.__init__

    def init(self, *a, **k):
        got.update(k)
        real(self, *a, **k)
    monkeypatch.setattr(Ti2RelayoutDialog, "__init__", init)
    s = _settings(tmp_path)
    dlg = TD.build_tool_dialog("ti2_relayout", ArgyllRunner(s), s, None,
                               preset_recipe=CUBE_9)
    assert got.get("preset_recipe") == CUBE_9
    dlg.deleteLater()


# --- the Create Chart tab ---------------------------------------------------

def test_choosing_an_own_preset_offers_its_design(qapp, tmp_path, presets_dir):
    tab = _tab(tmp_path)
    presets = {"Cube 9": {"editor_recipe": CUBE_9},
               "Cube 11": {"editor_recipe": CUBE_11}}
    tab._save_presets_to_settings(presets)
    tab._populate_preset_combo(presets)
    _choose(tab, "Cube 11")
    _choose(tab, "Cube 9")
    assert tab.recipe_for_new_patch_set()["sp"] == {"cube_n": 9}


def test_an_own_preset_with_no_design_clears_the_record(
        qapp, tmp_path, presets_dir):
    """`None` in the slot means "ask the run", so building this preset kept the
    previous preset's design on the run, and New Patch Set… showed it."""
    tab = _tab(tmp_path)
    presets = {"Cube 11": {"editor_recipe": CUBE_11}, "Plain": {}}
    tab._save_presets_to_settings(presets)
    tab._populate_preset_combo(presets)
    _choose(tab, "Cube 11")
    _choose(tab, "Plain")
    from workflow.ti2_relayout import NO_RECIPE
    assert tab._pending_editor_recipe is NO_RECIPE
    assert tab.recipe_for_new_patch_set() is None


def test_the_main_window_passes_the_selected_design(qapp, tmp_path,
                                                     monkeypatch):
    from ui import main_window as MW
    from ui.dialogs import tools_dialogs as TD
    s = _settings(tmp_path)
    win = MW.MainWindow(s)
    got = {}
    monkeypatch.setattr(TD, "open_tool_dialog",
                        lambda *a, **k: got.update(k))
    win._tab_chart._pending_editor_recipe = dict(CUBE_9)
    win._launch_tool("ti2_relayout")
    assert got.get("preset_recipe") == CUBE_9
    win.close()
    win.deleteLater()


# --- names on disk ----------------------------------------------------------

def _save_through_the_dialog(tab, monkeypatch, name, asked):
    from ui.widgets import PrefixLockedLineEdit

    def answer(dlg):
        for cb in dlg.findChildren(__import__(
                "PyQt6.QtWidgets", fromlist=["QCheckBox"]).QCheckBox):
            if cb.text().startswith("Add a descriptive prefix"):
                cb.setChecked(False)
        dlg.findChild(PrefixLockedLineEdit).setText(name)
        return int(QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QDialog, "exec", answer)
    monkeypatch.setattr(tab, "_confirm_overwrite_preset",
                        lambda n: asked.append(n) or False)
    tab._on_preset_save()


def test_two_names_stored_in_one_file_are_asked_about(
        qapp, tmp_path, presets_dir, monkeypatch):
    """"a/b" and "a_b" are one .json and one .ti1; the second save replaced
    the first preset's files without a word."""
    tab = _tab(tmp_path)
    tab._save_presets_to_settings({"a/b": {"editor_recipe": CUBE_9}})
    asked: list = []
    _save_through_the_dialog(tab, monkeypatch, "a_b", asked)
    assert asked == ["a/b"]
    doc = json.loads((presets_dir / "Create Chart" / "a_b.json")
                     .read_text(encoding="utf-8"))
    assert doc["name"] == "a/b" and doc["data"]["editor_recipe"] == CUBE_9


def test_a_preset_renamed_in_finder_keeps_its_patch_set(
        qapp, tmp_path, presets_dir):
    """Renaming the .json and .ti1 by hand left the preset listed under its
    old name, looking for a .ti1 of the old name, and building from targen."""
    from core.preset_store import sidecar_path
    tab = _tab(tmp_path)
    tab._save_presets_to_settings(
        {"Mine": {"attached_ti1": True, "editor_recipe": CUBE_9}})
    d = presets_dir / "Create Chart"
    ti1 = sidecar_path("create_chart", "Mine", ".ti1")
    ti1.write_text("CTI1\n", encoding="utf-8")
    (d / "Mine.json").rename(d / "Renamed.json")
    ti1.rename(d / "Renamed.ti1")
    presets = tab._load_presets_from_settings()
    assert list(presets) == ["Mine"]
    tab._populate_preset_combo(presets)
    _choose(tab, "Mine")
    assert tab._preset_ti1_path == d / "Renamed.ti1"
    assert tab.recipe_for_new_patch_set()["sp"] == {"cube_n": 9}


def test_a_profile_run_switch_drops_the_preset_s_design(
        qapp, tmp_path, presets_dir):
    """The design of the preset chosen last belongs to the run it was chosen
    for. Kept across a Profile-run switch, New Patch Set… opened run2's design
    over run1's loaded chart (challenge round before 4.3.0, driven on screen:
    run1 built as cube 7, run2 as cube 9, back to run1 showed cube 9)."""
    tab = _tab(tmp_path)
    from ui.measurement_target_bar import MeasurementTargetController
    tab._manual_target_name_edit.setText("ZZ-run-switch-probe")
    tab.set_target_controller(MeasurementTargetController(tab._file_mgr))
    tab._pending_editor_recipe = dict(CUBE_9)
    assert tab.recipe_for_new_patch_set() == CUBE_9
    tab._on_target_changed()
    assert tab.recipe_for_new_patch_set() is None, (
        "the last preset's design survived a Profile-run switch")
    tab.deleteLater()
