# SPDX-License-Identifier: GPL-3.0-or-later
"""Caller-reference M1 compatibility model; no bundled calibration weights."""
from dataclasses import dataclass
from .spectral import Curve
from .m2_research import M2ResearchModel, OUTPUT_BANDS, fit_m2_research


@dataclass(frozen=True)
class ResearchM1:
    spectrum: Curve
    calibrated: bool = False
    description: str = 'reference-scoped manufacturer M1 compatibility estimate'


@dataclass(frozen=True)
class M1ResearchModel(M2ResearchModel):
    def apply(self, low, high, *, scope):
        # The visible/red construction is shared; only the UV edge differs.
        result = super().apply(low, high, scope=scope)
        values = (high.at(380), high.at(390)) + result.spectrum.values[2:]
        return ResearchM1(Curve(OUTPUT_BANDS, values))


def fit_m1_research(references, *, scope, reference_source, minimum_rms_contrast=1e-6):
    fit = fit_m2_research(references, scope=scope, reference_source=reference_source,
                         minimum_rms_contrast=minimum_rms_contrast)
    return M1ResearchModel(fit.high_source_weights, fit.scope, fit.reference_source)
