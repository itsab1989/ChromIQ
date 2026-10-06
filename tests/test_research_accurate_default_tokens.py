"""Research integration 1 (2026-10-04): which of Agent 3's candidates a
Maximum accuracy build runs with by default. ON: b2a33s (B2A grid 33 with
scaled refit samples), rgbpos (RGB ramp positioning), rgbcol (F-13, Agent 20). OFF: gpfwd and
a2bfine (the GP layer; Agent 13's design challenge, agent13-01), and every
Agent 9 a9-* token. Fast and Bit-exact never read candidates."""
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates,
                                             candidates_from_env)


from workflow.profile_engine.builder import GP_FIN3_TOKENS as _FIN3

_DEF = {"b2a33s", "rgbpos", "v4prm", "rgbcol"}   # v4prm: integration 2, D-19; rgbcol: integration 3, D-20


def test_the_defaults_are_b2a33s_rgbpos_and_v4prm():
    assert ACCURATE_DEFAULT_TOKENS == _DEF
    # plus the fin3 GP set (integration 2), which acts only for <= 4 inks
    assert accurate_candidates(frozenset()) == _DEF | _FIN3
    assert accurate_candidates(None) == _DEF | _FIN3


def test_the_gp_layer_is_off_when_switched_off():
    assert not {"gpfwd", "a2bfine"} & accurate_candidates({"no-fin3"})
    assert {"gpfwd", "a2bfine"} <= accurate_candidates({"no-fin3", "gpfwd",
                                                        "a2bfine"})


def test_agent9_tokens_are_off_by_default():
    assert not [t for t in accurate_candidates(frozenset())
                if t.startswith("a9-")]


def test_a_default_can_be_switched_off_for_research():
    assert accurate_candidates({"no-b2a33s"}) == {"rgbpos", "v4prm", "rgbcol"} | _FIN3
    assert accurate_candidates({"no-rgbpos", "no-b2a33s", "no-v4prm",
                                "no-rgbcol", "no-fin3"}) == frozenset()
    assert "no-rgbcol" in ENGINE_CANDIDATE_TOKENS
    assert "no-b2a33s" in ENGINE_CANDIDATE_TOKENS
    assert candidates_from_env("no-rgbpos,bogus") == {"no-rgbpos"}


# Research integration 2 (2026-10-05): the fin3 GP set is wired as one
# switch, gated to <= 4 inks (test_research_gpfwd_only_up_to_four_inks), and
# ON by default since Validation/fin3-neutral-chroma-10seed.md cleared its
# safety rows. "a17-colpin" is an OFF research token; F-09 ("v4prm") is ON.

def test_fin3_is_on_by_default_and_gated():
    from workflow.profile_engine.builder import (GP_FIN3_DEFAULT_ON,
                                                 GP_FIN3_TOKENS,
                                                 gp_forward_applies)
    assert GP_FIN3_DEFAULT_ON is True
    assert GP_FIN3_TOKENS == {"gpfwd", "gpsel", "gpwarp", "gpclip",
                              "gplight2", "gpdark", "a2bfine", "gpkeep"}
    on = accurate_candidates(frozenset())
    assert GP_FIN3_TOKENS <= on
    assert gp_forward_applies(on, is_additive=False, n_channels=4,
                              n_patches=900)
    for n in (5, 6, 7):
        assert not gp_forward_applies(on, is_additive=False, n_channels=n,
                                      n_patches=5000)
    assert not gp_forward_applies(on, is_additive=True, n_channels=3,
                                  n_patches=900)


def test_no_fin3_removes_the_whole_set():
    from workflow.profile_engine.builder import GP_FIN3_TOKENS
    assert accurate_candidates({"fin3"}) == GP_FIN3_TOKENS | _DEF
    assert accurate_candidates({"no-fin3"}) == _DEF
    assert accurate_candidates({"fin3", "no-fin3"}) == _DEF
    assert "gpkeep" not in accurate_candidates({"no-gpkeep"})
    assert candidates_from_env("no-fin3") == {"no-fin3"}


def test_colpin_is_off_and_f09_on_by_default():
    assert "a17-colpin" not in accurate_candidates(frozenset())
    assert "v4prm" in accurate_candidates(frozenset())
    assert "v4prm" not in accurate_candidates({"no-v4prm"})
    assert candidates_from_env("no-v4prm") == {"no-v4prm"}
