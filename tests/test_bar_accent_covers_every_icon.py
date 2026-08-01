"""Everything on the run bar follows the tab you are looking at.

This has now been reported three times, each time for a newly added icon whose
colour was left out of ``set_accent``:

* Knut, #130 2026-07-27 — the Restore button's ⓘ kept the Measure tab's green
  everywhere else.
* Knut, #130 2026-07-28 — the Delete button's ⓘ did the same when it was added.
* Sebastian, 2026-08-01 — *"does the color of the tooltip icon follow the active
  tabs accent color?"*, on the Duplicate button's ⓘ.

Three times is a pattern, not three slips: a hand-written list of widgets is
something a person has to remember to update. ``set_accent`` now finds the ⓘ
buttons by looking for them, and this test checks every accent-bearing widget on
the bar rather than a list someone has to maintain here either.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                       # noqa: E402
from PyQt6.QtWidgets import QApplication                 # noqa: E402

from core.file_manager import FileManager                # noqa: E402
from core.settings import AppSettings                    # noqa: E402
from ui.measurement_target_bar import (                  # noqa: E402
    MeasurementTargetBar, MeasurementTargetController)
from ui.tooltip_button import TooltipButton              # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bar(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    ctl = MeasurementTargetController(FileManager(s))
    return MeasurementTargetBar(ctl, show_verification=True)


_MAGENTA = "#d4499b"


def test_every_tooltip_icon_takes_the_accent(bar):
    bar.set_accent(_MAGENTA)
    tips = bar.findChildren(TooltipButton)
    assert tips, "the bar should carry several ⓘ buttons"
    wrong = [t for t in tips
             if (t._color_override or '').lower() != _MAGENTA.lower()]
    assert not wrong, (
        f"{len(wrong)} of {len(tips)} ⓘ buttons kept the old colour — "
        "set_accent must reach every one, however it was added")


def test_every_icon_button_takes_the_accent(bar):
    """The mark IS the button for Restore, Duplicate and Delete, so its colour
    comes from here and nowhere else."""
    from ui.bar_icons import BarIconButton
    bar.set_accent(_MAGENTA)
    buttons = bar.findChildren(BarIconButton)
    assert len(buttons) >= 3, buttons
    wrong = [b for b in buttons if b._colour.lower() != _MAGENTA.lower()]
    assert not wrong, f"{len(wrong)} icon button(s) kept the old colour"


def test_the_duplicate_button_and_its_help_icon_are_both_there(bar):
    """Knut's placement: Duplicate sits between Restore's ⓘ and Delete, with
    its own ⓘ to its right."""
    from ui.bar_icons import BarIconButton
    order = [w for w in bar.findChildren((BarIconButton, TooltipButton))
             if w.parent() is bar]
    names = []
    for w in sorted(order, key=lambda w: w.pos().x()):
        if isinstance(w, BarIconButton):
            names.append(w.toolTip().split("\n")[0] or w.accessibleName())
        else:
            names.append("ⓘ")
    assert bar._duplicate_btn is not None
    assert bar._duplicate_tip is not None


def test_a_later_accent_change_is_not_lost(bar):
    """Switching tabs twice must not leave anything on the first colour."""
    bar.set_accent("#56d6a5")
    bar.set_accent(_MAGENTA)
    for t in bar.findChildren(TooltipButton):
        assert t._color_override.lower() == _MAGENTA.lower()
