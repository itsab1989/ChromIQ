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

#: The two "Sort by" choices (K33-8, B8-999). The first is the order the list
#: has always had, the Create Chart Preset pulldown's own; the second sorts
#: each group by how many of the counted metrics a preset's chart answers.
SORT_PULLDOWN = "pulldown_order"
SORT_MOST_ANSWERED = "most_answered"


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
    #: True while this preset's answer is being worked out on the background
    #: thread (K40-1): the row reads "Working…" and is re-read when it arrives.
    pending: bool = False


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
        # #182 B8-483: enough steps, but not the required number roughly
        # evenly spaced from black to white.
        MR.REASON_GREY_STEPS_BUNCHED:
            tr("The grey steps on this chart are bunched together: it has "
               "no {n} of them roughly evenly spaced from black to "
               "white.").format(n=MR.GREY_MIN_LEVELS),
        MR.REASON_NO_WHITE:
            tr("The grey ramp on this chart does not reach white."),
        MR.REASON_NO_BLACK:
            tr("The grey ramp on this chart does not reach black."),
        MR.REASON_NO_RAMP:
            tr("This chart has no tone ramp through the mid-tones."),
        # K31 rule A (Knut, #182 5801677743): the grey ramp's spacing rule,
        # applied to the 30 to 70 % band.
        MR.REASON_RAMP_STEPS_BUNCHED:
            tr("The mid-tone steps of this chart's tone ramps are bunched "
               "together: no ramp has {n} of them roughly evenly spaced "
               "between 30 % and 70 %.").format(n=MR.RAMP_MIN_STEPS),
        # K31 option (a): a FROM PROFILE GAMUT chart's grey steps are its
        # neutral aims, which come from the profile.
        MR.REASON_TOO_FEW_NEUTRAL_AIMS:
            tr("This chart was built with From Profile Gamut, and it carries "
               "fewer than {n} distinct neutral aims to serve as its grey "
               "steps.").format(n=MR.GREY_MIN_LEVELS),
        MR.REASON_NEUTRAL_AIMS_BUNCHED:
            tr("The neutral aims on this chart are bunched together: it has "
               "no {n} of them roughly evenly spaced from its black to its "
               "white.").format(n=MR.GREY_MIN_LEVELS),
        # K40-2 (Knut, #182 5832026677): the tone row of such a chart takes
        # its neutral aims too, placed at 100 minus their L*.
        MR.REASON_RAMP_TOO_FEW_NEUTRAL_AIMS:
            tr("This chart was built with From Profile Gamut, and it carries "
               "fewer than {n} distinct neutral aims between L* 30 and L* 70, "
               "spanning at least {span}, to serve as its mid-tone "
               "ramp.").format(n=MR.RAMP_MIN_STEPS,
                               span=f"{MR.RAMP_MIN_SPAN:g}"),
        MR.REASON_RAMP_NEUTRAL_AIMS_BUNCHED:
            tr("The neutral aims of this chart between L* 30 and L* 70 are "
               "bunched together: it has no {n} of them roughly evenly "
               "spaced.").format(n=MR.RAMP_MIN_STEPS),
        MR.REASON_NEUTRAL_AIMS_NO_WHITE:
            tr("The neutral aims on this chart do not reach its lightest "
               "colours."),
        MR.REASON_NEUTRAL_AIMS_NO_BLACK:
            tr("The neutral aims on this chart do not reach its darkest "
               "colours."),
        MR.REASON_SMALL_SAMPLE:
            tr("This chart has too few patches for a highest 5 % of them "
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
        MR.REASON_NO_DEVICE_VALUES:
            tr("This chart carries no device values."),
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
        # K40-1 (Knut, #182 5832026677): a printtarg preset is laid out
        # behind the scenes. While that runs the metric is not missing, it is
        # being checked; when printtarg cannot do it, the line says so and
        # the pane quotes printtarg (`detail_lines`).
        PE.REASON_EVENNESS_LAYING_OUT:
            tr("ChromIQ is laying this preset's page out to check it. The "
               "answer appears here in a moment."),
        PE.REASON_EVENNESS_LAYOUT_NO_TOOL:
            tr("printtarg, which lays this preset's page out, was not found "
               "in the ArgyllCMS folder set in Preferences, so where its "
               "patches will sit on the page is not known."),
        PE.REASON_EVENNESS_LAYOUT_REFUSED:
            tr("printtarg, which lays this preset's page out, could not lay "
               "it out, so where its patches will sit on the page is not "
               "known."),
    }.get(code, tr("ChromIQ cannot check this metric on this chart."))


#: The reasons that are about laying a preset out behind the scenes (K40-1).
#: No lever of the metric's own help fits them: a larger chart does not make
#: printtarg appear, and a row still being laid out is short of nothing.
_LAYOUT_REASONS = frozenset({PE.REASON_EVENNESS_LAYING_OUT,
                             PE.REASON_EVENNESS_LAYOUT_NO_TOOL,
                             PE.REASON_EVENNESS_LAYOUT_REFUSED})


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


def detail_lines(row: "PresetRow | None", *,
                 every_metric: bool = False) -> "list[Line]":
    """Everything the right-hand pane says about one chart, as data.

    **THE PANE'S CONTENT LEFT `_show_detail` SO THAT A SECOND WINDOW COULD
    SHOW IT** (#182, B8-610). Knut asked the Measure tab's verification
    pre-flight to *"initiate the same function used inside 'Which presets can
    be used for verification?' window"* and to *"output the same detailed
    information […] given in the right-side information panel"*. Same
    function, therefore: `_show_detail` renders this, and so does the popup,
    so the two can never come to describe the same chart differently.

    *every_metric* is True while "Judged against" says "All metrics"
    (B8-974): there is no limit set then, so the closing sentence may not
    name one.
    """
    if row is None:
        return [Line(tr("Select a preset on the left to see what it can "
                        "answer."), info=True)]
    out: "list[Line]" = [Line(row.label, bold=True)]
    if row.pending:
        # K40-1: worked out behind the scenes; nothing to say about it yet
        out.append(Line(tr("ChromIQ is still checking this preset, laying "
                           "its page out where it needs to. The answer "
                           "appears here in a moment."), info=True))
        return out
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
    # K40-1: a metric whose page is still being laid out behind the scenes
    # is not one the chart "cannot answer" yet; it is listed on its own.
    working = [(rid, why) for rid, why in a.missing
               if why == PE.REASON_EVENNESS_LAYING_OUT]
    missing = [(rid, why) for rid, why in a.missing
               if why != PE.REASON_EVENNESS_LAYING_OUT]
    if working:
        out.append(Line(tr("Still being checked"), bold=True))
        for rid, _why in working:
            out.append(Line("…  " + tr(PE.row_label(rid)), indent=6))
        out.append(Line(reason_line(PE.REASON_EVENNESS_LAYING_OUT),
                        info=True, indent=22))
    if missing:
        out.append(Line(tr("This chart cannot answer"), bold=True))
        said = PE.layout_failure_detail(row.chart, row.recipe)
        for rid, why in missing:
            out.append(Line("✕  " + tr(PE.row_label(rid)), indent=6))
            out.append(Line(reason_line(why), info=True, indent=22))
            if why == PE.REASON_EVENNESS_LAYOUT_REFUSED and said:
                # printtarg's own words, quoted as its own
                out.append(Line(tr("printtarg said: “{said}”").format(
                    said=said), info=True, indent=22))
            remedy = ("" if why in _LAYOUT_REASONS
                      else PE.row_remedy(rid, why))
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
    elif working:
        pass
    elif every_metric:
        out.append(Line(tr("This chart answers every metric a report of this "
                           "type can judge.")))
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
    """The list of presets, marked against one report type and one limit set,
    or against every metric that report type can judge ("All metrics")."""

    def __init__(self, rows: "list[PresetRow]",
                 overrides: "dict | None" = None,
                 parent: "QWidget | None" = None,
                 select: "str | None" = None,
                 current: "PresetRow | None" = None,
                 background: bool = False) -> None:
        """*select* is the label of the preset to open on.

        *background* (K40-1, Knut #182 5832026677: *"It must never block the
        window"*): a preset whose answer is not known yet is worked out on
        `preset_layout`'s background thread and reads "Working…" until it
        arrives, instead of the window computing it before it opens. The app
        opens the window this way (`TabChart._open_preset_verification_window`);
        a caller that wants every answer at once leaves it False.

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
        self._background = bool(background)
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

        # **SAYS WHAT THE TWO FIELDS DO, IN PLAIN WORDS** (K33, B8-997).
        # Knut, #182 5816565326: *"the intro sentence shall say what the
        # fields to, even if the default is set to show any and all metrics.
        # However, the sentence is hard to read and understand, so the
        # wording should be rephrased for easier understanding."* The old
        # sentence ran "the metrics a report of this type judged against
        # this limit set asks to verify on a chart" as one noun phrase.
        intro = QLabel(tr(
            "Every preset ChromIQ ships, and your own, with the number of "
            "metrics its chart can answer. The two fields below choose which "
            "metrics are counted: the ones a report of that type, judged "
            "against that limit set, would check. “Any” and “All metrics” "
            "count every metric a report can check. Click a preset to see "
            "what it can and cannot answer; double-click it to load it in "
            "Create Chart and close this window."), self)
        intro.setWordWrap(True)
        intro.setObjectName("info")
        outer.addWidget(intro)

        # -- the two pulldowns
        picks = QHBoxLayout()
        picks.setSpacing(8)
        picks.addWidget(QLabel(tr("Report type:"), self))
        self._type_combo = NoScrollComboBox(self)
        # **"ANY" FIRST, AND THEREFORE WHAT THE WINDOW OPENS ON** (K33,
        # B8-996), beside "All metrics" in the other pulldown. Knut, #182
        # 5816565326: *"the Report type should instead also have an option
        # called "Any", which is the default, set together with "All
        # metrics" as default for judged against. Report type and judged
        # against shall still be able to individually change if desired."*
        self._type_combo.addItem(tr("Any"), userData=PE.ANY_REPORT_TYPE)
        self._type_combo.setItemData(
            0, tr("Every metric any report of a verification can check, "
                  "whichever report type you choose later."),
            Qt.ItemDataRole.ToolTipRole)
        for tid, name, blurb, built in MR.REPORT_TYPE_MENU:
            if not MR.report_type_is_built(tid):
                continue
            self._type_combo.addItem(tr(name), userData=tid)
            self._type_combo.setItemData(
                self._type_combo.count() - 1, tr(blurb),
                Qt.ItemDataRole.ToolTipRole)
        picks.addWidget(self._type_combo, stretch=1)
        picks.addSpacing(12)
        picks.addWidget(QLabel(tr("Judged against:"), self))
        self._set_combo = NoScrollComboBox(self)
        # **"ALL METRICS" FIRST, AND THEREFORE WHAT THE WINDOW OPENS ON, EVERY
        # TIME** (B8-974). Knut, #182 5814820283: *"The 'All Metrics' option
        # should be the default when opening the window, as we do not know
        # what the user will pick when later creating reports."* Nothing
        # remembers the last choice: the pulldown is filled afresh on every
        # open and a combo box starts on its first entry.
        self._set_combo.addItem(tr("All metrics"), userData=PE.ALL_METRICS)
        self._set_combo.setItemData(
            0, tr("Every metric a report of this type can judge, whether or "
                  "not a limit set puts a limit on it. Use it to see which "
                  "chart answers the most."),
            Qt.ItemDataRole.ToolTipRole)
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
        # **"SORT BY", RIGHT OF THE TICK BOX** (K33-8, B8-999). Knut, #182
        # 5817191535: the default is today's order, named for what it really
        # is; a second choice puts the presets answering the most metrics
        # first; presets stay under their group names and are sorted within
        # each group. Today's order is NOT alphabetical: it is the Create
        # Chart Preset pulldown's own (`BUILTIN_PRESET_GROUPS`), the ready-made
        # "by Pharmacist" charts first, then the rest from the smallest sheet
        # up, and your own presets alphabetically.
        star_row = QHBoxLayout()
        star_row.setSpacing(8)
        star_row.addWidget(self._only_star)
        star_row.addSpacing(24)
        star_row.addWidget(QLabel(tr("Sort by:"), self))
        self._sort_combo = NoScrollComboBox(self)
        self._sort_combo.addItem(tr("Preset pulldown order"),
                                 userData=SORT_PULLDOWN)
        self._sort_combo.setItemData(
            0, tr("The order of the Preset pulldown in Create Chart, which is "
                  "not alphabetical: in each group the ready-made charts "
                  "“by Pharmacist” come first, then the others from the "
                  "smallest sheet up and, on one sheet size, by patch size "
                  "and count. Your own presets are listed alphabetically."),
            Qt.ItemDataRole.ToolTipRole)
        self._sort_combo.addItem(tr("Most metrics answered first"),
                                 userData=SORT_MOST_ANSWERED)
        self._sort_combo.setItemData(
            1, tr("In each group, the presets whose chart answers the most "
                  "of the metrics counted above come first. Presets that "
                  "answer the same number keep the Preset pulldown order."),
            Qt.ItemDataRole.ToolTipRole)
        star_row.addWidget(self._sort_combo)
        star_row.addStretch(1)
        outer.addLayout(star_row)

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

        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._set_combo.currentIndexChanged.connect(self._on_choice_changed)
        self._only_star.toggled.connect(self._on_choice_changed)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)

    # -- the current choice ----------------------------------------------
    def current_type(self) -> str:
        return str(self._type_combo.currentData() or "")

    def current_set(self) -> str:
        return str(self._set_combo.currentData() or "")

    # -- slots (bound methods, never lambdas) ----------------------------
    def _on_choice_changed(self, *_a) -> None:
        self.refresh()

    def _on_type_changed(self, *_a) -> None:
        """**K36-1 (Knut, #182 5820871320)**, the same rule as the report
        window: choosing an ISO report type moves "Judged against" to its
        standard's set unless it is already one of the four ISO sets, and while it is chosen only "All metrics" and the
        four ISO sets can be chosen; the others are greyed and say why."""
        tid = self.current_type()
        iso = MR.REPORT_TYPE_ISO_SET.get(tid)
        self._set_combo.blockSignals(True)
        try:
            # KEPT WHEN ALREADY ALLOWED (Knut, #182 5822758830, answer 4):
            # an ISO set stays, even the other standard's; only a set the
            # type refuses moves to the type's own ISO 12647 set.
            if iso and not MR.set_allowed_for_type(tid, self.current_set()):
                i = self._set_combo.findData(iso)
                if i >= 0:
                    self._set_combo.setCurrentIndex(i)
            self._grey_the_sets_the_type_refuses()
        finally:
            self._set_combo.blockSignals(False)
        self.refresh()

    def _grey_the_sets_the_type_refuses(self) -> None:
        from PyQt6.QtGui import QStandardItemModel
        model = self._set_combo.model()
        if not isinstance(model, QStandardItemModel):
            return
        tid = self.current_type()
        for i in range(self._set_combo.count()):
            sid = str(self._set_combo.itemData(i) or "")
            item = model.item(i)
            if item is None or sid not in CS.SET_BY_ID:
                continue
            ok = not tid or MR.set_allowed_for_type(tid, sid)
            item.setEnabled(ok)
            item.setToolTip(tr(CS.SET_BY_ID[sid].blurb) if ok else tr(
                "Not with the report type “{type}”: it is judged against one "
                "of the four ISO limit sets (ISO 12647-7, ISO 12647-8, Custom "
                "ISO 12647-7, Custom ISO 12647-8). Choose another report type "
                "to judge against this set."
            ).format(type=tr(MR.report_type_name(tid))))

    def _on_sort_changed(self, *_a) -> None:
        """Re-sort only: the assessments do not change with the order."""
        self._fill_tree()

    def current_sort(self) -> str:
        return str(self._sort_combo.currentData() or SORT_PULLDOWN)

    def _sorted_members(self, members: list) -> list:
        """*members* of one group in the order "Sort by" asks for.

        Python's sort is stable, so presets that answer the same number keep
        the Preset pulldown order among themselves; a preset that could not be
        checked answers nothing and goes last.
        """
        if self.current_sort() != SORT_MOST_ANSWERED:
            return members

        def answered(r):
            a = r.assessment
            return len(a.answered) if a is not None and a.checked else -1
        return sorted(members, key=lambda r: -answered(r))

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
            # K40-1: a preset whose answer is not known yet goes to the
            # background thread and reads "Working…"; the reader's own chart
            # (the first line) is always answered at once.
            row.pending = bool(
                self._background and not row.is_current_chart
                and row.chart is not None
                and not PE.values_ready(row.chart, row.recipe))
            if row.pending:
                PE.request_values(row.chart, row.recipe)
                row.assessment = PE.UNCHECKED
                row.starred = False
                continue
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
        any_type = type_id == PE.ANY_REPORT_TYPE
        # **WHY 18 AND NOT 20** (K33, B8-995). Knut counted more metrics than
        # this line names. ChromIQ can compute twenty; the two repeatability
        # rows are not a property of a chart (`rows_every_metric`), so they
        # are left out of every count in this window, and the line now says
        # so where a reader compares it with the Report limits table.
        not_counted = tr("ChromIQ's two repeatability metrics are not "
                         "counted here: they depend on measuring the chart "
                         "again, not on the chart.")
        if asked and set_id == PE.ALL_METRICS and any_type:
            self._asked_label.setText(count_phrase(
                len(asked),
                tr("All metrics: a report of any type can verify 1 metric of "
                   "a chart, whichever limit set it is judged against."),
                tr("All metrics: a report of any type can verify {n} metrics "
                   "of a chart, whichever limit set it is judged against."))
                + " " + not_counted)
        elif asked and set_id == PE.ALL_METRICS:
            self._asked_label.setText(count_phrase(
                len(asked),
                tr("All metrics: a report of this type can verify 1 metric of "
                   "a chart, whichever limit set it is judged against."),
                tr("All metrics: a report of this type can verify {n} metrics "
                   "of a chart, whichever limit set it is judged against."))
                + " " + not_counted)
        elif asked and any_type:
            self._asked_label.setText(count_phrase(
                len(asked),
                tr("A report of any type, judged against this limit set, asks "
                   "to verify 1 metric of a chart during verification."),
                tr("A report of any type, judged against this limit set, asks "
                   "to verify {n} metrics of a chart during verification.")))
        elif not asked:
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
        self._watch_layouts()

    # -- presets laid out behind the scenes (K40-1) ------------------------
    def _watch_layouts(self) -> None:
        """Poll for printtarg layouts the background thread is working on.

        **A TIMER AND AN INTEGER, NO SIGNAL FROM THE THREAD.** The thread in
        `workflow.preset_layout` touches no Qt object at all; this asks
        `preset_layout.generation()` five times a second and re-reads the rows
        that were waiting when it moves. A bound method, never a closure (see
        CLAUDE.md on the scroll-bar segfault)."""
        from PyQt6.QtCore import QTimer
        waiting = [r for r in self._all_rows() if self._is_waiting(r)]
        timer = getattr(self, "_layout_timer", None)
        if not waiting:
            if timer is not None:
                timer.stop()
            return
        if timer is None:
            timer = QTimer(self)
            timer.setInterval(200)
            timer.timeout.connect(self._poll_layouts)
            self._layout_timer = timer
        self._layout_seen = None
        if not timer.isActive():
            timer.start()

    def _all_rows(self) -> "list[PresetRow]":
        return self._rows + ([self._current] if self._current else [])

    @staticmethod
    def _is_waiting(r: "PresetRow") -> bool:
        return r.pending or (r.assessment.checked
                             and PE.is_being_laid_out(r.assessment))

    def _still_laying_out(self) -> bool:
        return any(self._is_waiting(r) for r in self._all_rows())

    def _poll_layouts(self) -> None:
        """Re-assess the rows whose layout has arrived, and redraw them."""
        from workflow import preset_layout as PL
        gen = PL.generation()
        if gen == getattr(self, "_layout_seen", None):
            return
        self._layout_seen = gen
        type_id, set_id = self.current_type(), self.current_set()
        changed = []
        for row in self._all_rows():
            if not self._is_waiting(row):
                continue
            if row.pending:
                if not PE.values_ready(row.chart, row.recipe):
                    # asked again (a no-op while it is queued): a chart that
                    # changed on disk meanwhile is worked out anew
                    PE.request_values(row.chart, row.recipe)
                    continue
                row.pending = False
            elif not PE.layout_is_ready(row.chart, row.recipe):
                continue
            row.assessment = PE.assess(row.chart, type_id, set_id,
                                       self._overrides, recipe=row.recipe)
            if not row.is_current_chart:
                row.starred = PE.made_for_verification(
                    row.chart, row.patches, row.pages,
                    relayoutable=row.relayoutable, recipe=row.recipe)
            changed.append(row)
        if not changed:
            return
        still = self._still_laying_out()
        if not still and (self.current_sort() == SORT_MOST_ANSWERED
                          or self._only_star.isChecked()):
            # the order, or what the tick box shows, moves with the counts
            self._fill_tree()
        else:
            self._redraw_rows(changed)
        self._fill_figures()
        if not still:
            self._layout_timer.stop()

    def _redraw_rows(self, rows: "list[PresetRow]") -> None:
        """Rewrite the items of *rows* in place, and the detail pane if one of
        them is the row shown there."""
        want = {id(r) for r in rows}
        cur = self._tree.currentItem()
        cur_row = cur.data(0, Qt.ItemDataRole.UserRole) if cur is not None else None
        stack = [self._tree.topLevelItem(i)
                 for i in range(self._tree.topLevelItemCount())]
        bold = self._tree.font()
        bold.setBold(True)
        while stack:
            item = stack.pop()
            stack += [item.child(j) for j in range(item.childCount())]
            row = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(row, PresetRow) or id(row) not in want:
                continue
            for col, text in enumerate(self._columns(row)):
                item.setText(col, text)
            if row.starred or row.is_current_chart:
                item.setFont(0, bold)
        if isinstance(cur_row, PresetRow) and id(cur_row) in want:
            self._show_detail(cur_row)

    def wait_for_layouts(self, timeout_s: float = 120.0) -> bool:
        """Block until every preset laid out behind the scenes has arrived
        and been redrawn. For tests and on-screen drivers only; the window
        itself never waits. True when nothing is left waiting."""
        import time as _time
        from PyQt6.QtWidgets import QApplication
        end = _time.monotonic() + timeout_s
        while _time.monotonic() < end:
            QApplication.processEvents()
            self._layout_seen = None
            self._poll_layouts()
            if not self._still_laying_out():
                return True
            _time.sleep(0.05)
        return False

    def waiting_count(self) -> int:
        """How many rows read "Working…" right now."""
        return sum(1 for r in self._all_rows() if self._is_waiting(r))

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
            members = self._sorted_members(
                [r for r in self._rows
                 if r.group == group and (r.starred or not only)])
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
        if row.pending:
            verdict = tr("Working…")
        elif not a.checked:
            verdict = tr("Cannot be checked")
        elif PE.is_being_laid_out(a):
            # K40-1: Knut asked for "a clear 'working…' state per row until
            # done"; a count now would be a count of what is known so far.
            verdict = tr("Working…")
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
        text = tr("Presets listed: {listed}     Made for verification: "
                  "{starred}     Answering every metric asked: {complete}"
                  ).format(listed=s["listed"], starred=s["starred"],
                           complete=s["complete"])
        # K40-1: the counts above grow while presets are still being checked
        waiting = sum(1 for r in shown if self._is_waiting(r))
        if waiting:
            text += "     " + tr("Still being checked: {n}").format(n=waiting)
        self._figures.setText(text)

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
        for line in detail_lines(
                row, every_metric=self.current_set() == PE.ALL_METRICS):
            self._add(line.text, bold=line.bold, info=line.info,
                      indent=line.indent)
        self._detail_layout.addStretch()
