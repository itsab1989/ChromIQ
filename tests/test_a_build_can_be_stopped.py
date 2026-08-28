"""F8: there was no way to stop a chart build, on either tab that runs one.

Measured on screen, 2026-08-28, with a real chart job in flight: 57 enabled and
visible buttons on Create Chart, and *"ANYTHING THAT COULD STOP IT: NOTHING"*.
Measure has START beside STOP; Create Chart and Build Profile run ArgyllCMS jobs
that take from seconds to many minutes and offered no counterpart, so the only
way out was to quit the app — which is exactly the path that used to destroy the
chart being replaced.

THE MECHANISM ALREADY EXISTED. `ChartCreator.cancel()` is reachable today, but
only from the slow-chart window that appears by itself after a wait, so it could
be waited for and not asked for. This is wiring, not a new feature.

ORDER MATTERS, and this ships second on purpose: a Stop button added BEFORE the
build learned to set the old chart aside would have turned "you must quit the
app to escape" into "one click", with the same destruction behind it.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager                       # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def test_there_is_a_stop_button_and_it_hides_when_nothing_runs(tab):
    assert tab._stop_btn is not None
    assert tab._stop_btn.isVisible() is False, \
        "Stop is showing while nothing is being built"


def test_stop_appears_exactly_while_a_build_is_in_flight(tab):
    """It follows `_chart_build_in_flight()`, which reads the Generate button —
    the marker every build path already maintains, failures included. Ten sites
    disable that button; none of them needed touching."""
    tab.show()
    assert tab._chart_build_in_flight() is False
    tab._generate_btn.setEnabled(False)          # what every build path does
    qapp = QApplication.instance()
    qapp.processEvents()
    assert tab._chart_build_in_flight() is True
    assert tab._stop_btn.isVisible() is True, \
        "a build started and no Stop appeared"
    tab._generate_btn.setEnabled(True)           # …and what every exit does
    qapp.processEvents()
    assert tab._stop_btn.isVisible() is False, \
        "Stop stayed on screen after the build ended"


def test_stop_asks_the_creator_to_cancel(tab, monkeypatch):
    called = []
    monkeypatch.setattr(tab._creator, "cancel", lambda: called.append(1))
    tab._on_stop_clicked()
    assert called == [1]
    assert tab._cancelled_by_user is True


def test_a_stop_during_printtarg_is_not_reported_as_a_failure():
    """printtarg is the phase that writes the pages, so it is the likeliest one
    to be stopped — and `_cancelling` was only ever checked in `_targen_done`,
    so the person was shown "Chart Generation Failed (printtarg)" for something
    they had just asked for."""
    from workflow.chart_creator import ChartCreator
    src = inspect.getsource(ChartCreator._printtarg_done)
    assert "_cancelling" in src, \
        "a deliberate Stop during printtarg still reads as a build failure"
    assert src.index("_cancelling") < src.index("printtarg failed with code"), \
        "the cancel branch must come before the error branch"


def test_the_tooltip_admits_what_stop_cannot_interrupt(tab):
    """ChromIQ's own layout engine runs in one go on the GUI thread, so a stop
    pressed during it takes effect when that phase ends. Saying so is better
    than a button that looks ignored."""
    tip = tab._stop_btn.toolTip()
    assert "layout engine" in tip
    assert "nothing is lost" in tip


def test_stop_is_safe_because_the_chart_is_set_aside_first(tab):
    """The reason this could ship at all. Without the stash, a Stop would leave
    the run with no chart — it would be a faster route to the data loss, not a
    fix for it."""
    from core.file_manager import Run
    assert hasattr(Run, "settle_chart_stash")
    src = inspect.getsource(Run.reset_chart_artefacts)
    assert "stash" in src


# ---------------------------------------------------------------------------
# Found on screen: Stop during the layout engine did nothing, and said otherwise
# ---------------------------------------------------------------------------

def test_stop_works_when_no_subprocess_is_running(tab):
    """`cancel()` used to return early unless an ArgyllCMS process was running.

    The ChromIQ layout engine is an in-process call on the GUI thread — there is
    no subprocess to kill — so Stop pressed during it did nothing at all, while
    the log said "the chart that was here before is being put back, so nothing
    is lost" and the chart was replaced anyway. Measured on screen:
    `runner_is_running: false, stop_visible: true`, chart replaced.
    """
    creator = tab._creator
    assert creator._runner.is_running is False, \
        "this test needs the idle case, which is what the engine phase looks like"
    creator._cancelling = False
    creator.cancel()
    assert creator._cancelling is True, \
        "Stop did nothing because no subprocess happened to be running"


def test_a_cancelled_build_puts_the_chart_back_even_if_it_produced_pages(tab,
                                                                         tmp_path):
    """The engine cannot be interrupted mid-page, so it returns a
    complete-looking result even when Stop was pressed. Taken at face value that
    reads as a finished build, and the chart the person was promised back would
    be dropped instead."""
    from core.file_manager import Project

    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    (run.dir / f"{run.stem}.ti2").write_text("the chart that was here")
    (run.dir / f"{run.stem}_01.tif").write_text("its page")
    before = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}

    creator = tab._creator
    creator._chart_stash_run = run
    creator._chart_stash = run.reset_chart_artefacts(stash=True)
    (run.dir / f"{run.stem}.ti2").write_text("what the engine got to")
    (run.dir / f"{run.stem}_01.tif").write_text("a page from the stopped build")
    creator._cancelling = True
    creator._pending_on_finish = lambda tiffs: None

    creator._finish([run.dir / f"{run.stem}_01.tif"])   # a NON-empty result

    after = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}
    assert after == before, (
        "a stopped build was treated as a finished one, so the chart it "
        "replaced was dropped")
