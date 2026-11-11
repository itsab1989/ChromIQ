"""Agent 59 research tokens on a58-purecolprof (keep-grid33in): off by default, and the helpers do what they say."""
import numpy as np

from workflow.profile_engine import purecolprof as p


def test_tokens_off_leave_the_hand_over_alone():
    assert p.a59_band([]) is None and p.a59_inside([]) is None
    fine = np.random.default_rng(0).random((17 ** 3, 3))
    assert p.a59_fine(fine, fine * 0, np.ones(17 ** 3), []) is fine


def test_band_and_inside_read_the_environment(monkeypatch):
    monkeypatch.setenv("CHROMIQ_A59_BAND", "8")
    monkeypatch.setenv("CHROMIQ_A59_IN", "16")
    monkeypatch.setenv("CHROMIQ_A59_INS", "0.5")
    assert p.a59_band(["a59-wideband"]) == 8.0
    assert p.a59_inside(["a59-inband"]) == (16.0, 0.5)


def test_depth_inside_counts_lab_distance_to_the_nearest_clipped_node():
    g = 33
    r = np.zeros((g, g, g))
    r[:, :, 30:] = 5.0
    d = p.depth_inside(r.reshape(-1), g, 10.0).reshape(g, g, g)
    assert d[5, 5, 30] == 0.0
    assert abs(d[5, 5, 29] - 8.0) < 0.1          # one a/b step (~7.97 dE)
    assert np.isinf(d[5, 5, 28])                 # two steps: beyond the depth


def test_inside_band_never_touches_clipped_nodes_beyond_the_outward_band():
    g_f, g_c = 33, 17
    fine = np.zeros((g_f ** 3, 3))
    coarse = np.ones((g_c ** 3, 3))
    res = np.zeros(g_f ** 3)
    res.reshape(g_f, g_f, g_f)[:, :, 30:] = 3.0
    out = p.coarse_outside(fine, coarse, res, g_f, g_c, band=8.0, inside=(10.0, 1.0)).reshape(g_f, g_f, g_f, 3)
    u = 3.0 / 8.0
    assert np.allclose(out[5, 5, 31], u * u * (3 - 2 * u))   # outward band only
    assert out[5, 5, 29, 0] > 0.0 and out[5, 5, 20, 0] == 0.0
