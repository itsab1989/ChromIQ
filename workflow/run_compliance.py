"""The starting choice of a new report's limit set, and what a run stores.

#182 K31 (Knut, #182 5801677743, 2026-09-23): *"the limit set belongs to the
report that is made for the profile run"*, and "Unlock this run's limits" is
removed with the run lock behind it. A profile run no longer OWNS a limit set,
is no longer bound at its first verification and is never locked. What a run
may still hold in ``runs/runN/meta.json`` is its own DEFAULT for new reports,
chosen in the Report limits window (*"the default in the Edit limits for that
run, if it changed to be different from the preferences default"*): a new
report of the run starts on it instead of the Preferences default. A run
bound by an earlier ChromIQ carries such a default already (its old binding),
and it is read as one; nothing on disk is rewritten to say so.

This module is the ONE place that reads and writes that record, for the
Measure tab (the automatic report after a measurement), the report window
("New report...") and the Report limits window (which sets it).

It also decides what a "run context" is (CH-14): a measurement file is judged
on behalf of a run only when it really sits in one, ``runs/runN/<file>`` or
``runs/runN/verifications/<date>/<file>``. A file in Downloads, or one the
user picked from an archived ``old/`` folder, has no run: the report is still
built and judged, but nothing is written anywhere.

No Qt in here.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.file_manager import (_VERIFY_ID_RE, VERIFICATIONS_DIRNAME, Run,
                               Verification)
from workflow.compliance_sets import (DEFAULT_SET_ID, SET_BY_ID, Limit,
                                      effective_limits, is_edited,
                                      is_known_set, limits_from_json,
                                      set_label)

log = logging.getLogger(__name__)

_RUN_DIR_RE = re.compile(r"^run\d+$")


# ---------------------------------------------------------------------------
# Run context
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RunContext:
    run: Run
    verification: "Verification | None" = None

    @property
    def dir(self) -> Path:
        return self.verification.dir if self.verification else self.run.dir


def _is_run_dir(d: Path) -> bool:
    return (d.is_dir() and _RUN_DIR_RE.match(d.name) is not None
            and d.parent.name == "runs")


def run_context_for(path: "Path | str | None") -> "RunContext | None":
    """The run a measurement file belongs to, or None when it belongs to none.

    Strict on purpose (CH-14): ``Run.for_dir`` binds to ANY folder and
    ``save_meta`` would happily write ``meta.json`` into Downloads or into
    ``verifications/old/``. Only the two real shapes count.
    """
    if path is None:
        return None
    p = Path(path)
    d = p.parent if p.suffix else p
    try:
        if _is_run_dir(d):
            return RunContext(Run.for_dir(d))
        if (_VERIFY_ID_RE.match(d.name) and d.parent.name == VERIFICATIONS_DIRNAME
                and _is_run_dir(d.parent.parent)):
            run = Run.for_dir(d.parent.parent)
            return RunContext(run, Verification(run, d.name))
    except (OSError, ValueError):
        return None
    return None


def project_root_for(path: "Path | str | None") -> "Path | None":
    """The ChromIQ project a file lies in, or None when it lies in none.

    NOT THE SAME QUESTION AS :func:`run_context_for`, and telling a user
    otherwise was a false sentence in shipped text (R24-F6). That one answers
    "which RUN is this measurement's", and a calibration has none: it lives at
    ``<project>/cal/<name>-cal.ti3``, which `calibration_run_type.md` gives it.
    The report window read the None and told the reader *"This measurement is
    not in a ChromIQ project"* about a file sitting inside one.

    A project is a folder carrying the manifest, asked of the folder itself
    rather than matched out of a string, and the walk stops at the first one
    found. Bounded: the deepest thing a measurement reaches from is
    ``<project>/runs/runN/verifications/<date>/``, four levels.
    """
    if path is None:
        return None
    from core.file_manager import is_a_project
    p = Path(path)
    d = p.parent if p.suffix else p
    try:
        for cand in (d, *list(d.parents)[:7]):
            if is_a_project(cand):
                return cand
    except (OSError, ValueError):
        return None
    return None


def has_measured_verification(run: Run) -> bool:
    """True once any dated verification of the run holds a measurement."""
    try:
        return any(v.exists() for v in run.verifications())
    except OSError:
        return False


def measured_dates(run: "Run | None") -> int:
    """How many dated verifications of the run hold a measurement."""
    if run is None:
        return 0
    try:
        return sum(1 for v in run.verifications() if v.exists())
    except OSError:
        return 0


def is_bound(run: "Run | None") -> bool:
    """Whether the run carries a COPY of a limit set's numbers.

    Only an earlier ChromIQ wrote one (it bound a run at its first verification
    until K31). Such a copy is read as the run's own default for new reports
    (:func:`run_limits`); this build never writes one, and nothing is locked by
    it.
    """
    if run is None:
        return False
    try:
        meta = run.load_meta()
    except Exception:                       # noqa: BLE001 — a missing meta
        return False
    return bool(getattr(meta, "compliance_set_id", "")
                and getattr(meta, "compliance_thresholds", None))


# ---------------------------------------------------------------------------
# The run's limits
# ---------------------------------------------------------------------------
@dataclass
class RunLimits:
    set_id: str
    set_label: str                       # translated, ready to show
    limits: "dict[str, Limit]"
    label_en: str = ""                   # the English label, for records on disk
    bound: bool = False                  # a copy is stored on the run (legacy)
    #: always False since K31: nothing is locked, so nothing is unlocked. Kept
    #: so an older caller's keyword still constructs one.
    unlocked: bool = False
    edited: bool = False                 # the copy differs from the set (CH-15)
    known: bool = True                   # the set id still exists (D23)
    columns: list = field(default_factory=list)


def run_limits(run: "Run | None", overrides: "dict | None",
               default_set: str = DEFAULT_SET_ID) -> RunLimits:
    """The limit set a NEW report of *run* starts on (K31).

    The run's own default when it has one, chosen in the Report limits window
    (``compliance_set_id``), or an earlier ChromIQ's bound copy of it, whose
    numbers are then used as they were stored; otherwise the Preferences
    default set, marked ``bound=False``. The default set falls back to ChromIQ
    default when the stored default id is unknown. Nothing here is a lock: a
    report may be judged against any set, and a saved report keeps its own.
    """
    if not is_known_set(default_set):
        default_set = DEFAULT_SET_ID
    meta = run.load_meta() if run is not None else None
    if meta is None or not meta.compliance_set_id or not meta.compliance_thresholds:
        # Unbound (every run written before this existed, or one whose first
        # verification has not happened yet): the Preferences default, or the
        # set a duplicated run carries from its source (F13: the copy keeps
        # the CHOICE of set, not the copy of its numbers). The column choice
        # is the run's own even so.
        preferred = default_set
        if meta is not None and is_known_set(meta.compliance_set_id):
            preferred = meta.compliance_set_id
        return RunLimits(preferred, set_label(preferred),
                         effective_limits(preferred, overrides),
                         label_en=SET_BY_ID[preferred].label, bound=False,
                         columns=list(meta.compliance_columns or []) if meta else [])
    limits = limits_from_json(meta.compliance_thresholds,
                              meta.compliance_set_id)
    known = is_known_set(meta.compliance_set_id)
    return RunLimits(
        meta.compliance_set_id,
        set_label(meta.compliance_set_id, meta.compliance_set_label),
        limits,
        label_en=(SET_BY_ID[meta.compliance_set_id].label if known
                  else (meta.compliance_set_label or meta.compliance_set_id)),
        bound=True,
        edited=is_edited(limits, meta.compliance_set_id, overrides) if known else False,
        known=known, columns=list(meta.compliance_columns or []))


def set_run_default_set(run: Run, set_id: str, preferences_default: str) -> None:
    """Record which limit set new reports of *run* start from (K31).

    Knut: *"the starting choice for 'New report...' should be the defaults in
    preferences -> reports first, then the default in the Edit limits for that
    run, if it changed to be different from the preferences default"*. So a
    choice equal to the Preferences default clears the run's own default and
    the run follows Preferences again; any other known set is stored by id
    (with its English label, D23). No numbers are copied: a report copies the
    numbers it is judged against when it is generated. A copy an earlier
    ChromIQ bound onto the run is dropped with the old choice, and nothing
    already saved changes.
    """
    meta = run.load_meta()
    if not is_known_set(set_id) or set_id == preferences_default:
        meta.compliance_set_id = ""
        meta.compliance_set_label = ""
    else:
        meta.compliance_set_id = set_id
        meta.compliance_set_label = SET_BY_ID[set_id].label
    meta.compliance_thresholds = {}
    meta.compliance_bound_at = ""
    meta.compliance_unlocked = False
    run.save_meta(meta)


def run_default_set_id(run: "Run | None") -> str:
    """The run's own default set id for new reports, or "" when it follows
    Preferences (K31). A set a later ChromIQ no longer knows is not a
    starting choice this build can offer, so it answers ""."""
    if run is None:
        return ""
    try:
        sid = str(run.load_meta().compliance_set_id or "")
    except Exception:                       # noqa: BLE001 — a missing meta
        return ""
    return sid if is_known_set(sid) else ""


def set_run_columns(run: Run, columns: "list[str]") -> None:
    meta = run.load_meta()
    meta.compliance_columns = list(columns)
    run.save_meta(meta)


# ---------------------------------------------------------------------------
# The run's report TYPE
# ---------------------------------------------------------------------------
# #182 (D28): the kind of document, as opposed to the numbers it is judged
# with. Until K31 a run stored one beside its set (D9). Since K31 the type is
# the REPORT's, like its limit set: a new report starts on the Preferences
# default (`new_report_type`), and a run's stored type is read only to name a
# report written before the type was recorded on the report itself.
def run_report_type(run: "Run | None") -> str:
    """The report type an earlier ChromIQ stored on this run (legacy, K31).

    A run that never chose, and a run carrying a type from a later ChromIQ,
    both answer with today's report. Never raises: a meta.json that cannot be
    read must not stop a report being built (CH-14).
    """
    from workflow.measurement_report import REPORT_TYPE_DEFAULT, report_type
    if run is None:
        return REPORT_TYPE_DEFAULT
    try:
        return report_type({"report_type": run.load_meta().report_type})
    except (OSError, ValueError) as exc:
        log.warning("could not read the report type of %s: %s", run.dir, exc)
        return REPORT_TYPE_DEFAULT


def report_type_default_for(run: "Run | None", preferred: str,
                            kind: "str | None" = None) -> str:
    """What a report of *run* that RECORDS NO TYPE of its own renders as.

    **SINCE K31 THIS IS NOT THE STARTING CHOICE OF A NEW REPORT**, which is
    :func:`new_report_type` (Preferences only). It is kept for reports written
    before a report recorded its own type, which are named and shown as the
    type their run was set to when they were written, exactly as before.

    Knut, 2026-09-18 (B8-388): *"Regarding 'the report type': The type belongs
    to the run, yes, but the default should be the 'Full colour check'."* and,
    of the Preferences pulldown, *"the selected option is used as default when
    opening measurement report (when no report is showing) or when an automatic
    measurement report is written after a completed measurement."*

    So the run still owns the type — a run that has chosen one is answered with
    it, which is D9 untouched — and the Preferences value is what a run that
    never chose gets, instead of the hard-coded T2 that
    :func:`run_report_type` answers with.

    An id this build cannot PRODUCE is refused from either source, for the
    reason :func:`workflow.measurement_report.report_type` gives: what this
    build renders is what it must say it rendered.

    **AND AN ID THE MEASUREMENT'S KIND DOES NOT ALLOW (K13, Knut on beta 34).**
    A profiling measurement's report is always the Printing record, whatever
    the run or Preferences say; a verification never is, so a run or a
    Preferences value of Printing record (both legal until beta 35) is refused
    for it at READ time and nothing on disk is rewritten. ``kind`` None keeps
    the old answer, for a caller that has no measurement to ask about.
    """
    from workflow.measurement_report import (KIND_PROFILING,
                                             REPORT_TYPE_DEFAULT,
                                             REPORT_TYPE_RECORD, REPORT_TYPES,
                                             report_type_is_built,
                                             report_types_for_kind)
    if kind == KIND_PROFILING:
        return REPORT_TYPE_RECORD
    allowed = report_types_for_kind(kind)

    def _usable(tid: str) -> bool:
        return (tid in REPORT_TYPES and report_type_is_built(tid)
                and tid in allowed)

    stored = ""
    if run is not None:
        try:
            stored = str(run.load_meta().report_type or "")
        except (OSError, ValueError) as exc:
            log.warning("could not read the report type of %s: %s", run.dir, exc)
    if _usable(stored):
        return stored
    pref = str(preferred or "")
    return pref if _usable(pref) else REPORT_TYPE_DEFAULT


def new_report_type(preferred: str, kind: "str | None" = None) -> str:
    """The type a NEW report starts as (K31): the Preferences > Reports
    default, fitted to the measurement's kind.

    Knut, #182 5801677743: *"the starting choice for 'New report...' should be
    the defaults in preferences -> reports first"*, and *"settings belongs to
    the report"*. So a run's own stored ``report_type`` (the type pulldown
    wrote it until K31) is no longer a starting choice; it is still read by
    :func:`report_type_default_for` only to name a report written before the
    type was recorded on the report itself. The per-run default Knut allows is
    the LIMIT SET chosen in Edit limits (:func:`run_limits`); the Report limits
    window holds no report type.
    """
    return report_type_default_for(None, preferred, kind)
