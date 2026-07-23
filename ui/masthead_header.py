"""ChromIQ masthead — full-width header with embedded settings button.

The settings button is positioned top-right as an absolute child so the
header fills 100 % of the window width with no gap. Emits ``settings_clicked``
when the gear button is pressed.
"""
from __future__ import annotations

from PyQt6.QtCore import QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetricsF, QGuiApplication, QIcon,
    QPainter, QPen, QPaintEvent, QPixmap,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QToolButton, QWidget

from core.resource_path import resource_path
from ui.welcome_button import WelcomeButton
from core.i18n import tr

_STOPS = (
    "#ff4573",  # Create Chart
    "#ffb42d",  # Print Chart
    "#56d6a5",  # Measure
    "#37bcd6",  # Build Profile
    "#9f82ff",  # Check & Refine
)

_ACCENT     = "#ff4573"  # tab-1 tint for "IQ" — unchanged in both modes

# Per-mode palettes. Dark values are historical; light values per the
# light-mode v2 handoff design.
_PALETTE_DARK = {
    "bg":             "#0a0a0a",
    "ver_bg":         "#070707",
    "ver_fg":         "#6a6a6a",
    "tag_fg":         "#4a4a4a",
    "wordmark":       "#ffffff",   # "Chrom"
    "ver_separator":  "#000000",
    "icon_track":     "#555555",   # programmatic fallback icon
    "wordmark_dy":    0,           # vertical fine-tune for the wordmark baseline
}
_PALETTE_LIGHT = {
    "bg":             "#f5f3ef",
    "ver_bg":         "#eeebe5",
    "ver_fg":         "#7a7570",
    "tag_fg":         "#b8b4ae",
    "wordmark":       "#1c1b18",
    "ver_separator":  "#d8d4ce",
    "icon_track":     "#c8c4be",
    "wordmark_dy":    -5,          # nudge "ChromIQ" 5 px up in light mode
}


class MastheadHeader(QWidget):
    """Custom header: spectrum stripe + centred Chrom/IQ wordmark + version rail
    + embedded settings button (no layout gap to the right)."""

    settings_clicked = pyqtSignal()
    help_clicked     = pyqtSignal()
    tools_clicked    = pyqtSignal()

    STRIPE_H  = 6
    VERSION_H = 22

    def __init__(
        self,
        parent: QWidget | None = None,
        version: str = "",
    ) -> None:
        super().__init__(parent)
        self._version = version
        self._mode    = "dark"
        self._palette = _PALETTE_DARK
        self.setFixedHeight(110)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)

        # ---- Embedded settings button (absolute child) ----
        self._btn = QToolButton(self)
        self._btn.setObjectName("tooltip_btn")
        self._btn.setToolTip(tr("Preferences"))
        self._btn.setFixedSize(QSize(44, 44))
        self._btn.clicked.connect(self.settings_clicked)
        self._load_settings_icon()

        # ---- Embedded tools button (absolute child, left of settings) ----
        self._tools_btn = QToolButton(self)
        self._tools_btn.setObjectName("tooltip_btn")
        self._tools_btn.setToolTip(tr("Tools"))
        self._tools_btn.setFixedSize(QSize(44, 44))
        self._tools_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tools_btn.clicked.connect(self.tools_clicked)
        self._load_tools_icon()

        # ---- Embedded "?" help button (absolute child, far right) ----
        self._help_btn = WelcomeButton(self)
        self._help_btn.help_clicked.connect(self.help_clicked)

        # ---- Optional centred widget on the version rail (the shared
        # Profile-run / Run-type bar, #130) ----
        self._center_widget: QWidget | None = None

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        """Switch between 'light' and 'dark' palettes and repaint."""
        new_mode = "light" if mode == "light" else "dark"
        if new_mode == self._mode:
            return
        self._mode = new_mode
        self._palette = _PALETTE_LIGHT if new_mode == "light" else _PALETTE_DARK
        self._load_settings_icon()
        self._load_tools_icon()
        self.update()

    # ------------------------------------------------------------------
    def setVersion(self, v: str) -> None:
        if v != self._version:
            self._version = v
            self.update()

    # ------------------------------------------------------------------
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Right edge: [ Tools ] [ Settings ] [ ? ] — help icon sits on the far right.
        bw, bh = self._btn.width(), self._btn.height()
        body_top  = self.STRIPE_H
        body_bot  = self.height() - self.VERSION_H
        btn_y = body_top + (body_bot - body_top - bh) // 2
        help_x = self.width() - self._help_btn.width() - 12
        self._help_btn.move(help_x, btn_y)
        self._btn.move(help_x - bw - 8, btn_y)
        self._tools_btn.move(help_x - bw - 8 - self._tools_btn.width() - 8, btn_y)
        self.reposition_center()

    # ------------------------------------------------------------------
    def set_center_widget(self, w: QWidget) -> None:
        """Host ``w`` centred on the version rail, in line with the
        'PRINTER PROFILING' tagline and the version number."""
        w.setParent(self)
        self._center_widget = w
        w.show()
        self.reposition_center()

    def reposition_center(self) -> None:
        w = self._center_widget
        if w is None:
            return
        cw = w.sizeHint().width()
        ch = w.sizeHint().height()
        ver_y = self.height() - self.VERSION_H
        x = (self.width() - cw) // 2
        y = ver_y + (self.VERSION_H - ch) // 2      # centred on the rail
        w.setGeometry(x, y, cw, ch)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(900, 110)

    # ------------------------------------------------------------------
    def paintEvent(self, _ev: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()

        pal = self._palette

        # Background
        p.fillRect(self.rect(), QColor(pal["bg"]))

        # Spectrum stripe
        n = len(_STOPS)
        for i, col in enumerate(_STOPS):
            x0 = int(round(i * w / n))
            x1 = int(round((i + 1) * w / n)) if i < n - 1 else w
            p.fillRect(x0, 0, x1 - x0, self.STRIPE_H, QColor(col))

        # Version rail
        ver_y = h - self.VERSION_H
        p.fillRect(0, ver_y, w, self.VERSION_H, QColor(pal["ver_bg"]))
        p.setPen(QPen(QColor(pal["ver_separator"]), 1))
        p.drawLine(0, ver_y, w, ver_y)

        mono = QFont()
        mono.setFamilies(["JetBrains Mono", "Menlo", "SF Mono", "Courier New", "monospace"])
        mono.setPixelSize(9)

        if self._version:
            mono_lc = QFont(mono)
            mono_lc.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 115)
            p.setFont(mono_lc)
            fm = QFontMetricsF(mono_lc)
            ver_text = f"v{self._version}"
            ver_tw = fm.horizontalAdvance(ver_text)
            base = int(ver_y + (self.VERSION_H + fm.ascent() - fm.descent()) / 2)
            p.setPen(QColor(pal["ver_fg"]))
            p.drawText(int(w - ver_tw - 18), base, ver_text)

            # Left tag
            tag_font = QFont(mono)
            tag_font.setPixelSize(9)
            tag_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 148)
            p.setFont(tag_font)
            p.setPen(QColor(pal["tag_fg"]))
            p.drawText(18, base, "PRINTER PROFILING")

        # ---- Centred wordmark ----
        body_cy = (self.STRIPE_H + ver_y) / 2

        # "Chrom" — regular weight Instrument Serif
        font_r = QFont()
        font_r.setFamilies(["Instrument Serif", "Georgia", "Times New Roman", "serif"])
        font_r.setPixelSize(62)
        font_r.setWeight(QFont.Weight.Normal)
        font_r.setItalic(False)

        # "IQ" — bold italic Instrument Serif
        font_i = QFont()
        font_i.setFamilies(["Instrument Serif", "Georgia", "Times New Roman", "serif"])
        font_i.setPixelSize(62)
        font_i.setWeight(QFont.Weight.Bold)
        font_i.setItalic(True)

        fm_r = QFontMetricsF(font_r)
        fm_i = QFontMetricsF(font_i)
        chrom_w = fm_r.horizontalAdvance("Chrom")
        iq_w    = fm_i.horizontalAdvance("IQ")
        total_w = chrom_w + iq_w - 1   # -1 optical kern

        x_start  = (w - total_w) / 2
        baseline = body_cy + (fm_r.ascent() - fm_r.descent()) / 2 + 8 + pal.get("wordmark_dy", 0)

        p.setFont(font_r)
        p.setPen(QColor(pal["wordmark"]))
        p.drawText(int(x_start), int(baseline), "Chrom")

        p.setFont(font_i)
        p.setPen(QColor(_ACCENT))
        p.drawText(int(x_start + chrom_w - 1), int(baseline), "IQ")

        p.end()

    # ------------------------------------------------------------------
    def _load_settings_icon(self) -> None:
        """Load the settings icon matching the current mode.

        Order of preference:
          1. mode-specific PNG asset (settings_v2_light.png in light mode)
          2. default settings_v2.png (in dark mode, or as fallback)
          3. programmatic sliders icon, tinted for the current mode
        """
        candidates: list[str] = []
        if self._mode == "light":
            candidates.append("assets/settings_v2_light.png")
        candidates.append("assets/settings_v2.png")

        for rel in candidates:
            path = resource_path(rel)
            if not path.exists():
                continue
            px = QPixmap(str(path))
            if px.isNull():
                continue
            dpr  = QGuiApplication.primaryScreen().devicePixelRatio()
            phys = round(26 * dpr)
            scaled = px.scaled(
                phys, phys,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(dpr)
            self._btn.setIcon(QIcon(scaled))
            self._btn.setIconSize(QSize(26, 26))
            # In light mode skip the dark-tuned PNG and fall through to the
            # programmatic icon, which we can re-tint to match.
            if self._mode == "light" and rel == "assets/settings_v2.png":
                break
            return

        self._btn.setIcon(self._draw_sliders_icon())
        self._btn.setIconSize(QSize(26, 26))

    # ------------------------------------------------------------------
    def tools_button(self) -> QToolButton:
        """Expose the Tools button so callers can anchor a popup under it."""
        return self._tools_btn

    # ------------------------------------------------------------------
    def _load_tools_icon(self) -> None:
        """Render the tools toolbox SVG to fill the button.

        The SVG ships in two flavours (``tools_v2.svg`` for dark, ``tools_v2_light.svg``
        for light). The toolbox graphic has noticeable internal padding inside its
        64x64 viewBox, so we render close to the full button area (40 px inside
        the 44x44 button) so the visible shape matches the optical weight of the
        adjacent settings gear and "?" help glyph.
        """
        rel = "assets/tools_v2_light.svg" if self._mode == "light" else "assets/tools_v2.svg"
        path = resource_path(rel)
        if not path.exists():
            return
        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return
        # The toolbox graphic is visually bottom-heavy (handle + lid above a
        # body of coloured stripes), so a strictly centred render reads as
        # sitting a bit low next to the gear and "?" buttons. Shift the SVG a
        # few logical px upward inside the pixmap to optically centre it.
        size      = 40   # logical px — fills the 44x44 button with a slim margin
        y_shift   = 3    # logical px — nudge the artwork upward
        dpr  = QGuiApplication.primaryScreen().devicePixelRatio()
        phys = round(size * dpr)
        shift_phys = round(y_shift * dpr)
        px = QPixmap(phys, phys)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(p, QRectF(0.0, float(-shift_phys), float(phys), float(phys)))
        p.end()
        px.setDevicePixelRatio(dpr)
        self._tools_btn.setIcon(QIcon(px))
        self._tools_btn.setIconSize(QSize(size, size))

    def _draw_sliders_icon(self) -> QIcon:
        dpr  = QGuiApplication.primaryScreen().devicePixelRatio()
        phys = round(26 * dpr)
        px   = QPixmap(phys, phys)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_cols = ["#ff4573", "#37bcd6", "#ffb42d"]
        knob_x     = [0.65, 0.30, 0.50]
        track_color = self._palette["icon_track"]
        for i, (col, kx) in enumerate(zip(track_cols, knob_x)):
            y = int(phys * (0.28 + i * 0.22))
            # Track
            p.setPen(QPen(QColor(track_color), max(1, int(phys * 0.07)),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(int(phys * 0.12), y, int(phys * 0.88), y)
            # Knob
            hx = int(phys * kx)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(col))
            r = max(2, int(phys * 0.13))
            p.drawEllipse(hx - r, y - r, r * 2, r * 2)
        p.end()
        px.setDevicePixelRatio(dpr)
        return QIcon(px)
