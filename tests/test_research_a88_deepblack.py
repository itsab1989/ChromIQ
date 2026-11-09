"""Research Agent 88: the three-level deepest black on a tinted printer black (a88-black-balanced,
a88-black-deepest; no token = Neutral = integration 11). Toy model from tests/test_research_a85_bpc.py."""
import numpy as np

from workflow.profile_engine import builder
from workflow.profile_engine import purecolprof as P

from test_research_a85_bpc import Toy, _column_case


def test_a88_levels_are_registered_and_off_by_default():
    for t in P.A88_LEVELS:
        assert t in builder.ENGINE_CANDIDATE_TOKENS
        assert t not in builder.ACCURATE_DEFAULT_TOKENS
    assert P.a88_params(builder.ACCURATE_DEFAULT_TOKENS) is None
    assert P.a88_params({"a88-black-balanced"})["level"] == "balanced"
    assert P.a88_params({"a88-black-deepest"})["level"] == "deepest"
    # both given: Deepest wins
    assert P.a88_params(set(P.A88_LEVELS))["level"] == "deepest"


def test_a88_dark_end_reports_black_and_darkest_neutral():
    m = Toy()
    d = P.a88_dark_end(m)
    assert np.allclose(d["black"], [4.0, 2.2, -3.4])
    assert d["neutral"] is not None and np.hypot(d["neutral"][1], d["neutral"][2]) <= 1.0
    assert d["gap"] == d["neutral"][0] - d["black"][0] and d["gap"] > 1.5


def test_a88_near_neutral_black_is_untouched_at_every_level():
    m = Toy(tint=0.0)
    nl, tab, res, tables = _column_case(m)
    for t in P.A88_LEVELS:
        out, info = P.a88_black(tab, nl, res, m, P.a88_params({t}), tables)
        assert not info["fires"] and out is tab


def _darkest_column_print(m, nl, out):
    col = np.hypot(nl[:, 1], nl[:, 2]) < 0.5
    k = np.flatnonzero(col & (nl[:, 0] > 0.5) & (nl[:, 0] < 4.0))[0]
    return np.asarray(m.predict(out[k:k + 1]))[0]


def test_a88_deepest_and_balanced_order_and_cast():
    m = Toy()
    nl, tab, res, tables = _column_case(m)
    dn, _ = P.a88_black(tab, nl, res, m, P.a88_params({"a88-black-deepest"}), tables)
    bl, ib = P.a88_black(tab, nl, res, m, P.a88_params({"a88-black-balanced"}), tables)
    neutral = _darkest_column_print(m, nl, tab)
    deep = _darkest_column_print(m, nl, dn)
    bal = _darkest_column_print(m, nl, bl)
    assert deep[0] < bal[0] < neutral[0]
    # Balanced: within one just-noticeable cast (penalty, so a little slack)
    assert P.a88_cast(bal)[0] <= P.A88["cast"] + 0.15
    assert P.a88_cast(deep)[0] > P.A88["cast"]
    # only the dark clipped column moves; the L* 0 plane (the profile's black) never does
    for out in (dn, bl):
        moved = np.abs(out - tab).max(1) > 1e-9
        col = np.hypot(nl[:, 1], nl[:, 2]) < 0.5
        assert moved.any() and not moved[~col].any() and not moved[nl[:, 0] < 0.5].any()
        assert not moved[res <= 0.5].any()
