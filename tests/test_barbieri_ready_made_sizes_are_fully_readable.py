"""Item 46: every ready-made size name of the Barbieri group is fully
readable, in every language, in the closed box and in the open list.

In 4.3.63 four of six names were cut ("Letter landscape, one p...") because
the box took only the room beside its label and the list was as wide as the
box. The box now spans the group, wraps the chosen name and keeps a height
fixed for the language, and the list grows to its widest name.

A first version of the fix passed a test that only measured text widths and
shipped a box whose 38 px minimum height lost to the app's 22 px maximum
(compact inputs): the layout reserved 26 px, the wrapped text was cut and the
box overlapped the row below. So this file looks at the REAL styled panel,
after the event loop has run: the box must be as tall as its text needs, must
not change height when another entry is chosen, and must leave the normal row
spacing to the row below.
"""
import inspect

import pytest
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionComboBox

from core import i18n
from ui.dialogs import barbieri_panel
from ui.styles import APP_STYLESHEET

PANEL_WIDTH = 520  # the Create Chart pane is locked at 580 (scroll bar, margins)
WRAP = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
           | Qt.TextFlag.TextWordWrap)


@pytest.fixture(autouse=True)
def _language_restored():
    before = i18n.current_language()
    yield
    i18n.set_language(before)


@pytest.fixture(autouse=True)
def _barbieri_on():
    from workflow.barbieri import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


def _panel():
    """The real group in the real panel, styled like the app (the stylesheet
    on the widget, never on the application)."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    host = LayoutOptionsPanel(with_selectors=True)
    host.setStyleSheet(APP_STYLESHEET)
    host.resize(PANEL_WIDTH, 900)
    host.show()
    host._barbieri_group.setVisible(True)
    for _ in range(3):
        QApplication.processEvents()
    return host


def _edit_rect(box):
    """The rectangle the text is painted into (the widget's own one when it
    has one, else the style's edit field)."""
    own = getattr(box, "_text_rect", None)
    if own is not None:
        return own()
    opt = QStyleOptionComboBox()
    box.initStyleOption(opt)
    return box.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox, opt,
        QStyle.SubControl.SC_ComboBoxEditField, box)


def _needed_height(box, text):
    """What painting *text* wrapped into the style's edit field needs."""
    w = _edit_rect(box).width()
    return box.fontMetrics().boundingRect(QRect(0, 0, w, 100000), WRAP,
                                          text).height()


def test_the_panel_builds_the_size_box_from_the_full_text_class():
    src = inspect.getsource(barbieri_panel)
    assert "self.barbieri_size = FullTextComboBox(" in src


@pytest.mark.parametrize("code", [c for c, _n in i18n.available_languages()])
def test_every_size_name_fits_closed_and_open(code):
    i18n.set_language(code)
    host = _panel()
    try:
        box = host.barbieri_size
        nxt = host.barbieri_head
        lay = host._barbieri_group.layout()
        fm = box.fontMetrics()
        # open: the list is at least as wide as the widest name
        box.showPopup()
        QApplication.processEvents()
        try:
            need = max(fm.horizontalAdvance(box.itemText(i))
                       for i in range(box.count()))
            assert box.view().width() >= need + 8, (code, need,
                                                    box.view().width())
        finally:
            box.hidePopup()
        # closed: on every choice, after the event loop has run
        heights = set()
        for i in range(box.count()):
            box.setCurrentIndex(i)
            for _ in range(3):
                QApplication.processEvents()
            heights.add(box.height())
            edit = _edit_rect(box)
            text = box.itemText(i)
            # the painted text fits the box: its wrapped height, with the
            # frame's two pixels, is within the real height
            assert _needed_height(box, text) + 2 <= box.height(), (
                code, i, text, _needed_height(box, text), box.height())
            # and no single word is wider than the field
            assert max(fm.horizontalAdvance(w) for w in text.split()) \
                <= edit.width(), (code, i, text)
            # the box does not overlap the row below: the layout's own row
            # spacing is kept between them
            gap = nxt.geometry().top() - box.geometry().bottom() - 1
            assert gap >= lay.verticalSpacing(), (code, i, gap)
        # the height is fixed for the language: choosing another entry never
        # moves the controls below
        assert len(heights) == 1, (code, heights)
    finally:
        host.close()


def test_a_greyed_box_looks_like_the_other_greyed_boxes():
    host = _panel()
    try:
        a, b = host.barbieri_size, host.barbieri_head
        a.setCurrentIndex(1)
        a.setEnabled(False)
        b.setEnabled(False)
        for _ in range(3):
            QApplication.processEvents()

        def text_colour(box):
            img = box.grab().toImage()
            best, best_l = QColor(), -1
            for y in range(4, img.height() - 4):
                for x in range(6, 40):
                    c = img.pixelColor(x, y)
                    if c.lightness() > best_l:
                        best, best_l = c, c.lightness()
            return best

        ca, cb = text_colour(a), text_colour(b)
        assert abs(ca.lightness() - cb.lightness()) <= 14, (ca.name(),
                                                           cb.name())
    finally:
        host.close()


def test_film_sizes_stay_greyed_and_unselectable_without_the_page_beta():
    from workflow.page_output import support as po
    before = po._latched
    po._latched = False
    try:
        host = _panel()
        try:
            box = host.barbieri_size
            model = box.model()
            greyed = [i for i in range(box.count())
                      if not model.item(i).isEnabled()]
            assert greyed, "the film frames must be greyed"
            for i in greyed:
                assert not (model.item(i).flags()
                            & Qt.ItemFlag.ItemIsEnabled)
                assert model.item(i).toolTip()
        finally:
            host.close()
    finally:
        po._latched = before
