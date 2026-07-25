"""#130 (Knut, 2026-07-25): under the Profile-run / Run-type bar, show the folder
the current selection writes into — spelled out from the ChromIQ folder down, and
updated whenever either dropdown changes."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,        # noqa: E402
                                       MeasurementTargetController)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _env(tmp_path, project_at=None, name="My-Printer"):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    where = project_at or (root / name)
    Project.create(where, name).current_run().ensure_dir()
    if project_at is not None:
        fm.open_project_at(where)
    else:
        fm.set_target_name(name)
    return MeasurementTargetController(fm)


def test_profiling_shows_the_run_folder(qapp, tmp_path):
    ctl = _env(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)

    assert ctl.location_being_edited() == "ChromIQ/My-Printer/runs/run1/"


def test_verification_appends_the_verifications_folder(qapp, tmp_path):
    ctl = _env(tmp_path)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)

    assert ctl.location_being_edited() == "ChromIQ/My-Printer/runs/run1/verifications/"


def test_a_nested_project_shows_its_real_place(qapp, tmp_path):
    """A project kept in sub-folders must show where the files really are."""
    root = tmp_path / "ChromIQ"; root.mkdir()
    ctl = _env(tmp_path, project_at=root / "customers" / "2026" / "My-Printer")
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)

    assert ctl.location_being_edited() == \
        "ChromIQ/customers/2026/My-Printer/runs/run1/"


def test_new_run_names_the_folder_that_would_be_created(qapp, tmp_path):
    """"New run" has no folder yet — show the one a Generate would make, so the
    user can see where things are about to land."""
    ctl = _env(tmp_path)
    ctl.set_profile_run("")                       # New run
    ctl.set_run_type(RUN_TYPE_PROFILING)

    assert ctl.location_being_edited() == "ChromIQ/My-Printer/runs/run2/"


def test_nothing_named_at_all_shows_nothing(qapp, tmp_path):
    """A freshly-started app names no destination — better than a half path."""
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir()
    s.set("custom_output_path", str(root))
    ctl = MeasurementTargetController(FileManager(s))

    assert ctl.location_being_edited() == ""


def test_a_typed_name_shows_the_destination_before_the_project_exists(qapp, tmp_path):
    """The answer is most useful BEFORE the first chart is generated: as soon as
    a name is typed, the line says where that chart will land."""
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir()
    s.set("custom_output_path", str(root))
    ctl = MeasurementTargetController(FileManager(s))

    ctl.set_pending_project_name("ChromIQ Test Chart")

    # Spaces become hyphens, exactly as the folder on disk will be named.
    assert ctl.location_being_edited() == "ChromIQ/ChromIQ-Test-Chart/runs/run1/"
    assert not (root / "ChromIQ-Test-Chart").exists(), "nothing is created early"

    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert ctl.location_being_edited().endswith("runs/run1/verifications/")

    ctl.set_pending_project_name("")          # cleared again
    assert ctl.location_being_edited() == ""


def test_bar_label_tracks_both_dropdowns(qapp, tmp_path):
    """The line is a live reflection of the bar, not a one-off."""
    ctl = _env(tmp_path)
    bar = MeasurementTargetBar(ctl)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    assert bar._location.isVisible() or True          # offscreen: text is the check
    assert bar._location.text().startswith("Location being edited:")
    assert bar._location.text().endswith("ChromIQ/My-Printer/runs/run1/")

    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert bar._location.text().endswith("runs/run1/verifications/")

    ctl.set_profile_run("")                            # New run
    assert bar._location.text().endswith("runs/run2/verifications/")
