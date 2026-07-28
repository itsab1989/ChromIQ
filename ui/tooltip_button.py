"""Clickable ⓘ icon button that opens a detailed info dialog.

The icon is drawn in code using the active tab's accent colour (``TooltipButton.ACCENT``),
set by MainWindow whenever the active tab changes.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QRect, QSize, Qt
from PyQt6.QtGui import (
    QColor, QFont, QGuiApplication, QIcon, QPainter, QPalette, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QScrollArea,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.i18n import tr

log = get_logger(__name__)

_ICON_SIZE = 18  # logical px


class TooltipButton(QToolButton):
    """Small ⓘ icon button that opens a modal info dialog on click."""

    # Set by MainWindow._on_tab_changed() each time the tab switches.
    ACCENT: str = "#1FB7C7"

    # The ⓘ glyph is fully determined by its colour and the screen's device
    # pixel ratio (the size and font are constants), so identical-colour buttons
    # render pixel-for-pixel the same icon. Cache the finished QIcon per
    # (colour, dpr): at startup ~600 tooltip buttons share a handful of accent
    # colours, so all but the first draw of each become a dict lookup instead of
    # a QPainter render (~90 ms off app start). QIcon is immutable, so sharing
    # one instance across buttons is safe.
    _ICON_CACHE: "dict[tuple, QIcon]" = {}

    def __init__(
        self,
        title: str,
        body: str,
        parent: QWidget | None = None,
        min_width: int = 420,
        color: str | None = None,
    ) -> None:
        super().__init__(parent)
        # A help icon: never take keyboard focus, so the space bar can't pop its
        # tooltip just because a tab handed it the initial focus (Knut).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._title     = title
        self._body      = body.strip()
        self._min_width = min_width
        # Per-instance icon colour. When None the shared tab ACCENT is used; the
        # Tools dialogs/editor set this to keep their own accent (e.g. magenta,
        # or the settings-window light/dark indicator). See _set_icon.
        if color is not None:
            self._color_override = color

        self.setObjectName("tooltip_btn")
        self.setToolTip(title + "\n\n" + tr("Click for details"))
        self.setFixedSize(QSize(_ICON_SIZE + 4, _ICON_SIZE + 4))
        self._explicitly_disabled = False
        self._set_icon()
        self.clicked.connect(self._show_dialog)
        log.debug("TooltipButton created: %s", title)

    # ------------------------------------------------------------------
    def set_content(self, title: str, body: str) -> None:
        """Replace the dialog title/body (e.g. to make a tooltip describe only
        the option that's available for the current selection)."""
        self._title = title
        self._body = body.strip()
        self.setToolTip(title + "\n\n" + tr("Click for details"))

    def setEnabled(self, enabled: bool) -> None:
        self._explicitly_disabled = not enabled
        super().setEnabled(enabled)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if (event.type() == QEvent.Type.EnabledChange
                and not self.isEnabled()
                and not self._explicitly_disabled):
            super().setEnabled(True)

    def set_color(self, color: str) -> None:
        """Override the ⓘ icon colour (e.g. to match a dialog's own accent)."""
        self._color_override = color
        self._set_icon()

    def _set_icon(self) -> None:
        color = getattr(self, "_color_override", None) or self.__class__.ACCENT
        self.setIcon(self._draw_icon(QColor(color)))
        self.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))

    def _draw_icon(self, color: QColor) -> QIcon:
        dpr  = QGuiApplication.primaryScreen().devicePixelRatio()
        key  = (color.rgba(), round(dpr, 4))
        cached = TooltipButton._ICON_CACHE.get(key)
        if cached is not None:
            return cached
        phys = round(_ICON_SIZE * dpr)
        px   = QPixmap(phys, phys)
        px.fill(Qt.GlobalColor.transparent)

        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(color, max(1.0, phys * 0.10))
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        margin = int(phys * 0.07)
        p.drawEllipse(margin, margin, phys - 2 * margin, phys - 2 * margin)

        # Italic "i" glyph
        font = QFont()
        font.setFamilies(["Georgia", "Times New Roman", "serif"])
        font.setItalic(True)
        font.setBold(True)
        font.setPixelSize(max(8, int(phys * 0.54)))
        p.setFont(font)
        p.setPen(color)
        p.drawText(
            QRect(0, 0, phys, int(phys * 1.05)),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            "i",
        )
        p.end()
        px.setDevicePixelRatio(dpr)
        icon = QIcon(px)
        TooltipButton._ICON_CACHE[key] = icon
        return icon

    # ------------------------------------------------------------------
    def _show_dialog(self) -> None:
        log.debug("Tooltip dialog opened: %s", self._title)
        win = self.window()
        dlg = _InfoDialog(self._title, self._body, win, self._min_width)
        dlg.exec()
        # macOS: when the ⓘ button lives in a dialog that is itself a child of
        # another dialog (e.g. the editor's "3D distribution…" cube, or the New
        # Chart window), closing this modal child can drop the owning window
        # *behind* the main window. Re-raise it so it stays in front (#66).
        if win is not None:
            win.raise_()
            win.activateWindow()


class _BodyScrollArea(QScrollArea):
    """Scroll area that advertises its content's full preferred height as its
    own size hint.

    This lets the dialog's ``adjustSize()`` grow tall enough to show the whole
    body when it fits. Only once the dialog hits its screen-height cap does the
    scroll area shrink below that and reveal a scrollbar — so content is never
    clipped, no matter how long it is or how small the display."""

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        w = self.widget()
        if w is not None:
            h = max(w.sizeHint().height(), w.minimumHeight()) + 2 * self.frameWidth()
            return QSize(base.width(), h)
        return base


class _InfoDialog(QDialog):
    def __init__(
        self,
        title: str,
        body:  str,
        parent: QWidget | None,
        min_width: int = 420,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)
        self.setMaximumWidth(max(min_width + 160, 720))
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        # Use the live applied palette's text colour — the same colour every
        # other dialog/popup uses — rather than re-resolving the appearance
        # setting (which can be stale during a live theme preview and paint
        # dark text on a dark background).
        text_color = self.palette().color(QPalette.ColorRole.WindowText).name()

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        # Heading stays pinned above the scroll region so it never scrolls away.
        heading = QLabel(title, self)
        heading.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {text_color};")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        # Body lives inside a scroll area: the dialog grows to show it in full
        # when it fits, and scrolls instead of overflowing the screen when it
        # doesn't.
        # A rich-text body does NOT inherit the label's colour: the table cells
        # come out in the default black, which is unreadable on the dark theme
        # (and the border invisible on the light one). So the colour is written
        # into the HTML, from the same value the rest of the dialog uses — which
        # keeps it correct in both themes.
        _rich = "<table" in body
        if _rich:
            body = body.replace("<table ",
                                f'<table bordercolor="{text_color}" ')
        text = QLabel(body, self)
        text.setWordWrap(True)
        text.setStyleSheet(f"color: {text_color};")
        if _rich:
            # A style sheet colours a PLAIN label; rich text takes its default
            # colour from the palette instead, so a table came out in black on
            # the dark theme — unreadable. Setting the palette is what actually
            # reaches the cells.
            from PyQt6.QtGui import QColor
            _pal = text.palette()
            for _role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text):
                _pal.setColor(_role, QColor(text_color))
            text.setPalette(_pal)
        # Plain text by default — help bodies are written as prose and a stray
        # "<" must never be swallowed as markup. A body that carries a real
        # table is the exception: Knut asked for the windows-and-sounds summary
        # to be "actually shown as a table" (#131, 2026-07-27), and a
        # proportional font cannot align columns any other way.
        text.setTextFormat(Qt.TextFormat.RichText if _rich
                           else Qt.TextFormat.PlainText)
        text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll = _BodyScrollArea(self)
        scroll.setWidget(text)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll.viewport().setStyleSheet("background: transparent;")
        layout.addWidget(scroll, 1)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        bb.rejected.connect(self.accept)
        layout.addWidget(bb)

        self.adjustSize()  # settle the width (clamped between min/max width) first

        # QLabel word-wrap pitfall: a wrapping label's sizeHint height assumes a
        # wider layout than it actually gets, so at the dialog's constrained
        # width a long paragraph wraps to more lines than budgeted and the body
        # is clipped top and bottom. Measure each wrapping label's true height at
        # the final content width and size the dialog from those numbers. (We
        # can't trust the labels' current geometry — before the dialog is shown
        # the layout hasn't distributed it yet.)
        margins = layout.contentsMargins()
        avail = self.width() - margins.left() - margins.right()

        heading_h = max(0, heading.heightForWidth(avail))
        heading.setMinimumHeight(heading_h)

        # The body wraps inside the scroll viewport; reserve room for a vertical
        # scrollbar so the text still fits horizontally if one ever appears.
        sb = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        body_h = max(0, text.heightForWidth(max(1, avail - sb)))
        text.setMinimumHeight(body_h)

        # Resize explicitly to the full height the content wants — adjustSize()
        # can't be used here because it silently caps a dialog to ~2/3 of the
        # screen, which would clip a long body even when the screen has room.
        # Cap at 90 % of the available screen instead; past that the scroll area
        # takes over so the body is never clipped or pushed off-screen.
        chrome = (margins.top() + margins.bottom()
                  + heading_h
                  + bb.sizeHint().height()
                  + 2 * layout.spacing())
        desired = chrome + body_h
        screen = self.screen() or QGuiApplication.primaryScreen()
        cap = (int(screen.availableGeometry().height() * 0.9)
               if screen is not None else desired)
        self.setMaximumHeight(cap)
        self.resize(self.width(), min(desired, cap))


InfoDialog = _InfoDialog  # public alias for use outside this module
