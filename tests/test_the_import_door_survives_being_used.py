"""The import door, CALLED — not read.

Every existing test of this feature asserts on `inspect.getsource`, so the whole
suite stayed green while the door aborted the app on its first click and again
on its success path. These tests run the code. That is the entire point of the
file: a string assertion cannot see a `NameError`.
"""
from __future__ import annotations

import contextlib

from pathlib import Path

import pytest

import ui.dialogs.name_prompt as name_prompt
import ui.dialogs.project_picker as project_picker
import ui.tabs.tab_check_refine as tcr
from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.settings import AppSettings
from ui.measurement_target_bar import MeasurementTargetController


@pytest.fixture
def door(qapp, tmp_path, monkeypatch):
    """A real Check & Refine tab, a real controller, an empty working folder."""
    work = tmp_path / "work"
    work.mkdir()
    s = AppSettings()
    s.set("custom_output_path", str(work))
    tab = tcr.TabCheckRefine(ArgyllRunner(s), s)
    tab.set_target_controller(MeasurementTargetController(FileManager(s)))

    # A REAL measurement, not three lines of pretend: the tab reads it to name
    # the instrument and to find a chart, and a stub file makes it open a
    # warning box that has nothing to do with what is being tested.
    import shutil
    src = (Path(__file__).resolve().parents[1] / "demo-projects"
           / "Demo-Report-Matrix" / "runs" / "run1")
    loose = tmp_path / "loose"
    loose.mkdir()
    # The WHOLE set, the way it actually sits on somebody's desktop: the
    # measurement, its chart and its profile. Handing the tab a lone .ti3 makes
    # it open a "there is no chart for this" box that has nothing to do with
    # what is under test here.
    for name in ("Demo-Report-Matrix.ti3", "Demo-Report-Matrix.ti2",
                 "Demo-Report-Matrix.ti1", "Demo-Report-Matrix.icc"):
        shutil.copy2(src / name, loose / name)
    outside = loose / "Demo-Report-Matrix.ti3"
    monkeypatch.setattr(tcr, "open_file_dialog", lambda *a, **k: str(outside))
    return tab, outside, work


def _browse(tab) -> None:
    """Click the real Browse button, the way the person does."""
    from PyQt6.QtWidgets import QAbstractButton
    for b in tab.findChildren(QAbstractButton):
        if ".ti3" in (b.toolTip() or "") or ".ti3" in (b.accessibleName() or ""):
            b.click()
            return
    raise AssertionError("the Browse for .ti3 button was not found")


def test_browsing_for_an_outside_measurement_does_not_kill_the_app(
        door, monkeypatch):
    """With no projects yet the picker shows nothing and goes straight to the
    name box — the path that raised `NameError: _TAB_COLOR` and, inside a Qt
    slot, took the whole process down with `qFatal()`."""
    tab, outside, _work = door
    seen: dict = {}

    def _name_box(*a, **kw):
        seen.update(kw)
        return ""                     # the person cancels

    monkeypatch.setattr(name_prompt, "ask_for_project_name", _name_box)
    # Cancelling drops through to the pre-existing `resolve_ti3` fallback,
    # which opens its own "Copy Chart Files" question. Not what these two are
    # about, and it must not be left standing at teardown.
    monkeypatch.setattr("ui.ti2_loader.resolve_ti3", lambda *a, **kw: None)

    _browse(tab)                      # must not raise

    assert seen, "the name box was never reached"
    assert seen.get("accent") == tcr._TAB_COLOR, (
        "the name box must wear Check & Refine's own accent; it was asked for "
        f"{seen.get('accent')!r}")


def test_make_a_new_project_instead_does_not_kill_the_app(door, monkeypatch):
    """The second door into the same line: the picker's own third answer."""
    tab, _outside, _work = door
    seen: dict = {}
    monkeypatch.setattr(project_picker, "choose_project",
                        lambda *a, **kw: project_picker.NEW_PROJECT)
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **kw: seen.update(kw) or "")
    monkeypatch.setattr("ui.ti2_loader.resolve_ti3", lambda *a, **kw: None)
    _browse(tab)
    assert seen.get("accent") == tcr._TAB_COLOR


def test_filing_hands_the_copy_back_instead_of_poking_a_tab(qapp):
    """`file_into_project` used to call `parent.set_ti3_path(...)`, which only
    Build Profile has. Check & Refine inherited the call when it became the
    third door and aborted AFTER copying the file, making the run and writing
    the manifest. No caller may be allowed to omit the answer again."""
    from ui.measurement_filing import file_into_project
    with pytest.raises(TypeError, match="on_filed"):
        file_into_project(None, "x", Path("/nowhere.ti3"), None, None)


def test_check_refine_can_adopt_a_filed_copy(door):
    """The callback it hands the helper must actually point the tab at the
    copy, or filing succeeds on disk and shows nothing on screen."""
    tab, outside, _work = door
    tab._adopt_ti3(outside)
    assert tab.ti3_path == outside
    assert tab._ti3_edit.text() == str(outside)


def test_checking_in_place_does_not_leak_into_the_next_measurement(door):
    """It was an attribute set in two of four paths, so a later browse that
    took a different path kept the previous file's answer — and wrote its
    report loose beside the file instead of into the run."""
    tab, outside, _work = door
    tab._adopt_ti3(outside, in_place=True)
    assert tab._checking_in_place is True
    tab._adopt_ti3(outside)                      # a second, ordinary browse
    assert tab._checking_in_place is False


def test_cancel_means_nothing_happens(door, monkeypatch):
    """Basti, 2026-09-01, on the old behaviour: *"now that the door asks
    properly, a Cancel that leads to a different question reads oddly"*.

    Cancelling used to return False with no project open, which sent the caller
    down the pre-existing `resolve_ti3` route — so the answer to "where should
    this go?" was another window asking about copying chart files.
    """
    tab, outside, _work = door
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **kw: "")          # the person cancels

    fell_through = []
    monkeypatch.setattr("ui.ti2_loader.resolve_ti3",
                        lambda *a, **kw: fell_through.append(1))

    _browse(tab)

    assert not fell_through, (
        "cancelling the question fell through to the old route, which asks a "
        "second question about a project the person just declined to choose")
    assert tab.ti3_path is None, "cancelling loaded a measurement anyway"


# ---------------------------------------------------------------------------
# THE SUCCESS PATH, DRIVEN — the half the first version of this file missed
# ---------------------------------------------------------------------------
# The tests above call `_adopt_ti3` directly, so they guard the callee and not
# the wiring. Three mutations survived them: never calling `on_filed`, calling
# it with the OUTSIDE file instead of the copy, and the list branch dropping
# `on_filed=` — which is the exact path the crash was on. These two drive each
# door for real and then ask the tab what it is pointing at.

@contextlib.contextmanager
def _driving_the_windows(app, clicks=("choose", "file", "ok", "continue")):
    """Answer whatever modal is up, the way a person would, until none is.

    A CONTEXT MANAGER, because the first version left its timer running: with
    no modal up it re-armed itself two hundred times, so it outlived the test
    and clicked buttons in whatever dialog the NEXT test opened. It failed a
    different innocent file on each gate run — the splash tests once, the dial
    pictogram tests the next time — which is the signature of exactly this.
    """
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QAbstractButton, QApplication, QListWidget

    state = {"n": 0, "stop": False}

    def tick():
        state["n"] += 1
        if state["stop"]:
            return
        dlg = QApplication.activeModalWidget()
        if dlg is None:
            if state["n"] < 200:
                QTimer.singleShot(10, tick)
            return
        for lst in dlg.findChildren(QListWidget):
            if lst.count():
                lst.setCurrentRow(0)
        # THE RUN PICKER: choose a run that already has a chart. "A new run"
        # is the first entry and would leave nothing to check against, which
        # is a different question from the one under test here.
        from PyQt6.QtWidgets import QComboBox
        for combo in dlg.findChildren(QComboBox):
            for i in range(combo.count()):
                if str(combo.itemData(i) or "").startswith("run"):
                    combo.setCurrentIndex(i)
                    break
        for b in dlg.findChildren(QAbstractButton):
            t = (b.text() or "").lower().replace("&", "")
            if any(k in t for k in clicks):
                b.click()
                QTimer.singleShot(10, tick)
                return
        dlg.reject()
        QTimer.singleShot(10, tick)

    QTimer.singleShot(0, tick)
    try:
        yield
    finally:
        state["stop"] = True


@pytest.fixture
def house(qapp, tmp_path, monkeypatch):
    """A real MainWindow, a real project in a scratch working folder, and a
    measurement sitting outside it."""
    import shutil
    from ui.main_window import MainWindow

    repo = Path(__file__).resolve().parents[1]
    work = tmp_path / "work"
    work.mkdir()
    shutil.copytree(repo / "demo-projects" / "Demo-Report-Matrix",
                    work / "Demo-Report-Matrix")

    outside = tmp_path / "outside"
    outside.mkdir()
    src = work / "Demo-Report-Matrix" / "runs" / "run1"
    for suffix in (".ti3", ".ti2", ".ti1", ".icc"):
        shutil.copy2(src / f"Demo-Report-Matrix{suffix}",
                     outside / f"from-elsewhere{suffix}")
    measurement = outside / "from-elsewhere.ti3"
    # Run 1 keeps its chart and loses its measurement, so filing into it is the
    # ordinary case and not "this run already holds one, make another".
    (src / "Demo-Report-Matrix.ti3").unlink()

    s = AppSettings()
    s.set("custom_output_path", str(work))
    win = MainWindow(s)
    return win, measurement, work


def test_check_refine_ends_up_pointing_at_the_filed_copy(house, qapp,
                                                         monkeypatch):
    """Filed means filed AND shown. The helper used to hand the copy to Build
    Profile's API, which this tab does not have, so the file was copied, the
    run made and the manifest written — and then the app died."""
    win, measurement, work = house
    tab = win._tab_check
    monkeypatch.setattr(tcr, "open_file_dialog", lambda *a, **k: str(measurement))

    with _driving_the_windows(qapp):
        tab._on_browse_ti3()
        for _ in range(50):
            qapp.processEvents()

    assert tab.ti3_path is not None, "the door filed nothing and said nothing"
    assert tab.ti3_path != measurement, (
        "the tab is pointing at the file OUTSIDE the project, not at the copy")
    assert work in tab.ti3_path.parents, (
        f"the tab points outside the working folder: {tab.ti3_path}")
    assert tab.ti3_path.is_file(), "the copy it points at is not on disk"


def test_build_profile_ends_up_pointing_at_the_filed_copy(house, qapp,
                                                          monkeypatch):
    """The same door, in the tab it was written for. Its own success path was
    never driven either, so a change to the shared helper could break it in
    exactly the way Check & Refine broke and nothing would say so."""
    import ui.tabs.tab_profile as tp

    win, measurement, work = house
    tab = win._tab_profile
    monkeypatch.setattr(tp, "open_file_dialog", lambda *a, **k: str(measurement))

    with _driving_the_windows(qapp):
        tab._on_load_ti3()
        for _ in range(50):
            qapp.processEvents()

    filed = tab.ti3_path if hasattr(tab, "ti3_path") else tab._ti3_path
    assert filed is not None, "the door filed nothing and said nothing"
    assert filed != measurement, (
        "the tab is pointing at the file OUTSIDE the project, not at the copy")
    assert work in Path(filed).parents, (
        f"the tab points outside the working folder: {filed}")


# ---------------------------------------------------------------------------
# ROUND 2 — what the second challenge found, and what must stay fixed
# ---------------------------------------------------------------------------

def test_checking_in_place_tells_nobody_else(door):
    """The promise is "nothing has been copied and no project has been made".

    These two signals reach Build Profile and Print, which find the sibling
    `.ti2` and offer to IMPORT THE SET into the working folder — so the log
    made the promise and the very next window broke it, and one OK created a
    whole project with the in-place flag cleared underneath it.
    """
    tab, outside, _work = door
    heard: list = []
    tab.ti3_selected.connect(lambda p: heard.append(("ti3", p)))
    tab.ti2_found.connect(lambda p: heard.append(("ti2", p)))

    tab._adopt_ti3(outside, in_place=True)
    assert heard == [], (
        f"checking in place broadcast the file to the other tabs: {heard}")

    # …and an ordinary load still does, or the tabs stop following each other.
    tab._adopt_ti3(outside)
    assert [k for k, _ in heard] == ["ti2", "ti3"], (
        f"an ordinary load stopped telling the other tabs: {heard}")


def test_a_folder_whose_name_does_not_survive_sanitising_is_still_that_folder(
        qapp, tmp_path, monkeypatch):
    """"Demo-Report-Matrix copy" — Finder's Duplicate, an unzipped hand-off, a
    Dropbox conflicted copy. The picker listed it and handed back its name; the
    filing threw that away and re-derived a SANITISED path, so ChromIQ made an
    empty "…-copy" project, switched to it, and refused with "has no chart in
    it yet" about the row that had just said "2 runs, 1 verification".
    """
    import shutil

    import ui.measurement_filing as mf

    work = tmp_path / "work"
    work.mkdir()
    repo = Path(__file__).resolve().parents[1]
    listed = "Demo-Report-Matrix copy"
    shutil.copytree(repo / "demo-projects" / "Demo-Report-Matrix",
                    work / listed)

    s = AppSettings()
    s.set("custom_output_path", str(work))
    fm = FileManager(s)

    # The premise: the sanitised twin is NOT this folder.
    assert fm.resolved_root_for_name(listed).name != listed

    # What the filing is handed when the picker is answered.
    seen: dict = {}
    monkeypatch.setattr(mf, "file_into_project",
                        lambda *a, **kw: seen.update(kw) or True)
    monkeypatch.setattr("ui.dialogs.project_picker.choose_project",
                        lambda *a, **kw: listed)

    class _Parent:
        _target_ctl = type("C", (), {"_fm": fm})()

    mf.offer_import_into_a_project(_Parent(), work / "x.ti3",
                                   accent="#000", on_filed=lambda p: None)

    assert seen.get("root") is not None, (
        "the picker's own folder was not passed through; the path is being "
        "re-derived and will be sanitised")
    assert Path(seen["root"]).name == listed, (
        f"the measurement would go to {Path(seen['root']).name!r}, not to the "
        f"folder that was picked, {listed!r}")


def test_the_bar_is_not_pointed_at_a_run_that_may_be_undone():
    """A refused import promised "nothing has been changed" while the bar read
    "Run 3 (overwrite)" for a run created and deleted in the same breath."""
    import inspect

    from ui.measurement_filing import file_into_project
    src = inspect.getsource(file_into_project)
    src = "\n".join(l for l in src.splitlines()
                    if not l.lstrip().startswith("#"))
    # the CALL, not the `def` line, which also contains the name
    assert src.index("verdict = assess(") < src.index(
        "\n    _point_the_bar_at_the_run()"), (
        "the bar is pointed at the run before the file has been judged, so a "
        "refusal leaves it naming a run that no longer exists")
