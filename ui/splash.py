"""ChromIQ startup splash.

The Chrom/IQ wordmark underlined by the full-width 5-colour spectrum bar (the
masthead motif), theme-aware. Shown while ``MainWindow`` is being built — it
overlaps the existing init and is dismissed with ``QSplashScreen.finish(win)``,
so it does NOT add load time (there is no artificial minimum display). No
sponsor content: this is the neutral, product-only splash.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPixmap
import time as _time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QApplication, QSplashScreen, QWidget

# Reuse the masthead's single source of truth for colours + wordmark styling.
from ui.masthead_header import _ACCENT, _PALETTE_DARK, _PALETTE_LIGHT, _STOPS

_W, _H = 640, 400          # logical size (points); rendered at device pixel ratio
_WORDMARK_PX = 118
_BAR_H = 9
_BAR_GAP = 24              # clear space between the italic-Q tail and the bar


def _wordmark_fonts() -> tuple[QFont, QFont]:
    """(regular 'Chrom', bold-italic 'IQ') — same families/weights as the masthead."""
    fams = ["Instrument Serif", "Georgia", "Times New Roman", "serif"]
    reg = QFont(); reg.setFamilies(fams); reg.setPixelSize(_WORDMARK_PX)
    reg.setWeight(QFont.Weight.Normal); reg.setItalic(False)
    ital = QFont(); ital.setFamilies(fams); ital.setPixelSize(_WORDMARK_PX)
    ital.setWeight(QFont.Weight.Bold); ital.setItalic(True)
    return reg, ital


def make_splash_pixmap(mode: str, version: str = "") -> QPixmap:
    """Render the splash for *mode* ('light' | 'dark') at the screen's DPR."""
    pal = _PALETTE_LIGHT if mode == "light" else _PALETTE_DARK
    screen = QApplication.primaryScreen()
    dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0

    pm = QPixmap(int(_W * dpr), int(_H * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(QColor(pal["bg"]))

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    reg, ital = _wordmark_fonts()
    fm_r, fm_i = QFontMetricsF(reg), QFontMetricsF(ital)
    chrom_w = fm_r.horizontalAdvance("Chrom")
    iq_w = fm_i.horizontalAdvance("IQ")
    total_w = chrom_w + iq_w - 1                     # -1 optical kern (as masthead)

    baseline = _H * 0.46
    x0 = (_W - total_w) / 2.0
    p.setFont(reg); p.setPen(QColor(pal["wordmark"]))
    p.drawText(int(x0), int(baseline), "Chrom")
    p.setFont(ital); p.setPen(QColor(_ACCENT))
    p.drawText(int(x0 + chrom_w - 1), int(baseline), "IQ")

    # Full-width spectrum bar (5 solid segments, no gaps) clearing the Q tail.
    q_ink_bottom = baseline + fm_i.tightBoundingRect("IQ").bottom()
    by = q_ink_bottom + _BAR_GAP
    n = len(_STOPS)
    for i, col in enumerate(_STOPS):
        xa = round(i * _W / n)
        xb = round((i + 1) * _W / n) if i < n - 1 else _W
        p.fillRect(int(xa), int(by), int(xb - xa), _BAR_H, QColor(col))

    # Tagline (product, not sponsor) + version, both muted.
    tag = QFont(); tag.setFamilies(["Inter", "Arial", "Helvetica Neue"]); tag.setPixelSize(17)
    p.setFont(tag); p.setPen(QColor(pal["ver_fg"]))
    p.drawText(0, int(by + _BAR_H + 34), _W, 24,
               int(Qt.AlignmentFlag.AlignHCenter),
               "Printer profiling with ArgyllCMS")
    if version:
        ver = QFont(); ver.setFamilies(["Inter", "Arial", "Helvetica Neue"]); ver.setPixelSize(14)
        p.setFont(ver); p.setPen(QColor(pal["ver_fg"]))
        p.drawText(0, _H - 40, _W - 22, 24,
                   int(Qt.AlignmentFlag.AlignRight), version)
    p.end()
    return pm


class PlainSplash(QWidget):
    """The splash as an ordinary frameless window.

    Qt's ``QSplashScreen.show()`` costs **~1030 ms** on this platform: its event
    handler runs a bounded 1000 ms wait loop for ``windowHandle()->isVisible()``,
    a condition that is never true during ``show_helper``, so it always burns the
    whole timeout. Measured against a plain frameless widget carrying the same
    pixmap: 1043 ms against 13.6 ms.

    The splash exists because users could not tell the app had started at all, so
    it must still be PAINTED before the blocking build begins — the first version
    of it showed nothing and then flashed just before the main window, and that
    must not come back. ``wait_until_visible`` waits on ``isExposed()``, which is
    what "actually on screen" means, rather than the ``isVisible()`` that Qt's own
    loop waits on and that is already true 1.8 ms in, while nothing is drawn.
    Measured: exposed after 9-66 ms.
    """

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__(None,
                         Qt.WindowType.SplashScreen
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self._pm = pixmap
        # LOGICAL size, not the pixmap's device size. make_splash_pixmap renders
        # at devicePixelRatio 2 on a Retina screen, so pixmap.size() is 1280x800
        # DEVICE pixels for a 640x400 window — sized from that, the window came
        # up twice as large with the artwork in its top-left quarter (Basti, on
        # the first real launch). QSplashScreen did this conversion for us.
        size = pixmap.deviceIndependentSize().toSize()
        self.setFixedSize(size)
        scr = QApplication.primaryScreen()
        if scr is not None:
            c = scr.geometry().center()
            self.move(c.x() - size.width() // 2, c.y() - size.height() // 2)

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt's name
        # Into the widget's rect, so the pixmap's own ratio is honoured whatever
        # screen it lands on.
        QPainter(self).drawPixmap(self.rect(), self._pm)

    def mousePressEvent(self, event) -> None:  # noqa: N802 — Qt's name
        """Click to dismiss, as QSplashScreen does.

        Not cosmetic: `MainWindow.__init__` can open the ArgyllCMS-not-found
        dialog with `exec()` while this window is still up and always-on-top, so
        on a first launch without ArgyllCMS a modal dialog would sit under a
        splash the user could not get rid of.
        """
        self.hide()

    def wait_until_visible(self, timeout_s: float = 0.3) -> bool:
        """Pump until the window is really on screen, or *timeout_s* passes.

        BOUNDED on purpose. A compositor that never exposes the window (remote
        desktop, an odd session) must cost a fraction of a second, not the launch
        — trading Qt's fixed 1 s delay for an unbounded one would be worse than
        the fault being fixed. Returns whether it was actually exposed.
        """
        app = QApplication.instance()
        end = _time.monotonic() + timeout_s
        while _time.monotonic() < end:
            if app is not None:
                app.processEvents()
            h = self.windowHandle()
            if h is not None and h.isExposed():
                self.repaint()
                if app is not None:
                    app.processEvents()
                return True
            _time.sleep(0.002)
        return False

    def finish(self, _window=None) -> None:
        """Same call shape as ``QSplashScreen.finish`` so callers do not care."""
        self.close()


def make_splash(mode: str, version: str = "", plain: bool = True):
    """A ready-to-show splash for *mode*.

    *plain* uses :class:`PlainSplash` (default); False returns Qt's
    ``QSplashScreen``, kept as the escape hatch behind the "Classic splash
    screen" setting. Either way the caller shows it and calls ``finish(window)``.
    """
    if plain:
        return PlainSplash(make_splash_pixmap(mode, version))
    splash = QSplashScreen(make_splash_pixmap(mode, version))
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    return splash
