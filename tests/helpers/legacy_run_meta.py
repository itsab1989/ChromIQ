"""A run's meta.json as an EARLIER ChromIQ left it (before K31, beta 40).

Until K31 (Knut, #182 5801677743) a profile run was BOUND to a limit set at
its first verification (``bind_run``: the set id, its English label, a copy of
its numbers and ``compliance_bound_at``), could carry an edited copy
(``set_run_limits``), an unlock flag (``set_run_unlocked``) and a report type
of its own (``set_run_report_type``). This build writes none of that: the
limit set and the type belong to the report, and a run holds at most its own
DEFAULT for new reports (`workflow.run_compliance.set_run_default_set`).

Projects written by those builds are still on users' disks, and this build
must read them (a bound copy is read as the run's own default; the stored
type names a report that records none; the unlock flag is ignored). So the
tests build those states with these writers, which put exactly the fields the
old writers put, and nothing in the app calls them.
"""
from __future__ import annotations

from datetime import datetime


def bind_run(run, set_id: str, overrides: "dict | None", when=None):
    """Write the binding an earlier ChromIQ wrote at a run's first
    verification; return what the run now starts new reports on."""
    from workflow.compliance_sets import (DEFAULT_SET_ID, SET_BY_ID,
                                          effective_limits, is_known_set,
                                          limits_to_json)
    from workflow.run_compliance import run_limits
    if not is_known_set(set_id):
        set_id = DEFAULT_SET_ID
    meta = run.load_meta()
    meta.compliance_set_id = set_id
    meta.compliance_set_label = SET_BY_ID[set_id].label
    meta.compliance_thresholds = limits_to_json(effective_limits(set_id, overrides))
    meta.compliance_bound_at = (when or datetime.now()).isoformat(timespec="seconds")
    run.save_meta(meta)
    return run_limits(run, overrides)


def ensure_bound(run, overrides: "dict | None", default_set: str):
    """What an earlier ChromIQ did at a verification measurement."""
    from workflow.run_compliance import run_limits
    current = run_limits(run, overrides, default_set)
    if current.bound:
        return current
    return bind_run(run, current.set_id, overrides)


def set_run_limits(run, limits: dict) -> None:
    """An earlier ChromIQ's edited "This run" column."""
    from workflow.compliance_sets import limits_to_json
    meta = run.load_meta()
    meta.compliance_thresholds = limits_to_json(limits)
    run.save_meta(meta)


def set_run_unlocked(run, unlocked: bool) -> None:
    """An earlier ChromIQ's "Unlock this run's limits" flag (ignored now)."""
    meta = run.load_meta()
    meta.compliance_unlocked = bool(unlocked)
    run.save_meta(meta)


def set_run_report_type(run, type_id: str) -> None:
    """An earlier ChromIQ's per-run report type (D9, until K31)."""
    from workflow.measurement_report import REPORT_TYPES
    if type_id not in REPORT_TYPES:
        raise ValueError(f"unknown report type {type_id!r}")
    meta = run.load_meta()
    meta.report_type = type_id
    run.save_meta(meta)
