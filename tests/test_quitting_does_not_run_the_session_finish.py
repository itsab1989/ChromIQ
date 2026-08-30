"""Beta 2: quitting ChromIQ warned about a failure that never happened.

The owner saw this in his terminal on every quit, three times in one evening:

    [WARNING] workflow.measure_manager: the chart's instrument is one stock
    chartread cannot read (unknown error) — not falling back

I first told him it fired on a deliberate Stop. **That was wrong**, and review
proved it: all seven occurrences in his log sit immediately after `closeEvent`'s
geometry writes, with no `abort()` line anywhere near them.

`ArgyllRunner.cleanup()` kills the helper, and `waitForFinished` then delivers
`finished` → `_on_finished` → the per-run callback synchronously — so the
session's finish handler runs while the window is closing, with exit code 9
(SIGKILL) and `_user_quit` False, because the user never asked to STOP. They
asked to QUIT.

⚠ AND THE FIRST FIX FOR THIS WAS TOO BLUNT, WHICH IS THE POINT OF THIS FILE.
It dropped the per-run callbacks at cleanup. That silenced the warning and ALSO
silenced the §3b / M-TI3-EMPTY reconciliation that legitimately runs when a
session ends, leaving an empty `.ti3` still claiming to be a measurement and the
one it replaced stranded in `old/`. Knut specified that reconciliation.
**Silencing a false alarm must never silence real work.**

The fix is to say WHY the session is ending. `_user_quit` is exactly the flag
the #159 branch and the fallback-relaunch branches test, so setting it removes
the warning and stops stock chartread being relaunched into a closing app —
while the finish handler still runs, and still reconciles.
"""
from __future__ import annotations

import inspect

from core.argyll_runner import ArgyllRunner
from workflow.measure_manager import MeasureManager


def test_the_manager_can_be_told_the_app_is_quitting():
    assert hasattr(MeasureManager, "note_app_quitting")


def test_it_marks_the_ending_as_deliberate():
    src = inspect.getsource(MeasureManager.note_app_quitting)
    assert "self._user_quit = True" in src, (
        "quitting is still reported to the session as an unexplained failure")


def test_quitting_silences_the_branch_that_warned():
    """`_user_quit` is the flag the #159 branch tests, so setting it is the
    whole fix — and it is the same flag the fallback-relaunch guards use, which
    is why an orphan stock chartread can no longer be started during shutdown."""
    # THE `if` ITSELF, not a character window before the log line. A fixed
    # window is measuring the source's shape; this one fell 100 characters
    # short of the guard it was checking for.
    # The GUARD's own text, not the first mention of the name — the first
    # occurrence is the attribute's declaration in __init__, which is how the
    # previous attempt ended up asserting against a hundred lines of comments.
    src = inspect.getsource(MeasureManager)
    i = src.index("was_engine and self._stock_reader_cannot_read")
    guard = src[src.rindex("if", 0, i):src.index(":", i)]
    assert "_user_quit" in guard, (
        f"the warning no longer depends on _user_quit, so marking the quit "
        f"would not silence it: {' '.join(guard.split())}")


def test_the_window_says_so_before_it_kills_anything():
    """After `cleanup()` is too late: the handler has already run."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.closeEvent)
    assert "note_app_quitting" in src, (
        "the session is never told the app is closing")
    assert src.index("note_app_quitting") < src.index("_runner.cleanup()"), (
        "the session is told after the helper is killed, which is after its "
        "finish handler has already run")


def test_the_callbacks_are_NOT_dropped_at_cleanup():
    """The regression this file exists to prevent. Dropping them silences the
    empty-.ti3 reconciliation along with the false warning."""
    src = inspect.getsource(ArgyllRunner.cleanup)
    assert "self._run_on_finish = None" not in src, (
        "cleanup drops the per-run callbacks again, so quitting no longer "
        "reconciles an empty .ti3 (§3b / M-TI3-EMPTY)")


def test_cleanup_still_kills_what_it_must():
    src = inspect.getsource(ArgyllRunner.cleanup)
    assert ".kill()" in src and "waitForFinished" in src
