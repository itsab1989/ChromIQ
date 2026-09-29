"""B8-963 / B8-964: what a ColorMunki density change may do to the margins,
and what the build log says about the grid.

B8-963. With "Use instrument margins" ticked the four margin boxes are locked
(disabled, tooltip "Locked to your instrument's minimum margins"). Picking
"Extra-high density" wrote 5 mm into those locked boxes anyway, so the chart
was built at 5 mm while the tick still promised the instrument's margins.
Driven on screen 2026-09-24 (A3+ 616p ColorMunki preset): margins 33/6/10/6
with the tick on, Extra-high -> 5/5/5/5 with the tick STILL on, strip
283.5 mm -> 316.6 mm.

The unlocked case keeps Sebastian's #93 rule (Extra-high seeds Guided's 5 mm
margins) for margins still at their default; since B8-965 (Basti, 2026-09-24)
a preset's or typed margins are left alone, see
tests/test_extra_high_seeds_only_default_margins.py.

B8-964. The build log printed the AREA grid (columns x rows) whatever the
layout mode, so a patch-first chart of 32 strips of 15 was logged as
"44x14 grid" at every density.
"""
import logging
import os
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from workflow.layout_engine.presets import LayoutRecipe

THR = {"T": 33.0, "R": 6.0, "B": 10.0, "L": 6.0}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _cm_panel(margins=(34.0, 24.0, 18.0, 14.0)):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    p.set_threshold_lookup(lambda inst, paper: dict(THR))
    r = LayoutRecipe(instrument="CM", paper="483x329", cm_density=2,
                     layout_mode="area_first", area_method="by_grid",
                     area_cols=44, area_rows=14,
                     use_instrument_margins=False)
    (r.margin_top, r.margin_right, r.margin_bottom, r.margin_left) = margins
    p.set_recipe(r)
    return p


def _margins(p):
    return [p.margins[k].value() for k in ("t", "r", "b", "l")]


def test_extra_high_does_not_write_into_locked_instrument_margins(app):
    p = _cm_panel()
    p.use_instr_margins.setChecked(True)
    assert _margins(p) == [33.0, 6.0, 10.0, 6.0]
    p.mode.setCurrentIndex(p.mode.findData("extrahigh"))
    # The boxes are still locked and still hold the instrument's margins...
    assert p.use_instr_margins.isChecked()
    assert not p.margins["t"].isEnabled()
    assert _margins(p) == [33.0, 6.0, 10.0, 6.0]
    # ...and so does the recipe the build is handed.
    r = p.get_recipe()
    assert (r.margin_top, r.margin_right, r.margin_bottom, r.margin_left) \
        == (33.0, 6.0, 10.0, 6.0)
    assert r.cm_density == 3
    # Unticking still gives back what was typed before the tick.
    p.use_instr_margins.setChecked(False)
    assert _margins(p) == [34.0, 24.0, 18.0, 14.0]


def test_unlocked_extra_high_still_seeds_guideds_margins(app):
    """#93 (Sebastian): unchanged by B8-963, for margins still at their
    default. A preset's or typed margins are kept since B8-965 (Basti,
    2026-09-24): tests/test_extra_high_seeds_only_default_margins.py."""
    p = _cm_panel(margins=(6.0, 6.0, 6.0, 6.0))
    assert not p.use_instr_margins.isChecked()
    p.mode.setCurrentIndex(p.mode.findData("extrahigh"))
    assert _margins(p) == [5.0, 5.0, 5.0, 5.0]


def _log_line(caplog, rec: LayoutRecipe) -> str:
    from ui.tabs.tab_chart import TabChart
    fake = types.SimpleNamespace(
        _manual_layout_panel=types.SimpleNamespace(get_recipe=lambda: rec),
        _current_mode=lambda: "manual")
    with caplog.at_level(logging.INFO, logger="ui.tabs.tab_chart"):
        TabChart._log_chart_build(fake, "live preview", "x.ti1")
    lines = [r.getMessage() for r in caplog.records
             if "chart build (live preview)" in r.getMessage()]
    assert lines, "no build line was logged"
    return lines[-1]


def test_the_build_log_names_the_grid_only_where_it_is_used(caplog):
    rec = LayoutRecipe(instrument="CM", paper="483x329", cm_density=2,
                       layout_mode="patch_first", area_method="by_grid",
                       area_cols=44, area_rows=14)
    line = _log_line(caplog, rec)
    assert "44x14" not in line, line
    assert "patch_first" in line and "density 2" in line, line
    caplog.clear()
    rec.layout_mode = "area_first"
    rec.cm_density = 3
    line = _log_line(caplog, rec)
    assert "44x14 grid" in line and "area_first" in line, line
    assert "density 3" in line, line
