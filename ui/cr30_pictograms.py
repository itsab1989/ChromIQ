"""Pictograms for the CR30's two calibration windows (#159).

The two steps ask for OPPOSITE things — cap ON with the white tile, then cap OFF
pointing at nothing — and the owner's worry was that two similar-looking windows
would have a user do the same thing twice. He chose the "steps pair" cue: each
window shows BOTH steps with the current one marked, so the difference is
visible rather than remembered.

**There is deliberately no black tile anywhere in these drawings.** The CR30 has
none; its dark reference is open air. A drawing of a black tile would send
someone hunting for an object that does not exist, and the nearest dark thing to
hand is the cap's GREEN face — the exact surface that silently corrupted this
unit's white reference during the research. The second step is drawn as the
instrument nose-down over emptiness, which is what actually happens.

Everything is drawn at runtime from the LIVE palette, so one drawing is correct
in light and dark by construction rather than by shipping two sets of art. That
was the trap the owner identified himself: a black swatch on a dark window is
invisible, and it is the dark step where being unmistakable matters most.
Sizes come from the font metrics, so the art follows the system font size.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFontMetrics, QPainter, QPainterPath, QPen,
                         QPixmap)
from PyQt6.QtWidgets import QWidget

WHITE_STEP = "white"
BLACK_STEP = "black"


def _ink(widget: QWidget | None) -> QColor:
    """The theme's own foreground. Never a hard-coded grey: the whole point is
    that this reads on both grounds."""
    if widget is not None:
        return widget.palette().windowText().color()
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return (app.palette().windowText().color() if app else QColor(0, 0, 0))


#: The Measure tab's accent, both grounds. `#56d6a5` is `ui.styles.SPEC_GREEN`,
#: which that tab uses for its own information boxes; on a pale ground the light
#: theme already darkens it to `#0f7a5a` for the same text, because the bright
#: green does not carry there. Kept as literals rather than imported so a
#: pictogram never drags the whole stylesheet module in behind it.
ACCENT_DARK = "#56d6a5"
ACCENT_LIGHT = "#0f7a5a"


def _accent(widget: QWidget | None) -> QColor:
    """The Measure tab's green, picked for the ground it will be drawn on."""
    ink = _ink(widget)
    # A light ink means a dark ground: the theme's own foreground is the only
    # reliable signal here, and it is the one _ink already trusts.
    return QColor(ACCENT_DARK if ink.lightness() > 127 else ACCENT_LIGHT)


def _draw_instrument(p: QPainter, r: QRectF, ink: QColor, nose_down: bool):
    """A CR30 in outline: a rounded body with the measuring opening marked."""
    pen = QPen(ink, max(1.0, r.width() / 28.0))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    body = QRectF(r.left() + r.width() * 0.22, r.top() + r.height() * 0.06,
                  r.width() * 0.56, r.height() * 0.62)
    p.drawRoundedRect(body, r.width() * 0.10, r.width() * 0.10)
    # the aperture, on the end that faces the surface
    ap = QRectF(0, 0, r.width() * 0.20, r.width() * 0.20)
    ap.moveCenter(QPointF(body.center().x(),
                          body.bottom() if nose_down else body.top()))
    p.drawEllipse(ap)


def _draw_cap(p: QPainter, r: QRectF, ink: QColor, face_white: bool):
    """The magnetic cap, showing WHICH FACE meets the opening — the one spatial
    hazard the window exists to prevent."""
    pen = QPen(ink, max(1.0, r.width() / 28.0))
    p.setPen(pen)
    tile = QRectF(r.left() + r.width() * 0.28, r.top() + r.height() * 0.70,
                  r.width() * 0.44, r.height() * 0.20)
    if face_white:
        # An outlined, unfilled disc reads as "white" on BOTH grounds; a filled
        # white one disappears on a light window.
        p.setBrush(Qt.BrushStyle.NoBrush)
    else:
        hatch = QColor(ink)
        hatch.setAlpha(90)
        p.setBrush(hatch)
    p.drawRoundedRect(tile, r.width() * 0.04, r.width() * 0.04)


def _draw_tick(p: QPainter, r: QRectF, ink: QColor):
    pen = QPen(ink, max(1.5, r.width() / 20.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    path = QPainterPath(QPointF(r.left(), r.center().y()))
    path.lineTo(r.left() + r.width() * 0.36, r.bottom())
    path.lineTo(r.right(), r.top())
    p.drawPath(path)


def _draw_surface(p: QPainter, r: QRectF, ink: QColor):
    """The solid line an instrument is resting ON. The opposite of
    :func:`_draw_nothing`, and drawn at the same height so the pair reads as
    one difference rather than two pictures."""
    pen = QPen(ink, max(1.5, r.width() / 26.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    y = r.bottom() - r.height() * 0.04
    p.drawLine(QPointF(r.left() + r.width() * 0.04, y),
               QPointF(r.right() - r.width() * 0.04, y))


def _draw_nothing(p: QPainter, r: QRectF, ink: QColor):
    """Emptiness under the instrument: a dashed floor line, well below it."""
    faint = QColor(ink)
    faint.setAlpha(110)
    pen = QPen(faint, max(1.0, r.width() / 40.0), Qt.PenStyle.DashLine)
    p.setPen(pen)
    y = r.bottom() - r.height() * 0.04
    p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))


def press_button(times: int = 2, widget: QWidget | None = None,
                 height: int | None = None) -> QPixmap:
    """The capped instrument, a press arrow, and **2×**.

    The window that teaches ChromIQ the white tile was titled "One press
    teaches…" and buried the real rule four paragraphs down: over USB one press
    is enough because the instrument flags the covered opening itself, but over
    **Bluetooth it says nothing**, so the value is only accepted when TWO
    presses come back bit-identical — something a real measurement never does.
    Basti pressed once, confirmed, and the window sat there; pressing twice
    worked immediately.

    Drawn from the same two primitives as the calibration steps, deliberately:
    this is the same instrument in the same cap that the person has just been
    looking at in the white-calibration window, so it must be recognisably the
    same picture rather than a new one that has to be learned.
    """
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if widget is not None:
        base = widget.font()
    elif app is not None:
        base = app.font()
    else:
        base = QFont()
    fm = QFontMetrics(base)
    cell = height or fm.height() * 7.2
    w = int(cell * 1.22)                     # room for the arrow and the "2x"
    h = int(cell)
    dpr = (widget.devicePixelRatioF() if widget is not None else 1.0) or 1.0
    pm = QPixmap(int(w * dpr), int(h * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)

    ink = _ink(widget)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # The instrument sits LOW in the cell: the press arrow lives above it, and
    # a first version drew the arrow off the top of the pixmap where it was
    # clipped to a stub.
    box = QRectF(w * 0.02, cell * 0.30, cell * 0.72, cell * 0.68)
    _draw_instrument(p, box, ink, nose_down=True)
    _draw_cap(p, box, ink, face_white=True)

    # THE PRESS: an arrow onto the top of the body, which is where the button
    # is. Down, because that is the direction of the hand.
    pen = QPen(ink, max(1.5, cell / 26.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    x = box.center().x()
    # A TINY GAP, NOT A TOUCH. The arrow tip used to land on the body outline
    # and the two strokes merged into one shape (Basti, 2026-08-31: *"i would
    # like to see a tiny gap between the arrow and the instrument icon"*).
    # Derived from where `_draw_instrument` actually puts the body top, not
    # from a constant, so moving the body cannot silently close it again.
    _body_top = box.top() + box.height() * 0.06
    tip = _body_top - cell * 0.08
    p.drawLine(QPointF(x, cell * 0.04), QPointF(x, tip))
    head = cell * 0.06
    p.drawLine(QPointF(x - head, tip - head), QPointF(x, tip))
    p.drawLine(QPointF(x + head, tip - head), QPointF(x, tip))

    # …AND HOW MANY TIMES. The whole point of the picture.
    f = QFont(base)
    f.setPointSizeF(max(9.0, base.pointSizeF() * 1.35))
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(box.right() + cell * 0.02, 0,
                      w - box.right() - cell * 0.02, h),
               int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
               f"{times}\u00d7")
    p.end()
    return pm


def steps_pair(step: str, widget: QWidget | None = None,
               height: int | None = None) -> QPixmap:
    """Both calibration steps, one above the other, with `step` marked.

    The same picture in both windows, so the pair is the thing the user reads
    and the difference between the two steps cannot be missed.

    STACKED, NOT SIDE BY SIDE. They were side by side until the owner saw them
    in the real window: the text beside them is a tall, narrow column, so a
    wide pair left the picture small and the space under it empty. Stacked, the
    pair fills the height the text already occupies and each step can be half
    again as large — and reading downwards matches the order the steps are
    taken in.
    """
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if widget is not None:
        base = widget.font()
    elif app is not None:
        base = app.font()
    else:
        # No application: a doc build, a headless import, a test that only
        # wants the geometry. Draw against a default font rather than raising —
        # a picture is never worth taking the caller down with it.
        base = QFont()
    fm = QFontMetrics(base)
    # Sized from the font, so it keeps its proportions at any text size. The
    # gap is what makes them two pictures rather than one tall one.
    gap = fm.height() * 0.9
    cell = (height - gap) / 2.0 if height else fm.height() * 7.2
    h = int(cell * 2 + gap)
    w = int(cell * 1.05)
    dpr = (widget.devicePixelRatioF() if widget is not None else 1.0) or 1.0
    pm = QPixmap(int(w * dpr), int(h * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)

    ink = _ink(widget)
    dim = QColor(ink)
    dim.setAlpha(70)                       # the step that is NOT current

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    top = QRectF(0, 0, w, cell)
    bottom = QRectF(0, cell + gap, w, cell)

    # --- step 1: cap on, white face --------------------------------------
    c = ink if step == WHITE_STEP else dim
    box = QRectF(top.left() + w * 0.10, top.top() + cell * 0.06,
                 w * 0.80, cell * 0.80)
    _draw_instrument(p, box, c, nose_down=True)
    _draw_cap(p, box, c, face_white=True)
    # THE SOLID LINE MEANS "RESTING ON SOMETHING", ALWAYS — it is not the
    # current-step marker, and it used to be. Because the marker was an
    # underline drawn at the same place, the step that means "pointing at
    # nothing" gained a solid floor underneath its dashes whenever it was the
    # current one, which says the opposite of what that step is. Confirmed on
    # screen in the real black-calibration window before this was changed.
    # NO TICK HERE. There was one, and the owner read it exactly as a tick
    # means: *"i don't want the checkmark next to the first one because i would
    # read it as done although it is not yet done in the first window"*. He is
    # right — in the white window that step is what he is about to do, and a
    # tick on a step nobody has taken is the picture disagreeing with the text.
    _draw_surface(p, box, c)

    # --- step 2: cap off, pointing at nothing -----------------------------
    c = ink if step == BLACK_STEP else dim
    box = QRectF(bottom.left() + w * 0.10, bottom.top() + cell * 0.06,
                 w * 0.80, cell * 0.80)
    _draw_instrument(p, box, c, nose_down=True)
    _draw_nothing(p, box, c)

    # The current step is marked DOWN THE SIDE, where nothing the drawing means
    # can be read into it, and in the MEASURE TAB'S OWN GREEN — these windows
    # belong to that tab, and its guidance already reads in that colour there.
    # The other step is simply fainter.
    cur = top if step == WHITE_STEP else bottom
    bar = max(2.5, cell / 28.0)
    pen = QPen(_accent(widget), bar)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    x = cur.left() + bar
    p.drawLine(QPointF(x, cur.top() + cell * 0.16),
               QPointF(x, cur.bottom() - cell * 0.16))
    p.end()
    return pm
