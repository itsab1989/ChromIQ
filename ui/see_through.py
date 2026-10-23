"""The see-through look of the chart preview's legend chip, shared with the
Measure tab's pause note (Basti, 2026-10-23: the note keeps "the same look as
the expected · measured legend chip in every mode").

K1 (Basti, 2026-10-21): a dark see-through panel, then the text in a light
colour over a dark outline. The words do not depend on the panel: each glyph
carries its own dark halo, so the panel can stay at 80 of 255 and the paper,
the arrow and the patches show through. Measured on Knut's run 1 chart then:
text against the darkest pixel beside it 12.8:1 (median), where a solid panel
gave 7.2:1.

`TiffPreview._paint_legend_chip` and `ui.pause_note.PauseNote` both paint
through these two functions, so the two can never drift apart.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap

#: The panel: (20, 20, 20) at this alpha (of 255) at full opacity.
PANEL_RGB = (20, 20, 20)
PANEL_ALPHA = 80
#: The text's light colour, and the dark outline every glyph carries.
TEXT_RGB = (244, 242, 239)
HALO_RGB = (20, 20, 20)
HALO_ALPHA = 220
#: Width of that outline, logical px (half of it falls outside the glyph).
TEXT_OUTLINE = 2.2
#: The pause note's panel. The same colour, halo, text and square corners as
#: the chip; only the panel is denser, because the chip's 80 does not carry
#: several sentences (Basti, 2026-10-23: "readability is bad now"). The value
#: is the lowest that measured at least 4.5:1 (WCAG AA for its text size)
#: between the words and the panel around them, worst case over light, mid
#: and dark patches, on screen, in light, dark and neutral alike
#: (agent20/contrast/alpha-sweep-*.json).
NOTE_PANEL_ALPHA = 152


def paint_panel(painter: QPainter, rect, opacity: float = 1.0,
                alpha: int = PANEL_ALPHA) -> None:
    """The see-through panel, square-cornered like the chip. *alpha* is the
    panel's own (of 255) at full opacity: the chip's 80, or the pause note's
    `NOTE_PANEL_ALPHA` (several sentences, not a label)."""
    painter.fillRect(rect, QColor(*PANEL_RGB, int(alpha * opacity)))


def paint_halo_text(painter: QPainter, x: float, baseline: float,
                    font: QFont, text: str, opacity: float = 1.0) -> None:
    """*text* at (*x*, *baseline*): the light glyphs over their dark halo."""
    if not text:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addText(float(x), float(baseline), font, text)
    # WINDING, NOT QT'S DEFAULT ODD-EVEN (Basti, 2026-10-23: "the text in
    # some cases looks bad when there are characters with crossing lines").
    # A glyph whose contours overlap (the crossing strokes of x, t, f, k, ß,
    # the joins of many fonts' ä) is drawn with odd-even as a HOLE where the
    # strokes cross, and the dark halo shows through it. The halo first,
    # round at every corner and end, then the glyphs filled over it with no
    # pen, winding, so nothing dark is ever drawn inside a letter.
    path.setFillRule(Qt.FillRule.WindingFill)
    halo = QPen(QColor(*HALO_RGB, int(HALO_ALPHA * opacity)))
    halo.setWidthF(TEXT_OUTLINE)
    halo.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    halo.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.strokePath(path, halo)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.fillPath(path, QColor(*TEXT_RGB, int(255 * opacity)))
    painter.restore()


#: Pictures of halo text already drawn, by (font, text, device pixel ratio).
_PICTURES: dict = {}
_PICTURES_MAX = 32


def halo_text_picture(font: QFont, text: str, dpr: float):
    """*text* drawn by :func:`paint_halo_text` into a transparent picture,
    once: ``(pixmap, left, top)``, the picture's top-left relative to the
    text's own origin (x, baseline), in whole logical pixels so the glyphs
    land on exactly the device pixels a direct draw would put them on."""
    key = (font.key(), text, float(dpr))
    hit = _PICTURES.get(key)
    if hit is not None:
        return hit
    path = QPainterPath()
    path.addText(0.0, 0.0, font, text)
    br = path.boundingRect()
    pad = TEXT_OUTLINE + 1.0
    left = math.floor(br.left() - pad)
    top = math.floor(br.top() - pad)
    w = math.ceil(br.right() + pad) - left
    h = math.ceil(br.bottom() + pad) - top
    pix = QPixmap(max(1, math.ceil(w * dpr)), max(1, math.ceil(h * dpr)))
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    paint_halo_text(p, -left, -top, font, text)
    p.end()
    if len(_PICTURES) >= _PICTURES_MAX:
        _PICTURES.clear()
    _PICTURES[key] = (pix, left, top)
    return _PICTURES[key]


def paint_halo_text_cached(painter: QPainter, x: int, baseline: int,
                           font: QFont, text: str,
                           opacity: float = 1.0) -> None:
    """:func:`paint_halo_text`, from a picture drawn once (for a fade).

    Stroking every glyph's outline for its halo costs about 6 ms for the
    chip's one line, and the chip's fade repainted it on every step (Basti,
    2026-10-23: "the fade ... sometimes does not look smooth"). At full
    opacity the result is the same pixels; while fading, the text and its
    halo fade as one (no halo showing through half-faded letters)."""
    if not text:
        return
    dev = painter.device()
    dpr = float(dev.devicePixelRatioF()) if dev is not None else 1.0
    pix, left, top = halo_text_picture(font, text, dpr)
    painter.save()
    painter.setOpacity(painter.opacity() * float(opacity))
    painter.drawPixmap(QPointF(float(x) + left, float(baseline) + top), pix)
    painter.restore()


def rectf(x, y, w, h) -> QRectF:
    return QRectF(float(x), float(y), float(w), float(h))
