"""Agent 54 (2026-10-11): research token "a54-bluepath".

On Knut's laser the relative colorimetric blue, azure and violet ramps held
their colour toward black much longer than colprof's, although a51 ports
colprof's clip metric. The cause (ProfileEngineResearch Findings/agent54-01):
our a29 dark floor lifts a target below the black to the black's CIELAB L*
with its CIELAB a*, b* kept, which Argyll's CAM no longer compresses, so the
lifted target is far more chromatic in Jab than the real one. Argyll's own
CAM clip (xicclu -b) on OUR A2B reproduces colprof's path, so it is not the
forward model. a54 applies the floor to J in the clip space instead.
Opt-in.
"""
import numpy as np

from workflow.profile_engine import b2a, oog_clip
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)
from tests.test_research_a51_colprofedge import _ToyPrinter

_BASE = {"a25-oog", "a29-oog-darkmono-floor", oog_clip.A51_TOKEN}


def teardown_function(_f):
    b2a.set_research_tokens((), is_additive=None)
    oog_clip.set_colorimetric(False)
    oog_clip.set_dark_floor(None)


def test_the_token_is_known_and_opt_in():
    assert oog_clip.A54_TOKEN == "a54-bluepath"
    assert oog_clip.A54_TOKEN in ENGINE_CANDIDATE_TOKENS
    assert oog_clip.A54_TOKEN not in ACCURATE_DEFAULT_TOKENS
    assert oog_clip.A54_TOKEN not in accurate_candidates(frozenset())
    assert oog_clip.A54_TOKEN in accurate_candidates({oog_clip.A54_TOKEN})
    b2a.set_research_tokens(frozenset(_BASE | {oog_clip.A54_TOKEN}), is_additive=True)
    oog_clip.set_colorimetric(True)
    assert oog_clip.table_params()["a54"] is True
    b2a.set_research_tokens(frozenset(_BASE), is_additive=True)
    assert oog_clip.PARAMS["a54"] is False


def test_jab_floor_lifts_j_only():
    t = np.array([[5.0, -3.0, -40.0], [30.0, 10.0, 20.0]])
    out = oog_clip.jab_floor(t, 12.0)
    np.testing.assert_array_equal(out[:, 1:], t[:, 1:])
    assert out[0, 0] == 12.0 and out[1, 0] == 30.0
    assert t[0, 0] == 5.0                                  # input untouched


def _clip(tokens, rgb_dir, floor=20.0):
    b2a.set_research_tokens(frozenset(tokens), is_additive=True)
    oog_clip.set_colorimetric(True)
    oog_clip.set_dark_floor(floor)
    model = _ToyPrinter()
    t = np.linspace(0.0, 0.95, 20)
    src = model.predict(np.outer(1 - t, rgb_dir))
    src[:, 1:] /= 0.45                                     # the sRGB source chroma
    src[:, 0] = (src[:, 0] - 20.0) / 0.8
    d = oog_clip.clip_nodes(model, src, np.tile([[0.0, 0.0, 0.2]], (len(src), 1)), np.full(len(src), 20.0),
                            free=np.arange(3), limit=None, channel_max=None, prior=None, prior_w=None,
                            gn_kw={}, damping=1e-3)
    return src, model.predict(d)


def test_below_the_black_the_blue_ramp_gives_up_chroma_like_colprof():
    src, a51 = _clip(_BASE, (0.0, 0.0, 1.0))
    _, a54 = _clip(_BASE | {oog_clip.A54_TOKEN}, (0.0, 0.0, 1.0))
    below = src[:, 0] < 20.0
    assert below.sum() >= 4 and (~below).any()
    np.testing.assert_allclose(a54[~below], a51[~below])   # above the black: unchanged
    c51, c54 = np.hypot(*a51[below, 1:].T), np.hypot(*a54[below, 1:].T)
    assert (c54 <= c51 + 0.5).all() and c54.mean() < c51.mean() - 0.5
    assert np.all(np.diff(a54[:, 0]) <= 0.5)               # still a ramp into black


def test_inert_without_the_cam_metric():
    _, off = _clip({"a25-oog", "a29-oog-darkmono-floor"}, (0.0, 0.0, 1.0))
    _, on = _clip({"a25-oog", "a29-oog-darkmono-floor", oog_clip.A54_TOKEN}, (0.0, 0.0, 1.0))
    np.testing.assert_array_equal(off, on)


def test_the_soft_floor_is_smooth_and_never_below_the_black():
    j = np.linspace(-10.0, 60.0, 141)
    t = np.stack([j, np.full_like(j, 5.0), np.full_like(j, -20.0)], 1)
    out = oog_clip.jab_floor(t, 20.0, soft=4.0)
    assert (out[:, 0] >= 20.0).all() and np.all(np.diff(out[:, 0]) >= 0.0)
    assert abs(out[-1, 0] - 60.0) < 1e-3                  # far above: unchanged
    np.testing.assert_array_equal(out[:, 1:], t[:, 1:])
