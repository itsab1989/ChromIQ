"""Agent 60 research token a60-darkfine on a58 keep-grid33in: off by default, and the dark keep does what it says."""
import numpy as np

from workflow.profile_engine import purecolprof as p


def _lab(g=33):
    from workflow.profile_engine.icc_writer import lab_grid_axes
    la, ab = lab_grid_axes(g)
    L, A, B = np.meshgrid(la, ab, ab, indexing="ij")
    return np.stack([L.ravel(), A.ravel(), B.ravel()], axis=1)


def test_token_off_is_none():
    assert p.a60_dark([], _lab()) is None
    assert p.a60_dark(["a59-wideband"], _lab()) is None


def test_keep_weight_is_one_in_the_dark_and_zero_above_the_blend(monkeypatch):
    monkeypatch.setenv("CHROMIQ_A60_L", "30")
    monkeypatch.setenv("CHROMIQ_A60_W", "10")
    monkeypatch.delenv("CHROMIQ_A60_C", raising=False)
    lab = _lab()
    keep, band = p.a60_dark(["a60-darkfine"], lab)
    assert band is None
    assert np.all(keep[lab[:, 0] <= 30] == 1.0) and np.all(keep[lab[:, 0] >= 40] == 0.0)
    assert np.all(np.diff(keep.reshape(33, 33, 33)[:, 5, 5]) <= 0)


def test_dark_nodes_keep_the_fine_table_light_ones_do_not(monkeypatch):
    monkeypatch.setenv("CHROMIQ_A60_L", "30")
    monkeypatch.setenv("CHROMIQ_A60_W", "10")
    g_f, g_c = 33, 17
    lab = _lab(g_f)
    fine = np.zeros((g_f ** 3, 3))
    coarse = np.ones((g_c ** 3, 3))
    res = np.full(g_f ** 3, 5.0)
    out = p.coarse_outside(fine, coarse, res, g_f, g_c, dark=p.a60_dark(["a60-darkfine"], lab))
    assert np.all(out[lab[:, 0] <= 30] == 0.0)
    assert np.allclose(out[lab[:, 0] >= 40], 1.0)
    ref = p.coarse_outside(fine, coarse, res, g_f, g_c)
    assert np.allclose(ref, 1.0)


def test_dark_band_widens_the_hand_over_instead(monkeypatch):
    monkeypatch.setenv("CHROMIQ_A60_C", "10")
    g_f, g_c = 33, 17
    lab = _lab(g_f)
    fine = np.zeros((g_f ** 3, 3))
    coarse = np.ones((g_c ** 3, 3))
    res = np.full(g_f ** 3, 5.0)
    out = p.coarse_outside(fine, coarse, res, g_f, g_c, dark=p.a60_dark(["a60-darkfine"], lab))
    assert np.allclose(out[lab[:, 0] <= 30], 0.5)        # smoothstep(5 / 10)
    assert np.allclose(out[lab[:, 0] >= 40], 1.0)


def test_darkrel_measures_the_limit_from_the_black(monkeypatch):
    monkeypatch.setenv("CHROMIQ_A60_L", "10")
    monkeypatch.setenv("CHROMIQ_A60_W", "10")
    monkeypatch.delenv("CHROMIQ_A60_C", raising=False)
    lab = _lab()
    keep, _ = p.a60_dark(["a60-darkfine", "a60-darkrel"], lab, black_l=20.0)
    assert np.all(keep[lab[:, 0] <= 30] == 1.0) and np.all(keep[lab[:, 0] >= 40] == 0.0)
    keep2, _ = p.a60_dark(["a60-darkfine"], lab, black_l=20.0)
    assert np.all(keep2[lab[:, 0] >= 20] == 0.0)


class _M:
    n_channels = 3

    def predict(self, d):
        return np.full((len(d), 3), 20.0)


def test_darkclip_weight_is_off_without_the_token_or_outside_a58():
    p.set_active(False)
    assert p.a60_clip_weight(_M(), _lab()) is None
    p.set_active(True)
    p.set_a60([])
    assert p.a60_clip_weight(_M(), _lab()) is None
    p.set_active(False)


def test_darkclip_weight_counts_from_the_black(monkeypatch):
    monkeypatch.delenv("CHROMIQ_A60_CL", raising=False)
    monkeypatch.delenv("CHROMIQ_A60_CW", raising=False)
    p.set_active(True)
    p.set_a60(["a60-darkclip"])
    lab = _lab()
    k = p.a60_clip_weight(_M(), lab)
    p.set_active(False)
    assert np.all(k[lab[:, 0] <= 30] == 1.0) and np.all(k[lab[:, 0] >= 40] == 0.0)
    assert p.a60_clip_weight(_M(), lab) is None


def test_darkacc_is_the_candidate_set(monkeypatch):
    for e in ("CHROMIQ_A60_L", "CHROMIQ_A60_W", "CHROMIQ_A60_C", "CHROMIQ_A60_CL", "CHROMIQ_A60_CW"):
        monkeypatch.delenv(e, raising=False)
    lab = _lab()
    keep, band = p.a60_dark(["a60-darkacc"], lab, black_l=20.0)
    assert band == 16.0
    assert np.all(keep[lab[:, 0] <= 30] == 1.0) and np.all(keep[lab[:, 0] >= 40] == 0.0)
    p.set_active(True)
    p.set_a60(["a60-darkacc"])
    k = p.a60_clip_weight(_M(), lab)
    p.set_active(False)
    assert np.all(k[lab[:, 0] <= 20] == 1.0) and np.all(k[lab[:, 0] >= 30] == 0.0)
