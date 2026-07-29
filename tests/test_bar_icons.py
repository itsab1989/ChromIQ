"""#130 (Knut, 2026-07-29): the two drawn marks on the Profile-run bar.

He asked for mockups of a trash can for **Delete** and of something for
**Restore Used Chart**, reviewed four rounds of them, then said *"finish the
images, so we can conclude that issue"* without naming his letters. These are
the two variants recommended in every round — the minimal can, and a sheet of
patches inside a counter-clockwise arc on the undo theme he specified.

The tests below are the four rules those rounds produced, each of which he
caught me breaking at least once.
"""
from __future__ import annotations

import inspect
import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QRectF                       # noqa: E402
from PyQt6.QtGui import QColor, QImage, QPainter      # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402

import ui.bar_icons as bi                             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _render(draw, colour="#ff4573", size=96):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(QColor("#00000000"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24.0, size / 24.0)
    draw(p, colour)
    p.end()
    return img


def _painted(img) -> int:
    return sum(1 for y in range(img.height()) for x in range(img.width())
               if img.pixelColor(x, y).alpha() > 40)


# ---- both icons actually draw something ---------------------------------
@pytest.mark.parametrize("draw", [bi.draw_trash_can, bi.draw_restore_chart],
                         ids=["trash", "restore"])
def test_the_icon_paints(qapp, draw):
    """The Getting Started cards once shipped painting nothing at all because
    they fell through an if/elif chain. Never again without a test."""
    assert _painted(_render(draw)) > 300


@pytest.mark.parametrize("draw", [bi.draw_trash_can, bi.draw_restore_chart],
                         ids=["trash", "restore"])
def test_it_stays_inside_its_box(qapp, draw):
    """A mark that overflows its 24-unit box is clipped by the button."""
    img = _render(draw, size=96)
    edge = [(x, y) for x in range(96) for y in range(96)
            if (x < 2 or y < 2 or x > 93 or y > 93)
            and img.pixelColor(x, y).alpha() > 40]
    assert not edge, f"paints into the margin at {edge[:4]}"


@pytest.mark.parametrize("draw", [bi.draw_trash_can, bi.draw_restore_chart],
                         ids=["trash", "restore"])
@pytest.mark.parametrize("colour", ["#ff4573", "#ffb42d", "#56d6a5",
                                    "#37bcd6", "#9f82ff"])
def test_it_takes_the_tab_accent(qapp, draw, colour):
    """Everything on this bar follows the tab you are looking at."""
    img = _render(draw, colour)
    want = QColor(colour)
    hit = False
    for y in range(0, 96, 3):
        for x in range(0, 96, 3):
            c = img.pixelColor(x, y)
            if c.alpha() > 200 and abs(c.red() - want.red()) < 12 \
               and abs(c.green() - want.green()) < 12 \
               and abs(c.blue() - want.blue()) < 12:
                hit = True
                break
    assert hit, f"nothing painted in {colour}"


# ---- the four rules the review rounds produced --------------------------
def test_curves_are_drawn_with_a_pen():
    """Rule 1. An outline that is then simplified leaves faint flats on a small
    circle — Knut saw them on the clock faces at once."""
    src = inspect.getsource(bi.draw_restore_chart)
    assert "p.drawPath(arc)" in src
    assert "simplified()" not in src


def test_the_arrow_is_counter_clockwise():
    """Rule 2, first half. He specified a counter-clockwise arc, and Qt's
    positive sweep is counter-clockwise on screen."""
    src = inspect.getsource(bi.draw_restore_chart)
    assert "_ccw_arrow(QRectF(3.4, 3.4, 17.2, 17.2), 200, 250)" in src, \
        "the arc's sweep changed — check the direction by hand"


def test_the_head_sits_at_the_end_along_the_tangent(qapp):
    """Rule 2, second half. A head on the START points backwards and makes a
    counter-clockwise arc read as clockwise, which is exactly what he reported.

    Checked numerically: the wings must straddle the tangent at the arc's end.
    """
    rect = QRectF(3.4, 3.4, 17.2, 17.2)
    start, span = 200.0, 250.0
    _arc, wings = bi._ccw_arrow(rect, start, span)

    theta = math.radians(start + span)
    cx, cy = rect.center().x(), rect.center().y()
    r = rect.width() / 2.0
    tip_x, tip_y = cx + r * math.cos(theta), cy - r * math.sin(theta)
    for (a, _b) in wings:
        assert abs(a.x() - tip_x) < 0.01 and abs(a.y() - tip_y) < 0.01, \
            "a wing does not start at the end of the arc"

    # the two wings point BACK along the travel direction, one either side
    vx, vy = -math.sin(theta), -math.cos(theta)
    dots = []
    for (a, b) in wings:
        dx, dy = b.x() - a.x(), b.y() - a.y()
        n = math.hypot(dx, dy)
        dots.append((dx / n) * vx + (dy / n) * vy)
    assert all(d < -0.5 for d in dots), \
        f"the wings point along the travel, not back against it: {dots}"


def test_the_head_is_in_proportion_to_its_arc():
    """Rule 3. A fixed head was nearly as long as the radius on a small circle
    and read as a curl rather than an arrow."""
    small = bi._ccw_arrow(QRectF(0, 0, 9, 9), 90, 250)[1]
    large = bi._ccw_arrow(QRectF(0, 0, 22, 22), 90, 250)[1]

    def length(w):
        (a, b) = w[0]
        return math.hypot(b.x() - a.x(), b.y() - a.y())

    assert length(small) < length(large), "the head does not scale with the arc"


def test_the_sheet_is_clipped_where_the_arc_passes_in_front():
    """Rule 4. A gap painted in a background colour is right on one theme and
    wrong on the other; the hole has to be cut out of the shape."""
    src = inspect.getsource(bi.draw_restore_chart)
    assert "setClipPath(_everything_but(" in src
    for wrong in ("#141414", "#f4f2ee", "white", "black"):
        assert wrong not in src, "a background colour is being painted into the gap"


# ---- the bar wires them up and re-tints them ----------------------------
def test_both_buttons_carry_their_mark():
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar.set_accent)
    assert "restore_chart_icon(color, 16)" in src
    assert "trash_can_icon(color, 16)" in src


def test_the_marks_are_re_tinted_with_everything_else():
    """They live in set_accent, beside the ⓘ tinting, so a new mark on this bar
    cannot be forgotten the way the Restore and Delete ⓘ both were."""
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar.set_accent)
    assert src.index("tip.set_color(color)") < src.index("restore_chart_icon")


def test_the_icons_have_a_size_so_the_button_reserves_room():
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar)
    assert src.count("setIconSize(QSize(16, 16))") >= 2
