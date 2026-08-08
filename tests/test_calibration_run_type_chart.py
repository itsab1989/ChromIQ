"""#137 Table B / D7 / R1 — what Run type = Calibration does to Create Chart.

Sebastian, 2026-08-05: *"setting run type to calibration turns the auto settings
off … total patch count, white, black patches, grey axis steps. Single channel
steps should be set to 20 … and then also be reset to how it was before when the
user sets another runtype again."*
"""
from __future__ import annotations

import inspect

import pytest

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.measurement_target import RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING
from ui.measurement_target_bar import MeasurementTargetController
from ui.tabs.tab_chart import TabChart


@pytest.fixture
def chart(cal_settings, qapp):
    fm = FileManager(cal_settings)
    fm.set_target_name("Test-Printer")
    fm.project()
    tab = TabChart(ArgyllRunner(cal_settings), fm, cal_settings)
    ctl = MeasurementTargetController(fm)
    ctl.set_calibration_allowed(True)
    tab.set_target_controller(ctl)
    tab.set_calibration_mode(True)
    return tab, ctl


def _pw(tab, flag, tool="targen"):
    for w in tab._manual_widgets.get(tool, []):
        if w.flag == flag:
            return w
    raise AssertionError(f"no {tool} {flag} widget")


def _autos(tab):
    return {n: (getattr(tab, n).isChecked(), getattr(tab, n).isEnabled())
            for n in tab._CAL_AUTO_CHECKS}


# ---- Table B: switching TO Calibration ----------------------------------
def test_every_auto_box_goes_off_and_grey(chart):
    tab, ctl = chart
    for name in tab._CAL_AUTO_CHECKS:
        getattr(tab, name).setChecked(True)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    for name, (checked, enabled) in _autos(tab).items():
        assert checked is False, f"{name} still ticked"
        assert enabled is False, f"{name} still clickable"


@pytest.mark.parametrize("flag,expected", [
    ("-f", 0), ("-e", 0), ("-B", 0), ("-s", 20)])
def test_the_ramp_is_what_gets_built(chart, flag, expected):
    tab, ctl = chart
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert _pw(tab, flag).get_raw_value() == expected


def test_pages_goes_quiet(chart):
    """It only means anything while Auto patch count decides the total."""
    tab, ctl = chart
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert not tab._manual_pages_spin.isEnabled()


def test_the_greyed_boxes_explain_themselves(chart):
    tab, ctl = chart
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    for name in tab._CAL_AUTO_CHECKS:
        tip = getattr(tab, name).toolTip()
        assert "Single Channel Steps" in tip, name
        assert "come back exactly as you left them" in tip, name


# ---- Table B: switching AWAY --------------------------------------------
def test_a_hand_set_value_comes_back(chart):
    """Not the calibration's 20 — the number the user chose."""
    tab, ctl = chart
    _pw(tab, "-s").set_value(37)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert _pw(tab, "-s").get_raw_value() == 20
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert _pw(tab, "-s").get_raw_value() == 37


def test_the_tick_states_come_back_too(chart):
    tab, ctl = chart
    tab._manual_auto_patches_check.setChecked(True)
    tab._manual_auto_grey_check.setChecked(False)
    before = _autos(tab)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert _autos(tab) == before


def test_pages_follows_auto_patch_count_again(chart):
    tab, ctl = chart
    tab._manual_auto_patches_check.setChecked(True)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert tab._manual_pages_spin.isEnabled()


# ---- R1: entering twice must not overwrite the originals ----------------
def test_entering_calibration_twice_keeps_the_snapshot(chart):
    tab, ctl = chart
    _pw(tab, "-s").set_value(41)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    tab._apply_calibration_knobs(True)           # a second entry
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert _pw(tab, "-s").get_raw_value() == 41, "the user's value was overwritten"


# ---- D7 / T7: the Generate-time guard ------------------------------------
def test_the_auto_estimate_is_skipped_for_a_calibration_build():
    """The UI state is what the user sees; this guard is what keeps the built
    command right if any path ever reaches Generate with Auto still on. Without
    it the command preview prints -f0 while the build uses the page-filling
    estimate — which is how D7 stayed invisible."""
    src = inspect.getsource(TabChart._on_generate)
    # Anchored on the condition, not on proximity: the guard has to be part of
    # the same `if` that gates the estimate, wherever the body grows to.
    start = src.index('if (self._current_mode() == "manual"')
    condition = src[start:src.index(":", src.index("isChecked()", start))]
    assert "not cal_target_active" in condition, (
        "the auto patch estimate is not gated on cal_target:\n" + condition)
    assert "estimate_patches(" in src[start:], "the estimate moved out of the guard"


def test_the_run_type_decides_where_the_build_goes():
    """Where the build lands comes from the bar, not from a checkbox.

    The call is duck-typed — ``getattr(target, "is_calibration", bool)()`` — so
    a host or a test double that predates this run type answers "no" instead of
    raising, which is how the older doubles in this suite keep working.
    """
    src = inspect.getsource(TabChart._on_generate)
    assert 'is_calibration"' in src and "cal_target_active" in src


# ---- E17: calibration is manual-only ------------------------------------
def test_calibration_mode_forces_manual(chart):
    tab, ctl = chart
    assert tab._current_mode() == "manual"


# ---- the retired checkbox ------------------------------------------------
def test_the_checkbox_is_retired(chart):
    """Two controls for one state is the confusion this feature removes."""
    tab, ctl = chart
    assert not tab._cal_target_grp.isVisible()
    assert not tab._cal_target_check.isChecked()


# ---- Knut 2026-08-08: a calibration is not a starting point for a run -----
def test_a_calibration_never_seeds_the_new_run_block(cal_settings, qapp,
                                                     tmp_path):
    """Knut: New-run seeding *"should only work for profiling and verification
    runs"*.

    Stripping the six ``_CALIBRATION_OWNED`` rows was not enough on its own —
    driven on screen, selecting Run type = Calibration still wrote a
    ``cal/cache/new_run.json`` carrying 34 other rows (paper, instrument,
    margins, the whole layout recipe) that a later New run would start from.
    """
    from core.file_manager import FileManager
    from workflow.per_target_settings import NEW_RUN_FILENAME

    fm = FileManager(cal_settings)
    fm.set_target_name("Seed-Printer")
    proj = fm.project()
    tab = TabChart(ArgyllRunner(cal_settings), fm, cal_settings)
    ctl = MeasurementTargetController(fm)
    ctl.set_calibration_allowed(True)
    tab.set_target_controller(ctl)
    tab.set_calibration_mode(True)

    cal = proj.calibration
    cal.dir.mkdir(parents=True, exist_ok=True)
    tab._seed_new_run_block(cal, {"printtarg-p": {"enabled": True,
                                                  "value": "A3"}})
    assert not (cal.dir / "cache" / NEW_RUN_FILENAME).exists(), \
        "a calibration seeded the New-run block"

    # …and a real run still does, or the feature is gone rather than guarded.
    run = proj.current_run()
    run.dir.mkdir(parents=True, exist_ok=True)
    tab._seed_new_run_block(run, {"printtarg-p": {"enabled": True,
                                                  "value": "A4"}})
    assert (run.dir / "cache" / NEW_RUN_FILENAME).exists(), \
        "a profiling run stopped seeding the New-run block"


def test_the_guard_reads_the_store_not_the_selection(cal_settings, qapp):
    """The seeding runs for the OUTGOING target while the bar already points at
    the incoming one, so asking the controller answers about the wrong target —
    which is how the first attempt at this guard passed its own unit test and
    still wrote the file on screen."""
    src = inspect.getsource(TabChart._seed_new_run_block)
    # Comments and the docstring both discuss `_target_ctl` on purpose — they
    # explain why it must NOT be used here — so strip them before looking, or
    # the test fails on its own explanation.
    body = src.split('"""')[-1]
    code = "\n".join(line.split("#", 1)[0] for line in body.splitlines())
    assert "isinstance(store, Calibration)" in code, \
        "the guard must come from the store, not from _target_ctl.target"
    assert "_target_ctl" not in code, \
        "asking the selection here answers about the incoming target"
