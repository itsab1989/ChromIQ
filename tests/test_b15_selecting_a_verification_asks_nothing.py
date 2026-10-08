"""Review of b15 item 9: the Verification box now opens on the latest dated
verification, so switching Run type to Verification selected a measured date
at once and "This chart already has a measurement" asked before the user had
done anything. Merely SELECTING a dated verification asks nothing (its
overlay follows the options panel's tick); ARRIVING at the Measure tab still
asks (Knut, #130 2026-07-29), and so does a profiling run's selection (#131
scenario 4). The protective questions at Start and on a chart change are not
touched by this."""
from __future__ import annotations

from types import SimpleNamespace

from ui.tabs.tab_measure import TabMeasure


class _Tab:
    """Just what `_offer_existing_overlay_now` reads."""

    _offer_is_for_a_selection_alone = TabMeasure._offer_is_for_a_selection_alone
    _offer_existing_overlay_now = TabMeasure._offer_existing_overlay_now

    def __init__(self, *, verification: bool, vid: str, arrival: bool):
        self._target_ctl = SimpleNamespace(target=SimpleNamespace(
            is_verification=lambda: verification, verification_id=vid))
        self._offer_on_arrival = arrival
        self._offer_queued = True
        self.asked = 0
        self.refreshed = 0

    def isVisible(self):            # noqa: N802
        return True

    def _another_window_is_open(self, which):
        return False

    def _recover_stranded_partial(self):
        return False

    def _maybe_offer_existing_overlay(self):
        self.asked += 1

    def refresh_patch_flags(self):
        self.refreshed += 1


def _run(qapp, tab):
    tab._offer_existing_overlay_now()
    qapp.processEvents()
    return tab


def test_selecting_a_dated_verification_asks_nothing(qapp):
    tab = _run(qapp, _Tab(verification=True, vid="2026-10-06_154750",
                          arrival=False))
    assert tab.asked == 0
    assert tab.refreshed == 1          # the overlay follows its tick


def test_arriving_at_the_tab_on_a_dated_verification_still_asks(qapp):
    tab = _run(qapp, _Tab(verification=True, vid="2026-10-06_154750",
                          arrival=True))
    assert tab.asked == 1
    assert tab._offer_on_arrival is False


def test_a_profiling_runs_selection_still_asks(qapp):
    tab = _run(qapp, _Tab(verification=False, vid="", arrival=False))
    assert tab.asked == 1


def test_show_event_marks_an_arrival():
    import inspect
    src = inspect.getsource(TabMeasure.showEvent)
    assert "self._offer_on_arrival = True" in src
    assert src.index("self._offer_on_arrival = True") < src.index(
        "self._queue_overlay_offer()")
