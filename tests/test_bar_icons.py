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


def test_the_arrow_is_counter_clockwise(qapp):
    """Rule 2, first half. He specified a counter-clockwise arc, and Qt's
    positive sweep is counter-clockwise on screen.

    Checked by walking the path rather than by matching the call: the head
    gained keyword arguments in beta.151 and a string match would have failed
    on a change that moved nothing.
    """
    rect = QRectF(3.4, 3.4, 17.2, 17.2)
    arc, _wings = bi._ccw_arrow(rect, 200, 250)
    pts = [arc.pointAtPercent(t / 20.0) for t in range(21)]
    cx, cy = rect.center().x(), rect.center().y()
    angles = [math.degrees(math.atan2(-(q.y() - cy), q.x() - cx)) for q in pts]
    steps = [(b - a + 540) % 360 - 180 for a, b in zip(angles, angles[1:])]
    assert all(s > 0 for s in steps), \
        "the arc's sweep changed — it is no longer counter-clockwise on screen"
    assert abs(sum(steps) - 250) < 2, f"the arc spans {sum(steps):.0f}°, not 250°"


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


def test_the_sheet_is_whole():
    """Rule 4, as Basti settled it by drawing it (2026-08-06).

    The sheet used to have a gap cut out of it wherever the arc came near — a
    clearance band, not an overlap; the two shapes never actually touch. He
    took it out: *"some of the edges of the sheet in the middle were cut off.
    so i made three new copies of it and rotated each 90 degrees more so all of
    the edges were fixed."* At 24 px those notches read as damage to the sheet
    rather than as depth.

    The half of the old rule that still holds is the half about colour: a gap
    painted in a background colour is right on one theme and wrong on the
    other, so nothing here may name one.
    """
    src = inspect.getsource(bi.draw_restore_chart)
    assert "setClipPath" not in src, \
        "the sheet is being cut into again — Basti removed that by hand"
    for wrong in ("#141414", "#f4f2ee", "white", "black"):
        assert wrong not in src, "a background colour is being painted into the mark"


def test_the_head_sits_forward_of_the_arc_so_the_join_reads_as_one_arrow(qapp):
    """With the wings springing from the arc's last point, the arc's round cap
    stands proud of the notch between them and the join reads as a step. Basti
    moved the head forward along the tangent to close it (2026-08-06).

    Measured, not asserted from a constant: the arc's end must fall INSIDE the
    triangle the head encloses.
    """
    rect = QRectF(3.4, 3.4, 17.2, 17.2)
    arc, wings = bi._ccw_arrow(rect, 200, 250,
                               advance=bi._RESTORE_HEAD_ADVANCE,
                               turns=bi._RESTORE_HEAD_TURNS,
                               lengths=bi._RESTORE_HEAD_LENGTHS)
    end = arc.pointAtPercent(1.0)
    tip = wings[0][0]
    a, b = wings[0][1], wings[1][1]

    def side(p, q, r):
        return ((q.x() - p.x()) * (r.y() - p.y())
                - (q.y() - p.y()) * (r.x() - p.x()))

    signs = [side(tip, a, end), side(a, b, end), side(b, tip, end)]
    assert all(s > 0 for s in signs) or all(s < 0 for s in signs), (
        "the arc's end is outside the arrowhead, so its cap sticks out of the "
        "notch — the step Basti drew out"
    )


# ---- the bar wires them up and re-tints them ----------------------------
def test_both_buttons_carry_their_mark():
    """The marks are no longer an icon set ON a labelled button — since
    beta.102 each mark IS its button (Knut, #130 2026-07-29), so what has to be
    wired up is the button's accent, not an icon."""
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar.set_accent)
    assert "self._restore_btn.set_accent(color)" in src
    assert "self._delete_btn.set_accent(color)" in src


def test_the_marks_are_re_tinted_with_everything_else():
    """They live in set_accent, beside the ⓘ tinting, so a new mark on this bar
    cannot be forgotten the way the Restore and Delete ⓘ both were."""
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar.set_accent)
    assert src.index("tip.set_color(color)") < src.index("_restore_btn.set_accent")


def test_the_icons_have_a_size_so_the_button_reserves_room():
    """Set by the button itself now, once, rather than at each call site. The
    mark grew to 27 px when Knut saw 18 px on screen and asked for about half
    again (#130, 2026-07-29); the button's square follows it."""
    assert bi.BarIconButton.ICON == 27
    assert bi.BarIconButton.HEIGHT > bi.BarIconButton.ICON, \
        "the mark would be clipped by its own button"
    # The ICON is the size of the MARK; the icon pixmap handed to Qt is the
    # button's full square, so a nudged mark has room to move without losing
    # its edge (#130, Basti 2026-08-03 — at right 6 the duplicate mark had
    # already lost five pixels of width).
    assert "setIconSize(QSize(self.HEIGHT, self.HEIGHT))" in inspect.getsource(
        bi.BarIconButton.__init__)


def test_the_head_is_deliberately_not_symmetric():
    """The wings are an unequal pair, and that is the point.

    Basti distorted the head by hand, was shown the symmetric reading of it
    beside the distorted one, and chose the distorted one (2026-08-06). There
    is no rule to derive these four numbers from, so the only thing standing
    between them and a well-meaning "surely this should be ±155°" is this test.
    """
    turn_a, turn_b = bi._RESTORE_HEAD_TURNS
    len_a, len_b = bi._RESTORE_HEAD_LENGTHS
    assert abs(turn_a) != abs(turn_b), "the wings have been made a mirror pair"
    assert len_a != len_b, "the wings have been made the same length"
    # …and it leans the way he drew it: the upper wing flatter and shorter.
    assert abs(turn_a) > abs(turn_b)
    assert len_a < len_b


def test_the_head_and_the_arc_are_drawn_at_one_weight():
    """The mark has a single stroke weight and the head is not an exception.

    The fit to his artwork wanted 1.84 for the wings against the arc's 1.9 —
    a by-product of the transform that scaled the head, and 3% thinner would
    read as a lighter arrowhead on a heavier curve for no gain anyone asked
    for. One number, one weight.
    """
    src = inspect.getsource(bi.draw_restore_chart)
    assert src.count("_pen(p, colour, 1.9)") == 1
    assert "1.84" not in src
