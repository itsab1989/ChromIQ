"""Research Agent 82 (a82-green): RGB colorimetric greens, clipped nodes near the black (fine table) and at the
green cusp (coarse table) smoothed; printable nodes and other hues untouched."""
import numpy as np

from workflow.profile_engine import builder, purecolprof as P


def _grid(g):
    L = np.linspace(0, 100, g)
    ab = np.linspace(-128, 127, g)
    return np.stack(np.meshgrid(L, ab, ab, indexing="ij"), -1).reshape(-1, 3)


def _hue(nl):
    return np.degrees(np.arctan2(nl[:, 2], nl[:, 1])) % 360


def test_token_is_registered_and_off_by_default():
    assert P.A82_TOKEN in builder.ENGINE_CANDIDATE_TOKENS
    assert P.A82_TOKEN not in builder.ACCURATE_DEFAULT_TOKENS
    assert P.a82_params(builder.ACCURATE_DEFAULT_TOKENS) is None
    assert P.A82_CUSP_TOKEN in builder.ENGINE_CANDIDATE_TOKENS
    p = P.a82_params({P.A82_TOKEN})
    assert p["dark"] and not p["cusp"]
    assert P.a82_params({P.A82_CUSP_TOKEN})["cusp"]


def test_dark_spike_on_a_clipped_green_node_is_smoothed_and_nothing_else_moves():
    g = 33
    nl = _grid(g)
    rng = np.random.default_rng(1)
    tab = rng.uniform(0.2, 0.3, (len(nl), 3))
    res = np.where(np.hypot(nl[:, 1], nl[:, 2]) > 10, 5.0, 0.0)
    green = (_hue(nl) >= 90) & (_hue(nl) <= 170)
    i = int(np.flatnonzero((np.abs(nl[:, 0] - 9.375) < 1e-6) & green & (res > 1))[0])
    tab[i] = [0.0, 0.9, 0.0]                         # the edge snap
    out = P.a82_dark(tab, nl, res, g, P.a82_params({P.A82_TOKEN}), black_l=3.0)
    assert np.abs(out[i] - tab[i]).max() > 0.2      # the spike is pulled toward its neighbours
    moved = np.abs(out - tab).max(1) > 0
    assert not moved[res <= 1.0].any()               # printable nodes never change
    assert not moved[~green].any()                   # other hues never change
    assert not moved[nl[:, 0] > 3.0 + P.A82["dark_l"] + P.A82["dark_f"]].any()


def test_coarse_cusp_is_rounded_only_on_clipped_green_nodes():
    gf, gc = 33, 17
    nl = _grid(gf)
    res = np.where(np.hypot(nl[:, 1], nl[:, 2]) > 60, 30.0, 0.0)
    st = (gf - 1) // (gc - 1)
    nlc = nl.reshape(gf, gf, gf, 3)[::st, ::st, ::st].reshape(-1, 3)
    v = 1.0 - np.abs(nlc[:, 0] - 56.25) / 50.0      # a cusp (peak) at L 56.25
    sub = np.stack([v, v, v], 1)
    p = P.a82_params({P.A82_TOKEN})
    assert P.a82_coarse(sub, nl, res, gf, gc, p, black_l=3.0, white_l=100.0) is sub   # not part of a82-green
    out = P.a82_coarse(sub, nl, res, gf, gc, P.a82_params({P.A82_CUSP_TOKEN}), black_l=3.0, white_l=100.0)
    h = _hue(nlc)
    sel = ((np.hypot(nlc[:, 1], nlc[:, 2]) > 60) & (h >= 90) & (h <= 170)
           & (nlc[:, 0] >= 33.0) & (nlc[:, 0] <= 90.0))
    assert np.array_equal(out[~sel], sub[~sel])
    k = int(np.flatnonzero(sel & (np.abs(nlc[:, 0] - 56.25) < 1e-6))[0])
    assert out[k, 0] < sub[k, 0]                    # the peak node is lowered (rounded)
