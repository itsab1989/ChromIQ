"""Agent 51 (2026-10-10): research token "a51-colprofedge" (and variants).

Relative colorimetric colour-to-black ramps on Knut's laser lost their colour
earlier than colprof's (Basti's eye, ProfileEngineResearch RESUME s56). The
cause is the clip METRIC (ProfileEngineResearch Findings/agent51-01): colprof
clips an out-of-gamut colour to the nearest printable colour in CIECAM02 Jab
with LCh weights J 2 / C 1 / H 2.2 and Argyll's Helmholtz-Kohlrausch lift
(xicc/xlut.c, rspl/rev.c, xicc/cam02.c); ours used CIELAB with J 4 / C 0.35 /
H 8 (squared), which gives chroma away much more readily. The token puts
colprof's metric into the a25-oog clip of the colorimetric table only.
Off by default.
"""
import inspect

import numpy as np

from workflow.profile_engine import b2a, builder, oog_clip
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)

_TOKENS = (oog_clip.A51_TOKEN, oog_clip.A51_BAND_TOKEN,
           oog_clip.A51_NOHK_TOKEN, oog_clip.A51_OWNHUE_TOKEN,
           oog_clip.A51_NOFLOOR_TOKEN, oog_clip.A51_LAB_TOKEN,
           oog_clip.A51_SOFT_TOKEN, "a51-shapersmooth")


class _ToyPrinter:
    """RGB -> Lab of a small, dark-narrowing gamut: sRGB primaries with the
    chroma scaled down and a black at L* 20 (like Knut's laser)."""
    n_channels = 3

    def predict(self, dev):
        d = np.clip(np.atleast_2d(np.asarray(dev, float)), 0.0, 1.0)
        lin = np.where(d <= 0.04045, d / 12.92, ((d + 0.055) / 1.055) ** 2.4)
        m = np.array([[0.4360747, 0.3850649, 0.1430804],
                      [0.2225045, 0.7168786, 0.0606169],
                      [0.0139322, 0.0971045, 0.7141733]])
        xyz = lin @ m.T
        w = np.array([0.96422, 1.0, 0.82521])
        r = np.clip(xyz / w, 0.0, None)
        f = np.where(r > (6 / 29) ** 3, np.cbrt(r), r / (3 * (6 / 29) ** 2) + 4 / 29)
        lab = np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]),
                        200 * (f[:, 1] - f[:, 2])], 1)
        lab[:, 1:] *= 0.45
        lab[:, 0] = 20.0 + lab[:, 0] * 0.8
        return lab


def _set(tokens, colorimetric):
    b2a.set_research_tokens(frozenset(tokens), is_additive=True)
    oog_clip.set_colorimetric(colorimetric)


def teardown_function(_f):
    b2a.set_research_tokens((), is_additive=None)
    oog_clip.set_colorimetric(False)


def test_the_tokens_are_known_and_not_defaults():
    for tok in _TOKENS:
        assert tok in ENGINE_CANDIDATE_TOKENS
        assert tok not in ACCURATE_DEFAULT_TOKENS
        assert tok not in accurate_candidates(frozenset())
        assert tok in accurate_candidates({tok})


def test_the_metric_is_colprofs_and_only_in_the_colorimetric_table():
    _set({"a25-oog", oog_clip.A51_TOKEN}, colorimetric=True)
    p = oog_clip.table_params()
    assert (p["space"], p["wj"], p["wc"], p["wh"]) == ("cam02", 4.0, 1.0, 4.84)
    assert p["hue_from"] == oog_clip.DEFAULTS["hue_from"]
    assert p["blend_hi"] == oog_clip.DEFAULTS["blend_hi"]
    oog_clip.set_colorimetric(False)          # perceptual / saturation
    assert oog_clip.table_params() is oog_clip.PARAMS
    assert oog_clip.PARAMS["space"] == oog_clip.DEFAULTS["space"]
    _set({"a25-oog"}, colorimetric=True)      # token off: unchanged
    assert oog_clip.table_params() is oog_clip.PARAMS


def test_the_variants():
    _set({"a25-oog", oog_clip.A51_BAND_TOKEN}, colorimetric=True)
    assert oog_clip.table_params()["blend_hi"] == 1.5
    _set({"a25-oog", oog_clip.A51_OWNHUE_TOKEN}, colorimetric=True)
    assert oog_clip.table_params()["hue_from"] == ""
    lab = np.array([[30.0, 50.0, 30.0]])
    _set({"a25-oog", oog_clip.A51_NOHK_TOKEN}, colorimetric=True)
    j_nohk = oog_clip.lab_to_argyll_jab(lab)[0, 0]
    _set({"a25-oog", oog_clip.A51_TOKEN}, colorimetric=True)
    assert oog_clip.lab_to_argyll_jab(lab)[0, 0] > j_nohk


def test_argyll_jab_lifts_saturated_colours_only():
    grey = oog_clip.lab_to_argyll_jab(np.array([[50.0, 0.0, 0.0]]))
    red = oog_clip.lab_to_argyll_jab(np.array([[50.0, 60.0, 40.0]]))
    assert np.hypot(grey[0, 1], grey[0, 2]) < 1.5       # incomplete adaptation (D < 1)
    oog_clip._HK["on"] = False
    try:
        red0 = oog_clip.lab_to_argyll_jab(np.array([[50.0, 60.0, 40.0]]))
        grey0 = oog_clip.lab_to_argyll_jab(np.array([[50.0, 0.0, 0.0]]))
    finally:
        oog_clip._HK["on"] = True
    assert abs(grey[0, 0] - grey0[0, 0]) < 0.05       # no lift without chroma
    assert 0.5 < red[0, 0] - red0[0, 0] < 10.0          # a modest lift
    np.testing.assert_allclose(red[0, 1:], red0[0, 1:])


def _clip(tokens):
    model = _ToyPrinter()
    t = np.linspace(0.45, 0.75, 7)
    rgb = np.outer(1 - t, (1.0, 0.0, 0.0))          # dark half of red -> black
    src = model.predict(rgb)
    src[:, 1:] /= 0.45                               # the sRGB source chroma
    src[:, 0] = (src[:, 0] - 20.0) / 0.8
    _set(tokens, colorimetric=True)
    d_near = np.tile([[0.2, 0.0, 0.0]], (len(src), 1))
    residual = np.full(len(src), 20.0)
    d = oog_clip.clip_nodes(model, src, d_near, residual, free=np.arange(3), limit=None,
                            channel_max=None, prior=None, prior_w=None,
                            gn_kw={}, damping=1e-3)
    return model.predict(d)


def test_on_a_toy_printer_the_colprof_metric_keeps_more_chroma():
    ours = _clip({"a25-oog"})
    cp = _clip({"a25-oog", oog_clip.A51_TOKEN})
    c_ours = np.hypot(ours[:, 1], ours[:, 2])
    c_cp = np.hypot(cp[:, 1], cp[:, 2])
    assert (c_cp >= c_ours - 0.5).all()
    assert c_cp.mean() > c_ours.mean() + 1.0
    assert cp[:, 0].mean() > ours[:, 0].mean()       # by giving up lightness
    assert np.all(np.diff(cp[:, 0]) <= 0.5)          # still a ramp into black


def test_the_builder_marks_the_colorimetric_table_and_clears_it():
    src = inspect.getsource(builder)
    on = src.index("_oog51.set_colorimetric(True)")
    build = src.index("dev_clut, residual = b2a_mod.build_b2a_clut(")
    off = src.index("_oogc.set_colorimetric(False)")
    assert on < build < off
    assert "set_colorimetric(False)" in inspect.getsource(b2a.set_research_tokens)
    assert "table_params()" in inspect.getsource(oog_clip.clip_nodes)


def test_the_argyll_cam_port_matches_argyll():
    """xicclu -ff -ia -pl / -pj (ArgyllCMS 3.5.0) on a colprof profile: five
    colours, Argyll's own Jab. The port agrees within 0.15 Jab."""
    from workflow.profile_engine.argyll_cam02 import lab_to_jab
    lab = np.array([[49.798362, 19.549516, -10.087625], [31.143779, 39.467543, 27.662800],
                    [12.132323, 16.967999, -37.481715], [70.007123, -30.132771, 60.234662],
                    [6.535774, 0.965383, -3.259200]])
    ref = np.array([[42.101706, 20.830131, -8.853912], [27.138492, 41.985893, 22.502855],
                    [15.453056, 2.395148, -34.673219], [60.913318, -31.269319, 52.870165],
                    [10.862479, 0.484235, -2.877773]])
    got = lab_to_jab(lab, La=40.0, Yb=0.2, Yf=0.01, Yg=0.0)
    assert np.abs(got - ref).max() < 0.15


def test_argyll_cam_stays_sane_on_imaginary_dark_colours():
    """Textbook CIECAM02 sends a dark, saturated, unreal colour to absurd
    chroma; Argyll's compression keeps it near its real neighbours."""
    real = oog_clip.lab_to_argyll_jab(np.array([[10.0, 30.0, 16.0]]))
    unreal = oog_clip.lab_to_argyll_jab(np.array([[10.0, 29.9, 25.9]]))
    assert np.hypot(*unreal[0, 1:]) < 1.6 * np.hypot(*real[0, 1:])
    assert abs(unreal[0, 0] - real[0, 0]) < 3.0


def test_shapersmooth_keeps_a_flat_stretch_from_collapsing():
    """a51-shapersmooth: a channel whose middle knots no patch constrains
    keeps a smooth curve; without the token the plain refit is unchanged."""
    from workflow.profile_engine import forward_model as fm
    rng = np.random.default_rng(5)
    lv = np.concatenate([rng.uniform(0, 0.45, 60), rng.uniform(0.75, 1.0, 60), [0.5] * 20, [0.7] * 20])
    dev = np.stack([lv, rng.uniform(0, 1, len(lv)), rng.uniform(0, 1, len(lv))], 1)
    lab = _ToyPrinter().predict(dev)
    b2a.set_research_tokens(frozenset(), is_additive=True)
    plain = fm.fit_forward_model(dev, lab, grid=5, curve_rounds=1)
    b2a.set_research_tokens(frozenset({"a51-shapersmooth"}), is_additive=True)
    try:
        smooth = fm.fit_forward_model(dev, lab, grid=5, curve_rounds=1)
    finally:
        b2a.set_research_tokens(frozenset(), is_additive=True)
    rough = lambda c: float((np.diff(c, 2) ** 2).sum())   # noqa: E731
    assert rough(smooth.curves[0]) <= rough(plain.curves[0]) + 1e-12
    assert fm.SHAPER_SMOOTH["mu"] is None
    assert "a51-shapersmooth" in ENGINE_CANDIDATE_TOKENS
    assert "a51-shapersmooth" not in ACCURATE_DEFAULT_TOKENS
