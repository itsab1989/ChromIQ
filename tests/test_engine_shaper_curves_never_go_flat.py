"""D-11 (Knut's icclib pointer): the engine's own curve inversions never meet a flat run.

ICC.1:2022 Annex F.1 a) says how to invert a curve that is flat over part of its
domain, and ArgyllCMS 3.5.0's ``icmTable_lookup_bwd`` does not follow it
(argyllcms list, 2 Oct 2026). The engine inverts its shaper curves in Python, in
two places: ``b2a.inverse_curves`` (the B2A output tables) and
``ForwardModel.unshape_device``. Both use ``np.interp`` with the curve as the
x-axis, and ``np.interp`` gives no promise at all for tied x values. They are
safe only because the engine's curves are STRICTLY increasing:

* ``ramp_positioning_curves`` blends the measured ramp half way with the
  identity, so even a ramp that does not move for its first steps stays rising;
* ``_refit_curve`` clips every knot to at least 1e-4 above its left neighbour
  and below its right one.

This file pins that, with the inputs most likely to break it: an ink that does
nothing below 15 % and an ink whose ramp patches read identical to the paper.
If a future change lets a curve go flat, these fail before an inverse does
something no specification defines. Evidence and the full analysis:
ProfileEngineResearch Findings/agent12-01-curve-inverse.md.
"""
from __future__ import annotations

import numpy as np

from workflow.profile_engine import b2a as b2a_mod
from workflow.profile_engine.forward_model import (fit_forward_model,
                                                   ramp_positioning_curves)

_FLOOR = 1e-4          # _refit_curve's minimum gap between neighbouring knots


def _dead_zone_printer(n: int = 600, seed: int = 4):
    """3 inks; ink 0 has no visible effect below 15 % (a dead zone that a
    least-squares curve fit would like to make flat)."""
    rng = np.random.default_rng(seed)
    dev = rng.uniform(0.0, 1.0, (n, 3))
    ramps = np.zeros((3 * 11, 3))
    for c in range(3):
        ramps[c * 11:(c + 1) * 11, c] = np.linspace(0.0, 1.0, 11)
    dev = np.vstack([np.zeros((1, 3)), ramps, dev])
    eff = dev.copy()
    eff[:, 0] = np.clip((dev[:, 0] - 0.15) / 0.85, 0.0, 1.0)
    lab = np.stack([95.0 - 40.0 * eff[:, 0] - 30.0 * eff[:, 1] - 10.0 * eff[:, 2],
                    -30.0 * eff[:, 0] + 50.0 * eff[:, 1] - 5.0 * eff[:, 2],
                    -20.0 * eff[:, 0] - 5.0 * eff[:, 1] + 70.0 * eff[:, 2]], 1)
    return dev, lab


def test_ramp_positioning_curves_stay_strictly_increasing_on_a_dead_zone():
    dev, lab = _dead_zone_printer()
    curves = ramp_positioning_curves(dev, lab)
    steps = np.diff(curves, axis=1)
    assert (steps > 0).all(), steps.min()
    assert np.allclose(curves[:, 0], 0.0) and np.allclose(curves[:, -1], 1.0)


def test_ramp_patches_that_read_like_paper_do_not_make_a_flat_curve():
    dev, lab = _dead_zone_printer()
    lab = lab.copy()
    on_ramp0 = (dev[:, 1] == 0) & (dev[:, 2] == 0) & (dev[:, 0] > 0) & (dev[:, 0] < 0.45)
    lab[on_ramp0] = lab[(dev == 0).all(1)][0]          # identical to paper white
    curves = ramp_positioning_curves(dev, lab)
    assert (np.diff(curves, axis=1) > 0).all()


def test_refit_keeps_every_knot_above_the_floor():
    dev, lab = _dead_zone_printer()
    model = fit_forward_model(dev, lab, grid=9, curve_rounds=2, cg_iters=200)
    steps = np.diff(model.curves, axis=1)
    assert steps.min() >= _FLOOR - 1e-12, steps.min()


def test_both_python_inversions_agree_with_the_forward_curve():
    dev, lab = _dead_zone_printer()
    model = fit_forward_model(dev, lab, grid=9, curve_rounds=2, cg_iters=200)
    x = np.linspace(0.0, 1.0, 257)
    shaped = model.shape_device(np.stack([x] * 3, 1))
    back = model.unshape_device(shaped)
    assert np.abs(back - x[:, None]).max() < 1e-9
    inv = b2a_mod.inverse_curves(model.curves, knots=257)
    assert (np.diff(inv, axis=1) > 0).all()
    k = model.curves.shape[1]
    xp = np.linspace(0.0, 1.0, k)
    for c in range(3):
        # at its own knots the inverse is exact: curve(inverse(y)) == y
        again = np.interp(inv[c], xp, model.curves[c])
        assert np.abs(again - x).max() < 1e-9
