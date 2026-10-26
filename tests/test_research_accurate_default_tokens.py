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

# v4prm: integration 2, D-19; rgbcol: integration 3, D-20; a25-*, a24-s1,
# a24-f05: integration 3 (Findings/agent26-01-integration3.md, D-24)
_INT3 = {"a25-oog", "a25-rgbcol", "a25-oracle-dev", "a25-oracle-neutral",
         "a24-s1", "a24-f05"}
# a29-oog-darkmono-floor: integration 4 (Findings/agent33-01-integration4.md)
_INT4 = {"a29-oog-darkmono-floor"}
# a34-blackseam: integration 5 candidate (Findings/agent35-01-percblack.md)
_INT5 = {"a34-blackseam", "a35-percblack-blend", "a35-oracle-limit",
         "a36-lcms8-safe", "a38-noisy-rgb"}
# integration 6 (Findings/agent47-01-integration6.md)
_INT6 = {"a40-inklimit", "a42-nearblack", "a43-shadowdetail-width",
         "a43-shadowdetail", "a40-knut-grey", "a44-exactkeep",
         "a44b-smoothexact", "a45-c1space", "a45-darkend"}
# integration 7 (Findings/agent52-01-integration7.md): RGB devices only
_INT7 = {"a51-colprofedge"}
# integration 8 (Findings/agent62-01-violet-int8.md): RGB colorimetric B2A1
# on colprof's recipe (v-noclip) + a60-darkacc + a62-camhue, RGB only
_INT8 = {"a58-purecolprof", "a58-keep-black", "a58-keep-grid33in",
         "a58-keep-floor", "a56-blackfade", "a58-keep-rgbcol",
         "a58-keep-refit", "a58-keep-a44", "a58-keep-a42", "a58-keep-a40",
         "a60-darkacc", "a62-camhue"}
# integration 8b (Findings/agent63-01-pale.md): pale in-gamut accuracy near
# the paper white, and no coarse table below grid 17 at quality l; RGB only
_INT8B = {"a63-palefine", "a63-lowgrid"}
# integration 9 (Findings/agent72-01-integration9.md): CMYK (a65 blue, a69
# port, a70 edge/fold, a71 dark end), CMY (a66-cmyaxis + the CMY-only a67 set
# with a66-refitguard, scoped by a72-cmyonly), RGB (a68-clipkeep)
_INT9 = {"a65-cmykhue-bluejab", "a66-cmyaxis", "a68-clipkeep", "a69-cmykport",
         "a69-cmykport-oog", "a69-cmykport-oogfine", "a70-edgesmooth",
         "a70-edgeadapt", "a70-foldcap", "a71-darkray",
         "a66-refitguard", "a67-camratio", "a67-guardall-dark",
         "a67-guardpolish", "a72-cmyonly", "a72-max4ink"}
# integration 10 (Findings/agent76-01-integration10.md): CMYK pale out-of-gamut
# lightness (a75) and the measured ink fold / dark end (a73 + a74)
_INT10 = {"a75-lightkeep", "a73-kfirst", "a74-foldmeas", "a74-kfloor",
          "a74-shellhold", "a74-shellhue"}
# integration 11 (Findings/agent83-01-integration11.md): RGB rel. col. smoothing
# (a78, a82) and the CMYK i1iSis / folding-printer greys (a79, a80)
_INT11 = {"a78-rgbsmooth", "a79-perccol", "a79-lincurve", "a79-lincurve-col",
          "a80-greywalk", "a80-colpin", "a80-lincurve", "a82-green"}
_DEF = ({"b2a33s", "rgbpos", "v4prm", "rgbcol"} | _INT3 | _INT4 | _INT5 | _INT6
        | _INT7 | _INT8 | _INT8B | _INT9 | _INT10 | _INT11)


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
    assert accurate_candidates({"no-b2a33s"}) == ({"rgbpos", "v4prm", "rgbcol"}
                                                  | _INT3 | _INT4 | _INT5 | _INT6 | _INT7 | _INT8 | _INT8B | _INT9 | _INT10 | _INT11 | _FIN3)
    assert accurate_candidates({"no-rgbpos", "no-b2a33s", "no-v4prm",
                                "no-rgbcol", "no-fin3"}
                               | {"no-" + t for t in _INT3 | _INT4 | _INT5 | _INT6 | _INT7 | _INT8 | _INT8B | _INT9 | _INT10 | _INT11}) == frozenset()
    for t in _INT3 | _INT4 | _INT5 | _INT6 | _INT7 | _INT8 | _INT8B | _INT9 | _INT10 | _INT11:
        assert "no-" + t in ENGINE_CANDIDATE_TOKENS


def test_integration3_opt_in_tokens_stay_off():
    on = accurate_candidates(frozenset())
    assert not {"a24-l1", "a19-extrap", "a21-lightcloud60", "a25-p-blend_light=10"} & on
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


def test_integration9_cmy_tokens_act_on_cmy_only():
    from workflow.profile_engine.builder import (INT9_CMY_TOKENS,
                                                 scope_device_tokens)
    on = accurate_candidates(frozenset())
    assert INT9_CMY_TOKENS <= on
    # CMY (3 ink channels): kept
    assert scope_device_tokens(on, n=3, is_additive=False) == on
    # CMYK, RGB: taken out, nothing else touched; 6 inks: bluejab out too
    for n, add in ((4, False), (3, True)):
        assert scope_device_tokens(on, n=n, is_additive=add) == on - INT9_CMY_TOKENS
    assert (scope_device_tokens(on, n=6, is_additive=False)
            == on - INT9_CMY_TOKENS - {"a65-cmykhue-bluejab"})
    assert "a65-cmykhue-bluejab" in scope_device_tokens(
        accurate_candidates({"no-a72-max4ink"}), n=6, is_additive=False)
    # "no-a72-cmyonly" gives Agent 67's research behaviour back (every device)
    raw = accurate_candidates({"no-a72-cmyonly"})
    assert scope_device_tokens(raw, n=4, is_additive=False) == raw
    assert INT9_CMY_TOKENS <= raw
    # one CMY token switched off stays off on CMY
    one = accurate_candidates({"no-a67-camratio"})
    assert "a67-camratio" not in scope_device_tokens(one, n=3, is_additive=False)


def test_a70_blackshell_stays_off():
    assert "a70-blackshell" not in accurate_candidates(frozenset())
    assert "a70-blackshell" in ENGINE_CANDIDATE_TOKENS


def test_integration10_tokens_are_on_and_switchable():
    from workflow.profile_engine.builder import INT10_TOKENS
    assert INT10_TOKENS == _INT10
    on = accurate_candidates(frozenset())
    assert _INT10 <= on
    for t in _INT10:
        assert t not in accurate_candidates({"no-" + t})
        assert "no-" + t in ENGINE_CANDIDATE_TOKENS
    # the a74 stronger version (cmax 50) is an env setting, not a default
    from workflow.profile_engine import cmykport
    assert cmykport.A74_SHELL == "3:0.5:60:3"


def test_integration11_tokens_are_on_and_switchable():
    from workflow.profile_engine.builder import INT11_TOKENS
    assert INT11_TOKENS == _INT11
    on = accurate_candidates(frozenset())
    assert _INT11 <= on
    for t in _INT11:
        assert t not in accurate_candidates({"no-" + t})
        assert "no-" + t in ENGINE_CANDIDATE_TOKENS
    # the research variants Basti did not pass stay off
    for t in ("a78-rgbsmooth-all", "a82-greencusp", "a82-greenin",
              "a80-oraclecurve", "a80-perccol"):
        assert t not in on
        assert t in ENGINE_CANDIDATE_TOKENS
