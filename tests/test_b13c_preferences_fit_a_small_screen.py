"""Beta 13, b13c (Basti, 2026-10-08, a 13" MacBook Air, 1470x956 points):
Preferences opened with its top on the menu bar and its OK / Cancel row just
below the bottom of the screen.

Root cause: the window's MINIMUM size was set to 1.5x its size hint (and at
least 1040 px wide), with no regard for the screen. The pages already scroll
and the button row already sits outside them, so the floor was the only thing
in the way. Now the opening size and the floor are capped to the screen's work
area (availableGeometry: no menu bar, no Dock) less a margin, and the frame is
moved fully inside it. On a screen where it fits, nothing changes.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QDialogButtonBox, QScrollArea

from ui.dialogs.settings_dialog import SettingsDialog

#: a 13" MacBook Air: 1470x956 points, less a 37 px menu bar and a 70 px Dock
AIR_13 = QRect(0, 37, 1470, 956 - 37 - 70)
BIG = QRect(0, 25, 3000, 2000)


def _dialog(qapp, monkeypatch, area: QRect) -> SettingsDialog:
    from core.settings import AppSettings
    monkeypatch.setattr(SettingsDialog, "_work_area", lambda self: QRect(area))
    return SettingsDialog(AppSettings())


def _pump(qapp, n=6):
    for _ in range(n):
        qapp.processEvents()


def test_on_a_big_screen_the_size_is_unchanged(qapp, monkeypatch):
    dlg = _dialog(qapp, monkeypatch, BIG)
    want_w = max(1040, dlg.sizeHint().width(), dlg._width_for_every_tab())
    # the size the window always opened at, which this change must not touch
    assert dlg.width() == want_w
    assert dlg.minimumSize() == dlg.size()
    assert dlg.height() >= int(dlg.layout().sizeHint().height())
    dlg.deleteLater()


@pytest.mark.parametrize("area", [AIR_13, QRect(0, 25, 1280, 700),
                                  QRect(100, 60, 1200, 640)])
def test_it_fits_the_work_area_and_the_buttons_stay_visible(qapp, monkeypatch,
                                                            area):
    dlg = _dialog(qapp, monkeypatch, area)
    m, cap = SettingsDialog._SCREEN_MARGIN, SettingsDialog._CAPTION_GUESS
    assert dlg.width() <= area.width() - 2 * m
    assert dlg.height() + cap <= area.height() - 2 * m
    # the user may not drag it bigger than that floor either
    assert dlg.minimumHeight() <= dlg.height()
    dlg.show()
    _pump(qapp)
    frame = dlg.frameGeometry()
    top = frame.y()
    bottom = top + max(frame.height(), dlg.height() + dlg._caption_height())
    assert area.x() + m <= frame.x()
    assert frame.x() + frame.width() <= area.x() + area.width() - m
    assert area.y() + m <= top and bottom <= area.y() + area.height() - m
    # OK and Cancel are inside the window, not cut off below it
    bb = dlg.findChild(QDialogButtonBox)
    for which in (QDialogButtonBox.StandardButton.Ok,
                  QDialogButtonBox.StandardButton.Cancel):
        b = bb.button(which)
        assert b.isVisible()
        r = QRect(b.mapTo(dlg, QPoint(0, 0)), b.size())
        assert dlg.rect().contains(r), (which, r, dlg.rect())
    # the pages scroll inside the smaller window; the buttons are not in them
    for i in range(dlg._tabs.count()):
        assert isinstance(dlg._tabs.widget(i), QScrollArea)
    p = bb.parentWidget()
    while p is not None:
        assert not isinstance(p, QScrollArea)
        p = p.parentWidget()
    dlg.close()
    dlg.deleteLater()


def test_a_window_hanging_off_the_bottom_is_moved_back_on(qapp, monkeypatch):
    dlg = _dialog(qapp, monkeypatch, AIR_13)
    dlg.show()
    _pump(qapp)
    dlg.move(dlg.x(), AIR_13.y() + AIR_13.height() - 100)
    dlg._keep_on_screen()
    m = SettingsDialog._SCREEN_MARGIN
    bottom = dlg.frameGeometry().y() + dlg.height() + dlg._caption_height()
    assert bottom <= AIR_13.y() + AIR_13.height() - m
    dlg.close()
    dlg.deleteLater()
