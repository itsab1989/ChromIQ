"""Agent 38 s6 (2026-10-07): research token "a40-knut-grey" (opt-in).

On Knut's laser chart the shipped RGB ramp curves cost the held-out grey
column. The token runs a five-fold exam of the shipped curves against
"mixed" curves (a gentler placement over the light part of each channel,
the shipped one at the dark end) and, where the shipped ones are clearly
worse, builds with the mixed curves at the standard smoothing; the neutral
column is then bridged from the device black and made monotone per channel.
Accuracy: Knut held-out A2B 1.75 -> 1.45 (colprof 1.50). Not a default: the
dark hand-over (L* 23-26) still kinks in the off-column nodes.
ProfileEngineResearch Findings/agent38-01-knut-laser.md s6.
"""
import inspect
import re

import numpy as np

from workflow.profile_engine import accuracy, b2a, forward_model, noisyrgb
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS)


def test_the_token_is_known_and_not_a_default():
    assert noisyrgb.A40_TOKEN == "a40-knut-grey"
    assert noisyrgb.A40_TOKEN in ENGINE_CANDIDATE_TOKENS
    assert noisyrgb.A40_TOKEN not in ACCURATE_DEFAULT_TOKENS
    assert noisyrgb.A40_BLENDS == (0.5, "mixed")


def _ramps():
    # one RGB channel's "ink" ramp that saturates early, like toner
    x = np.array([0.22, 0.47, 0.76, 1.0])
    dev = np.zeros((1 + 3 * len(x), 3))
    lab = np.tile([100.0, 0.0, 0.0], (len(dev), 1))
    for c in range(3):
        for i, v in enumerate(x):
            dev[1 + c * len(x) + i, c] = v
            lab[1 + c * len(x) + i] = [100 - 25 * min(v / 0.76, 1.0) - v, -30 * v, 0]
    return dev, lab


def test_mixed_curves_are_monotone_pinned_and_shipped_at_the_dark_end():
    dev, lab = _ramps()
    mix = forward_model.ramp_positioning_curves_mixed(dev, lab)
    ship = forward_model.ramp_positioning_curves(dev, lab, blend=0.5)
    gentle = forward_model.ramp_positioning_curves(dev, lab, blend=0.25)
    xp = np.linspace(0, 1, mix.shape[1])
    assert (np.diff(mix, axis=1) >= 0).all()
    assert np.allclose(mix[:, 0], 0) and np.allclose(mix[:, -1], 1)
    assert np.allclose(mix[:, xp >= 0.9], ship[:, xp >= 0.9])
    assert np.allclose(mix[:, xp <= 0.65], gentle[:, xp <= 0.65])


def test_the_shipped_blend_is_the_default_path():
    src = inspect.getsource(accuracy._ramp_curves)
    assert 'ramp_blend == "mixed"' in src
    sig = inspect.signature(accuracy.fit_forward_model_accurate)
    assert sig.parameters["ramp_blend"].default == 0.5


def test_monotone_channels_pools_a_turn_back_and_keeps_monotone_columns():
    col = np.array([[0, 0, 0.0], [0, 0, 0.17], [0.11, 0.09, 0.10], [0.18, 0.15, 0.14]])
    out = b2a.monotone_channels(col)
    assert (np.diff(out, axis=0) >= -1e-12).all()
    assert np.allclose(out[1:3, 2], 0.135)
    ok = np.cumsum(np.full((5, 3), 0.1), axis=0)
    assert np.array_equal(b2a.monotone_channels(ok), ok)


def test_dark_bridge_is_a_straight_line_from_the_black():
    l_star = np.array([0.0, 21.9, 25.0, 28.1, 31.3])
    dev = np.array([[0, 0, 0], [0, 0, 0.01], [0, 0, 0.17], [0.11, 0.09, 0.10], [0.18, 0.15, 0.14]])
    out = b2a.dark_bridge(dev, l_star, black_l=22.9, to_l=26.6)
    u = (25.0 - 22.9) / (28.1 - 22.9)
    assert np.allclose(out[2], u * dev[3])
    keep = [0, 1, 3, 4]
    assert np.array_equal(out[keep], dev[keep])


def test_the_builder_applies_it_only_after_the_exam_switched():
    from workflow.profile_engine import builder
    src = inspect.getsource(builder)
    assert '"a40-knut-grey" in candidates' in src
    assert "if (_a40_on and fixed_nodes is not None" in src
    assert src.count("_a40_on = True") == 1


def test_no_file_io_without_a_named_encoding():
    for mod in (noisyrgb, b2a, forward_model):
        src = inspect.getsource(mod)
        for call in re.findall(r"(?:open|read_text|write_text)\([^)]*\)", src):
            assert "encoding" in call, (mod.__name__, call)
