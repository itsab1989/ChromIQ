"""A chart build must lock the masthead the way a measurement and a profile do.

Only chartread and colprof had their own flags, so during targen/printtarg the
user could switch project, open another chart or open Tools mid-build — the
"build in flight vs the run's stored Create Chart state" shape that has been
clobbered twice — and Close Project LOOKED available while doing nothing (its
own guard returned silently, with no dialog and no log line).

Basti's #164 Q7 ("should be locked the same way") was satisfied for colprof and
not for targen.
"""
from unittest.mock import patch

import pytest


@pytest.fixture
def win(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    w = MainWindow(s)
    qapp.processEvents()
    w._file_mgr.set_target_name("Chart Lock")
    qapp.processEvents()
    yield w
    w.close()


def _states(win):
    m = win._masthead
    return {
        "open": m._load_project_btn.isEnabled(),
        "chart": m._load_ti2_btn.isEnabled(),
        "tools": m._tools_btn.isEnabled(),
        "prefs": m._btn.isEnabled(),
        "close": m._close_project_btn.isEnabled(),
    }


def _running():
    from core.argyll_runner import ArgyllRunner

    return patch.object(ArgyllRunner, "is_running", property(lambda self: True))


def test_a_chart_build_greys_the_masthead(win):
    """Driven through the REAL signal path.

    The first version of this test called `_on_chart_build_started()` from
    inside `patch.object(ArgyllRunner, "is_running", ...)` — it manufactured an
    ordering the app never produces, and so passed while the feature did not
    work at all. `target_started` fires BEFORE the process exists, so
    `is_running` is False there and the lock never engaged; sampled every 80 ms
    through a real targen build, the buttons stayed live the whole time.
    `ArgyllRunner.started` is the edge that actually engages it.
    """
    assert all(_states(win).values()), "should start live"

    win._on_chart_build_started()          # what target_started does
    assert all(_states(win).values()), (
        "the lock engaged before any process existed")

    win._runner.started.emit()             # what a real tool start does
    assert not any(_states(win).values()), (
        f"a running chart build left the masthead live: {_states(win)}")
    assert "chart" in win._masthead._load_project_btn.toolTip().lower()


def test_it_comes_back_when_the_chart_is_done(win):
    win._on_chart_build_started()
    win._runner.started.emit()
    assert not any(_states(win).values())
    win._on_chart_build_finished()
    assert all(_states(win).values()), "the masthead did not come back"


def test_an_unrelated_tool_does_not_lock_the_masthead(win):
    """Scoped deliberately: a background gamut or profcheck run is not a chart
    build and must not grey the window."""
    win._runner.started.emit()             # a tool starts, no chart build
    assert all(_states(win).values()), (
        "an unrelated Argyll tool greyed the masthead")


def test_target_started_without_a_process_never_wedges_the_lock(win):
    """Some Create Chart paths emit `target_started` and then return without
    starting anything. Those must not leave the window greyed for good."""
    win._on_chart_build_started()
    assert all(_states(win).values()), (
        "a chart build that never started anything greyed the masthead")


def test_the_lock_cannot_stick_on(win):
    """The latch is released by `runner.finished`, which now fires for EVERY
    ending — including a tool that could not start at all (the `errorOccurred`
    fix). So a build cannot leave the window greyed for good.

    Proven by driving the runner's own signal rather than the tab's: even if
    `chart_finished` never arrives, the runner's does.
    """
    win._on_chart_build_started()
    win._runner.started.emit()
    assert not any(_states(win).values()), "should be locked"

    # The tool ended badly. The lock is NOT dropped here — a Manual build runs
    # two tools and the second is still to come — so `chart_finished` (or the
    # watchdog beneath it) is what releases.
    win._runner.finished.emit(-1)
    win._on_chart_build_finished()
    assert all(_states(win).values()), (
        "a chart build that ended badly locked the app for good")


def test_a_tool_that_never_starts_leaves_nothing_latched(win):
    """`target_started` with no process must not latch anything, so a later
    unrelated tool cannot inherit the lock."""
    win._on_chart_build_started()
    assert all(_states(win).values())
    win._on_chart_build_finished()
    win._runner.started.emit()             # some other tool, later
    assert all(_states(win).values()), (
        "an unrelated tool inherited a stale chart-build flag")


def test_close_project_is_never_a_live_dead_click(win):
    """It used to look available during a chart build and return silently."""
    win._on_chart_build_started()
    win._runner.started.emit()
    assert win._masthead._close_project_btn.isEnabled() is False, (
        "Close Project looks clickable but its guard returns silently")


def test_the_lock_spans_a_TWO_TOOL_build(win):
    """A Manual chart is targen THEN printtarg — two ArgyllRunner runs.

    The lock used to be released by the first `finished`, so printtarg ran
    completely unlocked: measured at 50 ms through a real build, greyed for all
    19 samples of targen and 0 of the 8 samples of printtarg. printtarg is the
    phase that writes the .ti2 and the printable pages into the run folder —
    exactly what the lock is for — and Close Project was a live dead click for
    its whole duration.
    """
    win._on_chart_build_started()          # target_started
    win._runner.started.emit()             # targen starts
    assert not any(_states(win).values()), "targen did not lock"

    win._runner.finished.emit(0)           # targen ends — printtarg is next
    assert not any(_states(win).values()), (
        "the masthead was handed back between targen and printtarg — "
        "printtarg writes the .ti2 and the pages with the window unlocked")

    win._runner.started.emit()             # printtarg starts
    assert not any(_states(win).values()), "printtarg did not keep the lock"
    win._runner.finished.emit(0)

    win._on_chart_build_finished()         # chart_finished ends the build
    assert all(_states(win).values()), "the masthead did not come back"


def test_close_project_is_dead_for_no_part_of_a_two_tool_build(win):
    """The specific user-visible symptom: a button that looks clickable and
    silently does nothing, because its own guard refuses while a tool runs."""
    win._on_chart_build_started()
    for _ in range(2):                     # targen, then printtarg
        win._runner.started.emit()
        assert win._masthead._close_project_btn.isEnabled() is False, (
            "Close Project is enabled during a chart build, and its guard "
            "returns silently — a live dead click")
        win._runner.finished.emit(0)
        assert win._masthead._close_project_btn.isEnabled() is False, (
            "Close Project came back between the two tools of one build")
    win._on_chart_build_finished()
    assert win._masthead._close_project_btn.isEnabled() is True


def test_a_build_that_never_reports_finishing_is_released_by_the_watchdog(win,
                                                                         qapp):
    """Holding until `chart_finished` would wedge if that signal never came.
    The watchdog is the floor under that."""
    from PyQt6.QtCore import QEventLoop, QTimer

    win._CHART_LOCK_GRACE_MS = 120         # keep the test quick
    win._on_chart_build_started()
    win._runner.started.emit()
    win._runner.finished.emit(0)           # …and chart_finished never arrives
    assert not any(_states(win).values()), "should still be locked initially"

    loop = QEventLoop()
    QTimer.singleShot(400, loop.quit)
    loop.exec()
    qapp.processEvents()

    assert all(_states(win).values()), (
        "a chart build that never reported finishing left the window greyed")
