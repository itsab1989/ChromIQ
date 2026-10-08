"""Beta 15 sweep: a dated verification selected WITHOUT the question (item 9)
gets the overlay the question would have given it.

Measured on screen (2026-10-08, real ET-8550 project copy): Run type to
Verification on the Measure tab opened the latest date with "Show overlay from
existing measurement" visible but UNTICKED and nothing drawn. The selection
passes a state with no measurement, where `_update_resume_availability`
hides and unticks the box (#134); before item 9 the question then re-ticked it
from its remembered answer. Beta 14 showed the 616 patches after that
question; beta 15 showed none."""
from __future__ import annotations

from types import SimpleNamespace

from ui.tabs.tab_measure import TabMeasure


class _Box:
    def __init__(self, hidden=False, checked=False):
        self._hidden, self._checked = hidden, checked

    def isHidden(self):            # noqa: N802
        return self._hidden

    def isChecked(self):           # noqa: N802
        return self._checked


class _Tab:
    """What the selection-alone branch of `_offer_existing_overlay_now` reads."""

    _offer_is_for_a_selection_alone = TabMeasure._offer_is_for_a_selection_alone
    _offer_existing_overlay_now = TabMeasure._offer_existing_overlay_now
    _apply_the_remembered_overlay_answer = \
        TabMeasure._apply_the_remembered_overlay_answer

    def __init__(self, *, remembered=True, hidden=False, checked=False,
                 engine=True):
        self._target_ctl = SimpleNamespace(target=SimpleNamespace(
            is_verification=lambda: True, verification_id="2026-10-06_154750"))
        self._offer_on_arrival = False
        self._offer_queued = True
        self._settings = SimpleNamespace(
            get=lambda k, d=None: remembered if k == "overlay_prompt_show_overlay" else d)
        self._overlay_cb = _Box(hidden, checked)
        self._m_overlay_cb = _Box(True, False)
        self._engine = engine
        self.asked = 0
        self.toggled = []

    def isVisible(self):            # noqa: N802
        return True

    def _another_window_is_open(self, which):
        return False

    def _engine_selected(self):
        return self._engine

    def _current_mode(self):
        return "guided"

    def _update_resume_availability(self):
        pass

    def _sync_overlay_checkboxes(self, checked):
        self._overlay_cb._checked = checked

    def _on_overlay_toggled(self, checked, box=None):
        self.toggled.append(checked)

    def _maybe_offer_existing_overlay(self):
        self.asked += 1

    def refresh_patch_flags(self):
        pass


def _run(qapp, tab):
    tab._offer_existing_overlay_now()
    qapp.processEvents()
    return tab


def test_an_unticked_box_is_ticked_from_the_remembered_answer(qapp):
    tab = _run(qapp, _Tab())
    assert tab.asked == 0                  # still no question (item 9)
    assert tab.toggled == [True]           # the overlay is drawn
    assert tab._overlay_cb.isChecked()


def test_a_remembered_no_leaves_the_box_alone(qapp):
    tab = _run(qapp, _Tab(remembered=False))
    assert tab.toggled == []
    assert not tab._overlay_cb.isChecked()


def test_a_box_already_ticked_is_not_drawn_twice(qapp):
    tab = _run(qapp, _Tab(checked=True))
    assert tab.toggled == []


def test_no_box_no_overlay(qapp):
    """Hidden: no measurement, or the stock chartread engine (#130 beta.120)."""
    assert _run(qapp, _Tab(hidden=True)).toggled == []
    assert _run(qapp, _Tab(engine=False)).toggled == []
