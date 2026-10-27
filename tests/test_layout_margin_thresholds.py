"""Margin thresholds (Preferences > Margin Thresholds) are minimums that are
CHECKED, never applied: the margins asked for are the margins laid out (Knut's
model, #93). The engine once had a clamp that raised margins to the thresholds
(``layout_engine.margins_fit`` and a ``thresholds`` argument of
``instruments.geom_from_build_kwargs``); it was only ever called with nothing
to clamp to and was removed in 4.3.19 (review r1 N8). What stays is the lookup
of a combo's thresholds, which the panel and the inspector use, and the
guarantee that nothing raises a margin (also pinned by
``tests/test_chart_creator_engine.py::test_recipe_margins_always_authoritative_no_clamp``).
"""
from __future__ import annotations

import inspect
from dataclasses import replace
from pathlib import Path

from core.settings import (
    canonical_paper_name,
    margin_combo_key,
    thresholds_for_combo,
)
from workflow.layout_engine import instruments
from workflow.layout_engine.presets import default_recipe


def test_a_small_margin_is_laid_out_as_asked():
    """A 5 mm top margin stays 5 mm although the i1Pro's minimum is larger."""
    r = replace(default_recipe("i1", "A4", mode="clip"), margin_top=5.0,
                use_instrument_margins=True)
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    assert geom.margin_t == 5.0


def test_the_clamp_is_gone_for_good():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "workflow/layout_engine/margins_fit.py").exists()
    assert list(inspect.signature(
        instruments.geom_from_build_kwargs).parameters) == ["kw"]


def test_thresholds_for_combo_resolves_key():
    table = {margin_combo_key("i1Pro", "A4", "Portrait"): {"T": 38, "R": 9}}
    got = thresholds_for_combo(table, "i1", 210.0, 297.0)
    assert got == {"T": 38, "R": 9}
    # landscape page → Landscape key (absent here → None)
    assert thresholds_for_combo(table, "i1", 297.0, 210.0) is None
    # unknown instrument / paper → None
    assert thresholds_for_combo(table, "i1", 999.0, 999.0) is None


def test_canonical_paper_name_tolerant():
    assert canonical_paper_name(210.0, 297.0) == "A4"
    assert canonical_paper_name(297.0, 210.0) == "A4"      # orientation-agnostic
    assert canonical_paper_name(209.0, 298.0) == "A4"      # within tolerance
    assert canonical_paper_name(500.0, 500.0) is None
