"""R6 F2 — filing a measurement, then answering Cancel to a window nobody asked
for, must not empty the tab that just filed it.

Driven on screen (`d03_who_clears_check.py`): Check & Refine imports a `.ti3`
from outside every project, ChromIQ files it into `runs/run2/`, moves the bar
there — and then opens a *third-party* window offering to "copy the files to a
new subfolder so you can build a separate ICC profile". Cancel on it left the
tab holding nothing: the file field back to its placeholder, the ICC field
empty and ANALYSE PROFILE QUALITY disabled, with the measurement sitting on
disk in a run the tab could no longer name.

Two causes, and both are pinned here:

1. `tab_print.set_ti2_path` did not pass the controller to `resolve_ti2`, so
   every cross-tab propagation took the pre-#130 road and met the pre-#130
   window whatever the bar said.
2. `about_to_load_ti3` — the snapshot `MainWindow._restore_load_state` puts
   back — was emitted BEFORE the tab recorded the file, so the snapshot said
   "empty" and the restore wrote that over what had just been filed.

They RUN the code. A string assertion cannot see a tab being emptied.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import ui.ti2_loader as ti2_loader
from core.settings import AppSettings


@pytest.fixture
def house(qapp, tmp_path):
    """A real MainWindow over a scratch working folder with one real project
    open in it, and the run's own measurement + chart on disk."""
    from ui.main_window import MainWindow

    repo = Path(__file__).resolve().parents[1]
    work = tmp_path / "work"
    work.mkdir()
    shutil.copytree(repo / "demo-projects" / "Demo-Report-Matrix",
                    work / "Demo-Report-Matrix")

    s = AppSettings()
    s.set("custom_output_path", str(work))
    win = MainWindow(s)
    win._tab_chart.open_project_manifest(
        work / "Demo-Report-Matrix" / "project.json")
    run1 = work / "Demo-Report-Matrix" / "runs" / "run1"
    return win, run1 / "Demo-Report-Matrix.ti3", run1 / "Demo-Report-Matrix.ti2"


def _cancel_every_propagation(monkeypatch):
    """The person answers Cancel to whatever the propagation puts on screen."""
    monkeypatch.setattr(ti2_loader, "resolve_ti2", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# The harm itself
# ---------------------------------------------------------------------------

def test_cancel_downstream_leaves_check_and_refine_holding_the_file(
        house, monkeypatch):
    win, ti3, ti2 = house
    _cancel_every_propagation(monkeypatch)

    win._tab_check._adopt_ti3(ti3)

    assert win._tab_check.ti3_path == ti3, (
        "Cancel on a window the person did not ask for emptied the tab that "
        "had just filed the measurement")
    assert win._tab_check._ti3_edit.text() == str(ti3)


def test_cancel_downstream_leaves_build_profile_holding_the_file(
        house, monkeypatch):
    """The same shape on the other tab that adopts a filed measurement."""
    win, ti3, ti2 = house
    _cancel_every_propagation(monkeypatch)

    win._tab_profile._adopt_filed_ti3(ti3)

    assert win._tab_profile.ti3_path == ti3


def test_the_snapshot_is_taken_with_the_file_in_hand(house, monkeypatch):
    """The mechanism, so the two tabs cannot drift apart again: whatever
    `about_to_load_ti3` is connected to must see the file, because that is the
    state a cancelled propagation is restored to."""
    win, ti3, ti2 = house
    _cancel_every_propagation(monkeypatch)
    seen: list = []
    win._tab_check.about_to_load_ti3.connect(
        lambda: seen.append(("check", win._tab_check.ti3_path)))
    win._tab_profile.about_to_load_ti3.connect(
        lambda: seen.append(("profile", win._tab_profile.ti3_path)))

    win._tab_check._adopt_ti3(ti3)

    assert seen, "nothing snapshotted the state before the propagation"
    for who, held in seen:
        assert held == ti3, (
            f"{who} snapshotted itself as {held} while it was holding {ti3} — "
            f"a cancel restores that snapshot over the filed measurement")


# ---------------------------------------------------------------------------
# Cause 1 — the omitted controller
# ---------------------------------------------------------------------------

def test_a_cross_tab_chart_load_takes_the_130_road(house, monkeypatch):
    """`set_ti2_path` is Build Profile's only way into Print Chart, and it left
    the controller out — so a chart inside the OPEN project was handled by the
    pre-#130 "Load Test Session" window, which offers to duplicate the whole
    project into a subfolder."""
    win, ti3, ti2 = house
    took: list = []
    monkeypatch.setattr(ti2_loader, "_handle_inside",
                        lambda *a, **k: took.append("pre-#130") or None)
    monkeypatch.setattr(ti2_loader, "_handle_inside_current",
                        lambda *a, **k: took.append("#130") or None)

    win._tab_print.set_ti2_path(ti2)

    assert took == ["#130"], (
        f"the cross-tab propagation took the {took or ['no']} road; the tab's "
        f"own Browse passes the controller and this did not")


def test_every_resolve_ti2_call_site_passes_the_controller():
    """One call site missing an argument every sibling passes is how this
    happened; the next one is caught here rather than on screen."""
    import ast
    import inspect
    import ui.tabs.tab_measure as tab_measure
    import ui.tabs.tab_print as tab_print

    found = 0
    for module in (tab_print, tab_measure):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "resolve_ti2"):
                continue
            found += 1
            got = len(node.args) + len(node.keywords)
            assert got >= 4, (
                f"{module.__name__}:{node.lineno} calls resolve_ti2 with "
                f"{got} arguments — the controller is missing, so this "
                f"propagation takes the pre-#130 road")
    assert found >= 3, (
        f"only {found} resolve_ti2 call sites found; this test has gone blind")


# ---------------------------------------------------------------------------
# The restore must not invent what it did not record
# ---------------------------------------------------------------------------

def test_the_restore_does_not_invent_a_profile(house, monkeypatch):
    """`_restore_load_state` substituted `<ti3>.icc` when the snapshot had no
    profile in it. Analyse is enabled on the two paths alone, so that offers to
    analyse a file that does not exist."""
    win, ti3, ti2 = house
    win._load_state_snapshot = {
        "profile_ti3": None, "measure_ti2": None,
        "check_ti3": ti3, "check_icc": None,
    }

    win._restore_load_state()

    assert win._tab_check.ti3_path == ti3
    assert win._tab_check.icc_path is None, (
        "the restore invented a profile path the snapshot never held")
    assert win._tab_check._icc_edit.text() == ""
    assert not win._tab_check._run_btn.isEnabled(), (
        "Analyse is offered for a profile that does not exist")
