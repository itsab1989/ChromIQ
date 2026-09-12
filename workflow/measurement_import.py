"""Filing a measurement made somewhere else into a run of an open project.

WHAT THIS IS FOR. A person prints a ChromIQ chart, measures it in i1Profiler or
on an i1iSis, and wants the readings back. Until now every route decided where
they went by WHERE THE FILE WAS: a measurement sitting on the Desktop made a
brand-new project, and the project the person had open was never consulted.

WHAT IT DELIBERATELY DOES NOT DO — and this is the important part.

**It never re-pairs a measurement whose patch order does not match the chart.**
It refuses it and says so. Re-pairing by matching device values was designed,
measured, and rejected on the evidence (§I.9, Basti 2026-08-31):

* `measurement_report.verify_patch_identity` CANNOT validate such a repair. It
  compares the chart's device values with the measurement's for each pairing —
  and a repair assigns those pairings by minimising exactly that difference. It
  therefore reports "verified" afterwards whether the repair was right or
  wrong. Measured: `mismatch, worst=100.0` before, `verified, worst=0.0001`
  after, on a deliberately shuffled file.
* A tolerant match — which any real implementation needs, because 23 of 240
  device values in ChromIQ's own demo chart differ from its own measurement in
  the fourth decimal — can hand a reading to a patch **16.24 ΔE00 away** in
  design colour on real charts.
* "Patches asked to be the same colour may be swapped freely" is true, and
  measured true on 22 of 24 real charts — but only for EXACT duplicates, not
  for tolerant neighbours.

A wrong repair is invisible: the report renders normally, every patch compared
against a real patch, just not the right one. Refusing is the honest answer.

**WHAT IT DOES DO, AND WHY THAT IS A DIFFERENT THING.** A measurement that
carries NO device values at all — an i1Profiler export of a chart i1Profiler did
not generate — is paired with the chart by the patch NAME each one carries, and
the chart's own device values are written beside the readings before the copy is
filed (:func:`complete_from_chart`, :mod:`workflow.measurement_pairing`).

That is not the rejected repair. Nothing here looks at a colour, so nothing here
can be validated by the quantity it minimised. A name is exact: the chart issued
it, printed it beside the patch, and the person aimed the instrument at it. A
measurement of somebody else's chart names patches this chart does not have, and
is refused on that.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from core.i18n import tr

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportVerdict:
    """Whether this file may be filed into this run, and what to tell the user.

    *ok* False means refuse. *partial* True means it holds FEWER readings than
    the chart has patches, which §I.10 files rather than refuses — a person may
    stop part way through and come back, and ChromIQ already builds a profile
    from such a measurement made here. Both counts travel so the window and the
    report can state them.
    """
    ok: bool
    reason: str = ""
    partial: bool = False
    n_chart: int = 0
    n_measured: int = 0
    #: True when the file carries no device values and the chart has to supply
    #: them before it is filed — see :func:`complete_from_chart`. The verdict
    #: says so rather than the caller guessing, because a file filed WITHOUT
    #: them is paired by i1Profiler's reading order and every number in the
    #: report is then about the wrong patch.
    device_from_chart: bool = False


def assess(ti3: Path, chart_ti2: "Path | None") -> ImportVerdict:
    """Decide whether *ti3* is a measurement OF *chart_ti2*.

    Order matters: the patch count is the cheap, clear check and gives the
    clearest sentence, so it runs first. The identity comparison — the one the
    report itself uses — runs second and is what catches a file of the right
    SIZE but the wrong chart.
    """
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    try:
        measured = parse_ti3(ti3)
    except (Ti3ParseError, OSError) as exc:
        return ImportVerdict(False, tr(
            "the file could not be read as a measurement ({error})").format(
                error=exc))

    n_chart = _chart_patch_count(chart_ti2)
    n_sheet = _chart_sheet_count(chart_ti2) or n_chart
    n_got = int(measured.n_patches or 0)

    if n_chart:
        if n_got > n_sheet:
            # NOT a partial. More readings than the SHEET carries squares means
            # it is a measurement of something else.
            #
            # AGAINST THE SHEET, NOT AGAINST THE DESIGN. A chart's last strip
            # is filled out with rows that are not part of the design, and the
            # person reading it reads them too — so a complete measurement of a
            # 408-patch design printed as 420 squares holds 420. Judged against
            # 408 it was called "a measurement of a different chart" and
            # refused, on a user's own verification of her own profile,
            # 2026-09-11. `expected_patches` is the design and says when a
            # measurement is SHORT; `sheet_patches` is the paper and says when
            # it is somebody else's.
            return ImportVerdict(False, tr(
                "the chart carries {chart} patches on the sheet, but this file "
                "holds {got} measurements, so it is a measurement of a "
                "different chart"
            ).format(chart=n_sheet, got=n_got), n_chart=n_chart, n_measured=n_got)
        if n_got < n_chart:
            # §I.10: filed, not refused, and both counts are stated — BUT it is
            # still checked against the chart. Returning here unchecked meant a
            # 240-patch measurement of a DIFFERENT chart was filed into a
            # 399-patch run and described as "part of the chart was not
            # measured". Fewer readings is a reason to say so, never a reason
            # to stop asking whether they are readings of this chart at all.
            partial = True
        else:
            partial = False

    else:
        partial = False

    if not measured.has_device:
        if chart_ti2 is None:
            # …AND WITH NO CHART BESIDE IT, NOTHING WILL EVER SUPPLY THEM.
            #
            # `parse_ti3` used to refuse a file with no device columns outright,
            # so BOTH profile-build doors refused this before the pairing work.
            # Teaching the parser to read such a file opened it at every door at
            # once, and only the doors that HAVE a chart were given the
            # completion step: `say_what_was_filed` returns before it, with the
            # comment "a bare measurement: nothing to judge it by", so a
            # spectral-only export dropped into "New project from a
            # measurement" was copied in, announced as filed, and left with no
            # device values at all. `colprof` cannot build from it, the grey
            # ramp cannot be found in it, and no later action supplies what is
            # missing, because the completion only ever runs at import.
            #
            # A file that cannot be completed and cannot be used is refused at
            # the only moment where nothing has been changed yet, which is what
            # it was before and what §I.9 asks for.
            return ImportVerdict(False, tr(
                "this file carries no device values, and there is no chart "
                "file beside it to supply them, so nothing in it says which "
                "colour each reading was printed with"),
                n_chart=n_chart or 0, n_measured=n_got)
        # NO DEVICE VALUES, SO THE CHECK IS THE NAME. An i1Profiler export of a
        # chart i1Profiler did not generate carries the patch NAME and the
        # spectral curve and nothing else — it has no colour space to write
        # device values in, and will not let you ask for them. The colour
        # comparison below therefore has nothing to compare, and said so
        # ("the measurement carries no device values"), which let the file pass
        # unchecked while `parse_ti3` refused it outright a few lines earlier.
        #
        # The name is a real check, and a stricter one than "unchecked": the
        # chart issued those labels and printed them beside the patches, so a
        # measurement of a different chart names patches this one does not
        # have. See `workflow.measurement_pairing` for why this is NOT the
        # device-value re-pairing §I forbids.
        verdict = _name_verdict(ti3, chart_ti2, n_chart, n_got, partial)
        if verdict is not None:
            return verdict
        return ImportVerdict(True, "", partial=partial, n_chart=n_chart or 0,
                             n_measured=n_got, device_from_chart=True)

    from workflow.measurement_report import verify_patch_identity
    identity = verify_patch_identity(measured, chart_ti2)
    if identity.get("verdict") == "mismatch":
        return ImportVerdict(False, identity.get("reason") or tr(
            "the measured colours do not agree with the chart's patches"),
            n_chart=n_chart or 0, n_measured=n_got)
    if not identity.get("checked"):
        # An uncheckable identity is not a refusal — the report records the
        # same state — but it must not pass in silence.
        log.info("import: the patch-identity check could not run (%s); "
                 "the import continues", identity.get("reason", ""))
    return ImportVerdict(True, "", partial=partial,
                         n_chart=n_chart or 0, n_measured=n_got)


def _name_verdict(ti3: Path, chart_ti2: Path, n_chart: int, n_got: int,
                  partial: bool) -> "ImportVerdict | None":
    """The refusal for a device-less file whose names are not this chart's, or
    ``None`` when they are. Counts travel so the window can state them."""
    from workflow.measurement_pairing import (match_by_name,
                                              measurement_locations)
    m = match_by_name(ti3, chart_ti2)
    if m.ok:
        return None
    if m.reason == "the chart file carries no patch names":
        # Never `tr(m.reason)`: a tr() whose argument is a variable is
        # invisible to the extractor, so the string would ship untranslated.
        return ImportVerdict(False, tr(
            "this file carries no device values, so ChromIQ has to pair it "
            "with the chart by the patch names, and the chart file carries "
            "none"), n_chart=n_chart or 0, n_measured=n_got)
    if m.reason:
        return ImportVerdict(False, tr(
            "this file carries no device values and no patch names either, so "
            "there is nothing in it that says which patch each reading "
            "belongs to"), n_chart=n_chart or 0, n_measured=n_got)
    if m.unknown:
        n = len(m.unknown)
        # The names in the FILE'S OWN ORDER, not sorted: a sorted sample of
        # "ZA1, ZA10, ZA11, ZA12" reads like a bug in the app rather than a
        # sample of the file, because nobody's chart is numbered that way.
        first = [loc for loc in measurement_locations(ti3) if loc in
                 set(m.unknown)][:4]
        shown = ", ".join(first) + ("…" if n > 4 else "")
        if n >= m.n_measured:
            # EVERY name is a stranger. Naming four of them suggests the other
            # 416 were fine, and they were not.
            return ImportVerdict(False, tr(
                "not one of the {count} patch names in this file is on this "
                "chart ({names}), so it is a measurement of a different chart"
            ).format(count=n, names=shown),
                n_chart=n_chart or 0, n_measured=n_got)
        return ImportVerdict(False, (tr(
            "one patch in this file ({names}) is not on this chart, so it is a "
            "measurement of a different chart") if n == 1 else tr(
            "{count} patches in this file ({names}) are not on this chart, so "
            "it is a measurement of a different chart")).format(
                count=n, names=shown),
            n_chart=n_chart or 0, n_measured=n_got)
    n = len(m.duplicated)
    shown = ", ".join(m.duplicated[:4]) + ("…" if n > 4 else "")
    return ImportVerdict(False, (tr(
        "one patch ({names}) is measured twice in this file, so ChromIQ "
        "cannot tell which reading belongs to it") if n == 1 else tr(
        "{count} patches ({names}) are measured twice in this file, so ChromIQ "
        "cannot tell which reading belongs to each")).format(
            count=n, names=shown),
        n_chart=n_chart or 0, n_measured=n_got)


def complete_from_chart(ti3: Path, chart_ti2: "Path | None") -> int:
    """Give a device-less measurement the chart's device values and row order.

    Call it on the COPY, after :func:`assess` has said ``device_from_chart``,
    and BEFORE anything reads the file as a measurement. Returns how many rows
    were written, 0 when there was nothing to do.

    Filing such a file without this step is worse than refusing it: the report
    pairs by ``SAMPLE_ID``, the file's ids are i1Profiler's reading order, and
    every patch would be compared against a real patch that is not the right
    one — which renders as an ordinary report saying nothing is wrong.
    """
    if chart_ti2 is None:
        return 0
    from workflow.measurement_pairing import attach_device_values_from_chart
    n = attach_device_values_from_chart(ti3, chart_ti2)
    if n:
        log.info("import: %d patches took their device values from %s",
                 n, Path(chart_ti2).name)
    return n


def _chart_patch_count(ti2: "Path | None") -> int:
    """How many patches the chart has, or 0 when that cannot be known.

    0 means "do not judge by count" rather than "the chart is empty": a run
    whose chart file is missing must not have every measurement refused for
    holding more patches than nothing.
    """
    # FROM THE HEADER, not by parsing it as a measurement. A `.ti2` carries
    # device values and no XYZ, so `parse_ti3` raises "No XYZ or Lab columns"
    # on every chart — which returned 0 here, silently switched the count check
    # off, and let a partial through as an ordinary import.
    #
    # THROUGH `expected_patches`, NOT A `NUMBER_OF_SETS` OF ITS OWN. A chart's
    # last strip is filled out with patches that are not part of the design —
    # printtarg's carry `SAMPLE_ID` 0, ChromIQ's layout engine's are copies of
    # the media patch — and the Build Profile tab has discounted them since
    # report 16. This door counted the raw header instead, so the same
    # measurement was "complete" to one part of the app and "partial" to the
    # other: a user's complete 4,000-patch measurement of a 4,014-row chart was
    # filed with "part of the chart was not measured" on 2026-09-11. One
    # counting rule, in one place.
    if ti2 is None:
        return 0
    from workflow.measurement_state import expected_patches
    return int(expected_patches(Path(ti2)) or 0)


def _chart_sheet_count(ti2: "Path | None") -> int:
    """How many patches the chart PRINTS, fill-up rows included, or 0.

    The other half of the pair above. `_chart_patch_count` is what the design
    asked for and says when a measurement is short; this is what is on the
    paper and says when a measurement is of another chart entirely. Using one
    number for both questions got both of them wrong, a day apart and in
    opposite directions.
    """
    if ti2 is None:
        return 0
    from workflow.measurement_state import sheet_patches
    return int(sheet_patches(Path(ti2)) or 0)
