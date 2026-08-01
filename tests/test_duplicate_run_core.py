"""#130: the Duplicate button's file work.

Knut and Sebastian chose this over archiving a run's files whenever its chart
was regenerated (2026-08-01, "course B"). His reasoning for dropping the archive
model: moving everything into ``old/`` *"basically means to start fresh, and
that is better done by making a new run"*. So Duplicate never moves or
overwrites anything — it copies a run's work somewhere new to carry on from.

The copy list is his, settled over three exchanges on that day: chart,
measurement, profile, refinement seed, and the reports and export sidecars that
describe them. Never ``meta.json``, ``verifications/``, ``old/`` or ``cache/``.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Project                    # noqa: E402


@pytest.fixture
def project(tmp_path):
    proj = Project.create(tmp_path / "Demo", "Demo")
    run = proj.current_run()
    d = run.dir
    stem = run.stem

    def write(rel, data="x"):
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)
        return p

    # Chart
    for suffix in (".ti1", ".ti2", ".cht", ".cie", ".ps", ".pdf",
                   ".channels.json", ".strips.json"):
        write(f"{stem}{suffix}")
    write(f"{stem}_01.tif"); write(f"{stem}_02.tif")
    write(f"chart/{stem}.ti2"); write(f"chart/meta.json")
    # Measurement
    write(f"{stem}.ti3", "measurement" * 10)
    write("reads/read1.ti3")
    # Profile
    write(f"{stem}.icc"); write("merged.ti3"); write("merged.icc")
    write("calibrated.icc"); write("gamut.x3d.html"); write("x3dom.css")
    # Refinement seed
    write("preconditioning.ti3"); write("preconditioning.icc")
    # Reports — only the three kinds Knut named
    write(f"reports/Quality_Check_1_{stem}.txt")
    write(f"reports/Refine_Strips_{stem}.txt")
    write("reports/report_2026.json")
    write("reports/scratch_notes.txt")          # NOT one of his three
    # Exports
    write(f"exports/{stem}-colours.txt")
    # Excluded outright
    write("verifications/Demo-verify.ti2")
    write("verifications/2026-01-01/x.ti3")
    write("old/T1/something.ti3")
    write("cache/working.tif")
    return proj


def _names(run):
    return {str(p.relative_to(run.dir))
            for p in run.dir.rglob("*") if p.is_file()}


# ---- what comes across ---------------------------------------------------
def test_the_chart_measurement_and_profile_are_copied(project):
    src = project.current_run()
    stem = src.stem
    new = project.duplicate_run(src)
    got = _names(new)
    for rel in (f"{stem}.ti1", f"{stem}.ti2", f"{stem}.cht", f"{stem}.cie",
                f"{stem}.ps", f"{stem}.pdf", f"{stem}.channels.json",
                f"{stem}.strips.json", f"{stem}_01.tif", f"{stem}_02.tif",
                f"{stem}.ti3", "reads/read1.ti3", f"{stem}.icc",
                "merged.ti3", "merged.icc", "calibrated.icc",
                "gamut.x3d.html", "x3dom.css",
                "preconditioning.ti3", "preconditioning.icc",
                f"exports/{stem}-colours.txt"):
        assert rel in got, rel


def test_the_stored_chart_folder_comes_too(project):
    src = project.current_run()
    new = project.duplicate_run(src)
    got = _names(new)
    assert f"chart/{src.stem}.ti2" in got
    assert "chart/meta.json" in got, \
        "chart/ is copied whole — its meta.json describes the stored chart, " \
        "not the run"


def test_only_the_three_named_report_kinds_come(project):
    src = project.current_run()
    new = project.duplicate_run(src)
    got = _names(new)
    assert f"reports/Quality_Check_1_{src.stem}.txt" in got
    assert f"reports/Refine_Strips_{src.stem}.txt" in got
    assert "reports/report_2026.json" in got
    assert "reports/scratch_notes.txt" not in got


@pytest.mark.parametrize("excluded", [
    "verifications/Demo-verify.ti2",
    "verifications/2026-01-01/x.ti3",
    "old/T1/something.ti3",
    "cache/working.tif",
])
def test_the_excluded_folders_stay_behind(project, excluded):
    """verifications/ especially: use case 3 is "carry on with a DIFFERENT
    verification chart", so bringing the old one would defeat the purpose."""
    src = project.current_run()
    new = project.duplicate_run(src)
    assert excluded not in _names(new)


# ---- identity ------------------------------------------------------------
def test_the_new_run_does_not_claim_to_be_the_old_one(project):
    """meta.json is written fresh. Copied verbatim it would carry the source's
    run_id, and the manifest and the folder would disagree."""
    src = project.current_run()
    new = project.duplicate_run(src)
    meta = new.load_meta()
    assert meta.run_id == new.id != src.id
    assert meta.duplicated_from == src.id
    assert "meta.json" not in {p.name for p in new.dir.glob("meta.json")
                               if p.read_text() == (src.dir / "meta.json").read_text()}


def test_the_new_run_becomes_current(project):
    src = project.current_run()
    new = project.duplicate_run(src)
    assert project.current_run().id == new.id
    assert new.id in project._manifest.runs


def test_the_source_run_is_untouched(project):
    """Nothing is moved and nothing is overwritten — that is the whole promise
    the confirmation window makes."""
    src = project.current_run()
    before = _names(src)
    project.duplicate_run(src)
    assert _names(src) == before


def test_the_instrument_and_paper_travel_with_the_chart(project):
    src = project.current_run()
    m = src.load_meta(); m.instrument = "CM"; m.paper = "A4"; src.save_meta(m)
    new = project.duplicate_run(src)
    assert (new.load_meta().instrument, new.load_meta().paper) == ("CM", "A4")


# ---- the plan the confirmation window is built from ----------------------
def test_the_plan_lists_only_groups_that_exist(project, tmp_path):
    """A row reading "Profile — 0 files" would suggest something is missing
    rather than simply absent."""
    proj2 = Project.create(tmp_path / "Bare", "Bare")
    run = proj2.current_run()
    (run.dir / f"{run.stem}.ti1").write_text("x")
    groups = [g for g, _f, _s in proj2.duplicate_run_plan(run)]
    assert groups == ["chart"]


def test_the_plan_counts_and_sizes_what_it_names(project):
    src = project.current_run()
    plan = dict((g, (f, s)) for g, f, s in project.duplicate_run_plan(src))
    files, size = plan["measurement"]
    assert {p.name for p in files} == {f"{src.stem}.ti3", "read1.ti3"}
    assert size == sum(p.stat().st_size for p in files) > 0


def test_the_plan_matches_what_is_actually_copied(project):
    """The window would otherwise be able to promise one thing and do another."""
    src = project.current_run()
    planned = {p.relative_to(src.dir)
               for _g, files, _s in project.duplicate_run_plan(src)
               for p in files}
    new = project.duplicate_run(src)
    copied = {p.relative_to(new.dir) for p in new.dir.rglob("*") if p.is_file()}
    assert copied - {__import__("pathlib").Path("meta.json")} == planned


def test_a_file_listed_twice_is_copied_once(project):
    """`{stem}.tif` and `{stem}_*.tif` can both match on a one-page chart."""
    src = project.current_run()
    (src.dir / f"{src.stem}.tif").write_text("single page")
    files = [p for _g, fs, _s in project.duplicate_run_plan(src) for p in fs]
    assert len(files) == len(set(files))
