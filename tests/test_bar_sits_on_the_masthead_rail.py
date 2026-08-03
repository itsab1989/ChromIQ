"""#130 (Basti, 2026-08-03): the profile bar was a pale block on the rail.

    *"In dark mode only: in the bar the text for 'location being edited',
    'Profile run', 'Run type' and 'Load a profile project…' is put on a lighter
    background than the rest of the bar. Give it the same dark background as
    the rest. In Light mode this looks correct — everything has the same
    color."*

The bar is hosted **on** the masthead's version rail, which the masthead paints
itself with ``_PALETTE_DARK["ver_bg"]`` = ``#070707``. The dark stylesheet's
app-wide ``QWidget`` rule then painted ``BG_PANEL`` (``#181818``) over it — three
shades lighter — so the hosted widget showed as a rectangle across the rail.

**Light mode never had the fault, and that is the tell**: ``LIGHT_STYLESHEET``'s
``QWidget`` rule sets colour and font but *no background at all*, so the bar was
already transparent there and the masthead's own paint showed through. The fix
makes dark behave the same way rather than inventing a colour to match.
"""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.light_styles import LIGHT_STYLESHEET      # noqa: E402
from ui.styles import APP_STYLESHEET              # noqa: E402


def test_the_bar_identifies_itself(qapp):
    """A rule cannot reach it without a name."""
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import (MeasurementTargetBar,
                                           MeasurementTargetController)
    bar = MeasurementTargetBar(MeasurementTargetController(
        FileManager(AppSettings())))
    assert bar.objectName() == "target_bar"


def test_dark_keeps_its_background_off_the_bar():
    assert "QWidget#target_bar" in APP_STYLESHEET
    i = APP_STYLESHEET.index("QWidget#target_bar")
    rule = APP_STYLESHEET[i:i + 160]
    assert "background: transparent" in rule


def test_the_rule_covers_the_labels_too():
    """The labels are what actually showed the block — the bar itself is mostly
    covered by its own children."""
    i = APP_STYLESHEET.index("QWidget#target_bar")
    assert "QLabel" in APP_STYLESHEET[i:i + 160]


def test_light_mode_has_no_widget_background_to_remove():
    """The invariant that made light mode correct all along. If a background
    is ever added to LIGHT_STYLESHEET's QWidget rule, light gains the same
    fault and this test is where it should be noticed."""
    # LIGHT_STYLESHEET is the FORMATTED string, so the braces are single —
    # the doubled ones only exist in the template source.
    m = re.search(r"(?m)^QWidget \{(.*?)\}", LIGHT_STYLESHEET, re.S)
    assert m, "the QWidget rule moved; check whether it now sets a background"
    assert "background" not in m.group(1)


def test_the_masthead_rail_is_darker_than_the_panel_colour():
    """Why the block was visible at all — and why matching BG_PANEL to the rail
    would have been the wrong fix (it would have lightened the whole app)."""
    from ui.masthead_header import _PALETTE_DARK
    from ui.styles import BG_PANEL

    def grey(h):
        return int(h.lstrip("#")[0:2], 16)

    assert grey(_PALETTE_DARK["ver_bg"]) < grey(BG_PANEL)
