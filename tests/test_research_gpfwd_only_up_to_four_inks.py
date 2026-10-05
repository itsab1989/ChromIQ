"""Research integration 1 (2026-10-04): Agent 3's GP forward model ("gpfwd",
with "a2bfine", which acts only inside its projection) replaces the forward
fit for ink devices of at most 4 inks. On 5-7 inks it degraded the single-ink
ramps (Agent 14 interim: X5 ramp A2B median 1.2-1.8 dE00 against 0.1-0.4), so
5+ inks keep the shipped forward fit; "b2a33s" does not depend on the GP."""
import inspect

from workflow.profile_engine import builder
from workflow.profile_engine.builder import (GP_FORWARD_MAX_INKS,
                                             gp_forward_applies)

TOKENS = frozenset({"gpfwd", "a2bfine", "b2a33s"})


def test_the_gate_is_four_inks():
    assert GP_FORWARD_MAX_INKS == 4


def test_cmy_and_cmyk_get_the_gp():
    assert gp_forward_applies(TOKENS, is_additive=False, n_channels=4,
                              n_patches=900)
    assert gp_forward_applies(TOKENS, is_additive=False, n_channels=3,
                              n_patches=900)


def test_five_six_and_seven_inks_keep_the_forward_fit():
    for n in (5, 6, 7, 8):
        assert not gp_forward_applies(TOKENS, is_additive=False,
                                      n_channels=n, n_patches=5000), n


def test_rgb_never_gets_the_gp():
    assert not gp_forward_applies(TOKENS, is_additive=True, n_channels=3,
                                  n_patches=900)


def test_without_the_token_nothing_changes():
    assert not gp_forward_applies(frozenset({"a2bfine", "b2a33s"}),
                                  is_additive=False, n_channels=4,
                                  n_patches=900)


def test_sparse_charts_keep_the_forward_fit():
    # 75 patches per ink (agent 3, F0g/F0h)
    assert not gp_forward_applies(TOKENS, is_additive=False, n_channels=4,
                                  n_patches=299)
    assert gp_forward_applies(TOKENS, is_additive=False, n_channels=4,
                              n_patches=300)


def test_the_builder_fits_the_gp_only_behind_the_gate():
    src = inspect.getsource(builder._build_profile_impl)
    assert src.count("fit_gp_forward(") == 1
    call = src.index("fit_gp_forward(")
    gate = src.rfind("if gp_forward_applies(", 0, call)
    assert gate != -1
    # nothing else opens a branch between the gate and the call
    assert "\n        if " not in src[gate + 1:call]


# Research integration 2 (2026-10-05): Agent 15's repaired GP set ("fin3")
# may only ever act behind this gate, so that turning it on by default can
# change nothing for RGB and 5+ ink devices.

def test_agent15s_repair_is_fitted_only_behind_the_gate():
    src = inspect.getsource(builder._build_profile_impl)
    call = src.index("_agent15_gp(")
    gate = src.rfind("if gp_forward_applies(", 0, call)
    assert gate != -1 and gate < src.index("fit_gp_forward(")


def test_every_fin3_token_is_read_only_inside_the_gated_branch():
    src = inspect.getsource(builder._build_profile_impl)
    gate = src.index("if gp_forward_applies(")
    end = src.index("\n        if len(outliers):", gate)
    for tok in builder.GP_FIN3_TOKENS:
        q = f'"{tok}"'
        at = [i for i in range(len(src)) if src.startswith(q, i)]
        for i in at:
            line = src[src.rfind("\n", 0, i):src.find("\n", i)]
            if tok == "gpfwd" and "n > 4" in line:
                continue                      # the "not used for 5+ inks" log line
            assert gate < i < end, (tok, line)


def test_fin3_turned_on_still_skips_rgb_and_five_or_more_inks():
    on = builder.accurate_candidates({"fin3"})
    assert builder.GP_FIN3_TOKENS <= on
    for n in (5, 6, 7):
        assert not gp_forward_applies(on, is_additive=False, n_channels=n,
                                      n_patches=5000)
    assert not gp_forward_applies(on, is_additive=True, n_channels=3,
                                  n_patches=900)
    assert gp_forward_applies(on, is_additive=False, n_channels=4,
                              n_patches=900)
