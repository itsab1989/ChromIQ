"""Research F-05 (Agent 24, tokens a24-f05*): on 5+ ink devices the perceptual / saturation
mapper must not take the model at ALL inks 100 % as its black (500-700 % ink, outside every
patch; Argyll aligns the whole grey axis to it, so greys take its colour). The tokens act only
for Maximum accuracy, ink devices, 5 or more channels (Findings/agent24-01 s1)."""
import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from workflow.profile_engine import builder, gamut_map
from workflow.profile_engine.gamut_map import (F05_TOKENS, darkest_neutral_of_cloud,
                                               f05_variant)


def _s(*tokens):
    return SimpleNamespace(engine_candidates=frozenset(tokens))


def _m(n):
    return SimpleNamespace(n_channels=n)


@pytest.mark.parametrize("tok,var", sorted(F05_TOKENS.items()))
def test_each_token_selects_its_variant_on_five_to_seven_inks(tok, var):
    for n in (5, 6, 7):
        assert f05_variant(_s(tok), _m(n), is_additive=False, accurate=True) == var


@pytest.mark.parametrize("n", [3, 4])
def test_four_inks_or_fewer_are_never_touched(n):
    for tok in F05_TOKENS:
        assert f05_variant(_s(tok), _m(n), is_additive=False, accurate=True) is None


def test_rgb_and_other_modes_are_never_touched():
    assert f05_variant(_s("a24-f05"), _m(6), is_additive=True, accurate=True) is None
    assert f05_variant(_s("a24-f05"), _m(6), is_additive=False, accurate=False) is None
    assert f05_variant(_s(), _m(6), is_additive=False, accurate=True) is None


def test_the_minimal_fix_picks_the_darkest_near_neutral_point():
    cloud = np.array([[0.0, -2.0, -28.0],     # the all-inks extrapolation kind of point
                      [8.0, 0.5, -0.4],       # darkest near-neutral
                      [12.0, 0.1, 0.1],
                      [50.0, 40.0, 10.0]])
    assert np.allclose(darkest_neutral_of_cloud(cloud), [8.0, 0.5, -0.4])


def test_the_mapper_gets_the_black_and_the_pin_only_through_the_variant():
    src = inspect.getsource(gamut_map.build_mapped_b2a)
    assert "f05_variant(settings, model" in src
    assert "f05_pin or (" in src


def test_the_builder_builds_the_mapped_tables_after_the_colorimetric_black():
    src = inspect.getsource(builder._build_profile_impl)
    i = src.index("_f05_after = (")
    assert "n >= 5 and not meas.is_additive" in src[i:i + 200]
    assert "and not _f05_after" in src
    assert {"a24-f05", "a24-f05walk", "a24-f05min", "a24-f05pin",
            "a24-f05nopin"} <= builder.ENGINE_CANDIDATE_TOKENS
