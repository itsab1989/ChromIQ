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

def _partial_ti3(tmp_path: Path) -> Path:
    """A non-empty <stem>.ti3 standing in for the engine's autosave."""
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
