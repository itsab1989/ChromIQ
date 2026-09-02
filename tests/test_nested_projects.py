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
    ti2 = run / "P.ti2"; ti2.write_text("CTI2\n", encoding="utf-8")
    assert _project_root_for(ti2, root) == proj
    # A loose chart not inside any project → None.
    loose = root / "loose" / "x.ti2"; loose.parent.mkdir(parents=True); loose.write_text("x", encoding="utf-8")
    assert _project_root_for(loose, root) is None
    # A file outside the ChromIQ folder → None.
    assert _project_root_for(tmp_path / "elsewhere" / "y.ti2", root) is None


def test_reapplying_the_same_name_keeps_a_nested_project(qapp, tmp_path):
    """#130 (Knut K2): re-applying the UNCHANGED name — which the Create Chart
    name field, every preset and Generate all do — must not relocate a nested
    project to <ChromIQ>/<name> and create an empty duplicate there."""
    fm, root, s = _fm(tmp_path)
    nested = root / "load-test-data" / "working-folder" / "Test-Profiling-P"
    Project.create(nested, "Test-Profiling-P").current_run().ensure_dir()
    fm.open_project_at(nested)

    fm.set_target_name("Test-Profiling-P")       # what the name field re-applies

    assert fm.working_dir() == nested
    assert fm.project_root_override() == nested
    assert fm.project().root == nested           # a Generate would build here
    assert not (root / "Test-Profiling-P").exists()   # no phantom duplicate


def test_a_different_name_still_creates_a_direct_child_project(qapp, tmp_path):
    """The flip side: typing a genuinely different name is a NEW project, which
    always lives directly under the ChromIQ folder."""
    fm, root, s = _fm(tmp_path)
    nested = root / "sub" / "P"
    Project.create(nested, "P").current_run().ensure_dir()
    fm.open_project_at(nested)

    fm.set_target_name("P-take-two")

    assert fm.project_root_override() is None
    assert fm.working_dir() == root / "P-take-two"
    assert nested.exists()                        # the nested original is untouched


def test_start_new_project_overrides_a_nested_project_of_the_same_name(qapp, tmp_path):
    """Keeping the nested location for an unchanged name must not swallow a
    DELIBERATE "start a new project" that happens to reuse that name."""
    fm, root, s = _fm(tmp_path)
    nested = root / "sub" / "P"
    Project.create(nested, "P").current_run().ensure_dir()
    fm.open_project_at(nested)

    fm.start_new_project("P")

    assert fm.project_root_override() is None
    assert fm.working_dir() == root / "P"


def test_import_into_nested_project_after_name_reapply(qapp, tmp_path, monkeypatch):
    """#130 (Knut K4/K5): with a nested project open, a Print/Measure chart
    import must land in THAT project — not in a phantom copy at the ChromIQ
    root. This is the end-to-end shape of Knut's report ("the new .ti2 was not
    put into verifications/ or anywhere else")."""
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from ui.ti2_loader import resolve_ti2
    import ui.ti2_loader as L2
    fm, root, s = _fm(tmp_path)
    nested = root / "customers" / "2026" / "P"
    proj = Project.create(nested, "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("PROFILING-CHART", encoding="utf-8")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("OLD-VERIFY", encoding="utf-8")
    fm.open_project_at(nested)
    fm.set_target_name("P")                       # the relocation trigger

    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ext = tmp_path / "elsewhere" / "loose"; ext.mkdir(parents=True)
    src = ext / "loose.ti2"; src.write_text("NEW-VERIFY", encoding="utf-8")

    monkeypatch.setattr(L2, "_choice_dialog", lambda *a, **k: "replace")
    out = resolve_ti2(None, src, s, ctl)

    assert out is not None
    r = Project.load(nested).run("run1")
    assert r.verify_chart_ti2.read_text(encoding="utf-8") == "NEW-VERIFY"   # landed in the real project
    assert r.chart_ti2.read_text(encoding="utf-8") == "PROFILING-CHART"     # profiling side untouched
    assert r.verifications_old_dir.exists()                 # displaced files archived
    assert not (root / "P").exists()                        # no phantom project


def test_builds_into_project_compares_folders_not_names(qapp, tmp_path):
    """A nested project has the same NAME as the <ChromIQ>/<name> path a fresh
    project would use, so the in-project-build check must compare folders."""
    from types import SimpleNamespace
    fm, root, s = _fm(tmp_path)
    nested = root / "sub" / "P"
    proj = Project.create(nested, "P")
    fm.open_project_at(nested)
    tab = SimpleNamespace(_file_mgr=fm)

    assert TabChart._builds_into_project(tab, proj) is True
    assert TabChart._builds_into_project(tab, None) is False
    other = Project.create(root / "Q", "Q")
    assert TabChart._builds_into_project(tab, other) is False
    # Same name, different folder → not the same project.
    twin = Project.create(tmp_path / "elsewhere" / "P", "P")
    assert TabChart._builds_into_project(tab, twin) is False


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
    run.chart_ti2.write_text("chart", encoding="utf-8"); (run.dir / "P_01.tif").write_text("t", encoding="utf-8")

    monkeypatch.setattr(L2, "_choice_dialog", lambda *a, **k: "open")
    out = resolve_ti2(None, run.chart_ti2, s, ctl)

    assert out is not None and out[0] == run.chart_ti2      # used in place
    assert fm.get_target_name() == "P"
    assert fm.working_dir() == pnest                        # opened at the nested folder
    assert not (root / "P").exists()                        # no copy made
