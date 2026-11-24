"""Item 46: every ready-made size name of the Barbieri group is fully
readable, in every language, in the closed box and in the open list.

In 4.3.63 four of six names were cut ("Letter landscape, one p...") because
the box took only the room beside its label and the list was as wide as the
box. The group's inner width at the pane's locked minimum is 482 px; the box
now spans it, wraps the chosen text and the list grows to its widest name.
"""
import inspect

import pytest
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtWidgets import QApplication, QStyleOptionComboBox

from core import i18n
from ui.dialogs import barbieri_panel

PANEL_WIDTH = 520  # the Create Chart pane is locked at 580 (scroll bar, margins)


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


def _box():
    """The real group in the real panel, at the pane's locked width."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    host = LayoutOptionsPanel(with_selectors=True)
    host.resize(PANEL_WIDTH, 900)
    host.show()
    host._barbieri_group.setVisible(True)
    QApplication.processEvents()
    return host, host.barbieri_size


def test_the_panel_builds_the_size_box_from_the_full_text_class():
    src = inspect.getsource(barbieri_panel)
    assert "self.barbieri_size = FullTextComboBox(" in src


@pytest.mark.parametrize("code", [c for c, _n in i18n.available_languages()])
def test_every_size_name_fits_closed_and_open(code):
    i18n.set_language(code)
    host, box = _box()
    try:
        fm = box.fontMetrics()
        opt = QStyleOptionComboBox()
        box.initStyleOption(opt)
        edit = box._edit_rect(opt).adjusted(2, 0, -2, 0)
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
        # closed: the chosen name, wrapped, fits the box on every choice
        for i in range(box.count()):
            box.setCurrentIndex(i)
            QApplication.processEvents()
            opt = QStyleOptionComboBox()
            box.initStyleOption(opt)
            edit = box._edit_rect(opt).adjusted(2, 0, -2, 0)
            r = fm.boundingRect(QRect(0, 0, edit.width(), 10000),
                                int(Qt.TextFlag.TextWordWrap),
                                box.itemText(i))
            assert r.width() <= edit.width(), (code, i, box.itemText(i))
            assert r.height() <= box.height(), (code, i, box.itemText(i))
    finally:
        host.close()
