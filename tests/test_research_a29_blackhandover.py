"""Agent 29a (2026-10-06): research token "a29-blackhandover".

Battery v3.1 cluster 1 (ProfileEngineResearch/Findings/agent27-01 s6.3): the
Maximum accuracy black stops at the darkest NEUTRAL point (C* < 1) while
colprof's black is the deeper, slightly tinted one, so on printers whose
deepest black is tinted ours was 0.6..5.3 L* lighter. The token keeps the
grey axis neutral down to its neutral black and then hands it over to a
deeper black with C* rising smoothly; perceptual and saturation put the
source black on that black. Off by default.
"""
import numpy as np
import pytest

from workflow.profile_engine import b2a
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates,
                                             candidates_from_env)

TOKEN = "a29-blackhandover"


class _ToyCmyk:
    """A smooth CMYK model whose K ink is yellowish (``tint`` b* at K=1):
    under a 150 % limit there is not ink enough left to cancel the tint at
    full K, so the neutral axis ends well above the deepest black."""

    n_channels = 4

    def __init__(self, tint: float):
        self.tint = tint
        self.nodes = np.array([tint])          # hashed by the cloud memo
        self.curves = np.zeros(1)

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        c, m, y, k = d.T
        L = 100 * (1 - .3 * c) * (1 - .3 * m) * (1 - .2 * y) * (1 - .8 * k)
        a = 40 * (m - .5 * c - .5 * y) * L / 100
        b = (40 * (y - .5 * c - .5 * m) * L / 100
             + self.tint * k * (1 - .5 * c))
        return np.column_stack([L, a, b])


_KW = dict(channel_letters=list("CMYK"), is_additive=False, ink_limit=150.0)


def _axes(tint):
    model = _ToyCmyk(tint)
    axis = b2a.neutral_axis(model, accurate=True, **_KW)
    return model, axis, b2a.blackhandover_axis(model, axis, **_KW)


def test_the_token_is_known_and_off_by_default():
    assert TOKEN in ENGINE_CANDIDATE_TOKENS
    assert TOKEN not in ACCURATE_DEFAULT_TOKENS
    assert TOKEN not in accurate_candidates(frozenset())
    assert TOKEN in accurate_candidates({TOKEN})
    assert TOKEN in candidates_from_env(f"{TOKEN},ucs")


def test_a_tinted_deep_black_is_reached_below_the_neutral_black():
    model, axis, out = _axes(6.0)
    assert out.get("handover") is True
    assert out["neutral_l_black"] == pytest.approx(axis["l_black"], abs=0.05)
    # deeper by far, and its tint bounded by the ladder's widest step
    assert out["l_black"] < axis["l_black"] - 3.0
    lab = model.predict(out["black"])[0]
    assert lab[0] == pytest.approx(out["l_black"], abs=1e-6)
    assert np.hypot(lab[1], lab[2]) <= max(b2a._HANDOVER_LADDER) + 1e-6
    # the ink limit holds along the whole hand-over
    ok = np.asarray(out["ok"], bool)
    dev = np.asarray(out["dev"], float)
    assert (dev[ok].sum(1) <= 1.5 + 1e-6).all()


def test_the_neutral_part_of_the_axis_is_untouched():
    _, axis, out = _axes(6.0)
    ls = np.asarray(axis["l"])
    above = ls >= axis["l_black"]
    assert np.array_equal(np.asarray(out["dev"])[above],
                          np.asarray(axis["dev"])[above])
    assert np.array_equal(np.asarray(out["ok"])[above],
                          np.asarray(axis["ok"])[above])


def test_the_hand_over_is_monotone_and_its_chroma_rises_smoothly():
    model, axis, out = _axes(6.0)
    ok = np.asarray(out["ok"], bool)
    lab = model.predict(np.asarray(out["dev"])[ok])     # light to dark
    assert (np.diff(lab[:, 0]) <= 1e-6).all()
    below = lab[:, 0] < axis["l_black"] - 1e-6
    chroma = np.hypot(lab[below, 1], lab[below, 2])
    assert len(chroma) >= 4
    # no step of the hand-over jumps by more than a third of the full tint
    assert np.abs(np.diff(chroma)).max() < chroma.max() / 3 + 1e-6


def test_the_mapped_intents_end_at_the_exact_black_or_at_the_chroma_cap():
    model, axis, out = _axes(6.0)
    ls, ds, lb, bk = b2a.axis_points(out)
    assert (np.diff(ls) > 0).all()
    assert lb == pytest.approx(out["l_black"]) and np.allclose(bk, out["black"])
    ls1, ds1, lb1, bk1 = b2a.axis_points(out, chroma_cap=1.0)
    lab1 = model.predict(bk1)[0]
    assert np.hypot(lab1[1], lab1[2]) <= 1.0 + 1e-9
    assert out["l_black"] < lb1 <= axis["l_black"] + 1e-6
    # without a hand-over: the accepted grid and the axis's own black
    _, axis0, out0 = _axes(0.0)
    ls0, _, lb0, bk0 = b2a.axis_points(out0, chroma_cap=1.0)
    assert lb0 == axis0["l_black"] and np.array_equal(bk0, axis0["black"])
    assert len(ls0) == int(np.asarray(axis0["ok"]).sum())


def test_no_hand_over_when_the_deepest_black_is_neutral():
    _, axis, out = _axes(0.0)
    assert out is axis


def test_the_target_ab_curve_hands_over_with_zero_slope_at_both_ends():
    ab = np.array([1.0, 3.0])
    ls = np.linspace(10.0, 30.0, 201)
    t = b2a.handover_target_ab(ls, l_top=25.0, l_deep=15.0, ab_deep=ab)
    assert np.allclose(t[ls >= 25.0], 0.0)
    assert np.allclose(t[ls <= 15.0], ab)
    c = np.hypot(t[:, 0], t[:, 1])
    assert (np.diff(c) <= 1e-12).all()                 # rises toward the black
    # zero slope at both joins (smoothstep)
    d = np.abs(np.diff(c))
    assert d[(ls[1:] > 24.8) & (ls[1:] <= 25.0)].max() < 0.01
    assert d[(ls[1:] > 15.0) & (ls[1:] < 15.2)].max() < 0.01


def test_the_source_black_lands_on_the_destination_black():
    src = np.array([0.0, 6.25, 12.5, 25.0, 50.0, 100.0])
    # the engine model's lightness of colprof's black is 4 L* too light
    tl = np.array([9.0, 11.0, 15.0, 26.0, 50.0, 100.0])
    out = b2a.anchor_column_black(tl, src, black_l=5.0)
    assert out[0] == pytest.approx(5.0)
    assert out[-1] == pytest.approx(100.0) and out[-2] == pytest.approx(50.0)
    assert (np.diff(out) >= 0).all()                   # light to dark: monotone
    # already on the black: nothing moves
    assert np.allclose(b2a.anchor_column_black(tl, src, black_l=9.0), tl)


@pytest.mark.slow
def test_a_build_with_the_token_hands_the_axis_over(tmp_path, monkeypatch):
    """Wiring: a real Maximum accuracy build asks for the hand-over only
    when the token is on."""
    from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
    from workflow.profile_engine.builder import BuildSettings, build_profile
    calls = []
    real = b2a.blackhandover_axis

    def spy(model, axis, **kw):
        calls.append(kw.get("ink_limit"))
        return real(model, axis, **kw)

    monkeypatch.setattr(b2a, "blackhandover_axis", spy)
    p = PRINTERS["S3"]
    chart = make_chart(p, 400)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / "S3.ti3", p, chart, xyz, refl)
    for tokens, expect in ((frozenset(), 0), (frozenset({TOKEN}), 1)):
        calls.clear()
        build_profile(ti3, tmp_path / f"S3-{expect}.icc",
                      BuildSettings(quality="l", gammap_mode="accurate",
                                    engine_candidates=tokens))
        assert len(calls) == expect


# --- a29-darkmodel: the forward fit weighs the dark corner more --------------

def test_the_dark_model_token_is_known_and_off_by_default():
    assert "a29-darkmodel" in ENGINE_CANDIDATE_TOKENS
    assert "a29-darkmodel" not in ACCURATE_DEFAULT_TOKENS
    from workflow.profile_engine.builder import dark_model_weights
    lab = np.array([[0.0, 0, 0], [25.0, 0, 0], [50.0, 0, 0], [90.0, 0, 0]])
    assert dark_model_weights(lab, frozenset()) is None
    w = dark_model_weights(lab, {"a29-darkmodel"})
    assert w[0] == pytest.approx(4.0) and w[1] == pytest.approx(2.5)
    assert w[2] == pytest.approx(1.0) and w[3] == pytest.approx(1.0)
    w6 = dark_model_weights(lab, {"a29-darkmodel-a6-l25"})
    assert w6[0] == pytest.approx(7.0) and w6[1] == pytest.approx(1.0)


@pytest.mark.slow
def test_the_dark_model_token_reaches_the_forward_fit(tmp_path, monkeypatch):
    from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
    from workflow.profile_engine import accuracy
    from workflow.profile_engine.builder import BuildSettings, build_profile
    seen = []
    real = accuracy.fit_forward_model_accurate

    def spy(*a, row_weights=None, **kw):
        seen.append(None if row_weights is None else np.asarray(row_weights).copy())
        return real(*a, row_weights=row_weights, **kw)

    monkeypatch.setattr(accuracy, "fit_forward_model_accurate", spy)
    p = PRINTERS["S1"]
    chart = make_chart(p, 300)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / "S1.ti3", p, chart, xyz, refl)
    for tokens in (frozenset(), frozenset({"a29-darkmodel"})):
        seen.clear()
        build_profile(ti3, tmp_path / f"S1-{len(tokens)}.icc",
                      BuildSettings(quality="l", gammap_mode="accurate",
                                    engine_candidates=tokens))
        w = seen[0]
        if tokens:
            assert w is not None and w.max() > 1.5 and w.min() >= 1.0
        else:
            assert w is None or np.allclose(w, np.round(w))


def test_the_ink_variant_caps_the_deep_black_at_chroma_two():
    assert "a29-blackhandover-ink" in ENGINE_CANDIDATE_TOKENS
    assert "a29-blackhandover-ink" not in ACCURATE_DEFAULT_TOKENS
    model = _ToyCmyk(6.0)
    axis = b2a.neutral_axis(model, accurate=True, **_KW)
    out = b2a.blackhandover_axis(model, axis, ladder=(1.0, 2.0), **_KW)
    assert out.get("handover") is True
    lab = model.predict(out["black"])[0]
    assert np.hypot(lab[1], lab[2]) <= 2.0 + 1e-6
    assert out["l_black"] < axis["l_black"]
