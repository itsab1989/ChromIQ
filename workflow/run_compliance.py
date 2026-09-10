"""Which limit set a measurement is judged with, and where that is stored.

#182 (Knut, D9/D20/D23): the Measurement Report's limit set belongs to the
PROFILE RUN. It is bound at the run's first verification measurement, its
limits are copied into ``runs/runN/meta.json``, every dated verification of
the run is judged with that copy, and the copy moves only when the user
deliberately unlocks it. This module is the ONE place that reads and writes
that record, for the Measure tab (which stamps the verdict), the report
window (which shows it) and the Report limits window (which edits it).

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
from datetime import datetime
from pathlib import Path

from core.file_manager import (_VERIFY_ID_RE, VERIFICATIONS_DIRNAME, Run,
                               Verification)
from workflow.compliance_sets import (DEFAULT_SET_ID, SET_BY_ID, Limit,
                                      effective_limits, is_edited,
                                      is_known_set, limits_from_json,
                                      limits_to_json, set_label)

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
    """Whether the run has a limit set copied onto it.

    A run made before #182 never has one, and upgrading does not give it one,
    so those runs stay unbound for ever. That matters because an unbound run's
    limits come from the LIVE Preferences default, re-read every time they are
    looked at.
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
    bound: bool = False                  # a copy is stored on the run
    unlocked: bool = False
    edited: bool = False                 # the copy differs from the set (CH-15)
    known: bool = True                   # the set id still exists (D23)
    columns: list = field(default_factory=list)


def run_limits(run: "Run | None", overrides: "dict | None",
               default_set: str = DEFAULT_SET_ID) -> RunLimits:
    """What *run* is judged with right now.

    A bound run: its stored copy. An unbound run (or no run): the effective
    limits of the Preferences default set, marked ``bound=False`` so the caller
    can say "not stored". The default set falls back to ChromIQ default when
    the stored default id is unknown.
    """
    if not is_known_set(default_set):
        default_set = DEFAULT_SET_ID
    meta = run.load_meta() if run is not None else None
    if meta is None or not meta.compliance_set_id or not meta.compliance_thresholds:
        # Unbound (every run written before this existed, or one whose first
        # verification has not happened yet): the Preferences default, or the
        # set a duplicated run carries from its source (F13: the copy keeps
        # the CHOICE of set, not the copy of its numbers). The lock flag and
        # the column choice are the run's own even so.
        preferred = default_set
        if meta is not None and is_known_set(meta.compliance_set_id):
            preferred = meta.compliance_set_id
        return RunLimits(preferred, set_label(preferred),
                         effective_limits(preferred, overrides),
                         label_en=SET_BY_ID[preferred].label, bound=False,
                         unlocked=bool(meta.compliance_unlocked) if meta else False,
                         columns=list(meta.compliance_columns or []) if meta else [])
    limits = limits_from_json(meta.compliance_thresholds)
    known = is_known_set(meta.compliance_set_id)
    return RunLimits(
        meta.compliance_set_id,
        set_label(meta.compliance_set_id, meta.compliance_set_label),
        limits,
        label_en=(SET_BY_ID[meta.compliance_set_id].label if known
                  else (meta.compliance_set_label or meta.compliance_set_id)),
        bound=True, unlocked=bool(meta.compliance_unlocked),
        edited=is_edited(limits, meta.compliance_set_id, overrides) if known else False,
        known=known, columns=list(meta.compliance_columns or []))


def bind_run(run: Run, set_id: str, overrides: "dict | None",
             when: "datetime | None" = None) -> RunLimits:
    """Copy *set_id*'s effective limits onto the run and save (D20).

    Called at the first verification measurement (CH-2: regardless of the
    autosave setting) and when the user picks a set in the report window.
    The label is stored in English so a later ChromIQ that no longer knows
    the id can still name it (D23).
    """
    if not is_known_set(set_id):
        set_id = DEFAULT_SET_ID
    meta = run.load_meta()
    meta.compliance_set_id = set_id
    meta.compliance_set_label = SET_BY_ID[set_id].label
    meta.compliance_thresholds = limits_to_json(effective_limits(set_id, overrides))
    meta.compliance_bound_at = (when or datetime.now()).isoformat(timespec="seconds")
    run.save_meta(meta)
    return run_limits(run, overrides)


def ensure_bound(run: Run, overrides: "dict | None", default_set: str) -> RunLimits:
    """Bind the run to the Preferences default if it is not bound yet; return
    what it is judged with either way. Never raises: a binding that cannot be
    written is logged and the caller judges with the default (CH-14)."""
    try:
        current = run_limits(run, overrides, default_set)
        if current.bound:
            return current
        return bind_run(run, current.set_id, overrides)
    except (OSError, ValueError) as exc:
        log.warning("could not bind %s to a limit set: %s", run.dir, exc)
        return run_limits(None, overrides, default_set)


def set_run_limits(run: Run, limits: "dict[str, Limit]") -> None:
    """Write the run's edited copy (the "This run" column)."""
    meta = run.load_meta()
    meta.compliance_thresholds = limits_to_json(limits)
    run.save_meta(meta)


def set_run_unlocked(run: Run, unlocked: bool) -> None:
    meta = run.load_meta()
    meta.compliance_unlocked = bool(unlocked)
    run.save_meta(meta)


def set_run_columns(run: Run, columns: "list[str]") -> None:
    meta = run.load_meta()
    meta.compliance_columns = list(columns)
    run.save_meta(meta)


def is_locked(run: "Run | None") -> bool:
    """Whether the run's limit set may no longer be chosen in the report window.

    Two conditions were missing and Knut found both, from opposite ends.

    **A run that is not BOUND has nothing to lock.** The lock never asked, so a
    project made before #182 showed a greyed pulldown over a value that is not
    stored anywhere: an unbound run's limits come from the live Preferences
    default and are re-read every time. Driven on screen, the "Default for new
    runs" radio in the limits window then moved the greyed pulldown, the window
    contradicted its own report body, and on a measurement with no recorded
    verdict four rows flipped from PASS to FAIL on screen with nothing written
    to disk. The row was greyed while the value behind it was fixed to nothing.

    **And one measurement is not a history.** Knut, 2026-09-10: *"When only one
    measurement is done, I should be allowed to choose the type of report I want
    to print, and which limits to judge against."* The lock exists so that every
    dated verification of a run is judged the same way and the dates stay
    comparable. With one date there is nothing yet to be comparable with, so it
    protects nothing and only takes the choice away. Measured, changing the set
    at that point rewrites three keys, archives the report it replaces, and
    leaves eighteen keys of measured data untouched.

    This revises section 5 of `docs/design/measurement_report_limits.md`, which
    is still marked awaiting confirmation and confirmed by nobody, so it is a
    draft being corrected rather than a ruling being overturned.
    """
    if run is None:
        return False
    if not is_bound(run):
        return False
    if measured_dates(run) < 2:
        return False
    return not bool(run.load_meta().compliance_unlocked)


def may_unlock(run: "Run | None", allow_after_measurement: bool) -> bool:
    """Whether "Unlock this run's limits" may be ticked: always before the
    first measurement, afterwards only when Preferences allows it (D20)."""
    if run is None:
        return False
    if not has_measured_verification(run):
        return True
    return bool(allow_after_measurement)
