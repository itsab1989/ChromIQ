"""#130 (Knut, 2026-07-29): "Delete the whole project" must leave the app as it
starts — and must not quietly make the project again.

*"Continuation of the delete whole project bug: After the project was deleted, I
moved to Print Chart tab. Then, suddenly the "Location being edited" path below
the profile run bar had changed to "Location being edited:
ChromIQ/Demo-Verify-History/runs/run1/". A new project with the same project name
had been created under the default ChromIQ path. This is also wrong. After
deletion of the whole project I was working in, the user interface must return to
the starting state of the app, empty and no loaded project. It must not create
another project that I did not ask for."*

Two faults, one cause. The file manager still held the deleted project's NAME, so
anything that asked for "the project" created the folder from scratch —
``FileManager.project()`` is a create-or-load — and the bar then dutifully showed
the resurrected project as the one being edited.

The fix is to forget the name, which is exactly the state a freshly started
ChromIQ is in, plus emptying every tab. These tests hold both halves.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                            # noqa: E402
from PyQt6.QtWidgets import QApplication                      # noqa: E402

from core.file_manager import FileManager, Project            # noqa: E402
from core.measurement_target import RUN_TYPE_VERIFICATION     # noqa: E402
from core.settings import AppSettings                         # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,  # noqa: E402
                                       MeasurementTargetController)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _fm(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"
    root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    return FileManager(s), root


# ---- the file manager: forgetting is what stops the resurrection ----------
def test_a_closed_project_is_the_state_a_fresh_start_is_in(tmp_path):
    fm, root = _fm(tmp_path)
    fresh_name = fm._target_name
    fresh_override = fm.project_root_override()

    Project.create(root / "Demo", "Demo")
    fm.set_target_name("Demo")
    assert fm.has_project()

    fm.close_project()
    assert fm._target_name == fresh_name == ""
    assert fm.project_root_override() is fresh_override is None
    assert fm.has_project() is False


def test_a_nested_project_is_forgotten_too(tmp_path):
    """A project kept in a sub-folder is remembered by an override as well as by
    name — both have to go, or working_dir() still resolves to it."""
    fm, root = _fm(tmp_path)
    nested = root / "customers" / "2026" / "Demo"
    Project.create(nested, "Demo")
    fm.open_project_at(nested)
    assert fm.has_project()

    fm.close_project()
    assert fm.project_root_override() is None
    assert fm.has_project() is False


def test_asking_whether_a_project_is_open_creates_nothing(tmp_path):
    """has_project() is called from a UI refresh, so it must be safe: neither the
    ChromIQ folder's contents nor the invented auto-name may change."""
    fm, root = _fm(tmp_path)
    before = sorted(p.name for p in root.iterdir())
    assert fm.has_project() is False
    assert fm._target_name == "", "asking invented a name"
    assert sorted(p.name for p in root.iterdir()) == before


def test_after_close_nothing_names_the_deleted_project(tmp_path):
    """The heart of Knut's report: after the delete, the very next question about
    the project must not put the folder back under its old name."""
    import shutil
    fm, root = _fm(tmp_path)
    Project.create(root / "Demo-Verify-History", "Demo-Verify-History")
    fm.set_target_name("Demo-Verify-History")
    fm.project()                                     # cache it, as the app does

    shutil.rmtree(root / "Demo-Verify-History")
    fm.close_project()

    # Everything the UI does on a tab switch, in the order it does it.
    ctl = MeasurementTargetController(fm)
    assert ctl.project_or_none() is None
    assert ctl.location_being_edited() == ""
    assert not (root / "Demo-Verify-History").exists(), \
        "the deleted project was created again"


# ---- the controller: no run, no run type, no date is selected any more ----
def test_the_selection_is_forgotten(qapp, tmp_path):
    fm, root = _fm(tmp_path)
    Project.create(root / "Demo", "Demo")
    fm.set_target_name("Demo")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_verification_id("2026-07-29_120000")
    ctl.set_pending_project_name("Demo")

    fired = []
    ctl.changed.connect(lambda: fired.append(1))
    ctl.reset_to_empty()

    assert ctl.target.profile_run == ""
    assert ctl.target.verification_id == ""
    assert ctl.target.is_verification() is False
    assert fired, "the bar was never told to redraw"


def test_the_bar_goes_back_to_its_no_project_state(qapp, tmp_path):
    """What the user sees: greyed selectors, the "load or name a project" hint,
    and no location line naming a folder that is gone."""
    import shutil
    fm, root = _fm(tmp_path)
    Project.create(root / "Demo", "Demo")
    fm.set_target_name("Demo")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    bar = MeasurementTargetBar(ctl, show_verification=True)
    bar.refresh()
    assert bar._location.isVisibleTo(bar)

    shutil.rmtree(root / "Demo")
    fm.close_project()
    ctl.reset_to_empty()
    bar.refresh()

    assert not bar._run_combo.isEnabled()
    assert not bar._type_combo.isEnabled()
    assert bar._hint.isVisibleTo(bar), "the empty-app hint is missing"
    assert bar._location.text() == ""
    assert not bar._location.isVisibleTo(bar)


# ---- the window: every tab lets go, in a safe order ----------------------
def test_the_window_reacts_to_the_deletion_at_all():
    """The bar has always announced the deletion; before this fix nobody was
    listening, which is why the interface kept showing the deleted project."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.__init__)
    assert "project_deleted.connect(self._on_project_deleted)" in src


def test_the_window_empties_every_tab_and_forgets_the_session():
    from ui.main_window import MainWindow
    # The body moved into `_reset_after_project_gone` in #164, so that
    # deleting and CLOSING a project land in the same state — an app with
    # two different "no project" states is one nobody can predict.
    src = inspect.getsource(MainWindow._reset_after_project_gone)
    for step in ("self._file_mgr.close_project()",
                 "self._target_ctl.reset_to_empty()",
                 "self._tab_chart.clear_loaded_project()",
                 "self._tab_print.load_tiffs([])",
                 "self._tab_measure.clear_chart_file()",
                 "self._tab_profile.clear_files()",
                 "self._tab_check.clear_files()",
                 "self._target_bar.refresh()",
                 "session_target_name"):
        assert step in src, f"missing: {step}"


def test_the_name_is_forgotten_before_anything_else_runs():
    """Order matters. Every step after this one can ask about the project, and
    each such question is a chance to create the folder again."""
    from ui.main_window import MainWindow
    # The body moved into `_reset_after_project_gone` in #164, so that
    # deleting and CLOSING a project land in the same state — an app with
    # two different "no project" states is one nobody can predict.
    src = inspect.getsource(MainWindow._reset_after_project_gone)
    first = src.index("close_project()")
    for later in ("reset_to_empty()", "clear_loaded_project()",
                  "load_tiffs([])", "refresh()"):
        assert first < src.index(later), f"{later} runs before the name is gone"


def test_the_remembered_session_no_longer_points_at_the_deleted_project():
    from ui.main_window import MainWindow
    # The body moved into `_reset_after_project_gone` in #164, so that
    # deleting and CLOSING a project land in the same state — an app with
    # two different "no project" states is one nobody can predict.
    src = inspect.getsource(MainWindow._reset_after_project_gone)
    for key in ("session_target_name", "session_project_root",
                "session_ti1_path", "session_ti3_path", "session_icc_path",
                "session_cal_ti3_path"):
        assert key in src, f"{key} would still name the deleted project"


def test_the_delete_never_ends_in_a_crash():
    """A tab that fails to clear must not leave the app half-reset with a
    traceback on top of a destructive action."""
    from ui.main_window import MainWindow
    # The body moved into `_reset_after_project_gone` in #164, so that
    # deleting and CLOSING a project land in the same state — an app with
    # two different "no project" states is one nobody can predict.
    src = inspect.getsource(MainWindow._reset_after_project_gone)
    assert src.count("except Exception") >= 2


# ---- the Create Chart tab -------------------------------------------------
def test_the_chart_tab_drops_the_project_but_keeps_the_options():
    """Re-typing the instrument, paper and patch count after a delete would be
    its own annoyance — only the project's identity is dropped."""
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart.clear_loaded_project)
    assert 'self._last_target_name = ""' in src
    assert "self._shown_chart_ti2 = None" in src
    assert "self._preview.clear()" in src
    assert "chart_finished.emit([], None, False)" in src
    # It must not reach into the parameter panels.
    for forbidden in ("set_recipe", "_apply_params", "setCurrentIndex"):
        assert forbidden not in src, f"clearing touched {forbidden}"


# ---- Knut's sequence, played out on the real window ----------------------
@pytest.fixture(scope="module")
def win(qapp, tmp_path_factory):
    """The real window. Only the two offscreen-incompatible edges are stubbed
    (the ArgyllCMS-missing modal and the native title-bar tint); never closed,
    because closeEvent tears down WebEngine and segfaults under offscreen Qt."""
    from ui.main_window import MainWindow
    MainWindow._apply_title_bar = lambda self, mode: None
    tmp = tmp_path_factory.mktemp("delproj")
    s = AppSettings()
    s._qs = QSettings(str(tmp / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp / "ChromIQ"))
    s.set("restore_last_session", False)
    w = MainWindow(s)
    qapp.processEvents()
    return w


def test_his_exact_sequence_leaves_the_app_empty(qapp, win, monkeypatch):
    """Open a project, delete the whole project, then walk the tabs as he did.

    *"After the project was deleted, I moved to Print Chart tab. Then, suddenly
    the 'Location being edited' path… had changed to
    'ChromIQ/Demo-Verify-History/runs/run1/'. A new project with the same project
    name had been created."*
    """
    from PyQt6.QtWidgets import QMessageBox

    fm = win._file_mgr
    root = fm.root_dir()
    root.mkdir(parents=True, exist_ok=True)
    proj = Project.create(root / "Demo-Verify-History", "Demo-Verify-History")
    run = proj.current_run()
    run.ensure_dir()
    run.chart_ti1.write_text("TI1")
    run.chart_ti2.write_text("TI2")
    fm.set_target_name("Demo-Verify-History")
    win._target_ctl.set_profile_run(run.id)
    win._target_bar.refresh()
    assert win._target_bar._location.text() != ""

    # Confirm with "Delete the whole project", the way he did.
    seen: list = []

    def _fake_exec(self) -> int:
        seen.append(self)
        return 0

    def _clicked(self):
        for b in self.buttons():
            if "whole project" in b.text():
                return b
        return None

    monkeypatch.setattr(QMessageBox, "exec", _fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", _clicked)
    win._target_bar._on_delete_clicked()
    qapp.processEvents()
    assert seen, "no confirmation was shown before deleting a whole project"

    assert not (root / "Demo-Verify-History").exists(), "the folder survived"

    # Now walk every tab, which is what resurrected it.
    for i in range(win._tabs.count()):
        win._tabs.setCurrentIndex(i)
        qapp.processEvents()

    assert not (root / "Demo-Verify-History").exists(), \
        "walking the tabs created the deleted project again"
    assert fm._target_name == "", "the app still names the deleted project"
    assert win._target_bar._location.text() == "", \
        "the location line still points into the deleted project"
    assert win._tab_chart._manual_target_name_edit.text() == "", \
        "the name field still holds the deleted project's name"
    assert win._tab_measure.ti1_path is None
    assert win._tab_profile.ti3_path is None
    assert win._target_ctl.target.profile_run == ""
    # And nothing invented a replacement project anywhere.
    assert [p.name for p in root.iterdir() if p.is_dir()] == []


def test_the_bar_still_announces_the_deletion_after_removing_the_folder():
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar._delete_whole_project)
    assert "shutil.rmtree(root)" in src
    assert src.index("shutil.rmtree(root)") < src.index("project_deleted.emit()")
