"""End-to-end model test of the whole #130 verification workflow, wiring the
real pieces together with no Argyll/instrument:

  Create Chart  → a generated chart is *adopted* as the run's shared verify
                  chart (moved into verifications/ as <stem>-verify.*).
  Measure       → a verification is filed in its own dated
                  verifications/<date>/ folder, tagged, never a profile.
  Report        → gathering reads profiling and verification points from two
                  physically separate areas, so they NEVER mix.
  Bar/state     → the shared controller reflects the run + its verification
                  history and drives the Run type.

This is the "does the whole thing hang together" test; the per-piece edge
cases live in test_measure_verify / test_measurement_target(_bar) /
test_report_dialog_verification / test_project_run.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.file_manager import Project, Verification  # noqa: E402
from core.measurement_target import (  # noqa: E402
    RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow.measurement_report import (  # noqa: E402
    list_project_reports, save_report)


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _FM:
    def __init__(self, root: Path):
        self._root = root

    def working_dir(self) -> Path:
        return self._root

    def project(self) -> Project:
        return Project.load(self._root)


def _point(chart: str, *, verification: bool, created: str) -> dict:
    """A minimal report data point (what save_report persists per measurement)."""
    return {
        "chart": chart,
        "created": created,
        "is_verification": verification,
        "de00": {"mean": 1.0, "max": 2.0},
    }


def _write_run_chart(run) -> None:
    """Lay down a generated chart at the run root (what Create Chart produces),
    enough for adopt_run_chart_as_verify to move."""
    run.ensure_dir()
    for p in (run.chart_ti1, run.chart_ti2, run.chart_cht):
        p.write_text("x")
    (run.dir / f"{run.stem}_01.tif").write_text("tif")


def test_full_verification_workflow(tmp_path):
    # ---- project + a completed profiling run (run1 with a built profile) -----
    proj = Project.create(tmp_path / "Canon-Pro300", "Canon-Pro300")
    run = proj.current_run()          # run1
    run.ensure_dir()
    run.measurement_ti3.write_text("profiling measurement")
    run.profile_icc.write_text("icc")          # a finished profile exists
    # A profiling report point lives next to the profiling measurement.
    save_report(_point(run.stem, verification=False, created="2026-05-01T09:00:00"),
                run.dir)

    # ---- shared state: pick this run + switch to Verification ----------------
    ctl = MeasurementTargetController(_FM(proj.root))
    assert ctl.run_ids() == ["run1"]
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert ctl.target.is_verification()
    assert ctl.verification_ids("run1") == []          # none yet

    # ---- Create Chart: generate a chart, adopt it as the verify chart --------
    _write_run_chart(run)
    moved = run.adopt_run_chart_as_verify()
    assert moved == run.verify_chart_ti2
    assert run.has_verify_chart()
    # The chart moved OUT of the run root; the profiling measurement/profile stay.
    assert not run.chart_ti2.exists()
    assert run.measurement_ti3.exists() and run.profile_icc.exists()
    assert run.verify_chart_ti2.exists()
    assert run.verify_chart_tiffs()                    # page TIFF came along

    # ---- Measure: file two dated verification measurements (a history) -------
    v1 = run.new_verification(dt.datetime(2026, 6, 1, 9, 0, 0))
    v1.ensure_dir()
    v1.measurement_ti3.write_text('CTI3\nKEYWORD "CHROMIQ_VERIFICATION"\n'
                                  'CHROMIQ_VERIFICATION "true"\n')
    save_report(_point(run.verify_stem, verification=True,
                       created="2026-06-01T09:00:00"), v1.dir)

    v2 = run.new_verification(dt.datetime(2026, 7, 1, 9, 0, 0))
    v2.ensure_dir()
    v2.measurement_ti3.write_text('CTI3\nCHROMIQ_VERIFICATION "true"\n')
    save_report(_point(run.verify_stem, verification=True,
                       created="2026-07-01T09:00:00"), v2.dir)

    # The controller now sees the two dated verifications, oldest-first.
    vids = ctl.verification_ids("run1")
    assert vids == [v1.id, v2.id]

    # ---- Report gathering: two disjoint areas, never mixed -------------------
    prof_reports = list_project_reports(run.dir)
    verif_reports = list_project_reports(v2.dir)

    def _kinds(paths):
        import json
        return {json.loads(p.read_text())["is_verification"] for p in paths}

    assert len(prof_reports) == 1 and _kinds(prof_reports) == {False}
    assert len(verif_reports) == 2 and _kinds(verif_reports) == {True}
    # No path appears in both gathers → physical separation holds.
    assert set(prof_reports).isdisjoint(verif_reports)


def test_hole1_new_run_verification_without_profile(tmp_path):
    """A run with no built profile cannot host a verification: the controller's
    state is legal to set, but verification_blocked_reason flags it so the UI
    can soft-bounce Run type back to Profiling (Hole 1)."""
    from core.measurement_target import (
        BLOCK_NO_CHART, BLOCK_NO_PROFILE, MeasurementTarget,
        verification_blocked_reason)
    proj = Project.create(tmp_path / "Fresh", "Fresh")
    run = proj.current_run()
    run.ensure_dir()                              # no .icc → no profile yet

    target = MeasurementTarget(run_type=RUN_TYPE_VERIFICATION, profile_run="run1")
    assert verification_blocked_reason(proj, target) == BLOCK_NO_PROFILE

    # Build the profile → the profile block clears; now only the verify chart
    # is missing (that's produced on the Create Chart tab).
    run.profile_icc.write_text("icc")
    assert verification_blocked_reason(proj, target) == BLOCK_NO_CHART

    # Adopt a verify chart → nothing blocks the verification any more.
    _write_run_chart(run)
    run.adopt_run_chart_as_verify()
    assert verification_blocked_reason(proj, target) is None

    # A profiling target is never blocked on these grounds.
    prof = MeasurementTarget(run_type=RUN_TYPE_PROFILING, profile_run="run1")
    assert verification_blocked_reason(proj, prof) is None


def test_verification_for_dir_roundtrip(tmp_path):
    """A dated verification folder resolves back to its Verification (the report
    tool relies on this to find the run + shared chart one level up)."""
    proj = Project.create(tmp_path / "RT", "RT")
    run = proj.current_run(); run.ensure_dir()
    v = run.new_verification(dt.datetime(2026, 8, 1, 12, 0, 0)); v.ensure_dir()
    back = Verification.for_dir(v.dir)
    assert back.id == v.id
    assert back.dir == v.dir
    assert back.stem == run.verify_stem
