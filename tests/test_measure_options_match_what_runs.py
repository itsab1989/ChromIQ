"""What the Measure options show must be what chartread is actually given.

Basti, 2026-08-08, about the window offered when a chart already has a
measurement: *"as long as the settings chosen there are correctly reflecting
what is used in the app it is fine"*.

That is one invariant with three seams, and each has already gone wrong once:

1. **The two modules.** Guided builds its command from `_resume_cb`, Manual from
   `_m_resume_cb`. Anything that sets one must set the other, or the panel you
   are looking at describes a run the other module would make.
2. **The stored settings.** `load_target_settings` writes only the MANUAL
   control (`measure_settings` maps ``"resume"`` → ``_m_resume_cb``); the guided
   twin follows through the `_LINKED_PAIRS` signal. If that ever stopped
   emitting, the two would silently diverge.
3. **The refinement arming** added in beta.197 so a settings load cannot undo
   Check & Refine's instruction. Answering this window is the user saying,
   later and explicitly, what they want — so it has to outrank the arming, or
   the next load would put resume back on over their answer.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QCheckBox                       # noqa: E402

from ui.tabs.tab_measure import TabMeasure                  # noqa: E402


def test_both_modules_read_their_own_resume_box():
    """Guided and Manual each build from their own control — so both must be set.

    Structural: building the two panels needs a whole tab, which segfaults
    offscreen. If these move, the pairing below is what has to be rechecked.
    """
    import inspect

    src = inspect.getsource(TabMeasure)
    assert "resume              = self._resume_cb.isChecked()" in src, \
        "the guided command no longer reads _resume_cb"
    assert "resume              = self._m_resume_cb.isChecked()" in src, \
        "the manual command no longer reads _m_resume_cb"


def test_the_pop_up_sets_both_boxes():
    """It must not leave one module disagreeing with the other."""
    import inspect

    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    assert "for cb in (self._resume_cb, self._m_resume_cb)" in src, (
        "the 'chart already has a measurement' window no longer ticks both "
        "modules' resume boxes, so Guided and Manual can disagree"
    )


def test_the_resume_pair_is_linked():
    """The stored setting is applied to the manual box only; the link carries it."""
    assert ("_resume_cb", "_m_resume_cb") in TabMeasure._LINKED_PAIRS, (
        "resume is no longer linked between the modules, so a settings load "
        "(which writes only the manual control) would leave guided stale"
    )


def test_applying_stored_settings_does_not_block_the_link():
    """`apply` must emit `toggled`, or the linked twin never hears about it."""
    import inspect

    from workflow import measure_settings

    src = inspect.getsource(measure_settings.apply)
    assert "blockSignals" not in src, (
        "measure_settings.apply blocks signals, so setting the manual resume box "
        "no longer propagates to the guided one and the two modules diverge"
    )


class _Stub:
    """Enough of the tab to exercise the arming/disarming rule."""
    _reassert_guided_refinement = TabMeasure._reassert_guided_refinement

    def __init__(self):
        self._refinement_armed_for = None
        self._refine_strips_path = "refine.txt"
        self._resume_cb = QCheckBox()
        self._m_resume_cb = QCheckBox()
        self._refine_cb = QCheckBox()
        self._m_refine_cb = QCheckBox()

    def _chart_identity(self):
        return "chart-1"


def test_answering_the_window_outranks_an_armed_refinement(qapp):
    """The user's later, explicit answer must win over Check & Refine's."""
    s = _Stub()
    s._refinement_armed_for = s._chart_identity()      # refinement armed it
    # the window is answered with "do not resume"
    for cb in (s._resume_cb, s._m_resume_cb):
        cb.setChecked(False)
    s._refinement_armed_for = None                     # what the window now does
    s._reassert_guided_refinement()                    # a later settings load
    assert not s._resume_cb.isChecked() and not s._m_resume_cb.isChecked(), (
        "a settings load put resume back on after the user had explicitly "
        "answered 'no' — the box would stop describing what the app runs"
    )


def test_the_window_really_disarms_it():
    """Structural: prove the disarm is in the window's own apply block."""
    import inspect

    whole = inspect.getsource(TabMeasure)
    i = whole.index("for cb in (self._resume_cb, self._m_resume_cb)")
    assert "_refinement_armed_for = None" in whole[i:i + 1200], (
        "the 'chart already has a measurement' window does not clear the "
        "refinement arming, so a later settings load overrides the answer"
    )
