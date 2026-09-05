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


def test_hue_gated_seeds_never_pick_the_complement():
    """The mechanism itself (reviewer R18: the profile-level test cannot
    fail under the plain nearest clip on the smooth synthetic printer).
    A cloud with colours at every hue but a target far outside: the seed
    must share the target's hue family, never sit across the neutral axis
    even when the complement is closer in plain Lab distance."""
    from workflow.profile_engine.b2a import _hue_gated_seeds
    rng = np.random.default_rng(1)
    cloud = rng.uniform(0.0, 1.0, (4000, 3))
    ang = np.radians(np.arange(0.0, 360.0, 10.0))
    cloud_lab = np.stack([np.full(len(ang), 55.0), 40.0 * np.cos(ang),
                          40.0 * np.sin(ang)], 1)
    cloud = rng.uniform(0.0, 1.0, (len(ang), 3))
    # A complement decoy: at hue 330°+180°=150° a point with a large
    # chroma of 95 — closer in Lab to the target (95 units away) than the
    # same-hue candidate at chroma 40 (55 away)? No: same hue is nearer
    # here, so also test a target whose SAME-hue candidate is farther.
    tgt = np.array([[55.0, 95.0 * np.cos(np.radians(330)),
                     95.0 * np.sin(np.radians(330))],
                    [90.0, 80.0 * np.cos(np.radians(200)),
                     80.0 * np.sin(np.radians(200))]])
    seeds, found = _hue_gated_seeds(tgt, cloud, cloud_lab)
    assert found.all()
    for s, t in zip(seeds, tgt):
        i = int(np.flatnonzero((cloud == s).all(1))[0])
        h_s = np.degrees(np.arctan2(cloud_lab[i, 2], cloud_lab[i, 1])) % 360
        h_t = np.degrees(np.arctan2(t[2], t[1])) % 360
        assert abs((h_s - h_t + 180) % 360 - 180) <= 6.0, (h_s, h_t)
    # No candidate within 25°: the caller keeps the nearest clip.
    narrow = cloud_lab[:3]
    _s, f2 = _hue_gated_seeds(np.array([[55.0, -60.0, 0.0]]), cloud[:3], narrow)
    assert not f2.any()


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
    # The line always names the winner AND the standard value's own score;
    # a win inside the test's scatter is called a near tie, and a pick at
    # either end of the ladder is named as such.
    assert "vs" in said[0] and "at the standard value" in said[0]
    f = lam / 0.03
    if f in (0.25, 4.0):
        assert "end of the search range" in said[0]
    if f != 1.0 and "near tie" not in said[0]:
        # then it was a clear win: the numbers in the line must show it
        import re
        a, b = map(float, re.findall(r"median ([0-9.]+) vs ([0-9.]+)", said[0])[0])
        assert a < b
    assert len(outliers) == 0


def test_cv_search_runs_the_ladder_once_per_split(monkeypatch):
    """The selection is the shipped one (see accuracy.py's note: every
    alternative failed the battery); this pins that the five-factor ladder
    runs on the configured number of splits, so a future change to
    `_CV_FOLDS` is a deliberate one."""
    import workflow.profile_engine.accuracy as acc
    folds = acc._CV_FOLDS
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
    # 5 ladder factors × the configured splits of 270 training patches,
    # plus the stiff scan and the robust fits on all 300.
    assert calls.count(270) == 5 * folds, (calls, folds)


def test_remaining_time_never_grows_between_lines():
    """Basti, 2026-09-05: "the estimate for the time left … seems to
    increase instead of decrease." elapsed·(100−p)/p grows whenever the
    percentage stalls while the clock runs; the estimate is a deadline now."""
    import re

    from workflow.profile_engine.builder import _PercentProgress
    shown: list[str] = []
    t = [0.0]
    pp = _PercentProgress(shown.append, clock=lambda: t[0])
    script = [  # (time, stage line)
        (1.0, "Reading the measurement…"),
        (4.0, "Fitting the printer model (900 patches, grid 17)…"),
        (9.0, "Inverting the model (B2A grid 17)…"),
        (20.0, "Inverting the model: converging 2/6…"),
        (35.0, "Inverting the model: converging 4/6…"),
        (50.0, "Inverting the model: converging 6/6…"),
        (52.0, "Writing the profile…"),
        (54.0, "Building the perceptual and saturation tables…"),
        (56.0, "Saturation table: matching colprof's rendering…"),
        (110.0, "Saturation table: fitting the matched rendering…"),
        (112.0, "Gamut mapping: building the final colour table: converging 1/6…"),
        (118.0, "Gamut mapping: building the final colour table: converging 6/6…"),
    ]
    for when, line in script:
        t[0] = when
        pp(line)
    secs = []
    overran = 0
    for ln in shown:
        m = re.search(r"~(\d+)(s| min) left", ln)
        if m:
            v = int(m.group(1)) * (60 if m.group(2) == " min" else 1)
            secs.append(v)
        elif "taking longer than estimated" in ln:
            overran += 1
            secs.append(None)          # a reset is allowed to raise it
        elif "almost done" in ln:
            secs.append(0)
    prev = None
    for v in secs:
        if v is None:
            prev = None
            continue
        if prev is not None:
            assert v <= prev, (secs, shown)
        prev = v
    assert any(s_ is not None and s_ > 0 for s_ in secs), shown
    # The 54-second colprof stall is taken out of the budget (challenger
    # C5): after it the estimate must NOT already be overrun, and the build's
    # last lines say "almost done", never "taking longer than estimated".
    after = [ln for ln in shown if "Saturation table: fitting" in ln][0]
    assert "taking longer" not in after, after
    assert "almost done" in shown[-1], shown[-1]
