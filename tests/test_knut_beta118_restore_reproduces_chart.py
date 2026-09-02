"""#130 (Knut, 2026-07-28 and again 2026-08-01): Restore Used Chart must give
back the sheet that was measured.

    *"every time I clicked restore a new random sequence was shown in the
    preview"*

Driving the real app over his four-run ``Test-Profiling-P`` project reproduced
it: every page image changed after a restore. But the ``.ti2`` beside them came
back byte-identical apart from its ``CREATED`` line — so the **patch order was
never wrong**. The shuffle was innocent; the drawing of it was not.

Two causes, both of which made a rebuild draw a different sheet from the same
chart:

1. :meth:`TabChart._current_layout_recipe` overlays the ten strip-indicator
   styling fields from Preferences → Chart Layout on top of the panel's recipe.
   That is deliberate and right for a chart being *made* — the styling is
   app-wide. It is wrong for a chart being *reproduced*. His run was drawn with
   a 4.23 mm indicator; Preferences said "auto", so the rebuild used auto, the
   label band grew from 64 px to 86 px, and every page changed.

2. The record strip prints ``date:``, which the engine stamped as *today*. A
   chart restored a week after it was made came back claiming to have been made
   that day — the paper in your hand and the sheet on screen disagreeing about
   their own history.

The fix keeps the recipe read straight from the chart's sidecar (never the one
the widgets have rounded and Preferences has overlaid) and hands the chart's own
date back to the engine. Verified end to end by
``scripts/drive_restore_seed.py``: a locally built project now restores to
byte-identical page images.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart, _chart_date_from_ti2   # noqa: E402
from workflow.chart_creator import ChartParams                 # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe        # noqa: E402


# --------------------------------------------------------------------------
# 1. The chart's own recipe wins over anything the panel/Preferences hold
# --------------------------------------------------------------------------
def _tab_with_stored(recipe, date=""):
    tab = TabChart.__new__(TabChart)
    tab._restored_exact_recipe = recipe
    tab._restored_chart_date = date
    return tab


def test_stored_recipe_replaces_the_one_preferences_overlaid():
    """THE regression test: the panel's recipe carries the *global* indicator
    styling, the stored one carries the chart's. The rebuild must use the
    chart's, or it redraws a sheet that was never measured."""
    stored = LayoutRecipe(indicator_size_mm=4.23)
    overlaid = LayoutRecipe(indicator_size_mm=0.0)      # 0 = "auto"
    params = ChartParams()
    params.layout_recipe = overlaid

    assert _tab_with_stored(stored).\
        _pin_restored_recipe(params) is True
    assert params.layout_recipe is stored
    assert params.layout_recipe.indicator_size_mm == 4.23


def test_instrument_paper_and_dpi_follow_the_stored_recipe():
    """They are read off the recipe elsewhere in the build, so pinning the
    recipe without them would leave the params disagreeing with it."""
    stored = LayoutRecipe(instrument="CM", paper="A4", dpi=200)
    params = ChartParams()
    params.layout_recipe = LayoutRecipe(instrument="i1", paper="Letter", dpi=300)
    _tab_with_stored(stored)._pin_restored_recipe(params)
    assert (params.instrument, params.paper, params.tiff_dpi) == ("CM", "A4", 200)


def test_a_printtarg_chart_is_left_alone():
    """No recipe means the printtarg path, where there is nothing to pin. It
    must not be handed an engine recipe from whatever was loaded before."""
    params = ChartParams()
    params.layout_recipe = None
    assert _tab_with_stored(LayoutRecipe())._pin_restored_recipe(params) is False
    assert params.layout_recipe is None


def test_no_stored_recipe_leaves_the_params_untouched():
    own = LayoutRecipe(dpi=300)
    params = ChartParams()
    params.layout_recipe = own
    assert _tab_with_stored(None)._pin_restored_recipe(params) is False
    assert params.layout_recipe is own


# --------------------------------------------------------------------------
# 2. The record strip's date
# --------------------------------------------------------------------------
def test_the_stored_date_reaches_the_build():
    params = ChartParams()
    params.layout_recipe = LayoutRecipe()
    _tab_with_stored(LayoutRecipe(), date="2026-07-30")._pin_restored_recipe(params)
    assert params.chart_date == "2026-07-30"


def test_a_new_chart_carries_no_date_so_the_engine_stamps_today():
    """Empty is the signal for "today" — a *new* chart must not inherit the
    date of whichever stored chart was looked at last."""
    assert ChartParams().chart_date == ""


@pytest.mark.parametrize("created,expected", [
    ('CREATED "Thu Jul 30 17:45:54 2026"', "2026-07-30"),
    # A German run writes German month names; only the numbers are parsed.
    ('CREATED "Sa Aug 01 15:39:32 2026"',  "2026-08-01"),
    ('CREATED "Mi Dez 24 08:00:00 2025"',  "2025-12-24"),
    ('CREATED "2026-03-09"',               "2026-03-09"),
    # Unusable input must yield "" so the caller stamps today. An invented date
    # would be worse than an honest current one.
    ('CREATED "sometime last week"',       ""),
    ('CREATED "Thu Xxx 30 17:45:54 2026"', ""),
    ('CREATED "Thu Feb 31 00:00:00 2026"', ""),      # not a real day
    ('NO_SUCH_KEYWORD "x"',                ""),
])
def test_chart_date_read_from_the_ti2_header(tmp_path, created, expected):
    """Every project already on disk predates the saved date, so the ``.ti2``
    header is the only record of when the chart was made."""
    ti2 = tmp_path / "c.ti2"
    ti2.write_text(f'CTI2\n\n{created}\n\nKEYWORD "x"\n', encoding="utf-8")
    assert _chart_date_from_ti2(ti2) == expected


def test_a_missing_ti2_is_not_an_error():
    assert _chart_date_from_ti2(Path("/nonexistent/none.ti2")) == ""


# --------------------------------------------------------------------------
# 3. The engine draws the date it is given, and saves it with the chart
# --------------------------------------------------------------------------
def test_build_chart_accepts_a_chart_date():
    """Pins the parameter's existence and its default. Without a default of ""
    every existing caller would start stamping the empty string."""
    import inspect

    from workflow.layout_engine import chart as le_chart
    sig = inspect.signature(le_chart.build_chart)
    assert sig.parameters["chart_date"].default == ""


def test_the_engine_kwargs_carry_the_date_on_the_recipe_path():
    """The restore path builds from a recipe, so this is the branch that
    matters — the other one would have left the date behind."""
    from workflow.chart_creator import ChartCreator

    c = ChartCreator.__new__(ChartCreator)
    params = ChartParams()
    params.layout_recipe = LayoutRecipe()
    params.chart_date = "2026-07-30"
    params.target_name = "Demo"
    assert c._engine_kwargs(params)["chart_date"] == "2026-07-30"


def test_the_date_is_saved_with_the_chart(tmp_path):
    """So the NEXT restore reproduces it without falling back to the header."""
    from workflow.chart_creator import ChartCreator

    @dataclass
    class _Result:
        seed: int = 7
        color_rep: str = "RGB"
        chart_date: str = "2026-07-30"

    sidecar = tmp_path / "c.channels.json"
    sidecar.write_text("{}", encoding="utf-8")
    params = ChartParams()
    params.layout_recipe = LayoutRecipe()
    ChartCreator._embed_layout_geometry(
        ChartCreator.__new__(ChartCreator), tmp_path, "c", _Result(), params)
    assert json.loads(sidecar.read_text(encoding="utf-8"))["layout"]["date"] == "2026-07-30"


# --------------------------------------------------------------------------
# 4. The two halves must not drift apart again
# --------------------------------------------------------------------------
def test_the_restore_path_pins_the_recipe():
    """A rebuild that collects params and forgets to pin them is exactly the
    bug this file is about, and it is invisible in a unit test of either half."""
    import inspect

    src = inspect.getsource(TabChart.rebuild_verification_pages)
    assert "_pin_restored_recipe" in src
    assert src.index("_collect_params") < src.index("_pin_restored_recipe"), \
        "the recipe must be pinned AFTER the params are collected, or the " \
        "collect overwrites it again"


def test_restoring_settings_forgets_the_previous_chart(tmp_path):
    """A chart with no recipe must not be rebuilt with the last one's layout.
    The reset lives at the top of the method so even its early returns clear
    it."""
    import inspect

    src = inspect.getsource(TabChart._restore_chart_settings)
    body = src.split("\n")
    reset = next(i for i, ln in enumerate(body)
                 if "_restored_exact_recipe = None" in ln)
    first_return = next(i for i, ln in enumerate(body) if "return False" in ln)
    assert reset < first_return
