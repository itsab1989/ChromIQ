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
ratio is asked. The check does not need the paper to glow; on a paper without
brightener a mix-up could not change M1 or M2 anyway (J = 0), so there a
refusal costs a re-read but protects nothing: the caller may accept it with
:func:`glows` False.
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


@dataclass
class PairingEvidence:
    correlation: float          # nan when not asked
    median_ratio_error: float
    patches: int


def _led(x: np.ndarray) -> np.ndarray:
    m = (WAVELENGTHS >= LED_BANDS_NM[0]) & (WAVELENGTHS <= LED_BANDS_NM[1])
    return np.asarray(x, dtype=float)[:, m].mean(axis=1)


def check_pairing(lamp, uv, calibration: DualCalibration) -> PairingEvidence:
    """Refuses (``uv_pass_wrong_strip``) a UV pass that does not follow the
    lamp pass it is paired with; returns the evidence otherwise."""
    L = np.atleast_2d(np.asarray(lamp, dtype=float))
    U = np.atleast_2d(np.asarray(uv, dtype=float))
    if L.shape != U.shape:
        raise DualScanRefused("uv_pass_count", f"{L.shape} vs {U.shape}")
    cal = calibration.checked(L.shape[1])
    tw = np.asarray(cal.uv_tile) / np.asarray(cal.white)
    pred = _led(L * tw[None, :])
    obs = _led(U)
    if not (np.all(np.isfinite(pred)) and np.all(np.isfinite(obs))) or np.any(pred <= 0):
        raise DualScanRefused("bad_values", "LED bands")
    err = float(np.median(np.abs(obs / pred - 1.0)))
    corr = float("nan")
    if L.shape[0] >= 3 and pred.std() / pred.mean() >= MIN_SPREAD:
        corr = float(np.corrcoef(obs, pred)[0, 1])
    ev = PairingEvidence(corr, err, int(L.shape[0]))
    if err > MAX_MEDIAN_RATIO_ERROR or (corr == corr and corr < MIN_CORRELATION):
        raise DualScanRefused("uv_pass_wrong_strip",
                              f"correlation {corr:.3f}, median ratio error {err:.3f}")
    return ev


def glows(conditions_glow: np.ndarray, threshold: float = 0.002) -> bool:
    """Whether a strip's paper glows at all (largest patch mean of J over the
    glow bands above *threshold* reflectance)."""
    j = np.asarray(conditions_glow, dtype=float)
    return bool(j.size) and float(np.nanmax(np.abs(j).mean(axis=1))) > threshold
