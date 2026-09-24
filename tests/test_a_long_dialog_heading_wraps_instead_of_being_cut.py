"""A dialog heading that does not fit its window breaks between words; it is
never cut. Beta 42 challenge, item 2 (2026-09-24).

B8-962 said "a serif heading keeps its whole last letter in every dialog
masthead". It did so by giving the label its ink as a MINIMUM width, and a
minimum is only a request: the patch set editor calls `setMinimumWidth` on
itself, which switches off the layout's own minimum, so a source row that
cannot fit squeezes every item in it below its minimum. Measured on screen:

    uk  "Упорядкуйте та перефарбуйте свої патчі"   label 433 px, ink 482
    pt  "Organize e recolora as suas amostras"       label 349 px, ink 415

both cut mid-word. A dialog heading (`dialog_masthead`, and the three
`TabHeader`s of the patch set editor) now asks for its whole ink on one line
and wraps between words when it is given less; its minimum is its longest
word. The tabs keep one line.

The checks are made on the rendered pixels: the last inked column and the
last inked row of the heading lie inside the label, the label lies inside
its header and inside the window, and it does not run under the next control
in its row.

MUTATION: pass `wrap_title=False` (or drop it) at the patch set editor's
`TabHeader(...)`, or in `dialog_masthead`, and this goes red in uk and pt
(editor) and in most languages at the narrow width (masthead).
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPoint, QRect
from PyQt6.QtWidgets import (QApplication, QDialog, QPushButton, QVBoxLayout,
                             QWidget)

from core import i18n

LANGS = ("en", "de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
         "sv", "uk", "zh_CN")

#: The dialog masthead titles (the same list the B8-962 test uses).
TITLES = (
    "Update available", "Measurement Report", "Patch distribution",
    "Measurement info", "Profile info", "Read single patches",
    "Report limits", "Soft-proof / check image", "Translate / edit language",
    "Add patches", "Arrange and recolour your patches",
    "Set up your patch set",
)


@pytest.fixture(autouse=True)
def _english_and_nothing_left_alive(qapp):
    i18n.set_language("en")
    before = {id(w) for w in QApplication.topLevelWidgets()}
    yield
    for w in QApplication.topLevelWidgets():
        if id(w) not in before:
            w.hide()
            w.setParent(None)
            w.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    i18n.set_language("en")


def _ink_box(img, x0, y0, w, h):
    """Right-most column and bottom-most row inside the rect that hold a
    pixel clearly unlike the background (sampled at the rect's top-left
    corner, which a heading never inks: it is left-aligned from x0 but the
    first row is the ascent's air)."""
    bg = img.pixelColor(x0 + w - 1, y0).lightness()
    right = bottom = -1
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            if abs(img.pixelColor(x, y).lightness() - bg) > 50:
                right = max(right, x - x0)
                bottom = max(bottom, y - y0)
    return right, bottom


def _judge(dlg, header, where) -> "list[str]":
    """Every way a heading can be cut, measured."""
    faults = []
    lbl = header._title_lbl
    title = lbl.text()
    # 1. The label is as tall as its text needs at the width it was given.
    need_h = lbl.heightForWidth(lbl.width()) if lbl.wordWrap() else \
        lbl.sizeHint().height()
    if lbl.height() < need_h:
        faults.append(f"{where} {title!r}: label {lbl.height()} px tall, "
                      f"its lines need {need_h}")
    # 2. Inside its header and inside the window.
    r = QRect(lbl.mapTo(dlg, QPoint(0, 0)), lbl.size())
    hr = QRect(header.mapTo(dlg, QPoint(0, 0)), header.size())
    if not hr.contains(r):
        faults.append(f"{where} {title!r}: label {r} outside its header {hr}")
    if r.right() >= dlg.width() or r.bottom() >= dlg.height():
        faults.append(f"{where} {title!r}: label {r} outside the window "
                      f"{dlg.width()}x{dlg.height()}")
    # 3. Not under the next control in the row.
    for b in dlg.findChildren(QPushButton):
        if not b.isVisible():
            continue
        br = QRect(b.mapTo(dlg, QPoint(0, 0)), b.size())
        if br.intersects(r) and not header.isAncestorOf(b):
            faults.append(f"{where} {title!r}: runs under the button "
                          f"{b.text()!r}")
    # 4. The pixels: every inked column lies inside the label.
    img = dlg.grab().toImage()
    dpr = img.devicePixelRatio()
    x0, y0 = round(r.x() * dpr), round(r.y() * dpr)
    w, h = round(r.width() * dpr), round(r.height() * dpr)
    right, bottom = _ink_box(img, x0, y0, w, h)
    if right < 0:
        faults.append(f"{where} {title!r}: no ink at all")
    elif right >= w - 1:
        # (The bottom is judged by check 1: a descender legitimately inks
        # the last row of a line box.)
        faults.append(f"{where} {title!r}: ink reaches the label's right "
                      f"edge ({right / dpr:.1f} of {r.width()} px)")
    return faults


def _editor():
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    s = AppSettings()
    return Ti2RelayoutDialog(ArgyllRunner(s), s)


class _Screen:
    """A small laptop's screen: 1152 px of work area (a 1366 px panel at
    120 %, or an older 12-inch Mac). The offscreen platform's own is 800 px,
    narrower than the editor's 1000 px floor, which no supported screen is."""

    def __init__(self, w=1152, h=800):
        self._r = QRect(0, 0, w, h)

    def availableGeometry(self):  # noqa: N802
        return QRect(self._r)

    def geometry(self):
        return QRect(self._r)


@pytest.mark.parametrize("code", LANGS)
def test_the_patch_set_editor_heading_is_whole_in_every_language(qapp, code):
    """On a 1152 px screen, at the size it opens with and at the narrowest
    it lets itself be made. Two things make it so and each is a mutation: the
    wrap (without it the Ukrainian row needs 1,274 px, more than the screen,
    and Portuguese 1,227), and the window's floor being its rows' minimum
    (without it Spanish and Portuguese are squeezed at 1000 px, and the wrap
    is computed for a width the heading never gets)."""
    from ui.tab_header import TabHeader
    i18n.set_language(code)
    dlg = _editor()
    screen = _Screen()
    dlg.screen = lambda: screen
    dlg.show()
    qapp.processEvents()
    faults = []
    for width in (dlg.width(), dlg.minimumWidth()):
        dlg.resize(width, dlg.height())
        qapp.processEvents()
        header = dlg.findChildren(TabHeader)[0]
        faults += _judge(dlg, header, f"[{code}] editor at {dlg.width()} px")
    dlg.hide()
    assert not faults, "\n  ".join(["the heading is cut:"] + faults)


@pytest.mark.parametrize("code", LANGS)
def test_a_dialog_masthead_wraps_when_the_window_is_narrow(qapp, code):
    """A window narrower than its heading, as a dialog with its own minimum
    width can be: every title, in every language, wraps and stays whole."""
    from ui.tab_header import dialog_masthead
    i18n.set_language(code)
    faults = []
    for english in TITLES:
        dlg = QDialog()
        dlg.setMinimumWidth(100)          # switches the layout's minimum off
        root = QVBoxLayout(dlg)
        root.setContentsMargins(0, 0, 0, 0)
        head, header, stripe = dialog_masthead(
            dlg, "EYEBROW", i18n.tr(english),
            tooltip_title="t", tooltip_body="b")
        root.addLayout(head)
        root.addWidget(stripe)
        root.addWidget(QWidget(dlg), 1)
        # Narrower than the heading, wider than its longest word: measured
        # here in the label's own font, not asked of the label.
        from PyQt6.QtGui import QFontMetrics
        lbl = header._title_lbl
        lbl.ensurePolished()
        fm = QFontMetrics(lbl.font())
        word = max(fm.tightBoundingRect(w).width() for w in lbl.text().split())
        dlg.resize(max(word + 110, 260), 320)
        dlg.show()
        qapp.processEvents()
        faults += _judge(dlg, header, f"[{code}] masthead at {dlg.width()} px")
        dlg.hide()
        dlg.deleteLater()
    assert not faults, "\n  ".join(["a heading is cut:"] + faults)


def test_a_tab_heading_stays_on_one_line(qapp):
    """The tabs are sized by their heading and keep it on one line: a tab
    heading on two lines would move the module buttons under it."""
    from ui.tab_header import TabHeader
    h = TabHeader("STEP 01", "Create test chart", "#ffb42d", None)
    assert not h._title_lbl.wordWrap()
    h2 = TabHeader("X", "Create test chart", "#ffb42d", None, wrap_title=True)
    assert h2._title_lbl.wordWrap()
