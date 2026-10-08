"""Beta 13 review of b13a and b13c.

1. The floating honesty badge ("Approximate colours ...", shown on a
   device-native page with no known ink set) is anchored to the TOP right of
   the image area since #125 (Knut: the bottom is where the tabs keep their
   controls). Only its first placement followed that rule: the preview's
   resizeEvent still moved it to the widget's bottom right, the pre-#125 rule,
   so after any resize it left the image and sat on "Page 1 / 1" and the
   panel below. Measured on screen: y 54 when it appeared, 241 after the
   window was resized. It now follows the image area like the preview chip.

2. Preferences, dragged from a large display to a small one, kept the floor
   it was given on the large one: the user could not make it smaller, so OK
   and Cancel stayed below the edge of the small screen, which is the fault
   b13c fixed for opening. A screen change now lowers the floor to the new
   work area.

3. The narrowest real screens (a Windows laptop at 125 %, 1093 points wide;
   1024 at 1280x800 and 125 %) are narrower than the opening width (the tab
   bar's), which b13c caps; the layout floor (the button row) is what is left,
   and it must still fit them.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QDialogButtonBox

from ui.dialogs.settings_dialog import SettingsDialog


def _pump(qapp, n=6):
    for _ in range(n):
        qapp.processEvents()


# ---------------------------------------------------------------- the badge
@pytest.fixture()
def preview(qapp, monkeypatch):
    from ui import tiff_preview as TP
    monkeypatch.setattr(TP, "last_render_mode", lambda: "approx")
    pv = TP.TiffPreview()
    pv.resize(900, 700)
    pv.show()
    _pump(qapp)
    pv._update_render_badge()
    _pump(qapp)
    yield pv
    pv.close()
    pv.deleteLater()


def _badge_vs_rule(pv):
    b = pv._badge_lbl
    o = pv._img_label.mapTo(pv, QPoint(0, 0))
    want = (o.x() + pv._img_label.width() - b.width() - 10, o.y() + 10)
    return (b.x(), b.y()), want


def test_the_badge_appears_top_right_of_the_image(preview):
    assert preview._badge_lbl is not None and preview._badge_lbl.isVisible()
    got, want = _badge_vs_rule(preview)
    assert got == want


@pytest.mark.parametrize("size", [(700, 500), (1200, 900), (640, 1000)])
def test_the_badge_stays_top_right_after_a_resize(qapp, preview, size):
    preview.resize(*size)
    _pump(qapp)
    got, want = _badge_vs_rule(preview)
    assert got == want, (
        f"after a resize to {size} the badge sits at {got}, not at the image "
        f"area's top right {want}: it went back to the widget's bottom right")


def test_the_badge_follows_the_image_when_the_header_grows(qapp, preview):
    # the image moves down without the preview resizing (b13a's own case)
    preview._header_image_gap.setVisible(True)
    _pump(qapp)
    got, want = _badge_vs_rule(preview)
    assert got == want


def test_resize_event_has_no_second_badge_rule():
    import inspect
    from ui.tiff_preview import TiffPreview
    src = inspect.getsource(TiffPreview.resizeEvent)
    assert "_badge_lbl.move" not in src
    assert "_place_render_badge" in src


# ------------------------------------------------------- Preferences, screens
def _dialog(qapp, monkeypatch, area_ref: list) -> SettingsDialog:
    from core.settings import AppSettings
    monkeypatch.setattr(SettingsDialog, "_work_area",
                        lambda self: QRect(area_ref[0]))
    return SettingsDialog(AppSettings())


def test_a_screen_change_lowers_the_floor_to_the_new_screen(qapp, monkeypatch):
    big = QRect(0, 25, 3000, 2000)
    air = QRect(0, 37, 1470, 956 - 37 - 70)
    area = [big]
    dlg = _dialog(qapp, monkeypatch, area)
    floor_on_big = dlg.minimumHeight()
    m, cap = SettingsDialog._SCREEN_MARGIN, SettingsDialog._CAPTION_GUESS
    assert floor_on_big + cap > air.height() - 2 * m, (
        "the test needs a floor that does not fit the small screen")
    area[0] = air
    dlg._on_screen_changed(None)
    assert dlg.minimumHeight() + cap <= air.height() - 2 * m
    assert dlg.height() + cap <= air.height() - 2 * m
    dlg.deleteLater()


def test_the_dialog_follows_its_window_handle_screen():
    import inspect
    src = inspect.getsource(SettingsDialog.showEvent)
    assert "screenChanged.connect(self._on_screen_changed)" in src


@pytest.mark.parametrize("area", [QRect(0, 0, 1093, 574),   # 1366x768 @125 %
                                  QRect(0, 0, 1024, 600)])  # 1280x800 @125 %
def test_a_small_windows_laptop_still_shows_ok_and_cancel(qapp, monkeypatch,
                                                         area):
    dlg = _dialog(qapp, monkeypatch, [area])
    m = SettingsDialog._SCREEN_MARGIN
    assert dlg.width() <= area.width() - 2 * m
    dlg.show()
    _pump(qapp)
    bb = dlg.findChild(QDialogButtonBox)
    for which in (QDialogButtonBox.StandardButton.Ok,
                  QDialogButtonBox.StandardButton.Cancel):
        b = bb.button(which)
        r = QRect(b.mapTo(dlg, QPoint(0, 0)), b.size())
        assert dlg.rect().contains(r), (which, r, dlg.rect())
    dlg.close()
    dlg.deleteLater()
