"""Beta 16 final review of 2f1d3806b (the preview's page buttons hand their
focus to each other, not to the chip).

The fix must not take the chip out of the keyboard's reach: it is a Tab stop
on purpose (it opens and rings for keyboard focus, beta 12/13), and Tab from a
page button still reaches it and opens it. Measured on screen in the Measure
and Print Chart tabs (Next/Prev -> target bar -> chip, as in beta 15). Only a
focus Qt moves because a button was DISABLED may not land on it.
"""
from __future__ import annotations

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
