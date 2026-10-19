"""Agent 68 research token a68-clipkeep: off by default; a clipped node the B2A refit threw far off its own clip
takes the clip back, smoothly between A68_LO and A68_HI dE; in-gamut, near and pinned nodes are untouched."""
import numpy as np

from workflow.profile_engine import b2a


class _Lin:
    """Toy forward model: Lab = 100 * device (curve space = device squared)."""
    def predict(self, d):
        return 100.0 * np.asarray(d, float)

    def shape_device(self, d):
        return np.asarray(d, float) ** 2

    def unshape_device(self, s):
        return np.sqrt(np.clip(np.asarray(s, float), 0.0, None))


def test_off_by_default_and_known():
    from workflow.profile_engine import builder
    assert "a68-clipkeep" in builder.ENGINE_CANDIDATE_TOKENS
    assert "a68-clipkeep" not in builder.ACCURATE_DEFAULT_TOKENS
    assert "a68-clipkeep" not in builder.accurate_candidates([])


def test_far_clipped_node_takes_its_clip_back(monkeypatch):
    monkeypatch.delenv("CHROMIQ_A68", raising=False)
    m = _Lin()
    pern = np.array([[0.3, 0.8, 0.45], [0.3, 0.8, 0.45], [0.3, 0.8, 0.45], [0.3, 0.8, 0.45], [0.3, 0.8, 0.45]])
    refit = pern.copy()
    refit[0] = [0.7, 0.53, 0.63]           # far off (>> A68_HI dE): restored fully
    refit[1] = [0.33, 0.8, 0.45]           # 3 dE off: kept as the refit has it
    refit[2] = [0.7, 0.53, 0.63]           # far off but in gamut: a44's business
    refit[3] = [0.7, 0.53, 0.63]           # far off but pinned
    refit[4] = [0.39, 0.8, 0.45]           # 9 dE off: half way (smoothstep 0.5)
    res = np.array([8.8, 8.8, 0.2, 8.8, 8.8])
    out, info = b2a.clip_keep(m, m.shape_device(refit), pern, res, keep_out=np.array([3]))
    dev = m.unshape_device(out)
    assert np.allclose(dev[0], pern[0])
    assert np.allclose(dev[1], refit[1]) and np.allclose(dev[2], refit[2]) and np.allclose(dev[3], refit[3])
    sh = 0.5 * m.shape_device(refit[4]) + 0.5 * m.shape_device(pern[4])
    assert np.allclose(out[4], sh)
    assert info["nodes"] == 2 and info["full"] == 1


def test_nothing_to_do_returns_the_same_array():
    m = _Lin()
    pern = np.full((4, 3), 0.5)
    s = m.shape_device(pern)
    out, info = b2a.clip_keep(m, s, pern, np.full(4, 9.0))
    assert out is s and info["nodes"] == 0
