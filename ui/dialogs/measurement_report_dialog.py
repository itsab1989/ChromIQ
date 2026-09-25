"""Measurement report viewer (Knut): accuracy statistics for a measured chart
and drift comparison over time.

Pick a measurement (.ti3); the dialog shows how the reading compares to the
chart's expected colours — mean / median / worst / spread ΔE00, the worst
patches with their colours, and the paper white and darkest black. "Save this
report" keeps a timestamped copy next to the chart so later measurements of
the same chart can be compared, revealing ink / printer / instrument drift.
"""
from __future__ import annotations

from contextlib import contextmanager

import html
import json
import math
import os
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
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

#: The entry at the TOP of "Report shown" that is not a report yet (B8-388).
#: Knut, 2026-09-18: *"In the 'Measurement Report' window, when 'Report shown'
#: is set to 'New report....', all default values shall be loaded on the
#: settings, which then can be changed by a user. The default values are
#: fetched from the preferences->reports tab."* and, on where it sits and what
#: opens selected: *"The default when loading the Measurement Report window is
#: the latest report created. 'New report...' should be at the top of the list
#: in the pulldown."*
#:
#: It is deliberately NOT a `document_key`: no file can ever answer to it, so
#: `_saved_documents`, Delete and the label rules are untouched by it.
NEW_REPORT_KEY = "new:"


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


def _corner_ideal_hex(code: str) -> str:
    """The IDEAL colour of one cube corner, for a chart that has no patch at it.

    **A CORNER THE REPORT HAS JUST CALLED MISSING STILL HAD A COLOUR, A
    LOCATION AND A DeltaE00, AND ALL THREE BELONGED TO SOMETHING ELSE**
    (B8-290, reported by the design authority on a demo project).
    `build_report` finds each corner by taking the NEAREST patch in device RGB
    and then asks whether that patch is actually at the corner
    (`CORNER_PRESENT_TOL`, 12 device units). When it is not, `present` is False
    and the row is marked "(missing)" -- but every other field on it still
    described the stand-in. On his sheet Red and Blue both landed on patch 14,
    a neutral grey, so the table printed a grey swatch and 2.46 twice under two
    different ink names, and Cyan printed a green one.

    His remedy, and it is the one implemented: *"When the colors are missing,
    the expected should still show the ideal cube colour, the measured and the
    DeltaE columns could show only a dash to indicate it is not present or
    measured."*

    So the Expected swatch comes from here instead of from the stand-in's
    reference. It is the corner's own device value read as sRGB, derived from
    `CUBE_CORNERS` rather than written out again, so a change to that table
    cannot leave this one behind. Device 0..100 is not sRGB in any colorimetric
    sense, and it does not have to be: this swatch names WHICH corner the row
    is about, exactly as `_CORNER_LINE` does for the trend, and the honest
    colorimetric answer for a patch that was never printed is the dash beside
    it.
    """
    from workflow.measurement_report import CUBE_CORNERS
    for name, rgb in CUBE_CORNERS:
        if name == code:
            return "#" + "".join(
                f"{max(0, min(255, int(round(v * 255.0 / 100.0)))):02x}"
                for v in rgb)
    return ""

# The colour-accuracy metrics (Knut's revised set), keyed by report ``de00``
# field. Labels are lazy so tr() runs under the active language. ``_METRIC_LABELS``
# covers all six (Spread included); ``_ACCURACY_ROW_KEYS`` are the five that carry
# a Pass/Fail verdict, in display order; the trend chart plots those five.
#
# **ONE NAME PER METRIC, AND IT LIVES IN `compliance_sets.ROWS` (K28, #182
# 5795087247).** Knut: *"all metrics in report, in graphs and in Report Limits
# window, and in all help texts, use the same label/name and refer to these
# with those names so that there is no confusion."* This table used to hold a
# second vocabulary ("Average ΔE, all patches") beside the grid's first ("All
# patches, average"), the graph a third ("Average, all patches (ΔE00)"), and a
# within-gamut graph a fourth ("all judged patches"). Now every one of them is
# the row's own label, looked up through `_ROW_ID_OF`, so a sixth spelling
# cannot be added here without a test failing
# (`tests/test_k28b_one_vocabulary.py`). Spread is not a row of the limits
# table (it never has a limit), so it keeps its own name.
def _row_label_of_key(key: str):
    """The lazy label of the ROWS row behind one ``de00`` key."""
    def _label() -> str:
        from workflow.compliance_sets import ROW_BY_ID
        return tr(ROW_BY_ID[_ROW_ID_OF[key]].label)
    return _label


_ACCURACY_ROW_KEYS = ("avg_all", "avg_low95", "avg_high5", "max_all", "max_low95")
#: The rows a within-gamut split feeds: the five colour-accuracy rows
#: (`graded_de00`) and the two evenness rows (`evenness_block(only_ids=...)`).
#: Every other row counts every patch of its population, so a sentence saying
#: its words judge within-gamut figures would be false (K28, item 1).
WITHIN_GAMUT_ROWS = frozenset({
    "all_de00_avg", "best95_de00_avg", "worst5_de00_avg", "all_de00_max",
    "all_de00_p95", "uniformity_sd", "uniformity_de00_max_from_mean"})
_METRIC_LABELS = {k: _row_label_of_key(k) for k in _ACCURACY_ROW_KEYS}
# K31 (Knut, #182 5801677743, version 1): the unit and the patches in the
# name, as every limited figure carries them.
_METRIC_LABELS["std"] = lambda: tr("Standard deviation ΔE00, all patches")


def _report_across_projects_help() -> str:
    """Where a report of several projects is saved (#182 K30, Knut
    5798461562), for the help of "Report shown" and of the measurement list.
    ONE sentence, so the two helps cannot disagree."""
    return tr(
        "A report of measurements from more than one project is saved in the "
        "reports/ folder beside the projects when they are side by side in "
        "one folder. Otherwise it is always saved in the reports/ folder of "
        "your ChromIQ folder (~/ChromIQ, or your custom output folder from "
        "Settings), whichever folders the projects are in.")


def _a_calibration_with_saved_reports(ti3: "Path") -> bool:
    """Whether *ti3* is a project's calibration measurement that is not on
    disk now while its `cal/reports/` still holds reports (K30, F5)."""
    from workflow.measurement_report import is_calibration_dir
    try:
        return (not ti3.exists() and is_calibration_dir(ti3.parent)
                and any((ti3.parent / "reports").glob("report_*.json")))
    except OSError:
        return False


def _project_target_name(root: "Path") -> str:
    """A project's name as its ``project.json`` records it, else its folder
    name (#182 K30)."""
    try:
        doc = json.loads((Path(root) / "project.json").read_text(
            encoding="utf-8"))
        name = str(doc.get("target_name") or "").strip()
    except (OSError, ValueError, AttributeError):
        name = ""
    return name or Path(root).name


def _series_is_within_gamut(series: list) -> bool:
    """Whether any date of a trend series plots within-gamut figures."""
    return any(pt.get("de00_population") == "in_gamut"
               for pt in (series or []))

#: What a report written BEFORE the five-metric vocabulary calls the same
#: number. `_de00_block` writes both spellings on every report to this day and
#: says why: *"aliases kept for the trend series (report_trend reads
#: mean/max/p95)"* — and `report_trend` does copy them into the point. Nothing
#: then read them, so a report made by an older ChromIQ contributed no value to
#: any of the five lines, `_TrendChart.set_data` dropped the point entirely, and
#: the chart said *"A trend graph needs at least two measurement runs. Add
#: another measurement — or … tick 'Show all measurement runs' above"* with two
#: measurements listed, both ticked, and that box already on. Both instructions
#: were already done; the sentence was simply false.
#:
#: Only the two that are the SAME arithmetic, proved from `_de00_block`, where
#: the new key and the alias are written from one expression:
#: ``"avg_all": round(float(a.mean()), 3)`` / ``"mean": round(float(a.mean()), 3)``
#: and the same for ``max_all`` / ``max``. ``max_low95`` is deliberately NOT
#: mapped from the old ``p95``: today's is the nearest-rank maximum of the best
#: 95 % and stamps ``p95_rule`` to say so, and a report old enough to lack the
#: new key is also old enough to have recorded no rule at all. A line that
#: cannot be trusted is left with no point rather than given a wrong one.
_ACCURACY_ALIAS = {"avg_all": "mean", "max_all": "max"}


def _accuracy_value(pt: dict, key: str):
    """One accuracy metric of one trend point, in this report's own spelling."""
    v = pt.get(key)
    if v is None:
        v = pt.get(_ACCURACY_ALIAS.get(key, ""))
    return v
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

#: **THE JUDGED-METRIC TREND TABS (#182 K20/K21).** Knut, 5787117741: *"each
#: group show maximum two metrics with their own independent threshold level
#: line, no more... and that each metric within a group are related
#: metrics"*; 5787380408 adds "Paper white, diff". A tab is shown, and printed,
#: only when one of its rows was judged for the document (`_trend_plan`).
#:
#: ``(key, title, ((row_id, line word, colour), ...))``, lazy so tr() runs in
#: the active language. The legend is the row's own label from ``ROWS``, so
#: the graph names a metric exactly as the results table does; the WORD is the
#: short name of its dotted line, which has to fit the 40 px axis margin.
#:
#: The control strip plotted its average and its 95th percentile, not its
#: maximum: the 95th percentile is the same kind of number without jumping on
#: one misread patch. Since K47 the maximum is plotted too, while it is
#: judged, because ISO 12647-7 judges it and a judged row with no line is
#: what Knut ruled out.
#:
#: **K47 (Knut, #182 5840152058): EVERY LIMITED ROW HAS A DATA LINE.** *"If
#: the Control strip graph has data-lines in the graph, where each have their
#: own threshold (or maybe even uses the same threshold) then the graph shall
#: have both dotted horizontal lines ... and a sentence below it for the
#: threshold."* So the strip's maximum joins its tab (ISO 12647-7 judges the
#: maximum, not the 95th percentile, and the tab drew only the average), and
#: is the one tab that can hold three rows: a Custom set limits all three.
#: The rule of 5787117741 still decides everything else: a row is plotted
#: only while it is judged, and every row a set can limit now has a tab.
#: The two solid-colour rows carry different units, so each has its own.
_TREND_GROUPS = (
    # K31 (version 1): every tab name carries its unit.
    ("paper_diff", lambda: tr("Paper white difference (ΔE00)"), (
        ("substrate_de00_max", lambda: tr("Max"), "#8a8a8a"),)),
    # K47: the two rows judged on the solid ink corners, after Cube corners.
    ("solids", lambda: tr("Solid colours (ΔE00)"), (
        ("solids_de00_max", lambda: tr("Max"), "#c9a227"),)),
    ("solid_hue", lambda: tr("Hue of the solids (ΔH*ab)"), (
        ("cmy_solids_dhab_max", lambda: tr("Max"), "#b36bd6"),)),
    ("grey", lambda: tr("Grey balance (ΔCh)"), (
        ("grey_balance_neutral_ramp_avg", lambda: tr("Avg"), "#56d6a5"),
        ("grey_balance_neutral_ramp_max", lambda: tr("Max"), "#e0574b"))),
    ("tone", lambda: tr("Tone ramps 30 to 70 % (ΔL*)"), (
        ("ramps_30_70_dl_max", lambda: tr("Max"), "#37bcd6"),)),
    ("strip", lambda: tr("Control strip (ΔE00)"), (
        ("control_strip_de00_avg", lambda: tr("Avg"), "#56d6a5"),
        ("control_strip_de00_p95", lambda: tr("P95"), "#9f82ff"),
        # K47: the maximum, the row ISO 12647-7 judges.
        ("control_strip_de00_max", lambda: tr("Max"), "#e0574b"))),
    # K47: the two averages over selected patches of the chart.
    ("gamut_edge", lambda: tr("Outer and surface gamut (ΔE00)"), (
        ("outer_gamut_226_de00_avg", lambda: tr("Outer"), "#e0864b"),
        ("surface_gamut_de00_avg", lambda: tr("Shell"), "#37bcd6"))),
    ("repeat", lambda: tr("Repeatability (ΔE00)"), (
        ("repeat_patches_de00_max", lambda: tr("Sheet"), "#37bcd6"),
        ("repeat_measurement_de00_max", lambda: tr("Again"), "#e0864b"))),
    ("evenness", lambda: tr("Evenness (ΔE00)"), (
        # K31: "Pairs" was the one unclear limit-line word.
        ("uniformity_sd", lambda: tr("Areas"), "#e0574b"),
        ("uniformity_de00_max_from_mean", lambda: tr("Mean"), "#37bcd6"))),
)


def _trend_row_value(pt: dict, row_id: str, limit=None):
    """One judged row's value in a trend point, or None.

    An evenness value whose own noise is not below *limit* is None: the
    results table reads N-A for it (`evenness_withheld`), and a point drawn
    against the same limit line would say what the table refuses to."""
    v = (pt.get("rows") or {}).get(row_id)
    if v is None or limit is None:
        return v
    from workflow.compliance_sets import Limit
    from workflow.measurement_report import evenness_withheld
    noise = (pt.get("rows_noise") or {}).get(row_id)
    if evenness_withheld(row_id, {"value": v, "noise_p95": noise},
                         Limit.value(float(limit))):
        return None
    return v


# ---------------------------------------------------------------------------
# #182 K25 (Knut, 5789263863): what every line, every graph and every red x
# on a trend graph says, on screen as a tooltip and in the PDF as text.
# Written for whoever the PDF is handed to (K18): what the thing IS, never
# how to work ChromIQ and never how the report came to look like this.
# ---------------------------------------------------------------------------

#: One sentence per limit line, keyed by the row the line belongs to. The
#: accuracy chart's grey pair is keyed by the two rows `legacy_pair` reads.
#: Composed with the line's word and value by `_limit_line_note`.
def _limit_note_for(rid: str):
    """The note of one row's limit line: "the limit for “<name>”.", the name
    being the row's version 1 name (K31) or, given, the name this document
    prints for it (the within-gamut name on a split document)."""
    def note(name: "str | None" = None) -> str:
        from workflow.compliance_sets import ROW_BY_ID
        return tr("the limit for “{metric}”.").format(
            metric=name or tr(ROW_BY_ID[rid].label))
    return note


_LIMIT_NOTES = {
    # K28: the two lines of the Colour accuracy graph name their rows by the
    # rows' own names, as the legend beside them does. **AND SO DOES EVERY
    # OTHER LINE (B8-945, beta 40 challenge B, 6).** The grey, tone,
    # repeatability, strip and evenness lines described their metric in
    # words of their own ("the colour cast of the worst single step of the
    # grey ramp") while K31 gave every row ONE name, which the legend beside
    # the line prints. One sentence, the row's name in it.
    rid: _limit_note_for(rid) for rid in (
        "all_de00_avg", "all_de00_max", "substrate_de00_max",
        # K45-2: the three other rows the Colour accuracy graph plots, whose
        # limit a line of that graph now describes too.
        "best95_de00_avg", "worst5_de00_avg", "all_de00_p95",
        "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
        "ramps_30_70_dl_max", "control_strip_de00_avg",
        "control_strip_de00_p95", "repeat_patches_de00_max",
        # K47: the rows that gained a line.
        "control_strip_de00_max", "solids_de00_max", "cmy_solids_dhab_max",
        "outer_gamut_226_de00_avg", "surface_gamut_de00_avg",
        "repeat_measurement_de00_max", "uniformity_sd",
        "uniformity_de00_max_from_mean")
}

#: What each graph is and what it shows, printed above it in the PDF: at
#: most two lines at the picture's width (Knut: *"at most, a two-line
#: description above its chart"*), which a test measures in English and
#: German. Keyed like `_TREND_GROUPS`, plus the four original tabs.
_TREND_ABOUT = {
    # K28: the lines are named here as the legend names them, "Average" and
    # "Maximum" over all patches, the lowest 95 % and the highest 5 %.
    "de": lambda: tr(
        "How far each measured patch lies from its aim value (ΔE00), per "
        "date: the average and the maximum, over all patches, the lowest "
        "95 % and the highest 5 %."),
    "white": lambda: tr(
        "The lightness (L*) of the bare paper, per date. A change points to "
        "a different paper or to a change in the instrument."),
    "paper_diff": lambda: tr(
        "How far the bare paper lies from the reference paper (ΔE00), per "
        "date, with its limit."),
    "black": lambda: tr(
        "The lightness (L*) of the darkest patch on the sheet, per date. A "
        "rising line means the blacks print lighter."),
    "corners": lambda: tr(
        "How far the paper white, the black and each solid primary and "
        "secondary colour lie from their aim values (ΔE00), per date."),
    "grey": lambda: tr(
        "How neutral the grey ramp prints (ΔCh, the colour cast with "
        "lightness left out), per date: the average step and the worst step."),
    "tone": lambda: tr(
        "The maximum lightness difference (ΔL*) on the single-colour and grey "
        "ramps between 30 % and 70 %, per date."),
    # K47: the maximum joined the average and the 95th percentile, and a
    # set limits one, two or all three of them.
    "strip": lambda: tr(
        "The colour difference (ΔE00) of the control-strip patches, per date: "
        "their average, the value 95 % of them stay under and their maximum, "
        "each where a limit applies to it."),
    "solids": lambda: tr(
        "How far the solid colours lie from the reference (ΔE00), per date: "
        "the maximum over the solids the sheet carries."),
    "solid_hue": lambda: tr(
        "How far the hue of the cyan, magenta and yellow solids lies from the "
        "reference (ΔH*ab), per date: the maximum of the three."),
    "gamut_edge": lambda: tr(
        "How far the most saturated colours lie from their aim values "
        "(ΔE00), per date: the average over the outer-gamut patches and over "
        "the surface-gamut patches."),
    "repeat": lambda: tr(
        "How far apart the same colour measures (ΔE00), per date: repeated "
        "patches on one sheet, and the same chart measured again."),
    "evenness": lambda: tr(
        "Whether the sheet prints the same colour everywhere (ΔE00), per "
        "date: between any two of nine areas, and one area against all nine."),
}

#: The Colour accuracy description when the graph plots the within-gamut
#: figures its verdicts judged (K26). Two lines at most, like the others.
def _TREND_ABOUT_DE_JUDGED() -> str:                          # noqa: N802
    return tr(
        "How far each judged patch lies from its aim value (ΔE00), per date: "
        "within the profile's gamut where the sheet was split by it. The "
        "average and the maximum, the lowest 95 % and the highest 5 %.")


#: The same graph on a Printing record, which judges no patch (#182 K30, B3).
def _TREND_ABOUT_DE_WITHIN_GAMUT() -> str:                    # noqa: N802
    return tr(
        "How far each measured patch lies from its aim value (ΔE00), per "
        "date, over the patches within the profile's gamut where the sheet "
        "was split by it: the average and the maximum, the lowest 95 % and "
        "the highest 5 %.")


#: The colour of the mark for a withheld value (Knut: *"a small red x"*).
_WITHHELD_RED = "#d62828"
#: How far above the x-axis a withheld mark with no neighbouring point sits.
_WITHHELD_FLOOR_PX = 6.0
#: Half the width of one arm of the red x, in px.
_WITHHELD_ARM = 3.5
#: How far apart two red crosses of ONE date sit, centre to centre, when their
#: heights would make them overlap (K26): one tooltip box, so neither the
#: crosses nor the areas that show their tooltips overlap.
_WITHHELD_STACK_PX = 2 * _WITHHELD_ARM + 6


def _stack_withheld_marks(marks: list, top: float, bottom: float) -> list:
    """The centre of each red x, ``[QPointF]`` in the order of *marks*
    (``[(date index, QPointF)]``), after stacking (K26, Knut 5792484060,
    graph Q3: two crosses on one date, *"place them one above the other so
    they do not overlap"*).

    **THE LOWER VALUE'S CROSS STAYS LOWER (#182 beta 38, F8).** A second
    cross used to move up from the higher of the others whatever its own
    value, so with both evenness rows withheld on one date the later metric
    was always drawn on top, and "largest difference from the mean" (0.114)
    sat above "nine locations" (0.203). Crosses closer than
    `_WITHHELD_STACK_PX` on one date are now kept in the order of their own
    heights: the lowest stays where it is and each higher one sits at least
    that far above the one below it. When that would leave the plot at
    *top*, the highest stays where it is and each lower one sits that far
    below the one above it, down to *bottom*. Crosses at one height keep the
    order they are listed in, the first lowest. A lone cross never moves."""
    out = [QPointF(c) for _i, c in marks]
    groups: "dict[int, list[int]]" = {}
    for k, (i, _c) in enumerate(marks):
        groups.setdefault(i, []).append(k)
    for ks in groups.values():
        if len(ks) < 2:
            continue
        # bottom first: the largest y (the lowest value) first
        up = sorted(ks, key=lambda k: (-out[k].y(), k))
        ys = {}
        prev = None
        for k in up:
            y = out[k].y()
            if prev is not None and y > prev - _WITHHELD_STACK_PX:
                y = prev - _WITHHELD_STACK_PX
            ys[k] = prev = y
        if min(ys.values()) - _WITHHELD_ARM < top:
            # top first: the highest stays, the lower ones go below it
            ys, prev = {}, None
            for k in reversed(up):
                y = out[k].y()
                if prev is not None and y < prev + _WITHHELD_STACK_PX:
                    y = min(prev + _WITHHELD_STACK_PX, bottom - _WITHHELD_ARM)
                ys[k] = prev = y
        for k, y in ys.items():
            out[k].setY(y)
    return out


def _same_folder(a: "Path", b: "Path") -> bool:
    """Whether *a* and *b* are one folder: the same entry on disk, or the
    same path when either is not there (#182 beta 38, F4)."""
    try:
        return os.path.samefile(str(a), str(b))
    except OSError:
        return os.path.abspath(str(a)) == os.path.abspath(str(b))


def _limit_value_text(v: float, unit: str) -> str:
    """``1.5 ΔE00``: one decimal, two when the limit has them (0.75), with
    the decimal mark of the report's language (B8-957: German printed
    "Bereiche (1.5 ΔE00)" in a report that writes "59,4" elsewhere)."""
    from core.i18n import current_language
    s = f"{float(v):.2f}"
    if s.endswith("0"):
        s = s[:-1]
    if current_language() in _DECIMAL_COMMA:
        s = s.replace(".", ",")
    return f"{s} {unit}".strip()


def _limit_line_note(word: str, value: float, unit: str, row_id: str,
                     name: "str | None" = None) -> str:
    """The sentence a limit line's word stands for, on screen and in print.
    *name* is the row's name as the document prints it (B8-944: "…, within
    gamut" on a split document, as the legend beside the line)."""
    return tr("{word} ({value}): {text}").format(
        word=word, value=_limit_value_text(value, unit),
        text=_LIMIT_NOTES[row_id](name))


def _limit_line_note_for_rows(word: str, value: float, unit: str,
                              row_ids: list, names: list) -> str:
    """`_limit_line_note` for a line that is the limit for SEVERAL rows
    (K45-2, Knut #182 5834422633): the Colour accuracy graph's Avg line is the
    limit for every average row the set limits at that number, and its Max
    line for every maximum, so the sentence names each of them. One row reads
    exactly as `_limit_line_note` always has."""
    if len(row_ids) == 1:
        return _limit_line_note(word, value, unit, row_ids[0], names[0])
    quoted = [tr("“{metric}”").format(metric=n) for n in names]
    listed = tr("{items} and {item}").format(items=", ".join(quoted[:-1]),
                                              item=quoted[-1])
    return tr("{word} ({value}): {text}").format(
        word=word, value=_limit_value_text(value, unit),
        text=tr("the limit for {metrics}.").format(metrics=listed))


#: The five rows the Colour accuracy graph plots, each with the family of
#: limit line it belongs to: an average sits under the grey "Avg" line, a
#: maximum (the 95th percentile is "Maximum ΔE00, lowest 95 %") under "Max".
_ACCURACY_LINE_ROWS = (("all_de00_avg", "avg"), ("best95_de00_avg", "avg"),
                       ("worst5_de00_avg", "avg"), ("all_de00_max", "max"),
                       ("all_de00_p95", "max"))


def _with_unit(label: str, unit: str) -> str:
    """A legend entry carrying its unit, as Colour accuracy's already do.

    **A NAME THAT ALREADY CARRIES ITS UNIT IS NOT GIVEN IT TWICE (K28).** The
    five colour-accuracy names are Knut's i1Profiler-order names with the unit
    inside them, "Average ΔE00, all patches"; the legend is that name exactly,
    as the grid and the limits window print it, not "Average ΔE00, all
    patches (ΔE00)"."""
    if unit and unit in label:
        return label
    return tr("{metric} ({unit})").format(metric=label, unit=unit)


def _trend_withheld_reason(pt: dict, row_id: str, limit) -> "str | None":
    """Why *row_id* has no point on this date although it has a value: the
    same noise rule, and the same sentence, as the results table's N-A. None
    when the value is plotted, or when there is no value to withhold."""
    v = (pt.get("rows") or {}).get(row_id)
    if v is None or limit is None:
        return None
    if _trend_row_value(pt, row_id, limit) is not None:
        return None
    from workflow.measurement_report import EVENNESS_ROWS
    key = EVENNESS_ROWS.get(row_id) or "pairwise"
    noise = (pt.get("rows_noise") or {}).get(row_id)
    return _evenness_noise_sentence(
        {"evenness": {f"noise_{key}_p95": noise}}, key, float(limit))


def _withheld_mark_value(values: list, i: int) -> "float | None":
    """The height of the red x at date *i* of one metric (Knut, 5789263863):
    at the neighbouring value when only one side has one, at the mean of the
    two when both do, and None, the floor just above the x-axis, when neither
    does. *values* holds the metric's plotted value per date on the axis,
    None where it has no point.

    **THE NEAREST DATE THAT HAS A VALUE, on each side (K26, Knut 5792484060,
    graph Q1: "Yes").** It was the date directly beside *i*, as his first
    words read, and two withheld dates in a row then put the first one on the
    floor although a measured date stood one further along."""
    before = next((values[j] for j in range(i - 1, -1, -1)
                   if values[j] is not None), None)
    after = next((values[j] for j in range(i + 1, len(values))
                  if values[j] is not None), None)
    have = [v for v in (before, after) if v is not None]
    return sum(have) / len(have) if have else None


def _tip_rich(text: str) -> str:
    """*text* as a tooltip Qt wraps. Plain text is shown on ONE line, and the
    red x's sentence came out 1,580 px wide, wider than the report window
    (photographed in the K25 drive); rich text is wrapped by the tooltip."""
    return "<qt>" + html.escape(text) + "</qt>"


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

#: The text width of the saved PDF, in the 96-dpi pixels its document is laid
#: out in: A4 less 15 mm a side (`_export_pdf`), floored. A metric table wider
#: than this is cut off at the paper's right edge, which is what round B
#: before beta 37 photographed (H1).
_PDF_TEXT_W = 679.0

#: The share of a metric table's width its Metric column keeps (H1).
_METRIC_COL_SHARE = "32%"

#: How many lines the sentence beside "Report shown" may take before it is
#: shortened with "…" (K32, Knut on beta 41: "wrap to up to 3 lines").
_BESIDE_PULLDOWN_LINES = 3

#: The fewest dated columns a metric table in the WINDOW holds before it
#: continues below (K32, Knut on beta 41, #182 5814107188: "The on-screen
#: report in the measurement window should show at least 4 columns of
#: included measurements before braking the table"). The PDF is fitted to
#: the paper alone, because a column past the page edge is cut off.
_SCREEN_MIN_RUN_COLS = 4

#: How far past the text width a table may measure and still fit. Qt's table
#: layout rounds the Metric column's percentage share up: measured on the
#: Overview of four dates, the same table is 679 px wide without the share
#: and 680 px with it, and the old half-pixel allowance then halved the table
#: to two dates a block in the PDF and the window alike (K32). One pixel is
#: 0.26 mm of a 15 mm margin; a real overflow is a column, tens of pixels.
_TABLE_FIT_SLACK_PX = 1.5

#: A metric table's width in the WINDOW (challenge 2 of beta 42, #3): not
#: 100%, which Qt lays out up to one pixel wider than the page (217 of 1204
#: tables measured, 1 to 8 dates, 600 to 1800 px), so the page was one pixel
#: wider than the view and carried a horizontal scroll bar. 99.9% still ran
#: over in 18 of those, 99.8% in 1, 99.6% and 99.5% in none; 99.5% keeps at
#: least 3 px spare at the window's narrowest page (about 700 px).
_SCREEN_TABLE_WIDTH = "99.5%"


def _words_broken_across_lines(doc) -> "list[str]":
    """The texts of *doc* whose layout breaks a WORD over two lines.

    A cell narrower than its longest word is squeezed by Qt's table layout,
    and the word is then cut wherever the edge falls: "(recommende" over "d)".
    """
    out = []
    b = doc.begin()
    while b.isValid():
        lay, t = b.layout(), b.text()
        for i in range((lay.lineCount() if lay else 0) - 1):
            ln = lay.lineAt(i)
            end = ln.textStart() + ln.textLength()
            if 0 < end < len(t) and not t[end - 1].isspace() \
                    and not t[end].isspace() and t[end - 1] != "/":
                out.append(t)
                break
        b = b.next()
    return out


def _table_fits_the_page(table_html: str, width: float = _PDF_TEXT_W) -> bool:
    """Whether *table_html* lays out within the PDF's text width, in the
    report's own font, with no word broken over two lines."""
    from PyQt6.QtCore import QSizeF
    from PyQt6.QtGui import QTextDocument
    family = QApplication.font().family().replace("'", "")
    doc = QTextDocument()
    doc.setHtml(f"<div style=\"font-family:'{family}';font-size:12px\">"
                + table_html + "</div>")
    doc.setPageSize(QSizeF(width, 100_000))
    return (doc.size().width() <= width + _TABLE_FIT_SLACK_PX
            and not _words_broken_across_lines(doc))


def _swatch(hexc: str) -> str:
    """A solid colour block for rich text. Qt ignores width/height on an empty
    span but honours background-color on a span WITH content, so we fill it with
    spaces hidden by matching the text colour to the fill.

    NO COLOUR IS NOT WHITE. The fallback used to be `#ffffff`, so a patch with
    no expected colour — every patch of a converted chart whose colorimetric
    reference file is gone, which §9.1 deliberately refuses to guess for — drew
    a white block in the "Asked for" column, on the one page meant to be handed
    to a customer. It reads as the same nothing the ΔE column reads.

    AND THE EDGE IS A SECOND SPAN, because Qt's rich text ignores `border` on an
    inline one. It was written as `border:1px solid …` and drew NOTHING: rendered
    on its own against the report ground and counted, the border colour came back
    at zero pixels, and the only reason it looked present in a first probe was
    the antialiasing of the text beside it. So a patch near the ground colour had
    no edge to find: photographed on screen, `#191946` sat on `#1f1f1f` and read
    as an empty cell, and on the light palette and in every PDF paper white does
    the same. An outer span carrying the edge colour behind the fill draws, and
    is what the frame is made of now.
    """
    if not hexc:
        return _fmt(None)
    c = html.escape(hexc)
    e = html.escape(_C["swatch_edge"])
    return (f"<span style='background-color:{e};color:{e}'>&nbsp;"
            f"<span style='background-color:{c};color:{c}'>"
            f"&nbsp;&nbsp;&nbsp;</span>&nbsp;</span>")


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

    **AND THE THIRD BLOCK WAS MISSING FROM THIS LIST, WHICH IS THE SAME FAULT
    AGAIN.** Knut, 2026-09-11, opening a report from the shared demo package:
    the Colour summary's Example colours section read *"This measurement was
    saved before ChromIQ chose example colours. Measure the chart again to
    have them."* It was true and it was avoidable. `summary_patches` is the
    sixteen colours the one-page summary is mostly made of; the current builder
    always writes it beside `worst_patches` whenever the measurement has a
    reference, and it arrived after the two blocks named above. A report older
    than it passed this test, was never rebuilt, and told the reader to measure
    a chart again for something that is entirely computable from the file in
    the same folder.

    That is word for word the fault the paragraph above records being fixed for
    `grey_balance`. The rule in `docs/design/measurement_report_limits.md` §6
    is general, "a report missing a block the current builder always writes is
    stale, at any schema"; this function ENUMERATED, so each new block had to
    be remembered separately and the third was not. The blocks are listed in
    one tuple now, next to the sentence that says what belongs in it.

    A report with no reference is already stale by the `avg_all` clause above,
    which is the same condition under which the builder writes none of these
    three, so adding the third cannot put a report into a rebuild loop that the
    second clause was not already putting it into.
    """
    from workflow.measurement_report import REPORT_SCHEMA
    return (rep.get("schema", 0) < REPORT_SCHEMA
            or (rep.get("de00") or {}).get("avg_all") is None
            or any(k not in rep for k in ALWAYS_BUILT_BLOCKS))


#: Every block `workflow.measurement_report.build_report` writes on ANY
#: measurement that has a reference. A saved report missing one of them was
#: written by an older ChromIQ and is stale however new its schema says it is.
#:
#: ADD TO THIS TUPLE WHEN YOU ADD A BLOCK TO THE BUILDER. Three blocks have
#: been added since the schema stopped being bumped for them, and two of the
#: three had to be found by a user reading a report that told him to measure
#: his chart again for a number that was already on his disk.
#:
#: **AND THE INSTRUCTION ABOVE WAS NOT FOLLOWED, FOUR BLOCKS RUNNING.**
#: Measured 2026-09-22 on a report this branch's own demo builder saved:
#: schema 7, `avg_all` present, all three listed blocks present, so
#: :func:`_report_needs_rebuilding` answered **False** -- while
#: `repeat_within_sheet` and `repeat_across_sheets` were absent, and
#: `row_values` answered both of ChromIQ's own repeatability rows
#: ``value=None, reason='not_computed'``: *"this value is not in this saved
#: report; it was not one of the values ChromIQ kept when the report was
#: saved"*, with the `.ti3` that answers them in the same folder. That is
#: word for word the fault this tuple exists to stop, for a fourth, fifth,
#: sixth and seventh block.
#:
#: SO IT IS NOT MAINTAINED BY HAND ANY MORE. The list is now every block
#: `row_values` reads that `build_report` writes on an ordinary measurement,
#: plus `summary_patches`, which no row reads and the one-page summary does.
#: `tests/test_a_row_that_was_never_computed_is_rebuilt.py` DERIVES that set
#: from the two functions and fails on anything missing from here, so a block
#: added to the builder cannot be forgotten an eighth time.
ALWAYS_BUILT_BLOCKS: "tuple[str, ...]" = (
    "grey_balance", "ramps_30_70", "summary_patches",
    # S2w (2026-09-18) and the two repeatability rows (2026-09-21)
    "corners", "control_strip", "gamut_populations",
    "repeat_within_sheet", "repeat_across_sheets",
    # evenness across the sheet (Knut, 2026-09-22)
    "evenness",
    # #182 A10/A11 (Knut, 5817809396, beta 42): whether the chart has a paper
    # patch. A report without it took its paper white from the LIGHTEST
    # reading and, on a FROM PROFILE GAMUT chart, compared the paper with an
    # ideal white; it is worked out again from its measurement, as every
    # block above was, and the saved verdict is carried across untouched.
    "paper_patch",
    # #182 K37 (Knut, 5822758830): which paper white a sheet printed with a
    # white-mapping intent was judged relative to. A report without it judged
    # such a sheet with no paper patch in absolute Lab; it is worked out
    # again, the saved verdict carried across as above.
    "paper_white_used",
    # #182 K37 (i) (Knut, 5823088098): what a FROM PROFILE GAMUT chart's
    # corner rungs of the control strip were compared with. A report without
    # it compared them with their ideal values; it is worked out again.
    "strip_corner_aims",
)


#: **THE BLOCKS THAT SAY HOW A VERDICT WAS WORKED OUT, AND WHICH A RULE
#: INTRODUCED SINCE (challenge 5 of beta 42, M1, B8-1091).** A report saved
#: before one of them existed is rebuilt when it is read (the tuple above),
#: and its saved verdict is kept (§6). The rebuilt block describes how THIS
#: version works the sheet out, which is not how the kept verdict was worked
#: out: a Border-Conditions sheet saved before K37 kept FAIL, FAIL (absolute
#: Lab) under a note saying it was judged relative to its profile's paper
#: white, and a Second-Route sheet kept its strip rows under a rebuilt
#: `strip_corner_aims` of "the profile's prediction". So beside a kept
#: verdict these are taken ONLY from what the saved report recorded; a block
#: it did not record is left out, and the page says, once, that an earlier
#: version worked the report out (`_worked_out_earlier_html`).
RULE_BLOCKS: "tuple[str, ...]" = (
    "paper_patch", "paper_white_used", "strip_corner_aims")

#: Everything a saved report records about HOW its colours were judged. Beside
#: a kept verdict these come from the record, never from a rebuild; a report of
#: several dates records them per measurement in its `JUDGED_KEY` block.
EXPLANATION_BLOCKS: "tuple[str, ...]" = (
    "yardstick", "yardstick_no_paper", "paper_white", "printing",
    "colorimetric") + RULE_BLOCKS

#: Session key: the row as its saved report recorded it (`_the_saved_record`),
#: shown wherever the row's verdict is the kept one.
RECORD_KEY = "_record"
#: Session key: this version works the row out differently from the earlier
#: version that saved it (`_worked_out_differently`).
WORKED_OUT_EARLIER_KEY = "_worked_out_earlier"


def _worked_out_differently(saved: dict, rebuilt: dict) -> bool:
    """Would THIS version explain *saved*'s verdict differently from the
    earlier version that wrote it? Asked only of the rule blocks *saved*
    lacks (M1, B8-1091):

    * no `paper_white_used`: before K37 a white-mapped sheet with no paper
      patch was judged in absolute Lab; now it is judged relative to its
      profile's paper white when a profile can be read ((e), §33);
    * no `strip_corner_aims`: before K37 (i) a FROM PROFILE GAMUT chart's
      corner rungs were compared with their ideal values; now with the
      profile's prediction when a profile can be read (§34);
    * no `paper_patch`: before beta 42 the paper white was the lightest
      reading; now it is the patch printed with no ink (§31.4), which is a
      different patch, or none."""
    from workflow.measurement_report import (CORNER_AIMS_FROM_PROFILE,
                                             PAPER_WHITE_FROM_PROFILE)
    if not isinstance(saved, dict) or not isinstance(rebuilt, dict):
        return False
    if "paper_white_used" not in saved and (
            (rebuilt.get("paper_white_used") or {}).get("from")
            == PAPER_WHITE_FROM_PROFILE):
        return True
    if "strip_corner_aims" not in saved and (
            (rebuilt.get("strip_corner_aims") or {}).get("from")
            == CORNER_AIMS_FROM_PROFILE):
        return True
    if "paper_patch" not in saved:
        if rebuilt.get("paper_patch") is False:
            return True

        def _where(p):
            if not isinstance(p, dict):
                return None
            lab = p.get("lab")
            return (str(p.get("loc") or ""),
                    tuple(round(float(v), 1) for v in lab)
                    if isinstance(lab, (list, tuple)) else None)
        if _where(saved.get("paper_white")) != _where(
                rebuilt.get("paper_white")):
            return True
    return False


def _the_saved_record(saved: dict, rebuilt: dict) -> "dict | None":
    """The row a SAVED report is shown as beside its kept verdict (M1,
    B8-1091), or None when it kept no verdict (it is then judged live, from
    the rebuilt report, as before).

    §6: a saved report is a record; the rebuild computes the blocks it never
    had and re-grades nothing. So the record is the saved report itself,
    completed with the blocks it lacks, and never overwritten by them: its
    numbers, its yardstick, its print record and its paper white are the
    ones its verdict was worked out from. A rule block it lacks
    (`RULE_BLOCKS`) is NOT taken from the rebuild, because that block would
    explain the kept verdict by a rule it was not worked out by; where this
    version would work it out differently the record carries
    `WORKED_OUT_EARLIER_KEY`, and the page says so once.

    A report of an older SCHEMA (no ``avg_all``) cannot lend its metric
    block, so there the rebuild's numbers stand and only what the report
    recorded about how it was judged (`EXPLANATION_BLOCKS`) is kept."""
    from workflow.measurement_report import REPORT_SCHEMA, recorded_verdict
    if not isinstance(saved, dict) or recorded_verdict(saved) is None:
        return None
    rec = dict(rebuilt or {})
    if saved.get("schema", 0) >= REPORT_SCHEMA \
            and (saved.get("de00") or {}).get("avg_all") is not None:
        rec.update(saved)
    else:
        rec.update({k: saved[k] for k in
                    ("pass_thresholds", "verdict", "compliance",
                     "report_type", "document", "created")
                    + EXPLANATION_BLOCKS if k in saved})
    for k in RULE_BLOCKS:
        if k not in saved:
            rec.pop(k, None)
    if _worked_out_differently(saved, rebuilt or {}):
        rec[WORKED_OUT_EARLIER_KEY] = True
    return rec


def _h2(text: str, *, page_break: bool = False) -> str:
    """A main section heading, matching 'Trend over time' etc.

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


#: Languages whose decimal separator is a comma (B8-950). A level printed
#: inside a sentence follows the sentence's language: "59,4" in German.
_DECIMAL_COMMA = frozenset({"de", "es", "fr", "it", "nl", "no", "pl", "pt",
                            "ru", "sv", "uk"})


def _level_text(v) -> str:
    """A level (a tone value, an L*, a grey level) as a sentence prints it:
    as short as it is (``50``, ``59.4``), with the decimal comma of the
    report's language."""
    from core.i18n import current_language
    t = f"{float(v or 0):g}"
    return t.replace(".", ",") if current_language() in _DECIMAL_COMMA else t


def _small_sample_sentence(r: "dict | None") -> str:
    """Why "Average ΔE00, highest 5 %" was withheld, naming the population it
    counted. Its words are the row's own name (K28, one vocabulary).

    Two sentences, because the honest answer depends on whether the profile's
    gamut took patches out of the reckoning. A chart of 20 whose within-gamut
    subset is 18 is not "a chart of 20 patches, at least 20 are needed": that
    reads as a condition met and a row withheld anyway, which is what was
    measured on screen.
    """
    from workflow.measurement_report import graded_de00
    r = r or {}
    graded, _src = graded_de00(r)
    n = graded.get("n")
    total = r.get("patches")
    if isinstance(n, int) and isinstance(total, int) and n != total:
        # ONE OF THEM FALLS, NOT FALL. A twenty-patch sheet with nineteen
        # colours outside the gamut reaches n = 1, and "(s)" is banned in this
        # project's user-facing text.
        return (tr("{total} patches were measured and one of them falls inside "
                   "the profile's gamut; at least 20 inside it are needed to "
                   "split off "
                   "the highest 5 %").format(total=total) if n == 1 else
                tr("{total} patches were measured and {n} of them fall inside "
                   "the profile's gamut; at least 20 inside it are needed to "
                   "split off "
                   "the highest 5 %").format(total=total, n=n))
    _count = n if isinstance(n, int) else total if total is not None else None
    if _count == 1:
        return tr("the measured chart has one patch; at least 20 are needed to "
                  "split off the highest 5 %")
    return tr("the measured chart has {n} patches; at least 20 are needed to "
              "split off the highest 5 %").format(n=_count if _count is not None else "?")


# ---------------------------------------------------------------------------
# #182 S2w: why one of the five newly computable rows was withheld
# ---------------------------------------------------------------------------
#
# Each of these names the NUMBER THE CHART SUPPLIED and the number that is
# wanted, and each ends in something to change. A count with no target is a
# complaint; a target with no count leaves a reader guessing how far off they
# are. `_small_sample_sentence` above is the same shape, and it is the shape
# because a round measured its predecessor saying *"the chart has 20 patches;
# at least 20 are needed"*.


def _control_strip_sentence(r: "dict | None") -> str:
    """Why a control-strip row was withheld: the strip is too short.

    ONE SENTENCE FOR ALL THREE ROWS, and it names both thresholds because both
    are reachable from here. A strip of twelve satisfies the average and the
    largest and not the 95th percentile, so the sentence a reader sees beside
    that row has to say why the two rows above it were judged and this one was
    not.
    """
    from workflow.measurement_report import (CONTROL_STRIP_MIN,
                                             CONTROL_STRIP_P95_MIN)
    block = (r or {}).get("control_strip") or {}
    k = block.get("n")
    k = k if isinstance(k, int) else 0
    if k == 1:
        counted = tr("the control strip of the measured chart has one patch "
                     "with a reference value")
    else:
        counted = tr("the control strip of the measured chart has {k} patches "
                     "with reference values").format(k=k)
    return counted + tr("; at least {n} are needed for the average and the "
                        "maximum, and at least {p} for the 95th percentile").format(n=CONTROL_STRIP_MIN,
                                        p=CONTROL_STRIP_P95_MIN)


def _surface_gamut_sentence(r: "dict | None") -> str:
    """Why the surface-gamut row was withheld: too few patches on the cube."""
    from workflow.measurement_report import SURFACE_GAMUT_MIN
    block = ((r or {}).get("gamut_populations") or {}).get("surface") or {}
    n = block.get("n")
    n = n if isinstance(n, int) else 0
    if n == 1:
        counted = tr("one patch of the measured chart sits on the surface of "
                     "the device cube and carries a reference value")
    else:
        counted = tr("{n} patches of the measured chart sit on the surface of "
                     "the device cube and carry reference values").format(n=n)
    return counted + tr("; at least {k} are needed").format(
                            k=SURFACE_GAMUT_MIN)


def _repeat_groups_sentence(r: "dict | None") -> str:
    """Why the within-sheet repeatability row was withheld: the sheet repeats
    one colour, and one colour is not the sheet.

    Names the count it found, as every sentence in this family does, because
    *"at least 2 are needed"* beside a chart that has 2 is the shape that was
    measured on screen once and is not repeated here.
    """
    from workflow.measurement_report import REPEAT_WITHIN_MIN_GROUPS
    block = (r or {}).get("repeat_within_sheet") or {}
    n = block.get("n_groups")
    n = n if isinstance(n, int) else 0
    if n == 1:
        counted = tr("the measured chart repeats one colour")
    else:
        counted = tr("the measured chart repeats {n} colours").format(n=n)
    return counted + tr("; at least {k} are needed, because a reading taken "
                        "from a single colour stands for nothing else on the "
                        "sheet").format(
                            k=REPEAT_WITHIN_MIN_GROUPS)


def _repeat_shared_sentence(r: "dict | None") -> str:
    """Why the measured-again row was withheld: the two measurements are not
    of the same chart any more."""
    from workflow.measurement_report import REPEAT_ACROSS_MIN_PATCHES
    block = (r or {}).get("repeat_across_sheets") or {}
    n = block.get("n_shared")
    n = n if isinstance(n, int) else 0
    if n == 1:
        counted = tr("one patch of the measured chart is also in the "
                     "measurement before it, asked for the same colour")
    else:
        counted = tr("{n} patches of the measured chart are also in the "
                     "measurement before it, asked for the same colour").format(n=n)
    return counted + tr("; at least {k} are needed. The chart changed between "
                        "the two measurements, so most of it is no longer the "
                        "same patch set and what changed cannot be read as the "
                        "printer moving").format(
                            k=REPEAT_ACROSS_MIN_PATCHES)


def _evenness_block(r: "dict | None") -> dict:
    block = (r or {}).get("evenness")
    return block if isinstance(block, dict) else {}


def _evenness_grid_sentence(r: "dict | None") -> str:
    """Why evenness was withheld: no page of the measured chart reaches Knut's
    geometric floor. Names the largest page the chart has, because "at least 9
    are needed" beside a chart whose size is not said teaches nothing."""
    from workflow.measurement_report import EVENNESS_MIN_GRID
    s, rows = (_evenness_block(r).get("largest_page") or [0, 0])[:2]
    return tr("the measured chart has {s} strips and {r} rows on its largest "
              "page; at least {k} strips and {k} rows are needed on a "
              "page").format(s=int(s or 0), r=int(rows or 0),
                             k=EVENNESS_MIN_GRID)


def _coverage_pct(v) -> str:
    """A page's coverage as a percentage with one decimal, ROUNDED DOWN, so a
    page left out at 74.96 % never reads "75.0 %" beside "at least 75 %"."""
    if not isinstance(v, (int, float)):
        return "?"
    return f"{math.floor(float(v) * 1000.0) / 10.0:.1f}"


def _min_coverage_pct() -> str:
    from workflow.measurement_report import EVENNESS_MIN_PAGE_COVERAGE
    return f"{EVENNESS_MIN_PAGE_COVERAGE * 100:g}"


def _evenness_empty_area_sentence(r: "dict | None") -> str:
    """`evenness_empty_area`: an area of the nine with no patch to compare.

    A patch counts in an area when it was measured and has an aim value, and,
    on a sheet split by the profile's gamut, lies within it
    (`evenness_block`), so the sentence names the last condition only where it
    applied."""
    if _evenness_block(r).get("population") == "in_gamut":
        return tr("one of the nine areas of the measured chart holds no "
                  "measured patch with an aim value within the profile's "
                  "gamut")
    return tr("one of the nine areas of the measured chart holds no measured "
              "patch with an aim value")


def _evenness_coverage_sentence(r: "dict | None") -> str:
    """Why evenness was withheld: every page of at least 9 by 9 has its patch
    block cover less of the paper than Knut's floor (#182 E2). Written to his
    K22 rule: it names what the measured chart lacks, and the figure."""
    b = _evenness_block(r)
    short = list(b.get("pages_uncovered") or [])
    cov = list(b.get("coverage") or [])

    def of(p):
        return cov[p - 1] if 0 < p <= len(cov) else None
    if len(short) == 1:
        return tr("the patches on page {p} of the measured chart cover {x} % "
                  "of the page; at least {k} % is needed").format(
                      p=short[0], x=_coverage_pct(of(short[0])),
                      k=_min_coverage_pct())
    best = max((of(p) for p in short if of(p) is not None), default=None)
    return tr("the patches on pages {p} of the measured chart cover at most "
              "{x} % of their page; at least {k} % is needed").format(
                  p=", ".join(str(p) for p in short), x=_coverage_pct(best),
                  k=_min_coverage_pct())


def _evenness_noise_sentence(r: "dict | None", key: str,
                             limit: "float | None" = None) -> str:
    """Why an evenness row was withheld by the noise rule (Knut, ruling 6).

    **THE MEASUREMENT'S NOISE, NOT THE CHART'S PATCH COUNT** (the two
    challenge rounds before beta 37, A-F3 and B-H2). The sentence used to say
    "the measured chart has 42 patches in the emptiest ninth of the page, too
    few for this row" on the noisy date of the evenness demo, while the notes
    beside it judged the SAME chart's 42-patch areas on its three other
    dates. On a measured sheet the rule compares the sheet's own noise with
    the limit, and a sheet whose readings scatter is what withholds the row:
    it names the noise figure the rule compared, which Knut asked to be
    shown, and the limit it was compared with, and no patch count."""
    b = _evenness_block(r)
    noise = b.get(f"noise_{key}_p95")
    if isinstance(limit, (int, float)):
        return tr("the measured sheet is too noisy to judge this row: its own "
                  "noise here is {noise} ΔE00 (the 95th percentile of the "
                  "same figure with the patches shuffled across the nine "
                  "areas), which is not below the limit of {limit} "
                  "ΔE00").format(noise=_fmt(noise, 2), limit=_fmt(limit, 2))
    return tr("the measured sheet is too noisy to judge this row: its own "
              "noise here is {noise} ΔE00 (the 95th percentile of the same "
              "figure with the patches shuffled across the nine areas), which "
              "is not below the limit").format(noise=_fmt(noise, 2))


def _evenness_area_name(area: dict) -> str:
    """One ninth of the page, by the labels printed on the sheet.

    Never "top left": which way up a strip runs depends on the instrument and
    the orientation, and the letters and numbers are on the paper."""
    spans = [tr("{first} to {last}").format(first=a, last=b)
             for a, b in (area.get("strips") or [])]
    rows = area.get("rows") or ["", ""]
    if not spans:
        strips = "?"
    elif len(spans) == 1:
        strips = spans[0]
    else:
        strips = tr("{list} and {last}").format(list=", ".join(spans[:-1]),
                                                last=spans[-1])
    return tr("strips {strips}, rows {first} to {last}").format(
        strips=strips, first=rows[0], last=rows[1])


def _evenness_worst_area_sentence(r: "dict | None") -> str:
    """The one sentence naming the ninth of the page furthest from the rest,
    or "" when the sheet was not judged on evenness."""
    b = _evenness_block(r)
    areas = b.get("areas") or []
    if not b.get("eligible") or len(areas) != 9:
        return ""
    worst = areas[int(b.get("worst_area", 0))]
    return tr("On the measured chart the ninth of the page furthest from the "
              "average of all nine is {area}: {de} ΔE00 from it (ΔL* {dl}, "
              "Δa* {da}, Δb* {db} against its aim values, over {n} "
              "patches).").format(
                  area=_evenness_area_name(worst),
                  de=_fmt(worst.get("de_from_mean"), 2),
                  dl=_fmt(worst.get("dL"), 2), da=_fmt(worst.get("da"), 2),
                  db=_fmt(worst.get("db"), 2), n=int(worst.get("n") or 0))


def _evenness_where_sentence(r: "dict | None") -> str:
    """Which part of the measured sheet is off, for a note on the verdict.

    Knut, 2026-09-22: *"The results of this test should return indications of
    which part of the page are not uniform against other areas."*
    """
    out = _evenness_worst_area_sentence(r)
    if not out:
        return ""
    b = _evenness_block(r)
    areas = b.get("areas") or []
    i, j = (b.get("worst_pair") or [0, 1])[:2]
    out += " " + tr("The two ninths furthest apart are {a} and {b}, {de} "
                    "ΔE00 apart.").format(
                        a=_evenness_area_name(areas[int(i)]),
                        b=_evenness_area_name(areas[int(j)]),
                        de=_fmt(b.get("pairwise"), 2))
    out += " " + tr("The measured chart's own noise, the 95th percentile of "
                    "the same figures with its patches shuffled across the "
                    "nine areas, is {pw} ΔE00 between two areas and {fm} "
                    "ΔE00 from the average.").format(
                        pw=_fmt(b.get("noise_pairwise_p95"), 2),
                        fm=_fmt(b.get("noise_from_mean_p95"), 2))
    used = b.get("pages_used") or []
    pages = b.get("pages") or []
    # #182 E2: a page is left out for one of three things it lacks, and each
    # is named. A block saved before E2 has none of the three lists, and every
    # page it left out was left out for the grid.
    if "pages_small" in b:
        left = list(b.get("pages_small") or [])
    else:
        left = [p for p in range(1, len(pages) + 1) if p not in used]
    uncovered = list(b.get("pages_uncovered") or [])
    unmeasured = list(b.get("pages_unmeasured") or [])
    if left:
        from workflow.measurement_report import EVENNESS_MIN_GRID
        out += " " + (tr("Page {p} has fewer than {k} strips or rows and is "
                         "not counted.").format(p=left[0], k=EVENNESS_MIN_GRID)
                      if len(left) == 1 else
                      tr("Pages {p} have fewer than {k} strips or rows and are "
                         "not counted.").format(
                             p=", ".join(str(x) for x in left),
                             k=EVENNESS_MIN_GRID))
    if uncovered:
        cov = list(b.get("coverage") or [])
        if len(uncovered) == 1:
            p = uncovered[0]
            out += " " + tr("The patches on page {p} cover {x} % of the page, "
                            "less than {k} %, so it is not counted.").format(
                                p=p, x=_coverage_pct(cov[p - 1]
                                                     if p <= len(cov) else None),
                                k=_min_coverage_pct())
        else:
            out += " " + tr("The patches on pages {p} cover less than {k} % "
                            "of their page, so they are not counted.").format(
                                p=", ".join(str(x) for x in uncovered),
                                k=_min_coverage_pct())
    if unmeasured:
        out += " " + (tr("Where the patches sit on page {p} is not recorded, "
                         "so it is not counted.").format(p=unmeasured[0])
                      if len(unmeasured) == 1 else
                      tr("Where the patches sit on pages {p} is not recorded, "
                         "so they are not counted.").format(
                             p=", ".join(str(x) for x in unmeasured)))
    return out


def _outer_gamut_sentence(r: "dict | None") -> str:
    """Why the outer-gamut row was withheld: the top quarter is too small."""
    from workflow.measurement_report import OUTER_GAMUT_MIN
    block = ((r or {}).get("gamut_populations") or {}).get("outer") or {}
    n = block.get("n")
    n = n if isinstance(n, int) else 0
    if n == 1:
        counted = tr("the most saturated quarter of the measured chart is one "
                     "patch")
    else:
        counted = tr("the most saturated quarter of the measured chart is {n} "
                     "patches").format(n=n)
    return counted + tr("; at least {k} are needed for an average, which means "
                        "roughly {c} patches carrying reference values in the "
                        "measured chart").format(
                            k=OUTER_GAMUT_MIN, c=OUTER_GAMUT_MIN * 4)


def _faint_label_css(mode: str) -> str:
    """The style for a window's secondary one-line label, per appearance.

    **`color: palette(mid)` IS INVISIBLE IN THE DARK THEME**, and it was the
    style on both of this window's faint labels. Measured 2026-09-16 while
    photographing a greyed-out Delete with no reason beside it: the label's
    resolved foreground is `#161616` on a ground of about `#141414`, a contrast
    ratio of essentially 1. In the light theme the same role resolves to
    `#d8d4ce`, which is barely better the other way round. Qt's Mid role is a
    3-D frame shade, not a text colour, and ChromIQ's palettes never set it for
    reading.

    So the colour is chosen the way the strip under this row already chooses
    its own: per mode, explicitly. The neutral theme has a named text colour
    for exactly this (`NM_TEXT_DIM`, 12.13:1 on its panel).

    This cost the "Already generated for this run:" line too, which is the line
    Knut asked for on 2026-09-11 and reported as truncated on 2026-09-13. It
    was not being read short; in the dark theme it was not being read at all.
    """
    if mode == "dark":
        return "color: #9a9a9a; padding-left: 4px"
    if mode == "neutral":
        return f"color: {neutral_styles.NM_TEXT_DIM}; padding-left: 4px"
    return "color: #5b5b5b; padding-left: 4px"


def _report_file_order(name) -> tuple:
    """Where one `report_<stamp>[_N].json` sits in the order they were written.

    `save_report` stamps the file with the second it was saved and, for a
    second report of the same second, appends `_2`, `_3`, …  Compared as
    strings those stop sorting at ten: `"report_…_9.json"` is greater than
    `"report_…_16.json"`, so "the newest report wins" quietly meant "the ninth
    of that second wins". The stamp is read as text, which sorts correctly
    because it is `%Y-%m-%d_%H-%M-%S`, and the suffix as the number it is.

    A name in any other shape sorts BEFORE every readable one, whatever its
    letters: it carries no evidence of when it was written, and a file called
    `odd.json` must not win a row off a stamped report by alphabet.

    THE NAME IS THE TIE-BREAK AND NOT THE ANSWER: see `_report_order`.
    """
    import re as _re
    text = str(name or "")
    m = _re.fullmatch(r"report_(.+?)(?:_(\d+))?\.json", text)
    if m is None:
        return (0, text, 0)
    return (1, m.group(1), int(m.group(2) or 1))


def _report_order(origin, name) -> tuple:
    """When one saved report was written, for "the newest of them wins".

    **THE FILE'S OWN TIME FIRST, THE NAME SECOND.** `save_report` stamps the
    name with the second it saved, so on a disk where every report was written
    by ChromIQ the two agree and this changes nothing. They part company on a
    project that came from somewhere else: the demo packs a tester works from
    seed each report with the name they want its DATE to read, so a report he
    generated on 15 September sorted below one the pack had named
    `report_2026-11-02_10-00-00.json`.

    What that cost, driven in a real window: with an older report chosen in the
    pulldown, **Generate report** wrote a file and the page went on describing
    the one it was pointed at, because the merge still thought the pack's file
    was the newest of the three. A button that writes a file and changes
    nothing on screen is the complaint this window has already been through
    twice.

    Measured on that pack: the seeded `report_2026-11-02_10-00-00.json` files
    carry an mtime of 2026-09-15 13:36:00 and the reports the tester generated
    carry 2026-09-15 13:36:11, so the file times say plainly what the names do
    not. A copy that loses the times (`cp` without `-p`) gives every file the
    same one and the name decides, exactly as it did before.
    """
    try:
        ns = (Path(origin) / "reports" / str(name)).stat().st_mtime_ns
    except OSError:
        ns = 0
    return (ns, _report_file_order(name))


def _report_created_at(entry: dict) -> str:
    """When one entry of "Report shown" was CREATED, as ISO text, for the
    order inside a group (#182 A9, Knut 5817809396: *"the recommended is
    accepted"*, newest first by the report's own creation date).

    **FROM THE DOCUMENT, NOT FROM THE FILE.** The list was ordered by the
    time the files were written (`_report_order`), so reports ChromIQ wrote
    itself came out right and copied or restored files did not: a demo
    project listed 2026-12-08 before 2026-12-15 (B8-843). A copy keeps what
    the file SAYS, so the order is read from there:

    1. the document's own ``created`` (every report since the document block,
       B8-383; an Update keeps it, spec §13.8);
    2. **a report with no document date** (written before the document
       block): the stamp `save_report` put in its file name,
       ``report_YYYY-MM-DD_HH-MM-SS``, the second it was saved;
    3. a name in no such shape: the file's own time, the only evidence left.

    The file time stays the tie-break (`_saved_documents` sorts on this and
    then on ``order``), so two reports of one second keep the order they were
    written in."""
    import re as _re
    doc = entry.get("doc") or {}
    created = str(doc.get("created") or "")
    if _re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", created):
        return created[:19]
    names = []
    if entry.get("file") is not None:
        names.append(Path(str(entry["file"])).name)
    names += [str(n) for _r, n in (entry.get("members") or [])]
    for name in names:
        m = _re.match(r"report_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})",
                      name)
        if m:
            return f"{m.group(1)}T{m.group(2)}:{m.group(3)}:{m.group(4)}"
    order = entry.get("order") or ()
    if order and order[0]:
        return datetime.fromtimestamp(order[0] / 1e9).isoformat(
            timespec="seconds")
    return ""


def _dir_ident(d: "Path") -> str:
    """A directory's identity on the disk, or its path when it has none.

    Device and inode are the same under every spelling that names the same
    mounted directory: `/tmp` and `/private/tmp`, a symlink, a firmlink
    (`/Users/...` and `/System/Volumes/Data/Users/...`), and a different
    capitalisation on a case-insensitive volume. `resolve()` collapses the
    first two and neither of the last two, which is how one measurement kept
    being added to a report twice. Two MOUNTS of one filesystem still give
    different numbers, which is a known limit and not something anybody has
    driven here.
    """
    try:
        st = d.stat()
        return f"{st.st_dev}:{st.st_ino}"
    except OSError:
        try:
            return str(d.resolve())
        except OSError:
            return str(d)


#: #182 A10: the note code of a sheet with no paper patch, and the key its
#: "Paper white" line takes in the one note numbering (it is no limit row).
NOTE_NO_PAPER_PATCH = "no_paper_patch"
PAPER_WHITE_NOTE_ROW = "paper_white"


def _no_paper_patch(r: dict) -> bool:
    """Whether the report of this sheet records that its chart has NO paper
    patch (#182 A10, `measurement_report.paper_white_row`). False for a
    report written before beta 42, which records nothing either way."""
    return isinstance(r, dict) and r.get("paper_patch") is False


#: #182 K37: the note code of a sheet judged relative to its PROFILE's paper
#: white, (e). It carries its own sentence after `_NOTE_TEXT_SEP` (the profile
#: and its white are the sheet's), so two sheets through one profile share a
#: number and two through different profiles do not.
NOTE_PAPER_WHITE_FROM_PROFILE = "paper_white_from_profile"


def _paper_white_from_profile(r: dict) -> "dict | None":
    """The profile's paper white a sheet with no paper patch was judged
    relative to (#182 K37, (e)), or None."""
    from workflow.measurement_report import PAPER_WHITE_FROM_PROFILE
    used = (r or {}).get("paper_white_used") if isinstance(r, dict) else None
    if isinstance(used, dict) and used.get("from") == PAPER_WHITE_FROM_PROFILE \
            and isinstance(used.get("lab"), (list, tuple)) \
            and len(used["lab"]) == 3:
        return used
    return None


def _paper_white_note_code(r: dict) -> "str | None":
    """The note code the "Paper white" line of this sheet carries, or None.

    * no paper patch, judged relative to the profile's paper white (K37,
      (e)): M-REPORT-PAPER-WHITE-FROM-PROFILE, filled in for this sheet;
    * no paper patch otherwise: M-REPORT-NO-PAPER-PATCH (A10), whose words
      ("judged as measured, in absolute Lab") are true of such a sheet and
      FALSE of an (e) sheet, which is why the two never share a line."""
    if not _no_paper_patch(r) or r.get("paper_white"):
        return None
    used = _paper_white_from_profile(r)
    if used is None:
        return NOTE_NO_PAPER_PATCH
    from workflow import measurement_messages as M

    def _n(v) -> str:
        return f"{round(float(v), 1) + 0.0:.1f}"
    said = M.M_REPORT_PAPER_WHITE_FROM_PROFILE.render(
        profile=str(used.get("profile") or ""),
        L=_n(used["lab"][0]), a=_n(used["lab"][1]), b=_n(used["lab"][2]))[1]
    return (NOTE_PAPER_WHITE_FROM_PROFILE
            + MeasurementReportDialog._NOTE_TEXT_SEP + said)


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


#: The height of one trend chart in the PDF, at its 640 px render width.
_PDF_TREND_H = 176
#: Colour accuracy is printed this many times taller (#182, Knut 5787117741:
#: *"a y-axis on the graph that is, for ex. twice as tall as the graph on
#: screen"*), so a change of a tenth of a ΔE00 between dates stays visible.
_PDF_ACCURACY_SCALE = 2
#: The report's running text, in the 96-dpi pixels the document is laid out
#: in: 12 px, which the PDF prints as 9 pt (the writer maps 96 px to 72 pt).
_BODY_TEXT_PX = 12


def _how_to_read_frame(doc):
    """The coloured frame of "How to read this report" in a laid-out report
    document: the first table after the block that heads it, or None."""
    from PyQt6.QtGui import QTextCursor
    want = tr("How to read this report")
    block = doc.begin()
    while block.isValid():
        if (block.text().strip() == want
                and QTextCursor(block).currentTable() is None):
            nxt = block.next()
            while nxt.isValid():
                table = QTextCursor(nxt).currentTable()
                if table is not None:
                    return table
                if nxt.text().strip():
                    return None
                nxt = nxt.next()
            return None
        block = block.next()
    return None


#: The radius of the marker of a series with a single value on a trend graph:
#: it has no line to be seen on, so it is drawn larger than a joined point.
_TREND_LONE_POINT_R = 4.0


#: The PDF's type size for a graph's description and its key (K25). The
#: two-line test measures at this size.
_TREND_ABOUT_PX = 11


def _trend_about_html(text: str) -> str:
    """The description above a graph in the PDF (at most two lines)."""
    if not text:
        return ""
    return (f"<div style='font-size:{_TREND_ABOUT_PX}px;color:{_LIGHT_REPORT['dim']};"
            f"margin:2px 0 4px'>" + html.escape(text) + "</div>")


def no_limit_note() -> str:
    """The sentence under a drawn graph that has no limit line (K47, Knut
    #182 5840152058). General, so it is true of every such graph: the paper
    white and darkest black L*, the cube corners, and colour accuracy on a
    report that judges no colour-accuracy row."""
    return tr("No limit applies to what this graph shows, so it has no "
              "limit line. It shows the trend only.")


def _trend_key_html(descriptions: list) -> str:
    """Under a graph in the PDF: each limit line's word and each red x, with
    the text its tooltip shows on screen. A line is keyed by a short dotted
    stroke in its own colour, a withheld date by a red x."""
    if not descriptions:
        return ""
    rows = []
    for kind, col, text in descriptions:
        if kind == "note":
            # K47: a graph with no limit says so, with no mark: there is no
            # line for a mark to stand for.
            rows.append(f"<div style='color:{_LIGHT_REPORT['dim']}'>"
                        + html.escape(text) + "</div>")
            continue
        mark = ("\u00d7" if kind == "mark" else "\u2508\u2508")
        rows.append(
            f"<div style='color:{_LIGHT_REPORT['dim']}'>"
            f"<span style='color:{col.name()};font-weight:bold'>{mark}</span>"
            "&nbsp;&nbsp;" + html.escape(text) + "</div>")
    # Divs, not a table: `_paginate_tables` moves the graph's own one-cell
    # table as a whole, and a table inside it would be a second one to move.
    return (f"<div style='margin:4px 0 0;font-size:{_TREND_ABOUT_PX}px'>"
            + "".join(rows) + "</div>")


#: How close (px) a word in the left margin may come to a y-axis number's
#: centre, or to another margin word's, before the two would print over each
#: other. The first is the rule the margin always had (9, which keeps the
#: 10 px numerals apart); the second is a whole word box (14), so two words in
#: the margin never touch (K32: no limit word may overlap another; it was 11,
#: and two boxes 11 px apart share 3 px).
_WORD_AXIS_GAP = 9.0
_WORD_WORD_GAP = 14.0
#: What a limit word placed with ANOTHER limit line between it and its own
#: costs in `_place_limit_words`: more than printing over a red x (500), a
#: limit line (50) or data, because a word read against the wrong line gives
#: the wrong limit; less than printing over another word (1000), which reads
#: as neither.
_WORD_PAST_ANOTHER_LINE = 800.0


def _segment_length_in(rect: "QRectF", a: "QPointF", b: "QPointF") -> float:
    """How much of the segment a-b lies inside *rect*, in px (sampled)."""
    import math
    n = max(2, int(math.hypot(b.x() - a.x(), b.y() - a.y()) / 2.0) + 1)
    step = math.hypot(b.x() - a.x(), b.y() - a.y()) / (n - 1)
    inside = 0
    for k in range(n):
        t = k / (n - 1)
        if rect.contains(QPointF(a.x() + (b.x() - a.x()) * t,
                                 a.y() + (b.y() - a.y()) * t)):
            inside += 1
    return inside * step


def _word_conflict(rect: "QRectF", own_y: float, line_ys: "list[float]",
                   polys: list, marks: list, taken: list) -> float:
    """What a limit word placed in *rect* would print over, as one number:
    another word or a red x above all, then another limit line, then the
    length of data line under it (K32)."""
    r = rect.adjusted(-1.0, -1.0, 1.0, 1.0)
    score = 0.0
    for other in taken:
        if r.intersects(other):
            score += 1000.0
    for m in marks:
        if r.intersects(m):
            score += 500.0
    for ly in line_ys:
        if ly is not own_y and r.top() <= ly <= r.bottom():
            score += 50.0
    if r.top() <= own_y <= r.bottom():
        score += 30.0                    # clamped onto its own line
    for poly in polys:
        for q in poly:
            if r.contains(q):
                score += 5.0             # a data point's dot
        for a, b in zip(poly, poly[1:]):
            score += _segment_length_in(r, a, b)
    return score


def _place_limit_words(words: list, *, L: float, T: float, h: float,
                       axis_ys: "list[float]", polys: list,
                       marks: list) -> list:
    """Where each limit word of a trend graph goes: ``[(QRectF, where)]`` in
    the order of *words*, which are ``(line y, text width)``.

    **THE RULE, ONE FOR EVERY GRAPH, THE WINDOW AND THE PDF (K32, Knut on
    beta 41, #182 5814107188).**

    1. **The left margin, centred on its line**, when it fits there: the word
       is no wider than the margin, and it lands on no y-axis number
       (`_WORD_AXIS_GAP`) and on no word already put in the margin
       (`_WORD_WORD_GAP`). This is the Colour accuracy placement Knut
       pointed at.
    2. **Otherwise at the left end of its line** (K26: "it stays at the left
       end even over a line"), **above or below it, on the side that
       conflicts least** (`_word_conflict`): with another word or a red x
       first, then with another limit line, then with the data lines. On a
       tie, above.

    A word decided alone: one that does not fit the margin no longer sends
    the others inside with it, which is what put Grey balance's "Avg" under
    its line with a free margin beside it.
    """
    line_ys = [y for y, _w in words]
    out: list = [None] * len(words)
    taken: "list[QRectF]" = []
    margin_room = L - 4.0 - 2.0
    # The margin first, top to bottom, so a later word never displaces one
    # already there.
    order = sorted(range(len(words)), key=lambda i: words[i][0])
    for i in order:
        y, tw = words[i]
        fits = (tw <= margin_room
                and all(abs(y - ay) >= _WORD_AXIS_GAP for ay in axis_ys)
                and all(abs(y - out[j][0].center().y()) >= _WORD_WORD_GAP
                        for j in range(len(words))
                        if out[j] is not None and out[j][1] == "margin"))
        if fits:
            rect = QRectF(L - 4.0 - tw - 2.0, y - 7.0, tw + 4.0, 14.0)
            out[i] = (rect, "margin")
            taken.append(rect)
    for i in order:
        if out[i] is not None:
            continue
        y, tw = words[i]
        best = None
        # Just above and just below the line first; a step further out on
        # either side only when both of those print over something (another
        # word most of all, which near the plot's edge the clamp can cause),
        # at a small cost per step so the word stays by its own line.
        for step in range(0, 5):
            for where, top in (("above", y - 16.0 - 15.0 * step),
                               ("below", y + 2.0 + 15.0 * step)):
                top = min(max(top, T), T + h - 14.0)
                rect = QRectF(L + 4.0 - 1.0, top, tw + 2.0, 14.0)
                score = (_word_conflict(rect, y, line_ys, polys, marks, taken)
                         + 2.0 * step)
                # **BESIDE ITS OWN LINE, NEVER PAST ANOTHER ONE (challenge 2
                # of beta 42, #4).** With Max's word in the margin and the
                # Avg line a few pixels under it, Avg's word went a step up
                # and landed ABOVE the Max line: clear of everything, and
                # read as Max's. A place with another limit line between the
                # word and its own line costs more than anything but another
                # word, so the word takes the side away from the other line.
                cy = rect.center().y()
                if any(ly != y and min(cy, y) < ly < max(cy, y)
                       for ly in line_ys):
                    score += _WORD_PAST_ANOTHER_LINE
                if best is None or score < best[0]:
                    best = (score, rect, where)
        out[i] = (best[1], best[2])
        taken.append(best[1])
    return out


class _TrendKey(QLabel):
    """The limit-line key under the trend graph in the window (K45-2).

    **IT TAKES NOTHING FROM THE GRAPH.** A plain word-wrapped label counts in
    the window's minimum height, and the height ladder of `showEvent` /
    `_fit_to_screen` then took its lines out of the graphs: measured on
    screen at 1400 x 980, the Grey balance graph went from 110 px to 61 px
    with its axis numbers printed over each other. So this label asks for
    its lines only as its PREFERRED height and has no minimum: where the
    window has room (the report view under it takes the surplus) it gets all
    of them, and where it has none it is the first thing to give way."""

    def hasHeightForWidth(self) -> bool:  # noqa: D401
        return False

    def heightForWidth(self, _w: int) -> int:  # noqa: N802
        # Qt's layout item asks this WITHOUT asking `hasHeightForWidth`
        # first, and QLabel answers with its wrapped height at the window's
        # narrowest width: 157 px of need for two lines of key (measured).
        return -1

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(0, 0)

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        if not self.text():
            return QSize(0, 0)
        w = max(200, self.width())
        return QSize(w, super().heightForWidth(w))

    def resizeEvent(self, ev) -> None:  # noqa: N802
        super().resizeEvent(ev)
        if ev.oldSize().width() != ev.size().width():
            self.updateGeometry()


class _TrendChart(QWidget):
    """A compact multi-line chart of a printer's measurement history over time
    (#40, Knut). Generic: each instance plots one GROUP of related metrics
    (ΔE00 accuracy, paper white/black, or the eight cube corners) so unlike
    scales never share an axis. A metric is ``(label, QColor, accessor)`` where
    ``accessor(point)`` returns the value or ``None``. Hidden until ≥2 points.
    ``unit_dec`` sets the y-label decimals; ``y_max`` optionally pins the top
    (e.g. 100 for L*).

    #182 K25 (Knut, 5789263863): every limit line's word explains itself
    (``line_notes``, a tooltip here and the same text under the graph in the
    PDF, `descriptions`), and a date whose value was withheld is drawn as a
    small red x (``withheld``) instead of disappearing from the axis."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._series: list[dict] = []
        self._metrics: list = []
        self._dark = True
        self._y_max: "float | None" = None
        self._dec = 1
        self._auto = False
        self._thresholds: "tuple[float, float] | None" = None
        self._limit_lines: list = []
        self._line_notes: list = []
        self._withheld: list = []
        #: ``[(QRectF, text)]`` of everything painted that explains itself,
        #: refreshed by every paint, read by the tooltip (`event`).
        self._hits: list = []
        self.setMinimumHeight(150)

    def set_data(self, series, metrics, dark=True, y_max=None, dec=1,
                 auto=False, thresholds=None, limit_lines=None,
                 line_notes=None, withheld=None) -> None:
        # One entry per metric: ``withheld[k](pt)`` is the sentence saying
        # why metric k's value on that date is not drawn, or None.
        wh = list(withheld or [])
        self._withheld = (wh + [None] * len(metrics))[:len(metrics)]

        def has_any(pt) -> bool:
            # A DATE WITH A WITHHELD VALUE STAYS ON THE AXIS (K25). It used to
            # be dropped here when no other metric of the tab had a value on
            # it, so a four-date evenness report drew three dates and said
            # nothing about the fourth.
            return (any(acc(pt) is not None for _, _, acc in metrics)
                    or any(f is not None and f(pt) for f in self._withheld))
        self._series = [p for p in (series or []) if has_any(p)]
        #: How many measurements the graph was GIVEN, before the dates with
        #: nothing to draw were dropped: the empty graph's reason depends on
        #: it (challenge 5 of beta 42, B8-1095; B8-1084).
        self._n_given = len(series or [])
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
        # #182 K20/K21: one dotted limit line PER METRIC on the judged-metric
        # tabs, ``[(value, word, QColor)]``, drawn by the same code as the
        # pair above. The pair keeps its own name and grey pen: it is what
        # the R24-F3 guard watches, and its two lines serve five metrics.
        self._limit_lines = list(limit_lines or [])
        # K25: the sentence each line's word stands for, in the order of the
        # pair or of ``limit_lines``.
        self._line_notes = list(line_notes or [])
        # NB: visibility is owned by the container (the tab widget), NOT the
        # chart — a per-widget setVisible here fought the tab stack and made all
        # three pages paint on top of each other before layout settled.
        self.update()

    def empty_reason(self) -> str:
        """Why this graph draws no trend, in the one reason that is true
        (challenge 5 of beta 42, B8-1095, the pattern of B8-1084).

        "Needs at least two measurements" was printed whatever the cause, so
        the Control strip graph of a Full colour check said it over three
        ticked dates: the type judges no strip row, and the graph had no
        line to draw at all. And a graph given two or more dates of which
        fewer than two carry its value (Paper white on sheets with no paper
        patch, B8-1084) was told to add measurements it already had."""
        if not getattr(self, "_metrics", None):
            return tr("This report judges none of this graph's rows, so it "
                      "has nothing to draw. Choose a report type or a limit "
                      "set that judges them to see their trend.")
        if getattr(self, "_n_given", 0) >= 2:
            # K39-1: this graph is printed in the PDF, so it names no part
            # of the window ("the ticked measurements").
            return tr("Fewer than two of the measurements in this report "
                      "have a value for this graph, so it draws no trend. "
                      "The notes under the results say why a value is "
                      "missing.")
        return tr("A trend graph needs at least two measurements. "
                  "Add another measurement, or tick more of the measurements "
                  "in the list above. “Select all” ticks every one of "
                  "them.")

    def has_trend(self) -> bool:
        return len(self._series) >= 2

    # ---- K25: lines, words and red marks, described ------------------------
    def _lines(self) -> list:
        """``[(value, word, QColor | None, note)]`` for every limit line."""
        # The accuracy graph's grey pair FIRST, then any line of its own a
        # judged row needs that neither of the pair stands for (K45-2: a P95
        # limit set apart from the Max one); every other graph has only
        # `limit_lines`.
        raw = []
        if self._thresholds:
            raw = [(tv, tlab, None) for tv, tlab in
                   zip(self._thresholds, (tr("Avg"), tr("Max")))]
        raw += list(self._limit_lines)
        notes = self._line_notes + [""] * len(raw)
        return [(tv, tlab, tcol, notes[k])
                for k, (tv, tlab, tcol) in enumerate(raw)]

    def _date_label(self, i: int) -> str:
        """The x-axis label of date *i*: the day, and the time as well when
        several measurements share that day ("2026-08-10 11:36", Knut)."""
        pts = self._series
        c = str(pts[i].get("created") or "")
        days = [str(pt.get("created") or "")[:10] for pt in pts]
        if days.count(c[:10]) > 1 and len(c) >= 16:
            return f"{c[:10]} {c[11:16]}"
        return c[:10]

    def withheld_marks(self) -> list:
        """``[(metric index, date index, height or None, tooltip)]``: every
        red x, with the height `_withheld_mark_value` gives it (None is the
        floor just above the x-axis)."""
        out = []
        if len(self._series) < 2:
            return out
        for k, (lbl, _col, acc) in enumerate(self._metrics):
            f = self._withheld[k] if k < len(self._withheld) else None
            if f is None:
                continue
            values = [acc(pt) for pt in self._series]
            for i, pt in enumerate(self._series):
                reason = f(pt)
                if not reason:
                    continue
                out.append((k, i, _withheld_mark_value(values, i),
                            tr("{date}, {metric}: not judged, because "
                               "{reason}.").format(
                                   date=self._date_label(i), metric=lbl,
                                   reason=reason)))
        return out

    def descriptions(self) -> list:
        """What the PDF prints under the graph: ``[(kind, QColor, text)]``,
        one per limit line (kind ``"line"``) then one per red x (``"mark"``).
        The text is the tooltip's, word for word; a line outside the plotted
        range, which has no word on the graph to point at, says so."""
        out = []
        grey = QColor(120, 120, 120)
        vmin, vmax = self._y_range() if len(self._series) >= 2 else (None, None)
        for tv, _w, tcol, note in self._lines():
            if not note or not isinstance(tv, (int, float)):
                continue
            if vmin is not None and not (vmin <= tv <= vmax):
                note = note + " " + tr("Outside the range of values shown.")
            out.append(("line", QColor(tcol) if tcol is not None else grey,
                        note))
        # K47 (Knut, #182 5840152058, on a graph with no limit: *"If this is
        # not noted other places, then a short note could say so under the
        # graphs."*). Nothing near a graph said it: the detailed data's "For
        # information (no limit applies)" is pages away and names no graph.
        # So a drawn graph with no limit line says why it has none.
        if (len(self._series) >= 2 and self._metrics
                and not any(k == "line" for k, _c, _t in out)):
            out.insert(0, ("note", grey, no_limit_note()))
        for _k, _i, _v, text in self.withheld_marks():
            out.append(("mark", QColor(_WITHHELD_RED), text))
        return out

    def event(self, ev) -> bool:  # noqa: D401
        from PyQt6.QtCore import QEvent
        if ev.type() == QEvent.Type.ToolTip:
            from PyQt6.QtWidgets import QToolTip
            pos = QPointF(ev.pos())
            for rect, text in self._hits:
                if rect.contains(pos):
                    QToolTip.showText(ev.globalPos(), _tip_rich(text), self)
                    return True
            QToolTip.hideText()
            ev.ignore()
            return True
        return super().event(ev)

    def tooltip_at(self, pos: "QPointF") -> "str | None":
        """The tooltip a pointer at *pos* is shown (after a paint)."""
        for rect, text in self._hits:
            if rect.contains(pos):
                return text
        return None

    def _y_range(self) -> "tuple[float, float]":
        """The plotted y-range, from the DATA alone.

        A limit line never widens it (Knut, 5787117741: a threshold far from
        the trend *"is outside of the view shown for the y-scale, until a
        change in the measurement happens that creates a dip/spike large
        enough to change the y-scale"*), so a small drift keeps its height."""
        import math
        vals = [v for pt in self._series for _, _, acc in self._metrics
                if (v := acc(pt)) is not None]
        if self._auto and vals:
            dmin, dmax = min(vals), max(vals)
            pad = 0.3 if (dmax - dmin) < 1e-9 else (dmax - dmin) * 0.15
            return (math.floor((dmin - pad) * 10.0) / 10.0,
                    math.ceil((dmax + pad) * 10.0) / 10.0)
        return 0.0, (self._y_max if self._y_max else max(vals + [1.0]) * 1.12)

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
        self._hits = []
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
                self.empty_reason())
            p.end()
            return
        vmin, vmax = self._y_range()
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

        # One polyline per metric. Kept (K32) so the limit words can be
        # placed where they cross the least of them.
        self._polys = []
        for _lbl, col, acc in self._metrics:
            poly = [xy(i, v) for i, pt in enumerate(pts)
                    if (v := acc(pt)) is not None]
            if not poly:
                continue
            self._polys.append(poly)
            p.setPen(QPen(col, 2.0))
            for a, b in zip(poly, poly[1:]):
                p.drawLine(a, b)
            # A SERIES WITH ONE VALUE IS STILL A VALUE (round B before beta
            # 37, H6). "The same chart measured again" has nothing to compare
            # on a chart's first date, so on a three-date report it has one
            # value, 1.45 and PASS in the table, and `len(poly) < 2` skipped
            # it: the axis was sized to hold it and the graph drew nothing. A
            # lone point has no line to be seen on, so its marker is larger.
            p.setBrush(col); p.setPen(Qt.PenStyle.NoPen)
            r_dot = 2.4 if len(poly) > 1 else _TREND_LONE_POINT_R
            for q in poly:
                p.drawEllipse(q, r_dot, r_dot)

        # THE RED X (K25, Knut 5789263863): a date whose value was withheld,
        # at its neighbour's height, their mean, or just above the x-axis.
        self._marks = []
        xpen = QPen(QColor(_WITHHELD_RED), 2.0)
        xpen.setCapStyle(Qt.PenCapStyle.RoundCap)
        arm = _WITHHELD_ARM
        centres = _stack_withheld_marks(
            [(i, (xy(i, val) if val is not None
                  else QPointF(L + (w * i / (n - 1)),
                               T + h - _WITHHELD_FLOOR_PX)))
             for _k, i, val, _t in self.withheld_marks()], T, T + h)
        for (_k, i, val, text), c in zip(self.withheld_marks(), centres):
            p.setPen(xpen)
            p.drawLine(QPointF(c.x() - arm, c.y() - arm),
                       QPointF(c.x() + arm, c.y() + arm))
            p.drawLine(QPointF(c.x() - arm, c.y() + arm),
                       QPointF(c.x() + arm, c.y() - arm))
            box = QRectF(c.x() - arm - 3, c.y() - arm - 3,
                         2 * arm + 6, 2 * arm + 6)
            self._hits.append((box, text))
            self._marks.append(box)

        # Limit lines: the accuracy chart's grey Avg / Max pair, or one line
        # per metric on a judged-metric tab (#182 K20/K21) — dotted, and only
        # while they fall inside the visible y-range (Knut).
        grey_line = QColor(150, 150, 150) if self._dark else QColor(120, 120, 120)
        lines = self._lines()
        if lines:
            inside = [(tv, tlab, tcol, note) for tv, tlab, tcol, note in lines
                      if isinstance(tv, (int, float)) and vmin <= tv <= vmax]
            thr = [(tv, tlab) for tv, tlab, _c, _n in inside]
            notes = [note for _tv, _tl, _c, note in inside]
            pens = []
            for _tv, _tlab, tcol, _n in inside:
                tpen = QPen(QColor(tcol) if tcol is not None else grey_line)
                tpen.setStyle(Qt.PenStyle.DotLine); tpen.setWidthF(1.2)
                pens.append(tpen)
            # WHERE EACH WORD GOES (K32, Knut on beta 41, #182 5814107188).
            # *"If there is no space on the left edge for the threshold label
            # (maybe because the label then would crash with the y-axis
            # numbered axis labels), then the label should find a better
            # location, like on top or below the threshold line it belongs
            # to ... the label must be placed on the top or bottom side that
            # has the least conflict with other graph lines or other
            # horizontal threshold lines. This must be a general rule for all
            # the graphs label placement for the threshold lines."* Until
            # then one word that did not fit the margin sent EVERY word of
            # the graph inside, the upper above and the lower below whatever
            # was drawn there: on Grey balance the Avg word left a free margin
            # for a place under its line, on a data line. Now each word is
            # placed on its own, by `_place_limit_words`, the one rule every
            # tab and the PDF use.
            axis_ys = [T + h * (1.0 - f) for f in (0.0, 0.5, 1.0)]
            #: The plot as this paint laid it out, for a test and a driver
            #: to measure the words against.
            self._plot_geom = (T, h, list(axis_ys))
            thr_ys = [T + h * (1.0 - (tv - vmin) / span) for tv, _ in thr]
            for (tv, tlab), yy, tpen in zip(thr, thr_ys, pens):
                p.setPen(tpen)
                p.drawLine(QPointF(L, yy), QPointF(L + w, yy))
            p.setPen(QPen(fg, 1.0))
            fm = p.fontMetrics()
            placed = _place_limit_words(
                [(yy, fm.horizontalAdvance(tlab)) for (_tv, tlab), yy
                 in zip(thr, thr_ys)],
                L=L, T=T, h=h, axis_ys=axis_ys,
                polys=getattr(self, "_polys", []),
                marks=getattr(self, "_marks", []))
            #: ``[(QRectF, where, line y)]`` per drawn word, for a test and a
            #: driver to measure what was placed where ("margin" / "above" /
            #: "below").
            self._word_boxes = []
            for (tv, tlab), yy, note, (rect, where) in zip(thr, thr_ys, notes,
                                                           placed):
                if where == "margin":
                    p.drawText(QRectF(0, rect.center().y() - 7, L - 4, 14),
                               Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter, tlab)
                else:
                    p.drawText(QRectF(rect.left() + 1, rect.top(), 80, 14),
                               Qt.AlignmentFlag.AlignLeft
                               | Qt.AlignmentFlag.AlignVCenter, tlab)
                self._word_boxes.append((QRectF(rect), where, yy))
                if note:
                    self._hits.append((QRectF(rect), note))

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

        # Several checks on one day: the date alone reads as the same point
        # over and over, so those labels carry the time as well
        # ("2026-08-10 11:36" — Knut, 2026-08-11). Unique days stay short.
        _lab = self._date_label

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


#: **WHICH SET SUITS WHICH TYPE, AND WHAT THE CHART HAS TO DO WITH IT.** Knut,
#: 2026-09-14: *"the help text for the report type and judged against must
#: describe properly what each option are, when they are normally used, and
#: which Judged against limit sets are normally matched with which report type.
#: It should also be explained how report type and limit sets depend on
#: selection of the right chart / preset to be used and how the colors in that
#: chart is selected for verification."*
#:
#: The two paragraphs are shared by BOTH tooltips, because the question reads
#: the same from either control and a reader opens whichever one they are
#: standing on. The per-type descriptions are not repeated here: they are data
#: (`measurement_report.REPORT_TYPE_MENU`), already translated, and
#: :func:`_types_and_pairing_help` lists them from there so a seventh type
#: cannot appear in the pulldown and be missing from the help.
#: WHEN A READER WOULD REACH FOR EACH ONE. The menu's own blurbs say what a
#: type IS; this says on which day you pick it, which is the half of Knut's
#: question the data cannot answer for itself.
_WHEN_HELP = (
    "When you would reach for each. Full colour check is the one you keep: "
    "everything ChromIQ measures, for your own eye and for the record. Colour "
    "summary is the page you hand over with the job, one sheet somebody can "
    "read without knowing the vocabulary. Grey and tone check is for chasing "
    "a neutral problem, when greys go warm or the mid-tones sit heavy and the "
    "colour rows are only noise. Printing record is the report of a "
    "profiling measurement: the sheet a profile was built from, recorded and "
    "not graded. A file outside a project can have it too. "
    "The two ISO types are for a print that has to answer to a "
    "printing condition somebody else supplied: Validation print check for "
    "a validation print, Contract proof check for a contract proof. Either "
    "can be chosen for a verification run while that standard's values are "
    "loaded, as they are when ChromIQ is installed; if one is greyed, "
    "pointing at it says why.")
_PAIRING_HELP = (
    "Which limit set suits which type. Full colour check and Colour summary "
    "are the everyday pair for ChromIQ default, the set for checking a profile "
    "you built: 2.0 average and 3.0 maximum on the colour difference rows. "
    "ChromIQ tight halves those two, for critical work once a printer is "
    "behaving, and Quick check doubles them, for a health check only a clearly "
    "drifted printer fails; the grey rows move with them. Grey and "
    "tone check keeps three rows, the two grey balance ones and the mid-tone "
    "ramp. A ChromIQ set judges the two grey rows like any other row and puts "
    "no limit on the mid-tone ramp, so that row is left out of the report. "
    "The read-only ISO 12647-8 set and both Custom ISO sets judge all three; "
    "the read-only ISO 12647-7 set judges the two grey rows and puts no limit "
    "on the ramp. "
    "Printing record grades nothing: every row it can compute reads INFO "
    "whichever set is beside it, though the document still names the set it "
    "would otherwise have used. The two ISO types belong with the matching "
    "ISO set: the read-only one, which holds that standard's published "
    "values, or the Custom ISO set of the same number, the industry-practice "
    "alternative you can tune. For those two types that is a rule: choosing "
    "one keeps “Judged against” when it is one of the four ISO sets and "
    "otherwise sets it to that type's own ISO set, and only the four ISO "
    "sets can be chosen beside it; the others are greyed. Choosing another "
    "type then puts back the set the ISO type replaced. Every other type "
    "can be judged against any set, and the pairs above are the usual "
    "habits, not rules.")
#: The minimum width of the "Judged against" and "Report type" help windows
#: (K33, B8-992). Measured on screen before: both opened 616 x 971 px on a
#: 1728 x 1079 screen, the body scrolling. At 900 a line holds about 130
#: characters, still well inside a laptop screen, and the window is about as
#: wide as the Measurement Report window it is opened from.
JUDGED_AGAINST_HELP_WIDTH = 900

#: **WHEN EACH STANDARD'S SETS ARE THE RIGHT CHOICE** (K33, B8-993). Knut,
#: #182 5816565326: *"I cannot find any recommendation of what type of
#: situation the ISO limit sets normally would be used for."* Shown in the
#: "Judged against" help and in the Report limits window's title help. It
#: says what each standard is FOR and never that a print conforms to one.
_ISO_USE_HELP = (
    "When to judge against which set. ISO 12647-7 is the standard for "
    "contract proofs: a hard-copy proof made on a proofing system, which the "
    "printer and the customer agree shows the colour the job will have. "
    "Choose “ISO 12647-7:2016 values” when a print has to stand in for such "
    "a proof. ISO 12647-8 is the standard for validation prints: a print that "
    "shows the intended colour of a job, less strictly than a contract proof, "
    "for example to approve a layout or a design. Choose “ISO 12647-8:2021 "
    "values” for those. The two Custom ISO sets are an alternative to the "
    "standards' own numbers: they start from limits researched from industry "
    "practice, and every limit in them can be changed, so you can tune them "
    "to what you and your customer agree. ChromIQ's own sets are for your own "
    "printer: ChromIQ default for checking a profile you built, ChromIQ tight "
    "for critical work, and Quick check for a routine health check. Whichever "
    "you choose, ChromIQ measures and reports how close the print came; it "
    "does not certify that a print conforms to a standard.")
_CHART_HELP = (
    "And the chart you printed decides what any of it can say. A row is judged "
    "only when the sheet carries the patches that row needs: at least eight "
    "grey steps from white to black, spread roughly evenly, for the grey rows "
    "(on a chart built with FROM PROFILE GAMUT these are its neutral aims), a "
    "single-ink or grey ramp with three roughly evenly spaced steps through "
    "the mid-tones for the tone row (on such a chart its neutral aims in the "
    "mid-tones, 30 % to 70 % of the way from its paper to its darkest neutral "
    "aim, are that grey ramp too), and, for the paper and solid "
    "rows, a chart built with FROM PROFILE GAMUT on the Create Chart tab. That "
    "one picks its colours from what your own profile can actually print and "
    "carries an aim value for each of them, which is the thing those rows are "
    "measured against. An ordinary test chart carries no such aim values, and "
    "what you see then depends on the set: a ChromIQ set puts no limit on "
    "those rows anyway, so they are left out of the table altogether, while "
    "the ISO sets, the two read-only ones and the two Custom ones, limit some "
    "or all of them, show those as N-A, and the note under the results says "
    "what the chart was missing. Each row's own info icon in the Report limits "
    "window says what that row needs, and what to change where anything can "
    "be.")


def _types_and_pairing_help() -> str:
    """The six types with their own one-line descriptions, then the two shared
    paragraphs. Built from the menu data so the help cannot fall behind it.

    **ONE BULLET PER OPTION (B8-525).** Knut, beta 26: *"The report type and
    judged agains help text need to be more organised with bullets for each
    option."* The lines were already one per type; what they lacked was the
    mark that says so, and the room a blank line gives each of them.

    **AND THE COLOUR SUMMARY SAYS WHAT IT CANNOT DO.** Same review: *"If the
    one page 'Colour summary' only can contain ONE measurement, that is not
    specified anywhere, and it that is correct, it needs to be specified in the
    help text."* It can hold one, it has never held more, and it has no
    detailed section -- so the bullet says all three, where he looked for it.
    """
    from workflow.measurement_report import (REPORT_TYPE_MENU,
                                             REPORT_TYPE_SUMMARY)
    # …AND BOTH HALVES OF THAT SENTENCE WERE MADE FALSE BY B8-590, which
    # removed "Show all measurement runs" AND the freeze the sentence
    # promised. The commit reset the list's own tooltip and missed this one,
    # so the Report type help went on naming a control the window no longer
    # builds and a restriction it no longer applies, in all thirteen
    # languages: German readers got a false sentence in German. What the
    # window really does is `_sync_type_combo`'s live list plus
    # `_conflicts_with_the_ticks`, and this now says exactly that, in the
    # words the list's own tooltip already uses.
    one_page = tr("This one is about a single measurement: the sheet this "
                  "window is open on. Tick the one you want the page to be "
                  "about; if more than one is ticked when you click Generate "
                  "report, ChromIQ says so and asks you to choose. There is "
                  "no detailed section, because the whole report is one page "
                  "to print and hand over with a job.")
    lines = []
    for tid, name, blurb, _built in REPORT_TYPE_MENU:
        line = "\u2022 " + f"{tr(name)}: {tr(blurb)}"
        if tid == REPORT_TYPE_SUMMARY:
            line += " " + one_page
        lines.append(line)
    # WHICH ONES YOU CAN CHOOSE, AND WHEN (K13, Knut on beta 34): *"The help
    # text for the report type needs to explain when which report types are
    # available."*
    when_available = tr(
        "Which of them you can choose depends on the measurement the window is "
        "open on. A profiling measurement is the sheet a profile was built "
        "from, so its only report is the Printing record. A verification "
        "measurement is judged, so it can have every other type, and the "
        "Printing record is not offered for it. A measurement outside any "
        "project can have any type ChromIQ can produce. With Run type "
        "Calibration, the calibration run's measurement can have every type "
        "but the Printing record and the two ISO types; its limit set can "
        "still be an ISO one. The report ChromIQ "
        "writes by itself after a measurement follows the same rule. The "
        "type you choose belongs to the report shown and is stored with it "
        "when you press Generate report, never on a profile run.")
    return ("\n\n" + tr("What each one is for") + "\n\n"
            + "\n\n".join(lines)
            + "\n\n" + when_available
            + "\n\n" + tr(_WHEN_HELP)
            + "\n\n" + tr(_PAIRING_HELP) + "\n\n" + tr(_CHART_HELP))


def _run_tag(run_folder: str) -> str:
    """``Run1`` for the folder ``run1`` (K25 headings, K26 Profiling names);
    a folder that is not ``runN`` keeps its own name."""
    import re as _re
    m = _re.fullmatch(r"run(\d+)", str(run_folder or ""))
    return (tr("Run{number}").format(number=m.group(1)) if m
            else str(run_folder or ""))


def _sets_help() -> str:
    """Every limit set, one bullet each, from the catalogue that defines them.

    The other half of B8-525. The "Judged against" help described what a limit
    set IS and what the two controls beside it do, and never listed the sets a
    reader is choosing between; those sentences existed only as the pulldown's
    per-row tooltips, which a reader has to hover one at a time to collect.
    """
    from workflow.compliance_sets import SETS
    lines = ["\u2022 " + f"{tr(s.label)}: {tr(s.blurb)}"
             for s in SETS if s.blurb]
    return ("\n\n" + tr("What each set is") + "\n\n" + "\n\n".join(lines))


def _recommended_limit_note() -> str:
    """The body of M-LIMIT-RECOMMENDED, as one line of running text.

    The catalogue stores a body; this is what a note item in a list wants, so
    the paragraph breaks are flattened here rather than by each caller. The
    Report limits window asks the same function, which is why the number beside
    a metric there and the number beside a verdict here say the same thing.
    """
    from workflow.measurement_messages import M_LIMIT_RECOMMENDED
    _title, body = M_LIMIT_RECOMMENDED.render()
    return " ".join(body.split())


def _reflow_row(layout, sizes, parent, **kw):
    """The widgets of the one-line *layout*, in order, as a `ReflowRow` of
    groups of *sizes* widgets each (B8-927): at a width that cannot hold them
    on one line the later groups start a second one, instead of being drawn
    over each other. Spacer items in *layout* are dropped."""
    from ui.widgets import ReflowRow
    ws = [layout.itemAt(i).widget() for i in range(layout.count())]
    ws = [w for w in ws if w is not None]
    assert sum(sizes) == len(ws), (sizes, len(ws))
    row = ReflowRow(parent, **kw)
    i = 0
    for n in sizes:
        row.add_group(*ws[i:i + n])
        i += n
    return row


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
        #: the measurements a selected report loaded (A-F1), which leave with
        #: it (`_drop_borrowed_sources`, recheck R1)
        self._borrowed_sources: "set[str]" = set()
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
            "Three ways to use it\n"
            "  • Profiling runs: after building a profile, check how faithfully "
            "the chart reproduced.\n"
            "  • Verification runs: the most valuable habit: print a small chart "
            "THROUGH your finished profile (a colour-managed print, made "
            "with Run type Verification), measure it "
            "every so often, and save a report each time. When the Pass/Fail "
            "results start slipping, that's your sign the printer has drifted far "
            "enough to re-profile. A tiny verification chart is enough; you're "
            "watching the trend, not building a profile.\n"
            "  • Calibration: with Run type Calibration, the window opens on "
            "the project's calibration measurement. It can have every report "
            "type but the Printing record, and its reports are kept in the "
            "project's cal/reports folder.\n\n"
            "Building the report\n"
            "The report covers a list of profiles' measurements, shown in the "
            "list box. Use “Add Profile's Measurements…” to add a profile (pick "
            "any of its .ti3 files and ChromIQ gathers all its runs), and "
            "“Remove Profile's Measurements…” / “Clear List” to take profiles out. "
            "Tick the measurements the report is to cover: it covers exactly "
            "those, and nothing else. “Select all” and “Deselect all” beside "
            "the list tick and untick every row at once. The trend graphs "
            "need at least two measurements; with a single measurement each "
            "graph is drawn empty "
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
            "  • Report Results: a word per row and run (PASS, FAIL, INFO or "
            "N-A), with the column's Overall word, which may also read COND, "
            "and what it was judged against.\n"
            "  • Colour accuracy: the ΔE00 (colour difference) figures, split so "
            "the bulk of the chart (all patches, and the lowest 95 %) is "
            "separated from the few hardest patches (the highest 5 %). Each is "
            "judged against "
            "the report's limit set. 0 is perfect, 1–2 is barely visible, 10+ "
            "is clearly wrong.\n"
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
            "built; ChromIQ tight is half of that, Quick check twice. The set "
            "belongs to the report: every measurement ticked in it is judged "
            "with the same numbers, so the dates in one report are always "
            "comparable, and a saved report keeps the set it was made with. "
            "Open the limits table with “Edit limits…” to see every set side "
            "by side and this report's own limits beside them; edit the sets "
            "in Preferences → Reports.\n\n"
            "Options\n"
            "  • Select all / Deselect all: tick or untick every measurement "
            "in the list at once. They change nothing else.\n"
            "  • Show detailed data for each run: add the per-run breakdown.\n"
            "  • Save report as PDF: a ChromIQ-styled PDF you can keep or share; "
            "it opens automatically. Reveal folder opens the folder of the "
            "first measurement in the list, or its project folder for a "
            "profile run's own measurement.\n\n"
            "Using i1Profiler measurements\n"
            "You can feed this report measurements made in i1Profiler (handy when "
            "you measured with an i1iSis or i1iO, which lay out their own charts). "
            "Add i1Profiler's own saved file (.mxf), a text export (.txt) or a "
            "CxF file (.cxf) directly with “Add Profile's Measurements…”; "
            "ChromIQ converts it for you, and no export or convert step is "
            "needed.\n"
            "That's all; you get the full colour-accuracy figures, no extra "
            "reference file needed. ChromIQ works out each patch's expected colour "
            "from the device values recorded in the file (the RGB / ink code "
            "values sent to the printer, which are the chart's fixed design and "
            "the same for every print), so the reference stays just as static "
            "across runs as a .ti2 would. (If a matching .ti2 happens to sit next "
            "to the .ti3, that's used instead.) The instrument is read from the "
            "i1Profiler file.\n"
            "Keeping things tidy: keep your i1Profiler files in a folder of "
            "their own. The PDF report of such a file is offered in a reports "
            "folder beside it, so your i1Profiler work stays together and "
            "separate from ChromIQ's own profile folders.\n\n"
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

        # ------------------------------------------------------------------
        # KNUT'S BETA-25 MOCKUP, and it supersedes L.8 (B8-460)
        # ------------------------------------------------------------------
        # `~/Desktop/ChromIQ-knut-beta25-batch/mockup-report-window-layout.png`,
        # 2026-09-19: *"Note that a frame called 'Report settings' encompass all
        # the relevant buttons and input controls that are related to the
        # settings for a report. The report shown is above the frame, with its
        # help icon, and two text elements: the text 'Click a report to load …'
        # to the right of the 'report shown' (and its help icon) and the
        # 'Already generated…' below the 'report shown' input box. Below the
        # 'Report settings' frame there are 4 buttons and a help icon (starting
        # left with Generate Report, then Delete Selected Report, then Save
        # Report As PDF, then Reveal Folder, then help icon). Inside the
        # 'Report settings' frame all the remaining buttons and elements are
        # placed carefully."*
        #
        # L.8 put Generate report and Delete Selected Report beside the "Report
        # shown" pulldown, which is where beta 22 shipped them. This moves both
        # into the action row under the frame; the pulldown keeps its own help
        # button and its hint, which is the half of L.8 his mockup keeps.
        #
        # The containers are built HERE, before the widgets that go in them, so
        # that the order they are added to `top_v` is the order on his image.
        # Every widget below is created exactly where it was; only the layout
        # it is put into changed.
        from PyQt6.QtWidgets import QGridLayout, QGroupBox
        #: "Report shown", its help, its hint and the "Already generated" line.
        #: A grid, so the second row starts at the pulldown's left edge, which
        #: is where his mockup puts it.
        shown_grid = QGridLayout()
        shown_grid.setHorizontalSpacing(8)
        shown_grid.setVerticalSpacing(2)
        shown_grid.setContentsMargins(0, 0, 0, 0)
        #: The frame. Its title is the one new string this layout needs.
        self._settings_box = QGroupBox(tr("Report settings"), self)
        box_v = QVBoxLayout(self._settings_box)
        # **TIGHT, BECAUSE THE FRAME IS NOT FREE.** Measured on the real
        # window: his layout costs 61 px of the window's unshrinkable minimum
        # (the frame's title and margins, the list's new label, and the
        # "Already generated" line no longer sharing the type row), and this
        # window's minimum is measured against a laptop screen. 39 of the 61
        # are bought back here and in the two grids' spacings, which is the
        # difference between the run list opening at three rows and opening
        # compacted to two on a 1080 px display.
        box_v.setContentsMargins(12, 4, 12, 8)
        box_v.setSpacing(7)
        #: The three layouts `_compact_the_settings_frame` squeezes when the
        #: window's own minimum will not fit the screen. Kept here so the
        #: ladder in `showEvent` has one thing to call and no knowledge of how
        #: this block is built.
        self._roomy = (box_v, shown_grid)
        #: Four buttons and a help icon, under the frame, in his order.
        actions_row = QHBoxLayout()
        #: What rides to the RIGHT of "Report type" on his image: the type's own
        #: help button (prepended by the type block below) and the two report
        #: tick boxes with theirs.
        type_tail = QHBoxLayout()
        type_tail.setContentsMargins(0, 0, 0, 0)

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
               "instruments or a chart is missing cube corners.")
            + "\n\n" + _report_across_projects_help(),
            self, color=SPEC_GREEN))
        # **ON TWO LINES WHEN ONE CANNOT HOLD THEM (B8-927).** German asks
        # 759 px for the three buttons and the icon, and the frame has 694 at
        # the window's 760 px minimum: they were drawn over each other.
        self._add_reflow = _reflow_row(add_row, (1, 1, 2), self)
        box_v.addWidget(self._add_reflow)

        #: **THE LIST IS NAMED ON HIS MOCKUP AND WAS NOT NAMED HERE.** Every
        #: other control in the frame carries a label; the list of measurements
        #: carried only a tooltip, so a reader had to hover a box to learn what
        #: the box was.
        self._list_label = QLabel(tr("Included Measurements in report:"), self)
        box_v.addWidget(self._list_label)

        self._profile_list = QListWidget(self)
        # A fixed height cramped this into ~3 visible rows the moment a run
        # or two existed — nowhere near enough to see and untick a run
        # without scrolling first (Sebastian, 2026-08-10). Sized instead to
        # the CONTENT in _size_profile_list: small with few rows, capped
        # (never eats the report below it) once there are many, with an
        # internal scrollbar past the cap either way.
        #: The list's own sentence, kept so that the one-page summary can put
        #: its own in front of it and give this one back (B8-523).
        self._list_tooltip = tr(
            "The profiles whose measurements this report covers, with one row "
            "per dated run underneath. Untick a run to leave it out of the "
            "trend, the tables and the PDF. Nothing is changed on disk, and "
            "ticking it brings it straight back. Select a profile row and use "
            "“Remove Profile's Measurements…” to drop the whole profile.") \
            + " " + tr(
            "Every ticked measurement is judged against the report's one "
            "limit set, and the ticked measurements decide where Generate "
            "report saves the report, whichever profile run this window was "
            "opened from.") + "\n\n" + _report_across_projects_help()
        self._profile_list.setToolTip(self._list_tooltip)
        # **THE SELECTED ROW IS THE WINDOW'S OWN GREEN, NOT THE APP'S CYAN.**
        # Basti, 2026-09-18, on a photograph of this very list: *"when i click
        # the demo switching in the list it gets a cyan overlay. should be the
        # green accent color instead"*. The cyan comes from one app-wide rule
        # in `ui/styles.py` (`QListWidget::item:selected { background: ACCENT }`
        # with `ACCENT = SPEC_CYAN`), and every other accent in this window is
        # SPEC_GREEN already: the info icons, the tick boxes, the help buttons.
        # Overridden here rather than app-wide, because that one line repaints
        # every list in ChromIQ and that is his call, not this round's.
        #
        # Dark text on it, not white: SPEC_GREEN is a light colour and white on
        # it is the contrast fault this project has already fixed twice in
        # other places.
        self._profile_list.setStyleSheet(
            "QListWidget::item:selected {"
            f" background: {SPEC_GREEN}; color: #0a0a0a; }}"
            + self._list_tick_box_qss())
        self._profile_list.itemSelectionChanged.connect(self._update_source_buttons)
        #: run keys the user unticked — session-only, nothing on disk changes.
        self._hidden_runs: "set[str]" = set()
        self._list_rows: "list[tuple]" = []
        self._building_list = False
        self._profile_list.itemChanged.connect(self._on_run_row_toggled)

        #: **"SELECT ALL" AND "DESELECT ALL", BESIDE THE LIST (B8-590).**
        #: Knut, 2026-09-20, ruling "Show all measurement runs" out of the
        #: design and naming what replaces it: *"The feature that actually is
        #: desired here is a button 'Select All' that helps the user to tick
        #: all measurement dates in the 'included measurements in report'
        #: list, so the user does not need to manually click all of them, and
        #: a button 'Deselect All' that unticks all measurements … These
        #: should be placed to the right side of the 'included measurements in
        #: report' input selection box, since the … input box has too much
        #: available space compared to the width of its content. These two
        #: buttons then ONLY select or clear the selection of the listed
        #: measurements."*
        #:
        #: ONLY. They tick and untick; they change no other setting, they do
        #: not generate, and they are the only control besides a click in the
        #: list and a report selection that may move a tick.
        list_row = QHBoxLayout()
        list_row.setContentsMargins(0, 0, 0, 0)
        list_row.setSpacing(10)
        list_row.addWidget(self._profile_list, 1)
        tick_col = QVBoxLayout()
        tick_col.setContentsMargins(0, 0, 0, 0)
        tick_col.setSpacing(6)
        self._select_all_btn = QPushButton(tr("Select all"), self)
        self._select_all_btn.setStyleSheet(_compact_btn)
        self._select_all_btn.clicked.connect(self._on_select_all_measurements)
        self._select_all_btn.setToolTip(tr(
            "Tick every measurement in the list. It changes nothing else: the "
            "report covers exactly the measurements that are ticked when you "
            "click Generate report."))
        tick_col.addWidget(self._select_all_btn)
        self._deselect_all_btn = QPushButton(tr("Deselect all"), self)
        self._deselect_all_btn.setStyleSheet(_compact_btn)
        self._deselect_all_btn.clicked.connect(
            self._on_deselect_all_measurements)
        self._deselect_all_btn.setToolTip(tr(
            "Untick every measurement in the list. It changes nothing else: "
            "the report covers exactly the measurements that are ticked when "
            "you click Generate report."))
        tick_col.addWidget(self._deselect_all_btn)
        tick_col.addStretch(1)
        list_row.addLayout(tick_col)
        box_v.addLayout(list_row)

        out_row = type_tail
        # KNUT, 2026-09-11: *"A user should be allowed to print several report
        # types for a run, as the user may have several uses for different
        # reports … This also makes it logical that there is a Generate Report
        # button, so the user can choose to generate a report that is
        # selected."* The type is a VIEW of the same judged data, and this is
        # the button that keeps one.
        # **AND THE FOUR BUTTONS ARE ONE ROW UNDER THE FRAME (B8-460).** L.8
        # put Generate report and Delete Selected Report beside the "Report
        # shown" pulldown, and beta 25's mockup puts all four in a row of their
        # own under the "Report settings" frame, in this order: Generate
        # Report, Delete Selected Report, Save Report As PDF, Reveal Folder,
        # help icon. The widgets and their signals are unchanged.
        self._generate_btn = QPushButton(tr("Generate report"), self)
        self._generate_btn.setStyleSheet(_compact_btn)
        self._generate_btn.clicked.connect(self._on_generate_report)
        self._generate_btn.setEnabled(False)
        actions_row.addWidget(self._generate_btn)
        self._delete_report_btn = QPushButton(
            tr("Delete Selected Report"), self)
        self._delete_report_btn.setStyleSheet(_compact_btn)
        self._delete_report_btn.clicked.connect(self._on_delete_report)
        self._delete_report_btn.setEnabled(False)
        actions_row.addWidget(self._delete_report_btn)
        self._pdf_btn = QPushButton(tr("Save report as PDF…"), self)
        self._pdf_btn.setStyleSheet(_compact_btn)
        self._pdf_btn.clicked.connect(self._export_pdf)
        self._pdf_btn.setEnabled(False)
        actions_row.addWidget(self._pdf_btn)
        self._reveal_btn = QPushButton(tr("Reveal folder"), self)
        self._reveal_btn.setStyleSheet(_compact_btn)
        self._reveal_btn.clicked.connect(self._on_reveal)
        self._reveal_btn.setEnabled(False)
        actions_row.addWidget(self._reveal_btn)
        actions_row.addWidget(TooltipButton(
            tr("Saving and finding the report"),
            tr("Save report as PDF…: writes the whole report (this window's "
               "contents, laid out for print with the ChromIQ heading and page "
               "numbers) to a PDF and opens it. The trend graphs are included only "
               "when the report has two or more measurements.\n\n"
               "Where it is saved: in the reports folder of the place the "
               "report's ticked measurements cover, whichever profile run "
               "this window was opened from; the save dialog offers it, and "
               "you choose the exact place and name there. Nothing is "
               "written into any other measurement's folder.\n"
               "\u2022 One profile run's measurement: that run's own reports "
               "folder.\n"
               "\u2022 One dated verification: that date's own reports folder, "
               "verifications/<date>/reports.\n"
               "\u2022 Several dated verifications of one run: "
               "verifications/reports in that run.\n"
               "\u2022 A calibration (Run type Calibration): the project's "
               "cal/reports folder.\n"
               "\u2022 Several profile runs of one project: the reports folder "
               "of the whole project, next to its runs.\n"
               "\u2022 Several projects: the reports folder beside them when "
               "they are side by side in one folder, otherwise the reports "
               "folder of your ChromIQ folder.\n"
               "\u2022 A file outside any project: a reports folder beside "
               "it.\n\n"
               "Reveal folder: opens the folder of the first measurement in "
               "the list in your file manager (for a profile run's own "
               "measurement, its whole project folder), so you can browse to "
               "a reports folder and open any PDF you saved earlier."),
            self, color=SPEC_GREEN))
        #: Why Generate is greyed, when it is (C6): the button's own reason,
        #: on screen and whole, on its own row under the buttons.
        self._generate_why = QLabel(self)
        self._generate_why.setWordWrap(True)
        self._generate_why.setStyleSheet(_faint_label_css(
            resolve_mode(settings.get("appearance", "auto"))))
        self._generate_why.setVisible(False)
        self._generate_why_full = ""
        actions_row.addStretch(1)
        # **THE TWO TICK BOXES RIDE WITH "REPORT TYPE" NOW (B8-460).** Knut,
        # beta.5, put them to the right of the buttons *"to save a bit of
        # vertical space"*; his beta-25 mockup keeps them on one line and moves
        # that line to the right of the "Report type" pulldown, inside the
        # "Report settings" frame. The saving is the same and they now sit with
        # the setting they qualify.
        out_row.addSpacing(18)

        #: **"SHOW ALL MEASUREMENT RUNS" IS GONE, WITH THE FEATURE BEHIND IT
        #: (B8-590).** Knut, 2026-09-20, having watched it mean two different
        #: things in one window: *"Note that the 'Show all...' check mark does
        #: not mean show all measurements existing in the 'included
        #: measurements in report' list. No... It means show all measurement
        #: runs that was ticked (selected) … The help text for 'Show all
        #: measurement runs' describes that either ONE or ALL measurements are
        #: included depending on the state is OFF or ON. This description
        #: basically makes it impossible to show multiple measurement dates
        #: (neither one or all) and cannot be correct. I realise now this
        #: checkbox is not a reasonable feature to have (and has evolved to
        #: something that it was not originally used) and should be removed …
        #: Remove the feature 'Show all measurement runs' totally from the
        #: design, and any feature that belongs to that button."*
        #:
        #: So the box, its Preferences default, its tooltip, the rule that
        #: forced it off on a one-measurement list, and every conflict rule
        #: built around it are all gone. What replaces it is not another
        #: setting: **a report covers exactly the measurements that are ticked,
        #: always** (`_runs_for_report`), and the two buttons beside the list
        #: are the convenience that ticking eleven rows needed.
        # His mockup leaves clear air between the two tick boxes; without it
        # the first one's info icon reads as belonging to the second.
        out_row.addSpacing(14)
        self._detail_check = QCheckBox(tr("Show detailed data for each run"), self)
        self._detail_check.setChecked(
            bool(settings.get("report_default_show_details", True)))
        self._detail_check.toggled.connect(
            lambda on: (settings.set("report_show_details",
                                     "true" if on else "false"),
                        self._settings_touched()))
        out_row.addWidget(self._detail_check)
        out_row.addWidget(TooltipButton(
            tr("Show detailed data for each run"),
            tr("Adds the full breakdown for every run in the report, each on "
               "a page of its own: the colour-accuracy table, paper white and "
               "darkest black, the eight cube corners, and the worst patches "
               "with their expected and measured colours side by side. The "
               "table carries verdict words against the limit set named under "
               "“Judged against” wherever the report judges; a Printing "
               "record judges nothing, so its table has none.\n\n"
               "Handy when you want to see WHY a run passed or failed, not "
               "just that it did: for example which patches pushed the "
               "average over its limit.\n\n"
               # **A HELP TEXT IS A PROMISE, AND THIS ONE STOPPED BEING TRUE
               # (R27-F1).** It read *"which is why it starts unticked"*, and
               # it was right until P.3 of the design record made both boxes
               # default ON (`report_default_show_details` is True in
               # `core/settings.py`, and two lines above this the box is built
               # from it). Measured on a fresh settings file, which is every
               # new installation: the box opens TICKED under a sentence
               # saying it does not. The state is the user's to set, so the
               # sentence names the lever instead of claiming a value.
               # …AND IT STOPPED BEING TRUE A SECOND TIME (B8-490). The
               # sentence named Preferences as the one lever, and since Knut's
               # beta-25 ruling a report you select brings its own setting
               # with it: *"All settings that belong to a report shall be
               # loaded … 'Show all measurement runs' and 'Show detailed data
               # for each run'."* Preferences decides where a NEW report
               # starts; a saved one decides for itself.
               "It makes the report, and the saved PDF, considerably longer. "
               "Where a new report starts is yours to set, in Preferences ▸ "
               "Reports ▸ Measurement Report Defaults. A report you pick in "
               "“Report shown” brings its own setting with it."),
            self, min_width=440, color=SPEC_GREEN))
        out_row.addStretch(1)

        # ------------------------------------------------------------------
        # The list of generated reports (B8-380, §13 rules L.1, L.8, L.9)
        # ------------------------------------------------------------------
        # Knut, 2026-09-18: *"the area … is made into a selectable and
        # scrollable selection box … This selection box needs height to show at
        # least 3 to 4 rows of text, and only one named report can be selected
        # at a time, and if more reports than can be shown in the height of the
        # input box, then one may scroll down … Then it may need to be below the
        # Generate Report button, and above the Report type field."*
        #
        # It was a one-row pulldown, sitting BELOW "Judged against" — measured
        # on screen at y=388 with Generate report at y=250 and Report type at
        # y=292. The order is now his: the buttons stacked to the left of a
        # box that shows four rows and scrolls past them, the whole of it above
        # Report type.
        #
        # AND EVERY ENTRY IS A DOCUMENT, not a file. That is B8-383 and it is
        # why this could not be rearranged first: a control moved around the
        # wrong model is still the wrong model.
        from PyQt6.QtWidgets import QComboBox
        from ui.widgets import NoScrollComboBox
        # **THE TWO BUTTONS HAVE LEFT THIS ROW (B8-460).** L.8 kept Generate
        # report and Delete Selected Report beside the pulldown; his beta-25
        # mockup puts them in the action row under the frame, and this row is
        # the pulldown, its help button and its hint. Both buttons are built
        # above, with the other two they now stand beside.
        # **A PULLDOWN, ON HIS RULING.** His paragraph asked for "a selectable
        # and scrollable selection box … height to show at least 3 to 4 rows of
        # text"; asked about it, he answered *"It is ok that 'Current Report
        # Showing' is a pulldown list if that saves space in the window."* It
        # does: a three-row box beside two stacked buttons cost this window
        # 42 px of a minimum that already sits within about 30 px of an 800 px
        # screen, and the whole of it had to be traded back out of the report
        # view on a short display. What the pulldown keeps is the part of L.1
        # that matters with one row visible: a NAME that carries the settings
        # and the date and time, so one line can be told from another.
        self._saved_combo = NoScrollComboBox(self)
        self._saved_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._saved_combo.setMinimumWidth(320)
        self._saved_combo.currentIndexChanged.connect(self._on_saved_chosen)
        # **AND A CHOICE THAT DOES NOT MOVE THE INDEX IS STILL A CHOICE
        # (R24-F1).** `currentIndexChanged` cannot fire for the entry the list
        # is already on, so picking "New report…" while the pulldown read "New
        # report…" did nothing at all: the one control that loads the
        # Preferences defaults could not be used to load them. `activated`
        # fires whenever the USER picks a row, the same row included, and the
        # slot below acts only on that case so a real move is still handled
        # once by `currentIndexChanged`.
        self._saved_combo.activated.connect(self._on_saved_picked_again)
        # **THE NAME COMES BEFORE THE CONTROL IT NAMES.** The first cut put the
        # label in the column to the RIGHT of the pulldown, and the photograph
        # showed "Report shown (run2):" sitting past the far edge of the
        # box, reading as a caption for whatever came after it. The two rows
        # below this one have had their label on the left since the window was
        # built; this one now matches them.
        self._saved_label = QLabel(tr("Report shown:"), self)
        shown_grid.addWidget(self._saved_label, 0, 0)
        shown_grid.addWidget(self._saved_combo, 0, 1)
        # **ONE LINE, NOT THREE.** The name, the help button, the instruction
        # and the Delete refusal stacked three deep came to 46 px beside a box
        # that is 21 px tall when it is empty, and this window's minimum is
        # measured against an 800 px screen. Only one of the last two ever has
        # anything to say (`_set_saved_hint`), so the column is a row.
        side_col = QVBoxLayout()
        side_col.setSpacing(2)
        head = QHBoxLayout()
        self._saved_help = TooltipButton(
            tr("Report shown"),
            tr("Every report generated for the measurements in the list, "
               "newest first: this run's own, and reports that cover them "
               "together with measurements of other profile runs or other "
               "projects. With Run type Calibration only the calibrations' "
               "reports are listed. One entry "
               "is one document: a single press of “Generate report” makes "
               "one, however many measurements it covers.\n\n"
               "Click an entry to bring that report back into this window "
               "with the settings it was made with: its report type, the "
               "limit set it was judged against, both tick boxes and the "
               "measurements it covers. Nothing is rebuilt and nothing is "
               "written.\n\n"
               "Reports made by an earlier ChromIQ are listed one per file, "
               "exactly as they were saved, and open the same way.\n\n"
               "Delete Selected Report moves that report's files into an "
               "old/ folder. Nothing is destroyed, and the measurement "
               "itself is never touched.")
            # #182 K30 (Knut, 5798461562): a loaded report can always be
            # generated again, and where a report across projects lives.
            + "\n\n" + tr(
               "Every report shown can be generated again, whichever profile "
               "run this window was opened from. Change any of its settings, "
               "or none, and press “Generate report”: you are asked whether "
               "to update the report shown, create a new report, or cancel. "
               "Update rewrites the report where it lives, and its earlier "
               "version is kept in an old/ folder beside it. An update keeps "
               "the moment the report was created at the front of its name "
               "and adds when it was updated. The rest of the name follows "
               "the new settings, its report type, limit set and “Detailed”, "
               "and the scope in it (One date, Multiple runs, Cal and the "
               "like) follows the measurements it covers: a report of one "
               "date that you update to cover more dates becomes a report of "
               "those dates. A new report is saved where its ticked "
               "measurements decide.")
            + "\n\n" + tr(
               "An update never leaves a measurement out behind your back. "
               "When a project the report covers cannot be found, the update "
               "is refused and nothing is written. When a measurement it "
               "covers is gone from disk, you are asked first whether to "
               "update without it.")
            + "\n\n" + _report_across_projects_help(),
            self, min_width=460, color=SPEC_GREEN)
        head.addWidget(self._saved_help)
        #: L.9: what to do with the list. One line, elided, whole sentence as
        #: the tooltip, for the reason `_type_blurb` gives: a word-wrapped
        #: label of its own is what pushed this window's bottom off an 800 px
        #: screen, twice.
        self._saved_hint = QLabel(self)
        # Wrapped to TWO lines by `_wrap_beside_the_pulldown` (B8-524), never
        # to three: the cap is what keeps a word-wrapped label from asking for
        # a height the 800 px screen has not got.
        self._saved_hint.setWordWrap(True)
        self._saved_hint.setStyleSheet(_faint_label_css(
            resolve_mode(settings.get("appearance", "auto"))))
        self._saved_hint_full = ""
        head.addWidget(self._saved_hint, 1)
        #: Why Delete is refused, when it is. Same one-line treatment.
        self._saved_note = QLabel(self)
        self._saved_note.setWordWrap(True)
        self._saved_note.setStyleSheet(_faint_label_css(
            resolve_mode(settings.get("appearance", "auto"))))
        self._saved_note_full = ""
        head.addWidget(self._saved_note, 1)
        # **AND NO STRETCH AFTER THEM (B8-524).** A stretch of its own took a
        # third of the row while the sentence beside it was being shortened to
        # fit: measured at 1480 px, the label had 247 px of a row with about
        # 700 in it, so even an 80-character sentence had to lose its end.
        # Only one of the two labels is ever visible, it carries stretch 1, and
        # the grid column it sits in already takes the window's slack, so the
        # stretch bought nothing and cost the text.
        # **AND IT SITS WITH THE PULLDOWN, NOT ABOVE IT.** With a stretch only
        # BELOW it, this row was pinned to the top of its column while the
        # pulldown beside it is centred between the two stacked buttons, so the
        # help button floated visibly higher than the control it explains.
        # Basti saw it in a photograph: *"on the right the tooltip icon is up
        # high a bit"*. A stretch on each side centres it on the same line the
        # pulldown is on, and costs no height: the column's minimum is the
        # row's either way.
        side_col.addStretch(1)
        side_col.addLayout(head)
        side_col.addStretch(1)
        shown_grid.addLayout(side_col, 0, 2)
        # **AND THE "ALREADY GENERATED" LINE STARTS AT THE PULLDOWN'S LEFT
        # EDGE.** That is what his mockup shows, and a grid is the only way to
        # promise it: the line is row 1 of columns 1 and 2, so it begins
        # exactly under the box it is about however long the label gets in
        # another language. The widget itself (`_type_blurb`) is built with the
        # "Report type" row below, where it has always been built; only where
        # it is PLACED moved, because the line is about the run's reports and
        # not about the type.
        self._already_row = QHBoxLayout()
        self._already_row.setContentsMargins(0, 0, 0, 0)
        shown_grid.addLayout(self._already_row, 1, 1, 1, 2)
        shown_grid.setColumnStretch(1, 3)
        shown_grid.setColumnStretch(2, 2)
        self._saved_row = shown_grid
        top_v.addLayout(shown_grid)
        top_v.addWidget(self._settings_box)
        # **ON TWO LINES WHEN ONE CANNOT HOLD THEM (B8-927).** Measured at
        # the 760 px minimum: English asked 719 px of 716, German 857, and
        # "Ausgewählten Bericht…" sat under "Bericht als PDF speich…".
        self._actions_reflow = _reflow_row(actions_row, (1, 1, 1, 2), self)
        top_v.addWidget(self._actions_reflow)
        # **WHY GENERATE IS GREYED, ON A ROW OF ITS OWN (re-challenge R2 of
        # beta 39, #10).** Beside the four buttons it had what was left of the
        # row, which at the window's default width was room for four to six
        # words; the German remedy never appeared at all, only in the tooltip.
        # Under the buttons it has the window's whole width and wraps into as
        # many lines as the sentence needs. A hidden label claims no space, so
        # the row costs nothing while Generate is live.
        top_v.addWidget(self._generate_why)
        #: Says the document is older than the settings. **ON ITS OWN ROW,
        #: DIRECTLY UNDER THE BUTTON IT NAMES.** Put inside `out_row` with a
        #: stretch, as it was first built, it competed with four buttons and a
        #: photograph of the real window showed the result: "Generate report"
        #: read "erate rep", "Save report as PDF…" read "report as", "Reveal
        #: folder" read "veal fold", and the warning itself was cut off at "or
        #: put the s". A hidden widget claims no space in a Qt layout, so the
        #: row below costs nothing until the moment it has something to say.
        self._stale_label = QLabel(
            tr("⚠ Settings changed. Click “Generate report” to build the "
               "report with them, or put the setting back."), self)
        self._stale_label.setStyleSheet(
            f"color: {_C['fail']}; font-weight: bold")
        self._stale_label.setWordWrap(True)
        self._stale_label.setVisible(False)
        top_v.addWidget(self._stale_label)
        #: THE FOURTH DOOR ON THE COLOUR SCALE, and the loudest one, because
        #: this is the window that SAVES A DATED DOCUMENT from the numbers.
        #: Combined round 10 put one shared reading behind the Build ICC
        #: profile tab and both import doors; combined round 11 drove the same
        #: measurement in here, and a report whose `paper_white` reads
        #: `L* 8.89` was generated and filed with nothing said
        #: (`~/Desktop/ChromIQ-beta18-proof/round-11/D-result.json`). A `.ti3`
        #: is handed straight through by `_as_ti3` - no conversion, so
        #: `repair_converted_cie` never runs on it - and only a READING can
        #: catch it. Same words, same hidden-row pattern as the notice above:
        #: nothing is refused and nothing is rewritten, the window simply
        #: stops being silent. See `measurement_filing.the_colour_scale_note`.
        self._scale_label = QLabel("", self)
        self._scale_label.setStyleSheet(
            f"color: {_C['fail']}; font-weight: bold")
        self._scale_label.setWordWrap(True)
        self._scale_label.setVisible(False)
        top_v.addWidget(self._scale_label)

        # #182 (Knut D8, D20): the two Pass-threshold spin boxes are gone. A
        # report is judged against its own LIMIT SET (K31: the set belongs to
        # the report, not to a run); the row below names it and opens the
        # limits table. Every connection is a bound method: a lambda
        # capturing `self` on a child widget's signal is the shape that
        # segfaulted the app (CLAUDE.md).
        from ui.widgets import NoScrollComboBox
        self._run_ctx = None          # workflow.run_compliance.RunContext | None
        self._limits = None           # the starting choice (RunLimits)
        #: A type chosen in this window (K31: the REPORT's, kept for the
        #: session and written only by Generate report), exactly as the
        #: limit set is.
        self._session_type = ""
        #: B8-250. `_run_key` → the `report_*.json` name the user picked in
        #: "Saved reports". Session-only and written nowhere: it chooses which
        #: of a measurement's saved reports the window shows, and a run that
        #: holds one report never has an entry here.
        self._chosen_reports: "dict[str, str]" = {}
        #: B8-383. Which DOCUMENT the window is showing, and the settings that
        #: document was made with.
        #:
        #: `_loaded_doc_id` is the entry in the list (see `document_key`): it
        #: decides which entry is highlighted and, through `_chosen_reports`,
        #: which file of each measurement is drawn. It survives a settings
        #: change, because the document on screen does.
        #:
        #: `_loaded_doc` is that document's own recorded settings, and it is
        #: DROPPED the moment the user moves a control (`_settings_touched`).
        #: Restoring a report's settings and then going on to claim them after
        #: the user has changed one is the shape of Knut's fifth defect: an
        #: entry that disagrees with the document it names.
        self._loaded_doc_id = ""
        self._loaded_doc: "dict | None" = None
        #: **WHEN THE DOCUMENT ON SCREEN WAS CREATED (B8-461).** Knut, beta 25:
        #: *"The report text updates, but the first line says 'Created:
        #: 2026-09-19 17:57:22', which is not the same creation time as the
        #: report name is giving. They should be the same."* The body was
        #: stamped with `self._created`, which is the moment this WINDOW was
        #: opened, so every saved report ever loaded claimed to have been made
        #: seconds ago. Filled from the same two places the entry's own name is
        #: built from, so the line and the name cannot disagree: the document
        #: block's `created` when there is one, and the report file's own saved
        #: stamp when the document is a single pre-#182 file.
        #:
        #: Empty means "no document is loaded" — the "New report…" state and a
        #: measurement with nothing saved — and then the line is this window's
        #: own clock again, which is what it is for.
        self._doc_created = ""
        #: **WHAT THE TWO PULLDOWNS WERE SHOWING WHEN THE USER MOVED A CONTROL
        #: (B8-462).** Knut, beta 25: *"If I change Judged against from
        #: 'ChromIQ default' to 'ChromIQ tight', then suddenly report type also
        #: changes to 'Grey and tone check'. Changing judged against parameter
        #: shall not ever alter report type."*
        #:
        #: The mechanism is `_settings_touched` dropping the loaded document's
        #: claim on ALL the controls the moment ONE of them is moved: the type
        #: pulldown then fell back to the RUN, which may carry a different type
        #: from the report on screen, and jumped to it. The document's claim
        #: still has to go, because it no longer describes the screen; what
        #: replaces it is the value that WAS on screen, taken from the widgets
        #: themselves, so the control the user did not touch does not move.
        #:
        #: Session-only, written nowhere, and dropped the moment another
        #: document is loaded (`_forget_sticky_settings`).
        self._sticky_type = ""
        self._sticky_set = ""
        self._report_own_limits = None
        #: Whether the user has moved a setting since the document was loaded.
        #: While it is True the document's own settings are not consulted: they
        #: are no longer what is on screen. The document itself stays selected
        #: and stays on the page, which is what the red line is about.
        self._doc_settings_moved = False
        #: Whether this window has already opened on the latest report created
        #: (B8-388). Once per window: after that, what is loaded is whatever
        #: the user last clicked, and re-deciding it on every rebuild would
        #: take the page back off them.
        self._opened_on_a_report = False
        self._syncing_limits = False
        # #182 (D28, question 19): the KIND of document, chosen before the
        # numbers it is judged with. Since K31 both belong to the REPORT.
        # **ROW 0 OF THE FRAME'S GRID (B8-460).** His mockup aligns the
        # "Report type" and "Judged against" pulldowns on one left edge, which
        # two independent QHBoxLayouts cannot promise: the labels are different
        # lengths, so the boxes started 32 px apart on screen. A grid with the
        # label in column 0 and the box in column 1 is the promise.
        settings_grid = QGridLayout()
        settings_grid.setHorizontalSpacing(8)
        settings_grid.setVerticalSpacing(6)
        settings_grid.setContentsMargins(0, 0, 0, 0)
        self._settings_grid = settings_grid
        self._type_label = QLabel(tr("Report type:"), self)
        settings_grid.addWidget(self._type_label, 0, 0)
        self._type_combo = NoScrollComboBox(self)
        from PyQt6.QtWidgets import QComboBox
        self._type_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._type_combo.setMinimumWidth(260)
        self._type_combo.currentIndexChanged.connect(self._on_type_chosen)
        settings_grid.addWidget(self._type_combo, 0, 1)
        type_tail.insertWidget(0, TooltipButton(
            tr("Report type"),
            # K13 (round 2B, #2): these three sentences predated the rule
            # that a profiling measurement's only report is the Printing
            # record, and contradicted the paragraph appended below.
            tr("Which kind of document a measurement is made into. The "
               "measurement is the same either way; the type decides what is "
               "put in front of a reader, and how much of it.\n\n"
               "The type belongs to the report, like the limit set. A new "
               "report starts on the type chosen in Preferences, Reports; "
               "choosing another here changes only the report shown, and "
               "nothing is written until you press Generate report.\n\n"
               "A type shown greyed cannot be chosen here: either ChromIQ "
               "cannot produce it yet, or the kind of measurement does not "
               "allow it. Pointing at the greyed entry says which.")
            + _types_and_pairing_help(),
            # as wide as the "Judged against" help beside it (K33, B8-992):
            # it was the same 616 x 971 px tower
            self, min_width=JUDGED_AGAINST_HELP_WIDTH, color=SPEC_GREEN))
        #: What the chosen type is for, or, on a type that cannot be produced,
        #: what is missing. It rides on the SAME row, elided, with the whole
        #: sentence as its tooltip: a word-wrapped label of its own is what
        #: pushed this window's bottom off an 800 px screen, twice, because a
        #: wrapped label's minimum height is computed before the window has
        #: been given its width.
        self._type_blurb = QLabel(self)
        self._type_blurb.setWordWrap(False)
        self._type_blurb.setStyleSheet(_faint_label_css(
            resolve_mode(settings.get("appearance", "auto"))))
        # …AND WHEN IT DOES NOT FIT, A WAY TO READ IT. Knut, 2026-09-13: *"the
        # end of the text is cut off with a '...' at the end. All generated
        # reports should be listed clearly and visible, even if it is a list of
        # 6 report types. This might require a taller text area. If limited
        # space, this could be handled with one-line text that opens for more
        # detailed information."* The taller area is the thing the comment
        # above rules out, so it is his second option: the line stays one line
        # and grows a link that opens the whole list.
        self._type_blurb.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        self._type_blurb.linkActivated.connect(self._show_generated_reports)
        self._type_blurb_full = ""
        self._generated_full = ""
        # **IT SITS UNDER "REPORT SHOWN", NOT BESIDE "REPORT TYPE" (B8-460).**
        # His mockup puts "Already generated for this run: …" on its own line
        # directly under the pulldown, and the tick boxes take the room it used
        # to have. The widget, its eliding, its "show all" link and its tooltip
        # are unchanged; `_already_row` was reserved above, in the grid that
        # aligns it with the box.
        self._already_row.addWidget(self._type_blurb, 1)
        # **THE DETAIL BOX GOES UNDER THE TYPE'S ICON WHEN THE ROW IS SHORT
        # (B8-927).** At the 760 px minimum it had 205 of the 220 px its
        # English name asks (216 of 243 in German) and was cut.
        self._type_tail_reflow = _reflow_row(type_tail, (1, 2), self,
                                             gap=32)
        settings_grid.addWidget(self._type_tail_reflow, 0, 2,
                                Qt.AlignmentFlag.AlignVCenter)

        self._judged_label = QLabel(tr("Judged against:"), self)
        settings_grid.addWidget(self._judged_label, 1, 0)
        judged_row = QHBoxLayout()
        judged_row.setContentsMargins(0, 0, 0, 0)
        self._set_combo = NoScrollComboBox(self)
        from PyQt6.QtWidgets import QComboBox
        self._set_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._set_combo.setMinimumWidth(220)
        self._set_combo.currentIndexChanged.connect(self._on_set_chosen)
        settings_grid.addWidget(self._set_combo, 1, 1)
        self._limits_btn = QPushButton(tr("Edit limits…"), self)
        self._limits_btn.setStyleSheet(_compact_btn)
        self._limits_btn.clicked.connect(self._on_open_limits)
        judged_row.addWidget(self._limits_btn)
        judged_row.addSpacing(10)
        # **"UNLOCK THIS RUN'S LIMITS" IS GONE, WITH THE RUN LOCK (K31).**
        # Knut, 5801677743: *"I am beginning to think this 'Unlock this run's
        # limits' feature just creates a mess and confusion. Maybe it is better
        # to remove it and make the report have full mastery over its own
        # settings"*, and after our analysis, *"I agree that the 'Unlock this
        # run's limits' is no longer needed"*. §25 of
        # `docs/design/measurement_report_limits.md` records the analysis.
        judged_row.addWidget(TooltipButton(
            tr("Judged against"),
            tr("Every row of the results is compared with one limit set: one "
               "column of the limits table. The limit set belongs to the "
               "report: every measurement ticked in the list is judged "
               "against it, whichever profile run or project it comes from, "
               "so the dates in one report are always compared on the same "
               "numbers.\n\n"
               "Changing it, or a number in Edit limits…, changes only the "
               "settings of the report shown. Nothing is judged again and "
               "nothing is written until you press Generate report, and every "
               "report already saved keeps the limit set and the verdicts it "
               "was made with. To judge earlier measurements against another "
               "set, tick them in a report and generate it.\n\n"
               "Edit limits… opens the whole table: this report's own limits "
               "in its first column, “This report”, beside every set. When "
               "every measurement ticked is of one profile run, it also sets "
               "which limit set new reports of that run start on.\n\n"
               "A new report starts on the limit set chosen in Preferences, "
               "Reports, unless its profile run has a default of its own, "
               "chosen in Edit limits…, which then wins.\n\n"
               "A measurement that is not in a ChromIQ project (an imported "
               "file) is judged against the set chosen here for this session "
               "only; nothing is stored for it.")
            + _sets_help()
            + "\n\n" + tr(_ISO_USE_HELP)
            + "\n\n" + tr(_PAIRING_HELP) + "\n\n" + tr(_CHART_HELP),
            # **WIDER, SO IT IS NOT A TOWER** (K33, B8-992). Knut, #182
            # 5816565326: *"The help text window for Judged against is very
            # tall, so the window should be made wider."* 460 px opened it
            # 616 x 971 on a 1079 px screen, scrolling; see
            # `JUDGED_AGAINST_HELP_WIDTH`.
            self, min_width=JUDGED_AGAINST_HELP_WIDTH, color=SPEC_GREEN))
        judged_row.addStretch(1)
        settings_grid.addLayout(judged_row, 1, 2)
        # The tail column takes the slack, so the two pulldowns keep the width
        # their contents ask for and everything beside them stays put.
        settings_grid.setColumnStretch(2, 1)
        box_v.addLayout(settings_grid)

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
        # K32 (Knut, #182 5814390886): with more graph tabs than fit, a part
        # of the next hidden tab shows at each edge and an arrow with nothing
        # to scroll to is greyed out (`ui/peek_tab_bar.py`). Set before the
        # first tab is added, as QTabWidget requires.
        from ui.peek_tab_bar import PeekTabBar
        self._trend_tabs.setTabBar(PeekTabBar(self._trend_tabs))
        # The "Trend over time" heading rides in the tab row's free corner
        # instead of a row of its own — that row's height is exactly what the
        # charts were missing on screens where every pixel counts.
        self._trend_label = QLabel(tr("Trend over time"), self)
        self._trend_label.setStyleSheet(
            "font-weight:bold;padding:0 6px 2px 0")
        self._trend_label.setVisible(False)
        self._trend_tabs.setCornerWidget(self._trend_label,
                                         Qt.Corner.TopRightCorner)
        self._trend_de = _TrendChart(self)
        self._trend_white = _TrendChart(self)
        self._trend_black = _TrendChart(self)
        self._trend_corners = _TrendChart(self)
        # #182 K20/K21: one tab per judged-metric group, hidden until one of
        # its rows is judged (`_trend_plan`). "Paper white, diff" sits beside
        # the L* graph it complements (Knut, 5787380408).
        self._trend_groups = {key: _TrendChart(self)
                              for key, _t, _m in _TREND_GROUPS}
        self._trend_tabs.addTab(self._trend_de, tr("Colour accuracy (ΔE00)"))
        self._trend_tabs.addTab(self._trend_white, tr("Paper white (L*)"))
        for key, title, _m in _TREND_GROUPS[:1]:
            self._trend_tabs.addTab(self._trend_groups[key], title())
        self._trend_tabs.addTab(self._trend_black, tr("Darkest black (L*)"))
        self._trend_tabs.addTab(self._trend_corners, tr("Cube corners (ΔE00)"))
        for key, title, _m in _TREND_GROUPS[1:]:
            self._trend_tabs.addTab(self._trend_groups[key], title())
        for chart in self._trend_groups.values():
            self._trend_tabs.setTabVisible(
                self._trend_tabs.indexOf(chart), False)
        self._trend_tabs.setVisible(False)
        v.addWidget(self._trend_tabs)
        # UNDER THE GRAPH, WHAT EACH LIMIT LINE IS (K45-2, Knut #182
        # 5834422633: the descriptions "should always be showing below each
        # chart, if they have a threshold associated with that graph"). The
        # PDF prints them under every graph; on screen they were only a
        # tooltip on each word, and a line out of view had no word to point
        # at. One label for the tab in front, refilled when the tab or the
        # data changes.
        self._trend_key = _TrendKey(self)
        self._trend_key.setWordWrap(True)
        self._trend_key.setTextFormat(Qt.TextFormat.RichText)
        self._trend_key.setStyleSheet("font-size:11px;padding:2px 6px 0 6px")
        self._trend_key.setVisible(False)
        v.addWidget(self._trend_key)
        self._trend_key_box = v
        self._trend_tabs.currentChanged.connect(self._refresh_trend_key)

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

        # **RUN TYPE CALIBRATION MAKES REPORTS AFTER ALL (#182 beta 39).**
        # Knut, 5794078008: *"The run type set to calibration should be able
        # to make a report after all. I retract my statement that the
        # measurement report window should not allow making reports in this
        # run type."* Beta 38's empty, locked window (K26, §18.1) is gone: the
        # measurement a door hands in is loaded under every Run type, and
        # what a Calibration window lists, counts and writes is decided by its
        # kind (`_window_kind`, KIND_CALIBRATION).
        #: Whether the window was opened with nothing to show (K32): the
        #: empty page then says why, in the words of the bar's run type.
        self._opened_empty = True
        if initial_ti3 is not None and (
                Path(initial_ti3).exists()
                or _a_calibration_with_saved_reports(Path(initial_ti3))):
            self._opened_empty = False
            self._load(Path(initial_ti3))
        else:
            self._view.setHtml(self._empty_html())

    # ---- Run type Calibration (#182 beta 39) ------------------------------
    def _is_calibration_window(self) -> bool:
        """Whether this window is a Calibration window: the profile bar says
        Run type = Calibration, or, with no bar behind it, the measurement it
        is about is a project's calibration (`_window_kind`)."""
        from workflow.measurement_report import KIND_CALIBRATION
        return self._window_kind() == KIND_CALIBRATION

    def _own_cal_dir(self) -> "Path | None":
        """The calibration folder of the measurement this window is ON (its
        first source), or None when that is not a project's calibration.

        A calibration has no run, so this is what "the window's own run" is
        for a Calibration window: the folder Generate report writes into and
        the place "Report shown" puts first."""
        from workflow.measurement_report import is_calibration_dir
        if not self._sources:
            return None
        d = Path(str(self._sources[0]["origin"])).parent
        return d if is_calibration_dir(d) else None

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # C9: Return opens no chooser (`no_default_button`).
        from ui.dialogs.no_default_button import no_default_button
        no_default_button(self)
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
            # What the layout needs at its narrowest width, wrapped labels
            # counted: see `_layout_need` (B8-921).
            _need = self._layout_need

            def _over() -> int:
                return _need() - cap

            charts = (self._trend_de, self._trend_white,
                      self._trend_black, self._trend_corners,
                      *self._trend_groups.values())
            # **THE FRAME'S OWN AIR GOES BEFORE THE DOCUMENT DOES (B8-460).**
            # The ladder used to put Generate report and Delete Selected Report
            # side by side here; Knut's beta-25 mockup has all four buttons on
            # one row already, so that step is gone, and what took its place is
            # the padding his "Report settings" frame costs. Measured on the
            # two-date fixture: 781 px against a 760 px cap with the frame at
            # its roomy spacings, 751 with them squeezed, so this is the whole
            # of what the frame cost an 800 px screen and the report view keeps
            # every pixel it had. On a screen with room, nothing is squeezed.
            if _over() > 0:
                self._compact_the_settings_frame()
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
            if _over() > 0:
                # **THE VIEW'S LAST RUNG, SO THE LIST AND ITS BUTTONS DO NOT
                # PAY (B8-956).** The list never goes below the natural height
                # of Select all / Deselect all beside it now, which costs
                # about 30 px on an 800 px screen (offscreen, measured: 752 px
                # of 760 before, 780 after, and 17 px short once a report
                # with wrapped notes is picked). The report view scrolls, so
                # it gives them up, down to 60 px (three lines of text).
                self._view.setMinimumHeight(
                    max(60, self._view.minimumHeight() - _over()))
            if _over() > 0:
                # the last thing left: the list at two rows, as when even the
                # plain minimum did not fit
                self._size_profile_list(compact=True)
            need = min(_need(), cap)
            h = max(h, need)
            # and the user cannot drag the window below it either, which is
            # the other way the frame was squeezed
            self.setMinimumHeight(need)
        # **AND IT MAY NOT GROW PAST THE SCREEN AFTERWARDS.** `resize` was the
        # whole of this, and a resize is a one-off request: the window's own
        # PREFERRED height is the sum of what its widgets would like, which is
        # larger, and a platform that does not honour `resize` hands that back
        # instead. Measured under the offscreen plugin, which is exactly such a
        # platform: the ladder brought the layout's minimum to 729 px against a
        # 760 px cap, `resize` asked for 729, and the window reported 819,
        # because 819 is what its widgets would like. A maximum says the thing
        # the resize was trying to say, and says it for every later relayout
        # too. It is a ceiling and not a pin: the window can still be made
        # smaller, and `showEvent` runs once per window, so a screen change
        # does not leave an old screen's ceiling behind.
        self.setMaximumHeight(cap)
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
        # READ FIRST, THEN JUDGE. `_measurement_for` has to know whether the
        # folder a report came from has ever held more than ONE measurement
        # under that name, and one of the two places that is written down is
        # the set of dates the folder's own reports carry. So every file is
        # read once into a list and the dates are counted before anything is
        # rebuilt, rather than each report being judged in ignorance of its
        # neighbours.
        saved: "list[tuple]" = []
        dates_by_origin: "dict[str, set]" = {}
        for p in list_project_reports(ti3.parent):
            try:
                rep = json.loads(read_text(p))
            except Exception:  # noqa: BLE001
                continue
            # **AND A FILE THAT PARSES IS NOT NECESSARILY A REPORT (R25-F1).**
            # `json.loads` is happy with `[]`, `null`, `"x"` and `5`, and the
            # `.get` two lines down then raises OUTSIDE the `except` above. One
            # such file anywhere under `runs/*/reports/` took the whole window
            # down for EVERY measurement of EVERY run of the project: the list
            # empty, all three pulldowns blank, Generate, PDF, Reveal and
            # Delete all dead, and a message naming no file. Driven in a real
            # window in all four shapes (round 25), with the no-file control
            # rendering a full report.
            #
            # ChromIQ writes no such file; the doors are a shared project, a
            # hand edit, and the declutter migration. A file we cannot read is
            # skipped exactly as an unparseable one is, which is the behaviour
            # this loop already had for the case it thought of.
            if not isinstance(rep, dict):
                log.warning("ignoring %s: a report must be a JSON object, "
                            "this one is %s", p, type(rep).__name__)
                continue
            saved.append((p, rep))
            dates_by_origin.setdefault(str(p.parent.parent), set()).add(
                str(rep.get("created") or ""))
        for p, rep in saved:
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
                # ...FROM ITS OWN MEASUREMENT, AND THIS USED TO BE
                # `p.parent.parent / ti3.name`, WHICH IS WHATEVER IS IN THE RUN
                # FOLDER TODAY. Every measurement of one run carries the same
                # file name, so a run that has been measured again does not
                # hold this report's measurement any more: it was copied into
                # `old/<stamp>/` and a different sheet took its place under
                # that name. The rebuild then recomputed the row from a
                # DIFFERENT measurement, kept the old date and the old verdict,
                # and printed today's numbers under a date five weeks old.
                #
                # Measured on one real disk: of 54 saved reports, FOUR describe
                # the measurement still live in their run folder. On
                # CR30-Test/runs/run1 the window drew seventeen dated rows and
                # every one of them read 8 patches, ΔE00 avg 11.948, paper
                # white L* 66.97 — the sheet measured on 8 September — while
                # the row dated 29 August had been saved with 20 patches, ΔE00
                # 15.907 and white L* 92.39. The over-time trend (#40) drew
                # seventeen points in five flat lines across five weeks.
                # Photographed in `~/Desktop/ChromIQ-beta18-proof/
                # combined-round-3/B1-seventeen-dates-one-sheet.png`.
                #
                # `_measurement_for` answers with the run's measurement only
                # while it still IS this report's measurement, by the stamp
                # `build_report` wrote into the report, and with None
                # otherwise. A row that keeps the numbers it was saved with is
                # honest; a row filled in from another sheet is not.
                run_ti3 = self._measurement_for(
                    rep, p.parent.parent, ti3,
                    dates_here=dates_by_origin.get(str(p.parent.parent)))
                if run_ti3 is not None:
                    try:
                        created = rep.get("created")
                        # The verdict this report was SAVED with is a RECORD,
                        # not a derived figure — a rebuild recomputes today's
                        # statistics from the same measurement, and must carry
                        # the old judgement across untouched or the rebuild
                        # becomes the very re-grading #182 is about.
                        # …AND WHAT THE FILE SAYS IT IS (round 2A, R2A-1): its
                        # recorded type and its document block. They were
                        # dropped here, so an older Colour summary was shown,
                        # counted and then UPDATED as whatever the run's type
                        # happened to be, and its own creation stamp went too.
                        kept = {k: rep[k] for k in
                                ("pass_thresholds", "verdict", "compliance",
                                 "report_type", "document")
                                if k in rep}
                        saved_rep = rep
                        rep = build_report(run_ti3, argyll_bin=self._argyll_bin())
                        if created:
                            rep["created"] = created
                        # …AND THE RECORD ITSELF, FOR WHEREVER ITS KEPT
                        # VERDICT IS SHOWN (challenge 5 of beta 42, M1,
                        # B8-1091). `rep` is this version's working of the
                        # measurement, what a NEW report is judged from; the
                        # saved report's own page is drawn from what it
                        # recorded, so its notes and its "How the colours
                        # were judged" line cannot contradict its words.
                        record = _the_saved_record(saved_rep, dict(rep))
                        rep.update(kept)
                        if record is not None:
                            rep[RECORD_KEY] = record
                    except Exception:  # noqa: BLE001
                        pass
            # Session-only: where this run lives on disk. Saved reports carry
            # only the measurement's NAME, so the four-tier PDF location
            # (Knut's "Where are my files?" card) needs the origin recorded
            # here — reports/report_*.json sits one level under it.
            rep["_origin_dir"] = str(p.parent.parent)
            # Session-only, and the tie-break below. `save_report` names a
            # second report of the same second `report_<stamp>_2.json`, so the
            # file name sorts in the order the files were written.
            rep["_report_file"] = p.name
            runs.append(rep)
        # ONE ROW PER MEASUREMENT, NOT ONE PER REPORT FILE OF IT.
        runs = self._one_row_per_measurement(runs)
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
                # `reports` is where a document of several dates lives (K23),
                # never a date.
                if d.name in covered or d.name in ("old", "reports"):
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
        if runs and not ti3.exists() and _a_calibration_with_saved_reports(ti3):
            # **A CALIBRATION MEASURED BEFORE ITS CHART WAS MADE AGAIN (#182
            # K30, challenge A F5).** `Calibration.reset` moves the
            # measurement into `cal/old/` and leaves `cal/reports/`, whose
            # reports keep the numbers they were saved with (spec 18.12).
            # They are listed and opened; nothing is built from a file that
            # is not there, and Generate says why it is greyed.
            pass
        elif not any(self._is_this_measurement(r, ti3, dates_by_origin)
                     for r in runs):
            # THE MEASUREMENT THE WINDOW WAS OPENED ON IS ALWAYS IN ITS OWN
            # HISTORY. This said `if not runs:`, so the measurement in hand was
            # used only when the project had NO saved report anywhere — and
            # `list_project_reports` above deliberately gathers EVERY run of the
            # project. In a project with more than one profile run, the first
            # report anybody generated therefore became the answer for every
            # other run: opened on run 2, the window showed run 1's measurement,
            # `_origin_dir` pointed at run 1's folder, and Generate filed run 1's
            # numbers into run 1's reports/ while run 2 went on saying "No report
            # has been generated for this run yet" for ever. No error, no log
            # line; the tester who met it reported a button that does nothing.
            # Photographed on screen, 2026-09-15, in a two-run project.
            #
            # The gathering itself is right and stays: the trend across a
            # printer's builds is the feature (#40, Knut). What was wrong is that
            # the history was also being read as the subject. So the subject is
            # added to the history explicitly, exactly as the dated fall-back
            # above adds a date measured with the report switched off.
            #
            # A MEASUREMENT THAT CANNOT BE READ NOW SAYS SO, where a project
            # with another run's report used to answer with that other run's
            # numbers. The build below raises, `_add_source` turns it into the
            # error page naming the file, and that is the same thing a one-run
            # project has always done. Silently right-looking and wrong is the
            # failure this whole change is about. (The window cannot be opened
            # on a file that is simply MISSING: `__init__` checks `exists()`.)
            #
            # THE SAME MARKER THAT FALL-BACK SETS, AND FOR THE SAME
            # REASON. This report is being built right now, from a measurement
            # that never had one saved beside it — the run's own profiling
            # chart is the everyday case, because ChromIQ saves a report under
            # a dated verification and not under the sheet a profile was built
            # from. Without the marker `_recorded` returns None and `_fresh` is
            # absent, which is the one combination the window reads as "an
            # older ChromIQ saved this and lost the verdict": it then told the
            # reader the verdict had been thrown away, when nothing had ever
            # been saved to throw away. Knut, 2026-09-13, reading exactly this
            # column: *"The statemend 'It was saved by a version of ChromIQ
            # that did not yet keep the verdict together with the
            # measurements' seems wrong."* It was.
            fresh = build_report(ti3, argyll_bin=self._argyll_bin())
            fresh["_origin_dir"] = str(ti3.parent)
            fresh["_fresh"] = True
            runs.append(fresh)
        runs.sort(key=lambda r: str(r.get("created") or ""))
        from workflow.measurement_report import annotate_raw_drift
        annotate_raw_drift(runs)
        name = runs[-1].get("chart") or ti3.stem
        return name, runs

    def _source_key(self, ti3: Path, by_identity: bool = True) -> tuple:
        """Dedup identity for a measurement. A ChromIQ project (saved reports
        across its runs/) is ONE source per FOLDER — all its runs. A standalone or
        imported measurement is ONE source per FILE, so several loose measurements
        in the same folder each add instead of collapsing to one (Knut).

        With *by_identity* the second half of the key is the disk's own device
        and inode, which every SPELLING of one file agrees on; without it, the
        resolved path, which survives the file being REWRITTEN. `_source_keys`
        asks for both, because each one misses what the other catches.
        """
        from core.file_manager import VERIFICATIONS_DIRNAME
        from workflow.measurement_report import list_project_reports
        # ONE FILE IS ONE SOURCE, BY THE DISK'S OWN IDENTITY. `resolve()`
        # alone was not enough and the comment that claimed it was is the one
        # this replaces: it collapses `/private/tmp` and a symlink and it does
        # NOT collapse a firmlink or a different capitalisation on a
        # case-insensitive volume, both of which added the same measurement a
        # second time. Measured: symlink +0 rows, capitalisation +1, firmlink
        # +1, and the sentence went from "covers 1 of the 3" to "covers 2 of
        # the 3" with one sheet printed twice (R18-F2). A file's device and
        # inode are the same under every one of those spellings.
        _ident = None
        if by_identity:
            try:
                _st = ti3.stat()
                _ident = f"{_st.st_dev}:{_st.st_ino}"
            except OSError:
                pass
        try:
            ti3 = ti3.resolve()
        except OSError:
            pass
        # CASE-FOLDED, BECAUSE THE SPELLING DECIDES WHICH BRANCH RUNS. On a
        # case-insensitive volume the same folder can be reached as
        # `verifications` or `VERIFICATIONS`, and comparing the name exactly
        # sent the second spelling down the "loose file" branch: one key came
        # back as a `dir` and the other as a `file`, so the identity below
        # never got the chance to match them (R18-F2).
        if ti3.parent.parent.name.casefold() == VERIFICATIONS_DIRNAME.casefold():
            return ("dir", _dir_ident(ti3.parent.parent) if by_identity
                    else str(ti3.parent.parent))
        if list_project_reports(ti3.parent):
            return ("dir", _dir_ident(ti3.parent) if by_identity
                    else str(ti3.parent))
        return ("file", _ident or str(ti3))

    def _source_keys(self, ti3: Path,
                     origin: "Path | None" = None) -> tuple:
        """Every identity this measurement answers to: where it is, what it is,
        and where the USER got it. Two sources are the same when they share any
        of them.

        A path alone cannot see that two spellings name one file; an inode
        alone cannot see that one path has been written again. See
        `_append_source`, where both halves were learned the hard way one round
        apart.

        **AND THE FILE THE USER PICKED IS THE THIRD.** An `.mxf` or `.cxf`
        import is converted into a FRESH temporary folder every time, so its
        path and its inode are both new on every press and neither can see that
        it is the same measurement: importing one `.mxf` three times gave three
        sources, "3 runs" in the Report Scope and a flat trend through three
        points all carrying one date (R20-F2). That route had no duplicate
        guard of any kind. `origin` is the one thing about it that does not
        move.
        """
        keys = [self._source_key(ti3)]
        by_path = self._source_key(ti3, by_identity=False)
        if by_path not in keys:
            keys.append(by_path)
        if origin is not None and Path(origin) != Path(ti3):
            try:
                keys.append(("origin", str(Path(origin).resolve())))
            except OSError:
                keys.append(("origin", str(origin)))
        return tuple(keys)

    @staticmethod
    def _disk_stamp(ti3: Path) -> tuple:
        """What this file looked like on disk when it was last read.

        Deliberately (mtime, size) and not a hash: chartread rewrites a `.ti3`
        in place, every write moves both, and a hash of a measurement file is
        a read of the whole thing on a path a user can trigger in a loop. A
        file that cannot be stat'ed answers `()`, which never equals a real
        stamp, so an unreadable file is always treated as moved on.
        """
        try:
            st = Path(ti3).stat()
        except OSError:
            return ()
        return (st.st_mtime_ns, st.st_size)

    def _source_has_moved_on(self, src: dict) -> bool:
        """Has the measurement behind *src* changed since it was read?"""
        was = src.get("stamp")
        if not was:
            # Added before this window started stamping, or unreadable then:
            # the honest answer is "cannot tell", and re-reading is the safe
            # side of that.
            return True
        return tuple(was) != self._disk_stamp(src.get("ti3"))

    def _reread_one_source(self, src: dict) -> None:
        """Read ONE loaded measurement off disk again, and nothing else.

        `_reload_sources` re-reads everything, which is right when the disk has
        changed under the whole window (a delete) and ruinous when one file was
        picked again in a loop (R22-F2).
        """
        try:
            name, runs = self._gather_runs(Path(src["ti3"]))
        except Exception as exc:  # noqa: BLE001
            log.warning("could not re-read %s: %s", src.get("ti3"), exc)
            return
        src["name"], src["runs"] = name, runs
        src["stamp"] = self._disk_stamp(src.get("ti3"))
        # The subject may be one of the rows just replaced, and a stale object
        # would draw the old numbers for ever.
        subject = self._run_key(self._report) if self._report else None
        rows = [r for s in self._sources for r in s["runs"]]
        self._report = next(
            (r for r in rows if subject and self._run_key(r) == subject),
            rows[-1] if rows else self._report)

    def _append_source(self, ti3: Path, origin: "Path | None" = None) -> bool:
        """Add one measurement to the source list (no repaint). Returns False if it
        is already present or has no runs. Raises on a gather error, so a batch add
        can report which files failed.

        *origin* is the file the user actually picked (the same as *ti3* for a
        ChromIQ .ti3, but the original .mxf/.txt/.cxf when *ti3* is a temp
        conversion). The report is saved next to the origin, never the temp folder
        (Knut)."""
        # **EITHER THE SAME PLACE OR THE SAME FILE, BECAUSE NEITHER ALONE IS
        # ENOUGH.** Keying on the path let a second SPELLING of one measurement
        # in twice (a firmlink, another capitalisation: +1 row each, and one
        # sheet printed twice). Keying on the file's device and inode fixed
        # that and broke the other half: an inode does not survive the file
        # being REPLACED, which `os.replace`, a Finder replace, an export
        # written again and a synced folder all do, so the same path added
        # again became a third row and the Report Scope read "2 runs" for one
        # file (R19-2, a regression from the fix for R18-F2). A source is
        # already here when it matches on either.
        keys = self._source_keys(ti3, origin)
        for s in self._sources:
            if set(s.get("keys") or ()) & set(keys):
                # **A MEASUREMENT THE USER ADDS IS THE USER'S (GAP 0).** A
                # report across runs loads the other run's dates as BORROWED
                # (`_load_the_documents_other_measurements`); adding one of
                # them through "Add Profile's Measurements…" matched it here
                # and left it borrowed, so the next report picked unloaded
                # what the user had asked for. Asked for, it stays.
                borrowed = getattr(self, "_borrowed_sources", None)
                if borrowed:
                    borrowed.discard(str(s.get("ti3")))
                # **AND THE MATCH REFRESHES WHAT IT MATCHED ON.** The key set
                # was worked out once, when the source was added, and never
                # again: rewrite the file and its identity half goes stale for
                # good, so the NEXT spelling of it matches nothing and comes in
                # as a second row. Driven: add, replace in place, then add the
                # same file under another capitalisation, and the Report Scope
                # listed `exported - 1 run` and `EXPORTED - 1 run` with "No. of
                # Measurements: 3" for two files on the disk (R20-F1). What was
                # matched is this measurement, so what it answers to is updated
                # to what it answers to now.
                s["keys"] = tuple(dict.fromkeys(tuple(s.get("keys") or ())
                                                + tuple(keys)))
                # **AND THE MEASUREMENT ITSELF IS READ AGAIN, BUT ONLY WHEN
                # THE FILE HAS MOVED ON.** Refreshing the keys and returning
                # leaves `runs` exactly as it was when the source was first
                # added, and `runs` is the measurement. Driven through the real
                # Add button: a sheet added at 8 patches, re-measured in place
                # to 12, and added again still read **8**, with no message and
                # no change to the document; a fresh window on the same file
                # read 12, and an unrelated click later corrected it in silence
                # (Average ΔE 20.91 to 23.20, Spread 10.67 to 9.69, and a row
                # appearing that says the chart has 12 patches). Asking to add
                # a measurement that is already here is the clearest way a user
                # can say "look at this file again" (R21-F1).
                #
                # **THE FIRST VERSION OF THIS CALLED `_reload_sources`, AND
                # THAT WAS WRONG TWICE OVER (R22-F1, R22-F2).** It re-read
                # EVERY loaded source and ended in `_render`, which is the one
                # place that stamps `_doc_built_with`:
                #
                # * a duplicate add of an UNCHANGED file took the red "Settings
                #   changed" line down and put settings nobody had confirmed
                #   into the document, on screen, with nothing added and
                #   nothing written;
                # * and with 12 sources loaded, re-picking 11 already-loaded
                #   files cost **5.5 seconds and 132 `_gather_runs` calls**,
                #   synchronously, with no cursor and nothing on screen,
                #   because `_on_add_project` calls this in a loop.
                #
                # A file that has not changed has nothing to say, which is what
                # the code before R21 got right. So the disk is asked first,
                # only this one source is re-read, and the banner survives it:
                # re-reading a measurement is not the user confirming the
                # settings they moved.
                if not self._source_has_moved_on(s):
                    return False
                self._reread_one_source(s)
                # **`_rebuild_from_sources`, NOT `_render`.** The history rows,
                # the profile list and the button states all come from
                # `self._sources`, and a repaint that skips them redraws the
                # document from rows that were replaced a line above.
                #
                # **AND THE PAGE IS NOT REDRAWN (Knut, #182 5816794672):**
                # *"re-adding a file that changed on disk ... should result in
                # the red warning text appearing that settings have changed,
                # and never automatically change a report."* The list reads
                # the file again; the page, the graphs and the PDF stay the
                # report on screen, and the red line says the measurement it
                # covers has moved on (`_page_coverage_moved`, which compares
                # the file's disk stamp).
                with self._keeping_the_page():
                    self._rebuild_from_sources()
                return False
        key = keys[0]
        name, runs = self._gather_runs(ti3)
        # **A MEASUREMENT ANOTHER SOURCE ALREADY HOLDS IS NOT A SECOND ROW
        # (#182 beta 39, G7).** A profiling sheet gathers every run's sheet of
        # its project for the trend (#40), so loading run 2's sheet into run
        # 1's window brought run 1's sheet in a second time. It was reached
        # once a report across runs stopped leaving a record in run 2 (the
        # record is what made run 2's sheet part of run 1's gathering, so the
        # borrowed source was never added): run 1's window opened on that
        # report, loaded run 2 and listed run 1 twice.
        _key = MeasurementReportDialog._run_key
        have = {_key(r) for s in self._sources for r in s["runs"]}
        runs = [r for r in runs
                if not (r.get("_origin_dir") and r.get("ti3"))
                or _key(r) not in have]
        if not runs:
            return False
        # ASKED ONCE, HERE, because this is the one place a measurement joins
        # this window. The reading opens the file, so it is not something to
        # repeat on every repaint. See `_scale_label`.
        from ui.measurement_filing import the_colour_scale_note
        self._sources.append({"key": key, "keys": keys,
                              "name": name, "dir": ti3.parent,
                              "ti3": ti3, "origin": Path(origin or ti3),
                              "runs": runs,
                              "stamp": self._disk_stamp(ti3),
                              "scale_note": the_colour_scale_note(ti3)})
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
            # The window was opened ON this measurement — with "Show all
            # measurement runs" off it must show exactly that date, as its
            # own tooltip promises, not silently the history's newest
            # (found by Knut's report demo package, 2026-08-10).
            # ...AND THE SOURCE IT WAS JUST GIVEN, not `_sources[0]`, which is
            # a different measurement as soon as anything was loaded first.
            self._report = self._subject_of(self._sources[-1])
            self._rebuild_from_sources()

    def _one_row_per_measurement(self, runs: list) -> list:
        """The gathered history, with the SAME MEASUREMENT listed once.

        A row in this window is a MEASUREMENT: it is labelled with the
        measurement's date, it is one point on "Trend over time (this
        printer)", and it is what "No. of Measurements" counts. A saved report
        is a document ABOUT a measurement, and a run may hold several of them
        legitimately, which is Knut's ruling of 2026-09-11: *"A user should be
        allowed to print several report types for a run … The Report window
        must thus show which type of reports have been generated"*. Which types
        exist is said by its own line above the table
        (`_generated_types_line`); it was never the job of the run list, and
        the run list cannot do it anyway, because every row of it carries the
        same date and reads identically.

        WHAT IT LOOKED LIKE. `_gather_runs` yielded one row per report FILE, so
        a run with two saved reports of one measurement showed "2 runs", two
        identical rows, "No. of Measurements: 2", and a trend line drawn from
        the measurement to itself between one date and the same date. And
        because `build_report` stamps `created` from the MEASUREMENT (not from
        the moment Generate was pressed), the two rows also shared a
        `_run_key`, so unticking either one took both off the page. Driven on
        screen 2026-09-15 in `~/Desktop/ChromIQ-beta18-proof/combined-round-1/`
        (`D2-report-window-with-two-saved-reports.png`): 2 rows, 1 distinct
        key, and hiding one row left 0.

        IT IS THE OTHER HALF OF A RULE THIS WINDOW ALREADY APPLIES.
        `_reports_to_generate` writes "one report per MEASUREMENT rather than
        one per report already saved of it", for the same reason and with the
        same key; the reading side was left on the old rule, so the count the
        writer had just stopped doubling was doubled again on the way back in.

        The newest report of a measurement wins, so the row carries the type
        and the limits the user most recently asked for. Nothing is deleted:
        every file stays on disk and the types line still counts them all.

        AND "NEWEST" IS NOT THE GREATEST FILE NAME AS A STRING.
        `save_report` numbers a second report of the same second `_2`, `_3`, …,
        so past nine the suffixes stop sorting: `"…_9.json" > "…_16.json"`, and
        the row carried the NINTH report of that second instead of the
        sixteenth. Measured on the pack a tester sent in, one folder holds
        sixteen reports stamped `2026-09-15_13-35-33` and the string maximum of
        them is `_9`. Nothing visible came of it there, because all sixteen
        carry the same type and the same limit set; the promise in the
        paragraph above was broken all the same, and the next Generate that
        changes either would have been the one to show it.
        `_report_file_order` reads the stamp and the suffix as what they are.

        AND THE KEY IS `_run_key`, WHICH INCLUDES THE DATE. This first shipped
        keyed on the folder and the file name alone, and that is not a
        measurement: measuring a run AGAIN archives the previous `.ti3` into
        `old/` and writes the new one under the SAME name, so one run folder
        accrues a dated report per measurement, which is the whole of the
        over-time trend (#40). On a real disk, `printer-test/runs/run1` holds
        eleven such reports and fifty-five archived measurements; the window
        opened on it said "1 run", "No. of Measurements: 1", a date range of
        one day to the same day, and "A trend graph needs at least two
        measurement runs … tick 'Show all measurement runs'" with that box
        already ticked, while the line above it read "Already generated for
        this run: Full colour check (11)". Ten of the eleven measurements were
        gone from the list, from the tables and from the trend. Photographed on
        screen in `~/Desktop/ChromIQ-beta18-proof/combined-round-2/`
        (`E1-report-window-on-a-run-measured-many-times.png`).

        `_run_key` is this class's own answer to "which run is this", and its
        docstring gives the reason for each of its three parts. Two reports OF
        ONE MEASUREMENT still merge, because `build_report` stamps `created`
        from the measurement, so they share it; two MEASUREMENTS never do.
        """
        groups: "dict[str, list]" = {}
        order: list = []
        for r in runs:
            origin = str(r.get("_origin_dir") or "")
            if not origin:
                order.append(r)   # nothing to key on: never merged with another
                continue
            key = self._run_key(r)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(r)
        out: list = []
        for item in order:
            if not isinstance(item, str):
                out.append(item)
                continue
            group = groups[item]
            files = [str(r.get("_report_file") or "") for r in group]
            # THE ONE THE USER PICKED IN "Saved reports", IF THEY PICKED ONE.
            # A run may hold several reports of one measurement (Knut,
            # 2026-09-11) and until B8-250 only the newest could ever be seen.
            # A choice that no longer names a file on disk falls back to the
            # newest rather than emptying the row.
            want = self._chosen_reports.get(item)
            pick = None
            for r in group:
                if want and str(r.get("_report_file") or "") == want:
                    pick = r
                    break
            if pick is None:
                # **A VERDICT RECORD IS NOT THE DATE'S OWN REPORT (K31).**
                # Records an earlier ChromIQ wrote for a report of several
                # dates are read-only history of THAT report (they speak only
                # when it is loaded, through `want` above); the date's own row
                # is its newest own report OF ONE DATE (§25.1).
                #
                # **AND NEITHER IS A PRE-K23 COPY, AND NOTHING STANDS IN FOR
                # A MISSING ONE (B40-A 2 and 4).** This read `own = [...] or
                # group`, so a date whose own report was gone was drawn from
                # a record, verdict and all, and a date holding a newer copy
                # of a report of several dates (what a build before K23 wrote
                # into every date) was drawn from that copy. A date with no
                # report of its own is a measurement with no saved report:
                # its measured numbers, judged live and marked "(not saved)",
                # exactly as a date measured with the report switched off.
                # Every file stays listed through `_all_report_files`.
                own = [r for r in group if self._is_own_one_date_report(r)]
                if own:
                    pick = own[0]
                    for r in own[1:]:
                        if (_report_order(r.get("_origin_dir"),
                                          r.get("_report_file"))
                                >= _report_order(pick.get("_origin_dir"),
                                                 pick.get("_report_file"))):
                            pick = r
                else:
                    pick = self._measured_numbers_only(group[-1])
            # EVERY report file of this measurement, so the selector can offer
            # them without reading the folder again.
            pick["_all_report_files"] = files
            out.append(pick)
        return out

    @staticmethod
    def _is_own_one_date_report(rep: "dict | None") -> bool:
        """Is *rep* a date's own report of ONE date (§25.1)?

        Not a verdict record (K23, role "record"), and not a copy of a
        report of several dates that a build before K23 wrote into each
        date's folder (no role, scope "Multiple" or "All dates"). A file
        with no document block at all is a report of its one date, as it
        always was."""
        from workflow.measurement_report import (SCOPE_ONE_DATE,
                                                 document_scope_of,
                                                 is_verdict_record,
                                                 recorded_document)
        if not isinstance(rep, dict) or is_verdict_record(rep):
            return False
        return document_scope_of(recorded_document(rep)) == SCOPE_ONE_DATE

    @staticmethod
    def _measured_numbers_only(rep: dict) -> dict:
        """A copy of *rep* that keeps what was MEASURED and drops what a
        report said about it (B40-A 2): the row of a date with no report of
        its own. It is judged live (``_fresh``) and names no file, so
        nothing reads the other report's block or verdict as the date's."""
        row = {k: v for k, v in rep.items()
               if k not in ("verdict", "pass_thresholds", "compliance",
                            "document", "report_type", "_report_file")}
        row["_fresh"] = True
        return row

    def _is_this_measurement(self, r: dict, ti3: Path,
                             dates_by_origin: "dict | None" = None) -> bool:
        """Whether a gathered row is about the measurement THIS FILE HOLDS NOW.

        ONE IDENTITY, THREE USES. `_measurement_for` already answers "which
        measurement is this report's"; this asks the same question from the
        other end, so the history, the rebuild and the subject cannot disagree
        about what a measurement is. They did: this line used to ask
        `_report_is_about`, which matches on the run folder plus the bare file
        NAME, and every measurement of one run carries that pair.

        WHAT THAT COST, driven on screen through the app's own
        `MeasurementSession` and its own `_maybe_save_measurement_report`
        (`~/Desktop/ChromIQ-beta18-proof/combined-round-3/`,
        `L1-the-window-on-a-measurement-with-no-report-of-its-own.png`). With
        *Preferences ▸ Save measurement report* switched off, a run measured
        again leaves no report of the new sheet, and the eleven reports already
        in the folder answered "yes, this measurement is in the history". No
        row was added for it, so the window opened on a measurement of 90
        patches read 2026-09-15 and described one of 15 patches read on
        2026-08-08 — an older sheet, its verdict and its date — and Generate
        report would have filed a report about that older sheet while the page
        in front of the reader was supposed to be about the new one.

        `_report_is_about` is unchanged and still right where it is used: it
        picks the subject out of a history that already contains the right row,
        and its deliberate looseness is what lets a report saved before the
        name was kept still belong to its folder.
        """
        if str(r.get("_origin_dir", "")) != str(ti3.parent):
            return False
        here = (dates_by_origin or {}).get(str(ti3.parent))
        found = self._measurement_for(r, ti3.parent, ti3, dates_here=here)
        if found is None:
            return False
        # **THE SAME FILE UNDER ANOTHER CASE IS THIS FILE (#182 beta 38,
        # F1).** After a case-only rename a saved report names
        # "Report-Limits-verify.ti3", which on a case-insensitive volume IS
        # "report-limits-verify.ti3"; compared as strings they differed, and
        # the measurement the window was opened on was added a second time
        # (a date listed twice, driven on screen after the F1 rename).
        from core.file_manager import same_entry
        target = ti3.parent / ti3.name
        return found == target or same_entry(found, target)

    @staticmethod
    def _measurement_for(rep: dict, run_dir: Path, opened_on: Path, *,
                         dates_here: "set | None" = None) -> "Path | None":
        """The measurement a SAVED report was built from, or None.

        A saved report keeps the measurement's bare file NAME and its
        ``created`` stamp, and `workflow.measurement_report.created_stamp_for`
        is the one rule that produced that stamp. So the file in the run folder
        is certainly this report's measurement when its own stamp is the
        report's.

        WHEN THE STAMP DOES NOT MATCH, THAT IS NOT YET AN ANSWER, and the first
        cut of this said it was. It refused everything whose stamp had moved,
        and a dated verification's stamp moves for reasons that have nothing to
        do with measuring again: the demo package writes its reports with the
        dates it wants the history to show and leaves the files with the time
        they were generated. Driven on `Demo-Switching/runs/run2` on screen,
        both dated rows lost their ΔE block entirely — `avg_all` None, an empty
        trend — where the code before B8-205 had shown 20.146 and 20.042
        correctly, because a dated verification folder holds exactly ONE
        measurement and rebuilding from "the file in the folder" is right
        there. That is the shape B8-205 is NOT about.

        AND A FOLDER IS A PROXY, WHICH IS WHY THE FILE IS ASKED FIRST NOW.
        The two folder tests below stand for "this folder has held more than
        one measurement under that name", and they only see the doors that
        leave something behind. AVERAGING LEAVES NOTHING:
        `Run.promote_measurement_to_read` MOVES the measurement into
        `reads/readN.ti3`, so the next read's `MeasurementSession.begin` finds
        no file to archive, and `_run_average_and_proceed` then writes the
        averaged sheet straight over `Run.measurement_ti3`. Driven on screen
        with the app's own moves and ArgyllCMS `average`
        (`~/Desktop/ChromIQ-beta18-proof/combined-round-4/`,
        `C-C-Averaged-Old-Report.png`): a run whose saved report held delta-E00
        11.776 and paper white A14 L* 92.72 showed ONE row, under the saved
        report's own date, reading 13.513 and C5 L* 91.74 — the averaged
        sheet's numbers — and the measurement the window was opened on had no
        row, no trend point, and Generate report would have filed about the
        older sheet.

        So `workflow.measurement_report.facts_disagree` asks the FILE: a saved
        report records how many readings its measurement held and its lightest
        and darkest patch, and a file that contradicts them is not it. That is
        one-sided on purpose — agreement is not proof, so the folder tests
        still run underneath.

        So the stamp settles it one way, the file's own facts settle it the
        other, and the FOLDER is the last word for a report too old to record
        anything comparable. The file is refused where something on disk says
        this folder has held more than one measurement under that name:

        * an archived copy of it in ``old/<when>/``, which is what
          `MeasurementSession.begin` leaves behind every time a measurement is
          made over another one; or
        * a ``reads/readN.ti3`` beside it, which is what
          `Run.promote_measurement_to_read` leaves behind when the person
          answers "Measure again to average"; or
        * another saved report in the same folder carrying a different
          ``created``, which cannot happen unless there was another
          measurement to report.

        Neither is true of a run measured once, or of any dated verification
        folder. Both are true many times over of the run this was found on
        (`CR30-Test/runs/run1`: 22 archives, 17 distinct dates).

        THE NAME COMES FROM THE REPORT, and falls back to the file the window
        is about when the folder has no such file. Renaming a target renames
        the measurement and leaves the saved reports naming the old stem, so
        "the report names a file that is not here" is an everyday state and not
        a foreign report. A report that names a file which IS here, and a
        different one, is left alone.

        THE ARCHIVED COPY IS NOT OFFERED AS A REBUILD SOURCE, ON PURPOSE, AND
        THE FIRST REASON WRITTEN HERE FOR THAT WAS WRONG. It said an archived
        measurement cannot find a design reference. It can:
        `_find_reference_ti2` climbs three levels for a dated verification, and
        from ``runs/runN/old/<when>/`` those same three levels land on the run
        root, so `build_report` on an archive comes back with
        ``reference_source: design`` and a full ΔE block. Measured on three
        archives of `CR30-Test/runs/run1` before this paragraph was rewritten.

        The real reasons are two, and both are about being WRONG rather than
        empty. The reference it finds is whatever chart is in the run TODAY,
        and `_find_reference_ti2`'s own docstring records what that costs: a
        trend point that jumped to ΔE ≈ 41 after the chart was swapped, against
        an honest 2.8. A dated verification is protected from that by the
        ``chart/`` snapshot written beside it at measure time; an ``old/``
        archive has no snapshot, and a profiling run's chart can be generated
        again into the same run. And `_sheet_kind` reads the FOLDER, so a
        measurement rebuilt from ``old/<when>/`` comes back as ``standalone``
        and stops being the profiling sheet it was.

        The numbers a saved report already holds were computed from the right
        measurement AND the chart of the day. Nothing available now beats that,
        so where this answers None nothing replaces them.
        """
        from workflow.measurement_report import created_stamp_for, facts_disagree
        want = str(rep.get("created") or "")
        if not want:
            return None
        named = str(rep.get("ti3") or "")
        live = run_dir / (Path(named).name or opened_on.name)
        if not live.is_file():
            if named and (run_dir / opened_on.name).is_file():
                live = run_dir / opened_on.name   # the target was renamed
            else:
                return None
        if created_stamp_for(live) == want:
            return live
        # The stamp has moved. ASK THE FILE FIRST, wherever the folder is
        # capable of having held a second measurement under this name. A saved
        # report keeps three facts about its own measurement — how many
        # readings it held and its lightest and darkest patch — and a file
        # whose own facts contradict them is a different sheet whatever the
        # folder looks like.
        #
        # NOT IN A DATED VERIFICATION FOLDER, and that is B8-206's own sentence
        # rather than a new exception: such a folder holds exactly ONE
        # measurement (a replaced verification is archived into
        # `verifications/old/`, outside the dated folder), so the file in it is
        # the only candidate there has ever been. It matters because the demo
        # package writes a STUB report into each dated folder to give the
        # history its date — schema 5, no accuracy block at all, "patches": 240
        # and a paper white of L* 95.4 beside a real 64-patch sheet whose white
        # is L* 99.53. Measured on `Demo-Switching` and `Demo-Prefs-Speed`,
        # both dates, 2026-09-15. Asking the file there would take the accuracy
        # figures off exactly the rows B8-206 exists to keep, and the folder
        # tests below still catch a dated verification that really was
        # measured twice.
        from core.file_manager import VERIFICATIONS_DIRNAME
        if run_dir.parent.name != VERIFICATIONS_DIRNAME \
                and facts_disagree(rep, live):
            return None
        # Then the folder, for a report too old to record anything comparable.
        old_root = run_dir / "old"
        if old_root.is_dir() and any((d / live.name).is_file()
                                     for d in old_root.iterdir() if d.is_dir()):
            return None
        if (run_dir / "reads").is_dir() and \
                any((run_dir / "reads").glob("read*.ti3")):
            return None
        if any(c and c != want for c in (dates_here or set())):
            return None
        return live

    @staticmethod
    def _report_is_about(r: dict, ti3: Path) -> bool:
        """Whether a gathered report describes THIS measurement file.

        A saved report keeps the measurement's bare file NAME (`build_report`
        stores no path), and `_gather_runs` records the folder it was read from
        as `_origin_dir`, so the pair is the identity. The folder alone is not:
        a run folder holds `<name>.ti3` beside `preconditioning.ti3` and
        `merged.ti3`, and somebody's Downloads folder holds whatever they put
        there. A report saved before the name was kept carries none, and is
        matched on its folder alone rather than declared foreign.
        """
        if str(r.get("_origin_dir", "")) != str(ti3.parent):
            return False
        name = str(r.get("ti3") or "")
        return (not name) or Path(name).name == ti3.name

    def _subject_of(self, src: dict) -> dict:
        """THE MEASUREMENT A SOURCE IS ABOUT: the file the window was opened on,
        or the file the user added, never the newest thing in its history.

        The history a source carries deliberately spans the project's runs (#40,
        Knut: the printer's full measurement history), so its newest entry is
        routinely a DIFFERENT run's measurement. Every place that needs "the
        measurement in hand" asks this, and every place that wants the trend
        asks `_runs_for_report`.
        """
        runs = src.get("runs") or []
        ti3 = src.get("ti3")
        if ti3 is not None:
            ti3 = Path(ti3)
            mine = [r for r in runs if self._report_is_about(r, ti3)]
            if mine:
                return mine[-1]
            # Nothing about this exact file: a report from its own FOLDER is
            # still this run's, which is nearer than the history's newest.
            here = [r for r in runs
                    if str(r.get("_origin_dir", "")) == str(ti3.parent)]
            if here:
                return here[-1]
        return runs[-1]

    @staticmethod
    def _run_key(r: dict) -> str:
        """A stable identity for one run across list rebuilds.

        THE FOLDER IS PART OF IT. Created plus file name was not an identity in
        a project with several profile runs: every run's measurement carries the
        SAME file name (the sanitised project name), so two runs measured in the
        same second were one key. Unticking one row then hid both, and the
        one-page summary could pick either. The same collision is on record for
        two dated verifications built at load time
        (`tests/test_the_one_page_summary_is_about_one_sheet.py`); this removes
        the class rather than the instance. Session-only: `_hidden_runs` is the
        only thing that keeps one.
        """
        return (f"{r.get('_origin_dir', '')}|{r.get('created', '')}"
                f"|{r.get('ti3', '')}")

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

    def _rebuild_from_sources(self, repaint: bool = True) -> None:
        """Recompute the history, the profile list and button states, then repaint
        the trend + report.

        *repaint* False (K32) redraws the list and the buttons only: the page
        and the graphs stay the document they are, and the red line says
        whether the settings on screen still match it."""
        self._history = sorted(
            (r for s in self._sources for r in s["runs"]),
            key=lambda r: str(r.get("created") or ""))
        self._project_dirs = {s["dir"] for s in self._sources}
        self._building_list = True
        try:
            self._profile_list.clear()
            self._list_rows = []
            # THE SAME MARK AFTER THE SAME NAME the other three doors put it
            # after, so a row says WHICH measurement the sentence below the
            # buttons is about. See `_scale_label`.
            from ui.measurement_filing import the_colour_scale_tag
            _unticked = self._rows_drawn_unticked()
            for si, s in enumerate(self._sources):
                n = len(s["runs"])
                # A CALIBRATION HAS MEASUREMENTS, NOT RUNS (K30 leftover, as
                # B10 put it for the report's Scope): "P-cal · 1 run" named a
                # profile run that a calibration is not. AND NEITHER DOES A
                # LIST OF DATES (re-challenge R2 of beta 39, #15): the rows
                # under this header are measurements, one per date, and
                # "· 3 runs" stood above three dates of ONE run. So every
                # header counts measurements.
                self._profile_list.addItem(
                    f'{s["name"]}  ·  {n} '
                    + (tr("measurement") if n == 1 else tr("measurements"))
                    + (the_colour_scale_tag() if s.get("scale_note") else ""))
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
                        Qt.CheckState.Unchecked if key in _unticked
                        else Qt.CheckState.Checked)
                    self._profile_list.addItem(item)
                    self._list_rows.append(("run", si, key))
        finally:
            self._building_list = False
        self._size_profile_list()
        self._show_the_colour_scale_note()
        has = bool(self._sources)
        # A kept page is still a report on screen, and its PDF can be saved
        # with the list emptied under it (Knut, 2026-09-18: the button is
        # greyed only "if no report is loaded in the window at all").
        self._pdf_btn.setEnabled(has or self._page_shows_a_report())
        self._reveal_btn.setEnabled(has)
        self._clear_btn.setEnabled(has)
        self._update_source_buttons()
        # THE LATEST REPORT, WITH ITS OWN SETTINGS, ONCE PER WINDOW (B8-388).
        # Before `_refresh`, so the page is drawn with those settings already
        # on it rather than drawn twice.
        if not repaint:
            self._forget_limits()
            self._sync_limit_controls()
            self._show_stale_banner()
            return
        before = len(self._sources)
        self._open_on_the_latest_report()
        if len(self._sources) != before:
            # the report it opened on covers measurements that were not in
            # the list (A-F1), and they are now: the list is drawn again.
            # `_open_on_the_latest_report` runs once per window, so this
            # cannot come back here a second time.
            self._rebuild_from_sources()
            return
        self._refresh()

    def _show_the_colour_scale_note(self) -> None:
        """Say, once, that a measurement in this window is on the 0-to-1 scale.

        THE WORDS ARE NOT THIS WINDOW'S. They are the two strings the Build ICC
        profile tab has shown since 2026-09-11 and both import doors have shown
        since combined round 10, held in
        :func:`ui.measurement_filing.the_colour_scale_note` and
        :func:`~ui.measurement_filing.the_colour_scale_tag` so that four doors
        cannot drift apart and no new message text enters §M. The tag names
        which row it is about; this says what it means.

        A hidden label claims no space in a Qt layout, so the row costs nothing
        until there is something to say - the same reason `_stale_label` sits
        on a row of its own rather than in the button row.
        """
        lbl = getattr(self, "_scale_label", None)
        if lbl is None:
            return
        note = next((s.get("scale_note") for s in self._sources
                     if s.get("scale_note")), "")
        lbl.setText(note)
        lbl.setVisible(bool(note))

    #: Five visible rows, then a scrollbar — Sebastian's number (2026-08-10).
    #: The MINIMUM stays at two rows so the window's own overlap-free floor
    #: can never be pushed past a small screen by a long run history: a hard
    #: multi-row floor did exactly that (the layout minimum outgrew the
    #: screen, Qt refused the smaller resize, and the window's bottom — Close
    #: included — landed off-screen).
    _LIST_VISIBLE_ROWS = 5

    def _size_profile_list(self, *, compact: bool = False,
                           rows: "int | None" = None) -> None:
        """Size the list to its content, capped at ``_LIST_VISIBLE_ROWS``
        visible rows — past the cap the list scrolls internally, and that is
        the one scrollbar above the chart tabs (Knut's beta.5 point, settled
        with Sebastian 2026-08-11: "limited to 5 lines … then scroll after
        the 5 lines"). ``compact`` shrinks it to two rows when the window's
        own minimum would otherwise not fit the screen."""
        n = len(self._list_rows)
        if rows is None:
            rows = 2 if compact else min(max(n, 1), self._LIST_VISIBLE_ROWS)
        rows, h = self._list_box(rows)
        #: how many rows the list is sized to show, for the fit after show
        self._list_rows_shown = rows
        self._profile_list.setMinimumHeight(h)
        self._profile_list.setMaximumHeight(h)
        # **THE TWO BUTTONS BESIDE IT KEEP THEIR OWN HEIGHT (B8-956).** They
        # sit in a column to the right of the list. B8-590 capped them to a
        # list compacted to two rows, so the row could never be taller than
        # the list, and at the 760 px minimum size that squashed Select all /
        # Deselect all to about half their height with the text touching the
        # frame, over a list showing one date (beta 40 second check, a4-en
        # and a4-de, *-3-minimum-size.png). The LIST now yields to them
        # instead: `_list_box_height` never goes below the column's natural
        # height, and the window's fitting gives up the report view and the
        # charts first (`showEvent`, `_keep_the_list_inside_the_window`).
        for b in (getattr(self, "_select_all_btn", None),
                  getattr(self, "_deselect_all_btn", None)):
            if b is not None:
                b.setMinimumHeight(0)
                b.setMaximumHeight(16777215)

    def _tick_column_height(self) -> int:
        """Select all over Deselect all at their natural height, with the
        spacing between them (B8-956)."""
        btns = [b for b in (getattr(self, "_select_all_btn", None),
                            getattr(self, "_deselect_all_btn", None))
                if b is not None]
        if not btns:
            return 0
        return sum(max(b.sizeHint().height(), b.minimumSizeHint().height())
                   for b in btns) + 6 * (len(btns) - 1)

    #: never fewer whole rows than this, whatever the window's height
    _LIST_MIN_ROWS = 2

    def _list_box(self, rows: int) -> "tuple[int, int]":
        """``(rows, height)`` the list is given when *rows* rows are asked
        (B8-956): whole rows, at least `_LIST_MIN_ROWS`, and never lower than
        the column of buttons beside it. Rows are added (whole ones, so no
        sliver of the next peeks in) until the column fits; past the last
        row the list is simply taller than its content."""
        n = len(self._list_rows)
        rows = max(rows, self._LIST_MIN_ROWS)
        column = self._tick_column_height()
        h = self._list_height(rows)
        while h < column and rows < n:
            rows += 1
            h = self._list_height(rows)
        return rows, max(h, column)

    def _list_box_height(self, rows: int) -> int:
        return self._list_box(rows)[1]

    def _list_height(self, rows: int) -> int:
        """The list's height for *rows* whole rows, its frame included."""
        n = len(self._list_rows)
        # **THE FRAME AND NOTHING ELSE (B8-921).** This was `+ 4` on top of
        # the frame, and the viewport is the list's height minus the frame
        # only, so with a sixth row waiting the list painted four pixels of it
        # under the fifth: measured on screen, viewport 84 px over five
        # 16 px rows, row 6 at y 80. Basti photographed that sliver, half
        # behind the "Report type" pulldown.
        frame = 2 * self._profile_list.frameWidth()
        # Sum the real row heights — the checkable run rows are a few px
        # taller than the profile header row, so a rows×row_h estimate either
        # clipped the last visible row in half or let a sliver of the next
        # one peek in.
        heights = [self._profile_list.sizeHintForRow(i)
                   for i in range(min(n, rows))]
        if not heights or min(heights) <= 0:
            heights = [self._profile_list.fontMetrics().height() + 8] * rows
        return sum(heights) + frame

    def _layout_need(self) -> int:
        """The height this window's layout needs at its NARROWEST width.

        **NOT `minimumSize` (B8-921).** The wrapped labels (the intro, the
        "Already generated" line, the limits note) are height-for-width, and
        `minimumSize` does not count them. Measured on screen on
        Report-Limits-Threshold-Series: minimum 1065 px, window 1065 px, and
        the layout's own height for that width 1081. Qt found the 16 px by
        squeezing the "Report settings" frame 6 px below its 237 px minimum,
        and the "Report type" pulldown, which cannot shrink, was pushed 3 px
        up over the list (10 px at the 760 px minimum width). The narrowest
        width is the one asked, because a label only wraps further as the
        window narrows.
        """
        layout = self.layout()
        if layout is None:
            return 0
        layout.activate()
        need = layout.minimumSize().height()
        if layout.hasHeightForWidth():
            narrowest = max(self.minimumWidth(), layout.minimumSize().width())
            # THE LIMIT-LINE KEY IS NOT A NEED (K45-2). The height-for-width
            # total counts every item at its PREFERRED height, the key's lines
            # included, and a need that holds them sent the ladder below into
            # the graphs: measured on screen at 1400 x 980, Colour accuracy
            # went from 110 px to 60 px for two lines of key. The key has no
            # minimum (`_TrendKey`); it is given its lines out of the report
            # view's room, the part of the window that scrolls anyway.
            # Read from the LAYOUT'S item, whose cached hint is the one the
            # total was made of, with the spacing the item brings along.
            key = getattr(self, "_trend_key", None)
            box = getattr(self, "_trend_key_box", None)
            spare = 0
            if key is not None and box is not None and not key.isHidden():
                item = box.itemAt(box.indexOf(key))
                if item is not None and item.sizeHint().height() > 0:
                    spare = item.sizeHint().height() + max(0, box.spacing())
            need = max(need, layout.totalHeightForWidth(narrowest) - spare)
        return need

    def event(self, ev) -> bool:  # noqa: D401
        """A relayout after the window is on screen is checked against the
        window's ceiling once the event loop is idle (B8-921)."""
        from PyQt6.QtCore import QEvent
        if (ev.type() == QEvent.Type.LayoutRequest
                and getattr(self, "_sized_to_screen", False)
                and not getattr(self, "_fit_queued", False)):
            self._fit_queued = True
            QTimer.singleShot(0, self._keep_the_list_inside_the_window)
        return super().event(ev)

    def _trend_charts(self) -> list:
        return [c for c in (getattr(self, "_trend_de", None),
                            getattr(self, "_trend_white", None),
                            getattr(self, "_trend_black", None),
                            getattr(self, "_trend_corners", None),
                            *getattr(self, "_trend_groups", {}).values())
                if c is not None]

    def _keep_the_list_inside_the_window(self) -> None:
        """After the window is on screen, what grows later (the list rebuilt
        for a report picked, a sentence that wraps) must not grow the layout
        past the window's ceiling.

        **THE LADDER RAN ONCE AND THE WINDOW KEPT GROWING (B8-921).**
        `showEvent` fits the window to the screen as it is at that moment,
        with the list compacted to two rows; picking a report rebuilt the list
        with five and set longer sentences, and nothing asked again. Measured
        on screen on Report-Limits-Threshold-Series: the layout needed
        1083 px at its narrowest in a window capped at 1039, Qt squeezed the
        "Report settings" frame to 218 px of its 233, and the "Report type"
        pulldown sat 8 px over the list (12 px at the 760 px width). So the
        report view yields first (it scrolls, down to 150 px), then the list
        gives up whole rows, down to the two the compact case keeps, and the
        window's own minimum follows what is left, so a drag cannot squeeze
        the frame either. Run again on every relayout, so a list that shrinks
        gets its rows back when they fit.
        """
        self._fit_queued = False
        if not getattr(self, "_sized_to_screen", False):
            return
        cap = self.maximumHeight()
        if cap >= 16777215:
            return
        if not hasattr(self, "_chart_floor0"):
            self._chart_floor0 = {}
        charts = self._trend_charts()
        # a chart that yielded (the last rung, B8-927) is given its height
        # back before the list gets a row back
        shrunk = any(c.minimumHeight() < self._chart_floor0.get(id(c), 0)
                     for c in charts)
        current = getattr(self, "_list_rows_shown", 2)
        wanted = min(max(len(self._list_rows), 1), self._LIST_VISIBLE_ROWS)
        if shrunk:
            wanted = min(wanted, current)
        # the layout's need with the list taken out, so every row count can be
        # tried without laying the window out once per try, and the list is
        # set once, which keeps this from answering its own relayout
        base = self._layout_need() - self._profile_list.maximumHeight()
        over = base + self._list_box_height(wanted) - cap
        view = getattr(self, "_view", None)
        if over > 0 and view is not None and view.minimumHeight() > 150:
            # the report view scrolls, so it yields first, down to the
            # ladder's first floor; the list's rows go only after that
            view.setMinimumHeight(max(150, view.minimumHeight() - over))
            base = self._layout_need() - self._profile_list.maximumHeight()
        rows = wanted
        while rows > 2 and base + self._list_box_height(rows) > cap:
            rows -= 1
        # the rows the list will really show, the buttons' floor counted
        rows = self._list_box(rows)[0]
        if rows != current:
            self._size_profile_list(rows=rows)
        # **AND THE VIEW'S NEXT RUNG OF `showEvent`'s LADDER (B8-927).** A
        # row that wraps at a narrow width (`ReflowRow`) grows the layout
        # after the window is on screen: measured at the 760 px minimum,
        # 1051 px (English) against a 1039 px ceiling with the list at two
        # rows and the view at 150, and Qt squeezed the frame. The report view
        # scrolls, so it yields to 120, the floor `showEvent` gives it. The
        # trend charts are not asked: a squeezed chart stops being a graph.
        over = self._layout_need() - cap
        if over > 0 and view is not None and view.minimumHeight() > 120:
            view.setMinimumHeight(max(120, view.minimumHeight() - over))
            over = self._layout_need() - cap
        # ...and only then the trend charts, by what is still missing and no
        # lower than 100 px (`showEvent`'s first chart rung). When there is
        # room again they get it back before the list gets a row back (see
        # `shrunk` above), so a chart never pays for a list row.
        if over > 0 and getattr(self, "_list_rows_shown", 2) <= 2:
            for c in charts:
                floor0 = self._chart_floor0.setdefault(id(c),
                                                       c.minimumHeight())
                want = max(min(100, floor0), c.minimumHeight() - over)
                if want != c.minimumHeight():
                    c.setMinimumHeight(want)
        elif over < 0 and shrunk:
            for c in charts:
                floor0 = self._chart_floor0.get(id(c), c.minimumHeight())
                want = min(floor0, c.minimumHeight() - over)
                if want != c.minimumHeight():
                    c.setMinimumHeight(want)
        # and the view's last rung, as in `showEvent` (B8-956): the list's
        # floor is the buttons' natural height, and the view scrolls
        over = self._layout_need() - cap
        if over > 0 and view is not None and view.minimumHeight() > 60:
            view.setMinimumHeight(max(60, view.minimumHeight() - over))
        floor = min(self._layout_need(), cap)
        if floor != self.minimumHeight():
            self.setMinimumHeight(floor)

    def _compact_the_settings_frame(self) -> None:
        """Take the air out of the "Report settings" frame and the row above it.

        Knut's beta-25 mockup is the layout this window ships; the frame it
        adds costs 30 px of a minimum that is measured against an 800 px
        screen, and 30 px is what this gives back. Only the SPACING moves:
        every control, its order and its size are his.

        Idempotent, and called only from `showEvent`'s ladder.
        """
        pair = getattr(self, "_roomy", None)
        if not pair or getattr(self, "_frame_compacted", False):
            return
        self._frame_compacted = True
        box_v, shown_grid = pair
        box_v.setContentsMargins(10, 0, 10, 2)
        box_v.setSpacing(3)
        shown_grid.setVerticalSpacing(0)
        grid = getattr(self, "_settings_grid", None)
        if grid is not None:
            grid.setVerticalSpacing(2)
        lay = self.layout()
        if lay is not None:
            lay.activate()

    def _draw_the_row_ticks(self) -> None:
        """Put `_hidden_runs` on the screen, without rebuilding the list.

        **THE TICK MARKS AND THE SET BEHIND THEM COULD DISAGREE, AND THE
        DOCUMENT BELIEVED THE SET (B8-521).** Only `_rebuild_from_sources`
        ever drew a row's tick, and it is the one door that re-reads the files;
        every OTHER place that assigns `_hidden_runs` -- choosing "New
        report…", loading a document, the page adopting the document Generate
        just wrote -- assigned it and repainted through `_refresh`, which
        touches the report body and the charts and never the list.

        So the list went on showing the PREVIOUS narrowing while the code
        believed the new one. Measured on Knut's own
        `Report-Limits-Threshold-Series` run 1, 11 dated verifications, in a
        real window: after Generate the list showed 11 ticks over a
        `_hidden_runs` of 10, and choosing "New report…" showed 1 tick over a
        `_hidden_runs` of none. From there every later tick is read against the
        wrong baseline, because `QListWidgetItem.setCheckState` to the value a
        row already holds emits nothing: a user unticking a row that the list
        draws as ticked and the set already calls hidden changes neither.

        That is Knut's beta-26 fault in both directions at once: *"Only the
        measurements ticked at the time I press Generate Report shall be
        stored as part of the report"* -- ticking three of eleven produced a
        report of ten.
        """
        if getattr(self, "_building_list", False):
            return
        unticked = self._rows_drawn_unticked()
        self._building_list = True
        try:
            for i, (kind, _si, key) in enumerate(self._list_rows):
                if kind != "run" or key is None:
                    continue
                item = self._profile_list.item(i)
                if item is None:
                    continue
                want = (Qt.CheckState.Unchecked if key in unticked
                        else Qt.CheckState.Checked)
                if item.checkState() != want:
                    item.setCheckState(want)
        finally:
            self._building_list = False

    def _rows_drawn_unticked(self) -> "set[str]":
        """Which rows the LIST shows unticked, which is not always
        `_hidden_runs`.

        **THE LIST HAS TO SHOW WHAT GENERATE WILL STORE (B8-523).** On a
        one-page colour summary the document is about ONE sheet whatever the
        rows say (`_one_measurement`), so drawing eleven ticks over a document
        of one is the fault Knut reported: *"the report name ended with 'One
        date' … the 'Included Measurements in report' box only had one (the
        last one) ticked"*, after he had ticked all eleven himself.

        **AND IT IS NOW `_hidden_runs` AND NOTHING ELSE (B8-591).** The rule
        above rested on one sentence, which used to be in this docstring: *"The
        list is disabled while T1 is chosen, so nothing a user can press
        disagrees with it."* The list is no longer disabled, because that was
        the freeze Knut reported, so the premise is gone and with it the rule.

        What it did while it stood was worse than the fault it replaced. It
        drew ten rows unticked while `_hidden_runs` kept them ticked, so the
        ticks a reader could see were not the ticks the report would use:
        measured on screen with three measurements and Select all pressed, the
        list showed **1** ticked while `_runs_for_report` returned **3**. That
        is the other half of what Knut reported in the same breath as the
        freeze, *"the 'included measurements in report' became unticked for
        all measurements"* — they had not been unticked, they had been drawn
        that way. And a real click on such a row toggled the item and was
        immediately painted back, which is indistinguishable from a dead list.

        A one-page summary still covers one measurement. It says so when
        Generate is pressed (`_one_page_wants_one_measurement`) instead of
        quietly drawing a different answer, so the list can go on telling the
        truth about itself.
        """
        return set(self._hidden_runs)

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
        # WHICH MEASUREMENTS THE REPORT IS ABOUT is one of the five settings he
        # named, so the document waits for Generate like the other four.
        self._settings_touched()

    def _on_select_all_measurements(self) -> None:
        """Tick every measurement row. Nothing else (B8-590)."""
        self._set_every_run_row(True)

    def _on_deselect_all_measurements(self) -> None:
        """Untick every measurement row. Nothing else (B8-590)."""
        self._set_every_run_row(False)

    def _set_every_run_row(self, ticked: bool) -> None:
        """The one body behind both buttons.

        It writes `_hidden_runs` and the item check states TOGETHER, in one
        pass with `itemChanged` blocked, and then touches the settings ONCE.
        Letting the per-item signal run would call `_settings_touched` eleven
        times for one click and, on a list whose rows are rebuilt while it is
        walked, would leave the set and the ticks disagreeing.
        """
        was, self._building_list = self._building_list, True
        try:
            for i, (kind, _si, key) in enumerate(self._list_rows):
                if kind != "run" or key is None:
                    continue
                item = self._profile_list.item(i)
                if item is None:
                    continue
                item.setCheckState(Qt.CheckState.Checked if ticked
                                   else Qt.CheckState.Unchecked)
                if ticked:
                    self._hidden_runs.discard(key)
                else:
                    self._hidden_runs.add(key)
        finally:
            self._building_list = was
        self._settings_touched()

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
        # A WINDOW SHOWING A REPORT HAS A REPORT TO KEEP, whether or not its
        # list still holds anything (Knut, #182 5816794672): after Clear List
        # the page is still the report, so what is added comes in unticked
        # like any other add, and only Generate draws a new page.
        had_sources = bool(self._sources) or self._page_shows_a_report()
        before = {self._run_key(r) for s in self._sources for r in s["runs"]}
        for path in paths:
            try:
                if self._append_source(self._as_ti3(Path(path)), origin=Path(path)):
                    added += 1
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{Path(path).name} — {exc}")
        if added and had_sources:
            # **ADDED MEASUREMENTS COME IN UNTICKED, AND THE PAGE DOES NOT MOVE
            # (K32, Knut on beta 41, #182 5815133233).** *"When adding new
            # measurement sets, they should by default not be checked, and
            # even if they were checked, the currently selected report should
            # get a warning that the settings for the report has been
            # modified ... and the report never automatically updated without
            # first clicking generate report."* Adding run 2's measurements to
            # run 1's window ticked them and drew the report again with them
            # in, under the selected report's name, with no red line.
            #
            # So the new rows are unticked, and unticked in what the document
            # was built with as well (it did not cover them), so the page, the
            # PDF and the red line all go on describing the document on
            # screen. Ticking one is a changed setting like any other: the red
            # line comes up and Generate asks.
            new = {self._run_key(r) for s in self._sources
                   for r in s["runs"]} - before
            self._hidden_runs |= new
            built = getattr(self, "_doc_built_with", None)
            if built is not None:
                built = list(built)
                built[3] = tuple(sorted(set(built[3]) | new))
                self._doc_built_with = tuple(built)
            # after Clear List the list had no subject left; the page keeps
            # its own (`_the_page_as_drawn`), the list takes the first added
            if self._report is None and self._sources:
                self._report = self._subject_of(self._sources[0])
            self._rebuild_from_sources(repaint=False)
        elif added:
            # AN EMPTY WINDOW HAS NO REPORT TO KEEP: the first measurements
            # added fill it, ticked, as they always have (a K32 decision, put
            # to Knut). The first source's own measurement, not the newest
            # thing in its history, which, since the history spans the
            # project's runs, is routinely another run's (see `_subject_of`).
            self._report = self._subject_of(self._sources[0])
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
            self._report = self._subject_of(first)
            self._ti3 = first.get("ti3") or first["dir"] / f'{first["name"]}.ti3'
        else:
            self._report, self._ti3 = None, None
        # **THE PAGE STAYS THE REPORT IT IS (Knut, #182 5816794672).**
        # *"Remove Profile's Measurements, Clear List, re-adding a file that
        # changed on disk, these should all result in the red warning text
        # appearing that settings have changed, and never automatically
        # change a report."* The list and the buttons follow the removal;
        # the page, the graphs and the PDF stay the document on screen
        # (`_keeping_the_page`), and the red line says it no longer matches.
        with self._keeping_the_page():
            self._rebuild_from_sources()

    def _on_clear_list(self) -> None:
        self._sources = []
        self._opened_empty = False       # the user emptied it (K32)
        self._borrowed_sources = set()
        self._report, self._ti3 = None, None
        # **NO SAVED REPORT SURVIVES THE CLEAR (round 2A, R2A-6).** The
        # cleared report stayed selected: the page went on printing its
        # "Created:" time and offering its PDF name after other measurements
        # were added, and Generate asked "Nothing was changed for the selected
        # report" and Update rewrote a report that was no longer in the list.
        self._loaded_doc_id = NEW_REPORT_KEY
        self._loaded_doc = None
        self._doc_created = ""
        self._doc_sources = None
        # …AND THE PAGE IS KEPT (Knut, #182 5816794672): the list empties,
        # the report on screen does not, and the red line comes up. What was
        # R2A-6's reason for deselecting the report still holds: nothing in
        # the list is that report any more, so "Report shown" is "New
        # report…" and Generate cannot Update it.
        with self._keeping_the_page():
            self._rebuild_from_sources()

    #: The five controls that describe WHAT REPORT TO MAKE, as opposed to which
    #: measurements exist. Knut, 2026-09-14, having asked for this and been
    #: asked whether he meant it: *"This change give the user more feeling of
    #: control and understanding of when something should change, or when a
    #: change will result in a changed report, and will see that it does change
    #: or not when clicking 'Generate report'. It will also give a user a
    #: chance to undo a changed field, if not wanting to regenerate the report.
    #: Make the change."*
    #:
    #: His observation was that the button looked inert, because the document
    #: already followed every control: *"The generate report button seems not
    #: to do much, as the report auto-generates whenever report type or judged
    #: against is changed."*
    _SETTINGS_THAT_NEED_GENERATING = (
        "report type", "judged against", "show all measurement runs",
        "show detailed data", "the measurements ticked in the list")

    def _doc_settings(self) -> tuple:
        """Those five settings AS THEY STAND NOW, in one comparable value.

        The banner is a COMPARISON, never a flag. Knut asked for both halves in
        one sentence: *"It will also give a user a chance to undo a changed
        field, if not wanting to regenerate the report."* A flag set on every
        change cannot see an undo, so putting the control back would leave a
        red line over a document that already matches it, which is the same
        lie the other way round.
        """
        def _data(name: str) -> str:
            combo = getattr(self, name, None)
            if combo is None:
                return ""
            try:
                return str(combo.currentData() or "")
            except RuntimeError:          # the window is going away
                return ""
        # FOUR, NOT FIVE, SINCE B8-590: "Show all measurement runs" is gone
        # and with it the setting that used to sit between the set id and the
        # detail box. The tuple is compared and restored, never unpacked
        # outside `_as_the_document_was_built._put`.
        return (
            _data("_type_combo"),
            _data("_set_combo"),
            bool(getattr(self, "_detail_check", None) is not None
                 and self._detail_check.isChecked()),
            tuple(sorted(getattr(self, "_hidden_runs", ()) or ())),
            # THE REPORT'S OWN LIMITS, when they were edited for a report
            # across places (#182 K30): a number changed in the limits window
            # is a changed setting of the report, and with the set unchanged
            # nothing else in this tuple would move.
            self._report_own_limits_signature(),
        )

    def _report_own_limits_signature(self) -> str:
        """The report's own edited limits as one comparable string, "" when
        the report has none (K30)."""
        own = getattr(self, "_report_own_limits", None)
        if own is None:
            return ""
        from workflow.compliance_sets import limits_to_json
        return own.set_id + "|" + json.dumps(limits_to_json(own.limits),
                                             sort_keys=True, default=str)

    def _settings_touched(self, *, type_id: str = "", set_id: str = "") -> None:
        """One of those five moved: keep the DOCUMENT as it is and say so.

        **AND THE LOADED DOCUMENT STOPS SPEAKING FOR THE CONTROLS.** A document
        restores the settings it was made with (L.2); the moment the user moves
        one of them, those are no longer the settings on screen, and a pulldown
        that went on showing the document's answer would be Knut's fifth defect
        with the halves swapped: an entry disagreeing with the window that names
        it. The document stays SELECTED and stays on the page, which is what the
        red line below is about; only its claim on the controls is dropped.

        The control keeps its own new value, and NOTHING HAPPENS ON DISK
        (K31, Knut 5801677743: *"changing the reports settings does not change
        the report, and its binding to a limit set, unless you click Generate
        Report"*): no run is bound and no saved report is recalculated. What
        waits is the document on screen, so a reader can put a control back
        and be sure nothing moved under them.
        """
        # **THE VALUES ON SCREEN SURVIVE THE DOCUMENT'S CLAIM (B8-462).**
        # Read from the WIDGETS, before the flag below drops the document,
        # because a widget is the only thing that knows what the user is
        # looking at: the handler that called this has already put the user's
        # new value into the control they moved, and the control they did not
        # move still shows the document's. Knut's rule is that the second one
        # must not budge, and this is the whole of it.
        self._remember_what_is_on_screen(type_id, set_id)
        self._doc_settings_moved = True
        self._forget_limits()
        self._sync_limit_controls()
        # **NOTHING WAITS FOR A BUTTON THAT CANNOT BE PRESSED.** `Generate
        # report` writes a dated report into ONE run, so it is disabled when
        # the window is on a measurement that belongs to no run, when SEVERAL
        # profiles are loaded, and when every measurement has been unticked.
        # The two tick boxes and the run ticks stay live in all three.
        #
        # An adversary round drove the middle one, which is this window's main
        # job: with two profiles loaded, "Show detailed data" froze the
        # document and a red line told the reader to press a greyed-out button.
        # Those settings did nothing at all, ever, and the only way out was to
        # put the control back. Before the deferral they repainted at once, and
        # where there is nothing to press they do so again.
        #
        # Read AFTER `_sync_limit_controls`, which is what recomputes it.
        #
        # **AND NOW NOT EVEN THERE (Knut, #182 5816794672).** *"The report text
        # should never automatically be updated in any situation, as a report
        # is a record of history and shall never we changed unless
        # deliberately done by a user."* A setting moved while Generate is
        # greyed keeps the page and raises the line like any other; the
        # controls that cannot un-grey Generate are greyed with it
        # (`_grey_what_cannot_help`), so the dead-button trap the adversary
        # round found is not reached by moving them. The only page this still
        # draws is the first one, in a window that has never drawn a report.
        if getattr(self, "_doc_built_with", None) is None \
                and not self._page_shows_a_report():
            self._refresh_trend()
            self._render()
            return
        self._show_stale_banner()

    def _remember_what_is_on_screen(self, type_id: str = "",
                                    set_id: str = "") -> None:
        """Pin the type and the limit set the window is showing.

        **B8-462**, and the two halves of it are the same rule seen from each
        end: changing "Judged against" must not move "Report type", and
        changing "Report type" must not move "Judged against". Both moved for
        the same reason, so both are fixed in one place.

        Called from `_settings_touched`, BEFORE the loaded document's claim on
        the controls is dropped, so the values read here are the ones the user
        is looking at. The handler that just took a change passes ITS new value
        in, and the other is read from what is on the page:

        * `_report_type_now` answers with the loaded document's type while the
          document still speaks, which is the type on screen, and not with the
          RUN's, which is the thing that must not reach the other pulldown;
        * the set is the document's, or an earlier pin, or the run's, in the
          order `_sync_limit_controls` fills the box from.

        **NOT FROM THE WIDGETS.** That was the first cut, and a widget is only
        the truth when the signal came from it: `_on_set_chosen` can be called
        with an index the box has not moved to, which is how two existing
        guards drive this door, and reading the box then pins the value the
        user has just left rather than the one they chose.
        """
        from workflow.measurement_report import REPORT_TYPES
        tid = str(type_id or self._report_type_now() or "")
        if tid in REPORT_TYPES:
            self._sticky_type = tid
        sid = str(set_id or "")
        if not sid:
            lim = (self._document_limits() or self._sticky_limits()
                   or self._window_limits())
            sid = str(getattr(lim, "set_id", "") or "")
        if sid:
            self._sticky_set = sid

    def _settings_were_modified(self) -> bool:
        """Have the five settings moved since the page was drawn?

        The one answer to the question the red line asks and the question
        Knut's beta-25 popup asks, because they are the same question: *"If any
        of the settings are changed, a red text message will show user that he
        must click Generate Report to apply settings. When Generate Report is
        then clicked, the user must be shown a popup message…"*. Two copies of
        it would be a window whose line is up and whose button asks nothing.
        """
        built = getattr(self, "_doc_built_with", None)
        # …AND WHAT THE PAGE COVERS (Knut, #182 5816794672): a measurement
        # removed, a list cleared, a file changed on disk and re-read. The
        # page is kept for each of them, so each is a difference between the
        # page and what Generate would now write.
        return bool(built is not None and (
            tuple(built) != self._doc_settings()
            or self._page_coverage_moved()))

    def _show_stale_banner(self) -> None:
        if getattr(self, "_stale_label", None) is None:
            return
        # **AND IT NEVER ASKS FOR A PRESS THAT CANNOT HAPPEN (B8-601).** The
        # line reads *"Settings changed. Click 'Generate report' to build the
        # report with them, or put the setting back."* With every measurement
        # unticked the settings HAVE changed, and Generate is disabled (B8-600,
        # because a press would write a measurement the user unticked), so the
        # line was telling a reader to press a button that refuses them. A
        # message is a promise; this one could not be kept.
        #
        # The second half of its own sentence is what is left, and it is the
        # honest instruction here: put the setting back. Ticking a measurement
        # brings the line, and the button, straight back.
        #
        # …EXCEPT WHEN THE PAGE HAS LOST WHAT IT WAS DRAWN FROM (Knut, #182
        # 5816794672): a measurement it covers removed, the list cleared, a
        # file changed on disk. The page is kept for those, so the line is
        # the only thing saying the report on screen is no longer the list's,
        # whatever is ticked.
        # K39-3: after "New report…" the line is up whatever the settings
        # are, until a report is drawn: the page is still the report shown
        # before it, and the reader is told to set up the new one and press
        # Generate report (Knut, #182 5831246553).
        self._stale_label.setVisible(
            bool(getattr(self, "_new_report_pending", False))
            or (self._settings_were_modified()
                and (not self._nothing_is_ticked()
                     or self._page_lost_what_it_covers())))
        self._word_the_stale_line()
        # **THE PDF DOOR STAYS OPEN, AND THE PDF IS WHAT IS ON SCREEN
        # (B8-364).** Round 21 measured the fault: with the pulldown on `Colour
        # summary (one page)`, the red line up and the document still reading
        # *Full colour check* over several pages, Save report as PDF wrote a
        # one-page `Colour summary` nobody had ever seen.
        #
        # Knut first ruled that the button should be greyed until Generate was
        # pressed, and that was built. He then changed it, 2026-09-18: *"I
        # realise that it is better that clicking the button always generates a
        # pdf from the currently loaded report text. If some settings are
        # changed, those are not applied before clicking Generate Report, and
        # making the PDF should be possible still, because the user can also
        # revert any changed settings. Thus the disabling of the Print Report
        # As PDF button is not needed, unless no report is loaded in the window
        # at all."*
        #
        # So the button follows the SOURCES, exactly as it did before, and the
        # fault is fixed at the other end instead: `_export_pdf` builds from
        # the settings the document on screen was built with rather than from
        # whatever the controls say now. That answers the original complaint
        # better than greying the button did, because the reader can still hand
        # somebody the document they are looking at while they think about a
        # setting they have moved.

    def _list_tick_box_qss(self) -> str:
        """**THE LIST'S TICK BOXES, DRAWN LIKE EVERY OTHER TICK BOX (challenge
        3 of beta 42, B8-1037).** The rows' boxes are item indicators, which
        no rule of the app's style sheet reaches (it styles ``QCheckBox``), so
        Fusion drew them from the palette: on the dark page an unticked box
        was a dark square on a dark ground, all but invisible. Here they take
        a clear edge on the appearance's own input ground, and a ticked box
        the window's green (ACTION in Neutral) with a tick in it, so it still
        reads on a selected row, which is green too."""
        from core.resource_path import resource_path
        from ui.theme import APPEARANCE_NEUTRAL, has_dark_ground, resolve_mode
        mode = resolve_mode(self._settings.get("appearance", "auto"))
        if mode == APPEARANCE_NEUTRAL:
            from ui.neutral_styles import NM_ACTION, NM_BG_INPUT, NM_BORDER_HI
            edge, ground, on, tick = (NM_BORDER_HI, NM_BG_INPUT, NM_ACTION,
                                      "list_tick_light")
        elif has_dark_ground(mode):
            # Brighter than the app's #4a4a4a check-box edge: the list's
            # ground is nearly black, and #4a4a4a is what "nearly invisible"
            # was made of.
            edge, ground, on, tick = ("#8a8a8a", BG_INPUT, SPEC_GREEN,
                                      "list_tick_dark")
        else:
            from ui.light_styles import LM_BG_INPUT, LM_BORDER_HI
            edge, ground, on, tick = (LM_BORDER_HI, LM_BG_INPUT, SPEC_GREEN,
                                      "list_tick_dark")
        img = str(resource_path(f"assets/{tick}.svg")).replace("\\", "/")
        return (
            " QListWidget::indicator { width: 14px; height: 14px;"
            f" border: 1px solid {edge}; border-radius: 3px;"
            f" background: {ground}; }}"
            " QListWidget::indicator:checked {"
            f" background: {on}; border-color: {on}; image: url({img}); }}")

    def _word_the_stale_line(self) -> None:
        """**THE RED LINE NEVER ASKS FOR A PRESS THAT CANNOT HAPPEN (challenge
        3 of beta 42, B8-1034).** With Generate greyed (mixed kinds ticked,
        a file outside a project…) it said *"Click 'Generate report'"* over a
        button that refuses the click. B8-601 hid the line for the one case
        of nothing ticked; every other greyed state kept the false sentence.
        Now it says what is true: the settings changed, and Generate waits for
        the reason printed directly above it (`_set_generate_why`)."""
        label = getattr(self, "_stale_label", None)
        if label is None:
            return
        gen = getattr(self, "_generate_btn", None)
        greyed = gen is not None and not gen.isEnabled()
        if getattr(self, "_new_report_pending", False):
            # K39-3: "New report…" was chosen over a report on the page.
            from workflow.measurement_messages import (
                M_REPORT_NEW_REPORT_SETTINGS)
            label.setText("⚠ " + M_REPORT_NEW_REPORT_SETTINGS.render()[1])
            return
        # Two literals, not a variable: the catalogue extractor cannot see
        # what a tr(variable) will be asked for.
        label.setText(
            tr("⚠ Settings changed. “Generate report” is unavailable until "
               "the reason shown above is resolved.") if greyed else
            tr("⚠ Settings changed. Click “Generate report” to build the "
               "report with them, or put the setting back."))

    def _refresh(self) -> None:
        """Repaint both the trend charts and the report body (they share the same
        run set, so both react to Show-all / thresholds / the profile list).

        Everything that is NOT one of the five settings above still repaints at
        once: opening a measurement, adding or removing one, the limits window
        writing a number. Those change what there IS to report on, and leaving
        the document showing a measurement that is no longer loaded would be a
        different kind of lie from the one this defers.
        """
        self._forget_limits()
        self._sync_limit_controls()
        self._refresh_trend()
        self._render()

    def _render(self) -> None:
        # THE DOCUMENT IS ABOUT TO MATCH THE CONTROLS, so this is the one place
        # that may record what it was built from. Anything that repaints goes
        # through here, so nothing else has to remember to clear the banner.
        #
        # **EXCEPT WHEN NOTHING IS TICKED, WHICH IS NOT A DOCUMENT (B8-601).**
        # A state that Generate refuses to write (B8-600) cannot be the state a
        # document "was built with", and stamping it made the red line lie in
        # the ordinary way round: press "Deselect all", change your mind, tick
        # the row back, and the baseline has moved to the empty list while the
        # ticks have come back exactly where the document was built. Measured
        # on three measurements, one ticked:
        #
        #     open    hidden 2   built 2   modified False
        #     Deselect all      hidden 3   built 3   modified False
        #     tick one back     hidden 2   built 3   modified True
        #
        # …so the window asks "Update or Create New?" about a document nobody
        # changed. That is the exact invariant the banner exists for, Knut's
        # *"a chance to undo a changed field, if not wanting to regenerate the
        # report"*, and undoing the change is what triggered it.
        #
        # Found by the adversary pass over B8-590, in this round's own work:
        # "Deselect all" is what makes the transient empty list easy to reach,
        # and it is a button this round added.
        #
        # **AND ONLY A DOOR THAT SHOWS A REPORT DRAWS (Knut, #182
        # 5816794672).** *"The report text should never automatically be
        # updated in any situation."* Inside `_keeping_the_page` (Remove
        # Profile's Measurements, Clear List, a file re-read because it
        # changed on disk, a Generate that wrote nothing) the page on screen
        # is left exactly as it is, nothing is stamped, and the red line is
        # asked again. Everything else that reaches here is Generate, a
        # report chosen in "Report shown", "New report…", a delete, or the
        # window's first page.
        if getattr(self, "_keep_page", 0) and self._page_shows_a_report():
            self._show_stale_banner()
            return
        # A REPORT IS DRAWN, so a "New report…" waiting for Generate is over
        # (K39-3): the red line is asked again from here.
        self._new_report_pending = False
        if not self._nothing_is_ticked():
            self._doc_built_with = self._doc_settings()
            self._page_covers = self._coverage_now()
            self._page_snapshot = self._snapshot_of_the_page()
        self._show_stale_banner()
        self._note_which_document_the_page_is()
        if not self._sources:
            self._view.setHtml(self._empty_html())
            self._remember_how_it_was_built()
            return
        self._view.setHtml(
            self._report_body_html(self._runs_for_report(), for_pdf=False))
        self._remember_how_it_was_built()

    @contextmanager
    def _keeping_the_page(self):
        """Inside this block nothing redraws the page or the graphs: the list,
        the buttons and the red line follow what changed, the report on
        screen does not (Knut, #182 5816794672)."""
        self._keep_page = getattr(self, "_keep_page", 0) + 1
        try:
            yield
        finally:
            self._keep_page -= 1

    def _page_shows_a_report(self) -> bool:
        """Is a report drawn on the page, from measurements (not the empty
        page)? What `_keeping_the_page` keeps, and what makes an add come in
        unticked even when the list itself was cleared."""
        snap = getattr(self, "_page_snapshot", None)
        return bool(snap and snap.get("sources"))

    def _coverage_now(self) -> tuple:
        """What a page drawn now would cover: each TICKED measurement with
        the disk stamp of the file it was read from. Compared with the page's
        own (`_page_covers`), so a removed measurement, a cleared list and a
        file that changed on disk are each a change the red line names."""
        hidden = getattr(self, "_hidden_runs", set()) or set()
        out = []
        for s in getattr(self, "_sources", None) or []:
            stamp = tuple(s.get("stamp") or ())
            for r in s.get("runs") or []:
                key = self._run_key(r)
                if key not in hidden:
                    out.append((repr(key), stamp))
        return tuple(sorted(out))

    def _page_lost_what_it_covers(self) -> bool:
        """Is a measurement the page covers gone from the list, or re-read
        from a file that changed? (Ticks alone never answer yes.)"""
        covers = getattr(self, "_page_covers", None)
        if not covers:
            return False
        listed = set()
        for s in getattr(self, "_sources", None) or []:
            stamp = tuple(s.get("stamp") or ())
            for r in s.get("runs") or []:
                listed.add((repr(self._run_key(r)), stamp))
        return any(c not in listed for c in covers)

    def _page_coverage_moved(self) -> bool:
        """Has what the page covers moved since it was drawn?"""
        covers = getattr(self, "_page_covers", None)
        return covers is not None and covers != self._coverage_now()

    def _snapshot_of_the_page(self) -> dict:
        """The measurements the page is drawn from, copied, so the PDF of a
        page `_keeping_the_page` kept is still that page (Knut, 2026-09-18:
        *"clicking the button always generates a pdf from the currently
        loaded report text"*)."""
        return {
            "sources": [dict(s, runs=list(s.get("runs") or []))
                        for s in (getattr(self, "_sources", None) or [])],
            "history": list(getattr(self, "_history", None) or []),
            "report": getattr(self, "_report", None),
            "ti3": getattr(self, "_ti3", None),
            "run_ctx": getattr(self, "_run_ctx", None),
            "project_dirs": set(getattr(self, "_project_dirs", None) or ()),
        }

    @contextmanager
    def _the_page_as_drawn(self):
        """The measurements the page on screen was drawn from, for the length
        of the block (a PDF of the page). A page whose list has not moved is
        its own snapshot, and nothing is swapped."""
        snap = getattr(self, "_page_snapshot", None)
        moved = bool(snap) and (
            self._page_coverage_moved()
            or [str(s.get("origin")) for s in snap["sources"]]
            != [str(s.get("origin")) for s in (self._sources or [])])
        if not moved:
            yield
            return
        names = ("_sources", "_history", "_report", "_ti3", "_run_ctx",
                 "_project_dirs")
        held = {n: getattr(self, n, None) for n in names}
        try:
            self._sources = [dict(s, runs=list(s["runs"]))
                             for s in snap["sources"]]
            self._history = list(snap["history"])
            self._report, self._ti3 = snap["report"], snap["ti3"]
            self._run_ctx = snap["run_ctx"]
            self._project_dirs = set(snap["project_dirs"])
            yield
        finally:
            for n, v in held.items():
                setattr(self, n, v)

    def _source_signature(self) -> tuple:
        """Which measurements are loaded, as a comparable value (round 2B)."""
        return tuple(sorted(str(src.get("origin") or "")
                            for src in (self._sources or [])))

    def _note_which_document_the_page_is(self) -> None:
        """Record, as the page is drawn, which saved document it shows.

        **ROUND A, 2026-09-22 (A-3, A-6).** The "Created:" line and the PDF's
        file name read `_doc_created`, which says which document is SELECTED,
        not which one the page is. With two runs loaded a type change repaints
        at once (there is no Generate to wait for), so the page stopped being
        the saved document and still printed its creation time, and Save as
        PDF offered that document's exact file name: saving would have
        overwritten another report's PDF. And after an Update the name did not
        move at all, so the updated content was offered the earlier PDF's
        name.

        So the page records what it is when it is drawn: the selected
        document's creation time and last update while that document still
        speaks for the controls, and nothing when it no longer does. The
        "Created:" line and `_report_filename` read this, so the screen, the
        PDF body and the PDF's name cannot disagree.
        """
        from workflow.measurement_report import document_updated_stamps
        key = str(getattr(self, "_loaded_doc_id", "") or "")
        # …AND NOT ONCE THE LIST OF MEASUREMENTS HAS CHANGED UNDER IT (round
        # 2B, #6): adding or removing a profile's measurements redraws the page
        # at once, so it is no longer the saved document, and it kept printing
        # that document's "Created:" time.
        speaks = (bool(key) and key != NEW_REPORT_KEY
                  and not getattr(self, "_doc_settings_moved", False)
                  and getattr(self, "_doc_sources", None)
                  in (None, self._source_signature()))
        self._page_doc_created = (str(getattr(self, "_doc_created", "") or "")
                                  if speaks else "")
        updated = ""
        if speaks:
            try:
                ctx = self._run_ctx
                entry = next((d for d in self._saved_documents(
                    ctx.run if ctx is not None else None)
                    if d["key"] == key), None)
                stamps = document_updated_stamps((entry or {}).get("doc"))
                updated = stamps[-1] if stamps else ""
            except Exception:      # noqa: BLE001 — a name is never a blocker
                log.debug("could not read the document's update stamps",
                          exc_info=True)
        self._page_doc_updated = updated

    def _remember_how_it_was_built(self) -> None:
        """The TYPE and the LIMITS the page was just drawn with (R23-F1).

        `_doc_built_with` remembers the five deferred settings as WIDGET
        values, and `_as_the_document_was_built` puts those widgets back for
        the length of a PDF build. Two of the five are not read from widgets at
        all: `_on_set_chosen` and `_on_type_chosen` write the chosen set and
        type onto the RUN the moment they are moved, and the body reads them
        back through `_report_type_now` and `_limits_for`. So with the red line
        up, an export took the run's NEW answers while the screen still showed
        the old ones: measured in round 23, the screen said *Judged against:
        ChromIQ default (recommended)* and the exported PDF said *ChromIQ
        tight*.

        This is the other half of the wrapper: what the body actually read,
        kept in memory, so the export can be given the same answers.
        **Nothing is written to the run to achieve it** — an export must not
        touch the disk, and a build that fails half way must not leave a run
        carrying a set the user never chose.

        Taken AFTER the body is composed, because composing it is what fills
        the two limit caches.
        """
        self._doc_built_state = (
            self._report_type_now(),
            dict(getattr(self, "_limits_cache", None) or {}),
            dict(getattr(self, "_limits_by_origin", None) or {}),
            self._limits,
        )
        # ...AND THE REPORT'S OWN LIMITS (K30), which are not a widget either.
        self._own_limits_as_built = getattr(self, "_report_own_limits", None)
        # **AND THE ROWS THE PAGE WAS DRAWN FROM, WITH THEIR VERDICTS
        # (challenge 5 of beta 42, M2, B8-1092).** The wrapper put the four
        # settings back and still the PDF re-judged: touching one control sets
        # `_doc_settings_moved`, which silences `_document_settings()`, and
        # `_judged_by_the_document` then judged every row live against today's
        # numbers instead of showing the words the saved report was drawn
        # with. Measured on a report saved before K37 (Border-Conditions run 1,
        # 2026-12-01): the page FAIL, FAIL, Overall FAIL; after ticking only
        # "Show detailed data" the PDF PASS, PASS, Overall PASS. So the rows
        # themselves are kept, exactly as the page judged them, and the PDF
        # prints those (`_runs_for_report` hands them back inside the
        # wrapper), together with whether the loaded document still spoke for
        # the controls when the page was drawn. The SAME objects, not copies:
        # `_is_judged_now` recognises a row judged live by its identity.
        try:
            self._runs_as_drawn = list(self._runs_for_report())
        except Exception:      # noqa: BLE001 — never a blocker for the page
            log.debug("could not keep the page's rows", exc_info=True)
            self._runs_as_drawn = None
        self._doc_moved_as_built = bool(
            getattr(self, "_doc_settings_moved", False))
        # Which saved report the page is (K39-3, `_as_the_document_was_built`).
        self._doc_as_built = (getattr(self, "_loaded_doc_id", ""),
                              getattr(self, "_loaded_doc", None),
                              getattr(self, "_doc_created", ""))

    def _refresh_trend(self) -> None:
        """Repaint the trend charts from the report's current run set."""
        # The graphs are part of the page: kept with it (Knut, #182
        # 5816794672; `_keeping_the_page`).
        if getattr(self, "_keep_page", 0) and self._page_shows_a_report():
            return
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
        # K26: the figures each date's verdict judged, within gamut where the
        # sheet was split by the profile's gamut (`report_trend`). Since K31
        # the NAME says so too ("… within gamut", `compliance_sets.row_name`),
        # and the graph's description still says what the population is
        # (`_TREND_ABOUT_DE_JUDGED`).
        #
        # **A "–" LIMIT TAKES THE LINE OFF THE GRAPH (K28, item 3).** Knut:
        # a limit set to "–" removes the row from the results, the guide, the
        # detailed data, the Overview *"and the graph"*.
        dash = self._dash_row_ids(self._document_runs_for_graphs())
        # K31 (Knut, #182 5801677743): on a document holding a split sheet
        # the legend names the judged figures "within gamut", as Report
        # Results does, so one name never means two populations.
        _names_runs = self._document_runs_for_graphs()
        corner_metrics = [
            # K25: the unit on every data label, as Colour accuracy's carry.
            (_with_unit(_CORNER_LABELS[code](), "ΔE00"),
             QColor(_CORNER_LINE[code]),
             (lambda pt, c=code: (pt.get("corners") or {}).get(c)))
            for code in ("W", "K", "R", "G", "B", "C", "M", "Y")
        ]
        return [
            (self._trend_de, tr("Colour accuracy (ΔE00)"), [
                (_with_unit(self._row_name(_ROW_ID_OF[k], _names_runs),
                            "ΔE00"),
                 QColor(_METRIC_LINE[k]),
                 (lambda pt, kk=k: _accuracy_value(pt, kk)))
                for k in _ACCURACY_ROW_KEYS if _ROW_ID_OF[k] not in dash
            ], None, 1, False),
            # White (~L*100) and black (~L*10) are too far apart to share an axis
            # (Knut), so each is its own auto-scaled chart — and the axis ranges
            # tightly around the values (not from 0) so a small drift is visible.
            (self._trend_white, tr("Paper white (L*)"), [
                (tr("Paper white L*"), QColor("#8a8a8a"), lambda pt: pt.get("white_L")),
            ], None, 1, True),
            (self._trend_black, tr("Darkest black (L*)"), [
                # K31: one name for the tab, the legend and the Overview.
                (tr("Darkest black L*"), QColor("#505050"),
                 lambda pt: pt.get("black_L")),
            ], None, 1, True),
            (self._trend_corners, tr("Cube corners (ΔE00)"),
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
        folder next to the file itself.

        AND "WHAT THE REPORT SHOWS" IS NOW NARROWER THAN "WHAT IS LOADED" IN A
        SECOND WAY (B8-246): a document is written against one limit set, so
        this asks `_runs_for_document`, the same list the body and the Generate
        button ask. It asked `_runs_for_report`, and the first minute of the
        challenge round after that fix found what that cost: a report
        describing ONE run of a seven-run project offered to save itself into
        the whole project's `reports/` folder, because the common ancestor of
        seven runs is the `runs` container. The sentence above already said
        this must follow the report; the list it asked had stopped being it.
        """
        from core.file_manager import reports_subdir
        dirs = [Path(r["_origin_dir"])
                for r in self._runs_for_document() if r.get("_origin_dir")]
        # **SEVERAL PROJECTS: WHERE THE DOCUMENT LIVES (K9, K30).** The
        # common ancestor of two projects that are not side by side is some
        # folder nobody chose (the home folder); the report itself lives in
        # the ChromIQ folder's reports/ then (`document_home`), and the PDF
        # goes where the report is.
        from workflow.measurement_report import (_project_folder_of,
                                                 document_home)
        projects = {str(_project_folder_of(d)) for d in dirs}
        if len(projects) > 1 and "None" not in projects:
            home = document_home(dirs)
            if home is not None:
                return home
        lca = self._lca_dir(dirs) if dirs else self._anchor_dir()
        # The common ancestor being the ``runs`` container itself means the
        # report spans multiple runs → it belongs to the whole profile.
        if lca.name == "runs":
            return reports_subdir(lca.parent)
        return reports_subdir(lca)

    def _reports_to_generate(self) -> list:
        """THE MEASUREMENTS A PRESS OF GENERATE COVERS: the ticked ones, one
        row per measurement (K31).

        **FROM ANY WINDOW (Knut, #182 5801677743).** Asked *"With a report
        selected, may GENERATE REPORT > Update rewrite that report where it
        lives, whichever profile run the window was opened from?"* and
        *"With 'Create New', or 'New report...', and only another run's dates
        ticked, may the new report be saved where those dates decide?"*, he
        answered *"Agreed."* to both. This used to keep only the window's own
        run's rows, because the report type and the limit set belonged to the
        run and a file written from here was stamped with THIS run's; since
        K.8, K30 and K31 both belong to the report, so that reason is gone and
        so is the filter. Where the report is saved is `document_home`'s
        answer from what is ticked, whatever window pressed the button.

        ONE ROW PER MEASUREMENT, NOT ONE PER REPORT ALREADY SAVED OF IT. The
        count doubled on every press when each saved report came back as a
        history entry and was written again. Inside a folder the history can
        hold MANY measurements (measuring again archives the previous `.ti3`
        and reuses its name), and only one of them is the run's measurement
        today, so the row the window is ON wins, and where the window is on
        neither, the later measurement does.

        What still refuses (empty list): nothing ticked (B8-600), a report
        across places with a measurement outside every project, and under
        Calibration a measurement that is not a project's calibration (a
        calibration report covers calibrations only, K30 F4).
        """
        # NOTHING TICKED, NOTHING TO WRITE (B8-600). See `_nothing_is_ticked`:
        # `_runs_for_report`'s fallback keeps the page readable and must not
        # decide what a press of Generate puts on disk.
        if self._nothing_is_ticked():
            return []
        runs = self._runs_for_document()
        from workflow.measurement_report import (across_places_refusal,
                                                 is_calibration_dir)
        dirs = [str(r.get("_origin_dir") or "") for r in runs]
        if self._spans_places(runs) and across_places_refusal(dirs):
            return []
        if self._is_calibration_window() and not all(
                is_calibration_dir(d) for d in dirs if d):
            return []
        subject = self._run_key(self._report) if self._report else None
        out: list = []
        seen: "dict[tuple, int]" = {}
        for r in runs:
            origin = str(r.get("_origin_dir") or "")
            if not origin:
                continue
            key = (origin, Path(str(r.get("ti3") or "")).name)
            at = seen.get(key)
            if at is None:
                seen[key] = len(out)
                out.append(r)
                continue
            kept = out[at]
            if subject is not None and self._run_key(kept) == subject:
                continue                       # the window's own row stays
            if (subject is not None and self._run_key(r) == subject) or \
                    str(r.get("created") or "") > str(kept.get("created") or ""):
                out[at] = r
        return out

    def _document_scope(self, members: list) -> str:
        """Which of Knut's three date flags this press earns (B8-392).

        > *"If 'Show all measurement runs' is ON and all measurement dates are
        > marked to be included, then the name should include the flag 'All
        > dates'. … only one is marked to be included … 'One date'. … more
        > than one are marked to be included (but is not all …) … 'Multiple
        > dates'. If the list of measurement dates to be included only holds
        > one measurement … the report name should include the flag 'One
        > date'."*

        Decided from what the document really covers, not from the tick box
        alone, so the flag cannot disagree with the page: one measurement is
        "One date" whatever the box says, everything with nothing left out is
        "All dates", and anything between them is "Multiple dates".

        **HIS THIRD CASE IS NOT REACHABLE FROM THIS WINDOW TODAY**, and it is
        reported rather than built around: with "Show all measurement runs"
        OFF, `_runs_for_report` returns the ONE measurement the window is on
        and the row ticks are not consulted, so "OFF with several ticked"
        cannot produce a document of several. The flag is computed from the
        member list, so if that behaviour ever changes this says the right
        word without being touched.

        **AND IT IS COMPUTED FROM THE MEMBERS ALONE NOW (B8-522).** It asked
        the tick box and `_hidden_runs` for "all of them", which are two
        answers to a question the member list already answers, and they
        disagreed with it in both directions. Knut, beta 26, on a document of
        ten of eleven measurements named *"All dates"*: *"This is wrong."* And
        on a one-page summary of one measurement named *"One date"* after he
        had ticked all eleven -- the same disagreement the other way up, with
        the flag right and the ticks wrong (see `_draw_the_row_ticks`).

        "All dates" now means exactly what it says: every dated measurement in
        the list is in the document. Because it is derived from what the
        document COVERS, an Update that changes the membership changes the
        flag with it, which is the other half of his sentence: *"The 'One date'
        tag also needs to be updated if I update the report to contain other
        measurements included."*
        """
        from workflow.measurement_report import (SCOPE_ALL_DATES,
                                                 SCOPE_MULTIPLE_DATES,
                                                 SCOPE_ONE_DATE)
        if len(members) <= 1:
            return SCOPE_ONE_DATE
        here = {self._run_key(r) for r in self._history}
        covered = {str(m.get("key") or "") for m in members}
        if here and here <= covered:
            return SCOPE_ALL_DATES
        return SCOPE_MULTIPLE_DATES

    def _on_generate_report(self) -> None:
        """One press of Generate report (`_generate_once`), with each
        measurement worked out again from disk AT MOST ONCE (K39-2): the
        question after the press compares that working with the page, and
        the write that follows uses the same rows (`_worked_out_again`)."""
        self._press_cache = {}
        try:
            self._generate_once()
        finally:
            self._press_cache = None

    def _generate_once(self) -> None:
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
        reports = self._reports_to_generate()
        # A CALIBRATION HAS NO RUN AND IS WRITTEN (#182 beta 39); under Run
        # type Calibration nothing else is (the button says why).
        if self._is_calibration_window():
            if self._own_cal_dir() is None:
                return
        elif ctx is None:
            return
        if not reports:
            return
        # The button is disabled with a reason when both kinds are loaded
        # (FC-2); the handler refuses as well, so no other door writes one
        # type into both kinds of folder.
        if self._kinds_are_mixed():
            log.info("Generate refused: a profiling sheet and dated "
                     "verifications are loaded together")
            return
        # K36-1: an ISO type with a set that is not one of the four ISO sets
        # is a saved report's pair, never a new one (the button says why).
        if self._type_refuses_the_set():
            log.info("Generate refused: %s is not judged against %s",
                     self._report_type_now(), self._report_limits().set_id)
            return
        # MEASUREMENTS FROM MORE THAN ONE PLACE ARE NO LONGER REFUSED (#182
        # beta 39, G7). The refusal stood here because a report across runs
        # could only be written as one run's (A-F1, before beta 37); it is
        # now written as a document across places, judged against its own
        # limit set, and `_reports_to_generate` answers empty for the cases
        # that still cannot be written, which returned above.
        # **IT SAYS SO INSTEAD OF CORRECTING THE TICKS (B8-591).** Knut,
        # 2026-09-20, reporting the same silence from both ends: *"This
        # unselected all but the last measurement without a warning"* and *"the
        # measurement I had ticked was unticked and the last measurement in the
        # list was automatically ticked (I did not ask for that)"*. His rule for
        # what replaces it: *"the user should be informed … Then the user can
        # close that message and do the changes, and then click generate report
        # again."* So the press STOPS; nothing is written and no tick is moved.
        if self._one_page_wants_one_measurement():
            return
        # **AND IT MAY UPDATE THE SELECTED REPORT INSTEAD (B8-491).** Knut,
        # 2026-09-19, overruling his own K.1: *"When a report from 'Report
        # shown' is selected … If any of the settings are changed, a red text
        # message will show user that he must click Generate Report to apply
        # settings. When Generate Report is then clicked, the user must be
        # shown a popup message … The window must then have three buttons:
        # Update, Create New and Cancel. … This feature overrules a previous
        # ruling that Generate Report always should create a new report."*
        updating = self._document_being_updated()
        loaded = str(getattr(self, "_loaded_doc_id", "") or "")
        if updating is None and loaded and loaded != NEW_REPORT_KEY:
            # **A LOADED REPORT THE LIST NO LONGER HOLDS IS NEVER WRITTEN AS
            # A NEW ONE WITHOUT THE QUESTION (GAP 0, K4).** The window first
            # takes what "Report shown" names (`_load_what_the_list_names`),
            # and the press then acts on THAT: asked about if it is a
            # report, written new only if the list is on "New report…".
            log.warning("Generate found the loaded report %s missing from "
                        "the list; loading what the list shows", loaded)
            self._load_what_the_list_names(force=True)
            updating = self._document_being_updated()
            reports = self._reports_to_generate()
            if not reports:
                return
        if updating is not None:
            answer = self._ask_update_or_create_new()
            if answer == "cancel":
                return                      # *"Cancel aborts the Generate
                                            # Report function."*
            if answer != "update":
                updating = None             # *"'Create New' … will perform the
                                            # same function as if 'New report…'
                                            # option is selected."*
        # AN UPDATE NEVER DROPS A MEASUREMENT IT CANNOT FIND IN SILENCE
        # (challenge C, beta 39, #1 and #11): `_update_leaves_out`.
        leave_out: "set[str]" = set()
        if updating is not None:
            leave_out = self._update_leaves_out(updating)
            if leave_out is None:
                return
        self._write_the_document(ctx, reports, updating, leave_out=leave_out)

    def _update_leaves_out(self, updating: dict) -> "set[str] | None":
        """What an Update of *updating* may leave out: the identities of the
        measurements the user agreed to drop, an empty set when nothing is
        lost, None when the press stops (refused, or the user cancelled).

        The rule is `workflow.measurement_report.update_losses`; the words
        are M-REPORT-UPDATE-NOT-FOUND (a covered measurement no side can
        find: refused) and M-REPORT-UPDATE-LEAVES-OUT (measurements no longer
        on disk: asked, Cancel the default)."""
        from ui.warning_sign import inform
        from workflow import measurement_messages as M
        from workflow.measurement_report import (GONE_PROJECT,
                                                 document_measurement_key,
                                                 update_losses,
                                                 update_may_cover)
        recorded = [m for m in ((updating.get("doc") or {}).get("measurements")
                                or []) if isinstance(m, dict)]
        pressed = [{"dir": str(r.get("_origin_dir") or ""),
                    "created": str(r.get("created") or ""),
                    "ti3": str(r.get("ti3") or ""),
                    "key": document_measurement_key(
                        r.get("_origin_dir") or "", str(r.get("created") or ""),
                        str(r.get("ti3") or ""))}
                   for r in self._runs_for_document() if r.get("_origin_dir")]
        # **AN UPDATE COVERS THE REPORT'S OWN KIND OF MEASUREMENT (second
        # check R3, beta 39, B8-925).** With every verification of a report
        # gone, the window held the run's profiling sheets, this counted
        # them as what was "still there", and "Update without them" rewrote
        # the verification report about sheets it had never covered. What
        # the report cannot cover by its kind is never written into it, and
        # the NOTHING-LEFT / LEAVES-OUT decision is made on the rest.
        members = update_may_cover(recorded, pressed)
        foreign = {str(m["key"]) for m in pressed if m not in members}
        if foreign:
            log.info("an Update of %s leaves out %d measurement(s) of "
                     "another kind than the report's", updating.get("key"),
                     len(foreign))
        losses = update_losses(recorded, members,
                               self._entry_homes(updating))
        if not losses:
            return foreign
        missing = "\n".join(M.report_gone_line(e) for e in losses)
        for e in losses:
            log.info("the report covers %s (%s), which is not there: %s",
                     e.get("dir"), e.get("created"), e.get("reason"))
        if any(e.get("reason") == GONE_PROJECT for e in losses):
            inform(self, *M.CATALOGUE["M-REPORT-UPDATE-NOT-FOUND"].render(
                missing=missing))
            return None
        lost = {str(e["key"]) for e in losses if e.get("key")}
        # **A REPORT OF NOTHING IS NEVER WRITTEN (re-challenge R1, beta 39,
        # #4).** "Update without them" on a report whose EVERY measurement
        # was gone wrote ``measurements: []`` under its old verdict and its
        # old scope, and the list and the page went on showing it as the
        # report it had been. Nothing would be left, so there is nothing to
        # ask: the press is refused, and the window names Delete.
        if not [m for m in members if str(m.get("key") or "") not in lost]:
            inform(self, *M.CATALOGUE["M-REPORT-UPDATE-NOTHING-LEFT"].render(
                missing=missing))
            return None
        title, body = M.CATALOGUE["M-REPORT-UPDATE-LEAVES-OUT"].render(
            missing=missing)
        if not self._ask_leave_out(title, body):
            return None
        return lost | foreign

    def _update_would_orphan_a_date(self, updating: dict,
                                    members: list) -> bool:
        """Would updating *updating* to cover *members* take away the only
        own report of a date (B40-A 3, §25.7)?

        True when the report is a date's own report of one date, the Update
        widens it to more than one measurement folder, and that date holds
        no other own report of one date (`_is_own_one_date_report`; a
        verdict record or a pre-K23 copy is none). A report of several
        dates already, or one that stays on its date, is never affected."""
        import json
        if updating.get("file"):
            return False                     # a document file, not a date's
        if len({str(m.get("dir") or "") for m in members}) < 2:
            return False                     # not widened to several dates
        for r, name in (updating.get("members") or []):
            folder = Path(str(r.get("_origin_dir") or "")) / "reports"
            try:
                this = json.loads(read_text(folder / name))
            except Exception:                # noqa: BLE001
                continue
            if not self._is_own_one_date_report(this):
                continue
            spare = False
            for p in folder.glob("report_*.json"):
                if p.name == name:
                    continue
                try:
                    spare = self._is_own_one_date_report(
                        json.loads(read_text(p)))
                except Exception:            # noqa: BLE001
                    spare = False
                if spare:
                    break
            if not spare:
                return True
        return False

    def _ask_leave_out(self, title: str, body: str) -> bool:
        """M-REPORT-UPDATE-LEAVES-OUT's two buttons; True for "Update without
        them". Kept on the instance while it is up, so a driver can
        photograph it and press a real button."""
        from PyQt6.QtWidgets import QMessageBox
        from ui.widgets import fit_message_box_buttons
        from ui.warning_sign import set_question_icon
        box = QMessageBox(self)
        set_question_icon(box)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        go = box.addButton(tr("Update without them"),
                           QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        fit_message_box_buttons(box)
        self._leave_out_box = box
        try:
            box.exec()
            return box.clickedButton() is go
        finally:
            self._leave_out_box = None

    def _one_page_wants_one_measurement(self) -> bool:
        """True when the press was refused and the user was told why (B8-591).

        The one-page colour summary is a page about a single measurement, and
        it always was: `_one_page_html` renders one sheet. What changed is what
        happens when more than one is ticked. It used to narrow the list in
        `_runs_for_document` and write a document of one, which is what
        produced a report named "One date" out of eleven ticked rows, and a
        report about a measurement the user had not chosen.
        """
        from workflow.measurement_report import REPORT_TYPE_SUMMARY
        if self._report_type_now() != REPORT_TYPE_SUMMARY:
            return False
        # **IT COUNTS THE TICKS, NOT THE FILES THE PRESS WOULD WRITE.** The
        # first cut of this asked `_reports_to_generate`, which is already
        # narrowed: with eleven measurements ticked it answered ONE, so the
        # question "are several ticked?" was being put to a list that had
        # stopped being the ticks. Measured on screen, eleven ticked:
        # `_runs_for_report` 11, `_reports_to_generate` 1. `_runs_for_report`
        # IS the ticked set since B8-590, and it is what the user sees.
        ticked = self._runs_for_report()
        if len(ticked) <= 1:
            return False
        from ui.warning_sign import inform
        from workflow import measurement_messages as M
        title, body = M.CATALOGUE["M-REPORT-ONE-PAGE-ONE-DATE"].render(
            count=len(ticked))
        inform(self, title, body)
        return True

    def _document_being_updated(self) -> "dict | None":
        """The selected document Generate report would ask about, or None.

        Both halves of Knut's sentence have to hold, and neither is enough on
        its own:

        * **a report from "Report shown" is selected** — "New report…" is not a
          report, and a window that has generated nothing has none to update;
        * **its settings have been changed** — which is exactly the state the
          red line names, read through the one predicate that decides it, so
          the line and the question cannot disagree.

        **AND WITH NOTHING CHANGED, IT ASKS TOO (K4, Knut on beta 34).** The
        second half used to be a condition: nothing moved, so Generate wrote a
        new report and asked nothing. Knut, wanting an old report's text
        refreshed, pressed it on a selected report and got a new one instead;
        his log shows four presses in nine seconds and 44 files, because the
        silent success looked like nothing had happened. So a selected report
        is always asked about, and the question says truthfully whether
        anything was changed (`_ask_update_or_create_new` works that out).

        With "New report…" selected, Generate writes a new report and asks
        nothing, as it always has.
        """
        key = str(getattr(self, "_loaded_doc_id", "") or "")
        if not key or key == NEW_REPORT_KEY:
            return None
        ctx = self._run_ctx
        docs = self._saved_documents(ctx.run if ctx is not None else None)
        return next((d for d in docs if d["key"] == key), None)

    def _differs_from_the_saved_report(self) -> bool:
        """Do the report's settings on screen differ from the SELECTED saved
        report's own limit set or type?

        **ASKED OF THE FILE, NOT OF THE PAGE (challenge 2 of beta 42, #1b).**
        `_settings_were_modified` compares the controls with the page, and a
        page redrawn without Generate had taken the new set as its own: the
        question then said *"Nothing was changed for the selected report"*
        and Update rewrote a report judged against ChromIQ default as
        ChromIQ tight. The page is no longer redrawn that way (Knut, #182
        5816794672), and this is the second lock on the same door: whatever
        the page says, a set, a type or a detail box that is not the saved
        report's own is a change.
        """
        doc = getattr(self, "_loaded_doc", None)
        key = str(getattr(self, "_loaded_doc_id", "") or "")
        if not isinstance(doc, dict) or not key or key == NEW_REPORT_KEY:
            return False

        def _data(name: str) -> str:
            combo = getattr(self, name, None)
            try:
                return str(combo.currentData() or "") if combo else ""
            except RuntimeError:
                return ""
        comp = doc.get("compliance") or {}
        saved_set = str(comp.get("set_id") or "")
        if saved_set and _data("_set_combo") and saved_set != _data("_set_combo"):
            return True
        saved_type = str(doc.get("type") or "")
        if saved_type and _data("_type_combo") \
                and saved_type != _data("_type_combo"):
            return True
        return False

    def _ask_update_or_create_new(self) -> str:
        """Knut's three-button question: ``"update"``, ``"new"`` or ``"cancel"``.

        The words are M-REPORT-UPDATE-OR-NEW, **proposed and not approved**:
        he wrote them himself and ended *"(or similar)"*, and §M is still where
        a message goes before it is written into a window.

        ONE METHOD, so a driver can answer it and so the window has one place
        that knows the three answers. The box is kept on the instance while it
        is up (`_update_or_new_box`) so a driver can photograph the real
        window and press a real button, which is the only way of proving what
        a reader sees.
        """
        from PyQt6.QtWidgets import QMessageBox
        from ui.widgets import fit_message_box_buttons
        from ui.warning_sign import set_question_icon
        from workflow import measurement_messages as M
        # THE HEADLINE IS A STATEMENT OF FACT, so the unchanged case has its
        # own (K4): "Settings were modified" over a report nobody touched is
        # false, and the buttons are the same three either way. Worked out
        # here, not passed in, so every existing answerer of this one method
        # keeps working.
        # A recorded type the kind no longer allows is a change the press
        # WILL make (round 2B, #8), so the headline may not say nothing
        # changed over it.
        # ROUND 3A (R3A-4): adding a measurement repaints and re-baselines
        # the ticks, so `_settings_were_modified` saw nothing, and the box said
        # "Nothing was changed" over a page that had stopped being the saved
        # document (its "Created:" line already said so). The list of loaded
        # measurements is the same test the page uses (`_doc_sources`).
        sources_moved = (getattr(self, "_doc_sources", None)
                         not in (None, self._source_signature()))
        modified = (self._settings_were_modified()
                    or sources_moved
                    or self._differs_from_the_saved_report()
                    or self._fit_to_kind(self._report_type_now())
                    != self._report_type_now())
        # **K39-2 (Knut, #182 5831246553, "Yes"): NOTHING CHANGED, AND STILL
        # AN UPDATE WOULD CHANGE THE REPORT.** On a report an earlier version
        # worked out (B8-1091), "Nothing was changed for the selected report"
        # was followed by an Update that turned FAIL into PASS. So the window
        # asks the question the press will answer: the rows this version
        # works out from disk, judged against the report's own set, compared
        # with the rows on the page (`_update_would_change_the_report`).
        if modified:
            mid = "M-REPORT-UPDATE-OR-NEW"
        elif self._update_would_change_the_report():
            mid = "M-REPORT-WORKED-OUT-DIFFERENTLY-UPDATE-OR-NEW"
        else:
            mid = "M-REPORT-UNCHANGED-UPDATE-OR-NEW"
        self._update_or_new_asked = mid
        title, body = M.CATALOGUE[mid].render()
        box = QMessageBox(self)
        set_question_icon(box)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        # K32 (Knut, #182 5813851807): "Move Create New button to be the
        # first button on the left and Update button to be the middle button
        # ... The Create New button should be default selected, so that an
        # enter would Create New by default (Safest)." Both are AcceptRole, and
        # a QDialogButtonBox lays the FIRST accept button out first and the
        # rest after it in the order they were added (Qt's AlternateRole
        # slot), so the order of these two lines IS the order on screen, on
        # every platform: `WinButtonLayoutStyle` pins the Windows layout, with
        # the reject button last. Nothing is lost by pressing Enter: a new
        # report leaves the selected one as it was.
        new = box.addButton(tr("Create New"), QMessageBox.ButtonRole.AcceptRole)
        upd = box.addButton(tr("Update"), QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(new)
        box.setEscapeButton(cancel)
        fit_message_box_buttons(box)
        self._update_or_new_box = box
        try:
            box.exec()
            clicked = box.clickedButton()
        finally:
            self._update_or_new_box = None
        # NOT `exec() == …`: exec returns an int and a PyQt6 enum member never
        # equals one, which is the trap `_confirm` records.
        if clicked is upd:
            return "update"
        if clicked is new:
            return "new"
        return "cancel"

    @staticmethod
    def _results_signature(rows: list, overall) -> tuple:
        """What a reader of the results reads off *rows*: each row's name,
        its word and its number as printed (two decimals), and the overall
        word. Two workings with one signature print the same results."""
        out = []
        for x in rows or []:
            v = x.get("value")
            try:
                v = round(float(v), 2) if v is not None else None
            except (TypeError, ValueError):
                v = str(v)
            out.append((str(x.get("row_id") or x.get("key") or ""),
                        str(x.get("word") or ""), v))
        return (tuple(sorted(out)), str(overall or ""))

    def _update_would_change_the_report(self) -> bool:
        """Would an Update of the selected report, with nothing changed,
        print other results than the page shows (K39-2)?

        ASKED OF THE PRESS ITSELF, not guessed: each measurement the Update
        would write is worked out again from disk exactly as the write does
        (`_worked_out_again`, cached for the press), judged against the
        report's own limits (`stamp_verdict`), and its rows, words and
        numbers compared with the rows the page was drawn from
        (`_runs_as_drawn`). A change in how the rows are explained counts
        too: that is B8-1091's test (`_worked_out_differently`), which is
        also what puts M-REPORT-WORKED-OUT-EARLIER on the page. False when
        nothing can be compared (never a reason to refuse the press)."""
        from workflow.measurement_report import stamp_verdict
        try:
            lim = self._report_limits()
            drawn_rows = getattr(self, "_runs_as_drawn", None)
            if drawn_rows is None:
                drawn_rows = self._runs_for_report()
            drawn = {self._run_key(r): r for r in drawn_rows
                     if isinstance(r, dict)}
            for r in self._runs_for_document():
                if not isinstance(r, dict):
                    continue
                page = drawn.get(self._run_key(r), r)
                if page.get(WORKED_OUT_EARLIER_KEY):
                    return True
                new = self._worked_out_again(r)
                if new is r:
                    continue            # nothing on disk to work it out from
                rep = dict(new)
                stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                              set_label=lim.label_en, edited=lim.edited)
                if _worked_out_differently(
                        {k: v for k, v in page.items() if k != RECORD_KEY},
                        rep):
                    return True
                was = self._results_signature(
                    self._verdict_rows(page)[0],
                    (page.get("verdict") or {}).get("overall"))
                now = self._results_signature(
                    self._verdict_rows(rep)[0],
                    (rep.get("verdict") or {}).get("overall"))
                if was != now:
                    return True
        except Exception:                              # noqa: BLE001
            log.debug("could not compare the Update with the page",
                      exc_info=True)
            return False
        return False

    def _write_the_document(self, ctx, reports: list,
                            updating: "dict | None" = None, *,
                            leave_out: "set[str] | None" = None) -> None:
        """Write the page in front of the user as a saved report.

        **ONE FUNCTION FOR BOTH BUTTONS**, which is Knut's own sentence: *"The
        same function is used as when 'New report…' option is selected then
        Generate Report clicked, but is instead updating the selected
        report."* With *updating* None this is Generate report exactly as it
        was; with a document entry it keeps that document's id and its creation
        stamp, rewrites it where it lives, and records the press as an update.

        **K31: A REPORT IS THE ONLY THING THERE IS (Knut, #182 5801677743).**
        Asked *"Should a report of several measurements stop writing verdict
        records altogether?"*, he answered *"Agreed."*, and of the dates'
        folders, *"When a report covers more than one run or project, should
        GENERATE REPORT write anything into the dates' own folders? Answer:
        no."* So one press writes ONE file, in the folder its ticked
        measurements decide (`document_home`):

        * **one measurement**: that measurement's report, in its own
          `reports/` folder, as ever (the report ChromIQ writes after a
          measurement is exactly this);
        * **several measurements**: a document file in the shared folder,
          whose list of measurements carries each one's verdict against the
          report's own limit set (`JUDGED_KEY`). Nothing is written into any
          measurement's folder.

        **AND ONE LIMIT SET FOR THE WHOLE REPORT, ALWAYS (G7 Q2, option a):**
        every measurement is judged against the report's set, whichever run
        it is in.

        What an Update leaves behind is ARCHIVED, never deleted (D23): the
        files it rewrites and the ones it retires are copied into their
        folder's `old/<stamp>/` first. It retires the files of this report
        that the new shape no longer has: the one-date file of a report of
        one date widened to more dates (Knut: *"that is the logical thing, if
        a user chooses to update the automatically created reports of one
        date"*), and a document file that moves or narrows to one date. The
        verdict records an earlier ChromIQ wrote (K23) are never touched, this
        report's or any other's: they are read-only history (section 25).
        """
        from datetime import datetime as _dt
        from workflow.measurement_report import (JUDGED_KEY, document_file,
                                                 document_home,
                                                 document_measurement_key,
                                                 document_updated_stamps,
                                                 judged_block,
                                                 new_document_id, report_type,
                                                 rewrite_report,
                                                 save_report, set_report_type,
                                                 stamp_document,
                                                 stamp_verdict)
        # WHAT THE WINDOW IS SHOWING: the report's own limits (K31). Anything
        # else would file a report against numbers the reader never saw.
        lim = self._report_limits()
        when = _dt.now()
        now_iso = when.isoformat(timespec="seconds")
        # WHAT THE USER AGREED TO LEAVE OUT (`_update_leaves_out`): gone from
        # the disk, so gone from what this press covers and writes.
        leave_out = set(leave_out or ())
        if leave_out:
            reports = [r for r in reports
                       if self._run_key(r) not in leave_out]
        # **AN UPDATE KEEPS THE DOCUMENT'S OWN id AND ITS OWN created**, which
        # is the whole of *"keep the current selected report"*. A report
        # written before the document record existed has neither, and it is
        # still the report the user selected: it is given an id, and its
        # creation stamp is the one its NAME already shows.
        doc = (updating or {}).get("doc") if updating else None
        doc_id = str((doc or {}).get("id") or "") or new_document_id(when)
        doc_created = now_iso
        updated: "list[str]" = []
        #: {measurement -> the file of this report in that measurement's
        #: folder}: its one-date file. An Update rewrites the one it keeps
        #: and archives, then retires, the rest. **A VERDICT RECORD AN
        #: EARLIER CHROMIQ WROTE (K23) IS NOT ONE OF THEM**: records are
        #: read-only history since K31, never rewritten, moved or deleted by
        #: anything (section 25 of the spec), and the updated report carries
        #: every verdict itself.
        from workflow.measurement_report import is_verdict_record
        existing: "dict[str, Path]" = {}
        if updating is not None:
            doc_created = (str((doc or {}).get("created") or "")
                           or self._document_created_stamp(updating) or now_iso)
            updated = document_updated_stamps(doc) + [now_iso]
            existing = {
                self._run_key(r): Path(str(r.get("_origin_dir") or "")) /
                "reports" / name
                for r, name in (updating.get("members") or [])
                if not is_verdict_record(self._document_of(
                    str(r.get("_origin_dir") or ""), name, r))}
        # **WHAT THE DOCUMENT COVERS**: the ticked measurements (R.3).
        members = [{"dir": str(r.get("_origin_dir") or ""),
                    "created": str(r.get("created") or ""),
                    "ti3": str(r.get("ti3") or ""),
                    "key": document_measurement_key(
                        r.get("_origin_dir") or "", str(r.get("created") or ""),
                        str(r.get("ti3") or ""))}
                   for r in self._runs_for_document() if r.get("_origin_dir")
                   and self._run_key(r) not in leave_out]
        # THE SAME RULE AT THE DOOR THAT WRITES (R1 #4): an Update that would
        # cover nothing writes nothing, whichever way it got here.
        if updating is not None and not members:
            from ui.warning_sign import inform
            from workflow import measurement_messages as M
            log.warning("an Update of %s would cover no measurement; refused",
                        doc_id)
            inform(self, *M.CATALOGUE["M-REPORT-UPDATE-NOTHING-LEFT"].render(
                missing=""))
            return
        # **A DATE'S ONLY REPORT IS NOT WIDENED AWAY (B40-A 3, §25.7; Knut,
        # #182 5806297940: "go for (a) Keep the date's own report").** Widening a report of one date to several
        # dates (§25.2) archives its one-date file; when that file is the
        # date's ONLY own report, the date is left with none, which is what
        # Delete refuses (§25.6). So such an Update leaves the
        # one-date report where it is, untouched, and writes the widened
        # report as a NEW report of those dates: what Create New does. No
        # message is added; the new report is what the list then shows.
        if updating is not None and self._update_would_orphan_a_date(
                updating, members):
            log.info("the Update of %s would leave a date with no report of "
                     "its own; the one-date report is kept and the report "
                     "of %d dates is written as a new one (§25.7)",
                     doc_id, len(members))
            updating = None
            doc = None
            doc_id = new_document_id(when)
            doc_created = now_iso
            updated = []
            existing = {}
        detail = self._tick_state()
        scope = self._document_scope(members)
        # **AN UPDATE THAT COVERS THE SAME MEASUREMENTS KEEPS ITS NAME'S
        # SCOPE (challenge C, C10)**; only a change of membership moves it
        # (§24.2).
        if updating is not None and doc:
            from workflow.measurement_report import (DOCUMENT_SCOPES,
                                                     relative_measurement_key)
            was = {relative_measurement_key(str(m.get("key") or ""))
                   for m in (doc.get("measurements") or [])}
            now = {relative_measurement_key(str(m.get("key") or ""))
                   for m in members}
            recorded = str(doc.get("scope") or "")
            if was and was == now and recorded in DOCUMENT_SCOPES:
                scope = recorded
        # **WHERE THIS REPORT LIVES (K23)**, decided from what it covers.
        home = document_home([m["dir"] for m in members])
        several = len({m["dir"] for m in members}) > 1
        # A TYPE THE KIND ALLOWS (round 2B, #8): what is WRITTEN is fitted.
        _tid = self._fit_to_kind(self._report_type_now())
        #: The row of each measurement, for the verdicts of a document file,
        #: WORKED OUT AGAIN FROM DISK (M4, B8-1094; see `_worked_out_again`).
        by_key = {self._run_key(r): self._worked_out_again(r)
                  for r in self._runs_for_document()}
        doc_members = members
        if several:
            doc_members = []
            for m in members:
                m2 = dict(m)
                r = by_key.get(m["key"])
                if r is not None:
                    rep = {k: v for k, v in r.items() if not k.startswith("_")}
                    stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                                  set_label=lim.label_en, edited=lim.edited)
                    m2[JUDGED_KEY] = judged_block(rep)
                doc_members.append(m2)
        #: The document file it had before this press (Update only).
        old_doc_file = (Path(str(updating["file"]))
                        if updating is not None and updating.get("file")
                        else None)
        keep_doc_file = (old_doc_file is not None and several
                         and home is not None
                         and old_doc_file.parent.resolve() == home.resolve())
        #: The one measurement's own file this press writes (one date only).
        one = reports[0] if (not several and reports) else None
        one_key = self._run_key(one) if one is not None else None
        rewrite_here = existing.get(one_key) if one_key is not None else None
        #: Every file of this report the new shape does not keep: archived,
        #: then taken out of the live folder.
        retire = [p for k, p in existing.items()
                  if k != one_key and p.exists()]
        if old_doc_file is not None and not keep_doc_file \
                and old_doc_file.exists():
            retire.append(old_doc_file)
        saved, failed = [], []
        # **ALL OR NOTHING (round A, A-1; round 2A, R2A-3/R2A-4).** Decided
        # BEFORE anything is archived: every file the press rewrites or
        # retires must be writable in a writable folder (and its `old/`), and
        # the folder a new file goes into must be writable or creatable.
        from core.file_manager import archive_report_files
        _stuck: "set[Path]" = set()
        _touched = [p for p in list(existing.values())
                    + ([old_doc_file] if old_doc_file is not None else [])
                    if p is not None and p.exists()]
        for _p in _touched:
            _old = _p.parent / "old"
            if not (os.access(_p, os.W_OK) and os.access(_p.parent, os.W_OK)) \
                    or (_old.exists() and not os.access(_old, os.W_OK)):
                _stuck.add(_p.parent.resolve())
        if one is not None and (rewrite_here is None
                                or not rewrite_here.exists()):
            _rdir = Path(str(one.get("_origin_dir") or "")) / "reports"
            _ok = (os.access(_rdir, os.W_OK) if _rdir.exists()
                   else os.access(_rdir.parent, os.W_OK))
            if not _ok:
                _stuck.add(_rdir.resolve() if _rdir.exists()
                           else _rdir.parent.resolve())
        if several and home is not None and not keep_doc_file:
            _up = home
            while not _up.exists() and _up.parent != _up:
                _up = _up.parent
            if not os.access(_up, os.W_OK):
                _stuck.add(home.resolve())
        if several and home is None:
            _stuck.add(Path(str(members[0]["dir"])).resolve()
                       if members else Path("."))
        _unarchived: "set[Path]" = set()
        if _touched and not _stuck:
            _archived, _unarchived = archive_report_files(_touched, when)
            for _rdir, _to in _archived.items():
                log.info("archived the reports in %s to %s before updating",
                         _rdir, _to)
            _stuck |= set(_unarchived)
        _blocked = bool(_stuck)
        for _rdir in sorted(_stuck):
            log.warning("the report was not written: %s cannot be archived "
                        "or written, and a report is written whole or not "
                        "at all", _rdir)
        #: WHAT THE RED LINE WAS COMPARING AGAINST BEFORE THIS PRESS (R29-F2).
        was_built = getattr(self, "_doc_built_with", None)
        #: (measurement key, file name) for the one file of a report of one
        #: date, so the page stays on it.
        written: "list[tuple[str, str]]" = []
        if _blocked:
            failed.extend(str(p) for p in sorted(_stuck))
        elif one is not None:
            try:
                rep = dict(by_key.get(one_key) or self._worked_out_again(one))
                for k in [k for k in rep if k.startswith("_")]:
                    rep.pop(k, None)
                stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                              set_label=lim.label_en, edited=lim.edited)
                if _tid:
                    set_report_type(rep, _tid)
                stamp_document(rep, doc_id=doc_id, created=doc_created,
                               type_id=report_type(rep),
                               compliance=rep.get("compliance"),
                               detail=detail,
                               measurements=members, scope=scope,
                               updated=updated)
                if rewrite_here is not None and rewrite_here.exists():
                    # **THE SAME FILE, THE SAME NAME, THE SAME DATE** (CH-29).
                    path = rewrite_report(rewrite_here, rep)
                else:
                    path = save_report(rep, Path(str(one["_origin_dir"])))
                saved.append(path)
                written.append((one_key, path.name))
            except Exception as exc:             # noqa: BLE001
                log.warning("could not generate a report in %s: %s",
                            one.get("_origin_dir"), exc)
                failed.append(str(one.get("_origin_dir")))
        elif several and home is not None:
            first = next((m[JUDGED_KEY] for m in doc_members
                          if m.get(JUDGED_KEY)), {})
            body = document_file(
                doc_id=doc_id, created=doc_created, type_id=_tid,
                compliance=(first or {}).get("compliance"), detail=detail,
                measurements=doc_members, scope=scope, updated=updated)
            try:
                if keep_doc_file and old_doc_file.exists():
                    _doc_path = rewrite_report(old_doc_file, body)
                else:
                    _doc_path = save_report(body, home.parent)
                saved.append(_doc_path)
                log.info("wrote the report of %d measurements: %s",
                         len(members), _doc_path)
            except OSError as exc:               # noqa: BLE001
                log.warning("could not write the report in %s: %s",
                            home, exc)
                failed.append(str(home))
        # **WHAT THE NEW SHAPE NO LONGER HAS LEAVES THE LIVE FOLDERS**, only
        # after the new file is on disk and only where its archive copy was
        # made (D23: nothing is lost, everything is in `old/`).
        if saved and not failed:
            for path in retire:
                if path.parent.resolve() in _unarchived or not path.exists():
                    continue
                try:
                    path.unlink()
                    log.info("retired %s: the report no longer has this "
                             "file, its copy is in old/", path)
                except OSError as exc:           # noqa: BLE001
                    log.warning("could not remove %s: %s", path, exc)
        #: The folders that stopped the press, for M-REPORT-NOT-WRITABLE.
        self._unwritable_folders = sorted(str(p) for p in _stuck)
        self._say_generated(saved, failed)
        self._forget_limits()
        # THE FILE IT JUST WROTE IS WHAT THE PAGE SHOWS, AND IT IS IN THE LIST
        # (B8-252), ONLY WHEN SOMETHING WAS WRITTEN (R29-F2).
        if saved:
            for r in reports:
                self._chosen_reports.pop(self._run_key(r), None)
            for key in existing:
                self._chosen_reports.pop(key, None)
        for key, name in written:
            self._chosen_reports[key] = name
        if saved:
            self._loaded_doc_id = f"id:{doc_id}"
            self._loaded_doc = None          # read back off the file it wrote
            self._doc_settings_moved = False
            self._doc_created = doc_created
            self._doc_sources = self._source_signature()
            self._forget_sticky_settings()
            self._report_own_limits = None
            self._session_type = ""
            self._reload_sources()
        else:
            # **A PRESS THAT WROTE NOTHING MAY NOT TAKE THE RED LINE DOWN
            # (R29-F2).**
            with self._keeping_the_page():
                self._refresh()
            self._doc_built_with = was_built
            self._show_stale_banner()

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
        from workflow import measurement_messages as M
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
        elif failed and getattr(self, "_unwritable_folders", None):
            # WHICH FOLDER, AND WHAT TO DO (challenge C, beta 39, #8).
            warn(self, *M.CATALOGUE["M-REPORT-NOT-WRITABLE"].render(
                folders="\n".join(self._unwritable_folders),
                count=len(self._unwritable_folders)))
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

    @contextmanager
    def _as_the_document_was_built(self):
        """Put the five deferred settings back to what the DOCUMENT was built
        with, for the length of the block, with every signal blocked.

        Knut, 2026-09-18: *"clicking the button always generates a pdf from the
        currently loaded report text"*. The body is composed from the controls
        at the moment it is asked for, so a PDF taken while the red line is up
        was a document nobody had seen: round 21 photographed the screen saying
        *Full colour check* over several pages and the exported file saying
        *Colour summary (one page)* in one.

        `_doc_built_with` is exactly those five as they stood when `_render`
        last ran, so restoring them for the build and putting them back
        afterwards makes the file match the screen with no second code path to
        keep in step. Signals are blocked throughout, so nothing repaints and
        nothing is written to settings; if anything raises, the `finally` puts
        every control back.
        """
        built = getattr(self, "_doc_built_with", None)
        if not built:
            yield
            return
        w_type = getattr(self, "_type_combo", None)
        w_set = getattr(self, "_set_combo", None)
        w_det = getattr(self, "_detail_check", None)
        widgets = [w for w in (w_type, w_set, w_det) if w is not None]
        before = self._doc_settings()
        blocked = [(w, w.blockSignals(True)) for w in widgets]

        def _put(vals):
            t, st, det, hidden = tuple(vals)[:4]
            if w_type is not None and w_type.findData(t) >= 0:
                w_type.setCurrentIndex(w_type.findData(t))
            if w_set is not None and w_set.findData(st) >= 0:
                w_set.setCurrentIndex(w_set.findData(st))
            if w_det is not None:
                w_det.setChecked(bool(det))
            self._hidden_runs = set(hidden)

        # **AND THE TWO THAT ARE NOT WIDGETS AT ALL (R23-F1).** The type and
        # the limit set are read back off the RUN, which `_on_type_chosen` and
        # `_on_set_chosen` have already written to, so putting the pulldowns
        # back was never going to move them. `_remember_how_it_was_built`
        # keeps what the body really read; this hands it back for the build and
        # drops it afterwards. The run is neither read for this nor written to.
        state = getattr(self, "_doc_built_state", None)
        held = (getattr(self, "_type_as_built", ""),
                getattr(self, "_limits_cache", None),
                getattr(self, "_limits_by_origin", None),
                self._limits)
        held_own = getattr(self, "_report_own_limits", None)
        # The page's own rows and whether the document spoke for the controls
        # when it was drawn (M2, B8-1092; see `_remember_how_it_was_built`).
        held_moved = getattr(self, "_doc_settings_moved", False)
        held_rows = getattr(self, "_runs_forced", None)
        # …AND WHICH SAVED REPORT THE PAGE IS (K39-3): after "New report…"
        # the page is still the report shown before it, while the window
        # already holds the new report's defaults. What the body reads of the
        # selected report (its deleted runs, its creation) is the page's.
        held_doc = (getattr(self, "_loaded_doc_id", ""),
                    getattr(self, "_loaded_doc", None),
                    getattr(self, "_doc_created", ""))
        doc_as_built = getattr(self, "_doc_as_built", None)
        try:
            _put(tuple(built))
            if doc_as_built is not None:
                (self._loaded_doc_id, self._loaded_doc,
                 self._doc_created) = doc_as_built
            if state:
                (self._type_as_built, self._limits_cache,
                 self._limits_by_origin, self._limits) = (
                     state[0], dict(state[1]), dict(state[2]), state[3])
                self._report_own_limits = getattr(
                    self, "_own_limits_as_built", None)
            self._doc_settings_moved = bool(
                getattr(self, "_doc_moved_as_built", held_moved))
            drawn = getattr(self, "_runs_as_drawn", None)
            if drawn is not None:
                self._runs_forced = list(drawn)
            yield
        finally:
            (self._type_as_built, self._limits_cache,
             self._limits_by_origin, self._limits) = held
            self._report_own_limits = held_own
            self._doc_settings_moved = held_moved
            self._runs_forced = held_rows
            (self._loaded_doc_id, self._loaded_doc,
             self._doc_created) = held_doc
            _put(before)
            for w, was in blocked:
                w.blockSignals(was)

    def _export_pdf(self) -> None:
        """Write the full report — all data, the trend charts and a plain-language
        guide to reading them — as a PDF, then open it for viewing (Knut)."""
        # **FROM THE MEASUREMENTS THE PAGE WAS DRAWN FROM.** After Remove
        # Profile's Measurements, Clear List or a re-read file the page is
        # kept (Knut, #182 5816794672) and the list is not what it was drawn
        # from; the PDF is the page (Knut, 2026-09-18). So the whole export
        # runs once more inside `_the_page_as_drawn`.
        page = getattr(self, "_the_page_as_drawn", None)
        if page is not None and not getattr(self, "_exporting_the_page", False):
            self._exporting_the_page = True
            try:
                with page():
                    return self._export_pdf()
            finally:
                self._exporting_the_page = False
        if not self._report or not self._ti3:
            return
        from PyQt6.QtCore import QMarginsF, QRectF, QSizeF, QUrl
        from PyQt6.QtGui import (
            QAbstractTextDocumentLayout, QColor, QDesktopServices, QFont,
            QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument,
        )

        reports = self._report_dir()
        # Created for the chooser to open in, and taken away again if the
        # user cancels and nothing was saved there (the K26 round found a
        # cancelled save leaving an empty `<output folder>/reports/`, which
        # Knut ruled exists only once a report across projects is written).
        _made_reports = not reports.exists()
        reports.mkdir(parents=True, exist_ok=True)
        # THE SAME LIST THE DOCUMENT IS BUILT FROM. The one-page summary
        # narrows to a single measurement, and its title and kind narrow
        # with it, but the suggested FILE NAME was still worked out from
        # everything loaded: with a mixed history the name offered could
        # name a different chart from the one printed inside the PDF.
        #
        # AND IT IS THE DOCUMENT'S NAME, NOT THE CONTROLS' (R24-F3, the note).
        # `_report_title` reads the type and the set through the same two
        # readers the body uses, so a name offered outside this wrapper can
        # describe a document the file does not contain. Round 24 could not
        # photograph it moving on the project it drove, whose title strings
        # carry neither; that is a property of one project's Preferences, not
        # a reason to compute the name from a different state than the pages.
        with self._as_the_document_was_built():
            default = reports / self._report_filename(self._runs_for_document())
        # The house save dialog (sidebar shortcuts, ChromIQ styling) — this
        # was the one save in the app still opening the bare native dialog
        # (Sebastian, 2026-08-10).
        from ui.widgets import save_file_dialog
        path = save_file_dialog(
            self, tr("Save report as PDF"), "PDF (*.pdf)",
            start_path=str(default),
            extra_path=str(self._settings.get("custom_output_path", "")))
        # The dialog does not force the extension — a name typed without one
        # must still come out as a .pdf.
        if path and not path.lower().endswith(".pdf"):
            path += ".pdf"
        # **AND WHEN THE PDF GOES SOMEWHERE ELSE (#182 beta 38, F4).** The
        # folder was removed only on cancel, so a PDF saved outside it still
        # left `<output folder>/reports/` behind, empty. Whatever the answer,
        # a folder made here for the chooser goes again unless the PDF is
        # about to be written into it; `rmdir` removes only an empty folder.
        if _made_reports and not (
                path and _same_folder(Path(path).parent, reports)):
            try:
                reports.rmdir()
            except OSError:
                pass
        if not path:
            return

        doc = QTextDocument()
        charts_html = ""
        # The exact same run set the window shows, so the PDF matches it (Knut),
        # AND the settings it was built with rather than the ones the controls
        # hold now: see `_as_the_document_was_built`.
        #
        # **THE CHARTS ARE INSIDE THE SAME SNAPSHOT AS THE BODY (R24-F3).**
        # `_thresholds()` reads `self._limits`, which `_settings_touched` has
        # already cleared, so with the red line up the guide lines on the trend
        # chart were drawn from the set the PULLDOWN now holds while the text
        # beside them named the set the document was built with. Measured on
        # four real PDFs: body byte-identical, *"Judged against: ChromIQ
        # default"* in the text, [1.0, 1.5] in the picture, and the chart
        # image's hash moved. One file cannot be judged against two sets, and
        # nothing in it said which was which.
        with self._as_the_document_was_built():
            if self._trend_de.has_trend():
                # Render each grouped chart off-screen (the live tabs only lay
                # out the current one) and embed it as a resource. The same
                # plan as the tabs (`_trend_plan`), so a hidden tab is not
                # printed (#182 K20/K21).
                for i, (_c, title, metrics, y_max, dec, auto, thr, lines,
                        shown) in enumerate(self._trend_plan()):
                    if not shown:
                        continue
                    # COLOUR ACCURACY PRINTS TWICE AS TALL (Knut, 5787117741:
                    # *"printing the chart in the PDF with a y-axis on the
                    # graph that is, for ex. twice as tall as the graph on
                    # screen"*), so a small change between dates stays
                    # visible; the charts then flow over more than one page.
                    ch_h = _PDF_TREND_H * (_PDF_ACCURACY_SCALE
                                          if _c is self._trend_de else 1)
                    tmp = _TrendChart()
                    tmp.resize(640, ch_h)
                    ex = self._trend_extras(_c)
                    tmp.set_data(self._trend_series, metrics, dark=False,
                                 y_max=y_max, dec=dec, auto=auto, thresholds=thr,
                                 limit_lines=lines,
                                 line_notes=ex["line_notes"],
                                 withheld=ex["withheld"])
                    # Render at 3× and display at the same 600px layout width: a
                    # plain grab() gave a ~96-dpi raster that printed visibly
                    # blurry next to the vector text (Sebastian, 2026-08-10).
                    from PyQt6.QtGui import QImage
                    scale = 3
                    img = QImage(640 * scale, ch_h * scale,
                                 QImage.Format.Format_ARGB32_Premultiplied)
                    img.fill(0xFFFFFFFF)
                    ip = QPainter(img)
                    ip.scale(scale, scale)
                    tmp.render(ip)
                    ip.end()
                    url = QUrl(f"chart://{i}")
                    doc.addResource(QTextDocument.ResourceType.ImageResource,
                                    url, img)
                    # ONE CELL PER CHART, title and picture together, so
                    # `_paginate_tables` moves a whole chart to the next page
                    # rather than leaving its title at the foot of this one:
                    # with Colour accuracy twice as tall and up to ten charts,
                    # the trend section now runs over several pages.
                    #
                    # K25 (Knut, 5789263863): at most two lines above the
                    # picture saying what the graph is and shows, and under
                    # it every line's word and every red x explained, in the
                    # words their tooltips use on screen.
                    charts_html += (
                        "<table cellspacing='0' cellpadding='0'><tr><td>"
                        "<div style='font-size:16px;font-weight:bold;"
                        "margin-top:4px'>" + html.escape(title) + "</div>"
                        + _trend_about_html(ex["about"])
                        # THE PICTURE IN A BLOCK OF ITS OWN: a bare <img>
                        # after the description joined its last line, and a
                        # short last line ("all nine.") was printed beside
                        # the picture's foot, under the graph (drive, K25).
                        + f"<div><img src='chart://{i}' width='600'></div>"
                        + _trend_key_html(tmp.descriptions())
                        + "</td></tr></table>" + _gap())
            runs = self._runs_for_report()
            doc.setHtml(self._pdf_html(runs, charts_html))
            # THE HEADER DESCRIBES THE SAME ROWS AS THE BODY (round B,
            # 2026-09-22): it was built from every TICKED row, so a two-run
            # PDF said "2 measurement runs (2026-04-10 - 2026-05-25)" on every
            # page over a body about one measurement of one date. Read inside
            # this snapshot, as the body is.
            doc_runs = self._runs_for_document()

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
        # HEADINGS STAY WITH WHAT THEY HEAD, AND NO SHEET IS BLANK
        # (re-challenge R2 of beta 39, #12 and #13). `_paginate_tables` keeps a
        # heading with the TABLE under it; "For information (no limit
        # applies)" and "Paper white & darkest black" head lines of text, and
        # the German ISO 12647-8 report left both at the foot of page 9 with
        # their lines overleaf. The rule the help cards already use takes
        # them over together. Then a trend graph's spacer that spilled onto a
        # page of its own in front of a forced break (page 7 of 8, blank, on
        # the German calibration report across two projects) gives that break
        # to the spacer instead. Tables are fitted again after any heading
        # moved, since everything below it moved too.
        from ui.pdf_layout import (avoid_orphan_headings,
                                   break_before_unless_overflowed,
                                   no_blank_page_before_a_break,
                                   set_breaks_before,
                                   tighten_to_close_a_page)
        if avoid_orphan_headings(doc, body_h):
            _paginate_tables(doc, body_h)
        # "FOR INFORMATION" STARTS A PAGE OF ITS OWN (K45-3, Knut #182
        # 5834422633), unless the colour table in front of it already ran
        # over onto the page it would start on. Decided on the settled
        # layout, after the tables have been fitted, since that is what
        # decides where the colour section ends.
        #
        # THEN THE PAGE RULES START AGAIN FROM THE CLEAN DOCUMENT. Every
        # break they set further down was set for where things stood BEFORE
        # this one, and one of them is stale once "For information" has a
        # page of its own: "Worst patches", pushed off the foot of the old
        # page, went on alone to a third sheet with the page it had been
        # pushed from now half empty (the first drive of this change). So
        # everything they did is undone, the breaks decided here are set,
        # and the rules run once more; nothing above a break moves, so the
        # decision stands.
        _info_breaks = break_before_unless_overflowed(
            doc, tr("For information (no limit applies)"),
            tr("Colour accuracy (ΔE00 against the chart's design)"), body_h)
        if _info_breaks:
            while doc.isUndoAvailable():
                doc.undo()
            set_breaks_before(doc, _info_breaks)
            _paginate_tables(doc, body_h)
            if avoid_orphan_headings(doc, body_h):
                _paginate_tables(doc, body_h)
        no_blank_page_before_a_break(doc, body_h)
        # "HOW TO READ THIS REPORT" GIVES UP AT MOST 0.2 PT TO SAVE A SHEET
        # (K45-1, Knut #182 5834422633), and only when that really does
        # bring the one or two lines it spilled back onto its own page.
        # Last, because the section after it starts on a page of its own, so
        # nothing under it moves.
        _panel = _how_to_read_frame(doc)
        if _panel is not None:
            _step = tighten_to_close_a_page(doc, _panel, body_h,
                                            _BODY_TEXT_PX * 0.75)
            if _step:
                log.info("measurement report PDF: \"How to read this "
                         "report\" set %.1f pt tighter to end on its own "
                         "page", _step)

        units = self._scope_header_units(doc_runs)   # profile names + measurements/date
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

        # WHERE IT WENT, AND WHERE IT WAS OFFERED (K9). Knut reported the save
        # dialog opening in the wrong reports/ folder and his log could not
        # say where either the dialog or the file had been: the export wrote
        # nothing to it. Both are logged now, so the next report is checkable.
        log.info("measurement report PDF saved: %s (the dialog offered %s)",
                 path, default)
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
        # A CALIBRATION HAS MEASUREMENTS, NOT RUNS (re-challenge R2 of beta
        # 39, #14): the running header of a calibration report said
        # "2 measurement runs" / "2 Messläufe" on every page, as the list
        # header "P-cal · 1 run" once did (K30 leftover).
        # …AND NEITHER DO THE DATES OF ONE PROFILE RUN: a verification report
        # of three dates of run 1 said "3 measurement runs" while its
        # Included Measurements header says "· 3 measurements" (R2 #15). Each
        # entry here is one dated measurement, whatever holds it.
        count = (tr("{n} measurement").format(n=n) if n == 1
                 else tr("{n} measurements").format(n=n))
        if len(names) <= 4:
            units = [nm + ("," if i < len(names) - 1 else "")
                     for i, nm in enumerate(names)]
            units.append("  " + count)
        else:
            units = [count]
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
        # THE SET THE PAGE IS JUDGED AGAINST (#182 K30): the loaded report's
        # own, the one chosen for it, or the run's, in the order the document
        # writer uses. With the run's alone, a report across places whose own
        # limits were edited drew its Avg line at the run's 2.0 beside a
        # verdict judged at 0.4.
        lim = (self._document_limits() or self._sticky_limits()
               or self._window_limits())
        return legacy_pair(lim.limits if lim is not None else {})

    def _accuracy_thresholds(self) -> "tuple[float | None, float | None]":
        """`_thresholds`, with None for a member whose row is "–" (K28).

        `legacy_pair` answers 2.0 / 3.0 for a row the set does not limit,
        because its old readers need two numbers. A dotted "Avg 2.0" on the
        Colour accuracy graph for a row the set leaves at "–" is a limit line
        for a limit nobody set, so the graph asks this instead. `_TrendChart`
        already draws and describes only the members that are numbers."""
        avg_thr, max_thr = self._thresholds()
        dash = self._dash_row_ids(self._document_runs_for_graphs())
        # **AND ONLY A ROW THE REPORT TYPE JUDGES HAS A LINE (K30 leftover,
        # spec §17 item 4).** A Grey and tone check judges the neutral axis
        # and the ramps, not a colour-accuracy row
        # (`rows_for_report_type`), and its graph drew "Avg 2.0" and
        # "Max 5.0" as "the limit for" rows the page does not judge.
        from workflow.measurement_report import rows_for_report_type
        keep = rows_for_report_type(self._report_type_now())
        judged = (lambda rid: keep is None or rid in keep)
        return (None if "all_de00_avg" in dash or not judged("all_de00_avg")
                else avg_thr,
                None if "all_de00_max" in dash or not judged("all_de00_max")
                else max_thr)

    def _accuracy_row_limits(self) -> "dict[str, float]":
        """``{row_id: limit}`` for each of the five rows the Colour accuracy
        graph plots that this document judges against a number (K45-2).

        The same set `_thresholds` reads the grey pair from, and the same two
        filters `_accuracy_thresholds` puts on it: a row the set leaves at "–"
        and a row the report type does not judge have no line."""
        if self._ungraded_by_type():
            return {}
        from workflow.measurement_report import rows_for_report_type
        lim = (self._document_limits() or self._sticky_limits()
               or self._window_limits())
        limits = lim.limits if lim is not None else {}
        dash = self._dash_row_ids(self._document_runs_for_graphs())
        keep = rows_for_report_type(self._report_type_now())
        out: "dict[str, float]" = {}
        for rid, _family in _ACCURACY_LINE_ROWS:
            one = limits.get(rid)
            if (one is None or not getattr(one, "is_numeric", False)
                    or rid in dash or (keep is not None and rid not in keep)):
                continue
            out[rid] = float(one.number)
        return out

    def _accuracy_line_plan(self) -> "tuple[list, list]":
        """What the Colour accuracy graph's limit lines say (K45-2, Knut
        #182 5834422633: *"Several reports, or all, are lacking under the
        graph for 'Colour accuracy (ΔE00)' the description of the horizontal
        threshold lines ... they should always be showing below each chart,
        if they have a threshold associated with that graph."*).

        Returns ``(pair_notes, extra)``. ``pair_notes`` are the sentences of
        the grey Avg and Max lines, in that order ("" for a member that is not
        drawn); each names EVERY plotted row the set limits at that line's
        number in its family, not only the all-patch row: ChromIQ's own sets
        put the lowest 95 % and highest 5 % averages at the Avg number and the
        95th percentile at the Max number, and the graph plotted those rows
        with no word about their limit. ``extra`` is ``[(value, word, note)]``
        for a judged row neither line stands for: the ISO sets limit the 95th
        percentile at 5.0 and the all-patch maximum not at all, so that row
        gets a grey line of its own, "P95"."""
        avg_thr, max_thr = self._accuracy_thresholds()
        limits = self._accuracy_row_limits()
        runs = self._document_runs_for_graphs()
        covered: set = set()
        pair_notes = []
        for word, thr, family, own in ((tr("Avg"), avg_thr, "avg",
                                        "all_de00_avg"),
                                       (tr("Max"), max_thr, "max",
                                        "all_de00_max")):
            if not isinstance(thr, (int, float)):
                pair_notes.append("")
                continue
            rids = [own] + [rid for rid, fam in _ACCURACY_LINE_ROWS
                            if fam == family and rid != own and rid in limits
                            and abs(limits[rid] - float(thr)) < 1e-9]
            covered.update(rids)
            pair_notes.append(_limit_line_note_for_rows(
                word, thr, "ΔE00", rids,
                [self._row_name(r, runs) for r in rids]))
        groups: "dict[tuple, list]" = {}
        for rid, family in _ACCURACY_LINE_ROWS:
            if rid in covered or rid not in limits:
                continue
            groups.setdefault((family, limits[rid]), []).append(rid)
        extra = []
        for (family, value), rids in groups.items():
            word = (tr("Avg") if family == "avg"
                    else tr("P95") if rids == ["all_de00_p95"] else tr("Max"))
            extra.append((value, word, _limit_line_note_for_rows(
                word, value, "ΔE00", rids,
                [self._row_name(r, runs) for r in rids])))
        return pair_notes, extra

    def _colour_accuracy_is_judged(self) -> bool:
        """Whether the page judges either colour-accuracy row the graph's
        two lines stand for: not on a Printing record, and not on a type
        whose rows leave both out (a Grey and tone check)."""
        if self._ungraded_by_type():
            return False
        a, m = self._accuracy_thresholds()
        return (isinstance(a, (int, float)) or isinstance(m, (int, float))
                or bool(self._accuracy_row_limits()))

    def _document_runs_for_graphs(self) -> list:
        """The document's measurements, for a graph deciding what to draw;
        empty when nothing is loaded (a bare chart in a test, a window before
        its first source)."""
        if not getattr(self, "_sources", None):
            return []
        try:
            return self._runs_for_document()
        except Exception:      # noqa: BLE001 - a graph, never a gate
            log.debug("could not list the document's runs", exc_info=True)
            return []

    def _row_limits_of(self, r: dict) -> "dict | None":
        """``{row_id: Limit}`` *r* is judged against, or None when unknown.

        A saved verdict answers from the limits it was SAVED with (its
        ``compliance.thresholds``), which is what its rows were judged
        against; a verdict saved before those were recorded answers None, and
        nothing is dropped for it. A live column answers from its run's set,
        as `_verdict_rows` judges it."""
        from workflow.compliance_sets import Limit
        from workflow.measurement_report import recorded_compliance
        if self._recorded(r) is not None:
            comp = recorded_compliance(r) or {}
            th = comp.get("thresholds")
            if not isinstance(th, dict):
                return None
            return {str(k): Limit.from_json(v) for k, v in th.items()}
        try:
            lim = self._limits_for(r)
        except Exception:      # noqa: BLE001 - advisory, never a gate
            return None
        return dict(lim.limits) if lim is not None else None

    def _dash_row_ids(self, runs: list) -> "set[str]":
        """The rows the document's limit set leaves at "–" (K28, item 3).

        Knut, #182 5795087247: a limit set to "–" removes the row from Report
        Results, How to read, Detailed data, the graph AND the Overview table.
        The first three are built from `_verdict_rows`, which drops such a row
        itself; the Overview and the Colour accuracy graph are built from the
        measurement's figures, so they ask this.

        A row is dropped only when EVERY graded column leaves it at "–": one
        document has one limit set (`_one_limit_set`), so they agree, and when
        they cannot be read (an old saved verdict) nothing is dropped, because
        a row wrongly hidden is a figure the reader never sees."""
        out: "set[str] | None" = None
        for r in runs or ():
            if _is_raw_drift(r):
                continue
            lims = self._row_limits_of(r)
            if lims is None:
                return set()
            mine = {rid for rid, lim in lims.items()
                    if getattr(lim, "kind", "") == "none"}
            out = mine if out is None else (out & mine)
        return out or set()

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

    def _inside_a_project(self) -> bool:
        """Whether the measurement on screen lies inside a ChromIQ project.

        Asked of the same file `_context_run` asks about, because the two
        answers are read side by side: a calibration has no RUN and is in a
        project all the same (R24-F6).
        """
        from workflow.run_compliance import project_root_for
        origin = (self._sources[0]["origin"] if self._sources
                  else (self._ti3 or None))
        return project_root_for(origin) is not None

    def _distinct_run_dirs(self) -> "set[str]":
        """How many different PROFILE RUNS the window holds (CH-13)."""
        from workflow.run_compliance import run_context_for
        dirs: set = set()
        for src in self._sources:
            ctx = run_context_for(src["origin"])
            dirs.add(str(ctx.run.dir) if ctx else f"external:{src['origin']}")
        return dirs

    def _several_runs(self) -> bool:
        """Does the window hold measurements ADDED from more than one profile
        run (CH-13)? One name for the question `_sync_limit_controls` and
        `_on_type_chosen` both ask, so the two cannot drift apart.

        **SOURCES, NOT TICKED ROWS, and the ticked-rows version was tried and
        reverted the same day.** A window's history spans every run of its
        project, so an ordinary profiling window on run 2 ticks run 1's sheet
        as well by default: counting the runs of the ticked rows made every
        such window "several" and killed its Generate button, which the
        existing guard
        `test_the_button_refuses_when_its_own_run_is_unticked` caught. What
        makes a window span runs in the sense that matters here is a second
        profile ADDED through "Add profile's measurements...".
        """
        return len(self._distinct_run_dirs()) > 1

    def _window_limits(self):
        """The STARTING CHOICE of a new report's limits (K31): the window's
        run's own default when it has one, else the Preferences default. A
        loaded report, or a set chosen in this window, outranks it
        (`_report_limits`)."""
        if self._limits is None:
            from workflow.run_compliance import run_limits
            ctx = self._context_run()
            self._run_ctx = ctx
            self._limits = run_limits(ctx.run if ctx else None, self._overrides(),
                                      self._default_set_id())
        return self._limits

    def _limits_for(self, r: dict):
        """The RunLimits a measurement of this report is judged with live:
        THE REPORT'S, whichever run the measurement is in (K31, one set for
        the whole report). Until K31 this was the row's own run's set, which
        is how two dates of one report could be judged against two sets.

        *r* is kept in the signature because every caller asks it of a row.
        """
        return self._report_limits()

    def _forget_limits(self) -> None:
        """Drop what was read from disk so the next look re-reads it. A
        session-only choice for a file that is in no run (CH-14) is kept: there
        is nothing on disk to re-read it from."""
        self._limits_cache = {}
        # **AND `_limits_by_origin` IS DELIBERATELY NOT CLEARED HERE.** It was,
        # and that made the fix it exists for inert in the app: `_refresh()`
        # calls this and THEN renders, so with the folder already gone nothing
        # in the render could refill it and every row fell through to the
        # window's set again. Driven through `_refresh()`: memo 0 entries, 3
        # kept and 0 dropped, which is the symptom the fix was written for
        # (R19-3). It is only ever consulted when `run_context_for` cannot read
        # the run at all, so a stale entry can only be reached in the one state
        # where there is nothing on disk to be stale against.
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
        """Fill the pulldown, name the run, fill the strip.

        **K31: NO LOCK.** Every control here is live whenever a measurement is
        loaded: the limit set is the REPORT's (Knut, 5801677743), so there is
        no run whose numbers could be protected by greying it, and "Unlock
        this run's limits" is gone with the lock behind it (§25 of
        `docs/design/measurement_report_limits.md` says what it protected and
        why nothing replaces it).
        """
        if getattr(self, "_set_combo", None) is None:
            return
        from workflow.compliance_sets import SET_BY_ID, selectable_set_ids
        lim = self._window_limits()
        ctx = self._run_ctx
        run = ctx.run if ctx else None
        self._adopt_visible_document(run)
        self._syncing_limits = True
        try:
            self._set_combo.clear()
            ids = selectable_set_ids(self._overrides())
            # **THE LOADED DOCUMENT'S OWN SET, WHEN ONE IS LOADED (B8-382).**
            # Knut: *"Changing selected report in the saved report pulldown
            # does not change any of the other settings that the selected
            # report had when it was generated."*
            dlim = self._document_limits() or self._sticky_limits()
            shown = dlim or lim
            if lim.set_id not in ids:
                self._set_combo.addItem(lim.set_label, lim.set_id)
            if shown.set_id not in ids and shown.set_id != lim.set_id:
                self._set_combo.addItem(shown.set_label, shown.set_id)
            for sid in ids:
                self._set_combo.addItem(SET_BY_ID[sid].label and
                                        tr(SET_BY_ID[sid].label), sid)
                self._set_combo.setItemData(
                    self._set_combo.count() - 1, tr(SET_BY_ID[sid].blurb),
                    Qt.ItemDataRole.ToolTipRole)
            idx = self._set_combo.findData(shown.set_id)
            self._set_combo.setCurrentIndex(max(0, idx))
            several = self._several_runs()
            # F6: the button's text changes, so its width must follow it
            self._limits_btn.setText(tr("Edit limits…"))
            self._limits_btn.setMinimumWidth(self._limits_btn.sizeHint().width())
            self._set_combo.setEnabled(True)
            self._limits_btn.setEnabled(True)
            # **NO RUN IN THE LABEL (B8-946).** Since K31 the set is the
            # REPORT's, not a run's, so "Judged against (run1):" tied it to
            # a run it no longer belongs to (and printed "run1" in English in
            # every language).
            self._judged_label.setText(tr("Judged against:"))
            if not self._sources and self._ti3 is None:
                set_tip = tr("No measurement is loaded yet.")
                btn_tip = set_tip
            else:
                set_tip = tr(
                    "The limit set this report is judged against. Every "
                    "measurement ticked in the list is judged against it, "
                    "whichever profile run or project it comes from. Changing "
                    "it changes only the settings of the report shown: nothing "
                    "is judged again or written until you press Generate "
                    "report.")
                # **AND WHAT ELSE THE WINDOW CHANGES, AT ONCE (B8-943, §25.3).**
                # "A change applies to this report only" was false of every
                # column but the first: the Preferences sets and "Default for
                # new reports" are written the moment they are changed, as in
                # Preferences, Reports. The sentence now says both.
                btn_tip = tr(
                    "Opens the limits of the report shown, in the first column "
                    "“This report”, beside every limit set. A change in “This "
                    "report” applies to this report only and is applied when "
                    "you press Generate report. The other columns and “Default "
                    "for new reports” are the settings of Preferences, Reports: "
                    "a change there is stored at once and changes no saved "
                    "report.")
            # **AND WHY IT IS NOT THE PREFERENCES DEFAULT, WHEN IT IS NOT
            # (B8-526, K31).** Under "New report…" the set is the run's own
            # default when it has one (chosen in Edit limits, or bound by an
            # earlier ChromIQ), and the pulldown says so.
            if (self._loaded_doc_id == NEW_REPORT_KEY and run is not None
                    and not several and lim.set_id != self._default_set_id()):
                d = SET_BY_ID.get(self._default_set_id())
                # **A SET AN OLDER ChromIQ BOUND THE RUN TO WAS CHOSEN BY
                # NOBODY IN EDIT LIMITS (B40-A 5).** `bound` is that copy
                # (§25.4, "Old files"); the sentence says where it came from
                # and claims no one chose it.
                if lim.bound:
                    set_tip = tr(
                        "New reports of this profile run start on {set}, the "
                        "run's own default, carried over from an earlier "
                        "version of ChromIQ. The default for new reports is "
                        "{default}, in Preferences, Reports. Choose "
                        "“Default for this run” in Edit limits to change "
                        "it.")
                else:
                    set_tip = tr(
                        "New reports of this profile run start on {set}, the "
                        "run's own default, chosen in Edit limits. The default "
                        "for new reports is {default}, in Preferences, "
                        "Reports.")
                set_tip = set_tip.format(
                    set=lim.set_label,
                    default=tr(d.label) if d else self._default_set_id())
            self._set_combo.setToolTip(set_tip)
            self._limits_btn.setToolTip(btn_tip)
            self._sync_type_combo(run, several)
            self._grey_the_sets_the_type_refuses()
            self._sync_saved_reports(run)
            self._set_strip(self._mismatch_text())
            # **AND THE ROWS ARE DRAWN HERE, IN THE ONE PLACE EVERY DOOR GOES
            # THROUGH (B8-521).** Only `_rebuild_from_sources` used to draw a
            # tick, and it is the one door that re-reads the files; every
            # other door that assigns `_hidden_runs` -- "New report…", loading
            # a document, the page adopting the document Generate just wrote
            # -- repainted through `_refresh` or `_settings_touched`, both of
            # which touch the body and the charts and never the list. So the
            # list went on showing the PREVIOUS narrowing while the code
            # believed the new one, and because `setCheckState` to a value a
            # row already holds emits nothing, every later tick was read
            # against the wrong baseline: Knut ticked three of eleven and got
            # a document of ten.
            #
            # It sits AFTER `_sync_type_combo` because the report type decides
            # what the list draws (`_rows_drawn_unticked`), and inside
            # `_syncing_limits` because it must not be read as a user's tick.
            self._draw_the_row_ticks()
        finally:
            self._syncing_limits = False

    # ------------------------------------------------------------------
    # Saved reports: choose one, or delete one (B8-250)
    # ------------------------------------------------------------------
    def _saved_report_choices(self, run) -> list:
        """``[(row, file name, label)]`` for every saved report of *run*.

        Taken from the history the window already holds, not from a fresh walk
        of the folder: `_one_row_per_measurement` records every report file of
        a measurement on the row it keeps, so the list here and the row on
        screen cannot disagree about what exists.

        ONLY THIS RUN'S. Everything else this window WRITES is this run's, for
        the reason `_recalculate_run` gives at length: `…/runs/run10` starts
        with `…/runs/run1`, so the folders are asked of the run rather than
        matched out of a string. A window opened on one run gathers the whole
        project's history to draw the trend (#40), and offering to delete
        another run's files out of that list would be the widest reach in the
        window by far.
        """
        if run is None:
            return []
        try:
            mine = {str(run.dir)} | {str(v.dir) for v in run.verifications()}
        except Exception:                            # noqa: BLE001
            mine = {str(run.dir)}
        out: list = []
        for r in self._history:
            if str(r.get("_origin_dir") or "") not in mine:
                continue
            for name in (r.get("_all_report_files") or []):
                out.append((r, name, self._saved_report_label(r, name)))
        # Newest first: the one a reader is most likely to want is the one at
        # the top, and `_report_file_order` is the window's one answer to
        # "which of these was written last".
        out.sort(key=lambda t: (str(t[0].get("created") or ""),
                                _report_order(t[0].get("_origin_dir"), t[1])),
                 reverse=True)
        return out

    def _adopt_visible_document(self, run) -> None:
        """The document on the page speaks for the controls, until the user
        moves one.

        Without this, only a CLICK in the list restored a document's settings,
        and the two other ways of arriving at a document did not: opening the
        window on a measurement whose newest report belongs to one, and
        pressing Generate report, which writes one and shows it. The window
        then drew a document of one kind under a pulldown naming another, which
        is Knut's fifth defect seen from the other side.

        It runs before the pulldowns are filled, because they are filled from
        what this decides.
        """
        if getattr(self, "_doc_settings_moved", False):
            return
        # "New report…" is not a document and no file may claim its place: the
        # defaults on screen are the user's starting point until they press
        # Generate report (B8-388).
        if self._loaded_doc_id == NEW_REPORT_KEY:
            return
        here = self._loaded_doc_id or self._document_key_of_report()
        if not here:
            return
        if self._loaded_doc is not None and self._loaded_doc_id == here:
            # Already speaking for the controls, and it may be the settings
            # `_load_document` worked out for a report that records none of its
            # own. Re-reading the file here would throw those away.
            return
        entry = next((d for d in self._saved_documents(run)
                      if d["key"] == here), None)
        if entry is None:
            return
        self._loaded_doc_id = entry["key"]
        # **AND AN ENTRY WITHOUT A DOCUMENT BLOCK SPEAKS TOO (R27-F3).** This
        # was `entry["doc"]`, which is None for every report written before the
        # document record existed, so the pulldown NAMED such an entry and
        # nothing else on screen followed it. Driven on screen, default
        # Preferences, `Report-Limits-Report-Types/run1`, no user action at
        # all: *Report shown* read "2026-11-02 10:00 · **Printing record (not
        # graded)** · ChromIQ default (recommended)", *Report type* read
        # "**Colour summary (one page)**", the page's own head line agreed with
        # the type pulldown, and the red "settings have changed" line was down,
        # so the window said nothing was out of step. Clicking the entry the
        # pulldown was ALREADY on then changed both. Same entry, two documents.
        #
        # P.10 is the rule: *"Opening the window selects the latest report
        # created, with the settings it was made with"*, and K.5 says what
        # those settings are for a report that records none of its own.
        # `_settings_of_one_saved_report` is the one place that answers it, and
        # a CLICK has used it since B8-382; this is the same answer at the
        # other door, so the two cannot disagree again.
        #
        # **AND ALL FIVE SETTINGS MOVE, NOT TWO (B8-490).** This used to
        # restore the type and the limit set only, and said so: the two tick
        # boxes were `_apply_document`'s alone, because B8-388 had decided
        # deliberately against imposing them at this door. Knut overruled that
        # on 2026-09-19 — *"All settings that belong to a report shall be
        # loaded"* — so the one method that writes the other three is called
        # here as well, and the three doors into a document cannot disagree
        # about what a document IS.
        self._loaded_doc = (entry["doc"]
                            or self._settings_of_one_saved_report(entry))
        self._doc_created = self._document_created_stamp(entry)
        self._doc_sources = self._source_signature()
        self._restore_the_documents_view(
            self._loaded_doc, recorded=bool(entry["doc"]),
            covers={self._run_key(r) for r, _n in (entry["members"] or [])})

    def _saved_documents(self, run) -> list:
        """The generated reports of *run*, as DOCUMENTS, newest first.

        ``[{"key", "doc", "members": [(row, file name)], "label", "order"}]``.

        **THIS IS B8-383.** A saved report was a per-measurement verdict
        record, so one press of Generate report wrote one file per measurement
        and the selector listed every one of them. Knut counted it exactly:
        *"Clicking 'Show all measurement runs' ON, and then generate report,
        creates 2 new reports under the saved reports, which is wrong
        behaviour."* Measured on a run with two dated verifications, one press
        took the project from two files to four, and a second press from four
        to six.

        The files are still one per measurement, because a dated
        verification's verdict has to live in that date's own folder (§5). What
        they carry now is a shared document id and the settings of the press
        that wrote them, so ONE press is ONE entry here.

        **A REPORT WITH NO DOCUMENT BLOCK IS ITS OWN DOCUMENT.** Every report a
        user already has was written without one, and every one of them is
        still listed, still named the way it is named today and still opens.
        Nothing on disk is read for this beyond the report files themselves,
        and nothing is written.

        ONLY THIS RUN'S, for the reason `_recalculate_run` gives at length:
        `…/runs/run10` starts with `…/runs/run1`, so the folders are asked of
        the run rather than matched out of a string.
        """
        from workflow.measurement_report import (KIND_PROFILING,
                                                 KIND_VERIFICATION,
                                                 document_key_of,
                                                 report_types_for_kind)
        # A CALIBRATION HAS NO RUN AND HAS REPORTS (#182 beta 39): its
        # folders come from the list (`_measurement_dirs_of_the_list`).
        if run is None and not self._is_calibration_window():
            return []
        # **ONLY WHAT THE RUN TYPE CAN HAVE (K19).** Knut, 2026-09-23: *"the
        # listed reports in the pulldown and those counted in 'Already
        # generated for this run:...' text, must only include the correct
        # report type based on what the run type parameter is set to"*, and a
        # user may load measurements from more than one place. The folders
        # follow the window's kind (a profiling sheet's reports live in the
        # run's own folder, a verification's in its dated folders), and so do
        # the types; `generated_report_types` asks the same two questions.
        kind = self._window_kind()
        # **THE FOLDERS OF THE MEASUREMENTS IN THE LIST (K23).** Knut,
        # 2026-09-23: the reports listed and counted *"must look in the
        # folders that are relevant for the measurements added in the
        # 'Included measurements..' list"*. This asked the window's RUN for
        # its folders; it now asks the list, still by the profile bar's kind,
        # and `_generated_types_line` hands the same folders to the counter.
        mine = set(self._measurement_dirs_of_the_list(run, kind))
        allowed = set(report_types_for_kind(kind))
        docs: "dict[str, dict]" = {}
        order: "list[str]" = []
        #: {document id: [(row, file name)]} for the VERDICT RECORDS of a
        #: document of several measurements (K23). A record is never an
        #: entry of its own; it is a member of the document it records.
        records: "dict[str, list]" = {}
        from workflow.measurement_report import (is_verdict_record,
                                                 shared_documents)
        for r in self._history:
            origin = str(r.get("_origin_dir") or "")
            if origin not in mine:
                continue
            for name in (r.get("_all_report_files") or []):
                doc = self._document_of(origin, name, r)
                if is_verdict_record(doc):
                    records.setdefault(str(doc.get("id") or ""), []).append(
                        (r, name))
                    continue
                key = document_key_of(doc, Path(origin) / "reports" / name)
                entry = docs.get(key)
                if entry is None:
                    entry = docs[key] = {"key": key, "doc": doc,
                                         "members": [], "order": ()}
                    order.append(key)
                entry["members"].append((r, name))
                when = _report_order(origin, name)
                if when > entry["order"]:
                    entry["order"] = when
        # **AND THE DOCUMENTS OF SEVERAL MEASUREMENTS, FROM WHERE THEY LIVE
        # (K23)**: `runN/verifications/reports/` and `<project>/reports/`.
        # Each is listed once, when it covers a measurement in the list, with
        # its own file (`entry["file"]`, which Update rewrites and Delete
        # moves) and its verdict records as members, so the page is drawn
        # from the records exactly as a document's files always were.
        for path, block in shared_documents(sorted(mine)):
            key = document_key_of(block, path)
            origin = path.parent.parent
            entry = docs.get(key)
            if entry is None:
                entry = docs[key] = {"key": key, "doc": block,
                                     "members": [], "order": ()}
                order.append(key)
            entry["file"] = path
            entry["doc"] = block
            entry["members"].extend(records.get(str(block.get("id") or ""),
                                                []))
            when = _report_order(origin, path.name)
            if when > entry["order"]:
                entry["order"] = when
        out = [docs[k] for k in order
               if self._entry_type(docs[k]) in allowed]
        for entry in out:
            entry["label"] = self._document_label(entry)
        # **THE SAVED STAMP IS A TIE-BREAK, NOT A SECOND DATE ON EVERY LINE
        # (B8-594).** Knut, 2026-09-20, on the eleven reports the demo pack
        # ships: *"each are showing both the created date in front, and the
        # saved date at the end. Only the create date should be included for
        # reports creation, and the trailing ' - Updated date time' should be
        # added only upon update of a report."*
        #
        # It was appended to every legacy entry unconditionally, and the
        # paragraph in `_saved_report_label` says why it was put there: a
        # tester's run held fifty reports of one measurement and forty-eight
        # of them drew the identical line. Both are true, and neither needs
        # the other's cost. The stamp is what tells two entries apart, so it
        # is added where there ARE two to tell apart and nowhere else.
        seen: "dict[str, list]" = {}
        for entry in out:
            seen.setdefault(entry["label"], []).append(entry)
        for label, group in seen.items():
            if len(group) < 2:
                continue
            for entry in group:
                if entry.get("doc") or not entry.get("members"):
                    continue                 # a document names its own updates
                r, name = entry["members"][0]
                entry["label"] = self._saved_report_label(
                    r, name, with_stamp=True)
        # Newest first: the one a reader is most likely to want is at the top.
        # BY THE REPORT'S OWN CREATION DATE (#182 A9, `_report_created_at`),
        # and the file time (`_report_order`) only breaks a tie, so a copied
        # or restored report sorts where its date puts it.
        out.sort(key=lambda e: (_report_created_at(e), e["order"]),
                 reverse=True)
        return out

    def _measurement_dirs_of_the_list(self, run,
                                      kind: "str | None") -> "list[str]":
        """The folders of the measurements in "Included measurements" whose
        reports this window lists and counts, of *kind* (None keeps both), in
        list order (K23).

        One answer for the two readouts, so "Report shown" and "Already
        generated" look in the same folders by construction.

        **WHICH ROWS: EVERY ROW IN THE LIST (K25).** Knut, 2026-09-23, on a
        Profiling window: *"'Already generated for this run' and 'Report
        shown' shall list and count every run's Printing records if the rules
        are fulfilled ... The combination of measurements added in the
        'Included measurements...' and the locations defined by the added
        measurements ... defines ... where to search for Printing records."*

        This used to skip the other runs' sheets a Profiling window gathers
        by itself for the trend over a printer's builds (#40), and the K23
        entry asked him whether it should. That is his answer: every row the
        list holds names a folder, ticked or not, and those folders are read.
        The reason the skip existed (a window opened on run 2 came up on run
        1's newer report) is handled where it arose, in
        `_open_on_the_latest_report`, which opens on the newest report of
        the window's OWN run.
        """
        from workflow.measurement_report import (KIND_CALIBRATION,
                                                 measurement_dir_kind)
        if kind == KIND_CALIBRATION:
            return self._calibration_dirs_of_the_list()
        if run is None:
            return []
        own = {str(run.dir)}
        try:
            own |= {str(v.dir) for v in run.verifications()}
        except Exception:                            # noqa: BLE001
            pass
        wanted: "set[str]" = set(own)
        for src in getattr(self, "_sources", None) or []:
            wanted |= {str(r.get("_origin_dir") or "")
                       for r in (src.get("runs") or [])}
        wanted.discard("")
        # THE WINDOW'S OWN RUN ALWAYS, whether or not a row of it is in the
        # list (K24: a window on a dated verification with the bar on
        # Profiling still counts the run's Printing record).
        out: "list[str]" = [d for d in [str(run.dir)] + sorted(own - {str(run.dir)})
                            if kind is None or measurement_dir_kind(d) == kind]
        for r in getattr(self, "_history", None) or []:
            origin = str(r.get("_origin_dir") or "")
            if not origin or origin in out or origin not in wanted:
                continue
            if kind is None or measurement_dir_kind(origin) == kind:
                out.append(origin)
        return out

    def _calibration_dirs_of_the_list(self) -> "list[str]":
        """The calibration folders a Calibration window lists and counts the
        reports of, the window's own first (#182 beta 39).

        Knut, 5794078008: *"'Included measurements...' lists the measurement
        in the cal/ folder. If another cal-folder's measurement is selected
        (which is only possible selecting in a different project), then the
        'Included measurements...' list will hold multiple measurement
        sets."* So: every row of the list whose folder is a project's
        calibration, and nothing else; a run's measurement added to a
        Calibration window names no folder here, as a verification names
        none on a Profiling window (K24).
        """
        from workflow.measurement_report import is_calibration_dir
        out: "list[str]" = []
        own = self._own_cal_dir()
        if own is not None:
            out.append(str(own))
        wanted: "set[str]" = set()
        for src in getattr(self, "_sources", None) or []:
            wanted |= {str(r.get("_origin_dir") or "")
                       for r in (src.get("runs") or [])}
        wanted.discard("")
        for r in getattr(self, "_history", None) or []:
            origin = str(r.get("_origin_dir") or "")
            if (origin and origin not in out and origin in wanted
                    and is_calibration_dir(origin)):
                out.append(origin)
        return out

    def _entry_type(self, entry: dict) -> str:
        """The type one entry of "Report shown" is shown as: its document's
        own type, or, for a file with no document block, what its label names
        (`_type_a_file_renders_as`), so the list and its label agree."""
        doc = entry.get("doc") or {}
        tid = str(doc.get("type") or "")
        if tid:
            return tid
        if not entry.get("members"):
            return ""
        r, name = entry["members"][0]
        try:
            rep = json.loads(read_text(
                Path(str(r.get("_origin_dir") or "")) / "reports" / name))
        except Exception:                            # noqa: BLE001
            rep = {}
        return self._type_a_file_renders_as(
            rep if isinstance(rep, dict) else {}, r)

    def _document_of(self, origin, name: str, r: dict) -> "dict | None":
        """The document block of one saved report file, or None.

        READ ONCE PER FILE, keyed by path and mtime, for the reason
        `_saved_report_label` gives: this is asked for every saved report of
        the run on every repaint, and a run can hold fifty reports of 19 kB
        each.
        """
        from workflow.measurement_report import recorded_document
        path = Path(origin) / "reports" / name
        cache = getattr(self, "_doc_cache", None)
        if cache is None:
            cache = self._doc_cache = {}
        try:
            stamp = path.stat().st_mtime_ns
        except OSError:
            stamp = 0
        hit = cache.get(str(path))
        if hit is not None and hit[0] == stamp:
            return hit[1]
        rep: "dict | None" = None
        if str(r.get("_report_file") or "") == name:
            rep = r
        if rep is None:
            try:
                rep = json.loads(read_text(path))
            except Exception:                        # noqa: BLE001
                rep = {}
        doc = recorded_document(rep)
        cache[str(path)] = (stamp, doc)
        return doc

    def _document_label(self, entry: dict) -> str:
        """How one document is named in the list (L.3).

        Knut: *"The list of reports need to have names generated, with date and
        time, that reflect their selections, so that a user can distinguish
        between them. F.ex. 'Run type, Judged agains, All runs, with details,
        <date_time>', or 'Run type, Judged agains, only run <date>, without
        details, <date_time>'."*

        A file with no document block keeps the name it has today, because it
        recorded none of those selections and a name invented for it would be a
        claim about a press nobody made.
        """
        doc = entry.get("doc")
        members = entry.get("members") or []
        if not doc:
            r, name = members[0]
            return self._saved_report_label(r, name)
        from workflow.compliance_sets import set_label
        from workflow.measurement_report import report_type_name
        bits: "list[str]" = []
        # **THE CREATION STAMP LEADS THE NAME, AND THE TRAILING "saved …" IS
        # GONE (B8-490).** Knut, 2026-09-19: *"when a report created the first
        # time the trailing ' - saved <date> <time>' should not be added
        # (created time stamp already part of the beginning of the name)."*
        # His parenthesis is the premise, and it was not true of this build:
        # a document's name began with its report TYPE and carried the stamp
        # only at the end, so dropping the end alone would have left fifty
        # reports of one measurement drawing the identical line — the exact
        # fault `_saved_report_label` records at length. The stamp MOVES; no
        # information leaves the name, seconds included.
        #
        # **HIS RUN-NUMBER PREFIX IS NOT BUILT HERE.** The same comment asks
        # for *"Run 1 - <date_created> <time_created> -"* on a profiling run's
        # entries, and that belongs to the held storage/naming ruling (which
        # folder a report lives in, the report_profiling / report_verification
        # tags). This is the one half of it that moves no file.
        made = str(doc.get("created") or "").replace("T", " ")[:19]
        if made:
            bits.append(made)
        try:
            bits.append(tr(report_type_name(str(doc.get("type") or ""))))
        except Exception:                            # noqa: BLE001
            pass
        comp = doc.get("compliance") or {}
        if comp.get("set_id"):
            bits.append(set_label(str(comp.get("set_id", "")),
                                  str(comp.get("set_label", ""))))
        # **THE FLAGS KNUT SPECIFIED (B8-392, 2026-09-18).** *"The report names
        # created should include flags that indicate the settings, just as
        # Report type and Judged against"*: "All dates", "One date",
        # "Multiple dates", and "Detailed" when the detail box is on.
        #
        # TRANSLATED HERE, BECAUSE NOTHING OF THE NAME IS STORED. The document
        # block keeps ids and English labels (the type id, the set id beside
        # its English label, and now a scope id); this builder is the one place
        # that turns them into words, so a report named on a German machine
        # reads in English on an English one and matches what this build looks
        # for. The words are what changed; where they come from did not.
        from workflow.measurement_report import document_scope_of
        scope = document_scope_of(doc)
        bits.append(self._scope_tag(scope, entry))
        if doc.get("detail"):
            bits.append(tr("Detailed"))
        # A DOCUMENT THAT RECORDS NO MEASUREMENT AT ALL SAYS SO (R1 #4). This
        # build never writes one, but the build before it did, and its name
        # would otherwise read as the report it had been.
        if isinstance(doc.get("measurements"), list) \
                and not doc.get("measurements"):
            bits.append(tr("covers no measurement"))
        # **AND WHEN IT WAS LAST UPDATED, ON THE END (B8-491).** Knut:
        # *"Update button will keep the current selected report, then append on
        # the ending of the report name ' - updated <date> <time>'."* Whether a
        # SECOND update appends a second stamp or replaces the first is open
        # with him; `NAME_SHOWS_EVERY_UPDATE` is where that decision lives and
        # the default is replace, so the name says when the report was created
        # and when it was last updated and nothing else.
        from workflow.measurement_report import (NAME_SHOWS_EVERY_UPDATE,
                                                 document_updated_stamps)
        stamps = document_updated_stamps(doc)
        if not NAME_SHOWS_EVERY_UPDATE:
            stamps = stamps[-1:]
        for when in stamps:
            bits.append(tr("updated {when}").format(
                when=str(when).replace("T", " ")[:19]))
        return " · ".join(bits)

    def _scope_tag(self, scope: str, entry: "dict | None" = None, *,
                   origin: str = "") -> str:
        """The date-scope flag of one name in "Report shown".

        Verification: "One date", "Multiple dates", "All dates" (B8-392).

        **PROFILING: "Run1", "Multiple runs", "All runs" (K26, Knut
        5792484060).** *"When run type is set to Profiling: The name tags
        become Run1, Run2, ..., then Multiple runs and All runs"*: a
        profiling run has one measurement, so its report is named after the
        run it covers. The run comes from what the report covers (its
        recorded measurements, else its files), or from *origin* for a file
        with no document block.
        """
        from workflow.measurement_report import (KIND_CALIBRATION,
                                                 KIND_PROFILING,
                                                 SCOPE_ALL_DATES,
                                                 SCOPE_MULTIPLE_DATES,
                                                 measurement_place)
        kind = self._window_kind()
        if kind == KIND_CALIBRATION:
            # **"Cal", "Multiple cals", "All cals" (#182 beta 39).** Knut,
            # 5794078008: *"The report names shall have tags 'Cal' (when only
            # one calibration), or 'Multiple cals' when more than one
            # included measurement across projects (but not all listed in
            # 'Included measurements...' list), or 'All cals' when all
            # measurement sets in 'Included measurements...' list are
            # included across projects for a report."* A project has ONE
            # calibration, so "one calibration" is one PROJECT covered; the
            # rest follows the scope the report recorded when it was made, as
            # "Multiple dates" and "All dates" do.
            places = self._entry_places(entry) if entry else set()
            if not places and origin:
                places = {measurement_place(origin)}
            if len({p for p, _r in places}) <= 1:
                return tr("Cal")
            return (tr("All cals") if scope == SCOPE_ALL_DATES
                    else tr("Multiple cals"))
        if kind != KIND_PROFILING:
            return (tr("All dates") if scope == SCOPE_ALL_DATES
                    else tr("Multiple dates") if scope == SCOPE_MULTIPLE_DATES
                    else tr("One date"))
        if scope == SCOPE_ALL_DATES:
            return tr("All runs")
        if scope == SCOPE_MULTIPLE_DATES:
            return tr("Multiple runs")
        places = self._entry_places(entry) if entry else set()
        if not places and origin:
            places = {measurement_place(origin)}
        runs = sorted({r for _p, r in places})
        if len(runs) == 1:
            return _run_tag(runs[0])
        return tr("Multiple runs") if len(runs) > 1 else tr("One date")

    def _document_key_of_report(self) -> str:
        """The document key of the file the page is drawn from, or ""."""
        r = self._report
        if not r:
            return ""
        origin = str(r.get("_origin_dir") or "")
        name = str(r.get("_report_file") or "")
        if not origin or not name:
            return ""
        from workflow.measurement_report import document_key_of
        return document_key_of(self._document_of(origin, name, r),
                               Path(origin) / "reports" / name)

    def _entry_the_list_lands_on(self, docs: list) -> str:
        """Which entry "Report shown" will name, as its key.

        **ONE ANSWER TO ONE QUESTION (R24-F1).** `_sync_saved_reports` decides
        this when it fills the pulldown, and `_open_on_the_latest_report` has
        to know the same thing to decide whether the window is in the "New
        report…" state: the window opened saying *"New report…"* over settings
        that were not its defaults, because only the pulldown knew where it had
        landed. A second copy of the rule in the other place is how they would
        drift apart again, so both ask this.

        The order is the pulldown's own: the loaded document if it is still
        listed, "New report…" if that is what is loaded, otherwise the file the
        page is drawn from, and "New report…" when nothing names anything.
        """
        want = self._loaded_doc_id
        if want == NEW_REPORT_KEY:
            return NEW_REPORT_KEY
        if any(d["key"] == want for d in docs):
            return want
        here = self._document_key_of_report()
        if here and any(d["key"] == here for d in docs):
            return here
        return NEW_REPORT_KEY

    def _tick_state(self) -> bool:
        """"Show detailed data for each run", as it stands.

        It used to be a pair. "Show all measurement runs" was removed with the
        feature behind it (B8-590), so one box is left and the document no
        longer records the other.
        """
        return bool(getattr(self, "_detail_check", None) is not None
                    and self._detail_check.isChecked())

    def _settings_of_one_saved_report(self, entry: dict) -> "dict | None":
        """The settings to restore for a report that records no document.

        Knut, 2026-09-18, on the per-dated-verification records ChromIQ writes
        by itself at measurement time: *"If the list of reports in 'Current
        Report Showing' have one report per dated verification (by default
        created during measurement), then each of those reports, when selecting
        one, should load and show with its report text in the window. And each
        of those will automatically have the settings updated to what was used
        when generating those reports (Correct report type, correct Judge
        Against used, 'Show all measurement runs' OFF (since it is only one
        date), etc.)"*

        **NOTHING IS INVENTED AND NOTHING IS WRITTEN.** The type and the limit
        set are read off the file, which has recorded both since 4.2.0; a file
        that recorded no set leaves the set pulldown where it is, because a
        wrong set is worse than the run's. The two tick boxes are the only part
        that is not on disk anywhere, and his sentence is what decides them:
        such a report is about ONE dated verification, so "Show all measurement
        runs" is off, and it carries no per-run breakdown, so is the other.
        """
        from workflow.measurement_report import (document_measurement_key,
                                                 recorded_compliance,
                                                 recorded_report_type)
        members = entry.get("members") or []
        if not members:
            return None
        r, name = members[0]
        rep: dict = r
        if str(r.get("_report_file") or "") != name:
            try:
                rep = json.loads(read_text(
                    Path(str(r.get("_origin_dir") or "")) / "reports" / name))
            except Exception:                        # noqa: BLE001
                return None
        # **WHAT THE FILE RECORDS, NOT WHAT IT DEFAULTS TO.** `report_type`
        # answers T2 for a file that chose nothing, and a document built on
        # that answer makes the window claim a choice nobody made: §10 says a
        # report with no type of its own follows the RUN it was written for.
        # Since K31 `_report_type_now` no longer asks the run for a NEW
        # report, so that legacy reading is made here, for this old file
        # only (`report_type_default_for`, the rule the list's label uses).
        tid = recorded_report_type(rep)
        if not tid:
            from workflow.run_compliance import (report_type_default_for,
                                                 run_context_for)
            ctx = run_context_for(Path(str(r.get("_origin_dir") or ""))
                                  / str(r.get("ti3") or "m.ti3"))
            if ctx is not None:
                tid = report_type_default_for(ctx.run, "", self._window_kind())
        return {
            "id": entry["key"],
            "created": str(rep.get("created") or ""),
            "type": tid,
            "compliance": recorded_compliance(rep),
            "detail": False,
            "measurements": [{
                "dir": str(r.get("_origin_dir") or ""),
                "created": str(r.get("created") or ""),
                "ti3": str(r.get("ti3") or ""),
                "key": document_measurement_key(
                    r.get("_origin_dir") or "", str(r.get("created") or ""),
                    str(r.get("ti3") or "")),
            }],
        }

    def _document_created_stamp(self, entry: dict) -> str:
        """When the DOCUMENT in *entry* was created, exactly as its NAME says.

        **B8-461.** Knut, beta 25: *"The report text updates, but the first
        line says 'Created: 2026-09-19 17:57:22', which is not the same
        creation time as the report name is giving. They should be the
        same."*

        The name is built in two places and this reads the same two sources, so
        the two cannot drift apart:

        * a document written since #182 carries its own ``created`` stamp in
          the document block, which is what `_saved_document_label` puts after
          "saved";
        * a report written before that is a document of one file, and
          `_saved_report_label` takes its "saved" stamp from the FILE NAME,
          which `save_report` writes with the second it saved. So does this.

        Returns "" when neither is available, and the caller then falls back to
        the window's own clock, which is the honest answer for a page that no
        saved document is behind.
        """
        doc = entry.get("doc")
        if isinstance(doc, dict) and str(doc.get("created") or ""):
            return str(doc.get("created"))
        members = entry.get("members") or []
        if len(members) == 1:
            _rank, when_saved, _n = _report_file_order(members[0][1])
            if _rank:
                day, _, clock = str(when_saved).partition("_")
                if day and clock:
                    return f"{day}T{clock.replace('-', ':')}"
        return ""

    def _forget_sticky_settings(self) -> None:
        """Drop the "what the controls were showing" pair (B8-462).

        Called wherever a DOCUMENT starts or stops speaking for the controls:
        from that moment the document itself is the answer, and a leftover pair
        from the last one would outrank it.
        """
        self._sticky_type = ""
        self._sticky_set = ""
        # the set an ISO type moved belongs to the document it was moved in
        self._set_before_iso_type = None

    def _document_settings(self) -> "dict | None":
        """The loaded document's own settings, while they are still what is on
        screen. `None` once the user has moved one of the controls."""
        if getattr(self, "_doc_settings_moved", False):
            return None
        return getattr(self, "_loaded_doc", None)

    def _document_limits(self):
        """The RunLimits the LOADED document was judged against, or None.

        The run is not asked and the run is not changed: this is the document's
        own record, restored so that the "Judged against" pulldown, the page
        under it and a report generated from here all say the same thing. It is
        dropped the moment the user moves a control (`_settings_touched`),
        which is what keeps it from becoming Knut's fifth defect in reverse.
        """
        doc = self._document_settings()
        if not doc:
            return None
        comp = doc.get("compliance") or {}
        sid = str(comp.get("set_id") or "")
        thr = comp.get("thresholds")
        if not sid or not isinstance(thr, dict):
            return None
        from workflow.compliance_sets import (SET_BY_ID, is_known_set,
                                              limits_from_json, set_label)
        from workflow.run_compliance import RunLimits
        known = is_known_set(sid)
        stored = str(comp.get("set_label") or "")
        return RunLimits(sid, set_label(sid, stored), limits_from_json(thr, sid),
                         label_en=(SET_BY_ID[sid].label if known
                                   else (stored or sid)),
                         bound=True, edited=bool(comp.get("edited")),
                         known=known)

    def _sticky_limits(self):
        """The RunLimits the "Judged against" pulldown was showing, or None.

        The mirror of `_report_type_now`'s sticky type, and the other half of
        B8-462: choosing a report TYPE drops the loaded document's claim, and
        without this the limit-set pulldown fell back to the run's set and
        moved under a user who had touched a different control. Nothing is
        read from the run and nothing is written.

        Only a set the user can still be shown is honoured; anything else falls
        through to the run, which is what the pulldown does with an unknown set
        anyway.
        """
        # **A REPORT ACROSS PLACES CAN HAVE LIMITS OF ITS OWN (#182 K30).**
        # Knut, 5798461562: *"I have specified ... that all settings belong
        # to a report, not a specific run"*. Numbers edited in the limits
        # window with several places loaded are the report's, held here for
        # the session, written into the document by Generate report and
        # never onto a run.
        #
        # **AND WITH ONE PROFILE RUN LOADED TOO (K31, B40-A 1).** This said
        # `and self._several_runs()`, the pre-K31 rule that one place's limits
        # were its run's (section 5). K31 gave every window the "This report"
        # column (§25.3), so with one run loaded an edit there showed on the
        # page and under the red line and was then dropped at Generate: the
        # file carried the set's plain numbers and ``edited: False``. Driven
        # on screen in `~/Desktop/ChromIQ-beta40-proof/challenge-A-behaviour/
        # d2b` (E1, E2, E4, E8).
        own = getattr(self, "_report_own_limits", None)
        if own is not None:
            return own
        sid = str(getattr(self, "_sticky_set", "") or "")
        if not sid:
            return None
        from workflow.compliance_sets import (SET_BY_ID, effective_limits,
                                              is_known_set)
        from workflow.run_compliance import RunLimits
        if not is_known_set(sid):
            return None
        # **AND THE RUN'S OWN COPY WINS WHENEVER IT IS THE SAME SET.** A bound
        # run holds a COPY of the set's numbers, which a user may have edited
        # in the limits window; rebuilding them from the set here would quietly
        # judge the page against the published numbers instead of the run's.
        # Sticky is only ever about the pulldown showing a DIFFERENT set from
        # the run, which is the only case it was added for.
        run_lim = self._window_limits()
        if run_lim is not None and run_lim.set_id == sid:
            return None
        return RunLimits(sid, tr(SET_BY_ID[sid].label),
                         effective_limits(sid, self._overrides()),
                         label_en=SET_BY_ID[sid].label, bound=False)

    def _delete_refusal_for(self, entry: dict) -> str:
        """Why this DOCUMENT may not be deleted, or "".

        The rule is unchanged and is applied to every file the document is made
        of: the only saved report of a dated verification is kept, because that
        verdict is this run's record of that date (§5).

        **A DOCUMENT WITH A DOCUMENT FILE IS NEVER REFUSED (K23).** Deleting
        it moves that one file (`_on_delete_report`); its verdict records stay
        in their dates' folders, so no date loses its verdict.
        """
        if entry.get("file"):
            return ""
        for r, name in (entry.get("members") or []):
            why = self._saved_delete_refusal(r, name)
            if why:
                return why
        return ""

    def _type_a_file_renders_as(self, rep: dict, r: dict) -> str:
        """The type a saved report is SHOWN as, for its entry's label.

        **ROUND 2B (2026-09-22), #1.** The label read `report_type(rep)`, which
        answers Full colour check for a file that records no type, while the
        page follows the RUN for such a file (§10) and, since K13, a profiling
        sheet's run type is the Printing record. So "Report shown" said Full
        colour check over a page and a pulldown saying Printing record. A file
        that records a type is labelled with it, as recorded; one that records
        none is labelled with what the page draws for it.
        """
        from workflow.measurement_report import (KIND_PROFILING,
                                                 KIND_VERIFICATION,
                                                 recorded_report_type)
        from workflow.run_compliance import (report_type_default_for,
                                             run_context_for)
        rec = recorded_report_type(rep)
        if rec:
            return rec
        origin, ti3 = r.get("_origin_dir"), r.get("ti3")
        ctx = (run_context_for(Path(str(origin)) / str(ti3))
               if origin and ti3 else None)
        kind = (None if ctx is None else
                KIND_VERIFICATION if ctx.verification is not None
                else KIND_PROFILING)
        return report_type_default_for(
            ctx.run if ctx is not None else None,
            str(self._settings.get("report_default_type", "") or ""), kind)

    def _saved_report_label(self, r: dict, name: str,
                            with_stamp: bool = False) -> str:
        """How one saved report is named in the selector.

        The measurement's date, then what the FILE says it is: its own report
        type and its own limit set, read off that file rather than off the run,
        because the whole point of the list is that a run may hold several
        reports of one measurement and they may differ (Knut, 2026-09-11).

        **AND WHEN IT WAS SAVED, WHICH IS THE ONLY THING THAT TELLS TWO OF THEM
        APART.** Driven on screen before it was added: the run in a tester's
        pack holds fifty reports of one measurement and forty-eight of them
        drew the identical line, *"2026-10-26 10:00 · Full colour check ·
        Custom ISO 12647-7"*. A list where a reader cannot tell which entry
        they are about to delete is not a selector. The stamp is the file's
        own, and where several share a second the number `save_report` gave
        them is on the end, because that is exactly the case it exists for.

        READ ONCE PER FILE, keyed by path and mtime. This is asked for every
        saved report of the run on every repaint, and a run can hold fifty
        reports of 19 kB each; re-reading a megabyte to redraw a pulldown that
        has not changed is the kind of cost that only shows up on somebody
        else's disk.
        """
        import json as _json
        from workflow.measurement_report import (recorded_compliance,
                                                 report_type, report_type_name)
        when = str(r.get("created") or "").replace("T", " ")[:16] or "?"
        path = Path(str(r.get("_origin_dir") or "")) / "reports" / name
        cache = getattr(self, "_label_cache", None)
        if cache is None:
            cache = self._label_cache = {}
        try:
            stamp = path.stat().st_mtime_ns
        except OSError:
            stamp = 0
        # THE KIND IS PART OF THE NAME (K26): the same file is "One date" on
        # a Verification window and "Run1" on a Profiling one.
        kind = self._window_kind()
        hit = cache.get((str(path), bool(with_stamp), kind))
        if hit is not None and hit[0] == stamp:
            return hit[1]
        rep = r
        if str(r.get("_report_file") or "") != name:
            try:
                rep = _json.loads(read_text(path))
            except Exception:                        # noqa: BLE001
                rep = {}
        bits = [when]
        try:
            bits.append(tr(report_type_name(self._type_a_file_renders_as(rep, r))))
        except Exception:                            # noqa: BLE001
            pass
        comp = recorded_compliance(rep)
        if comp:
            from workflow.compliance_sets import set_label
            bits.append(set_label(str(comp.get("set_id", "")),
                                  str(comp.get("set_label", ""))))
        # **A REPORT THAT HAS NEVER BEEN UPDATED CARRIES NO SECOND DATE
        # (B8-594).** Knut, 2026-09-20, on the eleven reports the demo pack
        # ships: *"each are showing both the created date in front, and the
        # saved date at the end. Only the create date should be included for
        # reports creation, and the trailing ' - Updated date time' should be
        # added only upon update of a report."*
        #
        # It is the rule he had already given for a report WITH a document
        # block (K.7d, §13.8: *"when a report created the first time the
        # trailing ' - saved <date> <time>' should not be added (created time
        # stamp already part of the beginning of the name)"*), and this branch
        # never got it, because a legacy file has no document block to record
        # an `updated` list in. So the question is asked of the two stamps the
        # file itself carries: a file whose name stamp is its creation stamp
        # has been written once and never rewritten.
        #
        # The stamp is NOT dropped outright, because the paragraph above is
        # still true: fifty reports of one measurement drew forty-eight
        # identical lines without it. It is dropped only where it says nothing
        # a reader does not already have on the front of the line.
        _rank, _when_saved, _n = _report_file_order(name)
        if _rank and with_stamp:
            # the stamp is `%Y-%m-%d_%H-%M-%S`; a person reads the date with
            # hyphens and the clock with colons
            day, _, clock = str(_when_saved).partition("_")
            saved = tr("saved {when}").format(
                when=f"{day} {clock.replace('-', ':')}")
            bits.append(saved if _n <= 1 else f"{saved} ({_n})")
        # **AND IT CARRIES ITS DATE FLAG LIKE EVERY OTHER REPORT (B8-595).**
        # Knut: *"non of the pre-created reports have the tag '(one date)',
        # which they should."* The modern branch of `_document_label` appends
        # one; this one never did, so the eleven reports the demo pack ships
        # were the only entries in the pulldown with no flag at all. A legacy
        # file is one file about one measurement, so the flag is a fact here
        # and not a guess, exactly as it is for the automatic measurement-time
        # report (§13.7 F.4).
        # K26: on a Profiling window the flag names the run (`_scope_tag`).
        from workflow.measurement_report import SCOPE_ONE_DATE
        bits.append(self._scope_tag(SCOPE_ONE_DATE,
                                    origin=str(r.get("_origin_dir") or "")))
        label = " · ".join(bits)
        cache[(str(path), bool(with_stamp), kind)] = (stamp, label)
        return label

    def _saved_delete_refusal(self, r: dict, name: str) -> str:
        """Why this report may not be deleted, or "".

        **THE ONLY SAVED REPORT OF A DATED VERIFICATION STAYS.** §5 of
        `docs/design/measurement_report_limits.md` exists so that every dated
        verification of a run is judged the same way and the dates stay
        comparable; that comparability IS the recorded verdict, and a date
        whose last report is gone has none. The window would then grade it live
        against today's numbers, which is the one thing the lock is there to
        prevent. Nothing in the model governs deletion, so this rule waits for
        approval with M-REPORT-DELETE.

        **AND IT IS ASKED OF THE FOLDER, NOT OF THE WINDOW'S OWN MEMORY.**
        `_all_report_files` is filled when the window gathers its sources and
        is refreshed only by `_reload_sources`, so the "is there a spare?"
        half of this rule used to be answered from a snapshot. Combined round
        2 drove two of these windows on one dated verification that really did
        hold two reports, deleted the spare in the second window, and then
        pressed Delete in the first WITHOUT touching its selector, which is
        the one action that would have re-read the folder. The first window
        still believed there was a spare, the refusal did not fire, and the
        date's `reports/` folder was left EMPTY: the verdict this rule exists
        to keep was gone, under a confirmation that said "One saved report of
        it is left afterwards".

        Nothing ships that way today, because every door that opens this
        window opens it with `exec()` and a person cannot have two of them at
        once. That is the only reason the snapshot was safe, and it was
        written down nowhere, so
        `tests/test_the_saved_report_delete_rule_is_decided_on_the_folder.py`
        pins it. A rule a design document calls binding should not rest on a
        modality by coincidence either, so the count is taken from the
        directory the delete is about to write in: the same path
        `_on_delete_report` builds. The session list stays as the fall-back
        for a folder that cannot be read, which is the answer this had before
        and is no worse than it was.

        **AND IT COUNTS THE FILES THE WINDOW CAN READ, NOT THE FILES THAT
        MATCH THE GLOB.** Combined round 3 drove the fix above and found that
        it had widened the rule it was tightening. `_gather_runs` reads every
        `report_*.json` with `json.loads` and SKIPS the ones that raise, so a
        file that is not readable JSON is in no row, in no selector and in no
        trend; the bare `glob` counted it as a spare all the same. Driven on
        screen on a dated verification holding one good report and one
        truncated one (`save_report` writes with `write_text`, which is not
        atomic, so a process killed mid-write leaves exactly that): Delete came
        up ENABLED with no reason beside it, the confirmation said *"0 saved
        reports of it are left afterwards"*, and the press left the date with
        no verdict the window can read. Photographed in
        `~/Desktop/ChromIQ-beta20-proof/combined-round-3/`
        (`G-one-readable-report-and-one-truncated-file.png`,
        `G-after-the-press.png`).

        The confirmation was honest there and the rule was not, which is the
        diagnostic: the two were counting different things. So the count uses
        the same test `_gather_runs` uses, and stops at two, because that is
        all this question needs to know.

        **AND A VERDICT RECORD IS NOT A SPARE (K31, B40-A 2).** The count
        took every readable file, so a record an earlier ChromIQ wrote into
        the date for a report of several dates (§25.6: never a report, never
        listed or counted) let the date's last own report go, and the record
        then became the date's row. Driven on screen in
        `~/Desktop/ChromIQ-beta40-proof/challenge-A-behaviour/d3` (X1-X4).
        So the count is of the date's own reports of one date
        (`_is_own_one_date_report`). A file this press would move that is
        not one of them (a copy a build before K23 wrote of a report of
        several dates) keeps the rule it had: refused only when it is the
        last file of the date that is not a record.
        """
        import json
        from core.file_manager import VERIFICATIONS_DIRNAME
        from workflow.measurement_report import is_verdict_record
        origin = Path(str(r.get("_origin_dir") or ""))
        if origin.parent.name != VERIFICATIONS_DIRNAME:
            return ""
        try:
            own: "list[str]" = []
            others = 0
            for p in sorted((origin / "reports").glob("report_*.json")):
                try:
                    rep = json.loads(read_text(p))
                except Exception:             # noqa: BLE001
                    continue                  # not a verdict; see below
                # the class, not `self`: the rule is asked without a window
                if MeasurementReportDialog._is_own_one_date_report(rep):
                    own.append(p.name)
                elif isinstance(rep, dict) and not is_verdict_record(rep):
                    others += 1
            if name in own or not name:
                spares = len(own)
            else:
                spares = 2 if own else others
        except OSError:                       # unreadable: the answer it gave
            spares = len(r.get("_all_report_files") or [])
        if spares > 1:
            return ""
        return tr("The only saved report of a dated verification is kept: its "
                  "verdict is this run's record of that date.")

    def _own_place(self, ctx=None) -> "tuple[str, str] | None":
        """``(project, run)`` of the window's own profile run, by folder
        name (`measurement_place`), or None outside a run."""
        from workflow.measurement_report import measurement_place
        if ctx is None:
            ctx = self._context_run()
        if ctx is None or getattr(ctx, "run", None) is None:
            # A CALIBRATION WINDOW'S OWN PLACE is its calibration (#182 beta
            # 39): (project, "cal").
            if self._is_calibration_window():
                own = self._own_cal_dir()
                return measurement_place(own) if own is not None else None
            return None
        return measurement_place(ctx.run.dir)

    def _entry_places(self, entry: dict) -> "set[tuple[str, str]]":
        """Every ``(project, run)`` one entry of "Report shown" COVERS (K25).

        What the document RECORDS it covers (its measurements' folders), and
        the folders of the files it is made of; by folder NAME, so a moved
        project (every downloaded demo pack) groups the same as it did where
        it was written. Knut: a report is grouped by *"what a report
        includes"*, which is the recorded list, not only the measurements this
        window happens to have loaded.
        """
        from workflow.measurement_report import (measurement_place,
                                                 resolve_recorded_folder)
        recorded = [str(m.get("dir") or "")
                    for m in ((entry.get("doc") or {}).get("measurements")
                              or [])
                    if isinstance(m, dict)]
        # **SEEN FROM WHERE THE REPORT'S FILES ARE (#182 beta 38, F2).** The
        # recorded folders carry the project's name when the report was
        # written; after a rename that is its OLD name, and a renamed Finder
        # duplicate's every report read as covering two projects (its own
        # files, and its original's name) and was filed under "Reports
        # including multiple projects".
        homes = self._entry_homes(entry)
        one = self._records_one_project(recorded)
        dirs = [str(resolve_recorded_folder(d, homes, one_project=one,
                                            must_exist=False) or d)
                for d in recorded if d]
        dirs += [str(r.get("_origin_dir") or "")
                 for r, _n in (entry.get("members") or [])]
        return {measurement_place(d) for d in dirs if d}

    @staticmethod
    def _entry_homes(entry: dict) -> "list[Path]":
        """The project folders one entry of "Report shown" has FILES in: its
        members' folders and its document file, asked of the disk
        (`project_home_of`), first seen first (#182 beta 38, F2)."""
        from workflow.measurement_report import project_home_of
        paths = [str(r.get("_origin_dir") or "")
                 for r, _n in (entry.get("members") or [])]
        if entry.get("file"):
            paths.append(str(entry["file"]))
        out: "list[Path]" = []
        for p in paths:
            h = project_home_of(p) if p else None
            if h is not None and h not in out:
                out.append(h)
        return out

    @staticmethod
    def _records_one_project(recorded_dirs) -> bool:
        """Whether a report's recorded folders all name ONE project."""
        from workflow.measurement_report import _project_folder_of
        names = set()
        for d in recorded_dirs or []:
            if not d:
                continue
            proj = _project_folder_of(Path(str(d)))
            names.add(proj.name if proj is not None else "")
        return len(names) == 1

    def _grouped_documents(self, run, docs: list) -> list:
        """The rows of "Report shown" below "New report…", in order (K25).

        ``[("heading", text, tooltip, level)]`` and ``[("entry", doc)]``.

        Knut, 2026-09-23 (5789263863 and 5789532633): the report NAMES stay
        ("One date", "Multiple dates", "All dates"), and the list is grouped
        by where the included measurements come from:

        ==========================================  ============================
        the measurements in "Included measurements"  headings
        ==========================================  ============================
        one profile run                              none, as before
        several runs of one project                  Run1, Run2, ...
        several projects                             the project, then Run1, ...
        ==========================================  ============================

        and *"IF a report has included multiple measurements belonging to
        more than one project, then those reports are grouped in a separate
        group-heading ... 'Reports including multiple projects'"*.

        **THE LIST DECIDES WHETHER THERE ARE HEADINGS; THE REPORT DECIDES
        WHICH ONE IT IS UNDER.** Whether the list is grouped is his first
        sentence, about the measurements ADDED (`_measurement_dirs_of_the_
        list`, the folders the list and the counter already read). Where one
        report goes is what it covers (`_entry_places`): one run, under that
        run; several runs of one project, under that project's "Reports
        including multiple runs" (not in his text; asked, B8-826); more than
        one project, under "Reports including multiple projects", last.

        Projects: the window's own first, the others by name. Runs in number
        order (run2 before run10). Inside a group, the order `docs` already
        has: newest first.
        """
        import re as _re
        from workflow.measurement_report import measurement_place
        kind = self._window_kind()
        listed = {measurement_place(d)
                  for d in self._measurement_dirs_of_the_list(run, kind)}
        # **AND WHAT THE OFFERED REPORTS COVER (K26, Knut 5792576954).**
        # *"'Report shown' should be grouped from the start, because one of
        # the reports it offers covers two profile runs."* The list stayed
        # flat while "Included measurements in report" held one run's
        # measurements, and grouped only once such a report was selected and
        # had loaded the other run. The reports offered now count as well.
        offered: "set[tuple[str, str]]" = set()
        for d in docs:
            offered |= self._entry_places(d)
        from workflow.measurement_report import KIND_CALIBRATION
        if len(listed | offered) <= 1 or not docs:
            # **A LONE PROJECT CARRIES ITS HEADING UNDER CALIBRATION (#182
            # K30).** Asked (spec 18.12) whether a Calibration window whose
            # list holds one project should name it, Knut answered *"ok"*
            # (5798461562). A calibration has no run to head it, so its
            # reports sit under the project's name, as they do beside other
            # projects. Profiling and Verification keep K25's rule: one run,
            # no headings.
            places = listed | offered
            if kind == KIND_CALIBRATION and docs and len(places) == 1:
                proj = next(iter(places))[0]
                return ([("heading", proj, proj, 0)]
                        + [("entry", d) for d in docs])
            return [("entry", d) for d in docs]
        own = self._own_place() or next(iter(sorted(listed)))
        MULTI_RUNS, MULTI_PROJECTS = "\x00runs", "\x00projects"
        buckets: "dict[tuple[str, str], list]" = {}
        for d in docs:
            places = self._entry_places(d) or {own}
            projects = {p for p, _r in places}
            if len(projects) > 1:
                key = ("", MULTI_PROJECTS)
            elif len(places) > 1:
                key = (next(iter(projects)), MULTI_RUNS)
            else:
                key = next(iter(places))
            buckets.setdefault(key, []).append(d)
        projects = sorted({k[0] for k in buckets if k[1] != MULTI_PROJECTS}
                          | {p for p, _r in listed | offered},
                          key=lambda p: (p != own[0], p.casefold()))
        several_projects = len(projects) > 1 or (
            ("", MULTI_PROJECTS) in buckets)

        def _run_order(name: str):
            m = _re.fullmatch(r"run(\d+)", name)
            return (0, int(m.group(1)), "") if m else (1, 0, name.casefold())

        _run_heading = _run_tag
        # **A CALIBRATION WINDOW GROUPS BY PROJECT ONLY (#182 beta 39).**
        # Knut, 5794078008: *"The 'Report shown' dropdown list should then
        # group the reports (that include one measurement) with
        # group-headings according to the project name the measurements and
        # reports belong to. And reports with multiple measurements included
        # (across projects) are grouped under 'Reports including multiple
        # projects'."* A project has one calibration, so there is no run to
        # put under the project: its reports go straight under its name.
        from workflow.measurement_report import KIND_CALIBRATION
        calibration = kind == KIND_CALIBRATION

        out: list = []
        sub = 1 if several_projects else 0
        for proj in projects:
            runs = sorted((k[1] for k in buckets
                           if k[0] == proj and k[1] not in (MULTI_RUNS,
                                                            MULTI_PROJECTS)),
                          key=_run_order)
            if not runs and (proj, MULTI_RUNS) not in buckets:
                continue
            if several_projects:
                out.append(("heading", proj, proj, 0))
            for r in runs:
                if not calibration:
                    out.append(("heading", _run_heading(r),
                                f"{proj}/runs/{r}", sub))
                out.extend(("entry", d) for d in buckets[(proj, r)])
            if (proj, MULTI_RUNS) in buckets:
                out.append(("heading", tr("Reports including multiple runs"),
                            proj, sub))
                out.extend(("entry", d) for d in buckets[(proj, MULTI_RUNS)])
        if ("", MULTI_PROJECTS) in buckets:
            out.append(("heading", tr("Reports including multiple projects"),
                        "", 0))
            out.extend(("entry", d) for d in buckets[("", MULTI_PROJECTS)])
        return out

    @staticmethod
    def _add_report_group_heading(combo, text: str, tooltip: str,
                                  level: int) -> None:
        """One non-selectable heading row in "Report shown" (K25).

        **THE CREATE CHART PRESET PULLDOWN'S MECHANISM, as Knut asked** (*"the
        group-headings are the same type of feature that the preset pulldown
        list has"*): `TabChart._add_builtin_group_heading` puts a separator
        before a group and a bold row with no data whose model item is
        disabled, so it can be read and not chosen, and it carries no key, so
        nothing can dispatch on it even if selection were ever re-enabled.

        A sub-heading (a run under a project) is the same row, indented, and
        gets no separator of its own: the separator marks where a PROJECT
        starts, which is what a reader scanning the list needs to find.
        """
        if level == 0:
            combo.insertSeparator(combo.count())
        combo.addItem(("    " * level) + text, None)
        i = combo.count() - 1
        font = combo.font()
        font.setBold(True)
        combo.setItemData(i, font, Qt.ItemDataRole.FontRole)
        if tooltip:
            combo.setItemData(i, tooltip, Qt.ItemDataRole.ToolTipRole)
        model = combo.model()
        item = model.item(i) if hasattr(model, "item") else None
        if item is not None:
            item.setEnabled(False)

    def _sync_saved_reports(self, run) -> None:
        """Fill the list of generated reports, and say what may be pressed.

        ONE ENTRY PER DOCUMENT (B8-383). This filled a pulldown with one entry
        per FILE, which is why one press of Generate report appeared to add two
        reports: it wrote one file per measurement and the list counted them.
        """
        combo = getattr(self, "_saved_combo", None)
        if combo is None:
            return
        docs = self._saved_documents(run)
        want = self._loaded_doc_id
        grouped: list = []
        combo.blockSignals(True)
        try:
            combo.clear()
            # **"NEW REPORT…" IS THE FIRST ROW AND IS NEVER THE SELECTED ONE
            # BY DEFAULT (B8-388).** Knut: *"'New report...' should be at the
            # top of the list in the pulldown"*, and, in the same breath, *"The
            # default when loading the Measurement Report window is the latest
            # report created."* So it sits where he put it and
            # `_open_on_the_latest_report` decides what is on screen.
            combo.addItem(tr("New report…"), NEW_REPORT_KEY)
            combo.setItemData(
                0, tr("Start a new report from the defaults in Preferences ▸ "
                      "Reports. The report shown stays on the page, and "
                      "nothing is written, until you press Generate report."),
                Qt.ItemDataRole.ToolTipRole)
            # **GROUPED BY WHERE THE MEASUREMENTS COME FROM (K25).** Knut,
            # 2026-09-23: the names stay, *"but are grouped according to which
            # measurement sets have been added, where they come from, and
            # what a report includes"*. `_grouped_documents` decides; a
            # heading is the Create Chart preset pulldown's kind of row
            # (`_add_report_group_heading`), and it carries no key, so nothing
            # can land on it or dispatch on it.
            grouped = self._grouped_documents(run, docs)
            for row in grouped:
                if row[0] == "heading":
                    _k, text, tip, level = row
                    self._add_report_group_heading(combo, text, tip, level)
                    continue
                d = row[1]
                combo.addItem(d["label"], d["key"])
                combo.setItemData(combo.count() - 1, d["label"],
                                  Qt.ItemDataRole.ToolTipRole)
            # THE DOCUMENT DECIDES, NOT THE LIST'S LAST STATE — the rule the
            # pulldown already carried, and the reason is unchanged: after
            # "Generate report" the page moves to the new document and a
            # selector left on the old one puts two halves of one window in
            # disagreement in front of the reader (Knut, beta 20). With no
            # document loaded it follows the file the page is drawn from, so
            # the list names what the reader is looking at.
            #
            # The rule itself lives in `_entry_the_list_lands_on`, because
            # `_open_on_the_latest_report` has to know the same answer and a
            # second copy of it is exactly how the window came to say "New
            # report…" over settings that were not its defaults (R24-F1).
            lands = self._entry_the_list_lands_on(docs)
            # BY KEY, NEVER BY POSITION (K25): headings sit between the
            # entries, so "its place in `docs` plus one" is no longer its row.
            # Nothing matched and the new-report state both land on row 0.
            i = combo.findData(lands) if lands else -1
            combo.setCurrentIndex(i if i >= 0 else 0)
        finally:
            combo.blockSignals(False)
        # **THE ROW STAYS ON SCREEN WITH NOTHING IN IT (L.9).** The pulldown
        # hid itself and every widget beside it when a run had saved no report,
        # which saved 42 px and left a user with no way of knowing the list was
        # there at all. Knut: *"The window needs to show clearly that a user
        # should select a report in the list to show/load a previously
        # generated report. IF the list is empty, then the user could also be
        # informed to Click Generate Report to create the first report."*
        # ALWAYS LIVE, because "New report…" is in it even when no report has
        # been generated: a disabled pulldown would put the defaults out of
        # reach of the one run that most needs them.
        self._saved_combo.setEnabled(True)
        if not docs:
            self._saved_label.setText(tr("Report shown:"))
            self._set_saved_hint(tr("No report has been generated yet. Click "
                                    "“Generate report” to create the first "
                                    "one."))
            self._set_saved_note("")
            self._delete_report_btn.setEnabled(False)
            return
        # A GROUPED LIST IS NOT ONE RUN'S (K25), so the label stops naming
        # one: its headings say which run each report belongs to.
        is_grouped = any(row[0] == "heading" for row in grouped)
        self._saved_label.setText(
            tr("Report shown ({run}):").format(run=run.dir.name)
            if run is not None and not is_grouped else tr("Report shown:"))
        entry = self._chosen_document(docs)
        why = self._delete_refusal_for(entry) if entry else ""
        # ONE LINE, AND THE REFUSAL IS THE ONE WORTH READING. A reader who is
        # being told why a button is dead does not need to be told, on the line
        # above, that they may click an entry.
        self._set_saved_hint("" if why else
                             tr("Click a report to load it here with the "
                                "settings it was made with."))
        # NOTHING SELECTED IS NOT "NOTHING IN THE WAY". Driven on screen: the
        # last report of a profiling measurement deleted, the pulldown empty,
        # and Delete still live over a list with nothing in it.
        self._delete_report_btn.setEnabled(bool(entry and not why))
        self._set_saved_note(why)

    def _wrap_beside_the_pulldown(self, label, full: str) -> None:
        """Put *full* on the line beside "Report shown", wrapped to THREE lines.

        **K32 (Knut on beta 41, #182 5815133233): THREE LINES, THEN "…".**
        *"The text field should always wrap to up to 3 lines (since there is
        space for this vertically), and if still not enough space for the
        text, then end text with "..." as usual."* It was capped at two, and
        a label fitted to two lines at one width was sometimes drawn at a
        narrower one on three, its first and last lines cut by the two-line
        height. The cap is `_BESIDE_PULLDOWN_LINES`; the height is pinned to
        it, so a third line is drawn whole, and `resizeEvent` fits the text
        again once the layout has given the label its new width.

        **KNUT, BETA 26 (B8-524).** *"To the right of the Report shown and its
        help icon, there is a text 'The only saved report of a dated....'. This
        text is cut off and the window must be far too wide to see the whole
        text. It is better that the text is wrapped down to a second line, and
        then horizontally centred agains the Report shown input dropdown box,
        so that the text is always aligned."*

        Two things, and the second is already built: `side_col` carries a
        stretch above and below this row, so whatever height it takes is
        centred on the pulldown's own line. A one-line sentence and a two-line
        one therefore sit on the same axis, which is his *"always aligned"*.

        What is new is the wrap, and it is capped at two lines ON PURPOSE. A
        word-wrapped `QLabel` asks for whatever height its text needs at a
        width the layout has not decided yet, and that is what pushed this
        window's bottom off an 800 px screen twice (see `_type_blurb`). So the
        height is pinned to two lines, the text is shortened until it fits
        them, and the whole sentence stays in the tooltip as it always has.
        """
        from PyQt6.QtGui import QFontMetrics
        fm = QFontMetrics(label.font())
        two = _BESIDE_PULLDOWN_LINES * fm.lineSpacing() + 2
        # **THE ROOM IS THE LABEL'S OWN WIDTH ONCE IT HAS ONE**, and the
        # window's only before the first layout. `_set_saved_note` measured
        # `self.width() - label.x() - 40` because a label's width is zero
        # before the layout has run -- true, and wrong the moment it is not:
        # this label shares its row with a second label and a stretch, so the
        # layout gives it far less than the window has left, and a sentence
        # fitted to the window's room wraps to THREE lines in the label.
        # Photographed on screen at 1480 px with the two-line cap already in
        # place: the third line was clipped in half and drawn over the row
        # above it.
        room = label.width() if label.width() > 20 else max(
            160, self.width() - label.x() - 40)
        label.setWordWrap(True)
        label.setMaximumHeight(two)
        label.setMinimumHeight(0)

        # **ASK THE WIDGET, NOT THE FONT.** A `QFontMetrics.boundingRect` over
        # the label's width said two lines while the label drew THREE and
        # clipped the last one: this label carries a stylesheet
        # (`_faint_label_css`), so its own padding comes off the width before
        # the text is laid out, and the font metric knows nothing about that.
        # `QLabel.heightForWidth` is the label's own answer and includes it.
        # Photographed both ways before this line was written.
        def _fits(text: str) -> bool:
            label.setText(text)
            return label.heightForWidth(room) <= two

        if _fits(full):
            label.setToolTip(full)
            return
        # The longest prefix that still fits two lines, found by halving rather
        # than by trimming a character at a time: this runs on every resize.
        lo, hi = 0, len(full)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if _fits(full[:mid] + "…"):
                lo = mid
            else:
                hi = mid - 1
        label.setText(full[:lo].rstrip() + "…")
        label.setToolTip(full)

    def _set_saved_note(self, full: str) -> None:
        """Why Delete is refused, on one line, with the whole of it as tooltip.

        Same treatment `_type_blurb` gets, and for the reason given there: a
        word-wrapped label of its own is what pushed this window's bottom off
        an 800 px screen, twice.

        **THE ROOM IS THE WINDOW'S, NOT THE LABEL'S.** The first cut measured
        `self._saved_note.width()`, which is nothing at all before the layout
        has run, so the sentence elided to a floor of 120 px and a driver
        photographed a greyed-out Delete with no reason beside it at all: the
        exact shape of the faults this project has spent a beta fixing, a
        refusal a reader cannot act on. `_set_type_blurb` measures the window
        and the label's x, and `resizeEvent` asks both of them again.
        """
        self._saved_note_full = full or ""
        if not full:
            self._saved_note.setText("")
            self._saved_note.setToolTip("")
            self._saved_note.setVisible(False)
            return
        self._saved_note.setVisible(True)
        # TWO LINES, CENTRED ON THE PULLDOWN (B8-524). This is the label Knut
        # photographed cut off: *"The only saved report of a dated…"* is the
        # Delete refusal, and it is the longer of the two sentences that share
        # this row.
        self._wrap_beside_the_pulldown(self._saved_note, full)

    def _set_generate_why(self, full: str) -> None:
        """Why Generate is greyed, on its own row under the buttons (C6).

        The tooltip alone is a reason nobody sees until they hover over a
        dead button. It first sat beside the buttons, cut to two lines, and
        that left four to six words of it on screen (re-challenge R2, #10);
        it now has the window's width and is shown whole, wrapped.
        """
        self._generate_why_full = full or ""
        label = getattr(self, "_generate_why", None)
        if label is None:
            return
        if not full:
            label.setText("")
            label.setToolTip("")
            label.setVisible(False)
            return
        # THE WHOLE SENTENCE, NEVER SHORTENED (re-challenge R2, #10): the
        # label has its own full-width row now, so it wraps instead of being
        # cut to two lines with an ellipsis.
        label.setWordWrap(True)
        label.setMaximumHeight(16777215)
        label.setText(full)
        label.setToolTip(full)
        label.setVisible(True)

    def _set_saved_hint(self, full: str) -> None:
        """What to do with the list (L.9), on one line, whole text as tooltip.

        Knut: *"The window needs to show clearly that a user should select a
        report in the list to show/load a previously generated report. IF the
        list is empty, then the user could also be informed to Click Generate
        Report to create the first report."*

        THE ROOM IS THE WINDOW'S, NOT THE LABEL'S, exactly as `_set_saved_note`
        measures it: a label's own width is nothing at all before the layout has
        run, and eliding against it is how a driver came to photograph a greyed
        button with no reason beside it.
        """
        self._saved_hint_full = full or ""
        hint = getattr(self, "_saved_hint", None)
        if hint is None:
            return
        # A HIDDEN LABEL CLAIMS NO SPACE AND AN EMPTY ONE CLAIMS A LINE. This
        # row is beside a list box that is already the tallest thing above the
        # document, and only one of these two lines ever has anything to say.
        if not full:
            hint.setText("")
            hint.setToolTip("")
            hint.setVisible(False)
            return
        hint.setVisible(True)
        self._wrap_beside_the_pulldown(hint, full)

    def _chosen_document(self, docs: list) -> "dict | None":
        """The document entry the list is on, or None."""
        combo = getattr(self, "_saved_combo", None)
        if combo is None:
            return None
        key = combo.currentData()
        return next((d for d in docs if d["key"] == key), None)

    def _chosen_pair(self, choices: list) -> tuple:
        """The (row, file name) the list is on, or (None, "").

        Kept because three callers and a driver ask this window "which saved
        report is picked", and the answer is still a file: a document of one
        file answers with it, and a document of several answers with the file
        of the measurement the page is drawn from, which is the one a reader
        would name.
        """
        docs = self._saved_documents(self._run_ctx.run if self._run_ctx else None)
        entry = self._chosen_document(docs)
        if entry is None:
            return (None, "")
        subject = self._run_key(self._report) if self._report else None
        for r, name in entry["members"]:
            if subject and self._run_key(r) == subject:
                return (r, name)
        return entry["members"][0] if entry["members"] else (None, "")

    def _on_saved_chosen(self, _index: int) -> None:
        """A generated report was picked: bring THAT document back (L.2).

        Knut, 2026-09-18: *"When I select a report in the 'saved reports'
        dropdown, the report window does not seem to update according to the
        selected report"* and *"Changing selected report in the saved report
        pulldown does not change any of the other settings that the selected
        report had when it was generated."* (B8-381, B8-382.)

        Measured before this, with every entry picked in turn: the selection
        stuck and the rendered document's SHA-256 did not move. It could not:
        an entry named one FILE of one measurement, the window was already
        drawing that measurement's newest file, and nothing in this path ever
        wrote to the type pulldown, the limit-set pulldown or the tick boxes.
        """
        if self._syncing_limits:
            return
        combo = getattr(self, "_saved_combo", None)
        key = str((combo.currentData() if combo is not None else "") or "")
        if not key or key == self._loaded_doc_id:
            return
        # `activated` follows this signal for a USER's pick; it must not
        # load the same document a second time (`_on_saved_picked_again`).
        self._pick_just_loaded = key
        QTimer.singleShot(0, self._forget_the_pick)
        if key == NEW_REPORT_KEY:
            self._start_new_report(chosen=True)
            return
        self._load_document(key)

    def _forget_the_pick(self) -> None:
        self._pick_just_loaded = ""

    def _on_saved_picked_again(self, _index: int) -> None:
        """The user picked the entry the list was ALREADY on (R24-F1).

        `currentIndexChanged` never fires for it, so "New report…" over a
        window already showing "New report…" was a control with no effect --
        and that is precisely the window this fault leaves a user in. Only
        that case is handled here: a pick that moves the index is
        `_on_saved_chosen`'s, and doing it twice would load the same document
        twice.
        """
        if self._syncing_limits:
            return
        combo = getattr(self, "_saved_combo", None)
        key = str((combo.currentData() if combo is not None else "") or "")
        if not key:
            return
        if getattr(self, "_pick_just_loaded", "") == key:
            # `currentIndexChanged` has just loaded it for this very pick.
            self._pick_just_loaded = ""
            return
        # **AND AN ENTRY THE WINDOW DOES NOT HOLD IS LOADED TOO (C5).** This
        # returned when the entry was not the loaded report, which is the
        # one state in which a click on it is needed most: the list named a
        # report the page was not showing, and picking it did nothing.
        if key == NEW_REPORT_KEY:
            self._start_new_report(chosen=True)
        else:
            self._load_document(key)

    def _defaults_document(self) -> dict:
        """The settings a NEW report starts from, in a document's own shape.

        Knut, 2026-09-18 (B8-388): *"when 'Report shown' is set to 'New
        report....', all default values shall be loaded on the settings, which
        then can be changed by a user. The default values are fetched from the
        preferences->reports tab."*

        IT IS A DOCUMENT-SHAPED RECORD AND NOT A SECOND CODE PATH. The window
        already has one answer to "what settings is the page drawn with": the
        loaded document (`_document_settings`), read by `_report_type_now`, by
        `_document_limits` and by `_sync_limit_controls`. Writing the defaults
        into the type and set PULLDOWNS instead would be two answers to one
        question, and `_on_type_chosen` would store the default on the RUN,
        which is a write to a user's disk that nobody asked for.

        **`compliance` IS DELIBERATELY None**, which is what makes "Judged
        against" fall through to the starting choice (`_document_limits`
        returns None, `_sync_limit_controls` shows `lim`). That IS the default
        (K31, Knut 5801677743): the Preferences default set, unless the
        profile run has a default of its own chosen in Edit limits, which then
        wins (`run_compliance.run_limits`).
        """
        ctx = self._run_ctx
        s = self._settings
        return {
            "id": "new",
            "created": "",
            # **NO TYPE IS PINNED HERE.** `_report_type_now` answers a new
            # report with the Preferences default fitted to the kind (K31),
            # which is the same rule one step later.
            "type": "",
            "compliance": None,
            "detail": bool(s.get("report_default_show_details", True)),
            "measurements": [],
        }

    def _start_new_report(self, *, chosen: bool = False) -> None:
        """"New report…" was chosen: load the Preferences defaults (B8-388).

        Nothing on disk is read, written, deleted or renamed by this: it is the
        state the window is in before a document exists, made reachable again
        from the list. The user may then change anything, and Generate report
        writes a NEW document, which is Knut's K.1 (*"It is better that
        existing reports are not overwritten"*) unchanged.

        **K39-3 (Knut, #182 5831246553): CHOSEN BY THE READER, IT DOES NOT
        CHANGE THE REPORT ON THE PAGE.** *"Selecting "New report…" will not
        change whatever report is currently visible, but loads the default
        settings for "New report…", and should then also show a red text
        message telling user to modify settings as desired and then press
        Generate Report to apply and make a new report. Generate Report will
        then update the viewed report on screen."* So with *chosen* (a pick
        in "Report shown", by mouse or keyboard) and a report on the page,
        the defaults go into the controls and the list, the page and its
        graphs are kept (`_keeping_the_page`), and the red line says
        M-REPORT-NEW-REPORT-SETTINGS until a report is drawn. The doors that
        must replace the page (a delete that took the report shown, a
        Generate that found its report gone) pass no *chosen* and draw, as
        before. Choosing the previous report again loads it with its own
        stored settings (`_load_document`), which is his last sentence.
        """
        keep = chosen and self._page_shows_a_report()
        if keep:
            self._new_report_pending = True
            with self._keeping_the_page():
                self._enter_the_new_report()
            return
        self._enter_the_new_report()

    def _enter_the_new_report(self) -> None:
        """The body of `_start_new_report`: the defaults, the rows picked
        again, and the repaint (which `_keeping_the_page` may hold)."""
        self._drop_borrowed_sources()        # recheck R1
        self._load_the_defaults()
        # A NEW REPORT IS ABOUT THE NEWEST FILE OF EACH MEASUREMENT, so the
        # document a click left behind stops choosing which file is drawn.
        had_choices = bool(self._chosen_reports)
        self._chosen_reports.clear()
        self._hidden_runs = set()
        # **AND THE ROWS ARE PICKED AGAIN (B40-A 4).** Which file a row is
        # drawn from is decided when the folders are read
        # (`_one_row_per_measurement`), so clearing the choice alone left
        # every row on the file the previous report had chosen: after an old
        # report of several dates had been loaded, a date's row stayed that
        # report's verdict record under "New report…" (d3 run.log 381).
        if had_choices and self._sources:
            self._reread_sources()
            self._rebuild_from_sources()     # repaints, through `_refresh`
            return
        # The rows follow, through `_refresh` (B8-521).
        self._refresh()

    def _load_the_defaults(self) -> None:
        """Put the Preferences defaults on screen, WITHOUT repainting.

        The one place the "New report…" state is entered from, because there
        are two doors into it and they had drifted apart (R24-F1): choosing the
        entry did this, and OPENING a window that lands on the same entry did
        not, so the pulldown said *"New report…"* over settings that were not
        its defaults. `_start_new_report` adds what a CHOICE means on top of
        it (the chosen files and the unticked rows are forgotten) and repaints;
        `_open_on_the_latest_report` runs inside `_rebuild_from_sources`, which
        repaints straight afterwards.
        """
        doc = self._defaults_document()
        self._loaded_doc_id = NEW_REPORT_KEY
        self._loaded_doc = doc
        self._doc_settings_moved = False
        # NOTHING IS LOADED, so the "Created:" line is this window's own clock
        # and the controls answer for themselves again (B8-461, B8-462).
        self._doc_created = ""
        self._forget_sticky_settings()
        # "New report…" IS THE PREFERENCES DEFAULT (#182 beta 39 for a
        # calibration, K31 for every window): a type chosen earlier in this
        # window is the choice of the report it was chosen for, not of the
        # next one, and `_report_type_now` then asks Preferences. The limit
        # set follows the same rule through `_forget_sticky_settings` and the
        # report's own numbers below.
        self._session_type = ""
        self._report_own_limits = None
        # K36-1: an ISO type starts on an ISO set
        try:
            self._hold_the_set_to_the_type()
        except Exception:                                # noqa: BLE001
            log.debug("could not hold the set to the type", exc_info=True)
        chk = getattr(self, "_detail_check", None)
        if chk is not None:
            chk.blockSignals(True)
            chk.setChecked(bool(doc.get("detail")))
            chk.blockSignals(False)

    def _open_on_the_latest_report(self) -> None:
        """The window opens on the latest report created (B8-388), once.

        Knut, asked whether "New report…" is selected when a run has none:
        *"I have specified this earlier. The default when loading the
        Measurement Report window is the latest report created. 'New report...'
        should be at the top of the list in the pulldown."*

        So the top entry is not the selected one: the newest DOCUMENT is, with
        the settings it was made with, which is the same sentence he wrote
        about the automatic record (*"when the Measurement window appears, the
        latest report shall load automatically with its settings"*). A run that
        has generated nothing has no report to open on, and then the defaults
        are what a new report starts from.

        NO REPAINT OF ITS OWN: `_rebuild_from_sources` calls this and then
        repaints, so the page is drawn once, with these settings already on it.
        """
        if getattr(self, "_opened_on_a_report", False):
            return
        ctx = self._context_run()
        docs = self._saved_documents(ctx.run if ctx is not None else None)
        if not self._history:
            # Nothing is loaded yet (the window was built empty and is about to
            # be given a measurement). Ask again when there is something to ask
            # about, rather than deciding on an empty list.
            return
        self._opened_on_a_report = True
        # **ONLY A REPORT THAT RECORDS WHAT IT IS**, and that is about WHICH
        # entry this door lands on, not about which settings come with it.
        # "The latest report created" is a DOCUMENT: it carries the settings it
        # was made with, so loading it with them is reading a fact off the
        # file. A report written before the document record existed carries
        # none of that, so this door leaves it to `_entry_the_list_lands_on`,
        # which is the pulldown's own rule, and to `_adopt_visible_document`,
        # which follows the file the page is drawn from. Both of those now
        # restore all five settings (B8-490), which is the half of P.10 that
        # was missing; which entry each door lands on is unchanged, and R24-F1
        # — a window whose list lands on "New report…" holding its defaults —
        # still works because this can still fall through to it.
        #
        # **WHAT IS DELIBERATELY NOT BUILT HERE.** Knut's beta-25 comment also
        # says, twice, that *"the latest created report is by default selected
        # in 'Report shown'"* whatever it records. That sentence sits inside
        # the storage/naming ruling that is held (which folder a report lives
        # in, the report_profiling / report_verification tags, Delete moving a
        # report to old/date_ReportId), and moving this door onto it would
        # change which report a window opens on for every project made before
        # this beta. It is B8-492, open, and it is his to settle with the rest
        # of that ruling.
        #
        # **THE WINDOW'S OWN RUN FIRST (K25).** A Profiling window now lists
        # every run's Printing records (Knut, 5789263863), so "the newest
        # document" may be another run's: a window opened on run 1 would come
        # up on run 2's report, which is the fault that kept other runs out of
        # the list until now (measured again with this change: a window opened
        # on run 2 came up on run 1's report, ticked run 1 only, and Generate
        # wrote run 1's folder). The newest document covering the window's
        # own run is what "the latest report created" means for that window.
        # A run with none opens exactly as it did when the other runs were not
        # listed at all: on "New report…" with its defaults.
        own = self._own_place(ctx)
        if own is not None:
            docs = [d for d in docs if own in self._entry_places(d)]
        first = next((d for d in docs if d.get("doc")), None)
        if first is not None:
            self._apply_document(first)
            return
        # **AND A WINDOW WHOSE LIST LANDS ON "NEW REPORT…" IS IN THAT STATE,
        # SO IT HOLDS ITS DEFAULTS (R24-F1).** This returned here whenever the
        # run had saved reports at all, and only the empty case below loaded
        # the defaults -- while the pulldown, which has its own rule, showed
        # *"New report…"* for every project whose saved reports name no entry
        # the page is drawn from. So the window claimed a state it was not in,
        # over settings nobody had chosen, and Knut's B8-388 sentence (*"when
        # 'Report shown' is set to 'New report....', all default values shall
        # be loaded on the settings"*) was true of one door and not the other.
        #
        # The list is asked rather than second-guessed, so the two cannot
        # disagree again. A project whose newest file IS named by an entry
        # opens exactly as it did: none of those settings is imposed on it,
        # which is what B8-388 decided deliberately for reports that record
        # none of their own.
        #
        # Nothing on disk is read differently for any of this.
        if self._entry_the_list_lands_on(docs) != NEW_REPORT_KEY:
            return
        self._load_the_defaults()

    def _load_document(self, key: str) -> None:
        """Show the document *key* names, with the settings it was made with.

        NOTHING IS REGENERATED AND NOTHING IS WRITTEN (L.2). Every setting
        restored here is read out of the document's own files; the run is not
        asked, and the run is not told. A report that carries no document block
        (one saved by an earlier ChromIQ) restores what it does record, which is
        its own file, and leaves the controls where they are rather than
        inventing settings it never kept.
        """
        docs = self._saved_documents(self._run_ctx.run if self._run_ctx else None)
        entry = next((d for d in docs if d["key"] == key), None)
        if entry is None:
            return
        self._apply_document(entry)
        self._reload_sources()

    def _apply_document(self, entry: dict) -> None:
        """Put *entry*'s settings on screen, WITHOUT repainting.

        Split out of `_load_document` so that the window OPENING on the latest
        report (B8-388) can use the one code path a click uses and still draw
        the page once: `_open_on_the_latest_report` runs inside
        `_rebuild_from_sources`, which repaints immediately afterwards.
        """
        key = entry["key"]
        if self._drop_borrowed_sources(keep_for=entry):
            again = next((d for d in self._saved_documents(
                self._run_ctx.run if self._run_ctx else None)
                if d["key"] == key), None)
            if again is not None:
                entry = again
        # **A DOCUMENT IS SHOWN WHOLE, OR IT IS NOT SHOWN AS ITSELF (the
        # challenge round before beta 37, A-F1).** A document in
        # `<project>/reports` covering run1's 2026-12-15 and run2's
        # 2026-12-22, opened from run2's window, came up with 12-22 alone
        # ticked and "1 verification run" on the page; Generate then asked
        # "Nothing was changed for the selected report", and Update rewrote it
        # about one date and retired the file that covered two. So the
        # measurements it records that this window has not loaded are loaded
        # now, before anything is drawn. The several-places rule then greys
        # Generate with its reason, the page shows the whole report, and
        # nothing can be rewritten narrower than it is.
        if self._load_the_documents_other_measurements(entry):
            self._history = sorted(
                (r for s in self._sources for r in s["runs"]),
                key=lambda r: str(r.get("created") or ""))
            self._project_dirs = {s["dir"] for s in self._sources}
            again = next((d for d in self._saved_documents(
                self._run_ctx.run if self._run_ctx else None)
                if d["key"] == key), None)
            if again is not None:
                entry = again
        self._loaded_doc_id = key
        doc = entry["doc"] or self._settings_of_one_saved_report(entry)
        self._loaded_doc = doc
        self._doc_settings_moved = False
        self._doc_created = self._document_created_stamp(entry)
        self._doc_sources = self._source_signature()
        self._forget_sticky_settings()
        # **THE REPORT'S OWN LIMITS ARE THIS REPORT'S, NOT THE LAST ONE'S
        # (beta 40 second check, finding 1).** Numbers typed into "This
        # report" for one report and never generated stayed in
        # `_report_own_limits`; picking another report and ticking any control
        # made `_sticky_limits` hand them back, and Update wrote them into the
        # other report as `edited: True`. A report loaded here brings its own:
        # the numbers it was saved with when they were edited, nothing
        # otherwise (so a later touch keeps an edited report's numbers too).
        doc_lim = self._document_limits()
        self._report_own_limits = (
            doc_lim if doc_lim is not None and doc_lim.edited else None)
        # WHICH FILE OF EACH MEASUREMENT THE PAGE IS DRAWN FROM. Only the
        # document's own measurements are chosen: every other row is its
        # date's own report, so what the previous report chose goes first
        # (B40-A 4: a record it chose stayed a date's row after it).
        self._chosen_reports.clear()
        for r, name in entry["members"]:
            self._chosen_reports[self._run_key(r)] = name
        # THE SUBJECT IS ONE OF ITS OWN MEASUREMENTS, the newest of them, so
        # that with "Show all measurement runs" off the page is about a sheet
        # this document is actually about.
        if entry["members"]:
            self._report = max((r for r, _n in entry["members"]),
                               key=lambda r: str(r.get("created") or ""))
        self._restore_the_documents_view(
            doc, recorded=bool(entry.get("doc")),
            covers={self._run_key(r) for r, _n in entry["members"]})
        # The type and the limit set follow from `_loaded_doc`: they are read
        # back by `_report_type_now` and `_sync_limit_controls`, which the
        # repaint the caller runs. Setting the two combos here as well would be
        # two answers to one question, and this window has paid for that before.

    def _drop_borrowed_sources(self, keep_for: "dict | None" = None) -> bool:
        """Unload the measurements a selected report pulled in (recheck R1,
        before beta 37).

        `_load_the_documents_other_measurements` loads what a report covers
        so it is shown whole; nothing unloaded them, so a run whose newest
        report covered two runs opened with the other run's measurement in the
        list and Generate greyed, and it stayed so through "New report…" and
        every other report until Clear List. They belong to that report only,
        and leave with it. A source the user added is never touched.
        """
        borrowed = getattr(self, "_borrowed_sources", set())
        if not borrowed:
            return False
        # **NOT THE ONES THE REPORT BEING OPENED IS ABOUT (GAP 0).** A
        # Verification window on run 2 that opened on a report across run 2
        # and run 1 has run 1's dates borrowed; picking run 1's own "One date"
        # report dropped them first, so the picked report was no longer in
        # the list: "Report shown" landed on another entry while the page
        # showed the picked report's date, and Generate wrote a NEW report
        # without asking (K4). Such a source now belongs to *keep_for*.
        needed: "set[str]" = set()
        for r, _n in ((keep_for or {}).get("members") or []):
            if r.get("_origin_dir"):
                needed.add(str(Path(str(r["_origin_dir"]))))
        still = {t for t in borrowed if str(Path(t).parent) in needed}
        keep = [src for src in self._sources
                if str(src.get("ti3")) not in borrowed
                or str(src.get("ti3")) in still]
        dropped = len(keep) != len(self._sources)
        self._borrowed_sources = set(still)
        if dropped:
            self._sources = keep
            self._history = sorted(
                (r for src in self._sources for r in src["runs"]),
                key=lambda r: str(r.get("created") or ""))
            self._project_dirs = {src["dir"] for src in self._sources}
            log.info("unloaded the measurements the previous report covered")
        return dropped

    def _load_the_documents_other_measurements(self, entry: dict) -> int:
        """Load every measurement *entry*'s document records that is not in
        the list yet; the number loaded (A-F1, before beta 37).

        The document's own list is the answer to "what does it cover", named
        from the project down (`project_relative`) so a moved project finds
        the same folders. A folder that no longer holds its measurement is
        left out rather than guessed at.
        """
        from workflow.measurement_report import (_project_folder_of,
                                                 project_relative)
        block = entry.get("doc") if isinstance(entry, dict) else None
        wanted = (block or {}).get("measurements") or []
        if len(wanted) < 2:
            return 0
        # **BY PROJECT AND FOLDER, NOT BY FOLDER ALONE (K25).** A report
        # across two PROJECTS names `runs/run1` in each, and comparing from
        # `runs/` down alone took the other project's `runs/run1` for this
        # one's: measured on the demo pack, a Printing record across two
        # projects loaded nothing of the second, and a verification report
        # across them looked for the second project's date inside the first.
        from workflow.measurement_report import measurement_place

        def _ident(d) -> tuple:
            return (measurement_place(d)[0], project_relative(d))
        loaded = {_ident(r.get("_origin_dir") or "")
                  for r in self._history if r.get("_origin_dir")}
        # **WHERE THE REPORT'S OWN FILES ARE DECIDES WHOSE ITS FOLDERS ARE
        # (#182 beta 38, F2).** This used to take the recorded project's NAME
        # and look beside the window's project for a folder of that name. A
        # renamed Finder duplicate's reports record its ORIGINAL's name, and
        # the original sits right beside it, so the copy's window loaded the
        # original's measurements (8 rows, 5 of them the original's). A
        # recorded folder is now this project's when the name is one this
        # project has had (`names_of_project`), or the report names only one
        # project and is filed here; another project's only when the report
        # names that project and it is not this one.
        from workflow.measurement_report import resolve_recorded_folder
        homes = self._entry_homes(entry)
        if not homes:
            for r in self._history:
                if r.get("_origin_dir"):
                    project = _project_folder_of(Path(str(r["_origin_dir"])))
                    if project is not None:
                        homes = [project]
                        break
        one = self._records_one_project(
            [str(m.get("dir") or "") for m in wanted])
        added = 0
        for m in wanted:
            d, name = str(m.get("dir") or ""), str(m.get("ti3") or "")
            if not d or not name:
                continue
            folder = resolve_recorded_folder(d, homes, one_project=one)
            if folder is None:
                log.info("a report covers %s, which this project does not "
                         "have", d)
                continue
            if _ident(folder) in loaded:
                continue
            ti3 = folder / name
            if not ti3.is_file():
                # **THE FILE CARRIES THE PROJECT'S NEW NAME TOO (F2).** A
                # rename renames the measurement with the folder, and the
                # report recorded it under the old stem: the renamed copy's
                # "12-30 Multiple dates" found run 2's date and not its file.
                from workflow.measurement_report import renamed_file_name
                alt = renamed_file_name(name, d, folder)
                if alt is not None:
                    ti3 = folder / alt
            if not ti3.is_file():
                log.info("a report covers %s, which is not on disk", ti3)
                continue
            try:
                if self._append_source(ti3, origin=ti3):
                    added += 1
                    loaded.add(_ident(folder))
                    self._borrowed_sources.add(str(ti3))
                    log.info("loaded %s: the selected report covers it", ti3)
            except Exception as exc:                  # noqa: BLE001
                log.warning("could not load %s for the selected report: %s",
                            ti3, exc)
        return added

    def _restore_the_documents_view(self, doc: "dict | None", *,
                                    recorded: bool = True,
                                    covers: "set[str] | None" = None) -> None:
        """Put *doc*'s two tick boxes and its measurement ticks on screen.

        **THIS IS KNUT'S BETA-25 RULING, AND IT OVERRULES B8-388 (B8-490).**
        Asked whether opening a saved report should restore its two tick boxes
        as well as its type and limit set, he answered, 2026-09-19:

        > *"Yes. All settings that belong to a report shall be loaded.
        > Included measurements added for report is ticked, Report type, Judged
        > against, and 'Show all measurement runs' and 'Show detailed data for
        > each run'."*

        So there are FIVE settings, one answer, and one place that writes the
        three of them that are not pulldowns. Every door into a document calls
        this: a CLICK in the list (`_apply_document`), the window OPENING on a
        report (`_open_on_the_latest_report`), and the page moving to a
        document by itself (`_adopt_visible_document`, after Generate).

        **AND THE MEASUREMENT LIST NO LONGER WAITS FOR "Show all measurement
        runs".** It was re-ticked only when that box was ON, so a report made
        about ONE measurement came back with every row of the run's history
        ticked — the list said the report covered three sheets while the page
        under it described one. His first named item is *"Included
        measurements added for report is ticked"*, which is a statement about
        the LIST and not about the box above it.

        **`recorded=False` IS THE ONE NARROWING, AND IT IS DELIBERATE.** A
        report written before the document record existed lists no
        measurements, and `_settings_of_one_saved_report` does not read one off
        it: it INFERS, from Knut's own sentence, that such a report is about
        the one dated verification it was filed in. That inference is sound
        enough to decide two tick boxes, which are a view and which he named
        one by one. It is not sound enough to UNTICK rows, which is a filter
        that survives the view: on every project made before this beta, every
        window would open with the run's history narrowed to one sheet, and
        "Show all measurement runs" would then have one run to show. So the
        two tick boxes follow such a report and the list is left as it is,
        and a report that really records its measurements restores them
        exactly — including when "Show all measurement runs" is OFF, which is
        the case that was missing (B8-430 records it as left for Knut).

        Nothing is written to disk by any of this, and nothing is repainted:
        the caller repaints, once, with these settings already on screen.
        """
        if not doc:
            return
        chk = getattr(self, "_detail_check", None)
        if chk is not None:
            chk.blockSignals(True)
            chk.setChecked(bool(doc.get("detail")))
            chk.blockSignals(False)
        if not recorded:
            # **A LEGACY REPORT NOW TICKS ITS OWN MEASUREMENT TOO (B8-596).**
            # Knut, 2026-09-20: *"when ever I select any of the reports in the
            # drop down, the 'included measurements in report' always have all
            # measurements ticked. This is wrong. … only one measurement date
            # should be showing then I select one of the reports … One the
            # measurement used in the selected report shall be ticked."*
            #
            # This branch used to return here and leave the ticks alone, and
            # the paragraph above says why: a report with no document block
            # does not LIST its measurements, and inferring one was judged
            # sound enough to decide two tick boxes but not to untick rows,
            # because unticking would have left "Show all measurement runs"
            # with one run to show on every project made before beta 22.
            #
            # That argument died with the box (B8-590). A report now covers
            # exactly what is ticked, so a selected report whose ticks say
            # something else is lying about itself. And the list is not
            # inferred here: `entry["members"]` is which measurements this
            # pulldown entry was built from, gathered by `_saved_documents`
            # from the files on disk, so it is a fact about the report and not
            # a guess about the folder it sits in.
            if covers:
                here = {self._run_key(r) for r in self._history}
                if covers & here:
                    self._hidden_runs = here - covers
            return
        keys = {str(m.get("key") or "")
                for m in (doc.get("measurements") or [])}
        here = {self._run_key(r) for r in self._history}
        # A document whose recorded list is empty cannot say which rows were
        # ticked, so the rows are left as they are rather than all unticked.
        #
        # **AND NEITHER CAN ONE WHOSE EVERY RECORDED MEASUREMENT IS ABSENT
        # (R29-F3).** A measurement's identity in that list is
        # `document_measurement_key`, which begins with the measurement's
        # ABSOLUTE folder, so a project that has MOVED — copied to another
        # machine, restored from a backup, or found under a different output
        # folder — records keys that match nothing here. Measured: the same
        # project opened in place hid 1 row of 2 and drew the page; opened from
        # a copy at another path it hid 2 of 2, drew nothing at all, and left
        # "Generate report" disabled, with no sentence anywhere saying why.
        # Hiding everything is not a narrower view of the report, it is an
        # empty window, so the same rule as the empty list applies: a document
        # that names no row that is here cannot say which rows were ticked.
        # A document that names SOME of them still narrows to those.
        #
        # **AND A MOVED DOCUMENT STILL KNOWS ITS OWN FILES (K15).** The rule
        # above stopped the empty window and left a moved report with every
        # row ticked, which is the fault B8-596 fixed for a report with no
        # block: a "One date" report whose list says eleven. Every project a
        # user downloads has moved, the demo pack first among them, so this
        # was the state every one of its saved reports opened in. `covers` is
        # which measurements carry a FILE of this document, read off the disk
        # by `_saved_documents`, so it is right wherever the project now lives
        # and is the same set the recorded keys named before the move.
        #
        # **AND FIRST, THE SAME MEASUREMENTS NAMED FROM THE PROJECT DOWN
        # (K23, B8-810 R3A-2).** The file fallback below reads which
        # measurements carry a file of this document, and a measurement an
        # Update took OUT still carries one (it keeps its verdict), so a
        # narrowed document came back wider once the project had moved, and
        # an Update then put the date back. The recorded list is the truth
        # about what the document covers; only its absolute folder went
        # stale, so it is compared from `runs/` down before anything else.
        # **AND ONE MOVED PROJECT AMONG SEVERAL IS FOUND WHERE IT IS NOW
        # (re-challenge R1, beta 39, #6).** The rule below maps the recorded
        # keys only when NONE of them matched, so a report across two
        # projects of which one moved (into a sub-folder of the ChromIQ
        # folder, §24.4) ticked the project that stayed and left the moved
        # one's date unticked: the page covered 1 of 2, with no note. Each
        # recorded key that matches nothing is read the way the window
        # loaded it (`resolve_recorded_folder`) and matched by folder and
        # creation stamp.
        if keys - here:
            keys = keys | self._recorded_keys_where_they_are_now(
                keys - here, here, covers)
        if not (keys & here) and keys:
            from workflow.measurement_report import relative_measurement_key
            rel = {relative_measurement_key(k) for k in keys}
            moved = {h for h in here if relative_measurement_key(h) in rel}
            if moved:
                keys = moved
        if not (keys & here) and covers and (covers & here):
            keys = set(covers)
        # **AND A REPORT WHOSE OWN MEASUREMENTS ARE ALL GONE TICKS NOTHING
        # (second check R3, beta 39, B8-925).** "Names no row that is here"
        # left every row ticked, and with every verification of a report
        # removed from disk those rows were the run's PROFILING sheets: the
        # list showed them ticked under a verification report, and an Update
        # then covered them. The rule above is for a report whose
        # measurements are on disk somewhere this window did not match; one
        # whose every recorded measurement is gone has nothing here to tick.
        if keys and here and not (keys & here) \
                and self._documents_own_are_gone(doc, covers, here):
            log.info("none of the selected report's measurements is on "
                     "disk; no row of the list is ticked under it")
            self._hidden_runs = set(here)
            return
        self._hidden_runs = (here - keys) if (keys & here) else set()
        # The caller repaints, and `_refresh` is what draws the rows (B8-521).

    def _documents_own_are_gone(self, doc, covers, here) -> bool:
        """Whether EVERY measurement *doc* records is gone from disk
        (`update_losses`, read from the projects of *covers* and *here*, as
        `_recorded_keys_where_they_are_now` reads them). False when it
        records none or the question cannot be answered. Never raises."""
        from workflow.measurement_report import project_home_of, update_losses
        try:
            recorded = [m for m in ((doc or {}).get("measurements") or [])
                        if isinstance(m, dict) and m.get("dir")]
            if not recorded:
                return False
            homes: "list[Path]" = []
            for k in list(covers or ()) + list(here or ()):
                h = project_home_of(str(k).split("|", 1)[0])
                if h is not None and h not in homes:
                    homes.append(h)
            return len(update_losses(recorded, [], homes)) >= len(recorded)
        except Exception:                              # noqa: BLE001
            return False

    def _recorded_keys_where_they_are_now(self, missing, here,
                                          covers=None) -> "set[str]":
        """The keys of *here* that the recorded keys *missing* name, read
        through `resolve_recorded_folder` from the projects the document's
        files are in (*covers*, else the loaded rows). Never raises."""
        from workflow.measurement_report import (project_home_of,
                                                 resolve_recorded_folder)
        try:
            homes: "list[Path]" = []
            for k in list(covers or ()) + list(here):
                h = project_home_of(str(k).split("|", 1)[0])
                if h is not None and h not in homes:
                    homes.append(h)
            # A report across projects, which is the only kind with a key
            # that matches nothing while others match: never rule 2.
            one = False
            by_place: "dict[tuple[str, str], str]" = {}
            for h in here:
                parts = str(h).split("|")
                if len(parts) >= 3:
                    by_place[(os.path.realpath(parts[0]), parts[1])] = h
            out: "set[str]" = set()
            for k in missing:
                parts = str(k).split("|")
                if len(parts) < 3 or not parts[0]:
                    continue
                folder = resolve_recorded_folder(parts[0], homes,
                                                 one_project=one)
                if folder is None:
                    continue
                hit = by_place.get((os.path.realpath(str(folder)), parts[1]))
                if hit is not None:
                    out.add(hit)
            return out
        except Exception:                              # noqa: BLE001
            log.debug("could not place the recorded measurements",
                      exc_info=True)
            return set()

    def _reload_sources(self) -> None:
        """Read every loaded measurement's reports off disk again.

        The one way back from a change to what is ON DISK, which is what a
        delete is. `_rebuild_from_sources` only re-reads what `_gather_runs`
        already put in `self._sources`, so on its own it would redraw the
        window from the file that has just been removed.
        """
        self._reread_sources()
        self._rebuild_from_sources()
        # The disk moved under the list; the entry it now names is loaded.
        self._load_what_the_list_names()

    def _reread_sources(self) -> None:
        """Gather every loaded measurement's rows off disk again, keeping the
        subject; nothing is drawn (`_reload_sources`, `_start_new_report`)."""
        subject = self._run_key(self._report) if self._report else None
        for src in self._sources:
            try:
                name, runs = self._gather_runs(Path(src["ti3"]))
            except Exception as exc:                 # noqa: BLE001
                log.warning("could not re-read %s: %s", src.get("ti3"), exc)
                continue
            src["name"], src["runs"] = name, runs
            src["stamp"] = self._disk_stamp(src.get("ti3"))
        rows = [r for s in self._sources for r in s["runs"]]
        self._report = next(
            (r for r in rows if subject and self._run_key(r) == subject),
            rows[-1] if rows else self._report)

    def _on_delete_report(self) -> None:
        """Move the selected document's files into an ``old/`` folder (L.7).

        Knut, 2026-09-18: *"Having this list, also requires a 'Delete Selected
        Report' button, so that it is possible to remove reports a user does
        not want in the list, which then creates a dated report folder in the
        old/ folder where the files for that report is moved to."* With three
        destinations, decided by what the document spans:
        :func:`workflow.measurement_report.document_old_dir` holds the rule and
        its docstring quotes him on each of the three.

        **NOTHING IS DESTROYED.** This used to `unlink` the one file the
        pulldown named. It now moves every file of the document, and a file
        that cannot be moved leaves the rest where they are: a half-moved
        document is a document that is in neither place.
        """
        from datetime import datetime as _dt
        from ui.warning_sign import warn
        from workflow import measurement_messages as M
        from workflow.measurement_report import document_old_dir
        ctx = self._run_ctx
        docs = self._saved_documents(ctx.run if ctx else None)
        entry = self._chosen_document(docs)
        if entry is None:
            return
        if self._delete_refusal_for(entry):
            # A REFUSAL A READER CANNOT SEE IS A BUTTON THAT DOES NOTHING.
            # The refusal asks the FOLDER, so it can fire on a row whose button
            # is still live because the window has not re-read the folder
            # since. The window catches up with the disk and re-draws the row,
            # which greys the button and puts the reason beside it in the words
            # the row already uses.
            self._reload_sources()
            return
        members = entry.get("members") or []
        paths = [Path(str(r.get("_origin_dir") or "")) / "reports" / name
                 for r, name in members]
        dest = document_old_dir([p.parent.parent for p in paths], _dt.now())
        doc_file = entry.get("file")
        if doc_file:
            # **A DOCUMENT OF SEVERAL MEASUREMENTS (K23) MOVES ITS DOCUMENT
            # FILE, AND ONLY THAT.** Its verdict records are the dates' own
            # results, "not a report" (Knut, 2026-09-23), and they stay. The
            # destination is L.7's, read off where the file lives:
            # `verifications/reports/` -> `verifications/old/<stamp>/`, and
            # `<project>/reports/` -> `<project>/old/<stamp>/`. Asked of the
            # file and not of the recorded folders, which name where the
            # project USED to be when it has moved.
            doc_file = Path(str(doc_file))
            paths = [doc_file]
            dest = (doc_file.parent.parent / "old"
                    / _dt.now().strftime("%Y-%m-%d_%H%M%S"))
        if dest is None:
            return
        title, body = M.CATALOGUE["M-REPORT-DELETE"].render(
            what=entry.get("label", ""), n=len(paths), where=str(dest))
        if not self._confirm(title, body):
            return
        # ALL OR NOTHING, AND IN WORDS (challenge C, beta 39, #7): a
        # read-only folder left the report in old/ AND in the list, under a
        # raw "[Errno 13]". `move_report_files` moves every file or none.
        from core.file_manager import move_report_files
        moved, stuck = move_report_files(paths, dest)
        if stuck is not None:
            log.warning("the report was not moved to %s: %s cannot be "
                        "changed", dest, stuck)
            # THE REMEDY FOLLOWS WHERE THE REPORT LIVES (re-challenge R2,
            # #8): "copy the project" is no remedy for a report across
            # projects, which lives beside them and not in any one.
            warn(self, *M.CATALOGUE["M-REPORT-DELETE-FAILED"].render(
                folder=str(stuck),
                remedy=M.report_delete_remedy(paths[0] if paths else stuck)))
            self._reload_sources()
            return
        for path, target in zip(paths, moved):
            log.info("report moved to old/: %s -> %s", path, target)
        for r, name in members:
            key = self._run_key(r)
            if self._chosen_reports.get(key) == name:
                self._chosen_reports.pop(key, None)
        was_loaded = self._loaded_doc_id == entry["key"]
        if was_loaded:
            self._loaded_doc_id = ""
            self._loaded_doc = None
            self._doc_created = ""
            # **THE SETTINGS THAT MOVED BELONGED TO THE REPORT THAT IS GONE
            # (challenge C, C5).** A flag left up here kept
            # `_adopt_visible_document` from taking the entry the list then
            # landed on, so "Report shown" named a report the page was not
            # showing: nothing loaded, Generate greyed, the PDF offered in
            # the wrong folder under a now-stamp, and a click on the same
            # entry did nothing because the index did not move.
            self._doc_settings_moved = False
        self._reload_sources()
        if was_loaded:
            # **AND THE ENTRY IT LANDS ON IS LOADED THROUGH THE ONE DOOR A
            # CLICK USES**, whole (its other measurements included, A-F1),
            # or "New report…" with its defaults. Adopting it from the page
            # alone left a report across runs shown with one run.
            self._load_what_the_list_names(force=True)

    def _load_what_the_list_names(self, *, force: bool = False) -> None:
        """Make the window hold the entry "Report shown" names (C5).

        **ONE INVARIANT: THE SHOWN ENTRY IS THE LOADED REPORT, OR "NEW
        REPORT…" WITH ITS DEFAULTS.** The pulldown is filled by
        `_entry_the_list_lands_on`, which falls back to the file the page is
        drawn from when the loaded report has gone; what is loaded is
        `_loaded_doc_id`. When the two disagree, the entry wins, because it
        is what the reader sees and what a click would load. *force* loads
        the entry even when the ids agree (after a delete, where the id was
        adopted from the page without the report's other measurements).
        """
        if getattr(self, "_reconciling_the_list", False):
            return
        combo = getattr(self, "_saved_combo", None)
        if combo is None:
            return
        key = str(combo.currentData() or "")
        loaded = str(self._loaded_doc_id or "")
        if not force and key == loaded:
            return
        self._reconciling_the_list = True
        try:
            if not key or key == NEW_REPORT_KEY:
                if force or loaded != NEW_REPORT_KEY:
                    self._start_new_report()
            else:
                self._load_document(key)
        finally:
            self._reconciling_the_list = False

    def _window_kind(self) -> "str | None":
        """What kind of measurement this window is about, for K13.

        The SUBJECT decides (the measurement the window was opened on), and
        it is asked the same way the automatic report asks: its run context.
        A dated verification is "verification", a run's own sheet is
        "profiling", a project's calibration is "calibration" (#182 beta 39),
        and anything else with no run (a file outside any project) is None,
        which keeps every type.
        """
        from workflow.measurement_report import (KIND_PROFILING,
                                                 KIND_VERIFICATION)
        from workflow.run_compliance import run_context_for
        # **THE PROFILE BAR DECIDES (K24).** Knut, 2026-09-23: *"The open
        # measurement window strictly shows and lists and counts report types
        # that are allowed according to the set 'run type' in the profile
        # bar."* The measurement the window was opened on decided before, so
        # adding a profiling sheet to a Verification window flipped it and
        # Printing records were listed. The measurement is asked only when
        # there is no bar to ask (a window with no main window behind it).
        found, bar = self._bar_kind()
        if found:
            return bar
        r = getattr(self, "_report", None) or {}
        origin, ti3 = r.get("_origin_dir"), r.get("ti3")
        if not origin or not ti3:
            return None
        # A PROJECT'S CALIBRATION is its own kind (#182 beta 39), asked the
        # way the automatic report asks it: the folder, on disk.
        from workflow.measurement_report import (KIND_CALIBRATION,
                                                 is_calibration_dir)
        if is_calibration_dir(origin):
            return KIND_CALIBRATION
        ctx = run_context_for(Path(origin) / str(ti3))
        if ctx is None:
            return None
        return KIND_VERIFICATION if ctx.verification is not None \
            else KIND_PROFILING

    def _bar_kind(self) -> "tuple[bool, str | None]":
        """``(found, kind)`` from the profile bar's Run type, looked up
        through the window's parents; ``(False, None)`` when there is no bar.

        **CALIBRATION IS A KIND OF ITS OWN (#182 beta 39, Knut 5794078008).**
        It used to answer None ("every type"), and beta 38 then locked the
        window (K26); now it is KIND_CALIBRATION: every type but the Printing
        record, from the calibration folders' reports."""
        from core.measurement_target import (RUN_TYPE_CALIBRATION,
                                             RUN_TYPE_PROFILING,
                                             RUN_TYPE_VERIFICATION)
        from workflow.measurement_report import (KIND_CALIBRATION,
                                                 KIND_PROFILING,
                                                 KIND_VERIFICATION)
        p = self.parent()
        while p is not None:
            ctl = getattr(p, "_target_ctl", None)
            target = getattr(ctl, "target", None) if ctl is not None else None
            rt = getattr(target, "run_type", None)
            if isinstance(rt, str) and rt:
                return True, (KIND_VERIFICATION if rt == RUN_TYPE_VERIFICATION
                              else KIND_PROFILING if rt == RUN_TYPE_PROFILING
                              else KIND_CALIBRATION
                              if rt == RUN_TYPE_CALIBRATION else None)
            p = p.parent() if hasattr(p, "parent") else None
        return False, None

    def _kinds_are_mixed(self) -> bool:
        """True when the loaded measurements include both a profiling sheet
        and a dated verification (final round FC-2)."""
        from workflow.run_compliance import run_context_for
        kinds = set()
        # **ONLY WHAT IS TICKED (challenge 2 of beta 42, #1c).** A press
        # writes the ticked measurements and nothing else
        # (`_reports_to_generate`), so an unticked sheet of the other kind
        # cannot put one type into both kinds of folder, which is all FC-2
        # refuses. Counting it greyed Generate the moment the project's own
        # profiling sheet was added to a verification window, unticked as
        # K32 adds it.
        hidden = getattr(self, "_hidden_runs", set()) or set()
        for r in getattr(self, "_history", None) or []:
            if self._run_key(r) in hidden:
                continue
            origin, ti3 = r.get("_origin_dir"), r.get("ti3")
            if not origin or not ti3:
                continue
            try:
                ctx = run_context_for(Path(str(origin)) / str(ti3))
            except Exception:                        # noqa: BLE001
                ctx = None
            if ctx is not None:
                kinds.add(ctx.verification is not None)
            if len(kinds) > 1:
                return True
        return False

    def _fit_to_kind(self, tid: str) -> str:
        """*tid*, or the kind's own default when the kind does not allow it."""
        from workflow.measurement_report import report_types_for_kind
        kind = self._window_kind()
        if tid in report_types_for_kind(kind):
            return tid
        from workflow.run_compliance import report_type_default_for
        return report_type_default_for(
            None, str(self._settings.get("report_default_type", "") or ""),
            kind)

    def _report_type_now(self) -> str:
        """Which kind of document this window is producing.

        **K31: THE TYPE IS THE REPORT'S.** The loaded report's own type while
        it speaks for the controls; the type chosen in this window; and for a
        new report the Preferences > Reports default, fitted to the
        measurement's kind (`new_report_type`). A run's stored type (D9, the
        pulldown wrote it until K31) is no longer a starting choice, so two
        runs loaded together can no longer disagree about it. A measurement in
        no project keeps the type it was last saved as, failing that today's
        report.
        """
        from workflow.measurement_report import (REPORT_TYPE_DEFAULT,
                                                 REPORT_TYPES, report_type)
        # **WHAT THE PAGE ON SCREEN WAS BUILT WITH, while a PDF of that page is
        # being built (R23-F1).** Set only inside `_as_the_document_was_built`
        # and always cleared in its `finally`; empty at every other moment, so
        # nothing else in the window can see it.
        forced = getattr(self, "_type_as_built", "")
        if forced in REPORT_TYPES:
            return forced
        # **A LOADED DOCUMENT ANSWERS FOR ITSELF (B8-382, L.2).** Its own files
        # say what kind of document they are, and that is what the page is
        # drawing, so the pulldown must say it too. The RUN is not asked and the
        # run is not changed; the claim lasts exactly as long as the user leaves
        # the controls alone (`_settings_touched` drops it).
        doc = self._document_settings()
        if doc:
            tid = str(doc.get("type") or "")
            if tid in REPORT_TYPES:
                return tid
        # **AND WHEN THE DOCUMENT'S CLAIM WAS DROPPED, WHAT WAS ON SCREEN
        # (B8-462).** Moving the "Judged against" pulldown drops the claim
        # above, and this used to fall through to the RUN: on a run whose
        # stored type differs from the report being shown, the type pulldown
        # jumped on a change nobody made to it. Knut: *"Changing judged against
        # parameter shall not ever alter report type."* `_settings_touched`
        # pins the widget's own value first, so the fall-through below is
        # reached only when no document was speaking at all.
        # **EVERYTHING BELOW IS FITTED TO THE MEASUREMENT'S KIND (K13).** A
        # loaded document above answers for itself, so a saved report keeps
        # the type it was written as and is shown as recorded; every answer
        # from here on is what a NEW document would be, and a profiling
        # measurement's is the Printing record, a verification's never is.
        sticky = str(getattr(self, "_sticky_type", "") or "")
        if sticky in REPORT_TYPES:
            return self._fit_to_kind(sticky)
        if self._session_type:
            return self._fit_to_kind(self._session_type)
        # **A NEW REPORT OF A RUN OR A CALIBRATION STARTS ON THE PREFERENCES
        # DEFAULT (K31, B8-388).** Knut, 5801677743: *"the starting choice for
        # 'New report...' should be the the defaults in preferences ->
        # reports first"*. Fitted to the kind: a profiling sheet's is the
        # Printing record, a verification's and a calibration's never is.
        if self._run_ctx is not None or self._is_calibration_window():
            from workflow.run_compliance import new_report_type
            return new_report_type(
                str(self._settings.get("report_default_type", "") or ""),
                self._window_kind())
        reports = self._runs_for_report()
        return self._fit_to_kind(
            report_type(reports[0]) if reports else REPORT_TYPE_DEFAULT)

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
        `_syncing_limits` flag, so filling it is never read as a user's
        choice.
        """
        if getattr(self, "_type_combo", None) is None:
            return
        from workflow.measurement_report import (REPORT_TYPE_MENU,
                                                 REPORT_TYPE_MENU_HEADING,
                                                 REPORT_TYPE_MENU_SPLIT)
        current = self._report_type_now()
        from workflow.measurement_report import (KIND_CALIBRATION,
                                                 KIND_PROFILING,
                                                 REPORT_TYPE_ISO_SET,
                                                 report_types_for_kind)
        kind = self._window_kind()
        allowed = report_types_for_kind(kind)
        self._type_combo.clear()
        model = self._type_combo.model()
        for tid, name, blurb, built in REPORT_TYPE_MENU:
            # K33: the ISO types also need their values loaded
            from workflow.measurement_report import report_type_is_built as _is_built
            built = _is_built(tid)
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
            elif tid not in allowed and kind == KIND_CALIBRATION \
                    and tid in REPORT_TYPE_ISO_SET:
                # K36-2 (Knut, #182 5820871320): *"No, but the limit sets can
                # still be chosen, if the user wants to use those metrics and
                # threshold values in the report."*
                self._disable_item(model, i)
                self._type_combo.setItemData(
                    i, tr("Not for a calibration run: the two ISO report "
                          "types are for verification runs. A calibration "
                          "run's report can still be judged against an ISO "
                          "limit set, chosen in “Judged against”."),
                    Qt.ItemDataRole.ToolTipRole)
            elif tid not in allowed:
                # SHOWN AND REFUSED, like an unbuilt type, and it says why.
                self._disable_item(model, i)
                self._type_combo.setItemData(
                    i, tr("A profiling measurement is the sheet a profile was "
                          "built from, so its only report is the Printing "
                          "record.") if kind == KIND_PROFILING else
                    # #182 beta 39, Knut 5794078008: *"Allowed report types
                    # are all except the printing record"*.
                    tr("The Printing record is the report of a profiling "
                       "measurement. With Run type Calibration, the "
                       "calibration's measurement uses one of the other "
                       "types.") if kind == KIND_CALIBRATION else
                    tr("The Printing record is the report of a profiling "
                       "measurement. A verification is judged, so it uses "
                       "one of the other types."),
                    Qt.ItemDataRole.ToolTipRole)
        idx = self._type_combo.findData(current)
        self._type_combo.setCurrentIndex(max(0, idx))
        # **ENABLED WITH SEVERAL RUNS TOO (K17, Knut on beta 34):** *"I select
        # some measurements from both sets, but now I am not allowed to select
        # report type at all."* The type was greyed because a choice was
        # stored on ONE run, and with two there is no one run to store it on.
        # That reason went when the type became the DOCUMENT's (K.7, K.8): with
        # several runs the choice is this window's, kept for the session and
        # written to neither run (`_on_type_chosen`). §10 only ever asked for
        # the fallback below when the runs DISAGREE.
        self._type_combo.setEnabled(True)
        # B8-946: the type is the REPORT's since K31; no run in its label.
        self._type_label.setText(tr("Report type:"))
        self._type_combo.setToolTip("")
        # (K31: runs no longer carry a report type, so the line that said the
        # loaded runs "were set to different report types" has nothing left
        # to describe and is gone.)
        # WHICH TYPES EXIST COMES FIRST, and it used to come second.
        # Photographed on screen: with both on one elided line, the half
        # that got cut was "Already generated for this run: …", which is
        # precisely what Knut asked the window to show. What a type is FOR
        # has another home, the pulldown's own entries and the help button
        # beside it; what a run already holds has none.
        # ONE THING ON THE LINE, NOT TWO. An earlier round moved the
        # generated list in front of the type's description because, with
        # both on one elided line, the half that got cut was the list. It
        # is still one line, so the description was still pushing the list
        # out on any window narrow enough: what the type is FOR has two
        # other homes, the pulldown's own entries and its tooltip, and what
        # the run already holds has none. So the line is the list, and the
        # description keeps the tooltip.
        blurb = self._type_blurb_for(current)
        already = self._generated_types_line(run)
        self._generated_full = self._generated_types_detail(run)
        self._set_type_blurb(already or blurb)
        self._type_combo.setToolTip(blurb)
        self._generate_btn.setToolTip("")
        # **SEVERAL PLACES ARE NO LONGER A REFUSAL (#182 beta 39, G7).** Two
        # sentences stood here saying Generate saves into one profile run (or
        # one project's calibration) and asking the reader to remove every
        # other entry. Knut, 5794078008: *"a user may need to see how a
        # printers profile has changed across different periods that are
        # saved as different projects"*, so a report across places is written
        # (`_write_the_document`). Two states still cannot be, and each says
        # why: a document across places that has no one folder to live in,
        # and ticks that are all in ONE other place (a report of that place
        # alone belongs to that place's own window, whose run type and limit
        # set it would be filed under).
        calibration = self._is_calibration_window()
        cal_ok = calibration and self._own_cal_dir() is not None
        _doc_runs = [] if self._nothing_is_ticked() else self._runs_for_document()
        if self._spans_places(_doc_runs):
            from workflow.measurement_report import across_places_refusal
            if across_places_refusal(
                    [r.get("_origin_dir") or "" for r in _doc_runs]):
                self._generate_btn.setToolTip(tr(
                    "A report across profile runs or projects is saved only "
                    "when every ticked measurement is in a ChromIQ project. "
                    "Save report as PDF… saves the report shown here."))
        # **UNDER CALIBRATION A REPORT COVERS CALIBRATIONS ONLY (#182 K30,
        # challenge A F4).** A profile run's measurement ticked beside the
        # window's own calibration is refused (`_reports_to_generate`), and
        # the sentence below blamed "every ticked measurement", which was
        # false: the window's own calibration was ticked too.
        from workflow.measurement_report import is_calibration_dir
        _not_cal = [r for r in _doc_runs
                    if not is_calibration_dir(r.get("_origin_dir") or "")]
        if calibration and _not_cal and not self._generate_btn.toolTip():
            # ONE OR SEVERAL (re-challenge R2 of beta 39, #9): "Untick it"
            # was said of three ticked profile-run measurements as well.
            self._generate_btn.setToolTip(tr(
                "With Run type Calibration, a report covers calibrations "
                "only, and a profile run's measurement is ticked. Untick it "
                "to save a report of the calibrations. Save report as PDF… "
                "saves the report shown here.") if len(_not_cal) == 1 else tr(
                "With Run type Calibration, a report covers calibrations "
                "only, and {n} measurements of profile runs are ticked. "
                "Untick them to save a report of the calibrations. Save "
                "report as PDF… saves the report shown here.").format(
                    n=len(_not_cal)))
        # (K31, Knut 5801677743: a report is saved where its ticked
        # measurements decide, from any window, so ticks that are all in
        # another profile run or another project's calibration are no longer
        # refused, and the sentence that said so is gone.)
        # ROUND 3B (F9): only when no sentence above has said why. With a
        # profile run beside the loose file, the across-places sentence names
        # the file outside a project, and removing it gives Generate back.
        if (run is None and self._sources and not cal_ok and not calibration
                and not self._generate_btn.toolTip()):
            # NO RUN TO SAVE INTO, and removing entries cannot change that
            # (round 2B, #7): the window's own measurement is outside any
            # profile run. Said, rather than a greyed button with no reason.
            self._generate_btn.setToolTip(tr(
                "This measurement is not part of a profile run, so there is no "
                "run to save a report into. Save report as PDF… saves the "
                "report shown here."))
        # The button writes a report for the run the window is on. With no run,
        # or with several loaded, there is no single place for it to go.
        #
        # AND IT ASKS THE LIST IT WILL ACTUALLY WRITE FROM. It asked
        # `_runs_for_report`, which is everything loaded: unticking the row of
        # the run you are standing in left the button enabled over an empty
        # target list, so pressing it wrote nothing and said nothing. That is
        # the same "a button that does nothing" the cross-run fault presented
        # as, and an adversary round drove it on screen the same day the fault
        # was fixed. A disabled button is visibly refusing; a live one that
        # writes nothing is not. The all-unticked case already disabled it, so
        # this only makes the rule reach the row that matters.
        # FINAL ROUND FC-2 (and B8-803): a profiling sheet and dated
        # verifications loaded together. One press wrote ONE type into BOTH
        # kinds of folder: Printing records into verification folders, or a
        # graded Full colour check into the profiling folder, which K19 then
        # rightly hides from both readouts, so the press looked like it did
        # nothing. Each kind has its own reports (§13.10), so it is refused
        # and said, as several places are.
        mixed = self._kinds_are_mixed()
        if mixed:
            # TICKED, NOT LOADED (challenge 2 of beta 42, #1c): an unticked
            # measurement of the other kind no longer greys the button, so
            # the sentence names the tick as the way out as well.
            self._generate_btn.setToolTip(tr(
                "Measurements of a profiling sheet and of verifications are "
                "ticked together, and each has its own kind of report. "
                "Untick one kind, or remove it with Remove Profile's "
                "Measurements…, to save a report. Save report as PDF… saves "
                "the report shown here."))
        # UNDER CALIBRATION ONLY A CALIBRATION IS WRITTEN, whatever else is
        # loaded: a run's measurement left first in the list after a Remove
        # would otherwise be written as a calibration type into a profiling
        # or verification folder.
        own_cal = self._own_cal_dir() if calibration else None
        cal_missing = bool(
            own_cal is not None and self._sources
            and not Path(str(self._sources[0]["origin"])).exists())
        if cal_missing:
            # F5: the calibration's reports are listed, its measurement is
            # not on disk, so there is nothing new to report on.
            self._generate_btn.setToolTip(tr(
                "The calibration has not been measured since its chart was "
                "made, so there is no measurement to report on. Its earlier "
                "reports can still be opened, and Save report as PDF… saves "
                "the report shown here."))
        if calibration and not cal_ok and self._sources:
            self._generate_btn.setToolTip(tr(
                "With Run type Calibration, Generate report saves a report of "
                "a project's calibration, and the measurement this window is "
                "on is not one. Save report as PDF… saves the report shown "
                "here."))
        live = ((cal_ok if calibration else run is not None)
                and not mixed and not cal_missing
                and bool(self._reports_to_generate()))
        # **K36-1: AN ISO TYPE IS JUDGED AGAINST AN ISO SET (Knut, #182
        # 5820871320).** A saved report written before the rule may pair one
        # with another set; it opens as it was saved, and a NEW Generate of
        # that pair (Create New or Update) is refused with the way out. The
        # two pulldowns are that way out, so they stay live.
        live_but_for_the_pair = live
        if live and self._type_refuses_the_set():
            live = False
            self._generate_btn.setToolTip(self._type_refuses_the_set_line())
        if not live and not self._generate_btn.toolTip():
            # **EVERY GREYED GENERATE CARRIES ITS REASON (C6).** The two
            # states no sentence above covers: an empty window, and a list
            # whose every row is unticked.
            if not self._sources:
                self._generate_btn.setToolTip(tr(
                    "No measurement is loaded. Add a profile's measurements "
                    "to the list to generate a report."))
            elif self._nothing_is_ticked():
                self._generate_btn.setToolTip(tr(
                    "No measurement is ticked in the list, so there is "
                    "nothing to report on. Tick one to generate a report."))
        if live:
            self._generate_btn.setToolTip("")
        self._generate_btn.setEnabled(live)
        self._set_generate_why("" if live else self._generate_btn.toolTip())
        self._grey_what_cannot_help(live_but_for_the_pair)
        # The red line's words follow the button (B8-1034).
        self._word_the_stale_line()
        # **THE BOX THAT WIDENED THE REPORT IS GONE (B8-590), AND SO IS THE
        # RULE THAT FORCED IT OFF.** A one-measurement list needed "Show all
        # measurement runs" turned off and greyed (B8-392); a one-page summary
        # needed it disabled as well. Neither rule has anything left to act
        # on: the report covers the ticked rows and nothing else. What the
        # one-page type still constrains is how MANY rows it can cover, and
        # that is now said at Generate rather than enforced behind the user's
        # back.
        from workflow.measurement_report import REPORT_TYPE_SUMMARY
        one_page = current == REPORT_TYPE_SUMMARY
        self._show_that_a_one_page_summary_is_one_sheet(one_page)

    def _show_that_a_one_page_summary_is_one_sheet(self, one_page: bool) -> None:
        """Make the window SAY that the one-page summary is about one sheet.

        **KNUT, BETA 26, ON THE HALF THAT WAS LEFT TO BE GUESSED (B8-523).**
        *"When making a new 'Colour summary' with the 'Show detailed data for
        each run' ON, then there were no Detailed section in the report. When
        selecting 'Colour summary', the 'Show all measurement runs' checkbox is
        disabled and locked, indicating indirectly that only one measurment is
        possible. Help text must be clear about this, and a tool-tip
        explaining. However, the 'Show detailed data for each run' can still be
        clicked so I assumed the created new report should have a detailed
        section. If this is not allowed, due to the one page report size (check
        what previous releases could do), then also means the 'Show detailed
        data for each run' should be disabled."*

        **IT IS A LIMIT, NOT A REGRESSION, AND THAT WAS CHECKED BEFORE IT WAS
        CALLED ONE.** T1 was born on 2026-09-11 (`c8c96709`, *"the one-page
        report, built as its own document"*) and `_report_body_html` has
        branched to `_one_page_html` before the detail section since its first
        line: *"no 'How to read' essay, no trend charts, no comparison table,
        no opt-in detail"*. No release of ChromIQ has ever produced a Detailed
        section inside a Colour summary, so there is nothing to restore.

        Three controls, one fact:

        * **The detail box is disabled** while T1 is chosen, like the
          all-runs box beside it, with a tooltip saying why.
        * **The measurement list DRAWS the one sheet the page is about**, and
          is disabled. Ticking eleven rows and getting a document of one is
          the fault he reported first, and it is this: the document records
          what T1 covers, so the list has to show it BEFORE Generate is
          pressed, not after the report comes back named "One date".
          `_rows_drawn_unticked` is the drawing rule; `_hidden_runs` is not
          touched, so the trend charts keep the history and the ticks come
          back when another type is chosen.
        """
        det = getattr(self, "_detail_check", None)
        if det is not None:
            # …and greyed with Generate (`_grey_what_cannot_help`).
            gen = getattr(self, "_generate_btn", None)
            gen_live = gen is None or gen.isEnabled()
            det.setEnabled(not one_page and gen_live)
            det.setToolTip(tr(
                "The one-page colour summary has no per-run detail section: it "
                "is one page about one measurement, to print and hand over "
                "with a job. Choose another report type to see the detailed "
                "data.") if one_page else "")
            # …and why it is greyed when Generate is (B8-1034).
            det.setProperty(self._GREYED_TIP, None)
            if not gen_live and not one_page:
                self._say_why_greyed(det, True)
        lst = getattr(self, "_profile_list", None)
        if lst is None:
            return
        # **THE LIST IS NEVER DISABLED. THAT WAS THE FREEZE (B8-591).**
        # Knut, 2026-09-20: *"Now I tried selecting report type Colour summary.
        # Then the 'included measurements in report' became unticked for all
        # measurements and it froze, so I cannot scroll or select."* And again,
        # further down, when he left it: *"when selecting 'New report...' in
        # Report shown field, then the 'included measurements in report' input
        # box is frozen again."*
        #
        # It was `lst.setEnabled(False)`, put there for B8-523 so that a
        # one-page summary would SHOW the single sheet it covers. A disabled
        # QListWidget does not scroll, does not take a click and gives no
        # reason, so what it looked like from the outside was a hung window:
        # eleven rows, a live scrollbar with somewhere to go, and nothing
        # responding. The measured state, on screen: enabled=False,
        # viewport_enabled=False, a real mouse click on row 0 changed no tick,
        # and Key_Down moved a scrollbar whose range was 0..7 by nothing.
        #
        # A one-page summary really does cover one measurement, and that is
        # still true. It is no longer enforced by taking the control away: the
        # user picks WHICH sheet, and a press of Generate with more than one
        # ticked says so and asks (`_conflicts_with_the_ticks`). Taking the
        # control away also made the choice impossible, which is the part that
        # made it a fault rather than a restriction.
        lst.setEnabled(True)
        lst.setToolTip(tr(
            "A one-page colour summary is about ONE measurement. Tick the one "
            "you want the page to be about; if more than one is ticked when "
            "you click Generate report, ChromIQ says so and asks you to "
            "choose.") if one_page else self._list_tooltip)

    def _generated_types_line(self, run) -> str:
        """Which report types this run has already produced, or "".

        **Knut, 2026-09-11:** *"The Report window must thus show which type of
        reports have been generated."* Counted from the files on disk, never
        from anything this window remembers: a report is generated by a
        measurement no window was open for.
        """
        if run is None and not self._is_calibration_window():
            return ""
        from workflow.measurement_report import (generated_report_types,
                                                 report_type_name)
        kind = self._window_kind()
        dirs = self._measurement_dirs_of_the_list(run, kind)
        counts = generated_report_types(
            run, kind,
            str(self._settings.get("report_default_type", "") or ""),
            measurement_dirs=dirs)
        # **"FOR THESE MEASUREMENTS" ON A PROFILING WINDOW (K26, Knut
        # 5792484060, Q4: "yes").** Since K25 a Profiling window counts the
        # Printing records of every run in its list, so "for this run" was
        # no longer what it counted. A Verification window keeps its words.
        # A CALIBRATION WINDOW SAYS "these measurements" TOO (#182 beta 39):
        # it has no run, and its list may hold several projects'
        # calibrations.
        from workflow.measurement_report import (KIND_CALIBRATION,
                                                 KIND_PROFILING)
        profiling = (kind in (KIND_PROFILING, KIND_CALIBRATION)
                     or not self._dirs_are_the_runs_own(run, dirs))
        if not counts:
            return (tr("No report has been generated for these measurements "
                       "yet.") if profiling
                    else tr("No report has been generated for this run yet."))
        names = ", ".join(
            tr("{type}: {count}").format(type=tr(report_type_name(tid)),
                                          count=n)
            for tid, n in sorted(counts.items()))
        if profiling:
            return tr("Already generated for these measurements: "
                      "{names}").format(names=names)
        return tr("Already generated for this run: {names}").format(names=names)

    def _ticks_are_the_runs_own(self, run) -> bool:
        """Whether every ticked measurement is *run*'s own (K30 leftovers).

        A label that names the run ("Report type (run1):") is a claim about
        what the report covers. A Profiling window lists every run's sheet,
        and a report of another run, or across runs or projects, can be
        loaded into it; the label then names a run the report is not (only)
        about, so it drops the name, as it does with several profiles added.
        """
        runs = [] if self._nothing_is_ticked() else self._runs_for_document()
        return self._dirs_are_the_runs_own(
            run, [r.get("_origin_dir") or "" for r in runs])

    @staticmethod
    def _dirs_are_the_runs_own(run, dirs) -> bool:
        """Whether every folder *dirs* names is *run*'s own (its folder or
        one of its dated verifications).

        **"FOR THIS RUN" ONLY WHEN IT IS THIS RUN'S (challenge C, C12).** A
        Verification window lists and counts the reports of every
        measurement in its list (K23/K25), and a report across projects
        loads the other project's dates into that list: the line read
        "Already generated for this run: … 10" while three of the ten were
        another project's. The count is the list's, as K25 rules, so the
        words follow it: "for these measurements", as a Profiling window
        says it.
        """
        if run is None:
            return False
        own = {str(run.dir)}
        try:
            own |= {str(v.dir) for v in run.verifications()}
        except Exception:                            # noqa: BLE001
            pass
        return all(str(d) in own for d in (dirs or []) if str(d))

    def _set_type_blurb(self, full: str) -> None:
        """One line, elided to the room it has; the whole sentence as the
        tooltip. Same rule as the mismatch strip below it, for the same
        reason."""
        from PyQt6.QtGui import QFontMetrics
        self._type_blurb_full = full or ""
        import html as _html
        fm = QFontMetrics(self._type_blurb.font())
        room = max(120, self.width() - self._type_blurb.x() - 40)
        # THE LINK COSTS ROOM TOO, so the text is elided into what is left
        # rather than into the whole width and then having a link appended past
        # the edge.
        link_txt = tr("show all")
        link_w = fm.horizontalAdvance("  " + link_txt) if self._generated_full else 0
        shown = fm.elidedText(self._type_blurb_full, Qt.TextElideMode.ElideRight,
                              max(80, room - link_w))
        was_cut = shown != self._type_blurb_full
        if was_cut and self._generated_full:
            self._type_blurb.setText(
                f"{_html.escape(shown)}&nbsp;&nbsp;"
                f"<a href='#generated'>{_html.escape(link_txt)}</a>")
        else:
            self._type_blurb.setText(shown)
        self._type_blurb.setToolTip(self._generated_full or self._type_blurb_full)

    def _generated_types_detail(self, run) -> str:
        """Every report this run has produced, one per line, or "".

        The long form behind the link. `_generated_types_line` is the same
        facts on one line; this is what a reader gets when that line will not
        fit, which on six types it never will.
        """
        if run is None and not self._is_calibration_window():
            return ""
        from workflow.measurement_report import (generated_report_types,
                                                 report_type_name)
        kind = self._window_kind()
        counts = generated_report_types(
            run, kind,
            str(self._settings.get("report_default_type", "") or ""),
            measurement_dirs=self._measurement_dirs_of_the_list(run, kind))
        if not counts:
            return ""
        return "\n".join(
            tr("{type}: {count}").format(type=tr(report_type_name(tid)), count=n)
            for tid, n in sorted(counts.items()))

    def _show_generated_reports(self, _href: str = "") -> None:
        """The whole list, when the one line could not hold it."""
        if not self._generated_full:
            return
        from ui.warning_sign import inform
        from workflow.measurement_report import KIND_VERIFICATION
        ctx = self._run_ctx
        run = ctx.run if ctx is not None else None
        kind = self._window_kind()
        # The title says what the line counted (C12): one run's reports only
        # when every folder counted is that run's own.
        own = (kind == KIND_VERIFICATION and self._dirs_are_the_runs_own(
            run, self._measurement_dirs_of_the_list(run, kind)))
        inform(self, tr("Reports generated for this run") if own
               else tr("Reports generated for these measurements"),
               self._generated_full)

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
        from workflow.measurement_report import iso_type_values_missing
        # #182 S-2 (§23) and K33 (B8-994): the two ISO types are built, and
        # offered whenever their standard's values are loaded. The one reason
        # left for refusing one is that its values are NOT loaded: the
        # shipped file is missing or unreadable and nobody supplied their own.
        if iso_type_values_missing(type_id):
            return MeasurementReportDialog._iso_values_missing_line()
        return tr("Not available yet: this report is still being built.")

    @staticmethod
    def _iso_values_missing_line() -> str:
        """Why an ISO report type is greyed: its standard's values are not
        loaded (K33, B8-994). The demo pack's README quotes it."""
        return tr("Not available: no values of this standard are loaded. "
                  "They ship with ChromIQ; if they are missing, supply them "
                  "with “Reference values…” in the Report limits window.")

    def _type_blurb_for(self, type_id: str) -> str:
        from workflow.measurement_report import REPORT_TYPE_MENU
        for tid, _name, blurb, built in REPORT_TYPE_MENU:
            # K33: the ISO types also need their values loaded
            from workflow.measurement_report import report_type_is_built as _is_built
            built = _is_built(tid)
            if tid == type_id:
                return tr(blurb) if built else self._not_built_line(tid)
        return ""

    def _on_type_chosen(self, index: int) -> None:
        """The report type chose: the REPORT's, kept for the session (K31).

        Knut, 5801677743: *"settings belongs to the report"*. The type was
        stored on the run from a one-run window until K31 (D9); it is now the
        report's setting in every window, as it already was across places
        (K17): nothing is written until Generate report, and a new report
        starts on the Preferences default again (`_load_the_defaults`).
        NOTHING IS RECALCULATED HERE either: a type decides which document is
        produced from numbers that do not move.

        THROUGH THE ONE DOOR, like every other setting (`_settings_touched`),
        which pins the new type (`_sticky_type`) so the pulldown and the page
        agree.
        """
        if self._syncing_limits or index < 0:
            return
        from workflow.measurement_report import report_type_is_built
        type_id = self._type_combo.itemData(index)
        current = self._report_type_now()
        if not type_id or type_id == current:
            return
        from workflow.measurement_report import report_types_for_kind
        if not report_type_is_built(type_id) or \
                type_id not in report_types_for_kind(self._window_kind()):
            # Belt and braces: the entry is greyed, and a keyboard or a style
            # that ignores the flag must not be able to choose it anyway.
            # (K13's refusal rides the same door: a type the measurement's
            # kind does not allow.)
            self._sync_type_combo_to(current)
            return
        self._session_type = type_id
        # **K36-1 (Knut, #182 5820871320): CHOOSING AN ISO TYPE SETS "JUDGED
        # AGAINST" TO ITS STANDARD'S SET** (ISO 12647-8 for the Validation
        # print check, ISO 12647-7 for the Contract proof check). The user may
        # then move among the four ISO sets; the others are greyed.
        from workflow.measurement_report import REPORT_TYPE_ISO_SET
        iso_set = REPORT_TYPE_ISO_SET.get(type_id)
        # **A STEP IS NOT A CHOICE (challenge 4 of beta 42, B8-1074).** The
        # pulldown takes every wheel notch and arrow key as a choice, so
        # walking it past an ISO type moved "Judged against" and left it
        # moved. The set an ISO type moves (and the report's own edited
        # numbers with it) is remembered, and put back when the type leaves
        # the ISO types (Basti's option a).
        #
        # **AN ALLOWED SET IS KEPT (Knut, #182 5822758830, answer 4).** An
        # ISO type moves "Judged against" only when it is not one of the four
        # ISO sets, and then to the type's own ISO 12647 set; one of the four
        # stays, the other standard's included. A set it did not move needs
        # nothing put back.
        from workflow.measurement_report import set_allowed_for_type
        if iso_set:
            shown_set = str(self._report_limits().set_id or "")
            if not set_allowed_for_type(type_id, shown_set):
                if current not in REPORT_TYPE_ISO_SET \
                        and getattr(self, "_set_before_iso_type",
                                    None) is None:
                    self._set_before_iso_type = (
                        shown_set, getattr(self, "_report_own_limits", None))
                self._report_own_limits = None
                self._settings_touched(type_id=type_id, set_id=iso_set)
                return
            self._settings_touched(type_id=type_id)
            return
        back = getattr(self, "_set_before_iso_type", None)
        self._set_before_iso_type = None
        if current in REPORT_TYPE_ISO_SET and back and back[0] \
                and back[0] != self._report_limits().set_id:
            self._report_own_limits = back[1]
            self._settings_touched(type_id=type_id, set_id=back[0])
            return
        self._settings_touched(type_id=type_id)

    def _type_refuses_the_set(self) -> bool:
        """Does the report type on screen refuse the limit set on screen
        (K36-1): an ISO type beside a set that is not one of the four ISO
        sets? Only a saved report written before the rule can show that
        pair, and only a new Generate is refused for it."""
        from workflow.measurement_report import set_allowed_for_type
        try:
            return not set_allowed_for_type(self._report_type_now(),
                                            self._report_limits().set_id)
        except Exception:                                # noqa: BLE001
            return False

    def _type_refuses_the_set_line(self) -> str:
        """Why Generate is greyed over that pair (K36-1)."""
        from workflow.measurement_report import report_type_name
        return tr(
            "A report of the type “{type}” is judged against one of the four "
            "ISO limit sets. This report was saved with another set and is "
            "shown as it was saved. Choose an ISO set in “Judged against”, or "
            "another report type, to generate it again."
        ).format(type=tr(report_type_name(self._report_type_now())))

    @staticmethod
    def _set_refused_by_type_line(type_id: str) -> str:
        """The tooltip of a greyed "Judged against" entry (K36-1)."""
        from workflow.measurement_report import report_type_name
        return tr(
            "Not with the report type “{type}”: it is judged against one of "
            "the four ISO limit sets (ISO 12647-7, ISO 12647-8, Custom ISO "
            "12647-7, Custom ISO 12647-8). Choose another report type to "
            "judge against this set."
        ).format(type=tr(report_type_name(type_id)))

    def _grey_the_sets_the_type_refuses(self) -> None:
        """Grey, and leave visible, every "Judged against" entry the report
        type on screen does not allow (K36-1), each saying why."""
        combo = getattr(self, "_set_combo", None)
        if combo is None:
            return
        from workflow.measurement_report import set_allowed_for_type
        tid = self._report_type_now()
        model = combo.model()
        for i in range(combo.count()):
            sid = str(combo.itemData(i) or "")
            if not sid or set_allowed_for_type(tid, sid):
                continue
            self._disable_item(model, i)
            combo.setItemData(i, self._set_refused_by_type_line(tid),
                              Qt.ItemDataRole.ToolTipRole)

    def _hold_the_set_to_the_type(self) -> None:
        """A NEW report's starting pair, held to K36-1: with an ISO type and
        a starting set (the run's own default, else Preferences) that is not
        an ISO set, the set starts on the type's own standard's set. Nothing
        is written: this is the window's choice for the report shown."""
        from workflow.measurement_report import (REPORT_TYPE_ISO_SET,
                                                 set_allowed_for_type)
        tid = self._report_type_now()
        if tid not in REPORT_TYPE_ISO_SET:
            return
        lim = self._sticky_limits() or self._window_limits()
        if not set_allowed_for_type(tid, lim.set_id):
            self._sticky_set = REPORT_TYPE_ISO_SET[tid]

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
        # THE LINE IS THE GENERATED LIST, NOT THE TYPE'S DESCRIPTION, and this
        # call was left on the old composition when that changed. Reachable
        # without contrivance: make the run folder read-only, change the type,
        # `set_run_report_type` raises and this puts the pulldown back. An
        # adversary round photographed the result: a line describing the report
        # type, carrying a "show all" link that opens a list of generated
        # reports the line does not mention, over a tooltip contradicting the
        # visible text, and it stays that way until the next refresh.
        #
        # `_type_blurb_for` also has nothing to do with what the run holds, so
        # the link's own reason has to go with it.
        self._generated_full = self._generated_types_detail(
            self._run_ctx.run if self._run_ctx else None)
        self._set_type_blurb(self._generated_types_line(
            self._run_ctx.run if self._run_ctx else None)
            or self._type_blurb_for(type_id))
        self._type_combo.setToolTip(self._type_blurb_for(type_id))

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
            # **SHORTENED TO THE LABEL'S OWN TEXT AREA (challenge 2 of beta
            # 42, #7).** It was shortened to the window's width less 60,
            # which is wider than the strip's text area (the label's width
            # less its 10 px padding and 1 px border a side): the "…" was
            # drawn past the edge and cut to one dot. Only the shortening
            # moved: the choice between two wrapped lines and one shortened
            # line is asked exactly as before, because asking it of the
            # label's own width changed WHEN the strip wraps, and a strip
            # wrapped before the window's screen-fitting ladder ran took its
            # height out of the trend charts (measured on screen: 150 to
            # 62 px).
            self._mismatch.setText(fm.elidedText(
                one, Qt.TextElideMode.ElideRight,
                min(width, self._strip_text_width())))
        self._mismatch.setToolTip(full)
        self._mismatch.setVisible(True)

    #: The strip's padding and border, a side, as its style sheet sets them
    #: ("padding: 6px 10px", "border: 1px"), for a label whose contents rect
    #: does not already leave them out.
    _STRIP_SIDE_PX = 11

    def _strip_text_width(self) -> int:
        """The width the strip's text may take: the label's own text area
        once it is laid out, otherwise the window's width less the page's
        margins and the strip's padding."""
        lab = getattr(self, "_mismatch", None)
        if lab is not None and lab.isVisible() and lab.width() > 50:
            avail = lab.contentsRect().width()
            if avail >= lab.width():
                avail = lab.width() - 2 * self._STRIP_SIDE_PX
        else:
            avail = max(200, self.width() - 60) - 2 * self._STRIP_SIDE_PX
        return max(100, int(avail) - 2)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if getattr(self, "_mismatch_full", ""):
            self._set_strip(self._mismatch_full)
        if getattr(self, "_type_blurb_full", ""):
            self._set_type_blurb(self._type_blurb_full)
        if getattr(self, "_saved_note_full", ""):
            self._set_saved_note(self._saved_note_full)
        if getattr(self, "_saved_hint_full", ""):
            self._set_saved_hint(self._saved_hint_full)
        if getattr(self, "_generate_why_full", ""):
            self._set_generate_why(self._generate_why_full)
        # **AND AGAIN ONCE THE LAYOUT HAS RUN (B8-927).** The two lines beside
        # "Report shown" are fitted to their label's OWN width, and during
        # this event that is still the old one: narrowed to the 760 px
        # minimum, the German hint was fitted to two lines of the wider label
        # and then drawn in the narrower one on three, the first and last cut
        # in half (photographed before and after). The layout has given the
        # label its new width by the next turn of the event loop.
        if not getattr(self, "_rewrap_queued", False):
            self._rewrap_queued = True
            QTimer.singleShot(0, self._rewrap_beside_the_pulldown)

    def _rewrap_beside_the_pulldown(self) -> None:
        self._rewrap_queued = False
        # the strip too, now that the label has its own width (#7)
        lab = getattr(self, "_mismatch", None)
        if (getattr(self, "_mismatch_full", "") and lab is not None
                and lab.isVisible() and lab.width() > 50):
            self._set_strip(self._mismatch_full)
        if getattr(self, "_saved_note_full", ""):
            self._set_saved_note(self._saved_note_full)
        if getattr(self, "_saved_hint_full", ""):
            self._set_saved_hint(self._saved_hint_full)

    # -- reasons a row was not computed, as sentences --------------------------
    def _reason_sentence(self, code: "str | None", r: "dict | None" = None,
                         row: "dict | None" = None) -> str:
        """The sentence for one reason code. *row* is the verdict row it
        withholds, when the caller has it: the evenness noise sentence names
        that row's limit."""
        r = r or {}
        _limit = (row or {}).get("threshold")
        gb = r.get("grey_balance") or {}
        from workflow import measurement_report as _MR
        texts = {
            "no_greys": tr("the measured chart has no grey patches (R = G = B)"),
            "too_few_steps": tr("the measured chart has {k} grey steps; at "
                                "least 8 from white to black are needed").format(
                                    k=gb.get("levels", 0)),
            # #182 B8-483 (Knut, 2026-09-23): the required steps must be
            # pickable roughly evenly spaced. Names the level nothing is near.
            "grey_steps_bunched": tr(
                "the grey steps of the measured chart are bunched together: "
                "none lies within {tol} of the level {level} on a scale from "
                "0 (black) to 100 (white), and {n} roughly evenly spaced "
                "steps from black to white are needed").format(
                    tol=_level_text(_MR.GREY_SPACING_TOL),
                    n=_MR.GREY_MIN_LEVELS,
                    level=_level_text(gb.get('missing_level'))),
            "no_white": tr("the grey ramp in the measured chart does not reach "
                           "white"),
            "no_black": tr("the grey ramp in the measured chart does not reach "
                           "black"),
            "no_reference": tr("there is no reference value for these patches"),
            "needs_reference_file": tr("this row needs a reference for the "
                                       "printing condition, and the measured "
                                       "chart has no aim for it"),
            "no_ramp": tr("the measured chart has no tone ramp with at least "
                          "three steps between 30 % and 70 %"),
            # K31 rule A (Knut, #182 5801677743): the grey ramp's spacing
            # rule on the 30 to 70 % band. Names the tone value nothing is
            # near, as the grey sentence above names its level.
            "ramp_steps_bunched": tr(
                # B8-950: the tolerance carries its unit, percentage points
                # of tone value, and the level its language's decimal mark.
                "the mid-tone steps of the measured chart are bunched "
                "together: none lies within {tol} percentage points of the "
                "tone value {level} %, and {n} roughly evenly spaced steps "
                "between 30 % and 70 % on one ramp are needed").format(
                    tol=_level_text(_MR.RAMP_SPACING_TOL),
                    n=_MR.RAMP_MIN_STEPS,
                    level=_level_text((r.get('ramps_30_70') or {}).get(
                        'missing_level'))),
            # K31 option (a): on a chart built FROM PROFILE GAMUT the grey
            # steps are its neutral aims, placed by their L*.
            "too_few_neutral_aims": tr(
                "the measured chart was built from the profile's gamut and "
                "has {k} distinct neutral aims to serve as grey steps; at "
                "least {n} are needed").format(
                    k=gb.get("levels", 0), n=_MR.GREY_MIN_LEVELS),
            "neutral_aims_bunched": tr(
                "the neutral aims of the measured chart are bunched together: "
                "none lies within {tol} of the lightness L* {level}, and {n} "
                "roughly evenly spaced steps from its black to its white are "
                "needed").format(
                    tol=_level_text(_MR.GREY_SPACING_TOL),
                    n=_MR.GREY_MIN_LEVELS,
                    level=_level_text(gb.get('missing_level'))),
            # K40-2 (Knut, #182 5832026677): the tone row of such a chart
            # takes its neutral aims too; K43: at their tone value between
            # the chart's own paper and its darkest neutral aim.
            "ramp_too_few_neutral_aims": tr(
                "the measured chart was built from the profile's gamut and "
                "has fewer than {n} distinct neutral aims in its mid-tones "
                "(30 % to 70 % of the way from its paper to its darkest "
                "neutral aim), spanning at least {span}, to serve as its "
                "mid-tone ramp").format(n=_MR.RAMP_MIN_STEPS,
                               span=_level_text(_MR.RAMP_MIN_SPAN)),
            "ramp_neutral_aims_bunched": tr(
                "the neutral aims in the measured chart's mid-tones (30 % to "
                "70 % of the way from its paper to its darkest neutral aim) "
                "are bunched together: none lies within {tol} of the "
                "lightness L* {level}, and {n} roughly evenly spaced ones are "
                "needed").format(
                    # K43: the spacing tolerance in L* on this chart's own
                    # scale, the unit of the lightness it is read beside
                    tol=_level_text((r.get('ramps_30_70') or {}).get(
                        'spacing_tol_l', _MR.RAMP_SPACING_TOL)),
                    n=_MR.RAMP_MIN_STEPS,
                    level=_level_text((r.get('ramps_30_70') or {}).get(
                        'missing_level'))),
            "neutral_aims_no_white": tr(
                "the neutral aims of the measured chart do not reach within "
                "{reach} L* of its lightest aim").format(
                    reach=f"{_MR.NEUTRAL_AIM_END_REACH:g}"),
            "neutral_aims_no_black": tr(
                "the neutral aims of the measured chart do not reach within "
                "{reach} L* of its darkest aim").format(
                    reach=f"{_MR.NEUTRAL_AIM_END_REACH:g}"),
            # **THE POPULATION THAT WAS GRADED, NOT THE CHART'S OWN COUNT.**
            # Measured on a 20-patch chart: the row was withheld and the
            # sentence read *"the chart has 20 patches; at least 20 are
            # needed"*, which tells a reader the condition is met and the row
            # was withheld anyway. The verdict is passed on the WITHIN-gamut
            # subset (`graded_de00`), and that was 18. `{n}` was filled from
            # `report["patches"]`, which is the sheet.
            "small_sample": _small_sample_sentence(r),
            "printing_unrecorded": tr("how this sheet was printed is not "
                                      "recorded, so this value is shown for "
                                      "information only"),
            "no_corners": tr("the measured chart has no patch at the colour "
                             "corners this row needs"),
            # WHAT THE CODE MEANS, WHICH IS NOT WHAT THIS USED TO SAY.
            # `REASON_NOT_COMPUTED` is set when the BLOCK IS MISSING FROM THIS
            # REPORT; it says nothing about whether a file can be read. The old
            # sentence named a cause, "the measurement file could not be read
            # again", and that cause was untrue in both cases that reach here:
            # a report saved before the row existed was never asked for the
            # value, and a report of a measurement that has since been
            # re-measured has its own .ti3 sitting in the run's old/ folder.
            # This sentence is the one thing that is true of both.
            "not_computed": tr("this value is not in this saved report"),
            # K22 (B8-845, question 3): a measurement with no device values
            # printed `not_computed` on its grey, ramp and gamut rows, "this
            # value is not in this saved report", for a report built a second
            # ago. What is missing is the numbers each patch was printed from:
            # without them no patch can be found to be grey, a ramp step or on
            # the gamut's edge.
            "no_device_values": tr(
                "the measured chart carries no device values (the RGB numbers "
                "each patch was printed from)"),
            # #182 S2w, approved by Knut on 2026-09-18. TWO codes rather than
            # one, because they send a reader to different places: the first
            # asks the chart to declare a strip at all, the second says the
            # strip it declares is too short to average over. A reason a
            # reader cannot act on is not a reason, so each names the thing to
            # change and not only the thing that is wrong.
            "no_control_strip": tr(
                "the measured chart declares no control strip"),
            "control_strip_too_small": _control_strip_sentence(r),
            "too_few_surface_patches": _surface_gamut_sentence(r),
            "too_few_outer_patches": _outer_gamut_sentence(r),
            # ChromIQ's own two repeatability rows. FOUR codes for two rows,
            # by the same rule the pairs above follow: each sends a reader
            # somewhere different, and a reason nobody can act on is not a
            # reason. Neither sentence mentions a standard, because no
            # standard defines either row.
            "no_repeat_patches": tr(
                "the measured chart never asks for the same colour twice, so "
                "there is nothing on the sheet to compare with itself"),
            "too_few_repeat_groups": _repeat_groups_sentence(r),
            # K18 and K22 (B8-845, question 2): it ended "; the row is judged
            # from the second measurement onward", which explains ChromIQ to a
            # customer and is untrue on a Printing record, which judges
            # nothing on any measurement.
            "no_earlier_measurement": tr(
                "this is the first measurement of the measured chart, so "
                "there is nothing to compare it with"),
            "too_few_shared_patches": _repeat_shared_sentence(r),
            # EVENNESS ACROSS THE SHEET (Knut, 2026-09-22). Written to his
            # rule of 2026-09-23: each says what the MEASURED CHART lacks,
            # never what to add or where to add it.
            "evenness_no_layout": tr(
                "no chart file beside the measurement records where each "
                "patch of the measured chart was printed"),
            "evenness_no_positions": tr(
                "the measured chart's layout does not say which strip and "
                "which row each patch was printed in"),
            "evenness_grid_too_small": _evenness_grid_sentence(r),
            # #182 E2 (Knut, 2026-09-23), to the same K22 rule.
            "evenness_page_coverage_too_small": _evenness_coverage_sentence(r),
            "evenness_no_page_geometry": tr(
                "no file of the measured chart records where its patches sit "
                "on the page, so how much of the page they cover is not "
                "known"),
            # K22 (B8-845, question 4): the reachable cause is an area with
            # no READING (the notes demo's run5), whose patches do have aims;
            # "holds no patch with an aim value" named the other half of the
            # condition as the whole. `evenness_block` keeps a patch only when
            # it was measured, has an aim, and (on a split sheet) lies within
            # the profile's gamut, so the sentence names all it needs.
            "evenness_empty_area": _evenness_empty_area_sentence(r),
            "evenness_noisy_pairwise": _evenness_noise_sentence(
                r, "pairwise", _limit),
            "evenness_noisy_from_mean": _evenness_noise_sentence(
                r, "from_mean", _limit),
        }
        return texts.get(code or "", "")

    def _note_sentence(self, code: "str | None") -> str:
        """What one note code says, as a sentence that COMMENTS A VERDICT.

        Not a reason: `_reason_sentence` above explains why a row has no
        verdict, and these explain what to know about one that has. Knut's
        ruling of 2026-09-13 made the two different things, and the example he
        gave is this one, *"regarding the tint of a paper and profile
        combination"*.

        **…AND SINCE 2026-09-21 A NOTE MAY ALSO EXPLAIN AN ABSENCE**, which
        Knut asked for in as many words: an N-A cell carries a raised number
        pointing at a note saying why. `_note_the_absences` builds those
        codes, and they carry their own sentence after `_NOTE_TEXT_SEP`,
        because several of the reasons are computed from the measurement.
        """
        if code and self._NOTE_TEXT_SEP in code:
            return code.split(self._NOTE_TEXT_SEP, 1)[1]
        if code == NOTE_NO_PAPER_PATCH:
            # #182 A10: §M text (M-REPORT-NO-PAPER-PATCH, proposed)
            from workflow import measurement_messages as M
            return M.M_REPORT_NO_PAPER_PATCH.render()[1]
        from workflow.measurement_report import \
            NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE
        if code == NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE:
            # #182 K37, (b): §M text (proposed)
            from workflow import measurement_messages as M
            return M.M_REPORT_JUDGED_ABSOLUTE_NO_PAPER_WHITE.render()[1]
        from workflow.measurement_report import (NOTE_STRIP_CORNERS_IDEAL,
                                                 NOTE_STRIP_CORNERS_PREDICTED)
        if code in (NOTE_STRIP_CORNERS_PREDICTED, NOTE_STRIP_CORNERS_IDEAL):
            # #182 K37 (i): §M text (proposed)
            from workflow import measurement_messages as M
            return (M.M_REPORT_STRIP_CORNERS_PREDICTED
                    if code == NOTE_STRIP_CORNERS_PREDICTED
                    else M.M_REPORT_STRIP_CORNERS_IDEAL).render()[1]
        return {
            "printing_unrecorded": tr(
                "How this sheet was printed is not recorded, so the grey rows "
                "are judged against the chart's own design in absolute Lab. "
                "The paper's own tint is part of that measurement, so a good "
                "print on a warm or tinted paper reads higher here than the "
                "profile deserves."),
            # ONE TEXT FOR THIS NOTE, IN BOTH PLACES IT APPEARS. Knut asked for
            # the note in the Report limits window AND in the report text
            # (2026-09-21), so it lives in the §M catalogue and both renderers
            # ask for it. Two hand-written copies are two documents that drift.
            "recommended_limit": _recommended_limit_note(),
            # Knut, 2026-09-22: the likely causes of an uneven sheet belong
            # *"as notes on the results in the report text, for any report
            # type that has enabled this metric"*. Causes only: no step to
            # take and nothing about ChromIQ (his K18 rule for report text).
            "evenness_causes": tr(
                "A difference between areas of one sheet can come from the "
                "printer (banding, a partly blocked or misaligned print head), "
                "from the paper (not flat, or not the same all over), or, on "
                "an instrument that reads whole strips, from the instrument "
                "drifting during the reading. The strips are read one after "
                "another, so such a drift shows as a difference across the "
                "strips rather than down them."),
        }.get(code or "", "")

    def _numbered_notes(self, runs: list) -> "list[tuple[int, str, str]]":
        """``[(number, rows it comments, the sentence)]`` across every run shown.

        ONE NUMBERING FOR THE WHOLE DOCUMENT, not one per run. A report can
        hold several measurements and the same note can comment a verdict in
        each of them; numbering per run would put two different "note 1" on one
        page. The numbers come from `measurement_report.numbered_notes`, which
        the verdict cells ask as well, so the marker and the list cannot
        disagree.
        """
        return self._numbered_notes_from(self._note_numbering(runs))

    def _numbered_notes_from(self, numbering: list
                             ) -> "list[tuple[int, str, str]]":
        """`_numbered_notes` for a numbering already worked out, so the list
        under the Report Results grid and the lists under the detailed tables
        read one sentence per number from one place."""
        from workflow.compliance_sets import ROW_BY_ID
        out = []
        for n, code, rids in numbering or ():
            sentence = self._note_sentence(code)
            if not sentence:
                continue
            labels = [self._row_name(rid) if rid in ROW_BY_ID
                      else tr("Paper white") if rid == PAPER_WHITE_NOTE_ROW
                      else str(rid)
                      for rid in rids]
            # "; " and not ", ": since K28 the names carry commas of their
            # own ("Average ΔE00, all patches"), and two of them joined by a
            # comma read as four fragments.
            out.append((n, "; ".join(labels), sentence))
        return out

    def _has_an_absence(self, runs: list) -> bool:
        """Whether any row shown reads N-A, so the closing sentence under the
        numbered notes is about something that is on the page."""
        from workflow.compliance_sets import N_A
        for r in runs or ():
            if _is_raw_drift(r):
                continue
            rows, _rec = self._verdict_rows(r)
            if any(x.get("word") == N_A for x in rows):
                return True
        return False

    def _note_numbering(self, runs: list):
        """The raw numbering the verdict cells mark themselves from."""
        from workflow.measurement_report import numbered_notes
        merged: list = []
        for r in runs or ():
            if _is_raw_drift(r):
                continue
            rows, _rec = self._verdict_rows(r)
            merged.extend(rows)
        # #182 A10: A SHEET WITH NO PAPER PATCH carries a numbered note on
        # its "Paper white" line, which is no limit row, so the line is put
        # into the one numbering as a row of its own (after the limit rows,
        # so no row's number moves).
        # #182 K37: on a sheet judged relative to its profile's paper white
        # the line carries M-REPORT-PAPER-WHITE-FROM-PROFILE instead.
        for r in runs or ():
            if _is_raw_drift(r):
                continue
            _code = _paper_white_note_code(r)
            if _code is None:
                continue
            merged.append({"row_id": PAPER_WHITE_NOTE_ROW,
                           "notes": [_code]})
        return numbered_notes(merged)

    def _measured_not_graded(self, r: dict) -> "list[tuple[str, str]]":
        """``[(row label, why)]`` for rows that HAVE a number nobody graded.

        A DIFFERENT LIST FROM THE N-A ROWS, AND IT HAS TO BE. These rows were
        added to that one for a round, and the note it fed was headed "Not
        computed on this chart" and ended "add the missing patches to the
        chart in Create Chart to have it checked" — so a grey row carrying
        1.341, on a chart with a nine-step ramp, was called not computed and
        its reader was sent to add patches that are already there. That is the
        exact falsehood the round before had just removed from the sentence
        above it, reinstated one line below. (That note is itself gone since
        2026-09-21: an N-A now carries a numbered note of its own. This list
        is about rows that HAVE a number, which is why it survives it.)
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
            out.append((label, self._reason_sentence(row.get("reason"), r,
                                                     row)))
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
        from workflow.compliance_sets import N_A, POPULATION_MAY_BE_ABSENT
        from workflow.measurement_report import (EVENNESS_FILE_REASONS,
                                                 EVENNESS_NOISE_REASONS)
        # **EVERY ROW THE PAGE CANNOT ANSWER, ON EVERY SHEET IT SHOWS (#182
        # K30, challenge A F6).** This read the window's one subject sheet,
        # so with several dates ticked it named the two evenness rows while
        # the grey rows of another date on the same page read N-A (spec 19.7,
        # 22.5). One line per row, with the first sheet's reason.
        rows = []
        _seen_rows: "set[str]" = set()
        try:
            _pages = [x for x in self._runs_for_document() if x] or [r]
        except Exception:                               # noqa: BLE001
            _pages = [r]
        # **THE SUBJECT AS THE PAGE JUDGES IT (B8-942).** The raw subject was
        # put in front of the page's sheets whenever it was not among them,
        # and the page's sheets are COPIES judged against the report's set, so
        # it always was: the strip then read the date's own saved verdict (its
        # own set, its own edited numbers) and named rows the page did not
        # show. Its judged copy is used, or nothing when the page has it.
        _keys = {self._run_key(x) for x in _pages}
        if self._run_key(r) not in _keys:
            try:
                _pages = self._judged_by_the_document([r]) + _pages
            except Exception:                           # noqa: BLE001
                _pages = [r] + _pages
        for _sheet in _pages:
            _rows_here, _rec = self._verdict_rows(_sheet)
            for _row in _rows_here:
                _rid = str(_row.get("row_id") or _row.get("key") or "")
                if _row.get("word") == N_A and _rid not in _seen_rows:
                    _seen_rows.add(_rid)
                    rows.append((_row, _sheet))
        missing = [(row.get("row_id") or row.get("key"), row.get("reason"),
                    row, sheet)
                   for row, sheet in rows if row.get("word") == N_A
                   and row.get("reason") not in (None, "printing_unrecorded")
                   # …nor a row withheld for want of a chart FILE (the
                   # evenness layout): no patch added to the chart supplies it
                   and row.get("reason") not in EVENNESS_FILE_REASONS
                   # …NOR ONE WITHHELD FOR THE MEASUREMENT'S NOISE (the two
                   # rounds before beta 37, A-F3 and B-H2). The strip says
                   # "Point here for the reasons and what to add to the
                   # chart", and on the noisy date of the evenness demo it
                   # said so about a chart that was judged on its three other
                   # dates. The sheet scattered; nothing added to the chart
                   # answers that. The row still reads N-A with its note.
                   and row.get("reason") not in EVENNESS_NOISE_REASONS
                   # …AND THIS STRIP IS ABOUT THE CHART. Its message tells the
                   # reader to add patches in Create Chart, print the chart
                   # again and measure it, so naming a row whose population
                   # may honestly not exist makes that sentence false: nothing
                   # can be added to a chart to answer whether it has been
                   # measured twice. The row still reads N-A in the table and
                   # still carries its own reason; it is this promise about
                   # the CHART that it may not appear under. The same two rows
                   # as `set_summary`'s completeness arithmetic, from the same
                   # set, so the strip and the column word cannot drift.
                   and (row.get("row_id") or row.get("key"))
                   not in POPULATION_MAY_BE_ABSENT]
        if not missing:
            return ""
        from workflow.compliance_sets import ROW_BY_ID
        from workflow.measurement_messages import M_REPORT_CHART_MISMATCH
        from workflow.measurement_messages import (
            M_REPORT_CHART_MISMATCH_LAYOUT)
        from workflow.measurement_report import EVENNESS_ROWS
        lines = []
        for rid, reason, row, sheet in missing:
            # THE NAME THE PAGE PRINTS (B8-944): "…, within gamut" on a
            # document whose judged sheets are split, as Report Results.
            label = (self._row_name(rid, _pages) if rid in ROW_BY_ID
                     else str(rid))
            lines.append("• " + label + ": "
                         + self._reason_sentence(reason, sheet, row))
        # THE REPORT'S OWN SET, which is what the page is judged against
        # (B8-942); `_window_limits` is only where a new report STARTS.
        lim = self._report_limits()
        # WHEN EVERY ROW LISTED IS AN EVENNESS ROW, THE REMEDY IS THE LAYOUT
        # (round B before beta 37, M7). The general closing sends a reader to
        # add patches in Create Chart "(for the grey balance: “Neutral grey
        # ramp” with 16 steps)", and a round photographed it under a list
        # holding nothing but the two evenness rows: what they lack is strips
        # and rows on one page, which is the layout, not a patch set.
        # …AND THE GREY LEVER ONLY WHERE A GREY ROW IS LISTED FOR A DEVICE
        # GREY RAMP (B8-942). The general closing names "Neutral grey ramp"
        # with 16 steps; under a list with no grey row, or for the grey rows
        # of a FROM PROFILE GAMUT chart (its grey steps are its neutral aims,
        # §26.5, whose lever is a larger chart), that lever is false.
        from workflow.measurement_messages import (
            M_REPORT_CHART_MISMATCH_NO_GREY)
        _grey_on_a_device_ramp = any(
            str(rid).startswith("grey_balance")
            and sheet.get("reference_source") != "colorimetric"
            for rid, _r, _x, sheet in missing)
        msg = (M_REPORT_CHART_MISMATCH_LAYOUT
               if all(rid in EVENNESS_ROWS for rid, _r, _x, _s in missing)
               else M_REPORT_CHART_MISMATCH if _grey_on_a_device_ramp
               else M_REPORT_CHART_MISMATCH_NO_GREY)
        title, body = msg.render(set=lim.set_label, rows="\n".join(lines))
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
            # A SAVED "should" UNDER ONE OF CHROMIQ'S OWN SETS IS A RELIC (K3):
            # no bracket and no note about "the standard" for a set that is
            # none. The record on disk is not rewritten.
            from workflow.compliance_sets import set_marks_recommendations
            from workflow.measurement_report import (NOTE_RECOMMENDED_LIMIT,
                                                     recorded_compliance)
            _sid = str((recorded_compliance(r) or {}).get("set_id") or "")
            _plain = bool(_sid) and not set_marks_recommendations(_sid)
            for row in rows:
                if _plain:
                    row["should"] = False
                    row["notes"] = [n for n in (row.get("notes") or [])
                                    if n != NOTE_RECOMMENDED_LIMIT]
                row.setdefault("row_id", _ROW_ID_OF.get(row.get("key"), row.get("key")))
                if "word" not in row:
                    if row.get("pass") is True:
                        row["word"] = PASS
                    elif row.get("pass") is False:
                        row["word"] = FAIL
                    else:
                        row["word"] = INFO if rec.get("graded") is False else N_A
            return self._note_the_absences(self._ungrade(
                self._keep_rows_for_type(self._drop_dash_rows(rows))), r), True
        from workflow.measurement_report import judge
        return self._note_the_absences(self._ungrade(self._keep_rows_for_type(
            self._drop_dash_rows(judge(r, self._limits_for(r).limits)))),
            r), False

    @staticmethod
    def _drop_dash_rows(rows: list) -> list:
        """Every row whose limit is "–" leaves the document (K28, item 3).

        Knut, #182 5795087247, asked whether a "–" row should leave the
        Overview as well as Report Results, How to read, Detailed data and the
        graph: *"Yes."* And on rows no chart can answer: *"Any limit set
        selected shall stop showing rows ... only if the metric/row for a
        selected limit set has '-' for its limit."*

        `judge` already writes no row for a "–" limit WITHOUT a value (CH-20);
        a "–" limit WITH a value was written as INFO and printed. That is the
        row this removes. A written row carries ``threshold`` None only for a
        "–" limit (`row_verdict` writes nothing for "?" and "✕"), in a saved
        verdict as in a live one; a row with no ``threshold`` key at all is
        not claimed to be one and is kept. Nothing is counted differently:
        `set_summary` counts limit-bearing rows only, and a "–" row is not one.
        """
        return [x for x in (rows or [])
                if not ("threshold" in x and x.get("threshold") is None)]

    #: Separator inside a note code that carries its own sentence. A unit
    #: separator, because it can never occur in prose or in a reason code.
    _NOTE_TEXT_SEP = "\x1f"

    def _note_the_absences(self, rows: list, r: dict) -> list:
        """**KNUT'S RULING OF 2026-09-21: AN N-A CELL GETS A NUMBERED NOTE.**

        > *"I would say that the N-A for the first measurement instead should
        > have a super-script number, pointing to a note, where the note
        > explains why it is N-A for the first measurement."*

        `judge` deliberately gave an N-A row no notes -- *"a note beside an
        N-A would be a footnote on an absence, which is what `reason` is
        already for"* -- and that was right while the reason reached the
        reader some other way. It is the mechanism Knut has now asked for, so
        the reason becomes a note and travels through the numbering every
        other note uses: one number per distinct sentence, shared by every row
        that carries it, the same number on the cell and in the list.

        **THE SENTENCE TRAVELS WITH THE CODE, and it has to.** Several reasons
        are computed from the measurement (`_control_strip_sentence` counts
        the strip's patches, `_repeat_groups_sentence` counts the groups), so
        two runs in one report can carry one reason code and two different
        sentences. Numbering on the code alone would print one run's count
        beside both rows. Numbering on the code AND its sentence gives them
        separate numbers when they differ and one number when they do not.

        **ON A TYPE THAT JUDGES NOTHING, THE ABSENCES ARE STILL EXPLAINED
        (G12, beta 39).** This method used to return early on the Printing
        record, on the reasoning that a note comments a verdict and T4 gives
        none. That holds for a note that COMMENTS a verdict (`_ungrade` clears
        those, and the "where on the sheet" half below still asks for PASS or
        FAIL). It does not hold for a note that EXPLAINS AN ABSENCE: "this
        could not be worked out, because the measured chart lacks X" is not a
        judgement withheld, which is why `_ungrade` keeps N-A on T4 in the
        first place. Knut, 2026-09-22, on exactly this report type: *"Should
        there be a note there instead, so a user knows why a metric could not
        be checked?"* The heading and the closing sentence under the list are
        chosen per type in `_notes_list_html`, so T4 is never told about
        verdicts or failures.
        """
        from workflow.compliance_sets import FAIL, N_A, PASS
        from workflow.measurement_report import EVENNESS_ROWS
        # …AND WHERE ON THE SHEET, on an evenness verdict that was given.
        # Knut, 2026-09-22: *"The results of this test should return
        # indications of which part of the page are not uniform against other
        # areas."* The sentence carries this measurement's own numbers, so it
        # travels with its code exactly as a computed reason does below, and a
        # report holding two sheets numbers them apart.
        where = _evenness_where_sentence(r)
        if where:
            for row in rows or ():
                if ((row.get("row_id") or row.get("key")) in EVENNESS_ROWS
                        and row.get("word") in (PASS, FAIL)):
                    code = "evenness_where" + self._NOTE_TEXT_SEP + where
                    notes = list(row.get("notes") or ())
                    if code not in notes:
                        notes.append(code)
                    row["notes"] = notes
        for row in rows or ():
            if row.get("word") != N_A or not row.get("reason"):
                continue
            said = self._reason_sentence(row.get("reason"), r, row)
            if not said:
                continue
            code = str(row.get("reason")) + self._NOTE_TEXT_SEP + said
            notes = list(row.get("notes") or ())
            if code not in notes:
                notes.append(code)
            row["notes"] = notes
        return rows

    def _type_covers_sentence(self, type_id: "str | None" = None) -> str:
        """Which metrics the chosen report type judges, or "" when it judges all.

        **A LIMIT SET HAVING A THRESHOLD FOR A ROW, AND THAT ROW REACHING THE
        DOCUMENT, ARE TWO DIFFERENT THINGS, AND THE APP SAID SO NOWHERE.**
        Knut, on beta 32: *"For a 'grey and tone check' report type, the report
        output only shows [three rows] even when the judged against limit set
        details that more metrics are defined with thresholds ... this is not
        specified in help text or anywhere else. How will a user know which
        metrics are reported on for a report type?"*

        He was exactly right. `REPORT_TYPE_ROWS` filters one type, to those
        three rows, while the Report limits table shows thresholds for all
        thirty. The filtering is deliberate and `_keep_rows_for_type` gives a
        good reason for it; the reason lived only in the code.

        **THE ROWS ARE READ OUT OF THE TABLE THAT DOES THE FILTERING**, never
        repeated in prose. A sentence naming three metrics by hand goes stale
        the day a fourth is added; this one cannot, because it is built from
        the same constant the filter uses.

        He cancelled the larger feature this came from, on 2026-09-22, to get
        the report work finished: *"I think that these two things are
        sufficient for now. cancel the design of making a checkmark for each
        report type."*
        """
        from workflow.compliance_sets import ROW_BY_ID, limit_bearing
        from workflow.measurement_report import rows_for_report_type
        keep = rows_for_report_type(type_id or self._report_type_now())
        if not keep:
            return ""
        # **ONLY THE ROWS THE CHOSEN SET ACTUALLY LIMITS.** Challenge round 38
        # drove this on the demo pack and the first version promised three
        # metrics the document judged none of: two printed N-A in all twelve
        # columns, and `ramps_30_70_dl_max` printed no row at all because
        # `chromiq_default` leaves it at "–", as do chromiq_tight,
        # chromiq_quick and iso_12647_7, four of the seven sets. So the
        # sentence named a metric the set does not limit and then said in the
        # next breath that any other limit the set defines is not part of the
        # report, which told the reader all three were limits it defines.
        #
        # `limit_bearing` is the application's own answer to "does this set put
        # a number on this row", and it is the same filter `rows_asked` uses.
        try:
            lim = self._document_limits() or self._sticky_limits()
            bearing = set(limit_bearing(lim.limits)) if lim is not None else None
        except Exception:      # noqa: BLE001 — advisory text, never a gate
            bearing = None
        if bearing is not None:
            keep = tuple(rid for rid in keep if rid in bearing)
            if not keep:
                return ""
        names = [tr(ROW_BY_ID[rid].label) for rid in keep if rid in ROW_BY_ID]
        if not names:
            return ""
        if len(names) == 1:
            return tr("This kind of report judges one metric: {only}. Any "
                      "other limit the set defines is not part of it.").format(
                          only=names[0])
        return tr("This kind of report judges {count} metrics: {names}. Any "
                  "other limit the set defines is not part of it.").format(
                      count=len(names), names="; ".join(names))

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

        **AND THE NOTES GO WITH THE VERDICT, because a note comments a verdict
        and there is none here.** Missed on the first pass and caught by
        `test_the_printing_record_does_not_single_out_two_of_eight_rows`, which
        had been retargeted onto the new state an hour earlier: `judge` attached
        the note while the row still had a word, this method took the word away,
        and the note outlived it. The Printing record then printed a numbered
        note commenting a verdict it does not give, which is the same fault
        `_measured_not_graded`'s type guard exists for, arriving by a new door.
        The invariant is not "notes are set correctly once"; it is that a note
        and a verdict live and die together, after EVERY transformation.
        """
        if not self._ungraded_by_type():
            return rows
        from workflow.compliance_sets import INFO, N_A
        for row in rows:
            if row.get("word") != N_A:
                row["word"] = INFO
            row["notes"] = []
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
            # …AND A RECORDED SENTENCE THAT ITS OWN RECORDED COUNTS DENY IS
            # NOT REPLAYED. See `compliance_sets.recorded_reason`: beta 29
            # wrote "Every value this limit set requires was checked" beside a
            # not_computed of 2, and this early return printed it again, in the
            # window and in every PDF, on the one page that carries no table to
            # contradict it. The word and the counts are still the record.
            from workflow.compliance_sets import recorded_reason
            _reason = recorded_reason(
                str(sm.get("reason", "")), int(sm.get("checked", 0)),
                int(sm.get("total", 0)), int(sm.get("not_computed", 0)))
            return Summary(rec["overall"], int(sm.get("checked", 0)),
                           int(sm.get("total", 0)), int(sm.get("failed", 0)),
                           int(sm.get("cond", 0)), int(sm.get("not_computed", 0)),
                           _reason)
        rows, recorded = self._verdict_rows(r)
        if recorded:
            comp = recorded_compliance(r) or {}
            from workflow.compliance_sets import limits_from_json
            set_id = str(comp.get("set_id", "")) if comp else ""
            limits = (limits_from_json(comp.get("thresholds"), set_id)
                      if comp else {})
            if not limits:
                # an older record: two numbers, all-patch rows
                from workflow.measurement_report import (limits_from_pair,
                                                         recorded_thresholds)
                pair = recorded_thresholds(r)
                limits = limits_from_pair(*pair) if pair else {}
        else:
            lim = self._limits_for(r)
            limits, set_id = lim.limits, lim.set_id
        # The row id travels with the pair: see `measurement_report.summarise`
        # for why the column's completeness arithmetic needs it.
        pairs = [(limits.get(row.get("row_id"), Limit.none())
                  if isinstance(limits.get(row.get("row_id")), Limit)
                  else Limit.none(), row.get("word"), row.get("row_id"))
                 for row in rows]
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

    def _one_limit_set(self, runs: list) -> "tuple[list, list]":
        """``(in the report, left out of it)``: nothing is left out (K31).

        This narrowed a report of ONE profile run to the measurements whose
        own reports were judged against the same set as the window's subject,
        after Knut's 2026-09-16 rule *"only report data using the same judged
        against threshold sets as the judge against setting set in the report
        should be used when writing the report text"*. G7 lifted it across
        places; K31 lifts it everywhere. Knut, #182 5801677743: *"Go for
        option (a) One set for the whole report, always"*: every ticked
        measurement is judged against the report's own set
        (`_judged_by_the_document`), so there is never a second yardstick in a
        report to keep apart, and his 2026-09-16 rule holds by construction.
        """
        return list(runs), []

    def _names_a_standard(self, r: dict) -> bool:
        """Whether this column is judged against a standard's published
        figures, and therefore must carry the caveat.

        **ONE PREDICATE, BECAUSE A SECOND COPY OF IT WENT WRONG.** The notes
        block under the results table and the one-page summary both ask this,
        and the version in the notes block dropped `applies_a_standard`'s
        second argument on the live path: for a column with no saved report it
        passed "" for the stored label and asked the id alone. A run whose
        meta holds a set id this build no longer knows, with a standard's name
        recorded beside it, then printed a green PASS under "ISO 12647-7:2028
        (historical)" with no caveat in the window or the PDF. Found by
        adversary round 40a (F6), driven on screen. Pressing Generate closed
        it, because saving writes the label into the compliance block, so the
        hole was open exactly while the column was live.

        `label_en`, never `set_label`: the latter is translated, and whether a
        promise made to a rights holder is kept must not depend on the
        interface language. `run_limits` fills `label_en` from the run's stored
        label when the id is unknown, which is the case this closes.
        """
        from workflow.compliance_sets import applies_a_standard
        from workflow.measurement_report import recorded_compliance
        comp = recorded_compliance(r) or {}
        lim = self._limits_for(r)
        return applies_a_standard(
            str(comp.get("set_id", "") or "") or getattr(lim, "set_id", ""),
            str(comp.get("set_label", "") or "")
            or getattr(lim, "label_en", "")
            or getattr(lim, "set_label", ""))

    def _judged_label_for(self, r: dict, *, mark_unsaved: bool = True) -> str:
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
        # "(not saved)" IS A CELL MARKER, NOT PART OF THE SET'S NAME. In the
        # Report Results table it qualifies the column; interpolated into a
        # sentence whose subject is the limit set it says the wrong thing
        # entirely, and an adversary round read it back off the screen Knut had
        # been looking at: *"worked out now against this run's limit set
        # ChromIQ default (recommended) (not saved)"*. Marking a live column
        # `_fresh` is what made that branch reachable for a profiling sheet, so
        # the double negative is new the same day as the fix that caused it.
        if r.get("_fresh") and mark_unsaved:
            return label + " " + tr("(not saved)")
        return label

    def _is_in_a_run(self, r: dict) -> bool:
        """Whether this measurement belongs to a ChromIQ run at all."""
        from workflow.run_compliance import run_context_for
        origin, ti3 = r.get("_origin_dir"), r.get("ti3")
        if not (origin and ti3):
            return False
        try:
            return run_context_for(Path(origin) / str(ti3)) is not None
        except Exception:      # noqa: BLE001 — a sentence is never a blocker
            return False

    def _verdict_provenance(self, r: dict, recorded: bool) -> str:
        """The sentence under one run's accuracy table saying where its words
        came from: the saved record, or this run's limit set, now."""
        label = self._judged_label_for(r, mark_unsaved=False)
        # **STATEMENTS ABOUT THE REPORT, NOT ABOUT ChromIQ (#182 K30,
        # challenge B B7; spec 19.1, K18).** "...and this run's current limits
        # do not change it" explained how the app keeps a verdict; the reader
        # of a report holds no run and no limits.
        # **"RECORDED" ONLY OF A SAVED REPORT (B8-948, K18).** Under "New
        # report…", before Generate, every column is a copy judged just now,
        # which carries a verdict like a saved one; the sentence said it was
        # "recorded … when the report was made" of a report not yet made.
        if recorded and self._is_judged_now(r):
            return tr(
                "This sheet is judged against this report's limit set "
                "{label}."
            ).format(label=label)
        if recorded:
            return tr(
                "This verdict was recorded against the limit set {label} when "
                "the report was made."
            ).format(label=label)
        if r.get("_fresh"):
            # A MEASUREMENT IN NO RUN HAS NO "THIS RUN". An i1Profiler export or
            # a bare file opened from Downloads is judged against the window's
            # set, and the same adversary round found it being told about "this
            # run's limit set" for a file that belongs to no run at all.
            if not self._is_in_a_run(r):
                return tr(
                    "This measurement is not in a project, so it has no saved "
                    "report and no run of its own. Its words are worked out "
                    "against the limit set {label}."
                ).format(label=label)
            return tr(
                "This date has no saved report of its own, so its words are "
                "worked out against this report's limit set {label}."
            ).format(label=label)
        # K18 (B8-948): a statement about the report, never about which
        # version of ChromIQ saved it.
        return tr(
            "Nothing is wrong with this report. Its saved file for this sheet "
            "holds the measurements without a PASS or FAIL of its own, so the "
            "results above are worked out against this report's limit set "
            "{label}: they are not a verdict this sheet was given on the day "
            "it was measured."
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

    # ---- the deliberate acts: choose a set, edit the report's limits ----------
    #
    # **K31 (Knut, #182 5801677743): THE LIMIT SET BELONGS TO THE REPORT.**
    # *"changing the reports settings does not change the report, and its
    # binding to a limit set, unless you click Generate Report"*, and of
    # "Unlock this run's limits": *"Maybe it is better to remove it and make
    # the report have full mastery over its own settings and the measurements
    # selected to be included."* So every door below changes the settings of
    # the report on screen and nothing else: no run is bound, locked, unlocked
    # or recalculated, nothing is written to disk, and Generate report is the
    # one act that stores anything. What these doors replaced (a bind of the
    # window's run, the lock and its guards, the recalculation of a run's
    # dated reports, the undo of a refused edit) is listed in §25 of
    # `docs/design/measurement_report_limits.md`.
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
        # False. Found by the on-screen driver, 2026-09-08; the unit test had
        # stubbed this method.
        return box.clickedButton() is ok_btn

    def _report_limits(self):
        """The limits the report on screen is judged against: the loaded
        report's own, or the ones chosen in this window, or the starting
        choice (the run's own default, else Preferences). K31: one set for
        the whole report, whichever run each ticked measurement is in."""
        return (self._document_limits() or self._sticky_limits()
                or self._window_limits())

    def _on_set_chosen(self, index: int) -> None:
        """"Judged against" chose a set: the REPORT's, nothing else (K31).

        **"NOTHING CHANGED" IS ASKED OF WHAT THE PULLDOWN WAS SHOWING (N.1).**
        The box shows the loaded report's set when one is loaded, or the set
        chosen earlier in this window (B8-462), so choosing the starting set
        from there is a real change and must not read as a no-op.

        What happens is `_settings_touched`: the report's setting moves, the
        red line says to press Generate report, and nothing on disk changes.
        A report's own edited numbers (the "This report" column) were the
        other set's, so a new set drops them (K30).
        """
        if self._syncing_limits or index < 0:
            return
        set_id = self._set_combo.itemData(index)
        shown = self._report_limits()
        if not set_id or set_id == shown.set_id:
            return
        from workflow.measurement_report import set_allowed_for_type
        if not set_allowed_for_type(self._report_type_now(), set_id):
            # K36-1: the entry is greyed; a keyboard or a style that ignores
            # the flag must not choose it either.
            self._sync_set_combo_to(shown.set_id)
            return
        self._report_own_limits = None
        self._settings_touched(set_id=set_id)

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

    def _say_not_written(self, run, exc) -> None:
        from ui.warning_sign import warn
        log.warning("could not write %s: %s", run.meta_path, exc)
        warn(self, tr("The run folder could not be written"),
             tr("ChromIQ could not save the change to this run's folder:\n{path}\n\n"
                "The folder or its files may be read-only, on a disk that is "
                "full, or open in another program. Nothing was changed. Make the "
                "folder writable and try again.").format(path=str(run.dir)))

    def _on_open_limits(self) -> None:
        """"Edit limits…": the REPORT's limits window (K30, K31)."""
        self._open_report_limits_window()

    def _run_for_its_own_default(self):
        """The profile run whose own default for new reports the limits
        window may set, or None: the window's run, while measurements of one
        profile run only are loaded (K31). With several places loaded there
        is no one run the choice would be about."""
        ctx = self._run_ctx
        if ctx is None or self._several_runs():
            return None
        # **AND THE REPORT ITSELF MUST BE OF THAT ONE RUN (B8-940, §25.5).**
        # `_several_runs` counts SOURCES, and a Profiling window's history is
        # every run of its project from one source, so a report of three
        # profile runs offered a live "Default for this run" row for the
        # window's run. The row is about the report's run; a report whose
        # ticked measurements lie in more than one profile run has none.
        if len(self._profile_runs_of_the_report()) > 1:
            return None
        return ctx.run

    def _profile_runs_of_the_report(self) -> "set[str]":
        """The profile runs (folders) the ticked measurements lie in; a
        measurement in no run counts as a place of its own."""
        from workflow.run_compliance import run_context_for
        dirs: "set[str]" = set()
        try:
            rows = self._runs_for_report()
        except Exception:                                # noqa: BLE001
            rows = []
        for r in rows or ():
            origin = r.get("_origin_dir") or ""
            c = run_context_for(origin) if origin else None
            dirs.add(str(c.run.dir) if c else f"external:{origin}")
        return dirs

    def _open_report_limits_window(self) -> None:
        """The limits window of THE REPORT ON SCREEN (#182 K30, K31).

        Knut, 5798461562: *"all settings belong to a report, not a specific
        run"*, and 5801677743: *"changing the reports settings does not change
        the report, and its binding to a limit set, unless you click Generate
        Report"*. So the first column is THIS REPORT's limits, editable, and
        its "Used for this report" radios choose the report's set, from every
        report window alike, one profile run or several. Nothing is written
        to any run and nothing is recalculated here: a change is the report's,
        marks it changed (the red line) and is applied by Generate report,
        which asks Update / Create New / Cancel when a report is selected.

        Two things this window may still store, and neither is a report's
        setting: which COLUMNS it shows (a view setting, remembered per
        profile run, K-b), and, with one profile run loaded, the run's own
        DEFAULT for new reports ("Default for this run", K31: *"then the
        default in the Edit limits for that run"*). The Preferences columns
        beside it are the app-wide sets, exactly as from any other door.
        """
        from ui.dialogs.thresholds_dialog import (ReportLimitsColumn,
                                                  ThresholdsDialog)
        from workflow.compliance_sets import (SET_BY_ID, effective_limits,
                                              is_edited, limits_to_json)
        from workflow.run_compliance import RunLimits
        lim = self._report_limits()
        own_run = self._run_for_its_own_default()
        ctx = self._run_ctx
        view_run = ctx.run if ctx is not None else None
        cols_before: list = []
        if view_run is not None:
            try:
                cols_before = list(view_run.load_meta().compliance_columns or [])
            except Exception:                        # noqa: BLE001
                cols_before = []
        column = ReportLimitsColumn(lim, columns=cols_before)
        before = limits_to_json(lim.limits)
        dlg = ThresholdsDialog(
            self._settings, self, run=column, run_editable=True,
            report_column=True, run_default=own_run,
            # K36-1: the radios each row pairs with a report type
            report_type=self._report_type_now(),
            default_type=str(self._settings.get("report_default_type", "")
                             or ""))
        self._report_limits_dialog = dlg          # for a driver
        try:
            dlg.exec()
        finally:
            self._report_limits_dialog = None
        chosen = str(getattr(dlg, "run_set_chosen", "") or "")
        default_chosen = str(getattr(dlg, "run_default_chosen", "") or "")
        edited = column.limits()
        cols_after = column.columns()
        dlg.deleteLater()
        # THE COLUMN CHOICE, a view setting (K-b), back onto the run it is
        # remembered for. It moves no verdict and binds nothing.
        if view_run is not None and cols_after != cols_before:
            from workflow.run_compliance import set_run_columns
            try:
                set_run_columns(view_run, cols_after)
            except OSError as exc:
                log.warning("could not store the column choice: %s", exc)
        # THE RUN'S OWN DEFAULT FOR NEW REPORTS (K31). Written only when the
        # user picked one, and only onto the run the row named.
        if own_run is not None and default_chosen:
            from workflow.run_compliance import (run_default_set_id,
                                                 set_run_default_set)
            was = run_default_set_id(own_run) or self._default_set_id()
            if default_chosen != was:
                try:
                    set_run_default_set(own_run, default_chosen,
                                        self._default_set_id())
                    log.info("new reports of %s now start on %s",
                             own_run.dir, default_chosen)
                except OSError as exc:
                    self._say_not_written(own_run, exc)
        self._forget_limits()
        overrides = self._overrides()
        own = None
        if chosen and chosen != lim.set_id and chosen in SET_BY_ID:
            own = RunLimits(chosen, tr(SET_BY_ID[chosen].label),
                            effective_limits(chosen, overrides),
                            label_en=SET_BY_ID[chosen].label, bound=False)
        elif limits_to_json(edited) != before:
            known = lim.set_id in SET_BY_ID
            own = RunLimits(lim.set_id, lim.set_label, edited,
                            label_en=lim.label_en, bound=False,
                            edited=(is_edited(edited, lim.set_id, overrides)
                                    if known else True),
                            known=lim.known)
        if own is None:
            # NOTHING OF THE REPORT'S CHANGED (K31, found on screen, beta 40).
            # This called `_refresh()`, which re-renders the page and takes
            # what it was drawn with as the new baseline, so a "Judged against"
            # change made BEFORE opening the window stopped counting as a
            # change: the red line went and Generate asked "Nothing was
            # changed for the selected report". A column choice or the run's
            # own default moves nothing on the page, so the controls are
            # synced and the baseline is left alone.
            self._sync_limit_controls()
            self._show_stale_banner()
            return
        log.info("the report's own limits were changed in the limits window "
                 "(%s); no run is written", own.set_id)
        self._report_own_limits = own
        self._settings_touched(set_id=own.set_id)
        if own.set_id != self._set_combo.currentData():
            self._sync_limit_controls()

    def _runs_for_report(self) -> list:
        """**THE MEASUREMENTS THAT ARE TICKED. ALWAYS (B8-590).**

        Knut, 2026-09-20, removing "Show all measurement runs" and everything
        built on it: *"only the selected/ticked measurements shall be part of
        the report when created/updated (always)."*

        It used to read the tick box first and the list second: ON meant the
        whole history minus what was unticked, OFF meant the one measurement
        the window was opened on **and the ticks were not consulted at all**.
        That second branch is the fault he reported twice from the other end:
        several rows ticked and a report of one, and one row ticked and a
        report of a different one. Neither was a conflict rule misfiring; the
        ticks were simply never read.

        The same list drives the window and the PDF, so they always match
        (worst-patch count included, Knut).

        **INSIDE A PDF OF THE PAGE, THE PAGE'S OWN ROWS (M2, B8-1092).** Set
        only by `_as_the_document_was_built` and cleared in its `finally`: the
        rows exactly as the page judged them when it was drawn, so a control
        touched since cannot make the PDF judge them again.
        """
        forced = getattr(self, "_runs_forced", None)
        if forced is not None:
            return list(forced)
        ticked = [r for r in (self._history or [])
                  if self._run_key(r) not in self._hidden_runs]
        if ticked:
            return self._judged_by_the_document(ticked)
        # NOTHING TICKED IS NOT "EVERYTHING", and it is not "nothing" either:
        # the PAGE a reader is looking at falls back to the measurement the
        # window was opened on rather than going blank underneath them.
        #
        # **THIS FALLBACK IS FOR THE VIEW AND MUST NOT REACH THE WRITER
        # (B8-600).** It did, and an adversary round caught it: this method
        # feeds `_runs_for_document` and so `_reports_to_generate`, which
        # decides both what Generate writes AND whether its button is enabled.
        # So with every row unticked the button stayed live and a press would
        # have written a report covering a measurement the user had explicitly
        # unticked, which is the exact opposite of Knut's rule that *"only the
        # selected/ticked measurements shall be part of the report when
        # created/updated (always)"*. `_reports_to_generate` now asks
        # `_nothing_is_ticked` first, so the two questions are answered
        # separately: "what does this page show" and "what would a press
        # write".
        return [self._report] if self._report else []

    def _spans_places(self, runs: list) -> bool:
        """Do *runs* live in more than one PLACE: several profile runs, or
        calibrations of several projects (#182 beta 39, G7)?"""
        from workflow.measurement_report import document_spans_places
        return document_spans_places(
            [r.get("_origin_dir") for r in runs or [] if r.get("_origin_dir")])

    def _judged_by_the_document(self, rows: list) -> list:
        """*rows*, each carrying the verdict of THE REPORT'S limit set.

        **ONE SET FOR THE WHOLE REPORT, ALWAYS (K31; Knut, #182 5801677743:
        "Go for option (a) One set for the whole report, always").** Every
        ticked measurement is judged against the report's own "Judged
        against" set, whichever profile run or project it is in and whatever
        its own report of one date says. That was G7's rule across places
        (5794311113); K31 makes it the rule within one run as well, so the
        difference between one run and several is gone.

        A row's own file is that measurement's own report, and it stays so.
        The page is drawn from COPIES of the rows:

        * a loaded, unchanged report that recorded each measurement's verdict
          (`JUDGED_KEY`, every report of several measurements since G7/K31)
          shows exactly those words, never recalculated under its reader;
        * a row whose file IS the loaded report (a report of one date, or a
          verdict record an earlier ChromIQ wrote for that report) shows the
          words it was saved with;
        * everything else, a new report or one whose settings moved, is
          judged just now against the set "Judged against" names.

        Old verdict records are therefore read-only history: they speak only
        for the report they were written for (§25).

        **A PROFILING WINDOW TOO (K32, Knut on beta 41, #182 5813851807).**
        This used to return a Profiling window's rows untouched, on the
        grounds that a profiling sheet is never graded (§3). Not grading is
        the REPORT TYPE's business: the Printing record already prints INFO
        in every judged cell. What the early return really did was keep each
        sheet's OWN verdict record, so the Printing record listed the rows,
        the graph tabs and the "Judged against" line of the set each sheet's
        automatic report had used (ChromIQ default on every demo sheet), not
        the set the report was made against. Knut chose Custom ISO 12647-7,
        pressed Generate, and got a report headed "Judged against: ChromIQ
        default" without its solids, control strip, gamut and tone rows.
        §25.3 is one set for the whole report, always, and the Printing record
        is a report.
        """
        from workflow.measurement_report import (recorded_document,
                                                 recorded_judgement)
        if not rows:
            return rows
        doc = self._document_settings()
        doc_id = str((doc or {}).get("id") or "")
        lim = self._report_limits()
        out = []
        for r in rows:
            j = (recorded_judgement(doc, self._run_key(r),
                                    r.get("_origin_dir") or "")
                 if doc is not None else None)
            if j is not None:
                # THE DOCUMENT'S WORDS BESIDE THE RECORD'S EXPLANATION (M1,
                # B8-1091): what the document recorded of how the colours
                # were judged (since this fix, `judged_block`), else what the
                # date's own saved report recorded.
                c = self._as_recorded(r, j)
                c.update(j)
                out.append(c)
                continue
            own = recorded_document(r) if doc is not None else None
            if (own is not None and doc_id
                    and str(own.get("id") or "") == doc_id):
                # the loaded report's own file, as it was saved
                out.append(self._as_recorded(r))
                continue
            if doc_id.startswith("file:"):
                # A report written before the document record existed: its
                # one file is the report, and it is shown as it was saved.
                f = Path(doc_id[len("file:"):])
                if (f.name == str(r.get("_report_file") or "")
                        and str(f.parent.parent)
                        == str(r.get("_origin_dir") or "")):
                    out.append(self._as_recorded(r))
                    continue
            out.append(self._judged_live(r, lim))
        return out

    @staticmethod
    def _as_recorded(r: dict, judged: "dict | None" = None) -> dict:
        """*r* as its saved report RECORDED it, for a page that shows the
        verdict that report was saved with (challenge 5 of beta 42, M1,
        B8-1091).

        A row rebuilt from its measurement (`_report_needs_rebuilding`) is
        this version's working of it; its record (`RECORD_KEY`) is the saved
        report completed with the blocks it never had (`_the_saved_record`).
        The session keys (``_origin_dir``, ``_report_file`` …) are the row's.
        A row that was not rebuilt is its own record and comes back as it is.

        *judged*, a report of several dates' `JUDGED_KEY` block: the
        explanation blocks it recorded replace the date's own, and a rule
        block it did NOT record is left out when the date's record was
        rebuilt under a newer rule, exactly as for a report of one date."""
        if not isinstance(r, dict):
            return r
        rec = r.get(RECORD_KEY)
        if not isinstance(rec, dict) and not isinstance(judged, dict):
            return r
        c = dict(rec if isinstance(rec, dict) else r)
        c.update({k: v for k, v in r.items()
                  if k.startswith("_") and k != RECORD_KEY})
        c.pop(RECORD_KEY, None)
        if isinstance(rec, dict) and WORKED_OUT_EARLIER_KEY in rec:
            c[WORKED_OUT_EARLIER_KEY] = True
        else:
            c.pop(WORKED_OUT_EARLIER_KEY, None)
        if isinstance(judged, dict):
            # What the document recorded of the judgement wins; a rule
            # block it did not record did not exist for it (every report
            # of several dates written before this fix).
            for k in EXPLANATION_BLOCKS:
                if k in judged:
                    c[k] = judged[k]
            # The paper patch is the date's own fact, not the document's:
            # a judged block never carried it before this fix, and the
            # date's record answers for it above.
            working = {k: v for k, v in r.items() if k != RECORD_KEY}
            probe = dict(judged)
            probe.setdefault("paper_patch", c.get("paper_patch"))
            if _worked_out_differently(probe, working):
                c[WORKED_OUT_EARLIER_KEY] = True
                for k in ("paper_white_used", "strip_corner_aims"):
                    if k not in judged:
                        c.pop(k, None)
            elif any(k in judged for k in RULE_BLOCKS):
                c.pop(WORKED_OUT_EARLIER_KEY, None)
        return c

    def _worked_out_again(self, r: dict) -> dict:
        """*r* worked out again from what is on disk NOW, for Generate
        (Create New and Update; challenge 5 of beta 42, M4, B8-1094).

        The window's rows were worked out when it read them: a saved report
        that was not stale IS its saved numbers, and a stale one was rebuilt
        then. So a print record written since, a profile renamed away since,
        or a report saved under an older rule was written again from those
        cached inputs: the K37 recipes of the demo package did not raise
        their messages, and a new report with no profile on disk still said
        its strip corners were compared with the profile's prediction.
        Opening a saved report stays a record (§6); a press of Generate reads
        the measurement, its print record and the run's profile again.

        The measurement is the one this row is about (`_measurement_for`, the
        same rule the window reads a saved report's measurement by); where
        no file on disk is it any more, the row is written as it stands,
        which is the only honest source left. Its date and the session keys
        are the row's."""
        from workflow.measurement_report import build_report
        if not isinstance(r, dict):
            return r
        origin = str(r.get("_origin_dir") or "")
        if not origin:
            return r
        # ONE WORKING PER MEASUREMENT PER PRESS (K39-2): the question after
        # the press and the write both ask, and must be given the same rows.
        cache = getattr(self, "_press_cache", None)
        ck = (repr(self._run_key(r)), origin, str(r.get("ti3") or ""))
        if isinstance(cache, dict) and ck in cache:
            hit = cache[ck]
            return r if hit is None else dict(hit)
        new = self._worked_out_again_from_disk(r, origin)
        if isinstance(cache, dict):
            cache[ck] = None if new is r else dict(new)
        return new

    def _worked_out_again_from_disk(self, r: dict, origin: str) -> dict:
        """The body of `_worked_out_again`, uncached."""
        from workflow.measurement_report import build_report
        # The name the report records; the window's own file when it is in
        # this folder (a target renamed since keeps the old name in its
        # reports, `_measurement_for`).
        opened = Path(origin) / Path(str(r.get("ti3") or "")).name
        own = getattr(self, "_ti3", None)
        if own and Path(str(own)).parent == Path(origin):
            opened = Path(str(own))
        try:
            ti3 = self._measurement_for(r, Path(origin), opened)
        except Exception:                              # noqa: BLE001
            ti3 = None
        if ti3 is None and r.get("_fresh"):
            cand = Path(origin) / Path(str(r.get("ti3") or "")).name
            ti3 = cand if cand.is_file() else None
        if ti3 is None:
            log.info("Generate: %s is not on disk as it was, so its row is "
                     "written as the window read it", r.get("ti3"))
            return r
        try:
            new = build_report(ti3, argyll_bin=self._argyll_bin())
        except Exception as exc:                       # noqa: BLE001
            log.warning("Generate: %s could not be worked out again (%s); "
                        "its row is written as the window read it", ti3, exc)
            return r
        for k in ("created", "raw_drift", "report_type"):
            if k in r:
                new[k] = r[k]
        new.update({k: v for k, v in r.items()
                    if k.startswith("_") and k != RECORD_KEY
                    and k != WORKED_OUT_EARLIER_KEY})
        return new

    def _judged_live(self, r: dict, lim) -> dict:
        """A copy of *r* judged against *lim* just now (G7). Cached per row,
        file and yardstick, because the page asks many times per repaint."""
        from workflow.compliance_sets import limits_to_json
        from workflow.measurement_report import stamp_verdict
        thr = limits_to_json(lim.limits)
        key = (self._run_key(r), str(r.get("_report_file") or ""),
               lim.set_id, json.dumps(thr, sort_keys=True, default=str),
               bool(lim.edited))
        cache = getattr(self, "_judged_cache", None)
        if cache is None:
            cache = self._judged_cache = {}
        hit = cache.get(key)
        if hit is not None and hit[0] is r:
            return hit[1]
        c = dict(r)
        stamp_verdict(c, lim.limits, set_id=lim.set_id,
                      set_label=lim.label_en, edited=lim.edited)
        if len(cache) > 4000:
            cache.clear()
        cache[key] = (r, c)
        return c

    def _grey_what_cannot_help(self, live: bool) -> None:
        """With Generate greyed, grey the report settings that cannot un-grey
        it: Report type, Judged against and "Show detailed data".

        Knut, #182 5816794672: *"Changing the settings while Generate Report
        is greyed out and it is not allowed or possible to generate a report,
        then it makes no sense to allow changing settings."* Every reason
        Generate is greyed for is answered in the LIST (tick, untick, add,
        remove a measurement) or not at all, never by these three, so they
        wait for the list and come back with the button. The list, its
        buttons, "Report shown", Edit limits… and Save report as PDF… stay
        live: they are how a reader un-greys Generate, looks at another
        report, or keeps the one on screen.

        Their tooltips stay readable on a greyed control, and the reason
        Generate is greyed is printed under it (`_set_generate_why`).
        """
        for name in ("_type_combo", "_set_combo"):
            w = getattr(self, name, None)
            if w is not None:
                w.setEnabled(bool(live))
                self._say_why_greyed(w, not live)
        # The detail box also answers to the one-page type, which greys it
        # on its own (`_show_that_a_one_page_summary_is_one_sheet`); only
        # the greying is added here.
        det = getattr(self, "_detail_check", None)
        if det is not None and not live:
            det.setEnabled(False)

    #: Dynamic property: a control's own tooltip, kept while it is greyed.
    _OWN_TIP = "_chromiq_tip_before_greyed"
    #: Dynamic property: the tooltip this window put there while greyed.
    _GREYED_TIP = "_chromiq_tip_while_greyed"

    def _greyed_tooltip(self) -> str:
        # Wrapped by hand: a plain-text tooltip is one line, and the reason
        # ran 2600 px wide across the screen on the first photograph.
        import textwrap
        why = str(getattr(self, "_generate_why_full", "") or "")
        head = tr("Greyed, because no report can be generated now.")
        return (f"{head}\n\n" + textwrap.fill(why, 72)) if why else head

    def _say_why_greyed(self, w, greyed: bool) -> None:
        """**A GREYED CONTROL SAYS WHY IT IS GREYED (challenge 3 of beta 42,
        B8-1034).** Report type, Judged against and "Show detailed data" kept
        their ordinary tooltips (*"Changing it changes only the settings…"*)
        while greyed with Generate, so nothing said why they would not open;
        only the sentence under the buttons did. While greyed the tooltip is
        the reason; the control's own tooltip is kept and put back with the
        button. A tooltip the window wrote again meanwhile (the sync pass
        rewrites both pulldowns' on every change) is the one kept."""
        cur = w.toolTip()
        mine = w.property(self._GREYED_TIP)
        if greyed:
            if cur != mine:
                w.setProperty(self._OWN_TIP, cur)
            tip = self._greyed_tooltip()
            w.setProperty(self._GREYED_TIP, tip)
            w.setToolTip(tip)
        elif mine is not None:
            if cur == mine:
                w.setToolTip(str(w.property(self._OWN_TIP) or ""))
            w.setProperty(self._GREYED_TIP, None)
            w.setProperty(self._OWN_TIP, None)

    #: The four graphs a Printing record can carry, in tab order, with the
    #: words the sentence under its results names them by.
    _RECORD_GRAPHS = ("de", "white", "black", "corners")

    def _graphs_drawn_for(self, runs: list) -> "list[str]":
        """Which of the four graphs that need no limit are DRAWN for *runs*:
        shown in the plan and holding at least two dates (a graph of one date
        is the empty frame saying a trend needs two measurements, and the
        PDF prints no graph at all then)."""
        from workflow.measurement_report import report_trend
        charts = {"de": self._trend_de, "white": self._trend_white,
                  "black": self._trend_black,
                  "corners": self._trend_corners}
        series = report_trend(runs)
        out = []
        for chart, _t, metrics, _y, _d, _a, _thr, _l, shown in \
                self._trend_plan():
            key = next((k for k, c in charts.items() if c is chart), None)
            if key is None or not shown:
                continue
            wh = [f for f in (self._trend_extras(chart).get("withheld")
                              or []) if f is not None]
            dated = sum(1 for pt in series
                        if any(acc(pt) is not None for _n, _c, acc in metrics)
                        or any(f(pt) for f in wh))
            if dated >= 2:
                out.append(key)
        return [k for k in self._RECORD_GRAPHS if k in out]

    def _record_graphs_sentence(self, runs: list) -> str:
        """The sentence under a Printing record's results: why it carries no
        graph of a judged metric, and WHICH graphs it does carry (K32, Knut
        on beta 41, #182 5813851807).

        **ONLY THE GRAPHS THAT ARE DRAWN (challenge 2 of beta 42, #5).** It
        named all four whatever was drawn, and a record of one measurement
        draws none: its tabs are empty frames saying a trend needs two
        measurements, and its PDF has no graph at all."""
        head = tr("This report is not graded, so it carries no graph of a "
                  "judged metric: each of those graphs is drawn against its "
                  "limit.")
        drawn = self._graphs_drawn_for(runs)
        if drawn == list(self._RECORD_GRAPHS):
            return tr(
                "This report is not graded, so it carries no graph of a "
                "judged metric: each of those graphs is drawn against its "
                "limit. The graphs it carries show colour accuracy, paper "
                "white, darkest black and the cube corners.")
        if not drawn and len(runs) <= 1:
            return head + " " + tr(
                "It carries no other graph either: a graph needs at least "
                "two measurements, and this report has one.")
        if not drawn:
            return head + " " + tr(
                "It carries no other graph either: the measurements it "
                "covers have no values to draw one from.")
        names = {"de": tr("colour accuracy"), "white": tr("paper white"),
                 "black": tr("darkest black"),
                 "corners": tr("the cube corners")}
        words = [names[k] for k in drawn]
        if len(words) == 1:
            return head + " " + tr(
                "The one graph it carries shows {graph}.").format(
                    graph=words[0])
        return head + " " + tr("The graphs it carries show {graphs}.").format(
            graphs=tr("{list} and {last}").format(
                list=", ".join(words[:-1]), last=words[-1]))

    def _is_judged_now(self, r: dict) -> bool:
        """Whether *r* is a copy `_judged_live` made just now, and so carries
        a verdict no saved report holds yet (B8-948)."""
        cache = getattr(self, "_judged_cache", None) or {}
        return any(v[1] is r for v in cache.values())

    def _nothing_is_ticked(self) -> bool:
        """True when the user has unticked every measurement there is.

        Asked of the LIST, not of `_runs_for_report`, because that method
        deliberately falls back to the loaded measurement so the page is not
        blank. A window with no measurements at all is not "nothing ticked" —
        there is nothing to tick — so it answers False and the ordinary
        emptiness checks handle it.
        """
        keys = [k for kind, _si, k in getattr(self, "_list_rows", [])
                if kind == "run" and k]
        if not keys:
            return False
        return all(k in self._hidden_runs for k in keys)

    def _metric_table(self, dates: list, data_rows: list) -> str:
        """One metric×run table: a wide, no-wrap Metric column, dated run columns,
        a rule under the header row and a light-grey background on every other
        data row (Knut)."""
        thb = f"border-bottom:1.5px solid {_C['rule']}"
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

        # THE METRIC COLUMN KEEPS ITS SHARE (beta 37, H1). Once it could wrap,
        # Qt's table layout gave it whatever the dates left, and a PDF of six
        # dates came out with "Grey / balance / of the / grey / ramp" one word
        # a line. A fixed share of the width keeps a label on one or two
        # lines, and `_chunked_metric_tables` then fits the dates beside it.
        th = ("<tr><th align='left' width='" + _METRIC_COL_SHARE + "' style='"
              + thb + ";padding:2px 14px 3px 0'>"
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
            body.append(f"<tr{bg}><td width='{_METRIC_COL_SHARE}' style='padding-right:14px'>"
                        + html.escape(label) + "</td>" + "".join(cells) + "</tr>")
        # page-break-inside:avoid keeps a whole chunk-table together — if it won't
        # fit, it moves to the next page rather than splitting rows (Knut #PDF4).
        # **IN THE WINDOW, NOT QUITE ALL OF THE PAGE (challenge 2 of
        # beta 42, #3).** A table of width 100% is laid out one pixel wider
        # than the page (Qt rounds the Metric column's percentage share up,
        # `_TABLE_FIT_SLACK_PX`), and in the window that pixel made the page
        # wider than the view: a horizontal scroll bar of one pixel under
        # every report with a metric table. `_SCREEN_TABLE_WIDTH` leaves that
        # pixel inside the page at every window width and follows a resize,
        # which a width in pixels would not. The PDF keeps 100% of the
        # paper's text width.
        width_attr = str(getattr(self, "_table_width_attr", "") or "100%")
        return (f"<table width='{width_attr}' cellpadding='4' cellspacing='0' style='border-collapse:"
                "collapse;font-size:11px;margin-bottom:10px;"
                "page-break-inside:avoid'>"
                + "".join(body) + "</table>")

    def _chunked_metric_tables(self, runs: list, row_getters: list) -> str:
        """Stacked metric×run tables, at most :data:`_MAX_RUN_COLS` dated columns
        each, continuing below with the Metric column repeated; oldest run first.

        **AS MANY COLUMNS AS FIT ON THE PAGE, MEASURED, NOT ASSUMED** (round B
        before beta 37, H1). Six was a count chosen for English with short
        labels, and the table was cut off at the PDF's right margin: eleven
        dates of the Threshold series lost three verdict columns off the
        paper, four German dates lost "(empfohlen)" and a date's last digit,
        and English broke "(recommende/d)" mid-word. The Metric column now
        wraps, and each table is laid out at the PDF's text width before it
        is used: the largest column count whose tables fit that width with no
        word broken across two lines wins, and the dates are shared out
        evenly over as many tables as that takes.
        """
        days = [str(r.get("created") or "")[:10] for r in runs]
        shared = {d for d in days if days.count(d) > 1}

        def table(chunk) -> str:
            dates = [((str(r.get("created") or "")[:10],
                       str(r.get("created") or "")[11:16])
                      if str(r.get("created") or "")[:10] in shared
                      else str(r.get("created") or "")[:10])
                     for r in chunk]
            rows = [(label, None if get is None else [get(r) for r in chunk])
                    for label, get in row_getters]
            return self._metric_table(dates, rows)

        floor_cols = max(1, int(getattr(self, "_table_min_cols", 1) or 1))

        def split(k: int) -> "list[list]":
            n = len(runs)
            if floor_cols > 1:
                # THE WINDOW FILLS EACH TABLE BEFORE STARTING THE NEXT (K32):
                # "at least 4 columns ... before braking the table", so five
                # dates at four a table are 4 + 1, never shared out as 3 + 2.
                return [runs[i:i + k] for i in range(0, n, k)]
            m = -(-n // k) if n else 0
            out, i = [], 0
            for j in range(m):
                size = n // m + (1 if j < n % m else 0)
                out.append(runs[i:i + size])
                i += size
            return out

        # **THE WIDTH OF THE MEDIUM IT IS DRAWN FOR (K32).** The PDF's text
        # width for the PDF; the page's own width in the window, never fewer
        # than `_SCREEN_MIN_RUN_COLS` dates a table (Knut: "at least 4
        # columns ... before braking the table"). The window was fitted to the
        # PDF's 679 px however wide it was, and so showed what the paper had
        # room for, with "plenty of space between columns".
        width = float(getattr(self, "_table_width", None) or _PDF_TEXT_W)
        floor = max(1, min(len(runs),
                           int(getattr(self, "_table_min_cols", 1) or 1)))
        best: "list[str]" = []
        for k in range(min(_MAX_RUN_COLS, max(1, len(runs))), floor - 1, -1):
            best = [table(c) for c in split(k)]
            if all(_table_fits_the_page(t, width) for t in best):
                break
        return "".join(best)

    def _screen_table_width(self) -> float:
        """The width a metric table has in the window's page, in pixels: the
        report view's viewport less the document's margins (K32).

        Read when the page is drawn. Before the window is first shown the
        viewport has no size of its own yet, and the window's own width is
        the better guess of what it will have."""
        view = getattr(self, "_view", None)
        if view is None:
            return _PDF_TEXT_W
        vp = view.viewport().width()
        if not view.isVisible():
            vp = max(vp, self.width() - 40)
        margin = view.document().documentMargin() if view.document() else 4.0
        return max(200.0, float(vp) - 2.0 * float(margin) - 2.0)

    def _scope_html(self, runs: list, dropped: "list | None" = None) -> str:
        """Report Scope (Knut): which profiles + instruments are included, the run
        count and date range, and red warnings for mixed instruments or missing
        cube colours.

        *dropped* is what `_one_limit_set` left out of this document. A
        measurement that is loaded and not in the report has to be named here,
        or the window quietly describes fewer sheets than the list beside it
        shows, which is the honesty rule the "hidden by you" note below already
        follows.
        """
        from workflow.measurement_report import report_scope
        sc = report_scope(runs)
        kind = self._report_kind(runs)
        verification = kind == "verification"
        calibration = kind == "calibration"
        # **WHERE EACH MEASUREMENT COMES FROM (#182 K30, challenge B B8 and
        # B10).** Grouped by chart name alone, a report across two runs of
        # one project listed "...-verify · 5 verification runs", and the
        # several-runs notice that points here could not be answered from
        # it. Across places, and for a calibration, each group is now its
        # PLACE: the project and run, or the project's calibration.
        if calibration or self._spans_places(runs):
            from collections import Counter
            groups: "dict[tuple, dict]" = {}
            for r in runs:
                pl = self._places_of([r])
                proj, num = pl[0] if pl else ("", "")
                chart = str(r.get("chart") or "?")
                if calibration:
                    label = (tr("{project}, calibration").format(project=proj)
                             if proj else chart)
                elif proj:
                    label = (tr("{project}, run {n}").format(project=proj,
                                                             n=num)
                             if num else proj)
                    if chart and chart != proj:
                        label += " (" + chart + ")"
                else:
                    label = chart
                g = groups.setdefault((proj, num, chart),
                                      {"name": label, "instruments": [],
                                       "n": 0})
                g["instruments"].append(r.get("instrument")
                                        or "Unknown instrument")
                g["n"] += 1
            sc = dict(sc)
            sc["profiles"] = [
                {"name": g["name"], "n": g["n"],
                 "instrument": Counter(g["instruments"]).most_common(1)[0][0]}
                for g in groups.values()]

        # **A DATED VERIFICATION IS A MEASUREMENT, NOT A RUN (B8-928).**
        # Three dates of one profile run read "· 3 verification runs" while
        # the list header and the running header of the same report said
        # "3 measurements"; there was one profile run.
        def _count_label(n: int) -> str:
            if calibration or verification:
                return tr("measurement") if n == 1 else tr("measurements")
            return tr("profile run") if n == 1 else tr("profile runs")

        items = "".join(
            "<li>" + html.escape(p["name"]) + ", "
            + html.escape(tr("Instrument: {inst}").format(inst=p["instrument"]))
            + f" <span style='color:{_C['faint']}'>· {p['n']} "
            + html.escape(_count_label(p["n"]))
            + "</span></li>"
            for p in sc["profiles"])
        d0, d1 = sc["date_range"]
        ind = "margin:0 0 0 1.6em"
        # **SINGULAR OVER ONE ENTRY (B8-951).** The headings were plural
        # whatever the list under them held: "The following profiles'
        # measurement runs are included:" over one profile's one run, and
        # "calibration measurements" over "· 1 measurement". A heading about
        # groups counts the groups; one about measurements counts them.
        n_groups = len(sc["profiles"])
        n_total = sum(int(p.get("n") or 0) for p in sc["profiles"])
        #
        # **THE DICTIONARY'S THREE TERMS (K36-3, Knut #182 5820871320).** A
        # group under a verification is one verification run (the checks of
        # one profile run), under a calibration one calibration run (one per
        # project), and each counts its dated measurements; a profiling
        # report counts profile runs, one profiling measurement each. The
        # headings said "profile verification run" and "profile's measurement
        # run", two terms nothing defined.
        if verification:
            intro = (tr("The following verification run is included:")
                     if n_groups == 1
                     else tr("The following verification runs are "
                             "included:"))
        elif calibration:
            intro = (tr("The following calibration run is included:")
                     if n_groups == 1
                     else tr("The following calibration runs are "
                             "included:"))
        elif n_total == 1:
            intro = tr("The following profile run is included:")
        else:
            intro = tr("The following profile runs are included:")
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
        #
        # AND AIR BEFORE THE LINE UNDER IT. Knut, 2026-09-11: *"add a new line
        # as empty space before the text 'The following profile verification
        # runs are included:'"*. The description is a heading for the section
        # and was sitting four pixels above the sentence, so the two read as
        # one paragraph. `_gap()` is the report's own empty line, used under
        # every section heading, so the spacing matches the rest of the
        # document rather than inventing a margin here.
        #
        # AND IT IS LABELLED AS A DESCRIPTION. Knut, 2026-09-14, reading the
        # demo package's own description off the top of this section:
        #
        #   "The values change in the report, but the Report scope is not
        #    updated and is constantly saying: 'Grey and tone check, ChromIQ
        #    tight … Limits: bound to ChromIQ tight, and still open …'. This
        #    text, and possibly much of the other text in a report, is not
        #    updated when I change report type or judged against."
        #
        # Every word of that paragraph is the RUN'S DESCRIPTION, a field a
        # person writes, and the package's own descriptions name a report type
        # and a limit set because he asked for them to (2026-09-11: *"Be
        # specific in the explanation, so that user understands that chosen
        # limits are bound to chosen 'ChromIQ default' thresholds"*). So a
        # description can contradict the live lines above it, and unlabelled it
        # reads as one of them. It is the same trap for any user who writes
        # "judged with ChromIQ tight" in the box and later changes the set.
        #
        # The label is faint and the description keeps its weight, because it
        # is still the heading of this section, which is what he asked for.
        desc = self._run_description(runs)
        # SEVERAL RUNS OR PROJECTS: THE HEADING STAYS, AND SAYS WHY THERE IS
        # NO DESCRIPTION UNDER IT (K28, B8-798). In the dim note colour, not
        # the description's bold, because it is the document speaking and not
        # something a person wrote.
        several = "" if desc else self._several_places_notice(runs)
        out = (_h2(tr("Report Scope")) + _gap()
               + (f"<div style='color:{_C['faint']};margin:0'>"
                  + html.escape(tr("Run description")) + "</div>"
                  + f"<div style='font-weight:bold;margin:0 0 4px'>"
                  + html.escape(desc) + "</div>" + _gap() if desc else "")
               + (f"<div style='color:{_C['faint']};margin:0'>"
                  + html.escape(tr("Run description")) + "</div>"
                  + f"<div style='color:{_C['dim']};margin:0 0 4px'>"
                  + html.escape(several) + "</div>" + _gap()
                  if several else "")
               + "<div>" + html.escape(intro)
               + "</div><ul style='margin:2px 0 6px'>" + items + "</ul>"
               + "<div><b>" + html.escape(tr("No. of Measurements:")) + "</b></div>"
               + f"<div style='{ind}'>{sc['total']}</div>"
               + "<div><b>" + html.escape(tr("Date range:")) + "</b></div>"
               + f"<div style='{ind}'>{html.escape(d0)} – {html.escape(d1)}</div>")
        # WHICH METRICS THIS KIND OF REPORT JUDGES, when it judges fewer than
        # the limit set defines. Knut, on beta 32: the Grey and tone check
        # showed three rows while the set had thresholds for far more, and
        # nothing anywhere said that was deliberate. Silent on every type that
        # judges everything, because there is nothing to explain there.
        _covers = self._type_covers_sentence()
        if _covers:
            out += (f"<div style='color:{_C['faint']};margin:6px 0 0'>"
                    + html.escape(_covers) + "</div>")
        # Honesty note: a filtered report must say it is filtered, so it can
        # never pass as the complete history (Sebastian, 2026-08-10).
        # COUNT WHAT THE USER UNTICKED, not what is missing from the list.
        # This was `len(self._history) - len(runs)`, which is the same number
        # only while the ticks are the only thing that narrows a report. The
        # one-page summary narrows to a single measurement by its nature, and
        # the sentence then told a user who had unticked nothing that they had
        # hidden a run.
        # A FILTERED REPORT MUST SAY IT IS FILTERED, IN THE DOCUMENT'S OWN
        # VOICE. Knut, beta 20: *"the text must be written as if it is a
        # separate document printed for a customer, and that customer knows
        # nothing of the Measurement Report windows, buttons, selections that
        # can be made or changed ... shall only contain data and results
        # relating to that one report's settings, and not show information
        # that other reports exist with other 'judged against' threshold
        # sets."*
        #
        # So the two red blocks that stood here are gone: one said "runs in the
        # list above are hidden by you (unticked)", which names a list the
        # reader of a printed sheet cannot see, and the other named every
        # measurement left out AND the limit set each was judged against,
        # twelve of them on the demo project, which is exactly the "other
        # reports exist" he ruled out.
        #
        # What replaces them keeps Sebastian's honesty rule (a filtered report
        # may never pass as the complete history) without borrowing the
        # window's vocabulary: it states what this document covers, counted
        # against what the run holds. Whether they were unticked or judged on
        # other numbers is the same fact to the reader: not in here.
        covered = len([r for r in runs if not _is_raw_drift(r)])
        # THE RUN'S OWN MEASUREMENTS, NOT EVERYTHING LOADED. `self._history` is
        # every row in the window's list, and a person can load a second
        # project's measurement beside this one: round 11 photographed "This
        # report covers 1 of the 2 measurements recorded for this run" printed
        # under "No. of Measurements: 1" on a run that holds exactly one, the
        # other belonging to a different project. The sentence says "for this
        # run", so the total is the run's own rows, which includes the ones
        # left out (unticked, or judged on other numbers) and excludes another
        # project's.
        # The grouping is the PROJECT, not the run: a report can hold several
        # runs of one project (they are comparable, which is the point), and a
        # measurement left out of one of them is still this project's. Another
        # project's is not.
        def _project_of(_r) -> str:
            # RESOLVED, BECAUSE TWO SPELLINGS OF ONE FOLDER ARE ONE PROJECT.
            # These keys are grouped as strings, and on macOS `/tmp` and
            # `/private/tmp` name the same directory: a project holding four
            # measurements, two of them opened by each spelling, was counted
            # TWICE and the document said "2 of the 8 measurements recorded for
            # the projects it is drawn from" (R14-F4, photographed). A symlink
            # or a mapped drive does the same thing on the other platforms.
            from workflow.run_compliance import run_context_for
            _o = str(_r.get("_origin_dir") or _r.get("ti3") or "")
            try:
                _c = run_context_for(_o)
                if _c:
                    _d = _c.run.dir.parent.parent
                    try:
                        return str(_d.resolve())
                    except OSError:    # the folder has gone since it was read
                        return str(_d)
                # ...AND A FOLDER THAT HAS BEEN RENAMED IS STILL A PROJECT.
                # `run_context_for` is strict on purpose and asks the disk, so
                # renaming a project in Finder while its report is open makes
                # every row of it answer "belongs to no project": the document
                # then has no project to count against and the honesty note
                # disappears, which is a filtered report passing as complete
                # (R14-F5). The path's own shape still says which project it
                # was, and grouping is all that is wanted here.
                # ...RESOLVED HERE TOO. The disk branch above resolves its key
                # and this one did not, so a renamed project went straight back
                # to counting `/tmp` and `/private/tmp` as two projects: one
                # project, four measurements, and the document said "recorded
                # for THE PROJECTS it is drawn from" (R14-F4's exact symptom,
                # brought back by R14-F5's own fix and caught by round 15).
                try:
                    _pp = Path(_o).resolve()
                except OSError:
                    _pp = Path(_o)
                _parts = list(_pp.parts)
                if "runs" in _parts:
                    _i = len(_parts) - 1 - _parts[::-1].index("runs")
                    if _i > 0:
                        return str(Path(*_parts[:_i]))
                return f"external:{_o}"
            except Exception:      # noqa: BLE001 — a count is never a blocker
                return f"external:{_o}"

        # COUNTED OFF THE DISK, NOT OUT OF THE WINDOW. `self._history` is
        # what somebody has LOADED, and the sentence says "recorded for this
        # project": round 12 drove a project holding three measurements, loaded
        # two of them, and the document said "covers 1 of the 2"; loading the
        # third made the same document say "2 of the 3" with nothing else
        # changed (B8-346 F5). The project's own folder is the only thing that
        # can answer "recorded".
        #
        # AND A FILE THAT BELONGS TO NO PROJECT IS NOT IN EITHER NUMBER. A
        # colleague's `.ti3`, opened beside the project's own, was counted as
        # one of its measurements ("covers 2 of the 3" where the project
        # records two), and in the other direction it padded the covered count
        # until the sentence fell silent on a project that really was being
        # filtered (B8-346 F6). Both numbers now count only the rows that
        # belong to a project this report is about.
        # **THE DISK'S OWN IDENTITY, NOT THE SPELLING.** `resolve()` fixes a
        # symlink and `/private/tmp`, and it does NOT case-fold: APFS is
        # case-insensitive, so `.../CaseTest/runs/run1` and
        # `.../casetest/runs/run1` are one directory by `samefile` and two keys
        # after `resolve()`. Driven in the real window, one project holding
        # four measurements with two rows opened through the other case said
        # "covers 3 of the 8 measurements recorded for THE PROJECTS it is drawn
        # from" (R16-F1, photographed) -- R14-F4's symptom again, and this time
        # in BOTH branches. It is reachable because `FileManager.root_dir()` is
        # the custom output path verbatim, so a project carries the case typed
        # in Settings while a `.ti3` added through the file dialog carries the
        # volume's.
        #
        # A directory's device and inode agree across every spelling of it
        # that names the same mounted file: `/tmp` and `/private/tmp`, a
        # symlink, a firmlink (`/Users/...` and `/System/Volumes/Data/Users/...`
        # are one directory and `resolve()` does not collapse them), and a
        # different capitalisation on a case-insensitive volume. It is NOT
        # universal: two MOUNTS of one filesystem give different `st_dev` for
        # the same directory, so a share mounted twice would still split one
        # project in two. That case is a mechanism, not something anybody has
        # driven here, and it is recorded rather than guessed at.
        #
        # A folder that has gone has neither number, and then the resolved path
        # is the best identity there is.
        def _ident(_p: str) -> str:
            try:
                _st = os.stat(_p)
                return f"{_st.st_dev}:{_st.st_ino}"
            except OSError:
                return _p

        _mine: "dict[str, str]" = {}
        for _p in (_project_of(r) for r in runs):
            if not _p.startswith("external:"):
                _mine.setdefault(_ident(_p), _p)
        covered = len([r for r in runs
                       if not _is_raw_drift(r)
                       and _ident(_project_of(r)) in _mine])
        # A FOLDER THAT HAS GONE IS NOT A PROJECT WITH NOTHING IN IT. Rename a
        # project in Finder while its report is open and the disk count drops
        # to zero, `max(total, covered)` makes the two equal, and the sentence
        # disappears -- so a filtered report passes as complete, which is the
        # one thing Sebastian's rule two paragraphs up exists to prevent
        # (R14-F5). Where the folder cannot be read, the rows this window holds
        # for that project are the best count there is, which is what this
        # counted before it counted the disk at all.
        # **A NUMBER ONLY WHEN THE DISK CAN GIVE ONE.** A folder that has been
        # renamed or removed cannot be counted, and the two ways of guessing
        # round it were both worse than not guessing: counting the window's own
        # rows can never exceed what the report covers when the window holds
        # only this report's rows, so the sentence vanished (R17-F2); and
        # remembering the last count the folder gave produced a WRONG one, "3
        # of the 5" on a four-measurement project and "3 of the 4" on a project
        # whose folder had been emptied (R18-F3). So: every folder readable,
        # and the sentence carries numbers; any folder not, and it says the
        # same thing without them, which is still Sebastian's honesty rule and
        # claims nothing the app cannot stand behind.
        # THE REPORT'S OWN KIND, AND A VERIFICATION'S OWN RUNS (K14): a
        # profiling document is counted against the project's profiling
        # measurements, a verification document against the dated
        # verifications of the runs it is drawn from. A document mixing the
        # two kinds keeps the old count of everything.
        _kinds = {bool(r.get("is_verification")) for r in runs
                  if not _is_raw_drift(r)}
        _kind = ("verification" if _kinds == {True} else
                 "profiling" if _kinds == {False} else None)
        # THE RUNS OF EVERY ROW IN THE "INCLUDED MEASUREMENTS" LIST, not only
        # of the rows the document kept. Knut's own scope: *"the measurements
        # selected in included measurements input box"*. The first cut took
        # the DOCUMENT's rows, so a ticked measurement of another run that one
        # limit set per document leaves out also left its run out of the
        # total, and the sentence saying the report is filtered vanished: an
        # existing guard caught it the same hour.
        _run_names: "set[str] | None" = None
        if _kind == "verification":
            from workflow.run_compliance import run_context_for as _rcf
            _run_names = set()
            for r in list(runs) + list(getattr(self, "_history", None) or []):
                if not r.get("is_verification"):
                    continue
                _c = _rcf(str(r.get("_origin_dir") or ""))
                if _c is not None:
                    _run_names.add(_c.run.dir.name)
            _run_names = _run_names or None
        _counts = [self._measurements_recorded_in(_p, _kind, _run_names)
                   for _p in _mine.values()]
        _all_known = bool(_counts) and all(n > 0 for n in _counts)
        # A measurement with no saved report beside it is still in this
        # document, so the total can never be smaller than what is covered.
        total_known = max(sum(_counts), covered)
        if not _all_known:
            _held = len([r for r in self._history
                         if _ident(_project_of(r)) in _mine])
            if covered < _held:
                # ONE PROJECT OR SEVERAL, HERE TOO. The numbered branch below
                # learned this as R13-3 and this one was written without it, so
                # a document drawn from two projects with one folder unreadable
                # said "does not cover every measurement recorded for THIS
                # project" with the Report Scope naming both of them in the
                # same picture (R19-1, photographed).
                note = (tr("This report does not cover every measurement "
                           "recorded for this project.")
                        if len(_mine) == 1 else
                        tr("This report does not cover every measurement "
                           "recorded for the projects it is drawn from."))
                out += (f"<div style='color:{_C['dim']};margin-top:6px'>"
                        + html.escape(note) + "</div>")
        elif covered < total_known:
            # ONE PROJECT OR SEVERAL, AND THE SENTENCE SAYS WHICH. A report can
            # hold runs of more than one project -- the window lets a second be
            # opened beside the first -- and the total is then the sum of two
            # folders. "This project" was still the wording, so a document
            # covering a two-measurement project and a five-measurement one
            # said "2 of the 7 measurements recorded for this project", and no
            # project on the disk records seven (R13-3, photographed).
            # SCOPED BY KIND (K14), so a reader of a Printing record is told
            # "of the 3 measurements recorded for this project's profile runs"
            # and not a number that counts every verification of every run as
            # well; a verification's is the spec's own "for this run".
            if _kind == "profiling":
                note = (tr("This report covers {n} of the {total} measurements "
                           "recorded for this project's profile runs.")
                        if len(_mine) == 1 else
                        tr("This report covers {n} of the {total} measurements "
                           "recorded for the profile runs of the projects it is "
                           "drawn from."))
            elif _kind == "verification" and len(_mine) == 1:
                # "PROFILE RUN", AND A COUNT RATHER THAN "these runs" (round
                # 2B, #4/#10): on the same page "1 verification run" means a
                # date, so a bare "run" was ambiguous, and "these runs" named
                # runs the PDF never lists.
                _nr = len(_run_names or ())
                note = (tr("This report covers {n} of the {total} measurements "
                           "recorded for this profile run.")
                        if _nr <= 1 else
                        # K39-1: "it was chosen from" named the choosing
                        # done in the window; the report says what it is
                        # drawn from, as the other lines here do.
                        tr("This report covers {n} of the {total} measurements "
                           "recorded for the {runs} profile runs it is drawn "
                           "from."))
            elif _kind == "verification":
                note = tr("This report covers {n} of the {total} measurements "
                          "recorded for the profile runs of the projects it is "
                          "drawn from.")
            else:
                note = (tr("This report covers {n} of the {total} measurements "
                           "recorded for this project.")
                        if len(_mine) == 1 else
                        tr("This report covers {n} of the {total} measurements "
                           "recorded for the projects it is drawn from."))
            note = note.format(n=covered, total=total_known,
                               runs=len(_run_names or ()))
            out += (f"<div style='color:{_C['dim']};margin-top:6px'>"
                    + html.escape(note) + "</div>")
        return (out + self._scope_deleted_runs_html()
                + self._worked_out_earlier_html(runs)
                + self._scope_warnings_html(sc["warnings"])
                + self._scope_notes_html(sc.get("notes") or []))

    @staticmethod
    def _worked_out_earlier_html(runs: list) -> str:
        """One line when a measurement on the page is shown with the verdict
        an earlier version saved, and this version would work it out
        differently (challenge 5 of beta 42, M1, B8-1091): the page is the
        record (§6), its notes are the record's, and the reader is told once
        that a newer report would be worked out the current way
        (M-REPORT-WORKED-OUT-EARLIER; K39-1: report text names no button,
        Knut 5831246553). Empty
        for a new report, whose rows are this version's. Never raises."""
        try:
            if not any(isinstance(r, dict) and r.get(WORKED_OUT_EARLIER_KEY)
                       for r in runs or []):
                return ""
        except Exception:                              # noqa: BLE001
            return ""
        from workflow import measurement_messages as M
        title, body = M.M_REPORT_WORKED_OUT_EARLIER.render()
        return (f"<div style='color:{_C['dim']};margin-top:10px'><b>"
                + html.escape(title) + "</b><br>" + html.escape(body)
                + "</div>")

    def _scope_deleted_runs_html(self) -> str:
        """#182 A6 (Knut, 5817809396): the shown report covered a profile run
        that has since been deleted, and Report Scope says so.

        The bar's Delete renumbers the later runs, and a saved report's
        reference to the deleted run becomes ``runs/runN.deleted``, which no
        folder answers: the page then shows fewer measurements than the report
        was written about, and until beta 42 only an Update said why
        (M-REPORT-UPDATE-LEAVES-OUT). The words are M-REPORT-SCOPE-RUN-DELETED.
        Empty for "New report…" (nothing saved is shown) and for a report
        that names no deleted run. Never raises."""
        try:
            entry = self._document_being_updated()
        except Exception:                              # noqa: BLE001
            entry = None
        if not entry:
            return ""
        from workflow import measurement_messages as M
        from workflow.measurement_report import (deleted_runs_of,
                                                 measurement_place)
        doc = entry.get("doc") or {}
        gone = deleted_runs_of(doc)
        if not gone:
            return ""
        projects = set()
        for m in (doc.get("measurements") or []):
            if isinstance(m, dict) and m.get("dir"):
                try:
                    projects.add(measurement_place(str(m["dir"]))[0])
                except Exception:                      # noqa: BLE001
                    pass
        runs = M.deleted_runs_label(gone, len(projects) > 1)
        title, body = M.M_REPORT_SCOPE_RUN_DELETED.render(count=len(gone),
                                                          runs=runs)
        return (f"<div style='color:{_C['dim']};margin-top:10px'><b>"
                + html.escape(title) + "</b><br>" + html.escape(body)
                + "</div>")

    def _scope_notes_html(self, notes: list) -> str:
        """Report Scope's PLAIN notes, in the dim note colour.

        Separate from `_scope_warnings_html` because that method paints its
        whole block in the FAIL colour under the word "Warning", and Knut was
        explicit that the one note here is *"not an error"*. Keeping them in
        two methods means a note cannot become red by being appended to the
        wrong list.
        """
        if not notes:
            return ""
        blocks = []
        for n in notes:
            if n["kind"] != "patch_counts":
                continue
            from workflow.measurement_messages import (
                M_REPORT_PATCH_COUNTS_DIFFER)
            # THE COUNTS AS A SENTENCE, NOT AS A PYTHON LIST. `str(list)`
            # would put "[1617, 918]" into a document. Plain ", " is what every
            # other list in this file joins with (the cube-corner names, the
            # instrument list), so it stays the same here.
            counts = ", ".join(str(c) for c in n["counts"])
            title, body = M_REPORT_PATCH_COUNTS_DIFFER.render(counts=counts)
            paras = "".join("<div style='margin-top:4px'>" + html.escape(para)
                            + "</div>" for para in body.split("\n\n"))
            blocks.append("<div><b>" + html.escape(title) + "</b></div>"
                          + paras)
        if not blocks:
            return ""
        # **A NOTE THAT LOOKS LIKE A NOTE (R4, Knut 2026-09-22):** *"different
        # charts with different number of patches can still be a clear
        # information note, not the same font and colour as other bread-text,
        # so that the note is not hidden."* It was body text in the dim
        # colour. It is now a tinted box with a full-ink bar down its left
        # edge and full-ink text: set apart in colour and form, and in no hue
        # that reads as a warning, because it is not one (adversary round 40c
        # measured exactly that about this note). A one-row table, because
        # Qt's rich text draws a table cell's background reliably in the
        # window and in the PDF, and a div's border it does not.
        return ("<table cellspacing='0' cellpadding='0' width='100%' "
                "style='margin-top:10px'><tr>"
                f"<td width='4' bgcolor='{_C['head']}'>&nbsp;</td>"
                f"<td bgcolor='{_C['panel']}' style='padding:8px;"
                f"color:{_C['head']}'>" + "".join(blocks) + "</td>"
                "</tr></table>")

    @staticmethod
    def _measurements_recorded_in(project_dir: str, kind: "str | None" = None,
                                  run_names: "set[str] | None" = None) -> int:
        """How many measurements a project's folder holds, read from the disk.

        Every run's own measurement plus every dated verification of every run.

        **OF THE REPORT'S OWN KIND, AND FOR A VERIFICATION OF ITS OWN RUNS (K14,
        Knut on beta 34).** *"This report covers 1 of the 18 measurements
        recorded for this project" ... is wrong, as this demo project has 3
        runs (profile runs, when run type is Profiling) ... it should only show
        relating to run type is Profiling.* So ``kind="profiling"`` counts only
        the runs' own sheets, and ``kind="verification"`` only the dated
        verifications, of the runs in ``run_names`` when it is given. ``None``
        is the old count of both.
        Role-named files (`preconditioning.ti3`, `merged.ti3`, the
        `reads/readN.ti3` snapshots that are averaged back into the run's own)
        are not measurements in this sense and are not counted: what is counted
        is what the window would show as a row.

        Never raises: the count decorates a sentence and a missing folder or an
        unreadable manifest must not cost the reader the report.
        """
        try:
            from core.file_manager import VERIFICATIONS_DIRNAME
            root = Path(project_dir) / "runs"
            if not root.is_dir():
                return 0
            # ROLE-NAMED, SO NOT A MEASUREMENT. `preconditioning.ti3` is
            # inherited from the parent run and `merged.ti3` is the average of
            # two; neither is a sheet anybody read, and `reads/readN.ti3` lives
            # in its own folder and is averaged back into the run's own.
            roles = {"preconditioning.ti3", "merged.ti3"}
            n = 0
            for d in sorted(root.iterdir()):
                if not (d.is_dir() and d.name.startswith("run")):
                    continue
                if run_names is not None and d.name not in run_names:
                    continue
                if kind != "verification":
                    n += len([f for f in d.glob("*.ti3")
                              if f.name not in roles])
                if kind == "profiling":
                    continue
                # A DATED VERIFICATION IS FOUND BY ITS FOLDER, NOT BY ITS NAME.
                # `Verification.measurement_ti3` resolves `<the run's stem>.ti3`,
                # so a verification measured from a different chart is invisible
                # to it: measured on a two-date fixture holding `Alpha.ti3` and
                # `Bravo.ti3`, it found one of the two.
                for v in sorted((d / VERIFICATIONS_DIRNAME).glob("*")):
                    if v.is_dir() and any(v.glob("*.ti3")):
                        n += 1
            return n
        except Exception:      # noqa: BLE001 — a count is never a blocker
            return 0

    @staticmethod
    def _document_places(runs: list) -> "tuple[set[str], set[str]]":
        """``(runs, projects)`` the DOCUMENT's measurements come from.

        A run is its folder; a measurement in no run (a calibration, a file
        outside any project) counts as a place of its own, because no run's
        description is about it. A project is the folder carrying the
        manifest (`project_root_for`), so a calibration is counted in its
        project; a file in none is its own."""
        from workflow.run_compliance import project_root_for, run_context_for
        run_keys: "set[str]" = set()
        projects: "set[str]" = set()
        for r in runs or ():
            origin = str(r.get("_origin_dir") or r.get("ti3") or "")
            ctx = run_context_for(origin) if origin else None
            run_keys.add(str(ctx.run.dir) if ctx is not None
                         else f"external:{origin}")
            root = project_root_for(origin) if origin else None
            projects.add(str(root) if root is not None
                         else f"external:{origin}")
        return run_keys, projects

    def _run_description(self, runs: "list | None" = None) -> str:
        """What the user wrote about the document's run, or "".

        **THE DOCUMENT'S MEASUREMENTS DECIDE, NOT THE WINDOW'S SOURCES
        (B8-798).** This asked whether the window held several SOURCES, and a
        single project source spans every run of its project: a Printing
        record of three profile runs printed run1's description under Report
        Scope as if it described all three. It also read the WINDOW's run, so
        a window on run2 with only run1's sheet ticked printed run2's. Now the
        description is read from the one run the document's measurements come
        from, and a document drawn from several has none
        (`_several_places_notice` says so instead).

        *runs* None keeps the old question, for a caller with no document.
        """
        if runs is None:
            ctx = self._run_ctx
            if ctx is None or len(self._distinct_run_dirs()) > 1:
                return ""
            run = ctx.run
        else:
            run_keys, _projects = self._document_places(runs)
            if len(run_keys) != 1:
                return ""
            only = next(iter(run_keys))
            if only.startswith("external:"):
                return ""
            from core.file_manager import Run
            run = Run.for_dir(Path(only))
        try:
            return str(run.load_meta().description or "").strip()
        except Exception as exc:                 # noqa: BLE001 — a heading
            log.debug("could not read the run description: %s", exc)
            return ""

    def _several_places_notice(self, runs: list) -> str:
        """What stands under "Run description" when the document has no one
        run to describe, or "" when it has (K28; Knut, #182 5795087247, on
        B8-798): *"The report should under the 'Run Description' heading
        inform the user that the report includes data from multiple runs (or
        multiple projects (when that is specified), thus not written here.
        Then refer back to the Scope section for which measurements are
        included from which projects."*

        Written for the reader of the document (K18): what it holds and where
        in it to look, nothing about how ChromIQ came to leave it out. The
        list it points at is Report Scope's own, directly below it, which
        names each project and how many measurements come from it."""
        run_keys, projects = self._document_places(runs)
        if len(projects) > 1:
            return tr("This report includes measurements from several "
                      "projects, so no single run description is given. The "
                      "list below shows the measurements included from each "
                      "project.")
        if len(run_keys) > 1:
            return tr("This report includes measurements from several "
                      "profile runs, so no single run description is given. "
                      "The list below shows the measurements included.")
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
                        "Every measurement in a report should come from the same "
                        "instrument and the same printer; the report cannot tell "
                        "printers apart. These measurements use a different "
                        "instrument from the majority ({dom}):").format(dom=w["dominant"]))
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
                # NOT PRINTED ANY MORE, AND DELIBERATELY. This named every
                # other limit set a column had been judged against, which is
                # the thing Knut ruled out of the document in beta 20: *"shall
                # only contain data and results relating to that one report's
                # settings, and not show information that other reports exist
                # with other 'judged against' threshold sets."* It was already
                # unreachable, because `_one_limit_set` narrows the runs before
                # this is asked, so nothing on a sheet changes today; the
                # branch stays, empty, so that a future change to that
                # narrowing meets this ruling rather than the old paragraph.
                continue
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
                        "These measurements are missing one or more of the eight "
                        "cube corners, so their cube-corner figures are less "
                        "meaningful:"))
                    + "</div><ul>" + lis + "</ul>")
        return (f"<div style='color:{_C['fail']};margin-top:10px'>"
                + "".join(blocks) + "</div>")

    def _rows_the_results_show(self, runs: list) -> "list[str]":
        """The metric rows Report Results lists for *runs*, in the table's order.

        **ONE ANSWER TO ONE QUESTION (B8-463).** `_report_results_html` worked
        this out for the table and `_how_to_read_html` explained four fixed
        bullets beside it, so the guide and the table described different sets
        of metrics. Knut, beta 25: *"Whatever metrics are shown in Report
        Results: each metric used in the report shall have a corresponding
        explanation of each metric in the 'How to read this report' section …
        The bullet list of parameters explained is then changing with which
        metrics the report contains."* Both now ask this.
        """
        from workflow.compliance_sets import ROWS
        verd = {}
        for r in runs:
            rows, _rec = self._verdict_rows(r)
            verd[id(r)] = {(x.get("row_id") or x.get("key")) for x in rows}
        return [row.id for row in ROWS
                if any(row.id in verd[id(r)] for r in runs)]

    def _explained_row_groups(self) -> "set[str] | None":
        """Which row GROUPS this document's results table can contain.

        None when the type shows every row. A type with a row filter explains
        only what it shows: "Grey and tone check" drops the five colour-accuracy
        rows, and the guide above them went on describing "the ΔE00 across the
        patches, split so you can see the bulk of the chart", which is a
        paragraph about rows that are not in the document. The same shape as the
        note that told a reader to add patches to a chart that already had them.
        """
        from workflow.compliance_sets import ROWS
        from workflow.measurement_report import rows_for_report_type
        keep = rows_for_report_type(self._report_type_now())
        if keep is None:
            return None
        return {r.group for r in ROWS if r.id in set(keep)}

    def _how_to_read_html(self, present: "list[str] | None" = None, *,
                          standard: bool = False, split: bool = False,
                          calibration: bool = False) -> str:
        """The plain-language guide. The heading sits OUTSIDE its background frame,
        with a blank line above it like every other section heading (Knut).

        **AND ITS BULLET LIST IS THE RESULTS TABLE'S OWN ROWS (B8-463).** It
        used to be four fixed bullets about two row GROUPS and two report
        sections, whatever the table underneath actually listed: a report
        judged against a set that puts a limit on the control strip, the solid
        inks or the outer gamut showed those rows with no explanation anywhere,
        and a set that puts none still explained the grey ramp. Knut asked for
        one explanation per metric shown, and for the list to follow the
        metrics. `present` is the same list the table is built from
        (`_rows_the_results_show`); None means "work it out", which is what a
        caller with no runs to hand gets.
        """
        from workflow.compliance_sets import ROW_BY_ID
        # `_explained_row_groups` is no longer consulted HERE: the four
        # hand-written bullets it filtered are gone (B8-592), and the metric
        # bullets that replaced them are already exactly the rows the results
        # table shows, so there is nothing left to filter by group. It is kept
        # because it is the honest answer to "which groups can this type
        # contain" and `tests/test_the_guide_explains_only_the_rows_the_
        # document_has.py` asks it that question directly.

        def _metrics() -> str:
            """One bullet per metric row the results table lists, named by the
            row's OWN label and described by its own one-line blurb, so a
            metric is described in one place and reads the same wherever it
            appears."""
            out = []
            for rid in (present or []):
                row = ROW_BY_ID.get(rid)
                if row is None or not row.blurb:
                    continue
                out.append("<li>" + html.escape(
                    tr("{metric}: {explanation}").format(
                        metric=MeasurementReportDialog._row_name(self, rid),
                        explanation=tr(row.blurb)))
                    + "</li>")
            return "".join(out)

        try:
            _grades_nothing = self._ungraded_by_type()
        except Exception:              # noqa: BLE001 — a bare guide, no window
            _grades_nothing = False
        body = (
            "<p>" + html.escape(tr(
                "This report compares what the instrument measured against the "
                "chart's design colours (the reference values the chart was built "
                "from). Most numbers are colour differences in \u0394E00: 0 is a "
                "perfect match, 1\u20132 is barely visible, and 10 or more is "
                "clearly different. The others name their own unit: \u0394Ch "
                "for a colour cast, \u0394L* for a lightness difference, L* for "
                "a lightness.")) + "</p>"
            # **ONE LIST, AND EVERY NAME IN IT IS A REAL METRIC'S OWN NAME
            # (B8-592).** Knut, 2026-09-20: *"The report text section 'How to
            # read this report' lists all the metrics that a report uses, but
            # it is not ONE list, but split into TWO. Why? … Should this not
            # be re-written to be ONE bullet list? Do that.... Make sure all
            # the correct names for each metric is used in the description."*
            #
            # It was two: four hand-written bullets, then the line "Every
            # metric this report judges, and what it means:", then one bullet
            # per judged row. The first list was not a second view of the
            # second one. Measured against `compliance_sets.ROWS`:
            #
            # * "Colour accuracy" and "Grey balance" name row GROUPS, not
            #   metrics. Behind the first stand five rows and behind the
            #   second two, and every one of them was already in the second
            #   list under its real name, so the reader met the same numbers
            #   twice under two different vocabularies.
            # * "Paper white & darkest black" and "Cube corners" are REPORT
            #   SECTION headings. Neither is a row in `ROWS` at all: there is
            #   no "darkest black" metric and no "Cube corners" metric. Worse,
            #   both were written with no row group, which meant they survived
            #   every filter: a "Grey and tone check", which judges three grey
            #   and ramp rows and prints neither section, explained both.
            #
            # So the hand-written four are gone and what is left is the list
            # that was always correct: the rows the results table actually
            # judges, each under the label the table, the limits window and
            # the PDF all use for it.
            + ("<ul>" + _metrics() + "</ul>" if _metrics() else "")
            # ONE WORD PER BULLET. Knut, 2026-09-11: *"This paragraph must
            # describe each 5 words, one at a time in a bullet list, organised
            # and orderly, not in a messy bulk."* Every clause of the
            # paragraph it replaces is still here; only the shape changed,
            # plus the closing sentence covered by the note below.
            + "<p><b>" + html.escape(tr("The five verdict words.")) + "</b> "
            + html.escape(tr(
                "A limit set is one column of the limits table: the numbers a "
                "report is judged against. Every row of the results ends in "
                "one of five verdict words.")) + "</p>"
            "<ul>"
            "<li>" + html.escape(tr(
                "PASS: the measured value is within the limit for that "
                "row.")) + "</li>"
            "<li>" + html.escape(tr(
                "FAIL: the measured value is over the limit for that "
                "row.")) + "</li>"
            # COND IS AN OVERALL WORD AND NOTHING ELSE, since Knut retired it
            # as a row word on 2026-09-21: *"all metrics being tested against a
            # threshold shows as FAIL or PASS (always, also for the standards),
            # and the COND term is retired"*. The bullet used to open with the
            # row meaning, which is now the one thing it can never mean; the
            # last clause is what it is left saying, and it is the one that was
            # always about the column. Reports saved before that day still hold
            # the word on rows, so the bullet stays: a reader opening one needs
            # it explained, and the last sentence says so rather than leaving a
            # word on screen the guide no longer covers.
            # …AND THE FIRST HALF OF IT WAS THE DELETED RULE. "only partly
            # checked, either because it holds rows this chart could not
            # supply" is the arithmetic Knut's N-A ruling removed on the same
            # day this bullet was written, and the paragraph four lines below
            # it already says the opposite: "a row this chart could not answer
            # is not counted as a failure". One page, two rules. What is left
            # is the clause that is still true, plus the one that says so.
            # …AND THE SECOND HALF WENT THE SAME WAY ONE DAY LATER. The
            # clause left standing, "the column's values are a standard's
            # applied to your chart rather than to that standard's own", was
            # the ISO cap, which Knut retired on 2026-09-22: such a column
            # reads PASS or FAIL like any other now and carries the caveat as
            # a note instead. What is left is the one cause that survives,
            # which is a report saved before 4.3.0 holding the word on a row.
            "<li>" + html.escape(tr(
                "COND (short for conditional): a column's Overall word when a "
                "value in it is over a limit that is recommended rather than "
                "required. Rows do not use this word, and a row the test chart "
                "used could not answer does not make a column COND: it is not "
                "counted as a failure.")) + "</li>"
            # **INFO, AS IT IS TRUE OF THE DOCUMENT IT IS PRINTED IN (K28;
            # B8-845, question 5).** The bullet listed four causes and said
            # "the note under the results names the rows in the last two
            # cases". Two of the four went: a row this set puts no limit on is
            # no longer in the report at all (K28, item 3), and on a Printing
            # record, which judges nothing, there is no note naming rows, so
            # the promise was false in the one document it was about. What is
            # left is said per type, like the notes heading
            # (`_notes_list_html`).
            "<li>" + html.escape(tr(
                "INFO: the number is shown for information only. This kind "
                "of report judges nothing, so every value in it reads INFO.")
                if _grades_nothing else tr(
                "INFO: the number is shown for information only and nothing "
                "was judged from it. That happens when the sheet is a "
                "profiling measurement, which is never graded, and when the "
                "row needs something about the print that was not recorded; "
                "the note under the results names the rows in that last "
                "case.")) + "</li>"
            # N-A, AS KNUT RULED IT (K28, item 5): a raised number beside the
            # word, pointing at a note that names what the measured chart
            # lacks (K22). "The reason is listed under the results" described
            # the prose list that the numbered notes replaced on 2026-09-21.
            "<li>" + html.escape(tr(
                "N-A (not applicable): the value could not be worked out from "
                "the measured chart. A raised number beside it points to the "
                "note under the results that names what is missing.")) + "</li>"
            "</ul>"
            # WHAT THE REPORT SHOWS, NOT WHAT IT WITHHOLDS. Knut, 2026-09-11,
            # on the sentence that used to close this paragraph, *"and this
            # report never says that anything conforms to a standard"*:
            # *"Rephrase so that report text states what the report shows […]
            # which actually has the opposite effect of building confidence in
            # the report results."* The caveat itself is a fact about the
            # measurement and stays: a standard's figures are written for that
            # standard's own chart and control strip, and ChromIQ measures the
            # chart the user printed. It is now stated as that fact, and the
            # COND cap follows from it.
            #
            # The promise made to Idealliance on 2026-09-09 is that ChromIQ
            # never PRINTS that a print conforms to, is certified to, or
            # qualifies as anything (docs/design/issue_182_answers.md). It is a
            # promise of absence, and deleting a denial keeps it rather than
            # breaking it. The denials a GRANT requires to exist are a
            # different class and are untouched: Fogra's "It is not a
            # certification, approval or endorsement by …" beside every
            # reference set, and Idealliance's trademark line.
            # …AND THE SECOND SENTENCE WAS MADE FALSE BY KNUT'S RULING OF
            # 2026-09-21, which is why it is not the one that was there. It
            # said the Overall reads PASS "only when every row the set
            # requires was checked and passed", and since that day a row the
            # chart cannot answer does not stop a column reading PASS. Found
            # by PHOTOGRAPHING the guide after changing four sentences beside
            # it: the picture had this one in frame and nothing had flagged
            # it, because nothing in the suite reads this paragraph.
            "<p>" + html.escape(tr(
                "A column read as a drift check shows the word “drift” in "
                "every cell instead: it compares one measurement with another "
                "rather than with a limit. A column's Overall word is PASS "
                "when every row that could be checked passed; a row the test "
                "chart used could not answer is not counted as a failure, and "
                "the sentence under the word says how many there were.")) + "</p>"
            # A COLUMN'S NAME IS NOT ITS CONTENTS. The sentence this replaces
            # read "The columns named after a standard hold that standard's
            # published tolerance values", and for the two Custom columns that
            # is false: those start from ChromIQ's own numbers, because the
            # published ones are not ChromIQ's to ship, and every cell in them
            # is the user's to change. A reader holding a report headed "Custom
            # ISO 12647-7" was being told the figures behind it were ISO's. The
            # caveat that caps both at COND is the same for both and is stated
            # once, because it is about what the numbers are applied TO rather
            # than where they came from.
            # AND THE READ-ONLY HALF WAS WRONG IN THE OTHER DIRECTION, which
            # the fifth adversarial round caught within hours. The correction
            # above separated the Custom columns, which do NOT hold a
            # standard's numbers, from the read-only ones, which it then said
            # do. They do not either: `data/compliance_sets/iso12647.json`
            # ships empty by design, so in every build ChromIQ distributes
            # those two columns carry zero published values, and the guide said
            # in ChromIQ's own voice that they carry that standard's. Measured:
            # 30 rows each, 0 of them numeric. The same file already records
            # this exact trap for the Custom blurbs, and the fix for one half
            # wrote the identical claim onto the other.
            #
            # What is true in BOTH states is said instead: it is where those
            # values go, ChromIQ ships none, and a licence holder who supplies
            # them makes the column usable.
            # …AND THE THIRD VERSION WAS FALSE IN THE ONE STATE IT WAS WRITTEN
            # TO COVER. It said those columns "are empty" and "cannot be
            # chosen unless you hold the standard and supply its figures
            # yourself", and this paragraph is the same bytes in every state:
            # with figures supplied the two columns carried 7 and 5 numbers,
            # both appeared in the pulldown, and the guide inside that very
            # report still said they were empty. The second clause had an
            # exception as well, because a run bound to an ISO set carries that
            # choice to a machine holding no figures at all, where the set
            # stays selectable.
            #
            # So selectability is not described here any more, and emptiness is
            # stated as the condition it actually is. Every clause below is
            # true of a build that ships as this one does AND of one a licence
            # holder has pointed at their own file.
            #
            # NOT ON A RECORD THAT GRADES NOTHING (round B before beta 37,
            # H3): a Printing record reads no column PASS or FAIL, so a
            # paragraph saying what such a column's PASS is describes a page
            # the reader is not holding.
            # **ONLY IN A REPORT JUDGED AGAINST A STANDARD'S SET, AND WITHOUT A
            # CONFORMANCE CLAIM (re-challenge R2 of beta 39, #2).** This was
            # printed in every graded report, a ChromIQ default and a
            # calibration report included, pointing at a note under the
            # results that only a column named after a standard carries. It
            # now appears exactly when that note does (`standard`, the same
            # `_names_a_standard` question), and says what was judged and
            # against what; "may differ from the published values" went with
            # §23 and "would likely meet the standard" with K18.
            + (("<p>" + html.escape(tr(
                "A column named after a standard is judged against its limit "
                "set's limits, applied to the values measured on the printed "
                "test chart rather than to that standard's own chart and "
                "control strip. Such a column reads PASS or FAIL like any "
                "other, and the note under the results says what that word "
                "does and does not mean.")) + "</p>")
               if standard and not _grades_nothing else "")
            + ""
            # **"BOUND, AND LOCKED" IS NOT IN THE REPORT (K26, Knut
            # 5792484060, Q2: "Remove it from the report, and make sure this
            # information is in the relevant help text").** It explained how
            # ChromIQ binds and locks a run's limits, which K18 keeps out of a
            # document handed to a customer. The same two sentences are now in
            # the "Judged against" help (`_bound_and_locked_help`) and the help
            # card's glossary.
            "<p>" + html.escape(tr(
                "What the numbers mean depends on how the chart was printed:")) + "</p>"
            "<ul>"
            "<li>" + html.escape(tr(
                "A profiling chart is printed WITHOUT colour management (the raw "
                "print that is measured to build a profile). It is not expected to "
                "match the design closely, so the ΔE can look large, and that is "
                "normal. Here it is the CHANGE between dated reports that matters, "
                "not a single value.")) + "</li>"
            "<li>" + html.escape(tr(
                "A verification chart is printed THROUGH the finished profile, "
                "with the printer's colour management off. It SHOULD match the "
                "design closely, so low ΔE and passes mean the profile is "
                "still accurate; numbers rising over time mean that the "
                "profile describes the printer less well than it did. (Printed "
                "raw instead, the same sheet is a "
                "printer drift check, and the report says which way each sheet "
                "was printed.)")) + "</li>"
            "</ul>"
            # **ONLY WHERE A SHEET WAS SPLIT, AND AS A STATEMENT ABOUT THE
            # REPORT (re-challenge R2 of beta 39, #20).** "Where the report
            # can tell (it asks the run's profile)" described how ChromIQ
            # works, and a calibration report, which has no run profile,
            # printed it too.
            + (("<p>" + html.escape(tr(
                "Some of a chart's design colours can be brighter or more "
                "saturated than this printer and paper can physically produce; "
                "no profile can print them, however good it is. Where a sheet "
                "was compared with its profile's gamut, the colour-accuracy "
                "figures are split into two groups: “Within the "
                "profile's gamut”, the colours that were genuinely "
                "printable, the fair measure of accuracy, and “Beyond "
                "it”, the unreachable ones, whose distance describes the "
                "limit of the gamut, not a mistake of the profile. Every "
                "patch stays counted and visible.")) + "</p>") if split else "")
            # **ONLY WHERE A ROW SHOWN USES THE SPLIT (#182 K30, challenge B
            # B3; spec 22.1).** The sentence ended "the verdict words judge
            # the within-gamut figures" on every report, a Grey and tone
            # check (every grey patch counts) and a Printing record (nothing
            # is judged) included.
            + (("<p>" + html.escape(tr(
                "Where a sheet is split this way, the verdict words of the "
                "colour-accuracy and evenness rows judge the within-gamut "
                "figures.")) + "</p>")
               if (split and not _grades_nothing
                   and set(present or ()) & WITHIN_GAMUT_ROWS) else "")
            # THE CHAIN, WITHOUT A TIP AND WITHOUT A PROFILE THAT IS NOT
            # THERE (re-challenge R2 of beta 39, #20). It closed "Judging the
            # profile on its own is a separate check, made against the
            # measurement the profile was built from", which is advice about
            # another ChromIQ tool (K18), and a calibration's chart is printed
            # with no profile at all, so its chain has two links.
            + "<p>" + html.escape(tr(
                "The ΔE figures measure a whole chain in one number: the "
                "printer's behaviour on the day and the instrument's own "
                "small uncertainty. A rising number means something in "
                "that chain has moved; by itself it does not say which part.")
                if calibration else tr(
                "The ΔE figures measure a whole chain in one number: the "
                "profile's conversion of each colour to printer values, the "
                "printer's behaviour on the day, and the instrument's own "
                "small uncertainty. A rising number means something in "
                "that chain has moved; by itself it does not say which "
                "part.")) + "</p>"
            + ("" if calibration else "<p>" + html.escape(tr(
                "These figures show how one profile holds up over time. They "
                "are not a fair measure for ranking papers or printers "
                "against each other: where a sheet is split by the profile's "
                "gamut, the averages cover only the colours each profile can "
                "print, and that set differs with every paper. A glossy "
                "paper keeps more of the difficult, saturated colours than a "
                "matte one, so its average can look worse while it is "
                "printing better.")) + "</p>") +
            "<p>" + html.escape(tr(
                "Because the design reference never changes, comparing dated "
                "reports of the same chart on the same printer is a clean, "
                "reliable signal of drift: ageing inks, a wandering printer, "
                "or an instrument going off. Screen and print colours here are "
                "approximate; the numbers come from the measurement file and "
                "are exact.")) + "</p>")
        # page_break: the gap batch (2026-08-13) could leave this headline
        # orphaned at a page bottom; a fixed break makes page 2 deterministic.
        return (_h2(tr("How to read this report"), page_break=True) + _gap()
                + "<table width='100%' cellpadding='12' cellspacing='0'>"
                f"<tr><td style='background:{_C['panel']}'>" + body
                + "</td></tr></table>")

    def _report_results_html(self, runs: list,
                             present: "list[str] | None" = None) -> str:
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
        # THE SAME LIST THE GUIDE ABOVE EXPLAINS (B8-463), worked out once by
        # the caller and handed to both, so the two cannot disagree about which
        # metrics this report is about.
        if present is None:
            present = [row.id for row in ROWS
                       if any(row.id in verd[id(r)] for r in runs)]

        _note_nums = self._note_numbering(runs)

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
                tip = self._reason_sentence(x.get("reason"), r, x)
            elif word == COND:
                # A ROW CANNOT BE JUDGED COND ANY MORE, so reaching this line
                # means the report was SAVED with the word and is being read
                # back. The tooltip says that rather than describing a rule the
                # app no longer applies; the verdict itself is left exactly as
                # it was recorded, because a saved verdict is the record §5
                # keeps comparable across dates and rewriting it would change
                # history to make a screen tidy.
                tip = tr("CONDITIONAL: this report was saved by an earlier "
                         "ChromIQ, where a value over a limit the set "
                         "recommended rather than required read CONDITIONAL "
                         "instead of FAIL. The verdict is shown as it was "
                         "recorded. Generate the report again to have it "
                         "judged by today's rule.")
            # THE MARKER, WHICH IS THE HALF OF THE RULING THAT IS EASY TO
            # FORGET. A numbered list nobody is pointed at is a paragraph. The
            # numbers come from the same `numbered_notes` call the list below
            # uses, so the two cannot disagree about which note is note 1.
            from workflow.measurement_report import (note_label,
                                                      note_numbers_for)
            marks = note_numbers_for(x, _note_nums)
            mark = ("<sup style='font-weight:normal'>&nbsp;"
                    + html.escape(" ".join(note_label(n) for n in marks))
                    + "</sup>") if marks else ""
            if marks:
                seen = [self._note_sentence(c) for (n, c, _w) in _note_nums
                        if n in marks]
                seen = [t for t in seen if t]
                if seen and not tip:
                    tip = " ".join(seen)
            title = f" title='{html.escape(tip)}'" if tip else ""
            return (f"<td align='center'{title} style='color:{col};"
                    f"font-weight:{weight}'>{html.escape(word_label(word))}"
                    f"{mark}</td>")

        self._names_split = self._names_within_gamut(runs)

        def label_of(rid):
            row = ROW_BY_ID.get(rid)
            return (self._row_name(rid, runs) if row
                    else _METRIC_LABELS.get(rid, lambda: rid)())

        row_getters = [(label_of(rid), (lambda r, rid=rid: cell(r, rid)))
                       for rid in present]
        detail_on = (getattr(self, "_detail_check", None) is not None
                     and self._detail_check.isChecked())
        if detail_on:
            intro = tr("The following results are extracted from the detailed "
                       "Colour accuracy data shown below for each measurement.")
        elif len(runs) <= 1:
            # K30 (B7, spec 19.1): the report does not tell its reader which
            # checkbox to tick in a window they do not have.
            intro = tr("The following results are extracted from detailed data "
                       "for the included measurements in this report.")
        else:
            intro = tr("The following results are extracted from detailed data "
                       "(Colour accuracy) for the included measurements in this "
                       "report.")
        # **EVERY REPORT SAYS THAT ITS JUDGED FIGURES ARE THE WITHIN-GAMUT
        # ONES (K28, item 1)**, and only where that is TRUE of the rows it
        # shows. It was printed whenever any column was split, so a Grey and
        # tone check, whose rows use every grey patch, and a Printing record,
        # which judges nothing, both told the reader their words judged
        # within-gamut figures.
        if (any(r.get("gamut_split") for r in runs)
                and not self._ungraded_by_type()
                and set(present or ()) & WITHIN_GAMUT_ROWS):
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
                    # K18 (B8-948): about the report, not ChromIQ's past.
                    "A column judged against “not recorded” is not a "
                    "fault, and nothing is missing from it. Its saved file "
                    "holds the measurements without a verdict of its own, so "
                    "its words are worked out against the limit set this "
                    "report is judged against.")) + "</div>")
        if any(r.get("_fresh") for r in runs):
            notes += (
                f"<div style='{note_css}'>" + html.escape(tr(
                    "A column marked “(not saved)” is a measurement with no "
                    "saved report of its own; its words are worked out "
                    "against the limit set this report is judged against."))
                + "</div>")
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
        from workflow.compliance_sets import (SUMMARY_REASONS,
                                              STANDARD_CAVEAT_APPLIED,
                                              STANDARD_CAVEAT_PROOF,
                                              applies_a_standard, summary_text)
        from workflow.measurement_report import recorded_compliance
        # **THE STORED LABEL IS THE SECOND HALF OF THE QUESTION, AND THE LIVE
        # PATH WAS DROPPING IT** (adversary round 40a, F6). `applies_a_standard`
        # takes an id AND the label a run recorded, because a set id this build
        # no longer knows leaves nothing but that label behind, and a column
        # headed "ISO 12647-7:2028 (historical)" is named after a standard
        # whatever its id spells. For a SAVED column the label came from the
        # compliance block; for a live one this passed "" and asked the id
        # alone. Driven on screen on a run whose meta holds a forgotten id with
        # a standard's name stored beside it: green PASS, the standard's name
        # in the column head, and no caveat in the window or the PDF. Pressing
        # Generate closed it, because saving writes the label into the block,
        # so the hole was open exactly while the column was live.
        #
        # `label_en`, not `set_label`: the latter is translated, and whether a
        # promise to a rights holder is kept must not depend on the interface
        # language. `run_limits` fills `label_en` from the stored label when
        # the id is unknown, which is precisely the case this closes.
        _standard_cols = [r for r in runs
                          if not _is_raw_drift(r) and self._names_a_standard(r)]
        # ...AND NOT ON A PRINTING RECORD (round B before beta 37, H3). That
        # type grades nothing, so a sentence saying what a PASS under a
        # standard's name is describes a word the page never prints.
        if _standard_cols and not self._ungraded_by_type():
            # TRANSLATED IN HALVES AND JOINED HERE. `tr()` is a whole-string
            # lookup, so `tr(a + " " + b)` would miss every catalogue and
            # print English in thirteen languages.
            notes += (f"<div style='{note_css}'>"
                      + html.escape(tr(STANDARD_CAVEAT_APPLIED) + " "
                                    + tr(STANDARD_CAVEAT_PROOF)) + "</div>")
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
        # **AND WHY ITS GRAPHS ARE ONLY FOUR (K32, Knut on beta 41, #182
        # 5813851807).** A graph of a judged metric is shown only when one of
        # its rows was judged (§17 item 3, Knut's own rule: "a graph is only
        # shown and printed IF the metric has values tested against a
        # threshold"), and a Printing record judges nothing, so it carries
        # the four graphs that need no limit. Knut read the missing graphs as
        # a fault: "nothing in the report seems to say why metrics are
        # missing, if it was deliberate, or it is a clear bug". Said here,
        # under the results, where the window and the PDF both print it.
        if self._ungraded_by_type() and runs:
            notes += (f"<div style='{note_css}'>"
                      + html.escape(self._record_graphs_sentence(runs))
                      + "</div>")
        # **THE "Not computed on this chart" BLOCK USED TO BE HERE, AND IT IS
        # GONE BECAUSE KNUT REPLACED THE MECHANISM.** It printed every N-A row
        # and its reason as prose under the heading "Not computed on this
        # chart:", which challenge round 32 found false on its face: "The same
        # chart measured again" is not a property of a chart, so every clean
        # first verification ended under a heading that did not describe what
        # it listed. `_mismatch_text` had been corrected for exactly that and
        # this, which feeds the same claim into the report BODY and therefore
        # into every PDF, had not.
        #
        # Knut then ruled the mechanism on 2026-09-21: *"the N-A … should have
        # a super-script number, pointing to a note, where the note explains
        # why it is N-A."* `_note_the_absences` does that, through the same
        # numbering every other note uses, so the explanation now sits beside
        # the cell it is about instead of in a list under a heading that has
        # to be true of all of them at once. Printing both would say the same
        # thing twice on one page under two headings.
        #
        # What the prose block carried and the notes do not is the closing
        # sentence, so that moves to the notes list below.
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
        # …AND THE NUMBERED NOTES, which is Knut's ruling of 2026-09-13 and,
        # since 2026-09-21, his ruling on N-A as well. A note either comments
        # a verdict that stands (what to know when weighing it) or explains
        # one that could not be given at all. Numbered either way, because the
        # cell points at the number, which is what he asked for both times.
        numbered = self._numbered_notes(runs)
        if numbered:
            notes += self._notes_list_html(
                numbered, note_css, closing=self._has_an_absence(runs))
        return (_h2(tr("Report Results"), page_break=True) + _gap()
                + f"<div style='color:{_C['dim']};margin-bottom:4px'>" + html.escape(intro)
                + "</div>" + _gap()
                + self._chunked_metric_tables(runs, row_getters)
                + notes)

    def _notes_list_html(self, numbered: list, note_css: str, *,
                         closing: bool) -> str:
        """The numbered notes as a list, under a heading that is TRUE OF THE
        DOCUMENT it is printed in.

        ONE RENDERER FOR BOTH PLACES THE LIST APPEARS: under the Report Results
        grid and under each run's table in the detailed section (G12). Two
        copies of this markup would be two documents that drift, which is the
        reason the numbering itself lives in one function.

        **ON A TYPE THAT JUDGES NOTHING, NO WORD ABOUT VERDICTS OR FAILURES.**
        The Printing record now prints the notes that explain an absence
        (`_note_the_absences`), and the heading every other type uses, "Notes
        on the verdicts above", would describe verdicts the page never gives;
        its closing sentence would say an unanswered row "is not counted as a
        failure" on a document that counts nothing. Both are chosen here, by
        the same `_ungraded_by_type` that withholds the verdicts.

        *closing* adds the sentence about rows that could not be worked out;
        the caller passes whether any row shown actually reads N-A.
        """
        from workflow.measurement_report import note_label
        record = self._ungraded_by_type()
        items = "".join(
            "<li style='margin-bottom:2px'><b>"
            + html.escape(note_label(n)) + "</b> "
            + html.escape(f"{where}: ") + html.escape(sentence) + "</li>"
            for (n, where, sentence) in numbered)
        head = (tr("Notes on the values above:") if record
                else tr("Notes on the verdicts above:"))
        # THE CLOSING SENTENCE THE PROSE BLOCK USED TO CARRY, kept because it
        # answers the question a reader of an N-A actually has, and reworded
        # to Knut's ruling: an unanswerable row is not a failure. It does not
        # name one remedy for every reason (B8-397); each note above carries
        # its own.
        close = ""
        if closing:
            close = (tr("A value that could not be worked out says nothing "
                        "about the printer; each note above says why.")
                     if record else
                     tr("A row that could not be worked out says nothing about"
                        " the printer and is not counted as a failure;"
                        " each note above says why."))
        return (f"<div style='{note_css}'><b>" + html.escape(head) + "</b>"
                + f"<ol style='margin:2px 0 0 16px;padding:0;"
                f"list-style:none'>{items}</ol>"
                + ("<div style='margin-top:4px'>" + html.escape(close)
                   + "</div>" if close else "")
                + "</div>")

    def _comparison_table_html(self, runs: list) -> str:
        """Side-by-side: the full metric set across every run (columns = dated
        runs, ≤6 per table). Zebra rows, header rule, wide Metric column (Knut)."""
        de = lambda r: (r.get("de00") or {})

        def num(getter, dec):
            return lambda r: f"<td align='right'>{_fmt(getter(r), dec)}</td>"

        def corner_de(r, code):
            # **ONLY A CORNER THE CHART ACTUALLY HAS** -- B8-290. Without the
            # `present` test this column carried the DeltaE00 of whatever patch
            # happened to be nearest, and this table has no "(missing)" mark to
            # warn with: the number simply stood in the Red row. A dash is what
            # `_fmt(None)` draws for every other absent figure here.
            for cc in (r.get("corners") or []):
                if cc.get("name") == code:
                    return cc.get("de") if cc.get("present", True) else None
            return None

        row_getters = []
        # A "–" LIMIT TAKES THE ROW OUT OF THIS TABLE TOO (K28, item 3; Knut,
        # asked whether the Overview follows Report Results: *"Yes."*). Every
        # block below loses the same rows, so within, beyond and all read as
        # one table.
        dash = self._dash_row_ids(runs)
        keys = [k for k in ("avg_all", "avg_low95", "avg_high5", "max_all",
                            "max_low95") if _ROW_ID_OF[k] not in dash]
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
                            for k in keys]
            row_getters.append((tr("Beyond the profile's gamut"), None))
            row_getters.append((tr("Patches"),
                                num(lambda r: gs(r).get("n_out"), 0)))
            row_getters += [(_METRIC_LABELS[k](), num(part("de00_out", k), 2))
                            for k in keys]
            # K31 (Knut, #182 5801677743, section 6: "do as recommended").
            row_getters.append((tr("Within and beyond the gamut together"),
                                None))
        row_getters += [(_METRIC_LABELS[k](), num((lambda r, k=k: de(r).get(k)), 2))
                        for k in keys]
        # **FIGURES THAT NEVER HAVE A LIMIT, UNDER A HEADING THAT SAYS SO (K28,
        # item 4).** Knut, asked whether to keep the spread, the lightest and
        # darkest L* and the eight corner ΔE00 or remove them: *"keep them
        # under a heading 'For information (no limit applies)'"*. The heading
        # is a block row like "Within the profile's gamut" above, so the table
        # stays one table.
        row_getters.append((tr("For information (no limit applies)"), None))
        row_getters.append((_METRIC_LABELS["std"](),
                            num(lambda r: de(r).get("std"), 2)))
        # WHICHEVER SHAPE THE FILE IS IN (R24-F2). These two read `lab` only,
        # so a schema-5 measurement -- ChromIQ's own demo projects hold them --
        # printed a dash here while the detailed section below printed the very
        # same paper white as *L\* 95.4*. `point_lightness` is the one reader.
        from workflow.measurement_report import point_lightness
        _white_num = num(lambda r: point_lightness(r.get("paper_white")), 1)

        def _white_cell(r):
            # #182 A10: a chart with no paper patch reads N-A here too
            if _no_paper_patch(r) and not r.get("paper_white"):
                from workflow.compliance_sets import N_A, word_label
                return ("<td align='right'>"
                        + html.escape(word_label(N_A)) + "</td>")
            return _white_num(r)
        row_getters += [
            (tr("Paper white L*"), _white_cell),
            (tr("Darkest black L*"),
             num(lambda r: point_lightness(r.get("max_black")), 1)),
        ]
        for code in ("W", "K", "R", "G", "B", "C", "M", "Y"):
            lbl = tr("{corner} ΔE00").format(corner=_CORNER_LABELS[code]())
            row_getters.append((lbl, num((lambda r, c=code: corner_de(r, c)), 2)))
        return (_h2(tr("Overview of Measurement Metrics"), page_break=True)
                + _gap() + self._chunked_metric_tables(runs, row_getters))

    def _report_kind(self, runs: list) -> str:
        """"verification" when every included measurement is a colour-managed
        verification (carries CHROMIQ_VERIFICATION), "calibration" when every
        one is a project's calibration (#182 K30, challenge B B2: a
        calibration report was titled "Profiling of Printer"), else
        "profiling" (#130)."""
        from workflow.measurement_report import is_calibration_dir
        if runs and all(is_calibration_dir(r.get("_origin_dir") or "")
                        for r in runs):
            return "calibration"
        return ("verification"
                if runs and all(r.get("is_verification") for r in runs)
                else "profiling")

    @staticmethod
    def _places_of(runs: list) -> "list[tuple[str, str]]":
        """``[(project name, run number)]`` of *runs*, in order, each place
        once (#182 K30, B1): the run number is "" for a calibration."""
        out: "list[tuple[str, str]]" = []
        for r in runs:
            name = MeasurementReportDialog._project_name_for([r])
            num = MeasurementReportDialog._run_number_for([r])
            if not name:
                d = Path(str(r.get("_origin_dir") or ""))
                from workflow.measurement_report import is_calibration_dir
                if str(d) and is_calibration_dir(d):
                    name = _project_target_name(d.parent)
            if name and (name, num) not in out:
                out.append((name, num))
        return out

    def _what_this_report_judges(self, runs: list) -> str:
        """The one sentence that says what a reader is holding.

        Knut, 2026-09-20, correcting a release note of mine: *"It is not the
        chart that is verified, it is the profile that was made in the profile
        run that is verified using a chart, printing it, and measuring it, then
        qualifying the measurements quality using a set of metrics and methods
        compared against the chart data."* Then, on a first draft that named
        only "run 1": *"A person reading the report as a document will not be
        able to trace back where this report comes from, so the project name
        and run needs to be shown, as well as the included measurement dates
        (which usually is in the report)."*

        So it names the project and the run, and POINTS at the dates rather
        than repeating them, because Report Scope already prints the range four
        lines below and two copies of a date range can disagree.

        Verification only. A profiling measurement is not a judgement of
        anything, it is the sheet a profile was built from, and a sentence
        saying otherwise would be the sort of false claim this file keeps
        having to remove.

        Wording approved verbatim by Knut on 2026-09-20.
        """
        if self._report_kind(runs) != "verification":
            return ""
        # ROUND 3B (F5): the project came from `_report_profile_name`, which
        # is the CHART's file stem ("…-verify"), and the run from keys that
        # hold a bare file name, so every verification report said "built in
        # <chart stem>" and named no run; a loose file said "built in
        # loose-measurement", a file that holds no profile. Both are read off
        # the folder the measurement was loaded from now, and a measurement in
        # no project says nothing rather than name a file.
        project = self._project_name_for(runs)
        if not project:
            return ""
        # **SEVERAL PROFILE RUNS OR PROJECTS: NAME THEM ALL (#182 K30,
        # challenge B B1).** This took the first row's project and run, so a
        # report across runs said "This report judges the profile built in
        # P, run 1" over run 2's measurements too.
        places = MeasurementReportDialog._places_of(runs)
        if len(places) > 1:
            where = "; ".join(
                tr("{project}, run {n}").format(project=p, n=n) if n else p
                for p, n in places)
            return tr(
                "This report judges the profiles built in {where}. Each was "
                "verified by printing a chart through its profile, measuring "
                "it, and comparing the measurements with the chart's own aim "
                "values. The measurements it covers, and the profile run each "
                "comes from, are listed under Report Scope."
            ).format(where=where)
        run = self._run_number_for(runs)
        where = (tr("{project}, run {n}").format(project=project, n=run)
                 if run else project)
        return tr(
            "This report judges the profile built in {where}. It was verified "
            "by printing a chart through that profile, measuring it, and "
            "comparing the measurements with the chart's own aim values. The "
            "measurements it covers are listed under Report Scope."
        ).format(where=where)

    @staticmethod
    def _run_number_for(runs: list) -> str:
        """The run a report belongs to, read off the path it was measured in.

        Returned as text and empty when it cannot be read, because a report
        that cannot say which run it came from must say nothing rather than
        guess at "run 1".
        """
        import re as _re

        for r in runs:
            for key in ("_origin_dir", "ti3", "path", "source"):
                v = r.get(key)
                if not v:
                    continue
                m = _re.search(r"runs/run(\d+)(?:/|$)",
                               str(v).replace("\\", "/"))
                if m:
                    return m.group(1)
        return ""

    @staticmethod
    def _project_name_for(runs: list) -> str:
        """The project a report's measurements were loaded from: the folder
        that holds ``runs/runN``, by its ``project.json`` target name when that
        can be read. Empty for a measurement in no project."""
        for r in runs:
            v = r.get("_origin_dir")
            if not v:
                continue
            import re as _re
            from pathlib import PurePosixPath
            posix = str(v).replace("\\", "/")
            parts = PurePosixPath(posix).parts
            for i in range(len(parts) - 2, 0, -1):
                if (parts[i] == "runs"
                        and _re.fullmatch(r"run\d+", parts[i + 1])):
                    root = Path("/".join(parts[:i]) or "/")
                    try:
                        doc = json.loads((root / "project.json").read_text(
                            encoding="utf-8"))
                        name = str(doc.get("target_name") or "").strip()
                    except (OSError, ValueError, AttributeError):
                        name = ""
                    return name or root.name
        return ""

    def _report_profile_name(self, runs: list) -> str:
        """The dominant profile/chart name across the included runs.

        Final round FC-6 (open, B8-811): a verification's chart is
        "<project>-verify", so the title names the chart's file rather than
        the profile. Which one Knut wants is his call; the title design
        (and its Preferences toggle) predates it."""
        from collections import Counter
        names = [r.get("chart") for r in runs if r.get("chart")]
        # EVERY CHART, WHEN THE REPORT HOLDS SEVERAL (#182 K30, B1): the
        # title named the most common one over a report of two projects.
        distinct = list(dict.fromkeys(names))
        if len(distinct) > 1 and self._spans_places(runs):
            return ", ".join(distinct)
        return Counter(names).most_common(1)[0][0] if names else ""

    def _report_title(self, runs: list) -> str:
        """The report's first-page title from the user's Preferences → Reports
        prefixes: "<prefix>[ - <profile name>]" — NO date/time (the report shows
        its Created date inside; Knut). The prefix is the profiling or
        verification line depending on the included measurements (#130)."""
        # THE DEFAULT IN THE REPORT'S LANGUAGE, A USER'S OWN AS TYPED (round
        # B before beta 37, H5): every German PDF was headed "Measurement
        # Report - Verification of Profile".
        from core.settings import report_title_prefix
        kind = self._report_kind(runs)
        prefix = report_title_prefix(
            self._settings, "report_title_verification"
            if kind == "verification"
            else "report_title_calibration" if kind == "calibration"
            else "report_title_profiling")
        parts = [prefix.strip() or tr("Measurement Report")]
        if self._settings.get("report_add_profile_name", True):
            name = self._report_profile_name(runs)
            if name:
                parts.append(name)
        return " - ".join(parts)

    def _report_filename(self, runs: list) -> str:
        """Filesystem-safe PDF name = the title PLUS the date/time (which the
        title itself omits): "<title> - <date_time>.pdf" (#130, Knut).
        self._created is ISO "YYYY-MM-DDTHH:MM:SS" → "YYYY-MM-DD_HH-MM-SS".

        **THE DOCUMENT'S TIME, THE SAME ONE ITS "Created:" LINE PRINTS (K12).**
        This read `self._created`, the second the WINDOW opened, so every PDF
        saved from one window carried the same stamp: Knut generated a new
        report, saved it, and was offered the previous PDF's name. B8-461 had
        already moved the page's own line to `_doc_created`; the file name was
        left behind on the window's clock."""
        import re
        # WHAT THE PAGE IS, recorded when it was drawn (round A, A-3/A-6):
        # the document's creation time while it still speaks, the window's
        # clock when the page is no longer that document, and the last update
        # appended, so an updated report is not offered the earlier PDF's name.
        page = getattr(self, "_page_doc_created", None)
        when = (page if page is not None
                else getattr(self, "_doc_created", "")) or self._created
        dt = when.replace("T", "_").replace(":", "-")
        upd = str(getattr(self, "_page_doc_updated", "") or "")
        if page and upd:
            dt += " - updated " + upd.replace("T", "_").replace(":", "-")
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
        # K32: the metric tables are fitted to the medium this body is for.
        self._table_width = (_PDF_TEXT_W if for_pdf
                             else self._screen_table_width())
        self._table_width_attr = "100%" if for_pdf else _SCREEN_TABLE_WIDTH
        self._table_min_cols = 1 if for_pdf else _SCREEN_MIN_RUN_COLS
        # K31: whether the judged names say "within gamut" in this document.
        self._names_split = self._names_within_gamut(runs)
        # A plain "Created: …" line — at the top of the window body, and under
        # the title + spectrum line in the PDF (Knut). The profile line that used
        # to be here is dropped; Report Scope already lists it.
        # **THE DOCUMENT'S OWN CREATION TIME, NOT THIS WINDOW'S (B8-461).**
        # `self._created` is the second the window opened, so a report saved in
        # November and loaded today announced itself as made today, under an
        # entry whose name said November. Knut: *"They should be the same."*
        # `_doc_created` is empty whenever no saved document is on the page
        # ("New report…", an unsaved measurement), and then the window's own
        # clock is the right answer and is what is used.
        _page = getattr(self, "_page_doc_created", None)
        when = html.escape((created or (_page if _page is not None
                                        else getattr(self, "_doc_created", ""))
                            or self._created).replace("T", " "))
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
        # ONE LIMIT SET PER DOCUMENT. Before the title, the head line, the PDF
        # file name and every table, for the same reason the one-page summary
        # narrows here: each of them is a claim about the sheets in the report,
        # and a sheet that is not in it may not be counted in any of them.
        runs, _other_sets = self._one_limit_set(runs)
        # **NAME THE TYPE THE DOCUMENT ACTUALLY IS, ALWAYS.** Knut,
        # 2026-09-14, with two PDFs of the same run attached: *"The top of the
        # Report scope also does not show the report type generated."* The
        # guard used to be `_tid != REPORT_TYPE_FULL`, so the DEFAULT type
        # produced a document that never said what it was, and his two files
        # prove it: the Grey-and-tone one carries this line and the Full colour
        # check one carries nothing at all. The paragraph above about T2 being
        # "today's report unchanged" was our reasoning for the silence, not his
        # ruling, and he has now asked for the opposite.
        #
        # An UNBUILT type renders as the full report, so the type NAMED here is
        # the one that was produced, never the one that was asked for. That is
        # the half of the old guard worth keeping: naming a document after a
        # report it is not is worse than saying nothing.
        _produced = _tid if report_type_is_built(_tid) else REPORT_TYPE_FULL
        _head_bits = [html.escape(tr("Report type:")) + " "
                      + html.escape(tr(report_type_name(_produced)))]
        # …AND WHAT IT WAS JUDGED AGAINST, in the same place. It was in the
        # document already, in the "Judged against" row of Report Results and
        # again under each run's own table, and both follow the pulldown
        # correctly; what was missing is a line where a reader opening a saved
        # PDF looks first. Knut: *"there are texts that should state correct
        # report type used and judged against."*
        #
        # ONE SET, OR NONE NAMED. Two profile runs can be bound to different
        # sets, and one name at the head of a document covering both would be a
        # claim about columns it does not describe. The per-column row below
        # already answers that case and keeps answering it.
        _sets = {self._judged_label_for(r, mark_unsaved=False)
                 for r in runs if not _is_raw_drift(r)}
        if len(_sets) == 1:
            _head_bits.append(html.escape(tr("Judged against:")) + " "
                              + html.escape(_sets.pop()))
        # ONE LINE, NOT TWO. The one-page summary is exactly that, one page,
        # and `test_and_keeps_room_for_a_description_of_ordinary_length` keeps
        # 60 px of margin under it so the next sentence anybody adds does not
        # silently make it two. Two new lines here spent 30 of those 60. The
        # separator is the report's own middle dot.
        created_line += ("<div style='margin:2px 0 0;font-weight:bold'>"
                         + " &middot; ".join(_head_bits) + "</div>")
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
                    + head + self._one_page_html(runs, _other_sets) + "</div>")
        _present = self._rows_the_results_show(runs)
        # WHAT THE READER IS HOLDING, before anything else in the document.
        # See `_what_this_report_judges`: a printed page that never says which
        # project and run it came from cannot be traced back to either.
        _judges = self._what_this_report_judges(runs)
        if _judges:
            head = head + ("<div style='margin:6px 0 0'>"
                           + html.escape(_judges) + "</div>")
        # WHAT THE GUIDE MAY SAY ABOUT THIS DOCUMENT (re-challenge R2, #2 and
        # #20): the standard's paragraph only where a column names one (the
        # same question the note under the results asks), the gamut split only
        # where a sheet was split, and a calibration's chain has no profile.
        from workflow.measurement_report import is_calibration_dir
        _graded_runs = [r for r in runs if not _is_raw_drift(r)]
        parts = [head, self._scope_html(runs, _other_sets),
                 self._how_to_read_html(
                     _present,
                     standard=any(self._names_a_standard(r)
                                  for r in _graded_runs),
                     split=any((r.get("gamut_split") or {}).get("de00_in")
                               for r in runs),
                     calibration=bool(runs) and all(
                         is_calibration_dir(str(r.get("_origin_dir") or ""))
                         for r in runs)),
                 self._report_results_html(runs, _present)]
        if for_pdf and charts_html:
            parts.append(
                _h2(tr("Trend over time"), page_break=True) + _gap()
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
                f"font-size:{_BODY_TEXT_PX}px\">"
                + "".join(parts) + "</div>")

    def _runs_for_document(self) -> list:
        """Which measurements the document on screen is about.

        `_runs_for_report` answers "what is loaded", which is what the history
        list and the trend charts want. The DOCUMENT can be narrower: a one-page
        colour summary is about a single sheet. Both the body and the Generate
        report button ask this, because they must agree — the button iterated
        the wider list and wrote a file into every dated verification folder
        while the page in front of the user described one of them, and
        `_say_generated` is deliberately quiet on success, so nothing said so.
        """
        from workflow.measurement_report import (REPORT_TYPE_SUMMARY,
                                                 report_type_is_built)
        runs = self._runs_for_report()
        tid = self._report_type_now()
        if tid == REPORT_TYPE_SUMMARY and report_type_is_built(tid):
            runs = self._one_measurement(runs)
        # …AND ONE LIMIT SET, exactly as `_report_body_html` narrows it. The
        # two must agree: the button files a report for every measurement this
        # answers, and a measurement the document does not describe must not
        # get a file claiming it does.
        return self._one_limit_set(runs)[0]

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

    # **NO LIST OF UNCHECKED ROWS ON THE ONE-PAGE SUMMARY (K28, item 5 and
    # 7: "Keep option 1").** `_unchecked_rows_for` and its cap
    # `_ONE_PAGE_UNCHECKED_MAX` were built for option 3 and never called
    # (design-R3-R2-R1, beta 36). Knut: *"The reference numbers on all N-A
    # results, which points to notes that give explanations, this is the
    # information stating what was left out. Thus no other info needs to be
    # repeated after that. This also applies to the one-page summary."* So
    # both are deleted rather than left for someone to wire in.

    @staticmethod
    def _one_page_summary(sm):
        """The column summary as THIS page may state it.

        **THIS PAGE CANNOT KEEP THE PROMISE THE SENTENCE MAKES, SO IT MUST NOT
        MAKE IT.** Knut ruled on 2026-09-22 that the unchecked values shall be
        listed where there are any. On the full report they are: the numbered
        notes under the results table name every one, with the reason. This
        page has no results table and, measured, no room for one more line:
        `test_the_one_page_summary_prints_on_one_page` requires 60 px of
        headroom and the page has 33 with a single extra line on it, on the
        fixture's own run. A document whose entire promise is that it is one
        page may not become two to carry a list.

        So the ISO sentence loses its "listed below" clause HERE and keeps it
        everywhere the list exists. That is the truthful half of his ruling;
        the other half is put to him, because listing them here and keeping
        this a one-page document are two requirements of his that cannot both
        hold as they stand.
        """
        # …BUT IT STILL SAYS HOW MANY, AND WHY (round B before beta 37, M1).
        # Dropping the clause left "12 of 20 values checked, all within this
        # limit set's values." with not a word about the other 8, while the
        # same page under ChromIQ's own sets says "The other 8 could not be
        # worked out from this measurement". The one-page sentences below say
        # that, and point at no list.
        from workflow.compliance_sets import SUMMARY_REASONS
        import dataclasses
        swap = {SUMMARY_REASONS.get("iso_with_unchecked"):
                SUMMARY_REASONS.get("iso_partial_page"),
                SUMMARY_REASONS.get("iso_with_one_unchecked"):
                SUMMARY_REASONS.get("iso_partial_page_one")}
        new = swap.get(getattr(sm, "reason", None))
        if new:
            return dataclasses.replace(sm, reason=new)
        return sm

    def _one_page_evenness_html(self, r: dict) -> str:
        """The one-page summary's evenness paragraph, or "" when no evenness
        row was judged on this sheet."""
        from workflow.compliance_sets import (FAIL, PASS, ROW_BY_ID,
                                              word_label)
        from workflow.measurement_report import EVENNESS_ROWS
        rows, _rec = self._verdict_rows(r)
        judged = [x for x in rows
                  if (x.get("row_id") or x.get("key")) in EVENNESS_ROWS
                  and x.get("word") in (PASS, FAIL)]
        if not judged:
            return ""
        words = "; ".join(
            f"{self._row_name(x.get('row_id'), [r])}: "
            f"{word_label(x.get('word'))}" for x in judged
            if x.get("row_id") in ROW_BY_ID)
        where = _evenness_worst_area_sentence(r)
        return (f"<div style='color:{_C['dim']};margin-top:6px'>"
                + html.escape(words + ". " + where + " "
                              + self._note_sentence("evenness_causes"))
                + "</div>")

    def _one_page_html(self, runs: list, dropped: "list | None" = None) -> str:
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
        out = [self._scope_html(runs, dropped)]

        # -- the one line of numbers a reader acts on
        #
        # **THE JUDGED FIGURES, AND THE PAGE SAYS WHICH THEY ARE (K28, item
        # 1).** Knut, asked whether this page should show the within-gamut
        # figures the verdict judges, as the Colour accuracy graph does: *"Yes,
        # and the reports need to show that the figures judged are
        # within-gamut."* It printed `de00`, every patch, beside a word judged
        # on `graded_de00`, so a sheet with colours beyond the gamut showed a
        # PASS next to a larger number than the one that earned it.
        from workflow.measurement_report import (VERDICT_SOURCE_IN_GAMUT,
                                                 graded_de00)
        de, _source = graded_de00(r)
        within = _source == VERDICT_SOURCE_IN_GAMUT
        sm = self._column_summary(r)
        bits = []
        # WITH THE UNIT (K10, Knut on beta 34), which the names now carry
        # themselves: they are the one vocabulary of K28 (item 2), the same
        # words the full report, the graphs and the limits window print.
        # **AND A "–" ROW IS NOT HERE EITHER (K28, item 3).**
        _dash = self._dash_row_ids([r])
        for key in ("avg_all", "max_all"):
            if de.get(key) is not None and _ROW_ID_OF[key] not in _dash:
                bits.append(tr("{metric}: {value}").format(
                    metric=self._row_name(_ROW_ID_OF[key], [r]),
                    value=_fmt(de.get(key), 2)))
        _split = r.get("gamut_split") or {}
        _sheet = int((_split.get("n_in") or 0) + (_split.get("n_out") or 0))
        if de.get("n"):
            n = int(de["n"])
            # Singular and plural in full, never "(s)" (CLAUDE.md).
            if within and _sheet > n:
                bits.append(tr("{n} of {total} patches").format(
                    n=n, total=_sheet))
            else:
                bits.append(tr("{n} patch").format(n=n) if n == 1
                            else tr("{n} patches").format(n=n))
        said = summary_text(self._one_page_summary(sm))
        if within:
            said += " " + tr("The judged figures are those of the patches "
                             "within the profile's gamut.")
        out.append(_h2(tr("Result")) + _gap()
                   + "<div><b>" + html.escape(word_label(sm.word)) + "</b>"
                   + (" · " + html.escape("; ".join(bits)) if bits else "")
                   + "</div>"
                   + f"<div style='color:{_C['dim']};margin-top:2px'>"
                   + html.escape(said)
                   + "</div>")

        # **AND THE LIST THAT SENTENCE PROMISES.** Knut, 2026-09-22: *"it is
        # obvious that the list is missing, and thus shall be included, where
        # there are metrics that are not checked against the selected
        # measurements to be included in the report."*
        #
        # On the full report the promise is kept by the numbered notes under
        # the results table. This page has no results table, so the sentence
        # said "the values not checked are listed below" and then went straight
        # to Example colours. Measured by challenge round 33 on a run bound to
        # Custom ISO 12647-7: COND, 8 of 18 values checked, ten rows unchecked
        # and NONE of them named, on screen or in the PDF.
        #
        # The rows come from the same `_verdict_rows` the full report judges
        # from, so this page cannot name a different set of absences than the
        # document it summarises, and each carries the reason its numbered note
        # would have given it.
        #
        # **ONE PARAGRAPH, NOT A BULLETED LIST, AND THE PAGE DECIDED THAT.**
        # The first version gave each row its own line with its reason beside
        # it, and `test_the_one_page_summary_prints_on_one_page` measured the
        # body at 1059 px against 952 available: 107 px over, on the one
        # document whose whole promise is that it is one page. The names are
        # what the sentence promises; the reasons are on the full report, which
        # is where a reader who wants them is going anyway.
        # **AND CAPPED, BECAUSE THE PAGE IS THE PROMISE.** Listing all of them
        # on one line left only 33 px spare against the 60 px of headroom
        # `test_and_keeps_room_for_a_description_of_ordinary_length` requires,
        # and that guard is right: a document that fits by one pixel is one
        # sentence away from being two pages. So the page names the first few
        # and says where the rest are, which keeps the sentence's promise
        # without breaking the document's.
        # -- EVENNESS, when this page's verdict includes it. Knut, 2026-09-22:
        # the likely causes go *"as notes on the results in the report text,
        # for any report type that has enabled this metric"*, and this type
        # has no notes list, so the note is one short paragraph here, and only
        # when an evenness row was actually judged: a line about a verdict the
        # page did not give would be the unasked-for sentence this page's
        # length rule exists to keep out.
        out.append(self._one_page_evenness_html(r))
        # -- AND WHAT A PASS MEANS, AS THE LAST WORD OF THE RESULT (K42-2,
        # Knut #182 5832746557): *"This text should not be at the end, but as
        # an explanation for the results in the Results section. Move that
        # text to the end of the Results section."* It closed the page, under
        # the cube corners, where it explained nothing near it. Why it is the
        # caveat's second half and why it replaces the general line is said
        # at the foot of this method, where the general line still stands.
        from workflow.compliance_sets import STANDARD_CAVEAT_PROOF
        _standard = self._names_a_standard(r)
        if _standard:
            out.append(f"<div style='color:{_C['dim']};margin-top:6px'>"
                       + html.escape(tr(STANDARD_CAVEAT_PROOF)) + "</div>")

        # -- the colours, from the chart that was measured
        picked = r.get("summary_patches") or []
        if picked:
            out.append(_h2(tr("Example colours")) + _gap()
                       + f"<div style='color:{_C['dim']};margin-bottom:4px'>"
                       + html.escape(tr(
                           "{count} colours from the test chart used, spread "
                           "across what this printer can make. Left: what the "
                           "chart asked for. Right: what came back."
                       ).format(count=len(picked))) + "</div>"
                       + self._swatch_table_html(
                           picked,
                           columns=-(-len(picked)
                                     // self._SWATCH_ROWS_PER_COLUMN) or 1))
        else:
            # A report saved before the example colours existed carries none,
            # and says so rather than showing an empty frame.
            out.append(_h2(tr("Example colours")) + _gap()
                       + f"<div style='color:{_C['dim']}'>" + html.escape(tr(
                           "No example colours were recorded with this "
                           "measurement.")) + "</div>")

        corners = [c for c in (r.get("corners") or []) if c.get("present")]
        if corners:
            # K28 (item 4): the eight corner ΔE00 never have a limit, and say
            # so here as in the full report; in the heading, because this page
            # has no line to spare (`test_and_keeps_room_for_a_description_of
            # _ordinary_length`).
            out.append(_h2(tr("Cube corners, for information (no limit "
                              "applies)")) + _gap()
                       + self._swatch_table_html(corners))

        # **T1 NEVER REACHES THE CAVEAT BLOCK, AND THE CAP USED TO COVER FOR
        # THAT.** `_report_body_html` branches to this method before it builds
        # `_report_results_html`, which is where `STANDARD_CAVEAT` is printed
        # for every column applying a standard. While an ISO-named column was
        # capped at COND the word itself carried the qualification here; Knut
        # retired the cap on 2026-09-22 and this page would then have printed a
        # bold green PASS under "Custom ISO 12647-7" with only the general
        # not-certification line under it. That is the exact arrangement
        # `tests/test_a_custom_iso_column_carries_the_same_caveat.py` exists to
        # prevent, on the one report type designed to be handed to a customer.
        #
        # So the general line is REPLACED by the caveat here, not joined by it:
        # the caveat says everything the general line says and more, and this
        # is a page whose entire promise is that it is one page. The summary
        # sentence above already carries the caveat's first clause, which is
        # why the two together still read as one statement rather than a
        # repetition.
        # **AND THE SECOND HALF OF IT, NOT THE WHOLE.** Measured on this
        # page's own A4 layout with a run bound to Custom ISO 12647-7: the
        # whole caveat leaves 52 px spare against the 60 px
        # `test_and_keeps_room_for_a_description_of_ordinary_length` requires,
        # its second half leaves 82. And the trim is the right one rather than
        # merely the short one: the Result sentence a few centimetres above
        # already says this limit set holds a standard's published values
        # applied to your chart and is not a test against that standard, which
        # is the first half. The second half is what nothing else here says.
        # ONE QUESTION, ASKED ONCE. `_names_a_standard` is the full test,
        # including the stored label a live column used to drop (round 40a F6),
        # and this page must not ask a narrower version of it.
        # **AND IT STANDS IN THE RESULT, NOT HERE (K42-2).** `_standard` was
        # asked above, where the caveat is now printed as the Result's last
        # paragraph; this foot keeps only the general line, for a column that
        # names no standard.
        if not _standard:
            out.append(f"<div style='color:{_C['dim']};margin-top:10px'>"
                       + html.escape(tr(
                           "This page says what was measured and what it was "
                           "compared against; it does not certify."))
                       + "</div>")
        return "".join(out)

    #: How many patches the example-colour table stacks in one column before it
    #: starts a second. SIXTEEN IN ONE COLUMN DOES NOT FIT ON ONE PAGE: measured
    #: against the PDF's own A4 layout, the one-page summary came to 990 px of
    #: body against 952 available, so the document named "Colour summary (one
    #: page)" printed on two. Eight and eight is 112 px shorter than sixteen,
    #: and it also stops a hand-over page wasting its right half on a tall thin
    #: list.
    _SWATCH_ROWS_PER_COLUMN = 8

    def _swatch_table_html(self, rows: list, columns: int = 1) -> str:
        """A patch per row: what was asked for, what came back, and how far
        apart they are. Two swatches side by side, because a number alone is
        not what a person hands to a customer.

        With *columns* > 1 the patches are laid out in that many blocks side by
        side, each block carrying its own headings, so a long list becomes a
        short wide one.
        """
        def _head() -> str:
            return ("<th align='left' style='padding-right:8px'>"
                    + html.escape(tr("Patch")) + "</th>"
                    # THE TWO SWATCH COLUMNS NEED AIR. Photographed on screen:
                    # "Asked for" ran straight into "Measured" with no gap, so
                    # the header read as one word and the two blocks below it
                    # as one block.
                    "<th align='left' style='padding-right:10px'>"
                    + html.escape(tr("Asked for")) + "</th>"
                    "<th align='left' style='padding-right:10px'>"
                    + html.escape(tr("Measured")) + "</th>"
                    "<th align='right' style='padding-left:10px'>"
                    + html.escape(tr("ΔE00")) + "</th>")

        def _cells(x: "dict | None") -> str:
            if x is None:
                # A block short of its last patches keeps the shape of the row
                # rather than collapsing it, so the blocks beside it stay level.
                return "<td></td><td></td><td></td><td></td>"
            name = x.get("name") or x.get("loc") or ""
            exp, got = x.get("expected_hex", ""), x.get(
                "measured_hex") or x.get("hex", "")
            return (f"<td style='padding:1px 8px 1px 0'>{html.escape(str(name))}</td>"
                    f"<td style='padding-right:10px'>{_swatch(exp)}</td>"
                    f"<td>{_swatch(got)}</td>"
                    f"<td align='right' style='padding-left:10px'>"
                    f"{_fmt(x.get('de'), 2)}</td>")

        columns = max(1, int(columns))
        per = -(-len(rows) // columns) if rows else 0
        blocks = [rows[i * per:(i + 1) * per] for i in range(columns)] if per \
            else [rows]
        gap = "<td style='padding-right:22px'></td>"
        head = gap.join(_head() for _ in blocks)
        body = []
        for r in range(per):
            body.append("<tr>" + gap.join(
                _cells(b[r] if r < len(b) else None) for b in blocks) + "</tr>")
        return ("<table cellspacing='0' cellpadding='0' "
                "style='margin:2px 0 6px'>"
                f"<tr>{head}</tr>" + "".join(body) + "</table>")

    def _pdf_html(self, runs: list, charts_html: str) -> str:
        return self._report_body_html(runs, for_pdf=True, charts_html=charts_html)

    def _judged_trend_limits(self) -> "dict[str, float]":
        """``{row_id: limit}`` for every trend row the DOCUMENT judged.

        #182 K20/K21. Judged means a PASS, FAIL or COND on that row for some
        measurement of `_runs_for_document()` that is not a raw drift check,
        read from `_verdict_rows`, which is what the results table prints. The
        limit is the threshold that verdict was given against, so the dotted
        line sits at the number printed beside the word: a saved report's
        recorded set, or the run's set when judged live. Newest measurement
        wins if two disagree, which `_one_limit_set` should make impossible.
        """
        from workflow.compliance_sets import COND, FAIL, PASS
        from workflow.measurement_report import TREND_ROW_IDS
        if not self._sources:
            return {}
        want = set(TREND_ROW_IDS)
        out: "dict[str, float]" = {}
        for r in self._runs_for_document():
            if _is_raw_drift(r):
                continue
            rows, _rec = self._verdict_rows(r)
            for x in rows:
                rid = x.get("row_id") or x.get("key")
                thr = x.get("threshold")
                if (rid in want and x.get("word") in (PASS, FAIL, COND)
                        and isinstance(thr, (int, float))):
                    out[rid] = float(thr)
        return out

    def _trend_plan(self) -> list:
        """Every trend tab as ``(chart, title, metrics, y_max, dec, auto,
        thresholds, limit_lines, shown)``, in tab order.

        ONE ANSWER for the live tabs and the PDF, so a tab hidden on screen is
        never printed and a printed one never drawn with other lines. The four
        original tabs are always shown (Knut: keep them); a judged-metric tab
        is shown when at least one of its rows was judged, and plots only its
        judged rows, each with its own dotted line (`_TREND_GROUPS`)."""
        from workflow.compliance_sets import ROW_BY_ID
        avg_thr, max_thr = self._accuracy_thresholds()
        # **A PRINTING RECORD IS JUDGED AGAINST NOTHING, SO ITS GRAPH DRAWS
        # NO LIMIT (#182 K30, challenge B B4; spec 17 item 4).** Its Colour
        # accuracy graph drew the Avg and Max lines, each labelled "the limit
        # for ...", on a document that gives no verdict.
        _no_lines = self._ungraded_by_type()
        plan = []
        for chart, title, metrics, y_max, dec, auto in self._trend_configs():
            thr = ((avg_thr, max_thr) if chart is self._trend_de
                   and not _no_lines else None)
            # A Colour accuracy graph whose five rows are all "–" has nothing
            # left to draw (K28, item 3), and is hidden like a judged-metric
            # tab with no judged row. The other three always show.
            shown = bool(metrics) if chart is self._trend_de else True
            # K45-2: the lines a judged accuracy row needs besides the pair.
            extra = ([(v, w, None) for v, w, _n in
                      self._accuracy_line_plan()[1]]
                     if chart is self._trend_de and not _no_lines else [])
            plan.append((chart, title, metrics, y_max, dec, auto, thr, extra,
                         shown))
        judged = self._judged_trend_limits()
        for key, title, rows in _TREND_GROUPS:
            metrics, lines = [], []
            for rid, word, col in rows:
                if rid not in judged:
                    continue
                lim = judged[rid]
                # K25: the legend carries the row's unit, as Colour
                # accuracy's "Average ΔE, all patches" does.
                metrics.append((_with_unit(self._row_name(
                                    rid, self._document_runs_for_graphs()),
                                           ROW_BY_ID[rid].unit), QColor(col),
                                (lambda pt, rr=rid, ll=lim:
                                 _trend_row_value(pt, rr, ll))))
                lines.append((lim, word(), QColor(col)))
            plan.append((self._trend_groups[key], title(), metrics, None, 1,
                         False, None, lines, bool(metrics)))
        plan.sort(key=lambda e: self._trend_tabs.indexOf(e[0]))
        return plan

    def _trend_extras(self, chart) -> dict:
        """The K25 half of a chart's data: ``{"line_notes", "withheld",
        "about"}``, for the tab and the PDF alike (Knut, 5789263863).

        ``line_notes`` explains each limit line, in the order `_trend_plan`
        gives the lines; ``withheld`` says, per plotted metric, why a date's
        value is not drawn (the red x); ``about`` is the graph's two-line
        description for the PDF."""
        from workflow.compliance_sets import ROW_BY_ID
        key = {self._trend_de: "de", self._trend_white: "white",
               self._trend_black: "black",
               self._trend_corners: "corners"}.get(chart)
        if key is None:
            key = next((k for k, c in self._trend_groups.items()
                        if c is chart), None)
        about = _TREND_ABOUT[key]() if key in _TREND_ABOUT else ""
        ungraded = self._ungraded_by_type()
        if chart is self._trend_de and _series_is_within_gamut(
                getattr(self, "_trend_series", None)):
            # K30 (B3): a record judges no patch, so "each judged patch" is
            # the within-gamut population described as measured; and so does
            # a type that judges no colour-accuracy row (Grey and tone).
            about = (_TREND_ABOUT_DE_JUDGED()
                     if self._colour_accuracy_is_judged()
                     else _TREND_ABOUT_DE_WITHIN_GAMUT())
        if chart is self._trend_de and ungraded:
            return {"line_notes": [], "withheld": [], "about": about}
        # THE NAME THE LEGEND BESIDE THE LINE PRINTS (B8-944): "…, within
        # gamut" on a document holding a split sheet, the plain name on any
        # other, decided for the document exactly as `_trend_configs` does.
        _names_runs = self._document_runs_for_graphs()
        if chart is self._trend_de:
            pair_notes, extra = self._accuracy_line_plan()
            notes = list(pair_notes) + [n for _v, _w, n in extra]
            return {"line_notes": notes, "withheld": [], "about": about}
        rows = dict((k, r) for k, _t, r in _TREND_GROUPS).get(key)
        if not rows:
            return {"line_notes": [], "withheld": [], "about": about}
        judged = self._judged_trend_limits()
        notes, withheld = [], []
        for rid, word, _col in rows:
            if rid not in judged:
                continue
            lim = judged[rid]
            notes.append(_limit_line_note(word(), lim, ROW_BY_ID[rid].unit,
                                          rid, self._row_name(rid,
                                                              _names_runs)))
            withheld.append(lambda pt, rr=rid, ll=lim:
                            _trend_withheld_reason(pt, rr, ll))
        return {"line_notes": notes, "withheld": withheld, "about": about}

    def _update_trends(self, series: list, dark: bool) -> None:
        """Feed the grouped trend charts their metric sets. The tabs stay visible
        whenever a report is loaded — with a single run they show an empty chart
        and an explanatory message (Knut). The accuracy chart also gets the Pass
        thresholds as dotted guide lines; a judged-metric tab gets one line per
        metric and is hidden while none of its rows is judged (#182 K20/K21)."""
        for (chart, _title, metrics, y_max, dec, auto, thr, lines,
             shown) in self._trend_plan():
            ex = self._trend_extras(chart)
            chart.set_data(series, metrics, dark=dark, y_max=y_max, dec=dec,
                           auto=auto, thresholds=thr, limit_lines=lines,
                           line_notes=ex["line_notes"],
                           withheld=ex["withheld"])
            self._trend_tabs.setTabVisible(self._trend_tabs.indexOf(chart),
                                           shown)
        show = bool(self._sources)
        self._trend_label.setVisible(show)
        self._trend_tabs.setVisible(show)
        self._refresh_trend_key()

    def _refresh_trend_key(self, _index: int = -1) -> None:
        """The limit lines of the graph in front, described under it (K45-2):
        the same sentences, and the same dotted stroke in the line's colour,
        the PDF prints under that graph."""
        key = getattr(self, "_trend_key", None)
        if key is None:
            return
        chart = self._trend_tabs.currentWidget()
        # A graph with fewer than two dates draws no line, only the reason
        # it draws nothing, and the PDF prints no such graph; so no key.
        # K47: and a graph with no limit line says so, as in the PDF.
        lines = ([(kind, col, text) for kind, col, text
                  in chart.descriptions() if kind in ("line", "note")]
                 if isinstance(chart, _TrendChart) and chart.has_trend()
                 else [])
        if not lines or not self._trend_tabs.isVisibleTo(self):
            key.clear()
            key.setVisible(False)
            return
        key.setText("<br>".join(
            (html.escape(text) if kind == "note" else
             f"<span style='color:{col.name()};font-weight:bold'>"
             "\u2508\u2508</span>&nbsp;&nbsp;" + html.escape(text))
            for kind, col, text in lines))
        key.setVisible(True)

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
                + html.escape(self._empty_text()) + "</div>")

    def _empty_text(self) -> str:
        """What the empty page says (K32, Knut on beta 41, #182 5814558912
        and 5814673639).

        A window opened on a selection with nothing measured opens EMPTY, and
        says so in the words of the bar's run type, with the two ways forward
        Knut named: *"awaiting the user to add measurements ... or go out and
        perform a verification measurement"*. Anything else (a list the user
        cleared, a window with no bar) keeps the old sentence."""
        if getattr(self, "_opened_empty", False) and not self._sources:
            from workflow.measurement_report import (KIND_CALIBRATION,
                                                     KIND_PROFILING,
                                                     KIND_VERIFICATION)
            found, kind = self._bar_kind()
            if found and kind == KIND_VERIFICATION:
                return tr("This verification run has no dated measurement "
                          "yet, so there is nothing to report on. Measure its "
                          "chart on the Measure tab, or add measurements with "
                          "“Add Profile's Measurements…”.")
            if found and kind == KIND_PROFILING:
                return tr("No profile run of this project has a measurement "
                          "yet, so there is nothing to report on. Measure a "
                          "chart on the Measure tab, or add measurements with "
                          "“Add Profile's Measurements…”.")
            if found and kind == KIND_CALIBRATION:
                return tr("This calibration has no measurement yet, so there "
                          "is nothing to report on. Measure it on the Measure "
                          "tab, or add measurements with “Add Profile's "
                          "Measurements…”.")
        return tr("Open a measurement file to see its report.")

    def _error_html(self, msg: str) -> str:
        self._use_theme_palette()
        return (f"<div style='color:{_C['error']};padding:24px'>"
                + html.escape(tr("Could not read this measurement: {msg}")
                              .format(msg=msg)) + "</div>")

    @staticmethod
    def _doc_is_split(runs: "list | None") -> bool:
        """Whether any sheet of *runs* had its colours split by the profile's
        gamut (K31: the judged names then say "within gamut")."""
        return any((r or {}).get("gamut_split") for r in (runs or []))

    def _names_within_gamut(self, runs: "list | None") -> bool:
        """Whether this document names its judged figures "within gamut":
        a JUDGED sheet of it was split by the profile's gamut (B8-944).

        **SPLIT IS NOT ENOUGH.** "…, within gamut" says the figure the word
        judged is the within-gamut one. A profiling sheet is never graded
        (§3) and a Printing record judges nothing, so on those the name
        claimed a judgement nobody made, over a page that showed no split at
        all (beta 40 challenge B, 8). They print the plain names."""
        try:
            if MeasurementReportDialog._ungraded_by_type(self):
                return False
        except Exception:                                # noqa: BLE001
            pass
        return any((r or {}).get("gamut_split")
                   and (r or {}).get("is_verification")
                   for r in (runs or []))

    def _row_name(self, rid: str, runs: "list | None" = None) -> str:
        """One row's name as this document prints it: the ROWS label, or its
        within-gamut name when a sheet of the document is split by the
        profile's gamut and the row is judged on the within-gamut patches
        (K31, Knut #182 5801677743; `compliance_sets.row_name`). *runs*
        decides when given; otherwise the document being rendered does."""
        from workflow.compliance_sets import row_name
        split = (MeasurementReportDialog._names_within_gamut(self, runs)
                 if runs is not None
                 else bool(getattr(self, "_names_split", False)))
        return tr(row_name(rid, split))

    def _evenness_row_is_in_report(self, r: dict) -> bool:
        """Whether one of the two evenness rows is in this run's part of the
        report: in its verdict rows, which a "–" limit and the report type
        have already filtered (K31, the "How evenness was judged" line)."""
        from workflow.compliance_sets import N_A
        from workflow.measurement_report import EVENNESS_ROWS
        try:
            rows, _rec = self._verdict_rows(r)
        except Exception:      # noqa: BLE001 — an explanatory line, never a gate
            return False
        # **A ROW THAT WAS JUDGED, NOT A ROW THAT IS LISTED (B8-941).** The
        # line says how evenness WAS judged, and it was printed above two
        # evenness rows that both read N-A: nothing had been judged. An N-A
        # evenness row does not count (§26.1, correction awaiting Knut).
        return any((x.get("row_id") or x.get("key")) in EVENNESS_ROWS
                   and x.get("word") != N_A and x.get("value") is not None
                   for x in rows)

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
                "the whole everyday printing chain: the application's "
                "colour engine, this profile and the printer together"),
                False))
            rows.append((tr("Printed"), tr(
                "in another application with colour management (as answered "
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
                "not recorded"),
                False))
        route = printing.get("route")
        if route == "chromiq":
            rows.append((tr("Colour management at the printer"), tr(
                "off"), False))
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
        _pw_prof = _paper_white_from_profile(r)
        if r.get("yardstick") == "media-relative" and _pw_prof is not None:
            # #182 K37, (e): not the sheet's own paper white, which its chart
            # has no patch for, but the one its profile records.
            rows.append((tr("How the colours were judged"), tr(
                "relative to the paper white recorded in the profile "
                "{profile}, because this sheet's chart has no paper patch: the "
                "print mapped white to the paper, so the paper itself is not "
                "counted against the profile").format(
                    profile=str(_pw_prof.get("profile") or "")), False))
        elif r.get("yardstick") == "media-relative":
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
        # **K31, "BOTH TEXTS APPROVED"** (Knut, #182 5801677743, answering
        # 5798697107 section 3). Evenness is always judged on the readings
        # as measured (E8), so on a sheet whose line above says "relative to
        # this sheet's own paper white" a reader would assume the evenness
        # figures were too. Its own line, shown ONLY when an evenness row is
        # in this report, so it is always true where it is printed.
        if MeasurementReportDialog._evenness_row_is_in_report(self, r):
            rows.append((tr("How evenness was judged"), tr(
                "from the readings as the instrument took them, by comparing "
                "the nine areas of this sheet with each other."), False))
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

    def _run_detail_html(self, r: dict, numbering: "list | None" = None) -> str:
        """One run's full breakdown: the colour-accuracy Pass/Fail table
        (Metric / Measured ΔE00 / Threshold / Result), paper white & black, the
        cube corners, and the 16 worst patches (Knut).

        *numbering* is the DOCUMENT's note numbering (`_note_numbering` over
        every run the document holds), so a row's marker here is the number the
        same row carries in the Report Results grid (G12, CH-32/33). None
        works it out from this run alone, for a caller that has no document.
        """
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
            # **NO VERDICT COLUMN ON A TYPE THAT JUDGES NOTHING** (G12, Knut
            # 2026-09-22: *"The sections with detailed data still shows PASS
            # and FAIL, or if a metric could not be checked. Should there be a
            # note there instead"*). On the Printing record every word in this
            # column was INFO or N-A, two of the five verdict words, in the one
            # document that gives no verdict. What the column carried that is
            # not a verdict, "no number here", stays: the value cell reads "—"
            # with the raised number of the note saying why.
            record = self._ungraded_by_type()
            head = (f"<tr style='color:{_C['faint']}'>"
                    f"<th align='left' style='{thb}'>"
                    + html.escape(tr("Metric")) + "</th>"
                    + "".join(f"<th align='right' style='{thb}'>"
                              + html.escape(c) + "</th>" for c in cols)
                    + f"<th align='right' style='{thb}'>"
                    + html.escape(tr("Limit")) + "</th>"
                    + ("" if record else
                       f"<th align='center' style='{thb}'>"
                       + html.escape(tr("Result")) + "</th>")
                    + "</tr>")
            trs = [head]

            from workflow.compliance_sets import (COND, FAIL, PASS, ROW_BY_ID,
                                                  word_label)
            from workflow.measurement_report import (note_label,
                                                     note_numbers_for)
            # THE DOCUMENT'S NUMBERING, never this run's own: a note is "2)"
            # here because it is "2)" under the Report Results grid.
            _nums = (numbering if numbering is not None
                     else self._note_numbering([r]))
            _marked: "list[int]" = []

            def mark_for(row) -> str:
                if raw_drift or row is None:
                    return ""
                ns = note_numbers_for(row, _nums)
                for n in ns:
                    if n not in _marked:
                        _marked.append(n)
                return ("<sup style='font-weight:normal'>&nbsp;"
                        + html.escape(" ".join(note_label(n) for n in ns))
                        + "</sup>") if ns else ""

            def row_html(i, label, values, threshold, word, should=False,
                         bold_first=True, tip="", mark="", main=0):
                bg = f" style='background:{self._ZEBRA_BG}'" if i % 2 == 1 else ""
                if word is None:
                    res = "—" + mark
                else:
                    col = {PASS: _C["pass"], FAIL: _C["fail"],
                           COND: _C["cond"]}.get(word, _C["faint"])
                    weight = "bold" if word in (PASS, FAIL, COND) else "normal"
                    title = f" title='{html.escape(tip)}'" if tip else ""
                    res = (f"<span{title} style='color:{col};font-weight:{weight}'>"
                           + html.escape(word_label(word)) + "</span>" + mark)
                # F9 / CS Q12: a FAIL whose two-decimal value reads like the
                # limit shows three decimals, so a failing value never looks
                # like a passing one
                if (word == FAIL and threshold is not None and values
                        and isinstance(values[main], (int, float))
                        and _fmt(values[main]) == _fmt(threshold)):
                    values = list(values)
                    values[main] = f"{values[main]:.3f}"
                cells = []
                for j, v in enumerate(values):
                    txt = _fmt(v)
                    if bold_first and j == main:
                        txt = "<b>" + txt + "</b>"
                    # ON THE RECORD THE MARKER SITS ON THE EMPTY VALUE, since
                    # there is no verdict cell to carry it
                    if record and j == main and mark:
                        title = (f" title='{html.escape(tip)}'" if tip else "")
                        txt = f"<span{title}>" + txt + "</span>" + mark
                    cells.append("<td align='right'>" + txt + "</td>")
                tds = "".join(cells)
                thr = "—" if threshold is None else (
                    f"({_fmt(threshold)})" if should else _fmt(threshold))
                return (f"<tr{bg}><td style='padding-right:14px'>{html.escape(label)}</td>"
                        + tds +
                        f"<td align='right'>{thr}</td>"
                        + ("" if record else f"<td align='center'>{res}</td>")
                        + "</tr>")

            for i, row in enumerate(rows):
                k = row.get("key")
                rid = row.get("row_id") or k
                rowdef = ROW_BY_ID.get(rid)
                # one vocabulary with the results grid (N5): the row's label
                # K31: "within gamut" in the name on a split sheet.
                label = (self._row_name(rid, [r]) if rowdef
                         else (_METRIC_LABELS[k]() if k in _METRIC_LABELS else str(rid)))
                main = 0
                if split and k in de:
                    values = [d_in.get(k), d_out.get(k), de.get(k)]
                elif split and rid not in WITHIN_GAMUT_ROWS:
                    # **A ROW THAT COUNTS EVERY PATCH IS NOT A WITHIN-GAMUT
                    # FIGURE (#182 K30, challenge B B3).** The grey and ramp
                    # rows sat under "Within gamut" on a split sheet; they
                    # are worked out over every patch of their population.
                    values = [None, None, row.get("value")]
                    main = 2
                elif split:
                    values = [row.get("value"), None, None]
                else:
                    values = [row.get("value")]
                word = row.get("word")
                if word is None and row.get("pass") is not None:
                    word = PASS if row["pass"] else FAIL
                tip = (self._reason_sentence(row.get("reason"), r, row)
                       if row.get("reason") else "")
                trs.append(row_html(i, label, values, row.get("threshold"), word,
                                    should=bool(row.get("should")), tip=tip,
                                    mark=mark_for(row), main=main))
            # Spread is reported for completeness but carries no threshold
            # (Knut), and since K28 (item 4) it sits under a heading that says
            # so, as it does in the Overview: a separator row spanning the
            # table, because the figure needs this table's columns.
            _span = 1 + len(cols) + 1 + (0 if record else 1)
            trs.append(f"<tr><td colspan='{_span}' style='padding-top:8px;"
                       f"color:{_C['dim']};font-weight:bold'>"
                       + html.escape(tr("For information (no limit applies)"))
                       + "</td></tr>")
            trs.append(row_html(
                len(rows), _METRIC_LABELS["std"](),
                ([d_in.get("std"), d_out.get("std"), de.get("std")]
                 if split else [de.get("std")]), None, None))
            device_ref = r.get("reference_source") == "device"
            # Both cases compare against the chart's DESIGN — either straight from
            # the .ti2, or reconstructed from the device values — so the heading is
            # the same; the note below explains the reconstruction (Knut).
            parts.append(_h3(tr("Colour accuracy (ΔE00 against the chart's "
                                "design)")))
            parts.append("<table cellpadding='5' cellspacing='0' "
                         "style='border-collapse:collapse;font-size:11px'>"
                         + "".join(trs) + "</table>")
            # …AND THE NOTES THIS TABLE POINTS AT, UNDER IT (G12). In the PDF
            # the detailed section starts on a page of its own, and a marker
            # whose note is pages back is a marker nobody follows. Same
            # numbers, same sentences, one renderer with the Results list.
            if _marked:
                _said = {n: (where, sentence) for (n, where, sentence)
                         in self._numbered_notes_from(_nums)}
                _mine = [(n,) + _said[n] for n in sorted(_marked) if n in _said]
                if _mine:
                    parts.append(self._notes_list_html(
                        _mine,
                        f"color:{_C['faint']};font-size:10px;margin-top:4px",
                        closing=False))
            # WHERE THE WORDS CAME FROM, WHICH A RECORD HAS NONE OF (round B
            # before beta 37, H3). A Printing record grades nothing, so "This
            # verdict was recorded ... against the limit set ..." beside "This
            # sheet is not graded" is about a verdict the page does not show.
            if not raw_drift and not self._ungraded_by_type():
                parts.append(
                    f"<p style='color:{_C['faint']};font-size:10px'>"
                    + html.escape(self._verdict_provenance(r, recorded))
                    + "</p>")
            if raw_drift:
                rd = r.get("raw_drift") or {}
                if rd.get("baseline"):
                    drift_txt = tr(
                        "This sheet was printed raw, without the profile, "
                        "so it is a drift check, and it is the first one: "
                        "it is the baseline that later raw checks of this "
                        "chart are measured against.")
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
                        "{n} patches. Small numbers mean the printer still "
                        "behaves as it did then; growing numbers mean it has "
                        "drifted. "
                        "(PASS and FAIL against the report's limit set are not "
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
            # K30 (B3): "The Result judges the within-gamut figures" only
            # where a row in this table uses the split (spec 22.1); a Grey and
            # tone check's rows count every grey patch.
            _judges_split = any((row.get("row_id") or row.get("key"))
                                in WITHIN_GAMUT_ROWS for row in rows)
            if split and (record or not _judges_split):
                # THE OTHER PARAGRAPH SAYS "The Result judges the within-gamut
                # figures", and on the record there is no Result column
                parts.append(
                    f"<p style='color:{_C['faint']};font-size:10px'>" + html.escape(tr(
                        "Within what the profile ({profile}) can print: {n} of "
                        "this sheet's colours ({pct} %); beyond it: {m}. A "
                        "colour beyond the gamut was never printable, so its "
                        "distance describes the gamut's limit, not a mistake "
                        "of the profile.").format(
                            n=split.get("n_in"), m=split.get("n_out"),
                            pct=round(100 * (split.get("n_in") or 0)
                                      / max((split.get("n_in") or 0)
                                            + (split.get("n_out") or 0), 1)),
                            profile=split.get("profile", ""))) + "</p>")
            elif split:
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
                    "This chart was built from the profile's own gamut, so "
                    "its measurements can only be judged against the "
                    "colorimetric targets that were stored beside the chart "
                    "when it was made, and that reference file cannot be "
                    "found. Comparing against anything else would produce "
                    "confident-looking numbers measured against the wrong "
                    "yardstick, so none are shown."))
                # K39-1 (Knut, #182 5831246553): report text names no
                # action of the app ("reopen this report", "generate the
                # verification chart again"); it says what is missing.
                + "<br><br>" + html.escape(tr(
                    "The reference file belongs next to the chart in the "
                    "run's “verifications” folder and is not there. A chart "
                    "made again carries a reference of its own."))
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
                    "were worked out in the usual way and the measurement "
                    "file has not been touched."))
                + "</p>")

        _info_heading_done = False
        w, b = r.get("paper_white"), r.get("max_black")
        _no_paper = _no_paper_patch(r) and not w
        if (w or _no_paper) and b:
            # **WHAT THE FILE CARRIES, AND NO KeyError WHEN IT CARRIES LESS.**
            # This read `w['hex']`, `w['loc']` and `w['lab'][0]` straight out of
            # the record, and a report holding paper white as a bare
            # `{"L": …, "a": …, "b": …}` — which is what the demo projects on
            # this machine hold — took the whole window down with
            # `KeyError: 'hex'`. It was unreachable while "Show detailed data
            # for each run" started OFF; B8-388 makes that box default ON, so
            # the first on-screen run of the new default met it immediately.
            # Nothing is invented here: a swatch is drawn when there is a
            # colour to draw, the location is named when it is recorded, and
            # L* is printed from whichever of the two shapes the file uses.
            # …AND IT IS THE SAME READER THE OTHER TWO USE NOW (R24-F2). This
            # was a local `_lightness`, which is how the window came to print
            # one paper white three ways: right here, a dash in the Overview
            # table, and no point at all on the trend.
            from workflow.measurement_report import point_lab, point_lightness

            def _line(pt: dict, label: str) -> str:
                bits = []
                if pt.get("hex"):
                    bits.append(_swatch(str(pt["hex"])))
                bits.append(html.escape(label))
                if pt.get("loc"):
                    bits.append(f"({html.escape(str(pt['loc']))})")
                # ALL THREE, WHEN THE RECORD HAS THEM (K5): the swatch is drawn
                # from a* and b* as well, and a page printing only L* beside a
                # blue swatch gave the reader no way to see why it was blue.
                import math

                def _n(v: float) -> str:
                    # -0.04 is "0.0", not "-0.0" (round A, A-7)
                    return f"{round(v, 1) + 0.0:.1f}"
                lab = point_lab(pt)
                lv = point_lightness(pt)
                if lab is not None and all(math.isfinite(v) for v in lab):
                    bits.append(f"- L* {_n(lab[0])}, a* {_n(lab[1])}, "
                                f"b* {_n(lab[2])}")
                elif lv is not None and math.isfinite(lv):
                    # a record with no usable a*/b* (or a NaN in them) still
                    # prints the one number it has, never "nan" (A-7)
                    bits.append(f"- L* {_n(lv)}")
                return "<div>" + " ".join(bits) + "</div>"

            # K28 (item 4): the lightest and darkest L* and the eight corner
            # ΔE00 never have a limit, so they sit under one heading that says
            # so; the two headings they had become its sub-labels, rather
            # than three headings in a row.
            parts.append(_h3(tr("For information (no limit applies)")))
            _info_heading_done = True
            parts.append("<div style='font-weight:bold;margin-top:4px'>"
                         + html.escape(tr("Paper white and darkest black "
                                          "(L*)"))
                         + "</div>")
            if _no_paper:
                # #182 A10 (Knut, 5817809396): NO PAPER PATCH, NO PAPER
                # WHITE. The line reads N-A with its numbered note, the same
                # number the list under Report Results gives it.
                from workflow.compliance_sets import N_A, word_label
                from workflow.measurement_report import (note_label,
                                                         note_numbers_for)
                _pnums = (numbering if numbering is not None
                          else self._note_numbering([r]))
                _pn = note_numbers_for(
                    {"notes": [_paper_white_note_code(r)
                               or NOTE_NO_PAPER_PATCH]}, _pnums)
                _mk = ("<sup>&nbsp;" + html.escape(" ".join(
                    note_label(n) for n in _pn)) + "</sup>") if _pn else ""
                parts.append("<div>" + html.escape(tr("White")) + " - "
                             + html.escape(word_label(N_A)) + _mk + "</div>"
                             + _line(b, tr("Black")))
                _said = {n: (wh, s) for (n, wh, s)
                         in self._numbered_notes_from(_pnums)}
                _mine = [(n,) + _said[n] for n in _pn if n in _said]
                if _mine:
                    parts.append(self._notes_list_html(
                        _mine,
                        f"color:{_C['faint']};font-size:10px;margin-top:4px",
                        closing=False))
            else:
                parts.append(_line(w, tr("White")) + _line(b, tr("Black")))

        corners = r.get("corners") or []
        if corners:
            if not _info_heading_done:
                parts.append(_h3(tr("For information (no limit applies)")))
            parts.append("<div style='font-weight:bold;margin-top:6px'>"
                         + html.escape(tr("Cube corners (ΔE00)"))
                         + "</div>")
            head = (f"<tr style='color:{_C['faint']}'><th align='left'>" + html.escape(tr("Corner"))
                    + "</th><th>" + html.escape(tr("Expected")) + "</th><th>"
                    + html.escape(tr("Measured")) + "</th><th align='right'>ΔE00</th></tr>")
            crows = [head]
            for i, c in enumerate(corners):
                lbl = _CORNER_LABELS.get(c["name"], (lambda: c["name"]))()
                # **A MISSING CORNER OWNS NOTHING BUT ITS NAME** -- B8-290 and
                # `_corner_ideal_hex`. `present` False means the nearest patch
                # in device RGB is NOT at this corner, so its location, its
                # measured colour, its reference colour and its DeltaE00 all
                # describe a different patch. Printing them under this ink's
                # name is what let one grey patch answer for both Red and Blue.
                present = bool(c.get("present", True))
                miss = "" if present else (
                    f" <span style='color:{_C['fail']}'>(" + html.escape(tr("missing"))
                    + ")</span>")
                if present:
                    exp = _swatch(c.get("expected_hex", ""))
                    meas = _swatch(c.get("hex", ""))
                    de_c = (f"<b>{_fmt(c.get('de'))}</b>"
                            if c.get("de") is not None else _fmt(None))
                    # THE PATCH NUMBER GOES WITH THE PATCH. Two corners of his
                    # sheet both read "(14)", which is a claim about the chart
                    # and not only about a colour, so it goes when the rest of
                    # the stand-in does. `.get`, because a record that does not
                    # carry it must not take the window down: see the paper
                    # white block above, where a file of another shape did.
                    loc = ((f" <span style='color:{_C['faint']}'>"
                            f"({html.escape(str(c['loc']))})</span>")
                           if c.get("loc") else "")
                else:
                    exp = _swatch(_corner_ideal_hex(c["name"]))
                    meas = de_c = _fmt(None)
                    loc = ""
                bg = f" style='background:{self._ZEBRA_BG}'" if i % 2 == 1 else ""
                crows.append(
                    f"<tr{bg}><td>{html.escape(lbl)}{miss}{loc}</td>"
                    f"<td align='center'>{exp}</td>"
                    f"<td align='center'>{meas}</td>"
                    f"<td align='right'>{de_c}</td></tr>")
            parts.append("<table cellpadding='5' cellspacing='0' "
                         "style='border-collapse:collapse;font-size:11px'>"
                         + "".join(crows) + "</table>")

        worst = r.get("worst_patches") or []
        if worst:
            # Two 8-row halves side by side in one 9-column table (empty middle
            # column) — same columns, half the height (Knut).
            # **THE HEADING IS THE TABLE'S FIRST ROW (#182 K30, challenge B
            # B9).** As a paragraph of its own it was left alone at the foot
            # of a PDF page with its table on the next; inside a table that
            # may not break, the two move together.

            def wcells(p) -> str:
                if p is None:
                    return "<td></td><td></td><td></td><td></td>"
                # Patch · Expected · Measured · ΔE00 — the same column order as the
                # Cube-corners table, so the two read the same (Knut).
                #
                # **EVERY CELL IS WHAT THE FILE CARRIES.** This indexed all four
                # keys directly and a report whose worst-patch entries are
                # `{"id": …, "de00": …}` took the window down with
                # `KeyError: 'loc'`. Unreachable while "Show detailed data for
                # each run" started OFF; B8-388 makes it default ON. The patch
                # is named by whichever key the file uses, a swatch is drawn
                # only where there is a colour, and ΔE00 likewise.
                loc = p.get("loc")
                if loc is None:
                    loc = p.get("id")
                de = p.get("de")
                if de is None:
                    de = p.get("de00")
                return (f"<td>{html.escape('' if loc is None else str(loc))}</td>"
                        f"<td align='center'>{_swatch(p.get('expected_hex', ''))}</td>"
                        f"<td align='center'>{_swatch(p.get('measured_hex', ''))}</td>"
                        f"<td align='right'><b>{_fmt(de)}</b></td>")

            hdr = ("<th align='left'>" + html.escape(tr("Patch")) + "</th><th>"
                   + html.escape(tr("Expected")) + "</th><th>"
                   + html.escape(tr("Measured")) + "</th><th align='right'>ΔE00</th>")
            half = (len(worst) + 1) // 2
            left, right = worst[:half], worst[half:]
            rows = [f"<tr><td colspan='9' style='color:{_C["head"]};"
                    f"font-size:16px;font-weight:bold;padding:12px 0 3px 0'>"
                    + html.escape(tr("Worst patches")) + "</td></tr>",
                    f"<tr style='color:{_C['faint']}'>" + hdr
                    + "<th style='width:16px'></th>" + hdr + "</tr>"]
            for i in range(half):
                lp = left[i] if i < len(left) else None
                rp = right[i] if i < len(right) else None
                rows.append("<tr>" + wcells(lp) + "<td></td>" + wcells(rp) + "</tr>")
            parts.append("<table cellpadding='5' cellspacing='0' "
                         "style='border-collapse:collapse;font-size:11px;"
                         "page-break-inside:avoid'>"
                         + "".join(rows) + "</table>")

        return "<div>" + "".join(parts) + "</div>"

    def _detailed_section_html(self, runs: list) -> str:
        """The opt-in 'Detailed data per measurement run' section: each run on its
        own page, led by a 'Measurement run — date — N patches' heading and the
        profile name (Knut)."""
        out = [_h2(tr("Detailed data per measurement"), page_break=True)]
        # ONE NUMBERING FOR THE WHOLE DOCUMENT (CH-32), worked out over the
        # same runs the Report Results grid numbers, so the detailed tables'
        # markers and the grid's cannot disagree about which note is note 1.
        numbering = self._note_numbering(runs)
        # A CALIBRATION IS NO PROFILE (B8-952): its chart is the project's
        # calibration chart, and "Profile name: <name>-cal" named a profile
        # that does not exist.
        _calibration = self._report_kind(runs) == "calibration"
        for idx, run in enumerate(runs):
            brk = "page-break-before:always;" if idx > 0 else ""
            out.append(
                f"<h3 style='color:{_C["head"]};{brk}"
                f"border-bottom:1px solid {_C['hair']};"
                f"margin:12px 0 2px'>"
                + html.escape(tr("Measurement of {date}, {n} patches").format(
                    date=str(run.get("created") or ""), n=run.get("patches", 0)))
                + "</h3>"
                f"<div style='color:{_C['dim']};margin-bottom:4px'>"
                + html.escape((tr("Calibration chart: {name}")
                               if _calibration
                               else tr("Profile name: {name}")).format(
                    name=run.get("chart") or "")) + "</div>"
                + self._run_detail_html(run, numbering))
        return "".join(out)
