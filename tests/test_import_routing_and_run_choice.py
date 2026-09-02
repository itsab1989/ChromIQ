"""The import's routing and run choice — the parts a challenge found decorative.

Three faults, all of which left the feature looking as though it worked:
  * the run picker's `currentIndexChanged` was never connected, so the choice
    on screen was ignored and EVERY import went to "a new run";
  * that new run was EMPTY, so `assess()` had no chart to compare against and
    filed anything at all, in silence;
  * the "is this file already in a project?" test looked one level up, and a
    run's own measurement lives two levels down — so ChromIQ offered to copy a
    file into another project when it was already exactly where it belonged.
"""
import pathlib
import tempfile

import pytest


@pytest.fixture()
def work():
    return pathlib.Path(tempfile.mkdtemp())


#: A chart and a measurement of it, in the shape ChromIQ actually writes —
#: device values AND expected XYZ, so `assess` can read both ends.
_ROWS = [(100, 100, 100), (100, 0, 0), (0, 100, 0), (0, 0, 100),
         (50, 50, 50), (0, 0, 0)]


def _cgats(path, magic, rows):
    body = "".join(f"{i} \"A{i}\" {r} {g} {b} {r*0.9:.4f} {g*1.0:.4f} "
                   f"{b*1.1:.4f}\n" for i, (r, g, b) in enumerate(rows, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{magic}\n\nKEYWORD \"SAMPLE_LOC\"\n"
                    "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
                    "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y "
                    "XYZ_Z\nEND_DATA_FORMAT\n"
                    f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + body
                    + "END_DATA\n", encoding="utf-8")
    return path


def test_project_has_all_runs_not_runs(work, qapp):
    """The selection code called `proj.runs()`, which does not exist — it
    raised into a guard and fell through to "a new run" every time."""
    from core.file_manager import Project

    proj = Project.create(work / "P", "P")
    assert hasattr(proj, "all_runs"), "the API this depends on has moved"
    assert not hasattr(proj, "runs"), (
        "`runs` exists again — the selection code must use whichever is real")
    assert [r.id for r in proj.all_runs()] == ["run1"]


def test_a_new_run_for_an_import_carries_the_chart(work, qapp):
    """An empty run has nothing to check a measurement against, so the import
    accepted any file in silence. §I.9: the copy takes the chart, and only the
    chart."""
    from core.file_manager import Project

    proj = Project.create(work / "P", "P")
    src = proj.current_run()
    src.chart_ti2.write_text("CTI2\n\nNUMBER_OF_SETS 6\n", encoding="utf-8")
    src.measurement_ti3.write_text("CTI3 someone's measurement\n", encoding="utf-8")

    new = proj.duplicate_run(src, ("chart",))

    assert new.chart_ti2.is_file(), (
        "a new run with no chart cannot validate anything filed into it")
    assert not new.measurement_ti3.is_file(), "the copy carried a measurement"
    assert src.measurement_ti3.is_file(), "the source run was touched"


def test_a_runs_own_measurement_counts_as_already_in_a_project(work, qapp):
    """`<project>/runs/runN/` holds no `project.json`, so a one-level test said
    "not in a project" — and ChromIQ asked where to put a file that was already
    where it belonged, then offered to copy it into a different project."""
    from core.file_manager import Project, peek_project
    from ui.ti2_loader import _project_root_for

    proj = Project.create(work / "P", "P")
    run = proj.current_run()
    own = run.dir / "P.ti3"
    own.write_text("CTI3\n", encoding="utf-8")

    assert not peek_project(own.parent).exists, (
        "precondition: the run folder itself is not a project")
    assert _project_root_for(own, work) is not None, (
        "a run's own measurement must be recognised as inside its project")


def test_an_outside_measurement_is_still_outside(work, qapp):
    """…and the walk must not swallow the case the feature exists for."""
    from ui.ti2_loader import _project_root_for

    stray = work / "Desktop-ish" / "measured.ti3"
    stray.parent.mkdir(parents=True)
    stray.write_text("CTI3\n", encoding="utf-8")
    assert _project_root_for(stray, work) is None


def test_every_format_reaches_the_same_question(qapp):
    """`.mxf` and `.txt` — the files this feature exists for — were routed by
    suffix BEFORE the question and never met it."""
    import inspect
    from ui.tabs.tab_profile import TabProfile

    src = inspect.getsource(TabProfile._on_load_ti3)
    ask = src.index("_offer_import_into_a_project")
    mxf = src.index('".mxf", ".cxf"')
    assert src.index("_convert_for_import") < ask, (
        "the conversion must happen before the question, or the question "
        "cannot read the measurement")
    assert ask < src.rindex('".mxf", ".cxf"'), (
        "the format routing still runs before the question — .mxf and .txt "
        "never reach it")


def _import_into(work, monkeypatch, pick_run, n_runs=3, *,
                 bar_run=None, manifest_run=None, rows_per_run=None,
                 landed_out=None):
    """Drive the real routing with a real picker, and say where the file goes.

    Returns (which run the measurement landed in, the runs offered on screen).

    ``bar_run`` selects a run on the Profile-run pulldown; ``manifest_run``
    writes a DIFFERENT run into `project.json`'s `current_run`, which is what
    picking on the bar deliberately does not do. ``rows_per_run`` gives each
    run a chart of its own size, so the run a new run's chart was copied from
    can be read back off disk. ``landed_out`` receives the run folder the
    measurement ended up in.
    """
    from PyQt6.QtWidgets import QComboBox, QMessageBox
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager, Project
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart
    from ui.tabs.tab_profile import TabProfile

    settings = AppSettings()
    settings.set("custom_output_path", str(work / "out"))
    fm = FileManager(settings)
    root = fm.root_dir()
    root.mkdir(parents=True, exist_ok=True)
    proj = Project.create(root / "P", "P")
    for i in range(n_runs):
        run = proj.current_run() if i == 0 else proj.new_run()
        run.ensure_dir()
        rows = (rows_per_run or {}).get(run.id, _ROWS)
        _cgats(run.chart_ti2, "CTI2", rows)
    if manifest_run is not None:
        proj.set_current_run(manifest_run)
    fm.set_target_name("P")

    tab_chart = TabChart(ArgyllRunner(settings), fm, settings)
    ctl = MeasurementTargetController(fm)
    tab_chart.set_target_controller(ctl)
    if bar_run is not None:
        ctl.set_profile_run(bar_run)
    tab = TabProfile(ArgyllRunner(settings), settings)
    tab.set_target_controller(ctl)
    tab._tab_chart = tab_chart          # what `self.window()` is asked for

    measurement = _cgats(work / "measured.ti3", "CTI3", _ROWS)

    offered: list = []

    def _answer(self):
        """Choose *pick_run* in the picker, then press the accept button."""
        combo = self.findChild(QComboBox)
        if combo is not None:
            offered.extend(combo.itemData(i) for i in range(combo.count()))
            idx = next((i for i in range(combo.count())
                        if combo.itemData(i) == pick_run), None)
            if idx is not None:
                combo.setCurrentIndex(idx)
        for b in self.buttons():
            if self.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole:
                b.click()
                break
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _answer)
    monkeypatch.setattr("ui.tooltip_button._InfoDialog.exec",
                        lambda self: 0, raising=False)

    assert tab._file_into_project("P", measurement, fm, ctl) is True
    # Read the RESULT off disk: `proj` predates any run the import created,
    # so asking it would report an empty list for a file that is really there.
    landed = sorted(d.name for d in (root / "P" / "runs").iterdir()
                    if d.is_dir() and any(d.glob("*.ti3")))
    if landed_out is not None:
        landed_out.append(root / "P" / "runs")
    return landed, offered


def _patches(chart_ti2):
    """How many patches a chart holds, read off disk."""
    for line in chart_ti2.read_text(encoding="utf-8").splitlines():
        if line.startswith("NUMBER_OF_SETS"):
            return int(line.split()[1])
    raise AssertionError(f"no NUMBER_OF_SETS in {chart_ti2}")


def test_a_new_run_takes_its_chart_from_the_run_on_the_bar(
        work, qapp, monkeypatch):
    """R6 F1. "A new run" copied its chart from `project.json`'s `current_run`
    — a field picking a run on the bar does not write — so the run ChromIQ used
    and the run the person was shown were two different things.

    Driven the way it was found: the bar says Run 1, the manifest says run 3,
    and the two runs hold charts of different sizes. The chart in the new run
    must be RUN 1's, because Run 1 is the only run identity on screen.
    """
    runs_dir: list = []
    landed, _ = _import_into(
        work, monkeypatch, pick_run="", n_runs=3,
        bar_run="run1", manifest_run="run3",
        rows_per_run={"run3": _ROWS + [(25, 25, 25), (75, 75, 75)]},
        landed_out=runs_dir)
    new = [r for r in landed if r not in ("run1", "run2", "run3")]
    assert new, f"'a new run' filed into an existing one: {landed}"
    made = runs_dir[0] / new[0] / "P.ti2"
    assert _patches(made) == len(_ROWS), (
        f"the new run was seeded from the manifest's run3 "
        f"({_patches(made)} patches), not from Run 1 on the bar "
        f"({len(_ROWS)} patches)")


def test_the_manifest_still_decides_when_the_bar_names_no_run(
        work, qapp, monkeypatch):
    """The other half, so the fix above cannot be "always run 1".

    With the bar on "New run" there is no run on screen to take a chart from,
    and the manifest's current run is the documented fallback — the note in
    `file_into_project` says so, and it is what keeps a project ChromIQ has
    just opened on the person's behalf working at all.
    """
    runs_dir: list = []
    landed, _ = _import_into(
        work, monkeypatch, pick_run="", n_runs=3,
        bar_run="", manifest_run="run3",
        rows_per_run={"run3": _ROWS + [(25, 25, 25), (75, 75, 75)]},
        landed_out=runs_dir)
    new = [r for r in landed if r not in ("run1", "run2", "run3")]
    assert new, f"'a new run' filed into an existing one: {landed}"
    made = runs_dir[0] / new[0] / "P.ti2"
    assert _patches(made) == len(_ROWS) + 2, (
        "with no run named on the bar the manifest's current run is the "
        "source, and it was not used")


def test_the_run_picker_choice_is_connected(work, qapp, monkeypatch):
    """Asserted from WHERE THE FILE LANDS, not from the source text.

    This used to grep `_file_into_project` for "currentIndexChanged", which a
    no-op lambda satisfies — the exact fault it exists to catch (Run 2
    highlighted, Run 6 filed) would have passed it. So the picker is driven:
    run 2 is chosen on screen, and run 2 must be where the measurement is.
    """
    landed, offered = _import_into(work, monkeypatch, pick_run="run2")
    assert offered, "the window offered no runs at all"
    assert landed == ["run2"], (
        f"run2 was chosen on screen and the measurement landed in {landed} — "
        f"the picker is decorative")


def test_choosing_a_new_run_still_makes_one(work, qapp, monkeypatch):
    """The other answer, so the test above cannot pass by ignoring the picker
    in the opposite direction."""
    landed, _ = _import_into(work, monkeypatch, pick_run="", n_runs=2)
    assert landed and landed[0] not in ("run1", "run2"), (
        f"'a new run' filed into an existing one: {landed}")
