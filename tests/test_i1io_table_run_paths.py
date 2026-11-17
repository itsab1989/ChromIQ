"""WHERE A TABLE MEASUREMENT LIVES IN A RUN (the i1iO table drive, build step 3).

Every path of a table measurement is a member of `Run` (CLAUDE.md: all path construction goes
through Project / Run / Calibration). Nothing uses them yet (the drive is not wired in), so these
tests pin the names, that asking creates nothing, and that existing projects are untouched:

* the measurement itself is the run's own `<stem>.ti3` (`Run.measurement_ti3`), as for every
  other instrument, so every measurement state applies;
* the chart's side file `<stem>.i1io.json` is `Run.i1io_side_file`;
* each START of the table gets a session folder `i1io-table/<stamp>/` at the run root, holding what
  the moved table modules write there (row plans, raw reading streams, cuts, the scan's
  pending marker) and the session log `session.log`. Not under `cache/`: `cache/` is "deleting never
  loses data" (docs/dev_folder_layout.md), and raw readings and the pending marker are data.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.file_manager import (I1IO_TABLE_DIRNAME, I1IO_TABLE_PENDING_MARKER, Project, Run)


def _run(tmp_path, name="My-Target", run_id="run1") -> Run:
    d = tmp_path / name / "runs" / run_id
    d.mkdir(parents=True)
    return Run.for_dir(d)


def test_the_measurement_is_the_runs_own_ti3_and_the_side_file_its_stem(tmp_path):
    run = _run(tmp_path)
    assert run.measurement_ti3 == run.dir / "My-Target.ti3"
    assert run.i1io_side_file == run.dir / "My-Target.i1io.json"


def test_session_folders_sit_at_the_run_root_not_in_cache(tmp_path):
    run = _run(tmp_path)
    assert I1IO_TABLE_DIRNAME == "i1io-table"
    assert run.i1io_table_dir == run.dir / "i1io-table"
    assert run.cache_dir not in run.i1io_table_dir.parents
    s = run.i1io_table_session_dir("20261117-101500")
    assert s == run.dir / "i1io-table" / "20261117-101500"
    assert run.i1io_table_log("20261117-101500") == s / "session.log"
    assert run.i1io_table_pending_marker("20261117-101500") == s / I1IO_TABLE_PENDING_MARKER
    assert run.i1io_table_session_dir("20261117-101500_2").name == "20261117-101500_2"


def test_the_marker_name_is_the_one_the_scan_module_writes():
    from workflow.i1io.table import scan
    assert I1IO_TABLE_PENDING_MARKER == scan.PENDING_MARKER


@pytest.mark.parametrize("bad", ["", "..", "../x", "a/b", "2026-11-17", "20261117-1015",
                                 "20261117-101500/..", "20261117-101500_", "x20261117-101500"])
def test_a_session_name_is_a_stamp_and_nothing_else(tmp_path, bad):
    with pytest.raises(ValueError):
        _run(tmp_path).i1io_table_session_dir(bad)


def test_asking_creates_nothing(tmp_path):
    run = _run(tmp_path)
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    run.i1io_side_file, run.i1io_table_dir, run.i1io_table_sessions()
    run.i1io_table_session_dir("20261117-101500"), run.i1io_table_log("20261117-101500")
    run.i1io_table_pending_marker("20261117-101500"), run.i1io_table_pending_markers()
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before
    assert run.i1io_table_sessions() == [] and run.i1io_table_pending_markers() == []


def test_sessions_and_markers_are_listed_oldest_first(tmp_path):
    run = _run(tmp_path)
    for stamp in ("20261117-120000", "20261117-090000", "20261117-090000_2"):
        run.i1io_table_session_dir(stamp).mkdir(parents=True)
    (run.i1io_table_dir / "not-a-session").mkdir()
    (run.i1io_table_dir / "20261117-130000").write_text("a file, not a folder", encoding="utf-8")
    assert [p.name for p in run.i1io_table_sessions()] == [
        "20261117-090000", "20261117-090000_2", "20261117-120000"]
    run.i1io_table_pending_marker("20261117-120000").write_text("SWITCH THE TABLE OFF", encoding="utf-8")
    assert run.i1io_table_pending_markers() == [run.i1io_table_pending_marker("20261117-120000")]


def test_the_table_modules_get_the_folder_and_name_their_own_files(tmp_path):
    """scan.py (moved unchanged) writes inside the folder it is given; the pending marker it
    leaves is the one `Run` finds."""
    from workflow.i1io.table import scan
    run = _run(tmp_path)
    d = run.i1io_table_session_dir("20261117-101500")
    d.mkdir(parents=True)
    scan._mark_pending(str(d))
    assert run.i1io_table_pending_markers() == [d / I1IO_TABLE_PENDING_MARKER]


def _tree(root: Path):
    return sorted((p.relative_to(root).as_posix(), p.is_dir(),
                   None if p.is_dir() else p.read_bytes()) for p in root.rglob("*"))


def test_loading_a_project_is_unchanged(tmp_path):
    """Migration-neutral: a fresh v2 project loads twice to the same tree, and a v1 project (the
    golden fixture) migrates without any i1io-table folder appearing."""
    proj = Project.create(tmp_path / "v2" / "My-Target", "My-Target")
    run = proj.current_run()
    (run.dir / "My-Target.ti2").write_text("CTI2\n", encoding="utf-8")
    (run.dir / "My-Target.ti3").write_text("CTI3\n", encoding="utf-8")
    Project.load(proj.root)
    first = _tree(tmp_path / "v2")
    again = Project.load(proj.root)
    assert _tree(tmp_path / "v2") == first
    assert again.current_run().i1io_table_sessions() == []
    import shutil
    golden = Path(__file__).resolve().parent / "golden" / "project_v1" / "Golden-Printer"
    v1 = tmp_path / "v1" / "Golden-Printer"
    shutil.copytree(golden, v1)
    migrated = Project.load(v1)
    assert not [x for x in (tmp_path / "v1").rglob("*") if x.name == I1IO_TABLE_DIRNAME]
    for r in migrated.all_runs():
        assert r.i1io_table_sessions() == [] and r.i1io_table_pending_markers() == []


def test_no_other_file_builds_a_table_session_path():
    root = Path(__file__).resolve().parent.parent
    hits = []
    for base in ("core", "ui", "workflow", "scripts"):
        for f in (root / base).rglob("*.py"):
            if f.name == "file_manager.py" and f.parent.name == "core":
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            if '"i1io-table"' in text or "'i1io-table'" in text or "session.log" in text:
                hits.append(os.fspath(f.relative_to(root)))
    assert not hits, hits
