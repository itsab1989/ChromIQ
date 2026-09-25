"""B8-1191: the beta 43 gate lost a worker to a SIGSEGV in
`QCoreApplicationPrivate::sendThroughObjectEventFilters`, from a timer, with
`workflow.preset_layout`'s background thread alive and idle in `queue.get`.

B8-1161 had already traced that crash class to a garbage collection running
on the background thread (a collection that finds a closed window in a
reference cycle finalises it on whatever thread collects), and switched
collection off while the thread had work. It let the THREAD switch it back
on after 5 s idle, and that was the hole: while collection is off the count
climbs far past the threshold, so the very next allocation after
``gc.enable()`` collects, and the next allocation was the thread's own, in
its idle loop. Measured before the fix: 5 of 5 script runs collected on that
thread at exactly that moment, and an everyday-tier run collected 2,024
objects there during a test that builds a Create Chart tab.

Now collection is held for the thread's whole life, taken by whoever hands
it work before the thread starts, and given back only by another thread once
it has ended.
"""
from __future__ import annotations

import gc
import threading
import time

import pytest

from workflow import preset_layout as PL

THREAD = "chromiq-preset-layout"


@pytest.fixture(autouse=True)
def _settled():
    PL._HOLD_UNTIL = 0.0
    PL.settle(30)
    assert gc.isenabled()
    yield
    PL.settle(30)


def _collections_by_thread():
    seen: list = []

    def cb(phase, _info):
        if phase == "start":
            seen.append(threading.current_thread().name)
    gc.callbacks.append(cb)
    return seen, cb


def test_no_collection_ever_runs_on_the_background_thread(monkeypatch):
    """A job, then the thread idles and ends while the main thread keeps
    making cyclic garbage (a closed window in a cycle is exactly that) and
    polls `pending()` the way the Create Chart tab's warming does.

    RED BEFORE THE FIX, measured: the thread gave collection back itself
    after its idle wait (shortened here from 5 s so the test is quick) and
    its own next allocation collected, on that thread (3 of 3 runs on
    439dfcf9). `release_gc_if_idle` giving it back while the thread is still
    alive is caught by the two tests below, not by this one."""
    monkeypatch.setattr(PL, "_GC_GIVE_BACK_IDLE_S", 0.3, raising=False)
    monkeypatch.setattr(PL, "_IDLE_EXIT_S", 0.3, raising=False)
    seen, cb = _collections_by_thread()
    try:
        PL.request(("b8-1191", "one"), lambda: [object() for _ in range(5000)])
        end = time.monotonic() + 3.0
        while time.monotonic() < end:
            for _ in range(300):
                a: list = []
                a.append(a)
            PL.pending()
            time.sleep(0.002)
    finally:
        gc.callbacks.remove(cb)
    assert THREAD not in seen, (
        f"{seen.count(THREAD)} garbage collection(s) ran on the background "
        f"thread; a closed window in a cycle would be finalised there")
    assert "MainThread" in seen, "the main thread never collected at all"
    assert gc.isenabled(), "automatic collection was never given back"


def test_collection_is_off_before_the_thread_runs_a_line():
    """The hold is taken by the caller, before the thread exists, so there
    is no moment at which the thread runs with collection on."""
    started = threading.Event()
    release = threading.Event()

    def job():
        started.set()
        release.wait(5)
    PL.request(("b8-1191", "hold"), job)
    try:
        assert not gc.isenabled(), "the hold was not taken by the caller"
        assert PL.gc_held()
        assert started.wait(5)
        # the main thread may not give it back while the thread is alive
        assert PL.release_gc_if_idle() is False
        assert not gc.isenabled()
    finally:
        release.set()
    assert PL.settle(10)
    assert gc.isenabled() and not PL.gc_held()


def test_a_collector_switched_on_behind_its_back_is_switched_off_again():
    """`core/sound.py` guards an import by switching collection off and
    restoring what it found; a restore that lands while the thread lives
    must not leave the thread collecting."""
    seen: list = []
    gate = threading.Event()

    def first():
        gate.wait(5)

    def second():
        seen.append(gc.isenabled())
    PL.request(("b8-1191", "a"), first)
    gc.enable()                       # somebody else's restore
    PL.request(("b8-1191", "b"), second)
    gate.set()
    assert PL.settle(10)
    assert seen == [False], seen


def test_no_job_is_lost_to_a_thread_that_is_ending(monkeypatch):
    """The thread ends after `_IDLE_EXIT_S` idle; work handed over at that
    very moment must still run. With the idle wait at zero the thread ends
    between almost every pair of jobs."""
    monkeypatch.setattr(PL, "_IDLE_EXIT_S", 0.0)
    done: list = []
    lock = threading.Lock()

    def job(i=0):
        with lock:
            done.append(i)
    for i in range(120):
        PL.request(("b8-1191", "race", i), lambda i=i: job(i))
        time.sleep(0.001 * (i % 7))
    assert PL.settle(30)
    assert sorted(done) == list(range(120))
    assert gc.isenabled()


def test_the_presets_window_module_starts_the_collector_timer():
    """Work handed over on the main thread starts the GUI collector timer
    (which gives collection back once the thread has ended), whoever hands
    it: an assessment that queues a printtarg layout included."""
    import ui.dialogs.preset_verification_dialog as PVD
    assert PL._HOLD_LISTENER is PVD.collect_on_this_thread
