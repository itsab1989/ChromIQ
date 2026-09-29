"""Every serif heading keeps its whole last letter, in every shipped language.

B8-962. Basti, 2026-09-24, beta.40: the "Update available" masthead sliced
the final "e". A fix for exactly that had shipped on 2026-09-21
(`TabHeader._fit_title_ink`), and it covered the TABS only by luck.

Measured on screen at 2x, Georgia 30 px at 85 % spacing:

    heading               advance  ink  label width  label minimum
    Update available          189  191          189             88
    Patch distribution        204  206          204             92
    Update verfügbar          198  200          198             93

The minimum of 88 is the ink of the UNPOLISHED 13 px default font: the fit
ran in `__init__`, before the label's own stylesheet gave it Georgia 30 px,
and nothing re-ran it in a dialog. The tabs were re-fitted by
`apply_theme -> set_appearance`; a dialog built after that never is, and the
label's own FontChange never reaches the header's `changeEvent`.

The label now carries its ink in its size hints (`_InkTitleLabel`), computed
from the polished font whenever the layout asks, plus 2 px: at 2x the
antialiased edge of a round letter lands a device pixel past the integer ink
box.

This test builds each heading the way the app does, with NO font set by hand
and no fit called by hand (the earlier test did both, and so passed on the
code that failed on screen), renders it, and finds the right-most inked
column in the pixels.

MUTATION: make `_InkTitleLabel.sizeHint` and `minimumSizeHint` return
`super()`'s answer unchanged, and this goes red in every language.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPoint
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout

from core import i18n

#: Every title a TabHeader carries: the five tab headings and every dialog
#: masthead (grep `dialog_masthead(` and `TabHeader(` under ui/).
TITLES = (
    "Create test chart", "Print test chart", "Measure printed chart",
    "Build ICC profile", "Check & refine",
    "Update available", "Measurement Report", "Patch distribution",
    "Measurement info", "Profile info", "Read single patches",
    "Report limits", "Soft-proof / check image", "Translate / edit language",
    "Add patches", "Arrange and recolour your patches",
    "Set up your patch set",
)

LANGS = ("en", "de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
         "sv", "uk", "zh_CN")

#: Logical pixels of air required between the last inked column and the
#: label's right edge.
SPARE = 1


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


def _ink_right(img, x0, y0, w, h) -> int:
    """The right-most column inside the rect with a pixel clearly unlike the
    background, which is sampled just past the rect's right edge."""
    bg = img.pixelColor(min(img.width() - 1, x0 + w + 6), y0 + h // 2)
    right = -1
    for x in range(x0, x0 + w):
        for y in range(y0, y0 + h):
            if abs(img.pixelColor(x, y).lightness() - bg.lightness()) > 50:
                right = x
                break
    return right - x0


@pytest.mark.parametrize("code", LANGS)
def test_every_heading_has_air_after_its_last_letter(qapp, code):
    from ui.tab_header import dialog_masthead
    i18n.set_language(code)
    faults = []
    for english in TITLES:
        title = i18n.tr(english)
        dlg = QDialog()
        root = QVBoxLayout(dlg)
        root.setContentsMargins(0, 0, 0, 0)
        head, header, stripe = dialog_masthead(dlg, "EYEBROW", title)
        root.addLayout(head)
        root.addWidget(stripe)
        root.addStretch()
        # Wide enough that nothing but the label's own hint decides its width.
        dlg.resize(max(700, header.sizeHint().width() + 200), 200)
        dlg.show()
        qapp.processEvents()
        lbl = header._title_lbl
        img = dlg.grab().toImage()
        o = lbl.mapTo(dlg, QPoint(0, 0))
        dpr = img.devicePixelRatio()
        x0, y0 = round(o.x() * dpr), round(o.y() * dpr)
        w, h = round(lbl.width() * dpr), round(lbl.height() * dpr)
        ink = _ink_right(img, x0, y0, w, h)
        spare = (w - 1) - ink
        if ink < 0 or spare < SPARE * dpr:
            faults.append(f"{title!r}: label {lbl.width()} px, last inked "
                          f"column {ink / dpr:.1f}, spare {spare / dpr:.1f} px")
        dlg.hide()
        dlg.deleteLater()
    assert not faults, (
        f"[{code}] a heading's last letter touches or crosses the label's "
        "right edge, so it is clipped:\n  " + "\n  ".join(faults))
