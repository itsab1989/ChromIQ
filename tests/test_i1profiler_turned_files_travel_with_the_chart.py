"""The turned i1Profiler export travels with its chart (beta; review 4.3.17
r2, NIT-1).

`duplicate_run(run, ("chart",))` (the import doors' "a new run") and
`ti2_loader._copy_files` (a new project from a chart folder) took the chart and
left its turned export behind, so a LATER turned measurement of that very
sheet could not be paired in the copy. The files are bound to the chart by
its SHA-256, so they travel only with a byte-for-byte copy of it.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from core.file_manager import Project, exports_subdir
from workflow import i1profiler_turned as T
from workflow.measurement_import import assess
from workflow.reference_convert import cxf_measurement_to_ti3

from tests.test_i1profiler_turned_export import _chart
from tests.test_i1profiler_turned_import import _mxf_from_txf


@pytest.fixture(scope="module")
def src(tmp_path_factory):
    d = tmp_path_factory.mktemp("travel")
    return _chart(d / "src", "Src", 350)


def _place(src_ti2: Path, folder: Path, stem: str, *, turned: bool,
           beside: bool = False) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for f in src_ti2.parent.iterdir():
        if f.is_file() and f.name.startswith(src_ti2.stem):
            shutil.copy2(f, folder / (stem + f.name[len(src_ti2.stem):]))
    ti2 = folder / f"{stem}.ti2"
    if turned:
        T.write_turned_export(ti2, folder if beside else exports_subdir(folder),
                              stem)
    return ti2


def _pairs(chart: Path, files: T.TurnedFiles, tmp: Path) -> None:
    mxf = _mxf_from_txf(files.txf("i1Pro 3"), tmp / "later.mxf")
    v = assess(cxf_measurement_to_ti3(mxf, tmp / "later.ti3"), chart)
    assert v.ok and v.turned_order, v.reason


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()
            and p.name not in ("meta.json", "project.json", "README.txt")}


@pytest.mark.parametrize("beside", [False, True],
                         ids=["in-exports", "beside-the-chart"])
def test_a_duplicated_run_still_pairs_a_later_turned_mxf(
        tmp_path, src, beside):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    _place(src, run.dir, run.stem, turned=True, beside=beside)
    dup = proj.duplicate_run(run, ("chart",))
    order = T.turned_order_for(dup.chart_ti2)
    assert order is not None
    # Wherever it sat in the source, the copy holds it in exports/, as
    # `_copy_files` and Create Chart place it (review 4.3.17 r3, SF-2).
    assert order.path.parent == dup.exports_dir
    assert sorted(p.name for p in dup.exports_dir.iterdir()) == sorted(
        p.name for p in dup.i1profiler_turned.all())
    assert not [p for p in dup.dir.iterdir() if "turned" in p.name]
    assert _sha(dup.chart_ti2) == json.loads(
        order.path.read_text(encoding="utf-8"))["chart_sha256"]
    _pairs(dup.chart_ti2, T.TurnedFiles(order.path.parent, dup.stem), tmp_path)


def test_a_whole_run_duplicate_copies_each_turned_file_once(tmp_path, src):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    _place(src, run.dir, run.stem, turned=True)
    plan = proj.duplicate_run_plan(run)
    every = [p for _g, files, _s in plan for p in files]
    assert len(every) == len(set(every))
    chart = next(files for g, files, _s in plan if g == "chart")
    assert sum("turned" in p.name for p in chart) == 4


def test_a_new_project_from_a_chart_folder_holds_the_turned_files_and_pairs(
        tmp_path, src):
    from ui.ti2_loader import _copy_files
    loose = tmp_path / "loose"
    ti2 = _place(src, loose, "Loose", turned=True)
    new_ti2, _tiffs = _copy_files(ti2, ti2.with_suffix(".ti1"), [],
                                  tmp_path / "work", "Fresh")
    run = Project.load(tmp_path / "work" / "Fresh").current_run()
    assert sorted(p.name for p in run.exports_dir.iterdir()) == sorted(
        p.name for p in run.i1profiler_turned.all())
    assert T.turned_order_for(new_ti2) is not None
    _pairs(new_ti2, run.i1profiler_turned, tmp_path)


def test_an_order_that_names_another_chart_is_not_carried(tmp_path, src):
    from ui.ti2_loader import _copy_files
    loose = tmp_path / "loose"
    ti2 = _place(src, loose, "Loose", turned=True)
    ti2.write_text(ti2.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    new_ti2, _ = _copy_files(ti2, ti2.with_suffix(".ti1"), [],
                             tmp_path / "work", "Fresh")
    assert not (new_ti2.parent / "exports").exists()


def test_a_copy_that_is_not_the_same_chart_gets_no_order(tmp_path, src):
    loose = tmp_path / "loose"
    ti2 = _place(src, loose, "Loose", turned=True)
    other = tmp_path / "other" / "O.ti2"
    other.parent.mkdir()
    other.write_text(ti2.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert T.carry_turned_export(ti2, other, other.parent / "exports",
                                 "O") == []
    assert not (other.parent / "exports").exists()


def test_without_turned_files_duplicate_and_copy_are_as_before(tmp_path, src):
    """4.3.16: the same plan, the same files, nothing extra."""
    from ui.ti2_loader import _copy_files
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    _place(src, run.dir, run.stem, turned=False)
    (run.exports_dir).mkdir()
    (run.exports_dir / "P-colours.txt").write_text("x", encoding="utf-8")
    plan = proj.duplicate_run_plan(run, ("chart",))
    assert [g for g, _f, _s in plan] == ["chart"]
    names = sorted(p.name for p in plan[0][1])
    assert names == sorted(p.name for p in run.dir.iterdir()
                           if p.is_file() and p.name != "meta.json")
    dup = proj.duplicate_run(run, ("chart",))
    assert not dup.exports_dir.exists()
    whole = proj.duplicate_run_plan(run)
    assert [g for g, _f, _s in whole] == ["chart", "exports"]

    loose = tmp_path / "loose"
    ti2 = _place(src, loose, "Loose", turned=False)
    new_ti2, _ = _copy_files(ti2, ti2.with_suffix(".ti1"), [],
                             tmp_path / "work", "Fresh")
    got = _tree(new_ti2.parent)
    assert sorted(got) == sorted(["Fresh.ti2", "Fresh.ti1",
                                  *(["Fresh.channels.json"] if (
                                      loose / "Loose.channels.json").exists()
                                    else [])])
    assert got["Fresh.ti2"] == ti2.read_bytes()


@pytest.mark.parametrize("whole", [False, True], ids=["chart-only", "whole-run"])
@pytest.mark.parametrize("beside", [False, True],
                         ids=["in-exports", "beside-the-chart"])
def test_a_duplicate_does_not_carry_an_order_for_another_chart(
        tmp_path, src, whole, beside):
    """Review 4.3.17 r3, SF-2: `duplicate_run` copied the turned files by
    NAME, so a stale order (an earlier chart of this name) travelled into the
    copy. The same SHA-256 rule as `_copy_files` now applies: not carried by
    the chart group, and not by the whole run's exports/ either."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    _place(src, run.dir, run.stem, turned=True, beside=beside)
    run.chart_ti2.write_text(run.chart_ti2.read_text(encoding="utf-8")
                             + "\n", encoding="utf-8")
    run.ensure_exports_dir()
    (run.exports_dir / "P-colours.txt").write_text("x", encoding="utf-8")
    assert T.turned_order_for(run.chart_ti2) is None
    plan = proj.duplicate_run_plan(run, None if whole else ("chart",))
    assert not [p for _g, f, _s in plan for p in f
                if "-i1profiler-turned" in p.name]
    dup = proj.duplicate_run(run, None if whole else ("chart",))
    assert not [p for p in dup.dir.rglob("*") if "-i1profiler-turned" in p.name]
    if whole:
        assert (dup.exports_dir / "P-colours.txt").is_file()
    # The source keeps what it had.
    assert [p for p in run.dir.rglob("*") if "-i1profiler-turned" in p.name]


def test_a_whole_run_duplicate_keeps_a_users_own_file_of_a_similar_name(
        tmp_path, src):
    """Only the exact names the export writes are judged by the order; a file
    of the person's own that merely starts the same way is copied as ever."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    _place(src, run.dir, run.stem, turned=False)
    run.ensure_exports_dir()
    own = run.exports_dir / "P-i1profiler-turned-notes-of-mine.txt"
    own.write_text("mine", encoding="utf-8")
    dup = proj.duplicate_run(run)
    assert (dup.exports_dir / own.name).read_text(encoding="utf-8") == "mine"
