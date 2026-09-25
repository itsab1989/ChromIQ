"""Challenge 1 of beta 43, M1 (B8-1161): "Which presets can be used for
verification?" froze for about 1 s at a time while its "Working…" rows
resolved. Knut's rule (K40-1): *"It must never block the window."*

Measured on screen with a 50 ms heartbeat, every stall was the Create Chart
tab's idle warming (`TabChart._warm_one_preset_batch`, B8-984) working a chart
out ON THE WINDOW'S THREAD, inside the window's ``exec()``, while K40-1's
background thread (`workflow.preset_layout`) worked out the same presets.

What these tests hold, each with a heartbeat or a count, and each red on the
mutation its docstring names:

* the warming hands its charts to the background thread and never works one
  out on the event loop's thread, so a 50 ms heartbeat keeps beating while a
  chart costs 0.6 s;
* the warming waits while the background thread is busy, and a chart is never
  queued twice, however often the window is opened and closed (m4);
* the window's poll reads no chart off the disk until that chart's job has
  run, and one redraw reads each chart's files once;
* opening the window, or selecting a row in it, holds the background thread's
  next job back, so the window's own work is not starved of the GIL.
"""
from __future__ import annotations

import os
import threading
import time
import types
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer                                    # noqa: E402
from PyQt6.QtWidgets import QApplication                           # noqa: E402

from workflow import preset_eligibility as PE                      # noqa: E402
from workflow import preset_layout as PL                           # noqa: E402

#: What one chart with page images costs on the background thread in these
#: tests (the challenge measured about 1 s on screen).
HEAVY_S = 0.6


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _drain(timeout: float = 30.0) -> None:
    """Wait for the background thread, end it, and give collection back
    (B8-1191: only once the thread has ended, and never by that thread)."""
    PL.settle(timeout)


@pytest.fixture(autouse=True)
def _fresh():
    PL._HOLD_UNTIL = 0.0
    _drain()
    PE.clear_cache()
    yield
    PL._HOLD_UNTIL = 0.0
    _drain()
    PE.clear_cache()


def _charts(tmp_path: Path, n: int) -> "list[Path]":
    from workflow.i1profiler_import import RgbPatch, write_ti1
    out = []
    for i in range(n):
        p = tmp_path / f"c{i}.ti1"
        write_ti1([RgbPatch(i, 0, 0), RgbPatch(100, 100, 100)], p)
        out.append(p)
    return out


class _Heavy:
    """A stand-in for `chart_row_values` that costs what a chart with page
    images costs, and notes which thread paid for it."""

    def __init__(self) -> None:
        self.threads: "list[str]" = []
        self.charts: "list[str]" = []

    def __call__(self, chart, recipe=None, *, lay_out=False):
        self.threads.append(threading.current_thread().name)
        self.charts.append(Path(chart).name)
        time.sleep(HEAVY_S)
        key = PE._values_key(Path(chart), recipe)
        PE._CACHE[key] = {}
        return {}


class _Beat:
    def __init__(self) -> None:
        self.last = time.monotonic()
        self.longest = 0.0
        self.t = QTimer()
        self.t.timeout.connect(self.tick)
        self.t.start(50)

    def tick(self) -> None:
        now = time.monotonic()
        self.longest = max(self.longest, now - self.last)
        self.last = now


class _Warmer:
    """The tab's warming state and its tick, without a whole Create Chart
    tab: `_warm_one_preset_batch` reads only these attributes."""

    def __init__(self, charts) -> None:
        from ui.tabs.tab_chart import TabChart
        self.host = types.SimpleNamespace(
            _preset_warm_charts=[(c, None) for c in charts],
            _preset_warm_at=0, _preset_warm_timer=None)
        self._tick_fn = TabChart._warm_one_preset_batch
        self.t = QTimer()
        self.t.timeout.connect(self.tick)
        self.t.start(40)

    def tick(self) -> None:
        self._tick_fn(self.host)


def _spin(qapp, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.005)


def test_the_warming_never_works_a_chart_out_on_the_windows_thread(
        qapp, tmp_path, monkeypatch):
    """A heartbeat of 50 ms on the event loop while the warming runs over
    four charts that cost 0.6 s each: it never stalls past 0.25 s, and every
    chart is worked out on the background thread.

    MUTATION, proved red: `_warm_one_preset_batch` calling
    ``_pe.chart_row_values(c, recipe)`` itself, as it did before B8-1161
    (the heartbeat stalls 0.6 s; the work is on MainThread)."""
    heavy = _Heavy()
    monkeypatch.setattr(PE, "chart_row_values", heavy)
    charts = _charts(tmp_path, 4)
    beat = _Beat()
    warm = _Warmer(charts)
    try:
        beat.last = time.monotonic()
        _spin(qapp, HEAVY_S * 4 + 1.0)
    finally:
        warm.t.stop()
        beat.t.stop()
    assert heavy.threads, "the warming worked nothing out at all"
    assert set(heavy.threads) == {"chromiq-preset-layout"}, heavy.threads
    assert beat.longest < 0.25, (
        f"the event loop stalled {beat.longest:.2f} s while the warming ran")
    _drain()
    assert sorted(heavy.charts) == sorted(c.name for c in charts)


def test_the_warming_waits_while_the_background_is_busy(
        qapp, tmp_path, monkeypatch):
    """While the background thread has work (the window's own rows), a tick
    hands it nothing more.

    MUTATION, proved red: the ``if _pl.pending(): return`` guard removed (the
    tick queues its next chart behind the window's)."""
    heavy = _Heavy()
    monkeypatch.setattr(PE, "chart_row_values", heavy)
    busy, *charts = _charts(tmp_path, 3)
    PE.request_values(busy, None)
    assert PL.pending() == 1
    from ui.tabs.tab_chart import TabChart
    host = types.SimpleNamespace(
        _preset_warm_charts=[(c, None) for c in charts],
        _preset_warm_at=0, _preset_warm_timer=None)
    TabChart._warm_one_preset_batch(host)
    assert host._preset_warm_at == 0
    assert PL.pending() == 1


def test_opening_and_closing_the_window_never_queues_a_chart_twice(
        qapp, tmp_path, monkeypatch):
    """m4: three opens and closes while the first chart is still being
    worked out leave each chart queued once.

    MUTATION, proved red: `preset_layout.request` without its
    ``if key in _REQUESTED: return`` (every open queues the rows again)."""
    from ui.dialogs import preset_verification_dialog as PVD
    heavy = _Heavy()
    monkeypatch.setattr(PE, "chart_row_values", heavy)
    charts = _charts(tmp_path, 4)
    rows = [PVD.PresetRow(group="Custom presets", label=c.stem, chart=c,
                          patches=2, pages=1, builtin=False, key=c.stem)
            for c in charts]
    for _ in range(3):
        dlg = PVD.PresetVerificationDialog(rows, None, None, background=True)
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()
    jobs = [j[3][0] for j in list(PL._QUEUE.queue) if j is not None]
    assert len(jobs) == len(set(jobs)), jobs
    _drain()
    assert sorted(heavy.charts) == sorted(c.name for c in charts)


def test_the_poll_reads_no_chart_whose_job_has_not_run(
        qapp, tmp_path, monkeypatch):
    """Each time a background job finishes, the window re-reads its waiting
    rows. A row whose own job has not run is not read off the disk.

    MUTATION, proved red: the ``request_finished`` check dropped from
    `_poll_layouts_now` (every waiting row's files are read on every
    poll)."""
    from ui.dialogs import preset_verification_dialog as PVD
    heavy = _Heavy()
    monkeypatch.setattr(PE, "chart_row_values", heavy)
    charts = _charts(tmp_path, 5)
    rows = [PVD.PresetRow(group="Custom presets", label=c.stem, chart=c,
                          patches=2, pages=1, builtin=False, key=c.stem)
            for c in charts]
    PL.hold(30.0)                       # no job may start
    dlg = PVD.PresetVerificationDialog(rows, None, None, background=True)
    try:
        assert dlg.waiting_count() == 5
        reads: list = []
        real = PE._read_values_key
        monkeypatch.setattr(PE, "_read_values_key",
                            lambda p, r: reads.append(p) or real(p, r))
        dlg._layout_seen = None
        dlg._poll_layouts()
        assert reads == []
    finally:
        PL._HOLD_UNTIL = 0.0
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_one_redraw_reads_each_charts_files_once(qapp, tmp_path, monkeypatch):
    """`refresh` asks values_ready, assess and made_for_verification about
    each chart; the files behind the cache key are read once per redraw.

    MUTATION, proved red: `one_pass` yielding without setting the memo
    (three reads a chart)."""
    from ui.dialogs import preset_verification_dialog as PVD
    charts = _charts(tmp_path, 3)
    rows = [PVD.PresetRow(group="Custom presets", label=c.stem, chart=c,
                          patches=2, pages=1, builtin=False, key=c.stem)
            for c in charts]
    for c in charts:
        PE.chart_row_values(c, None)        # every answer known
    reads: list = []
    real = PE._read_values_key
    monkeypatch.setattr(PE, "_read_values_key",
                        lambda p, r: reads.append(Path(p).name) or real(p, r))
    dlg = PVD.PresetVerificationDialog(rows, None, None, background=True)
    try:
        assert dlg.waiting_count() == 0
        assert sorted(reads) == sorted(c.name for c in charts), reads
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_a_hold_keeps_the_next_job_back(qapp, tmp_path, monkeypatch):
    """`preset_layout.hold`: a job queued while the window is being opened
    starts only when the hold has passed.

    MUTATION, proved red: `_wait_while_held` returning at once (the job
    starts inside the hold)."""
    heavy = _Heavy()
    started: list = []
    monkeypatch.setattr(PE, "chart_row_values",
                        lambda c, r=None, **k: started.append(
                            time.monotonic()) or heavy(c, r))
    (chart,) = _charts(tmp_path, 1)
    t0 = time.monotonic()
    PL.hold(0.5)
    PE.request_values(chart, None)
    _drain()
    assert started and started[0] - t0 >= 0.45, started


def test_the_window_holds_the_background_while_it_opens_and_on_a_click():
    """The tab's open and the window's row selection both ask for a hold.

    MUTATION, proved red: either ``hold`` call removed."""
    import inspect
    from ui.dialogs import preset_verification_dialog as PVD
    from ui.tabs.tab_chart import TabChart
    assert "_pl.hold(PRESET_WINDOW_OPEN_HOLD_S)" in inspect.getsource(
        TabChart._open_preset_verification_window)
    assert "PL.hold(SELECTION_HOLD_S)" in inspect.getsource(
        PVD.PresetVerificationDialog._on_selected)


def test_the_collector_never_runs_on_the_background_thread(
        qapp, tmp_path, monkeypatch):
    """While the background thread works a chart out, automatic garbage
    collection is off, so a collection can never destroy a Qt widget on that
    thread (the everyday tier lost a worker to a SIGSEGV in Qt's event-filter
    dispatch with this thread in PIL); the GUI thread's timer gives it back
    once the thread is idle.

    MUTATION, proved red: `_hold_gc` doing nothing (collection stays on
    during the job)."""
    import gc
    seen: list = []

    def job(chart, recipe=None, **_k):
        seen.append(gc.isenabled())
        time.sleep(0.2)
        return {}
    monkeypatch.setattr(PE, "chart_row_values", job)
    assert gc.isenabled()
    (chart,) = _charts(tmp_path, 1)
    PE.request_values(chart, None)
    from ui.dialogs.preset_verification_dialog import collect_on_this_thread
    collect_on_this_thread()
    end = time.monotonic() + 10
    while PL.pending() and time.monotonic() < end:
        time.sleep(0.02)
    assert seen == [False], seen
    end = time.monotonic() + 5
    while not gc.isenabled() and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.02)
    assert gc.isenabled(), "automatic collection was never given back"


def test_a_hidden_tab_hands_out_no_work(qapp, tmp_path, monkeypatch):
    """A Create Chart tab that is not on screen (another tab chosen, or left
    alive and hidden) hands the background thread nothing; showing it again
    carries on (`_warm_preset_eligibility` restarts the timer).

    MUTATION, proved red: the ``isVisible`` check removed from
    `_warm_one_preset_batch` (the hidden tab queues a chart)."""
    heavy = _Heavy()
    monkeypatch.setattr(PE, "chart_row_values", heavy)
    charts = _charts(tmp_path, 2)
    from ui.tabs.tab_chart import TabChart
    host = types.SimpleNamespace(
        _preset_warm_charts=[(c, None) for c in charts],
        _preset_warm_at=0, _preset_warm_timer=None,
        isVisible=lambda: False)
    TabChart._warm_one_preset_batch(host)
    assert host._preset_warm_at == 0
    assert PL.pending() == 0
