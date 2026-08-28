"""§S4.7 — typing the name of a project you already have.

Knut, 2026-08-27: he started ChromIQ, typed "test" (a project he already had),
picked a preset, and the chart was built straight into that project. *"there is
no warning message that this project already exists, with choice to overwrite or
cancel, and message to change to a different name … Nothing shall ever be lost
and user shall always be notified if there is a risk of overwriting a project."*

Nothing in the model governed it: §4 governs what a RUN holds, not which PROJECT
a typed name lands on — and §4's own question was asked BEFORE the name was
applied, so when a name adopted a different project the question was answered
about the run the app happened to be on.

Three things are proved here:

1.  `peek_project` reads a project WITHOUT opening it — no manifest is rewritten,
    nothing is migrated, nothing is created. This is asked while the user is
    only considering a name, so it must not touch their files.
2.  The gate fires for a project that holds something, stays quiet for one that
    is empty, and stays quiet for the project already open.
3.  Every button leads where it says, Cancel included — and Cancel leaves the
    disk exactly as it was.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from core.file_manager import FileManager, Project, peek_project   # noqa: E402


# ---------------------------------------------------------------------------
# 1. peek_project — read-only, and right about what is there
# ---------------------------------------------------------------------------

def _project(tmp_path, name="test"):
    root = tmp_path / name
    proj = Project.create(root, name)
    return proj, proj.current_run()


def test_a_name_nobody_has_used_is_not_a_collision(tmp_path):
    assert peek_project(tmp_path / "nothing-here").exists is False
    assert peek_project(None).exists is False


def test_an_empty_project_exists_but_holds_nothing(tmp_path):
    _project(tmp_path)
    pk = peek_project(tmp_path / "test")
    assert pk.exists
    assert not pk.holds_anything, "an empty project must not raise a window"
    assert pk.run_number == "1"


def test_a_chart_alone_already_counts_as_something_to_lose(tmp_path):
    """Knut's exact case. §4 says a chart-only run raises no window of ITS own —
    which is precisely why this question had to be a different one."""
    _proj, run = _project(tmp_path)
    (run.dir / f"{run.stem}.ti2").write_text("chart")
    pk = peek_project(tmp_path / "test")
    assert (pk.chart, pk.measurement, pk.profile) == (True, False, False)
    assert pk.holds_anything


def test_it_sees_a_measurement_a_profile_and_dated_verifications(tmp_path):
    _proj, run = _project(tmp_path)
    (run.dir / f"{run.stem}.ti2").write_text("chart")
    (run.dir / f"{run.stem}.ti3").write_text("measured")
    (run.dir / f"{run.stem}.icc").write_text("profile")
    for stamp in ("2026-03-04_101122", "2026-06-19_144005"):
        (run.verifications_dir / stamp).mkdir(parents=True)
    pk = peek_project(tmp_path / "test")
    assert (pk.chart, pk.measurement, pk.profile) == (True, True, True)
    assert pk.verifications == 2


def test_a_seeded_preconditioning_copy_is_not_this_runs_own_work(tmp_path):
    """`preconditioning.*` is copied in from the PARENT run when a refinement
    run is made. Counting it would make a brand-new, untouched run look like a
    finished one and put a window in front of somebody for nothing."""
    _proj, run = _project(tmp_path)
    (run.dir / "preconditioning.ti3").write_text("parent's")
    (run.dir / "preconditioning.icc").write_text("parent's")
    pk = peek_project(tmp_path / "test")
    assert not pk.holds_anything


def test_peeking_does_not_migrate_or_write_anything(tmp_path):
    """The question must not rearrange the folder it is asking about.

    `Project.load` migrates in place — that is how a pre-#127 project is brought
    up to the current layout — so peeking must not go through it. Proved with a
    schema-1 manifest: after peeking, the bytes on disk are identical.
    """
    root = tmp_path / "old-project"
    # THE REAL v1 LAYOUT. v1 HAD `runs/runN/` — what #127 added was the
    # `reports/`, `exports/` and `cache/` sub-folders INSIDE each run
    # (`tests/test_legacy_migration.py` states this, and `_migrate_v1_to_v2`
    # only moves files within a run folder). Believing otherwise made every
    # pre-#127 project read as EMPTY, so no window appeared and it was adopted
    # in silence — Knut's original report, unfixed for every 3.13-era project.
    run = root / "runs" / "run1"
    run.mkdir(parents=True)
    manifest = root / "project.json"
    manifest.write_text(json.dumps(
        {"schema_version": 1, "target_name": "old-project",
         "current_run": "run1", "runs": ["run1"]}), encoding="utf-8")
    (run / "old-project.ti2").write_text("a v1 chart")
    (run / "old-project.ti3").write_text("a v1 measurement")
    before = {p.relative_to(root).as_posix(): p.read_bytes()
              for p in root.rglob("*") if p.is_file()}

    pk = peek_project(root)
    assert pk.exists and pk.chart and pk.measurement, \
        "a pre-#127 project read as empty — the window would never appear"

    after = {p.relative_to(root).as_posix(): p.read_bytes()
             for p in root.rglob("*") if p.is_file()}
    assert after == before, "peeking changed the project on disk"


def test_an_unreadable_manifest_is_treated_as_occupied(tmp_path):
    """The honest answer to "I cannot read it" is "something is there" — the
    other answer would let a build walk into somebody's folder."""
    root = tmp_path / "broken"
    root.mkdir()
    (root / "project.json").write_text("{not json")
    pk = peek_project(root)
    assert pk.exists and pk.holds_anything


# ---------------------------------------------------------------------------
# 2. the sentence the window shows
# ---------------------------------------------------------------------------

def test_the_holds_sentence_counts_properly():
    from workflow import measurement_messages as M

    one = M.holds_phrase("Run 1", chart=True, verifications=1)
    many = M.holds_phrase("Run 1", chart=True, verifications=4)
    assert "one dated verification check" in one
    assert "4 dated verification checks" in many
    assert "(s)" not in one + many
    assert "nothing yet" in M.holds_phrase("Run 1")


def test_the_window_text_has_no_placeholder_left_in_it():
    from workflow import measurement_messages as M

    title, body = M.M_PROJECT_EXISTS.render(
        name="test", folder="/x/test",
        runs=M.runs_phrase(3, 1), cal=M.calibration_phrase(True),
        chosen=M.chosen_phrase("Run 1"),
        holds=M.holds_phrase("Run 1", chart=True))
    for text in (title, body):
        assert "{" not in text and "}" not in text, text


# ---------------------------------------------------------------------------
# 3. the gate, on a real Create Chart tab
# ---------------------------------------------------------------------------

@pytest.fixture
def chart_tab(tmp_path, qapp):
    from core.argyll_runner import ArgyllRunner
    from tests.conftest_calibration import CalSettings
    from ui.tabs.tab_chart import TabChart

    settings = CalSettings(tmp_path)
    fm = FileManager(settings)
    tab = TabChart(ArgyllRunner(settings), fm, settings)
    return tab, fm, settings


def _type(tab, name):
    """TYPE it, do not setText it.

    The gate deliberately fires only for a name a person put there — a preset
    seeding the field must not raise a window. `QTest.keyClicks` emits
    `textEdited` exactly as a keystroke does; `setText` does not, and a test
    using it would prove nothing about the real path.
    """
    from PyQt6.QtTest import QTest

    tab._manual_btn.setChecked(True)
    f = tab._manual_target_name_edit
    f.clear()
    QTest.keyClicks(f, name)


def test_no_window_when_the_name_names_nothing(chart_tab, tmp_path):
    tab, _fm, _s = chart_tab
    _type(tab, "brand-new")
    assert tab._typed_project_peek() is None
    assert tab._gate_typed_project_name() == (True, False)


def test_no_window_for_the_project_that_is_already_open(chart_tab, tmp_path):
    """Continuing the project you have open is not news, and a window there
    would fire on every single build."""
    tab, fm, _s = chart_tab
    fm.set_target_name("mine")
    fm.project()
    _type(tab, "mine")
    assert tab._typed_project_peek() is None
    assert tab._gate_typed_project_name() == (True, False)


def test_no_window_for_an_existing_but_empty_project(chart_tab, tmp_path):
    tab, _fm, _s = chart_tab
    Project.create(tmp_path / "empty-one", "empty-one")
    _type(tab, "empty-one")
    assert tab._typed_project_peek() is not None, "the line still appears"
    assert tab._gate_typed_project_name() == (True, False), "but no window"


def _answer(monkeypatch, label_getter):
    """Click the button whose text `label_getter` picks out of the box."""
    from PyQt6.QtWidgets import QMessageBox
    seen = {}

    def _exec(self):
        seen["box"] = self
        wanted = label_getter([b.text() for b in self.buttons()])
        for b in self.buttons():
            if b.text() == wanted:
                b.click()          # sets clickedButton(), as a real click does
                return 0
        raise AssertionError(f"no button {wanted!r} in {[b.text() for b in self.buttons()]}")

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    return seen


def _occupied(tmp_path, name="test"):
    proj = Project.create(tmp_path / name, name)
    run = proj.current_run()
    (run.dir / f"{run.stem}.ti2").write_text("chart")
    (run.dir / f"{run.stem}.ti3").write_text("measured")
    return proj


@pytest.mark.parametrize("pick,expected", [
    (lambda labels: [l for l in labels if "Continue" in l][0], (True, True)),
    (lambda labels: [l for l in labels if "different name" in l][0], (False, False)),
    (lambda labels: [l for l in labels if l == "Cancel"][0], (False, False)),
])
def test_each_button_leads_where_it_says(chart_tab, tmp_path, monkeypatch,
                                         pick, expected):
    tab, _fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    before = sorted(p.relative_to(tmp_path).as_posix()
                    for p in (tmp_path / "test").rglob("*"))
    _answer(monkeypatch, pick)
    assert tab._gate_typed_project_name() == expected
    after = sorted(p.relative_to(tmp_path).as_posix()
                   for p in (tmp_path / "test").rglob("*"))
    assert after == before, "the question moved files on disk"


def test_replace_is_ARMED_by_the_window_and_not_carried_out_yet(
        chart_tab, tmp_path, monkeypatch):
    """The window asks; the point of no return acts.

    Several steps sit between the two and can still abort — a missing patch set
    is the one that bit: it archived the whole project and then said "Patch set
    not found", having built nothing at all.
    """
    tab, _fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    _answer(monkeypatch, lambda labels: [l for l in labels if "Replace" in l][0])
    assert tab._gate_typed_project_name() == (True, True)

    run1 = tmp_path / "test" / "runs" / "run1"
    assert (run1 / "test.ti3").exists(), "the window moved files by itself"
    assert tab._pending_replace is not None


def test_replace_archives_the_whole_project_and_deletes_nothing(
        chart_tab, tmp_path, monkeypatch):
    tab, _fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    _answer(monkeypatch, lambda labels: [l for l in labels if "Replace" in l][0])
    assert tab._gate_typed_project_name() == (True, True)
    assert tab._perform_pending_replace() is True

    root = tmp_path / "test"
    survivors = sorted(p.name for p in root.rglob("*") if p.is_file())
    assert "project.json" in survivors and "test.ti3" in survivors
    assert all("old" in p.parts for p in root.rglob("*.ti3")), \
        "the measurement is not in old/"
    assert not (root / "runs" / "run1" / "test.ti3").exists()


def test_a_build_that_aborts_after_the_window_leaves_the_project_alone(
        chart_tab, tmp_path, monkeypatch):
    """Measured before the fix: a missing .ti1 archived the whole project and
    then said "Patch set not found"."""
    tab, _fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    _answer(monkeypatch, lambda labels: [l for l in labels if "Replace" in l][0])
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: None)
    import ui.tabs.tab_chart as tc
    monkeypatch.setattr(tc, "InfoDialog",
                        lambda *a, **k: type("D", (), {"exec": lambda s: 0})())
    tab._generate_from_ti1(tmp_path / "there-is-no-such.ti1")

    run1 = tmp_path / "test" / "runs" / "run1"
    assert (run1 / "test.ti3").exists(), \
        "the project was archived for a build that never happened"


def test_a_name_changed_after_the_answer_drops_the_pending_replace(
        chart_tab, tmp_path, monkeypatch):
    """Replacing what they were asked about would now destroy a project the
    user was never shown by name."""
    tab, _fm, _s = chart_tab
    _occupied(tmp_path, "one")
    _occupied(tmp_path, "two")
    _type(tab, "one")
    _answer(monkeypatch, lambda labels: [l for l in labels if "Replace" in l][0])
    assert tab._gate_typed_project_name() == (True, True)
    _type(tab, "two")
    assert tab._perform_pending_replace() is True
    assert (tmp_path / "one" / "runs" / "run1" / "one.ti3").exists()
    assert (tmp_path / "two" / "runs" / "run1" / "two.ti3").exists()


def test_a_replace_that_fails_stops_the_build_and_says_so(
        chart_tab, tmp_path, monkeypatch):
    tab, _fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    _answer(monkeypatch, lambda labels: [l for l in labels if "Replace" in l][0])
    tab._gate_typed_project_name()

    import workflow.chart_import as ci
    monkeypatch.setattr(ci, "_archive_project_contents",
                        lambda root: (_ for _ in ()).throw(OSError("read-only")))
    said = []
    import ui.tabs.tab_chart as tc
    monkeypatch.setattr(tc, "InfoDialog",
                        lambda *a, **k: type("D", (), {"exec": lambda s: 0})())
    monkeypatch.setattr(tab, "_replace_failed_message",
                        lambda root, exc: said.append(str(exc)))
    assert tab._perform_pending_replace() is False
    assert said, "a failed Replace said nothing to the user"


def test_the_window_carries_the_s4_answer_so_only_one_window_opens(
        chart_tab, tmp_path, monkeypatch):
    """§S4 allows two windows for one action only at S4.3/S4.4. Continuing an
    existing project must not then also raise M-CHART-PROFILING."""
    tab, _fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    _answer(monkeypatch, lambda labels: [l for l in labels if "Continue" in l][0])
    proceed, s4_answered = tab._gate_typed_project_name()
    assert (proceed, s4_answered) == (True, True)


# ---------------------------------------------------------------------------
# 4. the line under the name box
# ---------------------------------------------------------------------------

def test_the_line_appears_only_when_the_name_matches(chart_tab, tmp_path):
    """Basti's ruling: no space is reserved for it, so its appearing is the
    signal. It must be hidden for a name that names nothing."""
    tab, _fm, _s = chart_tab
    Project.create(tmp_path / "already", "already")

    # `isHidden()`, not `isVisible()`: the tab itself is never shown in a
    # test, and `isVisible()` is False for every child of an unshown window —
    # it would pass whatever the code did.
    _type(tab, "brand-new")
    assert tab._manual_project_exists_lbl.isHidden()

    _type(tab, "already")
    assert not tab._manual_project_exists_lbl.isHidden()
    assert "already" in tab._manual_project_exists_lbl.text()

    _type(tab, "")
    assert tab._manual_project_exists_lbl.isHidden()


# ---------------------------------------------------------------------------
# 5. the gate is actually WIRED — the part a unit test of the gate cannot see
# ---------------------------------------------------------------------------

def _a_ti1(tmp_path):
    p = tmp_path / "patches.ti1"
    p.write_text("CTI1\nNUMBER_OF_SETS 1\nBEGIN_DATA\n1 0 0 0\nEND_DATA\n")
    return p


@pytest.mark.parametrize("entry", ["_on_generate", "_generate_from_ti1"])
def test_a_build_asks_before_it_adopts_the_project(chart_tab, tmp_path,
                                                   monkeypatch, entry):
    """Cancel must stop the build BEFORE anything is adopted or written.

    This is the half a unit test of the gate cannot prove: that the two build
    entry points call it at all, and call it before `set_target_name`.
    """
    tab, fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    seen = _answer(monkeypatch, lambda labels: [l for l in labels if l == "Cancel"][0])

    started = []
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: started.append(a))
    monkeypatch.setattr(tab._creator, "generate", lambda *a, **k: started.append(a))

    if entry == "_on_generate":
        tab._on_generate()
    else:
        tab._generate_from_ti1(_a_ti1(tmp_path))

    assert "box" in seen, f"{entry} built without asking about the project"
    assert not started, f"{entry} started a build after Cancel"
    assert not fm.is_named(), f"{entry} adopted the project after Cancel"


def test_the_live_preview_never_adopts_a_typed_name(chart_tab, tmp_path,
                                                    monkeypatch):
    """§4 forbids the auto-update preview from opening a window, so it must not
    be able to reach a project it would have to ask about. Before this, typing
    another project's name and nudging a layout knob moved ChromIQ into that
    project and rebuilt its chart, in silence."""
    from PyQt6.QtWidgets import QMessageBox

    tab, fm, _s = chart_tab
    fm.set_target_name("mine")
    fm.project()
    _occupied(tmp_path, "somebody-elses")
    _type(tab, "somebody-elses")

    def _no_window(self):
        raise AssertionError("the live preview opened a window")

    monkeypatch.setattr(QMessageBox, "exec", _no_window)
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: None)
    tab._generate_from_ti1(_a_ti1(tmp_path), ask=False, preview=True)

    assert fm.get_target_name() == "mine", \
        "the preview switched to the project whose name was merely typed"


def test_a_name_the_app_filled_in_never_raises_the_window(chart_tab, tmp_path,
                                                          monkeypatch):
    """A preset seeds the name box when it is empty (`_ensure_profile_name`),
    and the open project's name is reflected into it. Neither is the user
    asking for that project, so neither may interrupt them — the memory note
    calls this *the app answered its own question*, and the release gate caught
    it: selecting a preset opened a modal in a suite that types nothing.
    """
    from PyQt6.QtWidgets import QMessageBox

    tab, _fm, _s = chart_tab
    _occupied(tmp_path, "seeded-name")
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: (_ for _ in ()).throw(
                            AssertionError("a window opened for a seeded name")))

    tab._manual_btn.setChecked(True)
    tab._ensure_profile_name("seeded-name")           # what a preset does
    assert tab._manual_target_name_edit.text() == "seeded-name"
    assert tab._typed_project_peek() is None
    assert tab._gate_typed_project_name() == (True, False)

    # …and the moment the user edits it themselves, the gate is live again.
    from PyQt6.QtTest import QTest
    QTest.keyClicks(tab._manual_target_name_edit, "x")
    tab._manual_target_name_edit.setText("seeded-name")
    assert tab._typed_project_peek() is not None


# ---------------------------------------------------------------------------
# 6. the window must describe the project the build will ACTUALLY touch
# ---------------------------------------------------------------------------

def test_the_open_project_under_a_different_capitalisation_is_not_a_collision(
        chart_tab, tmp_path, monkeypatch):
    """macOS and Windows treat "REAL" and "real" as one folder, so a Path `==`
    called the project on screen a different one — and then offered to replace
    it. Measured: it emptied the open project."""
    from PyQt6.QtWidgets import QMessageBox

    tab, fm, _s = chart_tab
    _occupied(tmp_path, "real")
    fm.set_target_name("real")
    fm.project()
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: (_ for _ in ()).throw(
                            AssertionError("offered to replace the OPEN project")))
    _type(tab, "REAL")
    if (tmp_path / "REAL").exists():          # only on a case-insensitive volume
        assert tab._typed_project_peek() is None
        assert tab._gate_typed_project_name() == (True, False)


def test_a_nested_project_is_resolved_where_the_build_will_go(
        chart_tab, tmp_path, monkeypatch):
    """The sharpest form, and it lands on Knut's sub-folder question.

    `set_target_name` deliberately keeps a nested project where it is, but
    `preview_project_root` only ever answers <ChromIQ>/<name>. So with
    `Group-A/test` open and a DIFFERENT `test` at the top level, the window
    described the top-level one, "Replace it" emptied it, and the build went to
    the nested one regardless: one click, wrong project gutted.
    """
    from PyQt6.QtWidgets import QMessageBox

    tab, fm, _s = chart_tab
    _occupied(tmp_path, "test")                      # a different project
    nested = tmp_path / "Group-A" / "test"
    nested.parent.mkdir(parents=True)
    Project.create(nested, "test")
    fm.open_project_at(nested)

    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: (_ for _ in ()).throw(
                            AssertionError("asked about a project the build "
                                           "will not touch")))
    _type(tab, "test")
    assert tab._typed_project_peek() is None, \
        "the nested project's own name was read as a collision"
    assert tab._gate_typed_project_name() == (True, False)
    assert (tmp_path / "test" / "runs" / "run1" / "test.ti3").exists(), \
        "the top-level project was touched"


# ---------------------------------------------------------------------------
# 7. peek_project must survive whatever is on disk
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ['["not", "an", "object"]', "42", '"a string"'])
def test_a_manifest_that_is_json_but_not_a_project_does_not_raise(tmp_path, raw):
    """`data.get` on a list raises AttributeError out of a method whose whole
    promise is that asking is safe — and took Generate Chart down with it."""
    root = tmp_path / "odd"
    root.mkdir()
    (root / "project.json").write_text(raw)
    pk = peek_project(root)
    assert pk.exists and pk.holds_anything


def test_a_project_holding_only_a_calibration_is_not_empty(tmp_path):
    """A calibration lives in the project's own `cal/`, shared by every run.
    Looking only at the run made such a project read as empty, so no window
    appeared and a build could replace the calibration in silence."""
    proj = Project.create(tmp_path / "cal-only", "cal-only")
    cal = proj.calibration
    cal.ensure_dir()
    cal.cal_path.write_text("a calibration")
    pk = peek_project(tmp_path / "cal-only")
    assert pk.calibration and pk.holds_anything
    assert not (pk.chart or pk.measurement or pk.profile)

    # …and it is said ABOUT THE PROJECT, not listed under what a run holds —
    # "A new run holds: • a calibration" was a false statement about a run that
    # does not exist yet.
    from workflow import measurement_messages as M
    assert "calibration" in M.calibration_phrase(True)
    assert M.calibration_phrase(False) == ""
    assert "calibration" not in M.holds_phrase("Run 1", chart=True)


# ---------------------------------------------------------------------------
# 8. every route that adopts the typed name asks first
# ---------------------------------------------------------------------------

def test_choosing_a_prebuilt_preset_asks_before_it_adopts(
        chart_tab, tmp_path, monkeypatch):
    """Knut's exact report, on the one route the first fix missed: MERELY
    choosing a prebuilt-files preset from the dropdown adopts the typed name
    and resets the run's chart artefacts."""
    tab, fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    seen = _answer(monkeypatch, lambda labels: [l for l in labels if l == "Cancel"][0])
    key = next(iter(__import__("ui.tabs.tab_chart", fromlist=["PREBUILT_PRESETS"])
                    .PREBUILT_PRESETS))
    tab._create_prebuilt_target(key, "test")
    assert "box" in seen, "a prebuilt preset adopted the project with no window"
    assert not fm.is_named(), "Cancel still adopted the project"
    assert (tmp_path / "test" / "runs" / "run1" / "test.ti3").exists()


# ---------------------------------------------------------------------------
# 9. archiving reads/ must not make an old/ folder out of nothing
# ---------------------------------------------------------------------------

def test_regenerating_an_unmeasured_chart_leaves_no_old_folder(tmp_path):
    """§4's rule, and the reason `exports/` is NOT archived with `reads/`: the
    sidecars are derived and rebuilt on every build, so archiving them made
    every live-preview render leave an `old/<timestamp>/` behind on a run that
    had nothing to lose."""
    proj = Project.create(tmp_path / "fresh", "fresh")
    run = proj.current_run()
    (run.dir / f"{run.stem}.ti2").write_text("chart")
    run.exports_dir.mkdir(parents=True, exist_ok=True)
    (run.exports_dir / f"{run.stem}-colours.txt").write_text("derived")

    run.reset_chart_artefacts()
    assert not run.old_dir.exists(), \
        f"an old/ folder for a run with no results: {list(run.old_dir.rglob('*'))}"


def test_the_individual_reads_are_still_archived(tmp_path):
    """The half that IS the fix: instrument readings taken by hand cannot be
    regenerated, and `clear_reads()` used to rmtree them."""
    proj = Project.create(tmp_path / "measured", "measured")
    run = proj.current_run()
    (run.dir / f"{run.stem}.ti3").write_text("the measurement")
    run.reads_dir.mkdir(parents=True, exist_ok=True)
    for i in (1, 2, 3):
        (run.reads_dir / f"read{i}.ti3").write_text("a read")

    run.reset_chart_artefacts()
    archived = sorted(p.name for p in run.old_dir.rglob("read*.ti3"))
    assert archived == ["read1.ti3", "read2.ti3", "read3.ti3"], archived


# ---------------------------------------------------------------------------
# 10. the run picker — Basti's question, answered inside the window
# ---------------------------------------------------------------------------

def test_the_window_offers_every_run_and_defaults_to_a_new_one(chart_tab, tmp_path,
                                                               monkeypatch):
    """*"allowing me to either work in run 1 (or whatever runs exist for this
    name) or create a new run under this name"* — Basti, 2026-08-27.

    A NEW run is the default because it is the one answer that cannot cost
    anything; continuing into an existing run is one click away, and the window
    then says what that run holds.
    """
    tab, _fm, _s = chart_tab
    proj = Project.create(tmp_path / "many", "many")
    r1 = proj.current_run()
    (r1.dir / f"{r1.stem}.ti3").write_text("measured")
    proj.new_run()                                   # run2, empty and current
    _type(tab, "many")

    peek = tab._typed_project_peek()
    assert [r.id for r in peek.runs] == ["run1", "run2"]
    picker, chosen = tab._build_run_picker(peek)
    assert picker.currentData() == "", "the default is not a new run"
    assert [picker.itemData(i) for i in range(picker.count())] == ["", "run1", "run2"]

    # …and the body follows the picker.
    _t, body_new = tab._project_exists_message(peek, "")
    _t, body_r1 = tab._project_exists_message(peek, "run1")
    assert "nothing yet" in body_new
    assert "a measurement" in body_r1


def test_a_project_whose_current_run_is_empty_still_warns(chart_tab, tmp_path):
    """Basti's ruling, 2026-08-27. A project can have four finished runs and an
    empty current one: nothing is at risk, but joining somebody's project
    unannounced is exactly what he asked to be told about."""
    tab, _fm, _s = chart_tab
    proj = Project.create(tmp_path / "busy", "busy")
    r1 = proj.current_run()
    (r1.dir / f"{r1.stem}.ti3").write_text("measured")
    proj.new_run()                                   # current run, empty
    _type(tab, "busy")

    peek = tab._typed_project_peek()
    assert not (peek.chart or peek.measurement or peek.profile), \
        "the current run is supposed to be the empty one"
    assert peek.other_runs_hold and peek.holds_anything, \
        "a project with finished runs read as nothing to say"


def test_continuing_points_the_bar_at_the_run_that_was_chosen(chart_tab, tmp_path,
                                                              monkeypatch):
    """Measured before this: the window said Run 1, the bar said Run 1, and the
    build landed in run3 — the bar's choice was read and thrown away."""
    tab, _fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    _answer(monkeypatch, lambda labels: [l for l in labels if "Continue" in l][0])

    said = []
    tab._target_ctl = type("Ctl", (), {
        "set_profile_run": lambda self, rid: said.append(rid),
        "target": type("T", (), {"is_calibration": lambda self: False,
                                 "profile_run": ""})(),
    })()
    monkeypatch.setattr(type(tab), "_is_verification_target", lambda self: False)

    assert tab._gate_typed_project_name()[0] is True
    assert tab._adopted_via_gate is True
    tab._apply_gate_run_choice()
    assert said == [""], f"the bar was not pointed at the chosen run: {said}"
    # one-shot: the flag must not leak into the next build
    assert tab._builds_into_project(None) is True
    assert tab._builds_into_project(None) is False


# ---------------------------------------------------------------------------
# 11. what the regression check found in the round-2 build
# ---------------------------------------------------------------------------

def test_a_schema_1_project_with_several_runs_is_seen_whole(tmp_path):
    """Every run, not just the current one, and not just for schema 3."""
    root = tmp_path / "legacy"
    for rid in ("run1", "run2"):
        d = root / "runs" / rid
        d.mkdir(parents=True)
        (d / "legacy.ti2").write_text("chart")
        (d / "legacy.ti3").write_text("measured")
        (d / "legacy.icc").write_text("profile")
    (root / "project.json").write_text(json.dumps(
        {"schema_version": 1, "target_name": "legacy",
         "current_run": "run1", "runs": ["run1", "run2"]}), encoding="utf-8")
    pk = peek_project(root)
    assert pk.holds_anything
    assert [r.id for r in pk.runs] == ["run1", "run2"]
    assert pk.finished_runs == 2


def test_a_calibration_build_gets_no_run_picker(chart_tab, tmp_path):
    """A calibration lives in `cal/`, shared by every run, and
    `_align_current_run_to_target` is skipped for it — so a picker could not
    affect the build, and answering it moved the bar mid-build."""
    tab, _fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    peek = tab._typed_project_peek()

    tab._target_ctl = type("Ctl", (), {
        "target": type("T", (), {"is_calibration": lambda self: True,
                                 "profile_run": ""})(),
        "set_profile_run": lambda self, rid: None,
    })()
    picker, chosen = tab._build_run_picker(peek)
    assert picker is None
    assert chosen == [peek.run_id], "a calibration build must not move the run"


def test_the_live_preview_will_not_adopt_a_SEEDED_name_either(chart_tab, tmp_path,
                                                              monkeypatch):
    """The preview guard used to run through `_typed_project_peek`, which
    answers None unless the USER typed the name. A preset seeding the field with
    a name that happens to match an existing project, plus one nudge of a layout
    knob, then moved the preview into that project — with no window, because §4
    forbids one there."""
    tab, fm, _s = chart_tab
    fm.set_target_name("mine")
    fm.project()
    _occupied(tmp_path, "somebody-elses")

    tab._manual_btn.setChecked(True)
    tab._ensure_profile_name("somebody-elses")        # seeded, not typed
    assert tab._name_typed_by_user is False
    assert tab._typed_project_peek() is None, "the WINDOW must still stay quiet"
    assert tab._name_points_elsewhere("somebody-elses") is True

    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: None)
    tab._generate_from_ti1(_a_ti1(tmp_path), ask=False, preview=True)
    assert fm.get_target_name() == "mine", \
        "the live preview adopted a project from a name the user never typed"


def test_one_click_opens_the_window_once(chart_tab, tmp_path, monkeypatch):
    """`_on_generate` gates, then dispatches to a route that gates again — and
    the second gate reset the pending Replace, so a confirmed destructive answer
    was dropped without a word."""
    tab, _fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    shown = []
    from PyQt6.QtWidgets import QMessageBox

    def _exec(self):
        shown.append(self.text())
        for b in self.buttons():
            if "Continue" in b.text():
                b.click()
                return 0
        self.buttons()[-1].click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    proceed, _s4 = tab._gate_typed_project_name()
    assert proceed and len(shown) == 1
    # The caller SAYS it has already asked — the marker is an argument, not
    # state on the tab. A flag on `self` outlived early returns and then
    # suppressed the window for an unrelated action, which is how a preset
    # chosen later was adopted in silence.
    assert tab._gate_route_and_replace(already_asked=True) == (True, False)
    assert len(shown) == 1, f"the window opened {len(shown)} times for one click"

    # …and a genuinely separate action asks again.
    assert tab._gate_route_and_replace() [0] is True
    assert len(shown) == 2, "a second, separate action was not asked about"


def test_a_hand_edited_manifest_cannot_steer_the_read_out_of_the_project(tmp_path):
    """`current_run` and the run ids become path components. Project folders get
    zipped and mailed, and `project.json` is a text file — the same shape as the
    journal traversal fixed in 4.1.3-beta.18."""
    root = tmp_path / "evil"
    (root / "runs").mkdir(parents=True)
    (root / "project.json").write_text(json.dumps(
        {"schema_version": 3, "target_name": "evil",
         "current_run": "../../..",
         "runs": ["../..", "/etc", "run1", "..", "..\\\\..", ""]}), encoding="utf-8")
    pk = peek_project(root)
    assert pk.run_id == "run1", f"a traversal survived as the current run: {pk.run_id!r}"
    for r in pk.runs:
        assert ".." not in r.id and "/" not in r.id and "\\" not in r.id


def test_an_empty_reads_folder_does_not_spawn_an_old_folder(tmp_path):
    """A run with nothing to lose spawns no `old/` — an empty `reads/` is not
    work, and archiving it broke that rule the same way `exports/` did."""
    proj = Project.create(tmp_path / "empty-reads", "empty-reads")
    run = proj.current_run()
    (run.dir / f"{run.stem}.ti2").write_text("chart")
    run.reads_dir.mkdir(parents=True, exist_ok=True)      # there, but empty
    run.reset_chart_artefacts()
    assert not run.old_dir.exists(), list(run.old_dir.rglob("*"))


# ---------------------------------------------------------------------------
# 12. the line goes away when the project is adopted, and comes back on a
#     name that points somewhere else
# ---------------------------------------------------------------------------

def test_the_line_goes_away_once_the_project_is_open(chart_tab, tmp_path):
    """Basti, 2026-08-27. The line means "this name points at a project other
    than the one you have open" — and it was refreshed only when the TEXT
    changed, which adopting a project does not do. So it went on warning about
    a project ChromIQ had just opened."""
    tab, fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    assert not tab._manual_project_exists_lbl.isHidden()

    fm.set_target_name("test")               # what adopting it does
    tab._refresh_project_exists_line()
    assert tab._manual_project_exists_lbl.isHidden(), \
        "the hint went on warning about the project that is now open"


def test_the_refresh_is_actually_wired_to_the_project_change():
    """The rule above is worth nothing unless something calls it.

    `_refresh_project_exists_line` is wired to `textChanged` and adopting a
    project does not change the text, so the ONLY thing that makes this work is
    the main window subscribing to the file manager's project-change listener.
    Checked in the source, because building a whole MainWindow to prove one
    connection costs more than it is worth.
    """
    import inspect

    from ui.main_window import MainWindow

    src = inspect.getsource(MainWindow.__init__)
    assert "add_listener(self._refresh_project_hint)" in src, \
        "nothing refreshes the project hint when the open project changes"
    assert "_refresh_project_exists_line" in inspect.getsource(
        MainWindow._refresh_project_hint)


def test_the_open_project_change_reaches_a_listener(tmp_path):
    """The refresh needs a signal, and neither candidate fired for the case
    that matters: with project A open and a build adopting B, the named-state
    listener saw nothing because both are "named"."""
    from core.file_manager import FileManager, Project

    fm = FileManager(_ChartSettings(tmp_path))
    Project.create(tmp_path / "A", "A")
    Project.create(tmp_path / "B", "B")
    fired = []
    fm.add_named_state_listener(lambda: fired.append(1))

    fm.set_target_name("A")
    assert fired, "opening a project told nobody"
    fired.clear()
    fm.set_target_name("A")                  # the same one again
    assert not fired, "re-applying the same name is churn, not a change"
    fm.set_target_name("B")
    assert fired, "swapping one project for another told nobody"


class _ChartSettings:
    def __init__(self, tmp):
        from core.settings import DEFAULTS
        self.d = dict(DEFAULTS)
        self.d["custom_output_path"] = str(tmp)

    def get(self, k, d=None):
        return self.d.get(k, d)

    def set(self, k, v):
        self.d[k] = v


def test_the_hint_carries_no_project_name(chart_tab, tmp_path):
    """A real project name is long — the app's own `default_target_name` makes
    an 81-character one — and this label is a fixed 524 px with word wrap, so a
    name in it took two rows in German and Dutch and three in Japanese, pushing
    the rows beneath it down. The name is in the field just above."""
    tab, _fm, _s = chart_tab
    long_name = "Printer_Paper_Type_Instr_2026-08-27_20-30_Baryta_Gloss_i1Pro3_High"
    proj = Project.create(tmp_path / long_name, long_name)
    run = proj.current_run()
    (run.dir / f"{run.stem}.ti3").write_text("measured")

    _type(tab, long_name)
    text = tab._manual_project_exists_lbl.text()
    assert not tab._manual_project_exists_lbl.isHidden()
    assert long_name not in text, "a long project name is back in the hint"
    assert "—" not in text and " - " not in text, f"a dash crept back in: {text!r}"


# ---------------------------------------------------------------------------
# 13. an answer belongs to ONE action
# ---------------------------------------------------------------------------

def test_an_armed_replace_does_not_survive_an_aborted_build(chart_tab, tmp_path,
                                                            monkeypatch):
    """Answer "Replace it", then cancel the rename chooser: nothing is built and
    nothing is archived — but the answer used to stay armed on the tab, and one
    live-preview render then archived the whole project with no window at all,
    because the preview is the route forbidden to open one."""
    tab, _fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    _answer(monkeypatch, lambda labels: [l for l in labels if "Replace" in l][0])
    tab._gate_typed_project_name()
    assert tab._pending_replace is not None

    # …the build aborts before the point of no return
    monkeypatch.setattr(type(tab), "_handle_target_rename", lambda self, n: False)
    monkeypatch.setattr(tab._creator, "generate", lambda *a, **k: None)
    tab._on_generate()

    assert tab._pending_replace is None, "the answer outlived the click"
    assert not getattr(tab, "_adopted_via_gate", False)
    assert (tmp_path / "test" / "runs" / "run1" / "test.ti3").exists(), \
        "the project was archived by a build that never happened"


def test_the_live_preview_never_performs_a_replace(chart_tab, tmp_path,
                                                   monkeypatch):
    """Belt as well as braces: even with an answer somehow armed, the preview
    must not act on it."""
    tab, fm, _s = chart_tab
    _occupied(tmp_path)
    fm.set_target_name("test")
    # The name must be IN THE BOX, or `_perform_pending_replace` drops the
    # answer on its own and the test proves nothing.
    _type(tab, "test")
    tab._pending_replace = (tmp_path / "test", "test")
    tab._adopt_run_choice = "run1"
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: None)
    tab._generate_from_ti1(_a_ti1(tmp_path), ask=False, preview=True)
    assert (tmp_path / "test" / "runs" / "run1" / "test.ti3").exists(), \
        "a live preview archived the project"


# ---------------------------------------------------------------------------
# 14. the debounced command preview must not survive the Generate click
# ---------------------------------------------------------------------------

def test_generate_cancels_the_DEBOUNCED_preview_too(chart_tab, tmp_path):
    """`_on_generate` starts by cancelling any queued live re-render. The
    command preview is debounced now, and it is what ARMS that render — so
    cancelling only the render left the 150 ms scheduler pending, and a Generate
    click within 150 ms of the last change re-armed the render from inside the
    §S4.7 window. The user then pressed Cancel on a window that says it changes
    nothing, with their chart file already rewritten.

    Goes through `_schedule_manual_command_preview`, which every other test that
    touches the preview bypasses by calling the refresh directly.
    """
    tab, _fm, _s = chart_tab
    tab._manual_btn.setChecked(True)
    tab._schedule_manual_command_preview()
    assert tab._cmd_preview_timer.isActive(), "the debounce did not arm"

    tab._cancel_pending_auto_preview()
    assert not tab._cmd_preview_timer.isActive(), \
        "a queued command-preview refresh survived the Generate click"
    auto = getattr(tab, "_auto_preview_timer", None)
    assert auto is None or not auto.isActive()


# ---------------------------------------------------------------------------
# 15. a preset the user was told was not applied must not stay in the dropdown
# ---------------------------------------------------------------------------

def test_a_refused_preset_leaves_the_dropdown_where_it_was(chart_tab, tmp_path,
                                                           monkeypatch):
    """Answer the project window with Cancel, whose button says it changes
    nothing, and the dropdown went on showing a preset that had not been
    applied.

    `_on_preset_selected` committed `_last_preset_index = index` BEFORE it
    dispatched, so `_revert_preset_combo` restored the combo to the index it was
    already on and every built-in preset's revert was a no-op. It also made the
    same preset unpickable afterwards: the index matched, so choosing it again
    emitted no signal and nothing happened at all.
    """
    from ui.tabs.tab_chart import PREBUILT_PRESETS

    tab, fm, _s = chart_tab
    _occupied(tmp_path)
    _type(tab, "test")
    combo = tab._preset_combo
    key = next(iter(PREBUILT_PRESETS))
    idx = next((i for i in range(combo.count())
                if combo.itemData(i) == key), None)
    if idx is None:
        pytest.skip("this build ships no prebuilt presets")

    before_idx, before_last = combo.currentIndex(), tab._last_preset_index
    _answer(monkeypatch, lambda labels: [l for l in labels if l == "Cancel"][0])
    # WHAT CHOOSING IT DOES. The combo is wired to `activated`, which Qt emits
    # for a real interaction only, so a bare `setCurrentIndex` is silent (#175).
    combo.blockSignals(True)
    combo.setCurrentIndex(idx)
    combo.blockSignals(False)
    combo.activated.emit(idx)

    assert combo.currentIndex() == before_idx, \
        "the dropdown kept a preset the user was told was not applied"
    assert tab._last_preset_index == before_last, \
        "the abandoned selection was committed as the last one"
    assert not fm.is_named(), "Cancel adopted the project anyway"


def test_a_refusal_after_a_preset_was_applied_goes_back_to_that_preset(
        chart_tab, tmp_path, monkeypatch):
    """Basti's ruling, 2026-08-27: a refused preset leaves the tab exactly as it
    was — which includes the dropdown showing the preset that WAS applied.

    THIS TEST USED TO ASSERT THE OPPOSITE, AND WAS RIGHT TO (#175). Landing on
    "none" was the honest answer while a dispatch tore the previous preset down
    and never put it back: pointing the dropdown at a preset whose settings no
    longer existed would have been a lie, and — because the index then matched —
    that preset could never be chosen again either. Both halves are gone now.
    `_restore_preset_state` puts the previous preset's settings back with it, and
    the combo is wired to `activated`, which fires even when the index does not
    move. Neither change is safe without the other.
    """
    from ui.tabs.tab_chart import PREBUILT_PRESETS

    tab, fm, _s = chart_tab
    combo = tab._preset_combo
    keys = [k for k in PREBUILT_PRESETS
            if any(combo.itemData(i) == k for i in range(combo.count()))]
    if len(keys) < 2:
        pytest.skip("this build ships fewer than two prebuilt presets")
    idx_a = next(i for i in range(combo.count()) if combo.itemData(i) == keys[0])
    idx_b = next(i for i in range(combo.count()) if combo.itemData(i) == keys[1])

    # Preset A is the committed selection — the state the tab is in after it
    # has been applied. (Applying one for real here would run a whole build;
    # the committed index is the only part this behaviour depends on.)
    combo.blockSignals(True)
    combo.setCurrentIndex(idx_a)
    combo.blockSignals(False)
    tab._last_preset_index = idx_a

    # …then the user retypes a name that collides, picks B, and cancels.
    _occupied(tmp_path)
    _type(tab, "test")
    _answer(monkeypatch, lambda labels: [l for l in labels if l == "Cancel"][0])
    combo.blockSignals(True)
    combo.setCurrentIndex(idx_b)
    combo.blockSignals(False)
    combo.activated.emit(idx_b)

    assert combo.currentIndex() == idx_a, \
        "the dropdown did not go back to the preset that was actually applied"
    assert tab._last_preset_index == idx_a
    # …and A must still be choosable, which is the half the revert alone broke.
    assert combo.receivers(combo.activated) == 1, \
        "putting the dropdown back on A is only safe while A can be re-chosen"
