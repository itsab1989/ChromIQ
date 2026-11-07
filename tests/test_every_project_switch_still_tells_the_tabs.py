"""Every route that switches the open project still tells the tabs, exactly
as before 4.3.28 (review of 2da6c9a9c, a blocker found by running).

4.3.28 took a TYPED project name off `controller.changed` (an unapplied
Create Chart change survived a keystroke, and a keystroke cost ~100 ms). The
first version took every change of the name field off it, and the review
found what that cost: opening project B while project A was open on the same
run id got its ONLY `changed` from the name the open writes into the field.
Without it the bar kept A's runs, Create Chart kept A's settings store and
wrote into the project the user had left, every tab missed the open, and the
next `changed` dropped B's patch-set binding (#147).

Now only `textEdited` (a person's edit) is quiet; a name the app writes into
the field emits `changed` as it always did. For every route, switching from A
(on run1) to B (on run1 too), this checks against the numbers 4.3.27
(5662136c1) produced, measured by running this file on that code:

* exactly the `changed` emissions 4.3.27 made,
* the bar lists B's runs,
* Create Chart's settings store is B's run and its settings were loaded,
* a later no-op `changed` drops no binding.

Some routes did not do all of that on 4.3.27 either, and are pinned as they
were, NOT changed (reported, not fixed): the #70 rename on leaving the field
and Generate with a typed new name emit no `changed` of their own and leave
Create Chart's store on the project left behind; a session restore made
while another project is open (the app restores at start-up, with nothing
open) emits none either; and after a patch set is loaded into a new project
a later no-op `changed` calls `_drop_preset_bindings`.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from core.file_manager import Project

#: The whole outcome of each route on 4.3.27 (5662136c1), measured with this
#: file (CHROMIQ_RECORD_ROUTES=1); paths relative to the work folder. The
#: typing in the rename and Generate routes is not counted: those records
#: are the step after it.
OLD = {
    'open_manifest': {"changed": 1, "settings_loaded": True, "project": "Bravo", "runs_on_bar": ["Run 1 (overwrite)", "Run 2 (overwrite)", "Run 3 (overwrite)", "New run"], "store": "Bravo/runs/run1", "no_op_drops_nothing": True},
    'measurement_import': {"changed": 1, "settings_loaded": True, "project": "Bravo", "runs_on_bar": ["Run 1 (overwrite)", "Run 2 (overwrite)", "Run 3 (overwrite)", "New run"], "store": "Bravo/runs/run1", "no_op_drops_nothing": True},
    'session_restore': {"changed": 0, "settings_loaded": False, "project": "Bravo", "runs_on_bar": ["Run 1 (overwrite)", "New run"], "store": "Alpha/runs/run1", "no_op_drops_nothing": False},
    'load_patch_set_new_project': {"changed": 1, "settings_loaded": True, "project": "Charlie", "runs_on_bar": ["Run 1 (overwrite)", "New run"], "store": "None", "no_op_drops_nothing": False},
    'load_patch_set_new_project[printtarg]': {"changed": 1, "settings_loaded": True, "project": "Charlie", "runs_on_bar": ["Run 1 (overwrite)", "New run"], "store": "None", "no_op_drops_nothing": False},
    'close_project': {"changed": 1, "settings_loaded": True, "project": None, "runs_on_bar": ["New run"], "store": "None", "no_op_drops_nothing": True},
    'rename_on_leaving_the_field': {"changed": 0, "settings_loaded": False, "project": None, "runs_on_bar": ["Run 1 (overwrite)", "New run"], "store": "Alpha/runs/run1", "no_op_drops_nothing": False},
    'generate_with_a_typed_new_name': {"changed": 0, "settings_loaded": False, "project": "Delta", "runs_on_bar": ["New run"], "store": "Alpha/runs/run1", "no_op_drops_nothing": False},
}

RECORD = os.environ.get("CHROMIQ_RECORD_ROUTES") == "1"


@pytest.fixture(autouse=True)
def _preferences_put_back(qapp):
    """Every preference a test here sets is put back afterwards, so no later
    file on this worker inherits a layout route, an output folder or a
    session (the 4.3.28 gate failure came from such an inheritance)."""
    from core.settings import AppSettings
    qs = AppSettings()._qs
    before = {k: qs.value(k) for k in qs.allKeys()}
    yield
    qs = AppSettings()._qs
    for k in qs.allKeys():
        if k not in before:
            qs.remove(k)
    for k, v in before.items():
        qs.setValue(k, v)
    qs.sync()


def _mk(work: Path, name: str, nruns: int) -> Project:
    p = Project.create(work / name, name)
    p.current_run().ensure_dir()
    for _ in range(nruns - 1):
        p.new_run().ensure_dir()
    p.set_current_run("run1")
    return p


def _settle(qapp, w, seconds=0.0):
    end = time.monotonic() + seconds
    while True:
        qapp.processEvents()
        tab = w._tab_chart
        busy = tab._chart_build_in_flight() or tab._runner.is_running
        if not busy and time.monotonic() >= end:
            break
        if time.monotonic() > end + 120:
            raise AssertionError("a build did not finish in 120 s")
        time.sleep(0.01)
    for _ in range(10):
        qapp.processEvents()


@pytest.fixture
def world(qapp, tmp_path, monkeypatch):
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    work = tmp_path / "work"
    work.mkdir()
    _mk(work, "Alpha", 1)
    _mk(work, "Bravo", 3)
    s = AppSettings()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("session_project", "")
    s.set("session_target_name", "")
    s.set("session_project_root", "")
    s.set("auto_update_preview", False)
    s.set("use_chromiq_layout_engine", True)     # the default, pinned
    w = MainWindow(s)
    w._tab_chart.open_project_manifest(work / "Alpha" / "project.json")
    _settle(qapp, w)
    w._tab_chart._user_switch_mode("manual")
    _settle(qapp, w)
    assert w._target_ctl.target.profile_run == "run1"
    assert w._target_ctl.project_or_none().root.name == "Alpha"
    yield w, work, s
    w.close()


class _Watch:
    """Counts `changed` and Create Chart's settings loads."""

    def __init__(self, w):
        self.changed = 0
        self.loads = 0
        w._target_ctl.changed.connect(self._on_changed)
        tab = w._tab_chart
        real = tab.load_target_settings

        def counting(*a, **k):
            self.loads += 1
            return real(*a, **k)
        tab.load_target_settings = counting

    def _on_changed(self):
        self.changed += 1

    def reset(self):
        self.changed = self.loads = 0


def _runs_on_the_bar(w):
    combo = w._target_bar._run_combo
    return [combo.itemText(i) for i in range(combo.count())]


def _store_dir(w):
    st = getattr(w._tab_chart, "_settings_store", None)
    d = getattr(st, "dir", None)
    return Path(d) if d is not None else None


def _no_op_changed_drops_nothing(w, qapp):
    tab = w._tab_chart
    dropped = []
    real = tab._drop_preset_bindings

    def spy(*a, **k):
        dropped.append(a)
        return real(*a, **k)
    tab._drop_preset_bindings = spy
    w._target_ctl.changed.emit()         # Restore Used Chart, a refresh
    for _ in range(20):
        qapp.processEvents()
    tab._drop_preset_bindings = real
    return not dropped


def _check(route, w, qapp, watch, work):
    """The route's whole outcome, compared with what 4.3.27 did."""
    proj = w._target_ctl.project_or_none()
    store = _store_dir(w)
    try:
        store = store.relative_to(work).as_posix() if store else "None"
    except ValueError:
        store = str(store)
    got = {
        "changed": watch.changed,
        "settings_loaded": watch.loads > 0,
        "project": proj.root.name if proj is not None else None,
        "runs_on_bar": _runs_on_the_bar(w),
        "store": store,
    }
    got["no_op_drops_nothing"] = _no_op_changed_drops_nothing(w, qapp)
    if RECORD:
        print(f"\nROUTE {route} {json.dumps(got)}")
        return got
    assert got == OLD[route], (
        f"{route} differs from 4.3.27:\n now {got}\n was {OLD[route]}")
    return got


# ---- the routes that switch from Alpha to Bravo -----------------------------

def test_open_project(world, qapp):
    """The masthead's Load Project, the menu and the recent list all end in
    `open_project_manifest` (`_load_existing_profile`)."""
    w, work, s = world
    watch = _Watch(w)
    w._tab_chart.open_project_manifest(work / "Bravo" / "project.json")
    _settle(qapp, w)
    _check("open_manifest", w, qapp, watch, work)


def test_measurement_import_opens_the_project(world, qapp):
    from ui.measurement_filing import open_the_project
    w, work, s = world
    watch = _Watch(w)
    got = open_the_project(w._tab_chart, w._file_mgr, "Bravo", work / "Bravo")
    _settle(qapp, w)
    assert got is not None
    _check("measurement_import", w, qapp, watch, work)


def test_session_restore(world, qapp):
    w, work, s = world
    s.set("session_target_name", "Bravo")
    s.set("session_project_root", str(work / "Bravo"))
    watch = _Watch(w)
    w._restore_last_session()
    _settle(qapp, w)
    _check("session_restore", w, qapp, watch, work)


@pytest.mark.parametrize("engine", [True, False],
                         ids=["layout-engine", "printtarg"])
def test_load_patch_set_into_a_new_project_with_a_real_build(world, qapp,
                                                              monkeypatch,
                                                              tmp_path,
                                                              engine):
    """Alpha is open on run1; the patch set goes into a NEW project, whose
    run is run1 too. A real build, on each of the two layout routes, pinned:
    the 4.3.28 gate ran this on a worker whose settings store an earlier file
    had left on printtarg, and printtarg refused the hand-written ONE-table
    .ti1 this test used to make ("Input file doesn't contain two or three
    tables", then the "Chart Layout Failed" window at teardown). The patch
    set is now written by the app's own writer, with the three tables
    targen makes."""
    from workflow.i1profiler_import import RgbPatch, write_ti1
    w, work, s = world
    tab = w._tab_chart
    s.set("use_chromiq_layout_engine", engine)
    ti1 = tmp_path / "mine" / "my-patches.ti1"
    ti1.parent.mkdir()
    write_ti1([RgbPatch(v, v, v) for v in (100.0, 75.0, 50.0, 25.0, 0.0)],
              ti1)
    monkeypatch.setattr("ui.tabs.tab_chart.open_file_dialog",
                        lambda *a, **k: str(ti1))
    monkeypatch.setattr(type(tab), "_ti1_load_destination",
                        lambda self, src: "new")
    monkeypatch.setattr("ui.ti2_loader._ask_project_name",
                        lambda *a, **k: ("Charlie", False))
    monkeypatch.setattr(type(tab), "_confirm_displacing_results",
                        lambda self, *a, **k: True)
    watch = _Watch(w)
    tab._on_load_ti1()
    _settle(qapp, w, seconds=0.5)
    charlie = work / "Charlie"
    assert (charlie / "project.json").is_file()
    run1 = Project.load(charlie).run("run1")
    assert run1.chart_ti2.is_file(), "the build wrote no chart"
    _check("load_patch_set_new_project" + ("" if engine else "[printtarg]"),
           w, qapp, watch, work)
    assert tab._preset_ti1_path is not None, "the loaded patch set is bound"


def test_close_project(world, qapp):
    w, work, s = world
    watch = _Watch(w)
    w.close_current_project()
    _settle(qapp, w)
    _check("close_project", w, qapp, watch, work)


# ---- the two routes that never had a `changed` of their own -----------------

def test_rename_on_leaving_the_field(world, qapp, monkeypatch):
    """#70: the rename chooser comes when the field loses focus. The typing
    before it is not counted; only the leaving."""
    from PyQt6.QtTest import QTest
    w, work, s = world
    tab = w._tab_chart
    monkeypatch.setattr(type(tab), "_handle_target_rename",
                        lambda self, new: True)
    field = tab._manual_target_name_edit
    QTest.keyClicks(field, "-2")
    _settle(qapp, w)
    watch = _Watch(w)
    field.editingFinished.emit()
    _settle(qapp, w)
    _check("rename_on_leaving_the_field", w, qapp, watch, work)


def test_generate_with_a_typed_new_name(world, qapp, monkeypatch):
    """A name nobody has used, typed, then Generate: the build adopts it.
    The build itself is not run; only what Generate does to the target."""
    from PyQt6.QtTest import QTest
    w, work, s = world
    tab = w._tab_chart
    field = tab._manual_target_name_edit
    field.selectAll()
    QTest.keyClicks(field, "Delta")
    _settle(qapp, w)
    monkeypatch.setattr(tab._creator, "generate", lambda *a, **k: None)
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: None)
    monkeypatch.setattr(type(tab), "_confirm_displacing_results",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(type(tab), "_handle_target_rename",
                        lambda self, new: True)
    watch = _Watch(w)
    tab._on_generate()
    for _ in range(20):
        qapp.processEvents()
    # What `_on_generate_finished` leaves behind (the build is patched out).
    tab._generate_btn.setEnabled(True)
    tab._layout_owned_by_build = False
    _check("generate_with_a_typed_new_name", w, qapp, watch, work)
