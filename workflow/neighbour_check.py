"""The neighbour check: a patch whose reading does not fit the patches
nearest to it in colour (#182, beta 11).

**The ruling.** Knut, #182 5983470377, answer 5 (*"Build the neighbour check
for profiling charts?"* "Yes"), approving section C of the beta 10 analysis
(``2026-10-04_beta10/knut_analysis/ANALYSIS.md``; his own idea, 5982600086,
in its robust form). The analysis measured it on his real charts and
recommended it for charts with ESTIMATED expected colours, buffer 10; it is
not used on verification measurements (their limit of 10 already does the
work) nor on calibration charts (never measured, and a ramp chart has its
nearest colours in its own strip).

**The rule.** For each patch with a reading:

1. its comparison patches are up to :data:`MAX_COMPARED` (4) other patches
   that have a reading, were read in a DIFFERENT strip (one strip is one pass
   of the reader: a smudge or a slipped strip moves several patches of one
   strip alike) and whose EXPECTED colours lie within :data:`RADIUS_DE`
   (ΔE*ab 15) of its own, the nearest first;
2. with fewer than :data:`MIN_COMPARED` (3) of them it is not judged at all:
   a patch is never suspected for lack of comparisons;
3. for each comparison patch b, the excess is how much further apart the two
   READINGS are than the two EXPECTED colours:
   ``|meas_a - meas_b| - |exp_a - exp_b|`` (ΔE*ab, L*a*b* as the engine
   computes it, D50);
4. when the MEDIAN excess is over :data:`BUFFER_DE` (ΔE 10), the patch is a
   suspected misread.

Estimated expected colours are rough, but they are rough in the same way for
colours that lie close together, so two patches expected close together are
read close together on any printer; a reading that lands far from all of its
colour neighbours is more likely the reader's fault than the printer's. The
median is what keeps one misread neighbour from making its partners suspect.

Measured on the real profiling sheets of the analysis (Knut's HP laser 1944,
his run1 648 and run4 324, an Epson P300 924, a Canon Pro300 1168, his
scanner chart 315): 35 suspects at buffer 10 of 5,323 patches (0.7 %), 28 of
them on the wide-gamut Canon; none at buffer 15. Against injected misreads it
caught 43 % of smudges, 77 % of single glitches and every out-of-step or
wrong-strip read, most of which no limit can see because they land in the
middle of the colour space.

**When.** The check is a late one: while a chart is still being read most
patches have too few comparisons, so it is judged again after every strip
(and every patch, patch by patch) and when a measurement is opened from
disk. :meth:`NeighbourCheck.evaluate` judges every patch afresh from the
readings on hand.

Pure logic: no Qt, numpy only.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: A comparison patch's EXPECTED colour lies within this of the patch's own.
RADIUS_DE = 15.0
#: At most this many comparison patches, the nearest by expected colour.
MAX_COMPARED = 4
#: Fewer than this, and the patch is not judged.
MIN_COMPARED = 3
#: The median excess must be MORE than this for a suspect.
BUFFER_DE = 10.0

#: ArgyllCMS's icmD50, the white the engine's L*a*b* is computed against
#: (``workflow.measurement_report._engine_lab``).
_ICM_D50 = (0.9642, 1.0, 0.8249)

#: Rows judged at once: a 4,000-patch chart is judged in blocks of this many,
#: so no distance matrix larger than 512 x N is ever held.
_BLOCK = 512


def engine_lab(xyz100) -> "tuple[float, float, float]":
    """L*a*b* as the engine computes it: XYZ (0..100) / 100 against icmD50."""
    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else (
            (24389.0 / 27.0 * t + 16.0) / 116.0)
    fx, fy, fz = (f(float(v) / 100.0 / w) for v, w in zip(xyz100[:3], _ICM_D50))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


@dataclass(frozen=True)
class NeighbourFinding:
    """How one patch fared against its comparison patches.

    *compared* are their locations, nearest first. *excess* is the median of
    the pairs' excess, *expected_de* the median distance between its expected
    colour and theirs, *measured_de* the median distance between its reading
    and theirs (all ΔE*ab). *suspect* is the verdict: enough comparisons and
    the median excess over the buffer."""
    loc: str
    compared: tuple = ()
    excess: float = 0.0
    expected_de: float = 0.0
    measured_de: float = 0.0
    suspect: bool = False

    @property
    def checked(self) -> bool:
        return len(self.compared) >= MIN_COMPARED


class NeighbourCheck:
    """The readings of one measurement and their verdicts.

    The caller tells it every reading (:meth:`set_reading`, the latest wins)
    and asks :meth:`evaluate` once per batch; the findings stay until the
    next evaluation. :meth:`reset` starts afresh (a new chart, a fresh read).
    """

    def __init__(self, radius: float = RADIUS_DE, k: int = MAX_COMPARED,
                 min_compared: int = MIN_COMPARED,
                 buffer: float = BUFFER_DE) -> None:
        self.radius = float(radius)
        self.k = int(k)
        self.min_compared = int(min_compared)
        self.buffer = float(buffer)
        self.reset()

    def reset(self) -> None:
        #: loc -> (expected Lab, measured Lab, strip), in the order first read.
        self._rows: "dict[str, tuple]" = {}
        self._findings: "dict[str, NeighbourFinding]" = {}
        self._dirty = False

    def __len__(self) -> int:
        return len(self._rows)

    def set_reading(self, loc: str, exp_xyz100, meas_xyz100,
                    strip: "str | None") -> None:
        """Remember the latest reading of *loc* (XYZ 0..100, D50), read in
        *strip* (None or "": unknown, which never compares with anything)."""
        self.set_reading_lab(loc, engine_lab(exp_xyz100),
                             engine_lab(meas_xyz100), strip)

    def set_reading_lab(self, loc: str, exp_lab, meas_lab,
                        strip: "str | None") -> None:
        """:meth:`set_reading` for colours already in the engine's L*a*b*."""
        self._rows[str(loc)] = (tuple(float(v) for v in exp_lab[:3]),
                                tuple(float(v) for v in meas_lab[:3]),
                                str(strip or ""))
        self._dirty = True

    def forget(self, loc: str) -> None:
        """*loc* has no reading any more (set aside, or removed)."""
        if self._rows.pop(str(loc), None) is not None:
            self._dirty = True

    # ---- the verdicts ------------------------------------------------------
    def evaluate(self) -> "dict[str, NeighbourFinding]":
        """Judge every patch afresh; ``{loc: finding}`` for every patch whose
        suspect verdict CHANGED since the last evaluation."""
        if not self._dirty and self._findings:
            return {}
        locs = list(self._rows)
        before = self._findings
        self._findings = {}
        self._dirty = False
        n = len(locs)
        if n == 0:
            return {loc: NeighbourFinding(loc) for loc, f in before.items()
                    if f.suspect}
        exp = np.array([self._rows[x][0] for x in locs], dtype=float)
        meas = np.array([self._rows[x][1] for x in locs], dtype=float)
        strip_names = [self._rows[x][2] for x in locs]
        codes = {s: i for i, s in enumerate(sorted(set(strip_names)))}
        st = np.array([codes[s] for s in strip_names])
        known = np.array([bool(s) for s in strip_names])
        k = max(1, min(self.k, n - 1)) if n > 1 else 1
        for lo in range(0, n, _BLOCK):
            hi = min(n, lo + _BLOCK)
            d = np.linalg.norm(exp[lo:hi, None, :] - exp[None, :, :], axis=2)
            bad = (st[lo:hi, None] == st[None, :]) | ~known[None, :] \
                | ~known[lo:hi, None] | (d > self.radius)
            d[bad] = np.inf
            if n > k:
                idx = np.argpartition(d, k - 1, axis=1)[:, :k]
            else:
                idx = np.tile(np.arange(n), (hi - lo, 1))
            dk = np.take_along_axis(d, idx, axis=1)
            order = np.argsort(dk, axis=1, kind="stable")
            idx = np.take_along_axis(idx, order, axis=1)
            dk = np.take_along_axis(dk, order, axis=1)
            for r in range(hi - lo):
                i = lo + r
                ok = np.isfinite(dk[r])
                nb = idx[r][ok]
                if nb.size == 0:
                    self._findings[locs[i]] = NeighbourFinding(locs[i])
                    continue
                de = dk[r][ok]
                dm = np.linalg.norm(meas[nb] - meas[i], axis=1)
                ex = dm - de
                checked = nb.size >= self.min_compared
                med = float(np.median(ex))
                self._findings[locs[i]] = NeighbourFinding(
                    loc=locs[i],
                    compared=tuple(locs[j] for j in nb),
                    excess=med,
                    expected_de=float(np.median(de)),
                    measured_de=float(np.median(dm)),
                    suspect=bool(checked and med > self.buffer))
        changed = {}
        for loc in set(before) | set(self._findings):
            was = before.get(loc)
            now = self._findings.get(loc, NeighbourFinding(loc))
            if bool(was and was.suspect) != now.suspect:
                changed[loc] = now
        return changed

    def finding(self, loc: str) -> "NeighbourFinding | None":
        """The last evaluation's finding for *loc* (None: no reading then)."""
        return self._findings.get(str(loc))

    def is_suspect(self, loc: str) -> bool:
        f = self._findings.get(str(loc))
        return bool(f is not None and f.suspect)

    def suspects(self) -> "list[str]":
        """The suspected patches of the last evaluation, in reading order."""
        return [loc for loc in self._rows
                if self._findings.get(loc) is not None
                and self._findings[loc].suspect]

    def checked_count(self) -> int:
        """How many patches had enough comparisons to be judged."""
        return sum(1 for f in self._findings.values() if f.checked)
