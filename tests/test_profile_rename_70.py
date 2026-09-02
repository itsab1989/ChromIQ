"""#70 (Knut's model): the Create Chart name is a plain *printer-profile* name.

Renaming it after a project exists reconciles the folder on the spot (rename /
keep / delete); once the profile has been *built* renaming is refused and the
user is pointed at copy-to-new instead.
"""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    from PyQt6.QtCore import QSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))   # isolate the root
    return s


def _make_tab(settings):
    from ui.tabs.tab_chart import TabChart
    fm = FileManager(settings)
    t = TabChart(ArgyllRunner(settings), fm, settings)
    t._switch_mode("manual")
    return t, fm


def _create_project(fm, name):
    fm.set_target_name(name)
    fm.project()                       # writes project.json + runs/run1/
    return fm.root_dir() / name


def test_rename_on_edit_moves_the_folder(qapp, settings, monkeypatch):
    from ui.dialogs import target_change_dialog as tcd
    t, fm = _make_tab(settings)
    old_root = _create_project(fm, "OldProfile")
    assert (old_root / "project.json").exists()
    t._last_target_name = "OldProfile"

    # Choose "rename" in the chooser without showing it.
    monkeypatch.setattr(tcd.TargetChangeDialog, "exec", lambda self: 0)
    monkeypatch.setattr(tcd.TargetChangeDialog, "result_action",
                        lambda self: tcd.TargetChangeAction.RENAME)

    f = t._manual_target_name_edit
    f.setText("NewProfile")
    t._clean_target_name_field(f, t._manual_target_name_hint)

    new_root = fm.root_dir() / "NewProfile"
    assert new_root.exists() and not old_root.exists()
    assert fm.get_target_name() == "NewProfile"
    assert t._last_target_name == "NewProfile"


def test_rename_blocked_after_profile_built(qapp, settings, monkeypatch):
    from ui.tabs import tab_chart as tc
    t, fm = _make_tab(settings)
    old_root = _create_project(fm, "BuiltProfile")
    # Simulate a finished build: drop a deliverable ICC into the current run.
    run = fm.project().current_run()
    run.ensure_dir()
    run.profile_icc.write_bytes(b"icc")
    t._last_target_name = "BuiltProfile"

    seen = {"warned": False}
    monkeypatch.setattr(tc.InfoDialog, "exec", lambda self: seen.__setitem__("warned", True))

    f = t._manual_target_name_edit
    f.setText("RenamedAfterBuild")
    t._clean_target_name_field(f, t._manual_target_name_hint)

    # Refused: the folder is untouched and the field snaps back to the built name.
    assert old_root.exists()
    assert not (fm.root_dir() / "RenamedAfterBuild").exists()
    assert f.text() == "BuiltProfile"
    assert seen["warned"]


def test_load_existing_profile_activates_and_fills_name(qapp, settings, monkeypatch):
    from ui.widgets import PrefixLockedLineEdit
    import ui.tabs.tab_chart as tc
    t, fm = _make_tab(settings)
    # Create a project on disk to load back.
    proj_root = _create_project(fm, "SavedProfile")
    assert (proj_root / "project.json").is_file()
    # Switch away so loading has to re-activate it.
    fm.set_target_name("SomethingElse")

    monkeypatch.setattr(tc, "open_file_dialog",
                        lambda *a, **k: str(proj_root / "project.json"))
    t._load_existing_profile()

    assert fm.get_target_name() == "SavedProfile"
    assert t._last_target_name == "SavedProfile"
    f = t._manual_target_name_edit
    assert isinstance(f, PrefixLockedLineEdit)
    assert f.text() == "SavedProfile"


def test_load_existing_profile_rejects_non_project(qapp, settings, monkeypatch, tmp_path):
    import ui.tabs.tab_chart as tc
    t, fm = _make_tab(settings)
    fm.set_target_name("Keep")
    bogus = tmp_path / "notes.txt"
    bogus.write_text("hi", encoding="utf-8")
    warned = {"v": False}
    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(bogus))
    monkeypatch.setattr(tc.InfoDialog, "exec", lambda self: warned.__setitem__("v", True))
    t._load_existing_profile()
    assert warned["v"]
    assert fm.get_target_name() == "Keep"        # unchanged
