# SPDX-License-Identifier: GPL-3.0-or-later
"""Scoped research contrast with a candidate illumination-shape correction.

Dominant-source approximation: delta_target = gain * delta_raw * source/target.
Source/target curves must be supplied explicitly. Auxiliary FD-9 arrays are
not certified irradiance data, and this helper does not produce ISO spectra.
No vendor coefficients, source curves or reference spectra are bundled.
"""
from dataclasses import dataclass
import math
from .spectral import Curve


def _feature(low, high, source, target, wavelength):
    a, b = source.at(wavelength), target.at(wavelength)
    if a <= 0 or b <= 0:
        raise ValueError('Require positive source and target signal in every output band')
    value = (high.at(wavelength) - low.at(wavelength)) * (a / b)
    if not math.isfinite(value):
        raise ValueError('Source-adjusted contrast is non-finite')
    return value


@dataclass(frozen=True)
class ResearchContrast:
    contrast: Curve
    validated: bool = False
    description: str = 'source-shape research contrast; not an ISO measurement condition'


@dataclass(frozen=True)
class SourceContrastModel:
    wavelengths: tuple
    gain: float
    scope: str
    reference_source: str

    def __post_init__(self):
        Curve(self.wavelengths, [0.] * len(self.wavelengths))
        if not math.isfinite(self.gain) or self.gain <= 0:
            raise ValueError('Require a positive finite research gain')
        if not isinstance(self.scope, str) or not self.scope or not isinstance(self.reference_source, str) or not self.reference_source:
            raise ValueError('Explicit experiment scope and reference provenance required')

    def apply(self, low, high, source, target, *, scope):
        if scope != self.scope:
            raise ValueError('Source-contrast model belongs to another experiment scope')
        values = [self.gain * _feature(low, high, source, target, nm) for nm in self.wavelengths]
        return ResearchContrast(Curve(self.wavelengths, values))


def fit_source_contrast(low, high, source, target, reference_contrast, *, scope, reference_source, minimum_signal=1e-6):
    """Fit one positive scalar on explicitly supplied reference bands only.

    Fail when the observed contrast cannot identify a gain. Negative predicted
    contrast is retained; clipping must not conceal model or measurement error.
    The caller remains responsible for distinguishing fit and holdout samples.
    """
    if not math.isfinite(minimum_signal) or minimum_signal <= 0:
        raise ValueError('Require positive finite minimum contrast signal')
    nm = reference_contrast.wavelengths
    features = tuple(_feature(low, high, source, target, w) for w in nm)
    scale = max(abs(v) for v in features)
    if scale < minimum_signal:
        raise ValueError('Source contrast is unidentifiable')
    normalized = tuple(v / scale for v in features)
    numerator = math.fsum(v * r for v, r in zip(normalized, reference_contrast.values))
    denominator = math.fsum(v * v for v in normalized)
    gain = (numerator / denominator) / scale
    return SourceContrastModel(nm, gain, scope, reference_source)
