"""Bar-aware external-chart import (#130 unified file-handling model) — the pure
destination + old/-archive logic that the load dialogs call. Covers the Model-A
combination matrix headless (no Qt, no Argyll)."""
from __future__ import annotations

from pathlib import Path

from core.file_manager import Project
from core.measurement_target import (RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION,
                                     MeasurementTarget)
from workflow.chart_import import (archive_run_for_replace, copy_whole_project,
                                   import_external_chart, is_full_project,
                                   resolve_import_run)


# ---- helpers --------------------------------------------------------------
def _external_chart(folder: Path, stem: str, *, pages=2, ti3=False, icc=False):
    """A loose external chart: <stem>.ti1/.ti2/.cht/.channels.json + pages,
    optionally a sibling .ti3 / .icc."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}.ti1").write_text("ti1")
    ti2 = folder / f"{stem}.ti2"; ti2.write_text("ti2")
    (folder / f"{stem}.cht").write_text("cht")
    (folder / f"{stem}.channels.json").write_text("{}")
    tiffs = []
    for i in range(1, pages + 1):
        t = folder / f"{stem}_{i:02d}.tif"; t.write_text("tif"); tiffs.append(t)
    if ti3:
        (folder / f"{stem}.ti3").write_text("meas")
    if icc:
        (folder / f"{stem}.icc").write_text("prof")
    return ti2, (folder / f"{stem}.ti1"), tiffs


def _target(profiling=True, run=""):
    return MeasurementTarget(
        run_type=RUN_TYPE_PROFILING if profiling else RUN_TYPE_VERIFICATION,
        profile_run=run)


# ---- New run --------------------------------------------------------------
def test_new_run_profiling_full_set(tmp_path):
    proj = Project.create(tmp_path / "P", "P")
    proj.current_run().ensure_dir()                    # run1 exists (empty)
    ti2, ti1, tiffs = _external_chart(tmp_path / "ext", "src", ti3=True, icc=True)
    out = import_external_chart(ti2, ti1, tiffs, proj, _target(True, ""))
    run = Project.load(proj.root).run("run2")          # New run → run2
    assert out == run.chart_ti2 and run.chart_ti2.is_file()
    assert run.measurement_ti3.is_file() and run.profile_icc.is_file()  # full set
    assert len(run.chart_tiffs()) == 2


def test_new_run_verification_chart_only(tmp_path):
    proj = Project.create(tmp_path / "P", "P")
    proj.current_run().ensure_dir()
    ti2, ti1, tiffs = _external_chart(tmp_path / "ext", "src", ti3=True, icc=True)
    out = import_external_chart(ti2, ti1, tiffs, proj, _target(False, ""))
    run = Project.load(proj.root).run("run2")
    assert out == run.verify_chart_ti2 and run.verify_chart_ti2.is_file()
    # chart-only: NO icc/ti3 copied anywhere in the run
    assert not run.profile_icc.exists()
    assert not (run.verifications_dir / f"{run.verify_stem}.ti3").exists()
    assert not (run.verifications_dir / f"{run.verify_stem}.icc").exists()
    assert len(run.verify_chart_tiffs()) == 2


# ---- Overwrite · Replace archives to old/ ---------------------------------
def test_overwrite_profiling_replace_archives_incl_verifications(tmp_path):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    # existing run1 content: chart + measurement + profile + a verification
    (run.chart_ti2).write_text("old"); (run.measurement_ti3).write_text("m")
    (run.profile_icc).write_text("icc")
    import datetime as dt
    v = run.new_verification(dt.datetime(2026, 6, 1, 9, 0, 0)); v.ensure_dir()
    v.measurement_ti3.write_text("verif")

    ti2, ti1, tiffs = _external_chart(tmp_path / "ext", "src", ti3=True, icc=True)
    import_external_chart(ti2, ti1, tiffs, proj, _target(True, "run1"), replace=True)

    r = Project.load(proj.root).run("run1")
    old = r.old_dir
    assert old.exists()
    arch = next(old.iterdir())
    # displaced profiling files + the verifications tree are under old/
    assert (arch / f"{r.stem}.icc").exists() or (arch / f"{r.stem}.ti3").exists()
    assert (arch / "verifications").exists()
    # the new chart is in the run root; measurement/profile from the source too
    assert r.chart_ti2.read_text() == "ti2"
    # the live verifications/ no longer holds the old dated check
    assert not r.verification("2026-06-01_090000").measurement_ti3.exists()


def test_overwrite_verification_replace_moves_verifications_keeps_profile(tmp_path):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    run.measurement_ti3.write_text("m"); run.profile_icc.write_text("icc")
    # a verify chart + a dated verification already present
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("oldverify")
    import datetime as dt
    v = run.new_verification(dt.datetime(2026, 6, 1, 9, 0, 0)); v.ensure_dir()
    v.measurement_ti3.write_text("verif")

    ti2, ti1, tiffs = _external_chart(tmp_path / "ext", "src", pages=1)
    import_external_chart(ti2, ti1, tiffs, proj, _target(False, "run1"), replace=True)

    # Knut's ruling of 2026-07-25: a verification Replace acts ONLY on the files
    # at the root of verifications/, archives them INSIDE that folder, and keeps
    # the dated verification results where the user left them.
    r = Project.load(proj.root).run("run1")
    arch = next(r.verifications_old_dir.iterdir())
    assert (arch / f"{r.verify_stem}.ti2").exists()          # old verify chart archived
    assert not r.old_dir.exists()                            # run root untouched
    assert r.verification("2026-06-01_090000").measurement_ti3.exists(), \
        "dated verification results are kept, not archived"
    assert r.verify_chart_ti2.read_text() == "ti2"           # new verify chart installed
    assert r.measurement_ti3.exists() and r.profile_icc.exists()  # profile untouched


# ---- run resolution -------------------------------------------------------
def test_resolve_import_run(tmp_path):
    proj = Project.create(tmp_path / "P", "P"); proj.current_run().ensure_dir()
    proj.new_run()                                           # run2 current
    assert resolve_import_run(proj, _target(True, "run1")).id == "run1"
    assert Project.load(proj.root).current_run().id == "run1"
    assert resolve_import_run(proj, _target(True, "")).id == "run3"   # New run


# ---- whole-project copy (A1b) ---------------------------------------------
def test_copy_whole_project(tmp_path):
    src = Project.create(tmp_path / "src" / "Q", "Q")
    r = src.current_run(); r.ensure_dir(); r.chart_ti2.write_text("c")
    wd = tmp_path / "work"; wd.mkdir()
    dest = copy_whole_project(src.root, wd, "Q")
    assert (dest / "project.json").is_file()
    assert (dest / "runs" / "run1" / "Q.ti2").is_file()
    # collision without replace raises; with replace archives + overwrites
    import pytest
    with pytest.raises(FileExistsError):
        copy_whole_project(src.root, wd, "Q")
    dest2 = copy_whole_project(src.root, wd, "Q", replace=True)
    assert (dest2 / "old").exists() and (dest2 / "project.json").is_file()


def test_is_full_project(tmp_path):
    src = Project.create(tmp_path / "Q", "Q"); r = src.current_run(); r.ensure_dir()
    r.chart_ti2.write_text("c")
    assert is_full_project(r.chart_ti2) == src.root
    loose = tmp_path / "loose" / "x.ti2"; loose.parent.mkdir(); loose.write_text("x")
    assert is_full_project(loose) is None
