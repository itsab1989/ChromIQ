"""Asking CUPS for printers must not happen while the window is being built.

`_refresh_printers` shells out twice — `detect_printers`, then
`_on_printer_changed` → `query_options`. Both ran inside `TabPrint.__init__`,
so every launch waited on two external processes for a tab most sessions never
open: 73 ms of the startup, measured 2026-08-07.

Safe to defer because nothing outside the tab reads the printer list, and the
user cannot press a button on a tab they have not looked at.
"""
import inspect

import ui.tabs.tab_print as tp


def test_the_constructor_does_not_query_cups():
    src = inspect.getsource(tp.TabPrint.__init__)
    assert "self._refresh_printers()" not in src, (
        "the printer list is loaded during construction again, so every launch "
        "waits on CUPS for a tab that may never be opened"
    )


def test_it_is_loaded_when_the_tab_is_first_shown():
    assert hasattr(tp.TabPrint, "showEvent")
    src = inspect.getsource(tp.TabPrint.showEvent)
    assert "_refresh_printers()" in src
    assert "super().showEvent(event)" in src, "the base class must still run"


def test_it_is_loaded_once_not_on_every_show():
    """Showing the tab is common; re-querying CUPS each time would be a stall."""
    src = inspect.getsource(tp.TabPrint.showEvent)
    assert "_printers_loaded" in src
    assert src.index("self._printers_loaded = True") < src.index("_refresh_printers()"), (
        "the flag is set after the call, so a failure would retry for ever and "
        "a re-entrant show could query twice"
    )


def test_a_cups_failure_cannot_stop_the_tab_appearing():
    src = inspect.getsource(tp.TabPrint.showEvent)
    assert "except Exception" in src, (
        "an unreachable print system would keep the tab from being shown"
    )


def test_there_is_still_a_way_to_refresh_on_demand():
    """Deferring must not remove the ability to ask again."""
    assert callable(getattr(tp.TabPrint, "reload_printers", None))
    src = inspect.getsource(tp.TabPrint.reload_printers)
    assert "_refresh_printers()" in src
