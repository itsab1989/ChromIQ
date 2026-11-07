"""Typing in "Printer profile project name" is not a change of target
(4.3.28, perf audit 2026-11-07 item 3, approved by Basti).

Until 4.3.27 every keystroke went `textChanged -> set_pending_project_name ->
controller.changed`, so every tab ran its target-change handler per
character: about 100 ms a keystroke with a project open. Worse, Create
Chart's handler saved the target's settings and loaded them back, which
SILENTLY THREW AWAY a change not yet applied with Generate Chart: measured on
screen, the scale set to 1.37 with the red "What is on screen is not in this
run's chart yet" notice showing went back to 1.0, notice gone, after one
typed character. per_target_settings §2.2 says such a change is lost only
when you change run or close the project.

The typed name now has its own `pending_name_changed`, heard only by the
location line, which is the one thing that reads it. Basti asked what happens
to the name itself, so each of these is pinned here, in a real main window:

1. nothing applies to the project per keystroke;
2. the rename / keep chooser (#70) still comes only when the field loses
   focus, and a built profile still refuses the rename and puts the name back;
3. a name that belongs to another project still shows the §S4.7 line at once,
   per keystroke, and Generate still asks in the §S4.7 window before anything
   is touched;
4. with no project open, the location line follows the typing;
5. an unapplied change survives a typed character, notice and all.
"""
from __future__ import annotations

import shutil

import pytest

from core.file_manager import Project


def _window(qapp, work, open_name=None):
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    s = AppSettings()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("session_project", "")
    s.set("auto_update_preview", False)
    w = MainWindow(s)
    if open_name is not None:
        w._tab_chart.open_project_manifest(work / open_name / "project.json")
    for _ in range(20):
        qapp.processEvents()
    w._tab_chart._user_switch_mode("manual")
    # Opening a run may start a chart build of its own (the preview of its
    # chart); the §2.2 notice is silent while one is in flight, so wait.
    import time
    end = time.monotonic() + 90
    while w._tab_chart._chart_build_in_flight() and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.02)
    for _ in range(10):
        qapp.processEvents()
    return w


def _make_project(work, name):
    proj = Project.create(work / name, name)
    proj.current_run().ensure_dir()
    return proj


def _type(field, text):
    """Keystrokes: `textEdited` and `textChanged`, as a person typing."""
    from PyQt6.QtTest import QTest
    QTest.keyClicks(field, text)


class _Counter:
    def __init__(self):
        self.n = 0

    def __call__(self, *_a):
        self.n += 1


@pytest.fixture
def measured(qapp, tmp_path, demo_project, monkeypatch):
    """A real main window on a copy of a demo project whose run has a chart
    and a built profile."""
    work = tmp_path / "work"
    work.mkdir()
    src = demo_project("Demo-Full-RGB")
    shutil.copytree(src, work / src.name)
    w = _window(qapp, work, src.name)
    yield w, work, src.name
    w.close()


@pytest.fixture
def fresh(qapp, tmp_path):
    """A real main window on a project with an empty run (no profile)."""
    work = tmp_path / "work"
    work.mkdir()
    _make_project(work, "Open-One")
    w = _window(qapp, work, "Open-One")
    yield w, work, "Open-One"
    w.close()


# ---- 5. the fault: an unapplied change survives a keystroke -----------------

def test_an_unapplied_change_survives_a_typed_character(measured, qtbot):
    w, work, name = measured
    tab = w._tab_chart
    assert tab._shown_chart_ti2 is not None, "the run's chart is on screen"
    pw = [p for p in tab._manual_widgets["printtarg"] if p.flag == "-a"][0]
    pw.set_user_enabled(True)
    pw.set_value(1.37)
    qtbot.wait(500)
    assert tab._manual_get("printtarg", "-a", None) == pytest.approx(1.37)
    assert not tab._unapplied_lbl.isHidden(), "the red notice is up"

    _type(tab._manual_target_name_edit, "q")
    qtbot.wait(500)

    assert tab._manual_get("printtarg", "-a", None) == pytest.approx(1.37), (
        "one typed character threw the unapplied change away")
    assert not tab._unapplied_lbl.isHidden(), (
        "one typed character took the red notice away")


# ---- 1. nothing applies to the project per keystroke -------------------------

def test_a_keystroke_applies_nothing_to_the_project(measured, qtbot):
    w, work, name = measured
    tab, ctl = w._tab_chart, w._target_ctl
    root = work / name

    def disk():
        return {p.relative_to(work).as_posix(): (p.stat().st_mtime_ns,
                                                  p.stat().st_size)
                for p in work.rglob("*") if p.is_file()}
    before = disk()
    target_before = (w._file_mgr.get_target_name(), str(ctl.target),
                     str(ctl.project_or_none().root))
    changed, loads = _Counter(), _Counter()
    ctl.changed.connect(changed)
    real_load = tab.load_target_settings

    def counting_load(*a, **k):
        loads()
        return real_load(*a, **k)
    tab.load_target_settings = counting_load

    _type(tab._manual_target_name_edit, "xyz")
    qtbot.wait(300)

    assert changed.n == 0, "a keystroke was announced as a change of target"
    assert loads.n == 0, "a keystroke re-loaded the target's settings"
    assert disk() == before, "a keystroke wrote to the project folder"
    assert (w._file_mgr.get_target_name(), str(ctl.target),
            str(ctl.project_or_none().root)) == target_before
    assert tab._manual_target_name_edit.text() == name + "xyz"
    assert tab._target_name_edit.text() == name + "xyz", (
        "the Guided field no longer mirrors the Manual one")
    assert not (work / (name + "xyz")).exists(), "a folder was made early"
    assert (root / "project.json").is_file()


def test_a_real_target_change_still_reloads_once(measured, qtbot):
    w, work, name = measured
    tab, ctl = w._tab_chart, w._target_ctl
    changed, loads = _Counter(), _Counter()
    ctl.changed.connect(changed)
    real_load = tab.load_target_settings

    def counting_load(*a, **k):
        loads()
        return real_load(*a, **k)
    tab.load_target_settings = counting_load
    other = "run1" if ctl.target.profile_run != "run1" else "run2"
    ctl.set_profile_run(other)
    qtbot.wait(200)
    assert changed.n == 1
    assert loads.n >= 1


# ---- 2. the rename chooser, only when the field loses focus ------------------

def test_the_rename_chooser_comes_only_when_the_field_loses_focus(fresh, qtbot,
                                                                 monkeypatch):
    w, work, name = fresh
    tab = w._tab_chart
    asked = []
    monkeypatch.setattr(tab, "_handle_target_rename",
                        lambda new: asked.append(new) or False)
    field = tab._manual_target_name_edit
    _type(field, "-2")
    qtbot.wait(200)
    assert asked == [], "the chooser came while typing"
    field.editingFinished.emit()             # what losing focus sends
    qtbot.wait(200)
    assert asked == [name + "-2"], "the chooser did not come on leaving"
    assert field.text() == name, "a cancelled rename leaves the old name"
    assert w._file_mgr.get_target_name() == name


def test_a_built_profile_still_refuses_the_rename(measured, qtbot, monkeypatch):
    w, work, name = measured
    tab = w._tab_chart
    assert w._file_mgr.project_has_built_profile(name)
    warned = []
    monkeypatch.setattr(tab, "_warn_rename_after_profile",
                        lambda old: warned.append(old))
    renamed = []
    monkeypatch.setattr(tab, "_handle_target_rename",
                        lambda new: renamed.append(new) or True)
    field = tab._manual_target_name_edit
    _type(field, "-renamed")
    qtbot.wait(200)
    assert warned == [], "refused while still typing"
    field.editingFinished.emit()
    qtbot.wait(200)
    assert warned == [name] and renamed == []
    assert field.text() == name, "the name was not put back"
    assert (work / name / "project.json").is_file()
    assert not (work / (name + "-renamed")).exists()


# ---- 3. another project's name: the §S4.7 line, then the window --------------

def test_the_s47_line_shows_per_keystroke(fresh, qtbot):
    w, work, name = fresh
    _make_project(work, "Other")
    tab = w._tab_chart
    field = tab._manual_target_name_edit
    lbl = tab._manual_project_exists_lbl
    field.selectAll()
    _type(field, "Othe")
    assert lbl.isHidden()
    _type(field, "r")                        # no event loop turn in between
    assert not lbl.isHidden(), "the line did not come with the keystroke"
    assert lbl.text() == "You already have a project with this name."
    _type(field, "s")
    assert lbl.isHidden(), "the line stayed for a name nobody has"


def test_generate_asks_the_s47_window_before_anything_is_touched(
        fresh, qtbot, monkeypatch):
    w, work, name = fresh
    other = _make_project(work, "Other")
    run = other.current_run()
    (run.dir / f"{run.stem}.ti2").write_text("chart", encoding="utf-8")
    (run.dir / f"{run.stem}.ti3").write_text("measured", encoding="utf-8")
    tab = w._tab_chart
    field = tab._manual_target_name_edit
    field.selectAll()
    _type(field, "Other")

    def tree():
        return sorted((p.relative_to(work).as_posix(), p.stat().st_mtime_ns)
                      for p in work.rglob("*") if p.is_file())
    before = tree()
    from PyQt6.QtWidgets import QMessageBox
    seen = {}

    def _exec(box):
        seen["text"] = box.text()
        for b in box.buttons():
            if b.text() == "Cancel":
                b.click()
                return 0
        raise AssertionError([b.text() for b in box.buttons()])
    monkeypatch.setattr(QMessageBox, "exec", _exec)
    started = []
    monkeypatch.setattr(tab._creator, "generate",
                        lambda *a, **k: started.append(a))
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: started.append(a))
    tab._on_generate()
    qtbot.wait(200)
    assert "text" in seen, "Generate did not ask about the existing project"
    assert not started, "a build started after Cancel"
    assert tree() == before, "something on disk was touched"
    assert w._file_mgr.get_target_name() == name


# ---- 4. no project open: the location line follows the typing ----------------

def test_with_no_project_the_location_line_follows_typing(qapp, tmp_path,
                                                          qtbot):
    work = tmp_path / "work"
    work.mkdir()
    w = _window(qapp, work)
    try:
        bar, ctl = w._target_bar, w._target_ctl
        assert ctl.project_or_none() is None
        field = w._tab_chart._manual_target_name_edit
        field.clear()
        assert bar._location_full == ""
        _type(field, "My Printer")
        assert bar._location_full.endswith("My-Printer/runs/run1/"), (
            bar._location_full)
        _type(field, "2")
        assert bar._location_full.endswith("My-Printer2/runs/run1/")
        field.clear()
        assert bar._location_full == ""
        assert not (work / "My-Printer2").exists(), "nothing is made early"
    finally:
        w.close()


def test_no_kind_of_typing_is_a_target_change(measured, qtbot):
    """Keys, Backspace, a paste, an undo, a cut: every edit a person makes
    reaches the controller through `textEdited` first and emits nothing; a
    name the app writes into the field still emits `changed`, as it always
    did (tests/test_every_project_switch_still_tells_the_tabs.py)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    w, work, name = measured
    ctl = w._target_ctl
    field = w._tab_chart._manual_target_name_edit
    changed, typed = _Counter(), _Counter()
    ctl.changed.connect(changed)
    ctl.pending_name_changed.connect(typed)
    QTest.keyClicks(field, "ab")
    QTest.keyClick(field, Qt.Key.Key_Backspace)
    QApplication.clipboard().setText("-pasted")
    field.paste()
    field.undo()
    field.selectAll()
    field.cut()
    qtbot.wait(200)
    assert changed.n == 0, "an edit made by a person emitted `changed`"
    assert typed.n >= 5, "the location line did not follow the edits"
    field.setText(name)                      # the app writes the name back
    qtbot.wait(100)
    assert changed.n == 1, "a name the app wrote no longer tells the tabs"
