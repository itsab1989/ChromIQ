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
#: The user's buffer (Preferences ▸ Measurement, Knut #182 5983725218:
#: "a defined input box ... so that the threshold for when this check
#: triggers a red highlighted patch can be modified by user"), and its range.
BUFFER_KEY = "patch_neighbour_buffer_de"
BUFFER_MIN_DE = 1.0
BUFFER_MAX_DE = 50.0


def buffer_from(settings) -> float:
    """The user's buffer, or the default, kept within its range."""
    try:
        v = float(settings.get(BUFFER_KEY, BUFFER_DE))
    except (TypeError, ValueError, AttributeError):
        return BUFFER_DE
    if v != v:                      # NaN
        return BUFFER_DE
    return min(BUFFER_MAX_DE, max(BUFFER_MIN_DE, v))

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
        #: Readings changed since the last evaluation (None: judge them all),
        #: and the expected colours of readings forgotten or moved since.
        self._changed: "set[str] | None" = None
        self._gone: "list[tuple]" = []

    def set_buffer(self, buffer: float) -> None:
        """Take the user's buffer (Preferences ▸ Measurement); a new one
        judges every patch again at the next evaluation."""
        buffer = float(buffer)
        if buffer != self.buffer:
            self.buffer = buffer
            self._changed = None

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
        loc = str(loc)
        row = (tuple(float(v) for v in exp_lab[:3]),
               tuple(float(v) for v in meas_lab[:3]), str(strip or ""))
        old = self._rows.get(loc)
        if old == row:
            return
        self._rows[loc] = row
        self._touch(loc, old)

    def forget(self, loc: str) -> None:
        """*loc* has no reading any more (set aside, or removed)."""
        old = self._rows.pop(str(loc), None)
        if old is not None:
            self._touch(str(loc), old)

    def _touch(self, loc: str, old) -> None:
        """Note what the next evaluation must judge again: *loc*, and the
        patches near its old expected colour when that has gone or moved."""
        if self._changed is None:
            return                    # everything is judged anyway
        self._changed.add(loc)
        if old is not None:
            new = self._rows.get(loc)
            if new is None or new[0] != old[0]:
                self._gone.append(old[0])

    # ---- the verdicts ------------------------------------------------------
    def evaluate(self) -> "dict[str, NeighbourFinding]":
        """Judge again every patch a new reading can have changed (all of
        them the first time); ``{loc: finding}`` for every patch whose
        suspect verdict CHANGED since the last evaluation.

        A patch's finding depends only on its own reading and on those of the
        patches expected within :data:`RADIUS_DE` of it, so after a strip only
        the patches near in colour to what was read are judged again; the
        result is the same as judging them all."""
        locs = list(self._rows)
        n = len(locs)
        before = {loc: f.suspect for loc, f in self._findings.items()}
        changed_locs = self._changed
        gone = self._gone
        self._changed, self._gone = set(), []
        for loc in [x for x in self._findings if x not in self._rows]:
            del self._findings[loc]
        if changed_locs is not None and not changed_locs:
            return {}
        exp = (np.array([self._rows[x][0] for x in locs], dtype=float)
               if n else np.zeros((0, 3)))
        if changed_locs is None:
            todo = np.arange(n)
            self._findings = {}
        else:
            centres = [self._rows[x][0] for x in changed_locs if x in self._rows]
            centres += gone
            if n and centres:
                c = np.array(centres, dtype=float)
                near = np.zeros(n, dtype=bool)
                for lo in range(0, len(c), _BLOCK):
                    d = np.linalg.norm(exp[None, :, :] - c[lo:lo + _BLOCK, None, :],
                                       axis=2)
                    near |= (d <= self.radius).any(axis=0)
                todo = np.nonzero(near)[0]
            else:
                todo = np.arange(0)
        if n:
            self._judge_rows(locs, exp, todo)
        changed = {}
        for loc in set(before) | {locs[i] for i in todo}:
            now = self._findings.get(loc, NeighbourFinding(loc))
            if before.get(loc, False) != now.suspect:
                changed[loc] = now
        return changed

    def _judge_rows(self, locs, exp, todo) -> None:
        n = len(locs)
        meas = np.array([self._rows[x][1] for x in locs], dtype=float)
        strip_names = [self._rows[x][2] for x in locs]
        codes = {s: i for i, s in enumerate(sorted(set(strip_names)))}
        st = np.array([codes[s] for s in strip_names])
        known = np.array([bool(s) for s in strip_names])
        k = max(1, min(self.k, n - 1)) if n > 1 else 1
        for lo in range(0, len(todo), _BLOCK):
            rows = todo[lo:lo + _BLOCK]
            d = np.linalg.norm(exp[rows, None, :] - exp[None, :, :], axis=2)
            bad = (st[rows, None] == st[None, :]) | ~known[None, :] \
                | ~known[rows, None] | (d > self.radius)
            d[bad] = np.inf
            # Equal distances go to the patch first read, whichever rows are
            # judged together (a nudge far below any colour difference).
            d += np.arange(n)[None, :] * 1e-9
            if n > k:
                idx = np.argpartition(d, k - 1, axis=1)[:, :k]
            else:
                idx = np.tile(np.arange(n), (len(rows), 1))
            dk = np.take_along_axis(d, idx, axis=1)
            order = np.argsort(dk, axis=1, kind="stable")
            idx = np.take_along_axis(idx, order, axis=1)
            dk = np.take_along_axis(dk, order, axis=1)
            for r, i in enumerate(rows):
                ok = np.isfinite(dk[r])
                nb = idx[r][ok]
                if nb.size == 0:
                    self._findings[locs[i]] = NeighbourFinding(locs[i])
                    continue
                de = np.linalg.norm(exp[nb] - exp[i], axis=1)
                dm = np.linalg.norm(meas[nb] - meas[i], axis=1)
                ex = dm - de
                med = float(np.median(ex))
                self._findings[locs[i]] = NeighbourFinding(
                    loc=locs[i],
                    compared=tuple(locs[j] for j in nb),
                    excess=med,
                    expected_de=float(np.median(de)),
                    measured_de=float(np.median(dm)),
                    suspect=bool(nb.size >= self.min_compared
                                 and med > self.buffer))

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
