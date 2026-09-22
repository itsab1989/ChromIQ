"""`OptionPairRow` puts four widgets where it says it does.

**THIS FILE EXISTS BECAUSE AN ADVERSARY ROUND FOUND THE WIDGET HAD NO TESTS AT
ALL.** `ui/option_pair_row.py` replaced a `QHBoxLayout` in Create Chart, Guided,
so that a row of two options could stop demanding the sum of both widths and
stop pushing the panel's help buttons off the edge. The guard written with it
asks only for `minimumSizeHint`, and the round proved what that leaves open:
moving a button 24 px to the right inside `_put()` clipped two help buttons on
screen while the whole suite stayed green. The width question was guarded; the
PLACEMENT question, which is the other 100 lines of the class, was not.

The class also carries two faults that shipped for about an hour and were found
by measuring the real window, and each has a test below so they cannot come
back:

* `minimumSizeHint()` answered with `heightForWidth(its own minimum width)`,
  which is the STACKED height, for a row that is laid out on ONE line. A
  `QVBoxLayout` applies that as the row's floor whatever width it really gets:
  measured on screen in English, the Chart Size group's minimum height went
  94 -> 122 px, the panel 555 -> 567 and its scroll range 239 -> 251.
* hiding both options left the row visible with a zero size hint, and a
  `QVBoxLayout` still charges `spacing()` for a visible zero-height item. On
  every instrument that hides both (ColorMunki, SpectroScan, CR30, and
  ColorMunki in triple density) the group stood 66 -> 72 px and an empty band
  appeared under "Number of pages".

Geometry is asked of the widget after a real `resize()`, because `_place()` runs
from `resizeEvent`. No window is opened: these are arithmetic questions about
four rectangles, and the on-screen behaviour they stand for is measured by
`scripts/drive_panel_overflow_per_language.py`.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QCheckBox, QWidget

from ui.option_pair_row import BUTTON_GAP, OptionPairRow
from ui.tooltip_button import TooltipButton

SPACING = 6


@pytest.fixture()
def row(qapp):
    """A real row with real widgets, parented to a host that owns them."""
    host = QWidget()
    left = QCheckBox("Suppress left clip border (-L)", host)
    left_button = TooltipButton("Suppress Left Clip Border (-L)", "why", host)
    right = QCheckBox("Don't limit strip length (-P)", host)
    right_button = TooltipButton("Don't Limit Strip Length (-P)", "why", host)
    r = OptionPairRow(left, left_button, right, right_button, host,
                      spacing=SPACING)
    host.show()
    yield r
    host.hide()
    host.deleteLater()


def _half_width_according_to_qt(option, button) -> int:
    """What ONE (option, button) half costs, measured by Qt and not by us.

    A test that recomputes the widget's own arithmetic agrees with the widget
    whatever the widget does, which is how a fixture comes to certify the bug
    it was written to catch. So the oracle here is a real `QHBoxLayout` laid
    out exactly as the row this class replaced: the option, the ten pixels it
    spelled as `addSpacing(10)`, the button, and the layout's own spacing
    between each pair. Qt answers with the minimum, and Qt is the authority on
    what a widget costs.
    """
    from PyQt6.QtWidgets import QHBoxLayout
    host = QWidget()
    lay = QHBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(SPACING)
    lay.addWidget(option)
    lay.addSpacing(BUTTON_GAP)
    lay.addWidget(button)
    lay.activate()
    width = lay.minimumSize().width()
    # Hand the widgets back before the host dies, or they die with it.
    for w in (option, button):
        w.setParent(None)
    host.deleteLater()
    return width


def test_a_line_that_fits_puts_the_second_button_flush_to_the_right_edge(row):
    """The alignment the replaced layout existed to produce.

    Every other help button in that panel ends at the panel's right edge, and
    the comment on the old `addStretch()` said in so many words that this one
    lines up under the button in the row above. Measured on screen, all six sat
    at 526 before the change and all six sit at 526 after it.

    MUTATION: in `_put()`, place the button at `x_right - bs.width() + 24` and
    this goes red. That mutation clipped two help buttons on a real screen with
    the rest of the suite green.
    """
    row.resize(600, row.heightForWidth(600))
    assert row.width() >= row.sizeHint().width(), "this case must be the wide one"
    button = row._right_button
    assert button.x() + button.width() == row.width(), (
        f"the right-hand help button ends at {button.x() + button.width()} and "
        f"the row is {row.width()} wide, so it no longer lines up with the "
        f"column of help buttons down the rest of the panel"
    )


#: The gap between an option and its own help button, AS THE REPLACED LAYOUT
#: PAINTED IT. Measured at a083c6d6 in a real window, English: the -L option
#: ends at x=212 and its button starts at x=228. A `QHBoxLayout` puts its own
#: `spacing()` between every pair of items on top of an explicit
#: `addSpacing(10)`, which is where the other 6 px come from.
#:
#: WRITTEN AS THE MEASURED NUMBER AND NOT AS `BUTTON_GAP + SPACING`. Spelling
#: it with the module's own constants made this test read the value it is
#: meant to be checking: setting `BUTTON_GAP = 0` moved both widgets on screen
#: and the test happily agreed with the new number.
_MEASURED_GAP = 16


def test_a_line_that_fits_keeps_the_gap_the_old_layout_really_painted(row):
    """16 px, not the 10 the replaced row spelled.

    Using 10 moved two widgets six pixels while the outer edges still looked
    right, which is exactly the kind of change nobody sees in a screenshot.

    MUTATION: set `BUTTON_GAP = 0` in `ui/option_pair_row.py` and this goes
    red.
    """
    row.resize(600, row.heightForWidth(600))
    gap = row._left_button.x() - (row._left.x() + row._left.width())
    assert gap == _MEASURED_GAP, (
        f"the gap between the first option and its help button is {gap} px; "
        f"the layout this replaced painted {_MEASURED_GAP}"
    )


def test_the_two_halves_never_touch_on_a_line_that_fits(row):
    """The row wraps while a gap is still visible, not once they collide.

    `_one_line_width()` is the threshold that decides between one line and two,
    and it is the OWNING LAYOUT'S OWN SPACING that separates the halves at that
    threshold. Take it to zero and the row keeps both options on one line right
    up to the point where the first option's help button touches the second
    option's text, which reads as a single run-on control.

    Asked at exactly the narrowest width the row still calls a line, because
    that is where the margin is smallest and where a zero spread shows.

    MUTATION: return `lw + 0 + rw` from `_one_line_width()` and this goes red.
    """
    one_line = row.sizeHint().width()
    row.resize(one_line, row.heightForWidth(one_line))
    assert row._right.y() == row._left.y(), (
        "this case must be the single-line one, and the row stacked instead"
    )
    gap = row._right.x() - (row._left_button.x() + row._left_button.width())
    assert gap >= SPACING, (
        f"at its narrowest single line the row leaves {gap} px between the "
        f"first option's help button and the second option, and the panel's "
        f"own rhythm is {SPACING}. Below that the two halves read as one "
        f"control."
    )


def test_a_line_too_narrow_stacks_without_overlapping(row):
    """Two lines, both buttons flush right, and nothing on top of anything."""
    narrow = row.sizeHint().width() - 40
    row.resize(narrow, row.heightForWidth(narrow))

    left, lb = row._left, row._left_button
    right, rb = row._right, row._right_button
    assert right.y() >= left.y() + left.height(), (
        "the second option is not below the first: it is at y="
        f"{right.y()} and the first ends at y={left.y() + left.height()}"
    )
    for name, b in (("first", lb), ("second", rb)):
        assert b.x() + b.width() == row.width(), (
            f"the {name} help button ends at {b.x() + b.width()} in a row "
            f"{row.width()} wide, so it is out of the panel's button column"
        )
    bottom = max(right.y() + right.height(), rb.y() + rb.height())
    assert bottom <= row.height(), (
        f"the second line ends at y={bottom} in a row only {row.height()} px "
        f"tall, so it is cut off"
    )


def test_the_minimum_width_is_the_wider_half_and_not_the_sum(row):
    """THE WHOLE POINT OF THE CLASS.

    The `QHBoxLayout` this replaced had a minimum equal to the SUM of its
    items, 527 px, which the pane could not give it: measured on screen in
    Ukrainian the panel wanted 569 px inside a 540 px viewport and five of six
    help buttons were sliced in half.

    MUTATION: return `QSize(lw + rw, ...)` from `minimumSizeHint` and this goes
    red, naming both numbers.
    """
    got = row.minimumSizeHint().width()
    # Measured before the halves are borrowed by the oracle.
    half_left = _half_width_according_to_qt(row._left, row._left_button)
    half_right = _half_width_according_to_qt(row._right, row._right_button)
    assert got == max(half_left, half_right), (
        f"the row's minimum width is {got}; the wider of its two halves costs "
        f"{max(half_left, half_right)} by Qt's own reckoning and their sum is "
        f"{half_left + half_right}. A minimum equal to the sum is the fault "
        f"this class was written to remove."
    )


def test_the_minimum_height_is_one_line_not_the_stacked_two(row):
    """A floor of 50 px for a row that is 22 px tall cost the panel 12 px.

    `minimumSizeHint().height()` used to be `heightForWidth(minimum width)`,
    and at the minimum width the halves cannot share a line, so it answered
    with the stacked height. `QVBoxLayout` then applied it as the floor at any
    width. `heightForWidth` is what asks for the second line when the width
    really is too small, and it is tested above.

    MUTATION: return `heightForWidth(max(lw, rw))` as the height and this goes
    red.
    """
    wide = row.sizeHint().width() + 60
    row.resize(wide, row.heightForWidth(wide))
    one_line = row.height()
    assert row.minimumSizeHint().height() == one_line, (
        f"the row's minimum height is {row.minimumSizeHint().height()} while "
        f"laid out on one line {one_line} px tall, so every panel holding it "
        f"reserves the stacked height for a row that is not stacked"
    )


def test_one_hidden_half_leaves_the_other_a_whole_line(row):
    """Both options are hidden together by instrument, but not by this class."""
    row._right.setVisible(False)
    row._right_button.setVisible(False)
    row.relayout()
    row.resize(600, row.heightForWidth(600))

    assert row.isVisible(), "one half is still shown, so the row must stay"
    lb = row._left_button
    assert lb.x() + lb.width() == row.width(), (
        "with only one option left, its help button still belongs in the "
        f"panel's button column; it ends at {lb.x() + lb.width()} of "
        f"{row.width()}"
    )


def test_hiding_both_halves_takes_the_ROW_away_too(row):
    """Otherwise a `QVBoxLayout` charges its spacing for an empty row.

    Every instrument that reads patches individually or on a flatbed hides
    both of these options, and so does triple density. Measured on screen on
    ColorMunki, SpectroScan and CR30: with the row merely emptied, the Chart
    Size group stood 66 -> 72 px and an empty band appeared under "Number of
    pages".

    MUTATION: drop the `setVisible(lv or rv)` line from `relayout()` and this
    goes red.
    """
    for w in (row._left, row._left_button, row._right, row._right_button):
        w.setVisible(False)
    row.relayout()
    assert not row.isVisible(), (
        "both options are hidden and the row is still visible, so the layout "
        "above it still pays its spacing for a row with nothing in it"
    )
    assert row.minimumSizeHint().width() == 0
    assert row.heightForWidth(600) == 0
