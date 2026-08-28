"""Engine → stock-chartread safety net and the richer calibration prompt (#126).

mavtop's i1Pro1 measures fine under stock ArgyllCMS (spotread and chartread) but
ChromIQ's own engine cannot drive it. Since v3.14.0 turns the engine on by
default, a user in that position could no longer measure at all — so a failed
engine start now restarts the run on stock chartread automatically.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication

from workflow.measure_manager import MeasureManager, MeasureParams


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


class _RecordingRunner:
    """ArgyllRunner stand-in that records launches and hands back on_finish."""

    def __init__(self) -> None:
        self.runs: list[dict] = []
        self.writes: list[str] = []

    def run(self, tool, args, cwd, on_line=None, on_finish=None,
            use_pty=False) -> None:
        self.runs.append({"tool": str(tool), "args": list(args),
                          "on_line": on_line, "on_finish": on_finish,
                          "use_pty": use_pty})

    def write_stdin(self, text: str) -> None:
        self.writes.append(text)

    def abort(self) -> None:
        pass


def _start_engine_run(tmp_path: Path):
    """Start a measurement with the engine active; return the moving parts."""
    runner = _RecordingRunner()
    mgr = MeasureManager(runner)
    mgr._guided_state = "disabled"
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("")
    params = MeasureParams(ti1_path=ti1,
                           engine_helper=Path("/fake/chromiq-chartread"))
    lines: list[str] = []
    finished: list[int] = []
    mgr.start(params, lines.append, finished.append)
    assert len(runner.runs) == 1, "engine should have been launched"
    assert "chromiq-chartread" in runner.runs[0]["tool"]
    return mgr, runner, lines, finished


def _feed_engine(mgr: MeasureManager, event: dict, lines: list[str]) -> None:
    mgr._handle_engine_line(json.dumps(event), lines.append)


def _finish(runner: _RecordingRunner, code: int, idx: int = -1) -> None:
    runner.runs[idx]["on_finish"](code)


# --- the safety net -------------------------------------------------------

def test_engine_coms_failure_restarts_on_stock_chartread(tmp_path):
    """Normal case: the engine cannot talk to the instrument and read nothing."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)

    assert len(runner.runs) == 2, "should have restarted on stock chartread"
    assert runner.runs[1]["tool"] == "chartread"
    assert runner.runs[1]["use_pty"] is True, "stock path needs a PTY console"
    assert finished == [], "the caller must not see the failed engine attempt"
    assert any("ArgyllCMS" in ln for ln in lines), "user should be told"


def test_calibration_failure_also_falls_back(tmp_path):
    """mavtop's shape: the instrument never finishes its initial calibration."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _feed_engine(mgr, {"event": "error", "kind": "cal_failed",
                       "detail": "no answer from device"}, lines)
    _finish(runner, 1)

    assert len(runner.runs) == 2 and runner.runs[1]["tool"] == "chartread"
    assert any("no answer from device" in ln for ln in lines)


def test_no_fresh_restart_once_a_strip_was_read(tmp_path):
    """A FRESH restart would discard or duplicate real readings — never do it.
    With no saved .ti3 to resume from, the failed run ends normally (the resume
    path in test_resume_fallback_* handles the case where one exists)."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _feed_engine(mgr, {"event": "strip_read", "strip": "A", "worst_de": 0.4}, lines)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)

    assert len(runner.runs) == 1, "must not fresh-restart after real readings"
    assert finished == [1]


# --- the with-progress resume fallback (#134) -----------------------------

def _partial_ti3(tmp_path: Path, readings: int = 1) -> Path:
    """A <stem>.ti3 standing in for the engine's autosave.

    **It has to be a real CGATS file with real rows in it.** This used to be
    ``CTI3\\nNUMBER_OF_SETS 1\\n`` — a header and nothing else — which passed the
    old "is the file non-empty?" test while containing no readings whatsoever.
    ``chartread -r`` refuses such a file outright, so the rescue it was standing
    in for could never have worked on it.

    The real autosave goes through ArgyllCMS's own ``save_ti3()``
    (``cq_write_ti3_atomic``, native/chartread_helper/chromiq_chartread.c:447),
    which writes a complete file every time — header, format block, and one row
    per reading taken so far. This mirrors that.
    """
    ti3 = tmp_path / "chart.ti3"
    rows = "\n".join(f"{i + 1} 50 50 50 20 20 20" for i in range(readings))
    ti3.write_text(
        "CTI3\n\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n"
        f"NUMBER_OF_SETS {readings}\nBEGIN_DATA\n{rows}\nEND_DATA\n")
    return ti3


def _header_only_ti3(tmp_path: Path) -> Path:
    """A `.ti3` with a header and no readings — what the old stand-in was."""
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text("CTI3\nNUMBER_OF_SETS 1\n")
    return ti3


def test_resume_fallback_when_a_partial_ti3_exists(tmp_path):
    """Instrument dies mid-chart but strips are saved: continue on stock
    chartread RESUMING (-r), keeping the readings, and don't surface the fail."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _partial_ti3(tmp_path)
    resumed: list[str] = []
    mgr.engine_fell_back_resumed.connect(resumed.append)

    _feed_engine(mgr, {"event": "strip_read", "strip": "A", "worst_de": 0.4}, lines)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)

    assert len(runner.runs) == 2, "should have resumed on stock chartread"
    assert runner.runs[1]["tool"] == "chartread"
    assert "-r" in runner.runs[1]["args"], "must resume, not restart"
    assert runner.runs[1]["use_pty"] is True
    assert finished == [], "the caller must not see the failed engine attempt"
    assert resumed == ["communication problem"]
    assert any("kept" in ln.lower() for ln in lines), "user should be reassured"


def test_resume_fallback_backs_up_the_partial(tmp_path):
    """The partial .ti3 is copied aside first, so readings survive a bad resume."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _partial_ti3(tmp_path)
    _feed_engine(mgr, {"event": "strip_read", "strip": "A", "worst_de": 0.4}, lines)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)

    assert (tmp_path / "chart.ti3.engine-partial").is_file()


def test_resume_fallback_does_not_double_add_r(tmp_path):
    """When the run was already a resume (-r), don't add a second one."""
    runner = _RecordingRunner()
    mgr = MeasureManager(runner)
    mgr._guided_state = "disabled"
    ti1 = tmp_path / "chart.ti1"; ti1.write_text("")
    _partial_ti3(tmp_path)
    params = MeasureParams(ti1_path=ti1, resume=True,
                           engine_helper=Path("/fake/chromiq-chartread"))
    mgr.start(params, [].append, [].append)
    _feed_engine(mgr, {"event": "strip_read", "strip": "A"}, [])
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, [])
    _finish(runner, 1)

    assert runner.runs[1]["args"].count("-r") == 1


def test_no_resume_fallback_after_user_quit(tmp_path):
    """A deliberate stop is never second-guessed, even with saved strips."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _partial_ti3(tmp_path)
    _feed_engine(mgr, {"event": "strip_read", "strip": "A"}, lines)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    mgr.send_key("\x1b")
    _finish(runner, 1)

    assert len(runner.runs) == 1
    assert finished == [1]


def test_resume_fallback_happens_only_once(tmp_path):
    """If the resumed stock run also fails, the caller sees it — no loop."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _partial_ti3(tmp_path)
    _feed_engine(mgr, {"event": "strip_read", "strip": "A"}, lines)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)
    assert len(runner.runs) == 2

    _finish(runner, 1)                    # the stock resume fails too
    assert len(runner.runs) == 2
    assert finished == [1]


def test_no_fallback_when_the_user_stopped_the_run(tmp_path):
    """Esc/quit exits non-zero, but that is not an engine failure."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    mgr.send_key("\x1b")
    _finish(runner, 1)

    assert len(runner.runs) == 1
    assert finished == [1]


def test_no_fallback_on_a_clean_exit(tmp_path):
    """A successful engine run must never be re-run."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _finish(runner, 0)
    assert len(runner.runs) == 1
    assert finished == [0]


def test_fallback_happens_only_once(tmp_path):
    """A failing instrument must never put us in a restart loop."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)
    assert len(runner.runs) == 2

    # stock chartread fails too — the caller must now see it, not a third run
    _finish(runner, 1)
    assert len(runner.runs) == 2
    assert finished == [1]


# --- the calibration prompt ----------------------------------------------

def test_cal_required_carries_condition_message_and_optional(tmp_path):
    """The instrument's own request must reach the dialog intact."""
    mgr, runner, lines, _ = _start_engine_run(tmp_path)
    seen: list[tuple] = []
    mgr.calibration_prompt.connect(lambda *a: seen.append(a))

    _feed_engine(mgr, {"event": "cal_required", "cond": "man_ref_white",
                       "id": "Place instrument on white reference",
                       "optional": True}, lines)

    assert seen == [("man_ref_white", "Place instrument on white reference", True)]


def test_stock_chartread_prompt_still_works(tmp_path):
    """The console path has no condition to report, but must still prompt."""
    runner = _RecordingRunner()
    mgr = MeasureManager(runner)
    mgr._guided_state = "disabled"
    seen: list[tuple] = []
    mgr.calibration_prompt.connect(lambda *a: seen.append(a))

    mgr._handle_line("Set instrument sensor to calibration position,", lambda _l: None)

    assert seen == [("", "", False)]


def test_helper_that_never_ran_also_falls_back(tmp_path):
    """A helper that exits without saying anything never really started —
    missing execute permission, macOS quarantine, an immediate crash. Stock
    chartread is exactly the right thing to try instead."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _finish(runner, 126)                      # 126 = not executable

    assert len(runner.runs) == 2
    assert runner.runs[1]["tool"] == "chartread"
    assert finished == []


def test_a_helper_that_spoke_but_hit_no_error_is_not_retried(tmp_path):
    """It ran and reported normally, so a non-zero exit is its own business —
    retrying would just repeat whatever went wrong."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _feed_engine(mgr, {"event": "session_start", "strips": []}, lines)
    _finish(runner, 3)

    assert len(runner.runs) == 1
    assert finished == [3]


# --- the instrument's instruction text ------------------------------------
# Captured from a real X-Rite ColorMunki: chartread's condition-identifier
# buffer is uninitialised for man_cal_smode, so the helper serialises stack
# bytes. It must never reach the dialog.

def test_garbage_instruction_from_a_real_colormunki_is_dropped(tmp_path):
    mgr, runner, lines, _ = _start_engine_run(tmp_path)
    seen: list[tuple] = []
    mgr.calibration_prompt.connect(lambda *a: seen.append(a))

    _feed_engine(mgr, {"event": "cal_required", "cond": "man_cal_smode",
                       "id": "4k2\ufffd\u0001", "optional": False}, lines)

    assert seen == [("man_cal_smode", "", False)], \
        "binary junk must not be shown as an instruction"


@pytest.mark.parametrize("junk", ["", "   ", "ab", "\x01\x02\x03\x04", "1234", "42"])
def test_unusable_instruction_strings_are_dropped(tmp_path, junk):
    mgr, runner, lines, _ = _start_engine_run(tmp_path)
    seen: list[tuple] = []
    mgr.calibration_prompt.connect(lambda *a: seen.append(a))
    _feed_engine(mgr, {"event": "cal_required", "cond": "x", "id": junk}, lines)
    assert seen[0][1] == ""


def test_a_real_instruction_is_passed_through(tmp_path):
    mgr, runner, lines, _ = _start_engine_run(tmp_path)
    seen: list[tuple] = []
    mgr.calibration_prompt.connect(lambda *a: seen.append(a))
    _feed_engine(mgr, {"event": "cal_required", "cond": "man_ref_white",
                       "id": "Place instrument on white reference"}, lines)
    assert seen[0][1] == "Place instrument on white reference"


# --- automatic calibration retry ------------------------------------------
# The engine BLOCKS waiting for an answer after a failed calibration, so a
# reply must always be sent or the run deadlocks — the failure dialog only
# runs once the process has exited, which then never happens.

@pytest.fixture(autouse=True)
def _fast_retry_pause(monkeypatch):
    """Keep the real timer in play but drop its 2 s pause to milliseconds, so
    the suite doesn't spend half a minute waiting for USB rails to recover."""
    import workflow.measure_manager as mm
    monkeypatch.setattr(mm, "CAL_RETRY_PAUSE_MS", 5)


def _drain_timers(ms: int = 60) -> None:
    """Let the retry's single-shot timer fire."""
    from PyQt6.QtCore import QCoreApplication, QElapsedTimer
    t = QElapsedTimer()
    t.start()
    while t.elapsed() < ms:
        QCoreApplication.processEvents()


def test_failed_calibration_is_retried_automatically(tmp_path):
    """Normal case for a flaky instrument: retry instead of giving up."""
    from workflow.measure_manager import CAL_AUTO_RETRIES
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    seen: list[tuple] = []
    mgr.calibration_retrying.connect(lambda *a: seen.append(a))

    _feed_engine(mgr, {"event": "error", "kind": "cal_failed",
                       "detail": "no answer from device"}, lines)
    _drain_timers()

    assert seen == [(1, CAL_AUTO_RETRIES)]
    assert '{"cmd": "retry"}' in "".join(runner.writes)
    assert any("attempt 1" in ln for ln in lines)


def test_retries_are_bounded_then_the_run_is_ended(tmp_path):
    """After the budget is spent, report the failure and unblock the engine."""
    from workflow.measure_manager import CAL_AUTO_RETRIES
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    failures: list[str] = []
    mgr.inst_init_failed.connect(failures.append)

    for _ in range(CAL_AUTO_RETRIES + 1):
        _feed_engine(mgr, {"event": "error", "kind": "cal_failed",
                           "detail": "no answer"}, lines)
        _drain_timers()

    assert len(failures) == 1, "the user is told exactly once, at the end"
    writes = "".join(runner.writes)
    assert writes.count('"retry"') == CAL_AUTO_RETRIES
    assert '{"cmd": "quit"}' in writes, "the engine must never be left blocked"


def test_a_successful_calibration_restores_the_retry_budget(tmp_path):
    """Instruments can calibrate more than once; each step gets its own tries."""
    from workflow.measure_manager import CAL_AUTO_RETRIES
    mgr, runner, lines, _ = _start_engine_run(tmp_path)
    _feed_engine(mgr, {"event": "error", "kind": "cal_failed", "detail": "x"}, lines)
    _drain_timers()
    assert mgr._cal_retries_left == CAL_AUTO_RETRIES - 1

    _feed_engine(mgr, {"event": "cal_done"}, lines)
    assert mgr._cal_retries_left == CAL_AUTO_RETRIES


def test_no_retry_after_the_user_stopped_the_run(tmp_path):
    """A deliberate stop must not be second-guessed by an automatic retry."""
    mgr, runner, lines, _ = _start_engine_run(tmp_path)
    failures: list[str] = []
    mgr.inst_init_failed.connect(failures.append)

    mgr.send_key("\x1b")
    runner.writes.clear()
    _feed_engine(mgr, {"event": "error", "kind": "cal_failed", "detail": "x"}, lines)
    _drain_timers()

    assert failures == ["x"]
    assert '"retry"' not in "".join(runner.writes)


def test_the_automatic_quit_still_allows_the_argyll_fallback(tmp_path):
    """Ending the run ourselves must not look like a user abort, or the
    stock-chartread fallback would never get its turn."""
    from workflow.measure_manager import CAL_AUTO_RETRIES
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    for _ in range(CAL_AUTO_RETRIES + 1):
        _feed_engine(mgr, {"event": "error", "kind": "cal_failed",
                           "detail": "no answer"}, lines)
        _drain_timers()

    assert mgr._user_quit is False
    _finish(runner, 1)
    assert len(runner.runs) == 2 and runner.runs[1]["tool"] == "chartread"


# --- configurable retry count (mavtop: "make it 10") ----------------------

def _start_engine_run_retries(tmp_path, retries):
    """Like _start_engine_run but with an explicit per-run retry budget."""
    runner = _RecordingRunner()
    mgr = MeasureManager(runner)
    mgr._guided_state = "disabled"
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("")
    params = MeasureParams(ti1_path=ti1,
                           engine_helper=Path("/fake/chromiq-chartread"),
                           cal_auto_retries=retries)
    mgr.start(params, [].append, [].append)
    return mgr, runner


def test_retry_count_follows_the_setting(tmp_path):
    """mavtop's request: raising the setting raises the number of attempts."""
    mgr, runner = _start_engine_run_retries(tmp_path, 10)
    for _ in range(11):                       # 10 retries + the final give-up
        _feed_engine(mgr, {"event": "error", "kind": "cal_failed",
                           "detail": "misread"}, [])
        _drain_timers()
    writes = "".join(runner.writes)
    assert writes.count('"retry"') == 10
    assert '{"cmd": "quit"}' in writes


def test_retries_can_be_turned_off(tmp_path):
    """0 = no retries: report the failure immediately and end the run."""
    mgr, runner = _start_engine_run_retries(tmp_path, 0)
    failures: list[str] = []
    mgr.inst_init_failed.connect(failures.append)
    _feed_engine(mgr, {"event": "error", "kind": "cal_failed",
                       "detail": "misread"}, [])
    _drain_timers()
    assert '"retry"' not in "".join(runner.writes)
    assert failures == ["misread"]


def test_an_absurd_setting_is_clamped(tmp_path):
    """A value past the ceiling must not let the run loop for ever."""
    from workflow.measure_manager import CAL_AUTO_RETRIES_MAX
    mgr, runner = _start_engine_run_retries(tmp_path, 9999)
    assert mgr._cal_auto_retries == CAL_AUTO_RETRIES_MAX


def test_default_budget_when_unset(tmp_path):
    """No per-run value → the built-in default, so old callers are unaffected."""
    from workflow.measure_manager import CAL_AUTO_RETRIES
    mgr, runner, lines, finished = _start_engine_run(tmp_path)  # sets no retries
    assert mgr._cal_auto_retries == CAL_AUTO_RETRIES


def test_a_header_only_autosave_is_not_resumed(tmp_path):
    """The stand-in this file used to rely on: a `.ti3` carrying a header and no
    readings. `chartread -r` refuses it — *"Unable to read chart being resumed"*
    — so handing it over would just fail the measurement a second time, which is
    exactly what happened to Knut (#148). There is nothing in it to lose.
    """
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _header_only_ti3(tmp_path)
    _feed_engine(mgr, {"event": "strip_read", "strip": "A"}, lines)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)
    for run in runner.runs[1:]:
        assert "-r" not in run["args"], (
            "resumed from a file with no readings in it")


def test_a_real_autosave_is_still_resumed(tmp_path):
    """The counterweight: the rescue must keep working for the file the engine
    actually writes, or a crash costs the user every strip they measured."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _partial_ti3(tmp_path, readings=3)
    _feed_engine(mgr, {"event": "strip_read", "strip": "A"}, lines)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)
    assert len(runner.runs) == 2, "the rescue did not happen"
    assert "-r" in runner.runs[1]["args"]


# ---------------------------------------------------------------------------
# #159 — a chart stock chartread REFUSES has no fallback to fall back to
#
# The 2026-08-28 log, verbatim: the helper refused a CR30 chart, ChromIQ
# announced "restarting on stock chartread", and stock chartread died on
# `Unrecognised chart target instrument 'CR30'`. Two failures, the second more
# confusing than the first, plus a translated paragraph promising a rescue that
# could not happen. All THREE relaunch sites are gated, not just the one that
# fired that day.
# ---------------------------------------------------------------------------

def _start_cr30_run(tmp_path: Path, **kw):
    runner = _RecordingRunner()
    mgr = MeasureManager(runner)
    mgr._guided_state = "disabled"
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("")
    params = MeasureParams(ti1_path=ti1,
                           engine_helper=Path("/fake/chromiq-chartread"),
                           stock_reader_cannot_read=True, **kw)
    lines: list[str] = []
    finished: list[int] = []
    refused: list[str] = []
    mgr.engine_fallback_refused.connect(refused.append)
    mgr.start(params, lines.append, finished.append)
    assert len(runner.runs) == 1
    return mgr, runner, lines, finished, refused


def test_a_refused_chart_never_relaunches_on_stock_chartread(tmp_path):
    """THE REPORTED BUG. One launch, one ending, and the caller hears about it."""
    mgr, runner, lines, finished, refused = _start_cr30_run(tmp_path)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)

    assert len(runner.runs) == 1, "stock chartread must not be launched"
    assert finished == [1], "the run ends here, on the helper's own exit"
    assert len(refused) == 1
    assert not any("ArgyllCMS" in ln for ln in lines), \
        "no promise of a reader that would refuse the chart"


def test_an_ordinary_chart_still_falls_back(tmp_path):
    """The mutation guard: the gate must be the FLAG, not the situation.
    mavtop's i1Pro1 depends on this rescue and must keep it."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)
    assert len(runner.runs) == 2 and runner.runs[1]["tool"] == "chartread"


def test_the_resume_fallback_is_gated_too_and_keeps_its_promise_unspoken(
        tmp_path):
    """The dangerous one. It fires AFTER the user has measured part of the
    chart and announces "every strip you have already measured has been saved
    and will be kept" BEFORE relaunching — so the user is told they are
    continuing and then watches it die."""
    mgr, runner, lines, finished, refused = _start_cr30_run(tmp_path)
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(
        "CTI3\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 10 10 10\nEND_DATA\n",
        encoding="utf-8")
    from workflow.measurement_state import has_any_readings
    assert has_any_readings(ti3), "the premise: this .ti3 IS resumable"
    _feed_engine(mgr, {"event": "patch_read", "loc": "A1"}, lines)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)

    assert len(runner.runs) == 1, "the resume fallback must not fire either"
    assert not any("carry on measuring" in ln for ln in lines)
    assert len(refused) == 1


def test_the_mode_fallback_is_gated_too(tmp_path):
    """Unreachable once -x lands (no instrument is opened, so no mode can be
    reported), but free to gate and it must not be the one left open."""
    mgr, runner, lines, finished, refused = _start_cr30_run(tmp_path)
    mgr._engine_mode_fallback = True
    _finish(runner, 1)
    assert len(runner.runs) == 1
    assert not any("reads whole sheets" in ln for ln in lines)


def test_a_clean_run_is_untouched(tmp_path):
    """Boundary: exit 0 must end exactly as it always did."""
    mgr, runner, lines, finished, refused = _start_cr30_run(tmp_path)
    _finish(runner, 0)
    assert finished == [0] and refused == [] and len(runner.runs) == 1


def test_the_user_stopping_it_is_not_a_refusal(tmp_path):
    """Boundary: a deliberate quit is the user's ending, not a failure to
    explain. `_user_quit` already suppresses every other fallback."""
    mgr, runner, lines, finished, refused = _start_cr30_run(tmp_path)
    mgr._user_quit = True
    _finish(runner, 1)
    assert refused == [], "no failure window for a run the user ended"
    assert finished == [1] and len(runner.runs) == 1


# --- the reason string: the helper HAD said what was wrong -----------------

def test_the_helpers_own_error_sentence_becomes_the_reason(tmp_path):
    """`_engine_fatal` is only ever set from a typed JSON event, so a helper
    that dies before emitting one left the log saying "(unknown error)" while
    the sentence itself was one line above it, on stderr, as prose."""
    mgr, runner, lines, finished, refused = _start_cr30_run(tmp_path)
    mgr._handle_engine_line(
        "chromiq-chartread: Error - The chart was made for 'CR30', which "
        "ChromIQ reads itself. Measure it in ChromIQ, or use -x to supply "
        "values.", lines.append)
    _finish(runner, 1)
    assert refused and refused[0].startswith("The chart was made for 'CR30'")


def test_a_typed_event_still_wins_over_the_prose(tmp_path):
    """Ordering: the JSON channel is the authority when it spoke at all."""
    mgr, runner, lines, finished, refused = _start_cr30_run(tmp_path)
    mgr._handle_engine_line("chromiq-chartread: Error - something vague",
                            lines.append)
    _feed_engine(mgr, {"event": "error", "kind": "coms"}, lines)
    _finish(runner, 1)
    assert refused == ["communication problem"]


def test_prose_capture_never_sets_the_fallback_trigger(tmp_path):
    """CRITICAL: `_engine_fatal is not None` is a fallback TRIGGER for every
    instrument. Capturing prose into it would silently change when an ordinary
    chart falls back. It must stay in its own field."""
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    mgr._handle_engine_line("chromiq-chartread: Error - boom", lines.append)
    assert mgr._engine_fatal is None
    assert mgr._engine_error_prose == "boom"


def test_ordinary_prose_is_not_mistaken_for_a_fatal(tmp_path):
    mgr, runner, lines, finished = _start_engine_run(tmp_path)
    for ln in ("Reading strip A1", "Result is XYZ: 10 10 10",
               "Place instrument on spot A1"):
        mgr._handle_engine_line(ln, lines.append)
    assert mgr._engine_error_prose is None


def test_the_ending_message_is_in_the_catalogue_and_awaits_approval():
    from workflow import measurement_messages as M
    assert "M-CR30-READ-ENDED" in M.CATALOGUE
    assert M.CATALOGUE["M-CR30-READ-ENDED"].approved is False
    title, body = M.M_CR30_READ_ENDED.render(reason="the helper said so")
    assert "the helper said so" in body
    assert "ArgyllCMS chartread does not know the CR30" in body
