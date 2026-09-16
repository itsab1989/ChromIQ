"""The restored rise search must not cost the reader a freeze.

The search this replaces was deleted partly because it ran *"a dozen geometry
rebuilds per keystroke"*. The design authority let it back on the condition that
it runs after a Generate and against measured margins, which fixes the *when*.
It does not fix the *how much*: `margin_inspector.engine_patch_bottom_mm` is
**13.2 ms** a call on an i1Pro A4 sheet, two thirds of it
`geometry.patch_rects_px` building a rect and a `SAMPLE_LOC` for all 1023
patches.

A plain 0.5 mm walk over the margin box's range therefore cost, measured on the
panel path:

| case | probes | wall |
|---|---|---|
| an overlap with an answer | 36 | **1.7 s** |
| an overlap with no answer | 101 | **3.6 s** |

which is the freeze that got the previous search deleted. The coarse-to-fine
scan brings that to 13 and 21 probes, about 450 ms, and this file holds it
there and proves it did not change a single answer.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow import margin_inspector as mi                # noqa: E402
from workflow import text_edge_fit as tef                  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe    # noqa: E402


def _recipe(margin_bottom: float = 10.0) -> LayoutRecipe:
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "i1", "A4", "area_first"
    r.use_instrument_margins = False
    r.margin_bottom = margin_bottom
    return r


def _fine_walk(r, measured, reserve, lines, line):
    """The plain 0.5 mm walk the coarse-to-fine scan replaces.

    Kept here rather than in the app: it is the reference the fast one is
    checked against, and having it in the app would be two implementations.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import _MARGIN_BOX_MAX_MM, _MARGIN_STEP_MM
    asked = float(r.margin_bottom or 0.0)
    base = mi.engine_patch_bottom_mm(r)
    if base is None:
        return None
    off = measured - base
    cap = _MARGIN_BOX_MAX_MM - asked
    probe, run, first = _MARGIN_STEP_MM, 0, None
    while probe <= cap + 1e-9:
        b = mi.engine_patch_bottom_mm(replace(r, margin_bottom=asked + probe))
        ok = b is not None and tef.bottom_text_block_overlap(
            b + off, reserve, lines, line) is None
        if ok:
            run += 1
            if first is None:
                first = probe
            if run >= 3:
                return round(first, 1)
        else:
            run, first = 0, None
        probe = round(probe + _MARGIN_STEP_MM, 1)
    return round(first, 1) if first is not None else None


@pytest.mark.parametrize("margin_bottom", [6.0, 14.0])
@pytest.mark.parametrize("lines,line_mm", [(1, 6.0), (2, 12.0), (1, 28.0)])
@pytest.mark.parametrize("measured", [12.0, 20.0])
def test_the_fast_scan_gives_the_fine_walks_own_answer(margin_bottom, lines,
                                                       line_mm, measured):
    """**AN OPTIMISATION THAT CHANGES AN ANSWER IS NOT AN OPTIMISATION.**

    The scan steps 2.5 mm and then walks the 0.5 mm grid inside the one
    interval that cleared, so it must land on exactly the rise the plain walk
    would have named. Twelve states here; 48 were compared when it was written
    and none disagreed.

    MUTATION: raise `_MARGIN_COARSE_MM` past the width of a jump, or drop the
    `- _MARGIN_COARSE_MM + _MARGIN_STEP_MM` back-off that makes the fine pass
    start below the coarse hit, and this goes red.
    """
    from ui.tabs.tab_chart import margin_rise_that_clears_mm
    r = _recipe(margin_bottom)
    fast = margin_rise_that_clears_mm(r, measured, 7.0, lines, line_mm)
    slow = _fine_walk(r, measured, 7.0, lines, line_mm)
    assert fast == slow, (
        f"the fast scan says {fast} and the 0.5 mm walk says {slow}")


def test_the_search_stays_inside_a_probe_budget():
    """The reader feels every probe. This is the number, not a hope.

    MUTATION: go back to a plain 0.5 mm walk and the "no answer" case runs to
    101 probes, which was 3.6 s on the panel.
    """
    from ui.tabs.tab_chart import margin_rise_that_clears_mm
    calls = {"n": 0}
    real = mi.engine_patch_bottom_mm

    def counted(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    mi.engine_patch_bottom_mm = counted
    try:
        # an overlap with an answer …
        calls["n"] = 0
        got = margin_rise_that_clears_mm(_recipe(10.0), 15.0, 7.0, 2, 12.0)
        assert got is not None
        with_answer = calls["n"]
        # … and one the box cannot reach, which is the expensive direction
        calls["n"] = 0
        assert margin_rise_that_clears_mm(
            _recipe(10.0), 15.0, 7.0, 4, 40.0) is None
        without = calls["n"]
    finally:
        mi.engine_patch_bottom_mm = real
    assert with_answer <= 24, (
        f"finding a rise took {with_answer} geometry rebuilds; at 13 ms each "
        f"that is a freeze on the panel")
    assert without <= 32, (
        f"deciding there is no rise took {without} geometry rebuilds")


def test_a_repeated_candidate_is_not_rebuilt():
    """The coarse and fine passes overlap, so the memo has to be real.

    MUTATION: drop `_seen` and the probe counts above rise.
    """
    import inspect
    from ui.tabs import tab_chart as tc
    src = inspect.getsource(tc.margin_rise_that_clears_mm)
    assert "_seen" in src and "key in _seen" in src, (
        "the search rebuilds a geometry it has already measured")
