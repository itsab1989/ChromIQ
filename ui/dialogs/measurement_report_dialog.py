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

import copy
import html
import json
import os
import shutil
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
_METRIC_LABELS = {
    "avg_all":   lambda: tr("Average ΔE, all patches"),
    "avg_low95": lambda: tr("Average ΔE, lowest 95%"),
    "avg_high5": lambda: tr("Average ΔE, highest 5%"),
    "max_all":   lambda: tr("Maximum ΔE, all patches"),
    "max_low95": lambda: tr("Maximum ΔE, lowest 95%"),
    "std":       lambda: tr("Spread (std. dev.)"),
}
_ACCURACY_ROW_KEYS = ("avg_all", "avg_low95", "avg_high5", "max_all", "max_low95")

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
ALWAYS_BUILT_BLOCKS: "tuple[str, ...]" = ("grey_balance", "ramps_30_70",
                                          "summary_patches")


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


def _small_sample_sentence(r: "dict | None") -> str:
    """Why the worst-5 % row was withheld, naming the population it counted.

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
                   "the profile's gamut; at least 20 are needed to split off "
                   "the worst 5 %").format(total=total) if n == 1 else
                tr("{total} patches were measured and {n} of them fall inside "
                   "the profile's gamut; at least 20 are needed to split off "
                   "the worst 5 %").format(total=total, n=n))
    _count = n if isinstance(n, int) else total if total is not None else None
    if _count == 1:
        return tr("the chart has one patch; at least 20 are needed to split "
                  "off the worst 5 %")
    return tr("the chart has {n} patches; at least 20 are needed to split off "
              "the worst 5 %").format(n=_count if _count is not None else "?")


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
        counted = tr("the control strip this chart declares has one patch in "
                     "this measurement with a reference value")
    else:
        counted = tr("the control strip this chart declares has {k} patches in "
                     "this measurement with reference values").format(k=k)
    return counted + tr("; at least {n} are needed for the average and the "
                        "largest, and at least {p} for the 95th percentile. "
                        "Declare a longer strip, or add its patches to the "
                        "chart").format(n=CONTROL_STRIP_MIN,
                                        p=CONTROL_STRIP_P95_MIN)


def _surface_gamut_sentence(r: "dict | None") -> str:
    """Why the surface-gamut row was withheld: too few patches on the cube."""
    from workflow.measurement_report import SURFACE_GAMUT_MIN
    block = ((r or {}).get("gamut_populations") or {}).get("surface") or {}
    n = block.get("n")
    n = n if isinstance(n, int) else 0
    if n == 1:
        counted = tr("one patch of this chart sits on the surface of the "
                     "device cube and carries a reference value")
    else:
        counted = tr("{n} patches of this chart sit on the surface of the "
                     "device cube and carry reference values").format(n=n)
    return counted + tr("; at least {k} are needed. Add solid inks, two-ink "
                        "overprints, or steps that hold one of red, green or "
                        "blue at 0 or at 100, in Create Chart").format(
                            k=SURFACE_GAMUT_MIN)


def _outer_gamut_sentence(r: "dict | None") -> str:
    """Why the outer-gamut row was withheld: the top quarter is too small."""
    from workflow.measurement_report import OUTER_GAMUT_MIN
    block = ((r or {}).get("gamut_populations") or {}).get("outer") or {}
    n = block.get("n")
    n = n if isinstance(n, int) else 0
    if n == 1:
        counted = tr("the most saturated quarter of this chart is one patch")
    else:
        counted = tr("the most saturated quarter of this chart is {n} "
                     "patches").format(n=n)
    return counted + tr("; at least {k} are needed for an average, which wants "
                        "roughly {c} patches carrying reference values on the "
                        "chart. Use a larger chart").format(
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
    "colour rows are only noise. Printing record is for a job you have to "
    "document without grading, a print you were asked to record rather than "
    "to approve. The two ISO types are for a print that has to answer to a "
    "printing condition somebody else supplied; they are greyed today, and "
    "pointing at the greyed entry says why.")
_PAIRING_HELP = (
    "Which limit set suits which type. Full colour check and Colour summary "
    "are the everyday pair for ChromIQ default, the set for checking a profile "
    "you built: 2.0 average and 3.0 maximum on the colour difference rows. "
    "ChromIQ tight halves those two, for critical work once a printer is "
    "behaving, and Quick check doubles them, for a health check only a clearly "
    "drifted printer fails; the grey rows move with them. Grey and "
    "tone check keeps three rows, the two grey balance ones and the mid-tone "
    "ramp, and those are the three a ChromIQ set says least about: the grey "
    "rows are recommendations, so the worst they can report is COND, and no "
    "ChromIQ set puts a limit on the mid-tone ramp at all, so it is shown for "
    "information. A Custom ISO set you have filled in judges all three. "
    "Printing record grades nothing: every row it can compute reads INFO "
    "whichever set is beside it, though the document still names the set it "
    "would otherwise have used. The two ISO types belong with the matching "
    "Custom ISO set, the one you have typed the published tolerances into from "
    "your own copy of the standard. Any set can be chosen with any type; the "
    "pairs above are the usual habits, not rules.")
_CHART_HELP = (
    "And the chart you printed decides what any of it can say. A row is judged "
    "only when the sheet carries the patches that row needs: at least eight "
    "grey steps from white to black for the grey rows, a single-ink or grey "
    "ramp through the mid-tones for the tone row, and, for the paper and solid "
    "rows, a chart built with FROM PROFILE GAMUT on the Create Chart tab. That "
    "one picks its colours from what your own profile can actually print and "
    "carries an aim value for each of them, which is the thing those rows are "
    "measured against. An ordinary test chart carries no such aim values, and "
    "what you see then depends on the set: a ChromIQ set puts no limit on "
    "those rows anyway, so they are left out of the table altogether, while a "
    "Custom ISO set shows them as N-A and the note under the results says what "
    "the chart was missing. Each row's own info icon in the Report limits "
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
    one_page = tr("This one is about a single measurement: the sheet this "
                  "window is open on. While it is chosen, “Show all "
                  "measurement runs” and the list of included measurements "
                  "are fixed to that sheet, and there is no detailed section, "
                  "because the whole report is one page to print and hand "
                  "over with a job.")
    lines = []
    for tid, name, blurb, _built in REPORT_TYPE_MENU:
        line = "\u2022 " + f"{tr(name)}: {tr(blurb)}"
        if tid == REPORT_TYPE_SUMMARY:
            line += " " + one_page
        lines.append(line)
    return ("\n\n" + tr("What each one is for") + "\n\n"
            + "\n\n".join(lines)
            + "\n\n" + tr(_WHEN_HELP)
            + "\n\n" + tr(_PAIRING_HELP) + "\n\n" + tr(_CHART_HELP))


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
    #: and the app-wide stores at that same moment (B8-384): the class default
    #: is None so a door that runs before the first sync falls back to reading
    #: them, rather than comparing against an empty tuple nothing ever holds.
    _prefs_at_sync: "tuple | None" = None
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
               "instruments or a chart is missing cube corners."),
            self, color=SPEC_GREEN))
        add_row.addStretch(1)
        box_v.addLayout(add_row)

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
            "trend, the tables and the PDF — nothing is changed on disk, and "
            "ticking it brings it straight back. Select a profile row and use "
            "“Remove Profile's Measurements…” to drop the whole profile.")
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
            f" background: {SPEC_GREEN}; color: #0a0a0a; }}")
        self._profile_list.itemSelectionChanged.connect(self._update_source_buttons)
        #: run keys the user unticked — session-only, nothing on disk changes.
        self._hidden_runs: "set[str]" = set()
        self._list_rows: "list[tuple]" = []
        self._building_list = False
        self._profile_list.itemChanged.connect(self._on_run_row_toggled)
        box_v.addWidget(self._profile_list)

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
        actions_row.addStretch(1)
        # **THE TWO TICK BOXES RIDE WITH "REPORT TYPE" NOW (B8-460).** Knut,
        # beta.5, put them to the right of the buttons *"to save a bit of
        # vertical space"*; his beta-25 mockup keeps them on one line and moves
        # that line to the right of the "Report type" pulldown, inside the
        # "Report settings" frame. The saving is the same and they now sit with
        # the setting they qualify.
        out_row.addSpacing(18)

        self._all_runs_check = QCheckBox(tr("Show all measurement runs"), self)
        # **THE TWO BOXES START FROM PREFERENCES ▸ REPORTS, AND FROM NOTHING
        # ELSE (R24-F1).** They were built from `report_show_all_runs` /
        # `report_show_details`, the last-used pair Sebastian asked for on
        # 2026-08-10 (*"so I don't have to select it every time again"*), and
        # B8-388 then made Preferences the source of the opening state without
        # moving these two lines. So Preferences said "Show detailed data for
        # each run, by default" was ON, and every window that did not go
        # through `_defaults_document()` opened with it OFF: measured on a
        # fresh settings file, which is every new installation. One question,
        # one answer -- and the last-used pair is still written below, so
        # restoring that behaviour is still the one line B8-388 promised.
        self._all_runs_check.setChecked(
            bool(settings.get("report_default_show_all_runs", True)))
        self._all_runs_check.toggled.connect(
            lambda on: (settings.set("report_show_all_runs",
                                     "true" if on else "false"),
                        self._settings_touched()))
        out_row.addWidget(self._all_runs_check)
        out_row.addWidget(TooltipButton(
            tr("Show all measurement runs"),
            tr("The report can look at one measurement, or at your whole "
               "history.\n\n"
               "With this ticked, every dated run in the list above is part "
               # The second em dash of a string this round touched, and the
               # same rule: it was joining two complete statements, so it
               # becomes a full stop.
               "of the report: the trend graphs, Report Scope, Report Results "
               "and the tables compare them side by side. Any run you have "
               "unticked in the list stays out.\n\n"
               # The em dash goes with the edit, which is the rule for a
               # string touched for any reason (CLAUDE.md, 2026-09-06). A
               # colon is what the break was doing here: what follows explains
               # what came before.
               "With it off, the report shows only the measurement it was "
               "opened on: one run, in full, with no comparison.\n\n"
               "Where a new report starts is yours to set, in Preferences ▸ "
               "Reports ▸ Measurement Report Defaults. A report you pick in "
               "“Report shown” brings its own setting with it.\n\n"
               "The saved PDF always matches what you see here."),
            self, min_width=440, color=SPEC_GREEN))
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
               "a page of its own: the colour-accuracy table with its "
               "verdict words against the run's limit set, paper white and "
               "darkest black, the eight cube corners, and the worst patches "
               "with their expected and measured colours side by side.\n\n"
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
            tr("Every report this run has generated, newest first. One entry "
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
               "itself is never touched."),
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
        top_v.addLayout(actions_row)
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
        # numbers it is judged with. Two controls, one rule: D9 governs both,
        # because a run whose dated verifications produced different kinds of
        # report is no more comparable than one whose limits moved under it.
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
            tr("Which kind of document this run's verifications produce. The "
               "measurement is the same either way; the type decides what is "
               "put in front of a reader, and how much of it.\n\n"
               "Like the limit set, the type belongs to the profile run, so "
               "every dated verification of the run produces the same kind of "
               "document and the dates can be compared. Another run in the "
               "project may use a different one.\n\n"
               "A type shown greyed is one ChromIQ cannot produce yet. The "
               "line under it says what is missing.")
            + _types_and_pairing_help(),
            self, min_width=460, color=SPEC_GREEN))
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
        settings_grid.addLayout(type_tail, 0, 2)

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
        self._limits_btn = QPushButton(tr("Show limits…"), self)
        self._limits_btn.setStyleSheet(_compact_btn)
        self._limits_btn.clicked.connect(self._on_open_limits)
        judged_row.addWidget(self._limits_btn)
        judged_row.addSpacing(10)
        # **THE CLAUSE IN BRACKETS WAS FALSE FROM THE MOMENT THE DOOR CHANGED
        # (B8-391).** It read *"(recalculates its dated reports)"*, which is
        # exactly what Knut ruled must not happen: *"All dated reports shall
        # NOT be recalculated."* It is removed rather than rewritten, like the
        # clause in the question behind it; the sentence that says what the
        # door now does is §M-PROPOSED and unapproved. Found in a photograph of
        # the real window, after the question had already been fixed.
        self._unlock_check = QCheckBox(tr("Unlock this run's limits"), self)
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
               "this is a deliberate decision to change them, and it "
               "recalculates nothing by itself: the report you have open is "
               "rebuilt when you press Generate report, and every report "
               "already saved stays exactly as it is. It can be ticked only "
               "when Preferences → Reports allows editing after the first "
               "measurement.\n\n"
               "A measurement that is not in a ChromIQ project (an imported "
               "file) is judged with the default set for this session only; "
               "nothing is stored for it.")
            + _sets_help()
            + "\n\n" + tr(_PAIRING_HELP) + "\n\n" + tr(_CHART_HELP),
            self, min_width=460, color=SPEC_GREEN))
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
            h = max(h, min(layout.minimumSize().height(), cap))
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
        if not any(self._is_this_measurement(r, ti3, dates_by_origin)
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
                built = getattr(self, "_doc_built_with", None)
                self._reread_one_source(s)
                # **`_rebuild_from_sources`, NOT `_render`.** The history rows,
                # the profile list and the button states all come from
                # `self._sources`, and a repaint that skips them redraws the
                # document from rows that were replaced a line above.
                self._rebuild_from_sources()
                if built is not None:
                    self._doc_built_with = built
                    self._show_stale_banner()
                return False
        key = keys[0]
        name, runs = self._gather_runs(ti3)
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
                pick = group[0]
                for r in group[1:]:
                    if (_report_order(r.get("_origin_dir"),
                                      r.get("_report_file"))
                            >= _report_order(pick.get("_origin_dir"),
                                             pick.get("_report_file"))):
                        pick = r
            # EVERY report file of this measurement, so the selector can offer
            # them without reading the folder again.
            pick["_all_report_files"] = files
            out.append(pick)
        return out

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
        return self._measurement_for(r, ti3.parent, ti3,
                                     dates_here=here) == ti3.parent / ti3.name

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
            # THE SAME MARK AFTER THE SAME NAME the other three doors put it
            # after, so a row says WHICH measurement the sentence below the
            # buttons is about. See `_scale_label`.
            from ui.measurement_filing import the_colour_scale_tag
            _unticked = self._rows_drawn_unticked()
            for si, s in enumerate(self._sources):
                n = len(s["runs"])
                self._profile_list.addItem(
                    f'{s["name"]}  ·  {n} '
                    + (tr("run") if n == 1 else tr("runs"))
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
        self._pdf_btn.setEnabled(has)
        self._reveal_btn.setEnabled(has)
        self._clear_btn.setEnabled(has)
        self._update_source_buttons()
        # THE LATEST REPORT, WITH ITS OWN SETTINGS, ONCE PER WINDOW (B8-388).
        # Before `_refresh`, so the page is drawn with those settings already
        # on it rather than drawn twice.
        self._open_on_the_latest_report()
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

        It is a DRAWING rule and not a narrowing: `_hidden_runs` is left
        exactly as the user set it, so the trend charts, the tables and the
        other report types keep the whole history, and choosing T1 and
        choosing away from it again gives the ticks back untouched. The list
        is disabled while T1 is chosen, so nothing a user can press disagrees
        with it.
        """
        from workflow.measurement_report import (REPORT_TYPE_SUMMARY,
                                                 report_type_is_built)
        base = set(self._hidden_runs)
        try:
            tid = self._report_type_now()
        except Exception:                                  # noqa: BLE001
            return base
        if tid != REPORT_TYPE_SUMMARY or not report_type_is_built(tid):
            return base
        keys = {k for kind, _si, k in self._list_rows if kind == "run" and k}
        subject = self._run_key(self._report) if self._report else ""
        return (keys - {subject}) if subject in keys else base

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
            # The first source's own measurement, not the newest thing in its
            # history — which, since the history spans the project's runs, is
            # routinely another run's (see `_subject_of`).
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
        self._rebuild_from_sources()

    def _on_clear_list(self) -> None:
        self._sources = []
        self._report, self._ti3 = None, None
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
        return (
            _data("_type_combo"),
            _data("_set_combo"),
            bool(getattr(self, "_all_runs_check", None) is not None
                 and self._all_runs_check.isChecked()),
            bool(getattr(self, "_detail_check", None) is not None
                 and self._detail_check.isChecked()),
            tuple(sorted(getattr(self, "_hidden_runs", ()) or ())),
        )

    def _settings_touched(self, *, type_id: str = "", set_id: str = "") -> None:
        """One of those five moved: keep the DOCUMENT as it is and say so.

        **AND THE LOADED DOCUMENT STOPS SPEAKING FOR THE CONTROLS.** A document
        restores the settings it was made with (L.2); the moment the user moves
        one of them, those are no longer the settings on screen, and a pulldown
        that went on showing the document's answer would be Knut's fifth defect
        with the halves swapped: an entry disagreeing with the window that names
        it. The document stays SELECTED and stays on the page, which is what the
        red line below is about; only its claim on the controls is dropped.

        The control keeps its own new value, and whatever that value does on
        disk it still does: choosing a limit set still binds the RUN, which is
        the yardstick for the dates still to come. It no longer recalculates
        one saved report (B8-384, Knut's *"Agreed. D23 stands."*), so there is
        no question in front of it any more either. What waits is the document
        on screen, so a reader can put a control back and be sure nothing moved
        under them.
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
        btn = getattr(self, "_generate_btn", None)
        if btn is not None and btn.isEnabled():
            self._show_stale_banner()
            return
        self._refresh_trend()
        self._render()

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
        return bool(built is not None and tuple(built) != self._doc_settings())

    def _show_stale_banner(self) -> None:
        if getattr(self, "_stale_label", None) is None:
            return
        self._stale_label.setVisible(self._settings_were_modified())
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
        self._doc_built_with = self._doc_settings()
        self._show_stale_banner()
        if not self._sources:
            self._view.setHtml(self._empty_html())
            self._remember_how_it_was_built()
            return
        self._view.setHtml(
            self._report_body_html(self._runs_for_report(), for_pdf=False))
        self._remember_how_it_was_built()

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
                 (lambda pt, kk=k: _accuracy_value(pt, kk)))
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
        lca = self._lca_dir(dirs) if dirs else self._anchor_dir()
        # The common ancestor being the ``runs`` container itself means the
        # report spans multiple runs → it belongs to the whole profile.
        if lca.name == "runs":
            return reports_subdir(lca.parent)
        return reports_subdir(lca)

    def _reports_to_generate(self) -> list:
        """WHICH MEASUREMENTS THIS BUTTON WRITES A REPORT FOR, which is not the
        same question as what the document covers.

        `_runs_for_document` answers "what is this page about", and that may
        legitimately span the project's runs: the trend across a printer's
        builds is the feature (#40, Knut). What Generate writes is narrower, for
        two reasons that are both in the design record:

        * the report TYPE is stored on the run (§10 of
          `docs/design/measurement_report_limits.md`), and this method stamps
          the WINDOW's run's type on every file it writes;
        * the limit set belongs to the run (§5), and it stamps the WINDOW's
          limits with it.

        Filing such a file into another run's folder therefore writes that run's
        measurement under this run's yardstick and this run's type, which is the
        cross-run leak this window shipped with. The comment on the button's own
        enable line already said what it should do: *"the button writes a report
        for the run the window is on"*.

        So: never across a run boundary, and one report per MEASUREMENT rather
        than one per report already saved of it. That second rule is its own
        fault — the count doubled on every press, because each saved report came
        back as a history entry and each history entry was written again. Driven
        on screen: three presses on one profiling run left four files.

        A measurement in no run (an imported file, CH-14) has no run boundary to
        stay inside, so it keeps whatever the document covers, deduplicated.

        ONE FILE PER FOLDER, AND IT IS ABOUT THE MEASUREMENT IN HAND. The
        folder is the unit because a dated verification keeps one report per
        date and each date is its own folder. Inside a folder the history can
        hold MANY measurements (measuring again archives the previous `.ti3`
        and reuses its name), and only one of them is the run's measurement
        today, so "the first one seen" is the oldest and exactly the wrong one:
        it would file a report of a sheet measured hours earlier, stamped with
        this window's limits and this window's type, while the page in front of
        the user described a different sheet. So the row the window is ON wins,
        and where the window is on neither, the later measurement does.
        """
        runs = self._runs_for_document()
        ctx = self._run_ctx
        mine: "set[str] | None" = None
        if ctx is not None:
            # ASKED OF THE RUN, NOT MATCHED OUT OF A STRING — `…/runs/run10`
            # starts with `…/runs/run1`, and this window has paid for that once
            # already (see `_recalculate_run`).
            mine = {str(ctx.run.dir)}
            try:
                mine |= {str(v.dir) for v in ctx.run.verifications()}
            except Exception:                            # noqa: BLE001
                pass
        subject = self._run_key(self._report) if self._report else None
        out: list = []
        seen: "dict[tuple, int]" = {}
        for r in runs:
            origin = str(r.get("_origin_dir") or "")
            if not origin or (mine is not None and origin not in mine):
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
        if ctx is None or not reports:
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
        if updating is not None:
            answer = self._ask_update_or_create_new()
            if answer == "cancel":
                return                      # *"Cancel aborts the Generate
                                            # Report function."*
            if answer != "update":
                updating = None             # *"'Create New' … will perform the
                                            # same function as if 'New report…'
                                            # option is selected."*
        self._write_the_document(ctx, reports, updating)

    def _document_being_updated(self) -> "dict | None":
        """The selected document Generate report would ask about, or None.

        Both halves of Knut's sentence have to hold, and neither is enough on
        its own:

        * **a report from "Report shown" is selected** — "New report…" is not a
          report, and a window that has generated nothing has none to update;
        * **its settings have been changed** — which is exactly the state the
          red line names, read through the one predicate that decides it, so
          the line and the question cannot disagree.

        With nothing selected, or with nothing moved since the page was drawn,
        Generate report writes a new report and asks nothing, as it always
        has.
        """
        key = str(getattr(self, "_loaded_doc_id", "") or "")
        if not key or key == NEW_REPORT_KEY:
            return None
        if not self._settings_were_modified():
            return None
        ctx = self._run_ctx
        docs = self._saved_documents(ctx.run if ctx is not None else None)
        return next((d for d in docs if d["key"] == key), None)

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
        title, body = M.CATALOGUE["M-REPORT-UPDATE-OR-NEW"].render()
        box = QMessageBox(self)
        set_question_icon(box)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        upd = box.addButton(tr("Update"), QMessageBox.ButtonRole.AcceptRole)
        new = box.addButton(tr("Create New"), QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
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

    def _write_the_document(self, ctx, reports: list,
                            updating: "dict | None" = None) -> None:
        """Write the page in front of the user as a saved report.

        **ONE FUNCTION FOR BOTH BUTTONS**, which is Knut's own sentence: *"The
        same function is used as when 'New report…' option is selected then
        Generate Report clicked, but is instead updating the selected
        report."* With *updating* None this is Generate report exactly as it
        was; with a document entry it keeps that document's id and its creation
        stamp, rewrites its files where they exist, and records the press as an
        update.
        """
        from datetime import datetime as _dt
        from workflow.measurement_report import (document_measurement_key,
                                                 document_updated_stamps,
                                                 new_document_id, report_type,
                                                 rewrite_report,
                                                 save_report, set_report_type,
                                                 stamp_document,
                                                 stamp_report_type,
                                                 stamp_verdict)
        # WHAT THE WINDOW IS SHOWING, which is the run's set unless a
        # document is loaded that was judged against another one. Anything else
        # would file a report against numbers the reader never saw.
        lim = (self._document_limits() or self._sticky_limits()
               or self._window_limits())
        # ONE PRESS OF GENERATE IS ONE DOCUMENT (B8-383, §13.4).
        #
        # It still writes one FILE per measurement, because a dated
        # verification's verdict is its own record and §5 is built on it being
        # in that date's own folder. What it did not write was anything saying
        # those files are one thing, so the selector listed a file per
        # measurement and Knut counted two new reports for one press: *"Clicking
        # 'Show all measurement runs' ON, and then generate report, creates 2
        # new reports under the saved reports, which is wrong behaviour."*
        # Measured before this: 2 files on disk became 4, then 6.
        #
        # The id is decided HERE, once, before the first file is written, and
        # every file of the press carries it along with the settings the press
        # was made with. That is the whole of the document record, it is
        # additive, and `REPORT_SCHEMA` stays 7: a report already on disk has
        # no block, is not touched by this, and is its own one-file document.
        when = _dt.now()
        now_iso = when.isoformat(timespec="seconds")
        # **AN UPDATE KEEPS THE DOCUMENT'S OWN id AND ITS OWN created**, which
        # is the whole of *"keep the current selected report"*: the entry stays
        # the same entry in the list, its name still leads with the moment it
        # was created, and the press is recorded on the end instead.
        #
        # A report written before the document record existed has neither, and
        # it is still the report the user selected. It is given an id so the
        # files it is made of are one thing, and its creation stamp is the one
        # its NAME already shows (`_document_created_stamp`), never today's.
        doc = (updating or {}).get("doc") if updating else None
        doc_id = str((doc or {}).get("id") or "") or new_document_id(when)
        doc_created = now_iso
        updated: "list[str]" = []
        # {measurement -> the file of this document that describes it}
        existing: "dict[str, Path]" = {}
        if updating is not None:
            doc_created = (str((doc or {}).get("created") or "")
                           or self._document_created_stamp(updating) or now_iso)
            updated = document_updated_stamps(doc) + [now_iso]
            existing = {
                self._run_key(r): Path(str(r.get("_origin_dir") or "")) /
                "reports" / name
                for r, name in (updating.get("members") or [])}
        # **WHAT THE DOCUMENT COVERS, NOT WHAT IT WRITES FILES FOR**, which
        # are two different lists and §13.4 asks for the first: *"the list of
        # measurements included"*. `_reports_to_generate` never crosses a run
        # boundary, on purpose (a file must not be filed into another run's
        # folder under this run's yardstick); the PAGE may, because the trend
        # across a printer's builds is the feature (#40).
        #
        # Recording the narrower list made the document claim to cover one run
        # when the reader was looking at two, and `_apply_document` believes
        # that claim: loading such a document hid every row of the other run.
        # Measured on a project with two runs, two reports each, since the
        # window began opening on the latest document (B8-388): two rows became
        # one.
        members = [{"dir": str(r.get("_origin_dir") or ""),
                    "created": str(r.get("created") or ""),
                    "ti3": str(r.get("ti3") or ""),
                    "key": document_measurement_key(
                        r.get("_origin_dir") or "", str(r.get("created") or ""),
                        str(r.get("ti3") or ""))}
                   for r in self._runs_for_document() if r.get("_origin_dir")]
        all_runs, detail = self._tick_state()
        scope = self._document_scope(members)
        saved, failed = [], []
        #: WHAT THE RED LINE WAS COMPARING AGAINST BEFORE THIS PRESS (R29-F2).
        #: A press that writes nothing must leave it exactly there: see the
        #: failure branch at the end of this method.
        was_built = getattr(self, "_doc_built_with", None)
        #: (measurement key, file name) for every file this press owns, so the
        #: page stays on the document's own files rather than on whatever the
        #: newest file of each measurement happens to be.
        written: "list[tuple[str, str]]" = []
        _tid_for_block = self._report_type_now()
        for r in reports:
            origin = r.get("_origin_dir")
            if not origin:
                continue
            # THE FILE THIS DOCUMENT ALREADY HAS FOR THIS MEASUREMENT, when
            # Update is what was pressed. A measurement the document did not
            # cover before still gets a new file, with this document's id on
            # it, because the settings the user changed may be the tick that
            # brought it in.
            here = existing.pop(self._run_key(r), None)
            try:
                rep = dict(r)
                # The window's own bookkeeping keys are not part of a report.
                for k in [k for k in rep if k.startswith("_")]:
                    rep.pop(k, None)
                stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                              set_label=lim.label_en, edited=lim.edited)
                stamp_report_type(rep, ctx.run)
                # …AND THE TYPE THE PULLDOWN IS SHOWING, which is the run's
                # unless a document is loaded that is of another kind. D9 puts
                # the type on the run and that is untouched; what this refuses
                # to do is write a document of a kind the reader was not
                # looking at.
                _tid = self._report_type_now()
                if _tid and _tid != report_type(rep):
                    set_report_type(rep, _tid)
                stamp_document(rep, doc_id=doc_id, created=doc_created,
                               type_id=report_type(rep),
                               compliance=rep.get("compliance"),
                               all_runs=all_runs, detail=detail,
                               measurements=members, scope=scope,
                               updated=updated)
                if here is not None and here.exists():
                    # **THE SAME FILE, THE SAME NAME, THE SAME DATE.** An
                    # update must not leave two live reports of one press
                    # behind, which is the reason `rewrite_report` exists at
                    # all (CH-29). Nothing is deleted and nothing is renamed.
                    path = rewrite_report(here, rep)
                else:
                    path = save_report(rep, Path(origin))
                saved.append(path)
                written.append((self._run_key(r), path.name))
            except Exception as exc:             # noqa: BLE001
                log.warning("could not generate a report in %s: %s", origin, exc)
                failed.append(str(origin))
        # **A MEMBER THE DOCUMENT NO LONGER COVERS KEEPS ITS VERDICT AND GETS
        # THE NEW BLOCK.** Unticking a measurement and pressing Update takes
        # it out of `members`, and its file is still on disk carrying this
        # document's id. Leaving the old block on it would make one document
        # say two different things about itself, depending on which of its
        # files the list happened to read first (`_saved_documents`). The
        # measurement's own verdict is not re-judged: it was judged when it
        # was part of the document and that is a fact about that sheet.
        for path in existing.values():
            try:
                leftover = json.loads(read_text(path))
            except Exception as exc:             # noqa: BLE001
                log.warning("could not re-read %s: %s", path, exc)
                continue
            stamp_document(leftover, doc_id=doc_id, created=doc_created,
                           type_id=_tid_for_block,
                           compliance=leftover.get("compliance"),
                           all_runs=all_runs, detail=detail,
                           measurements=members, scope=scope, updated=updated)
            try:
                rewrite_report(path, leftover)
            except OSError as exc:               # noqa: BLE001
                log.warning("could not rewrite %s: %s", path, exc)
        self._say_generated(saved, failed)
        self._forget_limits()
        # THE FILE IT JUST WROTE IS WHAT THE PAGE SHOWS, AND IT IS IN THE LIST.
        # `_refresh` redraws from `self._sources`, which `_gather_runs` filled
        # when the measurement was loaded, so a report written a second ago was
        # in neither: the "Saved reports" pulldown went on naming the same four
        # files and the page went on describing the one it was pointed at.
        # Driven in a real window (B8-252): an older report of the date chosen
        # in the pulldown, Generate pressed, one new file on disk, the selector
        # still at four entries, and the document unchanged. A button that
        # writes a file and changes nothing on screen is the exact complaint
        # this window has already been through twice.
        #
        # So the choice this measurement carried is dropped, because the user
        # has just asked for a NEW document of it, and the sources are read
        # again so the file is in the list and is the one the merge keeps.
        #
        # **ONLY WHEN SOMETHING WAS WRITTEN (R29-F2).** With every write
        # refused there is no new file to move to, and dropping the choice
        # would walk the page off the report the reader is looking at as a
        # consequence of a press that failed.
        if saved:
            for r in reports:
                self._chosen_reports.pop(self._run_key(r), None)
        # …AND AN UPDATE PUTS THE DOCUMENT'S OWN FILES BACK, because a rewrite
        # keeps the file's original name and date and "the newest file of this
        # measurement" may therefore be a different report altogether.
        for key, name in written:
            self._chosen_reports[key] = name
        if saved:
            # …AND THE WINDOW IS NOW ON THE DOCUMENT IT JUST WROTE, not merely
            # on one of its files. Without this the list would show the new
            # entry and the selection would land on it, but nothing would hold
            # the document open, so the next repaint could fall back to the
            # newest file of each measurement — which is the same file here and
            # a different one the moment a second document exists.
            self._loaded_doc_id = f"id:{doc_id}"
            self._loaded_doc = None          # read back off the file it wrote
            self._doc_settings_moved = False
            self._doc_created = doc_created
            self._forget_sticky_settings()
            self._reload_sources()
        else:
            # **A PRESS THAT WROTE NOTHING MAY NOT TAKE THE RED LINE DOWN
            # (R29-F2).** The line says *"Settings changed. Click 'Generate
            # report' to build the report with them, or put the setting
            # back."* After a press that saved no file, they are still not in
            # any report, so both halves of that sentence still stand.
            #
            # `_render` re-stamps `_doc_built_with` from the controls every
            # time it draws, which is right for a repaint and wrong for this:
            # the reader was just shown *"Nothing could be written"* and the
            # window then cleared the one signal that says their change has
            # not been applied. Measured on screen with the reports folder
            # read-only (round 29): Update pressed, the failure box shown, and
            # the red line down with the saved report untouched on disk.
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
        w_all = getattr(self, "_all_runs_check", None)
        w_det = getattr(self, "_detail_check", None)
        widgets = [w for w in (w_type, w_set, w_all, w_det) if w is not None]
        before = self._doc_settings()
        blocked = [(w, w.blockSignals(True)) for w in widgets]

        def _put(vals):
            t, st, allr, det, hidden = vals
            if w_type is not None and w_type.findData(t) >= 0:
                w_type.setCurrentIndex(w_type.findData(t))
            if w_set is not None and w_set.findData(st) >= 0:
                w_set.setCurrentIndex(w_set.findData(st))
            if w_all is not None:
                w_all.setChecked(bool(allr))
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
        try:
            _put(tuple(built))
            if state:
                (self._type_as_built, self._limits_cache,
                 self._limits_by_origin, self._limits) = (
                     state[0], dict(state[1]), dict(state[2]), state[3])
            yield
        finally:
            (self._type_as_built, self._limits_cache,
             self._limits_by_origin, self._limits) = held
            _put(before)
            for w, was in blocked:
                w.blockSignals(was)

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
        if not path:
            return
        # The dialog does not force the extension — a name typed without one
        # must still come out as a .pdf.
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

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
                # out the current one) and embed it as a resource. Kept compact
                # so all four trend charts fit on the one trend page (Knut).
                avg_thr, max_thr = self._thresholds()
                for i, (_c, title, metrics, y_max, dec, auto) in enumerate(
                        self._trend_configs()):
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
                    doc.addResource(QTextDocument.ResourceType.ImageResource,
                                    url, img)
                    charts_html += (
                        "<div style='font-size:16px;font-weight:bold;"
                        "margin-top:4px'>" + html.escape(title) + "</div>"
                        f"<img src='chart://{i}' width='600'>" + _gap())
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
        # **A ROW THAT HAS ANSWERED ONCE KEEPS ITS ANSWER.** `run_context_for`
        # asks the disk, so a project renamed or moved while the window is open
        # makes every row of it fall through to the WINDOW's limit set, and the
        # document is written against one set: a measurement judged against
        # another was then silently pulled INTO it. Measured: folder present,
        # 2 kept and 1 dropped; folder renamed, 3 kept and 0 dropped, under a
        # heading still naming one "Judged against" set (R18-F4).
        #
        # This is not the memo that was removed from the scope count. That one
        # invented a TOTAL the disk no longer supported; this remembers a
        # property of a row that was read from its own run, and the alternative
        # is not silence but a different document.
        seen = getattr(self, "_limits_by_origin", None)
        if seen is None:
            seen = self._limits_by_origin = {}
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
                seen[str(origin)] = cache[key]
                return cache[key]
            if str(origin) in seen:
                return seen[str(origin)]
        return self._window_limits()

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
        self._adopt_visible_document(run)
        # WHAT THE USER IS ABOUT TO BE SHOWN, stamped here because here is the
        # last moment this window and the run agree. A guard that stamps it
        # when a control is CLICKED has already swallowed everything that
        # happened while the user was reading the screen, which is the whole
        # window a second writer has to work in. A challenge round drove
        # exactly that: rebind the run, then click, and the rebind was inside
        # the "before" the guard compared against.
        self._run_state_at_sync = self._run_state_now(run) if run else ()
        # **AND THE APP-WIDE STORES, AT THE SAME MOMENT AND FOR THE SAME
        # REASON.** The overrides on the set in the pulldown are what
        # `bind_run` will copy onto the run, and it reads them LIVE. That used
        # to be guarded by re-reading them across the recalculate question;
        # with the question gone (B8-384) the only window left is the one that
        # matters anyway, between the moment the user was shown these controls
        # and the moment they used one. R19-1 is what happens without it:
        # another window overrides the chosen set, and the run is bound to
        # numbers nobody in this window ever saw.
        self._prefs_at_sync = self._prefs_state_now()
        self._syncing_limits = True
        try:
            self._set_combo.clear()
            ids = selectable_set_ids(self._overrides())
            # **THE LOADED DOCUMENT'S OWN SET, WHEN ONE IS LOADED (B8-382).**
            # Knut: *"Changing selected report in the saved report pulldown
            # does not change any of the other settings that the selected
            # report had when it was generated."* The page already judges each
            # report by the set its own file records (`_yardstick_of`); this is
            # what stops the pulldown above it saying something else.
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
            # **KNUT PUT THIS CONTROL BACK, AND IT NEVER DISAPPEARS AGAIN
            # (B8-520).** 2026-09-20, reviewing beta 26: *"In the Measurement
            # Report window, relating to the new layout of buttons and
            # elements, you removed the 'Unlock this run's limits' checkbox and
            # its help icon. They should still be there and work as before."*
            # And, on the state two loaded runs put the window in: *"the
            # checkbox 'Unlock this run's limit set' was suddenly gone …
            # 'Unlock this run's limit set' should be available."*
            #
            # It was not the beta-25 re-layout that took it away, and that is
            # reported rather than repeated: the widget is built and added to
            # `judged_row` in both betas, byte for byte, and the line below is
            # the one that hid it. It has hidden it since round 6, on this
            # reasoning:
            #
            #   an unticked "Unlock this run's limits" MEANS "this run is
            #   locked", and greyed means "and you cannot change that"; on a
            #   run with one dated verification the pulldown is live, the
            #   button says "Edit limits…" and the column is editable, so the
            #   box sat dim beside three live controls saying the opposite of
            #   all of them.
            #
            # That reading of a greyed box is ours; his instruction is his, and
            # it wins. A control that vanishes is the worse of the two evils --
            # a user cannot ask why a control is grey if it is not there -- so
            # the box is ALWAYS on screen and the honesty problem is answered
            # where it belongs, in a tooltip that says what would have to be
            # true for it to be usable.
            self._unlock_check.setVisible(True)
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
                # **A CALIBRATION IS IN THE PROJECT, AND THIS SAID IT WAS NOT
                # (R24-F6).** `run_context_for` answers None for anything that
                # is not `runs/runN/…`, and the sentence read that as "not in a
                # ChromIQ project" -- to a user looking at
                # `<project>/cal/<name>-cal.ti3`, which is where
                # `calibration_run_type.md` puts a calibration. The half that
                # matters, and the reason the controls say anything at all, is
                # the second one: there is no run for the choice to be stored
                # on. That half was true in both states and is all that is
                # claimed now.
                self._judged_label.setText(tr("Judged against:"))
                tip = (tr("This measurement does not belong to a profile run, "
                          "so the choice is not stored anywhere.")
                       if self._inside_a_project() else
                       tr("This measurement is not in a ChromIQ project, so "
                          "the choice is not stored anywhere."))
            # **AND WHY IT IS NOT THE PREFERENCES DEFAULT, WHEN IT IS NOT
            # (B8-526).** Knut, beta 26: *"When selecting 'New report…' in
            # Report shown, then the Judged against is set to Quick check,
            # which is not set as the default limit set in the Report Limits
            # window."* He is reading a run that is BOUND to another set, and
            # §5 of `measurement_report_limits.md` is why: the set belongs to
            # the profile run, and the Preferences default is what a run that
            # is not bound yet takes. Measured on his own demo pack: 24 of its
            # 39 runs are bound to a set other than the Preferences default.
            #
            # Whether "New report…" should override that is HIS call and is
            # asked of him rather than answered here -- a report judged against
            # a set its run is not bound to is the one thing this window must
            # never file. What the window can do without a ruling is stop being
            # silent about it.
            if (self._loaded_doc_id == NEW_REPORT_KEY and run is not None
                    and not several and lim.bound
                    and lim.set_id != self._default_set_id()):
                from workflow.compliance_sets import SET_BY_ID
                d = SET_BY_ID.get(self._default_set_id())
                tip = tr(
                    "This run is judged against {set}, which was stored on the "
                    "run at its first verification so that every dated "
                    "verification of the run stays comparable. The default for "
                    "a run that has none is {default}, in Preferences, "
                    "Reports.").format(
                        set=lim.set_label,
                        default=tr(d.label) if d else self._default_set_id())
            for w in (self._set_combo, self._limits_btn):
                w.setToolTip(tip)
            # **AND THE UNLOCK BOX SAYS WHY IT IS GREY, IN ITS OWN WORDS.** It
            # shares the other two controls' sentence only when there is no
            # more specific one: a box that is always on screen has to answer
            # "why can I not press this?" wherever it is dim, which is the
            # whole of what hiding it used to answer.
            self._unlock_check.setToolTip(
                self._why_the_unlock_box_is_greyed(run, several, locked, lim)
                or tip)
            self._sync_type_combo(run, several)
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
        self._restore_the_documents_view(self._loaded_doc,
                                         recorded=bool(entry["doc"]))

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
        from workflow.measurement_report import document_key_of
        if run is None:
            return []
        try:
            mine = {str(run.dir)} | {str(v.dir) for v in run.verifications()}
        except Exception:                            # noqa: BLE001
            mine = {str(run.dir)}
        docs: "dict[str, dict]" = {}
        order: "list[str]" = []
        for r in self._history:
            origin = str(r.get("_origin_dir") or "")
            if origin not in mine:
                continue
            for name in (r.get("_all_report_files") or []):
                doc = self._document_of(origin, name, r)
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
        out = [docs[k] for k in order]
        for entry in out:
            entry["label"] = self._document_label(entry)
        # Newest first: the one a reader is most likely to want is at the top,
        # and `_report_order` is this window's one answer to "which of these
        # was written last".
        out.sort(key=lambda e: e["order"], reverse=True)
        return out

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
        from workflow.measurement_report import (SCOPE_ALL_DATES,
                                                 SCOPE_MULTIPLE_DATES,
                                                 document_scope_of)
        scope = document_scope_of(doc)
        bits.append(tr("All dates") if scope == SCOPE_ALL_DATES
                    else tr("Multiple dates") if scope == SCOPE_MULTIPLE_DATES
                    else tr("One date"))
        if doc.get("detail"):
            bits.append(tr("Detailed"))
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

    def _tick_state(self) -> "tuple[bool, bool]":
        """(Show all measurement runs, Show detailed data), as they stand."""
        return (bool(getattr(self, "_all_runs_check", None) is not None
                     and self._all_runs_check.isChecked()),
                bool(getattr(self, "_detail_check", None) is not None
                     and self._detail_check.isChecked()))

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
        return {
            "id": entry["key"],
            "created": str(rep.get("created") or ""),
            # **WHAT THE FILE RECORDS, NOT WHAT IT DEFAULTS TO.**
            # `report_type` answers T2 for a file that chose nothing, and a
            # document built on that answer makes the window claim a choice
            # nobody made: §10 says a report with no type of its own follows
            # the RUN, and "" is what lets `_report_type_now` do that.
            "type": recorded_report_type(rep),
            "compliance": recorded_compliance(rep),
            "all_runs": False,
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
        return RunLimits(sid, set_label(sid, stored), limits_from_json(thr),
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
        """
        for r, name in (entry.get("members") or []):
            why = self._saved_delete_refusal(r, name)
            if why:
                return why
        return ""

    def _saved_report_label(self, r: dict, name: str) -> str:
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
        hit = cache.get(str(path))
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
            bits.append(tr(report_type_name(report_type(rep))))
        except Exception:                            # noqa: BLE001
            pass
        comp = recorded_compliance(rep)
        if comp:
            from workflow.compliance_sets import set_label
            bits.append(set_label(str(comp.get("set_id", "")),
                                  str(comp.get("set_label", ""))))
        _rank, _when_saved, _n = _report_file_order(name)
        if _rank:
            # the stamp is `%Y-%m-%d_%H-%M-%S`; a person reads the date with
            # hyphens and the clock with colons
            day, _, clock = str(_when_saved).partition("_")
            saved = tr("saved {when}").format(
                when=f"{day} {clock.replace('-', ':')}")
            bits.append(saved if _n <= 1 else f"{saved} ({_n})")
        label = " · ".join(bits)
        cache[str(path)] = (stamp, label)
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
        """
        import json
        from core.file_manager import VERIFICATIONS_DIRNAME
        origin = Path(str(r.get("_origin_dir") or ""))
        if origin.parent.name != VERIFICATIONS_DIRNAME:
            return ""
        try:
            spares = 0
            for p in sorted((origin / "reports").glob("report_*.json")):
                try:
                    json.loads(read_text(p))
                except Exception:             # noqa: BLE001
                    continue                  # not a verdict; see below
                spares += 1
                if spares > 1:
                    break                     # two is all this has to know
        except OSError:                       # unreadable: the answer it gave
            spares = len(r.get("_all_report_files") or [])
        if spares > 1:
            return ""
        return tr("The only saved report of a dated verification is kept: its "
                  "verdict is this run's record of that date.")

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
                      "Reports. Nothing is written until you press Generate "
                      "report."),
                Qt.ItemDataRole.ToolTipRole)
            for d in docs:
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
            i = next((n for n, d in enumerate(docs) if d["key"] == lands), -1)
            # +1 for the "New report…" row above them; -1 (nothing matched)
            # and the new-report state both land on it.
            combo.setCurrentIndex(i + 1 if i >= 0 else 0)
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
        self._saved_label.setText(
            tr("Report shown ({run}):").format(run=run.dir.name)
            if run is not None else tr("Report shown:"))
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
        """Put *full* on the line beside "Report shown", wrapped to TWO lines.

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
        two = 2 * fm.lineSpacing() + 2
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
        if key == NEW_REPORT_KEY:
            self._start_new_report()
            return
        self._load_document(key)

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
        if not key or key != self._loaded_doc_id:
            return
        if key == NEW_REPORT_KEY:
            self._start_new_report()
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
        against" fall through to the run's own set (`_document_limits` returns
        None, `_sync_limit_controls` shows `lim`). That IS the default: §5 says
        the set belongs to the run, a run that is not bound takes the
        Preferences default set, and Knut asked for no second selector because
        *"The Report Limits button contain the Judged Against default
        chosen"*.
        """
        ctx = self._run_ctx
        s = self._settings
        return {
            "id": "new",
            "created": "",
            # **NO TYPE IS PINNED HERE, and that is deliberate.** D9 puts the
            # type on the RUN, and a document that recorded one would freeze
            # it: a run whose type changes under an open window would go on
            # being drawn as the type this dict was built with.
            # `_report_type_now` asks the run and falls back to the
            # Preferences default, which is the same rule one step later and
            # the only one that stays true.
            "type": "",
            "compliance": None,
            "all_runs": bool(s.get("report_default_show_all_runs", True)),
            "detail": bool(s.get("report_default_show_details", True)),
            "measurements": [],
        }

    def _start_new_report(self) -> None:
        """"New report…" was chosen: load the Preferences defaults (B8-388).

        Nothing on disk is read, written, deleted or renamed by this: it is the
        state the window is in before a document exists, made reachable again
        from the list. The user may then change anything, and Generate report
        writes a NEW document, which is Knut's K.1 (*"It is better that
        existing reports are not overwritten"*) unchanged.
        """
        self._load_the_defaults()
        # A NEW REPORT IS ABOUT THE NEWEST FILE OF EACH MEASUREMENT, so the
        # document a click left behind stops choosing which file is drawn.
        self._chosen_reports.clear()
        self._hidden_runs = set()
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
        for chk, val in ((getattr(self, "_all_runs_check", None),
                          bool(doc.get("all_runs"))),
                         (getattr(self, "_detail_check", None),
                          bool(doc.get("detail")))):
            if chk is None:
                continue
            chk.blockSignals(True)
            chk.setChecked(val)
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
        self._loaded_doc_id = key
        doc = entry["doc"] or self._settings_of_one_saved_report(entry)
        self._loaded_doc = doc
        self._doc_settings_moved = False
        self._doc_created = self._document_created_stamp(entry)
        self._forget_sticky_settings()
        # WHICH FILE OF EACH MEASUREMENT THE PAGE IS DRAWN FROM. Only the
        # document's own measurements are touched: a row belonging to another
        # run of the project is not this document's to move.
        for r, name in entry["members"]:
            self._chosen_reports[self._run_key(r)] = name
        # THE SUBJECT IS ONE OF ITS OWN MEASUREMENTS, the newest of them, so
        # that with "Show all measurement runs" off the page is about a sheet
        # this document is actually about.
        if entry["members"]:
            self._report = max((r for r, _n in entry["members"]),
                               key=lambda r: str(r.get("created") or ""))
        self._restore_the_documents_view(doc, recorded=bool(entry.get("doc")))
        # The type and the limit set follow from `_loaded_doc`: they are read
        # back by `_report_type_now` and `_sync_limit_controls`, which the
        # repaint the caller runs. Setting the two combos here as well would be
        # two answers to one question, and this window has paid for that before.

    def _restore_the_documents_view(self, doc: "dict | None", *,
                                    recorded: bool = True) -> None:
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
        for chk, val in ((getattr(self, "_all_runs_check", None),
                          bool(doc.get("all_runs"))),
                         (getattr(self, "_detail_check", None),
                          bool(doc.get("detail")))):
            if chk is None:
                continue
            chk.blockSignals(True)
            chk.setChecked(val)
            chk.blockSignals(False)
        if not recorded:
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
        self._hidden_runs = (here - keys) if (keys & here) else set()
        # The caller repaints, and `_refresh` is what draws the rows (B8-521).

    def _reload_sources(self) -> None:
        """Read every loaded measurement's reports off disk again.

        The one way back from a change to what is ON DISK, which is what a
        delete is. `_rebuild_from_sources` only re-reads what `_gather_runs`
        already put in `self._sources`, so on its own it would redraw the
        window from the file that has just been removed.
        """
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
        self._rebuild_from_sources()

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
        if dest is None:
            return
        title, body = M.CATALOGUE["M-REPORT-DELETE"].render(
            what=entry.get("label", ""), n=len(paths), where=str(dest))
        if not self._confirm(title, body):
            return
        try:
            dest.mkdir(parents=True, exist_ok=True)
            for path in paths:
                target = dest / path.name
                n = 1
                while target.exists():
                    target = dest / f"{path.stem}_{n}{path.suffix}"
                    n += 1
                shutil.move(str(path), str(target))
                log.info("report moved to old/: %s -> %s", path, target)
        except OSError as exc:
            log.warning("could not move %s: %s", dest, exc)
            warn(self, title, str(exc))
            self._reload_sources()
            return
        for r, name in members:
            key = self._run_key(r)
            if self._chosen_reports.get(key) == name:
                self._chosen_reports.pop(key, None)
        if self._loaded_doc_id == entry["key"]:
            self._loaded_doc_id = ""
            self._loaded_doc = None
            self._doc_created = ""
        self._reload_sources()

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
        from workflow.measurement_report import (REPORT_TYPE_DEFAULT,
                                                 REPORT_TYPES, report_type)
        from workflow.run_compliance import run_report_type
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
        sticky = str(getattr(self, "_sticky_type", "") or "")
        if sticky in REPORT_TYPES:
            return sticky
        types = self._types_of_loaded_runs()
        if len(types) > 1:
            return REPORT_TYPE_DEFAULT
        ctx = self._run_ctx
        if ctx is not None:
            # **THE RUN FIRST, THE PREFERENCES DEFAULT BEHIND IT (B8-388).**
            # Knut: *"The type belongs to the run, yes, but the default should
            # be the 'Full colour check'."* `run_report_type` answers a run
            # that never chose with a hard-coded T2; this answers it with
            # whatever Preferences ▸ Reports says, and a run that HAS chosen is
            # untouched, which is D9.
            from workflow.run_compliance import report_type_default_for
            return report_type_default_for(
                ctx.run,
                str(self._settings.get("report_default_type", "") or ""))
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
        self._generate_btn.setEnabled(
            run is not None and not several
            and bool(self._reports_to_generate()))
        # A ONE-PAGE SUMMARY IS ABOUT ONE SHEET, so the tick that widens every
        # other report to the whole history is disabled rather than left to do
        # nothing visible. See `_one_measurement` for what it was doing before.
        from workflow.measurement_report import REPORT_TYPE_SUMMARY
        if getattr(self, "_all_runs_check", None) is not None:
            one_page = current == REPORT_TYPE_SUMMARY
            # **ONE MEASUREMENT IN THE LIST TURNS IT OFF, AND THAT BEATS THE
            # PREFERENCES DEFAULT (B8-392).** Knut, 2026-09-18: *"If the list
            # of measurement dates to be included only holds one measurement,
            # then the 'Show all measurement runs' is automatically set to OFF,
            # and the report name should include the flag 'One date'."*
            #
            # It is a rule about the list, not about the user, so it is applied
            # wherever the list is drawn rather than only where the default is
            # read: B8-388 makes that box default ON, and without this the
            # default would tick it on a window that has one measurement to
            # show. It changes nothing a reader can see either way — with one
            # measurement loaded, "all of them" and "this one" are the same
            # page — so turning it off is the honest state rather than a
            # setting that claims to do something.
            # **AND IT IS GIVEN BACK WHEN THE LIST GROWS.** The rule is about
            # a list holding one measurement, not about the user: opening a
            # window on one sheet and then adding a project must widen the
            # report exactly as it did before, or a one-measurement window
            # would quietly switch the setting off for the rest of the session.
            # The box is DISABLED while it is alone, so nothing a user does can
            # be mistaken for this.
            alone = len(getattr(self, "_history", []) or []) <= 1
            if alone and self._all_runs_check.isChecked():
                self._all_runs_forced_off = True
                self._all_runs_check.blockSignals(True)
                self._all_runs_check.setChecked(False)
                self._all_runs_check.blockSignals(False)
            elif not alone and getattr(self, "_all_runs_forced_off", False):
                self._all_runs_forced_off = False
                self._all_runs_check.blockSignals(True)
                self._all_runs_check.setChecked(True)
                self._all_runs_check.blockSignals(False)
            self._all_runs_check.setEnabled(not one_page and not alone)
            self._all_runs_check.setToolTip(tr(
                "The one-page colour summary is about the single measurement "
                "you are looking at, so it does not widen to the whole "
                "history.") if one_page else tr(
                "There is one measurement in the list, so there is no history "
                "to widen to. Add another measurement, or open the report on a "
                "run with more dated verifications.") if alone else "")
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
            det.setEnabled(not one_page)
            det.setToolTip(tr(
                "The one-page colour summary has no per-run detail section: it "
                "is one page about one measurement, to print and hand over "
                "with a job. Choose another report type to see the detailed "
                "data.") if one_page else "")
        lst = getattr(self, "_profile_list", None)
        if lst is None:
            return
        if one_page:
            lst.setEnabled(False)
            lst.setToolTip(tr(
                "A one-page colour summary describes the single measurement "
                "this window is open on, so the list shows that one sheet and "
                "cannot be changed while the type is chosen. Choose another "
                "report type to include more measurements; the ticks you had "
                "come straight back."))
        else:
            lst.setEnabled(True)
            lst.setToolTip(self._list_tooltip)

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
        if run is None:
            return ""
        from workflow.measurement_report import (generated_report_types,
                                                 report_type_name)
        counts = generated_report_types(run)
        if not counts:
            return ""
        return "\n".join(
            tr("{type} ({count})").format(type=tr(report_type_name(tid)), count=n)
            for tid, n in sorted(counts.items()))

    def _show_generated_reports(self, _href: str = "") -> None:
        """The whole list, when the one line could not hold it."""
        if not self._generated_full:
            return
        from ui.warning_sign import inform
        inform(self, tr("Reports generated for this run"),
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
            #
            # THROUGH THE ONE DOOR, like every other setting. This branch kept
            # calling `_refresh` after the other four learned to wait, so on a
            # measurement outside any project the type pulldown still rebuilt
            # the document on its own while the limit pulldown two rows below
            # it did not. An adversary round drove both in one window and
            # photographed the difference; Knut's original complaint, *"the
            # report auto-generates whenever report type … is changed"*, was
            # still true there. `_settings_touched` repaints here anyway,
            # because a measurement in no run has no Generate button to press,
            # so the behaviour is the same and there is now one rule.
            self._session_type = type_id
            self._settings_touched(type_id=type_id)
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
        # THE TYPE IS STORED ON THE RUN AND THE DOCUMENT WAITS. Every refusal
        # path above still calls `_refresh`, because those PUT THE CONTROL BACK
        # and the document has to match the control again. This is the path
        # where the change took.
        #
        # AND IT NAMES WHAT IT JUST CHANGED (B8-462), so the pin taken inside
        # is the type the user chose and not the one the page still shows.
        self._settings_touched(type_id=type_id)

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
            self._mismatch.setText(fm.elidedText(one, Qt.TextElideMode.ElideRight, width))
        self._mismatch.setToolTip(full)
        self._mismatch.setVisible(True)

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
            "no_corners": tr("the chart has no patch at the colour corners this "
                             "row needs"),
            # WHAT THE CODE MEANS, WHICH IS NOT WHAT THIS USED TO SAY.
            # `REASON_NOT_COMPUTED` is set when the BLOCK IS MISSING FROM THIS
            # REPORT; it says nothing about whether a file can be read. The old
            # sentence named a cause, "the measurement file could not be read
            # again", and that cause was untrue in both cases that reach here:
            # a report saved before the row existed was never asked for the
            # value, and a report of a measurement that has since been
            # re-measured has its own .ti3 sitting in the run's old/ folder.
            # This sentence is the one thing that is true of both.
            "not_computed": tr("this value is not in this saved report; it "
                               "was not one of the values ChromIQ kept when "
                               "the report was saved"),
            # #182 S2w, approved by Knut on 2026-09-18. TWO codes rather than
            # one, because they send a reader to different places: the first
            # asks the chart to declare a strip at all, the second says the
            # strip it declares is too short to average over. A reason a
            # reader cannot act on is not a reason, so each names the thing to
            # change and not only the thing that is wrong.
            "no_control_strip": tr(
                "this chart declares no control strip; name the patches that "
                "make one up in a file beside the chart, called after it with "
                "\".control-strip.json\" on the end, or in a "
                "CONTROL_STRIP_IDS keyword in its .ti1 or .ti2"),
            "control_strip_too_small": _control_strip_sentence(r),
            "too_few_surface_patches": _surface_gamut_sentence(r),
            "too_few_outer_patches": _outer_gamut_sentence(r),
        }
        return texts.get(code or "", "")

    def _note_sentence(self, code: "str | None") -> str:
        """What one note code says, as a sentence that COMMENTS A VERDICT.

        Not a reason: `_reason_sentence` above explains why a row has no
        verdict, and these explain what to know about one that has. Knut's
        ruling of 2026-09-13 made the two different things, and the example he
        gave is this one, *"regarding the tint of a paper and profile
        combination"*.
        """
        return {
            "printing_unrecorded": tr(
                "How this sheet was printed is not recorded, so the grey rows "
                "are judged against the chart's own design in absolute Lab. "
                "The paper's own tint is part of that measurement, so a good "
                "print on a warm or tinted paper reads higher here than the "
                "profile deserves. Record the printing condition, or read this "
                "row against the paper you printed on."),
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
        from workflow.compliance_sets import ROW_BY_ID
        from workflow.measurement_report import numbered_notes
        merged: list = []
        for r in runs or ():
            if _is_raw_drift(r):
                continue
            rows, _rec = self._verdict_rows(r)
            merged.extend(rows)
        out = []
        for n, code, rids in numbered_notes(merged):
            sentence = self._note_sentence(code)
            if not sentence:
                continue
            labels = [tr(ROW_BY_ID[rid].label) if rid in ROW_BY_ID else str(rid)
                      for rid in rids]
            out.append((n, ", ".join(labels), sentence))
        return out

    def _note_numbering(self, runs: list):
        """The raw numbering the verdict cells mark themselves from."""
        from workflow.measurement_report import numbered_notes
        merged: list = []
        for r in runs or ():
            if _is_raw_drift(r):
                continue
            rows, _rec = self._verdict_rows(r)
            merged.extend(rows)
        return numbered_notes(merged)

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

    def _yardstick_of(self, r: dict):
        """The limit set a column is judged with, as a comparable key.

        The RECORD first: a saved report carries the copy of the numbers it was
        judged against, and that copy is the yardstick whatever the run is
        bound to today. A column with no record is worked out live, so its
        yardstick is the live one, which is what `_verdict_rows` uses for it.
        """
        from workflow.measurement_report import (recorded_compliance,
                                                 yardstick_key)
        comp = recorded_compliance(r)
        if comp is not None:
            return yardstick_key(comp)
        from workflow.compliance_sets import limits_to_json
        lim = self._limits_for(r)
        return yardstick_key({"set_id": lim.set_id,
                              "thresholds": limits_to_json(lim.limits)})

    def _one_limit_set(self, runs: list) -> "tuple[list, list]":
        """``(in the report, left out of it)``: ONE limit set per document.

        **A REPORT IS WRITTEN AGAINST ONE "JUDGED AGAINST" SET, AND ONLY
        MEASUREMENTS JUDGED AGAINST THAT SET MAY BE IN IT.** The project's
        design authority, 2026-09-16, on a report of his own:

            "the report sometimes lists in red text that several reports use
            different Judged against threshold set […] only report data using
            the same judged against threshold sets as the judge against
            setting set in the report should be used when writing the report
            text. Not mix them together in the report output."

        Until now the document put every gathered measurement in one results
        table whatever it had been judged against, printed a "Judged against"
        row naming three different sets side by side, and mitigated it with a
        red line saying the words were not comparable. Telling a reader that
        the table they are reading cannot be read is not a report.

        **THE HISTORY IS KEPT AND THE SETS ARE SEPARATED, which is not the same
        as dropping either.** Every measurement is still gathered, still in the
        run list, still tickable and still a point on the trend over time,
        which plots measured values and carries no verdict. What narrows is the
        DOCUMENT: the results, the metric tables and the comparison, the parts
        that carry words.

        **THE ANCHOR IS THE SHEET THE WINDOW IS ON**, never the pulldown. A
        run's own profiling report is deliberately not recalculated when its
        limit set changes (`_recalculate_run` walks `run.verifications()`,
        which is what §5 of the design record specifies), so a run bound to one
        set can hold a report judged against another, and anchoring on the
        pulldown would throw the window's own subject out of its own report.
        Where the subject is not in the list (the user unticked it), the newest
        measurement in the list is the anchor, so the document is never empty.

        A raw drift check is never judged at all and never leaves: it has no
        verdict to be incomparable with.
        """
        if len(runs) <= 1:
            return list(runs), []
        judged = [r for r in runs if not _is_raw_drift(r)]
        if not judged:
            return list(runs), []
        want = None
        key = self._run_key(self._report) if self._report else None
        if key is not None:
            for r in judged:
                if self._run_key(r) == key:
                    want = self._yardstick_of(r)
                    break
        if want is None:
            want = self._yardstick_of(judged[-1])
        keep, out = [], []
        for r in runs:
            if _is_raw_drift(r) or self._yardstick_of(r) == want:
                keep.append(r)
            else:
                out.append(r)
        return keep, out

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
        if recorded:
            return tr(
                "This verdict was recorded when the report was saved, against "
                "the limit set {label}. It is what this measurement was judged "
                "to be at the time, and this run's current limits do not "
                "change it. Only unlocking the run's limits recalculates it."
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
                "worked out now against this run's limit set {label}."
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
        # **"NOTHING CHANGED" IS ASKED OF WHAT THE PULLDOWN WAS SHOWING, NOT OF
        # THE RUN (N.1).** The box shows the LOADED DOCUMENT's set when one is
        # loaded (`_sync_limit_controls`), and that need not be the run's: a
        # report judged against Quick check on a run bound to ChromIQ default
        # is an ordinary state, and since B8-388 the window OPENS in it,
        # because it opens on the latest report created.
        #
        # Comparing with the run's set made choosing the run's own value a
        # no-op in every sense: no bind (there was nothing to bind), no red
        # line, and a document left claiming the set it was made with under a
        # pulldown now naming another. That is Knut's fifth defect exactly, in
        # the one window this round is about.
        # THE STICKY SET COUNTS AS "WHAT THE PULLDOWN WAS SHOWING" TOO
        # (B8-462): after a type change the box may be showing the document's
        # set over a run bound to another, and choosing the RUN's set from
        # there is a real change that must not read as a no-op.
        shown = self._document_limits() or self._sticky_limits() or lim
        if not set_id or set_id == shown.set_id:
            return
        if set_id == lim.set_id:
            # The RUN already carries it, so there is nothing to bind, nothing
            # to ask and nothing to write. What did change is the page: the
            # document on screen was made with another set and stops speaking
            # for the controls, and the red line says to press Generate report
            # (N.2). Nothing on disk is touched on this path at all.
            self._settings_touched(set_id=set_id)
            return
        ctx = self._run_ctx
        if ctx is None:
            # Not in a run: a session-only choice, nothing stored (CH-14).
            from workflow.compliance_sets import SET_BY_ID, effective_limits
            from workflow.run_compliance import RunLimits
            self._limits = RunLimits(set_id, tr(SET_BY_ID[set_id].label),
                                     effective_limits(set_id, self._overrides()),
                                     label_en=SET_BY_ID[set_id].label, bound=False)
            # THE ONE DOOR, which will repaint rather than defer here: a
            # measurement in no run has no Generate button to press.
            # `_forget_limits` deliberately KEEPS an unbound session choice, so
            # the RunLimits just built survives it.
            self._settings_touched(set_id=set_id)
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
        # THE STORES AS THEY WERE WHEN THIS WINDOW LAST DREW ITSELF, which is
        # where the user's reading of them comes from. See `_sync_limit_
        # controls`, which stamps it beside the run's own state.
        _prefs_at_question = getattr(self, "_prefs_at_sync", None)
        if _prefs_at_question is None:
            _prefs_at_question = self._prefs_state_now()
        # **THIS DOOR NO LONGER REWRITES ONE SAVED REPORT, SO IT NO LONGER ASKS
        # ABOUT REWRITING THEM (B8-384).**
        #
        # Knut, 2026-09-18, on beta 21: *"When I change Judged Against to
        # another setting, all listed reports in the Saved reports pulldown
        # change to the new judged against setting, AND created a new (third)
        # report. This is not the behaviour I specified."* Asked directly
        # whether his rule supersedes D23, he answered *"Agreed. D23 stands."*
        #
        # D23 is a rule about HOW a recalculation is done, never about whether
        # one happens: §5 of `docs/design/measurement_report_limits.md` states
        # it as *"first copies each dated report … then rewrites the file in
        # place (Knut D23; nothing is deleted)"*. His beta-20 ruling, and N.2
        # of the same section, decide the other question: *"If a report has
        # been generated, those reports shall not be recalculated if I want to
        # create a new report with a different Judged Against threshold set."*
        # Leaving the file alone satisfies both, and satisfies D23's promise
        # more completely than archiving would: nothing is rewritten, so
        # nothing has to be kept first.
        #
        # **AND FOR A REPORT THAT RECORDS NO SET OF ITS OWN IT IS THE ONLY SAFE
        # READING.** A rewrite is the one thing that can stamp a set onto such
        # a file, which is exactly what relabelled the two reports Knut
        # photographed: their names carried "ChromIQ tight" over a press nobody
        # made. `_saved_report_label` reads the set off the FILE, so a file
        # left alone keeps the name it had.
        #
        # THE OTHER TWO DOORS ARE UNCHANGED and still recalculate,
        # archive-first: "Unlock this run's limits" and the Report limits
        # window's Save. They are B8-310, where N.3 is still an open question
        # for Knut, and neither is what he ruled on here.
        if self._run_state_now(ctx.run) != self._run_state_at_sync:
            # THE RUN MOVED SINCE THIS WINDOW LAST DREW IT: a verification
            # measurement finished, a dated verification was deleted, or
            # another window rebound or re-locked it. Nothing is written on
            # that reading, exactly as before; what has gone is the question in
            # front of it, because there is no history to lose any more.
            #
            # `is_locked` turns on at the SECOND dated verification, so a
            # measurement finishing while this window sat open locks the run,
            # and this is the guard that catches it.
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
        # **AND NOT ONE SAVED REPORT IS TOUCHED (B8-384).** `self.
        # _recalculate_run()` stood here and rewrote every dated report of the
        # run with the new set, archiving each first. The long note at the head
        # of this method says why it is gone and what it means for the two
        # doors that still call it.
        #
        # The RUN is still bound to the chosen set, because that is what the
        # set pulldown is: the yardstick for measurements that carry no verdict
        # of their own, and for the dated verifications still to come. What the
        # user sees next is `_settings_touched`'s red line: the settings have
        # changed, press Generate report (N.2).
        self._settings_touched(set_id=set_id)

    def _saved_report_count(self, run) -> int:
        """How many saved report FILES a recalculation would rewrite.

        ASKED BY THE LIMITS WINDOW'S SAVE, and no longer by the "Judged
        against" pulldown, which stopped recalculating anything (B8-384).

        THIS COUNTED DATES AND THE SENTENCE SAID REPORTS, which is a lie the
        moment a date holds more than one. `save_report` is timestamped on
        purpose so that a printer's reports accrue for comparison, so several
        per date is designed behaviour: eleven dates saved three times each is
        thirty-three files, and the question said eleven while rewriting all
        thirty-three. A confirmation exists to tell the user the size of what
        they are about to lose, so it counts the thing that is lost.
        """
        from workflow.measurement_report import recorded_document
        n = 0
        try:
            for v in run.verifications():
                try:
                    for path in v.reports_dir.glob("report_*.json"):
                        # A GENERATED DOCUMENT IS NOT REWRITTEN AND IS NOT
                        # COUNTED. A confirmation exists to tell the user the
                        # size of what they are about to lose, and counting a
                        # file the recalculation now skips would name a loss
                        # that does not happen. See `_recalculate_run`.
                        try:
                            rep = json.loads(read_text(path))
                        except Exception:             # noqa: BLE001
                            continue    # unreadable: not rewritten either
                        if recorded_document(rep) is None:
                            n += 1
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

        **ONE DOOR SHOWS THIS NOW**: saving a change of the run's own numbers
        in the Report limits window. The "Judged against" pulldown does not
        recalculate any more (B8-384), so it does not ask; a question about a
        loss that cannot happen is worse than no question at all.
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
        # **THE CLAUSE THAT WAS FALSE IS GONE, AND NO NEW WORDS ARE IN ITS
        # PLACE (B8-391).** Knut, 2026-09-18, reading this very window:
        # *"The description is wrong. All dated reports shall NOT be
        # recalculated, only the selected report will be recalculated and
        # report text recreated according to new values."*
        #
        # The behaviour went first (see the foot of this method): unlocking
        # recalculates nothing at all now, so the promise about "every dated
        # report of this run" describes something that cannot happen. Every
        # word left here was already on screen and is still true.
        #
        # THE REPLACEMENT SENTENCE IS NOT WRITTEN HERE. It says what the door
        # does now, which is new user-facing text, so it is in §M-PROPOSED of
        # `unified_measurement_management.md` (M-UNLOCK-LIMITS) and waits for
        # approval. This is the same course B8-384 took at the "Judged against"
        # door an hour earlier: a false promise is removed the moment it
        # becomes false, and nothing is invented to replace it.
        _tail = tr(
            "Unlocking lets you change the run's limit set and its "
            "numbers.\n\nNothing is deleted. Continue?")
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
        # **AND NOT ONE SAVED REPORT IS RECALCULATED (B8-391).**
        # `self._recalculate_run()` stood here and rewrote EVERY dated report
        # of the run, archiving each first. Knut, 2026-09-18: *"All dated
        # reports shall NOT be recalculated, only the selected report will be
        # recalculated and report text recreated according to new values."*
        #
        # **AND AT THIS MOMENT THERE IS NOTHING TO RECALCULATE.** Unlocking
        # changes no number: it only lets the user change one. What his rule
        # asks for is what the window already does for the other doors since
        # B8-384 and what N.2/N.3 of §5 state: the change belongs to the ONE
        # report named in "Report shown", it marks that report stale, the red
        # line says so, and pressing Generate report rebuilds it. Re-stamping
        # files here with numbers nobody has changed yet would be a rewrite
        # that says nothing, and for a generated document it would break the
        # rule B8-384 was built on: a document records the settings it was
        # made with and is never recalculated under the reader.
        #
        # **THE WARNING IS NOT LOST WITH IT.** The Report limits window's Save
        # is the door that still recalculates, and it asks its own question
        # (`_confirm_recalculate`) at the moment the rewrite would happen,
        # which is the right moment for it. That door is B8-310, where N.3
        # (*"Unlocking a run's limits and saving a change in the Edit limits
        # window must result in the same behaviour"*) reaches it too; it is
        # reported rather than changed here, because this round was asked for
        # the unlock door and re-aiming another round's guards without a review
        # is how this window has been broken before.
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
                ctx, snap, report_failure=True, keep_columns=True)
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

    def _why_the_unlock_box_is_greyed(self, run, several: bool, locked: bool,
                                      lim) -> str:
        """The sentence a dim "Unlock this run's limits" owes the reader.

        Knut put the box back on screen in every state (B8-520), so the state
        it cannot act in is now a GREY control rather than an absent one, and a
        grey control with no explanation is the fault that made hiding it look
        reasonable in the first place. One sentence per reason, and an empty
        string when the box is live, so the caller falls back to the sentence
        the pulldown and the button share.
        """
        if self._unlock_check.isEnabled():
            return ""
        if several:
            return tr("Several measurement runs are loaded. Open the report "
                      "on one run to unlock that run's limits.")
        if run is None:
            return tr("This measurement does not belong to a profile run, so "
                      "there are no stored limits to unlock.")
        if not locked and not bool(getattr(lim, "unlocked", False)):
            return tr("This run's limits are not locked yet. A run is locked "
                      "by its second dated verification, and this box lifts "
                      "that lock.")
        return tr("Preferences, Reports does not allow editing limits after "
                  "the first measurement, so this run's limits cannot be "
                  "unlocked here.")

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

    def _undo_the_edit(self, ctx, snap, report_failure: bool = False,
                       keep_columns: bool = False) -> str:
        """Take the run's own column back to what it held, and touch nothing
        else. Returns whether the previous numbers were really recovered.

        *keep_columns* leaves `compliance_columns` exactly as it is on disk.
        WHICH COLUMNS ARE SHOWN IS NOT PART OF WHAT A REFUSAL REFUSES. A user
        who says no to "Changing the limit set recalculates…" is answering
        about the numbers; the ticks they set in the same visit were never in
        the question and were never a claim on a verdict. Knut reported the
        consequence as a separate fault (*"it is not remembered what I turned
        off some columns"*), and driven on screen it was this line: Cancel put
        an empty `compliance_columns` back and every column came up ticked
        again. The LOCK path is the one caller that still passes False, because
        there the question is whether this window may write to the run at all,
        and the answer covers every key it writes.

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
                        and (keep_columns
                             or list(getattr(m, "compliance_columns", []) or [])
                             == list(snap["run"][5] or []))):
                    return "restored"      # nothing to write, and nothing lost
                if not keep_columns:
                    m.compliance_columns = snap["run"][5]
                m.compliance_thresholds = snap["run"][2]
                ctx.run.save_meta(m)
                return "restored"
            if not keep_columns:
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
        """Open the limits window, then apply the set it was asked for.

        **THE PICK IS APPLIED AFTER, AND OUTSIDE, THE BODY.** Applying it in
        line asked the recalculate question TWICE and archived the run's saved
        reports twice: the body takes a snapshot of the run AFTER the point the
        pick was being applied, so its own "did what this run is judged by
        change?" test saw the movement this window had just made, and reported
        it as somebody else's. On the refusal path it also reverted the
        preferences the user had just set, silently, and raised a box accusing
        another window of a change nothing else had made. Found by an
        adversary round driving one pick with a default-for-new-runs pick
        beside it.

        The body has a dozen early returns, so `finally` is what makes "exactly
        once, at the end" true on all of them.
        """
        self._pending_run_set_pick = ""
        try:
            self._open_limits_window()
        finally:
            pick = str(getattr(self, "_pending_run_set_pick", "") or "")
            self._pending_run_set_pick = ""
            if pick:
                _i = self._set_combo.findData(pick)
                if _i >= 0 and self._set_combo.currentIndex() != _i:
                    # Fires `_on_set_chosen`, which is the one writer: it
                    # re-checks the lock, catches a preferences change
                    # underneath, and asks about recalculating.
                    self._set_combo.setCurrentIndex(_i)

    def _open_limits_window(self) -> None:
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
        # DID THEY PICK A SET FOR THIS RUN IN THERE? The limits window's "Used
        # for this run" row records a choice and writes nothing (Knut,
        # 2026-09-13: the only radios on that window were "Default for new
        # runs", so clicking one moved the app default and left the run alone,
        # which read as a dead control). It is applied HERE, through the
        # pulldown, so it takes the one guarded path: the lock is re-checked,
        # a preferences change underneath is caught, and the user is asked
        # about recalculating the run's saved reports. Driving the combo rather
        # than calling `_on_set_chosen` directly also keeps the control on
        # screen in step with what was chosen.
        self._pending_run_set_pick = str(getattr(dlg, "run_set_chosen", "") or "")
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
        # …AND IT IS NOT A CHANGE TO WHAT THE RUN IS JUDGED BY. Knut,
        # 2026-09-11: hiding two table columns and clicking Close raised "This
        # run (run1) has one saved report. Changing the limit set recalculates
        # it with the new numbers…", and *"this should only come when
        # thresholds are changed, not if table columns are hidden or shown"*.
        # Driven on screen on a run with one dated verification and one saved
        # report: unticking the two ISO columns raised that question, and
        # answering Cancel, which is the natural answer to a question about a
        # limit set nobody touched, ran the undo and put `compliance_columns`
        # back to empty. That is his other report, *"it is not remembered what
        # I turned off some columns"*, and it is the same fault twice: one
        # term, folded into `moved`, carried a VIEW setting into the branch
        # that asks about, and rewrites, a history.
        #
        # So the two are separated by what they can do. `_judged_moved` is the
        # question, the bind and the recalculation, because only numbers and
        # preferences can move a verdict. The column choice joins it only for
        # the lock, which is a question about whether this window may write to
        # the run at all, and that is true of every key it writes.
        _judged_moved = ctx is not None and (_run_numbers_moved or _prefs_moved)
        moved = _judged_moved or (ctx is not None and _run_columns_moved)

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
        if _judged_moved:
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

        **TWO DOORS REACH THIS, NOT THREE (B8-384).** "Unlock this run's
        limits" and the Report limits window's Save still do. The "Judged
        against" pulldown does NOT any more: Knut ruled that changing it may
        not rewrite a saved report, and `_on_set_chosen` says at length what
        that leaves. The two that remain are B8-310, where whether his N.3
        (*"Unlocking a run's limits and saving a change in the Edit limits
        window must result in the same behaviour"*) applies to them is still an
        open question for him and has not been assumed here.
        """
        ctx = self._run_ctx
        if ctx is None:
            return
        from datetime import datetime as _dt
        from PyQt6.QtGui import QCursor
        from workflow.measurement_report import (list_reports,
                                                 recorded_document,
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
        # THE DATED FOLDERS OF **THIS** RUN, asked of the run rather than
        # matched out of a string. See the loop at the foot of this method.
        mine = {str(v.dir) for v in ctx.run.verifications()}
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
                    # **A REPORT THAT IS A DOCUMENT IS NOT RECALCULATED.**
                    # Knut, 2026-09-18, asked whether D23's archive-then-
                    # recalculate rule still holds: *"Agreed. D23 stands."*,
                    # and, on what Generate does: *"It is better that existing
                    # reports are not overwritten. A user could instead select
                    # and delete old reports they do not want."*
                    #
                    # A document records the settings it was made with (B8-383)
                    # and is offered in the list under a name built from them.
                    # Rewriting its verdict against another set would make its
                    # own record false and its own name a lie, which is the
                    # photograph in B8-384: an entry reading "ChromIQ tight"
                    # over a page still reading "ChromIQ default".
                    #
                    # **THIS IS NOT THE WHOLE OF B8-384.** A report saved by an
                    # earlier ChromIQ carries no document block and is still
                    # rewritten here, exactly as it is today, because stopping
                    # that reaches the confirmation that precedes it and the
                    # sentence it puts on screen. That is registered and left.
                    if recorded_document(rep) is not None:
                        log.info("left alone (it is a generated document): %s",
                                 path)
                        continue
                    stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                                  set_label=lim.label_en, edited=lim.edited)
                    # …AND THE TYPE, BUT ONLY ONTO A REPORT THAT HAS NONE.
                    #
                    # An adversarial round added this so a recalculated report
                    # could not claim a type the run no longer held, and that
                    # was right while a run had exactly one. Knut ruled on
                    # 2026-09-11 that a run may hold reports of SEVERAL types:
                    # *"the user may have several uses for different reports."*
                    # Stamping every one with the run's current type then
                    # destroys the distinction he asked for. Measured: one
                    # change of limit set, the type pulldown untouched, turned
                    # a Colour summary, a Full colour check and a Printing
                    # record into three Colour summaries, and the line naming
                    # what the run has read "Colour summary (4)".
                    #
                    # A report generated AS a document keeps being that
                    # document. One saved before the types existed has no
                    # answer of its own, so it follows the run, which is what
                    # it renders as anyway.
                    if not (rep or {}).get("report_type"):
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
            # A PREFIX OF A PATH IS NOT A PARENT OF IT, AND THE NEXT RUN ALONG
            # PAID FOR THAT. This asked `origin.startswith(str(ctx.run.dir))`,
            # and `…/runs/run10` starts with `…/runs/run1`, so a project with
            # ten runs had run10's column re-judged by run1's choice. Driven on
            # screen, a project with run1 (ChromIQ default), run2 (ChromIQ
            # tight) and run10 (Quick check), all six columns shown: choosing
            # "ChromIQ tight" for run1 left run2's column alone, as it must,
            # and turned run10's from "Quick check" to "ChromIQ tight" in the
            # rendered document, while run10's file on disk still said
            # `chromiq_quick`. Nothing was written; the window simply told the
            # user a column had been judged by a set it is not bound to.
            #
            # …AND IT REACHED WIDER THAN THE WRITE ABOVE IN A SECOND WAY. The
            # disk pass walks `ctx.run.verifications()`, which is what §5 of
            # `docs/design/measurement_report_limits.md` specifies ("each dated
            # report"); this loop reached the run's own `reports/` as well, so
            # on the same drive run1's run-level report read "ChromIQ tight" on
            # screen and `chromiq_default` on disk, with no question asked,
            # because `_saved_report_count` counts dated folders and had
            # counted none. A baseline refreshed wider than the write that
            # earned it is the shape this window keeps producing; the cure is
            # to refresh exactly the folders the write above covered.
            _held = set(no_archive) | set(no_write) | set(part_written)
            for r in self._history:
                origin = str(r.get("_origin_dir", ""))
                if origin in mine and Path(origin).name not in _held:
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
        desc = self._run_description()
        out = (_h2(tr("Report Scope")) + _gap()
               + (f"<div style='color:{_C['faint']};margin:0'>"
                  + html.escape(tr("Run description")) + "</div>"
                  + f"<div style='font-weight:bold;margin:0 0 4px'>"
                  + html.escape(desc) + "</div>" + _gap() if desc else "")
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
        _counts = [self._measurements_recorded_in(_p) for _p in _mine.values()]
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
            note = (tr("This report covers {n} of the {total} measurements "
                       "recorded for this project.")
                    if len(_mine) == 1 else
                    tr("This report covers {n} of the {total} measurements "
                       "recorded for the projects it is drawn from.")
                    ).format(n=covered, total=total_known)
            out += (f"<div style='color:{_C['dim']};margin-top:6px'>"
                    + html.escape(note) + "</div>")
        return out + self._scope_warnings_html(sc["warnings"])

    @staticmethod
    def _measurements_recorded_in(project_dir: str) -> int:
        """How many measurements a project's folder holds, read from the disk.

        Every run's own measurement plus every dated verification of every run.
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
                n += len([f for f in d.glob("*.ti3") if f.name not in roles])
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
                        "These runs are missing one or more of the eight cube "
                        "corners, so their cube-corner figures are less meaningful:"))
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

    def _how_to_read_html(self, present: "list[str] | None" = None) -> str:
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
        groups = self._explained_row_groups()

        def _for(group: "str | None", text: str) -> str:
            # A bullet about data the document always carries (paper white, the
            # cube corners) has no row group and is never dropped.
            if group is not None and groups is not None and group not in groups:
                return ""
            return "<li>" + html.escape(text) + "</li>"

        def _metrics() -> str:
            """One bullet per metric row the results table lists."""
            out = []
            for rid in (present or []):
                row = ROW_BY_ID.get(rid)
                if row is None or not row.blurb:
                    continue
                out.append("<li>" + html.escape(
                    tr("{metric}: {explanation}").format(
                        metric=tr(row.label), explanation=tr(row.blurb)))
                    + "</li>")
            return "".join(out)

        body = (
            "<p>" + html.escape(tr(
                "This report compares what your instrument measured against the "
                "chart's design colours (the reference values the chart was built "
                "from). Every number is a colour difference (ΔE00): 0 is a perfect "
                "match, 1–2 is barely visible, and 10 or more is clearly "
                "different.")) + "</p>"
            "<ul>"
            + _for("all_patches", tr(
                "Colour accuracy: the ΔE00 across the patches, split so you can "
                "see the bulk of the chart (all patches and the best 95 %) apart "
                "from the few hardest patches (the worst 5 %). Each row is judged "
                "against the run's limit set."))
            + _for("grey_ramp", tr(
                "Grey balance: how far each grey patch (R = G = B) sits from a "
                "neutral grey, ignoring lightness. ΔCh is the distance in a* and "
                "b* only. Computed from the chart's grey ramp when it has at "
                "least 8 steps from white to black."))
            + _for(None, tr(
                "Paper white & darkest black — the brightest and deepest patches "
                "(L*), a quick health check of your paper and maximum ink."))
            + _for(None, tr(
                "Cube corners — paper white, composite black and the six primary "
                "and secondary inks. These say as much about your inks as about "
                "the instrument."))
            + "</ul>"
            # **AND THEN EVERY METRIC THE RESULTS TABLE JUDGES, BY NAME
            # (B8-463).** The four bullets above are about the report's
            # sections; Knut's beta-25 note is about its METRICS: *"Whatever
            # metrics are shown in Report Results: each metric used in the
            # report shall have a corresponding explanation of each metric in
            # the 'How to read this report' section … The bullet list of
            # parameters explained is then changing with which metrics the
            # report contains."* Measured before this, on his own demo project
            # and every type crossed with every limit set: 13 metrics judged,
            # 0 of them named here, in all 20 combinations.
            #
            # The words are the rows' own one-line descriptions, the same ones
            # the Report limits window shows against each row, so a metric is
            # described in one place and reads the same wherever it appears.
            + (("<p>" + html.escape(tr(
                "Every metric this report judges, and what it means:"))
                + "</p><ul>" + _metrics() + "</ul>") if _metrics() else "")
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
            "<li>" + html.escape(tr(
                "COND (short for conditional): nothing failed, but the result "
                "comes with a documented exception. For a row it means the row "
                "is a recommendation rather than a requirement and the value "
                "is over it. For a column's Overall it means a recommendation "
                "was exceeded, or the set contains rows this chart could not "
                "supply, so the set as a whole was only partly "
                "checked.")) + "</li>"
            "<li>" + html.escape(tr(
                "INFO: the number is shown for your information and nothing "
                "was judged from it. That happens when this limit set puts no "
                "limit on the row, when the sheet is a profiling measurement, "
                "which is never graded, when the row needs something about the "
                "print that was not recorded, and when you chose a report type "
                "that judges nothing. The note under the results names the "
                "rows in the last two cases.")) + "</li>"
            "<li>" + html.escape(tr(
                "N-A (not applicable): the row does not apply here. The reason "
                "is listed under the results, for example that the chart has "
                "too few grey steps.")) + "</li>"
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
            "<p>" + html.escape(tr(
                "A column read as a drift check shows the word “drift” in "
                "every cell instead: it compares one measurement with another "
                "rather than with a limit. A column's Overall word is PASS "
                "only when every row the set requires was checked and "
                "passed.")) + "</p>"
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
            "<p>" + html.escape(tr(
                "Two kinds of column carry a standard's name. A read-only "
                "column named after a standard holds that standard's "
                "published tolerance values and nothing else, and ChromIQ "
                "ships none of them, because it has no permission to include "
                "them: such a column is empty unless a licence holder has "
                "supplied its figures. An editable column named after a "
                "standard starts from those supplied figures where there are "
                "any and from ChromIQ's own numbers where there are none, and "
                "every limit in it is yours to change. Either way the values "
                "are applied to the chart you printed rather than to that "
                "standard's own chart and control strip, so their Overall "
                "reads COND at best.")) + "</p>"
            # BOUND AND LOCKED, in the report that uses both words. Knut,
            # 2026-09-11: *"what is the difference between bound and locked? Be
            # specific in the explanation, so that user understands that chosen
            # limits are bound to chosen 'ChromIQ default' thresholds as this
            # was used for the first dated verification run of the included
            # measurement sets."* The two facts are §5 of
            # docs/design/measurement_report_limits.md, in his terms: bound is
            # the run holding its own copy of the numbers, taken at its first
            # dated verification; locked is that copy no longer being
            # changeable, which starts at the second one.
            "<p><b>" + html.escape(tr("Bound, and locked.")) + "</b> "
            + html.escape(tr(
                "When the first dated verification of a profile run was "
                "measured, ChromIQ copied the limit set chosen at that moment "
                "onto the run. The run is bound to that copy: every later date "
                "of the same run is judged against the same numbers, so the "
                "dates can be compared, and changing the set in Preferences "
                "afterwards does not reach a run that is already bound. The "
                "copy is locked once a second dated verification has been "
                "measured, so the numbers behind a history cannot move under "
                "it. Until then the set may still be chosen in the report "
                "window, and choosing one recalculates the dates already "
                "saved, keeping a copy of each first.")) + "</p>"
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
                "that chain has moved; by itself it does not say which part. "
                "Judging the profile on its own is a separate check, made "
                "against the measurement the profile was built from.")) + "</p>"
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
                tip = self._reason_sentence(x.get("reason"), r)
            elif word == COND:
                tip = tr("CONDITIONAL: over a value this limit set recommends "
                         "but does not require. Nothing failed; the exceedance "
                         "is documented.")
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
                    # ONE REMEDY FOR EVERY REASON WAS TRUE UNTIL B8-397, AND IS
                    # NOT ANY MORE. The three control-strip rows are missing a
                    # DECLARATION, not patches, and this sentence told a reader
                    # to go and add patches that are already on the sheet, one
                    # line under a reason that had just said "declare a longer
                    # strip". Photographed on screen, 2026-09-18. Each reason
                    # now carries its own lever, so the closing sentence points
                    # at them instead of naming one of them for all.
                    "A row that was not computed says nothing about the "
                    "printer; each reason above names what that row needs, so "
                    "make that change, print the chart again and measure "
                    "it.")) + "</div>")
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
        # …AND THE NOTES ON VERDICTS THAT WERE GIVEN, which is a different list
        # again and is the second half of Knut's ruling of 2026-09-13. The two
        # above are about rows with NO verdict. These comment a verdict that
        # stands: the number is judged, and the note says what to know when
        # weighing it. Numbered, because the verdict cell points at the number.
        numbered = self._numbered_notes(runs)
        if numbered:
            from workflow.measurement_report import note_label
            items = "".join(
                "<li style='margin-bottom:2px'><b>"
                + html.escape(note_label(n)) + "</b> "
                + html.escape(f"{where}: ") + html.escape(sentence) + "</li>"
                for (n, where, sentence) in numbered)
            notes += (f"<div style='{note_css}'><b>" + html.escape(tr(
                "Notes on the verdicts above:")) + "</b>"
                + f"<ol style='margin:2px 0 0 16px;padding:0;"
                f"list-style:none'>{items}</ol></div>")
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
        # WHICHEVER SHAPE THE FILE IS IN (R24-F2). These two read `lab` only,
        # so a schema-5 measurement -- ChromIQ's own demo projects hold them --
        # printed a dash here while the detailed section below printed the very
        # same paper white as *L\* 95.4*. `point_lightness` is the one reader.
        from workflow.measurement_report import point_lightness
        row_getters += [
            (tr("Paper white L*"),
             num(lambda r: point_lightness(r.get("paper_white")), 1)),
            (tr("Black L*"),
             num(lambda r: point_lightness(r.get("max_black")), 1)),
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
        project = self._report_profile_name(runs)
        if not project:
            return ""
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
            for key in ("ti3", "path", "source"):
                v = r.get(key)
                if not v:
                    continue
                m = _re.search(r"runs/run(\d+)\b", str(v).replace("\\", "/"))
                if m:
                    return m.group(1)
        return ""

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
        # **THE DOCUMENT'S OWN CREATION TIME, NOT THIS WINDOW'S (B8-461).**
        # `self._created` is the second the window opened, so a report saved in
        # November and loaded today announced itself as made today, under an
        # entry whose name said November. Knut: *"They should be the same."*
        # `_doc_created` is empty whenever no saved document is on the page
        # ("New report…", an unsaved measurement), and then the window's own
        # clock is the right answer and is what is used.
        when = html.escape((created or getattr(self, "_doc_created", "")
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
        parts = [head, self._scope_html(runs, _other_sets),
                 self._how_to_read_html(_present),
                 self._report_results_html(runs, _present)]
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
                       + self._swatch_table_html(
                           picked,
                           columns=-(-len(picked)
                                     // self._SWATCH_ROWS_PER_COLUMN) or 1))
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
            from workflow.measurement_report import point_lightness

            def _line(pt: dict, label: str) -> str:
                bits = []
                if pt.get("hex"):
                    bits.append(_swatch(str(pt["hex"])))
                bits.append(html.escape(label))
                if pt.get("loc"):
                    bits.append(f"({html.escape(str(pt['loc']))})")
                lv = point_lightness(pt)
                if lv is not None:
                    bits.append(f"- L* {lv:.1f}")
                return "<div>" + " ".join(bits) + "</div>"

            parts.append(_h3(tr("Paper white & darkest black")))
            parts.append(_line(w, tr("White")) + _line(b, tr("Black")))

        corners = r.get("corners") or []
        if corners:
            parts.append(_h3(tr("Cube corners (the eight ink extremes)")))
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
            parts.append(_h3(tr("Worst patches")))

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
