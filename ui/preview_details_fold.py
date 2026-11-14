"""The fold for "Measured from Preview" and "Chart layout information".

Basti, 2026-11-14: *"in create chart tab can you make measured from preview
and chart layout information section collapsible? i think one button (or
triangle) should collapse both at once. i want a quick way to show and hide
it"*, then *"the purpose of this is to save space"*: the triangle takes no
line of its own in either state.

It lives in the chart preview's existing page line ("Page 1 / 1"), at its
left end, in the look of the tab's other folding sections
(`ui.widgets.CollapsibleGroupBox`: a filled ▼ / ▶ in the group-title ink).
Open, the tab is exactly as before. Folded, both frames go and the preview
takes their whole height; the right end of the same page line then repeats
their verdict, "Margins: OK" in green or the warning count in red, live after
a preview update or a Generate, and a click on it opens the frames again. A
new warning does not open them: the person chose to hide them.

The open / closed state is a view choice of the window, like the warning fold
inside "Measured from Preview" (`margin_warnings_expanded`): stored in the
app's settings (`preview_details_collapsed`), the same in Guided and Manual,
never part of a target or a preset (per_target_settings §1.1).
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QSizePolicy

from core.i18n import tr


def _fold_tooltip() -> str:
    return tr(
        "Hide or show the measurements and the chart layout information: the "
        "two boxes under the chart preview, “Measured from Preview” and "
        "“Chart layout information”, both at once.\n\n"
        "Hidden, the chart preview gets their room. The line under the "
        "preview then still tells you how the chart's margins look: “Margins: "
        "OK” in green when everything fits, or the number of warnings in red. "
        "Click the triangle or that text (or press Space while the triangle "
        "is selected) to see the boxes again.\n\n"
        "ChromIQ remembers your choice, also after a restart.")


def _title_ink() -> str:
    """The ink of every group-box title in the app ("Output", "Presets"), per
    appearance, so the triangle reads as one more of them."""
    from ui.theme import active_mode
    from ui.light_styles import LM_TEXT_FAINT
    from ui.neutral_styles import NM_TEXT_FAINT
    from ui.styles import TEXT_DIM
    return {"light": LM_TEXT_FAINT,
            "neutral": NM_TEXT_FAINT}.get(active_mode(), TEXT_DIM)


def _triangle_qss() -> str:
    # The page line's own size, so the line keeps its height.
    return f"color: {_title_ink()}; font-size: 12px; font-weight: 700;"


class _Triangle(QLabel):
    """▼ / ▶, focusable, clicked by mouse, Space or Return."""

    activated = pyqtSignal()

    def __init__(self, parent=None, accent: str = "#d0459a") -> None:
        super().__init__(parent)
        self._accent = accent
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def mousePressEvent(self, event) -> None:     # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:       # noqa: N802 (Qt override)
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return,
                           Qt.Key.Key_Enter):
            self.activated.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:        # noqa: N802 (Qt override)
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:       # noqa: N802 (Qt override)
        super().focusOutEvent(event)
        self.update()

    def changeEvent(self, event) -> None:         # noqa: N802 (Qt override)
        from PyQt6.QtCore import QEvent
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            qss = _triangle_qss()
            if qss != self.styleSheet():       # a style sheet is a palette
                self.setStyleSheet(qss)        # change too: no loop

    def paintEvent(self, event) -> None:          # noqa: N802 (Qt override)
        super().paintEvent(event)
        if not self.hasFocus():
            return
        # The keyboard focus, in the tab's own accent, inside the label so
        # the line keeps its height.
        from ui.theme import accent_for
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(accent_for(self._accent)))
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 3, 3)
        p.end()


class _Status(QLabel):
    """The folded verdict, elided to the room it has, never the page text."""

    clicked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._full = ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignRight
                          | Qt.AlignmentFlag.AlignVCenter)
        # Ignored across: it takes the room left over and is elided in it.
        self.setSizePolicy(QSizePolicy.Policy.Ignored,
                           QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._elide()

    def full_text(self) -> str:
        return self._full

    def sizeHint(self):                          # noqa: N802 (Qt override)
        h = super().sizeHint()
        h.setWidth(self.fontMetrics().horizontalAdvance(self._full) + 4)
        return h

    def _elide(self) -> None:
        self.setText(self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideRight, max(0, self.width())))

    def resizeEvent(self, event) -> None:         # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._elide()

    def mousePressEvent(self, event) -> None:     # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class PreviewDetailsFold(QObject):
    """The triangle and the folded verdict, placed in the preview's page line
    with `TiffPreview.set_nav_extras`; the owner hides the frames on
    `toggled`."""

    #: True when the person has just folded the frames away.
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None, *, collapsed: bool = False,
                 accent: str = "#d0459a", style: str = "C") -> None:
        super().__init__(parent)
        self._collapsed = bool(collapsed)
        self._verdict: "tuple[str, int]" = ("none", 0)
        self._available = True
        self._has_chart = False
        self.style = style
        self.triangle = _Triangle(None, accent)
        self.status = _Status(None)
        self.group = self.corner = self.badge = None
        if style == "A":
            self.group = FoldGroupA(self)
        elif style == "B":
            self.corner = CornerFoldB(self)
            self.badge = BadgeB(self)
            self.corner.setToolTip(_fold_tooltip())
        tip = _fold_tooltip()
        self.triangle.setToolTip(tip)
        self.triangle.setAccessibleName(tr("Measured from Preview"))
        self.triangle.setStyleSheet(_triangle_qss())
        self.triangle.activated.connect(self.toggle)
        self.status.clicked.connect(self._open)
        self._render()

    # -- state ---------------------------------------------------------------
    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool, *, emit: bool = False) -> None:
        """Fold or unfold. Restoring the stored answer does not emit, so it
        is not mistaken for the person's click and written back."""
        collapsed = bool(collapsed)
        changed = collapsed != self._collapsed
        self._collapsed = collapsed
        self._render()
        if emit and changed:
            self.toggled.emit(collapsed)

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed, emit=True)

    def _open(self) -> None:
        self.set_collapsed(False, emit=True)

    def set_verdict(self, kind: str, count: int = 0) -> None:
        """What the frames say, as `MarginInspectorPanel.verdict` gives it."""
        self._verdict = (kind, int(count))
        self._render()

    def set_available(self, available: bool) -> None:
        """False while Preferences hides both frames: nothing to fold."""
        self._available = bool(available)
        self._render()

    def set_has_chart(self, has: bool) -> None:
        """Whether the preview shows a page (and so its page line)."""
        self._has_chart = bool(has)
        self._render()

    def status_text(self) -> str:
        """The full verdict line as shown, or "" while it is hidden."""
        return "" if self.status.isHidden() else self.status.full_text()

    # -- drawing -------------------------------------------------------------
    def _render(self) -> None:
        from ui.widgets import set_ink
        self.triangle.setText("▶" if self._collapsed else "▼")
        # NO HEIGHT OF ITS OWN. Open with no chart the page line is empty and
        # takes no room, so the triangle stays away rather than add a line;
        # folded, it is always there, or the frames could not come back.
        shown = self._available and (self._has_chart or self._collapsed)
        self.triangle.setVisible(shown)
        if self.group is not None:
            self.group.setVisible(shown)
        if self.corner is not None:
            self.corner.setVisible(shown)
            self.corner.update()
        kind, n = self._verdict
        text = ""
        if self._collapsed and self._available:
            if kind == "warnings":
                text = (tr("1 warning") if n == 1
                        else tr("{n} warnings").format(n=n))
                set_ink(self.status, "#e0564b",
                        " font-size: 12px; font-weight: 700;", level="main")
            elif kind == "ok":
                text = tr("Margins: OK")
                set_ink(self.status, "#4fc27a",
                        " font-size: 12px; font-weight: 700;", level="main")
        self.status.set_full_text(text)
        self.status.setVisible(bool(text))
        if self.badge is not None:
            self.status.setVisible(False)
            if text and self.corner.isVisible():
                self.badge.show_verdict(kind, n, text)
            else:
                self.badge.setVisible(False)
            pv = self.corner.parentWidget()
            if pv is not None and hasattr(pv, "_place_corner_extras"):
                pv._place_corner_extras()
        if self.group is not None:
            self.group.adjustSize()


# ---------------------------------------------------------------------------
# PROTOTYPES for the owner's choice (2026-11-14): A = a separate group at the
# far left of the page line, B = a round button in the preview's bottom-right
# corner with a badge. Only the chosen one stays.
# ---------------------------------------------------------------------------
from PyQt6.QtWidgets import QAbstractButton, QHBoxLayout, QWidget  # noqa: E402

PILL = 22
RING = 3


class FoldGroupA(QWidget):
    """A: triangle + short label + status, one group at the row's left end."""

    def __init__(self, fold: "PreviewDetailsFold", parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(fold.triangle)
        self.label = QLabel(tr("Details"), self)
        self.label.setStyleSheet(_triangle_qss())
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label.mousePressEvent = self._label_click      # noqa: N815
        self._fold = fold
        row.addWidget(self.label)
        row.addSpacing(8)
        row.addWidget(fold.status)
        fold.status.setSizePolicy(QSizePolicy.Policy.Preferred,
                                  QSizePolicy.Policy.Fixed)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _label_click(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._fold.toggle()


class CornerFoldB(QAbstractButton):
    """B: a round button like the preview's top-right chip, bottom right,
    with a small badge on its left while folded."""

    def __init__(self, fold: "PreviewDetailsFold", parent=None) -> None:
        super().__init__(parent)
        self._fold = fold
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(fold.toggle)
        self._colours = ("#f7f5f2", "#2e2c29", "#4dd0e1", "#d0ccc6")
        self.setFixedSize(PILL + 2 * RING, PILL + 2 * RING)

    def set_colours(self, bg, ink, ring, edge) -> None:
        self._colours = (bg, ink, ring, edge)
        self.update()

    def paintEvent(self, _e) -> None:            # noqa: N802
        bg, ink, ring, edge = (QColor(c) for c in self._colours)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(RING, RING, PILL, PILL)
        if self.hasFocus():
            pen = QPen(ring); pen.setWidthF(2.0)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(r.adjusted(-1.5, -1.5, 1.5, 1.5))
        pen = QPen(edge); pen.setWidthF(1.0)
        p.setPen(pen); p.setBrush(bg)
        p.drawEllipse(r.adjusted(0.5, 0.5, -0.5, -0.5))
        # a chevron: down = hide the boxes below, up = show them again
        from PyQt6.QtGui import QPainterPath
        c = r.center()
        path = QPainterPath()
        if self._fold.is_collapsed():
            path.moveTo(c.x() - 5, c.y() + 2.5); path.lineTo(c.x(), c.y() - 2.5)
            path.lineTo(c.x() + 5, c.y() + 2.5)
        else:
            path.moveTo(c.x() - 5, c.y() - 2.5); path.lineTo(c.x(), c.y() + 2.5)
            path.lineTo(c.x() + 5, c.y() - 2.5)
        pen = QPen(ink); pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()


class BadgeB(QLabel):
    """B's badge: a green tick or a red count; the words in its tooltip."""

    def __init__(self, fold: "PreviewDetailsFold", parent=None) -> None:
        super().__init__(parent)
        self._fold = fold
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(PILL - 4)

    def show_verdict(self, kind: str, n: int, text: str) -> None:
        if kind == "warnings":
            self.setText(f"⚠ {n}")
            bg = "#e0564b"
        elif kind == "ok":
            self.setText("✓")
            bg = "#3fa66a"
        else:
            self.setVisible(False)
            return
        self.setStyleSheet(f"background: {bg}; color: white; font-weight: 700;"
                           f" font-size: 11px; border-radius: {(PILL - 4) // 2}px;"
                           " padding: 0 7px;")
        self.setToolTip(text)
        self.adjustSize()
        self.setVisible(True)

    def mousePressEvent(self, event) -> None:     # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._fold.set_collapsed(False, emit=True)
