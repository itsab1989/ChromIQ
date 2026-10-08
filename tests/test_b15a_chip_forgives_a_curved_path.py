"""b15a (Basti, 2026-10-08): the preview chip must not close the instant the
pointer leaves it.

The "Paper white" button sits at the LEFT end of the open chip, the icon at
the right. Until beta 14 the chip collapsed on the first Leave, so the button
could only be reached along a perfectly straight path inside a 22 px pill.

Now an open chip waits LEAVE_GRACE_MS after the pointer left, keeps waiting
while the pointer is within HOVER_MARGIN px of it, and coming back cancels
the close. The 170 ms animation and the keyboard behaviour are unchanged.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def chip(qapp, monkeypatch):
    from PyQt6.QtWidgets import QWidget
    from ui import print_view_chip as C
    monkeypatch.setattr(C, "reduce_motion", lambda: True)   # no animation wait
    host = QWidget()
    host.resize(400, 120)
    c = C.PrintViewChip(host)
    c.set_state(icon=C.ICON_PAPER, title="As on paper",
                hint="click: device values", tooltip="tip", switchable=True,
                paper_white=False, paper_label="Paper white")
    c.place(390, 10)
    host.show()
    yield c
    host.hide()
    host.deleteLater()


def _enter(chip):
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QEnterEvent
    chip.enterEvent(QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))


def _leave(chip):
    from PyQt6.QtCore import QEvent
    chip.leaveEvent(QEvent(QEvent.Type.Leave))


def test_the_grace_is_a_deliberate_half_second():
    from ui import print_view_chip as C
    assert 400 <= C.LEAVE_GRACE_MS <= 600
    assert 8 <= C.HOVER_MARGIN <= 20
    assert C.ANIM_MS == 170                     # the animation is kept


def test_leaving_does_not_close_at_once(chip, monkeypatch, qtbot):
    monkeypatch.setattr(chip, "_pointer_in_zone", lambda: False)
    _enter(chip)
    assert chip.is_open() and chip.width() == chip.expanded_width()
    _leave(chip)
    # the instant after the Leave, it is still open: the button can be reached
    assert chip.is_open() and chip.closing()
    assert chip.width() == chip.expanded_width()
    assert chip.paper_white_button().isVisibleTo(chip)
    qtbot.waitUntil(lambda: not chip.is_open(), timeout=3000)
    assert chip.width() == chip.collapsed_width()


def test_coming_back_cancels_the_close(chip, monkeypatch, qtbot):
    monkeypatch.setattr(chip, "_pointer_in_zone", lambda: False)
    _enter(chip)
    _leave(chip)
    assert chip.closing()
    _enter(chip)                                # back on the chip (or button)
    assert not chip.closing()
    qtbot.wait(800)                             # well past the grace
    assert chip.is_open() and chip.width() == chip.expanded_width()


def test_a_pointer_close_by_keeps_it_open(chip, monkeypatch, qtbot):
    near = {"v": True}
    monkeypatch.setattr(chip, "_pointer_in_zone", lambda: near["v"])
    _enter(chip)
    _leave(chip)
    qtbot.wait(900)                             # past the grace, still near
    assert chip.is_open()
    near["v"] = False                           # now really gone
    qtbot.waitUntil(lambda: not chip.is_open(), timeout=2000)


def test_the_zone_is_the_chip_grown_by_the_margin(chip):
    from ui import print_view_chip as C
    _enter(chip)
    z = chip.hover_zone()
    g = chip.geometry()
    tl = chip.mapToGlobal(chip.rect().topLeft())
    assert z.left() == tl.x() - C.HOVER_MARGIN
    assert z.top() == tl.y() - C.HOVER_MARGIN
    assert z.width() == g.width() + 2 * C.HOVER_MARGIN
    assert z.height() == g.height() + 2 * C.HOVER_MARGIN


def test_a_hidden_chip_closes_without_waiting(chip, monkeypatch):
    monkeypatch.setattr(chip, "_pointer_in_zone", lambda: True)
    _enter(chip)
    _leave(chip)
    chip.hide()
    assert not chip.is_open() and not chip.closing()


def test_a_collapsed_chip_has_nothing_to_wait_for(chip):
    _leave(chip)                                # never opened
    assert not chip.closing() and not chip.is_open()
