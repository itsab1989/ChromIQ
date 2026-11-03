# SPDX-License-Identifier: GPL-3.0-or-later
"""Spectral arithmetic with explicit wavelength coverage and caller-supplied data.

No illuminant, observer, excitation or instrument correction table is bundled.
"""
from bisect import bisect_right
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Curve:
    wavelengths: tuple
    values: tuple

    def __post_init__(self):
        object.__setattr__(self,'wavelengths',tuple(self.wavelengths))
        object.__setattr__(self,'values',tuple(self.values))
        if len(self.wavelengths)!=len(self.values) or len(self.values)<2:
            raise ValueError('A spectral curve requires at least two wavelength/value pairs')
        if not all(math.isfinite(v) for v in self.wavelengths+self.values):
            raise ValueError('Non-finite spectral data')
        if any(a>=b for a,b in zip(self.wavelengths,self.wavelengths[1:])):
            raise ValueError('Wavelengths must be strictly increasing')

    def at(self,wavelength):
        if not math.isfinite(wavelength) or not self.wavelengths[0]<=wavelength<=self.wavelengths[-1]:
            raise ValueError('Spectral extrapolation is not permitted')
        i=min(bisect_right(self.wavelengths,wavelength)-1,len(self.values)-2)
        a,b=self.wavelengths[i:i+2];t=(wavelength-a)/(b-a)
        return self.values[i]*(1-t)+self.values[i+1]*t

    def resample(self,wavelengths):
        wavelengths=tuple(wavelengths)
        return Curve(wavelengths,tuple(self.at(w) for w in wavelengths))


def product_integral(curves,lower,upper):
    """Exactly integrate products of up to three piecewise-linear curves.

    Simpson integration on each union-knot segment is exact for polynomials
    through degree three, avoiding an arbitrary integration sampling pitch.
    """
    curves=tuple(curves)
    if not 1<=len(curves)<=3 or not math.isfinite(lower) or not math.isfinite(upper) or lower>=upper:
        raise ValueError('Invalid product integration')
    if any(lower<c.wavelengths[0] or upper>c.wavelengths[-1] for c in curves):
        raise ValueError('Integration requires complete spectral coverage')
    knots=sorted({lower,upper}|{w for c in curves for w in c.wavelengths if lower<w<upper})
    def value(w):return math.prod(c.at(w) for c in curves)
    return math.fsum((b-a)/6*(value(a)+4*value((a+b)/2)+value(b)) for a,b in zip(knots,knots[1:]))


@dataclass(frozen=True)
class Colorimetry:
    xyz: tuple
    white_xyz: tuple
    lab: tuple
    coverage_nm: tuple


def xyz_to_lab(xyz,white):
    if len(xyz)!=3 or len(white)!=3 or not all(math.isfinite(v) for v in tuple(xyz)+tuple(white)) or min(white)<=0:
        raise ValueError('Invalid XYZ/white point')
    epsilon=216/24389;kappa=24389/27
    def f(t):return t**(1/3) if t>epsilon else (kappa*t+16)/116
    x,y,z=[f(v/w) for v,w in zip(xyz,white)]
    return (116*y-16,500*(x-y),200*(y-z))


def colorimetry(radiance_factor,illuminant,observer):
    """Relative XYZ/Lab over the supplied measurement range, explicitly reported.

    A finite-range result is not a claim to ASTM weighting tables or a full
    visible-range measurement. Illuminant/observer data must cover that range.
    """
    if len(observer)!=3 or min(illuminant.values)<0 or any(min(c.values)<0 for c in observer):
        raise ValueError('Invalid illuminant or observer')
    lower,upper=radiance_factor.wavelengths[0],radiance_factor.wavelengths[-1]
    norm=product_integral((illuminant,observer[1]),lower,upper)
    if norm<=0:raise ValueError('Illuminant has no positive luminance over measurement range')
    xyz=tuple(100*product_integral((radiance_factor,illuminant,c),lower,upper)/norm for c in observer)
    white=tuple(100*product_integral((illuminant,c),lower,upper)/norm for c in observer)
    return Colorimetry(xyz,white,xyz_to_lab(xyz,white),(lower,upper))
