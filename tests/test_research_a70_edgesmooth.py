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
