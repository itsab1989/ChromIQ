"""#130 (Knut, 2026-07-28): migration from the 3.13 layout, tested.

    *"The dummy data shall be able to test migration from 3.13, as well as
    perform full test of verification runs and reporting."*

``scripts/make_demo_projects.py`` builds the demo projects; this drives the
**real** ``Project.load`` over the two legacy ones and checks what actually
moved on disk.

**Why the fixtures are trustworthy, and where they are not.** The legacy shapes
are taken from the migration code itself — ``_migrate_v1_to_v2`` lists exactly
which files v1 kept flat inside each run folder, and ``_migrate_v2_to_v3`` what
v2 left at the run root. That is a far better source than my memory of 3.13:
writing this is what corrected my own assumption that v1 had no ``runs/``
folders at all. It **had** them; it was the sub-folders that did not exist.

What these cannot prove is that a genuine user's 3.13 folder holds nothing this
does not imagine — which is why a real one was asked for on the issue.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from make_demo_projects import (build_full, build_legacy_v1,  # noqa: E402
                                build_legacy_v2, build_verify_history)

from core.file_manager import Project                          # noqa: E402


def _schema(root: Path) -> int:
    return json.loads((root / "project.json").read_text())["schema_version"]


# ---- v1 (the 3.13 layout) ----------------------------------------------
@pytest.fixture
def legacy_v1(tmp_path):
    build_legacy_v1(tmp_path)
    return tmp_path / "Demo-Legacy-v1"


def test_the_fixture_really_is_the_old_layout(legacy_v1):
    """It has to start wrong for the migration to mean anything."""
    assert _schema(legacy_v1) == 1
    run = legacy_v1 / "runs" / "run1"
    assert (run / "Quality_Check_1_Demo-Legacy-v1.txt").is_file()
    assert (run / "Demo-Legacy-v1-diag.tif").is_file()
    assert not (run / "reports").exists()
    assert not (run / "cache").exists()


def test_opening_it_migrates_it(legacy_v1):
    Project.load(legacy_v1)
    assert _schema(legacy_v1) == 3


def test_the_quality_checks_and_refine_list_move_to_reports(legacy_v1):
    Project.load(legacy_v1)
    for rid in ("run1", "run2"):
        reports = legacy_v1 / "runs" / rid / "reports"
        names = sorted(p.name for p in reports.iterdir())
        assert names == ["Quality_Check_1_Demo-Legacy-v1.txt",
                         "Quality_Check_2_Demo-Legacy-v1.txt",
                         "Refine_Strips_Demo-Legacy-v1.txt"], rid


def test_the_scanner_intermediates_move_to_cache(legacy_v1):
    Project.load(legacy_v1)
    cache = legacy_v1 / "runs" / "run1" / "cache"
    names = sorted(p.name for p in cache.iterdir())
    assert names == ["Demo-Legacy-v1-aligned.cht", "Demo-Legacy-v1-diag.tif",
                     "Demo-Legacy-v1-patchbox.cht"]


def test_nothing_chromiq_writes_is_left_flat(legacy_v1):
    Project.load(legacy_v1)
    for rid in ("run1", "run2"):
        run = legacy_v1 / "runs" / rid
        stray = [p.name for p in run.iterdir() if p.is_file()
                 and (p.name.startswith(("Quality_Check_", "Refine_Strips_"))
                      or p.name.endswith(("-diag.tif", "-patchbox.cht",
                                          "-aligned.cht")))]
        assert not stray, f"{rid}: {stray}"


def test_the_measurement_and_profile_are_never_moved(legacy_v1):
    """The Argyll-coupled chain stays exactly where it is — that coupling is
    what makes the files work at all."""
    run = legacy_v1 / "runs" / "run1"
    before = (run / "Demo-Legacy-v1.ti3").read_text()

    Project.load(legacy_v1)

    assert (run / "Demo-Legacy-v1.ti3").is_file()
    assert (run / "Demo-Legacy-v1.icc").is_file()
    assert (run / "Demo-Legacy-v1.ti2").is_file()
    assert (run / "Demo-Legacy-v1.ti3").read_text() == before, \
        "the measurement was rewritten"


def test_migrating_twice_changes_nothing_more(legacy_v1):
    """Idempotent — a crash part-way must be recoverable by opening again."""
    Project.load(legacy_v1)
    snapshot = sorted(str(p.relative_to(legacy_v1))
                      for p in legacy_v1.rglob("*"))
    Project.load(legacy_v1)
    assert sorted(str(p.relative_to(legacy_v1))
                  for p in legacy_v1.rglob("*")) == snapshot


def test_the_runs_survive_with_their_numbering(legacy_v1):
    proj = Project.load(legacy_v1)
    assert [r.id for r in proj.all_runs()] == ["run1", "run2"]


# ---- v2 → v3 (the one-slot verification) --------------------------------
@pytest.fixture
def legacy_v2(tmp_path):
    build_legacy_v2(tmp_path)
    return tmp_path / "Demo-Legacy-v2"


def test_a_flat_verification_becomes_a_dated_one(legacy_v2):
    run = legacy_v2 / "runs" / "run1"
    assert (run / "Demo-Legacy-v2-verify.ti3").is_file(), "fixture must start flat"

    Project.load(legacy_v2)

    assert not (run / "Demo-Legacy-v2-verify.ti3").exists()
    dated = [d for d in (run / "verifications").iterdir() if d.is_dir()]
    assert len(dated) == 1, [d.name for d in dated]
    assert (dated[0] / "Demo-Legacy-v2-verify.ti3").is_file()


def test_the_shared_verify_chart_moves_beside_the_dates(legacy_v2):
    Project.load(legacy_v2)
    run = legacy_v2 / "runs" / "run1"
    assert (run / "verifications" / "Demo-Legacy-v2-verify.ti2").is_file()


# ---- the demo projects themselves ---------------------------------------
def test_the_full_demo_opens_and_has_what_it_claims(tmp_path):
    build_full(tmp_path)
    root = tmp_path / "Demo-Full-RGB"
    proj = Project.load(root)

    assert [r.id for r in proj.all_runs()] == ["run1", "run2", "run3"]
    run1 = proj.run("run1")
    assert run1.measurement_ti3.is_file() and run1.profile_icc.is_file()
    assert len(run1.reads()) == 2, "averaging reads"
    run2 = proj.run("run2")
    assert len(run2.verifications()) == 2
    assert run2.load_meta().parent_run == "run1"
    run3 = proj.run("run3")
    assert run3.chart_ti2.is_file() and not run3.measurement_ti3.exists()


def test_the_history_demo_gives_the_report_something_to_trend(tmp_path):
    build_verify_history(tmp_path)
    proj = Project.load(tmp_path / "Demo-Verify-History")
    run = proj.run("run1")
    dates = run.verifications()
    assert len(dates) == 5, "a trend needs several"
    ids = [v.id for v in dates]
    assert ids == sorted(ids), "oldest first, so a trend reads left to right"
    for v in dates:
        assert v.measurement_ti3.is_file()
        assert list(v.reports_dir.glob("report_*.json")), v.id


def test_every_demo_project_opens_without_migration_warnings(tmp_path):
    for build in (build_full, build_verify_history, build_legacy_v1,
                  build_legacy_v2):
        build(tmp_path)
    for name in ("Demo-Full-RGB", "Demo-Verify-History", "Demo-Legacy-v1",
                 "Demo-Legacy-v2"):
        proj = Project.load(tmp_path / name)
        assert not proj.schema_too_new, name
        assert _schema(tmp_path / name) == 3, name
