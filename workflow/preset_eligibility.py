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
* ``reference_source`` is ``"design"``, which is what a preset chart really
  gets. A colorimetric reference is written only beside a chart built FROM
  PROFILE GAMUT (:func:`workflow.verification_print.chart_conversion_state`),
  and no preset ships one, so the three reference rows read
  ``needs_reference_file`` here for every preset on the list. That is not a
  pessimistic guess, it is the state, and the row's own remedy text already
  says what to do about it.
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


def classified_reasons() -> "frozenset[str]":
    """Every reason this module knows how to file. The guard's subject."""
    return PATCH_SHORTFALL_REASONS | OTHER_SHORTFALL_REASONS


def is_patch_shortfall(reason: "str | None") -> bool:
    """Whether a different patch set would answer this row."""
    return bool(reason) and reason in PATCH_SHORTFALL_REASONS


# ---------------------------------------------------------------------------
# The stand-in report
# ---------------------------------------------------------------------------
def _perfect_print(chart: Path) -> dict:
    """The report a flawless print of *chart*, measured as a verification
    sheet, would produce. Every block comes from :mod:`measurement_report`."""
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

    report: dict = {
        "patches": n,
        "sheet_kind": "verification",
        "is_verification": True,
        # See the module docstring: a preset chart never carries a colorimetric
        # reference, and claiming one here would promise three rows it cannot
        # answer.
        "reference_source": "design",
        "de00": MR._stats([0.0] * n),
        "grey_balance": MR.grey_balance_block(rgb100, lab, ref, data.sample_ids),
        "ramps_30_70": MR.ramps_block(rgb100, lab, ref, data.sample_ids),
        "gamut_populations": MR.gamut_populations_block(
            rgb100, lab, ref, data.sample_ids),
        "control_strip": MR.control_strip_block(
            lab, ref, data.sample_ids, _declaration_it_would_get(chart)),
    }
    return report


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


def chart_row_values(chart: "str | Path") -> "dict[str, dict]":
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
        key = (str(p.resolve()), st.st_mtime_ns, st.st_size)
    except OSError as exc:
        raise Ti3ParseError(str(exc)) from exc
    hit = _CACHE.get(key)
    if hit is None:
        hit = MR.row_values(_perfect_print(p))
        _CACHE[key] = hit
    return hit


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
                 if r.id in limited and (only is None or r.id in only))


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

    @property
    def patch_shortfalls(self) -> "tuple[tuple[str, str], ...]":
        return tuple((rid, why) for rid, why in self.missing
                     if is_patch_shortfall(why))


UNCHECKED = Assessment(asked=(), answered=(), missing=(), checked=False)


def assess(chart: "str | Path | None", type_id: str, set_id: str,
           overrides: "dict | None" = None) -> Assessment:
    """One chart against one combination. Never raises."""
    asked = rows_asked(type_id, set_id, overrides)
    if chart is None:
        return Assessment(asked=asked, answered=(), missing=(), checked=False)
    try:
        values = chart_row_values(chart)
    except (Ti3ParseError, OSError) as exc:
        log.info("preset chart %s cannot be assessed: %s", chart, exc)
        return Assessment(asked=asked, answered=(), missing=(),
                          checked=False, unreadable=str(exc))
    answered, missing = [], []
    for rid in asked:
        v = values.get(rid) or {}
        if v.get("value") is not None:
            answered.append(rid)
        else:
            missing.append((rid, v.get("reason") or MR.REASON_NOT_COMPUTED))
    return Assessment(asked=asked, answered=tuple(answered),
                      missing=tuple(missing))


# ---------------------------------------------------------------------------
# The star
# ---------------------------------------------------------------------------
def made_for_verification(chart: "str | Path | None", patches: int,
                          pages: int) -> bool:
    """Whether this chart is one of the ones Knut asked to be highlighted.

    Three conditions, ANDed, and none of them depends on the two pulldowns:
    the mark says what the CHART is, so it does not flicker on and off while
    a reader compares report types.

    1. one printed page (:data:`VERIFICATION_MAX_PAGES`);
    2. :data:`VERIFICATION_MAX_PATCHES` patches or fewer;
    3. nothing withheld that a different patch set would supply, over every
       row ChromIQ can compute. Not "every row the selection asks", because a
       selection may ask for a colorimetric reference no preset carries.
    """
    if chart is None or pages < 1 or pages > VERIFICATION_MAX_PAGES:
        return False
    if patches < 1 or patches > VERIFICATION_MAX_PATCHES:
        return False
    try:
        values = chart_row_values(chart)
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
