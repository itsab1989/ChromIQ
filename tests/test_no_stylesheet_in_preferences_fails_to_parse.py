"""No style sheet in Preferences may fail to parse.

Basti ran `python main.py` on 2026-10-25 and the terminal showed
`Could not parse stylesheet of object QFrame(..., name = "misread_table")`
eight times. An f-string's `}}` had been joined to a PLAIN string literal, where
it stays two braces, so Qt threw the frame's whole sheet away. Qt only says so
on stderr, and a sheet it throws away paints nothing wrong that a test of
sizes would see, so nothing in the suite noticed.

This catches Qt's own message while the dialog is built and every tab is shown,
in each appearance, because the colours (and so the text of the sheets) differ
per appearance.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6 import QtCore                      # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def qt_messages():
    seen: list[str] = []

    def handler(_kind, _context, message):
        seen.append(str(message))

    old = QtCore.qInstallMessageHandler(handler)
    try:
        yield seen
    finally:
        QtCore.qInstallMessageHandler(old)


@pytest.mark.parametrize("mode", ["light", "dark", "neutral"])
def test_every_preferences_tab_parses_its_style_sheets(qapp, qt_messages,
                                                        monkeypatch, mode):
    from core.settings import AppSettings
    from ui import theme
    from ui.dialogs.settings_dialog import SettingsDialog
    monkeypatch.setattr(theme, "active_mode", lambda *_a, **_k: mode)
    dlg = SettingsDialog(AppSettings())
    try:
        dlg.show()
        tabs = dlg._tabs
        for i in range(tabs.count()):
            tabs.setCurrentIndex(i)
            for w in tabs.widget(i).findChildren(QWidget):
                w.ensurePolished()
            qapp.processEvents()
        bad = [m for m in qt_messages if "Could not parse stylesheet" in m]
        assert not bad, "\n".join(bad)
    finally:
        dlg.reject()
        dlg.deleteLater()
        qapp.processEvents()


def test_the_guard_sees_a_sheet_qt_cannot_parse(qapp, qt_messages):
    """The handler really receives Qt's complaint: the same mistake, made on
    purpose, must be heard."""
    w = QWidget()
    w.setObjectName("deliberately_broken")
    w.setStyleSheet("QWidget#deliberately_broken { border: none; }}")
    w.show()
    w.ensurePolished()
    qapp.processEvents()
    w.deleteLater()
    assert any("Could not parse stylesheet" in m for m in qt_messages), \
        qt_messages
