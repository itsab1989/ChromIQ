"""Offscreen end-to-end tests for the shared Profile-run / Run-type selector
(#130): the controller, and the bar widget driving + reflecting it."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.file_manager import Project  # noqa: E402
from core.measurement_target import RUN_TYPE_VERIFICATION  # noqa: E402
from ui.measurement_target_bar import (  # noqa: E402
    MeasurementTargetBar, MeasurementTargetController)


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _FM:
    """Minimal FileManager stand-in the controller needs."""
    def __init__(self, root: Path):
        self._root = root

    def working_dir(self) -> Path:
        return self._root

    def project(self) -> Project:
        return Project.load(self._root)


def _project_with_runs(tmp_path: Path) -> Path:
    proj = Project.create(tmp_path / "Canon", "Canon")
    proj.current_run().ensure_dir()          # run1
    proj.new_run()                           # run2 (becomes current)
    # run1 gets a profile + two dated verifications for the dropdown.
    r1 = proj.run("run1")
    r1.profile_icc.write_text("icc")
    import datetime as _dt
    r1.new_verification(_dt.datetime(2026, 6, 1, 9, 0, 0)).ensure_dir()
    r1.new_verification(_dt.datetime(2026, 7, 1, 9, 0, 0)).ensure_dir()
    return proj.root


def test_controller_lists_and_mutates(tmp_path):
    root = _project_with_runs(tmp_path)
    ctl = MeasurementTargetController(_FM(root))
    assert ctl.run_ids() == ["run1", "run2"]
    assert len(ctl.verification_ids("run1")) == 2
    assert ctl.verification_ids("run2") == []

    seen = []
    ctl.changed.connect(lambda: seen.append(1))
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run("run1")
    assert ctl.target.is_verification() and ctl.target.profile_run == "run1"
    assert len(seen) == 2
    # Changing the run clears a stale verification pick.
    ctl.set_verification_id("x")
    ctl.set_profile_run("run2")
    assert ctl.target.verification_id == ""


def test_bar_populates_and_drives_controller(tmp_path):
    root = _project_with_runs(tmp_path)
    ctl = MeasurementTargetController(_FM(root))
    bar = MeasurementTargetBar(ctl, show_verification=True)

    # Run dropdown: one entry per run + "New run".
    assert bar._run_combo.count() == 3
    assert bar._run_combo.itemData(bar._run_combo.count() - 1) == "\x00new"

    # Verification box hidden while type is Profiling.
    assert not bar._verify_combo.isVisible()

    # Switch to Verification via the widget → controller updates + box shows.
    bar._type_combo.setCurrentIndex(bar._type_combo.findData(RUN_TYPE_VERIFICATION))
    assert ctl.target.is_verification()
    assert bar._verify_combo.isVisibleTo(bar)

    # Pick run1 → its two dated verifications + "New verification" appear.
    bar._run_combo.setCurrentIndex(bar._run_combo.findData("run1"))
    assert ctl.target.profile_run == "run1"
    assert bar._verify_combo.count() == 3        # 2 dates + New

    # Pick an existing date → controller records it.
    bar._verify_combo.setCurrentIndex(0)
    assert ctl.target.verification_id == ctl.verification_ids("run1")[0]


def test_two_bars_stay_in_sync(tmp_path):
    """Two bars on one controller mirror each other — the cross-tab behaviour."""
    root = _project_with_runs(tmp_path)
    ctl = MeasurementTargetController(_FM(root))
    a = MeasurementTargetBar(ctl)
    b = MeasurementTargetBar(ctl)

    a._type_combo.setCurrentIndex(a._type_combo.findData(RUN_TYPE_VERIFICATION))
    # b reflects the change made on a.
    assert b._type_combo.currentData() == RUN_TYPE_VERIFICATION
    a._run_combo.setCurrentIndex(a._run_combo.findData("run1"))
    assert b._run_combo.currentData() == "run1"


def test_hole7_bar_disabled_and_hint_without_project(qapp, tmp_path):
    """#130 Hole 7 (State B): with no profile project loaded the selectors are
    disabled and a hint is shown; a loaded project enables them and hides it."""
    class _NoProj:
        def working_dir(self): return tmp_path / "nope"
        def project(self): raise AssertionError("no project")
    bar = MeasurementTargetBar(MeasurementTargetController(_NoProj()))
    assert not bar._run_combo.isEnabled() and not bar._type_combo.isEnabled()
    assert not bar._hint.isHidden()                       # hint shown

    proj = Project.create(tmp_path / "P", "P"); proj.current_run().ensure_dir()
    bar2 = MeasurementTargetBar(MeasurementTargetController(_FM(proj.root)))
    assert bar2._run_combo.isEnabled() and bar2._type_combo.isEnabled()
    assert bar2._hint.isHidden()                          # hint gone
