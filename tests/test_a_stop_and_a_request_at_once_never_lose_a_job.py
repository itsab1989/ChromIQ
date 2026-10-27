"""Fix round r7 of 4.3.18: a stop and a request from two threads at the same
moment must not lose the job that was requested.

`preset_layout._stop_worker` used to set `_STOP` outside `_LOCK`, put its
wake-up `None` on the queue, wait for the threads, and then empty the queue,
again outside the lock. A `request` from another thread in between saw the
flag, started a fresh worker (which clears the flag), queued its job and
returned; then the stop emptied the queue and dropped that job, which was
asked for AFTER the stop. Or the fresh worker took the stop's `None`, read it
as "end", and left the job in the queue with no thread to run it. Either way
the caller waited for a job that was never going to run.

Now the flag, the worker, the wake-up and the queue change hands under one
lock: a request is wholly before a stop (its job is dropped, and `queued()`
says so, so it may be asked for again) or wholly after it (its job runs). The
test hammers both from two threads and asserts that every key ends up run
exactly once, that no caller is left waiting on a job nothing will run, and
that no two jobs ever overlap.
"""
from __future__ import annotations

import queue
import random
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


class _CountedStop(threading.Event):
    """`_STOP`, counting how often a stop has set it, so the test can tell a
    request that came wholly after a stop's hand-over from one that may have
    come before it."""

    def __init__(self):
        super().__init__()
        self.sets = 0

    def set(self):
        self.sets += 1
        super().set()


class _WatchedQueue(queue.Queue):
    """`_QUEUE`, noting which stop (by `_CountedStop.sets`) took each job off
    it on the stopping thread and did not put it back: that is the stop that
    dropped it."""

    def __init__(self, flag, stopper):
        super().__init__()
        self.flag = flag
        self.stopper = stopper
        self.taken: dict = {}
        self.dropped_by: dict = {}

    def get_nowait(self):
        item = super().get_nowait()
        if item is not None and threading.current_thread() is self.stopper[0]:
            self.taken[id(item)] = (item, self.flag.sets)
        return item

    def put(self, item, *a, **k):
        if item is not None:
            self.taken.pop(id(item), None)
        super().put(item, *a, **k)

    def settle_drops(self):
        """Called on the stopping thread after each stop: what it took and did
        not give back was dropped."""
        for item, sets in self.taken.values():
            if item[0] == "call":
                # by the request's own work function: the same key asked
                # for again is another request
                self.dropped_by[id(item[3][1])] = (item[3][1], sets)
        self.taken.clear()


def _hammer(keys: int, seed: int, monkeypatch, wait_s: float = 10.0):
    """Requests *keys* jobs from one thread, without waiting between them,
    while another thread stops the worker over and over. A job a stop drops
    is asked for again, as the presets window does, until every key has run.

    Returns ``(runs, lost, dropped_after, overlap)``: how often each key ran;
    keys left "waiting or running" with nothing to run them; keys dropped
    although their request came AFTER the stop's hand-over (the flag was
    seen set, and no later stop set it again before the request returned);
    and any two jobs that ran at once."""
    rng = random.Random(seed)
    stop_flag = _CountedStop()
    monkeypatch.setattr(PL, "_STOP", stop_flag)
    stopper_thread: list = [None]
    q = _WatchedQueue(stop_flag, stopper_thread)
    monkeypatch.setattr(PL, "_QUEUE", q)
    lock = threading.Lock()
    running: list = []
    overlap: list = []
    runs: dict = {}
    lost: list = []
    dropped_after: list = []
    done = threading.Event()

    def work_for(key):
        pause = rng.choice((0.0, 0.0005, 0.002))

        def run():
            with lock:
                running.append(key)
                if len(running) > 1:
                    overlap.append(tuple(running))
                runs[key] = runs.get(key, 0) + 1
            time.sleep(pause)
            with lock:
                running.remove(key)
        return run

    def requester():
        try:
            todo = [("r7-hammer", seed, n) for n in range(keys)]
            after_stop_all = []
            end = time.monotonic() + wait_s * 6
            while todo and time.monotonic() < end:
                after_stop = {}
                for key in todo:
                    work = work_for(key)
                    sets = stop_flag.sets
                    was_set = stop_flag.is_set()
                    PL.request(key, work)
                    # the request came wholly after stop number `sets`
                    # began; that stop may not drop it (a later one may)
                    if was_set and stop_flag.sets == sets:
                        after_stop[key] = (work, sets)
                    if rng.random() < 0.3:
                        time.sleep(0.0005)
                after_stop_all.extend(after_stop.items())
                again = []
                for key in todo:
                    until = time.monotonic() + wait_s
                    while (PL.queued(key) and not PL.finished(key)
                           and time.monotonic() < until):
                        time.sleep(0.0005)
                    if PL.finished(key):
                        continue
                    if PL.queued(key):
                        lost.append(key)    # nothing will ever run it
                        continue
                    again.append(key)       # dropped by a stop: ask again
                todo = again
            lost.extend(todo)
            for key, (work, sets) in after_stop_all:
                got = q.dropped_by.get(id(work))
                if got is not None and got[0] is work and got[1] == sets:
                    dropped_after.append(key)
        finally:
            done.set()

    def stopper():
        stopper_thread[0] = threading.current_thread()
        while not done.is_set():
            PL._stop_worker(rng.choice((0.0, 0.0, 0.001, 0.005)))
            with PL._LOCK:
                q.settle_drops()
            time.sleep(rng.choice((0.0, 0.0002, 0.001)))

    threads = [threading.Thread(target=stopper, daemon=True),
               threading.Thread(target=requester, daemon=True)]
    stopper_thread[0] = threads[0]
    for t in threads:
        t.start()
    for t in threads:
        t.join(wait_s * 8 + 60)
    assert not any(t.is_alive() for t in threads), "the hammer never ended"
    PL.settle(30)
    return runs, lost, dropped_after, overlap


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_a_stop_and_a_request_from_two_threads_never_lose_a_job(seed, monkeypatch):
    keys = 200
    runs, lost, dropped_after, overlap = _hammer(keys, seed, monkeypatch)
    assert not lost, (
        f"{len(lost)} job(s) stayed queued with nothing to run them, first "
        f"{lost[:3]}")
    assert not dropped_after, (
        f"{len(dropped_after)} job(s) requested after a stop had begun were "
        f"dropped by it, first {dropped_after[:3]}")
    assert not overlap, f"two jobs ran at once: {overlap[:3]}"
    wrong = [(n, runs.get(("r7-hammer", seed, n))) for n in range(keys)
             if runs.get(("r7-hammer", seed, n)) != 1]
    assert not wrong, f"{len(wrong)} key(s) did not run exactly once: {wrong[:5]}"


def test_a_job_requested_after_a_stop_is_never_emptied_out_by_it():
    """The narrow case, made certain: the request lands while the stop is
    waiting for the old thread. Before the fix the stop then emptied the
    queue, and the job asked for after it was gone."""
    release = threading.Event()
    started = threading.Event()

    def slow():
        started.set()
        release.wait(10.0)

    PL.request(("r7-narrow", "slow"), slow)
    assert started.wait(5.0)
    stop_done = threading.Event()

    def stop():
        PL._stop_worker(2.0)
        stop_done.set()

    t = threading.Thread(target=stop, daemon=True)
    t.start()
    assert PL._STOP.wait(2.0), "the stop never began"
    time.sleep(0.05)               # the stop is now waiting for the old thread
    ran = threading.Event()
    PL.request(("r7-narrow", "next"), ran.set)
    release.set()
    assert stop_done.wait(10.0)
    assert ran.wait(10.0), (
        "the job requested while the stop was waiting was dropped by it")
    assert PL.finished(("r7-narrow", "next"))


def test_a_fresh_worker_is_not_ended_by_the_stop_before_it():
    """The stop's wake-up `None` is for the threads it is stopping. A worker
    started after the stop must not take it as its own ending and leave the
    queue with nobody to run it."""
    PL._stop_worker(0.0)
    with PL._LOCK:
        PL._QUEUE.put(None)        # a wake-up left behind by an earlier stop
    ran = threading.Event()
    PL.request(("r7-wake", 1), ran.set)
    assert ran.wait(10.0), "the fresh worker took a stale wake-up as its end"
