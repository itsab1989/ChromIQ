"""Round 2 of the import-door review: what the app SAYS, and about which run.

The commit that made both doors end on one call was reviewed against a
side-by-side table of `is_named`, `working_dir`, the Location line and the run
combo — and no row asked WHAT EITHER DOOR SAID. That is the row these tests
are. Driven first, on screen, 2026-09-02:

* the same loose chart and a 40-of-240-patch measurement of it: the
  existing-project door said "Filed — and it is a partial measurement" and the
  new-project door said nothing at all, while the `.ti2` it would have been
  judged against sat in the run it had just made (T1-G);
* while that notice was on screen the bar behind it read **Run 4** and the file
  had gone into **run 5** (T1-H);
* a truncated `project.json` — `save_manifest` writes non-atomically, so a short
  write is an ordinary accident — reported a successful open, and the bar said
  "Load a profile project…" and "Location being edited: …/runs/run1/" at the
  same time, with no window anywhere (T1-A);
* a project folder that went away between being made and being opened left an
  orphan holding the measurement and no `project.json`, announced by a
  `log.warning` and nothing else (T1-B);
* both of those then cleared the bar's run and verification id under a comment
  saying they left the bar alone (T1-C);
* and the one window that still opens for a plain folder arrived asserting, in
  red, that the folder was already a project (T1-D).

Evidence: `~/Desktop/beta7/review/FIX-IMPORT/ROUND2/shots/`.

THEY RUN THE CODE. Only the windows are stubbed, and they are stubbed by
recording what they were given — a fake that re-implements the decision would
be testing itself.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import ui.dialogs.name_prompt as name_prompt
import ui.dialogs.project_picker as project_picker
import ui.measurement_filing as filing
import ui.tabs.tab_profile as tp
import ui.ti2_loader as ti2
from core.settings import AppSettings


# ---------------------------------------------------------------------------
# A house with a real MainWindow, a real project, and a loose chart + its
# measurement sitting outside every project.
# ---------------------------------------------------------------------------

@pytest.fixture
def house(qapp, tmp_path):
    import shutil
    from ui.main_window import MainWindow

    repo = Path(__file__).resolve().parents[1]
    work = tmp_path / "work"
    work.mkdir()
    shutil.copytree(repo / "demo-projects" / "Demo-Report-Matrix",
                    work / "Demo-Report-Matrix")

    src = work / "Demo-Report-Matrix" / "runs" / "run1"
    loose = tmp_path / "outside"
    loose.mkdir()
    # THE CHART TRAVELS WITH IT, which is what makes the two doors comparable:
    # the new-project door imports that `.ti2` as the new run's chart, so the
    # file it files really does have a chart to be judged against.
    shutil.copy2(next(src.glob("*.ti2")), loose / "a-loose-chart.ti2")
    full = (src / "Demo-Report-Matrix.ti3").read_text(
        encoding="utf-8", errors="replace")
    (loose / "a-loose-chart.ti3").write_text(full, encoding="utf-8")
    # Run 1 keeps its chart and loses its measurement, so filing into it is the
    # ordinary case rather than "that run already has one".
    (src / "Demo-Report-Matrix.ti3").unlink()

    s = AppSettings()
    s.set("custom_output_path", str(work))
    win = MainWindow(s)
    return win, loose / "a-loose-chart.ti3", work


def keep_only(ti3: Path, n: int) -> None:
    """Cut *ti3* down to *n* readings, the way stopping part way through does."""
    lines = ti3.read_text(encoding="utf-8", errors="replace").splitlines(True)
    a = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    b = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
    head = re.sub(r"NUMBER_OF_SETS\s+\d+", f"NUMBER_OF_SETS {n}",
                  "".join(lines[:a + 1]))
    ti3.write_text(head + "".join(lines[a + 1:b][:n]) + "".join(lines[b:]),
                   encoding="utf-8")


def shrink_chart(ti2: Path, n: int) -> None:
    """Cut the CHART down, so the measurement holds more readings than it has
    patches — which `assess` refuses as a measurement of something else."""
    keep_only(ti2, n)


def win_ctl(house):
    return house[0]._tab_profile._target_ctl


class Said:
    """Every window the import put on screen, and the bar behind each one."""

    def __init__(self, ctl):
        self.ctl = ctl
        self.windows: list[dict] = []

    def install(self, monkeypatch):
        recorder = self

        class _Fake:
            def __init__(self, title, body, parent=None, **kw):
                recorder.windows.append({
                    "title": title, "body": body,
                    "run_behind": getattr(recorder.ctl.target, "profile_run",
                                          None),
                })

            def exec(self):
                return 0

        monkeypatch.setattr(filing, "InfoDialog", _Fake)
        return self

    def titles(self) -> list[str]:
        return [w["title"] for w in self.windows]

    def one(self, fragment: str) -> dict:
        hits = [w for w in self.windows if fragment in w["title"]]
        assert len(hits) == 1, (fragment, self.titles())
        return hits[0]

    def none(self, fragment: str) -> bool:
        return not any(fragment in w["title"] for w in self.windows)


def _new_project_door(monkeypatch, name: str):
    monkeypatch.setattr(project_picker, "choose_project",
                        lambda *a, **kw: project_picker.NEW_PROJECT)
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **kw: name)
    monkeypatch.setattr(ti2, "_ask_profile_name",
                        lambda *a, **kw: pytest.fail(
                            "the name was asked for a second time"))


def _existing_project_door(monkeypatch, name: str, run_id: str = ""):
    monkeypatch.setattr(project_picker, "choose_project", lambda *a, **kw: name)
    monkeypatch.setattr("ui.tabs.tab_chart.TabChart._build_run_picker",
                        lambda self, peek: (None, [run_id]))


def _load(win, measurement, monkeypatch):
    # THE ONE WINDOW THAT IS NOT PART OF THE IMPORT. Opening the project points
    # Print Chart at the run's `.ti2`, and a chart already inside a project
    # raises "Load Test Session" — a question about that tab, asked on every
    # open, before and after this change. Answered "Continue" (use the files as
    # they are), which is what the drives answered on screen.
    monkeypatch.setattr(ti2, "_handle_inside",
                        lambda parent, ti2_path, working_dir:
                        (ti2_path, ti2._related_files(ti2_path)[1]))
    monkeypatch.setattr(tp, "open_file_dialog", lambda *a, **k: str(measurement))
    win._tab_profile._on_load_ti3()


def _no_project_above_the_copy(monkeypatch):
    """The project folder goes away between being made and being opened.

    Narrowed to the `.ti3` the import just filed: patching `_project_root_for`
    outright also told Print Chart that the chart inside the project was
    outside it, which opened an unrelated window and would have made this test
    prove something else.
    """
    real = ti2._project_root_for

    def _gone(path, working_dir):
        if Path(path).suffix == ".ti3":
            return None
        return real(path, working_dir)

    monkeypatch.setattr(ti2, "_project_root_for", _gone)


PARTIAL = "partial measurement"
REFUSED = "does not belong to that chart"
NOT_OPENED = "could not be opened"


# ---------------------------------------------------------------------------
# T1-G — the two doors say the same thing about the same file
# ---------------------------------------------------------------------------

def test_the_new_project_door_says_a_partial_measurement_is_partial(house,
                                                                    monkeypatch):
    """The headline. It imported the chart and then never judged the file."""
    win, measurement, work = house
    keep_only(measurement, 40)
    said = Said(win._tab_profile._target_ctl).install(monkeypatch)
    _new_project_door(monkeypatch, "Fresh-One")

    _load(win, measurement, monkeypatch)

    assert (work / "Fresh-One" / "runs" / "run1" / "Fresh-One.ti3").is_file(), \
        "the measurement was not filed at all"
    w = said.one(PARTIAL)
    assert "40" in w["body"], f"the counts are not stated: {w['body'][:120]}"


def test_the_existing_project_door_says_the_same_thing(house, monkeypatch):
    """The other door, the same file, the same sentence — the comparison the
    original review's table had no row for."""
    win, measurement, work = house
    keep_only(measurement, 40)
    said = Said(win._tab_profile._target_ctl).install(monkeypatch)
    _existing_project_door(monkeypatch, "Demo-Report-Matrix", "run1")

    _load(win, measurement, monkeypatch)

    w = said.one(PARTIAL)
    assert "40" in w["body"], f"the counts are not stated: {w['body'][:120]}"


def test_a_complete_measurement_is_filed_without_a_word(house, monkeypatch):
    """The notice is about a partial file, not about every import."""
    win, measurement, work = house
    said = Said(win._tab_profile._target_ctl).install(monkeypatch)
    _new_project_door(monkeypatch, "Fresh-One")

    _load(win, measurement, monkeypatch)

    assert said.none(PARTIAL), (
        f"a complete measurement was called partial: {said.titles()}")


def test_the_new_project_door_refuses_a_measurement_of_another_chart(
        house, monkeypatch):
    """§I.9: *a measurement whose patches do not line up with the chart is
    refused with an explanation*. This door asked nothing and filed everything.

    And it is refused BEFORE anything is written, which is what makes the
    window's own "nothing has been changed" true on this door."""
    win, measurement, work = house
    shrink_chart(measurement.with_suffix(".ti2"), 100)
    said = Said(win._tab_profile._target_ctl).install(monkeypatch)
    _new_project_door(monkeypatch, "Fresh-One")
    before = sorted(p.name for p in work.iterdir())

    _load(win, measurement, monkeypatch)

    said.one(REFUSED)
    assert sorted(p.name for p in work.iterdir()) == before, (
        "a project was created for a measurement the app then refused, under a "
        "window promising nothing had been changed")


def test_the_sentence_about_the_filed_file_is_written_in_exactly_one_place(
        house, monkeypatch):
    """The structural half of T1-G: the doors cannot say different things if
    only one of them can say anything.

    A door that grows its own copy of this notice is how the two came apart in
    the first place, and the previous fix's own stated purpose was that they
    could not."""
    import inspect
    for door in (filing.file_into_project, filing.make_new_project_and_file):
        src = inspect.getsource(door)
        assert PARTIAL not in src, (
            f"{door.__name__} writes its own version of the partial notice; "
            "it belongs in finish_the_import, where both doors meet")
    assert PARTIAL in inspect.getsource(filing.say_what_was_filed)
    assert "say_what_was_filed" in inspect.getsource(filing.finish_the_import)


def test_the_two_doors_judge_the_same_chart(house, monkeypatch):
    """`chart_beside` and `chart_the_copy_will_be_judged_against` must name the
    same file for the same import, or the judging and the reporting disagree."""
    win, measurement, work = house
    _new_project_door(monkeypatch, "Fresh-One")
    Said(win._tab_profile._target_ctl).install(monkeypatch)

    before = ti2.chart_beside(measurement)
    _load(win, measurement, monkeypatch)
    filed = work / "Fresh-One" / "runs" / "run1" / "Fresh-One.ti3"
    after = filing.chart_the_copy_will_be_judged_against(filed)

    assert before is not None and after is not None
    assert before.read_bytes() == after.read_bytes(), (
        "the chart the import was judged against is not the chart that was "
        "filed beside it")


# ---------------------------------------------------------------------------
# T1-H — the bar names the run the file went into, behind the window
# ---------------------------------------------------------------------------

def test_the_bar_names_the_run_the_file_went_into_behind_the_notice(
        house, monkeypatch):
    """Recorded as "a cosmetic reorder". It was not: the bar behind that window
    named a DIFFERENT run from the one the file had gone into."""
    win, measurement, work = house
    keep_only(measurement, 40)
    ctl = win._tab_profile._target_ctl
    said = Said(ctl).install(monkeypatch)
    _existing_project_door(monkeypatch, "Demo-Report-Matrix", "run1")

    _load(win, measurement, monkeypatch)

    w = said.one(PARTIAL)
    assert w["run_behind"] == ctl.target.profile_run, (
        f"the bar read {w['run_behind']!r} while the notice was on screen and "
        f"{ctl.target.profile_run!r} after it: the window named one run and "
        "the bar behind it named another")
    filed = Path(win._tab_profile._ti3_path)
    assert filed.parent.name == ctl.target.profile_run, (
        f"the file went into {filed.parent.name} and the bar says "
        f"{ctl.target.profile_run}")


# ---------------------------------------------------------------------------
# T1-A — a manifest that will not read is a failed open, not a success
# ---------------------------------------------------------------------------

def _truncate_every_manifest_on_creation(monkeypatch):
    """`save_manifest` writes non-atomically; this is that short write."""
    import core.file_manager as fmod
    real = fmod.Project.create

    @classmethod
    def _short(cls, root, name, *a, **kw):
        proj = real.__func__(cls, root, name, *a, **kw)
        m = Path(root) / "project.json"
        m.write_bytes(m.read_bytes()[:60])
        return proj

    monkeypatch.setattr(fmod.Project, "create", _short)


def test_a_truncated_manifest_is_not_reported_as_a_successful_open(
        house, monkeypatch):
    win, measurement, work = house
    _truncate_every_manifest_on_creation(monkeypatch)
    said = Said(win._tab_profile._target_ctl).install(monkeypatch)
    _new_project_door(monkeypatch, "Broken-One")

    _load(win, measurement, monkeypatch)

    w = said.one(NOT_OPENED)
    assert "Broken-One" in w["body"], (
        "the window does not say where the file is, which is the one thing the "
        f"person cannot work out: {w['body'][:160]}")


def test_a_truncated_manifest_leaves_the_app_where_it_was(house, monkeypatch):
    """The bar said "Load a profile project…" and "Location being edited:
    out/Broken-One/runs/run1/" AT THE SAME TIME. Either it is open or it is
    not; a window explaining a half-open state is worth less than not entering
    one."""
    win, measurement, work = house
    _truncate_every_manifest_on_creation(monkeypatch)
    Said(win._tab_profile._target_ctl).install(monkeypatch)
    _new_project_door(monkeypatch, "Broken-One")

    _load(win, measurement, monkeypatch)

    fm = win._file_mgr
    if fm.is_named():
        assert Path(fm.working_dir()) != work / "Broken-One", (
            "the app reports itself inside a project whose manifest it cannot "
            "read")


def test_a_manifest_that_parses_and_will_not_load_is_also_a_failed_open(
        house, monkeypatch):
    """The backstop behind the parse check, and it has its own hazard.

    A manifest that is valid JSON and a dict gets past `_the_manifest_parses`
    and still fails `Project.load` — `{"schema_version": "x"}` raises
    `TypeError` out of a version comparison, `[]` raises `AttributeError`.
    Neither is an `OSError` or a `ValueError`, so an unguarded backstop would
    take the app down from inside a Qt slot, which is the very fault the
    importer's own comment records. It must end in a sentence."""
    import core.file_manager as fmod
    real = fmod.Project.create

    @classmethod
    def _bad_schema(cls, root, name, *a, **kw):
        proj = real.__func__(cls, root, name, *a, **kw)
        (Path(root) / "project.json").write_text(
            '{"schema_version": "x"}', encoding="utf-8")
        return proj

    monkeypatch.setattr(fmod.Project, "create", _bad_schema)
    said = Said(win_ctl(house)).install(monkeypatch)
    _new_project_door(monkeypatch, "Odd-One")
    win, measurement, work = house

    _load(win, measurement, monkeypatch)      # must not raise

    w = said.one(NOT_OPENED)
    assert "Odd-One" in w["body"], w["body"][:160]


def test_the_measurement_is_still_handed_back_when_the_open_fails(
        house, monkeypatch):
    """"Nothing the user made is deleted" cuts both ways: the copy is real, so
    the tab is pointed at it rather than left showing the old file."""
    win, measurement, work = house
    _truncate_every_manifest_on_creation(monkeypatch)
    Said(win._tab_profile._target_ctl).install(monkeypatch)
    _new_project_door(monkeypatch, "Broken-One")

    _load(win, measurement, monkeypatch)

    filed = work / "Broken-One" / "runs" / "run1" / "Broken-One.ti3"
    assert filed.is_file(), "the copy is not on disk"
    assert Path(win._tab_profile._ti3_path) == filed, (
        "the copy was made and then dropped on the floor")


# ---------------------------------------------------------------------------
# T1-B — an orphan folder says where it is
# ---------------------------------------------------------------------------

def test_a_copy_with_no_project_above_it_says_where_it_is(house, monkeypatch):
    """The whole of what the person used to get was a `log.warning`, and the
    folder left behind holds the measurement and no `project.json`, so Open
    Project can never find it again."""
    win, measurement, work = house
    _no_project_above_the_copy(monkeypatch)
    said = Said(win._tab_profile._target_ctl).install(monkeypatch)
    _new_project_door(monkeypatch, "Orphan-One")

    _load(win, measurement, monkeypatch)

    w = said.one(NOT_OPENED)
    assert "Orphan-One" in w["body"], (
        f"the folder is not named: {w['body'][:160]}")
    assert Path(win._tab_profile._ti3_path).is_file(), \
        "the copy was not handed back"


# ---------------------------------------------------------------------------
# T1-C — "leave the bar alone" is now true
# ---------------------------------------------------------------------------

def test_an_import_that_never_opened_a_project_leaves_the_bar_alone(
        house, monkeypatch):
    """`finish_the_import(ctl, "", …)` ran `set_run_type`, `set_verification_id`
    and `set_profile_run("")` under a comment saying it left the bar alone —
    clearing the run somebody was on because an unrelated import failed."""
    win, measurement, work = house
    ctl = win._tab_profile._target_ctl
    _no_project_above_the_copy(monkeypatch)
    Said(ctl).install(monkeypatch)
    _new_project_door(monkeypatch, "Orphan-One")
    before = (ctl.target.profile_run, ctl.target.verification_id,
              ctl.target.run_type)

    _load(win, measurement, monkeypatch)

    assert (ctl.target.profile_run, ctl.target.verification_id,
            ctl.target.run_type) == before, (
        "the bar was changed by an import that never reached a project")


def test_no_failure_path_calls_the_shared_ending(house):
    """The structural half: the shared ending points the bar, so a path with no
    run to point it at must not be routed through it at all."""
    import inspect
    src = inspect.getsource(filing.make_new_project_and_file)
    for call in re.findall(r'finish_the_import\([^)]*\)', src):
        assert '""' not in call, (
            "a failure path is still routed through the ending that points the "
            f"bar: {call}")


# ---------------------------------------------------------------------------
# T1-D — a folder is not a project
# ---------------------------------------------------------------------------

def test_a_plain_folder_is_not_a_project(tmp_path):
    from core.file_manager import is_a_project
    plain = tmp_path / "Not-A-Project"
    plain.mkdir()
    (plain / "my-own-notes.txt").write_text("mine\n", encoding="utf-8")
    assert not is_a_project(plain), "a folder of notes was called a project"

    real = tmp_path / "Real"
    real.mkdir()
    (real / "project.json").write_text("{}", encoding="utf-8")
    assert is_a_project(real), "a folder with a manifest was not called one"

    assert not is_a_project(tmp_path / "nothing-here")
    assert not is_a_project(None)


@pytest.mark.parametrize("loader", ["ui.ti2_loader", "ui.txt_loader"])
def test_the_collision_line_only_claims_a_project_when_there_is_one(loader):
    """The window opens for a plain folder BECAUSE it is not a project, and it
    arrived asserting that it was one, in red, before anything was typed."""
    import importlib
    import inspect
    mod = importlib.import_module(loader)
    src = inspect.getsource(mod)
    marker = "is already a project. Choose a different name"
    assert marker in src, f"{loader} no longer has the project sentence"
    where = src.index(marker)
    guard = src[max(0, where - 900):where]
    assert "is_a_project(" in guard, (
        f"{loader} shows “is already a project” without asking whether it is "
        "one; `.exists()` is true of any folder")


def test_the_folder_line_and_the_project_line_are_different_sentences():
    from workflow import measurement_messages as M
    folder = M.folder_taken_line("X")
    assert "not a ChromIQ project" in folder, folder
    assert "X" in folder


@pytest.mark.parametrize("fn,other", [
    ("_say_the_replace_failed", "M_IMPORT_REPLACE_FOLDER_FAILED"),
])
@pytest.mark.parametrize("loader", ["ui.ti2_loader", "ui.txt_loader"])
def test_the_replace_windows_have_a_folder_variant(loader, fn, other):
    """"The existing project could not be moved aside", about a read-only
    folder holding one text file."""
    import importlib
    import inspect
    mod = importlib.import_module(loader)
    src = inspect.getsource(getattr(mod, fn))
    assert other in src and "is_a_project(" in src, (
        f"{loader}.{fn} names a project whatever it was actually given")


# ---------------------------------------------------------------------------
# T1-I — the Check & Refine fallback still holds the original fault, and is
# unreachable. Pinned, because dead code that contains a fixed bug is a trap.
# ---------------------------------------------------------------------------

def test_the_check_and_refine_fallback_cannot_be_reached(house):
    """Its `else: resolve_ti3(...)` branch creates a project and never opens it
    — F1 and F2 verbatim. It is dead in the shipped app for two reasons, and
    both are pinned here: if either changes, that branch becomes live and needs
    the fix the doors got."""
    import inspect
    win, _measurement, _work = house
    assert win._tab_chart is not None, (
        "MainWindow no longer always builds a Create Chart tab, so "
        "open_the_project can return NO_MACHINERY in the shipped app")
    assert getattr(win._tab_check, "_target_ctl", None) is not None, (
        "Check & Refine is no longer given a target controller, so its import "
        "door falls through to a branch that creates a project without "
        "opening it")
    src = inspect.getsource(win._tab_check._on_browse_ti3)
    assert "resolve_ti3(self, _picked, self._settings)" in src, (
        "the fallback has changed; re-read T1-I before trusting this test")
