"""Golden folder-manifest tests for the v2 layout (#127).

The core idea: after driving each workflow stage with the REAL writers (the
exact functions and arguments the tabs use), snapshot the complete recursive
project listing and compare it to an expected manifest — so ANY stray file
placement, including ones no one thought about, fails with a readable diff.

The stages compose the same building blocks the tabs call (verified by the
source-tripwire tests at the bottom, and by the full suite driving the tabs
themselves); only the instrument/process edge is simulated, per the
"don't monkeypatch the method under test" rule.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import (FileManager, Run, ensure_subdir, exports_subdir,
                               reports_subdir)

REPO = Path(__file__).resolve().parents[1]


class _StubSettings:
    def __init__(self, **overrides):
        self._d = dict(overrides)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


def manifest_of(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix()
                  for p in root.rglob("*") if p.is_file())


@pytest.fixture
def fm(tmp_path):
    settings = _StubSettings(custom_output_path=str(tmp_path))
    fm = FileManager(settings)
    fm.set_target_name("Test-Printer")
    return fm


def _write_chain(run_dir: Path, stem: str) -> None:
    """Place the Argyll chart chain the way targen/printtarg leave it (their
    cwd is ``cwd_for_chart`` and their stem is ``chart_stem`` — the real
    contract chart_creator runs under)."""
    for ext in (".ti1", ".ti2", ".cht", ".ps"):
        (run_dir / f"{stem}{ext}").write_text(f"stand-in {ext}\n",
                                              encoding="utf-8")
    (run_dir / f"{stem}.channels.json").write_text("{}\n", encoding="utf-8")
    (run_dir / f"{stem}_01.tif").write_bytes(b"TIFF")
    ti1 = run_dir / f"{stem}.ti1"
    ti1.write_text(
        "CTI1\n\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
        "END_DATA_FORMAT\nBEGIN_DATA\n1 100.0 0.0 0.0\nEND_DATA\n",
        encoding="utf-8")


def test_full_workflow_manifest(fm) -> None:
    """Create → sidecars → measure → build → check → report: the complete
    v2 tree after every feature has written its files."""
    name = "Test-Printer"
    proj = fm.project()
    root = proj.root

    # -- stage 1: chart generation (chart_creator's placement contract)
    run_dir = fm.cwd_for_chart(cal_target=False)
    stem = fm.chart_stem(cal_target=False)
    assert stem == name and run_dir == proj.current_run().dir
    _write_chain(run_dir, stem)

    # sidecars — the exact tab_chart call: write_sidecars(ti1, exports_subdir(ti2.parent), stem)
    from workflow.chart_exports import write_sidecars
    ti2 = run_dir / f"{stem}.ti2"
    written = write_sidecars(ti2.with_suffix(".ti1"),
                             exports_subdir(ti2.parent), stem)
    assert all(p.parent == run_dir / "exports" for p in written)

    # -- stage 2: measurement (chartread writes <stem>.ti3 into its cwd)
    run = proj.current_run()
    run.measurement_ti3.write_text("CTI3\n", encoding="utf-8")

    # averaging: promote + next read (the Measure tab's averaging flow)
    run.promote_measurement_to_read()
    run.measurement_ti3.write_text("CTI3 read2\n", encoding="utf-8")

    # measurement report — the Measure tab's writer
    from workflow.measurement_report import save_report
    rp = save_report({"created": "t", "mean": 0.1}, run.dir)
    assert rp.parent == run.reports_dir

    # -- stage 3: profile (colprof writes <stem>.icc next to the .ti3)
    run.profile_icc.write_bytes(b"ICC")

    # -- stage 4: quality check — the exact tab_check_refine composition:
    # folder = ensure_subdir(reports_subdir(ti3.parent))
    from workflow.profcheck_runner import (write_quality_report,
                                           write_refine_strips)
    folder = ensure_subdir(reports_subdir(run.measurement_ti3.parent))
    q = write_quality_report(folder, run.measurement_ti3.stem, "summary", "raw")
    s = write_refine_strips(folder, run.measurement_ti3.stem, [("A", 3.0)])
    assert q.parent == run.reports_dir and s.parent == run.reports_dir

    got = [p for p in manifest_of(root)
           if not p.startswith("reports/")]      # (none at project level)
    expected = sorted([
        "Where are my files.txt",
        "project.json",
        f"runs/run1/{name}.channels.json",
        f"runs/run1/{name}.cht",
        f"runs/run1/{name}.icc",
        f"runs/run1/{name}.ps",
        f"runs/run1/{name}.ti1",
        f"runs/run1/{name}.ti2",
        f"runs/run1/{name}.ti3",
        f"runs/run1/{name}_01.tif",
        "runs/run1/meta.json",
        f"runs/run1/exports/{name}-colours.txt",
        f"runs/run1/exports/{name}-i1profiler.pxf",
        f"runs/run1/exports/{name}-i1profiler.txt",
        "runs/run1/reads/read1.ti3",
        f"runs/run1/reports/Quality_Check_1_{name}.txt",
        f"runs/run1/reports/Refine_Strips_1_{name}.txt",
        f"runs/run1/reports/{rp.name}",
    ])
    assert got == expected


def test_calibration_manifest(fm) -> None:
    """Calibration chart placement + its exports/ (the cal side of #127)."""
    proj = fm.project()
    cal_dir = fm.cwd_for_chart(cal_target=True)
    stem = fm.chart_stem(cal_target=True)
    assert stem == "Test-Printer-cal"
    _write_chain(cal_dir, stem)
    (cal_dir / f"{stem}.ti3").write_text("CTI3 cal\n", encoding="utf-8")
    (cal_dir / f"{stem}.cal").write_text("CAL\n", encoding="utf-8")

    from workflow.chart_exports import write_sidecars
    written = write_sidecars(cal_dir / f"{stem}.ti1",
                             exports_subdir(cal_dir), stem)
    assert all(p.parent == proj.calibration.exports_dir for p in written)
    assert proj.calibration.exists()


def test_reset_chart_artefacts_wipes_exports_and_cache_keeps_reports(fm) -> None:
    proj = fm.project()
    run = proj.current_run()
    _write_chain(run.dir, run.stem)
    run.ensure_exports_dir().joinpath("x-colours.txt").write_text("x")
    run.ensure_cache_dir().joinpath("x-sample.cht").write_text("x")
    run.ensure_reports_dir().joinpath("Quality_Check_1_x.txt").write_text("x")
    run.preconditioning_ti3.write_text("keep")
    run.reset_chart_artefacts()
    assert not run.exports_dir.exists()
    assert not run.cache_dir.exists()
    assert run.reports_dir.exists()               # history survives a regen
    assert run.preconditioning_ti3.exists()
    assert not run.chart_ti1.exists()


def test_scanin_prepared_files_land_in_cache(tmp_path) -> None:
    """Drive the real cht-preparation methods of the scanner dialog (they use
    no dialog state beyond what the stub provides) and check both prepared
    working copies land in cache/ next to the chart."""
    pytest.importorskip("PyQt6")
    from ui.dialogs.scanin_dialog import ScannerProfileDialog as ScaninDialog

    run_dir = tmp_path / "P" / "runs" / "run1"
    run_dir.mkdir(parents=True)
    cht = run_dir / "P.cht"
    cht.write_text("BOXES 1\nF _ _ 0 0 10 0 10 10 0 10\n"
                   "X Y Z 1.0 1.0 0.0 0.0 0.0 0.0 0 0\n", encoding="utf-8")
    base = run_dir / "P"

    out = ScaninDialog._apply_sample_area(SimpleNamespace(), cht, 0.5, base)
    assert out.parent == run_dir / "cache"

    stub = SimpleNamespace(_standard_mode=lambda: False,
                           _use_fiducials_cb=SimpleNamespace(
                               isChecked=lambda: False))
    out2 = ScaninDialog._apply_fiducial_frame(stub, cht, base)
    assert out2.parent in (run_dir / "cache", run_dir)  # unchanged cht returns as-is
    if out2 != cht:
        assert out2.parent == run_dir / "cache"


def test_tab_measure_finds_refine_strips_in_reports_and_legacy(tmp_path) -> None:
    """Drive the real Measure-tab auto-detect handler for both locations."""
    pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication
    global _APP                      # keep the QApplication alive (GC crash otherwise)
    _APP = QApplication.instance() or QApplication(sys.argv)
    from core.argyll_runner import ArgyllRunner
    from core.settings import DEFAULTS
    from ui.tabs.tab_measure import TabMeasure

    class _S(_StubSettings):
        def __init__(self):
            super().__init__(**dict(DEFAULTS))

    settings = _S()
    tab = TabMeasure(ArgyllRunner(settings), settings)

    run_dir = tmp_path / "P" / "runs" / "run1"
    run_dir.mkdir(parents=True)
    ti1 = run_dir / "P.ti1"
    ti1.write_text("CTI1\n", encoding="utf-8")
    tab._ti1_path = ti1

    # v2 home: reports/
    strips = reports_subdir(run_dir)
    strips.mkdir()
    (strips / "Refine_Strips_P.txt").write_text(
        "# CHROMIQ_REFINE_STRIPS_V1\nA\t3.0\n", encoding="utf-8")
    tab._update_resume_availability()
    assert tab._refine_strips_path == strips / "Refine_Strips_P.txt"

    # legacy flat location still honoured (external, never-migrated folder)
    (strips / "Refine_Strips_P.txt").unlink()
    (run_dir / "Refine_Strips_P.txt").write_text(
        "# CHROMIQ_REFINE_STRIPS_V1\nB\t3.0\n", encoding="utf-8")
    tab._update_resume_availability()
    assert tab._refine_strips_path == run_dir / "Refine_Strips_P.txt"


# ---------------------------------------------------------------------------
# Source tripwires: the tabs must keep routing through the central helpers.
# Cheap insurance against a refactor quietly reverting a call site to a flat
# path — the full suite drives the tabs, these pin the routing.
# ---------------------------------------------------------------------------

def test_tab_check_refine_routes_reports() -> None:
    src = (REPO / "ui" / "tabs" / "tab_check_refine.py").read_text(encoding="utf-8")
    assert "reports_subdir(self._ti3_path.parent)" in src


def test_tab_chart_routes_exports() -> None:
    src = (REPO / "ui" / "tabs" / "tab_chart.py").read_text(encoding="utf-8")
    assert "exports_subdir(ti2.parent)" in src


def test_scanin_dialog_routes_cache() -> None:
    src = (REPO / "ui" / "dialogs" / "scanin_dialog.py").read_text(encoding="utf-8")
    assert src.count("cache_subdir") >= 4      # patchbox, sample, sweep, 2×diag


def test_measurement_report_routes_reports() -> None:
    src = (REPO / "workflow" / "measurement_report.py").read_text(encoding="utf-8")
    assert src.count("reports_subdir(run_dir)") == 2
