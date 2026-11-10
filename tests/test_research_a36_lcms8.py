"""Agent 36 (2026-10-07): research token "a36-lcms8-safe".

With a35-percblack-blend the RGB perceptual neutral column passes through
b2a.anchor_column_black, whose running minimum turned a reversal of the
colprof oracle's column (S1 pessimistic september: target L* 73.6, then
70.4 two nodes darker) into a PLATEAU: sRGB grey 136 to 152 all printed
L* 70.4, so all three device channels went flat along the sRGB grey ramp.
lcms2's default 8-bit RGB -> RGB optimisation (cmsopt.c
OptimizeByComputingLinearization) places its CLUT nodes along exactly that
grey-ramp curve, and once the column was monotone (the reversal used to
make lcms reject the curve) it ran and put skin up to 11 % wrong. The token
makes the column monotone with a straight bridge over each reversal zone
instead (b2a.monotone_bridge), on RGB printers only; a Maximum accuracy
default after the A/B ("no-a36-lcms8-safe" switches it off). ProfileEngineResearch
Findings/agent36-01-lcms8.md.
"""
import inspect

import numpy as np
import pytest

from workflow.profile_engine import b2a, gamut_map
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)

# S1 pessimistic september, perceptual column as int-4 built it (source L*
# light to dark, target L* from the oracle): a 3 L* reversal at source L*
# 56-62 (Experiments/agent36, tools/axis.py on arm-base).
_SRC = np.array([75.0, 71.9, 68.8, 65.6, 62.5, 59.4, 56.2, 53.1, 50.0, 46.9])
_TGT = np.array([81.0, 78.4, 75.4, 73.9, 70.4, 71.9, 73.6, 64.5, 59.7, 55.2])


def test_the_token_is_a_default_with_an_off_switch():
    # Agent 36 A/B (Findings/agent36-01-lcms8.md s5): default since then
    assert b2a.A36_TOKEN == "a36-lcms8-safe"
    assert b2a.A36_TOKEN in ENGINE_CANDIDATE_TOKENS
    assert b2a.A36_TOKEN in ACCURATE_DEFAULT_TOKENS
    assert "no-a36-lcms8-safe" in ENGINE_CANDIDATE_TOKENS
    assert b2a.A36_TOKEN in accurate_candidates(frozenset())
    assert b2a.A36_TOKEN not in accurate_candidates({"no-a36-lcms8-safe"})


def test_the_running_minimum_makes_the_plateau_the_bridge_does_not():
    old = b2a.anchor_column_black(_TGT, _SRC, black_l=_TGT[-1], fade=1e-9)
    new = b2a.anchor_column_black(_TGT, _SRC, black_l=_TGT[-1], fade=1e-9,
                                  bridge=True)
    # before: three source nodes on one target L* (the flat step)
    assert np.sum(np.isclose(old, 70.4)) == 3
    # after: strictly decreasing from light to dark, no two nodes equal
    assert (np.diff(new) < -1e-6).all()


def test_nodes_outside_the_reversal_keep_their_value_exactly():
    new = b2a.monotone_bridge(_TGT, _SRC)
    keep = [0, 1, 2, 3, 7, 8, 9]
    assert np.array_equal(new[keep], _TGT[keep])
    # the zone is the straight line in source L* between its bounding nodes
    u = (_SRC[3] - _SRC[4:7]) / (_SRC[3] - _SRC[7])
    assert np.allclose(new[4:7], _TGT[3] + (_TGT[7] - _TGT[3]) * u)


def test_a_monotone_column_is_returned_unchanged():
    tl = np.array([90.0, 80.0, 80.0, 60.0, 40.0, 20.0])
    sl = np.array([95.0, 85.0, 70.0, 55.0, 30.0, 5.0])
    assert np.array_equal(b2a.monotone_bridge(tl, sl), tl)
    # node order does not matter (the column is sorted by source L* first)
    p = np.array([3, 0, 5, 1, 4, 2])
    assert np.array_equal(b2a.monotone_bridge(tl[p], sl[p]), tl[p])


def test_a_zone_open_at_an_end_falls_back_to_the_running_minimum():
    # the lightest node is lower than the next: no lighter bound exists
    tl = np.array([70.0, 75.0, 60.0, 50.0])
    sl = np.array([90.0, 80.0, 60.0, 40.0])
    out = b2a.monotone_bridge(tl, sl)
    order = np.argsort(-sl)
    assert np.array_equal(out[order], np.minimum.accumulate(tl[order]))


@pytest.mark.parametrize("seed", range(5))
def test_the_bridge_is_always_non_increasing_and_keeps_consistent_nodes(seed):
    rng = np.random.default_rng(seed)
    sl = np.sort(rng.uniform(0, 100, 33))[::-1]
    tl = sl * 0.8 + 15 + rng.normal(0, 3, 33)
    out = b2a.monotone_bridge(tl, sl)
    assert (np.diff(out) <= 1e-9).all()
    assert out.min() >= tl.min() - 1e-9 and out.max() <= tl.max() + 1e-9
    # a node that was already consistent with every other keeps its value
    lo = np.minimum.accumulate(tl)
    hi = np.maximum.accumulate(tl[::-1])[::-1]
    ok = np.isclose(lo, hi)
    assert np.array_equal(out[ok], tl[ok])


def test_the_default_anchor_is_unchanged_without_the_token():
    tl = b2a.anchor_column_black(_TGT, _SRC, black_l=50.0)
    ref = _TGT + (50.0 - _TGT[-1]) * np.clip(
        1.0 - (_SRC - _SRC.min()) / 25.0, 0.0, 1.0)
    assert np.array_equal(tl, np.minimum.accumulate(ref))


def test_the_bridge_is_wired_for_rgb_only_and_only_with_the_token():
    src = inspect.getsource(gamut_map.build_mapped_b2a)
    assert "bridge=bool(" in src
    assert "is_additive and b2a_mod.A36_TOKEN in _cands" in src
