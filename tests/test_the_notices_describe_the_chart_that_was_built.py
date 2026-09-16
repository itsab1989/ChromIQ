"""Every notice on the frame describes the sheet on screen and on disk.

**FOUR ROUTES RECOMPUTED THEM FROM THE LIVE BOXES AGAINST THE OLD SHEET.**
`_update_margin_inspector` re-measures the chart's own TIFFs and then asked
`_current_layout_recipe()` — the widgets — for everything else, and four callers
reach it with no build in between: a page turn, either of the two guide tick
boxes on the frame itself, and the Preferences round trip.

Driven on screen on beta 18
(`~/Desktop/ChromIQ-beta18-proof/knut-sweep-preview-truth/`,
`R11-3-HEADLINE-size-36pt-no-red-line-notice-says-6pt.png`). One page, one
sheet, the TIFF's SHA-256 identical at every step:

| step | Size box | the red "press Generate Chart" line | the notice |
|---|---|---|---|
| after the build | 36 pt | absent | true of the sheet |
| type 6 pt | 6 pt | shown | unchanged, correct |
| tick a guide box | 6 pt | shown | **recomputed at 6 pt against a 36 pt sheet** |
| type 36 pt back | 36 pt | **gone** | **still the 6 pt notice** |

The last row is the state nobody can read: the boxes match the chart, the chart
matches the disk, the red line is correctly absent, and the red notice describes
a sheet that was never generated.

So the recipe comes from the chart's own `channels.json`, which
`ChartCreator._embed_layout_geometry` writes with every build and which
`_restore_chart_settings` already trusts for exactly this reason.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from ui.tabs.tab_chart import TabChart                          # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe         # noqa: E402


class _Settings:
    def get(self, key, default=None):
        return True if key == "use_chromiq_layout_engine" else default

    def apply_indicator_style(self, r):
        return r


class _Tab:
    """A tab that holds a live recipe and a chart on disk."""

    _settings = _Settings()
    _manual_layout_panel = object()

    def __init__(self, live, ti2):
        self._live = live
        self._margin_ti2 = ti2
        self._margin_tiffs = []

    def _current_mode(self):
        return "manual"

    def _current_layout_recipe(self):
        return self._live


def _built_chart(tmp_path: Path, recipe: LayoutRecipe) -> Path:
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("NUMBER_OF_SETS 4\n", encoding="utf-8")
    (tmp_path / "chart.channels.json").write_text(
        json.dumps({"layout": {"dpi": recipe.dpi, "recipe": recipe.to_dict()}}),
        encoding="utf-8")
    return ti2


def _live_and_built(tmp_path):
    built = LayoutRecipe()
    built.instrument, built.paper, built.dpi = "i1", "A4", 300
    built.chart_text = "ChromIQ preview truth"
    built.chart_text_size_mm = 36.0 * 25.4 / 72.0
    ti2 = _built_chart(tmp_path, built)
    return built, ti2


def test_the_notice_recipe_comes_from_the_chart_and_not_from_the_boxes(tmp_path):
    """The headline state: the Size box says 6 pt, the sheet was built at 36.

    MUTATION: call `_current_layout_recipe()` in `_engine_text_notes` again and
    this goes red.
    """
    built, ti2 = _live_and_built(tmp_path)
    typed = replace(built, chart_text_size_mm=6.0 * 25.4 / 72.0)
    tab = _Tab(typed, ti2)
    got = TabChart._notice_layout_recipe(tab)
    assert got is not None
    assert got.chart_text_size_mm == pytest.approx(built.chart_text_size_mm), (
        "the notices would be recomputed at the size in the box against a "
        "sheet built at another size")


def test_typing_a_box_and_typing_it_back_changes_nothing(tmp_path):
    """The step that produced a false notice with NO red line beside it."""
    built, ti2 = _live_and_built(tmp_path)
    tab = _Tab(built, ti2)
    a = TabChart._notice_layout_recipe(tab).to_dict()
    tab._live = replace(built, chart_text_size_mm=6.0 * 25.4 / 72.0)
    b = TabChart._notice_layout_recipe(tab).to_dict()
    tab._live = built
    c = TabChart._notice_layout_recipe(tab).to_dict()
    assert a == b == c, "the notice recipe followed the boxes"


def test_the_recipe_is_re_read_when_the_chart_is_rebuilt(tmp_path):
    """A cache on the sidecar must not become the fault it was fixing.

    MUTATION: key the cache on the sidecar PATH and this goes red.
    """
    built, ti2 = _live_and_built(tmp_path)
    tab = _Tab(built, ti2)
    assert TabChart._notice_layout_recipe(tab).chart_text == \
        "ChromIQ preview truth"
    again = replace(built, chart_text="a second chart entirely")
    _built_chart(tmp_path, again)
    assert TabChart._notice_layout_recipe(tab).chart_text == \
        "a second chart entirely", (
        "the recipe was cached on the chart's NAME, so a rebuild into the "
        "same run kept the old one")


def test_a_chart_with_no_sidecar_still_judges_the_boxes(tmp_path):
    """A printtarg chart records no recipe, and a chart nobody has built yet
    has no sidecar at all. Both must keep working off the live panel rather
    than going silent."""
    built, _ti2 = _live_and_built(tmp_path)
    bare = tmp_path / "printtarg.ti2"
    bare.write_text("NUMBER_OF_SETS 4\n", encoding="utf-8")
    tab = _Tab(built, bare)
    assert TabChart._notice_layout_recipe(tab) is built
    tab._margin_ti2 = None
    assert TabChart._notice_layout_recipe(tab) is built


def test_the_notices_themselves_follow_the_built_recipe(tmp_path):
    """End to end, through the method the panel really calls.

    A sheet built with a 36 pt bottom line, the box typed down to 6 pt: the
    notice must still be the 36 pt one.
    """
    from tests.margin_reports import report_for
    built = LayoutRecipe()
    built.instrument, built.paper, built.dpi = "i1", "A4", 300
    built.use_instrument_margins = False
    built.margin_top = built.margin_left = built.margin_right = 12.0
    built.margin_bottom = 6.0
    built.chart_text = "ChromIQ preview truth"
    built.chart_text_size_mm = 36.0 * 25.4 / 72.0
    ti2 = _built_chart(tmp_path, built)
    tab = _Tab(replace(built, chart_text_size_mm=6.0 * 25.4 / 72.0), ti2)
    tab._manual_chart_notes_edit = type("E", (), {"text": lambda s: ""})()
    tab._manual_stamp_cmd_check = type("B", (), {"isChecked": lambda s: False})()
    _warns, over = TabChart._engine_text_notes(tab, report_for(built))
    typed_only = _Tab(replace(built, chart_text_size_mm=6.0 * 25.4 / 72.0),
                      None)
    typed_only._manual_chart_notes_edit = tab._manual_chart_notes_edit
    typed_only._manual_stamp_cmd_check = tab._manual_stamp_cmd_check
    _w2, over_typed = TabChart._engine_text_notes(typed_only, report_for(built))
    assert over != over_typed, (
        "the notice computed from the chart is the same as the one computed "
        "from the 6 pt boxes, so this test cannot see the fault it is for")
