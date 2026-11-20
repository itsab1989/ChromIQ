"""Review 2, M-1 (4.3.52): the rounds that tried to crash the process. NOT collected by the suite
on its own (no ``test_`` in the file name): ``test_4352_review2_close_race_no_crash.py`` runs
this file in a SUBPROCESS, because on the old code a lost round is a SIGSEGV, and a segfault in
a worker would take every other test of that worker with it.

Each round opens the table window on the simulated table, gets the job's thread to the bad
moment and HOLDS it there (a hook in the job's progress callback waits), deletes the window on
the GUI thread exactly as qtbot's teardown does (close, deleteLater, DeferredDelete), and only
then lets the job's thread go on into the window's callback. Before the fix that callback was
a stored bound emit of ``_Signals``, a child of the deleted window: the job's thread wrote
through a dead pointer. After it, the job holds a relay whose signals object outlives the
window and which the window's destruction closed: nothing is emitted.

Three moments, ROUNDS rounds each (environment CLOSE_RACE_ROUNDS, default 50):
  question  the aim question open, unguided: close() answers it on the job's thread (the
            withdraw turns the sitting guided, which emits "turned_guided")
  countdown the 3 s countdown before a move is running on the job's thread
  running   a job call is running (a row being read)
"""
from __future__ import annotations

import os
import threading

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QApplication

from tests.i1io_table.test_4352_guidance_off import UNGUIDED_ANSWERS
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from tests.i1io_table.window_person import WindowPerson
from ui import i1io_table_window as W

ROUNDS = int(os.environ.get("CLOSE_RACE_ROUNDS", "50"))

#: the job's progress events that mean "this moment has come", per case
TRIGGER = {"question": None,                       # any event after the close
           "countdown": ("countdown",),
           "running": ("row_start", "patch_read", "move")}


def _drop_from_qtbot(request, win) -> None:
    """The window was deleted on purpose: qtbot's own teardown must not close it again."""
    node = request.node
    widgets = getattr(node, "qt_widgets", None)
    if widgets:
        node.qt_widgets = [w for w in widgets if w[0]() is not win]


@pytest.mark.parametrize("case", ["question", "countdown", "running"])
@pytest.mark.parametrize("i", range(ROUNDS))
def test_delete_the_window_while_the_job_thread_is_held(qtbot, monkeypatch, tmp_path, settings,  # noqa: F811
                                                        request, case, i):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    guided=False)
    p.script.update(UNGUIDED_ANSWERS)
    job = win.job
    real = job.on_progress
    assert real is not None
    reached, deleted = threading.Event(), threading.Event()
    armed = [case != "question"]          # "question": armed only once the question is open
    held = []
    after_delete = []
    sig = win._signals
    # every emit that leaves through the window's signals object, counted on the emitting
    # thread itself (a direct connection to a plain function, never into the window)
    emits = []
    sig.progress.connect(emits.append, Qt.ConnectionType.DirectConnection)

    def hook(ev):
        if armed[0] and not reached.is_set():
            want = TRIGGER[case]
            if want is None or ev.get("event") in want:
                held.append(ev.get("event"))
                reached.set()
                deleted.wait(10)           # the GUI thread deletes the window now
                n = len(emits)
                real(ev)                   # ... and only then the window's callback runs
                after_delete.append(len(emits) - n)
                return
        if deleted.is_set():
            n = len(emits)
            real(ev)
            after_delete.append(len(emits) - n)
            return
        real(ev)
    job.on_progress = hook

    def wait(cond):
        qtbot.waitUntil(lambda: reached.is_set() or cond(), timeout=15000)
    person = WindowPerson(win, sim, wait, script=dict(p.script))

    if case == "question":
        person.drive_until(["aimed"])
        assert win._page_id == "aimed"
        armed[0] = True
        win.close()                        # answers the open question on the job's thread
    else:
        for _ in range(400):
            if reached.is_set():
                break
            try:
                person.answer_page()
            except AssertionError:
                if not reached.is_set():   # the moment came while a page was being read
                    raise
    qtbot.waitUntil(reached.is_set, timeout=15000)
    # the bad moment: the job's thread waits inside its progress call; the window goes
    win.close()
    win.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    from PyQt6 import sip
    assert sip.isdeleted(win), "the window was not deleted (the round tested nothing)"
    _drop_from_qtbot(request, win)
    deleted.set()
    assert W._pool().waitForDone(30000), "the job call never ended"
    QApplication.processEvents()
    assert held, "the job's thread never reached the moment"
    assert sum(after_delete) == 0, (
        f"the job's thread emitted {sum(after_delete)} time(s) into the window after it was "
        f"deleted ({case}, held at {held})")
