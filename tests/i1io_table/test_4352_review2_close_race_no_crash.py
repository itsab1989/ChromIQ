"""Review 2, M-1 (4.3.52): THE TABLE WINDOW NEVER LETS THE JOB'S THREAD WRITE INTO A DELETED
WINDOW.

The crash (a worker of the everyday tier, SIGSEGV, reproduced by the reviewer with exit 139):
the window handed the job ``self._signals.progress.emit``, a stored bound emit that keeps a raw
pointer to ``_Signals``, a child of the window. Deleting the window while a job call was still
running (qtbot's teardown after ``close()`` answered an open question on the job's thread; a
countdown; a row being read) and the job's thread then reaching its progress callback wrote
through a dead pointer. New on 4.3.52 only in that something now emits on the close path (the
sitting turning guided on a withdraw).

The fix (ui/i1io_table_window.py ``_JobRelay``): the job gets a plain callable of a relay; the
signals object has no Qt parent and lives as long as the relay, which the module keeps until the
job's pool is idle; every call checks an "open" flag under a lock; the window's ``_finish`` and
its ``destroyed`` close it; the tab deletes a finished panel only when the pool is idle
(``retire_window``).

The rounds run in a SUBPROCESS (close_race_rounds.py): on the old code a lost round is a
segfault, which must fail this test, not kill a worker of the suite.
MUTATIONS, proven red: the old line ``self.job.on_progress = self._signals.progress.emit``
(with ``_Signals(self)``) -> exit 139 in each of the three moments; the relay's flag never
closed -> "emitted ... into the window after it was deleted".
"""
from __future__ import annotations

import inspect
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from ui import i1io_table_window as W

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("case", ["question", "countdown", "running"])
def test_fifty_rounds_of_deleting_the_window_under_the_job_thread_never_crash(case):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", CLOSE_RACE_ROUNDS="50")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:xdist", "-o", "addopts=", "-q",
         "-p", "no:cacheprovider", "-k", case, "tests/i1io_table/close_race_rounds.py"],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=900)
    tail = "\n".join((r.stdout + r.stderr).splitlines()[-25:])
    assert r.returncode != -11 and r.returncode != 139 and "Fatal Python error" not in r.stderr, \
        f"{case}: the process CRASHED (exit {r.returncode}):\n{tail}"
    assert r.returncode == 0, f"{case}: the rounds did not finish green (exit {r.returncode}):\n" \
        + tail
    assert "50 passed" in r.stdout, tail


def test_the_job_is_never_handed_a_bound_emit_of_the_window():
    src = inspect.getsource(W)
    assert "on_progress = self._signals" not in src
    assert ".emit\n" not in src.replace(" ", "")      # no stored "x.emit" without a call
    build = inspect.getsource(W.TableMeasureWindow._build_job)
    assert "self.job.on_progress = self._relay.progress" in build
    init = inspect.getsource(W.TableMeasureWindow.__init__)
    assert "_Signals(self)" not in init                    # no Qt parent: the relay owns it
    assert "self.destroyed.connect(self._relay.detach)" in init
    assert "self._relay.detach()" in inspect.getsource(W.TableMeasureWindow._finish)
    assert "_JobCall(self._token, fn, self._relay)" in inspect.getsource(
        W.TableMeasureWindow._call)


def test_the_tab_deletes_a_finished_panel_only_through_retire_window():
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure.TabMeasure._on_table_window_finished)
    assert "retire_window(win)" in src and "win.deleteLater()" not in src


def test_the_relay_closes_and_emits_nothing_after(qapp):
    got = []
    relay = W._JobRelay()
    relay.signals.progress.connect(got.append)
    relay.progress({"event": "a"})
    qapp.processEvents()
    assert got == [{"event": "a"}]

    class Job:
        on_progress = None
    job = Job()
    job.on_progress = relay.progress
    relay.job = job
    relay.detach()
    assert job.on_progress is None and not relay.is_open
    relay.progress({"event": "b"})
    relay.done(1, None)
    qapp.processEvents()
    assert got == [{"event": "a"}]
    relay.detach()                                         # idempotent


def test_a_finished_panel_waits_for_an_idle_pool_and_never_blocks(qapp, monkeypatch):
    """retire_window: deleted at once when the pool is idle (as before); while a call runs it
    looks again on a timer (the GUI thread is never blocked) and, after the bound, keeps the
    panel rather than delete it under the call."""
    from PyQt6 import sip
    from PyQt6.QtCore import QEvent
    from PyQt6.QtWidgets import QApplication, QWidget

    class Pool:
        active = 1

        def activeThreadCount(self):  # noqa: N802 - Qt's name
            return self.active
    pool = Pool()
    monkeypatch.setattr(W, "_pool", lambda: pool)
    monkeypatch.setattr(W, "RETIRE_POLL_MS", 1)
    w = QWidget()
    W.retire_window(w)
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    assert not sip.isdeleted(w)                            # a call runs: not deleted
    pool.active = 0
    for _ in range(200):
        time.sleep(0.002)
        qapp.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        if sip.isdeleted(w):
            break
    assert sip.isdeleted(w)                                # the pool idle: deleted
    # the bound: kept, never deleted under a call
    monkeypatch.setattr(W, "RETIRE_TRIES", 3)
    pool.active = 1
    w2 = QWidget()
    W.retire_window(w2)
    for _ in range(50):
        time.sleep(0.002)
        qapp.processEvents()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    assert not sip.isdeleted(w2) and not W._RETIRING
    w2.deleteLater()
