"""Build Profile after a project switch, the i1iO Beta (4.3.42 integration).

Found on screen by review 2 (job 2, 4a): work in project A (its run holds a
whole measurement), open project B whose run holds pages 1 and 3 of a
three-page i1iO chart and no measurement. The tab still held A's ``.ti3``
(`_on_target_changed` only ever *offers* what is on disk, and B's run has
nothing to offer), said "Ready to build" with Build enabled, and the pages
notice and refusal stood aside for it: one click would have built B's profile
from A's readings, with no word about the missing page.

Keeping a hand-loaded or earlier measurement when the new run has none is the
approved design (M-BUILD-ELSEWHERE, Knut 2026-08-04: "switching Profile run in
the bar loads it for you when the run has one"), so the measurement is not
cleared here. What changes: the pages notice and refusal stand aside only for
a measurement that lies inside the bar's own project.
"""
from __future__ import annotations

import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Project  # noqa: E402
from tests.test_i1io_measure_chart_pages import (  # noqa: E402,F401
    _drive, _import, _profiling, _sheet_file, beta_on, charts, qapp)
from tests.test_import_measurement_module import _tab  # noqa: E402


def _second_project(tmp_path, fm, ctl, ti2):
    """Project B beside A in the same output folder, its run 1 holding the
    same chart, the bar moved onto it (as Open Project does)."""
    Project.create(tmp_path / "B", "B").current_run().ensure_dir()
    fm.set_target_name("B")
    run = fm.project().run("run1")
    stem = ti2.name[:-4]
    for p in ti2.parent.iterdir():
        if p.is_file() and p.name.startswith(stem + "."):
            shutil.copy2(p, run.dir / (run.stem + p.name[len(stem):]))
    ctl.set_profile_run("run1")
    ctl.notify_changed()
    return run


def _profile_tab(s, ctl):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_profile import TabProfile
    prof = TabProfile(ArgyllRunner(s), s)
    prof.set_target_controller(ctl)
    return prof


@pytest.fixture
def a_then_b(charts, tmp_path, qapp, beta_on, monkeypatch):
    """A complete in project A, Build Profile holding it; then project B with
    page 2 of 2 imported. Yields (prof, run_a, run_b, s, fm, ctl)."""
    s, fm, ctl, run_a = _profiling(tmp_path, charts["two"])
    tab = _tab(s, fm, ctl)
    rec = _drive(tab, monkeypatch)
    prof = None
    try:
        tab._switch_mode("import")
        _import(tab, _sheet_file(run_a.chart_ti2, 1, tmp_path / "a1.cmxf"),
                _sheet_file(run_a.chart_ti2, 2, tmp_path / "a2.cmxf"))
        assert run_a.measurement_ti3.is_file(), rec
        prof = _profile_tab(s, ctl)
        prof._on_target_changed()
        assert prof._ti3_path == run_a.measurement_ti3
        a_label = prof._file_lbl.text()
        run_b = _second_project(tmp_path, fm, ctl, charts["two"])
        rec = _drive(tab, monkeypatch)
        _import(tab, _sheet_file(run_b.chart_ti2, 2, tmp_path / "b2.cmxf"))
        assert not rec["refused"], rec["refused"]
        assert not run_b.measurement_ti3.exists()
        assert run_b.i1io_page_ti3(2).is_file()
        ctl.notify_changed()
        yield prof, run_a, run_b, a_label, ctl, fm
    finally:
        tab.deleteLater()
        if prof is not None:
            prof.deleteLater()


def test_the_other_projects_measurement_stays_loaded_as_designed(a_then_b):
    prof, run_a, run_b, _a_label, _ctl, _fm = a_then_b
    # M-BUILD-ELSEWHERE's design: nothing on B's run to offer, so the tab
    # keeps what it held. Not cleared.
    assert prof._ti3_path == run_a.measurement_ti3


def test_the_file_line_names_the_missing_page_over_the_other_measurement(
        a_then_b):
    prof, _run_a, _run_b, _a_label, _ctl, _fm = a_then_b
    assert "Still to import: page 1." in prof._file_lbl.text()
    assert "not every page is imported yet" in prof._build_btn.toolTip()


def test_build_is_refused_with_the_pages_still_to_come(a_then_b, monkeypatch):
    prof, _run_a, run_b, _a_label, _ctl, _fm = a_then_b
    said = []
    monkeypatch.setattr(prof, "_show_tool_failure_dialog",
                        lambda t, b: said.append((t, b)))
    asked_elsewhere = []
    monkeypatch.setattr(prof, "_confirm_building_outside_the_selected_run",
                        lambda: asked_elsewhere.append(1) or False)
    prof._on_build()
    assert said and "Still to import: page 1." in said[0][1]
    assert not asked_elsewhere, "refused before any other question"
    assert not list(run_b.dir.glob("*.icc"))


def test_back_to_project_a_gives_the_file_line_back(a_then_b, monkeypatch):
    prof, run_a, _run_b, a_label, ctl, fm = a_then_b
    fm.set_target_name("P")
    ctl.set_profile_run("run1")
    ctl.notify_changed()
    assert prof._ti3_path == run_a.measurement_ti3
    assert prof._file_lbl.text() == a_label
    assert "not every page" not in prof._build_btn.toolTip()
    said = []
    monkeypatch.setattr(prof, "_show_tool_failure_dialog",
                        lambda t, b: said.append((t, b)))
    assert not prof._refused_while_i1io_pages_missing()
    assert not said


def test_a_measurement_inside_the_bar_project_still_steps_aside(
        a_then_b, monkeypatch, tmp_path):
    """As before the fix: a measurement of the bar's own project (here a
    copy in another run folder of B) is not blocked by the pages refusal;
    M-BUILD-ELSEWHERE asks about it on Build."""
    prof, run_a, run_b, _a_label, _ctl, _fm = a_then_b
    other = run_b.dir.parent / "run9"
    other.mkdir()
    own = other / run_a.measurement_ti3.name
    shutil.copy2(run_a.measurement_ti3, own)
    prof.set_ti3_path(own, propagate=False)
    prof._say_i1io_pages_missing()
    assert "Still to import" not in prof._file_lbl.text()
    assert not prof._refused_while_i1io_pages_missing()


def test_beta_off_changes_nothing(a_then_b, monkeypatch):
    prof, run_a, _run_b, _a_label, _ctl, _fm = a_then_b
    from workflow.i1io import support
    support.set_enabled_for_this_process(False)
    prof._say_i1io_pages_missing()
    assert "Still to import" not in prof._file_lbl.text()
    assert not prof._refused_while_i1io_pages_missing()
    assert prof._ti3_path == run_a.measurement_ti3
