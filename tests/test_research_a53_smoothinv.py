"""Research Agent 53 (a53-smoothinv): the B2A is inverted from a smoothed copy of the forward model."""
import json

import numpy as np

from workflow.profile_engine import smoothinv as S
from workflow.profile_engine.forward_model import ForwardModel


def _model(grid=7, wiggle=3.0, seed=0):
    n = 3
    g = np.linspace(0, 1, grid)
    r, gg, b = np.meshgrid(g, g, g, indexing="ij")
    lab = np.stack([100 * (0.2 * r + 0.5 * gg + 0.3 * b), 60 * (r - gg), 50 * (gg - b)], -1).reshape(-1, 3)
    rng = np.random.default_rng(seed)
    lab = lab + rng.normal(0, wiggle, lab.shape)
    corner = np.ravel_multi_index((grid - 1,) * n, (grid,) * n)
    lab[corner] = [100.0, 0.0, 0.0]
    return ForwardModel(grid=grid, n_channels=n, nodes=lab, curves=np.tile(np.linspace(0, 1, 21), (n, 1)))


def test_modes_and_tokens_are_known():
    from workflow.profile_engine.builder import ENGINE_CANDIDATE_TOKENS, ACCURATE_DEFAULT_TOKENS
    assert S.a53_mode(()) is None
    assert S.a53_mode(["a53-smoothinv"]) == "b2a1"
    assert S.a53_mode(["a53-smoothinv-all"]) == "all"
    assert {S.A53_TOKEN, S.A53_ALL_TOKEN} <= ENGINE_CANDIDATE_TOKENS
    assert not {S.A53_TOKEN, S.A53_ALL_TOKEN} & ACCURATE_DEFAULT_TOKENS


def test_a_linear_field_is_left_alone():
    m = _model(wiggle=0.0)
    out = S.smooth_nodes(m.nodes, m.grid, 3, 50.0, np.array([0]))
    assert np.abs(out - m.nodes).max() < 1e-6


def test_smoothing_lowers_curvature_and_holds_the_pins():
    m = _model()
    pins = S._pins(m)
    out = S.smooth_nodes(m.nodes, m.grid, 3, 5.0, pins)
    c0 = np.abs(S.curvature(m.nodes, m.grid, 3)).sum()
    c1 = np.abs(S.curvature(out, m.grid, 3)).sum()
    assert c1 < 0.5 * c0
    assert np.abs(out[pins] - m.nodes[pins]).max() < 1e-3


def test_the_smoothed_copy_moves_the_patches_by_the_target_and_keeps_the_model():
    m = _model()
    before = m.nodes.copy()
    dev = np.random.default_rng(1).random((300, 3))
    sm, info = S.smoothed_copy(m, dev, target=0.5)
    assert np.array_equal(m.nodes, before)          # the A2B's model is untouched
    assert sm.curves is m.curves                     # same B2A curve space
    assert info["avgdev"] <= 0.5 + 1e-9
    assert info["avgdev"] > 0.4                      # it used its budget
    assert info["mu"] > 0


def test_env_override(monkeypatch):
    monkeypatch.setenv("CHROMIQ_A53_AVGDEV", "0.25")
    assert S.avgdev_target() == 0.25
    monkeypatch.setenv("CHROMIQ_A53_AVGDEV", "x")
    assert S.avgdev_target() == S.A53_AVGDEV


def test_info_round_trips_through_a_utf8_file(tmp_path):
    m = _model()
    _, info = S.smoothed_copy(m, np.random.default_rng(2).random((100, 3)), target=0.3)
    p = tmp_path / "info.json"
    p.write_text(json.dumps(info), encoding="utf-8")
    assert json.loads(p.read_text(encoding="utf-8"))["target"] == 0.3
