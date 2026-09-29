"""A Guided build is logged with what Guided built, not with the Manual panel.
Beta 42 challenge, item 3 (2026-09-24).

Driven on screen: a ColorMunki preset loaded in Manual (area-first, High,
12x12 grid, margins T34 R24 B18 L14), then Generate Chart in Guided, which
built patch-first, density 1, 6 mm on every side. The build log said:

    chart build (Generate Chart) in guided: patch set targen | manual panel:
    CM, A4, area_first, density 2, 12x12 grid, margins T34.0 R24.0 B18.0 L14.0

`_log_chart_build` read the Manual panel whatever built the chart. In Guided
it now describes Guided's own recipe (what `_engine_build_kwargs` hands the
engine), labelled "guided".

MUTATION: make `_log_chart_build` read the Manual panel in Guided again
(`if mode == "guided":` -> `if False:`) and this goes red.
"""
import logging
import os
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.chart_creator import ChartCreator, ChartParams
from workflow.layout_engine.presets import LayoutRecipe


def _line(caplog, mode, params, panel_recipe):
    from ui.tabs.tab_chart import TabChart
    creator = ChartCreator.__new__(ChartCreator)
    fake = types.SimpleNamespace(
        _manual_layout_panel=types.SimpleNamespace(get_recipe=lambda: panel_recipe),
        _current_mode=lambda: mode,
        _collect_guided=lambda: params,
        _creator=creator)
    with caplog.at_level(logging.INFO, logger="ui.tabs.tab_chart"):
        TabChart._log_chart_build(fake, "Generate Chart", "targen")
    lines = [r.getMessage() for r in caplog.records
             if "chart build (Generate Chart)" in r.getMessage()]
    assert lines, "no build line was logged"
    return lines


def _manual_preset():
    r = LayoutRecipe(instrument="CM", paper="A4", cm_density=2,
                     layout_mode="area_first", area_method="by_grid",
                     area_cols=12, area_rows=12, layout_explicit=True)
    (r.margin_top, r.margin_right, r.margin_bottom, r.margin_left) = \
        (34.0, 24.0, 18.0, 14.0)
    return r


def test_a_guided_build_is_logged_with_guideds_own_recipe(caplog):
    guided = ChartParams(instrument="CM", paper="A4", margin_mm=6.0)
    lines = _line(caplog, "guided", guided, _manual_preset())
    first = lines[0]
    assert "manual panel" not in first, first
    assert "| guided: CM, A4, patch_first, density 1" in first, first
    assert "12x12" not in first and "area_first" not in first, first
    assert "margins T6.0 R6.0 B6.0 L6.0" in first, first
    assert "T34.0" not in first, first


def test_guided_extra_high_is_logged_as_density_3_at_its_own_margin(caplog):
    guided = ChartParams(instrument="CM", paper="A4", triple_density=True,
                         margin_mm=5.0, patch_scale=1.3)
    first = _line(caplog, "guided", guided, _manual_preset())[0]
    assert "density 3" in first and "margins T5.0 R5.0 B5.0 L5.0" in first, first


def test_a_manual_build_is_still_logged_with_the_manual_panel(caplog):
    first = _line(caplog, "manual", ChartParams(), _manual_preset())[0]
    assert "| manual panel: CM, A4, area_first, density 2, 12x12 grid" in first
    assert "margins T34.0 R24.0 B18.0 L14.0" in first, first
