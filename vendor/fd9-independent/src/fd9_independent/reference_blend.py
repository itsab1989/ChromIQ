# SPDX-License-Identifier: GPL-3.0-or-later
"""Material/capture-scoped research blend learned from an independent white.

This estimates a wavelength-dependent two-source blend without a bundled
excitation table. It does not establish ISO conditions, raw-block meaning,
instrument calibration accuracy, or transfer to another substrate/session.
"""
from dataclasses import dataclass
import math
from .spectral import Curve
from .fluorescence import ModelResult


@dataclass(frozen=True)
class ReferenceBlend:
    wavelengths: tuple
    weights: tuple
    identified: tuple
    white_residual: tuple
    scope: str
    reference_source: str

    def apply(self,sample1,sample2,*,scope):
        if scope!=self.scope:raise ValueError('Reference blend belongs to a different material/capture scope')
        values=tuple(w*sample1.at(nm)+(1-w)*sample2.at(nm) for nm,w in zip(self.wavelengths,self.weights))
        return ModelResult(Curve(self.wavelengths,values),self.weights,'independent-reference research blend; not an ISO-condition claim')


def fit_reference_blend(white1,white2,reference,uncertainty,*,scope,reference_source):
    """Regularized least-squares blend, independently fitted at each wavelength.

    Minimize (w*d - (reference-white2))^2 + sigma^2*(w-.5)^2.
    Thus w=.5+d*(reference-(white1+white2)/2)/(d*d+sigma*sigma).
    The half-weight prior limits noise amplification when sources agree. Bands
    lacking 3-sigma source contrast are explicitly marked unidentifiable.
    Uncertainty is caller-provided in radiance-factor units; no silent fitting
    against colored validation patches or condition-specific endpoints occurs.
    """
    if not isinstance(scope,str) or not scope or not isinstance(reference_source,str) or not reference_source:
        raise ValueError('Explicit capture/material scope and reference provenance required')
    nm=reference.wavelengths;uncertainty=tuple(uncertainty)
    if len(uncertainty)!=len(nm) or not all(math.isfinite(s) and s>0 for s in uncertainty):raise ValueError('Require positive finite uncertainty for every wavelength')
    weights=[];identified=[];residual=[]
    for wavelength,target,sigma in zip(nm,reference.values,uncertainty):
        a,b=white1.at(wavelength),white2.at(wavelength);d=a-b
        mean=.5*a+.5*b;scale=max(abs(d),sigma)
        if not math.isfinite(d):raise ValueError('Source contrast overflows numerical range')
        dn,sn=d/scale,sigma/scale
        w=.5+dn*((target-mean)/scale)/(dn*dn+sn*sn)
        error=w*a+(1-w)*b-target
        if not math.isfinite(w) or not math.isfinite(error):raise ValueError('Non-finite reference fit')
        weights.append(w);identified.append(abs(d)>=3*sigma);residual.append(error)
    return ReferenceBlend(nm,tuple(weights),tuple(identified),tuple(residual),scope,reference_source)
