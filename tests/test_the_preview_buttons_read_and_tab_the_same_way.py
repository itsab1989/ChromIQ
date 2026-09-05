"""The block of buttons under the scanner preview: what it says, and its shape.

Basti, 2026-09-04, looking at the running window: *"could you task an agent to
rearrange the buttons under the preview in a way it makes sense and takes up
less space?"* It was four rows for six buttons, grouped by WHEN you press them,
with the longest label in the window — "⤢ Pop out for a bigger view" — alone on
the last one. Beta 8 made it three fixed rows of two, grouped by WHAT EACH
BUTTON ACTS ON.

Knut then looked at that and asked for the next thing:

    "All the buttons, including the Auto Align are clumped together though…
     They could be aligned better across the width available."

    "I mean, that much space is not needed. The buttons could wrap down to next
     line when no space in width. If you want consistency in position, I get
     it, but at least 3 buttons per line should be possible."

So the block no longer HAS a fixed shape. It is one wrapping row — the
`WrappingButtonRow` the app already had for Create Chart's preset bar, in its
new `balanced` mode — holding the same six buttons in one fixed reading order:

    ⟳ Rotate 90°   Reset view   ⤢ Pop out          what you LOOK at
    Reset grid     Auto align   Check alignment    where the GRID IS

and it lays that sequence out in as few lines as the width allows: 2 + 2 + 2
where only two fit, 3 + 3 at an ordinary window width in all thirteen
languages, one line of six from about 1600 px on.

The order is TWO RUNS OF THREE and it changed with the layout. Basti, on the
wrapping block: *"maybe auto align should be next to check alignment"* — one
action and its verification. Beta 8 grouped in PAIRS because it had three
fixed rows of two to fill; a block that wraps has no rows to fill, its natural
unit is a run, and its commonest shape is 3 + 3 — so the same principle (what
each button acts on) at the granularity the layout uses puts one line on the
picture and one on the grid, and Auto align beside Check alignment.

**This file is the ONE place that records the arrangement**, so the next
rearrangement edits one file rather than hunting for the shape in tests that
are about something else. What it pins is the INTENT — the order, that it
wraps, that it wraps evenly, that it can never widen the window, and that it
tabs the way it reads at every width — not one particular grid, because there
is no longer one particular grid to pin.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget   # noqa: E402


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


#: The order the block is read in, top-left to bottom-right, at every width.
#: A wrapping layout lays its items out in order and chooses only where the
#: lines break, so this sequence IS the reading order however it wraps — which
#: is what lets one fixed tab chain match the visual order at every width.
def _reading_order(d):
    return [d._rotate_btn, d._reset_btn, d._popout_btn,
            d._reset_grid_btn, d._auto_align_btn, d._check_align_btn]


def _flow(d):
    """The block's layout, found from the buttons rather than by name."""
    lay = d._preview_btn_row.layout()
    held = [lay.itemAt(i).widget() for i in range(lay.count())]
    assert held == _reading_order(d), (
        "the block holds " + " → ".join(str(b and b.text()) for b in held))
    return lay


def _lines_at(d, width):
    """The lines the block breaks into when it is *width* px wide."""
    lay = _flow(d)
    return [[it.widget() for it in line] for line in lay._pack(width)]


def _lines_on_screen(d):
    """The same, read off the real geometry rather than from the packer."""
    rows: dict[int, list] = {}
    for b in _reading_order(d):
        rows.setdefault(b.y(), []).append(b)
    return [sorted(rows[y], key=lambda w: w.x()) for y in sorted(rows)]


def test_the_six_buttons_are_one_wrapping_block_in_one_reading_order(dlg):
    """One block, one order, and a layout that can wrap it."""
    from ui.widgets import WrappingButtonRow
    lay = _flow(dlg)
    assert isinstance(lay, WrappingButtonRow), (
        f"the block is a {type(lay).__name__}; a plain box layout cannot wrap "
        f"and answers the window with the SUM of its buttons")
    assert lay._balanced, (
        "balanced mode off: greedy packing leaves one button alone on a "
        "full-width line — see WrappingButtonRow._balance")


def test_the_block_is_two_runs_of_three_and_they_are_in_that_order(dlg):
    """The grouping, and what a wrapping block can promise about it.

    Basti: *"maybe auto align should be next to check alignment"*. That is one
    action and its verification, and taking it re-cuts the block along a
    better line than beta 8's three pairs: the three that act on what you LOOK
    at, then the three that act on where the GRID IS.

    What a flow layout can promise is ADJACENCY IN THE SEQUENCE, and it
    promises it at every width — the layout never reorders, it only chooses
    where the lines break. What it cannot promise by itself is that a break
    never falls between two neighbours; that is measured, in the test below.
    """
    d = dlg
    assert _reading_order(d) == [d._rotate_btn, d._reset_btn, d._popout_btn,
                                 d._reset_grid_btn, d._auto_align_btn,
                                 d._check_align_btn]
    order = _reading_order(d)
    assert order.index(d._check_align_btn) - order.index(d._auto_align_btn) == 1, (
        "Auto align is no longer immediately before Check alignment")
    assert order.index(d._reset_btn) - order.index(d._rotate_btn) == 1, (
        "Rotate 90° and Reset view are no longer neighbours — `rotate_90` "
        "calls `_reset_view` itself, so they belong together")


def test_auto_align_and_check_alignment_share_a_line_at_every_width(dlg):
    """The pairing Basti asked for, swept rather than assumed.

    A line break CAN fall between two neighbours in a flow, and a grouping
    that only holds at some window widths would be worse than none. It never
    falls between these two: balanced packing gives one line of six, then
    3 + 3, then 2 + 2 + 2 as the panel narrows, and every one of those breaks
    after item 3 or item 4. It could only break after item 5 in the shapes
    balancing exists to prevent — 5 + 1 and 3 + 2 + 1 — or below the width
    at which 2 + 2 + 2 stops fitting, which is under this window's own floor.

    Swept here from the widest single button to well past one line, and
    measured the same way in all thirteen languages, from each language's real
    window floor over the next 1200 px: **not one width in 15,600 splits
    them** (`23-buttons-flow`).
    """
    lay = _flow(dlg)
    widths = [lay.itemAt(i).minimumSize().width() for i in range(lay.count())]
    order = _reading_order(dlg)
    auto, check = dlg._auto_align_btn, dlg._check_align_btn
    for w in range(max(widths) * 2 + lay.spacing(),
                   sum(widths) + lay.spacing() * 5 + 200):
        lines = _lines_at(dlg, w)
        home = {b: i for i, line in enumerate(lines) for b in line}
        assert home[auto] == home[check], (
            f"at {w} px the block is "
            f"{[len(ln) for ln in lines]} and puts Auto align on line "
            f"{home[auto]} with Check alignment on line {home[check]}")
    assert order[-2:] == [auto, check]


def test_it_uses_the_width_it_is_given_and_wraps_when_it_is_not(dlg):
    """The whole of what Knut asked for, in one measurement.

    The widths are the layout's own, so this says the same thing in every
    language: the sum of the six is what one line needs, the widest single
    button is what one column needs, and the block has to answer both.
    """
    lay = _flow(dlg)
    items = [lay.itemAt(i) for i in range(lay.count())]
    widths = [it.minimumSize().width() for it in items]
    one_line = sum(widths) + lay.spacing() * (len(widths) - 1)

    assert len(_lines_at(dlg, one_line + 40)) == 1, (
        "given room for all six on one line the block still wraps")
    narrow = max(widths) * 2 + lay.spacing() + 4
    assert len(_lines_at(dlg, narrow)) > 1, (
        "given room for two buttons the block still puts all six on one line")


def test_three_to_a_line_as_soon_as_three_fit(dlg):
    """Knut: *"at least 3 buttons per line should be possible."*

    It is, and this is the width at which it starts: three of that language's
    widest buttons. No FIXED 3 + 3 could promise this — brute-forced over all
    thirteen catalogues, not one exists that fits them all, and German, Spanish
    and Norwegian cannot do 3 + 3 at this window's own floor. A layout that
    wraps promises it wherever it is true instead.
    """
    lay = _flow(dlg)
    widest = max(lay.itemAt(i).minimumSize().width() for i in range(lay.count()))
    room_for_three = widest * 3 + lay.spacing() * 2
    lines = _lines_at(dlg, room_for_three)
    assert [len(ln) for ln in lines] == [3, 3], (
        f"three of the widest button fit in {room_for_three} px and the block "
        f"came out {[len(ln) for ln in lines]}")


def test_it_never_leaves_a_button_alone_on_a_line_it_did_not_have_to(dlg):
    """The balanced half of the layout, swept over every width it can have.

    Justified lines are what makes this matter: a line holding one button
    draws that button at the full width of the panel. Greedy packing does
    exactly that — English at a 1300 px window came out five buttons and then
    "⤢ Pop out" alone on a 648 px line — while the same number of lines held
    3 + 3.
    """
    lay = _flow(dlg)
    widths = [lay.itemAt(i).minimumSize().width() for i in range(lay.count())]
    lo = max(widths) * 2 + lay.spacing()
    hi = sum(widths) + lay.spacing() * (len(widths) - 1)
    for w in range(lo, hi + 1, 3):
        counts = [len(ln) for ln in _lines_at(dlg, w)]
        assert max(counts) - min(counts) <= 1, (
            f"at {w} px the block is {counts} — one line is at least two "
            f"buttons fuller than another")


def test_the_block_cannot_widen_the_window(dlg):
    """A wrapping row's floor is its WIDEST BUTTON, not the sum of them.

    `showEvent` pins the right pane at
    ``max(360, right_pane.minimumSizeHint().width()) + _PANE_GAP``, so what
    this block costs the window is its own minimum width. A QHBoxLayout
    answers "the sum" — 313 px in Spanish, and it was the block's rows that
    the beta 8 arrangement had to be brute-forced against. This answers "my
    widest single button", which is under the 360 px the marquee asks for in
    all thirteen languages, so the block does not reach the window at all.
    Measured before and after, per language: the window's minimum width is
    unchanged to the pixel in every one of the thirteen (`23-buttons-flow`).
    """
    lay = _flow(dlg)
    widths = [lay.itemAt(i).minimumSize().width() for i in range(lay.count())]
    m = lay.contentsMargins()
    assert lay.minimumSize().width() == max(widths) + m.left() + m.right()
    assert lay.minimumSize().width() < sum(widths)
    assert lay.minimumSize().width() <= 360, (
        f"the block asks for {lay.minimumSize().width()} px, which is more "
        f"than the 360 px floor the preview itself sets — it would now be "
        f"what decides how narrow this window can be")


def test_tab_follows_the_visual_order_at_every_width(dlg, qapp):
    """A block that reads left-to-right and tabs some other way is worse than
    the one it replaced.

    This was WRONG before beta 8 rearranged the block, and not because of it:
    the focus chain is creation order unless somebody says otherwise, "Check
    alignment" is built last because it arrived last (#108), and adding a
    layout to another layout reparents its widgets — so tabbing reached "Pop
    out" before the button drawn above it. `_order_the_preview_buttons` says
    otherwise, after the panes are built.

    WRAPPING DOES NOT REOPEN THE QUESTION, and that is worth stating: a
    wrapping layout lays its items out in order and chooses only where the
    lines break, so the reading order is the item order at every width. One
    fixed chain is therefore right at every width — checked here at three of
    them, from one column to one line.
    """
    visual = _reading_order(dlg)
    for width in (max(dlg._rotate_btn.minimumSizeHint().width(), 120),
                  400, 1200):
        assert [b for ln in _lines_at(dlg, width) for b in ln] == visual, (
            f"at {width} px the block reads in a different order")

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


def test_the_block_on_screen_is_the_block_the_packer_describes(qapp):
    """…and it re-wraps when the window is resized, which is the whole point.

    Every check above reads the layout's own packer. This one opens the real
    window at two widths and reads the buttons' geometry, so a packer that is
    right about a block nothing draws cannot pass the file.
    """
    from core.settings import AppSettings
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    d = ScannerProfileDialog(_Runner(), AppSettings())
    try:
        d.show()
        shapes = {}
        for w in (d.minimumWidth(), d.minimumWidth() + 700):
            d.resize(w, 1000)
            d.layout().activate()
            qapp.processEvents()
            qapp.processEvents()
            rows = _lines_on_screen(d)
            shapes[w] = [len(r) for r in rows]
            assert [b for r in rows for b in r] == _reading_order(d), (
                f"at a {w} px window the block does not read in its order")
        narrow, wide = sorted(shapes)
        assert len(shapes[wide]) < len(shapes[narrow]), (
            f"the block is {shapes[narrow]} in a {narrow} px window and "
            f"{shapes[wide]} in a {wide} px one — it is not using the width")
    finally:
        d.close()
        d.deleteLater()


def test_the_preview_takes_the_height_the_wrapped_rows_gave_back(qapp):
    """…and the height a taller window brings, which it never used to.

    Measured before this was fixed: a 1500x1000 window left the marquee at
    exactly its `setMinimumHeight(460)` and handed the other 350 px to the
    stretch at the bottom of the column. So removing a row of buttons would
    have bought the preview nothing at all — the spacer would simply have
    grown by 25 px. It buys more now than it did in beta 8: the block is 72 px
    tall in three lines, 46 in two and 20 in one.
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


# --------------------------------------------------------------------------
# The layout itself, on buttons whose widths this file chooses — so the two
# things that could quietly stop being true (that it wraps at all, and that it
# wraps EVENLY) are each shown against the arrangement they replaced.
# --------------------------------------------------------------------------

def _bar(qapp, widths, balanced):
    from ui.widgets import WrappingButtonRow
    host = QWidget()
    lay = WrappingButtonRow(host, balanced=balanced)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    for i, w in enumerate(widths):
        b = QPushButton(f"b{i}", host)
        b.setMinimumWidth(w)
        b.setMaximumWidth(w)
        lay.addWidget(b)
    return host, lay


def test_balanced_mode_is_what_stops_a_button_being_stranded(qapp):
    """The mutation, and the proof that it lands.

    The six preview buttons measure 97 · 86 · 78 · 83 · 82 · 118 px in English,
    in the order they are laid out. In 500 px of panel greedy packing takes
    five of them and leaves "Check alignment" alone — and every line is
    justified, so that button is drawn 500 px wide. Balanced packing uses the
    same two lines and cuts them 3 + 3.

    Not an English curiosity: measured over every width from each language's
    real window floor upward, greedy strands "Check alignment" on a line of
    its own in ALL THIRTEEN languages.
    """
    widths = [97, 86, 78, 83, 82, 118]
    host_g, greedy = _bar(qapp, widths, balanced=False)
    host_b, even = _bar(qapp, widths, balanced=True)
    try:
        assert [len(ln) for ln in greedy._pack(500)] == [5, 1], (
            "the mutation did not land: greedy packing no longer strands a "
            "button at 500 px, so this test proves nothing about balancing")
        assert [len(ln) for ln in even._pack(500)] == [3, 3]
        # …and it never spends a line it did not have to.
        for w in range(max(widths), sum(widths) + 6 * 5 + 20):
            assert len(even._pack(w)) == len(greedy._pack(w)), (
                f"at {w} px balanced packing uses "
                f"{len(even._pack(w))} lines where greedy uses "
                f"{len(greedy._pack(w))}")
    finally:
        host_g.deleteLater()
        host_b.deleteLater()


def test_balanced_mode_is_off_unless_it_is_asked_for(qapp):
    """Create Chart's preset bar is measured where it stands; it keeps greedy.

    A default that changed under it would change a row three buttons wide in
    thirteen languages, with nothing in this file looking at it.
    """
    from ui.widgets import WrappingButtonRow
    host = QWidget()
    try:
        assert WrappingButtonRow(host)._balanced is False
    finally:
        host.deleteLater()


def test_a_plain_row_would_widen_this_window(qapp):
    """Control — the arrangement this replaced, put back.

    A `QHBoxLayout`'s minimum is the SUM of its buttons. If that is not more
    than the wrapping row's, nothing above is measuring anything.
    """
    widths = [97, 86, 78, 83, 82, 118]
    host = QWidget()
    plain = QHBoxLayout(host)
    plain.setContentsMargins(0, 0, 0, 0)
    plain.setSpacing(6)
    for w in widths:
        b = QPushButton("x", host)
        b.setMinimumWidth(w)
        b.setMaximumWidth(w)
        plain.addWidget(b)
    host_b, even = _bar(qapp, widths, balanced=True)
    try:
        assert plain.minimumSize().width() > even.minimumSize().width() * 3, (
            f"a plain row asks for {plain.minimumSize().width()} px and the "
            f"wrapping row for {even.minimumSize().width()} — the difference "
            f"this change is built on has gone")
    finally:
        host.deleteLater()
        host_b.deleteLater()
