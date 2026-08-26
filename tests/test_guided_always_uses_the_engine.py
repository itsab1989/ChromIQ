"""Guided mode always lays out with the ChromIQ engine. Never printtarg.

Sebastian, 2026-08-26: *"guided is usually using the engine right? and it at
least should never use printtarg."*

`be85d7e5` (#93) made Guided engine-only — the engine reproduces printtarg's
Guided geometry for every instrument, paper and option (161/161 parity). But it
added `if not params.is_manual: return True` BELOW a clip-flag check that was
already there, so a Guided chart with `left_clip_info` or `chromiq_clip_style`
set silently fell back to printtarg. The flag is global, written only by
Manual's "Save as defaults", and Guided has no control for it — so ticking a box
in one tab permanently changed another tab's output, invisibly.

Worse, the Guided screen never consulted those flags: it displayed "ChromIQ
layout engine" and predicted the engine's patch count while printtarg built the
sheet, so the number on screen could differ from the number handed to targen.

The stamp guards are tested here too. They protect printtarg-era post-processing
from running on an engine chart, and they used to ask "does it carry a
`layout_recipe`?" — which a GUIDED chart never does. Reordering alone therefore
exposed them: measured, 5,942,676 px rewritten and 5,529,055 inked px destroyed
on one sheet. The predicate must be "is this an engine chart".
"""
from __future__ import annotations

import pytest

from workflow.chart_creator import ChartCreator, ChartParams, ENGINE_INSTRUMENTS


class _Settings:
    """Manual's engine toggle OFF — the setting Guided must ignore."""

    def __init__(self, **kw):
        self._d = {"use_chromiq_layout_engine": False, **kw}

    def get(self, key, default=None):
        return self._d.get(key, default)


def _creator(**settings):
    c = ChartCreator.__new__(ChartCreator)
    c._settings = _Settings(**settings)
    return c


def _params(*, is_manual, **kw):
    p = ChartParams()
    p.instrument = "i1"
    p.is_manual = is_manual
    p.left_clip_info = kw.get("left_clip_info", False)
    p.chromiq_clip_style = kw.get("chromiq_clip_style", False)
    p.layout_recipe = kw.get("layout_recipe", None)
    return p


@pytest.mark.parametrize("left_clip_info,chromiq_clip_style", [
    (False, False), (True, False), (False, True), (True, True),
])
def test_guided_uses_the_engine_whatever_the_clip_flags_say(
        left_clip_info, chromiq_clip_style):
    """No flag may drop Guided onto printtarg. This is the whole rule."""
    c = _creator()
    p = _params(is_manual=False, left_clip_info=left_clip_info,
                chromiq_clip_style=chromiq_clip_style)
    assert c._should_use_engine(p) is True, (
        f"Guided fell back to printtarg with left_clip_info={left_clip_info}, "
        f"chromiq_clip_style={chromiq_clip_style} — a Guided chart must always "
        "be laid out by the engine")


def test_manual_still_honours_the_clip_flags():
    """THE CONTROL. Without this, "always return True" would pass the test above.

    Manual is where those printtarg-era flags still mean something: a chart with
    no engine recipe and a clip flag set belongs on the printtarg path.
    """
    c = _creator()
    assert c._should_use_engine(
        _params(is_manual=True, left_clip_info=True)) is False
    assert c._should_use_engine(
        _params(is_manual=True, chromiq_clip_style=True)) is False


def test_a_manual_engine_recipe_still_outranks_a_stale_flag():
    """#168 must survive this change — the two rules are independent.

    Note what the recipe does and does not do: it stops a stale clip flag from
    VETOING the engine, but Manual still asks its own engine toggle afterwards.
    A recipe is only ever attached while that toggle is on, so this is the real
    combination. (An earlier version of this test left the toggle off and
    expected True — the code was right and the test was wrong.)
    """
    c = _creator(use_chromiq_layout_engine=True)
    p = _params(is_manual=True, left_clip_info=True, layout_recipe={"cols": 21})
    assert c._should_use_engine(p) is True

    # …and with the toggle off, Manual stays on printtarg even with a recipe.
    assert _creator()._should_use_engine(
        _params(is_manual=True, left_clip_info=True,
                layout_recipe={"cols": 21})) is False


def test_an_unsupported_instrument_never_reaches_the_engine():
    """The instrument gate stays first — Guided cannot force an engine that
    does not support the device."""
    c = _creator()
    p = _params(is_manual=False)
    p.instrument = "__not_an_engine_instrument__"
    assert p.instrument not in ENGINE_INSTRUMENTS
    assert c._should_use_engine(p) is False


def test_the_printtarg_stamps_ask_whether_it_is_an_engine_chart():
    """The stamp guards must not key off `layout_recipe`.

    A GUIDED chart carries no recipe, so a recipe-based guard does not protect
    it. Reordering without fixing this put printtarg's clip stamp on top of the
    engine's own band — 5.5 million inked pixels destroyed on one sheet.
    """
    import inspect
    src = inspect.getsource(ChartCreator._stamp_tiff_metadata)
    assert "engine_chart" in src, (
        "the stamp path no longer asks whether this is an engine chart")
    # both printtarg-era stamps gated on it, not on the recipe
    assert src.count("engine_chart") >= 3, (
        "only some of the printtarg-era stamp paths are gated on engine_chart")
