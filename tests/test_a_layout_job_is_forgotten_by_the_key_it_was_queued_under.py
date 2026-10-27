"""Review r7 of 4.3.18, NIT-1: a queued layout job is forgotten by the key it
was counted under, not by one worked out again later.

`preset_layout` counts a queued layout in `_PENDING` under
`layout_key(chart, spec)`: the chart's bytes, the arguments and the printtarg
binary. When the job was dropped by a stop, or when it ran, that key used to
be worked out AGAIN (reading the chart and stat'ing printtarg, with `_LOCK`
held on the drop path). A chart or printtarg changed after queuing gave
another key, the queued one stayed in `_PENDING` for good, `_schedule` never
queued it again, and `pending()` never reached 0, so `settle()` waited out
its whole timeout. The job now carries its key.
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


@pytest.fixture
def laid_out(monkeypatch):
    calls: list = []

    def fake(chart, spec):
        calls.append(chart)
        return {"pages": 1, "laid_out_by": "test"}
    monkeypatch.setattr(PL, "lay_out_with_printtarg", fake)
    return calls


def _busy_worker():
    """A job that keeps the background thread busy until released, so a
    layout queued now waits in the queue."""
    release = threading.Event()
    started = threading.Event()

    def hold():
        started.set()
        release.wait(10.0)
    PL.request(("nit-1", time.monotonic()), hold)
    assert started.wait(5.0), "the holding job never started"
    return release


def _wait_until(cond, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end and not cond():
        time.sleep(0.01)
    return cond()


def test_a_dropped_job_whose_chart_changed_is_not_pending_for_ever(
        tmp_path, laid_out):
    chart = tmp_path / "chart.ti1"
    chart.write_text("CTI1\nbefore\n", encoding="utf-8")
    release = _busy_worker()
    try:
        assert PL.grid_for(chart, {}) == {"reason": PL.REASON_LAYING_OUT}
        chart.write_text("CTI1\nchanged after it was queued\n",
                         encoding="utf-8")
        PL._stop_worker(0.05)       # drops the queued layout
    finally:
        release.set()
    assert _wait_until(lambda: PL.pending() == 0), (
        f"{PL.pending()} job(s) still counted as pending after the stop "
        f"dropped them")
    assert not laid_out, "a dropped job ran"


def test_a_job_that_ran_after_its_chart_changed_is_not_pending_for_ever(
        tmp_path, laid_out):
    chart = tmp_path / "chart.ti1"
    chart.write_text("CTI1\nbefore\n", encoding="utf-8")
    release = _busy_worker()
    try:
        assert PL.grid_for(chart, {}) == {"reason": PL.REASON_LAYING_OUT}
        chart.write_text("CTI1\nchanged after it was queued\n",
                         encoding="utf-8")
    finally:
        release.set()
    assert _wait_until(lambda: bool(laid_out)), "the layout never ran"
    assert _wait_until(lambda: PL.pending() == 0), (
        f"{PL.pending()} job(s) still counted as pending after the layout ran")
    # what it laid out is filed under the chart as it is now
    assert PL.grid_for(chart, {}) == {"pages": 1, "laid_out_by": "test"}


def test_the_drop_path_reads_no_file_under_the_lock():
    import inspect
    src = inspect.getsource(PL._forget_locked)
    assert "layout_key(" not in src


def test_a_running_job_does_not_forget_a_job_queued_for_the_chart_as_it_is_now(
        tmp_path, monkeypatch):
    """Review r8 of 4.3.18, NIT-3: a job whose chart changed before it ran
    lays out the chart as it is now. If that newer chart got a job of its own
    meanwhile, the first job used to forget the newer job's key as well, and
    `pending()` read one too low while the newer job still waited."""
    chart = tmp_path / "chart.ti1"
    chart.write_text("CTI1\nNIT-3 before\n", encoding="utf-8")
    entered = threading.Event()
    leave = threading.Event()

    def fake(c, spec):
        entered.set()
        leave.wait(10.0)
        return {"pages": 1, "laid_out_by": "test"}
    monkeypatch.setattr(PL, "lay_out_with_printtarg", fake)
    release = _busy_worker()
    try:
        assert PL.grid_for(chart, {}) == {"reason": PL.REASON_LAYING_OUT}
        chart.write_text("CTI1\nNIT-3 changed after it was queued\n",
                         encoding="utf-8")
    finally:
        release.set()
    try:
        assert entered.wait(10.0), "the first layout never started"
        # the chart as it is now gets its own job while the first one runs
        assert PL.grid_for(chart, {}) == {"reason": PL.REASON_LAYING_OUT}
        assert PL.pending() == 2
        # keep the next job waiting, so what is counted can be read
        PL._HOLD_UNTIL = time.monotonic() + 30.0
    finally:
        leave.set()
    try:
        assert _wait_until(lambda: PL.pending() < 2), "the first job never ended"
        time.sleep(0.2)
        assert PL.pending() == 1, (
            "the newer job is still queued, so it must still be counted")
    finally:
        PL._HOLD_UNTIL = 0.0
    assert _wait_until(lambda: PL.pending() == 0)
