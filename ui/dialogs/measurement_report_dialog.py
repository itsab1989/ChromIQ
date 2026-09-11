"""Measurement report viewer (Knut): accuracy statistics for a measured chart
and drift comparison over time.

Pick a measurement (.ti3); the dialog shows how the reading compares to the
chart's expected colours — mean / median / worst / spread ΔE00, the worst
patches with their colours, and the paper white and darkest black. "Save this
report" keeps a timestamped copy next to the chart so later measurements of
the same chart can be compared, revealing ink / printer / instrument drift.
"""
from __future__ import annotations

import copy
import html
import json
from functools import partial
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QTabWidget, QTextBrowser,
    QVBoxLayout, QWidget,
)

from core.i18n import tr
from core.logger import get_logger
from core.text_io import read_text
from ui import neutral_styles
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
#: the limit-set row id of each old de00 key (a recorded verdict written
#: before #182 carries only the key)
_ROW_ID_OF = {"avg_all": "all_de00_avg", "avg_low95": "best95_de00_avg",
              "avg_high5": "worst5_de00_avg", "max_all": "all_de00_max",
              "max_low95": "all_de00_p95"}
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
    "cond": "#9a5b00", "swatch_edge": "#999999",
}
_DARK_REPORT = {
    "text": "#e6e6e6", "head": "#e6e6e6", "dim": "#b8b8b8", "faint": "#9a9a9a",
    "rule": "#5a5a5a", "hair": "#3a3a3a", "zebra": "#272727", "panel": "#232323",
    "pass": "#4fd77a", "fail": "#ff6f61", "error": "#ff6f61",
    "cond": "#f0b35a", "swatch_edge": "#6a6a6a",
}
#: Neutral. NO HUE CARRIES A VERDICT HERE: the report already writes the words
#: "Pass" and "Fail" in bold beside every colour it sets, so the greens and
#: reds were reinforcement, not the message. Pass recedes to tertiary ink and a
#: failure takes full ink — the handoff's "a page of passes should look calm,
#: a failing row is findable while scrolling without reading". The GLYPHS that
#: complete that rule (solid disc / triangle / square, a 1px underline, a 3px
#: left bar) are a component job and are not here yet; until they land the two
#: verdicts differ by ink weight and the word alone.
#:
#: The PDF is untouched by this: ``_report_body_html`` picks ``_LIGHT_REPORT``
#: whenever ``for_pdf`` is set, because the report leaves the building, gets
#: printed, and is read by someone who never chose an appearance.
_NEUTRAL_REPORT = {
    "text": neutral_styles.NM_TEXT_MAIN,   "head": neutral_styles.NM_TEXT_MAIN,
    "dim":  neutral_styles.NM_TEXT_DIM,    "faint": neutral_styles.NM_TEXT_FAINT,
    "rule": neutral_styles.NM_BORDER,      "hair": neutral_styles.NM_DISABLED,
    "zebra": neutral_styles.NM_BG_SURFACE, "panel": neutral_styles.NM_BG_SURFACE,
    "pass": neutral_styles.NM_TEXT_FAINT,  "fail": neutral_styles.NM_TEXT_MAIN,
    "error": neutral_styles.NM_TEXT_MAIN,  "cond": neutral_styles.NM_TEXT_DIM,
    "swatch_edge": neutral_styles.NM_BORDER,
}
#: ``{appearance: palette}``. The two picks below were
#: ``_DARK_REPORT if … == "dark" else _LIGHT_REPORT`` — which gave Neutral the
#: LIGHT report by accident. Readable, and wrong: it is the warm light palette
#: with green and red verdicts in a theme that has no hue.
_REPORTS = {
    "light":   _LIGHT_REPORT,
    "dark":    _DARK_REPORT,
    "neutral": _NEUTRAL_REPORT,
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
    spaces hidden by matching the text colour to the fill.

    NO COLOUR IS NOT WHITE. The fallback used to be `#ffffff`, so a patch with
    no expected colour — every patch of a converted chart whose colorimetric
    reference file is gone, which §9.1 deliberately refuses to guess for — drew
    a white block in the "Asked for" column, on the one page meant to be handed
    to a customer. It reads as the same nothing the ΔE column reads.
    """
    if not hexc:
        return _fmt(None)
    c = html.escape(hexc)
    return (f"<span style='background-color:{c};color:{c};"
            f"border:1px solid {_C["swatch_edge"]}'>&nbsp;&nbsp;&nbsp;</span>")


def _colour_line_html(height: int = 5) -> str:
    """The ChromIQ five-part spectrum line as a full-width rich-text table row."""
    cells = "".join(
        f"<td width='20%' style='background:{c};font-size:1px;line-height:1px'>"
        f"&nbsp;</td>" for c in TAB_COLORS)
    return (f"<table width='100%' cellpadding='0' cellspacing='0' "
            f"style='height:{height}px;margin:0'><tr>{cells}</tr></table>")


def _report_needs_rebuilding(rep: dict) -> bool:
    """Whether a saved report must be recomputed from its measurement.

    A MODULE-LEVEL FUNCTION SO A TEST CAN CALL THE REAL RULE. It lived inline
    in the loop, so the only way to check it was to copy it into a test, and a
    copy proves nothing about the app: a mutation that broke the window left
    every behavioural assertion green.

    Two reasons a report is out of date, and the second cannot be seen in a
    schema number.

    An OLDER SCHEMA carries a metric set that predates the current one, so the
    window would show "no accuracy data" for it.

    And A ROW THAT WAS NEVER COMPUTED is stale at the current schema. Grey
    balance and the 30 to 70 per cent ramps were added ADDITIVELY, deliberately
    without bumping the schema so no report on disk would be re-derived. But
    4.2.0 already wrote schema 7 and had no grey balance in its builder at all,
    so every report saved by 4.2.0 and the first two betas passed this test, was
    never rebuilt, and showed N-A on both grey rows for ever. Surveyed on one
    real disk: 58 saved reports, none with a grey block, 33 already at schema 7.

    Worse than missing: the reason printed beside the N-A said the measurement
    file could not be read again, which is untrue. It was never asked for, and
    the number it was hiding was in the same folder.

    The caller carries the saved verdict across a rebuild untouched, so this
    computes rows that were never computed and re-grades nothing.
    """
    from workflow.measurement_report import REPORT_SCHEMA
    return (rep.get("schema", 0) < REPORT_SCHEMA
            or (rep.get("de00") or {}).get("avg_all") is None
            or "grey_balance" not in rep
            or "ramps_30_70" not in rep)


def _h2(text: str, *, page_break: bool = False) -> str:
    """A main section heading, matching 'Trend over time (this printer)' etc.

    A styled div, not an <h2>: Qt sizes h-tags from the *application*
    default font and ignores any font-size set on or inside them, so a PDF
    exported outside the running app (a test driver, a script) came out
    with headings ~10% smaller than the same report saved from the app
    (measured 2026-08-13). A div honours an explicit px size, which makes
    the report identical wherever it is rendered. 20px matches what the
    app's h2 rendered.
    """
    brk = "page-break-before:always;" if page_break else ""
    return (f"<div style='color:{_C["head"]};{brk}font-size:20px;"
            f"font-weight:bold;margin-top:14px;margin-bottom:4px'>"
            f"{html.escape(text)}</div>")


def _h3(text: str) -> str:
    return (f"<div style='color:{_C["head"]};font-size:16px;"
            f"font-weight:bold;margin-top:12px;margin-bottom:3px'>"
            f"{html.escape(text)}</div>")


def _gap() -> str:
    """One small empty line (Sebastian, 2026-08-13): air under the main
    section headlines, after their intro lines, and between the trend
    charts — the same in the window and the saved PDF."""
    return "<p style='font-size:8px;margin:0'>&nbsp;</p>"


def _fmt(v, dec: int = 2) -> str:
    if isinstance(v, str):
        return html.escape(v)          # already formatted (the 3-decimal FAIL case)
    return f"{v:.{dec}f}" if isinstance(v, (int, float)) else "—"


def _is_raw_drift(r: dict) -> bool:
    """A recorded-raw verification sheet judged against the design: its job is
    drift, not accuracy — Pass/Fail against the profile thresholds would fail
    a healthy printer forever (Knut, 2026-08-11). Unrecorded sheets keep the
    old grading: nobody knows how they were printed.

    The rule itself moved to `workflow.measurement_report.is_drift_check` when
    the verdict started being SAVED (#182): the verdict written into a report
    and the verdict drawn in this window have to agree about which sheets are
    graded at all, and a second copy of the rule would eventually not."""
    from workflow.measurement_report import is_drift_check
    return is_drift_check(r)


# The table/heading pagination moved to ui/pdf_layout.py in #164, so the printed
# Help cards obey the same rules rather than growing a second copy of them. Kept
# under its old name here: this module's own callers, and its tests, know it by
# that name and the behaviour is unchanged.
from ui.pdf_layout import paginate_tables as _paginate_tables  # noqa: E402


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
                tr("A trend graph needs at least two measurement runs. Add "
                   "another measurement — or, if the profile you have loaded "
                   "already holds more than one run, tick “Show all "
                   "measurement runs” above."))
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
            # each other (Sebastian, 2026-08-10). Dropping the words entirely
            # in that case looked clean in isolation but read as a regression
            # on real reports ("the Max and Avg labels are gone" — Knut,
            # 2026-08-11): the words must ALWAYS be drawn. So: clean margin
            # placement when it fits; otherwise both words move inside the
            # plot at the lines' left tips, the UPPER line's word above it
            # and the LOWER line's word below it, so the two diverge instead
            # of stacking however close the lines sit.
            collide = any(abs(ty - ay) < 9.0 for ty in thr_ys for ay in axis_ys)
            if len(thr_ys) == 2 and abs(thr_ys[0] - thr_ys[1]) < 11.0:
                collide = True
            for (tv, tlab), yy in zip(thr, thr_ys):
                p.setPen(tpen)
                p.drawLine(QPointF(L, yy), QPointF(L + w, yy))
            p.setPen(QPen(fg, 1.0))
            if not collide:
                for (tv, tlab), yy in zip(thr, thr_ys):
                    p.drawText(QRectF(0, yy - 7, L - 4, 14),
                               Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter,
                               tlab)
            else:
                order = sorted(range(len(thr)), key=lambda i: thr_ys[i])
                for rank, i in enumerate(order):
                    yy, tlab = thr_ys[i], thr[i][1]
                    above = rank == 0          # the upper line's word above it
                    top = yy - 16 if above else yy + 2
                    # never outside the plot: clamp, keeping above/below sense
                    top = min(max(top, T), T + h - 14)
                    p.drawText(QRectF(L + 4, top, 80, 14),
                               Qt.AlignmentFlag.AlignLeft
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

        days = [str(pt.get("created") or "")[:10] for pt in pts]
        shared_days = {d for d in days if days.count(d) > 1}

        def _lab(i: int) -> str:
            # Several checks on one day: the date alone reads as the same
            # point over and over, so those labels carry the time as well
            # ("2026-08-10 11:36" — Knut, 2026-08-11). Unique days stay short.
            c = str(pts[i].get("created") or "")
            if c[:10] in shared_days and len(c) >= 16:
                return f"{c[:10]} {c[11:16]}"
            return c[:10]

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


class _NothingToRestore(Exception):
    """The refusal had nothing to undo, so nothing is written."""


def _restore_sentence(outcome: str, refused: bool = True) -> str:
    """What really happened to the run's own numbers, in one sentence.

    ONE PLACE, BECAUSE TWO MESSAGES ASK THE SAME QUESTION and they had grown
    different answers to it. It used to be a yes/no, and `_undo_the_edit` has
    three branches, so one of them borrowed another's sentence: the branch that
    leaves the REFUSED numbers on a run bound to a set this build cannot answer
    for said only that the numbers could not be put back, and never that the
    run is now judged by the numbers the user had just said no to.

    AND ONE OF THE TWO CALLERS NEVER ASKS THE USER ANYTHING. The locked-
    meanwhile window follows no question: the edit was stopped by the lock, so
    there is no refusal and no other change for one to be "gone" beside. Both
    sentences that said so were false there, and a challenge round photographed
    them. `refused` is which of the two situations this is.
    """
    if outcome == "restored":
        return (tr("Its dated reports are unchanged, and ChromIQ put this "
                   "run's own numbers back to what they were when you opened "
                   "the window, so the other change is gone too.")
                if refused else
                tr("Its limits and its dated reports are unchanged."))
    if outcome == "rederived":
        # TRUE IN BOTH OF ITS CASES, which the first wording was not: this
        # branch fires for a run that was UNBOUND when the window opened and
        # for one another writer has since rebound, and the first draft
        # described only the former.
        return tr("Its dated reports are unchanged. This run is no longer bound "
                  "to what it was when you opened the window, so ChromIQ could "
                  "not put its own numbers back. It now holds the numbers of "
                  "the limit set it is bound to.")
    if outcome == "refused_numbers_left":
        return (tr("Its dated reports are unchanged, but this run is bound to "
                   "a limit set this version of ChromIQ does not know, so "
                   "ChromIQ left its numbers alone: it still holds the numbers "
                   "you have just refused and is judged by them.")
                if refused else
                tr("Its dated reports are unchanged, but this run is bound to "
                   "a limit set this version of ChromIQ does not know, so "
                   "ChromIQ left its numbers alone: it still holds the numbers "
                   "you were editing and is judged by them."))
    return tr("Its dated reports are unchanged, but ChromIQ could not put this "
              "run's own numbers back.")


class MeasurementReportDialog(QDialog):
    #: The three facts a refusal has to report, set on the way through
    #: `_on_open_limits` and read by the three `_say_*` methods. Declared here
    #: so a path that reaches one of them without going through that function
    #: gets a defined answer rather than an AttributeError.
    _pending_restore_error: "Exception | None" = None
    _pending_rebound: bool = False
    _pending_restore_outcome: str = "none"
    #: what the run was judged by when this window last drew its controls
    _run_state_at_sync: tuple = ()
    #: why the last `_confirm_about_run` returned False
    _last_refusal: str = ""

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
        # Width only — the HEIGHT minimum must stay the layout's own: an
        # explicit 640 px minimum let the window shrink ~200 px below what
        # the content honestly needs, and Qt answered by painting Close over
        # the report and squeezing the charts to an unreadable strip
        # (Sebastian, 2026-08-11, running from source). With no explicit
        # minimum the layout's minimum governs and resizing simply stops
        # before anything can overlap. Screens too small for that minimum
        # are handled in showEvent (compact list, then shorter charts).
        self.setMinimumWidth(760)
        # Open TALL: everything above the report view has a fixed height,
        # so near the minimum the report text itself was a ~90 px sliver —
        # "hard to get any information out of it" (Sebastian, 2026-08-10).
        # The view carries the stretch, so every extra pixel goes to the
        # report.
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
            "clean signal of drift: ageing inks, a printer slowly wandering, or "
            "an instrument going off.\n\n"
            "Two ways to use it\n"
            "  • Profiling runs: after building a profile, check how faithfully "
            "the chart reproduced.\n"
            "  • Verification runs: the most valuable habit: print a small chart "
            "THROUGH your finished profile (a colour-managed print, the "
            "“Verification measurement” option on the Measure tab), measure it "
            "every so often, and save a report each time. When the Pass/Fail "
            "results start slipping, that's your sign the printer has drifted far "
            "enough to re-profile. A tiny verification chart is enough; you're "
            "watching the trend, not building a profile.\n\n"
            "Building the report\n"
            "The report covers a list of profiles' measurements, shown in the "
            "list box. Use “Add Profile's Measurements…” to add a profile (pick "
            "any of its .ti3 files and ChromIQ gathers all its runs), and "
            "“Remove Profile's Measurements…” / “Clear List” to take profiles out. "
            "“Show all measurement runs” switches between the single loaded "
            "measurement and every run of every listed profile. The trend graphs "
            "need at least two runs; with a single run each graph is drawn empty "
            "and says so. Only combine profiles from the SAME printer (see "
            "below).\n\n"
            "The sections\n"
            "  • Report Scope: which profiles and instruments are in the report, "
            "the run count and date range. IMPORTANT: the report cannot tell which "
            "printer a measurement came from. It is up to YOU to only include runs "
            "from the same printer. A good habit is a clear name in “Printer "
            "profile project name” on the “1. Create Chart” tab (include the "
            "printer and the paper, for example), so profiles from one printer "
            "are easy to pick out. As a safety net "
            "the report still warns you if the runs you loaded use different "
            "instruments, or if a chart is missing any of the eight cube corners "
            "(which would make its cube-corner figures unreliable).\n"
            "  • Report Results: one of five words per row and run (PASS, FAIL, "
            "COND, INFO, N-A), with the column's Overall word and what it was "
            "judged against.\n"
            "  • Colour accuracy: the ΔE00 (colour difference) figures, split so "
            "the bulk of the chart (all patches, and the best 95 %) is separated "
            "from the few hardest patches (the worst 5 %). Each is judged against "
            "the run's limit set. 0 is perfect, 1–2 is barely visible, 10+ is "
            "clearly wrong.\n"
            "  • Trend over time: the same metrics plotted across every saved "
            "measurement, so a slow rise or a sudden jump stands out at a glance.\n"
            "  • Overview of Measurement Metrics: every metric for every run in "
            "one table.\n"
            "  • Detailed data per run (optional): the full breakdown for each "
            "run: the accuracy table, paper white & black, the cube corners and "
            "the sixteen worst patches.\n\n"
            "Limit sets\n"
            "A limit set is one column of the limits table: the numbers a report "
            "is judged against, one per row. ChromIQ default (2.0 on the averages, "
            "3.0 on the maxima) is the right choice for checking a profile you "
            "built; ChromIQ tight is half of that, Quick check twice. The set is "
            "chosen once per profile run and every dated verification of that "
            "run is judged with the same numbers, so your history stays "
            "comparable. Open the limits table with “Show limits…” to see every "
            "set side by side; edit the sets in Preferences → Reports.\n\n"
            "Options\n"
            "  • Show all measurement runs: the whole printer's history, not just "
            "the loaded one.\n"
            "  • Show detailed data for each run: add the per-run breakdown.\n"
            "  • Save report as PDF: a ChromIQ-styled PDF you can keep or share; "
            "it opens automatically. Reveal folder opens where it was saved.\n\n"
            "Using i1Profiler measurements\n"
            "You can feed this report measurements made in i1Profiler (handy when "
            "you measured with an i1iSis or i1iO, which lay out their own charts). "
            "Just two steps:\n"
            "  1. Export the measurement from i1Profiler as a text file.\n"
            "  2. Convert it with Tools → “Convert i1Profiler → TI3”, then add the "
            "resulting .ti3 here with “Add Profile's Measurements…”.\n"
            "That's all; you get the full colour-accuracy figures, no extra "
            "reference file needed. ChromIQ works out each patch's expected colour "
            "from the device values recorded in the file (the RGB / ink code "
            "values sent to the printer, which are the chart's fixed design and "
            "the same for every print), so the reference stays just as static "
            "across runs as a .ti2 would. (If a matching .ti2 happens to sit next "
            "to the .ti3, that's used instead.) The instrument is read from the "
            "i1Profiler file during conversion.\n"
            "Keeping things tidy: convert into the same folder as your i1Profiler "
            "files, add the .ti3, and save the PDF report right there, so your "
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
        # Knut's beta.5 point (one scrollbar above the chart tabs) is served
        # by the RUN LIST itself: it shows up to five rows and scrolls past
        # that (Sebastian, 2026-08-11), so the charts and the report below
        # always keep their room. Everything else up here — buttons,
        # checkboxes, thresholds — stays outside any scroll area and is
        # always visible: a first cut that wrapped this whole block in its
        # own scroll frame hid the PDF buttons at medium window heights and
        # painted the trend headline over the list.
        top_v = v
        top_v.addWidget(intro)

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
               "came from — only add profiles from the SAME printer. A clear name "
               "in “Printer profile project name” on the “1. Create Chart” tab "
               "makes them easy "
               "to recognise; the report also warns you if the runs use different "
               "instruments or a chart is missing cube corners."),
            self, color=SPEC_GREEN))
        add_row.addStretch(1)
        top_v.addLayout(add_row)

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
        top_v.addWidget(self._profile_list)

        out_row = QHBoxLayout()
        # KNUT, 2026-09-11: *"A user should be allowed to print several report
        # types for a run, as the user may have several uses for different
        # reports … This also makes it logical that there is a Generate Report
        # button, so the user can choose to generate a report that is
        # selected."* The type is a VIEW of the same judged data, and this is
        # the button that keeps one.
        self._generate_btn = QPushButton(tr("Generate report"), self)
        self._generate_btn.setStyleSheet(_compact_btn)
        self._generate_btn.clicked.connect(self._on_generate_report)
        self._generate_btn.setEnabled(False)
        out_row.addWidget(self._generate_btn)
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
               "numbers) to a PDF and opens it. The trend graphs are included only "
               "when the report has two or more runs.\n\n"
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
        # the two report-option checkboxes join this row on the right
        # (Knut, beta.5: 'moved to the right of the buttons, to save a
        # bit of vertical space')
        out_row.addSpacing(18)

        self._all_runs_check = QCheckBox(tr("Show all measurement runs"), self)
        # Both option boxes remember the user's last choice (Sebastian,
        # 2026-08-10: "so I don't have to select it every time again") —
        # saved the moment they are toggled, like the Pass thresholds.
        self._all_runs_check.setChecked(
            str(settings.get("report_show_all_runs", "true")).lower() != "false")
        self._all_runs_check.toggled.connect(
            lambda on: (settings.set("report_show_all_runs",
                                     "true" if on else "false"),
                        self._refresh()))
        out_row.addWidget(self._all_runs_check)
        out_row.addWidget(TooltipButton(
            tr("Show all measurement runs"),
            tr("The report can look at one measurement, or at your whole "
               "history.\n\n"
               "With this ticked, every dated run in the list above is part "
               "of the report: the trend graphs, Report Scope, Report Results "
               "and the tables compare them side by side — and any run you "
               "have unticked in the list stays out.\n\n"
               "With it off, the report shows only the measurement it was "
               "opened on — one run, in full, with no comparison.\n\n"
               "The saved PDF always matches what you see here."),
            self, min_width=440, color=SPEC_GREEN))
        self._detail_check = QCheckBox(tr("Show detailed data for each run"), self)
        self._detail_check.setChecked(
            str(settings.get("report_show_details", "false")).lower() == "true")
        self._detail_check.toggled.connect(
            lambda on: (settings.set("report_show_details",
                                     "true" if on else "false"),
                        self._render()))
        out_row.addWidget(self._detail_check)
        out_row.addWidget(TooltipButton(
            tr("Show detailed data for each run"),
            tr("Adds the full breakdown for every run in the report, each on "
               "a page of its own: the colour-accuracy table with its "
               "verdict words against the run's limit set, paper white and "
               "darkest black, the eight cube corners, and the worst patches "
               "with their expected and measured colours side by side.\n\n"
               "Handy when you want to see WHY a run passed or failed, not "
               "just that it did: for example which patches pushed the "
               "average over its limit.\n\n"
               "It makes the report, and the saved PDF, considerably longer, "
               "which is why it starts unticked."),
            self, min_width=440, color=SPEC_GREEN))
        out_row.addStretch(1)
        top_v.addLayout(out_row)

        # #182 (Knut D8, D20): the two Pass-threshold spin boxes are gone. A
        # report is judged against the LIMIT SET bound to its profile run; the
        # row below names it, opens the limits table, and carries the one
        # deliberate act that may change a run's limits after its first
        # verification: "Unlock". Every connection is a bound method: a lambda
        # capturing `self` on a child widget's signal is the shape that
        # segfaulted the app (CLAUDE.md).
        from ui.widgets import NoScrollComboBox
        self._run_ctx = None          # workflow.run_compliance.RunContext | None
        self._limits = None           # RunLimits the window judges with
        #: Runs this window bound during this session. A run that is bound
        #: becomes locked the moment it has a history, and taking the control
        #: away in the same act that used it is what three rounds kept trying
        #: to fix by writing a flag to disk. This remembers it here instead, so
        #: nothing untrue is recorded about a lock nobody lifted.
        self._bound_here: "set[str]" = set()
        #: A type chosen for a measurement that is in NO run (CH-14): kept for
        #: the session, written nowhere, exactly as the limit set is.
        self._session_type = ""
        self._syncing_limits = False
        # #182 (D28, question 19): the KIND of document, chosen before the
        # numbers it is judged with. Two controls, one rule: D9 governs both,
        # because a run whose dated verifications produced different kinds of
        # report is no more comparable than one whose limits moved under it.
        type_row = QHBoxLayout()
        self._type_label = QLabel(tr("Report type:"), self)
        type_row.addWidget(self._type_label)
        self._type_combo = NoScrollComboBox(self)
        from PyQt6.QtWidgets import QComboBox
        self._type_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._type_combo.setMinimumWidth(260)
        self._type_combo.currentIndexChanged.connect(self._on_type_chosen)
        type_row.addWidget(self._type_combo)
        type_row.addWidget(TooltipButton(
            tr("Report type"),
            tr("Which kind of document this run's verifications produce. The "
               "measurement is the same either way; the type decides what is "
               "put in front of a reader, and how much of it.\n\n"
               "Like the limit set, the type belongs to the profile run, so "
               "every dated verification of the run produces the same kind of "
               "document and the dates can be compared. Another run in the "
               "project may use a different one.\n\n"
               "A type shown greyed is one ChromIQ cannot produce yet. The "
               "line under it says what is missing."),
            self, min_width=460, color=SPEC_GREEN))
        #: What the chosen type is for, or, on a type that cannot be produced,
        #: what is missing. It rides on the SAME row, elided, with the whole
        #: sentence as its tooltip: a word-wrapped label of its own is what
        #: pushed this window's bottom off an 800 px screen, twice, because a
        #: wrapped label's minimum height is computed before the window has
        #: been given its width.
        self._type_blurb = QLabel(self)
        self._type_blurb.setWordWrap(False)
        self._type_blurb.setStyleSheet("color: palette(mid); padding-left: 4px")
        self._type_blurb_full = ""
        type_row.addWidget(self._type_blurb, 1)
        top_v.addLayout(type_row)

        judged_row = QHBoxLayout()
        self._judged_label = QLabel(tr("Judged against:"), self)
        judged_row.addWidget(self._judged_label)
        self._set_combo = NoScrollComboBox(self)
        from PyQt6.QtWidgets import QComboBox
        self._set_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._set_combo.setMinimumWidth(220)
        self._set_combo.currentIndexChanged.connect(self._on_set_chosen)
        judged_row.addWidget(self._set_combo)
        self._limits_btn = QPushButton(tr("Show limits…"), self)
        self._limits_btn.setStyleSheet(_compact_btn)
        self._limits_btn.clicked.connect(self._on_open_limits)
        judged_row.addWidget(self._limits_btn)
        judged_row.addSpacing(10)
        self._unlock_check = QCheckBox(
            tr("Unlock this run's limits (recalculates its dated reports)"), self)
        self._unlock_check.toggled.connect(self._on_unlock_toggled)
        judged_row.addWidget(self._unlock_check)
        judged_row.addWidget(TooltipButton(
            tr("Judged against"),
            tr("Every row of the results is compared with one limit set: one "
               "column of the limits table, chosen once per profile run. The "
               "first verification you measure binds the run to the default "
               "set from Preferences and copies its numbers into the run, so "
               "every later dated verification of the run is judged the same "
               "way and your history stays comparable.\n\n"
               "Show limits… opens the whole table: every set side by side, "
               "and, when the measurement is in a project, this run's own copy "
               "in its first column.\n\n"
               "Unlock this run's limits: once a verification has been "
               "measured the run's numbers are fixed, on purpose. Ticking "
               "this is a deliberate decision to change them: every dated "
               "report of this run is then recalculated with the numbers you "
               "set, and the previous reports are kept in a reports/old folder "
               "first. It can be ticked only when Preferences → Reports allows "
               "editing after the first measurement.\n\n"
               "A measurement that is not in a ChromIQ project (an imported "
               "file) is judged with the default set for this session only; "
               "nothing is stored for it."),
            self, min_width=460, color=SPEC_GREEN))
        judged_row.addStretch(1)
        top_v.addLayout(judged_row)
        # The strip (Knut D25): shown only when the chart cannot supply a row
        # the set limits; hidden, not blank, when there is nothing to say.
        self._mismatch = QLabel(self)
        self._mismatch.setWordWrap(False)
        self._mismatch.setTextFormat(Qt.TextFormat.PlainText)
        self._mismatch_full = ""
        _mode = resolve_mode(settings.get("appearance", "auto"))
        if _mode == "dark":
            _strip = ("border: 1px solid #b08040; color: #f0b35a;"
                      " background: rgba(240,180,80,0.14);")
        elif _mode == "neutral":
            _strip = (f"border: 1px solid {neutral_styles.NM_BORDER_HI};"
                      f" color: {neutral_styles.NM_TEXT_MAIN};"
                      f" background: {neutral_styles.NM_BG_SURFACE};")
        else:
            _strip = ("border: 1px solid #c8922a; color: #8a5a00;"
                      " background: rgba(240,180,80,0.12);")
        self._mismatch.setStyleSheet(
            "QLabel { border-radius: 4px; padding: 6px 10px; " + _strip + " }")
        self._mismatch.setVisible(False)
        top_v.addWidget(self._mismatch)

        # Unlike-scaled metrics can't share one axis (Knut), so group them into
        # separate tabbed charts. Paper white (~L*100) and black (~L*10) are too
        # far apart to read a trend on one axis, so they get a chart each.
        self._trend_tabs = QTabWidget(self)
        # The "Trend over time" heading rides in the tab row's free corner
        # instead of a row of its own — that row's height is exactly what the
        # charts were missing on screens where every pixel counts.
        self._trend_label = QLabel(tr("Trend over time (this printer)"), self)
        self._trend_label.setStyleSheet(
            "font-weight:bold;padding:0 6px 2px 0")
        self._trend_label.setVisible(False)
        self._trend_tabs.setCornerWidget(self._trend_label,
                                         Qt.Corner.TopRightCorner)
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
        qss = neutral_controls_qss(SPEC_GREEN, popup=SPEC_GREEN)
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
        w = max(self.width(), 940)      # +20 px default width (Sebastian, 2026-08-13)
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

            # When even that is too tall for the screen, space is traded in
            # the order of what stays USEFUL when short: the report view
            # scrolls, so it yields first — the charts do not scroll, and a
            # squeezed chart stops being a graph (Sebastian, 2026-08-12), so
            # they yield last and keep 100 px until nothing else is left.
            def _over() -> int:
                layout.activate()
                return layout.minimumSize().height() - cap

            charts = (self._trend_de, self._trend_white,
                      self._trend_black, self._trend_corners)
            if _over() > 0:
                self._view.setMinimumHeight(max(150, 240 - _over()))
            if _over() > 0:
                for c in charts:
                    c.setMinimumHeight(max(100, 150 - _over()))
            if _over() > 0:
                self._view.setMinimumHeight(
                    max(120, self._view.minimumHeight() - _over()))
            if _over() > 0:
                for c in charts:
                    c.setMinimumHeight(
                        max(60, c.minimumHeight() - _over()))
            h = max(h, min(layout.minimumSize().height(), cap))
        self.resize(w, h)
        x = area.left() + max(0, (area.width() - w) // 2)
        y = area.top() + max(0, (area.height() - h) // 2)
        self.move(x, y)

    # ---- sources (one per profile) ----------------------------------------
    def _argyll_bin(self) -> str:
        """The Argyll path for the report's in/out-of-gamut test — empty when
        unset, which makes build_report skip the split rather than fail."""
        return str(self._settings.get("argyll_bin_path", "") or "")

    def _gather_runs(self, ti3: Path) -> "tuple[str, list]":
        """``(profile name, runs oldest-first)`` for the profile that owns *ti3*:
        every saved report across the profile's runs, or the freshly built one
        when nothing is saved yet (a stand-alone / i1Profiler .ti3)."""
        import json
        from workflow.measurement_report import (build_report,
                                                  list_project_reports)
        runs: list[dict] = []
        for p in list_project_reports(ti3.parent):
            try:
                rep = json.loads(read_text(p))
            except Exception:  # noqa: BLE001
                continue
            # Reports saved by an older ChromIQ carry an older schema whose
            # metric set predates the current one (no avg_all/max_all …), so the
            # window would show "no accuracy data" for them. Rebuild such a
            # report from its run's own .ti3 — same measurement, current metrics —
            # keeping the saved date so the trend timeline is unchanged (Knut).
            # ...AND A ROW THAT WAS NEVER COMPUTED IS STALE TOO, WHICH THE
            # SCHEMA NUMBER CANNOT SAY. Grey balance and the tone ramps were
            # added ADDITIVELY, deliberately without bumping the schema so that
            # no report on disk would be re-derived. The consequence nobody
            # traced: 4.2.0 already wrote schema 7 and had no grey balance in
            # its builder at all, so every report saved by 4.2.0 and the first
            # two betas fails this test, is never rebuilt, and shows N-A on
            # both grey rows for ever. Surveyed on one real disk: 58 saved
            # reports, none with a grey block, 33 of them already at schema 7.
            #
            # Worse than missing: the reason printed beside the N-A says the
            # measurement file could not be read again, which is untrue. It was
            # never asked for, and in the case measured the number it was
            # hiding, 3.702, was sitting in the same folder.
            #
            # The rebuild below already carries the saved verdict across
            # untouched, so this computes rows that were never computed and
            # re-grades nothing. Section 6 of the design record is revised in
            # place, and it was a draft confirmed by nobody.
            stale = _report_needs_rebuilding(rep)
            if stale:
                run_ti3 = p.parent.parent / ti3.name
                if run_ti3.is_file():
                    try:
                        created = rep.get("created")
                        # The verdict this report was SAVED with is a RECORD,
                        # not a derived figure — a rebuild recomputes today's
                        # statistics from the same measurement, and must carry
                        # the old judgement across untouched or the rebuild
                        # becomes the very re-grading #182 is about.
                        kept = {k: rep[k] for k in
                                ("pass_thresholds", "verdict", "compliance")
                                if k in rep}
                        rep = build_report(run_ti3, argyll_bin=self._argyll_bin())
                        if created:
                            rep["created"] = created
                        rep.update(kept)
                    except Exception:  # noqa: BLE001
                        pass
            # Session-only: where this run lives on disk. Saved reports carry
            # only the measurement's NAME, so the four-tier PDF location
            # (Knut's "Where are my files?" card) needs the origin recorded
            # here — reports/report_*.json sits one level under it.
            rep["_origin_dir"] = str(p.parent.parent)
            runs.append(rep)
        # #130/#133: a dated verification trends across ALL of this run's
        # dates. A date measured with "Save measurement report" switched off
        # has no saved report — build its report fresh here, so the history is
        # complete either way (Sebastian, 2026-08-10: three measured dates
        # showed as "1 run" and the trend stayed empty).
        from core.file_manager import VERIFICATIONS_DIRNAME
        vroot = ti3.parent.parent
        if vroot.name == VERIFICATIONS_DIRNAME:
            # A saved report's "ti3" is the measurement's bare FILE NAME
            # (build_report keeps no path), so its parent is "" and nothing
            # was ever counted as covered: every date that HAD a saved report
            # was rebuilt a second time and listed twice (found on screen,
            # 2026-09-08, Demo-Verify-History: 10 rows for 5 dates). The
            # dated folder is the origin recorded two lines above.
            covered = {Path(r["_origin_dir"]).name
                       for r in runs if r.get("_origin_dir")}
            for d in sorted(p for p in vroot.iterdir() if p.is_dir()):
                if d.name in covered or d.name == "old":
                    continue
                cand = d / ti3.name
                if cand.is_file():
                    try:
                        rep = build_report(cand, argyll_bin=self._argyll_bin())
                        rep["_origin_dir"] = str(d)
                        rep["_fresh"] = True       # never saved: graded live
                        runs.append(rep)
                    except Exception:  # noqa: BLE001 — one bad date must
                        continue       # not empty the whole history
        if not runs:
            runs = [build_report(ti3, argyll_bin=self._argyll_bin())]
            runs[0]["_origin_dir"] = str(ti3.parent)
        runs.sort(key=lambda r: str(r.get("created") or ""))
        from workflow.measurement_report import annotate_raw_drift
        annotate_raw_drift(runs)
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
            runs = self._sources[0]["runs"]
            # The window was opened ON this measurement — with "Show all
            # measurement runs" off it must show exactly that date, as its
            # own tooltip promises, not silently the history's newest
            # (found by Knut's report demo package, 2026-08-10).
            mine = [r for r in runs
                    if str(r.get("_origin_dir", "")) == str(ti3.parent)]
            self._report = (mine[-1] if mine else runs[-1])
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
        if r.get("reference_source") in ("colorimetric",
                                         "colorimetric-missing"):
            label = tr("gamut check — profile applied at build")
        elif colour == "through-profile" and pr.get("route") == "external-cm":
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
        """Size the list to its content, capped at ``_LIST_VISIBLE_ROWS``
        visible rows — past the cap the list scrolls internally, and that is
        the one scrollbar above the chart tabs (Knut's beta.5 point, settled
        with Sebastian 2026-08-11: "limited to 5 lines … then scroll after
        the 5 lines"). ``compact`` shrinks it to two rows when the window's
        own minimum would otherwise not fit the screen."""
        n = len(self._list_rows)
        frame = 2 * self._profile_list.frameWidth() + 4
        rows = 2 if compact else min(max(n, 1), self._LIST_VISIBLE_ROWS)
        # Sum the real row heights — the checkable run rows are a few px
        # taller than the profile header row, so a rows×row_h estimate either
        # clipped the last visible row in half or let a sliver of the next
        # one peek in.
        heights = [self._profile_list.sizeHintForRow(i)
                   for i in range(min(n, rows))]
        if not heights or min(heights) <= 0:
            heights = [self._profile_list.fontMetrics().height() + 8] * rows
        h = sum(heights) + frame
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
        # Owned by the dialog, so the converted copy goes when the dialog does.
        # It used to be a bare mkdtemp with no owner and no cleanup — the
        # dialog has no closeEvent/reject at all — leaving ~350 KB per import.
        if not hasattr(self, "_converted_tmpdirs"):
            self._converted_tmpdirs = []
        holder = tempfile.TemporaryDirectory(prefix="chromiq_report_")
        self._converted_tmpdirs.append(holder)
        out_dir = Path(holder.name)
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
        self._forget_limits()
        self._sync_limit_controls()
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
        from ui.theme import has_dark_ground, resolve_mode
        from workflow.measurement_report import report_trend
        # WHICH KIND OF GROUND, not "is it not light". `!= "light"` had room for
        # two answers, so the light-grey appearance was told the charts sit on a
        # dark ground and got pale axes, pale labels and a white grid — on a
        # light panel. The trend tabs only appear once a report with more than
        # one run is open, so nothing had drawn them. (The five metric LINE
        # colours are untouched: they are what tells one series from another,
        # and the same chart is drawn into the PDF.)
        dark = has_dark_ground(
            resolve_mode(self._settings.get("appearance", "auto")))
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
        """Where a PDF is saved — the ``reports`` folder at the tightest place
        that still contains everything the report covers (#130 Hole 5 + the
        "Where are my files?" card, Knut — reconfirmed 2026-08-10). The four
        homes, from the least-common-ancestor of the covered measurements:

        * a single dated verification     → ``…/verifications/<date>/reports``
        * several checks of one run       → ``…/runs/<id>/verifications/reports``
        * a profiling run                 → ``…/runs/<id>/reports``
        * several runs / whole profile    → ``<project>/reports`` (next to ``runs/``)

        The covered set is exactly what the report shows — the same list as the
        window and the PDF, runs the user unticked excluded — so the location
        follows the SELECTED data, not what happens to be loaded. For a browsed
        measurement outside any ChromIQ project the report goes in a ``reports``
        folder next to the file itself."""
        from core.file_manager import reports_subdir
        dirs = [Path(r["_origin_dir"])
                for r in self._runs_for_report() if r.get("_origin_dir")]
        lca = self._lca_dir(dirs) if dirs else self._anchor_dir()
        # The common ancestor being the ``runs`` container itself means the
        # report spans multiple runs → it belongs to the whole profile.
        if lca.name == "runs":
            return reports_subdir(lca.parent)
        return reports_subdir(lca)

    def _on_generate_report(self) -> None:
        """Save a report of the type now chosen, for the run now shown.

        **Knut, 2026-09-11.** A run may hold reports of several types: *"the
        user may have several uses for different reports."* Pressing this keeps
        one, and the line beside the pulldown then names it among the types
        this run has.

        It does NOT re-judge anything. The verdict is stamped with the run's
        own limits, exactly as a measurement stamps one, so two reports of two
        types saved from one measurement carry the same words. That is the
        whole point of the type being a view: nothing about a verdict changes
        when you switch.
        """
        ctx = self._run_ctx
        reports = self._runs_for_report()
        if ctx is None or not reports:
            return
        from workflow.measurement_report import (save_report, stamp_report_type,
                                                 stamp_verdict)
        lim = self._window_limits()
        saved, failed = [], []
        for r in reports:
            origin = r.get("_origin_dir")
            if not origin:
                continue
            try:
                rep = dict(r)
                # The window's own bookkeeping keys are not part of a report.
                for k in [k for k in rep if k.startswith("_")]:
                    rep.pop(k, None)
                stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                              set_label=lim.label_en, edited=lim.edited)
                stamp_report_type(rep, ctx.run)
                saved.append(save_report(rep, Path(origin)))
            except Exception as exc:             # noqa: BLE001
                log.warning("could not generate a report in %s: %s", origin, exc)
                failed.append(str(origin))
        self._say_generated(saved, failed)
        self._forget_limits()
        self._refresh()

    def _say_generated(self, saved: list, failed: list) -> None:
        """SUCCESS IS QUIET; A FAILURE IS NOT.

        A button that writes files and says nothing is a button a user presses
        twice, so this began as a message box on every press. Driven on screen,
        keeping three types of one measurement then meant three boxes to
        dismiss in a row, which is exactly the flow Knut asked for: *"the user
        may have several uses for different reports."*

        The feedback is already on the page. The line beside the pulldown
        changes from "No report has been generated for this run yet" to a list
        naming what the run now has, in the same instant, and that is the thing
        he asked the window to show. A box that repeats it is a box in the way.

        A failure still speaks, because nothing else on the page would say so.
        """
        from ui.warning_sign import warn
        from workflow.measurement_report import report_type_name
        name = tr(report_type_name(self._report_type_now()))
        if saved and not failed:
            log.info("generated %d report(s) of type %s", len(saved), name)
            return
        if saved and failed:
            warn(self, tr("Report generated"), tr(
                "Saved {count} of {total}. The rest could not be written; the "
                "log says why.").format(count=len(saved),
                                        total=len(saved) + len(failed)))
        elif failed:
            warn(self, tr("Report not generated"), tr(
                "Nothing could be written. The log says why."))

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
                # Render at 3× and display at the same 600px layout width: a
                # plain grab() gave a ~96-dpi raster that printed visibly
                # blurry next to the vector text (Sebastian, 2026-08-10).
                from PyQt6.QtGui import QImage
                scale = 3
                img = QImage(640 * scale, 176 * scale,
                             QImage.Format.Format_ARGB32_Premultiplied)
                img.fill(0xFFFFFFFF)
                ip = QPainter(img)
                ip.scale(scale, scale)
                tmp.render(ip)
                ip.end()
                url = QUrl(f"chart://{i}")
                doc.addResource(QTextDocument.ResourceType.ImageResource, url, img)
                charts_html += (
                    "<div style='font-size:16px;font-weight:bold;"
                    "margin-top:4px'>" + html.escape(title) + "</div>"
                    f"<img src='chart://{i}' width='600'>" + _gap())
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
            # CLIP THE BODY BAND — the same line `ui.pdf_layout.render_paged`
            # carries, and the report's own loop never got. `PaintContext.clip`
            # tells the layout which slice to draw; it does NOT stop an element
            # from painting outside it. A one-cell panel table straddling a
            # page boundary drew its whole grey background on the second page,
            # over the wordmark and the scope strip, with a line of its text
            # on top of them (seen 2026-09-10 the moment the "How to read this
            # report" panel was allowed to flow instead of being pushed off
            # page 2). It also let the panel run behind the page number.
            painter.setClipRect(QRectF(0.0, header_h, page_w, body_h))
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
        """The (average, maximum) ΔE00 pair the trend chart draws as guide
        lines: the all-patch rows of the limit set this window judges with."""
        from workflow.compliance_sets import legacy_pair
        lim = self._window_limits()
        return legacy_pair(lim.limits if lim is not None else {})

    # ---- #182: which limit set, whose run, and the lock ----------------------
    #
    # The report used to judge against two GLOBAL numbers, re-read from the
    # spin boxes at display time; a saved report stored neither them nor its
    # verdict, and nudging a spin box re-graded every historical report. Now
    # (Knut, D9/D20/D23/D33):
    #
    #   * a report saved with a verdict shows THAT verdict, and nothing in this
    #     window moves it, except the one deliberate act below;
    #   * a report without one (saved by an older ChromIQ, or built just now
    #     from a date that was never saved) is graded live against ITS RUN's
    #     limit set, and says so;
    #   * the set belongs to the profile run; changing it, or its numbers, is
    #     "Unlock": every dated report of that run is archived once and
    #     recalculated once (CH-29), never on every keystroke.

    def _overrides(self) -> dict:
        from core.settings import compliance_overrides_of
        return compliance_overrides_of(self._settings)

    def _default_set_id(self) -> str:
        return str(self._settings.get("compliance_default_set", "chromiq_default")
                   or "chromiq_default")

    def _context_run(self):
        """The RunContext of the FIRST source's original file, or None for a
        file that is not in a run (CH-14: a run context exists only for
        runs/runN/<file> and runs/runN/verifications/<date>/<file>)."""
        from workflow.run_compliance import run_context_for
        if not self._sources:
            return run_context_for(self._ti3) if self._ti3 else None
        return run_context_for(self._sources[0]["origin"])

    def _distinct_run_dirs(self) -> "set[str]":
        """How many different PROFILE RUNS the window holds (CH-13)."""
        from workflow.run_compliance import run_context_for
        dirs: set = set()
        for src in self._sources:
            ctx = run_context_for(src["origin"])
            dirs.add(str(ctx.run.dir) if ctx else f"external:{src['origin']}")
        return dirs

    def _window_limits(self):
        """The RunLimits the window's own controls act on (the first run's)."""
        if self._limits is None:
            from workflow.run_compliance import run_limits
            ctx = self._context_run()
            self._run_ctx = ctx
            self._limits = run_limits(ctx.run if ctx else None, self._overrides(),
                                      self._default_set_id())
        return self._limits

    def _limits_for(self, r: dict):
        """The RunLimits a REPORT is judged with live: its own run's, or the
        window's when it is not in a run (an imported file)."""
        from workflow.run_compliance import run_context_for, run_limits
        origin = r.get("_origin_dir")
        ti3 = r.get("ti3")
        if origin and ti3:
            ctx = run_context_for(Path(origin) / str(ti3))
            if ctx is not None:
                cache = getattr(self, "_limits_cache", None)
                if cache is None:
                    cache = self._limits_cache = {}
                key = str(ctx.run.dir)
                if key not in cache:
                    cache[key] = run_limits(ctx.run, self._overrides(),
                                            self._default_set_id())
                return cache[key]
        return self._window_limits()

    def _forget_limits(self) -> None:
        """Drop what was read from disk so the next look re-reads it. A
        session-only choice for a file that is in no run (CH-14) is kept: there
        is nothing on disk to re-read it from."""
        self._limits_cache = {}
        # …AND THE TYPES, for the same reason and at the same moment. A cache
        # that outlives the read it was taken for is a baseline taken later
        # than the write that earned it, which is a fault shape this window has
        # already been bitten by four times.
        self._types_cache = None
        ctx = self._context_run()
        self._run_ctx = ctx
        if ctx is not None or self._limits is None or self._limits.bound:
            self._limits = None

    def _sync_limit_controls(self) -> None:
        """Fill the pulldown, set the lock, name the run, fill the strip."""
        if getattr(self, "_set_combo", None) is None:
            return
        from workflow.compliance_sets import SET_BY_ID, selectable_set_ids
        # NOT `is_locked`: `_locked_here` is the one answer this window gives
        # about a run, and importing the raw predicate here is how a line came
        # to use it by accident. Two rounds fixed that fault, in two doors.
        from workflow.run_compliance import (has_measured_verification,
                                             may_unlock)
        lim = self._window_limits()
        ctx = self._run_ctx
        run = ctx.run if ctx else None
        # WHAT THE USER IS ABOUT TO BE SHOWN, stamped here because here is the
        # last moment this window and the run agree. A guard that stamps it
        # when a control is CLICKED has already swallowed everything that
        # happened while the user was reading the screen, which is the whole
        # window a second writer has to work in. A challenge round drove
        # exactly that: rebind the run, then click, and the rebind was inside
        # the "before" the guard compared against.
        self._run_state_at_sync = self._run_state_now(run) if run else ()
        self._syncing_limits = True
        try:
            self._set_combo.clear()
            ids = selectable_set_ids(self._overrides())
            if lim.set_id not in ids:
                self._set_combo.addItem(lim.set_label, lim.set_id)
            for sid in ids:
                self._set_combo.addItem(SET_BY_ID[sid].label and
                                        tr(SET_BY_ID[sid].label), sid)
                self._set_combo.setItemData(
                    self._set_combo.count() - 1, tr(SET_BY_ID[sid].blurb),
                    Qt.ItemDataRole.ToolTipRole)
            idx = self._set_combo.findData(lim.set_id)
            self._set_combo.setCurrentIndex(max(0, idx))
            several = len(self._distinct_run_dirs()) > 1
            # A run THIS WINDOW bound a moment ago keeps its controls: binding
            # is what locks a run with a history, so without this the act of
            # choosing a limit set greys the pulldown that chose it.
            # Session-scoped on purpose, and the superseded `is_locked(run)`
            # that used to sit on the line above is gone rather than left
            # beside it, because a dead assignment holding the OTHER answer is
            # how the same function came to disagree with itself.
            locked = self._locked_here(run)
            self._unlock_check.blockSignals(True)
            self._unlock_check.setChecked(bool(lim.unlocked))
            self._unlock_check.blockSignals(False)
            allow = bool(self._settings.get(
                "compliance_allow_edit_after_measurement", False))
            self._unlock_check.setEnabled(
                run is not None and not several
                and ((may_unlock(run, allow) and has_measured_verification(run))
                     or bool(lim.unlocked)))     # F5: re-locking is always allowed
            # THE FOURTH CONTROL, AND IT WAS SAYING THE OPPOSITE OF THE OTHER
            # THREE. An unticked "Unlock this run's limits" MEANS "this run is
            # locked", and greyed means "and you cannot change that". On a run
            # with one dated verification, or on one that was never bound, the
            # pulldown is live, the button says "Edit limits…" and the column
            # is editable, while this box sat dim and unticked beside them
            # saying the run was locked. A challenge round photographed the
            # four together.
            #
            # There is nothing to unlock on such a run, so the honest thing is
            # not to offer the control at all. It comes back the moment the run
            # has the history that a lock would apply to, which is also the
            # moment its wording becomes true.
            # SHOWN ONLY WHERE IT SAYS SOMETHING TRUE.
            # It was widened to every bound run so that un-ticking at one dated
            # verification could not make it vanish. That put it back to
            # contradicting the other three controls in the commonest state
            # there is: with the shipped preference off, a run one measurement
            # old is bound and not unlocked, so the box sat VISIBLE, UNTICKED
            # AND GREYED, which reads "this run is locked and you cannot change
            # that", beside a live pulldown, an "Edit limits…" button and a
            # column of live spin boxes. That is the state every run is in after
            # its first verification.
            #
            # The vanishing it was meant to fix cannot happen any more: the flag
            # is no longer set on a run the lock does not reach, so there is no
            # ticked box at one date to un-tick.
            self._unlock_check.setVisible(
                run is not None and not several
                and (locked or bool(lim.unlocked)))
            # F6: the button's text changes, so its width must follow it
            self._limits_btn.setMinimumWidth(self._limits_btn.sizeHint().width())
            self._set_combo.setEnabled(not several and (run is None or not locked))
            self._limits_btn.setText(tr("Edit limits…") if (run is not None
                                                            and not locked)
                                     else tr("Show limits…"))
            self._limits_btn.setEnabled(not several)
            if several:
                self._judged_label.setText(tr("Judged against:"))
                tip = tr("Several measurement runs are loaded. Open the report "
                         "on one run to change its limits.")
            elif run is not None:
                self._judged_label.setText(
                    tr("Judged against ({run}):").format(run=run.dir.name))
                tip = ""
            else:
                self._judged_label.setText(tr("Judged against:"))
                tip = tr("This measurement is not in a ChromIQ project, so the "
                         "choice is not stored anywhere.")
            for w in (self._set_combo, self._unlock_check, self._limits_btn):
                w.setToolTip(tip)
            self._sync_type_combo(run, several)
            self._set_strip(self._mismatch_text())
        finally:
            self._syncing_limits = False

    # ------------------------------------------------------------------
    # The report TYPE (#182 D28)
    # ------------------------------------------------------------------
    def _report_type_now(self) -> str:
        """Which kind of document this window is producing.

        The RUN is the source of truth, because that is what D9 says: later
        dated verifications of a run follow the run's type. A measurement in no
        project has no run to ask, so the type it was last saved as is used,
        and failing that today's report.

        AND WHEN THE LOADED RUNS DISAGREE, NOBODY'S CHOICE WINS. This window
        asked ITS OWN run, which is the first one loaded, and applied that
        answer to every column. Measured: run 1 set to "Printing record" and
        run 2 left on "Full colour check", both loaded, and run 2's column came
        out ungraded, every verdict withheld, because run 1 had chosen that.
        Knut's own rule is the opposite: *"Another run in the project may use
        other verification run charts with other selected report type and
        thresholds."*

        A window produces ONE document, so the columns cannot each have their
        own type; the answer is to fall back to the one type that withholds
        nothing and drops no row, which is today's report, and to say so under
        the pulldown. That is also the only answer that cannot lose a verdict a
        run recorded.
        """
        from workflow.measurement_report import REPORT_TYPE_DEFAULT, report_type
        from workflow.run_compliance import run_report_type
        types = self._types_of_loaded_runs()
        if len(types) > 1:
            return REPORT_TYPE_DEFAULT
        ctx = self._run_ctx
        if ctx is not None:
            return run_report_type(ctx.run)
        if self._session_type:
            return self._session_type
        reports = self._runs_for_report()
        return report_type(reports[0]) if reports else REPORT_TYPE_DEFAULT

    def _types_of_loaded_runs(self) -> "set[str]":
        """The distinct report types of every RUN this window holds.

        Cached for one render, because it reads a `meta.json` per run and
        `_report_type_now` is asked several times per column.
        """
        cached = getattr(self, "_types_cache", None)
        if cached is not None:
            return cached
        from workflow.measurement_report import report_type
        from workflow.run_compliance import run_context_for, run_report_type
        out: "set[str]" = set()
        for src in getattr(self, "_sources", []):
            ctx = run_context_for(src.get("origin"))
            if ctx is not None:
                out.add(run_report_type(ctx.run))
                continue
            # A MEASUREMENT IN NO RUN HAS A TYPE TOO, and this loop could not
            # see it. Driven: a run on the Printing record beside a loose file
            # whose own saved report says Full colour check, and the window saw
            # no disagreement at all, so T4 was applied to both. Opened alone
            # that file reads FAIL; in company it read INFO, every verdict
            # withheld by a choice made on a different run. Nothing is written,
            # but it is exactly the state the fallback exists to prevent,
            # reached through the door the guard did not cover.
            for rep in (src.get("runs") or []):
                if isinstance(rep, dict):
                    out.add(report_type(rep))
        self._types_cache = out
        return out

    def _ungraded_by_type(self) -> bool:
        """Whether the CHOSEN TYPE says nothing here is judged.

        T4, "Printing record (not graded)", is a document about what was
        printed and measured. Its numbers are the measured ones, untouched;
        what it withholds is the judgement. Knut's 12b already allows INFO for
        a sheet that was not measured to check a profile, on condition the
        report explains it, and this is the same word with a different reason:
        the 12b sentence says the sheet "was measured to build a profile", and
        on a verification measurement a user deliberately chose to record, that
        would be false.

        NOTHING IS WRITTEN. A saved report keeps its recorded verdicts; this
        only decides what is drawn from them, so switching back to Full colour
        check brings the same words back.
        """
        from workflow.measurement_report import REPORT_TYPE_RECORD
        return self._report_type_now() == REPORT_TYPE_RECORD

    def _sync_type_combo(self, run, several: bool) -> None:
        """Fill the type pulldown and put the line under it.

        Called from inside `_sync_limit_controls`, under the same
        `_syncing_limits` flag and after the same `_run_state_at_sync` stamp,
        so the type control's guard compares against the state this window
        actually DREW. A separate stamp of its own is how a baseline comes to
        be taken later than the write it is meant to catch.
        """
        if getattr(self, "_type_combo", None) is None:
            return
        from workflow.measurement_report import (REPORT_TYPE_MENU,
                                                 REPORT_TYPE_MENU_HEADING,
                                                 REPORT_TYPE_MENU_SPLIT)
        current = self._report_type_now()
        self._type_combo.clear()
        model = self._type_combo.model()
        for tid, name, blurb, built in REPORT_TYPE_MENU:
            if tid == REPORT_TYPE_MENU_SPLIT:
                # A HEADING THAT LOOKS LIKE A REFUSED CHOICE IS NOT A HEADING.
                # Photographed on screen: greyed and unadorned, it sat in the
                # list reading as a seventh type nobody may pick, between six
                # that mostly are greyed too. A rule above it and a bold italic
                # face say what it is, and go on saying it once the two types
                # below become selectable.
                self._type_combo.insertSeparator(self._type_combo.count())
                self._type_combo.addItem(tr(REPORT_TYPE_MENU_HEADING), "")
                i = self._type_combo.count() - 1
                self._disable_item(model, i)
                item = model.item(i) if hasattr(model, "item") else None
                if item is not None:
                    f = item.font()
                    f.setBold(True)
                    f.setItalic(True)
                    item.setFont(f)
            self._type_combo.addItem(tr(name), tid)
            i = self._type_combo.count() - 1
            self._type_combo.setItemData(
                i, tr(blurb) if built else self._not_built_line(tid),
                Qt.ItemDataRole.ToolTipRole)
            if not built:
                self._disable_item(model, i)
        idx = self._type_combo.findData(current)
        self._type_combo.setCurrentIndex(max(0, idx))
        self._type_combo.setEnabled(not several)
        self._type_label.setText(
            tr("Report type ({run}):").format(run=run.dir.name)
            if run is not None and not several else tr("Report type:"))
        # …and when several runs are loaded that sentence replaces it, below.
        self._type_combo.setToolTip("")
        if several:
            self._type_combo.setToolTip(
                tr("Several measurement runs are loaded. Open the report on "
                   "one run to change its type."))
        # WHEN THEY DISAGREE, SAY SO WHERE THE PULLDOWN IS. A greyed control
        # over a value that is nobody's choice explains nothing, and this is
        # the one state where the line beside it has something more useful to
        # say than what the type is for.
        if len(self._types_of_loaded_runs()) > 1:
            self._set_type_blurb(tr(
                "The runs loaded here were set to different report types, so "
                "this report is shown as Full colour check, which withholds "
                "nothing. Open the report on one run to use that run's type."))
        else:
            # WHICH TYPES EXIST COMES FIRST, and it used to come second.
            # Photographed on screen: with both on one elided line, the half
            # that got cut was "Already generated for this run: …", which is
            # precisely what Knut asked the window to show. What a type is FOR
            # has another home, the pulldown's own entries and the help button
            # beside it; what a run already holds has none.
            blurb = self._type_blurb_for(current)
            already = self._generated_types_line(run)
            self._set_type_blurb(f"{already}  ·  {blurb}" if already else blurb)
            self._type_combo.setToolTip(blurb)
        # The button writes a report for the run the window is on. With no run,
        # or with several loaded, there is no single place for it to go.
        self._generate_btn.setEnabled(
            run is not None and not several and bool(self._runs_for_report()))
        # A ONE-PAGE SUMMARY IS ABOUT ONE SHEET, so the tick that widens every
        # other report to the whole history is disabled rather than left to do
        # nothing visible. See `_one_measurement` for what it was doing before.
        from workflow.measurement_report import REPORT_TYPE_SUMMARY
        if getattr(self, "_all_runs_check", None) is not None:
            one_page = current == REPORT_TYPE_SUMMARY
            self._all_runs_check.setEnabled(not one_page)
            self._all_runs_check.setToolTip(tr(
                "The one-page colour summary is about the single measurement "
                "you are looking at, so it does not widen to the whole "
                "history.") if one_page else "")

    def _generated_types_line(self, run) -> str:
        """Which report types this run has already produced, or "".

        **Knut, 2026-09-11:** *"The Report window must thus show which type of
        reports have been generated."* Counted from the files on disk, never
        from anything this window remembers: a report is generated by a
        measurement no window was open for.
        """
        if run is None:
            return ""
        from workflow.measurement_report import (generated_report_types,
                                                 report_type_name)
        counts = generated_report_types(run)
        if not counts:
            return tr("No report has been generated for this run yet.")
        names = ", ".join(
            tr("{type} ({count})").format(type=tr(report_type_name(tid)),
                                          count=n)
            for tid, n in sorted(counts.items()))
        return tr("Already generated for this run: {names}").format(names=names)

    def _set_type_blurb(self, full: str) -> None:
        """One line, elided to the room it has; the whole sentence as the
        tooltip. Same rule as the mismatch strip below it, for the same
        reason."""
        from PyQt6.QtGui import QFontMetrics
        self._type_blurb_full = full or ""
        fm = QFontMetrics(self._type_blurb.font())
        room = max(120, self.width() - self._type_blurb.x() - 40)
        self._type_blurb.setText(
            fm.elidedText(self._type_blurb_full, Qt.TextElideMode.ElideRight, room))
        self._type_blurb.setToolTip(self._type_blurb_full)

    @staticmethod
    def _disable_item(model, row: int) -> None:
        """Grey a pulldown entry without removing it. A type ChromIQ cannot
        produce is SHOWN and refused, per Knut 2026-09-09, because hiding it
        says nothing about why it is not there."""
        item = model.item(row) if hasattr(model, "item") else None
        if item is not None:
            item.setEnabled(False)

    @staticmethod
    def _not_built_line(type_id: str) -> str:
        """Why a type cannot be chosen yet. One sentence, and it names the
        reason rather than the word "unavailable"."""
        from workflow.measurement_report import REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8
        if type_id in (REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8):
            return tr("Not available yet: the figures this report judges "
                      "against are published in a standard ChromIQ may not "
                      "include.")
        return tr("Not available yet: this report is still being built.")

    def _type_blurb_for(self, type_id: str) -> str:
        from workflow.measurement_report import REPORT_TYPE_MENU
        for tid, _name, blurb, built in REPORT_TYPE_MENU:
            if tid == type_id:
                return tr(blurb) if built else self._not_built_line(tid)
        return ""

    def _on_type_chosen(self, index: int) -> None:
        """Store the chosen type on the run, or keep it for the session.

        NOTHING IS RECALCULATED HERE, and that is the difference from the set
        pulldown beside it. A limit set decides what a measurement is judged
        against, so changing it moves verdicts already on disk and every dated
        report has to be archived and rebuilt. A type decides which document is
        produced from numbers that do not move. No verdict, no measurement and
        no saved figure changes, so there is nothing to archive and no question
        to ask.

        The run can still stop being the run this window drew, though, and that
        is checked: a second window changing the type, or a measurement
        arriving, is refused here exactly as it is at the set pulldown.
        """
        if self._syncing_limits or index < 0:
            return
        from workflow.measurement_report import report_type_is_built
        type_id = self._type_combo.itemData(index)
        current = self._report_type_now()
        if not type_id or type_id == current:
            return
        if not report_type_is_built(type_id):
            # Belt and braces: the entry is greyed, and a keyboard or a style
            # that ignores the flag must not be able to store it anyway. A
            # guarded write behind an unguarded control is the shape that came
            # back in three separate rounds.
            self._sync_type_combo_to(current)
            return
        ctx = self._run_ctx
        if ctx is None:
            # Not in a run: a session-only choice, nothing stored (CH-14).
            self._session_type = type_id
            self._refresh()
            return
        if self._run_state_now(ctx.run) != self._run_state_at_sync:
            self._sync_type_combo_to(current)
            self._say_run_moved_while_asking(ctx.run)
            self._forget_limits()
            self._refresh()
            return
        from workflow.run_compliance import set_run_report_type
        try:
            set_run_report_type(ctx.run, type_id)
        except (OSError, ValueError) as exc:
            log.warning("could not store the report type on %s: %s",
                        ctx.run.dir, exc)
            self._sync_type_combo_to(current)
            return
        self._forget_limits()
        self._refresh()

    def _sync_type_combo_to(self, type_id: str) -> None:
        """Put the pulldown back on *type_id* without re-entering the handler."""
        combo = getattr(self, "_type_combo", None)
        if combo is None:
            return
        i = combo.findData(type_id)
        if i < 0:
            return
        combo.blockSignals(True)
        combo.setCurrentIndex(i)
        combo.blockSignals(False)
        self._set_type_blurb(self._type_blurb_for(type_id))

    def _set_strip(self, full: str) -> None:
        """One line on screen, elided to the window; the whole message as the
        strip's tooltip and, always, in the report text (D25). A multi-line
        strip pushed the window past an 800 px screen."""
        self._mismatch_full = full or ""
        if not full:
            self._mismatch.setVisible(False)
            self._mismatch.setToolTip("")
            return
        lines = full.splitlines()
        first = lines[0]
        # the rows come first: they are what the user acts on (review F8)
        rows = [l.strip().lstrip("•").strip() for l in lines[1:] if l.strip().startswith("•")]
        # the row NAMES only (the reasons and what to add are the tooltip and
        # the report text), so three rows still fit two lines (review F8)
        names = [r.split(":")[0].strip() for r in rows]
        one = (first + ": " + "; ".join(names) + ". "
               + tr("Point here for the reasons and what to add to the chart.")) if rows else first
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QFontMetrics
        fm = QFontMetrics(self._mismatch.font())
        width = max(200, self.width() - 60)
        # two wrapped lines when they suffice; one elided line otherwise, so
        # the window still fits an 800 px screen
        needed = fm.boundingRect(QRect(0, 0, width - 20, 10_000),
                                 int(Qt.TextFlag.TextWordWrap), one).height()
        if needed <= 2 * fm.lineSpacing() + 2:
            self._mismatch.setWordWrap(True)
            self._mismatch.setText(one)
        else:
            self._mismatch.setWordWrap(False)
            self._mismatch.setText(fm.elidedText(one, Qt.TextElideMode.ElideRight, width))
        self._mismatch.setToolTip(full)
        self._mismatch.setVisible(True)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if getattr(self, "_mismatch_full", ""):
            self._set_strip(self._mismatch_full)
        if getattr(self, "_type_blurb_full", ""):
            self._set_type_blurb(self._type_blurb_full)

    # -- reasons a row was not computed, as sentences --------------------------
    def _reason_sentence(self, code: "str | None", r: "dict | None" = None) -> str:
        r = r or {}
        gb = r.get("grey_balance") or {}
        texts = {
            "no_greys": tr("the chart has no grey patches (R = G = B)"),
            "too_few_steps": tr("the chart has {k} grey steps, at least 8 are "
                                "needed from white to black").format(
                                    k=gb.get("levels", 0)),
            "no_white": tr("the grey ramp does not reach white"),
            "no_black": tr("the grey ramp does not reach black"),
            "no_reference": tr("there is no reference value for these patches"),
            "needs_reference_file": tr("this row needs a reference file for the "
                                       "printing condition; the chart's design "
                                       "has no aim for it"),
            "no_ramp": tr("the chart has no tone ramp with at least three steps "
                          "between 30 % and 70 %"),
            "small_sample": tr("the chart has {n} patches; at least 20 are needed "
                               "to split off the worst 5 %").format(
                                   n=r.get("patches", "?")),
            "printing_unrecorded": tr("how this sheet was printed is not "
                                      "recorded, so this value is shown for "
                                      "information only"),
            "no_corners": tr("the chart has no patch at the colour corners this "
                             "row needs"),
            "not_computed": tr("this value was not computed for this report; "
                               "the measurement file could not be read again"),
        }
        return texts.get(code or "", "")

    def _measured_not_graded(self, r: dict) -> "list[tuple[str, str]]":
        """``[(row label, why)]`` for rows that HAVE a number nobody graded.

        A DIFFERENT LIST FROM `_not_computed`, AND IT HAS TO BE. These rows
        were added to that one for a round, and that note is headed "Not
        computed on this chart" and ends "add the missing patches to the chart
        in Create Chart to have it checked" — so a grey row carrying 1.341, on
        a chart with a nine-step ramp, was called not computed and its reader
        was sent to add patches that are already there. That is the exact
        falsehood the round before had just removed from the sentence above
        it, reinstated one line below.
        """
        # NOT ON A TYPE THAT JUDGES NOTHING. On the Printing record every row
        # is INFO because the TYPE says so, and this note would then single out
        # the two that happen to carry a per-row reason, implying the other six
        # were graded and blaming the printing condition for a choice the user
        # made. The summary beside it is type-aware; this note was added in the
        # same commit and was not, which is the first fault shape again, one
        # line below the fix that named it.
        if self._ungraded_by_type():
            return []
        from workflow.compliance_sets import INFO, ROW_BY_ID
        rows, _rec = self._verdict_rows(r)
        out = []
        for row in rows:
            if row.get("word") != INFO or not row.get("reason"):
                continue
            rid = row.get("row_id") or row.get("key")
            label = tr(ROW_BY_ID[rid].label) if rid in ROW_BY_ID else str(rid)
            out.append((label, self._reason_sentence(row.get("reason"), r)))
        return out

    def _not_computed(self, r: dict) -> "list[tuple[str, str]]":
        """``[(row label, reason sentence)]`` for the rows of *r*'s verdict
        that read N-A because the chart or the reference cannot supply them."""
        from workflow.compliance_sets import N_A, ROW_BY_ID
        rows, _rec = self._verdict_rows(r)
        out = []
        for row in rows:
            if row.get("word") != N_A:
                continue
            rid = row.get("row_id") or row.get("key")
            label = tr(ROW_BY_ID[rid].label) if rid in ROW_BY_ID else str(rid)
            out.append((label, self._reason_sentence(row.get("reason"), r)))
        return out

    def _mismatch_text(self) -> str:
        """The D25 strip: what this chart cannot supply for the chosen set.

        SILENT ON A TYPE THAT JUDGES NOTHING, and it was the third unguarded
        door beside a guarded one. The strip names the limit set and tells the
        user what to add to the chart to have it checked; on a Printing record
        no set is applied and nothing is checked, so every clause of it is
        about a document the user is not looking at.
        """
        r = self._report
        if not r or self._ungraded_by_type():
            return ""
        from workflow.compliance_sets import N_A
        rows, _rec = self._verdict_rows(r)
        missing = [(row.get("row_id") or row.get("key"), row.get("reason"))
                   for row in rows if row.get("word") == N_A
                   and row.get("reason") not in (None, "printing_unrecorded")]
        if not missing:
            return ""
        from workflow.compliance_sets import ROW_BY_ID
        from workflow.measurement_messages import M_REPORT_CHART_MISMATCH
        lines = []
        for rid, reason in missing:
            label = tr(ROW_BY_ID[rid].label) if rid in ROW_BY_ID else str(rid)
            lines.append("• " + label + ": " + self._reason_sentence(reason, r))
        lim = self._window_limits()
        title, body = M_REPORT_CHART_MISMATCH.render(
            set=lim.set_label, rows="\n".join(lines))
        return title + "\n" + body

    # ---- the verdict a report shows ---------------------------------------------
    def _recorded(self, r: dict) -> "dict | None":
        """The verdict *r* was saved with, or None if it carries none."""
        from workflow.measurement_report import recorded_verdict
        return recorded_verdict(r)

    def _verdict_rows(self, r: dict) -> "tuple[list, bool]":
        """``(rows, recorded)`` for one run's verdict.

        *recorded* is True when the rows come off the saved report and False
        when they were worked out just now against the run's limit set. Rows
        are copied, because callers blank them for a drift check. A recorded
        row written before the words existed gets its word from its ``pass``
        and the record's ``graded`` flag.
        """
        from workflow.compliance_sets import FAIL, INFO, N_A, PASS
        rec = self._recorded(r)
        if rec is not None:
            rows = [dict(x) for x in rec["rows"]]
            for row in rows:
                row.setdefault("row_id", _ROW_ID_OF.get(row.get("key"), row.get("key")))
                if "word" not in row:
                    if row.get("pass") is True:
                        row["word"] = PASS
                    elif row.get("pass") is False:
                        row["word"] = FAIL
                    else:
                        row["word"] = INFO if rec.get("graded") is False else N_A
            return self._ungrade(self._keep_rows_for_type(rows)), True
        from workflow.measurement_report import judge
        return self._ungrade(self._keep_rows_for_type(
            judge(r, self._limits_for(r).limits))), False

    def _keep_rows_for_type(self, rows: list) -> list:
        """Only the rows the chosen type is ABOUT.

        T3, "Grey and tone check", is a document about the neutral axis and the
        mid-tone ramps. Dropping the colour rows rather than showing them as
        not applicable is the whole point: a report on the neutral axis does
        not gain by listing what it deliberately leaves out, and a reader would
        have to work out which N-A meant "not measured" and which meant "not
        this report's subject".

        THE COLUMN'S OWN WORD FOLLOWS, and it has to. Filtering only the table
        would leave a Grey and tone check reading FAIL because of a colour row
        it does not show, which is a verdict about something the document never
        mentions.
        """
        from workflow.measurement_report import rows_for_report_type
        keep = rows_for_report_type(self._report_type_now())
        if keep is None:
            return rows
        want = set(keep)
        return [x for x in rows
                if (x.get("row_id") or x.get("key")) in want]

    def _type_changes_the_document(self) -> bool:
        """Whether the chosen type changes which rows the document contains.

        Two ways it can: T4 withholds every verdict, T3 drops the rows it is
        not about. Either way the saved summary, which `stamp_verdict` computed
        over the full report, is a statement about a document nobody is
        looking at.

        ONE QUESTION, ASKED OF THE TYPE. Asked per type, it was answered for
        T4 and not for T3, which is the first of the five fault shapes this
        project keeps meeting.
        """
        from workflow.measurement_report import rows_for_report_type
        return (self._ungraded_by_type()
                or rows_for_report_type(self._report_type_now()) is not None)

    def _ungrade(self, rows: list) -> list:
        """Every row's WORD becomes INFO when the chosen type judges nothing.

        The numbers are not touched, and neither is anything on disk: a row
        that reads FAIL in Full colour check reads INFO here and FAIL again the
        moment the type goes back. A row that was never computed keeps N-A,
        because "we could not measure this" is not a judgement being withheld.
        """
        if not self._ungraded_by_type():
            return rows
        from workflow.compliance_sets import INFO, N_A
        for row in rows:
            if row.get("word") != N_A:
                row["word"] = INFO
        return rows

    def _column_summary(self, r: dict):
        """The one word for a run's column, with its numbers."""
        from workflow.compliance_sets import (Limit, Summary, set_summary,
                                              applies_a_standard)
        from workflow.measurement_report import (is_graded_sheet,
                                                 recorded_compliance)
        rec = self._recorded(r)
        # THE SAVED SUMMARY IS THE FULL REPORT'S, AND A TYPE THAT CHANGES THE
        # DOCUMENT MAY NOT USE IT.
        #
        # This guard was written for T4 alone and the shape came straight back
        # in the door beside it: the early return below hands back the word
        # `stamp_verdict` computed over EVERY row, so a Grey and tone check,
        # which prints three rows, printed a red FAIL earned by five colour
        # rows it does not mention. An adversarial round drove it with a report
        # saved the way the app saves one, which is the state every real user
        # has; the round that built T3 missed it because a bare `.ti3` makes
        # the window derive the report live, the one state where this return
        # does not fire.
        #
        # So the question is asked once, of the type, and not once per type:
        # does the chosen type change which rows are in the document? If it
        # does, the column's word is recomputed over the rows that ARE in it.
        # Nothing is rewritten; the saved word is still on disk and comes back
        # the moment the type does.
        if rec is not None and not self._type_changes_the_document() \
                and isinstance(rec.get("summary"), dict) and rec.get("overall"):
            sm = rec["summary"]
            # THE SAVED WORD IS KEPT, AND IT MAY NOT STAND ALONE. This early
            # return never reached the caveat rule twenty lines below, so a
            # report saved by an earlier build printed a green unqualified PASS
            # under "Custom ISO 12647-7", in the window and in the PDF, while
            # the same report's own text two paragraphs above said it never
            # does that. Recomputing the word instead would contradict the
            # design record, where Knut ruled that a run keeps its values and
            # its verdicts, so the word stays and the sentence gains what the
            # promise requires.
            # THE CAVEAT IS NOT APPENDED HERE, AND THAT WAS TWO FAULTS IN ONE
            # LINE. It used to be, and the reason travels through exactly one
            # render, the Overall cell's `title=`, so the caveat reached a
            # tooltip and no PDF. It is a footnote under the results table now,
            # where a reader sees it.
            #
            # Appending it here broke two further things, both found by a
            # challenge round. The footnote that explains why a profiling sheet
            # has no verdict is chosen by EXACT EQUALITY on this reason, so a
            # longer string silently dropped Knut's 12b explanation for every
            # standard-named set. And `summary_text` calls tr() on the whole
            # reason, so an already-translated caveat glued onto an English key
            # produced a lookup that misses and a sentence half in each
            # language, proved in German.
            _reason = str(sm.get("reason", ""))
            return Summary(rec["overall"], int(sm.get("checked", 0)),
                           int(sm.get("total", 0)), int(sm.get("failed", 0)),
                           int(sm.get("cond", 0)), int(sm.get("not_computed", 0)),
                           _reason)
        rows, recorded = self._verdict_rows(r)
        if recorded:
            comp = recorded_compliance(r) or {}
            from workflow.compliance_sets import limits_from_json
            limits = limits_from_json(comp.get("thresholds")) if comp else {}
            set_id = str(comp.get("set_id", "")) if comp else ""
            if not limits:
                # an older record: two numbers, all-patch rows
                from workflow.measurement_report import (limits_from_pair,
                                                         recorded_thresholds)
                pair = recorded_thresholds(r)
                limits = limits_from_pair(*pair) if pair else {}
        else:
            lim = self._limits_for(r)
            limits, set_id = lim.limits, lim.set_id
        pairs = [(limits.get(row.get("row_id"), Limit.none())
                  if isinstance(limits.get(row.get("row_id")), Limit)
                  else Limit.none(), row.get("word")) for row in rows]
        graded = (bool(rec.get("graded")) if rec is not None
                  else is_graded_sheet(r))
        # THE RAW ID AND THE STORED LABEL, not the resolved set: both are None
        # for a set this ChromIQ no longer defines, and a column reading
        # "Custom ISO 12647-7 (historical)" beside a green PASS is a claim made
        # by arrangement rather than by any sentence.
        _stored = ""
        try:
            _stored = str((recorded_compliance(r) or {}).get("set_label", "") or "")
        except Exception:                       # noqa: BLE001 — a display detail
            _stored = ""
        from workflow.compliance_sets import SUMMARY_REASONS
        _by_type = self._ungraded_by_type()
        return set_summary(pairs,
                           set_is_iso=applies_a_standard(set_id, _stored),
                           graded=graded and not _by_type,
                           ungraded_reason=(SUMMARY_REASONS["record_type"]
                                            if _by_type and graded else ""))

    def _judged_label_for(self, r: dict) -> str:
        """What a column was judged against, for the grid and the provenance."""
        from workflow.measurement_report import (recorded_compliance,
                                                 recorded_thresholds)
        comp = recorded_compliance(r)
        if comp is not None:
            from workflow.compliance_sets import set_label
            label = set_label(str(comp.get("set_id", "")), str(comp.get("set_label", "")))
            if comp.get("set_id") == "pair":
                thr = recorded_thresholds(r)
                label = (tr("two thresholds ({avg} / {max})").format(
                    avg=f"{thr[0]:.1f}", max=f"{thr[1]:.1f}") if thr else label)
            if comp.get("edited"):
                label += " " + tr("(edited)")
            return label
        thr = recorded_thresholds(r)
        if thr is not None:
            return tr("two thresholds ({avg} / {max})").format(
                avg=f"{thr[0]:.1f}", max=f"{thr[1]:.1f}")
        lim = self._limits_for(r)
        label = lim.set_label + (" " + tr("(edited)") if lim.edited else "")
        if r.get("_fresh"):
            return label + " " + tr("(not saved)")
        return label

    def _verdict_provenance(self, r: dict, recorded: bool) -> str:
        """The sentence under one run's accuracy table saying where its words
        came from: the saved record, or this run's limit set, now."""
        label = self._judged_label_for(r)
        if recorded:
            return tr(
                "This verdict was recorded when the report was saved, against "
                "the limit set {label}. It is what this measurement was judged "
                "to be at the time, and this run's current limits do not "
                "change it. Only unlocking the run's limits recalculates it."
            ).format(label=label)
        if r.get("_fresh"):
            return tr(
                "This date has no saved report of its own, so its words are "
                "worked out now against this run's limit set {label}. A report "
                "is saved when a measurement is made with “Save a measurement "
                "report after each measurement” ticked in Preferences → Reports."
            ).format(label=label)
        return tr(
            "Nothing is wrong with this report. It was saved by a version of "
            "ChromIQ that did not yet keep the verdict together with the "
            "measurements, so no PASS or FAIL of its own was stored for it. "
            "The results above are therefore worked out now, against this "
            "run's limit set {label}: they are not the verdict this sheet was "
            "given on the day it was measured, and changing this run's limits "
            "will change them."
        ).format(label=label)

    def _thresholds_cell(self, r: dict) -> str:
        """The Report Results row that says what a column was judged against."""
        if _is_raw_drift(r):
            txt = "—"
        elif self._recorded(r) is None and not r.get("_fresh"):
            txt = tr("not recorded")
        else:
            txt = self._judged_label_for(r)
        return (f"<td align='center' style='color:{_C['faint']};"
                f"font-size:10px'>{html.escape(txt)}</td>")

    def _summary_cell(self, r: dict) -> str:
        """The Overall row: the column's one word, its reason as tooltip."""
        from workflow.compliance_sets import (COND, FAIL, PASS, summary_text,
                                              word_label)
        if _is_raw_drift(r):
            return (f"<td align='center' style='color:{_C['faint']}'>"
                    + html.escape(tr("drift")) + "</td>")
        sm = self._column_summary(r)
        col = {PASS: _C["pass"], FAIL: _C["fail"], COND: _C["cond"]}.get(
            sm.word, _C["faint"])
        return (f"<td align='center' title='{html.escape(summary_text(sm))}' "
                f"style='color:{col};font-weight:bold'>"
                + html.escape(word_label(sm.word)) + "</td>")

    # ---- the deliberate acts: choose a set, unlock, edit -----------------------
    def _confirm(self, title: str, text: str) -> bool:
        """A yes/no question. One method, so a driver can answer it."""
        from PyQt6.QtWidgets import QMessageBox
        from ui.warning_sign import set_question_icon
        box = QMessageBox(self)
        set_question_icon(box)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok
                               | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        ok_btn = box.button(QMessageBox.StandardButton.Ok)
        box.exec()
        # NOT `box.exec() == StandardButton.Ok`: exec() returns an int and a
        # PyQt6 enum member never equals an int, so that comparison is always
        # False and the unlock could never happen. Found by the on-screen
        # driver, 2026-09-08; the unit test had stubbed this method.
        return box.clickedButton() is ok_btn

    def _on_set_chosen(self, index: int) -> None:
        if self._syncing_limits or index < 0:
            return
        set_id = self._set_combo.itemData(index)
        lim = self._window_limits()
        if not set_id or set_id == lim.set_id:
            return
        ctx = self._run_ctx
        if ctx is None:
            # Not in a run: a session-only choice, nothing stored (CH-14).
            from workflow.compliance_sets import SET_BY_ID, effective_limits
            from workflow.run_compliance import RunLimits
            self._limits = RunLimits(set_id, tr(SET_BY_ID[set_id].label),
                                     effective_limits(set_id, self._overrides()),
                                     label_en=SET_BY_ID[set_id].label, bound=False)
            self._refresh()
            return
        # IS IT STILL UNLOCKED? THIS DOOR NEVER ASKED.
        # The lock is read when the window refreshes, to decide whether this
        # combo is ENABLED, and nothing external triggers a refresh. So a run
        # that becomes locked while the window sits open, by its own
        # verification measurement finishing or by another window re-locking
        # it, keeps a live pulldown, and one selection rebinds it and rewrites
        # its saved reports. A challenge round drove both ways in and watched a
        # verdict go from FAIL to PASS on a locked run, under nothing but the
        # ordinary recalculate question.
        #
        # `_locked_here`, not the raw predicate, which is the distinction
        # round 13 was about: a run THIS window bound a moment ago keeps its
        # controls on purpose, and that grace is what the combo was left live
        # for.
        if self._locked_here(ctx.run):
            self._sync_set_combo_to(lim.set_id)
            self._say_locked_before_the_set_changed(ctx.run)
            self._refresh()
            return
        # ASK FIRST WHEN THERE IS A HISTORY TO REWRITE, exactly as unlocking
        # does. This route reached the same consequence with no question at
        # all, and a challenge round drove it: on a run made before #182 with
        # eleven dated verifications, ONE selection in this pulldown rewrote
        # all eleven saved reports and flipped six verdicts from PASS to FAIL,
        # then bound and locked the run so the control was gone.
        #
        # The comment that used to sit here said the pulldown is live only for
        # an unlocked run or one with nothing measured yet, and that stopped
        # being true this morning: the lock now waits for a run to be BOUND and
        # for its SECOND date, both of which were right to add, and both of
        # which leave this pulldown live over a full history. The guard did not
        # move with the rule.
        # ASK, THEN CHECK THE ANSWER IS STILL ABOUT THIS RUN. The guard above
        # runs BEFORE the question, and the question takes as long as a person
        # takes to read it. A challenge round re-locked the run while it was on
        # screen: the user said yes, a locked run was rebound and a saved
        # verdict went from FAIL to PASS, under one box identical to the
        # control. The same re-lock one moment earlier fired a full guard.
        _prefs_at_question = self._prefs_state_now()
        if self._recalculating_would_rewrite_history(ctx.run):
            if not self._confirm_about_run(
                    ctx.run, partial(self._confirm_recalculate, ctx.run)):
                if self._last_refusal != "moved":
                    self._sync_set_combo_to(lim.set_id)
                return
        elif self._run_state_now(ctx.run) != self._run_state_at_sync:
            # NO HISTORY TO REWRITE MEANS NO QUESTION, AND THAT IS EXACTLY THE
            # STATE A LOCK CAN ARRIVE IN: `is_locked` turns on at the SECOND
            # dated verification, so a measurement finishing while this window
            # sat open locks the run with no question ever asked.
            self._sync_set_combo_to(lim.set_id)
            self._say_run_moved_while_asking(ctx.run)
            self._forget_limits()
            self._refresh()
            return
        # THE SAME BIND, AND IT LOCKED THE USER OUT ON THIS ROUTE TOO.
        # A round fixed the "Edit limits…" door and this one kept the fault:
        # on a project made before #182 with a history, choosing a set bound
        # the run and `is_locked` became true on the spot, so the pulldown the
        # user had just used went grey. Same question, same consequence, same
        # remedy: a run that had no set recorded keeps its controls.
        # AND THE FLAG WAS REMOVED FROM THE OTHER BIND DOOR AND NOT FROM THIS
        # ONE. `_bind_without_locking_out` stopped writing `compliance_unlocked`
        # a round ago, for the reason recorded there: it is a snapshot of
        # something that moves, and a challenge round drove the same fault back
        # in through this door. The run is remembered in the session instead,
        # exactly as the other route does it.
        # THE OVERRIDES THIS ANSWER WAS GIVEN FOR, not the ones on disk now.
        # `bind_run` reads them live, AFTER the question, so another window
        # overriding the chosen set while the question was on screen was baked
        # onto the run and every saved report recalculated against numbers
        # nobody in this window ever saw: a challenge round watched six
        # verdicts go from PASS to FAIL that way, under one box mentioning none
        # of it. The identical write through the "Edit limits…" door has been
        # guarded since an earlier round; this one had nothing.
        if self._prefs_state_now() != _prefs_at_question:
            self._sync_set_combo_to(lim.set_id)
            self._say_preferences_changed_meanwhile(reverted=False)
            self._forget_limits()
            self._refresh()
            return
        from workflow.run_compliance import bind_run, is_bound
        _was_bound = is_bound(ctx.run)
        try:
            bind_run(ctx.run, set_id, self._overrides())
            if not _was_bound:
                self._bound_here.add(str(ctx.run.dir))
        except OSError as exc:
            log.warning("could not store the limit set on %s: %s", ctx.run.dir, exc)
        self._forget_limits()
        # Every saved report of the run now follows the new set, once
        # (D23, CH-29).
        self._recalculate_run()
        self._refresh()

    def _saved_report_count(self, run) -> int:
        """How many saved report FILES a recalculation would rewrite.

        THIS COUNTED DATES AND THE SENTENCE SAID REPORTS, which is a lie the
        moment a date holds more than one. `save_report` is timestamped on
        purpose so that a printer's reports accrue for comparison, so several
        per date is designed behaviour: eleven dates saved three times each is
        thirty-three files, and the question said eleven while rewriting all
        thirty-three. A confirmation exists to tell the user the size of what
        they are about to lose, so it counts the thing that is lost.
        """
        n = 0
        try:
            for v in run.verifications():
                try:
                    n += sum(1 for _ in v.reports_dir.glob("report_*.json"))
                except OSError:
                    continue
        except (OSError, AttributeError):
            return 0
        return n

    def _recalculating_would_rewrite_history(self, run) -> bool:
        return self._saved_report_count(run) > 0

    def _confirm_recalculate(self, run) -> bool:
        """Ask before rewriting every saved report of a run.

        The wording follows the unlock confirmation deliberately: the two
        routes have the same consequence, so a user who has met one should
        recognise the other. Singular and plural in full, never "(s)".
        """
        n = self._saved_report_count(run)
        # THE TAIL IS SPLIT TOO, and the first version was not. It said "every
        # one of them" and "the reports they replace" after a head that had
        # just said "one saved report", so the pronouns had nothing to point
        # at, and in German the partitive has to agree as well. The sentence
        # this was modelled on does not have the problem because its tail is
        # self-contained; the copy took the shape and not the property that
        # made the shape work.
        if n == 1:
            _head = tr("This run ({run}) has one saved report.")
            _tail = tr(
                "Changing the limit set recalculates it with the new numbers, "
                "and the report it replaces is kept first, in a reports/old "
                "folder beside its date.\n\nNothing is deleted. Continue?")
        else:
            _head = tr("This run ({run}) has {n} saved reports.")
            _tail = tr(
                "Changing the limit set recalculates every one of them with "
                "the new numbers, and the reports they replace are kept first, "
                "in a reports/old folder beside each date.\n\nNothing is "
                "deleted. Continue?")
        return self._confirm(tr("Change this run's limit set?"),
                             _head.format(run=run.dir.name, n=n) + " " + _tail)

    def _sync_set_combo_to(self, set_id: str) -> None:
        """Put the pulldown back on *set_id* without re-entering this handler."""
        combo = getattr(self, "_set_combo", None)
        if combo is None:
            return
        i = combo.findData(set_id)
        if i < 0:
            return
        self._syncing_limits = True
        try:
            combo.setCurrentIndex(i)
        finally:
            self._syncing_limits = False

    def _relocking_would_take_the_controls(self, run) -> bool:
        """Whether putting the lock back will take the controls away, NOW OR AT
        THE NEXT MEASUREMENT.

        THIS ASKED FOR TWO DATED VERIFICATIONS AND THAT WAS THE WRONG MOMENT.
        The reasoning was that below two dates the lock does not apply, so there
        is nothing to warn about. It does not apply YET: it applies at the next
        measurement, and by then this question, which is the only place that
        names the Preferences setting needed to undo it, is gone. A challenge
        round drove it on the state the app itself creates when it binds a run:
        one click on a box the app had ticked for the user, one more dated
        verification, and the run was locked with the pulldown greyed and the
        unlock box disabled.

        AND IT IS TWO DATES AGAIN, because the state that made a bound run
        enough is gone. That reasoning existed because binding used to tick the
        box on a run the lock did not reach, so a click at one date mattered.
        It no longer does, and asking there made the question false in the
        present tense: it says the limit set can then no longer be changed here,
        while at one date the pulldown stays enabled, the button still reads
        "Edit limits…" and the column is still editable.
        """
        from workflow.run_compliance import is_bound, measured_dates
        try:
            return is_bound(run) and measured_dates(run) >= 2
        except Exception:              # noqa: BLE001
            return False

    def _confirm_relock(self, run) -> bool:
        allow = bool(self._settings.get(
            "compliance_allow_edit_after_measurement", False))
        _tail = tr(
            "Its limit set and its numbers can then no longer be changed here, "
            "and its dated reports stay as they are.")
        _how = ("" if allow else " " + tr(
            "To be able to unlock it again, switch on “Allow editing of "
            "thresholds after the first verification measurement” in "
            "Preferences."))
        return self._confirm(
            tr("Lock this run's limits again?"),
            tr("This run ({run}) will be locked.").format(run=run.dir.name)
            + " " + _tail + _how + "\n\n" + tr("Continue?"))

    def _on_unlock_toggled(self, on: bool) -> None:
        if self._syncing_limits:
            return
        ctx = self._run_ctx
        if ctx is None:
            return
        from workflow.run_compliance import set_run_unlocked
        if not on:
            # RE-LOCKING IS THE IRREVERSIBLE DIRECTION AND IT ASKED NOTHING.
            # Ticking this box asks a confirmation; unticking it did not, and
            # unticking is what takes the controls away. A challenge round found
            # a user who could reach that state in one click on a box the app
            # had ticked for them, and getting back needs a Preferences setting
            # that nothing on this screen names.
            #
            # Only when it would really lock: on a run with fewer than two
            # dated verifications the lock does not apply, so there is nothing
            # to warn about and a question there would be a habit-forming click.
            # THE THIRD DIRECTION, AND THE ONE DOOR OF THE THREE THAT
            # NEVER ASKED AGAIN. Round 17 built the guard and routed the other
            # two through it. A challenge round drove what is left: the user
            # locks their run onto ANOTHER window's looser set, having just
            # been told they could not change it afterwards.
            _would_lock = self._relocking_would_take_the_controls(ctx.run)
            _allow_asked = bool(self._settings.get(
                "compliance_allow_edit_after_measurement", False))
            if _would_lock and not self._confirm_about_run(
                    ctx.run, partial(self._confirm_relock, ctx.run)):
                if self._last_refusal != "moved":
                    self._syncing_limits = True
                    try:
                        self._unlock_check.setChecked(True)
                    finally:
                        self._syncing_limits = False
                return
            # AND THE SETTING THE QUESTION DESCRIBED, WHICH IS NOT THE SAME
            # VALUE. `_relocking_would_take_the_controls` asks whether the run
            # has a history; what decides the WORDING is
            # `compliance_allow_edit_after_measurement`, read inside
            # `_confirm_relock` while it builds the text. That is the right
            # moment to build it and the wrong moment to stop looking: the one
            # sentence in the app naming the setting that gets the controls
            # back is printed only when it is off, and it can go on or off
            # while the user reads. A challenge round flipped it both ways.
            if bool(self._settings.get(
                    "compliance_allow_edit_after_measurement", False)) != _allow_asked:
                self._syncing_limits = True
                try:
                    self._unlock_check.setChecked(True)
                finally:
                    self._syncing_limits = False
                self._say_run_moved_while_asking(ctx.run)
                self._forget_limits()
                self._refresh()
                return
            try:
                set_run_unlocked(ctx.run, False)
            except OSError as exc:
                self._say_not_written(ctx.run, exc)
            self._forget_limits()
            self._refresh()
            return
        n_dates = sum(1 for v in ctx.run.verifications() if v.exists())
        # ONE IS NOT "1 dated verifications". CLAUDE.md asks for explicit
        # singular and plural rather than "(s)", and this sentence read wrong in
        # exactly the state Knut was testing in.
        _tail = tr(
            "Unlocking lets you change the run's limit set and its numbers. "
            "Every dated report of this run will then be recalculated with the "
            "numbers you set, and the previous reports are kept first, in a "
            "reports/old folder beside each date.\n\nNothing is deleted. "
            "Continue?")
        _head = (tr("This run ({run}) has one dated verification.")
                 if n_dates == 1 else
                 tr("This run ({run}) has {n} dated verifications."))
        # ASK, THEN CHECK THE ANSWER IS STILL ABOUT THIS RUN. The question
        # promises the dated reports will be recalculated "with the numbers you
        # set", and it takes as long as a person takes to read it.
        #
        # `may_unlock` is asked again beside it because it is not a property of
        # the run at all: the Preferences switch can be turned off while the
        # question is on screen, and the tick box's enablement was decided when
        # the window last refreshed.
        from workflow.run_compliance import has_measured_verification, may_unlock

        def _put_the_box_back() -> None:
            self._syncing_limits = True
            try:
                self._unlock_check.setChecked(False)
            finally:
                self._syncing_limits = False

        if not self._confirm_about_run(
                ctx.run,
                partial(self._confirm, tr("Unlock this run's limits?"),
                        _head.format(run=ctx.run.dir.name, n=n_dates)
                        + " " + _tail)):
            if self._last_refusal != "moved":
                _put_the_box_back()
            return
        # READ AFTER THE QUESTION, WHICH IS THE WHOLE POINT. Read before it,
        # this holds the value from before the user was asked, so the switch
        # being turned off during the question was invisible and the unlock
        # went through.
        _allow = bool(self._settings.get(
            "compliance_allow_edit_after_measurement", False))
        if not (may_unlock(ctx.run, _allow)
                and has_measured_verification(ctx.run)):
            # SAID OUT LOUD, LIKE THE OTHER HALF. Folding this into the
            # condition above made it share that branch and lose its voice:
            # the Preferences switch went off while the question was on screen,
            # the unlock was refused, and the window said nothing at all.
            _put_the_box_back()
            self._say_run_moved_while_asking(ctx.run)
            self._forget_limits()
            self._refresh()
            return
        try:
            set_run_unlocked(ctx.run, True)
        except OSError as exc:
            # F3: the run folder could not be written; the box must not claim
            # an unlock the disk refused
            self._say_not_written(ctx.run, exc)
            self._syncing_limits = True
            try:
                self._unlock_check.setChecked(False)
            finally:
                self._syncing_limits = False
            return
        self._forget_limits()
        self._recalculate_run()
        self._refresh()

    def _prefs_state_now(self) -> tuple:
        """The two app-wide stores, as they stand on disk right now.

        The window reads these when it opens and the dialog reads them when it
        closes, and both of those are before the recalculate question. This is
        how the same question gets asked one more time, after it.
        """
        try:
            from core.settings import compliance_overrides_of
            return (str(self._settings.get("compliance_default_set", "") or ""),
                    json.dumps(compliance_overrides_of(self._settings),
                               sort_keys=True))
        except Exception:              # noqa: BLE001
            return ()

    def _run_state_now(self, run) -> tuple:
        """EVERYTHING THIS WINDOW'S DECISIONS ABOUT THE RUN DEPEND ON, read
        from disk at this moment.

        It used to be the three fields that say what a run is judged by, and
        that left the LOCK out: a second window re-locking the run while a
        question was on screen changed `compliance_unlocked`, which is not one
        of those three, so the guard saw nothing and the run was rebound on a
        lock. The count of dated verifications is here for the same reason, on
        the other side: the lock turns on at the second one, so a measurement
        finishing during a question locks the run without touching any field
        the first version watched.
        """
        try:
            m = run.load_meta()
            n = sum(1 for v in run.verifications() if v.exists())
        except Exception:              # noqa: BLE001
            return ()
        return (str(m.compliance_set_id or ""),
                # THE TYPE MOVES THE SAME WAY THE SET DOES, so a second window
                # changing it while a question is on screen has to be visible
                # to every door's guard, not only to the one that wrote it.
                str(getattr(m, "report_type", "") or ""),
                json.dumps(m.compliance_thresholds or {}, sort_keys=True),
                str(getattr(m, "compliance_bound_at", "") or ""),
                bool(getattr(m, "compliance_unlocked", False)),
                # THE ONE KEY `_undo_the_edit` WRITES, and it was missing from
                # the state described as everything this window's decisions
                # depend on. A limits window can change which columns a run's
                # report shows, the undo puts that back, and the guard could
                # not see it move.
                list(getattr(m, "compliance_columns", []) or []),
                n)

    def _confirm_about_run(self, run, ask) -> bool:
        """Ask with *ask*, then check the answer is still about the run the
        question described. True only when the user said yes AND nothing moved.

        `ask` is the door's own question, passed in rather than reproduced
        here, so each door keeps the wording it is tested through.

        ONE GUARD FOR EVERY DOOR, because four challenge rounds found the same
        hole in a fourth door each time. A question about recalculating a
        history takes as long as a person takes to read it, and that is the
        whole window a second writer needs: rounds 16 and 17 drove a run
        rebound, re-locked, and locked by its own second measurement, each
        during the question, each acted on afterwards as though the answer had
        been about the state that came back.

        The "before" is the state this window last DREW, not the state at the
        click: everything between the drawing and the click is time the user
        spent looking at the screen, and a guard that stamps at the click has
        already swallowed it.
        """
        _before = self._run_state_at_sync
        if not ask():
            self._last_refusal = "said_no"
            return False
        if self._run_state_now(run) != _before:
            # WHICH REFUSAL IT WAS MATTERS TO THE CALLER. Both end in False,
            # and the callers put their control back to the value it held
            # before the click; that is right when the user said no and wrong
            # here, because the run has MOVED and this has already redrawn the
            # window from disk. A challenge round photographed the result: a
            # pulldown naming a set the run is not bound to, and an unlock box
            # reading "locked" beside a live pulldown on a run that is unlocked
            # on disk.
            self._last_refusal = "moved"
            self._say_run_moved_while_asking(run)
            self._forget_limits()
            self._refresh()
            return False
        self._last_refusal = ""
        return True

    def _say_run_moved_while_asking(self, run) -> None:
        """The run stopped being the run the question was about, between the
        question going up and the answer coming back.

        Nothing is written here, which is what lets the sentence say so
        plainly.
        """
        from ui.warning_sign import warn
        warn(self, tr("This run changed while the question was on screen"),
             # ALL THREE WAYS IN, not two. The guard also fires when the
             # Preferences setting that allows these edits is switched off and
             # when a dated verification is deleted, and the first wording
             # named neither.
             tr("{run} is no longer the run that question was about: a "
                "verification measurement of it finished or was deleted, it "
                "was changed in another window, or the Preferences setting "
                "that allows these edits was switched off. Nothing was "
                "unlocked and nothing was recalculated.").format(
                    run=run.dir.name)
             + "\n\n"
             + tr("Open the limits again to see where it stands."))

    def _say_not_written(self, run, exc) -> None:
        from ui.warning_sign import warn
        log.warning("could not write %s: %s", run.meta_path, exc)
        warn(self, tr("The run folder could not be written"),
             tr("ChromIQ could not save the change to this run's folder:\n{path}\n\n"
                "The folder or its files may be read-only, on a disk that is "
                "full, or open in another program. Nothing was changed. Make the "
                "folder writable and try again.").format(path=str(run.dir)))

    # -- The limits window as ONE act -------------------------------------
    #
    # FIVE CONTROLS IN THAT WINDOW WRITE, AND ONLY ONE OF THEM WAS GUARDED.
    # Four challenge rounds each found the next unguarded one: the run's own
    # column was questioned, then the pulldown beside it, then the "Default for
    # new runs" radio, then a shipped column's cell, then its Restore button.
    # Every fix guarded one door and the round after it walked through the next.
    #
    # So the question is no longer "which control was touched". It is the only
    # one that matters to a user: **did what this run is judged by change?**
    # That is `run_limits()`, the app's own answer, asked before the window
    # opens and again after it closes. A control that cannot move that answer
    # needs no question, and one that can gets the same question whichever it is.

    def _judged_by(self, ctx):
        """What the run is judged by right now, as a comparable value.

        ASKED THROUGH `run_limits` THE WAY THE WINDOW ASKS IT, which is not the
        same as asking it plainly. `run_limits(run, overrides)` falls back to
        the factory set for an unbound run and never looks at the preference;
        the window passes `self._default_set_id()` as a third argument, and that
        is why its "Judged against" line follows the "Default for new runs"
        radio. A predicate that skipped that argument would have watched a value
        the radio cannot move and reported no change while the header changed on
        screen, which is the fault it exists to catch.
        """
        if ctx is None:
            return None
        from workflow.compliance_sets import limits_to_json
        from workflow.run_compliance import run_limits
        try:
            rl = run_limits(ctx.run, self._overrides(), self._default_set_id())
            return (rl.set_id, limits_to_json(rl.limits))
        except Exception:              # noqa: BLE001 — a missing meta
            return None

    def _limits_snapshot(self, ctx):
        """Everything the limits window can write, and what it is judged by."""
        from core.settings import compliance_overrides_of
        run_keys = None
        if ctx is not None:
            try:
                m = ctx.run.load_meta()
                run_keys = (m.compliance_set_id, m.compliance_set_label,
                            m.compliance_thresholds, m.compliance_bound_at,
                            bool(m.compliance_unlocked),
                            list(getattr(m, "compliance_columns", []) or []))
            except Exception:          # noqa: BLE001 — a missing meta
                run_keys = None
        return {
            "run": run_keys,
            "default_set": self._settings.get("compliance_default_set", None),
            "overrides": copy.deepcopy(compliance_overrides_of(self._settings)),
            "judged_by": self._judged_by(ctx),
        }

    def _restore_limits_snapshot(self, ctx, snap) -> bool:
        """Put every one of them back. False when the run's meta would not
        write, which is the case the user has to be told about."""
        from core.settings import store_compliance_overrides
        ok = True
        if ctx is not None and snap.get("run") is not None:
            # ONE UNDO, USED BY BOTH PATHS. This block and the locked-meanwhile
            # branch had grown separate copies of the same reasoning and they
            # disagreed: a refusal on a run another writer had rebound left the
            # user's REFUSED numbers on disk, because it bailed out rather than
            # recovering. `_undo_the_edit` answers the same three questions in
            # one place, and the caller only has to know whether the previous
            # numbers were really recovered.
            # NOT "did it restore", WHICH IS A DIFFERENT QUESTION. A refusal on
            # a run somebody else rebound cannot restore and that is not a
            # failure to write; only a write that was refused by the disk is.
            # KEPT IS NOT THE SAME QUESTION AS OK. A run whose previous
            # numbers really did come back is told its limits are unchanged;
            # one whose could not is told to go and look. The caller had no way
            # to ask, so both got the second sentence.
            self._pending_restore_outcome = self._undo_the_edit(
                ctx, snap, report_failure=True)
            if self._pending_restore_error is not None:
                ok = False
        # THE PREFERENCES GO BACK EVEN WHEN THE RUN'S FOLDER WOULD NOT WRITE.
        # They live in a different file, and leaving them moved is how a
        # refusal ended with the run judged by a set the user said no to.
        try:
            if self._settings.get("compliance_default_set", None) != snap["default_set"]:
                self._settings.set("compliance_default_set", snap["default_set"])
        except Exception:              # noqa: BLE001
            log.warning("could not put the default set back", exc_info=True)
        try:
            from core.settings import compliance_overrides_of
            if compliance_overrides_of(self._settings) != snap["overrides"]:
                store_compliance_overrides(self._settings, snap["overrides"])
        except Exception:              # noqa: BLE001
            log.warning("could not put the overrides back", exc_info=True)
        return ok

    def _say_rebound_meanwhile(self, run, outcome: str = "none") -> None:
        """Somebody else changed this run's limits while the window was open.

        NOT ONLY "a different set". A writer that rebinds to the SAME set with
        different numbers is the same situation and the first wording claimed
        the numbers belonged to a set the run was no longer bound to, which is
        false there.

        AND NOT ONLY "the refusal could not reach the run". It fires now for a
        second Report limits window as well, where the refusal reaches the run
        perfectly and puts the previous numbers back, taking the OTHER window's
        number with them. Telling the user their limits are unchanged and
        stopping would be true of the run and false about what just happened,
        so the second sentence says which of the two it was.
        """
        from ui.warning_sign import warn
        _what = _restore_sentence(outcome)
        warn(self, tr("This run's limits changed while you were editing them"),
             tr("Something else changed {run}'s limits while its own limits "
                "were open: a verification measurement of it finished, or it "
                "was changed in another window.").format(run=run.dir.name)
             + " " + _what + "\n\n"
             + tr("Open its limits and check them before you measure it "
                  "again."))

    def _locked_here(self, run) -> bool:
        """Whether THIS window treats the run as locked.

        The one place that answers it. A run this window bound a moment ago is
        genuinely locked on disk, and greying the control that bound it is what
        two rounds kept trying to prevent; every control in this window has to
        agree about that, and they did not.
        """
        from workflow.run_compliance import is_locked
        if run is None:
            return False
        try:
            if not is_locked(run):
                return False
        except Exception:              # noqa: BLE001
            return False
        return str(getattr(run, "dir", "")) not in self._bound_here

    def _undo_the_edit(self, ctx, snap, report_failure: bool = False) -> str:
        """Take the run's own column back to what it held, and touch nothing
        else. Returns whether the previous numbers were really recovered.

        RETURNS WHICH OF ITS THREE BRANCHES IT TOOK, because the caller has a
        different true sentence for each and there is no yes/no that covers
        them. "restored" put the run's own column back, and an EMPTY column is
        that when the run had none. "rederived" had no previous column to put
        back, so the numbers are the ones whoever bound it meant. And
        "refused_numbers_left" is the case a challenge round named: the set is
        one this build cannot answer for, so the run keeps the numbers the user
        has just REFUSED, is bound, and is judged by them. Only the door beside
        this one used to say that, and this path did not.

        RECOVERED, WHICH IS NOT "WAS BOUND", and it returned the second one.
        A challenge round drove a pre-#182 run that was unbound when the window
        opened: the undo put the empty column back perfectly, exactly as it had
        been, and the caller was handed False and told the user ChromIQ could
        not put this run's own numbers back. The one accurate sentence
        available was the one withheld. An empty column IS the previous
        numbers when the run had none.

        `bind_run` WAS USED FOR THIS AND IT IS NOT AN UNDO. It is a fresh bind:
        its first line replaces a set id this build does not know with the
        factory default, and its body overwrites the run's thresholds with the
        SET's effective limits. A challenge round drove both. On a run carrying
        an edited column, the "undo" deleted the edit that both of its saved
        reports had been judged against, under a message saying the limits were
        unchanged. On a run bound to a set from another build, it erased the id,
        the English label D23 exists for, and every number.

        So this writes exactly the two keys the limits dialog can write, and
        the ONE case it cannot honour, where the run was unbound when the window
        opened so there are no previous numbers to put back, is reported rather
        than papered over with somebody else's.
        """
        from workflow.compliance_sets import (effective_limits, is_known_set,
                                               limits_to_json)
        if snap.get("run") is None:
            return "none"
        _snap_sid = str(snap["run"][0] or "")
        try:
            m = ctx.run.load_meta()
            _sid_now = str(m.compliance_set_id or "")
            # "THE BINDING HAS NOT MOVED" IS NOT "THE SET ID IS THE SAME".
            # Comparing ids alone missed a writer that rebound to the SAME set
            # with different numbers, because its overrides had moved: the undo
            # then wrote the snapshot back over numbers somebody else had just
            # chosen, under a message saying the limits were unchanged.
            # `bind_run` stamps `compliance_bound_at` every time, so that is the
            # signal, and it is the only one that distinguishes a rebind from
            # the dialog's own write.
            #
            # ITS RESOLUTION IS ONE SECOND, and that is a real limit rather than
            # an oversight: `bind_run` writes `isoformat(timespec="seconds")`.
            # A rebind that lands in the same second as the one the snapshot
            # holds is invisible here. Nothing a person can do reaches that (the
            # window has to be opened, a control moved and the window closed),
            # and the case it is written for, a verification measurement
            # finishing while the window is open, takes far longer. Say so
            # rather than pretend the signal is exact.
            _moved = (_sid_now != _snap_sid
                      or str(m.compliance_bound_at or "") != str(snap["run"][3] or ""))
            # WHETHER SOMEBODY ELSE MOVED THE BINDING IS KNOWN HERE AND NOWHERE
            # ELSE, so it is recorded here. Inferring it in the caller by
            # comparing before and after cannot tell an undo that worked from a
            # binding that moved, and fired on the commonest refusal there is.
            if _moved:
                self._pending_rebound = True
            if not _moved:
                # A REAL UNDO: the run's own column, exactly as it was, which
                # for a run that had none means putting the absence back. The
                # binding has not moved, so nothing else has a claim on it.
                if (m.compliance_thresholds == snap["run"][2]
                        and list(getattr(m, "compliance_columns", []) or [])
                        == list(snap["run"][5] or [])):
                    return "restored"      # nothing to write, and nothing lost
                m.compliance_columns = snap["run"][5]
                m.compliance_thresholds = snap["run"][2]
                ctx.run.save_meta(m)
                return "restored"
            m.compliance_columns = snap["run"][5]
            if _sid_now and is_known_set(_sid_now):
                # Not an undo and not pretending to be one. The run was unbound
                # when the window opened, or is bound to something else now, so
                # there is no previous column to put back; leaving the refused
                # edit would be worse. These are the numbers whoever bound it
                # meant, derived with the overrides AS THEY WERE WHEN THIS
                # WINDOW OPENED, because the live table still holds the change
                # the user has just refused and the preferences do not go back
                # until later in this same function.
                m.compliance_thresholds = limits_to_json(
                    effective_limits(_sid_now, snap["overrides"]))
                ctx.run.save_meta(m)
                return "rederived"
            # A set this build does not know. `effective_limits` cannot answer
            # for it and `bind_run` would silently replace it with the factory
            # default, erasing the id, the English label D23 exists for, and
            # every number. Leave the record alone and say so.
            ctx.run.save_meta(m)
            return "refused_numbers_left"
        except OSError as exc:
            # NOT SWALLOWED. This returned False into a caller that dropped it,
            # so `ok` stayed True, `_say_restore_failed` became dead code and a
            # refusal that could not be honoured said nothing at all. A
            # challenge round measured it as a regression: two windows before,
            # one after.
            log.warning("could not undo the edit on %s: %s", ctx.run.dir, exc)
            if report_failure:
                self._pending_restore_error = exc
            return "failed"

    def _say_preferences_changed_meanwhile(self, reverted: bool) -> None:
        """The APP-WIDE report limits were changed by somebody else while this
        window was open.

        Its own message, because it is its own thing. Folded into the run's, it
        announced a change to the preferences as a change to a run whose files
        nothing had touched, and on the path where nothing is put back it
        claimed the other change was gone while it was still on disk.
        """
        from ui.warning_sign import warn
        _what = (tr("ChromIQ put them back to what they were when you opened "
                    "this window, so that change is gone too.")
                 if reverted else
                 tr("ChromIQ did not change them back, so they hold whichever "
                    "change was made last."))
        warn(self, tr("The report limits in Preferences changed while this "
                      "window was open"),
             # NOT "no run's own limits were touched", WHICH THIS WINDOW
             # CANNOT PROMISE. It is shown by a window that may have just
             # moved this run's own numbers and rewritten its saved reports,
             # and a challenge round photographed it landing directly under a
             # box saying exactly that. This message is about the app-wide
             # preferences and says only what it knows.
             tr("Something else changed the report limits in Preferences while "
                "this window was open: they were edited in another window.")
             + " " + _what + "\n\n"
             + tr("Open Preferences and check them before you measure "
                  "again."))

    def _say_collision_went_ahead(self, run) -> None:
        """Somebody else changed this run's limits while the window was open,
        and the user went ahead anyway, so the other change is gone.

        The refusal path has said this since round 13. THIS path said nothing:
        the user was asked the ordinary recalculate question, said yes, and the
        other window's number was overwritten with no mention of it. On a run
        with no saved reports there is not even a question, so nothing at all
        appeared.
        """
        from ui.warning_sign import warn
        warn(self, tr("This run's limits changed while you were editing them"),
             tr("Something else changed {run}'s limits while its own limits "
                "were open: a verification measurement of it finished, or it "
                "was changed in another window.").format(run=run.dir.name)
             + " "
             + tr("ChromIQ went ahead with the change you asked for, so the "
                  "other change is gone.")
             + "\n\n"
             + tr("Open its limits and check them before you measure it "
                  "again."))

    def _say_locked_before_the_set_changed(self, run) -> None:
        """The run was locked between the window opening and this pulldown
        being used, so the selection is put back and nothing is written.

        Nothing to undo here, which is what separates it from
        `_say_locked_meanwhile`: this door is guarded BEFORE it writes, so the
        run is untouched and the sentence can say so plainly.
        """
        from ui.warning_sign import warn
        warn(self, tr("This run was locked while this window was open"),
             tr("{run} was locked while this window was open: a verification "
                "measurement of it finished, or it was locked in another "
                "window.").format(run=run.dir.name)
             + " " + tr("Its limits and its dated reports are unchanged.")
             + "\n\n"
             + tr("Open the limits again to see where it stands."))

    def _say_locked_meanwhile(self, run, outcome: str) -> None:
        """The run was locked between opening the window and closing it."""
        from ui.warning_sign import warn
        # THE SECOND SENTENCE WAS TRUE ONLY WHERE IT WAS TESTED. It said the
        # run had no limits of its own when the window opened, and it fires
        # whenever the undo could not be honoured, which includes a run that WAS
        # bound and a set this build cannot answer for. In that last case the
        # numbers left on the run are the ones the app has just refused, and the
        # sentence claimed they were whatever locked it wrote.
        # NOTHING WAS REFUSED HERE. This window follows no question: the
        # lock stopped the edit. Both of the refusal-flavoured sentences were
        # false in it, one of them saying a change was "gone too" when the
        # only other change was the lock, which the undo never touches.
        _what = _restore_sentence(outcome, refused=False)
        warn(self, tr("This run was locked while you were editing it"),
             tr("Something else locked {run} while its limits were open: a "
                "verification measurement of it finished, or it was locked in "
                "another window.").format(run=run.dir.name)
             + " " + _what + "\n\n"
             + tr("Open the limits again to see where it stands."))

    def _say_restore_failed(self, run, exc) -> None:
        """The refusal could not be honoured, which is the opposite of what
        `_say_not_written` says.

        That message ends "Nothing was changed", and here something was: the
        limits window had already written the edit on its way out, and putting
        it back is what failed. Saying "nothing was changed" would be the one
        false sentence available, so this says what is true instead.
        """
        from ui.warning_sign import warn
        from workflow.run_compliance import is_bound
        log.warning("could not undo the edit in %s: %s", run.meta_path, exc)
        # SAY WHICH THING IS OUT OF STEP, AND ONLY IF IT IS.
        # The first version said "the run now holds the numbers you were
        # editing… so the two no longer agree", which is true only when the run
        # is BOUND. A challenge round drove the other case: on a project made
        # before #182 the run is still unbound, so the numbers left behind
        # govern nothing and the sentence named a disagreement that did not
        # exist, while the instruction that followed it fixed nothing.
        _bound = False
        try:
            _bound = is_bound(run)
        except Exception:              # noqa: BLE001
            _bound = False
        _what = (tr("This run is judged by those numbers, and its saved reports "
                    "were NOT recalculated, so the two no longer agree. Make "
                    "the folder writable, then either set the numbers back or "
                    "change the limits again to recalculate the reports.")
                 if _bound else
                 tr("Nothing is judged by those numbers: this run has no limit "
                    "set of its own, so it is still judged by the default, and "
                    "its saved reports were not recalculated. Make the folder "
                    "writable if you want the leftover numbers cleared."))
        warn(self, tr("The change could not be undone"),
             tr("You chose not to change this run's limits, but ChromIQ could "
                "not put the previous numbers back:\n{path}\n\nThe folder or "
                "its files may be read-only, on a disk that is full, or open in "
                "another program. Your Preferences were put back, because they "
                "are stored elsewhere.").format(path=str(run.dir))
             + "\n\n" + _what)

    def _on_open_limits(self) -> None:
        from ui.dialogs.thresholds_dialog import ThresholdsDialog
        ctx = self._run_ctx
        # EDITABLE MEANS NOT LOCKED, and this line asked a narrower question.
        # It keyed on the hand-lift flag alone, so a run that is not locked
        # because it has only ONE dated verification (the state Knut asked for
        # by name, so that the settings can still be changed) got a read-only
        # column, a note telling it to tick "Unlock this run's limits", and
        # that tick box greyed out in the window behind. Three controls, three
        # different answers about one run. The lock rule gained its second
        # condition this morning; this line did not move with it.
        # ONE ANSWER ABOUT THIS RUN, AND THIS LINE HAD ITS OWN.
        # `_sync_limit_controls` treats a run this window bound as unlocked, so
        # the pulldown stays live and the button reads "Edit limits…"; this
        # asked the raw predicate, so the same run opened a READ-ONLY column
        # whose note pointed at an unlock box the window was hiding. Three
        # controls, three answers, which is the fault two rounds fixed twice.
        dlg = ThresholdsDialog(self._settings, self,
                               run=ctx.run if ctx else None,
                               run_editable=bool(ctx and not self._locked_here(ctx.run)))
        # SNAPSHOT BEFORE, BECAUSE THE DIALOG WRITES ON ITS WAY OUT AND
        # FOUR OF ITS CONTROLS WRITE THE MOMENT THEY ARE TOUCHED.
        # `ThresholdsDialog.done()` stores the edited column whatever result it
        # is closing with, and its only button is Close, wired to accept, so
        # Escape writes too. The radio, a shipped column's cell, that column's
        # Restore button and the column tick boxes do not wait for the close at
        # all. There is no route out of that window that does not commit.
        snap = self._limits_snapshot(ctx)
        self._pending_restore_error = None
        dlg.exec()
        edited_run_column = bool(dlg.run_limits_changed)
        # SOMEBODY ELSE WROTE THIS RUN'S COLUMN WHILE THE WINDOW WAS OPEN, and
        # only the dialog can know it. The refusal path asks "has the binding
        # moved?" through `compliance_bound_at`, which ONLY `bind_run` stamps;
        # the other writer here is `set_run_limits`, which is a second Report
        # limits window closing. A challenge round drove all three cases side by
        # side: another `bind_run` produced two boxes and told the user, a real
        # second limits window produced one, its number erased in silence, and
        # a control run where nobody else wrote produced the same one box. The
        # user could not tell the middle case from the last.
        # TWO COLLISIONS, TWO ANSWERS. They were folded into one flag and
        # reported through messages written about the RUN, so a change to the
        # app-wide preferences was announced as a change to run3, and on the
        # accept path the sentence said the other change was gone while it was
        # still on disk. They are separate because what happens to them is
        # separate: the run's own column is put back by the undo, and the
        # preferences are put back only when the user refuses.
        collided = bool(getattr(dlg, "run_limits_collided", False))
        prefs_collided = bool(getattr(dlg, "prefs_collided", False))
        dlg.deleteLater()
        self._forget_limits()

        # DID WHAT THIS RUN IS JUDGED BY CHANGE? That is the whole test, and it
        # replaces asking which control was touched, which is the question that
        # let four rounds each find the next unguarded one. `run_limits` is the
        # app's own answer: for a bound run its stored copy, for an unbound one
        # the live preference and the app-wide overrides.
        # THE TRIGGER IS SOMETHING THIS WINDOW WROTE, AND ONLY THAT.
        #
        # Two rounds sharpened this. Taking `edited_run_column` on its own asked
        # the question for an edit that typed a number and typed it straight
        # back: net zero, and on an unbound run it still bound the run and
        # rewrote eleven reports, a permanent change with no control that undoes
        # it. And taking a movement in `judged_by` on its own asked the user
        # about a binding ANOTHER writer had made while the window sat open, a
        # second report window or `ensure_bound` at a verification measurement,
        # where the natural answer to a question you did not ask for silently
        # reverted the other writer.
        #
        # So each door is tested for what it really did:
        #   the run's own column   the dialog says it wrote, AND the numbers
        #                          on disk actually differ
        #   the preferences        they differ, AND that moved what this run is
        #                          judged by (on a bound run it cannot)
        # Anything else in the run's meta, a column tick or another writer's
        # bind, is not this window's doing and is left alone.
        _now = self._limits_snapshot(ctx)
        _run_numbers_moved = bool(
            edited_run_column and snap["run"] is not None
            and _now["run"] is not None and _now["run"][2] != snap["run"][2])
        _prefs_moved = ((_now["default_set"] != snap["default_set"]
                         or _now["overrides"] != snap["overrides"])
                        and _now["judged_by"] != snap["judged_by"])
        # THE THIRD THING THIS WINDOW WRITES TO A RUN, and it was in neither
        # term. The column tick box writes `compliance_columns` the moment it
        # is clicked, the undo puts that key back, and the lock branch's
        # trigger could not see it: a run re-locked while the window was open
        # kept that write with no message, and was refused only if the user had
        # ALSO typed a number.
        _run_columns_moved = bool(
            snap["run"] is not None and _now["run"] is not None
            and list(_now["run"][5] or []) != list(snap["run"][5] or []))
        moved = ctx is not None and (_run_numbers_moved or _run_columns_moved
                                     or _prefs_moved)

        # THE LOCK WAS READ WHEN THE WINDOW OPENED AND ENFORCED NOWHERE ELSE.
        # `run_editable` is decided before the dialog is built and the dialog
        # writes as it closes, so a run that becomes locked in between takes the
        # edit anyway. A challenge round drove both ways in: a verification
        # measurement's own `ensure_bound` binding the run while the window sat
        # open, and a second window re-locking it. Eleven saved reports were
        # rewritten on a locked run.
        # `_locked_here`, THE SAME ANSWER THE DIALOG WAS BUILT FROM TWELVE
        # LINES ABOVE. This asked the raw predicate, so on a run THIS window had
        # just bound, the window offered an editable column, took the number the
        # user typed, threw it away, and told them something else had locked the
        # run while they were editing it. Nothing else had: this window bound it
        # one action earlier. The escape hatch it points at is hidden in that
        # state, so the user can repeat it for ever.
        #
        # A challenge round drove it on both bind doors, two projects, two
        # languages, and proved with a mutation pair that no test could see it:
        # the one test covering this function stubs the dialog with a fake that
        # writes nothing, so `moved` is False and this line is never reached.
        # NOT GATED ON WHICH CONTROL MOVED. `_run_numbers_moved` was in this
        # condition, so the lock was enforced when the user had typed in the
        # run's own column and skipped when they had moved the "Default for new
        # runs" radio instead. A challenge round drove the difference on a
        # pre-#182 run with eleven saved reports: a verification measurement
        # binding and locking the run while the window sat open was refused in
        # the first case and went straight through in the second, archiving and
        # rewriting all eleven and moving six verdicts from PASS to FAIL, on a
        # run the app says is locked, judged by a set the user never picked.
        #
        # Which control the user touched has nothing to do with whether the run
        # may be written. `_locked_here` is the whole question.
        if moved and self._locked_here(ctx.run):
            log.info("the run was locked while its limits window was open; "
                     "the edit is not applied to %s", ctx.run.dir)
            _outcome = self._undo_the_edit(ctx, snap)
            self._say_locked_meanwhile(ctx.run, _outcome)
            if prefs_collided:
                # THIS BRANCH RETURNS ABOVE WHERE THE APP-WIDE COLLISION WAS
                # REPORTED, so a lock arriving at the same moment made the
                # window silent about a change it is noisy about otherwise, and
                # left that change standing. Nothing here puts the preferences
                # back, so the sentence is the one that says so.
                self._say_preferences_changed_meanwhile(reverted=False)
            self._forget_limits()
            self._refresh()
            return
        if moved:
            # THE STATE TO COMPARE AGAINST IS THE ONE TAKEN BEFORE THE
            # QUESTION, and the question is asked inside the condition below.
            # A challenge round wrote this run's numbers from another window
            # while that question was on screen: the collision check had
            # already run, so nothing was raised, and the recalculation judged
            # every saved report by a number the user never typed and never
            # saw. Read here, one line before the asking.
            _state_before_asking = self._run_state_now(ctx.run)
            # AND THE APP-WIDE STORES, FOR THE SAME REASON. `prefs_collided`
            # is decided inside the dialog's `done()`, which is over before
            # this question goes up. Round 17 taught this function to look at
            # the RUN again afterwards and left these on the old reading, so
            # another window's change to them during the question was reverted
            # by the refusal with no box at all. That is round 15's R15-3 and
            # round 16's R16-2 again, one moment later.
            _prefs_before_asking = self._prefs_state_now()
            if (self._recalculating_would_rewrite_history(ctx.run)
                    and not self._confirm_recalculate(ctx.run)):
                if self._prefs_state_now() != _prefs_before_asking:
                    prefs_collided = True
                # AND THE RUN'S OWN STATE, WHICH THIS BRANCH READ AND NEVER
                # COMPARED. The app-wide comparison was added four lines above
                # and the run's was left behind, so another window's write to
                # the run DURING the question was wiped by the undo with no box
                # at all, while the same write one moment earlier produced the
                # correct two.
                if self._run_state_now(ctx.run) != _state_before_asking:
                    collided = True
                self._pending_rebound = collided
                self._pending_restore_outcome = "none"
                if not self._restore_limits_snapshot(ctx, snap):
                    self._say_restore_failed(ctx.run, self._pending_restore_error)
                elif self._pending_rebound:
                    self._say_rebound_meanwhile(
                        ctx.run, self._pending_restore_outcome)
                if prefs_collided:
                    # The refusal put them back, so the other change is gone.
                    self._say_preferences_changed_meanwhile(reverted=True)
                self._forget_limits()
                self._refresh()
                return
            if self._prefs_state_now() != _prefs_before_asking:
                prefs_collided = True
            if self._run_state_now(ctx.run) != _state_before_asking:
                # SOMEBODY WROTE THIS RUN WHILE THE QUESTION WAS ON SCREEN.
                # Going ahead would recalculate every saved report against
                # whatever they wrote, under a question about what the user
                # typed. Treated as the refusal it has to be: the run's own
                # column goes back and the user is told, once, by the window
                # that already exists for exactly this.
                self._pending_restore_outcome = "none"
                if not self._restore_limits_snapshot(ctx, snap):
                    self._say_restore_failed(ctx.run,
                                             self._pending_restore_error)
                else:
                    self._say_rebound_meanwhile(
                        ctx.run, self._pending_restore_outcome)
                if prefs_collided:
                    self._say_preferences_changed_meanwhile(reverted=True)
                self._forget_limits()
                self._refresh()
                return
            # NOT `bind_run`, WHICH WOULD COPY THE SET'S NUMBERS OVER THE
            # USER'S. `done()` may have just written an edited column; all that
            # can be missing is the record that makes `is_bound` true.
            from workflow.run_compliance import is_bound
            if not is_bound(ctx.run):
                # KEEP THE USER'S OWN COLUMN, ADOPT NOTHING ELSE. A run can
                # hold thresholds and still be unbound, because
                # `ThresholdsDialog.done()` writes numbers without a set id, and
                # the app itself creates that state: a refusal whose undo fails
                # leaves them behind, and `_say_restore_failed` tells the user
                # they govern nothing. Testing `if not m.compliance_thresholds`
                # then adopted those leftovers, so a later visit that moved only
                # the "Default for new runs" radio bound the run to the chosen
                # set holding a stale number that was never on screen, and
                # rewrote eleven reports with it.
                self._bind_without_locking_out(
                    ctx.run, self._window_limits().set_id,
                    keep_numbers=_run_numbers_moved)
                self._forget_limits()
            self._recalculate_run()
            # AND THE SAME COLLISION ON THE WAY THROUGH, WHICH SAID NOTHING.
            # `collided` was read in one place, inside the refusal above, so a
            # user who said YES lost the other window's change in silence: one
            # box, the ordinary recalculate question, indistinguishable from
            # the case where nobody else wrote. A challenge round drove it, and
            # found a worse half of the same door: with no saved reports there
            # is no question to ask, so the collision produced NO box at all.
            if collided:
                self._say_collision_went_ahead(ctx.run)
            if prefs_collided:
                # NOTHING WAS PUT BACK HERE, so nothing is gone: whichever
                # window wrote last is what the preferences hold. Saying "the
                # other change is gone" on this path was false, and a challenge
                # round read the value off disk to prove it.
                self._say_preferences_changed_meanwhile(reverted=False)
        self._refresh()

    def _bind_without_locking_out(self, run, set_id: str,
                                  keep_numbers: bool = False) -> None:
        """Record the set on a run that had none, and leave the controls where
        they were.

        `is_locked` is bound AND two dated verifications AND not unlocked, so on
        a project made before #182 with a history, binding IS locking: the
        pulldown greys, the button becomes "Show limits…", and the unlock box
        comes back disabled, because it consults a preference that ships off.
        A challenge round drove both routes into this and found the user asking
        for control of these numbers and the act of granting it removing it,
        under a question that mentioned neither.

        The set label is stored in English so a later ChromIQ that no longer
        knows the id can still name it (D23), and `bound_at` is the other half
        of the record `bind_run` writes; a run bound with only the id printed
        the raw internal id to the user.
        """
        from workflow.compliance_sets import (SET_BY_ID, is_known_set,
                                               limits_to_json)
        try:
            m = run.load_meta()
            m.compliance_set_id = set_id
            if is_known_set(set_id):
                m.compliance_set_label = SET_BY_ID[set_id].label
            # THE NUMBERS, WHICH ARE THE HALF `is_bound` ACTUALLY TESTS.
            # This wrote four keys and not this one, so the run it "bound" was
            # not bound: `is_bound` wants the id AND the thresholds. A challenge
            # round drove the consequence and it is worse than a missing field.
            # The run could never lock again, its numbers went on following the
            # live app-wide overrides while eleven saved reports said something
            # else, `compliance_bound_at` recorded a binding that had not
            # happened, and the next verification measurement bound it a third
            # time to whatever was live at that moment.
            #
            # THE WINDOW'S OWN NUMBERS, unless this visit edited the run's
            # column, in which case `ThresholdsDialog.done()` has just written
            # the user's and they are the one thing that must not be
            # overwritten. Anything else already on the run was left by
            # something else and is not evidence of what the user just agreed
            # to.
            if not keep_numbers:
                m.compliance_thresholds = limits_to_json(
                    self._window_limits().limits)
            m.compliance_bound_at = datetime.now().isoformat(timespec="seconds")
            # NOTHING IS WRITTEN ABOUT THE LOCK, AND THAT WAS THE MISTAKE.
            #
            # Three rounds each moved this flag: set always, then set only at
            # two dated verifications or more. Both are a SNAPSHOT of something
            # that keeps moving. `compliance_unlocked` means "the user lifted
            # the lock", `is_locked` reads it live, and the number of dated
            # verifications can go DOWN, because "Delete a verification" is a
            # shipped menu action. A challenge round drove it on a shipped demo
            # project: the box ended up ticked and live on a run one date old,
            # one click un-ticked it with no question, and the box vanished.
            #
            # The run keeps its controls for as long as this window is open
            # instead, remembered in the session and not on disk. Nothing false
            # is recorded about a lock nobody lifted, and the lock itself
            # behaves exactly as it is designed to: a bound run with a history
            # is locked, which is what binding one means.
            run.save_meta(m)
        except OSError as exc:
            log.warning("could not record the set on %s: %s", run.dir, exc)
            return
        self._bound_here.add(str(run.dir))

    def _recalculate_run(self) -> None:
        """Re-stamp every saved report of the window's run with the run's
        current limits, rewriting each file in place (D23), once per
        deliberate act (CH-29), and refresh the loaded history to match.

        ARCHIVE FIRST, PER DATE, AND NEVER REWRITE WHAT COULD NOT BE ARCHIVED
        (R4, review F2/F11). ``Verification.archive_reports`` copies only
        content that has no copy yet, so a report stamped after the unlock
        gets its copy before its first rewrite and a repeat changes nothing.
        A date whose archive fails is left exactly as it is and named in a
        window.
        """
        ctx = self._run_ctx
        if ctx is None:
            return
        from datetime import datetime as _dt
        from PyQt6.QtGui import QCursor
        from workflow.measurement_report import (list_reports,
                                                 rewrite_report,
                                                 stamp_report_type,
                                                 stamp_verdict)
        from workflow.run_compliance import run_limits
        lim = run_limits(ctx.run, self._overrides(), self._default_set_id())
        when = _dt.now()
        # THREE THINGS CAN GO WRONG HERE AND THEY ARE NOT THE SAME THING.
        # They used to share one list and one message, and the message
        # described only the first of them. A challenge round drove the second:
        # three reports on one date with the middle file read-only and the
        # folder writable. Two of the three were rewritten, the date was
        # reported as untouched, and every sentence of the message was false in
        # that state, including the instruction, which fixed nothing.
        no_archive: list[str] = []    # nothing on this date was touched
        no_write: list[str] = []      # archived, and not one file was written
        part_written: list[str] = []  # some of this date's files were rewritten
        unreadable: list[str] = []    # a file that could not be parsed at all
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            for v in ctx.run.verifications():
                paths = list_reports(v.dir)
                if not paths:
                    continue
                try:
                    v.archive_reports(when)
                except OSError as exc:
                    log.warning("could not archive reports of %s: %s", v.dir, exc)
                    no_archive.append(v.id)
                    continue
                _failed = False
                _written = 0
                for path in paths:
                    try:
                        rep = json.loads(read_text(path))
                    except Exception:  # noqa: BLE001
                        # NOT SILENT ANY MORE. It is the safe direction, since
                        # the file is left exactly as it was, but a report the
                        # user can see in the window and that no recalculation
                        # ever reaches is worth one line.
                        # NOT `_failed`, AND THAT ONE LINE PUT THE DATE IN TWO
                        # LISTS AT ONCE. A challenge round drove a date whose
                        # ONLY report file is not JSON and read back four false
                        # clauses: some reports were recalculated (none were), a
                        # file could not be written (none was attempted), the
                        # date holds old and new verdicts (it holds one), and
                        # the window shows what the unwritten file carries
                        # (there is no unwritten file). A file that cannot be
                        # READ is its own kind of failure and has its own list.
                        log.warning("could not read %s; left as it is", path)
                        unreadable.append(f"{v.id}/{Path(path).name}")
                        continue
                    stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                                  set_label=lim.label_en, edited=lim.edited)
                    # …AND THE TYPE, which the verdict beside it was already
                    # getting. A recalculation rewrote every saved report with
                    # the run's current limits and left them claiming the type
                    # the run held when they were first saved, so the record
                    # said one thing and the run another. Driven by an
                    # adversarial round on three dated verifications, including
                    # the copies archived into reports/old.
                    stamp_report_type(rep, ctx.run)
                    try:
                        rewrite_report(path, rep)
                        _written += 1
                    except OSError as exc:
                        log.warning("could not rewrite %s: %s", path, exc)
                        _failed = True
                if _failed:
                    # "SOME WERE RECALCULATED" HAS TO BE TRUE, AND ON A DATE
                    # WITH ONE REPORT FILE IT NEVER IS. Every dated verification
                    # in the shared demo data ships with exactly one, which is
                    # the ordinary case: a single read-only file means NONE of
                    # that date was recalculated and it holds only its old
                    # verdict, while the message said it held both.
                    (part_written if _written else no_write).append(v.id)
            # the history in memory: the same records, refreshed (the dates
            # left untouched on disk are left untouched here as well)
            # A DATE THAT WAS ONLY PARTLY WRITTEN KEEPS ITS OLD VERDICT HERE
            # TOO, which is the conservative half of an unavoidable
            # inconsistency: some of its files now say one thing and some the
            # other, and showing the OLD word matches the file that could not
            # be written. The message below says exactly that rather than
            # letting the window imply the whole date moved.
            _held = set(no_archive) | set(no_write) | set(part_written)
            for r in self._history:
                origin = str(r.get("_origin_dir", ""))
                if origin.startswith(str(ctx.run.dir)) \
                        and Path(origin).name not in _held:
                    stamp_verdict(r, lim.limits, set_id=lim.set_id,
                                  set_label=lim.label_en, edited=lim.edited)
        finally:
            QApplication.restoreOverrideCursor()
        if no_archive or no_write or part_written or unreadable:
            from ui.warning_sign import warn
            _parts: list[str] = []
            if no_archive:
                _parts.append(tr(
                    "These dates were not touched at all, because the previous "
                    "report could not be copied into their reports/old folder, "
                    "and a report is never rewritten before its previous "
                    "version is kept:\n{dates}").format(
                        dates="\n".join(sorted(set(no_archive)))))
            if no_write:
                _parts.append(tr(
                    "On these dates the previous reports were kept, but none of "
                    "the reports could be written, so each of them still holds "
                    "the verdict it had:\n{dates}").format(
                        dates="\n".join(sorted(set(no_write)))))
            if part_written:
                _parts.append(tr(
                    "On these dates the previous reports WERE kept and some of "
                    "the reports were recalculated, but at least one file could "
                    "not be written, so that date now holds both old and new "
                    "verdicts. The window shows the old one, which is the one "
                    "the unwritten file still carries:\n{dates}").format(
                        dates="\n".join(sorted(set(part_written)))))
            if unreadable:
                _parts.append(tr(
                    "These report files could not be read at all and were left "
                    "exactly as they are:\n{files}").format(
                        files="\n".join(sorted(set(unreadable)))))
            # AND THE CLOSING LINE FOLLOWS THE LISTS THAT ARE ACTUALLY THERE.
            # It was appended unconditionally, so a date with one corrupt file
            # was told to make its files writable and try again, which fixes
            # nothing and re-runs the same failure.
            if no_archive or no_write or part_written:
                _parts.append(tr(
                    "Individual files can be read-only while their folder is "
                    "writable. Make the files and the folders writable, then "
                    "change the limits again to bring them all up to date."))
            if unreadable:
                _parts.append(tr(
                    "A file that cannot be read is not a permissions problem "
                    "and changing the limits again will not help. Open it, or "
                    "move it out of its reports folder, and the next "
                    "recalculation will leave a fresh one in its place."))
            warn(self, tr("Some reports were not recalculated"),
                 "\n\n".join(_parts))

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
        def _th(d):
            # (date, time) pairs arrive when several columns share a calendar
            # date — the time on a second line keeps them tellable apart
            # (Knut, 2026-08-11); a lone check per day stays date-only.
            if isinstance(d, tuple):
                day, clock = d
                inner = (html.escape(day) + "<br><span style='font-weight:"
                         "normal'>" + html.escape(clock) + "</span>")
            else:
                inner = html.escape(d)
            return "<th align='right' style='" + thb + "'>" + inner + "</th>"

        th = ("<tr><th align='left' style='" + thb + ";padding:2px 14px 3px 0'>"
              + html.escape(tr("Metric")) + "</th>"
              + "".join(_th(d) for d in dates) + "</tr>")
        body = [th]
        zebra = 0
        for label, cells in data_rows:
            if cells is None:
                # A block header spanning every column — the gamut-split groups
                # arrive as row blocks so the side-by-side dated columns stay
                # intact (Knut, 2026-08-10). Zebra restarts under each block.
                body.append(
                    f"<tr><td colspan='{1 + len(dates)}' style='padding:7px 0 "
                    f"2px;color:{_C['faint']};font-weight:bold;"
                    "white-space:nowrap'>" + html.escape(label) + "</td></tr>")
                zebra = 0
                continue
            bg = f" style='background:{self._ZEBRA_BG}'" if zebra % 2 == 1 else ""
            zebra += 1
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
        days = [str(r.get("created") or "")[:10] for r in runs]
        shared = {d for d in days if days.count(d) > 1}
        for i in range(0, len(runs), _MAX_RUN_COLS):
            chunk = runs[i:i + _MAX_RUN_COLS]
            dates = [((str(r.get("created") or "")[:10],
                       str(r.get("created") or "")[11:16])
                      if str(r.get("created") or "")[:10] in shared
                      else str(r.get("created") or "")[:10])
                     for r in chunk]
            rows = [(label, None if get is None else [get(r) for r in chunk])
                    for label, get in row_getters]
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
        # THE RUN'S DESCRIPTION, AT THE TOP OF THIS SECTION. Knut, 2026-09-11,
        # asked whether the one-page report should carry a customer or job
        # name: *"No customer or job name per today. But print the run's
        # description at the top of the section that shows the scope of the
        # report and the measurements included, and nothing when it is
        # empty."* He named this section, which every report type has, so it
        # is here rather than in one type's own body.
        #
        # NOTHING WHEN IT IS EMPTY. Not a blank line, not a label with no
        # value: a run nobody described says nothing about itself.
        desc = self._run_description()
        out = (_h2(tr("Report Scope")) + _gap()
               + (f"<div style='font-weight:bold;margin:0 0 4px'>"
                  + html.escape(desc) + "</div>" if desc else "")
               + "<div>" + html.escape(intro)
               + "</div><ul style='margin:2px 0 6px'>" + items + "</ul>"
               + "<div><b>" + html.escape(tr("No. of Measurements:")) + "</b></div>"
               + f"<div style='{ind}'>{sc['total']}</div>"
               + "<div><b>" + html.escape(tr("Date range:")) + "</b></div>"
               + f"<div style='{ind}'>{html.escape(d0)} – {html.escape(d1)}</div>")
        # Honesty note: a filtered report must say it is filtered, so it can
        # never pass as the complete history (Sebastian, 2026-08-10).
        # COUNT WHAT THE USER UNTICKED, not what is missing from the list.
        # This was `len(self._history) - len(runs)`, which is the same number
        # only while the ticks are the only thing that narrows a report. The
        # one-page summary narrows to a single measurement by its nature, and
        # the sentence then told a user who had unticked nothing that they had
        # hidden a run.
        hidden = (sum(1 for r in self._history
                      if self._run_key(r) in self._hidden_runs)
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

    def _run_description(self) -> str:
        """What the user wrote about this run, or "".

        The window's own run, not each column's: a report holding several runs
        has no single description, and a heading that names one of them would
        be wrong about the rest.
        """
        ctx = self._run_ctx
        if ctx is None or len(self._distinct_run_dirs()) > 1:
            return ""
        try:
            return str(ctx.run.load_meta().description or "").strip()
        except Exception as exc:                 # noqa: BLE001 — a heading
            log.debug("could not read the run description: %s", exc)
            return ""

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
                    "gamut": tr("gamut check — profile applied at build"),
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
            elif w["kind"] == "compliance":
                # #182 (D9): one limit set per profile run; two in one report
                # means archived history or two projects, and the reader must
                # see where the yardstick changed.
                lis = "".join(
                    "<li>" + html.escape(o["run"]) + ": "
                    + html.escape(tr("judged against {set}").format(set=o["set"]))
                    + "</li>" for o in w["runs"])
                blocks.append(
                    "<div><b>" + html.escape(tr(
                        "Warning: these reports were not all judged against "
                        "the same limit set.")) + "</b> "
                    + html.escape(tr(
                        "The words in one column are not comparable with the "
                        "words in another where the limit set differs:"))
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
                "Colour accuracy: the ΔE00 across the patches, split so you can "
                "see the bulk of the chart (all patches and the best 95 %) apart "
                "from the few hardest patches (the worst 5 %). Each row is judged "
                "against the run's limit set.")) + "</li>"
            "<li>" + html.escape(tr(
                "Grey balance: how far each grey patch (R = G = B) sits from a "
                "neutral grey, ignoring lightness. ΔCh is the distance in a* and "
                "b* only. Computed from the chart's grey ramp when it has at "
                "least 8 steps from white to black.")) + "</li>"
            "<li>" + html.escape(tr(
                "Paper white & darkest black — the brightest and deepest patches "
                "(L*), a quick health check of your paper and maximum ink.")) + "</li>"
            "<li>" + html.escape(tr(
                "Cube corners — paper white, composite black and the six primary "
                "and secondary inks. These say as much about your inks as about "
                "the instrument.")) + "</li>"
            "</ul>"
            "<p><b>" + html.escape(tr("The five verdict words.")) + "</b> "
            + html.escape(tr(
                "A limit set is one column of the limits table: the numbers a "
                "report is judged against. Every row of the results ends in one "
                "of five verdict words. PASS: the measured value is within the limit for "
                "that row. FAIL: it is over the limit. COND (short for "
                "conditional): nothing failed, but the result comes with a "
                "documented exception. For a row it means the row is a "
                "recommendation rather than a requirement and the value is over "
                "it. For a column's Overall it means a recommendation was "
                "exceeded, or the set contains rows this chart could not supply, "
                "so the set as a whole was only partly checked. INFO: the number "
                "is shown for your information and nothing was judged from it. "
                "That happens when this limit set puts no limit on the row, "
                "when the sheet is a profiling measurement, which is never "
                "graded, when the row needs something about the print that was "
                "not recorded, and when you chose a report type that judges "
                "nothing; the note under the results names the rows in the "
                "last two cases. A column read as a drift check shows the word "
                "“drift” in every cell instead: it compares one measurement "
                "with another rather than with a limit. N-A "
                "(not applicable): the row does not apply here; the reason is shown "
                "when you point at the cell and is listed under the results, for "
                "example the chart has too few grey steps. "
                "A column's Overall word is PASS only when every row the set "
                "requires was checked and passed. The columns named after a "
                "standard hold that standard's published tolerance values applied "
                "to the chart you printed; they are not a test of the standard's "
                "own chart, so their Overall is COND at best, and this report "
                "never says that anything conforms to a standard.")) + "</p>"
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
                "Some of a chart's design colours can be brighter or more "
                "saturated than this printer and paper can physically produce; "
                "no profile can print them, however good it is. Where the "
                "report can tell (it asks the run's profile), it splits the "
                "colour-accuracy figures into two groups: “Within the "
                "profile's gamut”, the colours that were genuinely "
                "printable, the fair measure of accuracy, and “Beyond "
                "it”, the unreachable ones, whose distance describes the "
                "limit of the gamut, not a mistake of the profile. Every "
                "patch stays counted and visible; the verdict words "
                "judge the within-gamut figures.")) + "</p>"
            "<p>" + html.escape(tr(
                "The ΔE figures measure a whole chain in one number: the "
                "profile's conversion of each colour to printer values, the "
                "printer's behaviour on the day, and your instrument's own "
                "small uncertainty. A rising number tells you something in "
                "that chain has moved — not, by itself, which part. To look "
                "at the profile alone, use Check & Refine ▸ “Analyse Profile "
                "Quality”: it checks how well the profile describes your "
                "printer, using the measurement it was built from.")) + "</p>"
            "<p>" + html.escape(tr(
                "Compare a profile with itself over time — that is what "
                "these figures are for. They are not a fair way to rank "
                "papers or printers against each other, because the averages "
                "cover only the colours each profile can actually print, and "
                "that set differs with every paper: a glossy paper keeps "
                "more of the difficult, saturated colours than a matte one, "
                "so its average can look worse while it is printing "
                "better.")) + "</p>"
            "<p>" + html.escape(tr(
                "Because the design reference never changes, comparing dated "
                "reports of the same chart on the same printer is a clean, reliable "
                "signal of drift — ageing inks, a wandering printer, or an "
                "instrument going off. Save a report after each measurement to "
                "build that history. Screen and print colours here are "
                "approximate; the numbers come from your measurement file and are "
                "exact.")) + "</p>")
        # page_break: the gap batch (2026-08-13) could leave this headline
        # orphaned at a page bottom; a fixed break makes page 2 deterministic.
        return (_h2(tr("How to read this report"), page_break=True) + _gap()
                + "<table width='100%' cellpadding='12' cellspacing='0'>"
                f"<tr><td style='background:{_C['panel']}'>" + body
                + "</td></tr></table>")

    def _report_results_html(self, runs: list) -> str:
        """Report Results: the verdict grid, rows = every row the runs' limit
        sets judge, columns = dated runs (≤6 per table, continuing below).
        Cells are the five words (Knut, K-f): PASS green, FAIL red, COND amber,
        INFO and N-A faint. Under them the Overall word per column and what each
        column was judged against."""
        from workflow.compliance_sets import (COND, FAIL, N_A, PASS, ROW_BY_ID,
                                              ROWS, word_label)
        verd = {}
        for r in runs:
            rows, _rec = self._verdict_rows(r)
            verd[id(r)] = {(x.get("row_id") or x.get("key")): x for x in rows}
        present = [row.id for row in ROWS
                   if any(row.id in verd[id(r)] for r in runs)]

        def cell(r, rid):
            if _is_raw_drift(r):
                return (f"<td align='center' style='color:{_C['faint']}'>"
                        + html.escape(tr("drift")) + "</td>")
            x = verd[id(r)].get(rid)
            if x is None:
                return "<td align='center'>—</td>"
            word = x.get("word") or (PASS if x.get("pass") else FAIL)
            col = {PASS: _C["pass"], FAIL: _C["fail"], COND: _C["cond"]}.get(
                word, _C["faint"])
            weight = "bold" if word in (PASS, FAIL, COND) else "normal"
            tip = ""
            if word == N_A and x.get("reason"):
                tip = self._reason_sentence(x.get("reason"), r)
            elif word == COND:
                tip = tr("CONDITIONAL: over a value this limit set recommends "
                         "but does not require. Nothing failed; the exceedance "
                         "is documented.")
            title = f" title='{html.escape(tip)}'" if tip else ""
            return (f"<td align='center'{title} style='color:{col};"
                    f"font-weight:{weight}'>{html.escape(word_label(word))}</td>")

        def label_of(rid):
            row = ROW_BY_ID.get(rid)
            return tr(row.label) if row else _METRIC_LABELS.get(rid, lambda: rid)()

        row_getters = [(label_of(rid), (lambda r, rid=rid: cell(r, rid)))
                       for rid in present]
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
        if any(r.get("gamut_split") for r in runs):
            intro += " " + tr(
                "Where a sheet's colours are split into within / beyond the "
                "profile's gamut, the words judge the within-gamut "
                "figures; colours the profile could never print are not "
                "counted against it.")
        # One row for the column's one word, one saying what each column was
        # judged against, so a recorded verdict and a live one can never be
        # read as the same thing (#182).
        row_getters.append((tr("Overall"), self._summary_cell))
        row_getters.append((tr("Judged against"), self._thresholds_cell))
        note_css = f"color:{_C['faint']};font-size:10px;margin-top:2px"
        notes = ""
        if any(_is_raw_drift(r) for r in runs):
            notes += (
                f"<div style='{note_css}'>" + html.escape(tr(
                    "Columns marked “drift” are sheets printed raw, without "
                    "the profile: they are not expected to match the design "
                    "closely, so PASS and FAIL would be unfair to a "
                    "perfectly healthy printer. For those sheets the "
                    "detailed chapter shows how far the printer has moved "
                    "since the previous raw check instead.")) + "</div>")
        # APPENDED, never assigned: a report can hold a raw-drift sheet AND a
        # column with no recorded verdict, and the first draft of this block
        # overwrote the drift note whenever it did.
        if any(self._recorded(r) is None and not _is_raw_drift(r)
               and not r.get("_fresh") for r in runs):
            notes += (
                f"<div style='{note_css}'>" + html.escape(tr(
                    "A column judged against “not recorded” is not a "
                    "fault, and nothing is missing from it. That report was "
                    "saved by a version of ChromIQ that did not yet keep the "
                    "verdict together with the measurements, so its words "
                    "are worked out now, against the run's limit set, and "
                    "changing that run's limits will change them. Every "
                    "report saved from now on keeps the verdict it was given "
                    "on the day.")) + "</div>")
        if any(r.get("_fresh") for r in runs):
            notes += (
                f"<div style='{note_css}'>" + html.escape(tr(
                    "A column marked “(not saved)” is a measurement with no "
                    "saved report of its own; its words are worked out now "
                    "against the run's limit set.")) + "</div>")
        # KNUT'S 12b CONDITION, AND IT WAS NOT MET. He allowed INFO for a
        # profiling run's report on one condition: "the report OUTPUT must
        # explain this". The explanation existed, but only as the `title=`
        # attribute of the Overall cell, which is a hover tooltip: it is not in
        # the rendered text and an on-screen round confirmed it reaches NONE of
        # the four PDF pages, in English or German. A sentence a reader cannot
        # read explains nothing, so it belongs here, in the same footnote block
        # that already carries the other three explanations under this table.
        # THE STANDARD'S CAVEAT, IN THE OUTPUT, NOT IN A TOOLTIP. This is the
        # SECOND time in one day: the ungraded explanation below reached only a
        # `title=` attribute, was fixed, and then the caveat added for a saved
        # PASS under a standard's name went into the very same attribute, on the
        # graded path, which `_summary_cell` renders and the PDF does not carry.
        # A sentence a reader cannot read explains nothing, whichever branch
        # puts it there.
        from workflow.compliance_sets import (SUMMARY_REASONS, STANDARD_CAVEAT,
                                              applies_a_standard, summary_text)
        from workflow.measurement_report import recorded_compliance
        _standard_cols = [
            r for r in runs
            if not _is_raw_drift(r)
            and applies_a_standard(
                str((recorded_compliance(r) or {}).get("set_id", "") or "")
                or getattr(self._limits_for(r), "set_id", ""),
                str((recorded_compliance(r) or {}).get("set_label", "") or ""))
        ]
        if _standard_cols:
            notes += (f"<div style='{note_css}'>"
                      + html.escape(tr(STANDARD_CAVEAT)) + "</div>")
        # EVERY reason that has to be read, not the one that existed first.
        # This selection is by EXACT EQUALITY on the sentence, and the comment
        # in `_column_summary` records that a longer string silently dropped
        # Knut's 12b explanation once already. A second reason was exactly that
        # fault again; a THIRD, `nothing_checked`, was found by an adversarial
        # round reading the saved PDFs back, so the question is asked of the
        # module that owns all of them rather than listed here.
        # …AND THE CODE SAID "EVERY" WHILE PRINTING ONE. `next(...)` took the
        # first column that needed a sentence and every other column went
        # silent, which widening the rule from two reasons to three made more
        # likely rather than less. Driven with three columns: a profiling sheet
        # and two dated verifications, all as a Printing record. Only the
        # profiling sheet's sentence printed, so the document told the reader
        # its verification sheets were "measured to build a profile rather than
        # to check one" — the sentence `record_type` exists because that would
        # be false. On a Grey and tone check the two columns read a bare N-A
        # with no explanation anywhere, which is the fault the footnote was
        # added to fix.
        #
        # Every DISTINCT sentence now, in column order. Distinct, because three
        # columns of the same kind need it said once.
        from workflow.compliance_sets import reason_needs_the_footnote
        _said: "list[str]" = []
        for r in runs:
            if _is_raw_drift(r):
                continue
            sm = self._column_summary(r)
            if not reason_needs_the_footnote(sm.reason):
                continue
            line = summary_text(sm)
            if line not in _said:
                _said.append(line)
        for line in _said:
            notes += (f"<div style='{note_css}'>"
                      + html.escape(line) + "</div>")
        # D25: what was not computed, and why, repeated in the report text.
        # …AND NEITHER OF THESE MAY SPEAK ON A TYPE THAT JUDGES NOTHING.
        # One note was guarded by type and the two beside it were not, which is
        # the first fault shape yet again. On a Printing record a chart with no
        # grey ramp printed, on one page: "You chose the Printing record, which
        # judges none of it", and under it "Not computed on this chart: … add
        # the missing patches to the chart in Create Chart to have it checked."
        # Under a type that checks nothing. The amber strip above the report
        # said the same, naming a limit set the document applies to nothing.
        seen: dict = {}
        if not self._ungraded_by_type():
            for r in runs:
                if _is_raw_drift(r):
                    continue
                for label, why in self._not_computed(r):
                    seen.setdefault((label, why), True)
        if seen:
            notes += (f"<div style='{note_css}'><b>" + html.escape(tr(
                "Not computed on this chart:")) + "</b> " + html.escape("; ".join(
                    f"{label} ({why})" for (label, why) in seen)) + " " + html.escape(tr(
                    "A row that was not computed says nothing about the "
                    "printer; add the missing patches to the chart in Create "
                    "Chart to have it checked.")) + "</div>")
        # …AND THE ROWS THAT WERE MEASURED AND NOT GRADED, WHICH ARE NOT THE
        # SAME THING AND MAY NOT SHARE THAT SENTENCE. The chart has these
        # patches; what it lacks is whatever the grading needed. The heading
        # says "on at least one measurement" because a report can hold several
        # and one row can be ungraded on one and missing on another.
        graded_note: dict = {}
        for r in runs:
            if _is_raw_drift(r):
                continue
            for label, why in self._measured_not_graded(r):
                graded_note.setdefault((label, why), True)
        if graded_note:
            notes += (f"<div style='{note_css}'><b>" + html.escape(tr(
                "Measured but not graded, on at least one measurement:"))
                + "</b> " + html.escape("; ".join(
                    f"{label} ({why})" for (label, why) in graded_note))
                + " " + html.escape(tr(
                    "The measurement is there; it is shown for information "
                    "because the report cannot judge it under these "
                    "conditions.")) + "</div>")
        return (_h2(tr("Report Results"), page_break=True) + _gap()
                + f"<div style='color:{_C['dim']};margin-bottom:4px'>" + html.escape(intro)
                + "</div>" + _gap()
                + self._chunked_metric_tables(runs, row_getters)
                + notes)

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

        row_getters = []
        # Knut's layout (2026-08-10): datasets stay side-by-side as columns;
        # the in/out-of-gamut split arrives as row BLOCKS one after another —
        # within, beyond, then all patches — so comparing two dates inside any
        # block stays a horizontal glance. Runs without a split show dashes in
        # the split blocks; without any split anywhere the table is unchanged.
        if any(r.get("gamut_split") for r in runs):
            gs = lambda r: (r.get("gamut_split") or {})

            def part(which, key):
                return lambda r: (gs(r).get(which) or {}).get(key)

            row_getters.append((tr("Within the profile's gamut"), None))
            row_getters.append((tr("Patches"),
                                num(lambda r: gs(r).get("n_in"), 0)))
            row_getters += [(_METRIC_LABELS[k](), num(part("de00_in", k), 2))
                            for k in ("avg_all", "avg_low95", "avg_high5",
                                      "max_all", "max_low95")]
            row_getters.append((tr("Beyond the profile's gamut"), None))
            row_getters.append((tr("Patches"),
                                num(lambda r: gs(r).get("n_out"), 0)))
            row_getters += [(_METRIC_LABELS[k](), num(part("de00_out", k), 2))
                            for k in ("avg_all", "avg_low95", "avg_high5",
                                      "max_all", "max_low95")]
            row_getters.append((tr("All patches together"), None))
        row_getters += [(_METRIC_LABELS[k](), num((lambda r, k=k: de(r).get(k)), 2))
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
                + _gap() + self._chunked_metric_tables(runs, row_getters))

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
        _C = dict(_LIGHT_REPORT if for_pdf else _REPORTS.get(
            resolve_mode(self._settings.get("appearance", "auto")),
            _LIGHT_REPORT))
        if not runs:
            return self._empty_html()
        # A plain "Created: …" line — at the top of the window body, and under
        # the title + spectrum line in the PDF (Knut). The profile line that used
        # to be here is dropped; Report Scope already lists it.
        when = html.escape((created or self._created).replace("T", " "))
        created_line = ("<div style='margin:2px 0 0'>"
                        + html.escape(tr("Created:")) + " " + when + "</div>")
        # WHICH DOCUMENT THIS IS. A two-page report about the neutral axis,
        # handed to a reader with no line saying so, is indistinguishable from
        # a full report that lost most of its rows.
        #
        # Not on T2, and that is deliberate: T2 is defined as today's report
        # unchanged, and a line naming it would be a change every existing user
        # sees without having chosen anything.
        #
        # AND ONLY ON A TYPE CHROMIQ CAN ACTUALLY PRODUCE. A run carrying a
        # type this build cannot make renders as today's report, so naming it
        # would put "Colour summary (one page)" at the head of the full report:
        # worse than saying nothing, because it is a claim rather than a
        # silence. Caught by the ratchet, on three types at once.
        from workflow.measurement_report import (REPORT_TYPE_FULL,
                                                 REPORT_TYPE_SUMMARY,
                                                 report_type_is_built,
                                                 report_type_name)
        _tid = self._report_type_now()
        # THE TITLE HAS TO BE ABOUT THE SAME SHEET AS THE PAGE UNDER IT, so the
        # one-page summary narrows the list HERE, before the title, the PDF
        # file name and `_report_kind` are worked out from it, and not only at
        # the call that builds the body. Disabling the tick box does not untick
        # it, so a user who ticked "Show all measurement runs" under another
        # type and then chose this one still arrives with the whole history.
        _one_page = _tid == REPORT_TYPE_SUMMARY and report_type_is_built(_tid)
        if _one_page:
            runs = self._one_measurement(runs)
        if _tid != REPORT_TYPE_FULL and report_type_is_built(_tid):
            created_line += ("<div style='margin:2px 0 0;font-weight:bold'>"
                             + html.escape(tr("Report type:")) + " "
                             + html.escape(tr(report_type_name(_tid)))
                             + "</div>")
        if for_pdf:
            head = (f"<div style='font-size:22px;font-weight:bold;color:{_C["head"]}'>"
                    + html.escape(self._report_title(runs)) + "</div>"
                    + _colour_line_html() + created_line + "<br>")
        else:
            head = created_line
        # T1 IS A DIFFERENT DOCUMENT, not the full one with rows removed. It
        # is one page to print and hand over with a job (Knut), so it branches
        # here rather than filtering below: no "How to read" essay, no trend
        # charts, no comparison table, no opt-in detail.
        if _one_page:
            family = QApplication.font().family().replace("'", "")
            return (f"<div style=\"font-family:'{family}';color:{_C['text']};"
                    f"font-size:12px\">"
                    + head + self._one_page_html(runs) + "</div>")
        parts = [head, self._scope_html(runs), self._how_to_read_html(),
                 self._report_results_html(runs)]
        if for_pdf and charts_html:
            parts.append(
                _h2(tr("Trend over time (this printer)"), page_break=True) + _gap()
                + f"<div style='color:{_C['dim']};margin-bottom:6px'>" + html.escape(tr(
                    "A rising average or shifting white/black/colour over time "
                    "points to ageing inks, printer drift, or instrument drift."))
                + "</div>" + _gap() + charts_html)
        if len(runs) > 1:
            parts.append(self._comparison_table_html(runs))
        if getattr(self, "_detail_check", None) is not None \
                and self._detail_check.isChecked():
            parts.append(self._detailed_section_html(runs))
        # The app's own font family, not the literal "sans-serif": Qt's rich
        # text reads that as a family NAME, warns "missing font family
        # Sans-serif" on the console (Sebastian, 2026-08-13), and substitutes
        # anyway — naming the running application's family gets the same look
        # with no lookup and no warning.
        family = QApplication.font().family().replace("'", "")
        return (f"<div style=\"font-family:'{family}';color:{_C['text']};"
                f"font-size:12px\">"
                + "".join(parts) + "</div>")

    def _one_measurement(self, runs: list) -> list:
        """The ONE measurement a one-page summary is about.

        T1 is the page that goes out with a job, so it describes the sheet that
        was printed for that job. `_runs_for_report` hands back the whole
        history when "Show all measurement runs" is ticked, and `_one_page_html`
        read `runs[0]` from it — the OLDEST measurement — while the Report Scope
        above it said "2 verification runs" and gave the date range of both.
        Measured on two dated verifications of one run: one verdict, one set of
        example colours and one set of cube corners, all from a sheet printed
        nine days before the one the window was opened on, with nothing on the
        page saying so.

        So the page takes the measurement the window is ON, and the scope is
        given the same single item, so the heading and the numbers under it are
        about the same sheet. The tick box is disabled while T1 is chosen
        rather than left to do nothing (`_sync_type_combo`).
        """
        if len(runs) <= 1:
            return list(runs)
        key = self._run_key(self._report) if self._report else None
        if key:
            for r in runs:
                if self._run_key(r) == key:
                    return [r]
        # No match: the history is oldest-first, so the sheet in hand is the
        # last one, never the first.
        return runs[-1:]

    def _one_page_html(self, runs: list) -> str:
        """T1, "Colour summary (one page)": the page that goes with the job.

        **Knut** described it as the report handed to a customer with the print
        they ordered: *"a very short overview of accuracy of a selection of
        colors, with some statistics, that can be printed out for every job."*

        So it carries the run's own description, one line of statistics, the
        sixteen example colours the chart itself supplied, the cube corners,
        and the promise that governs every report ChromIQ writes. It carries no
        customer or job name, which he ruled out for today, and no essay.
        """
        from workflow.compliance_sets import summary_text, word_label
        from workflow.measurement_report import SUMMARY_PATCH_COUNT
        r = runs[0]
        out = [self._scope_html(runs)]

        # -- the one line of numbers a reader acts on
        de = r.get("de00") or {}
        sm = self._column_summary(r)
        bits = []
        if de.get("avg_all") is not None:
            bits.append(tr("Average difference {v}").format(
                v=_fmt(de.get("avg_all"), 2)))
        if de.get("max_all") is not None:
            bits.append(tr("Largest {v}").format(v=_fmt(de.get("max_all"), 2)))
        if de.get("n"):
            n = int(de["n"])
            # Singular and plural in full, never "(s)" (CLAUDE.md).
            bits.append(tr("{n} patch").format(n=n) if n == 1
                        else tr("{n} patches").format(n=n))
        out.append(_h2(tr("Result")) + _gap()
                   + "<div><b>" + html.escape(word_label(sm.word)) + "</b>"
                   + (" · " + html.escape("; ".join(bits)) if bits else "")
                   + "</div>"
                   + f"<div style='color:{_C['dim']};margin-top:2px'>"
                   + html.escape(summary_text(sm)) + "</div>")

        # -- the colours, from the chart that was measured
        picked = r.get("summary_patches") or []
        if picked:
            out.append(_h2(tr("Example colours")) + _gap()
                       + f"<div style='color:{_C['dim']};margin-bottom:4px'>"
                       + html.escape(tr(
                           "{count} colours from the chart that was measured, "
                           "spread across what this printer can make. Left: "
                           "what the chart asked for. Right: what came back."
                       ).format(count=len(picked))) + "</div>"
                       + self._swatch_table_html(picked))
        else:
            # A report saved before the example colours existed carries none,
            # and says so rather than showing an empty frame.
            out.append(_h2(tr("Example colours")) + _gap()
                       + f"<div style='color:{_C['dim']}'>" + html.escape(tr(
                           "This measurement was saved before ChromIQ chose "
                           "example colours. Measure the chart again to have "
                           "them.")) + "</div>")

        corners = [c for c in (r.get("corners") or []) if c.get("present")]
        if corners:
            out.append(_h2(tr("Cube corners")) + _gap()
                       + self._swatch_table_html(corners))

        out.append(f"<div style='color:{_C['dim']};margin-top:10px'>"
                   + html.escape(tr(
                       "ChromIQ measures against published values; it does "
                       "not certify. This page says what was measured and "
                       "what it was compared against."))
                   + "</div>")
        return "".join(out)

    def _swatch_table_html(self, rows: list) -> str:
        """A patch per row: what was asked for, what came back, and how far
        apart they are. Two swatches side by side, because a number alone is
        not what a person hands to a customer."""
        cells = []
        for x in rows:
            name = x.get("name") or x.get("loc") or ""
            exp, got = x.get("expected_hex", ""), x.get(
                "measured_hex") or x.get("hex", "")
            d = x.get("de")
            cells.append(
                "<tr>"
                f"<td style='padding:1px 8px 1px 0'>{html.escape(str(name))}</td>"
                f"<td style='padding-right:10px'>{_swatch(exp)}</td>"
                f"<td>{_swatch(got)}</td>"
                f"<td align='right' style='padding-left:10px'>"
                f"{_fmt(d, 2)}</td></tr>")
        return ("<table cellspacing='0' cellpadding='0' "
                "style='margin:2px 0 6px'>"
                "<tr><th align='left' style='padding-right:8px'>"
                + html.escape(tr("Patch")) + "</th>"
                # THE TWO SWATCH COLUMNS NEED AIR. Photographed on screen:
                # "Asked for" ran straight into "Measured" with no gap, so the
                # header read as one word and the two blocks below it as one
                # block.
                "<th align='left' style='padding-right:10px'>"
                + html.escape(tr("Asked for")) + "</th>"
                "<th align='left' style='padding-right:10px'>"
                + html.escape(tr("Measured")) + "</th>"
                "<th align='right' style='padding-left:10px'>"
                + html.escape(tr("ΔE00")) + "</th></tr>"
                + "".join(cells) + "</table>")

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
        _C = dict(_REPORTS.get(
            resolve_mode(self._settings.get("appearance", "auto")),
            _LIGHT_REPORT))

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
        ref_src = r.get("reference_source")
        if ref_src in ("colorimetric", "colorimetric-missing"):
            # A FROM PROFILE GAMUT chart carries the profile from the moment
            # it is built — "no profile took part" was false for it, and its
            # Raw print is exactly right (Knut, 2026-08-11). This branch must
            # come before the raw/through ones, which only see the record.
            if ref_src == "colorimetric":
                rows.append((tr("What this measured"), tr(
                    "how accurate this profile is — this chart was built only "
                    "from colours the profile promised it can print, and "
                    "every figure compares a patch with that promise"), False))
            else:
                rows.append((tr("What this measured"), tr(
                    "this chart was built from the profile's own gamut and "
                    "was meant to measure its accuracy — but the stored "
                    "targets are missing, so no colour-accuracy figures are "
                    "shown"), True))
            rows.append((tr("Printed"), tr(
                "as it is (Raw) — the profile is already inside this chart "
                "from the moment it was made, so printing it unchanged is "
                "exactly right; nothing was skipped"), False))
        elif colour == "through-profile" and printing.get("route") == "external-cm":
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
                "as measured — no white adjustment: every difference "
                "counts, the paper's own tone included. (This is a way of "
                "comparing, not a rendering intent — a raw print has no "
                "intent at all.)"), False))
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
            split = r.get("gamut_split")
            d_in = (split or {}).get("de00_in") or {}
            d_out = (split or {}).get("de00_out") or {}
            # With a split the Result judges the WITHIN-gamut figure — the
            # beyond-gamut colours were never printable, so their distance is
            # a property of the gamut, not an error of the profile (Knut,
            # 2026-08-10). In the detailed chapter the groups may sit
            # side-by-side as columns (his layout ruling).
            #
            # #182: a report saved with its verdict shows THAT verdict and the
            # thresholds it was given, whatever the spin boxes say today.
            rows, recorded = self._verdict_rows(r)
            raw_drift = _is_raw_drift(r)
            if raw_drift:
                # A drift check is never graded against the profile
                # thresholds — the drift paragraph below carries the verdict.
                for row in rows:
                    row["pass"] = None
                    row["threshold"] = None
                    row["word"] = None
            thb = f"border-bottom:1.5px solid {_C['rule']}"
            cols = ([tr("Within gamut"), tr("Beyond it"), tr("All patches")]
                    if split else [tr("Measured ΔE00")])
            head = (f"<tr style='color:{_C['faint']}'>"
                    f"<th align='left' style='{thb}'>"
                    + html.escape(tr("Metric")) + "</th>"
                    + "".join(f"<th align='right' style='{thb}'>"
                              + html.escape(c) + "</th>" for c in cols)
                    + f"<th align='right' style='{thb}'>"
                    + html.escape(tr("Limit")) + "</th>"
                    f"<th align='center' style='{thb}'>"
                    + html.escape(tr("Result")) + "</th></tr>")
            trs = [head]

            from workflow.compliance_sets import (COND, FAIL, PASS, ROW_BY_ID,
                                                  word_label)

            def row_html(i, label, values, threshold, word, should=False,
                         bold_first=True, tip=""):
                bg = f" style='background:{self._ZEBRA_BG}'" if i % 2 == 1 else ""
                if word is None:
                    res = "—"
                else:
                    col = {PASS: _C["pass"], FAIL: _C["fail"],
                           COND: _C["cond"]}.get(word, _C["faint"])
                    weight = "bold" if word in (PASS, FAIL, COND) else "normal"
                    title = f" title='{html.escape(tip)}'" if tip else ""
                    res = (f"<span{title} style='color:{col};font-weight:{weight}'>"
                           + html.escape(word_label(word)) + "</span>")
                tds = "".join(
                    "<td align='right'>" + ("<b>" if bold_first and j == 0 else "")
                    + _fmt(v) + ("</b>" if bold_first and j == 0 else "") + "</td>"
                    for j, v in enumerate(values))
                thr = "—" if threshold is None else (
                    f"({_fmt(threshold)})" if should else _fmt(threshold))
                # F9 / CS Q12: a FAIL whose two-decimal value reads like the
                # limit shows three decimals, so a failing value never looks
                # like a passing one
                if (word == FAIL and threshold is not None and values
                        and isinstance(values[0], (int, float))
                        and _fmt(values[0]) == _fmt(threshold)):
                    values = list(values)
                    values[0] = f"{values[0]:.3f}"
                return (f"<tr{bg}><td style='padding-right:14px'>{html.escape(label)}</td>"
                        + tds +
                        f"<td align='right'>{thr}</td>"
                        f"<td align='center'>{res}</td></tr>")

            for i, row in enumerate(rows):
                k = row.get("key")
                rid = row.get("row_id") or k
                rowdef = ROW_BY_ID.get(rid)
                # one vocabulary with the results grid (N5): the row's label
                label = (tr(rowdef.label) if rowdef
                         else (_METRIC_LABELS[k]() if k in _METRIC_LABELS else str(rid)))
                if split and k in de:
                    values = [d_in.get(k), d_out.get(k), de.get(k)]
                elif split:
                    values = [row.get("value"), None, None]
                else:
                    values = [row.get("value")]
                word = row.get("word")
                if word is None and row.get("pass") is not None:
                    word = PASS if row["pass"] else FAIL
                tip = (self._reason_sentence(row.get("reason"), r)
                       if row.get("reason") else "")
                trs.append(row_html(i, label, values, row.get("threshold"), word,
                                    should=bool(row.get("should")), tip=tip))
            # Spread is reported for completeness but carries no threshold (Knut).
            trs.append(row_html(
                len(rows), _METRIC_LABELS["std"](),
                ([d_in.get("std"), d_out.get("std"), de.get("std")]
                 if split else [de.get("std")]), None, None))
            device_ref = r.get("reference_source") == "device"
            # Both cases compare against the chart's DESIGN — either straight from
            # the .ti2, or reconstructed from the device values — so the heading is
            # the same; the note below explains the reconstruction (Knut).
            parts.append(_h3(tr("Colour accuracy (ΔE00 vs the chart's design)")))
            parts.append("<table cellpadding='5' cellspacing='0' "
                         "style='border-collapse:collapse;font-size:11px'>"
                         + "".join(trs) + "</table>")
            if not raw_drift:
                parts.append(
                    f"<p style='color:{_C['faint']};font-size:10px'>"
                    + html.escape(self._verdict_provenance(r, recorded))
                    + "</p>")
            if raw_drift:
                rd = r.get("raw_drift") or {}
                if rd.get("baseline"):
                    drift_txt = tr(
                        "This sheet was printed raw, without the profile — "
                        "so it is a drift check, and this is the first one: "
                        "it becomes the baseline. From your next raw check "
                        "on, the report will show here how far the printer "
                        "has moved since this sheet.")
                elif rd.get("incomparable"):
                    drift_txt = tr(
                        "This sheet was printed raw, without the profile — a "
                        "drift check. The previous raw check used a "
                        "different chart, so print-to-print drift cannot be "
                        "measured for this pair; the next raw check of THIS "
                        "chart will start a fresh comparison.")
                elif rd.get("avg") is not None:
                    drift_txt = tr(
                        "Drift since the previous raw check ({prev}): "
                        "average {avg} ΔE00, maximum {max}: this print "
                        "measured against that print, patch by patch, "
                        "{n} patches. Small numbers mean your printer still "
                        "behaves as it did then; growing numbers mean drift, "
                        "worth re-profiling when they matter to you. "
                        "(PASS and FAIL against the run's limit set are not "
                        "shown here: a raw sheet is not expected to match "
                        "the design closely, so it would fail even a "
                        "perfectly healthy printer.)").format(
                            prev=str(rd.get("prev", ""))[:16].replace("T", " "),
                            avg=_fmt(rd.get("avg")), max=_fmt(rd.get("max")),
                            n=rd.get("n"))
                else:
                    drift_txt = tr(
                        "This sheet was printed raw, without the profile — a "
                        "drift check. Its ΔE figures above describe distance "
                        "from the design, and what matters is how they "
                        "change between dated checks, not their size.")
                parts.append(
                    f"<p style='color:{_C['faint']};font-size:10px'>"
                    + html.escape(drift_txt) + "</p>")
            if split:
                parts.append(
                    f"<p style='color:{_C['faint']};font-size:10px'>" + html.escape(tr(
                        "Within what the profile ({profile}) can print: {n} of "
                        "this sheet's colours ({pct} %); beyond it: {m}. The Result "
                        "judges the within-gamut figures — a colour beyond "
                        "the gamut was never printable, so its distance "
                        "describes the gamut's limit, not a mistake of the "
                        "profile. Those patches stay visible in their own "
                        "column, and how steady they are from check to check "
                        "is a drift signal.").format(
                            n=split.get("n_in"), m=split.get("n_out"),
                            pct=round(100 * (split.get("n_in") or 0)
                                      / max((split.get("n_in") or 0)
                                            + (split.get("n_out") or 0), 1)),
                            profile=split.get("profile", ""))) + "</p>")
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
                exp = _swatch(c.get("expected_hex", ""))
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
