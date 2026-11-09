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


class worker_budget:
    """``with worker_budget(n):`` the build on this thread uses ``n``
    threads (the app's own choice, BuildSettings.engine_workers); 0 or None
    leaves the default / the environment override. Agent 92."""

    def __init__(self, n: int | None) -> None:
        self._n = int(n) if n else 0

    def __enter__(self):
        self._prev = getattr(_SHARE, "budget", None)
        if self._n > 0:
            _SHARE.budget = self._n
        return self

    def __exit__(self, *exc):
        _SHARE.budget = self._prev
        return False


def default_workers() -> int:
    """The machine's usable CPUs minus one (the colprof oracle runs beside
    the engine as one more process; the UI thread is idle while a build
    runs), at most :data:`_MAX_WORKERS`, at least 1."""
    return max(1, min(_MAX_WORKERS, usable_cpus() - 1))


def worker_count() -> int:
    """Threads the engine may use: the app's budget for this build
    (:class:`worker_budget`), else the ``CHROMIQ_ENGINE_THREADS`` override,
    else :func:`default_workers`. Inside a task of :func:`run_tasks` it is
    that task's share of the budget, so nested pools never multiply the
    thread count."""
    share = getattr(_SHARE, "workers", None)
    if share is not None:
        return share
    budget = getattr(_SHARE, "budget", None)
    if budget:
        return max(1, int(budget))
    env = os.environ.get(_ENV, "").strip()
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return default_workers()


def chunk_bounds(n_rows: int, workers: int,
                 min_rows: int | None = None,
                 align: int = 1) -> list[tuple[int, int]]:
    """Contiguous [lo, hi) row ranges, at most ``workers`` of them, none
    smaller than ``min_rows`` (except a single range covering everything).
    ``align``: every range starts on a multiple of it (so every range but
    the last has a size that is a multiple of it; see :data:`ROW_ALIGN`)."""
    if min_rows is None:
        min_rows = MIN_ROWS_PER_CHUNK
    align = max(1, int(align))
    if align > 1:
        nb = -(-n_rows // align)
        bb = chunk_bounds(nb, workers, max(1, -(-min_rows // align)))
        return [(a * align, min(b * align, n_rows)) for a, b in bb
                if min(b * align, n_rows) > a * align]
    k = max(1, min(workers, n_rows // max(1, min_rows)))
    edges = np.linspace(0, n_rows, k + 1).round().astype(int)
    return [(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:]) if b > a]


# Agent 92 (D-06): a BLAS matrix product does not always give a row the
# same bits in a different batch. Measured on Accelerate (numpy 2.4.4,
# macOS 27): ``x @ M.T`` with x (N, 3) computes rows in pairs and a lone
# last row of an odd-sized batch by another path (1e-14 apart); the
# transposed form ``(M @ x.T).T`` differs for almost every N. Row-split
# work that may reach a matrix product (a colour-space view such as the
# CIECAM02 Jab of the a51 clip, a GP layer) therefore cuts its rows only on
# multiples of ROW_ALIGN, so every piece but the last has an even size that
# is also a multiple of the 4/8/12/16-row kernels other BLAS libraries
# use, and only after :func:`rows_stable` has checked on THIS machine that
# such pieces give the full batch's bits. Plain forward-model work
# (element-wise maths, gathers, argmin, batched small solves) needs neither.
ROW_ALIGN = 48
_ROWS_STABLE: list = []


def rows_stable() -> bool:
    """True when this machine's BLAS gives every row of the matrix-product
    shapes the engine's row-split work uses the same bits in ROW_ALIGN-
    aligned pieces as in one batch (checked once per process, about a
    millisecond: (N, 3) x (3, 3) as in the CIECAM02 / CAM16 conversions,
    (N, 900) x (900, 3) as in a GP layer's prediction, several sizes and
    every split the worker counts 2-16 make)."""
    if _ROWS_STABLE:
        return _ROWS_STABLE[0]
    ok = True
    try:
        rng = np.random.default_rng(92)
        cases = [(rng.uniform(-50, 150, (n, 3)), rng.standard_normal((3, 3)))
                 for n in (97, 1000, 6007, 20011)]
        cases.append((rng.standard_normal((2003, 900)),
                      rng.standard_normal((3, 900))))
        for x, m in cases:
            full = x @ m.T
            for w in (2, 3, 4, 5, 7, 8, 12, 16):
                for lo, hi in chunk_bounds(len(x), w, min_rows=1,
                                           align=ROW_ALIGN):
                    if (x[lo:hi] @ m.T).tobytes() != full[lo:hi].tobytes():
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
    except Exception:                                       # noqa: BLE001
        ok = False
    _ROWS_STABLE.append(ok)
    return ok


def row_bounds(n_rows: int, *, align: int = 1, min_rows: int = 64,
               blas: bool = True) -> list[tuple[int, int]]:
    """Contiguous [lo, hi) ranges for ROW-INDEPENDENT work (every row's
    result a function of that row alone), each starting on a multiple of
    ``align`` so a function that works in fixed blocks of ``align`` rows
    sees exactly the blocks it sees serially (Agent 92, D-06). One range
    covering everything outside a Maximum accuracy build or with one
    worker, so those paths run the serial code exactly."""
    import math
    w = worker_count()
    if not in_accurate_scope() or w <= 1 or n_rows < 2 * min_rows:
        return [(0, n_rows)]
    if blas and not rows_stable():
        return [(0, n_rows)]
    return chunk_bounds(n_rows, w, min_rows=min_rows,
                        align=math.lcm(max(1, int(align)), ROW_ALIGN))


def map_rows(fn, n_rows: int, *, align: int = 1, min_rows: int = 64,
             blas: bool = True) -> list:
    """``[fn(lo, hi) ...]`` over :func:`row_bounds`, on pool threads when
    there is more than one range; results in row order."""
    return run_chunks(fn, row_bounds(n_rows, align=align, min_rows=min_rows,
                                     blas=blas))


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


class Pool:
    """A fixed set of pool threads kept for the length of one stage that
    calls :meth:`map` many times (the conjugate-gradient iterations of the
    grid solve: hundreds of tiny parallel steps, where starting threads per
    step would cost more than the step). Agent 92 (D-06).

    ``map(fn, bounds)`` is ``[fn(lo, hi) for lo, hi in bounds]`` with the
    ranges on the pool threads and the calling thread; results in
    ``bounds`` order. With one worker (or one range) it is that plain loop,
    so ``CHROMIQ_ENGINE_THREADS=1`` runs exactly the serial code. Use as a
    context manager; the threads end when the block ends."""

    def __init__(self, workers: int | None = None) -> None:
        self.workers = max(1, worker_count() if workers is None
                           else int(workers))
        self._ex = None
        self._acc = in_accurate_scope()

    def __enter__(self):
        if self.workers > 1:
            acc = self._acc

            def _init():
                _SHARE.accurate = acc
                _SHARE.workers = 1          # nothing nests inside a step
            old = threading.stack_size()
            threading.stack_size(_STACK_BYTES)
            try:
                self._ex = ThreadPoolExecutor(
                    max_workers=self.workers - 1, initializer=_init,
                    thread_name_prefix="chromiq-engine")
                # start every thread now, while the stack size applies
                gate = threading.Barrier(self.workers)
                futs = [self._ex.submit(gate.wait)
                        for _ in range(self.workers - 1)]
                gate.wait()
                for f in futs:
                    f.result()
            finally:
                threading.stack_size(old)
        return self

    def __exit__(self, *exc):
        if self._ex is not None:
            self._ex.shutdown(wait=True)
            self._ex = None
        return False

    def bounds(self, n_rows: int, min_rows: int) -> list[tuple[int, int]]:
        return chunk_bounds(n_rows, self.workers, min_rows=min_rows)

    def map(self, fn, bounds: list[tuple[int, int]]) -> list:
        if self._ex is None or len(bounds) <= 1:
            return [fn(lo, hi) for lo, hi in bounds]
        futs = [self._ex.submit(fn, lo, hi) for lo, hi in bounds[1:]]
        first = None
        err = None
        try:
            first = fn(*bounds[0])
        except BaseException as exc:            # noqa: BLE001
            err = exc
        rest = []
        for f in futs:                          # every range ends first
            try:
                rest.append(f.result())
            except BaseException as exc:        # noqa: BLE001
                err = err or exc
        if err is not None:
            raise err
        return [first] + rest


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
