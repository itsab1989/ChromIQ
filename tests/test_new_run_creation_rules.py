"""#130 (Knut, 2026-07-25, second specification post): with **Profile run =
"New run"** and **Run type = Profiling**, a new run folder is created — and the
bar moves to it — by each of these actions:

  Create Chart : Generate Chart · choosing a preset · Load .ti1
  Print Chart  : Load .ti2
  Measure      : Load .ti2

The Print/Measure .ti2 route is covered by test_ti2_loader_model; this file pins
the Create Chart routes, which reach it through the Profile-run alignment."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog               # noqa: E402

import ui.tabs.tab_chart as tc                                  # noqa: E402
from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager, Project              # noqa: E402
from core.measurement_target import RUN_TYPE_PROFILING          # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _no_dialogs(monkeypatch):
    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)


def _tab_on_new_run(tmp_path):
    """A loaded project P with one run, the bar on "New run" · Profiling, and
    the name field agreeing with the project — the state after opening it."""
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path)); s.set("use_chromiq_layout_engine", False)
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    tab = TabChart(ArgyllRunner(s), fm, s)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()
    ctl = MeasurementTargetController(fm)
    tab.set_target_controller(ctl)
    tab._update_name_fields()                  # the name field reflects P
    ctl.set_profile_run(""); ctl.set_run_type(RUN_TYPE_PROFILING)
    return tab, fm, ctl


def _runs(tmp_path):
    return [r.id for r in Project.load(tmp_path / "P").all_runs()]


def test_prebuilt_preset_creates_the_new_run_and_selects_it(qapp, tmp_path):
    tab, fm, ctl = _tab_on_new_run(tmp_path)
    assert _runs(tmp_path) == ["run1"] and ctl.target.profile_run == ""

    tab._apply_prebuilt_preset("__chromiq_tc300_builtin__", "P")

    assert _runs(tmp_path) == ["run1", "run2"]
    assert ctl.target.profile_run == "run2", "the bar moves to the new run"
    assert Project.load(tmp_path / "P").run("run2").chart_ti2.exists()
    assert not Project.load(tmp_path / "P").run("run1").chart_ti2.exists()


def test_ti1_preset_creates_the_new_run(qapp, tmp_path, monkeypatch):
    tab, fm, ctl = _tab_on_new_run(tmp_path)
    captured = {}
    monkeypatch.setattr(
        tab._creator, "load_ti1_and_generate_preview",
        lambda *a, **k: captured.__setitem__(
            "run", Project.load(tmp_path / "P").current_run().id))
    ti1 = tmp_path / "seed.ti1"; ti1.write_text("CTI1\n")

    tab._generate_from_ti1(ti1)

    assert _runs(tmp_path) == ["run1", "run2"]
    assert captured.get("run") == "run2"
    assert ctl.target.profile_run == "run2"


def test_load_ti1_into_the_project_creates_the_new_run(qapp, tmp_path, monkeypatch):
    tab, fm, ctl = _tab_on_new_run(tmp_path)
    src = tmp_path / "patchset.ti1"; src.write_text("CTI1\n")
    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(src))
    monkeypatch.setattr(tab, "_ti1_load_destination", lambda _s: "into")
    captured = {}
    monkeypatch.setattr(
        tab._creator, "load_ti1_and_generate_preview",
        lambda *a, **k: captured.__setitem__(
            "run", Project.load(tmp_path / "P").current_run().id))

    tab._on_load_ti1()

    assert _runs(tmp_path) == ["run1", "run2"]
    assert captured.get("run") == "run2"
    assert ctl.target.profile_run == "run2"


def test_a_build_under_a_different_name_starts_its_own_project(qapp, tmp_path):
    """The flip side, and the reason the check compares folders: a build under a
    NEW name is a different project with its own run 1 — the loaded project must
    not gain a run from it."""
    tab, fm, ctl = _tab_on_new_run(tmp_path)
    tab._manual_target_name_edit.setText("Something Else")

    tab._apply_prebuilt_preset("__chromiq_tc300_builtin__", "Something Else")

    assert _runs(tmp_path) == ["run1"], "the loaded project is untouched"
    assert (tmp_path / "Something-Else" / "runs" / "run1").exists()
