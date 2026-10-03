"""Was a strip read twice? The live check while measuring (#182, approved).

Knut, #182 5963903650, question 5 (*"Do you want the optional live check while
measuring, which compares each new strip with the strips already measured and
asks 'Strip D looks very like strip C, which you already measured. Did you read
strip C again?'"*): **"Yes."**

WHY IT LOOKS ONLY AT WHAT WAS MEASURED. chartread's own "wrong strip" test
compares a strip with the chart's *expected* colours, and on low-quality paper
those are far from what the paper can print, which is why ChromIQ runs it with
``-S``. This check never looks at expected colours: it compares the new strip
with the strips already measured on the same sheet, which are the paper's own
colours. Measured on Knut's chart, two different strips are at least ΔE76 36
apart and the same strip read twice is under 1 (#182 5960926048), so a bar of
3 is far from both.

WHAT IT NEVER DOES:

* compare a strip with ITSELF. A strip read again where the reader is (strip C
  re-read with the reader on C) is a legitimate re-read; only a strip the
  engine filed under D whose readings match C is a question;
* fire on two strips the chart DESIGNED alike: their device values are
  compared first, and alike designs are left alone;
* decide on a handful of patches: fewer than :data:`MIN_PATCHES` compared
  says nothing.

The comparison allows the strip to be one patch out (the engine's DTP51-style
offset fix) and read in either direction, because a swipe of C filed as D need
not line up patch for patch.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

#: Median ΔE76 under which two strips count as the same strip read twice.
#: Knut's chart: different strips >= 36, the same strip twice < 1.
THRESHOLD_DE76 = 3.0

#: At least this many patch pairs must be compared before anything is said.
MIN_PATCHES = 4

#: Two strips whose DEVICE values differ by less than this (median, on the
#: 0-100 scale) were designed alike, so looking alike proves nothing.
SAME_DESIGN_DEVICE = 2.0

#: How far one strip may sit from the other, in patches.
SHIFTS = (-1, 0, 1)

_D50 = (96.42, 100.0, 82.49)

Triple = Sequence[float]


def xyz_to_lab(xyz: Triple) -> tuple[float, float, float]:
    """CIE L*a*b* (D50) of an XYZ on the 0-100 scale, as the engine computes it."""
    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else \
            (24389.0 / 27.0 * t + 16.0) / 116.0
    fx, fy, fz = (f(max(0.0, float(v)) / w) for v, w in zip(xyz, _D50))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def _dist(a: Triple, b: Triple) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _median(xs: "list[float]") -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def strip_distance(a: "Sequence[Triple]", b: "Sequence[Triple]") -> "float | None":
    """The smallest median distance between two strips' values.

    Tried both ways round and one patch out either side; None when no
    alignment compares at least :data:`MIN_PATCHES` pairs.
    """
    best: "float | None" = None
    for reverse in (False, True):
        bb = list(b)[::-1] if reverse else list(b)
        for shift in SHIFTS:
            pairs = [(a[i], bb[i + shift]) for i in range(len(a))
                     if 0 <= i + shift < len(bb)]
            if len(pairs) < MIN_PATCHES:
                continue
            d = _median([_dist(x, y) for x, y in pairs])
            if best is None or d < best:
                best = d
    return best


@dataclass(frozen=True)
class ReadTwice:
    """Strip *strip* (what the engine filed it as) looks like *like*."""
    strip: str
    like: str
    median_de76: float


def looks_read_twice(
        strip: str,
        labs: "Sequence[Triple]",
        measured: "Mapping[str, Sequence[Triple]]",
        device: "Callable[[str], Sequence[Triple] | None] | None" = None,
) -> "ReadTwice | None":
    """The already-measured strip the new reading of *strip* matches, or None.

    *labs* are the new strip's L*a*b* values in strip order; *measured* maps
    every strip measured so far to its values. *device*, when given, returns a
    strip's design (device) values in the same order, so strips the chart
    designed alike are never compared.
    """
    if len(labs) < MIN_PATCHES:
        return None
    found: "ReadTwice | None" = None
    mine = device(strip) if device is not None else None
    for other, values in measured.items():
        if other == strip or not values:
            continue
        d = strip_distance(labs, values)
        if d is None or d >= THRESHOLD_DE76:
            continue
        if mine:
            theirs = device(other) if device is not None else None
            if theirs:
                dd = strip_distance(mine, theirs)
                if dd is not None and dd < SAME_DESIGN_DEVICE:
                    continue            # designed alike: proves nothing
        if found is None or d < found.median_de76:
            found = ReadTwice(strip, other, d)
    return found
