"""The block of buttons under the scanner preview: what it says, and its shape.

Basti, 2026-09-04, looking at the running window: *"could you task an agent to
rearrange the buttons under the preview in a way it makes sense and takes up
less space?"*

It was four rows for six buttons, grouped by WHEN you press them, with the
longest label in the window — "⤢ Pop out for a bigger view" — alone on the last
one. It is now three rows of two, grouped by WHAT EACH BUTTON ACTS ON, which is
the one thing a user can see:

    ⟳ Rotate 90°      Reset view        the picture
    Auto align        Reset grid        the grid
    Check alignment   ⤢ Pop out         judging where the grid landed

**This file is the ONE place that records the arrangement**, so the next
rearrangement edits one file rather than hunting for the shape in tests that
are about something else. Everything here is a property of the block: what it
is made of, that it reads and tabs in the same order, and that the row it gave
back went to the preview rather than to a spacer.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout      # noqa: E402


class _Runner:
    is_running = False

    def run(self, *a, **k):                                # pragma: no cover
        raise AssertionError("no Argyll in this test")


@pytest.fixture(scope="module")
def dlg(qapp):
    from core.settings import AppSettings
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    d = ScannerProfileDialog(_Runner(), AppSettings())
    yield d
    d.deleteLater()


def _block_rows(d):
    """The rows of the preview's button block, read off the live layout."""
    btns = {d._rotate_btn, d._auto_align_btn, d._reset_btn,
            d._reset_grid_btn, d._check_align_btn, d._popout_btn}
    for lay in d.findChildren(QVBoxLayout):
        rows, found = [], set()
        for i in range(lay.count()):
            row = lay.itemAt(i).layout()
            if not isinstance(row, QHBoxLayout):
                continue
            widgets = [row.itemAt(j).widget() for j in range(row.count())]
            widgets = [w for w in widgets if w in btns]
            if widgets:
                rows.append(widgets)
                found |= set(widgets)
        if found == btns:
            return rows
    raise AssertionError("the six preview buttons are not in one block")


def test_three_rows_of_two_grouped_by_what_each_button_acts_on(dlg):
    """Six buttons, three rows, and each row answers exactly one question."""
    rows = _block_rows(dlg)
    assert [len(r) for r in rows] == [2, 2, 2], (
        f"expected three rows of two, got {[len(r) for r in rows]}")
    assert rows[0] == [dlg._rotate_btn, dlg._reset_btn], (
        "row 1 is the PICTURE: Rotate 90° turns the scan and calls "
        "_reset_view itself, so the two belong together")
    assert rows[1] == [dlg._auto_align_btn, dlg._reset_grid_btn], (
        "row 2 is the GRID: the two ways it gets somewhere")
    assert rows[2] == [dlg._check_align_btn, dlg._popout_btn], (
        "row 3 is the CHECK: by the numbers, or by eye")


def test_the_block_is_one_row_shorter_than_it_was(dlg):
    """Four rows of buttons under a preview is three too many for six of them.

    Pinned as a ceiling rather than as the number 3, so merging further is
    allowed and drifting back to four is not.
    """
    assert len(_block_rows(dlg)) <= 3


def test_tab_follows_the_visual_order(dlg):
    """A block that reads left-to-right and tabs some other way is worse than
    the one it replaced.

    This was WRONG before the rearrangement, and not because of it: the focus
    chain is creation order unless somebody says otherwise, "Check alignment"
    is built last because it arrived last (#108), and adding a layout to
    another layout reparents its widgets — so tabbing reached "Pop out" before
    the button drawn above it. `_order_the_preview_buttons` says otherwise,
    after the panes are built.
    """
    rows = _block_rows(dlg)
    visual = [b for row in rows for b in row]
    wanted = set(visual)
    seen, w, guard = [], visual[0], 0
    while guard < 5000 and len(seen) < len(visual):
        if w in wanted and w not in seen:
            seen.append(w)
        w = w.nextInFocusChain()
        guard += 1
    assert seen == visual, (
        "tab order: " + " → ".join(b.text() for b in seen) +
        "   but the block reads: " + " → ".join(b.text() for b in visual))


def test_the_pop_out_label_is_a_label_and_not_a_sentence(dlg):
    """It was the longest label in the window and cost the block a whole row.

    Shortened, it MUST still say what it does — an unexplained control is not
    an improvement — so what the four dropped words said has to be somewhere a
    user can reach: the tooltip.
    """
    from core.i18n import tr
    assert dlg._popout_btn.text() == tr("⤢ Pop out")
    tip = dlg._popout_btn.toolTip()
    assert tip and "bigger" in tip.lower(), (
        "the short label needs a tooltip that says what it opens")


def test_the_preview_takes_the_height_the_fourth_row_gave_back(qapp):
    """…and the height a taller window brings, which it never used to.

    Measured before this was fixed: a 1500x1000 window left the marquee at
    exactly its `setMinimumHeight(460)` and handed the other 350 px to the
    stretch at the bottom of the column. So removing a row of buttons would
    have bought the preview nothing at all — the spacer would simply have
    grown by 25 px.
    """
    from core.settings import AppSettings
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    d = ScannerProfileDialog(_Runner(), AppSettings())
    try:
        d.show()
        d.resize(1500, 1000)
        d.layout().activate()
        qapp.processEvents()
        assert d._marquee.height() > d._marquee.minimumHeight(), (
            f"the preview is {d._marquee.height()} px tall in a 1000 px "
            f"window and its floor is {d._marquee.minimumHeight()} — the "
            f"spare height went to a spacer again")
    finally:
        d.close()
        d.deleteLater()
