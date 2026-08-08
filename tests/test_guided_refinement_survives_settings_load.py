"""Guided refinement's ticks must survive the per-run settings load.

Basti, 2026-08-08: *"i wanted to be guided through refinement (directed there
from check refine tab). the options were selected in measure tab as you see in
my screenshot. but after confirming the message they were deselected again"* —
and, on being asked which: *"the refine resume option plus the refinement strips
one. probably in both guided and manual module of the measure tab"*.

Both are set by `start_guided_refinement`, and both are undone by
`load_target_settings`:

* `workflow/measure_settings` maps ``"resume"`` to ``_m_resume_cb`` — the
  MANUAL twin — and `_LINKED_PAIRS` links it to the guided `_resume_cb`, so
  restoring one clears both;
* a run with nothing stored takes the `_restore_defaults()` branch, which puts
  the same two back to their defaults.

Which of them wins is a matter of ordering, and that is why it looked as though
the pop-up did it: `QMessageBox.exec()` runs a nested event loop, so a load can
finish while the window is still on screen.

The tick is an instruction from Check & Refine, not a stored preference, so it
outranks the run's saved value until the user leaves that chart. These tests
assert exactly that, at the seam — they drive `load_target_settings`'s own
re-assert hook rather than a whole MainWindow, which segfaults offscreen.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QCheckBox                      # noqa: E402

from ui.tabs.tab_measure import TabMeasure                 # noqa: E402


class _Stub:
    """Only the parts the arming/re-asserting touches."""
    _reassert_guided_refinement = TabMeasure._reassert_guided_refinement

    def __init__(self, chart_id="chart-1", strips="refine.txt"):
        self._id = chart_id
        self._refine_strips_path = strips
        self._refinement_armed_for = None
        self._resume_cb = QCheckBox()
        self._m_resume_cb = QCheckBox()
        self._refine_cb = QCheckBox()
        self._m_refine_cb = QCheckBox()

    def _chart_identity(self):
        return self._id

    def arm(self):
        """What start_guided_refinement does to the four controls."""
        for cb in (self._resume_cb, self._m_resume_cb):
            cb.setChecked(True)
        for cb in (self._refine_cb, self._m_refine_cb):
            cb.setEnabled(True)
            cb.setChecked(True)
        self._refinement_armed_for = self._chart_identity()

    def wipe(self):
        """What a settings load does: put the stored/default values back."""
        for cb in (self._resume_cb, self._m_resume_cb,
                   self._refine_cb, self._m_refine_cb):
            cb.setChecked(False)

    def ticks(self):
        return (self._resume_cb.isChecked(), self._m_resume_cb.isChecked(),
                self._refine_cb.isChecked(), self._m_refine_cb.isChecked())


def test_a_settings_load_cannot_untick_an_armed_refinement(qapp):
    """The reported fault, in both modules."""
    s = _Stub()
    s.arm()
    s.wipe()                       # load_target_settings restoring stored values
    assert s.ticks() == (False, False, False, False), "premise: the load clears them"
    s._reassert_guided_refinement()
    assert s.ticks() == (True, True, True, True), (
        "the refinement instruction from Check & Refine was lost to the run's "
        "stored Measure settings — in guided and/or manual"
    )


def test_it_disarms_when_the_chart_changes(qapp):
    """Leaving the chart must NOT keep forcing the ticks on the next one."""
    s = _Stub()
    s.arm()
    s._id = "chart-2"              # a different chart is now loaded
    s.wipe()
    s._reassert_guided_refinement()
    assert s.ticks() == (False, False, False, False), (
        "the ticks were forced back on for a chart the refinement was not for"
    )
    assert s._refinement_armed_for is None, "it should have disarmed itself"


def test_nothing_happens_when_no_refinement_was_started(qapp):
    """The ordinary case must be untouched — this is not a way to force ticks on."""
    s = _Stub()
    s.wipe()
    s._reassert_guided_refinement()
    assert s.ticks() == (False, False, False, False)


def test_the_strips_tick_needs_a_strips_file(qapp):
    """Without a strips file there is nothing to re-measure from, so don't tick it."""
    s = _Stub(strips=None)
    s.arm()
    s.wipe()
    s._reassert_guided_refinement()
    resume_g, resume_m, refine_g, refine_m = s.ticks()
    assert (resume_g, resume_m) == (True, True)
    assert (refine_g, refine_m) == (False, False)


def test_both_load_paths_reassert():
    """Structural: a run with stored settings AND one with none both wipe them.

    `load_target_settings` has two exits that put values on screen — applying
    stored settings, and `_restore_defaults()` when the run has none. A fix on
    only one of them would leave the fault for exactly the runs that have never
    been measured, which is the likely case when refining for the first time.
    """
    import inspect

    src = inspect.getsource(TabMeasure.load_target_settings)
    assert src.count("_reassert_guided_refinement()") >= 2, (
        "only one of load_target_settings' two exits re-asserts the refinement "
        "ticks; the other still silently unticks them"
    )
