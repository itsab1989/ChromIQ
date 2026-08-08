"""Opening a chart must not drag you off the tab you are working on.

Basti, 2026-08-08: he was on the Measure tab, opened a `.ti2`, and ChromIQ
jumped him back to Create Chart. `_on_masthead_load_ti2` ended with an
unconditional `setCurrentWidget(self._tab_chart)`, justified as *"the tabs are
numbered in workflow order, so that is where a freshly opened chart is looked at
first"*.

Reasonable when the chart arrives from somewhere unrelated — but **the masthead
is the only way to load a chart**, so there was no route that left you where you
were. It also sat badly beside a rule this model has already corrected twice:
ending a measurement, and stopping a calibration, must not change tab by
themselves (K18, beta.153).

Measure and Print both display the loaded chart, so standing on either is
already the right place.

Structural, because the behavioural route needs the whole MainWindow, which
segfaults under the offscreen platform the gate runs on.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _source_of_masthead_load() -> str:
    from ui.main_window import MainWindow

    return inspect.getsource(MainWindow._on_masthead_load_ti2)


def test_the_jump_to_create_chart_is_conditional():
    """An unconditional navigate is the bug; the guard is the fix."""
    src = _source_of_masthead_load()
    assert "setCurrentWidget(self._tab_chart)" in src, (
        "the handler no longer navigates at all — if that is deliberate, this "
        "test should be updated rather than deleted, so the reason stays written "
        "down"
    )
    guard = "if self._tabs.currentWidget() not in (self._tab_measure, self._tab_print):"
    assert guard in src, (
        "the jump to Create Chart is unconditional again. A user standing on "
        "Measure, about to measure the chart they just opened, is thrown back to "
        "tab 1 — and the masthead is the only way to open a chart, so there is "
        "no route that avoids it."
    )


def test_the_guard_covers_both_tabs_that_show_the_chart():
    """Print shows the chart's pages; Measure shows its preview. Both count."""
    src = _source_of_masthead_load()
    for tab in ("self._tab_measure", "self._tab_print"):
        assert tab in src, f"{tab} is no longer exempt from the jump"
