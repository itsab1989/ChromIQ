"""However many reference sets are in force, the window stays on the screen.

B8-547, found by challenge round 31 by LOOKING at a photograph rather than at
the per-widget numbers, every one of which said the window was clean. No label
was clipped; the rows simply overlapped.

Measured on screen on a 1728x1079 display: the eleven sets ChromIQ ships open
this window at 626 px in English and 642 px in German. Fogra's published
archive, which this window's own help text tells the user to drop in exactly as
downloaded, carries 22 sets at two lines each, and the window grew to **1376 px
against 1079 px of available screen**. The Close button sat below the bottom of
the display, and once macOS clamped the height the rows began to overlap: 231
overlapping pairs in the German run.

A cap alone would have been worse than the fault, because it hides rows with no
way to reach them. The content scrolls instead, and the second test here is the
one that keeps that honest: with what ChromIQ actually ships, nothing scrolls
and the window is the window Sebastian specified.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from PyQt6.QtWidgets import QApplication


def _dialog(qapp):
    """Built AND SHOWN, because an unshown dialog has no layout.

    The first draft of this file measured `verticalScrollBar().maximum()` on a
    dialog that had only been constructed. Its viewport was 30 px tall, so the
    bar reported 378 px of scrolling on content that fits, and the test failed
    the product for a state no user is ever in. That is the same trap that has
    produced three false findings on this project: a widget answers questions
    about a geometry it has not been given yet.
    """
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    dlg = ReferenceValuesDialog(None)
    dlg.show()
    qapp.processEvents()
    return dlg


def _available_height(dlg) -> int:
    screen = dlg.screen() or QApplication.primaryScreen()
    return int(screen.availableGeometry().height())


def test_the_whole_published_archive_does_not_push_the_window_off_screen(
        qapp, monkeypatch):
    """Twenty-two sets, which is what Fogra's own archive installs.

    MUTATION, proven to land: drop the `min(...)` against the screen in
    `_opening_height` and the window opens taller than the display again.
    """
    from workflow import reference_sets as rs

    real = rs.available()
    assert real, "no reference sets at all; this test would prove nothing"
    many = []
    for n in range(22):
        base = real[n % len(real)]
        many.append(replace(base, id=f"FOGRA{40 + n}"))
    monkeypatch.setattr(rs, "available", lambda: many)

    dlg = _dialog(qapp)
    try:
        assert len(dlg._rows) >= 22, (
            f"the window drew {len(dlg._rows)} rows for 22 sets plus ISO")
        room = _available_height(dlg)
        assert dlg.height() <= room, (
            f"the window opens {dlg.height()} px tall on {room} px of screen, "
            "so its Close button is off the bottom and the rows overlap once "
            "the window manager clamps it")
        # AND EVERY ROW IS STILL REACHABLE, which is the half a cap alone
        # would have failed. The content is taller than the viewport, so the
        # scroll area must actually be able to move.
        bar = dlg._scroll.verticalScrollBar()
        assert bar.maximum() > 0, (
            "the content does not fit and yet nothing scrolls, so the rows "
            "below the fold cannot be reached at all")
    finally:
        dlg.close()


def test_what_chromiq_ships_opens_exactly_as_it_did(qapp):
    """The eleven bundled sets must not gain a scroll bar.

    Sebastian specified one door and a small window behind it. The scroll area
    is there for the archive case and is meant to be invisible otherwise, so
    this pins that it is: nothing to scroll, and a window well inside the
    screen.

    MUTATION, proven to land: give the scroll area a fixed height smaller than
    its content and this goes red.
    """
    dlg = _dialog(qapp)
    try:
        bar = dlg._scroll.verticalScrollBar()
        assert bar.maximum() == 0, (
            f"the shipped sets alone need {bar.maximum()} px of scrolling; "
            "this window is supposed to fit them without any")
        assert dlg.height() < _available_height(dlg), (
            "the window ChromIQ opens out of the box already fills the screen")
    finally:
        dlg.close()


def test_the_sets_are_listed_in_set_number_order(qapp, monkeypatch):
    """A list of 23 rows has to be scannable.

    `available()` orders by printing-condition group, which is right in a
    chooser where the groups are labelled and mean something. This window shows
    no headings, so that order is indistinguishable from none: photographed
    with Fogra's whole archive installed, the rows read 39, 51, 47, 52, 56, 57,
    45, 46, 42, 48, 60, 40, 41.

    MUTATION, proven to land: hand `rs.available()` straight to the item list
    again and this goes red.
    """
    from workflow import reference_sets as rs

    real = rs.available()
    assert len(real) > 3, "too few sets for the order to mean anything"

    dlg = _dialog(qapp)
    try:
        ids = [key for _src, key, _lbl, _btn in dlg._rows
               if key.upper().startswith("FOGRA")]
        assert len(ids) == len(real), (
            f"the window listed {len(ids)} Fogra rows for {len(real)} sets")
        numbers = [int("".join(c for c in i if c.isdigit())) for i in ids]
        assert numbers == sorted(numbers), (
            f"the sets are listed {numbers}, which a reader cannot scan")
    finally:
        dlg.close()
