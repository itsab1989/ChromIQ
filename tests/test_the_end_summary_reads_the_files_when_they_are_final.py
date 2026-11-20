"""S2 (review of the app-log branch, 20 Nov 2026): the end-of-measurement
summary is read on a thread. It used to start FIRST, while the Measure tab's
end of session was still moving the .ti3 to old/, recording the condition and
replacing the file with its provenance stamp: on Windows a file open for
reading cannot be renamed or replaced, so a few milliseconds of overlap could
make a guard fail to set an empty file aside. Now the summary waits for the
tab (``flush_measure_end_log`` after the file work; a fallback timer for a path
without it), and a read that meets a sharing violation is tried again briefly,
reading everything before it writes, so no line is written twice."""
from __future__ import annotations

import inspect
import logging
from pathlib import Path

import workflow.measure_log as ML


def _events(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "chromiq.events"]


def test_a_sharing_violation_is_tried_again_and_written_once(tmp_path, monkeypatch, caplog):
    ti3 = tmp_path / "T.ti3"
    ti3.write_text("CTI3\nBEGIN_DATA\nEND_DATA\n", encoding="utf-8")
    real_stat = Path.stat
    calls = {"n": 0}

    def flaky(self, *a, **k):
        if self == ti3 and calls["n"] < 2:
            calls["n"] += 1
            raise PermissionError(32, "The process cannot access the file")
        return real_stat(self, *a, **k)
    monkeypatch.setattr(Path, "stat", flaky)
    monkeypatch.setattr(ML, "_READ_RETRY_S", 0.0)
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        ML.log_measurement_end(ti3, code=0, conditions=False, dual=False, in_thread=False)
    ends = [m for m in _events(caplog) if m.startswith("measure end")]
    assert len(ends) == 1 and "measurement_bytes=" in ends[0], ends
    assert calls["n"] == 2


def test_a_file_that_stays_locked_gives_one_honest_line(tmp_path, monkeypatch, caplog):
    ti3 = tmp_path / "T.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    real_stat = Path.stat

    def locked(self, *a, **k):
        if self == ti3:
            raise PermissionError(32, "locked")
        return real_stat(self, *a, **k)
    monkeypatch.setattr(Path, "stat", locked)
    monkeypatch.setattr(ML, "_READ_RETRY_S", 0.0)
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        ML.log_measurement_end(ti3, code=0, conditions=True, dual=False, in_thread=False)
    ends = [m for m in _events(caplog) if m.startswith("measure end")]
    assert ends == ["measure end: exit=0 strips_logged=0 files=not_readable"]


def test_the_summary_waits_for_the_tab_s_file_work():
    from workflow.measure_manager import MeasureManager
    from ui.tabs.tab_measure import TabMeasure
    start = inspect.getsource(MeasureManager.start)
    assert "self._queue_measure_end_log(params, code)" in start
    assert "self._log_measure_end(params, code)" not in start
    done = inspect.getsource(TabMeasure._on_measure_done)
    assert done.index("_stamp_provenance_at_end()") < done.index("flush_measure_end_log")
    assert done.index("_archive_empty_measurement()") < done.index("flush_measure_end_log")


def test_flush_writes_once_and_a_new_measurement_flushes_the_old(qapp, monkeypatch):
    from workflow.measure_manager import MeasureManager

    class _R:
        is_running = False
    m = MeasureManager(_R())
    seen = []
    monkeypatch.setattr(m, "_log_measure_end", lambda p, c: seen.append((p, c)))
    m._queue_measure_end_log("first", 0)
    assert seen == []                       # held until the files are final
    m.flush_measure_end_log()
    m.flush_measure_end_log()               # the fallback timer later: nothing again
    assert seen == [("first", 0)]
    m._queue_measure_end_log("second", 1)
    m._queue_measure_end_log("third", 0)    # an older one still held is written first
    assert seen == [("first", 0), ("second", 1)]


def test_the_fallback_timer_is_cancelled_once_the_line_is_written(qapp, qtbot, monkeypatch):
    """4.3.51 (review of 4.3.50): the 20 s fallback was a bare singleShot that nothing could
    cancel. After the tab had written the line, the old timer still fired, and when a new
    measurement had queued its own line meanwhile, it wrote THAT one early, before the tab had
    finished with its files (on Windows: the short file-sharing overlap an earlier fix removed)."""
    from workflow.measure_manager import MeasureManager

    class _R:
        is_running = False
    m = MeasureManager(_R())
    m.END_LOG_FALLBACK_MS = 150
    seen = []
    monkeypatch.setattr(m, "_log_measure_end", lambda p, c: seen.append((p, c)))
    m._queue_measure_end_log("first", 0)
    m.flush_measure_end_log()               # the tab wrote it
    assert seen == [("first", 0)]
    qtbot.wait(60)
    m._queue_measure_end_log("second", 0)   # the next measurement's line, held for its tab
    qtbot.wait(120)                         # the FIRST timer would have fired by now
    assert seen == [("first", 0)], "the old fallback wrote the next measurement's line early"
    qtbot.wait(200)                         # the second line's own fallback still works
    assert seen == [("first", 0), ("second", 0)]


def test_the_fallback_timer_can_be_cancelled_when_the_manager_goes_away(qapp, qtbot, monkeypatch):
    from workflow.measure_manager import MeasureManager

    class _R:
        is_running = False
    m = MeasureManager(_R())
    m.END_LOG_FALLBACK_MS = 100
    seen = []
    monkeypatch.setattr(m, "_log_measure_end", lambda p, c: seen.append((p, c)))
    m._queue_measure_end_log("first", 0)
    t = m._end_log_timer
    assert t.isActive()
    m.cancel_measure_end_fallback()
    assert not t.isActive()
    qtbot.wait(150)
    assert seen == []                       # nothing written by a timer nobody wants
    m.flush_measure_end_log()               # the held line is still the tab's to write
    assert seen == [("first", 0)]
