"""#130 (Knut, 2026-07-29): the chart's instrument vs the one connected.

    *"When I make a chart for instrument i1Pro, then go to measure tab and start
    measurement, while my Colormunki instrument is connected, there is not error
    window poping up, nor an error sound."*

He is right that it should be caught, and the reason it was not is worth
recording: **there was nothing for ChromIQ to notice.** The existing "Instrument
Type Mismatch" window fires on an ArgyllCMS *capability* failure — a device
asked for a kind of reading it cannot do — and both an i1Pro and a ColorMunki
read reflective happily. The mismatch that matters here is between the chart's
LAYOUT and the device, which only ChromIQ knows, so only ChromIQ can raise it.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication              # noqa: E402

from data.patch_db import (instrument_family_of,      # noqa: E402
                           instrument_mismatch)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- recognising what is plugged in -------------------------------------
@pytest.mark.parametrize("model,code", [
    ("X-Rite ColorMunki", "CM"),
    ("ColorMunki Photo", "CM"),
    ("i1Studio", "CM"),
    ("ColorChecker Studio", "CM"),
    ("i1Pro", "i1"),
    ("X-Rite i1Pro 2", "i1"),
    ("i1Pro3", "i1"),
    ("i1Pro3 Plus", "p3"),
    ("SpectroScan", "SS"),
    ("i1iSis", "isis"),
])
def test_the_reported_model_is_recognised(model, code):
    assert instrument_family_of(model) == code


def test_the_plus_is_told_from_the_plain_family():
    """Its model string contains "i1Pro" too, and the specific answer is the
    right one — so the order of the checks is behaviour, not tidiness."""
    assert instrument_family_of("i1Pro3 Plus") == "p3"
    assert instrument_family_of("i1Pro3") == "i1"


def test_an_unknown_device_is_not_recognised():
    assert instrument_family_of("Frobnicator 9000") is None
    assert instrument_family_of("") is None


# ---- deciding whether to warn -------------------------------------------
def test_his_case_is_a_mismatch():
    pair = instrument_mismatch("i1", "X-Rite ColorMunki")
    assert pair is not None
    chart, found = pair
    assert "i1Pro" in chart
    assert "ColorMunki" in found


def test_the_right_instrument_says_nothing():
    assert instrument_mismatch("CM", "X-Rite ColorMunki") is None
    assert instrument_mismatch("i1", "i1Pro 2") is None


def test_a_plus_reading_a_plain_i1_chart_is_allowed():
    """It can read those patches — they are merely larger than it needs."""
    assert instrument_mismatch("i1", "i1Pro3 Plus") is None


def test_a_plain_i1_reading_a_plus_chart_is_a_mismatch():
    """The other way round is not safe: the Plus lays out bigger patches."""
    assert instrument_mismatch("p3", "i1Pro 2") is not None


def test_an_unknown_model_never_warns():
    """An unrecognised device is not evidence of a mismatch, and a wrong
    warning would be worse than none."""
    assert instrument_mismatch("i1", "Frobnicator 9000") is None
    assert instrument_mismatch("i1", "") is None


def test_no_chart_instrument_never_warns():
    assert instrument_mismatch("", "X-Rite ColorMunki") is None


# ---- the window ----------------------------------------------------------
def test_the_check_runs_when_the_instrument_reports_itself():
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_instrument_detected)
    assert "_warn_if_instrument_does_not_match_chart" in src


def test_the_window_sounds_and_offers_a_way_out():
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._warn_if_instrument_does_not_match_chart)
    assert '_cue_window("INSTRUMENT_ERROR")' in src
    assert "Measure anyway" in src and "Cancel" in src
    assert "self._manager.abort()" in src, "Cancel must actually stop it"
    assert "fit_message_box_buttons(box)" in src


def test_cancel_is_the_default_button():
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._warn_if_instrument_does_not_match_chart)
    assert "box.setDefaultButton(cancel)" in src


def test_it_warns_once_for_one_pairing():
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._warn_if_instrument_does_not_match_chart)
    assert "_mismatch_warned_for" in src


def test_it_never_breaks_a_measurement():
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    assert "except Exception" in inspect.getsource(
        TabMeasure._warn_if_instrument_does_not_match_chart)
