# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.54 release, the gate's hang (2026-11-21, and the same on 18 and 20 Nov): a table window's
first job call outlived the test person's wait under load, the Measure-tab fixture then deleted
the tab (and the panel, its child) under that running call, and the worker spun for good in
PyQt's slot-proxy destructor during pytest-qt's teardown processEvents. The app never deletes
the panel under a call (retire_window waits for the pool); the fixture now waits too.

These tests make a first job call slower than a short wait on purpose and go through the same
teardown, with a TIME LIMIT: if anything of this kind spins again, the test fails within two
minutes (the thread method ends the worker, which fails the run at once) instead of hanging a
gate for 50 minutes."""
from __future__ import annotations

import time

import pytest

from tests.i1io_table.test_window_in_the_measure_tab import beta, start, tab, table_run  # noqa: F401
from tests.i1io_table.window_person import WindowPerson
from tests.i1io_table.window_sim import WindowSim

pytestmark = pytest.mark.timeout(120, method="thread")


def test_a_call_still_running_at_the_end_of_a_test_is_waited_for_not_deleted_under(
        tab, beta, tmp_path, monkeypatch, qtbot):
    from PyQt6.QtWidgets import QDialog
    import ui.i1io_table_window as W
    run, sheet = table_run(tmp_path)
    monkeypatch.setattr(QDialog, "exec", lambda dlg: QDialog.DialogCode.Rejected)
    sim = start(tab, run, monkeypatch, WindowSim(delay_s=0.4))
    win = tab._table_window
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=1500))
    with pytest.raises(Exception):
        p.drive_until("end_of_session")          # the short wait gives up: a call still runs
    assert win._busy and W._pool().activeThreadCount() == 1
    # what the tab fixture now does at teardown, timed: the call ends, nothing spins
    t0 = time.time()
    win._finished = True
    win.close()
    assert W._pool().waitForDone(60000)
    qtbot.wait(200)
    assert time.time() - t0 < 60


def test_the_measure_tab_fixture_waits_for_the_pool_before_deleting_the_tab():
    import inspect
    from tests.i1io_table import test_window_in_the_measure_tab as M
    src = inspect.getsource(M.tab)
    assert src.index("W._pool().waitForDone(") < src.index("t.deleteLater()")
