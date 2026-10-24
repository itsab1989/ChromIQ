"""Research Agent 78 (a78-rgbsmooth): the RGB colorimetric table's clipped coarse nodes are smoothed along L*."""
import numpy as np

from workflow.profile_engine import builder, purecolprof as P


def _grid(g):
    L = np.linspace(0, 100, g)
    ab = np.linspace(-128, 127, g)
    return np.stack(np.meshgrid(L, ab, ab, indexing="ij"), -1).reshape(-1, 3)


def test_token_is_registered_and_off_by_default():
    assert P.A78_TOKEN in builder.ENGINE_CANDIDATE_TOKENS
    assert P.A78_TOKEN not in builder.ACCURATE_DEFAULT_TOKENS
    assert P.a78_params(builder.ACCURATE_DEFAULT_TOKENS) is None
    assert P.a78_params({P.A78_TOKEN}) == P.A78_SMOOTH


def test_a_knee_along_L_is_spread_and_printable_nodes_stay():
    gf, gc = 33, 17
    nl = _grid(gf)
    res = np.where(np.hypot(nl[:, 1], nl[:, 2]) > 60, 30.0, 0.0)     # far out of gamut: clipped
    st = (gf - 1) // (gc - 1)
    nlc = nl.reshape(gf, gf, gf, 3)[::st, ::st, ::st].reshape(-1, 3)
    # device value with a knee in L* at L 50 (slope 0 below, 1 above)
    v = np.clip((nlc[:, 0] - 50.0) / 50.0, 0, 1)
    sub = np.stack([v, v, v], 1)
    out = P.a78_smooth(sub, nl, res, gf, gc, P.A78_SMOOTH)
    clip = ((np.hypot(nlc[:, 1], nlc[:, 2]) > 60) & (np.linalg.norm(nlc, axis=1) > 1)
            & (nlc[:, 0] <= 100.0 - P.A78_SMOOTH["top"]))
    # printable nodes untouched
    assert np.array_equal(out[~clip], sub[~clip])
    # the knee node (L 50) is lifted, the second difference along L shrinks
    x = out.reshape(gc, gc, gc, 3)[:, 0, 0, 0]
    x0 = sub.reshape(gc, gc, gc, 3)[:, 0, 0, 0]
    assert x[8] > x0[8]
    assert np.abs(np.diff(x, 2)).max() < 0.5 * np.abs(np.diff(x0, 2)).max()


def test_the_pale_region_is_left_alone():
    gf, gc = 33, 17
    nl = _grid(gf)
    res = np.full(len(nl), 30.0)
    st = (gf - 1) // (gc - 1)
    nlc = nl.reshape(gf, gf, gf, 3)[::st, ::st, ::st].reshape(-1, 3)
    rng = np.random.default_rng(78)
    sub = rng.random((len(nlc), 3))
    out = P.a78_smooth(sub, nl, res, gf, gc, P.A78_SMOOTH, white_l=96.0)
    pale = nlc[:, 0] > 96.0 - P.A78_SMOOTH["top"]
    assert np.array_equal(out[pale], sub[pale])
    assert not np.array_equal(out[~pale], sub[~pale])
