"""A help card is as wide as the text written into it.

Knut, beta.144: *"Help text for 'Patch consistency threshold' uses only three
quarters of the window width. Fix it."*

Help bodies are hand-wrapped in the source, so each one has a width its author
chose. Nothing carried that width to the window: `_InfoDialog` could only ever
be as wide as the `min_width` its caller passed, so every card was either too
narrow (each written line re-wrapped, stranding single words) or too wide (a
strip of empty frame beside the text). The fix asks the body for a minimum
width and lets `adjustSize()` work out the frame.

These render the real dialog and measure it, because that gap is invisible to
any test that reads the source: the strings were always correct.
"""
from __future__ import annotations

import inspect
import re

import pytest
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QLabel

from ui.tooltip_button import _InfoDialog


def _body_label(dlg: _InfoDialog) -> QLabel:
    """The dialog's body label — the one inside the scroll area."""
    scroll = dlg.findChildren(type(dlg.findChildren(QLabel)[0].parentWidget()))
    labels = dlg.findChildren(QLabel)
    # The heading is added first, the body second; take the body.
    return labels[1] if len(labels) > 1 else labels[0]


def _widest_written_line(label: QLabel, body: str) -> int:
    fm = QFontMetrics(label.font())
    return max(fm.horizontalAdvance(ln) for ln in body.split("\n") if ln.strip())


HAND_WRAPPED = (
    "How much colour variation ChromIQ accepts WITHIN a\n"
    "single patch.\n\n"
    "Reading a strip, your instrument does not take one reading\n"
    "per patch — it takes many as it slides along, then divides\n"
    "them up. It can then compare the readings that belong to the\n"
    "same patch. On an evenly printed patch they agree closely.\n"
)

FREE_FLOWING = (
    "One paragraph that was never wrapped by hand and simply runs on and on "
    "until the label wraps it, which is exactly what it is meant to do, and "
    "which is why measuring its longest line would be meaningless."
)


def test_a_hand_wrapped_body_is_not_re_wrapped(qapp):
    """Every line the author wrote fits on one line on screen."""
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # re-wrap check pivots on real text widths
    dlg = _InfoDialog("Title", HAND_WRAPPED, None, 420)
    dlg.show()
    qapp.processEvents()
    label = _body_label(dlg)
    widest = _widest_written_line(label, HAND_WRAPPED)
    assert label.width() >= widest, (
        f"the body has {label.width()} px for a {widest} px line — it re-wraps"
    )
    dlg.close()


def test_a_hand_wrapped_body_leaves_no_strip_of_empty_frame(qapp):
    """The reported fault. The text must reach across the card, not three
    quarters of it."""
    dlg = _InfoDialog("Title", HAND_WRAPPED, None, 420)
    dlg.show()
    qapp.processEvents()
    label = _body_label(dlg)
    widest = _widest_written_line(label, HAND_WRAPPED)
    assert widest / label.width() > 0.9, (
        f"the text uses {widest / label.width():.0%} of the body width — the "
        f"rest is empty frame"
    )
    dlg.close()


def test_free_flowing_prose_keeps_the_width_its_caller_asked_for(qapp):
    """A body that was never hand-wrapped must not stretch the card.

    Its "longest line" is the whole paragraph, so measuring it would push every
    such card to the maximum width.
    """
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # width check pivots on real text widths
    dlg = _InfoDialog("Title", FREE_FLOWING, None, 420)
    dlg.show()
    qapp.processEvents()
    assert dlg.width() == 420
    dlg.close()


def test_an_absurdly_wide_body_is_left_alone(qapp):
    """The cap: past a readable line length the body was not hand-wrapped for
    a help card, so no width is asked for and the card is left as Qt sizes it.

    (Qt gives a wrapping label a minimum of its own, which is why this asserts
    "nothing was requested" rather than an exact number — the request is the
    only part this code owns.)
    """
    line = "wrap me " * 40          # real words, so the label CAN wrap them
    body = "\n".join([line, line])
    label = QLabel(body)
    assert _InfoDialog._hand_wrapped_width(label, body) == 0

    dlg = _InfoDialog("Title", body, None, 420)
    dlg.show()
    qapp.processEvents()
    assert dlg.width() < _InfoDialog._MAX_MEASURED_BODY_PX, (
        "an unwrapped body was stretched toward the maximum card width"
    )
    dlg.close()


def test_the_real_patch_consistency_card(qapp):
    """The card Knut named, with its real text, in both copies of it.

    Guided and Manual carry the same body; if they ever drift apart, the one
    that is not tested is the one that will show the gap.
    """
    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure)
    bodies = re.findall(
        r'tooltip_title=tr\("Patch consistency tolerance \(-T\)"\),\s*'
        r'tooltip_body=\(\s*(tr\(.*?\))\s*\),', src, re.S)
    # ONE copy since #160, and that is the point: Guided and Manual are built
    # from a single option table, so the drift this test was written to catch
    # cannot happen any more. Two is still accepted so the test keeps working if
    # a second definition is ever added deliberately — what it must never be is
    # zero, which would mean the card had been lost altogether.
    assert 1 <= len(bodies) <= 2, (
        f"expected the -T help card (one definition since #160, two before), "
        f"found {len(bodies)}"
    )
    # The drift check above is platform-independent; the width measurement below
    # needs real glyph advances, absent under offscreen Qt on Windows.
    from _fontcheck import skip_without_fonts
    skip_without_fonts()
    for raw in bodies:
        body = eval(raw, {"tr": lambda s: s})       # noqa: S307 — a literal
        dlg = _InfoDialog("Patch consistency tolerance (-T)", body, None, 420)
        dlg.show()
        qapp.processEvents()
        label = _body_label(dlg)
        widest = _widest_written_line(label, body)
        assert label.width() >= widest, "the -T card still re-wraps its text"
        assert widest / label.width() > 0.9, (
            f"the -T card uses {widest / label.width():.0%} of its body width"
        )
        dlg.close()


def test_no_hand_picked_widths_are_left_on_the_minus_T_option():
    """The hand-picked 560 px was the workaround; measuring replaced it.

    Left in place it would win over the measurement (`min_width` is a floor)
    and put the gap straight back.
    """
    from ui.tabs import tab_measure

    src = inspect.getsource(tab_measure)
    for m in re.finditer(r'key="tolerance".*?\)\)', src, re.S):
        assert "tooltip_width" not in m.group(0), (
            "the -T option still pins its help-card width by hand"
        )
