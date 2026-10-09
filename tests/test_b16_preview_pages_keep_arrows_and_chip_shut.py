"""Basti, beta 15 on macOS Sequoia, measuring (#182 6079656873): after the
measurement had moved to page 2 by itself he went back to page 1 to look at
the overlays, and

(a) from then on the preview chip stayed OPEN and never closed;
(b) back on page 2 the "next strip" arrows were missing until he clicked a
    strip.

Both reproduced on screen with a simulated measurement (ChromIQ engine and
the replay instrument, Demo-Full-RGB run 3, four pages):

(a) the page buttons TAKE the keyboard focus on a click. When "Next" reached
    the last page it was disabled while it held the focus, and Qt handed the
    focus to the next widget in the chain with ``Qt.TabFocusReason``; that
    widget was the chip, which opens and rings for keyboard focus, so it stayed
    open on every page until something else took the focus.
(b) every page change set the preview's active strip to -1, and nothing set it
    again until the reader moved, so the reader's page came back bare.
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget


def _pages(tmp_path, n):
    out = []
    for i in range(n):
        p = tmp_path / f"chart_{i + 1:02d}.tif"
        Image.fromarray(np.full((120, 90, 3), 200 - 20 * i, np.uint8), "RGB").save(p)
        out.append(p)
    return out


@pytest.fixture()
def preview(qapp, tmp_path):
    from ui.tiff_preview import TiffPreview
    top = QWidget()
    lay = QVBoxLayout(top)
    pv = TiffPreview(top)
    lay.addWidget(pv)
    top.resize(700, 600)
    pv.load_tiff(_pages(tmp_path, 3))
    top.show()
    qapp.processEvents()
    yield top, pv
    top.close()
    top.deleteLater()
    qapp.processEvents()


def _with_chip(pv):
    """The chip as the Measure tab's RGB chart page shows it: created after
    the page buttons, so it comes after them in the focus chain."""
    pv._set_print_view(device=True, title="Device values, no profile yet",
                       hint="", tooltip="t", switchable=False)
    pv._show_print_chip()
    chip = pv._print_chip
    assert chip is not None and chip.isVisible()
    return chip


def test_reaching_the_last_page_never_hands_the_focus_to_the_chip(preview, qapp):
    top, pv = preview
    chip = _with_chip(pv)
    QApplication.setActiveWindow(top)
    qapp.processEvents()
    QTest.mouseClick(pv._next_btn, Qt.MouseButton.LeftButton)   # page 2
    assert pv.current_page() == 1
    QTest.mouseClick(pv._next_btn, Qt.MouseButton.LeftButton)   # page 3, the last
    assert pv.current_page() == 2 and not pv._next_btn.isEnabled()
    # checked at once: the deferred render may hide the chip afterwards
    assert top.focusWidget() is not chip, "Qt handed the disabled Next's focus to the chip"
    assert not chip.is_open(), "the chip opened for a focus nobody gave it"
    assert top.focusWidget() is pv._prev_btn


def test_reaching_the_first_page_hands_the_focus_to_next(preview, qapp):
    top, pv = preview
    _with_chip(pv)
    QApplication.setActiveWindow(top)
    pv.show_page(1)
    qapp.processEvents()
    QTest.mouseClick(pv._prev_btn, Qt.MouseButton.LeftButton)
    assert pv.current_page() == 0
    assert top.focusWidget() is pv._next_btn


def test_a_single_page_takes_the_focus_off_the_hidden_buttons(preview, qapp, tmp_path):
    top, pv = preview
    chip = _with_chip(pv)
    QApplication.setActiveWindow(top)
    pv._next_btn.setFocus(Qt.FocusReason.MouseFocusReason)
    assert top.focusWidget() is pv._next_btn
    pv._pages = pv._pages[:1]
    pv._current = 0
    pv._update_nav()
    assert top.focusWidget() is not chip and not chip.is_open()


def test_the_readers_arrows_come_back_with_its_page(preview, qapp):
    top, pv = preview
    rects = [QRect(10, 10, 20, 100), QRect(40, 10, 20, 100)]
    pv.set_stripe_rects(rects)
    pv.show_page(1)                 # the reader moved on to page 2 ...
    pv.highlight_stripe(0)          # ... and its first strip
    assert pv.active_stripe_on_screen() == 0
    QTest.mouseClick(pv._prev_btn, Qt.MouseButton.LeftButton)   # look at page 1
    assert pv.current_page() == 0
    assert pv.active_stripe_on_screen() == -1, "page 1 must not show page 2's arrows"
    QTest.mouseClick(pv._next_btn, Qt.MouseButton.LeftButton)   # back to page 2
    assert pv.current_page() == 1
    assert pv._active_stripe == 0, "the arrows were dropped by the page change"
    assert pv.active_stripe_on_screen() == 0


def test_clearing_the_highlight_still_clears_it_everywhere(preview):
    _top, pv = preview
    pv.set_stripe_rects([QRect(10, 10, 20, 100)])
    pv.show_page(1)
    pv.highlight_stripe(0)
    pv.highlight_stripe(-1)
    for page in (0, 1, 2):
        pv.show_page(page)
        assert pv.active_stripe_on_screen() == -1
