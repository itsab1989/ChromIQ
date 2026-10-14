"""4.3.5 beta 5 regression review, fix 3: the ending window said "They are not
in your measurement file yet" over a file ChromIQ's engine had already
written (M-END-WRITTEN), and said nothing about putting back a measurement
"Measure anyway" had moved to old/.
"""
from __future__ import annotations

import inspect
import json
import os
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.confirmed_patches import confirmed_path      # noqa: E402
from workflow.measurement_session import MeasurementSession  # noqa: E402

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


def _ti3(path: Path, a: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TI3.format(a=a), encoding="latin-1")


def _mem(ti3: Path, tag: str) -> None:
    confirmed_path(ti3).write_text(json.dumps({"tag": tag}), encoding="utf-8")


def _tag(ti3: Path) -> str:
    return json.loads(confirmed_path(ti3).read_text(encoding="utf-8"))["tag"]



# ---- 3. the ending window tells the truth about the file ----------------
def test_the_guard_knows_when_the_session_wrote_the_file(tmp_path):
    ti3 = tmp_path / "test.ti3"
    _ti3(ti3, "10.0")
    s = MeasurementSession(ti3, None, tmp_path / "old")
    s.begin()
    assert s.file_written() is False
    _ti3(ti3, "55.0")
    os.utime(ti3, ns=(ti3.stat().st_atime_ns, ti3.stat().st_mtime_ns + 10**9))
    assert s.file_written() is True


def test_a_first_measurement_written_by_the_engine_counts(tmp_path):
    ti3 = tmp_path / "test.ti3"
    s = MeasurementSession(ti3, None, tmp_path / "old")
    s.begin()
    assert s.file_written() is False
    _ti3(ti3, "55.0")
    assert s.file_written() is True


def test_the_window_uses_the_written_variant():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._confirm_end_of_session)
    assert "self._session_wrote_its_file()" in src
    assert "M.M_END_WRITTEN.render(n=n, kept=kept)" in src
    from workflow import measurement_messages as M
    _t, body = M.M_END_WRITTEN.render(n=3, kept="")
    assert "not in your measurement file yet" not in body
    assert "already written them" in body
    _t, body = M.M_END_WRITTEN.render(n=1, kept="")
    assert "1 patch" in body and "written it" in body


def test_a_measurement_measure_anyway_set_aside_is_counted(tmp_path):
    """The guard begins after "Measure anyway" moved the file to old/, so it
    counts nothing; Discard puts that file back, and M-END says so."""
    from ui.tabs.tab_measure import TabMeasure
    run = tmp_path / "run"
    displaced = run / "old" / "2026-10-14_120000"
    _ti3(displaced / "test.ti3", "10.0")
    fake = types.SimpleNamespace(
        _session_guard=types.SimpleNamespace(before=0),
        _displaced_measurement=displaced,
        _ti1_path=run / "test.ti1")
    assert TabMeasure._readings_before_session(fake) == 2
    fake._displaced_measurement = None
    assert TabMeasure._readings_before_session(fake) == 0
    fake._session_guard.before = 7
    assert TabMeasure._readings_before_session(fake) == 7
