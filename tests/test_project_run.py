"""Tests for the Project / Run / Calibration API in core/file_manager.py.

These cover the lifecycle the redesigned workflow depends on:
  - Project.create / load / create_or_load round-trip
  - Run path properties (every artefact name)
  - Averaging via Run.promote_measurement_to_read + reads()
  - Pre-conditioning seed via Project.new_run(preconditioning_from=...)
  - Run.reset_chart_artefacts (what survives, what doesn't)
  - Calibration.exists / reset
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.file_manager import (
    Calibration,
    Project,
    ProjectManifest,
    Run,
    RunMeta,
)


# ---------------------------------------------------------------------------
# ProjectManifest / RunMeta
# ---------------------------------------------------------------------------

def test_project_manifest_fresh_defaults() -> None:
    from core.file_manager import SCHEMA_VERSION
    m = ProjectManifest.fresh("MyChart")
    assert m.schema_version == SCHEMA_VERSION == 3
    assert m.target_name == "MyChart"
    assert m.current_run == "run1"
    assert m.runs == ["run1"]
    assert m.created_at  # ISO timestamp, non-empty


def test_project_manifest_from_dict_ignores_unknown_keys() -> None:
    """Forward compatibility: a future field in project.json must not crash load()."""
    m = ProjectManifest.from_dict({
        "schema_version": 1,
        "target_name": "X",
        "current_run": "run1",
        "runs": ["run1"],
        "created_at": "now",
        "future_field": "ignored",
    })
    assert m.target_name == "X"


def test_run_meta_fresh_and_roundtrip() -> None:
    meta = RunMeta.fresh("run2", parent="run1")
    assert meta.run_id == "run2"
    assert meta.parent_run == "run1"
    assert meta.status == "in_progress"
    # Round-trip through dict
    from dataclasses import asdict
    restored = RunMeta.from_dict(asdict(meta))
    assert restored == meta


# ---------------------------------------------------------------------------
# Project lifecycle
# ---------------------------------------------------------------------------

def test_project_create_initialises_structure(tmp_path: Path) -> None:
    root = tmp_path / "MyChart"
    proj = Project.create(root, "MyChart")

    assert (root / "project.json").is_file()
    assert (root / "runs" / "run1").is_dir()
    assert (root / "runs" / "run1" / "meta.json").is_file()
    assert proj.current_run().id == "run1"
    assert proj.all_runs() == [proj.run("run1")] or len(proj.all_runs()) == 1


def test_project_create_writes_user_readme(tmp_path: Path) -> None:
    """`Where are my files.txt` lands at the project root and mentions the
    project name so the paths in the example lines are concrete."""
    proj = Project.create(tmp_path / "MyChart", "MyChart")
    readme = proj.root / "Where are my files.txt"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    # Concrete project name substituted into the example paths.
    assert "MyChart.icc" in text
    assert "MyChart-cal.ti3" in text
    assert "MyChart-i1profiler" in text
    assert "{name}" not in text
    # The guide's folder-first sections (#127) are present.
    assert "What the folders mean".upper() in text
    assert "cache" in text and "reports" in text and "exports" in text


def test_project_load_backfills_readme_when_missing(tmp_path: Path) -> None:
    """Older projects (created before the README shipped) get one on next load."""
    proj = Project.create(tmp_path / "P", "P")
    proj.readme_path.unlink()
    assert not proj.readme_path.exists()

    Project.load(tmp_path / "P")
    assert proj.readme_path.is_file()


def test_project_load_rewrites_blank_readme(tmp_path: Path) -> None:
    """A 0-byte README — the artefact a pre-fix Windows build left when
    write_readme crashed mid-write — is repopulated on next load."""
    proj = Project.create(tmp_path / "P", "P")
    proj.readme_path.write_text("")          # simulate the crash artefact
    assert proj.readme_path.stat().st_size == 0

    Project.load(tmp_path / "P")
    assert proj.readme_path.stat().st_size > 0
    assert "P.icc" in proj.readme_path.read_text(encoding="utf-8")


def test_project_load_does_not_overwrite_edited_readme(tmp_path: Path) -> None:
    """A README the user edited is left alone on load."""
    proj = Project.create(tmp_path / "P", "P")
    proj.readme_path.write_text("MY OWN NOTES — please leave alone\n", encoding="utf-8")

    Project.load(tmp_path / "P")
    assert proj.readme_path.read_text(encoding="utf-8") == "MY OWN NOTES — please leave alone\n"


def test_project_load_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "P"
    Project.create(root, "P")
    reloaded = Project.load(root)
    assert reloaded.target_name == "P"
    assert reloaded.current_run().id == "run1"


def test_project_load_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Project.load(tmp_path / "does_not_exist")


def test_project_create_or_load_loads_if_present(tmp_path: Path) -> None:
    root = tmp_path / "P"
    Project.create(root, "P")
    # Mutate the manifest so we can detect that load (not create) ran.
    (root / "project.json").write_text(json.dumps({
        "schema_version": 1, "created_at": "x",
        "target_name": "P", "current_run": "run1", "runs": ["run1"],
    }))
    proj = Project.create_or_load(root, "DIFFERENT")
    assert proj.target_name == "P", "should have loaded existing, not created fresh"


def test_project_create_or_load_creates_if_absent(tmp_path: Path) -> None:
    root = tmp_path / "Fresh"
    proj = Project.create_or_load(root, "Fresh")
    assert (root / "project.json").is_file()
    assert proj.current_run().id == "run1"


# ---------------------------------------------------------------------------
# Run — path properties
# ---------------------------------------------------------------------------

def test_run_path_properties(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    r = proj.current_run()
    # Chart stem is the (sanitised) project folder name — "P" in this test.
    assert r.stem == "P"

    expected = {
        r.chart_ti1:              "runs/run1/P.ti1",
        r.chart_ti2:              "runs/run1/P.ti2",
        r.chart_cht:              "runs/run1/P.cht",
        r.chart_ps:               "runs/run1/P.ps",
        r.chart_channels_json:    "runs/run1/P.channels.json",
        r.measurement_ti3:        "runs/run1/P.ti3",
        r.preconditioning_ti3:    "runs/run1/preconditioning.ti3",
        r.preconditioning_icc:    "runs/run1/preconditioning.icc",
        r.merged_ti3:             "runs/run1/merged.ti3",
        r.merged_icc:             "runs/run1/merged.icc",
        r.profile_icc:            "runs/run1/P.icc",
        r.meta_path:              "runs/run1/meta.json",
        r.reads_dir:              "runs/run1/reads",
    }
    for actual, suffix in expected.items():
        assert actual == proj.root / suffix, f"{actual} != {proj.root / suffix}"


def test_run_chart_tiffs_sorted_and_case_insensitive(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    r = proj.current_run()
    (r.dir / "P_02.tif").write_text("p2")
    (r.dir / "P_01.tif").write_text("p1")
    (r.dir / "P_03.TIF").write_text("p3")
    (r.dir / "P_04.tiff").write_text("p4")
    # A non-chart tiff must not be picked up.
    (r.dir / "other.tif").write_text("nope")
    tiffs = r.chart_tiffs()
    assert [p.name for p in tiffs] == ["P_01.tif", "P_02.tif", "P_03.TIF", "P_04.tiff"]


def test_run_chart_tiffs_finds_single_page_no_suffix(tmp_path: Path) -> None:
    """printtarg writes `<stem>.tif` (no _NN) for a one-page chart — it must be
    found, not silently skipped by a `<stem>_*.tif` (underscore) glob."""
    proj = Project.create(tmp_path / "P", "P")
    r = proj.current_run()
    (r.dir / "P.tif").write_text("single page")
    assert [p.name for p in r.chart_tiffs()] == ["P.tif"]


def test_run_stem_matches_project_folder(tmp_path: Path) -> None:
    """Stem derives from the project folder, so Run.for_dir works in isolation
    and stays consistent with the (sanitised) target name."""
    from core.file_manager import Run
    proj = Project.create(tmp_path / "printer-test-file", "printer-test-file")
    assert proj.current_run().stem == "printer-test-file"
    # Same answer for a project-less Run bound to the same directory.
    standalone = Run.for_dir(proj.current_run().dir)
    assert standalone.stem == "printer-test-file"
    assert standalone.chart_ti2.name == "printer-test-file.ti2"


# ---------------------------------------------------------------------------
# Run — averaging
# ---------------------------------------------------------------------------

def test_run_reads_empty_when_no_reads_dir(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    assert proj.current_run().reads() == []
    assert proj.current_run().next_read_index() == 1


def test_run_promote_measurement_to_read_increments(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    r = proj.current_run()

    r.measurement_ti3.write_text("M1")
    p1 = r.promote_measurement_to_read()
    assert p1.name == "read1.ti3"
    assert p1.read_text() == "M1"
    assert not r.measurement_ti3.exists(), "measurement.ti3 must be moved, not copied"

    r.measurement_ti3.write_text("M2")
    p2 = r.promote_measurement_to_read()
    assert p2.name == "read2.ti3"

    assert [p.name for p in r.reads()] == ["read1.ti3", "read2.ti3"]
    assert r.next_read_index() == 3


def test_run_promote_without_measurement_raises(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    with pytest.raises(FileNotFoundError):
        proj.current_run().promote_measurement_to_read()


def test_run_reads_ignores_non_matching_files(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    r = proj.current_run()
    r.reads_dir.mkdir()
    (r.reads_dir / "read1.ti3").write_text("R1")
    (r.reads_dir / "read2.ti3").write_text("R2")
    (r.reads_dir / "garbage.ti3").write_text("nope")
    (r.reads_dir / "readN.ti3").write_text("nope")  # not a number
    assert [p.name for p in r.reads()] == ["read1.ti3", "read2.ti3"]


def test_run_clear_reads_removes_dir(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    r = proj.current_run()
    r.reads_dir.mkdir()
    (r.reads_dir / "read1.ti3").write_text("R1")
    r.clear_reads()
    assert not r.reads_dir.exists()


# ---------------------------------------------------------------------------
# Pre-conditioning seed (the original double-counting scenario)
# ---------------------------------------------------------------------------

def test_new_run_seeds_preconditioning_from_parent(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    parent = proj.current_run()
    parent.measurement_ti3.write_text("PARENT MEASUREMENT")
    parent.profile_icc.write_text("PARENT PROFILE")

    child = proj.new_run(preconditioning_from=parent)

    assert child.id == "run2"
    assert proj.current_run().id == "run2", "new_run must switch current"
    assert proj.all_runs() == [proj.run("run1"), proj.run("run2")] or \
           [r.id for r in proj.all_runs()] == ["run1", "run2"]

    assert child.preconditioning_ti3.read_text() == "PARENT MEASUREMENT"
    assert child.preconditioning_icc.read_text() == "PARENT PROFILE"
    assert child.has_preconditioning()
    assert child.load_meta().parent_run == "run1"
    assert child.load_meta().preconditioning_source_run == "run1"

    # Parent is untouched.
    assert parent.measurement_ti3.read_text() == "PARENT MEASUREMENT"
    assert parent.profile_icc.read_text() == "PARENT PROFILE"


def test_new_run_without_parent_has_no_preconditioning(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    r2 = proj.new_run()
    assert r2.id == "run2"
    assert not r2.has_preconditioning()
    assert r2.load_meta().parent_run is None


def test_new_run_requires_parent_artefacts(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    parent = proj.current_run()
    # No measurement / profile written → must raise
    with pytest.raises(FileNotFoundError):
        proj.new_run(preconditioning_from=parent)


def test_run_2_reads_dir_isolated_from_run_1(tmp_path: Path) -> None:
    """The whole point of the redesign: cross-run averaging collision impossible."""
    proj = Project.create(tmp_path / "P", "P")
    r1 = proj.current_run()
    r1.reads_dir.mkdir()
    (r1.reads_dir / "read1.ti3").write_text("V1 R1")
    (r1.reads_dir / "read2.ti3").write_text("V1 R2")
    r1.measurement_ti3.write_text("V1 AVG")
    r1.profile_icc.write_text("V1 ICC")

    r2 = proj.new_run(preconditioning_from=r1)

    # Run 2 starts with NO reads visible from run 1's reads/ directory.
    assert r2.reads() == []
    assert r2.next_read_index() == 1

    # Run 1 reads still exist where they were (preserved for diagnostics).
    assert (r1.reads_dir / "read1.ti3").read_text() == "V1 R1"


def test_averaged_run1_to_refined_run2_no_double_count(tmp_path: Path) -> None:
    """End-to-end of the original double-counting bug — now impossible.

    Run 1 with averaging produces reads/ + an averaged chart.ti3 + profile.
    Promoting to run 2 seeds preconditioning.* from run 1's *averaged* outputs.
    Run 2's own averaging set lands in a fresh reads/ that never sees run 1's
    reads, so a later merge with preconditioning.ti3 cannot re-include run 1's
    individual reads.
    """
    proj = Project.create(tmp_path / "P", "P")

    # --- Run 1: averaged ---
    r1 = proj.current_run()
    r1.reads_dir.mkdir()
    (r1.reads_dir / "read1.ti3").write_text("V1 R1")
    (r1.reads_dir / "read2.ti3").write_text("V1 R2")
    r1.measurement_ti3.write_text("V1 AVERAGED")       # chart.ti3 = mean of reads
    r1.profile_icc.write_text("V1 PROFILE")

    # --- Promote to run 2 (refinement) ---
    r2 = proj.new_run(preconditioning_from=r1)
    # Pre-conditioning seed is run 1's AVERAGED measurement, not its raw reads.
    assert r2.preconditioning_ti3.read_text() == "V1 AVERAGED"

    # --- Run 2: its own averaging set ---
    r2.reads_dir.mkdir()
    (r2.reads_dir / "read1.ti3").write_text("V2 R1")
    (r2.reads_dir / "read2.ti3").write_text("V2 R2")
    # Run 2 only ever sees its own reads.
    assert [p.read_text() for p in r2.reads()] == ["V2 R1", "V2 R2"]
    # The merge inputs would be r2.measurement_ti3 + r2.preconditioning_ti3 —
    # exactly one copy of run 1's data (the average), never the raw reads.
    assert r1.reads_dir != r2.reads_dir


# ---------------------------------------------------------------------------
# Run.reset_chart_artefacts
# ---------------------------------------------------------------------------

def test_reset_chart_artefacts_preserves_preconditioning_and_meta(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    r1 = proj.current_run()
    r1.measurement_ti3.write_text("M")
    r1.profile_icc.write_text("ICC")
    r2 = proj.new_run(preconditioning_from=r1)
    # Now run 2 has preconditioning.* and meta.json. Add some chart artefacts
    # under the project-name stem ("P" here).
    r2.chart_ti1.write_text("TI1")
    r2.chart_ti2.write_text("TI2")
    (r2.dir / "P_01.tif").write_text("TIFF")
    r2.chart_channels_json.write_text("{}")
    # The vector-PDF export, .cie and .strips.json used to survive a re-gen
    # (Basti: a stale PDF lingered in the working folder).
    (r2.dir / "P.pdf").write_text("PDF")
    (r2.dir / "P.cie").write_text("CIE")
    (r2.dir / "P.strips.json").write_text("{}")
    r2.measurement_ti3.write_text("MEASURED")
    r2.merged_ti3.write_text("MERGED")
    r2.profile_icc.write_text("ICC2")
    r2.reads_dir.mkdir()
    (r2.reads_dir / "read1.ti3").write_text("R1")

    r2.reset_chart_artefacts()

    # Wiped:
    for name in ("P.ti1", "P.ti2", "P_01.tif", "P.channels.json",
                 "P.strips.json", "P.pdf", "P.cie",
                 "P.ti3", "merged.ti3", "P.icc"):
        assert not (r2.dir / name).exists(), f"{name} should be wiped"
    assert not r2.reads_dir.exists()

    # Preserved:
    assert r2.preconditioning_ti3.exists()
    assert r2.preconditioning_icc.exists()
    assert r2.meta_path.exists()


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def test_calibration_paths(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    cal = proj.calibration
    # Calibration stem = "<project>-cal" so the printed sheet is named after
    # the project but is distinguishable from the profiling chart.
    assert cal.stem == "P-cal"
    assert cal.dir == proj.root / "cal"
    assert cal.cal_path == proj.root / "cal" / "P-cal.cal"
    assert cal.ti3 == proj.root / "cal" / "P-cal.ti3"


def test_calibration_exists_false_when_empty(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    assert not proj.calibration.exists()


def test_calibration_exists_true_after_cal_written(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    cal = proj.calibration
    cal.ensure_dir()
    cal.cal_path.write_text("CAL")
    assert cal.exists()


def test_calibration_reset_removes_dir(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    cal = proj.calibration
    cal.ensure_dir()
    cal.cal_path.write_text("CAL")
    cal.ti3.write_text("TI3")
    cal.reset()
    assert not cal.dir.exists()


# ---------------------------------------------------------------------------
# FileManager.project()
# ---------------------------------------------------------------------------

class _FakeSettings:
    def __init__(self, root: Path) -> None:
        self._root = root

    def get(self, key: str, default=None):
        if key == "custom_output_path":
            return str(self._root)
        return default


def test_file_manager_project_creates_on_first_access(tmp_path: Path) -> None:
    from core.file_manager import FileManager
    fm = FileManager(_FakeSettings(tmp_path))
    fm.set_target_name("MyChart")
    proj = fm.project()
    assert proj.target_name == "MyChart"
    assert proj.root == tmp_path / "MyChart"
    assert (tmp_path / "MyChart" / "project.json").is_file()


def test_file_manager_project_cached_until_target_name_changes(tmp_path: Path) -> None:
    from core.file_manager import FileManager
    fm = FileManager(_FakeSettings(tmp_path))
    fm.set_target_name("A")
    p1 = fm.project()
    p2 = fm.project()
    assert p1 is p2

    fm.set_target_name("B")
    p3 = fm.project()
    assert p3 is not p1
    assert p3.target_name == "B"


# ---------------------------------------------------------------------------
# Project.rename — relabel an in-place project (stems + manifest + readme)
# ---------------------------------------------------------------------------

def test_project_rename_fixes_stems_manifest_and_readme(tmp_path: Path) -> None:
    # A renamed folder must also rename every artefact whose stem is the old
    # project name, or Run.stem (derived from the folder) points at files that
    # no longer exist.
    proj = Project.create(tmp_path / "Old", "Old")
    run = proj.current_run()
    run.chart_ti1.write_text("TI1")
    run.chart_ti2.write_text("TI2")
    (run.dir / "Old_01.tif").write_text("PAGE")
    run.chart_channels_json.write_text("{}")
    cal = proj.calibration
    cal.ensure_dir()
    cal.cal_path.write_text("CAL")
    cal.ti3.write_text("CALTI3")
    proj.ensure_exports_dir()
    (proj.exports_dir / "Old-i1profiler.pxf").write_text("PXF")
    # Chart hand-off sidecars carry the stem too and must follow the rename.
    run.chart_cht.write_text("CHT")
    (run.dir / "Old.cie").write_text("CIE")
    (run.dir / "Old-colours.txt").write_text("#ffffff")
    (run.dir / "Old-i1profiler.txt").write_text("TXT")
    # A user's own file that merely starts with the stem must NOT be renamed.
    (proj.root / "Old-notes.txt").write_text("keep me")

    # Simulate the caller having moved the folder, then rename contents.
    moved = tmp_path / "New"
    proj.root.rename(moved)
    proj = Project.load(moved)
    proj.rename("New")

    run = proj.current_run()
    assert proj.target_name == "New"
    assert run.chart_ti1.exists() and run.chart_ti1.name == "New.ti1"
    assert run.chart_ti2.exists()
    assert (run.dir / "New_01.tif").exists()
    assert run.chart_channels_json.name == "New.channels.json"
    assert proj.calibration.cal_path.name == "New-cal.cal"
    assert proj.calibration.ti3.name == "New-cal.ti3"
    assert (proj.exports_dir / "New-i1profiler.pxf").exists()
    # Hand-off sidecars followed the rename.
    assert run.chart_cht.name == "New.cht" and run.chart_cht.exists()
    assert (run.dir / "New.cie").exists()
    assert (run.dir / "New-colours.txt").exists()
    assert (run.dir / "New-i1profiler.txt").exists()
    # Old-stem files are gone; the user's note is untouched.
    assert not (run.dir / "Old.ti1").exists()
    assert not (run.dir / "Old-colours.txt").exists()
    assert (moved / "Old-notes.txt").read_text() == "keep me"
    # Manifest + README reflect the new name.
    manifest = json.loads(proj.manifest_path.read_text())
    assert manifest["target_name"] == "New"
    assert "New" in proj.readme_path.read_text(encoding="utf-8")


def test_project_rename_noop_when_same_name(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "Same", "Same")
    proj.current_run().chart_ti1.write_text("TI1")
    proj.rename("Same")
    assert proj.current_run().chart_ti1.exists()


# ---------------------------------------------------------------------------
# FileManager.rename_existing_project / delete_project_folder
# ---------------------------------------------------------------------------

def test_file_manager_rename_existing_project(tmp_path: Path) -> None:
    from core.file_manager import FileManager
    fm = FileManager(_FakeSettings(tmp_path))
    fm.set_target_name("Alpha")
    proj = fm.project()  # creates ~/Alpha
    proj.current_run().chart_ti2.write_text("TI2")

    new_root = fm.rename_existing_project("Alpha", "Beta")

    assert new_root == tmp_path / "Beta"
    assert not (tmp_path / "Alpha").exists()
    assert (tmp_path / "Beta" / "project.json").is_file()
    assert fm.get_target_name() == "Beta"
    # Chart stem followed the folder.
    assert (fm.project().current_run().dir / "Beta.ti2").exists()


def test_file_manager_rename_refuses_existing_target(tmp_path: Path) -> None:
    from core.file_manager import FileManager
    fm = FileManager(_FakeSettings(tmp_path))
    fm.set_target_name("Alpha")
    fm.project()
    fm.set_target_name("Beta")
    fm.project()  # Beta now exists on disk
    with pytest.raises(FileExistsError):
        fm.rename_existing_project("Alpha", "Beta")


def test_file_manager_delete_project_folder(tmp_path: Path) -> None:
    from core.file_manager import FileManager
    fm = FileManager(_FakeSettings(tmp_path))
    fm.set_target_name("Gone")
    fm.project()
    assert (tmp_path / "Gone").exists()
    fm.delete_project_folder("Gone")
    assert not (tmp_path / "Gone").exists()


def test_file_manager_delete_refuses_non_project(tmp_path: Path) -> None:
    from core.file_manager import FileManager
    fm = FileManager(_FakeSettings(tmp_path))
    # A bare folder with no project.json must not be deleted.
    (tmp_path / "NotAProject").mkdir()
    fm.delete_project_folder("NotAProject")
    assert (tmp_path / "NotAProject").exists()


# ---------------------------------------------------------------------------
# v2 sub-folder API + rename across sub-folders (#127)
# ---------------------------------------------------------------------------

def test_run_v2_subdir_properties(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    assert run.reports_dir == run.dir / "reports"
    assert run.exports_dir == run.dir / "exports"
    assert run.cache_dir == run.dir / "cache"
    assert run.ensure_cache_dir().is_dir()
    assert proj.calibration.exports_dir == proj.calibration.dir / "exports"


def test_project_rename_covers_cal_sidecars_and_subfolders(tmp_path: Path) -> None:
    """The #127 regex fix: a calibration chart's exports ("<stem>-cal-colours.txt")
    are renamed too, and files inside reports/exports/cache follow the stem."""
    import shutil as _sh
    proj = Project.create(tmp_path / "Old", "Old")
    run = proj.current_run()
    run.ensure_exports_dir().joinpath("Old-colours.txt").write_text("x")
    run.ensure_exports_dir().joinpath("Old-i1profiler.pxf").write_text("x")
    run.ensure_reports_dir().joinpath("Refine_Strips_Old.txt").write_text("x")
    cal = proj.calibration
    cal.ensure_dir()
    (cal.dir / "Old-cal.ti3").write_text("x")
    from core.file_manager import ensure_subdir
    ensure_subdir(cal.exports_dir).joinpath("Old-cal-colours.txt").write_text("x")
    ensure_subdir(cal.exports_dir).joinpath("Old-cal-i1profiler.txt").write_text("x")
    (run.dir / "Old-notes.txt").write_text("user file")     # must NOT rename

    _sh.move(str(tmp_path / "Old"), str(tmp_path / "New"))
    proj2 = Project.load(tmp_path / "New")
    proj2.rename("New")

    run2 = proj2.current_run()
    assert (run2.exports_dir / "New-colours.txt").exists()
    assert (run2.exports_dir / "New-i1profiler.pxf").exists()
    assert (proj2.calibration.dir / "New-cal.ti3").exists()
    assert (proj2.calibration.exports_dir / "New-cal-colours.txt").exists()
    assert (proj2.calibration.exports_dir / "New-cal-i1profiler.txt").exists()
    assert (run2.dir / "Old-notes.txt").exists()            # user file untouched
    # Refine_Strips keeps its own (report) name — not a stem-carrying artefact
    assert (run2.reports_dir / "Refine_Strips_Old.txt").exists()


def test_project_rename_covers_verification_stems(tmp_path: Path) -> None:
    """#130 Hole 8: a project rename also renames the shared verify-chart files
    (<stem>-verify.*) and the dated verification measurements
    (verifications/<date>/<stem>-verify.ti3), plus their exports sidecars."""
    import shutil as _sh
    import datetime as _dt
    proj = Project.create(tmp_path / "Old", "Old")
    run = proj.current_run(); run.ensure_dir()
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("v")                        # Old-verify.ti2
    (run.verifications_dir / f"{run.verify_stem}_01.tif").write_text("t")
    from core.file_manager import ensure_subdir
    ensure_subdir(run.verifications_dir / "exports").joinpath(
        f"{run.verify_stem}-colours.txt").write_text("x")
    v = run.new_verification(_dt.datetime(2026, 6, 1, 9, 0, 0)); v.ensure_dir()
    v.measurement_ti3.write_text("vm")                          # Old-verify.ti3

    _sh.move(str(tmp_path / "Old"), str(tmp_path / "New"))
    proj2 = Project.load(tmp_path / "New"); proj2.rename("New")

    r = proj2.current_run()
    assert r.verify_chart_ti2.exists() and r.verify_chart_ti2.name == "New-verify.ti2"
    assert (r.verifications_dir / f"{r.verify_stem}_01.tif").exists()
    assert (r.verifications_dir / "exports" / f"{r.verify_stem}-colours.txt").exists()
    assert r.verification("2026-06-01_090000").measurement_ti3.exists()
    assert not list(r.dir.rglob("Old*"))                        # nothing stale left


# ---------------------------------------------------------------------------
# #130: verification-run model + v2→v3 migration
# ---------------------------------------------------------------------------

def test_verification_paths_and_new_verification(tmp_path: Path) -> None:
    from core.file_manager import Verification
    proj = Project.create(tmp_path / "Canon-Pro300", "Canon-Pro300")
    run = proj.current_run()
    assert run.verify_stem == "Canon-Pro300-verify"
    assert run.verifications_dir == run.dir / "verifications"
    assert run.verify_chart_ti2 == run.verifications_dir / "Canon-Pro300-verify.ti2"
    assert run.has_verify_chart() is False
    assert run.verifications() == []

    v = run.new_verification()
    assert isinstance(v, Verification)
    assert v.dir.parent == run.verifications_dir
    assert v.measurement_ti3 == v.dir / "Canon-Pro300-verify.ti3"
    assert v.reports_dir == v.dir / "reports"
    assert v.exists() is False
    # Materialise it → it shows up in the sorted history.
    v.ensure_dir()
    v.measurement_ti3.write_text("CTI3\n")
    assert v.exists() is True
    ids = [x.id for x in run.verifications()]
    assert ids == [v.id]
    # for_dir round-trips (project-less path ops).
    v2 = Verification.for_dir(v.dir)
    assert v2.measurement_ti3 == v.measurement_ti3


def test_new_verification_ids_are_unique_same_second(tmp_path: Path) -> None:
    from datetime import datetime
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    when = datetime(2026, 7, 15, 10, 30, 0)
    a = run.new_verification(when); a.ensure_dir()
    b = run.new_verification(when); b.ensure_dir()
    assert a.id != b.id                      # collision suffix
    assert b.id.startswith(a.id)


def test_v2_to_v3_migration_folds_legacy_verify_ti3(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    # Simulate a pre-#130 project: a flat <stem>-verify.ti3 in the run root,
    # schema 2 on disk.
    legacy = run.dir / "P-verify.ti3"
    legacy.write_text("CTI3\n")
    proj._manifest.schema_version = 2
    proj.save_manifest()

    reloaded = Project.load(proj.root)
    assert reloaded._manifest.schema_version == 3
    assert not legacy.exists()                       # moved out of the root
    vs = reloaded.current_run().verifications()
    assert len(vs) == 1
    assert vs[0].measurement_ti3.is_file()
    assert vs[0].measurement_ti3.read_text().startswith("CTI3")


def test_archive_to_old_moves_existing_and_dedups(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    (run.dir / "P.ti3").write_text("meas")
    reads = run.reads_dir; reads.mkdir(); (reads / "read1.ti3").write_text("r1")
    missing = run.dir / "nope.icc"                 # doesn't exist → skipped

    dest = run.archive_to_old([run.dir / "P.ti3", reads, missing])
    assert dest is not None and dest.parent == run.old_dir
    assert (dest / "P.ti3").read_text() == "meas"  # file moved
    assert (dest / "reads" / "read1.ti3").is_file() # folder moved whole
    assert not (run.dir / "P.ti3").exists()         # gone from the run root
    assert not reads.exists()

    # Nothing to archive → None, no folder churn.
    assert run.archive_to_old([run.dir / "ghost.ti3"]) is None

    # A second archive of a same-named file de-dups within its own dated folder.
    (run.dir / "P.ti3").write_text("meas2")
    import datetime as _dt
    d2 = run.archive_to_old([run.dir / "P.ti3"], when=_dt.datetime(2026, 7, 15, 10, 30, 0))
    (run.dir / "P.ti3").write_text("meas3")
    d3 = run.archive_to_old([run.dir / "P.ti3"], when=_dt.datetime(2026, 7, 15, 10, 30, 0))
    assert d2 == d3                                 # same timestamped folder
    names = sorted(p.name for p in d2.iterdir())
    assert names == ["P.ti3", "P_1.ti3"]            # de-duped


def test_adopt_run_chart_as_verify(tmp_path: Path) -> None:
    proj = Project.create(tmp_path / "Canon", "Canon")
    run = proj.current_run(); run.ensure_dir()
    stem = run.stem
    # A freshly generated chart at the run root (chart files + two pages) +
    # a measurement/profile that must NOT move, and an exports sidecar.
    for ext in (".ti1", ".ti2", ".cht", ".channels.json"):
        (run.dir / f"{stem}{ext}").write_text("x")
    (run.dir / f"{stem}_01.tif").write_text("p1")
    (run.dir / f"{stem}_02.tif").write_text("p2")
    (run.dir / f"{stem}.ti3").write_text("meas")     # must stay
    (run.dir / f"{stem}.icc").write_text("prof")     # must stay
    run.ensure_exports_dir()
    (run.exports_dir / f"{stem}-colours.txt").write_text("c")

    ti2 = run.adopt_run_chart_as_verify()
    assert ti2 == run.verify_chart_ti2 and ti2.is_file()
    # Chart files moved + renamed to the -verify stem, in verifications/.
    assert run.verify_chart_ti1.is_file() and run.verify_chart_cht.is_file()
    assert (run.verifications_dir / f"{stem}-verify_01.tif").is_file()
    assert (run.verifications_dir / f"{stem}-verify_02.tif").is_file()
    # The chart files are gone from the run root.
    assert not (run.dir / f"{stem}.ti2").exists()
    assert not (run.dir / f"{stem}_01.tif").exists()
    # Measurement + profile stayed put.
    assert (run.dir / f"{stem}.ti3").is_file()
    assert (run.dir / f"{stem}.icc").is_file()
    # Sidecar followed the chart.
    assert (run.verifications_dir / "exports" / f"{stem}-verify-colours.txt").is_file()

    # Nothing to adopt → None.
    proj2 = Project.create(tmp_path / "P2", "P2")
    assert proj2.current_run().adopt_run_chart_as_verify() is None


def test_adopt_single_page_verify_chart_moves_its_tiff(tmp_path: Path) -> None:
    """#130 (Knut: 'Run type = Verification shows no preview'): a single-page
    chart's TIFF is '<stem>.tif' with no _NN suffix, so it must move into
    verifications/ too — otherwise the verify chart has no page bitmap and never
    previews (and Print/Measure get nothing)."""
    proj = Project.create(tmp_path / "Canon", "Canon")
    run = proj.current_run(); run.ensure_dir()
    stem = run.stem
    for ext in (".ti1", ".ti2", ".channels.json"):
        (run.dir / f"{stem}{ext}").write_text("x")
    (run.dir / f"{stem}.tif").write_text("single page")     # NO _NN suffix

    run.adopt_run_chart_as_verify()
    assert (run.verifications_dir / f"{stem}-verify.tif").is_file()
    assert not (run.dir / f"{stem}.tif").exists()           # not left behind
    assert run.verify_chart_tiffs() == [run.verifications_dir / f"{stem}-verify.tif"]


def test_readopt_smaller_verify_chart_leaves_no_stale_pages(tmp_path: Path) -> None:
    """#130 beta-2 test #2: regenerating a SMALLER verification chart (fewer
    pages) must not leave the old higher-numbered page behind — verify_chart_
    tiffs() globs the folder, so an orphan made the preview show a phantom page.
    The dated verification history must survive the chart replacement."""
    import datetime as dt
    proj = Project.create(tmp_path / "Canon", "Canon")
    run = proj.current_run(); run.ensure_dir()
    stem = run.stem

    def _generate(pages: int) -> None:
        for p in list(run.dir.glob(f"{stem}_*.tif")):
            p.unlink()
        for ext in (".ti1", ".ti2", ".cht", ".channels.json"):
            (run.dir / f"{stem}{ext}").write_text("x")
        for i in range(1, pages + 1):
            (run.dir / f"{stem}_{i:02d}.tif").write_text("p")

    _generate(2); run.adopt_run_chart_as_verify()
    assert len(run.verify_chart_tiffs()) == 2

    # A real verification measurement in a dated folder — must be preserved.
    v = run.new_verification(dt.datetime(2026, 6, 1, 9, 0, 0)); v.ensure_dir()
    v.measurement_ti3.write_text("meas")

    _generate(1); run.adopt_run_chart_as_verify()
    assert len(run.verify_chart_tiffs()) == 1                 # no stale _02.tif
    assert not (run.verifications_dir / f"{stem}-verify_02.tif").exists()
    assert run.verification("2026-06-01_090000").measurement_ti3.is_file()  # history kept
