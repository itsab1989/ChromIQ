"""A browse button that does nothing must say so, in the Neutral appearance.

THE FAULT, AND WHY IT SURVIVED A WHOLE THEME. QSS ranks an id selector above a
pseudo-class one: `QPushButton#browse` is specificity 0-1-0-1 and
`QPushButton:disabled` is 0-0-1-1. So the sheet's generic disabled rule never
reached a browse button — it kept the enabled fill, the enabled `BORDER` edge
and TEXT_MAIN while it was dead. The only thing that moved was the icon, which
Qt greys by itself to `#696969`; that is 4.61:1 on this theme's ground, a
perfectly readable ink and not a disabled one.

`ParameterWidget.set_enabled` disables the row's label, its field AND its
browse button together (ui/parameter_widget.py). With the label and the field
greyed and the button unchanged, the button beside them was the one control in
a locked row that still looked alive.

Rule 3 of the Neutral handoff is the one being kept here: *enabled controls
carry a fill and a solid 1px edge; disabled controls lose the fill and their
edge drops to DISABLED. Low contrast means "disabled" and nothing else.*

Measured, not asserted from the sheet alone: the two buttons are built for
real, carrying the real stylesheet, and their painted edge is read off the
pixels.
"""
from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from ui import neutral_styles as nm

BROWSE_IDS = ("browse", "browse_compact")


def _edge_colour(btn: QPushButton) -> str:
    """The colour of the button's own 1px edge, read from its grab.

    Taken at the vertical middle of the leftmost painted column, which is the
    border whichever radius the rule asks for.
    """
    img = btn.grab().toImage()
    y = img.height() // 2
    for x in range(img.width()):
        c = QColor(img.pixel(x, y))
        if c.alpha() >= 8:
            return c.name()
    raise AssertionError("nothing painted")


@pytest.fixture
def styled(qapp):
    """One host widget wearing the Neutral sheet, put back afterwards.

    The sheet goes on the HOST, never on the application: an app-wide
    stylesheet re-polishes every widget the suite has alive and costs the run
    half a minute (see CLAUDE.md).
    """
    host = QWidget()
    host.setStyleSheet(nm.NEUTRAL_STYLESHEET)
    host.setAutoFillBackground(True)
    QVBoxLayout(host)
    host.resize(200, 60)
    host.show()
    qapp.processEvents()
    yield host
    host.hide()
    host.deleteLater()


@pytest.mark.parametrize("object_name", BROWSE_IDS)
def test_a_disabled_browse_button_drops_its_edge_to_disabled(styled, qapp,
                                                             object_name):
    btn = QPushButton("...", styled)
    btn.setObjectName(object_name)
    styled.layout().addWidget(btn)
    qapp.processEvents()

    live = _edge_colour(btn)
    assert live == nm.NM_BORDER, (
        f"an enabled #{object_name} should carry the ordinary BORDER edge, "
        f"got {live}")

    btn.setEnabled(False)
    qapp.processEvents()
    dead = _edge_colour(btn)
    assert dead == nm.NM_DISABLED, (
        f"a disabled #{object_name} still paints {dead}; rule 3 wants the edge "
        f"to drop to DISABLED ({nm.NM_DISABLED}). An id selector outranks "
        f":disabled, so the rule has to name #{object_name} itself.")
    assert dead != live


@pytest.mark.parametrize("object_name", BROWSE_IDS)
def test_the_disabled_rule_is_solid_and_carries_no_hue(object_name):
    """The owner removed the dashed edge on 2026-09-02. It must not come back."""
    i = nm.NEUTRAL_STYLESHEET.index(f"QPushButton#{object_name}:disabled")
    # the block this selector opens, up to its closing brace
    block = nm.NEUTRAL_STYLESHEET[i:].split("}", 1)[0]
    assert "dashed" not in block and "dotted" not in block
    assert "solid" in block
    for hexval in (nm.NM_DISABLED,):
        assert hexval in block
