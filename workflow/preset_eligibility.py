"""Can this CHART answer the rows a report asks of it? (#182, Knut, beta 22)

Knut, on #182:

    *"the function button I specified in Create Chart, below the preset
    selection dropdown, which opens a window listing all the presets that
    fulfil the requirements for verification on a specified report type and
    judge against selection. […] it is important if any one-page preset has
    what it needs for verification measurements and the reporting, so the
    button mentioned in Create Chart opening a window with a list of
    compatible presets should highlight especially those charts suitable for
    verification."*

and, in the same message, that the check must cover *"the required chart size
and the patches that must be present to detect if a chart is usable for the
verification for these metrics, and all the other metrics"*.

**THERE IS NO SECOND OPINION IN HERE.** Every condition this module applies is
applied by :mod:`workflow.measurement_report` itself, over a chart that has not
been printed yet. That is possible because every eligibility test in the report
reads **device RGB and sample ids only**:

* :func:`~workflow.measurement_report.grey_balance_block` counts grey patches
  and distinct levels off the device column;
* :func:`~workflow.measurement_report.ramps_block` counts steps in the 30 to
  70 % band off the device column;
* :func:`~workflow.measurement_report.gamut_populations_block` takes the
  surface patches off the device column and the size of the outer quarter off
  the count of referenced patches;
* :func:`~workflow.measurement_report.control_strip_block` reads a
  DECLARATION, which :func:`workflow.control_strip.declare_for_chart` builds
  out of the chart's own device values;
* the five ΔE00 rows are gated by the patch count alone
  (:func:`~workflow.measurement_report._stats`, ``small_sample``).

None of them looks at a measured colour to decide whether a row is
*answerable*. So :func:`chart_row_values` builds the report a perfect print of
this chart would produce, hands it to
:func:`~workflow.measurement_report.row_values`, and returns the report's own
answer. A changed threshold in the report changes this window on the same day,
which is the whole point: two answers that disagree is the fault this project
keeps finding.

**WHAT THE STAND-IN REPORT CLAIMS, AND WHAT IT DOES NOT.**

* ``sheet_kind`` is ``"verification"``: the question is what the chart can do
  *when used as a verification sheet*, which is the question asked.
* ``reference_source`` is **read off the chart**, not assumed. A colorimetric
  reference is written only beside a chart built FROM PROFILE GAMUT
  (:func:`workflow.verification_print.chart_conversion_state`), and no preset
  ships one, so the three reference rows read ``needs_reference_file`` for
  every preset on the list. That is not a pessimistic guess, it is the state,
  and the row's own remedy text already says what to do about it. The CURRENT
  chart in Create Chart is the case where the answer differs, and B8-612 is
  where that was built: Knut asked the same check to run against it
  *"including if the current chart has applied the 'From Profile Gamut'
  feature"*, so a converted chart is modelled with its own declared corners
  and those three rows are answered.
* the measured colours are the chart's own aim values, so every ΔE00 is zero.
  Nothing in this module reads a number out of the stand-in report; only the
  reasons are read.

No Qt in here.
"""
from __future__ import annotations

import contextlib
import fnmatch
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from workflow import compliance_sets as CS
from workflow import measurement_report as MR
from workflow.ti3_analysis import Ti3ParseError, parse_ti3

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# What "made for verification" means, in numbers
# ---------------------------------------------------------------------------
#: Knut: *"Most preset groups for instruments and medium and small paper sizes
#: have at least one chart preset with a lower patch count, from about 80
#: patches to a few hundred patches. These are the presets made especially with
#: the thought they may be used for verification."*
#:
#: **One printed page.** His words ("any one-page preset"), and the reason is
#: the job: a verification is a check you run often, and a check that costs
#: four sheets and four strip-reading sessions is one nobody runs.
VERIFICATION_MAX_PAGES = 1

#: **"A few hundred patches."** Measured on the shipped set, 2026-09-19: the
#: one-page built-ins run 77, 84, 84, 84, 84, 88, 143 … 572, 572, **588**, and
#: then jump to **616**, 648, 648, 800, 1144, 1404, 3250, 3430. 600 sits in the
#: set's own gap, so the line is drawn where the charts themselves already
#: separate, not at a round number that cuts through a family.
VERIFICATION_MAX_PATCHES = 600

#: **NO LOWER BOUND IS IMPOSED, and that is deliberate.** S2w's outer-gamut
#: rule already sets one: the top quarter must hold 20 patches, so a chart
#: needs ``ceil(n / 4) >= 20``, i.e. **77** patches. The smallest one-page
#: built-in has exactly 77 and answers every row. Writing "80" beside that, on
#: the strength of the word "about" in a sentence of Knut's, would withhold the
#: star from a chart that meets every condition the code actually applies.
#: The floor is the rows, and the rows are checked directly.


# ---------------------------------------------------------------------------
# Which shortfalls are the CHART's to fix
# ---------------------------------------------------------------------------
#: A row can be withheld for two quite different kinds of reason, and the star
#: must only count the first:
#:
#: * **the chart is short of patches** — a longer grey ramp, more saturated
#:   colours, more patches full stop. A different preset fixes it.
#: * **the chart was built or declared differently** — it carries no
#:   colorimetric reference (build it FROM PROFILE GAMUT) or declares no
#:   control strip (drop a sidecar beside it). No preset on the list fixes
#:   those, because no preset ships either; marking every preset down for them
#:   would leave the star on nothing at all and say nothing to anybody.
#:
#: Both are shown in the window. Only the first decides the star.
PATCH_SHORTFALL_REASONS: "frozenset[str]" = frozenset({
    MR.REASON_NO_GREYS,                  # no grey patches on the chart
    MR.REASON_TOO_FEW_STEPS,             # the grey ramp is too short
    MR.REASON_GREY_STEPS_BUNCHED,        # its steps are bunched (B8-483)
    MR.REASON_NO_WHITE,                  # it does not reach white
    MR.REASON_NO_BLACK,                  # it does not reach black
    MR.REASON_NO_RAMP,                   # no 30-70 % tone ramp
    MR.REASON_RAMP_STEPS_BUNCHED,        # its steps are bunched (K31 rule A)
    # K31 option (a): a FROM PROFILE GAMUT chart's neutral aims. A larger
    # chart carries more of them, so it is the chart's size that is short.
    MR.REASON_TOO_FEW_NEUTRAL_AIMS,
    MR.REASON_NEUTRAL_AIMS_BUNCHED,
    MR.REASON_NEUTRAL_AIMS_NO_WHITE,
    MR.REASON_NEUTRAL_AIMS_NO_BLACK,
    # K40-2: the tone row of such a chart, on its neutral aims
    MR.REASON_RAMP_TOO_FEW_NEUTRAL_AIMS,
    MR.REASON_RAMP_NEUTRAL_AIMS_BUNCHED,
    MR.REASON_SMALL_SAMPLE,              # under 20 patches: no highest 5 %
    MR.REASON_TOO_FEW_SURFACE_PATCHES,   # under 10 on the cube surface
    MR.REASON_TOO_FEW_OUTER_PATCHES,     # under 20 in the top chroma quarter
})

#: The other side of the same coin, listed rather than implied so that
#: :func:`classified_reasons` can prove the two cover everything the
#: eligibility path can produce. A reason that is in neither set is a reason
#: this window would silently mis-file, and the guard fails on it.
OTHER_SHORTFALL_REASONS: "frozenset[str]" = frozenset({
    MR.REASON_NEEDS_REFERENCE_FILE,      # build it FROM PROFILE GAMUT
    MR.REASON_NO_REFERENCE,              # the file carries no aim values
    MR.REASON_NO_CONTROL_STRIP,          # the chart declares no strip
    MR.REASON_CONTROL_STRIP_TOO_SMALL,   # the declared strip is too short
    MR.REASON_NO_CORNERS,                # no patch at a solid corner
    # #182 K49, (b2): the paper row on a chart with no patch printed with
    # no ink. A chart-file matter like the corners above, and kept out of
    # the star for the same reason: it decided none before (the row read
    # needs_reference_file on every preset).
    MR.REASON_NO_PAPER_PATCH,
    MR.REASON_NOT_COMPUTED,              # the block is absent (old report)
    MR.REASON_NO_DEVICE_VALUES,          # the file carries no device values
})

#: A preset whose page grid does not exist yet: a printtarg preset is laid
#: out when printtarg runs, and a `.ti1` carries no grid. Only this window can
#: meet it, since every measured sheet was laid out, so it lives here and not
#: among the report's own codes.
REASON_EVENNESS_LAID_OUT_LATER = "evenness_laid_out_later"

#: **K40-1 (Knut, #182 5832026677): A PRINTTARG PRESET IS LAID OUT BEHIND THE
#: SCENES** (:mod:`workflow.preset_layout`), so "laid out later" is left only
#: for a caller that passes no layout at all. These three are what that can
#: say instead: still being laid out (transient, the window shows it as
#: working), printtarg not found, or printtarg refusing the preset. All three
#: are about the tools and the preset's files, not its size.
from workflow.preset_layout import (REASON_LAYING_OUT as REASON_EVENNESS_LAYING_OUT,  # noqa: E402
                                    REASON_LAYOUT_NO_TOOL as REASON_EVENNESS_LAYOUT_NO_TOOL,
                                    REASON_LAYOUT_REFUSED as REASON_EVENNESS_LAYOUT_REFUSED)

#: **EVENNESS ACROSS THE SHEET: A THIRD KIND OF SHORTFALL, THE LAYOUT'S.**
#: (Knut, 2026-09-22.) A page grid under 9 by 9, an area with no patch, or too
#: few patches per area for the sheet's noise to stay under the limit: a
#: larger chart fixes each of them, so they are shown as missing like any
#: patch shortfall. They do NOT decide the star, and that is a question put to
#: Knut rather than an answer (docs/design/measurement_report_limits.md §16,
#: Q-E4): at 1.5 the rows want about 30 patches in every ninth of the page,
#: roughly 270 on one page, and the verification presets the star was made
#: for are deliberately 77 to 204. Counting them would take the star off nearly
#: every chart it exists to mark.
LAYOUT_SHORTFALL_REASONS: "frozenset[str]" = frozenset({
    MR.REASON_EVENNESS_GRID_TOO_SMALL,
    MR.REASON_EVENNESS_EMPTY_AREA,
    MR.REASON_EVENNESS_NOISY_PAIRWISE,
    MR.REASON_EVENNESS_NOISY_FROM_MEAN,
    # #182 E2: no page of 9 by 9 covers 75 % of its paper. A chart laid out
    # to fill more of the page answers it, so it is the layout's shortfall.
    MR.REASON_EVENNESS_PAGE_COVERAGE,
})
#: …and the evenness codes that are about the chart FILE, not its size: no
#: layout beside it, locations that do not read as strip and row, a preset
#: that has not been laid out yet (printtarg decides its grid when it runs),
#: and a chart whose files do not say where its patch block sits (#182 E2).
OTHER_SHORTFALL_REASONS = OTHER_SHORTFALL_REASONS | frozenset({
    MR.REASON_EVENNESS_NO_LAYOUT,
    MR.REASON_EVENNESS_NO_POSITIONS,
    REASON_EVENNESS_LAID_OUT_LATER,
    MR.REASON_EVENNESS_NO_PAGE_GEOMETRY,
    # K40-1: a printtarg preset laid out behind the scenes
    REASON_EVENNESS_LAYING_OUT,
    REASON_EVENNESS_LAYOUT_NO_TOOL,
    REASON_EVENNESS_LAYOUT_REFUSED,
})

#: **CHROMIQ'S OWN TWO REPEATABILITY ROWS ARE NOT IN EITHER SET ABOVE, because
#: this window never asks them.** `rows_asked` filters them out through
#: `compliance_sets.POPULATION_MAY_BE_ABSENT`, so their four reason codes
#: cannot reach this module and must not be classified here: a code in
#: `classified_reasons` that nothing can produce is a sentence nobody will
#: ever read, and the pack's own coverage guard would then demand a preset
#: pair demonstrating a boundary no preset can cross.


def classified_reasons() -> "frozenset[str]":
    """Every reason this module knows how to file. The guard's subject."""
    return (PATCH_SHORTFALL_REASONS | OTHER_SHORTFALL_REASONS
            | LAYOUT_SHORTFALL_REASONS)


# ---------------------------------------------------------------------------
# The metrics only a FROM PROFILE GAMUT chart can answer
# ---------------------------------------------------------------------------
#: Knut, beta 25, on the eleven "by Pharmacist" presets: *"These cannot be used
#: for verification in many cases, because when assigning colors using 'From
#: Profile Gamut' the chart image must be recreated to be able to print it, and
#: that is not possible because these charts do not have a proper layout and
#: come with pre-made tif files. […] I prefer that these are noted as 'not
#: usable for verification using From Profile Gamut' and then also mention
#: which metrics cannot be fulfilled."*
#:
#: These are those metrics: the three rows `compliance_sets` marks ``ref``,
#: which is the status meaning *judged against a colorimetric reference*. A
#: reference is written beside a chart only when the chart was built FROM
#: PROFILE GAMUT (:func:`workflow.verification_print.chart_conversion_state`),
#: so a sheet that cannot be laid out again can never acquire one.
#:
#: DERIVED FROM THE ROW TABLE, never typed out, and
#: `test_the_gamut_only_metrics_are_the_rows_the_report_itself_withholds`
#: proves on a REAL preset chart that these are exactly the rows
#: `measurement_report` withholds with ``needs_reference_file``. Two lists that
#: could drift is the fault this project keeps finding.
def gamut_only_rows() -> "tuple[str, ...]":
    """The row ids no preset chart can answer, in table order.

    #182 K49, (b2): since Knut's "Yes" (5841092535) the paper row is
    compared with the profile's media white on any chart with a paper patch,
    so it left this list; the two solid rows stay, because only a chart whose
    solids are printed raw can answer them (`MR.ROWS_ON_RAW_SOLIDS`)."""
    return tuple(r.id for r in CS.ROWS if r.status == "ref"
                 and r.id in MR.ROWS_ON_RAW_SOLIDS)


def is_patch_shortfall(reason: "str | None") -> bool:
    """Whether a different patch set would answer this row."""
    return bool(reason) and reason in PATCH_SHORTFALL_REASONS


# ---------------------------------------------------------------------------
# The stand-in report
# ---------------------------------------------------------------------------
def _evenness_grid_for(chart: Path, recipe: "dict | None",
                       lay_out: bool = False) -> dict:
    """Where every patch of *chart* will sit, or the reason nobody knows yet.

    * a laid-out chart (a ``.ti2``, or a ``.ti1`` with its ``.ti2`` beside it,
      as the prebuilt bundles ship): read by the report's own
      :func:`~workflow.measurement_report.chart_grid`, exactly;
    * a preset laid out by PRINTTARG (K40-1): printtarg run on a copy of it,
      behind the scenes (:mod:`workflow.preset_layout`), and the ``.ti2`` it
      wrote read by the same ``chart_grid``. Without *lay_out* the layout is
      queued to a background thread and the answer until it arrives is
      "being laid out";
    * a preset with an engine layout recipe: the engine's own layout
      arithmetic (:func:`_predicted_grid`), with no file written;
    * anything else, a caller that passed no layout: "laid out later".
    """
    if chart.suffix.lower() == ".ti2":
        return MR.chart_grid(chart)
    beside = chart.with_suffix(".ti2")
    if beside.is_file():
        return MR.chart_grid(beside)
    from workflow import preset_layout as PL
    if PL.is_printtarg_spec(recipe):
        return PL.grid_for(chart, recipe, wait=lay_out)
    if recipe:
        try:
            return _predicted_grid(chart, recipe)
        except Exception as exc:      # noqa: BLE001 — an estimate, never a gate
            log.info("could not lay out %s for the evenness rows: %s",
                     chart, exc)
    return {"reason": REASON_EVENNESS_LAID_OUT_LATER}


def _predicted_grid(chart: Path, recipe: dict) -> dict:
    """The page grid the layout engine will give *chart* under *recipe*.

    The same chokepoint Create Chart's own capacity estimate goes through
    (`instruments.geom_from_build_kwargs` then `geometry.compute`), and the
    same per-page strip count `ti2_writer` writes into ``PASSES_IN_STRIPS2``.
    `side_stamp` is left at `build_chart`'s own default, which is the app's.
    `tests/test_evenness_across_the_sheet.py` builds real presets and holds
    this prediction to the ``.ti2`` the build wrote.
    """
    from workflow.layout_engine import geometry, instruments, papers
    from workflow.layout_engine.presets import LayoutRecipe
    rec = LayoutRecipe.from_dict(dict(recipe))
    kw = rec.build_kwargs()
    npat = patch_count(chart)
    if npat < 1:
        raise ValueError("no patches")
    kw.setdefault("side_stamp", True)
    kw["area_target_count"] = npat
    geom = instruments.geom_from_build_kwargs(kw)
    w_mm, h_mm = papers.dimensions_mm(kw["paper"])
    lay = geometry.compute(geom, w_mm, h_mm, npat)
    steps = lay.steps_in_pass or 1
    per_page = lay.patches_per_page or 0
    strips, remaining = [], lay.total_patches
    for _pg in range(max(1, lay.pages)):
        on_page = min(per_page, remaining) if per_page else remaining
        strips.append((on_page + steps - 1) // steps)
        remaining -= on_page
    # #182 E2: each page's coverage, from the same geometry widened the way
    # "Measured from Preview" widens a built chart's.
    from workflow.page_coverage import predicted_page_coverage
    cov = predicted_page_coverage(rec, npat)
    grid = MR.evenness_grid_from_layout(strips, steps, lay.total_patches,
                                        coverage=cov["pages"])
    grid["coverage_source"] = cov["source"]
    return grid


def _estimated_evenness(chart: Path, recipe: "dict | None",
                        lay_out: bool = False) -> dict:
    """The evenness block a TYPICAL print of *chart* would give.

    The grid is exact where the chart is laid out (see
    :func:`_evenness_grid_for`); the residuals cannot be known before the sheet
    is printed, so each patch gets one of the size the F1 measurement found on
    a real sheet (:data:`~workflow.measurement_report.EVENNESS_TYPICAL_SIGMA`),
    from a fixed seed, and the report's own arithmetic runs on them. The block
    says it is an estimate.
    """
    grid = _evenness_grid_for(chart, recipe, lay_out)
    if "reason" in grid:
        block = MR.evenness_from_residuals(grid, {})
    else:
        rng = np.random.default_rng(MR.EVENNESS_SEED)
        n = len(grid["ids"]) if "ids" in grid else len(grid["slot"])
        noise = rng.normal(0.0, MR.EVENNESS_TYPICAL_SIGMA, (n, 3))
        block = MR.evenness_from_residuals(
            grid, noise, shuffles=MR.EVENNESS_ESTIMATE_SHUFFLES)
    block["estimated"] = True
    return block


def _perfect_print(chart: Path, recipe: "dict | None" = None,
                   lay_out: bool = False) -> dict:
    """The report a flawless print of *chart*, measured as a verification
    sheet, would produce. Every block comes from :mod:`measurement_report`.

    The one exception is evenness, which a flawless print cannot answer: its
    noise IS the imperfection. That block is the report's own arithmetic on an
    estimated typical print (:func:`_estimated_evenness`)."""
    data = parse_ti3(chart)
    if not len(data.rgb):
        raise Ti3ParseError("The chart carries no device RGB columns.")
    rgb100 = MR._rgb_to_0_100(np.asarray(data.rgb, dtype=float))
    lab = [MR.xyz_to_lab((x / 100.0, y / 100.0, z / 100.0)) for x, y, z in data.xyz]
    # The aim values ARE the chart's own design colours, which is exactly what
    # `_reference_labs` reads off the sibling .ti2 of a printed preset chart.
    # Setting the measured values equal to them models a flawless print; no
    # eligibility test in the report reads either, only their presence.
    ref = {sid: tuple(lab[i]) for i, sid in enumerate(data.sample_ids)}
    n = len(data.sample_ids)
    #: K31 option (a): a FROM PROFILE GAMUT chart's grey steps are its neutral
    #: AIMS, read from the reference beside it, so a flawless print of it
    #: measures exactly those aims.
    aims = _colorimetric_aims(chart)
    if aims is not None:
        grey_lab = [tuple(aims.get(sid, lab[i]))
                    for i, sid in enumerate(data.sample_ids)]
        grey = MR.grey_balance_block(rgb100, grey_lab, aims, data.sample_ids,
                                     neutral_aims=aims,
                                     corner_ids=set(_declared_corners(chart)[0]
                                                    or ()))
    else:
        grey = MR.grey_balance_block(rgb100, lab, ref, data.sample_ids)

    # **DOES THIS CHART CARRY THE PROFILE'S OWN CONVERSION?** (B8-612.)
    # A preset never does, which is why this used to be the constant
    # "design" -- see the module docstring. The CURRENT chart in Create Chart
    # can, and Knut asked for that difference to be honoured: *"the check if
    # the current chart fulfils all the metric requirements, including if the
    # current chart has applied the 'From Profile Gamut' feature"*.
    #
    # ASKED OF THE FILE, never of a flag a caller passes in, so no window can
    # claim a reference a chart does not have. `chart_conversion_state` is the
    # Print tab's own predicate (§3.1a), so there is one answer to "is this a
    # converted chart" in the application, not two.
    corner_ids, corner_devices = _declared_corners(chart)
    colorimetric = corner_ids is not None
    report: dict = {
        "patches": n,
        "sheet_kind": "verification",
        "is_verification": True,
        "reference_source": "colorimetric" if colorimetric else "design",
        "de00": MR._stats([0.0] * n),
        "grey_balance": grey,
        # K40-2: a FROM PROFILE GAMUT chart's tone ramp takes its neutral
        # aims too, measured (flawlessly) at those aims
        "ramps_30_70": (MR.ramps_block(
            rgb100, grey_lab, ref, data.sample_ids, neutral_aims=aims,
            corner_ids=set(_declared_corners(chart)[0] or ()))
            if aims is not None
            else MR.ramps_block(rgb100, lab, ref, data.sample_ids)),
        "gamut_populations": MR.gamut_populations_block(
            rgb100, lab, ref, data.sample_ids),
        "control_strip": MR.control_strip_block(
            lab, ref, data.sample_ids, _declaration_it_would_get(chart)),
        "evenness": _estimated_evenness(chart, recipe, lay_out),
    }
    if colorimetric:
        # The three reference rows are computed from this block and nothing
        # else, so it is built by the report's OWN `corners_block` rather than
        # by a second reading of what a corner is.
        report["corners"] = MR.corners_block(rgb100, lab, ref, data,
                                             corner_ids, corner_devices)
    report["condition_reference"] = _condition_it_would_get(
        report, rgb100, lab, colorimetric)
    return report


def _condition_it_would_get(report: dict, rgb100, lab,
                            colorimetric: bool) -> dict:
    """#182 K49, (b2): what the paper row and the two solid rows of a
    flawless print of this chart would be compared with, asked of the
    report's own predicates.

    * **The paper:** any chart with a patch printed with no ink
      (`MR.paper_white_row`, the report's own test) is compared with its
      profile's media white. A verification is always measured in a run with
      a profile, so a flawless print reads 0; a chart with no such patch
      cannot answer.
    * **The solids:** a FROM PROFILE GAMUT chart prints its solids raw and is
      compared with the profile's prediction; any other chart is printed
      through its profile as a verification, so its solids are not the
      printer's own and the rows stay withheld, with the remedy the report's
      ``needs_reference_file`` carries (build it FROM PROFILE GAMUT)."""
    if colorimetric:
        corners = {c.get("name"): c for c in report.get("corners") or []}
        w = corners.get("W")
        paper = ({"from": MR.CONDITION_FROM_PROFILE, "de": 0.0}
                 if w and w.get("present")
                 else {"from": MR.CONDITION_NO_PAPER_PATCH})
        present = [n for n in MR.SOLID_CORNERS
                   if corners.get(n) and corners[n].get("present")]
        solids = ({"from": MR.CONDITION_FROM_PROFILE,
                   "de": {n: 0.0 for n in present},
                   "dhab": {n: 0.0 for n in present
                            if n in MR.HUE_CORNERS}}
                  if present else {"from": MR.CONDITION_NO_CORNERS})
    else:
        paper = ({"from": MR.CONDITION_FROM_PROFILE, "de": 0.0}
                 if MR.paper_white_row(lab, rgb100) is not None
                 else {"from": MR.CONDITION_NO_PAPER_PATCH})
        solids = {"from": MR.CONDITION_BEFORE_PRINTING}
    return {"paper": paper, "solids": solids}


def _declared_corners(chart: Path) -> "tuple[list | None, dict | None]":
    """``(corner sample ids, {id: device})`` for a FROM PROFILE GAMUT chart.

    ``(None, None)`` for every other chart, which is every preset ChromIQ
    ships and every chart laid out the ordinary way.

    A chart built FROM PROFILE GAMUT is printed in the profile's own numbers,
    so what comes off the press IS the aim, and the sheet carries that aim
    beside it as ``<stem>-reference.ti3`` with ``CHROMIQ_CORNER_IDS`` naming
    the eight patches printed at exact cube corners
    (:func:`workflow.gamut_target.write_colorimetric_reference`).

    **A CHART WHOSE REFERENCE HAS GONE IS NOT TREATED AS CONVERTED.**
    `chart_conversion_state` answers ``converted-reference-missing`` when the
    sidecar claims one and the file is not there; there is then nothing to
    read the corners out of, so the three rows fall back to
    ``needs_reference_file`` and the remedy that reason carries -- build it
    FROM PROFILE GAMUT -- is the right instruction for a sheet whose reference
    has been deleted.
    """
    from workflow.verification_print import (STATE_CONVERTED,
                                             chart_conversion_state,
                                             colorimetric_reference_for)
    if chart_conversion_state(chart) != STATE_CONVERTED:
        return None, None
    from workflow.gamut_target import read_colorimetric_reference
    try:
        blob = read_colorimetric_reference(colorimetric_reference_for(chart))
    except (OSError, ValueError):
        return None, None
    if not blob:
        return None, None
    ids = list(blob.get("corner_ids") or [])
    devices = dict(blob.get("devices") or {})
    if not ids or not devices:
        return None, None
    return ids, devices


def _colorimetric_aims(chart: Path) -> "dict[str, tuple] | None":
    """``{sample id: aim Lab}`` of a chart built FROM PROFILE GAMUT, read from
    the colorimetric reference beside it, or None for every other chart and
    for one whose reference has gone (the same door as
    :func:`_declared_corners`, so the two cannot disagree about which chart is
    converted)."""
    from workflow.verification_print import (STATE_CONVERTED,
                                             chart_conversion_state,
                                             colorimetric_reference_for)
    if chart_conversion_state(chart) != STATE_CONVERTED:
        return None
    from workflow.gamut_target import read_colorimetric_reference
    try:
        blob = read_colorimetric_reference(colorimetric_reference_for(chart))
    except (OSError, ValueError):
        return None
    labs = (blob or {}).get("labs") or {}
    return {str(k): tuple(v) for k, v in labs.items()} or None


def _declaration_it_would_get(chart: Path) -> "dict | None":
    """The control strip this chart would carry once ChromIQ files it.

    **ASKED OF `workflow.control_strip`, NOT GUESSED, AND NOT ASKED OF THE
    DISK.** No preset ships a `.control-strip.json`, so reading one off disk
    would have this window tell a user that every preset declares no control
    strip -- which was true until B8-405 landed the same week and is now false:
    ChromIQ writes the declaration out of the chart's own patches when a
    verification chart is filed. `declare_for_chart(..., write=False)` is that
    module's own door for asking without touching the disk, and the answer it
    gives here is the answer the chart will really have.

    A chart that already declares one (a `.ti1` carrying `CONTROL_STRIP_IDS`,
    or a sidecar somebody else wrote) keeps its own declaration, because that
    is what `declare_for_chart` does with it.
    """
    existing = MR.control_strip_declaration(chart, chart)
    if existing is not None:
        return existing
    from workflow import control_strip as CSP
    res = CSP.declare_for_chart(chart, write=False)
    if not res.written:
        return None
    return {"name": CSP.STRIP_NAME, "ids": list(res.selection.ids),
            "source": "sidecar", "file": CSP.declaration_path(chart).name}


#: Keyed by (resolved path, mtime, size), so a preset the user re-saves is read
#: again and a shipped asset is read once per session.
#:
#: **RE-MEASURED 2026-09-19 (round 27b), because the number that stood here was
#: wrong by a factor of six and it is the number the button's speed was
#: budgeted against.** It said 0.43 s for all 177 built-in charts and called
#: that "inside what a button press may take". Timed on this host with a clock
#: around the loop:
#:
#: ===============================================  ========
#: assessing all 177 built-in charts, cold          2.73 s
#: the same, before `control_strip.select_strip`
#: was vectorised                                   5.15 s
#: the same, warm (this cache)                      0.004 s
#: ===============================================  ========
#:
#: So it is NOT inside a button press, which is why `TabChart` fills this cache
#: while the tab is idle and puts a busy cursor on the click that finds it
#: empty. A measured 0.43 s would have needed neither.
_CACHE: "dict[tuple, dict]" = {}

#: The same trick for :func:`patch_count`, and for the same reason: it is the
#: OTHER half of what a button press pays. `verification_preset_rows` calls it
#: once per preset to build the list, which is 177 full `.ti1` parses — 280 ms,
#: measured — and it was paid again on every open of the window because nothing
#: remembered it. Keyed identically, so a preset the user re-saves is counted
#: again.
_PATCHES: "dict[tuple, int]" = {}


def chart_row_values(chart: "str | Path",
                     recipe: "dict | None" = None, *,
                     lay_out: bool = False) -> "dict[str, dict]":
    """``{row_id: {"value", "reason", …}}`` for a chart that is not printed yet.

    The report's own :func:`~workflow.measurement_report.row_values`, over the
    stand-in report of :func:`_perfect_print`. A row with a ``value`` is a row
    this chart can answer; a row with a ``reason`` is one it cannot, and the
    reason is the report's own code.

    *recipe* is the preset's layout: an engine recipe, or a printtarg spec
    (:func:`workflow.preset_layout.layout_for_user_preset`). A printtarg
    layout nobody has worked out yet is queued to the background and its two
    evenness rows read "being laid out"; with *lay_out* it is worked out here
    and now instead (scripts, tests, and the background thread itself).

    Raises :class:`~workflow.ti3_analysis.Ti3ParseError` when the file cannot
    be read as a chart at all.
    """
    from workflow import preset_layout as PL
    p = Path(chart)
    try:
        key = _values_key(p, recipe)
    except OSError as exc:
        raise Ti3ParseError(str(exc)) from exc
    hit = _CACHE.get(key)
    if hit is None:
        hit = MR.row_values(_perfect_print(p, recipe, lay_out))
        if not (PL.is_printtarg_spec(recipe) and lay_out):
            _CACHE[key] = hit
        else:
            # laid out just now: file it under the key that says so
            _CACHE[key[:-1] + (PL.state(p, recipe),)] = hit
    return hit


class _OnePass(threading.local):
    memo: "dict | None" = None


_PASS = _OnePass()


@contextlib.contextmanager
def one_pass():
    """Within this block, on this thread, each chart's files are read off the
    disk once (B8-1161).

    The presets window asks :func:`values_ready`, :func:`assess` and
    :func:`made_for_verification` about the same chart in one refresh, and
    each of them built :func:`_values_key` again: a ``realpath``, a ``stat``
    of the chart, of its reference and of every page image beside it, three
    times over for 220 presets. With the background thread busy, every one of
    those calls waits for the GIL on the way back, and the window stalled for
    up to 1.8 s (measured on screen). Nothing on disk that the key reads
    changes within one redraw, so it is read once. Thread-local: the
    background thread never sees it."""
    outer = _PASS.memo
    if outer is None:
        _PASS.memo = {}
    try:
        yield
    finally:
        if outer is None:
            _PASS.memo = None


def _values_key(p: Path, recipe: "dict | None") -> tuple:
    """The key :func:`chart_row_values` files an answer under. Raises OSError
    when the chart cannot be read."""
    memo = _PASS.memo
    if memo is None:
        return _read_values_key(p, recipe)
    mk = (str(p), repr(sorted((recipe or {}).items())))
    hit = memo.get(mk)
    if hit is None:
        try:
            hit = memo[mk] = _read_values_key(p, recipe)
        except OSError as exc:
            memo[mk] = exc
            raise
    elif isinstance(hit, OSError):
        raise hit
    return hit


#: ``str(path) -> str(path.resolve())`` for the session (B8-1161): a
#: ``realpath`` is an ``lstat`` per folder on the way, asked for every preset
#: on every redraw of the presets window. What the key must notice, a chart
#: that changed, it notices through the ``stat`` beside it.
_RESOLVED: "dict[str, str]" = {}


def _resolved(p: Path) -> str:
    k = str(p)
    hit = _RESOLVED.get(k)
    if hit is None:
        hit = _RESOLVED[k] = str(p.resolve())
    return hit


def _stem_files_once(folder: Path, stem: str, *tails: str) -> "list[Path]":
    """`core.file_manager.stem_files`, but within :func:`one_pass` each
    folder is listed once (B8-1161): the built-in charts share a handful of
    folders, and each of 220 presets listed its folder again."""
    from core.file_manager import _NAME_CASEFOLD, glob_escape, nfc, stem_files
    memo = _PASS.memo
    if memo is None:
        return stem_files(folder, stem, *tails)
    lk = ("ls", str(folder))
    names = memo.get(lk)
    if names is None:
        try:
            with os.scandir(str(folder)) as entries:
                names = [e.name for e in entries]
        except (OSError, ValueError):
            names = []
        memo[lk] = names
    lit = nfc(stem)
    pats = [nfc(glob_escape(lit) + t) for t in tails]
    if _NAME_CASEFOLD:
        lit = lit.lower()
        pats = [q.lower() for q in pats]
    out: "list[Path]" = []
    for name in names:
        n = nfc(name)
        if _NAME_CASEFOLD:
            n = n.lower()
        if n.startswith(lit) and any(fnmatch.fnmatchcase(n, q) for q in pats):
            out.append(Path(folder) / name)
    return out


def _read_values_key(p: Path, recipe: "dict | None") -> tuple:
    from workflow import preset_layout as PL
    st = p.stat()
    return (_resolved(p), st.st_mtime_ns, st.st_size,
            _reference_stamp(p), _layout_stamp(p),
            # the recipe decides the predicted page grid of a preset that
            # is not laid out yet, so two recipes are two answers
            repr(sorted((recipe or {}).items())),
            # …and a printtarg layout that has arrived since is a new
            # answer: "being laid out" must never be served after it
            PL.state(p, recipe) if PL.is_printtarg_spec(recipe) else ())


def values_ready(chart: "str | Path | None", recipe: "dict | None") -> bool:
    """Whether this chart's answer is known already, laid out and all, so a
    window can show it without computing anything. A chart that cannot be
    read is "ready": asking it again gives the same "cannot be checked"
    at once."""
    if chart is None:
        return True
    try:
        key = _values_key(Path(chart), recipe)
    except OSError:
        return True
    return key in _CACHE or key in _UNREADABLE


def request_values(chart: "str | Path", recipe: "dict | None") -> None:
    """Work this chart's answer out on the background thread (K40-1), laying
    it out first where printtarg lays it out. The presets window asks this
    for every preset whose answer is not known yet, shows it as working, and
    re-reads it when `preset_layout.generation()` moves."""
    from workflow import preset_layout as PL
    p = Path(chart)
    PL.request(_request_key(p, recipe), _Compute(p, recipe))


def _request_key(p: Path, recipe: "dict | None") -> tuple:
    return ("values", str(p), repr(sorted((recipe or {}).items())))


def request_queued(chart: "str | Path", recipe: "dict | None") -> bool:
    """Whether this chart's background job is waiting or running now
    (B8-1161): its answer is not known, and a window need not read the
    chart's files to find that out."""
    from workflow import preset_layout as PL
    return PL.queued(_request_key(Path(chart), recipe))


def request_finished(chart: "str | Path", recipe: "dict | None") -> bool:
    """Whether the background job :func:`request_values` queued for this
    chart has run (B8-1161). A set lookup: a window polling its waiting rows
    asks this first and reads a chart's files only once its job is done."""
    from workflow import preset_layout as PL
    return PL.finished(_request_key(Path(chart), recipe))


class _Compute:
    """A callable for the background thread (a class, not a closure, so the
    job names what it holds)."""

    def __init__(self, chart: Path, recipe: "dict | None") -> None:
        self.chart, self.recipe = chart, recipe

    def __call__(self) -> None:
        try:
            chart_row_values(self.chart, self.recipe, lay_out=True)
        except Exception:      # noqa: BLE001 - "cannot be checked" is an answer
            # an unreadable chart is an answer too, and the window must stop
            # showing it as working: `assess` gives "cannot be checked" at once
            try:
                _UNREADABLE.add(_values_key(self.chart, self.recipe))
            except OSError:
                pass


#: Keys of charts the background thread could not read, so `values_ready`
#: answers for them and the window stops showing them as working.
_UNREADABLE: "set[tuple]" = set()


def is_being_laid_out(assessment: "Assessment") -> bool:
    """Whether an assessment is still waiting for a background layout: the
    window shows such a row as working, not as short of anything."""
    return any(why == REASON_EVENNESS_LAYING_OUT
               for _rid, why in assessment.missing)


def layout_is_ready(chart: "str | Path | None",
                    recipe: "dict | None") -> bool:
    """False while this preset's printtarg layout is still being worked out
    behind the scenes; True for every other preset."""
    from workflow import preset_layout as PL
    if chart is None or not PL.is_printtarg_spec(recipe):
        return True
    p = Path(chart)
    if p.suffix.lower() == ".ti2" or p.with_suffix(".ti2").is_file():
        return True
    return PL.state(p, recipe)[0] == "done"


def layout_failure_detail(chart: "str | Path | None",
                          recipe: "dict | None") -> str:
    """printtarg's own words when it could not lay this preset out, or the
    folder it was looked for in; "" for every other preset."""
    from workflow import preset_layout as PL
    if chart is None or not PL.is_printtarg_spec(recipe):
        return ""
    p = Path(chart)
    if PL.state(p, recipe)[0] != "done":
        return ""
    got = PL.grid_for(p, recipe)
    return str(got.get("detail") or "") if "reason" in got else ""


def _layout_stamp(chart: Path) -> tuple:
    """The (mtime, size) of the ``.ti2`` beside a ``.ti1``, or ``()``: the
    evenness rows read the page grid from it, a second file, so it is part of
    the key for the reason `_reference_stamp` gives.

    #182 E2: and the page coverage reads the ``.channels.json`` and the page
    images beside that ``.ti2``, so they are part of the key as well."""
    ti2 = chart if chart.suffix.lower() == ".ti2" else chart.with_suffix(".ti2")
    out: list = []
    for p in [ti2, ti2.with_suffix(".channels.json")] + sorted(
            _stem_files_once(ti2.parent, ti2.stem, ".tif", ".TIF", ".tiff",
                             "_*.tif", "_*.TIF", "_*.tiff")):
        if p == chart:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        out.append((p.name, st.st_mtime_ns, st.st_size))
    return tuple(out)


def _reference_stamp(chart: Path) -> tuple:
    """The colorimetric reference's own (mtime, size), or ``()``.

    **PART OF THE CACHE KEY, because the answer depends on a SECOND file.**
    Since B8-612 a chart built FROM PROFILE GAMUT answers three rows a chart
    without a reference cannot, and the chart file itself does not change when
    that reference is written beside it: `_write_gamut_reference_after_adopt`
    runs after the sheet has been laid out. Keyed on the chart alone, the very
    first assessment of a freshly built gamut chart would be the one that is
    wrong, and it would stay wrong for the rest of the session.
    """
    from workflow.verification_print import colorimetric_reference_for
    try:
        st = colorimetric_reference_for(chart).stat()
    except OSError:
        return ()
    return (st.st_mtime_ns, st.st_size)


def clear_cache() -> None:
    """Forget every assessed chart (the tests, and a re-read on demand)."""
    _CACHE.clear()
    _PATCHES.clear()
    _UNREADABLE.clear()
    _RESOLVED.clear()
    from workflow import preset_layout
    preset_layout.clear_cache()
    from workflow import page_coverage
    page_coverage.clear_cache()


# ---------------------------------------------------------------------------
# What a (report type, limit set) combination asks of a chart
# ---------------------------------------------------------------------------
#: **"ALL METRICS", THE FIRST "JUDGED AGAINST" ENTRY OF THE PRESETS WINDOW**
#: (B8-974). Knut, #182 5814820283: the "Metrics answered" count covered only
#: the rows the chosen limit set switches on, and most sets leave many at
#: "-", *"thus there is no way to actually see if any of the reports could
#: fulfil ALL metrics"*. He asked for an entry that *"ignores the limit sets
#: selected thresholds"* and checks every preset and the current chart
#: *"against ALL metrics, to see which supports the most metrics"*, and for it
#: to be the default *"as we do not know what the user will pick when later
#: creating reports."* Not a limit set: nothing is judged against it and no
#: report can be bound to it, so it lives here and never in `compliance_sets`.
ALL_METRICS = "all_metrics"

#: **"ANY", THE FIRST "REPORT TYPE" ENTRY OF THE PRESETS WINDOW** (K33,
#: B8-996). Knut, #182 5816565326, asked whether "All metrics" should ignore
#: the report type too: *"No, the Report type should instead also have an
#: option called "Any", which is the default, set together with "All metrics"
#: as default for judged against. Report type and judged against shall still
#: be able to individually change if desired."* Not a report type: nothing is
#: ever generated as "Any", so it lives here and never in
#: `measurement_report.REPORT_TYPE_MENU`. It asks what ANY report a
#: verification can be made into would ask: the union, in table order, over
#: the types ChromIQ can produce for a verification measurement.
ANY_REPORT_TYPE = "any_report_type"


def _types_any_stands_for() -> "tuple[str, ...]":
    """The report types "Any" unions over: every type ChromIQ can produce
    that a verification measurement may be made into (the Printing record is
    a profiling sheet's report and asks nothing)."""
    return tuple(t for t in MR.report_types_for_kind(MR.KIND_VERIFICATION)
                 if MR.report_type_is_built(t))


def _union_in_table_order(groups) -> "tuple[str, ...]":
    seen: "set[str]" = set()
    for g in groups:
        seen.update(g)
    return tuple(r.id for r in CS.ROWS if r.id in seen)


def rows_every_metric(type_id: str) -> "tuple[str, ...]":
    """Every row a report of *type_id* can judge, whatever limit set it uses.

    "Every metric" is every row ChromIQ can compute (``now`` / ``build`` /
    ``ref``): an ``unmeasurable`` row can never carry a limit
    (`compliance_sets.limit_bearing`), so no report judges it on any chart.
    The report type still narrows ("Grey and tone check" is about three rows)
    and the Printing record still judges nothing, exactly as in
    :func:`rows_asked`; and ChromIQ's two repeatability rows stay out for the
    same reason they are out of every set there (not a property of a chart).
    On a Colour summary this is the same 18 the pre-flight counts over every
    type and set (`rows_any_report_can_ask`), but it is derived from the rows,
    not from the sets, so a user who empties a Custom column cannot shrink it.
    """
    if type_id == ANY_REPORT_TYPE:
        return _union_in_table_order(
            rows_every_metric(t) for t in _types_any_stands_for())
    if type_id == MR.REPORT_TYPE_RECORD:
        return ()
    only = MR.rows_for_report_type(type_id)
    return tuple(r.id for r in CS.ROWS
                 if r.status in ("now", "build", "ref")
                 and (only is None or r.id in only)
                 and r.id not in CS.POPULATION_MAY_BE_ABSENT)


def rows_asked(type_id: str, set_id: str,
               overrides: "dict | None" = None) -> "tuple[str, ...]":
    """The row ids a report of that type, judged against that set, asks a
    chart to supply, in table order.

    Two filters, both the application's own:

    * :func:`~workflow.measurement_report.rows_for_report_type` — which rows
      that document is ABOUT (only "Grey and tone check" narrows; the rest
      return None, meaning all of them);
    * :func:`~workflow.compliance_sets.limit_bearing` — which rows the set
      actually puts a number on. A row the set leaves at ``–`` or ``?`` is
      never judged, so a chart that cannot supply it is not short of anything.

    And one whole type asks nothing: "Printing record (not graded)" withholds
    the judgement by definition (``MeasurementReportDialog._is_record_type``),
    so no chart can be short of anything for it. Returning the set's sixteen
    rows there would mark every preset down for a document that grades none of
    them.
    """
    if set_id == ALL_METRICS:
        return rows_every_metric(type_id)
    if type_id == ANY_REPORT_TYPE:
        return _union_in_table_order(
            rows_asked(t, set_id, overrides) for t in _types_any_stands_for())
    if type_id == MR.REPORT_TYPE_RECORD:
        return ()
    limited = CS.limit_bearing(CS.effective_limits(set_id, overrides))
    only = MR.rows_for_report_type(type_id)
    return tuple(r.id for r in CS.ROWS
                 if r.id in limited and (only is None or r.id in only)
                 # …and a THIRD filter, the same set that governs the column
                 # summary and the mismatch strip
                 # (`compliance_sets.POPULATION_MAY_BE_ABSENT`). This window
                 # exists to help a user CHOOSE between charts, and neither of
                 # ChromIQ's two repeatability rows can do that: "has this
                 # chart been measured before" is not a property of a chart at
                 # all, and a chart that repeats no colour is short of nothing
                 # a preset advertises. Listing them would mark every preset
                 # down for the same two rows, which is the shape this
                 # module's two reason sets already exist to avoid. ONE set,
                 # three consumers, so the three cannot drift.
                 and r.id not in CS.POPULATION_MAY_BE_ABSENT)


#: The rows a chart's own PATCHES decide, whatever is selected above: every
#: row ChromIQ can compute at all, minus the ones a different patch set cannot
#: help with. Derived from the reason codes rather than listed by hand, so a
#: new row arrives here by itself.
def rows_the_patches_decide(values: "dict[str, dict]") -> "tuple[str, ...]":
    """Of the rows ChromIQ can compute, those whose answer on THIS chart is
    decided by its patches: answered, or withheld for a patch shortfall."""
    out = []
    for r in CS.ROWS:
        if r.status not in ("now", "build", "ref"):
            continue
        v = values.get(r.id)
        if v is None:
            continue
        if v.get("value") is not None or is_patch_shortfall(v.get("reason")):
            out.append(r.id)
    return tuple(out)


@dataclass(frozen=True)
class Assessment:
    """What one chart can answer, for one (report type, limit set) pair."""
    #: the rows the combination asks of a chart, in table order
    asked: "tuple[str, ...]"
    #: of those, the ones this chart answers
    answered: "tuple[str, ...]"
    #: of those, the ones it does not, each with the report's own reason code
    missing: "tuple[tuple[str, str], ...]"
    #: False when there was no chart file to read, or it could not be read
    checked: bool = True
    #: why not, when ``checked`` is False (an exception message, for the log)
    unreadable: str = ""

    @property
    def answers_everything(self) -> bool:
        return self.checked and not self.missing

    def missing_ids(self) -> "tuple[str, ...]":
        """Just the row ids of :attr:`missing`, without their reasons."""
        return tuple(rid for rid, _why in self.missing)

    @property
    def patch_shortfalls(self) -> "tuple[tuple[str, str], ...]":
        return tuple((rid, why) for rid, why in self.missing
                     if is_patch_shortfall(why))


UNCHECKED = Assessment(asked=(), answered=(), missing=(), checked=False)


def rows_any_report_can_ask(overrides: "dict | None" = None) -> "tuple[str, ...]":
    """Every row that ANY available report type and limit set could ask for.

    **THE PRE-FLIGHT CANNOT KNOW WHICH REPORT WILL BE MADE, AND SAID IT DID.**
    Knut, on beta 32: *"At the time of the popup message, when entering Measure
    tab, how do you know the report type and limit set asked for? We have not
    opened the Measurement Report yet at this point in the workflow, and no
    report exists. So this message must be generic, giving a count based on the
    maximum of metrics a report can check."*

    He is right, and it is a fault of logic rather than of wording: the window
    named a report type and a limit set at a moment when the user has chosen
    neither. `assess` against one pair is the correct question for the presets
    window, which is opened from a report; it is the wrong question before any
    report exists.

    So this unions the rows over every report type ChromIQ can actually build
    and every set a user can pick. The union is in table order, and a row asked
    by one combination and not another is IN it, because the chart either can
    or cannot supply that row whatever is chosen later.
    """
    from workflow.compliance_sets import SETS
    from workflow.measurement_report import (REPORT_TYPE_MENU,
                                             report_type_is_built)
    seen: "set[str]" = set()
    for tid, _name, _blurb, built in REPORT_TYPE_MENU:
        # K33: the ISO types also need their values loaded
        from workflow.measurement_report import report_type_is_built as _is_built
        built = _is_built(tid)
        if not built:
            continue
        for sd in SETS:
            seen.update(rows_asked(tid, sd.id, overrides))
    from workflow.compliance_sets import ROWS
    return tuple(r.id for r in ROWS if r.id in seen)


def assess_any(chart: "str | Path | None",
               overrides: "dict | None" = None,
               recipe: "dict | None" = None) -> Assessment:
    """One chart against everything any report could ask of it.

    The pre-flight's question, as opposed to the presets window's. See
    :func:`rows_any_report_can_ask` for why the two differ.

    The evenness noise rule needs a LIMIT, and this question has no one set:
    a row counts as one the chart can answer when it could be judged under the
    loosest limit any selectable set puts on it (:func:`loosest_limits`),
    which is the same "maximum a report can check" the row list itself is.
    """
    return assess_rows(chart, rows_any_report_can_ask(overrides),
                       limits=loosest_limits(overrides), recipe=recipe)


def loosest_limits(overrides: "dict | None" = None) -> "dict":
    """``{row_id: Limit}``, the largest numeric limit any selectable set puts
    on each row, for the pre-flight's set-independent question."""
    from workflow.compliance_sets import SETS
    out: dict = {}
    for sd in SETS:
        for rid, lim in CS.effective_limits(sd.id, overrides).items():
            if not lim.is_numeric:
                continue
            if rid not in out or lim.number > out[rid].number:
                out[rid] = CS.Limit.value(lim.number)
    return out


def assess_rows(chart: "str | Path | None",
                asked: "tuple[str, ...]", *,
                limits: "dict | None" = None,
                recipe: "dict | None" = None) -> Assessment:
    """One chart against a given set of rows. Never raises.

    `assess` decides the rows from one report type and one limit set;
    `assess_any` decides them from every combination there is. Both then ask
    the same question of the chart, and that question lives here so the two
    cannot drift apart.

    *limits* lets the one rule that depends on a limit apply here as it does
    in the report: an evenness row whose (estimated) noise is not below its
    limit is missing, with the report's own reason
    (:func:`~workflow.measurement_report.evenness_withheld`).
    """
    if chart is None:
        return Assessment(asked=asked, answered=(), missing=(), checked=False)
    try:
        values = chart_row_values(chart, recipe)
    except (Ti3ParseError, OSError) as exc:
        log.info("preset chart %s cannot be assessed: %s", chart, exc)
        return Assessment(asked=asked, answered=(), missing=(),
                          checked=False, unreadable=str(exc))
    answered, missing = [], []
    for rid in asked:
        v = values.get(rid) or {}
        withheld = (MR.evenness_withheld(rid, v, (limits or {}).get(rid))
                    if limits else None)
        if withheld:
            missing.append((rid, withheld))
        elif v.get("value") is not None:
            answered.append(rid)
        else:
            missing.append((rid, v.get("reason") or MR.REASON_NOT_COMPUTED))
    return Assessment(asked=asked, answered=tuple(answered),
                      missing=tuple(missing))


def assess(chart: "str | Path | None", type_id: str, set_id: str,
           overrides: "dict | None" = None,
           recipe: "dict | None" = None) -> Assessment:
    """One chart against one combination. Never raises.

    Under :data:`ALL_METRICS` there is no one set to take the evenness limit
    from, so it is the loosest any selectable set puts on the row, which is
    what the pre-flight's set-independent question uses too (`assess_any`).
    """
    limits = (loosest_limits(overrides) if set_id == ALL_METRICS
              else CS.effective_limits(set_id, overrides))
    return assess_rows(chart, rows_asked(type_id, set_id, overrides),
                       limits=limits, recipe=recipe)


# ---------------------------------------------------------------------------
# The star
# ---------------------------------------------------------------------------
def made_for_verification(chart: "str | Path | None", patches: int,
                          pages: int, *, relayoutable: bool = True,
                          recipe: "dict | None" = None) -> bool:
    """Whether this chart is one of the ones Knut asked to be highlighted.

    Four conditions, ANDed, and none of them depends on the two pulldowns:
    the mark says what the CHART is, so it does not flicker on and off while
    a reader compares report types.

    1. one printed page (:data:`VERIFICATION_MAX_PAGES`);
    2. :data:`VERIFICATION_MAX_PATCHES` patches or fewer;
    3. nothing withheld that a different patch set would supply, over every
       row ChromIQ can compute. Not "every row the selection asks", because a
       selection may ask for a colorimetric reference no preset carries.
    4. **the sheet can be laid out again** (*relayoutable*). A preset that
       ships finished page TIFFs is printed as the image it comes with, so it
       can never be built FROM PROFILE GAMUT and can never carry the
       colorimetric reference :func:`gamut_only_rows` needs. Knut, beta 25:
       *"when ticking 'Show only the presets made for verification' these
       presets should not show up in the list."* The caller knows which
       presets those are; this module only applies the rule.
    """
    if chart is None or pages < 1 or pages > VERIFICATION_MAX_PAGES:
        return False
    if not relayoutable:
        return False
    if patches < 1 or patches > VERIFICATION_MAX_PATCHES:
        return False
    try:
        values = chart_row_values(chart, recipe)
    except (Ti3ParseError, OSError):
        return False
    return not any(is_patch_shortfall((values.get(rid) or {}).get("reason"))
                   for rid in rows_the_patches_decide(values))


def patch_count(chart: "str | Path") -> int:
    """How many patches the chart really holds. Measured, never declared: a
    preset's ``patches`` field is a display value and a user preset has none.

    Cached on (path, mtime, size) like :func:`chart_row_values`, because the
    window's own list is built out of 177 of these and was re-parsing every
    shipped ``.ti1`` on every open. A chart that changes on disk is counted
    again; nothing here can go stale.
    """
    p = Path(chart)
    try:
        st = p.stat()
        key = (_resolved(p), st.st_mtime_ns, st.st_size)
    except OSError:
        return 0
    hit = _PATCHES.get(key)
    if hit is None:
        try:
            hit = int(parse_ti3(p).n_patches)
        except (Ti3ParseError, OSError):
            return 0
        _PATCHES[key] = hit
    return hit


def row_label(row_id: str) -> str:
    """The row's name, for a window that has only the id."""
    r = CS.ROW_BY_ID.get(row_id)
    return r.label if r is not None else row_id


def row_remedy(row_id: str, reason: "str | None" = None) -> str:
    """The lever the metric's own help icon offers. English source; the window
    puts it through ``tr()``. Reused rather than rewritten so the two windows
    cannot drift into saying different things about the same row.

    With *reason*, only the half of a two-part lever that fits it (K31: the
    grey rows of a FROM PROFILE GAMUT chart are not fixed by adding grey
    steps, `compliance_sets.remedy_for`)."""
    return CS.remedy_for(row_id, reason)


def summarise(entries: "list[Any]") -> "dict[str, int]":
    """``{"listed", "starred", "complete"}`` over already-assessed entries.

    *entries* are anything carrying ``starred`` and ``assessment`` attributes;
    the window's own row objects do.
    """
    listed = len(entries)
    starred = sum(1 for e in entries if getattr(e, "starred", False))
    complete = sum(1 for e in entries
                   if getattr(e, "assessment", UNCHECKED).answers_everything)
    return {"listed": listed, "starred": starred, "complete": complete}
