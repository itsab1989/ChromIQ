"""Beta 16 final review of 2f1d3806b (the preview's page buttons hand their
focus to each other, not to the chip).

The fix must not take the chip out of the keyboard's reach: it is a Tab stop
on purpose (it opens and rings for keyboard focus, beta 12/13), and Tab from a
page button still reaches it and opens it. Measured on screen in the Measure
and Print Chart tabs (Next/Prev -> target bar -> chip, as in beta 15). Only a
focus Qt moves because a button was DISABLED may not land on it.
"""
from __future__ import annotations

import time
import numpy as np
import pytest
from PIL import Image
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget


@pytest.fixture()
def preview(qapp, tmp_path):
    from ui.tiff_preview import TiffPreview
    pages = []
    for i in range(3):
        p = tmp_path / f"chart_{i + 1:02d}.tif"
        Image.fromarray(np.full((120, 90, 3), 200 - 20 * i, np.uint8), "RGB").save(p)
        pages.append(p)
    top = QWidget()
    lay = QVBoxLayout(top)
    pv = TiffPreview(top)
    lay.addWidget(pv)
    top.resize(700, 600)
    pv.load_tiff(pages)
    top.show()
    qapp.processEvents()
    # LET THE PREVIEW'S OWN REFRESH HAPPEN FIRST (agent 22, 2026-10-23).
    # `load_tiff` also starts an 80 ms debounced refresh, and every refresh
    # works the print view out again: this bare preview has print preview
    # off, so a refresh clears `_print_view` and HIDES the chip set by hand
    # below. Once a worker is warm, the line above returns in about 1 ms with
    # that timer still pending, and a loaded machine that pauses this worker
    # for 80 ms lets it fire later, inside the test: Tab from Next then had
    # nothing to reach ("the chip is no longer a keyboard stop", everyday
    # tier on aa3ade0f7). In the app the chip is only ever shown by that
    # refresh, so nothing there can undo it like this.
    _deadline = time.monotonic() + 5.0
    while pv._refresh_timer.isActive() and time.monotonic() < _deadline:
        QTest.qWait(10)
    qapp.processEvents()
    pv._set_print_view(device=True, title="Device values, no profile yet",
                       hint="", tooltip="t", switchable=False)
    pv._show_print_chip()
    QApplication.setActiveWindow(top)
    qapp.processEvents()
    yield top, pv
    top.close()
    top.deleteLater()
    qapp.processEvents()


def test_tab_from_a_page_button_still_reaches_the_chip_and_opens_it(preview, qapp):
    top, pv = preview
    chip = pv._print_chip
    pv._next_btn.setFocus(Qt.FocusReason.TabFocusReason)
    assert top.focusWidget() is pv._next_btn
    for _ in range(6):
        QTest.keyClick(top.focusWidget(), Qt.Key.Key_Tab)
        qapp.processEvents()
        if top.focusWidget() is chip:
            break
    assert top.focusWidget() is chip, "the chip is no longer a keyboard stop"
    assert chip.is_open() and chip._kb_focus


def test_paging_by_mouse_through_every_page_never_opens_the_chip(preview, qapp):
    top, pv = preview
    chip = pv._print_chip
    for btn in (pv._next_btn, pv._next_btn, pv._prev_btn, pv._prev_btn):
        QTest.mouseClick(btn, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert top.focusWidget() is not chip
        assert not chip.is_open()
        assert top.focusWidget() in (pv._prev_btn, pv._next_btn)
        assert top.focusWidget().isEnabled()


def test_a_paused_worker_cannot_hide_the_chip_before_the_test_starts(preview, qapp):
    """The everyday tier on aa3ade0f7 failed the Tab test above while it
    passed alone: the fixture had set the chip up while the preview's own
    debounced refresh was still pending, and on a loaded machine that refresh
    fired inside the test and hid it. Reproduced by pausing the worker for
    longer than the debounce; the fixture now waits for it first."""
    top, pv = preview
    assert not pv._refresh_timer.isActive(), "a refresh is still pending"
    time.sleep(0.12)                 # longer than _REFRESH_DELAY_MS (80 ms)
    qapp.processEvents()
    assert pv._print_chip.isVisible(), "the preview's own refresh hid the chip"
