"""Agent 38 (2026-10-07): research token "a38-noisy-rgb".

The RGB ramp positioning curves ("rgbpos", a default) were decided on the
synthetic S2 printer. On Knut's laser printer (315 patches, 3-4 points per
ramp) they cost the held-out grey column; on the other real RGB charts they
gain nothing. The token keeps them only where a five-fold held-out exam on the
chart shows they help (workflow/profile_engine/noisyrgb.py).
ProfileEngineResearch Findings/agent38-01-knut-laser.md.
"""
import inspect
import re

import numpy as np

from workflow.profile_engine import accuracy, noisyrgb
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)


def _lab(n, rng, light=False, neutral=False):
    lab = np.column_stack([rng.uniform(65 if light else 20, 95, n),
                           rng.uniform(-40, 40, n), rng.uniform(-40, 40, n)])
    if neutral:
        lab[:, 1:] = rng.uniform(-1, 1, (n, 2))
    return lab


def test_the_token_is_a_default_with_an_off_switch():
    # Integration 5 (Agent 39): v2 is a Maximum accuracy default (Agent 38 s5.4)
    assert noisyrgb.A38_TOKEN == "a38-noisy-rgb"
    assert noisyrgb.A38_TOKEN in ENGINE_CANDIDATE_TOKENS
    assert noisyrgb.A38_TOKEN in ACCURATE_DEFAULT_TOKENS
    assert "no-a38-noisy-rgb" in ENGINE_CANDIDATE_TOKENS
    assert noisyrgb.A38_TOKEN in accurate_candidates(frozenset())
    assert noisyrgb.A38_TOKEN not in accurate_candidates({"no-a38-noisy-rgb"})


def test_the_default_rule_is_v2_strict():
    # v1 (strict=False) was rejected; the exam must call the v2 rule
    assert inspect.signature(noisyrgb.decide).parameters["strict"].default is True
    src = inspect.getsource(noisyrgb.rgbpos_exam)
    assert "strict=False" not in src


def test_curves_that_are_clearly_better_are_kept():
    rng = np.random.default_rng(1)
    e_with = rng.uniform(0.2, 0.6, 400)
    rep = noisyrgb.decide(e_with, e_with + 0.2, _lab(400, rng))
    assert not rep["drop"] and "clearly better" in rep["why"]


def test_v1_dropped_curves_that_make_no_difference_v2_keeps_them():
    rng = np.random.default_rng(2)
    e = rng.uniform(0.2, 0.6, 400)
    e2 = e + rng.normal(0, 0.01, 400)
    lab = _lab(400, rng)
    v1 = noisyrgb.decide(e, e2, lab, strict=False)
    assert v1["drop"] and v1["why"] == ""
    v2 = noisyrgb.decide(e, e2, lab)
    assert not v2["drop"] and "not clearly worse" in v2["why"]


def test_v2_drops_curves_that_are_clearly_worse():
    rng = np.random.default_rng(9)
    e_with = rng.uniform(0.3, 0.6, 600)
    rep = noisyrgb.decide(e_with, e_with - 0.05 + rng.normal(0, 0.01, 600), _lab(600, rng))
    assert rep["lower95_with_minus_without"] > 0 and rep["drop"]


def test_curves_are_kept_when_dropping_them_costs_the_near_neutrals():
    rng = np.random.default_rng(3)
    lab = np.vstack([_lab(300, rng), _lab(100, rng, neutral=True)])
    e_with = rng.uniform(0.3, 0.6, 400)
    e_without = e_with - 0.05            # better on average ...
    e_without[300:] += 0.4               # ... but the greys get worse
    rep = noisyrgb.decide(e_with, e_without, lab, strict=False)
    assert not rep["drop"] and "neutral" in rep["why"]


def test_curves_are_kept_when_dropping_them_costs_the_light_colours():
    rng = np.random.default_rng(4)
    lab = np.vstack([_lab(300, rng), _lab(100, rng, light=True)])
    lab[:300, 0] = rng.uniform(20, 55, 300)
    e_with = rng.uniform(0.3, 0.6, 400)
    e_without = e_with - 0.03
    e_without[300:] += 0.3
    rep = noisyrgb.decide(e_with, e_without, lab, strict=False)
    assert not rep["drop"] and "light" in rep["why"]


def test_curves_are_kept_when_dropping_them_clearly_raises_the_p95():
    rng = np.random.default_rng(5)
    e_with = rng.uniform(0.2, 0.6, 2000)
    e_without = e_with - 0.01
    worst = np.argsort(e_with)[-200:]
    e_without[worst] += 1.0              # a heavier tail without the curves
    e_without[np.argsort(e_with)[:1500]] -= 0.2    # a better mean all the same
    rep = noisyrgb.decide(e_with, e_without, _lab(2000, rng), strict=False)
    assert rep["mean_without"] < rep["mean_with"]
    assert not rep["drop"] and "p95" in rep["why"]


def test_the_decision_is_deterministic():
    rng = np.random.default_rng(6)
    e = rng.uniform(0.2, 0.6, 300)
    e2 = e - 0.02 + rng.normal(0, 0.05, 300)
    lab = _lab(300, rng)
    assert noisyrgb.decide(e, e2, lab) == noisyrgb.decide(e.copy(), e2.copy(), lab.copy())


def test_paper_black_and_solids_always_train_and_duplicates_share_a_fold():
    rng = np.random.default_rng(8)
    dev = rng.uniform(0, 1, (200, 3))
    special = np.array([[1, 1, 1], [0, 0, 0], [0, 1, 1], [1, 0, 1], [1, 1, 0]], float)
    dev = np.vstack([dev, special, special[:2], dev[:10]])
    fold = noisyrgb.exam_folds(dev)
    for s in special:
        assert (fold[np.all(dev == s, axis=1)] == -1).all()
    assert np.array_equal(fold[:10], fold[-10:])
    assert set(np.unique(fold[fold >= 0])) == set(range(noisyrgb.A38_FOLDS))


def test_a_single_smoothing_factor_skips_the_search():
    src = inspect.getsource(accuracy.fit_forward_model_accurate)
    assert "lam_factors is None" in src
    assert "or len(lam_factors) > 1" in src


def test_the_builder_runs_the_exam_only_for_rgb_with_the_token():
    from workflow.profile_engine import builder
    src = inspect.getsource(builder)
    i = src.index('"a38-noisy-rgb" in candidates')
    window = src[i - 200:i + 50]
    assert "meas.is_additive" in window and "_positioning" in window


def test_no_file_io_without_a_named_encoding():
    src = inspect.getsource(noisyrgb)
    for call in re.findall(r"(?:open|read_text|write_text)\([^)]*\)", src):
        assert "encoding" in call, call
