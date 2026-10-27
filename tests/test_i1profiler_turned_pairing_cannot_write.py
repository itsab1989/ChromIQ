"""A pairing copy that cannot be written ends in the door's friendly "could not
file" window (beta; review 4.3.17 r2, NIT-4).

`TurnedPairing.first` copies the measurement before it puts it in order. That
copy is a write, and an OSError from it (a full disk, an unwritable temp
folder) escaped the door, which inside a Qt slot ends the app. Driven through
the real door functions with the copy failing.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings

from core.file_manager import FileManager, Project, exports_subdir
from core.settings import AppSettings
from workflow import i1profiler_turned as T
from workflow.reference_convert import cxf_measurement_to_ti3

from tests.test_i1profiler_turned_export import _chart
from tests.test_i1profiler_turned_import import _mxf_from_txf


@pytest.fixture
def scene(qapp, tmp_path, monkeypatch):
    import ui.measurement_filing as mf
    import ui.ti2_loader as L
    loose = tmp_path / "loose"
    ti2 = _chart(loose, "L", 350)
    T.write_turned_export(ti2, exports_subdir(loose), "L")
    mxf = _mxf_from_txf(T.TurnedFiles(exports_subdir(loose), "L").txf(
        "i1Pro 3"), tmp_path / "t.mxf")
    meas = cxf_measurement_to_ti3(mxf, loose / "L.ti3")
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    work = tmp_path / "work"
    work.mkdir()
    s.set("custom_output_path", str(work))
    said = {"info": [], "refused": []}

    class _Info:
        def __init__(self, title, *a, **kw):
            said["info"].append(title)

        def exec(self):
            return 0
    monkeypatch.setattr(mf, "InfoDialog", _Info)
    monkeypatch.setattr(mf, "refuse_it_does_not_belong",
                        lambda p, r: said["refused"].append(r))
    monkeypatch.setattr(mf, "ask_to_make_a_new_run", lambda *a: True)
    monkeypatch.setattr(mf, "only_you_can_confirm_the_chart",
                        lambda *a: True)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "continue")
    real = shutil.copy2

    def copy2(src, dst, *a, **k):
        if "chromiq-turned-" in str(dst):
            raise OSError(28, "No space left on device")
        return real(src, dst, *a, **k)
    monkeypatch.setattr(shutil, "copy2", copy2)
    return mf, s, work, ti2, meas, said


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_the_new_project_door_says_it_could_not_file(scene):
    from PyQt6.QtWidgets import QWidget
    mf, s, work, _ti2, meas, said = scene
    h = _sha(meas)
    assert mf.make_new_project_and_file(QWidget(), "Fresh", meas,
                                        FileManager(s), None,
                                        on_filed=lambda p: None) is True
    assert said["info"] == ["ChromIQ could not file the measurement"]
    assert not (work / "Fresh").exists()
    assert _sha(meas) == h


@pytest.mark.parametrize("occupied", [False, True],
                         ids=["empty-run", "run-holds-one"])
def test_the_existing_project_door_says_it_could_not_file(scene, occupied):
    from PyQt6.QtWidgets import QWidget
    mf, s, work, ti2, meas, said = scene
    proj = Project.create(work / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    for f in ti2.parent.iterdir():
        if f.is_file() and f.suffix != ".ti3":
            shutil.copy2(f, run.dir / ("P" + f.name[1:]))
    T.write_turned_export(run.chart_ti2, run.exports_dir, "P")
    if occupied:
        shutil.copy2(meas, run.measurement_ti3)
    fm = FileManager(s)
    fm.set_target_name("P")
    h = _sha(meas)
    filed = []
    assert mf.file_into_project(QWidget(), "P", meas, fm, None,
                                on_filed=filed.append) is True
    assert said["info"] == ["ChromIQ could not file the measurement"]
    assert filed == []
    assert sorted(p.name for p in (work / "P" / "runs").iterdir()) == ["run1"]
    assert Project.load(work / "P").current_run().id == "run1"
    assert _sha(meas) == h
