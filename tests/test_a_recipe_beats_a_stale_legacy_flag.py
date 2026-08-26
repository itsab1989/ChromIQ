"""A stale printtarg checkbox must not silently overrule an engine recipe.

`ChartCreator._should_use_engine` refuses the ChromIQ engine when either legacy
printtarg clip flag is set — "Print info in left clip area"
(`chart_left_clip_info`) or the old ChromIQ clip style. `Create Chart` clears
them when the engine TOGGLE MOVES, and only then.

**Presets → Default re-checks "Print info in left clip area" from the saved
setting with the engine already on**, so the toggle never moves and nothing
clears it. Picking a built-in engine preset from that state built a *printtarg*
chart under the preset's name — driven on screen for the ColorMunki A4-84p
chart: 6 strips instead of 7, no clip band, no helper markers, none of the
preset's margins, and a margin panel judging it against the instrument's
defaults instead of the chart's own (#167 follow-up).

A `layout_recipe` is attached by `_collect_manual` only when the engine is on,
so its presence is the user's explicit ask and outranks a leftover checkbox.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.chart_creator import ChartCreator, ChartParams
from workflow.layout_engine.presets import LayoutRecipe


class _Settings:
    def __init__(self, engine: bool = True) -> None:
        self._engine = engine

    def get(self, key, default=None):
        if key == "use_chromiq_layout_engine":
            return self._engine
        return default


def _creator(tmp_path, engine: bool = True) -> ChartCreator:
    class _FM:
        def project(self): raise AssertionError("not needed for this check")
    return ChartCreator(object(), _FM(), _Settings(engine))


def _manual(**kw) -> ChartParams:
    return ChartParams(instrument="CM", paper="A4", is_manual=True, **kw)


def test_a_leftover_left_clip_checkbox_does_not_disable_an_engine_recipe(tmp_path):
    c = _creator(tmp_path)
    recipe = LayoutRecipe(instrument="CM", paper="A4")
    assert c._should_use_engine(_manual(layout_recipe=recipe)), "sanity"
    assert c._should_use_engine(_manual(layout_recipe=recipe, left_clip_info=True)), \
        "an engine recipe must survive a leftover 'Print info in left clip area'"
    assert c._should_use_engine(
        _manual(layout_recipe=recipe, chromiq_clip_style=True)), \
        "an engine recipe must survive a leftover ChromIQ clip style"


def test_without_a_recipe_the_legacy_clip_flags_still_choose_printtarg(tmp_path):
    """The flags keep their meaning on the printtarg path — the fix must not
    turn into 'the engine always wins'."""
    c = _creator(tmp_path)
    assert c._should_use_engine(_manual()), "sanity: engine on, nothing set"
    assert not c._should_use_engine(_manual(left_clip_info=True))
    assert not c._should_use_engine(_manual(chromiq_clip_style=True))


def test_the_engine_toggle_still_governs_manual(tmp_path):
    c = _creator(tmp_path, engine=False)
    recipe = LayoutRecipe(instrument="CM", paper="A4")
    assert not c._should_use_engine(_manual(layout_recipe=recipe)), \
        "engine off in Manual must stay printtarg"
