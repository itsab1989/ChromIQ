"""Agent 45 (2026-10-07): research tokens "a45-c1space" and "a45-darkend".

The perceptual (and saturation) dark end of R-CMYK-default-i1iSis with the
held black of a43-shadowdetail (D-28) banded at 4-6 x colprof's and made the
colour-to-black ramps dip (ProfileEngineResearch
Findings/agent45-01-darkend.md). Part 1 ("a45-c1space", also on with
"a45-darkend"): the a42 B2A curve space is made C1 (no slope corner where a
floored shaper interval meets its neighbours). Parts 2/3 ("a45-darkend",
only where a43's data floor acts): the black is the oracle's own perceptual
black device (its neighbouring nodes are the oracle's), within the measured
data, reached from the top of the hand-over zone on one straight device
path, monotone in target L* by construction. Off by default.
"""
import inspect

import numpy as np

from workflow.profile_engine import b2a, builder, gamut_map
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)


def _collapsed_shaper():
    """21 knots, one interval almost flat (slope 0.13), like i1iSis K."""
    d = np.full(20, 1.0)
    d[12] = 0.13
    y = np.concatenate([[0.0], np.cumsum(d)])
    return (y / y[-1])[None, :]


def test_the_tokens_are_known_and_off_by_default():
    for tok in (b2a.A45_C1_TOKEN, b2a.A45_TOKEN):
        assert tok in ENGINE_CANDIDATE_TOKENS
        assert tok not in ACCURATE_DEFAULT_TOKENS
        assert tok not in accurate_candidates(frozenset())
    assert b2a.a45_c1({b2a.A45_TOKEN}) and b2a.a45_c1({b2a.A45_C1_TOKEN})
    assert not b2a.a45_c1({b2a.A42_TOKEN})


def test_the_smooth_space_is_c1_monotone_and_keeps_the_floor():
    c = _collapsed_shaper()
    plain = b2a.b2a_space_curves(c)
    smooth = b2a.b2a_space_curves(c, smooth=True)
    assert plain.shape == (1, 21)
    assert smooth.shape == (1, 20 * b2a.A45_FINE + 1)
    assert smooth[0, 0] == 0.0 and abs(smooth[0, -1] - 1.0) < 1e-12
    slope = np.diff(smooth[0]) * (smooth.shape[1] - 1)
    assert slope.min() > 0.45                      # the floor, renormalised
    # piecewise-constant floored slope jumps by > 1.0 at the interval;
    # the smooth one changes by at most one box step per fine sample
    plain_slope = np.repeat(np.diff(plain[0]) * 20, b2a.A45_FINE)
    assert np.abs(np.diff(plain_slope)).max() > 0.4
    assert np.abs(np.diff(slope)).max() < 0.05


def test_a_shaper_without_a_flat_interval_stays_untouched():
    c = np.linspace(0.0, 1.0, 21)[None, :] ** 1.2
    assert b2a.b2a_space_curves(c, smooth=True) is None


def test_reexpress_keeps_node_devices_on_a_finer_space():
    c = _collapsed_shaper()
    sp = b2a.b2a_space_curves(c, smooth=True)
    dev = np.linspace(0.0, 1.0, 37)
    shaped = np.interp(dev, np.linspace(0, 1, 21), c[0])[:, None]
    out = b2a.reexpress(shaped, c, sp)
    back = np.interp(out[:, 0], sp[0], np.linspace(0, 1, sp.shape[1]))
    assert np.abs(back - dev).max() < 1e-9
    # same-length spaces give exactly what they gave before
    plain = b2a.b2a_space_curves(c)
    xp = np.linspace(0, 1, 21)
    old = np.interp(np.interp(shaped[:, 0], c[0], xp), xp, plain[0])
    assert np.array_equal(b2a.reexpress(shaped, c, plain)[:, 0], old)


class _Model:
    n_channels = 4

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        return np.column_stack([60.0 - 40.0 * d[:, 3] - 3.0 * d[:, 0],
                                0 * d[:, 0], 2.0 * d[:, 2]])


def _axis():
    m = _Model()
    ls = np.arange(0.0, 60.0, 0.5)
    k = np.clip((60.0 - ls) / 40.0, 0, 1)
    dev = np.column_stack([0 * ls, 0 * ls, 0 * ls, k])
    nb = np.array([0.2, 0.0, 0.0, 0.95])
    return {"l": ls, "ok": ls >= float(m.predict(nb)[0, 0]), "dev": dev,
            "handover": True, "neutral_black": nb,
            "neutral_l_black": float(m.predict(nb)[0, 0]),
            "l_black": 15.0, "black": np.array([0.3, 0, 0, 1.0])}


def test_the_dark_path_ends_at_the_black_and_is_monotone_in_target_l():
    m = _Model()
    ax = _axis()
    blk = np.array([0.1, 0.1, 0.1, 1.0])
    l_n, l_b = ax["neutral_l_black"], float(m.predict(blk)[0, 0])
    p = b2a.a45_dark_path(m, ax, blk, l_deep=15.0, l_floor=l_b - 0.5)
    assert abs(p["l_b"] - l_b) < 1e-9
    assert abs(p["l_a"] - (l_n + (l_n - 15.0))) < 1e-9     # a42's zone top
    assert np.allclose(p["a"], [0, 0, 0, np.interp(p["l_a"], ax["l"],
                                                   ax["dev"][:, 3])])
    tl = np.linspace(l_b - 1, p["l_a"] + 1, 200)
    d = b2a.a45_path_devices(tl, p)
    assert np.allclose(d[tl <= l_b], blk)
    assert np.allclose(d[tl >= p["l_a"]], p["a"])
    for c in range(4):                       # each channel monotone in L*
        s_ = np.sign(np.diff(d[:, c]))
        assert (s_ >= 0).all() or (s_ <= 0).all()
    assert d.min() >= 0 and d.max() <= 1


def test_no_planned_path_where_it_does_not_apply():
    m = _Model()
    ax = _axis()
    blk = np.array([0.1, 0.1, 0.1, 1.0])
    l_b = float(m.predict(blk)[0, 0])
    kw = dict(l_deep=15.0, l_floor=l_b - 0.5)
    assert b2a.a45_dark_path(m, ax, None, **kw) is None          # no oracle
    assert b2a.a45_dark_path(m, dict(ax, handover=False), blk, **kw) is None
    # the oracle black lighter than the neutral black
    assert b2a.a45_dark_path(m, ax, np.array([0, 0, 0, 0.5]), **kw) is None
    # the oracle black below the measured data (D-28)
    assert b2a.a45_dark_path(m, ax, blk, l_deep=15.0,
                             l_floor=l_b + 0.5) is None


def test_the_wiring_sits_behind_the_tokens():
    src = inspect.getsource(gamut_map.build_mapped_b2a)
    assert "b2a_mod.A45_TOKEN in _cands" in src
    assert "a45_c1" in src
    bsrc = inspect.getsource(builder)
    assert "a45-darkend" in bsrc and "a45-c1space" in bsrc
    assert "smooth=b2a_mod.a45_c1(candidates)" in bsrc


def test_a45b_shaper_floor_keeps_every_interval_open():
    from workflow.profile_engine import forward_model as fm
    rng = np.random.default_rng(3)
    dev = rng.random((400, 1))
    # an ink that does nothing between 0.6 and 0.65 (a flat stretch)
    x = np.where(dev[:, 0] < 0.6, dev[:, 0],
                 np.where(dev[:, 0] < 0.65, 0.6, dev[:, 0] - 0.05))
    lab = np.column_stack([100 - 90 * x, 0 * x, 0 * x])
    try:
        b2a.set_research_tokens({b2a.A45B_TOKEN}, is_additive=False)
        assert fm.SHAPER_FLOOR["slope"] == b2a.A42_FLOOR
        m = fm.fit_forward_model(dev, lab, grid=5, curve_rounds=2)
        h = 1.0 / (m.curves.shape[1] - 1)
        assert np.diff(m.curves[0]).min() >= b2a.A42_FLOOR * h - 1e-12
    finally:
        b2a.set_research_tokens((), is_additive=None)
    assert fm.SHAPER_FLOOR["slope"] is None
    m0 = fm.fit_forward_model(dev, lab, grid=5, curve_rounds=2)
    assert np.diff(m0.curves[0]).min() > 0          # still monotone
