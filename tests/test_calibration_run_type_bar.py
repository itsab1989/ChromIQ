"""#137 Table A / Table E — the bar, per Run type.

The rule that outranks the feature: **with Preferences → Calibration options
switched off, the app behaves exactly as it did before this existed.** Half of
this file exists to hold that line.
"""
from __future__ import annotations

import pytest

from core.file_manager import FileManager
from core.measurement_target import (RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING,
                                     RUN_TYPE_VERIFICATION, coerce_run_type)
from ui.measurement_target_bar import (MeasurementTargetBar,
                                       MeasurementTargetController)


@pytest.fixture
def bar(cal_project, qapp):
    fm, proj = cal_project
    proj.new_run()
    ctl = MeasurementTargetController(fm)
    widget = MeasurementTargetBar(ctl)
    return widget, ctl


def _types(bar):
    return [bar._type_combo.itemData(i) for i in range(bar._type_combo.count())]


def _runs(bar):
    return [bar._run_combo.itemData(i) for i in range(bar._run_combo.count())]


# ---- the preference is off: nothing changes ------------------------------
def test_calibration_is_not_offered_while_the_preference_is_off(bar):
    widget, ctl = bar
    widget.set_calibration_allowed(False)
    assert _types(widget) == [RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION]


def test_calibration_cannot_be_selected_while_the_preference_is_off(bar):
    """Not merely absent from the list — unreachable, whatever asks for it."""
    widget, ctl = bar
    widget.set_calibration_allowed(False)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert ctl.target.run_type == RUN_TYPE_PROFILING


def test_the_run_box_is_untouched_while_the_preference_is_off(bar):
    widget, ctl = bar
    widget.set_calibration_allowed(False)
    ctl.set_profile_run("run1")
    widget.refresh()
    assert widget._run_combo.isEnabled()
    assert "run1" in _runs(widget)


# ---- E21: a stored value from a newer build ------------------------------
@pytest.mark.parametrize("stored,allowed,expected", [
    ("calibration", True, RUN_TYPE_CALIBRATION),
    ("calibration", False, RUN_TYPE_PROFILING),      # downgrade / preference off
    ("verification", False, RUN_TYPE_VERIFICATION),
    ("nonsense", True, RUN_TYPE_PROFILING),
    ("", True, RUN_TYPE_PROFILING),
    (None, True, RUN_TYPE_PROFILING),
])
def test_a_stored_run_type_lands_somewhere_usable(stored, allowed, expected):
    assert coerce_run_type(stored, calibration_allowed=allowed) == expected


# ---- Table A -------------------------------------------------------------
def test_the_third_type_appears_with_the_preference(bar):
    widget, ctl = bar
    widget.set_calibration_allowed(True)
    assert _types(widget) == [RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION,
                              RUN_TYPE_CALIBRATION]


def test_the_run_box_shows_one_fixed_entry(bar):
    widget, ctl = bar
    widget.set_calibration_allowed(True)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    widget.refresh()
    assert len(_runs(widget)) == 1
    assert not widget._run_combo.isEnabled()
    assert "no run to pick" in widget._run_combo.toolTip()


def test_the_verification_box_hides(bar):
    widget, ctl = bar
    widget.set_calibration_allowed(True)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    widget.refresh()
    assert not widget._verify_combo.isVisible()


# ---- R3: the invariant that would cost the user work ---------------------
def test_the_selected_run_survives_a_trip_through_calibration(bar):
    """Switching to Calibration and back must land on the run the user had.

    profile_run is meaningless while Calibration is selected, so the temptation
    is to clear it. Clearing it sends the user back to the wrong run — silently,
    and after they have done something else in between.
    """
    widget, ctl = bar
    widget.set_calibration_allowed(True)
    ctl.set_profile_run("run2")
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    widget.refresh()
    assert ctl.target.profile_run == "run2"
    ctl.set_run_type(RUN_TYPE_PROFILING)
    widget.refresh()
    assert ctl.target.profile_run == "run2"
    assert widget._run_combo.currentData() == "run2"


def test_the_sentinel_never_reaches_profile_run(bar):
    """Belt and braces on R3: even driving the combo directly cannot write it."""
    widget, ctl = bar
    widget.set_calibration_allowed(True)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    widget.refresh()
    widget._syncing = False
    widget._on_run_changed(0)               # as if the user had picked it
    assert ctl.target.profile_run == "run1"


# ---- E2: the preference goes off while Calibration is selected -----------
def test_switching_the_preference_off_falls_back(bar):
    widget, ctl = bar
    widget.set_calibration_allowed(True)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    widget.set_calibration_allowed(False)
    assert ctl.target.run_type == RUN_TYPE_PROFILING
    assert ctl.target.profile_run == "run1"
    assert _types(widget) == [RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION]


# ---- Table E: the three buttons ------------------------------------------
def test_duplicate_and_delete_say_what_to_do_instead(bar):
    widget, ctl = bar
    widget.set_calibration_allowed(True)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    for enabled, tip in (ctl.duplicate_state(), ctl.delete_state()):
        assert enabled is False
        assert "Profiling" in tip, tip


def test_delete_explains_that_a_calibration_is_replaced_not_deleted(bar):
    widget, ctl = bar
    widget.set_calibration_allowed(True)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    _, tip = ctl.delete_state()
    assert "cal/old" in tip and "go back to it" in tip


def test_restore_is_offered_once_a_chart_has_been_stored(bar, cal_project):
    """Decision 3: Restore Used Chart is in the first version, and it is what
    makes a calibration chart recoverable at all."""
    from workflow.chart_slot import slot_for
    from workflow.verify_chart_snapshot import snapshot_slot

    widget, ctl = bar
    fm, proj = cal_project
    widget.set_calibration_allowed(True)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)

    cal = proj.calibration
    assert ctl.restore_state()[0] is False       # nothing stored yet
    assert "no stored copy" in ctl.restore_state()[1]

    cal.ensure_dir()
    cal.ti1.write_text("ti1")
    cal.ti2.write_text("ti2")
    snapshot_slot(slot_for(cal))
    assert ctl.restore_state()[0] is False       # identical to live
    assert "already identical" in ctl.restore_state()[1]

    cal.ti2.write_text("regenerated")
    enabled, tip = ctl.restore_state()
    assert enabled is True
    assert "calibration chart" in tip
