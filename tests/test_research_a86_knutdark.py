"""Research Agent 86 (a86-knutdark): the RGB perceptual neutral column near the black takes the colprof oracle's
device values only where the oracle's A2B prints the engine's darkest steps merged (Findings/agent86-01)."""
import numpy as np

from workflow.profile_engine import builder, gamut_map as gm


class _Model:
    """L* = 20 + 30 * mean(device): the engine's model of a toy printer."""
    n_channels = 3

    def predict(self, d):
        d = np.atleast_2d(d)
        return np.column_stack([20 + 30 * d.mean(1), 0 * d[:, 0], 0 * d[:, 0]])


def _setup(monkeypatch, oracle_l):
    monkeypatch.setattr(gm, "_a86_oracle_l", lambda icc, dev, x: np.asarray(oracle_l(dev), float))
    node_l = np.array([0.0, 3.1, 6.2, 9.4, 12.5, 15.6])
    node_lab = np.column_stack([node_l, 0 * node_l, 0 * node_l])
    dev = np.column_stack([0 * node_l, 0 * node_l, node_l / 60])          # blue first, as on Knut
    odev = np.column_stack([node_l / 50, node_l / 110, node_l / 160])     # colprof's R-heavy column
    mapped = _Model().predict(dev)
    return dev, odev, mapped, node_lab


def test_registered_and_on_since_integration12():
    assert gm.A86_TOKEN in builder.ENGINE_CANDIDATE_TOKENS
    assert gm.A86_TOKEN in builder.ACCURATE_DEFAULT_TOKENS
    assert gm.A86_TOKEN not in builder.accurate_candidates({"no-" + gm.A86_TOKEN})


def test_no_change_when_the_oracle_agrees(monkeypatch):
    m = _Model()
    dev, odev, mapped, nl = _setup(monkeypatch, lambda d: m.predict(d)[:, 0])
    rep = {}
    out = gm.a86_knutdark(m, dev, mapped, np.arange(6), nl, odev, b"x", "xicclu", 21.0, report=rep)
    assert not rep["fired"] and np.array_equal(out, dev)


def test_fires_when_the_oracle_sees_merged_steps(monkeypatch):
    m = _Model()
    # the oracle: blue does nothing for the first steps
    dev, odev, mapped, nl = _setup(monkeypatch, lambda d: 20 + 30 * np.maximum(d[:, 2] - 0.1, 0) / 3)
    rep = {}
    out = gm.a86_knutdark(m, dev, mapped, np.arange(6), nl, odev, b"x", "xicclu", 21.0, report=rep)
    assert rep["fired"] and rep["ratio_min"] < gm.A86_RATIO
    tl = mapped[:, 0]
    full = tl <= 21.0
    assert np.allclose(out[full], odev[full])                               # oracle's devices at the black
    assert np.allclose(out[tl >= 21.0 + gm.A86_FADE], dev[tl >= 21.0 + gm.A86_FADE])   # engine's above the fade
