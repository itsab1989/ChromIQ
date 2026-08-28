"""F7: the target bar stayed live while a chart or profile was being built.

Measured on screen, 2026-08-28, with a real chart build in flight: Generate was
correctly greyed, and Delete, Duplicate, the run picker and the run-type picker
were all still live — on the very run targen was writing into. Driven to the
end, Delete removed that run under the running subprocess; targen then failed
with "Chart Generation Failed", which gives the person no hint that they caused
it, and the surviving runs were renumbered while a subprocess still held a path
inside the tree.

WHY NOT `ArgyllRunner.is_running`, which is the obvious answer: the masthead
tried exactly that and `ui/main_window.py` records why it does not use it — the
runner is briefly idle between targen and printtarg ("greyed for all 19 samples
of targen and 0 of the 8 samples of printtarg"), it is idle for the whole
in-process layout-engine phase, which is when the .ti2 and the pages are
written, and it is BUSY for every Tools subprocess that touches nothing here.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_the_bar_offers_a_build_lock_at_all(qapp):
    from ui.measurement_target_bar import MeasurementTargetBar
    assert hasattr(MeasurementTargetBar, "set_build_running")
    assert hasattr(MeasurementTargetBar, "_building_note")


def test_the_build_lock_says_something_true_about_a_build(qapp):
    """"Not while a measurement is running" is simply false during a chart
    build, and it is the sentence the person would have read."""
    from ui.measurement_target_bar import MeasurementTargetBar
    import inspect
    note = inspect.getsource(MeasurementTargetBar._building_note)
    assert "measurement" not in note.lower(), \
        "the build lock reuses the measurement wording, which is untrue here"
    assert "build" in note.lower()


def test_the_lock_is_fed_from_the_one_place_that_owns_it(qapp):
    """#164's rule: nothing else may enable or disable these, or they drift
    apart. The bar is fed from `_refresh_masthead_availability`, from the same
    three flags the masthead uses — NOT from `ArgyllRunner.is_running`."""
    import inspect

    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._refresh_masthead_availability)
    assert "set_build_running" in src, \
        "the target bar is not fed from the one place that owns the lock"
    assert "_chart_locked" in src and "_profile_building" in src
    assert "is_running" not in src, (
        "the bar is being locked on ArgyllRunner.is_running — that is false "
        "between targen and printtarg and for the whole engine phase, and true "
        "for every Tools subprocess")


def test_a_build_greys_the_run_picker_and_delete(qapp, tmp_path):
    from PyQt6.QtCore import QSettings

    from core.file_manager import FileManager, Project
    from core.settings import AppSettings
    from ui.measurement_target_bar import (MeasurementTargetBar,
                                           MeasurementTargetController)

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    fm = FileManager(s)
    Project.create(tmp_path / "out" / "Proj", "Proj")
    fm.set_target_name("Proj")
    bar = MeasurementTargetBar(MeasurementTargetController(fm))

    live = bar._run_combo.isEnabled()
    assert live, "the run picker should start live, or this proves nothing"
    bar.set_build_running(True)
    assert bar._run_combo.isEnabled() is False, \
        "the run picker stayed live while a build was running"
    assert bar._delete_btn.isEnabled() is False, \
        "Delete stayed live on the run being written to"
    bar.set_build_running(False)
    assert bar._run_combo.isEnabled() is live, "the lock did not come back off"
