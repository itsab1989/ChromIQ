"""#130 (Sebastian, 2026-07-29): buttons must not sit on top of one another.

His report, from the screenshots of the on-screen run: *"it looks like the
buttons in the print chart tab are overlapping and wider than they would have to
be for the text they contain. The same seems true for the measure tabs 'start
measurement' button. Its right side seems to be below the stop button because
they are wider than they would have to be for the text to fit inside."*

Both halves were true and both were measurable. Print Chart overlapped in three
places — by 47, 32 and 11 px — and Measure by 6 px, at 1280x800, 1400x900 and
1680x1050 alike.

**The cause was the sizing, not the layout.** The style asks for about 87 px of
chrome around a label; four such buttons wanted 675 px in a panel 580 px wide.
Because the button's MINIMUM width had been set to that full decorative figure,
the row could not compress — and a QHBoxLayout given less room than the sum of
its minimums lets its items overlap rather than shrink below them.

So the minimum is now what the label genuinely needs (widest line, widest
candidate font, plus enough chrome to frame it) while the style's roomier figure
remains the *preferred* width. Wide panels look as they did; cramped ones tighten
instead of stacking.

**Why the earlier on-screen check missed it:** it asked "is each button wide
enough for its text?" — which they all were. Overlap is a different question and
nobody had asked it. These tests ask it.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtGui import QFont, QFontMetrics                  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QHBoxLayout,      # noqa: E402
                             QPushButton, QWidget)

from ui.widgets import ButtonFontFilter, fit_button_width    # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _needed(btn: QPushButton) -> int:
    """The widest LINE, in the font the button paints — the same rule the
    fitter uses. Measuring a two-line label end to end asks for the width of
    "SAVE ASDEFAULTS" and calls a good button clipped."""
    text = btn.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&")
    if btn.font().capitalization() == QFont.Capitalization.AllUppercase:
        text = text.upper()
    fm = QFontMetrics(btn.font())
    return max(fm.horizontalAdvance(line) for line in text.split("\n"))


def _row(qapp, labels, width):
    """His Print Chart row, reduced to its essentials: several fitted buttons in
    one QHBoxLayout inside a container of a fixed width."""
    host = QWidget()
    lay = QHBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    buttons = []
    for text in labels:
        b = QPushButton(text, host)
        ButtonFontFilter.fit(b)
        lay.addWidget(b)
        buttons.append(b)
    host.resize(width, 60)
    host.show()
    lay.invalidate()
    lay.activate()
    return host, buttons


def _overlaps(buttons):
    out = []
    for i in range(len(buttons)):
        for j in range(i + 1, len(buttons)):
            a, b = buttons[i].geometry(), buttons[j].geometry()
            if a.intersects(b):
                out.append((buttons[i].text(), buttons[j].text(),
                            a.intersected(b).width()))
    return out


# ---- his two rows, at the width that broke them -------------------------
PRINT_ROW = ["Print\nCurrent Page", "Print All\nPages",
             "Clear\nPrint Queue", "Save as\nDefaults"]
MEASURE_ROW = ["Start Measurement", "Stop", "Save as Defaults"]


@pytest.mark.parametrize("labels", [PRINT_ROW, MEASURE_ROW],
                         ids=["print-chart", "measure"])
@pytest.mark.parametrize("width", [580, 520, 460])
def test_a_cramped_row_tightens_instead_of_overlapping(qapp, labels, width):
    host, buttons = _row(qapp, labels, width)
    try:
        assert _overlaps(buttons) == [], (
            f"buttons overlap at {width}px: {_overlaps(buttons)}")
    finally:
        host.close()


@pytest.mark.parametrize("labels", [PRINT_ROW, MEASURE_ROW],
                         ids=["print-chart", "measure"])
@pytest.mark.parametrize("width", [580, 520, 460])
def test_and_the_text_still_fits_when_it_tightens(qapp, labels, width):
    """The invariant the whole clipping saga was about. Compressing a row must
    never be paid for with a clipped label."""
    host, buttons = _row(qapp, labels, width)
    try:
        for b in buttons:
            assert b.minimumWidth() >= _needed(b), \
                f"{b.text()!r} may be squeezed below its own text"
    finally:
        host.close()


def test_the_minimum_is_the_text_plus_chrome_not_the_decorative_width(qapp):
    """The heart of the fix: minimum != preferred. A minimum equal to the
    style's roomy width is what stopped the row compressing."""
    from ui.widgets import _COMFORTABLE_CHROME, _MIN_CHROME
    # Parented, like the real row: a LOOSE button is treated as one that may
    # yet end up in a native alert, and is measured in the system font on
    # purpose. This is the in-window case.
    host = QWidget()
    b = QPushButton("Print\nCurrent Page", host)
    ButtonFontFilter.fit(b)
    slack = b.minimumWidth() - _needed(b)
    assert slack >= _MIN_CHROME, "not enough room to frame the label"
    assert slack <= _COMFORTABLE_CHROME + 2, (
        f"the minimum carries {slack}px of chrome — that is the decorative "
        f"width again, and a row of these cannot compress")


def test_the_stylesheet_rule_carries_the_TEXT_width(qapp):
    """The fault that survived three other corrections, and the reason the row
    still would not fit however the arithmetic above was adjusted.

    A stylesheet ``min-width`` is the minimum of the CONTENT box — Qt adds the
    padding and border on top. Writing the already-padded figure there counted
    ``padding: 6px 18px`` twice, so a button asking for 140 px got a 178 px
    minimum. Four of those do not fit a 580 px panel, and Qt overlapped them.
    """
    import re
    host = QWidget()
    b = QPushButton("Print\nCurrent Page", host)
    ButtonFontFilter.fit(b)
    rule = re.search(r"min-width:\s*(\d+)px", b.styleSheet())
    assert rule, b.styleSheet()
    declared = int(rule.group(1))
    text = _needed(b)
    assert text <= declared <= text + 2, (
        f"the rule declares {declared}px for {text}px of text — anything more "
        f"than a pixel or two of rounding tolerance is padding counted a "
        f"second time")


def test_the_effective_minimum_is_still_enough_for_the_text(qapp):
    """The other side of that coin: after Qt adds the padding back, the button
    must still not be squeezable below its own label."""
    host = QWidget()
    b = QPushButton("Print\nCurrent Page", host)
    host.show()
    try:
        ButtonFontFilter.fit(b)
        assert b.minimumSizeHint().width() >= _needed(b)
    finally:
        host.close()


def test_a_wide_row_still_gets_the_roomy_width(qapp):
    """Nothing changes where there is space: the style's preferred width is
    still what a comfortable panel shows."""
    host, buttons = _row(qapp, PRINT_ROW, 1200)
    try:
        for b in buttons:
            assert b.width() > b.minimumWidth(), \
                f"{b.text()!r} is stuck at its minimum in a wide row"
    finally:
        host.close()


# ---- re-fitting must not pile up stylesheet rules -----------------------
def test_refitting_replaces_its_own_width_rule(qapp):
    """It runs again on every Show and StyleChange. Appending left buttons
    carrying a stack of stale rules — "min-width: 145px" followed by
    "min-width: 149px" — with the last winning by accident of order."""
    b = QPushButton("Print\nCurrent Page")
    for _ in range(5):
        ButtonFontFilter.fit(b)
    assert b.styleSheet().count("min-width") <= 1, b.styleSheet()


def test_refitting_is_stable(qapp):
    """Five fits in a row must land on one width, not creep."""
    b = QPushButton("Start Measurement")
    ButtonFontFilter.fit(b)
    first = b.minimumWidth()
    for _ in range(4):
        ButtonFontFilter.fit(b)
    assert b.minimumWidth() == first


def test_a_deliberate_width_is_still_never_taken_away(qapp):
    """Widening stays one-way: a width somebody set on purpose survives."""
    b = QPushButton("Stop")
    b.setMinimumWidth(400)
    ButtonFontFilter.fit(b)
    assert b.minimumWidth() == 400


def test_widening_asks_the_row_to_place_it_again(qapp):
    """A button that grows after its row was laid out leaves its neighbours
    where they were — so the row has to be told."""
    import inspect
    src = inspect.getsource(ButtonFontFilter.fit)
    assert "relayout_around" in src
    around = inspect.getsource(ButtonFontFilter.relayout_around)
    assert "invalidate()" in around and "activate()" in around


def test_sizing_never_raises(qapp):
    """A window must open even when a button cannot be measured."""
    class _Broken(QPushButton):
        def style(self):
            raise RuntimeError("no style")

    fit_button_width(_Broken("Anything"))       # must not raise
