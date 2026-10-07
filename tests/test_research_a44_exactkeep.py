"""Agent 44 (2026-10-07): research token "a44-exactkeep" (opt-in).

a42's keep-the-exact-value rule anywhere in the colorimetric B2A table
(b2a.py, the comment above A44_TOKEN; ProfileEngineResearch
Findings/agent44-01-exactkeep.md): an in-gamut node (its own inversion
within A42_ACCEPT of its target) that the smoothing refit pulled more than
A44_TOL off takes its own inversion back, where the cells around it then
print closer to their targets in the model.

No file IO here or in the token code.
"""
import inspect

import numpy as np

from workflow.profile_engine import b2a, builder
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)

G = 9
_M = np.array([[0.3 * 70, 0.5 * 70, 0.2 * 70],
               [80.0, -80.0, 0.0],
               [0.0, 80.0, -80.0]])
_O = np.array([25.0, 0.0, 0.0])


class _ToyRgb:
    """A linear RGB printer (identity shaper curves): every node inside the
    parallelepiped is inverted exactly. ``fold``: channel R prints as
    |2R - 1| (R and 1 - R print alike), the competing branches a folded
    model hands the refit."""

    n_channels = 3

    def __init__(self, fold=False):
        self.fold = fold
        self.nodes = np.zeros(1)
        self.curves = np.tile(np.linspace(0.0, 1.0, 21), (3, 1))

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float)).copy()
        if self.fold:
            d[:, 0] = np.abs(2.0 * d[:, 0] - 1.0)
        return _O[None, :] + d @ _M.T

    def shape_device(self, d):
        return np.asarray(d, float).copy()

    def unshape_device(self, d):
        return np.asarray(d, float).copy()


def _table(model):
    node_lab = b2a.lab_grid(G)
    dev = np.linalg.solve(_M, (node_lab - _O[None, :]).T).T
    per = np.clip(dev, 0.0, 1.0)
    e = np.linalg.norm(model.predict(per) - node_lab, axis=1)
    return node_lab, per, np.flatnonzero(e <= b2a.A42_ACCEPT)


def test_the_token_is_known_and_not_a_default():
    assert b2a.A44_TOKEN == "a44-exactkeep"
    assert b2a.A44_TOKEN in ENGINE_CANDIDATE_TOKENS
    assert b2a.A44_TOKEN not in ACCURATE_DEFAULT_TOKENS
    assert b2a.A44_TOKEN not in accurate_candidates(frozenset())
    assert b2a.A44_TOL == 2.0


def test_the_toy_has_in_gamut_nodes():
    _lab, _per, ing = _table(_ToyRgb())
    assert len(ing) >= 8


def test_a_refit_within_the_tolerance_is_left_exactly_alone():
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    refit = per.copy()
    # a small smoothing move: about 1 dE76, inside A44_TOL
    refit[ing] += np.array([0.0, 0.0, 1.0 / 80.0])
    out, info = b2a.exact_keep(model, refit, node_lab, pernode=per, grid=G)
    assert out is refit and info["nodes"] == 0 and info["candidates"] == 0


def test_in_gamut_nodes_pulled_off_take_their_inversion_back():
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    refit = per.copy()
    hit = ing[::3]
    refit[hit] = np.clip(refit[hit] + np.array([0.08, -0.06, 0.05]), 0, 1)
    out_of_gamut = np.setdiff1d(np.arange(len(node_lab)), ing)[::50]
    refit[out_of_gamut] = 0.5           # a refit's clip: never touched
    out, info = b2a.exact_keep(model, refit, node_lab, pernode=per, grid=G)
    assert info["nodes"] == len(hit) == info["candidates"]
    assert np.allclose(out[hit], per[hit])
    rest = np.setdiff1d(np.arange(len(node_lab)), hit)
    assert np.array_equal(out[rest], refit[rest])
    assert sorted(info["restored"]) == sorted(hit.tolist())


def test_pinned_nodes_are_never_touched():
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    refit = per.copy()
    refit[ing] = np.clip(refit[ing] + 0.08, 0, 1)
    out, info = b2a.exact_keep(model, refit, node_lab, pernode=per, grid=G,
                               keep_out=ing[:2])
    assert np.array_equal(out[ing[:2]], refit[ing[:2]])
    assert info["nodes"] == len(ing) - 2


def test_a_restore_onto_the_other_branch_of_a_fold_is_refused():
    # Folded R: the per-node answer sits on R < 0.5, the refit field on the
    # mirror branch R > 0.5, shifted 3 dE76 (a candidate). Putting the node
    # back on its own branch would make every cell around it cross the fold
    # (R 0.5 prints as R = 0), so the guard keeps the refit.
    model = _ToyRgb(fold=True)
    node_lab, per, ing = _table(_ToyRgb())
    lin = per.copy()
    mirror = lin.copy()
    mirror[:, 0] = 0.5 + 0.5 * lin[:, 0]        # |2R - 1| = R_lin
    own = lin.copy()
    own[:, 0] = 0.5 - 0.5 * lin[:, 0]           # the other branch, exact
    j = ing[np.argmax(lin[ing, 0])]
    assert lin[j, 0] > 0.2
    refit = mirror.copy()
    refit[j, 2] = min(1.0, refit[j, 2] + 3.0 / 80.0)
    pern = mirror.copy()
    pern[j] = own[j]
    e = lambda v: np.linalg.norm(model.predict(v[j]) - node_lab[j])  # noqa: E731
    assert e(pern) < 1e-6 and e(refit) > b2a.A44_TOL
    out, info = b2a.exact_keep(model, refit, node_lab, pernode=pern, grid=G)
    assert info["candidates"] == 1 and info["nodes"] == 0
    assert out is refit


def test_a_grid_that_is_not_uniform_lab_is_skipped():
    model = _ToyRgb()
    node_lab, per, _ing = _table(model)
    warped = node_lab.copy()
    warped[:, 0] = 100.0 * (warped[:, 0] / 100.0) ** 2
    out, info = b2a.exact_keep(model, per + 0.1, warped, pernode=per, grid=G)
    assert info.get("skipped") == "grid" and info["nodes"] == 0


def test_the_builder_wires_it_only_with_the_token():
    src = inspect.getsource(builder._build_profile_impl)
    assert "b2a_mod.A44_TOKEN in candidates and n <= 4" in src
    assert "b2a_mod.exact_keep(" in src
    assert "keep_out=fixed_nodes" in src
    # after a42's near-black rows and before the ceiling, white and black
    # pins, so those still win
    i44 = src.index("b2a_mod.exact_keep(")
    assert src.index("b2a_mod.nearblack_column(") < i44
    assert i44 < src.index("if channel_max is not None:\n        # The smooth")


# Part 2 (with a40-knut-grey): the dark bridge drawn the way a CMM reads it.

def _column():
    ls = np.arange(0.0, 50.0 + 1e-9, 3.125)
    dev = np.tile(np.linspace(0.0, 0.4, len(ls))[:, None], (1, 3))
    dev[ls < 22.0] = 0.0                       # at and below the black
    return ls, dev


def test_the_bridge_runs_from_the_node_below_the_black_in_curve_space():
    ls, dev = _column()
    xp = np.linspace(0.0, 1.0, 21)
    space = np.vstack([xp, xp ** 0.7, xp ** 1.3])
    out = b2a.dark_bridge_on_grid(dev, ls, black_l=22.86, to_l=26.0,
                                  space=space)
    b = int(np.flatnonzero(ls <= 22.86)[-1])   # node L* 21.875
    a = int(np.flatnonzero(ls >= 26.0)[0])     # node L* 28.125
    assert np.array_equal(out[:b + 1], dev[:b + 1])
    assert np.array_equal(out[a:], dev[a:])
    cs = lambda v: np.array([np.interp(v[c], xp, space[c]) for c in range(3)])  # noqa: E731
    u = (ls[b + 1] - ls[b]) / (ls[a] - ls[b])
    want = cs(out[b]) + u * (cs(out[a]) - cs(out[b]))
    assert np.allclose(cs(out[b + 1]), want, atol=1e-9)


def test_without_a_node_below_the_black_it_is_the_a40_bridge():
    ls, dev = _column()
    ls = ls + 30.0                             # no node at or below 22.86
    xp = np.linspace(0.0, 1.0, 21)
    space = np.tile(xp, (3, 1))
    got = b2a.dark_bridge_on_grid(dev, ls, black_l=22.86, to_l=40.0,
                                  space=space)
    ref = b2a.dark_bridge(dev, ls, black_l=22.86, to_l=40.0)
    assert np.array_equal(got, ref)


def test_the_builder_draws_the_grid_bridge_only_with_the_token():
    src = inspect.getsource(builder._build_profile_impl)
    i = src.index("b2a_mod.dark_bridge_on_grid(")
    assert "if accurate and b2a_mod.A44_TOKEN in candidates:" in src[:i]
    assert "b2a_mod.dark_bridge(" in src[i:]   # the a40 bridge otherwise
