"""Battery v3.1: the wide-scale evenness rows (Agent 44 s10.6), integration 6.

The narrow smoothness rows missed the i1iSis grey steps and the Knut sky knee
Basti saw (ProfileEngineResearch RESUME.md s52, LESSON 2026-10-07). These
tests pin what the wide measure sees and what it ignores, and that the
property referee scores it for grey ramps, colour-to-black ramps and the sky.
"""
import numpy as np
import pytest

from benchmarks.research import evenness as ev
from benchmarks.research import oogq


def _line(n=401, a=(20.0, 0.0, 0.0), b=(90.0, 0.0, 0.0)):
    """A straight Lab line resampled at EQUAL dE00 steps (dE00 weights
    lightness by L*, so an even L* line is not an even pace)."""
    from benchmarks.research import colour
    t = np.linspace(0, 1, 20001)[:, None]
    fine = np.asarray(a) * (1 - t) + np.asarray(b) * t
    arc = np.concatenate([[0.0], np.cumsum(colour.de2000(fine[:-1], fine[1:]))])
    u = np.interp(np.linspace(0, arc[-1], n), arc, t[:, 0])[:, None]
    return np.asarray(a) * (1 - u) + np.asarray(b) * u


def test_an_evenly_paced_line_scores_zero():
    P = _line()
    assert ev.evenness(P) == pytest.approx(0.0, abs=0.01)
    assert ev.wide_rows(P, P)["turn_excess"] == pytest.approx(0.0, abs=1e-6)
    assert ev.turn(P) == pytest.approx(0.0, abs=1e-3)


def test_a_wide_slow_zone_is_seen():
    # the middle 40 % of the gradient moves at half the pace: a broad step
    # (the kind Basti saw), not a one-sample glitch
    t = np.linspace(0, 1, 401)
    speed = np.where((t > 0.3) & (t < 0.7), 0.5, 1.0)
    L = 20 + 70 * np.cumsum(speed) / speed.sum()
    P = np.stack([L, 0 * L, 0 * L], 1)
    assert ev.evenness(P) > 0.25


def test_a_one_sample_glitch_is_not_a_wide_unevenness():
    P = _line()
    P[200, 0] += 0.3              # narrow: the banding rows' business
    assert ev.evenness(P) < 0.1
    E = _line()
    wide = np.vstack([E[:120], E[120:280:2], E[280:]])     # half the pace over 40 %
    assert ev.evenness(P) < ev.evenness(wide)


def test_the_turn_sees_a_corner_the_source_does_not_have():
    S = _line(401, (30, 40, -40), (90, 0, 0))
    half = np.linspace(0, 1, 201)[:, None]
    corner = np.asarray([60.0, 20, -20])
    P = np.vstack([np.asarray([30.0, 40, -40]) * (1 - half) + corner * half,
                   (corner * (1 - half) + np.asarray([60.0, 60, 20]) * half)[1:]])
    assert ev.turn(S) == pytest.approx(0.0, abs=1e-3)
    assert ev.wide_rows(P, S)["turn_excess"] > 60


def test_a_path_that_does_not_move_is_nan_not_zero():
    P = np.tile([[20.0, 0, 0]], (100, 1))
    assert np.isnan(ev.evenness(P))


def test_the_lift_starts_at_the_truths_black():
    lab = np.array([[19.0, 1, 1], [34.0, 1, 1], [70.0, 1, 1]])
    o = ev.lift(lab, 19.0)
    assert o[0, 0] == 0 and o[1, 0] == pytest.approx(45.0) and o[2, 0] == 100
    assert np.allclose(o[:, 1:], 2.0)


def test_the_gradients_are_the_agents_ones():
    assert ev.grey_rgb().shape == (256, 3)
    assert set(ev.dark_rgb()) == {"blue", "red", "brown", "green"}
    assert ev.dark_rgb()["red"].max() == pytest.approx(110 / 255)
    sky = ev.sky_rgb()
    assert sky.shape == (ev.N_SKY, 3) and 0 <= sky.min() and sky.max() <= 1


class _Gamut:
    black_l = 10.0

    def depth(self, lab):
        return 40.0 - np.hypot(lab[:, 1], lab[:, 2])     # in gamut below C* 40


def _fake_srgb_to_lab(rgb):
    # a monotone stand-in for sRGB -> Lab so the test needs no lcms
    rgb = np.atleast_2d(rgb)
    L = 100 * rgb.mean(1) ** (1 / 2.2)
    return np.stack([L, 60 * (rgb[:, 0] - rgb[:, 1]), 60 * (rgb[:, 1] - rgb[:, 2])], 1)


class _Ctx:
    """Device = Lab / 100. The truth prints what was asked, but nothing
    darker than its black (L* 10); the perceptual table compresses L* into
    10..100 like a real one; optionally a band where the pace is squeezed."""
    n, additive, gamut = 3, True, _Gamut()

    def __init__(self, squeeze=False):
        self.squeeze = squeeze

    def lab2dev(self, lab, intent):
        lab = np.array(lab, float)
        if intent == "p":
            lab[:, 0] = 10 + 0.9 * lab[:, 0]
        return lab / 100.0

    def rgb2dev(self, src, rgb, intent):
        return self.lab2dev(_fake_srgb_to_lab(rgb), intent)

    def truth_lab(self, dev):
        lab = np.asarray(dev, float) * 100.0
        lab[:, 0] = np.maximum(lab[:, 0], 10.0)
        if self.squeeze:
            L = lab[:, 0]
            lab[:, 0] = np.where(L > 22, np.where(L < 32, 22 + 0.2 * (L - 22), L - 8.0), L)
        return lab


def test_a_faithful_print_scores_the_sources_own_evenness_and_no_turn():
    q, raw = ev.evaluate(_Ctx(), srgb_to_lab=_fake_srgb_to_lab)
    g = raw["r"]["grey"]      # rel. col. above the black: printed = source
    assert g["evenness_w"] == pytest.approx(g["evenness_src"], abs=1e-9)
    assert raw["r"]["sky"]["turn_excess"] == pytest.approx(0.0, abs=1e-6)
    assert q["sky_de_ingamut_r"] == pytest.approx(0.0, abs=1e-9)
    # every scored row is a known, lower-is-better referee key
    for k in q:
        assert k in oogq.KEYS and oogq.KEYS[k][0] == 1


def test_a_squeezed_dark_band_raises_the_lifted_grey_rows():
    q0, _ = ev.evaluate(_Ctx(), srgb_to_lab=_fake_srgb_to_lab)
    q1, _ = ev.evaluate(_Ctx(squeeze=True), srgb_to_lab=_fake_srgb_to_lab)
    for k in ("even_grey_lift_p", "even_grey_lift_r"):
        assert q1[k] > q0[k] + 0.1, k


def test_rel_col_rows_drop_the_part_below_the_truths_black():
    _, raw = ev.evaluate(_Ctx(), srgb_to_lab=_fake_srgb_to_lab)
    n_r = raw["r"]["grey_lift"]["n"]
    n_p = raw["p"]["grey_lift"]["n"]
    assert n_p == ev.N_RAMP and n_r < n_p
    assert n_r == int((ev.neutral_dark_lab()[:, 0] >= 11.0).sum())


def test_the_referee_scores_the_evenness_rows():
    keys = {"even_grey_r", "even_grey_p", "even_grey_lift_r", "even_grey_lift_p",
            "even_dark_r", "even_dark_p", "even_dark_lift_r", "even_dark_lift_p",
            "even_sky_r", "even_sky_p", "turn_sky_r", "turn_sky_p", "sky_de_ingamut_r"}
    assert keys <= set(oogq.KEYS)
    # the evenness rows are a decision gate (safety), the turn and the
    # in-gamut accuracy beside them are context
    assert all(oogq.KEYS[k][2] for k in keys if k.startswith("even_"))
    assert not any(oogq.KEYS[k][2] for k in ("turn_sky_r", "turn_sky_p", "sky_de_ingamut_r"))
    import inspect
    assert "evenness.evaluate" in inspect.getsource(oogq.evaluate)
