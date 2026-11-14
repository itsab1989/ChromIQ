"""A name THE PERSON gives is typed, however it reaches the box (2026-11-14).

4.3.28 made typing in "Printer profile project name" quiet: a typed name is
no change of target, so a Create Chart change not yet generated stays on
screen (`tests/test_typing_a_project_name_is_not_a_target_change.py`). Two
routes put the person's own name into the box with `setText`, which the bar
reads as the APP writing it, i.e. a project switch:

* the answer in the project-name window (Generate with a name a folder cannot
  take, "Delta:1");
* the typed name with a file extension taken off ("Beta.icc" -> "Beta").

Each reloaded the OPEN project's stored settings over the screen, and the new
project was built from them. Driven on screen 2026-11-14 (small-fixes
`runs/d2d_routes`): Letter chosen, "Beta.icc" typed, Beta built on A4; A3
chosen, "Delta:1" typed and corrected in the window, Delta built on A4.
"""
from __future__ import annotations

import pytest

from core.file_manager import Project


def _window(qapp, work, open_name):
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    s = AppSettings()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("session_project", "")
    s.set("auto_update_preview", False)
    w = MainWindow(s)
    w._tab_chart.open_project_manifest(work / open_name / "project.json")
    for _ in range(20):
        qapp.processEvents()
    w._tab_chart._user_switch_mode("manual")
    for _ in range(10):
        qapp.processEvents()
    return w


@pytest.fixture
def opened(qapp, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    proj = Project.create(work / "Open-One", "Open-One")
    proj.current_run().ensure_dir()
    w = _window(qapp, work, "Open-One")
    yield w
    w.close()


def _unapplied_scale(tab):
    pw = [p for p in tab._manual_widgets["printtarg"] if p.flag == "-a"][0]
    pw.set_user_enabled(True)
    pw.set_value(1.37)
    return pw


def _count_loads(tab, ctl):
    seen = {"changed": 0, "loads": 0}
    ctl.changed.connect(lambda *_a: seen.__setitem__("changed", seen["changed"] + 1))
    real = tab.load_target_settings

    def counting(*a, **k):
        seen["loads"] += 1
        return real(*a, **k)
    tab.load_target_settings = counting
    return seen


def test_the_name_window_answer_is_typed(opened, qtbot, monkeypatch):
    w = opened
    tab, ctl = w._tab_chart, w._target_ctl
    _unapplied_scale(tab)
    qtbot.wait(200)
    seen = _count_loads(tab, ctl)
    import ui.dialogs.name_prompt as np_mod
    monkeypatch.setattr(np_mod, "ask_for_project_name",
                        lambda *a, **k: "Delta")
    assert tab._ask_for_a_project_name() is True
    qtbot.wait(300)
    assert tab._manual_target_name_edit.text() == "Delta"
    assert tab._target_name_edit.text() == "Delta", "the Guided box follows"
    assert seen == {"changed": 0, "loads": 0}, (
        "the person's answer was taken as a project switch")
    assert tab._manual_get("printtarg", "-a", None) == pytest.approx(1.37), (
        "the unapplied change was thrown away")
    assert ctl._pending_name == "Delta", "the location line follows"


def test_a_typed_name_with_its_extension_taken_off_is_typed(opened, qtbot,
                                                            monkeypatch):
    from PyQt6.QtTest import QTest
    w = opened
    tab, ctl = w._tab_chart, w._target_ctl
    _unapplied_scale(tab)
    qtbot.wait(200)
    seen = _count_loads(tab, ctl)
    # The rename chooser that follows is not what this pins.
    monkeypatch.setattr(tab, "_maybe_rename_on_edit", lambda *a, **k: None)
    field = tab._manual_target_name_edit
    field.selectAll()
    QTest.keyClicks(field, "Beta.icc")
    field.editingFinished.emit()
    qtbot.wait(300)
    assert field.text() == "Beta"
    assert seen == {"changed": 0, "loads": 0}, (
        "taking '.icc' off was taken as a project switch")
    assert tab._manual_get("printtarg", "-a", None) == pytest.approx(1.37)


def test_with_no_project_open_the_answer_still_tells_the_tabs(qapp, tmp_path,
                                                              qtbot,
                                                              monkeypatch):
    """No project, no store: as before, the name is a change of target (the
    no-project guidance hangs on it, see d24008046)."""
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    work = tmp_path / "w"
    work.mkdir()
    s = AppSettings()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("session_project", "")
    w = MainWindow(s)
    try:
        tab, ctl = w._tab_chart, w._target_ctl
        seen = _count_loads(tab, ctl)
        import ui.dialogs.name_prompt as np_mod
        monkeypatch.setattr(np_mod, "ask_for_project_name",
                            lambda *a, **k: "First")
        assert tab._ask_for_a_project_name() is True
        qtbot.wait(200)
        assert seen["changed"] == 1
    finally:
        w.close()
