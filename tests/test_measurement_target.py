"""The shared Profile-run / Run-type target + its resolution (#130)."""
from __future__ import annotations

from pathlib import Path

from core.file_manager import Project, Run, Verification
from core.measurement_target import (
    BLOCK_NEW_RUN, BLOCK_NO_CHART, BLOCK_NO_PROFILE, MeasurementTarget,
    resolve_measurement, resolve_run, verification_blocked_reason,
)


def _project(tmp_path: Path) -> Project:
    return Project.create(tmp_path / "Canon", "Canon")


def test_flags_and_status_label():
    prof = MeasurementTarget()
    assert not prof.is_verification() and prof.is_new_run()
    assert prof.status_label() == "new run · profiling"

    v = MeasurementTarget(run_type="verification", profile_run="run1")
    assert v.is_verification() and v.is_new_verification()
    assert v.status_label() == "run1 · verification · new"
    v.verification_id = "2026-07-15_103000"
    assert not v.is_new_verification()
    assert v.status_label() == "run1 · verification · 2026-07-15_103000"


def test_resolve_run_existing_current_and_new(tmp_path):
    proj = _project(tmp_path)
    cur = proj.current_run()
    # Existing id wins.
    r = resolve_run(proj, MeasurementTarget(profile_run=cur.id))
    assert r.id == cur.id
    # Unknown id or new-run without create → current run.
    assert resolve_run(proj, MeasurementTarget(profile_run="run99")).id == cur.id
    assert resolve_run(proj, MeasurementTarget()).id == cur.id
    # New run WITH create → a fresh run.
    fresh = resolve_run(proj, MeasurementTarget(), create=True)
    assert fresh.id != cur.id and proj.has_run(fresh.id)


def test_resolve_measurement_profiling_vs_verification(tmp_path):
    proj = _project(tmp_path)
    run = proj.current_run()
    # Profiling → the Run itself (writes <stem>.ti3).
    m = resolve_measurement(proj, MeasurementTarget(profile_run=run.id))
    assert isinstance(m, Run)
    assert m.measurement_ti3 == run.measurement_ti3

    # Verification, new date → a Verification, materialised on disk.
    v = resolve_measurement(
        proj, MeasurementTarget(run_type="verification", profile_run=run.id),
        create=True)
    assert isinstance(v, Verification)
    assert v.dir.is_dir()
    assert v.measurement_ti3.name == "Canon-verify.ti3"

    # Verification, existing date → that dated folder.
    v2 = resolve_measurement(
        proj, MeasurementTarget(run_type="verification", profile_run=run.id,
                                verification_id=v.id))
    assert isinstance(v2, Verification) and v2.id == v.id


def test_verification_blocked_reason_hole1(tmp_path):
    proj = _project(tmp_path)
    run = proj.current_run(); run.ensure_dir()

    # Profiling target is never blocked.
    assert verification_blocked_reason(proj, MeasurementTarget()) is None

    # New-run + verification → blocked (nothing to verify yet).
    assert verification_blocked_reason(
        proj, MeasurementTarget(run_type="verification")) == BLOCK_NEW_RUN

    # Existing run, but no built profile → blocked.
    t = MeasurementTarget(run_type="verification", profile_run=run.id)
    assert verification_blocked_reason(proj, t) == BLOCK_NO_PROFILE

    # Profile exists but no verification chart → blocked on the chart.
    run.profile_icc.write_text("icc")
    assert verification_blocked_reason(proj, t) == BLOCK_NO_CHART

    # Profile + verify chart → good to go.
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("ti2")
    assert verification_blocked_reason(proj, t) is None


def test_verify_tool_dirs_cascade(tmp_path, monkeypatch):
    from pathlib import Path
    from core.measurement_target import verify_tool_dirs
    # No project → ~/ChromIQ for both.
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    prof, meas = verify_tool_dirs(None)
    assert prof == home / "ChromIQ" and meas == home / "ChromIQ"

    proj = _project(tmp_path)
    run = proj.current_run(); run.ensure_dir()
    # No verifications yet → profile & measurement default to the run folder.
    prof, meas = verify_tool_dirs(proj)
    assert prof == run.dir and meas == run.dir
    # With verification history → measurement defaults to the LATEST dated folder.
    import datetime as _dt
    run.new_verification(_dt.datetime(2026, 6, 1, 9, 0, 0)).ensure_dir()
    latest = run.new_verification(_dt.datetime(2026, 7, 1, 9, 0, 0)); latest.ensure_dir()
    prof, meas = verify_tool_dirs(proj)
    assert meas == latest.dir
    # An explicit verification_id in the target wins.
    t = MeasurementTarget(run_type="verification", profile_run=run.id,
                          verification_id=run.verifications()[0].id)
    _, meas = verify_tool_dirs(proj, t)
    assert meas == run.verifications()[0].dir
