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
    n_got = int(measured.n_patches or 0)

    if n_chart:
        if n_got > n_chart:
            # NOT a partial. More readings than the chart has patches means it
            # is a measurement of something else.
            return ImportVerdict(False, tr(
                "the chart has {chart} patches, but this file holds {got} "
                "measurements, so it is a measurement of a different chart"
            ).format(chart=n_chart, got=n_got), n_chart=n_chart, n_measured=n_got)
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


def _chart_patch_count(ti2: "Path | None") -> int:
    """How many patches the chart has, or 0 when that cannot be known.

    0 means "do not judge by count" rather than "the chart is empty": a run
    whose chart file is missing must not have every measurement refused for
    holding more patches than nothing.
    """
    # FROM THE HEADER, not by parsing it as a measurement. A `.ti2` carries
    # device values and no XYZ, so `parse_ti3` raises "No XYZ or Lab columns"
    # on every chart — which returned 0 here, silently switched the count check
    # off, and let a partial through as an ordinary import. The same one-line
    # read the Measure tab already uses (`tab_measure._chart_patch_count`).
    import re
    if ti2 is None:
        return 0
    try:
        m = re.search(r"NUMBER_OF_SETS\s+(\d+)",
                      Path(ti2).read_text(errors="replace"))
    except OSError:
        return 0
    return int(m.group(1)) if m else 0
