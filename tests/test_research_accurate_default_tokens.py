"""Research integration 1 (2026-10-04): which of Agent 3's candidates a
Maximum accuracy build runs with by default. ON: b2a33s (B2A grid 33 with
scaled refit samples), rgbpos (RGB ramp positioning), rgbcol (F-13, Agent 20). OFF: gpfwd and
a2bfine (the GP layer; Agent 13's design challenge, agent13-01), and every
Agent 9 a9-* token. Fast and Bit-exact never read candidates."""
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates,
                                             candidates_from_env)


def test_the_defaults_are_b2a33s_rgbpos_and_rgbcol():
    # rgbcol: research F-13 (Agent 20), the RGB neutral column below the black
    assert ACCURATE_DEFAULT_TOKENS == {"b2a33s", "rgbpos", "rgbcol"}
    assert accurate_candidates(frozenset()) == {"b2a33s", "rgbpos", "rgbcol"}
    assert accurate_candidates(None) == {"b2a33s", "rgbpos", "rgbcol"}


def test_the_gp_layer_is_off_unless_asked_for():
    assert not {"gpfwd", "a2bfine"} & accurate_candidates(frozenset())
    assert {"gpfwd", "a2bfine"} <= accurate_candidates({"gpfwd", "a2bfine"})


def test_agent9_tokens_are_off_by_default():
    assert not [t for t in accurate_candidates(frozenset())
                if t.startswith("a9-")]


def test_a_default_can_be_switched_off_for_research():
    assert accurate_candidates({"no-b2a33s"}) == {"rgbpos", "rgbcol"}
    assert accurate_candidates({"no-rgbpos", "no-b2a33s", "no-rgbcol"}) == frozenset()
    assert "no-rgbcol" in ENGINE_CANDIDATE_TOKENS
    assert "no-b2a33s" in ENGINE_CANDIDATE_TOKENS
    assert candidates_from_env("no-rgbpos,bogus") == {"no-rgbpos"}
