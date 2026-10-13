"""Agent 56 (2026-10-13, D-30 part 1): research token "a56-blackfade".

With a51's colprof clip metric on (RGB), the a29 floor lifts every clip
target darker than the printer black to the black's L* with its chroma kept,
so dark colours hold their colour into the black (int-7, Knut blue / azure);
without the floor (Agent 55) they snap onto the black a few steps early.
The token keeps the floor and fades the lifted target's chroma with its
depth below the black: k = (1 + r / R)^-R, r = alpha(h) * depth / C, where
alpha(h) is the cone ratio at which Argyll's metric (colprof's clip) lands
a target below the black on the black. First order equals colprof's
geometry, the fade is C1 and monotone. Off by default.
"""
from pathlib import Path

import numpy as np

from workflow.profile_engine import b2a, oog_clip
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)

TOK = oog_clip.A56_TOKEN


def _params(tokens, *, additive, colorimetric=True):
    b2a.set_research_tokens(frozenset(accurate_candidates(frozenset(tokens))),
                            is_additive=additive)
    oog_clip.set_colorimetric(colorimetric)
    return oog_clip.table_params()


def teardown_function(_f):
    b2a.set_research_tokens((), is_additive=None)
    oog_clip.set_colorimetric(False)
    oog_clip.set_dark_floor(None)


def test_the_token_is_known_and_a_default_since_integration_8():
    assert TOK == "a56-blackfade"
    assert TOK in ENGINE_CANDIDATE_TOKENS
    assert TOK in ACCURATE_DEFAULT_TOKENS
    assert TOK in accurate_candidates(frozenset())
    assert "no-" + TOK in ENGINE_CANDIDATE_TOKENS
    assert TOK not in accurate_candidates({"no-" + TOK})


def test_it_acts_only_in_the_rgb_colorimetric_table_with_a51():
    assert _params({TOK}, additive=True).get("a56_on") is True
    assert _params(set(), additive=True).get("a56_on") is True   # int-8 default
    assert not _params({"no-" + TOK}, additive=True).get("a56_on")
    # perceptual / saturation tables, ink devices, a51 switched off
    assert not _params({TOK}, additive=True, colorimetric=False).get("a56_on")
    assert not _params({TOK}, additive=False).get("a56_on")
    assert not _params({TOK, "no-a51-colprofedge"}, additive=True).get("a56_on")


def test_the_floor_stays_on():
    p = _params({TOK}, additive=True)
    assert p["dm_on"] and not p.get("dm_off")


def test_k_is_one_at_the_floor_and_matches_colprofs_first_order():
    c = np.full(5, 40.0)
    alpha = 2.0
    for shape in ("rat", "poly"):
        assert np.allclose(oog_clip.blackfade_k(c, np.zeros(5), alpha,
                                                2.0, shape), 1.0)
        # d(k c)/d depth at the floor = -alpha (colprof's cone: c - alpha d)
        h = 1e-4
        kc = oog_clip.blackfade_k(c[:1], np.array([h]), alpha, 2.0, shape) * c[0]
        assert abs((kc[0] - c[0]) / h + alpha) < 1e-2


def test_k_is_monotone_and_c1_in_depth():
    d = np.linspace(0.0, 30.0, 3001)
    c = np.full_like(d, 25.0)
    for shape in ("rat", "poly"):
        kc = oog_clip.blackfade_k(c, d, 1.7, 2.0, shape) * c
        g = np.diff(kc) / np.diff(d)
        assert (g <= 1e-12).all()                          # monotone
        assert np.abs(np.diff(g)).max() < 0.01             # no slope jump
        assert kc[-1] >= 0.0


def test_the_rational_fade_never_reaches_zero_and_poly_does_smoothly():
    c, d = np.array([10.0]), np.array([20.0])
    assert oog_clip.blackfade_k(c, d, 2.0, 2.0, "rat")[0] > 0.0
    assert oog_clip.blackfade_k(c, d, 2.0, 2.0, "poly")[0] == 0.0


def test_nothing_to_fade_without_depth_or_chroma():
    k = oog_clip.blackfade_k(np.array([0.0, 30.0, 30.0]),
                             np.array([5.0, 0.0, -2.0]), 3.0)
    assert np.allclose(k, 1.0)


class _ConePrinter:
    """An RGB 'printer' whose gamut is a cone with its apex at the black."""
    n_channels = 3

    def predict(self, dev):
        dev = np.clip(np.asarray(dev, float), 0.0, 1.0)
        m = dev.mean(1)
        lab = np.empty((len(dev), 3))
        lab[:, 0] = 20.0 + 75.0 * m
        lab[:, 1] = 60.0 * (dev[:, 0] - dev[:, 1])
        lab[:, 2] = 60.0 * (dev[:, 1] - dev[:, 2])
        return lab


def _a51p():
    p = dict(oog_clip.DEFAULTS)
    p.update(oog_clip.A51_PARAMS)
    return p, oog_clip.space_fn(p["space"])


def test_the_cone_ratio_is_positive_finite_and_memoised():
    p, fn = _a51p()
    m = _ConePrinter()
    al = oog_clip.blackfade_alpha(m, 20.0, p, fn, n_hues=12, iters=10)
    assert al.shape == (12,)
    assert np.isfinite(al).all() and (al > 0).all()
    assert oog_clip.blackfade_alpha(m, 20.0, p, fn, n_hues=12, iters=10) is al


def test_a_floor_at_paper_black_gives_no_fade():
    p, fn = _a51p()
    assert not oog_clip.blackfade_alpha(_ConePrinter(), 0.2, p, fn,
                                        n_hues=6).any()


def test_lifted_targets_keep_l_and_hue_and_lose_chroma_with_depth():
    p, fn = _a51p()
    p["a56_shape"], p["a56_r"] = "rat", 2.0
    m = _ConePrinter()
    floor = 20.0
    l0 = np.array([25.0, 15.0, 10.0, 5.0, 0.0])
    t = np.stack([l0, np.full(5, 30.0), np.full(5, -40.0)], 1)
    lift = np.maximum(floor - l0, 0.0)
    lifted = t.copy()
    lifted[:, 0] = np.maximum(l0, floor)
    out = oog_clip.blackfade_targets(m, lifted, lift, floor, p, fn)
    assert np.allclose(out[0], lifted[0])                # not lifted: as is
    assert np.allclose(out[:, 0], lifted[:, 0])          # L* untouched
    h_in = np.arctan2(lifted[:, 2], lifted[:, 1])
    h_out = np.arctan2(out[:, 2], out[:, 1])
    assert np.allclose(h_in, h_out)                      # hue kept
    c = np.hypot(out[:, 1], out[:, 2])
    assert (np.diff(c) < 0).all()                        # deeper, greyer


def test_the_clip_reads_the_fade_only_under_its_flag():
    src = Path(oog_clip.__file__).read_text(encoding="utf-8")
    i = src.index("def clip_nodes(")
    j = src.find("\ndef ", i + 10)
    body = src[i:] if j < 0 else src[i:j]
    assert 'if p.get("a56_on"):' in body
    assert body.count("blackfade_targets(") == 1


def test_the_hue_smoothing_keeps_a_constant_ratio_and_narrows_a_jump():
    flat = np.full(72, 2.5)
    assert np.allclose(oog_clip.smooth_hue_ratio(flat, 20.0), 2.5)
    step = np.where(np.arange(72) < 36, 0.2, 7.0)
    sm = oog_clip.smooth_hue_ratio(step, 20.0)
    assert np.abs(np.diff(np.log(sm))).max() < np.abs(np.diff(np.log(step))).max() / 3
    assert (sm > 0.2 - 1e-9).all() and (sm < 7.0 + 1e-9).all()
    assert np.allclose(oog_clip.smooth_hue_ratio(step, 0.0), step)
