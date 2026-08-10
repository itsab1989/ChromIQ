"""The preview's chart-file tooltip owns its tip label (Basti, 2026-08-10).

Qt keeps one shared tooltip label and reuses it while it is on screen —
including while it fades out on macOS — so moving straight from a widget with
a long tooltip into the preview showed the small folder/filename tooltip
inside the previous tooltip's much larger box. The preview now shows that
tooltip in a label of its own, measured for its own text every time.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QEvent, QPoint                   # noqa: E402
from PyQt6.QtGui import QHelpEvent                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def preview(qapp):
    from ui.tiff_preview import TiffPreview
    pv = TiffPreview()
    pv.resize(800, 600)
    pv.show()
    qapp.processEvents()
    yield pv
    pv.hide()


def _tooltip_event(qapp, widget, pos=QPoint(20, 20)):
    ev = QHelpEvent(QEvent.Type.ToolTip, pos, widget.mapToGlobal(pos))
    QApplication.sendEvent(widget, ev)
    qapp.processEvents()


def test_the_file_tip_is_an_owned_label_sized_to_its_text(qapp, preview):
    preview._file_tooltip = "Folder: /tmp/x\n\nchart_01.tif"
    preview._apply_file_tooltip()
    _tooltip_event(qapp, preview._img_label)
    lbl = preview._file_tip_lbl
    assert lbl.isVisible()
    assert lbl.text() == preview._file_tooltip
    short_h = lbl.height()
    assert short_h < 120

    # Longer text grows it; short text shrinks it back — a size can never be
    # inherited from an earlier showing.
    preview._img_label.setToolTip("line\n" * 30)
    _tooltip_event(qapp, preview._img_label)
    assert lbl.height() > short_h
    preview._img_label.setToolTip("short")
    _tooltip_event(qapp, preview._img_label)
    assert lbl.height() <= short_h


def test_the_tip_hides_on_leave_and_stays_off_without_text(qapp, preview):
    preview._file_tooltip = "Folder: /tmp/x\n\np.tif"
    preview._apply_file_tooltip()
    _tooltip_event(qapp, preview._img_label)
    assert preview._file_tip_lbl.isVisible()
    QApplication.sendEvent(preview._img_label, QEvent(QEvent.Type.Leave))
    qapp.processEvents()
    assert not preview._file_tip_lbl.isVisible()

    # No tooltip text (e.g. suppressed during a measurement) → nothing shows.
    preview._img_label.setToolTip("")
    _tooltip_event(qapp, preview._img_label)
    assert not preview._file_tip_lbl.isVisible()


def test_all_three_hover_targets_use_the_owned_label(qapp, preview):
    preview._file_tooltip = "Folder: /tmp/x\n\np.tif"
    preview._apply_file_tooltip()
    for w in (preview._caption_lbl, preview._filename_lbl,
              preview._img_label):
        QApplication.sendEvent(w, QEvent(QEvent.Type.Leave))
        _tooltip_event(qapp, w)
        assert preview._file_tip_lbl.isVisible(), w
        QApplication.sendEvent(w, QEvent(QEvent.Type.Leave))
        qapp.processEvents()
        assert not preview._file_tip_lbl.isVisible(), w
