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

import logging
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
    MR.REASON_NO_WHITE,                  # it does not reach white
    MR.REASON_NO_BLACK,                  # it does not reach black
    MR.REASON_NO_RAMP,                   # no 30-70 % tone ramp
    MR.REASON_SMALL_SAMPLE,              # under 20 patches: no worst twentieth
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
    MR.REASON_NOT_COMPUTED,              # the block is absent (old report)
})

#: A preset whose page grid does not exist yet: a printtarg preset is laid
#: out when printtarg runs, and a `.ti1` carries no grid. Only this window can
#: meet it, since every measured sheet was laid out, so it lives here and not
#: among the report's own codes.
REASON_EVENNESS_LAID_OUT_LATER = "evenness_laid_out_later"

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
})
#: …and the evenness codes that are about the chart FILE, not its size: no
#: layout beside it, locations that do not read as strip and row, and a preset
#: that has not been laid out yet (printtarg decides its grid when it runs).
OTHER_SHORTFALL_REASONS = OTHER_SHORTFALL_REASONS | frozenset({
    MR.REASON_EVENNESS_NO_LAYOUT,
    MR.REASON_EVENNESS_NO_POSITIONS,
    REASON_EVENNESS_LAID_OUT_LATER,
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
    """The row ids no preset chart can answer, in table order."""
    return tuple(r.id for r in CS.ROWS if r.status == "ref")


def is_patch_shortfall(reason: "str | None") -> bool:
    """Whether a different patch set would answer this row."""
    return bool(reason) and reason in PATCH_SHORTFALL_REASONS


# ---------------------------------------------------------------------------
# The stand-in report
# ---------------------------------------------------------------------------
def _evenness_grid_for(chart: Path, recipe: "dict | None") -> dict:
    """Where every patch of *chart* will sit, or the reason nobody knows yet.

    * a laid-out chart (a ``.ti2``, or a ``.ti1`` with its ``.ti2`` beside it,
      as the prebuilt bundles ship): read by the report's own
      :func:`~workflow.measurement_report.chart_grid`, exactly;
    * a preset with an engine layout recipe: the engine's own layout
      arithmetic (:func:`_predicted_grid`), with no file written;
    * anything else, a printtarg preset that has never been built: printtarg
      decides the grid when it runs, so the answer is "laid out later".
    """
    if chart.suffix.lower() == ".ti2":
        return MR.chart_grid(chart)
    beside = chart.with_suffix(".ti2")
    if beside.is_file():
        return MR.chart_grid(beside)
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
    return MR.evenness_grid_from_layout(strips, steps, lay.total_patches)


def _estimated_evenness(chart: Path, recipe: "dict | None") -> dict:
    """The evenness block a TYPICAL print of *chart* would give.

    The grid is exact where the chart is laid out (see
    :func:`_evenness_grid_for`); the residuals cannot be known before the sheet
    is printed, so each patch gets one of the size the F1 measurement found on
    a real sheet (:data:`~workflow.measurement_report.EVENNESS_TYPICAL_SIGMA`),
    from a fixed seed, and the report's own arithmetic runs on them. The block
    says it is an estimate.
    """
    grid = _evenness_grid_for(chart, recipe)
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


def _perfect_print(chart: Path, recipe: "dict | None" = None) -> dict:
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
        "grey_balance": MR.grey_balance_block(rgb100, lab, ref, data.sample_ids),
        "ramps_30_70": MR.ramps_block(rgb100, lab, ref, data.sample_ids),
        "gamut_populations": MR.gamut_populations_block(
            rgb100, lab, ref, data.sample_ids),
        "control_strip": MR.control_strip_block(
            lab, ref, data.sample_ids, _declaration_it_would_get(chart)),
        "evenness": _estimated_evenness(chart, recipe),
    }
    if colorimetric:
        # The three reference rows are computed from this block and nothing
        # else, so it is built by the report's OWN `corners_block` rather than
        # by a second reading of what a corner is.
        report["corners"] = MR.corners_block(rgb100, lab, ref, data,
                                             corner_ids, corner_devices)
    return report


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
                     recipe: "dict | None" = None) -> "dict[str, dict]":
    """``{row_id: {"value", "reason", …}}`` for a chart that is not printed yet.

    The report's own :func:`~workflow.measurement_report.row_values`, over the
    stand-in report of :func:`_perfect_print`. A row with a ``value`` is a row
    this chart can answer; a row with a ``reason`` is one it cannot, and the
    reason is the report's own code.

    Raises :class:`~workflow.ti3_analysis.Ti3ParseError` when the file cannot
    be read as a chart at all.
    """
    p = Path(chart)
    try:
        st = p.stat()
        key = (str(p.resolve()), st.st_mtime_ns, st.st_size,
               _reference_stamp(p), _layout_stamp(p),
               # the recipe decides the predicted page grid of a preset that
               # is not laid out yet, so two recipes are two answers
               repr(sorted((recipe or {}).items())))
    except OSError as exc:
        raise Ti3ParseError(str(exc)) from exc
    hit = _CACHE.get(key)
    if hit is None:
        hit = MR.row_values(_perfect_print(p, recipe))
        _CACHE[key] = hit
    return hit


def _layout_stamp(chart: Path) -> tuple:
    """The (mtime, size) of the ``.ti2`` beside a ``.ti1``, or ``()``: the
    evenness rows read the page grid from it, a second file, so it is part of
    the key for the reason `_reference_stamp` gives."""
    if chart.suffix.lower() == ".ti2":
        return ()
    try:
        st = chart.with_suffix(".ti2").stat()
    except OSError:
        return ()
    return (st.st_mtime_ns, st.st_size)


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


# ---------------------------------------------------------------------------
# What a (report type, limit set) combination asks of a chart
# ---------------------------------------------------------------------------
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
    """One chart against one combination. Never raises."""
    return assess_rows(chart, rows_asked(type_id, set_id, overrides),
                       limits=CS.effective_limits(set_id, overrides),
                       recipe=recipe)


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
        key = (str(p.resolve()), st.st_mtime_ns, st.st_size)
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


def row_remedy(row_id: str) -> str:
    """The lever the metric's own help icon offers. English source; the window
    puts it through ``tr()``. Reused rather than rewritten so the two windows
    cannot drift into saying different things about the same row."""
    r = CS.ROW_BY_ID.get(row_id)
    return r.remedy if r is not None else ""


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
