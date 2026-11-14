"""The fold for "Measured from Preview" and "Chart layout information".

Basti, 2026-11-14: *"in create chart tab can you make measured from preview
and chart layout information section collapsible? i think one button (or
triangle) should collapse both at once. i want a quick way to show and hide
it"*, then *"the purpose of this is to save space"*, and his choice among
three photographed placements: *"overall option b"*.

A small round button in the chart preview's bottom right corner, in the style
of the round button at its top right (`ui.print_view_chip`). It floats over
the preview, so it takes no line of its own: open, the tab is exactly as
before; folded, both frames go and the preview takes their whole height.
While they are folded a small badge beside the button repeats their verdict,
a green tick for "Margins: OK" or the warning count in red, with the words in
its tooltip, live after a preview update or a Generate; a click on it opens
the frames again. A new warning does not open them: the person chose to hide
them.

The open / closed state is a view choice of the window, like the warning fold
inside "Measured from Preview" (`margin_warnings_expanded`): stored in the
app's settings (`preview_details_collapsed`), the same in Guided and Manual,
never part of a target or a preset (per_target_settings §1.1).
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QAbstractButton, QLabel

from core.i18n import tr

#: The round button's diameter and the room left round it for the focus
#: ring: the top-right chip's own sizes (`print_view_chip.PILL_H`, `RING`).
PILL = 22
RING = 3

#: The badge's colours. White on them is 5.4:1 (red) and 5.1:1 (green), so a
#: bold digit or tick reads on any appearance; the badge brings its own
#: ground, so the preview's grey (light) or near-black (dark) never decides
#: whether it is seen. Neutral, which carries no hues, gets its dark ink and
#: says it in the glyph (⚠ or ✓) and the tooltip.
BADGE_RED = "#c0392b"
BADGE_GREEN = "#2e7d4f"


def fold_tooltip() -> str:
    return tr(
        "Hide or show the measurements and the chart layout information: the "
        "two boxes under the chart preview, “Measured from Preview” and "
        "“Chart layout information”, both at once.\n\n"
        "Hidden, the chart preview gets their room. A small badge beside this "
        "button then still tells you how the chart's margins look: a green "
        "tick when everything fits, or the number of warnings in red. Point "
        "at the badge to read it, and click this button or the badge (or "
        "press Space while the button is selected) to see the boxes again.\n\n"
        "ChromIQ remembers your choice, also after a restart.")


def verdict_words(kind: str, n: int) -> str:
    """The badge's tooltip: what the hidden frames say, in words."""
    if kind == "warnings":
        return (tr("1 warning: click to show the details") if n == 1
                else tr("{n} warnings: click to show the details").format(n=n))
    if kind == "ok":
        return tr("Margins: OK")
    return ""


class CornerFoldButton(QAbstractButton):
    """The round button: a chevron down hides the frames below, up shows
    them again. Clicked by mouse, Space or Return; takes the keyboard."""

    def __init__(self, fold: "PreviewDetailsFold", parent=None) -> None:
        super().__init__(parent)
        self._fold = fold
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(PILL + 2 * RING, PILL + 2 * RING)
        self._colours = ("#f7f5f2", "#2e2c29", "#4dd0e1", "#d0ccc6")

    def set_colours(self, ground: str, ink: str, ring: str, edge: str) -> None:
        """The top-right chip's own four colours for the appearance on
        screen (`TiffPreview._style_corner_extras`)."""
        self._colours = (ground, ink, ring, edge)
        self.update()

    def keyPressEvent(self, event) -> None:       # noqa: N802 (Qt override)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:         # noqa: N802 (Qt override)
        ground, ink, ring, edge = (QColor(c) for c in self._colours)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(RING, RING, PILL, PILL)
        if self.hasFocus():
            pen = QPen(ring)
            pen.setWidthF(2.0)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(r.adjusted(-1.5, -1.5, 1.5, 1.5))
        pen = QPen(edge)
        pen.setWidthF(1.0)
        p.setPen(pen)
        p.setBrush(ground)
        p.drawEllipse(r.adjusted(0.5, 0.5, -0.5, -0.5))
        c = r.center()
        path = QPainterPath()
        if self._fold.is_collapsed():                  # up: show them again
            path.moveTo(c.x() - 5, c.y() + 2.5)
            path.lineTo(c.x(), c.y() - 2.5)
            path.lineTo(c.x() + 5, c.y() + 2.5)
        else:                                          # down: hide them
            path.moveTo(c.x() - 5, c.y() - 2.5)
            path.lineTo(c.x(), c.y() + 2.5)
            path.lineTo(c.x() + 5, c.y() - 2.5)
        pen = QPen(ink)
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()


class VerdictBadge(QLabel):
    """The folded verdict: a tick or "⚠ n" on a solid ground, the words in
    its tooltip; a click opens the frames."""

    def __init__(self, fold: "PreviewDetailsFold", parent=None) -> None:
        super().__init__(parent)
        self._fold = fold
        self._words = ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(PILL - 2)
        self.setVisible(False)

    def words(self) -> str:
        return self._words

    def show_verdict(self, kind: str, n: int) -> None:
        from ui.theme import active_mode
        words = verdict_words(kind, n)
        self._words = words
        if not words:
            self.setVisible(False)
            return
        if kind == "warnings":
            glyph, ground = f"⚠ {n}", BADGE_RED
        else:
            glyph, ground = "✓", BADGE_GREEN
        if active_mode() == "neutral":
            from ui.neutral_styles import NM_TEXT_MAIN
            ground = NM_TEXT_MAIN
        self.setText(glyph)
        self.setToolTip(words)
        self.setAccessibleName(words)
        self.setStyleSheet(
            f"QLabel {{ background: {ground}; color: #ffffff;"
            f" font-weight: 700; font-size: 12px;"
            f" border-radius: {(PILL - 2) // 2}px; padding: 0 8px; }}")
        self.adjustSize()
        self.setVisible(True)

    def mousePressEvent(self, event) -> None:     # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._fold.set_collapsed(False, emit=True)
            event.accept()
            return
        super().mousePressEvent(event)


class PreviewDetailsFold(QObject):
    """The button and the badge, floated in the preview's corner with
    `TiffPreview.add_corner_extras`; the owner hides the frames on
    `toggled`."""

    #: True when the person has just folded the frames away.
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None, *, collapsed: bool = False) -> None:
        super().__init__(parent)
        self._collapsed = bool(collapsed)
        self._verdict: "tuple[str, int]" = ("none", 0)
        self._available = True
        self._has_chart = False
        self.button = CornerFoldButton(self)
        self.badge = VerdictBadge(self)
        self.button.setToolTip(fold_tooltip())
        self.button.setAccessibleName(tr("Measured from Preview"))
        self.button.clicked.connect(self.toggle)
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

    def set_verdict(self, kind: str, count: int = 0) -> None:
        """What the frames say, as `MarginInspectorPanel.verdict` gives it."""
        self._verdict = (kind, int(count))
        self._render()

    def set_available(self, available: bool) -> None:
        """False while Preferences hides both frames: nothing to fold."""
        self._available = bool(available)
        self._render()

    def set_has_chart(self, has: bool) -> None:
        """Whether the preview shows a chart."""
        self._has_chart = bool(has)
        self._render()

    def status_text(self) -> str:
        """The badge's words while it is shown, else ""."""
        return self.badge.words() if self.badge.isVisibleTo(
            self.badge.parentWidget() or self.badge) and not \
            self.badge.isHidden() else ""

    # -- drawing -------------------------------------------------------------
    def _render(self) -> None:
        # Open with no chart there is nothing to fold away from; folded, the
        # button is always there, or the frames could not come back.
        shown = self._available and (self._has_chart or self._collapsed)
        self.button.setVisible(shown)
        self.button.update()
        kind, n = self._verdict
        if self._collapsed and shown:
            self.badge.show_verdict(kind, n)
        else:
            self.badge._words = ""
            self.badge.setVisible(False)
        pv = self.button.parentWidget()
        place = getattr(pv, "_place_corner_extras", None)
        if callable(place):
            place()
