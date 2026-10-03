"""Deterministic parallelism for the Maximum accuracy build (D-06, D-07).

Rules this module enforces, so callers do not have to remember them:

* **Byte identity.** Work is only ever split where every row's result is a
  function of that row alone (the batched Gauss-Newton inversion: every node
  is solved independently). Chunks are contiguous, results are written back
  in input order, so the output never depends on scheduling. Nothing that
  reduces ACROSS rows (a sum, a least-squares fit, a GEMM whose blocking
  could change) is split here.
* **Threads, not processes.** numpy releases the GIL inside its kernels, so
  threads give real parallelism for the large array operations the
  inversion consists of. Threads need no pickling, no ``fork`` (Windows has
  none), no ``multiprocessing.freeze_support()`` in a PyInstaller bundle,
  and they end with the process when the app quits (``os._exit``).
* **Never all cores.** :func:`worker_count` leaves headroom for the UI
  thread and an Argyll child, honours CPU affinity (Linux ``sched``,
  ``os.process_cpu_count``), Linux cgroup CPU quotas (containers), and the
  ``CHROMIQ_ENGINE_THREADS`` override (1 = the serial code path exactly).
* **Stack.** Pool threads get 32 MiB of stack like every worker QThread
  (core/thread_stack.py: OpenBLAS's parallel LU on a small stack crashed).
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np

_STACK_BYTES = 32 * 1024 * 1024
_ENV = "CHROMIQ_ENGINE_THREADS"
# Below this many rows per chunk the per-call Python overhead of the
# Gauss-Newton loop outweighs the gain; small batches stay serial.
MIN_ROWS_PER_CHUNK = 1024
_MAX_WORKERS = 8


def _cgroup_cpu_limit() -> int | None:
    """CPUs allowed by a Linux cgroup quota (containers), else None."""
    for path in ("/sys/fs/cgroup/cpu.max",):                 # cgroup v2
        try:
            quota, period = open(path, encoding="ascii").read().split()[:2]
            if quota != "max":
                return max(1, int(float(quota) / float(period)))
        except (OSError, ValueError):
            pass
    try:                                                     # cgroup v1
        q = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us",
                     encoding="ascii").read())
        p = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us",
                     encoding="ascii").read())
        if q > 0 and p > 0:
            return max(1, q // p)
    except (OSError, ValueError):
        pass
    return None


def usable_cpus() -> int:
    """CPUs this process may run on: affinity mask (Linux; Windows through
    ``os.process_cpu_count`` on Python >= 3.13, which counts every
    processor group), capped by a cgroup quota."""
    n = None
    if hasattr(os, "process_cpu_count"):                     # 3.13+
        n = os.process_cpu_count()
    if n is None and hasattr(os, "sched_getaffinity"):
        try:
            n = len(os.sched_getaffinity(0))
        except OSError:
            n = None
    if n is None:
        n = os.cpu_count() or 1
    lim = _cgroup_cpu_limit()
    if lim is not None:
        n = min(n, lim)
    return max(1, int(n))


_SHARE = threading.local()


class accurate_scope:
    """``with accurate_scope():`` marks the current thread (and every pool
    thread this module starts from it) as running a Maximum accuracy
    build. Speed paths that live in code Fast and Bit-exact share (the
    forward fit) only switch on inside it, so those modes keep their serial
    code path whatever the bytes would be."""

    def __enter__(self):
        self._prev = getattr(_SHARE, "accurate", False)
        _SHARE.accurate = True
        return self

    def __exit__(self, *exc):
        _SHARE.accurate = self._prev
        return False


def in_accurate_scope() -> bool:
    return bool(getattr(_SHARE, "accurate", False))


def worker_count() -> int:
    """Threads the engine may use: the override if set, else the usable
    CPUs minus two (the UI thread and one Argyll child), at most 8, at
    least 1. On a 4-core laptop that is 2; on 16 cores it is 8. Inside a
    task of :func:`run_tasks` it is that task's share of the budget, so
    nested pools never multiply the thread count."""
    share = getattr(_SHARE, "workers", None)
    if share is not None:
        return share
    env = os.environ.get(_ENV, "").strip()
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return max(1, min(_MAX_WORKERS, usable_cpus() - 2))


def chunk_bounds(n_rows: int, workers: int,
                 min_rows: int | None = None) -> list[tuple[int, int]]:
    """Contiguous [lo, hi) row ranges, at most ``workers`` of them, none
    smaller than ``min_rows`` (except a single range covering everything)."""
    if min_rows is None:
        min_rows = MIN_ROWS_PER_CHUNK
    k = max(1, min(workers, n_rows // max(1, min_rows)))
    edges = np.linspace(0, n_rows, k + 1).round().astype(int)
    return [(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:]) if b > a]


def run_chunks(fn, bounds: list[tuple[int, int]]) -> list:
    """``[fn(lo, hi) for lo, hi in bounds]``, the ranges on pool threads.
    Results come back in ``bounds`` order whatever finishes first; the
    first exception is re-raised after every chunk has ended."""
    if len(bounds) <= 1:
        return [fn(lo, hi) for lo, hi in bounds]
    old = threading.stack_size()
    threading.stack_size(_STACK_BYTES)
    try:
        # Threads are created on submit, so the stack size applies to them
        # and is restored for everyone else right after.
        acc = in_accurate_scope()

        share = max(1, worker_count() // len(bounds))

        def _flagged(lo, hi):
            _SHARE.accurate = acc
            _SHARE.workers = share          # nested pools stay in budget
            return fn(lo, hi)
        with ThreadPoolExecutor(max_workers=len(bounds),
                                thread_name_prefix="chromiq-engine") as ex:
            futs = [ex.submit(_flagged, lo, hi) for lo, hi in bounds]
            threading.stack_size(old)
            return [f.result() for f in futs]
    finally:
        threading.stack_size(old)


def run_tasks(tasks: list, workers: int | None = None) -> list:
    """``[t() for t in tasks]`` with up to ``workers`` tasks at a time on
    pool threads (default :func:`worker_count`). For INDEPENDENT pieces of
    work only (each task builds its own result from inputs nobody mutates);
    results come back in task order."""
    total = worker_count()
    workers = total if workers is None else max(1, min(workers, total))
    if workers <= 1 or len(tasks) <= 1:
        return [t() for t in tasks]
    share = max(1, total // min(workers, len(tasks)))
    acc = in_accurate_scope()

    def _with_share(t):
        _SHARE.workers = share
        _SHARE.accurate = acc
        try:
            return t()
        finally:
            _SHARE.workers = None

    old = threading.stack_size()
    threading.stack_size(_STACK_BYTES)
    try:
        with ThreadPoolExecutor(max_workers=min(workers, len(tasks)),
                                thread_name_prefix="chromiq-engine") as ex:
            futs = [ex.submit(_with_share, t) for t in tasks]
            threading.stack_size(old)
            return [f.result() for f in futs]
    finally:
        threading.stack_size(old)


class Background:
    """Run ``fn()`` on one thread beside the caller (independent work only).

    While it runs, the caller and the background task each get half of the
    thread budget, so their inner pools together stay within
    :func:`worker_count`. :meth:`result` joins it and re-raises its
    exception; :meth:`join` only waits (the build's ``finally`` uses it, so
    no engine thread outlives ``build_profile``)."""

    def __init__(self, fn, name: str = "chromiq-engine-bg") -> None:
        total = worker_count()
        self._share = max(1, total // 2)
        self._prev = getattr(_SHARE, "workers", None)
        _SHARE.workers = self._share
        self._value = None
        self._exc: BaseException | None = None

        acc = in_accurate_scope()

        def _run():
            _SHARE.workers = self._share
            _SHARE.accurate = acc
            try:
                self._value = fn()
            except BaseException as exc:            # noqa: BLE001
                self._exc = exc

        old = threading.stack_size()
        threading.stack_size(_STACK_BYTES)
        try:
            self._t = threading.Thread(target=_run, name=name, daemon=True)
            self._t.start()
        finally:
            threading.stack_size(old)

    def join(self) -> None:
        self._t.join()
        _SHARE.workers = self._prev

    def result(self):
        self.join()
        if self._exc is not None:
            raise self._exc
        return self._value
