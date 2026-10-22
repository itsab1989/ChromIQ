"""The built-in presets' hover tooltip says how the chart is laid out, and it
says it right (agent 14's review, approved by Basti 2026-10-22).

The grid line used to read the recipe's AREA BOX: "{area_cols} patches across
x {area_rows} strips down per sheet". That is the box the layout engine fills,
not the strips it makes, so it was wrong for 181 of the 185 built-in engine
presets (agent 15 built every one of them for real and read the ``.ti2``
back: Knut's 300-patch card has 10 strips of 15 patches, the tooltip said 10
across and 15 down) and for every hexagonal layout. It was also English in
every language and carried an em dash.

Now the line comes from the layout engine's own arithmetic
(`preset_eligibility.predicted_strips`), checked here against real builds.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

GRID = re.compile(r"On (the|each full) sheet: (\d+) strips? of (\d+) patches")


def _engine_presets():
    from ui.tabs.tab_chart import KNUT_PRESETS
    return [p for p in KNUT_PRESETS
            if getattr(p, "layout_recipe", None) and p.group != "Scanner"]


def test_every_built_in_says_its_own_grid(qapp):
    from ui.tabs.tab_chart import TabChart
    from workflow.preset_eligibility import predicted_strips
    presets = _engine_presets()
    assert len(presets) >= 185
    for p in presets:
        tip = TabChart._knut_tooltip(p.key)
        m = GRID.search(tip)
        assert m, (p.key, tip)
        steps, per_page, _t = predicted_strips(dict(p.layout_recipe),
                                               int(p.patches))
        assert (int(m.group(2)), int(m.group(3))) == (per_page[0], steps), p.key
        assert (m.group(1) == "the") == (len(per_page) == 1), p.key
        assert "—" not in tip, p.key
        assert "across" not in tip and "strips down" not in tip, p.key


def test_the_300_patch_card_has_ten_strips_of_fifteen(qapp):
    from ui.tabs.tab_chart import TabChart
    p = next(x for x in _engine_presets() if "_300p_2pages_" in x.key
             and "photo_100x150" in x.key)
    assert "On each full sheet: 10 strips of 15 patches each." in \
        TabChart._knut_tooltip(p.key)


@pytest.mark.parametrize("pick", [
    "photo_100x150mm_300p_2pages",            # Knut's card (the reported one)
    "cr30_a4_450p_1page_portrait_w11_0mm_hexagonal_straight",
    "cr30_letter_390p_1page_portrait_w11_0mm_hexagonal",
    "cm_a4_1623p_8pages_portrait",            # many pages, padding
    "i1_w75_letter_324p_1page_portrait",
])
def test_the_grid_line_is_what_a_real_build_writes(qapp, tmp_path, pick):
    """Built for real, as the presets window and the evenness rows lay a
    preset out (`build_from_recipe` on its bundled patch set): the strip
    length and the first sheet's strips the ``.ti2`` says are the
    tooltip's. Agent 15 ran this over all 185 (tooltip_vs_real_build.py in
    the report folder): 0 wrong, 181 wrong before."""
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    p = next(x for x in _engine_presets() if pick in x.key)
    res, _ = build_from_recipe(str(resource_path(p.ti1_asset)),
                               str(tmp_path / "b"),
                               LayoutRecipe.from_dict(dict(p.layout_recipe)))
    t = Path(res.ti2_path).read_text(encoding="latin-1")
    steps = int(re.search(r'STEPS_IN_PASS "(\d+)"', t).group(1))
    first = int(re.search(r'PASSES_IN_STRIPS2 "(\d+)', t).group(1))
    m = GRID.search(TabChart._knut_tooltip(p.key))
    assert (int(m.group(2)), int(m.group(3))) == (first, steps)


def test_the_tooltip_is_translated(qapp):
    from core import i18n
    from ui.tabs.tab_chart import TabChart
    p = next(x for x in _engine_presets() if "_300p_2pages_" in x.key)
    english = TabChart._knut_tooltip(p.key)
    i18n.set_language("de")
    try:
        german = TabChart._knut_tooltip(p.key)
    finally:
        i18n.set_language("en")
    assert german != english
    assert "10" in german and "15" in german
    assert "Built-in chart" not in german and "On each full sheet" not in german
