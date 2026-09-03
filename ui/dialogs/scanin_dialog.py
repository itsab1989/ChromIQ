"""Tools → "Build profile with scanner or camera" — profile a scanner or camera (#98).

Workflow: pick a **measured** ChromIQ chart and a **scan** of the printed chart,
drag the four corners over the patch area (a live grid confirms the fit), and
ChromIQ runs ``scanin`` (manual ``-F`` registration + perspective) to read the
scan against the chart's measured colours, then ``colprof`` to build the scanner
ICC. Multi-page charts get a scan (or several) placed per page; several scans of
a page are averaged, then the pages are combined before profiling. It can also
profile from a standard target the user owns (IT8, ColorChecker, …) via its
Argyll ``.cht`` + the target's own reference file.

Needs the chart's ``.cht`` + ``.cie`` (built by "Create scanner target" / the
measure-tab checkbox); this tool builds them on the fly if they're missing but
the chart was measured. Green (measure/scanner family), ⓘ per option,
non-native pickers, readable helper text in both themes.
"""
from __future__ import annotations

import sys as _sys

from core.stem_paths import artefact

import re
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QVBoxLayout, QWidget)

from core.i18n import tr
from core.logger import get_logger
from core.text_io import read_text
from ui.dialogs.tools_dialogs import (
    _ToolDialogBase, _initial_dir, _remember_dir, neutral_controls_qss)
from ui.scan_grid_marquee import GridSpec, ScanGridMarquee
from ui.styles import SPEC_GREEN
from ui.dialogs.scanin_target_dialog import WHICH_CHART_HELP, WHICH_CHART_CAMERA_NOTE
from ui.dialogs import scanner_colprof
from ui.theme import APPEARANCE_NEUTRAL, accent_for, resolve_mode
from ui.tooltip_button import TooltipButton
from ui.widgets import (CollapsibleGroupBox, ElidingComboBox, NoScrollSpinBox,
                        ValueWidthComboBox, disabled_primary_qss,
                        make_browse_button, primary_hover, primary_label,
                        open_file_dialog)
from workflow.profile_builder import ProfileBuilder, ProfileParams
from workflow.scanin_runner import ScaninParams, ScaninRunner
from workflow.ti3_average import Ti3AverageError, average_scanner_ti3
from workflow.scanin_target import (
    ScaninTargetError, build_scanin_target_from_paths, has_scanner_geometry)
from workflow.standard_targets import (StandardTarget, ensure_user_targets_dir,
                                       grouped_standard_targets,
                                       user_targets_dir)

log = get_logger(__name__)

_TI3_FILTER = "Measured chart (*.ti3);;All files (*)"
# Printer mode reads the chart's device + aim values from its .ti2, so a chart you
# only PRINTED (never measured) is fine — accept either file.
_CHART_FILTER = "Chart you printed (*.ti2);;All files (*)"
_SCAN_FILTER = "Scans (*.tif *.tiff);;All files (*)"
_CHT_FILTER = "Chart recognition (*.cht);;All files (*)"
_REF_FILTER = "Target reference (*.cie *.txt *.ti3 *.cxf);;All files (*)"
# Compact button — a per-widget rule beats the app-wide 28px min-height.
_COMPACT_BTN = "QPushButton { padding: 2px 12px; min-height: 0; font-size: 11px; }"

# Scanner-side capture settings (folded from Knut's VueScan/ArgyllCMS guide).
# Kept as its own key so the large HELP block above stays stable — only this
# short section needs (re-)translating when the wording changes.
SCAN_SETUP_HELP = tr(
    "How to scan the chart for a good profile\n\n"
    "The profile can only be as faithful as the scan, so capture the chart flat "
    "and unaltered:\n\n"
    "• Colour: turn OFF every automatic correction — no colour balance, no "
    "auto-levels or curves, no sharpening, and no scanner ICC profile applied. "
    "(In VueScan: Colour balance = None, curves left at their defaults, "
    "brightness = 1.)\n"
    "• Depth & format: 48-bit RGB (16 bit per channel), saved as an "
    "uncompressed TIFF.\n"
    "• Resolution: 300–600 ppi is plenty for a patch chart. For best quality, "
    "scan higher (e.g. 2400 ppi) and let the software downsample — averaging "
    "pixels lowers noise.\n"
    "• Multiple samples: if your scanner software can average several passes "
    "per scan, turn it on to reduce noise further.\n"
    "• Placement: clean the glass and the chart, lay it flat and square, and "
    "crop to the patch area.\n\n"
    "Scan the same way every time. The profile describes your scanner at these "
    "settings, so changing them later means it no longer fits.")

# Consolidated workflow tips: averaging, multi-page charts, and standard targets.
SCANNING_TIPS_HELP = tr(
    "Getting the best result\n\n"
    "• Average several scans. Scanning the same sheet two or three times and "
    "averaging the reads cancels out the random noise every scanner adds, for a "
    "cleaner profile. Pick your first scan and place its four corners, then use "
    "“Add another scan to average” for each extra scan — each keeps its own "
    "placement, so it's fine if the sheet shifted a little. Pick how they're "
    "combined under “Combine repeated scans by”.\n\n"
    "• Multi-page ChromIQ charts. When a chart spans several pages, a Page "
    "selector appears. Pick and place each page's scan in turn — and you can add "
    "several scans per page too. ChromIQ averages each page's scans, then builds "
    "one profile from all the pages together.\n\n"
    "• A standard target is a single sheet. A bought IT8, ColorChecker or "
    "similar target has no pages (even a two-area target like the Wolf Faust IT8 "
    "is one sheet, read from one scan) — just scan it once, or a few times to "
    "average.")

# Camera profiling — same engine as scanning, so a photo of a target works too.
CAMERA_HELP = tr(
    "Profiling a camera\n\n"
    "This tool works for a digital camera too, not just a scanner — ArgyllCMS "
    "reads camera and scanner targets the same way. Use the “standard target” "
    "mode with a camera target (an X-Rite ColorChecker, IT8, and so on), and "
    "wherever ChromIQ says “scan”, a photo of the target works just the same.\n\n"
    "For a camera the capture matters more than the software:\n\n"
    "• Even light. A camera profile is only valid for the light you shot under, "
    "so light the target flatly and evenly — no glare or hot-spots — under the "
    "lighting you'll actually use (daylight, studio strobe, and so on).\n"
    "• Shoot flat. Photograph raw and convert with a neutral, linear setting — "
    "no creative white balance, tone curve, contrast or sharpening — then export "
    "a plain TIFF. That's the camera version of turning a scanner's correction "
    "off.\n"
    "• Fill the frame square-on, so the target is flat and undistorted.\n"
    "• Keep the profile type on Matrix for a small target like a 24-patch "
    "ColorChecker; a LUT needs a many-patch target.\n\n"
    "The profile applies to that camera under that light. A camera isn't a "
    "colorimeter, so treat it as a very good approximation — great for consistent "
    "studio or repro work, less so across mixed lighting.")


class _AdvancedSection(CollapsibleGroupBox):
    """The window's "Advanced…" disclosure: the app's ordinary collapsible
    section, wearing the checkable API this window (and its tests) already use.

    `CollapsibleGroupBox` toggles on a click in its title band and has no
    signal; the window needs to know, because opening the section changes the
    width the fixed left pane must have. `opened` carries that, and
    `setChecked` / `isChecked` keep the QToolButton vocabulary the call sites
    were written against. Not `toggled`: `QGroupBox` already owns that name for
    its checkable mode, and shadowing a base-class signal is how a slot ends up
    connected to the wrong one.
    """

    #: True when the section is open. Emitted for a click AND for setChecked().
    opened = pyqtSignal(bool)

    def set_collapsed(self, collapsed: bool) -> None:
        was = self.is_collapsed()
        super().set_collapsed(collapsed)
        if self.is_collapsed() != was:
            self.opened.emit(not self.is_collapsed())

    # -- QToolButton-shaped API the window and its tests speak ---------------
    def isChecked(self) -> bool:           # noqa: N802 (Qt vocabulary)
        return not self.is_collapsed()

    def setChecked(self, on: bool) -> None:  # noqa: N802 (Qt vocabulary)
        self.set_collapsed(not bool(on))


def _user_profile_dir() -> Path:
    """The colour-profile folder "Install profile" writes to (Nelson):
    the platform's per-user store, or the user's own choice from
    Preferences → Paths (Knut #108) — one source of truth in platform_paths."""
    from core.platform_paths import icc_install_dir
    return icc_install_dir()


def _load_scan_qimage(path) -> "QImage":
    """Load a scan for the marquee, robust to real scanner output (#108).

    A plain ``QImage(path)`` silently returns null for images whose decoded
    size exceeds Qt's allocation limit (256 MB — a 16-bit A4 scan at 600 dpi
    is over it), which left the marquee empty so the grid could never be
    aligned. Lift the limit; if Qt still can't decode the format, fall back to
    Pillow and convert to 8-bit RGB (the on-screen preview doesn't need more).
    """
    from PyQt6.QtGui import QImageReader
    reader = QImageReader(str(path))
    reader.setAllocationLimit(0)
    img = reader.read()
    if not img.isNull():
        return img
    try:
        from PIL import Image
        from PIL.ImageQt import ImageQt
        with Image.open(path) as im:
            return QImage(ImageQt(im.convert("RGB"))).copy()
    except Exception:  # noqa: BLE001 — the caller shows the empty-marquee state
        log.warning("could not load scan preview %s (Qt: %s)",
                    path, reader.errorString())
        return QImage()


class _ZoomPanImageView(QWidget):
    """Minimal zoom/pan image viewer for the alignment-check result (Knut):
    scroll (or pinch) zooms about the cursor, dragging pans, double-click
    fits the image to the window again."""

    def __init__(self, pixmap, parent=None) -> None:
        super().__init__(parent)
        self._pm = pixmap
        self._scale = None            # None = fit-to-widget
        self._off = [0.0, 0.0]        # top-left of the view in image coords
        self._drag = None
        self.setMouseTracking(True)

    def _fit_scale(self) -> float:
        if self._pm.width() == 0 or self._pm.height() == 0:
            return 1.0
        return min(self.width() / self._pm.width(),
                   self.height() / self._pm.height())

    def paintEvent(self, _ev) -> None:  # noqa: N802
        from PyQt6.QtGui import QPainter
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().window())
        s = self._scale or self._fit_scale()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(-self._off[0] * s, -self._off[1] * s)
        p.scale(s, s)
        p.drawPixmap(0, 0, self._pm)
        p.end()

    def wheelEvent(self, ev) -> None:  # noqa: N802
        s = self._scale or self._fit_scale()
        factor = 1.0015 ** ev.angleDelta().y()
        new = max(self._fit_scale() * 0.5, min(8.0, s * factor))
        # zoom about the cursor: keep the image point under it fixed
        pos = ev.position()
        ix = self._off[0] + pos.x() / s
        iy = self._off[1] + pos.y() / s
        self._scale = new
        self._off = [ix - pos.x() / new, iy - pos.y() / new]
        self.update()

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        self._drag = (ev.position(), list(self._off))

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        if self._drag is None:
            return
        s = self._scale or self._fit_scale()
        start, off0 = self._drag
        d = ev.position() - start
        self._off = [off0[0] - d.x() / s, off0[1] - d.y() / s]
        self.update()

    def mouseReleaseEvent(self, _ev) -> None:  # noqa: N802
        self._drag = None

    def mouseDoubleClickEvent(self, _ev) -> None:  # noqa: N802
        self._scale = None
        self._off = [0.0, 0.0]
        self.update()


def _chart_base(ti3: Path) -> Path:
    stem = ti3.stem
    if stem.endswith("-verify"):
        stem = stem[: -len("-verify")]
    return ti3.with_name(stem)


_PROFCHECK_RE = re.compile(
    r"Profile check complete, peak err = ([\d.]+), avg err = ([\d.]+)")


def _plain_id(sid: str) -> str:
    """``H01`` → ``H1``: scanin zero-pads sample IDs on output; the chart's
    ``.ti2`` rows and layout locs don't."""
    m = re.match(r"([A-Za-z]+)0*(\d+)$", sid)
    return (m.group(1) + m.group(2)) if m else sid


def page_ids_from_cht(cht: Path) -> set[str] | None:
    """The (plain) sample IDs of the patches a page's ``.cht`` reads — the
    subset of the chart that one scan can legitimately fill. ``None`` if the
    file can't be parsed."""
    from workflow.cht_parser import ChtParseError, parse_cht
    try:
        geom = parse_cht(read_text(cht, lenient=True))
    except (OSError, ChtParseError):
        return None
    return {_plain_id(b.name) for b in geom.patches} or None


def page_reference_agreement(ti3: Path, ti2: Path,
                             ids: set[str] | None = None) -> float | None:
    """Printer mode's misalignment signal (#108): Spearman rank agreement
    between what the scanner measured (through its profile) and the chart's
    aim values, optionally restricted to the *ids* one page fills.

    Replaces the retired ΔE-vs-aims share check, which was structurally wrong
    for real prints: a printer can't REACH the chart's ideal aims (gamut
    compression, paper white), so saturated patches sit ΔE 20–40 away even
    when everything is perfect — Knut's real aligned scans flagged 100 % on
    every page while colprof's own fit was excellent (peak 2.9). Print
    response is monotone, so RANK agreement survives it: his real aligned
    pages measure ≈ 0.95, scrambled reads ≈ 0. One methodology across
    scanner, printer and standard modes, as he asked. ``None`` when the
    files can't be parsed or too few patches match."""
    from workflow.ti3_analysis import parse_ti3
    got = parse_ti3(ti3)
    aim = parse_ti3(ti2)
    loc_of = {_plain_id(s): _plain_id(l.strip('"'))
              for s, l in zip(aim.sample_ids, aim.sample_locs)}
    aim_y = {_plain_id(s): y for s, (_x, y, _z) in zip(aim.sample_ids, aim.xyz)}
    pairs = []
    for sid, (_x, y, _z) in zip(got.sample_ids, got.xyz):
        sid = _plain_id(sid)
        if ids is not None and sid not in ids and loc_of.get(sid) not in ids:
            continue
        a = aim_y.get(sid)
        if a is not None:
            pairs.append((y, a))
    if len(pairs) < 8:
        return None

    def _ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = float(pos)
        return r

    ra = _ranks([p_[0] for p_ in pairs])
    rb = _ranks([p_[1] for p_ in pairs])
    n = len(ra)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((a - ma) * (b - mb) for a, b in zip(ra, rb))
    den = (sum((a - ma) ** 2 for a in ra) * sum((b - mb) ** 2 for b in rb)) ** 0.5
    return num / den if den else None


def placement_score(read_by_id: dict[str, float],
                    expected_by_id: dict[str, float]) -> float | None:
    """How badly the read values disagree with being ONE smooth response of
    the expected values — the placement objective of the Check-alignment
    probes (Knut, #108). A monotone (isotonic) curve is fitted through
    (expected, read); every patch's residual from that curve is computed,
    and the 95th-percentile |residual| (normalised by the read range) is
    returned. A perfectly placed grid leaves only scanner noise (≈0.05 on
    Knut's real Wolf Faust scan); sampling areas that cross into
    neighbouring patches break the single-response assumption and the
    score climbs steeply (his scan: 0.073 at a 15 % offset, 0.158 at 25 %,
    0.315 at 40 %). The high percentile implements his "worst value rules"
    without letting one dust speck decide the verdict."""
    ids = [i for i in read_by_id if i in expected_by_id]
    if len(ids) < 16:
        return None
    pairs = sorted((expected_by_id[i], read_by_id[i]) for i in ids)
    ys = [l for _e, l in pairs]

    # Isotonic regression (pool adjacent violators), weights = pool sizes.
    pools: list[list[float]] = []          # [mean, count]
    for v in ys:
        pools.append([v, 1.0])
        while len(pools) > 1 and pools[-2][0] > pools[-1][0]:
            v2, n2 = pools.pop()
            v1, n1 = pools.pop()
            pools.append([(v1 * n1 + v2 * n2) / (n1 + n2), n1 + n2])
    fit: list[float] = []
    for mean, count in pools:
        fit.extend([mean] * int(count))
    rng = (max(ys) - min(ys)) or 1.0
    res = sorted(abs(a - b) / rng for a, b in zip(ys, fit))
    return res[min(len(res) - 1, int(len(res) * 0.95))]


def locally_misaligned_groups(read_by_id: dict[str, float],
                              expected_by_id: dict[str, float],
                              z: float = 3.0) -> list[str]:
    """Knut's row/column pattern idea (#108), in the form that survives
    randomised charts: rank both value sets over the whole page (removing
    scanner/printer response to first order), take each patch's rank
    displacement |expected − read|, and flag a whole ROW or COLUMN whose
    mean displacement sits ``z`` standard errors above the page mean — a
    grid edge sitting a full cell off drags its entire line of patches
    onto the neighbours' values while the rest of the page stays put.

    Validated on Knut's own 3-page chart: 0 false alarms in 300 noisy
    aligned trials, 100 % detection of his mid-handle squeeze (top row
    reading the row below). Sub-⅔-of-a-patch blends stay invisible here
    (their values are individually plausible) — the post-build self-check
    covers those. His literal per-row own-pattern matching can't work on a
    randomised chart: 7-patch rows gave a 98.5 % false-alarm rate, because
    randomisation removes the row uniqueness the comparison needs.

    Groups are parsed from the sample IDs (letters = column/strip, digits
    = row); groups need ≥ 4 members and the page ≥ 4 groups to be judged.
    Returns human-readable labels like ``"row 3"`` / ``"column H"``."""
    import statistics
    ids = [i for i in read_by_id if i in expected_by_id]
    if len(ids) < 16:
        return []

    def _ranks(vals: list[float]) -> list[int]:
        order = sorted(range(len(vals)), key=lambda k: vals[k])
        r = [0] * len(vals)
        for pos, k in enumerate(order):
            r[k] = pos
        return r

    er = dict(zip(ids, _ranks([expected_by_id[i] for i in ids])))
    rr = dict(zip(ids, _ranks([read_by_id[i] for i in ids])))
    disp = {i: abs(er[i] - rr[i]) for i in ids}
    mean = statistics.mean(disp.values())
    sd = statistics.pstdev(disp.values()) or 1.0
    rows: dict[str, list[str]] = {}
    cols: dict[str, list[str]] = {}
    for i in ids:
        m = re.match(r"([A-Za-z]+)0*(\d+)$", i)
        if not m:
            continue
        cols.setdefault(m.group(1), []).append(i)
        rows.setdefault(m.group(2), []).append(i)
    def _key_parts(i: str) -> tuple[str, str]:
        m = re.match(r"([A-Za-z]+)0*(\d+)$", i)
        return (m.group(1), m.group(2)) if m else ("", "")

    flagged: list[str] = []
    for axis, (label, groups) in enumerate(
            ((tr("row {n}"), rows), (tr("column {n}"), cols))):
        if len(groups) < 4:
            continue
        # Neighbour order along this axis: rows by number, columns by letter.
        keys = sorted(groups, key=(lambda k: int(k)) if axis == 0
                      else (lambda k: (len(k), k)))
        for pos, key in enumerate(keys):
            members = groups[key]
            if len(members) < 4:
                continue
            own_d = statistics.mean(disp[i] for i in members)
            if own_d <= mean + z * sd / (len(members) ** 0.5):
                continue
            # Confirmation gate (Knut's Wolf Faust / LaserSoft false alarms,
            # #108): structured targets group COLOUR FAMILIES into rows and
            # columns, so a scanner's hue-dependent response displaces a whole
            # family coherently — mimicking a shifted line. The tell of a
            # TRULY shifted line is where it lands: its read ranks sit ON a
            # neighbouring line's expected ranks (distance ≈ noise), while a
            # response-shifted family lands BETWEEN lines. Only flag when the
            # neighbour explains the reads far better than the line itself
            # (validated: 0 % false alarms on Knut's Wolf Faust reference with
            # a hue-dependent response, 100 % detection of his engine-chart
            # squeezes, 93 % of single-line shifts on the structured target —
            # the remainder lands in the post-build self-check).
            # _key_parts is (letters, digits); rows are keyed by digits so
            # their cross key is the LETTERS part (index 0) and vice versa.
            cross = axis
            by_cross = {_key_parts(i)[cross]: i for i in members}
            for npos in (pos - 1, pos + 1):
                if not 0 <= npos < len(keys):
                    continue
                nb = {_key_parts(i)[cross]: i for i in groups[keys[npos]]}
                shared = sorted(set(by_cross) & set(nb))
                if len(shared) < 4:
                    continue
                nb_d = statistics.mean(
                    abs(rr[by_cross[c]] - er[nb[c]]) for c in shared)
                if nb_d < 0.4 * own_d:
                    flagged.append(label.format(n=key))
                    break
    return flagged


def scan_reference_correlation(ti3: Path) -> float | None:
    """Spearman rank correlation between the scan's RGB luminance and the
    reference Y in a scanner-mode ``.ti3`` (RGB = what the scanner saw, XYZ =
    the chart's known colours). Scanner response is monotone, so an aligned
    read correlates strongly (a real measured ChromIQ chart lands ≈ 0.9; a
    synthetic render ≈ 1.0) even on an unprofiled scanner; a misplaced grid
    scrambles the pairing toward 0 (Knut's flipped pages: 0.00–0.33, #108).
    ``None`` when the file can't be parsed or is too small to judge."""
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    try:
        t = parse_ti3(ti3)
    except (OSError, Ti3ParseError, ValueError):
        return None
    if t.rgb is None or len(t.rgb) < 8:
        return None
    lum = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in t.rgb]
    y = [v for _x, v, _z in t.xyz]

    def _ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = float(pos)
        return r

    ra, rb = _ranks(lum), _ranks(y)
    n = len(ra)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((a - ma) * (b - mb) for a, b in zip(ra, rb))
    den = (sum((a - ma) ** 2 for a in ra) * sum((b - mb) ** 2 for b in rb)) ** 0.5
    return num / den if den else None


def _remove_empty_icc(icc: Path) -> None:
    """Take away the EMPTY .icc a failed colprof leaves behind.

    colprof creates the output file before it decides it cannot build the
    profile, so a failed run left a 0-byte `.icc` sitting where a real profile
    would be — with exactly the name the user typed, beside the real profiles
    in the same folder. Measured: a failed printer build left
    `Review4 printer from scan.icc`, 0 bytes, next to a valid 27 KB one.

    ONLY at exactly zero bytes. That is unambiguous — no profile of any kind is
    empty — and it can destroy nothing: if a file of the user's had that name,
    colprof truncated it when it opened it for writing, long before this runs.
    """
    try:
        if icc.exists() and icc.stat().st_size == 0:
            icc.unlink()
    except OSError:                       # a read-only volume is not our problem
        log.warning("could not remove the empty %s left by a failed build", icc)


class ScannerProfileDialog(_ToolDialogBase):
    TOOL_KEY    = "scanner_profile"
    TITLE       = tr("Build profile with scanner or camera")
    EYEBROW     = tr("MEASURE · SCANNER / CAMERA PROFILE")
    ACCENT      = SPEC_GREEN
    RUN_LABEL   = tr("Build profile with scanner or camera")
    BUSY_BAR_IDLE_LABEL = tr("Ready")   # always-visible bar; animates while running
    # The width this window OPENS at. It is not the floor: the floor is read
    # off the two panes once they are real (`_refresh_min_width`), and is
    # smaller — 1048 px in English, 1186 in Spanish, the worst of the twelve.
    MIN_WIDTH   = 1240
    SCROLLABLE_CONTENT = True    # tall (mode toggle + inputs + marquee + averaging)

    # Prepended OUTSIDE the main tr() key — appending inside would orphan the
    # existing help key and its translations (the WHICH_CHART_HELP lesson).
    HELP = tr(
        "A scanner or camera is never as accurate as a real spectrophotometer "
        "— but it lets you build a genuinely useful printer profile with no "
        "spectro at all, and a fine scanner/camera profile for your device."
    ) + "\n\n" + tr(
        "Builds an ICC colour profile for a scanner or a digital camera, from a "
        "target whose true colours are known. Once built, the profile tells any "
        "colour-managed program how your device really sees colour, so scans and "
        "photos come out accurate instead of dull or colour-cast.\n\n"
        "There are two ways to provide the target — choose one at the top of the "
        "window:\n\n"
        "• A chart you made in ChromIQ. Print and measure a chart as usual and "
        "keep its scanner files (.cht + .cie) — tick 'Also save "
        "scanner-profiling files' after measuring, or use Tools ▸ Create scanner "
        "or camera target. Nothing extra to buy: ChromIQ already knows every "
        "patch's real colour.\n"
        "• A standard target you own. A bought reflective target such as an IT8 "
        "(for example Wolf Faust), an X-Rite ColorChecker or a LaserSoft target. "
        "Pick its type from the list and load the reference data file that came "
        "with it (.cie / .txt — or a .ti3 you measured from it yourself).\n\n"
        "Then capture the target on the device you want to profile — scan it, or "
        "for a camera photograph it — as a plain RGB TIFF, with the device's own "
        "colour correction turned OFF. When scanning, use 600 dpi or more — "
        "1200 dpi is preferred; 300 dpi is too coarse for clean patch reads. "
        "Load it here, drag the four corners over "
        "the patch area until the green grid sits on the real patches, and click "
        "Build profile with scanner or camera. ChromIQ compares how your device saw "
        "each patch against the true colours and writes the ICC profile next to "
        "your capture.\n\n"
        "The sections below cover, in order: the best way to capture the target, "
        "averaging several captures for less noise, profiling a camera, and "
        "which target to use.\n\n"
        "───────────────\n"
        "Using your profile\n\n"
        "The profile makes your scans or photos come out accurate — great for "
        "digitising prints, artwork and photos, or for repeatable studio and "
        "repro work, so the result matches the original.\n\n"
        "Two common ways to use it:\n\n"
        "• In your scanner software (VueScan, SilverFast, Epson Scan, etc.): "
        "set this .icc file as the scanner's input / ICC profile, and choose a "
        "working space such as sRGB or Adobe RGB as the output. New scans are "
        "then corrected automatically.\n\n"
        "• In Photoshop or another editor (this is also the route for camera "
        "photos): open the scan or photo — captured with correction OFF — then "
        "Assign Profile ▸ this profile (so the app knows how your device saw the "
        "colours), and Convert to Profile ▸ your working space (e.g. sRGB or "
        "Adobe RGB). The colours now match the original.\n\n"
        "Good to know:\n"
        "• The profile is specific to this device and the settings you captured "
        "with. Keep the scanner's auto-correction off — or the camera's lighting "
        "and raw settings the same — exactly as when you captured the target, or "
        "the profile won't fit.\n"
        "• A scanner profile is most accurate for media like the paper you "
        "profiled; a camera profile is tied to the light you shot under.\n"
        "• The profile characterises the device — it does not sharpen or "
        "retouch; it just makes the colours faithful."
    ) + "\n\n───────────────\n" + SCANNING_TIPS_HELP \
      + "\n\n───────────────\n" + SCAN_SETUP_HELP \
      + "\n\n───────────────\n" + CAMERA_HELP \
      + "\n\n───────────────\n" + WHICH_CHART_HELP \
      + "\n\n───────────────\n" + WHICH_CHART_CAMERA_NOTE
    DESCRIPTION = tr(
        "Turn a scan or photo of a target into a colour profile for your scanner "
        "or camera — or, from a scan of a chart you printed, a profile for your "
        "printer (using the scanner as the measuring instrument).")

    def __init__(self, runner, settings, parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._runner = runner
        self._scanin = ScaninRunner(runner)
        self._profiler = ProfileBuilder(runner)
        # Scanner colprof settings (#121, Knut): remembered main + advanced values,
        # stored PER CONTEXT — a printer profile, a scanner profile from a ChromIQ
        # chart, and a scanner profile from a standard target each keep their own
        # type / quality / description / Advanced choices, so toggling between them
        # loads the right set (Knut). Persisted to QSettings so Restore-factory-
        # defaults clears them. `_adv_vals` always mirrors the ACTIVE context.
        self._ctx_cfg: dict[str, dict] = self._load_ctx_configs()
        self._active_ctx: str = "chart"
        self._adv_vals: dict = {}
        self._ti3: Path | None = None
        self._layout: dict | None = None
        self._printer_scan_profile: Path | None = None   # scanner ICC for printer mode
        self._chart_measured = False   # loaded chart has a real .ti3 (not just .ti2)
        self._align_warnings: list[str] = []   # per-page misalignment findings
        # Findings about the DATA rather than the grid — review 5. Kept
        # apart from the alignment ones because they are a different
        # question with a different answer, and the two windows say so.
        self._read_findings: list[tuple[str, str]] = []
        self._run_diags: list[Path] = []       # diagnostic images this run writes
        self._chart_reject_reason: str | None = None  # why the last pick failed (#101)
        # Bring-your-own-.cht (#105): a printer-mode chart without channels.json
        # waits here for the user to pick printtarg's per-page .cht files.
        self._byo_awaiting = False
        self._byo_base: Path | None = None
        self._byo_ref: Path | None = None
        self._pages: list[int] = []
        self._page = 0
        # Per page, a list of "shots" — one or more scans of the same page, each
        # with its own corner placement — averaged before profiling (#98 ask 1c).
        self._shots: dict[int, list[dict]] = {}
        self._shot_idx = 0
        self._jobs: list[dict] = []
        # Standard-target (own IT8 / ColorChecker) mode state. A target can be
        # multi-page (the ISO 12641-2 3-page set): _std_chts holds one .cht per
        # page, locked to it, while _std_cht / _std_grid always mirror the page
        # currently shown (self._page) so the per-page-agnostic code below is
        # unchanged. _std_ref is the one reference shared by all pages.
        self._std_chts: list[Path] = []
        self._std_cht: Path | None = None
        self._std_ref: Path | None = None
        self._std_grid = None
        self._convert_tmp: Path | None = None   # scratch for converted references
        self._ref_converted_note = ""           # set when a .cxf/.txt was converted
        # THE HINT LINES UNDER EVERY FIELD, and a fold with room for two
        # answers gave the light-grey appearance the dark theme's `#b8b8b8` —
        # 1.53:1 on the Neutral dialog, which is not a faint hint, it is text
        # you cannot see. A perfect grey, so the hue census scores it zero, and
        # this is a Tools dialog nothing had opened in the first place.
        from ui.theme import by_mode
        from ui import neutral_styles as _n
        self._hint = by_mode("#4a4a4a", "#b8b8b8", _n.NM_TEXT_FAINT,
                             resolve_mode(settings.get("appearance", "auto")))
        # `_build_inputs` fills one column; `_build_two_panel_layout` then deals
        # it into the window's two panes. It is one pass, not a rebuild: the
        # same layout items are re-parented, so every widget, style and signal
        # built above is untouched.
        self._build_inputs()
        self._build_two_panel_layout()
        self._run_btn.setObjectName("primary")
        # "Reveal profile" — shown after a successful build so the .icc is easy to
        # find (ChromIQ doesn't auto-install scanner profiles). Hidden until then.
        self._last_profile: Path | None = None
        self._reveal_btn = self._button_box.addButton(
            tr("Reveal profile"), QDialogButtonBox.ButtonRole.ActionRole)
        self._reveal_btn.setToolTip(tr(
            "Open the folder containing the scanner/camera profile just built, so "
            "you can install it as your device's input profile."))
        self._reveal_btn.clicked.connect(self._reveal_profile)
        self._reveal_btn.setVisible(False)
        # "Install profile" — copy the built .icc into the user's colour-profile
        # folder so apps can pick it from their profile lists (Nelson).
        self._install_btn = self._button_box.addButton(
            tr("Install profile"), QDialogButtonBox.ButtonRole.ActionRole)
        self._install_btn.setToolTip(tr(
            "Copy the profile just built into your user colour-profile folder "
            "({dir}), where colour-managed programs look for profiles. Restart "
            "a program to see it in its lists.").format(
                dir=str(_user_profile_dir())))
        self._install_btn.clicked.connect(self._install_profile)
        self._install_btn.setVisible(False)
        self.setStyleSheet(self.styleSheet() + neutral_controls_qss(SPEC_GREEN))
        self._style_primary_button()
        self._refresh()

    def _reveal_profile(self) -> None:
        if self._last_profile is None:
            return
        from core.preset_store import reveal_in_file_manager
        reveal_in_file_manager(self._last_profile.parent)

    def _install_profile(self) -> None:
        if self._last_profile is None:
            return
        import shutil
        dest_dir = _user_profile_dir()
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / self._last_profile.name
            shutil.copy2(self._last_profile, dest)
        except OSError as exc:
            self._log.appendPlainText(
                f"[ERROR] {tr('Installing the profile failed: {e}').format(e=exc)}")
            return
        self._log.appendPlainText(
            tr("[OK] Profile installed: {p}").format(p=dest))
        self._log.appendPlainText(tr(
            "Colour-managed programs list it after they restart."))

    def _style_primary_button(self) -> None:
        mode = resolve_mode(self._settings.get("appearance", "auto"))
        c = accent_for(SPEC_GREEN, mode)
        hover = primary_hover(c, mode, 0.86)
        label = primary_label(mode)
        self._run_btn.setStyleSheet(
            f"QPushButton {{ background:{c}; border:1px solid {c}; color:{label};"
            f" font-weight:700; }}"
            f"QPushButton:hover {{ background:{hover}; border-color:{hover}; }}"
            + disabled_primary_qss(c, mode))

    def _tip(self, title: str, body: str) -> TooltipButton:
        return TooltipButton(title, body, self, min_width=500, color=SPEC_GREEN)

    # ------------------------------------------------------------------ UI
    def _labelled(self, text: str, tip_t: str, tip_b: str):
        h = QHBoxLayout()
        h.addWidget(QLabel(text, self))
        h.addStretch(1)
        h.addWidget(self._tip(tip_t, tip_b), 0, Qt.AlignmentFlag.AlignVCenter)
        return h

    def _hint_label(self, text: str) -> QLabel:
        lbl = QLabel(text, self)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{self._hint}; font-size:12px;")
        return lbl

    def _standard_mode(self) -> bool:
        return self._mode_standard.isChecked()

    def _target_label(self, t: StandardTarget) -> str:
        """Combo label for a standard target, annotated with its patch count so
        the size is visible before picking (Knut). A multi-page set shows its
        per-page count."""
        if t.is_multipage:
            counts = t.patch_counts
            total = sum(counts)
            # Show the whole-chart total too (Knut, #119): a per-page-only count
            # hid how big the set really is next to single-page targets.
            if len(set(counts)) == 1:
                return tr("{name}  ·  {pages} pages × {n} patches "
                          "= {total} patches").format(
                    name=t.name, pages=t.n_pages, n=counts[0], total=total)
            return tr("{name}  ·  {pages} pages ({counts} patches) "
                      "= {total} patches").format(
                name=t.name, pages=t.n_pages, total=total,
                counts=" + ".join(str(c) for c in counts))
        n = t.patch_counts[0] if t.patch_counts else 0
        if n <= 0:
            return t.name
        return tr("{name}  ·  {n} patches").format(name=t.name, n=n)

    def _build_mode_selector(self, form) -> None:
        row = QHBoxLayout()
        # Name the choice the radios make — without it the two options read as
        # floating statements (Knut, #108 follow-up).
        row.addWidget(QLabel(tr("Create profile using:"), self))
        self._mode_group = QButtonGroup(self)
        self._mode_chromiq = QRadioButton(tr("A chart I made in ChromIQ"), self)
        self._mode_standard = QRadioButton(
            tr("A standard target I own (IT8, ColorChecker…)"), self)
        self._mode_chromiq.setChecked(True)
        self._mode_group.addButton(self._mode_chromiq)
        self._mode_group.addButton(self._mode_standard)
        tip = self._tip(
            tr("Which source?"),
            tr("Two ways to profile a scanner:\n\n"
            "• A chart I made in ChromIQ — print and measure a chart, then scan "
            "the print. ChromIQ already knows its exact patch colours.\n\n"
            "• A standard target I own — a bought reflective target such as a "
            "Wolf Faust IT8, LaserSoft or X-Rite ColorChecker. Pick its type and "
            "the reference data file that came with your target (.cie / .txt), "
            "then scan it. No printing or measuring needed."))
        # The two options go on their own lines UNDER the question rather than
        # trailing after it. On one line the row has to be as wide as the label
        # plus BOTH options — 717 px in German — and it sits in the fixed-width
        # left pane, so that one row set the pane's width. Stacked it is only as
        # wide as the longer single option: 379 px in Russian, the worst of the
        # twelve. The pane is fixed, so nothing here has to reflow as the window
        # is resized; two lines from the start is the whole of it.
        row.addStretch(1)
        row.addWidget(tip, 0, Qt.AlignmentFlag.AlignVCenter)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        col.addLayout(row)
        for _r in (self._mode_chromiq, self._mode_standard):
            line = QHBoxLayout()
            line.setContentsMargins(0, 0, 0, 0)
            # Indent the options under the question that names them, the way a
            # list sits under its heading.
            line.addSpacing(14)
            line.addWidget(_r)
            line.addStretch(1)
            col.addLayout(line)
        form.addLayout(col)
        self._mode_chromiq.toggled.connect(self._on_mode_changed)

    def _build_chromiq_inputs(self, form) -> None:
        self._chromiq_box = QWidget(self)
        v = QVBoxLayout(self._chromiq_box)
        v.setContentsMargins(0, 0, 0, 0)
        # The printer-mode switch sits FIRST: it changes the labels and fields
        # below it (".ti3" vs ".ti2", the .cht row, the scanner profile), so it
        # must be seen before them (Knut, #108).
        # --- Printer-profile mode: use the scanner as the measuring instrument ---
        self._printer_cb = QCheckBox(
            tr("Profile my printer from this scan (scanner as the instrument)"), self)
        # Help lives only behind the ⓘ (click to open) — no hover tooltip on the
        # checkbox itself.
        _pr_help = tr(
            "Turn this on to build a profile for your PRINTER from this scan — using "
            "your flat-bed scanner in place of a spectrophotometer — instead of a "
            "profile for the scanner itself.\n\n"
            "How it works: you print one of your own ChromIQ charts, scan the print, "
            "and ChromIQ reads the patches and measures their colour through a "
            "scanner profile you made earlier. That gives colprof what it needs to "
            "build a printer profile — no spectrophotometer required.\n\n"
            "What you need first: a profile for THIS scanner. Build one in the normal "
            "scanner mode from a bought target (an IT8 or LaserSoft sheet). The "
            "printer profile is only as good as that scanner profile, so make a solid "
            "one first — and note the chicken-and-egg: profile the scanner off a "
            "bought target, then use it to profile the printer.\n\n"
            "Honest expectations: a scanner-based printer profile is great for "
            "clearing colour casts and making everyday prints look better, but it "
            "won't match a profile made with a real spectrophotometer. For critical "
            "or proofing work, a spectro is still the way.\n\n"
            "Good to know: a printer profile and a scanner profile are different "
            "things, so this window keeps their settings apart. Turning this on or "
            "off switches the profile type, quality, description and Advanced "
            "options to the ones you last used for that kind of profile — your "
            "printer choices and your scanner choices never overwrite each other.")
        self._printer_cb.toggled.connect(self._on_printer_toggled)
        # An always-visible ⓘ next to the checkbox opens the help on click.
        _pr_row = QHBoxLayout()
        _pr_row.addWidget(self._printer_cb)
        _pr_row.addStretch(1)
        _pr_row.addWidget(self._tip(tr("Printer profile from a scan"), _pr_help),
                          0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(_pr_row)

        self._printer_box = QWidget(self)
        pv = QVBoxLayout(self._printer_box)
        # Flush with the other rows — the old 22px indent left the label and
        # a shorter field floating right of everything else (Basti, #108).
        pv.setContentsMargins(0, 0, 0, 2)
        # Same labelled-field pattern as the other rows: an always-visible ⓘ that
        # carries the extensive help (a plain hover tooltip left no visible cue).
        pv.addLayout(self._labelled(
            tr("Scanner profile (.icc):"), tr("Scanner profile"),
            tr("The profile for THIS scanner that ChromIQ uses to turn the scanned "
            "colours into real, measured colour — the step that makes the printer "
            "profile trustworthy.\n\n"
            "You built this earlier in the normal scanner mode: scan a bought target "
            "(an IT8 or LaserSoft sheet), press Build, and you get a scanner .icc. "
            "Pick that file here.\n\n"
            "Without it, the scan would be raw scanner colour — carrying the "
            "scanner's own cast — and the printer profile would come out wrong. "
            "That's why it's required for this mode.")))
        prow = QHBoxLayout()
        self._printer_prof_field = QLineEdit(self)
        self._printer_prof_field.setReadOnly(True)
        self._printer_prof_field.setPlaceholderText(
            tr("Pick the scanner profile you built earlier…"))
        prow.addWidget(self._printer_prof_field, 1)
        pb = make_browse_button(self, tr("Browse…"), icon="folder_measure")
        pb.clicked.connect(self._pick_scanner_profile)
        prow.addWidget(pb)
        pv.addLayout(prow)
        self._printer_box.setVisible(False)
        v.addWidget(self._printer_box)

        _chart_row = QHBoxLayout()
        self._chart_label = QLabel(tr("Measured chart (.ti3):"), self)
        _chart_row.addWidget(self._chart_label)
        _chart_row.addStretch(1)
        _chart_row.addWidget(self._tip(
            tr("Which chart to read"),
            tr("Which chart your scan is of.\n\n"
            "• For a scanner or camera profile — pick a chart you have already "
            "MEASURED (its .ti3). ChromIQ compares the chart's known, measured "
            "colours with how your device saw them, and builds the profile from the "
            "difference.\n\n"
            "• For a printer profile (the “Profile my printer from this scan” tick "
            "below) — you can pick a chart you simply PRINTED, even if you never "
            "measured it. Pick its .ti2 — the file ChromIQ wrote when it created the "
            "chart, holding the exact colour values it sent to the printer. This time "
            "the scanner does the measuring, so no spectrophotometer reading is "
            "needed.\n\n"
            "Both files live in the chart's own folder, next to the chart image."),
            ), 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(_chart_row)
        row = QHBoxLayout()
        self._ti3_field = QLineEdit(self)
        self._ti3_field.setReadOnly(True)
        self._ti3_field.setPlaceholderText(tr("Pick the measured chart (.ti3)…"))
        row.addWidget(self._ti3_field, 1)
        b = make_browse_button(self, tr("Browse…"), icon="folder_measure")
        b.clicked.connect(self._pick_chart)
        row.addWidget(b)
        v.addLayout(row)
        self._chart_note = self._hint_label("")
        v.addWidget(self._chart_note)

        # Chart geometry (.cht) — printer mode only (#105). ChromIQ charts carry
        # their geometry in channels.json; a chart made outside ChromIQ (e.g. a
        # manual `printtarg -s` run) instead supplies printtarg's own per-page
        # .cht files here.
        self._byo_row_w = QWidget(self)
        _byo_v = QVBoxLayout(self._byo_row_w)
        _byo_v.setContentsMargins(0, 0, 0, 0)
        _byo_head = QHBoxLayout()
        _byo_head.addWidget(QLabel(tr("Chart geometry (.cht):"), self))
        _byo_head.addStretch(1)
        _byo_head.addWidget(self._tip(
            tr("Chart geometry (.cht)"),
            tr("Where ChromIQ learns the exact position of every patch on the "
               "printed sheet.\n\n"
               "For a chart made in ChromIQ there's nothing to do — the "
               "geometry is stored with the chart (its .channels.json), and "
               "this row just says so.\n\n"
               "For a chart you made outside ChromIQ (for example with "
               "printtarg on the command line), pick the .cht files that "
               "printtarg wrote next to your chart — one per page, e.g. "
               "chart_01.cht … chart_05.cht. Select all pages in one go. "
               "ChromIQ checks that the boxes match the chart's .ti2 exactly, "
               "so a wrong or missing page is caught before anything is "
               "read.")), 0, Qt.AlignmentFlag.AlignVCenter)
        _byo_v.addLayout(_byo_head)
        _byo_row = QHBoxLayout()
        self._byo_field = QLineEdit(self)
        self._byo_field.setReadOnly(True)
        self._byo_field.setPlaceholderText(
            tr("provided by the chart (.channels.json)"))
        _byo_row.addWidget(self._byo_field, 1)
        self._byo_btn = make_browse_button(self, tr("Browse…"),
                                           icon="folder_measure")
        self._byo_btn.clicked.connect(self._pick_byo_cht)
        _byo_row.addWidget(self._byo_btn)
        _byo_v.addLayout(_byo_row)
        self._byo_row_w.setVisible(False)          # printer mode only
        v.addWidget(self._byo_row_w)

        # Page selector (multi-page charts only)
        self._page_row = QHBoxLayout()
        self._page_row.setContentsMargins(0, 0, 0, 0)
        self._page_row.addWidget(QLabel(tr("Page:"), self))
        self._page_combo = ElidingComboBox(self)
        self._page_combo.currentIndexChanged.connect(self._on_page_changed)
        self._page_row.addWidget(self._page_combo)
        # Every page needs its own capture — say so, and count what's still
        # missing (Knut, #108).
        self._page_hint = self._hint_label("")
        self._page_row.addWidget(self._page_hint)
        self._page_row.addStretch(1)
        self._page_widget = QWidget(self)
        self._page_widget.setLayout(self._page_row)
        self._page_widget.setVisible(False)
        # Added to the shared form in _build_inputs, directly above the scan
        # field — picking a page changes which scan is shown, so the two belong
        # together (Knut, #108).

        form.addWidget(self._chromiq_box)

    def _build_standard_inputs(self, form) -> None:
        self._standard_box = QWidget(self)
        v = QVBoxLayout(self._standard_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addLayout(self._labelled(
            tr("Target type:"), tr("Target type"),
            tr("Pick the target you're holding. The list is every standard "
            "scanner target ArgyllCMS knows how to read — Wolf Faust and other "
            "IT8 charts, LaserSoft, the X-Rite ColorCheckers, and more. Choosing "
            "the right one lets ChromIQ lay its reading grid exactly over your "
            "target's patches.\n\n"
            "If your target isn't in the list, choose “Other…” and point ChromIQ "
            "at its own layout file (a .cht that came with the target or from "
            "ArgyllCMS).\n\n"
            "Want to look at — or fine-tune — a target's layout file? Every "
            "target's .cht sits in the “scanner-test-targets” folder inside "
            "your ChromIQ output folder, put there for exactly this purpose. "
            "Edit the file there (or copy your own over it, keeping the same "
            "file name) and ChromIQ uses your version instead of its built-in "
            "copy. If a file goes missing, ChromIQ places a fresh copy the "
            "next time this window opens — your edited files are never "
            "overwritten.")))
        trow = QHBoxLayout()
        self._target_combo = ValueWidthComboBox(self)
        # Every standard target, keyed so a multi-page set (three ISO 12641-2
        # pages folded into one) can carry all its page .cht files. The label
        # shows each target's patch count — for a set, the per-page count (Knut).
        self._std_targets: dict[str, StandardTarget] = {}
        # (Re)provision the user-visible scanner-test-targets folder in the
        # output root: copies of every bundled .cht land there for inspection
        # / tweaking, missing files are put back, edited ones never touched —
        # and a same-named .cht in that folder overrides the bundled copy
        # (Knut, beta.5).
        ensure_user_targets_dir(self._settings)
        for t in grouped_standard_targets(self._settings):
            self._std_targets[t.key] = t
            self._target_combo.addItem(self._target_label(t), t.key)
        self._target_combo.addItem(tr("Other… (choose a .cht file)"), "")
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        # This combo does not ask for the width of its LONGEST entry. The
        # standard-target panel would otherwise want 771 px in Spanish and 739
        # in Dutch purely because one target's name and patch count is that
        # wide, and that panel sits inside the fixed left pane.
        #
        # It asks for the width of the value it is SHOWING instead of a flat
        # 28 characters. Twenty-eight was enough for the target this window
        # opens on in eleven catalogues and six pixels short in Spanish,
        # seventeen in Dutch — the first thing the user reads, cut, with no
        # ellipsis. The entries themselves reach 771 px and no honest pane
        # width will ever hold the longest of them, so one the user picks later
        # is elided WITH an ellipsis and carries its full text as the tooltip,
        # and the drop-down still shows every name in full. See
        # `ValueWidthComboBox`.
        trow.addWidget(self._target_combo, 1)
        self._demo_btn = QPushButton(tr("Try with a demo scan"), self)
        self._demo_btn.setStyleSheet(_COMPACT_BTN)
        self._demo_btn.setToolTip(tr(
            "Loads a synthetic practice scan of this target — each patch a flat "
            "colour, drawn from the recognition file — plus its matching reference, "
            "so you can try placing the grid and building a profile with no scanner. "
            "It is NOT a real target: for a real profile, load your own scan and the "
            "reference that came with your physical target instead."))
        self._demo_btn.clicked.connect(self._reveal_target_files)
        trow.addWidget(self._demo_btn)
        v.addLayout(trow)

        # Custom .cht browse (only when "Other…" is selected). Labelled like
        # every other file row, and margin-free so its field lines up with
        # them on both sides (Knut, #108: it sat indented and unlabelled).
        self._cht_row_w = QWidget(self)
        _cht_v = QVBoxLayout(self._cht_row_w)
        _cht_v.setContentsMargins(0, 0, 0, 0)
        _cht_v.addLayout(self._labelled(
            tr("Target layout file (.cht):"), tr("Target layout file"),
            tr("The recognition file that describes where every patch sits on "
               "your target — ArgyllCMS calls it a .cht file. It usually comes "
               "with the target's software, or from ArgyllCMS's ref folder.\n\n"
               "Pick the one made for your exact target type; ChromIQ lays its "
               "reading grid from it.")))
        self._cht_row = QHBoxLayout()
        self._cht_field = QLineEdit(self)
        self._cht_field.setReadOnly(True)
        self._cht_field.setPlaceholderText(tr("Pick a .cht recognition file…"))
        self._cht_row.addWidget(self._cht_field, 1)
        bc = make_browse_button(self, tr("Browse…"), icon="folder_measure")
        bc.clicked.connect(self._pick_cht)
        self._cht_row.addWidget(bc)
        _cht_v.addLayout(self._cht_row)
        self._cht_row_w.setVisible(False)
        v.addWidget(self._cht_row_w)

        v.addLayout(self._labelled(
            tr("Target reference data (.cie / .txt / .ti3 / .cxf):"), tr("Reference data"),
            tr("The colour data file that came with your physical target — it "
            "lists the true colour of every patch. It's specific to your "
            "target's exact batch, so it can't be bundled; point ChromIQ at your "
            "own copy (the file you downloaded from the maker, or that came on "
            "the disc with the target).\n\n"
            "You don't need to prepare it — ChromIQ takes whatever format your "
            "target came in and converts it for you if needed:\n\n"
            "• Ready to use (used as-is): a .cie, .txt or .ti3 that already lists "
            "XYZ or Lab colour — for example Wolf Faust IT8, HutchColor HCT or "
            "LaserSoft DCPro. A .ti3 is what you get when you measure the "
            "target yourself with a spectrophotometer — the most accurate "
            "reference possible for your exact copy, better than the maker's "
            "batch average.\n"
            "• An X-Rite .cxf (for example LaserSoft's ISO 12641-2 targets): "
            "ChromIQ converts it automatically.\n"
            "• A raw or spectral .txt (for example the Christophe Métairie CMP "
            "Digital Target measurements): ChromIQ converts it automatically too.\n\n"
            "Any conversion is written to a temporary folder, so your original "
            "download is never changed.")))
        rrow = QHBoxLayout()
        self._ref_field = QLineEdit(self)
        self._ref_field.setReadOnly(True)
        self._ref_field.setPlaceholderText(tr("Pick the target's reference data…"))
        rrow.addWidget(self._ref_field, 1)
        br = make_browse_button(self, tr("Browse…"), icon="folder_measure")
        br.clicked.connect(self._pick_ref)
        rrow.addWidget(br)
        v.addLayout(rrow)
        self._std_note = self._hint_label("")
        v.addWidget(self._std_note)

        form.addWidget(self._standard_box)
        self._standard_box.setVisible(False)

    def _build_shot_bar(self, form) -> None:
        """Add-a-scan controls + averaging method (shown once a page has ≥2
        scans) — averaging repeated scans of a page cuts scanner noise."""
        row = QHBoxLayout()
        self._shot_combo = ElidingComboBox(self)
        self._shot_combo.currentIndexChanged.connect(self._on_shot_changed)
        self._shot_combo.setVisible(False)
        row.addWidget(self._shot_combo)
        # Compact height — a per-widget rule beats the app-wide 28px min-height.
        _compact_btn = ("QPushButton { padding: 2px 12px; min-height: 0;"
                        " font-size: 11px; }")
        self._add_shot_btn = QPushButton(tr("＋ Add another scan to average"), self)
        self._add_shot_btn.clicked.connect(self._add_shot)
        self._add_shot_btn.setStyleSheet(_compact_btn)
        row.addWidget(self._add_shot_btn)
        self._remove_shot_btn = QPushButton(tr("Remove this scan"), self)
        self._remove_shot_btn.clicked.connect(self._remove_shot)
        self._remove_shot_btn.setStyleSheet(_compact_btn)
        self._remove_shot_btn.setVisible(False)
        row.addWidget(self._remove_shot_btn)
        row.addStretch(1)
        # Kept, so it can be hidden WITH the row it explains. Printer mode hides
        # every control on this line (it reads one scan per page), and the ⓘ was
        # the one thing left behind — a lone info button floating against the
        # right edge, offering to explain a feature that is not there.
        self._avg_tip = self._tip(
            tr("Averaging several scans"),
            tr("Scanning the same sheet more than once and averaging the results "
            "smooths out the random noise every scanner adds, giving a cleaner, "
            "more accurate profile. Two or three scans is usually plenty.\n\n"
            "How to do it: pick your first scan above and place its four corners, "
            "then click “Add another scan to average”, pick the next scan, and "
            "place its corners too. Use the “Scan 1 / Scan 2 …” box to switch "
            "between them. Each scan keeps its own placement, so it's fine if the "
            "sheet shifted a little on the glass between scans.\n\n"
            "When you build, ChromIQ reads every scan, averages each patch, and "
            "profiles from the result. (For a multi-page ChromIQ chart, scans are "
            "averaged separately within each page.)"))
        row.addWidget(self._avg_tip, 0, Qt.AlignmentFlag.AlignVCenter)
        form.addLayout(row)

        self._avg_row = QHBoxLayout()
        self._avg_row.addWidget(QLabel(tr("Combine repeated scans by:"), self))
        self._avg_method = ElidingComboBox(self)
        self._avg_method.addItem(tr("Mean (simple average)"), "mean")
        self._avg_method.addItem(tr("Geometric mean (robust to an odd scan)"), "geomean")
        self._avg_method.addItem(tr("Trimmed mean (drop highest & lowest)"), "trimmed")
        self._avg_row.addWidget(self._avg_method)
        self._avg_row.addStretch(1)
        self._avg_row.addWidget(self._tip(
            tr("Averaging method"),
            tr("How repeated scans of a page are combined into one reading per "
            "patch:\n\n"
            "• Mean — the plain average. A good default.\n\n"
            "• Geometric mean — multiplies the readings and takes the root; a "
            "single unusually bright or dark scan pulls the result less than the "
            "plain mean. A good choice for scans.\n\n"
            "• Trimmed mean — throws away the highest and lowest reading of each "
            "patch, then averages the rest. Needs at least three scans; best when "
            "one scan might be off.")), 0, Qt.AlignmentFlag.AlignVCenter)
        self._avg_row_w = QWidget(self)
        self._avg_row_w.setLayout(self._avg_row)
        self._avg_row_w.setVisible(False)
        form.addWidget(self._avg_row_w)

    # ------------------------------------------------------------------ shots
    def _page_shots(self, pg: int | None = None) -> list[dict]:
        pg = self._page if pg is None else pg
        return self._shots.setdefault(pg, [{"path": None, "corners": None}])

    def _cur_shot(self) -> dict:
        shots = self._page_shots()
        if self._shot_idx >= len(shots):
            self._shot_idx = 0
        return shots[self._shot_idx]

    def _page_ready(self, pg: int) -> bool:
        return any(s["path"] for s in self._page_shots(pg))

    def _reset_shots(self) -> None:
        self._shots.clear()
        self._shot_idx = 0

    def _sync_shot_view(self) -> None:
        """Show the current shot's scan + placement in the marquee."""
        shot = self._cur_shot()
        scan = shot["path"]
        self._scan_field.setText(str(scan) if scan else "")
        if scan and Path(scan).is_file():
            self._marquee.set_image(_load_scan_qimage(scan))
            self._apply_shot_corners(shot)
        else:
            self._marquee.set_image(QImage())
        self._refresh_shot_bar()
        self._refresh()

    def _refresh_shot_bar(self) -> None:
        shots = self._page_shots()
        self._shot_combo.blockSignals(True)
        self._shot_combo.clear()
        for i in range(len(shots)):
            self._shot_combo.addItem(tr("Scan {n}").format(n=i + 1), i)
        self._shot_combo.setCurrentIndex(min(self._shot_idx, len(shots) - 1))
        self._shot_combo.blockSignals(False)
        multi = len(shots) > 1
        printer = self._printer_mode()
        # Printer mode reads ONE scan per page (the pages accumulate into a
        # single .ti3) — extra shots were silently ignored, so don't offer to
        # add them there (Knut's question; per-page averaging for printer mode
        # would be its own feature).
        self._add_shot_btn.setVisible(not printer)
        self._avg_tip.setVisible(not printer)
        self._shot_combo.setVisible(multi and not printer)
        self._remove_shot_btn.setVisible(multi)
        self._avg_row_w.setVisible(multi and not printer)
        if len(self._pages) > 1:
            done = sum(1 for pg in self._pages
                       if any(sh["path"] for sh in self._page_shots(pg)))
            self._page_hint.setText(
                tr("one scan per page — {k} of {n} picked").format(
                    k=done, n=len(self._pages)))

    def _add_shot(self) -> None:
        self._capture_current_corners()
        self._page_shots().append({"path": None, "corners": None})
        self._shot_idx = len(self._page_shots()) - 1
        self._sync_shot_view()

    def _remove_shot(self) -> None:
        shots = self._page_shots()
        if len(shots) <= 1:
            return
        del shots[self._shot_idx]
        self._shot_idx = min(self._shot_idx, len(shots) - 1)
        self._sync_shot_view()

    def _on_shot_changed(self, idx: int) -> None:
        if idx < 0:
            return
        self._capture_current_corners()
        self._shot_idx = idx
        self._sync_shot_view()

    def _build_inputs(self) -> None:
        form = self._content
        self._build_mode_selector(form)
        self._build_chromiq_inputs(form)
        self._build_standard_inputs(form)

        # Page selector directly above the scan it switches (Knut, #108).
        form.addWidget(self._page_widget)
        form.addLayout(self._labelled(
            tr("Scan or photo of the target (TIFF):"), tr("Scan or photo"),
            tr("Your capture of the target on the device you want to profile: a "
            "scan from a scanner, or a photo from a camera. Save it as a plain "
            "RGB TIFF, with the device's own colour correction turned off — the "
            "exact settings for scanners and cameras are further down in this "
            "note.\n\n"
            "Multi-page ChromIQ charts: switch pages with the Page selector and "
            "load each page's capture. To reduce noise you can also add several "
            "captures of the same sheet and let ChromIQ average them — see “Add "
            "another scan to average” below.")
            + "\n\n───────────────\n" + SCAN_SETUP_HELP
            + "\n\n───────────────\n" + SCANNING_TIPS_HELP
            + "\n\n───────────────\n" + CAMERA_HELP))
        row2 = QHBoxLayout()
        self._scan_field = QLineEdit(self)
        self._scan_field.setReadOnly(True)
        self._scan_field.setPlaceholderText(tr("Pick the scan or photo (TIFF)…"))
        row2.addWidget(self._scan_field, 1)
        self._scan_browse = make_browse_button(self, tr("Browse…"), icon="folder_measure")
        self._scan_browse.clicked.connect(self._pick_scan)
        row2.addWidget(self._scan_browse)
        form.addLayout(row2)

        # THE RIGHT PANE STARTS HERE. The window is two columns (see
        # `_build_two_panel_layout`): the preview and everything that acts on
        # it go on the right, the settings and the log stay on the left. The
        # boundary is recorded as this row is added rather than written down as
        # an index, so inserting a row above never silently moves the cut.
        self._right_first = form.count()
        self._marquee = ScanGridMarquee(self)
        self._marquee.setMinimumHeight(460)
        self._marquee_box = QVBoxLayout()
        self._marquee_box.setContentsMargins(0, 0, 0, 0)
        self._marquee_box.addWidget(self._marquee)
        self._marquee_placeholder = QLabel(
            tr("The grid is open in a separate window."), self)
        self._marquee_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._marquee_placeholder.setMinimumHeight(120)
        self._marquee_placeholder.setVisible(False)
        self._marquee_box.addWidget(self._marquee_placeholder)
        form.addLayout(self._marquee_box)

        ctl = QHBoxLayout()
        self._rotate_btn = QPushButton(tr("⟳ Rotate 90°"), self)
        self._rotate_btn.clicked.connect(self._marquee.rotate_90)
        self._reset_btn = QPushButton(tr("Reset view"), self)
        self._reset_btn.clicked.connect(self._marquee._reset_view)
        self._reset_grid_btn = QPushButton(tr("Reset grid"), self)
        self._reset_grid_btn.setToolTip(tr(
            "Re-centre the reading grid at the size computed from this target — use "
            "it if the grid has drifted off-screen (e.g. after loading an image at a "
            "different resolution)."))
        self._reset_grid_btn.clicked.connect(self._marquee.reset_selection_grid)
        self._popout_btn = QPushButton(tr("⤢ Pop out for a bigger view"), self)
        self._popout_btn.clicked.connect(self._toggle_popout)
        for _b in (self._rotate_btn, self._reset_btn, self._reset_grid_btn, self._popout_btn):
            _b.setStyleSheet(_COMPACT_BTN)
        # Pre-build alignment check (Knut, #108): a scanin dry-run for the
        # page on screen, into a temporary folder — verdict + diagnostic image
        # in a window, nothing left on disk.
        self._check_align_btn = QPushButton(tr("Check alignment"), self)
        self._check_align_btn.setToolTip(tr(
            "Read the page shown above once, WITHOUT building anything, and "
            "show the result: the diagnostic image of what was read plus the "
            "misalignment checks' verdict. Uses a temporary folder that is "
            "deleted when you close the result — your files stay untouched."))
        self._check_align_btn.setStyleSheet(_COMPACT_BTN)
        self._check_align_btn.clicked.connect(self._on_check_alignment)
        # Two lines, 3 + 2. Five buttons in one row need 840 px in German, and
        # with the preview beside a fixed left pane that alone puts the window's
        # floor above a 1440 screen, so one line is not available at any size
        # this window is meant for. The split is picked by measurement across
        # all twelve catalogues: 3 + 2 is the narrowest of the four
        # order-preserving splits in every one of them (worst line 447 px in
        # German; 2 + 3 costs 555, 4 + 1 costs 608). It also keeps the grouping
        # — the three "put it back where it was" buttons together, and "Pop out"
        # pushed away on its own.
        ctl.addWidget(self._rotate_btn)
        ctl.addWidget(self._reset_btn)
        ctl.addWidget(self._reset_grid_btn)
        ctl.addStretch(1)
        ctl2 = QHBoxLayout()
        ctl2.addWidget(self._check_align_btn)
        ctl2.addStretch(1)
        ctl2.addWidget(self._popout_btn)
        two = QVBoxLayout()
        two.setContentsMargins(0, 0, 0, 0)
        two.setSpacing(6)
        two.addLayout(ctl)
        two.addLayout(ctl2)
        form.addLayout(two)

        form.addWidget(self._hint_label(tr(
            "Drag the four corners onto the target's patch area until the green "
            "grid sits on the real patches. ChromIQ then reads each patch and "
            "builds the profile. On a ChromIQ chart the thin spacer strips "
            "printed above the first and below the last row stay OUTSIDE the "
            "grid — the dotted line shows where the printed block ends, so "
            "the corners belong on the patches just inside it.")))
        # ONE modifier, the one this user's keyboard actually has. It used to
        # read "⌘/Ctrl" everywhere, which shows a Windows user a key they do
        # not have and a Mac user one they do not need (Knut, 4.1.3-beta.15).
        _mod = "⌘" if _sys.platform == "darwin" else tr("Ctrl")
        form.addWidget(self._hint_label(tr(
            "Drag inside the grid to move it · drag a corner to reshape it · drag "
            "the background to pan · scroll (or {mod} + scroll) to zoom, also "
            "{mod} +/− and {mod} + 0 to reset · double-click resets the view. "
            "Rotate handles a sideways scan; Pop out gives a bigger view."
        ).format(mod=_mod)))

        # Inline label + control, sharing one label column with "Profile
        # type:" / "Profile name:" below (Basti: the control belongs NEXT to
        # its name, not under it, and the three should line up).
        self._sa_label = QLabel(tr("Patch sample area:"), self)
        row_sa = QHBoxLayout()
        row_sa.addWidget(self._sa_label)
        self._sample_area = NoScrollSpinBox(self)
        # Max 80%: at 100% the reading box would always include the patch
        # borders' blur; the edge check's activation window follows this
        # setting's rim in and out (Knut's #119 activation-box design — see
        # placement_probe), and the colour mean uses exactly this area.
        self._sample_area.setRange(20, 80)
        self._sample_area.setValue(60)
        self._sample_area.setSuffix(" %")
        self._sample_area.setMinimumWidth(110)
        self._sample_area.valueChanged.connect(
            lambda v: self._marquee.set_sample_fraction(v / 100.0))
        # Push the INITIAL value explicitly: setValue() above ran before the
        # connect, so the signal never fired and the marquee kept its own
        # built-in 50 % — invisible while the default WAS 50, but the moment
        # the default moved to 60 the drawn sample boxes silently stayed a
        # size smaller than everything scanin read (Knut measured it, #119:
        # grid 50.8 %, diagnostic 60 %).
        self._marquee.set_sample_fraction(self._sample_area.value() / 100.0)
        row_sa.addWidget(self._sample_area)
        row_sa.addStretch(1)
        row_sa.addWidget(self._tip(
            tr("Patch sample area"),
            tr("How much of each patch ChromIQ reads — shown as the filled green "
            "inner square inside every cell of the grid above.\n\n"
            "It always reads the middle of a patch and leaves the edges out, "
            "because the edges are where ink can bleed, a thin border may show, or "
            "the grid may sit a hair off. Reading only the clean centre keeps the "
            "measured colour honest.\n\n"
            "60% is a safe default. Lower it (a smaller square) if your patches are "
            "small or the grid isn't perfectly aligned, so you stay well clear of "
            "the edges. Raise it (a bigger square) only for large, cleanly-printed "
            "patches with the grid sitting exactly right, to average over more of "
            "each colour for a touch less noise. 80% is the maximum — beyond that "
            "the square would always take in the patches' soft borders, and the "
            "reading would no longer be the pure colour.\n\n"
            "On a chart with hexagonal patches the ceiling is lower, and ChromIQ "
            "works it out from the shape of your patches and sets it for you. A "
            "square is a comfortable fit inside a rectangle and a tight one "
            "inside a hexagon, whose sides slant away above and below; past that "
            "point the square would reach through them into the patch next door "
            "— on every patch at once, not just here and there.\n\n"
            "The misalignment checks look after themselves whatever you pick "
            "here: the placement agreement always judges the very area you "
            "chose, and the edge detector watches a thin ring just outside "
            "that same area — it moves in and out with this setting, so "
            "neither needs adjusting when you change it.")), 0, Qt.AlignmentFlag.AlignVCenter)
        form.addLayout(row_sa)

        self._build_shot_bar(form)

        opts = QGridLayout()
        opts.setHorizontalSpacing(24)
        opts.setVerticalSpacing(6)
        self._perspective = QCheckBox(tr("Correct perspective (slightly skewed scan)"), self)
        self._perspective.setChecked(True)
        self._diag = QCheckBox(tr("Save a diagnostic image of what was read"), self)
        # The three reading options in ONE column, not two across and one
        # under. Side by side this row is the widest thing in the right pane in
        # five of the twelve languages — 814 px in Russian, 746 in French,
        # against 447 for the button row — so it, and not the buttons, would
        # set the window's floor. Stacked it is 416 px at its worst, and three
        # related switches read better as a list than as a 2 + 1 block.
        opts.addWidget(self._perspective, 0, 0)
        opts.addWidget(self._diag, 1, 0)
        opts.setColumnStretch(2, 1)
        opts.addWidget(self._tip(
            tr("Reading options"),
            tr("How ChromIQ reads the patches from your scan.\n\n"
            "• Correct perspective — leave this on (it's on by default). Almost "
            "every scan or photo is very slightly skewed, and this lets ChromIQ "
            "read the patch area as a gently four-cornered shape instead of "
            "insisting on a perfect rectangle. That way the grid still lands on "
            "the patches even if the sheet wasn't perfectly square to the scanner "
            "or camera. There's no downside to leaving it on — only turn it off if "
            "you're certain the scan is geometrically perfect.\n\n"
            "• Save a diagnostic image — after reading, ChromIQ writes a copy of "
            "your scan with the patches it actually read drawn on top, right next "
            "to the scan file. Open that image to check the grid landed correctly: "
            "each drawn marker should sit squarely on its colour. It's the very "
            "first thing to look at if a profile comes out wrong, and it costs "
            "nothing but a little disk space — so it's worth leaving on while "
            "you're getting your placement right.\n\n"
            "• Use fiducial marks — shown only for standard targets that print "
            "small registration crosses just outside the patch block. Either way "
            "you line the four corners up on the patches themselves — the easy, "
            "always-visible reference. With it off, the reading is placed straight "
            "from those corners; with it on, ChromIQ also draws the crosses and "
            "anchors to them, working out where they are from your corner placement "
            "(so you still just line up the patches). It puts the grid in exactly "
            "the same spot, so turn it on only if you find the marks handy to see. "
            "It hides automatically for ChromIQ-made charts, which print no marks.")),
            0, 3, 3, 1, Qt.AlignmentFlag.AlignVCenter)

        self._use_fiducials_cb = QCheckBox(
            tr("Use fiducial marks in the .cht as reference"), self)
        self._use_fiducials_cb.setToolTip(tr(
            "How ChromIQ lines the reading grid up with your scan.\n\n"
            "Either way, you drag the four corners onto the patch area — the block "
            "of colour squares. It's the easiest thing to aim at and it works for "
            "every target, so you never have to hunt for anything smaller.\n\n"
            "Off (default): the grid is placed straight from where you put the four "
            "corners.\n\n"
            "On: ChromIQ also draws the target's fiducial marks — the little "
            "registration crosses printed just outside the patches — and lines the "
            "grid up with those instead. It figures out where the marks are from "
            "the corners you placed, so you still only line up the patches. The grid "
            "ends up in exactly the same place either way, so switch it on only if "
            "you like seeing the marks.\n\n"
            "The box turns itself off (with a quick flash) for targets that don't "
            "have separate fiducial marks — there's nothing extra to show."))
        self._use_fiducials_cb.toggled.connect(self._on_fiducial_toggled)
        opts.addWidget(self._use_fiducials_cb, 2, 0)
        form.addLayout(opts)
        # …and ends here, with the last of the reading options. Everything
        # below is a profile setting and belongs on the left.
        self._right_last = form.count() - 1

        # Profile type (-a) + colour space (-a) + quality (-q), the most-used
        # colprof settings, next to each other (#121, Knut). The friendly
        # profile-type combo maps to colprof -a; colour space picks the cLUT PCS
        # (only meaningful for the look-up-table type); the rest lives behind
        # "Advanced…". Same method + (-flag) label style as tab "4 Build profile".
        self._pt_label = QLabel(tr("Profile type (-a):"), self)
        row3 = QHBoxLayout()
        row3.addWidget(self._pt_label)
        self._ptype = ElidingComboBox(self)
        for data, label in scanner_colprof.PTYPE_CHOICES:
            self._ptype.addItem(label, data)
        row3.addWidget(self._ptype, 1)
        row3.addWidget(self._tip(
            tr("Profile type and quality"),
            tr("How the scanner or camera profile models colour.\n\n"
               "Profile type (-a):\n"
               "• Shaper + matrix — a small, robust profile (per-channel curves "
               "plus a 3×3 matrix). The usual choice for scanners: forgiving of "
               "noise and a modest number of patches, and enough for faithful "
               "colour. Recommended.\n"
               "• Matrix only — even simpler; use it if a chart has very few "
               "patches or the shaper curves misbehave.\n"
               "• cLUT — XYZ table / cLUT — Lab table — a full look-up table that "
               "can follow the device more closely. XYZ and Lab are just how the "
               "table stores colour inside; both are accurate, and Lab sometimes "
               "gives slightly smoother neutrals. A cLUT is worth it only with a "
               "large chart and clean, repeatable scans; with noisy data it just "
               "fits the noise.\n\n"
               "Quality (-q): the cLUT's grid resolution — higher is finer but "
               "slower, and needs better data to be worth it. It applies only to "
               "the two cLUT types (greyed for the matrix types). Medium is a "
               "good default; Low is a quick test, High/Ultra for large, clean "
               "charts.\n\n"
               "These settings build whichever profile this window makes. If you "
               "tick “Profile my printer from this scan”, the same type, quality "
               "and Advanced options build the printer profile instead — and "
               "because a printer is best modelled by a table, the type then "
               "defaults to “cLUT — Lab” (it's “Shaper + matrix” for a scanner or "
               "camera). You still won't find a working-space (like sRGB) or "
               "rendering-intent choice here; those aren't part of building a "
               "profile from measurements.")),
            0, Qt.AlignmentFlag.AlignVCenter)
        form.addLayout(row3)

        # Quality (cLUT only) + the Advanced button, on their own row so the type
        # row above never has to scroll sideways.
        row3b = QHBoxLayout()
        self._q_label = QLabel(tr("Quality (-q):"), self)
        row3b.addWidget(self._q_label)
        self._pq = ElidingComboBox(self)
        for data, label in scanner_colprof.QUALITY_CHOICES:
            self._pq.addItem(label, data)
        self._pq.setCurrentIndex(1)                      # Medium
        row3b.addWidget(self._pq)
        # The trailing spacer matches the ⓘ tooltip column, so the combo's
        # right edge lines up with the fields and the command box above and
        # below it (Knut).
        row3b.addStretch(1)
        # Save the current type / quality / description / Advanced choices as the
        # defaults for next time — the same explicit affordance the Build-Profile
        # tab offers (Basti, #121). Without it, changes live only for this window.
        # It and "Restore defaults" are BUILT here, beside the settings they act
        # on, and PLACED in the bottom button row (see showEvent).
        self._save_defaults_btn = QPushButton(tr("Save as Defaults"), self)
        self._save_defaults_btn.setToolTip(
            tr("Store everything you've set here — the profile type, quality, the "
               "description, and every option under Advanced — as your defaults. "
               "Next time you open this window they'll already be filled in, so "
               "you don't have to set them up again.\n\n"
               "Each kind of profile is remembered on its own: this saves the "
               "settings for whatever you're building right now (a printer "
               "profile, a scanner/camera profile from a ChromIQ chart, or one "
               "from a standard target), and leaves the other kinds untouched.\n\n"
               "Your choices are only remembered when you click this. Closing the "
               "window without saving leaves your saved defaults untouched, and "
               "“Restore factory defaults” in Preferences clears them again."))
        self._save_defaults_btn.clicked.connect(self._save_defaults_clicked)
        self._restore_defaults_btn = QPushButton(tr("Restore defaults"), self)
        self._restore_defaults_btn.clicked.connect(self._restore_defaults_clicked)
        row3b.addSpacing(32)                              # ⓘ tooltip column width
        form.addLayout(row3b)

        # Profile description (-D): the name embedded in the .icc and shown in
        # colour-management menus. Renamed from "Profile name" and given
        # scanner-appropriate examples (#121, Knut).
        row4 = QHBoxLayout()
        self._pn_label = QLabel(tr("Profile description (-D):"), self)
        row4.addWidget(self._pn_label)
        self._prof_name = QLineEdit(self)
        self._prof_name.setPlaceholderText(
            tr("e.g. Epson V850 · Photo · Positive · 2026-07"))
        row4.addWidget(self._prof_name, 1)
        row4.addWidget(self._tip(
            tr("Profile description (-D)"),
            tr("The name embedded in the finished profile (colprof's -D). It's "
               "used for the .icc file itself and is the name colour-managed "
               "programs — Photoshop, your scanning software, Preview — show in "
               "their profile lists.\n\n"
               "Use a consistent format that says what the profile is, so the "
               "right one is easy to find later. For a scanner or camera, a good "
               "recipe is device, media, film/print type, and date:\n\n"
               "  Device · Media · Type · Date\n"
               "  e.g. “Epson V850 · Photo paper · Positive · 2026-07”\n"
               "  e.g. “Canon R5 · IT8 target · 2026-07”\n\n"
               "A name like “Moab_Satin_240gsm” is easy to mistake for a paper "
               "or printer profile later, so name it for the scanner/camera it "
               "actually is.\n\n"
               "Leave it blank and the profile is named after the chart or target "
               "scan it was built from. When “Profile my printer from this scan” "
               "is ticked, this name applies to the printer profile instead.")))
        form.addLayout(row4)

        # Command preview: the exact colprof command the current settings run,
        # in a green-accented info box (like the Create Chart info box, #121 Knut).
        _mode = resolve_mode(self._settings.get("appearance", "auto"))
        _light = _mode == "light"
        _cmd_bg = "#eafaf3" if _light else "#06251a"
        _cmd_fg = "#0a7a58" if _light else SPEC_GREEN
        if _mode == APPEARANCE_NEUTRAL:
            # A command preview is a READING surface, not a status: the raised
            # card with body ink on it, and the edge carries the box.
            from ui import neutral_styles as _n
            _cmd_bg, _cmd_fg = _n.NM_BG_SURFACE, _n.NM_TEXT_MAIN
        cmd_row = QHBoxLayout()
        self._cmd_preview = QLabel("", self)
        self._cmd_preview.setObjectName("info")
        self._cmd_preview.setWordWrap(True)
        self._cmd_preview.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._cmd_preview.setStyleSheet(
            f"QLabel#info {{ background: {_cmd_bg}; color: {_cmd_fg};"
            f" border: 1px solid {accent_for(SPEC_GREEN, _mode)}; border-radius: 4px;"
            f" padding: 6px 10px; font-family: Menlo, monospace; font-size: 11px; }}")
        cmd_row.addWidget(self._cmd_preview, 1)
        cmd_row.addWidget(self._tip(
            tr("Command preview"),
            tr("The exact colprof command your current settings will run, "
               "including anything changed under Advanced. It's shown so you can "
               "see precisely what happens and copy it if you like; the profile "
               "is still built by ChromIQ when you press the build button.")),
            0, Qt.AlignmentFlag.AlignTop)
        form.addLayout(cmd_row)

        # Wire live updates, then load the active context's remembered settings.
        for _w in (self._ptype, self._pq):
            _w.currentIndexChanged.connect(self._on_colprof_changed)
        self._prof_name.textChanged.connect(self._update_command_preview)
        self._active_ctx = self._colprof_context()
        self._load_context(self._active_ctx)
        self._on_colprof_changed()
        self._mark_default_combos()
        # One shared label column → the spinbox, combos and name field all
        # start at the same x (Basti, #108 follow-up).
        _labels = (self._sa_label, self._pt_label, self._q_label, self._pn_label)
        _w = max(l.sizeHint().width() for l in _labels) + 8
        for _l in _labels:
            _l.setFixedWidth(_w)

    # ------------------------------------------------------------------
    # The window's two panes
    # ------------------------------------------------------------------
    # The settings and the log on the left, the preview and everything that
    # acts on it on the right. `_build_inputs` above fills one column; this
    # deals that column into two, re-parenting the SAME layout items, so every
    # widget, style and signal built above is untouched.
    #
    # Breathing room either side of the splitter handle — the same 16 px the
    # inner layout already leaves under the log.
    _PANE_GAP = 16
    # Clear air between the last thing in a column and its own scrollbar. Both
    # panes scroll, and without this the bar lands hard against the ⓘ buttons
    # on the left and against the ⓘ column on the right: they read as one
    # smudged edge, and the top ⓘ looks like part of the bar.
    _BAR_GAP = 12

    def _build_two_panel_layout(self) -> None:
        from PyQt6.QtWidgets import QFrame, QScrollArea
        first, last = self._right_first, self._right_last

        items = [self._content.itemAt(i) for i in range(self._content.count())]
        # Take every item out, back to front, so the indices stay valid.
        for i in range(self._content.count() - 1, -1, -1):
            self._content.takeAt(i)

        def column(idxs):
            lay = QVBoxLayout()
            lay.setSpacing(10)
            lay.setContentsMargins(0, 0, self._BAR_GAP, 0)
            for i in idxs:
                it = items[i]
                if it.widget() is not None:
                    lay.addWidget(it.widget())
                elif it.layout() is not None:
                    lay.addLayout(it.layout())
            return lay

        left_idx = [i for i in range(len(items)) if not (first <= i <= last)]
        right_idx = [i for i in range(len(items)) if first <= i <= last]
        left_lay, right_lay = column(left_idx), column(right_idx)

        # Room for the eight drag handles, or the ones on the grid's own edge
        # fall outside the widget and cannot be grabbed at all — and placing
        # the four corners is the whole job this preview exists for. See
        # ScanGridMarquee.
        from ui.scan_grid_marquee import _HANDLE_OFFSET, _HANDLE_R
        self._marquee.handle_margin = _HANDLE_OFFSET + _HANDLE_R
        # Advanced is a section of this window, not a separate modal. The real
        # editor's controls are re-parented in, so these ARE the controls, not
        # a copy of them. It sits directly above the command preview, which is
        # the last row of the left column: open the section and the box
        # beneath it is the answer to what you just changed (owner).
        self._adv_inline = self._build_inline_advanced()
        left_lay.insertWidget(left_lay.count() - 1, self._adv_inline)
        left_lay.addStretch(1)
        right_lay.addStretch(1)

        # The existing scroll area keeps the LEFT column; the right gets its own,
        # so the preview scrolls without dragging the settings out of view.
        # ORDER MATTERS. Build the RIGHT pane first: `self._scroll.setWidget`
        # destroys the old content widget, and doing that while the right
        # column's rows are still homeless crashes PyQt6 inside FadeScrollArea
        # (the re-entrant scroll-range path CLAUDE.md documents).
        right_w = QWidget(self)
        right_lay.setContentsMargins(self._PANE_GAP, 0, self._BAR_GAP, 0)
        right_w.setLayout(right_lay)
        self._scroll_right = QScrollArea(self)
        self._scroll_right.setWidgetResizable(True)
        self._scroll_right.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_right.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_right.setWidget(right_w)
        lw = QWidget(self)
        lw.setLayout(left_lay)
        self._scroll.setWidget(lw)

        # The spectrum bar, the big buttons and the log all sit UNDER THE LEFT
        # PANE ONLY, not across the whole window — and in the main window's
        # order: controls, bar, buttons, then the log LAST, drag-resizable.
        inner = self._inner
        for w in (self._scroll, self._busy_bar, self._log, self._button_box):
            if w is not None:
                inner.removeWidget(w)
        left_pane_w = QWidget(self)
        left_pane = QVBoxLayout(left_pane_w)
        left_pane.setContentsMargins(0, 0, self._PANE_GAP, 0)
        left_pane.setSpacing(10)
        left_pane.addWidget(self._scroll, 1)
        if self._busy_bar is not None:
            left_pane.addWidget(self._busy_bar)
        # The four big buttons, two rows of two, each pair filling the pane
        # (owner, 2026-09-02):
        #   Save as Defaults | Restore defaults
        #   Build profile    | Close
        # On ONE line this is the widest thing in the left column — 965 px in
        # Russian, 911 in German and Polish, against 501 for the widest
        # settings row — because the buttons sit under the left pane alone;
        # across the whole window they were free. And a QDialogButtonBox
        # cannot express this order anyway: it sorts by role and by platform
        # convention. A GRID rather than two independent rows, so the divider
        # sits at the same x on both lines: half the German pane is 298 px and
        # "Profil mit Scanner oder Kamera erstellen" alone is 356, so two free
        # rows would split at different places and read as crooked.
        from PyQt6.QtWidgets import QGridLayout
        self._btn_row_w = QWidget(self)
        self._btn_grid = QGridLayout(self._btn_row_w)
        self._btn_grid.setContentsMargins(0, 0, 0, 0)
        self._btn_grid.setHorizontalSpacing(8)
        self._btn_grid.setVerticalSpacing(8)
        self._btn_grid.setColumnStretch(0, 1)
        self._btn_grid.setColumnStretch(1, 1)
        left_pane.addWidget(self._btn_row_w)
        # The tabs' own log treatment: nine lines of the font it really gets,
        # plus the drag-the-top-edge grip whose height the app remembers.
        from ui.widgets import add_log_row, fit_log_height
        # NOT setObjectName("log") — that name pulls in the main window's own
        # green monospace log styling, which does not belong in a Tools window.
        # Only the height behaviour and the drag grip are wanted here.
        self._log.setMaximumHeight(16777215)
        fit_log_height(self._log)
        add_log_row(left_pane, self._log, left_pane_w)

        # A splitter, like the four main tabs (ui/tabs/tab_chart.py:2891), so
        # the divider can be dragged. tab_chart's own note warns that a splitter
        # OVERLAPS its panes when their minimums exceed the window — hence the
        # cap on the right pane below.
        from PyQt6.QtWidgets import QSplitter
        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.setHandleWidth(4)
        split.addWidget(left_pane_w)
        split.addWidget(self._scroll_right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        # The right pane's rows (the five view buttons, the two checkboxes) do
        # not shrink below this, so an even 50/50 clips them. Ask for the width
        # each pane actually needs.
        split.setSizes([700, 700])
        self._right_pane_w = right_w

        # A MINIMUM WIDTH IS NOT OPTIONAL HERE. A QScrollArea does not pass its
        # widget's minimum width up, and both scroll areas pin the horizontal
        # bar OFF — so without one the window can be dragged narrow enough that
        # the right pane is amputated and its controls, "Use fiducial marks"
        # included, cannot be reached at all. Both panes' floors are therefore
        # read off their content in showEvent, never hard-coded.
        self._left_pane_w = left_pane_w
        # The left pane is FIXED-WIDTH (owner), the way every main-window tab
        # already does it (ui/tabs/tab_chart.py:2897, `left.setFixedWidth(580)`).
        # Extra window width then goes entirely to the preview, which is the
        # only thing that gains from it. The number is READ, not chosen: it is
        # 596 px in English and 666 in Spanish, the widest of the twelve.
        split.setChildrenCollapsible(False)
        self._two_panel_split = split
        inner.addWidget(split, 1)

        # The bottom row is populated in showEvent, NOT here: __init__ adds
        # Reveal/Install to the button box after this runs, and a
        # QDialogButtonBox re-claims every button it still lists on its next
        # relayout — which silently pulled Build and Close back out of this row
        # and left it showing two buttons.

    def showEvent(self, event) -> None:  # noqa: N802
        """Place the bottom button row, then pin the fixed left-pane width and
        the window's minimum width — all three need the layout to be real."""
        first = not self._sized_once
        super().showEvent(event)
        if not first:
            return
        # The two "defaults" buttons above, the two that end the job below,
        # each pair filling the pane's width (owner). `removeButton` first, or
        # the box takes them back on its next relayout.
        from PyQt6.QtWidgets import QSizePolicy
        for b in (self._run_btn, self._save_defaults_btn,
                  self._restore_defaults_btn, self._close_btn):
            self._button_box.removeButton(b)
        for b, (r, c) in ((self._save_defaults_btn, (0, 0)),
                          (self._restore_defaults_btn, (0, 1)),
                          (self._run_btn, (1, 0)),
                          (self._close_btn, (1, 1))):
            # …filling its cell. Without this the buttons keep their own width
            # and sit left in a half-empty column.
            b.setSizePolicy(QSizePolicy.Policy.Expanding,
                            b.sizePolicy().verticalPolicy())
            # ADD FIRST, SHOW SECOND. `removeButton` leaves the button with no
            # parent AND explicitly hidden, so it does need showing again —
            # adding it to a layout does not undo an explicit hide. But **a
            # parentless widget IS a top-level window**, and showing one makes
            # macOS create a real NSWindow for it. Done in the other order,
            # opening this tool spawned FOUR extra native windows — measured,
            # each carrying NSWindowCollectionBehaviorFullScreenPrimary — which
            # were reclaimed a moment later when `addWidget` reparented them.
            # Invisible on a plain desktop; in macOS full screen that is four
            # windows the compositor has to animate into and out of a Space,
            # which is the "weird animation like other windows opening full
            # screen as well until it settled" the owner reported for beta 7.
            # `addWidget` reparents, so by the line below the button is an
            # ordinary child and no window is ever created.
            self._btn_grid.addWidget(b, r, c)
            b.setVisible(True)
        # "Reveal profile" / "Install profile" have to move too. They live on
        # the same button box, and the line below hides it for good — so a
        # build that succeeded set `setVisible(True)` on two buttons whose
        # PARENT was hidden, and neither ever appeared. The user was told the
        # profile was saved and then left with no way to open its folder and no
        # way to install it, which is the whole of what this window offers
        # afterwards. Same order as above (add, then show) for the same reason —
        # except these two must stay HIDDEN here: a build has not happened yet,
        # and Qt layouts skip a hidden widget, so the row costs nothing until
        # `_done` shows them.
        for b, (r, c) in ((self._reveal_btn, (2, 0)),
                          (self._install_btn, (2, 1))):
            self._button_box.removeButton(b)
            b.setSizePolicy(QSizePolicy.Policy.Expanding,
                            b.sizePolicy().verticalPolicy())
            self._btn_grid.addWidget(b, r, c)
        self._button_box.setVisible(False)

        lay = self.layout()
        lay.activate()
        # Read the width the CONTENT needs, not the scroll area's size hint —
        # a QScrollArea's hint is a generic default that has nothing to do with
        # its widget, and sizing the pane from it clips the widest row (the
        # "Create profile using:" radios) with no scrollbar to recover it.
        content_w = self._scroll.widget().sizeHint().width()
        # …and the width of the panels that are HIDDEN right now. The left
        # column swaps a whole sub-panel when the source changes and another
        # when "profile my printer" is ticked, and a fixed pane sized from
        # whichever one happens to be on screen at start-up is a permanent
        # clip the moment the user switches: measured at 65 px of the standard
        # target's own controls, with no scrollbar to recover them.
        for _hidden in (self._chromiq_box, self._standard_box,
                        self._printer_box):
            content_w = max(content_w,
                            _hidden.sizeHint().width() + self._BAR_GAP)
        self._pane_bar_w = self._scroll.verticalScrollBar().sizeHint().width() + 4
        want = max(content_w + self._pane_bar_w,
                   self._btn_row_w.sizeHint().width(),
                   self._log.minimumWidth(), 580)
        self._pane_w_closed = want + self._PANE_GAP
        self._measure_advanced_width()
        self._left_pane_w.setFixedWidth(self._pane_w_closed)
        # The right pane's floor, read off its content for the same reason. A
        # guessed number does not work here: 360 let the window report a floor
        # at which the view buttons and "Pop out" were simply off the edge —
        # 111 px of them in German. The 360 that remains is only the marquee's
        # own lower limit, below which the preview is too small to aim in.
        self._scroll_right.setMinimumWidth(
            max(360, self._right_pane_w.minimumSizeHint().width())
            + self._PANE_GAP)
        # A QSplitter caches the minimum it reports, and the two panes were
        # only just given their widths — read it without invalidating first and
        # the window's floor comes back as 547 px when the panes alone need
        # 1084. The window then lets itself be dragged to half its own content.
        self._refresh_min_width()

    def _measure_advanced_width(self) -> None:
        """How wide the fixed left pane has to be with Advanced OPEN.

        The section is hidden while it is collapsed, so it contributes nothing
        to the pane's ordinary measurement — and its own controls are the
        widest thing in the left column. Sized without it, opening Advanced
        clipped the whole column against a fixed pane with no scrollbar to
        recover it.

        Two widths, then, and the pane takes the one the current state needs.
        Making the window permanently as wide as an open Advanced would cost
        every user width for a section that starts closed; the disclosure
        already re-fits the window's height when it is toggled, so it asks for
        the width it needs at the same moment.
        """
        if getattr(self, "_pane_w_closed", None) is None:
            return                      # not sized yet; showEvent will do it
        m = self._adv_inline.contentsMargins()
        self._pane_w_open = max(
            self._pane_w_closed,
            self._adv_inline_body.minimumSizeHint().width() + self._pane_bar_w
            + m.left() + m.right() + self._BAR_GAP + 4 + self._PANE_GAP)

    def _refresh_min_width(self) -> None:
        """Re-read the window's floor from the layout."""
        lay = self.layout()
        # A QSplitter caches the minimum it reports, and the two panes were
        # only just given their widths — read it without invalidating first and
        # the window's floor comes back as 547 px when the panes alone need
        # 1084. The window then lets itself be dragged to half its own content.
        lay.invalidate()
        self._two_panel_split.refresh()
        lay.activate()
        # The LAYOUT's floor, not MIN_WIDTH: MIN_WIDTH is the width the window
        # opens at, and holding the minimum there would stop a 1280-px screen
        # from ever seeing the whole window with room to spare.
        floor = lay.minimumSize()
        self.setMinimumWidth(floor.width())
        self.resize(max(self.width(), self.minimumWidth()), self.height())

    def _build_inline_advanced(self) -> QWidget:
        """The 'Advanced' section of this window: a disclosure that starts
        closed and holds the REAL Advanced editor's controls, so there is no
        separate modal to open.

        THE SAME SECTION WIDGET THE REST OF THE APP USES (owner, beta 7): this
        window had grown its own disclosure — a square `QFrame` with a
        `QToolButton` sitting *inside* it — while the group boxes it contains,
        and every other collapsible section in the app (`tab_chart`,
        `layout_options_panel`, the device-link tool's "Expert options"), are
        `CollapsibleGroupBox`: a rounded frame with the label and its ▶/▼ on the
        frame itself. One odd section out of the whole app is exactly what he
        saw. `_adv_inline_head` keeps the checkable API the window and its tests
        already speak, so nothing else in here had to change.
        """
        box = _AdvancedSection(tr("Advanced…"), self, collapsed=True)
        self._adv_inline_layout = QVBoxLayout(box.body)
        self._adv_inline_layout.setContentsMargins(8, 4, 8, 4)
        self._adv_inline_layout.setSpacing(6)
        self._adv_inline_head = box
        self._adv_inline_body = self._make_advanced_body(box.body)
        self._adv_inline_layout.addWidget(self._adv_inline_body)
        # A BOUND METHOD, not a lambda or a closure: a slot that outlives the
        # widgets it captures is how this window has crashed before.
        box.opened.connect(self._on_advanced_toggled)
        return box

    def _make_advanced_body(self, parent: QWidget) -> QWidget:
        """A fresh Advanced editor for the profile kind being built right now,
        with its body lifted out of it.

        The applicable options are MODE-AWARE (#121): a printer profile offers
        gamut mapping, the intent overrides and the B2A table quality, and a
        scanner/camera profile offers white-point handling instead. So the
        section is rebuilt when the kind changes — see `_sync_inline_advanced`.
        """
        from PyQt6.QtWidgets import (QAbstractSpinBox, QCheckBox, QComboBox,
                                     QLineEdit, QScrollArea)
        from ui.dialogs.scanner_colprof import ScannerAdvancedDialog
        from workflow.softproof_runner import argyll_ref_dir
        self._adv_ctx = self._colprof_context()
        self._adv_editor = ScannerAdvancedDialog(
            dict(self._adv_vals), self, printer=self._printer_mode(),
            ref_dir=argyll_ref_dir(self._settings))
        body = self._adv_editor.findChildren(QScrollArea)[0].takeWidget()
        body.setParent(parent)
        body.setVisible(self._adv_inline_head.isChecked())
        # The command preview below the section names the flags these controls
        # set, so it follows them as they move — there is no OK button here to
        # wait for. Bound method, never a lambda (see above).
        for kind, signal in ((QCheckBox, "toggled"),
                             (QComboBox, "currentIndexChanged"),
                             (QLineEdit, "textChanged"),
                             (QAbstractSpinBox, "valueChanged")):
            for w in body.findChildren(kind):
                getattr(w, signal).connect(self._on_advanced_changed)
        return body

    def _sync_inline_advanced(self) -> None:
        """Point the Advanced section at the profile being built right now.

        The settings are remembered per context (#121) and the applicable
        options differ between them, so a change of context rebuilds the
        section from that context's own values. The modal this replaced was
        likewise built fresh every time it was opened.
        """
        if getattr(self, "_adv_inline_body", None) is None:
            return
        if self._adv_ctx == self._colprof_context():
            return
        old_body, old_editor = self._adv_inline_body, self._adv_editor
        self._adv_inline_body = self._make_advanced_body(self._adv_inline.body)
        self._adv_inline_layout.replaceWidget(old_body, self._adv_inline_body)
        old_body.setParent(None)
        old_body.deleteLater()
        old_editor.deleteLater()
        self._adv_vals = self._adv_editor.values()
        # A printer profile's options are the wider set, so the width the pane
        # needs when the section is open moves with the context.
        self._measure_advanced_width()
        self._on_advanced_toggled(self._adv_inline_head.isChecked())

    def _on_advanced_changed(self, *_args) -> None:
        """An Advanced control moved: it is the live value from now on."""
        self._adv_vals = self._adv_editor.values()
        self._update_command_preview()

    def _on_advanced_toggled(self, on: bool) -> None:
        self._adv_inline_body.setVisible(on)
        # Advanced's own controls are wider than the rest of the left column;
        # the fixed pane widens for them and gives the width back when the
        # section closes. See showEvent for why it is not simply always wide.
        if getattr(self, "_pane_w_open", None) is not None:
            self._left_pane_w.setFixedWidth(
                self._pane_w_open if on else self._pane_w_closed)
            self._refresh_min_width()
        self._refit_height()

    def _restore_defaults_clicked(self) -> None:
        """Put this window's profile settings back to the built-in defaults.

        The CONTROLS only. What is stored stays stored until "Save as Defaults"
        is pressed — exactly what this button did when it belonged to the
        Advanced editor's own button box.
        """
        self._adv_editor.restore_defaults()
        self._adv_vals = self._adv_editor.values()
        i = self._ptype.findData(
            scanner_colprof.PTYPE_DEFAULT[self._printer_mode()])
        if i >= 0:
            self._ptype.setCurrentIndex(i)
        i = self._pq.findData("m")
        if i >= 0:
            self._pq.setCurrentIndex(i)
        self._prof_name.clear()
        self._update_command_preview()

    # ------------------------------------------------------------------
    # Scanner colprof settings (#121, Knut)
    # ------------------------------------------------------------------
    _CONTEXTS = ("printer", "chart", "standard")

    def _colprof_context(self) -> str:
        """Which settings bucket the current mode uses (Knut, #121): a printer
        profile, a scanner profile from a ChromIQ chart, or a scanner profile
        from a standard target — each remembers its own settings."""
        if self._printer_mode():
            return "printer"
        if self._standard_mode():
            return "standard"
        return "chart"

    def _load_ctx_configs(self) -> dict[str, dict]:
        raw = self._settings.get("scanner_colprof_configs", {}) or {}
        out: dict[str, dict] = {}
        for ctx in self._CONTEXTS:
            c = raw.get(ctx) if isinstance(raw, dict) else None
            out[ctx] = dict(c) if isinstance(c, dict) else {}
        return out

    def _current_main_vals(self) -> dict:
        return {
            "ptype": self._ptype.currentData() or "s",   # -a letter
            "quality": self._pq.currentData() or "m",
        }

    def _snapshot_context(self, ctx: str) -> None:
        """Capture the current widgets into *ctx*'s in-memory config."""
        self._ctx_cfg[ctx] = {
            "main": {**self._current_main_vals(),
                     "description": self._prof_name.text()},
            "adv": dict(self._adv_vals),
        }

    def _load_context(self, ctx: str) -> None:
        """Load *ctx*'s remembered settings into the widgets (or the built-in
        defaults for a bucket that's never been used)."""
        cfg = self._ctx_cfg.get(ctx) or {}
        main = cfg.get("main") or {}
        adv = cfg.get("adv") or {}
        default_ptype = scanner_colprof.PTYPE_DEFAULT[ctx == "printer"]

        def _sel(combo, data) -> None:
            i = combo.findData(data)
            if i >= 0:
                combo.setCurrentIndex(i)
        for w in (self._ptype, self._pq):
            w.blockSignals(True)
        _sel(self._ptype, main.get("ptype") or default_ptype)
        _sel(self._pq, main.get("quality") or "m")
        for w in (self._ptype, self._pq):
            w.blockSignals(False)
        self._prof_name.blockSignals(True)
        self._prof_name.setText(main.get("description", "") or "")
        self._prof_name.blockSignals(False)
        self._adv_vals = dict(adv)

    def _sync_colprof_context(self) -> None:
        """On a mode change, save the settings of the context we're leaving and
        load the settings of the one we're entering (Knut, #121)."""
        new = self._colprof_context()
        if new != self._active_ctx:
            self._snapshot_context(self._active_ctx)
            self._active_ctx = new
            self._load_context(new)
        # …and the Advanced section shows the options of the profile now being
        # built, filled in from the settings just loaded.
        self._sync_inline_advanced()
        self._on_colprof_changed()          # refresh cLUT-enable + command preview
        self._mark_default_combos()

    def _save_defaults_clicked(self) -> None:
        # Save the CURRENT context's settings only — each bucket is independent,
        # so unsaved edits made in another context aren't persisted here.
        self._snapshot_context(self._active_ctx)
        stored = self._settings.get("scanner_colprof_configs", {}) or {}
        stored = dict(stored) if isinstance(stored, dict) else {}
        stored[self._active_ctx] = self._ctx_cfg[self._active_ctx]
        self._settings.set("scanner_colprof_configs", stored)
        if getattr(self, "_log", None) is not None:
            self._log.appendPlainText(tr("Profile settings saved as defaults."))
        # Brief in-place confirmation on the button itself.
        btn = self._save_defaults_btn
        btn.setText(tr("Saved ✓"))
        btn.setEnabled(False)
        # A BOUND METHOD, NOT A LAMBDA HOLDING THE BUTTON.
        # `QTimer.singleShot` keeps no owner, so a lambda capturing `btn` stays
        # armed after this dialog is gone — and 1.4 s later it calls setText on
        # a QPushButton whose C++ side has been deleted. Close the scanner
        # window within 1.4 s of pressing "Save as Defaults" and that is a
        # crash. It also fired inside whatever ELSE was running: it was the
        # single intermittent failure in the test gate, landing on a different
        # test each run because it depends on who happens to be pumping events
        # when the timer goes off.
        #
        # A bound method of a QObject is cleaned up with the object, so a dead
        # dialog simply never gets the call. `QTimer.singleShot(msec, context,
        # slot)` — the Qt 5.12 overload that takes an owner — does not exist in
        # PyQt6 (measured: TypeError), so this is the shape to use.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1400, self._restore_save_defaults_button)

    def _restore_save_defaults_button(self) -> None:
        """Put the Save-as-Defaults button back after its "Saved ✓" flash."""
        btn = getattr(self, "_save_defaults_btn", None)
        if btn is None:
            return
        btn.setText(tr("Save as Defaults"))
        btn.setEnabled(True)

    def _on_colprof_changed(self) -> None:
        is_clut = self._ptype.currentData() in scanner_colprof.CLUT_ALGOS
        self._q_label.setEnabled(is_clut)      # quality only applies to a cLUT
        self._pq.setEnabled(is_clut)
        self._update_command_preview()         # persistence is now explicit (Save button)

    def _mark_default_combos(self) -> None:
        """Label the factory-default option in each dropdown "(default)" so the
        user sees at a glance what the default is (Knut, #121). The profile-type
        default is mode-aware — Lab cLUT for a printer, shaper+matrix for a
        scanner — so this is re-run whenever the printer tick changes."""
        printer = self._printer_mode()
        ptype_default = scanner_colprof.PTYPE_DEFAULT[printer]
        for combo, choices, default in (
                (self._ptype, scanner_colprof.PTYPE_CHOICES, ptype_default),
                (self._pq, scanner_colprof.QUALITY_CHOICES, "m")):
            for i, (data, label) in enumerate(choices):
                combo.setItemText(
                    i, tr("{option} (default)").format(option=label)
                    if data == default else label)

    def _effective_adv(self) -> dict:
        """Advanced values for the current mode: printer mode preselects the
        default gamut source, scanner mode strips printer-only options (#121)."""
        from workflow.softproof_runner import argyll_ref_dir
        return scanner_colprof.effective_adv_vals(
            self._adv_vals, self._printer_mode(), argyll_ref_dir(self._settings))

    def _update_command_preview(self) -> None:
        try:
            desc = self._prof_name.text().strip() or tr("<chart name> scanner")
            params = scanner_colprof.make_profile_params(
                Path("<measurements>.ti3"), desc,
                self._current_main_vals(), self._effective_adv())
            args = self._profiler._build_args(params)
            self._cmd_preview.setText("colprof " + " ".join(args))
        except Exception:                       # never let the preview break the UI
            self._cmd_preview.setText("colprof …")

    def _custom_profile_stem(self) -> str | None:
        """The user-chosen profile name as a filesystem-safe stem, or None."""
        import re as _re
        raw = self._prof_name.text().strip()
        if not raw:
            return None
        return _re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw).strip(". ") or None

    def _archive_previous_profile(self, ti3: Path) -> "Path | None":
        """Move a profile this build is about to write over into
        ``old/<date>/`` first, and return the folder it went to.

        Review 5, finding B5: building twice in the same folder replaced the
        first profile in place — no copy, no question, and not a word in the
        log — and it may be one the user has already installed and been
        working against. The measurement beside it went the same way, because
        `_apply_profile_name` copies the read to ``<name>.ti3`` and that copy
        overwrites too. Everywhere else the app archives rather than destroys
        (``runs/run1, run2, …``, ``old/<timestamp>/``, "Deleting moves to the
        Trash"); this window was the exception.

        Called BEFORE `_apply_profile_name`, because by the time that has run
        the measurement has already been overwritten. Both `.icc` and `.icm`
        are looked for, since colprof writes either.

        Only files this build is really about to replace. The read scanin just
        wrote is never archived: it is this build's input, and it is derived
        from the scan anyway.
        """
        stem = self._custom_profile_stem() or ti3.stem
        folder = ti3.parent
        doomed = [folder / (stem + ext) for ext in (".icc", ".icm")]
        named_ti3 = folder / (stem + ".ti3")
        if named_ti3.resolve() != ti3.resolve():
            doomed.append(named_ti3)
        doomed = [p for p in doomed if p.is_file()]
        if not doomed:
            return None
        try:
            from core.file_manager import Run
            dest = Run.for_dir(folder).archive_to_old(doomed)
        except OSError:
            # A read-only volume is not worth failing a build over, but it IS
            # worth not pretending the old profile was kept.
            log.warning("could not archive the profile being replaced",
                        exc_info=True)
            return None
        if dest is None:
            return None
        from workflow import measurement_messages as M
        title, body = M.M_SCAN_PROFILE_ARCHIVED.render(folder=str(dest))
        self._log.appendPlainText(title)
        self._log.appendPlainText(body)
        return dest

    def _restore_archived_profile(self, dest: "Path | None") -> None:
        """Put an archived profile back when the build that displaced it
        failed, so a failed rebuild leaves the folder exactly as it found it.

        The same lesson `Run.reset_chart_artefacts`'s stash was added for: a
        build that is stopped, fails or is interrupted must not leave the user
        with less than they started with.
        """
        if dest is None or not dest.is_dir():
            return
        try:
            import shutil
            for p in sorted(dest.iterdir()):
                back = dest.parent.parent / p.name
                if not back.exists():
                    shutil.move(str(p), str(back))
            if not any(dest.iterdir()):
                dest.rmdir()
                old = dest.parent
                if old.name == "old" and not any(old.iterdir()):
                    old.rmdir()
        except OSError:
            log.warning("could not put the archived profile back", exc_info=True)

    def _apply_profile_name(self, ti3: Path) -> tuple[Path, str | None]:
        """Honour the optional profile name (Nelson): colprof names the .icc
        after its .ti3, so copy *ti3* to ``<name>.ti3`` and return it together
        with the description to embed. Returns (*ti3*, None) when no name was
        given — the caller keeps its defaults."""
        stem = self._custom_profile_stem()
        if not stem:
            return ti3, None
        named = ti3.with_name(stem + ".ti3")
        if named != ti3:
            import shutil
            try:
                shutil.copy2(ti3, named)
            except OSError as exc:
                self._log.appendPlainText(
                    f"[WARN] {tr('Could not apply the profile name: {e}').format(e=exc)}")
                return ti3, self._prof_name.text().strip()
            ti3 = named
        return ti3, self._prof_name.text().strip()

    # ------------------------------------------------------------------ chart
    def _reject_chart(self, reason: str) -> None:
        """Reject the picked chart with *reason* shown in BOTH the chart note
        and the status log — Knut picked a chart, missed the small note, and
        only hit a generic dead-Browse message much later (#101)."""
        self._layout = None
        self._chart_settings: dict = {}
        self._pages = []
        self._chart_reject_reason = reason
        self._chart_note.setText(reason)
        self._log.appendPlainText(reason)
        self._refresh()

    def _pick_chart(self) -> None:
        if self._printer_mode():
            title, flt = tr("Choose the chart you printed"), _CHART_FILTER
        else:
            title, flt = tr("Choose the measured chart"), _TI3_FILTER
        path = open_file_dialog(self, title, flt,
                                start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
                                declutter_settings=self._settings)
        if not path:
            return
        self._set_chart(Path(path))

    def _set_chart(self, picked: Path) -> None:
        import json
        # Honour the file the user actually picked (#101): auto-preferring a
        # sibling .ti3 silently swapped Knut's explicit .ti2 pick for an
        # unrelated scanner .ti3 that happened to share the folder — the field
        # then showed a file he never chose. Only when the picked file itself
        # isn't a chart table (e.g. a "-verify" pick) fall back to the measured
        # .ti3, then the .ti2 (aim values) — a chart you only PRINTED still
        # works for a printer profile; both carry loc + RGB + XYZ.
        base = _chart_base(picked)
        # Forget the previous chart's record first: it decides the sample-area
        # cap, and a honeycomb's answer must not survive into the next chart.
        self._chart_settings = {}
        # A hexagonal chart is turned away unless the user opted in under
        # Preferences → Beta. It profiles correctly — that was measured end to
        # end — but scanin's chart finder can abort on a honeycomb, so the
        # default stays the long-proven behaviour. See `hex_scanner_message`.
        from core.file_manager import nfc
        from workflow.hex_support import (chart_is_hexagonal,
                                          hex_scanner_allowed,
                                          hex_scanner_message)
        if chart_is_hexagonal(base) and not hex_scanner_allowed(self._settings):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, tr("Hexagonal chart"),
                                hex_scanner_message())
            return
        # `base` is a chart STEM (`_chart_base`), which for a dotted project
        # name has a "suffix" pathlib would replace — core/stem_paths.py.
        ti3, ti2 = artefact(base, ".ti3"), artefact(base, ".ti2")
        if (picked.suffix.lower() in (".ti2", ".ti3") and picked.is_file()
                and nfc(picked.stem) == nfc(base.name)):   # not a "-verify" alias pick
            ref = picked
        else:
            ref = ti3 if ti3.is_file() else ti2
        self._chart_measured = ref.suffix.lower() == ".ti3" and ref.is_file()
        self._ti3 = ref
        self._ti3_field.setText(str(ref))
        _remember_dir(self._settings, self.TOOL_KEY, picked.parent)
        self._reset_shots()
        self._reset_byo_cht()               # a fresh chart pick starts over (#105)
        channels = base.with_name(base.name + ".channels.json")
        if not has_scanner_geometry(channels):
            # Recovery (#101): the sidecar may not share the picked file's stem
            # (e.g. only some files were copied out of a run folder, or renamed).
            # If the folder holds exactly one usable .channels.json, take it —
            # a mispairing is still caught later by the loc-alignment check.
            cands = [c for c in sorted(base.parent.glob("*.channels.json"))
                     if has_scanner_geometry(c)]
            if len(cands) == 1:
                channels = cands[0]
            elif self._printer_mode() and ref.is_file():
                # No sidecar at all, but printer mode can take the chart's own
                # printtarg .cht page files instead (#105, Knut's manual charts).
                self._await_byo_cht(base, ref)
                return
            else:
                self._reject_chart(tr(
                    "⚠ No chart layout found: the chart “{name}” has no "
                    ".channels.json with usable geometry next to it. ChromIQ "
                    "writes that sidecar when it creates a chart — pick the "
                    "chart inside its original folder (or copy the "
                    ".channels.json along with it).").format(name=base.name))
                return
        if not ref.is_file():
            self._reject_chart(tr(
                "⚠ This chart has no .ti3 or .ti2 next to it, so ChromIQ can't read "
                "its patch values."))
            return
        _doc = json.loads(read_text(channels))
        self._layout = _doc["layout"]
        # The Create Chart registry travels beside the layout, and it is the
        # only place a printtarg-drawn honeycomb says so (there is no engine
        # recipe on that path) — see `hex_support.settings_are_hexagonal`.
        self._chart_settings = _doc.get("create_chart_settings") or {}
        # A stored printtarg capture whose page count differs from the printed
        # chart is wrong by construction (printtarg -s re-lays some chart
        # types out, e.g. ColorMunki double density) — reject it honestly
        # instead of showing a grid that can never match the scan (#108).
        if self._layout.get("engine") == "printtarg":
            stored = len(self._layout.get("cht_pages") or [])
            from core.file_manager import stem_files
            tifs = stem_files(base.parent, base.name, "_*.tif")
            printed = len(tifs) or (1 if artefact(base, ".tif").is_file() else 0)
            if stored and printed and stored != printed:
                self._layout = None
                # Two independent counts in one sentence, so each is phrased on
                # its own and slotted in — "(s)" would otherwise have to cover
                # a 2x2 of singular/plural.
                _g = (tr("1 recognition page") if stored == 1
                      else tr("{g} recognition pages").format(g=stored))
                _t = (tr("1 printed page") if printed == 1
                      else tr("{t} printed pages").format(t=printed))
                self._reject_chart(tr(
                    "⚠ This chart's stored scan geometry doesn't match the "
                    "chart: {g_pages} for {t_pages}. "
                    "The chart fills its pages right to the limit, and "
                    "printtarg needs slightly more room in scan mode. Reduce "
                    "the Patch Size Scale a little (e.g. 0.90 instead of "
                    "0.93) and regenerate — or use a ChromIQ layout-engine "
                    "chart.").format(g_pages=_g, t_pages=_t))
                return
        # Build the .cht/.cie from the reference (measured .ti3, or .ti2 aim values).
        try:
            build_scanin_target_from_paths(channels, ref, base)
        except ScaninTargetError as exc:
            self._layout = None
            self._reject_chart(f"⚠ {exc}")
            return
        self._chart_geometry_ready()

    def _chart_geometry_ready(self) -> None:
        """Shared success tail of a chart pick: the layout is set and its
        .cht/.cie were written — announce it, fill the page selector and show
        the grid. Used by the channels.json path and the BYO-.cht path (#105).

        In STANDARD mode this only records the layout and the note — the page
        selector always belongs to the selected target type there. (Switching
        to standard mode unchecks "Profile my printer", whose toggle handler
        re-picks the chart and landed here — repopulating the page dropdown
        with the chart's pages inside standard mode; Knut, beta.5. The
        switch back to chart mode rebuilds the selector from the layout.)"""
        if self._layout.get("patches"):                     # engine chart
            chart_pages = sorted({int(p.get("page", 0))
                                  for p in self._layout["patches"]})
            n_patches = len(self._layout["patches"])
        else:                                               # printtarg chart
            chart_pages = list(range(len(self._layout.get("cht_pages", [1]))))
            n_patches = len(self._layout.get("locs") or [])
        if not self._standard_mode():
            self._pages = chart_pages
        self._chart_reject_reason = None             # pick accepted (#101)
        if not self._chart_measured:
            if self._printer_mode():
                # Printer mode is already on — point at the next step instead
                # of asking to tick the checkbox again (#105).
                self._chart_note.setText((
                    tr("✓ {n} patches on one page — pick the scan of the "
                       "printed chart below.")
                    if len(chart_pages) == 1 else
                    tr("✓ {n} patches on {p} pages — pick each page's scan "
                       "below.")).format(n=n_patches, p=len(chart_pages)))
            else:
                self._chart_note.setText(tr(
                    "✓ {n} patches. This chart hasn't been measured — tick “Profile my "
                    "printer from this scan” below to build a printer profile from it "
                    "(no spectrophotometer needed).").format(n=n_patches))
        else:
            self._chart_note.setText((
                tr("✓ Ready — {n} patches on one page.")
                if len(chart_pages) == 1 else
                tr("✓ Ready — {n} patches on {p} pages.")
            ).format(n=n_patches, p=len(chart_pages)))
        if self._standard_mode():
            self._refresh()
            return
        self._page_widget.setVisible(len(self._pages) > 1)
        self._page_combo.blockSignals(True)
        self._page_combo.clear()
        for pg in self._pages:
            self._page_combo.addItem(tr("Page {n}").format(n=pg + 1), pg)
        self._page_combo.blockSignals(False)
        self._page = self._pages[0] if self._pages else 0
        self._shot_idx = 0
        self._load_page_grid()
        self._refresh()

    # ---------------------------------------------- bring-your-own .cht (#105)
    def _reset_byo_cht(self) -> None:
        self._byo_awaiting = False
        self._byo_base = None
        self._byo_ref = None
        self._byo_field.clear()
        self._byo_field.setPlaceholderText(
            tr("provided by the chart (.channels.json)"))

    def _await_byo_cht(self, base: Path, ref: Path) -> None:
        """Printer mode, chart without channels.json: hold the pick and ask for
        printtarg's per-page .cht files instead of rejecting (#105)."""
        self._layout = None
        self._pages = []
        self._byo_awaiting = True
        self._byo_base = base
        self._byo_ref = ref
        msg = tr(
            "This chart wasn't made by ChromIQ (no .channels.json) — that's "
            "fine for a printer profile: pick the .cht page files printtarg "
            "wrote for it under “Chart geometry (.cht)” below.")
        self._chart_reject_reason = "⚠ " + msg
        self._chart_note.setText("⚠ " + msg)
        self._log.appendPlainText("⚠ " + msg)
        self._byo_field.setPlaceholderText(
            tr("pick the chart's .cht page files…"))
        self._refresh()

    def _pick_byo_cht(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        if not self._byo_awaiting or self._byo_base is None:
            self._log.appendPlainText(tr(
                "⚠ This chart already carries its geometry (.channels.json) — "
                "there is nothing to pick. The .cht row is only used for "
                "charts made outside ChromIQ."))
            return
        from ui.widgets import open_files_dialog
        paths = open_files_dialog(
            self, tr("Pick the chart's .cht page files"),
            tr("Chart geometry (*.cht);;All files (*)"),
            start_dir=str(self._byo_base.parent),
            declutter_settings=self._settings)
        if not paths:
            return
        cht_paths = sorted(Path(p) for p in paths)   # printtarg numbers _01…_NN
        from workflow.scanin_target import build_scanin_target_from_cht_files
        try:
            layout, res = build_scanin_target_from_cht_files(
                cht_paths, self._byo_ref, self._byo_base)
        except ScaninTargetError as exc:
            self._byo_field.clear()
            self._reject_chart(f"⚠ {exc}")
            # Stay in the awaiting state so another pick can succeed.
            self._byo_awaiting = True
            return
        self._byo_field.setText(", ".join(p.name for p in cht_paths))
        self._byo_awaiting = False
        self._layout = layout
        self._log.appendPlainText(
            (tr("✓ Chart geometry loaded from 1 .cht file — {p} patches "
                "verified against the chart.").format(p=res.n_patches)
             if len(cht_paths) == 1 else
             tr("✓ Chart geometry loaded from {n} .cht files — {p} patches "
                "verified against the chart.").format(n=len(cht_paths),
                                                      p=res.n_patches)))
        self._chart_geometry_ready()

    def _load_page_grid(self) -> None:
        if self._standard_mode():
            # Each page of a multi-page set has its own locked .cht — swap the
            # current grid to it, then show the page's scan/placement.
            self._sync_std_page()
            self._sync_shot_view()
            self._update_std_note()
            return
        if self._layout is None:
            return
        pg = self._page
        # Engine charts have exact per-patch rects; printtarg charts carry a
        # captured .cht per page — both render a grid overlay (the .cht is parsed
        # into the fiducial frame just like a standard target).
        patches = [p for p in self._layout.get("patches", [])
                   if int(p.get("page", 0)) == pg]
        if patches:
            # The cells take the patch's own shape; the sampled rectangle
            # inside them is unchanged, which is what the CHT carries. The
            # recipe is already in the layout this method holds — reaching for
            # the chart path here raised NameError on EVERY engine chart,
            # rectangular ones included, because `base` belongs to the loader.
            from workflow.hex_support import (recipe_is_hexagonal,
                                              settings_are_hexagonal)
            # Two records, because two chart paths. The engine writes a recipe;
            # a printtarg honeycomb has none — its geometry is derived from the
            # rendered sheet (printtarg will not emit a .cht for hexagons at
            # all) — and only the Create Chart registry remembers the shape.
            hexagonal = (recipe_is_hexagonal(self._layout.get("recipe"))
                         or settings_are_hexagonal(
                             getattr(self, "_chart_settings", None)))
            self._marquee.set_grid(GridSpec.from_patches(patches,
                                                         hexagonal=hexagonal))
            self._clamp_sample_area(patches, hexagonal)
        else:
            cht_pages = self._layout.get("cht_pages") or []
            self._marquee.set_grid(
                GridSpec.from_cht(cht_pages[pg]) if 0 <= pg < len(cht_pages)
                else GridSpec([]))
            # A captured .cht is never hexagonal: printtarg refuses to make
            # one ("Can only select hexagonal patches if no scan recognition is
            # needed - ignored!"), so the capture describes a re-laid-out square
            # chart, its locs disagree with the .ti2 and ChromIQ's guard drops
            # it. Full 80 % here is the right answer, not an oversight.
            self._clamp_sample_area([], False)
        self._sync_shot_view()

    def _clamp_sample_area(self, patches: list[dict], hexagonal: bool) -> None:
        """Cap Sample area at what THIS chart's patches can actually give.

        A hexagon's slanted top and bottom cut the corners off the rectangle the
        patch is stored as, so the sampled square escapes it much sooner than on
        a square patch — and because the neighbour is flush against it, that is a
        switch, not a rate: every patch reads its neighbour at once. The ceiling
        depends on the patch proportions (64 % on a regular hexagon, 61 % at
        h/w = 2, and 60 % is already unsafe from h/w ≈ 2.58), so it is computed
        here rather than written down as a number. Rectangular charts keep 80 %."""
        from workflow.scanin_runner import hex_max_sample_fraction
        cap = 80
        if hexagonal and patches:
            ws = sorted(float(p["w"]) for p in patches if float(p.get("w", 0)) > 0)
            hs = sorted(float(p["h"]) for p in patches if float(p.get("h", 0)) > 0)
            if ws and hs:
                frac = hex_max_sample_fraction(ws[len(ws) // 2], hs[len(hs) // 2])
                cap = max(20, min(80, int(frac * 100.0)))   # floor: never round UP
        if cap != self._sample_area.maximum():
            # setMaximum pulls a too-large value down and emits valueChanged, so
            # the marquee and every read follow without extra wiring.
            self._sample_area.setMaximum(cap)
        self._sample_area.setToolTip(
            tr("Hexagonal patches: {cap} % is the most this chart can be read "
               "at. Above it the sampled square reaches past the hexagon's "
               "slanted sides into the neighbouring patches.").format(cap=cap)
            if cap < 80 else "")

    def _on_page_changed(self, idx: int) -> None:
        self._capture_current_corners()
        if 0 <= idx < len(self._pages):
            self._page = self._pages[idx]
            self._shot_idx = 0
            self._load_page_grid()

    def _capture_current_corners(self) -> None:
        if self._marquee.has_placement():
            shot = self._cur_shot()
            shot["corners"] = self._marquee.corners_image_px()
            # …and the image they were placed on. Corners are absolute pixels,
            # so without this they are meaningless on any other scan — see
            # `_apply_shot_corners`.
            shot["corners_size"] = self._marquee.image_size()

    def _apply_shot_corners(self, shot: dict) -> None:
        """Put this shot's remembered corners on the image now loaded, scaled
        to it if it is a different size.

        Review 5, finding A3: placing the grid on a 300 dpi scan and then
        picking a 1200 dpi re-scan of the same target — the most ordinary thing
        a user does after a first attempt reads badly — applied the 300 dpi
        scan's ABSOLUTE pixel corners to the bigger image, so the grid
        collapsed into the top-left quarter and nothing was said. Measured:
        (71,158)…(2170,1473) on a 2241x1544 image, reused unchanged on an
        8962x6173 one, where the truth is (283,633)…(8679,5890).

        `_restore_placement`, one branch below the offending line, had it right
        all along — it stores fractions of the image size, and `_save_placement`
        promises in its own docstring that a placement can be reused "on a
        future scan of the same target at any resolution". The two paths
        disagreed and the wrong one won. This is that same arithmetic, so the
        grid lands where the user put it whatever the scan's size, and there is
        nothing new to say to them.
        """
        corners = shot.get("corners")
        if not corners:
            return
        was = shot.get("corners_size")
        now = self._marquee.image_size()
        if (was and now and all(was) and all(now) and tuple(was) != tuple(now)):
            fx, fy = now[0] / was[0], now[1] / was[1]
            corners = [(x * fx, y * fy) for x, y in corners]
            shot["corners"] = corners
            shot["corners_size"] = now
        self._marquee.set_corners(corners)

    # -------------------------------------------------- remembered placement
    def _target_key(self) -> str | None:
        """A stable key for the current target, so its last grid placement can be
        restored next session. Standard targets key on the .cht stem; ChromIQ
        charts key on the chart stem."""
        if self._standard_mode():
            return f"std:{self._std_cht.stem}" if self._std_cht else None
        return f"chart:{self._ti3.stem}" if self._ti3 else None

    def _remember_accepted_placement(self) -> None:
        """Store the grid for next time, once this build is really going ahead.

        Called from both builders after every warning window has been answered,
        so the placement kept is the one the user accepted — never one they
        stopped."""
        self._save_placement()

    def _save_placement(self) -> None:
        """Store the current grid as fractions of the image size, keyed by target,
        so it can be reused on a future scan of the same target at any resolution."""
        key = self._target_key()
        w, h = self._marquee.image_size()
        if not key or not w or not h or not self._marquee.has_placement():
            return
        norm = [[x / w, y / h] for x, y in self._marquee.corners_image_px()]
        places = dict(self._settings.get("scanin_grid_placements", {}) or {})
        places[key] = norm
        self._settings.set("scanin_grid_placements", places)

    def _restore_placement(self) -> bool:
        """Apply the remembered placement for this target to the loaded image
        (scaled to its size). Returns True if one was applied."""
        key = self._target_key()
        w, h = self._marquee.image_size()
        if not key or not w or not h:
            return False
        norm = (self._settings.get("scanin_grid_placements", {}) or {}).get(key)
        if not norm or len(norm) != 4:
            return False
        self._marquee.set_corners([(fx * w, fy * h) for fx, fy in norm])
        return True

    # ------------------------------------------------------------- mode/standard
    def _on_mode_changed(self, _checked: bool = False) -> None:
        std = self._standard_mode()
        self._chromiq_box.setVisible(not std)
        self._standard_box.setVisible(std)
        # ChromIQ charts carry no fiducial marks, so hide the option and force it
        # off — the same align-the-patches / derive-the-F process is used either
        # way. (Shows again automatically for standard targets that have marks.)
        self._use_fiducials_cb.setVisible(std)
        if not std:
            self._use_fiducials_cb.setChecked(False)
        self._reset_shots()
        self._scan_field.setText("")
        self._marquee.set_image(QImage())
        if std:
            self._pages = [0]
            self._page = 0
            self._page_widget.setVisible(False)
            self._on_target_changed()   # sets pages/selector for the current target
        else:
            self._std_grid = None
            if self._layout is not None:
                # Restore the chart's own page list — the standard-mode visit
                # collapsed it to one page (a 3-page chart came back showing
                # only page 1 otherwise).
                if self._layout.get("patches"):
                    self._pages = sorted({int(pp.get("page", 0))
                                          for pp in self._layout["patches"]})
                else:
                    self._pages = list(range(len(
                        self._layout.get("cht_pages", [1]))))
                self._page = self._pages[0] if self._pages else 0
                self._page_combo.blockSignals(True)
                self._page_combo.clear()
                for pg in self._pages:
                    self._page_combo.addItem(tr("Page {n}").format(n=pg + 1), pg)
                self._page_combo.blockSignals(False)
                self._page_widget.setVisible(len(self._pages) > 1)
                self._load_page_grid()
            else:
                self._marquee.set_grid(GridSpec([]))
        # Printer mode is only meaningful with a ChromIQ chart (needs its .ti2).
        self._printer_cb.setVisible(not std)
        if std:
            self._printer_cb.setChecked(False)
        # A standard-target scanner profile and a ChromIQ-chart scanner profile
        # keep separate settings, so switching target kind loads the right bucket
        # (Knut, #121).
        self._sync_colprof_context()
        self._apply_mode_title()
        self._refresh_shot_bar()
        self._refresh()

    def _printer_mode(self) -> bool:
        """True when building a PRINTER profile from this scan (scanner as the
        instrument) — only offered for a ChromIQ chart, which carries the .ti2."""
        return not self._standard_mode() and self._printer_cb.isChecked()

    def _on_printer_toggled(self, checked: bool) -> None:
        self._printer_box.setVisible(checked)
        # The Chart-geometry (.cht) row only matters in printer mode (#105).
        self._byo_row_w.setVisible(checked)
        self._refresh_shot_bar()   # averaging affordances hide in printer mode
        # In printer mode the chart's .ti2 is enough (no measurement needed), so the
        # picker asks for the chart you printed rather than a measured .ti3.
        self._chart_label.setText(
            tr("Chart you printed (.ti2):") if checked else tr("Measured chart (.ti3):"))
        self._ti3_field.setPlaceholderText(
            tr("Pick the chart you printed (.ti2)…") if checked else
            tr("Pick the measured chart (.ti3)…"))
        # Ticking printer mode AFTER a sidecar-less chart was picked (and thus
        # rejected) re-evaluates it, so the BYO-.cht offer appears without
        # re-picking the chart (#105). Nothing to lose: the layout is unset.
        if (checked and self._layout is None and not self._byo_awaiting
                and self._ti3 is not None and Path(self._ti3).is_file()):
            self._set_chart(Path(self._ti3))
        # The field shows the file the MODE actually consumes: printer mode
        # reads the chart's .ti2, scanner mode its measured .ti3 — a
        # pre-filled .ti3 in printer mode read like the wrong input (Knut).
        elif self._ti3 is not None:
            want = Path(self._ti3).with_suffix(".ti2" if checked else ".ti3")
            if want.is_file() and want != Path(self._ti3):
                self._set_chart(want)
        # The colprof settings (type, quality, description, Advanced) are stored
        # per context, so switching printer ON/OFF loads that context's own
        # remembered settings — a printer profile and a scanner profile are
        # different things (Knut, #121).
        self._sync_colprof_context()
        self._update_command_preview()
        self._apply_mode_title()
        self._refresh()

    def _apply_mode_title(self) -> None:
        """Masthead / window title / build button track what's being built —
        a printer profile, or a scanner/camera profile (Knut, #121)."""
        title = (tr("Build printer profile") if self._printer_mode()
                 else tr("Build profile with scanner or camera"))
        self._run_btn.setText(title)
        self.setWindowTitle(title)
        if getattr(self, "_header", None) is not None:
            self._header.set_texts(self.EYEBROW, title)

    def _pick_scanner_profile(self) -> None:
        start = str(self._printer_scan_profile.parent) if self._printer_scan_profile \
            else self._settings.get("tools_last_dir_scanner_profile", "")
        # ChromIQ's file dialog (sidebar shortcuts incl. ~/ChromIQ, extension
        # filtering) — and it honours the native-dialogs setting by itself.
        p = open_file_dialog(
            self, tr("Pick the scanner profile (.icc) you built earlier"),
            tr("ICC profiles (*.icc *.icm);;All files (*)"), start_dir=start,
            extra_path=str(self._ti3.parent) if getattr(self, "_ti3", None) else "")
        if p:
            self._printer_scan_profile = Path(p)
            self._printer_prof_field.setText(p)
            self._refresh()

    def _on_target_changed(self, _idx: int = 0) -> None:
        key = self._target_combo.currentData()
        other = not key
        self._cht_row_w.setVisible(other)
        self._demo_btn.setEnabled(not other)
        if other:
            txt = self._cht_field.text()
            self._set_std_targets([Path(txt)] if txt else [])
        else:
            target = self._std_targets.get(key)
            self._set_std_targets(list(target.cht_paths) if target else [])

    def _reveal_target_files(self) -> None:
        """Generate a synthetic demo scan + matching reference from the selected
        target's ``.cht`` and load them into the dialog, so the grid (and the whole
        read → build) can be tried with no hardware. It is a practice image (each
        patch a flat colour), NOT a real target scan — the same known-colour pair
        the automated tests use to confirm scanin reads correctly."""
        if not self._std_chts:
            self._log.appendPlainText(tr("Pick a bundled target above first."))
            return
        from workflow.standard_targets import (
            make_multipage_test_scans, make_test_scan)
        out = user_targets_dir(self._settings)
        try:
            if len(self._std_chts) > 1:
                tifs, ref = make_multipage_test_scans(self._std_chts, out)
            else:
                tif, ref = make_test_scan(self._std_chts[0], out)
                tifs = [tif]
        except Exception as exc:  # noqa: BLE001
            self._log.appendPlainText(
                tr("Couldn't prepare the demo scan: {e}").format(e=exc))
            return
        # Load one demo scan into each page's first shot; a multi-page set gets a
        # demo per page and the one merged reference covering them all.
        for pg, tif in zip(self._pages, tifs):
            self._page_shots(pg)[0]["path"] = tif
        self._std_ref = ref
        self._ref_field.setText(str(ref))
        self._ref_converted_note = ""
        self._shot_idx = 0
        self._load_page_grid()                         # grid + current page's scan
        cur = self._cur_shot()
        if cur["path"] and not cur["corners"] and self._restore_placement():
            cur["corners"] = self._marquee.corners_image_px()
        self._update_std_note()
        self._refresh_shot_bar()
        self._refresh()
        pages_note = (tr(" (one demo scan per page — switch pages with the Page "
                         "selector)") if len(self._std_chts) > 1 else "")
        self._log.appendPlainText(tr(
            "Loaded a demo scan + reference to practise on.{pages} This is a "
            "synthetic image ChromIQ drew from the target's recognition file — "
            "each patch a flat colour — NOT a real target. Place the grid and "
            "Build to see the read work end-to-end.\n"
            "For a real profile, load your own scan (.tif) and the reference "
            "(.cie) that came with your physical target instead.").format(
                pages=pages_note))

    def _pick_cht(self) -> None:
        path = open_file_dialog(self, tr("Choose a .cht recognition file"),
                                _CHT_FILTER,
                                start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
                                declutter_settings=self._settings)
        if not path:
            return
        self._cht_field.setText(path)
        _remember_dir(self._settings, self.TOOL_KEY, Path(path).parent)
        self._set_std_targets([Path(path)])

    def _convert_dir(self) -> Path:
        if self._convert_tmp is None:
            import tempfile
            # Owned, so it goes when the dialog does — it accumulated every
            # converted reference for the dialog's life and was never removed.
            self._convert_tmp_holder = tempfile.TemporaryDirectory(
                prefix="chromiq-ref-")
            self._convert_tmp = Path(self._convert_tmp_holder.name)
        return self._convert_tmp

    def _pick_ref(self) -> None:
        path = open_file_dialog(self, tr("Choose the target reference data"),
                                _REF_FILTER,
                                start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
                                declutter_settings=self._settings)
        if not path:
            return
        p = Path(path)
        _remember_dir(self._settings, self.TOOL_KEY, p.parent)
        from workflow.reference_convert import (
            ReferenceConvertError, ReferenceKind, classify_reference,
            convert_reference)
        self._ref_converted_note = ""
        if classify_reference(p) is ReferenceKind.DIRECT:
            self._std_ref = p
        else:
            # A .cxf or raw/spectral .txt — convert it with Argyll for the user.
            self._std_note.setText(tr("Converting {name} to a reference file…")
                                   .format(name=p.name))
            QApplication.processEvents()
            try:
                self._std_ref = convert_reference(
                    p, self._settings.get("argyll_bin_path", ""), self._convert_dir())
            except ReferenceConvertError as exc:
                self._std_ref = None
                self._ref_field.setText("")
                self._std_note.setText(f"⚠ {exc}")
                self._refresh()
                return
            self._ref_converted_note = tr(
                "Converted “{name}” to a reference ChromIQ can read.").format(name=p.name)
        self._ref_field.setText(str(p))
        self._update_std_note()
        self._refresh()
        cov = self._reference_shortfall()
        if cov is not None:
            self._warn_short_reference(cov)

    def _set_std_targets(self, chts: list[Path]) -> None:
        """Select a standard target: one ``.cht`` for an ordinary target, or one
        per page for a multi-page set (each locked to its page). Sets up the page
        selector and shows the current page's grid."""
        chts = [Path(c) for c in chts if c]
        changed = (self._std_chts
                   and [Path(c) for c in chts] != [Path(c) for c in self._std_chts])
        self._std_chts = chts
        self._pages = list(range(len(chts))) if chts else [0]
        if self._page not in self._pages:
            self._page = self._pages[0] if self._pages else 0
        self._page_combo.blockSignals(True)
        self._page_combo.clear()
        for pg in self._pages:
            self._page_combo.addItem(tr("Page {n}").format(n=pg + 1), pg)
        if self._pages:
            self._page_combo.setCurrentIndex(self._pages.index(self._page))
        self._page_combo.blockSignals(False)
        self._page_widget.setVisible(len(self._pages) > 1)
        if changed:
            # A different target type has different geometry: previous placements
            # are meaningless on it, and any DEMO scans belong to the previous
            # target outright (Knut: switching types kept showing the old grid,
            # clearest with Try-a-demo between types). Clear every page.
            self._reset_shots()
            demo_dir = user_targets_dir(self._settings)
            self._scan_field.setText("")
            self._marquee.set_image(QImage())
            if self._std_ref and demo_dir in Path(self._std_ref).parents:
                self._std_ref = None
                self._ref_field.setText("")
        self._sync_std_page()
        if not self._fiducials_available() and self._use_fiducials_cb.isChecked():
            self._use_fiducials_cb.setChecked(False)   # new target has no fiducials
        self._update_std_note()
        self._refresh_shot_bar()
        self._refresh()

    def _sync_std_page(self) -> None:
        """Point ``_std_cht`` / ``_std_grid`` (and the marquee grid) at the page
        currently shown, so the rest of the standard-mode code stays page-agnostic."""
        chts = self._std_chts
        if not chts or not (0 <= self._page < len(chts)) or not chts[self._page].is_file():
            self._std_cht = chts[self._page] if 0 <= self._page < len(chts) else None
            self._std_grid = None
            self._marquee.set_grid(GridSpec([]))
            return
        self._std_cht = chts[self._page]
        self._rebuild_std_grid()

    def _rebuild_std_grid(self) -> None:
        """(Re)build the standard-target grid from the current .cht. The marquee
        **always** frames the patch block (the reliable, always-visible reference);
        the "Use fiducial marks" option no longer changes the grid — it only
        changes how scanin's ``-F`` is derived from this one alignment
        (:meth:`_scanin_corners`). Keeps the current scan's placement."""
        if not self._standard_mode() or self._std_cht is None:
            return
        self._capture_current_corners()
        try:
            self._std_grid = GridSpec.from_cht(read_text(self._std_cht, lenient=True))
        except OSError:
            self._std_grid = GridSpec([])
        self._marquee.set_grid(self._std_grid)
        self._marquee.set_show_fiducials(self._use_fiducials_cb.isChecked())
        if self._cur_shot()["corners"]:               # set_grid re-seeds — restore
            self._marquee.set_corners(self._cur_shot()["corners"])

    def _fiducials_available(self) -> bool:
        if not self._standard_mode() or self._std_cht is None:
            return False
        from ui.scan_grid_marquee import cht_has_fiducials
        try:
            return cht_has_fiducials(read_text(self._std_cht, lenient=True))
        except OSError:
            return False

    def _on_fiducial_toggled(self, checked: bool) -> None:
        if checked and not self._fiducials_available():
            self._blink_widget(self._use_fiducials_cb)   # "not available" feedback
            self._use_fiducials_cb.blockSignals(True)
            self._use_fiducials_cb.setChecked(False)
            self._use_fiducials_cb.blockSignals(False)
            return
        # The marquee stays on the patch grid; toggling only draws the fiducial
        # frame and changes how the scanin -F is derived at build time.
        self._marquee.set_show_fiducials(checked)
        self._update_std_note()

    def _reframe_marquee(self, to_fiducial: bool) -> None:
        """Grow the marquee out to the fiducial marks (or back to the patch area),
        keeping the patches on the same image spot — so ticking the box visibly
        adds the fiducial band around the patch grid."""
        if self._std_cht is None:
            return
        from ui.scan_grid_marquee import fiducial_frame
        from workflow.cht_parser import ChtParseError, parse_cht
        txt = read_text(self._std_cht, lenient=True)
        fr = fiducial_frame(txt)
        if fr is None:
            return
        try:
            g = parse_cht(txt)
        except ChtParseError:
            return
        xs = [b.x1 for b in g.patches] + [b.x2 for b in g.patches]
        ys = [b.y1 for b in g.patches] + [b.y2 for b in g.patches]
        px0, px1, py0, py1 = min(xs), max(xs), min(ys), max(ys)
        fx0, fx1, fy0, fy1 = fr
        self._marquee.reframe(px0 - fx0, py0 - fy0, fx1 - px1, fy1 - py1,
                              px1 - px0, py1 - py0, to_fiducial)

    def _blink_widget(self, w) -> None:
        """Flash a widget red twice to say "can't enable that" (Knut).

        THE TIMER IS PARENTED TO THE WIDGET IT FLASHES. `QTimer.singleShot`
        keeps no owner, so a chain of them kept this dialog blinking a widget
        for 800 ms after it could have been closed — and `setStyleSheet` on a
        deleted C++ object raises. A child QTimer is destroyed with its parent,
        so closing the window simply stops the flash.
        """
        from PyQt6.QtCore import QTimer
        orig = w.styleSheet()
        # The flash is MOTION, which greyscale keeps in full. Neutral swaps
        # the red for ACTION at bold weight so the blink still reads.
        from ui.theme import APPEARANCE_NEUTRAL as _NEU, active_mode as _am
        _flash = ("QCheckBox{color:%s;font-weight:700;}"
                  % __import__("ui.neutral_styles", fromlist=["x"]).NM_ACTION
                  if _am() == _NEU else "QCheckBox{color:#d9534f;}")
        seq = [_flash, orig] * 2
        timer = QTimer(w)                    # dies with the widget
        timer.setInterval(200)
        state = {"i": 0}

        def step() -> None:
            i = state["i"]
            if i >= len(seq):
                timer.stop()
                return
            w.setStyleSheet(seq[i])
            state["i"] = i + 1

        timer.timeout.connect(step)
        step()
        timer.start()

    def _chart_ids(self) -> "set[str] | None":
        """Every patch id the chosen target reads, across all its pages.

        The union, not one page's, because a reference file covers the whole
        target: judging a three-page ISO 12641-2 set against page 1 alone would
        call two thirds of a perfectly good reference "extra".
        """
        chts = self._std_chts if self._standard_mode() else []
        ids: set[str] = set()
        for c in chts:
            got = page_ids_from_cht(c)
            if got is None:
                return None
            ids |= got
        return ids or None

    def _reference_shortfall(self):
        """The chosen reference measured against the chosen target, or None.

        None where there is nothing to judge — no target, no reference, a file
        neither side can parse. **A check that cannot see must not accuse**:
        the cost of one false alarm here is a user who then clicks past the
        real one.
        """
        if not self._standard_mode() or self._std_ref is None:
            return None
        from workflow.scan_read_check import reference_coverage
        try:
            cov = reference_coverage(Path(self._std_ref), self._chart_ids())
        except Exception:  # noqa: BLE001 — a sanity check never blocks a pick
            log.warning("reference coverage check failed", exc_info=True)
            return None
        floor = float(self._settings.get("scanner_min_coverage", 0.97))
        return cov if (cov is not None and cov.is_short(floor)) else None

    def _short_reference_message(self, cov):
        """§M M-SCAN-REF-SHORT, rendered. PROPOSED wording — see
        `docs/design/unified_measurement_management.md` §M-PROPOSED."""
        from workflow import measurement_messages as M
        return M.M_SCAN_REF_SHORT.render(
            covered=cov.covered, total=cov.chart_patches, missing=cov.missing)

    def _warn_short_reference(self, cov) -> None:
        """Say it at the moment the reference is picked, where the user can
        still fix it by choosing another file — rather than after a read that
        has already thrown five sixths of the sheet away (review 5, finding D).
        """
        from PyQt6.QtWidgets import QMessageBox
        title, body = self._short_reference_message(cov)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()

    def _update_std_note(self) -> None:
        if not self._std_chts or self._std_cht is None:
            self._std_note.setText("")
            return
        n = len(self._std_grid.rects) if self._std_grid else 0
        multi = len(self._std_chts) > 1
        if n == 0:
            self._std_note.setText(tr(
                "⚠ Couldn't read this target's patch grid from the .cht."))
        elif self._std_ref is None:
            if multi:
                self._std_note.setText(tr(
                    "✓ Multi-page target: {pages} pages, {n} patches on this "
                    "page. Now choose the one reference data file that came with "
                    "your target — it covers every page.").format(
                        pages=len(self._std_chts), n=n))
            else:
                self._std_note.setText(tr(
                    "✓ {n} patches. Now choose the reference data file that came "
                    "with your target.").format(n=n))
        else:
            if multi:
                done = sum(1 for pg in self._pages if self._page_ready(pg))
                msg = tr("✓ Ready — {pages}-page target, reference loaded. Scan "
                         "each page and place the corners on its marks "
                         "({done} of {pages} pages ready).").format(
                             pages=len(self._std_chts), done=done)
            else:
                msg = tr("✓ Ready — {n} patches, reference loaded. Scan the "
                         "target and place the corners on its registration "
                         "marks.").format(n=n)
            if self._ref_converted_note:
                msg += "  " + self._ref_converted_note
            # The green tick is the lie in review 5's finding D: "Ready — 288
            # patches, reference loaded" is the .cht's count with the word
            # "reference" beside it, and it stayed green while the reference
            # named 48 of them. When it does, the line says so instead, in the
            # message's own headline so every word the user reads is §M's.
            cov = self._reference_shortfall()
            if cov is not None:
                msg = "⚠ " + self._short_reference_message(cov)[0]
            self._std_note.setText(msg)

    # ------------------------------------------------------------------ scan
    def _toggle_popout(self) -> None:
        """Open the grid in a separate, resizable window for a bigger view — or
        dock it back. The same marquee moves between the two windows, so the
        placement, zoom and rotation are preserved. The pop-out carries its own
        Rotate / Reset controls and a Done button; you build the profile back in
        the main window (placement is kept automatically)."""
        if getattr(self, "_popout", None) is not None:
            self._popout.close()
            return
        self._popout = QDialog(self)
        self._popout.setWindowTitle(tr("Place the grid — bigger view"))
        self._popout.setModal(False)
        v = QVBoxLayout(self._popout)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        self._marquee_box.removeWidget(self._marquee)
        self._marquee.set_wheel_zoom(True)       # plain scroll zooms in the pop-out
        v.addWidget(self._marquee, 1)
        bar = QHBoxLayout()
        rot = QPushButton(tr("⟳ Rotate 90°"), self._popout)
        rot.clicked.connect(self._marquee.rotate_90)
        rst = QPushButton(tr("Reset view"), self._popout)
        rst.clicked.connect(self._marquee._reset_view)
        note = QLabel(tr("Placement is saved automatically — click Done, then "
                         "build the profile in the main window."), self._popout)
        note.setStyleSheet("color:#8a8a8a; font-size:11px;")
        done = QPushButton(tr("Done"), self._popout)
        done.clicked.connect(self._popout.close)
        for _b in (rot, rst):
            _b.setStyleSheet(_COMPACT_BTN)
        # The pop-out is its own window, so it doesn't inherit the dialog's green
        # accent — the global "primary" style would make Done blue. Paint it green
        # (the scanner/measure family colour) explicitly.
        _done_bg = accent_for(SPEC_GREEN)
        done.setStyleSheet(
            "QPushButton {"
            f"  background: {_done_bg}; color: {primary_label()}; border: none;"
            "   border-radius: 6px; padding: 3px 22px; min-height: 0;"
            "   font-size: 11px; font-weight: 600; }"
            f"QPushButton:hover {{ background: {primary_hover(_done_bg, None, 0.86)}; }}"
            f"QPushButton:pressed {{ background: {primary_hover(_done_bg, None, 0.72)}; }}")
        bar.addWidget(rot)
        bar.addWidget(rst)
        bar.addStretch(1)
        bar.addWidget(note)
        bar.addStretch(1)
        bar.addWidget(done)
        v.addLayout(bar)
        self._marquee_placeholder.setVisible(True)
        self._popout_btn.setText(tr("⤢ Dock back"))
        self._rotate_btn.setEnabled(False)
        self._reset_btn.setEnabled(False)
        self._reset_grid_btn.setEnabled(False)
        self._popout.resize(1200, 940)
        self._popout.finished.connect(lambda _=0: self._dock_marquee())
        self._popout.show()
        self._popout.raise_()
        self._popout.activateWindow()

    def _dock_marquee(self) -> None:
        pop = getattr(self, "_popout", None)
        if pop is None:
            return
        self._marquee.setParent(None)            # detach from the pop-out layout
        self._marquee.set_wheel_zoom(False)
        self._marquee_box.insertWidget(0, self._marquee)
        self._marquee_placeholder.setVisible(False)
        self._popout_btn.setText(tr("⤢ Pop out for a bigger view"))
        self._rotate_btn.setEnabled(True)
        self._reset_btn.setEnabled(True)
        self._reset_grid_btn.setEnabled(True)
        self._marquee._reset_view()              # main view returns fully zoomed-out
        self._popout = None
        pop.deleteLater()

    def _pick_scan(self) -> None:
        ready = (self._std_cht is not None if self._standard_mode()
                 else self._layout is not None)
        if not ready:
            # Don't fail silently — Knut hit a dead Browse button because his .ti3
            # wasn't a ChromIQ engine chart. Say what to do, in the status box —
            # matching the active mode (the old text demanded a .ti3 even in
            # printer mode, where the .ti2 is the right file, #101) and repeating
            # why a picked chart was rejected instead of a generic hint.
            if self._byo_awaiting and self._printer_mode():
                self._log.appendPlainText(tr(
                    "⚠ Pick the chart's .cht page files first — the “Chart "
                    "geometry (.cht)” row above — then choose the scan."))
            elif self._chart_reject_reason and not self._standard_mode():
                self._log.appendPlainText(tr(
                    "⚠ The chart you picked can't be used — fix that first, then "
                    "choose the scan. The problem was:"))
                self._log.appendPlainText(self._chart_reject_reason)
            elif self._standard_mode():
                self._log.appendPlainText(tr(
                    "⚠ Choose your target first, then the scan: load the "
                    "target's .cht reference file above."))
            elif self._printer_mode():
                self._log.appendPlainText(tr(
                    "⚠ Choose your chart first, then the scan: pick the .ti2 of "
                    "the chart you printed (ChromIQ wrote it, with its "
                    ".channels.json, into the chart's folder when you created "
                    "the chart)."))
            else:
                self._log.appendPlainText(tr(
                    "⚠ Choose your target first, then the scan. Under “A chart I "
                    "made in ChromIQ”, pick the .ti3 of a chart you built here (it "
                    "needs its .channels.json alongside). An older .ti3 from a "
                    "plain scanin run won't work — for a bought target, switch to "
                    "“A standard target I own” above and load its .cht."))
            return
        path = open_file_dialog(self, tr("Choose the scan"), _SCAN_FILTER,
                                start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
                                declutter_settings=self._settings)
        if not path:
            return
        self._cur_shot()["path"] = Path(path)
        self._scan_field.setText(path)
        _remember_dir(self._settings, self.TOOL_KEY, Path(path).parent)
        img = _load_scan_qimage(path)
        self._marquee.set_image(img)
        if img.isNull():
            # Never leave the user staring at an empty marquee without a word —
            # without a preview the grid can't be aligned (#108).
            self._log.appendPlainText(tr(
                "⚠ This scan couldn't be decoded for the preview, so the grid "
                "can't be aligned on it. Re-save the scan as an 8-bit TIFF (or "
                "PNG) and pick it again."))
        if self._cur_shot()["corners"]:
            self._apply_shot_corners(self._cur_shot())
        elif self._restore_placement():          # reuse last session's placement
            self._cur_shot()["corners"] = self._marquee.corners_image_px()
            self._cur_shot()["corners_size"] = self._marquee.image_size()
        self._refresh_shot_bar()
        self._refresh()

    # ------------------------------------------------------------------ run
    def _can_run(self) -> bool:
        if self._standard_mode():
            return (bool(self._std_chts) and self._std_ref is not None
                    and self._std_grid is not None and bool(self._std_grid.rects)
                    and all(self._page_ready(pg) for pg in self._pages))
        if self._printer_mode() and self._printer_scan_profile is None:
            return False                         # printer mode needs a scanner ICC
        if not self._printer_mode() and not self._chart_measured:
            return False                         # a scanner profile needs a real .ti3
        return self._layout is not None and bool(self._pages) and all(
            self._page_ready(pg) for pg in self._pages)

    def _files_for_page(self, pg: int, base: Path) -> tuple[Path, Path]:
        """The (.cht, reference) pair for page *pg*: the chosen standard target,
        or the chart's own per-page .cht + .cie."""
        if self._standard_mode():
            cht = (self._std_chts[pg] if 0 <= pg < len(self._std_chts)
                   else self._std_cht)
            return cht, self._std_ref
        single = len(self._pages) == 1
        cht = (artefact(base, ".cht") if single
               else base.parent / f"{base.name}_{pg + 1:02d}.cht")
        return cht, artefact(base, ".cie")

    def _prepare_scanin_cht(self, orig_cht: Path, corners, frac: float,
                            base: Path, tag: str) -> Path:
        """The cht scanin reads for one scan: (1) reposition the boxes onto
        rectarg's integer edges for this scan's patch-area pixel size, so the
        interior lines up with a rounded rectarg image the same way the on-screen
        grid does; (2) fiducial-frame; (3) sample-area. One shared calculation for
        the marquee and scanin. Falls back to the original layout if the boxes
        aren't a uniform grid or the scan is too small to round."""
        cht = orig_cht
        # Sweep the prepared files an EARLIER release left next to a ChromIQ
        # chart before writing this run's set: their naming scheme changed
        # between betas, so a stale one (old sample area, even an old y-up F
        # line) can sit beside the current files and mislead anyone
        # inspecting the folder — Knut's #119 chart carried a months-old
        # "-sample.cht" whose read zone matched nothing the current release
        # does. (Standard targets never get prepared files written next to
        # the bundled .cht, so there is nothing to sweep there.)
        if not self._standard_mode():
            from core.file_manager import cache_subdir
            for stale in (f"{orig_cht.stem}-sample.cht",
                          f"{orig_cht.stem}-patchbox.cht",
                          f"{orig_cht.stem}-patchbox-sample.cht"):
                # Sweep both homes: cache/ (current, #127) and the chart's own
                # folder (pre-v2 flat leftovers).
                for folder in (cache_subdir(orig_cht.parent), orig_cht.parent):
                    try:
                        (folder / stale).unlink(missing_ok=True)
                    except OSError:
                        pass
        try:
            text = read_text(orig_cht, lenient=True)
        except OSError:
            text = None
        # The chart's own float geometry is used as-is for EVERY chart kind
        # (#119, Knut's CMP Studio find). The old rectarg "integer edge"
        # realignment assumed the image was rendered at exactly the corner
        # distance — true for nothing: a hand-placed corner is a few pixels
        # off, which shifts the integer remainder distribution and drags the
        # INTERIOR columns up to ~15 % of a patch off the image mid-grid
        # (his diagnostic: corners and edge columns aligned, middle adrift),
        # and a real printed target is uniform, never integer-edged. The
        # demo scans are now painted on the same float geometry, so all
        # three — image, marquee, scanin — agree without any rebuilding.
        _ = text  # (read above so an unreadable cht still falls through)
        cht = self._apply_fiducial_frame(cht, base)
        return self._apply_sample_area(cht, frac, base)

    def _scanin_corners(self, corners, orig_cht: Path):
        """Turn the patch-grid-aligned marquee quad into scanin's ``-F`` corners.
        With "Use fiducial marks" ON (standard mode) extrapolate the quad out to
        the fiducial frame (matching the on-disk ``F`` line kept by
        :meth:`_apply_fiducial_frame`); OFF returns the quad unchanged (its ``F``
        was rewritten to the patch bbox). One alignment, two consistent frames —
        so ON and OFF land the grid identically. *orig_cht* is read only in ON."""
        if not (corners and self._standard_mode()
                and self._use_fiducials_cb.isChecked()):
            return corners
        from ui.scan_grid_marquee import extrapolate_to_fiducials
        try:
            text = read_text(orig_cht, lenient=True)
        except OSError:
            return corners
        return extrapolate_to_fiducials(corners, text) or corners

    def _apply_fiducial_frame(self, cht: Path, base: Path) -> Path:
        """The ``.cht``'s ``F`` line is the real fiducial marks. When "Use
        fiducial marks" is ON, hand scanin that file unchanged — the user placed
        the marquee corners on the marks, and ``-F`` maps them to the ``F`` line.
        Otherwise rewrite ``F`` to the patch-area bounding box, so ``-F`` maps
        the corners the user placed on the patch grid instead.

        The rewrite runs for ChromIQ-chart mode too (#108): a user-supplied
        printtarg ``-s`` .cht carries real corner marks OUTSIDE the patch
        area — Knut's charts have them 7 mm out on three sides, so skipping
        the rewrite compressed the whole grid downward. The rewrite keeps the
        original F's corner ORDER (engine charts are y-up, standard charts
        y-down — a fixed order vertically mirrored engine reads, #108)."""
        if self._standard_mode() and self._use_fiducials_cb.isChecked():
            return cht                # ON: corners were placed on the real marks
        from workflow.scanin_runner import cht_with_patchbox_fiducials
        try:
            txt = read_text(cht, lenient=True)
        except OSError:
            return cht
        new = cht_with_patchbox_fiducials(txt)
        if new == txt:
            return cht
        # Prepared working copies are cache material (#127): scanin reads them
        # by explicit path, so they live in cache/ instead of cluttering the
        # chart's folder. ensure_subdir falls back to the flat folder if the
        # volume refuses a new directory (read-only scan location).
        from core.file_manager import cache_subdir, ensure_subdir
        dst = ensure_subdir(cache_subdir(base.parent)) / f"{cht.stem}-patchbox.cht"
        dst.write_text(new, encoding="utf-8")
        return dst

    def _apply_sample_area(self, cht: Path, frac: float, base: Path) -> Path:
        """Write a sibling ``.cht`` whose boxes sample *frac* of each patch
        (Knut's patch-sample-area control, per axis so the read zone keeps the
        patch's own shape), and hand scanin that copy. The bundled/original
        file is never modified. Runs at full area too: ChromIQ charts carry a
        baked-in default ``BOX_SHRINK`` that must be pinned to 0, or "100 %"
        silently reads ≈ 50 % of each patch (Knut, #119)."""
        from workflow.scanin_runner import cht_with_sample_area
        try:
            new_text = cht_with_sample_area(read_text(cht, lenient=True), frac)
        except OSError:
            return cht
        from core.file_manager import cache_subdir, ensure_subdir
        dst = ensure_subdir(cache_subdir(base.parent)) / f"{cht.stem}-sample.cht"
        dst.write_text(new_text, encoding="utf-8")
        return dst

    def _execute(self) -> None:
        self._capture_current_corners()
        # NOT _save_placement() here. It used to run at the top of this method,
        # so a grid that failed its own alignment check was written into the
        # settings BEFORE the user was asked, and pressing Stop stored it just
        # the same — every later session for that target then started from the
        # grid the app had itself just called wrong (review 5, A3). It now runs
        # where the user has said yes: see `_remember_accepted_placement`.
        self._log.clear()
        self._align_warnings = []                # per-page misalignment findings
        self._read_findings = []                 # per-page data findings (review 5)
        self._run_diags: list[Path] = []         # diagnostic images this run writes
        method = self._avg_method.currentData() or "mean"
        if self._standard_mode():
            pages = self._pages
            first = next(s["path"] for pg in pages
                         for s in self._page_shots(pg) if s["path"])
            base = first.parent / first.stem
            # Keep the result folder self-contained: drop the reference .cie (a
            # converted one otherwise lives in a temp dir) next to the scan +
            # outputs, so everything for this profile sits together (Knut).
            if self._std_ref is not None:
                dest = base.parent / self._std_ref.name
                try:
                    if self._std_ref.resolve() != dest.resolve():
                        import shutil
                        shutil.copy2(self._std_ref, dest)
                        self._std_ref = dest
                except OSError:
                    pass
        else:
            pages = self._pages
            base = _chart_base(self._ti3)

        # Tidy older releases' scanner intermediates into cache/ before this
        # run writes its own set there (#127, Knut's beta.5 report) — both the
        # chart's folder and every scan's folder, in all three modes.
        from workflow.scanin_runner import tidy_legacy_intermediates
        folders = {base.parent}
        for pg in pages:
            for s in self._page_shots(pg):
                if s["path"]:
                    folders.add(Path(s["path"]).parent)
        tidied = [p for f in sorted(folders)
                  for p in tidy_legacy_intermediates(f)]
        if len(tidied) == 1:
            self._log.appendPlainText(tr(
                "Tidied one working file from an earlier ChromIQ version into "
                "the cache folder — everything in cache is safe to delete."))
        elif tidied:
            self._log.appendPlainText(tr(
                "Tidied {n} working files from earlier ChromIQ versions into "
                "the cache folder — everything in cache is safe to delete."
            ).format(n=len(tidied)))

        frac = self._sample_area.value() / 100.0
        if self._printer_mode():
            self._execute_printer(base, frac)
            return
        self._jobs = []
        page_ti3s: list[Path] = []
        for pg in pages:
            orig_cht, cie = self._files_for_page(pg, base)   # pre-rewrite (fiducials)
            shots = [s for s in self._page_shots(pg) if s["path"]]
            shot_ti3s: list[Path] = []
            for k, s in enumerate(shots):
                scan = s["path"]
                # Per-scan cht: align the interior to THIS scan's pixel size (so a
                # rounded rectarg image lines up), then fiducial-frame + sample-area.
                cht = self._prepare_scanin_cht(orig_cht, s["corners"], frac, base,
                                               f"p{pg + 1}s{k + 1}")
                # One diag per scan, named after the scan itself — with averaging
                # you want to check EVERY shot's alignment, not just the first
                # (#102). Distinct scan stems keep the files from colliding.
                # Diags are cache material (#127) — kept until the next run,
                # never the only copy of anything.
                from core.file_manager import cache_subdir, ensure_subdir
                diag = (ensure_subdir(cache_subdir(scan.parent))
                        / f"{scan.stem}-diag.tif"
                        if self._diag.isChecked() else None)
                if diag is not None:
                    self._run_diags.append(diag)
                params = ScaninParams(
                    scan, cht, cie,
                    corners=self._scanin_corners(s["corners"], orig_cht),
                    perspective=self._perspective.isChecked(), diag=diag,
                    out_name=f"{base.name}-p{pg + 1}s{k + 1}-scanner.ti3")
                shot_ti3s.append(params.out_ti3)
                self._jobs.append({"kind": "scanin", "params": params,
                                   "page": pg + 1, "shot": k + 1,
                                   "nshots": len(shots),
                                   "label": (tr("Reading scan {k} of page {n}…")
                                             if len(shots) > 1 else
                                             tr("Reading page {n} from the scan…"))
                                   .format(k=k + 1, n=pg + 1)})
            if len(shot_ti3s) > 1:
                avg = base.parent / f"{base.name}-p{pg + 1}-avg.ti3"
                self._jobs.append({"kind": "average", "ti3s": shot_ti3s,
                                   "out": avg, "method": method})
                page_ti3s.append(avg)
            else:
                page_ti3s.append(shot_ti3s[0])
        self._jobs.append({"kind": "colprof", "ti3s": page_ti3s, "base": base})
        self._run_job(0)

    def _run_job(self, i: int) -> None:
        if i >= len(self._jobs):
            return
        job = self._jobs[i]
        total = len(self._jobs)
        step = tr("Step {k} of {n}").format(k=i + 1, n=total)
        if job["kind"] == "scanin":
            self._log.appendPlainText(job["label"])
            self._set_busy_note(f"{step} — {job['label']}", fraction=i / total)

            unfilled = []

            def _watch(line: str) -> None:
                # scanin keeps going after this, but the read is partial — buried
                # in the -v noise Knut only noticed via the bad diagnostics (#108).
                if "Not all sample values have been filled" in line:
                    unfilled.append(line)
                self._log_line(line)

            def _done(code: int, i=i, job=job) -> None:
                fail = self._scanin.primary_failure()
                if code != 0 or fail is not None or not job["params"].out_ti3.exists():
                    msg = fail[1] if fail else tr("ScanIn couldn't read this page.")
                    self._log.appendPlainText(f"[ERROR] {msg}")
                    self._finish(False)
                    return
                # In printer mode each page fills only its own share of the
                # accumulated .ti3, so scanin reports "Not all sample values
                # have been filled" on every page but the last even when all
                # is well (#108) — only the final page's report means real gaps.
                if unfilled and not (job["params"].is_printer
                                     and not job.get("final")):
                    self._log.appendPlainText(tr(
                        "⚠ Not every patch on this page could be read — the grid "
                        "placement is probably off. Check the diagnostic image "
                        "(if saved), realign the grid on this page's scan and "
                        "build again; a profile from a partial read will be "
                        "wrong."))
                if not job["params"].is_printer:     # printer .ti3 is accumulated;
                    self._sanitize_scanner_ti3(job["params"].out_ti3)  # sanitize at end
                self._check_page_alignment(job)
                self._run_job(i + 1)

            self._scanin.run(job["params"], on_line=_watch, on_finish=_done)
        elif job["kind"] == "average":
            _avg = tr("Averaging {n} scans of this page…").format(n=len(job["ti3s"]))
            self._log.appendPlainText(_avg)
            self._set_busy_note(f"{step} — {_avg}", fraction=i / total)
            try:
                average_scanner_ti3(job["ti3s"], job["out"], method=job["method"])
            except (Ti3AverageError, OSError) as exc:
                self._log.appendPlainText(f"[ERROR] {exc}")
                self._finish(False)
                return
            self._run_job(i + 1)
        elif job["kind"] == "colprof_printer":
            self._set_busy_note(
                f"{step} — " + tr("Building the printer profile…"),
                fraction=i / total)
            self._build_printer_profile(job["pbase"], job["base"])
        else:
            self._set_busy_note(
                f"{step} — " + tr("Building the scanner profile…"),
                fraction=i / total)
            self._build_profile(job["ti3s"], job["base"])

    def _execute_printer(self, base: Path, frac: float) -> None:
        """Printer profile from a scanned ChromIQ chart: ``scanin -c/-ca`` converts
        each page's patches to real colour through the scanner profile and reads the
        chart's ``<base>.ti2`` (printer device values), accumulating one
        ``<pbase>.ti3``; then colprof builds a printer profile from it. The flat-bed
        scanner is the measuring instrument."""
        import shutil
        chart_ti2 = artefact(base, ".ti2")
        if not chart_ti2.is_file():
            self._log.appendPlainText(tr(
                "[ERROR] This chart has no .ti2 (the printer values it was printed "
                "with) next to its .ti3, so a printer profile can't be built from it."))
            self._finish(False)
            return
        first = next((s["path"] for pg in self._pages
                      for s in self._page_shots(pg) if s["path"]), None)
        if first is None:
            self._finish(False)
            return
        pbase = first.parent / f"{base.name}-printer"
        try:
            # scanin -c reads `<pbase>.ti2` by STRCAT, so the copy must carry
            # the whole dotted stem (core/stem_paths.py).
            shutil.copy2(chart_ti2, artefact(pbase, ".ti2"))
        except OSError as exc:
            self._log.appendPlainText(f"[ERROR] {exc}")
            self._finish(False)
            return
        self._jobs = []
        if any(sum(1 for sh in self._page_shots(pg) if sh["path"]) > 1
               for pg in self._pages):
            self._log.appendPlainText(tr(
                "Note: averaging isn't used for a printer profile — only the "
                "first scan of each page is read."))
        first_page = True
        for pg in self._pages:
            orig_cht, _ = self._files_for_page(pg, base)
            shots = [s for s in self._page_shots(pg) if s["path"]]
            if not shots:
                continue
            s = shots[0]                             # one scan per page in printer mode
            cht = self._prepare_scanin_cht(orig_cht, s["corners"], frac, base,
                                           f"printer-p{pg + 1}")
            # A diag per page scan (each page is its own image), not just the
            # first — every page's alignment is worth checking (#102). Cache
            # material (#127), same as the profiling path above.
            from core.file_manager import cache_subdir, ensure_subdir
            diag = (ensure_subdir(cache_subdir(s["path"].parent))
                    / f"{s['path'].stem}-diag.tif"
                    if self._diag.isChecked() else None)
            if diag is not None:
                self._run_diags.append(diag)
            params = ScaninParams(
                s["path"], cht,
                corners=self._scanin_corners(s["corners"], orig_cht),
                perspective=self._perspective.isChecked(), diag=diag,
                scan_profile=self._printer_scan_profile, pbase=pbase,
                accumulate=not first_page)
            self._jobs.append({"kind": "scanin", "params": params,
                               "page": pg + 1,
                               "label": tr("Reading page {n} for the printer "
                                           "profile…").format(n=pg + 1)})
            first_page = False
        if not self._jobs:
            self._finish(False)
            return
        self._jobs[-1]["final"] = True      # last page: the .ti3 must be complete
        self._jobs.append({"kind": "colprof_printer", "pbase": pbase, "base": base})
        self._run_job(0)

    def _check_page_alignment(self, job: dict) -> None:
        """Knut's misalignment sanity check (#108), per page — so the warning
        names the scan to fix. Printer mode: compare the page's patches (the
        IDs its .cht reads) in the accumulated .ti3 against the chart's aim
        values — ΔE76 > 15 on more than 10% of them means a scrambled patch
        assignment, not an uncalibrated printer. Scanner mode: the reference
        is what the .ti3 itself pairs the read with, so ΔE is trivially small
        there — instead rank-correlate the scan's luminance with the
        reference Y (:func:`scan_reference_correlation`). Findings are logged
        AND collected in ``_align_warnings``; before colprof runs the user
        gets a modal choice — his misaligned build sailed through as one ⚠
        line buried in colprof's -v output."""
        try:
            p = job["params"]
            if p.is_printer:
                _read, exp = self._read_expected_dicts(
                    p.out_ti3, artefact(p.pbase, ".ti2"),
                    ids=page_ids_from_cht(p.cht))
            else:
                _read, exp = self._read_expected_dicts(p.out_ti3)
            report = self._dense_report(p, p.is_printer, exp)
            floor = 100.0 * float(self._settings.get(
                "scanner_check_agreement", 0.85))
            where = self._page_label(job.get("page", 1) - 1)
            on_edge = self._flank_offenders(report) if report else []
            if on_edge:
                msg = tr(
                    "{w}: sample boxes sit on patch edges — realign the "
                    "grid. Worst placed: {worst}. (Placement agreement: "
                    "{a}.)").format(
                        w=where, worst=", ".join(on_edge[:6]),
                        a=self._agreement_txt(report))
                self._log.appendPlainText("⚠ " + msg)
                self._align_warnings.append(msg)
            elif report is not None and report.agreement_pct < floor:
                worst = ", ".join(n for n, _pp in report.offenders[:5])
                msg = tr(
                    "{w}: a nearby grid position matches the chart better "
                    "than the current one — the grid probably sits a "
                    "fraction of a patch off (placement agreement: {a}, "
                    "floor {f} %). Patches reading furthest from "
                    "expectation: {worst}.").format(
                        w=where, a=self._agreement_txt(report),
                        f=f"{floor:.0f}", worst=worst)
                self._log.appendPlainText("⚠ " + msg)
                self._align_warnings.append(msg)
            elif p.is_printer:
                self._check_local_groups(job, p.out_ti3,
                                         artefact(p.pbase, ".ti2"),
                                         ids=page_ids_from_cht(p.cht))
            elif (scan_reference_correlation(p.out_ti3) or 1.0) >= 0.8:
                self._check_local_groups(job, p.out_ti3)
        except Exception:  # noqa: BLE001 — a sanity check must never block
            log.warning("misalignment check failed", exc_info=True)
        self._check_read_is_this_chart(job)

    def _read_verdicts(self, params, rho) -> list[str]:
        """The build gate's three questions, phrased for the Check-alignment
        window.

        Without this, that window prints a green tick over a scan that is not
        this chart at all — which is where review 5's B2 was found. At rho 0.03
        `ref_usable` below goes False, the rank-displacement layer is skipped
        because the reference cannot predict the scan, and the geometric ladder
        then reports "the current grid position keeps all sample boxes within
        their chart patches (placement agreement: worst 99.70 %)". Every word of
        that is true. It is also about a different target's reference, and the
        window said nothing about that.

        Headlines only: this is a list of verdict lines, and the full text
        belongs in the window the build gate raises.
        """
        from workflow.scan_read_check import inspect_read
        from workflow import measurement_messages as M
        out: list[str] = []
        try:
            got = inspect_read(params.out_ti3, rho)
            if got is None:
                return out
            cov = self._reference_shortfall()
            if cov is not None:
                out.append("⚠ " + self._short_reference_message(cov)[0])
            if got.disagrees(float(self._settings.get(
                    "scanner_min_agreement", 0.25))):
                out.append("⚠ " + M.M_SCAN_REF_DISAGREES.render(
                    rho=f"{got.agreement:.2f}")[0])
            if got.clipped > float(self._settings.get(
                    "scanner_max_clipped", 0.15)):
                out.append("⚠ " + M.M_SCAN_CLIPPED.render(
                    pct=f"{got.clipped * 100:.0f} %")[0])
        except Exception:  # noqa: BLE001 — a sanity check must never block
            log.warning("read sanity check failed", exc_info=True)
        return out

    def _check_read_is_this_chart(self, job: dict) -> None:
        """The other half of the question, asked of the DATA (review 5).

        Everything above judges where the grid sits. Nothing above asks whether
        what came back is this chart at all — and four of review 5's findings
        live in that gap: a reference covering a sixth of the target, a wrong
        reference, an upside-down scan, and a scan with two of every five
        patches clipped to white. All four are visible in the one file scanin
        has just written, and none of them is visible to the checks above.

        Findings go to ``_read_findings`` rather than ``_align_warnings``, so
        the window that shows them can say what they actually are instead of
        "the alignment check failed".
        """
        from workflow.scan_read_check import inspect_read
        from workflow import measurement_messages as M
        try:
            p = job["params"]
            ti3 = p.out_ti3
            if not ti3.exists():
                return
            rho = (page_reference_agreement(
                       ti3, artefact(p.pbase, ".ti2"),
                       ids=page_ids_from_cht(p.cht)) if p.is_printer
                   else scan_reference_correlation(ti3))
            got = inspect_read(ti3, rho)
            if got is None:
                return
            seen = {t for t, _b in self._read_findings}

            # (1) The reference covers only part of the chart. Asked of the
            # REFERENCE, never of the read: a read that came back short already
            # has two messages of its own (scanin's "Not all sample values have
            # been filled" and the dropped-patch note), and a third voice
            # saying the same thing in different numbers would be noise.
            cov = self._reference_shortfall()
            if cov is not None:
                t, b = self._short_reference_message(cov)
                if t not in seen:
                    self._read_findings.append((t, b))

            # (2) What was read and what the reference says barely rank
            # together. The floor sits well under the 0.8 gate above, which
            # exists for a different purpose: a saturated LaserSoft target
            # ranks at about 0.5 on a PERFECT read, so a warning floor must
            # clear that by a wide margin. Measured: good reads +0.940 to
            # +0.972, broken ones -0.60 to +0.14.
            floor = float(self._settings.get("scanner_min_agreement", 0.25))
            if got.disagrees(floor):
                t, b = M.M_SCAN_REF_DISAGREES.render(
                    rho=f"{got.agreement:.2f}")
                if t not in seen:
                    self._read_findings.append((t, b))

            # (3) The scan ran out of scale. Clipping is invisible to (2) — a
            # 39 %-clipped scan still ranks at +0.943, because clipping shifts
            # values without reordering them.
            cap = float(self._settings.get("scanner_max_clipped", 0.15))
            if got.clipped > cap:
                t, b = M.M_SCAN_CLIPPED.render(
                    pct=f"{got.clipped * 100:.0f} %")
                if t not in seen:
                    self._read_findings.append((t, b))
        except Exception:  # noqa: BLE001 — a sanity check must never block
            log.warning("read sanity check failed", exc_info=True)

    @staticmethod
    def _read_expected_dicts(ti3: Path, ti2: Path | None = None,
                             ids: set[str] | None = None
                             ) -> tuple[dict[str, float], dict[str, float]]:
        """(read, expected) per plain id: scanner/standard mode pairs the scan
        luminance with the inline reference; printer mode pairs measured Y
        with the .ti2 aim Y (keyed by loc). Shared by the per-page checks and
        the pre-build alignment check."""
        from workflow.ti3_analysis import parse_ti3
        got = parse_ti3(ti3)
        if ti2 is None:                       # scanner mode: reference is inline
            read = {_plain_id(s): 0.2126 * r + 0.7152 * g + 0.0722 * b
                    for s, (r, g, b) in zip(got.sample_ids, got.rgb)}
            exp = {_plain_id(s): y
                   for s, (_x, y, _z) in zip(got.sample_ids, got.xyz)}
        else:                                 # printer mode: aims from the .ti2
            aim = parse_ti3(ti2)
            loc_of = {_plain_id(s): _plain_id(l.strip('"'))
                      for s, l in zip(aim.sample_ids, aim.sample_locs)}
            exp = {loc_of.get(_plain_id(s), _plain_id(s)): y
                   for s, (_x, y, _z) in zip(aim.sample_ids, aim.xyz)}
            read = {loc_of.get(_plain_id(s), _plain_id(s)): y
                    for s, (_x, y, _z) in zip(got.sample_ids, got.xyz)}
            if ids is not None:
                read = {k: v for k, v in read.items() if k in ids}
        return read, exp

    def _check_local_groups(self, job: dict, ti3: Path,
                            ti2: Path | None = None,
                            ids: set[str] | None = None) -> None:
        """The LOCAL layer (Knut's row/column idea, #108): a page whose
        whole-page checks pass can still have one grid edge a cell off —
        rank-displacement clustering names the affected row/column."""
        read, exp = self._read_expected_dicts(ti3, ti2, ids)
        groups = locally_misaligned_groups(read, exp)
        if not groups:
            return
        msg = tr(
            "Page {n}: the patches in {groups} read like their neighbours' "
            "colours — a grid edge probably sits about one cell off there. "
            "Check that edge of the grid on this page's scan.").format(
                n=job.get("page", 1), groups=", ".join(groups))
        self._log.appendPlainText("⚠ " + msg)
        self._align_warnings.append(msg)

    # ------------------------------------------------- pre-build check (#108)
    def _on_check_alignment(self) -> None:
        """Knut's pre-build check: read ONLY the page on screen into a
        temporary folder, run the misalignment checks on it, and show the
        verdict with the diagnostic image. The temp folder is deleted when
        the result window closes — no files land next to the scans."""
        import shutil
        import tempfile
        shot = self._cur_shot()
        if not shot.get("path"):
            self._log.appendPlainText(tr(
                "Load a scan for this page first — then Check alignment can "
                "read it."))
            return
        if self._runner_busy():
            return
        self._capture_current_corners()
        corners = shot["corners"]
        pg = self._page
        frac = self._sample_area.value() / 100.0
        tmp = Path(tempfile.mkdtemp(prefix="chromiq-aligncheck-"))
        try:
            scan = tmp / shot["path"].name
            shutil.copy2(shot["path"], scan)
            if self._standard_mode():
                orig_cht, cie = self._std_cht, self._std_ref
                if orig_cht is None or cie is None:
                    shutil.rmtree(tmp, ignore_errors=True)
                    self._log.appendPlainText(tr(
                        "Pick the target type and its reference data first — "
                        "then Check alignment can read the scan."))
                    return
            else:
                base = _chart_base(self._ti3)
                orig_cht, cie = self._files_for_page(pg, base)
            cht = self._prepare_scanin_cht(orig_cht, corners, frac,
                                           tmp / "check", f"chk-p{pg + 1}")
            diag = tmp / "diag.tif"
            printer = (not self._standard_mode() and self._printer_mode()
                       and self._printer_scan_profile is not None)
            if printer:
                pbase = tmp / "printer"
                shutil.copy2(artefact(_chart_base(self._ti3), ".ti2"),
                             artefact(pbase, ".ti2"))
                params = ScaninParams(
                    scan, cht,
                    corners=self._scanin_corners(corners, orig_cht),
                    perspective=self._perspective.isChecked(), diag=diag,
                    scan_profile=self._printer_scan_profile, pbase=pbase)
            else:
                params = ScaninParams(
                    scan, cht, cie,
                    corners=self._scanin_corners(corners, orig_cht),
                    perspective=self._perspective.isChecked(), diag=diag,
                    out_name="aligncheck-scanner.ti3")
        except OSError as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            self._log.appendPlainText(f"[ERROR] {exc}")
            return
        note = tr("Checking the grid — {w}…").format(w=self._page_label(pg))
        self._log.appendPlainText(note)
        self._set_busy_note(note)

        def _done(code: int) -> None:
            try:
                verdicts = self._alignment_verdicts(params, printer, pg, code)
            except Exception:  # noqa: BLE001 — verdicts must never crash the UI
                log.warning("alignment check failed", exc_info=True)
                verdicts = [tr("The check couldn't judge this read — see the "
                               "status log.")]
            self._finish(True)
            for v in verdicts:
                self._log.appendPlainText(v)
            self._show_alignment_result(pg, verdicts, diag, tmp)

        self._scanin.run(params, on_line=self._log_line, on_finish=_done)

    def _page_label(self, pg: int) -> str:
        """"Page {n}" only when there ARE multiple pages — a single-page
        target reads better as just "Target" (Knut)."""
        if len(self._pages) > 1:
            return tr("Page {n}").format(n=pg + 1)
        return tr("Target")

    def _runner_busy(self) -> bool:
        runner = getattr(self._scanin, "_runner", None)
        if runner is not None and getattr(runner, "is_running", False):
            self._log.appendPlainText(tr(
                "Another ArgyllCMS task is still running — wait for it to "
                "finish, then check again."))
            return True
        return False

    def _alignment_verdicts(self, params, printer: bool, pg: int,
                            code: int) -> list[str]:
        """The build's layered checks plus the probe comparison, phrased as
        an honest verdict — praise only when the probes back it up (Knut)."""
        out: list[str] = []
        where = self._page_label(pg)
        ti3 = params.out_ti3
        if code != 0 or not ti3.exists():
            fail = self._scanin.primary_failure()
            return [("⚠ " + fail[1]) if fail else
                    tr("⚠ ScanIn couldn't read this — the grid is probably "
                       "far off the patches.")]
        if printer:
            read, exp = self._read_expected_dicts(
                ti3, artefact(params.pbase, ".ti2"),
                ids=page_ids_from_cht(params.cht))
            rho = page_reference_agreement(
                ti3, artefact(params.pbase, ".ti2"),
                ids=page_ids_from_cht(params.cht))
        else:
            read, exp = self._read_expected_dicts(ti3)
            rho = scan_reference_correlation(ti3)
        # Reference-based layers only make sense where the reference can
        # predict the scan at all: on strongly saturated targets (LaserSoft)
        # even a perfect read ranks against the reference at ρ≈0.5, and
        # rank-displacement clustering fires on nothing but metamerism.
        out += self._read_verdicts(params, rho)
        ref_usable = rho is None or rho >= 0.8
        groups = (locally_misaligned_groups(read, exp)
                  if ref_usable else [])
        if groups:
            out.append(tr(
                "⚠ {w}: the patches in {groups} read like their neighbours' "
                "colours — a grid edge probably sits about one cell off "
                "there.").format(w=where, groups=", ".join(groups)))

        # Knut's dense step ladder (#108): the scan is sampled once and the
        # grid position competes against every position of the 12-step ×
        # 8-direction ladder — baseline (best position) = 100 %, the worst
        # position in the grid's octant = 0 %, worst patch listed. Scanner
        # and standard mode rank positions by consistency with one smooth
        # response of the reference; printer mode has no usable per-patch
        # reference (aim values scatter against real prints), so it ranks by
        # sample-box uniformity — a centred box sits on flat colour, an
        # offset box straddles patch edges.
        agree = None
        report = None
        try:
            report = self._dense_report(params, printer, exp)
        except Exception:  # noqa: BLE001
            log.warning("dense placement evaluation failed", exc_info=True)
        if report is not None:
            agree = report.agreement_pct
            on_edge = self._flank_offenders(report)
            if on_edge:
                out.append(tr(
                    "⚠ {w}: sample boxes sit on patch edges — realign the "
                    "grid. Worst placed: {worst}. (Placement agreement: "
                    "{a}.)").format(
                        w=where, worst=", ".join(on_edge[:6]),
                        a=self._agreement_txt(report)))
            floor = 100.0 * float(self._settings.get(
                "scanner_check_agreement", 0.85))
            if not on_edge and agree < floor:
                worst = ", ".join(n for n, _p in report.offenders[:5])
                out.append(tr(
                    "⚠ {w}: a nearby grid position matches the chart better "
                    "than the current one — the grid probably sits a "
                    "fraction of a patch off. Nudge it and check again. "
                    "(Placement agreement: {a}, floor {f} %. Patches "
                    "reading furthest from expectation: {worst}.)").format(
                        w=where, a=self._agreement_txt(report),
                        f=f"{floor:.0f}", worst=worst))
        if not out:
            if agree is not None:
                out.append(tr(
                    "✓ {w}: the current grid position keeps all sample "
                    "boxes within their chart patches (placement agreement: "
                    "{r}).").format(w=where, r=self._agreement_txt(report)))
            else:
                r_txt = f"{rho:.2f}" if rho is not None else "—"
                out.append(tr(
                    "✓ {w} looks well aligned — what was read agrees with "
                    "the chart (agreement {r}).").format(w=where, r=r_txt))
        return out

    @staticmethod
    def _agreement_txt(report) -> str:
        """"worst 56.88 %, average 96.70 %" — the verdict is the worst-patch
        number (it alone decides), with the page average alongside so a few
        bad patches read differently from a wholesale misplacement (Knut)."""
        return tr("worst {w} %, average {a} %").format(
            w=f"{report.agreement_pct:.2f}", a=f"{report.average_pct:.2f}")

    def _flank_offenders(self, report) -> list[str]:
        """Patches whose sample box sits ON a patch border flank (Knut):
        the box contains a patch-border LINE — three or more CONNECTED
        sub-cells of its 11×11 grid carry a gradient peak above the page's
        grain floor (a line crosses adjacent cells; dust scatters, Knut) —
        and the box reads clean at some nearby position.

        ``scanner_flank_min_boxes`` such boxes flag the page whatever the
        ladder says; 0 turns edge detection off. The straight-run cell rule
        keeps grain and a target's own printed features out of the count
        (Knut's aligned LaserSoft leaves at most one), so the default is 2."""
        need = int(self._settings.get("scanner_flank_min_boxes", 2))
        if need <= 0:
            return []
        lim = float(self._settings.get("scanner_flank_limit", 0.20))
        hits = sorted(((n, v) for n, v in report.flank_by_patch.items()
                       if v > lim), key=lambda t: -t[1])
        return [n for n, _v in hits] if len(hits) >= need else []

    def _dense_report(self, params, printer: bool, exp: dict):
        """Run Knut's dense ladder on the dry-run's scan: patch boxes from
        the prepared .cht, the user's quad mapped to the PATCH-AREA bbox
        (when the corners were placed on a fiducial frame, the patch quad is
        interpolated from the frame), expectations from the same pairing the
        misalignment checks use."""
        from workflow.cht_parser import parse_cht
        from workflow.placement_probe import dense_placement_agreement
        corners = params.corners
        if not corners or len(corners) != 4:
            return None
        geom = parse_cht(read_text(params.cht, lenient=True))
        if not geom.patches:
            return None
        # The corners correspond to the prepared cht's F line — the real
        # fiducial frame with "Use fiducial marks" ON, the patch bbox
        # otherwise. Mapping the patch bbox onto fiducial-frame corners
        # displaced every sample box outward and blunted the whole ladder
        # (Knut's beta.136 test: agreement stuck above 99 % on offsets his
        # diagnostic image showed plainly).
        fid_quad = geom.fiducials if len(getattr(geom, "fiducials", []) or []) == 4 else None

        class _Box:
            __slots__ = ("x1", "y1", "x2", "y2", "name")

            def __init__(self, b, frac: float) -> None:
                mg = 0.0
                if frac < 0.999:
                    from workflow.scanin_runner import sample_margin_inverse
                    mg = sample_margin_inverse(b.x2 - b.x1, b.y2 - b.y1, frac)
                self.x1, self.y1 = b.x1 - mg, b.y1 - mg
                self.x2, self.y2 = b.x2 + mg, b.y2 + mg
                self.name = _plain_id(b.name)

        # The prepared cht's boxes are already shrunk to the sample area —
        # equal margins on all four sides (cht_with_sample_area). The probe
        # wants the FULL patch boxes (it applies the sample fraction
        # itself), so undo that margin around each box.
        frac = self._sample_area.value() / 100.0
        boxes = [_Box(b, frac) for b in geom.patches]
        expected = {_plain_id(k): v for k, v in exp.items()}
        if not printer:
            # Scanner/standard mode: the reference carries full XYZ — hand
            # the response lens the triples so it can model the scan's
            # luminance linearly in XYZ (monotone-in-Y breaks on saturated
            # targets like the LaserSoft).
            try:
                from workflow.ti3_analysis import parse_ti3
                t = parse_ti3(params.out_ti3)
                triples = {_plain_id(sid): tuple(xyz)
                           for sid, xyz in zip(t.sample_ids, t.xyz)}
                if len(triples) >= 16:
                    expected = triples
            except Exception:  # noqa: BLE001
                pass

        def _run(objective: str):
            return dense_placement_agreement(
                params.scan_tif, boxes, corners, expected,
                sample_frac=self._sample_area.value() / 100.0,
                objective=objective, src_quad=fid_quad,
                flank_min_cells=int(self._settings.get(
                    "scanner_flank_min_cells", 8)))

        if printer:
            # No usable per-patch reference (aim values scatter against real
            # prints) — the edge lens alone decides.
            return _run("uniformity")
        # Both lenses in ONE per-patch ladder (Knut, #119): the response
        # term sees blends the edge term can't (similar-spread neighbours,
        # and a box that lands wholly inside the WRONG patch reads perfectly
        # uniform), the edge term sees borders the response term can't
        # (similar-colour neighbours — an IT8's vertical steps especially).
        # The response term self-gates on targets its model can't explain;
        # the edge lens then rules alone.
        rep = _run("combined")
        return rep if rep is not None else _run("uniformity")

    def _show_alignment_result(self, pg: int, verdicts: list[str],
                               diag: Path, tmp: Path) -> None:
        """Verdict + diagnostic image in a window; the temp folder dies with
        it (Knut: no clutter and leftovers on drive). The image pans (drag)
        and zooms (scroll / pinch) like the marquee pop-out, so misalignment
        can be studied patch by patch (Knut)."""
        import shutil
        from PyQt6.QtGui import QPixmap
        dlg = QDialog(self)
        dlg.setWindowTitle(
            tr("Alignment check — {w}").format(w=self._page_label(pg)))
        v = QVBoxLayout(dlg)
        for line in verdicts:
            lbl = QLabel(line, dlg)
            lbl.setWordWrap(True)
            v.addWidget(lbl)
        pm = None
        if diag.exists():
            img = _load_scan_qimage(diag)
            if not img.isNull():
                pm = QPixmap.fromImage(img)
        if pm is not None:
            view = _ZoomPanImageView(pm, dlg)
            view.setMinimumSize(920, 560)
            v.addWidget(view, 1)
            hint = self._hint_label(tr(
                "Scroll to zoom · drag to pan · double-click to fit"))
            v.addWidget(hint)
        else:
            note = QLabel(tr(
                "No diagnostic image could be produced for this read."), dlg)
            note.setWordWrap(True)
            v.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dlg)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        v.addWidget(bb)
        dlg.finished.connect(
            lambda _r: shutil.rmtree(tmp, ignore_errors=True))
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dlg.show()

    def _stop_before_colprof(self, tip: bool = True) -> None:
        """Everything Stop does, whichever window asked. Factored out when the
        read-sanity window joined the alignment one: pressing Stop must leave
        the user in the same place either way, with the evidence one click
        away, and it used to be written into one of them only."""
        self._log.appendPlainText(tr(
            "Stopped — realign the flagged page's grid and build again."))
        # Put the evidence one click away (Knut: the reveal button only
        # appeared after a FINISHED build, so the diagnostic image the
        # message points at was left to hunt for by hand).
        diags = [d for d in getattr(self, "_run_diags", []) if d.exists()]
        scans = [s["path"] for pg in self._pages
                 for s in self._page_shots(pg) if s["path"]]
        target = diags[0] if diags else (scans[0] if scans else None)
        if target is not None:
            # It reveals the FOLDER (Knut: the old label promised the
            # image itself, and appeared even with the diag box unticked).
            self._last_profile = target
            self._reveal_btn.setText(tr("Reveal folder"))
            self._reveal_btn.setVisible(True)
            self._reveal_btn.setEnabled(True)
        if tip and not diags:
            self._log.appendPlainText(tr(
                "Tip: tick “Save a diagnostic image of what was read” and "
                "build again — the image shows exactly which patches were "
                "read from your scan."))
        self._finish(False)

    def _confirm_despite_read_findings(self) -> bool:
        """Modal stop before colprof when the READ does not look like this
        chart — review 5's D, B2, B3 and B4.

        Separate from the alignment window on purpose. That one says "the
        alignment check failed", which would be a lie about a reference file
        that covers a sixth of the target or a scan that has run out of scale,
        and a message the user can see is untrue is worse than none. Every word
        here comes from §M; where several findings arrive at once they are
        stacked under the first one's headline, worst first.

        Returns True to build anyway. The wording is §M-PROPOSED — the
        mechanism does not depend on it and the sentences are the owner's to
        approve.
        """
        from PyQt6.QtWidgets import QMessageBox
        title, first = self._read_findings[0]
        rest = [b for _t, b in self._read_findings[1:]]
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText("\n\n".join([first] + rest))
        stop = box.addButton(tr("Stop"), QMessageBox.ButtonRole.RejectRole)
        box.addButton(tr("Build anyway"), QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(stop)
        box.exec()
        if box.clickedButton() is stop:
            self._stop_before_colprof()
            return False
        return True

    def _confirm_despite_misalignment(self) -> bool:
        """Modal stop before colprof when a page failed the alignment check —
        a profile from a scrambled read is garbage, and a log line alone is
        overlooked (#108). Returns True to build anyway."""
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("Scan doesn't match the chart"))
        box.setText(tr("The alignment check failed:"))
        box.setInformativeText(
            "\n\n".join("• " + w for w in self._align_warnings) + "\n\n" + tr(
                "Check the flagged page's diagnostic image (if saved), realign "
                "the grid on its scan and build again. A profile built from "
                "this read will be wrong."))
        stop = box.addButton(tr("Stop"), QMessageBox.ButtonRole.RejectRole)
        box.addButton(tr("Build anyway"), QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(stop)
        box.exec()
        if box.clickedButton() is stop:
            self._stop_before_colprof()
            return False
        return True

    def _watch_profile_check(self):
        """An ``on_line`` wrapper that also captures colprof's own fit check
        ("Profile check complete, peak err = …"). Knut's sub-patch grid shifts
        slip past the per-page pre-checks (a half-patch shift reads plausible
        BLENDS of neighbouring colours) but blow this number up (his tests:
        peak 60–91 vs < 10 aligned) — so the fit check is the arbiter of
        subtle misalignment (#108)."""
        found: list[tuple[float, float]] = []

        def _on_line(line: str) -> None:
            m = _PROFCHECK_RE.search(line)
            if m:
                found.append((float(m.group(1)), float(m.group(2))))
            self._log_line(line)

        return _on_line, found

    def _selfcheck_verdict(self, found: list[tuple[float, float]]) -> bool:
        """Warn when colprof's fit check looks like a misread. BOTH numbers
        must be high: a matrix scanner profile legitimately fits a few
        extreme patches poorly (Knut's perfectly aligned build: peak 32.8,
        average 8.5), while a misplaced grid lifts the AVERAGE too (his
        misaligned runs: peak 60–91 with averages around 40).

        Returns **True when it warned**, so the caller can say the same thing
        with the button as well as the line — the warning used to be printed
        between "[OK] … profile saved" and "Install it as your …", where the
        two sentences either side of it both said the opposite."""
        if not found:
            return False
        peak, avg = found[-1]
        peak_lim = float(self._settings.get("scanner_selfcheck_peak", 30.0))
        avg_lim = float(self._settings.get("scanner_selfcheck_avg", 12.0))
        if peak <= peak_lim or avg <= avg_lim:
            return False
        self._log.appendPlainText(tr(
            "⚠ Self-check: colprof reports a peak fit error of {p} with an "
            "average of {a} — an aligned read keeps the average well under "
            "{al}. A grid sitting slightly off on one page (even by half a "
            "patch) produces exactly this. Check the diagnostic images, "
            "realign and rebuild before trusting this profile. (Thresholds: "
            "Preferences → Scanner Limits.)").format(
                p=round(peak, 1), a=round(avg, 1), al=round(avg_lim)))
        return True

    def _offer_install(self, failed_selfcheck: bool) -> None:
        """Show "Reveal profile" / "Install profile" after a build — and when
        the self-check warned, say so on the button itself.

        "Install Profile Anyway" is the app's own wording for exactly this,
        from `ui/tabs/tab_check_refine.py`, where a result that needs work
        grades the same button that way. It is an existing, already-translated
        string in all twelve catalogues, so this needs no new text. Reset on a
        clean build: the window can build again without being reopened."""
        self._reveal_btn.setText(tr("Reveal profile"))
        self._reveal_btn.setVisible(True)
        self._reveal_btn.setEnabled(True)
        self._install_btn.setText(tr("Install Profile Anyway") if failed_selfcheck
                                  else tr("Install profile"))
        self._install_btn.setVisible(True)
        self._install_btn.setEnabled(True)

    def _build_printer_profile(self, pbase: Path, base: Path) -> None:
        ti3 = artefact(pbase, ".ti3")
        self._sanitize_scanner_ti3(ti3)              # once, on the accumulated .ti3
        if self._read_findings and not self._confirm_despite_read_findings():
            return
        if self._align_warnings and not self._confirm_despite_misalignment():
            return
        self._remember_accepted_placement()
        self._log.appendPlainText(tr("Building the printer profile…"))
        stash = self._archive_previous_profile(ti3)
        ti3, custom = self._apply_profile_name(ti3)
        desc = custom or f"{base.name} (scanner-measured)"
        params = scanner_colprof.make_profile_params(       # #121: same settings
            ti3, desc, self._current_main_vals(), self._effective_adv())

        def _done(code: int) -> None:
            icc = self._profiler.expected_icc_path(params)
            if not (icc.exists() and icc.stat().st_size > 1000):
                _remove_empty_icc(icc)
                self._restore_archived_profile(stash)
                fail = self._profiler.primary_failure()
                if fail:
                    self._log.appendPlainText(f"[ERROR] {fail[1]}")
                else:
                    raw = self._profiler.last_output()
                    self._log.appendPlainText(
                        f"[ERROR] {tr('Building the profile failed. colprof said:')}")
                    self._log.appendPlainText(raw or tr("(colprof produced no output)"))
                self._finish(False)
                return
            self._log.appendPlainText(tr("[OK] Printer profile saved: {p}").format(p=icc))
            self._log.appendPlainText(tr(
                "Install it as your printer's profile. The measurement (.ti3) sits "
                "next to it — load that in the Build Profile tab if you want to "
                "fine-tune the printer profile (intents, quality, …)."))
            # LAST, not sandwiched. The warning used to be printed between
            # "[OK] Printer profile saved" and "Install it as your printer's
            # profile", so the user read a success headline, then "do not
            # trust this", then an instruction to install it — and the button
            # said "Install profile" either way.
            failed = self._selfcheck_verdict(_check)
            self._last_profile = icc
            self._offer_install(failed)
            self._finish(True)

        on_line, _check = self._watch_profile_check()
        self._profiler.build(params, on_line=on_line, on_finish=_done)

    def _sanitize_scanner_ti3(self, ti3: Path) -> None:
        """Fix nan/inf values scanin can write for degenerate patches, which would
        otherwise make colprof reject the whole .ti3 (a common Windows crash)."""
        from workflow.scanin_runner import sanitize_ti3
        try:
            clean, zeroed, dropped = sanitize_ti3(read_text(ti3, lenient=True))
        except OSError:
            return
        if not (zeroed or dropped):
            return
        try:
            ti3.write_text(clean, encoding="utf-8")
        except OSError:
            return
        if dropped:
            msg = (tr("Note: 1 patch that didn't read (no usable pixels) was left "
                      "out so the profile can still build — re-check the grid "
                      "covers every patch inside the image.")
                   if dropped == 1 else tr(
                      "Note: {n} patches that didn't read (no usable pixels) were "
                      "left out so the profile can still build — re-check the grid "
                      "covers every patch inside the image.").format(n=dropped))
            self._log.appendPlainText(msg)
        if zeroed:
            self._log.appendPlainText(tr(
                "Note: some patches had an undefined noise figure; it was set to "
                "zero (no effect on the measured colour)."))

    def _build_profile(self, page_ti3s: list[Path], base: Path) -> None:
        # Combine multi-page reads into one .ti3, then colprof → scanner ICC.
        if self._read_findings and not self._confirm_despite_read_findings():
            return
        if self._align_warnings and not self._confirm_despite_misalignment():
            return
        try:
            combined = self._combine_ti3(page_ti3s, base)
        except OSError as exc:
            self._log.appendPlainText(f"[ERROR] {exc}")
            self._finish(False)
            return
        self._remember_accepted_placement()
        self._log.appendPlainText(tr("Building the scanner profile…"))
        stash = self._archive_previous_profile(combined)
        combined, custom = self._apply_profile_name(combined)
        desc = custom or f"{base.name} scanner"
        params = scanner_colprof.make_profile_params(       # #121: main + advanced
            combined, desc, self._current_main_vals(), self._effective_adv())

        def _done(code: int) -> None:
            # Resolve the profile the same robust way the printer builder does:
            # colprof writes .icc OR .icm (Windows) and may append rather than
            # replace the extension. Trust a valid profile on disk over colprof's
            # exit code — on Windows it can exit non-zero *after* "Profile done",
            # which used to make ChromIQ cry failure and hide the profile (Nelson).
            icc = self._profiler.expected_icc_path(params)
            if not (icc.exists() and icc.stat().st_size > 1000):
                _remove_empty_icc(icc)
                self._restore_archived_profile(stash)
                fail = self._profiler.primary_failure()
                if fail:
                    self._log.appendPlainText(f"[ERROR] {fail[1]}")
                else:
                    # No recognised pattern — show what colprof actually said, so
                    # the reason is never hidden behind "see messages above".
                    raw = self._profiler.last_output()
                    self._log.appendPlainText(f"[ERROR] {tr('Building the profile failed. colprof said:')}")
                    self._log.appendPlainText(raw or tr("(colprof produced no output)"))
                self._finish(False)
                return
            self._log.appendPlainText(tr("[OK] Scanner profile saved: {p}").format(p=icc))
            self._log.appendPlainText(tr(
                "Install it as your scanner's input profile. Use the diagnostic "
                "image (if you saved one) to check the patches were read correctly."))
            # LAST, not sandwiched — see `_build_printer_profile._done`.
            failed = self._selfcheck_verdict(_check)
            self._last_profile = icc
            self._offer_install(failed)
            self._finish(True)

        on_line, _check = self._watch_profile_check()
        self._profiler.build(params, on_line=on_line, on_finish=_done)

    def _combine_ti3(self, page_ti3s: list[Path], base: Path) -> Path:
        """Single page → use it directly; multi-page → concatenate the data rows
        into one scanner ``.ti3`` for colprof (same DEVICE_CLASS/format)."""
        if len(page_ti3s) == 1:
            return page_ti3s[0]
        # "-scanner" so the combined read / built profile can never collide with
        # the chart's own <stem>.ti3 / <stem>.icc (the printer profile).
        merged = base.with_name(base.name + "-scanner.ti3")
        header, rows = None, []
        for tp in page_ti3s:
            text = read_text(tp)
            lines = text.splitlines()
            ds = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
            de = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
            if header is None:
                header = lines[:ds + 1]
            rows += [l for l in lines[ds + 1:de] if l.strip()]
        # renumber SET count
        out = []
        for l in header:
            if l.strip().startswith("NUMBER_OF_SETS"):
                out.append(f"NUMBER_OF_SETS {len(rows)}")
            else:
                out.append(l)
        out += rows + ["END_DATA", ""]
        merged.write_text("\n".join(out), encoding="utf-8")
        return merged

    def _log_line(self, line: str) -> None:
        text = line.rstrip()
        if text and not text.endswith("%"):
            self._log.appendPlainText(text)
            self._log.ensureCursorVisible()
