"""Adversary round on 528b7cfc (K2 pre-flight history, B8-777 window picking).

Two kinds of test live here, and they are labelled:

* ``test_FAULT_*`` failed on 528b7cfc and demonstrated a fault that commit
  left; both faults are fixed and the tests now guard the fixes.
* ``test_GAP_*`` is GREEN on 528b7cfc; each closes a hole a mutation showed the
  commit's own guard did not cover (the mutation is named in the docstring).
"""
from __future__ import annotations

import os
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                      # noqa: E402

from tests.test_a_driver_photographs_the_window_not_the_screen import (  # noqa: E402
    _cg, _FakeWin, _helper)
from tests.test_the_verification_preflight_fires_for_its_preconditions import (  # noqa: E402
    _corner_chart, _ready_tab, qapp)                                # noqa: F401


# ---------------------------------------------------------------------------
# B8-777 is still open for EVERY QMessageBox on macOS
# ---------------------------------------------------------------------------
def test_FAULT_an_untitled_popup_is_not_whichever_other_untitled_window_is_biggest():
    """**On macOS `QMessageBox.windowTitle()` is always ""**: Qt's
    `QMessageBox::setWindowTitle` is compiled out on Q_OS_MACOS (measured on
    screen: the pre-flight's `windowTitle()` reads '' although the tab calls
    `setWindowTitle`). So `_pick_window` is asked for title "", and `named` is
    EVERY untitled window of the process, not the empty list the commit's own
    test assumes (it passes the title "Before you measure", which a message box
    on macOS never has).

    With the popup not yet on the on-screen list, or listed with bounds that do
    not match yet (both states the commit's B8-777 entry describes), and any
    OTHER untitled window on screen, the size rule answers and returns that
    other window. Measured on screen, 2026-09-22: a message box over a message
    box, the top one hidden, `capture_window(top)` returned ok=True with a
    photograph of the box BEHIND it
    (`~/Desktop/ChromIQ-beta36-proof/adversary-k2/probe/probe-hidden.png`).
    """
    pick = _helper()._pick_window
    main = _cg(164, 100, 1433, 928, "ChromIQ — Printer Profiling", 11)
    other_box = _cg(799, 397, 142, 311, "", 22)         # an untitled box behind
    top_box = _FakeWin(778, 481, 164, 119)               # not listed yet
    assert pick(top_box, [main, other_box], "") is None, (
        "the other untitled message box was picked for this one")


# ---------------------------------------------------------------------------
# the history check: mutations the commit's own guard survived
# ---------------------------------------------------------------------------
def test_GAP_history_is_read_from_the_SELECTED_profile_run_not_the_current_one(
        qapp, tmp_path):
    """Mutation survived by 528b7cfc's guard: `proj.run(ctl.target.profile_run)`
    -> `proj.current_run()`. The fixture's selected run IS the manifest's
    current run, so the two cannot be told apart. Here the history is in run1,
    the current run is run2, and run1 is the selected profile run."""
    tab, ctl, _chart = _ready_tab(tmp_path, qapp)
    proj = ctl.project_or_none()
    run1 = proj.run("run1")
    old = run1.new_verification()
    old.dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_corner_chart(), old.dir / f"{old.stem}.ti3")
    proj.new_run()
    assert ctl.project_or_none().current_run().id != "run1", (
        "the fixture did not move the current run away from run1")
    ctl.set_profile_run("run1")
    ctl.set_verification_id("")
    assert tab._run_has_a_measured_verification() is True
    assert tab._verification_preflight_due() is False


def test_GAP_an_empty_first_date_does_not_hide_a_measured_later_one(
        qapp, tmp_path):
    """Mutation survived by 528b7cfc's guard: iterate `run.verifications()[:1]`.
    A folder is made when a sheet is printed, so the OLDEST date being empty
    (printed, never read) while later ones hold readings is ordinary."""
    tab, ctl, _chart = _ready_tab(tmp_path, qapp)
    run = ctl.project_or_none().run("run1")
    first = run.new_verification()
    first.dir.mkdir(parents=True, exist_ok=True)
    first.measurement_ti3.write_text('CTI3\nKEYWORD "X"\nNUMBER_OF_SETS 0\n',
                                     encoding="utf-8")
    later = run.new_verification()
    later.dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_corner_chart(), later.dir / f"{later.stem}.ti3")
    assert first.id < later.id
    ctl.set_verification_id("")
    assert tab._verification_preflight_due() is False


# ---------------------------------------------------------------------------
# the same getattr-with-a-default pattern, elsewhere
# ---------------------------------------------------------------------------
def test_FAULT_spot_readings_are_suggested_into_the_runs_exports_folder(
        qapp, tmp_path):
    """`SpotReadDialog._suggested_save_path` says "the current run's exports"
    and asks `getattr(run, "exports", None)`. `Run` has `exports_dir` and no
    `exports`, so the branch is dead and the suggestion is always the bare run
    folder: the K2 fault's shape, a default that turns a wrong name into a
    plausible answer."""
    import types
    from core.file_manager import FileManager, Project
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    got = SpotReadDialog._suggested_save_path(types.SimpleNamespace(_file_mgr=fm))
    run = fm.project().current_run()
    assert got.parent == run.exports_dir, got
