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

        #: An OPTICAL offset for the drawn ⓘ, in device-independent pixels.
        #: See :meth:`set_nudge` — and note that it grows the pixmap rather than
        #: shifting inside it, because the circle nearly fills its own box.
        self._nudge: "tuple[float, float]" = (0.0, 0.0)
        self.setObjectName("tooltip_btn")
        self.setToolTip(title + "\n\n" + tr("Click for details"))
        self.setFixedSize(QSize(_ICON_SIZE + 4, _ICON_SIZE + 4))
        self._explicitly_disabled = False
        self._set_icon()
        self.clicked.connect(self._show_dialog)
        # NO LOG LINE HERE. One DEBUG line per widget CONSTRUCTION, and this app
        # builds hundreds: measured at 99,751 of 170,000 lines -- 58.7 % of the
        # user's entire 30 MB rotating budget -- spent recording that a help
        # icon exists. It has never told anyone anything, and it was pushing
        # the lines that DO diagnose faults out of the rotation. Deleting it
        # roughly triples how far back a user's log reaches, which is what the
        # Bluetooth diagnosis depends on.

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

    def set_nudge(self, dx: float, dy: float) -> None:
        """Shift the drawn ⓘ inside its button, without moving the button.

        Used where an ⓘ has to travel with the control it explains rather than
        keep even spacing of its own (#130, Basti 2026-08-03).

        **The first attempt at this translated the painter inside a fixed
        pixmap, and Basti saw the result at once: the icons looked cut off.**
        The circle is drawn with a margin of about 7 % of its pixmap — roughly
        two physical pixels at 2× — so any offset eats its edge. So the pixmap
        grows by the offset instead and the circle is drawn off-centre inside
        it: same visual shift, nothing clipped.
        """
        if (dx, dy) == self._nudge:
            return
        self._nudge = (float(dx), float(dy))
        self._set_icon()

    def set_color(self, color: str) -> None:
        """Override the ⓘ icon colour (e.g. to match a dialog's own accent)."""
        self._color_override = color
        self._set_icon()

    def set_appearance(self, mode: str) -> None:
        """Redraw the ⓘ for a new appearance.

        The colour is resolved in :meth:`_set_icon`, at draw time — so a button
        built while Dark was on screen keeps Dark's value until something asks
        it to draw again. `MainWindow.apply_theme` broadcasts to every
        descendant that has this method, which is what makes a live theme
        switch reach the ~600 ⓘ icons in the app rather than only the ones
        whose tab happens to be restyled afterwards.

        The redraw is a dict lookup after the first icon of each colour
        (`_ICON_CACHE`), so this is cheap even at that count.
        """
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        self._set_icon()

    def _set_icon(self) -> None:
        # ONE ACCENT UNDER NEUTRAL, whatever set this one. The ⓘ ring is the
        # most repeated accent surface in the app — every parameter row, every
        # dialog masthead — and it arrives here from three directions: the
        # per-tab class ACCENT, a per-instance `color=`, and Preferences'
        # indicator override. Collapsing it at the one place all three pass
        # through means no caller has to know about a third appearance.
        # `accent_for` returns its argument unchanged in Light and Dark.
        from ui.theme import accent_for
        color = getattr(self, "_color_override", None) or self.__class__.ACCENT
        color = accent_for(color, getattr(self, "_mode", None))
        # THE OWNER, ON THE SHIPPED BUILD: *"in preferences neutral mode the
        # tooltip icons are too light. the color they currently have would be
        # good for a disabled state or something."* He was looking at
        # `#d0d0d0` — the DARK theme's indicator, handed to every ⓘ in
        # Preferences. Measured on this theme's window it is **1.19:1**, which
        # is fainter than DISABLED itself (**1.35:1**): not merely a poor
        # enabled value, a value *below* the one the theme reserves for
        # controls that do not work. Rule 3 says low contrast means "disabled"
        # and nothing else, so an ⓘ that works is ACTION, at **14.69:1**.
        #
        # And the two do NOT want swapping. A ⓘ is a ring and a glyph — it has
        # no fill to drop and no edge to dash, so the handoff's disabled SHAPE
        # does not apply to it; its disabled state is Qt fading this same icon
        # (QIcon.Mode.Disabled), which is one mechanism in all three
        # appearances and needs no value of its own.
        self.setIcon(self._draw_icon(QColor(color)))
        # The icon is as wide/tall as the nudge made it; Qt centres it in the
        # button, so the extra room on one side is what produces the shift.
        gx, gy = self._grow()
        self.setIconSize(QSize(_ICON_SIZE + gx, _ICON_SIZE + gy))

    def _grow(self) -> "tuple[int, int]":
        """How much bigger the pixmap has to be to hold a nudged circle."""
        import math
        return (2 * math.ceil(abs(self._nudge[0])),
                2 * math.ceil(abs(self._nudge[1])))

    def _draw_icon(self, color: QColor) -> QIcon:
        dpr  = QGuiApplication.primaryScreen().devicePixelRatio()
        # The nudge changes what the pixmap looks like AND how big it is, so it
        # belongs in the key — otherwise the first ⓘ drawn in a colour hands its
        # icon to every later one and the offset silently disappears.
        key  = (color.rgba(), round(dpr, 4), self._nudge)
        cached = TooltipButton._ICON_CACHE.get(key)
        if cached is not None:
            return cached
        phys = round(_ICON_SIZE * dpr)
        gx, gy = self._grow()
        w_ph, h_ph = phys + round(gx * dpr), phys + round(gy * dpr)
        px   = QPixmap(w_ph, h_ph)
        px.fill(Qt.GlobalColor.transparent)

        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Centre the circle in the grown pixmap, then move it by the nudge. The
        # growth is twice the nudge, so the circle always lands fully inside.
        ox = (w_ph - phys) / 2 + self._nudge[0] * dpr
        oy = (h_ph - phys) / 2 + self._nudge[1] * dpr

        pen = QPen(color, max(1.0, phys * 0.10))
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        margin = int(phys * 0.07)
        p.drawEllipse(int(ox) + margin, int(oy) + margin,
                      phys - 2 * margin, phys - 2 * margin)

        # Italic "i" glyph
        font = QFont()
        font.setFamilies(["Georgia", "Times New Roman", "serif"])
        font.setItalic(True)
        font.setBold(True)
        font.setPixelSize(max(8, int(phys * 0.54)))
        p.setFont(font)
        p.setPen(color)
        p.drawText(
            QRect(int(ox), int(oy), phys, int(phys * 1.05)),
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
            # The WIDTH matters too, or the dialog can only ever be as wide as
            # its caller's `min_width` and a body written wider than that shows
            # a strip of empty frame beside it (Knut, beta.144). The content
            # sets its own minimum width when it has been hand-wrapped; passing
            # that up — with the frame and the scrollbar that will sit next to
            # it — lets `adjustSize()` do the arithmetic instead of guessing at
            # the chrome, which is what got it four pixels wrong on macOS.
            wd = max(base.width(),
                     w.minimumWidth() + 2 * self.frameWidth()
                     + self.verticalScrollBar().sizeHint().width())
            return QSize(wd, h)
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

        # WIDEN THE WINDOW TO THE TEXT IT ALREADY HAS.
        #
        # A help body is written as prose and hand-wrapped in the source, so its
        # lines have the width its author chose. Nothing carried that width to
        # the dialog, so a card could only ever be as wide as its caller's
        # `min_width`: too narrow and every line re-wrapped, leaving single words
        # stranded; too wide and a strip of empty frame sat beside the text.
        # Knut, beta.144: *"Help text for 'Patch consistency threshold' uses only
        # three quarters of the window width."*
        #
        # Asking the body for a minimum width is all it takes — `_BodyScrollArea`
        # passes it up and `adjustSize()` works out the frame and the scrollbar
        # itself, which is the part a hand-computed answer got wrong.
        _wrapped_w = self._hand_wrapped_width(text, body) if not _rich else 0
        if _wrapped_w:
            text.setMinimumWidth(_wrapped_w)

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

    #: A hand-wrapped help body runs to about 60-70 characters a line. Past this
    #: the body is free-flowing prose that was never wrapped by hand, and its
    #: "longest line" is a whole paragraph — a useless measurement, and one that
    #: would stretch every such card to the maximum width. Those keep the width
    #: their caller asked for.
    _MAX_MEASURED_BODY_PX = 700

    @staticmethod
    def _hand_wrapped_width(label: QLabel, body: str) -> int:
        """Width the body's longest written line needs, or 0 to leave it alone.

        0 for anything that was never hand-wrapped and for anything wrapped
        wider than a help card should be — those keep the width their caller
        asked for.
        """
        lines = [ln for ln in body.split("\n") if ln.strip()]
        if len(lines) < 2:
            return 0
        fm = label.fontMetrics()
        widest = max(fm.horizontalAdvance(ln) for ln in lines)
        # +2: `horizontalAdvance` is the pen advance, and a glyph's rightmost
        # ink can sit a hair beyond it. Two pixels keeps the last word off the
        # wrap point without opening a visible gap.
        return widest + 2 if widest <= _InfoDialog._MAX_MEASURED_BODY_PX else 0


InfoDialog = _InfoDialog  # public alias for use outside this module
