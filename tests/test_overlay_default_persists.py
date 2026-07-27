"""#134/#130 (Knut, 2026-07-27): the Measure tab must not force
"Show overlay from existing measurement" off when it is built.

That was half of why "Save as Defaults" appeared to do nothing — the other half
being that the button never recorded the switch. Both halves are fixed; this
pins the half that can be checked without building a Measure tab.

Building one here aborted the interpreter at teardown (the QThread-lifetime
family), so the behavioural half is deliberately not tested from a live tab
rather than shipping a test that can crash the suite for everyone.
"""
from __future__ import annotations

import inspect


def _measure_tab_source() -> str:
    from ui.tabs.tab_measure import TabMeasure
    return inspect.getsource(TabMeasure)


def test_the_switch_starts_from_the_saved_value():
    src = _measure_tab_source()
    assert 'self._settings.get("measure_show_overlay", False)' in src, \
        "the tab must read the saved default when it is built"


def test_the_switch_is_never_forced_off_at_build_time():
    """The original fault: hard-coded off, so nothing saved could return."""
    src = _measure_tab_source()
    assert "self._overlay_cb.setChecked(False)" not in src
    assert "self._m_overlay_cb.setChecked(False)" not in src, "manual mode too"


def test_save_as_defaults_records_the_switch():
    """It was simply missing from the list that button writes."""
    src = _measure_tab_source()
    body = src[src.index("def _on_save_defaults"):]
    body = body[:body.index("\n    def ", 1)]
    assert 'measure_show_overlay' in body, \
        "Save as Defaults must write the overlay switch"
    assert body.count("measure_show_overlay") == 2, \
        "both guided and manual mode must record it"
