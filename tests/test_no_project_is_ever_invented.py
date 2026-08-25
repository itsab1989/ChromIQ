"""Nothing may create a project the user did not ask for (#164, and #130).

Knut, #130: *"It must not create another project that I did not ask for."* That
fix stopped an OLD name coming back; it did not stop a NEW one being invented.

`FileManager.get_target_name()` is a mutating getter — it makes up a name and
stores it when there is none — and `working_dir()` goes through it. So any code
that asked "is there a project?" by looking for `working_dir()/project.json`
armed a phantom simply by asking. Two paths then wrote to disk:

* opening the Tools menu armed the name, and the next action created
  `~/ChromIQ/Printer_Paper_Type_Instr_<date>/`;
* Tools ▸ patch-set editor ▸ Save & apply staged `edited_patch_set.ti1` into
  that invented folder — leaving an orphan with no `project.json`, which
  ChromIQ can never find again, and then made a second real project beside it.

`has_project()` short-circuits on an empty name and creates nothing, so it is
the only safe way to ask.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


def _clean_fm(tmp_path):
    from core.file_manager import FileManager
    from core.settings import AppSettings

    settings = AppSettings()
    settings.set("custom_output_path", str(tmp_path / "out"))
    fm = FileManager(settings)
    fm.close_project()
    return fm


def test_asking_whether_a_project_is_open_creates_nothing(qapp, tmp_path):
    """The question itself must be free of side effects."""
    fm = _clean_fm(tmp_path)
    assert fm.has_project() is False
    assert fm._target_name == "", "has_project() invented a name"
    assert not list((tmp_path / "out").glob("*")) if (tmp_path / "out").exists() \
        else True, "has_project() created a folder"


def test_working_dir_is_the_mutating_one(qapp, tmp_path):
    """The counter-example, so the reason for the rule stays visible.

    If this ever stops being true, `get_target_name()` has been made pure and
    the guards below can be relaxed — but until then, every "is a project open?"
    check must use `has_project()`.
    """
    fm = _clean_fm(tmp_path)
    fm.working_dir()
    assert fm._target_name != "", (
        "working_dir() no longer invents a name — the guards can be simplified")


def test_no_ui_path_asks_by_looking_for_project_json(qapp):
    """Structural: the unsafe idiom must not come back.

    A `working_dir() / "project.json"` existence check reads as harmless and is
    not — it arms the phantom on the way to the answer.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    bad = []
    for path in list((root / "ui").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r'working_dir\(\)\s*/\s*"project\.json"', text):
            line = text[:m.start()].count("\n") + 1
            bad.append(f"{path.relative_to(root)}:{line}")
    assert not bad, (
        "these ask whether a project exists by a route that invents one; use "
        "has_project(): " + ", ".join(bad))


def test_applying_an_edited_patch_set_needs_a_project(qapp, tmp_path):
    """It stages a file into the project folder, so with no project there is
    nowhere for it to go — and it must not invent somewhere."""
    import inspect

    from ui import main_window

    src = inspect.getsource(main_window.MainWindow._apply_editor_chart)
    assert "is_named()" in src, (
        "the editor's Save & apply adopts a chart without checking that a "
        "project is named — it creates an orphan folder")


def test_is_named_is_free_of_side_effects(qapp, tmp_path):
    """The weaker question must be as safe as the stronger one."""
    fm = _clean_fm(tmp_path)
    assert fm.is_named() is False
    assert fm._target_name == "", "is_named() invented a name"


# ---------------------------------------------------------------------------
# THE BUILD PROFILE TAB STAYS SHUT WHILE A MEASUREMENT RUNS (#164)
# ---------------------------------------------------------------------------
# `_on_measurement_active` disables every tab but Measure — and three lines
# later the signals it emits reach `_apply_profile_tab_gate`, which enables
# Build Profile again. The code contradicted itself: measured before the fix,
# idle → enabled and measuring → still enabled. Walking into a build mid-read
# is exactly what the disable exists to prevent.
#
# Whether the tab should also SAY why it is unavailable is a separate question
# and is parked; this only holds the code to its own intent.


def test_a_running_measurement_keeps_the_build_profile_tab_shut(qapp):
    import inspect

    from ui.main_window import MainWindow

    gate = inspect.getsource(MainWindow._apply_profile_tab_gate)
    assert "_measuring" in gate, (
        "the profile-tab gate cannot see that a measurement is running, so it "
        "re-enables the tab that _on_measurement_active just disabled")
    active = inspect.getsource(MainWindow._on_measurement_active)
    head = active.split("measure_idx", 1)[0]
    assert "_measuring" in head, (
        "_measuring is recorded too late — the gate runs from the signals "
        "emitted below it and would read the previous value")


def test_adopting_an_edited_chart_with_no_project_says_so_and_changes_nothing(
        qapp, tmp_path):
    """The branch itself, driven — not just its source text.

    A structural check that the guard exists cannot tell whether the guard
    RUNS: mine referenced `InfoDialog` without importing it and passed its
    arguments in the wrong order, and every test still passed, because none of
    them reached this branch. So this one reaches it.
    """
    import pathlib as _p
    from unittest import mock

    from core.settings import AppSettings
    from ui.main_window import MainWindow

    settings = AppSettings()
    settings.set("custom_output_path", str(tmp_path / "out"))
    settings.set("session_project", "")
    win = MainWindow(settings)
    try:
        win._file_mgr.close_project()
        with mock.patch("ui.tooltip_button._InfoDialog.exec",
                        return_value=0) as shown:
            adopted = win._apply_editor_chart(_p.Path(tmp_path / "nothing"), "x")
        assert adopted is False, "a chart was adopted with no project to hold it"
        assert shown.called, "the user was told nothing"
        assert win._file_mgr._target_name == "", "a project name was invented"
        out = tmp_path / "out"
        assert not out.exists() or not list(out.iterdir()), (
            "a folder was created for a project that does not exist")
    finally:
        win.close()
