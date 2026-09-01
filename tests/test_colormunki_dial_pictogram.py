"""The ColorMunki dial picture, and the two windows that carry it.

The picture exists to answer "which mark, and which way round" without words,
so what is worth guarding is exactly that: the two states must differ, they must
differ in the right place, and the windows that show them must actually show
them. A wheel drawn identically for both positions would look perfectly fine on
screen and be useless.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                             QVBoxLayout, QWidget)

from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings
from ui.dial_pictogram import dial
from ui.tabs.tab_measure import TabMeasure


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _accent_rows(pix, band: int = 8) -> list[int]:
    """Rows of the image that carry accent (saturated) pixels, top to bottom."""
    img = pix.toImage()
    rows = []
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = img.pixelColor(x, y)
            if c.alpha() > 200 and c.saturation() > 120 and c.value() > 90:
                rows.append(y)
                break
    return rows


def test_the_two_positions_are_not_the_same_picture(qapp):
    cal = dial("calibrate", None, 240)
    mea = dial("measure", None, 240)
    assert cal.toImage() != mea.toImage()


def test_the_measuring_mark_sits_lower_than_the_calibration_mark(qapp):
    """4:30 is above 6:00, so the accent must move DOWN between the two."""
    cal_rows = _accent_rows(dial("calibrate", None, 240))
    mea_rows = _accent_rows(dial("measure", None, 240))
    assert cal_rows and mea_rows
    # The lowest accent pixel: the gear at half past four is higher up the face
    # than the target mark at six o'clock.
    assert max(mea_rows) > max(cal_rows)


def _measure_tab(qapp) -> TabMeasure:
    st = AppSettings()
    return TabMeasure(ArgyllRunner(st), st)


def _pixmap_labels(w: QWidget) -> list[QLabel]:
    return [c for c in w.findChildren(QLabel)
            if c.pixmap() is not None and not c.pixmap().isNull()]


def _dialog_from(tab: TabMeasure, call) -> QDialog:
    """Run one of the two window methods and hand back the window it built.

    NOT by patching `QDialog.exec`. Restoring an inherited `exec` is the leak
    `tests/test_qmessagebox_exec_leak_repair.py` exists to document: it breaks
    every later `box.exec()` in the same worker, and the failure lands on an
    innocent file. So the window is caught the way a user would close it —
    a timer inside the modal loop that finds it on screen and rejects it.
    """
    seen: list[QDialog] = []
    timer = QTimer()
    timer.setInterval(5)

    def _look() -> None:
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible() and w.isModal():
                seen.append(w)
                timer.stop()
                w.reject()
                return

    timer.timeout.connect(_look)
    timer.start()
    try:
        call()
    finally:
        timer.stop()
    assert seen, "the window was never built"
    return seen[0]


@pytest.mark.parametrize("instrument,expected", [
    ("ColorMunki Photo", 1),
    ("i1Pro2", 0),
])
def test_the_calibration_window_draws_the_dial_only_for_the_dial_instrument(
        qapp, instrument, expected):
    tab = _measure_tab(qapp)
    tab._detected_instrument = instrument
    dlg = _dialog_from(
        tab, lambda: tab._on_calibration_prompt(cond="", message="", optional=False))
    assert len(_pixmap_labels(dlg)) == expected


def test_the_measure_window_draws_the_dial(qapp):
    tab = _measure_tab(qapp)
    tab._detected_instrument = "ColorMunki Photo"
    tab._spot_session = False
    tab._guided_refinement_active = False
    tab._resume_active = False
    dlg = _dialog_from(tab, tab._on_calibration_done)
    assert len(_pixmap_labels(dlg)) == 1


def test_no_text_sits_under_the_picture(qapp):
    """Basti, 2026-09-01: every line starts on the same left edge.

    The instrument's own words used to be added to the dialog layout, which put
    them under the wheel instead of beside the paragraph above them. They now
    belong to the same column as the message, so this asserts on the layout
    rather than on pixels.
    """
    tab = _measure_tab(qapp)
    tab._detected_instrument = "ColorMunki Photo"
    dlg = _dialog_from(
        tab,
        lambda: tab._on_calibration_prompt(
            cond="", message="Place instrument on white calibration tile",
            optional=False))

    pic = _pixmap_labels(dlg)[0]
    row = pic.parentWidget().layout().itemAt(0).layout()
    assert isinstance(row, QHBoxLayout)
    column = row.itemAt(1).layout()
    assert isinstance(column, QVBoxLayout)

    texts = [column.itemAt(i).widget().text() for i in range(column.count())
             if column.itemAt(i).widget() is not None]
    assert any("calibrated before measuring" in t for t in texts)
    assert any("What your instrument asked for" in t for t in texts), \
        "the instrument's own words fell out of the text column"
