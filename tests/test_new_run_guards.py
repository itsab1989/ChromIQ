"""#130 (Knut, 2026-07-25): "New run" names a run that does not exist yet, so
Print and Measure must refuse and explain — not fail obscurely — and the message
must say how to create a run."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox     # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     new_run_guard_message)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _env(tmp_path):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    return s, fm, MeasurementTargetController(fm)


@pytest.mark.parametrize("action", ["print", "measure"])
def test_guard_message_names_every_way_to_create_a_run(action):
    msg = new_run_guard_message(action)
    assert ("print" if action == "print" else "measure") in msg.lower()
    for needle in ("Create Chart", "Generate Chart", "preset", ".ti1", ".ti2",
                   "New run", "Profiling"):
        assert needle in msg, f"guard message must mention {needle!r}"


def test_measure_refuses_to_start_on_new_run(qapp, tmp_path, monkeypatch):
    from ui.tabs.tab_measure import TabMeasure
    s, fm, ctl = _env(tmp_path)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    ctl.set_profile_run(""); ctl.set_run_type(RUN_TYPE_PROFILING)   # New run
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda p, t, m, *a, **k: shown.append(m)))

    assert tab._blocked_by_new_run() is True
    assert shown and "already created chart" in shown[0]


def test_measure_proceeds_on_an_existing_run(qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    s, fm, ctl = _env(tmp_path)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    ctl.set_profile_run("run1")

    assert tab._blocked_by_new_run() is False


def test_print_refuses_on_new_run_and_proceeds_otherwise(qapp, tmp_path, monkeypatch):
    from ui.tabs.tab_print import TabPrint
    s, fm, ctl = _env(tmp_path)
    tab = TabPrint(s)
    tab.set_target_controller(ctl)
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda p, t, m, *a, **k: shown.append(m)))

    ctl.set_profile_run("")
    assert tab._blocked_by_new_run() is True
    assert shown and "already created chart" in shown[0]

    ctl.set_profile_run("run1")
    assert tab._blocked_by_new_run() is False
