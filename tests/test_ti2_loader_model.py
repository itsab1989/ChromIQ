"""#130 unified load model — the bar-aware `.ti2` load dialogs route an external
chart into the right place per Profile-run / Run-type. The pop-ups are stubbed
(offscreen widget-drive of the modal choice isn't practical); the file outcomes
and bar side-effects are asserted."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                       # noqa: E402

import ui.ti2_loader as L                                      # noqa: E402
from core.file_manager import Project                          # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,       # noqa: E402
                                     RUN_TYPE_VERIFICATION, MeasurementTarget)
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FM:
    def __init__(self, root: Path):
        self._root = root
        self._target_name = root.name

    def working_dir(self) -> Path:
        return self._root

    def project(self) -> Project:
        return Project.load(self._root)

    def set_target_name(self, name):        # used by A2b "open"
        self._target_name = name


def _settings(tmp_path):
    class _S:
        def get(self, k, d=None):
            return str(tmp_path / "work") if k == "custom_output_path" else d
    return _S()


def _loose(folder: Path, stem="ext", ti3=False, icc=False):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}.ti1").write_text("ti1")
    ti2 = folder / f"{stem}.ti2"; ti2.write_text("ti2")
    (folder / f"{stem}_01.tif").write_text("t")
    if ti3:
        (folder / f"{stem}.ti3").write_text("m")
    if icc:
        (folder / f"{stem}.icc").write_text("i")
    return ti2


def _ctl_for(project_root):
    return MeasurementTargetController(_FM(project_root))


def test_loose_new_run_profiling(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_PROFILING); ctl.set_profile_run("")     # New run
    ti2 = _loose(tmp_path / "ext", ti3=True, icc=True)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "import")
    out, tiffs = L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    r = Project.load(proj.root).run("run2")
    assert out == r.chart_ti2 and r.measurement_ti3.exists() and r.profile_icc.exists()
    assert ctl.target.profile_run == "run2"          # bar points at the new run


def test_loose_new_run_verification_chart_only(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_VERIFICATION); ctl.set_profile_run("")
    ti2 = _loose(tmp_path / "ext", ti3=True, icc=True)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "import")
    out, _ = L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    r = Project.load(proj.root).run("run2")
    assert out == r.verify_chart_ti2 and r.verify_chart_ti2.exists()
    assert not r.profile_icc.exists()                # icc/ti3 ignored


def test_loose_overwrite_replace_archives(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("old"); run.measurement_ti3.write_text("m")
    run.profile_icc.write_text("icc")
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_PROFILING); ctl.set_profile_run("run1")
    ti2 = _loose(tmp_path / "ext", ti3=True, icc=True)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "replace")
    out, _ = L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    r = Project.load(proj.root).run("run1")
    assert r.old_dir.exists() and out == r.chart_ti2 and r.chart_ti2.read_text() == "ti2"


def test_loose_overwrite_new_run_instead(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("old")
    ctl = _ctl_for(proj.root)
    ctl.set_run_type(RUN_TYPE_PROFILING); ctl.set_profile_run("run1")
    ti2 = _loose(tmp_path / "ext")
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "new")
    out, _ = L.resolve_ti2(None, ti2, _settings(tmp_path), ctl)
    assert out == Project.load(proj.root).run("run2").chart_ti2   # new run, run1 untouched
    assert (work / "P" / "runs" / "run1" / "P.ti2").read_text() == "old"


def test_inside_current_continue_sets_bar(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("c"); (run.dir / "P_01.tif").write_text("t")
    ctl = _ctl_for(proj.root)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "continue")
    out, _ = L.resolve_ti2(None, run.chart_ti2, _settings(tmp_path), ctl)
    assert out == run.chart_ti2                       # used in place, no copy
    assert ctl.target.profile_run == "run1" and not ctl.target.is_verification()


def test_cancel_returns_none(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    ctl = _ctl_for(proj.root); ctl.set_profile_run("")
    ti2 = _loose(tmp_path / "ext")
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: None)    # Cancel
    assert L.resolve_ti2(None, ti2, _settings(tmp_path), ctl) is None


def test_full_project_copy_whole(qapp, tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir(parents=True)
    proj = Project.create(work / "P", "P"); proj.current_run().ensure_dir()
    ctl = _ctl_for(proj.root)
    # an external complete project Q
    q = Project.create(tmp_path / "ext" / "Q", "Q"); qr = q.current_run(); qr.ensure_dir()
    qr.chart_ti2.write_text("qc"); (qr.dir / "Q_01.tif").write_text("t")
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "whole")
    monkeypatch.setattr(L, "_ask_project_name", lambda *a, **k: ("Q", False))
    out, _ = L.resolve_ti2(None, qr.chart_ti2, _settings(tmp_path), ctl)
    assert (work / "Q" / "project.json").is_file()
    assert out == Project.load(work / "Q").current_run().chart_ti2
