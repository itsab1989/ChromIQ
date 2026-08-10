"""Measurement report viewer (Knut): accuracy statistics for a measured chart
and drift comparison over time.

Pick a measurement (.ti3); the dialog shows how the reading compares to the
chart's expected colours — mean / median / worst / spread ΔE00, the worst
patches with their colours, and the paper white and darkest black. "Save this
report" keeps a timestamped copy next to the chart so later measurements of
the same chart can be compared, revealing ink / printer / instrument drift.
"""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from core.logger import get_logger
from ui.fade_scroll import attach_edge_fades
from ui.styles import BG_INPUT, BORDER, SPEC_GREEN, TAB_COLORS, TEXT_MAIN
from ui.tab_header import dialog_masthead
from ui.theme import resolve_mode
from ui.tooltip_button import TooltipButton
from ui.widgets import open_files_dialog

log = get_logger(__name__)


# Cube-corner codes → human labels (lazy so tr() runs under the active language).
_CORNER_LABELS = {
    "W": lambda: tr("White"),
    "K": lambda: tr("Black"),
    "R": lambda: tr("Red"),
    "G": lambda: tr("Green"),
    "B": lambda: tr("Blue"),
    "C": lambda: tr("Cyan"),
    "M": lambda: tr("Magenta"),
    "Y": lambda: tr("Yellow"),
}

# Distinct, theme-legible line colours for each cube corner's trend line.
_CORNER_LINE = {
    "W": "#9a9a9a", "K": "#555555", "R": "#e23b3b", "G": "#33a94a",
    "B": "#3b6fe2", "C": "#1fb0b0", "M": "#c93bc9", "Y": "#c2a41f",
}

# The colour-accuracy metrics (Knut's revised set), keyed by report ``de00``
# field. Labels are lazy so tr() runs under the active language. ``_METRIC_LABELS``
# covers all six (Spread included); ``_ACCURACY_ROW_KEYS`` are the five that carry
# a Pass/Fail verdict, in display order; the trend chart plots those five.
_METRIC_LABELS = {
    "avg_all":   lambda: tr("Average ΔE, all patches"),
    "avg_low95": lambda: tr("Average ΔE, lowest 95%"),
    "avg_high5": lambda: tr("Average ΔE, highest 5%"),
    "max_all":   lambda: tr("Maximum ΔE, all patches"),
    "max_low95": lambda: tr("Maximum ΔE, lowest 95%"),
    "std":       lambda: tr("Spread (std. dev.)"),
}
_ACCURACY_ROW_KEYS = ("avg_all", "avg_low95", "avg_high5", "max_all", "max_low95")
# Line colour per accuracy metric for the colour-accuracy trend chart.
_METRIC_LINE = {
    "avg_all":   "#56d6a5", "avg_low95": "#37bcd6", "avg_high5": "#e0864b",
    "max_all":   "#e0574b", "max_low95": "#9f82ff",
}

# The report body is one self-contained HTML document, shown in a QTextBrowser
# AND saved to PDF. Inline colours beat any widget stylesheet, so a fixed
# light-theme palette rendered the on-screen report as #333 text on the dark
# theme's #1f1f1f background — a contrast ratio of 1.29:1, where readable body
# text needs 4.5:1. Only the parts that happen to sit on a light panel could be
# read at all.
#
# So the palette is chosen per render: light for the PDF (it goes on white
# paper) and for the light theme, legible-on-dark for the dark theme. Every
# value below clears 4.5:1 against its own background.
_LIGHT_REPORT = {
    "text": "#333333", "head": "#2a2a2a", "dim": "#555555", "faint": "#757575",
    "rule": "#bbbbbb", "hair": "#dddddd", "zebra": "#f2f2f2", "panel": "#f4f7f6",
    # Nudged darker than the greens and reds this file used to carry: on white
    # #1e8e3e reached 4.20:1, #d9534f 3.96:1 and #888888 3.54:1, all short of
    # the 4.5:1 body-text minimum on the very paper the PDF is printed on.
    "pass": "#197a35", "fail": "#c0392b", "error": "#c0392b",
    "swatch_edge": "#999999",
}
_DARK_REPORT = {
    "text": "#e6e6e6", "head": "#e6e6e6", "dim": "#b8b8b8", "faint": "#9a9a9a",
    "rule": "#5a5a5a", "hair": "#3a3a3a", "zebra": "#272727", "panel": "#232323",
    "pass": "#4fd77a", "fail": "#ff6f61", "error": "#ff6f61",
    "swatch_edge": "#6a6a6a",
}
#: The palette the HTML builders are currently rendering with. Set by
#: ``_report_body_html`` before it builds anything, so the module-level
#: heading helpers below pick it up too.
_C = dict(_LIGHT_REPORT)
# Max dated columns (runs) per table before it continues below — a portrait page
# fits six run columns plus the Metric column without the dates wrapping (Knut).
_MAX_RUN_COLS = 6


def _swatch(hexc: str) -> str:
    """A solid colour block for rich text. Qt ignores width/height on an empty
    span but honours background-color on a span WITH content, so we fill it with
    spaces hidden by matching the text colour to the fill."""
    c = html.escape(hexc or "#ffffff")
    return (f"<span style='background-color:{c};color:{c};"
            f"border:1px solid {_C["swatch_edge"]}'>&nbsp;&nbsp;&nbsp;</span>")


def _colour_line_html(height: int = 5) -> str:
    """The ChromIQ five-part spectrum line as a full-width rich-text table row."""
    cells = "".join(
        f"<td width='20%' style='background:{c};font-size:1px;line-height:1px'>"
        f"&nbsp;</td>" for c in TAB_COLORS)
    return (f"<table width='100%' cellpadding='0' cellspacing='0' "
            f"style='height:{height}px;margin:0'><tr>{cells}</tr></table>")


def _h2(text: str, *, page_break: bool = False) -> str:
    """A main section heading, matching 'Trend over time (this printer)' etc."""
    brk = "page-break-before:always;" if page_break else ""
    return (f"<h2 style='color:{_C["head"]};{brk}margin:14px 0 4px'>"
            f"{html.escape(text)}</h2>")


def _h3(text: str) -> str:
    return (f"<h3 style='color:{_C["head"]};margin:12px 0 3px'>"
            f"{html.escape(text)}</h3>")


def _fmt(v, dec: int = 2) -> str:
    return f"{v:.{dec}f}" if isinstance(v, (int, float)) else "—"


def _paginate_tables(doc, body_h: float) -> None:
    """Keep whole tables on one page (Knut #PDF4), heading included.

    Qt ignores CSS page-break-inside, but honours a frame's page-break policy,
    so each table straddling a page boundary is nudged onto the next page
    (topmost first, re-laying-out until none split). A pushed table must take
    its heading along — breaking only the table left "Worst patches" alone at
    the bottom of one page with its rows on the next (Sebastian, 2026-08-10) —
    so the break goes on the single non-empty block sitting directly above the
    table when that block would otherwise stay behind; if the straddle
    survives the next pass, the table itself gets the break too. Tables taller
    than a page can't be helped and are left to flow.
    """
    from PyQt6.QtGui import QTextCursor, QTextFormat, QTextTable

    always = QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore

    def _straddling_tables():
        lay = doc.documentLayout()
        found = []
        stack = [doc.rootFrame()]
        while stack:
            for ch in stack.pop().childFrames():
                stack.append(ch)
                if isinstance(ch, QTextTable):
                    r = lay.frameBoundingRect(ch)
                    if (r.height() < body_h - 1
                            and int(r.top() // body_h)
                            != int((r.bottom() - 1) // body_h)):
                        found.append((r.top(), ch))
        found.sort(key=lambda t: t[0])
        return [t for _, t in found]

    def _push_to_next_page(table) -> None:
        lay = doc.documentLayout()
        block = doc.findBlock(table.firstPosition() - 1)
        if block.isValid() and block.text().strip():
            t_top = lay.frameBoundingRect(table).top()
            b_rect = lay.blockBoundingRect(block)
            same_page = int(b_rect.top() // body_h) == int(t_top // body_h)
            close = t_top - b_rect.bottom() < 24
            if same_page and close \
                    and not block.blockFormat().pageBreakPolicy() & always:
                bf = block.blockFormat()
                bf.setPageBreakPolicy(always)
                cur = QTextCursor(block)
                cur.setBlockFormat(bf)
                return
        fmt = table.frameFormat()
        fmt.setPageBreakPolicy(always)
        table.setFrameFormat(fmt)

    for _ in range(400):
        straddlers = _straddling_tables()
        if not straddlers:
            break
        _push_to_next_page(straddlers[0])


class _TrendChart(QWidget):
    """A compact multi-line chart of a printer's measurement history over time
    (#40, Knut). Generic: each instance plots one GROUP of related metrics
    (ΔE00 accuracy, paper white/black, or the eight cube corners) so unlike
    scales never share an axis. A metric is ``(label, QColor, accessor)`` where
    ``accessor(point)`` returns the value or ``None``. Hidden until ≥2 points.
    ``unit_dec`` sets the y-label decimals; ``y_max`` optionally pins the top
    (e.g. 100 for L*)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._series: list[dict] = []
        self._metrics: list = []
        self._dark = True
        self._y_max: "float | None" = None
        self._dec = 1
        self._auto = False
        self._thresholds: "tuple[float, float] | None" = None
        self.setMinimumHeight(150)

    def set_data(self, series, metrics, dark=True, y_max=None, dec=1,
                 auto=False, thresholds=None) -> None:
        def has_any(pt) -> bool:
            return any(acc(pt) is not None for _, _, acc in metrics)
        self._series = [p for p in (series or []) if has_any(p)]
        self._metrics = metrics
        self._dark = dark
        self._y_max = y_max
        self._dec = dec
        # auto: range the axis tightly around the data (rounded to 0.1) instead of
        # anchoring at 0, so a small paper-white/black drift is actually visible
        # (Knut). ΔE charts keep their 0-anchored axis.
        self._auto = auto
        # (avg, max) Pass thresholds drawn as dotted guide lines (accuracy chart),
        # or None (Knut).
        self._thresholds = thresholds
        # NB: visibility is owned by the container (the tab widget), NOT the
        # chart — a per-widget setVisible here fought the tab stack and made all
        # three pages paint on top of each other before layout settled.
        self.update()

    def has_trend(self) -> bool:
        return len(self._series) >= 2

    def _legend_rows(self, fm, L, w) -> int:
        """How many rows the legend needs at this width — the plot top must
        make room for every one of them, or a wrapped second row is painted
        straight across the top of the graph (Sebastian, 2026-08-10, the
        PDF's Colour-accuracy chart)."""
        rows, lx = 1, L + 4
        for lbl, _col, _acc in self._metrics:
            adv = 26 + fm.horizontalAdvance(lbl)
            if lx + adv > L + w:
                lx = L + 4
                rows += 1
            lx += adv
        return rows

    def _draw_legend(self, p, fg, L, w) -> None:
        fm = p.fontMetrics()
        lx, ly = L + 4, 12.0
        for lbl, col, _acc in self._metrics:
            adv = 26 + fm.horizontalAdvance(lbl)
            if lx + adv > L + w:
                lx = L + 4; ly += 13
            p.setBrush(col); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(lx + 4, ly), 3.0, 3.0)
            p.setPen(QPen(fg, 1.0))
            p.drawText(QPointF(lx + 12, ly + 4), lbl)
            lx += adv

    def paintEvent(self, _ev) -> None:  # noqa: N802
        fg = QColor(210, 210, 210) if self._dark else QColor(60, 60, 60)
        grid = QColor(255, 255, 255, 28) if self._dark else QColor(0, 0, 0, 22)
        p = QPainter(self)
        # A light-mode chart paints its own white ground. In dark mode the
        # widget stays transparent over the dialog — but the light rendering
        # is what the PDF grabs off-screen, where the widget's inherited
        # palette is the app's DARK one, so the exported charts came out as
        # light lines on a black slab (Sebastian, 2026-08-10: "a light
        # background looks better in this context").
        if not self._dark:
            p.fillRect(self.rect(), QColor("#ffffff"))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(); font.setPixelSize(10); p.setFont(font)

        import math
        L, R, B = 40.0, 12.0, 26.0
        w = max(1.0, self.width() - L - R)
        # The plot starts below the FULL legend, however many rows it wraps to.
        T = 24.0 + 13.0 * (self._legend_rows(p.fontMetrics(), L, w) - 1)
        h = max(1.0, self.height() - T - B)
        pts = self._series
        # Empty state: an empty plot (frame + gridlines) with the legend and a
        # clear message that the trend needs at least two runs (Knut).
        if len(pts) < 2:
            self._draw_legend(p, fg, L, w)
            p.setPen(QPen(grid, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)   # the legend left a coloured brush
            p.drawRect(QRectF(L, T, w, h))
            for frac in (0.25, 0.5, 0.75):
                yy = T + h * frac
                p.drawLine(QPointF(L, yy), QPointF(L + w, yy))
            muted = QColor(150, 150, 150) if self._dark else QColor(120, 120, 120)
            p.setPen(QPen(muted, 1.0))
            p.drawText(
                QRectF(L + 10, T, w - 20, h),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                tr("Chart rendering require minimum two measurement runs. Add "
                   "more measurements, or if the currently loaded profile "
                   "contains multiple runs, enable the checkbox “Show all "
                   "measurement runs”."))
            p.end()
            return
        vals = [v for pt in pts for _, _, acc in self._metrics
                if (v := acc(pt)) is not None]
        if self._auto and vals:
            dmin, dmax = min(vals), max(vals)
            pad = 0.3 if (dmax - dmin) < 1e-9 else (dmax - dmin) * 0.15
            vmin = math.floor((dmin - pad) * 10.0) / 10.0
            vmax = math.ceil((dmax + pad) * 10.0) / 10.0
        else:
            vmin = 0.0
            vmax = self._y_max if self._y_max else max(vals + [1.0]) * 1.12
        span = max(1e-6, vmax - vmin)
        n = len(pts)

        def xy(i: int, val: float):
            return QPointF(L + (w * i / (n - 1)),
                           T + h * (1.0 - (val - vmin) / span))

        # Y grid + labels (bottom, mid, top of the actual range).
        p.setPen(QPen(grid, 1.0))
        for frac in (0.0, 0.5, 1.0):
            yy = T + h * (1.0 - frac)
            p.drawLine(QPointF(L, yy), QPointF(L + w, yy))
            p.setPen(QPen(fg, 1.0))
            p.drawText(QRectF(0, yy - 7, L - 4, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{vmin + span * frac:.{self._dec}f}")
            p.setPen(QPen(grid, 1.0))

        # One polyline per metric.
        for _lbl, col, acc in self._metrics:
            poly = [xy(i, v) for i, pt in enumerate(pts)
                    if (v := acc(pt)) is not None]
            if len(poly) < 2:
                continue
            p.setPen(QPen(col, 2.0))
            for a, b in zip(poly, poly[1:]):
                p.drawLine(a, b)
            p.setBrush(col); p.setPen(Qt.PenStyle.NoPen)
            for q in poly:
                p.drawEllipse(q, 2.4, 2.4)

        # Pass-threshold guide lines (accuracy chart only) — dotted, and only
        # while they fall inside the visible y-range (Knut).
        if self._thresholds:
            tpen = QPen(QColor(150, 150, 150) if self._dark else QColor(120, 120, 120))
            tpen.setStyle(Qt.PenStyle.DotLine); tpen.setWidthF(1.2)
            thr = [(tv, tlab) for tv, tlab in zip(self._thresholds, (tr("Avg"), tr("Max")))
                   if isinstance(tv, (int, float)) and vmin <= tv <= vmax]
            # Default: the label sits outside the plot in the left margin, aligned
            # with the y-axis numbers. But a threshold can land ON a y-axis number
            # (e.g. Avg 2.0 with a gridline at 2.0), overlapping it — so if EITHER
            # label would collide, put BOTH just above their own line at the left
            # tip instead (Knut). y-axis numbers are at fracs 0 / 0.5 / 1.
            axis_ys = [T + h * (1.0 - f) for f in (0.0, 0.5, 1.0)]
            thr_ys = [T + h * (1.0 - (tv - vmin) / span) for tv, _ in thr]
            # Collide when a label would land on a y-axis number — or on the
            # OTHER threshold's label: on a large y-range Avg 2.0 and Max 3.0
            # map to almost the same pixel, and the two words printed over
            # each other (Sebastian, 2026-08-10).
            # The words are drawn ONLY when they fit cleanly in the left
            # margin, aligned with the y-axis numbers. When the two lines
            # crowd each other or a y-axis number (a large y-range maps
            # 2.0 and 3.0 to almost the same pixel), the words are dropped
            # entirely rather than stacked into the plot, where every
            # placement collided with something (Sebastian, 2026-08-10,
            # three rounds) — the dotted lines stay, and the Pass-threshold
            # controls directly above the chart name their values.
            collide = any(abs(ty - ay) < 9.0 for ty in thr_ys for ay in axis_ys)
            if len(thr_ys) == 2 and abs(thr_ys[0] - thr_ys[1]) < 11.0:
                collide = True
            for (tv, tlab), yy in zip(thr, thr_ys):
                p.setPen(tpen)
                p.drawLine(QPointF(L, yy), QPointF(L + w, yy))
                if not collide:
                    p.setPen(QPen(fg, 1.0))
                    p.drawText(QRectF(0, yy - 7, L - 4, 14),
                               Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter,
                               tlab)

        # X axis: a tick under EVERY measurement point plus as many dated labels
        # (YYYY-MM-DD) as fit without overlapping — always the first and last —
        # so you can read at WHICH date each change happened, not just the range
        # (Knut). Ticks mark every point even where the date label is skipped.
        axis_y = self.height() - B
        p.setPen(QPen(grid, 1.0))
        for i in range(n):
            x = L + (w * i / (n - 1))
            p.drawLine(QPointF(x, axis_y), QPointF(x, axis_y + 3))
        p.setPen(QPen(fg, 1.0))
        fm = p.fontMetrics()

        def _lab(i: int) -> str:
            return str(pts[i].get("created") or "")[:10]

        def _draw_date(left: float, text: str) -> None:
            p.drawText(QRectF(left, axis_y + 4, fm.horizontalAdvance(text) + 6, 16),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, text)

        # Reserve the first (flush-left) and last (flush-right) dates, then fill
        # in as many intermediate dates as fit without overlapping either those
        # or each other — so the ends never collide (Knut).
        d0, dn = _lab(0), _lab(n - 1)
        w0, wn = fm.horizontalAdvance(d0), fm.horizontalAdvance(dn)
        last_left = L + w - wn
        _draw_date(L, d0)
        _draw_date(last_left, dn)
        occupied = [(L, L + w0), (last_left, last_left + wn)]
        for i in range(1, n - 1):
            d = _lab(i)
            tw = fm.horizontalAdvance(d)
            left = L + (w * i / (n - 1)) - tw / 2.0
            right = left + tw
            if all(right < a - 8 or left > b + 8 for a, b in occupied):
                _draw_date(left, d)
                occupied.append((left, right))

        # Legend (wraps across as many rows as needed for 8 corners).
        self._draw_legend(p, fg, L, w)
        p.end()


class MeasurementReportDialog(QDialog):
    def __init__(self, settings, parent=None, initial_ti3=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._report: dict | None = None
        self._ti3: Path | None = None
        self._trend_series: list = []
        self._history: list = []
        self._project_dirs: set = set()
        # Each source is one profile's measurements: {"name", "dir", "runs"}.
        # The list-field mirrors this; _history is their runs, oldest-first.
        self._sources: "list[dict]" = []
        self._created = datetime.now().isoformat(timespec="seconds")
        self.setWindowTitle(tr("Measurement Report"))
        self.setMinimumSize(760, 640)
        # Open TALL: everything above the report view has a fixed height
        # (~600 px with the trend visible), so at the 640 px minimum the
        # report text itself was a ~90 px sliver — "hard to get any
        # information out of it" (Sebastian, 2026-08-10). The view carries
        # the stretch, so every extra pixel goes to the report.
        self._sized_to_screen = False
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        _help = tr(
            "What this tool does\n"
            "This report compares what your instrument measured on a printed "
            "chart against the colours the chart was designed to have, and turns "
            "it into a clear Pass/Fail verdict you can track over time. The real "
            "power is comparison: because the design reference never changes, the "
            "way the numbers move between dated reports of the same printer is a "
            "clean signal of drift — ageing inks, a printer slowly wandering, or "
            "an instrument going off.\n\n"
            "Two ways to use it\n"
            "  • Profiling runs — after building a profile, check how faithfully "
            "the chart reproduced.\n"
            "  • Verification runs — the most valuable habit: print a small chart "
            "THROUGH your finished profile (a colour-managed print, the "
            "“Verification measurement” option on the Measure tab), measure it "
            "every so often, and save a report each time. When the Pass/Fail "
            "results start slipping, that's your sign the printer has drifted far "
            "enough to re-profile. A tiny verification chart is enough — you're "
            "watching the trend, not building a profile.\n\n"
            "Building the report\n"
            "The report covers a list of profiles' measurements, shown in the "
            "list box. Use “Add Profile's Measurements…” to add a profile (pick "
            "any of its .ti3 files and ChromIQ gathers all its runs), and "
            "“Remove Profile's Measurements…” / “Clear List” to take profiles out. "
            "“Show all measurement runs” switches between the single loaded "
            "measurement and every run of every listed profile. The trend charts "
            "need at least two runs — with a single run they show an empty chart "
            "and say so. Only combine profiles from the SAME printer (see "
            "below).\n\n"
            "The sections\n"
            "  • Report Scope — which profiles and instruments are in the report, "
            "the run count and date range. IMPORTANT: the report cannot tell which "
            "printer a measurement came from. It is up to YOU to only include runs "
            "from the same printer. A good habit is a clear Printer Profile Name "
            "(set on the Create Chart tab) — e.g. include the printer and paper — "
            "so profiles from one printer are easy to pick out. As a safety net "
            "the report still warns you if the runs you loaded use different "
            "instruments, or if a chart is missing any of the eight cube corners "
            "(which would make its cube-corner figures unreliable).\n"
            "  • Report Results — a Pass/Fail grid: each colour-accuracy metric "
            "against each run. Green passes, red fails.\n"
            "  • Colour accuracy — the ΔE00 (colour difference) figures, split so "
            "the bulk of the chart (all patches, and the best 95 %) is separated "
            "from the few hardest patches (the worst 5 %). Each is judged against "
            "your Pass thresholds. 0 is perfect, 1–2 is barely visible, 10+ is "
            "clearly wrong.\n"
            "  • Trend over time — the same metrics plotted across every saved "
            "measurement, so a slow rise or a sudden jump stands out at a glance.\n"
            "  • Overview of Measurement Metrics — every metric for every run in "
            "one table.\n"
            "  • Detailed data per run (optional) — the full breakdown for each "
            "run: the accuracy table, paper white & black, the cube corners and "
            "the sixteen worst patches.\n\n"
            "Pass thresholds\n"
            "You set two limits. The Average threshold (default 2.0 ΔE) judges the "
            "three average metrics; the Maximum threshold (default 3.0 ΔE) judges "
            "the two maximum metrics. A metric passes when it is at or below its "
            "limit. Tighten them for critical work, loosen them for a quick check.\n\n"
            "Options\n"
            "  • Show all measurement runs — the whole printer's history, not just "
            "the loaded one.\n"
            "  • Show detailed data for each run — add the per-run breakdown.\n"
            "  • Save report as PDF — a ChromIQ-styled PDF you can keep or share; "
            "it opens automatically. Reveal folder opens where it was saved.\n\n"
            "Using i1Profiler measurements\n"
            "You can feed this report measurements made in i1Profiler (handy when "
            "you measured with an i1iSis or i1iO, which lay out their own charts). "
            "Just two steps:\n"
            "  1. Export the measurement from i1Profiler as a text file.\n"
            "  2. Convert it with Tools → “Convert i1Profiler → TI3”, then add the "
            "resulting .ti3 here with “Add Profile's Measurements…”.\n"
            "That's all — you get the full colour-accuracy figures, no extra "
            "reference file needed. ChromIQ works out each patch's expected colour "
            "from the device values recorded in the file — the RGB / ink code "
            "values sent to the printer, which are the chart's fixed design and "
            "the same for every print, so the reference stays just as static "
            "across runs as a .ti2 would. (If a matching .ti2 happens to sit next "
            "to the .ti3, that's used instead.) The instrument is read from the "
            "i1Profiler file during conversion.\n"
            "Keeping things tidy: convert into the same folder as your i1Profiler "
            "files, add the .ti3, and save the PDF report right there — your "
            "i1Profiler work stays together and separate from ChromIQ's own "
            "profile folders.\n\n"
            "Screen and print colours here are approximate; the numbers come from "
            "your measurement file and are exact.")

        # Tool-style chrome: uppercase eyebrow + serif title + ⓘ over a
        # full-width spectrum stripe, green accent — the same look as the other
        # Tools windows. Zero side margins so the stripe runs edge to edge.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        head, self._header, stripe = dialog_masthead(
            self, tr("MEASUREMENT · REPORT"), tr("Measurement Report"),
            tooltip_title=tr("Measurement report"), tooltip_body=_help,
            accent=SPEC_GREEN)
        outer.addLayout(head)
        outer.addWidget(stripe)

        v = QVBoxLayout()
        # Bottom 13, the same visual gap the main window's tabs give their
        # bottom-most buttons (Sebastian, 2026-08-10) — the Close button ends
        # level with what the rest of the app taught the eye to expect.
        v.setContentsMargins(22, 14, 22, 13)
        v.setSpacing(12)
        outer.addLayout(v)

        intro = QLabel(tr(
            "See how accurately your printed chart was reproduced, and keep a "
            "dated report so you can compare measurements of the same chart "
            "over time."), self)
        intro.setWordWrap(True)
        v.addWidget(intro)

        # Sourcing: add / remove / clear the profiles whose measurements the
        # report covers. Each list entry is one profile's runs (Knut).
        add_row = QHBoxLayout()
        self._add_btn = QPushButton(tr("Add Profile's Measurements…"), self)
        # Compact utility height (Sebastian, 2026-08-10) — these five are
        # housekeeping controls, not the window's primary action; Close
        # keeps the standard height. A per-widget rule beats the app-wide
        # 28px QSS min-height (the scanin dialog's pattern).
        _compact_btn = ("QPushButton { padding: 1px 14px;"
                        " min-height: 26px; max-height: 26px; }")
        self._add_btn.setStyleSheet(_compact_btn)
        self._add_btn.clicked.connect(self._on_add_project)
        add_row.addWidget(self._add_btn)
        self._remove_btn = QPushButton(tr("Remove Profile's Measurements…"), self)
        self._remove_btn.setStyleSheet(_compact_btn)
        self._remove_btn.clicked.connect(self._on_remove_profile)
        self._remove_btn.setEnabled(False)
        add_row.addWidget(self._remove_btn)
        self._clear_btn = QPushButton(tr("Clear List"), self)
        self._clear_btn.setStyleSheet(_compact_btn)
        self._clear_btn.clicked.connect(self._on_clear_list)
        self._clear_btn.setEnabled(False)
        add_row.addWidget(self._clear_btn)
        add_row.addWidget(TooltipButton(
            tr("Adding profiles' measurements"),
            tr("Build the report from one or more profiles' measurements.\n\n"
               "Add Profile's Measurements… — pick one or more measurement "
               "files (select several at once) — .ti3, or i1Profiler "
               "measurements (.mxf, .txt or .cxf) which ChromIQ converts for "
               "you. From a ChromIQ profile's .ti3 it gathers EVERY saved "
               "measurement of that "
               "profile (all its runs) and adds the profile to the list below. "
               "You can add as many profiles as you like.\n\n"
               "Where the runs come from: a ChromIQ profile lives in its own "
               "folder with a runs/ sub-folder (run1, run2, …), and each run "
               "keeps its saved reports in a reports/ folder. Point at any run's "
               ".ti3 and ChromIQ finds the whole profile's history automatically. "
               "The instrument shown in the report is read from each measurement "
               "file itself. For the colour figures the report uses the chart's "
               "design file (.ti2) when it sits next to the .ti3; if there isn't "
               "one, it derives the same reference from the device values in the "
               "file (the fixed code values sent to the printer, identical for "
               "every run) — so you still get the full ΔE comparison against a "
               "static reference.\n\n"
               "Using i1Profiler measurements: just add each measurement here "
               "directly — i1Profiler's own saved file (.mxf), a text/CGATS "
               "export (.txt) or a CxF file (.cxf). No export or convert step is "
               "needed. No .ti2 is required either — ChromIQ derives the "
               "reference from the measured values, and reads the instrument "
               "from the i1Profiler file. Add several measurements to see a trend "
               "across them.\n\n"
               "Remove Profile's Measurements… — select a profile in the list and "
               "remove it (its runs leave the report). Clear List empties the "
               "whole report.\n\n"
               "Important: the report cannot tell which printer a measurement "
               "came from — only add profiles from the SAME printer. A clear "
               "Printer Profile Name (set on the Create Chart tab) makes them easy "
               "to recognise; the report also warns you if the runs use different "
               "instruments or a chart is missing cube corners."),
            self, color=SPEC_GREEN))
        add_row.addStretch(1)
        v.addLayout(add_row)

        self._profile_list = QListWidget(self)
        # A fixed height cramped this into ~3 visible rows the moment a run
        # or two existed — nowhere near enough to see and untick a run
        # without scrolling first (Sebastian, 2026-08-10). Sized instead to
        # the CONTENT in _size_profile_list: small with few rows, capped
        # (never eats the report below it) once there are many, with an
        # internal scrollbar past the cap either way.
        self._profile_list.setToolTip(tr(
            "The profiles whose measurements this report covers, with one row "
            "per dated run underneath. Untick a run to leave it out of the "
            "trend, the tables and the PDF — nothing is changed on disk, and "
            "ticking it brings it straight back. Select a profile row and use "
            "“Remove Profile's Measurements…” to drop the whole profile."))
        self._profile_list.itemSelectionChanged.connect(self._update_source_buttons)
        #: run keys the user unticked — session-only, nothing on disk changes.
        self._hidden_runs: "set[str]" = set()
        self._list_rows: "list[tuple]" = []
        self._building_list = False
        self._profile_list.itemChanged.connect(self._on_run_row_toggled)
        v.addWidget(self._profile_list)

        out_row = QHBoxLayout()
        self._pdf_btn = QPushButton(tr("Save report as PDF…"), self)
        self._pdf_btn.setStyleSheet(_compact_btn)
        self._pdf_btn.clicked.connect(self._export_pdf)
        self._pdf_btn.setEnabled(False)
        out_row.addWidget(self._pdf_btn)
        self._reveal_btn = QPushButton(tr("Reveal folder"), self)
        self._reveal_btn.setStyleSheet(_compact_btn)
        self._reveal_btn.clicked.connect(self._on_reveal)
        self._reveal_btn.setEnabled(False)
        out_row.addWidget(self._reveal_btn)
        out_row.addWidget(TooltipButton(
            tr("Saving and finding the report"),
            tr("Save report as PDF… — writes the whole report (this window's "
               "contents, laid out for print with the ChromIQ heading and page "
               "numbers) to a PDF and opens it. The charts are included only when "
               "the report has two or more runs.\n\n"
               "Where it is saved: when “Show all measurement runs” is on, the PDF "
               "belongs to the whole printer profile and goes in a reports folder "
               "next to the profile's runs; when it is off, it goes in the loaded "
               "run's "
               "own reports folder. You choose the exact place and name in the "
               "save dialog.\n\n"
               "Reveal folder — opens that profile folder in your file manager so "
               "you can browse to the reports folder and open any PDF you saved "
               "earlier."),
            self, color=SPEC_GREEN))
        out_row.addStretch(1)
        v.addLayout(out_row)

        # Report options — the window and the PDF always show the same thing (Knut).
        opt_row = QHBoxLayout()
        self._all_runs_check = QCheckBox(tr("Show all measurement runs"), self)
        self._all_runs_check.setChecked(True)
        self._all_runs_check.toggled.connect(lambda _=None: self._refresh())
        opt_row.addWidget(self._all_runs_check)
        opt_row.addWidget(TooltipButton(
            tr("Show all measurement runs"),
            tr("The report can look at one measurement, or at your whole "
               "history.\n\n"
               "With this ticked, every dated run in the list above is part "
               "of the report: the trend charts, Report Scope, Report Results "
               "and the tables compare them side by side — and any run you "
               "have unticked in the list stays out.\n\n"
               "With it off, the report shows only the measurement it was "
               "opened on — one run, in full, with no comparison.\n\n"
               "The saved PDF always matches what you see here."),
            self, min_width=440, color=SPEC_GREEN))
        self._detail_check = QCheckBox(tr("Show detailed data for each run"), self)
        self._detail_check.setChecked(False)
        self._detail_check.toggled.connect(lambda _=None: self._render())
        opt_row.addWidget(self._detail_check)
        opt_row.addWidget(TooltipButton(
            tr("Show detailed data for each run"),
            tr("Adds the full breakdown for every run in the report, each on "
               "a page of its own: the colour-accuracy table with its "
               "Pass/Fail verdicts against your thresholds, paper white and "
               "darkest black, the eight cube corners, and the worst patches "
               "with their expected and measured colours side by side.\n\n"
               "Handy when you want to see WHY a run passed or failed, not "
               "just that it did — for example which patches pushed the "
               "average over your threshold.\n\n"
               "It makes the report, and the saved PDF, considerably longer — "
               "which is why it starts unticked."),
            self, min_width=440, color=SPEC_GREEN))
        opt_row.addStretch(1)
        v.addLayout(opt_row)

        # Pass/Fail thresholds — the average threshold judges the three average
        # metrics, the maximum threshold the two maximum metrics (Knut).
        from ui.widgets import NoScrollDoubleSpinBox
        from workflow.measurement_report import DEFAULT_PASS_AVG, DEFAULT_PASS_MAX
        # Open with the user's configured defaults (Preferences → Reports), falling
        # back to the built-in 2.0 / 3.0 (Knut).
        avg0 = float(settings.get("report_pass_threshold_avg", DEFAULT_PASS_AVG))
        max0 = float(settings.get("report_pass_threshold_max", DEFAULT_PASS_MAX))
        thr_row = QHBoxLayout()
        thr_row.addWidget(QLabel(tr("Pass threshold — Average:"), self))
        self._avg_thr_spin = NoScrollDoubleSpinBox(self)
        self._avg_thr_spin.setDecimals(1); self._avg_thr_spin.setRange(0.1, 100.0)
        self._avg_thr_spin.setSingleStep(0.5); self._avg_thr_spin.setSuffix(" ΔE")
        self._avg_thr_spin.setValue(avg0)
        self._avg_thr_spin.valueChanged.connect(lambda _=None: self._refresh())
        thr_row.addWidget(self._avg_thr_spin)
        thr_row.addSpacing(14)
        thr_row.addWidget(QLabel(tr("Maximum:"), self))
        self._max_thr_spin = NoScrollDoubleSpinBox(self)
        self._max_thr_spin.setDecimals(1); self._max_thr_spin.setRange(0.1, 100.0)
        self._max_thr_spin.setSingleStep(0.5); self._max_thr_spin.setSuffix(" ΔE")
        self._max_thr_spin.setValue(max0)
        self._max_thr_spin.valueChanged.connect(lambda _=None: self._refresh())
        thr_row.addWidget(self._max_thr_spin)
        thr_row.addWidget(TooltipButton(
            tr("Pass thresholds"),
            tr("The colour-accuracy verdict. A metric passes when its measured "
               "ΔE00 is at or below its threshold. The Average threshold is "
               "compared against the three average metrics (all patches, the best "
               "95%, and the worst 5%); the Maximum threshold against the two "
               "maximum metrics (all patches, and the best 95%). Typical starting "
               "points are 2.0 for the average and 3.0 for the maximum — tighten "
               "them for critical work, loosen them for a quick health check.\n\n"
               "The values a report starts with are the defaults set in "
               "Preferences → Reports (Pass Threshold Average and Maximum)."),
            self, color=SPEC_GREEN))
        thr_row.addStretch(1)
        v.addLayout(thr_row)

        self._trend_label = QLabel(tr("Trend over time (this printer)"), self)
        self._trend_label.setStyleSheet("font-weight:bold;margin-top:2px")
        self._trend_label.setVisible(False)
        v.addWidget(self._trend_label)
        # Unlike-scaled metrics can't share one axis (Knut), so group them into
        # separate tabbed charts. Paper white (~L*100) and black (~L*10) are too
        # far apart to read a trend on one axis, so they get a chart each.
        self._trend_tabs = QTabWidget(self)
        self._trend_de = _TrendChart(self)
        self._trend_white = _TrendChart(self)
        self._trend_black = _TrendChart(self)
        self._trend_corners = _TrendChart(self)
        self._trend_tabs.addTab(self._trend_de, tr("Colour accuracy (ΔE00)"))
        self._trend_tabs.addTab(self._trend_white, tr("Paper white (L*)"))
        self._trend_tabs.addTab(self._trend_black, tr("Darkest black (L*)"))
        self._trend_tabs.addTab(self._trend_corners, tr("Cube corners"))
        self._trend_tabs.setVisible(False)
        v.addWidget(self._trend_tabs)

        self._view = QTextBrowser(self)
        self._view.setOpenExternalLinks(False)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setHtml(self._empty_html())
        # The report TEXT is the point of the window — guarantee it real
        # space. With the trend visible the fixed content above squeezed it
        # to a strip a few lines high (Sebastian, 2026-08-10: "hard to get
        # any information out of it"). 240, not more: every hard minimum here
        # adds to the window's unshrinkable floor, and that floor must stay
        # inside a laptop screen.
        self._view.setMinimumHeight(240)
        v.addWidget(self._view, 1)
        # The report view scrolls internally — give it the same fade-to-surface
        # gradient the Tools dialogs use on their scroll areas.
        self._view_fades = attach_edge_fades(self._view, surface="dialog")
        self._view_fades.set_appearance(
            resolve_mode(self._settings.get("appearance", "auto")))

        close_row = QHBoxLayout()
        # Clear air between the report view and the button (the edge-fade
        # wrapper around the view swallows the layout spacing, so the gap
        # must live in this row's own top margin); the bottom inset comes
        # from the root layout's 13 px margin alone, so the gap under Close
        # matches the main window's tabs (Sebastian, 2026-08-10).
        close_row.setContentsMargins(0, 16, 0, 0)
        close_row.addStretch(1)
        close_btn = QPushButton(tr("Close"), self)
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        v.addLayout(close_row)

        # Controls take the window's own green accent (checked checkbox + focus
        # rings), like the Ti1→i1Profiler tool uses its masthead accent, instead
        # of the global tab cyan; in dark mode match the report view to the input
        # background so it isn't darker than the chrome.
        mode = resolve_mode(self._settings.get("appearance", "auto"))
        from ui.dialogs.tools_dialogs import neutral_controls_qss
        qss = neutral_controls_qss(SPEC_GREEN)
        if mode == "dark":
            qss += (f"QTextBrowser {{ background: {BG_INPUT}; color: {TEXT_MAIN};"
                    f" border: 1px solid {BORDER}; border-radius: 3px; }}")
        self.setStyleSheet(qss)

        if initial_ti3 is not None and Path(initial_ti3).exists():
            self._load(Path(initial_ti3))

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._sized_to_screen:
            return
        self._sized_to_screen = True
        from PyQt6.QtGui import QGuiApplication
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        # Sizing alone left the window's BOTTOM off-screen on Sebastian's
        # display — resize() never moves a window, and Qt's own initial
        # placement is not guaranteed to fit a size chosen only afterwards.
        # Clamp the height to what the screen can actually hold (leaving a
        # margin so window-manager chrome never eats into it) and then
        # centre the whole window inside the available area, so both very
        # tall and very short screens end up with the full window — Close
        # button included — on screen (2026-08-10).
        w = max(self.width(), 920)
        cap = max(1, area.height() - 40)          # never claim the whole screen
        h = min(int(area.height() * 0.88), cap)
        h = max(h, min(640, cap))                 # the 640 px floor, screen-capped
        # The profile list grows with the run count (see _size_profile_list),
        # so the layout's OWN minimum can exceed the screen — and Qt refuses
        # any resize below it, which is exactly how the window's bottom (and
        # the Close button) landed off-screen (Sebastian, 2026-08-10). When
        # the floor doesn't fit, compact the list to two rows first; only
        # then respect what remains of the floor.
        layout = self.layout()
        if layout is not None:
            layout.activate()
            if layout.minimumSize().height() > cap:
                self._size_profile_list(compact=True)
                layout.activate()
            h = max(h, min(layout.minimumSize().height(), cap))
        self.resize(w, h)
        x = area.left() + max(0, (area.width() - w) // 2)
        y = area.top() + max(0, (area.height() - h) // 2)
        self.move(x, y)

    # ---- sources (one per profile) ----------------------------------------
    def _gather_runs(self, ti3: Path) -> "tuple[str, list]":
        """``(profile name, runs oldest-first)`` for the profile that owns *ti3*:
        every saved report across the profile's runs, or the freshly built one
        when nothing is saved yet (a stand-alone / i1Profiler .ti3)."""
        import json
        from workflow.measurement_report import (
            build_report, list_project_reports, REPORT_SCHEMA)
        runs: list[dict] = []
        for p in list_project_reports(ti3.parent):
            try:
                rep = json.loads(p.read_text())
            except Exception:  # noqa: BLE001
                continue
            # Reports saved by an older ChromIQ carry an older schema whose
            # metric set predates the current one (no avg_all/max_all …), so the
            # window would show "no accuracy data" for them. Rebuild such a
            # report from its run's own .ti3 — same measurement, current metrics —
            # keeping the saved date so the trend timeline is unchanged (Knut).
            stale = (rep.get("schema", 0) < REPORT_SCHEMA
                     or (rep.get("de00") or {}).get("avg_all") is None)
            if stale:
                run_ti3 = p.parent.parent / ti3.name
                if run_ti3.is_file():
                    try:
                        created = rep.get("created")
                        rep = build_report(run_ti3)
                        if created:
                            rep["created"] = created
                    except Exception:  # noqa: BLE001
                        pass
            runs.append(rep)
        # #130/#133: a dated verification trends across ALL of this run's
        # dates. A date measured with "Save measurement report" switched off
        # has no saved report — build its report fresh here, so the history is
        # complete either way (Sebastian, 2026-08-10: three measured dates
        # showed as "1 run" and the trend stayed empty).
        from core.file_manager import VERIFICATIONS_DIRNAME
        vroot = ti3.parent.parent
        if vroot.name == VERIFICATIONS_DIRNAME:
            covered = {Path(r.get("ti3", "")).parent.name
                       for r in runs if r.get("ti3")}
            for d in sorted(p for p in vroot.iterdir() if p.is_dir()):
                if d.name in covered or d.name == "old":
                    continue
                cand = d / ti3.name
                if cand.is_file():
                    try:
                        runs.append(build_report(cand))
                    except Exception:  # noqa: BLE001 — one bad date must
                        continue       # not empty the whole history
        if not runs:
            runs = [build_report(ti3)]
        runs.sort(key=lambda r: str(r.get("created") or ""))
        name = runs[-1].get("chart") or ti3.stem
        return name, runs

    def _source_key(self, ti3: Path) -> tuple:
        """Dedup identity for a measurement. A ChromIQ project (saved reports
        across its runs/) is ONE source per FOLDER — all its runs. A standalone or
        imported measurement is ONE source per FILE, so several loose measurements
        in the same folder each add instead of collapsing to one (Knut)."""
        from core.file_manager import VERIFICATIONS_DIRNAME
        from workflow.measurement_report import list_project_reports
        # A dated verification is ONE source per RUN — every date of the run's
        # verifications/ is gathered together, so adding a second date must
        # dedup against the first.
        if ti3.parent.parent.name == VERIFICATIONS_DIRNAME:
            return ("dir", str(ti3.parent.parent))
        if list_project_reports(ti3.parent):
            return ("dir", str(ti3.parent))
        return ("file", str(ti3))

    def _append_source(self, ti3: Path, origin: "Path | None" = None) -> bool:
        """Add one measurement to the source list (no repaint). Returns False if it
        is already present or has no runs. Raises on a gather error, so a batch add
        can report which files failed.

        *origin* is the file the user actually picked (the same as *ti3* for a
        ChromIQ .ti3, but the original .mxf/.txt/.cxf when *ti3* is a temp
        conversion). The report is saved next to the origin, never the temp folder
        (Knut)."""
        key = self._source_key(ti3)
        if any(s.get("key") == key for s in self._sources):
            return False
        name, runs = self._gather_runs(ti3)
        if not runs:
            return False
        self._sources.append({"key": key, "name": name, "dir": ti3.parent,
                              "ti3": ti3, "origin": Path(origin or ti3), "runs": runs})
        if self._ti3 is None:
            self._ti3 = ti3
        return True

    def _add_source(self, ti3: Path, origin: "Path | None" = None) -> None:
        """Add a single measurement and repaint (used when opening the report on
        one file)."""
        try:
            added = self._append_source(ti3, origin)
        except Exception as exc:  # noqa: BLE001
            self._view.setHtml(self._error_html(str(exc)))
            return
        if added:
            self._report = self._sources[0]["runs"][-1]     # single-run / PDF anchor
            self._rebuild_from_sources()

    @staticmethod
    def _run_key(r: dict) -> str:
        """A stable identity for one run across list rebuilds."""
        return f"{r.get('created', '')}|{r.get('ti3', '')}"

    def _run_row_label(self, r: dict) -> str:
        """'2026-08-10 12:04 — printed raw — no profile' — the date plus how
        the sheet was printed, so the mixed-methods warning is actionable."""
        created = str(r.get("created") or "")
        when = created.replace("T", " ")[:16] or "?"
        pr = r.get("printing") or {}
        colour = pr.get("colour") or "unrecorded"
        if colour == "through-profile" and pr.get("route") == "external-cm":
            label = tr("printed in another app with colour management")
        else:
            label = {
                "through-profile": tr("printed through the profile"),
                "raw": tr("printed raw — no profile"),
            }.get(colour, tr("printing method not recorded"))
        return f"{when} — {label}"

    def _rebuild_from_sources(self) -> None:
        """Recompute the history, the profile list and button states, then repaint
        the trend + report."""
        self._history = sorted(
            (r for s in self._sources for r in s["runs"]),
            key=lambda r: str(r.get("created") or ""))
        self._project_dirs = {s["dir"] for s in self._sources}
        self._building_list = True
        try:
            self._profile_list.clear()
            self._list_rows = []
            for si, s in enumerate(self._sources):
                n = len(s["runs"])
                self._profile_list.addItem(
                    f'{s["name"]}  ·  {n} '
                    + (tr("run") if n == 1 else tr("runs")))
                self._list_rows.append(("source", si, None))
                # One checkable row per dated run: unticking leaves it out of
                # the trend, tables and PDF — nothing on disk is touched
                # (Sebastian, 2026-08-10: "manually deselect only a few").
                for r in s["runs"]:
                    key = self._run_key(r)
                    item = QListWidgetItem("      " + self._run_row_label(r))
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled
                                  | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(
                        Qt.CheckState.Unchecked if key in self._hidden_runs
                        else Qt.CheckState.Checked)
                    self._profile_list.addItem(item)
                    self._list_rows.append(("run", si, key))
        finally:
            self._building_list = False
        self._size_profile_list()
        has = bool(self._sources)
        self._pdf_btn.setEnabled(has)
        self._reveal_btn.setEnabled(has)
        self._clear_btn.setEnabled(has)
        self._update_source_buttons()
        self._refresh()

    #: Five visible rows, then a scrollbar — Sebastian's number (2026-08-10).
    #: The MINIMUM stays at two rows so the window's own overlap-free floor
    #: can never be pushed past a small screen by a long run history: a hard
    #: multi-row floor did exactly that (the layout minimum outgrew the
    #: screen, Qt refused the smaller resize, and the window's bottom — Close
    #: included — landed off-screen).
    _LIST_VISIBLE_ROWS = 5

    def _size_profile_list(self, *, compact: bool = False) -> None:
        """Pin the list to its visible-row target (five, Sebastian's number),
        or — ``compact``, chosen by showEvent only when the whole window
        would otherwise not fit the screen — to two rows with a scrollbar."""
        n = len(self._list_rows)
        row_h = self._profile_list.sizeHintForRow(0) if n else -1
        if row_h <= 0:
            row_h = self._profile_list.fontMetrics().height() + 8
        frame = 2 * self._profile_list.frameWidth() + 4
        target = 2 if compact else self._LIST_VISIBLE_ROWS
        visible = min(max(n, 1), target)
        h = visible * row_h + frame
        self._profile_list.setMinimumHeight(h)
        self._profile_list.setMaximumHeight(h)

    def _update_source_buttons(self) -> None:
        self._remove_btn.setEnabled(bool(self._profile_list.selectedItems()))

    def _on_run_row_toggled(self, item) -> None:
        """A run row was ticked/unticked — refresh the report with it in/out."""
        if self._building_list:
            return
        row = self._profile_list.row(item)
        if not (0 <= row < len(self._list_rows)):
            return
        kind, _si, key = self._list_rows[row]
        if kind != "run" or key is None:
            return
        if item.checkState() == Qt.CheckState.Unchecked:
            self._hidden_runs.add(key)
        else:
            self._hidden_runs.discard(key)
        self._refresh()

    def _load(self, path: Path) -> None:
        """Open the report on a measurement — the profile that owns it becomes the
        first list entry."""
        self._add_source(Path(path))

    def _on_add_project(self) -> None:
        paths = open_files_dialog(
            self, tr("Add measurements (.ti3, or i1Profiler .mxf / .txt / .cxf)"),
            tr("Measurement data (*.ti3 *.mxf *.txt *.cxf);;All files (*)"),
            extra_path=self._settings.get("custom_output_path", ""))
        if not paths:
            return
        added, failed = 0, []
        for path in paths:
            try:
                if self._append_source(self._as_ti3(Path(path)), origin=Path(path)):
                    added += 1
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{Path(path).name} — {exc}")
        if added:
            self._report = self._sources[0]["runs"][-1]
            self._rebuild_from_sources()
        if failed and not added:
            self._view.setHtml(self._error_html(
                tr("Could not add these measurements:") + "\n" + "\n".join(failed)))

    def _as_ti3(self, src: Path) -> Path:
        """A .ti3 is used as-is; an i1Profiler measurement (.mxf / .txt / .cxf) is
        converted first — no export step (Knut). Each conversion lands in its own
        temp folder. Raises :class:`ReferenceConvertError` on a bad file, so the
        batch adder can list what failed."""
        from workflow.reference_convert import (convert_i1profiler_measurement,
                                                is_ti3)
        if is_ti3(src):
            return src
        import tempfile
        out_dir = Path(tempfile.mkdtemp(prefix="chromiq_report_"))
        argyll = self._settings.get("argyll_bin_path", "/Applications/Argyll/bin")
        return convert_i1profiler_measurement(src, argyll, out_dir)

    def _on_remove_profile(self) -> None:
        # Any selected row — the profile's own or one of its run rows — names
        # its source; drop each source once.
        picked = set()
        for i in self._profile_list.selectedItems():
            row = self._profile_list.row(i)
            if 0 <= row < len(self._list_rows):
                picked.add(self._list_rows[row][1])
        for si in sorted(picked, reverse=True):
            if 0 <= si < len(self._sources):
                del self._sources[si]
        if self._sources:
            first = self._sources[0]
            self._report = first["runs"][-1]
            self._ti3 = first.get("ti3") or first["dir"] / f'{first["name"]}.ti3'
        else:
            self._report, self._ti3 = None, None
        self._rebuild_from_sources()

    def _on_clear_list(self) -> None:
        self._sources = []
        self._report, self._ti3 = None, None
        self._rebuild_from_sources()

    def _refresh(self) -> None:
        """Repaint both the trend charts and the report body (they share the same
        run set, so both react to Show-all / thresholds / the profile list)."""
        self._refresh_trend()
        self._render()

    def _render(self) -> None:
        if not self._sources:
            self._view.setHtml(self._empty_html())
            return
        self._view.setHtml(
            self._report_body_html(self._runs_for_report(), for_pdf=False))

    def _refresh_trend(self) -> None:
        """Repaint the trend charts from the report's current run set."""
        from ui.theme import resolve_mode
        from workflow.measurement_report import report_trend
        dark = resolve_mode(self._settings.get("appearance", "auto")) != "light"
        self._trend_series = report_trend(self._runs_for_report())
        self._update_trends(self._trend_series, dark)

    def _trend_configs(self) -> list:
        """The four grouped charts as ``(chart, title, metrics, y_max, dec, auto)``
        — shared by the live tabs and the PDF export so they always match. ``auto``
        ranges the axis tightly around the data instead of anchoring at 0."""
        corner_metrics = [
            (_CORNER_LABELS[code](), QColor(_CORNER_LINE[code]),
             (lambda pt, c=code: (pt.get("corners") or {}).get(c)))
            for code in ("W", "K", "R", "G", "B", "C", "M", "Y")
        ]
        return [
            (self._trend_de, tr("Colour accuracy (ΔE00)"), [
                (_METRIC_LABELS[k](), QColor(_METRIC_LINE[k]),
                 (lambda pt, kk=k: pt.get(kk)))
                for k in _ACCURACY_ROW_KEYS
            ], None, 1, False),
            # White (~L*100) and black (~L*10) are too far apart to share an axis
            # (Knut), so each is its own auto-scaled chart — and the axis ranges
            # tightly around the values (not from 0) so a small drift is visible.
            (self._trend_white, tr("Paper white (L*)"), [
                (tr("Paper white L*"), QColor("#8a8a8a"), lambda pt: pt.get("white_L")),
            ], None, 1, True),
            (self._trend_black, tr("Darkest black (L*)"), [
                (tr("Black L*"), QColor("#505050"), lambda pt: pt.get("black_L")),
            ], None, 1, True),
            (self._trend_corners, tr("Cube corners (ΔE00 per ink)"),
             corner_metrics, None, 1, False),
        ]

    def _anchor_dir(self) -> Path:
        """The folder the PDF and Reveal default to: the folder of the FIRST
        source's ORIGINAL file — a ChromIQ run folder, or the user's own folder for
        an imported measurement — never the temp folder an i1Profiler file is
        converted into (Knut)."""
        if self._sources:
            return self._sources[0]["origin"].parent
        return self._ti3.parent if self._ti3 else Path.cwd()

    def _profile_root(self) -> Path:
        """The profile's project folder (``<project>/runs/<id>`` → ``<project>``),
        or the folder itself for a browsed/imported measurement that isn't in a
        ChromIQ project layout."""
        run_dir = self._anchor_dir()
        if run_dir.parent.name == "runs":
            return run_dir.parents[1]
        return run_dir

    @staticmethod
    def _lca_dir(dirs: "list[Path]") -> Path:
        """The deepest folder that contains every path in *dirs* (their least
        common ancestor). One folder in → that folder."""
        dirs = [Path(d) for d in dirs if d is not None]
        if not dirs:
            return Path.cwd()
        common = dirs[0].parts
        for d in dirs[1:]:
            parts = d.parts
            n = 0
            while n < len(common) and n < len(parts) and common[n] == parts[n]:
                n += 1
            common = common[:n]
        return Path(*common) if common else dirs[0]

    def _report_dir(self) -> Path:
        """Where a PDF is saved — the ``reports`` folder at the tightest place that
        still contains everything the report covers (#130 Hole 5, Knut). The four
        natural homes, from the least-common-ancestor of the measurements:

        * a single profiling run  → ``runs/<id>/reports``
        * a single verification   → ``runs/<id>/verifications/<date>/reports``
        * several verifications of one run → ``runs/<id>/verifications/reports``
        * several runs / the whole profile → ``<project>/reports`` (next to ``runs/``)

        For a browsed / imported measurement that isn't in a ChromIQ project it
        goes in a ``reports`` folder next to the file itself."""
        from core.file_manager import reports_subdir
        # The measurements this report actually covers: every loaded source when
        # 'all runs' is on, otherwise just the anchored one.
        if self._all_runs_check.isChecked() and self._sources:
            lca = self._lca_dir([s["origin"].parent for s in self._sources])
        else:
            lca = self._anchor_dir()
        # If the common ancestor is the ``runs`` container itself, the report spans
        # multiple runs → it belongs to the whole profile, next to ``runs/``.
        if lca.name == "runs":
            return reports_subdir(lca.parent)
        # An all-runs report is a whole-profile document even when only one of the
        # profile's measurements is physically loaded: root it at the project (next
        # to ``runs/``), not inside the single run that happens to be open.
        if self._all_runs_check.isChecked():
            for anc in (lca, *lca.parents):
                if anc.name == "runs":
                    return reports_subdir(anc.parent)
        return reports_subdir(lca)

    def _on_reveal(self) -> None:
        """Open the profile's folder in the file manager so the user can browse to
        the reports folder and open saved PDFs (Knut)."""
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        if self._sources or self._ti3:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._profile_root())))

    def _export_pdf(self) -> None:
        """Write the full report — all data, the trend charts and a plain-language
        guide to reading them — as a PDF, then open it for viewing (Knut)."""
        if not self._report or not self._ti3:
            return
        from datetime import datetime
        from PyQt6.QtCore import QMarginsF, QRectF, QSizeF, QUrl
        from PyQt6.QtGui import (
            QAbstractTextDocumentLayout, QColor, QDesktopServices, QFont,
            QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument,
        )

        reports = self._report_dir()
        reports.mkdir(parents=True, exist_ok=True)
        default = reports / self._report_filename(self._runs_for_report())
        # The house save dialog (sidebar shortcuts, ChromIQ styling) — this
        # was the one save in the app still opening the bare native dialog
        # (Sebastian, 2026-08-10).
        from ui.widgets import save_file_dialog
        path = save_file_dialog(
            self, tr("Save report as PDF"), "PDF (*.pdf)",
            start_path=str(default),
            extra_path=str(self._settings.get("custom_output_path", "")))
        if not path:
            return
        # The dialog does not force the extension — a name typed without one
        # must still come out as a .pdf.
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        doc = QTextDocument()
        charts_html = ""
        if self._trend_de.has_trend():
            # Render each grouped chart off-screen (the live tabs only lay out the
            # current one) and embed it as a resource. Kept compact so all four
            # trend charts fit on the one trend page (Knut).
            avg_thr, max_thr = self._thresholds()
            for i, (_c, title, metrics, y_max, dec, auto) in enumerate(self._trend_configs()):
                tmp = _TrendChart()
                tmp.resize(640, 176)
                thr = (avg_thr, max_thr) if _c is self._trend_de else None
                tmp.set_data(self._trend_series, metrics, dark=False,
                             y_max=y_max, dec=dec, auto=auto, thresholds=thr)
                img = tmp.grab().toImage()
                url = QUrl(f"chart://{i}")
                doc.addResource(QTextDocument.ResourceType.ImageResource, url, img)
                charts_html += (f"<h3 style='margin:4px 0 0'>{html.escape(title)}</h3>"
                                f"<img src='chart://{i}' width='600'>")
        # The exact same run set the window shows, so the PDF matches it (Knut).
        runs = self._runs_for_report()
        doc.setHtml(self._pdf_html(runs, charts_html))

        from PyQt6.QtGui import QFontMetricsF

        writer = QPdfWriter(str(path))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        # 15 mm all round keeps the wordmark ≥ 1.5 cm from the paper edge (Knut).
        writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
        # QPdfWriter defaults to a very high resolution, but the document is laid
        # out in ~96-dpi pixels (font px, img widths), so match the writer to the
        # document's 96-dpi coordinate space; text stays vector-crisp regardless.
        writer.setResolution(96)
        page_w, page_h = float(writer.width()), float(writer.height())
        # Header band (wordmark + per-page scope + colour line) at the top of the
        # printable area, footer band (page number) at the bottom. 34 px ≈ 9 mm,
        # so with the 15 mm margin the top margin stays under 2.5 cm (Knut).
        header_h, footer_h = 34.0, 22.0
        body_h = page_h - header_h - footer_h
        doc.setPageSize(QSizeF(page_w, body_h))

        _paginate_tables(doc, body_h)

        units = self._scope_header_units(runs)   # profile names + measurements/date
        head_font = QFont(); head_font.setPixelSize(8)
        foot_font = QFont(); foot_font.setPixelSize(10)
        # The ChromIQ wordmark, exactly as the app masthead draws it: "Chrom" in
        # Instrument Serif near-black, "IQ" bold-italic in the magenta accent.
        wm_r = QFont(); wm_r.setPixelSize(22)
        wm_r.setFamilies(["Instrument Serif", "Georgia", "Times New Roman", "serif"])
        wm_i = QFont(wm_r); wm_i.setBold(True); wm_i.setItalic(True)
        wm_fr, wm_fi = QFontMetricsF(wm_r), QFontMetricsF(wm_i)
        wm_chrom_w = wm_fr.horizontalAdvance("Chrom")
        wm_iq_w = wm_fi.horizontalAdvance("IQ")

        def draw_wordmark() -> None:
            x = page_w - (wm_chrom_w + wm_iq_w)
            base = 1.0 + wm_fr.ascent()
            painter.save()
            painter.setFont(wm_r); painter.setPen(QColor("#1c1b18"))
            painter.drawText(QPointF(x, base), "Chrom")
            painter.setFont(wm_i); painter.setPen(QColor("#ff4573"))
            painter.drawText(QPointF(x + wm_chrom_w - 1.0, base), "IQ")
            painter.restore()

        painter = QPainter(writer)
        layout = doc.documentLayout()
        total = max(1, doc.pageCount())

        def draw_header(pg: int) -> None:
            draw_wordmark()
            if pg == 0:
                return                            # page 1: wordmark only (line is in body)
            # Scope text, left, wrapped by whole units within the width left of
            # the wordmark; and the five-part colour line along the band's bottom.
            painter.save()
            painter.setPen(QColor(90, 90, 90)); painter.setFont(head_font)
            fm = painter.fontMetrics()
            max_w = page_w - (wm_chrom_w + wm_iq_w) - 14.0
            x, y, line_h = 0.0, 8.0, fm.height() + 1.0
            for u in units:
                w = fm.horizontalAdvance(u)
                if x > 0 and x + w > max_w:
                    x = 0.0; y += line_h
                    if y > header_h - 8.0:        # keep it inside the band
                        break
                painter.drawText(QPointF(x, y + fm.ascent()), u)
                x += w
            painter.restore()
            seg = page_w / 5.0
            for i, col in enumerate(TAB_COLORS):
                painter.fillRect(QRectF(i * seg, header_h - 4.0, seg, 3.0), QColor(col))

        for pg in range(total):
            if pg > 0:
                writer.newPage()
            draw_header(pg)
            painter.save()
            painter.translate(0.0, header_h - pg * body_h)
            ctx = QAbstractTextDocumentLayout.PaintContext()
            ctx.clip = QRectF(0, pg * body_h, page_w, body_h)
            layout.draw(painter, ctx)
            painter.restore()
            painter.save()
            painter.setPen(QColor(120, 120, 120)); painter.setFont(foot_font)
            painter.drawText(
                QRectF(0, page_h - footer_h + 2, page_w, footer_h - 2),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                tr("Page {n} of {total}").format(n=pg + 1, total=total))
            painter.restore()
        painter.end()

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _scope_header_units(self, runs: list) -> list:
        """The per-page header units (Knut): each profile name (no quotes), then
        the run count + date range as one unit — wrapped by whole units in the
        painter. Profiles sharing a name collapse to a single entry (#PDF6)."""
        from workflow.measurement_report import report_scope
        sc = report_scope(runs)
        names = list(dict.fromkeys(p["name"] for p in sc["profiles"]))  # de-dup, ordered
        d0, d1 = sc["date_range"]
        n = sc["total"]
        # Listing every name gets unwieldy once there are many (e.g. a folder of
        # imported measurements); past a handful, drop the names and let the run
        # count + date range speak for the scope (Knut).
        if len(names) <= 4:
            units = [nm + ("," if i < len(names) - 1 else "")
                     for i, nm in enumerate(names)]
            units.append("  " + (tr("{n} measurement run").format(n=n) if n == 1
                                  else tr("{n} measurement runs").format(n=n)))
        else:
            units = [tr("{n} measurement runs").format(n=n)]
        units[-1] += f" ({d0} – {d1})"
        # Trailing space on the name units so they don't run together.
        return [(u + " ") if u.endswith(",") else u for u in units]

    # ---- report composition (shared by the window and the PDF) --------------
    @property
    def _ZEBRA_BG(self) -> str:
        """The alternate-row band, read at render time.

        It was a class attribute, which bound the light-theme colour once at
        import and could never follow the palette — leaving every second row
        of every table a light band under light text."""
        return _C["zebra"]

    def _thresholds(self) -> "tuple[float, float]":
        """The (average, maximum) ΔE00 Pass thresholds from the input fields, or
        the module defaults before those fields are built."""
        from workflow.measurement_report import DEFAULT_PASS_AVG, DEFAULT_PASS_MAX
        avg = getattr(self, "_avg_thr_spin", None)
        mx = getattr(self, "_max_thr_spin", None)
        return (float(avg.value()) if avg is not None else DEFAULT_PASS_AVG,
                float(mx.value()) if mx is not None else DEFAULT_PASS_MAX)

    def _runs_for_report(self) -> list:
        """Every saved run of the loaded printer(s) when 'Show all measurement
        runs' is on, else just the loaded one. The same list drives the window
        and the PDF, so they always match (worst-patch count included, Knut)."""
        if (getattr(self, "_all_runs_check", None) is not None
                and self._all_runs_check.isChecked() and self._history):
            # Minus the runs the user unticked in the list — session-only,
            # and the Report Scope says how many are hidden.
            return [r for r in self._history
                    if self._run_key(r) not in self._hidden_runs]
        return [self._report] if self._report else []

    def _metric_table(self, dates: list, data_rows: list) -> str:
        """One metric×run table: a wide, no-wrap Metric column, dated run columns,
        a rule under the header row and a light-grey background on every other
        data row (Knut)."""
        thb = f"border-bottom:1.5px solid {_C['rule']};white-space:nowrap"
        # Date headers inherit the table cellpadding (4 px) like the number cells
        # below them, so they line up on the right; the Metric header keeps its
        # own wide right pad to match the metric column (Knut #PDF3).
        th = ("<tr><th align='left' style='" + thb + ";padding:2px 14px 3px 0'>"
              + html.escape(tr("Metric")) + "</th>"
              + "".join("<th align='right' style='" + thb + "'>"
                        + html.escape(d) + "</th>" for d in dates) + "</tr>")
        body = [th]
        for i, (label, cells) in enumerate(data_rows):
            bg = f" style='background:{self._ZEBRA_BG}'" if i % 2 == 1 else ""
            body.append(f"<tr{bg}><td style='white-space:nowrap;padding-right:14px'>"
                        + html.escape(label) + "</td>" + "".join(cells) + "</tr>")
        # page-break-inside:avoid keeps a whole chunk-table together — if it won't
        # fit, it moves to the next page rather than splitting rows (Knut #PDF4).
        return ("<table cellpadding='4' cellspacing='0' style='border-collapse:"
                "collapse;font-size:11px;margin-bottom:10px;"
                "page-break-inside:avoid'>"
                + "".join(body) + "</table>")

    def _chunked_metric_tables(self, runs: list, row_getters: list) -> str:
        """Stacked metric×run tables, at most :data:`_MAX_RUN_COLS` dated columns
        each, continuing below with the Metric column repeated; oldest run first."""
        out = []
        for i in range(0, len(runs), _MAX_RUN_COLS):
            chunk = runs[i:i + _MAX_RUN_COLS]
            dates = [str(r.get("created") or "")[:10] for r in chunk]
            rows = [(label, [get(r) for r in chunk]) for label, get in row_getters]
            out.append(self._metric_table(dates, rows))
        return "".join(out)

    def _scope_html(self, runs: list) -> str:
        """Report Scope (Knut): which profiles + instruments are included, the run
        count and date range, and red warnings for mixed instruments or missing
        cube colours."""
        from workflow.measurement_report import report_scope
        sc = report_scope(runs)
        verification = self._report_kind(runs) == "verification"

        def _count_label(n: int) -> str:
            if verification:
                return tr("verification run") if n == 1 else tr("verification runs")
            return tr("run") if n == 1 else tr("runs")

        items = "".join(
            "<li>" + html.escape(p["name"]) + ", "
            + html.escape(tr("Instrument: {inst}").format(inst=p["instrument"]))
            + f" <span style='color:{_C['faint']}'>· {p['n']} "
            + html.escape(_count_label(p["n"]))
            + "</span></li>"
            for p in sc["profiles"])
        d0, d1 = sc["date_range"]
        ind = "margin:0 0 0 1.6em"
        intro = (tr("The following profile verification runs are included:")
                 if verification
                 else tr("The following profiles' measurement runs are included:"))
        out = (_h2(tr("Report Scope"))
               + "<div>" + html.escape(intro)
               + "</div><ul style='margin:2px 0 6px'>" + items + "</ul>"
               + "<div><b>" + html.escape(tr("No. of Measurements:")) + "</b></div>"
               + f"<div style='{ind}'>{sc['total']}</div>"
               + "<div><b>" + html.escape(tr("Date range:")) + "</b></div>"
               + f"<div style='{ind}'>{html.escape(d0)} – {html.escape(d1)}</div>")
        # Honesty note: a filtered report must say it is filtered, so it can
        # never pass as the complete history (Sebastian, 2026-08-10).
        hidden = (len(self._history) - len(runs)
                  if getattr(self, "_all_runs_check", None) is not None
                  and self._all_runs_check.isChecked() else 0)
        if hidden > 0:
            note = (tr("One run in the list above is hidden by you (unticked) "
                       "and is not part of this report.") if hidden == 1
                    else tr("{n} runs in the list above are hidden by you "
                            "(unticked) and are not part of this report.")
                    .format(n=hidden))
            out += (f"<div style='color:{_C['fail']};margin-top:6px'>"
                    + html.escape(note) + "</div>")
        return out + self._scope_warnings_html(sc["warnings"])

    def _scope_warnings_html(self, warnings: list) -> str:
        """Red warning block for the Report Scope checks (Knut). Empty when clean."""
        if not warnings:
            return ""
        blocks = []
        for w in warnings:
            if w["kind"] == "instrument":
                lis = "".join(
                    "<li>" + html.escape(o["run"]) + " — "
                    + html.escape(tr("uses {inst}").format(inst=o["instrument"]))
                    + "</li>" for o in w["runs"])
                blocks.append(
                    "<div><b>" + html.escape(tr("Warning — mixed instruments.")) + "</b> "
                    + html.escape(tr(
                        "Every run in a report should come from the same instrument "
                        "and the same printer; the report cannot tell printers apart. "
                        "These runs use a different instrument from the majority "
                        "({dom}):").format(dom=w["dominant"]))
                    + "</div><ul>" + lis + "</ul>")
            elif w["kind"] == "printing":
                # #130 feature A (Q3): the trend changes meaning where the
                # printing method changed — the report marks the point.
                method_labels = {
                    "through-profile": tr("printed through the profile"),
                    "external-cm": tr("printed in another app with colour "
                                      "management"),
                    "raw": tr("printed raw — no profile"),
                    "unrecorded": tr("method not recorded (made before "
                                     "ChromIQ recorded it, or printed "
                                     "outside ChromIQ)"),
                }
                lis = "".join(
                    "<li>" + html.escape(o["run"]) + " — "
                    + html.escape(method_labels.get(o["method"], o["method"]))
                    + "</li>" for o in w["runs"])
                blocks.append(
                    "<div><b>" + html.escape(tr(
                        "Warning — these verifications were not all printed "
                        "the same way.")) + "</b> "
                    + html.escape(tr(
                        "A sheet printed through the profile measures the "
                        "profile; a sheet printed raw measures the printer. "
                        "The trend changes meaning at the point where the "
                        "method changed:"))
                    + "</div><ul>" + lis + "</ul>")
            elif w["kind"] == "corners":
                lis = "".join(
                    "<li>" + html.escape(o["run"]) + " — "
                    + html.escape(tr("missing {names}").format(
                        names=", ".join(_CORNER_LABELS.get(n, (lambda n=n: n))()
                                        for n in o["missing"])))
                    + "</li>" for o in w["runs"])
                blocks.append(
                    "<div><b>" + html.escape(tr("Warning — missing cube colours.")) + "</b> "
                    + html.escape(tr(
                        "These runs are missing one or more of the eight cube "
                        "corners, so their cube-corner figures are less meaningful:"))
                    + "</div><ul>" + lis + "</ul>")
        return (f"<div style='color:{_C['fail']};margin-top:10px'>"
                + "".join(blocks) + "</div>")

    def _how_to_read_html(self) -> str:
        """The plain-language guide. The heading sits OUTSIDE its background frame,
        with a blank line above it like every other section heading (Knut)."""
        body = (
            "<p>" + html.escape(tr(
                "This report compares what your instrument measured against the "
                "chart's design colours (the reference values the chart was built "
                "from). Every number is a colour difference (ΔE00): 0 is a perfect "
                "match, 1–2 is barely visible, and 10 or more is clearly "
                "different.")) + "</p>"
            "<ul>"
            "<li>" + html.escape(tr(
                "Colour accuracy — the ΔE00 across the patches, split so you can "
                "see the bulk of the chart (all patches and the best 95%) apart "
                "from the few hardest patches (the worst 5%). Each metric is judged "
                "against your Pass thresholds.")) + "</li>"
            "<li>" + html.escape(tr(
                "Paper white & darkest black — the brightest and deepest patches "
                "(L*), a quick health check of your paper and maximum ink.")) + "</li>"
            "<li>" + html.escape(tr(
                "Cube corners — paper white, composite black and the six primary "
                "and secondary inks. These say as much about your inks as about "
                "the instrument.")) + "</li>"
            "</ul>"
            "<p>" + html.escape(tr(
                "What the numbers mean depends on how the chart was printed:")) + "</p>"
            "<ul>"
            "<li>" + html.escape(tr(
                "A profiling chart is printed WITHOUT colour management (the raw "
                "print you measure to build a profile). It is not expected to match "
                "the design closely, so the ΔE can look large — that's normal. Here "
                "it is the CHANGE between dated reports that matters, not a single "
                "value.")) + "</li>"
            "<li>" + html.escape(tr(
                "A verification chart is printed THROUGH your finished profile — "
                "ChromIQ converts the sheet itself and prints it with the "
                "printer's colour management off. It SHOULD match the design "
                "closely, so low ΔE and passes mean the profile is still "
                "accurate; rising numbers over time tell you when it's worth "
                "re-profiling. (Printed raw instead, the same sheet is a printer "
                "drift check — the report says which way each sheet was "
                "printed.)")) + "</li>"
            "</ul>"
            "<p>" + html.escape(tr(
                "Because the design reference never changes, comparing dated "
                "reports of the same chart on the same printer is a clean, reliable "
                "signal of drift — ageing inks, a wandering printer, or an "
                "instrument going off. Save a report after each measurement to "
                "build that history. Screen and print colours here are "
                "approximate; the numbers come from your measurement file and are "
                "exact.")) + "</p>")
        return (_h2(tr("How to read this report"))
                + "<table width='100%' cellpadding='12' cellspacing='0'>"
                f"<tr><td style='background:{_C['panel']}'>" + body
                + "</td></tr></table>")

    def _report_results_html(self, runs: list) -> str:
        """Report Results: a Pass/Fail grid, rows = the five threshold metrics,
        columns = dated runs (≤6 per table, continuing below). Pass green, Fail
        red (Knut)."""
        from workflow.measurement_report import accuracy_verdict
        avg_thr, max_thr = self._thresholds()
        verd = {id(r): {x["key"]: x["pass"]
                        for x in accuracy_verdict(r.get("de00") or {}, avg_thr, max_thr)[0]}
                for r in runs}

        def pf(r, key):
            p = verd[id(r)].get(key)
            if p is None:
                return "<td align='center'>—</td>"
            col = _C["pass"] if p else _C["fail"]
            txt = tr("Pass") if p else tr("Fail")
            return (f"<td align='center' style='color:{col};font-weight:bold'>"
                    f"{html.escape(txt)}</td>")

        row_getters = [(_METRIC_LABELS[k](), (lambda r, k=k: pf(r, k)))
                       for k in _ACCURACY_ROW_KEYS]
        detail_on = (getattr(self, "_detail_check", None) is not None
                     and self._detail_check.isChecked())
        if detail_on:
            intro = tr("The following results are extracted from the detailed "
                       "Colour accuracy data shown below for each measurement run.")
        elif len(runs) <= 1:
            intro = tr("The following results are extracted from detailed data for "
                       "the included measurements in this report. To show this data "
                       "create this report again while enabling the checkbox “Show "
                       "detailed data for each run”.")
        else:
            intro = tr("The following results are extracted from detailed data "
                       "(Colour accuracy) for the included measurements in this "
                       "report.")
        # Always start Report Results on a fresh page — the how-to-read section
        # can be long, so it reads cleaner on its own page (Knut).
        return (_h2(tr("Report Results"), page_break=True)
                + f"<div style='color:{_C['dim']};margin-bottom:4px'>" + html.escape(intro)
                + "</div>" + self._chunked_metric_tables(runs, row_getters))

    def _comparison_table_html(self, runs: list) -> str:
        """Side-by-side: the full metric set across every run (columns = dated
        runs, ≤6 per table). Zebra rows, header rule, wide Metric column (Knut)."""
        de = lambda r: (r.get("de00") or {})

        def num(getter, dec):
            return lambda r: f"<td align='right'>{_fmt(getter(r), dec)}</td>"

        def corner_de(r, code):
            for cc in (r.get("corners") or []):
                if cc.get("name") == code:
                    return cc.get("de")
            return None

        row_getters = [(_METRIC_LABELS[k](), num((lambda r, k=k: de(r).get(k)), 2))
                       for k in ("avg_all", "avg_low95", "avg_high5",
                                 "max_all", "max_low95", "std")]
        row_getters += [
            (tr("Paper white L*"),
             num(lambda r: (r.get("paper_white") or {}).get("lab", [None])[0], 1)),
            (tr("Black L*"),
             num(lambda r: (r.get("max_black") or {}).get("lab", [None])[0], 1)),
        ]
        for code in ("W", "K", "R", "G", "B", "C", "M", "Y"):
            lbl = tr("{corner} ΔE00").format(corner=_CORNER_LABELS[code]())
            row_getters.append((lbl, num((lambda r, c=code: corner_de(r, c)), 2)))
        return (_h2(tr("Overview of Measurement Metrics"), page_break=True)
                + self._chunked_metric_tables(runs, row_getters))

    def _report_kind(self, runs: list) -> str:
        """"verification" when every included measurement is a colour-managed
        verification (carries CHROMIQ_VERIFICATION), else "profiling" (#130)."""
        return ("verification"
                if runs and all(r.get("is_verification") for r in runs)
                else "profiling")

    def _report_profile_name(self, runs: list) -> str:
        """The dominant profile/chart name across the included runs."""
        from collections import Counter
        names = [r.get("chart") for r in runs if r.get("chart")]
        return Counter(names).most_common(1)[0][0] if names else ""

    def _report_title(self, runs: list) -> str:
        """The report's first-page title from the user's Preferences → Reports
        prefixes: "<prefix>[ - <profile name>]" — NO date/time (the report shows
        its Created date inside; Knut). The prefix is the profiling or
        verification line depending on the included measurements (#130)."""
        if self._report_kind(runs) == "verification":
            prefix = str(self._settings.get(
                "report_title_verification",
                "Measurement Report - Verification of Profile"))
        else:
            prefix = str(self._settings.get(
                "report_title_profiling",
                "Measurement Report - Profiling of Printer"))
        parts = [prefix.strip() or "Measurement Report"]
        if self._settings.get("report_add_profile_name", True):
            name = self._report_profile_name(runs)
            if name:
                parts.append(name)
        return " - ".join(parts)

    def _report_filename(self, runs: list) -> str:
        """Filesystem-safe PDF name = the title PLUS the date/time (which the
        title itself omits): "<title> - <date_time>.pdf" (#130, Knut).
        self._created is ISO "YYYY-MM-DDTHH:MM:SS" → "YYYY-MM-DD_HH-MM-SS"."""
        import re
        dt = self._created.replace("T", "_").replace(":", "-")
        return re.sub(r'[/\\:*?"<>|]', "_", f"{self._report_title(runs)} - {dt}") + ".pdf"

    def _report_body_html(self, runs: list, *, for_pdf: bool,
                          charts_html: str = "", created: "str | None" = None) -> str:
        """The full report body, shared by the window and the PDF in ONE sequence
        (Knut): Created → Report Scope → How to read → Report Results → trend
        charts (PDF) → Overview of Measurement Metrics (>1 run) → Detailed
        (opt-in). The profile names / date range live in Report Scope now."""
        # Choose the palette before anything is built: the PDF is printed on
        # white paper so it is always the light one, and the window follows the
        # theme. Global because the module-level heading helpers use it too.
        global _C
        _C = dict(_LIGHT_REPORT if for_pdf
                  else (_DARK_REPORT
                        if resolve_mode(self._settings.get("appearance", "auto")) == "dark"
                        else _LIGHT_REPORT))
        if not runs:
            return self._empty_html()
        # A plain "Created: …" line — at the top of the window body, and under
        # the title + spectrum line in the PDF (Knut). The profile line that used
        # to be here is dropped; Report Scope already lists it.
        when = html.escape((created or self._created).replace("T", " "))
        created_line = ("<div style='margin:2px 0 0'>"
                        + html.escape(tr("Created:")) + " " + when + "</div>")
        if for_pdf:
            head = (f"<div style='font-size:22px;font-weight:bold;color:{_C["head"]}'>"
                    + html.escape(self._report_title(runs)) + "</div>"
                    + _colour_line_html() + created_line + "<br>")
        else:
            head = created_line
        parts = [head, self._scope_html(runs), self._how_to_read_html(),
                 self._report_results_html(runs)]
        if for_pdf and charts_html:
            parts.append(
                _h2(tr("Trend over time (this printer)"), page_break=True)
                + f"<div style='color:{_C['dim']};margin-bottom:6px'>" + html.escape(tr(
                    "A rising average or shifting white/black/colour over time "
                    "points to ageing inks, printer drift, or instrument drift."))
                + "</div>" + charts_html)
        if len(runs) > 1:
            parts.append(self._comparison_table_html(runs))
        if getattr(self, "_detail_check", None) is not None \
                and self._detail_check.isChecked():
            parts.append(self._detailed_section_html(runs))
        return (f"<div style='font-family:sans-serif;color:{_C['text']};"
                f"font-size:12px'>"
                + "".join(parts) + "</div>")

    def _pdf_html(self, runs: list, charts_html: str) -> str:
        return self._report_body_html(runs, for_pdf=True, charts_html=charts_html)

    def _update_trends(self, series: list, dark: bool) -> None:
        """Feed the grouped trend charts their metric sets. The tabs stay visible
        whenever a report is loaded — with a single run they show an empty chart
        and an explanatory message (Knut). The accuracy chart also gets the Pass
        thresholds as dotted guide lines."""
        avg_thr, max_thr = self._thresholds()
        for chart, _title, metrics, y_max, dec, auto in self._trend_configs():
            thr = (avg_thr, max_thr) if chart is self._trend_de else None
            chart.set_data(series, metrics, dark=dark, y_max=y_max, dec=dec,
                           auto=auto, thresholds=thr)
        show = bool(self._sources)
        self._trend_label.setVisible(show)
        self._trend_tabs.setVisible(show)

    # ------------------------------------------------------------------
    def _use_theme_palette(self) -> None:
        """Point the HTML builders at the window's palette.

        ``_report_body_html`` does this itself, but the empty and error bodies
        are set straight onto the view, so they need it too — otherwise a
        message shown after a PDF save would still be wearing the PDF's
        light-on-white colours."""
        global _C
        _C = dict(_DARK_REPORT
                  if resolve_mode(self._settings.get("appearance", "auto")) == "dark"
                  else _LIGHT_REPORT)

    def _empty_html(self) -> str:
        self._use_theme_palette()
        return (f"<div style='color:{_C['faint']};padding:24px'>"
                + html.escape(tr("Open a measurement file to see its report."))
                + "</div>")

    def _error_html(self, msg: str) -> str:
        self._use_theme_palette()
        return (f"<div style='color:{_C['error']};padding:24px'>"
                + html.escape(tr("Could not read this measurement: {msg}")
                              .format(msg=msg)) + "</div>")

    def _printing_block_html(self, r: dict) -> str:
        """"How this verification was produced" (#130 feature A, §3.3).

        One account of the measurement's conditions: through the profile or
        raw (and so which QUESTION the figures answer — §3.1b), the rendering
        intent, who printed the sheet, which profile file (A17: flagged when
        the profile has been rebuilt since), the patch-identity verdict (A20)
        and the ΔE reference. Empty for profiling runs with no print record —
        their conditions have not changed."""
        printing = r.get("printing") or {}
        if not printing and not r.get("is_verification"):
            return ""
        colour = printing.get("colour")
        intent_labels = {
            "relative": tr("relative colorimetric"),
            "absolute": tr("absolute colorimetric"),
            "perceptual": tr("perceptual"),
            "saturation": tr("saturation"),
        }
        rows: "list[tuple[str, str, bool]]" = []   # (label, value, is_warning)
        if colour == "through-profile" and printing.get("route") == "external-cm":
            # The user's own answer at measure time (M-HOW-PRINTED): the
            # sheet went through another application's colour management.
            rows.append((tr("What this measured"), tr(
                "your whole everyday printing chain — the application's "
                "colour engine, this profile and the printer together"),
                False))
            rows.append((tr("Printed"), tr(
                "in another application with colour management (your answer "
                "when the sheet was measured)"), False))
        elif colour == "through-profile":
            intent = intent_labels.get(printing.get("intent") or "relative",
                                       printing.get("intent") or "")
            rows.append((tr("What this measured"), tr(
                "how accurate this profile is — the sheet was the profile's "
                "own prediction, made real"), False))
            rows.append((tr("Printed"),
                         tr("through this run's profile") + " · " + intent,
                         False))
        elif colour == "raw":
            rows.append((tr("What this measured"), tr(
                "whether this printer has changed — no profile took part, so "
                "this is a drift check, not a profile check"), False))
            rows.append((tr("Printed"), tr("raw — no profile applied"), False))
        else:
            rows.append((tr("Printed"), tr(
                "not recorded — this sheet was printed before ChromIQ "
                "recorded the method, or outside ChromIQ. Sheets ChromIQ "
                "printed before it kept this record always went out raw."),
                False))
        route = printing.get("route")
        if route == "chromiq":
            rows.append((tr("Colour management at the printer"), tr(
                "off — ChromIQ printed the sheet itself"), False))
        elif route == "external":
            rows.append((tr("Colour management at the printer"), tr(
                "printed in another application, which was asked not to "
                "convert the colours"), False))
        if printing.get("profile"):
            when = str(printing.get("printed_at") or "")[:10]
            rows.append((tr("Profile"), printing["profile"]
                         + (f" · {when}" if when else ""), False))
            if printing.get("profile_changed_since_print"):
                rows.append((tr("Take care"), tr(
                    "the profile has been rebuilt since this sheet was "
                    "printed, so these figures describe an older profile "
                    "than the one now in the run"), True))
            elif printing.get("profile_missing_now"):
                rows.append((tr("Take care"), tr(
                    "the profile this sheet was printed through is no longer "
                    "on disk"), True))
        pi = r.get("patch_identity") or {}
        verdict = pi.get("verdict")
        if verdict == "verified":
            rows.append((tr("Readings belong to this chart"), tr(
                "verified — every patch holds the colour the chart asked "
                "for"), False))
        elif verdict == "mismatch":
            rows.append((tr("Readings belong to this chart"), tr(
                "no — see the warning below the colour-accuracy table"), True))
        else:
            rows.append((tr("Readings belong to this chart"),
                         tr("could not be checked"), False))
        # Pairing 3: say WHICH yardstick judged the sheet, in plain words,
        # so a media-relative score can never be mistaken for an absolute one.
        if r.get("yardstick") == "media-relative":
            rows.append((tr("How the colours were judged"), tr(
                "relative to this sheet's own paper white — the print mapped "
                "white to the paper, so the paper itself is not counted "
                "against the profile"), False))
        elif r.get("is_verification") and r.get("yardstick") == "absolute" \
                and (r.get("printing") or {}).get("colour"):
            rows.append((tr("How the colours were judged"), tr(
                "as measured (absolute) — every difference counts, the "
                "paper's own tone included"), False))
        ref = r.get("reference_source")
        if ref == "colorimetric":
            cm = r.get("colorimetric") or {}
            detail = tr("the profile's own colorimetric targets")
            if cm.get("set_version"):
                detail += f" · {cm['set_version']}"
            if cm.get("in_gamut") and cm.get("master_total"):
                detail += " · " + tr(
                    "{n} of {total} master colours in this profile's gamut"
                ).format(n=cm["in_gamut"], total=cm["master_total"])
            rows.append((tr("Reference for the ΔE figures"), detail, False))
        elif ref == "colorimetric-missing":
            rows.append((tr("Reference for the ΔE figures"), tr(
                "missing — this chart's stored colorimetric targets could not "
                "be found, so no ΔE figures are shown. Comparing against "
                "anything else would produce plausible numbers from the wrong "
                "yardstick."), True))
        elif ref == "device":
            rows.append((tr("Reference for the ΔE figures"), tr(
                "the sRGB estimate of the chart's device values"), False))
        elif ref:
            rows.append((tr("Reference for the ΔE figures"), tr(
                "the chart's design colours"), False))
        trs = []
        for label, value, warn in rows:
            colour_css = _C["fail"] if warn else _C["text"]
            trs.append(
                f"<tr><td style='padding-right:14px;color:{_C['faint']};"
                "vertical-align:top' width='230'>" + html.escape(label)
                + f"</td><td style='color:{colour_css}'>"
                + html.escape(value) + "</td></tr>")
        return (_h3(tr("How this verification was produced"))
                + "<table cellpadding='4' cellspacing='0' "
                "style='border-collapse:collapse;font-size:11px'>"
                + "".join(trs) + "</table>")

    def _run_detail_html(self, r: dict) -> str:
        """One run's full breakdown: the colour-accuracy Pass/Fail table
        (Metric / Measured ΔE00 / Threshold / Result), paper white & black, the
        cube corners, and the 16 worst patches (Knut)."""
        de = r.get("de00") or {}
        parts = []
        produced = self._printing_block_html(r)
        if produced:
            parts.append(produced)
        if de.get("avg_all") is not None:
            from workflow.measurement_report import accuracy_verdict
            avg_thr, max_thr = self._thresholds()
            rows, _ = accuracy_verdict(de, avg_thr, max_thr)
            head = (f"<tr style='color:{_C['faint']}'>"
                    f"<th align='left' style='border-bottom:1.5px solid {_C['rule']}'>"
                    + html.escape(tr("Metric")) + "</th>"
                    f"<th align='right' style='border-bottom:1.5px solid {_C['rule']}'>"
                    + html.escape(tr("Measured ΔE00")) + "</th>"
                    f"<th align='right' style='border-bottom:1.5px solid {_C['rule']}'>"
                    + html.escape(tr("Threshold")) + "</th>"
                    f"<th align='center' style='border-bottom:1.5px solid {_C['rule']}'>"
                    + html.escape(tr("Result")) + "</th></tr>")
            trs = [head]

            def row_html(i, label, measured, threshold, verdict):
                bg = f" style='background:{self._ZEBRA_BG}'" if i % 2 == 1 else ""
                if verdict is None:
                    res = "—"
                else:
                    col = _C["pass"] if verdict else _C["fail"]
                    res = (f"<span style='color:{col};font-weight:bold'>"
                           + html.escape(tr("Pass") if verdict else tr("Fail"))
                           + "</span>")
                return (f"<tr{bg}><td style='padding-right:14px'>{html.escape(label)}</td>"
                        f"<td align='right'><b>{_fmt(measured)}</b></td>"
                        f"<td align='right'>{_fmt(threshold) if threshold is not None else '—'}</td>"
                        f"<td align='center'>{res}</td></tr>")

            for i, row in enumerate(rows):
                trs.append(row_html(i, _METRIC_LABELS[row["key"]](), row["value"],
                                    row["threshold"], row["pass"]))
            # Spread is reported for completeness but carries no threshold (Knut).
            trs.append(row_html(len(rows), _METRIC_LABELS["std"](),
                                de.get("std"), None, None))
            device_ref = r.get("reference_source") == "device"
            # Both cases compare against the chart's DESIGN — either straight from
            # the .ti2, or reconstructed from the device values — so the heading is
            # the same; the note below explains the reconstruction (Knut).
            parts.append(_h3(tr("Colour accuracy (ΔE00 vs the chart's design)")))
            parts.append("<table cellpadding='5' cellspacing='0' "
                         "style='border-collapse:collapse;font-size:11px'>"
                         + "".join(trs) + "</table>")
            if device_ref:
                parts.append(f"<p style='color:{_C['faint']};font-size:10px'>" + html.escape(tr(
                    "No design file (.ti2) sits next to this measurement, so the "
                    "expected colour of each patch is the sRGB estimate of its "
                    "device values — the fixed code values sent to the printer, "
                    "the chart's design, identical for every run. This is exactly "
                    "the reference a .ti2 would carry, so it stays static across "
                    "runs. Typical for imported i1Profiler measurements.")) + "</p>")
        elif r.get("reference_source") == "colorimetric-missing":
            # #133 §9.1: refusing beats a plausible number from the wrong
            # yardstick — say what could not be established (the beta.206 rule).
            parts.append(
                f"<p style='color:{_C['error']};font-size:11px;"
                f"border:1px solid {_C['error']};border-radius:4px;"
                "padding:8px 11px;line-height:1.45'>"
                + "<b>" + html.escape(tr(
                    "No colour-accuracy figures, on purpose.")) + "</b><br><br>"
                + html.escape(tr(
                    "This chart was built from your profile's own gamut, so "
                    "its measurements can only be judged against the "
                    "colorimetric targets that were stored beside the chart "
                    "when it was made — and that reference file cannot be "
                    "found. Comparing against anything else would produce "
                    "confident-looking numbers measured against the wrong "
                    "yardstick, so ChromIQ shows none at all."))
                + "<br><br>" + html.escape(tr(
                    "If the file was moved, put it back next to the chart in "
                    "the run's “verifications” folder and reopen this report. "
                    "If it is gone for good, generate the verification chart "
                    "again — a fresh chart brings a fresh reference with it."))
                + "</p>")
        else:
            parts.append(f"<p style='color:{_C['faint']}'>" + html.escape(tr(
                "This measurement has no device values to compare against, so "
                "colour-accuracy statistics aren't available — only the paper white "
                "and black below.")) + "</p>")

        # WHEN THE READINGS MAY NOT LINE UP WITH THE CHART, SAY SO ABOVE THE
        # NUMBERS THEY WOULD INVALIDATE.
        #
        # The figures above are only meaningful if each reading really belongs
        # to the chart patch it was compared with. That pairing is by patch
        # number, and for a measurement returned from i1Profiler the number is
        # only the position in the file — so a reordering somewhere in the
        # chain silently compares every patch with the wrong one. The check is
        # reported, never acted on: nothing above is suppressed or altered.
        pi = r.get("patch_identity") or {}
        if pi.get("verdict") == "mismatch":
            bad, total = pi.get("mismatched") or 0, pi.get("compared") or 0
            # Count-aware, with a real singular — never "patch(es)".
            found = (tr("Here one patch out of {total} came back as a "
                        "completely different colour.").format(total=total)
                     if bad == 1 else
                     tr("Here {bad} patches out of {total} came back as "
                        "completely different colours.").format(bad=bad,
                                                                total=total))
            parts.append(
                f"<p style='color:{_C['error']};font-size:11px;"
                f"border:1px solid {_C['error']};border-radius:4px;"
                "padding:8px 11px;line-height:1.45'>"
                + "<b>" + html.escape(tr(
                    "These readings might not belong to the chart they were "
                    "compared with, so please treat the figures above with "
                    "care.")) + "</b><br><br>"
                + html.escape(tr(
                    "Every time ChromIQ works out a report, it checks each "
                    "patch against the colour the chart asked the printer "
                    "for. The two should agree.")) + " " + html.escape(found)
                + "<br><br>" + html.escape(tr(
                    "That usually means one of two things: either this "
                    "measurement belongs to a different chart, or the patches "
                    "ended up in a different order somewhere between creating "
                    "the chart and measuring it. The second one can happen "
                    "when a chart is measured in another program, if that "
                    "program rearranges the patches for its own layout."))
                + "<br><br>" + html.escape(tr(
                    "Nothing has been changed or hidden. The figures above "
                    "were worked out in the usual way and your measurement "
                    "file has not been touched. It is worth checking that "
                    "this measurement really belongs to this chart — and, if "
                    "you measured it in another program, that the program "
                    "kept the patches in the order ChromIQ sent them."))
                + "</p>")

        w, b = r.get("paper_white"), r.get("max_black")
        if w and b:
            parts.append(_h3(tr("Paper white & darkest black")))
            parts.append(
                f"<div>{_swatch(w['hex'])} " + html.escape(tr("White"))
                + f" ({html.escape(str(w['loc']))}) — L* {w['lab'][0]:.1f}</div>"
                f"<div>{_swatch(b['hex'])} " + html.escape(tr("Black"))
                + f" ({html.escape(str(b['loc']))}) — L* {b['lab'][0]:.1f}</div>")

        corners = r.get("corners") or []
        if corners:
            parts.append(_h3(tr("Cube corners (the eight ink extremes)")))
            head = (f"<tr style='color:{_C['faint']}'><th align='left'>" + html.escape(tr("Corner"))
                    + "</th><th>" + html.escape(tr("Expected")) + "</th><th>"
                    + html.escape(tr("Measured")) + "</th><th align='right'>ΔE00</th></tr>")
            crows = [head]
            for i, c in enumerate(corners):
                lbl = _CORNER_LABELS.get(c["name"], (lambda: c["name"]))()
                exp = _swatch(c["expected_hex"]) if c.get("expected_hex") else "—"
                de_c = f"<b>{_fmt(c.get('de'))}</b>" if c.get("de") is not None else "—"
                miss = "" if c.get("present", True) else (
                    f" <span style='color:{_C['fail']}'>(" + html.escape(tr("missing"))
                    + ")</span>")
                bg = f" style='background:{self._ZEBRA_BG}'" if i % 2 == 1 else ""
                crows.append(
                    f"<tr{bg}><td>{html.escape(lbl)}{miss} "
                    f"<span style='color:{_C['faint']}'>({html.escape(str(c['loc']))})</span></td>"
                    f"<td align='center'>{exp}</td>"
                    f"<td align='center'>{_swatch(c['hex'])}</td>"
                    f"<td align='right'>{de_c}</td></tr>")
            parts.append("<table cellpadding='5' cellspacing='0' "
                         "style='border-collapse:collapse;font-size:11px'>"
                         + "".join(crows) + "</table>")

        worst = r.get("worst_patches") or []
        if worst:
            # Two 8-row halves side by side in one 9-column table (empty middle
            # column) — same columns, half the height (Knut).
            parts.append(_h3(tr("Worst patches")))

            def wcells(p) -> str:
                if p is None:
                    return "<td></td><td></td><td></td><td></td>"
                # Patch · Expected · Measured · ΔE00 — the same column order as the
                # Cube-corners table, so the two read the same (Knut).
                return (f"<td>{html.escape(str(p['loc']))}</td>"
                        f"<td align='center'>{_swatch(p['expected_hex'])}</td>"
                        f"<td align='center'>{_swatch(p['measured_hex'])}</td>"
                        f"<td align='right'><b>{_fmt(p['de'])}</b></td>")

            hdr = ("<th align='left'>" + html.escape(tr("Patch")) + "</th><th>"
                   + html.escape(tr("Expected")) + "</th><th>"
                   + html.escape(tr("Measured")) + "</th><th align='right'>ΔE00</th>")
            half = (len(worst) + 1) // 2
            left, right = worst[:half], worst[half:]
            rows = [f"<tr style='color:{_C['faint']}'>" + hdr
                    + "<th style='width:16px'></th>" + hdr + "</tr>"]
            for i in range(half):
                lp = left[i] if i < len(left) else None
                rp = right[i] if i < len(right) else None
                rows.append("<tr>" + wcells(lp) + "<td></td>" + wcells(rp) + "</tr>")
            parts.append("<table cellpadding='5' cellspacing='0' "
                         "style='border-collapse:collapse;font-size:11px'>"
                         + "".join(rows) + "</table>")

        return "<div>" + "".join(parts) + "</div>"

    def _detailed_section_html(self, runs: list) -> str:
        """The opt-in 'Detailed data per measurement run' section: each run on its
        own page, led by a 'Measurement run — date — N patches' heading and the
        profile name (Knut)."""
        out = [_h2(tr("Detailed data per measurement run"), page_break=True)]
        for idx, run in enumerate(runs):
            brk = "page-break-before:always;" if idx > 0 else ""
            out.append(
                f"<h3 style='color:{_C["head"]};{brk}"
                f"border-bottom:1px solid {_C['hair']};"
                f"margin:12px 0 2px'>"
                + html.escape(tr("Measurement run — {date} — {n} patches").format(
                    date=str(run.get("created") or ""), n=run.get("patches", 0)))
                + "</h3>"
                f"<div style='color:{_C['dim']};margin-bottom:4px'>"
                + html.escape(tr("Profile name: {name}").format(
                    name=run.get("chart") or "")) + "</div>"
                + self._run_detail_html(run))
        return "".join(out)
