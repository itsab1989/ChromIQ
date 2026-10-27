"""Every import door files a measurement of the turned i1Profiler chart with
every reading on its own patch (beta, §I.14; review 4.3.17 r1, S1 and S2).

The Measure tab's IMPORT module put the converted copy in the chart's order
BEFORE anything was filed. The other doors did it at the very end, against the
chart of the run the copy had landed in, and that chart had lost its order on
the way:

* S2: Build Profile and Check & Refine, filing into a run that already held a
  measurement (or into "a new run"), made the new run with
  ``duplicate_run(run, ("chart",))``, which copies no ``exports/``. The valid
  file was refused with "360 of 360 patches do not hold the colour".
* S1: the new-project door's pre-check said "turned", ``_copy_files`` then
  took the chart and the measurement but no order, and the copy was filed
  SILENTLY with every reading on the wrong patch.

Now every door pairs a copy first (`measurement_filing.TurnedPairing`). These
tests drive each door through the real tabs of a real MainWindow (the Measure
tab through its own profiling import), with only the windows answered, and
check the filed copy patch by patch.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Project, exports_subdir             # noqa: E402
from workflow import i1profiler_turned as T                         # noqa: E402
from workflow.measurement_import import assess                      # noqa: E402
from workflow.reference_convert import cxf_measurement_to_ti3        # noqa: E402

from tests.test_i1profiler_turned_export import _chart              # noqa: E402
from tests.test_i1profiler_turned_import import (                   # noqa: E402
    _expected_xyz, _mxf_from_txf, _plain_measurement, _xyz_by_sid)


# ---------------------------------------------------------------------------
# A real engine chart with its turned export, and a turned measurement of it
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def turned_source(tmp_path_factory):
    """One qualifying chart, its turned export, a turned .mxf and its .ti3,
    and what every chart patch reads as (the truth to check against)."""
    d = tmp_path_factory.mktemp("turned-doors")
    ti2 = _chart(d / "src", "Src", 350)
    res = T.write_turned_export(ti2, exports_subdir(ti2.parent), "Src")
    assert not res.skipped
    files = T.TurnedFiles(exports_subdir(ti2.parent), "Src")
    mxf = _mxf_from_txf(files.txf("i1Pro 3"), d / "turned.mxf")
    ti3 = cxf_measurement_to_ti3(mxf, d / "turned.ti3")
    truth_dir = d / "truth"
    truth_dir.mkdir()
    truth = _expected_xyz(ti2, truth_dir)
    return ti2, mxf, ti3, truth


def _place_chart(src_ti2: Path, folder: Path, stem: str) -> Path:
    """The chart's own files under *stem* in *folder*, and its turned export
    in ``folder/exports`` (as Create Chart leaves them)."""
    folder.mkdir(parents=True, exist_ok=True)
    for f in src_ti2.parent.iterdir():
        if f.is_file() and f.name.startswith(src_ti2.stem):
            shutil.copy2(f, folder / (stem + f.name[len(src_ti2.stem):]))
    ti2 = folder / f"{stem}.ti2"
    T.write_turned_export(ti2, exports_subdir(folder), stem)
    assert T.turned_order_for(ti2) is not None
    return ti2


def _project(work: Path, name: str, src_ti2: Path, *, with_measurement: bool):
    proj = Project.create(work / name, name)
    run = proj.current_run()
    run.ensure_dir()
    _place_chart(src_ti2, run.dir, run.stem)
    if with_measurement:
        _plain_measurement(run.chart_ti2, run.measurement_ti3, with_device=True)
    return proj, run


def _well_filed(filed: Path, chart: Path, truth: dict) -> None:
    """The filed copy pairs with its run's chart, by SAMPLE_ID, and every
    reading is the one its own patch gives."""
    v = assess(filed, chart)
    assert v.ok and not v.turned_order, v.reason
    from workflow.measurement_report import verify_patch_identity
    from workflow.ti3_analysis import parse_ti3
    ident = verify_patch_identity(parse_ti3(filed), chart)
    assert ident["verdict"] == "verified", ident
    assert _xyz_by_sid(filed) == truth
    assert T.TURNED_KEYWORD in filed.read_text(encoding="utf-8")


@pytest.fixture
def house(qapp, tmp_path, turned_source):
    """A real MainWindow over a scratch working folder with project "Turn",
    whose run 1 holds the turned chart AND a measurement already."""
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    work = tmp_path / "work"
    work.mkdir()
    src_ti2, mxf, ti3, truth = turned_source
    proj, run = _project(work, "Turn", src_ti2, with_measurement=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    s = AppSettings()
    s.set("custom_output_path", str(work))
    win = MainWindow(s)
    return win, work, proj, run, outside, turned_source


def _answer(monkeypatch, *, project="Turn", run_id="run1"):
    """Answer every window of the filing doors and record what they said."""
    import ui.dialogs.name_prompt as name_prompt
    import ui.dialogs.project_picker as project_picker
    import ui.measurement_filing as mf
    seen = {"refused": [], "info": [], "new_run": []}
    monkeypatch.setattr(project_picker, "choose_project",
                        lambda *a, **kw: project)
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **kw: project)
    monkeypatch.setattr("ui.tabs.tab_chart.TabChart._build_run_picker",
                        lambda self, peek: (None, [run_id]))
    monkeypatch.setattr(mf, "ask_to_make_a_new_run",
                        lambda parent, proj, run: (seen["new_run"].append(run.id)
                                                   or True))
    # The Print tab, handed the filed run's chart, asks whether to use it in
    # place; that question is not this file's subject.
    monkeypatch.setattr("ui.ti2_loader._choice_dialog",
                        lambda *a, **kw: "continue")
    monkeypatch.setattr(mf, "refuse_it_does_not_belong",
                        lambda parent, reason: seen["refused"].append(reason))

    class _Info:
        def __init__(self, title, body, *a, **kw):
            seen["info"].append((title, body))

        def exec(self):
            return 0
    monkeypatch.setattr(mf, "InfoDialog", _Info)
    return seen


def _the_only_new_run(proj_root: Path, before: "set[str]") -> Path:
    runs = {p.name for p in (proj_root / "runs").iterdir() if p.is_dir()}
    new = sorted(runs - before)
    assert len(new) == 1, (before, runs)
    return proj_root / "runs" / new[0]


# ---------------------------------------------------------------------------
# One test per door
# ---------------------------------------------------------------------------

def test_build_profile_files_a_turned_mxf_into_a_run_that_holds_one(
        house, monkeypatch):
    """S2, Build Profile: run 1 already holds a measurement, so a new run is
    made beside it; the turned .mxf lands there with every reading on its
    patch. Before the fix: refused, "360 of 360 patches do not hold..."."""
    win, work, proj, run, outside, (_s, mxf, _t, truth) = house
    seen = _answer(monkeypatch, run_id="run1")
    import ui.tabs.tab_profile as tp
    loose = outside / "turned.mxf"
    shutil.copy2(mxf, loose)
    before_bytes = loose.read_bytes()
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    monkeypatch.setattr(tp, "open_file_dialog", lambda *a, **k: str(loose))
    win._tab_profile._on_load_ti3()
    assert seen["refused"] == [], seen["refused"]
    assert seen["new_run"] == ["run1"]
    new_dir = _the_only_new_run(proj.root, before)
    filed = new_dir / "Turn.ti3"
    _well_filed(filed, new_dir / "Turn.ti2", truth)
    assert seen["info"] == [], "a well filed turned measurement raised a window"
    assert loose.read_bytes() == before_bytes, "the person's own file changed"


def test_build_profile_files_a_turned_mxf_into_a_new_run(house, monkeypatch):
    """S2, the "new run" answer: the run is duplicated from the one on the
    bar, which loses exports/ the same way."""
    win, work, proj, run, outside, (_s, mxf, _t, truth) = house
    seen = _answer(monkeypatch, run_id="")
    import ui.tabs.tab_profile as tp
    loose = outside / "turned.mxf"
    shutil.copy2(mxf, loose)
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    monkeypatch.setattr(tp, "open_file_dialog", lambda *a, **k: str(loose))
    win._tab_profile._on_load_ti3()
    assert seen["refused"] == [], seen["refused"]
    new_dir = _the_only_new_run(proj.root, before)
    _well_filed(new_dir / "Turn.ti3", new_dir / "Turn.ti2", truth)


def test_check_and_refine_files_a_turned_ti3_into_a_run_that_holds_one(
        house, monkeypatch):
    """S2, Check & Refine (its browse takes a .ti3, here the converted .mxf)."""
    win, work, proj, run, outside, (_s, _m, ti3, truth) = house
    seen = _answer(monkeypatch, run_id="run1")
    import ui.tabs.tab_check_refine as tcr
    loose = outside / "turned.ti3"
    shutil.copy2(ti3, loose)
    before_bytes = loose.read_bytes()
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    monkeypatch.setattr(tcr, "open_file_dialog", lambda *a, **k: str(loose))
    # The run has no profile yet, which Check & Refine warns about; not this
    # file's subject.
    monkeypatch.setattr(type(win._tab_check), "_auto_fill_icc",
                        lambda self, chosen: None)
    win._tab_check._on_browse_ti3()
    assert seen["refused"] == [], seen["refused"]
    assert seen["new_run"] == ["run1"]
    new_dir = _the_only_new_run(proj.root, before)
    _well_filed(new_dir / "Turn.ti3", new_dir / "Turn.ti2", truth)
    assert loose.read_bytes() == before_bytes


def test_the_new_project_door_files_a_turned_measurement_in_order(
        house, monkeypatch):
    """S1: a chart folder with its turned export and the measurement beside
    it, made into a new project. Before the fix it was filed silently with
    every reading on the wrong patch."""
    import ui.dialogs.project_picker as project_picker
    win, work, proj, run, outside, (src_ti2, _m, ti3, truth) = house
    seen = _answer(monkeypatch, project="Fresh")
    monkeypatch.setattr(project_picker, "choose_project",
                        lambda *a, **kw: project_picker.NEW_PROJECT)
    loose_dir = outside / "loose"
    _place_chart(src_ti2, loose_dir, "Loose")
    meas = loose_dir / "Loose.ti3"
    shutil.copy2(ti3, meas)
    before_bytes = meas.read_bytes()
    v = assess(meas, loose_dir / "Loose.ti2")
    assert v.ok and v.turned_order, "the pre-check must call it turned"
    import ui.tabs.tab_profile as tp
    monkeypatch.setattr(tp, "open_file_dialog", lambda *a, **k: str(meas))
    win._tab_profile._on_load_ti3()
    assert seen["refused"] == [], seen["refused"]
    run1 = work / "Fresh" / "runs" / "run1"
    _well_filed(run1 / "Fresh.ti3", run1 / "Fresh.ti2", truth)
    assert seen["info"] == []
    assert meas.read_bytes() == before_bytes, "the person's own file changed"


def test_the_measure_tab_files_a_turned_mxf_into_a_run_that_holds_one(
        qapp, tmp_path, turned_source, monkeypatch):
    """The door that always paired first: still does, into a new run."""
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.measurement_target import RUN_TYPE_PROFILING
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_measure import TabMeasure
    src_ti2, mxf, _t, truth = turned_source
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    proj, run = _project(tmp_path, "M", src_ti2, with_measurement=True)
    fm = FileManager(s)
    fm.set_target_name("M")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    seen = _answer(monkeypatch, project="M")
    monkeypatch.setattr(tab, "_show_import_done_profiling", lambda *a: None)
    monkeypatch.setattr(tab, "_say_on_screen",
                        lambda t, b: seen["info"].append((t, b)))
    monkeypatch.setattr(tab, "_ask_how_printed", lambda *a: None)
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    tab._import_into_profiling_run(ctl, fm.project().run("run1"), mxf)
    assert seen["refused"] == [], seen["refused"]
    new_dir = _the_only_new_run(proj.root, before)
    _well_filed(new_dir / "M.ti3", new_dir / "M.ti2", truth)


def test_there_is_no_tools_menu_door():
    """"…and Tools if any": no Tools-menu action imports a measurement; the
    four doors above are every caller of the shared filing code."""
    import inspect
    import ui.main_window as mw
    src = inspect.getsource(mw)
    assert "file_into_project" not in src
    assert "offer_import_into_a_project" not in src


# ---------------------------------------------------------------------------
# Tied to the chart, not to the switch (Sebastian, 2026-10-27)
# ---------------------------------------------------------------------------

def test_the_option_off_does_not_stop_a_chart_with_an_order_from_pairing(
        house, monkeypatch):
    """§I.14 belongs to the chart that has an order file, not to the current
    setting: switched off afterwards, the chart still pairs its turned
    measurement. Nothing in the import path reads the setting."""
    win, work, proj, run, outside, (_s, mxf, _t, truth) = house
    win._tab_profile._settings.set("i1profiler_turned_export", False)
    assert win._tab_profile._settings.get("i1profiler_turned_export") is False
    seen = _answer(monkeypatch, run_id="run1")
    import ui.tabs.tab_profile as tp
    loose = outside / "turned.mxf"
    shutil.copy2(mxf, loose)
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    monkeypatch.setattr(tp, "open_file_dialog", lambda *a, **k: str(loose))
    win._tab_profile._on_load_ti3()
    assert seen["refused"] == [], seen["refused"]
    new_dir = _the_only_new_run(proj.root, before)
    _well_filed(new_dir / "Turn.ti3", new_dir / "Turn.ti2", truth)
    import inspect
    from ui import measurement_filing
    from workflow import i1profiler_turned, measurement_import
    for mod in (measurement_import, measurement_filing):
        assert "i1profiler_turned_export" not in inspect.getsource(mod)
    for fn in (i1profiler_turned.turned_order_for, i1profiler_turned.turned_match,
               i1profiler_turned.reorder_turned_measurement):
        assert "i1profiler_turned_export" not in inspect.getsource(fn)


# ---------------------------------------------------------------------------
# Everything else is untouched
# ---------------------------------------------------------------------------

def test_without_an_order_file_the_pairing_step_does_nothing_at_all(
        tmp_path, turned_source, monkeypatch):
    """Option off (no order file): `TurnedPairing.first` hands the file back
    after one look for an order file. It neither judges nor copies it, and
    the chart is not even hashed."""
    import ui.measurement_filing as mf
    import workflow.measurement_import as mi
    src_ti2, _m, ti3, _truth = turned_source
    folder = tmp_path / "plain"
    folder.mkdir()
    for f in src_ti2.parent.iterdir():
        if f.is_file():
            shutil.copy2(f, folder / f.name)
    chart = folder / src_ti2.name
    meas = _plain_measurement(chart, tmp_path / "m.ti3", with_device=True)
    monkeypatch.setattr(mi, "assess", lambda *a, **k: pytest.fail("judged"))
    monkeypatch.setattr(T, "sha256_of", lambda *a, **k: pytest.fail("hashed"))
    with mf.TurnedPairing() as p:
        assert p.first(meas, chart) is meas
        assert p.first(ti3, chart) is ti3
        assert p._tmp is None and not p.paired
    assert T.turned_order_for(chart) is None


def test_an_ordinary_measurement_on_a_turned_chart_is_handed_back(
        tmp_path, turned_source):
    import ui.measurement_filing as mf
    src_ti2, *_ = turned_source
    chart = _place_chart(src_ti2, tmp_path / "c", "C")
    meas = _plain_measurement(chart, tmp_path / "m.ti3", with_device=True)
    with mf.TurnedPairing() as p:
        assert p.first(meas, chart) is meas
        assert not p.paired


def test_the_paired_copy_is_removed_when_the_door_ends(tmp_path, turned_source):
    import ui.measurement_filing as mf
    src_ti2, _m, ti3, _truth = turned_source
    chart = _place_chart(src_ti2, tmp_path / "c", "C")
    with mf.TurnedPairing() as p:
        copy = p.first(ti3, chart)
        assert copy != ti3 and copy.is_file() and p.paired
    assert not copy.exists() and not copy.parent.parent.exists()


def test_the_filed_copy_that_does_not_pair_is_said_not_left_silent(
        tmp_path, turned_source, monkeypatch):
    """S1's second half: if a door said "turned" and the filed copy then does
    not pair with its run's chart, a window says so."""
    import ui.measurement_filing as mf
    src_ti2, _m, ti3, _truth = turned_source
    folder = tmp_path / "run"
    folder.mkdir()
    for f in src_ti2.parent.iterdir():
        if f.is_file():
            shutil.copy2(f, folder / ("R" + f.name[len(src_ti2.stem):]))
    filed = folder / "R.ti3"
    shutil.copy2(ti3, filed)             # still in the turned order, no order
    shown = []
    monkeypatch.setattr(mf, "InfoDialog", lambda t, b, *a, **k: (
        shown.append((t, b)), type("D", (), {"exec": lambda s: 0})())[1])
    mf.say_what_was_filed(None, filed)
    assert shown == [], "an ordinary call must stay as it was"
    mf.say_what_was_filed(None, filed, turned=True)
    assert shown and "please check this measurement" in shown[0][0]
