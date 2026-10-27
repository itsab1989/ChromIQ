"""Restore Used Chart files the replaced chart's turned i1Profiler export where
that chart goes (beta; review 4.3.17 r4, NIT-2, NIT-3, NIT-4).

* NIT-2: a calibration's replaced chart is archived in
  ``cal/old/<date>/chart/``, and ``Calibration.reset``'s rule is that
  ``cal/exports/`` goes wherever the chart goes, so its turned files belong
  in ``cal/old/<date>/chart/exports/``, not at the top of the dated folder.
* NIT-3: two restores in the same second share one dated folder, and
  ``shutil.move`` onto an existing name replaced the first set.
* NIT-4: the turned files the TI2 layout editor writes beside the chart were
  left there as a stale second set beside the restored one.
"""
from __future__ import annotations

import datetime as _dt
import shutil
from pathlib import Path

from core.file_manager import Project, exports_subdir
from workflow import i1profiler_turned as T
from workflow.chart_slot import slot_for_calibration, slot_for_run
from workflow.verify_chart_snapshot import restore_slot, snapshot_slot

from tests.test_i1profiler_turned_export import _chart


def _put_chart(src: Path, d: Path, stem: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for f in src.parent.iterdir():
        if f.is_file():
            shutil.copy2(f, d / (stem + f.name[len(src.stem):]))
    return d / f"{stem}.ti2"


def _change(ti2: Path, tag: str) -> None:
    t = ti2.read_text(encoding="utf-8")
    ti2.write_text(t.replace('DESCRIPTOR "', f'DESCRIPTOR "{tag} ', 1),
                   encoding="utf-8")


def _turned(root: Path) -> list:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.is_file() and "turned" in p.name)


def _names(files: T.TurnedFiles) -> list:
    return sorted(p.name for p in files.all())


def test_a_calibrations_replaced_turned_files_go_into_chart_exports(tmp_path):
    src = _chart(tmp_path / "src", "Src", 350)
    proj = Project.create(tmp_path / "P", "P")
    cal = proj.calibration
    ti2 = _put_chart(src, cal.dir, cal.stem)
    T.write_turned_export(ti2, exports_subdir(cal.dir), cal.stem)
    slot = slot_for_calibration(cal)
    snapshot_slot(slot)
    _change(ti2, "B")
    T.write_turned_export(ti2, exports_subdir(cal.dir), cal.stem)
    b_order = T.TurnedFiles(exports_subdir(cal.dir), cal.stem).order.read_bytes()
    res = restore_slot(slot)
    assert res.ok and res.archive is not None
    # the replaced chart is in <archive>/chart/, and its turned files with it
    assert (res.archive / "chart" / f"{cal.stem}.ti2").is_file()
    kept = T.TurnedFiles(res.archive / "chart" / "exports", cal.stem)
    assert kept.order.read_bytes() == b_order
    assert all(p.is_file() for p in kept.all())
    assert not (res.archive / "exports").exists()
    assert T.turned_order_for(ti2) is not None


def test_two_restores_in_the_same_second_keep_both_archived_sets(
        tmp_path, monkeypatch):
    import core.file_manager as fm

    class _Frozen(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 27, 12, 0, 0)

    monkeypatch.setattr(fm, "datetime", _Frozen)
    src = _chart(tmp_path / "src", "Src", 350)
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    ti2 = _put_chart(src, run.dir, run.stem)
    T.write_turned_export(ti2, run.exports_dir, run.stem)
    slot = slot_for_run(run)
    snapshot_slot(slot)
    orders, archives = [], []
    for tag in ("B1", "B2"):
        _change(ti2, tag)
        T.write_turned_export(ti2, run.exports_dir, run.stem)
        orders.append(run.i1profiler_turned.order.read_bytes())
        res = restore_slot(slot)
        assert res.ok
        archives.append(res.archive)
    assert archives[0] == archives[1]          # one dated folder, same second
    keep = archives[0] / "exports"
    assert (keep / f"{run.stem}-i1profiler-turned.json").read_bytes() == orders[0]
    assert (keep / f"{run.stem}-i1profiler-turned_2.json").read_bytes() == orders[1]
    assert len([p for p in keep.iterdir() if "turned" in p.name]) == 8


def test_turned_files_beside_the_chart_are_archived_too(tmp_path):
    src = _chart(tmp_path / "src", "Src", 350)
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    ti2 = _put_chart(src, run.dir, run.stem)
    T.write_turned_export(ti2, run.dir, run.stem)       # the TI2 layout editor
    slot = slot_for_run(run)
    snapshot_slot(slot)
    _change(ti2, "B")
    T.remove_stale(run.dir, run.stem)
    T.write_turned_export(ti2, run.dir, run.stem)
    b_order = T.TurnedFiles(run.dir, run.stem).order.read_bytes()
    res = restore_slot(slot)
    assert res.ok and res.archive is not None
    # one set, in exports/, and none left beside the restored chart
    assert not [p for p in run.dir.iterdir() if "turned" in p.name]
    assert sorted(p.name for p in run.exports_dir.iterdir()
                  if "turned" in p.name) == _names(run.i1profiler_turned)
    order = T.turned_order_for(ti2)
    assert order is not None and order.path.parent == run.exports_dir
    # the replaced set sits beside the archived chart
    kept = T.TurnedFiles(res.archive, run.stem)
    assert kept.order.read_bytes() == b_order
    assert all(p.is_file() for p in kept.all())
    assert (res.archive / f"{run.stem}.ti2").is_file()


def test_both_places_are_archived_when_both_hold_a_set(tmp_path):
    src = _chart(tmp_path / "src", "Src", 350)
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    ti2 = _put_chart(src, run.dir, run.stem)
    T.write_turned_export(ti2, run.exports_dir, run.stem)
    slot = slot_for_run(run)
    snapshot_slot(slot)
    _change(ti2, "B")
    T.write_turned_export(ti2, run.exports_dir, run.stem)
    T.write_turned_export(ti2, run.dir, run.stem)
    res = restore_slot(slot)
    assert res.ok
    assert _turned(run.dir / "old") == sorted(
        [f"{res.archive.name}/{n}" for n in _names(T.TurnedFiles(
            res.archive, run.stem))]
        + [f"{res.archive.name}/exports/{n}" for n in _names(T.TurnedFiles(
            res.archive, run.stem))])
    assert [p for p in _turned(run.dir)
            if not p.startswith(("old/", "chart/"))] == [
        f"exports/{n}" for n in _names(run.i1profiler_turned)]
