"""#130 (Knut, 2026-07-29). Three rulings in one comment.

1. **The "This chart already has a measurement" window is informational, and its
   trigger was wrong.** *"Condition '1: the .ti2 path just loaded differs from
   the .ti2 path previously loaded' makes no sense to test for in relation to a
   specific run. It will only annoy users. Changing profile run naturally
   changes the path that the app sees, but from one specific run nothing has
   actually changed. I see this message as informational only, and if that is
   the intention, then it should also happen when moving from any other tab on
   the same run to the measure tab."*

   So the trigger is **arriving at the Measure tab**, not a changed path.

2. **The ColorMunki spacer margins were too small.** *"Due to the small values
   on paper, to make sure readings fall within a spacer (and not on the edges),
   a margin of 40-60% is needed."* — with the two worked lines rewritten to
   match, and a reminder that the width wants verifying by test.

3. **Three help sentences that tie a default to prose must go**, so *"the
   example calculations can stand for them self, and defaults can be set without
   thinking of the help text."*

(The per-instrument "Patches per strip" column from the same comment is tested
in test_pace_speed_estimate.py, beside the arithmetic it feeds.)
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import core.measure_pace as mp                       # noqa: E402


# ---- 1. the offer follows the tab, not the path -------------------------
def test_showing_the_tab_offers_the_existing_measurement():
    """It no longer waits for a flag that only a chart change could set."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure.showEvent)
    assert "self._queue_overlay_offer()" in src
    assert "if not self._pending_overlay_offer:" not in src, (
        "the offer is still gated on a chart having changed — Knut's point was "
        "that a run whose chart did not change is exactly when it is wanted")


def test_it_is_still_never_opened_from_inside_show_event():
    """The half-painted-window fault of 2026-07-28 must stay fixed."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure.showEvent)
    assert "_maybe_offer_existing_overlay()" not in src


def test_it_still_never_appears_over_another_tab():
    """#134 / K1 stands: the window is a Measure-tab feature."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._offer_existing_overlay_now)
    assert "self.isVisible()" in src


def test_it_never_appears_over_a_measurement_in_progress():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    assert "self._runner.is_running" in src


def test_only_one_window_can_be_open_at_a_time():
    """Being shown and a chart arriving can queue the offer in the same turn of
    the event loop; that must not stack two identical windows."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    assert '_offer_open' in src


def test_the_per_run_silence_is_what_stops_it_being_noise():
    """Offering on every arrival is only reasonable because one tick silences
    the run being worked through — his own "don't ask again" rule."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    assert "self._offer_silenced" in src
    assert "_replace_warning_scope()" in src


def test_nothing_is_offered_when_the_run_holds_no_measurement():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    first = src.index("_existing_ti3_for_chart()")
    assert first < src.index("QDialog(self)")


# ---- 2. the ColorMunki spacer margins -----------------------------------
def _munki_body() -> str:
    return mp.explanation_for("colormunki")[1]


def test_the_spacer_margin_is_forty_to_sixty_percent():
    body = _munki_body()
    assert "40 to 60 %" in body
    assert "20 to 30 %" not in body, "the old, too-small margin is still there"


def test_the_minimum_spacer_width_follows_the_new_margin():
    body = _munki_body()
    assert "roughly 1.0 to 1.1 mm" in body
    assert "0.8 to 0.9 mm" not in body


def test_the_worked_example_uses_the_new_margin():
    body = _munki_body()
    assert "0.8 × 1.4 = 1.1" in body and "0.8 × 1.6 = 1.3" in body
    assert "1.1 to 1.3 mm wide" in body
    assert "1.2 = 0.96" not in body and "about 1 mm wide" not in body


def test_the_user_is_told_to_verify_the_width_by_test():
    """His added line — the arithmetic gives a starting point, not a guarantee."""
    body = _munki_body()
    assert "verif" in body.lower() and "test" in body.lower()


# ---- 3. the three sentences that had to go ------------------------------
@pytest.mark.parametrize("key,gone", [
    ("i1pro3",     "The stricter of the two is taken."),
    ("i1pro3plus", "The default sits between the two."),
    ("colormunki", "The default is therefore 23"),
])
def test_a_default_is_no_longer_argued_for_in_prose(key, gone):
    assert gone not in mp.explanation_for(key)[1], key


def test_the_worked_examples_themselves_are_untouched():
    """He asked for the *conclusions* to go, not the arithmetic that leads to
    them: "then the example calculations can stand for them self"."""
    assert "1000 readings per strip" in mp.explanation_for("i1pro3")[1]
    assert "about 53 each" in mp.explanation_for("i1pro3plus")[1]
    assert "250 ÷ 11 = 23 readings per patch" in _munki_body()


# ---- Knut's new defaults, and reaching users who have the old ones -------
@pytest.mark.parametrize("key,hz,minimum,patches", [
    ("i1pro",       100.0, 20, 25),
    ("i1pro2",      200.0, 20, 25),
    ("i1pro3",      400.0, 33, 30),
    ("i1pro3plus",  400.0, 66, 15),
    ("colormunki",   50.0, 20, 15),
    ("spectroscan", 250.0, None, None),
])
def test_the_shipped_figures_are_his(key, hz, minimum, patches):
    assert mp.MODEL_DEFAULTS[key] == (hz, minimum), key
    assert mp.ESTIMATE_PATCHES[key] == patches, key


def test_an_unknown_instrument_borrows_the_slowest_strip_length():
    assert mp.estimate_patches_for("something-else") == \
        mp.ESTIMATE_PATCHES["i1pro"]


def test_a_stored_echo_of_an_old_minimum_is_dropped(tmp_path):
    """Preferences → Save writes every key, so anyone who has ever opened that
    dialog carries the old defaults and would never see the new ones."""
    from PyQt6.QtCore import QSettings

    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("pace_min_samples_i1pro3", 30)          # the old default
    s._qs.setValue("pace_min_samples_i1pro3plus", 60)      # the old default
    s._qs.setValue("pace_min_samples_colormunki", 23)      # the old default
    s._qs.setValue("pace_min_samples_i1pro", 45)           # the user's own
    s._qs.setValue("pace_estimate_patches", 24)            # the removed box

    s.migrate()

    for key in ("pace_min_samples_i1pro3", "pace_min_samples_i1pro3plus",
                "pace_min_samples_colormunki", "pace_estimate_patches"):
        assert s._qs.value(key, None) is None, key
    assert int(s._qs.value("pace_min_samples_i1pro")) == 45


def test_a_deliberately_chosen_minimum_survives(tmp_path):
    from PyQt6.QtCore import QSettings

    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("pace_min_samples_i1pro3", 41)
    s.migrate()
    assert int(s._qs.value("pace_min_samples_i1pro3")) == 41
