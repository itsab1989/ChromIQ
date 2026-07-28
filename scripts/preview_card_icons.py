"""Five icon proposals for each of the two new help cards (#130, Knut).

Drawn with the SAME conventions as ui.dialogs.welcome_dialog.WorkflowIcon:
96x96, monochrome strokes that flip with the theme, one magenta accent,
geometric. Rendered here at 4x into a contact sheet so Knut can choose.
"""
import os, math, pathlib
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QImage, QPainter, QPainterPath,
                         QPen)
from PyQt6.QtWidgets import QApplication

SPEC_MAGENTA = "#d6009a"
S = 96
SCALE = 4

app = QApplication([])


def _clear():
    return QColor(0, 0, 0, 0)


# --------------------------------------------------------------- getting started
def gs1_compass(p, fg, accent, st):
    """A compass — 'find your way around'."""
    c, r = S / 2, 30
    p.setPen(QPen(fg, st)); p.setBrush(_clear())
    p.drawEllipse(QRectF(c - r, c - r, 2 * r, 2 * r))
    for a in range(0, 360, 45):
        rad = math.radians(a)
        p.drawLine(QPointF(c + (r - 7) * math.cos(rad), c + (r - 7) * math.sin(rad)),
                   QPointF(c + r * math.cos(rad), c + r * math.sin(rad)))
    path = QPainterPath()
    path.moveTo(c, c - 20); path.lineTo(c + 7, c + 5); path.lineTo(c - 7, c + 5)
    path.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent); p.drawPath(path)
    p.setBrush(fg); p.drawEllipse(QRectF(c - 3, c - 3, 6, 6))


def gs2_layout(p, fg, accent, st):
    """The app's own layout — masthead, options panel, preview."""
    m = 12
    p.setPen(QPen(fg, st)); p.setBrush(_clear())
    p.drawRoundedRect(QRectF(m, m, S - 2 * m, S - 2 * m), 5, 5)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent)
    p.drawRoundedRect(QRectF(m + 3, m + 3, S - 2 * m - 6, 13), 3, 3)
    p.setPen(QPen(fg, st)); p.setBrush(_clear())
    p.drawLine(QPointF(m + 26, m + 20), QPointF(m + 26, S - m - 3))
    for i in range(4):
        y = m + 28 + i * 9
        p.drawLine(QPointF(m + 7, y), QPointF(m + 20, y))


def gs3_signpost(p, fg, accent, st):
    """A signpost — three ways from one place."""
    p.setPen(QPen(fg, st))
    p.drawLine(QPointF(S / 2, 22), QPointF(S / 2, S - 14))
    for i, (y, w, right) in enumerate(((30, 30, True), (46, 26, False),
                                       (62, 22, True))):
        x0 = S / 2 if right else S / 2 - w
        rect = QRectF(x0, y - 7, w, 14)
        if i == 0:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent)
        else:
            p.setPen(QPen(fg, st)); p.setBrush(_clear())
        p.drawRoundedRect(rect, 3, 3)


def gs4_numbered_path(p, fg, accent, st):
    """1 - 2 - 3 along a curve: the five steps, in order."""
    path = QPainterPath(QPointF(16, 74))
    path.cubicTo(34, 74, 30, 34, 50, 34)
    path.cubicTo(70, 34, 66, 66, 82, 60)
    p.setPen(QPen(fg, st, Qt.PenStyle.DashLine)); p.setBrush(_clear())
    p.drawPath(path)
    pts = [(16, 74), (50, 34), (82, 60)]
    for i, (x, y) in enumerate(pts):
        r = 9 if i == 0 else 7
        if i == 0:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent)
        else:
            p.setPen(QPen(fg, st)); p.setBrush(_clear())
        p.drawEllipse(QRectF(x - r, y - r, 2 * r, 2 * r))


def gs5_book(p, fg, accent, st):
    """An open guide with a bookmark."""
    p.setPen(QPen(fg, st)); p.setBrush(_clear())
    p.drawLine(QPointF(S / 2, 24), QPointF(S / 2, 74))
    for sgn in (-1, 1):
        path = QPainterPath(QPointF(S / 2, 24))
        path.lineTo(S / 2 + sgn * 32, 30)
        path.lineTo(S / 2 + sgn * 32, 70)
        path.lineTo(S / 2, 74)
        p.drawPath(path)
    p.setPen(QPen(fg, 1.8))
    for i in range(3):
        y = 40 + i * 9
        p.drawLine(QPointF(S / 2 - 26, y), QPointF(S / 2 - 8, y))
        p.drawLine(QPointF(S / 2 + 8, y), QPointF(S / 2 + 26, y))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent)
    path = QPainterPath(QPointF(60, 24)); path.lineTo(72, 24)
    path.lineTo(72, 46); path.lineTo(66, 40); path.lineTo(60, 46)
    path.closeSubpath(); p.drawPath(path)


# ----------------------------------------------------------------- main actions
def ma1_table(p, fg, accent, st):
    """A table — which is literally what the card is."""
    m = 13
    p.setPen(QPen(fg, st)); p.setBrush(_clear())
    p.drawRoundedRect(QRectF(m, m, S - 2 * m, S - 2 * m), 4, 4)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent)
    p.drawRect(QRectF(m + 2, m + 2, S - 2 * m - 4, 12))
    p.setPen(QPen(fg, 1.8))
    for i in range(1, 4):
        y = m + 14 + i * 14
        p.drawLine(QPointF(m, y), QPointF(S - m, y))
    p.drawLine(QPointF(m + 26, m + 14), QPointF(m + 26, S - m))


def ma2_branches(p, fg, accent, st):
    """One goal, several routes to it."""
    p.setPen(QPen(fg, st)); p.setBrush(_clear())
    src = QPointF(20, S / 2)
    for y in (26, 48, 70):
        path = QPainterPath(src)
        path.cubicTo(46, S / 2, 50, y, 72, y)
        p.drawPath(path)
        p.drawEllipse(QRectF(72 - 6, y - 6, 12, 12))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent)
    p.drawEllipse(QRectF(src.x() - 9, src.y() - 9, 18, 18))


def ma3_checklist(p, fg, accent, st):
    """A list of things you can do, one of them done."""
    for i in range(3):
        y = 26 + i * 22
        if i == 0:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent)
            p.drawRoundedRect(QRectF(16, y - 8, 16, 16), 3, 3)
            p.setPen(QPen(QColor("#ffffff"), 2.6))
            p.drawLine(QPointF(20, y), QPointF(23, y + 4))
            p.drawLine(QPointF(23, y + 4), QPointF(28, y - 4))
        else:
            p.setPen(QPen(fg, st)); p.setBrush(_clear())
            p.drawRoundedRect(QRectF(16, y - 8, 16, 16), 3, 3)
        p.setPen(QPen(fg, st)); p.setBrush(_clear())
        p.drawLine(QPointF(40, y), QPointF(80, y))


def ma4_crossroads(p, fg, accent, st):
    """A junction: the same place reached from several directions."""
    c = S / 2
    p.setPen(QPen(fg, st))
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        p.drawLine(QPointF(c + dx * 12, c + dy * 12),
                   QPointF(c + dx * 34, c + dy * 34))
        ex, ey = c + dx * 34, c + dy * 34
        p.setBrush(_clear())
        p.drawEllipse(QRectF(ex - 5, ey - 5, 10, 10))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent)
    p.drawEllipse(QRectF(c - 11, c - 11, 22, 22))


def ma5_stacked_rows(p, fg, accent, st):
    """Stacked action rows, the first one picked out."""
    for i in range(4):
        y = 20 + i * 16
        rect = QRectF(16, y, 64, 12)
        if i == 0:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent)
        else:
            p.setPen(QPen(fg, st)); p.setBrush(_clear())
        p.drawRoundedRect(rect, 3, 3)
    p.setPen(QPen(fg, st)); p.setBrush(_clear())
    p.drawLine(QPointF(16, 16), QPointF(80, 16))


CARDS = {
    "Getting started": [("A  Compass", gs1_compass), ("B  Interface map", gs2_layout),
                        ("C  Signpost", gs3_signpost),
                        ("D  Numbered path", gs4_numbered_path),
                        ("E  Open guide", gs5_book)],
    "Overview of Main Actions": [
        ("A  Table", ma1_table), ("B  Branching routes", ma2_branches),
        ("C  Checklist", ma3_checklist), ("D  Crossroads", ma4_crossroads),
        ("E  Stacked rows", ma5_stacked_rows)],
}


def render(fn, mode):
    img = QImage(S * SCALE, S * SCALE, QImage.Format.Format_ARGB32)
    img.fill(QColor("#f4f2ef") if mode == "light" else QColor("#1b1b1b"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(SCALE, SCALE)
    fn(p, QColor("#22211f" if mode == "light" else "#e6e6e6"),
       QColor(SPEC_MAGENTA), 2.4)
    p.end()
    return img


def sheet(out: pathlib.Path):
    cell, gap, label_h, head_h = S * SCALE, 26, 44, 60
    cols = 5
    w = gap + cols * (cell + gap)
    h = head_h + len(CARDS) * 2 * (cell + label_h + gap) + gap + 40
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#2a2a2a"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    f = QFont(); f.setPixelSize(30); f.setBold(True); p.setFont(f)
    p.setPen(QColor("#ffffff"))
    p.drawText(QRectF(gap, 12, w, 40), Qt.AlignmentFlag.AlignLeft,
               "Icon proposals — pick one letter per card")
    y = head_h
    for card, variants in CARDS.items():
        for mode in ("dark", "light"):
            f2 = QFont(); f2.setPixelSize(26); f2.setBold(True); p.setFont(f2)
            p.setPen(QColor("#d6009a"))
            p.drawText(QRectF(gap, y - 4, w, 34),
                       Qt.AlignmentFlag.AlignLeft, f"{card}  ({mode})")
            yy = y + 34
            for i, (name, fn) in enumerate(variants):
                x = gap + i * (cell + gap)
                p.drawImage(QRectF(x, yy, cell, cell), render(fn, mode))
                f3 = QFont(); f3.setPixelSize(24); p.setFont(f3)
                p.setPen(QColor("#e6e6e6"))
                p.drawText(QRectF(x, yy + cell + 6, cell, 30),
                           Qt.AlignmentFlag.AlignHCenter, name)
            y = yy + cell + label_h + gap
    p.end()
    img.save(str(out))
    print("wrote", out, img.width(), "x", img.height())


if __name__ == "__main__":
    sheet(pathlib.Path(__file__).parent / "icon_proposals.png")
