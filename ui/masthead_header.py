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
    #: The two left-hand buttons moved out of the tabs (#130).
    load_project_clicked = pyqtSignal()
    load_ti2_clicked     = pyqtSignal()

    STRIPE_H  = 6
    VERSION_H = 28      # tall enough to seat the compact target bar with margin
    BODY_H    = 88      # the masthead proper; the rail is added underneath it
    RAIL_PAD  = 3       # breathing room above + below the centre widget;
                        # matches the margin the 28 px rail always gave the
                        # one-line bar, so the default masthead is unchanged

    def __init__(
        self,
        parent: QWidget | None = None,
        version: str = "",
    ) -> None:
        super().__init__(parent)
        self._version = version
        self._mode    = "dark"
        self._palette = _PALETTE_DARK
        # The rail grows to fit whatever centre widget is installed — the
        # Profile-run bar gained a second line ("Location being edited"), and a
        # fixed 28 px rail silently pushed it up out of view (#130).
        self._rail_h = self.VERSION_H
        self.setFixedHeight(self.BODY_H + self._rail_h)
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

        # ---- Load Project / Load .ti2 (absolute children, far LEFT) ----
        #
        # Moved here out of the tabs (#130, spec agreed 2026-07-31): Load
        # Project used to sit in Create Chart and Load .ti2 in BOTH Print Chart
        # and Measure. They act on the whole app rather than on one tab, so the
        # masthead is where they belong — and one Load .ti2 button replaces two.
        #
        # These icons do NOT follow the active tab's colour. Sebastian,
        # 2026-07-31: *"In the masthead the icons don't have to follow the color
        # of the active tab anymore. That's why we asked you for multi-color
        # versions."* So they are static, and set_appearance only swaps the
        # light/dark artwork.
        self._load_project_btn = QToolButton(self)
        self._load_project_btn.setObjectName("tooltip_btn")
        self._load_project_btn.setToolTip(tr(
            "Open Project\n\n"
            "Opens a printer profile project you have already made.\n\n"
            "Brings back its runs, its charts and its measurements, and picks "
            "up where you left off. Unavailable while a measurement is "
            "running."))
        self._load_project_btn.setFixedSize(QSize(44, 44))
        self._load_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_project_btn.clicked.connect(self.load_project_clicked)

        self._load_ti2_btn = QToolButton(self)
        self._load_ti2_btn.setObjectName("tooltip_btn")
        self._load_ti2_btn.setToolTip(tr(
            "Open Chart File (.ti2)\n\n"
            "Opens a laid-out chart to print or measure.\n\n"
            "This is the laid-out chart ChromIQ made for you — the same one you "
            "printed. Loading it here shows its pages in Create Chart, Print "
            "Chart and Measure, so all three are working on the same chart. "
            "Unavailable while a measurement is running."))
        self._load_ti2_btn.setFixedSize(QSize(44, 44))
        self._load_ti2_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_ti2_btn.clicked.connect(self.load_ti2_clicked)
        self._load_masthead_left_icons()

        # ---- Optional centred widget on the version rail (the shared
        # Profile-run / Run-type bar, #130) ----
        self._center_widget: QWidget | None = None
        self._repositioning = False    # guards the layout-request filter

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
        self._load_masthead_left_icons()
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
        body_bot  = self.height() - self._rail_h
        btn_y = body_top + (body_bot - body_top - bh) // 2
        help_x = self.width() - self._help_btn.width() - 12
        self._help_btn.move(help_x, btn_y)
        self._btn.move(help_x - bw - 8, btn_y)
        self._tools_btn.move(help_x - bw - 8 - self._tools_btn.width() - 8, btn_y)
        # Left edge: [ Load Project ] [ Load .ti2 ], mirroring the right-hand
        # group. Knut's spec (#130, 2026-07-31): the same icon size, the gap
        # between them equal to the Tools↔Preferences gap (8 px), and the left
        # margin equal to the Help icon's right margin (12 px).
        self._load_project_btn.move(12, btn_y)
        self._load_ti2_btn.move(12 + self._load_project_btn.width() + 8, btn_y)
        self.reposition_center()

    # ------------------------------------------------------------------
    def set_center_widget(self, w: QWidget) -> None:
        """Host ``w`` centred on the version rail, in line with the
        'PRINTER PROFILING' tagline and the version number.

        The rail (and with it the masthead) grows when *w* needs more room than
        the default, so a taller centre widget is always fully visible instead
        of being centred out of the band."""
        w.setParent(self)
        self._center_widget = w
        # The rail is laid out by hand, so nothing re-lays the centre widget
        # when *its own* content changes — and it changes often: turning Run
        # type to Verification adds boxes. Left as it was, the widget kept its
        # old width and its children overlapped each other until some later
        # event happened to re-lay it (Knut, #130 2026-07-26). Watching for the
        # layout request keeps it in step, whatever caused the change.
        w.installEventFilter(self)
        w.show()
        self._fit_rail_to_center()
        self.reposition_center()

    @staticmethod
    def _center_height(w) -> int:
        """The height the centre widget will actually be given.

        Its hint, but never more than it is allowed to be. The Profile-run bar
        caps itself when its location line is hidden, and sizing the rail to
        the uncapped hint left a band of empty rail under it — the space below
        the boxes no longer matched the space above them.
        """
        hint = w.sizeHint().height()
        ceiling = w.maximumHeight()
        return min(hint, ceiling) if ceiling > 0 else hint

    def _fit_rail_to_center(self) -> None:
        """Size the version rail to the centre widget, never below the default."""
        w = self._center_widget
        needed = ((self._center_height(w) + 2 * self.RAIL_PAD)
                  if w is not None else 0)
        rail = max(self.VERSION_H, needed)
        if rail != self._rail_h:
            self._rail_h = rail
            self.setFixedHeight(self.BODY_H + rail)
            self.updateGeometry()
            self.update()

    @staticmethod
    def _rail_mono() -> QFont:
        """The rail's base font — one definition, so what is measured is
        exactly what is painted."""
        mono = QFont()
        mono.setFamilies(["JetBrains Mono", "Menlo", "SF Mono", "Courier New",
                          "monospace"])
        mono.setPixelSize(9)
        return mono

    def eventFilter(self, obj, event):      # noqa: N802
        """Re-lay the centre widget as soon as it asks for a layout."""
        from PyQt6.QtCore import QEvent
        if obj is self._center_widget and event.type() in (
                QEvent.Type.LayoutRequest, QEvent.Type.Show,
                QEvent.Type.FontChange, QEvent.Type.StyleChange):
            if not self._repositioning:
                self.reposition_center()
        return False

    def _rail_text_widths(self) -> "tuple[float, float]":
        """(left tag, right version) widths, measured with the very fonts the
        rail paints them in — so the centre widget can be placed against them."""
        mono = self._rail_mono()
        tag = QFont(mono)
        tag.setPixelSize(9)
        tag.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 148)
        tag_w = QFontMetricsF(tag).horizontalAdvance("PRINTER PROFILING")
        ver = QFont(mono)
        ver.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 115)
        ver_w = (QFontMetricsF(ver).horizontalAdvance(f"v{self._version}")
                 if self._version else 0.0)
        return tag_w, ver_w

    def reposition_center(self) -> None:
        w = self._center_widget
        if w is None or self._repositioning:
            return
        self._repositioning = True          # setGeometry re-enters this filter
        try:
            self._do_reposition(w)
        finally:
            self._repositioning = False

    def _do_reposition(self, w) -> None:
        self._fit_rail_to_center()          # the widget may have grown/shrunk
        # Tell it how much room there is first, so a widget that can give way
        # (the Profile-run bar can) has already done so before it is measured.
        tag_w0, ver_w0 = self._rail_text_widths()
        room0 = int(self.width() - 18 - ver_w0 - 12) - int(18 + tag_w0 + 16)
        if hasattr(w, "set_available_width") and room0 > 0:
            w.set_available_width(room0)
        cw = w.sizeHint().width()
        ch = self._center_height(w)     # provisional: refined once width is known
        ver_y = self.height() - self._rail_h
        # Left-aligned immediately after the "PRINTER PROFILING" tag, not
        # centred (Knut, #130 2026-07-26): a centred widget slides sideways
        # every time its content changes — turning Run type to Verification
        # moved the whole group. Anchored here, new boxes only extend to the
        # right and nothing already on screen moves.
        tag_w, ver_w = self._rail_text_widths()
        x = int(18 + tag_w + 16)
        room = int(self.width() - 18 - ver_w - 12) - x      # stay clear of vX.Y
        y = ver_y + (self._rail_h - ch) // 2        # centred on the rail
        # Never narrower than the widget's own minimum: squeezing it below that
        # does not shrink its children, it makes them overlap each other.
        floor = w.minimumSizeHint().width()
        width = min(cw, room) if room > 0 else cw
        # A widget may ask for the whole rail instead of its own preferred
        # width — the Profile-run bar does while its hint sentence is shown, so
        # that the sentence wraps against the version text rather than inside a
        # narrow column of its own (Knut, #131 2026-07-27).
        if room > 0 and getattr(w, "wants_full_width", lambda: False)():
            width = room
        width = max(width, floor)
        # A widget whose height depends on its width — one holding a wrapped
        # label — has to be measured at the width it is about to be given, or it
        # keeps the height it worked out for some other width and its text wraps
        # into a column of its own (Knut, #131 2026-07-27).
        if w.hasHeightForWidth():
            ch = max(ch, w.heightForWidth(width))
            # …but still never taller than it is allowed to be, or a wrapped
            # label re-inflates a widget that has just capped itself.
            if w.maximumHeight() > 0:
                ch = min(ch, w.maximumHeight())
        w.setGeometry(x, y, width, ch)
        # …and re-lay its children at that size, so the label inside is measured
        # against the width it actually has.
        lay = w.layout()
        if lay is not None:
            lay.activate()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(900, self.BODY_H + self._rail_h)

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
        ver_y = h - self._rail_h
        p.fillRect(0, ver_y, w, self._rail_h, QColor(pal["ver_bg"]))
        p.setPen(QPen(QColor(pal["ver_separator"]), 1))
        p.drawLine(0, ver_y, w, ver_y)

        mono = self._rail_mono()

        if self._version:
            mono_lc = QFont(mono)
            mono_lc.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 115)
            p.setFont(mono_lc)
            fm = QFontMetricsF(mono_lc)
            ver_text = f"v{self._version}"
            ver_tw = fm.horizontalAdvance(ver_text)
            base = int(ver_y + (self._rail_h + fm.ascent() - fm.descent()) / 2)
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
    def _load_masthead_left_icons(self) -> None:
        """Draw the Load Project / Load .ti2 marks for the current theme.

        Multi-colour by design — they keep their own palette whatever tab is on
        screen (Sebastian, 2026-07-31). Each ships a light variant whose strokes
        are heavier, because the dark artwork disappears on a pale background.
        """
        suffix = "_light" if self._mode == "light" else ""
        for btn, name in ((self._load_project_btn, "load_project"),
                          (self._load_ti2_btn, "load_ti2")):
            path = resource_path(f"assets/{name}{suffix}.svg")
            if not path.exists():
                continue
            renderer = QSvgRenderer(str(path))
            if not renderer.isValid():
                continue
            size = 40
            dpr = self.devicePixelRatioF() or 1.0
            pm = QPixmap(int(size * dpr), int(size * dpr))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(p, QRectF(0, 0, size, size))
            p.end()
            btn.setIcon(QIcon(pm))
            btn.setIconSize(QSize(size, size))

    def set_load_buttons_enabled(self, enabled: bool) -> None:
        """Grey both left-hand buttons while a measurement is running.

        Knut, #130 2026-07-31: *"Remember that also the Load Project icon should
        be Disabled while a measurement runs."* Load .ti2 already had that guard
        on the Measure tab; Load Project never did.
        """
        for btn in (self._load_project_btn, self._load_ti2_btn):
            btn.setEnabled(enabled)
            btn.setCursor(Qt.CursorShape.PointingHandCursor if enabled
                          else Qt.CursorShape.ArrowCursor)

    #: The right-hand icons that must also go quiet mid-measurement. Help is
    #: deliberately not among them — Knut, beta.120: *"Help button can be
    #: active still."*
    def set_measuring(self, running: bool) -> None:
        """Grey the Tools and Preferences icons while a measurement runs.

        Both open windows that change what the app is working on — Preferences
        can switch the chart-reading engine, Tools can rewrite files under the
        run — and neither is safe to reach for with an instrument mid-read
        (Knut, #130 beta.120). Help stays available, because reading is always
        safe.
        """
        self.set_load_buttons_enabled(not running)
        for btn in (self._tools_btn, self._btn):
            if btn is None:
                continue
            btn.setEnabled(not running)
            btn.setCursor(Qt.CursorShape.ArrowCursor if running
                          else Qt.CursorShape.PointingHandCursor)
            if not hasattr(btn, "_cq_tip"):
                btn._cq_tip = btn.toolTip()
            btn.setToolTip(tr(
                "Not while a measurement is running. It will be available "
                "again as soon as the current measurement finishes or is "
                "stopped.\n\n"
                "This opens a window that can change what ChromIQ is working "
                "on, and the instrument is reading a chart right now.")
                if running else btn._cq_tip)

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
