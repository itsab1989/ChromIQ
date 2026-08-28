"""#130: loading a patch set (.ti1) into the Create Chart tab is bar-aware.

With a profile project loaded the tab asks whether the patches should be laid
out INTO that project (Create Chart then follows the Profile-run bar) or start
their own new project named after the file. With no project loaded the file's
name simply seeds a new project — no dialog."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.file_manager import FileManager, Project              # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_tab(tmp_path):
    from core.argyll_runner import ArgyllRunner
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", False)
    fm = FileManager(s)
    tab = TabChart(ArgyllRunner(s), fm, s)
    ctl = MeasurementTargetController(fm)
    tab.set_target_controller(ctl)
    return tab, fm, ctl


def test_no_project_loaded_seeds_new_without_dialog(qapp, tmp_path):
    tab, fm, ctl = _make_tab(tmp_path)
    # No project on disk / current target is the auto name → treated as "new".
    assert tab._ti1_load_destination(Path("/some/where/MyPatches.ti1")) == "new"


def test_project_loaded_offers_new_vs_replace_on_an_existing_run(qapp, tmp_path,
                                                                monkeypatch):
    """#130, Knut's ruling of 2026-07-25: building into an EXISTING run always
    offers Replace / new run / new project, whatever that run holds — plus, since
    his ruling of 2026-07-27, "Replace only the chart", which swaps the chart and
    leaves the run's measurement and profile standing (see
    tests/test_load_chart_only.py)."""
    tab, fm, ctl = _make_tab(tmp_path)
    proj = Project.create(tmp_path / "projects" / "CanonP", "CanonP")
    proj.current_run().ensure_dir()
    fm.set_target_name("CanonP")
    ctl.set_profile_run(proj.current_run().id)

    import ui.ti2_loader as L
    seen = {}

    def _fake_dialog(parent, title, intro, choices):
        seen["keys"] = [c[2] for c in choices]
        seen["intro"] = intro
        return "into_replace"
    monkeypatch.setattr(L, "_choice_dialog", _fake_dialog)

    assert tab._ti1_load_destination(Path("/ext/Foreign.ti1")) == "into_replace"
    assert seen["keys"] == ["into_replace", "into_new", "into_chart", "new"]
    assert "CanonP" in seen["intro"]


def test_project_loaded_new_run_keeps_the_simple_choice(qapp, tmp_path, monkeypatch):
    """"New run" displaces nothing, so it keeps the two-way question."""
    tab, fm, ctl = _make_tab(tmp_path)
    proj = Project.create(tmp_path / "projects" / "CanonP", "CanonP")
    proj.current_run().ensure_dir()
    fm.set_target_name("CanonP")
    ctl.set_profile_run("")

    import ui.ti2_loader as L
    seen = {}

    def _fake_dialog(parent, title, intro, choices):
        seen["keys"] = [c[2] for c in choices]
        return "into"
    monkeypatch.setattr(L, "_choice_dialog", _fake_dialog)

    assert tab._ti1_load_destination(Path("/ext/Foreign.ti1")) == "into"
    assert seen["keys"] == ["into", "new"]


def test_project_loaded_cancel_returns_none(qapp, tmp_path, monkeypatch):
    tab, fm, ctl = _make_tab(tmp_path)
    proj = Project.create(tmp_path / "projects" / "P2", "P2")
    proj.current_run().ensure_dir()
    fm.set_target_name("P2")

    import ui.ti2_loader as L
    monkeypatch.setattr(L, "_choice_dialog", lambda *a, **k: None)
    assert tab._ti1_load_destination(Path("/ext/x.ti1")) is None


def test_port_announced_only_for_old_schema(qapp, tmp_path, monkeypatch):
    """#130 Model C: opening a pre-migration project announces the port; a
    current-schema project does not."""
    import json
    from core.file_manager import SCHEMA_VERSION
    import ui.tabs.tab_chart as T
    tab, fm, ctl = _make_tab(tmp_path)

    shown = {"n": 0}

    class _FakeInfo:
        def __init__(self, *a, **k):
            shown["n"] += 1
        def exec(self):
            return 0
    monkeypatch.setattr(T, "InfoDialog", _FakeInfo)

    old = tmp_path / "Old" / "project.json"
    old.parent.mkdir(parents=True)
    old.write_text(json.dumps({"schema_version": 1, "current_run": "run1", "runs": ["run1"]}))
    tab._maybe_announce_project_port(old)
    assert shown["n"] == 1                       # old project → announced

    new = tmp_path / "New" / "project.json"
    new.parent.mkdir(parents=True)
    new.write_text(json.dumps({"schema_version": SCHEMA_VERSION, "current_run": "run1", "runs": ["run1"]}))
    tab._maybe_announce_project_port(new)
    assert shown["n"] == 1                       # current schema → no extra dialog


def test_load_ti1_new_project_prompts_name_and_updates_field(qapp, tmp_path, monkeypatch):
    """#130 Bug 4 (Knut): loading a patch set and choosing 'Start a new project'
    prompts for the name (pre-filled, editable) AND updates the 'Printer profile
    project name' field so the new project is visibly loaded."""
    import ui.tabs.tab_chart as tc
    import ui.ti2_loader as L
    tab, fm, ctl = _make_tab(tmp_path)
    # A real Argyll .ti1 (used as-is, no conversion).
    ti1 = tmp_path / "MyPatches.ti1"; ti1.write_text("CTI1\n")
    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(ti1))
    monkeypatch.setattr(tab, "_ti1_load_destination", lambda src: "new")
    seen = {"prefill": None}

    def _ask(parent, default, working):
        seen["prefill"] = default
        return ("Chosen-Name", False)
    monkeypatch.setattr(L, "_ask_project_name", _ask)
    # Don't actually run targen/printtarg.
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: None)

    tab._on_load_ti1()

    assert seen["prefill"] == "MyPatches"          # pre-filled from the file
    assert fm.get_target_name() == "Chosen-Name"   # new name applied
    # The name field(s) now show the new project → it's visibly loaded.
    edits = [getattr(tab, "_target_name_edit", None),
             getattr(tab, "_manual_target_name_edit", None)]
    assert any(e is not None and e.text() == "Chosen-Name" for e in edits)


def test_load_ti1_new_project_cancel_aborts(qapp, tmp_path, monkeypatch):
    import ui.tabs.tab_chart as tc
    import ui.ti2_loader as L
    tab, fm, ctl = _make_tab(tmp_path)
    before = fm.get_target_name()
    ti1 = tmp_path / "P.ti1"; ti1.write_text("CTI1\n")
    monkeypatch.setattr(tc, "open_file_dialog", lambda *a, **k: str(ti1))
    monkeypatch.setattr(tab, "_ti1_load_destination", lambda src: "new")
    # CANCEL ANSWERS None, NOT (None, False). `_ask_project_name` only ever
    # returns None or a (name, replace) pair with a non-empty name — `_accept`
    # refuses an empty one (`ui/ti2_loader.py:783-784`). The old stub encoded a
    # shape the dialog cannot produce, written to fit a caller that unpacked the
    # answer before testing it; unpacking the REAL answer raised `TypeError` out
    # of a Qt slot and aborted the app. Both shapes are now guarded, and this
    # stubs the real one.
    monkeypatch.setattr(L, "_ask_project_name", lambda *a, **k: None)
    called = {"gen": 0}
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: called.__setitem__("gen", called["gen"] + 1))

    tab._on_load_ti1()

    assert called["gen"] == 0                      # cancelled → nothing generated
    assert fm.get_target_name() == before          # name unchanged
