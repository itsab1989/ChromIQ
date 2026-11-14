"""AN i1iO CUSTOM SIZE IS TURNED ONLY WHEN THE PERSON HAS LEFT BOTH BOXES
(4.3.34 combined review, major, commit 8acbc683f).

The turn ran on the WIDTH box's `editingFinished`, so Tab from width to
height turned a half-typed size: 148 x 210, type 230, Tab -> 210 x 230, type
320 -> built on 210 x 320 instead of the 230 x 320 typed. Now the turn waits
until focus is in neither box; the note and the log name the size finally
used, an upright size is never touched, and a size loaded from a recipe is
not turned by a timer left over from typing.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QLineEdit, QVBoxLayout, QWidget  # noqa: E402


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


@pytest.fixture
def io_panel(qtbot):
    """The panel in a shown, active window with a box to leave the custom
    boxes for (as the person clicks or tabs elsewhere)."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    host = QWidget()
    lay = QVBoxLayout(host)
    p = LayoutOptionsPanel(with_selectors=True, parent=host)
    elsewhere = QLineEdit(host)
    lay.addWidget(p)
    lay.addWidget(elsewhere)
    qtbot.addWidget(host)
    host.show()
    host.activateWindow()
    qtbot.waitExposed(host)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    said: list[str] = []
    p.notice.connect(said.append)
    p._said = said
    p._elsewhere = elsewhere
    p._host = host          # qtbot keeps only a weak reference
    return p


def _set(p, w, h):
    for box, v in ((p.custom_w, w), (p.custom_h, h)):
        box.blockSignals(True)
        box.setValue(v)
        box.blockSignals(False)
    p._custom_turned_lbl.setVisible(False)
    p._said.clear()


def _focus(qtbot, widget):
    widget.setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.waitUntil(widget.hasFocus, timeout=2000)


def _type(qtbot, box, text):
    """Select all and type, as a person does after clicking into a box."""
    _focus(qtbot, box)
    box.selectAll()
    QTest.keyClicks(box.lineEdit(), text)


def _tab_to(qtbot, box, target, key=Qt.Key.Key_Tab):
    QTest.keyClick(box.lineEdit(), key)
    qtbot.wait(30)
    if not target.hasFocus():          # a platform without tab focus chains
        _focus(qtbot, target)
    qtbot.wait(30)


def _leave(qtbot, p):
    _focus(qtbot, p._elsewhere)
    qtbot.wait(50)


def _sizes(p):
    return p.custom_w.value(), p.custom_h.value()


def test_repro_1_width_then_height_is_not_turned_half_typed(qtbot, io_panel):
    p = io_panel
    _set(p, 148, 210)
    _type(qtbot, p.custom_w, "230")
    _tab_to(qtbot, p.custom_w, p.custom_h)
    assert _sizes(p) == (230.0, 210.0), "turned while still typing"
    _type(qtbot, p.custom_h, "320")
    _leave(qtbot, p)
    assert _sizes(p) == (230.0, 320.0)
    assert p.selection()[1] == "230x320"
    assert p._said == [] and not p._custom_turned_lbl.isVisibleTo(p)


def test_repro_2(qtbot, io_panel):
    p = io_panel
    _set(p, 210, 297)
    _type(qtbot, p.custom_w, "320")
    _tab_to(qtbot, p.custom_w, p.custom_h)
    assert _sizes(p) == (320.0, 297.0)
    _type(qtbot, p.custom_h, "230")
    # still inside the height box: nothing turned yet, the build reads upright
    qtbot.wait(50)
    assert _sizes(p) == (320.0, 230.0)
    assert p.selection()[1] == "230x320"
    _leave(qtbot, p)
    assert _sizes(p) == (230.0, 320.0)
    from workflow import measurement_messages as _mm
    assert p._said == [_mm._I1IO_CUSTOM_TURNED.format(w="230", h="320")]
    assert p._custom_turned_lbl.isVisibleTo(p)
    assert p._custom_turned_lbl.text() == p._said[0]


def test_lying_down_is_still_turned_once_both_are_left(qtbot, io_panel):
    p = io_panel
    _set(p, 148, 210)
    _type(qtbot, p.custom_w, "210")
    _tab_to(qtbot, p.custom_w, p.custom_h)
    _type(qtbot, p.custom_h, "148")
    _leave(qtbot, p)
    assert _sizes(p) == (148.0, 210.0)
    assert len(p._said) == 1 and "148" in p._said[0] and "210" in p._said[0]


def test_an_upright_size_is_never_touched(qtbot, io_panel):
    p = io_panel
    _set(p, 148, 210)
    _type(qtbot, p.custom_h, "250")
    _leave(qtbot, p)
    assert _sizes(p) == (148.0, 250.0)
    assert p._said == []


def test_arrow_keys_inside_the_boxes_do_not_turn_until_left(qtbot, io_panel):
    p = io_panel
    _set(p, 200, 201)
    _focus(qtbot, p.custom_h)
    for _ in range(3):
        QTest.keyClick(p.custom_h.lineEdit(), Qt.Key.Key_Down)
    qtbot.wait(50)
    assert _sizes(p) == (200.0, 198.0)          # not turned while inside
    _tab_to(qtbot, p.custom_h, p.custom_w, Qt.Key.Key_Backtab)  # still inside
    qtbot.wait(50)
    assert _sizes(p) == (200.0, 198.0)
    _leave(qtbot, p)
    assert _sizes(p) == (198.0, 200.0)
    assert len(p._said) == 1


def test_a_recipe_load_is_not_turned_by_a_leftover_timer(qtbot, io_panel):
    """Typing then loading an upright recipe: nothing turns, nothing is said."""
    from workflow.layout_engine.presets import default_recipe
    p = io_panel
    _set(p, 148, 210)
    _type(qtbot, p.custom_w, "230")
    _tab_to(qtbot, p.custom_w, p.custom_h)
    r = default_recipe("IO2", "A4")
    r.paper = "200x280"
    p._said.clear()
    p.set_recipe(r)
    _leave(qtbot, p)
    assert p.selection()[1] == "200x280"
    assert _sizes(p) == (200.0, 280.0)
    assert p._said == []


def test_the_timer_is_the_panels_child_and_a_bound_method():
    import inspect
    from ui.dialogs import layout_options_panel as m
    src = inspect.getsource(m.LayoutOptionsPanel.__init__)
    assert "self._custom_turn_timer = QTimer(self)" in src
    assert "timeout.connect(\n                self._turn_custom_upright_when_left)" in src
    assert "editingFinished.connect(self._turn_custom_upright)" not in src


def test_moving_between_the_boxes_in_an_inactive_window_does_not_turn(
        qtbot, io_panel):
    """The application's focus widget is None while another window is
    active; the panel asks its own window where the focus is."""
    p = io_panel
    _set(p, 320, 297)
    other = QWidget()
    qtbot.addWidget(other)
    other.show()
    other.activateWindow()
    qtbot.wait(50)
    p.custom_h.setFocus(Qt.FocusReason.OtherFocusReason)
    assert p.window().focusWidget() is p.custom_h
    p.custom_w.editingFinished.emit()
    qtbot.wait(50)
    assert _sizes(p) == (320.0, 297.0)
    p._elsewhere.setFocus(Qt.FocusReason.OtherFocusReason)
    p.custom_h.editingFinished.emit()
    qtbot.waitUntil(lambda: p.custom_w.value() == 297.0, timeout=2000)
    assert _sizes(p) == (297.0, 320.0)


# ---- the three leftovers of the release review (r2), 2026-11-14 -------------

def test_r2a_paper_away_and_back_while_typing_does_not_turn(qtbot, io_panel):
    """Paper away from Custom and back with 230 half typed turned it at once."""
    p = io_panel
    _set(p, 148, 210)
    _type(qtbot, p.custom_w, "230")
    # The window's focus stays in the box when the combo is changed from
    # outside it (the release review's case: a window that is not the
    # active one keeps its focus widget); here it is put back the same way.
    p._custom_box_has_focus = lambda: True
    p.paper.setCurrentIndex(p.paper.findData("A4"))
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    qtbot.wait(30)
    assert _sizes(p) == (230.0, 210.0), "turned while still typing"
    assert p.selection()[1] == "210x230", "the build reads it upright anyway"
    del p._custom_box_has_focus
    assert p._said == []
    _focus(qtbot, p.custom_w)           # the person goes on in the box …
    _leave(qtbot, p)                    # … and leaves it
    assert _sizes(p) == (210.0, 230.0)
    assert len(p._said) == 1 and p._custom_turned_lbl.isVisibleTo(p)


def test_r2b_instrument_away_and_back_keeps_the_note_with_the_size(
        qtbot, io_panel):
    """A turned size came back from another instrument upright with its
    line gone; the line belongs to the size until a size is typed."""
    p = io_panel
    _set(p, 148, 210)
    _type(qtbot, p.custom_w, "230")
    _leave(qtbot, p)
    assert _sizes(p) == (210.0, 230.0) and p._custom_turned_lbl.isVisibleTo(p)
    note = p._custom_turned_lbl.text()
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    assert not p._custom_turned_lbl.isVisibleTo(p), "the i1Pro says nothing"
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    assert _sizes(p) == (210.0, 230.0)
    assert p._custom_turned_lbl.isVisibleTo(p)
    assert p._custom_turned_lbl.text() == note
    # a size typed again takes the line away
    _type(qtbot, p.custom_h, "250")
    assert not p._custom_turned_lbl.isVisibleTo(p)


def test_r2c_a_build_shows_the_size_it_uses_in_the_boxes(qtbot, io_panel):
    """Return in a box, then Generate with the cursor still there: the
    boxes and the line now show the upright size the build uses."""
    p = io_panel
    _set(p, 148, 210)
    _type(qtbot, p.custom_w, "300")
    _tab_to(qtbot, p.custom_w, p.custom_h)
    _type(qtbot, p.custom_h, "200")
    QTest.keyClick(p.custom_h.lineEdit(), Qt.Key.Key_Return)
    qtbot.wait(30)
    assert p.custom_h.hasFocus() and _sizes(p) == (300.0, 200.0)
    built = p.selection()[1]
    p.commit_custom_size()              # what Generate calls first
    assert built == "200x300"
    assert _sizes(p) == (200.0, 300.0)
    assert p._custom_turned_lbl.isVisibleTo(p) and len(p._said) == 1
    _leave(qtbot, p)
    assert len(p._said) == 1, "said once, not again on leaving"


def test_r2c_generate_calls_the_commit_first():
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_generate)
    assert src.index("commit_custom_size()") < src.index("_mode_name() == \"gamut\"")


def test_r2b_leaving_the_i1io_while_typing_turns_it_and_says_so(qtbot,
                                                                io_panel):
    """Typing 230, then another instrument and back: the size came back
    upright with no line. It is turned on leaving, and the line comes back
    with it."""
    p = io_panel
    _set(p, 148, 210)
    _type(qtbot, p.custom_w, "230")
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    qtbot.wait(30)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    if p.paper.currentData() != "__custom__":
        p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    qtbot.wait(30)
    assert _sizes(p) == (210.0, 230.0)
    assert p._custom_turned_lbl.isVisibleTo(p), "upright, but nothing said"
    assert "210 x 230" in p._custom_turned_lbl.text()
