# SPDX-License-Identifier: GPL-3.0-or-later
"""Reference-scoped M2 compatibility estimate from two measured spectra.

Reporting rules were observed through owned black-box SDK output comparisons.
No manufacturer library, fitted weight table or reference spectrum is bundled.
References must be supplied by the caller; this is not traceable calibration.
"""
from dataclasses import dataclass
import math
from .spectral import Curve

FIT_BANDS = tuple(range(400, 611, 10))
OUTPUT_BANDS = tuple(range(380, 731, 10))


@dataclass(frozen=True)
class ResearchM2:
    spectrum: Curve
    calibrated: bool = False
    description: str = 'reference-scoped manufacturer M2 compatibility estimate'


@dataclass(frozen=True)
class M2ResearchModel:
    high_source_weights: tuple
    scope: str
    reference_source: str

    def __post_init__(self):
        object.__setattr__(self, 'high_source_weights', tuple(self.high_source_weights))
        if len(self.high_source_weights) != len(FIT_BANDS) or not all(math.isfinite(v) for v in self.high_source_weights):
            raise ValueError('Require one finite blend weight per 400–610 nm band')
        if not isinstance(self.scope, str) or not self.scope or not isinstance(self.reference_source, str) or not self.reference_source:
            raise ValueError('Explicit acquisition/calibration scope and reference provenance required')

    def apply(self, low, high, *, scope):
        if scope != self.scope:
            raise ValueError('M2 model belongs to another acquisition/calibration scope')
        values = [low.at(w) + q * (high.at(w) - low.at(w))
                  for w, q in zip(FIT_BANDS, self.high_source_weights)]
        # Preserve the manufacturer's observed reporting convention, including
        # extrapolation at the red edge. Do not disguise it as a measured band.
        values = [values[0], values[0]] + values
        values.extend((low.at(w) + high.at(w)) / 2 for w in range(620, 721, 10))
        values.append(2 * values[-1] - values[-2])
        return ResearchM2(Curve(OUTPUT_BANDS, values))


def fit_m2_research(references, *, scope, reference_source, minimum_rms_contrast=1e-6):
    """Fit per-band least-squares weights from explicit paired references.

    Each entry is (low-source Curve, high-source Curve, reference M2 Curve).
    Use separate holdouts to evaluate transfer. Extrapolating weights and
    negative output values are retained; a convex constraint would hide error.
    Scope must identify the instrument and acquisition/calibration context.
    """
    references = tuple(references)
    if len(references) < 2:
        raise ValueError('Require at least two paired calibration references')
    if not math.isfinite(minimum_rms_contrast) or minimum_rms_contrast <= 0:
        raise ValueError('Require positive finite minimum RMS contrast')
    weights = []
    for w in FIT_BANDS:
        differences = tuple(high.at(w) - low.at(w) for low, high, _ in references)
        scale = max(abs(d) for d in differences)
        if scale == 0:
            raise ValueError(f'Unidentifiable source contrast at {w} nm')
        normalized = tuple(d / scale for d in differences)
        denominator = math.fsum(d*d for d in normalized)
        if scale * math.sqrt(denominator / len(references)) < minimum_rms_contrast:
            raise ValueError(f'Unidentifiable source contrast at {w} nm')
        offsets = tuple(ref.at(w) - low.at(w) for low, _, ref in references)
        numerator = math.fsum(d*r for d, r in zip(normalized, offsets))
        weights.append((numerator / denominator) / scale)
    return M2ResearchModel(tuple(weights), scope, reference_source)
