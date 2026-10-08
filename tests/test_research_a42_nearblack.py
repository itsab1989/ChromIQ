"""Agent 42 (2026-10-07): research token "a42-nearblack" (opt-in).

The near-black hand-over of the B2A tables, two parts (b2a.py, the comment
above A42_TOKEN; ProfileEngineResearch Findings/agent42-01-nearblack.md):

1. The B2A curve space keeps every ink interval at least half the
   identity's share (the shipped ramp curves' own guarantee), so a B2A cell
   no longer jumps through an interval the shaper refit collapsed (i1iSis K
   0.60-0.65, Knut G 0-0.05 with a40-knut-grey).
2. The near-black column the smoothing refit gave way on takes the neutral
   axis's values back where that prints smoother; the correction fades
   across the cells that touch the column.

No file IO here or in the token code.
"""
import inspect

import numpy as np
import pytest

from tests.test_research_a29_blackhandover import _KW, _ToyCmyk
from workflow.profile_engine import b2a, builder, gamut_map
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)

XP = np.linspace(0.0, 1.0, 21)


def test_the_token_is_known_and_not_a_default():
    assert b2a.A42_TOKEN == "a42-nearblack"
    assert b2a.A42_TOKEN in ENGINE_CANDIDATE_TOKENS
    assert b2a.A42_TOKEN not in ACCURATE_DEFAULT_TOKENS
    assert b2a.A42_TOKEN not in accurate_candidates(frozenset())
    assert b2a.A42_FLOOR == 0.5 and b2a.A42_ACCEPT == 0.5


def _dead_curve():
    # a shaper whose refit pushed the knot at 0.05 onto the one at 0.00
    y = XP.copy()
    y[1] = 1e-4
    return y


def test_a_shaper_without_a_flat_interval_is_left_exactly_alone():
    curves = np.vstack([XP, XP ** 0.8])        # slopes >= 0.8 everywhere
    assert b2a.b2a_space_curves(curves) is None


def test_a_collapsed_interval_gets_the_floor_and_the_curve_stays_a_shaper():
    curves = np.vstack([XP, _dead_curve()])
    sp = b2a.b2a_space_curves(curves)
    assert sp is not None
    assert np.array_equal(sp[0], curves[0])     # untouched channel
    d = np.diff(sp[1]) / np.diff(XP)
    assert (d > 0).all()
    assert d.min() >= b2a.A42_FLOOR / 1.1       # floored, then renormalised
    assert sp[1][0] == 0.0 and sp[1][-1] == pytest.approx(1.0)
    # the other intervals keep their relative slopes
    assert np.allclose(d[2:] / d[2], 1.0)


def test_reexpression_keeps_every_node_device_value():
    curves = np.vstack([XP, _dead_curve(), XP ** 1.2])
    sp = b2a.b2a_space_curves(curves)
    dev = np.random.default_rng(1).uniform(0, 1, (50, 3))
    shaped = np.stack([np.interp(dev[:, c], XP, curves[c]) for c in range(3)], 1)
    re = b2a.reexpress(shaped, curves, sp)
    back = np.stack([np.interp(re[:, c], sp[c], XP) for c in range(3)], 1)
    assert np.allclose(back, dev, atol=1e-9)
    assert np.allclose(b2a.reexpress(shaped, curves, curves), shaped)


def _path(curves, d0, d1, t):
    """Device along one B2A cell: linear in curve space, then the inverse."""
    s0, s1 = np.interp(d0, XP, curves), np.interp(d1, XP, curves)
    return np.interp(s0 + t * (s1 - s0), curves, XP)


def test_a_cell_across_the_collapsed_interval_no_longer_jumps():
    # Knut, a40 curves: node L* 25 at G 0.001, node L* 28.1 at G 0.091; the
    # CMM interpolates in curve space, so G leapt to 0.05 in the first few
    # per cent of the cell (a 1.8 L* kink on every reference).
    cur = _dead_curve()
    sp = b2a.b2a_space_curves(cur[None, :])[0]
    t = np.linspace(0.0, 1.0, 101)
    old = _path(cur, 0.001, 0.091, t)
    new = _path(sp, 0.001, 0.091, t)
    linear = 0.001 + t * 0.090
    rate = lambda p: np.diff(p).max() / np.diff(linear).mean()  # noqa: E731
    assert rate(old) > 20.0                      # the jump
    assert rate(new) < 2.5                       # bounded (old: 55x)
    assert np.all(np.diff(new) >= 0)


def test_ill_posed_flags_values_inside_a_floored_interval_only():
    curves = np.vstack([XP, _dead_curve()])
    dev = np.array([[0.3, 0.02], [0.3, 0.30], [0.01, 0.5]])
    assert b2a.ill_posed(dev, curves).tolist() == [True, False, False]


class _Toy(_ToyCmyk):
    """29a's toy printer with identity shaper curves."""

    def __init__(self, tint):
        super().__init__(tint)
        self.curves = np.tile(XP, (4, 1))

    def shape_device(self, d):
        return np.asarray(d, float).copy()

    def unshape_device(self, d):
        return np.asarray(d, float).copy()


def _toy_table():
    model = _Toy(6.0)
    axis = b2a.neutral_axis(model, accurate=True, **_KW)
    axis = b2a.blackhandover_axis(model, axis, **_KW)
    node_lab = b2a.lab_grid(9)
    pl, pd, _lb, blk = b2a.axis_points(axis)
    col = np.flatnonzero(np.hypot(node_lab[:, 1], node_lab[:, 2]) < 1.0)
    want = np.stack([np.interp(node_lab[col, 0], pl, pd[:, k])
                     for k in range(4)], 1)
    want[node_lab[col, 0] < pl[0]] = blk
    shaped = np.full((len(node_lab), 4), 0.3)
    shaped[col] = want
    return model, axis, node_lab, shaped, col


def _per_node(model, node_lab, shaped, col):
    """The toy's own per-node answer: the axis on the column, and for the
    others the inversion of their target (clipped by the solver)."""
    per = shaped.copy()
    rest = np.setdiff1d(np.arange(len(node_lab)), col)
    near = rest[(node_lab[rest, 0] < 45)
                & (np.abs(node_lab[rest, 1]) < 40)
                & (np.abs(node_lab[rest, 2]) < 40)]
    per[near] = b2a.invert_to_device(model, node_lab[near], accurate=True,
                                     **_KW)[0]
    return per


def _top(axis):
    nb = axis["neutral_l_black"]
    return nb + (nb - axis["l_black"])


def test_a_table_the_refit_held_is_left_exactly_alone():
    model, axis, node_lab, shaped, col = _toy_table()
    per = _per_node(model, node_lab, shaped, col)
    out, info = b2a.nearblack_column(model, per, node_lab, pernode=per,
                                     l_top=_top(axis), grid=9)
    assert out is per and not info["restored"] and info["rows"]


def test_the_hand_over_rows_take_their_own_inversion_back():
    model, axis, node_lab, shaped, col = _toy_table()
    per = _per_node(model, node_lab, shaped, col)
    refit = per.copy()
    rng = np.random.default_rng(3)
    refit = np.clip(refit + rng.normal(0, 0.15, refit.shape), 0, 1)
    out, info = b2a.nearblack_column(model, refit, node_lab, pernode=per,
                                     l_top=_top(axis), grid=9)
    assert info["restored"]
    assert info["d2_restored"] <= info["d2_refit"]
    # the zone: every row up to the first one at or above the hand-over top
    rows = np.unique(node_lab[:, 0])
    first = rows[rows >= _top(axis)][0]
    assert info["rows"][-1] == pytest.approx(first)
    step = 255.996 / 8
    ring1 = (np.abs(node_lab[:, 1]) <= step * 1.01) & (
        np.abs(node_lab[:, 2]) <= step * 1.01)
    changed = np.flatnonzero(np.any(out != refit, axis=1))
    assert len(changed) and ring1[changed].all()
    assert (node_lab[changed, 0] <= first + 1e-6).all()
    assert np.allclose(out[changed], per[changed])
    # nothing restored prints further from its target than the refit did
    e = lambda v: np.linalg.norm(model.predict(v) - node_lab[changed], axis=1)  # noqa: E731
    assert (e(out[changed]) + b2a.A42_ACCEPT <= e(refit[changed]) + 1e-9).all()


def test_a_restore_that_prints_rougher_is_refused():
    model, axis, node_lab, shaped, col = _toy_table()
    per = _per_node(model, node_lab, shaped, col)
    bad = per.copy()
    zone = node_lab[:, 0] <= _top(axis) + 12.5
    bad[zone] = np.random.default_rng(5).uniform(0, 0.5, (zone.sum(), 4))
    refit = per.copy()
    refit[zone] = 0.0
    out, info = b2a.nearblack_column(model, refit, node_lab, pernode=bad,
                                     l_top=_top(axis), grid=9)
    if "d2_restored" in info and info["d2_restored"] > info["d2_refit"]:
        assert out is refit and not info["restored"]
    else:
        assert info["restored"] or out is refit


def test_the_builder_wires_both_parts_only_with_the_token():
    src = inspect.getsource(builder._build_profile_impl)
    assert "b2a_mod.A42_TOKEN in candidates" in src
    assert "b2a_mod.nearblack_column(" in src
    assert "b2a_mod.b2a_space_curves(\n                      model.curves, smooth=" in src
    assert "b2a_mod.rgb_neutral_black(model, _bl, ucs=use_ucs)" in src
    assert "_nb + max(_nb - float(axis[\"l_black\"]), 0.0)" in src
    # the a40 bridge skips an ill-posed top only with a42
    assert "b2a_mod.ill_posed(dev_clut[_col[_j]]" in src
    gsrc = inspect.getsource(gamut_map.build_mapped_b2a)
    assert "b2a_mod.A42_TOKEN in getattr(" in gsrc
    assert "b2a_mod.reexpress(shaped, model.curves, _a42_space)" in gsrc
