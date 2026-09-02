"""ChromIQ startup splash.

The Chrom/IQ wordmark underlined by the full-width 5-colour spectrum bar (the
masthead motif), theme-aware. Shown while ``MainWindow`` is being built — it
overlaps the existing init and is dismissed with ``QSplashScreen.finish(win)``,
so it does NOT add load time (there is no artificial minimum display). No
sponsor content: this is the neutral, product-only splash.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPixmap
import time as _time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QApplication, QSplashScreen, QWidget

# Reuse the masthead's single source of truth for colours + wordmark styling.
from ui import index_rule
from ui.masthead_header import _ACCENT, _PALETTE_DARK, _PALETTES, _STOPS

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
    """Render the splash for *mode* at the screen's DPR.

    *mode* is a concrete appearance — 'light', 'dark' or 'neutral'. It used to
    be folded, ``_PALETTE_LIGHT if mode == "light" else _PALETTE_DARK``, which
    would have opened a light-grey session on a near-black splash.

    THE WORDMARK'S ACCENT COMES FROM THE PALETTE, not from a module constant.
    ``_ACCENT`` (magenta) painted "IQ" in every appearance; on a light ground
    it measures 2.55:1, so it was not carrying the mark there at all. Neutral
    sets "Chrom" in TEXT_FAINT and "IQ" in TEXT_MAIN — the italic already
    separates them, and that is a larger contrast step than the magenta was
    providing. Light and Dark still name the magenta, so they are unchanged.
    """
    pal = _PALETTES.get(mode, _PALETTE_DARK)
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
    p.setFont(ital); p.setPen(QColor(pal.get("wordmark_accent", _ACCENT)))
    p.drawText(int(x0 + chrom_w - 1), int(baseline), "IQ")

    # Full-width bar clearing the Q tail: five solid hue segments in Light and
    # Dark, the Index rule in Neutral — the same part the masthead stripe wears,
    # and the last of the five screen sites the spectrum bar occupied. It is
    # filled to ALL here rather than to a step: a splash has no position in the
    # run, so it wears the mark and not a readout.
    q_ink_bottom = baseline + fm_i.tightBoundingRect("IQ").bottom()
    by = q_ink_bottom + _BAR_GAP
    if index_rule.use_index_rule(mode):
        index_rule.paint_index_rule(p, 0, int(by), _W, _BAR_H, index_rule.ALL)
    else:
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


class _YieldsToModals:
    """Step aside for the duration of an application-modal dialog.

    A splash is always-on-top (``WindowStaysOnTopHint`` → ``WS_EX_TOPMOST``).
    A modal dialog is NOT, and on Windows a non-topmost window can never be
    raised above a topmost one — so a modal opened while the splash is up sits
    UNDER it, ~83% covered, with its buttons unclickable because the topmost
    splash swallows the clicks. Only Alt+Tab reaches it. Measured on Windows 11
    with no ArgyllCMS installed: the first thing a new user meets.

    Clicking the splash away cannot rescue this (see
    :meth:`PlainSplash.mousePressEvent`): ``QDialog.exec()`` is application-modal
    and Qt discards mouse events to blocked windows, so the one documented
    escape hatch is inert exactly when it is needed.

    Qt does tell us, though: it delivers ``WindowBlocked`` to every top-level
    window a modal blocks, and ``WindowUnblocked`` when it clears — one pair per
    modal, and no ``WindowUnblocked`` while an outer modal is still up, so the
    splash can never pop back on top of a dialog that is still open.

    Two guards carry real weight:

    * ``_finished`` — ``finish()`` only ``close()``s the widget; the object
      lives as long as ``main()``, which does not return until the app quits.
      Without this flag the splash would re-appear over *every* modal in the
      session, hours after startup.
    * ``isVisible()`` — ``WindowBlocked`` is delivered to hidden windows too.

    The RE-SHOW must not activate: a plain ``show()`` there takes focus off the
    main window (measured: ``activeWindow`` went from the main window to none),
    so it sets ``WA_ShowWithoutActivating`` first. That attribute is deliberately
    NOT set in the constructor — doing so also stops the app taking the
    foreground on the *initial* show (measured: ``activeWindow`` None instead of
    the splash), which is a launch-feel regression on the branch that exists to
    improve launch feel. ``main.py`` raises the splash on that initial show; the
    re-show never does.
    """

    def _init_modal_yield(self) -> None:
        self._hidden_by_modal = False
        self._finished = False

    def event(self, e):  # noqa: D102 — Qt's name
        kind = e.type()
        if kind == QEvent.Type.WindowBlocked:
            if self.isVisible():
                self._hidden_by_modal = True
                self.hide()
        elif kind == QEvent.Type.WindowUnblocked:
            # Every condition is tested BEFORE the flag is cleared. Clearing it
            # first would leave a refused re-show hidden *and* disarmed — the
            # next WindowUnblocked would see False and do nothing, stranding the
            # splash for the rest of startup. That trades a possible flicker for
            # a possible permanent disappearance, which is the wrong way round.
            if (self._hidden_by_modal and not self._finished
                    and QApplication.activeModalWidget() is None):
                self._hidden_by_modal = False
                self.setAttribute(
                    Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                self.show()
        return super().event(e)


class PlainSplash(_YieldsToModals, QWidget):
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
        self._init_modal_yield()
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

        THIS IS NOT A BACKSTOP FOR A MODAL DIALOG, whatever it used to claim.
        Qt discards mouse events to windows a modal has blocked, so on the one
        launch that needs it — no ArgyllCMS, dialog under the splash — this
        handler is never reached. It was measured doing nothing on Windows:
        clicking the splash moved the foreground to no window at all.

        :class:`_YieldsToModals` is what actually keeps a modal reachable. This
        stays because a user who wants the branding gone should be able to
        click it away.
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

    def finish(self, window=None) -> None:
        """Same call shape as ``QSplashScreen.finish`` so callers do not care.

        The parameter is named to match :class:`ClassicSplash` (and Qt), so a
        caller writing ``finish(window=…)`` works against either splash.
        """
        self._finished = True          # load-bearing: see _YieldsToModals
        self.close()


class ClassicSplash(_YieldsToModals, QSplashScreen):
    """Qt's own splash, with the same yield-to-modals rule as :class:`PlainSplash`.

    Qt's ``QSplashScreen`` ignores ``WindowBlocked`` (verified: it stays visible
    for the whole modal), so without this the "Classic splash screen" setting
    reproduced the trapped-dialog bug exactly. That matters more than it looks:
    the escape hatch a user reaches for when the splash misbehaves must not be
    the one place the misbehaviour survives.
    """

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__(pixmap)
        self._init_modal_yield()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    def finish(self, window=None) -> None:  # noqa: D102 — Qt's name
        self._finished = True              # load-bearing: see _YieldsToModals
        super().finish(window)


def make_splash(mode: str, version: str = "", plain: bool = True):
    """A ready-to-show splash for *mode* — 'light', 'dark' or 'neutral'.

    *plain* uses :class:`PlainSplash` (default); False returns
    :class:`ClassicSplash` — Qt's ``QSplashScreen`` — kept as the escape hatch
    behind the "Classic splash screen" setting. Either way the caller shows it
    and calls ``finish(window)``, and either way it steps aside for a modal.
    """
    if plain:
        return PlainSplash(make_splash_pixmap(mode, version))
    return ClassicSplash(make_splash_pixmap(mode, version))
