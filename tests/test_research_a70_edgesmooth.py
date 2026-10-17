"""Agent 70 (a70-edgesmooth): the gamut-edge softening only touches chromatic dark nodes in a thin band across the
gamut boundary, never the deep in-gamut table, the neutral column or the fixed nodes; with a 0 weight it is the
identity."""
import numpy as np

from workflow.profile_engine import cmykport as P


def _table(g=9):
    ax = np.linspace(0, 100, g)
    ab = np.linspace(-128, 128, g)
    L, A, B = np.meshgrid(ax, ab, ab, indexing="ij")
    lab = np.stack([L.ravel(), A.ravel(), B.ravel()], 1)
    rng = np.random.default_rng(1)
    tab = rng.uniform(0, 1, (len(lab), 4))
    res = np.where(np.hypot(lab[:, 1], lab[:, 2]) < 50, 0.0, 5.0)     # a cylinder of in-gamut nodes
    return lab, tab, res, g


def test_zero_weights_are_identity():
    lab, tab, res, g = _table()
    out, info = P.edge_smooth(tab, res, lab, g, params="0:0:0:4:75:6:0")
    assert np.array_equal(out, tab) and info["nodes"] == 0


def test_only_band_nodes_move():
    lab, tab, res, g = _table()
    out, info = P.edge_smooth(tab, res, lab, g, params="0.3:0:2:4:75:6:0.5", fixed_nodes=np.array([0, 5]))
    moved = np.abs(out - tab).max(1) > 0
    dep, hgt = P.edge_layers(res < 0.5, g)
    C = np.hypot(lab[:, 1], lab[:, 2])
    allowed = (((dep == 1) | ((hgt >= 1) & (hgt <= 2))) & (C > 6) & (lab[:, 0] < 75))
    assert info["nodes"] > 0
    assert not moved[~allowed].any()
    assert not moved[[0, 5]].any()
    assert not moved[dep >= 2].any()                  # deep in-gamut nodes keep their exact value


def test_layers():
    ins = np.zeros((5, 5, 5), bool)
    ins[:, :, :3] = True
    dep, hgt = P.edge_layers(ins.ravel(), 5)
    d = dep.reshape(5, 5, 5)
    h = hgt.reshape(5, 5, 5)
    assert (d[2, 2, 2] == 1) and (d[2, 2, 1] == 2) and (h[2, 2, 3] == 1) and (h[2, 2, 4] == 2)


class _Fold:
    """A toy CMYK printer: L* falls with K; above K 0.9 any C/M/Y lightens the print (the i1Pro fold)."""

    def predict(self, d):
        d = np.atleast_2d(d)
        L = 100.0 - 75.0 * d[:, 3] - 10.0 * d[:, :3].sum(1)
        lift = np.where(d[:, 3] > 0.9, 30.0 * d[:, :3].sum(1), 0.0)
        return np.stack([L + lift, np.zeros(len(d)), np.zeros(len(d))], 1)


class _Press(_Fold):
    def predict(self, d):
        d = np.atleast_2d(d)
        L = 100.0 - 75.0 * d[:, 3] - 10.0 * d[:, :3].sum(1)
        return np.stack([L, np.zeros(len(d)), np.zeros(len(d))], 1)


def test_k_fold_found_only_where_inks_lighten_the_black():
    assert P.k_fold(_Press()) is None
    kf = P.k_fold(_Fold())
    assert kf is not None and 0.88 <= kf <= 0.91


class _Lin:
    def unshape_device(self, x):
        return x

    def predict(self, d):
        d = np.atleast_2d(d)
        return np.stack([100.0 - 100.0 * d[:, 3], 50.0 * d[:, 0], 50.0 * d[:, 1]], 1)


def test_adaptive_layer_never_moves_more_than_the_plain_one():
    lab, tab, res, g = _table()
    plain, _ = P.edge_smooth(tab, res, lab, g, params="0.3:0:2:4:75:6:0.5")
    adapt, _ = P.edge_smooth(tab, res, lab, g, params="0.3:0:2:4:75:6:0.5", model=_Lin(), adapt="2:5")
    dep, hgt = P.edge_layers(res < 0.5, g)
    m = dep == 1
    assert np.all(np.abs(adapt - tab)[m].max(1) <= np.abs(plain - tab)[m].max(1) + 1e-9)


def test_black_shell_moves_only_clipped_nodes_below_the_black():
    lab, tab, res, g = _table()
    blk = np.array([0.0, 0.0, 0.0, 1.0])
    out, info = P.black_shell(tab, res, lab, blk, l_min=20.0, params="3:0.5:80")
    moved = np.abs(out - tab).max(1) > 0
    assert not moved[lab[:, 0] >= 17.0].any()
    assert not moved[res < 0.5].any()
    assert info["nodes"] > 0
    # with a strong fold at the black (i1Pro-like) the shell is off
    out2, info2 = P.black_shell(tab, res, lab, blk, l_min=20.0, model=_FoldBlack(), params="3:0.5:80")
    assert np.array_equal(out2, tab) and info2["fold_factor"] == 0.0


class _FoldBlack:
    def predict(self, d):
        d = np.atleast_2d(d)
        L = 100.0 - 80.0 * d[:, 3] + 40.0 * d[:, :3].sum(1) * (d[:, 3] > 0.9)
        return np.stack([L, np.zeros(len(d)), np.zeros(len(d))], 1)
