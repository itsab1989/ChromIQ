"""Tab 3: Measure Chart."""
from __future__ import annotations

import html
import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from core.stem_paths import without_ext

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

from core.file_manager import (
    FileManager,
    Run,
    files_matching,
    glob_escape,
    stem_files,
)
from core.platform_paths import file_manager_name
from core.logger import get_logger
from core.preset_store import (
    load_presets as _load_tab_presets,
    reveal_in_file_manager,
    save_presets as _save_tab_presets,
    tab_dir,
)
from core.resource_path import resource_path
from core.strip_utils import letter_to_idx, parse_passes_per_page
from ui.cr30_calibration import Cr30CalibrationMixin
from ui.fade_scroll import FadeScrollArea
from ui.tab_header import TabHeader
from ui.tooltip_button import TooltipButton
from ui.widgets import ElidingComboBox, ElidingLabel, NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox, info_box_qss, make_browse_button, open_file_dialog, set_accent_html, set_ink, set_folder_icon, set_preset_icon, spectrum_cell, tint_dialog_primary

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
    from PyQt6.QtWidgets import (
        QCheckBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout)

    # ``hint_light``/``hint_dark`` and the two tint alphas are per-theme
    # values, so this is a theme question and the theme module answers it.
    #
    # AND THE THIRD APPEARANCE IS ANSWERED HERE NOW. This docstring used to end
    # "a third appearance needs a third hint colour here", and it was right and
    # nothing had supplied one — because the card is only built when the chart
    # you have just measured carries scanner geometry, i.e. at the end of a real
    # measurement, which no census reaches. Left alone it painted a green (or,
    # in Check & Refine, violet) tinted card with a coloured tick and coloured
    # helper text into a theme with one accent and no hues.
    from ui.theme import APPEARANCE_NEUTRAL, accent_for, active_mode, is_dark
    dark = is_dark()
    neutral = active_mode() == APPEARANCE_NEUTRAL
    # Readable secondary text on the tinted card — a muted accent that keeps
    # clear contrast in both themes (palette(mid) washed out on the tint).
    hint_color = hint_dark if dark else hint_light
    accent = accent_for(accent)
    r, g, b    = (int(accent[i:i + 2], 16) for i in (1, 3, 5))
    tint_a     = "0.13" if dark else "0.10"
    tint_bg    = f"rgba({r},{g},{b},{tint_a})"
    if neutral:
        # The card keeps its SHAPE — a bordered, slightly-raised panel is what
        # says "this is an aside you can opt into" — and spends the theme's own
        # values on it: the raised surface, the ordinary border, body ink for
        # the hint. The tick and the ⓘ are accents and are already ACTION.
        from ui import neutral_styles as _n
        hint_color = _n.NM_TEXT_DIM
        tint_bg = _n.NM_BG_SURFACE

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
from core.text_io import read_text
from core.platform_paths import default_output_root
from ui.warning_sign import inform, set_warning_icon, warn

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

log = get_logger(__name__)


def _REREAD_TOOLTIP() -> str:
    """What "Re-read Individual Strips" actually does — spelled out, because
    nothing said it (Knut, #131 2026-07-27: "the descriptions of the buttons do
    not properly explain the consequences when clicking them")."""
    return tr(
        "Goes back to the chart so you can read single strips again.\n\n"
        "Everything you have already measured stays exactly as it is — a strip "
        "you do not read again keeps the reading it has. Only the strips you "
        "do read are replaced.\n\n"
        "Strips you re-read in this session are marked in the preview, so you "
        "can see what you have done. When you have finished, press Stop: your "
        "measurement is saved either way, and because the chart is already "
        "complete there is no second “All strips read” window to wait for.")

#: The preview's nav row is inset by 12 px, so the reading-times frame uses the
#: same inset and its edges line up with the PREV and NEXT buttons (Knut, #131).
_PACE_SIDE_MARGIN = 12
#: ~2-3 mm of air above and below the frame, so the page buttons and the warning
#: line are not crammed against it (Knut, #131 2026-07-27).
_PACE_GAP = 10

#: How long the completion sound waits for the final strip's own cue to finish
#: (Knut, #131 2026-07-27: "a small 0.5 second delay … so that any sound that
#: was played before this window has a chance to finish").
_ALL_DONE_SOUND_GAP_MS = 500



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

#: The dark-reference threshold moved with the window that reads it, to
#: ``ui/cr30_calibration.py``. One constant, wherever the calibration runs
#: from: two copies of a number is how two windows come to disagree about
#: which readings are healthy.


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


def _save_partial_name() -> str:
    """The Save Partial & Quit button's label, as HTML.

    Qt reads `&&` in a button label as one literal ampersand; HTML wants
    `&amp;`. Naming the button in a message therefore needs this one
    substitution — and doing it here, from the button's OWN key, is what stops
    the message and the button becoming two separately translated strings. They
    already had: German called the button „Teilweise speichern && beenden" and
    every message that named it „Teil speichern &amp; beenden".
    """
    return tr("Save Partial && Quit").replace("&&", "&amp;")


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
            data = json.loads(read_text(strips_json))
            got = _ingest(data.get("patches") or [])
        except Exception:
            pass

    if not got:
        channels = ti2_path.with_suffix(".channels.json")
        if channels.is_file():
            try:
                layout = json.loads(read_text(channels)).get("layout") or {}
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
        layout = json.loads(read_text(channels)).get("layout") or {}
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
    """Nothing to do — the recorded boxes already hold the drawn position.

    SpectroScan hexagons are drawn with a ±¼-width horizontal zigzag by row
    (`raster._hexagon_points`), and this shifted every box to match, because
    "the recorded boxes hold only the slot x" (#32). That was true when it was
    written. On 2026-08-13 `geometry.patch_rects_px` started recording the
    stagger itself — so the boxes arrived already shifted and this moved them a
    SECOND time, putting the patch-by-patch ring and the click target a quarter
    patch off the hexagon they name, on every row of every hexagonal chart.
    Seen on screen: the highlight sat between two hexagons (Sebastian).

    A LEGACY sidecar still needs it, and says so itself. Hexagonal charts built
    between 2026-06-28 (when hexagons began to be drawn) and 2026-08-13 have
    unstaggered rects frozen in their sidecar, which is written once at chart
    creation and never rebuilt. `engine_version` is written but never read, so
    it cannot tell the vintages apart — but the geometry can: in an unstaggered
    sidecar every patch of a column shares one x, while a staggered one
    alternates two. Compensate only there.

    The identical stale compensation lived in `workflow.margin_inspector` and
    was removed at the same time.
    """
    import re
    from workflow.hex_support import chart_is_hexagonal
    if not chart_is_hexagonal(ti2_path):
        return
    for page in pages:
        if not page:
            continue
        columns: "dict[str, list[int]]" = {}
        for loc, r in page.items():
            m = re.match(r"([A-Za-z]+)", loc)
            columns.setdefault(m.group(1) if m else "", []).append(r.x())
        # A column of TWO OR MORE patches that all share one x is the fingerprint
        # of an unstaggered sidecar. Counting distinct x alone called a modern
        # chart legacy whenever a column held a single patch — real on short or
        # roll media with a big hexagon (210x40 mm at 20 mm) — and shifted every
        # box on it. Anything not positively identified as legacy is modern.
        legacy = any(len(xs) >= 2 and len(set(xs)) == 1 for xs in columns.values())
        if not legacy:
            continue
        for loc, r in list(page.items()):
            m = re.search(r"(\d+)\s*$", loc)
            if not m:
                continue                # the old code skipped these, and was wrong to
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
        layout = json.loads(read_text(sidecar)).get("layout")
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
    "strips in Check & Refine exactly as usual.\n\n"
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

#: Which chartread options the GUIDED module offers. Everything else is Manual
#: only, and Guided keeps a good fixed default for it (#160).
#:
#: Guided is "a few good defaults for a beginner"; Manual is full control. The
#: split is declared here rather than by hiding rows, because a hidden row that
#: is still collected is exactly how Guided ended up measuring with options
#: nobody could see.
#:
#: "tolerance" earns its place: a strip that keeps failing is the commonest
#: thing a beginner hits, and loosening the consistency tolerance is the
#: documented remedy.
GUIDED_CHARTREAD_KEYS: "set[str]" = {"tolerance"}

#: The options Manual keeps to itself, in the order Guided's information box
#: lists them. Derived from the single option table at run time, so this can
#: never fall out of step with what Guided actually builds.
def guided_fixed_option_labels(all_opts) -> "list[str]":
    """Labels of the options Guided does NOT offer, for its information box."""
    return [o.label for o in all_opts if o.key not in GUIDED_CHARTREAD_KEYS]


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

    #: Options this option row must not emit, whatever its checkbox says.
    #: Set when the instrument cannot honour them — see `suppress_for_cr30`.
    suppressed: bool = False

    def build_args(self) -> list[str]:
        """Return CLI tokens for this option if enabled."""
        if self.suppressed:
            # Deliberately BEFORE the checkbox test. Disabling a control greys
            # it but does not untick it, and the user's own value must survive
            # for the day they measure the same chart with another instrument.
            # So the row keeps its state and simply stops speaking.
            return []
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


def _cgats_has_no_readings(path) -> bool:
    """Whether a CGATS file (.ti3) carries a header but no readable readings.

    Used before offering to recover an interrupted measurement, and — since
    beta.133 — to decide whether "Refine / resume" is offered at all: a file
    with nothing countable in it is not readings to carry on from (#130, Knut
    2026-07-30).

    **It asks the model, rather than parsing again.** Its own parse split on the
    bare string ``"BEGIN_DATA"``, which also matches ``BEGIN_DATA_FORMAT`` — so
    a header-only file (§3a's *no data block*) looked like a data block holding
    one row, the format line. Knut, beta.132, on Demo-05: the window correctly
    said *"Refine / resume is not offered for this file"* while the checkbox for
    it was still on screen. He asked the right question — *"same check for ti3
    used for model?"* — and this is that check: ``count_sets`` anchors
    BEGIN_DATA/END_DATA to whole lines.
    """
    from workflow.measurement_state import count_sets
    counts = count_sets(path)
    if counts is None:
        return False          # unreadable is a different problem, not emptiness
    claimed, held = counts
    if held is None:          # no data block at all — §3a "header only"
        return True
    return held == 0


class TabMeasure(Cr30CalibrationMixin, QWidget):
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
        # Runs whose "this chart already has a measurement" warning the user has
        # silenced with the window's tick. **Deliberately an in-memory set and
        # never a setting** (Knut, #131 2026-07-28): it must survive moving
        # between runs and back, and must NOT survive closing the program, so
        # revisiting a run another day warns again. Keys come from
        # _replace_warning_scope().
        self._replace_warning_silenced: set = set()
        # The same, for the "this chart already has a measurement" window that
        # appears when a chart with readings is loaded or a run is switched to
        # (Knut's scenario 4). A SEPARATE set: silencing one window must not
        # silence the other — they say different things and one of them is the
        # last guard before readings are overwritten.
        self._offer_silenced: set = set()
        # A chart was loaded while another tab was on screen and still owes the
        # user the "this chart already has a measurement" offer — made when this
        # tab is next shown. See set_ti1_path / showEvent. (Since #130
        # 2026-07-29 showing the tab offers anyway, so this only shortens the
        # wait when a chart arrives while another tab is up.)
        self._pending_overlay_offer: bool = False
        # One existing-measurement window at a time — see
        # _maybe_offer_existing_overlay — and at most one queued offer per turn
        # of the event loop — see _queue_overlay_offer.
        self._offer_open: bool = False
        self._offer_queued: bool = False
        # When averaging is enabled, the "All Strips Read" dialog records the
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
        self._patch_missing_warned = False
        # Engine spot (patch-by-patch) mode: the patch currently awaiting a
        # read, and whether click-to-jump has been armed for this session.
        self._spot_current_loc: str = ""
        self._spot_click_on: bool = False
        self._spot_session: bool = False
        self._device_busy: bool = False
        self._no_instrument: bool = False
        #: raised once per SESSION, and cleared when the next one starts —
        #: see the note where it is reset. Declared here so it is a real
        #: attribute rather than something only `getattr` knows about.
        self._no_instrument_shown: bool = False
        self._usb_claimed_by_vm: bool = False
        # Pending terminal dialogs for group-B startup failures (shown by _on_measure_done).
        self._coms_init_failed_msg: str | None = None
        self._inst_init_failed_msg: str | None = None
        self._instrument_wrong_type: str | None = None
        self._ccmx_load_failed_msg: str | None = None
        self._mode_set_failed_msg: str | None = None
        self._ti3_mtime_before: float | None = None
        self._mode: str = "dark"

        # Sounds FIRST. Qt calls slots in connection order, and every one of the
        # slots below opens a modal dialog — which blocks inside itself. A cue
        # connected after such a slot is therefore not heard until the user
        # dismisses the window, which is the "sound on button press" Knut has
        # reported three times (#131, 2026-07-27). Connecting the cues ahead of
        # the windows makes them arrive together, for the whole family at once.
        self._connect_instrument_error_cues()
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
        # The pace report FIRST: it times the failed swipe, and _on_strip_error
        # opens a modal window that blocks inside its own slot. Connected after
        # it, the timing ran only once the user had answered — so the strip's
        # reading time included however long the window had been open (Knut,
        # #131 2026-07-27, after my first fix missed this).
        self._manager.strip_error.connect(self._report_failed_strip_pace)
        self._manager.strip_error.connect(self._on_strip_error)
        # #126 chart-reading engine
        self._manager.session_map.connect(self._on_session_map)
        self._manager.strip_measured.connect(self._on_strip_measured)
        # #153: progress counts PATCHES, so both reading modes feed one
        # set of patch locations. A set makes re-reading idempotent,
        # which is exactly what Knut asked for — measuring a patch again
        # must not move the number, because that patch was already read.
        self._manager.strip_measured.connect(self._count_strip_progress)
        self._manager.patch_measured.connect(self._count_patch_progress)
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
        self._manager.engine_fallback_refused.connect(
            self._on_engine_fallback_refused)
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
        # (every window that opens a modal cues itself from the top of its own
        #  slot — see _cue_window. The instrument-error signals below are the
        #  exception: their cue is CONNECTED, and connection order is therefore
        #  part of the behaviour. It is set up in _connect_instrument_error_cues,
        #  called BEFORE the slots that open those windows.)
        self.measure_finished.connect(
            lambda _p: self._play_measurement_finished_once())

        # Watchdog: if a dialog sends a key but chartread emits no new output
        # within KEY_WATCHDOG_MS, surface a recoverable warning so the user is
        # not left staring at a frozen dialog when a keystroke vanishes
        # (e.g. Windows AttachConsole failure — issue #20).
        self._last_chartread_output_ts: float = 0.0
        self._saw_instrument: bool = False
        self._key_watchdog = QTimer(self)
        self._key_watchdog.setSingleShot(True)
        self._key_watchdog.setInterval(12000)
        #: Windows opened while a read is in progress. Knut, beta.139:
        #: *"When the measurement session ends, everything relating to
        #: measurements should end, I would think. Restarted when starting a
        #: measurement."* Each one runs its own event loop, so without this a
        #: window could outlive the process it belongs to and its buttons then
        #: sent keys to nothing.
        self._live_measure_windows: list = []
        self._key_watchdog.timeout.connect(self._on_key_watchdog_timeout)
        self._build_ui()
        self._restore_defaults()
        self._link_mode_controls()
        self._start_btn.setEnabled(False)
        # THE ENGINE-ONLY CONTROLS MUST START IN THE RIGHT STATE.
        #
        # This ran only after Preferences was closed, so a session that began
        # with the chart-reading engine switched off still showed the
        # engine-only rows until the user happened to open Settings — Knut,
        # beta.128: *"'Play sounds during measurements' was not hidden when
        # starting up ChromIQ with the stock argyllcms chartread engine."*
        # The two "Live preview" groups were set at construction; the sounds
        # switch and the overlay boxes were not, which is the whole difference.
        self.refresh_engine_visibility(initial=True)

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _switch_mode(self, mode: str) -> None:
        # IMPORT exists only while the shared Run type is Verification; asked
        # for at any other moment (e.g. a restored state) it falls back to
        # Guided rather than showing a module that cannot run (#133).
        if mode == "import" and not self._import_available():
            mode = "guided"
        if mode == "guided":
            self._stack.setCurrentIndex(0)
        elif mode == "import":
            self._stack.setCurrentIndex(2)
        else:
            mode = "manual"
            self._stack.setCurrentIndex(1)
        self._guided_btn.setChecked(mode == "guided")
        self._manual_btn.setChecked(mode == "manual")
        if hasattr(self, "_import_btn"):
            self._import_btn.setChecked(mode == "import")
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
            self._refresh_import_controls()

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
        aim = getattr(self, f"_{prefix}_aim_help", None)
        if aim is not None:
            ap, body = self._cr30_aim_diameters_px()
            self._preview.set_aim_overlay(aim.isChecked() and body > 0,
                                          ap, body)

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
        # #133: the IMPORT module exists only for a verification run, so its
        # button follows the bar — and the destination line inside the module
        # follows the selected run / verification date.
        controller.changed.connect(self._refresh_import_visibility)
        self._refresh_import_visibility()

    # ------------------------------------------------------------------
    # Per-target settings (#130 §5 — Knut: "measure tab must be included")
    # ------------------------------------------------------------------
    #: What was last written for each target, so a repeated write trigger costs
    #: nothing (§3a Q-4). Reached through the accessor: as a bare class
    #: attribute every tab would share one dict and a second tab's writes would
    #: be silently skipped — that exact bug cost a debugging session on the
    #: Create Chart side.
    _measure_written: dict = {}

    def _measure_written_cache(self) -> dict:
        if "_measure_written" not in self.__dict__:
            self._measure_written = {}
        return self._measure_written

    def save_target_settings(self, store=None, key=None) -> bool:
        """Record this tab's settings against the selected target.

        Named to match the Create Chart tab because MainWindow calls it by
        duck-typing on the same L1/W6 events — leaving a tab, changing target,
        quitting.
        """
        if getattr(self, "_loading_measure_settings", False):
            return False
        if store is None:
            from workflow.per_target_settings import store_for_target
            store = store_for_target(getattr(self, "_target_ctl", None))
        if store is None:
            return False           # "New run", or no project
        # A WRITE MUST NEVER BRING A DELETED PROJECT BACK — save_meta creates
        # what it needs, and both "leaving a tab" and "quitting" fire right
        # after a delete (Knut's beta.102 sequence, which has now caught this
        # twice elsewhere).
        try:
            if not Path(getattr(store, "dir", "")).is_dir():
                return False
        except (TypeError, ValueError):
            return False
        try:
            from workflow.measure_settings import snapshot
            wanted = snapshot(self)
            if not wanted:
                return False
            fingerprint = str(getattr(store, "dir", store))
            if self._measure_written_cache().get(fingerprint) == wanted:
                return False
            meta = store.load_meta()
            if getattr(meta, "measure_settings", None) == wanted:
                self._measure_written_cache()[fingerprint] = wanted
                return False
            meta.measure_settings = wanted
            store.save_meta(meta)
            self._measure_written_cache()[fingerprint] = wanted
            log.debug("measure settings written for %s (%d)",
                      getattr(store, "id", store), len(wanted))
            return True
        except Exception:      # noqa: BLE001 — never lose the tab over a write
            log.warning("Could not save the target's Measure settings",
                        exc_info=True)
            return False

    def load_target_settings(self) -> bool:
        """Put the selected target's Measure settings on screen (§2 L1).

        Guarded, because filling these controls fires their signals and several
        of them rebuild the command preview.
        """
        from workflow.per_target_settings import store_for_target
        store = store_for_target(getattr(self, "_target_ctl", None))
        if store is None:
            return False
        try:
            stored = getattr(store.load_meta(), "measure_settings", None)
        except Exception:      # noqa: BLE001
            log.warning("Could not read the target's Measure settings",
                        exc_info=True)
            return False
        if not stored:
            # §4 S4–S7: A TARGET WITH NOTHING STORED OPENS ON ITS DEFAULTS.
            #
            # Returning here left the PREVIOUS target's values on screen, so
            # ticking "skip initial calibration" on run 1 and switching to run 2
            # showed it still ticked — Knut's beta.148 leak, rebuilt by the very
            # feature meant to prevent it. Every unit test passed while this was
            # broken, because none of them switched to a target with nothing
            # stored; the on-screen drive found it in one step.
            #
            # `_restore_defaults` is the tab's own saved-defaults loader, so the
            # values are the ones the user chose under "Save as Defaults" — not
            # a second idea of what a default is.
            self._loading_measure_settings = True
            try:
                self._restore_defaults()
            except Exception:      # noqa: BLE001
                log.warning("Could not restore the Measure defaults",
                            exc_info=True)
            finally:
                self._loading_measure_settings = False
            self._reassert_guided_refinement()
            # …and the CR30 patch-by-patch lock, for the same reason: a stored
            # or default `false` has just been written onto the screen (#159).
            self._apply_cr30_pbp_lock()
            self._apply_cr30_dead_options()
            return False
        self._loading_measure_settings = True
        try:
            from workflow.measure_settings import apply
            unknown = apply(self, stored)
            if unknown:
                log.info("ignored %d unknown stored Measure setting(s): %s",
                         len(unknown), ", ".join(sorted(unknown)[:8]))
            self._reassert_guided_refinement()
            self._apply_cr30_pbp_lock()
            self._apply_cr30_dead_options()
            return True
        except Exception:      # noqa: BLE001
            log.warning("Could not apply the target's Measure settings",
                        exc_info=True)
            return False
        finally:
            self._loading_measure_settings = False

    def _is_verification_run(self) -> bool:
        """True when the shared Run type says this read is a verification.

        It used to be "the module's Verification checkbox is ticked, OR the
        shared Run type is Verification". The checkbox is gone (Knut, #130
        2026-07-29) — under the unified file handling the bar is the only place
        a run's type is decided, and a second control could only disagree with
        it.
        """
        ctl = getattr(self, "_target_ctl", None)
        return ctl is not None and ctl.target.is_verification()

    def _is_pbp_checked(self) -> bool:
        """Whether the active module will read patch by patch.

        Not "is the box ticked" any more — see :meth:`_resolve_patch_by_patch`.
        This one answer drives about ten downstream UI behaviours through
        ``_spot_session``, so it has to agree with the flag the command is
        actually built from, or the tab renders a strip session over a spot
        read.
        """
        return self._resolve_patch_by_patch(self._current_mode())

    # ------------------------------------------------------------------
    # Patch-by-patch: the resolver decides, the widget only shows (#159)
    # ------------------------------------------------------------------
    #: Snapshot of the user's own patch-by-patch state while the CR30 lock is
    #: engaged: ``{"guided": (checked, tooltip), "manual": (checked, tooltip)}``,
    #: or ``None`` when the lock is off. Taken ONCE on the way in, exactly like
    #: ``TabChart._pre_cal_snapshot`` — engaging twice must never overwrite the
    #: user's values with the forced ones.
    _pbp_lock_snapshot: "dict | None" = None

    def _resolve_patch_by_patch(self, mode: str) -> bool:
        """Whether *mode* reads patch by patch.

        **The resolver decides; the widget only shows.** This is
        :meth:`_resolve_bidir_value`'s contract, and it is here for the same
        reason: there are nine readers of "patch by patch" in this tab and its
        stores, and locking only the checkbox would leave the stale-state paths
        (Save as Defaults, the Manual preset, the per-target store, the two
        global keys) disagreeing with the read that is actually running.

        A CR30 chart is always True. ChromIQ reads that instrument itself, one
        patch at a time — the helper takes the spot branch unconditionally under
        ``-x`` — and Basti's ruling is that the user cannot deselect it, in
        either module. Keyed on the CHART and nothing else: this tab has no
        notion of a selected instrument (`_chart_instrument_code` states the
        rule), and the sheet in the user's hand is what decides.
        """
        if self._chart_is_cr30():
            return True
        cb = self._pbp_cb if mode == "guided" else self._m_pbp_cb
        return bool(cb.isChecked())

    def _pbp_user_value(self, mode: str) -> bool:
        """The user's OWN patch-by-patch choice, ignoring the CR30 lock.

        What every *saved* copy of the setting must be written from. Without
        this, one press of "Save as Defaults" on a CR30 chart writes a forced
        tick into ``measure_patch_by_patch`` / ``manual2_chartread_pbp``, which
        are the globals that seed **every target that has nothing stored** — so
        every future non-CR30 run would open in patch-by-patch, a slow, wrong
        read nobody asked for. The same for a Manual preset, which then carries
        it into whatever chart it is later applied to.

        The per-target store may keep the forced value: it belongs to one run,
        and a run's chart does not change instrument.
        """
        snap = self._pbp_lock_snapshot
        if snap is not None and mode in snap:
            return bool(snap[mode][0])
        cb = self._pbp_cb if mode == "guided" else self._m_pbp_cb
        return bool(cb.isChecked())

    def _set_pbp_user_value(self, mode: str, value: bool) -> None:
        """Load a stored patch-by-patch value without fighting the lock.

        While the lock is on, a restore (global defaults, a Manual preset) must
        land in the snapshot — where it becomes what comes back when a non-CR30
        chart is loaded — and NOT on screen, where it would show an unticked box
        over a read that is ticked.
        """
        snap = self._pbp_lock_snapshot
        if snap is not None and mode in snap:
            _was, tip = snap[mode]
            snap[mode] = (bool(value), tip)
            return
        cb = self._pbp_cb if mode == "guided" else self._m_pbp_cb
        cb.setChecked(bool(value))

    #: Chartread options a CR30 cannot honour. Under `-xx` the helper opens no
    #: instrument, so everything that configures one is inert — the helper's own
    #: comment says as much of `-c`, `-N`, `-B`/`-b` and `-T`. Confirmed against
    #: the helper source, and against the instrument's own phone app, which
    #: offers no measurement condition and no UV filter at all: there is nothing
    #: on this device for these to configure, so they can never be made to work.
    #:
    #: `-F` is the one that had to stop being SENT rather than merely greyed.
    #: Proved against the real helper: with `-F 6` the measurement file comes
    #: back carrying `INSTRUMENT_FILTER "D65"` although no instrument was ever
    #: opened and the CR30 has no filter — a false claim about how the data was
    #: gathered, written into the user's own record of it.
    CR30_DEAD_OPTIONS = ("highres", "filter", "tolerance", "xrga")

    def _refresh_calm_subtext(self) -> None:
        """The panel's one line of advice has to match how you actually read.

        *"Scan each strip with a slow, steady motion"* is the right thing to
        say to somebody holding an i1 Pro over a printed row. It is the wrong
        thing to say to somebody holding a CR30, which reads ONE PATCH AT A
        TIME: there is no strip to scan and no motion to make — you rest it on
        the highlighted patch and press its own button. Found on screen during
        review, on a real CR30 chart.
        """
        label = getattr(self, "_calm_subtext", None)
        if label is None:
            return
        try:
            label.setText(
                tr("Rest the instrument on the highlighted patch and press "
                   "its button.")
                if self._chart_is_cr30() else
                tr("Scan each strip with a slow, steady motion."))
        except RuntimeError:            # the widget is gone with its tab
            pass

    def _cr30_aim_diameters_px(self) -> "tuple[float, float]":
        """(aperture, body) diameters in IMAGE pixels for this chart, or (0, 0).

        Scaled from the chart's own recorded dpi, never from an assumed one. A
        circle that claims to be 33 mm and is not is worse than no circle, so
        an unreadable sidecar returns zeros and the preview draws nothing.
        """
        if not self._chart_is_cr30():
            return 0.0, 0.0
        import json
        try:
            ti2 = self._chart_file_for(getattr(self, "_ti1_path", None))
            channels = Path(ti2).with_suffix(".channels.json")
            if not channels.is_file():
                return 0.0, 0.0
            dpi = float((json.loads(read_text(channels)).get("layout") or {})
                        .get("dpi") or 0.0)
            if dpi <= 0:
                return 0.0, 0.0
            from workflow.layout_engine.instruments import (
                CR30_APERTURE_DIAMETER_MM, CR30_BODY_DIAMETER_MM)
            per_mm = dpi / 25.4
            return (CR30_APERTURE_DIAMETER_MM * per_mm,
                    CR30_BODY_DIAMETER_MM * per_mm)
        except Exception:          # noqa: BLE001 — a drawing aid, never fatal
            log.debug("CR30: could not scale the aiming help", exc_info=True)
            return 0.0, 0.0

    def _apply_cr30_aim_visibility(self) -> None:
        """The aiming row belongs to the CR30 and to nothing else.

        Hidden -- label, checkbox and help icon together -- for every other
        instrument, because it would describe a body diameter that has nothing
        to do with what the user is holding. Routed through `_chart_is_cr30`
        like every other CR30 decision in this tab: a direct
        `read_target_instrument` answers "not a CR30" after every project
        reopen, and that mistake has been made twice here already.
        """
        show = bool(self._chart_is_cr30())
        for prefix in ("g", "m"):
            for name in (f"_{prefix}_aim_help", f"_{prefix}_aim_help_tip"):
                w = getattr(self, name, None)
                if w is not None:
                    w.setVisible(show)

    def _apply_cr30_dead_options(self) -> None:
        """Grey the options this instrument cannot honour, in both modules.

        DISABLE ONLY, NEVER UNTICK. The saved value belongs to the target and
        must survive for the day the same chart is measured with an instrument
        that does honour it — every save path reads the widget whether or not it
        is enabled. What actually falls silent is `build_args`.
        """
        is_cr30 = bool(self._chart_is_cr30())
        # The aiming row answers the SAME question at the SAME moment, so it is
        # refreshed from here rather than from three call sites of its own --
        # three that could drift apart, and one of which someone would forget.
        self._apply_cr30_aim_visibility()
        self._apply_active_view_settings()
        self._refresh_calm_subtext()
        why = tr(
            "Your CR30 cannot use this. ChromIQ reads this instrument itself, "
            "so ArgyllCMS never opens it and there is nothing here for this "
            "setting to change. Your choice is remembered for other "
            "instruments.")
        for opts in (getattr(self, "_chartread_opts", None) or [],
                     getattr(self, "_m_chartread_opts", None) or []):
            for opt in opts:
                if opt.key not in self.CR30_DEAD_OPTIONS:
                    continue
                opt.suppressed = is_cr30
                for w in (opt.checkbox, opt.widget, opt.row_widget):
                    if w is not None:
                        w.setEnabled(not is_cr30)
                if opt.checkbox is not None:
                    opt.checkbox.setToolTip(why if is_cr30 else "")

    def _apply_cr30_pbp_lock(self) -> None:
        """Show, in both modules, that a CR30 chart reads patch by patch.

        **Ticked and disabled, never hidden.** This tab's own rule, in capitals
        at ``_collect_guided``: *"NEVER FROM A CONTROL THE USER CANNOT SEE."* A
        hidden `-N` whose value was still sent ran every Guided measurement
        uncalibrated for a whole beta, and a hidden `-p` would be the same
        shape. A greyed box that reports the mode the read is genuinely in is
        not a dead control — it is what the Strip-recognition combo one row
        above already does.

        The tick **and the tooltip** are snapshotted and restored, following
        ``TabChart._apply_calibration_knobs``: the row must read as "not yours
        to set right now" rather than as an invitation, and the user's own
        setting has to come back exactly when a different chart is loaded.

        Safe to call as often as you like — it is the re-assert hook for chart
        changes and settings loads alike.
        """
        pairs = [("guided", getattr(self, "_pbp_cb", None)),
                 ("manual", getattr(self, "_m_pbp_cb", None))]
        if any(cb is None for _m, cb in pairs):
            return                       # called before the UI is built
        snap = self._pbp_lock_snapshot
        if self._chart_is_cr30():
            if snap is None:
                self._pbp_lock_snapshot = {m: (cb.isChecked(), cb.toolTip())
                                           for m, cb in pairs}
            for _m, cb in pairs:
                # Signals blocked: _LINKED_PAIRS mirrors these two in both
                # directions, and both are being set to the same value here
                # anyway. Blocking keeps the mirror out of the snapshot's way.
                cb.blockSignals(True)
                try:
                    cb.setChecked(True)
                    cb.setEnabled(False)
                    # A DISABLED CHECKBOX NORMALLY RENDERS AS UNCHECKED HERE.
                    # Both themes deliberately override the checked fill when a
                    # box is disabled (main_window.py's
                    # `QCheckBox::indicator:checked:disabled`, light_styles.py's
                    # `QCheckBox::indicator:disabled`) — correct for "this whole
                    # group is off", wrong for "this is on and not yours to
                    # change": the row then reads as switched OFF while the
                    # measurement is patch-by-patch (Basti saw exactly that,
                    # 2026-08-28). `#locked_on` keeps a muted accent fill so the
                    # tick still reads while the control stays obviously
                    # inactive.
                    cb.setObjectName("locked_on")
                    # objectName is part of the selector, so the box has to be
                    # re-polished for the new rule to take effect on a widget
                    # that already exists.
                    cb.style().unpolish(cb)
                    cb.style().polish(cb)
                    # The literal lives HERE, inside tr(), on purpose: tr() with
                    # a variable is invisible to scripts/i18n_extract.py, so the
                    # string would never reach a catalogue (the same note
                    # _apply_calibration_knobs carries).
                    cb.setToolTip(tr(
                        "This chart was made for the CR30, and ChromIQ reads "
                        "that instrument one patch at a time — it has no strip "
                        "reading to offer. So patch-by-patch is switched on for "
                        "you and cannot be turned off here; the box is ticked "
                        "so you can see the mode the measurement is really "
                        "in.\n\n"
                        "Load a chart made for a different instrument and this "
                        "option comes back exactly as you had it."))
                finally:
                    cb.blockSignals(False)
        elif snap is not None:
            for m, cb in pairs:
                was, tip = snap[m]
                cb.blockSignals(True)
                try:
                    cb.setChecked(bool(was))
                    cb.setEnabled(True)
                    # Drop the locked look with the lock. Left on, the box would
                    # read as "forced on" the next time it is disabled for some
                    # entirely different reason.
                    cb.setObjectName("")
                    cb.style().unpolish(cb)
                    cb.style().polish(cb)
                    cb.setToolTip(tip)
                finally:
                    cb.blockSignals(False)
            self._pbp_lock_snapshot = None

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
        if not self._is_verification_run():
            return None
        run = self._guard_run()
        if run is None:
            return None        # external chart / no project run — model doesn't apply
        if run.dir.parent.name != "runs":
            return None
        # The text is the catalogue's — Knut, beta.128: *"The S1.2 / S1.3 guard
        # windows: bring them into §M so the model owns their text."* This
        # method's job is to pick which of the two applies, nothing else.
        from workflow import measurement_messages as M

        if run.built_profile_icc().exists():
            # Hole 1 satisfied. Hole 2: a verification needs a verification chart
            # to measure. If the run has a profile but no verify chart yet, guide
            # the user to create one (a distinct message from Hole 1).
            if not run.has_verify_chart():
                return M.M_VERIFY_NO_CHART
            return None
        return M.M_VERIFY_NO_PROFILE


    #: How many lines of chartread output the log shows at once.
    _log_visible_lines = 9

    def _fit_log_height(self) -> None:
        """Size the log the same way every other log panel in the app is sized.

        QSS sets the log's family and size, and a stylesheet reaches a widget
        only at polish — so a height measured in __init__ is measured against
        the wrong font. This runs after polish and again on every style change,
        which is also what makes it follow a theme or font switch.

        It used to do that arithmetic itself, against a private line count.
        That made this the one panel that ignored the user's own size: dragging
        any other log resized every panel except this one, because nothing here
        went through the shared helper or registered with it.
        """
        log = getattr(self, "_log", None)
        if log is None:
            return
        from ui.widgets import fit_log_height
        fit_log_height(log)

    def changeEvent(self, event) -> None:      # noqa: N802
        super().changeEvent(event)
        from PyQt6.QtCore import QEvent as _QEvent
        if event.type() in (_QEvent.Type.StyleChange, _QEvent.Type.FontChange):
            self._fit_log_height()

    def set_calibration_mode(self, enabled: bool) -> None:
        """Hide guided mode toggle and lock to manual when calibration mode is active."""
        self._mode_row_widget.setVisible(not enabled)
        if enabled:
            self._switch_mode("manual")

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        """Re-tint the Stop button's disabled background for the active theme."""
        from ui.theme import accept_mode
        new_mode = accept_mode(mode)
        if new_mode == self._mode:
            return
        self._mode = new_mode
        if hasattr(self, "_stop_btn"):
            self._apply_stop_btn_style()
        if hasattr(self, "_import_box"):
            self._apply_import_box_style()

    def _apply_stop_btn_style(self) -> None:
        # The button keeps its light-grey "always-stand-out" base in both
        # themes; only the disabled state changes so it doesn't paint a
        # dark slab over the light tab background.
        #
        # AND THE THIRD APPEARANCE WAS GETTING EXACTLY THAT SLAB. The fold had
        # room for two answers, so Neutral took the dark branch: `#2a2a2a` on
        # `#e2e2e2`, 16,493 pixels of near-black button on the light-grey
        # Measure tab — and it is the DEFAULT state of the tab, because Stop is
        # disabled until a measurement is running. Every pixel census walked
        # straight past it, because `#2a2a2a` is a perfect grey: R = G = B,
        # chroma 0, invisible to an instrument that only looks for hue. Nothing
        # about the wrong LIGHTNESS of a grey is measurable that way, which is
        # the larger half of what those censuses could not see.
        #
        # Neutral answers with the shape the theme already uses for a disabled
        # control (`ui.widgets.disabled_button_qss`): no fill, DISABLED edge and
        # label. Light and Dark keep their four values untouched.
        from ui.theme import APPEARANCE_NEUTRAL
        if self._mode == APPEARANCE_NEUTRAL:
            from ui import neutral_styles as _n
            disabled_rule = (f"QPushButton:disabled {{ background: transparent;"
                             f" color: {_n.NM_DISABLED};"
                             f" border-color: {_n.NM_DISABLED}; }}")
        else:
            if self._mode == "light":
                disabled_bg     = "#eeeae5"
                disabled_fg     = "#a8a4a0"
                disabled_border = "#ccc9c3"
            else:
                disabled_bg     = "#2a2a2a"
                disabled_fg     = "#555555"
                disabled_border = "#333333"
            disabled_rule = (
                f"QPushButton:disabled {{ background: {disabled_bg};"
                f" color: {disabled_fg}; border-color: {disabled_border}; }}")
        self._stop_btn.setStyleSheet(
            "QPushButton { background: #f4f4f4; color: #121212; border: 1px solid #cccccc; font-weight: 600; }"
            "QPushButton:hover { background: #e0e0e0; border-color: #bbbbbb; }"
            + disabled_rule
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
        from ui.widgets import RevealFolderButton
        # "Load .ti2" MOVED TO THE MASTHEAD (#130, spec agreed 2026-07-31): one
        # button for the whole app, top-left, replacing the one that used to be
        # here and the one on the Print tab. The reveal-folder icon stays.
        self._reveal_btn = RevealFolderButton(_TAB_COLOR, top_widget)
        self._reveal_btn.setToolTip(tr(
            "Open this chart's folder in {manager} — where "
            "the chart, its measurements and the finished profile all live. "
            "Handy for finding the printable pages, or the ICC profile after "
            "you build it.").format(manager=file_manager_name()))
        self._reveal_btn.clicked.connect(self._reveal_chart_folder)
        _hdr_trailing = QWidget(top_widget)
        _ht = QHBoxLayout(_hdr_trailing)
        _ht.setContentsMargins(0, 0, 0, 0)
        _ht.setSpacing(6)
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
        # #133: IMPORT — file a measurement made in i1Profiler. Only a
        # verification run can use it, so the button is hidden until the shared
        # Run type says Verification (mirrors the Create Chart tab's
        # FROM PROFILE GAMUT button).
        self._import_btn = QPushButton(tr("IMPORT"), self._mode_row_widget)
        self._import_btn.setCheckable(True)
        self._import_btn.setObjectName("mode_btn")
        self._import_btn.setFont(_mode_font)
        self._import_btn.setVisible(False)
        self._guided_btn.clicked.connect(lambda: self._switch_mode("guided"))
        self._manual_btn.clicked.connect(lambda: self._switch_mode("manual"))
        self._import_btn.clicked.connect(lambda: self._switch_mode("import"))
        mode_row.addWidget(self._guided_btn)
        mode_row.addWidget(self._manual_btn)
        mode_row.addWidget(self._import_btn)
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
        # Both option lists exist now, so Guided can name what it fixes.
        self._update_guided_fixed_info()
        self._import_panel = self._make_import_panel()
        self._stack.addWidget(self._guided_panel)
        self._stack.addWidget(self._manual_panel)
        self._stack.addWidget(self._import_panel)
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
        headline = QLabel(calm_box)
        # An inline colour beats the stylesheet -- see ui.widgets.set_accent_html.
        set_accent_html(
            headline,
            tr("Keep calm<span style=\"color: {SPEC_GREEN}; font-style: italic;\">!</span>"),
            SPEC_GREEN=SPEC_GREEN)
        headline.setTextFormat(Qt.TextFormat.RichText)
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline.setStyleSheet(
            "background: transparent;"
            " font-family: Georgia; font-size: 28px;"
        )
        calm_layout.addWidget(headline)
        subtext = QLabel(tr("Scan each strip with a slow, steady motion."), calm_box)
        # Kept, because the sentence is only true for a strip-reading
        # instrument — see _refresh_calm_subtext.
        self._calm_subtext = subtext
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
        # Decoration, not a readout: the same five cells on every tab. One
        # ACTION value under Neutral, and the hue kept on each cell so a live
        # appearance switch repaints it -- see ui.widgets.spectrum_cell.
        for _color in TAB_COLORS:
            bar_row.addWidget(spectrum_cell(calm_outer, _color))
        bar_row.addStretch()
        calm_layout.addLayout(bar_row)
        co_layout.addWidget(calm_box)
        self._calm_outer = calm_outer
        lc_layout.addWidget(calm_outer)

        # Buttons — shared
        btn_outer = QWidget(left_container)
        bo_layout = QVBoxLayout(btn_outer)
        # 13 at the bottom, so the gap above the log matches every other tab.
        # On this tab the buttons are NOT the last thing before the log — a
        # sound row sits between them — so what the eye reads as "the gap
        # above the log" is this margin, not the button-to-log distance.
        # Top margin 8, not 6: measured with the real styling, this tab's
        # buttons sat 2px higher than every other tab's, so they shifted
        # slightly as you changed tab (Basti, 2026-08-07).
        bo_layout.setContentsMargins(16, 8, 16, 13)
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
        # #133: the IMPORT module's action button. It stands where Start
        # Measurement stands — same place, same weight — because it IS this
        # module's "start": the two are swapped by _refresh_import_controls.
        self._import_go_btn = QPushButton(tr("Import Measurement"), btn_outer)
        self._import_go_btn.setObjectName("primary")
        self._import_go_btn.setFixedHeight(36)
        self._import_go_btn.clicked.connect(self._on_import_measurement)
        self._import_go_btn.setVisible(False)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addWidget(self._import_go_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._save_defaults_btn)
        # THE BUTTONS ARE THE LAST THING BEFORE THE LOG, LIKE EVERY OTHER TAB.
        # Basti, 2026-08-07. The sounds switch used to sit between the two,
        # which pushed the buttons up and made this the one tab where they
        # were not level with the rest. Added AFTER the sound row below, so
        # the order on screen is: sounds, buttons, log.

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
        self._sound_tip = TooltipButton(
            tr("Play sounds during measurement"),
            tr("Plays a short sound at each step of a measurement — a tick as "
               "each patch is read, a bell when a strip is finished, a warning "
               "if a reading looks off, and a fanfare when the whole chart is "
               "done. It's a hands-free way to follow the measurement without "
               "watching the screen.\n\n"
               "Choose which sound plays for each event, and add your own, in "
               "Preferences → Sounds. This switch is remembered between "
               "sessions."),
            btn_outer, min_width=460)
        sound_row.addWidget(self._sound_tip)
        bo_layout.addLayout(sound_row)
        bo_layout.addLayout(btn_row)
        lc_layout.addWidget(btn_outer)

        # Log — shared
        log_outer = QWidget(left_container)
        # Named so hiding the log hides its margins with it — see
        # MainWindow._apply_log_visibility.
        log_outer.setObjectName("log_container")
        lo_layout = QVBoxLayout(log_outer)
        # 10 below the log, with the missing 2 px added OUTSIDE the wrapper
        # below — the mirror image of what every other tab needs. Here the
        # buttons live in their own container whose 13 px bottom margin is all
        # they get once the log is hidden, and 13 minus the buttons' 2 px
        # overflow left them at 11, higher than the log ever sat. Moving 2 px
        # out of the wrapper keeps them when the log goes, so both states end
        # on 13. Elsewhere the gap is *above* the log and the 2 px has to move
        # the other way, into the wrapper: see ui.widgets.add_log_row.
        lo_layout.setContentsMargins(16, 0, 16, 10)
        self._log = QPlainTextEdit(log_outer)
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        # Height in LINES, not pixels (Knut, beta.120: "only 6 lines of text
        # are visible, but showing 9 is better"). A pixel number cannot promise
        # a line count — the log's font comes from the stylesheet and is only
        # applied at polish — so it is measured from the widget's own metrics
        # once that has happened. See _fit_log_height.
        self._log_visible_lines = 9
        self._log.setPlaceholderText(tr("chartread output will appear here…"))
        lo_layout.addWidget(self._log)
        lc_layout.addWidget(log_outer)
        # The 2 px taken out of the wrapper above. Outside it, so it survives
        # the log being hidden and brings the buttons down to the same 13 px.
        lc_layout.addSpacing(2)

        # Status bar (replaces main-window status bar)
        self._status_bar_lbl = QLabel("", left_container)
        self._status_bar_lbl.setWordWrap(True)
        self._status_bar_lbl.setVisible(False)
        lc_layout.addWidget(self._status_bar_lbl)

        splitter.addWidget(left_container)

        # ---- Right preview ----
        right = QWidget(self)
        rl = QVBoxLayout(right)
        # Bottom 15 = the left panel's 13 px button margin + the 2 px spacing
        # outside its log wrapper, so with the log hidden the preview's
        # Prev/Next row ends level with the action buttons (Basti, 2026-08-09).
        # The pace area below contributes nothing while empty — see
        # _sync_pace_area_visible.
        rl.setContentsMargins(0, 0, 0, 15)
        rl.setSpacing(0)
        self._preview = TiffPreview(right)
        self._preview.stripe_clicked.connect(self._on_preview_strip_clicked)
        # The times are kept for the whole measurement, so turning to another
        # page of a multi-page chart must redraw them for THAT page (Knut,
        # #131 2026-07-26).
        # THE CLICKABLE STRIPS BELONG TO THE PAGE ON SCREEN, not to the page
        # the reader is on. See _on_preview_page_changed.
        self._preview.page_changed.connect(self._on_preview_page_changed)
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
        # Knut's layout (#131, 2026-07-27): a framed panel that looks like every
        # other one in the window, its title naming the chart's strip length; a
        # clear gap above it so the page buttons are not crammed against it; the
        # frame's left and right edges lined up with PREV and NEXT; and the
        # warning line BELOW the frame, as a label of its own — as part of the
        # panel it was the first thing a squeeze removed, which is why he lost
        # sight of it three times.
        pace_area = QWidget(right)
        pa = QVBoxLayout(pace_area)
        # 12 px left/right is the preview's own nav-row margin, so the frame
        # lines up with the PREV and NEXT buttons above it.
        pa.setContentsMargins(_PACE_SIDE_MARGIN, _PACE_GAP,
                              _PACE_SIDE_MARGIN, 0)
        pa.setSpacing(_PACE_GAP)

        self._pace_group = QGroupBox("", pace_area)
        self._pace_group.setFlat(True)
        pg = QVBoxLayout(self._pace_group)
        pg.setContentsMargins(8, 4, 8, 6)
        pg.setSpacing(0)
        self._pace_panel = StripTimesPanel(self._pace_group)
        pg.addWidget(self._pace_panel)
        self._pace_group.setVisible(False)
        pa.addWidget(self._pace_group)

        # The verdict. A real label, wrapped, with a floor under its height, so
        # no amount of squeezing can hide it again.
        self._pace_verdict_lbl = QLabel("", pace_area)
        self._pace_verdict_lbl.setWordWrap(True)
        self._pace_verdict_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter
                                            | Qt.AlignmentFlag.AlignVCenter)
        _vf = self._pace_verdict_lbl.font()
        _vf.setPointSizeF(_vf.pointSizeF() + 3)
        _vf.setBold(True)
        self._pace_verdict_lbl.setFont(_vf)
        self._pace_verdict_lbl.setVisible(False)
        pa.addWidget(self._pace_verdict_lbl)
        self._pace_area = pace_area
        # Empty, the area's _PACE_GAP top margin still pushed the Prev/Next row
        # ~10 px above the level every other action row sits at (Basti,
        # 2026-08-09) — so it only takes room when it has something to show.
        # The show/hide events of the two children keep it in step — see
        # eventFilter.
        pace_area.setVisible(False)
        self._pace_group.installEventFilter(self)
        self._pace_verdict_lbl.installEventFilter(self)
        rl.addWidget(pace_area)
        # Times measured so far, per strip letter, plus whether each passed.
        self._pace_times: dict = {}
        # #153: patch locations measured so far, plus what the run's own
        # measurement file already held when this chart was opened.
        self._progress_locs: set = set()
        self._progress_base = 0
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
            "For a chart ChromIQ reads itself — a CR30 — there is no chartread\n"
            "prompt, and this option instead decides whether ChromIQ offers\n"
            "you its own calibration window before the measurement starts.\n\n"
            "Enable this only if you have already calibrated the instrument\n"
            "earlier in the same session and do not want to repeat the step."),
        )
        self._nocal_cb.setVisible(False)
        # NOT PERSISTED, DELIBERATELY. Guided hides this control outright, and a
        # remembered `measure_no_cal` once ran every guided measurement
        # uncalibrated with nothing on screen to say so — beta.148, where every
        # patch came back "Reading is inconsistent". Guided does not offer the
        # option, so Guided does not store one. Only the Manual box below is
        # remembered (#156).
        _nocal_tip.setVisible(False)
        self._pbp_cb, _pbp_tip = _bool_row(
            tr("Patch-by-patch mode (-p)"), False,
            tr("Patch-by-Patch Mode (-p)"),
            tr("Switches from strip reading to single-patch measurement mode.\n\n"
            "Instead of scanning entire strips, chartread guides you patch\n"
            "by patch across the chart. This is significantly slower — one\n"
            "reading per patch — but more reliable on heavily textured\n"
            "surfaces or when strip reading consistently fails on a\n"
            "particular chart layout.\n\n"
            "RED OUTLINES WORK DIFFERENTLY HERE\n"
            "While you measure, a patch that looks like a misread is outlined "
            "in red. The two reading modes decide that differently, and "
            "deliberately so.\n\n"
            "Reading a STRIP, the whole strip arrives at once, so ChromIQ can "
            "ask two questions: is this patch past your colour-error limit "
            "(Preferences → Beta), AND does it stand out from the other patches "
            "of its own strip? Both must be true. That second question matters "
            "because a chart's expected colours are design values and a printer "
            "does not reproduce them — on a good print, vivid patches sit far "
            "from their design colour quite legitimately, and without the "
            "comparison half a normal chart would light up red.\n\n"
            "Reading PATCH BY PATCH, there is no strip to compare against — the "
            "patch you have just read is the only one that has arrived. So this "
            "mode asks the plainer question on its own: is this patch past your "
            "limit?\n\n"
            "What that means in practice: patch by patch flags MORE patches "
            "than strip reading does on the same chart, and vivid colours are "
            "among them. That is the honest consequence of having no "
            "neighbours to compare with — not a fault, and not something to "
            "read as \u201cyour printer is worse than the strips suggested\u201d. If it "
            "flags more than you want, raise the limit in Preferences → Beta."),
        )
        # SHOWN IN GUIDED (#160). It used to be hidden here while
        # `_collect_guided` still read it, so a stored preference put `-p` on
        # every Guided measurement with no control on screen to change it — the
        # same fault as the `-N` incident in beta.148, one line below its fix.
        #
        # Shown rather than hard-coded off, because it is genuinely useful to a
        # beginner: it is the documented remedy for a strip that keeps failing
        # and for textured stock, and §M-ALL-STRIPS-PATCHES-LEFT tells the user
        # to tick it to finish patches a strip read left behind.

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
            tr("Available when a Refine_Strips_N_<name>.txt file exists in\n"
            "the reports folder next to your chart.\n\n"
            "That file is created automatically by the Check & Refine\n"
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
        # Starts from the saved default (#134/#130): it used to be hard-coded
        # off, so even a saved default could not bring it back.
        self._overlay_cb.setChecked(
            bool(self._settings.get("measure_show_overlay", False)))
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
            lambda _state: self._sync_refine_rows())
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
                # -T IS NOT FORCED ON ANY MORE. It used to be ticked here at
                # 0.7 for everybody, and chartread hands that number to the
                # instrument, where it scales the driver's own
                # patch-recognition threshold while a strip is being swiped
                # (munki_imp.c:5353). Every measurement anybody made was
                # therefore judged stricter than the manufacturer's setting,
                # and on a ColorMunki that reads as a swipe the driver will not
                # recognise at all — Knut, beta.139: *"no strip is ever
                # finished without the 'Strip Read Failed' window"*. The row
                # stays visible so the option is still one tick away.
                opt.checkbox.setChecked(
                    bool(self._settings.get("measure_tolerance_enabled", False)))
                if opt.widget is not None:
                    opt.widget.setValue(
                        float(self._settings.get("measure_tolerance_value", 1.0)))
                    opt.widget.setEnabled(opt.checkbox.isChecked())
            # NO `else: hide the row` HERE, deliberately. Every key in
            # GUIDED_CHARTREAD_KEYS gets a row, and `_collect_guided` builds
            # every option Guided owns — so hiding one would put a flag on the
            # command line with no control on screen, which is exactly D2. A key
            # in the set is a key Guided offers, and it must be visible.

        ll.addWidget(adv_grp)

        # The "Profile verification" group that used to sit here is gone
        # (Knut, #130 2026-07-29): *"this frame, the checkbox, and the
        # information icon can be removed totally from the code"*. Under the
        # unified file handling the Profile-run bar's **Run type** decides
        # whether a read is a verification, and a second control saying the same
        # thing could only ever disagree with it.
        # WHAT GUIDED KEEPS FIXED — the same slot Create Chart's Guided box
        # occupies: on the panel itself, after the last group and before the
        # stretch, so it reads as a footnote to the whole panel rather than as
        # part of one group (Basti, on screen).
        self._guided_fixed_lbl = QLabel("", left)
        self._guided_fixed_lbl.setObjectName("info_measure")
        self._guided_fixed_lbl.setWordWrap(True)
        ll.addWidget(self._guided_fixed_lbl)

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

        # AIMING HELP — a CR30 row, hidden for every other instrument (#159).
        #
        # It is the only aiming aid there will be: the owner ruled on
        # 2026-08-30 that a patch smaller than the aperture is NOT refused at
        # layout time, because ArgyllCMS offers no such guard for any
        # instrument. So this shows the user what they are up against instead
        # of the app deciding for them.
        aim = QCheckBox(tr("Show where the instrument will sit"), row)
        aim.setChecked(True)          # on by default; the user's choice is kept
        # HIDDEN UNTIL A CHART SAYS OTHERWISE. `_apply_cr30_aim_visibility` is
        # reached through `_apply_cr30_dead_options`, which never runs at
        # construction -- so with no chart loaded the row stood there offering
        # help for an instrument nobody had mentioned.
        aim.setVisible(False)
        aim.toggled.connect(
            lambda _on, p=prefix: self._on_view_control_changed(p))
        aim_tip = TooltipButton(
            tr("Show where the instrument will sit"),
            tr("Turn this on and the patch you are being asked to read gets a "
            "dashed circle around it, drawn to scale: it is exactly how much "
            "of your chart the body of your CR30 will cover when you put it "
            "down.\n\nThat sounds like a small thing, and it is the whole "
            "difficulty of measuring by hand. The instrument is 33 mm across "
            "and completely hides the patch the moment you lower it onto the "
            "paper — so you cannot look at what you are aiming at while you "
            "aim. What you CAN do is line the circle up on screen first and "
            "note which neighbouring patches it touches, then place the "
            "instrument so those same neighbours are evenly covered. The "
            "circle is dashed so the patch edges you are aiming by stay "
            "visible through it.\n\nA second, much smaller circle appears "
            "only when there is a problem: it is the 4 mm measuring opening, "
            "and you will see it if the patch is too small for it. Then part "
            "of what the instrument reads is the neighbouring patch, and that "
            "reading will be wrong no matter how carefully you aim — build the "
            "chart again with larger patches — in Create Chart, either raise "
            "the patch size or ask for fewer patches, depending on which "
            "layout method you are using.\n\nThe circles appear while a "
            "measurement is running, on the patch you are being asked for. "
            "Before you press Start there is nothing to point at, so you "
            "will not see them yet.\n\nIt changes nothing about your "
            "measurements; it only draws on the preview. This option appears "
            "for the CR30 only — it is the one instrument ChromIQ always "
            "reads one patch at a time, by hand."),
            row)
        aim_tip.setVisible(False)
        aim_row = QHBoxLayout()
        aim_row.setContentsMargins(0, 0, 0, 0)
        aim_row.setSpacing(0)
        aim_row.addWidget(aim)
        aim_row.addSpacing(10)
        aim_row.addWidget(aim_tip)
        aim_row.addStretch(1)
        v.addLayout(aim_row)

        gv.addWidget(row)
        setattr(self, f"_{prefix}_aim_help", aim)
        setattr(self, f"_{prefix}_aim_help_tip", aim_tip)
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
            tr("Open this tab's presets folder in {manager}.\n"
            "Each preset is a plain .json file — copy one to a colleague\n"
            "and they can drop it into their own folder to share.").format(manager=file_manager_name())
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
            "  ▢  Open this tab's presets folder in {manager}.\n\n"
            "Select a preset from the dropdown to instantly restore all\n"
            "values. The Default entry always resets to built-in defaults.\n\n"
            "Presets are stored as plain .json files — one per preset —\n"
            "in a ChromIQ folder under your system's Preferences / AppData\n"
            "/ config location. Use the folder button (▢) on the right of\n"
            "the preset row to open it. To share a preset, copy the .json\n"
            "out of that folder and send it to a colleague; to install a\n"
            "shared preset, drop the .json into the matching folder on the\n"
            "target machine and ChromIQ will pick it up on the next launch.\n\n"
            "Presets persist between sessions.").format(manager=file_manager_name()),
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
            "For a chart ChromIQ reads itself — a CR30 — there is no chartread\n"
            "prompt, and this option instead decides whether ChromIQ offers\n"
            "you its own calibration window before the measurement starts.\n\n"
            "Enable this only if you have already calibrated the instrument\n"
            "earlier in the same session and do not want to repeat the step."),
        )
        self._m_nocal_cb.toggled.connect(self._persist_skip_calibration)
        self._m_pbp_cb = _bool_row_m(
            tr("Patch-by-patch mode (-p)"), False,
            tr("Patch-by-Patch Mode (-p)"),
            tr("Switches from strip reading to single-patch measurement mode.\n\n"
            "Instead of scanning entire strips, chartread guides you patch\n"
            "by patch across the chart. This is significantly slower — one\n"
            "reading per patch — but more reliable on heavily textured\n"
            "surfaces or when strip reading consistently fails on a\n"
            "particular chart layout.\n\n"
            "RED OUTLINES WORK DIFFERENTLY HERE\n"
            "While you measure, a patch that looks like a misread is outlined "
            "in red. The two reading modes decide that differently, and "
            "deliberately so.\n\n"
            "Reading a STRIP, the whole strip arrives at once, so ChromIQ can "
            "ask two questions: is this patch past your colour-error limit "
            "(Preferences → Beta), AND does it stand out from the other patches "
            "of its own strip? Both must be true. That second question matters "
            "because a chart's expected colours are design values and a printer "
            "does not reproduce them — on a good print, vivid patches sit far "
            "from their design colour quite legitimately, and without the "
            "comparison half a normal chart would light up red.\n\n"
            "Reading PATCH BY PATCH, there is no strip to compare against — the "
            "patch you have just read is the only one that has arrived. So this "
            "mode asks the plainer question on its own: is this patch past your "
            "limit?\n\n"
            "What that means in practice: patch by patch flags MORE patches "
            "than strip reading does on the same chart, and vivid colours are "
            "among them. That is the honest consequence of having no "
            "neighbours to compare with — not a fault, and not something to "
            "read as \u201cyour printer is worse than the strips suggested\u201d. If it "
            "flags more than you want, raise the limit in Preferences → Beta."),
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
            tr("Available when a Refine_Strips_N_<name>.txt file exists in\n"
            "the reports folder next to your chart.\n\n"
            "That file is created automatically by the Check & Refine\n"
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
        self._m_overlay_cb.setChecked(
            bool(self._settings.get("measure_show_overlay", False)))
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
            lambda _state: self._sync_refine_rows())
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
            "a misread, or when Check & Refine has flagged strips worth a "
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
            "pbp":        self._pbp_user_value("manual"),
            # "Live preview" view controls (#126) — preview-only, but saved so a
            # preset restores the whole workspace look the user prefers.
            "overlay_mode":  self._m_overlay_mode.currentData(),
            "only_measured": self._m_only_measured.isChecked(),
            "aim_help": self._m_aim_help.isChecked(),
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
        self._set_pbp_user_value("manual", bool(data.get("pbp", False)))
        # "verify" in an older preset is ignored: the checkbox it drove is gone.
        _om = self._m_overlay_mode.findData(data.get("overlay_mode", "both"))
        if _om >= 0:
            self._m_overlay_mode.setCurrentIndex(_om)
        self._m_only_measured.setChecked(bool(data.get("only_measured", False)))
        # ON unless this preset says otherwise: the aiming help is the CR30's
        # only aid, so a preset written before it existed must not switch it
        # off for someone who has never seen it.
        self._m_aim_help.setChecked(bool(data.get("aim_help", True)))
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
            self._set_pbp_user_value(
                "manual", bool(s.get("manual2_chartread_pbp", False)))
            _om = self._m_overlay_mode.findData(s.get("manual2_overlay_mode", "both"))
            if _om >= 0:
                self._m_overlay_mode.setCurrentIndex(_om)
            self._m_only_measured.setChecked(bool(s.get("manual2_only_measured", False)))
            self._m_aim_help.setChecked(bool(s.get("manual2_aim_help", True)))
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
        """Guided's chartread options — **the same definitions Manual uses**,
        narrowed to the few a beginner benefits from (#160).

        Guided therefore *owns* only what it offers, which is what makes
        `_collect_guided` correct by construction: it can no longer build a flag
        the user cannot see. Before this, five hidden rows were still collected —
        ticking them in Manual and measuring in Guided produced
        ``-H -F 5 -T 0.7 -l -L -A N`` with nothing on the Guided panel to say so,
        and "Save as Defaults" then baked them into every future target.

        NOT filtered on ``isVisible()``: on a tab that has not been shown yet,
        even the row Guided *does* offer reports ``isVisible() == False``, so a
        visibility test would silently drop ``-T`` — a wrong measurement created
        by the fix meant to prevent wrong measurements.
        """
        return self._make_manual_chartread_options(parent, GUIDED_CHARTREAD_KEYS)

    def _update_guided_fixed_info(self) -> None:
        """Name the options Guided keeps fixed, in its information box.

        Derived from the one option table at run time (see
        :func:`guided_fixed_option_labels`), so it can never fall out of step
        with what Guided actually builds — the failure this box exists to
        prevent.
        """
        lbl = getattr(self, "_guided_fixed_lbl", None)
        if lbl is None:
            return
        fixed = guided_fixed_option_labels(getattr(self, "_m_chartread_opts", []))
        if not fixed:
            lbl.setVisible(False)
            return
        lbl.setVisible(True)
        # "standard settings", not "recommended values": Guided simply does not
        # send these flags, so ArgyllCMS's own defaults apply. Saying we chose a
        # value would be a small lie about who decided.
        # Same shape as the Create Chart Guided box (tab_chart.py:9166): a
        # heading line, then the specifics, then what to do about it. One long
        # paragraph is harder to scan and does not match the reference.
        lbl.setText(
            tr("Guided leaves these at their standard settings:") + "\n"
            + " · ".join(fixed) + "\n"
            + tr("Need one of them? Switch to MANUAL at the top — "
                 "it gives you every option."))

    def _make_manual_chartread_options(
            self, parent: QWidget,
            keys: "set[str] | None" = None) -> list[_ChartreadOption]:
        """**The** chartread option definitions. Both modules are built from
        here (#160).

        *keys* limits which options are created; Guided passes
        :data:`GUIDED_CHARTREAD_KEYS` so it owns only the options it offers.
        Everything else — labels, tooltips, ranges, defaults — is therefore
        written once, and the two modules cannot drift apart.

        They did drift: `-n` existed only in Manual, so the Guided↔Manual mirror
        (which pairs by key) silently skipped it. Note what this fixes and what
        it does not — `-n` is still Manual-only, so measuring in Guided still
        saves spectral data. The difference is that Guided no longer *pretends*
        to carry the option: it is named in Guided's information box as one of
        the settings Manual owns, instead of appearing to be honoured and not
        being.
        """
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

        _tol_spin = _spinbox(0.1, 10.0, 0.1, 0.7, decimals=1)
        if keys is not None:
            # GUIDED KEEPS THE STANDARD INPUT HEIGHT for this one control.
            # `_spinbox` names every box `compact_input`, which the themes pin
            # to 22 px — and removing that from this spinbox in Guided is a fix
            # that shipped in 3.1.2 and is in the CHANGELOG. Merging the two
            # option tables silently reverted it; this keeps it.
            _tol_spin.setObjectName("")

        opts.append(_ChartreadOption(
            key="tolerance", flag="-T",
            label=tr("Patch consistency tolerance (-T)"),
            tooltip_title=tr("Patch consistency tolerance (-T)"),
            tooltip_body=(
                tr("How much colour variation ChromIQ accepts WITHIN a\n"
                "single patch.\n\n"
                "Reading a strip, your instrument does not take one reading\n"
                "per patch — it takes many as it slides along, then divides\n"
                "them up. It can then compare the readings that belong to the\n"
                "same patch. On an evenly printed patch they agree closely. If\n"
                "they disagree by more than this tolerance, the strip is\n"
                "rejected and you are asked to read it again.\n\n"
                "WHY THAT IS WORTH HAVING\n"
                "Patches that are not an even colour are telling you something\n"
                "about the print, not about your scanning: a nozzle starting\n"
                "to clog, ink running low, a toner roller leaving banding, a\n"
                "sheet that was handled. Catching that while you measure is\n"
                "much cheaper than discovering it in a finished profile — and\n"
                "the better the print you measure, the better the profile you\n"
                "get. That is why this is switched on by default.\n\n"
                "CHOOSING A VALUE\n"
                "The number multiplies your instrument's own built-in\n"
                "threshold, so 1.0 means exactly what the manufacturer set.\n"
                "ChromIQ starts you at 0.7, a little stricter than that, which\n"
                "has proved comfortable in practice: it still accepts quite\n"
                "large variation and catches real problems.\n\n"
                "  • Lower (0.4–0.7) — stricter, and a useful thing to want.\n"
                "      You are told sooner when a patch is uneven, so a poor\n"
                "      print gets reprinted rather than profiled. The cost is\n"
                "      re-reading a strip more often, especially on textured\n"
                "      or matte papers where the surface itself varies.\n\n"
                "  • Higher (1.0–2.0) — more forgiving. The right choice for\n"
                "      coarse-screened media, fabric, canvas and art papers,\n"
                "      and for laser printers, whose patches vary more than an\n"
                "      inkjet's by nature. Raise it if you are being asked to\n"
                "      re-read strips that look perfectly good to you;\n"
                "      ArgyllCMS suggests 1.5 or 2.0 where the default is\n"
                "      unreasonably tight for the medium.\n\n"
                "There is no single right answer — it depends on your printer,\n"
                "your paper and your instrument. Start at the default; if you\n"
                "are stopped on strips that look fine, raise it a little, and\n"
                "if you want earlier warning about print quality, lower it a\n"
                "little.\n\n"
                "Only some instruments support this (the i1 Pro and ColorMunki\n"
                "families do); on others it is quietly ignored.")
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

        if keys is not None:
            # Only hand back what this module offers, and destroy the widgets
            # for the rest: a value widget parented here but never put in a
            # layout would still be painted, in the corner of the panel.
            keep = [o for o in opts if o.key in keys]
            for o in opts:
                if o.key not in keys and o.widget is not None:
                    o.widget.setParent(None)
                    o.widget.deleteLater()
            return keep
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
        # #153: pick this chart up where it was left, from its own .ti3.
        self._reset_progress()
        # Only when there is a laid-out chart to read. chartread measures the
        # `.ti2` — it is the file that says where each patch sits on the sheet —
        # so without one there is nothing a measurement could do.
        #
        # Knut, #130 2026-08-04: *"Can a chart read at all be initiated if a ti2
        # file does not exist? I thought it could not. Thus the Start
        # Measurement button should not be available at all."* He was right
        # about what should happen and, as it turned out, wrong about what did:
        # the tab is loaded from the `.ti1` in one path (a project opened with
        # no `.ti2`), and Start was offered anyway. Measured, not assumed —
        # the button was enabled and chartread would have failed.
        self._start_btn.setEnabled(self._chart_file_for(path).exists())
        self._update_start_tooltip()
        self._try_load_tiffs(path)
        self._update_resume_availability()
        self._update_precond_availability()
        self._refresh_bidir_autodetect()
        # The chart decides patch-by-patch for a CR30 (#159), and set_ti1_path
        # is where the chart changes: project open, Profile-run and Run-type
        # changes, and every cross-tab load all arrive here. Same place, same
        # reason as the -B auto-detect one line above.
        self._apply_cr30_pbp_lock()
        self._apply_cr30_dead_options()
        # #134 / K1 (Knut): the overlay auto-offer is a MEASURE-tab feature, but
        # set_ti1_path is also driven cross-tab — the Print tab's ti2_loaded, the
        # Check tab's ti2_found, project open, session restore and Profile-run /
        # Run-type bar changes all call it. Only pop the offer when the Measure
        # tab is actually the one on screen, so it never appears over Create Chart
        # or Print Chart.
        if is_new_chart:
            if self.isVisible():
                # Deferred for the same reason as the showEvent path below: a
                # modal opened straight out of a selection change blocks inside
                # the layout that change started, and the window comes up over a
                # partly painted tab (Knut, #130 2026-07-28).
                self._queue_overlay_offer()
            else:
                # …but a chart loaded from Create Chart or Print Chart used to
                # lose the offer altogether: it was made while another tab was
                # on screen, suppressed, and never revisited (Knut, #131
                # 2026-07-28 — he expected it in exactly those two workflows).
                # Hold it instead, and make it when this tab is next shown.
                self._pending_overlay_offer = True

    def showEvent(self, event) -> None:            # noqa: N802 — Qt name
        """Offer the existing measurement whenever this tab comes on screen.

        The #134 rule stands — the window must never appear over Create Chart or
        Print Chart — and "not now" must not mean "never", which is why loading
        a chart in either of those tabs and then coming here used to be silent
        (Knut, #131 2026-07-28).

        Knut settled the trigger itself on #130, 2026-07-29. It used to need a
        *changed* .ti2 path, and he showed why that was wrong: **"Changing
        profile run naturally changes the path that the app sees, but from one
        specific run nothing has actually changed."** The window is
        informational — it tells you this run already holds readings and lets
        you choose what to do about them — so the moment it is useful is the
        moment you arrive at the Measure tab, whether you came from another run
        or from another tab of the same run. So: every time this tab is shown.
        The per-run "don't ask this again" tick is what keeps it from becoming
        noise while you work through one run.
        """
        super().showEvent(event)
        # Polish has run by now, so the log's stylesheet font is real and its
        # nine lines can be measured (Knut, beta.120).
        self._fit_log_height()
        # RE-READ THE MEASUREMENT FILE. Everything on this tab that depends on
        # the .ti3 — "Refine / resume existing measurement", its strips
        # sub-option, the overlay toggle — was decided the last time something
        # handed us a chart, and the file can change underneath that. Knut,
        # beta.147: *"If I now delete the ti3 file, so there are no measurement.
        # And then go out of the measure tab and in again, just to update
        # everything. Then the 'Refine / resume …' checkbox is still visible.
        # It is not supposed to show when there is no measurement to resume."*
        # Arriving at the tab is the moment to look again — the same reasoning
        # that puts the existing-measurement offer here.
        self._update_resume_availability()
        self._pending_overlay_offer = False
        # NOT here and now. Opening a modal window from inside showEvent blocks
        # before the tab has finished being painted, so the window comes up over
        # a half-drawn tab — Knut, #130 2026-07-28: "the whole main window
        # behind the popup warning window is half drawn… the right preview
        # panel is not at all drawn". Handing it to the event loop lets the tab
        # paint completely first, and the window then opens over a finished
        # screen.
        self._queue_overlay_offer()

    def _queue_overlay_offer(self) -> None:
        """Ask for the existing-measurement offer on the next turn of the event
        loop — at most once, however many things asked for it.

        Being shown and having a chart handed to us usually happen together
        (open a project, switch Profile run, come back from Print Chart), and
        each of them wants the offer. Without this the user would answer the
        same window twice in a row.
        """
        if getattr(self, "_offer_queued", False):
            return
        self._offer_queued = True
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._offer_existing_overlay_now)

    def _offer_existing_overlay_now(self) -> None:
        """Make the held offer, once the tab has actually painted."""
        self._offer_queued = False
        try:
            if self.isVisible():
                # An empty measurement is dealt with before anything else looks
                # at it. Knut set this sequence himself (#130, 2026-07-30):
                # *"When the ti3 has no readings, the warning window … appears,
                # then ti3 file is moved to old/ folder and window 'This chart
                # already has a measurement' never appears. When the ti3 has
                # readings, the file is not touched and only window 'This chart
                # already has a measurement' appears, with all the text and
                # choices that previously was defined."*
                #
                # NO LONGER ARCHIVED AT TAB-OPEN — §3a owns this file.
                #
                # Two rulings of Knut's meet here. Beta.110: a session that
                # measured nothing must archive the file it left behind, *"right
                # after measurement session was exited/stopped/completed"* —
                # still done, at the end of a session (_on_measure_done).
                # Extending it to files FOUND at tab-open was my addition, and
                # it pre-empts the model: §3a's "header only" and "empty" rows
                # say such a file is answered at **Start Measurement**, with
                # M-REPLACE-UNCOUNTABLE, which is the message that says what is
                # true — *"ChromIQ cannot tell how many readings it contains"* —
                # rather than claiming a measurement exists, which was his July
                # complaint. Archiving it here made that message unreachable:
                # the file was gone before Start could mention it (beta.132,
                # Demo-05 step 1). Raised on the issue; the reviewed model wins
                # until he says otherwise.
                # Stranded readings next: recovering them is what makes the
                # already-measured offer below have anything to offer (#130).
                self._recover_stranded_partial()
                self._maybe_offer_existing_overlay()
        except Exception:      # noqa: BLE001 — never break showing the tab
            log.warning("Could not offer the existing measurement", exc_info=True)

    def _recover_stranded_partial(self) -> bool:
        """Put a stranded engine partial measurement back as the run's ``.ti3``,
        after asking. Returns True when readings were recovered.

        Knut, #130 2026-07-30: *"I loaded a project that had a run with a file
        'Test-Profiling-P.ti3.engine-partial'. But the measure tab did not
        register that it had a partial measurement… A partial stored measurement
        should be allowed to be continued on, and show overlay, and get warned."*

        He is right, and there were two faults behind it. The backup was being
        orphaned when a re-generation archived the measurement it belonged to
        (fixed in :meth:`core.file_manager.Run.reset_chart_artefacts`), and
        nothing ever read a backup back — so readings that exist on disk were
        unreachable, which is the opposite of why the copy is taken.

        Recovering it as the ordinary ``.ti3`` is deliberately the whole fix:
        every existing feature — the resume tick, the overlay, the
        already-measured window — then works without knowing this file was ever
        special. Nothing is overwritten, because this only runs when there is no
        measurement there.
        """
        if self._ti1_path is None or self._runner.is_running:
            return False
        from core.file_manager import Run
        try:
            run = Run.for_dir(self._ti1_path.parent)
            partial = run.recoverable_partial_ti3()
        except Exception:      # noqa: BLE001 — never break loading a chart
            return False
        if partial is None:
            return False
        if partial in getattr(self, "_partial_declined", set()):
            return False
        # A backup with no readings in it is not a recovery — it is an empty file
        # that would then be reported as a measurement. Knut, #130 2026-07-30:
        # his partial held nothing, ChromIQ "recovered" it, and the overlay then
        # blamed a chart mismatch. Say plainly that there is nothing to carry on
        # from, and leave the run without a measurement, which is the truth.
        if _cgats_has_no_readings(partial):
            if not hasattr(self, "_partial_declined"):
                self._partial_declined = set()
            self._partial_declined.add(partial)
            self._log.appendPlainText(tr(
                "An interrupted measurement left a backup file for this chart, "
                "but it holds no readings — nothing was recorded before it "
                "stopped, so there is nothing to carry on from. Measure the "
                "chart when you are ready; the backup file is left where it is."))
            return False

        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("Part of this chart has already been measured"))
        box.setText(tr(
            "Some readings for this chart were saved when a measurement stopped "
            "early, and they are still here — but they are sitting in a backup "
            "file rather than in the run's own measurement, so ChromIQ has been "
            "ignoring them.\n\n"
            "Recover them and they become this run's measurement, exactly as if "
            "the earlier session had ended there: you can carry on where it "
            "stopped, see what was read as an overlay on the chart, and you will "
            "be warned before anything replaces them. The backup file is kept "
            "either way.\n\n"
            "Nothing is overwritten — this run has no measurement of its own at "
            "the moment."))
        recover = box.addButton(tr("Recover the readings"),
                               QMessageBox.ButtonRole.AcceptRole)
        leave = box.addButton(tr("Leave them alone"),
                              QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(recover)
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        fit_message_box_buttons(box)
        box.exec()
        if box.clickedButton() is not recover:
            # Asked and declined: don't ask again for this file while the app runs.
            if not hasattr(self, "_partial_declined"):
                self._partial_declined = set()
            self._partial_declined.add(partial)
            _ = leave
            return False
        import shutil
        try:
            shutil.copy2(partial, run.measurement_ti3)
        except OSError as exc:
            warn(
                self, tr("Could not recover the readings"),
                tr("The readings are still safe in the backup file, and nothing "
                   "has been changed.\n\nReason: {reason}").format(reason=str(exc)))
            return False
        log.info("recovered stranded engine partial %s -> %s",
                 partial.name, run.measurement_ti3.name)
        self._log.appendPlainText(tr(
            "Recovered the readings from an interrupted measurement — they are "
            "now this run's measurement, and you can carry on from where it "
            "stopped."))
        self._update_resume_availability()
        return True

    def _resume_is_set_on_the_panel(self) -> "bool | None":
        """What the Measure panel currently says about refine/resume.

        ``None`` when neither control exists yet, so the caller can fall back to
        the remembered answer. Guided and Manual are linked, so either one
        answers for both; guided is asked first because it is the default view.
        """
        for name in ("_resume_cb", "_m_resume_cb"):
            cb = getattr(self, name, None)
            if cb is not None:
                return bool(cb.isChecked())
        return None

    def _maybe_offer_existing_overlay(self) -> None:
        """#134: when a freshly-loaded chart already has a measurement, show a
        small dialog offering BOTH choices as checkboxes (Basti): see it as an
        overlay, and/or refine/resume it so a new read doesn't replace it — with
        a clear warning about replacement. The last choice is remembered.

        Knut ruled (#131, 2026-07-28) that this window is right to appear when
        you switch Profile run or Run type — *"scenario 4: keep it"* — and that
        it should carry the same per-run silence as the replace warning, so a
        run you are working through stops asking while every other run, and the
        same run tomorrow, still does.
        """
        if self._existing_ti3_for_chart() is None:
            return
        if self._runner.is_running:
            return          # never over a measurement in progress
        # Two routes can queue this in the same turn of the event loop — being
        # shown, and a chart arriving while shown. Only one window, ever.
        if getattr(self, "_offer_open", False):
            return
        scope_now = self._replace_warning_scope()
        if scope_now is not None and scope_now in self._offer_silenced:
            return
        from PyQt6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                                     QLabel, QVBoxLayout)
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("This chart already has a measurement"))
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        # #130 (Knut, beta.120): the overlay is drawn from the ChromIQ reading
        # engine's per-patch reporting, so with stock chartread there is only
        # ONE choice here — and the window has to stop describing two.
        engine_on = self._engine_selected()
        intro = QLabel(tr(
            "A measurement (.ti3) already exists for this chart, so anything "
            "you measure here builds on readings that are already saved. "
            "Choose what you'd like to do — you can change either of these any "
            "time from the options panel:") if engine_on else tr(
            "A measurement (.ti3) already exists for this chart, so anything "
            "you measure here builds on readings that are already saved. "
            "Choose what you'd like to do — you can change this any time from "
            "the options panel:"), dlg)
        intro.setWordWrap(True)
        lay.addWidget(intro)

        # THIS WINDOW ONLY OPENS WHEN THE CHART YOU JUST LOADED ALREADY HAS A
        # MEASUREMENT (#134). That is a state, not a screen, so nothing that
        # opened the app and walked the tabs has ever drawn it — and it carried
        # three separate hues into a colourless theme: the tab's green on every
        # checkbox tick, a near-black info box (`#181818`, the dark branch of a
        # two-answer fold) and an amber warning line.
        from ui.theme import APPEARANCE_NEUTRAL, accent_for, resolve_mode
        _dlg_mode = resolve_mode(self._settings.get("appearance", "auto"))
        # Tint the checkboxes with the Measure tab's green accent (the app fills
        # a checked indicator with the accent; per-tab code overrides :checked).
        # `accent_for` collapses that to the theme's single ACTION in Neutral
        # and hands the green back untouched in Light and Dark.
        _cb_accent = accent_for(_TAB_COLOR, _dlg_mode)
        _green_cb_css = (
            "QCheckBox::indicator:checked { background:%s; border-color:%s; }"
            "QCheckBox::indicator:hover { border-color:%s; }"
            % (_cb_accent, _cb_accent, _cb_accent))
        # Info boxes under each choice — neutral boxed frame matching the
        # post-measurement / "calibration complete" dialogs (see
        # _on_calibration_done): gray surface, gray border, default text.
        # NB: object name is NOT "info" — the global stylesheet paints QLabel#info
        # magenta-on-dark (a different kind of callout). Use our own name so the
        # neutral frame fully wins, text colour included.
        if _dlg_mode == APPEARANCE_NEUTRAL:
            from ui import neutral_styles as _n
            _info_bg, _info_bd, _info_fg = (_n.NM_BG_SURFACE, _n.NM_BORDER,
                                            _n.NM_TEXT_DIM)
        elif _dlg_mode == "light":
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
        if engine_on:
            lay.addWidget(show_cb); lay.addWidget(show_sub)
        else:
            # Kept alive (the caller reads its state) but never shown, and
            # forced off so a stale saved preference cannot switch on a feature
            # this engine does not have.
            show_cb.setChecked(False)
            show_cb.setVisible(False); show_sub.setVisible(False)

        resume_cb = QCheckBox(
            tr("Refine / resume this measurement (keep the strips already "
               "measured)"), dlg)
        resume_cb.setStyleSheet(_green_cb_css)
        # OPEN SHOWING WHAT THE PANEL ALREADY SAYS.
        #
        # Seeding this purely from the remembered answer let the window
        # contradict the options behind it. Basti, 2026-08-08: he asked
        # Check & Refine to guide him through a refinement, which ticks
        # "Refine / resume" and the strips file — and this window then opened
        # with resume UNTICKED. Pressing OK applies these two values, so it
        # would have quietly cancelled the refinement he had just asked for.
        #
        # The panel is the truth of what will run, so the window starts from it
        # and the remembered preference only supplies the default when the panel
        # has nothing set. That also makes the memory per run rather than global,
        # because the panel's own value comes from the run's stored settings.
        _panel_resume = self._resume_is_set_on_the_panel()
        resume_cb.setChecked(bool(_panel_resume) if _panel_resume is not None
                             else bool(self._settings.get("overlay_prompt_resume", False)))
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
        # The amber was decoration: the line already opens with a warning glyph
        # and spells out, in words, that an untick REPLACES the measurement. It
        # is already bold, so the emphasis survives without it.
        set_ink(warn, "#c8781e", " font-weight:600;", level="main")
        lay.addWidget(warn)

        # What each button does, spelled out — Knut, #131 2026-07-28: "Make
        # sure the actions/consequences of each window's buttons are explained
        # for all windows."
        buttons_note = QLabel(tr(
            "What each button does:\n\n"
            "•  OK — applies the two choices above to this chart. Nothing is "
            "measured and nothing is written yet; you still press Start "
            "Measurement when you are ready.\n\n"
            "•  Cancel — changes nothing at all. The chart stays loaded, your "
            "existing measurement is untouched, and both settings stay as they "
            "were. You can set either of them later in the options panel.")
            if engine_on else tr(
            "What each button does:\n\n"
            "•  OK — applies the choice above to this chart. Nothing is "
            "measured and nothing is written yet; you still press Start "
            "Measurement when you are ready.\n\n"
            "•  Cancel — changes nothing at all. The chart stays loaded, your "
            "existing measurement is untouched, and the setting stays as it "
            "was. You can set it later in the options panel."), dlg)
        buttons_note.setWordWrap(True)
        buttons_note.setObjectName("overlay_note")
        buttons_note.setStyleSheet(_info_css)
        lay.addWidget(buttons_note)

        # The same per-run, session-only silence as the replace warning — his
        # ruling on scenario 4: "keep it and implement the same per-run 'don't
        # ask again' I specified."
        scope = self._replace_warning_scope()
        ask_cb = None
        if scope is not None:
            ask_cb = QCheckBox(self._offer_silence_label(), dlg)
            ask_cb.setStyleSheet(_green_cb_css)
            ask_cb.setToolTip(tr(
                "Only for this one run, and only until you close ChromIQ. Every "
                "other run keeps asking, and so does this one the next time you "
                "start the program."))
            lay.addWidget(ask_cb)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel, dlg)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)

        from PyQt6.QtWidgets import QDialog as _QD
        self._offer_open = True
        try:
            accepted = dlg.exec() == int(_QD.DialogCode.Accepted)
        finally:
            self._offer_open = False
        if not accepted:
            return
        # Remembered only when the user went ahead — ticking and then
        # cancelling means "not this time", not "never ask me again".
        if ask_cb is not None and ask_cb.isChecked() and scope is not None:
            self._offer_silenced.add(scope)
            log.info("Existing-measurement offer silenced for %s (this session)",
                     scope)
        want_overlay = show_cb.isChecked()
        want_resume = resume_cb.isChecked()
        # Remember the choice for next time.
        self._settings.set("overlay_prompt_show_overlay", want_overlay)
        self._settings.set("overlay_prompt_resume", want_resume)
        # THE CONTROLS THIS WINDOW DECIDES MUST EXIST BEFORE THEY ARE SET.
        #
        # This used to assume the resume box was already on screen, and it is
        # only put there by _update_resume_availability(), which last ran
        # whenever the chart was loaded — before the measurement was recovered,
        # or while it was archived. So the window could offer a choice about a
        # measurement and then set it on a hidden control. Knut, beta.128, both
        # halves of it: with resume OFF, *"the measure tab options area is
        # missing the 'Refine / Resume ...' checkbox, although the ti3 file is
        # present"*; with resume ON, *"the measure tab options area is missing
        # the 'Refine / Resume ...' checkbox (but the 'Use refinement strips
        # file for guided re-measurement' is visible)"* — because ticking a
        # hidden box still let _sync_refine_rows show the sub-option under it.
        #
        # And his question — *"The visibility … is controlled on activating the
        # measure tab, but in addition also when the window comes up. Is that
        # correct?"* — has one answer: visibility is decided in ONE place, from
        # the file on disk. This window sets values and asks for that decision
        # to be re-made; it never decides visibility itself.
        self._update_resume_availability()
        # Apply: overlay toggle (paints, or explains + unticks if not placeable).
        self._sync_overlay_checkboxes(want_overlay)
        self._on_overlay_toggled(want_overlay)
        # Refine/resume: tick the resume box in both modes, now that it is there.
        for cb in (self._resume_cb, self._m_resume_cb):
            if cb is not None and cb.isVisibleTo(self):
                cb.setChecked(want_resume)
        # AND THIS ANSWER OUTRANKS AN EARLIER REFINEMENT INSTRUCTION.
        #
        # `start_guided_refinement` arms the ticks so a settings load cannot
        # undo them (beta.197). This window is the user saying, later and
        # explicitly, what they want for this chart — so the arming has to go,
        # or the next settings load would put resume back on over the top of
        # their answer and the box would stop describing what the app runs.
        # Basti, 2026-08-08: *"as long as the settings chosen there are
        # correctly reflecting what is used in the app it is fine"*.
        self._refinement_armed_for = None
        self._sync_refine_rows()

    def set_chart_notice(self, text: "str | None") -> None:
        """Show guidance in the preview when there's no chart to measure for the
        selected Profile-run / Run-type (#130, Knut)."""
        self._preview.set_notice(text)

    def clear_chart_file(self) -> None:
        self._ti1_path = None
        self._reset_progress(from_files=False)
        self._averaging_active = False
        self._ti1_lbl.setText(tr("No file selected"))
        self._ti1_lbl.setStyleSheet("color: #909090; font-size: 11px;")
        self._start_btn.setEnabled(False)
        # …and SAY WHY. This is the path a Run-type switch takes when the new
        # target has no chart — the very case where the greyed button needs its
        # explanation — and it left the tooltip from the previous chart, or
        # none at all. Found by walking the demo package on screen: "Start
        # Measurement is greyed out … hover it" showed an empty tooltip.
        self._update_start_tooltip()
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
        # Both keywords are written by the LAYOUT stage and live in the .ti2:
        # TARGET_INSTRUMENT, and printtarg's RANDOM_START. Opening a project
        # hands this tab run.chart_ti1, where neither exists — so an unresolved
        # read cost an i1Pro chart its automatic -b (force_bidir_for_instrument
        # never saw the name) and reported the chart as non-randomised, after
        # ANY project reopen. Not a CR30 fault; resolve the sibling like every
        # other reader on this tab.
        chart = self._chart_file_for(self._ti1_path)
        if self._ti1_path is not None and chart.exists():
            instr = read_target_instrument(chart)
            randomized = is_randomized(chart)
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
            else:
                # SAY SO WHEN THE CHART NAMES NOBODY — otherwise ArgyllCMS
                # speaks for it, and says something untrue.
                #
                # Driven on screen 2026-08-30 with a chart carrying no
                # TARGET_INSTRUMENT: Argyll's own line claims "chart is for
                # GretagMacbeth i1 Pro", which is its INTERNAL DEFAULT and not
                # anything in the file — verified, the file names nothing. That
                # line reaches the user through the log, and this branch was
                # silent, so nothing corrected it. A user could reasonably
                # believe their chart is committed to an instrument it has
                # never heard of, and buy or borrow one to match.
                msg = tr(
                    "Chart instrument: this chart does not name one. ChromIQ "
                    "will measure it with whichever instrument you have "
                    "connected. ArgyllCMS may still say the chart is for a "
                    "GretagMacbeth i1 Pro further down — that is its own "
                    "assumption when a chart is silent, not something written "
                    "in your file.")
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
        combo = ElidingComboBox(parent)
        # Guided mode shows a full-size (non-compact) combo; Manual keeps the
        # compact styling that matches its other dense option rows.
        #
        # NO PINNED WIDTH. It used to be `setMinimumWidth(240)` here and 210 for
        # Manual — English measurements, and a hard FLOOR for the whole row.
        # With the label on one side and the Auto toggle and two ⓘ on the other,
        # that row could not go below 540 px in Spanish, 536 in Portuguese and
        # 529 in French, against the 540 the Measure pane has; so this tab
        # scrolled sideways in exactly those three languages, which is what
        # `scripts/i18n_onscreen_audit.py` had been reporting as
        # "es 590, pt 586, fr 579 into a 572 px viewport" and nobody had traced.
        # An ElidingComboBox still takes the width of its longest entry wherever
        # there is room — the same width the pinned number was approximating —
        # and gives it back when there is not.
        if mode == "manual":
            combo.setObjectName("compact_input")
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
        # Whatever is painted on the preview describes the chart that was
        # showing a moment ago, and this method runs exactly when that chart
        # may have stopped being the current one — a different .ti2, a
        # different profiling run, or the same chart re-generated underneath.
        # Knut, #131 2026-07-28: he measured one strip of a 3-column chart,
        # re-generated it with 4 columns, and the old strip stayed painted on
        # top of the new one — then followed him into every other run he
        # switched to. The painting is discarded here and re-established below
        # from whatever the *current* chart actually has.
        self._discard_stale_overlay()
        if self._ti1_path is None:
            for cb, tip, rcb in [
                (self._resume_cb,   self._resume_tip,   self._refine_cb),
                (self._m_resume_cb, self._m_resume_tip, self._m_refine_cb),
            ]:
                cb.setVisible(False)
                tip.setVisible(False)
                cb.setChecked(False)
                # "Use refinement strips file" is a sub-option OF the resume
                # tick, so it goes wherever its parent goes. It used only to be
                # greyed, which left it standing under a hidden parent (Knut,
                # #130 2026-07-30).
                rcb.setVisible(False)
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
        # A measurement file with NO READINGS must not offer "Refine / resume":
        # chartread is then asked to resume FROM that file and rejects it with
        # "Field SAMPLE_LOC is wrong type - corrupted file ?" — an error no user
        # can act on. Knut worked this out himself (#130, 2026-07-30): the empty
        # file keeps its BEGIN_DATA_FORMAT naming SAMPLE_LOC but has no rows, and
        # unticking resume made the error disappear because the file was replaced.
        # The overlay is hidden for the same reason: there is nothing to draw.
        has_ti3 = ti3.exists() and not _cgats_has_no_readings(ti3)
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
        # #130 (Knut, beta.120): and only with the ChromIQ reading engine. The
        # overlay is drawn from the engine's per-patch reporting, which stock
        # chartread does not provide — *"All 'Show overlay...' related
        # functionality is not supported for the stock argyllcms chartread
        # measurement engine and must be removed and in OFF state"*.
        show_overlay = has_ti3 and self._engine_selected()
        for ocb, otip in [(self._overlay_cb, self._overlay_tip),
                          (self._m_overlay_cb, self._m_overlay_tip)]:
            ocb.setVisible(show_overlay); otip.setVisible(show_overlay)
            if not show_overlay:
                ocb.setChecked(False)
        # The box remembers its setting, so after loading a project it can come
        # up already ticked — and nothing painted the overlay, so the preview
        # stayed empty until it was switched off and on again (Knut, #131
        # 2026-07-27). Paint it now, so what the box says is what you see.
        if show_overlay:
            self._restore_overlay_after_measurement()
        # Auto-detect Refine_Strips file — reports/ since #127, with a
        # fallback to the flat pre-v2 location (an external chart folder that
        # never went through project migration may still hold one there).
        # THE NEWEST ONE, and the old unnumbered name still counts. The strip
        # list is numbered now (`Refine_Strips_2_<stem>.txt`) so a second check
        # cannot destroy the first one's list, and a file written by an older
        # version has no number at all — both are looked for, newest first.
        from core.file_manager import reports_subdir
        _stem = self._ti1_path.stem

        def _newest_refine(folder):
            # The stem sits in the MIDDLE here, so this is the one place
            # `stem_files` does not fit and the literal is escaped by hand: a
            # project called `Chart [v2]` would otherwise find no re-measure
            # list at all, and one called `Chart*A` would offer another
            # project's.
            found = sorted(files_matching(
                folder,
                "Refine_Strips_*_" + glob_escape(_stem) + ".txt"),
                           key=lambda q: q.stat().st_mtime)
            plain = folder / f"Refine_Strips_{_stem}.txt"
            if plain.exists():
                found.append(plain) if not found else found.insert(0, plain)
            return found[-1] if found else None

        refine_file = (_newest_refine(reports_subdir(self._ti1_path.parent))
                       or _newest_refine(self._ti1_path.parent))
        if refine_file is not None and refine_file.exists():
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
        if not has_ti3:
            for rcb in (self._refine_cb, self._m_refine_cb):
                rcb.setChecked(False)
        self._sync_refine_rows()
        self._refresh_start_button_label()

    def _sync_refine_rows(self) -> None:
        """Show the "use refinement strips file" row, ⓘ and all, or hide it whole.

        Knut, #130 2026-07-30: *"'Refine / resume..' and 'Show overlay...' are
        hidden, but the sub-level checkbox 'Use refinement strips file ....'
        still shows"* — a lone sub-option under nothing. Then, 2026-08-01, the
        other half of the same fault: *"the 'Refine...' checkbox is an empty
        space, but its help icon is there and present."*

        Both came from the row and the checkbox inside it being decided in two
        different places. The row followed the resume tick; the checkbox
        followed whether a measurement exists. Tick resume while the checkbox
        was hidden and the row appeared holding nothing but its help icon —
        which is what he saw, because its ⓘ is added straight to the layout and
        so was never hidden with it.

        One decision now, for both modes: the row is on screen when there is a
        measurement to refine AND the resume option it belongs to is ticked.
        """
        ti3 = (self._ti1_path.with_suffix(".ti3")
               if self._ti1_path is not None else None)
        has_ti3 = bool(ti3 and ti3.exists() and not _cgats_has_no_readings(ti3))
        for row, resume, cb in ((self._refine_row, self._resume_cb,
                                 self._refine_cb),
                                (self._m_refine_row, self._m_resume_cb,
                                 self._m_refine_cb)):
            if row is None or resume is None:
                continue
            # THE ROW, never the checkbox on its own. The row carries the help
            # icon too, so hiding it takes the whole sub-option off screen;
            # hiding just the checkbox is what left the icon behind in an empty
            # space. Anything inside the row is therefore left visible — the row
            # decides, once, for all of it.
            row.setVisible(bool(has_ti3 and resume.isChecked()))
            if cb is not None and cb.isHidden():
                cb.setVisible(True)

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

    def _start_button_name(self) -> str:
        """What the Start button ACTUALLY says right now.

        It reads "Continue Measurement" whenever the resume box is ticked
        (`_refresh_start_button_label`), so any message that hard-codes "Start
        Measurement" names a button the user cannot see. Ask the button.
        """
        btn = getattr(self, "_start_btn", None)
        try:
            return btn.text() if btn is not None else tr("Start Measurement")
        except RuntimeError:            # the widget is gone; the name is not
            return tr("Start Measurement")

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
        # REMEMBER WHY THESE ARE TICKED, so a settings load cannot untick them.
        #
        # Basti, 2026-08-08: *"i wanted to be guided through refinement …the
        # options were selected …but after confirming the message they were
        # deselected again"*, in both Guided and Manual. `load_target_settings`
        # restores `resume` from the run's stored Measure settings — or calls
        # `_restore_defaults()` when the run has none stored — and `resume` is
        # linked between the two modules, so either path silently undoes both
        # ticks. Whoever wins is then a matter of ordering, which is why it
        # looked like the pop-up did it: a QMessageBox runs a nested event loop,
        # so a load can complete while the window is up.
        #
        # The tick is an instruction from Check & Refine, not a preference, so
        # it outranks the stored value until the user leaves this chart.
        self._refinement_armed_for = self._chart_identity()

    def _reassert_guided_refinement(self) -> None:
        """Put the refinement ticks back after a settings load, while they apply.

        Self-disarming: the arming records which chart the instruction was for,
        so loading a different chart — or regenerating this one — drops it
        without anyone having to remember to clear the flag.
        """
        armed = getattr(self, "_refinement_armed_for", None)
        if armed is None:
            return
        if armed != self._chart_identity():
            self._refinement_armed_for = None
            return
        for cb in (getattr(self, "_resume_cb", None),
                   getattr(self, "_m_resume_cb", None)):
            if cb is not None and not cb.isChecked():
                cb.setChecked(True)
        if getattr(self, "_refine_strips_path", None) is not None:
            for cb in (getattr(self, "_refine_cb", None),
                       getattr(self, "_m_refine_cb", None)):
                if cb is not None:
                    cb.setEnabled(True)
                    if not cb.isChecked():
                        cb.setChecked(True)

    def _try_load_tiffs(self, base_path: Path) -> None:
        # ONE strip, by name: `with_suffix("").stem` stripped twice, turning
        # "X-w10.0mm.ti2" into "X-w10" and widening the glob below to any
        # chart sharing that prefix (core/stem_paths.py).
        stem   = without_ext(without_ext(base_path, ".ti2"), ".ti1").name
        folder = base_path.parent
        tiffs  = stem_files(folder, stem, "*.tif")
        if tiffs:
            self._tiff_pages = tiffs
            self._preview.load_tiff(tiffs)
            self._setup_stripe_rects()
        else:
            self._tiff_pages = []
            self._page_stripe_rects = []
            self._strips_per_page = []
            # And the per-patch geometry, which is built in _setup_stripe_rects
            # and so is only ever REPLACED on the branch above. Left behind, the
            # previous chart's boxes stayed live for a chart that has no preview
            # at all: _locate_patch would answer with a rect belonging to a
            # different sheet, and the split-patch overlay would draw this
            # chart's colours at the last chart's coordinates.
            self._patch_boxes = []
            self._preview.set_page_patch_boxes({})
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
        # A CR30 chart has no swipe either, so the arrow goes — but its patches
        # are square, so it must NOT borrow the hex zigzag to achieve that
        # (#159). Read from the chart, like everything else on this path — via
        # _chart_is_cr30, which resolves the .ti2 the keyword actually lives in.
        self._preview.set_no_swipe(self._chart_is_cr30())

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

    def _persist_skip_calibration(self, on: bool) -> None:
        """Kept as a no-op: this setting belongs to the target, not to the app.

        The first fix for Knut's report (#156) wrote Manual's "Skip initial
        calibration" into a single global preference the moment it was ticked.
        That stopped the symptom and was the wrong shape — `per_target_settings.md`
        §0 is explicit that one value several places can write is the fault
        itself: *"having fields change randomly because some other
        run-specification changed something is similar to a global parameter in
        a programming code where several actors can change that parameter, but
        not know when or where."*

        A global write here also leaks between runs in the one direction that is
        hardest to notice: it is what a target with nothing stored opens on, so
        ticking the box on one run would quietly change what a brand-new run
        starts with.

        The real cause was that **Start Measurement never wrote the tab's
        settings at all** (§3 W8) — see `_on_start`. With that wired, this
        setting is stored against its own run like every other control on the
        panel, and nothing global is needed.
        """
        return

    def _on_sound_toggled(self, on: bool) -> None:
        """Master switch for measurement sounds (#131): persist it so it's
        remembered, and pre-load the selected sounds when turning it on so the
        first play during a measurement isn't delayed by a disk read."""
        self._settings.set("sound_enabled", on)
        if on and getattr(self, "_sound", None) is not None:
            # DISARMING DURING A MEASUREMENT SILENCES IT.
            #
            # arm() pre-loads the clips; disarm() leaves measurement mode, and
            # Sound.play() then drops everything that is not a completion or
            # window sound. Switching the master on WHILE measuring therefore
            # turned the measurement's own sounds off — Knut, beta.133: *"Enabling
            # of 'Play sounds during measurement' does NOT enable the sounds when
            # measuring. Error sound comes on Reading Failure window, but when
            # clicking instrument button the sound is no longer present."* The
            # window sound survived because windows are exempt from that gate.
            self._sound.arm(reading_engine=self._engine_wanted())
            if not getattr(self, "_session_live", False):
                self._sound.disarm()      # preload only; no measurement running

    def _engine_wanted(self) -> bool:
        """Whether this measurement will run on ChromIQ's own reading engine.

        The manager settles it when the run starts (it can still fall back to
        stock chartread if the instrument refuses), but the sounds are armed
        before that — so the preference is read here and corrected if a fallback
        happens (see :meth:`_on_engine_fell_back`).
        """
        try:
            # A STRING IS ALWAYS TRUTHY. The setting holds "argyll" or
            # "chromiq", so bool() of it was True either way — which armed the
            # sounds as if the engine were running even on stock chartread,
            # where ChromIQ deliberately stays quiet because Argyll beeps for
            # itself (Knut, #131 2026-07-27). Same comparison as
            # _engine_selected(), which is the one that was right.
            return str(self._settings.get("chartread_engine", "argyll")) == "chromiq"
        except Exception:      # noqa: BLE001
            return False

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
                    # Resolve to the .ti2 — the keyword is not in the .ti1, so a
                    # reopened project used to fall through to the i1Pro rate.
                    key = model_key(read_target_instrument(
                        self._chart_file_for(self._ti1_path)))
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
        # How close to the limit still counts as "close" (#149). A percentage
        # of this instrument's own limit, so one setting is right for every
        # instrument however fast each one has to be read.
        try:
            marginal_pct = float(self._settings.get("pace_marginal_percent", 10.0))
        except (TypeError, ValueError):
            marginal_pct = 10.0
        marginal_pct = max(0.0, min(100.0, marginal_pct))
        # 0 = off for this instrument: a rate of 0 makes samples_for() return
        # None and target_seconds fall back to a threshold nothing can trip.
        if min_samples <= 0:
            return PaceConfig(min_samples=0, sample_hz=0.0,
                              min_patch_seconds=0.0,
                              marginal_percent=marginal_pct)
        return PaceConfig(min_samples=min_samples, sample_hz=hz,
                          min_patch_seconds=0.0,
                          marginal_percent=marginal_pct)

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
            # The device has answered: the startup wait is over.
            self._saw_instrument = True
        self._warn_if_instrument_does_not_match_chart(model)

    def _blocked_by_stock_chartread_for_cr30(self) -> bool:
        """Refuse to start a CR30 measurement while Preferences selects stock
        ArgyllCMS chartread — and offer the one setting that fixes it.

        The CR30 chart carries ``TARGET_INSTRUMENT "CR30"``, the honest name the
        device reports for itself (#159, Basti's ruling). ChromIQ's own
        chartread fork accepts that name; **stock ArgyllCMS chartread does
        not** — it matches the keyword against its own instrument table and
        fatals before a patch is read, which is exactly the abrupt cut-off Knut
        reported on #130 and which the sibling guard
        ``_blocked_by_unusable_target_instrument`` exists to prevent.

        That sibling can no longer catch this: "CR30" had to go into
        ``KNOWN_INSTRUMENTS`` for a CR30 measurement to be possible at all, and
        with it there the sibling's message ("ArgyllCMS … does not know this
        one") would be silenced for the one case where it is still true. So the
        two guards split the question: the sibling asks *does ChromIQ know this
        name*, this one asks *can the reader the user has chosen actually use
        it*.

        Offering the switch rather than only naming it: the setting lives in
        Preferences → Measurement, several clicks away from a user who has just
        pressed Start, and there is exactly one right answer for this chart.
        Declining cancels — a measurement that cannot succeed must not begin.
        The **text** comes from ``workflow/measurement_messages.py`` (§M); this
        method only renders it.
        """
        if self._ti1_path is None or self._engine_selected():
            return False
        if not self._chart_is_cr30():
            return False

        if not self._cr30_stock_reader_window():
            self._log.appendPlainText(tr(
                "Measurement not started: a CR30 chart needs ChromIQ's own "
                "chart reader, and Preferences is set to ArgyllCMS chartread."))
            return True
        self._settings.set("chartread_engine", "chromiq")
        self._log.appendPlainText(tr(
            "Chart-reading engine switched to ChromIQ's own reader, so this "
            "CR30 chart can be measured."))
        # Same refresh the Settings dialog triggers, so the engine-only UI
        # follows the setting immediately instead of at the next restart.
        try:
            self.refresh_engine_visibility()
        except Exception:      # noqa: BLE001 — the setting is what matters
            log.debug("refresh_engine_visibility failed after the CR30 switch",
                      exc_info=True)
        return False

    def _blocked_by_the_instrument_being_in_use(self) -> bool:
        """Refuse to start while another window is holding the instrument.

        M-INSTRUMENT-BUSY (§M-PROPOSED). Tools ▸ *Read single patches* can now
        read a CR30 with ChromIQ's own driver, and that reader is NOT A
        PROCESS: `ArgyllRunner.is_running`, which every other guard in this app
        asks, answers from process state and cannot see it at all.

        The failure this prevents is not an error message. Over Bluetooth a
        CR30 accepts one connection and stops advertising once it is taken;
        over USB two openers interleave their bytes on one port. And the
        instrument holds its last reading indefinitely and hands it back to
        whoever asks — so what the second session gets is a plausible colour
        belonging to the first one's patch, written into a .ti3 in silence.

        Only asked for a chart this app reads itself. Two ArgyllCMS sessions
        already exclude each other through the process guard above, and a
        ColorMunki chart read while a CR30 spot session is open is two
        different instruments doing two different jobs.
        """
        if not self._chart_is_cr30():
            return False
        from core import instrument_lease
        where = instrument_lease.held_by_other(
            getattr(self, "_cr30_reader", None))
        if where is None:
            return False
        self._instrument_busy_window(where)
        return True

    def _instrument_busy_window(self, where: str) -> None:
        """M-INSTRUMENT-BUSY on screen. Split from the decision above so the
        decision can be driven without a modal standing in front of it."""
        from PyQt6.QtWidgets import QMessageBox
        from core import instrument_lease
        from workflow import measurement_messages as M
        from ui.widgets import fit_message_box_buttons
        title, body = M.M_INSTRUMENT_BUSY.render(
            where=instrument_lease.where_label(where))
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        fit_message_box_buttons(box)
        box.exec()

    def _cr30_stock_reader_window(self) -> bool:
        """Show §M's M-CR30-STOCK-READER and return True when the user accepts
        the switch to ChromIQ's own chart reader.

        Kept apart from the guard above so this method holds nothing but the
        window: the **text** comes from ``workflow/measurement_messages.py``
        (§M) and the only literals here are the two button labels. The guard's
        log lines are sentences of its own, which is fine in a log and is not
        fine in a window — ``tests/test_message_catalogue.py`` draws that line
        for us, and this split is how the window stays on the right side of it.
        """
        from PyQt6.QtWidgets import QMessageBox

        from workflow import measurement_messages as M
        title, body = M.M_CR30_STOCK_READER.render()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(body)
        use = box.addButton(tr("Use ChromIQ's reader and measure"),
                            QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(use)
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        fit_message_box_buttons(box)
        box.exec()
        return box.clickedButton() is use

    def _blocked_by_unusable_target_instrument(self) -> bool:
        """Refuse to start when the chart's ``TARGET_INSTRUMENT`` is not a name
        ArgyllCMS recognises — and say so properly.

        Knut, #130 2026-07-30: *"chartread: Error - Unrecognised chart target
        instrument 'i1Pro' … Normally, it is allowed to measure anyway, but here I
        am cut off abruptly without any warning or message, beside the log info
        that is a bit hidden."*

        He is right on both counts. chartread maps that keyword to a device by an
        exact string match and refuses the whole run if it does not know the
        value, so the measurement was doomed before a patch was read — and ChromIQ
        let it start anyway, then ended the session with nothing on screen but a
        raw tool error in the log.

        This is checked BEFORE anything is armed, because a run that cannot
        possibly succeed should never begin. The chart itself is easy to repair —
        only the keyword is wrong — so the window offers to do it rather than
        leaving the user with an unmeasurable file and no way forward.
        """
        if self._ti1_path is None:
            return False
        from ui.ti2_loader import KNOWN_INSTRUMENTS, read_target_instrument
        # TARGET_INSTRUMENT is a .ti2 keyword — a .ti1 is a patch set and never
        # carries it. Reading the tab's path raw therefore answered None on a
        # REOPENED project (the one route that hands this tab the .ti1), so the
        # repair window silently never appeared for exactly the users who had
        # closed the app and come back.
        chart = self._chart_file_for(self._ti1_path)
        try:
            name = read_target_instrument(chart)
        except Exception:      # noqa: BLE001 — never block a read on this check
            return False
        if name is None or name in KNOWN_INSTRUMENTS:
            return False       # absent is fine: ArgyllCMS then uses its default

        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("This chart names an instrument ArgyllCMS cannot use"))
        box.setText(tr(
            "The chart file records the instrument it was laid out for, and this "
            "one says “{found}”. ArgyllCMS matches that name exactly, and it does "
            "not know this one — so it would refuse the measurement before "
            "reading a single patch, whichever instrument you have connected.\n\n"
            "This is only the name in the file: the patches, the layout and your "
            "measurements are all fine. ChromIQ can correct the name for you, "
            "and then the chart measures normally.\n\n"
            "Charts ChromIQ creates itself always carry a name ArgyllCMS knows, "
            "so this usually means the file came from somewhere else."
        ).format(found=name))
        fix = box.addButton(tr("Correct the name and measure"),
                            QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(fix)
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        fit_message_box_buttons(box)
        box.exec()
        if box.clickedButton() is not fix:
            self._log.appendPlainText(tr(
                "Measurement not started: this chart names the instrument "
                "“{found}”, which ArgyllCMS does not recognise.").format(found=name))
            return True
        if not self._repair_target_instrument(chart, name):
            return True
        return False           # repaired — carry on and measure

    def _repair_target_instrument(self, ti2, found: str) -> bool:
        """Rewrite an unusable ``TARGET_INSTRUMENT`` to the ArgyllCMS name for the
        same family. Returns True when the chart is now measurable.

        Only the keyword line is touched, and only when the family is clear from
        the name itself — guessing which device a chart was laid out for would be
        far worse than saying we cannot tell.
        """
        import re
        from ui.ti2_loader import KNOWN_INSTRUMENTS
        low = found.lower().replace(" ", "")
        wanted = None
        # Checked first, and it is the one repair that does NOT make the chart
        # readable by ArgyllCMS: "CR30" is the name ChromIQ itself uses, so a
        # near-miss ("ChnSpec CR30", "CR-30") becomes the exact name our own
        # reader matches on. Whether the SELECTED reader can use it is the
        # separate question _blocked_by_stock_chartread_for_cr30 asks, and it
        # runs before this guard (#159).
        if "cr30" in low or "cr-30" in low:
            wanted = next(n for n in KNOWN_INSTRUMENTS if n == "CR30")
        elif "colormunki" in low or "i1studio" in low or "ccstudio" in low:
            wanted = next(n for n in KNOWN_INSTRUMENTS if "ColorMunki" in n)
        elif "spectroscan" in low:
            wanted = next(n for n in KNOWN_INSTRUMENTS if "SpectroScan" in n)
        elif "i1pro" in low or low in ("i1", "p3", "i1pro2", "i1pro3"):
            wanted = next(n for n in KNOWN_INSTRUMENTS if "i1 Pro" in n)
        if wanted is None:
            from PyQt6.QtWidgets import QMessageBox
            warn(
                self, tr("ChromIQ cannot tell which instrument this chart is for"),
                tr("The name in the file, “{found}”, does not say which device "
                   "the chart was laid out for, and guessing would be worse than "
                   "asking.\n\nCreate the chart again in the Create Chart tab "
                   "for the instrument you have, and nothing about this will come "
                   "up again. Your measurements are untouched."
                   ).format(found=found))
            return False
        try:
            for path in (ti2, ti2.with_suffix(".ti1"), ti2.with_suffix(".ti3")):
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                fixed = re.sub(r'TARGET_INSTRUMENT\s+"[^"]*"',
                               f'TARGET_INSTRUMENT "{wanted}"', text)
                if fixed != text:
                    path.write_text(fixed, encoding="utf-8")
                    self._log.appendPlainText(tr(
                        "Corrected the instrument name in {file} to “{name}”."
                        ).format(file=path.name, name=wanted))
        except OSError as exc:
            from PyQt6.QtWidgets import QMessageBox
            warn(
                self, tr("Could not correct the instrument name"),
                tr("Nothing was changed.\n\nReason: {reason}").format(reason=str(exc)))
            return False
        self._refresh_bidir_autodetect()
        return True

    def _chart_instrument_code(self) -> "str | None":
        """The family code the LOADED chart records, or None if it records none.

        printtarg writes TARGET_INSTRUMENT into the .ti2, not the .ti1, and the
        Measure tab loads the .ti1 — so the answer usually lives in the sibling
        file. Reading the chart is the whole point: the preference this used to
        consult says nothing about the sheet in the user's hand.
        """
        path = getattr(self, "_ti1_path", None)
        if path is None:
            return None
        from pathlib import Path as _P
        from data.patch_db import instrument_family_of
        from ui.ti2_loader import read_target_instrument
        candidates = [_P(path)]
        if _P(path).suffix.lower() != ".ti2":
            candidates.insert(0, _P(path).with_suffix(".ti2"))
        for cand in candidates:
            try:
                if not cand.is_file():
                    continue
                name = read_target_instrument(cand)
            except Exception:      # noqa: BLE001 — never block a read on this
                continue
            if name:
                return instrument_family_of(name)
        return None

    def _warn_if_instrument_does_not_match_chart(self, model: str) -> None:
        """Say so when the connected instrument is not the one the chart was
        made for (#130, Knut 2026-07-29).

        His case: a chart laid out for an i1Pro, measured with a ColorMunki
        connected — no window, no sound, and the strips are the wrong size for
        the device. There was nothing for ChromIQ to notice, either: ArgyllCMS
        reports a *capability* failure only when a device cannot do the KIND of
        reading asked of it, and both of these read reflective happily. The
        mismatch that matters here is between the chart's layout and the device,
        which only ChromIQ knows — so only ChromIQ can raise it.

        A warning, not a refusal: the reading may still be what the user wants
        (a spot check, a deliberate experiment), and the measurement is theirs
        to make.
        """
        try:
            # THERE HAS TO BE A CHART. The window says "the chart you are about
            # to measure", and `chart_instrument` is an app-wide setting, so
            # with no chart loaded the comparison is between a connected device
            # and a leftover preference — a warning about nothing, naming a
            # chart that is not there.
            #
            # It was reachable: opening the Measure tab with an instrument
            # connected and no chart raised it, and in the test suite it hung a
            # worker outright on a modal nobody could answer (the stack in the
            # #130 note of 2026-08-01). A warning that depends on state nobody
            # set is a warning that appears when it should not.
            if getattr(self, "_ti1_path", None) is None:
                return
            from data.patch_db import instrument_family_of, instrument_mismatch
            # ASK THE CHART, NOT THE PREFERENCE.
            #
            # This used to read `chart_instrument`, an app-wide setting whose
            # default is "i1" (core/settings.py). So the dialog's "the chart you
            # are about to measure was laid out for …" named whatever that
            # preference happened to hold — for anyone who had never set it,
            # always an i1Pro. Basti hit it on 2026-08-08 with a chart whose own
            # .ti2 says TARGET_INSTRUMENT "X-Rite ColorMunki": the app told him
            # it was made for an i1Pro and offered to cancel a measurement that
            # was perfectly fine.
            #
            # The .ti1 is the file the tab loads, and a .ti1 carries no
            # TARGET_INSTRUMENT — printtarg writes it into the .ti2. So look
            # beside it. The preference stays as a last resort, for a chart that
            # genuinely records nothing.
            chart_code = self._chart_instrument_code() or str(
                self._settings.get("chart_instrument", "") or "")
            pair = instrument_mismatch(chart_code, model)
            if pair is None:
                return
            chart_label, found_label = pair
            if getattr(self, "_mismatch_warned_for", None) == (chart_code, model):
                return
            self._mismatch_warned_for = (chart_code, model)
            self._cue_window("INSTRUMENT_ERROR")
            from PyQt6.QtWidgets import QMessageBox
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.NoIcon)
            title = tr("This chart was made for a different instrument")
            box.setWindowTitle(title)
            box.setText(title + "\n\n" + tr(
                "The chart you are about to measure was laid out for:\n"
                "    {chart}\n\n"
                "but the instrument connected is:\n"
                "    {found}\n\n"
                "Each instrument needs its own patch size and strip spacing, so "
                "reading this chart with that device will usually misread, "
                "skip strips, or fail to find the patches at all.\n\n"
                "What each button does:\n\n"
                "•  Measure anyway — goes ahead exactly as before. Use this if "
                "you know what you are doing, or to see what happens.\n\n"
                "•  Cancel — stops here so you can make a chart for this "
                "instrument, or connect the one this chart expects.").format(
                    chart=chart_label, found=found_label))
            go = box.addButton(tr("Measure anyway"),
                               QMessageBox.ButtonRole.AcceptRole)
            cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel)
            from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
            fit_message_box_buttons(box)
            # Nothing else may open over this until it is answered.
            self._pre_measure_window_open = True
            try:
                box.exec()
            finally:
                self._pre_measure_window_open = False
            # Anything that arrived while the question was open now has its turn.
            deferred = getattr(self, "_deferred_strip_error", None)
            if deferred is not None:
                self._deferred_strip_error = None
                self._on_strip_error(deferred)
            if box.clickedButton() is not go:
                self._manager.abort()
                # Measuring was declined, so a calibration for it would be a
                # window about something that is no longer happening.
                self._deferred_calibration = None
                return
            # "Measure Anyway": now, and only now, the measurement may raise the
            # windows of its own that were waiting behind this one.
            held = getattr(self, "_deferred_calibration", None)
            if held is not None:
                self._deferred_calibration = None
                self._on_calibration_prompt(*held)
        except Exception:      # noqa: BLE001 — never break a measurement
            log.warning("Could not check the instrument against the chart",
                        exc_info=True)

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
        # The swipe clock is consumed HERE whatever the preference says. Leaving
        # it set meant the next strip was timed from the failed swipe — so the
        # reading time it reported included however long the user spent in the
        # failure window before pressing Retry (Knut, #131 2026-07-27: "a strip
        # reading time is added below its column, where the time is depending on
        # how long time I waited to click Retry").
        started = getattr(self, "_scan_started_at", None)
        self._scan_started_at = None
        # Reading patch by patch there is no swipe to have been too quick, so
        # none of this applies — and its advice ("check that the swipe starts
        # before the first patch…") describes something the user is not doing
        # (Knut, #131 2026-07-27).
        if bool(getattr(self, "_spot_session", False)):
            return
        if not self._settings.get("pace_hint_enabled", True):
            return
        try:
            import time
            from core.measure_pace import failure_advice, failure_kind
            patches = getattr(self, "_last_strip_patches", 0)
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
            self._exec_measurement_window(dlg)
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
            # "All Strips Read" window must not appear — whether it arrived
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
        set_warning_icon(box)
        # macOS does not paint a window title on a message box, so the title has
        # to be IN the window to be readable — and a window you can name is a
        # window you can report (Knut, #131 2026-07-27: "This window also is
        # missing a title, add one, so that it easier to refer to it").
        box.setWindowTitle(tr("Stored chart differs"))
        box.setText(tr("Stored chart differs") + "\n\n" + tr(
            "This run already has a stored chart, and it is not the one you "
            "are about to measure."))
        extra = ""
        try:
            if Run.for_dir(run.dir).reads():
                extra = "\n\n" + tr(
                    "You are averaging several readings of this run. Replacing "
                    "the chart now would mean averaging readings taken from two "
                    "different sheets.")
        except Exception:      # noqa: BLE001
            pass
        box.setInformativeText(tr(
            "{run} keeps a copy of the chart it was measured with, so its "
            "measurement always describes a sheet you still have. The chart "
            "loaded now is a different one.\n\n"
            "What each choice does:\n\n"
            "•  {replace} — the copy is updated to the chart you "
            "are about to measure. Use this when the new chart is the one this "
            "run should keep.\n\n"
            "•  {keep} — the copy is left exactly as it is, and the "
            "measurement still goes ahead. Use this to try a chart out. The "
            "copy will then describe an earlier measurement, and ChromIQ says "
            "so on the “{restore}” button.\n\n"
            "•  Cancel — nothing is written and no measurement starts."
            # The three bullets name three controls, and a name TYPED here is a
            # name that drifts: German called these buttons „Gespeichertes
            # Chart ersetzen/behalten" while they read „Gesichertes
            # ersetzen/behalten", and Italian had the same pair twice over.
            # Each bullet now interpolates the button's OWN tr() key, so the
            # two cannot disagree in any language. (This window is NOT in §M —
            # it has no M- id and is in neither of test_message_catalogue's
            # allow-lists — so the English may move; §M's own M-END window a
            # few hundred lines below is fixed in the catalogue instead.)
        ).format(run=self._pretty_run_name(run),
                 replace=tr("Replace stored chart"),
                 keep=tr("Keep stored chart"),
                 restore=tr("Restore Used Chart")) + extra)
        replace = box.addButton(tr("Replace stored chart"),
                                QMessageBox.ButtonRole.DestructiveRole)
        keep = box.addButton(tr("Keep stored chart"),
                             QMessageBox.ButtonRole.ActionRole)
        keep.setToolTip(tr(
            "Measures without touching the stored copy — for trying a chart "
            "out. The copy will no longer describe this run's measurement."))
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
        set_warning_icon(box)
        box.setWindowTitle(tr("Stored chart differs"))
        box.setText(tr("Stored chart differs") + "\n\n" + tr(
            "Measuring here replaces the chart stored with that verification "
            "date."))
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
        if not ctl.target.is_verification() or not self._is_verification_run():
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
            if proj is None:
                return True
            # A CALIBRATION KEEPS ITS CHART TOO, in `cal/chart/`.
            #
            # This method was written for runs and reached for
            # `target.profile_run`, which under Run type = Calibration names
            # whatever run happened to be selected — so the calibration chart
            # was never copied anywhere, and a measured calibration could not
            # say which chart it was measured with. Knut, beta.148: *"the chart
            # in cal/ folder should have been copied to cal/chart/ folder,
            # similar to when measuring on a profile run."* The slot already
            # exists (`slot_for_calibration`); only the routing was missing.
            if ctl.target.is_calibration():
                snapshot_slot(slot_for(proj.calibration))
                return True
            run_id = ctl.target.profile_run
            if not run_id or not proj.has_run(run_id):
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

    @staticmethod
    def _chart_file_for(path: "Path | None") -> Path:
        """The `.ti2` that goes with whatever chart file the tab was given.

        Most paths hand this tab the `.ti2` already; opening a project can hand
        it the `.ti1` instead, so both are accepted and resolved to the one file
        chartread actually reads.
        """
        from pathlib import Path as _P
        if path is None:
            return _P("")
        path = _P(path)
        return path if path.suffix.lower() == ".ti2" else path.with_suffix(".ti2")

    def _chart_is_cr30(self) -> bool:
        """Does the chart in the user's hand name a CR30? (#159)

        The single CR30 question for this whole tab. It exists because
        ``TARGET_INSTRUMENT`` is written by the layout stage into the **.ti2**
        and is not in the `.ti1` at all — while opening a project hands this tab
        ``run.chart_ti1`` (``ui/main_window.py``). Every open-coded
        ``read_target_instrument(self._ti1_path)`` therefore read ``None`` after
        a reopen and silently answered "not a CR30".

        So: resolve through :meth:`_chart_file_for` first, exactly as
        ``set_ti1_path`` already does to decide whether Start is enabled, and
        route every CR30 decision — the stock-chartread guard, the swipe arrow,
        ``-x``, and the patch-by-patch lock — through this one method. Never add
        a second open-coded read; there were two and they were both wrong.
        """
        from ui.ti2_loader import is_cr30, read_target_instrument
        try:
            chart = self._chart_file_for(getattr(self, "_ti1_path", None))
            if not chart or not chart.exists():
                return False
            return is_cr30(read_target_instrument(chart))
        except Exception:      # noqa: BLE001 — never block a read on this check
            return False

    def _update_start_tooltip(self) -> None:
        """Say why Start is unavailable, rather than leaving it greyed in
        silence — the rule the rest of the app follows."""
        if self._start_btn.isEnabled():
            # An ENABLED Start still carries its shortcut hint. Clearing the
            # tooltip outright threw away the "(⌘↵)" the main window attaches
            # to each tab's primary button, so this was the one of the five
            # that never showed it (#164, Knut).
            from ui.keyboard_help import with_shortcut

            self._start_btn.setToolTip(
                with_shortcut(self._start_btn.text().replace("&", ""),
                              "primary_action"))
            return
        # A VERIFICATION HAS ITS OWN REASONS, AND THEY ARE IN §M.
        #
        # Since Start needs a `.ti2` (beta.128), a verification target with no
        # verification chart greys the button — and the two guard messages
        # written for exactly that situation could no longer be reached. Knut,
        # beta.128, on Demo-01: *"Start Measurement button is not available, so
        # test cannot be performed. You have not counted for that a verification
        # run must have a chart first."* The guidance belongs where he met it.
        try:
            block = self._verification_guard()
        except Exception:      # noqa: BLE001 — a tooltip is never worth a crash
            block = None
        if block is not None:
            title, body = block.render()
            self._start_btn.setToolTip(f"{title}\n\n{body}")
            return
        self._start_btn.setToolTip(tr(
            "There is no laid-out chart to measure. ChromIQ measures the "
            "chart's .ti2 file, which says where every patch sits on the "
            "sheet, and this run does not have one.\n\n"
            "Create the chart in the “Create Chart” tab — or load a .ti2 with "
            "“Open Chart File (.ti2)” — and this button becomes available."))

    def _blocked_by_missing_chart_file(self) -> bool:
        """A last guard for the same thing, in case Start is reached anyway."""
        if self._chart_file_for(self._ti1_path).exists():
            return False
        self._say_on_screen(
            tr("There is no laid-out chart to measure"),
            self._start_btn.toolTip() or tr(
                "ChromIQ measures the chart's .ti2 file, and this run does not "
                "have one."))
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
        inform(self, tr(
            "Choose a profile run to measure — pick one in the Profile-run "
            "bar above, or choose “New run” to start a fresh one"),
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
        # …and nothing to measure without the laid-out chart (Knut, 2026-08-04).
        if self._blocked_by_missing_chart_file():
            return
        # …and stop here when the chart names an instrument ArgyllCMS cannot
        # use. The CR30 check comes FIRST: "CR30" is a name ChromIQ knows, so
        # the general guard passes it — the open question is whether the READER
        # the user has selected can use it (#159).
        if self._blocked_by_stock_chartread_for_cr30():
            return
        # …and stop here when another window already has the instrument (#159).
        # Beside the CR30 guard because it is the same class of question and
        # the same instrument: both are "can this measurement have the device
        # it needs", and both must be answered before anything is archived,
        # opened or written.
        if self._blocked_by_the_instrument_being_in_use():
            return
        if self._blocked_by_unusable_target_instrument():
            return
        # #131: enter measurement mode so per-patch/strip sounds are allowed and
        # the selected clips are pre-loaded for zero-latency playback. On stock
        # ArgyllCMS chartread ChromIQ stays quiet — Argyll beeps for itself
        # there and cannot be silenced, so ours would only double it (Knut,
        # 2026-07-27). Whether the engine is in use is settled once the run has
        # started; it is re-stated there, and this is the safe default.
        if getattr(self, "_sound", None) is not None:
            self._sound.arm(reading_engine=self._engine_wanted())
        # A fresh read starts with a clean pace panel (Knut: it must be cleared
        # when a strip is re-read, a chart is re-read, or measuring is stopped).
        self._clear_pace_readout()
        self._finish_sound_played = False
        # Each run gets one immediate instrument-fault sound.
        self._instrument_fault_sounded = False
        import time as _t
        self._measure_started_at = _t.monotonic()

        # #130 Hole 1: don't start a verification of a run that has no profile.
        block = self._verification_guard()
        if block:
            from PyQt6.QtWidgets import QMessageBox
            # Each guard carries its own headline now that both are in §M. The
            # window used to say "Build a profile before verifying" for both,
            # which was wrong for the run that HAS a profile and only lacks its
            # verification chart.
            title, body = block.render()
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.NoIcon)
            box.setWindowTitle(title)
            box.setText(title)
            box.setInformativeText(body)
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
            from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
            fit_message_box_buttons(box)
            box.exec()
            # The old code unticked the module's Verification box here. With
            # that box gone the equivalent would be to change the Profile-run
            # bar under the user, which is a bigger thing to do unasked — the
            # message already tells them what to do, so nothing is changed.
            return

        # #130: keep a copy of the chart this verification measures, BEFORE any
        # measurement file is written.
        if not self._snapshot_verification_chart():
            return          # the user chose not to replace the stored chart

        params = self._collect_params()
        if not self._confirm_nonrandom_bidir(params):
            return
        if not self._confirm_replacing_measurement():
            return

        # CALIBRATE THE INSTRUMENT FIRST — AND DO IT HERE, NOT LATER.
        #
        # This sits between "the user agreed to replace the measurement" and
        # the archiving below ON PURPOSE. Everything after this point is
        # irreversible or has to be undone by hand: the next call moves the
        # run's existing .ti3 into old/, the session guard after it copies the
        # file aside and records its state, and further down the settings panel
        # is greyed out, Start is disabled, Stop enabled and an app-wide event
        # filter installed. A user who opens the calibration window and then
        # cancels because the white tile is in the other room must lose
        # NOTHING — and one line later they would already have lost the
        # measurement that run was holding.
        #
        # The one thing already done that a cancel must undo is the armed
        # per-patch sound (#131: sounds must not be live outside a read).
        # One window per measurement, and this run has not shown it yet (#159).
        # Reset HERE, above anything that can show it: it used to be cleared
        # just before the helper started, which is after the calibration flow —
        # so the calibration's copy of the window would be forgotten and the
        # user would be shown the same instructions twice in a row.
        self._cr30_how_shown = False
        # CLEAR THE LOG BEFORE THE CALIBRATION, NOT AFTER IT.
        #
        # It used to be cleared fifty-one lines further down, AFTER
        # _run_cr30_calibration had already written its notes — so every
        # calibration message was erased milliseconds after being written:
        # the dark-reference check (the only honest check either calibration
        # has), the note that a white calibration cannot be verified at all,
        # and the note saying which dark reference a skipped step left in
        # place. None of it had ever been seen by anybody.
        #
        # Found on 2026-08-30 by the owner running the black-calibration test
        # and pasting a log that simply did not contain the answer. The check
        # had been firing correctly the whole time.
        self._log.clear()
        if params.external_values and not params.disable_initial_cal:
            # `params`, never the checkbox. `disable_initial_cal` is hard-coded
            # False for Guided behind a comment headed "NEVER FROM A CONTROL
            # THE USER CANNOT SEE" — the Skip box is hidden there, and reading
            # the widget would let whatever Manual last set govern a Guided
            # run. That is beta.148, where a stored tick ran every guided
            # measurement uncalibrated and every patch was rejected.
            #
            # So the owner's ruling — mandatory in Guided, the existing Skip
            # box in Manual — is already the value of this one field.
            if not self._run_cr30_calibration():
                self._sound.disarm()
                self._log.appendPlainText("\n" + tr(
                    "Measurement not started: the instrument was not "
                    "calibrated. Nothing has been changed."))
                self._log.ensureCursorVisible()
                return

        # Keep the measurement this read is about to replace. chartread
        # truncates its output file the moment it starts, so without this the
        # old readings are simply gone — Knut, #130 2026-07-31: *"The previous
        # ti3 file that had measurements were cleared to become empty and then
        # moved to old/ folder."* He agreed to REPLACE it, not to have it
        # destroyed, and every other displacement in ChromIQ keeps a copy.
        #
        # Here rather than inside the question above: asking and archiving are
        # different jobs, and a method called _confirm_… that quietly moves
        # files is a surprise waiting for the next reader.
        #
        # NOTE THE FILE'S AGE **BEFORE** IT IS MOVED OUT OF THE WAY.
        #
        # `_on_measure_done` decides whether THIS session wrote a measurement by
        # comparing the .ti3's mtime against this snapshot, and reads "no file
        # here beforehand" as "so anything here now is fresh". Taken after the
        # archive below, that snapshot was `None` on every fresh read — and when
        # the session then measured nothing, `_restore_displaced_measurement`
        # put the previous file back with its original mtime and the app read
        # the restored file as this session's own work: it claimed "partial
        # readings saved", ticked Refine/resume, emitted `measure_finished` and
        # minted a dated measurement report that was a byte-for-byte copy of the
        # previous session's. The owner hit exactly that on 2026-09-03.
        _ti3_pre = self._ti1_path.with_suffix(".ti3") if self._ti1_path else None
        self._ti3_mtime_before = (
            _ti3_pre.stat().st_mtime if (_ti3_pre and _ti3_pre.exists()) else None
        )
        self._archive_measurement_before_replacing()
        # A FRESH READ STARTS WITH A CLEAN SHEET.
        #
        # Knut, #130 2026-08-01: *"the strip that has been read is shown as
        # overlay on the first strip. The 'Show overlay...' checkbox is not
        # visible, so why is it showing, also when I am starting a fresh
        # reading."* The overlay draws the measurement that is being replaced,
        # so once this read begins it describes a file that is on its way to
        # old/ — and it was still on screen with no visible control to turn it
        # off. Resuming is the opposite case: there the overlay is the readings
        # being added to, so it stays.
        if not self._read_builds_on_existing():
            self._sync_overlay_checkboxes(False)
            self._clear_overlay()
            # …AND SO DOES THE PROGRESS FIGURE. It is the same sentence about
            # the same file, and it was only half said.
            #
            # `_progress_base` is seeded from the run's .ti3 when the chart is
            # loaded, and nothing put it back to zero when a fresh read moved
            # that .ti3 to old/. So a replacing read began with the previous
            # measurement's count still in it: the owner's chart holds 390
            # patches and his previous measurement held 18, and the bar sat at
            # 18/390 = 4.6% for the whole session while the overlay beside it —
            # cleared one line above — showed no patch as read. Two readouts of
            # one thing, disagreeing, and the frozen one was the wrong one.
            self._reset_progress(from_files=False)
        else:
            # SHOW EVERYTHING ALREADY MEASURED, NOT JUST THIS SESSION (#156).
            #
            # Knut: *"When starting a measurement ALL previously measured
            # patches shall ALWAYS be shown, so that user knows where to measure
            # if patches are missing."* That is the whole point of the overlay
            # during a refinement — the gaps are what he is there to fill.
            #
            # The overlay was not being cleared here, but nor was it seeded, so
            # a refinement began with a blank chart and filled in only what this
            # session read. Painting the existing measurement first means the
            # session's own patches land on top of a complete picture.
            try:
                if self._show_overlay_from_existing_ti3():
                    self._sync_overlay_checkboxes(True)
            except Exception:      # noqa: BLE001 — never block a measurement
                log.warning("Could not seed the overlay from the existing "
                            "measurement", exc_info=True)
            # The bar counts the same readings the overlay has just painted, so
            # it is seeded from the same file at the same moment. Stated rather
            # than left to whatever the last chart load happened to leave
            # behind — that assumption is what the fresh branch above got wrong.
            self._reset_progress()
        self._preview.set_bidirectional(self._effective_bidirectional(params))
        # (the log was cleared before the calibration — see above)
        self._auto_proceed = False
        self._all_done_shown = False
        self._spot_current_loc = ""
        self._spot_click_on = False
        # Remember whether this is a patch-by-patch (spot) session, so the
        # completion dialog can speak of "patches" instead of "strips".
        self._spot_session = self._is_pbp_checked()
        # Capture the verification-measurement choice now, so toggling the box
        # mid-read can't change how the finished .ti3 is handled.
        self._verify_run = self._is_verification_run()
        self._instrument_disconnected = False
        self._device_busy = False
        self._no_instrument = False
        # (`_ti3_pre` / `_ti3_mtime_before` were taken above, before the archive)
        # §2a: copy the measurement aside and record C₀ before anything can
        # touch it. chartread writes its .ti3 only on a clean exit and a resume
        # overwrites the file it resumed from, so this is the last moment the
        # previous readings still exist to be protected.
        self._begin_session_guard(_ti3_pre)
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
        # W8 — START MEASUREMENT WRITES THIS TAB'S SETTINGS FOR THIS TARGET.
        #
        # `per_target_settings.md` §3: *"Load settings when activating tab, Save
        # / write settings when leaving tab, and when main button for tab is
        # pressed (… Start Measurement / Continue Measurement for Measure
        # tab …)"*, listed as W8. Every other event in that table was wired —
        # leaving a tab and changing target through MainWindow (W6), Generate
        # Chart on the Create Chart tab (W1) — and this one was not, so the
        # Measure tab was the only place where pressing the tab's own main
        # button did not record what it was pressed with.
        #
        # That is the whole of Knut's report (#156): tick "Skip initial
        # calibration", press Start, measure, stop — and the tick is gone. It
        # was never stored, so the next load put back the last value that was,
        # and the same is true of every other control on the panel. Written
        # BEFORE the reader launches, so what is recorded is what the
        # measurement actually ran with.
        self.save_target_settings()
        self._set_settings_enabled(False)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        #: True while a reader is waiting for keys — what makes the app-wide
        #: event filter below legitimate. Cleared in _on_measure_done.
        self._session_live = True
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
        if params.external_values:
            # ChromIQ supplies the readings itself: stand up the bridge that
            # answers the helper's spot prompts (#159 B.3-B.7), then say how to
            # measure — no instrument is opened, so `calibration_done`, the only
            # route to that window, can never arrive (F9).
            self._open_cr30_bridge()
            # SAY IT ONCE, WHERE A PUZZLED USER WILL LOOK.
            #
            # Measured on the owner's own instrument, 2026-08-29: a phone app
            # that is merely CONNECTED — not in use — takes the button press
            # exclusively, and the cable never sees it. He had to switch his
            # phone's Bluetooth off before ChromIQ registered a press at all.
            # The failure is completely silent and looks exactly like broken
            # software: the patch stays highlighted and nothing arrives.
            #
            # This is a log line rather than a window because it is rare and
            # the window would be paid for on every Start. The proper answer is
            # a banner when nothing has arrived for a while, which also catches
            # a flat battery and a sleeping instrument; until that exists, this
            # is the cheapest honest place for it.
            self._log.appendPlainText("\n" + tr(
                "[NOTE] If you have the CR30's phone app open, close it or "
                "turn Bluetooth off on the phone. While that app is connected "
                "it takes the instrument's button presses for itself, and "
                "ChromIQ never sees them — the patch simply stays highlighted "
                "and nothing happens."))
            self._log.ensureCursorVisible()
            self._show_cr30_measuring_window()
        # SAY WHEN THE INSTRUMENT IS NOT BEING CALIBRATED.
        #
        # Skipping the initial calibration changes every reading that follows,
        # and it is a setting that persists between sessions — so it can be on
        # today because of something done last week. It is now impossible for
        # that to be invisible: it goes in the log beside the command, where the
        # reason for a chart full of rejected patches should have been all
        # along (Knut, beta.148).
        if params.disable_initial_cal:
            # The wording has to differ for a reader ChromIQ drives itself.
            # `-N` suppresses ArgyllCMS chartread's calibration PROMPT — and
            # under `-xx` chartread opens no instrument and prompts nobody, so
            # the flag is inert on the command line. What the tick now means
            # for such a chart is that ChromIQ's own calibration window is not
            # offered. Telling a CR30 user about a prompt that cannot appear
            # would send them looking for something that does not exist.
            self._log.appendPlainText("\n" + tr(
                "[NOTE] Skip initial calibration (-N) is switched on, so your "
                "instrument will not be calibrated before this measurement.\n"
                "That is fine if you calibrated it earlier in this session. If "
                "you did not, readings can drift and whole patches may come "
                "back as “inconsistent” — switch the option off in the "
                "measurement options and start again.")
                if not params.external_values else
                "\n" + tr(
                "[NOTE] Skip initial calibration is switched on, so ChromIQ "
                "has not offered to calibrate your instrument before this "
                "measurement.\n"
                "That is fine if you calibrated it earlier. If you did not, "
                "every reading in this measurement can be shifted by the same "
                "amount, which is not visible in the numbers — untick the "
                "option in the measurement options and start again to be "
                "offered the calibration."))
            self._log.ensureCursorVisible()
        # A fresh session: nothing detected yet, and no window pending from the
        # last one.
        self._saw_instrument = False
        self._no_instrument = False
        # …AND THE WINDOW IS ALLOWED TO APPEAR AGAIN.
        #
        # `_no_instrument_shown` is the once-per-session guard that stops the
        # window being raised twice by the timer and the process exit. It was
        # set on the first showing and never cleared, so it silently became
        # once per *application run*: every later session with no instrument
        # logged the failure and showed nothing. Knut, beta.157: *"after ca. 20
        # sec the log window gets message: 'Unknown, inappropriate or no
        # instrument detected', but the 'No Instrument Found' message does not
        # come. The first few times I tested it came, but then stopped
        # coming."* Exactly that — the first time in the process, then never.
        self._no_instrument_shown = False
        self._disarm_no_instrument_window()
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

    def _begin_session_guard(self, ti3: "Path | None") -> None:
        """Start the §2a guard for this measurement."""
        from workflow.measurement_session import MeasurementSession
        self._session_guard = None
        if ti3 is None:
            return
        try:
            run = Run.for_dir(ti3.parent)
            old_dir = run.old_dir
        except Exception:      # noqa: BLE001 — a chart outside a project
            old_dir = ti3.parent / "old"
        try:
            guard = MeasurementSession(
                ti3, self._ti1_path.with_suffix(".ti2") if self._ti1_path else None,
                old_dir)
            guard.begin()
            self._session_guard = guard
        except Exception:      # noqa: BLE001 — never block a measurement
            log.warning("could not start the measurement guard", exc_info=True)

    def _finish_session_guard(self) -> None:
        """Judge what the session left behind and say so — §3b, §S3.

        At most one of the outcomes applies, which is what keeps §S3 to a single
        window after a measurement.
        """
        guard = getattr(self, "_session_guard", None)
        if guard is None:
            return
        self._session_guard = None
        try:
            resumed = bool(self._resume_is_active())
            out = guard.finish(resumed=resumed)
        except Exception:      # noqa: BLE001
            log.warning("could not judge the measurement session", exc_info=True)
            return

        if out.message_id == "M-TI3-EMPTY":
            self._say_on_screen(
                tr("The measurement file was empty, so it has been put aside"),
                tr("The file this session wrote contains no readings. It has "
                   "been moved to the run's “old” folder, and {restored}.")
                .format(restored=(
                    tr("your previous measurement of {m} patches has been put "
                       "back").format(m=out.before) if out.restored
                    else tr("this run has no measurement, as before"))))
        elif out.message_id == "M-TI3-SHRANK":
            self._say_on_screen(
                tr("This session ended with fewer readings than it started with"),
                tr("The measurement held {c0} patches when this session began "
                   "and {c} when it ended. A resume should only ever add "
                   "readings, so something has gone wrong.\n\n"
                   "Your earlier measurement has been put back, and the file "
                   "this session wrote is kept beside it so nothing is lost. "
                   "Nothing needs doing right now — measure again when you are "
                   "ready.").format(c0=out.before, c=out.after))
        elif out.added:
            # §3: every outcome is reported ON SCREEN, not only in the log —
            # Knut: "The user should always be informed on-screen on events, or
            # it will seem like hidden information."
            self._flash_status(tr(
                "{added} patches added — {total} in the measurement now.")
                .format(added=out.added, total=out.after))

    def _resume_is_active(self) -> bool:
        for name in ("_resume_cb", "_m_resume_cb"):
            cb = getattr(self, name, None)
            if cb is not None and cb.isVisible() and cb.isChecked():
                return True
        return False

    def _say_on_screen(self, title: str, body: str) -> None:
        """One informational window, with the title repeated in the body so it
        reads the same in a screenshot as on screen."""
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title + "\n\n" + body)
        box.addButton(QMessageBox.StandardButton.Ok)
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        fit_message_box_buttons(box)
        box.exec()

    #: Sentinel put in a failure window's "chosen" slot when the user asked to
    #: save instead of giving up. Not a key: saving is a protocol, not a
    #: keystroke, and which protocol depends on the engine.
    END_SAVE = "\x00save"

    #: "The user pressed Give Up" — resolved into a real answer only once the
    #: window they pressed it in has closed. See _resolve_give_up.
    GIVE_UP_PENDING = "__give_up_pending__"

    def _resolve_give_up(self, choice: str) -> str:
        """Turn a pending Give Up into the ending the user actually wants.

        Called after the failure window has closed, so the ending question is
        the only thing on screen — and, when the answer is to stop, the manager
        is told the ending has been answered, so the reader's own report of the
        interruption cannot raise a second window about it.

        Knut, beta.141, strip mode: *"clicking 'Give Up' called both
        'Instrument Error' and 'Strip Read Interrupted' windows simultaneously.
        The 'Strip Read Interrupted' window should not come at all."*
        """
        if choice != self.GIVE_UP_PENDING:
            return choice
        answer = self._give_up_or_save()
        if answer in ("\x1b", self.END_SAVE):
            # Stopping, either way. Whatever the reader says about it next is
            # about the ending the user has just chosen, not news.
            mark = getattr(self._manager, "mark_ending_answered", None)
            if callable(mark):
                mark()
        if answer == "\x1b":
            # …and in strip mode the quit that is about to go out may land at
            # the strip menu rather than at a give-up prompt, which interrupts
            # the read instead of ending the session. The manager finishes it
            # when the reader comes back (Knut, beta.147).
            mark = getattr(self._manager, "mark_stop_requested", None)
            if callable(mark):
                mark()
        return answer

    def _give_up_or_save(self) -> str:
        """What "Give Up" should do — specification §1a.

        Five failure windows offered Retry or Give Up, and Give Up sent Esc,
        which for chartread means quit WITHOUT saving. They said so honestly,
        but they asked the user to choose between retrying and losing the
        session when saving was available all along — the same fault as the Esc
        key, wearing a button.

        So Give Up now asks the one ending question, and maps the answer back
        into what the failure window has to send:

        * save → :data:`END_SAVE`, and the caller runs the save protocol
        * discard → Esc, as before
        * keep measuring → Return, which is "retry" at every one of these
          prompts — the user changed their mind about ending, and at a failure
          prompt not ending means trying again
        """
        choice = self._confirm_end_of_session(self.END_FAILURE_WINDOW)
        if choice == "save":
            return self.END_SAVE
        if choice == "discard":
            return "\x1b"
        return "\r"

    def _exec_measurement_window(self, dlg) -> int:
        """Run a during-the-read window, remembering it while it is up.

        Every window here belongs to a live measurement, so it must not survive
        the measurement — see _close_measurement_windows.
        """
        self._live_measure_windows.append(dlg)
        try:
            return dlg.exec()
        finally:
            try:
                self._live_measure_windows.remove(dlg)
            except ValueError:
                pass

    def _close_measurement_windows(self) -> None:
        """Close every window that belongs to the measurement that just ended.

        Knut's rule (beta.139): *"When the measurement session ends, everything
        relating to measurements should end."* Each of these windows spins its
        own event loop, so one could still be on screen after chartread had
        gone — and pressing its buttons then wrote keys to a process that no
        longer existed, which is where the *"no active process"* warnings in his
        logs came from. Rejecting them unwinds those loops; the choice each one
        would have sent is dropped by _send_failure_choice, because there is
        nothing left to send it to.
        """
        for dlg in list(self._live_measure_windows):
            try:
                dlg.reject()
            except RuntimeError:
                pass            # already gone with its parent
        self._live_measure_windows.clear()

    def _send_failure_choice(self, key: str) -> None:
        """Send what a failure window decided, honouring :data:`END_SAVE`.

        Silent when the measurement has already ended: the window may have been
        closed *by* that ending (see _close_measurement_windows), and a key sent
        into a finished process is not a warning worth showing anybody.
        """
        if not self._runner.is_running:
            log.debug("measurement already ended; not sending %r", key)
            return
        if key == self.END_SAVE:
            self._manager.send_save_partial_and_quit()
        else:
            self._manager.send_key(key)

    #: What ended the session, for the one window that asks about it (§S2).
    END_STOP = "stop"
    END_DONE_KEY = "done"
    END_ABORT_KEY = "abort"
    END_FAILURE_WINDOW = "failure"
    #: Closing the application. It ends a session like any other route, so it
    #: asks the same question — see confirm_quit_during_measurement.
    END_QUIT = "quit"

    def _confirm_end_of_session(self, how: str = END_STOP) -> "str | None":
        """M-END / M-END-EMPTY — the one window every ending route goes through.

        Specification §1, §1a and §2 (docs/design/unified_measurement_management.md).
        Stop, the 'd' key, Esc/'q' and every failure window that can end a
        session all arrive here, so there is no longer a safe way and an unsafe
        way to stop measuring — which is what Knut asked for after finding that
        Stop threw readings away while 'd' saved them.

        Returns ``"save"``, ``"discard"`` or ``None`` for "carry on". The caller
        performs the action; this only asks.
        """
        from PyQt6.QtWidgets import QMessageBox
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)

        if not self._manager.has_unsaved_readings:
            # M-END-EMPTY. Nothing to lose, so nothing to ask — but say so,
            # because silence after pressing Stop is what has to be interpreted.
            self._log.appendPlainText(
                "\n" + tr("Nothing was measured, so nothing was saved."))
            self._log.ensureCursorVisible()
            return "discard"

        self._cue_window("STRIP_FAIL")
        n = self._manager.readings_this_session
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        title = tr("Keep what you have measured so far?")
        box.setWindowTitle(title)
        had = self._readings_before_session()
        # Count-bearing sentences get real singular and plural variants, never
        # "(s)" — CLAUDE.md. Both of these could say "1 patches", and the first
        # one is reached with n == 1 more often than any other value: it is the
        # window a patch-by-patch user meets after their very first reading.
        if not had:
            kept = ""
        elif had == 1:
            kept = "\n\n" + tr(
                "Your previous measurement of 1 patch is put back exactly as "
                "it was.")
        else:
            kept = "\n\n" + tr(
                "Your previous measurement of {m} patches is put back exactly "
                "as it was.").format(m=had)
        read_line = (tr("You have read 1 patch in this session.") if n == 1
                     else tr("You have read {n} patches in this "
                             "session.").format(n=n))
        box.setText(title + "\n\n" + read_line + " " + tr(
            "They are not in your "
            "measurement file yet — ChromIQ can write them now, or end the "
            "session without them.\n\n"
            "What each button does:\n\n"
            "•  Save and stop — writes what you have read so far to this run's "
            "measurement file and ends the session. You can carry on later "
            "with “Refine / resume existing measurement (-r)”, reading only the "
            "strips or patches that are still missing.\n\n"
            "•  Discard and stop — ends the session and keeps nothing from "
            "it.{kept}\n\n"
            "•  Keep measuring — closes this window and carries on where you "
            "were.").format(kept=kept))
        save = box.addButton(tr("Save and stop"),
                             QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(tr("Discard and stop"),
                                QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("Keep measuring"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        fit_message_box_buttons(box)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return "save"
        if clicked is discard:
            return "discard"
        return None

    def _readings_before_session(self) -> int:
        """C₀ — how many readings the run held when this session began."""
        sess = getattr(self, "_session_guard", None)
        return int(getattr(sess, "before", 0) or 0)

    def _end_session(self, choice: "str | None") -> None:
        """Carry out what :meth:`_confirm_end_of_session` returned."""
        if choice is None:
            return                       # the user is carrying on
        # AN ENDING THE USER CHOSE NEVER CHANGES TAB.
        #
        # Moving to tab 4 by itself is the all-done window's accept button and
        # nothing else — *"This is where user shall decide to change tab"*
        # (Knut, beta.148, after Stop → Save and stop dropped him on Calibration
        # & Profiling). `_auto_proceed` can still be carrying that window's
        # earlier answer, so it is spent here.
        self._auto_proceed = False
        if choice == "save":
            self._manager.send_save_partial_and_quit()
        elif choice == "discard":
            self._manager.abort()

    def _on_stop(self) -> None:
        """Stop the measurement — through the one ending window (§S2.4/S2.5).

        Knut, #130 2026-08-01, twice in one session: he read a strip, pressed
        Stop, and *"the measurement session is ended without any measurement and
        the ti3 file is gone"*; then the same patch by patch — *"no ti3 file is
        saved, even though I did read one patch"*.

        The cause was never Stop itself: chartread keeps its readings in memory
        and writes the ``.ti3`` only when it exits cleanly, so killing the
        process discards them. Pressing 'd' asked and saved; pressing Stop threw
        the work away without a word. Both now ask the same question.
        """
        self._key_watchdog.stop()
        self._end_session(self._confirm_end_of_session(self.END_STOP))

    # ------------------------------------------------------------------
    # Quitting the application, which is an ending like any other
    # ------------------------------------------------------------------

    def a_measurement_is_running(self) -> bool:
        """True while a reader is live and waiting for this tab's keys."""
        return bool(getattr(self, "_session_live", False)) and \
            bool(self._runner.is_running)

    def confirm_quit_during_measurement(self) -> bool:
        """The quit door. Returns True when the application may close.

        `measurement_exit_strategy.md`: *"Every way out of a session goes
        through `_confirm_end_of_session` … A window that ends a session any
        other way is a second exit, and that is the thing this document exists
        to catch."* Quitting was that second exit, and the worst one: closing
        the window went straight to `ArgyllRunner.cleanup()`, which kills the
        reader, and stock chartread writes its `.ti3` only on a clean exit
        (§0). Measured on the real binary with one strip read: ended by 'd'
        then 'y' the file holds 16 readings, killed there is no file at all.
        No question was asked, and the window had already been hidden, so
        nothing said afterwards could be seen either.

        So it asks the one question every other ending asks, and each answer
        means here what it means everywhere else:

        * **Save and stop** — the save chain runs, and the quit waits for it.
        * **Discard and stop** — the session ends with nothing kept, and the
          app closes.
        * **Keep measuring** — the session continues, so the quit is cancelled.

        Nothing is asked when nothing has been read: `_confirm_end_of_session`
        answers that case itself (M-END-EMPTY) and the app closes.
        """
        if not self.a_measurement_is_running():
            return True
        self._key_watchdog.stop()
        choice = self._confirm_end_of_session(self.END_QUIT)
        if choice is None:
            log.info("quit cancelled: the user chose to keep measuring")
            return False
        self._end_session(choice)
        self.wait_for_the_reader_to_finish()
        return True

    def wait_for_the_reader_to_finish(self, timeout_s: float = 20.0) -> bool:
        """Let a chosen ending complete before the caller tears the app down.

        **The save chain is a conversation, not a keystroke.** It sends one key
        and then waits for what the reader prints or reports back before
        sending the one that actually writes the file — the give-up prompt on
        the engine, "Are you sure" on stock (§1b). Returning to `closeEvent`
        before that round trip has happened puts the process straight into
        `ArgyllRunner.cleanup()`, which kills it. That would answer "Save and
        stop" by destroying exactly what the user asked to keep, which is the
        fault this whole door exists to remove.

        Bounded, because a quit must never hang: if the reader has not finished
        in `timeout_s` the app closes anyway and says so in the log.
        """
        deadline = time.monotonic() + float(timeout_s)
        app = QApplication.instance()
        while self._runner.is_running and time.monotonic() < deadline:
            if app is not None:
                app.processEvents()
            time.sleep(0.01)
        if self._runner.is_running:
            log.warning("the reader had not finished %.0fs after the ending "
                        "was chosen; closing anyway", timeout_s)
            return False
        return True

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
        self._cue_window("STRIP_FAIL")
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
            "one strip.<br><br>&nbsp;&nbsp;<b>{remeasure}</b> — jump "
            "back to strip {strip} and scan it again (recommended).<br><br>"
            "&nbsp;&nbsp;<b>{keep}</b> — accept this reading as it is.<br><br>"
            "&nbsp;&nbsp;<b>{stop}</b> — stop measuring for now."
        ).format(strip=strip, patches=patches, base=base_de, best=best_de,
                 remeasure=tr("Re-measure this strip"), keep=tr("Keep it"),
                 stop=tr("Stop")), dlg)
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
        self._exec_measurement_window(dlg)
        if choice[0] == "remeasure":
            self._manager.goto_strip(strip)     # re-read this strip next
        elif choice[0] == "stop":
            self._on_stop()

    def _flash_status(self, text: str, duration_ms: int = 8000) -> None:
        self._status_bar_lbl.setText(text)
        self._status_bar_lbl.setVisible(True)
        # A BOUND METHOD, NOT A LAMBDA HOLDING THE LABEL — `singleShot` keeps no
        # owner, so this stays armed for eight seconds after the tab is gone and
        # then calls setVisible on a deleted C++ widget. The same shape in the
        # scanner dialog was the intermittent failure in the test gate; eight
        # seconds is a far wider window than its 1.4.
        QTimer.singleShot(duration_ms, self._hide_status_flash)

    def _hide_status_flash(self) -> None:
        """Take the flashed status line down again (see `_flash_status`)."""
        lbl = getattr(self, "_status_bar_lbl", None)
        if lbl is not None:
            lbl.setVisible(False)

    #: How long after "no instrument" is detected the window arrives. Knut,
    #: beta.150: *"move the time the 'No Instrument Found' window comes to
    #: arrive 5 seconds after no instrument is detected, instead of the almost
    #: 20 seconds that it takes for this warning to come. Make sure this window
    #: uses the same detection logic as today, only change when the time that
    #: the message will arrive."* The 20 seconds were not a timer at all — the
    #: window waited for chartread to exit.
    _NO_INSTRUMENT_DELAY_S = 5

    def _arm_no_instrument_window(self) -> None:
        """Show the No Instrument Found window without waiting for the exit."""
        wd = getattr(self, "_no_instrument_timer", None)
        if wd is None:
            wd = QTimer(self)
            wd.setSingleShot(True)
            wd.setInterval(self._NO_INSTRUMENT_DELAY_S * 1000)
            wd.timeout.connect(self._show_no_instrument_window)
            self._no_instrument_timer = wd
        wd.start()

    def _show_no_instrument_window(self) -> None:
        """M-NO-INSTRUMENT — one button, and it ends the session the model's way.

        Knut wrote this text (beta.150) and asked for it to replace the
        original's bullet list, for the window to arrive five seconds after the
        detection instead of at the end of the process, and for its button to
        use the single exit every other window uses:

        > *"verify that the OK button in this window closes the measurement
        > session using the standard exit strategy for the Unified Measurement
        > Management model … All messages that can arrive during measurement
        > must exit in that safe manner, as a single exit strategy for all
        > cases."*

        So OK goes through :meth:`_confirm_end_of_session` like Stop does: with
        nothing read it ends and the archived measurement is put back, and with
        readings in hand it asks "Keep what you have measured so far?" first.
        """
        if getattr(self, "_no_instrument_shown", False):
            return
        self._no_instrument_shown = True
        self._disarm_no_instrument_window()
        self._cue_window("INSTRUMENT_ERROR")

        from PyQt6.QtWidgets import QMessageBox
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        from workflow.measurement_messages import (M_NO_INSTRUMENT,
                                                   M_NO_INSTRUMENT_FAST)

        # While the "Faster instrument connection" shortcut is on it is the
        # likeliest cause on older hardware (Knut, 2026-08-13: his ColorMunki
        # was invisible on a 2019 MacBook until he switched it off), so that
        # case gets the variant naming it — and the switch itself, so nobody
        # has to go hunting through Preferences mid-measurement (Sebastian).
        fast_on = bool(self._settings.get("fast_instrument_connect", True))
        msg = M_NO_INSTRUMENT_FAST if fast_on else M_NO_INSTRUMENT
        title, body = msg.render(n=self._NO_INSTRUMENT_DELAY_S)
        self._log.appendPlainText("\n" + title + "\n" + body)
        self._log.ensureCursorVisible()

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        # ResetRole, not ActionRole: the role decides the placement, and OK
        # belongs on the right (Sebastian, 2026-08-13). ActionRole puts the
        # extra button there instead, which reads as the default action.
        turn_off = (box.addButton(tr("Turn off faster connection"),
                                  QMessageBox.ButtonRole.ResetRole)
                    if fast_on else None)
        box.addButton(tr("OK"), QMessageBox.ButtonRole.AcceptRole)
        fit_message_box_buttons(box)
        self._exec_measurement_window(box)
        if turn_off is not None and box.clickedButton() is turn_off:
            self._settings.set("fast_instrument_connect", False)
            log.info("No-instrument window: faster instrument connection "
                     "switched OFF at the user's request")
        # …and then the one ending every route shares.
        if self._runner.is_running:
            self._end_session(self._confirm_end_of_session(self.END_FAILURE_WINDOW))

    def _disarm_no_instrument_window(self) -> None:
        wd = getattr(self, "_no_instrument_timer", None)
        if wd is not None and wd.isActive():
            wd.stop()

    def _on_log_line(self, line: str) -> None:
        self._log.appendPlainText(line)
        self._log.ensureCursorVisible()
        # MIRROR IT INTO THE APPLICATION LOG TOO.
        #
        # Everything the measurement narrates — "[Guided Refinement] Moving to
        # strip C…", the engine's own notes, chartread's prose — existed ONLY in
        # this panel. So when Basti hit a guided refinement that stopped
        # advancing (2026-08-08) the file held the raw `[argyll]` events and not
        # one line of what ChromIQ decided, and the panel was hidden behind a
        # running measurement he would have had to stop to read. He asked for
        # this: *"can you make it write your info to the real log for next
        # time"*.
        #
        # A near-miss worth recording: the absence of "[Guided Refinement]" lines
        # in the file looked like proof that guided navigation never started. It
        # was not — no panel line reached the file at all. Mirroring removes that
        # trap as well as the inconvenience.
        try:
            log.info("%s", line.rstrip())
        except Exception:      # noqa: BLE001 — logging must never break a read
            pass
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
        self._cue_window("STRIP_FAIL")
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Wrong Strip Read"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            tr("<b>This reading looks like strip {read}, but strip {expected} was expected.</b><br><br>This usually means the instrument was placed on the wrong row — or two rows simply look very similar. You have three options:<br><br>&nbsp;&nbsp;<b>{use_anyway}</b> — keep this reading and save it as strip {expected} (the row you were asked to scan). Only choose this if you are sure the instrument really was on strip {expected} and the warning is a false alarm — the reading is always filed under {expected}, not {read}.<br><br>&nbsp;&nbsp;<b>{retry}</b> — discard this reading and try again. Place your instrument on strip {expected} and re-scan.<br><br>&nbsp;&nbsp;<b>{give_up}</b> — stop the measurement without saving.").format(read=read, expected=expected,
                    use_anyway=tr("Use Anyway"), retry=tr("Retry"),
                    give_up=tr("Give Up")),
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
            # ASK AFTER THIS WINDOW HAS CLOSED, never before.
            # _give_up_or_save() opens the ending question, and dlg.accept()
            # only runs after it returns — so the question appeared ON TOP of
            # the failure window it belongs to. Knut, beta.141: *"it appears on
            # top of the previous window (the window was not closed, or it came
            # more than once)"*, on all three of these windows.
            chosen[0] = self.GIVE_UP_PENDING
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
        self._exec_measurement_window(dlg)
        chosen[0] = self._resolve_give_up(chosen[0])
        self._send_failure_choice(chosen[0])
        self._arm_key_watchdog()

        if chosen[0] not in ("\x1b", self.END_SAVE):
            QApplication.instance().installEventFilter(self)
        # If giving up, chartread will exit and _on_measure_done re-enables UI.

    def _on_unexpected_response(self, delta_e: str) -> None:
        self._cue_window("PATCH_OUT_OF_TOL")
        from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Unexpected Color Response"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            tr("<b>An unexpected color response was detected (ΔE {delta_e}).</b><br><br>This usually means the instrument was not aligned correctly with the strip, was moved during the scan, or the wrong strip was read. A ΔE this high indicates the measured colors are very far from what is expected.<br><br>&nbsp;&nbsp;<b>{use_anyway}</b> — accept the reading and continue. Only use this if you are sure the scan was correct.<br><br>&nbsp;&nbsp;<b>{retry}</b> — discard this reading, re-position your instrument carefully on the correct strip, and try again.<br><br>&nbsp;&nbsp;<b>{give_up}</b> — stop the measurement without saving.").format(delta_e=delta_e,
                    use_anyway=tr("Use Anyway"), retry=tr("Retry"),
                    give_up=tr("Give Up")),
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
            # ASK AFTER THIS WINDOW HAS CLOSED, never before.
            # _give_up_or_save() opens the ending question, and dlg.accept()
            # only runs after it returns — so the question appeared ON TOP of
            # the failure window it belongs to. Knut, beta.141: *"it appears on
            # top of the previous window (the window was not closed, or it came
            # more than once)"*, on all three of these windows.
            chosen[0] = self.GIVE_UP_PENDING
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
        self._exec_measurement_window(dlg)
        chosen[0] = self._resolve_give_up(chosen[0])
        self._send_failure_choice(chosen[0])
        self._arm_key_watchdog()

        if chosen[0] not in ("\x1b", self.END_SAVE):
            QApplication.instance().installEventFilter(self)

    def _on_sensor_wrong_position(self) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        # "Instrument in Wrong Position" is an Instrument error row in
        # core.measure_windows.WINDOW_ROWS, and it played nothing. Cued from
        # the top of the slot, before the modal blocks — see _cue_window.
        self._cue_window("INSTRUMENT_ERROR")
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
        self._exec_measurement_window(dlg)
        QApplication.instance().installEventFilter(self)

    def _on_strip_interrupted(self) -> None:
        self._cue_window("STRIP_FAIL")
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
            "&nbsp;&nbsp;<b>{resume}</b> — chartread is still waiting; "
            "re-position the instrument at the start of the current strip and continue.<br><br>"
            "&nbsp;&nbsp;<b>{give_up}</b> — stop the measurement without saving."
            ).format(resume=tr("Resume"), give_up=tr("Give Up")),
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
            # ASK AFTER THIS WINDOW HAS CLOSED, never before.
            # _give_up_or_save() opens the ending question, and dlg.accept()
            # only runs after it returns — so the question appeared ON TOP of
            # the failure window it belongs to. Knut, beta.141: *"it appears on
            # top of the previous window (the window was not closed, or it came
            # more than once)"*, on all three of these windows.
            chosen[0] = self.GIVE_UP_PENDING
            dlg.accept()

        resume_btn.clicked.connect(_resume)
        give_btn.clicked.connect(_give_up)

        btn_row.addWidget(resume_btn)
        btn_row.addStretch()
        btn_row.addWidget(give_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        self._exec_measurement_window(dlg)
        chosen[0] = self._resolve_give_up(chosen[0])
        self._send_failure_choice(chosen[0])
        self._arm_key_watchdog()

        if chosen[0] not in ("\x1b", self.END_SAVE):
            QApplication.instance().installEventFilter(self)

    def _on_unread_confirm(self, patch_info: str) -> None:
        self._cue_window("STRIP_FAIL")
        QApplication.instance().removeEventFilter(self)

        # §S2.6: the 'd' key ends a session exactly as Stop does, so it asks the
        # same question. Knut: *"These two ways of stopping should have same
        # window. I prefer warning message 'Keep what you have measured so far?'
        # for both cases."* The patch it used to name in its title is in the
        # body of that window instead.
        choice = self._confirm_end_of_session(self.END_DONE_KEY)
        if choice is not None:
            self._end_session(choice)
            self._arm_key_watchdog()
            return
        # KEEP MEASURING HAS TO SEND THE 'n' ITSELF.
        #
        # This is a SLOT (`self._manager.unread_confirm.connect(...)`), and Qt
        # throws a slot's return value away — so the 'n' this used to return
        # went nowhere and chartread stayed blocked on its own "Are you sure
        # [y/n]" for the rest of the session. Nothing the user did afterwards
        # reached the reader: measured on screen, a further swipe of the
        # instrument changed nothing at all.
        #
        # And the event filter removed at the top of this method was never put
        # back, so the keyboard was disconnected as well — every other window
        # handler in this tab re-installs it (:6853, :6925, :7030, :7099,
        # :7178, :8786), and the handler this one replaced did both of these
        # things. It is the only one that did neither.
        #
        # 'n' is right on both readers: chartread accepts only 'y' at that
        # prompt and treats anything else as "no, carry on", and on the engine
        # 'n' is mapped in KEY_TO_COMMAND, so it is not one of the silently
        # dropped keys.
        self._send_failure_choice("n")
        self._arm_key_watchdog()
        QApplication.instance().installEventFilter(self)

    def _legacy_patches_still_unread(self, patch_info: str) -> str:
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
        self._exec_measurement_window(dlg)
        chosen[0] = self._resolve_give_up(chosen[0])
        self._send_failure_choice(chosen[0])
        self._arm_key_watchdog()

        # 'y' makes chartread write the partial .ti3 and exit; 'n' returns
        # to the strip menu where the event filter is needed again.
        if chosen[0] == "n":
            QApplication.instance().installEventFilter(self)

    def _on_generic_instrument_error(self, friendly: str, technical: str) -> None:
        # ONE WINDOW AT A TIME. Each of these runs its own event loop, so the
        # reader's output keeps arriving while one is up — and pressing the
        # instrument button again raises another failure, which used to open a
        # second window on top of the first. Knut, beta.140: *"I can also click
        # the instrument button more times, and this window comes on top of
        # previous windows, all at the same time. This should not be allowed."*
        #
        # The rule was already agreed for the instrument-mismatch window in
        # beta.136 — *"The first window must be terminated/finished before other
        # windows should be allowed"* — and the register that makes it checkable
        # is the one every during-a-read window registers itself in.
        if self._live_measure_windows:
            log.debug("instrument error while a window is open — not stacking "
                      "a second one: %s", friendly)
            return
        # AFTER the guard above, never before it: a window that is suppressed
        # must not make a sound. "Instrument Error (anything else the
        # instrument reports)" is an Instrument error row in
        # core.measure_windows.WINDOW_ROWS and it was silent.
        self._cue_window("INSTRUMENT_ERROR")
        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Instrument Error"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Show the friendly message first, with the technical detail as a smaller line.
        msg = QLabel(
            tr("<b>{friendly}</b><br><span style='color:#888;'>({technical})</span><br><br>&nbsp;&nbsp;<b>{retry}</b> — try the operation again.<br><br>&nbsp;&nbsp;<b>{give_up}</b> — stop the measurement without saving.").format(friendly=friendly, technical=technical,
                    retry=tr("Retry"), give_up=tr("Give Up")),
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
            # ASK AFTER THIS WINDOW HAS CLOSED, never before.
            # _give_up_or_save() opens the ending question, and dlg.accept()
            # only runs after it returns — so the question appeared ON TOP of
            # the failure window it belongs to. Knut, beta.141: *"it appears on
            # top of the previous window (the window was not closed, or it came
            # more than once)"*, on all three of these windows.
            chosen[0] = self.GIVE_UP_PENDING
            dlg.accept()

        retry_btn.clicked.connect(_retry)
        give_btn.clicked.connect(_give_up)

        btn_row.addWidget(retry_btn)
        btn_row.addStretch()
        btn_row.addWidget(give_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        self._exec_measurement_window(dlg)
        chosen[0] = self._resolve_give_up(chosen[0])
        self._send_failure_choice(chosen[0])
        self._arm_key_watchdog()

        if chosen[0] not in ("\x1b", self.END_SAVE):
            QApplication.instance().installEventFilter(self)

    def _on_device_busy(self) -> None:
        if self._device_busy:
            return
        self._device_busy = True

    def _on_no_instrument(self) -> None:
        self._no_instrument = True
        # The window used to wait for chartread to exit, which is where the
        # twenty seconds came from. The detection is unchanged; only the moment
        # it reaches the user has moved (Knut, beta.150).
        self._arm_no_instrument_window()

    def _on_usb_claimed_by_vm(self) -> None:
        self._usb_claimed_by_vm = True

    # Group B: capture startup-failure messages so _on_measure_done can show
    # a friendly terminal dialog instead of the generic "measurement failed".
    def _on_coms_init_failed(self, msg: str) -> None:
        self._coms_init_failed_msg = msg
        # chartread EXITS 0 when it cannot open the instrument (Knut's log,
        # #130 beta.120: "Initialising instrument failed with message
        # 'Communications failure'" followed by "finished with code 0"). So
        # the exit code alone reads as success and the dialog below was never
        # reached — ChromIQ simply did nothing, which is how the instrument
        # came to look dead. It is a failure; say so.
        self._measure_failed = True

    def _on_inst_init_failed(self, msg: str) -> None:
        self._inst_init_failed_msg = msg
        self._measure_failed = True      # exits 0 — see _on_coms_init_failed

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

    def _silence_for_stock_chartread(self) -> None:
        """The engine gave way to stock ArgyllCMS chartread mid-run: Argyll's own
        beeps take over from here, so ChromIQ's measurement sounds stop (Knut,
        #131 2026-07-27)."""
        snd = getattr(self, "_sound", None)
        if snd is not None:
            snd._reading_engine = False

    def _on_engine_fell_back(self, reason: str) -> None:
        self._silence_for_stock_chartread()
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
        self._silence_for_stock_chartread()
        """Like _on_engine_fell_back, but the engine had already measured part of
        the chart when the instrument failed (#134). The manager writes the full,
        reassuring explanation to the log; here we add a brief, non-blocking
        status flash so the good news — nothing was lost, just carry on — is
        impossible to miss without interrupting the measurement."""
        self._flash_status(
            tr("Your measured strips are safe — continuing on ArgyllCMS "
               "chartread from where you left off."),
            duration_ms=8000)

    def _cr30_reading_from_the_keyboard(self) -> None:
        """Space or Enter: take the reading without touching the instrument.

        M-CR30-TRIGGER-NOT-ARMED (§M-PROPOSED) when this instrument's tile is
        not known yet. A reading ChromIQ asks for cannot report the magnet
        gate -- byte 58 marks the reply solicited and the flag at offset 24 is
        meaningful only in the unsolicited header a button press produces -- so
        the learned tile signature is what replaces it. Without one there is no
        replacement, and the trigger is refused rather than made silently
        unsafe.

        The request only sets a flag. The reader thread owns the link for the
        whole of its wait, so the trigger has to leave from there; see
        `DeviceReader.request_trigger`.
        """
        reader = getattr(self, "_cr30_reader", None)
        if reader is None:
            return
        try:
            if reader.request_trigger():
                self._flash_status(
                    tr("Taking the reading — keep the instrument still."),
                    duration_ms=2000)
                return
        except Exception:              # noqa: BLE001 — never eat a keystroke
            log.debug("CR30: could not request a reading", exc_info=True)
            return
        if getattr(self, "_cr30_said_trigger_not_armed", False):
            self._flash_status(tr(
                "Press the button on the instrument — ChromIQ cannot take "
                "this reading for you yet."), duration_ms=4000)
            return
        self._cr30_said_trigger_not_armed = True
        from PyQt6.QtWidgets import QMessageBox
        from workflow import measurement_messages as M
        from ui.widgets import fit_message_box_buttons
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("Measuring from the keyboard"))
        box.setText(tr(M.M_CR30_TRIGGER_NOT_ARMED.title))
        box.setInformativeText(tr(M.M_CR30_TRIGGER_NOT_ARMED.body))
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        fit_message_box_buttons(box)
        box.exec()

    def _open_cr30_bridge(self) -> None:
        """Stand up the thing that answers the helper's spot prompts (#159).

        `workflow.cr30.measure_bridge` owns every protocol rule; this method
        only decides *when* it exists. It is deliberately not fatal: if the
        driver dependencies are missing the run still starts and the user is
        told, rather than Start doing nothing.
        """
        if getattr(self, "_cr30_bridge", None) is not None:
            # ALREADY STANDING, AND IT MUST STAY STANDING.
            #
            # The calibration opens the bridge before the helper starts, on
            # purpose: it calibrates through the session's own reader so the
            # instrument is opened once. Rebuilding here would call
            # _close_cr30_bridge() and shut the instrument the calibration had
            # just opened and used — over Bluetooth a full disconnect from a
            # peripheral that takes one connection at a time. Measured on
            # screen before this guard: two DeviceReader constructions and two
            # close() calls for a single Start.
            return
        self._close_cr30_bridge()
        try:
            from workflow.cr30.measure_bridge import (Cr30MeasureBridge,
                                                      DeviceReader)
            self._cr30_reader = DeviceReader()
            # CLAIM IT, so a window that opens no process is still visible to
            # the rest of the app. Not fatal if it is refused: `_on_start`'s
            # guard is what stops a measurement, and this call is the record of
            # who holds the device — a failure here means somebody else already
            # does, which the guard has already reported.
            from core import instrument_lease
            instrument_lease.acquire(self._cr30_reader,
                                     instrument_lease.MEASURE_TAB)
            self._cr30_bridge = Cr30MeasureBridge(
                self._manager.send_command, self._cr30_reader, self)
            self._cr30_bridge.reading_dropped.connect(self._on_cr30_dropped)
            self._cr30_bridge.read_failed.connect(self._on_cr30_read_failed)
            self._cr30_bridge.mispaired.connect(self._on_cr30_mispaired)
            self._cr30_bridge.patch_rearmed.connect(self._on_cr30_rearmed)
            self._cr30_bridge.readings_discarded.connect(
                self._on_cr30_readings_discarded)
            self._cr30_bridge.device_lost.connect(self._on_cr30_device_lost)
            self._cr30_bridge.magnet_gated.connect(self._on_cr30_magnet)
            self._cr30_bridge.read_gave_up.connect(self._on_cr30_gave_up)
        except Exception:      # noqa: BLE001 — say so, do not kill the run
            log.warning("could not start the CR30 reading bridge", exc_info=True)
            self._cr30_bridge = self._cr30_reader = None
            self._log.appendPlainText(tr(
                "ChromIQ could not start its CR30 reader, so this measurement "
                "cannot collect readings. Check that the instrument is "
                "connected and try again."))

    def _close_cr30_bridge(self) -> None:
        """Let go of the bridge and the instrument when the run ends."""
        bridge = getattr(self, "_cr30_bridge", None)
        if bridge is not None:
            bridge.stop()
        reader = getattr(self, "_cr30_reader", None)
        if reader is not None:
            from core import instrument_lease
            instrument_lease.release(reader)
            try:
                reader.close()
            except Exception:      # noqa: BLE001 — teardown only
                log.debug("CR30 reader close failed", exc_info=True)
        self._cr30_bridge = self._cr30_reader = None

    def _on_cr30_dropped(self, loc: str, why: str) -> None:
        """A reading was refused rather than sent. Never silently.

        Dropping costs the operator one button press; sending it would put a
        colour on the wrong patch, which nothing downstream can detect.
        """
        from workflow.cr30.measure_bridge import DROPPED_NAVIGATING
        if why == DROPPED_NAVIGATING:
            text = tr("That reading arrived while ChromIQ was moving to another "
                      "patch, so it was not used. Read patch {loc} again."
                      ).format(loc=loc)
        else:
            text = tr("That reading arrived when ChromIQ was not waiting for "
                      "one, so it was not used. Read the highlighted patch "
                      "again.")
        self._log.appendPlainText(text)
        self._log.ensureCursorVisible()
        self._flash_status(text, duration_ms=6000)

    def _on_cr30_read_failed(self, loc: str, message: str) -> None:
        """A reading did not arrive complete. The patch is armed again.

        M-CR30-READ-FAILED (§M-PROPOSED). The owner, 2026-08-30, with a
        screenshot of this as a line of grey text under the buttons: *"a
        message like this would be better in a pop up so the user is aware of
        it instead of ruining a whole measurement session when this is
        unnoticed"*.

        He is describing the cost exactly. The failure itself is one button
        press — the bridge re-arms the patch automatically. Not NOTICING it is
        the expensive part: the instrument waits, the operator believes they
        have already pressed it, and the session stands still.
        """
        text = tr("The CR30 could not be read for patch {loc}: {message}. "
                  "Press the button on the instrument again."
                  ).format(loc=loc, message=message)
        self._log.appendPlainText(text)
        self._log.ensureCursorVisible()
        self._flash_status(text, duration_ms=8000)
        self._show_cr30_read_failed_window(loc, message)

    def _show_cr30_read_failed_window(self, loc: str, message: str) -> None:
        """The window for the above — modeless, and once per patch.

        MODELESS ON PURPOSE. The remedy is to press the button on the
        instrument, so a window that had to be dismissed first would stand
        between the user and the only thing that puts it right — and if they
        pressed the instrument while it was up, the reading would arrive behind
        a window still asking for it. It closes itself when the chart moves on.

        ONCE PER PATCH, for the same reason the retry limit exists: a flaky
        link can refuse the same patch five times, and five windows for one
        stuck patch is a worse interface than none. The second and later
        refusals of the same patch keep the log line and the status flash.
        """
        from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QLabel,
                                     QVBoxLayout)
        from workflow import measurement_messages as M

        if getattr(self, "_cr30_failed_window_for", None) == loc:
            return                     # already asking about this very patch
        self._close_cr30_read_failed_window()
        self._cr30_failed_window_for = loc

        title, body = M.M_CR30_READ_FAILED.render(loc=loc, reason=message)
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(460)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(14)
        lay.setContentsMargins(24, 20, 24, 20)
        # ESCAPE FIRST, THEN ADD THE BREAKS. The body carries {reason}, which
        # is the instrument's own sentence — and rich text would swallow a "<"
        # or start an entity at an "&". No message reaches here with either
        # today, which is exactly why it would be found the hard way.
        from html import escape
        label = QLabel(escape(body).replace("\n\n", "<br><br>"), dlg)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        lay.addWidget(label)
        box = QDialogButtonBox()
        box.addButton(tr("Close"), QDialogButtonBox.ButtonRole.AcceptRole)
        box.accepted.connect(dlg.accept)
        lay.addWidget(box)
        dlg.setModal(False)
        # It belongs to the measurement, so the ending closes it too
        # (Knut, beta.139).
        self._live_measure_windows.append(dlg)

        def _gone(_result, d=dlg):
            self._forget_measure_window(d)
            # AND FORGET THE PATCH IT WAS ABOUT. Otherwise the "already asked
            # about this one" flag outlives the window — the user closes it by
            # hand, or the session ends and the ending closes it, and the next
            # refusal of that same patch is silent because a window nobody can
            # see is remembered as still standing.
            if getattr(self, "_cr30_failed_dlg", None) is d:
                self._cr30_failed_dlg = None
                self._cr30_failed_window_for = None

        dlg.finished.connect(_gone)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        self._cr30_failed_dlg = dlg    # keep it referenced, or it is collected

    def _close_read_failed_window_if_moved_on(self, ev: dict) -> None:
        """Take the read-failure window down once the chart has moved past it.

        The window promises "This window will close by itself when the reading
        comes through", and that promise is the reason it asks nothing of the
        user. So it has to hold everywhere, including the two places where the
        prompt does not simply name a different patch:

        * on the chart's LAST patch the helper re-offers the same loc with
          `all_done`;
        * a patch that comes back marked `read` has been read.

        It must NOT close on the prompt that is still asking for the very
        reading it is about — that would show the message and take it away
        again in the same breath.

        Split out from `_on_patch_ready` so this decision can be tested for
        what it is, rather than through a handler that needs half the tab
        standing up around it.
        """
        waiting_for = getattr(self, "_cr30_failed_window_for", None)
        if waiting_for is None:
            return
        if waiting_for != str(ev.get("loc", "")) or ev.get("all_done") \
                or ev.get("read"):
            self._close_cr30_read_failed_window()

    def _close_cr30_read_failed_window(self) -> None:
        """Take the window down once the reading it asked for has arrived."""
        self._cr30_failed_window_for = None
        dlg = getattr(self, "_cr30_failed_dlg", None)
        self._cr30_failed_dlg = None
        if dlg is not None:
            try:
                dlg.accept()
            except RuntimeError:
                pass               # already gone with its parent

    def _on_cr30_readings_discarded(self, n: int) -> None:
        """The instrument took readings while no patch was armed.

        They belong to no patch anyone can name, so they are dropped — that is
        what stops a reading landing on the wrong patch. But to the operator
        those were button presses that did nothing, and an unexplained press is
        the thing that has made every version of this fault feel broken.
        """
        text = (tr("One reading was taken before ChromIQ was ready for it, so "
                   "it was not used. Read the highlighted patch again.")
                if n == 1 else
                tr("{n} readings were taken before ChromIQ was ready for them, "
                   "so they were not used. Read the highlighted patch again."
                   ).format(n=n))
        self._log.appendPlainText(text)
        self._log.ensureCursorVisible()
        self._flash_status(text, duration_ms=6000)

    def _on_cr30_rearmed(self, loc: str) -> None:
        """A patch that was already measured is ready to be measured again.

        Say so. Before this, clicking an already-read patch did nothing at all
        and looked exactly like a dead session — the preview highlighted it,
        the helper waited on it, and no reader was listening. Silence is what
        made that fault so expensive, so the re-arm must never be silent
        either.
        """
        text = tr("Patch {loc} was already measured. Read it again now to "
                  "replace that reading — press the button on the instrument."
                  ).format(loc=loc)
        self._log.appendPlainText(text)
        self._log.ensureCursorVisible()
        self._flash_status(text, duration_ms=8000)

    def _on_cr30_magnet(self, loc: str, message: str) -> None:
        """A magnet was at the aperture. The instrument has already
        recalibrated itself, and the session stops until that is put right.

        M-CR30-MAGNET (§M-PROPOSED). This is not "that reading was refused" —
        the reading is the least of it. The instrument performed a white
        calibration against whatever it was sitting on, so every reading from
        here would be wrong by an unknown factor and nothing downstream could
        tell. The owner hit exactly this with a sheet of paper on a MacBook,
        whose magnets reached through it: the old code refused the reading, told
        him to press the button again, and let the session continue.

        Nothing measured BEFORE this moment is affected — the refusal happens
        before any reading is accepted, so there is no suspect data to mark or
        discard, and nothing of his is touched.
        """
        from PyQt6.QtWidgets import QMessageBox
        from workflow import measurement_messages as M
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)

        self._log.appendPlainText("\n" + tr(
            "[STOPPED] A magnet was against the measuring opening, so the "
            "instrument recalibrated itself instead of measuring. Nothing "
            "more can be measured until its white calibration is taken "
            "again."))
        self._log.ensureCursorVisible()
        self._sound_instrument_fault_once()

        # A LOOP, BECAUSE THERE ARE ONLY TWO REAL WAYS OUT: recalibrate, or end
        # the session. Anything else leaves an instrument whose white reference
        # has been overwritten and a chart that cannot be measured against it,
        # and offering a third door would only mean pretending otherwise.
        while True:
            title, body = M.M_CR30_MAGNET.render(reason=message)
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.NoIcon)
            box.setWindowTitle(tr("The instrument has recalibrated itself"))
            box.setText(title)
            box.setInformativeText(body)
            again = box.addButton(tr("Recalibrate now"),
                                  QMessageBox.ButtonRole.AcceptRole)
            stop = box.addButton(tr("Stop the measurement"),
                                 QMessageBox.ButtonRole.DestructiveRole)
            box.setDefaultButton(again)
            fit_message_box_buttons(box)
            order_message_box_buttons(box, [again, stop])
            box.exec()

            if box.clickedButton() is again:
                # KEEPING the bridge, because it IS the stopped session: the
                # patch still outstanding, and the flag resume_after_magnet
                # clears.
                if self._run_cr30_calibration(keep_bridge=True):
                    break
                # Cancelled at the calibration window. Not an ending by itself.
            if self._end_after_magnet():
                return                     # the user ended the session
            # "Keep measuring" — so it is not ended, and the remedy comes back.

        bridge = getattr(self, "_cr30_bridge", None)
        if bridge is not None and bridge.resume_after_magnet():
            self._log.appendPlainText(tr(
                "Carrying on. Read the highlighted patch again — and check "
                "there is no magnet under your paper this time."))
            self._log.ensureCursorVisible()

    def _end_after_magnet(self) -> bool:
        """Offer the ending after a magnet. True if the session really ended.

        THE ONE ANSWER THIS HAS TO HANDLE IS "KEEP MEASURING", and it is the
        one the first version got wrong: `_end_session(None)` is deliberately a
        no-op, so declining to end left the session stopped with nothing armed
        and nothing on screen — the same dead end the magnet remedy was written
        to remove, reached by the other door.

        Resuming is NOT the answer either. The instrument's white reference has
        been overwritten; that is why the session stopped, and it is still true
        however the user answers a window about ending. So "keep measuring" is
        taken at its word — the session is not ended — and the caller puts the
        remedy back on screen, because recalibrating is the only thing that can
        make measuring possible again.
        """
        choice = self._confirm_end_of_session(self.END_FAILURE_WINDOW)
        self._end_session(choice)
        if choice is not None:
            return True
        self._log.appendPlainText(tr(
            "The measurement is still stopped: nothing can be read until the "
            "white calibration has been taken again."))
        self._log.ensureCursorVisible()
        return False

    def _on_cr30_device_lost(self, loc: str, message: str) -> None:
        """The instrument is gone — not merely unpressed.

        M-CR30-INSTRUMENT-GONE. Its wording is not approved yet, so like every
        other proposed message it says its piece in the log for now (§M).

        The ENDING, though, goes through the one exit every route shares
        (measurement_exit_strategy.md §1): the old handler for this called
        `abort()` directly, which is a second exit — and on any instrument that
        is not a CR30, `abort()` destroys the session, because stock chartread
        writes its .ti3 only on a clean exit. Nothing is at risk here (the
        helper saves after every patch), but the way out must still be the safe
        one, and the user must be the one who chooses it.
        """
        from PyQt6.QtWidgets import QMessageBox
        from workflow import measurement_messages as M
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)

        title, body = M.M_CR30_INSTRUMENT_GONE.render(loc=loc, reason=message)
        self._log.appendPlainText(f"\n[{title}]\n{body}")
        self._log.ensureCursorVisible()
        self._flash_status(title, duration_ms=10000)
        self._sound_instrument_fault_once()

        # IT SAYS ITS PIECE IN A WINDOW, and the owner ruled on that directly
        # (2026-08-30): *"if this is an important message this should be in a
        # pop up windows with benefitial options for this case"*. It used to
        # reach the log only, under the §M rule that unapproved wording speaks
        # through the log — while the user got the shared ending window with no
        # idea WHY it had appeared. An instrument that has vanished mid-chart
        # is not something to find out about by scrolling.
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("The instrument stopped answering"))
        box.setText(title)
        box.setInformativeText(body)
        again = box.addButton(tr("Carry on measuring"),
                              QMessageBox.ButtonRole.AcceptRole)
        stop = box.addButton(tr("Stop the measurement"),
                             QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(again)
        fit_message_box_buttons(box)
        order_message_box_buttons(box, [again, stop])
        box.exec()

        # Anything but "Carry on measuring" — including the red traffic light,
        # the Windows X and Esc, for all of which `clickedButton()` is None —
        # goes to the one shared ending window (measurement_exit_strategy.md
        # §1). That window offers "Keep measuring" of its own, and THAT is the
        # answer this handler has to finish properly.
        if box.clickedButton() is not again:
            choice = self._confirm_end_of_session(self.END_FAILURE_WINDOW)
            self._end_session(choice)
            if choice is not None:
                return
            # ⚠ "KEEP MEASURING", AND `_end_session(None)` IS A NO-OP.
            #
            # So declining to end used to leave the session standing with no
            # reader armed and nothing on screen — the same dead end that was
            # found and fixed at the magnet window one commit earlier, walked
            # straight back in through a window written the day after. Unlike
            # the magnet, carrying on here is legitimate: nothing about the
            # instrument's calibration is in doubt, it simply went away.
        self._carry_on_after_the_instrument_went(loc)

    def _carry_on_after_the_instrument_went(self, loc: str) -> None:
        """Re-arm the outstanding patch after the instrument came back.

        The helper's prompt is still outstanding, so the only thing missing is
        a reader — and the handle to the vanished instrument has been dropped,
        so this reopens it. If it is still not there the next attempt lands
        back at the window rather than in silence.
        """
        bridge = getattr(self, "_cr30_bridge", None)
        if bridge is not None and bridge.rearm():
            self._log.appendPlainText(tr(
                "Carrying on: reconnect the instrument and read the "
                "highlighted patch again."))
            self._log.ensureCursorVisible()
            return
        # NOTHING WAS RE-ARMED, so say so rather than let the user believe the
        # session is live. `rearm` returns False when the bridge is stopped or
        # has no outstanding patch, and a silent False here is precisely the
        # shape of every fault this area has had.
        self._log.appendPlainText(tr(
            "This measurement cannot carry on: there is no patch waiting to "
            "be read. Start the measurement again with “{refine}” ticked and "
            "ChromIQ will offer you only the patches that are still missing."
            ).format(refine=tr("Refine / resume existing measurement (-r)")))
        self._log.ensureCursorVisible()

    def _on_cr30_gave_up(self, loc: str, message: str) -> None:
        """One patch was refused over and over. M-CR30-PATCH-GAVE-UP.

        This does NOT end the session. Everything already read is safe, the
        helper is still alive, and the message names the two things that cause
        it — so the choice of what to do next is the user's.
        """
        from workflow import measurement_messages as M
        # The read-failure window for this patch says "press the button on the
        # instrument again". After the last retry nothing is armed, so that
        # sentence has stopped being true — and a window asking for a press
        # nothing is listening for is the exact fault this round removed
        # everywhere else.
        self._close_cr30_read_failed_window()
        title, body = M.M_CR30_PATCH_GAVE_UP.render(loc=loc, reason=message)
        self._log.appendPlainText(f"\n[{title}]\n{body}")
        self._log.ensureCursorVisible()
        self._flash_status(title, duration_ms=10000)
        self._sound_instrument_fault_once()

    def _on_cr30_mispaired(self, answered: str, reported: str) -> None:
        """The helper recorded a value against a patch we did not answer.

        This must stop the read, not warn about it: every reading after a
        mis-pairing is suspect, and a wrong colour in the .ti3 is invisible to
        everything downstream of it.
        """
        text = tr("ChromIQ stopped this measurement: a reading it took for "
                  "patch {answered} was recorded against patch {reported}. "
                  "Nothing already saved is affected. Please start the "
                  "measurement again and report this."
                  ).format(answered=answered, reported=reported)
        log.error("CR30 mispairing: answered %s, recorded %s", answered, reported)
        self._log.appendPlainText(text)
        self._log.ensureCursorVisible()
        self._flash_status(text, duration_ms=15000)
        try:
            self._on_stop()
        except Exception:      # noqa: BLE001 — the message is what matters
            log.debug("could not stop the run after a mispairing", exc_info=True)

    def _show_cr30_measuring_window(self) -> None:
        """The "how to measure" window for a reader ChromIQ drives itself (#159).

        Every other instrument gets this through `calibration_done` —
        `_on_calibration_done` is the ONLY route to
        `patch_measurement_instructions_html`. Under `-x` the helper opens no
        instrument and `cq_handle_calibrate` is inside `if (xtern == 0)`, so
        that signal cannot fire and a CR30 user was given a spot session with
        no on-screen instruction at all (finding F9).

        Modeless, and shown once per measurement: the reading is driven by the
        instrument's own button, so a modal would sit between the user and the
        preview they are meant to be watching.
        """
        if getattr(self, "_cr30_how_shown", False):
            return
        self._cr30_how_shown = True
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        from ui.ti2_loader import patch_measurement_instructions_html
        from workflow import measurement_messages as M

        title, body = M.M_CR30_HOW_TO_MEASURE.render(
            how=patch_measurement_instructions_html("cr30"))
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(520)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(14)
        lay.setContentsMargins(24, 20, 24, 20)
        # The §M body is plain text with {how} carrying HTML, so the paragraph
        # breaks are turned into markup here rather than in the catalogue —
        # a message constant must never hold layout (feedback: no Markdown in
        # message strings).
        msg = QLabel(body.replace("\n\n", "<br><br>"), dlg)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setWordWrap(True)
        lay.addWidget(msg)
        box = QDialogButtonBox()
        ok = box.addButton(tr("Start measuring"),
                           QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("primary")
        box.accepted.connect(dlg.accept)
        lay.addWidget(box)
        dlg.setModal(False)
        # IT BELONGS TO THE MEASUREMENT, SO IT ENDS WITH IT.
        #
        # Knut's rule, beta.139: *"When the measurement session ends,
        # everything relating to measurements should end."* This window was
        # never registered, because the registry is filled by
        # _exec_measure_dialog and this one is shown rather than exec'd — so it
        # sat on screen after the session it explains had finished, telling the
        # user how to measure a chart nothing was reading. Found on Windows,
        # reproduced on macOS.
        self._live_measure_windows.append(dlg)
        dlg.finished.connect(lambda _r, d=dlg: self._forget_measure_window(d))
        dlg.show()
        self._cr30_how_dlg = dlg          # keep it referenced, or it is collected

    def _forget_measure_window(self, dlg) -> None:
        """Drop a window from the live registry once it has closed itself."""
        try:
            self._live_measure_windows.remove(dlg)
        except ValueError:
            pass

    def _on_engine_fallback_refused(self, reason: str) -> None:
        """The read failed and there is no reader to fall back to (#159).

        Stock ArgyllCMS chartread refuses this chart's ``TARGET_INSTRUMENT``
        before the first patch, so the rescue the other two handlers announce
        would only produce a second, more confusing failure. Say the one true
        thing instead — and say it from §M, not from a `tr()` invented here.

        The reason is the helper's own sentence when it printed one; it used to
        render as "unknown error" while the helper had said exactly what was
        wrong (`MeasureManager._engine_failure_reason`).
        """
        from workflow import measurement_messages as M
        title, body = M.M_CR30_READ_ENDED.render(reason=reason)
        self._log.appendPlainText(f"[{title}]\n{body}")
        self._log.ensureCursorVisible()
        self._flash_status(title, duration_ms=8000)

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
            tr("<b>Place sheet {sheet_n} of {total} on the XY table.</b><br><br>Press <b>{continue_}</b> when the sheet is positioned, or <b>{give_up}</b> to stop without saving.").format(sheet_n=sheet_n, total=total,
                    continue_=tr("Continue"), give_up=tr("Give Up")),
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
            # ASK AFTER THIS WINDOW HAS CLOSED, never before.
            # _give_up_or_save() opens the ending question, and dlg.accept()
            # only runs after it returns — so the question appeared ON TOP of
            # the failure window it belongs to. Knut, beta.141: *"it appears on
            # top of the previous window (the window was not closed, or it came
            # more than once)"*, on all three of these windows.
            chosen[0] = self.GIVE_UP_PENDING
            dlg.accept()

        cont_btn.clicked.connect(_cont)
        give_btn.clicked.connect(_give_up)

        btn_row.addWidget(cont_btn)
        btn_row.addStretch()
        btn_row.addWidget(give_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        self._exec_measurement_window(dlg)
        chosen[0] = self._resolve_give_up(chosen[0])
        self._send_failure_choice(chosen[0])
        self._arm_key_watchdog()
        if chosen[0] not in ("\x1b", self.END_SAVE):
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
        self._cue_window("INSTRUMENT_ERROR")
        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Confirm Abort"))
        dlg.setMinimumWidth(420)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)
        # KNUT'S WORDING, ACCEPTED VERBATIM (#130, 2026-08-06: "Accepted
        # suggestion for text").
        #
        # The old title was "Stop measuring without saving?", which is true on
        # stock chartread — Yes sends 'y' and the readings are gone — but false
        # on the engine since beta.156, where Yes opens "Keep what you have
        # measured so far?" and OFFERS to save. The question and the outcome
        # disagreed on the default reader, so a careful reader would think Yes
        # discarded their work.
        msg = QLabel(
            tr("<b>Stop measuring?</b><br><br>"
               "You will be asked next whether to keep the strips you have "
               "already measured, so nothing is thrown away by mistake."),
            dlg,
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        chosen = ["n"]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        yes_btn = QPushButton(tr("Yes — Stop"), dlg)
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
        if chosen[0] == "y" and self._manager.engine_active:
            # ABORT GOES THROUGH THE ONE ENDING, like everything else.
            #
            # "y" is chartread's own answer and it throws the readings away
            # with no offer to keep them — the clearest break of the model's
            # single exit, and the one Knut ruled on (beta.155): *"The 'Abort?'
            # confirm should be replaced with calling the 'Keep what you have
            # measured so far?' chain."*
            #
            # So chartread is told **no** — it leaves its own question and goes
            # back to the prompt it came from — and OUR ending runs instead.
            # That is what keeps his warning satisfied: *"the buttons pressed
            # is different for patch-per-patch mode or strip mode"*. This sends
            # no mode-specific key of its own; `_end_session` delegates to
            # `send_save_partial_and_quit` / `abort`, which already know which
            # mode and which reader they are in.
            self._send_failure_choice("n")
            self._end_session(self._confirm_end_of_session(self.END_ABORT_KEY))
            self._arm_key_watchdog()
            return
        self._send_failure_choice(chosen[0])
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
            "\n" + tr("[ERROR] Instrument disconnected — stopping measurement."))
        self._log.ensureCursorVisible()
        self._sound_instrument_fault_once()
        # THE ONE EXIT, not abort().
        #
        # abort() is a second exit, which §1 of measurement_exit_strategy.md
        # forbids outright — and on every instrument that is not a CR30 it
        # destroys the session, because stock chartread writes its .ti3 only on
        # a clean exit. So a disconnect used to be survivable for a CR30 and
        # fatal for an i1Pro on the very same line. The helper is still alive
        # after a disconnect — the instrument went away, not the process — so
        # the ordinary ending works from here, and the user chooses it.
        self._end_session(self._confirm_end_of_session(self.END_FAILURE_WINDOW))

    def _sound_instrument_fault_once(self) -> None:
        """Sound the instrument error the moment the fault appears — once.

        Knut reversed the 2-second design (#130, 2026-07-29): *"Leave the code
        as it was earlier: the instrument sound appearing immediately, and then
        the instrument error window appearing when the error run ends, but then
        keep the sound also when the window appears."*

        **Once, though, not once per line.** A pulled cable produces dozens of
        identical messages, and the original wiring — the cue hung off the
        signal — fired on every one of them. That is the only part of the older
        behaviour not restored here, and deliberately: he asked for a sound when
        the fault appears, not for a burst of them.
        """
        if getattr(self, "_instrument_fault_sounded", False):
            return
        self._instrument_fault_sounded = True
        self._cue_window("INSTRUMENT_ERROR")

    def _show_instrument_disconnected_window(self) -> None:
        """The "Instrument Disconnected" window, with its sound.

        Shared by the two paths that can raise it: the 2-second rule while the
        fault is still happening, and the end of the run for a fault that only
        became clear once the reader stopped.
        """
        self._cue_window("INSTRUMENT_ERROR")   # as the window opens
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
        from ui.widgets import ButtonFontFilter
        ButtonFontFilter.fit_window(dlg)
        self._exec_measurement_window(dlg)

    def _is_last_unread_strip(self) -> bool:
        """True when the strip that just failed is the only one still unread.

        "Skip Strip" asks ArgyllCMS for the next UNREAD strip, and that search
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

        # ONE QUESTION AT A TIME. A pre-measurement window — "This chart was
        # made for a different instrument" — runs its own event loop, so
        # chartread's output keeps arriving while it waits for an answer, and a
        # failure window could open on top of a question nobody had answered
        # yet. Knut, beta.135: *"Then I touched the button by accident, and
        # another window came on top, the 'Strip Read Failed'. The first window
        # must be terminated/finished before other windows should be allowed."*
        # The calibration prompt already deferred itself this way; this is the
        # same rule for the same reason.
        if getattr(self, "_pre_measure_window_open", False):
            self._deferred_strip_error = reason
            return

        # Sound FIRST: this handler opens a modal dialog and blocks inside its
        # own slot, so anything connected after it could not be heard until the
        # dialog was dismissed. The cue belongs to the window appearing (Knut,
        # #131 2026-07-26) — and there is deliberately no sound on the buttons,
        # because the failure has already been announced.
        self._on_strip_error_sound(reason)

        # "All Strips Read" is always the LAST window (Knut): while any strip
        # window is up, the completion window waits its turn.
        self._pace_prompt_open = True

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Patch Read Failed")
                          if bool(getattr(self, "_spot_session", False))
                          else tr("Strip Read Failed"))
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
                "<i>{save_partial}</i>. If the instrument stays silent, "
                "the readings from this session cannot be saved."
            ).format(save_partial=_save_partial_name()) + "<br><br>"
        elif bool(getattr(self, "_spot_session", False)):
            # Reading one patch at a time there is no swipe, so swipe advice is
            # not merely unhelpful — it describes an action the user is not
            # performing (Knut, #131 2026-07-27).
            advice = tr(
                "<b>The patch could not be read:</b> {reason}<br><br>"
                "Place the instrument flat on the patch, covering it fully, and "
                "read again. If the error keeps happening, check that the "
                "instrument is on the patch the arrow points to and that the "
                "sheet is lying flat."
            ).format(reason=reason) + "<br><br>"
        else:
            advice = tr(
                "<b>The strip could not be read:</b> {reason}<br><br>"
                "Re-position your instrument at the beginning of the strip and try again. "
                "If the error keeps occurring, try scanning more slowly and steadily, or "
                "raise the <i>Patch consistency tolerance</i> setting before the next run."
            ).format(reason=reason) + "<br><br>"

        # Worked out before the text, because the second choice changes both
        # its name and what it does when this is the only unread stripe.
        last_one = self._is_last_unread_strip()
        _spot = bool(getattr(self, "_spot_session", False))
        if last_one and _spot:
            # No "finish without this one" button here: it did exactly what
            # Save Partial & Quit does, and two buttons for one action is a
            # question the user has to answer for no reason (Knut, #131
            # 2026-07-28). What it explained is now said by the remaining one.
            choices = tr(
                "&nbsp;&nbsp;<b>{retry}</b> — read this same patch again.<br>"
            ).format(retry=tr("Retry"))
        elif last_one:
            choices = tr(
                "&nbsp;&nbsp;<b>{retry}</b> — read this same strip again.<br>"
            ).format(retry=tr("Retry"))
        elif _spot:
            choices = tr(
                "&nbsp;&nbsp;<b>{retry}</b> — read this same patch again.<br>"
                "&nbsp;&nbsp;<b>{skip}</b> — leave this patch unread and move "
                "on to the next one. You can come back to it later in this "
                "session; the chart is not finished until every patch has a "
                "reading.<br>"
            ).format(retry=tr("Retry"), skip=tr("Skip Patch"))
        else:
            choices = tr(
                "&nbsp;&nbsp;<b>{retry}</b> — read this same strip again.<br>"
                "&nbsp;&nbsp;<b>{skip}</b> — leave this strip unread for now "
                "and jump to the next unread one. You can come back to it later in "
                "this session.<br>"
            ).format(retry=tr("Retry"), skip=tr("Skip Strip"))
        # Describe only what is on screen: no "nowhere to skip to", because
        # there is no Skip button in this case to refer to (Knut's standing
        # rule, restated #131 2026-07-28).
        if last_one and _spot:
            save_text = tr(
                "&nbsp;&nbsp;<b>{save_partial}</b> — ends the measurement "
                "and saves every patch you have read. This patch stays unread, "
                "and nothing else is lost. Next time you load this chart, "
                "<i>Continue Measurement</i> picks up from here."
            ).format(save_partial=_save_partial_name())
        elif last_one:
            save_text = tr(
                "&nbsp;&nbsp;<b>{save_partial}</b> — ends the measurement "
                "and saves every strip you have read. This strip stays unread, "
                "and nothing else is lost. Next time you load this chart, "
                "<i>Continue Measurement</i> picks up from here."
            ).format(save_partial=_save_partial_name())
        else:
            save_text = tr(
                "&nbsp;&nbsp;<b>{save_partial}</b> — stop here and save what "
                "you have read so far. Next time you load this chart, "
                "<i>Continue Measurement</i> will pick up where you left off."
            ).format(save_partial=_save_partial_name())
        msg = QLabel(advice + choices + save_text, dlg)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        # "retry" → send "\r"                     (any key = retry)
        # "skip"  → the manager picks the next unread strip, or simply the next
        #           one when the chart is complete
        # "save"  → two 'q's: the first stops the armed strip, the second
        #           answers chartread's give-up prompt, and THAT is what makes
        #           it write the .ti3 and exit (Knut established this by hand,
        #           #130 2026-07-30)
        chosen = ["retry"]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        retry_btn = QPushButton(tr("Retry"), dlg)
        # Reading one patch at a time, this window is about a patch — so the
        # button says so (Knut, #131 2026-07-28: "This button could in this mode
        # become 'skip patch' feature").
        _spot = bool(getattr(self, "_spot_session", False))
        # On the LAST unread one there is nothing to skip to, and the button
        # that used to stand here did exactly what Save Partial & Quit does —
        # so it is gone, and its explanation moved there (Knut, #131
        # 2026-07-28). Retry and Save Partial & Quit remain, which is the whole
        # of the choice.
        skip_btn = None
        if not last_one:
            skip_label = tr("Skip Patch") if _spot else tr("Skip Strip")
            skip_btn = QPushButton(skip_label, dlg)
        if _spot and skip_btn is not None:
            skip_btn.setToolTip(tr(
                "Leaves this patch unmeasured and moves on to the next one. "
                "You can come back to it later — the chart is not finished "
                "until every patch has a reading."))
        save_btn  = QPushButton(tr("Save Partial && Quit"), dlg)
        retry_btn.setObjectName("primary")
        retry_btn.setFixedHeight(32)
        if skip_btn is not None:
            skip_btn.setFixedHeight(32)
        save_btn.setFixedHeight(32)

        def _retry():
            chosen[0] = "retry"
            dlg.accept()

        def _skip():
            chosen[0] = "skip"
            dlg.accept()

        def _save():
            chosen[0] = "save"
            dlg.accept()

        retry_btn.clicked.connect(_retry)
        if skip_btn is not None:
            skip_btn.clicked.connect(_skip)
        save_btn.clicked.connect(_save)

        btn_row.addWidget(retry_btn)
        if skip_btn is not None:
            btn_row.addWidget(skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        tint_dialog_primary(dlg, _TAB_COLOR)
        self._exec_measurement_window(dlg)
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
        elif chosen[0] == "skip":
            # The manager decides what "skip" can mean: the next unread strip
            # while anything is unread, otherwise simply the next strip — on a
            # complete chart there is no unread one to go to (Knut, #131
            # 2026-07-27).
            self._manager.skip_current_strip()
        else:  # save partial and quit
            # Two 'q's, sent one after the other by the manager: the first
            # stops the armed strip, the second answers "Hit Esc or 'q' to give
            # up" — and chartread then writes the .ti3 and exits.
            self._manager.send_save_partial_and_quit()

        self._arm_key_watchdog()
        QApplication.instance().installEventFilter(self)
        # On the save path chartread will exit on its own once 'y' is sent,
        # and _on_measure_done will then re-enable the UI and auto-arm resume.

    def _on_calibration_prompt(self, cond: str = "", message: str = "",
                               optional: bool = False) -> None:
        # A check that must be settled before measuring is on screen — hold this
        # window until it has been answered, and open it afterwards. Knut, #130
        # 2026-07-30: *"Two windows popped up simultaneously, first 'This chart
        # was made for a different instrument' … then 'Calibration Required'
        # came on top. The window check that makes [it] appear should come
        # first, and should be completed before progressing … Any check that has
        # a window popup that come before going into actual measurement mode,
        # should be handled and completed first."*
        #
        # They stacked because the first window runs a nested event loop, which
        # keeps delivering chartread's output — so the second one opened on top
        # of a question that had not been answered yet.
        if getattr(self, "_pre_measure_window_open", False):
            self._deferred_calibration = (cond, message, optional)
            return
        self._cue_window("INSTRUMENT_ERROR")
        from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout,
                                     QLabel, QVBoxLayout)

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Calibration Required"))
        dlg.setMinimumWidth(500)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)
        _outer = layout             # the buttons stay on the dialog, not in a column

        from ui.ti2_loader import (calibration_instructions_html,
                                    instrument_family)
        _fam_cal = instrument_family(self._detected_instrument)
        msg = QLabel(
            calibration_instructions_html(_fam_cal),
            dlg,
        )
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setWordWrap(True)

        # THE DIAL, DRAWN, for the one instrument whose calibration is a
        # position on a wheel. "Turn it to the gear" is a sentence somebody has
        # to map onto a device in their hand; the picture shows which mark and
        # which way (Basti, 2026-09-01). Every other instrument keeps the words
        # alone, because for them there is no wheel to point at.
        #
        # NOTHING SITS UNDER THE PICTURE. The picture is a column of its own and
        # every line of text is a column of its own, so the instrument's own
        # words start on the same left edge as the paragraph above them rather
        # than stepping back under the wheel (Basti, 2026-09-01).
        if _fam_cal == "colormunki":
            from ui.dial_pictogram import dial
            dlg.setMinimumWidth(620)
            _pic = QLabel(dlg)
            _pic.setPixmap(dial("calibrate", dlg, 150))
            _pic.setAlignment(Qt.AlignmentFlag.AlignTop)
            _row = QHBoxLayout()
            _row.setSpacing(18)
            _row.addWidget(_pic, 0, Qt.AlignmentFlag.AlignTop)
            _text_col = QVBoxLayout()
            _text_col.setSpacing(16)
            _row.addLayout(_text_col, 1)
            layout.addLayout(_row)
            layout = _text_col          # every text widget below joins the column
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
        # SKIP IS ITS OWN ANSWER, AND IT HAS TO WIRE ITSELF.
        #
        # `DestructiveRole` emits neither `accepted` nor `rejected`, so with
        # nothing connected to it the button did nothing at all — clicked five
        # times, the window stayed up (challenge round, 2026-09-01). It is
        # remembered in a flag rather than read back afterwards; see the exec
        # below for why that matters.
        skipped = {"asked": False}
        skip_btn = None
        if optional:
            skip_btn = btn_box.addButton(
                tr("Skip this step"),
                QDialogButtonBox.ButtonRole.DestructiveRole)

            def _skip() -> None:
                skipped["asked"] = True
                dlg.done(QDialog.DialogCode.Accepted.value)

            skip_btn.clicked.connect(_skip)
        # A real Cancel, because the only way out was the window's close box and
        # that is not obvious (Knut, #131 2026-07-27: "so that a user is not
        # confused how to stop the calibration and the measurement session.
        # Sometimes that is needed"). It does what closing the window did —
        # cancels the calibration and ends the reading cleanly.
        cancel_btn = btn_box.addButton(tr("Cancel Measurement"),
                                       QDialogButtonBox.ButtonRole.RejectRole)
        cancel_btn.setToolTip(tr(
            "Stops the calibration and ends this measurement. Anything already "
            "measured has been saved as you went, so nothing is lost."))
        btn_box.rejected.connect(dlg.reject)
        btn_box.accepted.connect(dlg.accept)
        _outer.addWidget(btn_box)

        tint_dialog_primary(dlg, _TAB_COLOR)
        result = dlg.exec()
        # THE FLAG, NOT `clickedButton()`. That is `QMessageBox`'s API;
        # `QDialogButtonBox` has no such method, so this line raised
        # `AttributeError` on EVERY exit of this window whenever the step was
        # optional — Start Calibration, Cancel, Esc, the close box alike. In a
        # Qt slot an unhandled exception is not a log line: PyQt6 calls
        # `qFatal()` and the process ends, mid measurement, with chartread's
        # `.ti3` unwritten. It survived because `optional` is only ever set by
        # a SwatchMate Cube, and because the `and` short-circuits for every
        # other instrument, so no test ever reached it.
        if skipped["asked"]:
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
            QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
            QVBoxLayout,
        )

        QApplication.instance().removeEventFilter(self)

        dlg = QDialog(self)
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)
        _outer = layout             # the buttons stay on the dialog, not in a column

        # THE WINDOW THAT ONLY OPENS AFTER THE INSTRUMENT HAS CALIBRATED. Two
        # more values folded into two answers, so the light-grey appearance got
        # the dark one: a near-black card (`#181818`) with the Measure tab's
        # green on every key cap, in the middle of a colourless dialog. It takes
        # an instrument on the desk to reach, which is why nothing had drawn it.
        from ui.theme import APPEARANCE_NEUTRAL, accent_for, resolve_mode
        _mode = resolve_mode(self._settings.get("appearance", "auto"))
        if _mode == APPEARANCE_NEUTRAL:
            from ui import neutral_styles as _n
            _frame_bg, _frame_border, _dim_text = (_n.NM_BG_SURFACE,
                                                   _n.NM_BORDER,
                                                   _n.NM_TEXT_FAINT)
        elif _mode == "light":
            _frame_bg, _frame_border, _dim_text = "#f7f4ef", "#d0ccc6", "#7a7570"
        else:
            _frame_bg, _frame_border, _dim_text = "#181818", "#2a2a2a", "#909090"
        _frame_style = (
            f"QFrame {{ background: {_frame_bg}; border: 1px solid {_frame_border};"
            " border-radius: 6px; }"
        )
        _key_style = (
            f"font-family: Menlo, monospace; font-weight: 700;"
            f" color: {accent_for(_TAB_COLOR, _mode)};"
            " background: transparent; border: none;"
        )
        _dim_style = f"color: {_dim_text}; background: transparent; border: none;"
        _plain_style = "background: transparent; border: none;"

        # Instrument-specific "how to scan a strip" wording, shared by all three
        # variants below (standard / guided / resume) so the physical steps match
        # the chart's instrument (ColorMunki dial, i1Pro base-and-slide, …).
        from ui.ti2_loader import (instrument_family,
                                    measurement_instructions_html,
                                    patch_measurement_instructions_html)
        _fam = instrument_family(self._detected_instrument)
        # Patch by patch there is no swipe, so the steps are the single-patch
        # ones for the same instrument (Knut, #131 2026-07-28).
        _how = (patch_measurement_instructions_html(_fam) if self._spot_session
                else measurement_instructions_html(_fam))

        # THE DIAL AGAIN, IN ITS MEASURING POSITION. The calibration window
        # showed the wheel turned to the gear; this one shows the same wheel
        # turned to the target mark, so the two windows read as one movement of
        # one physical thing rather than two unrelated instructions (Basti,
        # 2026-09-01). It sits at the top for every variant of this window,
        # because every variant then goes on to say "turn the dial".
        #
        # Nothing sits under the picture here either: it takes a column of its
        # own and every variant's text goes into the column beside it.
        if _fam == "colormunki":
            from ui.dial_pictogram import dial
            dlg.setMinimumWidth(660)
            _pic = QLabel(dlg)
            _pic.setPixmap(dial("measure", dlg, 150))
            _dial_row = QHBoxLayout()
            _dial_row.setSpacing(18)
            _dial_row.addWidget(_pic, 0, Qt.AlignmentFlag.AlignTop)
            _text_col = QVBoxLayout()
            _text_col.setSpacing(14)
            _dial_row.addLayout(_text_col, 1)
            layout.addLayout(_dial_row)
            layout = _text_col

        if self._spot_session:
            dlg.setWindowTitle(tr("Calibration Complete — How to Measure"))

            # The instrument's OWN steps belong here too — this window was the
            # only one of the three that dropped them, so patch by patch you
            # were told "take a reading" without being told how your particular
            # instrument takes one (Knut, #131 2026-07-28).
            msg = QLabel(
                tr("<b>Calibration complete. You are ready to measure patch by "
                   "patch.</b><br><br>Place the instrument on the "
                   "<b>highlighted patch</b> in the preview and take a reading. "
                   "The next patch is highlighted automatically.<br><br>{how}"
                   ).format(how=_how),
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
                # Click-to-jump is the ChromIQ reading engine's own feature —
                # it needs the engine's patch positions. Listing it under stock
                # chartread promises something that cannot happen (Knut,
                # #130 beta.120).
                *(((tr("click"),
                    tr("Click a patch in the preview to jump to it")),)
                  if self._engine_selected() else ()),
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

            # Real singular and plural, never "(s)": one strip to re-measure is
            # a common case here, and "1 strip(s)" reads like a bug.
            body = (tr("<b>Calibration complete. The app will guide you to the "
                       "strip.</b><br><br>There is <b>1 strip</b> to re-measure. "
                       "The app will navigate chartread to it for you — <b>you "
                       "do not need to press f or b yourself.</b>")
                    if n == 1 else
                    tr("<b>Calibration complete. The app will guide you to each "
                       "strip.</b><br><br>There are <b>{n} strips</b> to "
                       "re-measure. The app will automatically navigate "
                       "chartread to each one — <b>you do not need to press f "
                       "or b yourself.</b>").format(n=n))
            msg = QLabel(body, dlg)
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
                   "</b><br><br>{how}<br><br>Then proceed strip by strip until "
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
                ("f", tr("Move to the next strip")),
                ("b", tr("Move back to the previous strip")),
                ("n", tr("Jump to the next unread strip")),
                ("d", tr("Finish and save when all strips are done")),
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
        _outer.addWidget(btn_box)

        tint_dialog_primary(dlg, _TAB_COLOR)
        self._exec_measurement_window(dlg)
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
        # ALL STRIPS IS NOT ALL PATCHES (#156, Knut).
        #
        #     "When finishing strip G (last strip) the 'All Strips Read' message
        #     comes, despite that the progress percentage shows 97.1% (since 3
        #     patches are not read in strip B). This message must come only when
        #     all patches are read, as some patches may be missing, so all
        #     patches read shall be the finishing metric, not strips read."
        #
        # A strip can be accepted while individual patches inside it were never
        # recorded — which is exactly what a refinement pass exists to pick up.
        # Announcing the chart finished at that moment invites the user to walk
        # away from an unfinished measurement, and it was his own progress bar
        # that caught the contradiction on screen.
        unread = self._unread_patch_count()
        if unread:
            # Say nothing in a window. Knut's requirement is that the finished
            # message *"must come only when all patches are read"* — so the fix
            # is to stop showing it, not to invent a replacement. A new window
            # needs new wording, and measurement wording goes to §M-PROPOSED for
            # approval before it reaches a tab.
            self._all_done_shown = True
            if unread == 1:
                self._log.appendPlainText(tr(
                    "Every strip has been read, but 1 patch still has no "
                    "reading. Measure again with patch-by-patch mode to pick "
                    "it up."))
            else:
                self._log.appendPlainText(tr(
                    "Every strip has been read, but {n} patches still have no "
                    "reading. Measure again with patch-by-patch mode to pick "
                    "them up.").format(n=unread))
            return
        self._all_done_shown = True

        # The final strip's own "read OK" cue is still sounding when the chart
        # finishes, so the completion sound landed on top of it (Knut, #131
        # 2026-07-27). Give the cue its moment, then show the window — the
        # guard above has already been set, so this cannot run twice.
        QTimer.singleShot(_ALL_DONE_SOUND_GAP_MS, self._show_all_stripes_done)

    def _calibration_options_on(self) -> bool:
        """Whether Preferences → Calibration options is switched on.

        Tab 4 is called "4. Build Profile" normally and "4. Calibration &
        Profiling" while this is on, so anything that NAMES that tab has to ask
        (Knut, beta.148).
        """
        return bool(self._settings.get("calibration_mode", False))

    def _profile_tab_name(self) -> str:
        """What tab 4 is called right now, for text that points the user at it.

        For prose and for rich text. A **button** needs `_profile_tab_name_btn`
        instead — see there.
        """
        return (tr("Calibration & Profiling") if self._calibration_options_on()
                else tr("Build Profile"))

    def _profile_tab_name_btn(self) -> str:
        """The same name, safe to put on a QPushButton.

        Qt reads "&" in button text as the mnemonic marker: it eats the
        ampersand and underlines the letter after it, so "Calibration &
        Profiling" came out as *"CALIBRATION _PROFILING"*. Knut, beta.150:
        *"The _ is here some unknown sign, maybe in place of the & sign."* It
        is; doubling it prints one.
        """
        return self._profile_tab_name().replace("&", "&&")

    def _show_all_stripes_done(self) -> None:
        """The completion sound and window, after the short gap that keeps the
        last strip's cue from being drowned out."""

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
            dlg.setWindowTitle(tr("Verification Measurement — All Strips Read"))
            dlg.setMinimumWidth(560)
            lay = QVBoxLayout(dlg)
            lay.setSpacing(16)
            lay.setContentsMargins(24, 20, 24, 20)
            msg = QLabel(tr(
                "<b>All strips have been read.</b><br><br>This is a "
                "<b>verification measurement</b> of a colour-managed print, so it "
                "will be saved as a separate <b>verify</b> file and is <b>not</b> "
                "for building a profile.<br><br>Click <b>Finish</b> to save it, "
                "then open it in <b>Tools ▸ Inspect a measurement</b> to check how "
                "the profile performed. Or click <b>Re-read Individual Strips</b> to scan a "
                "strip again (<b>f</b>&nbsp;/&nbsp;<b>b</b> to move, <b>n</b> for "
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
            reread = QPushButton(tr("Re-read Individual Strips"), dlg)
            reread.setToolTip(_REREAD_TOOLTIP())
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
            # The rest of the window is identical either way; only the opening
            # sentence counts, so only that varies (real plural, never "(s)").
            _opening = (tr("<b>The chart strip has been re-measured "
                           "successfully.</b>") if n == 1 else
                        tr("<b>All {n} chart strips have been re-measured "
                           "successfully.</b>").format(n=n))
            msg = QLabel(
                _opening
                + tr("<br><br>What would you like to do next?<br><br>&nbsp;&nbsp;•&nbsp; <b>Build Profile</b> — saves the measurement and takes you straight to the Build Profile tab to create your updated ICC profile.<br><br>&nbsp;&nbsp;•&nbsp; <b>Continue Measuring Manually</b> — keeps chartread running so you can scan additional strips yourself. You will have <b>full manual control</b>: use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move between strips, <b>n</b> to jump to the next unread one, and <b>d</b> when you are done. The automatic strip navigation is switched off for the rest of this session."),
                dlg,
            )
        elif is_cal:
            dlg.setWindowTitle(tr("Calibration Measurement Complete"))
            msg = QLabel(
                tr("<b>All strips of your calibration chart have been read successfully.</b><br><br>"
                "The measurement data has been saved. The next step is to turn it into a "
                "<b>calibration file (.cal)</b> — click <b>Create Calibration File</b> to go "
                "directly to the <b>4. Calibration &amp; Profiling</b> tab, where the file "
                "path is already filled in and ready to go.<br><br>"
                "If you would like to re-read any strip first, click <b>Re-read Individual Strips</b>. "
                "Use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move forward and back between strips, "
                "<b>n</b> to jump to the next unread strip, and press <b>d</b> when you "
                "are done.<br><br>"
                "<span style='color:#909090;'>These instructions are always visible in "
                "the output log below.</span>"),
                dlg,
            )
        elif self._spot_session:
            dlg.setWindowTitle(tr("All Patches Read"))
            msg = QLabel(
                tr("<b>All patches have been read successfully.</b><br><br>"
                "Click <b>Go to {tab} Tab</b> to finalise the measurement and "
                "go straight to that tab — the next and final step.<br><br>"
                "If you would like to re-read any patch first, click <b>Re-read Patches</b>. "
                "Use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move forward and back between patches, "
                "<b>n</b> to jump to the next unread patch, click a patch in the preview to "
                "jump to it, and press <b>d</b> when you are done.<br><br>"
                "<span style='color:#909090;'>These instructions are always visible in "
                "the output log below.</span>").format(tab=self._profile_tab_name()),
                dlg,
            )
        else:
            dlg.setWindowTitle(tr("All Strips Read"))
            msg = QLabel(
                tr("<b>All strips have been read successfully.</b><br><br>"
                "Click <b>Go to {tab} Tab</b> to finalise the measurement and "
                "go straight to that tab — the next and final step.<br><br>"
                "If you would like to re-read any strip first, click <b>Re-read Individual Strips</b>. "
                "Use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move forward and back between strips, "
                "<b>n</b> to jump to the next unread strip, and press <b>d</b> when you "
                "are done.<br><br>"
                "<span style='color:#909090;'>These instructions are always visible in "
                "the output log below.</span>").format(tab=self._profile_tab_name()),
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
            #
            # …and it has to say the name the tab is ACTUALLY wearing. Tab 4 is
            # "4. Build Profile" normally and "4. Calibration & Profiling" while
            # Preferences → Calibration options is on, so a button that always
            # said "Build Profile" sent the user looking for a tab that is not
            # there. Knut, beta.148: *"this last button must change its name …
            # When Calibration mode is OFF again in preferences the button name
            # … shall again be named 'Go to Build Profile tab' (as before)."*
            accept_label = tr("Go to {tab} Tab →").format(
                tab=self._profile_tab_name_btn())
        # tr() on all three: these feed a QPushButton, so without it the button
        # reads English in every language while the help text two lines up names
        # it translated. Found by the Swedish translator, not by any test —
        # "Re-read Individual Strips" was already a catalogue key with a
        # translation waiting that the button never asked for.
        if self._guided_refinement_active:
            cont_label = tr("Continue Measuring Manually")
        elif self._spot_session:
            cont_label = tr("Re-read Patches")
        else:
            cont_label = tr("Re-read Individual Strips")

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cont_btn = QPushButton(cont_label, dlg)
        if cont_label == tr("Re-read Individual Strips"):
            cont_btn.setToolTip(_REREAD_TOOLTIP())
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
            "Saves the measurement and opens the {tab} tab. The profile is not "
            "built yet — press “Build Profile” there when your settings are how "
            "you want them.").format(tab=self._profile_tab_name()))
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
        """The 'All Strips Read' dialog when measurement averaging is on.

        First read of a chart → Re-read Individual Strips / Measure again to average /
        Build Profile. Mid-set (≥1 read already saved) → Use last read only /
        Measure again to average / Average all reads & build. The chosen action is
        stored in ``_pending_avg_action`` so :meth:`_on_measure_done` can act on it
        once chartread has written the final .ti3 (it isn't final while chartread
        is still running). 'Re-read Individual Strips' instead keeps chartread running for
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
        dlg.setWindowTitle(tr("All Strips Read"))
        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        if in_set:
            body = tr(
                "<b>All strips read — {n} reads of this chart are now saved.</b>"
                "<br><br>"
                "Combining repeated reads of the same chart averages out instrument "
                "noise and can improve profile accuracy.<br><br>"
                "&nbsp;&nbsp;•&nbsp; <b>Average all reads &amp; build</b> — combine all "
                "{n} reads into one measurement, then continue to Build Profile.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>{measure_again}</b> — read the whole "
                "chart once more and add it to the set.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Use last read only</b> — build from this most "
                "recent read and ignore the others.<br><br>"
                "<span style='color:#909090;'>After <b>{measure_again}</b> the "
                "instrument is set up again — this can take a few seconds and may ask you "
                "to recalibrate before the next read starts, so a brief pause here is "
                "normal.</span>"
            ).format(n=n_total,
                     measure_again=tr("Measure again to average"))
        else:
            body = tr(
                "<b>All strips have been read successfully.</b><br><br>"
                "&nbsp;&nbsp;•&nbsp; <b>Build Profile</b> — finalise the measurement and "
                "go to the Build Profile tab.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>{measure_again}</b> — read the whole chart "
                "once more; the reads are averaged together to reduce instrument noise "
                "(saved as …_average).<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Re-read Individual Strips</b> — re-read individual strips into "
                "this same measurement. Use <b>f</b>&nbsp;/&nbsp;<b>b</b> to move, "
                "<b>n</b> for the next unread strip, and <b>d</b> when done.<br><br>"
                "<span style='color:#909090;'>After <b>{measure_again}</b> the "
                "instrument is set up again — this can take a few seconds and may ask you "
                "to recalibrate before the next read starts, so a brief pause here is "
                "normal.</span>"
            ).format(measure_again=tr("Measure again to average"))
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
            reread_btn = QPushButton(tr("Re-read Individual Strips"), dlg)
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
            build_btn = QPushButton(tr("Go to {tab} Tab →").format(
                tab=self._profile_tab_name_btn()), dlg)
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
            # the classic "Re-read Individual Strips" path; the event filter must go back on.
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

        self._ask_how_printed(dst)
        self._show_verification_saved(dst)

    def _ask_how_printed(self, ti3: Path) -> None:
        """One question, only when ChromIQ cannot know: a verification sheet
        with NO print record was printed outside ChromIQ. The **text** comes
        from ``workflow/measurement_messages.py`` (§M); the answer is stored
        beside the dated measurement so the report can pick the fair
        yardstick (pairing 3 — Knut/Sebastian, 2026-08-10). "Not sure" stores
        nothing and is always safe."""
        from PyQt6.QtWidgets import QMessageBox
        from workflow import measurement_messages as M
        from workflow.verification_print import (COLOUR_RAW, COLOUR_THROUGH,
                                                 read_print_record,
                                                 record_answers_how_printed,
                                                 write_print_record)
        try:
            # NOT "a record exists" — "a record that answers this".
            #
            # `is not None` here was the second half of R6 F5: a print ChromIQ
            # refused to make still left a `<stem>.print.json`, and that file
            # silenced this question about a sheet ChromIQ had not printed. The
            # write is now timed to a real print (`tab_print`), and this side
            # checks what it found rather than only that it found something —
            # so a malformed or half-written record asks instead of assuming.
            if record_answers_how_printed(read_print_record(ti3)):
                return                    # it says how it was made, and that it was
        except Exception:      # noqa: BLE001 — a question must never crash
            return
        title, body = M.M_HOW_PRINTED.render()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        raw_btn = box.addButton(tr("Raw — no profile"),
                                QMessageBox.ButtonRole.ActionRole)
        cm_btn = box.addButton(tr("With colour management"),
                               QMessageBox.ButtonRole.ActionRole)
        unsure_btn = box.addButton(tr("Not sure"),
                                   QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(unsure_btn)
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        fit_message_box_buttons(box)
        box.exec()
        clicked = box.clickedButton()
        if clicked is raw_btn:
            colour, route = COLOUR_RAW, "external"
        elif clicked is cm_btn:
            colour, route = COLOUR_THROUGH, "external-cm"
        else:
            return                        # honest ignorance stays recorded as such
        try:
            rec = write_print_record(ti3, colour=colour,
                                     intent="unknown", profile=None,
                                     route=route)
            # The record's timestamp is when the ANSWER was given, not when
            # the sheet was printed — mark it so the report never claims a
            # print time it does not know.
            if rec is not None:
                import json as _json
                data = _json.loads(read_text(Path(rec)))
                data["recorded"] = "asked-at-measure"
                data.pop("printed_at", None)
                Path(rec).write_text(_json.dumps(data, indent=2), encoding="utf-8")
        except Exception:      # noqa: BLE001 — never lose a measurement over it
            log.warning("Could not store the how-printed answer", exc_info=True)

    def _show_verification_saved(self, dst: Path) -> None:
        """The verification-saved window, with BOTH doors — report and
        inspector — each explained. The **text** comes from
        ``workflow/measurement_messages.py`` (§M); this method only renders
        it. Proposed by Basti mid-hardware-session, 2026-08-10: the report is
        the analysis a verification exists for, and this window only offered
        the inspector."""
        from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                                     QVBoxLayout)
        from workflow import measurement_messages as M
        title, body = M.M_VERIFY_SAVED.render(name=dst.name)
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(600)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)
        msg = QLabel(body, dlg)
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(msg)
        row = QHBoxLayout()
        row.addStretch(1)
        close_btn = QPushButton(tr("Close"), dlg)
        close_btn.clicked.connect(dlg.reject)
        choice = {"open": ""}

        def _pick(what: str) -> None:
            choice["open"] = what
            dlg.accept()

        insp_btn = QPushButton(tr("Open in measurement inspector"), dlg)
        insp_btn.clicked.connect(lambda: _pick("inspector"))
        report_btn = QPushButton(tr("Open measurement report"), dlg)
        report_btn.setObjectName("primary")
        report_btn.setDefault(True)
        report_btn.clicked.connect(lambda: _pick("report"))
        row.addWidget(close_btn)
        row.addWidget(insp_btn)
        row.addWidget(report_btn)
        lay.addLayout(row)
        tint_dialog_primary(dlg, _TAB_COLOR)
        dlg.exec()
        if choice["open"] == "report":
            from ui.dialogs.measurement_report_dialog import \
                MeasurementReportDialog
            MeasurementReportDialog(self._settings, self,
                                    initial_ti3=dst).exec()
        elif choice["open"] == "inspector":
            from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
            insp = Ti3InfoDialog(self._runner, self._settings, self)
            insp.load_measurement(dst)
            insp.exec()

    # ------------------------------------------------------------------
    # IMPORT module (#133) — file a measurement made in i1Profiler
    # ------------------------------------------------------------------

    def _make_import_panel(self) -> QWidget:
        """The IMPORT module's panel: a file row (green folder button) and an
        info box saying, in the tab's own accent, exactly what the import will
        do and where the measurement will be filed. No chartread options — an
        imported file carries its own facts (instrument, date, patch values),
        and the destination comes from the bar above."""
        scroll = FadeScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 8, 16, 8)
        ll.setSpacing(10)

        self._import_path: "Path | None" = None

        grp = QGroupBox(tr("Measurement File (from i1Profiler)"), left)
        grp.setFlat(True)
        g = QVBoxLayout(grp)
        g.setContentsMargins(8, 6, 8, 8)
        row = QHBoxLayout()
        self._import_file_lbl = ElidingLabel(tr("No file chosen yet"), grp)
        self._import_file_lbl.setStyleSheet("color: #909090; font-size: 11px;")
        row.addWidget(self._import_file_lbl, stretch=1)
        self._import_browse_btn = make_browse_button(grp, tooltip=tr(
            "Choose the measurement file to import — i1Profiler's own "
            "measurement (.mxf or .cxf), its CGATS text export (.txt), or a "
            "measurement already in Argyll's .ti3 format."),
            color=_TAB_COLOR)
        self._import_browse_btn.clicked.connect(self._on_import_browse)
        row.addWidget(self._import_browse_btn)
        row.addWidget(TooltipButton(
            tr("Import a measurement made in i1Profiler"),
            tr("Use this when this run's verification chart was printed and "
               "measured outside ChromIQ — typically on an i1iO table in "
               "i1Profiler, using the chart's exported patch list from the "
               "run's exports folder.\n\n"
               "What to pick: i1Profiler's own measurement file (.mxf or "
               ".cxf), its CGATS text export (.txt), or a measurement that is "
               "already a .ti3. Measure with the chart's NORMAL export — not "
               "the file with “shuffled” in its name — so the patches come "
               "back in the order ChromIQ sent them.\n\n"
               "What happens when you press Import Measurement:\n"
               "1. ChromIQ converts the file to Argyll's .ti3 format for you "
               "(nothing to do by hand).\n"
               "2. It checks, patch for patch, that the measurement really "
               "belongs to this run's verification chart. A file that does "
               "not match is refused before anything is written.\n"
               "3. It files a copy in its own dated verification folder — the "
               "same place a measurement made here would go — together with a "
               "copy of the chart it was measured against.\n\n"
               "Your original file is never moved or changed. Afterwards, "
               "open Tools ▸ “Measurement report” to see the colour-accuracy "
               "figures — the imported measurement is already in place there."),
            grp, min_width=480))
        g.addLayout(row)
        ll.addWidget(grp)

        # The green info box (Basti): same shape as the Create Chart tab's
        # info boxes, in this tab's accent — says what THIS import will do.
        box = QFrame(left)
        box.setObjectName("importInfoBox")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(12, 10, 12, 12)
        bl.setSpacing(6)
        title_lbl = QLabel(tr("What this import will do"), box)
        title_lbl.setObjectName("importInfoTitle")
        bl.addWidget(title_lbl)
        self._import_box_body = QLabel("", box)
        self._import_box_body.setObjectName("importInfoBody")
        self._import_box_body.setWordWrap(True)
        self._import_box_body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        bl.addWidget(self._import_box_body)
        self._import_box = box
        self._apply_import_box_style()
        ll.addWidget(box)

        ll.addStretch(1)
        scroll.setWidget(left)
        return scroll

    def _apply_import_box_style(self) -> None:
        """Paint the import info box in the Measure tab's green — readable in
        both themes (the shared QLabel#info chrome is magenta, so this box
        carries its own).

        THIS MODULE EXISTS ONLY IN A VERIFICATION RUN (see
        :meth:`_import_available`, #133 §9.1), so no pixel census has ever
        rendered it: every one of them opened the app in its default
        configuration, where the run type is Profiling and this box is not on
        screen at all. The fold below had room for two answers and gave the
        light-grey appearance the DARK one — a near-black green box
        (``#0b1f18``) with mint-green text, measured at 150,784 hued pixels. It
        is a plain explanation of what the import will do, not a warning, so it
        takes no escalation mark in Neutral."""
        if getattr(self, "_mode", "dark") == "light":
            bg, border = "#e9f9f2", _TAB_COLOR
            title_color, body_color = "#157a52", "#23553f"
        else:
            bg, border = "#0b1f18", _TAB_COLOR
            title_color, body_color = _TAB_COLOR, "#cfe9dd"
        self._import_box.setStyleSheet(info_box_qss(
            "import", bg=bg, border=border, title=title_color,
            body=body_color, mode=getattr(self, "_mode", "dark"), kind="note"))

    def _import_available(self) -> bool:
        """The IMPORT module exists only while the shared Run type is
        Verification — a profiling measurement must come from a real read
        here, never from an outside file (#133 §9.1)."""
        return self._is_verification_run()

    def _refresh_import_visibility(self) -> None:
        """Follow the bar: show/hide the IMPORT mode button, leave the module
        when it no longer applies, and keep the destination line current."""
        if not hasattr(self, "_import_btn"):
            return
        avail = self._import_available()
        self._import_btn.setVisible(avail)
        if not avail and self._stack.currentIndex() == 2:
            self._switch_mode("guided")
        elif self._stack.currentIndex() == 2:
            self._update_import_panel()

    def _refresh_import_controls(self) -> None:
        """Swap the action row for the active module: IMPORT shows one Import
        Measurement button where Start stands; the chartread-only controls
        (Stop, Save as Defaults, the sounds switch) step aside with it."""
        if not hasattr(self, "_import_go_btn"):
            return
        importing = self._stack.currentIndex() == 2
        for w in (self._start_btn, self._stop_btn, self._save_defaults_btn):
            w.setVisible(not importing)
        self._import_go_btn.setVisible(importing)
        if importing:
            self._sound_cb.setVisible(False)
            self._sound_tip.setVisible(False)
            self._update_import_panel()
        else:
            # The sounds switch has its own visibility rule (hidden on the
            # stock chartread engine) — re-apply it rather than assuming.
            try:
                self.refresh_engine_visibility()
            except Exception:      # noqa: BLE001 — a refresh must not break the swap
                pass

    @staticmethod
    def _pretty_verification_when(vid: str) -> str:
        """A dated-folder id (``2026-08-09_142530``) as the human line the
        messages show (``2026-08-09 14:25``)."""
        import re
        m = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})\d{2}", vid)
        return f"{m.group(1)} {m.group(2)}:{m.group(3)}" if m else vid

    @staticmethod
    def _chart_patch_count(ti2: "Path | None") -> "int | None":
        """The chart's patch count, from its own header — cheap enough to read
        on every panel refresh."""
        import re
        if ti2 is None:
            return None
        try:
            m = re.search(r"NUMBER_OF_SETS\s+(\d+)", read_text(ti2, lenient=True))
        except OSError:
            return None
        return int(m.group(1)) if m else None

    def _update_import_panel(self) -> None:
        """Fill the info box for the current file + target, and set the Import
        button's availability accordingly."""
        if not hasattr(self, "_import_box_body"):
            return
        parts: "list[str]" = []
        path = getattr(self, "_import_path", None)
        if path is None:
            self._import_file_lbl.setText(tr("No file chosen yet"))
            parts.append(tr(
                "Press the green folder button above and choose the "
                "measurement you made in i1Profiler — its own measurement "
                "file (.mxf or .cxf), its CGATS text export (.txt), or a "
                "ready .ti3."))
        else:
            self._import_file_lbl.setText(str(path))
            ext = Path(path).suffix.lower()
            if ext in (".mxf", ".cxf"):
                parts.append(tr(
                    "{name} is an i1Profiler measurement (CxF3) — ChromIQ "
                    "reads it directly, no export step needed.").format(
                        name=Path(path).name))
            elif ext == ".ti3":
                parts.append(tr(
                    "{name} is already in Argyll's measurement format — it "
                    "will be used as it is.").format(name=Path(path).name))
            else:
                parts.append(tr(
                    "{name} is a CGATS text export — ChromIQ converts it "
                    "with ArgyllCMS's txt2ti3 for you.").format(
                        name=Path(path).name))
        run = self._guard_run()
        chart = run.verify_chart_ti2 if run is not None else None
        if chart is not None and chart.exists():
            n = self._chart_patch_count(chart)
            if n:
                parts.append(tr(
                    "Before anything is filed, the measurement is checked "
                    "patch for patch against this run's verification chart "
                    "({name}, {n} patches). A file that does not match is "
                    "refused, and nothing changes.").format(name=chart.name,
                                                            n=n))
            else:
                parts.append(tr(
                    "Before anything is filed, the measurement is checked "
                    "patch for patch against this run's verification chart "
                    "({name}). A file that does not match is refused, and "
                    "nothing changes.").format(name=chart.name))
        parts.append(self._import_destination_text(run))
        parts.append(tr(
            "Your original file is not moved or changed — ChromIQ files a "
            "copy."))
        self._import_box_body.setText("\n\n".join(parts))

        ok = path is not None and self._import_available()
        self._import_go_btn.setEnabled(ok)
        self._import_go_btn.setToolTip("" if ok else tr(
            "Choose a measurement file first — press the green folder button "
            "above."))

    def _import_destination_text(self, run) -> str:
        """Where the measurement will be filed, named exactly — so 'where are
        my files?' is answered before the import runs."""
        ctl = getattr(self, "_target_ctl", None)
        if run is None:
            return tr(
                "Pick a profile run in the bar above first — the measurement "
                "is filed into that run's verifications folder.")
        vid = ctl.target.verification_id if ctl is not None else ""
        if vid:
            v = run.verification(vid)
            text = tr(
                "It will be filed with the verification from {when}, in:\n"
                "{folder}").format(
                    when=self._pretty_verification_when(vid),
                    folder=str(v.dir))
            if v.measurement_ti3.exists():
                text += "\n\n" + tr(
                    "⚠ That verification already holds a measurement, and an "
                    "import never replaces one. To file this as a new check, "
                    "set the “Verification” field in the bar above to “New "
                    "verification” first.")
            return text
        return tr(
            "A new dated folder is created for it (named after today's date "
            "and time), under:\n{folder}").format(
                folder=str(run.verifications_dir))

    def _on_import_browse(self) -> None:
        # The house file dialog — sidebar shortcuts incl. the working folder
        # — not the bare native one (Sebastian, 2026-08-10).
        start_dir = str(self._settings.get("import_measurement_dir", "") or
                        str(Path.home()))
        path = open_file_dialog(
            self, tr("Choose the measurement to import"),
            tr("Measurement files (*.mxf *.cxf *.txt *.ti3);;All files (*)"),
            start_dir=start_dir,
            extra_path=self._settings.get("custom_output_path", ""),
            declutter_settings=self._settings)
        if not path:
            return
        self._import_path = Path(path)
        self._settings.set("import_measurement_dir", str(Path(path).parent))
        self._update_import_panel()

    def _import_mismatch_reason(self, ti3: Path, ti2: Path) -> "str | None":
        """The plain-words reason this file must be refused, or None when it
        really belongs to the chart. Patch counts first (the cheap, clear
        check), then the patch-identity comparison the report itself uses."""
        from workflow.ti3_analysis import Ti3ParseError, parse_ti3
        try:
            measured = parse_ti3(ti3)
        except (Ti3ParseError, OSError) as exc:
            return tr("the file could not be read as a measurement "
                      "({error})").format(error=exc)
        n_chart = self._chart_patch_count(ti2)
        if n_chart is not None and measured.n_patches != n_chart:
            return tr("the verification chart has {chart} patches, but this "
                      "file holds {got} measurements").format(
                          chart=n_chart, got=measured.n_patches)
        from workflow.measurement_report import verify_patch_identity
        identity = verify_patch_identity(measured, ti2)
        if identity.get("verdict") == "mismatch":
            return identity.get("reason") or tr(
                "the measured colours do not agree with the chart's patches")
        if not identity.get("checked"):
            # An uncheckable identity is not a refusal — the report records the
            # same state. Say so in the log rather than blocking the user.
            self._log.appendPlainText("\n" + tr(
                "[INFO] The patch-identity check could not run ({reason}) — "
                "the import continues.").format(
                    reason=identity.get("reason", "")))
        return None

    def _show_import_refusal(self, message, **kw) -> None:
        """One of the IMPORT module's refusal/guard windows. The **text** comes
        from ``workflow/measurement_messages.py`` (§M) — this method only
        renders the given catalogue message; it writes no prose of its own."""
        from PyQt6.QtWidgets import QMessageBox
        title, body = message.render(**kw)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        fit_message_box_buttons(box)
        box.exec()

    def _on_import_measurement(self) -> None:
        """The whole import, through the same doors a native verification read
        uses: guards → convert → validate → dated folder + chart snapshot →
        file the copy → say where it went. Nothing is written until the file
        has passed validation, and the user's original is never touched."""
        from workflow import measurement_messages as M
        if self._runner.is_running:
            return
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return
        if self._blocked_by_new_run():
            return
        block = self._verification_guard()
        if block is not None:
            self._show_import_refusal(block)
            return
        run = self._guard_run()
        if run is None:
            return
        path = getattr(self, "_import_path", None)
        if path is None or not Path(path).exists():
            self._say_on_screen(
                tr("Choose a measurement file first"),
                tr("Press the green folder button and choose the measurement "
                   "you made in i1Profiler — then press Import Measurement "
                   "again."))
            return
        # A chosen dated verification that already holds its measurement is
        # refused BEFORE anything is converted or written (§ the import never
        # replaces a result).
        vid = ctl.target.verification_id
        if vid and run.verification(vid).measurement_ti3.exists():
            self._show_import_refusal(
                M.M_IMPORT_DATE_TAKEN,
                when=self._pretty_verification_when(vid))
            return

        # 1) Convert — into the run's cache (always safe to delete); a .ti3
        #    passes through untouched.
        try:
            from workflow.reference_convert import (
                ReferenceConvertError, convert_i1profiler_measurement)
            argyll = self._settings.get("argyll_bin_path",
                                        "/Applications/Argyll/bin")
            converted = convert_i1profiler_measurement(
                Path(path), argyll, run.ensure_cache_dir() / "import")
        except ReferenceConvertError as exc:
            self._say_on_screen(
                tr("The file could not be converted"), str(exc))
            return
        if converted != Path(path):
            self._log.appendPlainText("\n" + tr(
                "[OK] Converted {name} to Argyll's .ti3 format.").format(
                    name=Path(path).name))

        # 2) Validate — before anything is filed.
        reason = self._import_mismatch_reason(converted, run.verify_chart_ti2)
        if reason:
            self._show_import_refusal(M.M_IMPORT_MISMATCH, reason=reason)
            return

        # 3) File it. The snapshot step is the same front door a native
        #    verification read uses: it creates the dated folder on "New
        #    verification" (and moves the bar to it), and asks before replacing
        #    a stored chart that differs.
        if not self._snapshot_verification_chart():
            return
        vid = ctl.target.verification_id
        verification = (run.verification(vid) if vid
                        else run.new_verification())
        verification.ensure_dir()
        dst = verification.measurement_ti3
        if dst.exists():
            self._show_import_refusal(
                M.M_IMPORT_DATE_TAKEN,
                when=self._pretty_verification_when(verification.id))
            return
        import shutil
        try:
            shutil.copy2(converted, dst)
            mark_verification_ti3(dst)     # stamps CHROMIQ_VERIFICATION "true"
        except OSError as exc:
            self._log.appendPlainText(
                f"\n[ERROR] Could not save the imported measurement: {exc}")
            return
        self._log.appendPlainText(
            "\n" + tr("[OK] Measurement imported.") + f"\nSaved: {dst}\n\n"
            + tr("→ This file is for verification only — do not build a "
                 "profile from it. Open Tools ▸ Measurement report to see "
                 "the colour-accuracy figures."))
        self._update_import_panel()
        # An imported sheet was by definition printed outside ChromIQ — ask
        # how, unless a record already travelled with the chart snapshot.
        self._ask_how_printed(dst)
        self._show_import_done(verification, dst)

    def _show_import_done(self, verification, dst: Path) -> None:
        """The success window — the §M text, plus a button straight into the
        measurement report (the analysis this import exists for)."""
        from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                                     QVBoxLayout)
        from workflow import measurement_messages as M
        title, body = M.M_IMPORT_DONE.render(
            when=self._pretty_verification_when(verification.id),
            folder=str(verification.dir))
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)
        msg = QLabel(title + "\n\n" + body, dlg)
        msg.setWordWrap(True)
        lay.addWidget(msg)
        row = QHBoxLayout()
        row.addStretch(1)
        close_btn = QPushButton(tr("Close"), dlg)
        close_btn.clicked.connect(dlg.reject)
        report_btn = QPushButton(tr("Open measurement report"), dlg)
        report_btn.setObjectName("primary")
        report_btn.setDefault(True)
        report_btn.clicked.connect(dlg.accept)
        row.addWidget(close_btn)
        row.addWidget(report_btn)
        lay.addLayout(row)
        tint_dialog_primary(dlg, _TAB_COLOR)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            from ui.dialogs.measurement_report_dialog import \
                MeasurementReportDialog
            MeasurementReportDialog(self._settings, self,
                                    initial_ti3=dst).exec()

    def _restore_displaced_measurement(self, empty_ti3) -> bool:
        """Undo a replacement that measured nothing: drop the empty file, put the
        previous measurement back where it was, and remove the folder it sat in.

        Returns True when it did so — the caller then has nothing left to say
        about an empty file, because there is no longer one.
        """
        displaced = getattr(self, "_displaced_measurement", None)
        if displaced is None:
            return False
        self._displaced_measurement = None
        saved = displaced / empty_ti3.name
        if not saved.is_file():
            return False                  # nothing to put back; archive as usual
        import shutil
        try:
            # The file may not exist at all: a session that was cancelled in a
            # window (or whose instrument never opened) leaves nothing behind,
            # and there is then nothing to remove before putting the previous
            # measurement back.
            if empty_ti3.is_file():
                empty_ti3.unlink()
            shutil.move(str(saved), str(empty_ti3))
            # Only if we emptied it — never remove a folder holding other files.
            if not any(displaced.iterdir()):
                displaced.rmdir()
        except OSError as exc:
            log.warning("could not restore the measurement from %s: %s",
                        displaced, exc)
            return False
        log.info("nothing was measured — restored %s from %s",
                 empty_ti3.name, displaced.name)
        self._log.appendPlainText(tr(
            "Nothing was measured, so your previous measurement has been put "
            "back exactly where it was."))
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("Nothing was measured"))
        box.setText(tr(
            "That session ended before any patch was read successfully, so "
            "there are no readings to keep.\n\n"
            "Because nothing was measured, your previous measurement has been "
            "put back exactly where it was — this read has changed nothing at "
            "all. Your chart is untouched too.\n\n"
            "When you are ready, start the measurement again."))
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        fit_message_box_buttons(box)
        box.exec()
        return True

    def _archive_empty_measurement(self) -> None:
        """Move a measurement file that holds no readings into ``old/``, and say so.

        Nothing was measured, so nothing should be left claiming otherwise. The
        file is moved rather than deleted — Knut asked for exactly that (#130,
        2026-07-30) — so an empty file is never destroyed, only put where it
        stops being mistaken for a measurement. A partial measurement, however
        short, is real ink on real paper and is always left alone.
        """
        if self._ti1_path is None:
            return
        ti3 = self._ti1_path.with_suffix(".ti3")
        # A SESSION THAT WROTE NOTHING NEVER REPLACED ANYTHING.
        #
        # Knut, beta.128: cancelling the instrument-mismatch window (and the
        # same for an instrument that never opens) ends the session before
        # chartread writes a thing — so there is no empty file to judge, and the
        # measurement moved aside at Start stayed in `old/` for ever. *"when
        # action/session was cancelled in a window, the ti3 file is not
        # returned."* Archiving at Start is right — chartread truncates its
        # output file the moment it opens it — but the archive is only a
        # replacement once something takes its place.
        if not ti3.is_file():
            self._restore_displaced_measurement(ti3)
            return
        if not _cgats_has_no_readings(ti3):
            return
        # Nothing was measured, so a measurement this read displaced should not
        # stay displaced. Knut, #130 2026-07-31: *"the empty ti3 should be
        # removed and the ti3 that was temporarily stored in old should be
        # returned to where it was placed … and the old/<date_time>/ folder
        # removed afterwords."* The whole read becomes a no-op, which is what
        # "no readings" honestly means.
        #
        # Symmetric for a run and a verification by construction: the folder
        # being undone is the one the archive step recorded, wherever that was.
        if self._restore_displaced_measurement(ti3):
            return
        from core.file_manager import Run
        try:
            dest = Run.for_dir(ti3.parent).archive_to_old([ti3])
        except OSError as exc:
            log.warning("could not archive the empty measurement %s: %s", ti3, exc)
            return
        if dest is None:                      # nothing was there after all
            return
        log.info("archived empty measurement %s -> old/%s/", ti3.name, dest.name)
        self._log.appendPlainText(tr(
            "No measurements were recorded in that session. The empty file has "
            "been moved to the run's old folder, so this chart is not treated "
            "as measured."))
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("Nothing was measured"))
        # What is true here depends on whether this read replaced an earlier
        # measurement. Knut, #130 2026-07-31, on both halves of that: on a first
        # attempt *"there are no earlier measurement file in place, so the
        # information is a bit misleading"*, and after replacing one *"THINGS
        # HAVE changed … the information in the widow after exiting measurement
        # session is wrong"*. He was right twice; one sentence cannot cover both.
        displaced = getattr(self, "_displaced_measurement", None)
        self._displaced_measurement = None
        if displaced is not None:
            tail = tr(
                "The measurement you had before this read was moved into the "
                "same \u201cold\u201d folder when this read started, exactly as the "
                "warning said it would be. It is still there, and you can put "
                "it back by moving it up one level.\n\n"
                "Your chart itself is untouched.")
        else:
            tail = tr(
                "Nothing has been deleted and nothing else has changed — your "
                "chart is exactly as it was.")
        box.setText(tr(
            "That session ended before any patch was read successfully, so "
            "there are no readings to keep.\n\n"
            "The empty measurement file it left behind has been moved into this "
            "run's \u201cold\u201d folder. ") + tail + tr(
            "\n\nChromIQ will no longer treat this chart as measured, so you "
            "will not be warned about a measurement that was never taken.\n\n"
            "When you are ready, start the measurement again."))
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        fit_message_box_buttons(box)
        box.exec()

    def _refresh_progress_from_files(self) -> None:
        """Re-read the run's measurement once a session has ended.

        Called from `_on_measure_done` **after** §S3 has judged the session and
        settled the file — an empty one is aside and the previous measurement is
        back — because until then the .ti3 on disk is not the run's answer.

        ArgyllCMS writes the .ti3 only on a clean exit, so this is the first
        moment the file is authoritative again. It corrects the live count,
        including the one case the set cannot see for itself: re-reading a patch
        that was already in the file this session resumed from.

        Not gated on the progress-bar preference. `_count_strip_progress` says
        why: the ids are collected *"whether or not the progress bar is switched
        on"*, because #156 needs the record of WHICH patches have a reading to
        know when a chart is actually finished — and `_unread_patch_count` reads
        the same two numbers. Returning early here left that record frozen at
        whatever the last chart load found for every user who had turned the bar
        off, which is the opposite of what the collector promises.
        """
        self._reset_progress()

    def _on_measure_done(self, code: int) -> None:
        # EVERYTHING THAT BELONGS TO THE MEASUREMENT GOES WITH IT (Knut,
        # beta.139). First, before any of the tidying below, so a window that
        # is still spinning its own event loop cannot answer into a process
        # that has already gone.
        self._close_cr30_bridge()
        self._close_measurement_windows()
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

        # A session that recorded nothing leaves an empty measurement file
        # behind, and that file then makes ChromIQ claim this run HAS a
        # measurement: the Measure tab warns about one, Generate Chart warns
        # that a measurement would be displaced, and a resume tries to continue
        # from it and fails. Knut asked for exactly this remedy, and for a MOVE
        # rather than a delete (#130, 2026-07-30): *"move the empty ti3 files
        # that do not have measurements to old/ folder right after measurement
        # session was exited/stopped/completed … and then give user an
        # information message window explaining that no measurements were
        # performed or stored for that session, so file was moved to old/
        # folder … This would have to be done before determining if 'Refine /
        # resume' or 'Show overlay...' should be made visible after a
        # measurement, and should never be done during measurement, and only if
        # the created file has no measurements."*
        #
        # Done here, before anything else looks at the file, so every ending —
        # strip, patch-by-patch, resume, single patches — is covered by one
        # place rather than four.
        #
        # §S3: the session's own verdict comes FIRST. The guard both sets an
        # empty file aside and puts the previous measurement back, and both have
        # to happen before anything reads the file — the overlay, the resume
        # checkbox and the report all describe whatever is on disk when they
        # look. A test pins this order; it caught the mistake of judging at the
        # END of this method, by which point the resume checkbox had already
        # refreshed itself from the file that was about to be replaced.
        self._session_live = False
        self._finish_session_guard()
        # Superseded by the guard for any run it protects; still the only
        # handler for a session that never got one.
        self._archive_empty_measurement()

        # #153: NOW the .ti3 on disk is the run's answer, so it can settle the
        # count. Not one line earlier.
        #
        # This ran at the very top of this method, which is the one moment in
        # the whole session when the file is wrong: chartread had written its
        # own .ti3 (or, for a session that read nothing, written none at all)
        # and §S3 had not yet judged it. So a stopped-with-nothing-read session
        # read a missing file, put the bar at 0%, and never looked again — while
        # the two lines above restored the previous measurement and every other
        # readout in the app went back to saying 18 of 390. The owner saw both
        # numbers at once on 2026-09-03: *"it showed the measured vs expected
        # patches from before but the progress bar was then at 0%"*.
        #
        # §S3 of `unified_measurement_management.md` already fixes this order —
        # S3.2 moves an empty file aside and restores the archived copy, and
        # only S3.7 reports. The progress refresh had simply been added in front
        # of the queue rather than behind it.
        self._refresh_progress_from_files()

        # With "Show overlay from existing measurement" ticked, the overlay is
        # what the user wants to look at — including right after stopping, when
        # the question is usually "what did I actually get?". Stopping used to
        # leave the preview blank until the box was toggled off and on again
        # (Knut, #131 2026-07-27).
        self._restore_overlay_after_measurement()
        # A run that had no measurement before now has one, so the two boxes
        # that act on a measurement can appear — and the overlay box appears
        # TICKED, matching the readings already drawn on the preview (Knut,
        # #131 2026-07-28). Refreshed here so every completion path gets it,
        # not only the interrupted one.
        self._update_resume_availability()
        self._adopt_overlay_after_first_measurement()

        if self._usb_claimed_by_vm:
            self._cue_window("INSTRUMENT_ERROR")   # as the window opens
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
            self._show_no_instrument_window()
            return

        if self._device_busy:
            self._cue_window("INSTRUMENT_ERROR")   # as the window opens
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
            # The window sounds again as it opens — his ruling: the sound comes
            # immediately AND with the window (#130, 2026-07-29).
            self._show_instrument_disconnected_window()
            return

        # Group B: friendly terminal dialogs for chartread startup failures.
        # The communications/init failures share a dialog body — the only
        # difference is which Argyll error string is shown.
        _b_init_msg = self._coms_init_failed_msg or self._inst_init_failed_msg
        if _b_init_msg:
            self._cue_window("INSTRUMENT_ERROR")   # as the window opens
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
                tr("<b>The instrument could not be initialised.</b><br><br>Argyll reported: <i>{_b_init_msg}</i><br><br><b>Try again first.</b> This often happens for a few seconds straight after a measurement ends, while the instrument is still letting go of the previous session — waiting a moment and pressing <b>Start Measurement</b> again is usually all it takes.<br><br>If it keeps happening:<br>&nbsp;&nbsp;• Unplug and replug the USB cable<br>&nbsp;&nbsp;• Make sure the instrument is switched on<br>&nbsp;&nbsp;• Close any other application that might be using it").format(_b_init_msg=_b_init_msg),
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
            self._cue_window("INSTRUMENT_ERROR")   # as the window opens
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
            self._cue_window("INSTRUMENT_ERROR")   # as the window opens
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
            self._cue_window("INSTRUMENT_ERROR")   # as the window opens
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
        # AN ENDING THE USER CHOSE IS NOT A FAILURE.
        #
        # Stop kills the reader, so `code` is non-zero on every deliberate
        # ending; the only thing that used to keep "[ERROR] Measurement failed"
        # off the screen was a `.ti3` being there afterwards. For a session
        # stopped before the first patch there is none — and the previous
        # measurement, restored a moment ago, was standing in for one. With that
        # mistake gone the honest path is to ask whether the user ended it,
        # which `MeasureManager` has recorded all along: *"the non-zero exit
        # that follows must not be described as one"* (`abort`).
        #
        # A genuine fault still sets `_measure_failed`, which this does not
        # touch, and §1 row 5 of the specification has already been honoured —
        # "nothing was measured, so nothing was saved", on screen.
        failed = self._measure_failed or (
            code != 0 and not ti3_exists
            and not self._manager.ended_by_the_user)
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
            # The overlay box has just appeared for the first time — tick it, so
            # the control agrees with the readings already on the preview
            # (Knut, #131 2026-07-28).
            self._adopt_overlay_after_first_measurement()
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
            # "All Strips Read" dialog already captured the user's choice in
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
        """When the chart is flagged for it (the 'All Strips Read' checkbox),
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
        the 'All Strips Read' dialog never fired). Promote the read, then ask via
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
                # {tab}, not a hard-coded "Build Profile": tab 4 is renamed to
                # "Calibration & Profiling" whenever Preferences → Calibration
                # options is on (main_window._apply_calibration_mode), so the
                # literal named a tab the user could not see. The two sibling
                # texts above were converted for beta.148 — Knut's own fix —
                # and this third one was missed. Found by the Russian
                # translator, who looked up every control name it quotes.
                "&nbsp;&nbsp;•&nbsp; <b>Go to {tab} Tab</b> — use this single "
                "measurement as it is, and open the {tab} tab. The profile "
                "is built there, when you press <i>Build Profile</i>.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>{measure_again}</b> — read the same "
                "chart once more; the results will be averaged together.<br>"
                "&nbsp;&nbsp;•&nbsp; <b>Close</b> — keep this measurement and go "
                "nowhere; you can build the profile whenever you like."
            ).format(tab=self._profile_tab_name(),
                     measure_again=tr("Measure again to average"))
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
            cont_btn = QPushButton(tr("Go to {tab} Tab →").format(
                tab=self._profile_tab_name_btn()), dlg)
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
        # Found by the audit of 2026-07-28 (Knut): a failure window raised
        # during a measurement that had no sound at all. It is not an
        # instrument fault, so it takes the general reading-failure sound.
        self._cue_window("STRIP_FAIL")
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
        # The pace area shows exactly when one of its two children does —
        # reacting to their own show/hide events means no caller has to
        # remember a sync call (and Knut's layout tests drive them directly).
        if obj in (getattr(self, "_pace_group", None),
                   getattr(self, "_pace_verdict_lbl", None)) \
                and event.type() in (QEvent.Type.Show, QEvent.Type.Hide,
                                     QEvent.Type.ShowToParent,
                                     QEvent.Type.HideToParent):
            self._sync_pace_area_visible()
            return False
        # THE VERDICT MUST STILL FIT AFTER THE WINDOW IS NARROWED.
        #
        # Its minimum height is computed from heightForWidth at the width it had
        # when the text was set. Narrow the window afterwards and the same words
        # need another line, but the floor still describes the old, wider
        # label — so the last line is clipped. #149 makes this reachable: the
        # message now carries the whole-strip limit as well, and Knut asked what
        # happens to it when the preview area is made smaller —
        # *"the message area must be adapted in height to fit the text"*.
        if obj is getattr(self, "_pace_verdict_lbl", None) \
                and event.type() == QEvent.Type.Resize:
            self._refit_pace_verdict_height()
            return False
        if event.type() == QEvent.Type.KeyPress:
            # NO PROCESS, NO BUSINESS SWALLOWING KEYS.
            #
            # This filter exists to route keystrokes to a running chartread, and
            # it is installed on the whole application. Every ending removes it
            # — but the recovery windows re-install it as they close, so a
            # session that ended inside one could leave it behind, and from then
            # on an arrow key anywhere in the app was eaten and logged as
            # "send_key LEFT: no active process". Found by a keyboard-navigation
            # test that lost its arrow keys to a Measure tab from an earlier
            # test in the same process; the same could happen to a user after a
            # session that ended in one of those windows.
            if not getattr(self, "_session_live", False):
                QApplication.instance().removeEventFilter(self)
                return False
            key = event.key()
            # A SHORTCUT IS NOT AN INSTRUMENT KEY.
            #
            # This filter is installed on the whole application while a
            # measurement waits for a keypress, and it used to forward
            # `event.text()` for anything it did not recognise — which for
            # ⌘C is the bare letter "c". So copying text out of the log window
            # sent a 'c' to the reader, and consuming the event meant the copy
            # did not happen either.
            #
            # Knut, #130 2026-08-01, seeing exactly that in his log: *"the
            # stray c was part of the log window. No keys were pressed. only
            # the sequence I told you, so the code generated these extra key
            # strokes."* He was right and my first answer — that these were his
            # own keystrokes — was wrong: they were his *shortcuts*, turned
            # into instrument keys here. His log shows a Tab two minutes later
            # for the same reason.
            #
            # Anything carrying Ctrl / ⌘ / Alt is left for the application, and
            # Tab is left for focus navigation.
            mods = event.modifiers()
            if (mods & (Qt.KeyboardModifier.ControlModifier
                        | Qt.KeyboardModifier.MetaModifier
                        | Qt.KeyboardModifier.AltModifier)):
                return False
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                return False
            # A CR30 SESSION HAS NO ARGYLL PROCESS TO SEND KEYS TO.
            #
            # Everything below forwards to `self._manager.send_key`, which
            # feeds a running chartread. ChromIQ reads the CR30 itself, so
            # those keys reached nobody and Space did nothing at all. Here it
            # takes the reading instead -- which is not merely a convenience:
            # pressing the instrument's own button moves it, measured at
            # ~0.5 %R against its own repeat noise of 0.05 %R when nothing
            # touches it (EXP-TILE-003/004). Taking the reading from the
            # keyboard removes that error.
            # ONLY WHILE A PATCH IS ACTUALLY BEING ASKED FOR.
            #
            # Space and Enter already mean something here: Space throws a
            # reading away and retries, Enter keeps one the reader has
            # questioned. Claiming them for the whole of a CR30 session would
            # swallow both, so a warning could not be answered at all. The
            # bridge knows when it is waiting for a patch, and that is the only
            # moment the keys are free.
            bridge = getattr(self, "_cr30_bridge", None)
            loc = getattr(bridge, "awaiting_loc", None)
            # `awaiting_loc` IS NOT THE SAME AS "SOMEONE IS LISTENING".
            #
            # After the bridge gives up on a patch it is still set, with no
            # reader waiting -- so Space flashed "Taking the reading" into a
            # stalled session and nothing came. `armed_for` is the state that
            # actually means a press will be collected.
            armed = False
            if loc is not None:
                try:
                    armed = bool(bridge.armed_for(loc))
                except Exception:      # noqa: BLE001 — never eat a keystroke
                    log.debug("CR30: could not ask whether %s is armed", loc,
                              exc_info=True)
            if (getattr(self, "_cr30_reader", None) is not None and armed
                    and key in (Qt.Key.Key_Space, Qt.Key.Key_Return,
                                Qt.Key.Key_Enter)):
                self._cr30_reading_from_the_keyboard()
                return True
            sent = True
            if key == Qt.Key.Key_Escape:
                self._manager.send_key("\x1b")
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._manager.send_key("\r")
            elif key == Qt.Key.Key_Space:
                self._manager.send_key(" ")
            elif key == Qt.Key.Key_Left:
                # AN ARROW KEY IS THREE CHARACTERS, AND THE FIRST ONE IS ESCAPE.
                # Left used to go out as the raw terminal sequence "\x1b[D".
                # chartread reads one character at a time and 0x1b is give-up
                # (chartread.c:1611, :1654, :1857) — so a Left arrow at any
                # prompt abandoned the session without saving, and on the engine
                # it matched no command at all and did nothing. The movement
                # keys chartread itself prints are 'b' and 'f', and those work
                # on both engines.
                self._manager.send_key("b")
            elif key == Qt.Key.Key_Right:
                self._manager.send_key("f")
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

    def refresh_engine_visibility(self, *, initial: bool = False) -> None:
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
        # #130 (Knut, beta.120): the overlay toggles and the sounds switch are
        # engine-only too. Hidden AND unticked — a box that is off-screen but
        # still ticked would paint an overlay nobody asked for the next time
        # the engine came back on.
        for ocb, otip in ((getattr(self, "_overlay_cb", None),
                           getattr(self, "_overlay_tip", None)),
                          (getattr(self, "_m_overlay_cb", None),
                           getattr(self, "_m_overlay_tip", None))):
            if ocb is None:
                continue
            if not on:
                ocb.setChecked(False)
                ocb.setVisible(False)
                if otip is not None:
                    otip.setVisible(False)
        for w in (getattr(self, "_sound_cb", None),
                  getattr(self, "_sound_tip", None)):
            if w is not None:
                w.setVisible(on)
        # HIDDEN, BUT NOT SWITCHED OFF — unlike the overlay boxes above.
        #
        # A hidden overlay tick would paint an overlay nobody asked for, so it
        # is cleared. The sound switch is different: it is also the master
        # switch for ChromIQ's WINDOW sounds, which do play on stock chartread —
        # Knut, #130 2026-07-28: *"when starting a measurement without the
        # colormunki connected, the window 'No instrument Found' comes, but
        # without any sound."* Turning it off here silenced those too. The
        # per-patch and per-strip sounds are already held back for stock
        # chartread inside Sound.play(), which is where that rule belongs.
        # The overlay boxes come back only if a measurement is there to draw,
        # which _sync_resume_and_overlay decides. Skipped at construction:
        # there is no chart yet, so it has nothing to decide — and re-entering
        # the availability pass from inside __init__ pulls a good deal of the
        # tab's machinery into a half-built widget for no result.
        if on and not initial:
            try:
                self._update_resume_availability()
            except Exception:      # noqa: BLE001 — visibility, never a crash
                pass

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
        # THE OVERLAY SHOWS EVERYTHING THE .ti3 HOLDS, not only this session.
        #
        # Clearing it here left a resumed session showing only the strips read
        # *since Start* — so the strips measured earlier lost their split
        # patches (and their hover values) the moment a re-read began, and got
        # them back when the session ended and the file was read again. Knut,
        # beta.135: *"That immediately caused the split expected/measured
        # overlay for strip A+B to disappear … After measurement session stopped
        # the overlay updated to also include strip A+B."* He and Sebastian
        # agreed the rule: *"the overlay shall always show everything the .ti3
        # holds, not only what this session read."* So it is cleared and then
        # immediately re-drawn from the file, and this session's strips add to
        # it as they are read.
        self._preview.clear_patch_overlay()
        self._repaint_overlay_from_disk()
        self._patch_geom_warned = False
        self._patch_missing_warned = False
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

    def _on_preview_page_changed(self, page: int) -> None:
        """Re-point the clickable strip rects at the page now on screen.

        ``TiffPreview`` keeps rects for ONE page — the one it was last told
        about — and ``show_page`` only changes which image is drawn. Those rects
        were set in exactly one place: ``_on_stripe_changed``, i.e. when the
        READER moves. So paging by hand left the previous page's rects in place.

        Knut, beta.140, on a chart with A-E on sheet 1 and F on sheet 2: he read
        D, the reader jumped to F on page 2, and he pressed PREV to come back.
        *"Now I am unable to click any of the strips to select them, except
        strip A. When I select strip A, then all the others suddenly allow for
        selecting them."* Page 2 has one strip, so one rect survived — sitting
        over strip A — and clicking it moved the reader, which recomputed the
        rects and made the page whole again.

        Not caused by anything in beta.139/140: it needs the reader and the
        viewer to be on different pages, which is what jumping to a strip on
        another sheet finally made easy to do.
        """
        rects = getattr(self, "_page_stripe_rects", None)
        if not rects:
            return
        idx = max(0, min(int(page), len(rects) - 1))
        self._preview.set_stripe_rects(rects[idx],
                                       getattr(self, "_stripe_arrow_mode", "base"))

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
        # #149, approved by Knut 2026-08-14. Two things changed: the whole-strip
        # limit is stated as well as the per-patch one, because "milliseconds
        # per patch" is hard for a person to relate to; and the "close to the
        # limit" band is now the user's own percentage rather than a fixed 35%,
        # which used to call a 521 ms strip "close" to a 400 ms limit.
        #
        # The trailing clause is deliberately terse — "6.0 sec. or more per
        # strip", not "for this 15-patch strip". His reasoning: the panel sits
        # under the preview where width is scarce, and *"there is no need
        # mentioning how many patches a strip has, as it is visible in the
        # preview"*.
        from core.measure_pace import (measured_phrase, strip_limit_fact,
                                       strip_limit_phrase)
        measured = measured_phrase(pace)
        if pace.too_fast:
            colour, verdict = "#ff6b6b", tr("Too fast — read more slowly")
            limit = tr("Aim for {limit}.").format(
                limit=strip_limit_phrase(config, pace.patches))
        elif pace.marginal:
            colour, verdict = "#e0a63a", tr("Close to the limit")
            limit = tr("Aim for {limit}.").format(
                limit=strip_limit_phrase(config, pace.patches))
        else:
            colour, verdict = "#5cb85c", tr("Good reading speed")
            # Already faster than the limit, so the limit is stated as a fact
            # rather than as an instruction to do what they are doing.
            limit = tr("{limit}.").format(
                limit=strip_limit_fact(config, pace.patches))
        self._refresh_pace_panel(f"{verdict} · {measured}. {limit}", colour)

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
            # The panel resolves each strip index through stripe_x_centres()
            # at PAINT time and translates into its own space then, when both
            # widgets' geometry is real. Positions captured here went stale
            # the moment the panel's own appearance re-fitted the preview
            # smaller — the strips compressed, the stored spacing did not,
            # and the times drifted right across the sheet (2026-08-11).
            panel.set_reference_widget(self._preview)
            panel.set_position_provider(self._preview.stripe_x_centres)
            for letter, (secs, ok) in self._pace_times.items():
                page, local_idx, _rect = self._locate_strip(letter)
                if page == page_now and 0 <= local_idx < len(centres):
                    text = (tr("{secs} s").format(secs=f"{secs:.1f}") if ok
                            else tr("{secs} s ✕").format(secs=f"{secs:.1f}"))
                    # not-ok times are "important": never thinned away when a
                    # small preview leaves too little room for every label.
                    columns.append((local_idx, text, not ok))
        except Exception:      # noqa: BLE001 — a panel must never break a read
            columns = []
        self._pace_verdict = verdict
        self._pace_verdict_colour = colour
        # The caption is the FRAME'S TITLE now, so it sits above the times and a
        # reading can be drawn in any column without colliding with it (Knut,
        # #131 2026-07-27). Singular and plural both spelled out.
        group = getattr(self, "_pace_group", None)
        if group is not None:
            if self._pace_patches == 1:
                title = tr("Strip reading times (1 patch per strip)")
            else:
                title = tr("Strip reading times ({n} patches per strip)").format(
                    n=self._pace_patches)
            group.setTitle(title if self._pace_patches else
                           tr("Strip reading times"))
            # Which strips have you read in THIS session? Exactly the ones with
            # a time under them — which matters most while refining, where every
            # strip already holds a reading and the overlay looks the same
            # either way (Knut, #131 2026-07-27).
            group.setToolTip(tr(
                "One time for each strip you have read in this session, under "
                "the strip it belongs to.\n\n"
                "A time with an ✕ after it means that strip was swiped faster "
                "than your instrument can measure reliably — read that strip "
                "again, more slowly, and the ✕ disappears with the new time.\n\n"
                "While you are refining an existing measurement this is also "
                "how you see your own progress: every strip on the sheet "
                "already has a reading, so the overlay looks the same whether "
                "you have re-read a strip or not — but only the strips you have "
                "read now have a time here."))
            group.setVisible(bool(columns))
        panel.set_content("", sorted(columns), verdict, colour)

        lbl = getattr(self, "_pace_verdict_lbl", None)
        if lbl is not None:
            lbl.setText(verdict or "")
            # THE VERDICT ONLY EXISTS WHILE A STRIP IS BEING READ, which is why
            # no census had ever drawn it: red for "Too fast", amber for "Close
            # to the limit", green for "Good reading speed", and an instrument
            # in your hand is the only way to get any of the three on screen.
            #
            # THE SEVERITY IS THE INFORMATION HERE, so flattening all three to
            # one ink would delete it rather than de-hue it. The words do say
            # which is which — but a verdict you glance at while swiping has to
            # be readable at a glance, so in Neutral the WEIGHT carries the
            # escalation the colour carried: bold for a strip that must be read
            # again, normal when nothing needs doing. Light and Dark keep all
            # three hues and their normal weight — `set_ink` hands the value
            # back untouched there, and the extra rule is empty for them.
            from ui.theme import APPEARANCE_NEUTRAL, active_mode
            _needs_action = colour in ("#ff6b6b", "#e0a63a")
            _extra = (" font-weight: 700;"
                      if _needs_action and active_mode() == APPEARANCE_NEUTRAL
                      else "")
            set_ink(lbl, colour, _extra,
                    level="main" if _needs_action else "dim")
            lbl.setVisible(bool(verdict))
            self._sync_pace_area_visible()
            if verdict:
                self._refit_pace_verdict_height()

    def _refit_pace_verdict_height(self) -> None:
        """Give the verdict a height floor that matches its CURRENT width.

        A floor under its own height is why the warning cannot be squeezed out
        of the layout — the one failure Knut has reported three times. But the
        floor has to be recomputed whenever the width changes, or a narrower
        window wraps the text onto another line that the old floor has no room
        for. Called on set and on every resize.
        """
        lbl = getattr(self, "_pace_verdict_lbl", None)
        if lbl is None or not lbl.text():
            return
        try:
            if lbl.wordWrap():
                # 200 px is a floor for the *measurement*, not for the label:
                # heightForWidth on a not-yet-laid-out label can be asked about
                # width 0 and answer with a single line.
                want = lbl.heightForWidth(max(lbl.width(), 200))
            else:
                want = lbl.sizeHint().height()
            if want > 0 and want != lbl.minimumHeight():
                lbl.setMinimumHeight(want)
        except Exception:      # noqa: BLE001 — a verdict must never break a read
            log.debug("could not refit the pace verdict height", exc_info=True)

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
        group = getattr(self, "_pace_group", None)
        if group is not None:
            group.setVisible(False)
        lbl = getattr(self, "_pace_verdict_lbl", None)
        if lbl is not None:
            lbl.clear()
            lbl.setVisible(False)
        self._sync_pace_area_visible()

    def _sync_pace_area_visible(self) -> None:
        """The pace area only takes vertical room when it has something to
        show. Empty but visible, its top margin pushed the preview's Prev/Next
        row ~10 px above the level the action buttons sit at (Basti,
        2026-08-09)."""
        area = getattr(self, "_pace_area", None)
        if area is None:
            return
        # isHidden() reads each child's own explicit state, which stays valid
        # while the area itself is hidden — isVisible() would not.
        area.setVisible(not self._pace_group.isHidden()
                        or not self._pace_verdict_lbl.isHidden())

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

    def _connect_instrument_error_cues(self) -> None:
        """Cue the two instrument windows that open **the moment their signal
        arrives**. Connected BEFORE those windows' own slots, so the sound is
        heard as the window appears rather than when it is dismissed (#131,
        Knut 2026-07-27).

        **Only these two.** The completion audit of 2026-07-28 (Knut: *"compare
        … and note any discrepancies between the design specification and
        implementation"*) found that the other nine instrument signals do not
        open a window at all — they set a flag, and the window is raised later,
        in :meth:`_on_measure_done`, once the process has exited. Cueing those
        from the signal played the sound seconds before the window it belongs
        to, which is exactly what his rule forbids. They are now cued where
        they are actually raised.
        """
        import core.sound as _snd
        _m = self._manager
        for _sig in (_m.sensor_wrong_position, _m.generic_instrument_error):
            _sig.connect(lambda *_: self._sound.play(_snd.INSTRUMENT_ERROR))

    def _use_outlier_fence(self) -> bool:
        """Whether a patch must ALSO stand out from its own strip to be flagged.

        Knut's ruling of 2026-07-27, option (c): make it a switch, defaulting to
        today's behaviour. With it on — the default — a patch is flagged only
        when it is both past your ΔE threshold and unusual for its strip, which
        keeps a good print from being flagged almost everywhere (the chart's
        "expected" values are design values, and a printer does not reproduce
        them). With it off, the threshold means exactly what it says.
        """
        try:
            return bool(self._settings.get("patch_warn_outlier_fence", True))
        except Exception:      # noqa: BLE001
            return True

    def _cue_window(self, event: str) -> None:
        """Sound a window at the moment it opens (#131, Knut 2026-07-27).

        His rule: *"ALL warnings and error windows that could occur during
        measurement … shall have their belonging sound played at the same time
        as the window appears."*

        It has to be called from the TOP of the slot that opens the window, not
        connected alongside it: a slot that opens a modal dialog blocks inside
        itself, so anything connected after it is not heard until the window is
        dismissed — which is how a cue ended up playing on a button press twice
        before (beta.35, beta.43).

        **And it must not be gated on a read being in progress.** Several of
        these windows are raised only after the process has exited — the
        instrument ones especially — by which time the measurement is over and
        ``play()`` would drop the sound. That is why "No Instrument Found" was
        silent even after its cue was in the right branch (Knut, #130
        2026-07-28). ``play_window`` is the same sound without that gate.
        """
        import core.sound as _snd
        try:
            self._sound.play_window(getattr(_snd, event))
        except Exception:      # noqa: BLE001 — a cue must never block a window
            log.warning("could not play the cue for %s", event, exc_info=True)

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

    # ---- measurement progress (#153, Knut) --------------------------------
    #
    # "The calculation of progress shall count actual measured patches (not
    # strips), so that same calculation works for both strip mode or
    # patch-by-patch mode. This is also important because a user may go back and
    # forth between strip mode and patch-by-patch mode to read and re-read
    # patches, which may lead to single patches not read in a strip."
    #
    # So the count is a SET of patch location ids, not a running total. Reading
    # a strip adds every patch in it; reading a single patch adds one; reading
    # either again adds nothing, because the ids are already there.
    #
    # The .ti3 cannot be the live source: ArgyllCMS writes it only when a
    # session ends cleanly, so during a measurement it is stale or absent. The
    # files are read when the tab opens and again when a session ends, and the
    # set carries the truth in between.

    def _progress_enabled(self) -> bool:
        try:
            return bool(self._settings.get("measure_progress_bar", True))
        except Exception:      # noqa: BLE001
            return True

    def _count_strip_progress(self, ev: dict) -> None:
        """Every patch of a finished strip counts, by its own location id.

        Collected whether or not the progress bar is switched on. Knut's #153
        wording turns off *"the calculation of patches read in relation to total
        patches"* — the percentage on screen — and #156 needs the record of
        WHICH patches have a reading to know when a chart is actually finished.
        Keeping a set of short strings costs nothing; getting the completion
        metric wrong cost him a chart he thought was done.
        """
        try:
            for p in (ev.get("patches") or []):
                loc = str(p.get("loc", "")).strip()
                if loc:
                    self._progress_locs.add(loc)
            self._refresh_progress()
        except Exception:      # noqa: BLE001 — a readout must never break a read
            log.debug("could not count strip progress", exc_info=True)

    def _count_patch_progress(self, ev: dict) -> None:
        try:
            loc = str(ev.get("loc", "")).strip()
            if loc:
                self._progress_locs.add(loc)
            self._refresh_progress()
        except Exception:      # noqa: BLE001
            log.debug("could not count patch progress", exc_info=True)

    def refresh_progress_setting(self) -> None:
        """Apply a changed "Show measurement progress bar" straight away (#153).

        Called by the main window when Preferences closes. Knut: *"the checkbox
        did not remove progress bar when disabled and pressing OK … Changing
        tabs did also not update"* — the option was read when the bar was drawn
        and never again, so switching it off left the last bar on screen.

        Switching it back on repaints from what the run has actually measured,
        rather than showing whatever figure was last calculated.
        """
        try:
            self._refresh_progress()
        except Exception:      # noqa: BLE001 — a preference must never break the tab
            log.debug("could not apply the progress-bar preference",
                      exc_info=True)

    def _unread_patch_count(self) -> "int | None":
        """How many patches of this chart still have no reading, or ``None``
        when that cannot be established (#156).

        ``None`` is not zero. It means the chart's patch count could not be
        read, and a completion claim must never be made on a guess.
        """
        try:
            from workflow.measurement_state import expected_patches
            _ti3, ti2 = self._progress_files()
            total = expected_patches(ti2)
            if not total or total <= 0:
                return None
            measured = getattr(self, "_progress_base", 0) + len(
                getattr(self, "_progress_locs", ()))
            return max(0, int(total) - int(measured))
        except Exception:      # noqa: BLE001
            log.debug("could not count the unread patches", exc_info=True)
            return None

    def _reset_progress(self, *, from_files: bool = True) -> None:
        """Start the count again — a different chart, or a fresh session.

        With *from_files* the run's own measurement is read first, so a chart
        started earlier is picked up where it was left rather than beginning at
        zero again.
        """
        self._progress_locs = set()
        self._progress_base = 0
        if from_files:
            try:
                from workflow.measurement_state import classify, PROGRESS_STATES
                ti3, ti2 = self._progress_files()
                facts = classify(ti3, ti2)
                if facts.state in PROGRESS_STATES and facts.held:
                    self._progress_base = int(facts.held)
            except Exception:  # noqa: BLE001
                log.debug("could not read progress from the run", exc_info=True)
        self._refresh_progress()

    def _progress_files(self):
        """``(ti3, ti2)`` for the chart on screen, or ``(None, None)``."""
        ti1 = getattr(self, "_ti1_path", None)
        if ti1 is None:
            return None, None
        return ti1.with_suffix(".ti3"), ti1.with_suffix(".ti2")

    def _refresh_progress(self) -> None:
        """Push the current figure at the preview header."""
        preview = getattr(self, "_preview", None)
        if preview is None or not hasattr(preview, "set_measurement_progress"):
            return
        if not self._progress_enabled():
            preview.set_measurement_progress(None, tracking=False)
            return
        try:
            from workflow.measurement_state import (expected_patches,
                                                    progress_percent)
            _ti3, ti2 = self._progress_files()
            total = expected_patches(ti2)
            measured = getattr(self, "_progress_base", 0) + len(
                getattr(self, "_progress_locs", ()))
            preview.set_measurement_progress(
                progress_percent(measured, total), tracking=True)
        except Exception:      # noqa: BLE001
            log.debug("could not refresh the progress bar", exc_info=True)

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
        fence = (_strip_outlier_fence([float(p.get("de", 0)) for p in patches])
                 if self._use_outlier_fence() else 0.0)
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
        self._close_read_failed_window_if_moved_on(ev)
        # ChromIQ supplies the readings for this chart (#159): the bridge owns
        # the whole protocol discipline — one value per outstanding prompt,
        # nothing while a jump is in flight, the read taken off this thread.
        bridge = getattr(self, "_cr30_bridge", None)
        if bridge is not None:
            bridge.on_patch_ready(ev)
        if not self._spot_click_on and any(self._patch_boxes):
            self._spot_click_on = True
            self._preview.set_patch_click_enabled(True, self._patch_boxes)
            self._log.appendPlainText(
                tr("[Engine] Tip: click any patch in the preview to jump "
                   "straight to it."))
        # NEVER HIGHLIGHT A PATCH NOTHING IS LISTENING TO.
        #
        # That is the shape every fault in this area has taken: the preview
        # says "read this", the helper waits on it, and the instrument's button
        # is connected to nothing. The bridge has already decided by the time
        # we get here, so ask it rather than assume — a patch it passed over is
        # one it is moving on from, and pointing at it would invite a press
        # that cannot land.
        if bridge is not None and not bridge.armed_for(loc):
            self._preview.highlight_patch(-1, None)
            return
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
        bridge = getattr(self, "_cr30_bridge", None)
        if bridge is not None:
            # Verify the value we answered was recorded against the patch we
            # answered it FOR. A mis-paired patch is a wrong colour in the .ti3
            # that nothing downstream can detect (#159 B.6).
            bridge.on_patch_measured(ev)
        loc = str(ev.get("loc", ""))
        page, box = self._locate_patch(loc)
        if page < 0 or box is None:
            if not any(self._patch_boxes):
                if not self._patch_geom_warned:
                    self._patch_geom_warned = True
                    self._log.appendPlainText(
                        tr("[Engine] Live patch preview needs a chart made with the "
                           "ChromIQ layout engine, so it is off for this chart. Your "
                           "measurement is unaffected — every patch is still saved and "
                           "checked."))
            elif not self._patch_missing_warned:
                # The chart HAS geometry and this one patch is not in it. That
                # used to return in silence, so the overlay simply stopped
                # growing and nothing said why — indistinguishable, on screen,
                # from the overlay being broken. Said once per session: it is a
                # property of the chart, so every later patch would repeat it.
                self._patch_missing_warned = True
                log.warning("no geometry for patch %r; the chart has %d boxes",
                            loc, sum(len(d) for d in self._patch_boxes))
                self._log.appendPlainText(
                    tr("[Engine] This chart records where its patches are, but "
                       "not where “{loc}” is, so that patch is left out of the "
                       "live preview. Your measurement is unaffected — every "
                       "patch is still saved and checked.").format(loc=loc))
            return
        from PyQt6.QtGui import QColor as _QC
        from workflow.icc_info import xyz_to_lab
        warn_de = float(self._settings.get("patch_read_warn_de", _PATCH_WARN_DE))
        de_p = float(ev.get("de", 0))
        exyz = ev.get("exyz", [0, 0, 0])
        mxyz = ev.get("xyz", [0, 0, 0])
        exp_rgb = _xyz_d50_to_srgb8(exyz)
        meas_rgb = _xyz_d50_to_srgb8(mxyz)
        # Patch by patch the limit is the whole rule — Knut's ruling of
        # 2026-07-27 (option (a)), after asking how "stands out" could possibly
        # be judged from a handful of patches. There is no finished strip here
        # to compare against, and a comparison against however many patches
        # happen to have been read so far would mean the same patch was judged
        # differently depending on when in the session it was read. So this mode
        # answers the plainer question: is this patch past your limit?
        #
        # The two modes therefore behave differently ON PURPOSE, and both help
        # texts say so — see the "Patch-reading error limit" and the
        # patch-by-patch explanations.
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

    def _read_builds_on_existing(self) -> bool:
        """True when this read ADDS to the measurement already on disk.

        Refine and resume both hand the existing ``.ti3`` to chartread with
        ``-r``, so it is read, not replaced. Two things must agree about that
        and used not to:

        * the question before Start (nothing is being replaced, so nothing to
          warn about), and
        * whether the measurement gets moved into ``old/`` first.

        They disagreed, and it destroyed measurements. Knut, #130 2026-08-01,
        five times in one session::

            Error - Unable to read chart being resumed '…/run4/<name>.ti3'
                  : Unable to open file '…' for reading

        ChromIQ archived the ``.ti3`` and then told chartread to resume from
        it. The session died on the spot and the readings were only still there
        because ``old/`` had them — *"Many of these errors above worked in
        earlier betas. What has happened?"* This is what happened: the archive
        call was moved out of the question so that asking and moving files were
        separate jobs, and in the move it lost the condition the question
        applies. One test now asserts both call this.
        """
        guided = self._current_mode() == "guided"
        resume = (self._resume_cb if guided else self._m_resume_cb)
        refine = (self._refine_cb if guided else self._m_refine_cb)
        return bool(
            (resume is not None and resume.isVisible() and resume.isChecked())
            or (refine is not None and refine.isEnabled() and refine.isChecked()))

    def _replace_message(self, facts, ti3) -> "tuple[str, str]":
        """One of §5's messages, chosen by what the measurement file holds.

        The **text** comes from ``workflow/measurement_messages.py``, which is
        the reviewed catalogue (§M) — Knut, beta.125: *"Only approved message
        text shall be used in any of the windows."* This method's job is to
        pick the right ID and supply the numbers, nothing else.
        """
        from workflow import measurement_messages as M
        from workflow.measurement_state import Ti3State

        a = facts.expected
        c = facts.held or 0
        path = str(ti3)

        if facts.state is Ti3State.MISMATCHED:
            extra = ""
            if facts.claimed is not None and facts.claimed != c:
                extra = tr(M.M_TI3_MISMATCH_EXTRA).format(b=facts.claimed, c=c)
            stem = Path(ti3).stem
            return M.M_TI3_MISMATCH.render(
                c=c, a=a if a is not None else "?", extra=extra,
                stem=stem, path=str(Path(ti3).parent))

        if facts.state is Ti3State.COMPLETE:
            return M.M_REPLACE_COMPLETE.render(a=a if a is not None else c,
                                               path=path)

        if c == 0:
            # The file is there but holds nothing readable (§3a's empty,
            # headerless and unreadable states). The approved catalogue has no
            # message for this, and the partial one would print "0 of the
            # chart's ? patches have been read" — which reads as a bug rather
            # than a fact. M-REPLACE-UNCOUNTABLE is flagged PROPOSED and is on
            # the issue for Knut to approve or reword.
            return M.M_REPLACE_UNCOUNTABLE.render(path=path)

        if a is None:
            # The chart's patch count could not be read. Since beta.128 Start
            # Measurement is unavailable without a `.ti2`, so the only way here
            # is a `.ti2` that exists but cannot be parsed — which chartread
            # would refuse as well. Try the `.ti1`, which carries the same
            # count, before giving up.
            from workflow.measurement_state import expected_patches
            _ti1 = getattr(self, "_ti1_path", None)
            a = expected_patches(
                Path(_ti1).with_suffix(".ti1") if _ti1 else None)
        if a is None:
            # Still unknown: say what is true rather than state a fraction with
            # a missing denominator. Defensive — the condition Knut asked about
            # ("readings with no chart") is prevented, not messaged.
            log.warning("chart patch count unreadable for %s", ti3)
            return M.M_REPLACE_UNCOUNTABLE.render(path=path)

        return M.M_REPLACE_PARTIAL.render(c=c, a=a, path=path)

    def _confirm_replacing_measurement(self) -> bool:
        """Ask before a fresh read writes over a measurement that is already there.

        Knut, #131 2026-07-28: *"if I click on Start Measurement on a chart that
        has a measurement, there is supposed to be a warning, which not always
        comes."* It did not come at Start at all — the only warning about
        replacement lived in the window that appears when a chart with a
        measurement is **loaded**, so once that window had been dismissed (or
        the chart was already open) nothing stood between a click and the old
        readings.

        It asks only when the read really would replace something: a
        measurement exists **and** neither refine/resume is ticked, because with
        either of those the existing readings are added to rather than
        overwritten.

        **"Don't ask again" is deliberately narrow** (Knut, #131 2026-07-28):
        remembered for the *currently selected* profiling run or dated
        verification only, and only in memory — so it goes quiet while you work
        on that one run, and comes back both for any other run and for the same
        run on another day. See :meth:`_replace_warning_scope`.
        """
        ti3 = self._measurement_at_risk()
        if ti3 is None:
            return True
        if self._read_builds_on_existing():
            return True        # the old readings are kept and built on

        scope = self._replace_warning_scope()
        if scope is not None and scope in self._replace_warning_silenced:
            return True

        from PyQt6.QtWidgets import QCheckBox, QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        # §5: which of the three this is depends on what the file actually
        # holds, so the message says the real numbers rather than "a
        # measurement". Resume is deliberately NOT offered as a checkbox here —
        # Knut: *"the Resume setting should be as the user set it before
        # pressing start measurement, and the message should not show a separate
        # Resume checkbox to change the users choice."*
        from workflow.measurement_state import Ti3State, classify
        _ti1 = getattr(self, "_ti1_path", None)
        facts = classify(ti3, _ti1.with_suffix(".ti2") if _ti1 else None)
        title, body = self._replace_message(facts, ti3)
        box.setWindowTitle(title)
        # The headline goes in setText (bold) and the explanation in
        # setInformativeText (normal weight) — the pattern the rest of the app
        # already uses. A whole screen of bold is a wall nobody reads, and the
        # message is long on purpose.
        box.setText(title)
        # THE BODY IS ALREADY THE BODY. Slicing `len(title)` characters off it
        # here is a leftover from when render() returned one string with the
        # headline on the front; it now returns the two separately, so the cut
        # ate the opening sentence of every §5 message — Knut, beta.128: *"the
        # text starts with '. Starting now without …'"* and *"first sentence
        # after title is 'ad, and this run's profile was built …'"*. Exactly
        # len("This run already holds part of a measurement") and
        # len("This chart is fully measured") characters, respectively.
        box.setInformativeText(body)
        # Only offered where it can be scoped to one run — with no run selected
        # there is nothing to remember it against, and a blanket "never ask"
        # is exactly what this must not become.
        ask = None
        if scope is not None:
            ask = QCheckBox(self._replace_warning_silence_label(), box)
            ask.setToolTip(tr(
                "Only for this one run, and only until you close ChromIQ. Every "
                "other run keeps asking, and so does this one the next time you "
                "start the program."))
            box.setCheckBox(ask)
        # NOTHING HAS STARTED YET. Knut, beta.132: *"Measurement has not yet
        # started, so it is wrong name for the 'MEASURE AGAIN' button. Call
        # button instead 'MEASURE ANYWAY'."* This window opens on the way IN to
        # a measurement — it is the last chance to stop — so the button says
        # what pressing it does now, not what happened before.
        go = box.addButton(tr("Measure anyway"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(go)
        # Long labels clip once the font swap widens them, and polish
        # does not happen offscreen — so fit them here (Knut, #130).
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        fit_message_box_buttons(box)
        box.exec()
        agreed = box.clickedButton() is go
        # Remember only when the user actually went ahead: ticking the box and
        # then cancelling means "not this time", not "never warn me again".
        if agreed and ask is not None and ask.isChecked() and scope is not None:
            self._replace_warning_silenced.add(scope)
            log.info("Replace-measurement warning silenced for %s (this session)",
                     scope)
        return agreed

    def _archive_measurement_before_replacing(self) -> None:
        """Move the current measurement into ``old/`` before a fresh read
        overwrites it. Quiet: the window that just asked has said what happens.
        """
        if self._ti1_path is None:
            return
        # NOTHING IS BEING REPLACED WHEN THE READ RESUMES OR REFINES.
        #
        # chartread is handed the existing .ti3 with -r and reads it. Moving it
        # away first does not protect it — it removes the file the measurement
        # is about to continue from, and the session dies with "Unable to read
        # chart being resumed" (Knut, #130 2026-08-01). See
        # :meth:`_read_builds_on_existing`.
        if self._read_builds_on_existing():
            return
        ti3 = self._ti1_path.with_suffix(".ti3")
        if not ti3.is_file():
            return          # nothing to keep
        # An unreadable file is archived too, because M-REPLACE-UNCOUNTABLE has
        # just promised it would be: *"The file you have is moved to the run's
        # 'old' folder and nothing is deleted, so you can always look at it
        # afterwards."* If the session then writes nothing, the archive comes
        # straight back — see _restore_displaced_measurement.
        try:
            from core.file_manager import Run
            dest = Run.for_dir(ti3.parent).archive_to_old([ti3])
        except OSError as exc:
            log.warning("could not archive %s before replacing it: %s", ti3, exc)
            return
        if dest is not None:
            self._displaced_measurement = dest
            self._log.appendPlainText(tr(
                "Your previous measurement has been moved to the run's old "
                "folder before this new one starts, so it is still there if "
                "you need it."))

    def _replace_warning_scope(self) -> "tuple | None":
        """What the "don't ask again" tick is remembered against, or None when
        there is nothing specific enough to remember it against.

        Knut's rule (#131, 2026-07-28): the currently selected **profile run**
        with Run type = Profiling, or the currently selected **dated
        verification** with Run type = Verification — and for a verification
        only when that dated folder actually holds a measurement. "New run" and
        "New verification" name nothing yet, so they are never scoped.

        The project root is part of the key so two projects that both have a
        "run1" can never silence each other.
        """
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return None
        try:
            proj = ctl.project_or_none()
            if proj is None:
                return None
            root = str(proj.root)
            run_id = ctl.target.profile_run
            if not run_id or not proj.has_run(run_id):
                return None                      # "New run" — nothing to key on
            if not ctl.target.is_verification():
                return ("profiling", root, run_id)
            vid = ctl.target.verification_id
            if not vid:
                return None                      # "New verification"
            verification = proj.run(run_id).verification(vid)
            if not verification.measurement_ti3.exists():
                return None                      # nothing there to be replaced
            return ("verification", root, run_id, vid)
        except Exception:      # noqa: BLE001 — a scope is a convenience, never a gate
            return None

    def _offer_silence_label(self) -> str:
        """The tick's wording in the existing-measurement window. It names the
        window it silences, so silencing one is never mistaken for the other."""
        ctl = getattr(self, "_target_ctl", None)
        try:
            if ctl is not None and ctl.target.is_verification():
                return tr("Don't ask this again for this verification, until I "
                          "close ChromIQ")
        except Exception:      # noqa: BLE001
            pass
        return tr("Don't ask this again for this profile run, until I close "
                  "ChromIQ")

    def _replace_warning_silence_label(self) -> str:
        """The tick's wording, naming the run it will be remembered for so the
        promise is visible rather than implied."""
        ctl = getattr(self, "_target_ctl", None)
        try:
            if ctl is not None and ctl.target.is_verification():
                return tr("Don't ask again for this verification, until I "
                          "close ChromIQ")
        except Exception:      # noqa: BLE001
            pass
        return tr("Don't ask again for this profile run, until I close ChromIQ")

    def _measurement_at_risk(self) -> "Path | None":
        """The measurement a plain re-read would overwrite, or None.

        Not the same as :meth:`_existing_ti3_for_chart`, and that difference was
        a real gap: a verification's readings live in its **dated folder**, not
        beside the shared verification chart, so keying on the chart-adjacent
        .ti3 meant the warning could never fire for a verification at all
        (Knut, #131 2026-07-28).
        """
        ctl = getattr(self, "_target_ctl", None)
        try:
            if ctl is not None and ctl.target.is_verification():
                proj = ctl.project_or_none()
                run_id = ctl.target.profile_run
                vid = ctl.target.verification_id
                if proj is None or not run_id or not vid \
                   or not proj.has_run(run_id):
                    return None      # a new verification replaces nothing
                ti3 = proj.run(run_id).verification(vid).measurement_ti3
                return ti3 if ti3.is_file() else None
        except Exception:      # noqa: BLE001
            pass
        # NOT _existing_ti3_for_chart(): that one hides a file with no readings
        # on purpose, so the tab and Generate Chart stop warning about a
        # measurement that was never taken (Knut, #130 2026-07-30). Pressing
        # Start is the one place where such a file must still be mentioned —
        # §3a's "header only" and "empty" rows are exactly what
        # M-REPLACE-UNCOUNTABLE is for, and it promises the file is moved to
        # "old" rather than quietly overwritten.
        ti3 = self._existing_ti3_for_chart()
        if ti3 is not None:
            return ti3
        path = getattr(self, "_ti1_path", None)
        if path is None:
            return None
        cand = Path(path).with_suffix(".ti3")
        return cand if cand.is_file() else None

    def _existing_ti3_for_chart(self) -> "Path | None":
        """The measured .ti3 sitting next to the loaded chart (#134), or None."""
        if self._ti1_path is None:
            return None
        ti3 = self._ti1_path.with_suffix(".ti3")
        if not ti3.is_file():
            return None
        # A file with no readings is not a measurement, and treating it as one
        # is what made ChromIQ warn about a measurement that was never taken —
        # on activating the Measure tab, and again from Generate Chart (Knut,
        # #130 2026-07-30): *"activating measure tab still detects a ti3 file so
        # reports a warning message … while it is not really true"*. Sessions
        # from this version onwards archive such a file the moment they end;
        # this keeps the older ones already on disk equally quiet.
        if _cgats_has_no_readings(ti3):
            return None
        return ti3

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
        # Resolve to the .ti2 FIRST. per_patch_overlay names each patch from
        # the reference chart, and only the .ti2 knows where a patch sits: from
        # a .ti1 it can only return SAMPLE_IDs ("103"), while _patch_boxes and
        # _locate_patch are keyed by chart location ("A2"). Nothing then
        # matches, every patch is dropped by the page<0 guard in
        # _on_chart_measured, and the overlay comes up empty.
        #
        # Opening a project is exactly the route that hands this tab the .ti1
        # (ui/main_window.py, _restore_last_session) — which is why this only
        # ever failed on a REOPENED project and never on one measured in the
        # same sitting. _chart_file_for exists for this and says so.
        chart = self._chart_file_for(self._ti1_path)
        try:
            from workflow.measurement_report import per_patch_overlay
            patches = per_patch_overlay(ti3, chart)
        except Exception:          # noqa: BLE001 — never break on a bad file
            patches = []
        if not patches or not any(self._patch_boxes):
            return False
        # Will ANY of these patches actually land? _on_chart_measured drops
        # every patch whose loc resolves to no box, and it does so silently, so
        # asking afterwards how full the preview is cannot answer this
        # question: the overlay accumulates, so a leftover from an earlier
        # chart would read as success for a file that painted nothing. Decide
        # from the patches themselves, before drawing.
        drawable = sum(1 for p in patches
                       if self._locate_patch(str(p.get("loc", "")))[1] is not None)
        if not drawable:
            # Returning True on an empty overlay is what made this silent: the
            # caller took it as painted and so never pointed the user at
            # Tools > Inspect a measurement, and the user was left looking at
            # an unchanged chart with no message of any kind.
            log.info("overlay: none of the %d measured patches match this "
                     "chart's geometry", len(patches))
            return False
        self._on_chart_measured({"patches": patches})
        return True

    def _clear_overlay(self) -> None:
        """Remove a statically-shown overlay (#134)."""
        self._preview.clear_patch_overlay()

    def _chart_identity(self) -> "tuple | None":
        """What makes the loaded chart *this* chart: its path and the moment its
        .ti2 was written. The second half matters — re-generating a chart into
        the same run keeps the path and replaces the patches, which is exactly
        the case that fooled the preview (Knut, #131 2026-07-28)."""
        if self._ti1_path is None:
            return None
        try:
            return (str(self._ti1_path), self._ti1_path.stat().st_mtime_ns)
        except OSError:
            return (str(self._ti1_path), None)

    def _discard_stale_overlay(self) -> None:
        """Drop a painting that belongs to a chart we are leaving (#131).

        Two different things end up on the preview and both had to go: the
        static overlay read back from a .ti3, and the live expected-vs-measured
        painting a measurement leaves behind. Only the first was ever cleared,
        and only when its checkbox happened to be ticked — so the live one from
        a part-measured chart survived a re-generation and every run switch
        after it (Knut, #131 2026-07-28).

        **Only when the chart has actually changed.** This runs from the same
        place that refreshes the option boxes, and that place also runs at the
        end of a measurement — where the painting is the freshly-read strips and
        clearing it would blank the preview at the very moment the user wants to
        see what they got. A measurement still in progress is skipped for the
        same reason.
        """
        if self._runner.is_running:
            return
        now = self._chart_identity()
        if now == getattr(self, "_painted_chart", None):
            return
        self._painted_chart = now
        try:
            self._clear_overlay()
            # The strip reading times belong to the chart that was measured,
            # not to the one now in front of you. They were only ever cleared
            # when a measurement STARTED, so switching to a new run still
            # showed the previous run's times — six of them, on a run that had
            # never been measured (Knut, #130 2026-07-28).
            self._clear_pace_readout()
        except Exception:      # noqa: BLE001 — never block a chart change
            log.warning("Could not clear the previous chart's readout",
                        exc_info=True)

    # ------------------------------------------------------------------
    # Guided and Manual show the same settings (Knut, beta.138)
    # ------------------------------------------------------------------
    #: Every control that exists once per module and means the same thing in
    #: both. "Show overlay" was already linked; Knut asked for the rest:
    #: *"They all shall be linked between Guided mode and Manual mode, so same
    #: parameter in both modes follow each other when changed."*
    _LINKED_PAIRS: tuple = (
        ("_resume_cb", "_m_resume_cb"),
        # Patch-by-patch is visible in BOTH modules since #160, and Knut's rule
        # (beta.138, confirmed by him 2026-08-21) is that a parameter which is
        # *shared and visible* must follow between them. It is not a Guided
        # hard-coded default — those must NOT be linked — so it belongs here.
        ("_pbp_cb", "_m_pbp_cb"),
        ("_suppress_cb", "_m_suppress_cb"),
        ("_bidir_combo", "_m_bidir_combo"),
        ("_bidir_auto_cb", "_m_bidir_auto_cb"),
        ("_g_overlay_mode", "_m_overlay_mode"),
        ("_g_only_measured", "_m_only_measured"),
        ("_g_aim_help", "_m_aim_help"),
        ("_g_patch_tile", "_m_patch_tile"),
    )

    def _link_mode_controls(self) -> None:
        """Make each pair follow the other, in both directions.

        Signals are blocked on the receiving side, so a change travels once and
        no pair can bounce. The **tolerance** and the rest of the chartread
        option rows are linked by key rather than by attribute, because they are
        built from one table into two lists.
        """
        from PyQt6.QtWidgets import (QAbstractSpinBox, QCheckBox, QComboBox)

        def _mirror(src, dst) -> None:
            if src is None or dst is None:
                return
            # RESTORING IS NOT CHANGING.
            #
            # `measure_settings.apply` writes both modules' stored values, and
            # the Manual key comes fifteen keys before its Guided twin. With the
            # mirror live, the Guided write travelled back into Manual and
            # overwrote the value that had just been restored from the file —
            # and the next save wrote that loss into meta.json. A target's
            # settings must come from that target's own record
            # (docs/design/per_target_settings.md), so the link stands down
            # while a record is being applied and resumes for the user's own
            # edits. Only the mirror is suspended, not the signals: the overlay
            # checkbox loads the overlay on its own signal, and the option rows
            # grey their spin boxes on theirs.
            if getattr(self, "_suspend_linking", False):
                return
            dst.blockSignals(True)
            try:
                if isinstance(src, QCheckBox) and isinstance(dst, QCheckBox):
                    dst.setChecked(src.isChecked())
                elif isinstance(src, QComboBox) and isinstance(dst, QComboBox):
                    i = dst.findData(src.currentData())
                    dst.setCurrentIndex(i if i >= 0 else dst.currentIndex())
                elif isinstance(src, QAbstractSpinBox) \
                        and isinstance(dst, QAbstractSpinBox):
                    dst.setValue(src.value())
            finally:
                dst.blockSignals(False)

        def _pair(a, b) -> None:
            if a is None or b is None:
                return
            for src, dst in ((a, b), (b, a)):
                if isinstance(src, QCheckBox):
                    src.toggled.connect(
                        lambda _c, s=src, d=dst: _mirror(s, d))
                elif isinstance(src, QComboBox):
                    src.currentIndexChanged.connect(
                        lambda _i, s=src, d=dst: _mirror(s, d))
                elif isinstance(src, QAbstractSpinBox):
                    src.valueChanged.connect(
                        lambda _v, s=src, d=dst: _mirror(s, d))

        for a_name, b_name in self._LINKED_PAIRS:
            _pair(getattr(self, a_name, None), getattr(self, b_name, None))

        # The chartread option rows — tolerance and its neighbours — come from
        # one table built twice, so they are matched by their key.
        guided = {o.key: o for o in getattr(self, "_chartread_opts", [])}
        for opt in getattr(self, "_m_chartread_opts", []):
            twin = guided.get(opt.key)
            if twin is None:
                continue
            _pair(opt.checkbox, twin.checkbox)
            _pair(opt.widget, twin.widget)

    def _sync_overlay_checkboxes(self, checked: bool) -> None:
        """Keep the guided + manual 'Show overlay' boxes in step (#134)."""
        for cb in (getattr(self, "_overlay_cb", None),
                   getattr(self, "_m_overlay_cb", None)):
            if cb is not None and cb.isChecked() != checked:
                cb.blockSignals(True)
                cb.setChecked(checked)
                cb.blockSignals(False)

    def _adopt_overlay_after_first_measurement(self) -> None:
        """Tick "Show overlay from existing measurement" when a measurement has
        just created one (Knut, #131 2026-07-28).

        His report: he measured a run that had nothing, read one strip and
        stopped. The readings were on the preview — but the checkbox, which had
        been hidden the whole time because there was no measurement to show,
        appeared **unticked**. So the picture said "overlay on" and the control
        said "overlay off".

        His rule: *"After creating measurements, where the Show overlay function
        did show during the measurement, then the checkbox should be ON when
        exiting the measurement and the checkbox becomes visible."* Ticking it
        also makes the two agree in substance, not just in appearance — the
        painting is re-read from the finished .ti3.

        Only on the transition. A box the user has deliberately unticked on a
        chart that already had a measurement is left alone.
        """
        try:
            if self._existing_ti3_for_chart() is None:
                return
            cb = (self._overlay_cb if self._current_mode() == "guided"
                  else self._m_overlay_cb)
            if cb is None or not cb.isVisible() or cb.isChecked():
                return
            self._sync_overlay_checkboxes(True)
            self._show_overlay_from_existing_ti3()
        except Exception:      # noqa: BLE001 — never break the end of a read
            log.warning("Could not adopt the overlay after the measurement",
                        exc_info=True)

    def _repaint_overlay_from_disk(self) -> None:
        """Draw the overlay for everything the run's measurement already holds.

        Used at the start of a session (and after one), so a resumed read never
        shows less than the file does.
        """
        try:
            cb = (self._overlay_cb if self._current_mode() == "guided"
                  else self._m_overlay_cb)
            if cb is None or not cb.isChecked():
                return
            self._show_overlay_from_existing_ti3()
        except Exception:      # noqa: BLE001 — an overlay is never worth a crash
            log.warning("Could not draw the overlay from the measurement",
                        exc_info=True)

    def _restore_overlay_after_measurement(self) -> None:
        """Put the from-measurement overlay back on the preview when the user
        asked to see it (#131, Knut 2026-07-27).

        Best-effort by design: a measurement that produced nothing placeable
        simply leaves the preview as it is, exactly as ticking the box would.
        """
        try:
            cb = (self._overlay_cb if self._current_mode() == "guided"
                  else self._m_overlay_cb)
            if cb is None or not cb.isChecked():
                return
            self._show_overlay_from_existing_ti3()
        except Exception:      # noqa: BLE001 — never break the end of a read
            log.warning("Could not restore the overlay after the measurement",
                        exc_info=True)

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
        # No usable overlay data → undo the tick and say WHICH of the two very
        # different reasons applies.
        #
        # Knut, #130 2026-07-30: he recovered a partial measurement that turned
        # out to hold no readings at all, and this window told him it "looks like
        # it was made for a different chart". Nothing mismatched — there was
        # simply nothing in the file. *"The message is wrong and it should have
        # been detected that the measurements were empty."* He is right: one calls
        # for measuring, the other for finding the right chart, so telling them
        # apart is the whole value of the message.
        self._sync_overlay_checkboxes(False)
        reason = self._overlay_failure_reason()
        # The catalogue, imported here like the six other methods that use it.
        # It was missing, so the "absent" branch below raised NameError and the
        # approved M-OVERLAY-NO-MEASUREMENT window never opened — the box just
        # unticked itself. The test that guards this window read the method's
        # SOURCE and so stayed green through three releases.
        from workflow import measurement_messages as M
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)      # clean style, no icon (Basti)
        # Headline in setText (QMessageBox paints it bold), body in
        # setInformativeText. Written as one bold block before, which is the
        # fault Basti reported on the chart-choice window in beta.189.
        if reason == "absent":
            # M-OVERLAY-NO-MEASUREMENT — approved by Knut, 2026-08-14.
            #
            # A chart that has never been measured used to be told *"This
            # measurement was made for a different chart"* — a claim about a
            # file that does not exist (#155). Stopping that claim was the bug
            # fix; this is the window that replaces it. It said its piece in the
            # log until the text was approved, because measurement wording goes
            # to §M-PROPOSED first — and his ruling on where it belongs is
            # equally clear: *"all events shall have windows, and not hidden in
            # a log where user will not see it."*
            title, body = M.M_OVERLAY_NO_MEASUREMENT.render()
            box.setWindowTitle(tr("This chart has not been measured yet"))
            box.setText(title)
            box.setInformativeText(body)
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
            box.exec()
            return
        elif reason == "empty":
            box.setWindowTitle(tr("There is nothing measured yet to show"))
            box.setText(tr("This measurement holds no readings yet"))
            box.setInformativeText(
                tr("The measurement file exists, but nothing has been read into "
                   "it, so there is nothing to draw on the patches.\n\n"
                   "That happens when a measurement was started and stopped "
                   "before any strip was read successfully. Measure the chart "
                   "and the overlay will show what you read as you go."))
        elif reason == "no_geometry":
            box.setWindowTitle(tr("This chart doesn't record where its patches are"))
            box.setText(tr("Your measurement is fine — this chart just can't "
                           "display it on the patches"))
            box.setInformativeText(
                tr("Nothing is wrong with the measurement: it belongs to this "
                   "chart and every reading in it is valid. It can be built into "
                   "a profile exactly as it is.\n\n"
                   "The overlay needs to know where each patch sits on the "
                   "printed page, and this chart does not carry that "
                   "information. Charts made by older versions of ChromIQ — "
                   "before the ChromIQ layout engine — were laid out by "
                   "ArgyllCMS's printtarg, which does not record the patch "
                   "positions anywhere, so there is nothing to draw onto.\n\n"
                   "To see the measured values, open the measurement in "
                   "Tools ▸ Inspect a measurement, which shows every patch and "
                   "its colour as a table. If you would like the overlay on a "
                   "future chart, generate it with the ChromIQ layout engine "
                   "switched on in Create Chart — those charts save their patch "
                   "positions beside the chart file."))
        else:
            box.setWindowTitle(tr("Can't show the overlay"))
            box.setText(tr("This measurement was made for a different chart"))
            box.setInformativeText(
                tr("The patches in the measurement don't line up with the "
                   "patches in this chart, so drawing them here would put "
                   "colours on the wrong squares.\n\n"
                   "Open it in Tools ▸ Inspect a measurement to see the measured "
                   "values as a table instead."))
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        from ui.widgets import (fit_message_box_buttons,
                                order_message_box_buttons)
        fit_message_box_buttons(box)
        box.exec()

    def _overlay_failure_reason(self) -> str:
        """Why the overlay could not be drawn: ``empty`` / ``no_geometry`` /
        ``mismatch``. THREE causes, not two, and they need different answers.

        Basti, 2026-08-08, measuring a chart made long before the layout engine:
        the window told him the measurement "looks like it was made for a
        different chart". It was not — measured on his own files, the
        measurement resolved 90 patches against that chart with real ΔE values.
        The only thing missing was the per-patch geometry: a printtarg sheet
        carries no ``.strips.json`` and no ``channels.json`` ``layout`` block,
        so there is nowhere to draw. Telling someone their good measurement
        belongs to another chart invites them to throw it away and re-measure.

        This is the same shape as Knut's report in #130 (an empty ``.ti3``
        reported as a mismatch): the overlay failing says nothing about *why*,
        so each cause is established from the files rather than inferred.
        """
        if self._ti1_path is None:
            return "absent"
        if self._measurement_is_empty():
            return "empty"
        # NO MEASUREMENT AT ALL IS NOT A FOREIGN MEASUREMENT.
        #
        # `_existing_ti3_for_chart` answers None for three different situations:
        # no chart, no file, and a file holding no readings. Only the last two
        # were told apart, so a run that has never been measured was reported as
        # *"This measurement was made for a different chart"* — a claim about a
        # file that does not exist (#155, Knut: *"This is strange, as the chart
        # is what I printed and started measurements on."*). His project shows it
        # exactly: run1 has no .ti3 at all.
        #
        # This is the same shape as the empty-file fault he found in #130. That
        # fix taught the code to recognise EMPTY; ABSENT was left behind it.
        if not self._ti1_path.with_suffix(".ti3").is_file():
            return "absent"
        ti3 = self._existing_ti3_for_chart()
        if ti3 is None:
            return "mismatch"
        try:
            from workflow.measurement_report import per_patch_overlay
            # The .ti2, for the same reason as
            # _show_overlay_from_existing_ti3: from a .ti1 every patch comes
            # back named by SAMPLE_ID, which matches nothing — and here that
            # produced the OPPOSITE of a missing overlay. `matched` was True,
            # so this reported "no_geometry" and told the user their chart
            # carries no patch positions, about a chart with 390 of them.
            matched = bool(per_patch_overlay(
                ti3, self._chart_file_for(self._ti1_path)))
        except Exception:      # noqa: BLE001 — a bad file is not a mismatch claim
            matched = False
        if not matched:
            return "mismatch"
        # The readings belong to this chart, so the only thing that can have
        # failed is the geometry.
        return "no_geometry"

    def _measurement_is_empty(self) -> bool:
        """Whether this chart's ``.ti3`` exists but carries no readings.

        Read from the file rather than inferred from the overlay having failed:
        an empty measurement and a foreign one both leave the overlay with
        nothing to draw, and only the file itself says which happened (#130,
        Knut 2026-07-30).
        """
        if self._ti1_path is None:
            return False
        ti3 = self._ti1_path.with_suffix(".ti3")
        if not ti3.is_file():
            return False
        return _cgats_has_no_readings(ti3)

    def _on_preview_patch_clicked(self, page: int, loc: str) -> None:
        if not self._manager.engine_active or not loc:
            return
        # BEFORE the command goes out, not after: a reading can arrive between
        # the two, and while a jump is outstanding it belongs to the patch the
        # user is leaving (#159 B.4 — measured landing B1's colour in A1).
        bridge = getattr(self, "_cr30_bridge", None)
        if bridge is not None:
            bridge.note_goto(loc)
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
            target = Path(custom).expanduser() if custom else default_output_root()
        reveal_in_file_manager(target)

    def _maybe_save_measurement_report(self, ti3) -> None:
        """When the Settings option is on, build + save a dated accuracy report
        next to the chart after a measurement, so reports accrue for
        over-time comparison (Knut). Best-effort — never blocks or errors the
        measurement flow."""
        if not bool(self._settings.get("save_measurement_report", False)):
            return
        try:
            from workflow.measurement_report import (
                DEFAULT_PASS_AVG, DEFAULT_PASS_MAX, build_report, save_report,
                stamp_verdict)
            from pathlib import Path as _P
            ti3 = _P(ti3)
            if ti3.suffix.lower() != ".ti3" or not ti3.exists():
                return
            report = build_report(
                ti3, argyll_bin=str(self._settings.get("argyll_bin_path", "") or ""))
            # #182, Knut 2026-09-04: *"Verdict should be saved for each dated
            # run."* The thresholds are a GLOBAL setting, so a report that
            # stored neither them nor its verdict was re-graded by whatever the
            # spin boxes said the next time anybody opened the window. Stamped
            # HERE, with the thresholds in force at the moment of the
            # measurement, and never again afterwards.
            stamp_verdict(
                report,
                float(self._settings.get("report_pass_threshold_avg",
                                         DEFAULT_PASS_AVG)),
                float(self._settings.get("report_pass_threshold_max",
                                         DEFAULT_PASS_MAX)))
            path = save_report(report, ti3.parent)
            self._log.appendPlainText(
                tr("[Report] Measurement report saved: {name}").format(
                    name=path.name))
        except Exception as exc:  # noqa: BLE001
            log.warning("measurement report failed: %s", exc)
            self._say_report_not_saved(exc)

    def _say_report_not_saved(self, exc: Exception) -> None:
        """Tell the user, on screen, that the report they asked for is not there.

        M-REPORT-NOT-SAVED (§M-PROPOSED). Until this existed the failure went to
        `log.warning` and nowhere else: the measurement finished, the window
        looked exactly as it does on a good run, and the only trace was a line
        in a file the user never opens. A success says so in this same log —
        so a silent failure did not merely fail to inform, it read as a success.

        THE LOG AND THE STATUS FLASH, NOT A WINDOW. The shape is the one
        `_on_cr30_dropped_reading` already uses in this tab. Basti asked for a
        pop-up on M-CR30-READ-FAILED for a stated reason — *"instead of ruining
        a whole measurement session when this is unnoticed"* — and that reason
        does not reach here: the measurement is already over and safe on disk,
        the .ti3 is the record, and `Measurement report…` rebuilds this report
        from it whenever the user likes. There is nothing to interrupt and
        nothing to do at that instant, so a modal would cost more than it says.
        """
        from workflow import measurement_messages as M
        title, body = M.M_REPORT_NOT_SAVED.render()
        self._log.appendPlainText("")
        self._log.appendPlainText(title)
        self._log.appendPlainText(body)
        # THE EXCEPTION IS NOT PART OF THE MESSAGE. Basti's standing rule for
        # user-facing text is "friendly, extensive, easy to understand and
        # correct", and an errno with a path in it fails three of the four: it
        # blames, it is not plain language, and — because this method cannot
        # tell a failure to BUILD the report from a failure to WRITE it — a
        # sentence built around it would state a cause nobody has established.
        # So the message says what happened and what it costs, and the
        # technical line follows it, named as such, on the line the message
        # itself points at. `str(exc)` is empty for a bare `RuntimeError()`,
        # which is the one case where the class name is the only thing there is.
        self._log.appendPlainText(tr("[Report] Technical detail: {detail}").format(
            detail=f"{type(exc).__name__}: {exc}" if str(exc)
            else type(exc).__name__))
        self._log.ensureCursorVisible()
        self._flash_status(title, duration_ms=10000)

    def _open_measurement_report(self) -> None:
        """Open the measurement-report viewer for the current chart's .ti3."""
        from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
        ti3 = self._ti1_path.with_suffix(".ti3") if self._ti1_path else None
        # A verification's measurements live in DATED folders, never beside
        # the shared chart — so the beside-the-chart guess above never finds
        # them (Sebastian, 2026-08-10: after Restore Used Chart the report
        # claimed the measured chart was unmeasured). Resolve through the
        # bar: the selected date first, else the run's newest measured date.
        if self._is_verification_run():
            run = self._guard_run()
            if run is not None:
                ctl = getattr(self, "_target_ctl", None)
                vid = ctl.target.verification_id if ctl is not None else ""
                cand = None
                if vid and run.verification(vid).measurement_ti3.exists():
                    cand = run.verification(vid).measurement_ti3
                else:
                    dated = [v for v in run.verifications() if v.exists()]
                    if dated:
                        cand = dated[-1].measurement_ti3
                if cand is not None:
                    ti3 = cand
        if ti3 is None or not ti3.exists():
            from PyQt6.QtWidgets import QMessageBox
            inform(
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
        # Set BEFORE every early return: this is a property of the chart, not
        # of the engine, and the manager needs it whichever reader runs (#159).
        p.stock_reader_cannot_read = p.external_values = self._chart_is_cr30()
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

    def _resume_has_anything_to_resume(self, ticked: bool) -> bool:
        """The resume tick, honoured only when there is something behind it.

        Specification §3a/§5: a missing, empty, header-only or corrupt `.ti3`
        gives ``C₀ = 0`` and is *"treated exactly as 'no measurement'"*, and §5's
        first row pairs that state with **no warning** — the measurement just
        starts. Sending ``-r`` there makes chartread refuse before the first
        patch (*"Unable to read chart being resumed"*), and the fallback to stock
        chartread keeps the flag and fails identically (Knut's log, #148).

        Applied in BOTH modules from one place on purpose. Guided and Manual have
        separate resume checkboxes, and the last time a flag was resolved twice
        the two drifted — every Guided measurement ran with `-N` because a hidden
        control was still being read. One rule, both callers.
        """
        if not ticked:
            return False
        ti1 = getattr(self, "_ti1_path", None)
        if ti1 is None:
            return False
        from workflow.measurement_state import can_resume
        ti1 = Path(ti1)
        ok = can_resume(ti1.with_suffix(".ti3"), ti1.with_suffix(".ti2"))
        if not ok:
            log.info("Refine / resume is ticked, but this run has no measurement "
                     "to resume from — measuring from the start instead.")
        return ok

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
            # NEVER FROM A CONTROL THE USER CANNOT SEE.
            #
            # "Skip initial calibration (-N)" is built here but hidden outright
            # in Guided (`self._nocal_cb.setVisible(False)`, and never shown
            # again) — while its value was still read, still sent, and still
            # remembered between sessions. A stored `measure_no_cal` therefore
            # ran EVERY guided measurement uncalibrated, with nothing on screen
            # to say so and no way to switch it off.
            #
            # That is not a small thing: without its white calibration a
            # ColorMunki's readings drift, and ArgyllCMS's own consistency
            # check throws them out. Knut's beta.148 log is the proof — `-N` on
            # every run from 09:46, `cal_required` never seen again after
            # 08:41, and every single patch rejected as *"Reading is
            # inconsistent"*. Guided does not offer the option, so Guided does
            # not use it.
            disable_initial_cal = False,
            patch_by_patch      = self._resolve_patch_by_patch("guided"),
            resume              = self._resume_has_anything_to_resume(
                self._resume_cb.isChecked()),
            # `shlex.join`, not `" ".join`: `measure_manager` re-splits
            # this with `shlex.split`, so a value containing a space is
            # torn in two on the way back. No option row carries one
            # today, but `data/parameters.yaml` already declares a
            # `-X file.ccmx` row, and a path with a space is the normal
            # case the day that is wired up. `tab_chart` does this
            # round trip correctly already.
            extra_args          = shlex.join(extra_args),
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
            patch_by_patch      = self._resolve_patch_by_patch("manual"),
            resume              = self._resume_has_anything_to_resume(
                self._m_resume_cb.isChecked()),
            # `shlex.join`, not `" ".join`: `measure_manager` re-splits
            # this with `shlex.split`, so a value containing a space is
            # torn in two on the way back. No option row carries one
            # today, but `data/parameters.yaml` already declares a
            # `-X file.ccmx` row, and a path with a space is the normal
            # case the day that is wired up. `tab_chart` does this
            # round trip correctly already.
            extra_args          = shlex.join(extra_args),
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
            # NOT measure_no_cal: `_nocal_cb` is hidden in Guided and
            # `_collect_guided` hard-codes the flag off, so saving its state
            # would write a default no Guided user can see or change — D4's
            # exact shape. Manual's Save as Defaults still stores it below.
            s.set("measure_patch_by_patch",    self._pbp_user_value("guided"))
            s.set("measure_overlay_mode",      self._g_overlay_mode.currentData())
            s.set("measure_only_measured",     self._g_only_measured.isChecked())
            s.set("measure_aim_help",          self._g_aim_help.isChecked())
            s.set("measure_patch_tile",        self._g_patch_tile.isChecked())
            # #134/#130 (Knut, 2026-07-27): this switch was left out, so
            # "Save as Defaults" never kept it and it came back off every time.
            s.set("measure_show_overlay",      self._overlay_cb.isChecked())
            for opt in self._chartread_opts:
                if opt.checkbox:
                    s.set(f"measure_{opt.key}_enabled", opt.checkbox.isChecked())
                if opt.widget is not None:
                    if isinstance(opt.widget, (QSpinBox, QDoubleSpinBox)):
                        s.set(f"measure_{opt.key}_value", opt.widget.value())
                    elif isinstance(opt.widget, QComboBox):
                        s.set(f"measure_{opt.key}_value", opt.widget.currentData())
        else:
            s.set("measure_show_overlay",       self._m_overlay_cb.isChecked())
            s.set("manual2_chartread_instr",    self._m_instr_spin.value())
            s.set("manual2_chartread_bidir_mode", self._m_bidir_combo.currentData())
            s.set("manual2_chartread_bidir_auto", self._m_bidir_auto_cb.isChecked())
            s.set("manual2_chartread_suppress", self._m_suppress_cb.isChecked())
            s.set("manual2_chartread_nocal",    self._m_nocal_cb.isChecked())
            s.set("manual2_chartread_pbp",      self._pbp_user_value("manual"))
            s.set("manual2_overlay_mode",       self._m_overlay_mode.currentData())
            s.set("manual2_only_measured",      self._m_only_measured.isChecked())
            s.set("manual2_aim_help",           self._m_aim_help.isChecked())
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
        self._set_pbp_user_value(
            "guided", bool(s.get("measure_patch_by_patch", False)))
        _gom = self._g_overlay_mode.findData(s.get("measure_overlay_mode", "both"))
        if _gom >= 0:
            self._g_overlay_mode.setCurrentIndex(_gom)
        self._g_only_measured.setChecked(bool(s.get("measure_only_measured", False)))
        # DEFAULTS ON. Basti, 2026-08-30: "on by default first and it should
        # remember what the user set it to then" -- so the stored value wins
        # once there is one, and until then a first-time CR30 user gets the
        # help without having to know the option exists.
        self._g_aim_help.setChecked(bool(s.get("measure_aim_help", True)))
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
        # DELIBERATELY NO HARD RESET for the port spins and the overlay
        # toggle: a control with no saved default keeps what is on screen.
        # Knut, 2026-08-11: *"It is by design that last loaded run type is
        # used when choosing New run. Fall back to that behaviour and keep
        # to the design specification"* (§4a — a New run is seeded from the
        # run you were on, and for this tab the screen IS the seed until the
        # first write files it).
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
        self._set_pbp_user_value(
            "manual", bool(s.get("manual2_chartread_pbp", False)))
        _om = self._m_overlay_mode.findData(s.get("manual2_overlay_mode", "both"))
        if _om >= 0:
            self._m_overlay_mode.setCurrentIndex(_om)
        self._m_only_measured.setChecked(bool(s.get("manual2_only_measured", False)))
        self._m_aim_help.setChecked(bool(s.get("manual2_aim_help", True)))
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
