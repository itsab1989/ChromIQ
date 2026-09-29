"""A control-strip declaration belongs to its CHART, and follows it everywhere.

Knut, 2026-09-19, settling the question `workflow/control_strip.py` had left
open (*"whether a declaration should FOLLOW a user across a regenerate"*):

    *"The control strip declaration is tied to the chart it is made for, not
    the run. If the declaration exists, and measurement is started, that file
    shall also be backed up to chart/ folder (like other chart files), and if
    the Restore Used Chart button is pressed, the controls strip declaration
    shall also be restored with the other chart files. The delete function,
    when run type is set to verification, or when the profile run is selected
    which the verification belongs to (profile run = run1 etc.), then the
    delete button function shall also delete the controls strip declaration
    file. Also, the backup function that copies to old/ folder shall copy the
    controls strip declaration file if it exists."*

Four places, and when it was measured (B8-409) three of them were **already
right, by accident of how they were written and not by anything that held them
there**:

* the dated snapshot copies *everything* at the ``verifications/`` root,
* ``_clear_verify_chart_files`` archives ``<verify stem>*``,
* Delete moves a whole folder to the Trash.

Every one of those is a general mechanism that somebody could narrow next week
for a perfectly good reason, and nothing anywhere named this file. That is what
these guards are for: they fail if the declaration stops travelling, whichever
of the three gets narrowed. The fourth place was genuinely broken — a PROFILING
run's snapshot takes a NAMED list of suffixes and the declaration was not on it
— and its guard is the last two here.

**THE APP'S OWN SEQUENCE, END TO END.** The chart is built by real ``targen``
and ``printtarg``; the declaration is written by ``TabChart._on_generate_
finished``, the funnel every creation path reaches; the snapshot is taken by
``TabMeasure._snapshot_verification_chart``, which is the one call every
measurement start makes; the restore is ``MeasurementTargetController.
restore_used_chart``, which is what the button's slot calls; and Delete is
``delete_plan()`` followed by the very line the button runs. Nothing here
copies a file by hand.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core import run_delete as rd                         # noqa: E402
from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import control_strip as cs                  # noqa: E402
from workflow import measurement_report as mr             # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")

#: Big enough to fill the ladder well past ``CONTROL_STRIP_MIN`` — the point
#: here is the file's journey, not the ladder, which
#: `test_a_verification_chart_declares_its_control_strip.py` owns.
PATCHES = 100


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _argyll(tool: str) -> str:
    p = shutil.which(tool) or str(ARGYLL / tool)
    if not Path(p).exists():
        pytest.skip(f"Argyll {tool} not available")
    return p


def _build(d: Path, patches: int) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for cmd in ([_argyll("targen"), "-v", "-d2", f"-f{patches}", "-e4", "-B4",
                 "-G", "chart"],
                [_argyll("printtarg"), "-v", "-ii1", "-pA4", "-t300", "chart"]):
        subprocess.run([str(c) for c in cmd], cwd=str(d), check=True,
                       capture_output=True, timeout=300)
    ti2 = d / "chart.ti2"
    assert ti2.is_file()
    return ti2


@pytest.fixture(scope="module")
def chart(tmp_path_factory):
    """One real chart, built with ChartCreator's own manual-build flags."""
    return _build(tmp_path_factory.mktemp("decl-chart"), PATCHES)


@pytest.fixture(scope="module")
def other_chart(tmp_path_factory):
    """A second real chart, of a different size, so the two declare different
    strips and a declaration can be traced to the chart it came from."""
    return _build(tmp_path_factory.mktemp("decl-chart-b"), PATCHES + 61)


def _env(tmp_path):
    """A real project, a real FileManager, a real target controller."""
    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path / "s.ini"),
                             QSettings.Format.IniFormat)
    out = tmp_path / "ChromIQ"
    out.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(out))
    settings.set("argyll_bin_path", str(ARGYLL))
    fm = FileManager(settings)
    Project.create(out / "D", "D").current_run().ensure_dir()
    fm.set_target_name("D")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    return settings, fm, ctl


def _chart_tab(settings, fm, ctl):
    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(settings), fm, settings, None)
    tab.set_target_controller(ctl)
    return tab


def _measure_tab(settings, ctl):
    from ui.tabs.tab_measure import TabMeasure
    tab = TabMeasure(ArgyllRunner(settings), settings)
    tab.set_target_controller(ctl)
    return tab


def _generate_through_the_app(tab, fm, ctl, chart_ti2: Path, run_type: str,
                              monkeypatch) -> None:
    """Put the chart at the run root and let the app finish a generation.

    ``_on_generate_finished`` is the funnel every chart-creation path reaches,
    so this drives the adopt into ``verifications/``, the archive of whatever
    stood there, and the declaration, in the app's own order.
    """
    run = fm.project().current_run()
    run.ensure_dir()
    for ext in (".ti1", ".ti2"):
        src = chart_ti2.with_suffix(ext)
        if src.is_file():
            shutil.copyfile(src, run.artefact(ext))
    tif = run.dir / f"{run.stem}_01.tif"
    src_tif = next(p for p in chart_ti2.parent.glob("*.tif"))
    shutil.copyfile(src_tif, tif)
    monkeypatch.setattr("ui.tabs.tab_chart.InfoDialog",
                        lambda *a, **kw: type("D", (), {"exec": lambda s: 0})())
    monkeypatch.setattr(type(tab), "_warn_no_control_strip",
                        lambda self, n: None)
    ctl.set_run_type(run_type)
    tab._on_generate_finished([tif])              # THE APP'S OWN FUNNEL


def _declared_verify_chart(tmp_path, chart, monkeypatch):
    """A run whose verification chart really declares a control strip."""
    settings, fm, ctl = _env(tmp_path)
    tab = _chart_tab(settings, fm, ctl)
    _generate_through_the_app(tab, fm, ctl, chart, RUN_TYPE_VERIFICATION,
                              monkeypatch)
    run = fm.project().current_run()
    decl = cs.declaration_path(run.verify_chart_ti2)
    assert decl.is_file(), (
        "the app filed a verification chart without declaring a strip, so "
        "nothing below is measuring what it claims to")
    assert json.loads(decl.read_text(encoding="utf-8"))["sample_ids"]
    return settings, fm, ctl, run, decl


# --- 1. the chart/ snapshot a measurement takes -----------------------------

def test_a_verification_measurement_stores_the_declaration_with_the_chart(
        qapp, tmp_path, chart, monkeypatch):
    """Knut: *"If the declaration exists, and measurement is started, that file
    shall also be backed up to chart/ folder (like other chart files)."*"""
    settings, fm, ctl, run, decl = _declared_verify_chart(tmp_path, chart,
                                                          monkeypatch)
    tab = _measure_tab(settings, ctl)

    assert tab._snapshot_verification_chart() is True   # the app's own call

    v = run.verification(ctl.target.verification_id)
    stored = v.dir / "chart" / decl.name
    assert stored.is_file(), (
        "the measurement stored the chart and left its control-strip "
        "declaration behind: %s" % sorted(
            p.name for p in (v.dir / "chart").iterdir()))
    assert stored.read_bytes() == decl.read_bytes()


# --- 2. Restore Used Chart --------------------------------------------------

def test_restore_used_chart_puts_the_declaration_back_too(
        qapp, tmp_path, chart, monkeypatch):
    """Knut: *"if the Restore Used Chart button is pressed, the controls strip
    declaration shall also be restored with the other chart files."*"""
    settings, fm, ctl, run, decl = _declared_verify_chart(tmp_path, chart,
                                                          monkeypatch)
    tab = _measure_tab(settings, ctl)
    tab._snapshot_verification_chart()
    kept = decl.read_bytes()

    # The live chart moves on: a different declaration, and a different .ti2,
    # so the button is offered at all.
    decl.write_text(json.dumps({"name": "a later chart's strip",
                                "sample_ids": ["1"]}) + "\n", encoding="utf-8")
    run.verify_chart_ti2.write_text("A DIFFERENT CHART", encoding="utf-8")

    result = ctl.restore_used_chart()              # the button's own call

    assert result is not None and result.ok
    assert decl.read_bytes() == kept, (
        "Restore Used Chart put the chart back under the newer chart's "
        "control-strip declaration")


# --- 3. the old/ archive ----------------------------------------------------

def test_replacing_the_chart_archives_its_declaration_and_destroys_nothing(
        qapp, tmp_path, chart, monkeypatch):
    """Knut: *"the backup function that copies to old/ folder shall copy the
    controls strip declaration file if it exists."*

    Measured as already true when he ruled. It is guarded because
    ``_clear_verify_chart_files`` only catches the declaration through a
    ``<stem>*`` glob, and a narrower list would drop it silently.
    """
    settings, fm, ctl, run, decl = _declared_verify_chart(tmp_path, chart,
                                                          monkeypatch)
    first = decl.read_bytes()
    tab = _chart_tab(settings, fm, ctl)

    _generate_through_the_app(tab, fm, ctl, chart, RUN_TYPE_VERIFICATION,
                              monkeypatch)        # regenerate over it

    archived = list(run.verifications_old_dir.rglob("*" + mr.CONTROL_STRIP_SIDECAR))
    assert archived, (
        "the displaced chart was archived and its declaration was not: %s"
        % sorted(p.name for p in run.verifications_old_dir.rglob("*")))
    assert any(p.read_bytes() == first for p in archived), (
        "a declaration reached old/, but not the one that was displaced")


# --- 4. Delete --------------------------------------------------------------

def test_delete_with_run_type_verification_removes_the_declaration(
        qapp, tmp_path, chart, monkeypatch):
    """Knut: *"The delete function, when run type is set to verification …
    shall also delete the controls strip declaration file."*"""
    settings, fm, ctl, run, decl = _declared_verify_chart(tmp_path, chart,
                                                          monkeypatch)
    _measure_tab(settings, ctl)._snapshot_verification_chart()
    assert decl.is_file()

    plan = ctl.delete_plan()                       # the button's own plan
    assert plan.kind == rd.KIND_VERIFY_ALL, plan
    rd.delete_verification(plan)                   # the button's own call

    assert not decl.exists(), "the declaration outlived the delete"
    # ANYWHERE IN THE PROJECT, not just at the path it was deleted from: a
    # narrowing that moves the declaration out of the way and then deletes
    # around it satisfies a check on one path and leaves the file on the disk.
    assert not list(fm.project().root.rglob("*" + mr.CONTROL_STRIP_SIDECAR)), (
        "a copy of the declaration is still somewhere in the project")


def test_delete_of_the_profile_run_removes_the_declaration(
        qapp, tmp_path, chart, monkeypatch):
    """Knut: *"or when the profile run is selected which the verification
    belongs to (profile run = run1 etc.)."*"""
    settings, fm, ctl, run, decl = _declared_verify_chart(tmp_path, chart,
                                                          monkeypatch)
    _measure_tab(settings, ctl)._snapshot_verification_chart()
    proj = fm.project()
    proj.new_run()                       # a project always keeps one run
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)

    plan = ctl.delete_plan()
    assert plan.kind == rd.KIND_RUN, plan
    rd.delete_run(proj, plan)                      # the button's own call

    assert not decl.exists(), (
        "deleting the profile run left its verification chart's declaration "
        "on disk")
    assert not list(proj.root.rglob("*" + mr.CONTROL_STRIP_SIDECAR)), (
        "a copy of the declaration survived the delete elsewhere in the "
        "project")


# --- the fourth place, which was broken -------------------------------------

def test_a_profiling_run_stores_the_declaration_beside_its_chart(
        qapp, tmp_path, chart, monkeypatch):
    """A declaration is tied to the CHART, and a profiling chart can carry one.

    The Measurement Report reads a sidecar beside whatever chart a measurement
    is paired with, and the report window's own help text tells the user to
    write one. The profiling snapshot takes a named list of suffixes and this
    was not on it, so the copy came back without it.
    """
    settings, fm, ctl = _env(tmp_path)
    tab = _chart_tab(settings, fm, ctl)
    _generate_through_the_app(tab, fm, ctl, chart, RUN_TYPE_PROFILING,
                              monkeypatch)
    run = fm.project().current_run()
    decl = cs.declaration_path(run.chart_ti2)
    decl.write_text(json.dumps(                    # a user's own declaration
        {"name": "My press wedge",
         "sample_ids": [str(i) for i in range(1, 13)]}) + "\n",
        encoding="utf-8")

    assert _measure_tab(settings, ctl)._snapshot_verification_chart() is True

    stored = run.chart_snapshot_dir / decl.name
    assert stored.is_file(), (
        "the profiling run stored its chart without the declaration: %s"
        % sorted(p.name for p in run.chart_snapshot_dir.iterdir()))
    assert stored.read_bytes() == decl.read_bytes()


def test_restoring_a_profiling_chart_brings_its_declaration_with_it(
        qapp, tmp_path, chart, monkeypatch):
    """The other half: a restored chart must not come back under a later
    chart's declaration."""
    settings, fm, ctl = _env(tmp_path)
    tab = _chart_tab(settings, fm, ctl)
    _generate_through_the_app(tab, fm, ctl, chart, RUN_TYPE_PROFILING,
                              monkeypatch)
    run = fm.project().current_run()
    decl = cs.declaration_path(run.chart_ti2)
    decl.write_text(json.dumps(
        {"name": "My press wedge",
         "sample_ids": [str(i) for i in range(1, 13)]}) + "\n",
        encoding="utf-8")
    _measure_tab(settings, ctl)._snapshot_verification_chart()
    kept = decl.read_bytes()

    decl.write_text(json.dumps({"name": "a later chart's strip",
                                "sample_ids": ["1"]}) + "\n", encoding="utf-8")
    run.chart_ti2.write_text("A DIFFERENT CHART", encoding="utf-8")

    result = ctl.restore_used_chart()

    assert result is not None and result.ok
    assert decl.read_bytes() == kept, (
        "the profiling chart came back under the newer chart's declaration")


# --- the fault the on-screen run found --------------------------------------

def test_the_declaration_describes_the_chart_the_rebuild_guard_left_on_disk(
        qapp, tmp_path, chart, other_chart, monkeypatch):
    """Restoring a chart redraws its pages, and the redraw can lay the chart
    out again — so ``_ChartRebuildGuard`` puts the restored bytes back at the
    end of ``_on_generate_finished``. The declaration was written before that,
    from the chart the redraw had produced, and the guard then threw that chart
    away: the strip on disk named patches of a layout that no longer existed
    (measured on screen, 2026-09-19: 22 patches restored, 23 declared).

    A declaration is tied to the chart it is made for, so it must describe the
    chart the guard leaves behind.
    """
    from ui.tabs.tab_chart import _ChartRebuildGuard
    settings, fm, ctl, run, decl = _declared_verify_chart(tmp_path, chart,
                                                          monkeypatch)
    tab = _chart_tab(settings, fm, ctl)
    kept_ti2 = run.verify_chart_ti2.read_bytes()

    # Exactly what the restore path does before it redraws the pages.
    tab._rebuild_guard = _ChartRebuildGuard(run.verify_chart_ti2)
    # …and the redraw comes back with a DIFFERENT chart.
    _generate_through_the_app(tab, fm, ctl, other_chart, RUN_TYPE_VERIFICATION,
                              monkeypatch)

    assert run.verify_chart_ti2.read_bytes() == kept_ti2, (
        "the guard did not put the restored chart back, so this test is not "
        "measuring the case it describes")
    on_disk = cs.strip_for_chart(run.verify_chart_ti2).ids
    redrawn = cs.strip_for_chart(other_chart).ids
    assert on_disk != redrawn, (
        "the two charts declare the same strip, so nothing here could tell "
        "them apart")
    declared = json.loads(
        cs.declaration_path(run.verify_chart_ti2).read_text(
            encoding="utf-8"))["sample_ids"]
    assert declared == on_disk, (
        "the declaration beside the restored chart describes %d patches of a "
        "layout that is not on disk" % len(declared))
