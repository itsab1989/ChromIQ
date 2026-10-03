"""A binding belongs to its target, and only a real change of target drops it.

Knut, #182 5964478612 (2026-10-03): *"The settings from profiling run type
leak into calibration run type"*, and back: the "Edit patch recipe" tick made
in Calibration was still on for run1, whose chart was never overridden.
`_on_target_changed` never cleared a preset or patch-set binding, and showing
a run re-attached its own; nothing took the previous one away.

What holds now (per_target_settings §2.2, "the chart wins on a run change";
calibration_run_type §4.2):

* entering or leaving Calibration drops every binding and unticks both
  override boxes, so Calibration shows no lock and an editable targen panel;
* back on run1 its own patch set is bound again, locked and unticked;
* run1 (a loaded set) -> run2 (a targen chart): run2 is NOT bound to run1's set.
"""
from __future__ import annotations

import pytest

from core.measurement_target import RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING
from tests._cal_target_fixture import (bound, make_window, override_row_shown,
                                       show_run, targen_panel_enabled,
                                       write_run_chart)


@pytest.fixture
def win(qapp, tmp_path):
    w = make_window(qapp, tmp_path)
    proj = w._file_mgr.project()
    run1 = proj.current_run()
    files = write_run_chart(run1, given=True)
    show_run(w, qapp, run1.id)
    yield w, proj, run1, files
    w.close()


def test_calibration_shows_no_lock(win, qapp):
    w, _proj, _run1, files = win
    tc = w._tab_chart
    assert tc._preset_ti1_path == files["ti1"]
    assert override_row_shown(tc)
    w._target_ctl.set_run_type(RUN_TYPE_CALIBRATION)
    qapp.processEvents()
    assert not bound(tc), "run1's patch set followed the bar into Calibration"
    assert not override_row_shown(tc)
    assert targen_panel_enabled(tc), "the targen panel is greyed in Calibration"


def test_back_on_run1_it_is_bound_locked_and_unticked(win, qapp):
    w, _proj, _run1, files = win
    tc = w._tab_chart
    ctl = w._target_ctl
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    qapp.processEvents()
    # The tick Knut made in Calibration (state C of the diagnosis drive).
    tc._override_targen_check.setChecked(True)
    ctl.set_run_type(RUN_TYPE_PROFILING)
    qapp.processEvents()
    assert tc._preset_ti1_path == files["ti1"], "run1 came back unbound"
    assert override_row_shown(tc)
    assert not tc._override_targen_check.isChecked(), (
        "the tick made in Calibration is still on for run1")
    assert not targen_panel_enabled(tc), "run1's patch set is not locked"


def test_a_run_whose_chart_came_from_targen_is_not_bound_to_the_last_one(
        win, qapp):
    w, proj, _run1, _files = win
    tc = w._tab_chart
    run2 = proj.new_run()
    write_run_chart(run2, given=False, rows=6)
    w._target_ctl.changed.emit()
    show_run(w, qapp, run2.id)
    assert tc._shown_chart_ti2 == run2.chart_ti2, "run2's chart is not shown"
    assert not bound(tc), (
        "run2's chart was made by targen, and Generate there would have laid "
        "out run1's patches")
    assert not override_row_shown(tc)


def test_a_verification_does_not_inherit_the_binding(win, qapp):
    """A5 of the challenge: the same leak into Run type Verification."""
    from core.measurement_target import RUN_TYPE_VERIFICATION

    w, _proj, _run1, _files = win
    tc = w._tab_chart
    w._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    qapp.processEvents()
    assert not bound(tc)


def test_dropping_puts_the_preset_box_back_to_neutral(win, qapp):
    """The box is global (§1.1), but naming a preset whose binding is gone
    says something untrue."""
    w, _proj, _run1, _files = win
    tc = w._tab_chart
    combo = tc._preset_combo
    combo.blockSignals(True)
    combo.setCurrentIndex(min(1, combo.count() - 1))
    combo.blockSignals(False)
    w._target_ctl.set_run_type(RUN_TYPE_CALIBRATION)
    qapp.processEvents()
    assert combo.currentIndex() == 0
