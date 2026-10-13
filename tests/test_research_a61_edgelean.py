"""Agent 61 research token a61-edgelean (off by default): near the cusp edges of the device cube the
keep-grid33in table leans toward the coarse (colprof) table; elsewhere nothing changes."""
import numpy as np

from workflow.profile_engine import purecolprof as M


def test_token_off_is_none():
    assert M.a61_edge(set()) is None
    assert M.a61_edge({"a60-darkacc"}) is None
    assert M.a61_edge({"a61-edgelean"}) == (M.A61_EDGE, M.A61_EDGE_S)


def test_edge_weight_only_near_cusp_edges():
    f = np.array([[0.5, 0.5, 0.5],      # interior
                  [1.0, 0.0, 0.4],      # on the red-magenta cusp edge
                  [1.0, 1.0, 0.5],      # white-side edge (two at 1): not a cusp edge
                  [0.0, 0.0, 0.5],      # black-side edge: not a cusp edge
                  [0.95, 0.05, 0.3]])   # half way inside the width
    w = M.edge_weight(f, (0.1, 1.0))
    assert w[0] == 0 and w[2] == 0 and w[3] == 0
    assert w[1] == 1.0
    assert 0.0 < w[4] < 1.0


def test_coarse_outside_unchanged_without_edge():
    rng = np.random.default_rng(1)
    g, gc = 5, 3
    fine = rng.random((g ** 3, 3))
    coarse = rng.random((gc ** 3, 3))
    res = rng.random(g ** 3) * 4
    a = M.coarse_outside(fine, coarse, res, g, gc)
    b = M.coarse_outside(fine, coarse, res, g, gc, edge=None)
    assert np.array_equal(a, b)
    c = M.coarse_outside(fine, coarse, res, g, gc, edge=(0.1, 1.0))
    far = M.edge_weight(fine, (0.1, 1.0)) == 0
    assert np.array_equal(a[far], c[far])
