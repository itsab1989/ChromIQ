"""Naming a project in the import window puts you IN that project (#182).

Knut, issue #182, 2026-09-11, after "Open chart file (.ti2)" on a chart that
lives outside the ChromIQ folder and typing ``scan-test2`` into the window that
follows:

    *"The main window, Create Chart tab, now shows red text under the Printer
    profile project name, that 'You already have a project with this name', and
    a project was not created (profile run bar is still locked and saying New
    Run). … I did not have this project when defining the name in the first
    window. After clicking OK and returning to main window, the project was not
    created, only the defined name was placed in the project name field."*

Three complaints, one omission. The project WAS created on disk, and nothing
opened it: every other route through :func:`ui.ti2_loader.resolve_ti2` that ends
in a project opens it and points the Profile-run bar, and the two that CREATE
one did not. So the app finished the import standing outside the folder it had
just filled, which made

* the red "You already have a project with this name" line true, about the
  project the import had just made, under a name the app itself had put in the
  box;
* the bar read "New run", locked, with nothing selected;
* and Create Chart call the chart "loaded from elsewhere", which is what refused
  Generate Chart until an unrelated "Edit patch recipe" tick dropped that state.

Driven on screen before and after the fix, with the run folder and the
controller read at every step.

The second half of this file is the fault found while reproducing that route:
the import copied whatever file it was handed into the new project AS the
chart, so a page bitmap became ``<project>.ti2``.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                        # noqa: E402

import ui.ti2_loader as L                                       # noqa: E402
from core.file_manager import Project                           # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import measurement_messages as M                  # noqa: E402
from workflow.chart_import import holds_a_chart                 # noqa: E402

#: The head of a real Argyll chart file. Enough of one that `holds_a_chart`
#: recognises it, which is the property under test.
CHART_TEXT = (
    "CTI2   \n\nDESCRIPTOR \"Argyll Calibration Target chart information 2\"\n"
    "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
    "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n1 100 100 100\nEND_DATA\n"
)
#: The first bytes of a TIFF, little-endian. A page bitmap begins with these.
TIFF_HEAD = b"II*\x00\x08\x00\x00\x00"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FM:
    """The FileManager surface the loader uses, and nothing else."""

    def __init__(self, work: Path):
        self._work = work
        self._root: "Path | None" = None

    def working_dir(self) -> Path:
        return self._root if self._root is not None else self._work

    def project(self) -> Project:
        if self._root is None:
            raise FileNotFoundError("nothing open")
        return Project.load(self._root)

    def set_target_name(self, name):
        self._root = self._work / name

    def open_project_at(self, root):
        self._root = Path(root)


def _settings(work: Path):
    class _S:
        def get(self, k, d=None):
            return str(work) if k == "custom_output_path" else d
    return _S()


def _external_chart(folder: Path, stem: str = "testHex") -> Path:
    """A chart with its pages, OUTSIDE the ChromIQ folder."""
    folder.mkdir(parents=True, exist_ok=True)
    ti2 = folder / f"{stem}.ti2"
    ti2.write_text(CHART_TEXT, encoding="utf-8")
    (folder / f"{stem}.ti1").write_text(CHART_TEXT, encoding="utf-8")
    for i in (1, 2):
        (folder / f"{stem}_{i:02d}.tif").write_bytes(TIFF_HEAD + b"\0" * 64)
    return ti2


# ---------------------------------------------------------------------------
# the project you have just named is the project you are in
# ---------------------------------------------------------------------------
def test_importing_a_chart_from_outside_opens_the_project_it_makes(
        qapp, tmp_path, monkeypatch):
    """Knut's route: nothing open, a chart from elsewhere, a name typed."""
    work = tmp_path / "work"; work.mkdir()
    ti2 = _external_chart(tmp_path / "elsewhere" / "chart")
    ctl = MeasurementTargetController(_FM(work))
    assert ctl.project_or_none() is None            # nothing open, as he had
    monkeypatch.setattr(L, "_ask_profile_name", lambda *a, **k: ("scan-test2", False))

    out, _tiffs = L.resolve_ti2(None, ti2, _settings(work), ctl)

    assert out == work / "scan-test2" / "runs" / "run1" / "scan-test2.ti2"
    proj = ctl.project_or_none()
    assert proj is not None, (
        "the project was made on disk and the app is still standing outside "
        "it: this is exactly what Knut saw as 'the project was not created'")
    assert Path(proj.root) == work / "scan-test2"
    assert ctl.target.profile_run == "run1", (
        "the Profile-run bar must name the run the chart landed in, not stay "
        "on 'New run'")


def test_the_name_the_import_took_is_no_longer_a_name_that_is_taken(
        qapp, tmp_path, monkeypatch):
    """The red line under the name box asks the SAME question this fix answers.

    ``TabChart._project_already_exists`` reports a name as taken only when it
    is not the project already open, so opening the new project is what stops
    the tab announcing the import's own project back at the person. Asserted
    here through that predicate's own rule rather than through the widget, so
    the two cannot drift.
    """
    work = tmp_path / "work"; work.mkdir()
    ti2 = _external_chart(tmp_path / "elsewhere" / "chart")
    fm = _FM(work)
    ctl = MeasurementTargetController(fm)
    monkeypatch.setattr(L, "_ask_profile_name", lambda *a, **k: ("scan-test2", False))

    L.resolve_ti2(None, ti2, _settings(work), ctl)

    assert (work / "scan-test2" / "project.json").is_file()
    assert fm.working_dir() == work / "scan-test2", (
        "the working folder must be the imported project, or the name box "
        "matches a project on disk that is not the open one and the tab says "
        "'You already have a project with this name'")


def test_use_as_base_for_a_new_profile_opens_the_copy(qapp, tmp_path, monkeypatch):
    """The other door that makes a project: copying one chart out of another."""
    work = tmp_path / "work"; work.mkdir()
    src = Project.create(work / "P", "P")
    run = src.current_run(); run.ensure_dir()
    run.chart_ti2.write_text(CHART_TEXT, encoding="utf-8")
    (run.dir / "P_01.tif").write_bytes(TIFF_HEAD)
    fm = _FM(work); fm.open_project_at(src.root)
    ctl = MeasurementTargetController(fm)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "new")
    monkeypatch.setattr(L, "_ask_profile_name", lambda *a, **k: ("Fresh", False))

    L.resolve_ti2(None, run.chart_ti2, _settings(work), ctl)

    assert Path(ctl.project_or_none().root) == work / "Fresh"
    assert ctl.target.profile_run == "run1"


def test_the_new_project_is_entered_as_a_profiling_run(qapp, tmp_path,
                                                       monkeypatch):
    """A brand-new project has one run and no verification chart in it.

    "Use as base for a new profile" is reachable with Run type = Verification,
    and the copy is filed as the new run's OWN chart. Left on Verification the
    bar would point at a verification chart the new project has not got.
    """
    from core.measurement_target import RUN_TYPE_VERIFICATION
    work = tmp_path / "work"; work.mkdir()
    src = Project.create(work / "P", "P")
    run = src.current_run(); run.ensure_dir()
    run.chart_ti2.write_text(CHART_TEXT, encoding="utf-8")
    fm = _FM(work); fm.open_project_at(src.root)
    ctl = MeasurementTargetController(fm)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "new")
    monkeypatch.setattr(L, "_ask_profile_name", lambda *a, **k: ("Fresh", False))

    L.resolve_ti2(None, run.chart_ti2, _settings(work), ctl)

    assert not ctl.target.is_verification(), (
        "the bar is pointing at a verification chart the new project has not "
        "got")


# ---------------------------------------------------------------------------
# …and a file that is not a chart never becomes one by being copied
# ---------------------------------------------------------------------------
def test_holds_a_chart_tells_a_chart_from_a_page_image(tmp_path):
    good = tmp_path / "c.ti2"; good.write_text(CHART_TEXT, encoding="utf-8")
    page = tmp_path / "c_01.tif"; page.write_bytes(TIFF_HEAD + b"\xff" * 4096)
    assert holds_a_chart(good)
    assert not holds_a_chart(page)
    assert not holds_a_chart(tmp_path / "missing.ti2")


def test_a_file_with_no_chart_in_it_is_refused_before_anything_is_made(
        qapp, tmp_path, monkeypatch):
    """The chooser hides a .tif; its NAME BOX takes one, and this is the guard.

    Measured on screen 2026-09-11: typing ``testHex_02.tif`` into the "Load
    .ti2 file" window was accepted, and the import made a project whose
    ``.ti2`` began ``II*`` — a TIFF under a chart's name, with nothing said.
    """
    work = tmp_path / "work"; work.mkdir()
    folder = tmp_path / "elsewhere" / "chart"
    _external_chart(folder)
    page = folder / "testHex_02.tif"
    ctl = MeasurementTargetController(_FM(work))
    said: list = []
    monkeypatch.setattr(L, "_say_that_file_holds_no_chart",
                        lambda parent, path: said.append(Path(path).name))
    monkeypatch.setattr(L, "_ask_profile_name",
                        lambda *a, **k: pytest.fail(
                            "a file with no chart in it must be refused before "
                            "anybody is asked to name a project for it"))

    out = L.resolve_ti2(None, page, _settings(work), ctl)

    assert out is None
    assert said == ["testHex_02.tif"]
    assert list(work.iterdir()) == [], (
        "nothing may be created for a file that is not a chart; the folder "
        f"holds {[p.name for p in work.iterdir()]}")


def test_the_refusal_says_the_catalogue_message_with_nothing_left_over():
    """M-IMPORT-NOT-A-CHART is PROPOSED; the window still renders from §M."""
    import inspect
    src = inspect.getsource(L._say_that_file_holds_no_chart)
    assert "measurement_messages" in src and "M_IMPORT_NOT_A_CHART" in src, (
        "the refusal window must take its words from the catalogue")
    title, body = M.M_IMPORT_NOT_A_CHART.render(name="testHex_02.tif")
    assert "{" not in title and "{" not in body
    assert "testHex_02.tif" in body
    assert not M.M_IMPORT_NOT_A_CHART.approved, (
        "the wording has not been reviewed; it must stay in §M-PROPOSED until "
        "Knut or Basti approves it")


def test_a_chart_already_inside_a_project_is_never_refused(qapp, tmp_path,
                                                           monkeypatch):
    """The guard judges what is about to be IMPORTED, and nothing else.

    A chart already in a project is opened in place. Refusing one over a header
    this function cannot judge would lock a person out of their own work, so
    the guard is asked only about a file from outside.
    """
    work = tmp_path / "work"; work.mkdir()
    proj = Project.create(work / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_bytes(TIFF_HEAD + b"\0" * 32)     # not a chart at all
    fm = _FM(work); fm.open_project_at(proj.root)
    ctl = MeasurementTargetController(fm)
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: "continue")
    monkeypatch.setattr(L, "_say_that_file_holds_no_chart",
                        lambda *a, **k: pytest.fail(
                            "a chart inside a project must open in place"))

    out, _ = L.resolve_ti2(None, run.chart_ti2, _settings(work), ctl)
    assert out == run.chart_ti2
