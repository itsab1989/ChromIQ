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
from PyQt6.QtWidgets import QApplication, QSplashScreen

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
    tag = QFont(); tag.setFamilies(["Inter", "Arial", "sans-serif"]); tag.setPixelSize(17)
    p.setFont(tag); p.setPen(QColor(pal["ver_fg"]))
    p.drawText(0, int(by + _BAR_H + 34), _W, 24,
               int(Qt.AlignmentFlag.AlignHCenter),
               "Printer profiling with ArgyllCMS")
    if version:
        ver = QFont(); ver.setFamilies(["Inter", "Arial", "sans-serif"]); ver.setPixelSize(14)
        p.setFont(ver); p.setPen(QColor(pal["ver_fg"]))
        p.drawText(0, _H - 40, _W - 22, 24,
                   int(Qt.AlignmentFlag.AlignRight), version)
    p.end()
    return pm


def make_splash(mode: str, version: str = "") -> QSplashScreen:
    """A ready-to-show ``QSplashScreen`` for *mode*. Caller shows it, then calls
    ``splash.finish(main_window)`` once the window is up."""
    splash = QSplashScreen(make_splash_pixmap(mode, version))
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    return splash
