"""Tab 3: Measure Chart."""
from __future__ import annotations

import html
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.file_manager import FileManager, Run
from core.logger import get_logger
from core.preset_store import (
    load_presets as _load_tab_presets,
    reveal_in_file_manager,
    save_presets as _save_tab_presets,
    tab_dir,
)
from core.resource_path import resource_path
from core.strip_utils import letter_to_idx, parse_passes_per_page
from ui.fade_scroll import FadeScrollArea
from ui.tab_header import TabHeader
from ui.tooltip_button import TooltipButton
from ui.widgets import ElidingLabel, NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox, make_browse_button, open_file_dialog, set_folder_icon, set_preset_icon, tint_dialog_primary

_TAB_COLOR = "#56d6a5"  # Measure tab accent
from ui.styles import SPEC_GREEN, TAB_COLORS


def make_scanner_target_row(parent, checked: bool, *, accent: str = "#56d6a5",
                            hint_light: str = "#2f6b52",
                            hint_dark: str = "#a6e3ca"):
    """The opt-in "save scanner-profiling files" checkbox for the 'All Stripes
    Read' dialog, as a bordered row (checkbox + ⓘ + one-line helper).

    Shared by the real dialog and the render harness so they can't drift. Ticking
    it flags the chart so ChromIQ (re)builds its ``.cht`` + ``.cie`` from the
    measurement whenever it's finalised — letting you profile a **scanner** from
    the same chart later, with no reprint (#97). Returns ``(row_widget,
    checkbox)``; only shown for engine charts.

    ``accent`` tints the card border/fill and the ⓘ; ``hint_light``/``hint_dark``
    are the readable helper-text colours per theme (see
    [[feedback_readability_light_dark]]). Defaults are the scanner-family green —
    the Check & Refine assessment dialog overrides them with its violet accent so
    the card matches the dialog it lives in."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPalette
    from PyQt6.QtWidgets import (
        QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout)

    app = QApplication.instance()
    dark = (app is not None
            and app.palette().color(QPalette.ColorRole.Window).lightness() < 128)
    # Readable secondary text on the tinted card — a muted accent that keeps
    # clear contrast in both themes (palette(mid) washed out on the tint).
    hint_color = hint_dark if dark else hint_light
    r, g, b    = (int(accent[i:i + 2], 16) for i in (1, 3, 5))
    tint_a     = "0.13" if dark else "0.10"
    tint_bg    = f"rgba({r},{g},{b},{tint_a})"

    row = QFrame(parent)
    row.setObjectName("scannerTargetRow")
    # The checkbox/label must be transparent so the card tint shows through —
    # without this the QCheckBox paints its own opaque base colour (a black box
    # behind the label in dark mode).
    row.setStyleSheet(
        f"#scannerTargetRow {{ border: 1px solid rgba({r},{g},{b},0.55);"
        f" border-radius: 6px; background: {tint_bg}; }}"
        " #scannerTargetRow QCheckBox, #scannerTargetRow QLabel"
        " { background: transparent; }"
        # Without this the checked indicator falls back to the system accent
        # (blue); tint it with this card's accent (green here, violet in Check
        # & Refine) so it matches the rest of the card.
        f" #scannerTargetRow QCheckBox::indicator:checked {{ background: {accent};"
        f" border-color: {accent}; }}"
        # Same for the hover border, which otherwise shows the system blue.
        f" #scannerTargetRow QCheckBox::indicator:hover {{ border-color: {accent}; }}")
    outer = QVBoxLayout(row)
    outer.setContentsMargins(12, 8, 12, 10)
    outer.setSpacing(2)

    top = QHBoxLayout()
    top.setSpacing(8)
    cb = QCheckBox(tr("Also save scanner-profiling files for this chart"), row)
    cb.setChecked(checked)
    top.addWidget(cb)
    top.addStretch(1)
    top.addWidget(TooltipButton(
        tr("Reuse this chart to profile a scanner or camera"),
        tr("Saves two small extra files (.cht + .cie) alongside your chart. "
        "Later, you can build a colour profile for your scanner — or your "
        "camera — from this exact chart, with no need to print or measure "
        "anything again. You just scan the printed chart (or photograph it with "
        "a camera), and ChromIQ compares how your device saw each patch against "
        "the real colours the spectrophotometer measured here.\n\n"
        "So the same two files work for both: scan the chart to profile a "
        "scanner, or photograph it to profile a camera.\n\n"
        "Leave this off if you're only profiling your printer. You can always "
        "turn it on later from Tools ▸ Create scanner or camera target."),
        row, min_width=460, color=accent),
        0, Qt.AlignmentFlag.AlignVCenter)
    outer.addLayout(top)

    hint = QLabel(tr("For scanning — or photographing — the printed chart to "
                     "profile your scanner or camera; not needed for printer "
                     "profiling."), row)
    hint.setWordWrap(True)
    hint.setStyleSheet(f"color: {hint_color}; font-size: 12px;")
    outer.addWidget(hint)
    return row, cb
from workflow.average_runner import AverageParams, AverageRunner
from workflow.measure_manager import MeasureManager, MeasureParams
from workflow.ti3_analysis import mark_verification_ti3
from workflow.scanin_target import has_scanner_geometry
from ui.tiff_preview import TiffPreview
from core.i18n import tr

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

log = get_logger(__name__)



# Absolute FLOOR ΔE for the split-patch warning outline: a patch is never
# flagged below this, whatever its strip looks like. It is only half the test —
# see _strip_outlier_fence(). The design "expected" is the chart's sRGB values,
# and a printer does NOT reproduce sRGB, so vivid patches legitimately sit at
# 30-40+ ΔE with a perfect print (verified on a real i1Pro read). An absolute
# threshold alone therefore flags most saturated patches on a good chart, which
# is just noise — so we ALSO require the patch to be an outlier within its own
# strip (a real misread stands out from its neighbours; uniform sRGB deviation
# does not).
_PATCH_WARN_DE = 50.0


def _strip_outlier_fence(des: "list[float]") -> float:
    """Tukey upper fence (Q3 + 1.5·IQR) of a strip's per-patch ΔEs — the level
    above which a patch is an outlier *for this strip*, adapting to how vivid the
    strip is. Returns 0.0 for strips too short to judge a spread (then only the
    absolute floor applies)."""
    if len(des) < 4:
        return 0.0
    s = sorted(des)

    def pct(p: float) -> float:
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    q1, q3 = pct(0.25), pct(0.75)
    return q3 + 1.5 * (q3 - q1)


def _xyz_d50_to_srgb8(xyz: "list[float]") -> tuple[int, int, int]:
    """D50 XYZ (0..100) → display sRGB 0..255 (Bradford to D65). Preview
    colouring only — never feeds back into measurement data (#126)."""
    x, y, z = (float(v) / 100.0 for v in xyz[:3])
    # Bradford D50→D65
    xd = 0.9555766 * x + -0.0230393 * y + 0.0631636 * z
    yd = -0.0282895 * x + 1.0099416 * y + 0.0210077 * z
    zd = 0.0122982 * x + -0.0204830 * y + 1.3299098 * z
    r = 3.2404542 * xd + -1.5371385 * yd + -0.4985314 * zd
    g = -0.9692660 * xd + 1.8760108 * yd + 0.0415560 * zd
    b = 0.0556434 * xd + -0.2040259 * yd + 1.0572252 * zd

    def enc(c: float) -> int:
        c = max(0.0, min(1.0, c))
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        return max(0, min(255, round(c * 255.0)))

    return enc(r), enc(g), enc(b)


def _detect_stripe_rects(tiff_path: Path) -> list[QRect]:
    """Locate vertical strip columns in a printtarg TIFF.

    Strategy
    --------
    1. Find the label zone: the first contiguous block of rows that have a
       "moderate" number of dark pixels (printed label characters — neither
       blank white rows nor full-width separator lines).
    2. Build a per-column dark-pixel count from those rows; merge adjacent
       non-zero runs to get one cluster per strip label.
    3. Convert label-cluster centres → strip x-boundaries (midpoints between
       centres, extrapolated at the edges).
    4. Derive the vertical extent from the full content bounding box.
    """
    from PIL import Image
    try:
        try:
            img = Image.open(tiff_path).convert("L")
        except Exception:
            from ui.tiff_preview import load_tiff_as_rgb, _find_sidecar_channels
            img = load_tiff_as_rgb(
                tiff_path, ink_channels=_find_sidecar_channels(tiff_path)
            ).convert("L")
        orig_w, orig_h = img.size

        ANALYSIS_W = 1000
        scale  = ANALYSIS_W / orig_w if orig_w > ANALYSIS_W else 1.0
        aw     = max(1, int(orig_w * scale))
        ah     = max(1, int(orig_h * scale))
        small  = img.resize((aw, ah), Image.BOX)
        pix    = small.load()

        DARK            = 80
        WHITE           = 240
        MIN_LABEL_DARK  = max(5, aw // 200)   # at least this many dark px/row
        MAX_LABEL_FRAC  = 0.30                 # exclude separator lines (>30% dark)
        EMPTY_STOP      = 8                    # white rows before stopping label scan
        # Merge within-label character gaps. Must be large enough to bridge the
        # faint crossbar gap in letters like "H" (~5 px at aw=1000) but well
        # below the inter-letter gap (~22+ px on standard printtarg charts).
        MERGE_GAP       = max(8, aw // 100)

        # ── 1. Locate the label zone ─────────────────────────────────────────
        max_label_dark = int(aw * MAX_LABEL_FRAC)
        y_lab_start: int | None = None
        y_lab_end:   int | None = None
        empty_streak = 0
        for y in range(ah * 30 // 100):
            count = sum(1 for x in range(aw) if pix[x, y] < DARK)
            if MIN_LABEL_DARK <= count <= max_label_dark:
                if y_lab_start is None:
                    y_lab_start = y
                y_lab_end = y
                empty_streak = 0
            else:
                empty_streak += 1
                if y_lab_start is not None and empty_streak >= EMPTY_STOP:
                    break

        if y_lab_start is None or y_lab_end is None:
            log.debug("Strip detection: no label zone found")
            return []

        # ── 2. Column dark-pixel profile → merge into per-strip clusters ─────
        col_dark = [0] * aw
        for y in range(y_lab_start, y_lab_end + 1):
            for x in range(aw):
                if pix[x, y] < DARK:
                    col_dark[x] += 1

        runs: list[tuple[int, int]] = []
        in_run = False
        r_start = 0
        for x in range(aw):
            if col_dark[x] > 0 and not in_run:
                in_run, r_start = True, x
            elif col_dark[x] == 0 and in_run:
                in_run = False
                runs.append((r_start, x - 1))
        if in_run:
            runs.append((r_start, aw - 1))

        merged: list[list[int]] = []
        for s, e in runs:
            if merged and s - merged[-1][1] <= MERGE_GAP:
                merged[-1][1] = e
            else:
                merged.append([s, e])

        if not merged:
            log.debug("Strip detection: no label clusters found")
            return []

        raw_centers = [(s + e) / 2 for s, e in merged]

        # Robustify against split letters ("H" crossbar, narrow "I" cluttering
        # the neighbour) and merged adjacent two-character labels (page 3 has
        # "AW AX AY …"): derive the true column pitch from the MEDIAN gap
        # between adjacent cluster centres — both kinds of artefact only
        # distort a minority of gaps, so the median stays correct.  Then
        # generate a uniform grid between the leftmost and rightmost real
        # cluster (trimming clusters whose nearest neighbour is implausibly
        # close, since those are likely spurious edge clusters).
        if len(raw_centers) >= 3:
            gaps_sorted = sorted(raw_centers[i + 1] - raw_centers[i]
                                 for i in range(len(raw_centers) - 1))
            median_pitch = gaps_sorted[len(gaps_sorted) // 2]
            # Drop a leading cluster whose gap to neighbour is < 60% of median
            # (almost certainly a spurious mark, not a strip label).
            left_centers = list(raw_centers)
            while len(left_centers) >= 2 and \
                    (left_centers[1] - left_centers[0]) < 0.6 * median_pitch:
                left_centers.pop(0)
            while len(left_centers) >= 2 and \
                    (left_centers[-1] - left_centers[-2]) < 0.6 * median_pitch:
                left_centers.pop()
            if len(left_centers) >= 2 and median_pitch > 0:
                left, right = left_centers[0], left_centers[-1]
                n_strips = round((right - left) / median_pitch) + 1
                # Hard sanity bound — never invent or drop more than 25% of
                # what was raw-detected.
                n_strips = max(int(len(raw_centers) * 0.75),
                               min(int(len(raw_centers) * 1.25) + 2, n_strips))
                centers = [left + i * (right - left) / max(1, n_strips - 1)
                           for i in range(n_strips)]
            else:
                centers = raw_centers
        else:
            centers = raw_centers
        n_strips = len(centers)

        # ── 3. Vertical extent ───────────────────────────────────────────────
        y_top_a    = next((y for y in range(ah)
                           if any(pix[x, y] < WHITE for x in range(0, aw, 4))), 0)
        y_bottom_a = next((y for y in range(ah - 1, -1, -1)
                           if any(pix[x, y] < WHITE for x in range(0, aw, 4))), ah - 1)

        inv           = 1.0 / scale
        y_top         = max(0,      int(y_top_a    * inv))
        y_bottom      = min(orig_h, int((y_bottom_a + 1) * inv))
        strip_h       = max(1, y_bottom - y_top)
        y_label_bot   = min(orig_h, int((y_lab_end + 1) * inv))

        # ── 4. Build vertical column rects ───────────────────────────────────
        rects: list[QRect] = []
        for i, cx in enumerate(centers):
            half_l = (cx - centers[i - 1]) / 2 if i > 0         else (centers[1] - centers[0]) / 2
            half_r = (centers[i + 1] - cx) / 2 if i < n_strips-1 else (centers[-1] - centers[-2]) / 2
            x0 = max(0,      int((cx - half_l) * inv))
            x1 = min(orig_w, int((cx + half_r) * inv))
            rects.append(QRect(x0, y_label_bot, max(1, x1 - x0), strip_h))

        log.info("Strip detection: %d strips, label y=%d–%d (scaled), content y=%d–%d (orig)",
                 n_strips, y_lab_start, y_lab_end, y_top, y_bottom)
        return rects

    except Exception as exc:
        log.warning("Strip detection failed: %s", exc)
        return []


def patch_boxes_from_sidecar(ti2_path: Path, n_pages: int
                             ) -> "list[dict[str, QRect]]":
    """Exact per-patch pixel boxes for the split-patch overlay (#126).

    Returns a per-page list of ``{loc: QRect}`` in TIFF-pixel space (the same
    space the strip rects use), or a list of empty dicts when the chart
    exposes no per-patch geometry. The overlay is drawn only where a real box
    exists — so a split can never land anywhere but on its own patch, whatever
    the layout (spacers, ColorMunki double density, multi-page). Sources, in
    order: the layout engine's ``<stem>.strips.json``, then a
    ``channels.json`` ``layout.patches`` block.
    """
    import json
    out: list[dict[str, QRect]] = [dict() for _ in range(max(0, n_pages))]
    if n_pages < 1 or ti2_path is None:
        return out

    def _ingest(patches) -> bool:
        got = False
        for p in patches:
            try:
                pg = int(p["page"])
                if 0 <= pg < n_pages:
                    out[pg][str(p["loc"])] = QRect(
                        int(p["x"]), int(p["y"]), int(p["w"]), int(p["h"]))
                    got = True
            except (KeyError, TypeError, ValueError):
                continue
        return got

    got = False
    strips_json = ti2_path.with_suffix(".strips.json")
    if strips_json.is_file():
        try:
            data = json.loads(strips_json.read_text())
            got = _ingest(data.get("patches") or [])
        except Exception:
            pass

    if not got:
        channels = ti2_path.with_suffix(".channels.json")
        if channels.is_file():
            try:
                layout = json.loads(channels.read_text()).get("layout") or {}
                if isinstance(layout, dict):
                    _ingest(layout.get("patches") or [])
            except Exception:
                pass
    _apply_hex_stagger(ti2_path, out)
    return out


def edge_spacer_px_from_sidecar(ti2_path: "Path | None") -> int:
    """Height (image px) of a leader/trailer edge spacer for this chart, or 0
    when the chart has none (#43, Basti). Edge spacers bracket each strip (one
    spacer-width above the first patch, one below the last) but aren't in the
    recorded patch geometry, so the strip-hover frame must add them back.

    Read straight from the chart's own geometry so it is always accurate: the
    channels.json recipe's ``edge_spacers`` flag says whether they exist, and
    the engine geometry gives their height (the patch spacing ``pspa``, the same
    value the margin inspector uses for edge spacers, #18)."""
    if ti2_path is None:
        return 0
    import json
    channels = Path(ti2_path).with_suffix(".channels.json")
    if not channels.is_file():
        return 0
    try:
        layout = json.loads(channels.read_text()).get("layout") or {}
        recipe = layout.get("recipe") or {}
        if not recipe.get("edge_spacers"):
            return 0
        from dataclasses import fields as _fields
        from workflow.layout_engine import instruments
        from workflow.layout_engine.presets import LayoutRecipe
        valid = {f.name for f in _fields(LayoutRecipe)}
        rc = LayoutRecipe(**{k: v for k, v in recipe.items() if k in valid})
        geom = instruments.geom_from_build_kwargs(rc.build_kwargs())
        dpi = float(layout.get("dpi") or 300) or 300.0
        return max(0, round(geom.pspa * dpi / 25.4))
    except Exception:  # noqa: BLE001 — a hover nicety must never break loading
        return 0


def _apply_hex_stagger(ti2_path: Path, pages: "list[dict[str, QRect]]") -> None:
    """SpectroScan hexagons are DRAWN with a ±¼-width horizontal zigzag by row
    (raster._hexagon_points), but the recorded boxes hold only the slot x. So the
    split overlay would sit a quarter-patch off the real hexagons on every row
    (Knut #32). Shift each box to match the drawn hexagon: odd patch numbers
    (1,3,5…) shift left, even ones right — exactly the renderer's step parity."""
    import re
    from workflow.hex_support import chart_is_hexagonal
    if not chart_is_hexagonal(ti2_path):
        return
    for page in pages:
        for loc, r in list(page.items()):
            m = re.search(r"(\d+)\s*$", loc)
            if not m:
                continue
            j = int(m.group(1)) - 1                    # 0-based row in the strip
            dx = round(-r.width() / 4) if (j % 2 == 0) else round(r.width() / 4)
            page[loc] = QRect(r.x() + dx, r.y(), r.width(), r.height())


def engine_strip_rects_from_sidecar(sidecar: Path, n_pages: int):
    """Per-page strip rects from a ChromIQ-engine chart's ``channels.json``.

    Returns ``(per_page_rects, counts, arrow_mode)`` (rects in TIFF-pixel
    space, the same space the image detectors use), or ``None`` when there's
    no usable engine ``layout`` block or it doesn't cover every loaded page
    (issue #93).

    The rect top doubles as the scan-arrow anchor. Charts WITH strip labels
    store the rendered label-band bottom (``label_band_bottom_px``); the rect
    is grown up to that line so the arrow hangs directly under the labels,
    printtarg-style, with ``arrow_mode`` "base" (arrow points down from the
    anchor). Charts WITHOUT labels have no band to hang from, so the rect
    keeps the patch-area top and ``arrow_mode`` "tip" makes the preview float
    the arrow with its tip a tiny gap above the patches. Older sidecars
    (no band key) keep the legacy patch-top/"base" behaviour, except when
    their stored recipe says indicators were off — then "tip" is safe too.
    """
    import json
    if n_pages < 1 or not sidecar.is_file():
        return None
    try:
        layout = json.loads(sidecar.read_text()).get("layout")
    except Exception:
        return None
    if not isinstance(layout, dict):
        return None
    strips = layout.get("strips") or []
    if not strips:
        return None
    band_bot = layout.get("label_band_bottom_px")
    if isinstance(band_bot, (int, float)) and not isinstance(band_bot, bool):
        band_bot = int(band_bot)
        arrow_mode = "base"
    else:
        band_bot = None
        recipe = layout.get("recipe") or {}
        labels_off = ("label_band_bottom_px" in layout
                      or recipe.get("draw_indicators") is False)
        arrow_mode = "tip" if labels_off else "base"
    per_page: list[list[QRect]] = [[] for _ in range(n_pages)]
    try:
        for s in strips:
            pg = int(s["page"])
            if 0 <= pg < n_pages:
                x, y, w, h = int(s["x"]), int(s["y"]), int(s["w"]), int(s["h"])
                if band_bot is not None and band_bot < y:
                    h += y - band_bot
                    y = band_bot
                per_page[pg].append(QRect(x, y, w, h))
    except (KeyError, TypeError, ValueError):
        return None
    if any(not p for p in per_page):
        return None
    return per_page, [len(p) for p in per_page], arrow_mode


def _detect_uniform_stripe_rects(tiff_path: Path, n_strips: int) -> list[QRect]:
    """Locate strip columns when the page's strip count is already known.

    Used when the chart's .ti2 tells us exactly how many strips a page holds
    (see ``parse_passes_per_page``). Counting strip *labels* from the image is
    fragile — two-character labels (AA, AB, …) cluster unpredictably and the
    rotated title string printtarg prints down the right margin looks like an
    extra strip. Here we sidestep all of that:

    1. Find the label band at the top (vertical anchor for the arrow).
    2. Isolate the patch block as the *widest contiguous run* of "has content"
       columns below the labels — one solid, edge-to-edge run of equal-width
       strips. The white margin before the right-edge title text splits that
       text into its own narrow run, so it is excluded.
    3. Divide the block into exactly ``n_strips`` equal columns.

    Returns [] if the page can't be analysed, so the caller can fall back to
    the label-based detector.
    """
    from PIL import Image
    if n_strips < 1:
        return []
    try:
        try:
            img = Image.open(tiff_path).convert("L")
        except Exception:
            from ui.tiff_preview import load_tiff_as_rgb, _find_sidecar_channels
            img = load_tiff_as_rgb(
                tiff_path, ink_channels=_find_sidecar_channels(tiff_path)
            ).convert("L")
        orig_w, orig_h = img.size

        ANALYSIS_W = 1000
        scale = ANALYSIS_W / orig_w if orig_w > ANALYSIS_W else 1.0
        aw    = max(1, int(orig_w * scale))
        ah    = max(1, int(orig_h * scale))
        small = img.resize((aw, ah), Image.BOX)
        pix   = small.load()

        DARK            = 80
        WHITE           = 240
        MIN_LABEL_DARK  = max(5, aw // 200)
        MAX_LABEL_FRAC  = 0.30
        EMPTY_STOP      = 8

        # ── 1. Label band → vertical anchor (same as the legacy detector) ────
        max_label_dark = int(aw * MAX_LABEL_FRAC)
        y_lab_start: int | None = None
        y_lab_end:   int | None = None
        empty_streak = 0
        for y in range(ah * 30 // 100):
            count = sum(1 for x in range(aw) if pix[x, y] < DARK)
            if MIN_LABEL_DARK <= count <= max_label_dark:
                if y_lab_start is None:
                    y_lab_start = y
                y_lab_end = y
                empty_streak = 0
            else:
                empty_streak += 1
                if y_lab_start is not None and empty_streak >= EMPTY_STOP:
                    break
        if y_lab_end is None:
            return []

        # ── 2. Patch block = widest contiguous run of content columns ────────
        y0 = y_lab_end + 1
        y1 = int(ah * 0.97)
        if y1 <= y0:
            return []
        col_content = [
            sum(1 for y in range(y0, y1) if pix[x, y] < WHITE) for x in range(aw)
        ]
        thr = (y1 - y0) * 0.10
        gap = max(2, aw // 250)   # bridge anti-alias dropouts between strips
        best: tuple[int, int] | None = None
        run_start: int | None = None
        last = 0
        for x in range(aw):
            if col_content[x] > thr:
                if run_start is None:
                    run_start = x
                last = x
            elif run_start is not None and x - last > gap:
                if best is None or (last - run_start) > (best[1] - best[0]):
                    best = (run_start, last)
                run_start = None
        if run_start is not None and (
            best is None or (last - run_start) > (best[1] - best[0])
        ):
            best = (run_start, last)
        if best is None:
            return []
        block_l, block_r = best
        block_w = block_r - block_l + 1

        # ── 2b. Re-derive the label-band bottom inside the patch block ───────
        # The full-width band scan in step 1 also counts the rotated descriptive
        # caption printtarg stamps down the page margin. When that caption
        # reaches up to the A,B,C label row with no gap (e.g. a long target
        # description), those margin rows get folded into the band and push the
        # strip arrow — anchored to ``y_label_bot`` — downward. Re-running the
        # band scan counting only dark pixels INSIDE [block_l, block_r] (the
        # patch grid, which holds the real labels) drops the margin caption.
        # Clamping can only shorten the band, never lengthen it, so the arrow
        # moves up to just under the real label row or stays put — strip
        # division below is left byte-identical. Skipped when the block is
        # implausibly narrow (a 1–2 strip chart, where margin text could rival
        # the block width) so we never trade a cosmetic offset for a misdetect.
        # See memory project_measure_arrow_position.
        if block_w >= aw * 0.30:
            blk_max_dark = int(block_w * MAX_LABEL_FRAC)
            blk_min_dark = max(5, block_w // 200)
            ys_blk: int | None = None
            ye_blk: int | None = None
            empty_blk = 0
            for y in range(ah * 30 // 100):
                count = sum(1 for x in range(block_l, block_r + 1)
                            if pix[x, y] < DARK)
                if blk_min_dark <= count <= blk_max_dark:
                    if ys_blk is None:
                        ys_blk = y
                    ye_blk = y
                    empty_blk = 0
                else:
                    empty_blk += 1
                    if ys_blk is not None and empty_blk >= EMPTY_STOP:
                        break
            if ye_blk is not None:
                y_lab_end = ye_blk

        # ── 3. Vertical extent for the rect height ───────────────────────────
        y_top_a    = next((y for y in range(ah)
                           if any(pix[x, y] < WHITE for x in range(0, aw, 4))), 0)
        y_bottom_a = next((y for y in range(ah - 1, -1, -1)
                           if any(pix[x, y] < WHITE for x in range(0, aw, 4))), ah - 1)
        inv         = 1.0 / scale
        y_top       = max(0,      int(y_top_a * inv))
        y_bottom    = min(orig_h, int((y_bottom_a + 1) * inv))
        y_label_bot = min(orig_h, int((y_lab_end + 1) * inv))
        strip_h     = max(1, y_bottom - y_top)

        # ── 4. Divide the block into n_strips equal columns ──────────────────
        col_w = block_w / n_strips
        rects: list[QRect] = []
        for i in range(n_strips):
            x0 = int((block_l + i * col_w) * inv)
            x1 = int((block_l + (i + 1) * col_w) * inv)
            rects.append(QRect(x0, y_label_bot, max(1, x1 - x0), strip_h))

        log.info("Uniform strip detection: %d strips, block x=%d–%d (scaled)",
                 n_strips, block_l, block_r)
        return rects

    except Exception as exc:
        log.warning("Uniform strip detection failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Per-option chartread row helper
# ---------------------------------------------------------------------------

# Tooltip for the optional "also use pre-conditioning data" checkbox (shown only
# when ChromIQ-style refinement is on and this run carries a preconditioning.ti3).
_PRECOND_TIP_TITLE = "Also Use Pre-conditioning Measurement Data"
_PRECOND_TIP_BODY = (
    "ChromIQ found saved measurement data from the pre-conditioning profile you\n"
    "selected when creating this chart (the run's preconditioning.ti3).\n\n"
    "Tick this to fold those earlier measurements into your profile. When you\n"
    "build the profile, ChromIQ combines the patches you just measured with the\n"
    "saved earlier ones and builds from the larger set — generally a more\n"
    "accurate profile.\n\n"
    "Your freshly measured file is not changed: the combining happens on a\n"
    "separate copy only at build time. You can still re-measure individual\n"
    "strips in Check && Refine exactly as usual.\n\n"
    "This option only appears when ChromIQ-style refinement is enabled in\n"
    "Settings and saved pre-conditioning data is present."
)

# #134: tooltip for the "Show overlay from existing measurement" toggle.
_OVERLAY_TIP_BODY = (
    "Paints the colours from a measurement you already made onto the chart in "
    "the preview — each patch split between the colour the chart EXPECTED and "
    "what your instrument actually MEASURED, with the far-off ones outlined. It "
    "reads the .ti3 measurement file sitting next to this chart, so you can look "
    "back at how a print turned out without measuring it again.\n\n"
    "This option appears only when a measurement (.ti3) is found for the loaded "
    "chart. If the measurement came from a different chart (no matching patch "
    "layout), open it in Tools ▸ Inspect a measurement to see the numbers "
    "instead.")

_VERIFY_TIP_TITLE = "Verification measurement (colour-managed print)"
_VERIFY_TIP_BODY = (
    "Tick this ONLY when you are measuring a chart you printed *through* a "
    "profile (with colour management ON) to check how good that profile is — "
    "NOT the normal profiling chart.\n\n"
    "Normally you print the chart with colour management OFF so ChromIQ can "
    "learn your printer's raw behaviour and build a profile from it. A chart "
    "printed THROUGH a profile is the opposite: it shows the corrected result, "
    "so a profile built from it would be wrong.\n\n"
    "When this is ticked, ChromIQ:\n"
    "  • saves the reading as a separate '…-verify.ti3' file (your real "
    "measurement is never overwritten),\n"
    "  • marks it so it can't be turned into a profile by accident, and\n"
    "  • afterwards reminds you to open it in Tools ▸ Inspect a measurement, "
    "where it checks the colours against the profile.\n\n"
    "Leave it OFF for normal profiling. To verify, reprint your chart through "
    "the finished profile, then measure it with this ticked."
)


@dataclass
class _ChartreadOption:
    """One chartread option row with enable-checkbox and optional value widget."""
    key: str           # settings key suffix
    flag: str          # CLI flag
    label: str
    tooltip_title: str
    tooltip_body: str
    widget: QWidget | None = None   # value widget (spinbox, combo…)
    checkbox: QCheckBox | None = None
    row_widget: QWidget | None = None
    tooltip_width: int = 420        # min width of this option's info dialog

    def build_args(self) -> list[str]:
        """Return CLI tokens for this option if enabled."""
        if self.checkbox is None or not self.checkbox.isChecked():
            return []
        if self.widget is None:
            return [self.flag]
        val = self._read_widget()
        if val is None:
            return [self.flag]
        return [self.flag, str(val)]

    def _read_widget(self):
        if isinstance(self.widget, (QSpinBox, QDoubleSpinBox)):
            return self.widget.value()
        if isinstance(self.widget, QComboBox):
            return self.widget.currentData()
        return None


class TabMeasure(QWidget):
    """Step 3: interactive chart measurement with chartread."""

    measure_finished   = pyqtSignal(Path)  # emits the .ti3 path on success
    proceed_to_profile = pyqtSignal()      # emitted when user chooses to go straight to tab 4
    measurement_active = pyqtSignal(bool)  # True when chartread is running, False when done
    ti2_replaced       = pyqtSignal()      # emitted when the user manually loads a different .ti2 file
    ti2_loaded         = pyqtSignal(Path)  # emitted when the user loads a .ti2 file (for cross-tab sync)
    chart_load_requested = pyqtSignal(Path, list)  # user loaded a .ti2 here → reflect it in Create Chart

    def __init__(
        self,
        runner: "ArgyllRunner",
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner   = runner
        self._settings = settings
        self._manager  = MeasureManager(runner, self)
        self._avg_runner = AverageRunner(runner)
        self._ti1_path: Path | None = None
        self._tiff_pages: list[Path] = []
        # Per-page strip highlight rects and the authoritative per-page strip
        # counts (from the .ti2 PASSES_IN_STRIPS2). Together these let the
        # highlighter map an absolute strip letter to the right page + column,
        # even on multi-page charts whose last page is partly empty.
        self._page_stripe_rects: list[list[QRect]] = []
        self._strips_per_page: list[int] = []
        self._stripe_arrow_mode = "base"
        self._chartread_opts: list[_ChartreadOption] = []
        # ChromIQ-style refinement: this run's preconditioning.ti3, if any
        # (the pre-conditioning profile's measurement data, seeded by
        # Project.new_run when the user refined a prior run).
        self._precond_ti3: Path | None = None
        # Auto bidir-detection: resolved -B value for the loaded .ti2 (False =
        # bidirectional allowed; the no-file / unknown-instrument fallback).
        self._detected_disable_bidir: bool = False
        # Auto force-bidir (-b): resolved for the loaded .ti2 — True for the
        # i1 Pro family, which reads strips either way (mutually exclusive with
        # _detected_disable_bidir).
        self._detected_force_bidir: bool = False
        self._detected_instrument: str | None = None
        # Whether the loaded chart was laid out in randomised patch order.
        # Forcing bidirectional reading (-b) on a non-randomised chart can make
        # chartread misrecognise strips, so _on_start warns when both are true.
        # Default True so we never warn until a real (non-random) chart is seen.
        self._detected_randomized: bool = True
        # Text of the last "Chart instrument:" line logged, so a new chart can
        # replace it instead of letting the messages accumulate.
        self._instr_log_text: str | None = None
        self._measure_failed: bool = False
        self._strip_list: list[str] = []
        self._refine_strips_path: Path | None = None
        self._guided_refinement_active: bool = False
        self._resume_active: bool = False
        self._auto_proceed: bool = False
        self._all_done_shown: bool = False
        # True for the current read when the "Verification measurement" box was
        # ticked at start — the result is saved as a verify-only file, never a profile.
        self._verify_run: bool = False
        # "Read again & average": True once the user opts to re-read the chart,
        # so each subsequent successful read is moved into reads/readN.ti3.
        self._averaging_active: bool = False
        # When averaging is enabled, the "All Stripes Read" dialog records the
        # user's choice here so _on_measure_done can act on it once chartread has
        # finished writing the .ti3 (the file isn't final while chartread runs).
        # None → no decision pending (fall back to the post-process dialog).
        self._pending_avg_action: str | None = None
        self._pending_avg_method: str = "mean"
        self._instrument_disconnected: bool = False
        # #126 chart-reading engine session state
        self._engine_strips: list[dict] = []      # session_start strip map
        self._engine_read: dict[str, bool] = {}   # letter → measured?
        # Per-page {loc: QRect} for the split-patch overlay; empty when the
        # chart exposes no per-patch geometry (then the overlay is suppressed).
        self._patch_boxes: list[dict[str, QRect]] = []
        self._patch_geom_warned = False
        # Engine spot (patch-by-patch) mode: the patch currently awaiting a
        # read, and whether click-to-jump has been armed for this session.
        self._spot_current_loc: str = ""
        self._spot_click_on: bool = False
        self._spot_session: bool = False
        self._device_busy: bool = False
        self._no_instrument: bool = False
        self._usb_claimed_by_vm: bool = False
        # Pending terminal dialogs for group-B startup failures (shown by _on_measure_done).
        self._coms_init_failed_msg: str | None = None
        self._inst_init_failed_msg: str | None = None
        self._instrument_wrong_type: str | None = None
        self._ccmx_load_failed_msg: str | None = None
        self._mode_set_failed_msg: str | None = None
        self._ti3_mtime_before: float | None = None
        self._mode: str = "dark"

        self._manager.stripe_changed.connect(self._on_stripe_changed)
        self._manager.all_stripes_done.connect(self._on_all_stripes_done)
        # Opt-in scanner target: (re)build .cht + .cie from every finalised
        # measurement when the chart is flagged for it (#97). measure_finished
        # carries the final .ti3 in every proceed-to-build case (normal, cal/
        # guided, and both averaging exits), so one connection covers them all.
        self.measure_finished.connect(self._maybe_build_scanner_target)
        self.measure_finished.connect(self._maybe_save_measurement_report)
        self._manager.calibration_prompt.connect(self._on_calibration_prompt)
        self._manager.calibration_done.connect(self._on_calibration_done)
        self._manager.strip_error.connect(self._on_strip_error)
        self._manager.strip_error.connect(self._report_failed_strip_pace)
        # #126 chart-reading engine
        self._manager.session_map.connect(self._on_session_map)
        self._manager.strip_measured.connect(self._on_strip_measured)
        # #131 Phase 2: reading pace is judged per STRIP, not per patch. Knut
        # (2026-07-26): timing single patches in patch-by-patch mode has no
        # value — pace only means something while swiping a whole strip — so
        # nothing subscribes to patch events for pace any more.
        if hasattr(self._manager, "instrument_detected"):
            self._manager.instrument_detected.connect(self._on_instrument_detected)
        self._manager.strip_measured.connect(self._report_strip_pace)
        self._manager.scan_started.connect(self._on_scan_started)
        self._manager.patch_ready.connect(self._on_patch_ready)
        self._manager.patch_measured.connect(self._on_patch_measured)
        self._manager.chart_measured.connect(self._on_chart_measured)
        self._manager.chart_reading.connect(self._on_chart_reading)
        self._manager.readings_saved.connect(self._on_readings_saved)
        self._manager.instrument_disconnected.connect(self._on_instrument_disconnected)
        self._manager.device_busy.connect(self._on_device_busy)
        self._manager.no_instrument.connect(self._on_no_instrument)
        self._manager.wrong_strip.connect(self._on_wrong_strip)
        self._manager.unexpected_response.connect(self._on_unexpected_response)
        self._manager.strip_misaligned.connect(self._on_strip_misaligned)
        self._manager.sensor_wrong_position.connect(self._on_sensor_wrong_position)
        self._manager.usb_claimed_by_vm.connect(self._on_usb_claimed_by_vm)
        # A. Mid-measurement recovery dialogs
        self._manager.strip_interrupted.connect(self._on_strip_interrupted)
        self._manager.unread_confirm.connect(self._on_unread_confirm)
        self._manager.generic_instrument_error.connect(self._on_generic_instrument_error)
        # B. Startup / config error capture (dialogs shown in _on_measure_done)
        self._manager.coms_init_failed.connect(self._on_coms_init_failed)
        self._manager.inst_init_failed.connect(self._on_inst_init_failed)
        self._manager.instrument_wrong_type.connect(self._on_instrument_wrong_type)
        self._manager.ccmx_load_failed.connect(self._on_ccmx_load_failed)
        self._manager.mode_set_failed.connect(self._on_mode_set_failed)
        # B-status. Non-blocking informational messages
        self._manager.info_message.connect(self._on_info_message)
        self._manager.engine_fell_back.connect(self._on_engine_fell_back)
        self._manager.engine_fell_back_resumed.connect(
            self._on_engine_fell_back_resumed)
        self._manager.calibration_retrying.connect(self._on_calibration_retrying)
        # D. Spot / XY mode defensive handlers
        self._manager.xy_place_sheet.connect(self._on_xy_place_sheet)
        self._manager.spot_ready.connect(self._on_spot_ready)
        self._manager.abort_confirm.connect(self._on_abort_confirm)
        self._runner.keypress_failed.connect(self._on_keypress_failed)

        # #131 sound feedback: play a sound at each measurement event, connected
        # alongside the existing handlers so the sound layer stays decoupled. The
        # SoundManager itself no-ops when sounds are off or the event is OFF.
        import core.sound as _snd
        self._sound = _snd.SoundManager(self._settings)
        _m = self._manager
        _m.patch_measured.connect(self._on_patch_sound)
        # (the strip cue is played by _on_strip_measured itself — see there)
        # (strip_error's sound is played by _on_strip_error itself — see there)
        for _sig in (_m.instrument_disconnected, _m.no_instrument,
                     _m.device_busy, _m.sensor_wrong_position,
                     _m.usb_claimed_by_vm):
            _sig.connect(lambda *_: self._sound.play(_snd.INSTRUMENT_ERROR))
        for _sig in (_m.generic_instrument_error, _m.coms_init_failed,
                     _m.inst_init_failed, _m.instrument_wrong_type,
                     _m.ccmx_load_failed, _m.mode_set_failed):
            _sig.connect(lambda *_: self._sound.play(_snd.INSTRUMENT_ERROR))
        self.measure_finished.connect(
            lambda _p: self._play_measurement_finished_once())

        # Watchdog: if a dialog sends a key but chartread emits no new output
        # within KEY_WATCHDOG_MS, surface a recoverable warning so the user is
        # not left staring at a frozen dialog when a keystroke vanishes
        # (e.g. Windows AttachConsole failure — issue #20).
        self._last_chartread_output_ts: float = 0.0
        self._key_watchdog = QTimer(self)
        self._key_watchdog.setSingleShot(True)
        self._key_watchdog.setInterval(12000)
        self._key_watchdog.timeout.connect(self._on_key_watchdog_timeout)
        self._build_ui()
        self._restore_defaults()
        self._start_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _switch_mode(self, mode: str) -> None:
        if mode == "guided":
            self._stack.setCurrentIndex(0)
            self._guided_btn.setChecked(True)
            self._manual_btn.setChecked(False)
        else:
            self._stack.setCurrentIndex(1)
            self._guided_btn.setChecked(False)
            self._manual_btn.setChecked(True)
        self._calm_outer.setVisible(mode == "guided")
        # The two modules keep INDEPENDENT "Live preview" settings; apply the
        # now-active module's view state to the shared preview so switching
        # module shows that module's chosen view (Basti). Guarded for build time.
        self._apply_active_view_settings()
        # The two modes have separate resume checkboxes; reflect the active
        # one's state on the shared Start button. Guarded because _switch_mode
        # is also reachable during UI build before _start_btn exists.
        if hasattr(self, "_start_btn"):
            self._refresh_start_button_label()

    def _apply_active_view_settings(self) -> None:
        """Push the active module's independent Live-preview controls to the
        shared preview (called on module switch and after restore) (#44)."""
        if getattr(self, "_preview", None) is None:
            return                       # called during UI build — nothing yet
        prefix = "g" if self._current_mode() == "guided" else "m"
        combo = getattr(self, f"_{prefix}_overlay_mode", None)
        only = getattr(self, f"_{prefix}_only_measured", None)
        tile = getattr(self, f"_{prefix}_patch_tile", None)
        if combo is not None:
            self._preview.set_overlay_mode(combo.currentData())
        if only is not None:
            self._preview.set_show_only_measured(only.isChecked())
        if tile is not None:
            self._preview.set_show_patch_tile(tile.isChecked())

    def _on_view_control_changed(self, prefix: str) -> None:
        """A Live-preview control changed. Only the ACTIVE module's controls
        drive the shared preview, so the two modules stay independent (#44) —
        e.g. restoring the manual defaults while Guided is showing must not
        change the guided view."""
        active = "g" if self._current_mode() == "guided" else "m"
        if prefix == active:
            self._apply_active_view_settings()

    def _current_mode(self) -> str:
        return "guided" if self._stack.currentIndex() == 0 else "manual"

    def set_target_controller(self, controller) -> None:
        """Receive the shared Profile-run / Run-type controller (#130) so the
        'Verification' run type drives the verification flow and its dated
        destination."""
        self._target_ctl = controller

    def _is_verify_checked(self) -> bool:
        """True when this is a verification read — either the active module's
        'Verification measurement' box is ticked, or the shared Run type is set
        to Verification (#130)."""
        cb = self._verify_cb if self._current_mode() == "guided" else self._m_verify_cb
        if cb.isChecked():
            return True
        ctl = getattr(self, "_target_ctl", None)
        return ctl is not None and ctl.target.is_verification()

    def _is_pbp_checked(self) -> bool:
        """True if the active module's 'Patch-by-patch mode' box is ticked."""
        cb = self._pbp_cb if self._current_mode() == "guided" else self._m_pbp_cb
        return cb.isChecked()

    def _guard_run(self) -> "Run | None":
        """The run the verification guard checks (#130). Prefers the Profile-run
        bar — reliable even before a chart is loaded, and correct when the loaded
        chart is a verify chart living under verifications/ — then falls back to
        the loaded chart's own run (walking up to runs/runN)."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is not None:
            try:
                proj = ctl.project_or_none()
                rid = ctl.target.profile_run
                if proj is not None and rid and proj.has_run(rid):
                    return proj.run(rid)
            except Exception:      # noqa: BLE001
                pass
        if self._ti1_path is not None:
            p = self._ti1_path.parent
            for anc in (p, *p.parents):
                if anc.parent.name == "runs":
                    try:
                        return Run.for_dir(anc)
                    except Exception:      # noqa: BLE001
                        return None
        return None

    def _verification_guard(self) -> "str | None":
        """#130 Holes 1+2: a verification checks a FINISHED profile. If Run type
        is Verification but the selected run has no built profile yet (Hole 1), or
        it has a profile but no verification chart yet (Hole 2), return a guiding
        message so the caller stops and explains. Keyed off the Profile-run bar,
        so it fires even when the loaded chart is a verify chart under
        verifications/ (Knut). None when the read may proceed."""
        if not self._is_verify_checked():
            return None
        run = self._guard_run()
        if run is None:
            return None        # external chart / no project run — model doesn't apply
        if run.dir.parent.name != "runs":
            return None
        if run.built_profile_icc().exists():
            # Hole 1 satisfied. Hole 2: a verification needs a verification chart
            # to measure. If the run has a profile but no verify chart yet, guide
            # the user to create one (a distinct message from Hole 1).
            if not run.has_verify_chart():
                return tr(
                    "No verification chart for this run yet.\n\n"
                    "This run has a finished profile, but you haven't created its "
                    "verification chart.\n\n"
                    "  1. Go to the Create Chart tab and, with “Run type” = "
                    "“Verification”, create the verification chart (a smaller "
                    "chart is fine).\n"
                    "  2. Print it through this run's profile (with colour "
                    "management on).\n"
                    "  3. Come back here with “Run type” = “Verification” and "
                    "measure it — the result is stored in a dated folder under "
                    "this run's “verifications” folder.")
            return None
        return tr(
            "A verification checks a finished profile — but this profile run "
            "doesn't have a built profile yet.\n\n"
            "To build the profile first:\n"
            "  1. Set “Run type” to “Profiling”.\n"
            "  2. Create, print and measure the profiling chart as normal — its "
            "measurement is stored in the run folder.\n"
            "  3. Build the profile on the Build Profile tab (this makes the "
            "profile's .icc / .icm file).\n\n"
            "Once the profile exists, you can verify it:\n"
            "  4. Set “Run type” back to “Verification”.\n"
            "  5. Create a verification chart in the Create Chart tab.\n"
            "  6. Print that chart THROUGH the finished profile (with colour "
            "management on).\n"
            "  7. Measure it here with “Run type” = “Verification” — the result "
            "is kept in a dated folder under this run's “verifications” folder.")

    def _uncheck_verification(self) -> None:
        cb = self._verify_cb if self._current_mode() == "guided" else self._m_verify_cb
        cb.setChecked(False)

    def set_calibration_mode(self, enabled: bool) -> None:
        """Hide guided mode toggle and lock to manual when calibration mode is active."""
        self._mode_row_widget.setVisible(not enabled)
        if enabled:
            self._switch_mode("manual")

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        """Re-tint the Stop button's disabled background for the active theme."""
        new_mode = "light" if mode == "light" else "dark"
        if new_mode == self._mode:
            return
        self._mode = new_mode
        if hasattr(self, "_stop_btn"):
            self._apply_stop_btn_style()

    def _apply_stop_btn_style(self) -> None:
        # The button keeps its light-grey "always-stand-out" base in both
        # themes; only the disabled state changes so it doesn't paint a
        # dark slab over the light tab background.
        if self._mode == "light":
            disabled_bg     = "#eeeae5"
            disabled_fg     = "#a8a4a0"
            disabled_border = "#ccc9c3"
        else:
            disabled_bg     = "#2a2a2a"
            disabled_fg     = "#555555"
            disabled_border = "#333333"
        self._stop_btn.setStyleSheet(
            "QPushButton { background: #f4f4f4; color: #121212; border: 1px solid #cccccc; font-weight: 600; }"
            "QPushButton:hover { background: #e0e0e0; border-color: #bbbbbb; }"
            f"QPushButton:disabled {{ background: {disabled_bg}; color: {disabled_fg}; border-color: {disabled_border}; }}"
        )

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ---- Left ----
        left_container = QWidget(self)
        self._left_panel = left_container
        left_container.setFixedWidth(580)
        lc_layout = QVBoxLayout(left_container)
        lc_layout.setContentsMargins(0, 0, 0, 0)
        lc_layout.setSpacing(0)

        # Header + mode buttons (outside scroll/stack)
        top_widget = QWidget(left_container)
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(16, 12, 16, 6)
        top_layout.setSpacing(8)
        # Load-chart + reveal-folder icons in the header's upper-right, like the
        # Create Chart and Print Chart tabs (Knut/Basti). The selected file still
        # shows in the Chart File frame below.
        from ui.widgets import PatchGridButton, RevealFolderButton
        self._load_ti1_btn = PatchGridButton(_TAB_COLOR, top_widget, page=True)
        self._load_ti1_btn.setToolTip(tr(
            "Load a chart file (.ti2) to measure.\n\n"
            "This is the laid-out chart ChromIQ made for you in Create Chart — "
            "the same one you printed. Pick it here and the preview shows the "
            "page(s) so you can read them strip by strip. The finished "
            "measurements are saved as a .ti3 file for building the profile."))
        self._load_ti1_btn.clicked.connect(self._on_load_ti2)
        self._reveal_btn = RevealFolderButton(_TAB_COLOR, top_widget)
        self._reveal_btn.setToolTip(tr(
            "Open this chart's folder in Finder / your file manager — where "
            "the chart, its measurements and the finished profile all live. "
            "Handy for finding the printable pages, or the ICC profile after "
            "you build it."))
        self._reveal_btn.clicked.connect(self._reveal_chart_folder)
        _hdr_trailing = QWidget(top_widget)
        _ht = QHBoxLayout(_hdr_trailing)
        _ht.setContentsMargins(0, 0, 0, 0)
        _ht.setSpacing(6)
        _ht.addWidget(self._load_ti1_btn)
        _ht.addWidget(self._reveal_btn)
        top_layout.addWidget(TabHeader(
            tr("STEP 03 · MEASURE CHART"), tr("Measure printed chart"), "#56d6a5", top_widget,
            tooltip_title=tr("Step 3 — Measure the print"),
            tooltip_body=(
                tr("On this screen, your spectrophotometer reads every colour patch "
                "on the printed chart and records what colour your printer actually "
                "produced. ChromIQ pairs each measurement with the RGB value that "
                "was requested in step 1, and saves the result as a .ti3 file.\n\n"
                "Before you start:\n"
                "• Your measurement device (e.g. i1Pro, ColorMunki, ColorMeter) "
                "MUST be plugged in via USB before you open this tab. If ChromIQ "
                "doesn't see it, unplug and replug, then restart the app.\n"
                "• The print must be fully dry — wet ink gives wrong readings.\n"
                "• Have the printed chart in front of you, well-lit, on a flat "
                "surface. Avoid direct sunlight.\n\n"
                "How to use this screen:\n"
                "• Guided mode walks you through reading the chart one strip (row) "
                "at a time. Recommended for first-timers.\n"
                "• Manual mode exposes every chartread option for advanced users.\n"
                "• Follow the on-screen prompts: place the device on the indicated "
                "patch or strip, press the button on the device, and wait for the "
                "beep before moving to the next.\n\n"
                "If you misread a patch, you can usually re-do that strip from the "
                "prompt. Don't rush — accurate reads now mean an accurate profile.\n\n"
                "Next step: build the ICC profile on tab 4.")
            ),
            trailing_widget=_hdr_trailing,
        ))
        _mode_font = QFont()
        _mode_font.setFamilies(["Menlo", "Consolas", "Courier New", "monospace"])
        _mode_font.setPointSize(11)
        _mode_font.setWeight(QFont.Weight.Bold)
        self._mode_row_widget = QWidget(top_widget)
        mode_row = QHBoxLayout(self._mode_row_widget)
        mode_row.setContentsMargins(0, 0, 0, 0)
        self._guided_btn = QPushButton(tr("GUIDED"), self._mode_row_widget)
        self._guided_btn.setCheckable(True)
        self._guided_btn.setChecked(True)
        self._guided_btn.setObjectName("mode_btn")
        self._guided_btn.setFont(_mode_font)
        self._manual_btn = QPushButton(tr("MANUAL"), self._mode_row_widget)
        self._manual_btn.setCheckable(True)
        self._manual_btn.setObjectName("mode_btn")
        self._manual_btn.setFont(_mode_font)
        self._guided_btn.clicked.connect(lambda: self._switch_mode("guided"))
        self._manual_btn.clicked.connect(lambda: self._switch_mode("manual"))
        mode_row.addWidget(self._guided_btn)
        mode_row.addWidget(self._manual_btn)
        mode_row.addStretch()
        top_layout.addWidget(self._mode_row_widget)
        lc_layout.addWidget(top_widget)

        # File selection — shared between modes
        file_outer = QWidget(left_container)
        fo_layout = QVBoxLayout(file_outer)
        fo_layout.setContentsMargins(16, 4, 16, 0)
        fo_layout.setSpacing(0)
        self._file_grp = file_grp = QGroupBox(tr("Chart File (.ti2)"), file_outer)
        file_grp.setFlat(True)
        fg = QVBoxLayout(file_grp)
        fg.setContentsMargins(8, 6, 8, 8)
        # The load + reveal buttons now live in the header's upper-right; this
        # frame just shows which chart is selected.
        file_row = QHBoxLayout()
        self._ti1_lbl = ElidingLabel(tr("No file selected"), file_outer)
        self._ti1_lbl.setStyleSheet("color: #909090; font-size: 11px;")
        file_row.addWidget(self._ti1_lbl, stretch=1)
        fg.addLayout(file_row)
        fo_layout.addWidget(file_grp)
        lc_layout.addWidget(file_outer)

        # Stacked panels
        self._stack = QStackedWidget(left_container)
        self._guided_panel = self._make_guided_panel()
        self._manual_panel = self._make_manual_panel()
        self._stack.addWidget(self._guided_panel)
        self._stack.addWidget(self._manual_panel)
        lc_layout.addWidget(self._stack, stretch=1)

        # Keep-calm block — guided mode only, sits directly above buttons
        calm_outer = QWidget(left_container)
        co_layout = QVBoxLayout(calm_outer)
        co_layout.setContentsMargins(16, 8, 16, 0)
        calm_box = QGroupBox(calm_outer)
        # Only override layout; let border + radius come from the global theme.
        calm_box.setStyleSheet(
            "QGroupBox { margin-top: 0px; padding: 14px 8px 12px 8px; }"
        )
        calm_layout = QVBoxLayout(calm_box)
        calm_layout.setContentsMargins(0, 0, 0, 0)
        calm_layout.setSpacing(4)
        headline = QLabel(tr("Keep calm<span style=\"color: {SPEC_GREEN}; font-style: italic;\">!</span>").format(SPEC_GREEN=SPEC_GREEN), calm_box)
        headline.setTextFormat(Qt.TextFormat.RichText)
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline.setStyleSheet(
            "background: transparent;"
            " font-family: Georgia; font-size: 28px;"
        )
        calm_layout.addWidget(headline)
        subtext = QLabel(tr("Scan each strip with a slow, steady motion."), calm_box)
        subtext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtext.setStyleSheet(
            "color: #808080; background: transparent;"
            " font-family: Menlo; font-size: 9px; font-weight: 300;"
        )
        calm_layout.addWidget(subtext)
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(0, 6, 0, 0)
        bar_row.setSpacing(0)
        bar_row.addStretch()
        for _color in TAB_COLORS:
            _seg = QFrame(calm_outer)
            _seg.setFixedSize(22, 2)
            _seg.setStyleSheet(f"background-color: {_color}; border: none;")
            bar_row.addWidget(_seg)
        bar_row.addStretch()
        calm_layout.addLayout(bar_row)
        co_layout.addWidget(calm_box)
        self._calm_outer = calm_outer
        lc_layout.addWidget(calm_outer)

        # Buttons — shared
        btn_outer = QWidget(left_container)
        bo_layout = QVBoxLayout(btn_outer)
        bo_layout.setContentsMargins(16, 6, 16, 8)
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton(tr("Start Measurement"), btn_outer)
        self._start_btn.setObjectName("primary")
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn = QPushButton(tr("Stop"), btn_outer)
        self._stop_btn.setFixedHeight(36)
        self._apply_stop_btn_style()
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        self._save_defaults_btn = QPushButton(tr("Save as Defaults"), btn_outer)
        self._save_defaults_btn.setFixedHeight(36)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._save_defaults_btn)
        bo_layout.addLayout(btn_row)

        # #131: master switch for measurement sounds (shared by both modes). The
        # individual sounds for each event are chosen in Preferences → Sounds.
        sound_row = QHBoxLayout()
        self._sound_cb = QCheckBox(tr("Play sounds during measurement"), btn_outer)
        self._sound_cb.setChecked(bool(self._settings.get("sound_enabled", False)))
        self._sound_cb.toggled.connect(self._on_sound_toggled)
        sound_row.addWidget(self._sound_cb)
        # Tooltip icon sits at the far right of the panel (Basti), not hugging
        # the checkbox label.
        sound_row.addStretch()
        sound_row.addWidget(TooltipButton(
            tr("Play sounds during measurement"),
            tr("Plays a short sound at each step of a measurement — a tick as "
               "each patch is read, a bell when a strip is finished, a warning "
               "if a reading looks off, and a fanfare when the whole chart is "
               "done. It's a hands-free way to follow the measurement without "
               "watching the screen.\n\n"
               "Choose which sound plays for each event, and add your own, in "
               "Preferences → Sounds. This switch is remembered between "
               "sessions."),
            btn_outer, min_width=460))
        bo_layout.addLayout(sound_row)
        lc_layout.addWidget(btn_outer)

        # Log — shared
        log_outer = QWidget(left_container)
        lo_layout = QVBoxLayout(log_outer)
        lo_layout.setContentsMargins(16, 0, 16, 12)
        self._log = QPlainTextEdit(log_outer)
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(100)
        self._log.setMaximumHeight(100)
        self._log.setPlaceholderText(tr("chartread output will appear here…"))
        lo_layout.addWidget(self._log)
        lc_layout.addWidget(log_outer)

        # Status bar (replaces main-window status bar)
        self._status_bar_lbl = QLabel("", left_container)
        self._status_bar_lbl.setWordWrap(True)
        self._status_bar_lbl.setVisible(False)
        lc_layout.addWidget(self._status_bar_lbl)

        splitter.addWidget(left_container)

        # ---- Right preview ----
        right = QWidget(self)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 12)
        rl.setSpacing(0)
        self._preview = TiffPreview(right)
        self._preview.stripe_clicked.connect(self._on_preview_strip_clicked)
        # The times are kept for the whole measurement, so turning to another
        # page of a multi-page chart must redraw them for THAT page (Knut,
        # #131 2026-07-26).
        self._preview.page_changed.connect(lambda _i: self._refresh_pace_panel(
            getattr(self, "_pace_verdict", ""),
            getattr(self, "_pace_verdict_colour", "#909090")))
        self._preview.patch_clicked.connect(self._on_preview_patch_clicked)
        self._preview.set_caption(tr("CHART PREVIEW"))
        rl.addWidget(self._preview, stretch=1)

        # #131 (Knut, 2026-07-26): reading pace, right under the chart where the
        # eye already is. Two lines — the strips read so far with the time each
        # scan took, and one large verdict line, green when the pace is fine and
        # red when it is too fast. Hidden until there is something to say, so it
        # takes no room from the preview otherwise.
        from ui.strip_times_panel import StripTimesPanel
        self._pace_panel = StripTimesPanel(right)
        rl.addWidget(self._pace_panel)
        # Times measured so far, per strip letter, plus whether each passed.
        self._pace_times: dict = {}
        self._pace_patches = 0

        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # Guided panel
    # ------------------------------------------------------------------

    def _make_guided_panel(self) -> QWidget:
        scroll = FadeScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 8, 16, 8)
        ll.setSpacing(10)

        # Instrument
        self._instr_grp = instr_grp = QGroupBox(tr("Measurement Instrument"), left)
        instr_grp.setFlat(True)
        ig = QVBoxLayout(instr_grp)
        ig.setContentsMargins(8, 6, 8, 8)
        instr_row = QHBoxLayout()
        instr_row.addWidget(QLabel(tr("Instrument port number:"), left))
        self._instr_spin = NoScrollSpinBox(left)
        self._instr_spin.setRange(1, 9)
        self._instr_spin.setValue(1)
        instr_row.addWidget(self._instr_spin)
        instr_row.addStretch()
        instr_row.addWidget(TooltipButton(
            tr("Instrument Port"),
            tr("Port index passed to chartread via -c.\n\n"
            "Most setups use 1. When chartread starts it prints a numbered\n"
            "list of detected instruments — set this to the number shown\n"
            "next to your spectrophotometer in that list.\n\n"
            "Only change it if you have more than one instrument connected\n"
            "at the same time."),
            left,
        ))
        ig.addLayout(instr_row)
        ll.addWidget(instr_grp)
        instr_grp.setVisible(False)

        # Core measurement options (always shown)
        self._core_grp = core_grp = QGroupBox(tr("Measurement Options"), left)
        cg = QVBoxLayout(core_grp)
        cg.setContentsMargins(8, 14, 8, 8)
        cg.setSpacing(8)

        def _bool_row(label, default, tt_title, tt_body):
            row = QHBoxLayout()
            cb = QCheckBox(label, left)
            cb.setChecked(default)
            row.addWidget(cb)
            row.addStretch()
            tip = TooltipButton(tt_title, tt_body, left)
            row.addWidget(tip)
            cg.addLayout(row)
            return cb, tip

        # Strip-recognition row: a single combo (Default / -B / -b) plus the
        # "Auto" toggle. Auto derives the value from the loaded chart's
        # instrument and greys out the combo while on. See _make_bidir_row.
        self._make_bidir_row(left, cg, "guided")

        self._suppress_cb, _ = _bool_row(
            tr("Suppress warning messages (-S)"), True,
            tr("Suppress Warnings (-S)"),
            tr("Suppresses non-fatal instrument warnings from chartread.\n\n"
            "Suppressed messages include: calibration drift notices,\n"
            "reflectance range warnings on very dark patches, and strip\n"
            "timing cautions. These rarely affect measurement quality.\n\n"
            "Fatal errors that would prevent a .ti3 from being written are\n"
            "always shown regardless of this setting."),
        )
        self._nocal_cb, _nocal_tip = _bool_row(
            tr("Skip initial calibration (-N)"), False,
            tr("Skip Initial Calibration (-N)"),
            tr("Skips the automatic white-tile calibration at chartread startup.\n\n"
            "Normally chartread prompts you to place the instrument on its\n"
            "white calibration tile before measuring begins. This ensures\n"
            "accurate absolute reflectance values and takes only a few seconds.\n\n"
            "Enable this only if you have already calibrated the instrument\n"
            "earlier in the same session and do not want to repeat the step."),
        )
        self._nocal_cb.setVisible(False)
        _nocal_tip.setVisible(False)
        self._pbp_cb, _pbp_tip = _bool_row(
            tr("Patch-by-patch mode (-p)"), False,
            tr("Patch-by-Patch Mode (-p)"),
            tr("Switches from strip reading to single-patch measurement mode.\n\n"
            "Instead of scanning entire strips, chartread guides you patch\n"
            "by patch across the chart. This is significantly slower — one\n"
            "reading per patch — but more reliable on heavily textured\n"
            "surfaces or when strip reading consistently fails on a\n"
            "particular chart layout."),
        )
        self._pbp_cb.setVisible(False)
        _pbp_tip.setVisible(False)

        resume_row = QHBoxLayout()
        self._resume_cb = QCheckBox(tr("Refine / resume existing measurement (-r)"), left)
        self._resume_cb.setChecked(False)
        self._resume_cb.setVisible(False)
        resume_row.addWidget(self._resume_cb)
        resume_row.addStretch()
        self._resume_tip = TooltipButton(
            tr("Refine / Resume Existing Measurement (-r)"),
            tr("Reuses the existing .ti3 file in the same folder as the\n"
            ".ti2 file. Previously measured strips are kept — you only need\n"
            "to scan the strips you want to update or add.\n\n"
            "Use this after a quality check to re-measure problem strips,\n"
            "or to continue a measurement that was interrupted.\n\n"
            "This option appears only when a matching .ti3 file is found."),
            left,
        )
        self._resume_tip.setVisible(False)
        resume_row.addWidget(self._resume_tip)
        cg.addLayout(resume_row)

        # Refinement file row — shown only when resume is checked
        self._refine_row = QWidget(left)
        refine_rl = QHBoxLayout(self._refine_row)
        refine_rl.setContentsMargins(20, 0, 0, 0)
        refine_rl.setSpacing(6)
        self._refine_cb = QCheckBox(
            tr("Use refinement strips file for guided re-measurement"),
            self._refine_row,
        )
        self._refine_cb.setEnabled(False)
        refine_rl.addWidget(self._refine_cb, stretch=1)
        refine_rl.addWidget(TooltipButton(
            tr("Refinement Strips File"),
            tr("Available when a Refine_Strips_<name>.txt file exists in\n"
            "the reports folder next to your chart.\n\n"
            "That file is created automatically by the Check && Refine\n"
            "tab after a quality check. It lists the strips with the\n"
            "highest colour errors, sorted worst-first.\n\n"
            "When active, the app navigates chartread to each of those\n"
            "strips automatically — you only need to scan them."),
            self._refine_row,
        ))
        self._refine_row.setVisible(False)
        cg.addWidget(self._refine_row)

        # #134: show the expected-vs-measured overlay from a measurement already
        # on disk. Like the resume option, it appears only when a matching .ti3
        # is found next to the chart.
        overlay_row = QHBoxLayout()
        self._overlay_cb = QCheckBox(
            tr("Show overlay from existing measurement"), left)
        self._overlay_cb.setChecked(False)
        self._overlay_cb.setVisible(False)
        self._overlay_cb.toggled.connect(self._on_overlay_toggled)
        overlay_row.addWidget(self._overlay_cb)
        overlay_row.addStretch()
        self._overlay_tip = TooltipButton(
            tr("Show overlay from existing measurement"),
            tr(_OVERLAY_TIP_BODY), left)
        self._overlay_tip.setVisible(False)
        overlay_row.addWidget(self._overlay_tip)
        cg.addLayout(overlay_row)

        precond_row = QHBoxLayout()
        self._use_precond_cb = QCheckBox(
            tr("Also use measurement data from the pre-conditioning profile"), left
        )
        self._use_precond_cb.setChecked(False)
        self._use_precond_cb.setVisible(False)
        precond_row.addWidget(self._use_precond_cb)
        precond_row.addStretch()
        self._precond_tip = TooltipButton(tr(_PRECOND_TIP_TITLE), tr(_PRECOND_TIP_BODY), left)
        self._precond_tip.setVisible(False)
        precond_row.addWidget(self._precond_tip)
        cg.addLayout(precond_row)

        self._resume_cb.stateChanged.connect(
            lambda state: self._refine_row.setVisible(
                state == Qt.CheckState.Checked.value
            )
        )
        self._resume_cb.toggled.connect(lambda _checked: self._refresh_start_button_label())

        ll.addWidget(core_grp)

        # Additional chartread arguments — structured
        self._adv_grp = adv_grp = QGroupBox(tr("Additional Options"), left)
        ag = QVBoxLayout(adv_grp)
        ag.setContentsMargins(8, 14, 8, 8)
        ag.setSpacing(6)

        self._chartread_opts = self._make_chartread_options(left)
        for opt in self._chartread_opts:
            row_w = QWidget(left)
            row = QHBoxLayout(row_w)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            opt.row_widget = row_w

            cb = QCheckBox(opt.label, left)
            cb.setChecked(False)
            opt.checkbox = cb

            if opt.widget is not None:
                opt.widget.setEnabled(False)
                cb.toggled.connect(opt.widget.setEnabled)
                row.addWidget(cb, stretch=1)
                row.addWidget(opt.widget)
            else:
                row.addWidget(cb, stretch=1)

            row.addWidget(TooltipButton(opt.tooltip_title, opt.tooltip_body, left, min_width=opt.tooltip_width))
            ag.addWidget(row_w)

        for opt in self._chartread_opts:
            if opt.key == "tolerance":
                opt.checkbox.setChecked(True)
                if opt.widget is not None:
                    opt.widget.setValue(0.7)
                    opt.widget.setEnabled(True)
            else:
                if opt.row_widget is not None:
                    opt.row_widget.setVisible(False)

        ll.addWidget(adv_grp)

        verify_grp = QGroupBox(tr("Profile verification"), left)
        vg = QVBoxLayout(verify_grp)
        vg.setContentsMargins(8, 14, 8, 8)
        verify_row = QHBoxLayout()
        self._verify_cb = QCheckBox(
            tr("Verification measurement (colour-managed print)"), left)
        verify_row.addWidget(self._verify_cb)
        verify_row.addStretch()
        verify_row.addWidget(
            TooltipButton(tr(_VERIFY_TIP_TITLE), tr(_VERIFY_TIP_BODY), left))
        vg.addLayout(verify_row)
        ll.addWidget(verify_grp)
        ll.addStretch(1)

        scroll.setWidget(left)
        # The scroll's inner content — disabled during a measurement while the
        # scroll AREA stays live, so the panel is still scrollable (#42).
        self._g_options = left
        # Wrap the scroll so the guided module gets the same always-visible
        # "Live preview" group below it (#44, Basti) — usable while a read runs.
        container = QWidget()
        gcl = QVBoxLayout(container)
        gcl.setContentsMargins(0, 0, 0, 0)
        gcl.setSpacing(0)
        gcl.addWidget(scroll, stretch=1)
        # Inset the group by the same 16 px the scrolling sections use (their
        # content carries it), so it doesn't run edge-to-edge and look too wide.
        _vg_wrap = QWidget()
        _vg_wl = QVBoxLayout(_vg_wrap)
        _vg_wl.setContentsMargins(16, 0, 16, 8)
        _vg_wl.addWidget(self._make_live_preview_group("g"))
        gcl.addWidget(_vg_wrap)
        self._g_view_grp.setVisible(self._engine_selected())
        return container

    def _make_live_preview_group(self, prefix: str) -> QGroupBox:
        """The engine's "Live preview" view controls, shared by the Manual and
        Guided modules (#126, Knut/Basti). *prefix* is "m" or "g"; each module
        gets its own combo + checkbox (independent widgets that both drive the
        one shared chart preview). Built as a self-contained group placed OUTSIDE
        the scrolling parameter area, so it stays visible and usable while a
        measurement locks the parameters, and its state saves as defaults / in a
        preset. Stores self._{prefix}_view_grp / _engine_row / _overlay_mode /
        _only_measured / _patch_tile."""
        grp = QGroupBox(tr("Live preview"), self)
        grp.setFlat(True)
        gv = QVBoxLayout(grp)
        gv.setContentsMargins(8, 6, 8, 8)
        gv.setSpacing(6)
        row = QWidget(grp)
        v = QVBoxLayout(row)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        show_row = QHBoxLayout()
        show_row.setContentsMargins(0, 0, 0, 0)
        show_row.setSpacing(6)
        show_row.addWidget(QLabel(tr("Each patch shows:"), row))
        combo = NoScrollComboBox(row)
        combo.setObjectName("compact_input")
        combo.setMinimumWidth(210)
        combo.addItem(tr("Expected & measured (split)"), "both")
        combo.addItem(tr("Expected colour only"), "expected")
        combo.addItem(tr("Measured colour only"), "measured")
        combo.currentIndexChanged.connect(
            lambda _i, p=prefix: self._on_view_control_changed(p))
        show_row.addWidget(combo)
        show_row.addStretch(1)
        show_row.addWidget(TooltipButton(
            tr("What each patch shows"),
            tr("Choose what the coloured patches in the preview show:\n\n"
            "  • Expected & measured (split) — each patch is split diagonally: "
            "the colour the chart expected in the upper-left, what the "
            "instrument actually measured in the lower-right. Differences jump "
            "out at the seam.\n"
            "  • Expected colour only — every patch shows the colour the chart "
            "was supposed to have.\n"
            "  • Measured colour only — every patch shows what your instrument "
            "read; patches you haven't read yet keep their expected colour.\n\n"
            "You can switch between these at any time, during a measurement "
            "or after it's finished — it only changes the preview, never your "
            "readings. (Screen colours are approximate; the numbers in your "
            "file are exact.)"),
            row))
        v.addLayout(show_row)

        only = QCheckBox(tr("Show only measured patches"), row)
        only.toggled.connect(
            lambda _on, p=prefix: self._on_view_control_changed(p))
        tile = QCheckBox(tr("Show patch values on hover"), row)
        tile.toggled.connect(
            lambda _on, p=prefix: self._on_view_control_changed(p))
        # Two options share this row: "only measured" on the left with its help
        # icon right beside it, then a stretch, then "values on hover" with its
        # own help icon on the right (Basti).
        om_row = QHBoxLayout()
        om_row.setContentsMargins(0, 0, 0, 0)
        om_row.setSpacing(0)
        om_row.addWidget(only)
        om_row.addSpacing(10)   # a little breathing room before the help icon
        om_row.addWidget(TooltipButton(
            tr("Show only measured patches"),
            tr("Turn this on to see your progress through the chart at a glance: "
            "every patch you have already read keeps its colour (or split), and "
            "every patch you have NOT read yet is blanked to white with a thin "
            "outline.\n\nAs you work down the strips, the white area shrinks and "
            "the coloured, measured area grows — so it's instantly clear how far "
            "you've come and which rows are still to do. Turn it off to see the "
            "whole printed chart again. It only changes the preview, never your "
            "readings."),
            row))
        om_row.addStretch(1)
        om_row.addWidget(tile)
        om_row.addSpacing(10)   # same breathing room before its help icon
        om_row.addWidget(TooltipButton(
            tr("Show patch values on hover"),
            tr("Turn this on to inspect any patch you've already measured: point "
            "at it and a small card appears next to your mouse with the exact "
            "numbers behind the two colours in the split — what the chart "
            "expected, and what your instrument actually read.\n\n"
            "For each colour the card shows RGB (roughly the colour you see on "
            "screen) and L*a*b* (the exact measurement), plus the ΔE between "
            "them — how far the print landed from the target for that single "
            "patch. A large ΔE on a strong, saturated colour is normal (paper "
            "simply can't reach every colour a screen can); what you're really "
            "looking for is one patch that sits far off its neighbours.\n\n"
            "The card follows the 'Each patch shows' setting above: with "
            "'Expected & measured (split)' you get both colours and the ΔE; with "
            "'Expected colour only' or 'Measured colour only' you get just that "
            "one. It only reads out numbers — it never changes your readings."),
            row))
        v.addLayout(om_row)

        gv.addWidget(row)
        setattr(self, f"_{prefix}_view_grp", grp)
        setattr(self, f"_{prefix}_engine_row", row)
        setattr(self, f"_{prefix}_overlay_mode", combo)
        setattr(self, f"_{prefix}_only_measured", only)
        setattr(self, f"_{prefix}_patch_tile", tile)
        return grp

    # ------------------------------------------------------------------
    # Manual panel
    # ------------------------------------------------------------------

    def _make_manual_panel(self) -> QWidget:
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(16, 8, 16, 0)
        cl.setSpacing(0)

        # Presets group
        presets_grp = self._m_presets_grp = QGroupBox(tr("Presets"), container)
        presets_row = QHBoxLayout(presets_grp)
        presets_row.setContentsMargins(8, 4, 8, 8)
        presets_row.addWidget(QLabel(tr("Select preset:"), container))
        self._m_preset_combo = NoScrollComboBox(container)
        self._m_preset_combo.addItem(tr("none"), userData=None)
        presets_row.addWidget(self._m_preset_combo, stretch=1)
        self._m_preset_add_btn = QPushButton(container)
        self._m_preset_add_btn.setObjectName("icon_btn")
        self._m_preset_add_btn.setFixedSize(28, 28)
        set_preset_icon(self._m_preset_add_btn, "plus")
        self._m_preset_add_btn.setToolTip(tr("Save current settings as a new preset"))
        self._m_preset_del_btn = QPushButton(container)
        self._m_preset_del_btn.setObjectName("icon_btn")
        self._m_preset_del_btn.setFixedSize(28, 28)
        set_preset_icon(self._m_preset_del_btn, "minus")
        self._m_preset_del_btn.setToolTip(tr("Delete selected preset"))
        self._m_preset_del_btn.setEnabled(False)
        self._m_preset_reveal_btn = QPushButton(container)
        self._m_preset_reveal_btn.setObjectName("icon_btn")
        self._m_preset_reveal_btn.setFixedSize(28, 28)
        set_folder_icon(self._m_preset_reveal_btn, "folder_measure")
        self._m_preset_reveal_btn.setToolTip(
            tr("Open this tab's presets folder in Finder/Explorer.\n"
            "Each preset is a plain .json file — copy one to a colleague\n"
            "and they can drop it into their own folder to share.")
        )
        self._m_preset_reveal_btn.clicked.connect(
            lambda: reveal_in_file_manager(tab_dir("measure"))
        )
        presets_row.addWidget(self._m_preset_add_btn)
        presets_row.addWidget(self._m_preset_del_btn)
        presets_row.addWidget(self._m_preset_reveal_btn)
        presets_row.addWidget(TooltipButton(
            tr("Manual Presets"),
            tr("Save and recall named snapshots of all Manual mode settings.\n\n"
            "  +  Save current parameter values as a new named preset.\n"
            "  −  Delete the currently selected preset.\n"
            "  ▢  Open this tab's presets folder in Finder/Explorer.\n\n"
            "Select a preset from the dropdown to instantly restore all\n"
            "values. The Default entry always resets to built-in defaults.\n\n"
            "Presets are stored as plain .json files — one per preset —\n"
            "in a ChromIQ folder under your system's Preferences / AppData\n"
            "/ config location. Use the folder button (▢) on the right of\n"
            "the preset row to open it. To share a preset, copy the .json\n"
            "out of that folder and send it to a colleague; to install a\n"
            "shared preset, drop the .json into the matching folder on the\n"
            "target machine and ChromIQ will pick it up on the next launch.\n\n"
            "Presets persist between sessions."),
            container,
            min_width=600,
        ))
        self._m_preset_combo.currentIndexChanged.connect(self._on_m_preset_selected)
        self._m_preset_add_btn.clicked.connect(self._on_m_preset_save)
        self._m_preset_del_btn.clicked.connect(self._on_m_preset_delete)
        cl.addWidget(presets_grp)
        cl.addSpacing(8)

        scroll = FadeScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 8, 0, 8)
        ll.setSpacing(10)

        # Instrument — mirrors guided "Measurement Instrument" group
        m_instr_grp = QGroupBox(tr("Measurement Instrument"), left)
        m_instr_grp.setFlat(True)
        mig = QVBoxLayout(m_instr_grp)
        mig.setContentsMargins(8, 6, 8, 8)
        m_instr_row = QHBoxLayout()
        m_instr_row.addWidget(QLabel(tr("Instrument port number:"), left))
        self._m_instr_spin = NoScrollSpinBox(left)
        self._m_instr_spin.setRange(1, 9)
        self._m_instr_spin.setValue(1)
        self._m_instr_spin.setFixedWidth(61)
        self._m_instr_spin.setObjectName("compact_input")
        m_instr_row.addWidget(self._m_instr_spin)
        m_instr_row.addStretch()
        m_instr_row.addWidget(TooltipButton(
            tr("Instrument Port"),
            tr("Port index passed to chartread via -c.\n\n"
            "Most setups use 1. When chartread starts it prints a numbered\n"
            "list of detected instruments — set this to the number shown\n"
            "next to your spectrophotometer in that list.\n\n"
            "Only change it if you have more than one instrument connected\n"
            "at the same time."),
            left,
        ))
        mig.addLayout(m_instr_row)
        ll.addWidget(m_instr_grp)

        # Measurement Options — mirrors guided "Measurement Options" group
        m_core_grp = QGroupBox(tr("Measurement Options"), left)
        mcg = QVBoxLayout(m_core_grp)
        mcg.setContentsMargins(8, 14, 8, 8)
        mcg.setSpacing(8)

        def _bool_row_m(label, default, tt_title, tt_body):
            row = QHBoxLayout()
            cb = QCheckBox(label, left)
            cb.setChecked(default)
            row.addWidget(cb)
            row.addStretch()
            row.addWidget(TooltipButton(tt_title, tt_body, left))
            mcg.addLayout(row)
            return cb

        # Strip-recognition row (mirrors guided): single combo + Auto toggle.
        self._make_bidir_row(left, mcg, "manual")

        self._m_suppress_cb = _bool_row_m(
            tr("Suppress warning messages (-S)"), True,
            tr("Suppress Warnings (-S)"),
            tr("Suppresses non-fatal instrument warnings from chartread.\n\n"
            "Suppressed messages include: calibration drift notices,\n"
            "reflectance range warnings on very dark patches, and strip\n"
            "timing cautions. These rarely affect measurement quality.\n\n"
            "Fatal errors that would prevent a .ti3 from being written are\n"
            "always shown regardless of this setting."),
        )
        self._m_nocal_cb = _bool_row_m(
            tr("Skip initial calibration (-N)"), False,
            tr("Skip Initial Calibration (-N)"),
            tr("Skips the automatic white-tile calibration at chartread startup.\n\n"
            "Normally chartread prompts you to place the instrument on its\n"
            "white calibration tile before measuring begins. This ensures\n"
            "accurate absolute reflectance values and takes only a few seconds.\n\n"
            "Enable this only if you have already calibrated the instrument\n"
            "earlier in the same session and do not want to repeat the step."),
        )
        self._m_pbp_cb = _bool_row_m(
            tr("Patch-by-patch mode (-p)"), False,
            tr("Patch-by-Patch Mode (-p)"),
            tr("Switches from strip reading to single-patch measurement mode.\n\n"
            "Instead of scanning entire strips, chartread guides you patch\n"
            "by patch across the chart. This is significantly slower — one\n"
            "reading per patch — but more reliable on heavily textured\n"
            "surfaces or when strip reading consistently fails on a\n"
            "particular chart layout."),
        )

        m_resume_row = QHBoxLayout()
        self._m_resume_cb = QCheckBox(tr("Refine / resume existing measurement (-r)"), left)
        self._m_resume_cb.setChecked(False)
        self._m_resume_cb.setVisible(False)
        m_resume_row.addWidget(self._m_resume_cb)
        m_resume_row.addStretch()
        self._m_resume_tip = TooltipButton(
            tr("Refine / Resume Existing Measurement (-r)"),
            tr("Reuses the existing .ti3 file in the same folder as the\n"
            ".ti2 file. Previously measured strips are kept — you only need\n"
            "to scan the strips you want to update or add.\n\n"
            "Use this after a quality check to re-measure problem strips,\n"
            "or to continue a measurement that was interrupted.\n\n"
            "This option appears only when a matching .ti3 file is found."),
            left,
        )
        self._m_resume_tip.setVisible(False)
        m_resume_row.addWidget(self._m_resume_tip)
        mcg.addLayout(m_resume_row)

        # The engine "Live preview" view controls (patch-colour mode + show-only-
        # measured) are built as a shared group by _make_live_preview_group and
        # placed OUTSIDE this scrolling area (see the panel tail), so they stay
        # visible and usable while a measurement locks the parameters (#126).
        # The autosave reassurance lives on the preview itself (as a banner
        # under the caption), not here — see _set_autosave_banner().
        # The click-a-strip tip lives at the BOTTOM of the manual options
        # (built later), not here — see self._m_engine_tip.
        # ------------------------------------------------------------------

        self._m_refine_row = QWidget(left)
        m_refine_rl = QHBoxLayout(self._m_refine_row)
        m_refine_rl.setContentsMargins(20, 0, 0, 0)
        m_refine_rl.setSpacing(6)
        self._m_refine_cb = QCheckBox(
            tr("Use refinement strips file for guided re-measurement"),
            self._m_refine_row,
        )
        self._m_refine_cb.setEnabled(False)
        m_refine_rl.addWidget(self._m_refine_cb, stretch=1)
        m_refine_rl.addWidget(TooltipButton(
            tr("Refinement Strips File"),
            tr("Available when a Refine_Strips_<name>.txt file exists in\n"
            "the reports folder next to your chart.\n\n"
            "That file is created automatically by the Check && Refine\n"
            "tab after a quality check. It lists the strips with the\n"
            "highest colour errors, sorted worst-first.\n\n"
            "When active, the app navigates chartread to each of those\n"
            "strips automatically — you only need to scan them."),
            self._m_refine_row,
        ))
        self._m_refine_row.setVisible(False)
        mcg.addWidget(self._m_refine_row)

        # #134: manual-mode counterpart of the "Show overlay from existing
        # measurement" toggle (kept in sync with the guided one).
        m_overlay_row = QHBoxLayout()
        self._m_overlay_cb = QCheckBox(
            tr("Show overlay from existing measurement"), left)
        self._m_overlay_cb.setChecked(False)
        self._m_overlay_cb.setVisible(False)
        self._m_overlay_cb.toggled.connect(self._on_overlay_toggled)
        m_overlay_row.addWidget(self._m_overlay_cb)
        m_overlay_row.addStretch()
        self._m_overlay_tip = TooltipButton(
            tr("Show overlay from existing measurement"),
            tr(_OVERLAY_TIP_BODY), left)
        self._m_overlay_tip.setVisible(False)
        m_overlay_row.addWidget(self._m_overlay_tip)
        mcg.addLayout(m_overlay_row)

        # Measurement report (Knut) — accuracy stats + drift-over-time for the
        # current chart. Available for any measured chart (engine or not).
        _report_row = QHBoxLayout()
        _report_row.setContentsMargins(0, 0, 0, 0)
        _report_row.setSpacing(6)
        self._m_report_btn = QPushButton(tr("Measurement report…"), left)
        # min-height in the button's OWN stylesheet — the app QSS min-height on
        # QPushButton otherwise overrides setFixedHeight (feedback_qt_button_sizing).
        self._m_report_btn.setStyleSheet(
            "QPushButton { min-height: 20px; max-height: 24px; padding: 2px 12px; }")
        self._m_report_btn.clicked.connect(self._open_measurement_report)
        _report_row.addWidget(self._m_report_btn)
        _report_row.addStretch(1)                       # push the tip icon to the right
        _report_row.addWidget(TooltipButton(
            tr("Measurement report"),
            tr("Opens a report on the chart you've measured: how close each "
            "patch came to the colour the chart was designed to have — the "
            "average, worst and spread of the colour difference (ΔE00), the "
            "worst-offending patches with their colours side by side, and the "
            "paper white and darkest black.\n\n"
            "Its real strength is comparing over time: if you turn on "
            "“Save a measurement report after each measurement” in "
            "Settings, ChromIQ keeps a dated report beside every chart, and "
            "this window shows how the latest one has changed from the last — "
            "a rising colour difference or a shifting white/black points to "
            "ageing inks, a drifting printer, or a drifting instrument.\n\n"
            "Measure the chart first, then open this. Screen colours are "
            "approximate; the numbers come from your measurement file."),
            left))
        mcg.addLayout(_report_row)

        m_precond_row = QHBoxLayout()
        self._m_use_precond_cb = QCheckBox(
            tr("Also use measurement data from the pre-conditioning profile"), left
        )
        self._m_use_precond_cb.setChecked(False)
        self._m_use_precond_cb.setVisible(False)
        m_precond_row.addWidget(self._m_use_precond_cb)
        m_precond_row.addStretch()
        self._m_precond_tip = TooltipButton(tr(_PRECOND_TIP_TITLE), tr(_PRECOND_TIP_BODY), left)
        self._m_precond_tip.setVisible(False)
        m_precond_row.addWidget(self._m_precond_tip)
        mcg.addLayout(m_precond_row)

        self._m_resume_cb.stateChanged.connect(
            lambda state: self._m_refine_row.setVisible(
                state == Qt.CheckState.Checked.value
            )
        )
        self._m_resume_cb.toggled.connect(lambda _checked: self._refresh_start_button_label())

        ll.addWidget(m_core_grp)

        # Additional Options — mirrors guided "Additional Options" group
        m_adv_grp = QGroupBox(tr("Additional Options"), left)
        mag = QVBoxLayout(m_adv_grp)
        mag.setContentsMargins(8, 14, 8, 8)
        mag.setSpacing(6)

        self._m_chartread_opts = self._make_manual_chartread_options(left)
        for opt in self._m_chartread_opts:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            cb = QCheckBox(opt.label, left)
            cb.setChecked(False)
            opt.checkbox = cb
            if opt.widget is not None:
                opt.widget.setEnabled(False)
                cb.toggled.connect(opt.widget.setEnabled)
                row.addWidget(cb, stretch=1)
                row.addWidget(opt.widget)
            else:
                row.addWidget(cb, stretch=1)
            row.addWidget(TooltipButton(opt.tooltip_title, opt.tooltip_body, left, min_width=opt.tooltip_width))
            mag.addLayout(row)

        ll.addWidget(m_adv_grp)

        m_verify_grp = QGroupBox(tr("Profile verification"), left)
        mvg = QVBoxLayout(m_verify_grp)
        mvg.setContentsMargins(8, 14, 8, 8)
        m_verify_row = QHBoxLayout()
        self._m_verify_cb = QCheckBox(
            tr("Verification measurement (colour-managed print)"), left)
        m_verify_row.addWidget(self._m_verify_cb)
        m_verify_row.addStretch()
        m_verify_row.addWidget(
            TooltipButton(tr(_VERIFY_TIP_TITLE), tr(_VERIFY_TIP_BODY), left))
        mvg.addLayout(m_verify_row)
        ll.addWidget(m_verify_grp)

        # Click-a-strip tip — at the BOTTOM of the manual options (Knut: it
        # looked out of place in the middle). Shown only with the engine on.
        self._m_engine_tip = QWidget(left)
        _tip_row = QHBoxLayout(self._m_engine_tip)
        _tip_row.setContentsMargins(0, 4, 0, 0)
        _tip_row.setSpacing(6)
        _tip_lbl = QLabel(
            tr("Tip: click any strip in the chart preview to jump straight "
               "to it — for example to measure a strip again."),
            self._m_engine_tip)
        _tip_lbl.setWordWrap(True)
        _tip_row.addWidget(_tip_lbl, stretch=1)
        _tip_row.addWidget(TooltipButton(
            tr("Jumping between strips"),
            tr("With the ChromIQ chart-reading engine on, you don't have to "
            "step through the strips one by one.\n\n"
            "Simply click a strip directly in the chart preview on the "
            "right — while a measurement is running, every strip under your "
            "mouse shows a hand cursor. Clicking takes you straight there.\n\n"
            "Strips you have already read are marked with a check mark; "
            "clicking one lets you measure it again — handy after a smudge, "
            "a misread, or when Check && Refine has flagged strips worth a "
            "second pass. Guided refinement uses the very same jump "
            "automatically.\n\n"
            "This tip appears because the ChromIQ chart-reading engine is "
            "enabled in Preferences → Beta features."),
            self._m_engine_tip))
        self._m_engine_tip.setVisible(False)
        ll.addWidget(self._m_engine_tip)
        ll.addStretch(1)

        scroll.setWidget(left)
        self._m_options = left          # scroll content — locked during a read
        cl.addWidget(scroll, stretch=1)

        # "Live preview" view controls — their own group BELOW the scroll, so
        # they stay visible + usable while a measurement locks the parameters,
        # and save as defaults / in a preset (#126 follow-up, Knut/Basti).
        cl.addWidget(self._make_live_preview_group("m"))
        # Only meaningful with the chart-reading engine on; hidden otherwise.
        self._m_view_grp.setVisible(self._engine_selected())
        return container

    # ------------------------------------------------------------------
    # Manual preset helpers (Measure tab)
    # ------------------------------------------------------------------

    def _m_load_presets(self) -> dict:
        return _load_tab_presets("measure", self._settings)

    def _m_save_presets(self, presets: dict) -> None:
        _save_tab_presets("measure", presets)

    def _m_populate_preset_combo(self, presets: dict, select_name: str | None = None) -> None:
        self._m_preset_combo.blockSignals(True)
        self._m_preset_combo.clear()
        self._m_preset_combo.addItem(tr("none"), userData=None)
        for name in presets:
            self._m_preset_combo.addItem(name, userData=name)
        if select_name is not None:
            idx = self._m_preset_combo.findText(select_name)
            if idx >= 0:
                self._m_preset_combo.setCurrentIndex(idx)
        self._m_preset_combo.blockSignals(False)
        self._m_preset_del_btn.setEnabled(self._m_preset_combo.currentIndex() > 0)

    def _m_collect_preset_data(self) -> dict:
        data: dict = {
            "instr":      self._m_instr_spin.value(),
            "bidir_mode": self._m_bidir_combo.currentData(),
            "bidir_auto": self._m_bidir_auto_cb.isChecked(),
            "suppress":   self._m_suppress_cb.isChecked(),
            "nocal":      self._m_nocal_cb.isChecked(),
            "pbp":        self._m_pbp_cb.isChecked(),
            "verify":     self._m_verify_cb.isChecked(),
            # "Live preview" view controls (#126) — preview-only, but saved so a
            # preset restores the whole workspace look the user prefers.
            "overlay_mode":  self._m_overlay_mode.currentData(),
            "only_measured": self._m_only_measured.isChecked(),
            "patch_tile":    self._m_patch_tile.isChecked(),
        }
        for opt in self._m_chartread_opts:
            if opt.checkbox:
                data[f"{opt.key}_enabled"] = opt.checkbox.isChecked()
            if opt.widget is not None:
                if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                    data[f"{opt.key}_value"] = opt.widget.value()
                elif isinstance(opt.widget, QComboBox):
                    data[f"{opt.key}_value"] = opt.widget.currentData()
        return data

    def _m_apply_preset_data(self, data: dict) -> None:
        try:
            self._m_instr_spin.setValue(int(data.get("instr", 1)))
        except (ValueError, TypeError):
            pass
        self._set_bidir_value(self._m_bidir_combo, self._coerce_bidir_mode(
            data.get("bidir_mode"), bool(data.get("bidir")), bool(data.get("force_bidir"))))
        self._m_bidir_auto_cb.setChecked(bool(data.get("bidir_auto", True)))
        self._m_suppress_cb.setChecked(bool(data.get("suppress", True)))
        self._m_nocal_cb.setChecked(bool(data.get("nocal", False)))
        self._m_pbp_cb.setChecked(bool(data.get("pbp", False)))
        self._m_verify_cb.setChecked(bool(data.get("verify", False)))
        _om = self._m_overlay_mode.findData(data.get("overlay_mode", "both"))
        if _om >= 0:
            self._m_overlay_mode.setCurrentIndex(_om)
        self._m_only_measured.setChecked(bool(data.get("only_measured", False)))
        self._m_patch_tile.setChecked(bool(data.get("patch_tile", False)))
        for opt in self._m_chartread_opts:
            if opt.checkbox:
                opt.checkbox.setChecked(bool(data.get(f"{opt.key}_enabled", False)))
            if opt.widget is not None:
                val = data.get(f"{opt.key}_value")
                if val is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        try:
                            opt.widget.setValue(float(val))
                        except (ValueError, TypeError):
                            pass
                    elif isinstance(opt.widget, QComboBox):
                        idx = opt.widget.findData(str(val))
                        if idx >= 0:
                            opt.widget.setCurrentIndex(idx)
        self._apply_bidir_auto_state("manual")

    def _on_m_preset_selected(self, index: int) -> None:
        self._m_preset_del_btn.setEnabled(index > 0)
        s = self._settings
        if index == 0:
            # Restore from individual manual2_chartread_* settings
            try:
                self._m_instr_spin.setValue(int(s.get("manual2_chartread_instr", 1)))
            except (ValueError, TypeError):
                pass
            self._set_bidir_value(self._m_bidir_combo, self._coerce_bidir_mode(
                s.get("manual2_chartread_bidir_mode"),
                bool(s.get("manual2_chartread_bidir", False)),
                bool(s.get("manual2_chartread_force_bidir", False))))
            self._m_bidir_auto_cb.setChecked(bool(s.get("manual2_chartread_bidir_auto", True)))
            self._m_suppress_cb.setChecked(bool(s.get("manual2_chartread_suppress", True)))
            self._m_nocal_cb.setChecked(bool(s.get("manual2_chartread_nocal", False)))
            self._m_pbp_cb.setChecked(bool(s.get("manual2_chartread_pbp", False)))
            _om = self._m_overlay_mode.findData(s.get("manual2_overlay_mode", "both"))
            if _om >= 0:
                self._m_overlay_mode.setCurrentIndex(_om)
            self._m_only_measured.setChecked(bool(s.get("manual2_only_measured", False)))
            self._m_patch_tile.setChecked(bool(s.get("manual2_patch_tile", False)))
            for opt in self._m_chartread_opts:
                if opt.checkbox:
                    opt.checkbox.setChecked(bool(s.get(f"manual2_chartread_{opt.key}_enabled", False)))
                if opt.widget is not None:
                    val = s.get(f"manual2_chartread_{opt.key}_value")
                    if val is not None:
                        if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                            try:
                                opt.widget.setValue(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif isinstance(opt.widget, QComboBox):
                            idx = opt.widget.findData(str(val))
                            if idx >= 0:
                                opt.widget.setCurrentIndex(idx)
            self._apply_bidir_auto_state("manual")
        else:
            name = self._m_preset_combo.currentData()
            presets = self._m_load_presets()
            self._m_apply_preset_data(presets.get(name, {}))

    def _on_m_preset_save(self) -> None:
        data = self._m_collect_preset_data()
        dlg = QInputDialog(self)
        dlg.setWindowTitle(tr("Save Preset"))
        dlg.setLabelText(
            tr("Give this preset a name.\n"
            "All current Manual mode settings will be saved under that name\n"
            "and can be recalled at any time from the preset list.")
        )
        dlg.setMinimumWidth(460)
        if not dlg.exec():
            return
        name = dlg.textValue().strip()
        if not name:
            return
        presets = self._m_load_presets()
        presets[name] = data
        self._m_save_presets(presets)
        self._m_populate_preset_combo(presets, select_name=name)

    def _on_m_preset_delete(self) -> None:
        name = self._m_preset_combo.currentText()
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Delete Preset"))
        dlg.setMinimumWidth(460)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setSpacing(10)
        dlg_layout.setContentsMargins(20, 20, 20, 16)
        heading = QLabel(tr("Delete the preset \"{name}\"?").format(name=name), dlg)
        heading.setStyleSheet("font-weight: bold;")
        heading.setWordWrap(True)
        dlg_layout.addWidget(heading)
        info = QLabel(
            tr("All parameter values saved in this preset will be permanently removed. "
            "This cannot be undone."),
            dlg,
        )
        info.setWordWrap(True)
        dlg_layout.addWidget(info)
        bb = QDialogButtonBox(dlg)
        bb.addButton(tr("Cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        del_btn = bb.addButton(tr("Delete"), QDialogButtonBox.ButtonRole.AcceptRole)
        del_btn.setObjectName("primary")
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        dlg_layout.addWidget(bb)
        tint_dialog_primary(dlg, _TAB_COLOR)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        presets = self._m_load_presets()
        presets.pop(name, None)
        self._m_save_presets(presets)
        self._m_populate_preset_combo(presets)

    # ------------------------------------------------------------------
    # Chartread option rows (guided panel)
    # ------------------------------------------------------------------

    def _make_chartread_options(self, parent: QWidget) -> list[_ChartreadOption]:
        opts = []

        def _spinbox(lo, hi, step, default, decimals=0):
            if decimals > 0:
                sb = NoScrollDoubleSpinBox(parent)
                sb.setRange(lo, hi)
                sb.setSingleStep(step)
                sb.setDecimals(decimals)
                sb.setValue(default)
                sb.setFixedWidth(90)
            else:
                sb = NoScrollSpinBox(parent)
                sb.setRange(int(lo), int(hi))
                sb.setSingleStep(int(step))
                sb.setValue(int(default))
                sb.setFixedWidth(90)
            sb.setObjectName("compact_input")
            return sb

        opts.append(_ChartreadOption(
            key="highres", flag="-H",
            label=tr("High resolution spectral mode (-H)"),
            tooltip_title=tr("High Resolution Spectral Mode (-H)"),
            tooltip_body=(
                tr("Enables high-resolution spectral sampling on instruments that\n"
                "support it (i1Pro 2 and i1Pro 3).\n\n"
                "Standard mode samples the spectrum at 10 nm intervals.\n"
                "High-resolution mode uses 5 nm intervals, capturing finer\n"
                "spectral detail and improving colour accuracy for profiling,\n"
                "particularly on saturated or fluorescent colours.\n\n"
                "The measurement time increase is small (roughly 10–20% per\n"
                "strip). Leave this off unless you specifically need the\n"
                "extra spectral resolution.")
            ),
        ))

        filter_combo = NoScrollComboBox(parent)
        filter_combo.setFixedWidth(130)
        filter_combo.setObjectName("compact_input")
        for code, lbl in [("n", "None (M0)"), ("5", "D50 (M1)"), ("6", "D65"), ("u", "UV Cut (M2)"), ("p", "Polarizing (M3)")]:
            filter_combo.addItem(lbl, code)
        filter_combo.setCurrentIndex(1)  # default to D50 (M1)
        opts.append(_ChartreadOption(
            key="filter", flag="-F",
            label=tr("Spectral filter type (-F)"),
            tooltip_title=tr("Spectral Filter (-F)"),
            tooltip_body=(
                tr("Overrides the illuminant/filter condition used for measurement.\n\n"
                "Select the filter physically in use on your spectrophotometer:\n\n"
                "  n = None  (M0 — no filter, uncontrolled UV)\n"
                "  5 = D50   (M1 — controlled UV, ISO 13655 standard)\n"
                "  6 = D65   illuminant\n"
                "  u = UV Cut (M2 — UV excluded)\n"
                "  p = Polarizing filter (M3)\n\n"
                "The app defaults to D50 (M1), which matches the most common\n"
                "workflow for ICC print profiling with the i1Pro family.\n"
                "Change this only if your instrument has a different filter\n"
                "physically fitted. Wrong selection silently skews measured values.")
            ),
            widget=filter_combo,
        ))

        _tol_spin = _spinbox(0.1, 10.0, 0.1, 0.5, decimals=1)
        _tol_spin.setObjectName("")
        opts.append(_ChartreadOption(
            key="tolerance", flag="-T",
            label=tr("Patch consistency tolerance (-T)"),
            tooltip_title=tr("Patch Tolerance Multiplier (-T)"),
            tooltip_body=(
                tr("A multiplier on chartread's built-in patch consistency\n"
                "threshold — not a delta-E value. chartread re-reads each patch\n"
                "and rejects strips where the readings disagree by more than\n"
                "the threshold × this number.\n\n"
                "Lower = stricter. A strict setting catches real problems early:\n"
                "clogged inkjet nozzles, low ink, dirty drum rollers, drifting\n"
                "laser toner. On a healthy printer + spectrophotometer combo\n"
                "the default of 0.7 leaves comfortable headroom; experienced\n"
                "users on printerknowledge.com run 0.4 with i1 Pro 2 / 3.\n\n"
                "Raise to 0.8–1.5 if you get false \"inconsistent patch\" errors\n"
                "on textured, matte, or fine-art papers — the surface itself\n"
                "contributes real variance there. Values above 2 mostly mask\n"
                "genuine issues; if you need them, fix the printer first.")
            ),
            widget=_tol_spin,
        ))

        opts.append(_ChartreadOption(
            key="save_lab", flag="-l",
            label=tr("Save L*a*b* instead of XYZ (-l)"),
            tooltip_title=tr("Save L*a*b* Values (-l)"),
            tooltip_body=(
                tr("Saves measurement data as D50 L*a*b* instead of XYZ in the\n"
                "output .ti3 file.\n\n"
                "Standard ArgyllCMS tools (including colprof) work with XYZ.\n"
                "This option is almost never needed — enable it only if a\n"
                "downstream tool explicitly requires D50 L*a*b* input.")
            ),
        ))

        opts.append(_ChartreadOption(
            key="save_lab_and_xyz", flag="-L",
            label=tr("Save L*a*b* AND XYZ (-L)"),
            tooltip_title=tr("Save L*a*b* AND XYZ (-L)"),
            tooltip_body=(
                tr("Saves both D50 L*a*b* values and XYZ values in the output\n"
                ".ti3 file.\n\n"
                "Use this when you need the .ti3 to be compatible with tools\n"
                "that require L*a*b* while keeping the XYZ data that colprof\n"
                "and other ArgyllCMS tools expect.")
            ),
        ))

        # XRGA conversion combo
        xrga_combo = NoScrollComboBox(parent)
        xrga_combo.setFixedWidth(110)
        xrga_combo.setObjectName("compact_input")
        for code, lbl in [("N", "None"), ("A", "XRGA"), ("X", "XRDI"), ("G", "GMDI")]:
            xrga_combo.addItem(lbl, code)
        opts.append(_ChartreadOption(
            key="xrga", flag="-A",
            label=tr("XRGA instrument correction (-A)"),
            tooltip_title=tr("XRGA Correction (-A)"),
            tooltip_body=(
                tr("Applies a colorimetric correction to convert between\n"
                "spectrophotometer calibration standards.\n\n"
                "Different instrument generations use slightly different white\n"
                "references. XRGA standardisation corrects for these offsets:\n\n"
                "  N = No correction   (default — use for modern instruments)\n"
                "  A = XRGA   (X-Rite Global Reference Architecture)\n"
                "  X = XRDI   (older X-Rite reference)\n"
                "  G = GMDI   (GretagMacbeth reference)\n\n"
                "Only change this if you are combining measurements from\n"
                "instruments of different generations or manufacturers.")
            ),
            widget=xrga_combo,
        ))

        return opts

    def _make_manual_chartread_options(self, parent: QWidget) -> list[_ChartreadOption]:
        """Mirror of _make_chartread_options for the manual panel."""
        opts = []

        def _spinbox(lo, hi, step, default, decimals=0):
            if decimals > 0:
                sb = NoScrollDoubleSpinBox(parent)
                sb.setRange(lo, hi)
                sb.setSingleStep(step)
                sb.setDecimals(decimals)
                sb.setValue(default)
                sb.setFixedWidth(90)
            else:
                sb = NoScrollSpinBox(parent)
                sb.setRange(int(lo), int(hi))
                sb.setSingleStep(int(step))
                sb.setValue(int(default))
                sb.setFixedWidth(90)
            sb.setObjectName("compact_input")
            return sb

        opts.append(_ChartreadOption(
            key="highres", flag="-H",
            label=tr("High resolution spectral mode (-H)"),
            tooltip_title=tr("High Resolution Spectral Mode (-H)"),
            tooltip_body=(
                tr("Enables high-resolution spectral sampling on instruments that\n"
                "support it (i1Pro 2 and i1Pro 3).\n\n"
                "Standard mode samples the spectrum at 10 nm intervals.\n"
                "High-resolution mode uses 5 nm intervals, capturing finer\n"
                "spectral detail and improving colour accuracy for profiling,\n"
                "particularly on saturated or fluorescent colours.\n\n"
                "The measurement time increase is small (roughly 10–20% per\n"
                "strip). Leave this off unless you specifically need the\n"
                "extra spectral resolution.")
            ),
        ))

        filter_combo = NoScrollComboBox(parent)
        filter_combo.setFixedWidth(130)
        filter_combo.setObjectName("compact_input")
        for code, lbl in [("n", "None (M0)"), ("5", "D50 (M1)"), ("6", "D65"), ("u", "UV Cut (M2)"), ("p", "Polarizing (M3)")]:
            filter_combo.addItem(lbl, code)
        filter_combo.setCurrentIndex(1)
        opts.append(_ChartreadOption(
            key="filter", flag="-F",
            label=tr("Spectral filter type (-F)"),
            tooltip_title=tr("Spectral Filter (-F)"),
            tooltip_body=(
                tr("Overrides the illuminant/filter condition used for measurement.\n\n"
                "Select the filter physically in use on your spectrophotometer:\n\n"
                "  n = None  (M0 — no filter, uncontrolled UV)\n"
                "  5 = D50   (M1 — controlled UV, ISO 13655 standard)\n"
                "  6 = D65   illuminant\n"
                "  u = UV Cut (M2 — UV excluded)\n"
                "  p = Polarizing filter (M3)\n\n"
                "The app defaults to D50 (M1), which matches the most common\n"
                "workflow for ICC print profiling with the i1Pro family.\n"
                "Change this only if your instrument has a different filter\n"
                "physically fitted. Wrong selection silently skews measured values.")
            ),
            widget=filter_combo,
        ))

        opts.append(_ChartreadOption(
            key="tolerance", flag="-T",
            label=tr("Patch consistency tolerance (-T)"),
            tooltip_title=tr("Patch Tolerance Multiplier (-T)"),
            tooltip_body=(
                tr("A multiplier on chartread's built-in patch consistency\n"
                "threshold — not a delta-E value. chartread re-reads each patch\n"
                "and rejects strips where the readings disagree by more than\n"
                "the threshold × this number.\n\n"
                "Lower = stricter. A strict setting catches real problems early:\n"
                "clogged inkjet nozzles, low ink, dirty drum rollers, drifting\n"
                "laser toner. On a healthy printer + spectrophotometer combo\n"
                "the default of 0.7 leaves comfortable headroom; experienced\n"
                "users on printerknowledge.com run 0.4 with i1 Pro 2 / 3.\n\n"
                "Raise to 0.8–1.5 if you get false \"inconsistent patch\" errors\n"
                "on textured, matte, or fine-art papers — the surface itself\n"
                "contributes real variance there. Values above 2 mostly mask\n"
                "genuine issues; if you need them, fix the printer first.")
            ),
            widget=_spinbox(0.1, 10.0, 0.1, 0.5, decimals=1),
        ))

        opts.append(_ChartreadOption(
            key="save_lab", flag="-l",
            label=tr("Save L*a*b* instead of XYZ (-l)"),
            tooltip_title=tr("Save L*a*b* Values (-l)"),
            tooltip_body=(
                tr("Saves measurement data as D50 L*a*b* instead of XYZ in the\n"
                "output .ti3 file.\n\n"
                "Standard ArgyllCMS tools (including colprof) work with XYZ.\n"
                "This option is almost never needed — enable it only if a\n"
                "downstream tool explicitly requires D50 L*a*b* input.")
            ),
        ))

        opts.append(_ChartreadOption(
            key="save_lab_and_xyz", flag="-L",
            label=tr("Save L*a*b* AND XYZ (-L)"),
            tooltip_title=tr("Save L*a*b* AND XYZ (-L)"),
            tooltip_body=(
                tr("Saves both D50 L*a*b* values and XYZ values in the output\n"
                ".ti3 file.\n\n"
                "Use this when you need the .ti3 to be compatible with tools\n"
                "that require L*a*b* while keeping the XYZ data that colprof\n"
                "and other ArgyllCMS tools expect.")
            ),
        ))

        opts.append(_ChartreadOption(
            key="no_spectral", flag="-n",
            tooltip_width=540,
            label=tr("Don't save spectral data (-n)"),
            tooltip_title=tr("Don't Save Spectral Data (-n)"),
            tooltip_body=(
                tr("What this does\n"
                "\n"
                "When you measure a chart, your instrument records two kinds of\n"
                "numbers for every patch:\n"
                "\n"
                "  •  The colour values (XYZ, or L*a*b*) — a small handful of\n"
                "     numbers that describe the colour your eye sees.\n"
                "\n"
                "  •  The full spectrum — how much light the patch reflects at\n"
                "     each wavelength, measured in roughly 10 nm steps across\n"
                "     the visible range. That is around 36 extra numbers for\n"
                "     every single patch.\n"
                "\n"
                "Tick this box to keep only the colour values and leave the\n"
                "spectrum out of the measurement (.ti3) file.\n"
                "\n"
                "Why you might want it\n"
                "\n"
                "The spectral numbers make the .ti3 file several times longer. If\n"
                "you ever open the file to check a reading by eye, all those extra\n"
                "columns make it hard to find what you are looking for. Switching\n"
                "this on gives you a short, tidy file with just the colour data —\n"
                "much easier to scan and review.\n"
                "\n"
                "Does it change my profile?\n"
                "\n"
                "No. Building the ICC profile only needs the XYZ colour values,\n"
                "and those are always kept. A profile made with this option on is\n"
                "identical to one made with it off.\n"
                "\n"
                "When to leave it OFF\n"
                "\n"
                "Keep the spectral data if you plan to:\n"
                "\n"
                "  •  use optical-brightener (FWA) compensation when building the\n"
                "     profile — that feature reads the spectrum to model the\n"
                "     brighteners in modern photo papers,\n"
                "\n"
                "  •  re-calculate your colours under a different illuminant\n"
                "     later on, or\n"
                "\n"
                "  •  hand the file to other tools that expect spectral data.\n"
                "\n"
                "If none of that applies — and for everyday printer profiling it\n"
                "usually doesn't — this option is perfectly safe to turn on. It is\n"
                "off by default, so the spectrum is always kept unless you ask for\n"
                "it to be dropped.")
            ),
        ))

        xrga_combo = NoScrollComboBox(parent)
        xrga_combo.setFixedWidth(110)
        xrga_combo.setObjectName("compact_input")
        for code, lbl in [("N", "None"), ("A", "XRGA"), ("X", "XRDI"), ("G", "GMDI")]:
            xrga_combo.addItem(lbl, code)
        opts.append(_ChartreadOption(
            key="xrga", flag="-A",
            label=tr("XRGA instrument correction (-A)"),
            tooltip_title=tr("XRGA Correction (-A)"),
            tooltip_body=(
                tr("Applies a colorimetric correction to convert between\n"
                "spectrophotometer calibration standards.\n\n"
                "Different instrument generations use slightly different white\n"
                "references. XRGA standardisation corrects for these offsets:\n\n"
                "  N = No correction   (default — use for modern instruments)\n"
                "  A = XRGA   (X-Rite Global Reference Architecture)\n"
                "  X = XRDI   (older X-Rite reference)\n"
                "  G = GMDI   (GretagMacbeth reference)\n\n"
                "Only change this if you are combining measurements from\n"
                "instruments of different generations or manufacturers.")
            ),
            widget=xrga_combo,
        ))

        return opts

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def ti1_path(self) -> Path | None:
        return self._ti1_path

    def set_ti1_path(self, path: Path) -> None:
        is_new_chart = path != self._ti1_path
        if is_new_chart:
            self._averaging_active = False   # new chart → fresh averaging session
        self._ti1_path = path
        self._ti1_lbl.setText(str(path))
        self._start_btn.setEnabled(True)
        self._try_load_tiffs(path)
        self._update_resume_availability()
        self._update_precond_availability()
        self._refresh_bidir_autodetect()
        # #134 / K1 (Knut): the overlay auto-offer is a MEASURE-tab feature, but
        # set_ti1_path is also driven cross-tab — the Print tab's ti2_loaded, the
        # Check tab's ti2_found, project open, session restore and Profile-run /
        # Run-type bar changes all call it. Only pop the offer when the Measure
        # tab is actually the one on screen, so it never appears over Create Chart
        # or Print Chart.
        if is_new_chart and self.isVisible():
            self._maybe_offer_existing_overlay()

    def _maybe_offer_existing_overlay(self) -> None:
        """#134: when a freshly-loaded chart already has a measurement, show a
        small dialog offering BOTH choices as checkboxes (Basti): see it as an
        overlay, and/or refine/resume it so a new read doesn't replace it — with
        a clear warning about replacement. The last choice is remembered."""
        if self._existing_ti3_for_chart() is None:
            return
        from PyQt6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                                     QLabel, QVBoxLayout)
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("This chart already has a measurement"))
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        intro = QLabel(tr(
            "A measurement (.ti3) already exists for this chart. Choose what "
            "you'd like to do — you can change either of these any time from the "
            "options panel:"), dlg)
        intro.setWordWrap(True)
        lay.addWidget(intro)

        # Tint the checkboxes with the Measure tab's green accent (the app fills
        # a checked indicator with the accent; per-tab code overrides :checked).
        _green_cb_css = (
            "QCheckBox::indicator:checked { background:%s; border-color:%s; }"
            "QCheckBox::indicator:hover { border-color:%s; }"
            % (_TAB_COLOR, _TAB_COLOR, _TAB_COLOR))
        # Info boxes under each choice — neutral boxed frame matching the
        # post-measurement / "calibration complete" dialogs (see
        # _on_calibration_done): gray surface, gray border, default text.
        # NB: object name is NOT "info" — the global stylesheet paints QLabel#info
        # magenta-on-dark (a different kind of callout). Use our own name so the
        # neutral frame fully wins, text colour included.
        from ui.theme import resolve_mode
        if resolve_mode(self._settings.get("appearance", "auto")) == "light":
            _info_bg, _info_bd, _info_fg = "#f7f4ef", "#d0ccc6", "#33312e"
        else:
            _info_bg, _info_bd, _info_fg = "#181818", "#2a2a2a", "#c8c8c8"
        _info_css = (
            "QLabel#overlay_note { background:%s; border:1px solid %s; color:%s; "
            "border-radius:6px; padding:8px 10px; }"
            % (_info_bg, _info_bd, _info_fg))

        show_cb = QCheckBox(tr("Show it as an overlay on the patches"), dlg)
        show_cb.setStyleSheet(_green_cb_css)
        show_cb.setChecked(bool(self._settings.get("overlay_prompt_show_overlay", True)))
        show_sub = QLabel(tr(
            "Each patch is split between the colour the chart EXPECTED and what "
            "your instrument actually MEASURED, with the far-off ones outlined "
            "— so you can see how the print turned out without measuring again."),
            dlg)
        show_sub.setWordWrap(True); show_sub.setObjectName("overlay_note")
        show_sub.setStyleSheet(_info_css)
        lay.addWidget(show_cb); lay.addWidget(show_sub)

        resume_cb = QCheckBox(
            tr("Refine / resume this measurement (keep the strips already "
               "measured)"), dlg)
        resume_cb.setStyleSheet(_green_cb_css)
        resume_cb.setChecked(bool(self._settings.get("overlay_prompt_resume", False)))
        resume_sub = QLabel(tr(
            "With this on, a new measurement re-uses the existing one — you only "
            "scan the strips you want to update or add, and everything already "
            "measured is kept."), dlg)
        resume_sub.setWordWrap(True); resume_sub.setObjectName("overlay_note")
        resume_sub.setStyleSheet(_info_css)
        lay.addWidget(resume_cb); lay.addWidget(resume_sub)

        warn = QLabel(tr(
            "⚠  If you leave “Refine / resume” unticked and start a new "
            "measurement, it will REPLACE this existing measurement. Tick it to "
            "keep your previous readings."), dlg)
        warn.setWordWrap(True)
        warn.setStyleSheet("color:#c8781e; font-weight:600;")
        lay.addWidget(warn)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel, dlg)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)

        from PyQt6.QtWidgets import QDialog as _QD
        if dlg.exec() != int(_QD.DialogCode.Accepted):
            return
        want_overlay = show_cb.isChecked()
        want_resume = resume_cb.isChecked()
        # Remember the choice for next time.
        self._settings.set("overlay_prompt_show_overlay", want_overlay)
        self._settings.set("overlay_prompt_resume", want_resume)
        # Apply: overlay toggle (paints, or explains + unticks if not placeable).
        self._sync_overlay_checkboxes(want_overlay)
        self._on_overlay_toggled(want_overlay)
        # Refine/resume: tick the (already-visible) resume box in both modes.
        for cb in (self._resume_cb, self._m_resume_cb):
            if cb is not None:
                cb.setChecked(want_resume)

    def set_chart_notice(self, text: "str | None") -> None:
        """Show guidance in the preview when there's no chart to measure for the
        selected Profile-run / Run-type (#130, Knut)."""
        self._preview.set_notice(text)

    def clear_chart_file(self) -> None:
        self._ti1_path = None
        self._averaging_active = False
        self._ti1_lbl.setText(tr("No file selected"))
        self._ti1_lbl.setStyleSheet("color: #909090; font-size: 11px;")
        self._start_btn.setEnabled(False)
        self._tiff_pages = []
        self._page_stripe_rects = []
        self._strips_per_page = []
        self._stripe_arrow_mode = "base"
        self._preview.clear()
        self._update_resume_availability()
        self._settings.set("session_ti1_path", "")
        self._refresh_bidir_autodetect()

    # ------------------------------------------------------------------
    # Auto bidirectional (-B) detection
    # ------------------------------------------------------------------

    def _refresh_bidir_autodetect(self) -> None:
        """Re-read the loaded chart's TARGET_INSTRUMENT and refresh -B state.

        Called whenever the chart file changes. Resolves the -B value the
        Auto toggle will apply, logs the decision, and updates both modes'
        (greyed) checkboxes so they show what will happen.
        """
        from ui.ti2_loader import (
            disable_bidir_for_instrument, force_bidir_for_instrument,
            instrument_label, is_randomized, is_spectroscan, read_target_instrument,
        )

        instr = None
        randomized = True
        if self._ti1_path is not None and self._ti1_path.exists():
            instr = read_target_instrument(self._ti1_path)
            randomized = is_randomized(self._ti1_path)
        self._detected_instrument    = instr
        self._detected_disable_bidir = disable_bidir_for_instrument(instr)
        self._detected_force_bidir   = force_bidir_for_instrument(instr)
        self._detected_randomized    = randomized

        if hasattr(self, "_log"):
            # Drop the previous instrument line so only the most recent
            # detection stays visible across repeated chart generation.
            self._clear_previous_instrument_log()
            if instr:
                label = instrument_label(instr)
                if is_spectroscan(instr):
                    # XY table — reads patches individually, so the
                    # bidirectional "reading direction" note does not apply.
                    msg = tr("Chart instrument: {label}.").format(label=label)
                else:
                    value = self._detected_bidir_value()
                    if value == "disable":
                        detail = tr("reading one direction only (-B)")
                    elif value == "force":
                        detail = tr("reading both directions (forced, -b)")
                    else:
                        detail = tr("using Argyll's default strip recognition")
                    msg = tr("Chart instrument: {label} → {detail}.").format(
                        label=label, detail=detail)
                self._log.appendPlainText(msg)
                self._instr_log_text = msg

        self._apply_bidir_auto_state("guided")
        self._apply_bidir_auto_state("manual")

    def _clear_previous_instrument_log(self) -> None:
        """Remove the last logged "Chart instrument:" line, if still present.

        Lets repeated chart generation replace the instrument/-B notice in
        place rather than stacking up identical lines in the output field.
        """
        if not self._instr_log_text or not hasattr(self, "_log"):
            return
        from PyQt6.QtGui import QTextCursor

        doc = self._log.document()
        found = doc.find(self._instr_log_text)
        if not found.isNull():
            # Remove the whole line plus exactly one adjacent block separator
            # (the trailing one if anything follows, else the leading one) so
            # no blank line is left behind wherever the line sits.
            block = found.block()
            keep = QTextCursor.MoveMode.KeepAnchor
            cursor = QTextCursor(doc)
            if block.next().isValid():
                cursor.setPosition(block.position())
                cursor.setPosition(block.next().position(), keep)
            elif block.previous().isValid():
                cursor.setPosition(block.position() - 1)
                cursor.setPosition(block.position() + len(block.text()), keep)
            else:
                cursor.setPosition(0)
                cursor.setPosition(len(block.text()), keep)
            cursor.removeSelectedText()
        self._instr_log_text = None

    # Strip-recognition combo entries: (userData, label). The userData maps to
    # a chartread flag — "default" = no flag, "disable" = -B, "force" = -b.

    def _make_bidir_row(self, parent: QWidget, layout, mode: str) -> None:
        """Build the 'Strip recognition' combo + Auto toggle for a mode.

        The combo offers Default / -B / -b as one mutually-exclusive choice.
        The Auto toggle (right) derives the value from the loaded chart's
        instrument and greys out (but still shows) the combo while on.
        """
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Strip recognition:"), parent))
        combo = NoScrollComboBox(parent)
        # Guided mode shows a full-size (non-compact) combo; Manual keeps the
        # compact styling that matches its other dense option rows.
        if mode == "manual":
            combo.setObjectName("compact_input")
            combo.setMinimumWidth(210)
        else:
            combo.setMinimumWidth(240)
        # tr() at build time, not import time — tabs are imported before
        # set_language() runs, so a class-level constant would stay English.
        for data, label in (
            ("default", tr("Argyll default")),
            ("disable", tr("Bidirectional disabled (-B)")),
            ("force",   tr("Bidirectional forced (-b)")),
        ):
            combo.addItem(label, data)
        row.addWidget(combo)
        row.addSpacing(12)
        row.addWidget(TooltipButton(
            tr("Strip recognition"),
            tr("When you measure a chart you slide the instrument along each row\n"
            "of colour patches — that row is called a \"strip\". You can slide\n"
            "it either way: left-to-right or right-to-left. This setting tells\n"
            "the measuring tool which sliding directions to accept.\n\n"
            "Why it matters: if the tool expects one direction but you slide\n"
            "the other way, it can't tell which patch is which, so it rejects\n"
            "the read and makes you scan the strip again. The right setting\n"
            "here lets a strip be accepted however you happen to slide it.\n\n"
            "The three choices:\n\n"
            "  • Argyll default\n"
            "      Don't force anything — hand the decision to ArgyllCMS's own\n"
            "      built-in rule. That rule looks only at how the chart was\n"
            "      printed: if the patches are in a shuffled (randomised) order\n"
            "      it accepts both directions, and if they are in plain order it\n"
            "      accepts one direction only. This is a fixed rule inside the\n"
            "      tool — it is NOT the same as ChromIQ's \"Auto\" (see the note\n"
            "      at the end).\n\n"
            "  • Bidirectional disabled\n"
            "      Always accept one direction only. Choose this if your\n"
            "      instrument can read one way only — the ColorMunki (and the\n"
            "      i1Studio / ColorChecker Studio, which are the same hardware)\n"
            "      work like this. It also helps if you keep getting false\n"
            "      \"wrong direction\" errors.\n\n"
            "  • Bidirectional forced\n"
            "      Always accept a strip slid either way, even on a plain-order\n"
            "      chart. Choose this for the i1 Pro family (i1 Pro / Pro 2 /\n"
            "      Pro 3), which reads both directions happily. It saves you\n"
            "      having to slide every strip the same way, and rescues charts\n"
            "      the tool would otherwise only read in one direction.\n\n"
            "\"Auto\" is not the same as \"Argyll default\":\n"
            "  • \"Argyll default\" is one of the three fixed choices above. It\n"
            "      simply forwards your chart to ArgyllCMS and lets the tool's\n"
            "      built-in rule decide.\n"
            "  • \"Auto\" (the switch next to this menu) is ChromIQ's helper. It\n"
            "      reads the instrument saved in your chart and picks whichever\n"
            "      of the three choices suits it — \"Bidirectional forced\" for an\n"
            "      i1 Pro, \"Argyll default\" for a ColorMunki and most others.\n"
            "      While Auto is on, the menu is locked and shows the choice it\n"
            "      made.\n\n"
            "Leave Auto on unless you specifically want to choose by hand."),
            parent,
            min_width=560,
        ))
        row.addStretch()
        auto_cb = QCheckBox(tr("Auto"), parent)
        auto_cb.setChecked(True)
        auto_cb.toggled.connect(lambda _checked, m=mode: self._apply_bidir_auto_state(m))
        row.addWidget(auto_cb)
        row.addSpacing(18)
        row.addWidget(TooltipButton(
            tr("Auto (recommended)"),
            tr("Lets ChromIQ choose the \"Strip recognition\" option for you, based\n"
            "on the measuring instrument saved in the chart you loaded:\n\n"
            "  • i1 Pro / i1 Pro 2 / i1 Pro 3 — reads strips in both\n"
            "      directions, so Auto chooses \"Bidirectional forced\".\n"
            "  • ColorMunki / i1Studio / ColorChecker Studio — Argyll's\n"
            "      default already reads these correctly, so Auto chooses\n"
            "      \"Argyll default\".\n"
            "  • Any other or unknown instrument — uses \"Argyll default\".\n\n"
            "While Auto is on, the menu on the left is locked and simply shows\n"
            "the option Auto has chosen, so you can always see what will be\n"
            "used. Switch Auto off to pick the option yourself.\n\n"
            "Auto is the recommended setting — most people never need to\n"
            "change it."),
            parent,
            min_width=520,
        ))
        layout.addLayout(row)
        if mode == "guided":
            self._bidir_combo, self._bidir_auto_cb = combo, auto_cb
        else:
            self._m_bidir_combo, self._m_bidir_auto_cb = combo, auto_cb

    def _bidir_widgets(self, mode: str):
        """(auto checkbox, strip-recognition combo) for the given mode."""
        if mode == "guided":
            return self._bidir_auto_cb, self._bidir_combo
        return self._m_bidir_auto_cb, self._m_bidir_combo

    @staticmethod
    def _coerce_bidir_mode(mode, legacy_disable: bool, legacy_force: bool,
                           fallback: str = "default") -> str:
        """Resolve a stored strip-recognition value, migrating the old scheme.

        Pre-combo presets/settings stored two booleans (disable -B / force -b);
        this maps them to the new combo value. `fallback` is used when neither
        the new key nor a legacy flag is present.
        """
        if mode in ("default", "disable", "force"):
            return mode
        if legacy_disable:
            return "disable"
        if legacy_force:
            return "force"
        return fallback

    def _detected_bidir_value(self) -> str:
        """The combo value the Auto toggle resolves for the loaded chart."""
        if self._detected_disable_bidir:
            return "disable"
        if self._detected_force_bidir:
            return "force"
        return "default"

    def _set_bidir_value(self, combo: "QComboBox", value: str) -> None:
        """Select the combo entry for a strip-recognition value, without firing
        signals (falls back to the first entry if the value is unknown)."""
        idx = combo.findData(value)
        combo.blockSignals(True)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _apply_bidir_auto_state(self, mode: str) -> None:
        """Grey out and sync a mode's strip-recognition combo per its Auto toggle.

        While Auto is on the combo is disabled and shows the detected value
        (so the locked menu reflects the effective setting); its own selection
        is ignored when the command is built (see _resolve_bidir_value).
        """
        auto_cb, combo = self._bidir_widgets(mode)
        auto_on = auto_cb.isChecked()
        combo.setEnabled(not auto_on)
        if auto_on:
            self._set_bidir_value(combo, self._detected_bidir_value())

    def _resolve_bidir_value(self, mode: str) -> str:
        """The strip-recognition value to apply: auto-detected when Auto is on,
        else the user's combo selection (its saved preset/default)."""
        auto_cb, combo = self._bidir_widgets(mode)
        if auto_cb.isChecked():
            return self._detected_bidir_value()
        return combo.currentData() or "default"

    def _resolve_disable_bidir(self, mode: str) -> bool:
        return self._resolve_bidir_value(mode) == "disable"

    def _resolve_force_bidir(self, mode: str) -> bool:
        return self._resolve_bidir_value(mode) == "force"

    def _effective_bidirectional(self, params: "MeasureParams") -> bool:
        """Whether the read will *effectively* be bidirectional.

        Drives the preview's double (bottom) strip arrow so it mirrors what
        chartread actually does:
          • "force" (-b)   → always bidirectional, any chart
          • "disable" (-B) → never bidirectional
          • Argyll default → bidirectional only on a randomised chart (chartread
            reads both directions there, one direction on a fixed-order chart)
        """
        return params.force_bidir or (
            not params.disable_bidir and self._detected_randomized
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_load_ti2(self) -> None:
        from ui.ti2_loader import resolve_ti2
        path = open_file_dialog(
            self, tr("Load .ti2 file"), tr("TI2 files (*.ti2)"),
            extra_path=self._settings.get("custom_output_path", ""),
            declutter_settings=self._settings,
        )
        if not path:
            return
        result = resolve_ti2(self, Path(path), self._settings,
                             getattr(self, "_target_ctl", None))
        if result is None:
            return
        ti2_path, tiffs = result   # TIFFs re-discovered by set_ti1_path → _try_load_tiffs
        if ti2_path != self._ti1_path:
            self.ti2_replaced.emit()
        self.set_ti1_path(ti2_path)
        self.ti2_loaded.emit(ti2_path)
        # Mirror this explicit load into the Create Chart tab (reflect-only).
        self.chart_load_requested.emit(ti2_path, list(tiffs or []))

    def _update_resume_availability(self) -> None:
        if self._ti1_path is None:
            for cb, tip, rcb in [
                (self._resume_cb,   self._resume_tip,   self._refine_cb),
                (self._m_resume_cb, self._m_resume_tip, self._m_refine_cb),
            ]:
                cb.setVisible(False)
                tip.setVisible(False)
                cb.setChecked(False)
                rcb.setEnabled(False)
                rcb.setChecked(False)
            for ocb, otip in [(self._overlay_cb, self._overlay_tip),
                              (self._m_overlay_cb, self._m_overlay_tip)]:
                ocb.setVisible(False); otip.setVisible(False)
                ocb.setChecked(False)      # #134: no chart → no overlay
            self._refine_strips_path = None
            self._strip_list = []
            return
        ti3 = self._ti1_path.with_suffix(".ti3")
        has_ti3 = ti3.exists()
        for cb, tip in [
            (self._resume_cb,   self._resume_tip),
            (self._m_resume_cb, self._m_resume_tip),
        ]:
            cb.setVisible(has_ti3)
            tip.setVisible(has_ti3)
            if not has_ti3:
                cb.setChecked(False)
        # #134: the "Show overlay from existing measurement" toggle appears only
        # when a matching .ti3 is present; hide + untick it otherwise.
        for ocb, otip in [(self._overlay_cb, self._overlay_tip),
                          (self._m_overlay_cb, self._m_overlay_tip)]:
            ocb.setVisible(has_ti3); otip.setVisible(has_ti3)
            if not has_ti3:
                ocb.setChecked(False)
        # Auto-detect Refine_Strips file — reports/ since #127, with a
        # fallback to the flat pre-v2 location (an external chart folder that
        # never went through project migration may still hold one there).
        from core.file_manager import reports_subdir
        _name = f"Refine_Strips_{self._ti1_path.stem}.txt"
        refine_file = reports_subdir(self._ti1_path.parent) / _name
        if not refine_file.exists():
            refine_file = self._ti1_path.parent / _name
        if refine_file.exists():
            self._refine_strips_path = refine_file
            self._load_refine_strips(refine_file)
            for rcb in (self._refine_cb, self._m_refine_cb):
                rcb.setEnabled(True)
                rcb.setChecked(True)
        else:
            self._refine_strips_path = None
            self._strip_list = []
            for rcb in (self._refine_cb, self._m_refine_cb):
                rcb.setEnabled(False)
                rcb.setChecked(False)
        self._refresh_start_button_label()

    def _update_precond_availability(self) -> None:
        """Show the 'also use pre-conditioning data' option when ChromIQ-style
        refinement is enabled and this run carries a preconditioning.ti3 seed."""
        found: Path | None = None
        if (
            self._ti1_path is not None
            and bool(self._settings.get("chromiq_refinement", False))
        ):
            run = Run.for_dir(self._ti1_path.parent)
            if run.preconditioning_ti3.exists():
                found = run.preconditioning_ti3
        self._precond_ti3 = found
        visible = found is not None
        for cb, tip in [
            (self._use_precond_cb, self._precond_tip),
            (self._m_use_precond_cb, self._m_precond_tip),
        ]:
            cb.setVisible(visible)
            tip.setVisible(visible)
            if not visible:
                cb.setChecked(False)

    def preconditioning_choice(self) -> Path | None:
        """The preconditioning.ti3 the user opted into merging, or None.

        Returns the discovered file only when its checkbox is visible AND ticked
        in the active mode — the main window forwards this to Build Profile.
        """
        if self._precond_ti3 is None:
            return None
        cb = self._use_precond_cb if self._current_mode() == "guided" else self._m_use_precond_cb
        # isHidden() reflects the explicit show/hide state set in
        # _update_precond_availability, independent of which tab is front-most.
        if not cb.isHidden() and cb.isChecked():
            return self._precond_ti3
        return None

    def _refresh_start_button_label(self) -> None:
        """Show 'Continue Measurement' on the Start button when the resume
        checkbox for the active mode is ticked (i.e. the next run will pass
        chartread's -r flag)."""
        cb = self._resume_cb if self._current_mode() == "guided" else self._m_resume_cb
        if cb.isVisible() and cb.isChecked():
            self._start_btn.setText(tr("Continue Measurement"))
        else:
            self._start_btn.setText(tr("Start Measurement"))

    def _load_refine_strips(self, path: Path) -> None:
        from workflow.profcheck_runner import parse_refine_strips
        try:
            self._strip_list = parse_refine_strips(path)
        except Exception:
            self._strip_list = []

    def start_guided_refinement(self, ti3: Path, strips_file: Path) -> None:
        """Called by main window when user launches guided refinement from Check & Refine tab."""
        ti2 = ti3.with_suffix(".ti2")
        if ti2.exists():
            self.set_ti1_path(ti2)
        self._resume_cb.setChecked(True)
        self._refine_strips_path = strips_file
        self._load_refine_strips(strips_file)
        self._refine_cb.setEnabled(True)
        self._refine_cb.setChecked(True)

    def _try_load_tiffs(self, base_path: Path) -> None:
        stem   = base_path.with_suffix("").stem
        folder = base_path.parent
        tiffs  = sorted(folder.glob(f"{stem}*.tif"))
        if tiffs:
            self._tiff_pages = tiffs
            self._preview.load_tiff(tiffs)
            self._setup_stripe_rects()
        else:
            self._tiff_pages = []
            self._page_stripe_rects = []
            self._strips_per_page = []
            self._preview.clear()
            self._log.appendPlainText(
                "[WARNING] No matching TIFF preview found. "
                "Ensure you scan the correct target."
            )
            self._log.ensureCursorVisible()

    def _setup_stripe_rects(self) -> None:
        """Detect per-page strip positions and resolve per-page strip counts.

        Strip counts come from the chart's .ti2 (``PASSES_IN_STRIPS2``) — the
        authoritative source — so the highlighter maps the right strip to the
        right page even when the last page is partly empty (e.g. a 24,23 chart).
        Rects are detected per page so the arrow lands correctly on every page,
        not just page 1.

        Falls back to the legacy single-page label detector when the .ti2 is
        unavailable or its page count doesn't line up with the loaded TIFFs.
        """
        self._page_stripe_rects = []
        self._strips_per_page = []
        self._stripe_arrow_mode = "base"
        if not self._tiff_pages:
            return

        # ChromIQ layout engine (issue #93): if the chart carries exact strip
        # geometry in its channels.json, use it directly — guess-free, no image
        # detection. This is the solid path for engine-generated charts.
        # Per-patch boxes for the split-patch overlay (#126) — independent of
        # how strip rects are found below.
        self._patch_boxes = patch_boxes_from_sidecar(
            self._ti1_path, len(self._tiff_pages))
        # Hand the preview the exact per-patch boxes so the click-to-jump hover
        # outline can hug just a strip's patches, on every page (Basti, #126).
        self._preview.set_page_patch_boxes({
            pg: list(d.values()) for pg, d in enumerate(self._patch_boxes)})
        # Grow the strip-hover frame over the edge spacers, when the chart's own
        # geometry says it has them (#43).
        self._preview.set_edge_spacer_px(edge_spacer_px_from_sidecar(self._ti1_path))
        # SpectroScan hexagonal charts: the strip highlight follows the column's
        # zigzag (staggered hexagons) instead of a straight rect that would spill
        # into the neighbouring column, and the swipe arrow is hidden — an XY
        # table reads patch-by-patch, so there's nothing to swipe (Knut/Basti).
        from workflow.hex_support import chart_is_hexagonal
        self._preview.set_hex_zigzag(chart_is_hexagonal(self._ti1_path))

        engine = self._engine_stripe_rects()
        if engine is not None:
            per_page, counts, arrow_mode = engine
            self._page_stripe_rects = per_page
            self._strips_per_page = counts
            self._stripe_arrow_mode = arrow_mode
            self._preview.set_stripe_rects(per_page[0], arrow_mode)
            return

        # PASSES_IN_STRIPS2 lives only in the .ti2, but _ti1_path can hold either
        # a .ti2 (most load paths) or a real .ti1 (reopening a saved run passes
        # run.chart_ti1). Resolve the sibling .ti2 so the authoritative uniform
        # detector runs in both cases instead of falling back to the fragile
        # label-counter, which miscounts charts whose rotated caption sits in the
        # page margin. Unchanged when _ti1_path is already a .ti2, or when no
        # sibling .ti2 exists (then parse returns [] and we fall back as before).
        ti2_for_counts = self._ti1_path
        if ti2_for_counts is not None and ti2_for_counts.suffix.lower() != ".ti2":
            sibling = ti2_for_counts.with_suffix(".ti2")
            if sibling.is_file():
                ti2_for_counts = sibling
        counts = parse_passes_per_page(ti2_for_counts) if ti2_for_counts else []
        if counts and len(counts) == len(self._tiff_pages):
            per_page: list[list[QRect]] = []
            for page_path, n in zip(self._tiff_pages, counts):
                rects = _detect_uniform_stripe_rects(page_path, n)
                if not rects:
                    per_page = []
                    break
                per_page.append(rects)
            if per_page:
                self._page_stripe_rects = per_page
                self._strips_per_page = counts
                self._preview.set_stripe_rects(per_page[0])
                return

        # Fallback: legacy label-based detection on page 1 only. Page mapping
        # in _on_stripe_changed then assumes uniform pages (len(rects)/page).
        rects = _detect_stripe_rects(self._tiff_pages[0])
        if rects:
            self._page_stripe_rects = [rects]
            self._preview.set_stripe_rects(rects)

    def _engine_stripe_rects(self):
        """Exact per-page strip rects from a ChromIQ-engine chart's channels.json,
        or None if this isn't an engine chart / the geometry doesn't line up."""
        if self._ti1_path is None:
            return None
        return engine_strip_rects_from_sidecar(
            self._ti1_path.with_suffix(".channels.json"), len(self._tiff_pages))

    def _set_settings_enabled(self, enabled: bool) -> None:
        # Lock the measurement PARAMETERS during a read, but NOT the scroll areas
        # (so the panel stays scrollable, #42) nor the "Live preview" view group
        # (its controls only change the preview, so they stay usable, #41).
        # Disabling the scrolls' inner content greys the options exactly as
        # before, while the scroll widgets themselves remain interactive.
        for w in (getattr(self, "_g_options", None), getattr(self, "_m_options", None),
                  getattr(self, "_m_presets_grp", None)):
            if w is not None:
                w.setEnabled(enabled)
        self._file_grp.setEnabled(enabled)
        self._save_defaults_btn.setEnabled(enabled)
        # Keep the chart path/name tooltip from popping up over the chart while a
        # read runs — it gets in the way of swiping and the patch hover tile.
        self._preview.set_suppress_file_tooltip(not enabled)

    def _on_sound_toggled(self, on: bool) -> None:
        """Master switch for measurement sounds (#131): persist it so it's
        remembered, and pre-load the selected sounds when turning it on so the
        first play during a measurement isn't delayed by a disk read."""
        self._settings.set("sound_enabled", on)
        if on and getattr(self, "_sound", None) is not None:
            self._sound.arm()
            self._sound.disarm()      # preload only; not in a measurement yet

    def _pace_config(self):
        """Build the pace thresholds for the instrument this chart was laid out
        for (#131 Phase 2). The sampling rate is only used when it has been set
        for that instrument — otherwise the pace is judged in time per patch and
        no sample count is claimed."""
        from core.measure_pace import PaceConfig, defaults_for, model_key
        # The model the instrument REPORTED when it was opened, which Argyll
        # distinguishes down to the i1Pro generation. Falls back to the chart's
        # instrument family, and finally to the slowest i1Pro rate — never to a
        # faster one, which would let a too-quick swipe pass unremarked (Knut).
        key = model_key(getattr(self, "_detected_instrument", None))
        if key is None:
            from ui.ti2_loader import read_target_instrument
            try:
                if self._ti1_path is not None:
                    key = model_key(read_target_instrument(self._ti1_path))
            except Exception:      # noqa: BLE001
                key = None
        hz_default, min_default = defaults_for(key)
        lookup = key or "i1pro"
        try:
            hz = float(self._settings.get(f"pace_sample_hz_{lookup}", hz_default)
                       or hz_default)
        except (TypeError, ValueError):
            hz = hz_default
        stored_min = self._settings.get(f"pace_min_samples_{lookup}", None)
        if stored_min is None:
            stored_min = 0 if min_default is None else min_default
        try:
            min_samples = int(stored_min or 0)
        except (TypeError, ValueError):
            min_samples = min_default or 0
        # 0 = off for this instrument: a rate of 0 makes samples_for() return
        # None and target_seconds fall back to a threshold nothing can trip.
        if min_samples <= 0:
            return PaceConfig(min_samples=0, sample_hz=0.0,
                              min_patch_seconds=0.0)
        return PaceConfig(min_samples=min_samples, sample_hz=hz,
                          min_patch_seconds=0.0)

    def _pace_tracker(self):
        """The tracker for this measurement, created on first use."""
        from core.measure_pace import PaceTracker
        t = getattr(self, "_pace", None)
        if t is None:
            t = self._pace = PaceTracker(self._pace_config())
        else:
            # Rebuilt from the settings every time, so changing a threshold in
            # Preferences → Measurement takes effect on the very next strip
            # rather than at the next restart (Knut, #131 2026-07-26).
            t.config = self._pace_config()
        return t

    def _on_instrument_detected(self, model: str) -> None:
        """Remember the model the instrument reported when it was opened (#131).
        A chart records only the family it was laid out for, so this is the only
        place the actual generation — i1Pro vs i1Pro 2 vs i1Pro 3 — is known."""
        self._detected_instrument = model or ""
        self._pace = None            # rebuild the tracker with that model's rate
        if model:
            log.info("measurement: instrument reported as %s", model)

    def _on_patch_sound(self, payload: dict) -> None:
        """Per-patch sound (#131): a normal tick, or the 'looks off' sound when
        the just-read patch is far from its expected colour (ΔE over the patch-
        read warning limit — the same limit that red-outlines it in the live
        preview). ΔE is only present with the ChromIQ reading engine."""
        import core.sound as _snd
        de = payload.get("de")
        try:
            warn = float(self._settings.get("patch_read_warn_de", 50.0))
        except (TypeError, ValueError):
            warn = 50.0
        if de is not None and de > warn:
            self._sound.play(_snd.PATCH_OUT_OF_TOL)
        else:
            self._sound.play(_snd.PATCH_OK)

    def _report_failed_strip_pace(self, reason: str) -> None:
        """When a strip FAILS, say how fast it was read and whether speed was
        the likely cause (#131, Knut 2026-07-26).

        Knut asked for the timing to appear for every strip, "even if OK or
        failed" — so a failed strip is listed with its scan time like any
        other. Whether speed is *blamed* depends on Argyll's own wording: a
        hurried scan and a hesitant one fail with different messages, and the
        advice has to match.

        A failed scan returns no patches, so the count comes from a strip that
        did succeed — every strip of a chart holds the same number. Without one,
        the time is still shown but no per-patch figure is claimed.
        """
        if not self._settings.get("pace_hint_enabled", True):
            return
        try:
            import time
            from core.measure_pace import failure_advice, failure_kind
            started = getattr(self, "_scan_started_at", None)
            patches = getattr(self, "_last_strip_patches", 0)
            self._scan_started_at = None
            if not started:
                return
            elapsed = time.monotonic() - started
            tracker = self._pace_tracker()          # config re-read from settings
            kind = failure_kind(reason)

            pace = tracker.strip_timed(elapsed, patches) if patches else None
            if kind == "too_fast":
                headline = tr("Too fast — that is probably why the strip failed")
                colour = "#ff6b6b"
            elif kind == "too_slow":
                headline = tr("Uneven swipe — too many patches were found")
                colour = "#e0a63a"
            else:
                headline = tr("Strip failed — this does not look like speed")
                colour = "#e0a63a"
            # The failed strip is listed with its time like any other (Knut:
            # "even if OK or failed"), marked so it reads as a failure.
            letter = getattr(self, "_current_strip_letter", "") or "?"
            self._pace_times[letter] = (elapsed, False)
            self._refresh_pace_panel(headline, colour)

            note = failure_advice(reason, tracker.config)
            if pace is not None and pace.mean_seconds > 0:
                note = tr("That strip took {secs} s — about {ms} ms per patch. "
                          ).format(secs=f"{elapsed:.1f}",
                                   ms=int(pace.mean_seconds * 1000)) + note
            self._log.appendPlainText("\n" + note)
            self._log.ensureCursorVisible()
        except Exception:      # noqa: BLE001 — a hint must never break a read
            log.warning("failed-strip pace hint failed", exc_info=True)

    def _prompt_too_fast_strip(self, strip: str, pace, config) -> None:
        """A strip ArgyllCMS accepted, but read faster than the minimum set for
        this instrument (#131, Knut 2026-07-26).

        Argyll only refuses a strip once it is unusable; between "fine" and
        "refused" lies a band where the readings are accepted but thin — fewer
        readings per patch means more noise in every patch, and that noise ends
        up in the profile. Argyll never mentions it, so ChromIQ asks: read the
        strip again, or keep it.

        Only offered with the ChromIQ engine, because going back to a strip
        Argyll has already accepted needs the engine's own "go to strip".
        """
        from PyQt6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                                     QPushButton, QVBoxLayout)
        if not self._manager.engine_active or not strip:
            return
        if getattr(self, "_suppress_fast_prompt", False):
            # Asked for by the user for the rest of this measurement (Knut,
            # #131 2026-07-26). The "slow down" sound has already played, and
            # the panel under the preview still shows the verdict — only the
            # window is held back.
            return
        ms = int(pace.mean_seconds * 1000)
        target_ms = int(config.target_seconds * 1000)
        good_secs = (target_ms * pace.patches) / 1000.0

        QApplication.instance().removeEventFilter(self)
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Strip Read Quickly"))
        dlg.setMinimumWidth(560)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        detail = tr(
            "<b>Strip {name} was accepted, but it was read quickly.</b><br><br>"
            "It took {secs} s for {n} patches — about <b>{ms} ms</b> on each "
            "patch, where this instrument is set to want at least "
            "<b>{target} ms</b>. Reading the whole strip in about "
            "<b>{good} s</b> would sit comfortably above that."
        ).format(name=strip, secs=f"{pace.elapsed:.1f}", n=pace.patches, ms=ms,
                 target=target_ms, good=f"{good_secs:.0f}")
        if pace.est_samples is not None:
            detail += "<br><br>" + tr(
                "At this speed each patch received roughly <b>{n} readings</b> "
                "instead of the {want} asked for."
            ).format(n=pace.est_samples, want=config.min_samples)
        detail += "<br><br>" + tr(
            "<b>Why it matters:</b> the instrument averages the readings it "
            "takes while passing over a patch. Fewer readings mean a noisier "
            "measurement, and that noise is carried into the profile you build "
            "from it. ArgyllCMS only refuses a strip once it is unusable, so a "
            "strip can pass and still be thinner than you want."
        ) + "<br><br>" + tr(
            "The limits come from Preferences → Measurement, and the defaults "
            "are set to give good-quality readings. If you would rather trade "
            "some quality for speed, lower the minimum readings per patch "
            "there and this warning will follow your setting."
        ) + "<br><br>" + tr(
            "&nbsp;&nbsp;<b>Re-read Strip</b> — read strip {name} again, more "
            "slowly. The new reading replaces this one.<br>"
            "&nbsp;&nbsp;<b>Continue Anyway</b> — keep what was just read and "
            "carry on to the next strip."
        ).format(name=strip)

        msg = QLabel(detail, dlg)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        quiet = QCheckBox(
            tr("Do not show this message for the rest of the measurement "
               "session"), dlg)
        quiet.setToolTip(tr(
            "Keeps the reading-speed window out of your way while you finish "
            "this chart. The slow-down sound still plays, and the reading times "
            "and verdict under the chart still update, so you can see the pace "
            "without being interrupted. It comes back for your next "
            "measurement."))
        layout.addWidget(quiet)

        chosen = ["continue"]
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        again = QPushButton(tr("Re-read Strip"), dlg)
        again.setObjectName("primary")
        again.setFixedHeight(32)
        again.clicked.connect(lambda: (chosen.__setitem__(0, "reread"),
                                       dlg.accept()))
        keep = QPushButton(tr("Continue Anyway"), dlg)
        keep.setFixedHeight(32)
        keep.clicked.connect(lambda: (chosen.__setitem__(0, "continue"),
                                      dlg.accept()))
        row.addWidget(keep)
        row.addWidget(again)
        layout.addLayout(row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        # While this is open, a modal dialog runs a nested event loop, so the
        # engine's "all strips read" arrives and would open its window on top of
        # this one — two windows and two sounds at once on the last strip (Knut,
        # #131 2026-07-26). Held back here and released below.
        self._pace_prompt_open = True
        try:
            dlg.exec()
        finally:
            self._pace_prompt_open = False
        if quiet.isChecked():
            self._suppress_fast_prompt = True
            self._log.appendPlainText(
                "\n" + tr("The reading-speed window will stay out of the way "
                          "for the rest of this measurement. The slow-down "
                          "sound and the times under the chart still appear."))
            self._log.ensureCursorVisible()
        QApplication.instance().installEventFilter(self)

        if chosen[0] == "reread":
            # Back to measuring: the chart is no longer finished, so the
            # "All Stripes Read" window must not appear — whether it arrived
            # while this window was open or arrives just after it closes
            # (Knut, #131 2026-07-27).
            self._all_done_deferred = False
            self._skip_next_all_done = True
            self._manager.goto_strip(strip)     # the next swipe overwrites it
            self._log.appendPlainText(
                "\n" + tr("Re-reading strip {name} — take it more slowly this "
                          "time.").format(name=strip))
            self._log.ensureCursorVisible()
        elif getattr(self, "_all_done_deferred", False):
            # "Continue Anyway" on the last strip: now show the window that was
            # held back, alone and after this one.
            self._all_done_deferred = False
            self._on_all_stripes_done()

    def _on_strip_error_sound(self, reason: str) -> None:
        """Strip-failure sound (#131): Argyll's own 'Slow Down!' comes through
        here after a too-fast swipe — play the calmer 'slow down' cue for that,
        and the plain 'strip failed' sound otherwise."""
        import core.sound as _snd
        from core.measure_pace import failure_kind
        # Knut (#131): the cue must match the fault. Argyll's own wording is
        # classified — only a genuinely hurried scan gets the "slow down" cue,
        # because telling someone to slow down when they hesitated (too many
        # patches) or drifted off the strip sends them the wrong way.
        if failure_kind(reason) == "too_fast":
            self._sound.play(_snd.SLOW_DOWN)
        else:
            self._sound.play(_snd.STRIP_FAIL)

    def _profiling_overwrite_choice(self, run) -> str:
        """Ask before a measurement replaces the chart stored with a profile
        run (#130, Knut 2026-07-27). ``"go"`` / ``"keep"`` / ``"cancel"``.

        ``keep`` is Knut's third option: measure, but leave the stored copy
        alone — for trying a changed chart out without losing the copy that
        describes the run's existing measurement. It is recorded on the run,
        because the copy then no longer describes what the run holds, and that
        must never be silent.
        """
        from workflow.chart_slot import slot_for
        from workflow.verify_chart_snapshot import (slot_has_snapshot,
                                                    slot_live_differs)
        slot = slot_for(run)
        if not slot_has_snapshot(slot) or not slot_live_differs(slot):
            return "go"

        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("This profile run was measured with another chart"))
        box.setText(tr("Measuring here replaces the chart stored with this "
                       "profile run."))
        extra = ""
        try:
            if Run.for_dir(run.dir).reads():
                extra = "\n\n" + tr(
                    "You have already measured this run and are averaging the "
                    "results. Replacing the chart now means the earlier reads "
                    "and this one were made from different sheets, and "
                    "averaging them together would mix two different charts. "
                    "Cancel if you did not intend that.")
        except Exception:      # noqa: BLE001
            pass
        box.setInformativeText(tr(
            "{run} was measured with a different chart from the one loaded "
            "now. That run keeps its own copy of the chart it was measured "
            "with — the copy “Restore Used Chart” puts back. If you measure "
            "the chart you have loaded into this same run, that stored copy is "
            "replaced, and the measurement already sitting there would no "
            "longer describe a chart you still have.\n\n"
            "If you meant to build a separate profile, set “Profile run” to "
            "“New run” and start the measurement again — this run then stays "
            "exactly as it is, with its own chart, and today's reading starts "
            "a run of its own."
        ).format(run=self._pretty_run_name(run)) + extra)
        replace = box.addButton(tr("Replace the stored chart"),
                                QMessageBox.ButtonRole.DestructiveRole)
        keep = box.addButton(tr("Measure without changing the stored chart"),
                             QMessageBox.ButtonRole.ActionRole)
        keep.setToolTip(tr(
            "For trying something out. The stored copy stays as it is, so it "
            "will no longer describe the measurement this run ends up with — "
            "ChromIQ remembers that and says so."))
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is replace:
            return "go"
        if clicked is keep:
            return "keep"
        return "cancel"

    @staticmethod
    def _pretty_run_name(run) -> str:
        rid = getattr(run, "id", "") or ""
        n = rid[3:] if rid.startswith("run") else rid
        return tr("Run {n}").format(n=n) if n else tr("This run")

    def _chart_overwrite_choice(self, verification) -> str:
        """Ask before replacing the chart a verification date was measured with
        (#130, Knut 2026-07-26). Returns ``"go"`` or ``"cancel"``.

        The comparison is the same one behind **Restore Used Chart**: content
        digests of the stored chart against the live one. A date with no stored
        chart, or one whose stored chart *is* what is loaded, goes ahead without
        a word — re-measuring the same chart is the ordinary case and must not
        be interrupted.
        """
        from workflow.verify_chart_snapshot import (has_snapshot,
                                                    live_differs_from_snapshot)
        if not has_snapshot(verification):
            return "go"
        if not live_differs_from_snapshot(verification):
            return "go"          # same chart — nothing would be lost

        from PyQt6.QtWidgets import QMessageBox
        from core.measurement_target import chart_overwrite_message
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("This verification was measured with another chart"))
        box.setText(tr("Measuring here replaces the chart stored with that "
                       "verification date."))
        box.setInformativeText(chart_overwrite_message(verification.id))
        over_btn = box.addButton(tr("Replace the stored chart"),
                                 QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        # Cancel is the default: the route the message recommends — switching
        # the Verification field to "New verification" — starts by stopping here.
        box.setDefaultButton(cancel_btn)
        box.exec()
        return "go" if box.clickedButton() is over_btn else "cancel"

    def _snapshot_verification_chart(self) -> bool:
        """Before a verification measurement starts, copy the chart it is about
        to measure into its own dated folder (#130, Knut 2026-07-25).

        A run's verification chart is shared by every dated verification beneath
        it, so replacing it later would leave the older results describing a
        chart nobody has any more. The snapshot is what **Restore Used Chart**
        puts back.

        With the Verification dropdown on "New verification" the dated folder is
        created here — before anything else is written — and the bar moves to it,
        so the rest of the measurement files into that folder. Best-effort: a
        snapshot must never stop a measurement from running.

        Returns **False** only when the user, asked whether to replace the chart
        an existing verification date was measured with, chose to stop.
        """
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return True
        if not ctl.target.is_verification() or not self._is_verify_checked():
            # Profiling: the run keeps one copy of the chart it was measured
            # with, in runs/runN/chart/ (#130, Knut 2026-07-27).
            return self._snapshot_profiling_chart(ctl)
        try:
            from workflow.verify_chart_snapshot import snapshot_chart
            proj = ctl.project_or_none()
            run_id = ctl.target.profile_run
            if proj is None or not run_id or not proj.has_run(run_id):
                return True
            run = proj.run(run_id)
            vid = ctl.target.verification_id
            verification = None
            if vid and run.verification(vid).dir.exists():
                verification = run.verification(vid)
                if self._chart_overwrite_choice(verification) == "cancel":
                    return False
            if verification is None:
                verification = run.new_verification()
                verification.ensure_dir()
                ctl.set_verification_id(verification.id)
            snapshot_chart(verification)
        except Exception:      # noqa: BLE001 — never block a measurement
            log.warning("Could not snapshot the verification chart",
                        exc_info=True)
        return True

    def _snapshot_profiling_chart(self, ctl) -> bool:
        """Copy the run's chart into ``runs/runN/chart/`` before measuring.

        Returns False only when the user chose to stop. Choosing "Measure
        without changing the stored chart" leaves the copy alone and marks the
        run, so the interface can say the copy no longer describes what the run
        holds.
        """
        try:
            from workflow.chart_slot import slot_for
            from workflow.verify_chart_snapshot import snapshot_slot
            proj = ctl.project_or_none()
            run_id = ctl.target.profile_run
            if proj is None or not run_id or not proj.has_run(run_id):
                return True
            run = proj.run(run_id)
            choice = self._profiling_overwrite_choice(run)
            if choice == "cancel":
                return False
            meta = run.load_meta()
            if choice == "keep":
                if not meta.chart_snapshot_stale:
                    meta.chart_snapshot_stale = True
                    run.save_meta(meta)
                self._log.appendPlainText(
                    "\n" + tr("The stored chart for this run is being left as "
                              "it is, so it will not describe this measurement."))
                return True
            snapshot_slot(slot_for(run))
            if meta.chart_snapshot_stale:
                meta.chart_snapshot_stale = False   # the copy matches again
                run.save_meta(meta)
        except Exception:      # noqa: BLE001 — never block a measurement
            log.warning("Could not snapshot the profiling chart", exc_info=True)
        return True

    def _blocked_by_new_run(self) -> bool:
        """True — and the explaining pop-up has been shown — when the bar's
        **Profile run** is "New run" (#130, Knut). A run has to exist before its
        chart can be measured."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None or ctl.target.profile_run:
            return False
        from PyQt6.QtWidgets import QMessageBox
        from core.measurement_target import new_run_guard_message
        QMessageBox.information(self, tr("Choose a profile run to measure"),
                                new_run_guard_message("measure"))
        return True

    def _on_start(self) -> None:
        if not self._ti1_path:
            self._log.appendPlainText("[ERROR] No .ti2 file selected.")
            self._log.ensureCursorVisible()
            return
        if self._runner.is_running:
            return
        # #130 (Knut): "New run" names a run that does not exist yet, so there is
        # nothing to measure. Say so, and explain how to create one.
        if self._blocked_by_new_run():
            return
        # #131: enter measurement mode so per-patch/strip sounds are allowed and
        # the selected clips are pre-loaded for zero-latency playback.
        if getattr(self, "_sound", None) is not None:
            self._sound.arm()
        # A fresh read starts with a clean pace panel (Knut: it must be cleared
        # when a strip is re-read, a chart is re-read, or measuring is stopped).
        self._clear_pace_readout()
        self._finish_sound_played = False
        import time as _t
        self._measure_started_at = _t.monotonic()

        # #130 Hole 1: don't start a verification of a run that has no profile.
        block = self._verification_guard()
        if block:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, tr("Build a profile before verifying"), block)
            self._uncheck_verification()      # auto-switch back to Profiling (Knut)
            return

        # #130: keep a copy of the chart this verification measures, BEFORE any
        # measurement file is written.
        if not self._snapshot_verification_chart():
            return          # the user chose not to replace the stored chart

        params = self._collect_params()
        if not self._confirm_nonrandom_bidir(params):
            return
        self._preview.set_bidirectional(self._effective_bidirectional(params))
        self._log.clear()
        self._auto_proceed = False
        self._all_done_shown = False
        self._spot_current_loc = ""
        self._spot_click_on = False
        # Remember whether this is a patch-by-patch (spot) session, so the
        # completion dialog can speak of "patches" instead of "stripes".
        self._spot_session = self._is_pbp_checked()
        # Capture the verification-measurement choice now, so toggling the box
        # mid-read can't change how the finished .ti3 is handled.
        self._verify_run = self._is_verify_checked()
        self._instrument_disconnected = False
        self._device_busy = False
        self._no_instrument = False
        _ti3_pre = self._ti1_path.with_suffix(".ti3") if self._ti1_path else None
        self._ti3_mtime_before = (
            _ti3_pre.stat().st_mtime if (_ti3_pre and _ti3_pre.exists()) else None
        )
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/IM", "chartread.exe"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            subprocess.run(
                ["killall", "-q", "chartread"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
            )
        self._set_settings_enabled(False)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        QApplication.instance().installEventFilter(self)

        if self._current_mode() == "guided":
            resume_cb  = self._resume_cb
            refine_cb  = self._refine_cb
        else:
            resume_cb  = self._m_resume_cb
            refine_cb  = self._m_refine_cb
        guided = (
            resume_cb.isChecked()
            and refine_cb.isChecked()
            and bool(self._strip_list)
        )
        self._guided_refinement_active = guided
        self._resume_active = resume_cb.isChecked()

        self._manager.set_guided_strips(self._strip_list if guided else [])

        self._manager.start(
            params,
            on_line=self._on_log_line,
            on_finish=self._on_measure_done,
        )
        self.measurement_active.emit(True)

    def _confirm_nonrandom_bidir(self, params: "MeasureParams") -> bool:
        """Warn before forcing bidirectional reading on a non-randomised chart.

        Forcing ``-b`` lets a strip be read in either direction, but chartread
        relies on randomised patch order to tell strips (and reading direction)
        apart. On a fixed-order chart that recognition can silently latch onto
        the wrong strip, producing a measurement that builds a colour-cast
        profile with no obvious error.

        Returns True if measurement should proceed (chart is randomised, the
        option isn't forcing ``-b``, the warning is suppressed, or the user
        chose to continue), False if the user cancelled.
        """
        if not params.force_bidir or self._detected_randomized:
            return True
        if bool(self._settings.get("measure_hide_nonrandom_bidir_warning", False)):
            return True

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Bidirectional reading on a fixed-order chart"))
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(12)

        heading = QLabel(
            tr("This chart is laid out in a fixed (non-randomised) patch order, "
            "and strip recognition is set to <b>Bidirectional forced (-b)</b>."),
            dlg,
        )
        heading.setWordWrap(True)
        heading.setStyleSheet("font-weight: 600;")
        lay.addWidget(heading)

        body = QLabel(
            tr("Forcing bidirectional reading lets you scan each strip in either "
            "direction. To do that reliably, chartread depends on the patches "
            "being printed in a shuffled (randomised) order — that is what gives "
            "every strip a unique colour signature.<br><br>"
            "On a fixed-order chart the strips can look alike, so chartread may "
            "lock onto the <i>wrong</i> strip or the wrong direction. That "
            "usually produces no error message — just a measurement file that "
            "builds a profile with colour casts.<br><br>"
            "<b>What to do:</b><br>"
            "• Safest: set Strip recognition to <b>Argyll default</b> (turn "
            "<i>Auto</i> off and pick it), then scan every strip the same way.<br>"
            "• Or regenerate this chart with randomisation enabled, then measure "
            "that copy.<br>"
            "• If you know this chart's patch order is already well mixed, it is "
            "safe to continue."),
            dlg,
        )
        body.setWordWrap(True)
        lay.addWidget(body)

        hide_cb = QCheckBox(tr("Don't show this again"), dlg)
        lay.addWidget(hide_cb)

        bb = QDialogButtonBox(dlg)
        continue_btn = bb.addButton(tr("Continue anyway"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = bb.addButton(tr("Cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        cancel_btn.setDefault(True)
        continue_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        lay.addWidget(bb)

        proceed = dlg.exec() == QDialog.DialogCode.Accepted
        # Honour "don't show again" whichever button was used, so a user who
        # cancels to fix the chart isn't nagged on every subsequent attempt.
        if hide_cb.isChecked():
            self._settings.set("measure_hide_nonrandom_bidir_warning", True)
        return proceed

    def _on_stop(self) -> None:
        self._key_watchdog.stop()
        self._manager.abort()

    def _arm_key_watchdog(self) -> None:
        """Start the no-response watchdog after sending a keystroke from a dialog.

        If chartread does not emit any output within the timer interval, the
        watchdog assumes the keystroke did not reach the instrument and warns
        the user (without auto-aborting — the Stop button stays in their hands).
        """
        self._last_chartread_output_ts = time.monotonic()
        self._key_watchdog.start()

    def _on_key_watchdog_timeout(self) -> None:
        # Only warn if chartread is still expected to be running and no output
        # arrived between arming and now.
        if not self._stop_btn.isEnabled():
            return
        idle = time.monotonic() - self._last_chartread_output_ts
        if idle < self._key_watchdog.interval() / 1000.0 - 0.5:
            return
        self._log.appendPlainText(
            "[WARN] No response from chartread after sending a key. "
            "The keystroke may not have reached the instrument. "
            "Try pressing the key again, or click Stop and restart the measurement."
        )
        self._log.ensureCursorVisible()
        self._flash_status(
            "chartread is not responding — the last keystroke may have been lost.",
            duration_ms=8000,
        )

    def _on_keypress_failed(self, key_label: str, reason: str) -> None:
        self._log.appendPlainText(
            f"[WARN] Could not send '{key_label}' to chartread: {reason} "
            "Click Stop and restart the measurement; if the problem persists, "
            "please report it with the log file."
        )
        self._log.ensureCursorVisible()
        self._flash_status(
            f"Keypress '{key_label}' could not be delivered to chartread.",
            duration_ms=8000,
        )

    def _on_strip_misaligned(self, strip: str, offset: int,
                             base_de: str, best_de: str) -> None:
        """Opt-in safety net (#50): a strip fit dramatically better shifted by a
        patch — a likely one-off misread. Offer to re-measure it. This fires
        AFTER the strip is already saved, so we don't answer a chartread prompt;
        we just inform and, on request, jump back to re-read the strip."""
        from PyQt6.QtWidgets import (
            QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
        )
        n = abs(int(offset))
        patches = (tr("one patch") if n == 1
                   else tr("{n} patches").format(n=n))
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Strip may be misaligned"))
        dlg.setMinimumWidth(540)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)
        msg = QLabel(tr(
            "<b>Strip {strip} may have been read slightly out of alignment.</b>"
            "<br><br>Its colours came out much closer to the chart's design when "
            "shifted by {patches} — the average colour error drops from {base} to "
            "{best} ΔE. That usually means the reader locked onto the row one "
            "patch off (for example it started on the blank paper before the "
            "first patch), so every patch is filed one position out and the last "
            "one reads the empty paper.<br><br>Nothing else is affected — your "
            "other strips and everything read so far are saved. It is only this "
            "one strip.<br><br>&nbsp;&nbsp;<b>Re-measure this strip</b> — jump "
            "back to strip {strip} and scan it again (recommended).<br><br>"
            "&nbsp;&nbsp;<b>Keep it</b> — accept this reading as it is.<br><br>"
            "&nbsp;&nbsp;<b>Stop</b> — stop measuring for now."
        ).format(strip=strip, patches=patches, base=base_de, best=best_de), dlg)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        choice = ["keep"]
        remeasure_btn = QPushButton(tr("Re-measure this strip"), dlg)
        keep_btn = QPushButton(tr("Keep it"), dlg)
        stop_btn = QPushButton(tr("Stop"), dlg)
        remeasure_btn.setObjectName("primary")
        for b in (remeasure_btn, keep_btn, stop_btn):
            b.setFixedHeight(32)

        def _pick(v):
            choice[0] = v
            dlg.accept()
        remeasure_btn.clicked.connect(lambda: _pick("remeasure"))
        keep_btn.clicked.connect(lambda: _pick("keep"))
        stop_btn.clicked.connect(lambda: _pick("stop"))

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(remeasure_btn)
        row.addWidget(keep_btn)
        row.addStretch()
        row.addWidget(stop_btn)
        layout.addLayout(row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        if choice[0] == "remeasure":
            self._manager.goto_strip(strip)     # re-read this strip next
        elif choice[0] == "stop":
            self._on_stop()

    def _flash_status(self, text: str, duration_ms: int = 8000) -> None:
        self._status_bar_lbl.setText(text)
        self._status_bar_lbl.setVisible(True)
        QTimer.singleShot(duration_ms, lambda: self._status_bar_lbl.setVisible(False))

    def _on_log_line(self, line: str) -> None:
        self._log.appendPlainText(line)
        self._log.ensureCursorVisible()
        # chartread produced output → it is alive and processed (or never needed)
        # the last keystroke. Cancel the watchdog so it cannot misfire mid-scan.
        self._last_chartread_output_ts = time.monotonic()
        if self._key_watchdog.isActive():
            self._key_watchdog.stop()
        # Only flag fatal errors — strip read failures are recoverable and handled
        # separately via the strip_error signal / dialog.
        if "communications failure" in line.lower():
            self._measure_failed = True

    def _on_wrong_strip(self, read: str, expected: str) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Wrong Strip Read"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            tr("<b>This reading looks like strip {read}, but strip {expected} was expected.</b><br><br>This usually means the instrument was placed on the wrong row — or two rows simply look very similar. You have three options:<br><br>&nbsp;&nbsp;<b>Use Anyway</b> — keep this reading and save it as strip {expected} (the row you were asked to scan). Only choose this if you are sure the instrument really was on strip {expected} and the warning is a false alarm — the reading is always filed under {expected}, not {read}.<br><br>&nbsp;&nbsp;<b>Retry</b> — discard this reading and try again. Place your instrument on strip {expected} and re-scan.<br><br>&nbsp;&nbsp;<b>Give Up</b> — stop the measurement without saving.").format(read=read, expected=expected),
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        chosen = ["\r"]   # default: use anyway

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        use_btn   = QPushButton(tr("Use Anyway"), dlg)
        retry_btn = QPushButton(tr("Retry"),      dlg)
        give_btn  = QPushButton(tr("Give Up"),    dlg)
        use_btn.setObjectName("primary")
        use_btn.setFixedHeight(32)
        retry_btn.setFixedHeight(32)
        give_btn.setFixedHeight(32)

        def _use():
            chosen[0] = "\r"
            dlg.accept()

        def _retry():
            chosen[0] = " "
            dlg.accept()

        def _give_up():
            chosen[0] = "\x1b"
            dlg.accept()

        use_btn.clicked.connect(_use)
        retry_btn.clicked.connect(_retry)
        give_btn.clicked.connect(_give_up)

        btn_row.addWidget(use_btn)
        btn_row.addWidget(retry_btn)
        btn_row.addStretch()
        btn_row.addWidget(give_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        self._manager.send_key(chosen[0])
        self._arm_key_watchdog()

        if chosen[0] != "\x1b":
            QApplication.instance().installEventFilter(self)
        # If giving up, chartread will exit and _on_measure_done re-enables UI.

    def _on_unexpected_response(self, delta_e: str) -> None:
        from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Unexpected Color Response"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            tr("<b>An unexpected color response was detected (ΔE {delta_e}).</b><br><br>This usually means the instrument was not aligned correctly with the stripe, was moved during the scan, or the wrong stripe was read. A ΔE this high indicates the measured colors are very far from what is expected.<br><br>&nbsp;&nbsp;<b>Use Anyway</b> — accept the reading and continue. Only use this if you are sure the scan was correct.<br><br>&nbsp;&nbsp;<b>Retry</b> — discard this reading, re-position your instrument carefully on the correct stripe, and try again.<br><br>&nbsp;&nbsp;<b>Give Up</b> — stop the measurement without saving.").format(delta_e=delta_e),
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        chosen = ["\r"]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        use_btn   = QPushButton(tr("Use Anyway"), dlg)
        retry_btn = QPushButton(tr("Retry"),      dlg)
        give_btn  = QPushButton(tr("Give Up"),    dlg)
        use_btn.setObjectName("primary")
        use_btn.setFixedHeight(32)
        retry_btn.setFixedHeight(32)
        give_btn.setFixedHeight(32)

        def _use():
            chosen[0] = "\r"
            dlg.accept()

        def _retry():
            chosen[0] = " "
            dlg.accept()

        def _give_up():
            chosen[0] = "\x1b"
            dlg.accept()

        use_btn.clicked.connect(_use)
        retry_btn.clicked.connect(_retry)
        give_btn.clicked.connect(_give_up)

        btn_row.addWidget(use_btn)
        btn_row.addWidget(retry_btn)
        btn_row.addStretch()
        btn_row.addWidget(give_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        self._manager.send_key(chosen[0])
        self._arm_key_watchdog()

        if chosen[0] != "\x1b":
            QApplication.instance().installEventFilter(self)

    def _on_sensor_wrong_position(self) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Instrument in Wrong Position"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            tr("<b>The measurement device is in the wrong position.</b><br><br>"
            "It looks like the instrument is still in its <b>calibration position</b> "
            "(sensor facing up or to the side). "
            "To scan a strip, it needs to be switched to <b>measuring position</b> "
            "(sensor facing down, resting on the paper).<br><br>"
            "How to fix it:<br>"
            "&nbsp;&nbsp;1. Flip or slide the sensor head so it faces <b>downward</b>.<br>"
            "&nbsp;&nbsp;2. Place the instrument at the beginning of the strip.<br>"
            "&nbsp;&nbsp;3. Press <b>OK</b> — chartread is still waiting and you can scan straight away."),
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        QApplication.instance().installEventFilter(self)

    def _on_strip_interrupted(self) -> None:
        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Strip Read Interrupted"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            tr("<b>The strip read was stopped before it finished.</b><br><br>"
            "This usually happens if the instrument switch is pressed mid-scan "
            "or if scanning is interrupted by another process.<br><br>"
            "&nbsp;&nbsp;<b>Resume</b> — chartread is still waiting; "
            "re-position the instrument at the start of the current strip and continue.<br><br>"
            "&nbsp;&nbsp;<b>Give Up</b> — stop the measurement without saving."),
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        chosen = ["\r"]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        resume_btn = QPushButton(tr("Resume"), dlg)
        give_btn   = QPushButton(tr("Give Up"), dlg)
        resume_btn.setObjectName("primary")
        resume_btn.setFixedHeight(32)
        give_btn.setFixedHeight(32)

        def _resume():
            chosen[0] = "\r"
            dlg.accept()

        def _give_up():
            chosen[0] = "\x1b"
            dlg.accept()

        resume_btn.clicked.connect(_resume)
        give_btn.clicked.connect(_give_up)

        btn_row.addWidget(resume_btn)
        btn_row.addStretch()
        btn_row.addWidget(give_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        self._manager.send_key(chosen[0])
        self._arm_key_watchdog()

        if chosen[0] != "\x1b":
            QApplication.instance().installEventFilter(self)

    def _on_unread_confirm(self, patch_info: str) -> None:
        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Patches Still Unread"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            tr("<b>The chart is not fully measured yet.</b><br><br>At least one patch is still unread: <b>{patch_info}</b>.<br><br>&nbsp;&nbsp;<b>Save Partial</b> — save what's been measured so far. You can resume later by ticking <i>Refine / resume existing measurement (-r)</i>.<br><br>&nbsp;&nbsp;<b>Keep Measuring</b> — return to the strip menu and continue.").format(patch_info=patch_info),
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        chosen = ["n"]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        save_btn = QPushButton(tr("Save Partial"), dlg)
        keep_btn = QPushButton(tr("Keep Measuring"), dlg)
        save_btn.setObjectName("primary")
        save_btn.setFixedHeight(32)
        keep_btn.setFixedHeight(32)

        def _save():
            chosen[0] = "y"
            dlg.accept()

        def _keep():
            chosen[0] = "n"
            dlg.accept()

        save_btn.clicked.connect(_save)
        keep_btn.clicked.connect(_keep)

        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        btn_row.addWidget(keep_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        self._manager.send_key(chosen[0])
        self._arm_key_watchdog()

        # 'y' makes chartread write the partial .ti3 and exit; 'n' returns
        # to the strip menu where the event filter is needed again.
        if chosen[0] == "n":
            QApplication.instance().installEventFilter(self)

    def _on_generic_instrument_error(self, friendly: str, technical: str) -> None:
        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Instrument Error"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Show the friendly message first, with the technical detail as a smaller line.
        msg = QLabel(
            tr("<b>{friendly}</b><br><span style='color:#888;'>({technical})</span><br><br>&nbsp;&nbsp;<b>Retry</b> — try the operation again.<br><br>&nbsp;&nbsp;<b>Give Up</b> — stop the measurement without saving.").format(friendly=friendly, technical=technical),
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        chosen = ["\r"]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        retry_btn = QPushButton(tr("Retry"), dlg)
        give_btn  = QPushButton(tr("Give Up"), dlg)
        retry_btn.setObjectName("primary")
        retry_btn.setFixedHeight(32)
        give_btn.setFixedHeight(32)

        def _retry():
            chosen[0] = "\r"
            dlg.accept()

        def _give_up():
            chosen[0] = "\x1b"
            dlg.accept()

        retry_btn.clicked.connect(_retry)
        give_btn.clicked.connect(_give_up)

        btn_row.addWidget(retry_btn)
        btn_row.addStretch()
        btn_row.addWidget(give_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        self._manager.send_key(chosen[0])
        self._arm_key_watchdog()

        if chosen[0] != "\x1b":
            QApplication.instance().installEventFilter(self)

    def _on_device_busy(self) -> None:
        if self._device_busy:
            return
        self._device_busy = True

    def _on_no_instrument(self) -> None:
        self._no_instrument = True

    def _on_usb_claimed_by_vm(self) -> None:
        self._usb_claimed_by_vm = True

    # Group B: capture startup-failure messages so _on_measure_done can show
    # a friendly terminal dialog instead of the generic "measurement failed".
    def _on_coms_init_failed(self, msg: str) -> None:
        self._coms_init_failed_msg = msg

    def _on_inst_init_failed(self, msg: str) -> None:
        self._inst_init_failed_msg = msg

    def _on_instrument_wrong_type(self, capability: str) -> None:
        self._instrument_wrong_type = capability

    def _on_ccmx_load_failed(self, msg: str) -> None:
        self._ccmx_load_failed_msg = msg

    def _on_mode_set_failed(self, msg: str) -> None:
        self._mode_set_failed_msg = msg

    def _on_calibration_retrying(self, attempt: int, total: int) -> None:
        """A failed calibration is being retried automatically. The log already
        carries the detail; this keeps the cursor on it so the user sees why the
        app pauses for a moment instead of thinking it has frozen."""
        self._log.ensureCursorVisible()

    def _on_engine_fell_back(self, reason: str) -> None:
        """ChromIQ's engine could not drive the instrument, so the run restarted
        on stock ArgyllCMS chartread. Say so plainly — the measurement carries on
        and the user needs no different handling, but they should know which
        reader they are now using (the live preview stays off, for one)."""
        self._log.appendPlainText(tr(
            "[Engine] Switched to ArgyllCMS chartread because ChromIQ's own "
            "measuring engine could not use your instrument ({reason}). "
            "Measuring continues as normal; you can turn the ChromIQ engine off "
            "for good in Preferences if this keeps happening."
        ).format(reason=reason))
        self._log.ensureCursorVisible()

    def _on_engine_fell_back_resumed(self, reason: str) -> None:
        """Like _on_engine_fell_back, but the engine had already measured part of
        the chart when the instrument failed (#134). The manager writes the full,
        reassuring explanation to the log; here we add a brief, non-blocking
        status flash so the good news — nothing was lost, just carry on — is
        impossible to miss without interrupting the measurement."""
        self._flash_status(
            tr("Your measured strips are safe — continuing on ArgyllCMS "
               "chartread from where you left off."),
            duration_ms=8000)

    def _on_info_message(self, category: str, text: str) -> None:
        # Log it and flash a status bar message (non-blocking).
        self._log.appendPlainText(f"[INFO] {text}")
        self._log.ensureCursorVisible()
        self._flash_status(text, duration_ms=6000)

    # Group D: spot/XY mode defensive dialogs. They only fire if someone
    # invokes chartread in a non-strip mode (e.g. through extra-args). In
    # strip mode these signals are never emitted.
    def _on_xy_place_sheet(self, sheet_n: int, total: int) -> None:
        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Place Sheet on XY Table"))
        dlg.setMinimumWidth(460)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)
        msg = QLabel(
            tr("<b>Place sheet {sheet_n} of {total} on the XY table.</b><br><br>Press <b>Continue</b> when the sheet is positioned, or <b>Give Up</b> to stop without saving.").format(sheet_n=sheet_n, total=total),
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        chosen = ["\r"]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cont_btn = QPushButton(tr("Continue"), dlg)
        give_btn = QPushButton(tr("Give Up"), dlg)
        cont_btn.setObjectName("primary")
        cont_btn.setFixedHeight(32)
        give_btn.setFixedHeight(32)

        def _cont():
            chosen[0] = "\r"
            dlg.accept()

        def _give_up():
            chosen[0] = "\x1b"
            dlg.accept()

        cont_btn.clicked.connect(_cont)
        give_btn.clicked.connect(_give_up)

        btn_row.addWidget(cont_btn)
        btn_row.addStretch()
        btn_row.addWidget(give_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        self._manager.send_key(chosen[0])
        self._arm_key_watchdog()
        if chosen[0] != "\x1b":
            QApplication.instance().installEventFilter(self)

    def _on_spot_ready(self, patch_id: str) -> None:
        # Spot mode isn't ChromIQ's default workflow; a status-bar hint is
        # enough — the keyboard event filter still passes f/b/n/d/Enter/Esc
        # through to chartread so the user can drive it manually.
        self._flash_status(
            tr("Spot mode: ready to read patch '{patch}'. "
               "Press Enter to read, f/b to navigate, d when done.").format(
                patch=patch_id),
            duration_ms=10000,
        )

    def _on_abort_confirm(self) -> None:
        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Confirm Abort"))
        dlg.setMinimumWidth(420)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)
        msg = QLabel(
            tr("<b>Stop measuring without saving?</b><br><br>"
            "Choose <b>Yes</b> to abort, or <b>No</b> to keep measuring."),
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        chosen = ["n"]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        yes_btn = QPushButton(tr("Yes — Abort"), dlg)
        no_btn  = QPushButton(tr("No — Keep Measuring"), dlg)
        no_btn.setObjectName("primary")
        yes_btn.setFixedHeight(32)
        no_btn.setFixedHeight(32)

        def _yes():
            chosen[0] = "y"
            dlg.accept()

        def _no():
            chosen[0] = "n"
            dlg.accept()

        yes_btn.clicked.connect(_yes)
        no_btn.clicked.connect(_no)

        btn_row.addWidget(yes_btn)
        btn_row.addStretch()
        btn_row.addWidget(no_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        self._manager.send_key(chosen[0])
        self._arm_key_watchdog()
        if chosen[0] == "n":
            QApplication.instance().installEventFilter(self)

    def _on_instrument_disconnected(self) -> None:
        if self._instrument_disconnected:
            return
        # The readings live only in chartread's memory until 'd' writes the
        # .ti3 — killing the process during the Save-Partial chain would
        # discard them. Let the chain run; if chartread dies anyway,
        # _on_measure_done reports the failure.
        if self._manager.save_partial_in_progress:
            self._log.appendPlainText(
                "\n" + tr("[WARN] Instrument connection lost — still trying "
                          "to save the partial measurement…")
            )
            self._log.ensureCursorVisible()
            return
        self._instrument_disconnected = True
        self._log.appendPlainText(
            "\n[ERROR] Instrument disconnected — stopping measurement."
        )
        self._log.ensureCursorVisible()
        self._manager.abort()

    def _is_last_unread_strip(self) -> bool:
        """True when the strip that just failed is the only one still unread.

        "Skip Stripe" asks ArgyllCMS for the next UNREAD strip, and that search
        wraps around — so with nothing else unread it comes back to this very
        strip. Skipping then skips nothing (Knut, #131 2026-07-26). Answered
        only from the engine's own read map: with the separate chartread there
        is no reliable list, and guessing would put the wrong button on screen.
        """
        if not self._manager.engine_active:
            return False
        read_map = getattr(self, "_engine_read", None)
        if not read_map:
            return False
        current = getattr(self, "_current_strip_letter", "")
        unread = [s for s, done in read_map.items() if not done]
        return unread == [current] if current else False

    def _on_strip_error(self, reason: str) -> None:
        from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

        # Sound FIRST: this handler opens a modal dialog and blocks inside its
        # own slot, so anything connected after it could not be heard until the
        # dialog was dismissed. The cue belongs to the window appearing (Knut,
        # #131 2026-07-26) — and there is deliberately no sound on the buttons,
        # because the failure has already been announced.
        self._on_strip_error_sound(reason)

        # "All Stripes Read" is always the LAST window (Knut): while any strip
        # window is up, the completion window waits its turn.
        self._pace_prompt_open = True

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Strip Read Failed"))
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        is_coms = "communication" in reason.lower()
        if is_coms and self._manager.engine_active:
            # Engine: the readings were already written to disk before this
            # dialog appeared — no data-loss warning needed, just calm facts.
            advice = tr(
                "<b>The instrument lost communication with the computer.</b><br><br>"
                "Check that the instrument's cable is firmly connected (try a "
                "different USB port or cable), make sure no other application is "
                "using the device, then reconnect it before retrying.") + "<br><br>" + tr(
                "<b>Good news:</b> everything you have read so far is already "
                "saved on disk — the engine writes your readings after every "
                "strip. Whatever you choose here, nothing is lost, and "
                "<i>Continue Measurement</i> can pick up exactly where you "
                "stopped.") + "<br><br>"
        elif is_coms:
            advice = tr(
                "<b>The instrument lost communication with the computer.</b><br><br>"
                "Check that the instrument's cable is firmly connected (try a "
                "different USB port or cable), make sure no other application is "
                "using the device, then reconnect it before retrying.") + "<br><br>" + tr(
                "<b>Note:</b> saving needs one last response from the instrument. "
                "Unplug the USB cable and plug it back in — directly into the "
                "computer if possible, not through a hub — and only then click "
                "<i>Save Partial &amp; Quit</i>. If the instrument stays silent, "
                "the readings from this session cannot be saved.") + "<br><br>"
        else:
            advice = tr(
                "<b>The stripe could not be read:</b> {reason}<br><br>"
                "Re-position your instrument at the beginning of the stripe and try again. "
                "If the error keeps occurring, try scanning more slowly and steadily, or "
                "raise the <i>Patch consistency tolerance</i> setting before the next run."
            ).format(reason=reason) + "<br><br>"

        # Worked out before the text, because the second choice changes both
        # its name and what it does when this is the only unread stripe.
        last_one = self._is_last_unread_strip()
        if last_one:
            choices = tr(
                "&nbsp;&nbsp;<b>Retry</b> — read this same stripe again.<br>"
                "&nbsp;&nbsp;<b>Finish Without This Strip</b> — this is the only "
                "stripe still unread, so there is nowhere to skip to. Saves the "
                "stripes you have read and ends the measurement; loading the "
                "chart again lets you continue from here.<br>")
        else:
            choices = tr(
                "&nbsp;&nbsp;<b>Retry</b> — read this same stripe again.<br>"
                "&nbsp;&nbsp;<b>Skip Stripe</b> — leave this stripe unread for now "
                "and jump to the next unread one. You can come back to it later in "
                "this session.<br>")
        msg = QLabel(
            advice + choices + tr(
                "&nbsp;&nbsp;<b>Save Partial &amp; Quit</b> — stop here and save what "
                "you have read so far. Next time you load this chart, "
                "<i>Continue Measurement</i> will pick up where you left off."),
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        # "retry" → send "\r"                                        (any key = retry)
        # "skip"  → send "\r" then "n" via manager                   (retry → strip menu → next unread)
        # "save"  → send "\r" then "d" then auto-"y" on Are-you-sure (retry → strip menu → done → confirm)
        chosen = ["retry"]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        retry_btn = QPushButton(tr("Retry"), dlg)
        skip_btn = QPushButton(
            tr("Finish Without This Strip") if last_one else tr("Skip Stripe"),
            dlg)
        if last_one:
            skip_btn.setToolTip(tr(
                "Saves the strips you have read and ends the measurement. This "
                "strip stays unread; loading the chart again lets you continue "
                "from here."))
        save_btn  = QPushButton(tr("Save Partial && Quit"), dlg)
        retry_btn.setObjectName("primary")
        retry_btn.setFixedHeight(32)
        skip_btn.setFixedHeight(32)
        save_btn.setFixedHeight(32)

        def _retry():
            chosen[0] = "retry"
            dlg.accept()

        def _skip():
            # With nothing else unread there is nowhere to skip to, so the
            # honest action is to save what has been read and stop.
            chosen[0] = "finish" if last_one else "skip"
            dlg.accept()

        def _save():
            chosen[0] = "save"
            dlg.accept()

        retry_btn.clicked.connect(_retry)
        skip_btn.clicked.connect(_skip)
        save_btn.clicked.connect(_save)

        btn_row.addWidget(retry_btn)
        btn_row.addWidget(skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        self._pace_prompt_open = False
        if getattr(self, "_all_done_deferred", False) and chosen[0] not in (
                "retry", "skip"):
            # Nothing more will be read, so the completion window that arrived
            # while this one was up may now have its turn (Knut: it is always
            # the last window).
            self._all_done_deferred = False
            self._on_all_stripes_done()
        elif chosen[0] in ("retry", "skip"):
            self._all_done_deferred = False   # back to measuring

        if chosen[0] == "retry":
            self._manager.send_key("\r")
        elif chosen[0] == "finish":
            # Save what has been read and end, which is what skipping the only
            # unread strip actually means (Knut, #131 2026-07-26).
            self._manager.send_save_partial_and_quit()
        elif chosen[0] == "skip":
            # Two-step: retry returns chartread to the strip menu, then 'n'
            # jumps to the next unread stripe.
            self._manager.send_post_retry_key("n")
        else:  # save partial and quit
            # Three-step chain inside the manager: \r → strip menu → 'd' →
            # ("Are you sure" → 'y') → chartread writes the .ti3 and exits.
            self._manager.send_save_partial_and_quit()

        self._arm_key_watchdog()
        QApplication.instance().installEventFilter(self)
        # On the save path chartread will exit on its own once 'y' is sent,
        # and _on_measure_done will then re-enable the UI and auto-arm resume.

    def _on_calibration_prompt(self, cond: str = "", message: str = "",
                               optional: bool = False) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Calibration Required"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        from ui.ti2_loader import (calibration_instructions_html,
                                    instrument_family)
        msg = QLabel(
            calibration_instructions_html(
                instrument_family(self._detected_instrument)),
            dlg,
        )
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        # The instrument's own words for this particular step. Stock chartread
        # prints them; showing them here means the user follows what their meter
        # actually asked for rather than a generic instruction — which matters
        # when a meter wants something unusual, like an i1Pro's white tile.
        if message.strip():
            own = QLabel(
                f"<b>{tr('What your instrument asked for:')}</b><br>"
                f"{html.escape(message.strip())}", dlg)
            own.setTextFormat(Qt.TextFormat.RichText)
            own.setWordWrap(True)
            layout.addWidget(own)

        if optional:
            note = QLabel(tr(
                "This calibration step is optional. You can skip it and carry "
                "on measuring, but your readings may be a little less accurate "
                "without it."), dlg)
            note.setWordWrap(True)
            layout.addWidget(note)

        btn_box = QDialogButtonBox()
        ok_btn = btn_box.addButton(tr("Start Calibration"), QDialogButtonBox.ButtonRole.AcceptRole)
        ok_btn.setObjectName("primary")
        skip_btn = (btn_box.addButton(tr("Skip this step"),
                                      QDialogButtonBox.ButtonRole.DestructiveRole)
                    if optional else None)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        tint_dialog_primary(dlg, _TAB_COLOR)
        result = dlg.exec()
        if skip_btn is not None and btn_box.clickedButton() is skip_btn:
            # Only offered when the instrument itself said the step is optional,
            # so 's' is the answer chartread expects here.
            self._manager.send_key("s")
            self._arm_key_watchdog()
            QApplication.instance().installEventFilter(self)
        elif result == QDialog.DialogCode.Accepted:
            # "Start Calibration" — any key tells chartread to proceed.
            self._manager.send_key("\r")
            self._arm_key_watchdog()
            QApplication.instance().installEventFilter(self)
        else:
            # The user dismissed the prompt with the window's close button (or
            # Esc) instead of starting calibration. Esc at chartread's
            # calibration prompt cancels the run cleanly; chartread then exits
            # and _on_measure_done re-enables the UI (same path as "Give Up").
            self._manager.send_key("\x1b")
            self._arm_key_watchdog()
            # Don't re-install the event filter: chartread is shutting down.

    def _on_calibration_done(self) -> None:
        from PyQt6.QtWidgets import (
            QDialog, QDialogButtonBox, QFrame, QGridLayout, QLabel, QVBoxLayout,
        )

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        from ui.theme import resolve_mode
        _mode = resolve_mode(self._settings.get("appearance", "auto"))
        if _mode == "light":
            _frame_bg, _frame_border, _dim_text = "#f7f4ef", "#d0ccc6", "#7a7570"
        else:
            _frame_bg, _frame_border, _dim_text = "#181818", "#2a2a2a", "#909090"
        _frame_style = (
            f"QFrame {{ background: {_frame_bg}; border: 1px solid {_frame_border};"
            " border-radius: 6px; }"
        )
        _key_style = (
            f"font-family: Menlo, monospace; font-weight: 700; color: {_TAB_COLOR};"
            " background: transparent; border: none;"
        )
        _dim_style = f"color: {_dim_text}; background: transparent; border: none;"
        _plain_style = "background: transparent; border: none;"

        # Instrument-specific "how to scan a strip" wording, shared by all three
        # variants below (standard / guided / resume) so the physical steps match
        # the chart's instrument (ColorMunki dial, i1Pro base-and-slide, …).
        from ui.ti2_loader import instrument_family, measurement_instructions_html
        _fam = instrument_family(self._detected_instrument)
        _how = measurement_instructions_html(_fam)

        if self._spot_session:
            dlg.setWindowTitle(tr("Calibration Complete — How to Measure"))

            msg = QLabel(
                tr("<b>Calibration complete. You are ready to measure patch by "
                   "patch.</b><br><br>Place the instrument on the "
                   "<b>highlighted patch</b> in the preview and take a reading. "
                   "The next patch is highlighted automatically."),
                dlg,
            )
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setWordWrap(True)
            layout.addWidget(msg)

            key_frame = QFrame(dlg)
            key_frame.setStyleSheet(_frame_style)
            kfl = QGridLayout(key_frame)
            kfl.setContentsMargins(16, 12, 16, 12)
            kfl.setHorizontalSpacing(20)
            kfl.setVerticalSpacing(6)
            kfl.setColumnStretch(1, 1)
            key_rows = [
                ("f", tr("Move to the next patch")),
                ("b", tr("Move back to the previous patch")),
                ("n", tr("Jump to the next unread patch")),
                (tr("click"), tr("Click a patch in the preview to jump to it")),
                ("d", tr("Finish and save when all patches are done")),
                ("Esc / q", tr("Quit without saving")),
            ]
            for row, (key, desc) in enumerate(key_rows):
                k = QLabel(key)
                k.setStyleSheet(_key_style)
                d = QLabel(desc)
                d.setStyleSheet(_plain_style)
                kfl.addWidget(k, row, 0, Qt.AlignmentFlag.AlignLeft)
                kfl.addWidget(d, row, 1, Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(key_frame)

            footnote = QLabel(tr("These instructions are always visible in the output log below."), dlg)
            footnote.setWordWrap(True)
            footnote.setStyleSheet(_dim_style)
            layout.addWidget(footnote)

        elif self._guided_refinement_active and self._strip_list:
            first = self._strip_list[0]
            n = len(self._strip_list)
            dlg.setWindowTitle(tr("Calibration Complete — Guided Refinement Ready"))

            msg = QLabel(
                tr("<b>Calibration complete. The app will guide you to each strip.</b><br><br>There are <b>{n} strip(s)</b> to re-measure. The app will automatically navigate chartread to each one — <b>you do not need to press f or b yourself.</b>").format(n=n),
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)

            hint_frame = QFrame(dlg)
            hint_frame.setStyleSheet(_frame_style)
            hfl = QVBoxLayout(hint_frame)
            hfl.setContentsMargins(16, 12, 16, 12)
            hfl.setSpacing(6)
            hdr = QLabel(tr("To identify which strip to scan:"), dlg)
            hdr.setStyleSheet("font-weight: 600; " + _plain_style)
            hfl.addWidget(hdr)
            for bullet_text in (
                tr("Watch the <b>highlighted strip</b> in the preview panel on the right."),
                tr("Or follow the <b>output field</b> below — it will name the strip."),
            ):
                b = QLabel(tr("  •  {bullet_text}").format(bullet_text=bullet_text), dlg)
                b.setWordWrap(True)
                b.setStyleSheet(_plain_style)
                hfl.addWidget(b)
            layout.addWidget(hint_frame)

            first_lbl = QLabel(
                tr("<b>First strip: {first}.</b> When it's highlighted, scan it "
                   "like this:<br><br>{how}").format(first=first, how=_how),
                dlg,
            )
            first_lbl.setTextFormat(Qt.TextFormat.RichText)
            first_lbl.setWordWrap(True)
            layout.addWidget(first_lbl)

            footnote = QLabel(
                tr("When all strips are done, the output field will tell you to press ‘d’ to finish and save."),
                dlg,
            )
            footnote.setWordWrap(True)
            footnote.setStyleSheet(_dim_style)
            layout.addWidget(footnote)

        elif self._resume_active:
            dlg.setWindowTitle(tr("Calibration Complete — Manual Re-measurement"))

            msg = QLabel(
                tr("<b>Calibration complete. You are ready to re-measure strips manually.</b><br><br>"
                "chartread is resuming from your existing measurement. Re-scan any strip "
                "to overwrite it, or scan unread strips to fill them in — follow the steps "
                "below to pick which one."),
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)

            step_frame = QFrame(dlg)
            step_frame.setStyleSheet(_frame_style)
            sfl = QGridLayout(step_frame)
            sfl.setContentsMargins(16, 12, 16, 12)
            sfl.setHorizontalSpacing(14)
            sfl.setVerticalSpacing(7)
            sfl.setColumnStretch(1, 1)
            steps = [
                ("1.", tr("Press <b>f</b> (forward) or <b>b</b> (back) until chartread shows the strip you want.")),
                ("2.", _how),
                ("3.", tr("Repeat for each strip you want to update, then press <b>d</b> to finish and save.")),
            ]
            for row, (num, text) in enumerate(steps):
                n_lbl = QLabel(num)
                n_lbl.setStyleSheet(_key_style)
                n_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
                t_lbl = QLabel(text)
                t_lbl.setWordWrap(True)
                t_lbl.setStyleSheet(_plain_style)
                sfl.addWidget(n_lbl, row, 0)
                sfl.addWidget(t_lbl, row, 1)
            layout.addWidget(step_frame)

            footnote = QLabel(
                tr("<b>n</b> jumps to the next unread strip  —  <b>Esc / q</b> quits without saving."),
                dlg,
            )
            footnote.setWordWrap(True)
            footnote.setStyleSheet(_dim_style)
            layout.addWidget(footnote)

        else:
            dlg.setWindowTitle(tr("Calibration Complete — How to Measure"))

            msg = QLabel(
                tr("<b>Calibration complete. You are ready to start measuring."
                   "</b><br><br>{how}<br><br>Then proceed stripe by stripe until "
                   "all are done.").format(how=_how),
                dlg,
            )
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setWordWrap(True)
            layout.addWidget(msg)

            key_frame = QFrame(dlg)
            key_frame.setStyleSheet(_frame_style)
            kfl = QGridLayout(key_frame)
            kfl.setContentsMargins(16, 12, 16, 12)
            kfl.setHorizontalSpacing(20)
            kfl.setVerticalSpacing(6)
            kfl.setColumnStretch(1, 1)
            key_rows = [
                ("f", tr("Move to the next stripe")),
                ("b", tr("Move back to the previous stripe")),
                ("n", tr("Jump to the next unread stripe")),
                ("d", tr("Finish and save when all stripes are done")),
                ("Esc / q", tr("Quit without saving")),
            ]
            for row, (key, desc) in enumerate(key_rows):
                k = QLabel(key)
                k.setStyleSheet(_key_style)
                d = QLabel(desc)
                d.setStyleSheet(_plain_style)
                kfl.addWidget(k, row, 0, Qt.AlignmentFlag.AlignLeft)
                kfl.addWidget(d, row, 1, Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(key_frame)

            footnote = QLabel(tr("These instructions are always visible in the output log below."), dlg)
            footnote.setWordWrap(True)
            footnote.setStyleSheet(_dim_style)
            layout.addWidget(footnote)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setObjectName("primary")
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        QApplication.instance().installEventFilter(self)

    def _on_all_stripes_done(self) -> None:
        # The pace prompt for the final strip owns the screen until it is
        # answered (#131, Knut): "Strip Read Quickly" always comes alone and
        # first, and this window follows only if the reading was kept.
        if getattr(self, "_pace_prompt_open", False):
            self._all_done_deferred = True
            return
        if getattr(self, "_skip_next_all_done", False):
            # A strip is being read again, so the chart is not finished.
            self._skip_next_all_done = False
            return
        if self._all_done_shown:
            return
        self._all_done_shown = True

        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        _ti3_path = self._ti1_path.with_suffix(".ti3") if self._ti1_path else None
        # A calibration measurement lives in the project's cal/ folder
        # (cal/calibration.ti3) rather than carrying a cal_ filename prefix.
        is_cal = (
            _ti3_path is not None
            and _ti3_path.parent.name == "cal"
            and bool(self._settings.get("calibration_mode", False))
        )

        # The chart is read: sound it now, before anything is asked (Knut,
        # #131 — the completion sound belongs to finishing the measurement, not
        # to whatever you decide to do afterwards).
        self._play_measurement_finished_once()

        # Suspend the event filter while the dialog is open so that keyboard
        # interactions with the dialog (Enter, Space, Esc) are not forwarded
        # to chartread as spurious keystrokes.
        QApplication.instance().removeEventFilter(self)

        # Verification read of a colour-managed print: a dedicated dialog that
        # never offers "Build Profile" and warns this file is verification-only.
        if self._verify_run and not is_cal and not self._guided_refinement_active:
            from PyQt6.QtWidgets import QHBoxLayout, QPushButton
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Verification Measurement — All Stripes Read"))
            dlg.setMinimumWidth(560)
            lay = QVBoxLayout(dlg)
            lay.setSpacing(16)
            lay.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(tr(
                "<b>All stripes have been read.</b><br><br>This is a "
                "<b>verification measurement</b> of a colour-managed print, so it "
                "will be saved as a separate <b>verify</b> file and is <b>not</b> "
                "for building a profile.<br><br>Click <b>Finish</b> to save it, "
                "then open it in <b>Tools ▸ Inspect a measurement</b> to check how "
                "the profile performed. Or click <b>Re-read Stripes</b> to scan a "
                "stripe again (<b>f</b>&nbsp;/&nbsp;<b>b</b> to move, <b>n</b> for "
                "the next unread, <b>d</b> when done)."), dlg)
            msg.setWordWrap(True)
            lay.addWidget(msg)

            summary = self._measurement_summary()
            if summary:
                sum_lbl = QLabel(summary, dlg)
                sum_lbl.setWordWrap(True)
                sum_lbl.setStyleSheet("color: #909090; font-size: 11px;")
                lay.addWidget(sum_lbl)
            row = QHBoxLayout()
            row.addStretch(1)
            reread = QPushButton(tr("Re-read Stripes"), dlg)
            reread.clicked.connect(dlg.reject)
            finish = QPushButton(tr("Finish"), dlg)
            finish.setObjectName("primary")
            finish.setDefault(True)
            finish.setAutoDefault(True)
            finish.clicked.connect(dlg.accept)
            row.addWidget(reread)
            row.addWidget(finish)
            lay.addLayout(row)
            tint_dialog_primary(dlg, _TAB_COLOR)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._manager.send_key("d")
                self._arm_key_watchdog()
            else:
                QApplication.instance().installEventFilter(self)
            return

        # Measurement averaging (docs/dev_averaging.md): for a normal read (not a
        # calibration or guided-refinement re-read) fold the averaging choice into
        # this dialog so there is no redundant second popup afterwards.
        if (
            self._settings.get("averaging_enabled", False)
            and not is_cal
            and not self._guided_refinement_active
        ):
            self._show_all_stripes_averaging_dialog()
            return

        dlg = QDialog(self)
        dlg.setMinimumWidth(560)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        if self._guided_refinement_active:
            n = len(self._strip_list)
            dlg.setWindowTitle(tr("Re-measurement Complete"))
            msg = QLabel(
                tr("<b>All {n} chart strip(s) have been re-measured successfully.</b><br><br>What would you like to do next?<br><br>&nbsp;&nbsp;•&nbsp; <b>Build Profile</b> — saves the measurement and takes you straight to the Build Profile tab to create your updated ICC profile.<br><br>&nbsp;&nbsp;•&nbsp; <b>Continue Measuring Manually</b> — keeps chartread running so you can scan additional strips yourself. You will have <b>full manual control</b>: use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move between strips, <b>n</b> to jump to the next unread one, and <b>d</b> when you are done. The automatic strip navigation is switched off for the rest of this session.").format(n=n),
                dlg,
            )
        elif is_cal:
            dlg.setWindowTitle(tr("Calibration Measurement Complete"))
            msg = QLabel(
                tr("<b>All stripes of your calibration chart have been read successfully.</b><br><br>"
                "The measurement data has been saved. The next step is to turn it into a "
                "<b>calibration file (.cal)</b> — click <b>Create Calibration File</b> to go "
                "directly to the <b>4. Calibration &amp; Profiling</b> tab, where the file "
                "path is already filled in and ready to go.<br><br>"
                "If you would like to re-read any stripe first, click <b>Re-read Stripes</b>. "
                "Use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move forward and back between stripes, "
                "<b>n</b> to jump to the next unread stripe, and press <b>d</b> when you "
                "are done.<br><br>"
                "<span style='color:#909090;'>These instructions are always visible in "
                "the output log below.</span>"),
                dlg,
            )
        elif self._spot_session:
            dlg.setWindowTitle(tr("All Patches Read"))
            msg = QLabel(
                tr("<b>All patches have been read successfully.</b><br><br>"
                "Click <b>Build Profile</b> to finalise the measurement and go directly "
                "to the Build Profile tab — the next and final step.<br><br>"
                "If you would like to re-read any patch first, click <b>Re-read Patches</b>. "
                "Use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move forward and back between patches, "
                "<b>n</b> to jump to the next unread patch, click a patch in the preview to "
                "jump to it, and press <b>d</b> when you are done.<br><br>"
                "<span style='color:#909090;'>These instructions are always visible in "
                "the output log below.</span>"),
                dlg,
            )
        else:
            dlg.setWindowTitle(tr("All Stripes Read"))
            msg = QLabel(
                tr("<b>All stripes have been read successfully.</b><br><br>"
                "Click <b>Build Profile</b> to finalise the measurement and go directly "
                "to the Build Profile tab — the next and final step.<br><br>"
                "If you would like to re-read any stripe first, click <b>Re-read Stripes</b>. "
                "Use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move forward and back between stripes, "
                "<b>n</b> to jump to the next unread stripe, and press <b>d</b> when you "
                "are done.<br><br>"
                "<span style='color:#909090;'>These instructions are always visible in "
                "the output log below.</span>"),
                dlg,
            )

        msg.setWordWrap(True)
        layout.addWidget(msg)

        summary = self._measurement_summary()
        if summary:
            from PyQt6.QtWidgets import QLabel as _QL
            sum_lbl = _QL(summary, dlg)
            sum_lbl.setWordWrap(True)
            sum_lbl.setStyleSheet("color: #909090; font-size: 11px;")
            layout.addWidget(sum_lbl)

        # Opt-in scanner-target checkbox — offered for a profiling read of an
        # engine chart (not calibration), so the user can later profile a scanner
        # from this same chart (#97). Ticking it flags the run; the .cht/.cie are
        # (re)built from the measurement once it's finalised.
        scanner_cb = None
        scanner_run = (Run.for_dir(self._ti1_path.parent)
                       if self._ti1_path is not None else None)
        if (scanner_run is not None and not is_cal
                and has_scanner_geometry(scanner_run.chart_channels_json)):
            row, scanner_cb = make_scanner_target_row(
                dlg, scanner_run.load_meta().scanner_target_enabled)
            layout.addWidget(row)

        # Manual button row so Re-read / Continue sits on the left and the
        # primary "Build Profile / Create Calibration File" sits on the right —
        # QDialogButtonBox auto-orders by platform (Accept-left on Windows),
        # which doesn't match the averaging-on dialog's layout.
        from PyQt6.QtWidgets import QHBoxLayout, QPushButton

        if is_cal and not self._guided_refinement_active:
            accept_label = tr("Create Calibration File →")
        else:
            # Knut (#131): it only takes you to the tab — the profile is still
            # built there, by you. The name has to say that.
            accept_label = tr("Go to Build Profile Tab →")
        if self._guided_refinement_active:
            cont_label = "Continue Measuring Manually"
        elif self._spot_session:
            cont_label = "Re-read Patches"
        else:
            cont_label = "Re-read Stripes"

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cont_btn = QPushButton(cont_label, dlg)
        cont_btn.clicked.connect(dlg.reject)
        # Knut (#131): a way to keep the measurement and go nowhere.
        close_btn = QPushButton(tr("Close"), dlg)
        close_btn.setToolTip(tr(
            "Keeps your measurement and closes this window without going "
            "anywhere. You can build the profile whenever you like."))
        closed = {"chosen": False}
        close_btn.clicked.connect(lambda: (closed.__setitem__("chosen", True),
                                           dlg.reject()))
        build_btn = QPushButton(accept_label, dlg)
        build_btn.setObjectName("primary")
        build_btn.setToolTip(tr(
            "Saves the measurement and opens the Build Profile tab. The profile "
            "is not built yet — press “Build Profile” there when your settings "
            "are how you want them."))
        build_btn.setDefault(True)
        build_btn.setAutoDefault(True)
        build_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(cont_btn)
        btn_row.addWidget(close_btn)
        btn_row.addWidget(build_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        # Persist the scanner-target preference regardless of Re-read vs Build —
        # it's a per-chart choice, applied when the .ti3 is finalised.
        if scanner_cb is not None and scanner_run is not None:
            meta = scanner_run.load_meta()
            if meta.scanner_target_enabled != scanner_cb.isChecked():
                meta.scanner_target_enabled = scanner_cb.isChecked()
                scanner_run.save_meta(meta)
        if accepted or closed["chosen"]:
            # Close keeps the measurement exactly like Build does — it only
            # declines the trip to the Build Profile tab.
            self._auto_proceed = accepted
            if closed["chosen"]:
                self._log.appendPlainText(
                    "\n" + tr("→ Your measurement is saved. When you want the "
                              "profile, go to the “4. Build Profile” tab and "
                              "press “Build Profile”."))
            self._manager.send_key("d")
            self._arm_key_watchdog()
            # Event filter stays off — chartread will finish momentarily.
        else:
            if self._guided_refinement_active:
                # Hand back full keyboard control; disable auto-navigation.
                self._guided_refinement_active = False
                self._manager.set_guided_strips([])
            QApplication.instance().installEventFilter(self)

    def _show_all_stripes_averaging_dialog(self) -> None:
        """The 'All Stripes Read' dialog when measurement averaging is on.

        First read of a chart → Re-read Stripes / Measure again to average /
        Build Profile. Mid-set (≥1 read already saved) → Use last read only /
        Measure again to average / Average all reads & build. The chosen action is
        stored in ``_pending_avg_action`` so :meth:`_on_measure_done` can act on it
        once chartread has written the final .ti3 (it isn't final while chartread
        is still running). 'Re-read Stripes' instead keeps chartread running for
        manual single-strip re-reads, exactly like the classic dialog.
        """
        from PyQt6.QtWidgets import (
            QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
        )

        self._play_measurement_finished_once()   # read is done — sound it now

        prior = (
            Run.for_dir(self._ti1_path.parent).reads()
            if self._ti1_path is not None else []
        )
        in_set  = self._averaging_active and len(prior) >= 1
        n_total = len(prior) + 1   # prior saved reads + this just-finished one

        dlg = QDialog(self)
        dlg.setMinimumWidth(560)
        dlg.setWindowTitle(tr("All Stripes Read"))
        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        if in_set:
            body = tr(
                "<b>All stripes read — {n} reads of this chart are now saved.</b>"
                "<br><br>"
                "Combining repeated reads of the same chart averages out instrument "
                "noise and can improve profile accuracy.<br><br>"
                "&nbsp;&nbsp;•&nbsp; <b>Average all reads &amp; build</b> — combine all "
                "{n} reads into one measurement, then continue to Build Profile.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Measure again to average</b> — read the whole "
                "chart once more and add it to the set.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Use last read only</b> — build from this most "
                "recent read and ignore the others.<br><br>"
                "<span style='color:#909090;'>After <b>Measure again to average</b> the "
                "instrument is set up again — this can take a few seconds and may ask you "
                "to recalibrate before the next read starts, so a brief pause here is "
                "normal.</span>"
            ).format(n=n_total)
        else:
            body = tr(
                "<b>All stripes have been read successfully.</b><br><br>"
                "&nbsp;&nbsp;•&nbsp; <b>Build Profile</b> — finalise the measurement and "
                "go to the Build Profile tab.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Measure again to average</b> — read the whole chart "
                "once more; the reads are averaged together to reduce instrument noise "
                "(saved as …_average).<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Re-read Stripes</b> — re-scan individual strips into "
                "this same measurement. Use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move, "
                "<b>n</b> for the next unread stripe, and <b>d</b> when done.<br><br>"
                "<span style='color:#909090;'>After <b>Measure again to average</b> the "
                "instrument is set up again — this can take a few seconds and may ask you "
                "to recalibrate before the next read starts, so a brief pause here is "
                "normal.</span>"
            )
        msg = QLabel(body, dlg)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        summary = self._measurement_summary()
        if summary:
            from PyQt6.QtWidgets import QLabel as _QL
            sum_lbl = _QL(summary, dlg)
            sum_lbl.setWordWrap(True)
            sum_lbl.setStyleSheet("color: #909090; font-size: 11px;")
            layout.addWidget(sum_lbl)

        method_combo = None
        if in_set:
            method_row = QHBoxLayout()
            # NoScrollComboBox so the body picks up the per-theme white input
            # background in light mode (plain QComboBox keeps the surface color
            # — see _input_bg_qss in ui/widgets.py) and the wheel doesn't change
            # the selection on accidental page-scroll.
            method_combo = NoScrollComboBox(dlg)
            method_combo.addItem(tr("Mean (recommended)"), "mean")
            method_combo.addItem(tr("Median — needs 3+ reads"), "median")
            saved = self._settings.get("average_method", "mean")
            method_combo.setCurrentIndex(max(0, method_combo.findData(saved)))
            method_combo.setToolTip(
                tr("Mean averages every read. Median rejects a single outlier read, "
                "but only differs from the mean with three or more reads.")
            )
            method_row.addWidget(QLabel(tr("Combine method:"), dlg))
            method_row.addWidget(method_combo, 1)
            layout.addLayout(method_row)

        # Opt-in scanner-target checkbox (engine charts only) — same as the
        # classic dialog; the averaging path is always a profiling read.
        scanner_cb = None
        scanner_run = (Run.for_dir(self._ti1_path.parent)
                       if self._ti1_path is not None else None)
        if (scanner_run is not None
                and has_scanner_geometry(scanner_run.chart_channels_json)):
            row, scanner_cb = make_scanner_target_row(
                dlg, scanner_run.load_meta().scanner_target_enabled)
            layout.addWidget(row)

        choice = {"action": "average" if in_set else "build"}

        def _pick(action: str) -> None:
            choice["action"] = action
            dlg.accept()

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        if in_set:
            last_btn = QPushButton(tr("Use last read only"), dlg)
            last_btn.clicked.connect(lambda: _pick("use_last"))
            again_btn = QPushButton(tr("Measure again to average"), dlg)
            again_btn.clicked.connect(lambda: _pick("again"))
            avg_btn = QPushButton(tr("Average all reads && build →"), dlg)
            avg_btn.setObjectName("primary")
            avg_btn.clicked.connect(lambda: _pick("average"))
            for b in (last_btn, again_btn, avg_btn):
                btn_row.addWidget(b)
        else:
            reread_btn = QPushButton(tr("Re-read Stripes"), dlg)
            reread_btn.clicked.connect(lambda: _pick("reread"))
            again_btn = QPushButton(tr("Measure again to average"), dlg)
            again_btn.clicked.connect(lambda: _pick("again"))
            close_btn = QPushButton(tr("Close"), dlg)
            close_btn.setToolTip(tr(
                "Keeps your measurement and closes this window without going "
                "anywhere. You can build the profile whenever you like."))
            close_btn.clicked.connect(lambda: _pick("close"))
            # Knut (#131): "Build Profile" read as though it would build the
            # profile there and then — it only takes you to the tab, where you
            # still press Build Profile yourself. The name now says that.
            build_btn = QPushButton(tr("Go to Build Profile Tab →"), dlg)
            build_btn.setObjectName("primary")
            build_btn.setToolTip(tr(
                "Saves the measurement and opens the Build Profile tab. The "
                "profile is not built yet — press “Build Profile” there when "
                "your settings are how you want them."))
            build_btn.clicked.connect(lambda: _pick("build"))
            for b in (reread_btn, again_btn, close_btn, build_btn):
                btn_row.addWidget(b)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()

        if scanner_cb is not None and scanner_run is not None:
            meta = scanner_run.load_meta()
            if meta.scanner_target_enabled != scanner_cb.isChecked():
                meta.scanner_target_enabled = scanner_cb.isChecked()
                scanner_run.save_meta(meta)

        action = choice["action"]
        method = "mean"
        if method_combo is not None:
            method = method_combo.currentData() or "mean"
            self._settings.set("average_method", method)

        if action == "reread":
            # Keep chartread running for manual single-strip re-reads, exactly like
            # the classic "Re-read Stripes" path; the event filter must go back on.
            QApplication.instance().installEventFilter(self)
            return

        # build / again / average / use_last: finish this read. _on_measure_done
        # promotes the file and acts on the decision once the .ti3 is written.
        self._pending_avg_action = action
        self._pending_avg_method = method
        self._manager.send_key("d")
        self._arm_key_watchdog()
        # Event filter stays off — chartread will finish momentarily.

    def _finalize_verification(self, ti3: Path) -> None:
        """Tag a verification read as verify-only ('<name>-verify.ti3' + marker)
        and file it in a dated verification-run folder so a profile's monthly
        verifications accrue as history (#130), then offer to open it in the
        measurement inspector — never build a profile."""
        import shutil

        from core.file_manager import VERIFICATIONS_DIRNAME
        try:
            marked = mark_verification_ti3(ti3)          # <name>-verify.ti3
            # Resolve the run whether the loaded chart is the run's profiling
            # chart (run root) or its shared verify chart (in verifications/).
            parent = marked.parent
            run = (Run.for_dir(parent.parent)
                   if parent.name == VERIFICATIONS_DIRNAME
                   else Run.for_dir(parent))
            # Honour the shared target: overwrite a chosen dated verification, or
            # start a new one (the default). New verifications never overwrite a
            # prior date, so the history accrues.
            ctl = getattr(self, "_target_ctl", None)
            vid = (ctl.target.verification_id
                   if (ctl is not None and ctl.target.is_verification()) else "")
            verification = (run.verification(vid) if vid else run.new_verification())
            verification.ensure_dir()
            dst = verification.measurement_ti3           # verifications/<date>/<name>-verify.ti3
            shutil.move(str(marked), str(dst))
        except OSError as exc:
            self._log.appendPlainText(f"\n[ERROR] Could not save verification file: {exc}")
            return
        self._log.appendPlainText(
            "\n" + tr("[OK] Verification measurement saved.")
            + f"\nSaved: {dst}\n\n"
            + tr("→ This file is for verification only — do not build a profile "
                 "from it. Open it in Tools ▸ Inspect a measurement to check the "
                 "profile."))

        from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Verification Measurement Saved"))
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)
        msg = QLabel(tr(
            "<b>Your verification measurement has been saved</b> as "
            "<code>{name}</code>.<br><br>This file checks a colour-managed print "
            "against a profile — <b>don't build a profile from it</b>. Open it in "
            "<b>Tools ▸ Inspect a measurement</b> (it opens in Verify mode "
            "automatically) to see the residual cast and colour accuracy.").format(
                name=dst.name), dlg)
        msg.setWordWrap(True)
        lay.addWidget(msg)
        row = QHBoxLayout()
        row.addStretch(1)
        close_btn = QPushButton(tr("Close"), dlg)
        close_btn.clicked.connect(dlg.reject)
        open_btn = QPushButton(tr("Open in measurement inspector"), dlg)
        open_btn.setObjectName("primary")
        open_btn.setDefault(True)
        open_btn.clicked.connect(dlg.accept)
        row.addWidget(close_btn)
        row.addWidget(open_btn)
        lay.addLayout(row)
        tint_dialog_primary(dlg, _TAB_COLOR)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
            insp = Ti3InfoDialog(self._runner, self._settings, self)
            insp.load_measurement(dst)
            insp.exec()

    def _on_measure_done(self, code: int) -> None:
        # #131: leave measurement mode. Any completion sound (played via
        # measure_finished, below) is exempt from the at-rest gate, so it still
        # fires; per-patch/strip sounds can no longer sound outside a read.
        if getattr(self, "_sound", None) is not None:
            self._sound.disarm()
        self._preview.highlight_stripe(-1)
        self._preview.set_bidirectional(False)
        # #126: click-to-jump only lives while an engine session runs; the
        # split-patch overlay stays so the finished chart can be inspected.
        self._preview.set_stripe_click_enabled(False)
        # #126 spot mode: drop the current-patch highlight + click-to-jump; the
        # split-patch overlay stays so the finished chart can be inspected.
        self._preview.highlight_patch(-1, None)
        self._preview.set_patch_click_enabled(False)
        self._spot_click_on = False
        self._preview.set_notice(None)
        # The view controls live in the always-visible "Live preview" group now
        # (not hidden between reads); only the click-a-strip tip is transient.
        self._m_engine_tip.setVisible(False)
        self._key_watchdog.stop()
        self.measurement_active.emit(False)
        QApplication.instance().removeEventFilter(self)
        self._set_settings_enabled(True)
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

        if self._usb_claimed_by_vm:
            self._usb_claimed_by_vm = False
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Instrument Not Accessible"))
            dlg.setMinimumWidth(500)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(
                tr("<b>Your measurement device could not be opened — it appears to be "
                "connected to a virtual machine.</b><br><br>"
                "When a device is assigned to a VM (Parallels, VMware, VirtualBox, etc.), "
                "the host operating system cannot access it at the same time.<br><br>"
                "To fix this:<br>"
                "&nbsp;&nbsp;1. In your VM software, disconnect the device from the "
                "virtual machine<br>"
                "&nbsp;&nbsp;2. Reconnect the USB cable if needed<br>"
                "&nbsp;&nbsp;3. Press <b>Start Measurement</b> again"),
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        if self._no_instrument:
            self._no_instrument = False
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("No Instrument Found"))
            dlg.setMinimumWidth(460)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            _conn_bullet = (
                tr("&nbsp;&nbsp;• connected to your Windows PC via USB<br>")
                if sys.platform == "win32" else
                tr("&nbsp;&nbsp;• connected to your Mac via USB<br>")
            )
            _driver_hint = (
                tr("<br>If the instrument is connected but still not found, make sure the "
                   "Argyll WinUSB driver is installed for your device (use Argyll's "
                   "ArgyllInstallers tool or Zadig). See the Argyll documentation for details.")
                if sys.platform == "win32" else ""
            )
            msg = QLabel(
                tr("<b>No measurement instrument was detected.</b><br><br>"
                   "Please make sure your instrument is:<br>")
                + _conn_bullet +
                tr("&nbsp;&nbsp;• switched on<br>"
                   "&nbsp;&nbsp;• not in use by another application<br><br>"
                   "Once the instrument is ready, press <b>Start Measurement</b> again.")
                + _driver_hint,
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        if self._device_busy:
            self._device_busy = False
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Instrument Not Available"))
            dlg.setMinimumWidth(480)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(
                tr("<b>The instrument could not be opened — it is already in use by "
                "another process.</b><br><br>"
                "This usually happens when a previous measurement session was not "
                "stopped properly before closing the app. ChromIQ automatically "
                "tries to free the device when starting a new measurement.<br><br>"
                "Please click OK and then press <b>Start Measurement</b> again."),
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        if self._instrument_disconnected:
            self._instrument_disconnected = False
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Instrument Disconnected"))
            dlg.setMinimumWidth(460)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(
                tr("<b>The measurement instrument was disconnected.</b><br><br>"
                "The measurement has been stopped automatically. Please check "
                "the USB connection, reconnect your instrument, and start a "
                "new measurement."),
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        # Group B: friendly terminal dialogs for chartread startup failures.
        # The communications/init failures share a dialog body — the only
        # difference is which Argyll error string is shown.
        _b_init_msg = self._coms_init_failed_msg or self._inst_init_failed_msg
        if _b_init_msg:
            self._coms_init_failed_msg = None
            self._inst_init_failed_msg = None
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Instrument Failed to Initialize"))
            dlg.setMinimumWidth(480)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(
                tr("<b>The instrument could not be initialised.</b><br><br>Argyll reported: <i>{_b_init_msg}</i><br><br>Try the following:<br>&nbsp;&nbsp;• Unplug and replug the USB cable<br>&nbsp;&nbsp;• Make sure the instrument is switched on<br>&nbsp;&nbsp;• Close any other application that might be using it<br><br>Then press <b>Start Measurement</b> again.").format(_b_init_msg=_b_init_msg),
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        if self._instrument_wrong_type:
            cap = self._instrument_wrong_type
            self._instrument_wrong_type = None
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Instrument Type Mismatch"))
            dlg.setMinimumWidth(480)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(
                tr("<b>This instrument cannot measure in {cap} mode.</b><br><br>ChromIQ measures printed test charts, which need a <b>reflection-capable</b> instrument (e.g. i1Pro, i1Pro 2, i1Pro 3, ColorMunki, SpectroScan).<br><br>Display-only colorimeters (e.g. i1Display) cannot read paper. Connect a reflection-capable instrument and try again.").format(cap=cap),
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        if self._ccmx_load_failed_msg:
            err = self._ccmx_load_failed_msg
            self._ccmx_load_failed_msg = None
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Correction File Failed to Load"))
            dlg.setMinimumWidth(500)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(
                tr("<b>The colorimeter correction file could not be applied.</b><br><br>Argyll reported: <i>{err}</i><br><br>Check the path in <b>Preferences → Argyll Options</b>, or remove the CCMX / CCSS reference from the extra-args field and try again.").format(err=err),
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        if self._mode_set_failed_msg:
            err = self._mode_set_failed_msg
            self._mode_set_failed_msg = None
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Instrument Mode Rejected"))
            dlg.setMinimumWidth(480)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(
                tr("<b>The instrument refused the requested measurement mode.</b><br><br>Argyll reported: <i>{err}</i><br><br>Check the instrument-specific flags in your settings (high-res, UV mode, scan tolerance, etc.) and try again.").format(err=err),
                dlg,
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dlg.accept)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _TAB_COLOR)
            dlg.exec()
            return

        # chartread exits non-zero even on a clean 'd' (done) completion.
        # Only count the .ti3 as valid if it was actually written during this run —
        # a stale file from a previous session must not mask a fresh failure.
        ti3 = self._ti1_path.with_suffix(".ti3") if self._ti1_path else None
        if ti3 is not None and ti3.exists():
            ti3_exists = (
                self._ti3_mtime_before is None          # file didn't exist before → fresh
                or ti3.stat().st_mtime > self._ti3_mtime_before
            )
        else:
            ti3_exists = False
        failed = self._measure_failed or (code != 0 and not ti3_exists)
        self._measure_failed = False

        is_cal = (
            ti3 is not None
            and ti3.parent.name == "cal"
            and bool(self._settings.get("calibration_mode", False))
        )
        # Verification read: rename + tag the file as verify-only and stop —
        # never emit measure_finished or advance to Build Profile.
        if self._verify_run and ti3_exists and not failed and not is_cal:
            self._verify_run = False
            self._finalize_verification(ti3)
            return
        if failed:
            self._log.appendPlainText("\n[ERROR] Measurement failed — see output above.")
        elif ti3_exists and not self._all_done_shown:
            # chartread wrote a .ti3 but never emitted "ALL ROWS READ" —
            # the user pressed 'd' (Save Partial & Quit, or manually in the
            # log) with some patches still unread. Refresh the resume
            # checkbox visibility and auto-tick it so the next click on the
            # Start button (now relabelled "Continue Measurement") resumes
            # chartread with -r against this partial file.
            self._update_resume_availability()
            cb = self._resume_cb if self._current_mode() == "guided" else self._m_resume_cb
            if cb.isVisible():
                cb.setChecked(True)
            self._log.appendPlainText(
                "\n" + tr("[INFO] Measurement was interrupted — partial readings saved.")
                + f"\nSaved: {ti3}\n\n"
                + tr("→ Press Continue Measurement to resume where you left off, "
                     "or untick 'Refine / resume existing measurement (-r)' to start over.")
            )
            self.measure_finished.emit(ti3)
        elif ti3_exists and (is_cal or self._guided_refinement_active):
            # Calibration and guided-refinement reads keep their dedicated flow.
            if is_cal:
                next_step = tr("→ Next step: go to the '4. Calibration & Profiling' tab to create your calibration file.")
            else:
                next_step = tr("→ Next step: go to the '4. Build Profile' tab to create your ICC profile.")
            self._log.appendPlainText(
                "\n" + tr("[OK] Measurement complete.")
                + f"\nSaved: {ti3}\n\n"
                + next_step
            )
            self.measure_finished.emit(ti3)
            if self._auto_proceed:
                self.proceed_to_profile.emit()
        elif ti3_exists and self._settings.get("averaging_enabled", False):
            # Normal full read, averaging enabled (docs/dev_averaging.md). The
            # "All Stripes Read" dialog already captured the user's choice in
            # _pending_avg_action; act on it now that chartread has written the
            # final .ti3. If nothing was captured (the all-rows-read dialog never
            # fired — e.g. detection miss), fall back to the post-process dialog.
            if self._pending_avg_action is not None:
                action = self._pending_avg_action
                method = self._pending_avg_method
                self._pending_avg_action = None
                current, reads = self._promote_completed_read(ti3)
                self._apply_completion_action(ti3, current, reads, action, method)
            else:
                self._handle_measure_complete(ti3)
        elif ti3_exists:
            # Normal full read, averaging off → classic behaviour: log the result
            # and proceed straight to Build Profile (mirrors the cal/refinement
            # branch above, minus the dedicated next-step wording).
            self._log.appendPlainText(
                "\n" + tr("[OK] Measurement complete.")
                + f"\nSaved: {ti3}\n\n"
                + tr("→ Next step: go to the '4. Build Profile' tab to create your ICC profile.")
            )
            self.measure_finished.emit(ti3)
            if self._auto_proceed:
                self.proceed_to_profile.emit()
        else:
            # chartread exited cleanly but wrote no fresh .ti3 — e.g. the user
            # aborted at the calibration prompt (Esc/Q, or by closing the
            # "Calibration Required" dialog). Don't claim success or a saved
            # file that doesn't exist.
            self._log.appendPlainText(
                "\n" + tr("[INFO] Measurement stopped — no measurement (.ti3) file was created.")
            )
        self._auto_proceed = False
        self._log.ensureCursorVisible()

    def _maybe_build_scanner_target(self, ti3: Path) -> None:
        """When the chart is flagged for it (the 'All Stripes Read' checkbox),
        (re)build its ``.cht`` + ``.cie`` from the just-finalised measurement so
        the scanner target always reflects the latest read (#97).

        Best-effort: an engine-only, opt-in feature that must never disrupt the
        profiling flow. Silently skips non-engine charts, un-flagged runs, and
        partial/mismatched reads (which raise :class:`ScaninTargetError`)."""
        try:
            run = Run.for_dir(Path(ti3).parent)
            if not run.load_meta().scanner_target_enabled:
                return
            if not has_scanner_geometry(run.chart_channels_json):
                return
            from workflow.scanin_target import (
                ScaninTargetError, build_scanin_target_from_paths)
            try:
                res = build_scanin_target_from_paths(
                    run.chart_channels_json, run.measurement_ti3,
                    run.dir / run.stem)
            except ScaninTargetError:
                return   # e.g. a partial read → not every patch measured yet
            self._log.appendPlainText(
                "\n" + tr("[OK] Recognition files (.cht + .cie) saved for {n} "
                          "patches — scan or photograph the printed chart, then "
                          "use Tools ▸ Build profile with scanner or camera."
                          ).format(n=res.n_patches))
        except Exception:  # noqa: BLE001 — never let this break measurement
            log.exception("Scanner-target build failed (non-fatal)")

    # ------------------------------------------------------------------
    # Read again & average  (docs/dev_averaging.md)
    # ------------------------------------------------------------------

    def _handle_measure_complete(self, ti3: Path) -> None:
        """A normal full read finished without a pre-made choice (Manual mode, or
        the 'All Stripes Read' dialog never fired). Promote the read, then ask via
        the post-process completion dialog and carry out the answer."""
        current, reads = self._promote_completed_read(ti3)
        action, method = self._show_completion_dialog(current, reads)
        self._apply_completion_action(ti3, current, reads, action, method)

    def _promote_completed_read(self, ti3: Path) -> tuple[Path, list[Path]]:
        """If an averaging set is active, move this read into the run's
        ``reads/readN.ti3`` slot and return (saved_path, all_reads). Otherwise
        leave the file in place and return (ti3, [])."""
        run = Run.for_dir(ti3.parent)   # ti3 == runs/<id>/chart.ti3
        if self._averaging_active:
            # Save this fresh read as the next read in the current set.
            try:
                current = run.promote_measurement_to_read()
            except (OSError, FileNotFoundError) as exc:
                log.warning("Could not save read variant: %s", exc)
                current = ti3
            self._log.appendPlainText(f"\n[OK] Read saved: reads/{current.name}")
            reads = run.reads()
        else:
            # A standalone read. Ignore any reads/ left over from an earlier
            # session — opting into averaging below starts a clean set.
            current = ti3
            reads = []
            self._log.appendPlainText(f"\n[OK] Measurement complete.\nSaved: {current}")
        return current, reads

    def _apply_completion_action(
        self, ti3: Path, current: Path, reads: list[Path], action: str, method: str
    ) -> None:
        """Carry out the chosen averaging action.

        ``action`` ∈ {again, average, use_last, continue, build}; the latter three
        all mean "stop and build from ``current``".
        """
        if action == "again":
            if not self._averaging_active:
                # Begin a fresh averaging set: discard any stale reads/, then
                # move this first read into reads/read1.ti3 so the next read
                # lands beside it as reads/read2.ti3.
                run = Run.for_dir(ti3.parent)
                run.clear_reads()
                try:
                    first = run.promote_measurement_to_read()
                    self._log.appendPlainText(f"[INFO] First read saved as reads/{first.name}")
                except (OSError, FileNotFoundError) as exc:
                    log.warning("Could not save first read variant: %s", exc)
                self._averaging_active = True
            QTimer.singleShot(0, self._start_averaging_read)
            return

        self._averaging_active = False
        if action == "average" and len(reads) >= 2:
            self._run_average_and_proceed(ti3, reads, method)
            return

        # "continue" / "build" (single read) or "use_last" (last read of a set).
        self.measure_finished.emit(current)
        if action == "close":
            # Knut (#131): keep the measurement, go nowhere. The profile can be
            # built whenever the user likes.
            self._log.appendPlainText(
                "\n" + tr("→ Your measurement is saved. When you want the "
                          "profile, go to the “4. Build Profile” tab and press "
                          "“Build Profile”."))
            return
        self.proceed_to_profile.emit()


    def _show_completion_dialog(
        self, current: Path, reads: list[Path]
    ) -> tuple[str, str]:
        """Return (action, method). action ∈ {continue, again, use_last, average}."""
        from PyQt6.QtWidgets import (
            QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
        )
        n_reads = len(reads)

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setMinimumWidth(580)
        dlg.setWindowTitle(tr("Measurement Complete"))
        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        if n_reads >= 2:
            body = tr(
                "<b>Measurement complete — {n} reads of this chart are saved.</b>"
                "<br><br>"
                "Combining repeated reads of the same chart averages out instrument "
                "noise and can improve profile accuracy.<br><br>"
                "&nbsp;&nbsp;•&nbsp; <b>Average all reads &amp; build</b> — combine all "
                "{n} reads into one measurement, then continue to Build Profile.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Use last read only</b> — build from the most "
                "recent read and ignore the others.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Measure again</b> — read the chart once more and "
                "add it to the set."
            ).format(n=n_reads)
        else:
            body = tr(
                "<b>Measurement complete — your readings have been saved.</b><br><br>"
                "Reading the same chart a second time and averaging the two results "
                "reduces instrument noise and can improve profile accuracy.<br><br>"
                "&nbsp;&nbsp;•&nbsp; <b>Go to Build Profile Tab</b> — use this single "
                "measurement as it is, and open the Build Profile tab. The profile "
                "is built there, when you press <i>Build Profile</i>.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Measure again to average</b> — read the same "
                "chart once more; the results will be averaged together.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Close</b> — keep this measurement and go "
                "nowhere; you can build the profile whenever you like."
            )
        msg = QLabel(body, dlg)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        method_combo = None
        if n_reads >= 2:
            method_row = QHBoxLayout()
            # NoScrollComboBox: per-widget input-bg QSS (white in light mode) +
            # wheel-scroll guard. See _input_bg_qss in ui/widgets.py.
            method_combo = NoScrollComboBox(dlg)
            method_combo.addItem(tr("Mean (recommended)"), "mean")
            method_combo.addItem(tr("Median — needs 3+ reads"), "median")
            saved = self._settings.get("average_method", "mean")
            method_combo.setCurrentIndex(max(0, method_combo.findData(saved)))
            method_combo.setToolTip(
                tr("Mean averages every read. Median rejects a single outlier read, "
                "but only differs from the mean with three or more reads.")
            )
            method_row.addWidget(QLabel(tr("Combine method:"), dlg))
            method_row.addWidget(method_combo, 1)
            layout.addLayout(method_row)

        choice = {"action": "use_last" if n_reads >= 2 else "continue"}

        def _pick(action: str) -> None:
            choice["action"] = action
            dlg.accept()

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        if n_reads >= 2:
            again_btn = QPushButton(tr("Measure again"), dlg)
            again_btn.clicked.connect(lambda: _pick("again"))
            last_btn = QPushButton(tr("Use last read only"), dlg)
            last_btn.clicked.connect(lambda: _pick("use_last"))
            avg_btn = QPushButton(tr("Average all reads && build →"), dlg)
            avg_btn.setObjectName("primary")
            avg_btn.clicked.connect(lambda: _pick("average"))
            for b in (again_btn, last_btn, avg_btn):
                btn_row.addWidget(b)
        else:
            again_btn = QPushButton(tr("Measure again to average"), dlg)
            again_btn.clicked.connect(lambda: _pick("again"))
            close_btn = QPushButton(tr("Close"), dlg)
            close_btn.setToolTip(tr(
                "Keeps your measurement and closes this window without going "
                "anywhere. You can build the profile whenever you like."))
            close_btn.clicked.connect(lambda: _pick("close"))
            cont_btn = QPushButton(tr("Go to Build Profile Tab →"), dlg)
            cont_btn.setObjectName("primary")
            cont_btn.setToolTip(tr(
                "Saves the measurement and opens the Build Profile tab. The "
                "profile is not built yet — press “Build Profile” there when "
                "your settings are how you want them."))
            cont_btn.clicked.connect(lambda: _pick("continue"))
            for b in (again_btn, close_btn, cont_btn):
                btn_row.addWidget(b)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()

        method = "mean"
        if method_combo is not None:
            method = method_combo.currentData() or "mean"
            self._settings.set("average_method", method)
        return choice["action"], method

    def _start_averaging_read(self) -> None:
        """Re-run a fresh, full read of the same chart for the averaging set."""
        if self._ti1_path is None:
            return
        if self._runner.is_running:
            QTimer.singleShot(200, self._start_averaging_read)
            return
        # Force a clean full read — never resume/refine the previous pass.
        cb = self._resume_cb if self._current_mode() == "guided" else self._m_resume_cb
        if cb.isChecked():
            cb.setChecked(False)
        self._on_start()

    def _run_average_and_proceed(
        self, base: Path, reads: list[Path], method: str
    ) -> None:
        # The averaged result IS the canonical measurement (chart.ti3); the
        # per-read snapshots stay in reads/ for diagnostics.
        out = Run.for_dir(base.parent).measurement_ti3
        self._log.appendPlainText(
            f"\n[INFO] Averaging {len(reads)} reads → {out.name} …"
        )

        def _on_avg_finish(result: Path | None) -> None:
            if result is None:
                fail = self._avg_runner.primary_failure()
                detail = fail[1] if fail else tr("see the output log above.")
                self._log.appendPlainText(f"[ERROR] Averaging failed — {detail}")
                self._show_average_failed_dialog(detail)
                return
            self._log.appendPlainText(
                tr("[OK] Averaged measurement saved: {name}").format(name=result.name)
                + "\n" + tr("→ Next step: go to the '4. Build Profile' tab to create your ICC profile.")
            )
            self.measure_finished.emit(result)
            self.proceed_to_profile.emit()

        self._avg_runner.run(
            AverageParams(inputs=reads, output=out, method=method),
            on_line=self._on_log_line,
            on_finish=_on_avg_finish,
        )

    def _show_average_failed_dialog(self, detail: str) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Averaging Failed"))
        dlg.setMinimumWidth(500)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)
        msg = QLabel(
            "<b>The reads could not be averaged.</b><br><br>"
            + detail
            + "<br><br>Your individual reads are still saved — you can continue "
            "from the Build Profile tab using one of them.",
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)
        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            sent = True
            if key == Qt.Key.Key_Escape:
                self._manager.send_key("\x1b")
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._manager.send_key("\r")
            elif key == Qt.Key.Key_Space:
                self._manager.send_key(" ")
            elif key == Qt.Key.Key_Left:
                self._manager.send_key("\x1b[D")
            elif key == Qt.Key.Key_Right:
                self._manager.send_key("\x1b[C")
            else:
                text = event.text()
                if text:
                    self._manager.send_key(text)
                else:
                    sent = False
            if sent:
                self._arm_key_watchdog()
            return True   # consume — don't let widgets act on it
        return False

    def _on_stripe_changed(self, strip_id: str) -> None:
        self._log.appendPlainText(f"[→ strip {strip_id}]")
        self._log.ensureCursorVisible()
        letter = "".join(c for c in strip_id if c.isalpha()).upper()
        if not letter:
            return
        # A failed strip reports no data, so this is the only way to name it in
        # the reading-times panel (#131).
        self._current_strip_letter = letter
        if not self._page_stripe_rects:
            return
        global_idx = letter_to_idx(letter)
        n_pages    = max(1, len(self._tiff_pages))

        # Map the absolute strip index → (page, local index). Prefer the
        # authoritative per-page counts from the .ti2: walking them handles a
        # non-uniform last page (e.g. 24,23) correctly, where a flat
        # global_idx // strips_per_page would keep the first strip of page 2 on
        # page 1. Fall back to a uniform split only when those counts are
        # absent (legacy label-detection path).
        if self._strips_per_page:
            page = 0
            local_idx = global_idx
            for count in self._strips_per_page:
                if local_idx < count:
                    break
                local_idx -= count
                page += 1
            strips_per_page_dbg = ",".join(str(c) for c in self._strips_per_page)
        else:
            strips_per_page = max(1, len(self._page_stripe_rects[0]))
            page            = global_idx // strips_per_page
            local_idx       = global_idx % strips_per_page
            strips_per_page_dbg = str(strips_per_page)

        page = max(0, min(page, n_pages - 1))
        # Use this page's own rects when we detected them per page; otherwise
        # (legacy fallback) reuse the only page we have.
        rects_idx = min(page, len(self._page_stripe_rects) - 1)
        rects = self._page_stripe_rects[rects_idx]

        if bool(self._settings.get("debug_highlighter", False)):
            msg = (
                f"[highlighter] id={strip_id} letter={letter} "
                f"global_idx={global_idx} strips_per_page={strips_per_page_dbg} "
                f"page={page + 1}/{n_pages} local_idx={local_idx}"
            )
            self._log.appendPlainText(msg)
            log.warning(msg)  # also goes to chromiq.log file

        self._preview.set_stripe_rects(rects, self._stripe_arrow_mode)
        if 0 <= page < n_pages:
            self._preview.show_page(page)
        self._preview.highlight_stripe(local_idx)

    # ------------------------------------------------------------------
    # ChromIQ chart-reading engine (#126)
    # ------------------------------------------------------------------

    def _engine_selected(self) -> bool:
        return str(self._settings.get("chartread_engine", "argyll")) == "chromiq"

    def refresh_engine_visibility(self) -> None:
        """Re-apply the chart-reading-engine beta flag to the engine-only UI so
        turning it on/off in Preferences takes effect the moment you click OK — no
        app restart. Called by MainWindow after the Settings dialog closes; the
        engine itself is already chosen live at the start of each measurement, so
        this only syncs the visible chrome (the "Live preview" view groups)."""
        on = self._engine_selected()
        for grp in (getattr(self, "_g_view_grp", None),
                    getattr(self, "_m_view_grp", None)):
            if grp is not None:
                grp.setVisible(on)

    def _locate_strip(self, letter: str) -> "tuple[int, int, QRect | None]":
        """(page, local index, image-px rect) for a strip letter — the same
        mapping _on_stripe_changed uses for the measure arrow."""
        global_idx = letter_to_idx(letter)
        page, local_idx = 0, global_idx
        if self._strips_per_page:
            for count in self._strips_per_page:
                if local_idx < count:
                    break
                local_idx -= count
                page += 1
        elif self._page_stripe_rects:
            spp = max(1, len(self._page_stripe_rects[0]))
            page, local_idx = global_idx // spp, global_idx % spp
        rect = None
        if self._page_stripe_rects:
            ridx = min(page, len(self._page_stripe_rects) - 1)
            rects = self._page_stripe_rects[ridx]
            if 0 <= local_idx < len(rects):
                rect = rects[local_idx]
        return page, local_idx, rect

    def _letter_for_page_idx(self, page: int, local_idx: int) -> str | None:
        """Inverse of _locate_strip for preview clicks."""
        if self._strips_per_page:
            base = sum(self._strips_per_page[:page])
        elif self._page_stripe_rects:
            base = page * max(1, len(self._page_stripe_rects[0]))
        else:
            base = 0
        global_idx = base + local_idx
        # idx → letters (A..Z, AA..): inverse of letter_to_idx
        letters = ""
        n = global_idx
        while True:
            letters = chr(ord("A") + n % 26) + letters
            n = n // 26 - 1
            if n < 0:
                break
        return letters or None

    def _on_session_map(self, strips: list) -> None:
        self._engine_strips = list(strips)
        self._engine_read = {s.get("strip", ""): bool(s.get("read"))
                             for s in strips}
        self._preview.clear_patch_overlay()
        self._patch_geom_warned = False
        if self._spot_session:
            # Patch-by-patch mode drives the preview via spot_ready/patch_read
            # with its OWN per-patch highlight + click-to-jump. The strip
            # click/highlight UI must stay off, or it frames the whole strip and
            # (because strip-click is tested before patch-click) swallows the
            # patch click so nothing jumps.
            self._preview.set_stripe_click_enabled(False)
            self._m_engine_tip.setVisible(False)
            self._set_autosave_banner()
            return
        is_manual = self._current_mode() == "manual"
        # The view controls are always visible in the "Live preview" group now;
        # only the transient click-a-strip tip appears while a manual read runs.
        self._m_engine_tip.setVisible(is_manual)
        # Autosave reassurance shows on the preview for both modes (autosave
        # protects guided reads too).
        self._set_autosave_banner()
        # Click-to-jump: hover + click a strip in the preview to jump to it —
        # in BOTH modules now (Basti). The engine handles `goto` the same way in
        # guided as in manual, and autosave makes jumping non-destructive.
        read_map = {}
        for s in strips:
            _pg, li, _r = self._locate_strip(s.get("strip", "A"))
            read_map[li] = bool(s.get("read"))
        self._preview.set_stripe_click_enabled(True, read_map)
        if any(not s.get("verifiable", True) for s in strips):
            self._log.appendPlainText(
                tr("[Engine] Note: some rows of this chart are too similar "
                   "for automatic row identification — for those, take the "
                   "usual care to swipe the row shown in the preview."))

    def _on_preview_strip_clicked(self, page: int, local_idx: int) -> None:
        if not self._manager.engine_active:
            return
        letter = self._letter_for_page_idx(page, local_idx)
        if letter:
            self._manager.goto_strip(letter)
            self._log.appendPlainText(
                tr("[Engine] Jumping to strip {strip}…").format(strip=letter))

    def _show_strip_pace(self, strip: str, pace, config) -> None:
        """Record this strip's time and redraw the panel under the preview."""
        if pace.patches <= 0 or pace.mean_seconds <= 0:
            return
        self._pace_patches = pace.patches
        self._pace_times[strip or "?"] = (pace.elapsed, True)
        ms = int(pace.mean_seconds * 1000)
        target_ms = int(config.target_seconds * 1000)
        if pace.too_fast:
            colour, verdict = "#ff6b6b", tr("Too fast — read more slowly")
        elif pace.marginal:
            colour, verdict = "#e0a63a", tr("Close to the limit")
        else:
            colour, verdict = "#5cb85c", tr("Good reading speed")
        detail = tr("{ms} ms per patch (aim for {target} ms or more)").format(
            ms=ms, target=target_ms)
        if pace.est_samples is not None:
            detail = tr(
                "{ms} ms per patch — roughly {n} readings (aim for {target} ms "
                "or more)").format(ms=ms, n=pace.est_samples, target=target_ms)
        self._refresh_pace_panel(f"{verdict} · {detail}", colour)

    def _measurement_summary(self) -> str:
        """How the whole chart went, for the window that closes a measurement
        (#131, Knut 2026-07-26). Empty when nothing was timed — with stock
        chartread there are no scan times, and an empty summary is better than
        a made-up one."""
        try:
            from core.measure_pace import session_summary
            times = getattr(self, "_pace_times", None)
            started = getattr(self, "_measure_started_at", None)
            if not times or started is None:
                return ""
            import time
            return session_summary(times, time.monotonic() - started)
        except Exception:      # noqa: BLE001 — a summary must never block a read
            log.warning("could not build the measurement summary", exc_info=True)
            return ""

    def _refresh_pace_panel(self, verdict: str = "", colour: str = "#909090") -> None:
        """Lay the recorded times out under the strips they belong to.

        A time is only drawn for a strip on the page currently shown, and only
        when the preview can say where that strip is — otherwise the panel would
        put numbers under the wrong columns, which is worse than none.
        """
        panel = getattr(self, "_pace_panel", None)
        if panel is None:
            return
        columns = []
        try:
            centres = self._preview.stripe_x_centres()
            page_now = self._preview.current_page()
            for letter, (secs, ok) in self._pace_times.items():
                page, local_idx, _rect = self._locate_strip(letter)
                if page == page_now and 0 <= local_idx < len(centres):
                    text = (tr("{secs} s").format(secs=f"{secs:.1f}") if ok
                            else tr("{secs} s ✕").format(secs=f"{secs:.1f}"))
                    columns.append((centres[local_idx], text))
        except Exception:      # noqa: BLE001 — a panel must never break a read
            columns = []
        self._pace_verdict = verdict
        self._pace_verdict_colour = colour
        label = ""
        if columns and self._pace_patches:
            label = tr("Strip reading times, {n} patches:").format(
                n=self._pace_patches)
        panel.set_content(label, sorted(columns), verdict, colour)

    def _clear_pace_readout(self) -> None:
        """Forget the pace shown on screen — a new or re-read chart starts from
        nothing, so an old strip's verdict can never be mistaken for this one."""
        self._pace_times = {}
        self._pace_patches = 0
        self._scan_started_at = None
        # Each measurement decides for itself whether the reading-speed window
        # is wanted: another chart may need a different pace, and that is worth
        # seeing once (Knut, #131 2026-07-26).
        self._suppress_fast_prompt = False
        panel = getattr(self, "_pace_panel", None)
        if panel is not None:
            panel.clear()

    def _play_measurement_finished_once(self) -> None:
        """Sound "measurement finished" the moment the chart is read.

        Knut (#131): it used to come only once the pop-up had been answered and
        the profile tab opened, which felt wrong — the measurement was over the
        instant the last strip was accepted, whatever you choose to do next. The
        once-per-read flag keeps it from sounding twice when the read also ends
        through the measure_finished signal.
        """
        if getattr(self, "_finish_sound_played", False):
            return
        self._finish_sound_played = True
        if getattr(self, "_sound", None) is not None:
            import core.sound as _snd
            self._sound.play(_snd.MEASUREMENT_FINISHED)

    def _play_strip_cue(self, *, too_fast: bool) -> None:
        """Sound the one cue this finished strip has earned.

        Called exactly once per accepted strip — the slow-down cue when it was
        read too fast, the strip cue otherwise. Never both (Knut, #131).
        """
        if getattr(self, "_sound", None) is None:
            return
        import core.sound as _snd
        self._sound.play(_snd.SLOW_DOWN if too_fast else _snd.STRIP_OK)

    def _on_scan_started(self) -> None:
        """The instrument fired: the swipe starts now (#131, Knut 2026-07-26).

        This is the only true start time for a strip. ``strip_ready`` arrives
        while the head is still being lined up, and timing from there would add
        the user's positioning to the swipe and make every strip look slow.
        """
        import time
        self._scan_started_at = time.monotonic()

    def _report_strip_pace(self, ev: "dict | None" = None) -> None:
        """After a strip that Argyll ACCEPTED, say how fast it was read — and
        say so loudly when it was read close to (or past) the speed at which it
        would have been rejected, which Argyll only tells you once the strip has
        already failed.

        **A strip-scanning instrument hands the whole strip back at once**, so
        there are no per-patch events during a swipe and no per-patch times to
        show. What is real is the scan's total time and the number of patches in
        the strip — the same two numbers Knut derived the thresholds from.
        """
        if not self._settings.get("pace_hint_enabled", True):
            # No pace judgement wanted, so the strip simply sounds as read.
            self._play_strip_cue(too_fast=False)
            return
        try:
            import time
            from core.measure_pace import strip_pace_message
            # Created here, not merely fetched: in strip mode nothing else makes
            # one, because the per-patch handler that used to create it never
            # runs (a strip-scanning instrument reports no per-patch events).
            tracker = self._pace_tracker()
            started = getattr(self, "_scan_started_at", None)
            patches = len((ev or {}).get("patches") or [])
            if started is None or not patches:
                # Nothing to judge: no scan start (stock chartread reports none)
                # or no patches (a strip that failed is handled separately).
                # The strip was still read, so it still gets its cue.
                self._play_strip_cue(too_fast=False)
                return
            pace = tracker.strip_timed(time.monotonic() - started, patches)
            self._scan_started_at = None
            if patches:
                # Every strip of a chart holds the same number, so this is what
                # a FAILED strip (which returns nothing) is judged by.
                self._last_strip_patches = patches
            self._show_strip_pace(str((ev or {}).get("strip", "")), pace,
                                  tracker.config)
            msg = strip_pace_message(pace, tracker.config)
            if msg:
                self._log.appendPlainText("\n" + msg)
                self._log.ensureCursorVisible()
            # ONE strip, ONE sound (Knut, #131 2026-07-27): a strip that was
            # accepted but read too fast used to sound its "strip read OK" cue
            # and the slow-down cue together. The verdict is only known here,
            # which is why the cue is chosen here and nowhere else.
            self._play_strip_cue(too_fast=pace.too_fast)
            if pace.too_fast:
                # Accepted, but under the threshold: offer the same choice a
                # failed strip gets — read it again, or keep it (Knut, #131).
                self._prompt_too_fast_strip(str((ev or {}).get("strip", "")),
                                            pace, tracker.config)
        except Exception:      # noqa: BLE001 — a hint must never break a read
            log.warning("pace hint failed", exc_info=True)

    def _on_strip_measured(self, ev: dict) -> None:
        letter = str(ev.get("strip", ""))
        self._skip_next_all_done = False       # the re-read has happened
        self._engine_read[letter] = True
        page, local_idx, rect = self._locate_strip(letter)
        patches = ev.get("patches", [])
        if not patches:
            return

        # Split-patch overlay: place each split on the patch's OWN box, looked
        # up by its location id (e.g. "A12"). This keeps every split exactly on
        # the printed patch — spacers, ColorMunki double density and multi-page
        # layouts all just work. If the chart exposes no per-patch geometry we
        # draw nothing (never a misaligned block over the chart).
        boxes = self._patch_boxes[page] if 0 <= page < len(self._patch_boxes) else {}
        if not boxes:
            if not self._patch_geom_warned:
                self._patch_geom_warned = True
                self._log.appendPlainText(
                    tr("[Engine] Live patch preview needs a chart made with the "
                       "ChromIQ layout engine, so it is off for this chart. Your "
                       "measurement is unaffected — every strip is still saved and "
                       "checked."))
            # Keep the read-map / strip highlight current even without overlay.
            self._update_engine_read_map()
            return

        from PyQt6.QtGui import QColor as _QC
        # The ΔE at which a patch gets the red warning outline is user-settable
        # (Preferences → Beta), defaulting to _PATCH_WARN_DE (Knut).
        warn_de = float(self._settings.get("patch_read_warn_de", _PATCH_WARN_DE))
        # A patch is flagged only if it is BOTH above the absolute floor AND an
        # outlier within this strip (Tukey fence). Vivid patches that all sit
        # high against sRGB stay unflagged (they're the strip's norm, not an
        # outlier); a genuine misread — a smudge, a skipped row — spikes above
        # its neighbours and is caught. This can only REDUCE flags versus the
        # floor alone, so it never adds false alarms (Nelson/pharmacist: a good
        # print was flagged almost everywhere against sRGB).
        fence = _strip_outlier_fence([float(p.get("de", 0)) for p in patches])
        from workflow.icc_info import xyz_to_lab
        items = []
        info_items = []
        for p in patches:
            box = boxes.get(str(p.get("loc", "")))
            if box is None:
                continue
            de_p = float(p.get("de", 0))
            warn = de_p >= warn_de and de_p >= fence
            exyz = p.get("exyz", [0, 0, 0])
            mxyz = p.get("xyz", [0, 0, 0])
            exp_rgb = _xyz_d50_to_srgb8(exyz)
            meas_rgb = _xyz_d50_to_srgb8(mxyz)
            items.append((box, _QC(*exp_rgb), _QC(*meas_rgb), warn))
            # Numbers behind the split, for the "values on hover" tile. The tile
            # shows the SAME sRGB as the swatch (so card and patch always agree)
            # plus the exact D50 L*a*b* and the engine's own ΔE for the patch.
            info_items.append((box, {
                "loc": str(p.get("loc", "")),
                "exp_rgb": exp_rgb,
                "meas_rgb": meas_rgb,
                "exp_lab": xyz_to_lab(tuple(float(v) / 100.0 for v in exyz[:3])),
                "meas_lab": xyz_to_lab(tuple(float(v) / 100.0 for v in mxyz[:3])),
                "de": de_p,
            }))
        if items:
            self._preview.set_patch_overlay(page, items)
            self._preview.set_patch_info(page, info_items)
        self._update_engine_read_map()

    def _locate_patch(self, loc: str) -> "tuple[int, QRect | None]":
        """(page, image-px box) of patch `loc` across the chart's pages, or
        (-1, None) when the chart exposes no geometry for it."""
        for page, boxes in enumerate(self._patch_boxes):
            if loc in boxes:
                return page, boxes[loc]
        return -1, None

    def _on_patch_ready(self, ev: dict) -> None:
        """Engine spot (patch-by-patch) mode: highlight the patch to read next
        and flip to its page. The first call arms click-to-jump for the whole
        chart's patches."""
        loc = str(ev.get("loc", ""))
        self._spot_current_loc = loc
        if not self._spot_click_on and any(self._patch_boxes):
            self._spot_click_on = True
            self._preview.set_patch_click_enabled(True, self._patch_boxes)
            self._log.appendPlainText(
                tr("[Engine] Tip: click any patch in the preview to jump "
                   "straight to it."))
        page, box = self._locate_patch(loc)
        if page < 0:
            self._preview.highlight_patch(-1, None)
            return
        if page != self._preview.current_page():
            self._preview.show_page(page)
        self._preview.highlight_patch(page, box)

    def _on_patch_measured(self, ev: dict) -> None:
        """Engine spot mode: add this patch's expected/measured split and its
        hover values (mirrors _on_strip_measured for a single patch)."""
        loc = str(ev.get("loc", ""))
        page, box = self._locate_patch(loc)
        if page < 0 or box is None:
            if not self._patch_geom_warned and not any(self._patch_boxes):
                self._patch_geom_warned = True
                self._log.appendPlainText(
                    tr("[Engine] Live patch preview needs a chart made with the "
                       "ChromIQ layout engine, so it is off for this chart. Your "
                       "measurement is unaffected — every patch is still saved and "
                       "checked."))
            return
        from PyQt6.QtGui import QColor as _QC
        from workflow.icc_info import xyz_to_lab
        warn_de = float(self._settings.get("patch_read_warn_de", _PATCH_WARN_DE))
        de_p = float(ev.get("de", 0))
        exyz = ev.get("exyz", [0, 0, 0])
        mxyz = ev.get("xyz", [0, 0, 0])
        exp_rgb = _xyz_d50_to_srgb8(exyz)
        meas_rgb = _xyz_d50_to_srgb8(mxyz)
        item = (box, _QC(*exp_rgb), _QC(*meas_rgb), de_p >= warn_de)
        info = (box, {
            "loc": loc,
            "exp_rgb": exp_rgb,
            "meas_rgb": meas_rgb,
            "exp_lab": xyz_to_lab(tuple(float(v) / 100.0 for v in exyz[:3])),
            "meas_lab": xyz_to_lab(tuple(float(v) / 100.0 for v in mxyz[:3])),
            "de": de_p,
        })
        # Accumulate: each patch adds its own split + numbers (dedup by box, so
        # re-reading a patch refreshes it rather than stacking).
        self._preview.set_patch_overlay(page, [item])
        self._preview.set_patch_info(page, [info])

    def _on_chart_reading(self) -> None:
        """XY/chart mode (engine opt-in): an autonomous whole-chart read began."""
        self._log.appendPlainText(
            tr("[Engine] Reading the whole chart — this may take a moment…"))

    def _on_chart_measured(self, ev: dict) -> None:
        """XY/chart mode: fill the expected/measured split + hover values for
        every patch that was read at once (a whole chart, or one XY sheet)."""
        patches = ev.get("patches", [])
        if not patches or not any(self._patch_boxes):
            return
        from PyQt6.QtGui import QColor as _QC
        from workflow.icc_info import xyz_to_lab
        warn_de = float(self._settings.get("patch_read_warn_de", _PATCH_WARN_DE))
        items: dict[int, list] = {}
        infos: dict[int, list] = {}
        for p in patches:
            loc = str(p.get("loc", ""))
            page, box = self._locate_patch(loc)
            if page < 0 or box is None:
                continue
            de_p = float(p.get("de", 0))
            exyz = p.get("exyz", [0, 0, 0])
            mxyz = p.get("xyz", [0, 0, 0])
            exp_rgb = _xyz_d50_to_srgb8(exyz)
            meas_rgb = _xyz_d50_to_srgb8(mxyz)
            items.setdefault(page, []).append(
                (box, _QC(*exp_rgb), _QC(*meas_rgb), de_p >= warn_de))
            infos.setdefault(page, []).append((box, {
                "loc": loc,
                "exp_rgb": exp_rgb,
                "meas_rgb": meas_rgb,
                "exp_lab": xyz_to_lab(tuple(float(v) / 100.0 for v in exyz[:3])),
                "meas_lab": xyz_to_lab(tuple(float(v) / 100.0 for v in mxyz[:3])),
                "de": de_p,
            }))
        for page, its in items.items():
            self._preview.set_patch_overlay(page, its)
            self._preview.set_patch_info(page, infos[page])

    def _existing_ti3_for_chart(self) -> "Path | None":
        """The measured .ti3 sitting next to the loaded chart (#134), or None."""
        if self._ti1_path is None:
            return None
        ti3 = self._ti1_path.with_suffix(".ti3")
        return ti3 if ti3.is_file() else None

    def _show_overlay_from_existing_ti3(self) -> bool:
        """Paint the expected-vs-measured split-patch overlay from a measurement
        already on disk (#134), without re-reading. Returns True when the overlay
        was painted; False when there's no usable data (foreign / geometry-less
        .ti3) — the caller then points the user at Tools ▸ Inspect a measurement."""
        ti3 = self._existing_ti3_for_chart()
        if ti3 is None or self._ti1_path is None:
            return False
        # Ensure we have this chart's per-patch geometry (populated on load, but
        # be defensive so the overlay works even if it wasn't).
        if not any(self._patch_boxes):
            try:
                self._patch_boxes = patch_boxes_from_sidecar(
                    self._ti1_path, len(self._tiff_pages) or 1)
            except Exception:      # noqa: BLE001
                self._patch_boxes = []
        try:
            from workflow.measurement_report import per_patch_overlay
            patches = per_patch_overlay(ti3, self._ti1_path)
        except Exception:          # noqa: BLE001 — never break on a bad file
            patches = []
        if not patches or not any(self._patch_boxes):
            return False
        self._on_chart_measured({"patches": patches})
        return True

    def _clear_overlay(self) -> None:
        """Remove a statically-shown overlay (#134)."""
        self._preview.clear_patch_overlay()

    def _sync_overlay_checkboxes(self, checked: bool) -> None:
        """Keep the guided + manual 'Show overlay' boxes in step (#134)."""
        for cb in (getattr(self, "_overlay_cb", None),
                   getattr(self, "_m_overlay_cb", None)):
            if cb is not None and cb.isChecked() != checked:
                cb.blockSignals(True)
                cb.setChecked(checked)
                cb.blockSignals(False)

    def _on_overlay_toggled(self, checked: bool) -> None:
        """Show/hide the from-.ti3 overlay (#134). If the chart's measurement
        can't be placed (foreign / geometry-less .ti3), inform the user and
        untick — the numbers are still available in Tools ▸ Inspect a
        measurement."""
        self._sync_overlay_checkboxes(checked)
        if not checked:
            self._clear_overlay()
            return
        if self._show_overlay_from_existing_ti3():
            self._log.appendPlainText(tr(
                "Showing the expected vs. measured colours from this chart's "
                "existing measurement. Untick to hide them."))
            return
        # No usable overlay data → undo the tick and guide to the tabular view.
        self._sync_overlay_checkboxes(False)
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)      # clean style, no icon (Basti)
        box.setWindowTitle(tr("Can't show the overlay"))
        box.setText(
            tr("This chart's measurement can't be shown on the patches — it "
               "looks like it was made for a different chart (the patch layout "
               "doesn't match).\n\nOpen it in Tools ▸ Inspect a measurement to "
               "see the measured values as a table instead."))
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _on_preview_patch_clicked(self, page: int, loc: str) -> None:
        if not self._manager.engine_active or not loc:
            return
        self._manager.goto_patch(loc)
        self._log.appendPlainText(
            tr("[Engine] Jumping to patch {loc}…").format(loc=loc))

    def _update_engine_read_map(self) -> None:
        read_map = {}
        for s in self._engine_strips:
            _pg, li, _r = self._locate_strip(s.get("strip", "A"))
            read_map[li] = self._engine_read.get(s.get("strip", ""), False)
        self._preview.set_stripe_read_map(read_map)

    def _reveal_chart_folder(self) -> None:
        """Open the current chart's folder in the file manager (Knut — same
        button name and behaviour as the Create Chart tab, for consistency)."""
        from core.preset_store import reveal_in_file_manager
        if self._ti1_path is not None:
            target = self._ti1_path.parent
        else:
            custom = str(self._settings.get("custom_output_path", "")).strip()
            target = Path(custom).expanduser() if custom else Path.home() / "ChromIQ"
        reveal_in_file_manager(target)

    def _maybe_save_measurement_report(self, ti3) -> None:
        """When the Settings option is on, build + save a dated accuracy report
        next to the chart after a measurement, so reports accrue for
        over-time comparison (Knut). Best-effort — never blocks or errors the
        measurement flow."""
        if not bool(self._settings.get("save_measurement_report", False)):
            return
        try:
            from workflow.measurement_report import build_report, save_report
            from pathlib import Path as _P
            ti3 = _P(ti3)
            if ti3.suffix.lower() != ".ti3" or not ti3.exists():
                return
            report = build_report(ti3)
            path = save_report(report, ti3.parent)
            self._log.appendPlainText(
                tr("[Report] Measurement report saved: {name}").format(
                    name=path.name))
        except Exception as exc:  # noqa: BLE001
            log.warning("measurement report failed: %s", exc)

    def _open_measurement_report(self) -> None:
        """Open the measurement-report viewer for the current chart's .ti3."""
        from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
        ti3 = self._ti1_path.with_suffix(".ti3") if self._ti1_path else None
        if ti3 is None or not ti3.exists():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, tr("Measurement Report"),
                tr("Measure this chart first — the report compares your "
                   "measurement against the chart's design colours."))
            return
        MeasurementReportDialog(self._settings, self, initial_ti3=ti3).exec()

    def _set_autosave_banner(self, saved: int | None = None) -> None:
        """Show the autosave reassurance as a preview banner (the same amber
        note style as the Create Chart 'approximate colours' note), or hide it
        when the engine isn't active."""
        if not self._manager.engine_active:
            self._preview.set_notice(None)
            return
        if saved and saved > 0:
            self._preview.set_notice(tr(
                "Auto-save on — {count} patches already safe on disk. Every "
                "strip is written the moment it is accepted, so you can always "
                "continue where you left off.").format(count=saved))
        else:
            self._preview.set_notice(tr(
                "Auto-save on — every strip is written to disk the moment it "
                "is accepted, so if anything goes wrong you can always "
                "continue where you left off."))

    def _on_readings_saved(self, path: str, n: int) -> None:
        self._set_autosave_banner(n)

    def _apply_engine_params(self, p: MeasureParams) -> MeasureParams:
        """Attach the chart-reading engine when selected and usable."""
        if not self._engine_selected():
            return p
        from workflow import chartread_engine
        try:
            p.engine_helper = chartread_engine.helper_path()
        except chartread_engine.EngineUnavailable:
            self._log.appendPlainText(
                tr("[Engine] The ChromIQ chart-reading engine isn't "
                   "available on this system — using regular chartread. "
                   "Everything works as before."))
            return p
        p.engine_safenet = bool(self._settings.get("misalign_safenet", False))
        p.engine_xy_chart = bool(self._settings.get("engine_all_modes", False))
        p.cal_auto_retries = int(self._settings.get("cal_auto_retries", 3))
        import os as _os
        replay = _os.environ.get("CHROMIQ_REPLAY")
        if replay:
            p.engine_replay = Path(replay)
        return p

    # ------------------------------------------------------------------
    # Param collection
    # ------------------------------------------------------------------

    def _collect_guided(self) -> MeasureParams:
        extra_args: list[str] = []
        for opt in self._chartread_opts:
            extra_args += opt.build_args()

        return MeasureParams(
            ti1_path            = self._ti1_path,
            instrument          = str(self._instr_spin.value()),
            disable_bidir       = self._resolve_disable_bidir("guided"),
            force_bidir         = self._resolve_force_bidir("guided"),
            suppress_warnings   = self._suppress_cb.isChecked(),
            disable_initial_cal = self._nocal_cb.isChecked(),
            patch_by_patch      = self._pbp_cb.isChecked(),
            resume              = self._resume_cb.isChecked(),
            extra_args          = " ".join(extra_args),
        )

    def _collect_manual(self) -> MeasureParams:
        extra_args: list[str] = []
        for opt in self._m_chartread_opts:
            extra_args += opt.build_args()

        return MeasureParams(
            ti1_path            = self._ti1_path,
            instrument          = str(self._m_instr_spin.value()),
            disable_bidir       = self._resolve_disable_bidir("manual"),
            force_bidir         = self._resolve_force_bidir("manual"),
            suppress_warnings   = self._m_suppress_cb.isChecked(),
            disable_initial_cal = self._m_nocal_cb.isChecked(),
            patch_by_patch      = self._m_pbp_cb.isChecked(),
            resume              = self._m_resume_cb.isChecked(),
            extra_args          = " ".join(extra_args),
        )

    def _collect_params(self) -> MeasureParams:
        if self._current_mode() == "guided":
            return self._apply_engine_params(self._collect_guided())
        return self._apply_engine_params(self._collect_manual())

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _on_save_defaults(self) -> None:
        s = self._settings
        if self._current_mode() == "guided":
            s.set("measure_bidir_mode",        self._bidir_combo.currentData())
            s.set("measure_bidir_auto",        self._bidir_auto_cb.isChecked())
            s.set("measure_suppress_warnings", self._suppress_cb.isChecked())
            s.set("measure_no_cal",            self._nocal_cb.isChecked())
            s.set("measure_patch_by_patch",    self._pbp_cb.isChecked())
            s.set("measure_overlay_mode",      self._g_overlay_mode.currentData())
            s.set("measure_only_measured",     self._g_only_measured.isChecked())
            s.set("measure_patch_tile",        self._g_patch_tile.isChecked())
            for opt in self._chartread_opts:
                if opt.checkbox:
                    s.set(f"measure_{opt.key}_enabled", opt.checkbox.isChecked())
                if opt.widget is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        s.set(f"measure_{opt.key}_value", opt.widget.value())
                    elif isinstance(opt.widget, QComboBox):
                        s.set(f"measure_{opt.key}_value", opt.widget.currentData())
        else:
            s.set("manual2_chartread_instr",    self._m_instr_spin.value())
            s.set("manual2_chartread_bidir_mode", self._m_bidir_combo.currentData())
            s.set("manual2_chartread_bidir_auto", self._m_bidir_auto_cb.isChecked())
            s.set("manual2_chartread_suppress", self._m_suppress_cb.isChecked())
            s.set("manual2_chartread_nocal",    self._m_nocal_cb.isChecked())
            s.set("manual2_chartread_pbp",      self._m_pbp_cb.isChecked())
            s.set("manual2_overlay_mode",       self._m_overlay_mode.currentData())
            s.set("manual2_only_measured",      self._m_only_measured.isChecked())
            s.set("manual2_patch_tile",         self._m_patch_tile.isChecked())
            for opt in self._m_chartread_opts:
                if opt.checkbox:
                    s.set(f"manual2_chartread_{opt.key}_enabled", opt.checkbox.isChecked())
                if opt.widget is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        s.set(f"manual2_chartread_{opt.key}_value", opt.widget.value())
                    elif isinstance(opt.widget, QComboBox):
                        s.set(f"manual2_chartread_{opt.key}_value", opt.widget.currentData())
        self._log.appendPlainText("Measurement settings saved as defaults.")
        self._log.ensureCursorVisible()

    def _restore_defaults(self) -> None:
        s = self._settings
        # Guided defaults. The legacy guided default was -B on (DEFAULTS has
        # measure_disable_bidir=True), so a brand-new user migrates to "disable"
        # via legacy_disable; someone who saved it False migrates to "default".
        self._set_bidir_value(self._bidir_combo, self._coerce_bidir_mode(
            s.get("measure_bidir_mode"),
            bool(s.get("measure_disable_bidir", True)),
            bool(s.get("measure_force_bidir", False))))
        self._bidir_auto_cb.setChecked(bool(s.get("measure_bidir_auto", True)))
        self._suppress_cb.setChecked(bool(s.get("measure_suppress_warnings", True)))
        self._nocal_cb.setChecked(bool(s.get("measure_no_cal", False)))
        self._pbp_cb.setChecked(bool(s.get("measure_patch_by_patch", False)))
        _gom = self._g_overlay_mode.findData(s.get("measure_overlay_mode", "both"))
        if _gom >= 0:
            self._g_overlay_mode.setCurrentIndex(_gom)
        self._g_only_measured.setChecked(bool(s.get("measure_only_measured", False)))
        self._g_patch_tile.setChecked(bool(s.get("measure_patch_tile", False)))
        for opt in self._chartread_opts:
            if opt.checkbox:
                enabled = bool(s.get(f"measure_{opt.key}_enabled", False))
                opt.checkbox.setChecked(enabled)
            if opt.widget is not None:
                val = s.get(f"measure_{opt.key}_value")
                if val is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        try:
                            opt.widget.setValue(float(val))
                        except (ValueError, TypeError):
                            pass
                    elif isinstance(opt.widget, QComboBox):
                        idx = opt.widget.findData(str(val))
                        if idx >= 0:
                            opt.widget.setCurrentIndex(idx)
        # Manual defaults
        m_instr = s.get("manual2_chartread_instr")
        if m_instr is not None:
            try:
                self._m_instr_spin.setValue(int(m_instr))
            except (ValueError, TypeError):
                pass
        self._set_bidir_value(self._m_bidir_combo, self._coerce_bidir_mode(
            s.get("manual2_chartread_bidir_mode"),
            bool(s.get("manual2_chartread_bidir", False)),
            bool(s.get("manual2_chartread_force_bidir", False))))
        self._m_bidir_auto_cb.setChecked(bool(s.get("manual2_chartread_bidir_auto", True)))
        self._m_suppress_cb.setChecked(bool(s.get("manual2_chartread_suppress", True)))
        self._m_nocal_cb.setChecked(bool(s.get("manual2_chartread_nocal", False)))
        self._m_pbp_cb.setChecked(bool(s.get("manual2_chartread_pbp", False)))
        _om = self._m_overlay_mode.findData(s.get("manual2_overlay_mode", "both"))
        if _om >= 0:
            self._m_overlay_mode.setCurrentIndex(_om)
        self._m_only_measured.setChecked(bool(s.get("manual2_only_measured", False)))
        self._m_patch_tile.setChecked(bool(s.get("manual2_patch_tile", False)))
        for opt in self._m_chartread_opts:
            if opt.checkbox:
                enabled = bool(s.get(f"manual2_chartread_{opt.key}_enabled", False))
                opt.checkbox.setChecked(enabled)
            if opt.widget is not None:
                val = s.get(f"manual2_chartread_{opt.key}_value")
                if val is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        try:
                            opt.widget.setValue(float(val))
                        except (ValueError, TypeError):
                            pass
                    elif isinstance(opt.widget, QComboBox):
                        idx = opt.widget.findData(str(val))
                        if idx >= 0:
                            opt.widget.setCurrentIndex(idx)
        presets = self._m_load_presets()
        self._m_populate_preset_combo(presets)
        # Reflect the restored Auto toggles (grey out / sync the combos).
        self._apply_bidir_auto_state("guided")
        self._apply_bidir_auto_state("manual")
