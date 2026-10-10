"""Beta 17, Basti's hand test of Tools ▸ Read single patches (2026-10-10).

1. "Undo delete" was cut off ("NDO DELET"): the button was fitted to "Delete"
   when the window opened and never again. Now it reserves its longest label,
   and the window is never narrower than its button row.
2. The selected row and the right-click menu's highlighted item were the
   appearance's blue/cyan; they wear the window's green.
3. The hex code on a dark swatch (#34312e) was unreadable: its ink now follows
   the swatch's lightness.
4. The notes under the list are in a splitter with the list, so the user can
   give the list the room.
5. The default height shows seven readings with the notes open, and still fits
   a 13-inch MacBook (1440x900, menu bar and Dock taken off).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPalette  # noqa: E402
from PyQt6.QtTest import QTest                                 # noqa: E402
from PyQt6.QtWidgets import (QApplication, QPushButton,        # noqa: E402
                             QSplitter)

from core import i18n                                          # noqa: E402
from core.argyll_runner import ArgyllRunner                    # noqa: E402
from core.settings import AppSettings                          # noqa: E402
from ui.dialogs import spot_read_dialog as srd                 # noqa: E402
from ui.dialogs.spot_read_dialog import SpotReadDialog         # noqa: E402
from ui.dialogs.tools_dialogs import _popup_pair               # noqa: E402

#: A 13-inch MacBook Air/Pro's default "looks like" resolution, less a notched
#: menu bar (37) and a default Dock at the bottom (about 75).
_SMALL_WORK_AREA_H = 900 - 37 - 75


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _build(qapp, lang="en"):
    i18n.set_language(lang)
    s = AppSettings()
    d = SpotReadDialog(ArgyllRunner(s), s)
    d.show()
    QTest.qWaitForWindowExposed(d, 2000)
    return d


def _close(d):
    d._closing = True
    d.hide()
    d.deleteLater()


def _label_needs(btn: QPushButton, text: str) -> int:
    """The width *text* needs on *btn*: the label as painted (capitals when
    the app's button font asks for them), plus the fitter's own 2 px against
    rounding. The fitter states it as the button's style-sheet min-width,
    which Qt turns into the minimum width with the padding on top."""
    font = btn.font()
    if font.capitalization() == QFont.Capitalization.AllUppercase:
        text = text.upper()
    return QFontMetrics(font).horizontalAdvance(text) + 2


# --- 1. the button fits its longest label ------------------------------------
@pytest.mark.parametrize("lang", ["en", "de", "fr"])
def test_delete_button_is_wide_enough_for_undo_delete(qapp, lang):
    d = _build(qapp, lang)
    try:
        for btn, labels in (
                (d._del_btn, ("Delete", "Undo delete")),
                (d._clear_btn, ("Clear", "Undo clear"))):
            for label in labels:
                need = _label_needs(btn, i18n.tr(label))
                assert btn.minimumWidth() >= need, (lang, label)
    finally:
        _close(d)


@pytest.mark.parametrize("lang", ["en", "de", "fr"])
def test_button_row_does_not_overlap_at_the_minimum_width(qapp, lang):
    d = _build(qapp, lang)
    try:
        for i in range(3):
            d._on_reading((10.0 + i, 10.0, 10.0), (40.0 + i, 0.0, 0.0))
        d._table.selectRow(1)
        d._delete_selected()
        assert d._del_btn.text() == i18n.tr("Undo delete")
        d.resize(d.minimumWidth(), d.height())
        QApplication.processEvents()
        assert d.width() == d.minimumWidth()
        btns = [d._start_btn, d._read_btn, d._avg_btn, d._del_btn,
                d._clear_btn, d._save_btn]
        for b in btns:
            assert b.width() >= b.minimumWidth(), (lang, b.text())
        for a, b in zip(btns, btns[1:]):
            assert a.geometry().right() < b.geometry().left(), \
                (lang, a.text(), b.text())
        assert d.minimumWidth() <= 1440, "must fit a 13-inch screen"
    finally:
        _close(d)


# --- 2. selection and menu wear the window's green ----------------------------
def test_selected_row_and_menu_highlight_are_the_window_accent(qapp):
    d = _build(qapp)
    try:
        bg, fg = _popup_pair(srd._ACCENT)
        d._on_reading((10.0, 10.0, 10.0), (40.0, 0.0, 0.0))
        d._table.selectRow(0)
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            pal = d._table.palette()
            assert pal.color(group, QPalette.ColorRole.Highlight) == QColor(bg)
            assert pal.color(group, QPalette.ColorRole.HighlightedText) \
                == QColor(fg)
        menu = d._table_menu()
        menu.ensurePolished()
        assert menu.palette().color(QPalette.ColorRole.Highlight) == QColor(bg)
        assert menu.palette().color(QPalette.ColorRole.HighlightedText) \
            == QColor(fg)
        menu.deleteLater()
    finally:
        _close(d)


# --- 3. the hex code reads on its own swatch -----------------------------------
def _contrast(a: QColor, b: QColor) -> float:
    def lum(c):
        def lin(v):
            return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        return (0.2126 * lin(c.redF()) + 0.7152 * lin(c.greenF())
                + 0.0722 * lin(c.blueF()))
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_hex_text_reads_on_every_swatch_including_after_undo(qapp):
    d = _build(qapp)
    try:
        labs = [(20.6, 0.6, 2.2), (95, 0, 2), (50, 60, 30), (10, 0, 0),
                (60, 0, 0), (85, -5, 80)]
        for i, lab in enumerate(labs):
            d._on_reading((10.0 + i, 10.0, 10.0), lab)

        def check():
            for r in range(d._table.rowCount()):
                item = d._table.item(r, 7)
                bg = item.background().color()
                fg = item.foreground().color()
                assert _contrast(bg, fg) >= 4.5, (item.text(), fg.name())

        assert d._table.item(0, 7).text() == "#34312e"
        assert d._table.item(0, 7).foreground().color() == QColor("#ffffff")
        check()
        d._table.item(0, 0).setText("Renamed")      # rename
        check()
        d._table.selectRow(0)
        d._delete_selected()
        d._undo_delete()                            # back where it was
        assert d._table.item(0, 7).text() == "#34312e"
        check()
    finally:
        _close(d)


# --- 4. the notes can be resized against the list -----------------------------
def test_list_and_notes_share_a_splitter_with_floors(qapp):
    d = _build(qapp)
    try:
        split = d.findChild(QSplitter, "spotListLogSplit")
        assert split is not None
        assert split.indexOf(d._table) == 0 and split.indexOf(d._log) == 1
        assert not split.childrenCollapsible()
        d._note("CR30: connected.")
        QApplication.processEvents()
        assert d._log.isVisible()
        list_h, log_h = split.sizes()
        assert log_h < list_h
        # drag the notes up as far as they go: the list keeps two readings
        split.moveSplitter(0, 1)
        QApplication.processEvents()
        assert split.sizes()[0] >= d._rows_height(srd._MIN_LIST_ROWS)
        grown = split.sizes()[1]
        assert grown > log_h
        # and down as far as they go: the notes keep two lines
        split.moveSplitter(sum(split.sizes()), 1)
        QApplication.processEvents()
        assert split.sizes()[1] >= d._log_lines_height(srd._MIN_LOG_LINES)
        assert split.sizes()[1] < grown
        # the log no longer has a fixed height
        assert d._log.maximumHeight() > 10000
    finally:
        _close(d)


# --- 5. the default height --------------------------------------------------------
def _rows_fully_visible(d) -> int:
    t = d._table
    return sum(1 for r in range(t.rowCount())
               if t.visualRect(t.model().index(r, 0)).bottom()
               < t.viewport().height())


def test_default_height_shows_seven_readings_with_the_notes_open(qapp):
    d = _build(qapp)
    try:
        for i in range(10):
            d._on_reading((10.0 + i, 10.0, 10.0), (40.0 + i, 0.0, 0.0))
        d._note("CR30: connected.")
        QApplication.processEvents()
        d._table.scrollToTop()
        QApplication.processEvents()
        assert _rows_fully_visible(d) >= 7
        # with its title bar, on a 13-inch MacBook's work area
        assert d.height() + srd._TITLE_BAR <= _SMALL_WORK_AREA_H
    finally:
        _close(d)


def test_default_height_is_capped_by_a_short_screen(qapp, monkeypatch):
    d = _build(qapp)
    try:
        from PyQt6.QtCore import QRect

        class _Screen:
            def availableGeometry(self):
                return QRect(0, 0, 1440, 500)
        monkeypatch.setattr(d, "screen", lambda: _Screen())
        assert d._default_height() <= max(500 - srd._TITLE_BAR,
                                          d.minimumSizeHint().height())
    finally:
        _close(d)
