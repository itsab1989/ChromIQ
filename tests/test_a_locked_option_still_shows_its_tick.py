"""A ticked box still reads as ticked when it is disabled, everywhere.

Basti's screenshot, 2026-10-23 13:06: during a run the greyed Measurement
Options ("Refine / resume existing measurement (-r)", "Suppress warning
messages (-S)") looked unticked while the reader really ran with -r -S.
4.3.10 (4941bbde4) fixed only those boxes, by marking them `keepsTick`. Every
other disabled, ticked box in the app still drew exactly like an unticked one
(Preferences ▸ "Confirm print settings before printing" under the macOS
printer dialog, a preset's locked options, …), because the shared rules
`QCheckBox::indicator:disabled` (light, dark, neutral app sheets) and
`QCheckBox::indicator:checked:disabled` (the main window's per-tab sheet)
give a disabled box the unticked fill.

4.3.11: each appearance gives EVERY ticked, disabled box (and the chosen
radio of a disabled group) a greyed fill plainly different from an unticked
one, with no marker needed; `keepsTick` and the Measure tab's
`_options_keep_their_ticks` are gone. Each test here fails on 4.3.10.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                    # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog,  # noqa: E402
                             QRadioButton, QVBoxLayout, QWidget)

MODES = ["light", "dark", "neutral"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _app_sheet(mode):
    if mode == "light":
        from ui.light_styles import LIGHT_STYLESHEET
        return LIGHT_STYLESHEET
    if mode == "neutral":
        from ui.neutral_styles import NEUTRAL_STYLESHEET
        return NEUTRAL_STYLESHEET
    from ui.styles import APP_STYLESHEET
    return APP_STYLESHEET


class _StubWindow:
    """Just enough of MainWindow for its per-tab sheet to be made."""

    def __init__(self, tab, mode):
        class _Tabs:
            def widget(self, _i):
                return tab
        self._tabs = _Tabs()
        self._title_bar_mode = mode
        self._styled_tab_theme = {}


def _indicator_colour(box):
    img = box.grab().toImage()
    # the indicator is the 14-16 px square/circle at the left, centred
    return img.pixelColor(int(8 * img.devicePixelRatio()),
                          int(img.height() / 2))


def _diff(a, b):
    return (abs(a.red() - b.red()) + abs(a.green() - b.green())
            + abs(a.blue() - b.blue()))


def _pair(kind, parent, layout):
    on, off = kind("on", parent), kind("off", parent)
    on.setChecked(True)
    for w in (on, off):
        layout.addWidget(w)
    return on, off


def _measure(outer, on, off, disable):
    for w in disable:
        w.setEnabled(False)
    outer.resize(300, 160)
    outer.show()
    QApplication.processEvents()
    d = _diff(_indicator_colour(on), _indicator_colour(off))
    outer.close()
    return d


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind", [QCheckBox, QRadioButton])
def test_in_a_tab(qapp, mode, kind):
    """Under the main window's per-tab sheet, box disabled on its own."""
    from ui.main_window import MainWindow
    outer = QWidget()
    outer.setStyleSheet(_app_sheet(mode))
    lay = QVBoxLayout(outer)
    tab = QWidget()
    lay.addWidget(tab)
    MainWindow._apply_tab_widget_styling(_StubWindow(tab, mode), 1)
    inner = QVBoxLayout(tab)
    if kind is QRadioButton:
        a, b = QWidget(tab), QWidget(tab)       # one radio per group
        on, _x = _pair(kind, a, QVBoxLayout(a))
        _y, off = _pair(kind, b, QVBoxLayout(b))
        inner.addWidget(a)
        inner.addWidget(b)
        disable = (a, b)
    else:
        on, off = _pair(kind, tab, inner)
        disable = (on, off)
    assert _measure(outer, on, off, disable) >= 60, mode


@pytest.mark.parametrize("mode", MODES)
def test_in_a_dialog_with_the_app_sheet_only(qapp, mode):
    """A dialog (Preferences) gets only the appearance's app sheet."""
    dlg = QDialog()
    dlg.setStyleSheet(_app_sheet(mode))
    lay = QVBoxLayout(dlg)
    on, off = _pair(QCheckBox, dlg, lay)
    assert _measure(dlg, on, off, (on, off)) >= 60, mode


@pytest.mark.parametrize("mode", MODES)
def test_a_disabled_box_still_looks_disabled(qapp, mode):
    """The greyed tick is not the live one: a disabled ticked box differs
    from an enabled ticked box."""
    outer = QWidget()
    outer.setStyleSheet(_app_sheet(mode))
    lay = QVBoxLayout(outer)
    live, locked = QCheckBox("live", outer), QCheckBox("locked", outer)
    for w in (live, locked):
        w.setChecked(True)
        lay.addWidget(w)
    assert _measure(outer, live, locked, (locked,)) >= 60, mode


def test_no_marker_is_needed_any_more():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "ui"
    for name in ("light_styles.py", "styles.py", "neutral_styles.py",
                 "main_window.py", "tabs/tab_measure.py"):
        src = (root / name).read_text(encoding="utf-8")
        assert 'keepsTick="true"' not in src, name
        assert "_options_keep_their_ticks" not in src, name


def test_the_measure_tabs_locked_options_keep_their_tick(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    outer = QWidget()
    outer.setStyleSheet(_app_sheet("light"))
    lay = QVBoxLayout(outer)
    t = TabMeasure(ArgyllRunner(s), s)
    lay.addWidget(t)
    MainWindow._apply_tab_widget_styling(_StubWindow(t, "light"), 2)
    boxes = (t._g_options.findChildren(QCheckBox)
             + t._m_options.findChildren(QCheckBox))
    assert boxes
    outer.resize(1200, 900)
    outer.show()
    QApplication.processEvents()
    for cb in boxes:
        cb.setChecked(True)
    t._set_settings_enabled(False)
    QApplication.processEvents()
    shown = [cb for cb in boxes if cb.isVisible()]
    probe = QCheckBox("off", t._g_options)
    probe.setEnabled(False)
    probe.show()
    QApplication.processEvents()
    off = _indicator_colour(probe)
    assert shown
    for cb in shown:
        assert _diff(_indicator_colour(cb), off) >= 60, cb.text()
    t._set_settings_enabled(True)
    outer.close()


@pytest.mark.parametrize("mode", MODES)
def test_in_preferences_and_the_tools_dialogs(qapp, mode):
    """Preferences and the Tools dialogs add `neutral_controls_qss` (with its
    own :checked:disabled rule) to their own sheet; until 4.3.11 Preferences
    added one more on top that drew the unticked look, and Neutral's shared
    rule had no fill at all."""
    from ui.dialogs.tools_dialogs import neutral_controls_qss
    dlg = QDialog()
    dlg.setStyleSheet(_app_sheet(mode))
    inner = QWidget(dlg)
    inner.setStyleSheet(neutral_controls_qss("#ff2d9b", mode=mode))
    QVBoxLayout(dlg).addWidget(inner)
    lay = QVBoxLayout(inner)
    on, off = _pair(QCheckBox, inner, lay)
    assert _measure(dlg, on, off, (on, off)) >= 60, mode


@pytest.mark.parametrize("mode", MODES)
def test_in_the_patch_set_editor(qapp, mode):
    from ui.dialogs.ti2_relayout_dialog import _dis_ind
    from ui.dialogs.tools_dialogs import neutral_controls_qss
    dlg = QDialog()
    dlg.setStyleSheet(_app_sheet(mode) + neutral_controls_qss("#ff2d9b", mode=mode)
                      + "QCheckBox::indicator:checked:disabled {"
                      + _dis_ind(mode) + "}")
    lay = QVBoxLayout(dlg)
    on, off = _pair(QCheckBox, dlg, lay)
    assert _measure(dlg, on, off, (on, off)) >= 60, mode


# ---- 4.3.11 (d): the greyed tick is READABLE in every appearance ------------
def _lum(c):
    def f(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c.red()) + 0.7152 * f(c.green()) + 0.0722 * f(c.blue())


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _tab_pair(mode, index, kind=QCheckBox):
    from ui.main_window import MainWindow
    outer = QWidget()
    outer.setStyleSheet(_app_sheet(mode))
    lay = QVBoxLayout(outer)
    tab = QWidget()
    lay.addWidget(tab)
    MainWindow._apply_tab_widget_styling(_StubWindow(tab, mode), index)
    on, off = _pair(kind, tab, QVBoxLayout(tab))
    live = kind("live", tab)
    live.setChecked(True)
    tab.layout().addWidget(live)
    return outer, on, off, live


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("index", range(5))
def test_the_greyed_tick_reads_at_least_2_5_to_1(qapp, mode, index):
    """Measured 2026-10-23 before the change: light 2.1 : 1, dark 1.9 : 1 in
    the app sheets, and in a tab's sheet down to 1.2 : 1 (the muted accent on
    the yellow and green tabs). Now at least 2.5 : 1 against an unticked
    disabled box everywhere, and still plainly not the live tick."""
    outer, on, off, live = _tab_pair(mode, index)
    for w in (on, off):
        w.setEnabled(False)
    outer.resize(300, 200)
    outer.show()
    QApplication.processEvents()
    a, b, c = (_indicator_colour(w) for w in (on, off, live))
    outer.close()
    assert _ratio(a, b) >= 2.5, (mode, index, a.name(), b.name())
    assert _diff(a, c) >= 60, (mode, index, a.name(), c.name())


@pytest.mark.parametrize("mode", MODES)
def test_the_dialogs_greyed_tick_reads_at_least_2_5_to_1(qapp, mode):
    from ui.dialogs.tools_dialogs import neutral_controls_qss
    dlg = QDialog()
    dlg.setStyleSheet(_app_sheet(mode) + neutral_controls_qss("#ff2d9b", mode=mode))
    lay = QVBoxLayout(dlg)
    on, off = _pair(QCheckBox, dlg, lay)
    for w in (on, off):
        w.setEnabled(False)
    dlg.resize(300, 160)
    dlg.show()
    QApplication.processEvents()
    a, b = _indicator_colour(on), _indicator_colour(off)
    dlg.close()
    assert _ratio(a, b) >= 2.5, (mode, a.name(), b.name())
