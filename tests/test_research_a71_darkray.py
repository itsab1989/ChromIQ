"""Agent 71 (a71-darkray): below the black a colour-to-black ramp darkens steadily into the table's black. Only clipped
nodes below the black move; in-gamut nodes, fixed nodes and the black corner keep their values; on a toy press with a
node printing darker than the black, the lift brings it up to the black's L*; on a toy printer whose C/M/Y lighten a
heavy K, the K-first path is used (K moves first, C/M/Y late)."""
import numpy as np

from workflow.profile_engine import cmykport as P


class _Toy:
    """Identity shaping; L* falls with K and C/M/Y; optional fold (C/M/Y above K 0.9 lighten)."""

    def __init__(self, fold=0.0):
        self.fold = fold

    def shape_device(self, d):
        return np.asarray(d, float)

    def unshape_device(self, d):
        return np.asarray(d, float)

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        L = 100.0 - 70.0 * d[:, 3] - 12.0 * d[:, :3].sum(1)
        L = L + np.where(d[:, 3] > 0.9, self.fold * d[:, :3].sum(1), 0.0)
        return np.stack([L, 20 * (d[:, 0] - d[:, 1]), 20 * (d[:, 1] - d[:, 2])], 1)


def _grid(g=9):
    L = np.linspace(0, 100, g)
    ab = np.linspace(-128, 128, g)
    A, B, C = np.meshgrid(L, ab, ab, indexing="ij")
    lab = np.stack([A.ravel(), B.ravel(), C.ravel()], 1)
    return lab, g


def test_only_clipped_dark_nodes_move():
    lab, g = _grid()
    rng = np.random.default_rng(3)
    tab = rng.uniform(0, 0.6, (len(lab), 4))
    res = np.where(lab[:, 0] < 20, 9.0, 0.0)
    m = _Toy()
    black = np.array([0.6, 0.5, 0.5, 1.0])
    out, info = P.dark_ray(tab, res, lab, g, m, black, l_min=10.0, fixed_nodes=np.array([1, 2]))
    moved = np.abs(out - tab).max(1) > 0
    assert not moved[lab[:, 0] >= 10.0].any()
    assert not moved[[1, 2]].any()
    assert not moved[np.linalg.norm(lab, axis=1) < 1e-6].any()


def test_lift_to_black():
    lab, g = _grid()
    m = _Toy()
    black = np.array([0.3, 0.3, 0.3, 1.0])            # prints 100 - 70 - 10.8 = 19.2
    tab = np.tile([0.0, 0.0, 0.0, 0.0], (len(lab), 1))
    res = np.where(lab[:, 0] < 20, 9.0, 0.0)
    j = np.flatnonzero((lab[:, 0] == 0) & (np.hypot(lab[:, 1], lab[:, 2]) > 50))[0]
    tab[j] = [1.0, 1.0, 0.0, 1.0]                      # prints 6: darker than the black
    out, _ = P.dark_ray(tab, res, lab, g, m, black, l_min=19.2, params="0:3:99:1:0")
    assert m.predict(out[j])[0, 0] >= 19.2 - 1e-6
    assert m.predict(out[j])[0, 0] < 22.0


def test_paths_hit_both_ends():
    d0 = np.array([[0.9, 0.8, 0.1, 0.2]])
    db = np.array([0.1, 0.1, 0.0, 1.0])
    for k in ("linear", "klead"):
        assert np.allclose(P._path(d0, db, np.array([0.0]), k), d0)
        assert np.allclose(P._path(d0, db, np.array([1.0]), k), db[None])
    mid = P._path(d0, db, np.array([0.5]), "klead")[0]
    assert mid[3] > 0.5 * (0.2 + 1.0) and mid[0] > 0.5 * (0.9 + 0.1)   # K first, C late


def test_k_shell_leaves_gamut_alone():
    lab, g = _grid()
    tab = np.full((len(lab), 4), 0.4)
    res = np.where(lab[:, 0] < 10, 9.0, 0.0)
    out, info = P.k_shell(tab, res, lab, _Toy(fold=40), np.array([0, 0, 0, 1.0]), l_min=20.0)
    assert info["nodes"] > 0
    assert np.array_equal(out[res < 0.5], tab[res < 0.5])
