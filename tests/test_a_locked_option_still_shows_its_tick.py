"""A ticked Measure option still reads as ticked while a measurement runs.

Basti's screenshot, 2026-10-23 13:06: during a run the greyed Measurement
Options ("Refine / resume existing measurement (-r)", "Suppress warning
messages (-S)") all looked unticked, while the reader really ran with -r -S.
The app's style greys a disabled box to the look of an unticked one, which is
right for a group that is switched off and wrong here: these boxes are locked
only because the measurement is running WITH them.

The Measure tab marks its option boxes `keepsTick`, and each appearance's
sheet (light, dark, neutral, and the main window's per-tab sheet) gives a
ticked, disabled `keepsTick` box a greyed fill that is plainly different from
an unticked one. Every test here fails on the code before the change.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                    # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QVBoxLayout,  # noqa: E402
                             QWidget)


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
    # the indicator is the 16 px square at the left, vertically centred
    return img.pixelColor(int(9 * img.devicePixelRatio()),
                          int(img.height() / 2))


@pytest.mark.parametrize("mode", ["light", "dark", "neutral"])
def test_a_ticked_locked_option_does_not_look_unticked(qapp, mode):
    from ui.main_window import MainWindow
    outer = QWidget()
    outer.setStyleSheet(_app_sheet(mode))
    lay = QVBoxLayout(outer)
    tab = QWidget()
    lay.addWidget(tab)
    MainWindow._apply_tab_widget_styling(_StubWindow(tab, mode), 2)
    inner = QVBoxLayout(tab)
    ticked, unticked = QCheckBox("on", tab), QCheckBox("off", tab)
    ticked.setChecked(True)
    for cb in (ticked, unticked):
        cb.setProperty("keepsTick", True)
        cb.setEnabled(False)
        inner.addWidget(cb)
    outer.resize(300, 120)
    outer.show()
    QApplication.processEvents()
    a, b = _indicator_colour(ticked), _indicator_colour(unticked)
    diff = (abs(a.red() - b.red()) + abs(a.green() - b.green())
            + abs(a.blue() - b.blue()))
    outer.close()
    assert diff >= 60, (mode, a.name(), b.name())


def test_the_measure_tab_marks_its_options_while_they_are_locked(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    t = TabMeasure(ArgyllRunner(s), s)
    t._set_settings_enabled(False)
    boxes = (t._g_options.findChildren(QCheckBox)
             + t._m_options.findChildren(QCheckBox))
    assert boxes
    assert all(cb.property("keepsTick") is True for cb in boxes), [
        cb.text() for cb in boxes if cb.property("keepsTick") is not True]
    t._set_settings_enabled(True)
