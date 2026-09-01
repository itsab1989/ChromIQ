"""The ColorMunki / i1Studio / ColorChecker Studio dial, as a pictogram.

Same house style as `ui/cr30_pictograms.py`, whose `_ink` and `_accent` it
borrows: line art in the theme's own foreground, the Measure tab's green for
the one thing the person must do. It lives in its own module because it is not
a CR30, and the two instruments share nothing but the drawing conventions.

The shape was settled by Basti at the instrument, over a dozen rounds, and
several readings were tried and rejected on the way. What is here is what he
approved:

* the body is a square with ONE very large corner: straight down the left,
  straight along the bottom, a short rise on the right, a quarter circle, and a
  short run back along the top. Not a rounded square, not a quarter disc, and
  NOT concentric with the dial (that was asked for, built, and rejected: it
  puts the join low on the right and dents the outline);
* the dial ring is CLOSED. It was drawn with a wedge cut out of it, which the
  instrument does not have;
* there is no hinged arm across the top;
* the calibration mark is a GEAR, not a sun. At this size the two are nearly
  the same picture, and it was drawn wrong for several rounds. The long-rayed
  sun on the instrument is the AMBIENT position, a different thing;
* the measuring mark is a CROSS INSIDE FOUR CORNER BRACKETS, the registration
  mark, not the four filled squares it resembles at a glance.

The pointer bar rides ON the ring, it does not interrupt it: the ring is drawn
first and whole, the bar over it. Nothing here is a gap in the ring.
"""
import math
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QApplication

from ui.cr30_pictograms import _accent, _ink

def _at(c: QPointF, r: float, clock: float) -> QPointF:
    ang = math.radians(clock * 30.0 - 90.0)
    return QPointF(c.x() + r * math.cos(ang), c.y() + r * math.sin(ang))


def _gear(p, c, r, ink):
    """The calibration mark: a GEAR, not a sun.

    It was drawn as a sun for several rounds, because at this size the two are
    nearly the same picture: a small circle with short strokes around it.
    ChromIQ's own ColorMunki wording has said "the small gear icon" all along
    (`ui/ti2_loader.py`), and the long-rayed sun on the instrument is the
    AMBIENT position at twelve o'clock, a different thing entirely.

    Drawn so it cannot be mistaken for the sun: the teeth are square, they
    touch the body of the gear, and there is a hole in the middle."""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(ink)
    teeth, tw, th = 8, r * 0.30, r * 0.42
    for i in range(teeth):
        a = math.radians(i * 360.0 / teeth)
        p.save()
        p.translate(c.x() + math.cos(a) * r * 0.72,
                    c.y() + math.sin(a) * r * 0.72)
        p.rotate(math.degrees(a))
        p.drawRect(QRectF(-th / 2, -tw / 2, th, tw))
        p.restore()
    p.drawEllipse(c, r * 0.74, r * 0.74)
    # the hole, punched by painting the ground back through it
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(ink, r * 0.30))
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    p.setBrush(ink)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(c, r * 0.30, r * 0.30)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _target_mark(p, c, r, ink):
    """The measuring mark: a CROSS inside four corner brackets.

    Drawn from a close photograph of the instrument (Basti, 2026-09-01). It had
    been four filled squares for several rounds, which is what it looks like at
    a glance and is not what it is: the corners are open brackets framing a
    plus, the registration mark every printer knows. "Target" is the honest
    name for it; ChromIQ's own wording already calls it "the target / aperture
    icon".
    """
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(ink, r * 0.26, cap=Qt.PenCapStyle.FlatCap,
                  join=Qt.PenJoinStyle.MiterJoin))
    box = r * 0.92          # half the distance between opposite brackets
    arm = r * 0.46          # how long each bracket arm is
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x, y = c.x() + sx * box, c.y() + sy * box
        path = QPainterPath()
        path.moveTo(x, y - sy * arm)      # the vertical arm
        path.lineTo(x, y)                 # to the corner
        path.lineTo(x - sx * arm, y)      # and out along the horizontal
        p.drawPath(path)
    # the cross in the middle
    cross = r * 0.62
    p.setPen(QPen(ink, r * 0.26, cap=Qt.PenCapStyle.FlatCap))
    p.drawLine(QPointF(c.x() - cross, c.y()), QPointF(c.x() + cross, c.y()))
    p.drawLine(QPointF(c.x(), c.y() - cross), QPointF(c.x(), c.y() + cross))


def dial(position: str = "calibrate", widget=None, size: int = 260) -> QPixmap:
    """`position` is "calibrate" (the white bar at half past four, pointing at
    the gear mark) or "measure" (the bar at six o'clock, pointing at the target
    mark). The mark being pointed at wears the accent; the other stays ink."""
    dpr = (widget.devicePixelRatioF() if widget is not None
           else (QApplication.instance().devicePixelRatio()
                 if QApplication.instance() else 1.0))
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.GlobalColor.transparent)
    ink, acc = _ink(widget), _accent(widget)

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    w = size
    lw = w * 0.030
    p.setPen(QPen(ink, lw, cap=Qt.PenCapStyle.RoundCap,
                  join=Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)

    # --- THE BODY, in Basti's words and his correction (2026-09-01):
    #
    #   "on the left a straight line down, then from its bottom a line of the
    #    same length 90 degrees to the right, and the ends of those lines
    #    connected by an arc"
    #   "it is not completely an arc ... from both ends it starts straight
    #    before it turns into an arc"
    #
    # So: straight down the left, straight along the bottom, a short straight
    # rise on the right, one big sweeping arc, and a short straight run back
    # along the top. A square with a single very large corner, not a rounded
    # square and not a quarter disc, both of which were drawn and rejected.
    body = QRectF(w * 0.14, w * 0.16, w * 0.72, w * 0.70)
    small = w * 0.055            # the three ordinary corners

    # CONCENTRIC WITH THE DIAL WAS TRIED AND REJECTED (Basti, 2026-09-01):
    # sharing the dial's centre put the join low on the right-hand side and
    # dented the body. A quarter circle of its own is the shape he approved.
    c = QPointF(body.center().x() - w * 0.020,
                body.center().y() - w * 0.030)
    path = QPainterPath()
    path.moveTo(body.left(), body.top() + small)
    path.quadTo(body.left(), body.top(), body.left() + small, body.top())
    big = body.width() * 0.56
    path.lineTo(body.right() - big, body.top())                 # straight, top
    path.arcTo(QRectF(body.right() - big * 2, body.top(),
                      big * 2, big * 2), 90.0, -90.0)           # the big arc
    path.lineTo(body.right(), body.bottom() - small)            # straight, right
    path.quadTo(body.right(), body.bottom(),
                body.right() - small, body.bottom())
    path.lineTo(body.left() + small, body.bottom())             # straight, base
    path.quadTo(body.left(), body.bottom(), body.left(),
                body.bottom() - small)
    path.closeSubpath()
    p.drawPath(path)

    # the small hole by the bottom corner
    p.drawEllipse(QPointF(body.left() + w * 0.078,
                          body.bottom() - w * 0.072), w * 0.024, w * 0.024)
    # --- THE DIAL, and its wedge. The ring is a thick annulus with a piece
    # missing at the lower right; the pointer bar sits in that gap. This is the
    # shape that makes the device recognisable, and the first attempt put it in
    # the body instead.
    clock = 4.5 if position == "calibrate" else 6.0
    r_out, r_in = w * 0.231, w * 0.133
    # A CLOSED RING. It was drawn open at one point, with a wedge cut out
    # where the pointer sits; Basti has the instrument in front of him and the
    # ring is continuous. The pointer bar rides ON it, it does not interrupt it.
    p.drawEllipse(QPointF(c.x(), c.y()), r_out, r_out)
    p.drawEllipse(QPointF(c.x(), c.y()), r_in, r_in)

    # --- the pointer bar, in the gap, pointing outward
    p.setPen(QPen(acc, lw * 2.3, cap=Qt.PenCapStyle.RoundCap))
    p.drawLine(_at(c, r_in + lw * 0.9, clock), _at(c, r_out - lw * 0.5, clock))

    # --- the marks the dial points at
    # A little further out than the ring, so the marks read as sitting ON
    # the silver rather than crowding the dial (Basti, 2026-09-01).
    mark_r = w * 0.300
    _gear(p, _at(c, mark_r, 4.5), w * 0.048,
         acc if position == "calibrate" else ink)
    _target_mark(p, _at(c, mark_r, 6.0), w * 0.043,
                acc if position == "measure" else ink)
    p.end()
    return px
