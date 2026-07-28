"""#131 (Knut, 2026-07-28), testing beta.71 in patch-by-patch mode.

Two faults, both the patch-mode half of something already fixed for strips:

* **"All patches read" the moment a resume starts.** beta.69 stopped this for
  strip reading by asking whether the chart *became* complete in this session —
  but only the `strip_ready` path consulted that rule. The `spot_ready` path,
  which is the one patch-by-patch uses, still announced it.
* **The calibration windows were not adapted to the instrument.** The
  "Calibration Complete" window has per-instrument steps in strip mode and
  dropped them entirely in patch mode — so you were told to "take a reading"
  without being told how your instrument takes one.

The first was reproduced against the real reading engine before the change and
re-measured after; what is asserted here is the rule it now follows.
"""
from __future__ import annotations

import inspect
import json

import pytest

from workflow.measure_manager import MeasureManager


class _Runner:
    def __init__(self): self.out = []
    def write_stdin(self, d): self.out.append(d)
    def __getattr__(self, _n): return lambda *a, **k: None


@pytest.fixture
def manager():
    m = MeasureManager(_Runner())
    m._engine_active = True
    m._spot_mode = True
    return m


def _session(manager, all_read):
    manager._handle_engine_line(json.dumps({
        "event": "session_start",
        "strips": [{"strip": s, "read": all_read} for s in "AB"],
    }), lambda _x: None)


# ---- "All patches read" on a resume ---------------------------------------
def test_a_complete_chart_does_not_announce_completion_in_patch_mode(manager):
    manager._is_resume = True
    _session(manager, all_read=True)
    fired = []
    manager.all_stripes_done.connect(lambda: fired.append(1))

    manager._handle_engine_line(json.dumps(
        {"event": "spot_ready", "loc": "A1", "read": True, "all_done": True}),
        lambda _x: None)

    assert fired == []


def test_reading_a_patch_does_not_make_it_news_either(manager):
    """Re-reading a patch of a finished chart completes nothing."""
    manager._is_resume = True
    _session(manager, all_read=True)
    fired = []
    manager.all_stripes_done.connect(lambda: fired.append(1))

    manager._handle_engine_line(json.dumps(
        {"event": "patch_read", "loc": "A1"}), lambda _x: None)
    manager._handle_engine_line(json.dumps(
        {"event": "spot_ready", "loc": "A2", "read": True, "all_done": True}),
        lambda _x: None)

    assert fired == []


def test_finishing_a_partly_read_chart_still_announces_it(manager):
    manager._is_resume = True
    _session(manager, all_read=False)
    fired = []
    manager.all_stripes_done.connect(lambda: fired.append(1))

    manager._handle_engine_line(json.dumps(
        {"event": "patch_read", "loc": "A9"}), lambda _x: None)
    manager._handle_engine_line(json.dumps(
        {"event": "spot_ready", "loc": "A1", "read": True, "all_done": True}),
        lambda _x: None)

    assert fired == [1]


def test_a_first_patch_measurement_is_unaffected(manager):
    manager._is_resume = False
    _session(manager, all_read=False)
    fired = []
    manager.all_stripes_done.connect(lambda: fired.append(1))
    manager._handle_engine_line(json.dumps(
        {"event": "spot_ready", "loc": "A1", "read": False, "all_done": True}),
        lambda _x: None)
    assert fired == [1]


def test_reading_a_patch_counts_as_something_happening(manager):
    """The strip path already did this; the patch path did not."""
    manager._handle_engine_line(json.dumps(
        {"event": "patch_read", "loc": "A1"}), lambda _x: None)
    assert manager._read_something is True


# ---- the calibration windows ----------------------------------------------
def test_patch_mode_has_its_own_per_instrument_steps():
    """The strip steps describe a swipe — press, hold, slide — which is not what
    this mode asks of you, so quoting them here would describe something the
    user is not doing."""
    from ui.ti2_loader import (instrument_family,
                               patch_measurement_instructions_html)
    munki = patch_measurement_instructions_html(instrument_family("X-Rite ColorMunki"))
    i1 = patch_measurement_instructions_html(instrument_family("GretagMacbeth i1 Pro"))

    assert "dial" in munki and "once" in munki
    assert "i1Pro" in i1 and "once" in i1
    assert munki != i1, "each instrument gets its own steps"
    for text in (munki, i1):
        # It may SAY there is no sliding; it must not instruct one.
        assert "and slide" not in text.lower()
        assert "press and hold" not in text.lower()
        assert "no sliding in this mode" in text.lower()


def test_an_unknown_instrument_still_gets_sensible_steps():
    from ui.ti2_loader import patch_measurement_instructions_html
    generic = patch_measurement_instructions_html(None)
    assert "highlighted patch" in generic


def test_the_calibration_complete_window_uses_them_in_patch_mode():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_calibration_done)
    assert "patch_measurement_instructions_html" in src
    assert "self._spot_session" in src
    # …and the spot branch actually shows them.
    i = src.index("if self._spot_session:")
    assert "{how}" in src[i:i + 1200]


def test_the_calibration_prompt_is_already_per_instrument():
    """It always was — this test pins it so the two windows cannot diverge."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_calibration_prompt)
    assert "calibration_instructions_html" in src
    assert "instrument_family(self._detected_instrument)" in src
