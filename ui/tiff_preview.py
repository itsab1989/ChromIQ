"""Multi-page TIFF preview widget with stripe highlight overlay."""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Optional

from PIL import Image
from PyQt6 import sip
from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.i18n import tr

log = get_logger(__name__)

_REFRESH_DELAY_MS = 80   # debounce repaint
_BORDER = 15             # white display border: all sides (px)

# QToolTip block appended to per-widget stylesheets so the tooltip popup
# uses the active theme even when the source label has its own QSS — on
# macOS the global QToolTip rule fails to reach tooltips originating from
# widgets with `background: transparent` or per-side border overrides.
_TOOLTIP_QSS_DARK = (
    "QToolTip { "
    "background-color: #262626; "
    "color: #e6e6e6; "
    "border: 1px solid #404040; "
    "padding: 4px;"
    " }"
)
_TOOLTIP_QSS_LIGHT = (
    "QToolTip { "
    "background-color: #ffffff; "
    "color: #22211f; "
    "border: 1px solid #d0ccc6; "
    "padding: 4px;"
    " }"
)
# Back-compat alias: existing dark stylesheet strings concatenate this.
_TOOLTIP_QSS = _TOOLTIP_QSS_DARK

# ---------------------------------------------------------------------------
# Ink channel tables
# ---------------------------------------------------------------------------

# ink code → (R, G, B) absorption per unit ink value (0–1). The canonical
# table now lives in workflow.layout_engine.colorants (shared with the chart
# raster + swatch previews, #124); imported here under the historical names.
from workflow.layout_engine.colorants import (  # noqa: E402
    _INK_ABSORPTION,
    ink_absorption_linear as _ink_absorption_linear,
)

# targen -d<N> → ordered ink codes (source: data/parameters.yaml device_type labels)
_D_TYPE_CHANNELS: dict[int, list[str]] = {
    0:  ["k"],
    1:  ["k"],
    2:  ["r", "g", "b"],
    3:  ["r", "g", "b"],
    4:  ["c", "m", "y", "k"],
    5:  ["c", "m", "y"],
    6:  ["c", "m", "y", "k", "lc", "lm"],
    7:  ["c", "m", "y", "k", "lc", "lm", "lk"],
    8:  ["c", "m", "y", "k", "r", "b"],
    9:  ["c", "m", "y", "k", "o", "g"],
    10: ["c", "m", "y", "k", "r", "g", "b"],
    11: ["c", "m", "y", "k", "o", "g", "v"],
    12: ["c", "m", "y", "k", "o", "g", "b"],
    13: ["c", "m", "y", "k", "lc", "lm", "lk", "llk"],
    14: ["c", "m", "y", "k", "o", "g", "lc", "lm"],
    15: ["c", "m", "y", "k", "lc", "lm", "mc", "mm"],
}

# targen -D <N> → ink code
_D_FLAG_CODE: dict[int, str] = {
    1: "c", 2: "m", 3: "y", 4: "k",
    5: "o", 6: "r", 7: "g", 8: "b", 9: "v", 10: "w",
    11: "lc", 12: "lm", 13: "ly", 14: "lk",
    15: "mc", 16: "mm", 17: "my", 18: "mk",
    19: "llk",
}

# --- #72 Tier D: honest preview plumbing -----------------------------------
# How the LAST separated-TIFF frame was rendered: "profile" (true colours via
# cctiff + the chart's device profile) or "approx" (absorption composite).
# Read by the preview widget right after loading to badge the picture; "" for
# ordinary RGB pages (no badge).
_render_mode: dict[str, str] = {"mode": ""}


def _set_render_mode(mode: str) -> None:
    _render_mode["mode"] = mode


def last_render_mode() -> str:
    return _render_mode["mode"]


def _srgb_to_linear(a):
    """sRGB-encoded 0..1 array → linear light."""
    import numpy as np
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(a):
    """Linear-light 0..1 array → sRGB encoding."""
    import numpy as np
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


# Channel count → most common ink layout (fallback when sidecar is absent)
_N_CHANNELS_FALLBACK: dict[int, list[str]] = {
    1: ["k"],
    3: ["r", "g", "b"],
    4: ["c", "m", "y", "k"],
    6: ["c", "m", "y", "k", "lc", "lm"],
    7: ["c", "m", "y", "k", "lc", "lm", "lk"],
    8: ["c", "m", "y", "k", "lc", "lm", "lk", "llk"],
    9: ["c", "m", "y", "k", "o", "g", "lc", "lm", "lk"],
    10: ["c", "m", "y", "k", "o", "g", "lc", "lm", "lk", "llk"],
    11: ["c", "m", "y", "k", "o", "g", "v", "lc", "lm", "lk", "llk"],
}

# ---------------------------------------------------------------------------
# ICC transform cache
# ---------------------------------------------------------------------------

_cmyk_icc_transform: object = None  # None = not tried; False = unavailable; transform = ready


def _get_cmyk_transform():
    """Return a cached PIL.ImageCms CMYK→sRGB transform, or None if unavailable."""
    global _cmyk_icc_transform
    if _cmyk_icc_transform is not None:
        return _cmyk_icc_transform if _cmyk_icc_transform is not False else None
    from PIL import ImageCms
    from core.resource_path import resource_path
    import sys as _sys
    if _sys.platform == "win32":
        import os as _os
        _windir = Path(_os.environ.get("WINDIR", r"C:\Windows"))
        _extra = [
            _windir / "System32" / "spool" / "drivers" / "color" / "USWebCoatedSWOP.icc",
            Path(r"C:\Program Files\Common Files\Adobe\Color\Profiles\USWebCoatedSWOP.icc"),
        ]
    else:
        _extra = [
            Path("/Library/Application Support/Adobe/Color/Profiles/Recommended/USWebCoatedSWOP.icc"),
            Path("/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc"),
        ]
    candidates = [resource_path("assets/USWebCoatedSWOP.icc")] + _extra
    for p in candidates:
        if p.exists():
            try:
                src = ImageCms.getOpenProfile(str(p))
                dst = ImageCms.createProfile("sRGB")
                t = ImageCms.buildTransformFromOpenProfiles(
                    src, dst, "CMYK", "RGB",
                    renderingIntent=ImageCms.Intent.PERCEPTUAL,
                )
                _cmyk_icc_transform = t
                log.debug("ICC CMYK transform loaded from %s", p.name)
                return t
            except Exception:
                continue
    _cmyk_icc_transform = False
    log.debug("No CMYK ICC profile found; will use naive subtractive fallback")
    return None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def resolve_ink_channels(device_type: str, extra_targen_args: str = "") -> list[str]:
    """Return ordered ink codes for a targen -d / -D configuration.

    device_type:       ChartParams.device_type string (e.g. "6")
    extra_targen_args: ChartParams.extra_targen_args (may contain -D N)
    """
    try:
        base = list(_D_TYPE_CHANNELS.get(int(device_type), ["c", "m", "y", "k"]))
    except ValueError:
        return ["c", "m", "y", "k"]
    try:
        tokens = shlex.split(extra_targen_args)
    except ValueError:
        return base
    i = 0
    while i < len(tokens):
        m = re.match(r"^-D(\d+)?$", tokens[i])
        if m:
            raw = m.group(1)
            if raw is None and i + 1 < len(tokens) and tokens[i + 1].isdigit():
                i += 1
                raw = tokens[i]
            if raw is not None:
                code = _D_FLAG_CODE.get(int(raw))
                if code:
                    if code in base:
                        base.remove(code)
                    else:
                        base.append(code)
        i += 1
    return base


def _find_sidecar_channels(path: Path) -> list[str] | None:
    """Return ink channels from a ChromIQ sidecar file next to path, or None."""
    stem = path.stem
    while stem and (stem[-1].isdigit() or stem[-1] in "_- "):
        stem = stem[:-1]
    candidates = [path.parent / f"{path.stem}.channels.json"]
    if stem:
        candidates.append(path.parent / f"{stem}.channels.json")
    for candidate in candidates:
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text())
                channels = data.get("ink_channels")
                if isinstance(channels, list):
                    return channels
            except Exception:
                pass
    return None


def load_tiff_as_rgb(
    path: Path, frame: int = 0, ink_channels: list[str] | None = None
) -> Image.Image:
    """Load any TIFF frame as RGB PIL Image, handling multi-channel Separated TIFFs."""
    return TiffPreview._load_frame(path, frame, ink_channels)


class _CursorOverlay(QWidget):
    """A transparent overlay that draws the #29 coordinate cross-hair + readout
    box right at the pointer. It sits on top of the image label and shares its
    coordinates, so it needs no centring maths, and it repaints itself alone —
    no chart re-render — so the cross tracks the mouse smoothly and instantly.
    Transparent to mouse events, so hovering/clicking still reaches the preview."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._pos: "QPoint | None" = None
        self._mm: "tuple[float, float] | None" = None

    def show_cursor(self, pos: "QPoint | None", mm: "tuple[float, float] | None") -> None:
        self._pos, self._mm = pos, mm
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        if self._pos is None or self._mm is None:
            return
        from PyQt6.QtGui import QPen, QFontMetrics
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        cx, cy = self._pos.x(), self._pos.y()
        arm = 8
        for pen_col, w in ((QColor(255, 255, 255, 235), 2.4),
                           (QColor(20, 20, 20), 0.8)):
            pen = QPen(pen_col); pen.setWidthF(w); p.setPen(pen)
            p.drawLine(cx - arm, cy, cx + arm, cy)
            p.drawLine(cx, cy - arm, cx, cy + arm)

        x_mm, y_mm = self._mm
        line_mm = tr("X {x:.1f}   Y {y:.1f} mm").format(x=x_mm, y=y_mm)
        line_in = tr("X {x:.3f}   Y {y:.3f} in").format(x=x_mm / 25.4, y=y_mm / 25.4)
        font = QFont("Menlo"); font.setPixelSize(11); p.setFont(font)
        fm = QFontMetrics(font)
        pad = 4
        bw = max(fm.horizontalAdvance(line_mm), fm.horizontalAdvance(line_in)) + 2 * pad
        bh = 2 * fm.height() + 2 * pad
        bx = cx + arm + 4
        by = cy - bh / 2
        if bx + bw > self.width():
            bx = cx - arm - 4 - bw
        bx = max(2.0, min(bx, self.width() - bw - 2))
        by = max(2.0, min(by, self.height() - bh - 2))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(0, 0, 0, 175))
        p.drawRoundedRect(int(bx), int(by), int(bw), int(bh), 3, 3)
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QColor(255, 255, 255))
        ty = by + pad + fm.ascent()
        p.drawText(int(bx + pad), int(ty), line_mm)
        p.drawText(int(bx + pad), int(ty + fm.height()), line_in)
        p.end()


class _PatchInfoTile(QWidget):
    """A small floating card that shows the numbers behind a measured patch.

    When "Show patch values on hover" is on, this tile follows the pointer and
    prints the expected and measured colour of the patch underneath it — each
    as sRGB (the colour you see on screen) and as exact L*a*b* — plus the ΔE
    between them. Which rows it shows follows the "Each patch shows" mode, so it
    always matches the split you are looking at. It is transparent to the mouse,
    so it never gets in the way of hovering or clicking (#126 follow-up)."""

    _PAD = 8
    _SWATCH = 13
    _GUTTER = 8

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._mode: str = "dark"
        # Each row is (swatch QColor | None, text). A None swatch means the row
        # is a plain text line (header, RGB/Lab detail, or the ΔE footer).
        self._rows: list[tuple["QColor | None", str]] = []
        self._font = QFont("Menlo")
        self._font.setPixelSize(11)
        self._font_hdr = QFont("Menlo")
        self._font_hdr.setPixelSize(11)
        self._font_hdr.setBold(True)

    def set_theme(self, mode: str) -> None:
        self._mode = "light" if mode == "light" else "dark"

    @staticmethod
    def _fmt_rgb(rgb) -> str:
        r, g, b = (int(v) for v in rgb[:3])
        return f"RGB  {r:>3} {g:>3} {b:>3}"

    @staticmethod
    def _fmt_lab(lab) -> str:
        L, a, b = (float(v) for v in lab[:3])
        return f"Lab  {L:>5.1f} {a:>5.1f} {b:>5.1f}"

    def set_content(self, info: dict, view_mode: str) -> None:
        """Build the rows for one patch and resize to fit them exactly."""
        from PyQt6.QtGui import QFontMetrics

        rows: list[tuple["QColor | None", str]] = []
        loc = str(info.get("loc", "")).strip()
        rows.append((None, tr("Patch {loc}").format(loc=loc) if loc
                     else tr("Patch")))

        def add_colour(label: str, rgb, lab) -> None:
            rows.append((QColor(*(int(v) for v in rgb[:3])), label))
            rows.append((None, "  " + self._fmt_rgb(rgb)))
            rows.append((None, "  " + self._fmt_lab(lab)))

        show_exp = view_mode in ("both", "expected")
        show_meas = view_mode in ("both", "measured")
        if show_exp:
            add_colour(tr("Expected"), info.get("exp_rgb", (0, 0, 0)),
                       info.get("exp_lab", (0, 0, 0)))
        if show_meas:
            add_colour(tr("Measured"), info.get("meas_rgb", (0, 0, 0)),
                       info.get("meas_lab", (0, 0, 0)))
        # ΔE compares the two colours, so only show it when both are on screen.
        # Named in full, because "ΔE" alone says neither which formula nor which
        # white point — and there are several of each (Knut, #131 2026-07-27:
        # "Please show what the value means, which standard it is calculated
        # with"). The reading engine computes it as CIE76 ΔE*ab on L*a*b*
        # under D50, which is what the two Lab lines above are shown in too.
        if view_mode == "both":
            rows.append((None, tr("ΔE*ab  {de:.2f}").format(
                de=float(info.get("de", 0.0)))))
            rows.append((None, tr("  (CIE76, L*a*b* D50)")))

        self._rows = rows

        fm = QFontMetrics(self._font)
        line_h = fm.height() + 2
        text_x = self._PAD + self._SWATCH + self._GUTTER
        width = 0
        for _sw, text in rows:
            width = max(width, fm.horizontalAdvance(text))
        self._line_h = line_h
        self._text_x = text_x
        w = text_x + width + self._PAD
        h = self._PAD + line_h * len(rows) + self._PAD
        self.resize(int(w), int(h))
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        if not self._rows:
            return
        if self._mode == "light":
            bg, border, fg = QColor(255, 255, 255, 244), QColor("#c9c4be"), QColor("#2a2a2a")
            sw_border = QColor("#b8b3ad")
        else:
            bg, border, fg = QColor(34, 34, 34, 246), QColor("#4a4a4a"), QColor("#ececec")
            sw_border = QColor("#5a5a5a")
        from PyQt6.QtGui import QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(border, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 5, 5)

        from PyQt6.QtGui import QFontMetrics
        fm = QFontMetrics(self._font)
        y = self._PAD
        for i, (sw, text) in enumerate(self._rows):
            row_top = y + i * self._line_h
            baseline = row_top + fm.ascent() + 1
            if sw is not None:
                sy = row_top + (self._line_h - self._SWATCH) / 2.0
                p.setPen(QPen(sw_border, 1.0))
                p.setBrush(sw)
                p.drawRect(QRectF(self._PAD, sy, self._SWATCH, self._SWATCH))
            p.setFont(self._font_hdr if (i == 0 or sw is not None) else self._font)
            p.setPen(fg)
            p.drawText(int(self._text_x), int(baseline), text)
        p.end()


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class TiffPreview(QWidget):
    """Displays multi-page TIFF files with optional stripe highlight overlay."""

    # Emitted (with the new 0-based page index) when the shown page changes, so
    # observers like the margin inspector can re-measure the visible page.
    page_changed = pyqtSignal(int)
    # #126: user clicked a strip in the preview (page index, local stripe
    # index on that page). Only emitted while set_stripe_click_enabled(True).
    stripe_clicked = pyqtSignal(int, int)
    # #126 spot mode: user clicked a patch (page index, patch location id e.g.
    # "A12"). Only emitted while set_patch_click_enabled(True).
    patch_clicked = pyqtSignal(int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pages: list[tuple[Path, int]] = []   # (file_path, frame_index)
        self._current: int = 0
        self._active_stripe: int = -1
        self._bidirectional: bool = False
        self._stripe_rects: list[QRect] = []
        # #126 chart-reading engine overlays
        self._stripe_click_enabled: bool = False
        self._stripe_read_map: dict[int, bool] = {}
        self._hover_stripe: int = -1
        self._pan_dist: int = 0
        self._patch_overlay: dict[int, list] = {}
        # Exact per-patch pixel boxes per page (#126, Basti): lets the hover
        # outline hug only the patches of a strip — never the label band or the
        # white paper around them — for every layout, including ColorMunki
        # charts whose every-second strip is offset. Empty ⇒ hover falls back to
        # the full strip rect.
        self._page_patch_boxes: dict[int, list[QRect]] = {}
        # Leader/trailer edge-spacer height (px) for the strip-hover frame: a
        # chart with edge spacers brackets each strip with one spacer above the
        # first patch and one below the last, which the recorded patch geometry
        # omits — so the hover frame adds it back (#43). 0 ⇒ no edge spacers.
        self._edge_spacer_px: int = 0
        # Split-patch display: "both" (diagonal split), "expected" or
        # "measured" (whole patch one side). Switchable any time (#126, Knut).
        self._overlay_mode: str = "both"
        # "Show only measured patches" (#126, Knut): unread patches drawn white
        # with a thin outline so reading progress is obvious.
        self._show_only_measured: bool = False
        # Per-patch numbers for the hover info tile: {page: [(image-px QRect,
        # info-dict)]}, kept in lockstep with _patch_overlay. Empty ⇒ no tile.
        self._patch_info: dict[int, list] = {}
        # "Show patch values on hover": a small card near the pointer with the
        # expected/measured RGB + L*a*b* and ΔE of the patch underneath it.
        self._show_patch_tile: bool = False
        self._patch_tile: "_PatchInfoTile | None" = None
        # #126 spot (patch-by-patch) mode: the single patch to read next, drawn
        # with a bright highlight so the user knows where to place the
        # instrument; plus click-to-jump geometry (per page: {loc: image-px
        # QRect}) and the patch currently hovered for its jump outline.
        self._active_patch_box: "QRect | None" = None
        self._active_patch_page: int = -1
        self._patch_click_enabled: bool = False
        self._patch_click_pages: "list[dict[str, QRect]]" = []
        self._hover_patch_loc: str = ""
        # Chart path/name tooltip (shown on the caption/filename/image widgets).
        # Suppressed over the image during a measurement so it doesn't pop up
        # while swiping/inspecting patches (Basti).
        self._file_tooltip: str = ""
        self._suppress_file_tooltip: bool = False
        self.stripe_clicked_page = -1  # last emit bookkeeping (tests)
        self._stripe_arrow_mode: str = "base"
        # SpectroScan hexagonal charts: the strip highlight traces the column's
        # zigzag (staggered hexagons) instead of a straight rect, and the swipe
        # arrow is hidden (an XY table reads patch-by-patch — nothing to swipe).
        self._hex_zigzag: bool = False
        self._pixmap: QPixmap | None = None
        self._frame_color = QColor(Qt.GlobalColor.white)   # the margin around the image
        # Opt-in zoom/pan (soft-proof tool). Off elsewhere so the measure-tab
        # stripe overlay is untouched. _zoom 1.0 = fit-to-window; _pan is the
        # image-centre offset in logical px.
        self._interactive = False
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._panning = False
        self._pan_anchor = QPoint()
        self._ink_channels: list[str] | None = None
        # Margin-threshold guide lines: list of (axis, frac, violated) where
        # axis is "v"/"h" and frac is 0..1 of the image width/height. Drawn on
        # top of the preview only (never baked into the TIFF). Empty = none.
        self._margin_guides: list[tuple[str, float, bool]] = []
        # Measured-margin guide lines: (axis, frac) at the actual patch-area
        # edges, drawn as long purple/blue dots (a separate toggle).
        self._measured_guides: list[tuple[str, float]] = []
        # Coordinate readout on the pointer (#29, Knut): a cross-hair + the
        # cursor position in paper mm/inch, measured from the paper top-left.
        self._coord_readout: bool = False
        self._coord_dpi: float = 300.0
        # Resolution of each loaded page, read from the TIFF itself and cached
        # by page index — filled on demand, so a preview that never shows the
        # ruler pays nothing for it (#146).
        self._page_dpi: dict[int, "float | None"] = {}
        self._coord_pos: "QPoint | None" = None   # label-space cursor position
        self._cursor_overlay: "_CursorOverlay | None" = None
        self._mode: str = "dark"
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(_REFRESH_DELAY_MS)
        self._refresh_timer.timeout.connect(self._update_display)

        self._build_ui()
        # Reflect the empty state immediately: without this the Prev/Next buttons
        # keep their default (visible + enabled) look on a freshly-opened tab
        # until the first load/clear, so they appear active with no file loaded.
        self._update_nav()

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        """Switch between dark and light visuals (called by MainWindow.apply_theme)."""
        new_mode = "light" if mode == "light" else "dark"
        if new_mode == self._mode:
            return
        self._mode = new_mode
        self._apply_mode_styles()

    def _apply_mode_styles(self) -> None:
        if self._mode == "light":
            tooltip = _TOOLTIP_QSS_LIGHT
            caption_color  = "#7a7570"
            filename_color = "#7a7570"
            page_color     = "#7a7570"
            img_bg         = "#efebe6"
            img_border     = "#d0ccc6"
            img_text       = "#a8a4a0"
        else:
            tooltip = _TOOLTIP_QSS_DARK
            caption_color  = "#808080"
            filename_color = "#b8b8b8"
            page_color     = "#909090"
            img_bg         = "#111111"
            img_border     = "#333"
            img_text       = "#606060"
        self._caption_lbl.setStyleSheet(
            f"QLabel {{ color: {caption_color}; background: transparent; padding: 4px;"
            " font-family: Menlo; font-size: 9px; font-weight: 300; }"
            + tooltip
        )
        self._filename_lbl.setStyleSheet(
            f"QLabel {{ color: {filename_color}; background: transparent; padding: 0 8px 0 8px;"
            " font-family: Menlo; font-size: 11px; }"
            + tooltip
        )
        self._img_label.setStyleSheet(
            f"QLabel {{ background: {img_bg};"
            f" border: 1px solid {img_border};"
            " border-left: none;"
            f" color: {img_text};"
            " font-family: 'Menlo'; }"
            + tooltip
        )
        self._page_label.setStyleSheet(f"color: {page_color}; font-size: 12px;")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_tiff(self, paths: list[Path], ink_channels: list[str] | None = None,
                  preserve_view: bool = False) -> None:
        """Load a list of TIFF pages (one entry per printable page).

        ``preserve_view`` keeps the current zoom/pan (interactive mode) — used
        when only the *content* changes for the same image (e.g. the soft-proof
        re-rendering as options change), so the user isn't yanked back to fit.
        """
        self._ink_channels = ink_channels
        self._pages = []
        for p in paths:
            n = self._count_frames(p)
            if n == 0:
                log.warning("Cannot open TIFF %s", p)
                continue
            for i in range(n):
                self._pages.append((p, i))

        if not self._pages and paths:
            log.warning("TiffPreview: received %d path(s) but none could be opened: %s",
                        len(paths), [str(p) for p in paths])

        self._page_dpi = {}         # a new chart may render at another dpi
        self._current = 0
        self._active_stripe = -1
        self._stripe_rects = []
        self._stripe_arrow_mode = "base"
        if not preserve_view:       # a fresh image starts fit-to-window
            self._zoom = 1.0
            self._pan = QPointF(0.0, 0.0)
        self._update_nav()
        self._update_filename_label(paths)
        self._rebuild_ink_row()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._update_display)
        self._schedule_refresh()
        log.debug("TiffPreview: loaded %d page(s)", len(self._pages))

    def page_count(self) -> int:
        """Number of pages currently shown (one per printed sheet), or 0 when
        empty. The authoritative count of what the chart actually spans —
        printtarg may split a fixed layout across more sheets than the Pages
        control suggests (#73)."""
        return len(self._pages)

    def set_caption(self, text: str) -> None:
        """Set the small ALL-CAPS caption above the preview (e.g. 'PRINT PREVIEW')."""
        self._caption_lbl.setText(text)
        self._caption_lbl.setVisible(bool(text))

    def set_notice(self, text: str | None) -> None:
        """Show an advisory notice at the bottom of the preview (same style as
        the render badge), or hide it (text=None/empty)."""
        if text:
            self._notice_lbl.setText(text)
            self._notice_lbl.setVisible(True)
        else:
            self._notice_lbl.clear()
            self._notice_lbl.setVisible(False)

    def set_frame_color(self, color: "QColor | None") -> None:
        """Tint the margin drawn around the image (e.g. to the simulated paper
        white). ``None`` restores plain white. Repaints if an image is shown."""
        self._frame_color = QColor(color) if color is not None else QColor(Qt.GlobalColor.white)
        if self._pixmap:
            self._repaint_label()

    def set_margin_guides(
        self, guides: "list[tuple[str, float, bool]] | None"
    ) -> None:
        """Set dotted margin-threshold guide lines drawn over the preview.

        Each guide is ``(axis, frac, violated)``: ``axis`` "v" draws a vertical
        line at ``frac`` of the image width, "h" a horizontal line at ``frac``
        of the height; ``violated`` paints it red instead of the neutral
        black/white dash. Drawn on the display only — never into the TIFF.
        Pass ``None`` or an empty list to clear.
        """
        self._margin_guides = list(guides or [])
        if self._pixmap:
            self._repaint_label()

    def set_measured_guides(self, guides: "list[tuple[str, float]] | None") -> None:
        """Long purple/blue dotted lines at the measured margins (patch-area
        edges). Each guide is ``(axis, frac)``. Pass None/empty to clear."""
        self._measured_guides = list(guides or [])
        if self._pixmap:
            self._repaint_label()

    def set_coord_readout(self, on: bool, dpi: float | None = None) -> None:
        """Turn the pointer coordinate readout on/off (#29, Knut).

        Image pixels convert to paper millimetres through the resolution of the
        page on screen, which is read from the TIFF itself. *dpi* is only the
        fallback for a page that carries no resolution tag — do not rely on it
        to describe a chart, because the caller's idea of the resolution and the
        chart's own can differ (#146).

        ChromIQ renders every chart with printtarg ``-M`` / a full-sheet engine
        page, so image pixel (0, 0) is the paper's top-left corner.
        """
        self._coord_readout = bool(on)
        if dpi and dpi > 0:
            self._coord_dpi = float(dpi)
        if not self._coord_readout:
            self._coord_pos = None
        # Mouse tracking so the readout follows the pointer without a button held.
        self.setMouseTracking(True)
        if self._img_label is not None and not sip.isdeleted(self._img_label):
            self._img_label.setMouseTracking(True)
            if self._coord_readout and self._cursor_overlay is None:
                self._cursor_overlay = _CursorOverlay(self._img_label)
            if self._cursor_overlay is not None:
                self._sync_cursor_overlay_geometry()
                self._cursor_overlay.setVisible(self._coord_readout)
                if not self._coord_readout:
                    self._cursor_overlay.show_cursor(None, None)

    def _sync_cursor_overlay_geometry(self) -> None:
        """Keep the cursor overlay covering the whole image label, so its
        coordinates equal the label's (no offset) and it sits over the chart."""
        ov = self._cursor_overlay
        if ov is None or self._img_label is None or sip.isdeleted(self._img_label):
            return
        ov.setGeometry(0, 0, self._img_label.width(), self._img_label.height())
        ov.raise_()

    @staticmethod
    def _read_page_dpi(path) -> "float | None":
        """The resolution baked into a page TIFF, or None when it carries none.

        Reuses the margin inspector's reader, so the pointer ruler and the
        measured-margins panel convert pixels to millimetres through exactly the
        same number and can never disagree (#146). Imported lazily: this widget
        is created long before anything needs numpy/tifffile.
        """
        try:
            from workflow.margin_inspector import _tiff_dpi
            dpi = _tiff_dpi(Path(path), 0.0)
            return dpi if dpi > 1.0 else None
        except Exception as exc:            # unreadable / not a TIFF at all
            log.debug("TiffPreview: no resolution in %s: %s", path, exc)
            return None

    def _current_page_dpi(self) -> float:
        """Resolution of the page on screen: the TIFF's own, falling back to the
        value the caller supplied.

        The page's own tag has to win. The fallback used to be the only source,
        and it is the *current* "Resolution" preference — which says nothing
        about a chart generated earlier, or by a preset that renders at another
        resolution. A 200 dpi chart read as 300 put the bottom-right corner of
        an A4 sheet at 140.0 x 198.0 mm instead of 210 x 297 (Knut, #146).
        """
        idx = self._current
        if 0 <= idx < len(self._pages):
            if idx not in self._page_dpi:
                self._page_dpi[idx] = self._read_page_dpi(self._pages[idx][0])
            dpi = self._page_dpi[idx]
            if dpi and dpi > 0:
                return float(dpi)
        return float(self._coord_dpi)

    def _coord_mm_at(self, label_pos) -> "tuple[float, float] | None":
        """Paper (x, y) in mm at a label-space position, from the paper's
        top-left corner. Uses the current fit/zoom/pan transform; values may be
        negative or past the sheet when the pointer is off the paper — that is
        intentional, so the ruler still reads there."""
        dpi = self._current_page_dpi()
        if self._paint_geom is None or dpi <= 0:
            return None
        scale, ox, oy = self._paint_geom
        if scale <= 0:
            return None
        ix = (label_pos.x() - ox) / scale      # image pixels (may be off-sheet)
        iy = (label_pos.y() - oy) / scale
        k = 25.4 / dpi
        return ix * k, iy * k

    def set_navigation_visible(self, visible: bool) -> None:
        """Hide the page count + Prev/Next bar for single-image use (e.g. the
        soft-proof tool, which only ever shows one image at a time)."""
        self._nav.setVisible(visible)
        self._image_nav_gap.setVisible(visible)

    # ------------------------------------------------------------------
    # Zoom / pan (opt-in) — wheel zoom, middle-drag pan, keyboard (#65)
    # ------------------------------------------------------------------
    def set_interactive(self, on: bool) -> None:
        """Enable wheel-zoom + drag-pan + keyboard zoom/pan on the image."""
        self._interactive = on
        if on:
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self._img_label.setMouseTracking(True)

    def reset_view(self) -> None:
        """Back to fit-to-window, centred."""
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._repaint_label()

    def _apply_zoom(self, factor: float, focus: QPoint | None = None) -> None:
        """Multiply the zoom by ``factor``, keeping the image point under
        ``focus`` (label-viewport coords) fixed; clamp to [1, 8]."""
        new_zoom = max(1.0, min(8.0, self._zoom * factor))
        if new_zoom == self._zoom:
            return
        if focus is not None:
            # Keep the point under the cursor stationary while scaling.
            B = _BORDER
            cx = (self._img_label.width() - 2 * B) / 2
            cy = (self._img_label.height() - 2 * B) / 2
            rel = QPointF(focus.x() - B - cx, focus.y() - B - cy)
            ratio = new_zoom / self._zoom
            self._pan = QPointF(rel.x() - (rel.x() - self._pan.x()) * ratio,
                                rel.y() - (rel.y() - self._pan.y()) * ratio)
        self._zoom = new_zoom
        self._repaint_label()

    def set_banner(self, text: str | None) -> None:
        """Show an advisory banner above the image, or hide it (text=None/empty)."""
        if text:
            self._banner_lbl.setText(text)
            self._banner_lbl.setVisible(True)
        else:
            self._banner_lbl.clear()
            self._banner_lbl.setVisible(False)

    def _update_filename_label(self, paths: list[Path]) -> None:
        """Show the chart stem of the loaded files; full path on hover.

        Toggles the header→image spacer and broadcasts the tooltip to the
        caption, filename, and image labels so users find the hover info
        wherever they happen to point at.
        """
        if not paths:
            self._filename_lbl.clear()
            self._filename_lbl.setVisible(False)
            self._header_image_gap.setVisible(False)
            self._file_tooltip = ""
            for w in (self._caption_lbl, self._filename_lbl, self._img_label):
                w.setToolTip("")
                w.unsetCursor()
            return
        first = paths[0]
        stem = re.sub(r"_(\d{1,3})$", "", first.stem)
        self._filename_lbl.setText(self._elide_middle(stem, 60))
        try:
            folder = first.resolve().parent
        except Exception:
            folder = first.parent
        self._file_tooltip = "\n".join([f"Folder: {folder}", "",
                                        *(p.name for p in paths)])
        self._apply_file_tooltip()
        # Help cursor on the header text only — image gets a tooltip but keeps
        # its arrow cursor so it doesn't suggest the dark area itself is clickable.
        self._caption_lbl.setCursor(Qt.CursorShape.WhatsThisCursor)
        self._filename_lbl.setCursor(Qt.CursorShape.WhatsThisCursor)
        self._filename_lbl.setVisible(True)
        self._header_image_gap.setVisible(True)

    def eventFilter(self, obj, ev):  # noqa: N802
        """Show the chart-file tooltip in a tip label of OUR OWN.

        Qt keeps one shared tooltip label and reuses it while it is still on
        screen — including while it is fading out on macOS. Arriving here
        straight from a widget with a long tooltip (e.g. the Run-type box in
        the bar) therefore showed the small folder/filename tooltip inside
        the previous tooltip's much larger box, and hiding first only traded
        that for a flicker, because the fade keeps the label alive (Basti,
        2026-08-10, twice). An owned label is measured for its own text every
        time, so no other tooltip can lend it a size."""
        from PyQt6.QtCore import QEvent as _QEvent
        if obj in (self._caption_lbl, self._filename_lbl, self._img_label):
            t = ev.type()
            if t == _QEvent.Type.ToolTip:
                tip = obj.toolTip()
                if tip:
                    self._show_file_tip(ev.globalPos(), tip)
                else:
                    self._hide_file_tip()
                return True          # never let the shared label show these
            if t in (_QEvent.Type.Leave, _QEvent.Type.MouseButtonPress,
                     _QEvent.Type.Wheel, _QEvent.Type.Hide,
                     _QEvent.Type.WindowDeactivate):
                self._hide_file_tip()
        return super().eventFilter(obj, ev)

    def _show_file_tip(self, global_pos, text: str) -> None:
        from PyQt6.QtCore import QPoint, QTimer
        from PyQt6.QtWidgets import QApplication, QToolTip
        # A tooltip carried over from another widget may still be on screen —
        # and hideText() only STARTS the macOS fade-out, which leaves the old
        # (often much larger) box hanging over ours for a split second. Close
        # the shared tip label outright instead; measured on screen,
        # 2026-08-10.
        QToolTip.hideText()
        for w in QApplication.topLevelWidgets():
            if w.metaObject().className() == "QTipLabel":
                w.close()
        lbl = getattr(self, "_file_tip_lbl", None)
        if lbl is None:
            lbl = QLabel(self.window())
            lbl.setObjectName("file_tip")
            lbl.setWindowFlags(Qt.WindowType.ToolTip
                               | Qt.WindowType.FramelessWindowHint)
            lbl.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            lbl.setTextFormat(Qt.TextFormat.PlainText)
            self._file_tip_lbl = lbl
            self._file_tip_timer = QTimer(self)
            self._file_tip_timer.setSingleShot(True)
            self._file_tip_timer.timeout.connect(self._hide_file_tip)
        if self._mode == "light":
            lbl.setStyleSheet(
                "QLabel { background-color: #ffffff; color: #22211f;"
                " border: 1px solid #d0ccc6; padding: 4px; }")
        else:
            lbl.setStyleSheet(
                "QLabel { background-color: #262626; color: #e6e6e6;"
                " border: 1px solid #404040; padding: 4px; }")
        lbl.setText(text)
        lbl.adjustSize()
        pos = global_pos + QPoint(12, 16)
        screen = QApplication.screenAt(global_pos)
        if screen is not None:
            area = screen.availableGeometry()
            if pos.x() + lbl.width() > area.right():
                pos.setX(max(area.left(), area.right() - lbl.width()))
            if pos.y() + lbl.height() > area.bottom():
                pos.setY(global_pos.y() - lbl.height() - 12)
        lbl.move(pos)
        lbl.show()
        lbl.raise_()
        # Same idea as Qt's own display time: longer text stays longer.
        self._file_tip_timer.start(min(10000, 3000 + 30 * len(text)))

    def _hide_file_tip(self) -> None:
        lbl = getattr(self, "_file_tip_lbl", None)
        if lbl is not None and lbl.isVisible():
            lbl.hide()
        timer = getattr(self, "_file_tip_timer", None)
        if timer is not None:
            timer.stop()

    def _apply_file_tooltip(self) -> None:
        """Push the stored chart-file tooltip to the caption/filename/image
        widgets, honouring :meth:`set_suppress_file_tooltip`. While a
        measurement runs the tooltip is dropped from the IMAGE only — so it
        never pops up over the chart while you swipe or inspect patches — but
        stays on the header text, where the file is still easy to check."""
        tip = self._file_tooltip
        self._caption_lbl.setToolTip(tip)
        self._filename_lbl.setToolTip(tip)
        hide_over_image = (self._suppress_file_tooltip
                           or getattr(self, "_show_patch_tile", False))
        self._img_label.setToolTip("" if hide_over_image else tip)

    def set_suppress_file_tooltip(self, on: bool) -> None:
        """Hide the chart path/name tooltip over the image while `on` (used to
        keep it out of the way during a measurement) (Basti)."""
        on = bool(on)
        if on != self._suppress_file_tooltip:
            self._suppress_file_tooltip = on
            self._apply_file_tooltip()

    @staticmethod
    def _elide_middle(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        keep = max_len - 1
        head = keep // 2
        tail = keep - head
        return f"{text[:head]}…{text[-tail:]}"

    def highlight_stripe(self, stripe_index: int) -> None:
        """Highlight a strip (0-based) in the current preview page."""
        self._active_stripe = stripe_index
        self._schedule_refresh()

    def set_bidirectional(self, enabled: bool) -> None:
        """Toggle the second (bottom, upward-pointing) strip arrow."""
        if self._bidirectional == enabled:
            return
        self._bidirectional = enabled
        self._schedule_refresh()

    # ------------------------------------------------------------------
    # ChromIQ chart-reading engine overlays (#126)
    # ------------------------------------------------------------------

    def set_stripe_click_enabled(self, on: bool,
                                 read_map: "dict[int, bool] | None" = None) -> None:
        """Enable click-to-jump: hovering a known stripe shows a pointing
        hand + tooltip, clicking emits stripe_clicked(page, local_index).
        `read_map` marks stripes already measured (affects the tooltip)."""
        self._stripe_click_enabled = on
        self._stripe_read_map = read_map or {}
        if not on:
            self._hover_stripe = -1
            self.unsetCursor()
        self._schedule_refresh()

    def set_stripe_read_map(self, read_map: "dict[int, bool]") -> None:
        self._stripe_read_map = dict(read_map)

    # ---- spot (patch-by-patch) mode --------------------------------------
    def highlight_patch(self, page: int, box: "QRect | None") -> None:
        """Highlight the single patch to be read next (engine spot mode). The
        highlight shows only while `page` is the visible page; pass box=None to
        clear it."""
        self._active_patch_box = box
        self._active_patch_page = page if box is not None else -1
        self._schedule_refresh()

    def set_patch_click_enabled(self, on: bool,
                                pages: "list[dict[str, QRect]] | None" = None) -> None:
        """Enable click-to-jump in spot mode: clicking a patch emits
        patch_clicked(page, loc). `pages` is a per-page list of {loc: image-px
        QRect}; when omitted the previous geometry is kept."""
        self._patch_click_enabled = on
        if pages is not None:
            self._patch_click_pages = list(pages)
        if not on:
            self._hover_patch_loc = ""
            self._active_patch_box = None
            self._active_patch_page = -1
            self.unsetCursor()
        self._schedule_refresh()

    def _patch_at(self, widget_pos) -> "tuple[str, QRect] | None":
        """The (loc, image-px rect) of the patch under a widget-space point, or
        None. Uses the current page's click geometry."""
        if self._pixmap is None or not (0 <= self._current < len(self._patch_click_pages)):
            return None
        boxes = self._patch_click_pages[self._current]
        if not boxes:
            return None
        label_pos = self._img_label.mapFrom(self, widget_pos)
        px = self._image_px_at(label_pos)
        if px is None:
            return None
        ix, iy = px
        for loc, rect in boxes.items():
            if rect.contains(ix, iy):
                return loc, rect
        return None

    def set_patch_overlay(self, page: int,
                          items: "list[tuple[QRect, QColor, QColor, bool]]",
                          replace_page: bool = False) -> None:
        """Add split-patch results for `page`: each item is (image-px rect,
        expected colour, measured colour, warn). Drawn as an i1Profiler-style
        corner-to-corner split — expected upper-left, measured lower-right —
        with a red outline when warn is set."""
        if replace_page or page not in self._patch_overlay:
            self._patch_overlay[page] = list(items)
        else:
            # Re-measuring a strip must REPLACE its patches' results, not stack a
            # second copy on top: drop any existing entry whose box matches one of
            # the incoming patches, then add the new ones. So measuring different
            # strips accumulates, but re-reading the same strip refreshes it (no
            # duplicates, no stale warning outline) (Basti).
            new_boxes = {(r.x(), r.y(), r.width(), r.height()) for r, *_ in items}
            self._patch_overlay[page] = [
                it for it in self._patch_overlay[page]
                if (it[0].x(), it[0].y(), it[0].width(), it[0].height()) not in new_boxes
            ] + list(items)
        self._schedule_refresh()

    def clear_patch_overlay(self) -> None:
        self._patch_overlay = {}
        self._patch_info = {}
        self._hide_patch_tile()
        self._schedule_refresh()

    def set_patch_info(self, page: int,
                       items: "list[tuple[QRect, dict]]",
                       replace_page: bool = False) -> None:
        """Per-patch numbers for the hover info tile on `page`: each item is
        (image-px rect, info-dict with loc / exp_rgb / meas_rgb / exp_lab /
        meas_lab / de). Kept in lockstep with :meth:`set_patch_overlay` — the
        same accumulate/replace-by-box rule, so re-reading a strip refreshes its
        patches' numbers instead of stacking a stale copy (#126 follow-up)."""
        if replace_page or page not in self._patch_info:
            self._patch_info[page] = list(items)
        else:
            new_boxes = {(r.x(), r.y(), r.width(), r.height()) for r, _ in items}
            self._patch_info[page] = [
                it for it in self._patch_info[page]
                if (it[0].x(), it[0].y(), it[0].width(), it[0].height()) not in new_boxes
            ] + list(items)

    def set_show_patch_tile(self, on: bool) -> None:
        """Turn the hover info tile on/off. When off, any visible tile hides at
        once; when on, it appears the next time the pointer is over a measured
        patch (#126 follow-up, Basti).

        Turning it on also drops the chart path/name tooltip from the image:
        the two appear in the same place, and the tooltip kept popping up on top
        of the patch values you were trying to read (Knut, #131 2026-07-26).
        """
        self._show_patch_tile = bool(on)
        if not self._show_patch_tile:
            self._hide_patch_tile()
        self._apply_file_tooltip()

    def _ensure_patch_tile(self) -> "_PatchInfoTile":
        if self._patch_tile is None:
            self._patch_tile = _PatchInfoTile(self)
        return self._patch_tile

    def _hide_patch_tile(self) -> None:
        # Guard on isHidden() (the explicit shown/hidden flag), not isVisible()
        # (which also goes False when the parent is hidden) — so the tile is
        # reliably taken down whenever it isn't already down.
        if self._patch_tile is not None and not self._patch_tile.isHidden():
            self._patch_tile.hide()

    def _update_patch_tile(self, pos: QPoint) -> None:
        """Show/move/hide the hover info tile for the patch under `pos` (a point
        in this widget's own coordinates)."""
        if not self._show_patch_tile or self._pixmap is None:
            self._hide_patch_tile()
            return
        info_items = self._patch_info.get(self._current)
        if not info_items:
            self._hide_patch_tile()
            return
        label_pos = self._img_label.mapFrom(self, pos)
        px = self._image_px_at(label_pos)
        if px is None:
            self._hide_patch_tile()
            return
        ix, iy = px
        hit = None
        for rect, info in info_items:
            if rect.contains(ix, iy):
                hit = info
                break
        if hit is None:
            self._hide_patch_tile()
            return
        tile = self._ensure_patch_tile()
        tile.set_theme(self._mode)
        tile.set_content(hit, self._overlay_mode)
        tw, th = tile.width(), tile.height()
        # Sit just off the pointer, but flip/clamp so the whole card stays inside
        # the preview instead of being cut off at an edge.
        x = pos.x() + 18
        y = pos.y() + 18
        if x + tw > self.width():
            x = pos.x() - 18 - tw
        if y + th > self.height():
            y = pos.y() - 18 - th
        x = max(2, min(x, self.width() - tw - 2))
        y = max(2, min(y, self.height() - th - 2))
        tile.move(int(x), int(y))
        tile.raise_()
        tile.show()

    def set_page_patch_boxes(self, mapping: "dict[int, list[QRect]]") -> None:
        """Exact per-patch pixel boxes per page (#126, Basti).

        Used to draw the click-to-jump hover outline tightly around a strip's
        patches only — not the label band above them, not the white paper to
        either side. Taken straight from the chart geometry (``strips.json`` /
        ``channels.json``), so it's pixel-exact for every layout, including
        ColorMunki charts whose every-second strip is offset. Pass ``{}`` to
        clear (the hover then falls back to the full strip rectangle)."""
        self._page_patch_boxes = dict(mapping or {})
        self._schedule_refresh()

    def set_edge_spacer_px(self, px: int) -> None:
        """Height of a leader/trailer edge spacer in image px, or 0 when the
        chart has none — used to grow the strip-hover frame over the spacers that
        bracket each strip (#43). Read from the chart geometry by the caller."""
        self._edge_spacer_px = max(0, int(px or 0))

    def set_hex_zigzag(self, on: bool) -> None:
        """Enable the hexagonal-column highlight mode (SpectroScan hex charts):
        the strip outline follows the staggered hexagon zigzag and the swipe
        arrow is suppressed. No-op change is ignored to avoid needless repaints."""
        on = bool(on)
        if on != self._hex_zigzag:
            self._hex_zigzag = on
            self._repaint_label()

    def _strip_patches(self, strip_rect: QRect) -> "list[QRect]":
        """The current page's patch boxes belonging to *strip_rect*, top→bottom.

        Membership is by centre-x (a patch belongs to the column its centre sits
        in), so the staggered hex patches — which overhang ±¼ patch on alternate
        rows — are still assigned to the right column."""
        boxes = self._page_patch_boxes.get(self._current) or []
        col = [b for b in boxes
               if strip_rect.left() <= b.x() + b.width() / 2 <= strip_rect.right()]
        col.sort(key=lambda b: b.y())
        return col

    def _strip_zigzag_path(self, strip_rect: QRect, s: float,
                           ox: float, oy: float) -> "QPainterPath | None":
        """A single closed outline following the actual hexagonal patches of a
        strip and their ±¼-patch zigzag — one frame for the whole column, not a
        straight rect that spills into the neighbour (nor a frame per patch).
        Returns None when the strip exposes no per-patch geometry."""
        col = self._strip_patches(strip_rect)
        if not col:
            return None
        # The hexagons tessellate edge-to-edge (zero overlap area), so a boolean
        # union can't merge them — it leaves each as its own closed loop, drawing
        # little frames around patch pairs (Basti). Trace the column's OUTER
        # boundary by hand instead: down every hexagon's left edge, across the
        # last hexagon's bottom apex, up every right edge, and close over the
        # first hexagon's top apex. The intermediate apexes are internal seams,
        # correctly omitted, so it's a single clean hexagon-zigzag outline.
        def verts(b: QRect):
            left, right = b.left(), b.right() + 1
            cx = b.x() + b.width() / 2.0
            y0, h = b.y(), b.height()
            t6 = h / 6.0
            return {
                "top": (cx, y0 - t6), "ur": (right, y0 + t6),
                "lr": (right, y0 + 5 * t6), "bot": (cx, y0 + h + t6),
                "ll": (left, y0 + 5 * t6), "ul": (left, y0 + t6),
            }

        def X(v: float) -> float:
            return v * s + ox

        def Y(v: float) -> float:
            return v * s + oy

        path = QPainterPath()
        first, last = verts(col[0]), verts(col[-1])
        path.moveTo(X(first["top"][0]), Y(first["top"][1]))
        for b in col:                                   # left side, top → bottom
            v = verts(b)
            path.lineTo(X(v["ul"][0]), Y(v["ul"][1]))
            path.lineTo(X(v["ll"][0]), Y(v["ll"][1]))
        path.lineTo(X(last["bot"][0]), Y(last["bot"][1]))
        for b in reversed(col):                         # right side, bottom → top
            v = verts(b)
            path.lineTo(X(v["lr"][0]), Y(v["lr"][1]))
            path.lineTo(X(v["ur"][0]), Y(v["ur"][1]))
        path.closeSubpath()
        return path

    @staticmethod
    def _patch_hexagon(b: QRect, s: float, ox: float, oy: float) -> "QPainterPath":
        """A closed hexagon outline for a single SpectroScan patch box, matching
        the same pointy-top/flat-side geometry the strip zigzag uses. Used to
        draw unread hex patches as their true shape in "Show only measured
        patches" (Knut) — a rectangle grid there is wrong for a hex chart."""
        left, right = b.left(), b.right() + 1
        cx = b.x() + b.width() / 2.0
        y0, h = b.y(), b.height()
        t6 = h / 6.0

        def X(v: float) -> float:
            return v * s + ox

        def Y(v: float) -> float:
            return v * s + oy

        path = QPainterPath()
        path.moveTo(X(cx), Y(y0 - t6))               # top apex
        path.lineTo(X(right), Y(y0 + t6))            # upper right
        path.lineTo(X(right), Y(y0 + 5 * t6))        # lower right
        path.lineTo(X(cx), Y(y0 + h + t6))           # bottom apex
        path.lineTo(X(left), Y(y0 + 5 * t6))         # lower left
        path.lineTo(X(left), Y(y0 + t6))             # upper left
        path.closeSubpath()
        return path

    def _hover_patch_bounds(self, strip_rect: QRect) -> "QRect | None":
        """Bounding box of just the patches of the strip at *strip_rect* on the
        current page, or None when no per-patch geometry is known.

        A strip is one vertical column of patches, so a patch belongs to it when
        its centre-x falls in the strip's x-span. We deliberately do NOT bound by
        y: on ColorMunki "offset every second strip" charts the odd strips are
        shifted down, so their last patch hangs below the strip rect's bottom —
        a y-test would clip it off (Basti). The resulting box therefore always
        spans exactly the strip's patches, top patch to bottom patch, and never
        the label band above or the white paper to either side."""
        boxes = self._page_patch_boxes.get(self._current)
        if not boxes:
            return None
        union: "QRect | None" = None
        for b in boxes:
            cx = b.x() + b.width() / 2
            if strip_rect.left() <= cx <= strip_rect.right():
                union = b if union is None else union.united(b)
        if union is not None and self._edge_spacer_px > 0:
            # Grow over the leader/trailer edge spacers that bracket the strip
            # (one spacer above the first patch, one below the last) — they're
            # part of the swiped strip but absent from the patch geometry (#43).
            sp = self._edge_spacer_px
            union = QRect(union.x(), union.y() - sp,
                          union.width(), union.height() + 2 * sp)
        return union

    def set_overlay_mode(self, mode: str) -> None:
        """How the split-patch overlay draws: "both" (expected ◤ / measured ◢
        diagonal split), "expected" (whole patch = expected colour) or
        "measured" (whole patch = measured colour). Applies immediately, at any
        point during or after a measurement (#126, Knut)."""
        if mode not in ("both", "expected", "measured"):
            mode = "both"
        if mode != self._overlay_mode:
            self._overlay_mode = mode
            # Repaint the overlay immediately (no TIFF reload) so the switch is
            # instant — the split/expected/measured view is just a redraw.
            if self._pixmap is not None:
                self._repaint_label()
            else:
                self._schedule_refresh()

    def overlay_mode(self) -> str:
        return self._overlay_mode

    def set_show_only_measured(self, on: bool) -> None:
        """Blank unread patches to white (thin outline) so reading progress is
        obvious; the measured split patches still draw on top (#126, Knut).
        Applies immediately."""
        on = bool(on)
        if on != self._show_only_measured:
            self._show_only_measured = on
            if self._pixmap is not None:
                self._repaint_label()
            else:
                self._schedule_refresh()

    def has_patch_overlay(self) -> bool:
        return bool(self._patch_overlay)

    def _stripe_at(self, widget_pos) -> int:
        """Local stripe index under a widget position, or -1."""
        if not (self._stripe_click_enabled and self._stripe_rects):
            return -1
        pos = self._img_label.mapFrom(self, widget_pos)
        px = self._image_px_at(pos)
        if px is None:
            return -1
        ix, iy = px
        for i, r in enumerate(self._stripe_rects):
            if r.left() <= ix <= r.right() and r.top() <= iy <= r.bottom():
                return i
        return -1

    def stripe_x_centres(self) -> "list[int]":
        """The horizontal centre of every stripe on the current page, in **this
        widget's** coordinates — index-aligned with the stripe rects.

        Used to line the per-strip reading times up underneath the strips they
        belong to (#131, Knut 2026-07-26): the times have to sit exactly where
        the strip labels do, whatever the zoom or page size. Empty when the page
        has not been laid out yet, so a caller can simply skip drawing.
        """
        from PyQt6.QtCore import QPoint
        if self._paint_geom is None or not self._stripe_rects:
            return []
        scale, ox, oy = self._paint_geom
        if scale <= 0:
            return []
        out = []
        for r in self._stripe_rects:
            label_x = int(r.center().x() * scale + ox)
            out.append(self._img_label.mapTo(self, QPoint(label_x, 0)).x())
        return out

    def set_stripe_rects(self, rects: list[QRect],
                         arrow_mode: str = "base") -> None:
        """Provide precomputed pixel rects for each stripe on current page.

        *arrow_mode* "base" draws the scan arrow pointing down FROM the rect
        top (the anchor is a label-band bottom — printtarg charts and engine
        charts with strip labels). "tip" floats the arrow ABOVE the rect top
        with its tip a tiny gap over the patches — engine charts without
        strip labels, where there is no label band to hang from.

        RECTS ARE CLAMPED TO THE PAGE. A chart carrying no engine geometry
        (one made before the layout engine, or in another program) has its
        strips DETECTED from the page image instead, and that detector can
        return a rect reaching past the paper: measured 3516 px on a 3508 px
        page (2026-08-13). Everything anchored to a strip inherits the error —
        the scan arrow, the measured-patch blanking, and the overlay legend,
        which is where it surfaced. Clamping here covers all of them, because
        this is the one door every source comes through.
        """
        self._stripe_rects = rects
        self._stripe_arrow_mode = arrow_mode
        self._clamp_stripe_rects_to_page()

    def _clamp_stripe_rects_to_page(self) -> None:
        """Trim the strip rects to the page, whenever the page is known.

        Called from :meth:`set_stripe_rects` AND from the render, because the
        page image is built by a deferred timer: rects usually arrive BEFORE
        there is a pixmap to measure against, so clamping only in the setter
        silently did nothing (caught while testing the fix itself, 2026-08-13).
        Idempotent, so running it on every render costs nothing once the rects
        already fit.
        """
        page = self._pixmap
        if page is None or not self._stripe_rects:
            return
        pw, ph = page.width(), page.height()
        fixed = []
        for r in self._stripe_rects:
            x = max(0, min(r.x(), pw))
            y = max(0, min(r.y(), ph))
            fixed.append(QRect(x, y,
                               max(1, min(r.width(), pw - x)),
                               max(1, min(r.height(), ph - y))))
        self._stripe_rects = fixed

    def show_page(self, index: int) -> None:
        """Switch to page by index and repaint."""
        if 0 <= index < len(self._pages) and index != self._current:
            self._current = index
            self._active_stripe = -1
            self._hide_patch_tile()   # its patch is on the page we just left
            self._update_nav()
            self._schedule_refresh()
            self.page_changed.emit(self._current)

    def reset_ink_inspector(self) -> None:
        """Hide the per-ink row + badge immediately (#72, Basti): called when
        a chart build starts, so options from the previous chart never linger
        while the new one is generated; load_tiff rebuilds them for the new
        chart's ink set."""
        self._ink_row.setVisible(False)
        self._ink_readout.setText("")
        self._ink_badge.setVisible(False)
        if getattr(self, "_badge_lbl", None) is not None:
            self._badge_lbl.setVisible(False)

    def clear(self) -> None:
        self.reset_ink_inspector()
        self._pages = []
        self._current = 0
        self._active_stripe = -1
        self._bidirectional = False
        self._stripe_rects = []
        self._stripe_arrow_mode = "base"
        self._page_patch_boxes = {}
        self._patch_info = {}
        self._hide_patch_tile()
        self._pixmap = None
        self._ink_channels = None
        self._img_label.setText(tr("No preview"))
        self._update_nav()
        self._update_filename_label([])

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header: caption (set by parent tab) + active filename (auto-updated).
        # Spacers below are explicit so the header→image gap only appears when
        # a filename is showing — caption alone hugs the image like the
        # pre-load layout did.
        header = QWidget(self)
        hl = QVBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        self._caption_lbl = QLabel("", header)
        self._caption_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption_lbl.setStyleSheet(
            "QLabel { color: #808080; background: transparent; padding: 4px;"
            " font-family: Menlo; font-size: 9px; font-weight: 300; }"
            + _TOOLTIP_QSS
        )
        self._caption_lbl.setVisible(False)
        hl.addWidget(self._caption_lbl)

        self._filename_lbl = QLabel("", header)
        self._filename_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._filename_lbl.setStyleSheet(
            "QLabel { color: #b8b8b8; background: transparent; padding: 0 8px 0 8px;"
            " font-family: Menlo; font-size: 11px; }"
            + _TOOLTIP_QSS
        )
        self._filename_lbl.setVisible(False)
        hl.addWidget(self._filename_lbl)

        # Advisory banner — shown only when something noteworthy needs to be
        # communicated about the preview (e.g. i1iSis layout-only preview).
        # Hidden by default so it consumes no vertical space.
        self._banner_lbl = QLabel("", header)
        self._banner_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner_lbl.setWordWrap(True)
        self._banner_lbl.setStyleSheet(
            "QLabel { color: #2a1a00; background: #f0c674;"
            " border: 1px solid #b88a2a; border-radius: 4px;"
            " padding: 6px 10px; margin: 6px 4px 0 4px;"
            " font-size: 11px; }"
        )
        self._banner_lbl.setVisible(False)
        hl.addWidget(self._banner_lbl)

        layout.addWidget(header)

        # Gap between header and image — only shown when a filename is present
        self._header_image_gap = QWidget(self)
        self._header_image_gap.setFixedHeight(12)
        self._header_image_gap.setVisible(False)
        layout.addWidget(self._header_image_gap)

        # Image label
        self._img_label = QLabel(tr("No preview"), self)
        # The file tooltip on these three is shown through eventFilter, so a
        # tooltip carried over from another widget can never lend it its size.
        for _w in (self._caption_lbl, self._filename_lbl, self._img_label):
            _w.installEventFilter(self)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._img_label.setStyleSheet(
            "QLabel { background: #111111;"
            " border: 1px solid #333;"
            " border-left: none;"
            " color: #606060;"
            " font-family: 'Menlo'; }"
            + _TOOLTIP_QSS
        )
        _lbl_font = self._img_label.font()
        _lbl_font.setCapitalization(QFont.Capitalization.AllUppercase)
        self._img_label.setFont(_lbl_font)
        self._img_label.setMinimumSize(200, 200)
        layout.addWidget(self._img_label, stretch=1)

        # Per-ink inspector for device-native (separated) charts (#72 Tier D):
        # mute checkboxes recomposite the preview from the remaining inks, and
        # the readout shows the exact ink values under the cursor — the file's
        # real numbers, straight from the channel data.
        self._muted_inks: set[int] = set()
        self._ink_checks: list = []
        self._ink_page_data = None      # (H, W, n) uint8 of the current page
        self._ink_page_key = None
        self._paint_geom = None         # (scale, x, y): image px → label px
        self._ink_row = QWidget(self)
        _ink_l = QHBoxLayout(self._ink_row)
        _ink_l.setContentsMargins(8, 2, 8, 2)
        _ink_l.setSpacing(8)
        self._ink_row_label = QLabel(tr("Inks:"), self._ink_row)
        _ink_l.addWidget(self._ink_row_label)
        self._ink_checks_bar = QHBoxLayout()
        self._ink_checks_bar.setSpacing(6)
        _ink_l.addLayout(self._ink_checks_bar)
        _ink_l.addStretch(1)
        self._ink_readout = QLabel("", self._ink_row)
        self._ink_readout.setStyleSheet(
            "QLabel { color: #808080; font-family: 'Menlo'; }")
        _ink_l.addWidget(self._ink_readout)
        # The honesty badge shares this line whenever the ink row is shown
        # (Basti) — the floating overlay is only the fallback for
        # device-native pages without a known ink set.
        self._ink_badge = QLabel("", self._ink_row)
        self._ink_badge.setStyleSheet(
            "QLabel { background: rgba(30, 30, 30, 185); color: #f4f2ef;"
            " border-radius: 4px; padding: 2px 8px; font-size: 11px; }")
        self._ink_badge.setVisible(False)
        _ink_l.addWidget(self._ink_badge)
        self._ink_row.setVisible(False)
        layout.addWidget(self._ink_row)

        # Advisory notice at the BOTTOM of the preview, same look as the
        # "Approximate colours" render badge (#126 autosave note). Hidden by
        # default so it takes no vertical space.
        self._notice_lbl = QLabel("", self)
        self._notice_lbl.setWordWrap(True)
        self._notice_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # No colours of its own. This notice sits BELOW the preview, in the
        # panel — it is not a badge floating over the image — so a fixed dark
        # slab was a little brighter than its surroundings in dark mode and a
        # grey block against a light panel in light mode (Basti, beta.143).
        # Leaving background and text to the palette makes it match whichever
        # theme is on, and keeps matching when the theme is switched at runtime.
        self._notice_lbl.setStyleSheet(
            "QLabel { background: transparent; border-radius: 4px;"
            " padding: 4px 10px; margin: 4px 8px; font-size: 11px; }")
        self._notice_lbl.setVisible(False)
        layout.addWidget(self._notice_lbl)

        # Cursor readout needs move events without a button held.
        self.setMouseTracking(True)
        self._img_label.setMouseTracking(True)

        # Gap between image and nav (replaces the old setSpacing(12))
        self._image_nav_gap = QWidget(self)
        self._image_nav_gap.setFixedHeight(12)
        layout.addWidget(self._image_nav_gap)

        # Navigation bar
        self._nav = QWidget(self)
        nav = self._nav
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(12, 0, 12, 0)

        self._prev_btn = QPushButton(tr("‹ Prev"), nav)
        self._prev_btn.setFixedWidth(84)
        self._prev_btn.clicked.connect(self._go_prev)
        nav_layout.addWidget(self._prev_btn)

        nav_layout.addStretch()
        self._page_label = QLabel("", nav)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet("color: #909090; font-size: 12px;")
        nav_layout.addWidget(self._page_label)
        nav_layout.addStretch()

        self._next_btn = QPushButton(tr("Next ›"), nav)
        self._next_btn.setFixedWidth(84)
        self._next_btn.clicked.connect(self._go_next)
        nav_layout.addWidget(self._next_btn)

        layout.addWidget(nav)

        # Replace the inline dark styles set above with mode-aware versions.
        # No-op for dark (values match); swaps to light palette when active.
        self._apply_mode_styles()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def current_page(self) -> int:
        """0-based index of the page currently shown."""
        return self._current

    def _go_prev(self) -> None:
        if self._current > 0:
            self._current -= 1
            self._active_stripe = -1
            self._update_nav()
            self._schedule_refresh()
            self.page_changed.emit(self._current)

    def _go_next(self) -> None:
        if self._current < len(self._pages) - 1:
            self._current += 1
            self._active_stripe = -1
            self._update_nav()
            self._schedule_refresh()
            self.page_changed.emit(self._current)

    # ---- per-ink inspector (#72 Tier D) ---------------------------------

    def _current_ink_codes(self) -> "list[str] | None":
        """Ink codes when the shown pages are device-native (≥4 channels)."""
        if not self._pages:
            return None
        path = self._pages[0][0]
        codes = self._ink_channels or _find_sidecar_channels(path)
        return codes if codes and len(codes) >= 4 else None

    def _rebuild_ink_row(self) -> None:
        """(Re)build the mute checkboxes for the loaded chart's ink set."""
        from PyQt6.QtWidgets import QCheckBox
        while self._ink_checks_bar.count():
            it = self._ink_checks_bar.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        self._ink_checks = []
        self._muted_inks = set()
        self._ink_page_data = None
        self._ink_page_key = None
        self._ink_readout.setText("")
        codes = self._current_ink_codes()
        if not codes:
            self._ink_row.setVisible(False)
            return
        for i, code in enumerate(codes):
            cb = QCheckBox(code.upper(), self._ink_row)
            cb.setChecked(True)
            cb.setToolTip(tr("Show or hide this ink in the preview — the "
                             "file itself is untouched."))
            cb.toggled.connect(self._on_ink_toggle)
            self._ink_checks_bar.addWidget(cb)
            self._ink_checks.append(cb)
        self._ink_row.setVisible(True)

    def _on_ink_toggle(self, _on: bool) -> None:
        self._muted_inks = {i for i, cb in enumerate(self._ink_checks)
                            if not cb.isChecked()}
        self._update_display()

    def _ensure_ink_page_data(self) -> None:
        """Cache the current page's raw channel data for the cursor readout."""
        if not self._pages or self._current_ink_codes() is None:
            self._ink_page_data = None
            return
        path, frame = self._pages[self._current]
        key = (str(path), frame)
        if self._ink_page_key == key and self._ink_page_data is not None:
            return
        try:
            import tifffile
            with tifffile.TiffFile(str(path)) as tif:
                idx = min(frame, len(tif.pages) - 1)
                data = tif.pages[idx].asarray()
            import numpy as np
            if data.dtype != np.uint8:
                data = (data.astype(np.float32)
                        * (255.0 / np.iinfo(data.dtype).max)).astype(np.uint8)
            self._ink_page_data = data if data.ndim == 3 else None
            self._ink_page_key = key
        except Exception:  # noqa: BLE001 — readout is best-effort
            self._ink_page_data = None

    def _image_px_at(self, label_pos) -> "tuple[int, int] | None":
        """Map a position on the image label to image pixel coords, honouring
        the current fit/zoom/pan (both paint modes store their geometry)."""
        if self._paint_geom is None or self._pixmap is None:
            return None
        scale, ox, oy = self._paint_geom
        if scale <= 0:
            return None
        ix = int((label_pos.x() - ox) / scale)
        iy = int((label_pos.y() - oy) / scale)
        if 0 <= ix < self._pixmap.width() and 0 <= iy < self._pixmap.height():
            return ix, iy
        return None

    def _update_ink_readout(self, event) -> None:
        codes = self._current_ink_codes()
        if not codes or not self._ink_row.isVisible():
            return
        self._ensure_ink_page_data()
        if self._ink_page_data is None:
            return
        pos = self._img_label.mapFrom(self, event.position().toPoint())
        px = self._image_px_at(pos)
        if px is None:
            self._ink_readout.setText("")
            return
        x, y = px
        h, w = self._ink_page_data.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            self._ink_readout.setText("")
            return
        vals = self._ink_page_data[y, x]
        self._ink_readout.setText(" · ".join(
            f"{c.upper()} {round(float(v) / 2.55)}"
            for c, v in zip(codes, vals.tolist())))

    def _update_nav(self) -> None:
        n = len(self._pages)
        visible = n > 1
        self._prev_btn.setVisible(visible)
        self._next_btn.setVisible(visible)
        self._page_label.setVisible(n > 0)
        if n > 0:
            self._page_label.setText(
                tr("Page {page} / {total}").format(page=self._current + 1, total=n))
        else:
            self._page_label.setText("")
        self._prev_btn.setEnabled(self._current > 0)
        self._next_btn.setEnabled(self._current < n - 1)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()

    def _update_display(self) -> None:
        # A deferred repaint (QTimer.singleShot in load_tiff) can fire after the
        # widget was torn down — bail rather than touch a deleted C++ object.
        if self._img_label is None or sip.isdeleted(self._img_label):
            return
        if not self._pages:
            self._img_label.setText(tr("No preview"))
            self._pixmap = None
            return

        path, frame = self._pages[self._current]
        try:
            img = self._load_frame(path, frame, self._ink_channels,
                                   muted=frozenset(self._muted_inks))
            self._pixmap = self._pil_to_pixmap(img)
        except Exception as exc:
            log.warning("Preview render error: %s", exc)
            self._img_label.setText(tr("Preview error:\n{exc}").format(exc=exc))
            return

        # The page is known now, so any strip rects that arrived before it can
        # finally be measured against it.
        self._clamp_stripe_rects_to_page()

        self._update_render_badge()
        self._repaint_label()

    def _update_render_badge(self) -> None:
        """Honesty badge for device-native (multi-ink) pages (#72 Tier D):
        'via profile' when the preview is a true colorimetric render, or a
        clear note that the colours are approximate while the ink values in
        the file are exact. Hidden for ordinary RGB pages.

        Guarded like :meth:`_update_display`, and for the same reason: a
        deferred repaint can arrive after the widgets are gone. The guard there
        checks ``_img_label`` only, and this reaches a different widget — so a
        teardown that had already taken ``_ink_row`` got past it and raised
        *"wrapped C/C++ object of type QWidget has been deleted"* mid-paint.

        Found by running the suite in parallel (2026-08-01), which changes the
        timing enough to expose it; it is not a test artefact, and the same
        race can be lost when a user closes a preview while one is pending.
        """
        for w in (getattr(self, "_ink_row", None),
                  getattr(self, "_ink_badge", None)):
            if w is None or sip.isdeleted(w):
                return
        mode = last_render_mode()
        text = ("" if not mode else
                tr("True colours — via the chart's profile") if mode == "profile"
                else tr("Approximate colours — the ink values in the file are exact"))
        if self._ink_row.isVisible():
            # Share the ink-options line (Basti) — no floating overlay then.
            self._ink_badge.setText(text)
            self._ink_badge.setVisible(bool(text))
            if getattr(self, "_badge_lbl", None) is not None:
                self._badge_lbl.setVisible(False)
            return
        self._ink_badge.setVisible(False)
        if getattr(self, "_badge_lbl", None) is None:
            if not mode:
                return
            self._badge_lbl = QLabel(self)
            self._badge_lbl.setStyleSheet(
                "QLabel { background: rgba(30, 30, 30, 185); color: #f4f2ef;"
                " border-radius: 4px; padding: 2px 8px; font-size: 11px; }")
            self._badge_lbl.raise_()
        if not mode:
            self._badge_lbl.setVisible(False)
            return
        self._badge_lbl.setText(text)
        self._badge_lbl.adjustSize()
        # Anchor to the TOP-right of the image area, not the widget's bottom
        # edge: the bottom is where the surrounding tab places its controls
        # (e.g. the Next button), which the old bottom-anchored badge covered
        # (#125, Knut). mapTo handles the label's nesting inside the header/
        # image layout.
        from PyQt6.QtCore import QPoint
        origin = (self._img_label.mapTo(self, QPoint(0, 0))
                  if self._img_label is not None
                  and not sip.isdeleted(self._img_label) else QPoint(0, 0))
        x = origin.x() + self._img_label.width() - self._badge_lbl.width() - 10
        y = origin.y() + 10
        self._badge_lbl.move(max(0, x), max(0, y))
        self._badge_lbl.raise_()
        self._badge_lbl.setVisible(True)

    def _repaint_label(self) -> None:
        if not self._pixmap:
            return
        if self._img_label is None or sip.isdeleted(self._img_label):
            return                          # torn down before a deferred repaint
        if self._interactive:
            self._repaint_interactive()
            return
        B = _BORDER
        dpr = self._img_label.devicePixelRatioF()
        label_size = self._img_label.size()  # logical pixels

        # Scale to device pixels so the preview is sharp on HiDPI/Retina displays
        avail = QSize(
            max(1, int((label_size.width()  - 2 * B) * dpr)),
            max(1, int((label_size.height() - 2 * B) * dpr)),
        )
        scaled = self._pixmap.scaled(
            avail,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)

        # Canvas at device pixel dimensions; DPR tells Qt the logical display size
        canvas = QPixmap(scaled.width() + int(2 * B * dpr),
                         scaled.height() + int(2 * B * dpr))
        canvas.setDevicePixelRatio(dpr)
        canvas.fill(self._frame_color)

        # Painter coordinates are logical (canvas has DPR set)
        painter = QPainter(canvas)
        painter.drawPixmap(B, B, scaled)
        # Cursor→image mapping (#72): the centred canvas' top-left plus the
        # border offset, at the fitted scale.
        _cw = scaled.width() / dpr + 2 * B
        _ch = scaled.height() / dpr + 2 * B
        _s = (scaled.width() / dpr) / max(1, self._pixmap.width())
        self._paint_geom = (_s,
                            (label_size.width() - _cw) / 2 + B,
                            (label_size.height() - _ch) / 2 + B)

        if self._active_stripe >= 0 and self._stripe_rects and not self._hex_zigzag:
            # sx/sy: device pixels per original image pixel
            sx = scaled.width()  / self._pixmap.width()
            sy = scaled.height() / self._pixmap.height()

            if self._active_stripe < len(self._stripe_rects):
                r   = self._stripe_rects[self._active_stripe]
                # Convert device-pixel coords → logical coords for painter
                x   = r.x()     * sx / dpr + B
                rw  = max(1.0, r.width() * sx / dpr + 2.0 / dpr)
                cx  = x + rw / 2
                arrow_h = 20  # logical pixels — constant visual size on all displays
                path = QPainterPath()
                if self._stripe_arrow_mode == "tip":
                    # No label band to hang from: float the arrow so its tip
                    # ends a tiny gap above the patch area (= the rect top).
                    y = r.y() * sy / dpr + B - 3
                    path.moveTo(cx - rw / 2, y - arrow_h)
                    path.lineTo(cx + rw / 2, y - arrow_h)
                    path.lineTo(cx, y)
                else:
                    y = r.y() * sy / dpr + B + 3
                    path.moveTo(cx - rw / 2, y)
                    path.lineTo(cx + rw / 2, y)
                    path.lineTo(cx, y + arrow_h)
                path.closeSubpath()
                painter.fillPath(path, QColor("#56d6a5"))

                # Bidirectional reading: mirror a second arrow near the
                # chart's bottom edge (not the strip's own bottom — that
                # overlaps patches on multi-strip layouts). Horizontal
                # extent still tracks the active strip so the two arrows
                # stay visually paired.
                if self._bidirectional:
                    chart_bottom = scaled.height() / dpr + B
                    y_bot = chart_bottom - 5
                    bot = QPainterPath()
                    bot.moveTo(cx - rw / 2, y_bot)
                    bot.lineTo(cx + rw / 2, y_bot)
                    bot.lineTo(cx, y_bot - arrow_h)
                    bot.closeSubpath()
                    painter.fillPath(bot, QColor("#56d6a5"))

        if self._margin_guides or self._measured_guides:
            self._draw_margin_guides(
                painter, B, scaled.width() / dpr, scaled.height() / dpr)

        # #126 engine overlays (split patches, hover outline, legend)
        self._draw_cq_overlay(painter,
                              (scaled.width() / dpr) / max(1, self._pixmap.width()),
                              B, B)

        painter.end()
        self._img_label.setPixmap(canvas)
        # The coordinate cross-hair lives in its own overlay (drawn on mouse
        # move, not baked into the canvas) — keep it covering the label (#29).
        if self._cursor_overlay is not None and self._coord_readout:
            self._sync_cursor_overlay_geometry()

    def _draw_cq_overlay(self, painter: QPainter,
                         s: float, ox: float, oy: float) -> None:
        """#126 chart-reading engine overlays, drawn in canvas coordinates
        (image px × `s` + offset). Three layers: the split-patch results for
        the current page, a hover outline for click-to-jump, and a small
        expected/measured legend once any patches are shown."""
        from PyQt6.QtGui import QPen, QPainterPath as _QP

        # Device-pixel snapping: see the split-patch block below. Read once —
        # the ratio cannot change mid-paint, and a widget with no window yet
        # reports 1.0, which is the honest fallback.
        try:
            _dpr = float(self.devicePixelRatioF()) or 1.0
        except Exception:      # noqa: BLE001 — never fail a repaint over this
            _dpr = 1.0

        def _dsnap(v: float) -> float:
            """*v* (logical px) moved to the nearest real device pixel."""
            return round(v * _dpr) / _dpr

        items = self._patch_overlay.get(self._current, [])
        # "Show only measured patches" (Knut): blank every patch on the page to
        # white with a thin outline first, so unread patches read as empty; the
        # measured split-patch items then draw on top, leaving only the read
        # ones coloured — an at-a-glance progress view.
        if self._show_only_measured and self._stripe_rects:
            # Blank the UNREAD strips (whole columns) to paper-white; leave the
            # measured strips exactly as they normally look. We blank per strip
            # (not per patch) and use the paper colour, so there are NO fine
            # gaps and NO contrast edges to alias when the chart is scaled to fit
            # the window — the endless moiré that per-patch outlines/fills kept
            # producing (Sebastian). Reading progress is still obvious: measured
            # columns are coloured, unread ones are blank.
            read_map = self._stripe_read_map or {}
            white = QColor(255, 255, 255)
            rects = self._stripe_rects
            n = len(rects)

            def _bounds(k):
                return self._hover_patch_bounds(rects[k]) or rects[k]

            # A small pad = the inter-row spacer, so the blank also covers the
            # spacer just above the first row and below the last row (otherwise
            # a chart hairline peeks out at the blank's top/bottom edge).
            pad = 2.0
            allb = self._page_patch_boxes.get(self._current) or []
            _cols: dict = {}
            for b in allb:
                _cols.setdefault(b.x(), []).append(b)
            for _bs in _cols.values():
                _bs.sort(key=lambda b: b.y())
                for _k in range(len(_bs) - 1):
                    _g = _bs[_k + 1].y() - (_bs[_k].y() + _bs[_k].height())
                    if _g > 0:
                        pad = float(_g)
                        break
                else:
                    continue
                break

            # Blank each unread strip as its OWN column: tight to that column's
            # own patches vertically (± the row spacer) and reaching the GAP
            # MIDPOINT to each neighbour horizontally, with only a hairline pad
            # at the row's outer edge. Adjacent unread columns abut exactly at
            # the midpoints ⇒ one seamless white area with no internal gaps to
            # alias (Sebastian), while NO single giant rectangle overshoots. The
            # old per-run bounding box reached the tallest column's bottom and
            # padded its outer edge by a whole row-gap, which on a ragged/partial
            # LAST page wiped the right-margin caption sitting just past the short
            # columns (Knut). Per-column bounds never leave the actual patch grid.
            for i in range(n):
                if read_map.get(i, False):
                    continue
                # Use the column's RAW patch boxes, NOT _hover_patch_bounds: that
                # helper grows the box by edge_spacer_px (for the swipe outline,
                # #43), and on a SpectroScan hex chart with a leader spacer that
                # growth reached up into the label band, so the fill wiped the
                # column labels (Knut). Raw boxes keep the fill on the patches.
                cp = [b for b in allb
                      if rects[i].left() <= b.x() + b.width() / 2 <= rects[i].right()]
                if not cp:
                    continue
                # Hexagons overshoot their box by ~h/6 top and bottom — cover that
                # apex so no colour peeks above/below the blank; rectangles just
                # need the small row-spacer pad.
                apex = (cp[0].height() / 6.0 + 2.0) if self._hex_zigzag else 0.0
                vpad = max(pad, apex)
                min_py = min(b.y() for b in cp)
                top = min_py - vpad
                # Never rise into the strip-label band. When this strip's rect
                # extends ABOVE its patches its top sits at the rendered label-band
                # bottom (grown there in engine_strip_rects_from_sidecar), so clamp
                # the fill to it — otherwise the hex apex padding above reached up
                # and wiped the column labels (A, B, C…) on a SpectroScan hex chart
                # (Knut). With labels off the rect top == the patch top, so this is
                # a no-op and the apex stays covered.
                band_top = float(rects[i].top())
                if band_top < min_py:
                    top = max(top, band_top)
                bot = max(b.y() + b.height() for b in cp) + vpad
                # Horizontally cover the column's own patches (min-left / max-right
                # already include the ±¼-patch hex stagger overhang) AND reach the
                # gap midpoint to each neighbour so the inter-column gap is hidden —
                # whichever is further. At the row's OUTER edge there is no
                # neighbour, so we stop a hairline past the last patch: that keeps
                # the fill from bleeding into the right-margin caption on a
                # ragged/partial last page (Knut). Adjacent unread columns overlap
                # in white ⇒ seamless, nothing to alias (Sebastian).
                left = min(b.left() for b in cp) - 2.0
                if i > 0:
                    left = min(left, (rects[i - 1].right() + rects[i].left()) / 2.0)
                right = max(b.right() + 1 for b in cp) + 2.0
                if i < n - 1:
                    right = max(right, (rects[i].right() + rects[i + 1].left()) / 2.0)
                painter.fillRect(
                    QRectF(left * s + ox, top * s + oy,
                           (right - left) * s, (bot - top) * s),
                    white)

            # On the clean white background, draw a thin cell grid so each unread
            # patch reads as its own empty cell (Knut). Each patch gets its
            # left + right + bottom edge, and the TOP edge only on the topmost
            # patch of its strip — so between two stacked patches there is a
            # single line, never two side by side. Read strips are left alone,
            # so their real spacers stay visible (Knut).
            gpen = QPen(QColor(206, 206, 206))
            gpen.setCosmetic(True)
            gpen.setWidthF(1.0)
            painter.setPen(gpen)
            for i, srect in enumerate(self._stripe_rects):
                pats = [b for b in allb
                        if srect.left() <= b.x() + b.width() / 2 <= srect.right()]
                if not pats:
                    continue
                pats.sort(key=lambda b: b.y())
                if read_map.get(i, False):
                    # Read strip: no grid — it keeps its normal split and the
                    # chart's own spacers between patches. Knut confirmed read
                    # patches don't need the unread-cell grid lines.
                    continue
                # True dedup grid (Knut): every patch draws RIGHT + BOTTOM; the
                # TOP edge only on the topmost patch of the strip; the LEFT edge
                # only when the strip to the left is NOT also unread (i.e. this is
                # the left column of an unread run, or the page edge). So the
                # boundary between any two neighbouring unread patches is drawn
                # exactly once — never two lines side by side.
                if self._hex_zigzag:
                    # SpectroScan hexagonal chart: draw each unread patch as its
                    # true hexagon, not a rectangle (Knut). The hexagons tessellate
                    # edge-to-edge so per-patch outlines already read as one clean
                    # honeycomb; no dedup needed the way rectangles need it.
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    for b in pats:
                        painter.drawPath(self._patch_hexagon(b, s, ox, oy))
                    continue
                left_is_border = (i == 0) or read_map.get(i - 1, False)
                # The left edge is normally deduped against the unread column to
                # the left (its right edge already draws that boundary). But that
                # only holds when the neighbour's patches line up row-for-row. On
                # a ColorMunki "offset every second strip" chart the neighbour is
                # shifted half a patch, so it covers only the overlapping middle —
                # the top and bottom patches would lose their left edge (Knut). So
                # we dedup a patch's left edge ONLY when a left-neighbour patch
                # fully spans it vertically; otherwise we draw it.
                left_pats = []
                if not left_is_border:
                    lrect = self._stripe_rects[i - 1]
                    left_pats = [b for b in allb
                                 if lrect.left() <= b.x() + b.width() / 2 <= lrect.right()]
                for idx, b in enumerate(pats):
                    x0 = b.x() * s + ox
                    y0 = b.y() * s + oy
                    x1 = (b.x() + b.width()) * s + ox
                    y1 = (b.y() + b.height()) * s + oy
                    painter.drawLine(QPointF(x1, y0), QPointF(x1, y1))   # right
                    painter.drawLine(QPointF(x0, y1), QPointF(x1, y1))   # bottom
                    if idx == 0:
                        painter.drawLine(QPointF(x0, y0), QPointF(x1, y0))  # top
                    covered = any(lb.y() <= b.y() + 1
                                  and lb.y() + lb.height() >= b.y() + b.height() - 1
                                  for lb in left_pats)
                    if left_is_border or not covered:
                        painter.drawLine(QPointF(x0, y0), QPointF(x0, y1))  # left
        for rect, c_exp, c_meas, warn in items:
            if self._hex_zigzag:
                # SpectroScan hexagonal chart: the measured/expected patch must
                # follow the hexagon and its ±¼-patch zigzag, not a rectangle
                # (Knut). Fill the same hexagon the unread outline uses; the
                # split mode clips the corner-to-corner diagonal to the hexagon.
                b = (rect if isinstance(rect, QRect)
                     else QRect(int(rect.x()), int(rect.y()),
                                int(rect.width()), int(rect.height())))
                hexp = self._patch_hexagon(b, s, ox, oy)
                # Fill by PATH intersection, never a clip: a clip path is hard-
                # edged and left a faint seam around every patch (Knut, zoomed in).
                # A hairline stroke in the fill colour closes the sub-pixel gaps
                # where antialiased neighbours meet, so the honeycomb reads solid.
                if self._overlay_mode == "expected":
                    painter.fillPath(hexp, c_exp)
                    _edge = c_exp
                elif self._overlay_mode == "measured":
                    painter.fillPath(hexp, c_meas)
                    _edge = c_meas
                else:
                    painter.fillPath(hexp, c_meas)        # whole patch = measured ◢
                    br = hexp.boundingRect()
                    tri = _QP()
                    tri.moveTo(br.left(), br.top())
                    tri.lineTo(br.right(), br.top())
                    tri.lineTo(br.left(), br.bottom())
                    tri.closeSubpath()
                    painter.fillPath(hexp.intersected(tri), c_exp)   # expected ◤
                    _edge = c_meas
                _seam = QPen(_edge)
                _seam.setCosmetic(True)
                _seam.setWidthF(1.0)
                painter.setPen(_seam)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(hexp)
                if warn:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    rw = max(1.8, s * 2.2)
                    halo = QPen(QColor(255, 255, 255, 235))
                    halo.setWidthF(rw + 2.6)
                    halo.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(halo)
                    painter.drawPath(hexp)
                    red = QPen(QColor("#ff2b2b"))
                    red.setWidthF(rw)
                    red.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(red)
                    painter.drawPath(hexp)
                continue
            # Round BOTH edges to whole pixels so the split covers exactly the
            # same span as the printed patch — flooring each of x/y/w/h
            # separately (the old int() calls) shifted every patch up-left by
            # up to a pixel and let edges drift (Knut/Basti).
            # …AND SNAP THEM TO THE DEVICE GRID, NOT THE LOGICAL ONE. A Retina
            # screen paints two device pixels per logical pixel, so rounding to
            # whole logical pixels can land half a logical pixel from the
            # image's own edge — one device pixel of the printed patch left
            # showing along an edge, which is the colour fringe Sebastian saw
            # around the split (2026-08-13). Rounding at device resolution puts
            # every edge on a real screen pixel. On a non-Retina display the
            # ratio is 1 and this is exactly the old behaviour.
            x0 = _dsnap(rect.x() * s + ox)
            y0 = _dsnap(rect.y() * s + oy)
            x1 = _dsnap((rect.x() + rect.width()) * s + ox)
            y1 = _dsnap((rect.y() + rect.height()) * s + oy)
            w = max(2.0 / _dpr, x1 - x0)
            h = max(2.0 / _dpr, y1 - y0)
            if self._overlay_mode == "expected":
                painter.fillRect(QRectF(x0, y0, w, h), c_exp)
            elif self._overlay_mode == "measured":
                painter.fillRect(QRectF(x0, y0, w, h), c_meas)
            else:
                # Expected: upper-left triangle; measured: lower-right — the
                # i1Profiler split, corner to corner, hard edge, no gap.
                tri = _QP()
                tri.moveTo(x0, y0)
                tri.lineTo(x0 + w, y0)
                tri.lineTo(x0, y0 + h)
                tri.closeSubpath()
                painter.fillRect(QRectF(x0, y0, w, h), c_meas)
                painter.fillPath(tri, c_exp)
            if warn:
                # A bright red outline over a white halo (the same trick the
                # margin guides use) so a likely misread is unmistakable on ANY
                # patch colour — a muted red-on-red border was easy to miss
                # (Sebastian). The stroke widths are constant across the page
                # (from the zoom `s`, NOT the per-patch size) and the frame is a
                # float QRectF inset by exactly half the halo width, so its outer
                # edge lands precisely on the fill box (x0..x1, y0..y1) on every
                # patch — no per-patch rounding drift (Sebastian: "off by a
                # little" on some patches).
                rw = max(1.8, s * 2.2)
                hw = rw + 2.6
                inset = hw / 2.0
                if w - 2 * inset >= 1 and h - 2 * inset >= 1:
                    wr = QRectF(x0 + inset, y0 + inset,
                                w - 2 * inset, h - 2 * inset)
                else:                       # tiny patch: hug the box itself
                    wr = QRectF(x0 + 0.5, y0 + 0.5, w - 1, h - 1)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                halo = QPen(QColor(255, 255, 255, 235))
                halo.setWidthF(hw)
                halo.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
                painter.setPen(halo)
                painter.drawRect(wr)
                red = QPen(QColor("#ff2b2b"))
                red.setWidthF(rw)
                red.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
                painter.setPen(red)
                painter.drawRect(wr)

        # #126 spot mode: highlight the patch to read next with a bright
        # haloed accent ring so the user knows where to place the instrument.
        if self._active_patch_box is not None and self._active_patch_page == self._current:
            r = self._active_patch_box
            x0 = round(r.x() * s + ox)
            y0 = round(r.y() * s + oy)
            x1 = round((r.x() + r.width()) * s + ox)
            y1 = round((r.y() + r.height()) * s + oy)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            halo = QPen(QColor(255, 255, 255, 235))
            halo.setWidthF(5.0)
            halo.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(halo)
            painter.drawRect(x0, y0, x1 - x0, y1 - y0)
            ring = QPen(QColor("#1f8f6b"))
            ring.setWidthF(2.5)
            ring.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(ring)
            painter.drawRect(x0, y0, x1 - x0, y1 - y0)

        # #126 spot mode: click-to-jump hover outline around the patch under
        # the pointer (mirrors the strip hover outline below).
        if self._patch_click_enabled and self._hover_patch_loc:
            _boxes = (self._patch_click_pages[self._current]
                      if 0 <= self._current < len(self._patch_click_pages) else {})
            hr = _boxes.get(self._hover_patch_loc)
            if hr is not None:
                x0 = round(hr.x() * s + ox)
                y0 = round(hr.y() * s + oy)
                x1 = round((hr.x() + hr.width()) * s + ox)
                y1 = round((hr.y() + hr.height()) * s + oy)
                pen = QPen(QColor("#56d6a5"))
                pen.setWidthF(2.5)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(x0, y0, x1 - x0, y1 - y0)

        if self._stripe_click_enabled and self._hover_stripe >= 0 \
                and self._hover_stripe < len(self._stripe_rects):
            # Hug only the patches of the hovered strip (never the label band or
            # the white paper around them). Fall back to the full strip rect
            # when the chart exposes no per-patch geometry (Basti, #126).
            strip_rect = self._stripe_rects[self._hover_stripe]
            pen = QPen(QColor("#56d6a5"))
            pen.setWidthF(2.5)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            zig = (self._strip_zigzag_path(strip_rect, s, ox, oy)
                   if self._hex_zigzag else None)
            if zig is not None:
                painter.drawPath(zig)             # follow the hex column's zigzag
            else:
                r = self._hover_patch_bounds(strip_rect) or strip_rect
                x0 = round(r.x() * s + ox)
                y0 = round(r.y() * s + oy)
                x1 = round((r.x() + r.width()) * s + ox)
                y1 = round((r.y() + r.height()) * s + oy)
                painter.drawRect(x0, y0, x1 - x0, y1 - y0)

        if items and self._pixmap is not None:
            # Legend chip — text reflects the current view (Knut). No split
            # wording unless the split is actually shown; in Measured view the
            # not-yet-read patches still show their expected colour, so say so.
            if self._overlay_mode == "expected":
                txt = tr("Showing expected colours (screen colours approximate)")
            elif self._overlay_mode == "measured":
                txt = tr("Showing measured colours, unread patches show expected "
                         "colours (screen colours approximate)")
            else:
                txt = tr("expected ◤ · measured ◢ (screen colours approximate)")
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(txt) + 16
            th = fm.height() + 8
            img_l = ox
            img_r = ox + self._pixmap.width() * s
            img_b = oy + self._pixmap.height() * s
            # Sit in the bottom paper margin, below the lowest patch, so it
            # never covers patches even on charts that reach near the edge
            # (Knut). Fall back to just above the paper edge if the margin is
            # tight.
            patch_bottom = oy
            for r in self._stripe_rects:
                patch_bottom = max(patch_bottom, oy + (r.y() + r.height()) * s)
            # THE STRIP DOES NOT END AT ITS LAST PATCH. A chart with edge
            # spacers draws one more band below it — the recorded geometry
            # stops at the patch (see edge_spacer_px_from_sidecar: they
            # "aren't in the recorded patch geometry"), so a chip placed 6 px
            # under the patches lands ON the trailing spacer. Sebastian's
            # ColorMunki verification chart has 12 px of it, which is why the
            # legend looked as if it were touching (2026-08-13). The strip
            # HOVER frame already grows over these; this makes the legend
            # agree with it instead of holding a second opinion.
            patch_bottom += self._edge_spacer_px * s
            cx = int((img_l + img_r) / 2 - tw / 2)
            # Keep the whole chip within the paper width so it never clips.
            cx = max(int(img_l), min(cx, int(img_r - tw)))
            # …AND OUT OF THE SCAN ARROW'S BAND. Reading both ways mirrors an
            # arrow at the very bottom of the sheet (`chart_bottom - 5`, 20 px
            # tall), which is exactly where the fall-back position below puts
            # the chip on a densely filled chart — the two would sit on top of
            # each other (Sebastian). Reserve that band while it is in use.
            floor = img_b - th - 4 - (25 if self._bidirectional else 0)
            cy = int(min(floor, patch_bottom + 6))
            cy = max(cy, int(patch_bottom + 2))
            # …AND KEEP THE WHOLE CHIP ON THE PAPER, like the width above.
            # The line before prefers "below the last patch", which on a chart
            # whose patches run close to the bottom edge pushes the chip past
            # the paper and the pane, so it is drawn half cut off (Sebastian
            # spotted it in the overlay screenshot, 2026-08-13). When the
            # bottom margin cannot hold it, resting on the last row is the
            # lesser evil: the chip is semi-transparent and readable, whereas
            # a clipped one says nothing at all.
            cy = max(int(oy), min(cy, int(floor)))
            painter.fillRect(cx, cy, tw, th, QColor(20, 20, 20, 190))
            painter.setPen(QColor("#f4f2ef"))
            painter.drawText(cx + 8, cy + th - 6, txt)

    def _draw_margin_guides(
        self, painter: QPainter, border: float, disp_w: float, disp_h: float
    ) -> None:
        """Paint the margin-threshold guide lines over the displayed image.

        Each non-violated line is a black dash over a white halo so it stays
        visible on any patch colour in either theme; a violated line is red over
        the same halo so the eye goes straight to the offending edge.

        A solid page-edge rectangle is drawn at the image boundary first, so the
        white display border around the page can't be mistaken for page margin —
        a 0 mm threshold guide then visibly sits on the paper edge (#83).
        """
        from PyQt6.QtGui import QPen

        edge = QPen(QColor(120, 120, 120))
        edge.setWidthF(1.0)
        painter.setPen(edge)
        painter.drawRect(int(border), int(border), int(disp_w), int(disp_h))

        for axis, frac, violated in self._margin_guides:
            frac = max(0.0, min(1.0, frac))
            if axis == "v":
                x = border + frac * disp_w
                p1 = (x, border); p2 = (x, border + disp_h)
            else:
                y = border + frac * disp_h
                p1 = (border, y); p2 = (border + disp_w, y)
            # White halo underlay (solid, slightly wider) for contrast.
            halo = QPen(QColor(255, 255, 255, 200))
            halo.setWidthF(2.6)
            painter.setPen(halo)
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
            # Dashed top line: red when violated, else near-black.
            top = QPen(QColor("#e0564b") if violated else QColor(20, 20, 20))
            top.setWidthF(1.2)
            top.setStyle(Qt.PenStyle.CustomDashLine)
            top.setDashPattern([4, 4])
            painter.setPen(top)
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

        # Measured-margin lines: long purple/blue dots at the patch-area edges,
        # over a white halo, distinct from the (shorter) threshold dashes.
        for axis, frac in self._measured_guides:
            frac = max(0.0, min(1.0, frac))
            if axis == "v":
                x = border + frac * disp_w
                p1 = (x, border); p2 = (x, border + disp_h)
            else:
                y = border + frac * disp_h
                p1 = (border, y); p2 = (border + disp_w, y)
            halo = QPen(QColor(255, 255, 255, 200))
            halo.setWidthF(2.6)
            painter.setPen(halo)
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
            line = QPen(QColor("#7b3ff2"))   # blue-violet
            line.setWidthF(1.3)
            line.setStyle(Qt.PenStyle.CustomDashLine)
            line.setDashPattern([10, 5])      # long dots
            painter.setPen(line)
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

        painter.setPen(Qt.PenStyle.SolidLine)

    def _repaint_interactive(self) -> None:
        """Fit-to-window at zoom 1, then scale + pan within the viewport. The
        canvas fills the whole viewport (so the margin shows around a zoomed
        image), painting the image scaled and offset, clamped so it can't be
        dragged fully out of view."""
        B = _BORDER
        dpr = self._img_label.devicePixelRatioF()
        ls = self._img_label.size()
        W, H = max(1, ls.width()), max(1, ls.height())
        pw, ph = self._pixmap.width(), self._pixmap.height()
        # Fit inside a B-wide inset at zoom 1 so the tinted frame + a dark
        # surround show on all sides (the canvas is the whole viewport so the
        # image can pan).
        fit = min(max(1, W - 2 * B) / pw, max(1, H - 2 * B) / ph)
        scale = fit * self._zoom
        disp_w, disp_h = pw * scale, ph * scale

        # Clamp pan so the image can't be dragged fully out of view.
        max_x = max(0.0, (disp_w - W) / 2)
        max_y = max(0.0, (disp_h - H) / 2)
        self._pan = QPointF(max(-max_x, min(max_x, self._pan.x())),
                            max(-max_y, min(max_y, self._pan.y())))

        canvas = QPixmap(int(W * dpr), int(H * dpr))
        canvas.setDevicePixelRatio(dpr)
        # Dark/light viewer background fills the surround; only a thin frame
        # hugging the image is tinted (e.g. simulated paper white).
        bg = QColor("#efebe6") if self._mode == "light" else QColor("#111111")
        canvas.fill(bg)
        painter = QPainter(canvas)
        scaled = self._pixmap.scaled(
            max(1, int(disp_w * dpr)), max(1, int(disp_h * dpr)),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        x = (W - disp_w) / 2 + self._pan.x()
        y = (H - disp_h) / 2 + self._pan.y()
        painter.fillRect(int(x - B), int(y - B), int(disp_w + 2 * B),
                         int(disp_h + 2 * B), self._frame_color)   # thin tinted frame
        painter.drawPixmap(int(x), int(y), scaled)
        # #126 engine overlays (split patches, hover outline, legend)
        self._draw_cq_overlay(painter, scale, x, y)
        self._paint_geom = (scale, x, y)   # for the cursor→image mapping (#72)
        painter.end()
        self._img_label.setPixmap(canvas)
        if self._cursor_overlay is not None and self._coord_readout:
            self._sync_cursor_overlay_geometry()

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if not (self._interactive and self._pixmap):
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()  # trackpad too
        if delta == 0:
            return
        focus = self._img_label.mapFrom(self, event.position().toPoint())
        self._apply_zoom(1.0015 ** delta, focus)
        event.accept()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._interactive and self._pixmap and event.button() in (
                Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._panning = True
            self._pan_dist = 0
            self._pan_anchor = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._panning:
            now = event.position().toPoint()
            d = now - self._pan_anchor
            self._pan_dist += abs(d.x()) + abs(d.y())
            self._pan_anchor = now
            self._pan = QPointF(self._pan.x() + d.x(), self._pan.y() + d.y())
            self._repaint_label()
            event.accept()
            return
        # #126: hovering a clickable strip
        if self._stripe_click_enabled:
            idx = self._stripe_at(event.position().toPoint())
            if idx != self._hover_stripe:
                self._hover_stripe = idx
                if idx >= 0:
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                    if self._stripe_read_map.get(idx):
                        self.setToolTip(tr("Click to jump to this strip. It "
                                           "has already been read — clicking "
                                           "lets you measure it again."))
                    else:
                        self.setToolTip(tr("Click to jump to this strip and "
                                           "measure it next."))
                else:
                    self.unsetCursor()
                    self.setToolTip("")
                # Repaint the hover highlight NOW, not via the 80 ms debounce:
                # the highlight changes only when the pointer crosses into a new
                # strip (not every pixel), and a full repaint is ~3 ms, so the
                # jump-target highlight should track the pointer without lag
                # (Basti). The debounce is kept for bulk changes elsewhere.
                self._repaint_label()
        # #126 spot mode: hovering a clickable patch
        if self._patch_click_enabled:
            hit = self._patch_at(event.position().toPoint())
            loc = hit[0] if hit else ""
            if loc != self._hover_patch_loc:
                self._hover_patch_loc = loc
                if loc:
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                    self.setToolTip(tr("Click to jump to this patch and "
                                       "measure it next."))
                else:
                    self.unsetCursor()
                    self.setToolTip("")
                self._repaint_label()
        self._update_ink_readout(event)   # per-ink cursor readout (#72)
        self._update_patch_tile(event.position().toPoint())  # hover value tile
        if self._coord_readout and self._pixmap is not None:
            self._coord_pos = self._img_label.mapFrom(
                self, event.position().toPoint())
            # Draw straight into the lightweight overlay — no chart re-render —
            # so the cross-hair tracks the pointer instantly (#29).
            if self._cursor_overlay is not None:
                self._sync_cursor_overlay_geometry()
                self._cursor_overlay.show_cursor(
                    self._coord_pos, self._coord_mm_at(self._coord_pos))
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        if self._coord_readout and self._coord_pos is not None:
            self._coord_pos = None
            if self._cursor_overlay is not None:
                self._cursor_overlay.show_cursor(None, None)
        self._hide_patch_tile()
        if self._hover_patch_loc:
            self._hover_patch_loc = ""
            self._repaint_label()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._panning:
            self._panning = False
            self.unsetCursor()
            # #126: a press-release without meaningful movement on a strip
            # is a click, not a pan.
            if (self._stripe_click_enabled and self._pan_dist < 4
                    and event.button() == Qt.MouseButton.LeftButton):
                idx = self._stripe_at(event.position().toPoint())
                if idx >= 0:
                    self.stripe_clicked_page = self._current
                    self.stripe_clicked.emit(self._current, idx)
            elif (self._patch_click_enabled and self._pan_dist < 4
                    and event.button() == Qt.MouseButton.LeftButton):
                hit = self._patch_at(event.position().toPoint())
                if hit is not None:
                    self.patch_clicked.emit(self._current, hit[0])
            self._pan_dist = 0
            event.accept()
            return
        if (self._stripe_click_enabled
                and event.button() == Qt.MouseButton.LeftButton):
            idx = self._stripe_at(event.position().toPoint())
            if idx >= 0:
                self.stripe_clicked_page = self._current
                self.stripe_clicked.emit(self._current, idx)
                event.accept()
                return
        if (self._patch_click_enabled
                and event.button() == Qt.MouseButton.LeftButton):
            hit = self._patch_at(event.position().toPoint())
            if hit is not None:
                self.patch_clicked.emit(self._current, hit[0])
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if self._interactive and self._pixmap:
            self.reset_view()       # double-click → back to fit
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if self._interactive and self._pixmap:
            k = event.key()
            if k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._apply_zoom(1.25); event.accept(); return
            if k in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
                self._apply_zoom(1 / 1.25); event.accept(); return
            if k in (Qt.Key.Key_0, Qt.Key.Key_F):
                self.reset_view(); event.accept(); return
            step = 40
            pans = {Qt.Key.Key_Left: (step, 0), Qt.Key.Key_Right: (-step, 0),
                    Qt.Key.Key_Up: (0, step), Qt.Key.Key_Down: (0, -step)}
            if k in pans:
                dx, dy = pans[k]
                self._pan = QPointF(self._pan.x() + dx, self._pan.y() + dy)
                self._repaint_label(); event.accept(); return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._repaint_label()
        if getattr(self, "_badge_lbl", None) is not None \
                and self._badge_lbl.isVisible():
            self._badge_lbl.move(
                self.width() - self._badge_lbl.width() - 12,
                self.height() - self._badge_lbl.height() - 12)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._pixmap:
            # Defer until Qt has activated the now-visible tab's layout —
            # otherwise _img_label.size() is still the hidden minimum and the
            # pixmap gets scaled too small, leaving a "border" around it.
            QTimer.singleShot(0, self._repaint_label)

    # ------------------------------------------------------------------
    # Image loading helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count_frames(path: Path) -> int:
        """Return number of frames in a TIFF, trying PIL then tifffile."""
        try:
            return getattr(Image.open(path), "n_frames", 1)
        except Exception:
            pass
        try:
            import tifffile
            with tifffile.TiffFile(str(path)) as tif:
                return len(tif.pages)
        except Exception:
            return 0

    @staticmethod
    def _load_frame(path: Path, frame: int, ink_channels: list[str] | None,
                    muted: frozenset = frozenset()) -> Image.Image:
        """Load one TIFF frame as RGB, handling CMYK and multi-channel Separated.

        ``muted`` (channel indices) recomposites the page without those inks —
        the per-ink inspector (#72); it forces the channel-composite path,
        since cctiff can only render the complete ink set.
        """
        _set_render_mode("")   # plain RGB pages carry no badge
        # Bypass PIL for known multi-channel files: PIL may silently return only 4 channels
        # from a Separated TIFF, dropping any extra ink channels without raising an exception.
        known_codes = ink_channels or _find_sidecar_channels(path)
        if known_codes and (len(known_codes) > 4 or muted):
            return TiffPreview._tifffile_load_frame(path, frame, ink_channels,
                                                    muted=muted)

        try:
            img = Image.open(path)
            if hasattr(img, "seek"):
                try:
                    img.seek(frame)
                except EOFError:
                    pass
            if img.mode in ("RGB", "RGBA"):
                return img.convert("RGB")
            if img.mode == "CMYK":
                # Device-native CMYK chart: true colours via the chart's own
                # profile when known (#72 Tier D), else the ICC approximation.
                cimg = TiffPreview._colorimetric_frame(path, frame)
                if cimg is not None:
                    _set_render_mode("profile")
                    return cimg
                _set_render_mode("approx")
                return TiffPreview._cmyk_pil_to_rgb(img)
            return img.convert("RGB")
        except Exception:
            return TiffPreview._tifffile_load_frame(path, frame, ink_channels,
                                                    muted=muted)

    @staticmethod
    def _cmyk_pil_to_rgb(img: Image.Image) -> Image.Image:
        """Convert CMYK PIL image to RGB using ICC profile (embedded or system SWOP)."""
        from PIL import ImageCms
        icc_data = img.info.get("icc_profile")
        if icc_data:
            try:
                import io
                src = ImageCms.ImageCmsProfile(io.BytesIO(icc_data))
                dst = ImageCms.createProfile("sRGB")
                t = ImageCms.buildTransformFromOpenProfiles(
                    src, dst, "CMYK", "RGB",
                    renderingIntent=ImageCms.Intent.PERCEPTUAL,
                )
                return ImageCms.applyTransform(img, t)
            except Exception:
                pass
        t = _get_cmyk_transform()
        if t:
            try:
                return ImageCms.applyTransform(img, t)
            except Exception:
                pass
        from PIL import ImageChops, ImageOps
        c, m, y, k = img.split()
        k_inv = ImageOps.invert(k)
        r = ImageChops.multiply(ImageOps.invert(c), k_inv)
        g = ImageChops.multiply(ImageOps.invert(m), k_inv)
        b = ImageChops.multiply(ImageOps.invert(y), k_inv)
        return Image.merge("RGB", (r, g, b))

    @staticmethod
    def _colorimetric_frame(path: Path, frame: int) -> "Image.Image | None":
        """True-colour render of a separated chart page via cctiff (#72 Tier D).

        Only possible when the chart's device profile is discoverable next to
        the TIFF (run's preconditioning.icc / meta.json recipe) and Argyll is
        installed; returns None otherwise — callers fall back to the
        approximate composite. Conversion results are cached by mtime.
        """
        try:
            from workflow.colorimetric_preview import (
                colorimetric_rgb_tiff, find_device_profile,
            )
            profile = find_device_profile(path)
            if profile is None:
                return None
            from core.platform_paths import argyll_candidate_dirs
            from core.resource_path import argyll_binary
            bin_dir = next((d for d in argyll_candidate_dirs()
                            if (d / argyll_binary("cctiff")).exists()), None)
            if bin_dir is None:
                return None
            conv = colorimetric_rgb_tiff(path, profile, bin_dir)
            if conv is None:
                return None
            img = Image.open(conv)
            if hasattr(img, "seek"):
                try:
                    img.seek(frame)
                except EOFError:
                    pass
            return img.convert("RGB")
        except Exception:  # noqa: BLE001 — preview upgrade is best-effort
            return None

    @staticmethod
    def _tifffile_load_frame(
        path: Path, frame: int, ink_channels: list[str] | None,
        muted: frozenset = frozenset()
    ) -> Image.Image:
        """Load multi-channel/malformed TIFF via tifffile and composite to RGB.

        ``muted`` channel indices are zeroed before compositing (the per-ink
        inspector, #72) — the picture shows what the remaining inks lay down.
        """
        import tifffile
        import numpy as np

        with tifffile.TiffFile(str(path)) as tif:
            idx = min(frame, len(tif.pages) - 1)
            data = tif.pages[idx].asarray()
        if muted and data.ndim == 3:
            data = data.copy()
            for i in muted:
                if 0 <= i < data.shape[2]:
                    data[:, :, i] = 0

        if data.dtype != np.uint8:
            data = (data.astype(np.float32) * (255.0 / np.iinfo(data.dtype).max)).astype(np.uint8)

        if data.ndim == 2:
            return Image.fromarray(data.astype(np.uint8), "L").convert("RGB")

        n_ch = data.shape[2] if data.ndim == 3 else 1
        if n_ch == 3:
            return Image.fromarray(data.astype(np.uint8), "RGB")
        if n_ch < 2:
            return Image.fromarray(data[:, :, 0].astype(np.uint8), "L").convert("RGB")

        # Resolve ink codes: caller-supplied → sidecar → count heuristic → generic
        codes = (
            ink_channels
            or _find_sidecar_channels(path)
            or _N_CHANNELS_FALLBACK.get(n_ch)
            or (["c", "m", "y", "k"] + ["k"] * max(0, n_ch - 4))
        )

        # n_ch >= 4: a device-native chart. When the chart's own profile is
        # known, render the TRUE colours through cctiff (#72 Tier D) — the
        # honest picture; otherwise composite an approximation and say so.
        if n_ch >= 4:
            img = None if muted else TiffPreview._colorimetric_frame(path, frame)
            if img is not None:
                _set_render_mode("profile")
                return img
            _set_render_mode("approx")
            cmyk_img = Image.fromarray(data[:, :, :4], "CMYK")
            base = TiffPreview._cmyk_pil_to_rgb(cmyk_img)
            if n_ch == 4:
                return base
            # Extra inks multiply the base's REFLECTANCE — physical light is
            # linear, so decode the sRGB gamma first and re-encode after
            # (#72 Tier D item 2: overprints get visibly more believable).
            ref = _srgb_to_linear(np.array(base, dtype=np.float32) / 255.0)
            for i, code in enumerate(codes[4:n_ch], start=4):
                ink_val = data[:, :, i].astype(np.float32) / 255.0
                ar, ag, ab = _ink_absorption_linear(code)
                ref[:, :, 0] *= 1.0 - ink_val * ar
                ref[:, :, 1] *= 1.0 - ink_val * ag
                ref[:, :, 2] *= 1.0 - ink_val * ab
            out = _linear_to_srgb(ref.clip(0.0, 1.0))
            return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGB")

        # n_ch < 4 but > 1: pure absorption compositing (RGB/CMY devices)
        h, w = data.shape[:2]
        ref = np.ones((h, w, 3), dtype=np.float32)
        for ch_idx, code in enumerate(codes[:n_ch]):
            ink_val = data[:, :, ch_idx].astype(np.float32) / 255.0
            ar, ag, ab = _INK_ABSORPTION.get(code, (1.0, 1.0, 1.0))
            ref[:, :, 0] *= 1.0 - ink_val * ar
            ref[:, :, 1] *= 1.0 - ink_val * ag
            ref[:, :, 2] *= 1.0 - ink_val * ab
        return Image.fromarray((ref.clip(0, 1) * 255).astype(np.uint8), "RGB")

    @staticmethod
    def _pil_to_pixmap(img: Image.Image) -> QPixmap:
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        px = QPixmap()
        if not px.loadFromData(buf.read()):
            raise RuntimeError(
                f"QPixmap.loadFromData failed for {img.size} {img.mode} image"
            )
        return px
