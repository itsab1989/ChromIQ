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


# ---- the optical nudge (#130, Basti 2026-08-03) --------------------------
def test_the_marks_are_geometrically_identical_which_is_the_whole_point():
    """The reason the nudges exist, and the reason they must not be "fixed".

    All three marks are drawn into the same box and occupy the same rows, so
    anyone measuring them finds them perfectly aligned — and they still did not
    look aligned, because their weight is not evenly spread. This test states
    that so the next reader meets the reasoning before the constants.
    """
    from ui.bar_icons import BarIconButton
    assert BarIconButton.NUDGE == (0.0, 0.0), \
        "the base class stays honest; only the two that need it are nudged"


def test_duplicate_and_delete_carry_the_values_basti_chose():
    from ui.bar_icons import delete_button, duplicate_run_button
    from ui.styles import SPEC_MAGENTA
    assert duplicate_run_button(SPEC_MAGENTA, "d").NUDGE == (7.0, 1.0)
    assert delete_button(SPEC_MAGENTA, "x").NUDGE == (4.0, -2.0)


def test_restore_moves_right_but_not_vertically():
    """It was the vertical reference the other two were judged against, so it
    keeps its baseline — only its distance to its own ⓘ was corrected."""
    from ui.bar_icons import restore_chart_button
    from ui.styles import SPEC_MAGENTA
    assert restore_chart_button(SPEC_MAGENTA, "r").NUDGE == (4.0, 0.0)


def test_the_nudge_moves_the_mark_and_not_the_button(qapp):
    """A layout nudge would have shifted the hit area and every neighbour. This
    one is applied to the glyph inside its own pixmap, so the widget is
    untouched."""
    from ui.bar_icons import BarIconButton, delete_button, duplicate_run_button
    from ui.styles import SPEC_MAGENTA
    for btn in (duplicate_run_button(SPEC_MAGENTA, "d"),
                delete_button(SPEC_MAGENTA, "x")):
        assert btn.size().width() == BarIconButton.HEIGHT
        assert btn.size().height() == BarIconButton.HEIGHT


def test_an_unnudged_tooltip_icon_keeps_its_plain_size(qapp):
    """Every other ⓘ in the app is untouched, and pays nothing for the
    mechanism: no nudge means no growth and the original pixmap."""
    from ui.tooltip_button import TooltipButton
    t = TooltipButton("t", "b")
    assert t._nudge == (0.0, 0.0)
    assert t._grow() == (0, 0)


def test_a_nudged_tooltip_icon_grows_instead_of_clipping(qapp):
    """#130, Basti 2026-08-03: *"the tooltip icons now looked cut off"*.

    The first attempt translated the painter inside a fixed pixmap. The circle
    is drawn with a margin of about 7 % — roughly two physical pixels at 2× —
    so the shift ate its edge. The pixmap now GROWS by twice the nudge and the
    circle is drawn off-centre inside it, so the same visual shift costs
    nothing."""
    from ui.tooltip_button import TooltipButton
    t = TooltipButton("t", "b")
    t.set_nudge(-1.0, 0.0)
    assert t._grow() == (2, 0), "twice the nudge, so the circle always fits"
    assert t.iconSize().width() > t.iconSize().height(), \
        "the extra room is on the axis that moved"


def test_each_tip_travels_with_its_mark(qapp, tmp_path):
    """Each ⓘ moves with the mark it explains, so the gap within each pair is
    unchanged and the cluster shifts as a whole."""
    from PyQt6.QtCore import QSettings
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import (MeasurementTargetBar,
                                           MeasurementTargetController)
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    bar = MeasurementTargetBar(MeasurementTargetController(FileManager(s)))
    assert bar._delete_tip._nudge == (-2.0, 0.0)
    assert bar._restore_tip._nudge == (1.0, 0.0)
    assert bar._duplicate_tip._nudge == (1.0, 0.0)


def test_the_stretch_mechanism_still_works_though_nothing_uses_it(qapp):
    """The one-pixel stretch of the bin was tried and reverted (#130, Basti
    2026-08-03). The mechanism stays, so this checks it still does what it
    claims: anchored on the ink's TOP, so extra height lands at the BOTTOM.

    That anchor is the whole subtlety — scaling about the box origin makes a
    mark taller AND lower, which is what the first attempt did.
    """
    import numpy as np
    from PyQt6.QtGui import QImage
    from ui.bar_icons import BarIconButton, _DeleteButton, _pixmap, draw_trash_can
    from ui.styles import SPEC_MAGENTA

    def ink(stretch, ink_top):
        pm = _pixmap(draw_trash_can, SPEC_MAGENTA, BarIconButton.ICON,
                     _DeleteButton.NUDGE, BarIconButton.HEIGHT, stretch, ink_top)
        img = pm.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        w, h = img.width(), img.height()
        ptr = img.bits(); ptr.setsize(h * img.bytesPerLine())
        a = np.frombuffer(ptr, np.uint8).reshape(
            h, img.bytesPerLine() // 4, 4)[:, :w, :]
        ys = np.nonzero((a[:, :, 3] > 20).any(1))[0]
        return int(ys.min()), int(ys.max())

    t0, b0 = ink(1.0, 0.0)
    t1, b1 = ink(21.5 / 20.5, 3.5)
    assert t1 == t0, "the top must not move — extra height goes on the bottom"
    assert (b1 - t1) - (b0 - t0) == 2, "one device-independent pixel, at 2× dpr"


def test_the_bin_is_not_stretched_now():
    """Reverted at Basti's word."""
    from ui.bar_icons import _DeleteButton
    assert _DeleteButton.STRETCH_Y == 1.0


def test_no_other_mark_is_stretched():
    from ui.bar_icons import BarIconButton
    assert BarIconButton.STRETCH_Y == 1.0


def test_the_cluster_shift_is_layout_not_another_drawn_pixel(qapp):
    """#130, Basti 2026-08-03: another pixel right for all six.

    The duplicate mark had reached the edge of its canvas — one more DRAWN
    pixel would have clipped it, which is the fault he had already caught twice.
    A whole-group move is a layout move by nature, so it is real spacing: no
    canvas, no edge, nothing to lose. The per-mark NUDGE values keep doing what
    they are for — the marks' positions relative to one another.
    """
    import inspect
    from ui.measurement_target_bar import MeasurementTargetBar
    assert MeasurementTargetBar.CLUSTER_SHIFT >= 1
    src = inspect.getsource(MeasurementTargetBar.__init__)
    assert "row.addSpacing(self.CLUSTER_SHIFT)" in src
    i = src.index("row.addSpacing(self.CLUSTER_SHIFT)")
    assert "restore_chart_button" in src[i:i + 400], \
        "the spacing must sit immediately before the first of the three pairs"


def test_the_tooltip_nudge_has_a_ceiling_and_delete_is_at_it(qapp):
    """The grown icon may not exceed the button, or Qt clips it there instead —
    which is the same fault in a different place.

    At −2 the icon is exactly the button's width, so this is as far as an ⓘ can
    travel by drawing. Anything further has to be a layout move, like
    CLUSTER_SHIFT.
    """
    from ui.tooltip_button import TooltipButton
    t = TooltipButton("t", "b")
    t.set_nudge(-2.0, 0.0)
    assert t.iconSize().width() == t.width(), \
        "−2 is the ceiling: the icon exactly fills the button"
    t.set_nudge(-3.0, 0.0)
    assert t.iconSize().width() > t.width(), \
        "…and beyond it the widget would do the clipping"
