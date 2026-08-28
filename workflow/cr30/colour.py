"""Spectrum -> XYZ -> L*a*b*.

NOT device protocol. This is a small, self-validating colour utility used to
interpret what the CR30 returns, kept separate from `frame.py`/`session.py` so
the protocol layer stays free of colour science.

The default observer is **CIE 1964 10 degree** with **D65**, because that is
what the device's own display reports and what its own Lab numbers are computed
under. ⚠ This docstring previously said the opposite ("CIE 1931 2 degree ...
that is what the vendor software pins, M0 / D50 / 1931 2 deg") while the code
below already selected 10 degrees -- a reader would have believed the wrong
observer was in force.

D65/10 is not merely assumed from the screen label. Two vendor captures in
`PRIORART-001` carry the vendor application's own L*a*b* in their file names
for a SATURATED cyan, which is a sample that CAN separate observers:

    "Test Sample 36.61 -20.75 -2.86"  -> our decode, D65/10: 36.612 -20.732 -2.847   dE 0.02
                                                    D65/2 : 36.154 -20.448 -4.302   dE 1.46
                                                    D50/10: 36.109 -21.224 -4.150   dE 1.35
                                                    D50/2 : 35.678 -21.177 -5.550   dE 2.79

A 60:1 margin, on a second unit, against numbers we did not compute. The
near-neutral tile in `MEASUREMENT.md` could only separate D65 from D50; this
separates the observer as well. Argyll ships CIE *2012* 2 deg, which is a
different observer again and would introduce a difference of our own making.

The observer and illuminant tables are hard-coded and are therefore CHECKED:
`validate_illuminants()` recomputes each white point's chromaticity from these
very tables and compares it against the published value. A mistyped coefficient
fails the check instead of quietly producing plausible-looking Lab values.
"""
from __future__ import annotations

WL = list(range(400, 701, 10))          # the CR30's 31 bands

# CIE standard illuminant relative SPDs, 400-700 nm at 10 nm.
#
# ⚠ These are NOT hand-typed. They are ArgyllCMS 3.5.0's own `il_D50` / `il_D65`
# (`xicc/xspect.c:244`), sampled at the CR30's 31 wavelengths. Using Argyll's
# numbers means our XYZ and Argyll's XYZ cannot drift apart, and they meet in
# the same .ti3.
#
# The hand-typed tables these replaced were wrong by up to 0.55 at 600 nm, and
# `validate_illuminants()` PASSED them -- a chromaticity check is nearly blind
# to a single-band error. `tests/test_colour_tables.py` re-derives these from
# the Argyll source when it is present.
#
# NB the ref/D50_*.sp files are the UV-content variants used for FWA, NOT the
# colorimetric D50: D50_0.0.sp is zero below 440 nm. Do not substitute them.
D65 = [
    82.7549, 91.486, 93.4318, 86.6823, 104.865, 117.008,
    117.812, 114.861, 115.923, 108.811, 109.354, 107.802,
    104.79, 107.689, 104.405, 104.046, 100, 96.3342,
    95.788, 88.6856, 90.0062, 89.5991, 87.6987, 83.2886,
    83.6992, 80.0268, 80.2146, 82.2778, 78.2842, 69.7213,
    71.6091,
]
# CORRECTED 2026-08-28 by [CR30-SKEPTIC]. The previous table was contaminated
# from 610 nm and its last five entries (660-700 nm) were literally D65's
# entries for 600-640 nm, copied in. The error reached 13.4 units (13 %) at
# 670 nm. `validate_illuminants()` passed it: a correct table validates to
# ~1e-4 chromaticity error and the corrupt one gave 1.5e-3, four times inside
# the 6e-3 tolerance. The tolerance has been tightened to 1e-3 and a mutation
# test now proves the control can see this class of error.
D50 = [
    49.31, 56.51, 60.03, 57.82, 74.82, 87.25,
    90.61, 91.37, 95.11, 91.96, 95.72, 96.61,
    97.13, 102.1, 100.75, 102.32, 100, 97.74,
    98.92, 93.5, 97.69, 99.27, 99.04, 95.72,
    98.86, 95.67, 98.19, 103, 99.13, 87.38,
    91.6,
]

# CIE 1931 2-degree observer at 10 nm, 400-700 (fallback if Argyll is absent).
_X = [0.01431, 0.04351, 0.13438, 0.28390, 0.34828, 0.33620, 0.29080, 0.19536,
      0.09564, 0.03201, 0.00490, 0.00930, 0.06327, 0.16550, 0.29040, 0.43345,
      0.59450, 0.76210, 0.91630, 1.02630, 1.06220, 1.00260, 0.85445, 0.64240,
      0.44790, 0.28350, 0.16490, 0.08740, 0.04677, 0.02270, 0.01136]
_Y = [0.00040, 0.00121, 0.00400, 0.01160, 0.02300, 0.03800, 0.06000, 0.09098,
      0.13902, 0.20802, 0.32300, 0.50300, 0.71000, 0.86200, 0.95400, 0.99495,
      0.99500, 0.95200, 0.87000, 0.75700, 0.63100, 0.50300, 0.38100, 0.26500,
      0.17500, 0.10700, 0.06100, 0.03200, 0.01700, 0.00821, 0.00410]
_Z = [0.06785, 0.20740, 0.64560, 1.38560, 1.74706, 1.77211, 1.66920, 1.28764,
      0.81295, 0.46518, 0.27200, 0.15820, 0.07825, 0.04216, 0.02030, 0.00875,
      0.00390, 0.00210, 0.00165, 0.00110, 0.00080, 0.00034, 0.00019, 0.00005,
      0.00002, 0.00000, 0.00000, 0.00000, 0.00000, 0.00000, 0.00000]

# CIE 1964 10-degree supplementary observer at 10 nm, 400-700.
# The CR30's own display reports "D65/10", so THIS is the observer that must be
# used to compare against numbers the device itself shows (operator, 2026-08-28).
_X10 = [0.01911, 0.08474, 0.20449, 0.31468, 0.38373, 0.37070, 0.30228, 0.19562,
        0.08051, 0.01617, 0.00382, 0.03747, 0.11775, 0.23649, 0.37677, 0.52977,
        0.70522, 0.87866, 1.01416, 1.11852, 1.12399, 1.03048, 0.85630, 0.64747,
        0.43157, 0.26834, 0.15258, 0.08126, 0.04085, 0.01994, 0.00958]
_Y10 = [0.002004, 0.008756, 0.021391, 0.038676, 0.062077, 0.089456, 0.128201,
        0.185190, 0.253589, 0.339133, 0.460777, 0.606741, 0.761757, 0.875211,
        0.961988, 0.991761, 0.997340, 0.955552, 0.868934, 0.777405, 0.658341,
        0.527963, 0.398057, 0.283493, 0.179828, 0.107633, 0.060281, 0.031800,
        0.015905, 0.007749, 0.003718]
_Z10 = [0.08601, 0.38937, 0.97254, 1.55348, 1.96723, 1.99480, 1.74537, 1.31756,
        0.77213, 0.41525, 0.21850, 0.11204, 0.06071, 0.03045, 0.01368, 0.00399,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

OBS = {"2": (_X, _Y, _Z), "10": (_X10, _Y10, _Z10)}

# ⚠ NO PROCESS-WIDE OBSERVER STATE.
#
# An earlier version kept the observer in module globals with a `use_observer()`
# switch. That is a trap in an application: two callers wanting different
# conditions race, and whichever ran last silently decides the colour of the
# other's numbers. ChromIQ profiling needs **D50 / CIE 1931 2 degree**; the
# device's own display uses D65/10 for ITS readout. Both are legitimate and they
# must never share a global.
#
# Every function now takes the condition explicitly, and the profiling default
# is the one Argyll expects.
PROFILING_OBSERVER = "2"      # CIE 1931 2 deg -- what colprof/.ti3 expect
DEVICE_OBSERVER = "10"        # CIE 1964 10 deg -- what the CR30 shows on screen


def _obs(observer):
    try:
        return OBS[str(observer)]
    except KeyError:
        raise ValueError(
            f"observer must be '2' or '10', got {observer!r}") from None


def spectrum_to_xyz(refl, illum=D50, observer=PROFILING_OBSERVER):
    """refl: 31 values in PERCENT reflectance (as the CR30 returns them).

    Defaults to **D50 / CIE 1931 2 degree**, the condition ArgyllCMS expects in
    a .ti3. Y is returned on a 0-100 scale (a perfect diffuser is Y=100), which
    is what `chartread -x` and `colprof` want.
    """
    if len(refl) != len(WL):
        raise ValueError(f"need {len(WL)} bands, got {len(refl)}")
    xb, yb, zb = _obs(observer)
    k = 100.0 / sum(s * y for s, y in zip(illum, yb))
    r = [v / 100.0 for v in refl]
    return tuple(k * sum(ri * s * c for ri, s, c in zip(r, illum, cmf))
                 for cmf in (xb, yb, zb))


def white_point(illum=D50, observer=PROFILING_OBSERVER):
    xb, yb, zb = _obs(observer)
    k = 100.0 / sum(s * y for s, y in zip(illum, yb))
    return tuple(k * sum(s * c for s, c in zip(illum, cmf))
                 for cmf in (xb, yb, zb))


def xyz_to_lab(xyz, illum=D50, observer=PROFILING_OBSERVER):
    wp = white_point(illum, observer)
    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29
    fx, fy, fz = (f(c / w) for c, w in zip(xyz, wp))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def spectrum_to_lab(refl, illum=D50, observer=PROFILING_OBSERVER):
    return xyz_to_lab(spectrum_to_xyz(refl, illum, observer), illum, observer)


def validate_illuminants(tol=0.001, observer=PROFILING_OBSERVER):
    """Positive control on OUR OWN hard-coded numbers.

    Recomputes each illuminant's chromaticity and compares with the published
    value. A mistyped coefficient shows up here instead of quietly shifting
    every Lab number we report.

    ⚠ The tolerance is 1e-3 and not 6e-3 for a measured reason: at 6e-3 this
    control PASSED a D50 table whose 670 nm entry was 13 % wrong (see the note
    on `D50`). A control that cannot fail on a real defect is not a control.
    `tests/test_colour_tables.py::test_the_illuminant_control_can_actually_fail`
    proves the mutation lands.
    """
    out = {}
    want_by_obs = {
        "2":  {"D65": (0.31272, 0.32903), "D50": (0.34567, 0.35850)},
        "10": {"D65": (0.31382, 0.33100), "D50": (0.34773, 0.35952)},
    }
    key = str(observer)
    for name, sp, want in (("D65", D65, want_by_obs[key]["D65"]),
                           ("D50", D50, want_by_obs[key]["D50"])):
        X, Y, Z = white_point(sp, observer)
        x, y = X / (X + Y + Z), Y / (X + Y + Z)
        err = max(abs(x - want[0]), abs(y - want[1]))
        out[name] = {"xy": (round(x, 5), round(y, 5)), "expected": want,
                     "max_error": round(err, 5), "ok": err < tol}
    return out


if __name__ == "__main__":
    print("observer:", OBSERVER)
    for k, v in validate_illuminants().items():
        print(f"  {k}: xy={v['xy']} expected={v['expected']} "
              f"err={v['max_error']} {'OK' if v['ok'] else '** FAIL **'}")
