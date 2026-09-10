"""#182: a profile run owns the limit set its verifications are judged with.

Run context is strict (a file in Downloads has no run); binding copies the
set's effective limits into meta.json; locked/unlocked follow Knut's D20; the
duplicate partition classifies every new field; archiving copies, never moves.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.file_manager import Project, RunMeta, DUPLICATE_META_CARRY, DUPLICATE_META_FRESH
from workflow import run_compliance as rc
from workflow.compliance_sets import Limit, factory_limits

_TI3 = "CTI3\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n1 100 100 100 96 100 82\nEND_DATA\n"


def _project(tmp_path: Path):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    return proj, run


# ---- run context ---------------------------------------------------------------

def test_a_run_folder_and_a_dated_verification_folder_are_run_contexts(tmp_path):
    _proj, run = _project(tmp_path)
    ctx = rc.run_context_for(run.dir / "P.ti3")
    assert ctx is not None and ctx.run.dir == run.dir and ctx.verification is None
    v = run.new_verification(); v.ensure_dir()
    ctx = rc.run_context_for(v.dir / "P-verify.ti3")
    assert ctx is not None and ctx.run.dir == run.dir and ctx.verification.id == v.id
    assert ctx.dir == v.dir


def test_downloads_archives_and_nothing_are_not_run_contexts(tmp_path):
    _proj, run = _project(tmp_path)
    (tmp_path / "Downloads").mkdir()
    assert rc.run_context_for(tmp_path / "Downloads" / "x.ti3") is None
    old = run.verifications_dir / "old" / "2026-01-01_120000"
    old.mkdir(parents=True)
    assert rc.run_context_for(old / "P-verify.ti3") is None      # CH-14
    assert rc.run_context_for(None) is None
    assert rc.run_context_for(tmp_path / "runs" / "run1" / "x.ti3") is None  # no such folder


# ---- binding ------------------------------------------------------------------

def test_an_unbound_run_is_judged_with_the_default_set_and_says_so(tmp_path):
    _proj, run = _project(tmp_path)
    rl = rc.run_limits(run, {}, "chromiq_default")
    assert not rl.bound and rl.set_id == "chromiq_default"
    assert rl.limits["all_de00_avg"] == Limit.value(2.0)
    # an unknown default id falls back to ChromIQ default
    assert rc.run_limits(run, {}, "gone").set_id == "chromiq_default"
    assert rc.run_limits(None, {}).set_id == "chromiq_default"


def test_binding_copies_the_effective_limits_including_the_users_overrides(tmp_path):
    """CH-5: a user who moved 2.0 to 2.5 before the migration keeps 2.5."""
    _proj, run = _project(tmp_path)
    ov = {"chromiq_default": {"all_de00_avg": 2.5}}
    rl = rc.bind_run(run, "chromiq_default", ov)
    assert rl.bound and rl.limits["all_de00_avg"] == Limit.value(2.5)
    assert not rl.edited                       # equals the effective set → not an edit
    meta = run.load_meta()
    assert meta.compliance_set_id == "chromiq_default"
    assert meta.compliance_set_label == "ChromIQ default (recommended)"
    assert meta.compliance_thresholds["all_de00_avg"] == 2.5
    assert meta.compliance_thresholds["grey_balance_neutral_ramp_avg"] == [1.5, "should"]
    assert meta.compliance_bound_at


def test_the_copy_is_a_copy_a_later_preferences_change_does_not_move_it(tmp_path):
    _proj, run = _project(tmp_path)
    rc.bind_run(run, "chromiq_default", {})
    later = {"chromiq_default": {"all_de00_avg": 9.0}}
    rl = rc.run_limits(run, later)
    assert rl.limits["all_de00_avg"] == Limit.value(2.0)
    assert rl.edited                           # it now differs from the set → shown as edited


def test_ensure_bound_binds_once_and_never_raises(tmp_path, monkeypatch):
    _proj, run = _project(tmp_path)
    a = rc.ensure_bound(run, {}, "chromiq_tight")
    assert a.bound and a.set_id == "chromiq_tight"
    b = rc.ensure_bound(run, {}, "chromiq_quick")     # already bound: unchanged
    assert b.set_id == "chromiq_tight"
    # a run whose meta cannot be written: judged with the default, no exception
    _proj2, run2 = _project(tmp_path / "second")
    def boom(_m): raise OSError("read-only")
    monkeypatch.setattr(type(run2), "save_meta", lambda self, m: boom(m))
    c = rc.ensure_bound(run2, {}, "chromiq_default")
    assert not c.bound and c.set_id == "chromiq_default"


def test_a_historical_set_keeps_its_values_and_label(tmp_path):
    _proj, run = _project(tmp_path)
    meta = run.load_meta()
    meta.compliance_set_id = "iso_99999"
    meta.compliance_set_label = "ISO 99999 values"
    meta.compliance_thresholds = {"all_de00_avg": 7.0}
    run.save_meta(meta)
    rl = rc.run_limits(run, {})
    assert rl.bound and not rl.known
    assert rl.set_label == "ISO 99999 values (historical)"
    assert rl.limits["all_de00_avg"] == Limit.value(7.0)
    assert not rl.edited


def test_unknown_set_id_on_bind_falls_back_to_the_default(tmp_path):
    _proj, run = _project(tmp_path)
    assert rc.bind_run(run, "nonsense", {}).set_id == "chromiq_default"


# ---- lock -----------------------------------------------------------------------

def test_locked_follows_the_second_measurement_and_the_unlock_flag(tmp_path):
    """REVISED 2026-09-10, on Knut's report, and it moved twice.

    It used to lock on the FIRST measured verification. Two things were wrong
    with that, from opposite ends, and he found both.

    A run that is not BOUND has nothing to lock: its limits come from the live
    Preferences default, so the pulldown was greyed over a value stored nowhere,
    and a radio button in another window moved it.

    And one measurement is not a history. The lock exists so that every dated
    verification of a run is judged the same way; with one date there is nothing
    to be consistent with, so it only takes the choice away.
    """
    _proj, run = _project(tmp_path)
    assert not rc.is_locked(run)                       # nothing measured
    assert rc.may_unlock(run, allow_after_measurement=False)

    v = run.new_verification(); v.ensure_dir()
    v.measurement_ti3.write_text(_TI3, encoding="utf-8")
    assert rc.has_measured_verification(run)
    assert rc.measured_dates(run) == 1
    # bound, but only one date: still the user's to choose
    rc.bind_run(run, "chromiq_default", {})
    assert rc.is_bound(run)
    assert not rc.is_locked(run), "one date is not a history to protect"
    # unlocking is still gated the same way once anything is measured
    assert not rc.may_unlock(run, allow_after_measurement=False)
    assert rc.may_unlock(run, allow_after_measurement=True)

    from datetime import datetime, timedelta
    v2 = run.new_verification(datetime.now() + timedelta(days=30)); v2.ensure_dir()
    v2.measurement_ti3.write_text(_TI3, encoding="utf-8")
    assert rc.measured_dates(run) == 2
    assert rc.is_locked(run), "a second date is what the lock is for"

    rc.set_run_unlocked(run, True)
    assert not rc.is_locked(run)
    # the flag is the run's own even before it is bound (a legacy run that a
    # user unlocks must not read as locked again on the next look)
    assert rc.run_limits(run, {}).unlocked is True
    assert not rc.is_locked(None) and not rc.may_unlock(None, True)


def test_edited_copy_columns_and_unlock_round_trip(tmp_path):
    _proj, run = _project(tmp_path)
    rc.bind_run(run, "chromiq_default", {})
    lim = factory_limits("chromiq_default"); lim["all_de00_avg"] = Limit.value(2.7)
    rc.set_run_limits(run, lim)
    rc.set_run_columns(run, ["chromiq_default", "chromiq_tight"])
    rc.set_run_unlocked(run, True)
    rl = rc.run_limits(run, {})
    assert rl.edited and rl.unlocked and rl.columns == ["chromiq_default", "chromiq_tight"]
    assert rl.limits["all_de00_avg"] == Limit.value(2.7)


# ---- the partition and the archive ------------------------------------------------

def test_the_six_fields_are_classified_as_the_record_says():
    assert {"compliance_set_id", "compliance_set_label", "compliance_columns"} <= DUPLICATE_META_CARRY
    assert {"compliance_bound_at", "compliance_unlocked",
            "compliance_thresholds"} <= DUPLICATE_META_FRESH
    m = RunMeta.from_dict({"run_id": "run1", "compliance_thresholds": {"a": 1},
                           "something_from_the_future": 1})
    assert m.compliance_thresholds == {"a": 1} and m.compliance_set_id == ""


def test_archive_reports_copies_and_never_moves(tmp_path):
    _proj, run = _project(tmp_path)
    v = run.new_verification(); v.ensure_dir()
    assert v.archive_reports() is None                  # nothing to archive
    v.reports_dir.mkdir(parents=True)
    live = v.reports_dir / "report_2026-01-01_10-00-00.json"
    live.write_text(json.dumps({"schema": 7}), encoding="utf-8")
    from datetime import datetime
    when = datetime(2026, 9, 8, 12, 0, 0)
    a = v.archive_reports(when)
    assert v.archive_reports(when) is None              # identical content: no second copy (N2)
    live.write_text(json.dumps({"schema": 7, "changed": True}), encoding="utf-8")
    b = v.archive_reports(when)                         # changed content, same second: a second folder
    assert a == v.reports_dir / "old" / "2026-09-08_120000"
    assert b == v.reports_dir / "old" / "2026-09-08_120000_2"
    assert live.exists() and (a / live.name).exists() and (b / live.name).exists()
    # the archive is invisible to the report listing
    from workflow.measurement_report import list_reports
    assert list_reports(v.dir) == [live]


def test_a_duplicated_run_carries_the_choice_of_set_but_is_bound_afresh(tmp_path):
    """F13: the record's words, "carries the chosen set and clears the binding"."""
    proj, run = _project(tmp_path)
    rc.bind_run(run, "chromiq_tight", {})
    lim = factory_limits("chromiq_tight"); lim["all_de00_avg"] = Limit.value(0.7)
    rc.set_run_limits(run, lim)
    dup_run = proj.duplicate_run(run)
    rl = rc.run_limits(dup_run, {}, "chromiq_default")
    assert not rl.bound and not rl.edited
    assert rl.set_id == "chromiq_tight"                     # the choice travels
    assert rl.limits["all_de00_avg"] == Limit.value(1.0)     # not the source's edit
    bound = rc.ensure_bound(dup_run, {}, "chromiq_default")
    assert bound.bound and bound.set_id == "chromiq_tight"
