"""#130 (Knut): projects may be organised in SUB-folders of the ChromIQ folder.
The app must recognise a nested project as one it manages (no "copy it in"
pop-up) and open it in place, resolving all paths at its real location."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

import ui.tabs.tab_chart as tc                                 # noqa: E402
import ui.ti2_loader as L                                      # noqa: E402
from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager, Project              # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _no_dialogs(monkeypatch):
    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)
    monkeypatch.setattr(tc, "InfoDialog",
                        type("_I", (), {"__init__": lambda self, *a, **k: None,
                                        "exec": lambda self: 0}))
    for n in ("warning", "critical", "information", "question"):
        monkeypatch.setattr(QMessageBox, n, staticmethod(lambda *a, **k: 0), raising=False)


def _fm(tmp_path):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir()
    s.set("custom_output_path", str(root))
    return FileManager(s), root, s


def test_open_project_at_resolves_nested(qapp, tmp_path):
    fm, root, s = _fm(tmp_path)
    nested = root / "companyA" / "2026" / "P"
    Project.create(nested, "P")
    fm.open_project_at(nested)
    assert fm.working_dir() == nested            # resolves at the real location
    assert fm.get_target_name() == "P"
    assert fm.project().root == nested
    # A fresh direct-name project drops the override.
    fm.set_target_name("Q")
    assert fm.working_dir() == root / "Q"
    assert fm.project_root_override() is None


def test_load_profile_nested_opens_in_place_no_copy(qapp, tmp_path, monkeypatch):
    fm, root, s = _fm(tmp_path)
    tab = TabChart(ArgyllRunner(s), fm, s)
    tab.set_target_controller(MeasurementTargetController(fm))
    nested = root / "sub" / "working-folder" / "Test-Profiling-P"
    Project.create(nested, "Test-Profiling-P").current_run().ensure_dir()

    monkeypatch.setattr(tc, "open_file_dialog",
                        lambda *a, **k: str(nested / "project.json"))
    seen = {"choice": 0}
    monkeypatch.setattr(L, "_choice_dialog",
                        lambda *a, **k: (seen.__setitem__("choice", seen["choice"] + 1), None)[1])

    tab._load_existing_profile()

    assert seen["choice"] == 0                   # NO copy-in pop-up for a nested project
    assert fm.get_target_name() == "Test-Profiling-P"
    assert fm.working_dir() == nested            # opened in place, at its real folder
    # No duplicate was created directly under the ChromIQ folder.
    assert not (root / "Test-Profiling-P").exists()


def test_truly_external_project_still_offers_copy_in(qapp, tmp_path, monkeypatch):
    fm, root, s = _fm(tmp_path)
    tab = TabChart(ArgyllRunner(s), fm, s)
    tab.set_target_controller(MeasurementTargetController(fm))
    outside = tmp_path / "elsewhere" / "Q"
    Project.create(outside, "Q").current_run().ensure_dir()

    monkeypatch.setattr(tc, "open_file_dialog",
                        lambda *a, **k: str(outside / "project.json"))
    seen = {"choice": 0}
    monkeypatch.setattr(L, "_choice_dialog",
                        lambda *a, **k: (seen.__setitem__("choice", seen["choice"] + 1), "copy")[1])
    monkeypatch.setattr(L, "_ask_project_name", lambda *a, **k: ("Q", False))

    tab._load_existing_profile()

    assert seen["choice"] == 1                    # copy-in offered (truly external)
    assert (root / "Q" / "project.json").is_file()  # copied in


def test_project_root_for_finds_nested_project(qapp, tmp_path):
    """#130: _project_root_for recognises a project nested at any depth."""
    from ui.ti2_loader import _project_root_for
    root = tmp_path / "ChromIQ"; root.mkdir()
    proj = root / "companyA" / "2026" / "P"
    Project.create(proj, "P")
    run = proj / "runs" / "run1"; run.mkdir(parents=True, exist_ok=True)
    ti2 = run / "P.ti2"; ti2.write_text("CTI2\n")
    assert _project_root_for(ti2, root) == proj
    # A loose chart not inside any project → None.
    loose = root / "loose" / "x.ti2"; loose.parent.mkdir(parents=True); loose.write_text("x")
    assert _project_root_for(loose, root) is None
    # A file outside the ChromIQ folder → None.
    assert _project_root_for(tmp_path / "elsewhere" / "y.ti2", root) is None


def test_resolve_ti2_opens_nested_other_project_in_place(qapp, tmp_path, monkeypatch):
    """Loading a .ti2 from a nested project (not the current one) offers 'Open'
    and switches to it AT ITS REAL nested location — not copy-whole."""
    from core.measurement_target import RUN_TYPE_PROFILING
    from ui.ti2_loader import resolve_ti2
    import ui.ti2_loader as L2
    fm, root, s = _fm(tmp_path)
    # Current project A (direct child).
    Project.create(root / "A", "A").current_run().ensure_dir()
    fm.set_target_name("A")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    # A DIFFERENT project P nested deep, with a real chart.
    pnest = root / "sub" / "deep" / "P"
    pnest_proj = Project.create(pnest, "P"); run = pnest_proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("chart"); (run.dir / "P_01.tif").write_text("t")

    monkeypatch.setattr(L2, "_choice_dialog", lambda *a, **k: "open")
    out = resolve_ti2(None, run.chart_ti2, s, ctl)

    assert out is not None and out[0] == run.chart_ti2      # used in place
    assert fm.get_target_name() == "P"
    assert fm.working_dir() == pnest                        # opened at the nested folder
    assert not (root / "P").exists()                        # no copy made
