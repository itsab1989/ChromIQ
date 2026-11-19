"""The strip SHIFT test's Python twin (4.3.50, the patch finder study of 2026-11-19).

The test itself runs in the helper (``native/chartread_helper/chromiq_shift.c``),
on every strip the instrument's patch finder accepted, after the colour check
and before the strip is kept. This module computes exactly the same numbers, so
the suite can check the C file against it (``tests/test_strip_shift_c.py``) and
run the regression set of real strips without building anything. Nothing in the
app calls it.

What it decides: whether the first (or last) two or three readings of a strip
fit "moved by one patch, with the white paper in front" clearly better than
the colours they were filed under, or whether the first (or last) reading is
the white paper itself where a colour far from it was expected. That is what happens when ArgyllCMS's strip
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
#: k = 1, the paper's fingerprint (CQS_P_*): the end reading as read is
#: paper-like while it misses its own expected colour by P_D or more.
P_L = 85.0
P_C = 12.0
P_D = 50.0
#: A strip that fits nothing (worst patch >= W, the colour check's WERR_TH):
#: s_3 must reach T3_W, and k = 1 is not judged (CQS_W, CQS_T3_W).
W = 95.0
T3_W = 20.0
#: A finding stands only if the strip fits the explanation within FMAX, and
#: no other row of the chart fits the reading better (CQS_FMAX).
FMAX = 60.0

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
    chroma: float = 0.0
    pd: float = 0.0
    werror: float = 0.0
    fit: float = 0.0
    other: float = -1.0
    guarded: bool = False


def other_rows_best(read: Sequence[Sequence[float]],
                    rows: "Sequence[Sequence[Sequence[float]]]") -> float:
    """The best mean CIE76 of *read* (Y-normalised per row, as the helper's
    colour check) against any of *rows* (the chart's OTHER rows' expected
    XYZ), both ways round; -1 when there is none."""
    best = -1.0
    for exp in rows:
        if len(exp) != len(read):
            continue
        se = sum(e[1] for e in exp)
        for rr in (list(read), list(read)[::-1]):
            sr = sum(r[1] for r in rr)
            if not (sr > 1e-6) or not (se > 1e-6):
                continue
            yn = se / sr
            m = sum(_de(_lab(r, yn), _lab(e)) for r, e in zip(rr, exp)) / len(exp)
            if best < 0.0 or m < best:
                best = m
    return best


def shift_test(read: Sequence[Sequence[float]], expected: Sequence[Sequence[float]],
               paper: Sequence[float], other_best: float = -1.0) -> ShiftResult:
    """*read*, *expected*: XYZ (0..100) per patch in row order; *paper*: the
    expected XYZ of the chart's paper (its brightest expected patch);
    *other_best*: `other_rows_best` of the reading (negative: not known)."""
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
    res.werror = max(_de(a, b) for a, b in zip(lr, le))
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
                ok = (s >= (T3_W if res.werror >= W else T3) if kk == 3
                      else (s >= T2 and s >= F2 * dd))
                if ok and (not res.flagged or s > res.score):
                    res.flagged, res.end, res.k, res.score = True, e, kk, s
    for e in (0, 1):
        if res.flagged or res.werror >= W:
            break
        ix = 0 if e == 0 else n - 1
        raw = _lab(read[ix])
        c = math.hypot(raw[1], raw[2])
        dp = _de(lr[ix], le[ix])      # the reading against its own colour
        if raw[0] >= P_L and c <= P_C and dp >= P_D:
            res.flagged, res.end, res.k, res.score = True, e, 1, raw[0]
            res.chroma, res.pd = c, dp
    res.other = other_best
    if res.flagged:
        e0, k0 = res.end, res.k
        whole = rest = 0.0
        nr = 0
        for i in range(n):
            ix = i if e0 == 0 else n - 1 - i
            sh = lp if i == 0 else le[ix - 1 if e0 == 0 else ix + 1]
            whole += _de(lr[ix], sh)
            if i >= k0:
                rest += _de(lr[ix], le[ix])
                nr += 1
        whole /= n
        rest = rest / nr if nr else 1e9
        res.fit = min(rest, whole)
        if res.fit > FMAX or (other_best >= 0.0 and other_best < res.fit):
            res.flagged, res.guarded = False, True
    return res
