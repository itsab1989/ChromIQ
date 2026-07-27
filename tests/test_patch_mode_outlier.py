"""#131 (Knut, 2026-07-27): what "stands out" can mean when patches arrive one
at a time.

His question, and it caught a real overstatement in my release note: I said the
switch "governs both reading modes", but it only ever reached strip mode — patch
by patch still used the bare limit. His follow-up is the right one: *"when only a
few patches have been measured how is the 'standing out' determined? is the
feature dependant on reading the whole strip manually before it is really known
if one or more stand out?"*

It cannot be a strip, because there is no finished strip. So the comparison is
against **the patches already read in this session**:

* the first few are judged on the limit alone — the fence returns 0 below four
  readings, so nothing is compared against a population too small to have a
  spread;
* from there on, the population grows as you work;
* and a patch's outline is decided once, when it is drawn. A flag that appeared
  or disappeared later, as the population shifted, would be worse than none.
"""
from __future__ import annotations

import inspect

from ui.tabs.tab_measure import TabMeasure, _strip_outlier_fence


def test_a_population_too_small_to_judge_falls_back_to_the_limit():
    """Below four readings there is no spread worth calling a spread."""
    assert _strip_outlier_fence([]) == 0.0
    assert _strip_outlier_fence([10.0]) == 0.0
    assert _strip_outlier_fence([10.0, 12.0, 11.0]) == 0.0


def test_with_enough_readings_it_answers_from_the_population():
    """Twenty ordinary readings and one wild one: the fence sits above the
    ordinary ones and below the wild one."""
    des = [8.0, 9.0, 8.5, 9.5, 10.0, 8.2, 9.1, 8.8, 9.3, 8.6] + [70.0]
    fence = _strip_outlier_fence(des)
    assert 10.0 < fence < 70.0


def test_a_uniformly_bad_reading_set_flags_nothing_extra():
    """Knut's deliberately-wrong chart: everything is far off together, so
    nothing stands out — which is the behaviour the switch exists to turn off."""
    des = [55.0, 58.0, 60.0, 57.0, 56.0, 59.0, 61.0, 54.0]
    fence = _strip_outlier_fence(des)
    assert all(d < fence for d in des), fence


def test_patch_mode_uses_the_running_population():
    src = inspect.getsource(TabMeasure._on_patch_measured)
    assert "self._spot_des.append(de_p)" in src
    assert "_strip_outlier_fence(self._spot_des)" in src
    assert "self._use_outlier_fence()" in src


def test_patch_mode_honours_the_same_switch_as_strip_mode():
    """Which is what my release note claimed before it was true."""
    patch = inspect.getsource(TabMeasure._on_patch_measured)
    strip = inspect.getsource(TabMeasure._on_strip_measured)
    assert "_use_outlier_fence()" in patch and "_use_outlier_fence()" in strip


def test_a_flag_is_decided_once_and_not_revisited():
    """No retroactive outlines: the patch is drawn with the verdict it had when
    it was read."""
    src = inspect.getsource(TabMeasure._on_patch_measured)
    # It draws THIS patch only — one item, appended to what is already there.
    assert "set_patch_overlay(page, [item])" in src


def test_the_population_starts_empty_for_each_measurement():
    src = inspect.getsource(TabMeasure._clear_pace_readout)
    assert "self._spot_des = []" in src


def test_the_population_exists_before_any_measurement():
    """A patch read before anything cleared the state must not raise, so it is
    created while the tab is built rather than only when a read starts."""
    src = inspect.getsource(TabMeasure._build_ui)
    assert "self._spot_des: list = []" in src
