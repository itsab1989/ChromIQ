"""Moving a layout box leaves the "Measured from Preview" frame alone.

**THIS FILE USED TO ASSERT THE OPPOSITE, AND KNUT REVERSED IT.** B8-176 put
`self._update_margin_inspector()` into `_refresh_manual_command_preview` on
2026-09-15, measured on screen: with a real Generate and then eleven real
keyboard and mouse gestures, 8 of the 11 left the frame showing a sentence the
state had not earned. That was the right fix for the panel it found, where
every notice was PREDICTED from the boxes and so a frozen notice was simply
stale.

It is the wrong fix for the panel Knut's ruling of the same day builds
(#182, comment 5679470670):

    "When any chart layout parameter changes, a red text says to click Generate
     Chart to update the preview. This is the correct behaviour, so the margin
     warnings need only be updated upon the chart being updated with Generate
     Chart, and the also the calculations should use the Measured from Preview
     numbers in the calculations if text fit. This simplifies very much the
     calculation and it does not need to calculate across many page sizes or
     other searches, and does not need to do this every time a setting is
     changed. ... they are only usable after the Measured from Preview margin
     values have been completed (after a Generate Chart has been performed)."

Every notice on that frame is now a measurement of the sheet in the preview,
and no spin box can change that sheet without a Generate. A frame headed
"Measured from Preview" that repainted on a keystroke would be asserting a
measurement of a sheet nobody has drawn. What tells the reader the boxes are
ahead of the frame is the red "press Generate Chart" sentence
`_refresh_unapplied_warning` paints, which Knut names in the same ruling as
already correct, and which this file also pins.

**AND THE COST THE REVERTED CALL WAS ACCEPTED ON WAS WRONG BY 28x.** Its
comment quoted "8.5 to 20.3 ms median, worst single pass 63.7 ms". Measured on
a real chart, ten consecutive calls, `_update_margin_inspector` is **563 ms
median** (556 to 594) on a 1.86 MB TIFF, because a non-engine chart re-measures
the raster every time: `measure_margins` costs 93 ms on Knut's 0.58 MB sheet
against 0.7 ms for `measure_from_engine`. It shipped in beta 17 and was paid on
every layout keystroke. B8-179.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    s.set("auto_update_preview", False)      # the shipped default
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    yield t
    t.deleteLater()


def test_a_layout_change_does_not_remeasure_the_frame(tab, monkeypatch):
    """A margin box moves and the frame is NOT asked for a fresh report.

    MUTATION: put `self._update_margin_inspector()` back into
    `_refresh_manual_command_preview` and this goes red, which is the state
    v4.3.0-beta.17 shipped in.
    """
    calls: list[int] = []
    monkeypatch.setattr(type(tab), "_update_margin_inspector",
                        lambda self: calls.append(1), raising=True)
    tab._margin_tiffs = ["a-chart.tif"]
    tab._refresh_manual_command_preview()
    assert calls == [], (
        "moving a layout box re-measured the 'Measured from Preview' frame. "
        "Under Knut's ruling of 2026-09-15 that frame describes the sheet in "
        "the preview, which only Generate Chart can change")


def test_the_notes_box_and_the_stamp_tick_leave_it_alone_too(tab, monkeypatch):
    """The two controls `_on_chart_settings_touched` serves, same rule.

    They were given the call on 2026-09-13, before the other twenty, and it
    comes out with them.

    MUTATION: put the call back and this goes red.
    """
    calls: list[int] = []
    monkeypatch.setattr(type(tab), "_update_margin_inspector",
                        lambda self: calls.append(1), raising=True)
    tab._margin_tiffs = ["a-chart.tif"]
    tab._on_chart_settings_touched()
    assert calls == [], (
        "typing in the chart-notes box re-measured the frame")


def test_the_red_press_generate_sentence_is_what_moves_instead(tab,
                                                               monkeypatch):
    """The reader is not left with nothing: the UNAPPLIED warning still fires.

    Knut's ruling leans on it by name, so it is pinned here rather than
    assumed. Both hooks must reach it.
    """
    seen: list[str] = []
    monkeypatch.setattr(type(tab), "_refresh_unapplied_warning",
                        lambda self: seen.append("x"), raising=True)
    tab._margin_tiffs = ["a-chart.tif"]
    tab._refresh_manual_command_preview()
    assert seen, ("a layout change no longer repaints the 'press Generate "
                  "Chart' sentence, which is the only thing telling the "
                  "reader the frame is behind the boxes")
    seen.clear()
    tab._on_chart_settings_touched()
    assert seen, ("the chart-notes box no longer repaints the 'press Generate "
                  "Chart' sentence")


def test_the_layout_panel_really_routes_through_that_hook(tab):
    """The hook is still the one every layout control reaches.

    It is what carries the unapplied warning now, so it matters just as much
    as it did when it carried the panel refresh.
    """
    src = inspect.getsource(inspect.getmodule(type(tab)))
    assert "_manual_layout_panel.changed.connect(" \
           "self._refresh_manual_command_preview)" in src.replace("\n", ""), (
        "the layout panel no longer routes its changes through "
        "_refresh_manual_command_preview")


def test_no_hook_on_a_keystroke_calls_the_margin_inspector():
    """Said of the SOURCE as well, so a differently-spelled call is caught.

    MUTATION: add `self._update_margin_inspector()` to either method and this
    goes red.
    """
    from ui.tabs.tab_chart import TabChart
    for name in ("_refresh_manual_command_preview",
                 "_on_chart_settings_touched"):
        src = inspect.getsource(getattr(TabChart, name))
        body = "\n".join(l for l in src.splitlines()
                         if not l.strip().startswith("#")
                         and '"""' not in l)
        assert "_update_margin_inspector()" not in body, (
            f"{name} measures the preview again on every keystroke; Knut's "
            f"ruling of 2026-09-15 says only Generate Chart may")
