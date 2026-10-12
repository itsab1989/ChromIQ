"""Agent 55 (2026-10-12, D-30 part 1): research token "a55-nofloor-rgb".

Agent 54 (ProfileEngineResearch Findings/agent54-01) found that Knut's
blue / azure relative colorimetric path to black differs from colprof only
because of the a29 dark floor: a clip target darker than the printer black
is lifted to the black's L* with its chroma kept. Argyll's own clip on our
A2B reproduces colprof's path once the floor is gone. The token removes the
floor from the colorimetric clip wherever a51's colprof metric acts (RGB
devices), and nowhere else. Off by default.
"""
import numpy as np

from workflow.profile_engine import b2a, oog_clip
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)

TOK = oog_clip.A55_NOFLOOR_TOKEN


def _params(tokens, *, additive, colorimetric=True):
    b2a.set_research_tokens(frozenset(accurate_candidates(frozenset(tokens))),
                            is_additive=additive)
    oog_clip.set_colorimetric(colorimetric)
    return oog_clip.table_params()


def teardown_function(_f):
    b2a.set_research_tokens((), is_additive=None)
    oog_clip.set_colorimetric(False)
    oog_clip.set_dark_floor(None)


def test_the_token_is_known_and_not_a_default():
    assert TOK == "a55-nofloor-rgb"
    assert TOK in ENGINE_CANDIDATE_TOKENS
    assert TOK not in ACCURATE_DEFAULT_TOKENS
    assert TOK not in accurate_candidates(frozenset())
    assert TOK in accurate_candidates({TOK})


def test_without_the_token_the_rgb_colorimetric_clip_keeps_the_floor():
    p = _params(set(), additive=True)
    assert p["a51"] and p["dm_on"]
    assert not p.get("dm_off")


def test_the_token_drops_the_floor_in_the_rgb_colorimetric_table():
    p = _params({TOK}, additive=True)
    assert p["a51"] and p.get("dm_off") is True


def test_the_perceptual_and_saturation_tables_are_untouched():
    p = _params({TOK}, additive=True, colorimetric=False)
    assert not p.get("dm_off")


def test_ink_devices_keep_the_floor():
    # a51 is RGB-only by default, so the floor stays on CMYK (byte identity)
    p = _params({TOK}, additive=False)
    assert not p["a51"] and not p.get("dm_off")


def test_switching_a51_off_also_switches_the_token_off():
    p = _params({TOK, "no-a51-colprofedge"}, additive=True)
    assert not p["a51"] and not p.get("dm_off")


def test_the_dark_floor_is_ignored_by_the_clip_only_with_the_token():
    # the floor is set by the builder per table; with dm_off the clip must
    # not read it (oog_clip.clip_nodes: floor = None if dm_off)
    for toks, expect in (({TOK}, None), (set(), 23.0)):
        p = _params(toks, additive=True)
        oog_clip.set_dark_floor(23.0)   # set_research_tokens clears it
        floor = None if p.get("dm_off") else oog_clip.dark_floor()
        assert floor == expect
    assert np.isfinite(oog_clip.dark_floor())
