"""Every help that walks through measuring says to start sliding at the beep,
for every strip reader (Knut, #202 5952802491): "the reading speed measurement
from the time beep occurs shall be the same for all the instruments that perform
strip-reading (Not CR30 or SpectroScan), and that the help text and the
Calibration Complete message for all these instruments should mention to start
after the beep sound occurs ... Also the help cards that detail steps on how to
perform measurement should mention when to start sliding the instrument, after
the beep (not at click of button)."

The clock itself is instrument-blind: `TabMeasure._on_scan_ready` moves it on
the engine's `scan_ready`, which ArgyllCMS 3.5.0 raises for the i1Pro
(i1pro_imp.c:3199), the i1Pro 3 (i1pro3_imp.c:12857) and the ColorMunki
(munki_imp.c:2320), the strip readers ChromIQ times.
"""
from __future__ import annotations

import inspect


def test_each_measuring_step_of_the_cards_carries_the_note():
    from ui.dialogs import welcome_dialog as W
    src = inspect.getsource(W)
    assert src.count("_beep_note())") == 3
    title, text = W._beep_note()
    assert title == "When to start sliding"
    for name in ("i1Pro", "i1Pro 3", "ColorMunki", "CR30", "SpectroScan"):
        assert name in text


def test_the_tour_says_it_too():
    import ui.getting_started as G
    src = inspect.getsource(G)
    assert '"With an instrument that reads strips, start sliding when "' in src
    assert '"you hear the beep, not at the press of its button."' in src


def test_preferences_names_every_strip_reader():
    from ui.dialogs.settings_dialog import pace_clock_note, pace_clock_section
    for t in (pace_clock_note(), pace_clock_section()):
        for name in ("i1Pro 2", "i1Pro 3 Plus", "ColorMunki"):
            assert name in t, name


def test_the_calibration_window_does_not_claim_a_lamp_for_every_instrument():
    from ui.ti2_loader import measurement_instructions_html as how
    assert "needs a moment before it starts reading" in how("colormunki")
    assert "warms up its lamp, and the reading" not in how("colormunki")


def test_the_clock_starts_at_the_beep_whatever_the_instrument():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_scan_ready)
    for fam in ("i1pro", "colormunki", "instrument_family", "_detected_instrument"):
        assert fam not in src.split('"""')[2], fam
