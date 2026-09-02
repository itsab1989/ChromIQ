"""One question, asked once — and the same ending whichever way it is answered.

The import door asks "Where should this measurement go?" and takes a name. For
a name that was NOT already a project it used to throw that answer away
(`return False  # a new project: the old path`) and let the caller's
`resolve_ti3` fallback ask for it again, in a second window that arrived empty,
called the project a "profile" and showed a literal `<name>` in the folder it
promised to use. The project was then made and never opened, so ChromIQ
finished by telling the person to load the project it had just made for them,
with `working_dir()` naming a folder that had never been created.

Driven on screen, 2026-09-02: three windows, `is_named() == False`,
`working_dir() == out/Printer_Paper_Type_Instr_2026-09-02_15-46` (absent), and
the bar reading "Load a profile project…". These tests are the same journey
without a screen.

They RUN the code. A string assertion cannot see a door that asks twice.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import ui.dialogs.name_prompt as name_prompt
import ui.dialogs.project_picker as project_picker
import ui.measurement_filing as filing
import ui.tabs.tab_profile as tp
import ui.ti2_loader as ti2
from core.settings import AppSettings


@pytest.fixture
def house(qapp, tmp_path):
    """A real MainWindow over a scratch working folder, with one real project
    in it and a measurement sitting outside every project."""
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
    shutil.copy2(src / "Demo-Report-Matrix.ti3", outside / "from-elsewhere.ti3")
    measurement = outside / "from-elsewhere.ti3"
    # Run 1 keeps its chart and loses its measurement, so filing into it is the
    # ordinary case and not "this run already holds one, make another" — a
    # different question, with a window of its own.
    (src / "Demo-Report-Matrix.ti3").unlink()

    s = AppSettings()
    s.set("custom_output_path", str(work))
    win = MainWindow(s)
    return win, measurement, work


def _answer_the_door(monkeypatch, name):
    """Answer the picker with "make a new project" and the name box with *name*.

    Returns the list the second name window would write into, so a test can ask
    whether anything asked again.
    """
    asked_again: list = []
    monkeypatch.setattr(project_picker, "choose_project",
                        lambda *a, **kw: project_picker.NEW_PROJECT)
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **kw: name)

    def _second_window(parent, path, ti1, tiffs, working_dir, subject=None,
                       is_measurement=False, prefill=""):
        asked_again.append(prefill)
        return None                       # the person cancels it

    monkeypatch.setattr(ti2, "_ask_profile_name", _second_window)
    return asked_again


def _load(win, measurement, monkeypatch):
    monkeypatch.setattr(tp, "open_file_dialog", lambda *a, **k: str(measurement))
    win._tab_profile._on_load_ti3()


# ---------------------------------------------------------------------------
# F2 — the answer is kept
# ---------------------------------------------------------------------------

def test_the_name_typed_at_the_door_is_the_name_that_is_used(house,
                                                             monkeypatch):
    win, measurement, work = house
    asked_again = _answer_the_door(monkeypatch, "Fresh-One")

    _load(win, measurement, monkeypatch)

    assert asked_again == [], (
        "the name was asked for a second time after the person had already "
        "given it at the door")
    assert (work / "Fresh-One" / "project.json").is_file(), (
        "the name that was typed did not become a project")
    assert (work / "Fresh-One" / "runs" / "run1" / "Fresh-One.ti3").is_file(), (
        "the measurement was not filed into the project's first run")


def test_the_original_file_is_not_moved_or_changed(house, monkeypatch):
    """The door promises "the file you picked stays where it is"."""
    win, measurement, work = house
    before = measurement.read_bytes()
    _answer_the_door(monkeypatch, "Fresh-One")

    _load(win, measurement, monkeypatch)

    assert measurement.is_file(), "the file the person picked was moved away"
    assert measurement.read_bytes() == before, "their own file was rewritten"


# ---------------------------------------------------------------------------
# F1 — the app is IN the project it just made
# ---------------------------------------------------------------------------

def test_a_new_project_is_the_project_the_app_is_then_in(house, monkeypatch):
    win, measurement, work = house
    _answer_the_door(monkeypatch, "Fresh-One")

    _load(win, measurement, monkeypatch)

    fm = win._file_mgr
    assert fm.is_named(), (
        "ChromIQ made a project and then said no project was open, so the bar "
        "tells the person to load the one it just made")
    assert Path(fm.working_dir()) == work / "Fresh-One", (
        f"the working folder is {fm.working_dir()}, not the project just made")
    assert Path(fm.working_dir()).is_dir(), (
        "working_dir() names a folder that does not exist — the same shape as "
        "the damage recorded at core/settings.py:786")


def test_the_tab_ends_up_pointing_at_the_filed_copy(house, monkeypatch):
    win, measurement, work = house
    _answer_the_door(monkeypatch, "Fresh-One")

    _load(win, measurement, monkeypatch)

    filed = win._tab_profile._ti3_path
    assert filed is not None, "the import filed nothing and said nothing"
    assert Path(filed) == work / "Fresh-One" / "runs" / "run1" / "Fresh-One.ti3", (
        f"the tab points at {filed}, not at the copy that was filed")


def test_the_bar_is_pointed_at_the_run_the_measurement_went_into(house,
                                                                 monkeypatch):
    win, measurement, work = house
    _answer_the_door(monkeypatch, "Fresh-One")

    _load(win, measurement, monkeypatch)

    ctl = win._tab_profile._target_ctl
    assert ctl.target.profile_run == "run1", (
        f"the bar is on {ctl.target.profile_run!r}, not the run the "
        "measurement was filed into")
    assert not ctl.target.is_verification(), (
        "an import from Build Profile left the app calling this a "
        "verification run, which disables the tab it was made from")


# ---------------------------------------------------------------------------
# The two doors agree
# ---------------------------------------------------------------------------

def test_both_answers_to_one_question_end_on_the_same_call(house, monkeypatch):
    """A name that IS a project and a name that is NOT must reach the same
    ending. They had two endings, and one of them had none at all."""
    win, measurement, work = house
    seen: list = []
    monkeypatch.setattr(filing, "finish_the_import",
                        lambda parent, ctl, run_id, filed, on_filed:
                        seen.append((run_id, Path(filed))))
    monkeypatch.setattr(project_picker, "choose_project",
                        lambda *a, **kw: project_picker.NEW_PROJECT)

    # …a name that is not a project yet
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **kw: "Fresh-One")
    _load(win, measurement, monkeypatch)
    assert seen, "the new-project answer reached no ending at all"
    new_run, new_filed = seen[-1]

    # …and the name of a project that already exists
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **kw: "Demo-Report-Matrix")
    monkeypatch.setattr(
        "ui.tabs.tab_chart.TabChart._build_run_picker",
        lambda self, peek: (None, ["run1"]))
    _load(win, measurement, monkeypatch)
    assert len(seen) == 2, "the existing-project answer reached no ending"
    old_run, old_filed = seen[-1]

    for run_id, filed in ((new_run, new_filed), (old_run, old_filed)):
        assert run_id, "the ending was reached without naming a run"
        assert work in filed.parents, (
            f"the copy handed back is outside the working folder: {filed}")
        assert filed.is_file(), f"the copy handed back is not on disk: {filed}"


# ---------------------------------------------------------------------------
# Cancel leaves nothing behind
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("where", ["picker", "name box"])
def test_cancelling_creates_no_project(house, monkeypatch, where):
    win, measurement, work = house
    before = sorted(p.name for p in work.iterdir())
    monkeypatch.setattr(
        project_picker, "choose_project",
        lambda *a, **kw: None if where == "picker" else project_picker.NEW_PROJECT)
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **kw: None)
    monkeypatch.setattr(ti2, "_ask_profile_name",
                        lambda *a, **kw: pytest.fail(
                            "a cancelled question was met by another question"))

    _load(win, measurement, monkeypatch)

    assert sorted(p.name for p in work.iterdir()) == before, (
        "cancelling left a project behind")
    assert win._tab_profile._ti3_path is None, (
        "cancelling loaded a measurement anyway")


# ---------------------------------------------------------------------------
# Nothing the user made is destroyed
# ---------------------------------------------------------------------------

def test_a_name_that_is_a_folder_but_not_a_project_still_asks_before_replacing(
        house, monkeypatch):
    """The ONE question the door cannot answer for the person: their own folder
    is already sitting there. It is still asked — and it arrives with the name
    they gave already in it, so it asks only what it alone can ask."""
    win, measurement, work = house
    taken = work / "Taken"
    taken.mkdir()
    (taken / "my-own-notes.txt").write_text("keep me\n", encoding="utf-8")

    asked_again = _answer_the_door(monkeypatch, "Taken")
    _load(win, measurement, monkeypatch)

    assert asked_again == ["Taken"], (
        f"the replace question arrived with {asked_again!r} in its name box; "
        "an empty box means the person's answer was thrown away again")
    assert (taken / "my-own-notes.txt").is_file(), (
        "the folder was replaced without anybody being asked")
    assert not (taken / "project.json").exists(), (
        "a project was written into the person's own folder in silence")


def test_a_project_of_that_name_never_reaches_the_create_route(house,
                                                               monkeypatch):
    """A name that IS a project takes the other branch, which files into a RUN
    and never touches what is there. The create route must not be reachable
    with the name of a project that exists — that is the one road on which
    something of the person's could be archived without them asking for it."""
    win, measurement, work = house
    went_new: list = []
    went_file: list = []
    monkeypatch.setattr(filing, "make_new_project_and_file",
                        lambda parent, name, *a, **kw: went_new.append(name) or True)
    monkeypatch.setattr(filing, "file_into_project",
                        lambda parent, name, *a, **kw: went_file.append(name) or True)
    monkeypatch.setattr(project_picker, "choose_project",
                        lambda *a, **kw: project_picker.NEW_PROJECT)
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **kw: "Demo-Report-Matrix")

    _load(win, measurement, monkeypatch)

    assert went_new == [], (
        f"the name of an existing project reached the create route: {went_new}")
    assert went_file == ["Demo-Report-Matrix"], (
        f"it did not reach the filing route either: {went_file}")
    assert (work / "Demo-Report-Matrix" / "runs" / "run1"
            / "Demo-Report-Matrix.ti2").is_file(), "the project lost its chart"
    assert (work / "Demo-Report-Matrix" / "project.json").is_file(), (
        "the project lost its manifest")
