"""Agent 62 (2026-10-14): research token "a62-camhue".

The a29 floor lifts a clip target darker than the printer black to the
black's L* at constant a*, b*. In the dark blue that turns the target's
CIECAM02 hue (the clip metric's own space) toward violet by up to 10 deg,
so the clip adds red and a blue ramp into black shows a violet patch near
the black that colprof does not have (R-RGB-default-i1Pro, Knut, h300). With
the token the lifted target is turned about the L* axis, at its own L* and
C*, until its CAM hue is the hue of the target it was lifted from.
"""
from pathlib import Path

import numpy as np

from workflow.profile_engine import b2a, oog_clip, purecolprof
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)

TOK = oog_clip.A62_TOKEN


def _params(tokens, *, additive, colorimetric=True):
    b2a.set_research_tokens(frozenset(accurate_candidates(frozenset(tokens))),
                            is_additive=additive)
    oog_clip.set_colorimetric(colorimetric)
    return oog_clip.table_params()


def teardown_function(_f):
    b2a.set_research_tokens((), is_additive=None)
    oog_clip.set_colorimetric(False)
    oog_clip.set_dark_floor(None)


def _cam_hue(lab):
    j = oog_clip.lab_to_argyll_jab(np.asarray(lab, float))
    return np.degrees(np.arctan2(j[:, 2], j[:, 1])) % 360.0


def test_the_token_is_known():
    assert TOK == "a62-camhue"
    assert TOK in ENGINE_CANDIDATE_TOKENS
    assert TOK in accurate_candidates({TOK})
    assert TOK not in accurate_candidates({TOK, "no-" + TOK})


def test_it_acts_only_in_the_rgb_colorimetric_table_with_a51():
    assert _params({TOK}, additive=True).get("a62_on") is True
    assert not _params({"no-" + TOK}, additive=True).get("a62_on")
    assert not _params({TOK}, additive=True, colorimetric=False).get("a62_on")
    assert not _params({TOK}, additive=False).get("a62_on")
    assert not _params({TOK, "no-a51-colprofedge"}, additive=True).get("a62_on")


def test_a_lifted_dark_blue_keeps_its_cam_hue():
    c = 65.0
    orig = np.array([[8.2, c * np.cos(np.radians(300)), c * np.sin(np.radians(300))]])
    lifted = orig.copy()
    lifted[:, 0] = 19.3
    # the plain lift turns the CAM hue toward violet (the cause)
    assert _cam_hue(lifted)[0] - _cam_hue(orig)[0] > 4.0
    out = oog_clip.camhue_lift(lifted, orig, np.array([11.1]))
    assert abs(_cam_hue(out)[0] - _cam_hue(orig)[0]) < 0.05
    # L* and C* of the lifted target are kept
    assert out[0, 0] == lifted[0, 0]
    assert np.hypot(out[0, 1], out[0, 2]) == np.hypot(lifted[0, 1], lifted[0, 2])


def test_unlifted_and_neutral_targets_are_left_alone():
    orig = np.array([[30.0, 40.0, -50.0], [5.0, 0.0, 0.0], [5.0, 20.0, 10.0]])
    lifted = orig.copy()
    lifted[1:, 0] = 19.0
    out = oog_clip.camhue_lift(lifted, orig, np.array([0.0, 14.0, 14.0]))
    assert np.array_equal(out[0], lifted[0])          # no lift: unchanged
    assert np.allclose(out[1], lifted[1])              # neutral: no hue
    assert abs(_cam_hue(out[2:])[0] - _cam_hue(orig[2:])[0]) < 0.05
    assert np.array_equal(oog_clip.camhue_lift(lifted, orig, np.zeros(3)), lifted)


def test_both_clips_read_it_only_under_their_flag():
    src = Path(oog_clip.__file__).read_text(encoding="utf-8")
    i = src.index("def clip_nodes(")
    body = src[i:src.find("\ndef ", i + 10)]
    assert 'if p.get("a62_on"):' in body and body.count("camhue_lift(") == 1
    src = Path(purecolprof.__file__).read_text(encoding="utf-8")
    i = src.index("def cam_clip(")
    body = src[i:src.find("\ndef ", i + 10)]
    assert 'getattr(_LOCAL, "a62", False)' in body and body.count("camhue_lift(") == 1


def test_the_purecolprof_flag_follows_the_tokens():
    purecolprof.set_active(True, floor=19.0, fade=True)
    try:
        purecolprof.set_a60({TOK})
        assert purecolprof._LOCAL.a62 is True
        purecolprof.set_a60(set())
        assert purecolprof._LOCAL.a62 is False
    finally:
        purecolprof.set_active(False)
    assert purecolprof._LOCAL.a62 is False
