"""In "By columns / rows" the strips and patches per strip asked for are KEPT.

Knut, #182 6126438230 (4.3.5-beta.1): the preset "i1Pro · A4-1200p-3pages-
Portrait-w8.5mm-Uniform 9x9x9-Edge Emphasis", in "Prioritise chart area" and
"By columns / rows" at 20 columns and 20 rows, with margins Top 40 / Right 14 /
Bottom 26 / Left 26, printed 19 patches per strip instead of 20; Bottom 25.5
gave 20 again. Top 41 / Right 14 / Bottom 20 / Left 26 gave 19 too, and Bottom
20.5 gave 20. *"height of patches shall always adapt according to the set
columns ("Strips") and rows ("patches per strip") setting"*.

THE CAUSE IS A FLOOR THAT ROUNDS UP. `area_fit` derives the height that fills
the usable length with exactly 20 rows, 10.709999999999999 mm for the first
case, and floors it to 0.01 mm "so rounding can't nudge the patch over the
boundary". But `floor(10.709999999999999 * 100)` is `floor(1071.0)`: the
multiplication rounds up in floating point, so the floor hands back 10.71, and
`geometry.compute` then divides 230.2 by 11.51 and gets 19.999999999999996,
which `int()` makes 19. It happens exactly when the usable length divides
evenly into the rows at 0.01 mm, which is why half a millimetre of margin
either way made it go away.

THE FIX measures the floored size on the very geometry the renderer uses and
steps it down by 0.01 mm until the pinned counts come out
(`area_fit._keep_the_pinned_grid`). A grid no patch of at least 1 mm can hold
is not printed short in silence either: `area_fit.pinned_grid_shortfall`
names it and Create Chart says so in red.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                    # noqa: E402

from workflow.layout_engine import area_fit, papers               # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe, default_recipe  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KNUT_1200 = ROOT / ("assets/charts/knut/rgb/fulllayout/"
                    "fls_i1pro_a4_1200p_3pages_portrait/layout.json")


def _grid(recipe: dict) -> "tuple[int, int]":
    """(strips, patches per strip) the renderer lays out on one page."""
    kw = LayoutRecipe.from_dict(recipe).build_kwargs()
    area_fit._CACHE.clear()
    size = area_fit.derive_area_patch_size(kw)
    assert size is not None
    w, h = papers.dimensions_mm(kw["paper"])
    got = area_fit.realised_grid(kw, w, h, *size)
    assert got is not None
    return got


def _knut(top, right, bottom, left) -> dict:
    rec = json.loads(KNUT_1200.read_text(encoding="utf-8"))
    assert (rec["layout_mode"], rec["area_method"]) == ("area_first", "by_grid")
    assert (rec["area_cols"], rec["area_rows"]) == (20, 20)
    return dict(rec, margin_top=top, margin_right=right,
                margin_bottom=bottom, margin_left=left)


@pytest.mark.parametrize("margins", [
    (40.0, 14.0, 26.0, 26.0),       # Knut: 19 per strip
    (41.0, 14.0, 20.0, 26.0),       # Knut: 19 per strip
    (40.0, 14.0, 25.5, 26.0),       # Knut: 20, the control
    (41.0, 14.0, 20.5, 26.0),       # Knut: 20, the control
    (41.0, 14.0, 21.0, 26.0),       # the preset as he ships it
])
def test_knuts_four_margins_keep_twenty_by_twenty(margins):
    """MUTATION: drop the `_keep_the_pinned_grid` call in
    `_derive_area_patch_size` and the first two go to (20, 19)."""
    assert _grid(_knut(*margins)) == (20, 20)


def test_the_cause_is_the_floor_rounding_up():
    """The arithmetic, pinned so the explanation above stays true."""
    import math
    exact = (297.0 - 40.0 - 26.0 - 0.8) / 20 - 0.8
    floored = math.floor(exact * 100) / 100.0
    assert floored == 10.71 and floored > exact
    assert int((297.0 - 40.0 - 26.0 - 0.8) / (floored + 0.8)) == 19


#: (instrument, paper): the four strip instruments on the three sheets the
#: built-in presets use.
_SHEETS = [(i, p) for i in ("i1", "p3", "CM", "SS")
           for p in ("A4", "Letter", "A3")]
#: Grids the built-ins and Knut's reports use.
_GRIDS = [(20, 20), (22, 26), (24, 27), (12, 27), (11, 14), (17, 12)]


@pytest.mark.parametrize("instrument,paper", _SHEETS)
def test_a_sweep_of_margins_always_keeps_the_grid(instrument, paper):
    """Every margin from 30 to 44.5 mm at the top and 10 to 29.5 mm at the
    bottom in 1.5 mm steps, every grid above: the realised grid is exactly the
    one asked for. Unfixed, this sweep finds 30 grids one row short, on
    US Letter with the i1Pro, the ColorMunki and the SpectroScan."""
    base = default_recipe(instrument, paper).to_dict()
    short = []
    for cols, rows in _GRIDS:
        for t in [x / 2 for x in range(60, 90, 3)]:
            for b in [x / 2 for x in range(20, 60, 3)]:
                rec = dict(base, layout_mode="area_first",
                           area_method="by_grid", area_cols=cols,
                           area_rows=rows, margin_top=t, margin_bottom=b,
                           use_instrument_margins=False)
                got = _grid(rec)
                if got != (cols, rows):
                    short.append((cols, rows, t, b, got))
    assert not short, short[:5]


@pytest.mark.parametrize("bottom", [x / 10 for x in range(150, 300, 5)])
def test_every_half_millimetre_of_bottom_margin_on_knuts_preset(bottom):
    """His own preset, his own top margins, the bottom walked half a
    millimetre at a time across the range he tried."""
    for top in (39.0, 40.0, 41.0):
        assert _grid(_knut(top, 14.0, bottom, 26.0)) == (20, 20), (top, bottom)


def test_a_grid_the_paper_cannot_hold_is_named_not_shrunk_in_silence():
    """300 patches down an A4 strip would need patches under the 1 mm floor.
    That is the one case the count cannot be kept, and it is reported."""
    rec = dict(json.loads(KNUT_1200.read_text(encoding="utf-8")), area_rows=300)
    kw = LayoutRecipe.from_dict(rec).build_kwargs()
    short = area_fit.pinned_grid_shortfall(kw)
    assert short is not None
    cols, rows, got_cols, got_rows = short
    assert (cols, rows, got_cols) == (20, 300, 20) and got_rows < 300


def test_a_grid_that_fits_is_not_reported():
    kw = LayoutRecipe.from_dict(_knut(40.0, 14.0, 26.0, 26.0)).build_kwargs()
    assert area_fit.pinned_grid_shortfall(kw) is None


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


def _notices(tab, rows: int) -> "list[str]":
    from ui.tabs.tab_chart import TabChart
    rec = dict(json.loads(KNUT_1200.read_text(encoding="utf-8")), area_rows=rows)
    tab._manual_layout_panel.set_recipe(LayoutRecipe.from_dict(rec))
    return [w for w in TabChart._engine_text_notes(tab)[1]
            if "By columns / rows" in w]


def test_create_chart_says_so_in_red(tab):
    got = _notices(tab, 300)
    assert len(got) == 1, got
    assert "asks for 20 strips of 300 patches" in got[0]


def test_and_says_nothing_when_the_grid_is_kept(tab):
    assert _notices(tab, 20) == []
