"""A user preset picked after the tab showed a run's own chart is applied,
even when the dropdown still shows that preset from another run (review of
4.3.14: on run2, Verification, From Profile's Gamut, the pick was taken for
a re-pick and its label style and X offset never reached the panel)."""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart                      # noqa: E402


class _Combo:
    def itemData(self, i):
        return "My-preset"


class _Tab:
    _on_preset_activated = TabChart._on_preset_activated

    def __init__(self, last):
        self._last_preset_index = last
        self._preset_combo = _Combo()
        self.applied = []

    def _on_preset_selected(self, i):
        self.applied.append(i)


def test_showing_a_run_chart_forgets_the_applied_preset():
    src = inspect.getsource(TabChart._display_run_chart)
    restore = src.index("self._restore_chart_settings(ti2)")
    assert "self._last_preset_index = -1" in src[restore:]


def test_after_that_the_same_entry_is_applied_and_a_real_repick_is_not():
    t = _Tab(last=-1)          # a run's chart was shown
    t._on_preset_activated(3)
    assert t.applied == [3]
    t = _Tab(last=3)           # the preset itself was the last thing applied
    t._on_preset_activated(3)
    assert t.applied == []     # #175: a re-pick changes nothing
