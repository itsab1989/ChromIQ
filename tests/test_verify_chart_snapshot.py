"""#130 (Knut, 2026-07-25): each verification measurement snapshots the chart it
is about to measure, and "Restore Used Chart" puts that snapshot back.

Covers the rows of the posted test plan that are pure file logic: what is copied,
what is deliberately not, the no-recipe exception, the content-hash comparison,
the stem rename, and the transactional rollback."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.file_manager import Project
from workflow.verify_chart_snapshot import (
    files_to_snapshot, has_snapshot, live_chart_files,
    live_differs_from_snapshot, restore_chart, snapshot_chart, snapshot_dir,
    snapshot_files,
)


def _run_with_verify_chart(tmp_path, *, recipe=True, name="P"):
    proj = Project.create(tmp_path / name, name)
    run = proj.current_run(); run.ensure_dir()
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti1.write_text("TI1-v1", encoding="utf-8")
    run.verify_chart_ti2.write_text("TI2-v1", encoding="utf-8")
    if recipe:
        (run.verifications_dir / f"{run.verify_stem}.channels.json").write_text("{}", encoding="utf-8")
    (run.verifications_dir / f"{run.verify_stem}_01.tif").write_text("PAGE1", encoding="utf-8")
    (run.verifications_dir / f"{run.verify_stem}_02.tif").write_text("PAGE2", encoding="utf-8")
    return proj, run


def _dated(run, when="2026-07-25_143000"):
    v = run.verification(when); v.ensure_dir()
    return v


# ---- what gets snapshotted -----------------------------------------------
def test_snapshot_takes_chart_files_but_not_the_pages(tmp_path):
    proj, run = _run_with_verify_chart(tmp_path)
    v = _dated(run)

    snapshot_chart(v)

    names = sorted(p.name for p in snapshot_files(v))
    assert names == [f"{run.verify_stem}.channels.json",
                     f"{run.verify_stem}.ti1", f"{run.verify_stem}.ti2"]
    # the live chart is untouched — a snapshot copies, never moves
    assert run.verify_chart_ti2.read_text(encoding="utf-8") == "TI2-v1"
    assert len(run.verify_chart_tiffs()) == 2


def test_pages_are_snapshotted_when_there_is_no_recipe_to_rebuild_them(tmp_path):
    """Knut's rule: without a .json the images cannot be rebuilt, so they travel
    with the snapshot and a restore still ends with printable pages."""
    proj, run = _run_with_verify_chart(tmp_path, recipe=False)
    v = _dated(run)

    snapshot_chart(v)

    names = sorted(p.name for p in snapshot_files(v))
    assert f"{run.verify_stem}_01.tif" in names
    assert f"{run.verify_stem}_02.tif" in names


def test_folders_inside_verifications_are_never_snapshotted(tmp_path):
    proj, run = _run_with_verify_chart(tmp_path)
    (run.verifications_dir / "old").mkdir()
    (run.verifications_dir / "old" / "stale.ti2").write_text("x", encoding="utf-8")
    (run.verifications_dir / "reports").mkdir()
    v = _dated(run)

    snapshot_chart(v)

    assert all(p.is_file() for p in snapshot_files(v))
    assert "old" not in [p.name for p in snapshot_files(v)]
    assert not (snapshot_dir(v) / "old").exists()


def test_no_verification_chart_means_no_snapshot(tmp_path):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    v = _dated(run)

    assert snapshot_chart(v) is None
    assert has_snapshot(v) is False


# ---- has the live chart changed? -----------------------------------------
def test_unchanged_chart_compares_equal(tmp_path):
    proj, run = _run_with_verify_chart(tmp_path)
    v = _dated(run); snapshot_chart(v)

    assert live_differs_from_snapshot(v) is False


def test_a_changed_chart_is_detected_by_content_not_timestamp(tmp_path):
    """copy2 preserves mtimes, so only content can answer this honestly."""
    import os, time
    proj, run = _run_with_verify_chart(tmp_path)
    v = _dated(run); snapshot_chart(v)
    run.verify_chart_ti2.write_text("TI2-REPLACED", encoding="utf-8")
    # Force the mtime BACKWARDS: a "newer than" test would call this unchanged.
    old = time.time() - 10_000
    os.utime(run.verify_chart_ti2, (old, old))

    assert live_differs_from_snapshot(v) is True


def test_a_missing_live_file_counts_as_different(tmp_path):
    proj, run = _run_with_verify_chart(tmp_path)
    v = _dated(run); snapshot_chart(v)
    run.verify_chart_ti1.unlink()

    assert live_differs_from_snapshot(v) is True


# ---- restore --------------------------------------------------------------
def test_restore_puts_the_snapshot_back_and_keeps_folders(tmp_path):
    proj, run = _run_with_verify_chart(tmp_path)
    v = _dated(run); snapshot_chart(v)
    v.measurement_ti3.write_text("MEASURED", encoding="utf-8")
    run.verify_chart_ti2.write_text("TI2-REPLACED", encoding="utf-8")
    (run.verifications_dir / "old").mkdir()

    res = restore_chart(v)

    assert res.ok and not res.rolled_back
    assert run.verify_chart_ti2.read_text(encoding="utf-8") == "TI2-v1"
    assert v.measurement_ti3.read_text(encoding="utf-8") == "MEASURED"   # results untouched
    assert (run.verifications_dir / "old").exists()      # folders untouched
    assert snapshot_files(v), "the snapshot itself survives a restore"


def test_restore_reports_that_pages_need_rebuilding(tmp_path):
    proj, run = _run_with_verify_chart(tmp_path)
    v = _dated(run); snapshot_chart(v)

    res = restore_chart(v)

    assert res.images_restored is False
    assert res.needs_regeneration is False, "a recipe is present, so rebuild"


def test_restore_brings_the_pages_back_when_there_was_no_recipe(tmp_path):
    proj, run = _run_with_verify_chart(tmp_path, recipe=False)
    v = _dated(run); snapshot_chart(v)
    for p in run.verify_chart_tiffs():
        p.unlink()

    res = restore_chart(v)

    assert res.images_restored is True
    assert res.needs_regeneration is False
    assert len(run.verify_chart_tiffs()) == 2


def test_restore_renames_to_the_runs_current_verify_stem(tmp_path):
    """The project was renamed after the snapshot was taken."""
    proj, run = _run_with_verify_chart(tmp_path, name="Old-Name")
    v = _dated(run); snapshot_chart(v)
    old_stem = run.verify_stem
    # Simulate the rename: the run now answers to a new stem.
    proj2 = Project.create(tmp_path / "New-Name", "New-Name")
    run2 = proj2.current_run(); run2.ensure_dir()
    run2.verifications_dir.mkdir(parents=True, exist_ok=True)
    v2 = run2.verification(v.id); v2.ensure_dir()
    (v2.dir / "chart").mkdir()
    for p in snapshot_files(v):
        (v2.dir / "chart" / p.name).write_bytes(p.read_bytes())

    res = restore_chart(v2)

    assert res.ok
    assert run2.verify_chart_ti2.exists(), "restored under the CURRENT stem"
    assert run2.verify_chart_ti2.read_text(encoding="utf-8") == "TI2-v1"
    assert not (run2.verifications_dir / f"{old_stem}.ti2").exists()


def test_restore_rolls_back_and_changes_nothing_on_failure(tmp_path, monkeypatch):
    proj, run = _run_with_verify_chart(tmp_path)
    v = _dated(run); snapshot_chart(v)
    run.verify_chart_ti2.write_text("TI2-LIVE", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in live_chart_files(run)}

    import workflow.verify_chart_snapshot as M
    calls = {"n": 0}
    real_copy = M.shutil.copy2

    def boom(src, dst, *a, **k):
        calls["n"] += 1
        if calls["n"] == 2:            # fail midway through the restore
            raise OSError("disk full")
        return real_copy(src, dst, *a, **k)
    monkeypatch.setattr(M.shutil, "copy2", boom)

    res = restore_chart(v)

    assert res.rolled_back and not res.ok and "disk full" in res.error
    after = {p.name: p.read_bytes() for p in live_chart_files(run)}
    assert after == before, "a failed restore must leave the chart exactly as it was"


def test_restore_without_a_snapshot_is_a_no_op(tmp_path):
    proj, run = _run_with_verify_chart(tmp_path)
    v = _dated(run)

    res = restore_chart(v)

    assert not res.ok and res.error == "no snapshot"
    assert run.verify_chart_ti2.read_text(encoding="utf-8") == "TI2-v1"


def test_restore_into_an_empty_verifications_root_needs_no_stash(tmp_path):
    proj, run = _run_with_verify_chart(tmp_path)
    v = _dated(run); snapshot_chart(v)
    for p in live_chart_files(run):
        p.unlink()

    res = restore_chart(v)

    assert res.ok
    assert run.verify_chart_ti2.read_text(encoding="utf-8") == "TI2-v1"
