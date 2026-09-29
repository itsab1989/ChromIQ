"""B8-1360 (beta 44 challenge round 8, MAJOR, regression from 02c41b99):
the CR30 chosen in printtarg's own Instrument (-i) with the engine box
unticked, after the layout panel had been shown on the i1Pro, left the panel
hidden and on the i1Pro. `_collect_manual` takes the chart's instrument from
the panel whenever the panel lays the chart out (B8-1295), so the chart came
back as an i1Pro: the frame read `printtarg -ii1 -pA4 -t300 -m5 -M5` and
Generate built a 441-patch i1Pro chart.

These tests go through the real path: the tab's own widgets, `_collect_manual`
(what Generate builds from) and `ChartCreator._should_use_engine` (what decides
printtarg or the engine for that build), and the frame's command line.

On screen: ~/Desktop/ChromIQ-beta44-proof/fixes-8-cr30/. MUTATIONS:
fixes-8-cr30/mutations.txt.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from ui.tabs import tab_chart as TC                             # noqa: E402

KEY = "use_chromiq_layout_engine"


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


def _tab(qapp, settings, engine_on: bool):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    settings.set(KEY, engine_on)
    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    qapp.processEvents()
    t._refresh_manual_command_preview()
    qapp.processEvents()
    return t


def _close(qapp, t):
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _settle(qapp, t):
    qapp.processEvents()
    t._refresh_manual_command_preview()
    qapp.processEvents()


def _pick_i(qapp, t, instr):
    c = t._manual_instr_pw._control
    c.setCurrentIndex(c.findData(instr))
    c.activated.emit(c.currentIndex())
    _settle(qapp, t)
    assert t._manual_get("printtarg", "-i", "") == instr


def _pick_panel(qapp, t, instr):
    c = t._manual_layout_panel.instr
    c.setCurrentIndex(c.findData(instr))
    c.activated.emit(c.currentIndex())
    _settle(qapp, t)


def _untick(qapp, t):
    chk = t._manual_engine_check
    assert chk.isChecked() and chk.isEnabled()
    chk.click()                                   # the person's click
    _settle(qapp, t)
    assert not chk.isChecked()


def _build(t):
    """What Generate builds from, and what it builds with."""
    p = t._collect_manual()
    return p, t._creator._should_use_engine(p)


def _frame(t) -> str:
    return t._manual_info_lbl.text()


def _assert_cr30_engine(t):
    panel = t._manual_layout_panel
    assert panel.instr.currentData() == "CR30", \
        "the layout panel is not on the CR30"
    assert not t._manual_layout_grp.isHidden(), "the layout panel is hidden"
    assert t._manual_printtarg_grp.isHidden()
    frame = _frame(t)
    assert "printtarg -i" not in frame, f"the frame is printtarg:\n{frame}"
    assert "ChromIQ layout engine · CR30" in frame, frame
    p, engine = _build(t)
    assert p.instrument == "CR30", f"the build's instrument is {p.instrument}"
    assert p.layout_recipe is not None \
        and p.layout_recipe.instrument == "CR30"
    assert engine, "the build goes to printtarg"
    est = t._layout_info_panel.predicted()
    assert est is not None and est.get("total"), "no estimate for the CR30"


# -- the reported path, and the start states --------------------------------

def test_the_reported_path_engine_on_untick_then_cr30_in_printtarg_i(
        qapp, settings):
    t = _tab(qapp, settings, True)
    try:
        assert t._manual_layout_panel.instr.currentData() == "i1"
        _untick(qapp, t)
        _pick_i(qapp, t, "CR30")
        _assert_cr30_engine(t)
        assert bool(settings.get(KEY)) is False, \
            "the person's own choice was written"
        # and a refresh changes nothing
        _settle(qapp, t)
        _assert_cr30_engine(t)
    finally:
        _close(qapp, t)


def test_engine_off_from_the_start_then_cr30_in_printtarg_i(qapp, settings):
    t = _tab(qapp, settings, False)
    try:
        _pick_i(qapp, t, "CR30")
        _assert_cr30_engine(t)
    finally:
        _close(qapp, t)


def test_panel_shown_ticked_off_on_and_off_again_then_cr30(qapp, settings):
    """The panel shown twice before, on another paper."""
    t = _tab(qapp, settings, False)
    try:
        t._manual_engine_check.click()
        _settle(qapp, t)
        _pick_panel(qapp, t, "CM")
        _untick(qapp, t)
        assert t._manual_get("printtarg", "-i", "") == "CM"
        _pick_i(qapp, t, "CR30")
        _assert_cr30_engine(t)
    finally:
        _close(qapp, t)


def test_the_build_asked_before_any_refresh_is_the_cr30(qapp, settings):
    """Generate reads `_collect_manual` on its own; it may not depend on a
    frame refresh having run after the pick."""
    t = _tab(qapp, settings, True)
    try:
        _untick(qapp, t)
        c = t._manual_instr_pw._control
        c.blockSignals(True)
        c.setCurrentIndex(c.findData("CR30"))
        c.blockSignals(False)
        assert t._manual_get("printtarg", "-i", "") == "CR30"
        p, engine = _build(t)
        assert p.instrument == "CR30" and engine
    finally:
        _close(qapp, t)


def test_a_stored_i1pro_recipe_beside_a_cr30_opens_on_the_cr30(
        qapp, settings):
    """The shape 9676b987 to 2194eec7 wrote into a target and into "Save as
    Defaults" (challenge 8, tip-start1): -i CR30, the box unticked and the
    hidden panel's i1Pro recipe. Restored, it must lay the CR30 out."""
    from dataclasses import replace
    t = _tab(qapp, settings, True)
    try:
        _untick(qapp, t)
        i1_recipe = t._manual_layout_panel.get_recipe()
        assert i1_recipe.instrument == "i1"
        _pick_i(qapp, t, "CR30")
        # the hidden panel holding the i1Pro beside -i on the CR30 (the
        # mirror held off, as it is for a panel nobody is looking at)
        t._syncing_manual_sel = True
        try:
            t._set_engine_recipe(replace(i1_recipe, instrument="i1"))
        finally:
            t._syncing_manual_sel = False
        assert t._manual_layout_panel.instr.currentData() == "i1"
        assert t._manual_get("printtarg", "-i", "") == "CR30"
        _settle(qapp, t)
        _assert_cr30_engine(t)
    finally:
        _close(qapp, t)


# -- the other paths --------------------------------------------------------

def test_the_cr30_chosen_in_the_panel(qapp, settings):
    t = _tab(qapp, settings, True)
    try:
        _pick_panel(qapp, t, "CR30")
        assert t._manual_get("printtarg", "-i", "") == "CR30"
        _assert_cr30_engine(t)
    finally:
        _close(qapp, t)


@pytest.mark.parametrize("engine_on", [True, False], ids=["on", "off"])
def test_the_cr30_chosen_in_guided_then_manual(qapp, settings, engine_on):
    t = _tab(qapp, settings, engine_on)
    try:
        if engine_on:
            _untick(qapp, t)
        t._switch_mode("guided")
        qapp.processEvents()
        c = t._instr_combo
        c.setCurrentIndex(c.findData("CR30"))
        qapp.processEvents()
        t._switch_mode("manual")
        _settle(qapp, t)
        assert t._manual_get("printtarg", "-i", "") == "CR30"
        _assert_cr30_engine(t)
    finally:
        _close(qapp, t)


# -- the reverse, and every other instrument --------------------------------

def test_back_from_the_cr30_to_the_i1pro_is_printtarg_again(qapp, settings):
    t = _tab(qapp, settings, True)
    try:
        _untick(qapp, t)
        _pick_i(qapp, t, "CR30")
        _assert_cr30_engine(t)
        _pick_panel(qapp, t, "i1")          # the only Instrument on screen
        assert t._manual_get("printtarg", "-i", "") == "i1"
        assert t._manual_layout_grp.isHidden()
        assert not t._manual_printtarg_grp.isHidden()
        assert "printtarg -ii1 " in _frame(t), _frame(t)
        p, engine = _build(t)
        assert p.instrument == "i1" and p.layout_recipe is None
        assert not engine
    finally:
        _close(qapp, t)


@pytest.mark.parametrize("instr,flag", [
    ("i1", "i1"), ("p3", "3p"), ("CM", "CM"), ("SS", "SS"), ("isis", "isis")])
def test_every_other_instrument_through_i_after_the_panel_was_shown(
        qapp, settings, instr, flag):
    t = _tab(qapp, settings, True)
    try:
        _untick(qapp, t)
        _pick_i(qapp, t, "CR30")            # a CR30 in between, too
        _pick_i(qapp, t, instr)
        assert t._manual_layout_grp.isHidden(), \
            f"{instr}: the panel is shown with the box unticked"
        assert f"printtarg -i{flag} " in _frame(t), _frame(t)
        p, engine = _build(t)
        assert p.instrument == instr and p.layout_recipe is None
        assert not engine, f"{instr}: built with the engine, box unticked"
    finally:
        _close(qapp, t)


# -- B8-1361: a built-in CR30 preset's frame names the layout engine ----------

@pytest.mark.parametrize("engine_on", [True, False], ids=["on", "off"])
def test_a_built_in_cr30_presets_frame_names_the_engine_not_printtarg(
        qapp, settings, monkeypatch, engine_on):
    """The fixed-patch-set branch of the frame printed `printtarg -iCR30
    -pA4 -t200 ...` above a chart the engine lays out (challenge 8 fixes,
    the preset cells)."""
    from PyQt6.QtWidgets import QDialog
    monkeypatch.setattr(TC.QDialog, "exec",
                        lambda self: QDialog.DialogCode.Accepted, raising=True)
    t = _tab(qapp, settings, engine_on)
    try:
        if engine_on:
            _untick(qapp, t)
        monkeypatch.setattr(
            "ui.dialogs.name_prompt.ask_for_project_name",
            lambda *a, **k: "B8-1361", raising=True)
        cb = t._preset_combo
        i = cb.findData("__chromiq_knut_cr30_a4_360p_1page_portrait_w11_0mm__")
        assert i >= 0
        cb.setCurrentIndex(i)
        t._on_preset_selected(i)
        _settle(qapp, t)
        assert t._manual_get("printtarg", "-i", "") == "CR30"
        frame = _frame(t)
        assert "360-patch" in frame, frame
        assert "printtarg -i" not in frame, frame
        assert "ChromIQ layout engine · CR30" in frame, frame
        p, engine = _build(t)
        assert p.instrument == "CR30" and engine
    finally:
        _close(qapp, t)


# -- B8-1341: the presets button's help says the star's rule as K51 set it ---

def test_the_presets_button_help_says_the_stars_rule(qapp, settings):
    from workflow import preset_eligibility as PE
    t = _tab(qapp, settings, False)
    try:
        body = t._preset_verify_help._body
        assert "one printed page of a few hundred" not in body
        assert "one or two printed pages" in body
        assert f"fewer than {PE.VERIFICATION_PATCHES_UNDER} patches" in body
        assert PE.VERIFICATION_MAX_PAGES == 2
        assert "no ink to measure the paper" in body
        assert "evenness included" in body
    finally:
        _close(qapp, t)
