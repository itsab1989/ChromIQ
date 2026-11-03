"""OPENING A PROJECT NEVER WRITES THE TARGET IT LEAVES WITH THE CHART IT BRINGS.

Open Project paints the incoming project's chart over the Create Chart panel
(`_display_run_chart` -> `_restore_chart_settings`) and only then moves the bar
to that project's current run with Run type Profiling. Each bar setter emits
`about_to_change_target` BEFORE it changes the selection, which is the §2.1
write of the target being left, so that write filed the INCOMING chart's
recipe (paper, margins, layout mode, "layout chosen explicitly", the layout
engine tick) into the OUTGOING target:

  (a) Run type Verification, Open Project on the same project: the profiling
      chart's recipe landed in the run's verification settings;
  (b) the bar on another run of the same project: that run got the current
      run's chart recipe;
  (c) the bar on run 1 of one project, open another: the OTHER project's run 1
      got its current run's chart recipe, because the file manager had
      already switched when the write resolved "run 1".

Found while checking 0a6e1a9fe (the reopen of the open target, which does not
move the bar) and present since 4.1.x. Fixed for 4.3.23: the outgoing target
is written once, before the open starts and while its own screen is still up,
and nothing writes it again until the open has moved the bar. Both ways in are
covered: the masthead (Create Chart visible) and the Measure tab's import,
which opens a project and stays on Measure (its door opens only a project
that is not open already, so it drives (c); (a) and (b) are driven with the
same open and Measure on screen).

These drive the real main window and real demo projects; the incoming chart's
sidecar margins are tweaked so its recipe is unmistakable.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

from core.settings import AppSettings

FIELDS = ("paper", "margin_top", "margin_left", "margin_bottom",
          "margin_right", "layout_mode", "layout_explicit")
ROUTES = ("masthead", "measure")


def _pump(qapp, ms=150):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.005)


def _bytes(meta: Path) -> "bytes | None":
    return meta.read_bytes() if meta.is_file() else None


def _stored(meta: Path) -> dict:
    data = json.loads(meta.read_text(encoding="utf-8"))
    ui = data.get("create_chart_ui") or {}
    rec = ui.get("engine_recipe") or {}
    out = {f: rec.get(f) for f in FIELDS}
    out["engine_on"] = ui.get("engine_on")
    return out


def _tweak_sidecar(sidecar: Path, top: float, left: float) -> None:
    doc = json.loads(sidecar.read_text(encoding="utf-8"))
    rec = doc["layout"]["recipe"]
    rec["margin_top"] = top
    rec["margin_left"] = left
    sidecar.write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture
def world(qapp, demo_projects_root, tmp_path, monkeypatch):
    """A real main window over a working folder; *copy* puts a demo project in
    it. Nothing here should ask a question; if something does, answer "no"."""
    from PyQt6.QtWidgets import QDialog, QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    work = tmp_path / "work"
    work.mkdir()

    def copy(name: str) -> Path:
        dst = work / name
        shutil.copytree(demo_projects_root / name, dst)
        return dst

    s = AppSettings()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("session_project", "")
    s.set("sound_enabled", False)
    from ui.main_window import MainWindow
    win = MainWindow(s)
    win.resize(1400, 900)
    yield win, copy
    win.close()
    win.deleteLater()
    _pump(qapp, 50)


def _to_measure(qapp, win) -> None:
    """Put the Measure tab on screen with its own settings already filed for
    the selected target, so that the write the open owes the target it
    leaves (§2.1, which on this route is the Measure tab's) has nothing new
    to say, and anything else it writes shows."""
    if win._tabs.currentWidget() is win._tab_measure:
        return
    win._tabs.setCurrentWidget(win._tab_measure)
    _pump(qapp, 150)
    win._tabs.setCurrentIndex(1)
    _pump(qapp, 150)
    win._tabs.setCurrentWidget(win._tab_measure)
    _pump(qapp, 150)


def _open(qapp, win, project: Path, route: str = "masthead") -> None:
    if route == "masthead":
        # What MainWindow._on_masthead_load_project does around the file pick.
        win._tabs.setCurrentWidget(win._tab_chart)
        _pump(qapp, 100)
        win._tab_chart.open_project_manifest(project / "project.json")
    elif route == "measure":
        # The whole open with the Measure tab on screen, which is how the
        # import performs it (`measurement_filing.open_the_project` calls
        # `open_project_manifest` and stays on Measure).
        _to_measure(qapp, win)
        win._tab_chart.open_project_manifest(project / "project.json")
    else:
        # The import's own door. It opens only a project that is not open
        # already, so it is the route for (c).
        from ui.measurement_filing import open_the_project
        _to_measure(qapp, win)
        assert open_the_project(win._tab_measure, win._file_mgr,
                                project.name, project) is not None
    _pump(qapp, 400)


def _leave_and_return(qapp, win) -> None:
    """§3 W6: leaving Create Chart writes its settings."""
    win._tabs.setCurrentIndex(1)
    _pump(qapp, 200)
    win._tabs.setCurrentWidget(win._tab_chart)
    _pump(qapp, 200)


def _one_tab_change(qapp, win) -> None:
    """After the open, the user goes to Create Chart and leaves it again."""
    if win._tabs.currentWidget() is not win._tab_chart:
        win._tabs.setCurrentWidget(win._tab_chart)
        _pump(qapp, 200)
    _leave_and_return(qapp, win)


def _own_layout(qapp, win, top: float, left: float) -> None:
    """A Manual layout of the user's own, unlike any chart's, not generated."""
    tab = win._tab_chart
    panel = tab._manual_layout_panel
    chk = tab._manual_engine_check
    chk.setChecked(True)
    _pump(qapp, 100)
    rec = panel.get_recipe()
    rec.paper = "Letter"
    rec.margin_top = top
    rec.margin_left = left
    rec.layout_mode = "area_first"
    rec.layout_explicit = False
    panel.set_recipe(rec)
    panel.changed.emit()
    chk.setChecked(False)
    _pump(qapp, 200)


def _top(qapp, win, value: float) -> None:
    win._tab_chart._manual_layout_panel.margins["t"].setValue(value)
    _pump(qapp, 200)


def _settle(qapp, win, meta: Path) -> None:
    """Leave and come back until what is stored is what is on screen.

    With "Prioritise chart area" and no explicit layout the panel derives the
    margins itself, so the first visit after a hand-typed margin shows the
    derived one, and the next write files it. That is the ordinary rule of
    every write and not what these tests are about; they start from a
    target whose screen and store agree, so that anything the open writes
    into it shows."""
    for _ in range(3):
        before = _bytes(meta)
        _leave_and_return(qapp, win)
        if _bytes(meta) == before:
            return
    raise AssertionError(f"{meta} does not settle: {_stored(meta)}")


# ---- (a) Run type Verification, then Open Project on the same project ------

def _verification_world(qapp, win, copy):
    name = "Demo-Verify-History"
    project = copy(name)
    run = project / "runs" / "run1"
    _tweak_sidecar(run / f"{name}.channels.json", 12.0, 9.0)
    ctl = win._target_ctl
    _open(qapp, win, project)
    _leave_and_return(qapp, win)
    _own_layout(qapp, win, 38.0, 26.0)              # profiling's own
    _leave_and_return(qapp, win)
    ctl.set_run_type("verification")
    _pump(qapp, 400)
    _leave_and_return(qapp, win)
    _own_layout(qapp, win, 30.0, 20.0)              # verification's own
    _top(qapp, win, 30.0)
    _leave_and_return(qapp, win)
    assert ctl.target.is_verification()
    ver = run / "verifications" / "meta.json"
    _settle(qapp, win, ver)
    assert _stored(ver)["paper"] == "Letter", _stored(ver)
    return project, run / "meta.json", ver


@pytest.mark.parametrize("route", ROUTES)
def test_a_verification_store_is_not_written_by_the_open(qapp, world, route):
    win, copy = world
    project, prof, ver = _verification_world(qapp, win, copy)
    if route != "masthead":
        _to_measure(qapp, win)
    before = _bytes(ver)
    _open(qapp, win, project, route)
    assert win._target_ctl.target.run_type == "profiling"
    _one_tab_change(qapp, win)
    assert _bytes(ver) == before, (
        "Open Project wrote the verification settings it was leaving:\n"
        f"  now {_stored(ver)}")


# ---- (b) the bar on another run of the same project ------------------------

def _other_run_world(qapp, win, copy):
    name = "Demo-Full-RGB"
    project = copy(name)
    _tweak_sidecar(project / "runs" / "run3" / f"{name}.channels.json",
                   12.0, 9.0)
    ctl = win._target_ctl
    _open(qapp, win, project)
    assert ctl.target.profile_run == "run3", ctl.target.profile_run
    _leave_and_return(qapp, win)
    _own_layout(qapp, win, 38.0, 26.0)              # run3's own
    _leave_and_return(qapp, win)
    ctl.set_profile_run("run2")
    _pump(qapp, 400)
    _leave_and_return(qapp, win)
    _own_layout(qapp, win, 30.0, 20.0)              # run2's own
    _top(qapp, win, 30.0)
    _leave_and_return(qapp, win)
    m2 = project / "runs" / "run2" / "meta.json"
    m3 = project / "runs" / "run3" / "meta.json"
    _settle(qapp, win, m2)
    assert _stored(m2)["paper"] == "Letter", _stored(m2)
    return project, m2, m3


@pytest.mark.parametrize("route", ROUTES)
def test_b_the_run_the_bar_was_on_is_not_written_by_the_open(
        qapp, world, route):
    win, copy = world
    project, m2, _m3 = _other_run_world(qapp, win, copy)
    if route != "masthead":
        _to_measure(qapp, win)
    before = _bytes(m2)
    _open(qapp, win, project, route)
    assert win._target_ctl.target.profile_run == "run3"
    _one_tab_change(qapp, win)
    assert _bytes(m2) == before, (
        "Open Project wrote the run the bar was leaving:\n"
        f"  now {_stored(m2)}")


# ---- (c) the bar on run 1 of one project, another project opened ----------

def _two_projects_world(qapp, win, copy):
    x = copy("Demo-Full-RGB")
    y = copy("Demo-Legacy-v1")
    _tweak_sidecar(y / "runs" / "run2" / "Demo-Legacy-v1.channels.json",
                   17.0, 13.0)
    ctl = win._target_ctl
    _open(qapp, win, x)
    _leave_and_return(qapp, win)
    ctl.set_profile_run("run1")
    _pump(qapp, 400)
    _leave_and_return(qapp, win)
    _top(qapp, win, 30.0)
    _leave_and_return(qapp, win)
    _settle(qapp, win, x / "runs" / "run1" / "meta.json")
    return x, y


def _settings_in(meta: Path) -> set:
    if not meta.is_file():
        return set()
    data = json.loads(meta.read_text(encoding="utf-8"))
    return {k for k in ("create_chart_settings", "create_chart_ui",
                        "measure_settings") if data.get(k)}


@pytest.mark.parametrize("route", ROUTES + ("import",))
def test_c_the_other_projects_run1_is_not_written_by_the_open(
        qapp, world, route):
    win, copy = world
    x, y = _two_projects_world(qapp, win, copy)
    y1 = y / "runs" / "run1" / "meta.json"
    x1 = x / "runs" / "run1" / "meta.json"
    if route != "masthead":
        _to_measure(qapp, win)
    x_before = _bytes(x1)
    assert _settings_in(y1) == set(), "the demo's run 1 already has settings"
    _open(qapp, win, y, route)
    assert win._target_ctl.target.profile_run == "run2"
    _one_tab_change(qapp, win)
    assert _settings_in(y1) == set(), (
        "opening a project wrote its run 1, which nobody selected: "
        f"{sorted(_settings_in(y1))}")
    assert _bytes(x1) == x_before, "the project left behind was written"


# ---- the write the open does owe: the outgoing target's own edit ----------

def test_an_unsaved_edit_on_the_verification_lands_in_its_store_only(
        qapp, world):
    win, copy = world
    project, prof, ver = _verification_world(qapp, win, copy)
    prof_before, ver_before = _stored(prof), _stored(ver)
    assert ver_before["margin_top"] != 33.0
    _top(qapp, win, 33.0)            # typed, tab never left
    _open(qapp, win, project)
    want = dict(ver_before, margin_top=33.0)
    assert _stored(ver) == want, _stored(ver)
    _one_tab_change(qapp, win)
    assert _stored(ver) == want, _stored(ver)
    assert _stored(prof) == prof_before, (
        f"the edit reached the profiling store: {_stored(prof)}")


def test_an_unsaved_edit_on_the_other_run_lands_in_its_store_only(
        qapp, world):
    win, copy = world
    project, m2, m3 = _other_run_world(qapp, win, copy)
    m2_before, m3_before = _stored(m2), _stored(m3)
    assert m2_before["margin_top"] != 33.0
    _top(qapp, win, 33.0)            # typed on run 2, tab never left
    _open(qapp, win, project)
    want = dict(m2_before, margin_top=33.0)
    assert _stored(m2) == want, _stored(m2)
    _one_tab_change(qapp, win)
    assert _stored(m2) == want, _stored(m2)
    assert _stored(m3)["margin_top"] != 33.0, (
        f"run 2's edit reached run 3: {_stored(m3)}")


def test_an_unsaved_edit_in_the_project_left_lands_in_its_run_only(
        qapp, world):
    win, copy = world
    x, y = _two_projects_world(qapp, win, copy)
    x1 = x / "runs" / "run1" / "meta.json"
    x1_before = _stored(x1)
    assert x1_before["margin_top"] != 33.0
    _top(qapp, win, 33.0)            # typed on X run 1, tab never left
    _open(qapp, win, y)
    want = dict(x1_before, margin_top=33.0)
    assert _stored(x1) == want, _stored(x1)
    _one_tab_change(qapp, win)
    assert _settings_in(y / "runs" / "run1" / "meta.json") == set()
    assert _stored(x1) == want, _stored(x1)


# ---- the screen after an open that moves the bar (review r2B S1) ----------
#
# §2.2 (confirmed by Knut and Sebastian, 2026-09-10): selecting a run paints
# that run's chart over the Create Chart panel, and what the chart moved is
# noted so the next write files the run's own values. An open that ends on a
# run with a chart is held to the same rule (Basti's ruling, 2026-11-03). The
# open used to paint the chart and then let the bar move load the run's
# stored settings over it, where "already showing this chart" left them: the
# panel showed the stored Manual layout under the chart's preview, the log
# said the chart's own settings had been restored, and Generate would have
# built the stored layout. Each route below lands on a run whose stored
# layout (Letter, 38/26 mm, area first, engine off) differs from its chart's.

OPEN_ROUTES = ("cold", "other_run", "verification",
               "other_project", "other_project_measure",
               "other_project_import")


def _a_run_with_its_own_layout(qapp, win, copy, name, run_id):
    project = copy(name)
    _tweak_sidecar(project / "runs" / run_id / f"{name}.channels.json",
                   12.0, 9.0)
    _open(qapp, win, project)
    assert win._target_ctl.target.profile_run == run_id
    _leave_and_return(qapp, win)
    _own_layout(qapp, win, 38.0, 26.0)
    _leave_and_return(qapp, win)
    meta = project / "runs" / run_id / "meta.json"
    _settle(qapp, win, meta)
    assert _stored(meta)["paper"] == "Letter", _stored(meta)
    return project, meta


def _before_the_open(qapp, win, copy, route):
    """Set the scene for *route*; return (project to open, the incoming
    run's meta.json, the chart's sidecar recipe, how to open it)."""
    if route == "other_run":
        project, meta = _a_run_with_its_own_layout(
            qapp, win, copy, "Demo-Full-RGB", "run3")
        win._target_ctl.set_profile_run("run2")
        _pump(qapp, 400)
        _leave_and_return(qapp, win)
        how = "masthead"
    else:
        project, meta = _a_run_with_its_own_layout(
            qapp, win, copy, "Demo-Verify-History", "run1")
        how = "masthead"
        if route == "cold":
            win._reset_after_project_gone(deleted=False)
            _pump(qapp, 300)
            assert win._target_ctl.project_or_none() is None
        elif route == "verification":
            win._target_ctl.set_run_type("verification")
            _pump(qapp, 400)
            _leave_and_return(qapp, win)
        else:
            x = copy("Demo-Full-RGB")
            _open(qapp, win, x)
            _leave_and_return(qapp, win)
            win._target_ctl.set_profile_run("run2")
            _pump(qapp, 400)
            _leave_and_return(qapp, win)
            _settle(qapp, win, x / "runs" / "run2" / "meta.json")
            how = {"other_project": "masthead",
                   "other_project_measure": "measure",
                   "other_project_import": "import"}[route]
    side = project / "runs" / meta.parent.name / (
        f"{project.name}.channels.json")
    chart = json.loads(side.read_text(encoding="utf-8"))["layout"]["recipe"]
    return project, meta, chart, how


def _panel(win) -> dict:
    rec = win._tab_chart._manual_layout_panel.get_recipe()
    return {f: getattr(rec, f, None)
            for f in ("paper", "margin_top", "margin_left", "layout_mode")}


@pytest.mark.parametrize("route", OPEN_ROUTES)
def test_an_open_shows_the_runs_chart_in_the_panel(qapp, world, route):
    win, copy = world
    project, meta, chart, how = _before_the_open(qapp, win, copy, route)
    stored = _stored(meta)
    _open(qapp, win, project, how)
    tab = win._tab_chart
    assert win._target_ctl.target.profile_run == meta.parent.name
    assert win._target_ctl.target.run_type == "profiling"
    assert Path(tab._shown_chart_ti2).name == f"{project.name}.ti2"
    want = {f: chart[f] for f in
            ("paper", "margin_top", "margin_left", "layout_mode")}
    assert want != {f: stored[f] for f in want}, "nothing to tell apart"
    assert _panel(win) == want, (
        "after the open the Create Chart panel does not show the chart on "
        f"screen:\n  panel {_panel(win)}\n  chart {want}\n  stored {stored}")
    # …with the §2.2 shield armed, as after a run change.
    assert tab._chart_imposed, "the §2.2 shield is not armed"
    # The log says what the panel shows.
    assert "Restored the chart's own layout settings" in (
        tab._log.toPlainText())


# THE MEASURE AND IMPORT ROUTES WERE A STRICT XFAIL UNTIL 4.3.23 fix_final:
# entering Create Chart after the run change filed the chart's paper into
# printtarg -p, the run change's own older gap (4.3.22 had it). Loading the
# run's stored layout mirrored the panel's PREVIOUS paper, the chart's, into
# -p before the recipe's own paper arrived, so the §2.2 shield never saw -p
# move. The mirror now waits for the whole recipe (`_set_engine_recipe`);
# tests/test_4323_run_change_keeps_the_paper.py pins the plain run change.

@pytest.mark.parametrize("route", OPEN_ROUTES)
def test_after_an_open_a_tab_change_writes_nothing_into_the_run(
        qapp, world, route):
    """The §2.2 shield is armed: what the chart put on the panel is not
    filed as the run's own."""
    win, copy = world
    project, meta, _chart, how = _before_the_open(qapp, win, copy, route)
    before = _but_measure(meta)
    before_bytes = _bytes(meta)
    _open(qapp, win, project, how)
    assert win._tab_chart._chart_imposed, "the §2.2 shield is not armed"
    # Two tab changes: the second used to file the chart's paper into
    # printtarg -p (fixed in 4.3.23, fix_final).
    _one_tab_change(qapp, win)
    assert _but_measure(meta) == before, (
        f"the open's chart was filed as the run's own: {_stored(meta)}")
    _one_tab_change(qapp, win)
    assert _but_measure(meta) == before, (
        f"the second tab change filed the chart: {_everything_stored(meta)}")
    if how == "masthead":
        # Measure never left: the file itself, byte for byte.
        assert _bytes(meta) == before_bytes


def _but_measure(meta: Path) -> str:
    """meta.json as text without `measure_settings`. On the Measure and
    import routes the first tab change LEAVES Measure, and the Measure tab
    files its own settings into the opened run, which had none stored: its
    own §2.1 write, not Create Chart's. Everything else must be unchanged,
    byte for byte in its serialisation."""
    data = json.loads(meta.read_text(encoding="utf-8"))
    data.pop("measure_settings", None)
    return json.dumps(data, indent=2)


@pytest.mark.parametrize("route", ("cold", "other_run", "verification",
                                   "other_project"))
def test_an_edit_after_an_open_is_saved_as_the_users(qapp, world, route):
    win, copy = world
    project, meta, _chart, how = _before_the_open(qapp, win, copy, route)
    before = _everything_stored(meta)
    _open(qapp, win, project, how)
    spin = win._tab_chart._manual_layout_panel.margins["b"]
    spin.setValue(spin.value() + 7.0)
    want = spin.value()
    _pump(qapp, 200)
    _leave_and_return(qapp, win)
    after = _everything_stored(meta)
    assert after["ui.engine_recipe.margin_bottom"] == want, after
    moved = {k: (before.get(k), after.get(k))
             for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert set(moved) == {"ui.engine_recipe.margin_bottom"}, (
        f"more than the one edited value was saved: {moved}")


def _everything_stored(meta: Path) -> dict:
    """Every Create Chart value the run stores, flattened."""
    data = json.loads(meta.read_text(encoding="utf-8"))
    out = {}

    def walk(prefix, value):
        if isinstance(value, dict):
            for k, v in value.items():
                walk(f"{prefix}.{k}", v)
        else:
            out[prefix] = value

    walk("params", data.get("create_chart_settings") or {})
    walk("ui", data.get("create_chart_ui") or {})
    return out
