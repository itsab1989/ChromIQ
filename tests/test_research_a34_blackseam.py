"""Agent 34 (2026-10-06): research token ``a34-blackseam``.

Three parts, all inert without the token (Findings agent34-01):

1. the deep black of the a29 hand-over is chosen by depth bought per C* of
   tint (``rate_deep_black``), bounded by the printer's own darkest measured
   near-neutral patches (``measured_dark_chroma``), instead of a fixed C* 2;
2. rows of the neutral walk that did not solve neutral are filled along
   their separation branch (``fill_axis_gaps``), so no neutral column node
   falls back to its own per-node inversion;
3. the a29-oog-darkmono clip floor stays at the NEUTRAL black when the
   column is handed over to a deeper, tinted black.

No file IO here (the encoding rule of tests/test_encoding_is_named.py has
nothing to check in this file).
"""
from __future__ import annotations

import inspect

import numpy as np
import pytest

from tests.test_research_a29_blackhandover import _KW, _ToyCmyk
from workflow.profile_engine import b2a, builder
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates,
                                             candidates_from_env,
                                             darkmono_clip_floor)

TOKEN = "a34-blackseam"
VARIANTS = ("a34-blackseam-pin", "a34-blackseam-deepfloor")


def test_a34_blackseam_is_default_and_its_variants_are_not():
    # Agent 35 made a34-blackseam a Maximum accuracy default (Agent 34's
    # verdict, Findings/agent34-01 s5.4); -pin and -deepfloor stay opt-in.
    assert TOKEN in ENGINE_CANDIDATE_TOKENS
    assert TOKEN in ACCURATE_DEFAULT_TOKENS
    assert TOKEN in accurate_candidates(frozenset())
    assert "no-" + TOKEN in ENGINE_CANDIDATE_TOKENS
    assert TOKEN not in accurate_candidates({"no-" + TOKEN})
    for tok in VARIANTS:
        assert tok in ENGINE_CANDIDATE_TOKENS
        assert tok not in ACCURATE_DEFAULT_TOKENS
        assert tok not in accurate_candidates(frozenset())
        assert tok in accurate_candidates({tok})
    both = candidates_from_env(f"{TOKEN},a29-oog-darkmono-floor")
    assert TOKEN in both and "a29-oog-darkmono-floor" in both


def _rung(l_star, c_star):
    """(model Lab, device) of a ladder rung with chroma ``c_star``."""
    return (np.array([l_star, c_star, 0.0]), np.array([0.1, 0.1, 0.0, 1.0]))


def test_the_rate_rule_takes_the_rung_that_buys_the_most_depth_per_chroma():
    # i1iSis-like (measured on the captured model, Findings s3): C* <= 2
    # finds nothing, C* 2.5 buys 1.1 L* per C*, C* 3 buys 1.55 from the
    # neutral black, C* 4 / 5 then add 0.1 L* for 0.2 C* (0.5 per C*).
    cands = [None, None, None, _rung(18.27, 2.44), _rung(16.61, 2.83),
             _rung(16.51, 3.02), _rung(16.50, 3.04)]
    out = b2a.rate_deep_black(None, l_neutral=21.0, c_neutral=0.0, kw={},
                              candidates=cands)
    assert out["chroma_max"] == 3.0
    assert out["lab"][0] == pytest.approx(16.61)


def test_a_tint_that_buys_less_than_one_l_star_per_c_star_is_refused():
    # XKB pessimistic t400-like: the first rung pays (1.06 L* per C*), every
    # further one buys 0.2-0.5 L* per C* (the a29 cap of 2 took 7.73 / C*
    # 1.63, which the proxy printed at C* 1.62 vs colprof's 1.15).
    cands = [_rung(8.15, 0.80), _rung(7.94, 1.38), _rung(7.73, 1.63),
             _rung(7.53, 2.02), _rung(7.32, 2.42), _rung(7.20, 3.25),
             _rung(7.07, 4.00)]
    out = b2a.rate_deep_black(None, l_neutral=9.0, c_neutral=0.0, kw={},
                              candidates=cands)
    assert out["chroma_max"] == 1.0
    # SWOP C5-like: no rung buys an L* per C*; no hand-over at all
    cands = [_rung(12.80, 0.92), _rung(12.70, 1.32), _rung(12.59, 1.73),
             _rung(12.50, 2.12), _rung(12.40, 2.49), _rung(12.19, 3.31),
             _rung(11.98, 4.15)]
    assert b2a.rate_deep_black(None, l_neutral=13.09, c_neutral=0.01, kw={},
                               candidates=cands) is None


def test_the_measured_bound_removes_rungs_above_it():
    seen = []

    def fake_deepest(model, *, chroma_max, kw):
        seen.append(chroma_max)
        return _rung(20.0 - chroma_max, chroma_max * 0.9)

    orig = b2a.deepest_tinted
    b2a.deepest_tinted = fake_deepest
    try:
        out = b2a.rate_deep_black(None, l_neutral=21.0, c_neutral=0.0,
                                  kw={}, max_chroma=2.2)
    finally:
        b2a.deepest_tinted = orig
    assert seen == [1.0, 1.5, 2.0]
    assert out["chroma_max"] <= 2.0


def test_measured_dark_chroma_reads_the_darkest_near_neutral_patches():
    lab = np.array([[10.0, 8.0, 0.0],      # darkest, but chromatic (C* 8)
                    [12.0, 2.0, 0.0],
                    [13.0, 0.0, 3.0],
                    [14.0, 1.0, 0.0],
                    [11.0, 0.5, 0.0],      # over the ink limit
                    [50.0, 0.0, 0.0]])
    dev = np.array([[1, 1, 0, 1], [.5, .5, .5, 1], [.5, .5, .5, 1],
                    [.4, .4, .4, 1], [1, 1, 1, 1], [0, 0, 0, .3]], float)
    c = b2a.measured_dark_chroma(lab, dev, ink_limit=300.0)
    assert c == pytest.approx(2.0)          # median of 2.0, 3.0, 1.0
    assert b2a.measured_dark_chroma(lab[:1], dev[:1]) is None


class _TwoBranch:
    """L* falls linearly with the row index along the axis; a* is 0 on
    the device line the stub's axis uses."""

    n_channels = 4

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        L = 100.0 - 75.0 * d[:, 3] - 10.0 * d[:, :3].sum(1)
        return np.column_stack([L, np.zeros(len(d)), np.zeros(len(d))])


def _stub_axis():
    ls = np.arange(100.0, 19.9, -0.5)
    dev = np.zeros((len(ls), 4))
    dev[:, 3] = np.clip((100.0 - ls) / 75.0, 0, 1)   # K-only branch: L exact
    ok = np.ones(len(ls), bool)
    return {"l": ls, "dev": dev, "ok": ok, "l_black": 25.0,
            "black": dev[np.argmin(np.abs(ls - 25.0))].copy()}


def test_unsolved_rows_are_filled_along_their_branch():
    model = _TwoBranch()
    axis = _stub_axis()
    ls = axis["l"]
    hole = (ls > 39.9) & (ls < 42.1)
    axis["ok"][hole] = False
    axis["dev"][hole] = [0.9, 0.9, 0.9, 0.1]     # a stray solve
    out = b2a.fill_axis_gaps(model, axis)
    assert out["ok"][hole].all()
    assert sorted(out["filled"]) == sorted(ls[hole].tolist())
    lab = model.predict(out["dev"][hole])
    assert np.allclose(lab[:, 0], ls[hole], atol=1e-9)
    # the input axis is not modified
    assert not axis["ok"][hole].any()


def test_a_gap_across_a_branch_jump_is_not_filled():
    model = _TwoBranch()
    axis = _stub_axis()
    ls = axis["l"]
    upper = ls > 41.0
    # the rows above the hole are on another branch (C+M+Y with less K)
    axis["dev"][upper, :3] = 0.5
    axis["dev"][upper, 3] = np.clip((100.0 - ls[upper] - 15.0) / 75.0, 0, 1)
    hole = (ls > 39.9) & (ls < 41.1)
    axis["ok"][hole] = False
    out = b2a.fill_axis_gaps(model, axis)
    assert out is axis or not out["ok"][hole].any()


def test_nothing_to_fill_returns_the_axis_itself():
    model = _TwoBranch()
    axis = _stub_axis()
    assert b2a.fill_axis_gaps(model, axis) is axis


def test_the_rate_rule_hands_the_toy_printer_over_and_the_floor_stays_neutral():
    model = _ToyCmyk(6.0)
    axis = b2a.neutral_axis(model, accurate=True, **_KW)
    import functools
    out = b2a.blackhandover_axis(
        model, axis, ladder=b2a.A34_LADDER,
        chooser=functools.partial(b2a.rate_deep_black, max_chroma=None),
        **_KW)
    assert out.get("handover") is True
    assert out["l_black"] < out["neutral_l_black"] - 1.0
    # a34: the clip floor stays at the neutral black
    assert darkmono_clip_floor(out, model, is_additive=False, n=4,
                               neutral=True) == pytest.approx(
        out["neutral_l_black"])
    # the a29/a31 behaviour is unchanged without the flag
    assert darkmono_clip_floor(out, model, is_additive=False,
                               n=4) == pytest.approx(out["l_black"])
    # without a hand-over the flag changes nothing
    assert darkmono_clip_floor(axis, model, is_additive=False, n=4,
                               neutral=True) == pytest.approx(axis["l_black"])


def test_the_builder_runs_fill_then_hand_over_then_the_floor():
    src = inspect.getsource(builder._build_profile_impl)
    i_fill = src.index("b2a_mod.fill_axis_gaps(model, axis)")
    i_rate = src.index("b2a_mod.rate_deep_black")
    i_floor = src.index("_floor = darkmono_clip_floor(")
    i_clut = src.index("dev_clut, residual = b2a_mod.build_b2a_clut(")
    assert i_fill < i_rate < i_floor < i_clut
    # a34 replaces the a29 rule: the a29 hand-over is the elif branch
    assert "elif (\"a29-blackhandover\" in candidates or _bh_ink)" in src
    # ink devices with an axis only (<= 4 inks); RGB never reaches it
    assert "if _a34 and n <= 4:" in src
