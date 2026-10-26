"""The verification pre-flight fits any work area.

Found 2026-10-26: its one-line version is 999 px tall in German, and a work
area below 1000 px (a 13-inch screen with the Dock at the bottom) cannot hold
it. A QMessageBox cannot be shortened, so when, and only when, even the one
line does not fit, its text goes into a scroll area inside the same box
(`tab_measure._scroll_the_preflight_text`). Everything else about the window
stays as it was.
"""
from __future__ import annotations

import inspect

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (QApplication, QCheckBox, QLabel, QMessageBox,
                             QScrollArea)


@pytest.fixture
def _app():
    return QApplication.instance() or QApplication([])


def _preflight_like_box():
    from ui.tabs import tab_measure as TM
    from ui.widgets import fit_message_box_buttons, widen_message_box
    blocks = [(True, "Before you measure this verification chart")]
    blocks += [(False, "This chart can answer 17 of the 18 metrics that the "
                       "available report types and limit sets can use, and "
                       "this line is long enough to wrap.")] * 12
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.NoIcon)
    box.setWindowTitle("Before you measure")
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(TM.preflight_html(blocks))
    ok = box.addButton(QMessageBox.StandardButton.Ok)
    box.setDefaultButton(ok)
    box.setEscapeButton(ok)
    cb = QCheckBox("Do not show this again for this run", box)
    box.setCheckBox(cb)
    widen_message_box(box, TM.preflight_text_width(box))
    fit_message_box_buttons(box)
    return box, ok, cb


def _show(box, app):
    box.show()
    app.processEvents()


def _wait_closed(box):
    # On macOS Qt answers Escape with animateClick, a click 100 ms later.
    for _ in range(100):
        if not box.isVisible():
            return
        QTest.qWait(10)


def test_a_box_that_fits_is_never_touched(_app, monkeypatch):
    from ui.tabs import tab_measure as TM
    box, ok, cb = _preflight_like_box()
    _show(box, _app)
    size, text = box.size(), box.text()
    monkeypatch.setattr(TM, "_preflight_work_height",
                        lambda _b: box.frameGeometry().height() + 40)
    assert TM._scroll_the_preflight_text(box) is False
    _app.processEvents()
    assert box.findChild(QScrollArea, "preflightScroll") is None
    assert box.size() == size and box.text() == text
    box.close()
    box.deleteLater()


def test_a_box_that_does_not_fit_scrolls_and_keeps_everything_else(
        _app, monkeypatch):
    from ui.tabs import tab_measure as TM
    box, ok, cb = _preflight_like_box()
    _show(box, _app)
    tall = box.frameGeometry().height()
    work = tall - 150
    monkeypatch.setattr(TM, "_preflight_work_height", lambda _b: work)
    text, title = box.text(), box.windowTitle()
    assert not TM._preflight_fits(box)

    assert TM._scroll_the_preflight_text(box) is True
    _app.processEvents()
    assert box.frameGeometry().height() <= work, (
        "the box is still taller than the work area")
    assert TM._preflight_fits(box)
    scroll = box.findChild(QScrollArea, "preflightScroll")
    assert scroll is not None and scroll.isVisible()
    assert scroll.verticalScrollBar().maximum() > 0, "nothing to scroll"
    inner = scroll.widget()
    assert isinstance(inner, QLabel)
    assert inner.text() == text
    assert inner.textFormat() == Qt.TextFormat.RichText
    assert not box.findChild(QLabel, "qt_msgbox_label").isVisible()
    # the same window: text, title, icon, buttons, default, Escape, tick
    assert box.text() == text and box.windowTitle() == title
    assert box.icon() == QMessageBox.Icon.NoIcon
    assert box.buttons() == [ok]
    assert box.defaultButton() is ok and box.escapeButton() is ok
    assert box.checkBox() is cb
    assert scroll.focusPolicy() == Qt.FocusPolicy.NoFocus
    # …and Escape still closes it through OK
    cb.setChecked(True)
    QTest.keyClick(box, Qt.Key.Key_Escape)
    _wait_closed(box)
    assert box.clickedButton() is ok
    assert not box.isVisible()
    assert cb.isChecked()
    box.deleteLater()


def test_return_still_presses_ok(_app, monkeypatch):
    from ui.tabs import tab_measure as TM
    box, ok, _cb = _preflight_like_box()
    _show(box, _app)
    work = box.frameGeometry().height() - 150
    monkeypatch.setattr(TM, "_preflight_work_height", lambda _b: work)
    assert TM._scroll_the_preflight_text(box) is True
    _app.processEvents()
    QTest.keyClick(box, Qt.Key.Key_Return)
    _wait_closed(box)
    assert box.clickedButton() is ok
    assert box.result() == QMessageBox.StandardButton.Ok.value
    box.deleteLater()


def test_the_preflight_asks_for_it_only_after_the_one_line_does_not_fit():
    """MUTATION: call `_scroll_the_preflight_text` without asking
    `_preflight_fits` first, or before the one-line version is in, and this
    goes red."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._show_verification_preflight_now)
    one_line = src.index("short=True")
    queued = src.index("QTimer.singleShot(0, _scroll_if_still_too_tall)")
    assert one_line < queued
    body = src[src.index("def _scroll_if_still_too_tall"):]
    assert body.index("if not _preflight_fits(box):") < \
        body.index("_scroll_the_preflight_text(box)")
