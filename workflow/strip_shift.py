"""The strip SHIFT test's Python twin (4.3.50, the patch finder study of 2026-11-19).

The test itself runs in the helper (``native/chartread_helper/chromiq_shift.c``),
on every strip the instrument's patch finder accepted, after the colour check
and before the strip is kept. This module computes exactly the same numbers, so
the suite can check the C file against it (``tests/test_strip_shift_c.py``) and
run the regression set of real strips without building anything. Nothing in the
app calls it.

What it decides: whether the first (or last) two or three readings of a strip
fit "moved by one patch, with the white paper in front" clearly better than
the colours they were filed under. That is what happens when ArgyllCMS's strip
patch finder takes the white run-up before the first patch (or the white after
the last) as a patch. See chromiq_shift.h for the full rule and the reasons for
its numbers.

Pure arithmetic, no Qt, no files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Sequence

#: The thresholds, the same numbers as chromiq_shift.h (CQS_*).
T3 = 10.0
T2 = 20.0
F2 = 0.5
QMIN = 0.5
NMIN = 4

_W = (0.9642, 1.0000, 0.8249)


def _lab(xyz: Sequence[float], scale: float = 1.0) -> "tuple[float, float, float]":
    f = []
    for j in range(3):
        t = scale * xyz[j] / 100.0 / _W[j]
        f.append(t ** (1.0 / 3.0) if t > 0.008856451586 else 7.787036979 * t + 16.0 / 116.0)
    return (116.0 * f[1] - 16.0, 500.0 * (f[0] - f[1]), 200.0 * (f[1] - f[2]))


def _de(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


@dataclass
class ShiftResult:
    flagged: bool = False
    #: 0: at the strip's first patch (as filed); 1: at its last
    end: int = 0
    k: int = 0
    score: float = -1e9
    #: s[end][k-2], d[end][k-2]
    s: list = field(default_factory=lambda: [[0.0, 0.0], [0.0, 0.0]])
    d: list = field(default_factory=lambda: [[0.0, 0.0], [0.0, 0.0]])
    m: float = 0.0


def shift_test(read: Sequence[Sequence[float]], expected: Sequence[Sequence[float]],
               paper: Sequence[float]) -> ShiftResult:
    """*read*, *expected*: XYZ (0..100) per patch in row order; *paper*: the
    expected XYZ of the chart's paper (its brightest expected patch)."""
    res = ShiftResult()
    n = len(read)
    if n < NMIN or len(expected) != n:
        return res
    sr = sum(r[1] for r in read)
    se = sum(e[1] for e in expected)
    if not (sr > 1e-6) or not (se > 1e-6):
        return res
    yn = se / sr
    lr = [_lab(r, yn) for r in read]
    le = [_lab(e) for e in expected]
    lp = _lab(paper)
    pd = sorted(_de(le[i], le[j]) for i in range(n) for j in range(i + 1, n))
    np_ = len(pd)
    res.m = pd[np_ // 2] if np_ % 2 else 0.5 * (pd[np_ // 2 - 1] + pd[np_ // 2])
    for e in (0, 1):
        a = b = d = 0.0
        for i in range(3):
            ix = i if e == 0 else n - 1 - i
            sh = lp if i == 0 else le[ix - 1 if e == 0 else ix + 1]
            a += _de(lr[ix], le[ix])
            b += _de(lr[ix], sh)
            d += _de(le[ix], sh)
            if i >= 1:
                kk = i + 1
                s, dd = (a - b) / kk, d / kk
                res.s[e][kk - 2] = s
                res.d[e][kk - 2] = dd
                if s > res.score and not res.flagged:
                    res.score = s
                if not (res.m > 0.0) or dd < QMIN * res.m:
                    continue
                ok = s >= T3 if kk == 3 else (s >= T2 and s >= F2 * dd)
                if ok and (not res.flagged or s > res.score):
                    res.flagged, res.end, res.k, res.score = True, e, kk, s
    return res
