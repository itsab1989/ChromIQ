"""Agent 69 (a69-cmykport): the port of colprof's CMYK colorimetric recipe is CMYK-only and its inking curve is
Argyll's -kr curve (icxKcurve, xicc/xlut.c)."""
import numpy as np

from workflow.profile_engine import cmykport as P


def test_only_cmyk_accurate_with_token():
    t = {"a69-cmykport"}
    assert P.applies(t, accurate=True, is_additive=False, n=4, letters="CMYK")
    assert not P.applies(t, accurate=True, is_additive=True, n=3, letters="RGB")
    assert not P.applies(t, accurate=True, is_additive=False, n=3, letters="CMY")
    assert not P.applies(t, accurate=False, is_additive=False, n=4, letters="CMYK")
    assert not P.applies(set(), accurate=True, is_additive=False, n=4, letters="CMYK")


def test_kr_curve_is_argylls_ramp():
    # -kr: linear in normalised L between the two +-0.09 transition windows
    L = np.array([0.2, 0.35, 0.5, 0.65, 0.8])
    assert np.allclose(P.kcurve(L), 1.0 - L, atol=1e-12)
    # filtered ends: K 0 at white, 1 at black, monotone
    x = np.linspace(0, 1, 201)
    k = P.kcurve(x)
    assert k[-1] == 0.0 and k[0] == 1.0
    assert np.all(np.diff(k) <= 1e-12)
    assert np.allclose(P.k_target(np.array([10.0, 100.0]), 10.0), [1.0, 0.0])
