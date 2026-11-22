"""4.3.57 (item 35, second part): a START is not a load event (per_target_settings.md §2).

Found on screen with the simulated table (2026-11-23, the coordinator's lead from the table
owner's photos of 22 Nov: "Patch-by-patch mode (-p)" and "Spectral filter type (-F)" cleared on
the Measure tab while the table ran, and a later START made without the dual scan): every
START emits ``measurement_active``; MainWindow passes it to the bar
(``MeasurementTargetController.set_measuring``), whose ``changed`` MainWindow also treats as
"a new target was selected" and so reloaded the Measure tab's STORED settings over the screen.
The hand path stores them first (W8), so it reloaded what was on screen; the table path stored
nothing (part 1 of this item), so the stale values came back over the person's ticks, after the
table's arguments had been built from the ticked boxes.

Now the bar says that such a ``changed`` is only the measuring flag, and MainWindow loads
nothing for it.
"""
from __future__ import annotations

from types import SimpleNamespace

from tests.i1io_table.test_window_in_the_measure_tab import (  # noqa: F401 - fixtures
    beta, start, tab, table_run)


def test_the_bar_marks_a_change_that_is_only_the_measuring_flag(qapp):
    from ui.measurement_target_bar import MeasurementTargetController
    ctl = MeasurementTargetController.__new__(MeasurementTargetController)
    from PyQt6.QtCore import QObject
    QObject.__init__(ctl)
    ctl._measuring = False
    seen = []
    ctl.changed.connect(lambda: seen.append(ctl.only_measuring_changed))
    ctl.set_measuring(True)
    ctl.set_measuring(False)
    assert seen == [True, True]
    assert ctl.only_measuring_changed is False


def test_mainwindow_loads_nothing_for_the_measuring_flag():
    from ui.main_window import MainWindow
    loads = []
    tab = SimpleNamespace(load_target_settings=lambda: loads.append(1))
    win = SimpleNamespace(_target_ctl=SimpleNamespace(only_measuring_changed=True),
                          _tabs=SimpleNamespace(currentWidget=lambda: tab))
    MainWindow._load_settings_of_visible_tab(win)
    assert loads == []
    win._target_ctl.only_measuring_changed = False
    MainWindow._load_settings_of_visible_tab(win)
    assert loads == [1]


def test_stale_stored_settings_never_reach_the_screen_at_a_table_start(tab, beta, tmp_path,
                                                                      monkeypatch):
    """The tab wired to a controller that reloads on ``changed`` (as MainWindow does): a table
    START with stale stored settings keeps the person's ticks."""
    from workflow.measure_settings import snapshot
    import ui.main_window as MW
    from ui.measurement_target_bar import MeasurementTargetController
    from PyQt6.QtCore import QObject
    ctl = MeasurementTargetController.__new__(MeasurementTargetController)
    QObject.__init__(ctl)
    ctl._measuring = False
    stale = {}
    store = SimpleNamespace(dir=str(tmp_path), id="t",
                            load_meta=lambda: SimpleNamespace(measure_settings=dict(stale)),
                            save_meta=lambda m: None)       # a store that never takes the save
    monkeypatch.setattr("workflow.per_target_settings.store_for_target", lambda _c: store)
    win = SimpleNamespace(_target_ctl=ctl, _tabs=SimpleNamespace(currentWidget=lambda: tab))
    ctl.changed.connect(lambda: MW.MainWindow._load_settings_of_visible_tab(win))
    tab.measurement_active.connect(ctl.set_measuring)
    run, _sheet = table_run(tmp_path)
    real_set = tab.set_ti1_path

    def set_then_tick(path):
        real_set(path)
        tab._m_pbp_cb.setChecked(True)
        stale.update({k: dict(v) for k, v in snapshot(tab).items()})
        stale["patch_by_patch"] = {"enabled": True, "value": False}    # what an old START left
    monkeypatch.setattr(tab, "set_ti1_path", set_then_tick)
    start(tab, run, monkeypatch)
    assert tab._table_window is not None
    assert tab._m_pbp_cb.isChecked() is True
