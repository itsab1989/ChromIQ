""""Discard and stop" keeps nothing from the session (§2, M-END), even what
ChromIQ's engine already wrote.

Found by the regression review of 4.3.5 beta 4 and reproduced ON SCREEN in
beta 5 by the real buttons (report folder 2026-10-14_b5_texts,
drive_discard.py): after "All Strips Read", "Re-read Individual Strips", one
strip read, Stop, "Discard and stop", the run's .ti3 held the session's
readings. The engine writes the file itself once every strip is read, and
"Discard and stop" only killed the reader. Beta 3 did the same.
"""
from __future__ import annotations

import inspect

from workflow.measurement_session import MeasurementSession

TI3 = """CTI3
NUMBER_OF_FIELDS 4
BEGIN_DATA_FORMAT
SAMPLE_ID XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 2
BEGIN_DATA
1 {a} 1.0 1.0
2 {a} 2.0 2.0
END_DATA
"""


def _ti3(path, a):
    path.write_text(TI3.format(a=a), encoding="latin-1")


def test_a_discard_puts_the_previous_measurement_back(tmp_path):
    ti3 = tmp_path / "run" / "chart.ti3"
    ti3.parent.mkdir()
    _ti3(ti3, "10.0")
    before = ti3.read_bytes()
    s = MeasurementSession(ti3, None, tmp_path / "run" / "old")
    s.begin()
    _ti3(ti3, "55.0")          # the engine wrote the session's readings
    out = s.finish(resumed=False, discarded=True)
    assert ti3.read_bytes() == before and out.restored
    assert out.kept_beside is not None and out.kept_beside.name.startswith("discarded-")
    assert "55.0" in out.kept_beside.read_text(encoding="latin-1"), "never deleted"


def test_a_discard_of_a_first_measurement_leaves_none(tmp_path):
    ti3 = tmp_path / "chart.ti3"
    s = MeasurementSession(ti3, None, tmp_path / "old")
    s.begin()
    _ti3(ti3, "55.0")
    out = s.finish(resumed=False, discarded=True)
    assert not ti3.exists() and out.kept_beside.is_file()


def test_a_discard_that_wrote_nothing_moves_nothing(tmp_path):
    ti3 = tmp_path / "chart.ti3"
    _ti3(ti3, "10.0")
    s = MeasurementSession(ti3, None, tmp_path / "old")
    s.begin()
    out = s.finish(resumed=True, discarded=True)
    assert ti3.is_file() and out.kept_beside is None


def test_the_tab_passes_the_choice_on():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._end_session)
    assert "_discard_chosen = True" in src
    src = inspect.getsource(TabMeasure._finish_session_guard)
    assert "discarded=discarded" in src
    # and no "That session ended before any patch was read" after a discard
    src = inspect.getsource(TabMeasure._archive_empty_measurement)
    assert "quiet=quiet" in src
