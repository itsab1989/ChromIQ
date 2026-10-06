"""Agent 35 (2026-10-07): research tokens "a35-percblack-blend",
"a35-percblack-deep" and "a35-oracle-limit".

Basti's decision (2026-10-06 night): on printers whose deepest black is
tinted, the perceptual and saturation black goes to the same deep (tinted,
capped) black the colorimetric table ends at. Option 3, the BLEND: neutral
through the shadows, hand-over only in the last few L*, its width taken
from the L* gap between the neutral and the deep black (widened only as far
as the measured hand-over path needs to stay printable). Option 1, DEEP:
colprof's own way to its black (Argyll gamut/gammap.c gmm_bendBP: a band as
wide as the black's a*b* distance from neutral). "a35-oracle-limit": the
colprof oracle runs with the build's ink limit (without -l colprof takes
the .ti3 limit minus 10 %, which made XKH september's perceptual black
3.8 L* light). All off by default (ProfileEngineResearch
Findings/agent35-01-percblack.md).
"""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from workflow.profile_engine import b2a, gamut_map
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates,
                                             candidates_from_env)

TOKENS = ("a35-percblack-blend", "a35-percblack-deep", "a35-oracle-limit")


class _ToyCmyk:
    """agent29a's toy: a smooth CMYK model whose K ink is yellowish, so
    under a 150 % limit the neutral axis ends well above the deepest
    black."""

    n_channels = 4

    def __init__(self, tint: float):
        self.tint = tint
        self.nodes = np.array([tint])
        self.curves = np.zeros(1)

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        c, m, y, k = d.T
        L = 100 * (1 - .3 * c) * (1 - .3 * m) * (1 - .2 * y) * (1 - .8 * k)
        a = 40 * (m - .5 * c - .5 * y) * L / 100
        b = (40 * (y - .5 * c - .5 * m) * L / 100
             + self.tint * k * (1 - .5 * c))
        return np.column_stack([L, a, b])


class _ToyRgb:
    """An RGB printer whose device black is bluish (b* -6 at RGB 0)."""

    n_channels = 3

    def __init__(self):
        self.nodes = np.array([1.0])
        self.curves = np.zeros(1)

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        r, g, b = d.T
        L = 20 + 80 * (0.3 * r + 0.5 * g + 0.2 * b)
        a = 40 * (r - g)
        bb = 40 * (g - b) - 6.0 * (1 - (r + g + b) / 3) ** 4
        return np.column_stack([L, a, bb])


def test_the_tokens_are_known_and_off_by_default():
    for tok in TOKENS:
        assert tok in ENGINE_CANDIDATE_TOKENS
        assert tok not in ACCURATE_DEFAULT_TOKENS
        assert tok not in accurate_candidates(frozenset())
        assert tok in accurate_candidates({tok})
    both = candidates_from_env(",".join(TOKENS))
    assert set(TOKENS) <= both
    assert b2a.a35_mode(both) == "deep"          # deep wins when both given
    assert b2a.a35_mode({"a35-percblack-blend"}) == "blend"
    assert b2a.a35_mode(accurate_candidates(frozenset())) is None


@pytest.mark.parametrize("mode", ["blend", "deep"])
def test_the_hand_over_fraction_is_monotone_and_c1(mode):
    l_deep, w = 20.0, 4.0
    ls = np.linspace(15.0, 30.0, 3001)
    f = b2a.percblack_fraction(ls, l_deep=l_deep, width=w, mode=mode)
    assert (f[ls >= l_deep + w] == 0.0).all()
    assert (f[ls <= l_deep] == 1.0).all()
    assert (np.diff(f) <= 1e-12).all()             # falls as L* rises
    df = np.gradient(f, ls)
    top = np.argmin(np.abs(ls - (l_deep + w)))
    assert abs(df[top]) < 1e-2                     # zero slope at the top
    if mode == "blend":
        bot = np.argmin(np.abs(ls - l_deep))
        assert abs(df[bot]) < 1e-2                 # smoothstep: also at 0


def test_the_deep_fraction_is_argylls_bend():
    # gammap.c l. 1426-1436: t = smoothstep(u); ty = smoothstep(t);
    # t = (1 - t) * ty + t * t
    u = 0.37
    t = u * u * (3 - 2 * u)
    ty = t * t * (3 - 2 * t)
    want = (1 - t) * ty + t * t
    got = b2a.percblack_fraction(np.array([20.0 + 4.0 * (1 - u)]),
                                 l_deep=20.0, width=4.0, mode="deep")[0]
    assert got == pytest.approx(want, abs=1e-12)


def test_the_blend_width_is_the_gap_widened_only_to_stay_printable():
    # a path whose tint rises linearly from the neutral black (L* 24) to
    # the deep black (L* 20, C* 4): smoothstep covers it at 9/8 of the gap
    pl = np.linspace(24.0, 20.0, 81)
    pc = np.linspace(0.0, 4.0, 81)
    w = b2a.percblack_width(pl, pc, l_neutral=24.0, l_deep=20.0,
                            c_deep=4.0, mode="blend")
    assert w == pytest.approx(4.0 * 1.125)
    f = b2a.percblack_fraction(pl, l_deep=20.0, width=w, mode="blend")
    assert (f >= pc / 4.0 - 1e-6).all()
    # a path that stays nearly neutral until close to the black needs no
    # widening: the gap itself
    pc2 = 4.0 * ((24.0 - pl) / 4.0) ** 3
    assert b2a.percblack_width(pl, pc2, l_neutral=24.0, l_deep=20.0,
                               c_deep=4.0, mode="blend") == pytest.approx(4.0)
    # deep: the black's chroma (brad), never narrower than printable
    assert b2a.percblack_width(pl, pc, l_neutral=24.0, l_deep=20.0,
                               c_deep=4.0, mode="deep") == pytest.approx(4.5)
    assert b2a.percblack_width(pl, pc * 2.5, l_neutral=24.0, l_deep=20.0,
                               c_deep=10.0, mode="deep") == pytest.approx(10.0)


def test_the_tint_ends_at_the_deep_blacks_ab():
    ab = np.array([1.0, -6.0])
    t = b2a.percblack_tint(np.array([30.0, 20.0, 10.0]), l_deep=20.0,
                           ab_deep=ab, width=4.0, mode="blend")
    np.testing.assert_allclose(t, [[0, 0], ab, ab])
    # deep: towards the straight white-to-black axis (scaled by L*)
    t = b2a.percblack_tint(np.array([20.0, 22.0]), l_deep=20.0, ab_deep=ab,
                           width=4.0, mode="deep")
    np.testing.assert_allclose(t[0], ab)
    f = b2a.percblack_fraction(np.array([22.0]), l_deep=20.0, width=4.0,
                               mode="deep")[0]
    np.testing.assert_allclose(t[1], f * (78.0 / 80.0) * ab)


def test_the_rgb_hand_over_path_darkens_monotonically_to_rgb_0():
    model = _ToyRgb()
    l0 = float(model.predict(np.zeros((1, 3)))[0, 0])
    l_nb, d_nb = b2a.rgb_neutral_black(model, l0)
    assert l_nb > l0                                 # RGB 0 is tinted
    pl, pd, pc = b2a.rgb_handover_path(model, d_nb)
    assert (np.diff(pl) < 0).all()
    np.testing.assert_allclose(pd[-1], 0.0)
    assert pc[-1] == pytest.approx(6.0, abs=1e-6)
    np.testing.assert_allclose(b2a.path_device_at([pl[-1]], pl, pd)[0], 0.0)


def test_a_band_node_keeps_the_path_where_the_inversion_lands_further():
    model = _ToyRgb()
    tgt = np.array([[25.0, 0.0, -3.0]])
    far, near = np.array([[0.4, 0.4, 0.4]]), np.array([[0.06, 0.06, 0.06]])
    got = b2a.percblack_band_devices(model, tgt, far, near)
    np.testing.assert_allclose(got, near)
    got = b2a.percblack_band_devices(model, tgt, near, far)
    np.testing.assert_allclose(got, near)


def test_the_band_lands_the_column_on_the_deep_black_monotonically():
    model = _ToyCmyk(6.0)
    kw = dict(channel_letters=list("CMYK"), is_additive=False,
              ink_limit=150.0)
    axis = b2a.neutral_axis(model, accurate=True, **kw)
    out = b2a.blackhandover_axis(model, axis, **kw)
    assert out.get("handover")
    lab_d = np.asarray(out["handover_lab"], float)
    w = b2a.percblack_width(out["blend_l"], out["blend_c"],
                            l_neutral=out["neutral_l_black"],
                            l_deep=out["l_black"],
                            c_deep=float(np.hypot(*lab_d[1:])), mode="blend")
    assert w >= out["neutral_l_black"] - out["l_black"] - 1e-9
    pts = b2a.axis_points(out)
    # a column from well above the band to below the deep black
    tl = np.linspace(out["l_black"] - 2.0, out["neutral_l_black"] + 6.0, 15)
    mapped = np.column_stack([tl, np.zeros_like(tl), np.zeros_like(tl)])
    col = np.arange(len(tl))
    dev = np.array([[np.interp(l, pts[0], pts[1][:, c]) for c in range(4)]
                    for l in tl])
    band = {"l_deep": out["l_black"], "ab_deep": lab_d[1:], "width": w,
            "path_l": np.asarray(out["blend_l"], float),
            "path_dev": np.asarray(out["blend_dev"], float)}
    got = gamut_map._a35_apply_band(model, dev, mapped, col, band, "blend",
                                    dict(kw, accurate=True))
    lab = model.predict(got)
    below = tl <= out["l_black"]
    np.testing.assert_allclose(got[below], out["black"][None, :].repeat(
        below.sum(), 0))
    above = tl >= out["l_black"] + w
    np.testing.assert_allclose(got[above], dev[above])   # untouched
    order = np.argsort(-tl)
    assert (np.diff(lab[order, 0]) <= 1e-6).all()        # monotone
    assert (got.sum(1) <= 1.5 + 1e-6).all()              # ink limit kept
    c = np.hypot(lab[:, 1], lab[:, 2])
    assert c[below].min() == pytest.approx(float(np.hypot(*lab_d[1:])),
                                           abs=1e-6)


def test_the_oracle_gets_the_builds_ink_limit_only_with_the_token():
    ink = SimpleNamespace(is_additive=False, ink_limit=300.0)
    rgb = SimpleNamespace(is_additive=True, ink_limit=None)

    def st(tokens, **kw):
        return SimpleNamespace(quality="m", engine_candidates=frozenset(tokens),
                               **kw)
    cp, src = Path("colprof"), Path("src.icm")
    assert not [a for a in gamut_map._oracle_args(cp, st(()), src, ink)
                if a.startswith("-l")]
    args = gamut_map._oracle_args(cp, st({"a35-oracle-limit"}), src, ink)
    assert "-l300" in args
    args = gamut_map._oracle_args(
        cp, st({"a35-oracle-limit"}, ink_limit=280.0, black_ink_limit=95.0),
        src, ink)
    assert "-l280" in args and "-L95" in args
    assert not [a for a in gamut_map._oracle_args(
        cp, st({"a35-oracle-limit"}), src, rgb) if a.startswith("-l")]
    # without the measurement (older callers) nothing changes
    assert gamut_map._oracle_args(cp, st({"a35-oracle-limit"}), src) == \
        gamut_map._oracle_args(cp, st(()), src)
