"""#130 (Knut bug): 'Load profile' on a project OUTSIDE the working folder must
not open silently — it offers to copy the project into the working folder (the
unified load strategy). A project already in the working folder opens directly."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

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
def _no_modal_dialogs(monkeypatch):
    """_load_existing_profile can open advisory dialogs (port note, rename
    prompt) — make every dialog non-blocking so the test exercises the flow."""
    from PyQt6.QtWidgets import QDialog, QMessageBox
    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)
    monkeypatch.setattr(tc, "InfoDialog",
                        type("_I", (), {"__init__": lambda self, *a, **k: None,
                                        "exec": lambda self: 0}))
    for name in ("warning", "critical", "information", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: 0),
                            raising=False)


def _tab(tmp_path):
    work = tmp_path / "work"; work.mkdir()
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(work))
    fm = FileManager(s)
    tab = TabChart(ArgyllRunner(s), fm, s)
    tab.set_target_controller(MeasurementTargetController(fm))
    return tab, fm, work


def test_external_project_offers_copy_in(qapp, tmp_path, monkeypatch):
    tab, fm, work = _tab(tmp_path)
    ext = tmp_path / "external" / "Full-Project-Q"
    Project.create(ext, "Full-Project-Q").current_run().ensure_dir()

    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(ext / "project.json"))
    seen = {"choice": 0}

    def _choice(*a, **k):
        seen["choice"] += 1
        return "copy"
    monkeypatch.setattr(L, "_choice_dialog", _choice)
    monkeypatch.setattr(L, "_ask_project_name", lambda *a, **k: ("Full-Project-Q", False))

    tab._load_existing_profile()

    assert seen["choice"] == 1                       # the pop-up appeared
    assert (work / "Full-Project-Q" / "project.json").is_file()   # copied in
    assert fm.get_target_name() == "Full-Project-Q"  # opened the copy


def test_internal_project_opens_without_popup(qapp, tmp_path, monkeypatch):
    tab, fm, work = _tab(tmp_path)
    Project.create(work / "Local-P", "Local-P").current_run().ensure_dir()

    monkeypatch.setattr(tc, "open_file_dialog",
                        lambda *a, **k: str(work / "Local-P" / "project.json"))
    seen = {"choice": 0}
    monkeypatch.setattr(L, "_choice_dialog",
                        lambda *a, **k: (seen.__setitem__("choice", seen["choice"] + 1), "copy")[1])

    tab._load_existing_profile()

    assert seen["choice"] == 0                       # no pop-up for a local project
    assert fm.get_target_name() == "Local-P"
