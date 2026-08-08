"""The "already has a measurement" window must not contradict the panel behind it.

Basti, 2026-08-08: he asked Check & Refine to guide him through a refinement —
which ticks "Refine / resume existing measurement" and "Use refinement strips
file" on the Measure panel — and the window then opened with **Refine / resume
unticked**. His screenshot shows the two disagreeing side by side.

That is not cosmetic. Pressing OK *applies* the window's two values:

    for cb in (self._resume_cb, self._m_resume_cb):
        cb.setChecked(want_resume)

so OK would have silently unticked the refinement he had just asked for and
turned the next read into a full replacement of his measurement. beta.199 also
made the window clear `_refinement_armed_for`, so nothing would have put the
ticks back either.

The cause was two stores with nearly the same meaning: the window seeded itself
from the app-wide `overlay_prompt_resume` (the last answer given in the window)
while the panel showed the live state. The panel is what actually runs, so the
window now starts from it and falls back to the remembered answer only when the
panel has nothing to say.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QCheckBox                      # noqa: E402

from ui.tabs.tab_measure import TabMeasure                 # noqa: E402


class _Stub:
    _resume_is_set_on_the_panel = TabMeasure._resume_is_set_on_the_panel


def test_it_reports_a_ticked_panel(qapp):
    s = _Stub()
    s._resume_cb = QCheckBox(); s._resume_cb.setChecked(True)
    s._m_resume_cb = QCheckBox(); s._m_resume_cb.setChecked(True)
    assert s._resume_is_set_on_the_panel() is True


def test_it_reports_an_unticked_panel(qapp):
    s = _Stub()
    s._resume_cb = QCheckBox()
    s._m_resume_cb = QCheckBox()
    assert s._resume_is_set_on_the_panel() is False


def test_no_controls_means_fall_back_to_the_remembered_answer():
    """None, not False — the caller must be able to tell 'unset' from 'off'."""
    assert _Stub()._resume_is_set_on_the_panel() is None


def test_the_window_seeds_resume_from_the_panel():
    """Structural: the window must consult the panel, not only the preference.

    Building the window needs a whole tab, which segfaults offscreen, so this
    checks the seam. If it ever goes back to reading `overlay_prompt_resume`
    alone, the window can contradict the panel again — and OK applies the
    window's values, so the contradiction is destructive.
    """
    import inspect

    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    assert "_resume_is_set_on_the_panel()" in src, \
        "the window never asks the panel what it says"
    # …and the answer must actually be USED. Checking only that the helper is
    # called nearby passed with the seeding reverted — the call was still there,
    # its result simply ignored.
    i = src.index("resume_cb.setChecked(")
    call = src[i:src.index(")\n", i) + 1]
    assert "_panel_resume" in call, (
        "Refine/resume is seeded from the remembered answer, ignoring the panel: "
        f"{call.strip()!r}. The window can then open contradicting the options "
        "behind it, and OK applies its values — unticking a refinement the user "
        "had just asked Check & Refine for."
    )


def test_ok_still_applies_to_both_modules():
    """The other half of the invariant must not have been lost in the fix."""
    import inspect

    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    assert "for cb in (self._resume_cb, self._m_resume_cb)" in src
