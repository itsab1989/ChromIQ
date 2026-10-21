"""M3 (jctay's Windows log, 2026-10-20): the engine's save after an accepted
strip failed (``autosave_rename``) and nothing happened.

Before: on Windows ``remove(.ti3)`` then ``rename(.cqtmp, .ti3)``, two steps,
so a refused rename left NO .ti3 and every strip only in the .cqtmp; the error
event was ignored by the app; a resume never looked at the .cqtmp.

Now:
* the engine replaces in one step (MoveFileEx REPLACE_EXISTING on Windows,
  rename() on POSIX) with a short retry, keeps the .cqtmp when it still fails
  and says so, naming the kept file and the system's error number;
* the app writes M-AUTOSAVE-NOT-SAVED into the Measure log;
* loading the chart, Start, and the engine-fallback resume put a kept .cqtmp
  that is newer than the .ti3 in its place.

The engine half is proved on POSIX by making the .ti3 path a non-empty folder,
which rename() refuses; the Windows branch is compiled by the Windows build
(and was cross-compiled with mingw-w64 when this was written).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "native" / "chartread_helper" / "chromiq_chartread.c"

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")

TI3 = """CTI3

DESCRIPTOR "Argyll Calibrated Device Response Data"
ORIGINATOR "Argyll chartread"
CREATED "Tue Oct 20 11:51:31 2026"
DEVICE_CLASS "OUTPUT"
COLOR_REP "RGB_XYZ"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS {n}
BEGIN_DATA
{rows}
END_DATA
"""


def _ti3(path: Path, n: int) -> None:
    rows = "\n".join(f"{i + 1} 50.0 50.0 50.0 20.0 21.0 22.0" for i in range(n))
    path.write_text(TI3.format(n=n, rows=rows), encoding="utf-8")


# ---------------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------------
def test_the_windows_branch_replaces_in_one_step_with_a_retry():
    src = SRC.read_text(encoding="utf-8")
    body = src[src.index("static void cq_write_ti3_atomic(void)"):]
    body = body[:body.index("\n}\n")]
    assert "remove(realname);" not in body, "two-step replace is back"
    assert "MoveFileExA(tmpname, realname" in body
    assert "MOVEFILE_REPLACE_EXISTING" in body
    assert "ERROR_SHARING_VIOLATION" in body and "Sleep(" in body
    assert '\\"temp\\":' in body and '\\"code\\":' in body


@needs_helper
def test_a_refused_save_keeps_the_temp_file_and_says_so(tmp_path):
    from test_chartread_engine import _make_chart, _quit
    base = _make_chart(tmp_path, randomised=False)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    ti3 = base.with_suffix(".ti3")
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        # rename() over a non-empty folder is refused on every POSIX system
        ti3.mkdir()
        (ti3 / "blocker").write_text("x")
        idx = s.event_index()
        s.send(cmd="trigger", ready_ms="0")
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=idx)
        deadline = time.monotonic() + 10
        err = None
        while time.monotonic() < deadline and err is None:
            for e in s.events[idx:]:
                if e.get("event") == "error" and e.get("kind") == "autosave_rename":
                    err = e
            time.sleep(0.05)
        _quit(s)
    assert err is not None, "the failed save was not reported"
    tmp = Path(str(ti3) + ".cqtmp")
    assert err["detail"].endswith(ti3.name)
    assert err["temp"].endswith(tmp.name)
    assert isinstance(err["code"], int) and err["code"] != 0
    assert tmp.is_file(), "the temp file holding the readings was not kept"
    from workflow.measurement_state import has_any_readings
    assert has_any_readings(tmp)


# ---------------------------------------------------------------------------
# the recovery
# ---------------------------------------------------------------------------
def test_a_newer_kept_save_replaces_the_measurement(tmp_path):
    from workflow.measurement_state import (engine_autosave_temp,
                                            recover_engine_autosave)
    ti3 = tmp_path / "chart.ti3"
    _ti3(ti3, 3)
    tmp = engine_autosave_temp(ti3)
    _ti3(tmp, 6)
    os.utime(ti3, (time.time() - 60, time.time() - 60))
    assert recover_engine_autosave(ti3) is True
    assert not tmp.exists()
    assert "NUMBER_OF_SETS 6" in ti3.read_text(encoding="utf-8")


def test_a_kept_save_with_no_measurement_beside_it_is_used(tmp_path):
    from workflow.measurement_state import (engine_autosave_temp,
                                            recover_engine_autosave)
    ti3 = tmp_path / "chart.ti3"
    _ti3(engine_autosave_temp(ti3), 4)
    assert recover_engine_autosave(ti3) is True
    assert "NUMBER_OF_SETS 4" in ti3.read_text(encoding="utf-8")


def test_an_older_or_empty_temp_file_is_left_alone(tmp_path):
    from workflow.measurement_state import (engine_autosave_temp,
                                            recover_engine_autosave)
    ti3 = tmp_path / "chart.ti3"
    tmp = engine_autosave_temp(ti3)
    _ti3(tmp, 2)
    os.utime(tmp, (time.time() - 60, time.time() - 60))
    _ti3(ti3, 5)
    assert recover_engine_autosave(ti3) is False
    assert "NUMBER_OF_SETS 5" in ti3.read_text(encoding="utf-8")
    tmp.write_text("CTI3\n", encoding="utf-8")       # header only: nothing to keep
    os.utime(tmp, None)
    assert recover_engine_autosave(ti3) is False
    assert recover_engine_autosave(None) is False


def test_load_start_and_the_fallback_resume_all_recover():
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    from workflow.measure_manager import MeasureManager
    assert "self._recover_engine_autosave()" in inspect.getsource(TabMeasure.set_ti1_path)
    assert "self._recover_engine_autosave()" in inspect.getsource(TabMeasure._on_start)
    assert "recover_engine_autosave(ti3)" in inspect.getsource(
        MeasureManager._resumable_partial_ti3)


# ---------------------------------------------------------------------------
# the app says so
# ---------------------------------------------------------------------------
def test_the_error_is_written_into_the_measure_log():
    from workflow.measure_manager import MeasureManager
    lines: list = []
    mm = MeasureManager.__new__(MeasureManager)
    MeasureManager._on_autosave_failed(
        mm, {"event": "error", "kind": "autosave_rename",
             "detail": r"C:\\Users\\j\\ChromIQ\\p\\runs\\run1\\p.ti3",
             "temp": r"C:\\Users\\j\\ChromIQ\\p\\runs\\run1\\p.ti3.cqtmp",
             "code": 32}, lines.append)
    assert len(lines) == 1
    line = lines[0]
    assert line.startswith("[Engine] ChromIQ could not save the readings to ")
    assert "(error 32)" in line and "p.ti3.cqtmp" in line
    assert "{" not in line
