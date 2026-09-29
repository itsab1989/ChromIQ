"""B8-1353 (Knut, #182 5846545713): *"Should not "Use the ChromIQ layout
engine instead of printtarg" always be ON and locked when CR30 instrument is
selected? I think so."*

On the CR30 (Manual's printtarg -i, whichever path set it) the box shows
ticked and is disabled, with a tooltip saying why. It is SHOWN, not written:
`use_chromiq_layout_engine` keeps the person's own choice, so the box goes
back to it when the instrument is no longer the CR30, and a person's
printtarg choice for the other instruments survives a CR30 in between.

On screen: ~/Desktop/ChromIQ-beta44-proof/k53/ (cr30-lock). MUTATIONS:
k53/mutations.txt (M1353-a to M1353-c).
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


def _tab(qapp, settings, own: bool):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    settings.set(KEY, own)
    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    qapp.processEvents()
    return t


def _pick(qapp, t, instr):
    c = t._manual_instr_pw._control
    c.setCurrentIndex(c.findData(instr))
    c.activated.emit(c.currentIndex())
    qapp.processEvents()
    t._refresh_manual_command_preview()
    qapp.processEvents()
    assert t._manual_get("printtarg", "-i", "") == instr


def _close(qapp, t):
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _box(t):
    chk = t._manual_engine_check
    return chk.isChecked(), chk.isEnabled()


@pytest.mark.parametrize("own", [False, True], ids=["unticked", "ticked"])
def test_the_cr30_locks_the_box_on_and_the_i1pro_gives_it_back(
        qapp, settings, own):
    t = _tab(qapp, settings, own)
    try:
        _pick(qapp, t, "i1")
        assert _box(t) == (own, True)
        _pick(qapp, t, "CR30")
        assert _box(t) == (True, False), "the CR30 did not lock the box on"
        assert t._manual_engine_check.toolTip(), "the lock does not say why"
        # drawn ticked: a disabled ticked box is drawn EMPTY in both themes
        # unless it is `#locked_on` (measured on screen, k53 cr30-lock)
        assert t._manual_engine_check.objectName() == "locked_on"
        assert bool(settings.get(KEY)) is own, \
            "the lock wrote the person's setting"
        _pick(qapp, t, "i1")
        assert _box(t) == (own, True), "the box did not return to its own"
        assert t._manual_engine_check.toolTip() == ""
        assert t._manual_engine_check.objectName() != "locked_on"
        assert bool(settings.get(KEY)) is own
    finally:
        _close(qapp, t)


def test_an_i1pro_on_printtarg_stays_printtarg_after_a_cr30(qapp, settings):
    """The person's printtarg choice is not flipped by a CR30 in between:
    the i1Pro after it is laid out by printtarg again."""
    t = _tab(qapp, settings, False)
    try:
        _pick(qapp, t, "CR30")
        assert not t._manual_layout_grp.isHidden()
        _pick(qapp, t, "i1")
        assert t._manual_layout_grp.isHidden()
        assert not t._manual_printtarg_grp.isHidden()
        assert t._collect_manual().layout_recipe is None
    finally:
        _close(qapp, t)


def test_the_cr30_chosen_in_the_panel_locks_it_too(qapp, settings):
    """The panel's own Instrument (engine on) mirrors into -i, so the lock
    follows that path as well."""
    t = _tab(qapp, settings, True)
    try:
        t._refresh_manual_command_preview()
        qapp.processEvents()
        p = t._manual_layout_panel
        i = p.instr.findData("CR30")
        p.instr.setCurrentIndex(i)
        p.instr.activated.emit(i)
        qapp.processEvents()
        t._refresh_manual_command_preview()
        qapp.processEvents()
        assert t._manual_get("printtarg", "-i", "") == "CR30"
        assert _box(t) == (True, False)
    finally:
        _close(qapp, t)


def test_an_app_move_while_locked_moves_the_setting_not_the_box(
        qapp, settings):
    """A restore or a built-in load asks for the engine while the box is
    locked: what moves is the person's setting, the box stays ticked."""
    t = _tab(qapp, settings, False)
    try:
        _pick(qapp, t, "CR30")
        t._set_engine_checked(True)
        qapp.processEvents()
        assert settings.get(KEY) is True
        assert _box(t) == (True, False)
        t._set_engine_checked(False)
        qapp.processEvents()
        assert settings.get(KEY) is False
        assert _box(t) == (True, False)
    finally:
        _close(qapp, t)


def test_save_as_defaults_on_the_cr30_keeps_the_persons_choice(
        qapp, settings):
    """Saved on the CR30 with the person's box unticked, the store says
    unticked; the restart shows the CR30 locked, and an i1Pro after it is
    printtarg."""
    t = _tab(qapp, settings, False)
    try:
        _pick(qapp, t, "CR30")
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    assert settings.get(KEY) in (False, "false")
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    try:
        t._switch_mode("manual")
        qapp.processEvents()
        t._refresh_manual_command_preview()
        qapp.processEvents()
        assert t._manual_get("printtarg", "-i", "") == "CR30"
        assert _box(t) == (True, False)
        _pick(qapp, t, "i1")
        assert _box(t) == (False, True)
    finally:
        _close(qapp, t)
