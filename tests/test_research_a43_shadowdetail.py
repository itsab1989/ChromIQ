"""Agent 43 (2026-10-07): research tokens "a43-shadowdetail" and
"a43-shadowdetail-width".

Basti saw the engine's i1iSis shadows warm and crushed next to colprof's.
Measured (ProfileEngineResearch Findings/agent43-01-shadowdetail.md): the
a35 perceptual hand-over band had fallen back to its widest width (4 x the
gap), because the hand-over path's chroma reaches the deep black's above
the deep black, so the tint ran up to L* 34; and the perceptual black lay
2.6 L* below the darkest measured patch, where the references disagree.
Part 1 (both tokens): the tint is full from where the path reaches the deep
black's chroma, the smoothstep band above it. Part 2 ("a43-shadowdetail"):
the perceptual and saturation black no deeper than the darkest measured
near-neutral patch. Off by default.
"""
import inspect

import numpy as np

from workflow.profile_engine import b2a, builder, gamut_map
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)


class _LineModel:
    """L* falls with the first channel, b* rises with the second."""

    n_channels = 4

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        return np.column_stack([21.0 - 5.0 * d[:, 0], 0.0 * d[:, 0],
                                3.0 * d[:, 1]])


def _path(chroma_of_u, n=81):
    u = np.linspace(0.0, 1.0, n)
    dev = np.column_stack([u, chroma_of_u(u) / 3.0, 0 * u, 0 * u])
    lab = _LineModel().predict(dev)
    return lab[:, 0], dev, np.hypot(lab[:, 1], lab[:, 2])


def _axis(path_l, path_dev, path_c):
    m = _LineModel()
    ls = np.arange(0.0, 100.0, 0.5)
    return {"l": ls, "ok": ls >= 15.9, "dev": np.zeros((len(ls), 4)),
            "handover": True, "l_black": float(path_l[-1]),
            "black": path_dev[-1].copy(),
            "neutral_l_black": float(path_l[0]),
            "neutral_black": path_dev[0].copy(),
            "handover_lab": m.predict(path_dev[-1:])[0],
            "blend_l": path_l, "blend_dev": path_dev, "blend_c": path_c}


def test_the_tokens_are_known_and_defaults_since_integration_6():
    for tok in (b2a.A43_TOKEN, b2a.A43_WIDTH_TOKEN):
        assert tok in ENGINE_CANDIDATE_TOKENS
        assert tok in ACCURATE_DEFAULT_TOKENS
        assert tok in accurate_candidates(frozenset())
        assert tok not in accurate_candidates({"no-" + tok})
    # D-28: the held black is the default mode
    assert b2a.a43_mode(accurate_candidates(frozenset())) == "floor"
    assert b2a.a43_mode({b2a.A43_TOKEN, b2a.A43_WIDTH_TOKEN}) == "floor"
    assert b2a.a43_mode({b2a.A43_WIDTH_TOKEN}) == "width"
    assert b2a.a43_mode(set()) is None


def test_a_path_whose_chroma_never_overshoots_keeps_a35s_band():
    pl, _, pc = _path(lambda u: 3.0 * u)          # linear: chroma ends at 3
    l_full, w = b2a.a43_band(pl, pc, l_neutral=pl[0], l_deep=pl[-1],
                             c_deep=pc[-1])
    assert l_full == pl[-1]
    assert w == b2a.percblack_width(pl, pc, l_neutral=pl[0], l_deep=pl[-1],
                                    c_deep=pc[-1], mode="blend")


def test_an_overshooting_path_no_longer_takes_the_widest_band():
    # the i1iSis shape: the chroma is at the deep black's by 40 % of the way
    pl, _, pc = _path(lambda u: 3.2 * np.minimum(u / 0.4, 1.0) - 0.2 * u)
    c_deep = float(pc[-1])
    gap = pl[0] - pl[-1]
    old = b2a.percblack_width(pl, pc, l_neutral=pl[0], l_deep=pl[-1],
                              c_deep=c_deep, mode="blend")
    assert abs(old - 4.0 * gap) < 1e-9            # a35 fell back to 4 x gap
    l_full, w = b2a.a43_band(pl, pc, l_neutral=pl[0], l_deep=pl[-1],
                             c_deep=c_deep)
    assert pl[-1] < l_full < pl[0]
    assert l_full + w < pl[0] + gap               # the band ends near the top
    above = pl >= l_full
    f = b2a.percblack_fraction(pl[above], l_deep=l_full, width=w,
                               mode="blend")
    need = np.clip(pc[above] / c_deep, 0.0, 1.0)
    assert np.all(f >= need - 1e-6)               # still printable


def test_the_measured_dark_floor_reads_the_near_neutral_patches():
    lab = np.array([[19.2, 2.0, 1.9], [12.0, 9.0, 0.0], [17.0, 1.0, 0.0],
                    [30.0, 0.0, 0.0]])
    dev = np.array([[.3, .3, 0, 1], [1, 1, 0, 1], [1, 1, 1, 1],
                    [0, 0, 0, .5]])
    assert b2a.measured_dark_floor(lab, dev) == 17.0
    assert b2a.measured_dark_floor(lab, dev, ink_limit=300.0) == 19.2
    assert b2a.measured_dark_floor(lab[1:2], dev[1:2]) is None


def test_the_perceptual_axis_ends_at_the_data_floor():
    m = _LineModel()
    pl, pd, pc = _path(lambda u: 3.0 * u)         # L* 21 -> 16
    ax = _axis(pl, pd, pc)
    f = b2a.a43_floor_axis(m, ax, 18.0)
    assert abs(f["l_black"] - 18.0) < 1e-6
    assert abs(m.predict(f["black"][None])[0, 0] - 18.0) < 1e-6
    assert f["blend_l"].min() >= 18.0 - 1e-6
    assert f["handover"] and f["a43_floor"] == 18.0
    assert ax["l_black"] == pl[-1]                # the input is not touched
    # the deep black within the data, no floor, no hand-over: unchanged
    assert b2a.a43_floor_axis(m, ax, 15.0) is ax
    assert b2a.a43_floor_axis(m, ax, None) is ax
    assert b2a.a43_floor_axis(m, dict(ax, handover=False), 18.0) is not None
    # a floor at or above the neutral black: no hand-over, neutral black
    g = b2a.a43_floor_axis(m, ax, 22.0)
    assert not g["handover"] and g["l_black"] == pl[0]
    assert not np.any(g["ok"] & (g["l"] < pl[0] - 1e-9))


def test_the_wiring_is_behind_the_tokens():
    gm = inspect.getsource(gamut_map)
    assert "b2a_mod.a43_floor_axis(" in gm and 'a43 == "floor"' in gm
    assert gm.count("b2a_mod.a43_band(") == 2      # ink and RGB band
    assert 'band.get("l_full", l_deep)' in gm
    bs = inspect.getsource(builder)
    assert 'a43_mode(candidates) == "floor"' in bs
    assert "a43_meas_floor" in bs and "a43_meas_floor" in gm
