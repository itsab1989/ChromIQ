"""Gradient wash overlay — paints a colour-to-transparent strip at the top of a tab pane."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import QWidget

_HEIGHT = 50  # px
_ALPHA  = 15  # ≈ 6 % opacity at the top


class GradientOverlay(QWidget):
    """Transparent overlay that draws a vertical gradient over the top 50 px.

    Passes all mouse/keyboard events through to siblings beneath it.
    Install one on each tab widget after the tab widget is fully built.
    """

    def __init__(self, color: str, parent: QWidget,
                 alpha: int = _ALPHA, height: int = _HEIGHT,
                 on_top: bool = True) -> None:
        super().__init__(parent)
        #: The hue this wash was BUILT with — one of the five tab accents. Kept
        #: so :meth:`set_appearance` can go back to it: the wash is created once
        #: per tab at construction and never rebuilt, so folding the appearance
        #: into `_color` here would strand it on whatever theme was on screen
        #: when the window was made.
        self._base_color = color
        self._color = QColor(self._resolved(color))
        self._alpha = alpha
        self._height = height
        # When True the wash is raised above the content (subtle tint over it,
        # as on the main-window tabs). When False it sits just above the parent's
        # background but below the content, so opaque widgets (e.g. the editor's
        # New chart / Load .ti2 / undo / redo buttons in the headline row) paint
        # over it while the transparent headline text still shows it behind.
        self._on_top = on_top
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        parent.installEventFilter(self)
        self._fit()
        self._restack()

    # ------------------------------------------------------------------

    @staticmethod
    def _resolved(color: str) -> str:
        """The colour this wash actually paints under the live appearance.

        In Neutral there is ONE accent value, so a wash cannot be a tab's hue:
        this one measured **28 % of its own area** in the scan — the densest
        single offender in the app, because a gradient spreads its hue over
        every pixel it touches instead of a 3px strip. The gesture stays; the
        hue does not. ACTION at the same alpha darkens the top of the pane by
        the same amount, which is the handoff's rule 1 (nothing is ever lighter
        than its ground) and reads as the same wash.
        """
        from ui import index_rule
        if index_rule.use_index_rule():
            from ui import neutral_styles
            return neutral_styles.NM_ACTION
        return color

    def set_appearance(self, _mode: str) -> None:
        """Re-resolve the wash for a new appearance.

        `MainWindow.apply_theme` broadcasts to every descendant with this
        method, and a dialog's wash is re-created with the dialog, so between
        them every wash in the app follows a theme switch.
        """
        new = QColor(self._resolved(self._base_color))
        if new != self._color:
            self._color = new
            self.update()

    def _restack(self) -> None:
        if self._on_top:
            self.raise_()
        else:
            self.lower()

    def _fit(self) -> None:
        p = self.parent()
        if p:
            self.setGeometry(0, 0, p.width(), self._height)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.parent():
            t = event.type()
            if t == QEvent.Type.Resize:
                self._fit()
                self._restack()
            elif t == QEvent.Type.Show:
                self._restack()
        return False

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, 0, self._height)
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        # Both stops use the same hue — avoids the black fringe from
        # pre-multiplied alpha interpolation toward QColor(0,0,0,0).
        n = 8
        for i in range(n + 1):
            t = i / n
            a = round(self._alpha * (1 - t) ** 2)
            grad.setColorAt(t, QColor(r, g, b, a))
        painter.fillRect(self.rect(), grad)
        painter.end()

    def showEvent(self, event) -> None:  # type: ignore[override]
        self._restack()
