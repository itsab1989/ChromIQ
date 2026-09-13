"""The layout stamp is a bottom line too, and nothing measured its width.

Knut, 2026-09-13, testing beta 8::

    When using "Stamp layout information along the bottom" (and no custom text)
    with font size 13 or 14 makes text that cross into the right clip-border
    text, but no warning is given. This happens regardless of the clip-border
    is on left of right side.

The bottom of a sheet carries up to two lines: the custom "Sheet text" and the
layout summary. `raster.render_pages` builds them as one list and shrinks the
PAIR against the room between the two side bounds. The panel's HEIGHT check
counts both. Its WIDTH check asked `if r.chart_text:` and measured that string
alone, so with the stamp on and the text box empty the check never ran, and
with both on it under-measured whenever the stamp was the longer line.

That is this project's recurring fault: a guard on one door and not the
identical door beside it.

The stamp's text is predicted from `chart.stamp_summary_line`, the function
the build itself calls. It must not be a second copy of that f-string, and
`test_the_panel_and_the_build_word_the_stamp_the_same` below is what stops one
appearing.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow import text_edge_fit as tef                  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe    # noqa: E402


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
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    yield t
    t.deleteLater()


def _recipe(**kw) -> LayoutRecipe:
    """Knut's case: A4, the stamp on, the text box empty, a typed 13 pt."""
    r = LayoutRecipe()
    r.instrument, r.paper = "CM", "A4"
    r.layout_mode, r.use_instrument_margins = "area_first", False
    r.margin_top = r.margin_bottom = 15.0
    r.margin_left = r.margin_right = 12.0
    r.text_edge_top_mm = r.text_edge_mm = r.text_edge_clip_mm = 4.0
    r.chart_text, r.stamp_command = "", True
    # 13 pt, typed, which is what he set and what never shrinks.
    r.chart_text_size_mm = 13.0 * 25.4 / 72.0
    r.show_strip_indicators, r.show_row_indicators = True, False
    r.helper_markers = False
    r.helper_marker_edge_mm, r.helper_marker_len_mm = 4.0, 2.0
    r.helper_markers_top_bottom = r.helper_markers_sides = True
    r.clip_border, r.clip_border_width_mm, r.clip_side = True, 12.0, "right"
    r.randomize, r.seed_fixed, r.seed = True, True, 1234567890
    for k, v in kw.items():
        setattr(r, k, v)
    return r


# --------------------------------------------------------------- the line
def test_the_panel_and_the_build_word_the_stamp_the_same():
    """ONE f-string. A re-implementation that drifts from the shipped function
    is how a prediction comes to warn about a sheet nobody prints."""
    from workflow.layout_engine.chart import (friendly_instrument,
                                              stamp_summary_line)
    from workflow.layout_engine import papers
    line = stamp_summary_line("CM", "A4", 300, 918, 42)
    assert line == (f"ChromIQ engine · {friendly_instrument('CM')} · "
                    f"{papers.friendly_label('A4')} · 300 dpi · "
                    f"918 patches · seed 42")
    assert "ColorMunki" in line, "the instrument is printed by its key, not its name"


def test_the_bottom_lines_include_the_stamp(tab):
    """MUTATION: put `_bottom_sheet_text_lines` back to `[r.chart_text]` and
    this goes red, which is the state that shipped in beta 8."""
    r = _recipe()
    lines = tab._bottom_sheet_text_lines(r)
    assert len(lines) == 1, f"expected the stamp alone, got {lines}"
    assert lines[0].startswith("ChromIQ engine"), lines[0]
    both = tab._bottom_sheet_text_lines(_recipe(chart_text="A CUSTOM LINE"))
    assert len(both) == 2 and both[0] == "A CUSTOM LINE"
    assert both[1].startswith("ChromIQ engine")


def test_the_stamp_alone_is_given_a_width(tab):
    """With no custom text the panel used to measure nothing at all."""
    assert tab._sheet_text_width_mm(_recipe()) > 0.0, (
        "the panel predicts no width for a sheet that prints a line")
    assert tab._sheet_text_width_mm(_recipe(stamp_command=False)) == 0.0, (
        "a sheet with neither line must still predict nothing")


# ------------------------------------------------------------ the warning
#: A real ColorMunki chart's patch count. The stamp prints it, so it is part of
#: the line's WIDTH: Knut's report is about a preset chart, and a fresh tab
#: with no patch source chosen stamps "0 patches", four characters shorter.
_PATCHES = 918


def _panel_warnings(tab, **over) -> "list[str]":
    """Knut's configuration pushed through the REAL panel, and what the red
    message field then holds.

    Driven through `panel.set_recipe` and `TabChart._engine_text_notes` rather
    than by calling the helpers directly, because the fault being fixed was a
    gate in `_engine_text_notes` and a helper that never got there would prove
    nothing about it.
    """
    from ui.tabs.tab_chart import TabChart
    if tab._manual_auto_patches_check is not None:
        tab._manual_auto_patches_check.setChecked(False)
    if tab._manual_f_pw is not None:
        tab._manual_f_pw._control.setValue(_PATCHES)
    panel = tab._manual_layout_panel
    r = panel.get_recipe()
    r.instrument, r.paper = "CM", "A4"
    r.chart_text, r.stamp_command = "", True
    r.chart_text_size_mm = 14.0 * 25.4 / 72.0      # his size, typed, no shrink
    r.clip_border, r.clip_border_width_mm = True, 12.0
    r.clip_side, r.text_edge_clip_mm = "right", 4.0
    for k, v in over.items():
        setattr(r, k, v)
    panel.set_recipe(r)
    return [m for m in TabChart._engine_text_notes(tab)[1]
            if "along the bottom is too wide" in m]


def test_the_control_says_this_configuration_really_does_overflow(tab):
    """The control. Every test below is vacuous if the line happens to fit, so
    the overflow is measured off `text_edge_fit` first, from the panel's own
    predicted width."""
    from workflow.layout_engine import papers
    if tab._manual_auto_patches_check is not None:
        tab._manual_auto_patches_check.setChecked(False)
    if tab._manual_f_pw is not None:
        tab._manual_f_pw._control.setValue(_PATCHES)
    r = _recipe(chart_text_size_mm=14.0 * 25.4 / 72.0)
    w = tab._sheet_text_width_mm(r)
    pw = float(papers.dimensions_mm(r.paper)[0])
    wo = tef.bottom_text_overflow(
        pw, r.text_edge_clip_mm, w, r.helper_markers,
        r.helper_marker_edge_mm, r.helper_marker_len_mm,
        r.helper_markers_sides,
        clip_border_mm=r.clip_border_width_mm, clip_side=r.clip_side)
    assert wo is not None, (
        f"this fixture does not overflow ({w:.1f} mm on a {pw:.0f} mm sheet), "
        f"so it cannot prove a warning is given")
    assert wo.overlap_mm > 0.0


def test_the_overflowing_stamp_is_reported(tab):
    """His case, end to end. MUTATION: put the gate back to `if r.chart_text:`
    and this goes red, which is the state that shipped in beta 8."""
    msgs = _panel_warnings(tab)
    assert msgs, ("the layout stamp runs off the sheet and the message field "
                  "says nothing")


@pytest.mark.parametrize("side", ["left", "right"])
def test_it_does_not_matter_which_side_the_border_is_on(tab, side):
    """*"This happens regardless of the clip-border is on left of right side."*"""
    assert _panel_warnings(tab, clip_side=side), (
        f"nothing is said with the clip border on the {side}")


def test_the_message_names_the_tick_and_not_the_empty_text_box(tab):
    """"Shorten the text" reaches nothing when the box is empty."""
    msgs = _panel_warnings(tab)
    assert msgs, "no message to read"
    assert "Stamp layout summary along the bottom" in msgs[0], (
        "the message does not name the tick that removes the line: " + msgs[0])


def test_a_long_custom_line_is_still_blamed_on_the_text(tab):
    """THE OTHER HALF. When the custom text really is the widest line, the
    stamp sentence would send the reader to switch off the wrong thing."""
    msgs = _panel_warnings(tab, chart_text="X" * 400)
    assert msgs, "a 400-character line does not fit and nothing is said"
    assert "Stamp layout summary along the bottom" not in msgs[0], (
        "the text is what overflows, and the message blames the stamp: "
        + msgs[0])


def test_nothing_is_said_when_both_lines_are_off(tab):
    """A sheet with no bottom text at all must not warn about one."""
    assert not _panel_warnings(tab, stamp_command=False, chart_text="")


def test_the_remedy_names_the_tick_and_not_the_empty_text_box(tab):
    """The same question asked of the helper, so a change of message wording
    cannot quietly take the decision with it."""
    if tab._manual_auto_patches_check is not None:
        tab._manual_auto_patches_check.setChecked(False)
    if tab._manual_f_pw is not None:
        tab._manual_f_pw._control.setValue(_PATCHES)
    assert tab._stamp_is_the_widest_bottom_line(_recipe()) is True
    long_r = _recipe(chart_text="X" * 400)
    assert tab._stamp_is_the_widest_bottom_line(long_r) is False
    assert tab._stamp_is_the_widest_bottom_line(
        _recipe(stamp_command=False, chart_text="X" * 400)) is False


def test_the_predicted_width_is_the_one_the_renderer_draws(tab):
    """The panel and the sheet must measure the same list with the same font."""
    from workflow.layout_engine.raster import sheet_text_width_mm
    from ui.tabs.tab_chart import TabChart
    r = _recipe(chart_text="A CUSTOM LINE")
    lines = tab._bottom_sheet_text_lines(r)
    drawn = sheet_text_width_mm(
        lines, r.chart_text_size_mm, TabChart._DEFAULT_SHEET_TEXT_FONT,
        False, False, float(getattr(r, "dpi", 300) or 300))
    assert tab._sheet_text_width_mm(r) == pytest.approx(drawn, abs=0.05)
