"""Three things Maximum accuracy promised and did not deliver (2026-09-05).

Measured by the engine-accuracy challenge on a real 924-patch ColorMunki
chart (Agent A, findings A-04, A-05, A-07):

* **Hue flip on far out-of-gamut colours.** The "hue-preserving clip"
  measured hue error with a first-order metric that cannot tell a colour
  from its complement — both lie on one line through the neutral axis — so
  5.7 % of out-of-gamut nodes printed the OPPOSITE hue (sRGB magenta
  255/64/239 came out green 71/186/66). colprof: 0 %. Now the clip seeds from
  a printable colour of the same hue angle, and the survey reads 0.000 above
  30° in every gamut-distance bin (colprof 0.014 in the far bin).
* **L*=0 did not print the printer's black.** The Lab grid's black corner is
  only ~3 ΔE76 outside a real gamut, so the smooth refit extrapolated it:
  RGB 3/4/18 (fast, a blue cast) and 3/0/4 (accurate). Pinned now: 0.01.
* **The smoothing "chosen by cross-validation" was a coin toss.** One
  hold-out split spread 0.01–0.1 ΔE00 across the whole ×0.25…×4 ladder and
  0.1 between splits; the full chart chose ×0.25, 90 % of it chose ×4, and
  the stiffer profile generalised worse than the plain fit. Three splits and
  a margin now; the log says when nothing won.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from benchmarks.iccread import IccProfile
from tests.test_profile_engine import synth_xyz, write_synth_ti3
from workflow.profile_engine import BuildSettings, build_profile
from workflow.profile_engine.accuracy import fit_forward_model_accurate
from workflow.profile_engine.ti3_data import xyz_to_lab

_TS = datetime(2026, 9, 5, tzinfo=timezone.utc)
_RGB = ["RGB_R", "RGB_G", "RGB_B"]


def _hue(lab: np.ndarray) -> np.ndarray:
    return np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360.0


def _hue_err(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.abs((_hue(a) - _hue(b) + 180.0) % 360.0 - 180.0)


def _build(tmp_path, mode: str, **kw):
    ti3 = write_synth_ti3(tmp_path / f"{mode}.ti3", "iRGB", _RGB, True,
                          n_per_axis=6)
    out = tmp_path / f"{mode}.icc"
    build_profile(ti3, out, BuildSettings(quality="l", gammap_mode=mode,
                                          timestamp=_TS, **kw))
    return IccProfile(out)


def test_far_out_of_gamut_relative_clip_keeps_the_hue_family(tmp_path):
    icc = _build(tmp_path, "accurate")
    # A ring of very saturated targets at mid lightness — far outside any
    # printer, one per 15° of hue — plus the two colours that flipped.
    hues = np.arange(0.0, 360.0, 15.0)
    ring = np.stack([np.full_like(hues, 55.0),
                     95.0 * np.cos(np.radians(hues)),
                     95.0 * np.sin(np.radians(hues))], 1)
    flipped = np.array([[62.6, 82.9, -47.7], [82.9, -75.3, 75.8]])
    targets = np.vstack([ring, flipped])
    dev = np.clip(icc.b2a_device(targets, "B2A1"), 0.0, 1.0)
    printed = icc.a2b_lab(dev, "A2B1")
    err = _hue_err(printed, targets)
    assert err.max() <= 30.0, err.round(1)
    assert np.median(err) <= 10.0, err.round(1)
    # …and the printed colour is still a saturated one, not grey: the clip
    # loses chroma but does not collapse onto the neutral axis.
    assert np.hypot(printed[:, 1], printed[:, 2]).min() > 15.0


def test_l_zero_prints_the_deepest_black(tmp_path):
    for mode in ("fast", "accurate"):
        icc = _build(tmp_path, mode)
        for tag in ("B2A1", "B2A0", "B2A2"):
            dev = icc.b2a_device(np.array([[0.0, 0.0, 0.0]]), tag)[0]
            assert np.abs(dev).max() < 2e-3, (mode, tag, dev)
        # The pin did not disturb the in-gamut rows above it (the synthetic
        # printer's black sits above L* 20): L*=40 still maps darker than
        # L*=60 on every channel.
        d40 = icc.b2a_device(np.array([[40.0, 0.0, 0.0]]), "B2A1")[0]
        d60 = icc.b2a_device(np.array([[60.0, 0.0, 0.0]]), "B2A1")[0]
        assert (d40 < d60).all(), (mode, d40, d60)


def test_cv_smoothing_keeps_the_standard_value_when_nothing_wins():
    """On a clean synthetic chart no ladder factor beats ×1 by more than
    the criterion's scatter — the fit must say so and keep ×1, instead of
    reporting the split's noise as a decision."""
    rng = np.random.default_rng(11)
    dev = rng.uniform(0.0, 1.0, (400, 3))
    dev[0] = 1.0
    lab = xyz_to_lab(synth_xyz(dev, additive=True))
    lab = lab + rng.normal(0.0, 0.15, lab.shape)        # instrument noise
    lines: list[str] = []
    _model, outliers, lam = fit_forward_model_accurate(
        dev, lab, grid=9, base_lam=0.03, progress=lines.append)
    said = [ln for ln in lines if ln.startswith("Smoothing")]
    assert said, lines
    if "keeping the standard smoothing" in said[0]:
        assert lam == pytest.approx(0.03)
    else:
        # A genuine win names the margin it beat and never hides a pick at
        # the end of the ladder.
        assert "vs" in said[0] and "at the standard value" in said[0]
        f = lam / 0.03
        if f in (0.25, 4.0):
            assert "end of the search range" in said[0]
    assert len(outliers) == 0


def test_cv_search_ran_more_than_one_split(monkeypatch):
    """The margin only means something if it is measured across splits:
    at most one split per factor was the coin toss."""
    import workflow.profile_engine.accuracy as acc
    calls: list[int] = []
    real = acc.fit_forward_model

    def counting(device, lab, **kw):
        calls.append(len(device))
        return real(device, lab, **kw)

    monkeypatch.setattr(acc, "fit_forward_model", counting)
    rng = np.random.default_rng(5)
    dev = rng.uniform(0.0, 1.0, (300, 3))
    dev[0] = 1.0
    lab = xyz_to_lab(synth_xyz(dev, additive=True))
    fit_forward_model_accurate(dev, lab, grid=9, base_lam=0.03)
    # 5 ladder factors × 3 splits of 270 training patches, plus the stiff
    # scan and the robust fits on all 300.
    assert calls.count(270) == 15, calls
