"""Release review r6 of 4.3.18, N-2: a stop that times out must not strand
the next job.

`preset_layout._stop_worker(timeout)` sets `_STOP`, waits for the background
thread, and returns when the wait runs out even if the thread is still busy
with the job it was running. Before the fix that thread still counted as the
worker: the next `request` neither started a thread nor cleared `_STOP`, the
old thread ended straight after its job, and the new job sat in the queue with
nothing to run it. The suite's module fixture
(`conftest._the_presets_thread_ends_with_its_file`) stops the thread with a
30 s wait, so a job running longer than that under load would have left the
next file's first request waiting until its own timeout.

The fix is in the app (`_start_worker`): a set stop flag means the current
thread is ending, so a fresh one starts. And the old thread must never take
up the queue again beside it, which the second test pins.
"""
from __future__ import annotations

import threading
import time

import pytest

from workflow import preset_layout as PL


@pytest.fixture(autouse=True)
def _settled():
    PL._HOLD_UNTIL = 0.0
    PL.settle(30)
    yield
    PL.settle(30)


def _wait(cond, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def test_a_job_requested_after_a_timed_out_stop_still_runs():
    release = threading.Event()
    started = threading.Event()

    def slow():
        started.set()
        release.wait(10.0)

    PL.request(("r6-n2", "slow"), slow)
    assert started.wait(5.0), "the first job never started"
    old = PL._WORKER
    # the fixture's stop, with a wait far shorter than the running job
    PL._stop_worker(0.05)
    assert old.is_alive(), "the job was meant to outlast the stop's wait"
    assert PL._STOP.is_set()

    ran = threading.Event()
    PL.request(("r6-n2", "next"), ran.set)
    release.set()
    assert ran.wait(10.0), (
        "the job requested after a timed-out stop never ran: no thread was "
        "left to run it")
    assert PL.finished(("r6-n2", "next"))
    assert not PL._STOP.is_set()


def test_the_old_thread_never_runs_beside_its_successor():
    """Every job requested after the takeover is run by the new thread, and
    only once the old one has finished its last job: no two jobs ever
    overlap, as before the fix."""
    release = threading.Event()
    started = threading.Event()
    running = []
    overlap = []
    ran_on = []
    lock = threading.Lock()

    def job(name, block=False):
        def run():
            with lock:
                running.append(name)
                if len(running) > 1:
                    overlap.append(tuple(running))
            ran_on.append((name, threading.current_thread()))
            if block:
                started.set()
                release.wait(10.0)
            else:
                time.sleep(0.02)
            with lock:
                running.remove(name)
        return run

    PL.request(("r6-n2b", "slow"), job("slow", block=True))
    assert started.wait(5.0)
    old = PL._WORKER
    PL._stop_worker(0.05)
    for n in range(8):
        PL.request(("r6-n2b", n), job(n))
    new = PL._WORKER
    assert new is not old and new.is_alive()
    assert old in PL._RETIRING
    release.set()
    assert _wait(lambda: all(PL.finished(("r6-n2b", n)) for n in range(8)))
    assert _wait(lambda: not old.is_alive(), 5.0), "the old thread never ended"
    assert not overlap, f"two jobs ran at once: {overlap}"
    assert all(t is new for name, t in ran_on if name != "slow"), [
        (name, t.name) for name, t in ran_on]


def test_a_superseded_thread_hands_its_job_back():
    """The narrow case inside the loop: the old thread had already taken a
    job off the queue when the new one took over. It hands the job back
    rather than run it beside its successor."""
    me = threading.Thread(target=lambda: None)
    other = threading.Event()
    keeper = threading.Thread(target=other.wait, args=(5.0,), daemon=True)
    keeper.start()
    job = ("call", None, None, (("r6-n2c", 1), lambda: None))
    saved = PL._WORKER
    try:
        with PL._LOCK:
            PL._WORKER = keeper     # took over, which clears a stop's flag
            PL._STOP.clear()
        assert PL._still_the_worker(me, job) is False
        assert PL._QUEUE.get_nowait() == job
        # with a stop under way instead, the job is dropped as the stop drops
        # every queued one, and forgotten, so asking again queues it again
        # (fix round r7 of 4.3.18): put back, it outlived the stop's emptying
        # of the queue with nothing left to run it
        with PL._LOCK:
            PL._REQUESTED.add(("r6-n2c", 1))
            PL._STOP.set()
        assert PL._still_the_worker(me, job) is False
        assert PL._QUEUE.empty()
        assert not PL.queued(("r6-n2c", 1))
        # nobody else alive and no stop under way: the thread takes the
        # queue on again, so the job is not left behind
        with PL._LOCK:
            PL._WORKER = None
            PL._STOP.clear()
        assert PL._still_the_worker(me, job) is True
        assert PL._WORKER is me
    finally:
        other.set()
        keeper.join(5.0)
        with PL._LOCK:
            PL._WORKER = saved
