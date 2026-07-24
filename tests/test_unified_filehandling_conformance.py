"""#130 unified file-handling model v3 — conformance guards (Knut, 2026-07-24).

These encode model-v3 rules the existing suite didn't assert. A failure here is a
conformance FINDING to report on the issue, not necessarily a code defect to fix
silently — some are design decisions for Sebastian to rule on.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Project                              # noqa: E402


# ---------------------------------------------------------------------------
# X-05 — terminology sweep: the old "Printer profile name" label must be gone,
# replaced by "Printer profile project name" (model v3 §0).
# ---------------------------------------------------------------------------
def test_X05_no_stale_printer_profile_name_label():
    root = Path(__file__).resolve().parent.parent
    hits: list[str] = []
    for sub in ("ui",):
        for f in (root / sub).rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            text = f.read_text(encoding="utf-8")
            # the bare label, NOT the compliant "... project name"
            for ln, line in enumerate(text.splitlines(), 1):
                if "Printer profile name" in line:
                    hits.append(f"{f.relative_to(root)}:{ln}")
    assert not hits, (
        "model v3 §0 renames the label to 'Printer profile project name'; "
        f"stale 'Printer profile name' still in: {hits}")


# ---------------------------------------------------------------------------
# Model B (regenerate/build into a run) — §3/§5a say an Overwrite Replace moves
# the run's chart, measurement, profile, reports AND its verifications to old/.
# reset_chart_artefacts() is the build path; check what it actually archives.
# ---------------------------------------------------------------------------
def _seed_full_run(run):
    run.ensure_dir()
    run.chart_ti2.write_text("c"); run.measurement_ti3.write_text("m")
    run.profile_icc.write_text("p")
    run.reports_dir.mkdir(parents=True, exist_ok=True)
    (run.reports_dir / "Quality_Check_1.txt").write_text("q")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("vc")
    vd = run.verifications_dir / "2026-01-01_120000"
    vd.mkdir(parents=True, exist_ok=True)
    (vd / "measured.ti3").write_text("v")
    return vd


def test_B_regenerate_archives_measurement_and_profile(tmp_path):
    """The beta.10 safety net: regenerating a chart must NOT delete a run's
    finished measurement/profile — they archive to old/. (Expected PASS.)"""
    proj = Project.create(tmp_path / "P", "P"); run = proj.current_run()
    _seed_full_run(run)
    run.reset_chart_artefacts()
    assert run.old_dir.exists()
    assert not run.measurement_ti3.exists() and not run.profile_icc.exists()


@pytest.mark.xfail(reason="#130 FINDING F2: regenerating a chart into a run does "
                          "NOT archive its verifications/ tree to old/ (model v3 "
                          "§3/§5a); Model A Replace does. Awaiting ruling.",
                   strict=False)
def test_B_regenerate_archives_verifications_tree(tmp_path):
    """Model v3 §3/§5a: a Model B Overwrite Replace should archive the run's
    verifications/ tree to old/ too. Documents whether the build path does."""
    proj = Project.create(tmp_path / "P", "P"); run = proj.current_run()
    vd = _seed_full_run(run)
    run.reset_chart_artefacts()
    assert not vd.exists(), (
        "FINDING: regenerating a chart into a run leaves its dated verifications "
        "in place; model v3 §3/§5a says a Replace archives them to old/")


@pytest.mark.xfail(reason="#130 FINDING F3: regenerating preserves reports/ as "
                          "history; model v3 §3 lists reports among what a Replace "
                          "archives. Design tension — awaiting ruling.",
                   strict=False)
def test_B_regenerate_archives_reports(tmp_path):
    """Model v3 §3: a Model B Replace lists 'reports' among what moves to old/.
    reset_chart_artefacts documents itself as PRESERVING reports/ — this test
    records the discrepancy for Sebastian to rule on."""
    proj = Project.create(tmp_path / "P", "P"); run = proj.current_run()
    _seed_full_run(run)
    run.reset_chart_artefacts()
    assert not run.reports_dir.exists() or not list(run.reports_dir.glob("*.txt")), (
        "FINDING: regenerating preserves reports/; model v3 §3 lists reports "
        "among what a Replace archives to old/ (design decision)")
