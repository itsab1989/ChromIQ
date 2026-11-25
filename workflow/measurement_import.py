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
    #: How many DESIGN patches have a reading, by location, when that differs
    #: from the row count: a partial file that also holds the readings of the
    #: layout engine's fill-up squares has as many rows as the chart has
    #: patches, or more, and "the chart has 390 patches and this file holds
    #: 398 readings, so part of the chart was not measured" contradicts itself
    #: (review of 4.3.5 beta 8). ``None`` when the row count is the answer.
    n_read: "int | None" = None
    #: True when the file is an i1Profiler measurement of the TURNED export
    #: (beta, `workflow.i1profiler_turned`, §I.14): its readings are numbered
    #: in the turned order, and they agree with the chart's device values,
    #: patch for patch, only in that order. The caller files it through
    #: :func:`complete_from_turned_order`; filed as it is, every reading would
    #: sit on the wrong patch.
    turned_order: bool = False
    #: The i1iO Beta (one page): an i1Profiler "Measure Chart" measurement of
    #: this i1iO chart's own sheet, judged by `workflow.i1io.measure_chart`;
    #: its verdict (`McVerdict`) travels here. The caller files it through
    #: :func:`complete_from_i1io_grid` (asking first when ``ask_why`` says the
    #: chart's colours cannot tell); filed as it is, the placeholders in it
    #: would be taken for device values.
    i1io_grid: object = None
    #: True when the i1iO Beta's Measure Chart route refused the file: the
    #: doors show it under M-IMPORT-I1IO-REFUSED, whose title does not say
    #: "another chart" (review m3).
    i1io_refusal: bool = False
    #: True when the Barbieri Beta's Spectro32 route refused the file: the
    #: doors show it under M-IMPORT-BARBIERI-REFUSED.
    barbieri_refusal: bool = False
    #: Why the colours of an i1iSis measurement of a chart that is not
    #: randomised cannot show how the sheet was fed (`isis.import_check`:
    #: "few", "similar", "way", "whole"), or "". The file may be filed, but
    #: every door asks the person first (M-IMPORT-ISIS-CANNOT-CHECK).
    isis_ask_why: str = ""

    @property
    def patches_read(self) -> int:
        """The number a partial window states beside the chart's count."""
        return self.n_read if self.n_read is not None else self.n_measured


def _cgats_table_kind(path: Path) -> str:
    """The CGATS keyword the file opens with (``CTI1``/``CTI2``/``CTI3``/…), or
    "" when it does not announce one.

    The first non-blank line of an ArgyllCMS table IS its type — printtarg
    writes `CTI2` at the top of every chart it lays out, chartread writes
    `CTI3` at the top of every measurement — so this is the file saying what it
    is rather than anybody guessing from a suffix.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for _ in range(8):
                line = fh.readline()
                if not line:
                    break
                word = line.strip().split()[:1]
                if word:
                    return word[0].upper()
    except OSError:
        return ""
    return ""


def looks_like_a_chart(path: "Path | str") -> bool:
    """Is this file a CHART rather than a measurement of one?

    Public because it has to be asked TWICE, in two different places, and the
    second one is not obvious. `assess` asks it below and catches a chart that
    arrives under a `.ti3` name — but a chart picked as a `.ti2` never reaches
    `assess` looking like one: it is not a `.ti3`, so the import hands it to
    txt2ti3 first, and what comes back out is a well-formed CTI3 table of the
    chart's aim values with nothing left in it to give the game away. So the
    door asks this of the file the PERSON picked, before anything is converted.
    """
    return _cgats_table_kind(Path(path)) in ("CTI1", "CTI2")


#: The one sentence both places say about it, so they cannot drift.
CHART_NOT_A_MEASUREMENT = (
    "this file is a chart, not a measurement of one. It is the list of "
    "colours to print, and the numbers in it are the colours ChromIQ "
    "ASKED for, not the ones an instrument read back. Choose the file "
    "your measuring software saved instead.")


def assess(ti3: Path, chart_ti2: "Path | None",
           source: "Path | None" = None) -> ImportVerdict:
    """Decide whether *ti3* is a measurement OF *chart_ti2*.

    Order matters: is it a measurement at all, then the patch count (the cheap,
    clear check, and the clearest sentence), then the identity comparison — the
    one the report itself uses — which is what catches a file of the right SIZE
    but the wrong chart.

    *source* is the file the person PICKED (the Measure tab's import passes
    it; other doors do not): the i1iO Beta reads an i1Profiler Measure Chart
    measurement's places from it (`_i1io_route`). Without the Beta, or for a
    chart that is not an i1iO chart, it is never looked at.
    """
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3

    # A CHART IS NOT A MEASUREMENT OF ITSELF, and nothing below could tell.
    #
    # Found by driving the refusal doors (challenge round 6, 2026-09-15) with
    # the run's own `.ti2` picked as the measurement — an easy slip, since the
    # chart and the measurement sit in the same folder under the same stem and
    # both are CGATS tables. printtarg writes the chart's AIM XYZ into the
    # `.ti2`, so `parse_ti3` reads it happily as a full set of readings, the
    # patch count matches exactly (it is the same file), and
    # `verify_patch_identity` compares the chart against itself and reports a
    # flawless match. It was filed, in silence, as the run's measurement — and
    # a profile built from it would be a profile of a printer that had never
    # printed anything.
    #
    # The file says what it is on its first line, so ask it. Here rather than
    # in one door, because both doors reach `assess` and neither could see it.
    if looks_like_a_chart(ti3):
        return ImportVerdict(False, tr(CHART_NOT_A_MEASUREMENT))

    # AN i1Profiler "MEASURE CHART" MEASUREMENT OF AN i1iO SHEET (the i1iO
    # Beta, one page). Asked first, because its device values are i1Profiler's
    # placeholders: every check below would read them as device values.
    # Nothing is read for it unless the Beta is on and the chart is an i1iO
    # chart with its side file.
    route = _i1io_route(ti3, chart_ti2, source)
    if route is not None:
        return route

    # A SPECTRO32 MEASUREMENT OF A BARBIERI CHART (the Barbieri Beta, step
    # 2). The Measure tab's door judged and paired it while converting it
    # (`workflow.barbieri.spectro32_import`); here the copy must say so.
    # Nothing is read for it unless the Beta is on, the chart is a Barbieri
    # chart with its side file and the picked file is Spectro32's.
    route = _barbieri_route(ti3, chart_ti2, source)
    if route is not None:
        return route

    # A CMYK OR MULTI-INK MEASUREMENT HAS ITS OWN BRANCH (beta 7, Basti
    # 2026-10-03: "yes, allow importing cmyk into a cmyk run"). `parse_ti3`
    # refuses it and is left refusing it: thirty readers rely on that, and
    # `Ti3Data.has_device` would call a CMYK file device-less if the parser
    # returned one with `rgb` empty, which would send it down the §I.11 NAME
    # pairing below and write the chart's values over its own. So it is
    # judged here with the N-channel tools, by the same rules.
    from workflow.ti3_analysis import device_space_of
    m_space = device_space_of(ti3)
    if m_space and m_space != "RGB":
        return _assess_non_rgb(ti3, chart_ti2, m_space)
    # …AND AN RGB MEASUREMENT IS NOT A MEASUREMENT OF A CMYK CHART. Before,
    # `verify_patch_identity` could not read such a chart, answered
    # "unchecked", and the import went on.
    c_space = device_space_of(chart_ti2) if chart_ti2 is not None else None
    if m_space == "RGB" and c_space and c_space != "RGB":
        return ImportVerdict(False, _device_type_reason("RGB", c_space))

    try:
        measured = parse_ti3(ti3)
    except (Ti3ParseError, OSError) as exc:
        return ImportVerdict(False, tr(
            "the file could not be read as a measurement ({error})").format(
                error=exc))

    n_chart = _chart_patch_count(chart_ti2)
    n_sheet = _chart_sheet_count(chart_ti2) or n_chart
    n_got = int(measured.n_patches or 0)
    n_read = None

    if n_chart:
        if n_got > n_sheet:
            # NOT a partial. More readings than the SHEET carries squares means
            # it is a measurement of something else.
            #
            # AGAINST EVERY ROW OF THE CHART. A chart's last strip may be
            # filled out, and the person reading it reads those squares too:
            # a complete measurement of a 408-patch design printed as 420
            # squares holds 420 (a user's verification, 2026-09-11). Since
            # Knut's ruling (#182 6191934889) those squares are patches and
            # `expected_patches` counts them; `sheet_patches` differs from it
            # only by printtarg's SAMPLE_ID 0 padding.
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
            n_read = _patches_read_by_location(ti3, chart_ti2, n_chart)
            partial = n_read is not None

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
        # …EXCEPT FOR A CHART WITH A TURNED i1PROFILER EXPORT (beta, §I.14).
        # i1Profiler names the patches of a chart it laid out by ITS rows and
        # columns, and on a turned chart those names are the very set ChromIQ
        # printed (rows = strips, columns = places), each on a different patch.
        # A name pairing would pass every check and put every reading on the
        # wrong patch. Without device values nothing can tell the two apart.
        # ONLY WHERE THIS CHART'S OWN ORDER FILE EXISTS: `turned_order_for`
        # answers None unless an order file sits beside the chart (exports/ or
        # its own folder) AND names this exact .ti2 by its SHA-256. A chart
        # made with the option off has none (Create Chart removes a stale
        # one), so it is judged exactly as before.
        from workflow.i1profiler_turned import turned_order_for
        if turned_order_for(chart_ti2) is not None:
            return ImportVerdict(False, tr(
                "this file carries no device values, and this chart also has "
                "a turned i1Profiler chart, whose patch names are the same as "
                "this chart's but sit on other patches, so ChromIQ cannot tell "
                "which patch each reading belongs to. If you measured the "
                "turned chart in i1Profiler, save the measurement as an .mxf "
                "file, or as a CGATS text export that includes the RGB values: "
                "both keep the colours ChromIQ needs. Then import that file "
                "instead. If you read this chart another way that gives a "
                "file without device values (for example with an i1iO "
                "through i1Profiler), "
                "ChromIQ pairs such a file by patch name only on a chart that "
                "was made with the turned i1Profiler option switched off "
                "(Preferences, Beta)"),
                n_chart=n_chart or 0, n_measured=n_got)
        verdict = _name_verdict(ti3, chart_ti2, n_chart, n_got, partial)
        if verdict is not None:
            return verdict
        return ImportVerdict(True, "", partial=partial, n_chart=n_chart or 0,
                             n_measured=n_got, device_from_chart=True,
                             n_read=n_read)

    from workflow.measurement_report import verify_patch_identity
    identity = verify_patch_identity(measured, chart_ti2)
    if identity.get("verdict") == "mismatch":
        # A MEASUREMENT OF THE TURNED i1PROFILER EXPORT (beta, §I.14) arrives
        # numbered in the turned order. It is paired by THAT order, which was
        # fixed when the chart was made and is tied to this exact .ti2 by its
        # checksum, and only when the device values then agree on every
        # patch: the colours check a pairing they did not choose (§I.9).
        from workflow.i1profiler_turned import turned_match
        turned = turned_match(measured, chart_ti2)
        if turned.applies and turned.verified and turned.partial:
            # PART OF A TURNED MEASUREMENT, refused for what it is. The
            # identity sentence would say every patch holds the wrong colour,
            # which is not what is wrong: the readings follow the turned order
            # and only the rest of the rows is missing. §I.14 pairs a COMPLETE
            # turned measurement only; that rule is unchanged here, the
            # refusal just gives its true reason now.
            return ImportVerdict(False, _turned_partial_reason(
                n_got, len(turned.order.sample_ids)),
                n_chart=n_chart or 0, n_measured=n_got)
        if turned.applies and turned.ambiguous:
            # MORE THAN ONE ORDER FITS, AND THEY DISAGREE (review 4.3.18 r1,
            # SF-1): the chart repeats its colours so that this file agrees
            # with the order in force AND with an earlier one ChromIQ wrote
            # for the same chart, each putting readings on other patches.
            return ImportVerdict(False, turned_ambiguous_reason(),
                                 n_chart=n_chart or 0, n_measured=n_got)
        if (turned.applies and turned.verified
                and getattr(turned.order, "kind", "") == "isis"
                and int(getattr(turned.order, "pages", 1) or 1) > 1):
            # AN i1iSis CHART OF SEVERAL PAGES (a Beta, stage 1): measuring
            # it in i1Profiler works, bringing it back needs a later version
            # (the pages' places are not read yet). Said, never guessed.
            return ImportVerdict(False, _isis_pages_reason(turned.order),
                                 n_chart=n_chart or 0, n_measured=n_got)
        if turned.applies and turned.verified:
            # …AND ONLY WHEN i1PROFILER LAID IT OUT ON THE GRID THE .TXF ASKS
            # FOR (4.3.19). The device values repeat the patch list whatever
            # grid i1Profiler made, so with one column more every row was
            # read on other patches and the file still agreed on every patch.
            # An .mxf records the grid and every patch's place on it; a file
            # that does not (a CGATS export) is judged as before.
            from workflow.i1profiler_turned import grid_mismatch
            isis = getattr(turned.order, "kind", "") == "isis"
            grid = _isis_source_grid(ti3, source) if isis else None
            why = grid_mismatch(ti3, turned.order, chart_ti2, grid=grid)
            if why:
                return ImportVerdict(False, why, n_chart=n_chart or 0,
                                     n_measured=n_got)
            if isis:
                # G1 (the i1iSis Beta): the device values prove which test
                # chart i1Profiler used, not how the sheet went in (§I.14
                # point 1's own caveat), so the colours are asked too. Only
                # a clear disagreement refuses; "cannot tell" is filed as
                # before, said in the log (review m5).
                why = _isis_colours_refuse(ti3, turned.order, chart_ti2)
                if why:
                    return ImportVerdict(False, why, n_chart=n_chart or 0,
                                         n_measured=n_got)
            return ImportVerdict(True, "", partial=False,
                                 n_chart=n_chart or 0, n_measured=n_got,
                                 turned_order=True)
        if turned.applies:
            log.info("import: not the turned order either (%d of %d patches "
                     "differ)", turned.mismatched, turned.compared)
        return ImportVerdict(False, identity.get("reason") or tr(
            "the measured colours do not agree with the chart's patches"),
            n_chart=n_chart or 0, n_measured=n_got)
    if identity.get("verdict") == "verified" and chart_ti2 is not None:
        # THE ORDINARY PAIRING FITS, BUT DOES A TURNED ONE FIT AS WELL? Only a
        # chart with its own turned order is asked (`turned_order_for` is one
        # stat per folder without one), and only a chart that repeats its
        # colours can fit both: an evenness sheet read on the turned
        # i1Profiler chart agrees with its own patches by SAMPLE_ID too, and
        # was filed with every reading on the wrong patch (review 4.3.18 r1,
        # SF-1). Nothing in the file says which way it was measured.
        from workflow.i1profiler_turned import (fits_straight_and_turned,
                                                turned_match,
                                                turned_order_for)
        # …UNLESS THE FILE SAYS IT WAS READ FROM CHROMIQ'S OWN SHEET (review
        # 4.3.18 r2, SF-B): chartread reads the sheet as printed, by the
        # chart's own .ti2, and could never have read i1Profiler's turned
        # chart; a measurement ChromIQ already paired through the turned order
        # carries its keyword and is in the chart's order. Refusing those told
        # a person who HAD measured in ChromIQ to measure in ChromIQ.
        if (turned_order_for(chart_ti2) is not None
                and not read_from_the_sheet_as_printed(ti3)):
            turned = turned_match(measured, chart_ti2)
            if fits_straight_and_turned(measured, turned):
                return ImportVerdict(False, straight_or_turned_reason(),
                                     n_chart=n_chart or 0, n_measured=n_got)
        # AN i1iSis CHART THAT IS NOT RANDOMISED (a Beta, item 63). Its order
        # is the chart's own numbering, so the check by SAMPLE_ID above passes
        # and the i1iSis checks of the branch above were never reached: a
        # measurement of several pages, of a sheet fed the wrong way round or
        # read one column off was filed. i1Profiler copies the device values
        # from its test chart, so here they prove nothing about the sheet.
        if not read_from_the_sheet_as_printed(ti3):
            isis = _isis_same_order(ti3, measured, chart_ti2, source,
                                    n_chart or 0, n_got)
            if isis is not None:
                return isis
    if not identity.get("checked"):
        # An uncheckable identity is not a refusal — the report records the
        # same state — but it must not pass in silence.
        log.info("import: the patch-identity check could not run (%s); "
                 "the import continues", identity.get("reason", ""))
    return ImportVerdict(True, "", partial=partial,
                         n_chart=n_chart or 0, n_measured=n_got, n_read=n_read)


def i1io_route_applies(chart_ti2: "Path | None") -> bool:
    """True when the i1iO Beta is on and *chart_ti2* is an i1iO chart with
    its side file: the only charts the Measure Chart route is for. Reads the
    switch first, so with the Beta off nothing is opened at all."""
    if chart_ti2 is None:
        return False
    from workflow.i1io.support import i1io_enabled
    if not i1io_enabled():
        return False
    from workflow.i1io.support import chart_names_i1io
    if chart_names_i1io(chart_ti2) is not True:
        return False
    text = str(chart_ti2)
    stem = text[:-4] if text.lower().endswith(".ti2") else text
    return Path(stem + ".i1io.json").is_file()


def _i1io_route(ti3: Path, chart_ti2: "Path | None",
                source: "Path | None") -> "ImportVerdict | None":
    """The i1iO Beta's import route, or None: the ordinary import judges.

    * the picked file is a CxF and a Measure Chart measurement (placeholders
      for device values, a place for every reading): judged and paired by
      `workflow.i1io.measure_chart`, refused with its reason;
    * the picked file is a text export without device values, or with one
      value for every patch (challenge S3): refused, because only the .cmxf
      says where each reading was taken; any other text export goes on as
      before (i1Profiler's own iO chart with real device values);
    * no picked file (another door) and one device value for every patch:
      refused with a sentence that sends it to the Measure tab.
    """
    if not i1io_route_applies(chart_ti2):
        return None
    n_chart = _chart_patch_count(chart_ti2)
    from workflow import measurement_messages as MM
    if source is not None and Path(source).suffix.lower() in (
            ".cmxf", ".cxf", ".mxf"):
        from workflow.i1io import measure_chart as MC
        v = MC.assess_file(source, ti3, chart_ti2)
        if v is None:
            return None
        if not v.ok:
            return ImportVerdict(False, v.reason, n_chart=n_chart or 0,
                                 i1io_refusal=True)
        n = len(v.sample_of_row)
        return ImportVerdict(True, "", n_chart=n_chart or 0, n_measured=n,
                             i1io_grid=v)
    one = _one_device_value_for_all(ti3, chart_ti2)
    if source is not None:
        if one is None or one:
            # no device values (None) or the placeholders: a text export of
            # a Measure Chart measurement
            if one is None and not _has_readings(ti3):
                return None
            return ImportVerdict(False, MM.i1io_import_reason("text"),
                                 n_chart=n_chart or 0, i1io_refusal=True)
        return None
    if one:
        return ImportVerdict(False, MM.i1io_import_reason("other-door"),
                             n_chart=n_chart or 0)
    return None


def barbieri_route_applies(chart_ti2: "Path | None") -> bool:
    """True when the Barbieri Beta is on and *chart_ti2* is a Barbieri chart
    with its side file (`spectro32_import.route_applies`). Reads the switch
    first, so with the Beta off nothing is opened at all."""
    if chart_ti2 is None:
        return False
    from workflow.barbieri.support import barbieri_enabled
    if not barbieri_enabled():
        return False
    from workflow.barbieri.spectro32_import import route_applies
    return route_applies(chart_ti2)


def _barbieri_route(ti3: Path, chart_ti2: "Path | None",
                    source: "Path | None") -> "ImportVerdict | None":
    """The Barbieri Beta's import route, or None: the ordinary import
    judges. A Spectro32 file is converted only by the Measure tab, which
    judges it there and writes the paired copy (`spectro32_import.
    write_ti3`); a copy that does not carry the pairing, or does not hold
    every patch of the chart, is refused here."""
    if source is None or not barbieri_route_applies(chart_ti2):
        return None
    from workflow.barbieri import spectro32_import as S
    if not S.looks_like_spectro32(source):
        return None
    n_chart = _chart_patch_count(chart_ti2) or 0
    from workflow import measurement_messages as MM
    try:
        with open(ti3, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(8192)
    except OSError:
        head = ""
    if S.PAIRED_KEYWORD not in head:
        return ImportVerdict(False, MM.barbieri_import_reason(
            "not-spectro32", name=Path(source).name), n_chart=n_chart,
            barbieri_refusal=True)
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    try:
        n = parse_ti3(Path(ti3)).n_patches
    except (Ti3ParseError, OSError):
        n = 0
    if not n or (n_chart and n != n_chart):
        return ImportVerdict(False, MM.barbieri_import_reason(
            "side", side=Path(str(chart_ti2)[:-4] + ".barbieri.json").name),
            n_chart=n_chart, n_measured=n, barbieri_refusal=True)
    log.info("import: a Spectro32 measurement paired by reading order with "
             "%s (%d patches)", Path(chart_ti2).name, n)
    return ImportVerdict(True, "", n_chart=n_chart, n_measured=n)


def _has_readings(ti3: Path) -> bool:
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    try:
        return bool(parse_ti3(Path(ti3)).n_patches)
    except (Ti3ParseError, OSError):
        return False


def _one_device_value_for_all(ti3: Path, chart_ti2: Path) -> "bool | None":
    """None when *ti3* carries no device values; True when every row has the
    same one and the chart has more than that one (i1Profiler's
    placeholders); False otherwise."""
    from core.text_io import read_text
    from workflow.measurement_pairing import _first_table
    from workflow.ti3_analysis import _has_device_columns

    def table(path):
        try:
            return _first_table(read_text(Path(path), lenient=True))
        except OSError:
            return None
    t = table(ti3)
    if t is None:
        return None
    fields, rows = t
    if not _has_device_columns(fields):
        return None
    di = [i for i, f in enumerate(fields)
          if f.startswith(("RGB_", "CMYK_"))]
    if not di:
        return False
    vals = {tuple(ln.split()[i] for i in di if i < len(ln.split()))
            for ln in rows}
    if len(vals) != 1 or not rows:
        return False
    c = table(chart_ti2)
    if c is None:
        return True
    cf, cr = c
    ci = [i for i, f in enumerate(cf) if f.startswith(("RGB_", "CMYK_"))]
    try:
        chart_vals = {tuple(round(float(ln.split()[i]), 2) for i in ci)
                      for ln in cr}
        mine = tuple(round(float(v), 2) for v in next(iter(vals)))
    except (ValueError, IndexError):
        return True
    return chart_vals != {mine}


def _turned_partial_reason(got: int, total: int) -> str:
    return tr(
        "this file is a measurement of the turned i1Profiler chart, "
        "and ChromIQ can only bring such a measurement back when "
        "every patch of the chart has been measured. This file holds "
        "{got} of the chart's {total} readings. Measure the remaining "
        "rows in i1Profiler, save the measurement again as an .mxf "
        "file and import that file").format(got=got, total=total)


def _isis_pages_reason(order) -> str:
    return tr(
        "this file is a measurement of an i1iSis chart with {pages} "
        "pages. Bringing a measurement of several pages back into "
        "ChromIQ needs a later version of ChromIQ; the measurement "
        "itself is fine, so keep the file").format(pages=int(order.pages))


def _isis_source_grid(ti3: Path, source: "Path | None"):
    """G2 (the i1iSis Beta): a CxF whose NumberPatchPages is "0" carries no
    grid keyword in the converted copy, so the grid check was skipped; read
    from the picked file, "0" taken as one page. None: the copy's own grid.
    The converter is unchanged."""
    if source is None:
        return None
    from workflow.i1profiler_turned import isis_grid_from_source
    from workflow.reference_convert import i1p_grid_of
    return isis_grid_from_source(source) if i1p_grid_of(ti3) is None else None


def _isis_order_for(chart_ti2: Path):
    """The order of the i1iSis chart *chart_ti2*: its order file, or, when
    that is missing (exports/ is derived), worked out again from the chart
    and its side file; None when neither can say."""
    from workflow.i1profiler_turned import turned_order_for
    order = turned_order_for(chart_ti2)
    if getattr(order, "kind", "") != "isis":
        from workflow.isis.export import order_of
        order = order_of(chart_ti2)
    return order


def _made_by_the_isis_beta(chart_ti2: Path) -> bool:
    """True for a chart the i1iSis Beta laid out, while the Beta is on. The
    switch is read first: with it off nothing is opened."""
    from workflow.isis.support import chart_names_isis, isis_enabled
    if not isis_enabled() or chart_names_isis(chart_ti2) is not True:
        return False
    try:
        with open(chart_ti2, "rb") as fh:
            head = fh.read(65536).split(b"BEGIN_DATA_FORMAT", 1)[0]
    except OSError:
        return False
    return b"CHROMIQ_ISIS_LAYOUT" in head


def _isis_same_order(ti3: Path, measured, chart_ti2: Path,
                     source: "Path | None", n_chart: int,
                     n_got: int) -> "ImportVerdict | None":
    """The i1iSis checks (pages, every patch, grid, colours) for a measurement
    whose device values already agree with the chart by SAMPLE_ID, i.e. of a
    chart that is not randomised. None: not such a chart."""
    if not _made_by_the_isis_beta(chart_ti2):
        return None

    def refuse(reason: str) -> ImportVerdict:
        return ImportVerdict(False, reason, n_chart=n_chart,
                             n_measured=n_got)
    order = _isis_order_for(chart_ti2)
    if order is None:
        from workflow.isis.support import side_file_for
        from workflow.measurement_messages import isis_files_missing_reason
        return refuse(isis_files_missing_reason(
            side_file_for(chart_ti2).name))
    n = len(order.sample_ids)
    if list(order.sample_ids) != [str(i + 1) for i in range(n)]:
        return None                  # randomised: the branches above judged it
    if int(order.pages or 1) > 1:
        return refuse(_isis_pages_reason(order))
    # EVERY ENTRY ONCE (§I.14, as for a randomised chart). i1Profiler numbers
    # its entries 1..N; a file whose ids are none of these was compared by
    # position, and is judged by position here too.
    numbers = {str(i + 1): i for i in range(n)}
    ids = [str(s).strip('"') for s in (measured.sample_ids or [])]
    at = [numbers[s] for s in ids if s in numbers]
    by_number = sorted(at) == list(range(n)) and len(ids) == n
    if not by_number and (at or n_got != n):
        return refuse(_turned_partial_reason(len(set(at)), n))
    if not by_number:
        at = list(range(n))
    from workflow.i1profiler_turned import grid_mismatch
    why = grid_mismatch(ti3, order, chart_ti2,
                        grid=_isis_source_grid(ti3, source))
    if why:
        return refuse(why)
    from workflow.isis import import_check as IC
    verdict = IC.judge_rows(measured, at, order, chart_ti2)
    log.info("import: the colours of the measurement of an i1iSis chart that "
             "is not randomised were compared with the chart: %s (%s) %s",
             verdict.verdict, verdict.why or "agree", verdict.detail)
    if verdict.verdict == IC.WRONG:
        from workflow.measurement_messages import isis_colours_reason
        return refuse(isis_colours_reason())
    return ImportVerdict(
        True, "", n_chart=n_chart, n_measured=n_got,
        isis_ask_why=verdict.why if verdict.verdict == IC.CANNOT else "")


def _isis_colours_refuse(ti3: Path, order, chart_ti2) -> str:
    """G1: the refusal when the colours of an i1iSis measurement CLEARLY do
    not fit the chart in its order; "" to file it.

    A guard, not a new gate (review 2026-11-15, m5): before it such a file
    was filed on its device values alone, and right readings of a small
    chart on a very glossy paper can leave the judge unsure ("between",
    "strip-unclear"; reproduced: 4 of 90 small charts). So only a clear
    disagreement refuses; every "cannot tell" is filed as before, said in
    the log."""
    from workflow.turned_colour_check import (DISAGREE,
                                              judge_turned_measurement)
    colour = judge_turned_measurement(ti3, order, chart_ti2)
    if colour.verdict != DISAGREE:
        log.info("import: the colours of the i1iSis measurement were "
                 "compared with the chart (%s); the device values agree on "
                 "every patch, so it is filed", colour.log_text())
        return ""
    log.info("import: the colours of the i1iSis measurement do not fit the "
             "chart: %s", colour.log_text())
    from workflow.measurement_messages import isis_colours_reason
    return isis_colours_reason()


def complete_from_i1io_grid(ti3: Path, chart_ti2: "Path | None",
                            verdict: ImportVerdict) -> int:
    """File a Measure Chart measurement on the COPY *ti3* by its own places
    (`workflow.i1io.measure_chart.complete`). Returns the rows written; 0
    means refuse."""
    if chart_ti2 is None or verdict.i1io_grid is None:
        return 0
    from workflow.i1io import measure_chart as MC
    n = MC.complete(ti3, chart_ti2, verdict.i1io_grid)
    if n:
        log.info("import: %d readings of an i1Profiler Measure Chart "
                 "measurement paired with %s by their places in its grid",
                 n, Path(chart_ti2).name)
    return n


#: The ``ORIGINATOR`` of a measurement made by ArgyllCMS chartread, the only
#: tool ChromIQ measures a strip-reader chart with. It reads the sheet as
#: printed, by the chart's own .ti2. An i1Profiler measurement reaches
#: :func:`assess` as ``"ChromIQ"`` (converted from its .mxf / .cxf,
#: `reference_convert.cxf_measurement_to_ti3`) or as ``"Argyll target"``
#: (converted from its CGATS .txt by txt2ti3: measured with ArgyllCMS 3.5.0,
#: review 4.3.18 r3, SF-2), never as this.
CHARTREAD_ORIGINATOR = "Argyll chartread"


def read_from_the_sheet_as_printed(ti3: "Path | str") -> bool:
    """True when *ti3* itself says it holds readings in the chart's own order
    and cannot be a measurement of the turned i1Profiler chart: written by
    chartread (:data:`CHARTREAD_ORIGINATOR`), or already paired through the
    turned order by ChromIQ (``TURNED_KEYWORD``). Anything else, including an
    unreadable file, is "cannot tell" and keeps the straight-or-turned check
    (review 4.3.18 r2, SF-B)."""
    import re
    from workflow.i1profiler_turned import TURNED_KEYWORD
    try:
        with open(ti3, "r", encoding="utf-8", errors="replace") as fh:
            head = []
            for line in fh:
                if line.strip() == "BEGIN_DATA":
                    break
                head.append(line)
                if len(head) > 400:
                    break
    except OSError:
        return False
    text = "".join(head)
    if re.search(r'^\s*' + re.escape(TURNED_KEYWORD) + r'\b', text,
                 re.MULTILINE):
        return True
    m = re.search(r'^\s*ORIGINATOR\s+"([^"]*)"', text, re.MULTILINE)
    # Safe for an averaged read too (r3, N-3): Argyll `average` keeps its
    # FIRST input's header, so ChromIQ's average of chartread reads is
    # exempt, and one with any other first input is asked (the safe side).
    return bool(m) and m.group(1).strip() == CHARTREAD_ORIGINATOR


def turned_ambiguous_reason() -> str:
    """The refusal for a turned measurement that fits more than one order
    ChromIQ wrote for the chart (review 4.3.18 r1, SF-1; §I.14)."""
    return tr(
        "this file is a measurement of the turned i1Profiler chart, but "
        "ChromIQ cannot tell which patch each of its readings belongs to. "
        "ChromIQ has written more than one i1Profiler test-chart file for "
        "this chart: the one it wrote last, and an earlier one (for example "
        "from ChromIQ 4.3.17, which turned the sheet the other way). This "
        "chart repeats its colours in such a way that the readings fit both "
        "files on every patch, yet the two would put some readings on "
        "different patches. Nothing in the file says which one you measured "
        "with, so ChromIQ does not guess. "
        "Measuring the sheet again in i1Profiler would not help, because the "
        "new readings would fit both files in the same way. Please measure "
        "this sheet in ChromIQ instead: ChromIQ reads every patch where it "
        "is printed")


def straight_or_turned_reason() -> str:
    """The refusal for a measurement that fits the chart both as it is and
    through its turned i1Profiler order (review 4.3.18 r1, SF-1; §I.14)."""
    return tr(
        "ChromIQ cannot tell which patch each reading of this file belongs "
        "to. This chart also has a turned i1Profiler chart, and it repeats "
        "its colours in such a way that the readings fit the chart's patches "
        "both in the chart's own order and in the order of the turned "
        "i1Profiler chart, yet the two would put some readings on different "
        "patches. Nothing in the file says whether it was measured on "
        "ChromIQ's sheet as printed or on the turned i1Profiler chart, so "
        "ChromIQ does not guess. (A measurement made in ChromIQ, or with "
        "ArgyllCMS chartread, says so in the file and is filed without this "
        "question.) Measuring the "
        "sheet again in i1Profiler would not help, because the new readings "
        "would fit both orders in the same way. Please measure this sheet in "
        "ChromIQ instead: ChromIQ reads every patch where it is printed")


def _device_type_reason(measured_space: str, chart_space: str) -> str:
    """The refusal for a measurement made for other inks than the chart."""
    from workflow.layout_engine.calibration import colour_space_name
    return tr(
        "this measurement is {measured}, but the chart is {chart}, so it is "
        "a measurement of a different chart"
    ).format(measured=colour_space_name(measured_space),
             chart=colour_space_name(chart_space))


def _assess_non_rgb(ti3: Path, chart_ti2: "Path | None",
                    m_space: str) -> ImportVerdict:
    """`assess` for a CMYK or multi-ink measurement (beta 7).

    The same questions in the same order as the RGB branch, asked with the
    N-channel readers (`printer_calibration.read_table`,
    `ti3_analysis.device_columns`), so nothing here is CMYK-specific: any ink
    set targen writes is judged alike.

    1. it carries colour (XYZ or L*a*b*), or it is no measurement;
    2. its inks are the chart's, compared by colorant letter as
       `calibration.check_matches` compares a calibration with a chart;
    3. the count rules of §I.10/§I.12: more readings than the sheet carries
       is a different chart, fewer than the design is a partial;
    4. identity per SAMPLE_ID: every device value the chart has must be the
       measurement's within `PATCH_IDENTITY_TOL`
       (`printer_calibration.device_values_differ`). No re-pairing, §I.9.

    It never takes the chart's device values (`device_from_chart` stays
    False): the file has its own, and they are what was checked.
    """
    from workflow.printer_calibration import device_values_differ, read_table
    from workflow.ti3_analysis import device_inks_of, device_space_of
    try:
        fields, rows, _kw = read_table(ti3)
    except (OSError, ValueError) as exc:
        return ImportVerdict(False, tr(
            "the file could not be read as a measurement ({error})").format(
                error=exc))
    has_xyz = all(f"XYZ_{c}" in fields for c in "XYZ")
    has_lab = all(f"LAB_{c}" in fields for c in "LAB")
    if not (has_xyz or has_lab):
        return ImportVerdict(False, tr(
            "the file could not be read as a measurement ({error})").format(
                error="No XYZ or Lab columns"))
    n_got = len(rows)
    if chart_ti2 is None:
        # As for an RGB file with no chart beside it: it carries its own
        # device values, so it can be used; there is nothing to judge it by.
        return ImportVerdict(True, "", n_measured=n_got)

    c_space = device_space_of(chart_ti2)
    if c_space is not None and (c_space == "" or c_space == "RGB"
                                or device_inks_of(chart_ti2)
                                != device_inks_of(ti3)):
        return ImportVerdict(False, _device_type_reason(
            m_space, c_space or "?"), n_measured=n_got)

    n_chart = _chart_patch_count(chart_ti2)
    n_sheet = _chart_sheet_count(chart_ti2) or n_chart
    partial = False
    n_read = None
    if n_chart:
        if n_got > n_sheet:
            return ImportVerdict(False, tr(
                "the chart carries {chart} patches on the sheet, but this file "
                "holds {got} measurements, so it is a measurement of a "
                "different chart"
            ).format(chart=n_sheet, got=n_got), n_chart=n_chart, n_measured=n_got)
        if n_got < n_chart:
            partial = True
        else:
            n_read = _patches_read_by_location(ti3, chart_ti2, n_chart)
            partial = n_read is not None

    from workflow.measurement_report import PATCH_IDENTITY_TOL
    differs = device_values_differ(chart_ti2, ti3, tol=PATCH_IDENTITY_TOL)
    if differs:
        return ImportVerdict(False, tr(
            "the measured device values do not agree with the chart's patches, "
            "so the readings do not line up with this chart"),
            n_chart=n_chart or 0, n_measured=n_got)
    if differs is None:
        log.info("import: the device values of %s could not be compared with "
                 "%s; the import continues", Path(ti3).name, Path(chart_ti2).name)
    return ImportVerdict(True, "", partial=partial, n_chart=n_chart or 0,
                         n_measured=n_got, n_read=n_read)


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


def complete_from_turned_order(ti3: Path, chart_ti2: "Path | None") -> int:
    """Give a measurement of the turned i1Profiler export the chart's own
    patch ids and names, in the chart's order (§I.14).

    Call it on the COPY, after :func:`assess` has said ``turned_order``.
    Returns how many rows were written; 0 means the file did not pair
    through the turned order after all and was left untouched.
    """
    if chart_ti2 is None:
        return 0
    from workflow.i1profiler_turned import reorder_turned_measurement
    n = reorder_turned_measurement(ti3, chart_ti2)
    if n:
        log.info("import: %d readings paired with %s through its turned "
                 "i1Profiler order", n, Path(chart_ti2).name)
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
    # THROUGH `expected_patches`, NOT A `NUMBER_OF_SETS` OF ITS OWN: one
    # counting rule, in one place. Every patch a reader records counts, the
    # fill-up squares of ChromIQ's layout engine included (Knut, #182
    # 6191934889); only printtarg's `SAMPLE_ID` 0 padding, which no reader
    # records, is left out.
    if ti2 is None:
        return 0
    from workflow.measurement_state import expected_patches
    return int(expected_patches(Path(ti2)) or 0)


def _patches_unread(ti3: Path, ti2: "Path | None") -> bool:
    """Whether a measurement holding at least as many rows as the chart has
    patches still lacks a reading for one of them, judged by location.

    Every patch counts, the fill-up squares of ChromIQ's layout engine
    included (Knut, #182 6191934889). The same question
    `measurement_state.classify` asks; ``False`` when the files cannot be
    compared by location, which keeps the count's answer.
    """
    if ti2 is None:
        return False
    from workflow.measurement_state import unread_locations
    return bool(unread_locations(ti3, ti2))


def _patches_read_by_location(ti3: Path, ti2: "Path | None",
                         n_chart: int) -> "int | None":
    """How many of the chart's *n_chart* patches (fill-up squares included)
    *ti3* has a reading for, when the location question finds one unread
    (`_patches_unread`);
    ``None`` when none is, or the files cannot be compared by location."""
    if ti2 is None:
        return None
    from workflow.measurement_state import unread_locations
    unread = unread_locations(ti3, ti2)
    if not unread:
        return None
    return max(0, n_chart - len(unread))


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
