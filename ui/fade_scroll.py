"""QScrollArea with gradient fade-to-transparent at the top and bottom edges.

The fade colour follows the current ChromIQ theme — set via the standard
``set_appearance(mode)`` broadcast wired in ``MainWindow.apply_theme()``. A
``surface`` keyword chooses between common backdrop colours (tab pane,
dialog body) so callers don't have to thread theme constants by hand.

Typical use:

    scroll = FadeScrollArea(parent)                # default "panel" surface
    scroll = FadeScrollArea(parent, surface="dialog")
    scroll.set_fade_color("#1a1a1a")               # explicit colour override
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPaintEvent
from PyQt6.QtWidgets import QAbstractScrollArea, QScrollArea, QWidget

from ui import neutral_styles


# Per-surface backdrop colours, keyed by appearance.
#
# THIS WAS A (dark, light) PAIR unpacked as `dark, light = _SURFACES[...]` and
# picked with `light if self._mode == "light" else dark`. A tuple of two has
# room for two answers, so a third appearance faded a light-grey panel to
# #181818 — a black band across the top and bottom of every scroll area in the
# app. A mapping per appearance has no such ceiling.
_SURFACES: dict[str, dict[str, str]] = {
    # Tab pane / generic content area. Light mode targets the window tint
    # (#eeece8) — the same colour as the welcome dialog's fade, which reads
    # seamless. Fading to a brighter surface tint left a faint band at the
    # fade edge in tabs that wrap group-box content. Neutral fades to its own
    # panel value, which IS the pane colour, so there is no band to avoid.
    "panel":   {"dark": "#181818", "light": "#eeece8",
                "neutral": neutral_styles.NM_BG_PANEL},
    # QDialog body — matches WelcomeDialog / SettingsDialog backgrounds
    "dialog":  {"dark": "#181818", "light": "#eeece8",
                "neutral": neutral_styles.NM_BG_WINDOW},
    # GroupBox / surface tint
    "surface": {"dark": "#181818", "light": "#f7f4ef",
                "neutral": neutral_styles.NM_BG_SURFACE},
}


class _ScrollFade(QWidget):
    """Vertical gradient strip — opaque on the active edge, transparent on
    the inner edge. Overlay child of :class:`FadeScrollArea`."""

    def __init__(self, position: str, parent: QWidget) -> None:
        super().__init__(parent)
        self._position = position  # "top" | "bottom"
        self._color = QColor("#181818")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _ev: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        opaque = QColor(self._color); opaque.setAlpha(255)
        clear  = QColor(self._color); clear.setAlpha(0)
        if self._position == "top":
            gradient.setColorAt(0.0, opaque)
            gradient.setColorAt(1.0, clear)
        else:
            gradient.setColorAt(0.0, clear)
            gradient.setColorAt(1.0, opaque)
        p.fillRect(self.rect(), gradient)
        p.end()


class FadeScrollArea(QScrollArea):
    """QScrollArea whose top/bottom edges fade to the surface colour."""

    FADE_H = 24

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        surface: str = "panel",
    ) -> None:
        super().__init__(parent)
        self._surface: str | None = surface if surface in _SURFACES else "panel"
        self._mode = "dark"
        self._top_fade = _ScrollFade("top", self)
        self._bot_fade = _ScrollFade("bottom", self)
        self.verticalScrollBar().valueChanged.connect(self._refresh_fade)
        # A BOUND METHOD, NEVER A LAMBDA THAT CAPTURES `self`. See
        # `_on_range_changed` — this line used to segfault the process.
        self.verticalScrollBar().rangeChanged.connect(self._on_range_changed)
        self._refresh_color()

    def _on_range_changed(self, _minimum: int, _maximum: int) -> None:
        """`rangeChanged(int, int)` -> the no-argument refresh.

        THIS EXISTS ONLY SO THAT THE SLOT IS A BOUND METHOD. It was

            self.verticalScrollBar().rangeChanged.connect(
                lambda _mn, _mx: self._refresh_fade())

        and that line crashed the process — SIGSEGV, `EXC_BAD_ACCESS ...
        address=0x20`, a `Py_INCREF` of a pointer read from NULL+0x20 inside
        `_PyEval_EvalFrameDefault` while PyQt6 was setting up the lambda's own
        frame (`PyQtSlotProxy::unislot` -> `PyQtSlot::invoke` ->
        `PyQtSlot::call` -> `_PyEval_Vector`).

        HOW IT WAS PINNED DOWN, because the shape of the evidence is the point.
        The crash needs `rangeChanged` to be emitted RE-ENTRANTLY: `main.py`
        installs `CompositeAppFilter`, whose `ButtonFontFilter` calls
        `relayout_around()` -> `layout.invalidate(); layout.activate()`
        synchronously from inside an application event filter, so
        `QScrollAreaPrivate::updateScrollBars()` runs inside itself and calls
        `QAbstractSlider::setRange` a second time. Four variants of this one
        line were then run against a standalone reproduction that faults on the
        eighth widget build, every time:

            connected as a self-capturing lambda   -> crash on build 8
            slot body emptied to `return None`     -> crash on build 8
            connected as a bound method            -> 52 builds, clean
            lambda capturing nothing               -> 52 builds, clean

        So it is not what the slot does (an empty body still crashes) and not
        the re-entrancy on its own (a bound method survives it). It is PyQt6
        6.11 calling a Python closure that captures the very widget whose child
        scroll bar owns the proxy holding that closure. A bound method is the
        pattern PyQt is built for: it keeps a WEAK reference to the receiver and
        lets Qt sever the connection with the receiver, instead of parking a
        Python closure in a C++ object on the other side of the cycle.

        The same crash reached the release gate as a phantom red in FOUR OF TEN
        measured runs — always in
        `tests/test_the_manual_panel_does_not_scroll_sideways.py`, because that
        is the only test file that installs the application event filter — and
        each time it took an unrelated test down with it, so the run came out
        red naming something that passes on its own.
        """
        self._refresh_fade()

    def set_appearance(self, mode: str) -> None:
        """Picked up automatically by MainWindow.apply_theme()'s broadcast."""
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        self._refresh_color()

    def set_fade_color(self, color: str) -> None:
        """Pin an explicit fade colour — overrides the surface preset."""
        self._surface = None
        self._top_fade.set_color(color)
        self._bot_fade.set_color(color)

    def _refresh_color(self) -> None:
        if self._surface is None:
            return  # explicit colour pinned via set_fade_color
        surfaces = _SURFACES[self._surface]
        color = surfaces.get(self._mode, surfaces["dark"])
        self._top_fade.set_color(color)
        self._bot_fade.set_color(color)

    def resizeEvent(self, ev) -> None:  # noqa: N802
        super().resizeEvent(ev)
        self._refresh_fade()

    def _refresh_fade(self) -> None:
        vw = self.viewport().width()
        self._top_fade.setGeometry(0, 0, vw, self.FADE_H)
        self._bot_fade.setGeometry(
            0, self.viewport().height() - self.FADE_H, vw, self.FADE_H
        )
        sb = self.verticalScrollBar()
        scrollable = sb.maximum() > sb.minimum()
        at_top = sb.value() <= sb.minimum()
        at_bot = sb.value() >= sb.maximum()
        self._top_fade.setVisible(scrollable and not at_top)
        self._bot_fade.setVisible(scrollable and not at_bot)
        self._top_fade.raise_()
        self._bot_fade.raise_()


class EdgeFades(QObject):
    """Attach the same top/bottom fade-to-surface gradient to *any* existing
    scroll area — a ``QTextBrowser``, ``QListWidget``, etc. — that already
    manages its own scrolling, without re-parenting it into a FadeScrollArea.

    The fades are overlaid on the area's viewport and follow the theme via
    :meth:`set_appearance` (call once with the current mode; dialogs rarely
    change theme while open). Keep the returned object alive."""

    FADE_H = FadeScrollArea.FADE_H

    def __init__(self, area: QAbstractScrollArea, *, surface: str = "dialog") -> None:
        super().__init__(area)
        self._area = area
        self._surface = surface if surface in _SURFACES else "dialog"
        self._mode = "dark"
        vp = area.viewport()
        self._top = _ScrollFade("top", vp)
        self._bot = _ScrollFade("bottom", vp)
        sb = area.verticalScrollBar()
        sb.valueChanged.connect(self._refresh)
        # A bound method, for the reason spelt out in
        # `FadeScrollArea._on_range_changed`: a lambda here that captures `self`
        # is what segfaulted the process.
        sb.rangeChanged.connect(self._on_range_changed)
        vp.installEventFilter(self)
        self._refresh_color()
        self._refresh()

    def _on_range_changed(self, _minimum: int, _maximum: int) -> None:
        """`rangeChanged(int, int)` -> the no-argument refresh, as a BOUND
        METHOD. See `FadeScrollArea._on_range_changed` for what a lambda here
        cost."""
        self._refresh()

    def set_appearance(self, mode: str) -> None:
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        self._refresh_color()

    def _refresh_color(self) -> None:
        surfaces = _SURFACES[self._surface]
        color = surfaces.get(self._mode, surfaces["dark"])
        self._top.set_color(color)
        self._bot.set_color(color)

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:  # noqa: N802
        if ev.type() == QEvent.Type.Resize:
            self._refresh()
        return False

    def _refresh(self) -> None:
        vp = self._area.viewport()
        w, h = vp.width(), vp.height()
        self._top.setGeometry(0, 0, w, self.FADE_H)
        self._bot.setGeometry(0, h - self.FADE_H, w, self.FADE_H)
        sb = self._area.verticalScrollBar()
        scrollable = sb.maximum() > sb.minimum()
        self._top.setVisible(scrollable and sb.value() > sb.minimum())
        self._bot.setVisible(scrollable and sb.value() < sb.maximum())
        self._top.raise_()
        self._bot.raise_()


def attach_edge_fades(area: QAbstractScrollArea, *, surface: str = "dialog") -> EdgeFades:
    """Convenience wrapper around :class:`EdgeFades`."""
    return EdgeFades(area, surface=surface)
