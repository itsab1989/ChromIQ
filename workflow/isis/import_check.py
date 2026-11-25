"""Did an i1iSis measurement of a chart that was NOT randomised come from the
right way round? (item 63, the i1iSis chart Beta.)

WHY THIS MODULE. i1Profiler copies the device values of its test chart into
the measurement, so they prove which test chart was used and never how the
sheet went through the instrument. On a randomised chart the colours answer
that (`workflow.turned_colour_check.judge`). A chart that is not randomised
has regular colours (ramps, grids, a sorted list), and there that judge stops
at "cannot tell" before it compares anything, because neighbouring patches
look alike. Most wrong ways of feeding such a sheet can still be told apart:
a ramp read from the other end runs the other way, a grid read one column off
jumps by a whole step of another channel.

WHAT IS COMPARED. Two things, and neither of them depends on how the patches
are ordered on the sheet:

* THE WHOLE: the rank agreement of expected and measured L*, a* and b*, over
  the channels the chart really spreads. Right readings score the same
  whatever Randomise says (0.82 to 0.94 on real sets, see
  `turned_colour_check`);
* EACH WRONG WAY BY ITSELF: the readings shifted by one, two or three columns
  or rows, mirrored either way, turned half a turn, transposed. Each is
  compared with the right way ON THE SAME READINGS, by how far the readings
  are from the colours a plausible printer would give: L* any rising function
  of the expected L* (so a ramp read backwards cannot be explained away), a*
  and b* one common gain and a small hue turn.

* every wrong way clearly worse: the readings sit on their own patches
  (:data:`RIGHT`);
* one of them clearly better, or a whole that does not follow the chart at
  all: refused (:data:`WRONG`);
* otherwise nobody can tell from the values (:data:`CANNOT`): the person is
  asked, never refused and never filed in silence.

Nothing is paired by colour: the order file pairs.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from workflow.turned_colour_check import (
    ACCEPT_FROM, DISAGREE_BELOW, DISTINCT_DE, MIN_CHANNEL_SPREAD,
    MIN_DISTINCT, MIN_PATCHES, _cell, _distinct, _spearman)

RIGHT, WRONG, CANNOT = "right", "wrong", "cannot"

#: The right way's misfit over a wrong way's, on the same readings. At most
#: CLEARLY_RIGHT for every wrong way: told apart. At least CLEARLY_WRONG for
#: one: that way fits and the right one does not.
CLEARLY_RIGHT = 0.85
CLEARLY_WRONG = 2.00
#: How many whole columns / rows off are asked about.
SHIFTS = (1, 2, 3)


@dataclass(frozen=True)
class Verdict:
    verdict: str
    why: str = ""              # "few", "similar", "whole", "way", ""
    detail: str = ""


def wrong_ways(n: int, rows: int, cols: int) -> "dict[str, np.ndarray]":
    """name -> p: reading j would really be of entry p[j] (-1: no patch)."""
    idx = np.arange(n)
    r, c = idx % rows, idx // rows
    out = {}
    for k in SHIFTS:
        out[f"columns+{k}"] = _cell(rows, cols, n, r, c + k)
        out[f"columns-{k}"] = _cell(rows, cols, n, r, c - k)
        out[f"rows+{k}"] = _cell(rows, cols, n, r + k, c)
        out[f"rows-{k}"] = _cell(rows, cols, n, r - k, c)
        out[f"entries+{k}"] = np.where(idx + k < n, idx + k, -1)
        out[f"entries-{k}"] = np.where(idx - k >= 0, idx - k, -1)
    out["mirrored-columns"] = _cell(rows, cols, n, r, cols - 1 - c)
    out["mirrored-rows"] = _cell(rows, cols, n, rows - 1 - r, c)
    out["half-turn"] = _cell(rows, cols, n, rows - 1 - r, cols - 1 - c)
    out["last-first"] = n - 1 - idx
    if n == rows * cols:
        out["rows-and-columns-swapped"] = (idx % cols) * rows + idx // cols
    return {k: v for k, v in out.items()
            if (v >= 0).sum() >= max(6, n // 4) and float((v == idx).mean()) < 0.5}


def _rising(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """The best rising step function of *x* to *y* (pool adjacent
    violators), at each x; equal x share one value."""
    o = np.lexsort((y, x))
    xs, ys = x[o], y[o]
    # equal x first become one point
    vals, wts, ends = [], [], []
    i, n = 0, len(xs)
    while i < n:
        k = i
        while k + 1 < n and xs[k + 1] - xs[i] < 1e-9:
            k += 1
        vals.append(float(ys[i:k + 1].mean()))
        wts.append(k + 1 - i)
        ends.append(k + 1)
        while len(vals) > 1 and vals[-2] >= vals[-1]:
            w = wts[-2] + wts[-1]
            v = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / w
            e = ends[-1]
            del vals[-2:], wts[-2:], ends[-2:]
            vals.append(v)
            wts.append(w)
            ends.append(e)
        i = k + 1
    fit = np.empty(n)
    s = 0
    for v, e in zip(vals, ends):
        fit[s:e] = v
        s = e
    out = np.empty(n)
    out[o] = fit
    return out


def _misfit(E: np.ndarray, M: np.ndarray) -> float:
    """How far readings *M* are from what a plausible printer makes of the
    expected colours *E* (root mean square of L*, a*, b* together)."""
    l_res = M[:, 0] - _rising(E[:, 0], M[:, 0])
    e = E[:, 1] + 1j * E[:, 2]
    m = M[:, 1] + 1j * M[:, 2]
    e, m = e - e.mean(), m - m.mean()
    p = float((np.abs(e) ** 2).mean())
    k = complex((np.conj(e) * m).mean() / p) if p > 1e-9 else 0j
    ang = float(np.clip(np.angle(k), -0.45, 0.45))
    gain = float(np.clip(abs(k) * np.cos(np.angle(k) - ang), 0.3, 1.4))
    ab = m - gain * np.exp(1j * ang) * e
    return float(np.sqrt((l_res ** 2 + np.abs(ab) ** 2).mean()))


def compare(E, M, rows: int, cols: int) -> Verdict:
    """Judge readings *M* (L*a*b*, entry order) against expected *E*."""
    E, M = np.asarray(E, float), np.asarray(M, float)
    n = len(E)
    if n != len(M) or n == 0 or not (np.all(np.isfinite(E))
                                     and np.all(np.isfinite(M))):
        return Verdict(CANNOT, "similar", "no colours")
    if n < MIN_PATCHES:
        return Verdict(CANNOT, "few", f"{n} patches")
    spread = E.std(axis=0)
    channels = [c for c in range(3) if spread[c] >= MIN_CHANNEL_SPREAD]
    enough = _distinct(E, DISTINCT_DE) >= MIN_DISTINCT
    if not channels or not enough:
        return Verdict(CANNOT, "similar", f"spread {np.round(spread, 1).tolist()}")
    ranks = [_spearman(E[:, c], M[:, c]) for c in channels]
    whole = min(ranks)
    if not all(np.isfinite(v) for v in ranks):
        return Verdict(CANNOT, "similar", "a constant channel")
    # The MIDDLE channel refuses, not the lowest: one channel of 24 right
    # readings of a chart that hardly spreads it scored 0.399.
    if float(np.median(ranks)) < DISAGREE_BELOW:
        return Verdict(WRONG, "whole", f"rank agreement {whole:.3f}")
    worst, name = 0.0, ""
    for k, p in wrong_ways(n, rows, cols).items():
        keep = p >= 0
        right = _misfit(E[keep], M[keep])
        other = _misfit(E[p[keep]], M[keep])
        ratio = right / other if other > 1e-9 else np.inf
        if ratio > worst:
            worst, name = ratio, k
    detail = f"rank agreement {whole:.3f}; closest {name} {worst:.2f}"
    if worst >= CLEARLY_WRONG:
        return Verdict(WRONG, "way", detail)
    if worst > CLEARLY_RIGHT:
        return Verdict(CANNOT, "way", detail)
    if whole < ACCEPT_FROM:
        return Verdict(CANNOT, "whole", detail)
    return Verdict(RIGHT, "", detail)


def _row_of_equals(E: np.ndarray, rows: int, row: int) -> bool:
    """True when a third or more of the neighbours along i1Profiler's *row*
    are about the same colour: such a row (white patches filling it up, say)
    fits its neighbours as well as itself, also when it was read rightly."""
    e = E[np.arange(len(E)) % rows == row]
    if len(e) < 2:
        return True
    d = np.linalg.norm(e[1:] - e[:-1], axis=1)
    return float((d < DISTINCT_DE).mean()) >= 1 / 3


def judge_rows(measured, at, order, chart_ti2) -> Verdict:
    """Judge the parsed measurement *measured*, whose row i is i1Profiler's
    entry ``at[i]`` of *order*: first by the judge of randomised charts, and
    where that one cannot tell by :func:`compare`."""
    from pathlib import Path

    from workflow.turned_colour_check import _expected_lab, measured_lab
    n, pos = len(order.sample_ids), np.argsort(np.asarray(at))
    xyz = np.asarray(measured.xyz, float)
    rgb = np.asarray(measured.rgb, float)
    if len(xyz) != n or len(rgb) != n or not np.all(np.isfinite(xyz)) \
            or float(xyz[:, 1].max()) <= 0:
        return Verdict(CANNOT, "no-colours")
    E = _expected_lab(rgb[pos], Path(chart_ti2), order)
    if E is None or len(E) != n:
        return Verdict(CANNOT, "no-colours")
    M = measured_lab(xyz[pos])
    return decide(E, M, int(order.rows), int(order.columns))


def decide(E: np.ndarray, M: np.ndarray, rows: int, cols: int) -> Verdict:
    """The judge of randomised charts first, then :func:`compare` where that
    one cannot tell (or only tripped over a row of equal patches)."""
    from workflow.turned_colour_check import AGREE, DISAGREE, judge
    first = judge(E, M, rows, cols)
    if first.verdict == AGREE:
        return Verdict(RIGHT, "", first.log_text())
    if first.verdict == DISAGREE and not (
            first.why == "strip-wrong"
            and _row_of_equals(E, rows, first.strip)):
        return Verdict(WRONG, first.why, first.log_text())
    v = compare(E, M, rows, cols)
    return Verdict(v.verdict, v.why, f"{first.log_text()}; {v.detail}")
