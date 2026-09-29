"""B8-1300: with the CR30 and the "ChromIQ layout engine" box unticked, the
layout panel is on screen and lays the chart out (`_layout_panel_lays_out`,
B8-1295), and every reader below now asks that predicate, not the box.

Reproduced on screen by the beta 44 challenge round 6
(`~/Desktop/ChromIQ-beta44-proof/challenge-6/`):

* B1 / B2: a CR30 preset saved with the box unticked had no ``layout_recipe``;
  loading it built the panel's Letter instead of the preset's 250 x 300,
  400 dpi, margins 11 / 12 / 13 / 14 (`_on_preset_save`).
* A2 / AP: after a build the estimate column went blank
  (`_refresh_layout_estimate` without ``use_engine`` read the box), and the
  auto-preview ignored panel-only edits (`_layout_signature` described
  printtarg's hidden rows).

Also the preset's recipe sync (`_recipe_synced_to_manual`), the patch count
(`_update_patch_count`), the gamut module's per-sheet and page counts
(`_gamut_per_sheet`, `_gamut_pages`) and the text notes (`_engine_text_notes`).

LEFT ON THE BOX, DELIBERATELY: `_collect_ui_state` and
`_chart_settings_fingerprint` store and compare the box itself, because a run
change puts that value back into the tick; the panel's recipe is stored and
fingerprinted whatever the box says (pinned below).

The CONTROLS are the same checks with the box ticked on the CR30 and with the
i1Pro unticked (printtarg lays that one out, so the old answers stand).

MUTATIONS (mutations.txt of the k50 proof): each reader put back on the box
alone, one at a time; each is red here.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QLineEdit    # noqa: E402

from ui.tabs import tab_chart as TC                             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("create_chart_auto_suffix", False)
    return s


def _tab(qapp, settings, instr: str, box: bool):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    settings.set("use_chromiq_layout_engine", box)
    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    qapp.processEvents()
    c = t._manual_instr_pw._control
    c.setCurrentIndex(c.findData(instr))
    c.activated.emit(c.currentIndex())
    qapp.processEvents()
    t._refresh_manual_command_preview()
    qapp.processEvents()
    assert t._manual_get("printtarg", "-i", "") == instr
    # B8-1353: on the CR30 the box SHOWS ticked and is locked; the setting
    # keeps the person's own choice ("unticked" is the setting from here on).
    assert bool(t._manual_engine_check.isChecked()) is (box or instr == "CR30")
    assert bool(t._settings.get("use_chromiq_layout_engine", None)) is box
    return t


@pytest.fixture()
def cr30_unticked(qapp, settings):
    t = _tab(qapp, settings, "CR30", False)
    assert not t._manual_layout_grp.isHidden(), "the CR30's panel is not shown"
    yield t
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _set_panel(qapp, t, *, custom=None, paper=None, dpi=None, margins=None):
    p = t._manual_layout_panel
    if custom:
        p.custom_w.setValue(custom[0])
        p.custom_h.setValue(custom[1])
        p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    if paper:
        p.paper.setCurrentIndex(p.paper.findData(paper))
    if margins is not None:
        p.use_instr_margins.setChecked(False)
        for k, v in zip("trbl", margins):
            p.margins[k].setValue(float(v))
            p.margins[k].editingFinished.emit()
    elif paper:
        p.use_instr_margins.setChecked(True)
    if dpi:
        p.dpi.setValue(dpi)
    qapp.processEvents()


def _save_preset(t, monkeypatch, name):
    def fake_exec(self):
        edit = self.findChild(QLineEdit)
        if edit is not None:
            edit.setText(name)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(TC.QDialog, "exec", fake_exec, raising=True)
    t._on_preset_save()
    monkeypatch.undo()
    saved = t._load_presets_from_settings().get(name)
    assert saved is not None, "the preset was not saved"
    return saved


# ---- B1 / B2: the preset --------------------------------------------------

def test_a_cr30_preset_saved_unticked_carries_the_panels_recipe(
        cr30_unticked, qapp, monkeypatch):
    t = cr30_unticked
    _set_panel(qapp, t, custom=(250, 300), dpi=400, margins=(11, 12, 13, 14))
    saved = _save_preset(t, monkeypatch, "C6-P-Y")
    lr = saved.get("layout_recipe")
    assert isinstance(lr, dict), "no layout_recipe in a CR30 preset (B1)"
    assert (lr["instrument"], lr["paper"], lr["dpi"]) == ("CR30", "250x300", 400)
    assert [lr[f"margin_{s}"] for s in ("top", "right", "bottom", "left")] \
        == [11, 12, 13, 14]


def test_loading_it_puts_the_presets_layout_back_and_leaves_the_box(
        cr30_unticked, qapp, monkeypatch):
    t = cr30_unticked
    _set_panel(qapp, t, custom=(250, 300), dpi=400, margins=(11, 12, 13, 14))
    saved = _save_preset(t, monkeypatch, "C6-P-Y")
    _set_panel(qapp, t, paper="Letter", dpi=300)          # B2: defaults X
    assert t._manual_layout_panel.selection()[1] == "Letter"
    # CHOSEN FROM THE PULLDOWN, the whole path a person takes (the first cut
    # of this test called `_restore_user_preset` alone, and the pulldown's
    # own handler still ticked the box: caught on screen, k50 after/cells).
    presets = t._load_presets_from_settings()
    name = next(k for k in presets if k.endswith("C6-P-Y"))
    presets[name]["auto_run"] = False          # no build in a unit test
    t._save_presets_to_settings(presets)
    t._populate_preset_combo(presets, select_name=name)
    t._on_preset_selected(t._preset_combo.currentIndex())
    qapp.processEvents()
    r = t._manual_layout_panel.get_recipe()
    assert t._manual_layout_panel.selection()[1] == "250x300"
    assert r.dpi == 400
    assert [r.margin_top, r.margin_right, r.margin_bottom, r.margin_left] \
        == [11, 12, 13, 14]
    # the box decides nothing for the CR30, and a CR30 preset does not move
    # the person's setting (B8-1353: the box itself shows ticked and locked)
    assert t._manual_engine_check.isChecked() is True
    assert not t._manual_engine_check.isEnabled()
    assert t._settings.get("use_chromiq_layout_engine", True) is False
    assert not t._manual_layout_grp.isHidden()


def test_the_presets_recipe_sync_keeps_the_panels_recipe(cr30_unticked):
    rec = {"layout": {"marker": "as created"}, "instrument": "CR30"}
    assert cr30_unticked._recipe_synced_to_manual(rec) is rec


# ---- A2 / AP: the estimate and the live preview -------------------------

def test_the_estimate_is_not_cleared_when_called_without_use_engine(
        cr30_unticked, qapp, monkeypatch):
    t = cr30_unticked
    cleared, set_ = [], []
    lip = t._layout_info_panel
    monkeypatch.setattr(lip, "clear_estimate", lambda: cleared.append(1))
    orig = lip.set_estimate
    monkeypatch.setattr(lip, "set_estimate",
                        lambda **kw: (set_.append(kw), orig(**kw)))
    t._refresh_layout_estimate()          # what a finished build calls
    assert not cleared, "the estimate column was blanked (challenge 6, A2)"
    assert set_, "no estimate was computed for the panel's layout"


def test_a_panel_only_edit_moves_the_live_preview_signature(
        cr30_unticked, qapp):
    t = cr30_unticked
    before = t._layout_signature()
    _set_panel(qapp, t, margins=(20, 20, 20, 20))
    assert t._layout_signature() != before, (
        "a margin typed in the panel did not change what the auto-preview "
        "compares (challenge 6, AP)")


# ---- the counts ------------------------------------------------------------

def test_the_patch_count_is_the_engines_not_printtargs(cr30_unticked, qapp):
    t = cr30_unticked
    t._update_patch_count()
    assert t._predicted_patch_count, (
        "printtarg's capacity table has no CR30: the count read '?'")


def test_the_gamut_pages_are_the_panels(cr30_unticked, qapp):
    t = cr30_unticked
    # printtarg's hidden Pages spin kept apart from the panel's, as it can be
    t._manual_pages_spin.blockSignals(True)
    t._manual_pages_spin.setValue(1)
    t._manual_pages_spin.blockSignals(False)
    t._manual_layout_panel.pages.blockSignals(True)
    t._manual_layout_panel.set_pages(3)
    t._manual_layout_panel.pages.blockSignals(False)
    assert t._gamut_pages() == 3


def test_the_gamut_per_sheet_is_the_panels_recipe(cr30_unticked, qapp,
                                                  monkeypatch):
    t = cr30_unticked
    monkeypatch.setattr(t, "_recipe_capacity", lambda: 123)
    assert t._gamut_per_sheet() == 123


def test_the_text_notes_are_checked_for_the_panels_sheet(cr30_unticked,
                                                         monkeypatch):
    asked = []
    monkeypatch.setattr(TC.TabChart, "_notice_layout_recipe",
                        lambda self: asked.append(1))
    TC.TabChart._engine_text_notes(cr30_unticked)
    assert asked, "the notes returned before looking at the panel's sheet"


# ---- left on the box, deliberately ------------------------------------------

def test_the_per_target_record_keeps_the_box_and_the_recipe(cr30_unticked,
                                                            qapp):
    t = cr30_unticked
    _set_panel(qapp, t, custom=(250, 300), dpi=400)
    ui = t._collect_ui_state()
    assert ui["engine_on"] is False              # the box, what a run restores
    assert ui["engine_recipe"]["paper"] == "250x300"
    fp = t._chart_settings_fingerprint()
    _set_panel(qapp, t, margins=(20, 20, 20, 20))
    assert t._chart_settings_fingerprint() != fp


# ---- controls ---------------------------------------------------------------

def test_control_the_i1pro_unticked_is_still_printtarg(qapp, settings,
                                                       monkeypatch):
    t = _tab(qapp, settings, "i1", False)
    try:
        assert t._manual_layout_grp.isHidden()
        assert not TC._panel_lays_out_on(t)
        saved = _save_preset(t, monkeypatch, "i1-off")
        assert "layout_recipe" not in saved
        cleared = []
        monkeypatch.setattr(t._layout_info_panel, "clear_estimate",
                            lambda: cleared.append(1))
        t._refresh_layout_estimate()
        assert cleared
    finally:
        t.hide()
        t.deleteLater()
        qapp.processEvents()


def test_control_the_cr30_ticked_is_the_panel_as_before(qapp, settings,
                                                        monkeypatch):
    t = _tab(qapp, settings, "CR30", True)
    try:
        assert TC._panel_lays_out_on(t)
        _set_panel(qapp, t, custom=(250, 300), dpi=400)
        saved = _save_preset(t, monkeypatch, "cr30-on")
        assert saved["layout_recipe"]["paper"] == "250x300"
    finally:
        t.hide()
        t.deleteLater()
        qapp.processEvents()
