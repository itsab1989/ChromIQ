"""B8-756: Preferences opens wide enough to show every tab, Beta included.

The window took `max(1040, sizeHint)` and never asked its own tab bar, whose
hint is wider than that in every shipped language (English 1089, German 1165,
French 1189). It opened with scroll arrows and the Beta tab, where a user opts
into betas, off the edge. Measured on screen after the fix, 2026-09-28: every
tab of all fourteen languages is inside the bar when the window opens, the
widest window 1299 px (Ukrainian), inside a 1512 px work area
(`~/Desktop/ChromIQ-430-stable-prep/fixes-a/`).

The offscreen screen is 800 px wide, where the window is capped at 90 % of the
screen by design, so these tests stand it on a 1512 x 982 work area, the
smallest the item names.

MUTATION: drop `self._width_for_every_tab()` from the `max(...)` in
`SettingsDialog.__init__`, and the test fails for every language here.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication

import core.i18n as i18n
from core.settings import DEFAULTS
from ui.dialogs.settings_dialog import SettingsDialog


class _FakeSettings:
    def __init__(self):
        self._store = dict(DEFAULTS)

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


class _Screen:
    def __init__(self, width, height):
        self._rect = QRect(0, 0, width, height)

    def availableGeometry(self):
        return self._rect


@pytest.fixture
def work_area(monkeypatch):
    QApplication.instance() or QApplication([])
    def _set(width, height=982):
        monkeypatch.setattr(SettingsDialog, "screen",
                            lambda self: _Screen(width, height))
    return _set


def _open(lang):
    i18n.set_language(lang)
    dlg = SettingsDialog(_FakeSettings(), None)
    bar = dlg._tabs.tabBar()
    return dlg, bar


@pytest.mark.parametrize("lang", ["en", "de", "fr", "uk", "ja"])
def test_every_tab_fits_when_the_window_opens(work_area, lang):
    work_area(1512)
    dlg, bar = _open(lang)
    try:
        margins = dlg.layout().contentsMargins()
        room = dlg.width() - margins.left() - margins.right()
        assert room >= bar.sizeHint().width(), (
            f"{lang}: Preferences opens {dlg.width()} px wide, leaving {room} px "
            f"for a tab bar that needs {bar.sizeHint().width()}, so "
            f"{bar.tabText(bar.count() - 1)!r} starts off the edge")
        assert dlg.width() <= int(1512 * 0.9)
    finally:
        dlg.deleteLater()


def test_the_tab_width_never_asks_for_more_than_the_screen(work_area):
    work_area(900, 700)
    dlg, bar = _open("fr")
    try:
        assert dlg._width_for_every_tab() <= int(900 * 0.9)
    finally:
        dlg.deleteLater()
