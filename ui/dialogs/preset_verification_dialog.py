"""“Which presets can be used for verification” — the window under the Create
Chart presets dropdown (#182, Knut, beta 22).

Knut asked for *"a window listing all the presets that fulfil the requirements
for verification on a specified report type and judge against selection"*, with
*"those charts suitable for verification"* highlighted, and for a preset that
does not qualify to say what it is missing.

**IT SAYS "METRICS", NOT "ROWS".** Knut, beta 25: *"The text refers to 'rows',
or 'Rows answered', which is not intuitively understood as 'verification
metrics' … Try to reword all the text, and the help text, so that you avoid
'rows' and 'rows of a report'."* A row is what the Measurement Report's own
table calls its lines; a reader of THIS window is choosing a chart, and what a
chart supplies is a metric. The row ids underneath are untouched.

**IT MARKS, IT DOES NOT FILTER, and that decision was measured rather than
guessed.** On the 177 built-in presets ChromIQ ships (2026-09-19):

=========================================  ============  =======================
report type / limit set                    metrics asked  answering every one
=========================================  ============  =======================
any / ChromIQ default, tight, quick                    7  **177 of 177**
Grey and tone check / Custom ISO                       3  **177 of 177**
Colour summary or Full check / Custom ISO             16  **0 of 177** (13 each)
Printing record (not graded) / any                     0  every one, nothing judged
=========================================  ============  =======================

A filter is therefore either a no-op or an empty window; it is never the thing
that helps. The list always holds every preset and marks each one, and a single
opt-in tick box narrows 177 rows to the ones the star is on.

**THE ONE THING THAT TICK BOX DOES HIDE** is a preset that ships finished page
TIFFs, which is the eleven "by Pharmacist" bundles. Knut, beta 25: their sheet
is an image and cannot be laid out again, so it can never be built FROM PROFILE
GAMUT, which is the only way a chart acquires the colorimetric reference three
metrics are judged against. They stay on the unfiltered list, with the detail
pane saying so and naming those three, because hiding them outright would
answer none of the questions this window exists to answer.

The zero is not a bug in the presets. Both Custom ISO columns put a limit on
the three reference rows, and **no preset chart can supply them**: a
colorimetric reference is written only beside a chart built FROM PROFILE GAMUT.
Every one of the other thirteen rows IS answered, the three control-strip rows
included, because `workflow.control_strip` builds a declaration out of a
chart's own patches when the chart is filed and all 177 fill the ladder past
its twenty-rung mark. The detail pane says which three are out of reach, in the
metric help icons' own words, which is why this window teaches instead of only
filtering.

Every judgement in here comes from :mod:`workflow.preset_eligibility`, which in
turn is :mod:`workflow.measurement_report`'s own eligibility code over a chart
that has not been printed yet. No sentence about what a chart can answer is
written twice.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.i18n import count_phrase, tr
from ui.fade_scroll import FadeScrollArea
from ui.theme import active_mode
from ui.widgets import NoScrollComboBox, WorkAreaClamped
from workflow import compliance_sets as CS
from workflow import measurement_report as MR
from workflow import preset_eligibility as PE

log = logging.getLogger(__name__)

#: Room beside a column heading's text: the section's own margins and the
#: sort indicator a header may draw.
_HEADER_PAD = 28


# ---------------------------------------------------------------------------
# One row of the list
# ---------------------------------------------------------------------------
@dataclass
class PresetRow:
    """A preset as this window sees it: a name, a chart, and what it can do."""
    group: str
    label: str
    chart: "Path | None"
    patches: int
    pages: int
    builtin: bool
    #: the Create Chart pulldown's own userData for this preset: a built-in's
    #: KEY or a user preset's NAME. Knut, beta 25, asked a double-click here to
    #: be *"equivalent to selecting and loading a preset from the 'Select
    #: preset' pulldown list"*, and the pulldown is addressed by this.
    key: "str | None" = None
    #: False when the preset ships finished page TIFFs, so its sheet cannot be
    #: laid out again. See `PE.made_for_verification` and `_no_gamut_note`.
    relayoutable: bool = True
    starred: bool = False
    assessment: PE.Assessment = PE.UNCHECKED
    #: **THE ONE ROW THAT IS NOT A PRESET** (#182, Knut, 2026-09-21): *"the
    #: first line should be a separate line not part of the presets list, but
    #: representing the current layout defined in Create Chart."* It sits above
    #: every group, under a separator that cannot be clicked, and a
    #: double-click on it does nothing because there is no preset to apply.
    is_current_chart: bool = False
    #: True when that chart was built with FROM PROFILE GAMUT, which is the
    #: one thing a preset can never be. Read off the chart by
    #: `workflow.verification_print.chart_conversion_state`, never passed in as
    #: a claim: see `TabChart.current_chart_row`.
    from_profile_gamut: bool = False
    #: The layout engine recipe of a built-in preset, when it has one. The
    #: evenness rows need the chart's PAGE GRID, which a `.ti1` does not carry;
    #: for an engine preset `PE._predicted_grid` computes it from this, with
    #: the engine's own arithmetic and no file written.
    recipe: "dict | None" = None


# ---------------------------------------------------------------------------
# What is missing, in one line, before the metric's own remedy
# ---------------------------------------------------------------------------
#: One short sentence per reason code, saying WHAT is short. The lever that
#: follows it is the metric help icon's own `remedy` text, reused verbatim so
#: the two windows cannot drift: see `preset_eligibility.row_remedy`.
#:
#: Every code `workflow.preset_eligibility.classified_reasons` knows has an
#: entry, and `tests/test_the_preset_window_says_what_is_missing.py` fails when
#: one does not, because a row that says only "✕" teaches nobody anything.
def reason_line(code: str) -> str:
    """What this chart is short of, in one sentence."""
    return {
        MR.REASON_NEEDS_REFERENCE_FILE:
            tr("This chart carries no colorimetric reference."),
        MR.REASON_NO_REFERENCE:
            tr("This chart carries no aim values for its patches."),
        MR.REASON_NO_CONTROL_STRIP:
            tr("This chart declares no control strip."),
        MR.REASON_CONTROL_STRIP_TOO_SMALL:
            tr("The control strip this chart declares is too short."),
        MR.REASON_NO_GREYS:
            tr("This chart has no grey patches."),
        MR.REASON_TOO_FEW_STEPS:
            tr("The grey ramp on this chart has too few steps."),
        MR.REASON_NO_WHITE:
            tr("The grey ramp on this chart does not reach white."),
        MR.REASON_NO_BLACK:
            tr("The grey ramp on this chart does not reach black."),
        MR.REASON_NO_RAMP:
            tr("This chart has no tone ramp through the mid-tones."),
        MR.REASON_SMALL_SAMPLE:
            tr("This chart has too few patches for a worst twentieth of them "
               "to exist."),
        MR.REASON_TOO_FEW_SURFACE_PATCHES:
            tr("Too few of this chart's patches sit on the surface of the "
               "device cube."),
        MR.REASON_TOO_FEW_OUTER_PATCHES:
            tr("The most saturated quarter of this chart holds too few "
               "patches."),
        MR.REASON_NO_CORNERS:
            tr("This chart has no patch at any of the solid ink corners."),
        MR.REASON_NOT_COMPUTED:
            tr("ChromIQ cannot check this metric on this chart."),
        # EVENNESS ACROSS THE SHEET (Knut, 2026-09-22). The page grid is
        # exact for a laid-out chart and for an engine preset; the noise is an
        # estimate for a typical print, and the line says so.
        MR.REASON_EVENNESS_NO_LAYOUT:
            tr("This chart has no layout file saying where each patch is "
               "printed."),
        MR.REASON_EVENNESS_NO_POSITIONS:
            tr("This chart's layout does not say which strip and row each "
               "patch is printed in."),
        MR.REASON_EVENNESS_GRID_TOO_SMALL:
            tr("No page of this chart has at least {k} strips and {k} "
               "rows.").format(k=MR.EVENNESS_MIN_GRID),
        MR.REASON_EVENNESS_EMPTY_AREA:
            tr("One of the nine areas of the page holds no patch."),
        MR.REASON_EVENNESS_NOISY_PAIRWISE:
            tr("Too few patches in each ninth of the page: on a typical print "
               "the chart's own noise would not be below this limit. The "
               "report measures the real noise on the printed sheet."),
        MR.REASON_EVENNESS_NOISY_FROM_MEAN:
            tr("Too few patches in each ninth of the page: on a typical print "
               "the chart's own noise would not be below this limit. The "
               "report measures the real noise on the printed sheet."),
        # #182 E2 (Knut, 2026-09-23): the patch block's share of the page,
        # from the same margins "Measured from Preview" shows.
        MR.REASON_EVENNESS_PAGE_COVERAGE:
            tr("On no page of this chart with at least {k} strips and {k} "
               "rows do the patches cover at least {c} % of the page.").format(
                   k=MR.EVENNESS_MIN_GRID,
                   c=f"{MR.EVENNESS_MIN_PAGE_COVERAGE * 100:g}"),
        MR.REASON_EVENNESS_NO_PAGE_GEOMETRY:
            tr("This chart's files do not record where its patches sit on the "
               "page, so how much of the page they cover is not known."),
        PE.REASON_EVENNESS_LAID_OUT_LATER:
            tr("This preset's page layout is decided when the chart is "
               "built, so whether each page has at least {k} strips and {k} "
               "rows is not known yet.").format(k=MR.EVENNESS_MIN_GRID),
    }.get(code, tr("ChromIQ cannot check this metric on this chart."))


#: **A SHEET THAT IS ALREADY AN IMAGE CANNOT BE BUILT FROM PROFILE GAMUT.**
#: Knut, beta 25, on the eleven "by Pharmacist" bundles: *"I prefer that these
#: are noted as 'not usable for verification using From Profile Gamut' and then
#: also mention which metrics cannot be fulfilled."*
#:
#: The metrics are not typed here: they come from
#: :func:`workflow.preset_eligibility.gamut_only_rows`, which reads them off
#: the row table, and each is named by the label the Measurement Report uses
#: for it, so the two windows cannot come to say different things.
def _no_gamut_lines() -> "list[str]":
    """The heading and the sentence, then one line per metric out of reach."""
    lines = [tr(
        "This preset comes with its pages already rendered, so ChromIQ cannot "
        "lay the sheet out again. That means it cannot be built with From "
        "Profile Gamut, and a chart printed any other way carries no "
        "colorimetric reference. It can still be printed and measured, but "
        "these metrics can never be fulfilled on it, whichever report type "
        "and limit set you choose:")]
    for rid in PE.gamut_only_rows():
        lines.append("\u2022  " + tr(PE.row_label(rid)))
    return lines


#: Why a preset cannot be checked at all. Knut's window must say something
#: about every preset on the list, and "nothing" is not an option: a user
#: preset saved without its patch set is the one real case, and the sentence
#: names the tick box that fixes it.
def _unreadable_line(row: PresetRow) -> str:
    if row.is_current_chart:
        # **NOT "THIS PRESET STORES SETTINGS ONLY".** The top line is not a
        # preset, so every sentence written for one is wrong about it. Knut,
        # 2026-09-21: *"If a chart has not been created in Create Chart […]
        # then the right info panel notifies about this and informs that a
        # chart must first be created."*
        if row.chart is None:
            return tr(
                "No chart is defined in the Create Chart tab for the run you "
                "have selected, so there is no patch set to check. Create a "
                "chart first: build one in Create Chart, load a preset, or "
                "import a chart file. The check then runs on that chart and "
                "says which metrics it can and cannot serve.")
        return tr(
            "ChromIQ could not read the patch set of the chart in Create "
            "Chart, so it cannot say what that chart can answer.")
    if row.chart is None:
        return tr(
            "This preset stores settings only, so ChromIQ has no patch set to "
            "check. Load or generate its chart, then save the preset again "
            "with \"Build from the currently loaded patch set (attach its "
            ".ti1)\" ticked, and it will be checked like the rest.")
    return tr(
        "ChromIQ could not read this preset's patch set, so it cannot say "
        "what the chart can answer.")


# ---------------------------------------------------------------------------
# The detail pane's content, as DATA — so two windows can show it
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Line:
    """One paragraph of the detail pane: its text and how it is set."""
    text: str
    bold: bool = False
    info: bool = False
    indent: int = 0


def detail_lines(row: "PresetRow | None") -> "list[Line]":
    """Everything the right-hand pane says about one chart, as data.

    **THE PANE'S CONTENT LEFT `_show_detail` SO THAT A SECOND WINDOW COULD
    SHOW IT** (#182, B8-610). Knut asked the Measure tab's verification
    pre-flight to *"initiate the same function used inside 'Which presets can
    be used for verification?' window"* and to *"output the same detailed
    information […] given in the right-side information panel"*. Same
    function, therefore: `_show_detail` renders this, and so does the popup,
    so the two can never come to describe the same chart differently.
    """
    if row is None:
        return [Line(tr("Select a preset on the left to see what it can "
                        "answer."), info=True)]
    out: "list[Line]" = [Line(row.label, bold=True)]
    # NEVER "0 patches · 0 pages". A zero here means ChromIQ does not know,
    # and printing it as a number is a false statement about the preset:
    # measured on a user preset saved without its patch set, the pane said
    # "0 patches · 0 pages" about a preset whose chart it had never seen.
    facts = []
    if row.patches:
        facts.append(count_phrase(row.patches, tr("1 patch"), tr("{n} patches")))
    if row.pages:
        facts.append(count_phrase(row.pages, tr("1 page"), tr("{n} pages")))
    if facts:
        out.append(Line("   ·   ".join(facts), info=True))
    a = row.assessment
    # **THE GAMUT NOTE COMES FIRST, BEFORE THE STAR'S ABSENCE IS EXPLAINED ANY
    # OTHER WAY.** It is the reason this preset has no star and the reason it
    # is gone from the filtered list, so a reader who has just ticked the box
    # and lost it finds the answer at the top of the pane rather than under
    # two ticks and a cross.
    if not row.relayoutable:
        lines = _no_gamut_lines()
        out.append(Line(tr("Not usable for verification using From Profile "
                           "Gamut"), bold=True))
        out.append(Line(lines[0], info=True))
        out += [Line(t, info=True, indent=10) for t in lines[1:]]
    if row.is_current_chart:
        # WHY THIS ROW DOES NOT BEHAVE LIKE THE OTHERS, said where the reader
        # is already looking. Every other line in the list loads on a
        # double-click; this one cannot, because there is no preset to apply.
        out.append(Line(tr(
            "This is the chart the Create Chart tab currently holds for the "
            "run you have selected. It is not a preset, so double-clicking it "
            "loads nothing."), info=True))
        if row.chart is not None:
            out.append(Line(_gamut_state_line(row), info=True))
    if row.starred:
        out.append(Line(tr("★  Made for verification.")))
    elif (not row.is_current_chart and row.chart is not None
            and not row.pages and a.checked):
        # A USER PRESET'S PAGE COUNT IS NOT KNOWABLE FROM ITS PATCH SET. How
        # many sheets a set lays out depends on the instrument, the paper and
        # the patch width, so the star is withheld and this says why rather
        # than leaving a reader to wonder.
        #
        # **…AND NOT FOR THE CURRENT CHART EITHER** (B8-611): that row is not
        # a preset, nothing can be "marked as made for verification" about it,
        # and a chart that has been laid out has a page count that simply was
        # not passed in when the caller could not count the sheets.
        out.append(Line(tr(
            "ChromIQ cannot tell how many pages this preset lays out until "
            "its chart is generated, so it is not marked as made for "
            "verification."), info=True))

    if not a.checked:
        out.append(Line(tr("Cannot be checked"), bold=True))
        out.append(Line(_unreadable_line(row)))
        return out
    if not a.asked:
        out.append(Line(tr("This report type judges nothing, so this preset "
                           "cannot fall short of it.")))
        return out

    if a.answered:
        out.append(Line(tr("This chart can answer"), bold=True))
        out += [Line("✓  " + tr(PE.row_label(rid)), indent=6)
                for rid in a.answered]
    if a.missing:
        out.append(Line(tr("This chart cannot answer"), bold=True))
        for rid, why in a.missing:
            out.append(Line("✕  " + tr(PE.row_label(rid)), indent=6))
            out.append(Line(reason_line(why), info=True, indent=22))
            remedy = PE.row_remedy(rid)
            if remedy:
                out.append(Line(tr(remedy), info=True, indent=22))
        # **WHAT THE REPORT DOES WITH THESE ROWS, AND THE ONE LEVER OVER IT.**
        # M-VERIFY-UNCHECKED-METRICS, asked for by Knut on 2026-09-22. Every
        # line above says what a row is short of; none of them said what the
        # reader will actually see in the finished document, which is an N-A
        # and a numbered note rather than nothing at all. Knut's point is that
        # a document handed to a customer can be made to hold only the metrics
        # that were checked, and that the control for it is in Report limits.
        #
        # Under the list and not above it: the list is the answer to the
        # question this window is opened with, and this is what to do about it.
        from workflow.measurement_messages import M_VERIFY_UNCHECKED_METRICS
        for para in M_VERIFY_UNCHECKED_METRICS.render()[1].split("\n\n"):
            out.append(Line(para, info=True))
    else:
        out.append(Line(tr("This chart answers every metric this report type "
                           "and limit set ask of it.")))
    return out


def _gamut_state_line(row: PresetRow) -> str:
    """Whether FROM PROFILE GAMUT was used on the chart now in Create Chart.

    Knut asked the check on that row to include *"if the current chart has
    applied the 'From Profile Gamut' feature"*, and a reader cannot act on an
    answer that is never stated: the three metrics it unlocks are withheld
    with the same words on a chart that was never converted and on one whose
    reference has been deleted, and only this line tells them apart.
    """
    if row.from_profile_gamut:
        return tr(
            "This chart was built with From Profile Gamut, so it carries the "
            "colorimetric reference the three reference metrics are judged "
            "against.")
    return tr(
        "This chart was not built with From Profile Gamut, so it carries no "
        "colorimetric reference.")


def summary_lines(row: "PresetRow | None", *, generic: bool = False) -> "list[Line]":
    """The same answer, short enough for a popup to carry it.

    Knut, on the pre-flight window: *"A summary of that info shall be shown in
    the pop-up message, so that the text does not become too long."* So the
    ticks are collapsed into one count and only the metrics the chart CANNOT
    serve are listed, each with the one sentence saying what it is short of.
    The metric's own remedy stays in the full pane, which the reader is sent
    to by name.
    """
    if row is None or not row.assessment.checked:
        return [Line(_unreadable_line(row)) if row is not None else Line("")]
    a = row.assessment
    out: "list[Line]" = []
    if row.is_current_chart and row.chart is not None:
        out.append(Line(_gamut_state_line(row), info=True))
    if not a.asked:
        out.append(Line(tr("This report type judges nothing, so this chart "
                           "cannot fall short of it.")))
        return out
    # NOT `count_phrase`: it formats `{n}` and hands the string straight back,
    # so a second placeholder in the same sentence reaches `.format` already
    # applied and the call dies on the one it has not seen. Its own docstring
    # says it fills in `{n}`, which is exactly one placeholder. Two sentences,
    # both formatted here, for the same house rule it exists to serve.
    n, total = len(a.answered), len(a.asked)
    # GENERIC WHEN NOTHING HAS BEEN CHOSEN YET. Knut, on beta 32: the
    # pre-flight named "this report type and limit set" at a moment when the
    # user has opened no report and picked neither. That window now asks
    # `assess_any`, which unions every combination, so the sentence has to say
    # what it really counted: 16 rows across every type and set, against 7 for
    # one pair on his own chart.
    if generic:
        one = tr("This chart can answer 1 of the {total} metrics that the "
                 "available report types and limit sets can use.")
        many = tr("This chart can answer {n} of the {total} metrics that the "
                  "available report types and limit sets can use.")
    else:
        one = tr("This chart can answer 1 of the {total} metrics this report "
                 "type and limit set ask of it.")
        many = tr("This chart can answer {n} of the {total} metrics this "
                  "report type and limit set ask of it.")
    out.append(Line((one if n == 1 else many).format(n=n, total=total),
                    bold=True))
    if not a.missing:
        out.append(Line(tr("Nothing is missing: every metric this chart is "
                           "asked for can be measured on it.")))
        return out
    out.append(Line(tr("It cannot answer these"), bold=True))
    for rid, why in a.missing:
        out.append(Line("✕  " + tr(PE.row_label(rid)), indent=6))
        out.append(Line(reason_line(why), info=True, indent=22))
    return out


def gamut_only_shortfalls(row: "PresetRow | None") -> "tuple[str, ...]":
    """Of the metrics this chart cannot answer, those FROM PROFILE GAMUT is
    the only lever for. Empty when there are none, which is what decides
    whether the pre-flight window mentions the feature at all."""
    if row is None or not row.assessment.checked:
        return ()
    gamut = set(PE.gamut_only_rows())
    return tuple(rid for rid, _why in row.assessment.missing if rid in gamut)


#: **KNUT'S OWN WORDING FOR THE TOP LINE**, 2026-09-21: *"That line should
#: always be at the top and be shown as 'Current chart layout in Create Chart
#: tab'."* A function rather than a constant because `tr()` is answered against
#: the language chosen at start-up, and a module constant would fix the English
#: at import time.
def CURRENT_CHART_LABEL() -> str:      # noqa: N802 — it reads as a constant
    return tr("Current chart layout in Create Chart tab")


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------
class PresetVerificationDialog(WorkAreaClamped, QDialog):
    """The list of presets, marked against one report type and one limit set."""

    def __init__(self, rows: "list[PresetRow]",
                 overrides: "dict | None" = None,
                 parent: "QWidget | None" = None,
                 select: "str | None" = None,
                 current: "PresetRow | None" = None) -> None:
        """*select* is the label of the preset to open on.

        *current* is the chart the Create Chart tab currently holds, shown as
        the first line of the list above a separator that cannot be clicked
        (#182, Knut, 2026-09-21). It is never None in the app: `TabChart`
        always passes a row, carrying a chart or carrying None to say there is
        none, because *"if a chart has not been created in Create Chart […]
        the right info panel notifies about this"* is itself an answer the
        window owes the reader. It defaults to None only so the window can
        still be built by a caller that has no Create Chart tab.

        **A LIST OF 177 IS NOT AN ANSWER TO "CAN THIS ONE BE VERIFIED?"**
        Measured on screen (round 27b, B8-423): the window opened with nothing
        selected, the detail pane reading "Select a preset on the left", and
        the preset the user had chosen in the pulldown one row among 177 in
        nine instrument groups, with no search field to find it by name. The
        question this window is the door to is asked about a particular chart,
        and the caller knows which one, so it says.

        Nothing is filtered and nothing is hidden by this: the whole list is
        still there and the reader can click any of it. Only the starting point
        changes, and it changes to the row they came in asking about.
        """
        super().__init__(parent)
        self.setWindowTitle(tr("Which presets can be used for verification"))
        self._rows = list(rows)
        #: The one row that is not a preset. Kept OUT of `_rows` so that every
        #: count, filter and group loop in here goes on meaning presets: the
        #: figures line says "Presets listed", and the current chart is not one.
        self._current = current
        if self._current is not None:
            self._current.is_current_chart = True
            self._current.label = CURRENT_CHART_LABEL()
        self._overrides = overrides
        #: Set by a double-click, read by the caller once `exec` has returned:
        #: the Create Chart pulldown key of the preset to load. Knut, beta 25.
        self.chosen_key: "str | None" = None
        #: consumed by the FIRST `_fill_tree`; after that the user's own
        #: selection is what is kept across a refresh.
        #:
        #: **AND IT FALLS BACK TO THE CURRENT CHART** (B8-611), photographed
        #: before this line: with no preset chosen in the pulldown the window
        #: opened with 177 rows and a detail pane reading "Select a preset on
        #: the left", which is the same emptiness B8-423 fixed for the preset
        #: case. The chart the reader already has is the most particular chart
        #: in the list, so it is where the window starts when nothing else is
        #: indicated. A named preset still wins.
        self._open_on = select or (CURRENT_CHART_LABEL() if current is not None
                                   else None)
        self._build()
        # **THE SIZE IN KNUT'S OWN SCREENSHOT.** Beta 25: *"The width of the
        # right panel for detailed info is too narrow. A good default width of
        # the right panel in proportion to the left panel is shown in this
        # screenshot"* — 1179 x 730, with the list 838 px and the detail pane
        # 305 px. Measured on screen before this line: the splitter holds
        # 73.8 / 26.2 at EVERY window width (1040, 1179 and 1400 all gave it),
        # so the proportion he photographed is the proportion the window
        # already had and the only thing his screenshot changes is how much
        # window there is to divide. At the old 1040 the detail pane opened at
        # 263 px; at his 1179 it opens at 299. So the default is his, and the
        # list keeps the width it has in his picture rather than paying for
        # the detail pane.
        self.resize(1179, min(730, self._work_area_cap(730)))
        self._keep_inside_the_work_area()
        self.refresh()

    # -- construction ----------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        intro = QLabel(tr(
            "Every preset ChromIQ ships, and your own, against the metrics a "
            "report of this type judged against this limit set asks to verify "
            "on a chart. Nothing is hidden: click a preset to see what it can "
            "answer and what it cannot, and double-click it to close this "
            "window and load it in Create Chart."), self)
        intro.setWordWrap(True)
        intro.setObjectName("info")
        outer.addWidget(intro)

        # -- the two pulldowns
        picks = QHBoxLayout()
        picks.setSpacing(8)
        picks.addWidget(QLabel(tr("Report type:"), self))
        self._type_combo = NoScrollComboBox(self)
        for tid, name, blurb, built in MR.REPORT_TYPE_MENU:
            if not built:
                continue
            self._type_combo.addItem(tr(name), userData=tid)
            self._type_combo.setItemData(
                self._type_combo.count() - 1, tr(blurb),
                Qt.ItemDataRole.ToolTipRole)
        picks.addWidget(self._type_combo, stretch=1)
        picks.addSpacing(12)
        picks.addWidget(QLabel(tr("Judged against:"), self))
        self._set_combo = NoScrollComboBox(self)
        for sid in CS.selectable_set_ids(self._overrides):
            self._set_combo.addItem(CS.set_label(sid), userData=sid)
            self._set_combo.setItemData(
                self._set_combo.count() - 1, tr(CS.SET_BY_ID[sid].blurb),
                Qt.ItemDataRole.ToolTipRole)
        picks.addWidget(self._set_combo, stretch=1)
        outer.addLayout(picks)

        self._asked_label = QLabel("", self)
        self._asked_label.setWordWrap(True)
        outer.addWidget(self._asked_label)

        self._only_star = QCheckBox(
            tr("Show only the presets made for verification"), self)
        outer.addWidget(self._only_star)

        star_note = QLabel(tr(
            "★ marks a chart made for verification: one printed page, "
            "{max_patches} patches or fewer, and nothing withheld that a "
            "different patch set would supply. The mark describes the chart, "
            "so it does not change with the two pulldowns above.").format(
                max_patches=PE.VERIFICATION_MAX_PATCHES), self)
        star_note.setWordWrap(True)
        star_note.setObjectName("info")
        outer.addWidget(star_note)

        # -- the list and the detail
        split = QSplitter(Qt.Orientation.Horizontal, self)
        self._tree = QTreeWidget(split)
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels([tr("Preset"), tr("Patches"), tr("Pages"),
                                    tr("Metrics answered")])
        self._tree.setRootIsDecorated(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setAlternatingRowColors(True)
        # The NAME takes the leftover width and the three figures keep a
        # fixed one. With the last section stretching instead, 240 px of empty
        # column sat to the right of "Metrics answered" while every preset name
        # was elided; photographed before this line.
        from PyQt6.QtWidgets import QHeaderView
        head = self._tree.header()
        head.setStretchLastSection(False)
        head.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        # …AND NEVER NARROWER THAN ITS OWN HEADING (round B before beta 37,
        # L3): 140 px cut the German "Beantwortete Metriken" to "…Metriker".
        # A heading is a translated string, so its width is measured.
        hfm = head.fontMetrics()
        for c, wdt in ((1, 80), (2, 70), (3, 140)):
            head.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            label = self._tree.headerItem().text(c)
            self._tree.setColumnWidth(
                c, max(wdt, hfm.horizontalAdvance(label) + _HEADER_PAD))
        # A BOUND METHOD, never a self-capturing lambda on a signal a widget's
        # own child emits: CLAUDE.md, the fade-scroll SIGSEGV.
        self._tree.currentItemChanged.connect(self._on_selected)
        # Knut, beta 25: *"make it so that double-clicking a preset is
        # equivalent to selecting and loading a preset from the 'Select preset'
        # pulldown list."* A BOUND METHOD, for the same reason as the line
        # above it.
        self._tree.itemDoubleClicked.connect(self._on_double_clicked)
        split.addWidget(self._tree)

        detail_host = QWidget(split)
        dh = QVBoxLayout(detail_host)
        dh.setContentsMargins(0, 0, 0, 0)
        self._detail_scroll = FadeScrollArea(detail_host)
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setFrameShape(FadeScrollArea.Shape.NoFrame)
        self._detail_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # A DIALOG NEVER RECEIVES `MainWindow.apply_theme`'s BROADCAST, and
        # `FadeScrollArea` starts in dark. Photographed on the light theme
        # before this line: the bottom fade painted a black band with white
        # text over the detail pane's last paragraph. `_ToolDialogBase` does
        # the same thing for the same reason.
        self._detail_scroll.set_appearance(active_mode())
        self._detail = QWidget()
        self._detail_layout = QVBoxLayout(self._detail)
        self._detail_layout.setContentsMargins(10, 4, 10, 10)
        self._detail_layout.setSpacing(6)
        self._detail_scroll.setWidget(self._detail)
        dh.addWidget(self._detail_scroll)
        # **THE DETAIL PANE HAS A FLOOR NOW.** Every metric label in it is
        # word-wrapped, and the pane is the half of the window Knut called too
        # narrow, so it may not be squeezed below what his screenshot shows
        # (305 px) however small the window gets: the list can elide a preset
        # name and still be read, a wrapped sentence three words wide cannot.
        detail_host.setMinimumWidth(300)
        split.addWidget(detail_host)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 4)
        outer.addWidget(split, stretch=1)

        self._figures = QLabel("", self)
        self._figures.setWordWrap(True)
        outer.addWidget(self._figures)

        bb = QDialogButtonBox(self)
        close = bb.addButton(tr("Close"), QDialogButtonBox.ButtonRole.RejectRole)
        close.setDefault(True)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        self._type_combo.currentIndexChanged.connect(self._on_choice_changed)
        self._set_combo.currentIndexChanged.connect(self._on_choice_changed)
        self._only_star.toggled.connect(self._on_choice_changed)

    # -- the current choice ----------------------------------------------
    def current_type(self) -> str:
        return str(self._type_combo.currentData() or "")

    def current_set(self) -> str:
        return str(self._set_combo.currentData() or "")

    # -- slots (bound methods, never lambdas) ----------------------------
    def _on_choice_changed(self, *_a) -> None:
        self.refresh()

    def _on_selected(self, current, _previous=None) -> None:
        self._show_detail(current.data(0, Qt.ItemDataRole.UserRole)
                          if current is not None else None)

    def _on_double_clicked(self, item, _column: int = 0) -> None:
        """Knut, beta 25: a double-click loads the preset and closes this.

        *"What happens when double-clicking a preset is that the window is
        closed and the selected preset is loaded in Create Chart for the
        selected 'profile run' and 'run type'=verification."*

        THE LOADING IS THE CALLER'S, not this window's, and deliberately so:
        applying a preset asks for a name, can start a build and can be backed
        out of (#175), and none of that may happen underneath a modal that is
        still on screen. This records WHICH preset and accepts; `TabChart`
        reads `chosen_key` once `exec` has returned and routes it through the
        pulldown's own handler, so a double-click and a pick in the dropdown
        run the same code.

        A GROUP HEADING IS NOT A PRESET. Its item carries no `PresetRow`, and
        the tree expands and collapses on a double-click there, which is what
        a reader expects; this leaves that alone.
        """
        row = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(row, PresetRow) or not row.key:
            return
        # **AND THE CURRENT-CHART LINE IS NOT DOUBLE-CLICKABLE EITHER.** Knut,
        # 2026-09-21: *"This line cannot be double-clicked, as no new preset
        # shall be applied, as with the other lines in the list that are
        # actual presets."* It carries no `key` in the app, so the guard above
        # already covers it; this one makes the rule true of the row rather
        # than of a field a caller could fill in by mistake.
        if row.is_current_chart:
            return
        self.chosen_key = str(row.key)
        self.accept()

    # -- the work --------------------------------------------------------
    def refresh(self) -> None:
        """Re-assess every preset against the current choice and redraw."""
        type_id, set_id = self.current_type(), self.current_set()
        for row in self._rows + ([self._current] if self._current else []):
            row.assessment = PE.assess(row.chart, type_id, set_id,
                                       self._overrides, recipe=row.recipe)
            row.starred = PE.made_for_verification(
                row.chart, row.patches, row.pages,
                relayoutable=row.relayoutable, recipe=row.recipe)
        if self._current is not None:
            # **THE STAR IS A MARK ON A PRESET, AND THIS ROW IS NOT ONE.**
            # It says "this is one of the charts made for verification, pick
            # it", which is advice about a list. The chart already in Create
            # Chart is the one the reader HAS; marking it would read as a
            # verdict on their own chart, and the pane under it is where the
            # verdict belongs.
            self._current.starred = False
        asked = PE.rows_asked(type_id, set_id, self._overrides)
        if not asked:
            self._asked_label.setText(tr(
                "This report type judges nothing, so no chart can fall short "
                "of it."))
        else:
            # Knut's own sentence, beta 25: *"How about writing 'This report
            # type and limit set asks to verify 9 metrics of a chart during
            # verification.'"*
            self._asked_label.setText(count_phrase(
                len(asked),
                tr("This report type and limit set asks to verify 1 metric "
                   "of a chart during verification."),
                tr("This report type and limit set asks to verify {n} "
                   "metrics of a chart during verification.")))
        self._fill_tree()
        self._fill_figures()

    def _style_separator(self, sep) -> None:
        """Make the row under the current chart LOOK like a rule, not a gap.

        A blank disabled row is a gap, and a gap is what the list already has
        between groups; Knut asked for *"a separator line"*. A real `QFrame`
        in the row draws one at the palette's own mid tone, so it is a line in
        every appearance without a colour being typed here.
        """
        from PyQt6.QtCore import QSize
        from PyQt6.QtWidgets import QFrame
        rule = QFrame(self._tree)
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFrameShadow(QFrame.Shadow.Plain)
        rule.setFixedHeight(9)
        sep.setSizeHint(0, QSize(1, 9))
        self._tree.setItemWidget(sep, 0, rule)

    def _fill_tree(self) -> None:
        only = self._only_star.isChecked()
        keep_label = None
        cur = self._tree.currentItem()
        if cur is not None:
            row = cur.data(0, Qt.ItemDataRole.UserRole)
            keep_label = row.label if isinstance(row, PresetRow) else None
        if keep_label is None and self._open_on is not None:
            keep_label, self._open_on = self._open_on, None
        self._tree.clear()
        bold = self._tree.font()
        bold.setBold(True)
        select_me = None
        # **THE CURRENT CHART, ALWAYS FIRST, NEVER FILTERED.** Knut,
        # 2026-09-21: *"That line should always be at the top and be shown as
        # 'Current chart layout in Create Chart tab'. That line must be clearly
        # separated from all the other presets with a separator line which is
        # not clickable."* It is a TOP-LEVEL item, not a member of any group,
        # and the tick box above cannot remove it: the reader's own chart is
        # the one row that is never advice about somebody else's.
        if self._current is not None:
            item = QTreeWidgetItem(self._tree, self._columns(self._current))
            item.setData(0, Qt.ItemDataRole.UserRole, self._current)
            item.setFont(0, bold)
            if self._current.label == keep_label:
                select_me = item
            sep = QTreeWidgetItem(self._tree, ["", "", "", ""])
            sep.setFirstColumnSpanned(True)
            # NOT CLICKABLE, and that is the whole point of it: no
            # ItemIsSelectable and no ItemIsEnabled, so a click lands nowhere
            # and the keyboard walks straight past it.
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            self._style_separator(sep)
        for group in dict.fromkeys(r.group for r in self._rows):
            members = [r for r in self._rows
                       if r.group == group and (r.starred or not only)]
            if not members:
                continue
            head = QTreeWidgetItem(self._tree, [group, "", "", ""])
            head.setFirstColumnSpanned(True)
            head.setFont(0, bold)
            head.setFlags(Qt.ItemFlag.ItemIsEnabled)
            for r in members:
                item = QTreeWidgetItem(head, self._columns(r))
                item.setData(0, Qt.ItemDataRole.UserRole, r)
                if r.starred:
                    item.setFont(0, bold)
                if r.label == keep_label:
                    select_me = item
            head.setExpanded(True)
        if select_me is not None:
            self._tree.setCurrentItem(select_me)
            # …AND SHOW IT. `setCurrentItem` does not scroll on a tree that has
            # just been filled, and a selection below the fold is a selection
            # nobody can see: the preset the caller opened on sat 140 rows down.
            from PyQt6.QtWidgets import QAbstractItemView
            self._tree.scrollToItem(
                select_me, QAbstractItemView.ScrollHint.PositionAtCenter)
        else:
            self._show_detail(None)

    def _columns(self, row: PresetRow) -> "list[str]":
        name = ("★  " + row.label) if row.starred else row.label
        a = row.assessment
        if not a.checked:
            verdict = tr("Cannot be checked")
        elif not a.asked:
            verdict = tr("Nothing is judged")
        else:
            verdict = tr("{n} of {total} metrics").format(
                n=len(a.answered), total=len(a.asked))
        return [name,
                str(row.patches) if row.patches else "",
                str(row.pages) if row.pages else "",
                verdict]

    def _fill_figures(self) -> None:
        shown = [r for r in self._rows
                 if r.starred or not self._only_star.isChecked()]
        s = PE.summarise(shown)
        self._figures.setText(
            tr("Presets listed: {listed}     Made for verification: "
               "{starred}     Answering every metric asked: {complete}").format(
                   listed=s["listed"], starred=s["starred"],
                   complete=s["complete"]))

    # -- the detail pane -------------------------------------------------
    def _clear_detail(self) -> None:
        while self._detail_layout.count():
            it = self._detail_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _add(self, text: str, *, bold: bool = False, info: bool = False,
             indent: int = 0) -> QLabel:
        lab = QLabel(text, self._detail)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        if bold:
            f = lab.font()
            f.setBold(True)
            lab.setFont(f)
        if info:
            lab.setObjectName("info")
        if indent:
            lab.setContentsMargins(indent, 0, 0, 0)
        self._detail_layout.addWidget(lab)
        return lab

    def _show_detail(self, row: "PresetRow | None") -> None:
        """Draw what `detail_lines` says, and decide nothing of its own.

        The content moved out to module level for B8-610 so the Measure tab's
        verification pre-flight can show the same answer about the same chart.
        """
        self._clear_detail()
        for line in detail_lines(row):
            self._add(line.text, bold=line.bold, info=line.info,
                      indent=line.indent)
        self._detail_layout.addStretch()
