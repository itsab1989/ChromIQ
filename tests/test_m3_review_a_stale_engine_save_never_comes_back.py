"""Review of M3 (2026-10-21): the engine's kept save (``<name>.ti3.cqtmp``)
must never put back readings nobody wants.

The engine's FINAL save writes the ``.ti3`` directly and never touches the
``.cqtmp``, so one left by a failed autosave lingered for ever, and the
recovery put it over the measurement whenever there was no ``.ti3`` (a filed
verification, a replaced chart) or the ``.ti3`` was older by date, which is
exactly what "Discard and stop" leaves: the measurement it puts back is a
``copy2`` of the archive and keeps the archive's old date. A file cut short,
or another chart's, also counted.

Now the recovery takes only a well-formed file of this chart with at least
the readings the ``.ti3`` holds, and a session's end puts the newest copy in
place first and then sets any left-over one aside to old/ (moved, never
deleted).
"""
from __future__ import annotations

import inspect
import os
import time
from pathlib import Path

from test_m3_a_failed_autosave_keeps_the_readings import _ti3

TI2 = """CTI2

DESCRIPTOR "Argyll Calibration Target chart information 2"
ORIGINATOR "Argyll printtarg"

NUMBER_OF_FIELDS 5
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B
END_DATA_FORMAT

NUMBER_OF_SETS {n}
BEGIN_DATA
{rows}
END_DATA
"""


def _ti2(path: Path, n: int) -> None:
    rows = "\n".join(f'{i + 1} "A{i + 1}" 50.0 50.0 50.0' for i in range(n))
    path.write_text(TI2.format(n=n, rows=rows), encoding="utf-8")


def _age(p: Path, s: float = 60) -> None:
    os.utime(p, (time.time() - s, time.time() - s))


def test_a_save_cut_short_is_not_used(tmp_path):
    from workflow.measurement_state import (engine_autosave_temp,
                                            recover_engine_autosave)
    ti3 = tmp_path / "chart.ti3"
    _ti3(ti3, 5)
    _age(ti3)
    tmp = engine_autosave_temp(ti3)
    _ti3(tmp, 6)
    text = tmp.read_text(encoding="utf-8")
    tmp.write_text(text[:text.index("\n4 ")], encoding="utf-8")   # torn write
    assert recover_engine_autosave(ti3) is False
    assert "NUMBER_OF_SETS 5" in ti3.read_text(encoding="utf-8")


def test_another_charts_save_is_not_used(tmp_path):
    from workflow.measurement_state import (engine_autosave_temp,
                                            recover_engine_autosave)
    ti3, ti2 = tmp_path / "chart.ti3", tmp_path / "chart.ti2"
    _ti2(ti2, 4)                         # the chart now lays out 4 patches
    _ti3(engine_autosave_temp(ti3), 9)   # left by a 9-patch chart it replaced
    assert recover_engine_autosave(ti3, ti2) is False
    assert not ti3.exists()


def test_a_save_with_fewer_readings_is_not_used(tmp_path):
    from workflow.measurement_state import (engine_autosave_temp,
                                            recover_engine_autosave)
    ti3 = tmp_path / "chart.ti3"
    _ti3(ti3, 6)
    _age(ti3)
    _ti3(engine_autosave_temp(ti3), 3)
    assert recover_engine_autosave(ti3) is False
    assert "NUMBER_OF_SETS 6" in ti3.read_text(encoding="utf-8")


def test_a_discard_is_not_undone_by_the_next_load(tmp_path):
    """The whole story: a session whose last save failed, then "Discard and
    stop", then the chart is loaded again."""
    from workflow.measurement_session import MeasurementSession
    from workflow.measurement_state import (engine_autosave_temp,
                                            recover_engine_autosave,
                                            set_aside_engine_autosave)
    ti3, ti2 = tmp_path / "chart.ti3", tmp_path / "chart.ti2"
    _ti2(ti2, 8)
    _ti3(ti3, 3)                              # the measurement before
    _age(ti3, 3600)
    guard = MeasurementSession(ti3, ti2)
    guard.begin()
    tmp = engine_autosave_temp(ti3)
    _ti3(ti3, 5)                              # saved after strip 2
    _ti3(tmp, 6)                              # strip 3: the replace failed
    # session end, in the tab's order: settle, then judge
    assert recover_engine_autosave(ti3, ti2) is True
    assert set_aside_engine_autosave(ti3, guard.old_dir) is None
    out = guard.finish(resumed=True, discarded=True)
    assert out.restored
    assert "NUMBER_OF_SETS 3" in ti3.read_text(encoding="utf-8")
    assert not tmp.exists()
    # the next load
    assert recover_engine_autosave(ti3, ti2) is False
    assert "NUMBER_OF_SETS 3" in ti3.read_text(encoding="utf-8")


def test_a_left_over_save_is_moved_to_old_never_deleted(tmp_path):
    from workflow.measurement_state import (engine_autosave_temp,
                                            set_aside_engine_autosave)
    ti3 = tmp_path / "chart.ti3"
    tmp = engine_autosave_temp(ti3)
    _ti3(tmp, 4)
    _age(tmp)
    _ti3(ti3, 8)                    # the final save wrote the .ti3 itself
    moved = set_aside_engine_autosave(ti3, tmp_path / "old")
    assert moved is not None and moved.parent == tmp_path / "old"
    assert "NUMBER_OF_SETS 4" in moved.read_text(encoding="utf-8")
    assert not tmp.exists()
    assert set_aside_engine_autosave(ti3, tmp_path / "old") is None


def test_the_session_end_settles_the_save_before_anything_reads_the_file():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    settle = src.index("self._settle_engine_autosave_at_end()")
    assert settle < src.index("        self._drop_set_aside_readings()\n"
                              "        self._finish_session_guard()")
    body = inspect.getsource(TabMeasure._settle_engine_autosave_at_end)
    assert body.index("_recover_engine_autosave()") \
        < body.index("set_aside_engine_autosave(")


def test_a_newer_save_that_could_not_be_put_in_place_stays_for_the_next_load(tmp_path):
    """The .ti3 still locked at the session's end (here: a folder in its
    place): the kept save is the only newest copy, so it stays beside it."""
    from workflow.measurement_state import (engine_autosave_temp,
                                            recover_engine_autosave,
                                            set_aside_engine_autosave)
    ti3 = tmp_path / "chart.ti3"
    ti3.mkdir()
    (ti3 / "blocker").write_text("x", encoding="utf-8")
    tmp = engine_autosave_temp(ti3)
    _ti3(tmp, 6)
    assert recover_engine_autosave(ti3) is False
    assert set_aside_engine_autosave(ti3, tmp_path / "old") is None
    assert tmp.is_file()
    # ...unless the person discarded the session
    moved = set_aside_engine_autosave(ti3, tmp_path / "old", discarded=True)
    assert moved is not None and moved.is_file() and not tmp.exists()
