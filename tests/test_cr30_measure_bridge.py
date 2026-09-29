"""The protocol discipline that answers `-xx` spot prompts (#159, Change B).

`workflow/cr30/measure_bridge.py` is the ONLY place a `{"cmd":"value"}` is
written, and every rule it enforces exists because breaking it corrupts data
silently. The device access is injected, so all of it is provable with no CR30
attached and no helper running:

 B.3  never send a value while no prompt is outstanding
 B.4  hold values while a navigation command is in flight
 B.5  key the latch on `loc` and on transitions, never on the event count
 B.6  verify the pairing after the fact and stop the read if it is wrong
 B.7  take the reading off the Qt main thread

`tests/test_cr30_external_values.py` proves the other side of the same channel
against the real binary.
"""
from __future__ import annotations

import gc
import threading
import time

import pytest
from PyQt6.QtCore import QCoreApplication, QThread
from PyQt6.QtWidgets import QApplication

from workflow.cr30 import measure_bridge
from workflow.cr30.measure_bridge import (DROPPED_NAVIGATING, DROPPED_NO_PROMPT,
                                          DROPPED_STALE_LOC, Cr30MeasureBridge)


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QCoreApplication.instance() or QApplication([])


class Harness:
    """A bridge with a controllable device and a recorded command channel."""

    def __init__(self, xyz=(10.0, 20.0, 30.0)):
        self.sent: list = []
        self.xyz = xyz
        self.read_calls: list = []
        self.threads: list = []
        self.gate = threading.Event()
        self.gate.set()                     # readings return at once by default
        self.raise_with: "Exception | None" = None
        self.bridge = Cr30MeasureBridge(self.sent.append, self._read)
        self.dropped: list = []
        self.failed: list = []
        self.mispaired: list = []
        self.bridge.reading_dropped.connect(
            lambda loc, why: self.dropped.append((loc, why)))
        self.bridge.read_failed.connect(
            lambda loc, msg: self.failed.append((loc, msg)))
        self.bridge.mispaired.connect(
            lambda a, b: self.mispaired.append((a, b)))
        self.lost: list = []
        self.gave_up: list = []
        self.bridge.device_lost.connect(
            lambda loc, msg: self.lost.append((loc, msg)))
        self.bridge.read_gave_up.connect(
            lambda loc, msg: self.gave_up.append((loc, msg)))

    def _read(self):
        self.read_calls.append(True)
        self.threads.append(QThread.currentThread())
        self.gate.wait(5)
        if self.raise_with is not None:
            raise self.raise_with
        return self.xyz

    def ready(self, loc, **kw):
        self.bridge.on_patch_ready({"loc": loc, "read": False,
                                    "all_done": False, **kw})
        self.settle()

    def settle(self, tries=400):
        """Let the worker thread finish and its queued signals be delivered."""
        app = QApplication.instance() or QCoreApplication.instance()
        for _ in range(tries):
            app.processEvents()
            if not self.bridge._threads and not self._pending():
                break
            QThread.msleep(2)
        app.processEvents()

    def _pending(self):
        return any(t.isRunning() for t, _w in self.bridge._threads)


# --- B.3: a value only ever answers an outstanding prompt -----------------

def test_a_prompt_is_answered_exactly_once():
    h = Harness()
    h.ready("A1")
    assert h.sent == [{"cmd": "value", "xyz": "10.000000 20.000000 30.000000"}]
    assert h.bridge.awaiting_loc is None, "the prompt is spent once answered"


def test_no_value_is_sent_before_any_prompt():
    """A value written ahead of its prompt is not queued and not refused — it
    is consumed by the wrong prompt or lost, and neither leaves a trace."""
    h = Harness()
    h.bridge._on_reading("A1", (1.0, 2.0, 3.0))
    assert h.sent == []
    assert h.dropped == [("A1", DROPPED_NO_PROMPT)]


def test_a_reading_for_a_patch_we_are_no_longer_on_is_dropped():
    h = Harness()
    h.ready("A1")
    h.bridge.on_patch_ready({"loc": "A2", "read": False, "all_done": False})
    before = len(h.sent)
    h.bridge._on_reading("A1", (1.0, 2.0, 3.0))     # late arrival for A1
    assert len(h.sent) == before
    assert h.dropped[-1] == ("A1", DROPPED_STALE_LOC)


def test_stop_ends_the_answering():
    h = Harness()
    h.bridge.stop()
    h.ready("A1")
    assert h.sent == [] and h.read_calls == []


# --- B.5: the latch is keyed on loc, never on the event count -------------

def test_a_repeated_prompt_for_the_same_patch_does_not_start_a_second_read():
    """`{"cmd":"ok"}` and `{"cmd":"retry"}` are not recognised by the
    external-value parser and simply loop the prompt, each producing a
    duplicate `spot_ready` for the SAME loc — and
    `MeasureManager.send_post_retry_key` sends `ok` from the existing
    failure-recovery UI, so this is reached by real users. A backend that
    counted events would send three values for one patch and lose two."""
    h = Harness()
    h.gate.clear()                          # hold the first reading open
    h.bridge.on_patch_ready({"loc": "A1", "read": False, "all_done": False})
    for _ in range(3):                      # the echoes
        h.bridge.on_patch_ready({"loc": "A1", "read": False, "all_done": False})
    h.gate.set()
    h.settle()
    assert len(h.read_calls) == 1, f"{len(h.read_calls)} reads for one patch"
    assert len(h.sent) == 1


def test_moving_on_does_start_a_new_read():
    """The counterpart: a genuine transition must not be swallowed."""
    h = Harness()
    h.ready("A1")
    h.ready("A2")
    assert len(h.read_calls) == 2
    assert [c["cmd"] for c in h.sent] == ["value", "value"]


def test_an_already_read_patch_is_not_re_read():
    """It is not re-read — but the session must not stop on it either. The
    helper advances by index, so on a resumed chart it lands on measured
    patches constantly; stopping on each one is the stall the owner hit."""
    h = Harness()
    h.ready("A1", read=True)
    assert h.read_calls == []
    assert h.sent == [{"cmd": "next_unread"}]


def test_all_done_is_not_a_patch_to_read():
    h = Harness()
    h.ready("F15", all_done=True)
    assert h.read_calls == [] and h.sent == []


# --- B.4: navigation in flight -------------------------------------------

def test_a_reading_arriving_during_a_jump_is_dropped():
    """Both orders of the measured bug: whichever way round, the reading used
    to land on the patch the user was trying to leave."""
    h = Harness()
    h.gate.clear()
    h.bridge.on_patch_ready({"loc": "A1", "read": False, "all_done": False})
    h.bridge.note_goto("B1")                # the user clicked B1
    h.gate.set()
    h.settle()
    assert h.sent == [], "A1's reading must not be sent after a jump to B1"
    assert h.dropped == [("A1", DROPPED_NAVIGATING)]
    assert h.bridge.navigating is True


def test_the_jump_settles_only_on_the_new_locs_own_prompt():
    """`_awaiting_loc` is settled by the `spot_ready` for the NEW loc, not by
    the next prompt of any kind — an inert command echoes the OLD one first."""
    h = Harness()
    h.bridge.note_goto("B1")
    h.bridge.on_patch_ready({"loc": "A1", "read": False, "all_done": False})
    h.settle()
    assert h.bridge.navigating is True, "A1's echo is not B1's prompt"
    assert h.read_calls == []
    h.ready("B1")
    assert h.bridge.navigating is False
    assert h.sent == [{"cmd": "value", "xyz": "10.000000 20.000000 30.000000"}]


# --- B.6: verify the pairing after the fact -------------------------------

def test_a_value_recorded_against_another_patch_stops_the_read():
    """`patch_read` carries its own `loc`. A mis-paired patch is a wrong
    colour in the .ti3 that nothing downstream can detect."""
    h = Harness()
    h.ready("B1")
    h.bridge.on_patch_measured({"loc": "A3", "xyz": [1, 2, 3]})
    assert h.mispaired == [("B1", "A3")]
    h.ready("C1")
    assert len(h.sent) == 1, "the read must stop, not carry on"


def test_the_ordinary_case_raises_nothing():
    h = Harness()
    h.ready("B1")
    h.bridge.on_patch_measured({"loc": "B1", "xyz": [1, 2, 3]})
    assert h.mispaired == []
    h.ready("B2")
    assert len(h.sent) == 2


def test_a_patch_read_with_no_loc_is_not_treated_as_a_mispairing():
    h = Harness()
    h.ready("B1")
    h.bridge.on_patch_measured({"xyz": [1, 2, 3]})
    assert h.mispaired == []


# --- B.7: off the Qt main thread -----------------------------------------

def test_the_reading_is_taken_off_the_main_thread():
    """Obtaining a CR30 reading waits on a human pressing the instrument's own
    button. On the main thread that freezes the preview the user is watching."""
    app = QApplication.instance() or QCoreApplication.instance()
    h = Harness()
    h.ready("A1")
    assert h.threads and all(t is not app.thread() for t in h.threads)


def test_the_worker_is_kept_referenced_until_it_finishes():
    """feedback_qthread_reference_lifetime: a QThread collected while running
    takes the process with it."""
    h = Harness()
    h.gate.clear()
    h.bridge.on_patch_ready({"loc": "A1", "read": False, "all_done": False})
    assert h.bridge._threads, "the thread must be held while it runs"
    h.gate.set()
    h.settle()
    assert h.bridge._threads == [], "…and released when it is done"


def test_the_read_thread_is_not_the_bridge_s_to_destroy():
    """A QThread PARENTED TO THE BRIDGE dies with the bridge, and a QThread
    destroyed while it is still running takes the process with it.

    Measured here, on this machine, with the same seven-line script run twice
    against the two versions of this module — bridge dropped while a read is
    held open, then the interpreter allowed to end:

        QThread(self)   ->  "QThread: Destroyed while thread '' is still
                            running", Abort trap: 6, exit 134
        QThread()       ->  exit 0

    On Windows that same `qFatal` is a FAIL-FAST (`0xC0000409`) which bypasses
    SEH, so faulthandler never runs, buffered output dies with the process, and
    pytest-xdist reports only `[gw0] node down: Not properly terminated` with no
    traceback anywhere. That is the gate crash `23dc8ea7` diagnosed; this file
    was one of the sites it did not reach.

    `self._threads` alone cannot prevent it, and that is the subtle part: the
    bridge, its `_threads` list, the thread, the `finished` connection and the
    lambda that closes back onto the bridge form a REFERENCE CYCLE, so the whole
    of it is freed at some arbitrary later moment — inside an unrelated test, or
    at interpreter shutdown — and whatever was running inside it is destroyed
    there. `workflow/cr30_spot_manager.py` refuses to parent its own read loop
    for exactly this reason and says so in the code; the bridge was never given
    the same treatment.

    So this asserts the invariant rather than the abort: no parent, and a
    reference held OUTSIDE the bridge until the thread reports itself finished.
    An abort cannot be asserted on — it takes the assertion with it.
    """
    h = Harness()
    gate = h.gate
    gate.clear()                            # hold the read open
    h.bridge.on_patch_ready({"loc": "A1", "read": False, "all_done": False})
    (thread, _worker), = h.bridge._threads
    assert thread.isRunning(), (
        "the read was over before the moment under test — this proved nothing")
    assert thread.parent() is None, (
        "the read thread is parented to the bridge again: dropping the bridge "
        "will destroy a running QThread and take the process down")
    assert any(t is thread for t, _w in measure_bridge._LIVE), (
        "nothing outside the bridge holds the thread, so the whole cycle is "
        "collectable while it is still running")

    del h
    gc.collect()
    assert thread.isRunning(), "the module global did not keep the thread alive"

    # …and it is released again, so this is a keep-alive and not a leak.
    gate.set()
    # `thread.wait()` would DEADLOCK here, and it is worth saying why: the
    # `quit()` that ends the read is connected as a plain Python callable, so
    # PyQt delivers it through a proxy whose affinity is the MAIN thread.
    # Blocking the main thread blocks the only thread that can stop this one.
    # `Harness.settle()` is the shape that works.
    app = QApplication.instance() or QCoreApplication.instance()
    deadline = time.monotonic() + 30.0
    while (thread.isRunning() or measure_bridge._LIVE) \
            and time.monotonic() < deadline:
        app.processEvents()
        QThread.msleep(2)
    assert not thread.isRunning(), "the read thread never finished"
    assert measure_bridge._LIVE == [], "a finished thread was never released"


# --- errors ---------------------------------------------------------------

def test_a_device_error_is_reported_and_sends_nothing():
    h = Harness()
    h.raise_with = RuntimeError("the magnet gate is set")
    h.ready("A1")
    assert h.sent == []
    assert h.failed, "a refused reading was not reported at all"
    assert all(loc == "A1" for loc, _ in h.failed)
    assert h.failed[0][1] == "the magnet gate is set"


def test_a_refused_reading_re_arms_so_the_session_survives(): 
    """The dead end: `_start_read` is called only from `on_patch_ready`, which
    runs only on a new `spot_ready`, which the helper sends only when it
    receives a command. So a failure that re-armed nothing left no reader and
    no prompt ever coming again — while the preview kept the patch highlighted
    and the message said "press the button on the instrument again".

    The way in is the likeliest first-run mistake there is: start with the
    magnetic cap on — where the instrument lives when idle — and patch A1 is
    refused by the magnet guard. One mistake, whole session dead.
    """
    h = Harness()
    h.raise_with = RuntimeError("the magnet gate is set")
    h.ready("A1")
    assert len(h.read_calls) > 1, (
        "a refused reading re-armed nothing — the session is a dead end and "
        "the button the user is told to press is connected to nothing")
    assert h.gave_up, "it retried for ever instead of eventually saying so"
    assert h.gave_up[0][0] == "A1"
    assert h.sent == []


def test_a_vanished_instrument_is_NOT_re_armed():
    """The opposite case, and it needs the opposite answer: re-arming would
    wait for a button on a device that cannot answer, and "press it again" is
    the wrong advice for an unplugged instrument."""
    from workflow.cr30.device import DeviceLost
    h = Harness()
    h.raise_with = DeviceLost("the instrument stopped answering")
    h.ready("A1")
    assert h.lost and h.lost[0][0] == "A1"
    assert len(h.read_calls) == 1, "it kept re-arming a device that is gone"
    assert h.gave_up == []


def test_a_patch_that_finally_works_starts_fresh():
    """Retries are per patch and spent by the operator, so a session where
    several patches each needed one retry is a session going fine."""
    h = Harness()
    h.raise_with = RuntimeError("no answer")
    h.ready("A1")
    assert h.gave_up
    h.raise_with = None
    h.ready("A2")
    assert len(h.sent) == 1
    assert h.bridge._retries.get("A2") is None


def test_an_unusable_reading_is_reported_and_sends_nothing():
    h = Harness(xyz=("not", "a", "number"))
    h.ready("A1")
    assert h.sent == []
    assert h.failed and h.failed[0][0] == "A1"


def test_a_failed_read_leaves_the_patch_readable_again():
    """The operator presses the button again; the prompt is still outstanding,
    so the retry must not be swallowed by the same-loc latch."""
    h = Harness()
    h.raise_with = RuntimeError("no answer")
    h.ready("A1")
    before = len(h.read_calls)
    h.raise_with = None
    h.ready("A1")                              # the helper re-offers it
    assert len(h.read_calls) > before
    assert len(h.sent) == 1


def test_a_prompt_with_no_loc_is_ignored():
    h = Harness()
    h.bridge.on_patch_ready({"read": False, "all_done": False})
    assert h.read_calls == [] and h.sent == []


# --- the tab's side of the wiring -----------------------------------------
# The bridge can be perfect and still never be consulted. These pin that the
# Measure tab feeds it BOTH spot signals and tells it about a jump BEFORE the
# command goes out — the ordering matters, because a reading can arrive between
# the two calls.

@pytest.fixture
def tab(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("chartread_engine", "chromiq")
    return TabMeasure(ArgyllRunner(s), s)


class _Spy:
    def __init__(self):
        self.ready, self.measured, self.gotos = [], [], []

    def on_patch_ready(self, ev):    self.ready.append(ev)
    def on_patch_measured(self, ev): self.measured.append(ev)
    def note_goto(self, loc):        self.gotos.append(loc)
    def stop(self):                  pass
    # The tab asks before it highlights, so that it can never point at a patch
    # nothing is listening to. This spy is always armed; the rule itself is
    # tested in test_cr30_can_re_read_a_patch.py.
    def armed_for(self, _loc):       return True


def test_the_tab_feeds_the_bridge_both_spot_signals(tab):
    spy = _Spy()
    tab._cr30_bridge = spy
    tab._on_patch_ready({"loc": "A1", "read": False, "all_done": False})
    tab._on_patch_measured({"loc": "A1", "xyz": [1, 2, 3], "exyz": [1, 2, 3],
                            "de": 0.1})
    assert [e["loc"] for e in spy.ready] == ["A1"]
    assert [e["loc"] for e in spy.measured] == ["A1"]


def test_the_tab_announces_a_jump_before_it_sends_it(tab, monkeypatch):
    """Order, not merely presence: a reading arriving between `note_goto` and
    the command would otherwise be sent against the patch being left."""
    order: list = []
    spy = _Spy()
    spy.note_goto = lambda loc: order.append(("note", loc))
    tab._cr30_bridge = spy
    monkeypatch.setattr(type(tab._manager), "engine_active",
                        property(lambda self: True))
    monkeypatch.setattr(type(tab._manager), "goto_patch",
                        lambda self, loc: order.append(("send", loc)))
    tab._on_preview_patch_clicked(0, "B1")
    assert order == [("note", "B1"), ("send", "B1")]


def test_a_chart_that_is_not_a_cr30_has_no_bridge_at_all(tab):
    """Nothing here may run for an instrument ArgyllCMS drives itself."""
    assert getattr(tab, "_cr30_bridge", None) is None
    tab._on_patch_ready({"loc": "A1", "read": False, "all_done": False})   # no raise


def test_closing_the_bridge_stops_it_and_releases_the_instrument(tab):
    closed: list = []
    stopped: list = []
    spy = _Spy()
    spy.stop = lambda: stopped.append(True)
    tab._cr30_bridge = spy
    tab._cr30_reader = type("R", (), {"close": lambda self: closed.append(True)})()
    tab._close_cr30_bridge()
    assert stopped == [True] and closed == [True]
    assert tab._cr30_bridge is None and tab._cr30_reader is None
