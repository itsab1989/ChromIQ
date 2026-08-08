"""The patch set editor opens the chart of the SELECTED target, not the run's.

Knut, relayed 2026-08-08: *"I also realized many features may need checking,
like if the patch set editor applies new patches to calibration run."* He was
right. ``MainWindow._current_chart_ti2`` — which pre-loads Tools ▸ "Chart patch
set editor" — asked the project for ``current_run().chart_ti2`` whatever the bar
was pointing at. Driven on screen against the Argyll-built Demo-Full-RGB, with
Run type = Calibration, the editor opened **400 patches** named
``Demo-Full-RGB`` while the calibration chart beside it was 64 patches of
``Demo-Full-RGB-cal``.

Why that is worse than cosmetic: a calibration build writes to ``cal/``
(``TabChart._confirm_replacing_calibration`` — *"A CALIBRATION BUILD TOUCHES
cal/, NOT THE RUN"*), so editing from that wrong patch set and applying it lays
the profile run's colours over the calibration chart. It is the same shape as
the beta.165 fault: two run types assumed where there are three.

These tests drive the real resolution through a real ``TabChart`` and a real
``FileManager``, with a duck-typed host object, because a ``MainWindow`` built
under ``QT_QPA_PLATFORM=offscreen`` segfaults.
"""
from __future__ import annotations

import inspect

import pytest

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.measurement_target import (
    RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION,
)
from ui.main_window import MainWindow
from ui.measurement_target_bar import MeasurementTargetController
from ui.tabs.tab_chart import TabChart


class _Host:
    """Just enough of MainWindow for ``_current_chart_ti2`` to run."""

    def __init__(self, fm, tab):
        self._file_mgr = fm
        self._tab_chart = tab


def _touch(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def three_charts(cal_settings, qapp):
    """A project holding all three kinds of chart, each a different size.

    The patch counts are only in the file names/contents here — the resolver
    checks existence, not contents — but they are kept distinct so a failure
    message names which chart was picked.
    """
    fm = FileManager(cal_settings)
    fm.set_target_name("Test-Printer")
    proj = fm.project()

    run = proj.current_run()
    _touch(run.chart_ti2, "profiling")
    _touch(run.chart_ti1, "profiling")
    _touch(run.dir / f"{run.stem}.tif")

    _touch(run.verify_chart_ti2, "verification")
    _touch(run.verify_chart_ti1, "verification")
    _touch(run.verifications_dir / f"{run.verify_chart_ti2.stem}.tif")

    cal = proj.calibration
    _touch(cal.ti2, "calibration")
    _touch(cal.ti1, "calibration")
    _touch(cal.dir / f"{cal.stem}.tif")

    tab = TabChart(ArgyllRunner(cal_settings), fm, cal_settings)
    ctl = MeasurementTargetController(fm)
    ctl.set_calibration_allowed(True)
    tab.set_target_controller(ctl)
    tab.set_calibration_mode(True)
    return _Host(fm, tab), ctl, proj, run


# ---- the fault Knut asked about ------------------------------------------
def test_calibration_selected_opens_the_calibration_chart(three_charts):
    host, ctl, proj, _run = three_charts
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    got = MainWindow._current_chart_ti2(host)
    assert got == proj.calibration.ti2, (
        "the patch set editor would open "
        f"{got.name if got else None!r} for a calibration run; editing and "
        "applying that writes the wrong patch set over cal/")


def test_calibration_chart_is_not_the_runs_chart(three_charts):
    """Guards the exact confusion: the two must not be the same file."""
    host, ctl, proj, run = three_charts
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert MainWindow._current_chart_ti2(host) != run.chart_ti2


# ---- the other two targets must keep working -----------------------------
def test_profiling_selected_opens_the_runs_chart(three_charts):
    host, ctl, _proj, run = three_charts
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run(run.id)
    assert MainWindow._current_chart_ti2(host) == run.chart_ti2


def test_verification_selected_opens_the_verification_chart(three_charts):
    host, ctl, _proj, run = three_charts
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run(run.id)
    assert MainWindow._current_chart_ti2(host) == run.verify_chart_ti2


def test_no_chart_yet_opens_the_editor_empty(cal_settings, qapp):
    """A project with no generated chart must still return None, so the editor
    opens empty rather than being handed a path that isn't there."""
    fm = FileManager(cal_settings)
    fm.set_target_name("Empty-Printer")
    fm.project()
    tab = TabChart(ArgyllRunner(cal_settings), fm, cal_settings)
    ctl = MeasurementTargetController(fm)
    ctl.set_calibration_allowed(True)
    tab.set_target_controller(ctl)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert MainWindow._current_chart_ti2(_Host(fm, tab)) is None


# ---- and it must stay a single definition -------------------------------
def test_it_delegates_instead_of_branching_again(three_charts):
    """The fault was a *second* definition of "the current chart".

    Re-adding one would pass every test above on the day it was written and
    then drift, which is exactly what happened here and in beta.165. So pin the
    delegation: this method resolves through the tab's resolver and does not
    reach for a run's chart itself.
    """
    src = inspect.getsource(MainWindow._current_chart_ti2)
    assert "_resolve_target_chart" in src, \
        "_current_chart_ti2 must delegate to TabChart._resolve_target_chart"
    for stem_pattern in ("chart_ti2", "current_run()"):
        assert stem_pattern not in src.split('"""')[-1], (
            f"_current_chart_ti2 builds its own path again ({stem_pattern!r}) "
            "instead of asking the one resolver that knows all three run types")
