"""Beta 2: quitting ChromIQ ran the measurement's finish handler.

The owner saw this in his terminal on every quit, three times in one evening:

    [WARNING] workflow.measure_manager: the chart's instrument is one stock
    chartread cannot read (unknown error) — not falling back

I first told him it fired on a deliberate Stop. **That was wrong**, and review
proved it: all seven occurrences in his log sit immediately after `closeEvent`'s
geometry writes, with no `abort()` line anywhere near them.

The mechanism is `ArgyllRunner.cleanup()`. It kills the process, and
`waitForFinished` then delivers `finished` → `_on_finished` → the per-run
`on_finish` callback → the measurement session's finish handler, in the middle
of application shutdown. Exit code 9 is SIGKILL and `_user_quit` is False —
because the user never asked to stop, they asked to quit — so the #159 branch
warns about a failure that never happened.

Disconnecting `self.finished` did NOT prevent it, and that is why it survived:
`_on_finished` calls the per-run callback DIRECTLY, on purpose, so a chained
run can register its own. The public signal is not the path that matters.

⚠ THE WARNING IS THE HARMLESS HALF. Latent in the same code: a non-CR30 engine
session quit before its first event would RELAUNCH stock chartread during
shutdown, leaving an orphan process behind the closing app. One fix removes
both.
"""
from __future__ import annotations

import inspect

from core.argyll_runner import ArgyllRunner


def _cleanup_source() -> str:
    return inspect.getsource(ArgyllRunner.cleanup)


def test_the_per_run_callbacks_are_dropped():
    src = _cleanup_source()
    assert "self._run_on_finish = None" in src, (
        "quitting still runs the measurement session's finish handler")
    assert "self._run_on_line = None" in src


def test_they_are_dropped_before_the_process_is_killed():
    """After the kill is too late: waitForFinished delivers `finished`
    synchronously, and the handler has already run."""
    src = _cleanup_source()
    assert src.index("self._run_on_finish = None") < src.index(".kill()"), (
        "the callbacks are cleared after the kill, so the finish handler has "
        "already fired by then")


def test_the_qprocess_signal_itself_is_disconnected():
    """Not just the runner's public one — that was the mistake. `_on_finished`
    calls the per-run callback directly, so the public signal is not the path
    that matters."""
    src = _cleanup_source()
    assert "self._process.finished, self._on_finished" in src, (
        "QProcess.finished still reaches _on_finished during shutdown")
    assert "_sig.disconnect(_slot)" in src


def test_the_public_signal_disconnect_is_still_there():
    """It was not wrong, only insufficient. Removing it would reintroduce a
    different fault — signals firing into freed C++ objects at teardown, the
    segfault this method was written for."""
    src = _cleanup_source()
    assert "self.line_received, self.finished, self._pty_done" in src


def test_cleanup_still_kills_what_it_must():
    src = _cleanup_source()
    assert ".kill()" in src and "waitForFinished" in src
