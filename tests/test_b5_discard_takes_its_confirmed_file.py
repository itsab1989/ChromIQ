"""4.3.5 beta 5 regression review, fix 1: "Discard and stop" on a resumed
verification moved the session's ``test-verify.ti3`` into
``<date>/old/<stamp>/discarded-*`` and left its yellow memory
``test-verify.confirmed.json`` at the ``verifications/`` root, beside a
measurement it does not describe. The memory now goes with the readings, and
a measurement put back gets its own memory back.
"""
from __future__ import annotations

import json
import os
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



# ---- 1. the yellow memory goes with the discarded readings ---------------
def test_a_staged_resume_leaves_no_confirmed_file_beside_the_chart(tmp_path):
    """Knut's run 5, resumed verification: the copy beside the chart had no
    memory when it was staged, the session wrote one, Discard."""
    v = tmp_path / "verifications"
    dated = v / "2026-10-10_095840" / "test-verify.ti3"
    _ti3(dated, "10.0")
    _mem(dated, "dated")
    staged = v / "test-verify.ti3"
    staged.write_bytes(dated.read_bytes())
    s = MeasurementSession(staged, None, dated.parent / "old")
    s.begin()
    _ti3(staged, "55.0")              # the engine wrote the session's readings
    _mem(staged, "session")           # and the session confirmed patches
    out = s.finish(resumed=True, discarded=True)
    assert not confirmed_path(staged).exists(), \
        "the session's confirmed file stayed at the verifications/ root"
    moved = confirmed_path(out.kept_beside)
    assert moved.is_file() and _tag(out.kept_beside) == "session", \
        "the session's memory belongs beside discarded-test-verify.ti3"
    assert _tag(dated) == "dated", "the date's own memory is untouched"


def test_a_discard_puts_back_the_earlier_measurements_own_memory(tmp_path):
    ti3 = tmp_path / "run" / "test.ti3"
    _ti3(ti3, "10.0")
    _mem(ti3, "earlier")
    s = MeasurementSession(ti3, None, tmp_path / "run" / "old")
    s.begin()
    _ti3(ti3, "55.0")
    _mem(ti3, "session")
    out = s.finish(resumed=False, discarded=True)
    assert out.restored and "10.0" in ti3.read_text(encoding="latin-1")
    assert _tag(ti3) == "earlier"
    assert _tag(out.kept_beside) == "session"


def test_a_discard_that_wrote_no_readings_still_drops_the_sessions_memory(tmp_path):
    ti3 = tmp_path / "run" / "test.ti3"
    _ti3(ti3, "10.0")
    _mem(ti3, "earlier")
    s = MeasurementSession(ti3, None, tmp_path / "run" / "old")
    s.begin()
    _mem(ti3, "session")              # confirmed, but the readings unchanged
    s.finish(resumed=True, discarded=True)
    assert _tag(ti3) == "earlier"
    assert list((tmp_path / "run" / "old").rglob("discarded-test.confirmed.json"))


def test_an_untouched_memory_stays_where_it_is(tmp_path):
    ti3 = tmp_path / "run" / "test.ti3"
    _ti3(ti3, "10.0")
    _mem(ti3, "earlier")
    s = MeasurementSession(ti3, None, tmp_path / "run" / "old")
    s.begin()
    s.finish(resumed=True, discarded=True)
    assert _tag(ti3) == "earlier"
    assert not list((tmp_path / "run" / "old").rglob("discarded-*"))
