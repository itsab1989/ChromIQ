"""Preferences must open at its full size.

Ten test files build a `SettingsDialog` and not one of them asserted a single
pixel of geometry — so when a performance change moved the dialog's stylesheet
from the finished nine-tab dialog to the top of the build, the dialog began
opening **255 px tall instead of 886**, with `setMinimumHeight` pinned to the
same wrong number, and a full green `--runslow` gate said nothing at all.

The cause was a side effect nobody had written down: setting a stylesheet on the
finished dialog re-polished it, and that flushed Qt's cached layout hints. The
layout item for the tab widget was otherwise still reporting the 137x4 hint it
had while the QTabWidget was empty — adding nine pages never invalidated it.

These pin the OUTCOME (the dialog measures itself correctly), not the mechanism,
so a future rework is free to flush the hints some other way.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings          # noqa: E402
from PyQt6.QtWidgets import QApplication, QTabWidget    # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    """WITH the app-wide button-font filter installed, which is what the real
    app does — and what makes this test able to see the fault at all.

    The 253 px dialog reproduces ONLY when a `ButtonFontFilter` is on the
    application: its `fit_window` ends in `layout().invalidate(); activate()`,
    which caches the tab widget's hint while the widget is still empty. Without
    the filter the dialog measures 885 px either way and the test is decoration.
    The first version of this file had no filter and passed against the broken
    tree.

    No `app.setStyleSheet` here: it re-polishes every widget the suite has alive
    (CLAUDE.md), and the fault does not need it.
    """
    app = QApplication.instance() or QApplication([])
    from ui.widgets import ButtonFontFilter
    if not getattr(app, "_test_btn_filter", None):
        app._test_btn_filter = ButtonFontFilter(app)
        app.installEventFilter(app._test_btn_filter)
    return app


@pytest.fixture
def dialog(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return SettingsDialog(s, None)


def test_preferences_opens_tall_enough_to_use(dialog):
    """886 px on a real screen, 885 offscreen. The broken version was 255 —
    a quarter of the window, with every tab behind a scrollbar."""
    assert dialog.height() >= 700, (
        f"Preferences opened {dialog.width()}x{dialog.height()}; the dialog has "
        "not measured itself and most of it is hidden")
    assert dialog.width() >= 1040


def test_the_floor_is_not_pinned_to_a_wrong_measurement(dialog):
    """`setMinimumHeight` is taken from the same hint, so a bad measurement is
    not merely the opening size — the user cannot resize past it either."""
    assert dialog.minimumHeight() >= 700
    assert dialog.minimumWidth() >= 1040


def test_the_tab_widget_reports_its_real_hint(dialog):
    """The proximate cause, pinned directly: the tab widget's hint must reflect
    the nine pages it holds, not the empty widget it briefly was."""
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None and tabs.count() >= 9
    assert tabs.sizeHint().height() > 200, (
        f"the tab widget still reports {tabs.sizeHint()}, the hint it had while "
        "it was empty")
