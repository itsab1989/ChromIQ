"""Start Measurement is offered only when there is a chart to measure.

Knut, #130 2026-08-04, reviewing a proposed message for "readings with no chart
beside them": *"Is this realistic? Can a chart read at all be initiated if a ti2
file does not exist? I thought it could not. Thus the Start Measurement button
should not be available at all for starting a measurement, meaning this
condition is not valid."*

He was right about what should happen. He was wrong about what did — and that is
the point of this file. **Start Measurement was enabled with no `.ti2`**: the
Measure tab is loaded from the `.ti1` when a project is opened, and the button
was enabled from that alone, so pressing it ran chartread against a chart file
that was not there.

The fix is to prevent the condition, exactly as he reasoned, rather than to
write a message for it. The message that was proposed for it is gone.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_measure import TabMeasure       # noqa: E402


def _tab(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

    st = AppSettings()
    return TabMeasure(ArgyllRunner(st), st, None)


def test_a_chart_with_no_ti2_does_not_offer_start(qapp, tmp_path):
    tab = _tab(qapp)
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("CTI1\n", encoding="utf-8")
    tab.set_ti1_path(ti1)                       # what opening a project does
    assert not tab._start_btn.isEnabled()


def test_the_same_chart_with_a_ti2_does(qapp, tmp_path):
    tab = _tab(qapp)
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("CTI1\n", encoding="utf-8")
    (tmp_path / "chart.ti2").write_text("CGATS.17\n", encoding="utf-8")
    tab.set_ti1_path(ti1)
    assert tab._start_btn.isEnabled()


def test_being_handed_the_ti2_itself_works_too(qapp, tmp_path):
    """Most paths hand this tab the `.ti2`; one hands it the `.ti1`."""
    tab = _tab(qapp)
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("CGATS.17\n", encoding="utf-8")
    tab.set_ti1_path(ti2)
    assert tab._start_btn.isEnabled()


def test_a_greyed_button_says_why(qapp, tmp_path):
    """A control that is unavailable without explanation is the thing this
    project keeps having to fix."""
    tab = _tab(qapp)
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("CTI1\n", encoding="utf-8")
    tab.set_ti1_path(ti1)
    tip = tab._start_btn.toolTip()
    assert "no laid-out chart to measure" in tip
    assert ".ti2" in tip
    assert "Create Chart" in tip, "…and how to get one"


def test_the_tooltip_is_cleared_once_it_can_be_pressed(qapp, tmp_path):
    """The REASON it was greyed must go once it can be pressed.

    It used to assert the tooltip was empty. Since 4.1.3-beta.15 an enabled
    primary button carries its keyboard shortcut — "Start Measurement (⌘↵)" —
    so emptiness is no longer the right test, and asserting it would have
    forced that hint back off the one button of the five that shows it. What
    matters is unchanged: no explanation of a block that no longer applies.
    """
    tab = _tab(qapp)
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("CGATS.17\n", encoding="utf-8")
    tab.set_ti1_path(ti2)

    tip = tab._start_btn.toolTip()
    assert "chart" not in tip.lower(), (
        f"the greyed-reason survived into an enabled button: {tip!r}")
    assert "\n" not in tip, f"an explanation is still attached: {tip!r}"
    assert tip == "" or "Start" in tip, (
        f"expected either nothing or the button's own name + shortcut, got {tip!r}")


def test_start_is_guarded_as_well_as_greyed():
    """Greying a button is a hint; a guard is the rule. Both, because the
    button can be re-enabled by any number of other paths."""
    src = inspect.getsource(TabMeasure._on_start)
    assert "_blocked_by_missing_chart_file()" in src
    guard = inspect.getsource(TabMeasure._blocked_by_missing_chart_file)
    assert "_say_on_screen" in guard, "and it explains, rather than doing nothing"


def test_the_chart_file_is_resolved_from_either_extension():
    fn = TabMeasure._chart_file_for
    assert fn(Path("/x/chart.ti1")).name == "chart.ti2"
    assert fn(Path("/x/chart.ti2")).name == "chart.ti2"
    assert fn(None).name == ""


def test_the_message_for_the_prevented_condition_is_gone():
    """It described a state that can no longer be reached."""
    from workflow import measurement_messages as M

    assert not hasattr(M, "M_REPLACE_NO_CHART")
    assert "M-REPLACE-NO-CHART" not in M.CATALOGUE


def test_the_model_records_why_it_was_removed():
    spec = (Path(__file__).resolve().parent.parent / "docs" / "design"
            / "unified_measurement_management.md").read_text(encoding="utf-8")
    assert "Removed 2026-08-04" in spec
    assert "Start Measurement was offered without a `.ti2`" in spec
