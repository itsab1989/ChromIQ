"""Limit sets for the Measurement Report (#182): the table of tolerances, the
verdict words, and nothing else.

The Measurement Report used to judge five statistics with TWO numbers, the
"average" and the "maximum" threshold, both global settings. Knut's #182
rulings (2026-09-04 to 2026-09-07) replace that with **limit sets**: a column
of limits, one per *population × statistic* row, that a profile run is bound
to and that every dated verification of that run is judged with.

Everything the rest of the application needs to know about limit sets lives
here, once:

* the **rows** (:data:`ROWS`): what is measured, over which patches, in which
  unit, and whether ChromIQ can compute it today (``now`` / ``build`` /
  ``ref`` needs a reference file / ``unknown`` the clause is not held /
  ``unmeasurable`` ChromIQ cannot measure it at all);
* the **sets** (:data:`SETS`): ChromIQ default, ChromIQ tight, Quick check,
  the two ISO value sets (read-only) and the two Custom sets that start from
  their ISO parent;
* the **factory limits** of each set (:func:`factory_limits`), and the
  effective limits once the user's Preferences overrides are applied
  (:func:`effective_limits`);
* the **verdict words** PASS / FAIL / COND / INFO / N-A (Knut, K-f,
  2026-09-07) and the two decision rules that produce them
  (:func:`row_verdict`, :func:`set_summary`). COND is an OVERALL word only,
  since Knut retired it as a row word on 2026-09-21; it stays defined because
  reports saved before that day carry it.

**The ISO tolerance numbers are not in this file.** They are read from
``data/compliance_sets/iso12647.json``. Each of its two set objects is either
EMPTY, and a row that ISO set is known to limit then reads ``?`` (the limit is
in a clause ChromIQ does not hold or may not show), or COMPLETE, carrying the
standard's values and nothing else. The licensing question (#182, Sebastian's
S-2) was answered in principle by DIN's legal department on 2026-09-23: values
alone, without pages, images or texts, are not reproduction. Filling the file
waits on the owner's explicit go-ahead
(``scripts/install_iso_12647_values_into_repo.py`` does it, printing no
value), and the code below is written for both states (§23 of
``docs/design/measurement_report_limits.md``). The *structure* of a standard, which rows it
writes a limit over, is not licensed content and is stated below so the table
can draw ``?`` in the right cells and ``–`` (the set defines no limit) in the
others.

**A verdict never names a standard.** A column may be headed "ISO 12647-8:2021
values"; a verdict sentence says "this limit set's values" and never
"conforms" (D7, D24). ChromIQ does not certify anything.

No Qt in here: this module is imported by the report code, the Measure tab's
save path, the settings migration and the two windows, and is tested without
a QApplication.
"""
from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.i18n import tr
from core.resource_path import resource_path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# The five words
# ---------------------------------------------------------------------------
#: Knut, #182 K-f (2026-09-07): *"PASS / FAIL / CONDITIONAL / INFO / N-A, and
#: maybe using a shorter version of the word for CONDITIONAL"*. The stored
#: token is English and never translated; the DISPLAYED word goes through
#: :func:`word_label`. N-A keeps his hyphen (he wrote N-A, not N/A).
PASS = "PASS"
FAIL = "FAIL"
COND = "COND"
INFO = "INFO"
N_A = "N-A"
WORDS = (PASS, FAIL, COND, INFO, N_A)


def word_label(word: str) -> str:
    """The word as shown on screen (translatable; the token is not)."""
    return {PASS: tr("PASS"), FAIL: tr("FAIL"), COND: tr("COND"),
            INFO: tr("INFO"), N_A: tr("N-A")}.get(word, word)


# ---------------------------------------------------------------------------
# A limit: one cell of the table
# ---------------------------------------------------------------------------
#: ``value`` a required limit (a *shall*); ``should`` a recommendation the set
#: does not require, drawn in brackets and carrying a numbered note, but judged
#: PASS / FAIL like any other limit (Knut, 2026-09-21); ``none`` the set
#: defines no limit for this row (``–``); ``unknown`` the number is in a
#: clause ChromIQ does not hold or may not show (``?``); ``unmeasurable`` the
#: set defines a limit ChromIQ cannot measure at all (``✕``).
LIMIT_KINDS = ("value", "should", "none", "unknown", "unmeasurable")


@dataclass(frozen=True)
class Limit:
    kind: str
    number: "float | None" = None

    # -- constructors
    @classmethod
    def value(cls, x: float) -> "Limit":
        return cls("value", float(x))

    @classmethod
    def should(cls, x: float) -> "Limit":
        return cls("should", float(x))

    @classmethod
    def none(cls) -> "Limit":
        return cls("none")

    @classmethod
    def unknown(cls) -> "Limit":
        return cls("unknown")

    @classmethod
    def unmeasurable(cls) -> "Limit":
        return cls("unmeasurable")

    # -- properties
    @property
    def is_numeric(self) -> bool:
        """True for a limit a value can be compared against (shall or should)."""
        return self.kind in ("value", "should") and self.number is not None

    @property
    def is_should(self) -> bool:
        return self.kind == "should"

    # -- JSON: number | [number, "should"] | null | "?" | "x"
    def to_json(self) -> Any:
        if self.kind == "value":
            return self.number
        if self.kind == "should":
            return [self.number, "should"]
        if self.kind == "none":
            return None
        if self.kind == "unknown":
            return "?"
        return "x"

    @classmethod
    def from_json(cls, v: Any) -> "Limit":
        """Tolerant: anything unreadable becomes ``unknown`` (``?``), never a
        number nobody wrote and never an exception."""
        if v is None:
            return cls.none()
        if isinstance(v, bool):
            return cls.unknown()
        if isinstance(v, (int, float)):
            return cls.value(float(v)) if math.isfinite(float(v)) else cls.unknown()
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("?", "unknown"):
                return cls.unknown()
            if s in ("x", "✕", "unmeasurable"):
                return cls.unmeasurable()
            if s in ("", "-", "–", "none"):
                return cls.none()
            try:
                return cls.value(float(s.replace(",", ".")))
            except ValueError:
                return cls.unknown()
        if isinstance(v, (list, tuple)) and v:
            try:
                n = float(v[0])
            except (TypeError, ValueError):
                return cls.unknown()
            if not math.isfinite(n):
                return cls.unknown()
            return cls.should(n) if (len(v) > 1 and str(v[1]).lower() == "should") \
                else cls.value(n)
        return cls.unknown()


def format_number(x: float) -> str:
    """``2.0``, ``2.5``, ``0.75``: one decimal, two when the second is not
    zero. Decimal POINT, as every number ChromIQ writes elsewhere."""
    s = f"{x:.2f}"
    if s.endswith("0"):
        s = s[:-1]
    return s


def limit_text(limit: Limit) -> str:
    """The table cell: ``2.0``, ``(2.0)`` for a should-limit, ``–``, ``?``, ``✕``."""
    if limit.kind == "value":
        return format_number(limit.number)
    if limit.kind == "should":
        return f"({format_number(limit.number)})"
    if limit.kind == "none":
        return "–"
    if limit.kind == "unknown":
        return "?"
    return "✕"


# ---------------------------------------------------------------------------
# The rows: population × statistic
# ---------------------------------------------------------------------------
#: Row status. ``now``: computed today; ``build``: computed from this release;
#: ``ref``: computable only against a reference file for the printing
#: condition (N-A until one exists); ``unknown``: the population is in a
#: clause ChromIQ does not hold (``?`` for every set that limits it);
#: ``unmeasurable``: ChromIQ cannot evaluate it at all (``✕``; it stays in the
#: table so the user sees what a standard asks that ChromIQ does not do, Knut
#: K2 / D16, and it is a note in the report, never a verdict, D11).
ROW_STATUSES = ("now", "build", "ref", "unknown", "unmeasurable")

GROUP_LABELS: "dict[str, str]" = {
    "substrate":     "Paper",
    "solids":        "Solid colours",
    # Knut, 2026-09-18, asked directly: *"change the heading, 'Control strip' is
    # fine, then the help text explains what that means and the method used to
    # select the patches"*. It said "the standard's own patches" while what
    # ChromIQ detects is the CHART's own declaration, which is the same claim
    # the heading above it was changed for an hour earlier: this file already
    # records that coverage has twice been attributed to a standard that never
    # granted it.
    "control_strip": "Control strip",
    "grey_ramp":     "Grey ramp of the measured chart",
    "all_patches":   "All patches of the measured chart",
    # KNUT, 2026-09-18, ruling on S2w: *"I have already proposed to change the
    # heading from 'Selected patches of the standard's chart' to 'Selected
    # patches of the chart'."* It had to change in the same breath as the two
    # rows under it became computable: giving them ChromIQ's OWN definition of
    # their population while the heading still said "of the standard's chart"
    # is the attributing-coverage-to-a-standard mistake this file already
    # records being made twice, a third time.
    "selected":      "Selected patches of the chart",
    # **THE ONE HEADING IN THIS TABLE THAT NAMES ITS OWN AUTHOR, BECAUSE IT
    # HAS TO.** Every other numeric row here comes from a document somebody
    # else wrote. The two rows under this heading do not: they are computed
    # from the user's own measurements of the user's own prints, no standard
    # defines them, nobody licenses them, and they can be judged for a printer
    # user who holds no document at all. Saying so in the heading is what
    # stops the arrangement claiming otherwise, which is the failure this file
    # already records being made twice by juxtaposition rather than by words.
    "repeatability": "Repeatability, measured by ChromIQ",
    # Knut, 2026-09-22: the two evenness rows became computable, by a method he
    # ruled rather than one a standard publishes, so they leave "Not evaluated
    # by ChromIQ" for a heading of their own. Their help text says whose method
    # it is; the heading only says what the rows are about.
    "evenness":      "Evenness across the sheet",
    "not_evaluated": "Not evaluated by ChromIQ",
}


@dataclass(frozen=True)
class Row:
    id: str
    group: str
    label: str            # English source; display through tr()
    unit: str             # "ΔE00" | "ΔCh" | "ΔH*ab" | "ΔL*" | ""
    status: str
    #: the key of the same statistic in ``report["de00"]`` (the five ChromIQ
    #: statistics keep their old keys so trends and old tests still read)
    metric_key: "str | None" = None
    #: why ChromIQ cannot measure it (``unmeasurable`` rows only); English
    note: str = ""
    #: WHAT THIS ROW MEASURES, in one sentence a printer user can read, and
    #: WHEN CHROMIQ CAN JUDGE A CHART ON IT. Knut, 2026-09-14: *"add an info
    #: help icon, where each help icon describes the metric for that line and
    #: details the conditions used to detect if a chart contains the patches
    #: needed to assess and judge this metric."* English source strings,
    #: displayed through `tr()`; `detect` is left empty on an `unmeasurable`
    #: row, where `note` already says why there is nothing to detect.
    blurb: str = ""
    detect: str = ""
    #: the lever a reader can pull, on a row that CAN be judged. Empty where
    #: there is nothing on the chart to change.
    remedy: str = ""

    def __post_init__(self) -> None:
        assert self.status in ROW_STATUSES, self.status
        assert self.group in GROUP_LABELS, self.group
        assert self.blurb, f"{self.id} has no blurb"
        if self.status == "unmeasurable":
            assert self.note and not self.detect, self.id
        else:
            assert self.detect, f"{self.id} has no detection sentence"
        if self.remedy:
            assert self.status not in ("unmeasurable", "unknown"), self.id


#: The detection conditions, written once because rows share them. Knut,
#: 2026-09-14, asked each row's help icon to *"detail the conditions used to
#: detect if a chart contains the patches needed to assess and judge this
#: metric"*, and to say so plainly where a row has no detection at all.
#:
#: These are the conditions the code really applies, in a user's words. The
#: arithmetic behind each one is in `measurement_report.row_values` and the
#: blocks it calls; `tests/test_every_metric_says_how_it_is_detected.py` holds
#: the two together.
_D_REFERENCE_WHITE = (
    "ChromIQ can judge this row only when the chart carries a colorimetric "
    "reference, which is a file of aim values measured beside the chart, and "
    "the chart has a patch within 12 device units of bare paper. Charts built "
    "from your profile's gamut carry that reference; an ordinary test chart "
    "has no aim for this row and the report says so instead of guessing.")
_D_REFERENCE_SOLIDS = (
    "Two things are needed. The chart has to carry a colorimetric reference, "
    "which is a file of aim values measured beside it. And it has to have a "
    "patch at one or more of the four solid corners: cyan, magenta, yellow, "
    "and the composite black where all three inks are at full.\n\n"
    "A corner counts as present when a patch sits within 12 device units of "
    "it. The row then reports the worst of the corners that were found, not of "
    "all four, so on a chart with only cyan it is a verdict on cyan.\n\n"
    "Charts built from your profile's gamut carry the reference. An ordinary "
    "test chart has no aim for this row.")
_D_REFERENCE_CMY = (
    "ChromIQ can judge this row only when the chart carries a colorimetric "
    "reference and has a patch at one or more of the cyan, magenta and yellow "
    "solid corners, within 12 device units. The row reports the worst of the "
    "corners that were found, not of all three. Charts built from your "
    "profile's gamut carry that reference; an ordinary test chart has no aim "
    "for this row.")
#: **A CHART DECLARES ITS OWN STRIP.** Knut approved this on 2026-09-18
#: (S2w). It replaces a sentence that said this row is never judged, which was
#: true for as long as ChromIQ had no way to be told which patches the strip
#: is. It still holds no standard's published list and still will not guess
#: one; the chart is asked instead.
_D_CONTROL_STRIP = (
    "A chart carries a control strip when it says so itself. ChromIQ holds no "
    "standard's published patch list and will not guess one, so the chart "
    "declares its own: a file beside the chart, named after it with "
    "\".control-strip.json\" on the end, holding the strip's name and the "
    "sample ids that make it up. A CONTROL_STRIP_IDS keyword in the chart's "
    ".ti1 or .ti2, naming the same ids, does the same job.\n\n"
    "ChromIQ then counts how many of those ids are in the measurement and "
    "carry a reference value. At least 8 are needed for the average and the "
    "maximum, because below that an average over the strip says nothing. The "
    "95th percentile needs 20: on a shorter strip its nearest rank is the "
    "worst patch itself, so the row would only repeat the maximum.")
_D_GREY_RAMP = (
    "The chart needs a grey ramp. On most charts a patch counts as grey when "
    "its red, green and blue values are within one unit of each other.\n\n"
    "There have to be at least eight distinct steps of it, it has to reach "
    "white at one end and black at the other, and the patches have to carry "
    "reference values.\n\n"
    "At least eight of those steps also have to be roughly evenly spaced from "
    "black to white: each within 4 % of full scale of where an even spacing "
    "puts it, "
    "so that the steps between the two ends are not bunched together. A "
    "longer ramp is fine; ChromIQ picks the steps that fit.\n\n"
    "Bare paper counts as one of those steps and can be the white end on its "
    "own, but it is left out of the figure itself. The report names whichever "
    "of those is missing.\n\n"
    # K31 (Knut, #182 5801677743, option a): a FROM PROFILE GAMUT chart's
    # neutral AIMS are its grey steps. `measurement_report.grey_balance_block`
    # with `neutral_aims`; the numbers are NEUTRAL_AIM_CHROMA_MAX,
    # GREY_SPACING_TOL and NEUTRAL_AIM_END_REACH.
    "A chart built with FROM PROFILE GAMUT is different. Every patch on it is "
    "printed in the profile's own numbers, so a grey is seldom printed with "
    "equal red, green and blue. On such a chart the grey steps are the "
    "patches whose aim colour is neutral, with a* and b* together less than "
    "1.0 from zero, and each step is placed by the lightness L* of its aim, "
    "on the same scale from 0 to 100. The same rules apply: at least eight "
    "distinct steps, eight of them each within 4 of an even spacing, and a "
    "ramp that reaches within 10 of the lightest and the darkest aim on the "
    "chart. The eight solid corners are not counted as steps.")
_D_ALL_PATCHES = (
    "ChromIQ can judge this row on any VERIFICATION sheet it built, because "
    "every patch carries the colour it was asked for. A run's own profiling "
    "chart is printed raw before a profile exists, so its numbers are shown "
    "for information only and no row on it is judged. A measurement with no "
    "reference values at all is not judged either, and the report says so.\n\n"
    # K31 (Knut, #182 5801677743, sections 5 and 6): `IN_GAMUT_LABELS`.
    "Where the report splits a sheet's colours into those within the "
    "profile's gamut and those beyond it, this row is judged on the colours "
    "within the gamut, and its name then ends in \"within gamut\". The "
    "colours beyond the gamut, and all of them together, are shown in the "
    "Overview for information and are never judged. A chart built with FROM "
    "PROFILE GAMUT is never split, because every colour on it was chosen "
    "inside the gamut.")
_D_WORST5 = (
    "As the rows above, a verification sheet only, and the chart needs at "
    "least twenty patches counted, so that the highest 5 % holds a patch to "
    "average. Where the report separates colours the profile could never "
    "print, the count is of the patches inside the gamut, and that is the "
    "number the report quotes.")
_D_RAMPS = (
    "ChromIQ can judge this row when the chart has a single-ink or grey ramp "
    "with at least three distinct steps between 30 % and 70 % tone value, "
    "spanning at least twenty points of it, and carrying reference values. Any "
    "one of the four axes, red, green, blue or grey, is enough.\n\n"
    # K31 (Knut, #182 5801677743: "Implement rule A"): the grey ramp's
    # spacing rule of K28a, `pick_even_grey_steps(n=RAMP_MIN_STEPS)`.
    "Three of those steps also have to be roughly evenly spaced over the "
    "ramp's own part of the band, from its lowest step to its highest: each "
    "within 4 % of full scale of where an even spacing puts it. It is the "
    "grey ramp's rule, applied to this band, so that three readings bunched "
    "at one end cannot stand for the whole mid-tone range. A ramp with more "
    "steps is fine; ChromIQ picks the steps that fit. The report names the "
    "tone value that no step is near.")
#: **CHROMIQ'S OWN POPULATION, UNDER A HEADING THAT NO LONGER NAMES A
#: STANDARD.** These two rows were never missing a detection method; they were
#: missing the DEFINITION of the patches they are about, which the standards
#: publish as lists ChromIQ does not hold. Knut settled both halves on
#: 2026-09-18: ChromIQ defines the populations, and the group heading above
#: them drops the words "of the standard's chart".
_D_OUTER_GAMUT = (
    "These are the most saturated patches of your own chart. ChromIQ ranks "
    "every patch that carries a reference value by the chroma of that "
    "reference, C*ab, and takes the top quarter of them.\n\n"
    "The row is judged when that quarter holds at least 20 patches, so the "
    "average is not one or two readings. That wants roughly 80 patches with "
    "reference values on the chart. The ranking uses the aim values and not "
    "the measured ones, so the same chart picks the same patches however well "
    "it printed.")
_D_SURFACE_GAMUT = (
    "These are the patches on the surface of the device cube. A patch counts "
    "when at least one of its red, green and blue values is within 2.0 of 0 "
    "or of 100, so it sits on a face, an edge or a corner of everything the "
    "printer can be asked for.\n\n"
    "The row is judged when at least 10 of them carry a reference value. The "
    "cube corners are counted with the rest: they are surface patches, and "
    "they are where a profile has least room.")

#: **AND WHAT TO DO ABOUT IT.** Every other help text in this app ends with a
#: lever a reader can pull; the first version of these thirty stopped at the
#: diagnosis. Basti, 2026-09-14, asked whether the new icons were as friendly
#: and as useful as the app's usual help, and this is the half that was
#: missing. Only rows that CAN be judged get one: on a row that needs a gloss
#: meter there is nothing on the chart to change, and inventing advice would be
#: worse than the silence.
_R_REFERENCE = (
    "Build the verification chart with FROM PROFILE GAMUT on the Create Chart "
    "tab. That chart is made from your own profile and carries the aim values "
    "this row is measured against, so the row can be judged. A chart made any "
    "other way will keep reading N-A here however good the print is.")
_R_GREY_RAMP_DEVICE = (
    "Use a chart with a longer grey ramp: at least eight steps of neutral "
    "grey, running from white through to black and spread evenly between "
    "them. Most of the built-in presets have one. If you are building your own patch set on the Create Chart tab, "
    "add grey steps until there are eight or more.")
#: K31: the lever on a FROM PROFILE GAMUT chart, whose neutrals come from the
#: profile. `gamut_target._neutral_budget` gives about one patch in eight to
#: the neutral block, so a larger chart is the lever there is.
_R_GREY_RAMP_AIMS = (
    "On a chart built with FROM PROFILE GAMUT the grey steps come from the "
    "profile, not from a grey step setting, so build the chart again with "
    "more patches: about one patch in eight is a neutral aim, and a larger "
    "chart carries more of them, spread from the profile's white to its "
    "black.")
_R_GREY_RAMP = _R_GREY_RAMP_DEVICE + "\n\n" + _R_GREY_RAMP_AIMS
_R_ALL_PATCHES = (
    "Nothing needs changing on the chart: any verification sheet ChromIQ "
    "builds can be judged on this row. If it is blank, the measurement is "
    "either the run's own profiling sheet, which is not graded, or a file with "
    "no reference values, and the report says which.")
_R_WORST5 = (
    "Use a chart with at least twenty patches, and remember that colours your "
    "profile cannot print are set aside first, so a small chart of difficult "
    "colours can still fall short. On a chart this small the other four "
    "accuracy rows are still judged.")
_R_RAMPS = (
    "Use a chart with a tone ramp through the mid-tones: three steps between "
    "30 % and 70 % of one single ink, or of grey, spread evenly rather than "
    "bunched together, is enough. The built-in presets have one; a patch set "
    "you build yourself may not. On the Create Chart tab, raise Single "
    "Channel Steps (-s) or Grey Axis Steps (-g) so that the ramp has steps "
    "near the low end, the middle and the high end of 30 to 70 %, then "
    "generate the chart again.")
_R_CONTROL_STRIP = (
    "Declare the strip on the chart. Put a file beside the chart named after "
    "it with \".control-strip.json\" on the end, holding the strip's name and "
    "the list of sample ids that make it up, and make sure the chart really "
    "has those patches: 8 of them for the average and the maximum, 20 for the "
    "95th percentile.")
_R_SURFACE_GAMUT = (
    "Add patches at the edge of the device cube in Create Chart: the solid "
    "inks, their two-ink overprints, and steps that hold one of red, green or "
    "blue at 0 or at 100. Ten such patches carrying reference values is all "
    "this row needs.")
_R_OUTER_GAMUT = (
    "Use a larger chart. The top quarter by chroma has to hold 20 patches, so "
    "the chart needs roughly 80 patches carrying reference values. The "
    "built-in Create Chart presets are well past that; a small patch set you "
    "build yourself may not be.")
#: **THE TWO ROWS THAT ARE CHROMIQ'S OWN.** Both say so in as many words, in
#: the place a reader actually looks, because a row in this table is read
#: against the column it sits under and two of those columns are named after a
#: standard. Neither sentence may be softened into implying that anybody
#: published these.
_D_REPEAT_WITHIN = (
    "ChromIQ can judge this row when your chart asks for the same device "
    "colour more than once on one sheet. Two patches count as repeats of each "
    "other when their red, green and blue values agree to two decimal "
    "places, and a set of them is called a group.\n\n"
    "The row is judged when the sheet carries at least 2 such groups. One "
    "group is one colour, and where a chart repeats anything at all it "
    "usually repeats bare paper and solid black, so a reading taken from one "
    "of those alone would stand for nothing else on the sheet.\n\n"
    "This row is ChromIQ's own. No standard defines it. It needs no reference "
    "values and no second print, so it can be judged on a chart that carries "
    "no aim values at all.")
_D_REPEAT_ACROSS = (
    "ChromIQ can judge this row from the second measurement of a verification "
    "chart onward. Each dated verification of a run is compared with the one "
    "immediately before it, patch by patch, paired by sample id.\n\n"
    "A patch is counted only when both measurements agree about the device "
    "values it was asked for, so a chart that was rebuilt between the two "
    "dates drops out of the comparison instead of being read as the printer "
    "moving. At least 14 patches have to survive that test, because below "
    "that the maximum difference says more about which patches happened to "
    "match than about the printer.\n\n"
    "This row is ChromIQ's own. No standard defines it, and it needs no "
    "reference values, so it can be judged on a chart that carries no aim "
    "values at all.")
_R_REPEAT_WITHIN = (
    "Use a chart that repeats a colour. Most of the built-in Create Chart "
    "presets place a few repeated patches for the instrument to settle on, "
    "and a patch set you build yourself may place none at all. Adding two or "
    "more patches that ask for the same device values, at different places on "
    "the sheet, is all this row needs.")
_R_REPEAT_ACROSS = (
    "Measure the same verification chart a second time, on another sheet or "
    "on another day. Keep the chart itself as it is rather than building a "
    "new one in Create Chart: the comparison counts only patches whose device "
    "values both measurements agree on, so a rebuilt chart starts the series "
    "again instead of extending it.")

#: **EVENNESS ACROSS THE SHEET** (Knut, #182, 2026-09-22). The help text
#: carries the likely causes, which he asked for in the help text AND in the
#: report: *"information on what type of faults may result in uniformity issues
#: need to be mentioned in the help text, but also as notes on the results in
#: the report text"*. The 9, the 75 %, the 500 and the 30 are
#: `measurement_report.EVENNESS_MIN_GRID`, `EVENNESS_MIN_PAGE_COVERAGE`,
#: `EVENNESS_SHUFFLES` and the F1 measurement; `tests/test_evenness_across_the_sheet.py` holds the sentence to
#: the constants.
_EVEN_CAUSES = (
    "An uneven sheet usually has one of these causes: banding from the "
    "printer, a partly blocked or misaligned print head, paper that is not "
    "flat or not the same all over, or, on an instrument that reads whole "
    "strips, the instrument drifting while it reads. The strips are read one "
    "after another, so a drift during the reading shows as a difference "
    "across the strips rather than down them.")
_B_EVEN_PAIRWISE = (
    "Whether the sheet prints the same colour everywhere. Every patch is "
    "compared with its own aim value, the differences are averaged over each "
    "ninth of the page, and this row is the maximum difference between any "
    "two of those nine areas.\n\n" + _EVEN_CAUSES)
_B_EVEN_FROM_MEAN = (
    "The ninth of the page that sits furthest from the sheet as a whole: the "
    "maximum difference between one of the nine areas and the average of all "
    "nine. One area on its own that is off, a blotch, shows here first; a "
    "gradual change from one side to the other shows first in the row "
    "above.\n\n" + _EVEN_CAUSES)
_D_EVENNESS = (
    "ChromIQ can judge these two rows on a verification sheet whose chart "
    "file records where each patch is printed, which every chart ChromIQ lays "
    "out does. Each page is divided into three bands of strips and three "
    "bands of rows, whole strips and rows only, with any remainder in the "
    "middle band, and the same ninth of every page is counted together. Only "
    "pages with at least 9 strips and 9 rows whose patches cover at least "
    "60 % of the page are used, so the chart needs at least one such page. "
    "The share is worked out from the distance between each paper edge and "
    "the first patch, the four margins Create Chart shows as Measured from "
    "Preview.\n\n"
    "Every patch is compared with its own aim value, the same one the colour "
    "accuracy rows use, and the differences are averaged in each of the nine "
    "areas. No patches are matched by brightness or by grey.\n\n"
    # K31 (Knut, #182 5801677743, section 3: "Both texts approved").
    "Which readings are used. Evenness compares the nine areas of this one "
    "sheet with each other, so it uses the readings exactly as the "
    "instrument took them. How the sheet was colour-managed does not matter "
    "here: a colour that prints differently in one corner than in another is "
    "a fault of the printer or the paper either way.\n\n"
    "Some sheets are printed with an intent that makes the paper the white, "
    "and on those the colour accuracy figures are worked out relative to the "
    "paper. On such a sheet ChromIQ moves every aim colour onto the paper by "
    "the same amount instead. The paper's own tint then does not count as "
    "unevenness, and because every aim moves by the same amount, no area of "
    "the page can come out different from another because of it.\n\n"
    "The report also measures the sheet's own noise: it shuffles the patches "
    "across the nine areas 500 times and takes the 95th percentile of what "
    "the same arithmetic reads. A row is judged only when that noise is below "
    "the row's limit. On a typical print this takes about 30 patches in "
    "each area, roughly 270 on a page.\n\n"
    # K31: `IN_GAMUT_LABELS`, the evenness rows among them.
    "Where the report splits a sheet's colours into those within the "
    "profile's gamut and those beyond it, only the patches within the gamut "
    "are counted, and the two names then end in \"within gamut\".\n\n"
    "This method is ChromIQ's own. A standard that limits evenness reads it "
    "its own way, on its own chart.")
_R_EVENNESS = (
    "Use a chart whose pages hold at least 9 strips and 9 rows, with patches "
    "covering at least 60 % of the page, and enough patches that about 30 "
    "land in each ninth of the page. If a metric reads a difference, measure the same sheet "
    "again before looking for a cause, since an instrument that drifts during "
    "a long reading makes the strips read last differ from the first.")

ROWS: "tuple[Row, ...]" = (
    # -- Paper
    Row("substrate_de00_max", "substrate",
        "ΔE00, paper white against the reference paper", "ΔE00", "ref",
        blurb='How far the bare paper of the printed test chart sits from the paper the reference describes. A paper that is bluer, warmer or darker than the aim moves every colour printed on it.',
        detect=_D_REFERENCE_WHITE,
        remedy=_R_REFERENCE),
    Row("substrate_overprinted_de00_max", "substrate",
        "ΔE00, overprinted proofing paper against the production paper", "ΔE00",
        "unmeasurable",
        note="needs the production paper measured as well",
        blurb='Whether the proofing stock, once printed, matches the stock the job will really run on.'),
    Row("substrate_gloss_class", "substrate", "Gloss class of the paper", "",
        "unmeasurable", note="needs a gloss meter or the paper maker's data sheet",
        blurb='Which gloss band the paper falls in. Gloss changes how dark a black can look and how a proof compares with a press sheet.'),
    Row("substrate_fluorescence_class", "substrate",
        "Fluorescence class of the paper", "", "unmeasurable",
        note="needs a brightness reading with and without UV",
        blurb='How much optical brightener the paper carries. Brighteners glow under the ultraviolet in daylight, so the paper can measure and look bluer than it is.'),
    # -- Solid colours
    Row("solids_de00_max", "solids",
        "Maximum ΔE00, solid colours", "ΔE00", "ref",
        blurb='The worst of the four solid ink corners against what they should be. Solids are where an ink is laid down at full strength, so they show the ink itself rather than the profile.',
        detect=_D_REFERENCE_SOLIDS,
        remedy=_R_REFERENCE),
    Row("cmy_solids_dhab_max", "solids",
        "Maximum ΔH*ab, cyan, magenta and yellow solids", "ΔH*ab", "ref",
        blurb='Whether the three chromatic solids drifted in hue, ignoring how light or how saturated they are. A hue shift in a solid is the one error the eye finds hardest to forgive.',
        detect=_D_REFERENCE_CMY,
        remedy=_R_REFERENCE),
    Row("spot_solids_de00_max", "solids",
        "Maximum ΔE00, spot colours", "ΔE00", "unmeasurable",
        note="ChromIQ has no spot-colour workflow",
        blurb='Named brand inks, such as a company colour, against their published book values.'),
    # -- Control strip
    Row("control_strip_de00_avg", "control_strip",
        "Average ΔE00, control strip", "ΔE00", "build",
        blurb='The average colour error over the patches of the control strip on the test chart used: the run of patches a press or a proof is checked on.',
        detect=_D_CONTROL_STRIP,
        remedy=_R_CONTROL_STRIP),
    Row("control_strip_de00_max", "control_strip",
        "Maximum ΔE00, control strip", "ΔE00", "build",
        blurb='The worst single patch of that control strip.',
        detect=_D_CONTROL_STRIP,
        remedy=_R_CONTROL_STRIP),
    Row("control_strip_de00_p95", "control_strip",
        "Maximum ΔE00, control strip, lowest 95 % (95th percentile)", "ΔE00", "build",
        blurb='The error that 95 % of the declared strip stays under, so one bad patch does not decide the result.',
        detect=_D_CONTROL_STRIP,
        remedy=_R_CONTROL_STRIP),
    # -- Grey ramp (K-h)
    Row("grey_balance_neutral_ramp_avg", "grey_ramp",
        "Average ΔCh, grey balance of the grey ramp", "ΔCh", "build",
        blurb='How neutral the greys of the printed test chart are on average: how far each step of the grey ramp sits from having no colour cast at all. Lightness is ignored, only the cast is counted.',
        detect=_D_GREY_RAMP,
        remedy=_R_GREY_RAMP),
    Row("grey_balance_neutral_ramp_max", "grey_ramp",
        "Maximum ΔCh, grey balance of the grey ramp", "ΔCh", "build",
        blurb='The worst single step of the grey ramp. One step with a cast is visible in a photograph even when the average looks healthy.',
        detect=_D_GREY_RAMP,
        remedy=_R_GREY_RAMP),
    # -- All patches (ChromIQ's five, shape A merge with the ISO all-patch rows)
    # **THE FIVE NAMES ARE KNUT'S, IN i1PROFILER'S WORD ORDER WITH THE UNIT**
    # (K28, #182 5795087247, 2026-09-23): *"all metrics in report, in graphs
    # and in Report Limits window, and in all help texts, use the same
    # label/name ... so that there is no confusion"*. These labels ARE that
    # name: the report grid, How to read, the detailed tables, the Overview,
    # the graphs, both limits windows and the notes all read them from here
    # (`tests/test_k28b_one_vocabulary.py`). Before beta 39 the same five
    # numbers had three vocabularies ("All patches, average", "Average ΔE, all
    # patches", "Average, all patches (ΔE00)") and a fourth for a within-gamut
    # graph ("all judged patches").
    Row("all_de00_avg", "all_patches", "Average ΔE00, all patches", "ΔE00", "now",
        metric_key="avg_all",
        blurb='The average colour error over the whole chart. The headline number, and the one to watch over time.',
        detect=_D_ALL_PATCHES,
        remedy=_R_ALL_PATCHES),
    Row("best95_de00_avg", "all_patches", "Average ΔE00, lowest 95 %", "ΔE00",
        "now", metric_key="avg_low95",
        blurb='The average over the lowest 95 % of the patches, with the highest 5 % left out, so a handful of very hard colours cannot hide an otherwise good result.',
        detect=_D_ALL_PATCHES,
        remedy=_R_ALL_PATCHES),
    Row("worst5_de00_avg", "all_patches", "Average ΔE00, highest 5 %", "ΔE00",
        "now", metric_key="avg_high5",
        blurb='How bad the hardest colours are: the average over the highest 5 % alone. This is the row that answers what happens at the edge of what the printer can do.',
        detect=_D_WORST5,
        remedy=_R_WORST5),
    Row("all_de00_max", "all_patches", "Maximum ΔE00, all patches", "ΔE00", "now",
        metric_key="max_all",
        blurb='The single worst patch on the sheet. Useful for finding a misread or a damaged patch as well as a real error.',
        detect=_D_ALL_PATCHES,
        remedy=_R_ALL_PATCHES),
    Row("all_de00_p95", "all_patches", "Maximum ΔE00, lowest 95 % (95th percentile)", "ΔE00",
        "now", metric_key="max_low95",
        blurb='The maximum difference within the lowest 95 %, which is the 95th percentile: the error 95 % of the chart stays under, counted by rank rather than by fitting a curve.',
        detect=_D_ALL_PATCHES,
        remedy=_R_ALL_PATCHES),
    # -- Selected patches of the chart (S2w, Knut 2026-09-18)
    # THE ID KEEPS ITS "226", which came from a standard's 226-patch list this
    # row is no longer about. A run's stored limits and every saved report on
    # disk are keyed by the id; renaming it would silently drop the limit a
    # user set and the verdict a report recorded. The id is not shown anywhere.
    Row("outer_gamut_226_de00_avg", "selected",
        "Average ΔE00, outer-gamut patches", "ΔE00", "build",
        blurb="The average error over the most saturated quarter of the test chart used, the colours at the edge of what the printer can reach.",
        detect=_D_OUTER_GAMUT,
        remedy=_R_OUTER_GAMUT),
    Row("surface_gamut_de00_avg", "selected",
        "Average ΔE00, surface-gamut patches", "ΔE00", "build",
        blurb='The average error over the patches that sit on the outside of the device cube, where a profile has least room.',
        detect=_D_SURFACE_GAMUT,
        remedy=_R_SURFACE_GAMUT),
    Row("ramps_30_70_dl_max", "selected",
        "Maximum ΔL*, single-colour ramps 30 % to 70 %", "ΔL*",
        "build",
        blurb='Whether the mid-tones of each single ink, and of grey, land at the right lightness. This is the part of a ramp the eye reads as contrast.',
        detect=_D_RAMPS,
        remedy=_R_RAMPS),
    # -- Repeatability, measured by ChromIQ
    #
    # TWO ROWS NOBODY ELSE WROTE. They are computed from the user's own
    # measurements of the user's own prints, and they are the only numeric
    # rows in this table that are ChromIQ's rather than a standard's. Both
    # populations are ChromIQ's own definition, both work without a reference
    # file and without a profile, and both say so in their own help text.
    #
    # `repeatability_de00_max`, further down under "Not evaluated by ChromIQ",
    # is NOT these and is deliberately left exactly as it is. That row is a
    # standard's criterion over that standard's own timed protocol; repointing
    # it at a number ChromIQ can compute would attribute these definitions to
    # a document that does not contain them.
    Row("repeat_patches_de00_max", "repeatability",
        "Maximum ΔE00, repeat patches on one sheet", "ΔE00", "build",
        blurb='How far apart the patches of one colour landed where that colour appears more than once on one sheet of the test chart used. No profile and no aim value is in this number: the patches were asked for the same thing, so what separates them is the printer and the instrument together.',
        detect=_D_REPEAT_WITHIN,
        remedy=_R_REPEAT_WITHIN),
    Row("repeat_measurement_de00_max", "repeatability",
        "Maximum ΔE00, the same chart measured again", "ΔE00", "build",
        blurb='Whether the same file prints the same colour on another sheet and on another day. This is the question behind asking whether a printer is steady, and it is answered by measuring the same chart more than once.',
        detect=_D_REPEAT_ACROSS,
        remedy=_R_REPEAT_ACROSS),
    # -- Evenness across the sheet (Knut, #182, 2026-09-22)
    #
    # THE TWO IDS ARE KEPT, as `outer_gamut_226` kept its "226": a run's stored
    # limits, a saved report's verdict and a licence holder's values file are
    # all keyed by the id, and the id is shown nowhere. What changed is what
    # the rows MEAN. Until 2026-09-22 they were ✕, "needs nine readings at set
    # positions on one sheet"; Knut then ruled a method that needs no set
    # positions at all (every patch against its own aim, averaged over nine
    # areas of the page), and named the two numbers: the pairwise maximum for
    # "nine locations", the largest difference from the mean for the other.
    # The first label drops "spread of L*, a*, b*", which was the standards'
    # statistic and is not the one computed here; `docs/design/
    # measurement_report_limits.md` §16 records that a licence holder's figure
    # for this row was written for a different statistic.
    Row("uniformity_sd", "evenness",
        "Maximum ΔE00, between two of the nine sheet areas", "ΔE00", "build",
        blurb=_B_EVEN_PAIRWISE,
        detect=_D_EVENNESS,
        remedy=_R_EVENNESS),
    Row("uniformity_de00_max_from_mean", "evenness",
        "Maximum ΔE00, one sheet area against the whole sheet", "ΔE00",
        "build",
        blurb=_B_EVEN_FROM_MEAN,
        detect=_D_EVENNESS,
        remedy=_R_EVENNESS),
    # -- Not evaluated by ChromIQ (✕ rows; notes in the report)
    Row("macro_uniformity_score", "not_evaluated",
        "Macro-uniformity score", "", "unmeasurable",
        note="a scanned-image method; ChromIQ measures patches, not areas",
        blurb='Banding, mottle and streaks judged over areas of print rather than over patches.'),
    Row("repeatability_de00_max", "not_evaluated",
        "Maximum ΔE00, print to print and day to day", "ΔE00",
        "unmeasurable", note="a timed protocol, not a property of one sheet",
        blurb='Whether the same file prints the same colour today, tomorrow and on the next sheet.'),
    Row("permanence_de00_max", "not_evaluated",
        "Maximum ΔE00, permanence in storage", "ΔE00", "unmeasurable",
        note="needs climate chambers",
        blurb='How far the print moves while it is simply stored.'),
    Row("fading_24h_de00_max", "not_evaluated",
        "Maximum ΔE00, fading in the dark, first 24 hours", "ΔE00", "unmeasurable",
        note="a timed physical test",
        blurb='How much the print changes in its first day in the dark, while the ink is still settling.'),
    Row("light_fastness", "not_evaluated", "Light fastness", "", "unmeasurable",
        note="needs a xenon exposure rig",
        blurb='How well the print holds up under strong light over time.'),
    Row("stabilization_minutes_max", "not_evaluated",
        "Print stabilisation and rub resistance", "", "unmeasurable",
        note="needs the rub apparatus of the standard",
        blurb='How long a print needs before it is stable enough to measure, and whether the surface survives handling.'),
    Row("tone_value_limits", "not_evaluated", "Tone value reproduction limits", "",
        # B8-949: "measures no tone value" sat beside the tone ramp rows,
        # which ChromIQ does judge; what it does not measure is this row's
        # quantity, the tone value (dot area) of the lightest and darkest
        # tones.
        "unmeasurable",
        note=("ChromIQ measures the lightness of tone steps, not the tone "
              "value (dot area) of the lightest and darkest tones this row "
              "limits"),
        blurb='Whether the lightest and darkest tones that should print separately actually do.'),
    Row("measurement_condition", "not_evaluated",
        "Measurement condition (M0, M1, M2) stated and matched", "",
        "unmeasurable",
        note="ArgyllCMS records no measurement condition in the file",
        blurb="Whether the instrument's illumination condition is stated and matches the one the limits assume."),
)

ROW_BY_ID: "dict[str, Row]" = {r.id: r for r in ROWS}
GROUP_ORDER: "tuple[str, ...]" = tuple(dict.fromkeys(r.group for r in ROWS))

#: **"WITHIN GAMUT" IN THE JUDGED NAMES ON A SPLIT SHEET** (K31, Knut, #182
#: 5801677743, answering 5798697107 sections 5 and 6: *"Use version 1
#: everywhere and implement your recommendations"*, *"do as recommended"*).
#: Where a report holds a sheet whose colours were split by the profile's gamut,
#: these seven rows are judged on the within-gamut patches only
#: (`measurement_report.graded_de00`, `evenness_block(only_ids=...)`), and
#: "Average ΔE00, all patches" would then mean the within-gamut figure in
#: Report Results and all patches together in the Overview. So on such a
#: report the judged figures carry "within gamut" in their name, and "all
#: patches" never means two things in one document. English source strings,
#: displayed through `tr()`; `row_name` is the one door.
IN_GAMUT_LABELS: "dict[str, str]" = {
    "all_de00_avg": "Average ΔE00, all patches within gamut",
    "best95_de00_avg": "Average ΔE00, lowest 95 % within gamut",
    "worst5_de00_avg": "Average ΔE00, highest 5 % within gamut",
    "all_de00_max": "Maximum ΔE00, all patches within gamut",
    "all_de00_p95": "Maximum ΔE00, lowest 95 % within gamut (95th percentile)",
    "uniformity_sd":
        "Maximum ΔE00, between two of the nine sheet areas, within gamut",
    "uniformity_de00_max_from_mean":
        "Maximum ΔE00, one sheet area against the whole sheet, within gamut",
}


def row_name(row_id: str, within_gamut: bool = False) -> str:
    """The English name of one row: its `label`, or its within-gamut name
    when *within_gamut* is True and the row is judged on the within-gamut
    patches of a split sheet (`IN_GAMUT_LABELS`). The id itself for an id
    no row carries. Display it through `tr()`."""
    if within_gamut and row_id in IN_GAMUT_LABELS:
        return IN_GAMUT_LABELS[row_id]
    row = ROW_BY_ID.get(row_id)
    return row.label if row is not None else str(row_id)


#: The reasons a FROM PROFILE GAMUT chart's grey steps give (K31), and the
#: grey-ramp reasons of every other chart. Spelled here rather than imported,
#: because `measurement_report` imports this module; a test holds the two
#: spellings together.
GREY_AIM_REASONS = frozenset({"too_few_neutral_aims", "neutral_aims_bunched",
                              "neutral_aims_no_white",
                              "neutral_aims_no_black"})
GREY_DEVICE_REASONS = frozenset({"no_greys", "too_few_steps",
                                 "grey_steps_bunched", "no_white",
                                 "no_black"})


def remedy_for(row_id: str, reason: "str | None" = None) -> str:
    """The lever for one row, as the row's help icon offers it, narrowed to
    the half that fits *reason* where a row has two (K31: the grey rows on a
    FROM PROFILE GAMUT chart and on any other chart). English source."""
    row = ROW_BY_ID.get(row_id)
    if row is None:
        return ""
    if row.remedy == _R_GREY_RAMP:
        if reason in GREY_AIM_REASONS:
            return _R_GREY_RAMP_AIMS
        if reason in GREY_DEVICE_REASONS:
            return _R_GREY_RAMP_DEVICE
    return row.remedy


def rows_in_group(group: str) -> "list[Row]":
    return [r for r in ROWS if r.group == group]


# ---------------------------------------------------------------------------
# The sets
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SetDef:
    id: str
    label: str            # English source; display through tr()
    kind: str             # "chromiq" | "iso" | "custom"
    editable: bool
    parent: "str | None" = None   # custom sets start from their parent's factory
    #: one sentence for the pulldown's tooltip (English source)
    blurb: str = ""


SETS: "tuple[SetDef, ...]" = (
    SetDef("chromiq_default", "ChromIQ default (recommended)", "chromiq", True,
           blurb="ChromIQ's own limits: 2.0 on the averages, 3.0 on the "
                 "maxima. The right choice for checking a profile you built."),
    SetDef("chromiq_tight", "ChromIQ tight", "chromiq", True,
           blurb="Half of ChromIQ default: for critical work where a small "
                 "colour difference matters."),
    SetDef("chromiq_quick", "Quick check", "chromiq", True,
           blurb="Twice ChromIQ default: a quick health check that only a "
                 "clearly drifted printer fails."),
    SetDef("iso_12647_7", "ISO 12647-7:2016 values", "iso", False,
           blurb="The published tolerance values of ISO 12647-7:2016 "
                 "(contract proofs), applied to the chart you printed. "
                 "Read-only."),
    SetDef("iso_12647_8", "ISO 12647-8:2021 values", "iso", False,
           blurb="The published tolerance values of ISO 12647-8:2021 "
                 "(validation prints), applied to the chart you printed. "
                 "Read-only."),
    # THE BLURBS SAY WHAT THE COLUMN REALLY HOLDS, AND TWICE THEY HAVE NOT.
    #
    # They first read "Starts from the ISO 12647-7:2016 values", which was true
    # of the structure and not of the numbers: the data file ships empty, so
    # every cell read ? or – and the column judged nothing.
    #
    # They were then rewritten to "The rows ISO 12647-7:2016 writes a limit
    # over, starting from ChromIQ's own numbers rather than that standard's",
    # and the third adversarial round measured that and found it false in both
    # directions. Four of the eleven rows carrying a number are rows that
    # standard writes no limit over (one of them belongs to the OTHER
    # standard's structure), and fifteen of the twenty-two rows it does write a
    # limit over are empty. Both Custom columns hold the same eleven rows with
    # the same numbers, so the sentence also described two different row sets
    # that are in fact one.
    #
    # Attributing coverage to a standard that does not have it is the same
    # class of claim as denying coverage it does, and neither is ChromIQ's to
    # make. The blurb says what the column IS, and says nothing about which
    # rows any standard limits.
    #
    # AND THE THIRD VERSION WAS FALSE IN THE STATE NOBODY HERE RUNS IN. It read
    # "The starting numbers are ChromIQ's own, not ISO 12647-7:2016's" and "the
    # two editable columns start from the same numbers". Both are true only
    # while the data file is empty. `factory_limits` takes the placeholders
    # "only where the data file supplied no real number, so a licence holder
    # who points ChromIQ at their own file still starts from theirs" -- so with
    # figures supplied, custom-7 starts from the 12647-7 block and custom-8
    # from the 12647-8 block, and the two are not the same numbers at all. The
    # sixth adversarial round drove both states and measured 7 and 5 supplied
    # figures respectively. It is worded for both states now.
    SetDef("custom_iso_12647_7", "Custom ISO 12647-7", "custom", True,
           parent="iso_12647_7",
           blurb="Every metric ChromIQ can measure, for judging against "
                 "figures you set yourself. It starts from the published "
                 "figures of ISO 12647-7:2016 where a licence holder has "
                 "supplied them, and where nobody has, from limits "
                 "researched from industry practice and from ChromIQ's own "
                 "numbers, neither of which is that standard's. Every limit "
                 "in it is yours to change, the rows that start empty "
                 "included."),
    SetDef("custom_iso_12647_8", "Custom ISO 12647-8", "custom", True,
           parent="iso_12647_8",
           blurb="Every metric ChromIQ can measure, for judging against "
                 "figures you set yourself. It starts from the published "
                 "figures of ISO 12647-8:2021 where a licence holder has "
                 "supplied them, and where nobody has, from limits "
                 "researched from industry practice and from ChromIQ's own "
                 "numbers, neither of which is that standard's. Every limit "
                 "in it is yours to change, the rows that start empty "
                 "included."),
)
SET_BY_ID: "dict[str, SetDef]" = {s.id: s for s in SETS}


#: Names that mean "these numbers are somebody's published figures". Matched
#: against a set id and against the label a run stored, and only ever consulted
#: for a set this ChromIQ no longer defines.
_STANDARD_BODY_MARKERS: "tuple[str, ...]" = (
    "iso", "12647", "fogra", "gracol", "swop", "idealliance", "cgats",
)


def applies_a_standard(set_id: "str | None",
                       stored_label: "str | None" = "") -> bool:
    """Whether this set judges with a STANDARD's published figures.

    True for the two read-only ISO columns and ALSO for the Custom columns that
    start from them, and the second half is the point.

    An on-screen round drove the documented route on 2026-09-10: a tester who
    owns the standard puts one number into "Custom ISO 12647-7", the set becomes
    selectable, and the report printed a bold green **PASS** with the sentence
    "Every value this limit set requires was checked and is within its limit."
    No string claimed anything, so the sweep for claim words could not see it:
    the claim was made by JUXTAPOSITION, a column named after a standard beside
    a green PASS with no caveat.

    The caveat on an ISO column is not about licensing and never was. It is
    that a standard's figures are written for that standard's own control strip
    on that standard's own chart, and ChromIQ measures the chart YOU printed.
    Typing the numbers in by hand does not change what they are being applied
    to, so a set derived from one carries exactly the same caveat.

    Until 2026-09-22 that caveat was ALSO carried by the verdict word: such a
    column was capped at COND however well it read. Knut retired the cap that
    day -- *"Most users are just interested in knowing if the measurements
    passed against the criteria set"* -- so the word is now PASS or FAIL and
    this function's answer is what decides whether :data:`STANDARD_CAVEAT` is
    printed. It went from shaping a word to being the whole promise.
    """
    s = SET_BY_ID.get(set_id or "")
    if s is not None:
        if s.kind == "iso":
            return True
        return bool(s.parent) and SET_BY_ID.get(s.parent or "", None) is not None \
            and SET_BY_ID[s.parent].kind == "iso"
    # AN ID WE NO LONGER KNOW IS THE OTHER WAY IN, AND IT WAS OPEN. A run keeps
    # the id and the label of the set it was bound to; when a later ChromIQ no
    # longer defines that id, `set_label` shows the stored label marked
    # "(historical)" and this function used to answer False, so the column read
    # "Custom ISO 12647-7 (historical)" beside a green PASS with no caveat. No
    # string claimed anything; the claim was the arrangement.
    #
    # Judged by NAME, on the id and on whatever label the run stored, because
    # that is all a forgotten set leaves behind. The list is the bodies whose
    # published figures ChromIQ can name at all, so it covers a set that has
    # not been written yet as well as the two that have.
    _hay = f"{set_id or ''} {stored_label or ''}".lower()
    return any(k in _hay for k in _STANDARD_BODY_MARKERS)
SET_IDS: "tuple[str, ...]" = tuple(s.id for s in SETS)
EDITABLE_SET_IDS: "tuple[str, ...]" = tuple(s.id for s in SETS if s.editable)
DEFAULT_SET_ID = "chromiq_default"


def is_known_set(set_id: str) -> bool:
    return set_id in SET_BY_ID


def set_label(set_id: str, stored_label: str = "") -> str:
    """The display label of a set, or the label a run stored when the id is
    no longer known (D23: shown as historical)."""
    s = SET_BY_ID.get(set_id)
    if s is not None:
        return tr(s.label)
    if stored_label:
        return tr("{label} (historical)").format(label=stored_label)
    return tr("{id} (historical)").format(id=set_id or "?")


# ---------------------------------------------------------------------------
# Factory limits
# ---------------------------------------------------------------------------
#: ChromIQ's own numbers. Knut, #182 K4 (2026-09-05) and Q1 (2026-09-06): the
#: default stays 2.0 / 2.0 / 2.0 / 3.0 / 3.0; tight and quick are half and
#: double, "modifiable in the future if needed".
#:
#: THE GREY PAIR IS AN ORDINARY LIMIT AGAIN. It was a SHOULD limit in every
#: ChromIQ set (CH-9), which drew a bracket in three columns that name no
#: standard. Knut, 2026-09-21, agreeing to remove them: *"Remove them, so a
#: bracket only ever appears where a standard is involved, and ChromIQ's own
#: sets have requirements and nothing else. Simpler, and consistent with your
#: 'treat all thresholds the same'."* The numbers are unchanged; only the kind
#: is. See `row_verdict` for the word that went with them.
_CHROMIQ_FACTORY: "dict[str, dict[str, Limit]]" = {
    "chromiq_default": {
        "all_de00_avg": Limit.value(2.0), "best95_de00_avg": Limit.value(2.0),
        "worst5_de00_avg": Limit.value(2.0), "all_de00_max": Limit.value(3.0),
        "all_de00_p95": Limit.value(3.0),
        "grey_balance_neutral_ramp_avg": Limit.value(1.5),
        "grey_balance_neutral_ramp_max": Limit.value(3.0),
        # ChromIQ's own two repeatability rows. Row A takes the number default
        # already puts on an AVERAGE and Row B the one it puts on a MAXIMUM,
        # and the order between them is the point: Row B's population contains
        # Row A's entirely and adds a second print and a second day, so its
        # limit cannot be the tighter of the two. Checked against measurement,
        # not chosen to be tidy: 21 sheets on this machine that a real
        # instrument read and that carry repeat patches have within-sheet
        # maxima from 0.32 to 1.999, median 0.698.
        "repeat_patches_de00_max": Limit.value(2.0),
        "repeat_measurement_de00_max": Limit.value(3.0),
        # EVENNESS ACROSS THE SHEET, Knut 2026-09-22: *"keep 1.5 for pairwise
        # row. largest diff 1.0 I think may be ok"*. The 1.0 was Basti's
        # proposal and awaits Knut's confirmation (§16 of the limits spec).
        # With nine areas the pairwise figure P and the from-the-mean figure D
        # satisfy 1.125 D <= P <= 2 D, so 1.5 and 1.0 make each row catch a
        # fault the other misses: a blotch trips D first, a gradient P first.
        "uniformity_sd": Limit.value(1.5),
        "uniformity_de00_max_from_mean": Limit.value(1.0),
    },
    "chromiq_tight": {
        "all_de00_avg": Limit.value(1.0), "best95_de00_avg": Limit.value(1.0),
        "worst5_de00_avg": Limit.value(1.0), "all_de00_max": Limit.value(1.5),
        "all_de00_p95": Limit.value(1.5),
        "grey_balance_neutral_ramp_avg": Limit.value(1.0),
        "grey_balance_neutral_ramp_max": Limit.value(2.0),
        "repeat_patches_de00_max": Limit.value(1.0),
        "repeat_measurement_de00_max": Limit.value(1.5),
        # NOT half of default, unlike every other row here. Knut, E3
        # (2026-09-23): all three ChromIQ sets carry 1.5 / 1.0, because at
        # 0.75 the sheet's own noise must fall under 0.75 too, and most
        # charts then read N-A on these two.
        "uniformity_sd": Limit.value(1.5),
        "uniformity_de00_max_from_mean": Limit.value(1.0),
    },
    "chromiq_quick": {
        "all_de00_avg": Limit.value(4.0), "best95_de00_avg": Limit.value(4.0),
        "worst5_de00_avg": Limit.value(4.0), "all_de00_max": Limit.value(6.0),
        "all_de00_p95": Limit.value(6.0),
        "grey_balance_neutral_ramp_avg": Limit.value(3.0),
        "grey_balance_neutral_ramp_max": Limit.value(7.0),
        "repeat_patches_de00_max": Limit.value(4.0),
        "repeat_measurement_de00_max": Limit.value(6.0),
        # E3, as in tight above: the same 1.5 / 1.0 as default.
        "uniformity_sd": Limit.value(1.5),
        "uniformity_de00_max_from_mean": Limit.value(1.0),
    },
}

#: Which rows each ISO set writes a limit over. This is the STRUCTURE of the
#: standard (what it regulates), not its numbers; the numbers come from the
#: data file and read ``?`` while that file is empty. Sources: ISO 12647-7:2016
#: Table 2 and 4.3.2 to 4.3.7; ISO 12647-8:2021 Table 1 and 4.2.1 to 4.2.8
#: (the free previews).
_ISO_ROWS: "dict[str, tuple[str, ...]]" = {
    "iso_12647_7": (
        "substrate_de00_max", "substrate_overprinted_de00_max",
        "substrate_gloss_class", "substrate_fluorescence_class",
        "solids_de00_max", "cmy_solids_dhab_max", "spot_solids_de00_max",
        "control_strip_de00_avg", "control_strip_de00_max",
        "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
        "all_de00_avg", "all_de00_p95", "outer_gamut_226_de00_avg",
        "uniformity_sd", "uniformity_de00_max_from_mean",
        "repeatability_de00_max", "permanence_de00_max", "light_fastness",
        "stabilization_minutes_max", "tone_value_limits",
        "measurement_condition",
    ),
    "iso_12647_8": (
        "substrate_de00_max", "substrate_gloss_class",
        "substrate_fluorescence_class", "spot_solids_de00_max",
        "control_strip_de00_avg", "control_strip_de00_p95",
        "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
        "all_de00_avg", "all_de00_p95", "surface_gamut_de00_avg",
        "ramps_30_70_dl_max",
        "uniformity_sd", "uniformity_de00_max_from_mean",
        "macro_uniformity_score", "repeatability_de00_max",
        "permanence_de00_max", "fading_24h_de00_max", "light_fastness",
        "stabilization_minutes_max", "tone_value_limits",
        "measurement_condition",
    ),
}

#: The data file ChromIQ SHIPS (see the module docstring: each set in it is
#: either empty or complete). The environment variable exists so a licence
#: holder can point ChromIQ at their own copy.
ISO_DATA_FILE = "data/compliance_sets/iso12647.json"
ISO_DATA_ENV = "CHROMIQ_COMPLIANCE_ISO_FILE"
_iso_cache: "dict[str, dict[str, Limit]] | None" = None
#: Per set, the rows the USER'S OWN file gave a number for (the file the
#: environment variable names, or the one in :func:`user_values_path`), and
#: never the shipped file's. See :func:`supplied_iso_rows`.
_iso_supplied: "dict[str, frozenset[str]] | None" = None
#: Per set, the rows the SHIPPED file gives a number for. See
#: :func:`shipped_iso_sets`.
_iso_shipped: "dict[str, frozenset[str]] | None" = None

#: THE TWO CUSTOM COLUMNS' STARTING NUMBERS, AND WHERE EACH ONE COMES FROM.
#:
#: There are two sources, and the difference between them is the whole point
#: of this section:
#:
#: * :data:`_CUSTOM_INDUSTRY` — Knut's own researched figures, per column.
#:   Knut, #182, 2026-09-21: *"I have filled in the json file with the
#:   threshold limits I have manually set, based on findings from research
#:   online of industry practice and reasoned limits from the industry, which
#:   are independently set by various actors in the industry, companies or
#:   communities, not based on ISO standard values. I would like these to be
#:   set as default for the two Custom ISO 12647 columns."*
#: * :data:`_CUSTOM_CHROMIQ_FILL` — ChromIQ's own numbers, kept for the rows
#:   his research puts no figure on for that column, so that the invariant he
#:   asked for on 2026-09-11 still holds: every metric ChromIQ can measure
#:   arrives with a limit to be judged against.
#:
#: **NEITHER SOURCE IS A STANDARD'S PUBLISHED VALUE, AND NEITHER MAY BECOME
#: ONE.** No value of ISO 12647-7 or ISO 12647-8 is in this file and none may
#: be (`docs/design/issue_182_answers.md`, the owner's standing rule). A
#: licence holder supplies the real figures through the file
#: ``CHROMIQ_COMPLIANCE_ISO_FILE`` names, and where that file HAS a number for
#: a row, the Custom set takes it and none of this is used
#: (:func:`factory_limits`). That a column is NAMED after a standard while
#: holding numbers that are not that standard's is exactly the attribution the
#: window's own description has had to be corrected for four times, so
#: :func:`custom_default_counts` exists to let that description be GENERATED
#: from what is actually loaded rather than asserted by hand.
#:
#: A row appears in either table only when ChromIQ can actually measure it,
#: ``now`` / ``build`` / ``ref``. A number on a row ChromIQ cannot compute is a
#: limit nothing is ever judged against, which is the shape of "a column that
#: checked nothing said PASS"; :func:`factory_limits` enforces it and a test
#: pins it. Knut's file carries figures on rows ChromIQ cannot judge today as
#: well; those are deliberately NOT here, and belong with the detection that
#: makes each of those rows computable.

#: Knut's researched industry figures, keyed by the PARENT ISO set id, so each
#: Custom column starts from the block he filled in for it. His file gives a
#: figure per standard's own structure, so a row one column carries and the
#: other does not is his structure, not an omission.
_CUSTOM_INDUSTRY: "dict[str, dict[str, Limit]]" = {
    "iso_12647_7": {
        "substrate_de00_max": Limit.value(2.0),          # ΔE00
        "solids_de00_max": Limit.value(2.0),             # ΔE00
        "cmy_solids_dhab_max": Limit.value(2.5),         # ΔH*ab
        "control_strip_de00_avg": Limit.value(2.0),      # ΔE00
        "control_strip_de00_max": Limit.value(4.0),      # ΔE00
        "grey_balance_neutral_ramp_avg": Limit.value(1.5),   # ΔCh
        "grey_balance_neutral_ramp_max": Limit.value(3.0),   # ΔCh
        "all_de00_avg": Limit.value(2.0),                # ΔE00
        "all_de00_p95": Limit.value(4.0),                # ΔE00
        "outer_gamut_226_de00_avg": Limit.value(4.0),    # ΔE00
    },
    "iso_12647_8": {
        "substrate_de00_max": Limit.value(2.0),          # ΔE00
        "control_strip_de00_avg": Limit.value(2.0),      # ΔE00
        "control_strip_de00_p95": Limit.value(4.0),      # ΔE00
        "grey_balance_neutral_ramp_avg": Limit.value(1.5),   # ΔCh
        "grey_balance_neutral_ramp_max": Limit.value(3.0),   # ΔCh
        "all_de00_avg": Limit.value(2.0),                # ΔE00
        "all_de00_p95": Limit.value(4.0),                # ΔE00
        "surface_gamut_de00_avg": Limit.value(4.0),      # ΔE00
        "ramps_30_70_dl_max": Limit.value(2.0),          # ΔL*
    },
}

#: ChromIQ's own numbers, for the rows Knut's research leaves to us. Shared by
#: both columns, because these are not a standard's structure but ChromIQ's own
#: statistics and the rows the other column's block covers.
#:
#: > **Only ChromIQ default's own three numbers are used: 1.5, 2.0 and 3.0.**
#: > The five all-patch rows and the two grey rows take exactly what ChromIQ
#: > default puts on them. Every other row here takes 2.0 or 3.0, reused
#: > because it is the right order of magnitude for a ΔE00, a ΔCh, a ΔH*ab or a
#: > ΔL* and for no other reason.
#:
#: That rule still governs THIS table and a test still pins it. It does not
#: govern :data:`_CUSTOM_INDUSTRY`, whose numbers are Knut's and are researched.
_CUSTOM_CHROMIQ_FILL: "dict[str, Limit]" = {
    # the five ChromIQ statistics, exactly ChromIQ default's numbers
    "all_de00_avg": Limit.value(2.0),
    "best95_de00_avg": Limit.value(2.0),
    "worst5_de00_avg": Limit.value(2.0),
    "all_de00_max": Limit.value(3.0),
    "all_de00_p95": Limit.value(3.0),
    # the grey pair, ChromIQ default's own numbers
    "grey_balance_neutral_ramp_avg": Limit.value(1.5),
    "grey_balance_neutral_ramp_max": Limit.value(3.0),
    # the rows ChromIQ default puts no limit on
    "substrate_de00_max": Limit.value(3.0),          # ΔE00
    "solids_de00_max": Limit.value(3.0),             # ΔE00
    "cmy_solids_dhab_max": Limit.value(2.0),         # ΔH*ab
    # A BRACKET IN A COLUMN NAMED AFTER A STANDARD CLAIMED SOMETHING ChromIQ
    # does not know. This row was marked a recommendation on the reading that
    # ISO 12647-8:2021 4.2.7 is a *should*; the number beside it is ChromIQ's
    # own figure, not the standard's, so the bracket said "ISO 12647-8
    # calls this a recommendation" over a figure ISO never wrote. Knut,
    # 2026-09-21: *"Then the thresholds that use a bracket, ex. '(3,00)',
    # should not have a bracket, since it is not a 'recommended'/'should' type
    # metric."* A licence holder's own file may still mark it "should".
    "ramps_30_70_dl_max": Limit.value(2.0),          # ΔL*
    # THE FIVE ROWS S2w MADE COMPUTABLE (Knut, 2026-09-18).
    "control_strip_de00_avg": Limit.value(2.0),      # ΔE00
    "control_strip_de00_max": Limit.value(3.0),      # ΔE00
    "control_strip_de00_p95": Limit.value(3.0),      # ΔE00
    "outer_gamut_226_de00_avg": Limit.value(2.0),    # ΔE00
    "surface_gamut_de00_avg": Limit.value(2.0),      # ΔE00
    # CHROMIQ'S OWN TWO REPEATABILITY ROWS. Neither standard writes a limit
    # over either row, so both read "–" in the two read-only ISO columns, and
    # that is the honest cell: those columns hold a standard's published values
    # and no standard published these. Knut's research puts no figure on them
    # either, so ChromIQ's own numbers stand.
    "repeat_patches_de00_max": Limit.value(2.0),      # ΔE00
    "repeat_measurement_de00_max": Limit.value(3.0),  # ΔE00
    # EVENNESS ACROSS THE SHEET, computable since 2026-09-22: ChromIQ
    # default's own two numbers, by the rule this table follows. Knut's values
    # file may carry figures of his own for these rows; nothing here reads it
    # (§16 asks him whether he wants those as the Custom starting numbers).
    "uniformity_sd": Limit.value(1.5),                  # ΔE00
    "uniformity_de00_max_from_mean": Limit.value(1.0),  # ΔE00
}


def custom_defaults(parent_set_id: str) -> "dict[str, Limit]":
    """The starting numbers of the Custom column whose parent is *parent_set_id*.

    Knut's researched figure for a row where he set one, ChromIQ's own number
    where he did not. Merged here rather than stored merged, so that
    :func:`custom_default_sources` cannot drift from what this returns.
    """
    out = dict(_CUSTOM_CHROMIQ_FILL)
    out.update(_CUSTOM_INDUSTRY.get(parent_set_id, {}))
    return out


def custom_default_sources(parent_set_id: str) -> "dict[str, str]":
    """Where each starting number of that Custom column came from.

    ``"industry"`` for one of Knut's researched figures, ``"chromiq"`` for one
    of ChromIQ's own. Same keys as :func:`custom_defaults`, always.
    """
    industry = _CUSTOM_INDUSTRY.get(parent_set_id, {})
    return {rid: ("industry" if rid in industry else "chromiq")
            for rid in custom_defaults(parent_set_id)}


def custom_default_counts(set_id: str) -> "dict[str, int]":
    """How many of a Custom column's limits come from where, COUNTED.

    Keys: ``industry`` (Knut's researched figures), ``chromiq`` (ChromIQ's own
    numbers), ``supplied`` (a licence holder's own values file answered the
    row, so neither default is used), ``total`` (limit-bearing rows).

    This is what lets the Report limits window's description of its columns be
    generated instead of written: a sentence built from these counts cannot go
    on saying "starts from ChromIQ's own numbers" after the numbers changed,
    nor claim a standard's figures for a column that holds none. Returns all
    zeroes for a set that is not a Custom one.
    """
    s = SET_BY_ID.get(set_id)
    zero = {"industry": 0, "chromiq": 0, "supplied": 0, "total": 0}
    if s is None or s.kind != "custom" or not s.parent:
        return zero
    sources = custom_default_sources(s.parent)
    # ASK THE FILE, DO NOT INFER FROM THE NUMBER. Deciding "supplied" by
    # comparing the limit with the default would miscount the one case that
    # matters most: a licence holder whose own figure happens to EQUAL a
    # default would be reported as not having supplied it, and the window
    # would then name our sources and not theirs.
    supplied = supplied_iso_rows(s.parent)
    out = dict(zero)
    for rid in limit_bearing(factory_limits(set_id)):
        out["total"] += 1
        if rid in supplied:
            out["supplied"] += 1
        else:
            out[sources.get(rid, "chromiq")] += 1
    return out

#: What went wrong with the file the ENVIRONMENT VARIABLE names, as
#: ``(kind, detail)`` pairs. See :func:`iso_data_problems`.
_iso_problems: "list[tuple[str, str]] | None" = None

#: The spellings that MEAN "unknown" in the file. Anything else that comes out
#: of :meth:`Limit.from_json` as ``unknown`` was not understood, which is a
#: different thing and the one a user needs telling about.
_MEANS_UNKNOWN = ("?", "unknown")

#: The set ids the file may carry.
ISO_SET_IDS = ("iso_12647_7", "iso_12647_8")


#: The name the user's own values file has in :func:`user_values_path`.
ISO_USER_FILE = "iso12647.json"


def user_values_path() -> Path:
    """Where a licence holder's own values live on this machine.

    **THE ENVIRONMENT VARIABLE IS A DEVELOPER'S DOOR AND WAS THE ONLY ONE.**
    A shipped ChromIQ carries no `scripts/` folder to write the template with,
    and a variable exported in a shell never reaches an app launched from
    Finder or the Dock, so the feature existed and nobody outside this checkout
    could use it. It is a known file beside the presets now, and the Report
    limits window puts it there with an ordinary file dialog.
    """
    from core.platform_paths import compliance_dir

    return compliance_dir() / ISO_USER_FILE


def install_user_values(src: "str | Path") -> Path:
    """Copy the user's filled-in file into place. Returns where it landed.

    It is COPIED and not linked: the values then survive the user tidying up
    their Downloads folder, which is where a file they just edited usually is.
    """
    import shutil

    dst = user_values_path()
    dst.parent.mkdir(parents=True, exist_ok=True)
    json.loads(Path(src).read_text(encoding="utf-8"))   # refuse rubbish early
    shutil.copyfile(str(src), str(dst))
    reset_iso_cache()
    return dst


def forget_user_values() -> bool:
    """Go back to the empty shipped file. True when something was removed."""
    dst = user_values_path()
    if not dst.is_file():
        return False
    dst.unlink()
    reset_iso_cache()
    return True


def _bundled_iso_path() -> Path:
    """The values file ChromIQ ships. One function, so a test can stand a
    fixture in for the shipped file without touching the real one."""
    return resource_path(ISO_DATA_FILE)


def _same_file(a: Path, b: Path) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


def _iso_data_path() -> Path:
    override = os.environ.get(ISO_DATA_ENV, "").strip()
    if override:
        return Path(override)
    own = user_values_path()
    return own if own.is_file() else _bundled_iso_path()


def _numeric_cells(doc: Any) -> "dict[str, dict[str, Limit]]":
    """The rows of each known set that carry a NUMBER, and nothing else.

    Used for the shipped file underneath a user's own, where a cell that is
    not a number (a ``null`` left from the template, a ``?``) must not blank
    a figure ChromIQ ships.
    """
    out: "dict[str, dict[str, Limit]]" = {}
    if not isinstance(doc, dict):
        return out
    for sid in ISO_SET_IDS:
        cells = doc.get(sid)
        if not isinstance(cells, dict):
            continue
        out[sid] = {rid: lim for rid, lim in
                    ((rid, Limit.from_json(v)) for rid, v in cells.items()
                     if rid in ROW_BY_ID)
                    if lim.is_numeric}
    return out


def _is_the_users_own_file() -> bool:
    """True when the file is one the user supplied, either way in.

    An empty set in the bundled file is one ChromIQ does not ship, which is a
    normal state and not something to report. The user's own file is the only
    one whose emptiness is a mistake.
    """
    if os.environ.get(ISO_DATA_ENV, "").strip():
        return True
    return user_values_path().is_file()


def _looks_unreadable(raw: Any) -> bool:
    """A cell that came out ``unknown`` without asking to be unknown."""
    if isinstance(raw, str) and raw.strip().lower() in _MEANS_UNKNOWN:
        return False
    return Limit.from_json(raw).kind == "unknown"


def iso_values_template(set_id: "str | None" = None) -> str:
    """A file a LICENCE HOLDER can fill in, in the Report limits window's order.

    Knut asked, 2026-09-19: *"Can you list the limits set by the standards in a
    post, in a table, and in the same sequence of the metrics in the Report
    Limits window?"* The values themselves cannot come from us: they are the
    content of a paid standard, this repository published those tables once
    already by accident, and DIN's written answer of 2026-09-18 puts shipping
    the numbers on the *Wiedergabe* side of the line and prices it at 50 % of
    the standard's purchase price.

    What CAN be given is everything except the numbers, which is most of what
    the question was really after: **which rows each standard writes a limit
    over, in the order the window draws them, ready to be filled in from a copy
    the reader owns.** The structure of a standard is not its content, and
    `_ISO_ROWS` has been in this file, in the open, since the sets existed.

    So: run `python scripts/iso_values_template.py`, fill the nulls in from
    your own copy, and point `CHROMIQ_COMPLIANCE_ISO_FILE` at the result. The
    numbers stay on the machine of somebody licensed to have them, which is the
    only place they can be.

    A row is written as ``null`` for "no number yet". A filled row is a number,
    or ``[number, "should"]`` for a recommendation rather than a requirement.
    Rows the standard writes no limit over are simply absent, which is what
    makes this a template and not a guess at a table.
    """
    import json as _json

    want = (set_id,) if set_id else ("iso_12647_7", "iso_12647_8")
    order = {r.id: i for i, r in enumerate(ROWS)}
    labels = {r.id: (r.label, r.unit, r.status) for r in ROWS}
    out: "dict[str, Any]" = {
        "_readme": (
            "Tolerance values for ChromIQ's two ISO limit sets, filled in "
            "from your own copy of the standard. Put this file in place from "
            "the Report limits window, under 'Reference values...', or point "
            "CHROMIQ_COMPLIANCE_ISO_FILE at it. A row is "
            "a number, or [number, \"should\"] for a recommendation. A number "
            "you give takes the place of any figure ChromIQ ships for that "
            "row; leave a row null and ChromIQ goes on showing what it shows "
            "for it now, its own figure where it ships one and '?' where it "
            "does not. The rows are in the order the Report limits window "
            "draws them."),
        "_rows": {},
    }
    for sid in want:
        rows = [r for r in _ISO_ROWS.get(sid, ()) if r in order]
        rows.sort(key=lambda r: order[r])
        out[sid] = {r: None for r in rows}
        for r in rows:
            lab, unit, status = labels[r]
            out["_rows"][r] = (f"{lab} [{unit}]" if unit else lab) + (
                "" if status in ("now", "build", "ref")
                else "  (ChromIQ cannot judge this row today)")
    return _json.dumps(out, indent=2, ensure_ascii=False) + "\n"


def _load_iso_numbers() -> "dict[str, dict[str, Limit]]":
    """``{set_id: {row_id: Limit}}`` from the data file; unreadable → empty.

    **AND IT SAYS WHAT IT COULD NOT READ.** `Limit.from_json` is deliberately
    tolerant and turns anything it cannot parse into ``?``, which is the same
    thing the empty bundled file produces. A licence holder who pointed
    ChromIQ at a file in the wrong shape therefore saw a window identical to
    the one they would see with no file at all, with no message anywhere: the
    one route offered to them could not tell them they had got it wrong. The
    most likely wrong shape is not exotic, either. It is
    ``{"kind": "value", "number": 2.5}``, which is what ChromIQ's own
    `limits_to_json` writes into `meta.json`, so it is the shape a user is
    most likely to copy.

    Problems are only collected for the file the ENVIRONMENT VARIABLE names.

    **THE SHIPPED FILE IS THE GROUND, AND A USER'S OWN FILE IS LAID OVER IT.**
    While the shipped file was empty the two were never both in play, and "read
    the user's file instead" was the whole rule. Once a set ships complete
    (#182 S-2, §23 of the limits record), reading the user's file INSTEAD would
    take every shipped figure away from a licence holder who supplied three
    rows of the other set. So a user's NUMBER wins its row, a row their file
    leaves null keeps the shipped figure, and a row neither answers reads
    ``?`` exactly as before. A path that IS the shipped file (the tests and
    drivers force the variable at it) is read once, as the shipped file.
    """
    global _iso_cache, _iso_problems, _iso_supplied, _iso_shipped
    if _iso_cache is not None:
        return _iso_cache
    out: "dict[str, dict[str, Limit]]" = {}
    problems: "list[tuple[str, str]]" = []
    mine = _is_the_users_own_file()
    path = _iso_data_path()
    bundled = _bundled_iso_path()
    from_bundle = _same_file(path, bundled)
    if from_bundle:
        shipped_doc = None             # read below, as `doc`
    else:
        try:
            shipped_doc = json.loads(bundled.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("shipped compliance data file %s unreadable (%s)",
                        bundled, exc)
            shipped_doc = {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("compliance data file %s unreadable (%s); ISO cells read ?",
                    path, exc)
        if mine:
            problems.append(("unreadable", str(exc)))
        doc = {}
    if not isinstance(doc, dict):
        if mine:
            problems.append(("not_an_object", type(doc).__name__))
        doc = {}
    unreadable_cells: "list[str]" = []
    unknown_rows: "list[str]" = []
    for set_id, cells in doc.items():
        if set_id.startswith("_"):
            continue
        if not isinstance(cells, dict):
            if mine and set_id in ISO_SET_IDS:
                problems.append(("set_not_an_object", set_id))
            continue
        # A null is "not filled in yet" (the template writes one per row), so
        # it is left out rather than read as "no limit".
        out[set_id] = {rid: Limit.from_json(v) for rid, v in cells.items()
                       if rid in ROW_BY_ID and v is not None}
        if not mine or set_id not in ISO_SET_IDS:
            continue
        for rid, raw in cells.items():
            if rid not in ROW_BY_ID:
                unknown_rows.append(rid)
            elif _looks_unreadable(raw):
                unreadable_cells.append(rid)
    # IS THE SET NAMED, not "did any of its rows survive". These are different
    # questions and the answer to the second was being given under the name of
    # the first: `out[sid]` is built by a comprehension that drops every row id
    # ChromIQ does not know, so a file whose top-level key IS `iso_12647_7`,
    # holding rows that are all misspelled, was told "The file names no limit
    # set ChromIQ knows. It needs a top-level key iso_12647_7" — two lines
    # above a sentence listing the misspelled rows, which proves the key was
    # found. A licence holder following that instruction would rename a key
    # that is already right. Driven and photographed by an adversarial round.
    if mine and not problems and not any(
            isinstance(doc, dict) and sid in doc for sid in ISO_SET_IDS):
        problems.append(("no_known_set", ", ".join(ISO_SET_IDS)))
    if unreadable_cells:
        problems.append(("unreadable_cells", ", ".join(sorted(
            dict.fromkeys(unreadable_cells)))))
    if unknown_rows:
        problems.append(("unknown_rows", ", ".join(sorted(
            dict.fromkeys(unknown_rows)))))
    for kind, detail in problems:
        log.warning("compliance data file %s: %s (%s)", path, kind, detail)
    if from_bundle:
        shipped = _numeric_cells(doc)
        supplied: "dict[str, frozenset[str]]" = {}
    else:
        shipped = _numeric_cells(shipped_doc)
        supplied = {sid: frozenset(rid for rid, lim in out.get(sid, {}).items()
                                   if lim.is_numeric)
                    for sid in ISO_SET_IDS}
        for sid, cells in shipped.items():
            merged = dict(cells)
            for rid, lim in out.get(sid, {}).items():
                if lim.is_numeric or rid not in merged:
                    merged[rid] = lim
            out[sid] = merged
    _iso_cache = out
    _iso_problems = problems
    _iso_supplied = supplied
    _iso_shipped = {sid: frozenset(cells) for sid, cells in shipped.items()}
    return out


def supplied_iso_rows(set_id: str) -> "frozenset[str]":
    """The rows of *set_id* that a USER'S OWN values file gave a number for.

    Never the shipped file's rows. This is the question a Custom column asks
    before it starts from a standard's figure instead of its own default:
    §2a's order of precedence names "a licence holder's own values file", and
    the shipped values are not that. The Custom columns start from Knut's
    researched figures whatever ChromIQ ships (Knut, 2026-09-21), so shipping a
    set changes the read-only column beside them and nothing in them.
    """
    if _iso_supplied is None:
        _load_iso_numbers()
    return (_iso_supplied or {}).get(set_id, frozenset())


def shipped_iso_sets() -> "tuple[str, ...]":
    """The ISO sets whose values ship WITH ChromIQ, in window order.

    A set counts when the shipped file carries a number on at least one row
    ChromIQ can judge, which in practice means a set that ships complete
    (``tests/test_compliance_sets.py`` holds the file to "empty or complete").
    Empty while nothing is shipped, which is what the file holds until the
    owner's go-ahead; every sentence that says what ChromIQ ships asks this
    rather than assuming either state.
    """
    if _iso_shipped is None:
        _load_iso_numbers()
    got = _iso_shipped or {}
    return tuple(sid for sid in ISO_SET_IDS
                 if any(ROW_BY_ID[rid].status in ("now", "build", "ref")
                        for rid in got.get(sid, ())))


def iso_data_problems() -> "list[tuple[str, str]]":
    """What is wrong with the user's own limits file, ``(kind, detail)`` each.

    Empty when there is no such file, or when it was understood. The kinds are
    a closed set the window turns into sentences; a kind it does not know is
    still shown, with its detail, rather than dropped.
    """
    if _iso_cache is None:
        _load_iso_numbers()
    return list(_iso_problems or [])


def iso_data_path_text() -> str:
    """The path the user's values came from, or "" when they supplied none."""
    env = os.environ.get(ISO_DATA_ENV, "").strip()
    if env:
        return env
    own = user_values_path()
    return str(own) if own.is_file() else ""


def reset_iso_cache() -> None:
    """For tests that swap the data file."""
    global _iso_cache, _iso_problems, _iso_supplied, _iso_shipped
    _iso_cache = None
    _iso_problems = None
    _iso_supplied = None
    _iso_shipped = None


def factory_limits(set_id: str) -> "dict[str, Limit]":
    """Every row's factory limit for *set_id* (a Custom set: its parent's).

    An ``unmeasurable`` row that a set limits reads ``✕`` whatever the set's
    number is: the cell says "the standard asks this, ChromIQ cannot measure
    it" (D16), and such a row never carries a verdict.
    """
    s = SET_BY_ID.get(set_id)
    if s is None:
        return {r.id: Limit.none() for r in ROWS}
    source = s.parent or s.id
    out: "dict[str, Limit]" = {}
    if source in _CHROMIQ_FACTORY:
        table = _CHROMIQ_FACTORY[source]
        for r in ROWS:
            out[r.id] = table.get(r.id, Limit.none())
    else:
        numbers = _load_iso_numbers().get(source, {})
        touched = set(_ISO_ROWS.get(source, ()))
        for r in ROWS:
            if r.id not in touched:
                out[r.id] = Limit.none()
            elif r.status == "unmeasurable":
                out[r.id] = Limit.unmeasurable()
            else:
                out[r.id] = numbers.get(r.id, Limit.unknown())
        # A CUSTOM SET ARRIVES WITH A NUMBER ON EVERY ROW CHROMIQ CAN MEASURE.
        # Knut, 2026-09-11, asked for the two Custom columns to be usable:
        # every cell of both read ``?`` or ``–``, so the columns judged nothing.
        # The read-only ISO columns keep exactly what the data file gives them,
        # which is nothing today; only the Custom sets take the defaults, and
        # only where the data file supplied no real number, so a licence
        # holder who points ChromIQ at their own file still starts from theirs.
        #
        # THE DEFAULTS ARE PER COLUMN, because Knut's researched figures are.
        # `source` is the PARENT id here, which is exactly the key his file
        # and `_CUSTOM_INDUSTRY` are written against.
        #
        # `custom_defaults` holds only measurable rows, and the status test
        # below is the second lock on the same door: a ``?`` on an ``unknown``
        # row means ChromIQ does not know WHICH patches the row is about, so a
        # number there would be a limit nothing is ever compared with.
        #
        # AND ONLY A USER'S OWN FILE ANSWERS FOR A CUSTOM ROW, never the
        # shipped one. §2a's first source is "a licence holder's own values
        # file"; the figures ChromIQ ships for a standard belong in the
        # read-only column beside this one, and Knut asked for his researched
        # figures as the Custom columns' starting numbers. So a shipped
        # figure is replaced here by the default, exactly as "?" is.
        if s.kind == "custom":
            mine = supplied_iso_rows(source)
            for rid, lim in custom_defaults(source).items():
                row = ROW_BY_ID.get(rid)
                if row is None or row.status not in ("now", "build", "ref"):
                    continue
                if rid in mine and out.get(rid, Limit.none()).is_numeric:
                    continue            # the user's own file answered this row
                out[rid] = lim
            for rid, lim in list(out.items()):
                if lim.is_numeric and rid not in mine \
                        and rid not in custom_defaults(source):
                    out[rid] = Limit.unknown()
    return out


def effective_limits(set_id: str, overrides: "dict | None") -> "dict[str, Limit]":
    """Factory limits with the user's Preferences overrides applied.

    *overrides* is ``{set_id: {row_id: number | None}}`` (None = the user set
    "no limit"). Only editable sets take overrides; a number on a row whose
    factory limit is a *should* stays a should. Unknown row ids are ignored.
    """
    limits = factory_limits(set_id)
    s = SET_BY_ID.get(set_id)
    if s is None or not s.editable or not overrides:
        return limits
    mine = overrides.get(set_id) or {}
    if not isinstance(mine, dict):
        return limits
    for rid, v in mine.items():
        row = ROW_BY_ID.get(rid)
        if row is None or row.status in ("unmeasurable", "unknown"):
            continue
        if v is None:
            limits[rid] = Limit.none()
            continue
        try:
            n = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(n) or n <= 0.0:
            limits[rid] = Limit.none()          # the spin box's "–" (CH-21)
            continue
        limits[rid] = Limit.should(n) if limits[rid].is_should else Limit.value(n)
    return limits


def limit_bearing(limits: "dict[str, Limit]") -> "dict[str, Limit]":
    """The rows a report is actually judged on: numeric limits on rows ChromIQ
    can compute (``now`` / ``build`` / ``ref``)."""
    return {rid: lim for rid, lim in limits.items()
            if lim.is_numeric
            and ROW_BY_ID[rid].status in ("now", "build", "ref")}


def selectable_set_ids(overrides: "dict | None") -> "list[str]":
    """The sets the report window may offer: those with at least one
    limit-bearing row (CH-11: an empty column is never a choice)."""
    return [s.id for s in SETS if limit_bearing(effective_limits(s.id, overrides))]


def limits_to_json(limits: "dict[str, Limit]") -> "dict[str, Any]":
    return {rid: lim.to_json() for rid, lim in limits.items()}


def set_marks_recommendations(set_id: "str | None") -> bool:
    """Whether a limit of *set_id* may be a RECOMMENDATION ("should").

    **K3 (Knut on beta 34).** "Recommended rather than required" is a
    standard's distinction, and the note that explains it says "The standard
    calls this metric recommended". ChromIQ's own sets are no standard and
    mark no row that way any more, but copies bound while they still did keep
    the flag: Knut's run on "Quick check" printed that note about a standard
    nobody had chosen. So a set of the ``chromiq`` family never carries one,
    whatever an older copy says; every other set, and an id this build does
    not know, keeps what it was given.
    """
    d = SET_BY_ID.get(str(set_id or ""))
    return d is None or d.kind != "chromiq"


def limits_from_json(doc: "dict | None",
                     set_id: "str | None" = None) -> "dict[str, Limit]":
    """A run's or a report's stored copy back into limits. Unknown row ids are
    KEPT (a report from a newer ChromIQ must not lose them; CH-20).

    With *set_id*, a "should" the set may not carry (see
    `set_marks_recommendations`) is read as the plain limit it is. The number
    is untouched and nothing on disk is rewritten."""
    out: "dict[str, Limit]" = {}
    plain = set_id is not None and not set_marks_recommendations(set_id)
    if isinstance(doc, dict):
        for rid, v in doc.items():
            lim = Limit.from_json(v)
            if plain and lim.is_should and lim.is_numeric:
                lim = Limit.value(lim.number)
            out[str(rid)] = lim
    return out


def is_edited(values: "dict[str, Limit]", set_id: str,
              overrides: "dict | None") -> bool:
    """True when a run's stored copy differs from its set's effective values on
    any limit-bearing row (CH-15: derived, never trusted to a flag)."""
    if not is_known_set(set_id):
        return False
    ref = effective_limits(set_id, overrides)
    for rid in set(ref) | set(values):
        # **A ROW ONE SIDE HAS NEVER HEARD OF IS NOT AN EDIT EITHER**, and
        # this is the same fault as the ``?`` carve-out below, arriving
        # through a different door. `limits_to_json` writes EVERY row of the
        # column, a removed limit included (it goes to disk as ``null``), so a
        # row the user took away is PRESENT and reads ``none``. A row that is
        # ABSENT was never in the column at all: the build that bound the run
        # did not define it.
        #
        # MEASURED, 2026-09-22: the two repeatability rows added on
        # 2026-09-21 are absent from every copy bound before that day, so
        # `a.is_numeric != b.is_numeric` fired on both and EVERY run bound by
        # any earlier ChromIQ read "(edited)" -- on screen, in the PDF, and
        # stamped into every report the build saved (`stamp_verdict(...,
        # edited=lim.edited)`). Nobody had edited anything. The mirror case is
        # covered by the same clause and for the same reason: CH-20 keeps a
        # row id a LATER ChromIQ wrote, and a row this set does not define
        # cannot be an edit OF this set.
        if rid not in ref or rid not in values:
            continue
        a, b = ref.get(rid, Limit.none()), values.get(rid, Limit.none())
        # A STORED ``?`` IS NOT AN EDIT, AND CANNOT BE ONE. Nothing a user can
        # do produces an ``unknown`` limit: the spin box writes a number or
        # "–", and `effective_limits` turns an override into ``value``,
        # ``should`` or ``none``. A ``?`` on a run's copy is what the SET gave
        # it on the day it was bound, for a row that build could not judge.
        #
        # MEASURED, 2026-09-18: without this, the five rows S2w made
        # computable (B8-397) turned every run bound to a Custom column before
        # that release into an "edited" run, because its stored ``?`` now
        # faces a number. The user had edited nothing. The other direction is
        # untouched: a number stored where the set now says ``?`` is a real
        # edit and still reads as one.
        if b.kind == "unknown":
            continue
        if a.is_numeric != b.is_numeric:
            return True
        if a.is_numeric and b.is_numeric and abs(a.number - b.number) > 1e-9:
            return True
    return False


# ---------------------------------------------------------------------------
# The two decision rules
# ---------------------------------------------------------------------------
def same_limits(a: "dict[str, Limit]", b: "dict[str, Limit]") -> bool:
    """True when two stored copies are the SAME yardstick.

    **`is_edited`'S TWIN, AND IT EXISTS BECAUSE THE TWO DISAGREED.** That
    predicate asks whether a run's copy differs from its set; this one asks
    whether two copies differ from each other. They must answer the same
    question the same way, because the window derives "(edited)" from one and
    decides which measurements share a document from the other, and a user who
    is told two runs are not edited and then sees half their measurements
    silently dropped has been told two different things about one fact.

    MEASURED, 2026-09-22, one project, two profile runs, both bound to ChromIQ
    default, neither showing "(edited)": the document kept **11 measurements
    and left 11 out**, and printed *"This report covers 11 of the 30
    measurements recorded for this project"* with nothing on the page saying
    why. The two copies differed only in ways ChromIQ itself had changed
    underneath the user, on 2026-09-21: the two repeatability rows did not
    exist in the older copy, and the grey balance pair was stored there as a
    recommendation and here as a plain limit.

    Knut ruled on it the same day: *"I would say one and the same yardstick ...
    It does not matter if one report uses a metric as recommendation ('should')
    and the other report uses required ('shall')."*

    The rules are `is_edited`'s in spirit and in two of three cases exactly,
    with ONE deliberate difference measured by challenge round 38: `is_edited`
    skips a stored ``?`` only on the RUN's copy, because a number stored where
    the set now says ``?`` is a real edit of that set. Here there is no set and
    no "other direction": two run copies are being compared with each other, so
    a ``?`` on EITHER side is the same absence of a judgement and is skipped
    both ways. The reasons for the other two are as written there:

    * **a row ABSENT from either side is not a difference.** `limits_to_json`
      writes every row of a column, a removed limit included, so a row the user
      took away is PRESENT and reads ``none``; a row that is absent was never
      defined by the build that bound that copy.
    * **a stored ``?`` is not a difference**, because nothing a user can do
      produces one: it is what the set gave that row on the day it was bound.
    * **``should`` versus ``shall`` is not a difference**, only the number is.
      That is Knut's sentence above, and it is why this compares `is_numeric`
      and the value rather than the kind.
    """
    for rid in set(a) | set(b):
        if rid not in a or rid not in b:
            continue
        x, y = a[rid], b[rid]
        if x.kind == "unknown" or y.kind == "unknown":
            continue
        if x.is_numeric != y.is_numeric:
            return False
        if x.is_numeric and y.is_numeric and abs(x.number - y.number) > 1e-9:
            return False
    return True


def row_verdict(limit: Limit, value: "float | None", graded: bool) -> "str | None":
    """The word for one row of one column, or None when the cell is not a
    verdict at all (a ``?`` or ``✕`` limit, or a ``–`` limit with no value).

    CH-3, recorded in docs/design/measurement_report_limits.md (no "not
    recorded" case here: a
    report without a recorded verdict is graded live by its caller) and
    CH-20 (a ``–`` row with no value is blank, not INFO).
    """
    if limit.kind in ("unknown", "unmeasurable"):
        return None
    if limit.kind == "none":
        return INFO if value is not None else None
    if value is None:
        return N_A
    if not graded:
        return INFO
    if float(value) <= float(limit.number) + 1e-9:
        return PASS
    # KNUT RETIRED COND AS A ROW WORD, 2026-09-21 (#182): *"it might be better
    # to standardise on all metrics being tested against a threshold shows as
    # FAIL or PASS (always, also for the standards), and the COND term is
    # retired, all tests that fail or pass are handled equally"*, and nine
    # minutes later, withdrawing the special aggregation he had first asked
    # for: *"all thresholds tested against are treated the same, so there is
    # no need to have special handling of the results of a metric with
    # 'should' … If the test is applied the report shall show the result as is,
    # and the overall result follows as normal."*
    #
    # His reasoning is the part worth keeping: outside the ISO sets a
    # recommended row is simply another test, so a third word carries no
    # information there and costs understanding everywhere. The
    # recommended-versus-required distinction survives as `Limit.is_should`,
    # the bracket in the table cell, and the per-metric NOTE -- see
    # `measurement_report.NOTE_RECOMMENDED_LIMIT`. Only the word goes.
    #
    # COND itself is NOT deleted: it is still an Overall word, because a
    # report saved before 4.3.0 carries it on rows and `set_summary` reports
    # a column holding such a row as COND. That is the ONLY way left in: the
    # other one, an ISO column capped at COND, went on 2026-09-22 when Knut
    # retired the cap in favour of the note. See `STANDARD_CAVEAT`.
    return FAIL


#: Appended to a SAVED verdict when the set it was judged against applies a
#: standard's published figures. The saved word itself is kept, because the
#: design record has Knut ruling that a run keeps its values and verdicts; what
#: may not stand is the word ALONE under a standard's name, because ChromIQ
#: promised a rights holder in writing that it never claims conformance. A
#: challenge round found a saved PASS printed green and unqualified under
#: "Custom ISO 12647-7", in the window and in the PDF.
#: **IT IS IN TWO HALVES BECAUSE ONE PAGE COULD NOT CARRY BOTH.** The
#: one-page summary (report type T1) branches away before the block that
#: prints this note, so while an ISO-named column was capped at COND the WORD
#: carried the qualification there. The cap went on 2026-09-22 and T1 needed
#: the note instead. Measured on the PDF's own A4 layout, the same maths
#: `test_the_one_page_summary_prints_on_one_page` uses, on a run bound to
#: Custom ISO 12647-7:
#:
#:     whole caveat   900 px used, 52 px spare   <- under the 60 px rule
#:     first half     885 px used, 67 px spare
#:     second half    870 px used, 82 px spare
#:     the general not-certification line it replaces   885 px, 67 px spare
#:
#: T1 takes the SECOND half, and that is not an arbitrary trim: its summary
#: sentence one section above already says "This limit set holds a standard's
#: published values applied to your chart; it is not a test against that
#: standard", which is the first half. The second half is the part Knut asked
#: for and the part nothing else on that page says.
#:
#: Split rather than paraphrased so there is only ONE wording to translate and
#: only one to keep true. `tr()` is a whole-string lookup, so a sentence
#: sliced out of a longer key at runtime would reach every language as
#: English; each half is its own key.
#:
#: **WHAT WAS JUDGED, AGAINST WHAT, AND NO CONFORMANCE CLAIM (re-challenge R2
#: of beta 39, #2).** The first half said the limits "may differ from that
#: standard's published values"; since §23 the read-only ISO columns HOLD
#: those values, so in the one state where a read-only ISO column prints this
#: note the sentence was false. The second half said a result inside the
#: limits indicates that "the print would likely meet the standard", which is
#: a hedged conformance claim in text handed to a customer (K18), beside a
#: Report limits window that says a report can never say a print conforms.
#: Both halves now state what the report did: the values measured on the
#: printed test chart were compared with this set's limits. Knut's "not proof"
#: and "as long as the limits stay within the standard's" (K18, §19.1) stay.
STANDARD_CAVEAT_APPLIED = ("This limit set is named after a standard. Its "
                           "limits were applied to the values measured on the "
                           "printed test chart with ChromIQ's own metrics, "
                           "not to that standard's own chart and control "
                           "strip with its own methods, so this is not a test "
                           "against that standard.")
STANDARD_CAVEAT_PROOF = ("A PASS means that the measured values are inside "
                         "these limits. It is not proof that the print meets "
                         "the standard, and where these limits are wider "
                         "than the standard's own it says nothing about the "
                         "standard.")
#: The whole note, for the report types that have room for it. NOT a catalogue
#: key itself: `tr()` is applied to each half and the two are joined, or the
#: join would reach every language as English.
STANDARD_CAVEAT = STANDARD_CAVEAT_APPLIED + " " + STANDARD_CAVEAT_PROOF


#: The column summary's sentences (English source; the extractor sweeps this
#: dict, review F6). Filled with {checked} {total} {failed} {cond} {not_computed}.
SUMMARY_REASONS: "dict[str, str]" = {
    "empty": "This limit set defines no limits.",
    # Knut, #182 12b (2026-09-09): showing INFO for a profiling run's report is
    # right, "since the measurements are not a verification run and will most
    # often not fall within set accuracy threshold values. In this case the
    # report output must explain this." The old sentence said the sheet was not
    # graded and stopped there, which explains nothing: a reader who sees big
    # numbers and no verdict is left to guess whether something is wrong.
    "not_graded": "This sheet is not graded, so its numbers are shown for "
                  "information only. It was measured to build a profile rather "
                  "than to check one, and a profiling measurement is expected "
                  "to fall outside the accuracy limits. That is normal here, "
                  "and it is not a fault.",
    # #182 D28, report type T4. The sentence above names a reason that is only
    # true of a PROFILING sheet, and T4 is a deliberate choice about a
    # verification measurement: telling such a reader the sheet "was measured
    # to build a profile" would be false. Same word, INFO, different reason.
    "record_type": "This is a Printing record, which sets down what was "
                   "printed and measured and judges none of it. The numbers "
                   "are shown for information only.",
    # FOUND BUILDING T3, AND REACHABLE TODAY. A column where NOTHING could be
    # checked, and where every row that is missing is a recommendation rather
    # than a requirement, fell through every clause to PASS — under a sentence
    # that says "Every value this limit set requires was checked", with nothing
    # checked at all. T3 shows two bracketed grey rows and nothing else, so it
    # meets that state on the first chart without an 8-step grey ramp, which is
    # most of them; but a 3-patch measurement reaches it in the full report too.
    "nothing_checked": "The test chart used supplied none of the values this "
                       "limit set puts a limit on, so there is nothing to "
                       "judge. The rows above say what is missing.",
    # …AND "NOTHING WAS CHECKED" HAS TWO CAUSES, WHICH THE FIRST SENTENCE
    # ANSWERED AS ONE. An adversarial round drove a chart WITH a nine-step grey
    # ramp: both grey rows carried real numbers, both over their limits, and
    # both read INFO because nobody recorded how the sheet was printed (CH-17).
    # Nothing was checked, and the chart had supplied every value, so the
    # sentence above was simply untrue and sent the reader to Create Chart to
    # add patches that are already there.
    # "THE ROWS ABOVE SHOW WHAT WAS MEASURED" WAS ALSO FALSE. The detailed
    # figures are opt-in and off by default, so on the ordinary page those
    # numbers appear nowhere at all. The sentence points at the note that is
    # always printed instead.
    "nothing_graded": "None of the values this limit set puts a limit on was "
                      "graded on this sheet, so there is nothing to judge. "
                      "The note below says why each was left ungraded.",
    "fail": "{failed} of {checked} values checked are over this limit set's limits.",
    # KNUT, 2026-09-22: *"it is obvious that the list is missing, and thus
    # shall be included, where there are metrics that are not checked against
    # the selected measurements to be included in the report."* So the promise
    # is now CONDITIONAL and is kept where it is made. It used to be
    # unconditional, which meant a column with nothing unchecked also said the
    # unchecked values were listed below: measured on T3, *"3 of 3 values
    # checked ... and the values not checked are listed below."*
    "iso": "{checked} of {total} values checked, all within this limit set's "
           "values. This limit set is named after a standard; it is not a test "
           "against that standard.",
    "iso_with_unchecked": "{checked} of {total} values checked, all within "
                          "this limit set's values. This limit set is named "
                          "after a standard; it is not a test against that "
                          "standard. The {not_computed} values not checked are "
                          "listed below.",
    "iso_with_one_unchecked": "{checked} of {total} values checked, all within "
                              "this limit set's values. This limit set is "
                              "named after a standard; it is not a test "
                              "against that standard. The one value not "
                              "checked is listed below.",
    # …AND THE ONE-PAGE SUMMARY'S OWN TWO, which have no list to point at.
    # That page used to drop the unchecked values altogether, so a Custom ISO
    # summary read "12 of 20 values checked, all within this limit set's
    # values." and said nothing about the other 8 (round B before beta 37,
    # M1), where ChromIQ's own sets say how many could not be worked out.
    # `MeasurementReportDialog._one_page_summary` is the only reader.
    "iso_partial_page": "{checked} of {total} values checked, all within "
                        "this limit set's values; the other {not_computed} "
                        "could not be worked out from this measurement. This "
                        "limit set is named after a standard; it is not a "
                        "test against that standard.",
    "iso_partial_page_one": "{checked} of {total} values checked, all within "
                            "this limit set's values; the one other value "
                            "could not be worked out from this measurement. "
                            "This limit set is named after a standard; it is "
                            "not a test against that standard.",
    "cond_both": "{checked} of {total} values checked, none over a required "
                 "limit; {not_computed} not computed and {cond} over a "
                 "recommended value.",
    "cond_missing": "{checked} of {total} values checked, none over a required "
                    "limit; {not_computed} not computed on this chart.",
    "cond_recommended": "{checked} of {total} values checked, none over a "
                        "required limit; {cond} over a recommended value.",
    "pass": "Every value this limit set requires was checked and is within its limit.",
    # …AND THAT SENTENCE WAS FALSE WHENEVER A COLUMN REACHED PASS WITH A ROW
    # UNCHECKED. Driven end to end on a first verification: "overall PASS,
    # checked 7, total 9, not_computed 2" printed under "Every value this
    # limit set requires was checked". It contradicted itself inside one
    # dict, on report type T1, which carries no row table and so could not be
    # corrected by anything else on the page, and it went to disk with every
    # report saved.
    #
    # KNUT WIDENED WHEN THAT HAPPENS, 2026-09-21, amending §15.5: *"Not
    # Applicable must not be counted as a fail, so the overall verdict should
    # show PASS, not COND, if all others pass … When all other metrics PASS,
    # that N-A is not applicable, thus not relevant for the verdict, thus
    # overall verdict becomes PASS (or FAIL if some metric fails)."* So an
    # N-A row of ANY kind now reaches this branch, not just the two
    # repeatability rows a carve-out had exempted, and the sentence cannot
    # say anything about WHICH rows were left over. It says the count, and it
    # says the thing Knut's ruling turns on: an unanswerable row is not a
    # failure. Which rows, and why, is the numbered note on each N-A cell.
    #
    # Singular and plural in full, never "(s)" (CLAUDE.md). The WORDING is
    # proposed, not settled: §15.5 is Knut's.
    "pass_partial": "{checked} of {total} values checked, all within this "
                    "limit set's limits. The other {not_computed} could not "
                    "be worked out from this measurement, and a value that "
                    "could not be worked out is not counted as a failure.",
    "pass_partial_one": "{checked} of {total} values checked, all within this "
                        "limit set's limits. The one other value could not be "
                        "worked out from this measurement, and a value that "
                        "could not be worked out is not counted as a failure.",
}


def recorded_reason(reason: str, checked: int, total: int,
                    not_computed: int) -> str:
    """The sentence to print for a summary READ BACK OFF DISK.

    **A SAVED VERDICT IS THE RECORD. A SAVED SENTENCE IS A RENDERING.** Knut's
    rule is that a run keeps its values and its verdicts, so the word and the
    counts a report was saved with are never recomputed. The REASON is not one
    of those: it is prose generated from the counts at the moment of saving,
    and a build that generated it wrongly wrote the wrong prose into every file
    it saved.

    That happened, and this is the residue of B8-690. Up to 4.3.0-beta.29 a
    column whose only unanswered rows were the two repeatability rows reached
    PASS carrying ``"pass"`` -- *"Every value this limit set requires was
    checked and is within its limit."* -- beside a recorded ``not_computed``
    of 2. The live path was corrected; the files already on disk were not, and
    `_column_summary` replays a recorded summary verbatim. Measured on a clean
    first verification saved the way the app saves one: the one-page summary
    printed that sentence in the window and in the PDF under ``checked 7,
    total 9, not_computed 2``.

    So a recorded reason that claims completeness its own recorded counts deny
    is replaced by the sentence today's code would have written for those
    counts. Nothing else is touched: the word, the counts and the file are the
    record. Any other reason is returned exactly as it was saved.
    """
    if reason != SUMMARY_REASONS["pass"] or int(not_computed) <= 0:
        return reason
    return (SUMMARY_REASONS["pass_partial_one"] if int(not_computed) == 1
            else SUMMARY_REASONS["pass_partial"])


@dataclass(frozen=True)
class Summary:
    word: str
    checked: int          # limit-bearing rows that produced PASS/FAIL/COND
    total: int            # limit-bearing rows
    failed: int
    conditional: int
    not_computed: int     # limit-bearing rows that read N-A
    reason: str           # English source sentence; display through tr()


#: Every reason that means "INFO, because nothing here was judged". The
#: footnote under the results table is chosen by EXACT EQUALITY on the reason
#: string, and a second ungraded reason arriving silently dropped that footnote
#: once already, so the set is named here rather than spelled out at the two
#: places that ask.
def is_ungraded_reason(reason: str) -> bool:
    return reason in (SUMMARY_REASONS["not_graded"],
                      SUMMARY_REASONS["record_type"])


#: Reasons that have to appear as TEXT under the results table, because the
#: word above them cannot be accounted for from the table itself.
#:
#: An adversarial round read the saved PDFs back and found the third one
#: missing: `nothing_checked` is the whole user-facing payload of the
#: false-PASS fix, and it reached only the Overall cell's `title=`, which is a
#: tooltip and which no PDF page carries. That is the SAME fault the comment in
#: `_column_summary` records being fixed twice before, arriving a third time
#: inside the fix that named it.
#:
#: A graded column's ordinary sentence ("5 of 7 values checked…") is not here
#: on purpose: its numbers are the table the reader is already looking at.
_FOOTNOTE_REASONS = ("not_graded", "record_type", "nothing_checked",
                     "nothing_graded")


def reason_needs_the_footnote(reason: str) -> bool:
    """Whether this Overall reason must be printed under the table."""
    return reason in tuple(SUMMARY_REASONS[k] for k in _FOOTNOTE_REASONS)


#: **ROWS WHOSE N-A IS NOT A SHORTFALL IN THE CHART.**
#:
#: **THIS SET NO LONGER TOUCHES ANY VERDICT.** It was built to exempt two rows
#: from `set_summary`'s completeness arithmetic. Knut then ruled the general
#: case on 2026-09-21 -- an N-A never demotes a column, whatever row it is on
#: -- so the arithmetic it was carved out of is gone and the carve-out with
#: it. What is left is the job the set turned out to be doing all along, which
#: is not about verdicts at all: deciding which of two MESSAGES a row may
#: appear under. Both of those messages promise something about the CHART
#: ("add those patches in Create Chart", "Not computed on this chart"), and
#: nothing can be added to a chart to answer whether it has been measured
#: twice. `_mismatch_text` and `_not_computed` are the two callers.
#:
#: The original reasoning, kept because it is what put these two rows here:
#:
#: `set_summary` used to demote a column to COND when a REQUIRED row read N-A,
#: on the reading that the set asked for something and did not get it. That is
#: right for every row the rule was written for: a chart either has a grey ramp
#: or the user can go and get one, so a missing answer is a shortfall.
#:
#: It is NOT right for ChromIQ's own two repeatability rows, and measuring it
#: is how that was found. Row B compares a measurement with the one before it,
#: so it is N-A on every FIRST measurement of a chart, which is the ordinary
#: state of most reports anybody has. Left in the general rule, a user who
#: measured a verification sheet once would read COND instead of PASS purely
#: because ChromIQ cannot yet say whether the printer repeats, and a clean
#: report would have been demoted by the arrival of a row that asks a question
#: no single sheet can answer. Row A is the same shape: roughly half the
#: charts ChromIQ ships repeat a colour and half do not.
#:
#: So these two rows declare that their population is conditional. The row is
#: still shown, still reads N-A, and still carries its own reason sentence;
#: only the COLUMN's completeness arithmetic left it out. That arithmetic is
#: gone; see the head of this comment for what the set still decides, and
#: `docs/design/measurement_report_limits.md` §15.5, which is awaiting
#: confirmation.
POPULATION_MAY_BE_ABSENT: "frozenset[str]" = frozenset({
    "repeat_patches_de00_max",
    "repeat_measurement_de00_max",
})


def set_summary(rows: "list[tuple]", *, set_is_iso: bool,
                graded: bool, ungraded_reason: str = "") -> Summary:
    """The column's one word, with the numbers a reader needs beside it.

    *rows* is ``[(limit, word)]`` for every row of the column, words from
    :func:`row_verdict`, or ``[(limit, word, row_id)]`` where the caller knows
    which row each pair came from. The id is optional and only ever used to
    apply :data:`POPULATION_MAY_BE_ABSENT`; a caller that passes pairs gets
    exactly the behaviour it always got. Rules (CS §3.3 as amended by CH-9,
    CH-21, CH-22, and §15):

    * no limit-bearing row → N-A ("this limit set defines no limits");
    * a sheet that is not graded (drift check, profiling measurement) → INFO;
    * any FAIL → FAIL;
    * an ISO column reads PASS or FAIL like any other. It was capped at COND
      until 2026-09-22, when Knut retired the cap and moved what it carried
      into :data:`STANDARD_CAVEAT`, which is printed below the table for
      every column applying a standard. Its summary sentence still says the
      values are applied to your chart rather than tested against the
      standard;
    * any COND → COND. Since 2026-09-21 no LIVE row can read COND --
      `row_verdict` never returns it -- so this clause now fires only for a
      report saved before that day, whose stored rows still carry the word;
    * **an N-A NEVER demotes a column, whatever row it is on.** Knut,
      2026-09-21, amending §15.5: *"Not Applicable must not be counted as a
      fail, so the overall verdict should show PASS, not COND, if all others
      pass. I say, a metric that is not applicable should not have verdict
      conditional because COND does not indicate which of the verdicts cause
      the COND."* See `POPULATION_MAY_BE_ABSENT` for what this replaced;
    * else PASS.
    """
    bearing = [(r[0], r[1], (r[2] if len(r) > 2 else None))
               for r in rows if r[0].is_numeric]
    total = len(bearing)
    R = SUMMARY_REASONS
    # "NOTHING WAS JUDGED" OUTRANKS "THERE WERE NO LIMITS", and the two used to
    # be the other way round. A report saved before the limits were recorded
    # has no limit-bearing row, so an UNGRADED document about it answered
    # "This limit set defines no limits" — true, and the wrong thing to tell
    # somebody who chose a report that judges nothing. The `not graded` clause
    # now comes first and the empty-set clause sits below it, where it still
    # answers every graded column exactly as before.
    failed = sum(1 for _l, w, _r in bearing if w == FAIL)
    cond = sum(1 for _l, w, _r in bearing if w == COND)
    not_computed = sum(1 for _l, w, _r in bearing if w == N_A)
    checked = sum(1 for _l, w, _r in bearing if w in (PASS, FAIL, COND))
    if not graded:
        return Summary(INFO, checked, total, failed, cond, not_computed,
                       ungraded_reason or R["not_graded"])
    if total == 0:
        return Summary(N_A, 0, 0, 0, 0, 0, R["empty"])
    if checked == 0:
        # WHICH of the two: did the chart supply nothing, or was nothing
        # graded? `not_computed` counts the bearing rows that read N-A, which
        # is exactly "the chart could not supply this".
        # A verdict is a statement about measured values. With none of them
        # measured there is no statement to make, and PASS would be a claim
        # about a chart nobody checked. N-A is what the five words already use
        # for "not computed", and the clause above it, "no limit-bearing row",
        # is the same idea one step earlier.
        return Summary(N_A, 0, total, 0, cond, not_computed,
                       R["nothing_checked"] if not_computed == total
                       else R["nothing_graded"])
    if failed:
        return Summary(FAIL, checked, total, failed, cond, not_computed, R["fail"])
    # **AN N-A NEVER DEMOTES A COLUMN.** This used to count the REQUIRED rows
    # that read N-A and turn the column COND for them, with two rows exempted
    # by name. Knut generalised it on 2026-09-21: *"a metric that is not
    # applicable should not have verdict conditional because COND does not
    # indicate which of the verdicts cause the COND … When all other metrics
    # PASS, that N-A is not applicable, thus not relevant for the verdict,
    # thus overall verdict becomes PASS (or FAIL if some metric fails)."*
    # So there is no arithmetic here at all any more, and no list of rows to
    # keep in step with one: the count is reported beside the word and the
    # cell carries a numbered note saying why it could not be worked out.
    # **THE ISO CAP IS GONE, ON KNUT'S RULING OF 2026-09-22**, and what it used
    # to carry now lives in the note. He asked for it in these words: *"The
    # note is sufficient. Most users are just interested in knowing if the
    # measurements passed against the criteria set, and we do not supply
    # charts that are defined by a standard ... ChromIQ's results are only
    # indications that results that PASS likely fulfil the standard ... It is
    # not proof that results fulfil the standard. The report text notes should
    # explain this detail."*
    #
    # **WHAT THE CAP WAS ALSO DOING, so nobody removes the replacement by
    # accident.** `tests/test_a_custom_iso_column_carries_the_same_caveat.py`
    # exists because a challenge round found a saved green PASS, unqualified,
    # under a column named "Custom ISO 12647-7". Its own words: *"the claim was
    # made by JUXTAPOSITION: a column named after a standard, a green PASS, and
    # no caveat. That is precisely what ChromIQ promised a rights holder in
    # writing it would never do."* The cap was what prevented that
    # juxtaposition. `STANDARD_CAVEAT` now prevents it instead, and
    # `measurement_report_dialog` already prints that note for EVERY column
    # applying a standard, live or saved, which is why the word could go
    # without the promise going with it.
    #
    # **THE COND CLAUSE STAYS ABOVE THE ISO ONE**, and it was below it for the
    # first hour of this change. Every `iso*` sentence ends "all within this
    # limit set's values", so an ISO column holding a row that reads COND --
    # over a RECOMMENDED value, which only a report saved before 2026-09-21
    # can still carry -- would have been handed PASS under a sentence that
    # denies the row exists. The cap used to hide that: it returned COND for
    # the whole column whatever the rows said. Removing it exposed the
    # ordering, so the ISO branch now answers only what the non-ISO branch
    # would have answered PASS.
    if cond:
        # no "0 over a recommended value" clauses (text review)
        key = ("cond_both" if (cond and not_computed)
               else "cond_missing" if not_computed else "cond_recommended")
        return Summary(COND, checked, total, failed, cond, not_computed, R[key])
    # `failed` is 0 on this line -- the FAIL clause above returns -- so the
    # word here is PASS and not a choice. A FAIL under a standard's name keeps
    # `R["fail"]`, which claims nothing, and the caveat note below the table
    # is printed for EVERY column applying a standard whatever its word.
    if set_is_iso:
        key = ("iso" if not not_computed
               else "iso_with_one_unchecked" if not_computed == 1
               else "iso_with_unchecked")
        return Summary(PASS, checked, total, failed, cond, not_computed, R[key])
    if not_computed:
        # PASS, and not a claim that everything was checked. See the two
        # `pass_partial` sentences for what reaches this line and why.
        return Summary(PASS, checked, total, failed, cond, not_computed,
                       R["pass_partial_one"] if not_computed == 1
                       else R["pass_partial"])
    return Summary(PASS, checked, total, failed, cond, not_computed, R["pass"])


def summary_text(s: Summary) -> str:
    """The summary's sentence, translated and filled."""
    return tr(s.reason).format(checked=s.checked, total=s.total,
                               failed=s.failed, cond=s.conditional,
                               not_computed=s.not_computed)


# ---------------------------------------------------------------------------
# The two old settings keys → the five rows (the schema-23 migration reads this)
# ---------------------------------------------------------------------------
#: The old "average" threshold judged the three average rows, the old
#: "maximum" threshold the two maximum rows.
OLD_AVG_ROWS: "tuple[str, ...]" = ("all_de00_avg", "best95_de00_avg", "worst5_de00_avg")
OLD_MAX_ROWS: "tuple[str, ...]" = ("all_de00_max", "all_de00_p95")


def legacy_pair(limits: "dict[str, Limit]") -> "tuple[float, float]":
    """``(avg, max)`` for readers of the old ``pass_thresholds`` block: the
    all-patch average and the all-patch maximum, or the factory 2.0 / 3.0."""
    a = limits.get("all_de00_avg")
    m = limits.get("all_de00_max")
    return (float(a.number) if a is not None and a.is_numeric else 2.0,
            float(m.number) if m is not None and m.is_numeric else 3.0)
