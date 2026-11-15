"""The owner, during the 4.3.39 integration: in a German window two buttons
overlapped ("Nur das Chart ersetzen"). Reproduced on screen: the four-choice
window "Where should this patch set's chart go?" (a run holding a chart and a
measurement) laid "Lieber als neuen Lauf bauen" under "Nur das Chart ersetzen":
four choices and Cancel need more than the 1000 px Qt allows a message box,
and the row was squeezed. `_choice_dialog` now stacks the buttons when side by
side they cannot fit, for every caller.

For each of the 14 languages, the window is built with that language's own
labels (the longest set the app has for it) and shown; no two button
rectangles may intersect and no label may be wider than its button.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

LANGS = ["en", "de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
         "sv", "uk", "zh_CN"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def language():
    from core import i18n
    before = i18n.current_language()
    yield i18n.set_language
    i18n.set_language(before)


def _four_choices():
    from core.i18n import tr
    run = tr("Run {n}").format(n=1)
    desc = tr("Build it as a new run instead") + ". " * 40
    return [(tr("Replace {run}").format(run=run), desc, "into_replace"),
            (tr("Build it as a new run instead"), desc, "into_new"),
            (tr("Replace only the chart"), desc, "into_chart"),
            (tr("Start a new project"), desc, "new")]


def _shown(qapp, box):
    """Show *box* as the app would and measure it: (box size, button rects,
    labels wider than their buttons)."""
    box.show()
    for _ in range(5):
        qapp.processEvents()
    rects = [(b.text(), QRect(b.mapTo(box, b.rect().topLeft()), b.size()))
             for b in box.buttons()]
    cut = [(b.text(), b.fontMetrics().horizontalAdvance(b.text()), b.width())
           for b in box.buttons()
           if b.width() < b.fontMetrics().horizontalAdvance(b.text())
           or b.mapTo(box, b.rect().topRight()).x() > box.width()]
    return (box.width(), box.height()), rects, cut


@pytest.mark.parametrize("code", LANGS)
def test_no_two_buttons_overlap_and_none_is_cut(qapp, language, code):
    language(code)
    from core.i18n import tr
    from ui.ti2_loader import _choice_box
    seen = {}

    def door(box):
        seen["m"] = _shown(qapp, box)
        box.hide()
        box.deleteLater()
        return None
    assert _choice_box(None, tr("Where should this patch set's chart go?"),
                       "", _four_choices(), _exec_choice_box=door) is None
    _size, rects, cut = seen["m"]
    qapp.processEvents()
    assert len(rects) == 5
    for i, (ta, ra) in enumerate(rects):
        for tb, rb in rects[i + 1:]:
            assert not ra.intersects(rb), (code, ta, ra, tb, rb)
    assert not cut, (code, cut)


def test_stacked_the_window_keeps_its_width(qapp, language):
    """Stacked, the window stays as wide as a message box may be, so its
    text is not wrapped to twice its height (German: 618 px wide before)."""
    language("de")
    from core.i18n import tr
    from ui.ti2_loader import _choice_box
    from ui.widgets import _message_box_width_limit
    seen = {}

    def door(box):
        seen["m"] = _shown(qapp, box)
        seen["limit"] = _message_box_width_limit(box)
        box.hide()
        box.deleteLater()
    _choice_box(None, tr("Where should this patch set's chart go?"), "",
                _four_choices(), _exec_choice_box=door)
    (w, _h), rects, _cut = seen["m"]
    assert len({r.x() for _t, r in rects}) == 1          # one above the other
    assert w >= seen["limit"] - 40, (w, seen["limit"])
