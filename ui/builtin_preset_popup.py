"""Speech-bubble popup listing the built-in Create Chart presets.

Opened from the Create Chart tab's star button (next to GUIDED / MANUAL);
auto-closes on outside click (Qt.Popup). Same rounded-panel-with-tail look as
``ui.tools_popup.ToolsPopup``, but the rows are grouped under a small instrument
header (e.g. "i1Pro", "ColorMunki"). Header rows are inert; preset rows behave
like combobox items — hover highlight, click emits ``selected`` with the preset
key. Picking one is wired by the tab to the very same flow as choosing the
preset in the Manual presets dropdown (name prompt + generate).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

from PyQt6.QtCore import (QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt,
                          pyqtSignal)
from PyQt6.QtGui import (
    QColor, QFont, QFontMetricsF, QMouseEvent, QPainter, QPainterPath,
    QPaintEvent, QPen,
)
from PyQt6.QtWidgets import QApplication, QToolButton, QWidget

from ui.styles import SPEC_MAGENTA
from core.i18n import tr
from ui import neutral_styles


# Per-mode visual tokens — kept in step with ui.tools_popup so the two popups
# read as siblings. ``header_text`` is the muted instrument-label colour.
_PALETTE_DARK = {
    "panel_bg":      "#1f1f1f",
    "panel_border":  "#333333",
    "text":          "#e6e6e6",
    "text_hover":    "#ffffff",
    "header_text":   "#8a8a8a",
    "hover_bg":      "#2a2a2a",
    "shadow":        QColor(0, 0, 0, 110),
}
_PALETTE_LIGHT = {
    "panel_bg":      "#ffffff",
    "panel_border":  "#d0ccc6",
    "text":          "#22211f",
    "text_hover":    "#22211f",
    "header_text":   "#9b958c",
    "hover_bg":      "#f0ece6",
    "shadow":        QColor(0, 0, 0, 30),
}
#: Neutral — kept in step with ui.tools_popup, as the two dark/light pairs
#: already are. ``header_text`` is TERTIARY, not faint: at 8.13:1 it still
#: reads, because an instrument label that works may not be faint.
_PALETTE_NEUTRAL = {
    "panel_bg":      neutral_styles.NM_BG_SURFACE,
    "panel_border":  neutral_styles.NM_BORDER,
    "text":          neutral_styles.NM_TEXT_MAIN,
    "text_hover":    neutral_styles.NM_TEXT_MAIN,
    "header_text":   neutral_styles.NM_TEXT_FAINT,
    # THE THEME'S HOVER TOKEN, not the window value it used to name. Those
    # were the same colour until the grounds were collapsed onto one; after
    # that, a hover row painted in the window value IS the card it sits on and
    # the row stops lighting up at all. NM_BG_HOVER steps down instead.
    "hover_bg":      neutral_styles.NM_BG_HOVER,
    "shadow":        QColor(0, 0, 0, 30),
}

#: ``{appearance: palette}`` — a TABLE, not a ternary. ``_PALETTE_LIGHT if
#: mode == "light" else _PALETTE_DARK`` had room for two answers and gave the
#: dark one to everything else: the appearance name arrived intact (that was
#: ``accept_mode``'s job, one layer up) and the COLOURS were still folded.
#: Adding an appearance is adding a row.
_PALETTES = {
    "light":   _PALETTE_LIGHT,
    "dark":    _PALETTE_DARK,
    "neutral": _PALETTE_NEUTRAL,
}


class BuiltinPresetButton(QToolButton):
    """Presets button that opens the Built-in presets overlay.

    Sits next to the GUIDED / MANUAL switch. The glyph is a small **list** (three
    rows, each a bullet + line) — a menu of presets to pick from, which reads as
    "presets" rather than "favourites" (the old star did). It's the app's spectrum
    magenta in the two COLOURED themes, painted directly in ``paintEvent`` like
    the welcome "?" button — building a QIcon from a DPR-scaled pixmap clips on
    Retina, painting in logical coords doesn't. The QSS ``#tooltip_btn`` rule
    still paints the hover background (we chain to ``super().paintEvent``).

    ``set_appearance`` used to be a no-op on the grounds that "magenta is
    theme-independent". That stopped being true the moment a third appearance
    had ONE accent: it now remembers the mode and the glyph is painted in
    whatever that appearance's accent is.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tooltip_btn")
        # Icon-only: never take keyboard focus (space would open the presets
        # overlay just because a tab handed it the initial focus) (Knut).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(tr("Built-in presets"))
        self.setFixedSize(QSize(40, 40))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self._mode = "dark"

    def set_appearance(self, mode: str) -> None:
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, ev: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(ev)  # QSS background (incl. :hover) under the glyph
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        s = min(w, h)
        from ui.theme import accent_for
        color = QColor(accent_for(SPEC_MAGENTA, self._mode))
        if not self.isEnabled():
            color.setAlpha(70)      # parked (e.g. FROM PROFILE GAMUT active)
        elif not self._hover:
            color.setAlpha(230)
        # Three list rows: a rounded-square bullet + a line, centred with a
        # comfortable margin so the glyph reads as a small icon in the hit target.
        line_w = s * 0.075
        bullet = s * 0.10
        for i in range(3):
            y = h * (0.32 + i * 0.20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(w * 0.22, y - bullet / 2, bullet, bullet),
                              bullet * 0.28, bullet * 0.28)
            pen = QPen(color)
            pen.setWidthF(line_w)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(w * 0.40, y), QPointF(w * 0.78, y))
        p.end()


@dataclass(frozen=True)
class _VisualRow:
    """One painted line: an instrument header, a selectable preset, or the
    arrow that opens and closes a group's other presets."""
    kind:   str          # "header" | "item" | "more" | "note"
    text:   str
    key:    str | None   # preset key for "item" rows, the group for "more"
    top:    int          # y of the row within the widget
    height: int
    group:  str = ""     # the heading an "item" under an arrow belongs to


class BuiltinPresetPopup(QWidget):
    """Grouped speech-bubble popup. Show via ``show_under(button)``.

    ``groups`` is ``[(instrument, [(overlay_label, key), …]), …]`` — exactly
    what the tab derives from BUILTIN_PRESET_GROUPS. Emits ``selected(key)``.

    ``more`` is ``{instrument: [(overlay_label, key), …]}``: the presets of a
    group that are NOT ticked in the window behind Create Chart's gear button
    (#182 5818659478). They wait under an arrow row after the group's ticked
    ones, pointing right while closed and down while open, exactly as in the
    "Select preset" pulldown. A click on the arrow, or Return, Space or the
    Right arrow key on it, opens the group and leaves the list open; Left
    closes it again. Up and Down move through the rows, Return picks a preset.

    ``note`` is the paper-filter note (Knut, #182 5834773589, B8-1171), the
    list's last row, painted in the app's information colours
    (:func:`ui.theme.info_colours`) and wrapped to the panel's width. It is
    never selectable: Up and Down skip it, a click on it does nothing, and
    it can never be emitted as a preset.
    """

    selected = pyqtSignal(str)  # preset key

    TAIL_W       = 16   # base width of the tail triangle
    TAIL_H       = 9    # height of the tail (sticks up above the panel)
    CORNER_R     = 10
    HEADER_H     = 26   # instrument header row
    ROW_H        = 34   # preset row
    H_PAD        = 18   # horizontal padding inside the panel
    V_PAD        = 8    # vertical padding above the first / below the last row
    ITEM_INDENT  = 12   # extra left inset for preset labels under a header
    PANEL_MARGIN = 12   # transparent space around panel for the drop shadow
    # When the built-in list is taller than this many preset entries the panel
    # caps its height and scrolls (mouse wheel). One leading header is allowed
    # for on top of the visible entries.
    MAX_VISIBLE_ITEMS = 10
    SCROLLBAR_W       = 4    # width of the scroll thumb drawn inside the panel

    def __init__(
        self,
        groups: list[tuple[str, list[tuple[str, str]]]],
        parent: QWidget | None = None,
        more: dict[str, list[tuple[str, str]]] | None = None,
        note: str = "",
    ) -> None:
        super().__init__(parent)
        # NoDropShadowWindowHint suppresses the platform's own popup shadow (see
        # ui.tools_popup for the rationale); we paint our own soft shadow.
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._groups  = groups
        self._more    = dict(more or {})
        self._note    = note
        self._open: set[str] = set()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._mode    = "dark"
        self._palette = _PALETTE_DARK
        self._hover_index: int = -1
        self._tail_offset_x: int = 0
        self._anchor: QWidget | None = None

        self._item_font = QFont()
        self._item_font.setPixelSize(13)
        self._header_font = QFont()
        self._header_font.setPixelSize(11)
        self._header_font.setBold(True)
        self.setFont(self._item_font)

        # Scroll state (set in _compute_size). _content_top is the widget-space y
        # of the first row; rows store content-relative tops and are offset by
        # _content_top - _scroll_y when painted / hit-tested.
        self._scroll_y    = 0
        self._max_scroll  = 0
        self._viewport_h  = 0
        self._content_h   = 0
        self._content_top = 0

        self._rows: list[_VisualRow] = []
        self._build_rows()
        self._compute_size()

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        self._palette = _PALETTES.get(self._mode, _PALETTE_DARK)
        self.update()

    # ------------------------------------------------------------------
    def _build_rows(self) -> None:
        """Flatten the grouped presets into headers + item rows.

        ``top`` is content-relative (first row at y=0); painting/hit-testing add
        ``_content_top - _scroll_y`` so the same list can be scrolled."""
        self._rows = []
        y = 0
        for instr, entries in self._groups:
            self._rows.append(_VisualRow("header", instr, None, y, self.HEADER_H))
            y += self.HEADER_H
            for label, key in entries:
                self._rows.append(_VisualRow("item", label, key, y, self.ROW_H))
                y += self.ROW_H
            rest = self._more.get(instr) or []
            if not rest:
                continue
            is_open = instr in self._open
            self._rows.append(_VisualRow(
                "more", self._more_text(len(rest), is_open), instr, y,
                self.ROW_H))
            y += self.ROW_H
            if is_open:
                for label, key in rest:
                    self._rows.append(_VisualRow("item", label, key, y,
                                                 self.ROW_H, group=instr))
                    y += self.ROW_H
        if self._note:
            # Its height is set by _compute_size, once the width is known.
            self._rows.append(_VisualRow("note", self._note, None, y,
                                         self.ROW_H))

    @staticmethod
    def _more_text(count: int, is_open: bool) -> str:
        words = (tr("1 more preset") if count == 1 else
                 tr("{count} more presets").format(count=count))
        return f"{'▾' if is_open else '▸'}  {words}"

    def is_open(self, group: str) -> bool:
        return group in self._open

    def toggle_group(self, group: str, is_open: bool | None = None) -> None:
        """Open or close a group's arrow. The panel keeps its top edge and
        grows or shrinks below it, and the arrow row stays in view."""
        if group not in self._more:
            return
        if is_open is None:
            is_open = group not in self._open
        if is_open:
            self._open.add(group)
        else:
            self._open.discard(group)
        scroll = self._scroll_y
        self._build_rows()
        self._compute_size(keep_scroll=scroll)
        for i, row in enumerate(self._rows):
            if row.kind == "more" and row.key == group:
                self._hover_index = i
                self._ensure_visible(i)
                break
        self.update()

    def _ensure_visible(self, index: int) -> None:
        row = self._rows[index]
        top = row.top
        if index > 0 and self._rows[index - 1].kind == "header":
            top = self._rows[index - 1].top      # keep a group's heading with it
        if top < self._scroll_y:
            self._scroll_y = max(0, top)
        elif row.top + row.height > self._scroll_y + self._viewport_h:
            self._scroll_y = min(self._max_scroll,
                                 row.top + row.height - self._viewport_h)

    def _compute_size(self, keep_scroll: int = 0) -> None:
        item_fm   = QFontMetricsF(self._item_font)
        header_fm = QFontMetricsF(self._header_font)
        text_w = 0.0
        # Measured over EVERY preset, the ones under a closed arrow included,
        # so the panel does not change width when an arrow is opened.
        # Not the note: it wraps to the panel, it does not widen it.
        texts = [(r.kind, r.text) for r in self._rows if r.kind != "note"]
        for rest in self._more.values():
            texts.extend(("item", label) for label, _k in rest)
        for kind, text in texts:
            if kind != "header":
                # Items inset by ROW(6)+TEXT(12)+ITEM_INDENT on the left.
                w = item_fm.horizontalAdvance(text) + self.ITEM_INDENT
            else:
                w = header_fm.horizontalAdvance(text)
            text_w = max(text_w, w)
        inner = 2 * (6 + 12)
        panel_w = math.ceil(text_w) + inner + self.H_PAD + self.SCROLLBAR_W
        panel_w = max(panel_w, 260)
        if self._rows and self._rows[-1].kind == "note":
            self._rows[-1] = replace(
                self._rows[-1], height=self._note_height(panel_w))

        self._content_h = sum(r.height for r in self._rows)
        # Cap the viewport to one header + MAX_VISIBLE_ITEMS entries; scroll the
        # rest. A short list (≤ cap) shows in full with no scrolling.
        cap_h = self.HEADER_H + self.MAX_VISIBLE_ITEMS * self.ROW_H
        self._viewport_h = min(self._content_h, cap_h)
        self._max_scroll = self._content_h - self._viewport_h
        self._scroll_y = max(0, min(keep_scroll, self._max_scroll))

        self._content_top = self.PANEL_MARGIN + self.TAIL_H + self.V_PAD
        panel_h = self._viewport_h + 2 * self.V_PAD
        w = panel_w + 2 * self.PANEL_MARGIN
        h = panel_h + 2 * self.PANEL_MARGIN + self.TAIL_H
        self.setFixedSize(w, h)

    #: The note's padding inside its box, and the gap above the box.
    NOTE_PAD = 8
    NOTE_GAP = 6

    def _note_text_width(self, row_w: float) -> int:
        """The width the note's text wraps to in a row ``row_w`` wide: the
        box keeps the rows' own inset and the scroll thumb's room."""
        return max(40, int(row_w) - 2 * self.NOTE_PAD - self.SCROLLBAR_W - 4)

    def _note_height(self, panel_w: int) -> int:
        fm = QFontMetricsF(self._item_font)
        row_w = panel_w - 12
        rect = fm.boundingRect(
            QRectF(0, 0, self._note_text_width(row_w), 10000),
            int(Qt.TextFlag.TextWordWrap), self._note)
        return math.ceil(rect.height()) + 2 * self.NOTE_PAD + self.NOTE_GAP

    def _panel_rect(self) -> QRect:
        return QRect(
            self.PANEL_MARGIN,
            self.PANEL_MARGIN + self.TAIL_H,
            self.width()  - 2 * self.PANEL_MARGIN,
            self.height() - 2 * self.PANEL_MARGIN - self.TAIL_H,
        )

    def _viewport_rect(self) -> QRect:
        """The scrolling content region inside the panel (rows are clipped here)."""
        panel = self._panel_rect()
        return QRect(panel.left(), self._content_top, panel.width(), self._viewport_h)

    def _row_rect(self, row: _VisualRow) -> QRect:
        panel = self._panel_rect()
        y = self._content_top + row.top - self._scroll_y
        return QRect(panel.left() + 6, y, panel.width() - 12, row.height)

    # ------------------------------------------------------------------
    def show_under(self, anchor: QWidget) -> None:
        """Position so the tail apex lands at the horizontal centre of ``anchor``."""
        self._anchor = anchor
        gp = anchor.mapToGlobal(QPoint(0, anchor.height()))
        anchor_center_x = gp.x() + anchor.width() // 2

        ideal_x = anchor_center_x - self.width() // 2
        screen = anchor.screen()
        avail = screen.availableGeometry() if screen else None
        if avail:
            min_x = avail.left() + 4
            max_x = avail.right() - self.width() - 4
            x = max(min_x, min(ideal_x, max_x))
        else:
            x = ideal_x

        y = gp.y() + 2

        self._tail_offset_x = anchor_center_x - x
        self._tail_offset_x = max(
            self.PANEL_MARGIN + self.CORNER_R + self.TAIL_W,
            min(self._tail_offset_x,
                self.width() - self.PANEL_MARGIN - self.CORNER_R - self.TAIL_W),
        )

        self.move(x, y)
        self._hover_index = -1
        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    def paintEvent(self, _ev: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        pal = self._palette
        panel = self._panel_rect()

        bubble = QPainterPath()
        bubble.addRoundedRect(
            float(panel.left()), float(panel.top()),
            float(panel.width()), float(panel.height()),
            float(self.CORNER_R), float(self.CORNER_R),
        )
        tail = QPainterPath()
        apex_x = self._tail_offset_x
        apex_y = panel.top() - self.TAIL_H + 1
        base_y = panel.top() + 1
        tail.moveTo(float(apex_x),                   float(apex_y))
        tail.lineTo(float(apex_x - self.TAIL_W / 2), float(base_y))
        tail.lineTo(float(apex_x + self.TAIL_W / 2), float(base_y))
        tail.closeSubpath()
        bubble = bubble.united(tail)

        shadow = QPainterPath(bubble)
        shadow.translate(0, 3)
        p.fillPath(shadow, pal["shadow"])

        p.fillPath(bubble, QColor(pal["panel_bg"]))
        p.setPen(QPen(QColor(pal["panel_border"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bubble)

        # Clip the rows to the scrolling viewport so partial rows don't bleed
        # over the rounded corners / tail / padding.
        viewport = self._viewport_rect()
        sb_w = self.SCROLLBAR_W if self._max_scroll > 0 else 0
        p.save()
        p.setClipRect(viewport)
        for i, row in enumerate(self._rows):
            rect = self._row_rect(row)
            if rect.bottom() < viewport.top() or rect.top() > viewport.bottom():
                continue  # fully scrolled out of view
            if row.kind == "note":
                self._paint_note(p, rect, sb_w)
                continue
            if row.kind == "header":
                p.setPen(QColor(pal["header_text"]))
                p.setFont(self._header_font)
                p.drawText(
                    QRect(rect.left() + 12, rect.top(),
                          rect.width() - 24 - sb_w, rect.height()),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
                    row.text,
                )
                continue
            if i == self._hover_index:
                p.setBrush(QColor(pal["hover_bg"]))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(
                    QRect(rect.left(), rect.top(), rect.width() - sb_w, rect.height()),
                    6, 6,
                )
                text_color = pal["text_hover"]
            else:
                text_color = pal["text"]
            p.setPen(QColor(text_color))
            p.setFont(self._item_font)
            p.drawText(
                QRect(rect.left() + 12 + self.ITEM_INDENT, rect.top(),
                      rect.width() - 24 - self.ITEM_INDENT - sb_w, rect.height()),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                row.text,
            )
        p.restore()

        # Scroll thumb on the right edge of the viewport.
        if self._max_scroll > 0:
            track_h = viewport.height()
            thumb_h = max(24, int(track_h * self._viewport_h / self._content_h))
            travel  = track_h - thumb_h
            frac    = self._scroll_y / self._max_scroll if self._max_scroll else 0
            thumb_y = viewport.top() + int(travel * frac)
            thumb_x = panel.right() - self.SCROLLBAR_W - 3
            thumb   = QColor(pal["text"])
            thumb.setAlpha(70)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(thumb)
            p.drawRoundedRect(
                QRect(thumb_x, thumb_y, self.SCROLLBAR_W, thumb_h),
                2, 2,
            )

        p.end()

    def _paint_note(self, p: QPainter, rect: QRect, sb_w: int) -> None:
        """The paper-filter note: a box in the app's information colours for
        this appearance, the text wrapped inside it."""
        from ui.theme import info_colours
        colours = info_colours(self._mode)
        box = QRectF(rect.left(), rect.top() + self.NOTE_GAP,
                     rect.width() - sb_w - 4,
                     rect.height() - self.NOTE_GAP).adjusted(0.5, 0.5,
                                                            -0.5, -0.5)
        p.setPen(QPen(QColor(colours["border"]), 1))
        p.setBrush(QColor(colours["bg"]))
        p.drawRoundedRect(box, 6, 6)
        p.setPen(QColor(colours["text"]))
        p.setFont(self._item_font)
        p.drawText(box.adjusted(self.NOTE_PAD, self.NOTE_PAD,
                                -self.NOTE_PAD, -self.NOTE_PAD),
                   int(Qt.AlignmentFlag.AlignLeft
                       | Qt.AlignmentFlag.AlignVCenter
                       | Qt.TextFlag.TextWordWrap),
                   self._note)

    # ------------------------------------------------------------------
    def _index_at(self, pt: QPoint) -> int:
        """Index of the selectable (item) row under ``pt``; -1 over headers,
        gaps, the scrolled-away region, or the transparent margin."""
        if not self._viewport_rect().contains(pt):
            return -1
        for i, row in enumerate(self._rows):
            if row.kind in ("header", "note"):
                continue
            if self._row_rect(row).contains(pt):
                return i
        return -1

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self._max_scroll <= 0:
            return
        # angleDelta is in eighths of a degree; one notch ≈ 120 → ~ROW_H/notch.
        dy = event.angleDelta().y()
        step = int(round(dy / 120 * self.ROW_H)) or (1 if dy > 0 else -1)
        new_y = max(0, min(self._max_scroll, self._scroll_y - step))
        if new_y != self._scroll_y:
            self._scroll_y = new_y
            self._hover_index = self._index_at(
                self.mapFromGlobal(self.cursor().pos())
            )
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        idx = self._index_at(event.position().toPoint())
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover_index != -1:
            self._hover_index = -1
            self.update()
        super().leaveEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        # Same synthetic-Leave fix as ToolsPopup: the Qt.Popup mouse grab robs
        # the anchor button of the Leave that would clear its :hover state.
        super().hideEvent(event)
        anchor = self._anchor
        if anchor is not None:
            QApplication.sendEvent(anchor, QEvent(QEvent.Type.Leave))
            anchor.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        pt = event.position().toPoint()
        if not self._panel_rect().contains(pt):
            self.close()
            return
        idx = self._index_at(pt)
        if idx < 0:
            return
        self._activate(idx)

    def _activate(self, idx: int) -> None:
        row = self._rows[idx]
        if row.kind not in ("item", "more"):
            return                  # a heading or the note is never chosen
        if row.kind == "more":
            self.toggle_group(str(row.key))
            return
        key = row.key
        self.close()
        if key is not None:
            self.selected.emit(key)

    def _selectable(self) -> list[int]:
        return [i for i, r in enumerate(self._rows)
                if r.kind in ("item", "more")]

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """The list by keyboard: Up and Down move, Return or Space picks a
        preset or opens an arrow, Right opens and Left closes an arrow (Left on
        a preset under an open arrow goes back up to it), Escape closes."""
        rows = self._selectable()
        key = event.key()
        cur = self._hover_index
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up) and rows:
            if cur not in rows:
                nxt = rows[0] if key == Qt.Key.Key_Down else rows[-1]
            else:
                pos = rows.index(cur) + (1 if key == Qt.Key.Key_Down else -1)
                nxt = rows[max(0, min(len(rows) - 1, pos))]
            self._hover_index = nxt
            self._ensure_visible(nxt)
            self.update()
            return
        if cur in rows:
            row = self._rows[cur]
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                self._activate(cur)
                return
            if row.kind == "more" and key in (Qt.Key.Key_Right, Qt.Key.Key_Left):
                self.toggle_group(str(row.key), key == Qt.Key.Key_Right)
                return
            if row.kind == "item" and row.group and key == Qt.Key.Key_Left:
                self.toggle_group(row.group, True)   # stays open, goes up
                return
        super().keyPressEvent(event)
