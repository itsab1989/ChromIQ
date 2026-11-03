# SPDX-License-Identifier: GPL-3.0-or-later
"""Research-only two-illuminant fluorescence model from published equations.

Model assumptions: measured inputs are already radiance factors; substrate
fluorescence is separable into excitation and emission functions. Neither raw
FD-9 block identity nor excitation data is inferred or supplied by this module.
Source: Yamamoto et al., Konica Minolta Technology Report 8 (2011), pp.138-142,
https://research.konicaminolta.com/jp/pdf/technology_report/2011/pdf/industry_008.pdf
"""
from dataclasses import dataclass
import math
from .spectral import Curve,product_integral


@dataclass(frozen=True)
class ModelResult:
    radiance_factor: Curve
    weights: tuple
    measurement_condition: str='research two-illuminant model; unvalidated'
    validated: bool=False


def combine(sample1,sample2,illuminant1,illuminant2,target,excitation,output_nm,*,minimum_contrast=1e-6):
    """Solve Btarget = w B1 + (1-w) B2 with q = integral(I e)/I(lambda).

    Excitation and illuminants must cover the entire requested excitation
    interval. Weights can exceed [0,1]; no clipping hides model extrapolation.
    Equal excitation efficiencies are unidentifiable and fail rather than
    silently selecting a raw block or averaging it.
    """
    if not math.isfinite(minimum_contrast) or minimum_contrast<=0:raise ValueError('Invalid excitation contrast threshold')
    sources=(illuminant1,illuminant2,target)
    if any(min(c.values)<0 for c in sources) or min(excitation.values)<0:
        raise ValueError('Illuminant and excitation values must be nonnegative')
    lower,upper=excitation.wavelengths[0],excitation.wavelengths[-1]
    energy=tuple(product_integral((c,excitation),lower,upper) for c in sources)
    if max(energy)<=0:raise ValueError('Excitation function has no measured response')
    wavelengths=tuple(output_nm);weights=[];values=[]
    for wavelength in wavelengths:
        powers=tuple(c.at(wavelength) for c in sources)
        if min(powers)<=0:raise ValueError('Emission wavelength has zero illumination')
        q1,q2,qt=(e/p for e,p in zip(energy,powers))
        contrast=q1-q2
        if abs(contrast)<=minimum_contrast*max(abs(q1),abs(q2),1e-300):
            raise ValueError(f'Excitation response is unidentifiable at {wavelength} nm')
        weight=(qt-q2)/contrast
        value=weight*sample1.at(wavelength)+(1-weight)*sample2.at(wavelength)
        if not math.isfinite(weight) or not math.isfinite(value):raise ValueError('Non-finite model result')
        weights.append(weight);values.append(value)
    return ModelResult(Curve(wavelengths,tuple(values)),tuple(weights))
