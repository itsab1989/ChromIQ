"""DOES THIS UV PASS BELONG TO THIS LAMP PASS? (the owner's question of
2026-11-18: each pass of a hand dual scan is its own unit, so a UV pass
read again must be proved to belong to the strip's lamp pass.)

The UV pass carries almost no colour, so it cannot be recognised by colour
the way ArgyllCMS recognises a lamp pass. But at 380-400 nm nothing glows
(the factory tables are zero there), so what the UV reading holds there is
only the LED's light that the patch reflects: ``U = (T / W) * L`` for the
patch's own lamp reflectance L. Across a strip's patches the observed UV
signal at 380-400 nm must therefore follow ``(T / W) * L`` of the SAME
strip's lamp pass.

MEASURED on the two instruments' private recordings (2026-11-18,
work-folder ``proof/out/e_pairing.txt``), per strip, UV pass against its
own lamp pass and against every OTHER row's lamp pass:

* correlation across the patches: right 0.9997-0.9999; wrong at most 0.574;
* median |ratio - 1|: right at most 0.044; wrong at least 0.146.

So a pass is refused (``uv_pass_wrong_strip``) when the correlation is
below :data:`MIN_CORRELATION` or the median ratio is off by more than
:data:`MAX_MEDIAN_RATIO_ERROR`. When the strip's patches hardly differ at
380-400 nm (a strip of one colour) the correlation says nothing and only the
ratio is asked.

DARK PATCHES (review of 2026-11-18, M2). The ratio's noise grows as the
lamp level falls (instrument 1, |ratio - 1| median 0.025 at lamp reflectance
0.1-0.3 at 380-400 nm, 0.036 at 0.05-0.1, 0.072 at 0.02-0.05, 0.107 below
0.02): a strip of dark patches was refused as "wrong strip" every time,
though it was its own pass, and a black patch (lamp signal 0) as "values
that are not numbers". So a patch takes part only when its predicted LED
signal, or the observed one, reaches what a patch of reflectance
:data:`LEVEL_FLOOR` would give (``(T / W) * LEVEL_FLOOR``); the observed one
counts at twice the floor, so that a dark strip's lamp pass with a BRIGHT
strip's UV pass is still judged (and refused). With fewer than
:data:`MIN_USABLE` such patches the pairing is SKIPPED for the strip: the
pass is accepted, the evidence says ``checked = False`` and the caller shows
the note ``pairing_not_checked`` (:data:`~workflow.dual_scan.reasons.NOTES`).
The ruler checks (:mod:`.cut`) apply to every pass all the same.

NO UV LIGHT. When the usable patches' median ratio is below
:data:`MIN_LIGHT_RATIO`, the pass brought back almost no LED light: the LED
did not light, or the pass was read over a much darker strip. Refused with
``uv_pass_no_uv_light``, whose sentence names both.

The check does not need the paper to glow; on a paper without brightener a
mix-up could not change M1 or M2 anyway (J = 0), so there a refusal costs a
re-read but protects nothing: the caller may accept it with :func:`glows`
False.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from workflow.dual_scan.model import WAVELENGTHS, DualCalibration
from workflow.dual_scan.reasons import DualScanRefused

#: the bands that hold only reflected LED light (no glow, tables zero)
LED_BANDS_NM = (380, 400)
MIN_CORRELATION = 0.95
MAX_MEDIAN_RATIO_ERROR = 0.10
#: below this spread (std / mean of the prediction) the correlation is not asked
MIN_SPREAD = 0.05
#: lamp reflectance at 380-400 nm below which a patch's ratio is mostly noise
#: (MEASURED, instrument 1: at 0.05-0.1 the error is at most 0.084, below
#: 0.05 it reaches 0.22)
LEVEL_FLOOR = 0.05
#: fewest patches above the floor for any judgment of the strip
MIN_USABLE = 2
#: fewest usable patches for the correlation to be asked
MIN_FOR_CORRELATION = 3
#: below this median observed / predicted the pass brought back no LED light
MIN_LIGHT_RATIO = 0.3


@dataclass
class PairingEvidence:
    correlation: float          # nan when not asked
    median_ratio_error: float   # nan when not checked
    patches: int
    usable: int = 0             # patches above the signal floor
    checked: bool = True        # False: too dark to judge (note pairing_not_checked)


def _led(x: np.ndarray) -> np.ndarray:
    m = (WAVELENGTHS >= LED_BANDS_NM[0]) & (WAVELENGTHS <= LED_BANDS_NM[1])
    return np.asarray(x, dtype=float)[:, m].mean(axis=1)


def check_pairing(lamp, uv, calibration: DualCalibration) -> PairingEvidence:
    """Refuses (``uv_pass_wrong_strip``, ``uv_pass_no_uv_light``) a UV pass
    that does not follow the lamp pass it is paired with; returns the
    evidence otherwise (``checked`` False when too dark to judge)."""
    L = np.atleast_2d(np.asarray(lamp, dtype=float))
    U = np.atleast_2d(np.asarray(uv, dtype=float))
    if L.shape != U.shape:
        raise DualScanRefused("uv_pass_count", f"{L.shape} vs {U.shape}")
    cal = calibration.checked(L.shape[1])
    tw = np.asarray(cal.uv_tile) / np.asarray(cal.white)
    pred = _led(L * tw[None, :])
    obs = _led(U)
    if not (np.all(np.isfinite(pred)) and np.all(np.isfinite(obs))):
        raise DualScanRefused("bad_values", "LED bands")
    floor = float(_led(tw[None, :] * LEVEL_FLOOR)[0])
    use = (pred >= floor) | (obs >= 2.0 * floor)
    n = int(L.shape[0])
    k = int(use.sum())
    if k < MIN_USABLE:
        return PairingEvidence(float("nan"), float("nan"), n, k, False)
    p, o = np.maximum(pred[use], 1e-12), obs[use]
    ratio = o / p
    if float(np.median(ratio)) < MIN_LIGHT_RATIO:
        raise DualScanRefused("uv_pass_no_uv_light",
                              f"median observed / predicted {float(np.median(ratio)):.3f}")
    err = float(np.median(np.abs(ratio - 1.0)))
    corr = float("nan")
    if k >= MIN_FOR_CORRELATION and p.std() / p.mean() >= MIN_SPREAD:
        corr = float(np.corrcoef(o, p)[0, 1])
    ev = PairingEvidence(corr, err, n, k, True)
    if err > MAX_MEDIAN_RATIO_ERROR or (corr == corr and corr < MIN_CORRELATION):
        raise DualScanRefused("uv_pass_wrong_strip",
                              f"correlation {corr:.3f}, median ratio error {err:.3f}, "
                              f"{k} of {n} patches judged")
    return ev


def glows(conditions_glow: np.ndarray, threshold: float = 0.002) -> bool:
    """Whether a strip's paper glows at all (largest patch mean of J over the
    glow bands above *threshold* reflectance)."""
    j = np.asarray(conditions_glow, dtype=float)
    return bool(j.size) and float(np.nanmax(np.abs(j).mean(axis=1))) > threshold
