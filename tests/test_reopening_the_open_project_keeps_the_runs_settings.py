"""OPENING THE PROJECT THAT IS ALREADY OPEN DOES NOT FILE THE CHART AS THE RUN'S OWN.

Open Project paints the run's chart over the Create Chart panel
(`_display_run_chart` -> `_restore_chart_settings`) and only then points the
bar at the project's current run. When that is the project and the run that
were open already, the bar does not move, so `_on_target_changed` (save
first, load the stored settings, shield the chart's values) never ran, and the
next tab change filed the chart's layout recipe as the run's own: a Manual
layout the user had saved but not generated (paper, margins, layout mode) was
silently replaced, and the "ChromIQ layout engine" tick could flip with it.

Found on screen (A4/38/26/area_first became Letter/6/6/patch_first after a
reopen and one tab change) and present since 4.1.x. Approved by Basti for
4.3.23: a reopen of the open target runs the same protected sequence as a
real target change. The screen stays as it was (the panel shows the chart's
own recipe, `per_target_settings.md` §2.2); only what is SAVED changes.

These drive the real main window and a real demo project.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

from core.settings import AppSettings

NAME = "Demo-Verify-History"
FIELDS = ("paper", "margin_top", "margin_left", "margin_bottom",
          "margin_right", "layout_mode", "layout_explicit")


def _pump(qapp, ms=150):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.005)


def _stored(project: Path) -> dict:
    meta = json.loads((project / "runs" / "run1" / "meta.json")
                      .read_text(encoding="utf-8"))
    ui = meta.get("create_chart_ui") or {}
    rec = ui.get("engine_recipe") or {}
    out = {f: rec.get(f) for f in FIELDS}
    out["engine_on"] = ui.get("engine_on")
    return out


def _chart_recipe(project: Path) -> dict:
    side = json.loads((project / "runs" / "run1" / f"{NAME}.channels.json")
                      .read_text(encoding="utf-8"))
    return side["layout"]["recipe"]


@pytest.fixture
def world(qapp, demo_projects_root, tmp_path, monkeypatch):
    """A real main window, with a copy of a demo project whose run 1 chart
    carries a full layout recipe in its sidecar."""
    work = tmp_path / "work"
    work.mkdir()
    project = work / NAME
    shutil.copytree(demo_projects_root / NAME, project)
    assert _chart_recipe(project).get("layout_mode"), (
        "the demo chart carries no layout recipe, so this proves nothing")
    # Nothing in these journeys should ask a question; if something does,
    # answer "no" rather than wait for a person.
    from PyQt6.QtWidgets import QDialog, QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    s = AppSettings()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("session_project", "")
    s.set("sound_enabled", False)
    from ui.main_window import MainWindow
    win = MainWindow(s)
    win.resize(1400, 900)
    yield win, project
    win.close()
    win.deleteLater()
    _pump(qapp, 50)


def _open(qapp, win, project):
    win._tabs.setCurrentWidget(win._tab_chart)
    win._tab_chart.open_project_manifest(project / "project.json")
    _pump(qapp, 400)


def _leave_and_return(qapp, win):
    """§3 W6: leaving Create Chart writes its settings."""
    win._tabs.setCurrentIndex(1)
    _pump(qapp, 200)
    win._tabs.setCurrentWidget(win._tab_chart)
    _pump(qapp, 200)


def _users_own_layout(qapp, win):
    """The user sets a Manual layout of their own, unlike the chart's, and
    turns the layout engine off, without generating anything."""
    tab = win._tab_chart
    panel = tab._manual_layout_panel
    chk = tab._manual_engine_check
    # From a known state: the tick is a preference too, and an earlier test
    # in this process may have left it either way.
    chk.setChecked(True)
    _pump(qapp, 100)
    rec = panel.get_recipe()
    rec.paper = "Letter"
    rec.margin_top = 38.0
    rec.margin_left = 26.0
    rec.layout_mode = "area_first"
    rec.layout_explicit = False
    panel.set_recipe(rec)
    panel.changed.emit()
    chk.setChecked(False)
    _pump(qapp, 200)


def _a_saved_layout_of_the_users_own(qapp, win, project) -> dict:
    _open(qapp, win, project)
    _leave_and_return(qapp, win)
    _users_own_layout(qapp, win)
    _leave_and_return(qapp, win)
    stored = _stored(project)
    chart = _chart_recipe(project)
    # The precondition: what is stored differs from the chart in every field
    # this file is about, or a drift to the chart could not be seen.
    assert stored["paper"] == "Letter" and stored["margin_top"] == 38.0, stored
    assert stored["layout_mode"] != chart["layout_mode"], (stored, chart)
    assert stored["margin_left"] != chart["margin_left"], (stored, chart)
    # Painting the chart forces "layout chosen explicitly" on; the user's own
    # layout here has it off, so a flip would show as well.
    assert stored["layout_explicit"] is False, stored
    assert stored["engine_on"] is False, stored
    return stored


def test_reopening_the_open_project_files_nothing_of_the_chart(qapp, world):
    win, project = world
    before = _a_saved_layout_of_the_users_own(qapp, win, project)
    chart = _chart_recipe(project)

    # Open the same project again, twice: the bar is already on run 1.
    _open(qapp, win, project)
    _open(qapp, win, project)

    # THE SCREEN IS AS IT WAS: the panel shows the chart's own recipe (§2.2).
    shown = win._tab_chart._manual_layout_panel.get_recipe()
    assert shown.layout_mode == chart["layout_mode"]
    assert shown.margin_left == chart["margin_left"]

    _leave_and_return(qapp, win)
    after = _stored(project)
    assert after == before, (
        "opening the project that was already open filed the chart's layout "
        f"as the run's own:\n  before {before}\n  after  {after}")


def test_a_change_after_the_reopen_is_the_only_thing_saved(qapp, world):
    win, project = world
    before = _a_saved_layout_of_the_users_own(qapp, win, project)
    _open(qapp, win, project)
    # The user nudges ONE margin on the panel, by hand.
    spin = win._tab_chart._manual_layout_panel.margins["b"]
    spin.setValue(spin.value() + 7.0)
    want = spin.value()
    _pump(qapp, 200)
    _leave_and_return(qapp, win)
    after = _stored(project)
    assert after["margin_bottom"] == want, after
    expected = dict(before, margin_bottom=want)
    assert after == expected, (
        f"more than the one edited field moved:\n  expected {expected}\n"
        f"  after    {after}")


def test_a_fresh_open_shows_the_chart_and_files_nothing_of_it(qapp, world):
    """The other route, nothing open before: the bar moves, so the open is a
    real target change. It ends as one (§2.2): the run's chart on screen and
    in the panel, the shield armed, so leaving the tab files nothing of the
    chart. (Checks behaviour; it used to spy on the reopen method, which
    does not exist on the code before it.)"""
    win, project = world
    before = _a_saved_layout_of_the_users_own(qapp, win, project)
    chart = _chart_recipe(project)
    raw = (project / "runs" / "run1" / "meta.json").read_bytes
    stored_bytes = raw()
    win._reset_after_project_gone(deleted=False)
    _pump(qapp, 300)
    assert win._target_ctl.project_or_none() is None

    _open(qapp, win, project)
    tab = win._tab_chart
    # The run's chart is what Create Chart shows and hands on…
    assert tab._shown_chart_ti2 is not None
    assert Path(tab._shown_chart_ti2).name == f"{NAME}.ti2"
    # …and what its panel shows, not the stored layout.
    shown = tab._manual_layout_panel.get_recipe()
    assert shown.layout_mode == chart["layout_mode"], shown.layout_mode
    assert shown.margin_left == chart["margin_left"], shown.margin_left
    assert shown.paper == chart["paper"], shown.paper
    _leave_and_return(qapp, win)
    assert raw() == stored_bytes, (
        f"the fresh open filed the chart as the run's own: {_stored(project)}")
    assert _stored(project) == before
