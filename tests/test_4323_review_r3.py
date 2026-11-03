"""4.3.23 final review (r3): the findings, each pinned.

B1  Open Project while Run type is Calibration ends on the project's
    calibration (an open resets only Verification), so the preview, Print
    Chart and Measure hold the CALIBRATION chart afterwards: with the bar
    moved to the opened project's current run (95828edc2 painted the run's
    profiling chart over the bar move's calibration chart) and with the bar
    already there (4.3.22 showed the profiling chart too). Profiling and
    Verification opens still show the current run's profiling chart.
M1  With the layout engine off, a printtarg -p set by hand survives a run
    change: the hidden layout panel's recipe paper is not mirrored into -p
    while the run's stored settings are being loaded. With the engine on,
    -p still follows the stored recipe.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

from core.settings import AppSettings


def _pump(qapp, ms=150):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.005)


def _make_world(qapp, demo_projects_root, tmp_path, monkeypatch, calibration):
    from PyQt6.QtWidgets import QDialog, QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    work = tmp_path / "work"
    work.mkdir()

    def copy(name):
        dst = work / name
        shutil.copytree(demo_projects_root / name, dst)
        return dst

    s = AppSettings()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("session_project", "")
    s.set("sound_enabled", False)
    s.set("calibration_mode", bool(calibration))
    from ui.main_window import MainWindow
    win = MainWindow(s)
    win.resize(1400, 900)
    handed = []
    win._tab_chart.chart_finished.connect(
        lambda tiffs, ti2, *_a: handed.append(
            (None if ti2 is None else Path(ti2), list(tiffs))))
    return win, copy, handed


@pytest.fixture
def cal_world(qapp, demo_projects_root, tmp_path, monkeypatch):
    win, copy, handed = _make_world(qapp, demo_projects_root, tmp_path,
                                    monkeypatch, True)
    yield win, copy, handed
    win.close()
    win.deleteLater()
    _pump(qapp, 50)


@pytest.fixture
def plain_world(qapp, demo_projects_root, tmp_path, monkeypatch):
    win, copy, handed = _make_world(qapp, demo_projects_root, tmp_path,
                                    monkeypatch, False)
    yield win, copy, handed
    win.close()
    win.deleteLater()
    _pump(qapp, 50)


def _same(a, b) -> bool:
    return a is not None and b is not None and \
        Path(a).resolve() == Path(b).resolve()


# ---------------------------------------------------------------------------
# B1: an open under Calibration shows the calibration chart
# ---------------------------------------------------------------------------

# (cross, bar run before the open). Demo-Full-RGB's current run is run3,
# Demo-Legacy-v1's is run2: run1 moves the bar in both projects, run3 leaves
# it in place in the same project, run2 leaves it in place in the other one.
CAL_CASES = [
    pytest.param(False, "run1", id="same-project-bar-moves"),
    pytest.param(False, "run3", id="same-project-bar-stays"),
    pytest.param(True, "run1", id="other-project-bar-moves"),
    pytest.param(True, "run2", id="other-project-bar-stays"),
]


@pytest.mark.parametrize("cross,bar_run", CAL_CASES)
def test_b1_an_open_under_calibration_shows_the_calibration_chart(
        qapp, cal_world, cross, bar_run):
    win, copy, handed = cal_world
    x = copy("Demo-Full-RGB")
    y = copy("Demo-Legacy-v1")
    tab = win._tab_chart
    ctl = win._target_ctl
    win._tabs.setCurrentWidget(tab)
    _pump(qapp, 100)
    tab.open_project_manifest(x / "project.json")
    _pump(qapp, 400)
    ctl.set_calibration_allowed(True)
    ctl.set_profile_run(bar_run)
    _pump(qapp, 300)
    ctl.set_run_type("calibration")
    _pump(qapp, 400)
    target = y if cross else x
    assert handed, "the calibration chart was handed on before the open"
    began = len(handed)
    tab.open_project_manifest(target / "project.json")
    _pump(qapp, 600)

    proj = ctl.project_or_none()
    assert Path(proj.root).resolve() == target.resolve()
    assert ctl.target.is_calibration(), "an open keeps Run type Calibration"
    cal = proj.calibration
    assert cal.ti2.is_file(), "the demo project carries a calibration chart"
    # The preview…
    assert _same(tab._shown_chart_ti2, cal.ti2), tab._shown_chart_ti2
    assert tab._preview.page_count() == len(cal.chart_tiffs())
    # …and what Print Chart and Measure were handed last (the same chart
    # needs no second hand-over when the open did not change it).
    assert _same(handed[-1][0], cal.ti2), handed[-1]
    # Never the run's profiling chart, at any point after the open began.
    run_ti2 = proj.current_run().chart_ti2
    assert not any(_same(t, run_ti2) for t, _ in handed[began:]), handed


PROF_CASES = [
    pytest.param(False, "run1", "profiling", id="same-project-bar-moves"),
    pytest.param(False, "run3", "profiling", id="same-project-bar-stays"),
    pytest.param(True, "run1", "profiling", id="other-project"),
    pytest.param(False, "run3", "verification", id="verification"),
]


@pytest.mark.parametrize("cross,bar_run,run_type", PROF_CASES)
def test_b1_profiling_and_verification_opens_show_the_runs_chart(
        qapp, plain_world, cross, bar_run, run_type):
    win, copy, handed = plain_world
    x = copy("Demo-Full-RGB")
    y = copy("Demo-Legacy-v1")
    tab = win._tab_chart
    ctl = win._target_ctl
    win._tabs.setCurrentWidget(tab)
    _pump(qapp, 100)
    tab.open_project_manifest(x / "project.json")
    _pump(qapp, 400)
    ctl.set_profile_run(bar_run)
    _pump(qapp, 300)
    if run_type == "verification":
        ctl.set_run_type("verification")
        _pump(qapp, 400)
    target = y if cross else x
    tab.open_project_manifest(target / "project.json")
    _pump(qapp, 600)

    proj = ctl.project_or_none()
    assert not ctl.target.is_calibration()
    assert not ctl.target.is_verification()
    run_ti2 = proj.current_run().chart_ti2
    assert _same(tab._shown_chart_ti2, run_ti2), tab._shown_chart_ti2
    assert handed and _same(handed[-1][0], run_ti2), handed


# ---------------------------------------------------------------------------
# M1: engine off, a hand-set -p survives a run change
# ---------------------------------------------------------------------------

def _tab_round(qapp, win):
    win._tabs.setCurrentIndex(1)
    _pump(qapp, 200)
    win._tabs.setCurrentWidget(win._tab_chart)
    _pump(qapp, 200)


def _stored_p(meta: Path):
    d = json.loads(meta.read_text())
    v = (d.get("create_chart_settings") or {}).get("printtarg-p")
    return v.get("value") if isinstance(v, dict) else v


def _stored_recipe_paper(meta: Path):
    d = json.loads(meta.read_text())
    rec = (d.get("create_chart_ui") or {}).get("engine_recipe") or {}
    return rec.get("paper")


@pytest.mark.parametrize("panel_paper", [None, "A3"],
                         ids=["panel-default-paper", "panel-A3"])
def test_m1_engine_off_a_hand_set_paper_survives_a_run_change(
        qapp, plain_world, panel_paper):
    win, copy, _handed = plain_world
    x = copy("Demo-Full-RGB")
    tab = win._tab_chart
    ctl = win._target_ctl
    win._tabs.setCurrentWidget(tab)
    _pump(qapp, 100)
    tab.open_project_manifest(x / "project.json")
    _pump(qapp, 400)
    ctl.set_profile_run("run1")
    _pump(qapp, 400)
    _tab_round(qapp, win)
    panel = tab._manual_layout_panel
    chk = tab._manual_engine_check
    # The hidden panel holds a recipe of its own (another instrument, maybe
    # another paper)…
    chk.setChecked(True)
    _pump(qapp, 100)
    panel.instr.setCurrentIndex(panel.instr.findData("CM"))
    _pump(qapp, 100)
    if panel_paper:
        panel.paper.setCurrentIndex(panel.paper.findData(panel_paper))
        _pump(qapp, 100)
    # …then the engine goes off and printtarg's paper is set by hand.
    chk.setChecked(False)
    _pump(qapp, 100)
    tab._set_manual_value("printtarg", "-p", "Letter")
    _pump(qapp, 100)
    _tab_round(qapp, win)
    _tab_round(qapp, win)
    m1 = x / "runs" / "run1" / "meta.json"
    assert _stored_p(m1) == "Letter"
    # Away to another run (engine on there, another instrument) and back.
    ctl.set_profile_run("run2")
    _pump(qapp, 400)
    _tab_round(qapp, win)
    chk.setChecked(True)
    _pump(qapp, 100)
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    _pump(qapp, 100)
    _tab_round(qapp, win)
    ctl.set_profile_run("run1")
    _pump(qapp, 400)
    _tab_round(qapp, win)
    _tab_round(qapp, win)
    assert _stored_p(m1) == "Letter"
    d = json.loads(m1.read_text())
    assert (d.get("create_chart_ui") or {}).get("engine_on") is False


def test_m1_engine_on_the_paper_still_follows_the_stored_recipe(
        qapp, plain_world):
    """The other half: with the engine on, the run's stored recipe paper is
    what printtarg -p shows and stores after a run change (56f21256a)."""
    win, copy, _handed = plain_world
    x = copy("Demo-Full-RGB")
    tab = win._tab_chart
    ctl = win._target_ctl
    win._tabs.setCurrentWidget(tab)
    _pump(qapp, 100)
    tab.open_project_manifest(x / "project.json")
    _pump(qapp, 400)
    ctl.set_profile_run("run1")
    _pump(qapp, 400)
    _tab_round(qapp, win)
    panel = tab._manual_layout_panel
    chk = tab._manual_engine_check
    chk.setChecked(True)
    _pump(qapp, 100)
    panel.paper.setCurrentIndex(panel.paper.findData("A3"))
    _pump(qapp, 100)
    _tab_round(qapp, win)
    m1 = x / "runs" / "run1" / "meta.json"
    assert _stored_recipe_paper(m1) == "A3"
    assert _stored_p(m1) == "A3"
    ctl.set_profile_run("run2")
    _pump(qapp, 400)
    _tab_round(qapp, win)
    panel.paper.setCurrentIndex(panel.paper.findData("A4"))
    _pump(qapp, 100)
    _tab_round(qapp, win)
    ctl.set_profile_run("run1")
    _pump(qapp, 400)
    _tab_round(qapp, win)
    _tab_round(qapp, win)
    assert _stored_p(m1) == "A3"
    assert _stored_recipe_paper(m1) == "A3"
