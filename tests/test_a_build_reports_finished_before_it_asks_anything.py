"""The chart build says it has finished BEFORE it opens a modal.

Knut's log of 2026-09-10 carries one line nobody had explained:

    Chart-build lock released by watchdog, no chart_finished arrived after the
    last tool ended

The Argyll run before it reported code 0 and the preview loaded, so the work was
done and only the signal was late. An on-screen reproduction found the cause and
proved it with a four-way control: hold the partial-last-page dialog open for
3 s and the watchdog fires at +1577 ms; answer it in 155 ms, or suppress it with
auto-preview, or build a chart that fills its last page, and it never does.

`_maybe_warn_partial_last_page` ends in a blocking `QMessageBox.exec()`, and it
was called BEFORE `chart_finished.emit`. `exec()` runs a nested event loop, which
is what lets the main window's watchdog `QTimer` fire; its grace is 1500 ms and
the dialog waits for a person.

**Nothing was lost and no sheet was wrong.** What it cost is that the masthead
lock dropped early, so Close Project, the run picker and Restore Used Chart came
back live while the build was still finishing, which is the "build in flight
against the run's stored state" the lock exists to prevent.

This file pins the ORDER, by source, because the fault is not in what either
call does. Both are correct on their own; only their sequence was wrong, and a
behavioural test cannot see a sequence that produces the same end state.
"""
from __future__ import annotations

import inspect
import re


def _finish_body() -> str:
    """The success branch of the chart-finished handler, as source."""
    from ui.tabs.tab_chart import TabChart

    for name in dir(TabChart):
        fn = getattr(TabChart, name, None)
        if not callable(fn):
            continue
        try:
            src = inspect.getsource(fn)
        except (OSError, TypeError):
            continue
        if ("chart_finished.emit(tiffs, ti2, is_isis)" in src
                and "_maybe_warn_partial_last_page" in src):
            return src
    raise AssertionError(
        "no method carries both the completion signal and the partial-page "
        "warning; this test has lost its subject")


def test_the_completion_signal_goes_before_the_partial_page_dialog():
    """MUTATION: move `_maybe_warn_partial_last_page(ti2)` back above the emit
    and this goes red. Watched."""
    src = _finish_body()
    emit = src.index("chart_finished.emit(tiffs, ti2, is_isis)")
    warn = src.index("self._maybe_warn_partial_last_page(ti2)")
    assert emit < warn, (
        "the build opens a modal before it reports that it has finished, so "
        "the main window's watchdog fires inside that dialog's event loop and "
        "releases the chart-build lock while the build is still running")


def test_the_partial_page_warning_really_is_modal():
    """The premise. If it stops blocking, the ordering above stops mattering
    and this file should be revisited rather than left as decoration."""
    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._maybe_warn_partial_last_page)
    assert re.search(r"\.exec\(\)", src), (
        "the partial-page warning no longer blocks; the ordering this file "
        "pins was only needed because it does")


def test_the_watchdog_grace_is_shorter_than_a_person():
    """And the other half of the premise, in the window that owns the lock.

    The grace is what makes a human-length pause long enough to fire it. If it
    ever grew past the time a dialog is on screen, the log line would stop
    appearing and the underlying ordering fault would go quiet rather than
    away.
    """
    from ui.main_window import MainWindow

    grace = getattr(MainWindow, "_CHART_LOCK_GRACE_MS", None)
    if grace is None:
        import ui.main_window as mw
        grace = getattr(mw, "_CHART_LOCK_GRACE_MS", None)
    assert grace is not None, "the watchdog grace is gone; check the premise"
    assert grace < 5000, (
        f"the grace is {grace} ms, long enough that a dialog no longer trips "
        "it; this file's reasoning needs re-checking")
