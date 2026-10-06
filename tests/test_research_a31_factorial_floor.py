"""Agent 31 (2026-10-06): the 29a x 29b factorial branch.

Agent 29a's ``a29-blackhandover(-ink)`` lowers ``axis["l_black"]`` from the
neutral black to a deeper, slightly tinted black (the old value stays in
``axis["neutral_l_black"]``). Agent 29b's ``a29-oog-darkmono(-floor)`` clip
floor must follow the black the column ends at AFTER that hand-over, or the
clip stops above where the column ends (Findings agent29a-01 s11, agent29b-01
s6). These tests pin that, and that both arm tokens combine.
"""
from __future__ import annotations

import inspect

import numpy as np
import pytest

from tests.test_research_a29_blackhandover import _KW, _ToyCmyk
from workflow.profile_engine import b2a, builder
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates,
                                             candidates_from_env,
                                             darkmono_clip_floor)

ARM_A = "a29-blackhandover-ink"
ARM_B = "a29-oog-darkmono-floor"


def test_both_arm_tokens_are_known_off_by_default_and_combine():
    for tok in (ARM_A, ARM_B):
        assert tok in ENGINE_CANDIDATE_TOKENS
        assert tok not in ACCURATE_DEFAULT_TOKENS
        assert tok not in accurate_candidates(frozenset())
    both = candidates_from_env(f"{ARM_A},{ARM_B}")
    assert ARM_A in both and ARM_B in both


def test_the_floor_follows_the_deep_black_after_the_hand_over():
    model = _ToyCmyk(6.0)
    axis = b2a.neutral_axis(model, accurate=True, **_KW)
    out = b2a.blackhandover_axis(model, axis, ladder=(1.0, 2.0), **_KW)
    assert out.get("handover") is True
    floor = darkmono_clip_floor(out, model, is_additive=False, n=4)
    assert floor == pytest.approx(out["l_black"])
    # the deep end, not the neutral black it was handed over from
    assert floor < out["neutral_l_black"] - 1.0
    assert floor == pytest.approx(float(model.predict(out["black"])[0, 0]),
                                  abs=1e-6)


def test_without_a_hand_over_the_floor_is_the_neutral_black():
    model = _ToyCmyk(6.0)
    axis = b2a.neutral_axis(model, accurate=True, **_KW)
    assert darkmono_clip_floor(axis, model, is_additive=False,
                               n=4) == pytest.approx(axis["l_black"])


class _RgbStub:
    n_channels = 3

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        return np.column_stack([4.2 + 90 * d.mean(1), d[:, 0], d[:, 2]])


def test_rgb_without_an_axis_floors_at_device_rgb_zero():
    assert darkmono_clip_floor(None, _RgbStub(), is_additive=True,
                               n=3) == pytest.approx(4.2)
    assert darkmono_clip_floor({"l_black": None}, _RgbStub(),
                               is_additive=True, n=3) == pytest.approx(4.2)


def test_an_ink_device_without_an_axis_has_no_floor():
    assert darkmono_clip_floor(None, _ToyCmyk(0.0), is_additive=False,
                               n=4) is None


def test_the_build_sets_the_floor_after_the_hand_over():
    src = inspect.getsource(builder._build_profile_impl)
    i_hand = src.index("b2a_mod.blackhandover_axis(")
    i_floor = src.index("darkmono_clip_floor(axis")
    i_set = src.index("_oogc.set_dark_floor(_floor)")
    i_clut = src.index("b2a_mod.build_b2a_clut(")
    assert i_hand < i_floor < i_set < i_clut
