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
2. with fewer than :data:`MIN_COMPARED` (2 since beta 15, was 3) of them it
   is not judged at all: a patch is never suspected for lack of comparisons;
3. for each comparison patch b, the excess is how much further apart the two
   READINGS are than the two EXPECTED colours:
   ``|meas_a - meas_b| - |exp_a - exp_b|`` (ΔE*ab, L*a*b* as the engine
   computes it, D50);
4. when the MEDIAN excess is over the buffer (:data:`BUFFER_DE`, ΔE 10, on a
   chart with estimated colours; :data:`BUFFER_ACCURATE_DE`, ΔE 5, on a chart
   made with a pre-conditioning profile, beta 15),
5. AND the patch is the one that is off (beta 15, "B2+"): the median of
   ``|meas_a - exp_a| - |meas_b - exp_b|`` is above 0, so it is further from
   its own expected colour than its comparison patches are from theirs,
   the patch is a suspected misread.

**B2+ (beta 15, Knut #182 6059912998, "Use the suggested B2+ method"),**
measured in ``2026-10-08_neighbour_methods/ANALYSIS.md`` on 3,492 simulated
measurements: two comparisons are enough (small charts: 34 % of patches
checked instead of 17 %, gross misreads caught 34 % instead of 19 %), and
condition 5 keeps a HEALTHY patch beside a nozzle line or a drying ink from
turning red with the faulty ones (38 and 81 healthy reds per measurement
before, 3.5 and 5.3 after). Exactly two, never more, was worse; up to four
stays.

Estimated expected colours are rough, but they are rough in the same way for
colours that lie close together, so two patches expected close together are
read close together on any printer; a reading that lands far from all of its
colour neighbours is more likely the reader's fault than the printer's. The
median is what keeps one misread neighbour from making its partners suspect.

Measured on the real profiling sheets of the analysis (Knut's HP laser 1944,
his run1 648 and run4 324, an Epson P300 924, a Canon Pro300 1168, his
scanner chart 315): beta 11's rule found 35 suspects at buffer 10 of 5,323
patches (0.7 %), 28 of them on the wide-gamut Canon; none at buffer 15. B2+,
re-measured for beta 15 on the same sheets (`tests/test_neighbour_check.py`
``REAL``): 24 at buffer 10, 18 of them on the Canon, none at 15. Against injected misreads it
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
#: Fewer than this, and the patch is not judged (B2+, beta 15: was 3).
MIN_COMPARED = 2
#: The median excess must be MORE than this for a suspect, on a chart with
#: estimated colours (most charts).
BUFFER_DE = 10.0
#: ... and on a chart made with a pre-conditioning profile, whose expected
#: colours are close to the print (Knut #182 6059912998, answer 6: "a
#: separate variable for charts made from a pre-conditioning profile, with 5
#: as default"). The analysis: 0 to 3 false reds there at 5.
BUFFER_ACCURATE_DE = 5.0
BUFFER_ACCURATE_KEY = "patch_neighbour_buffer_de_accurate"
#: The neighbour check's own switch (k44, Knut #182 6060201176), on by
#: default. Off, it judges nothing: no patch is red for it, and its outlines
#: come back as they were when it is switched on again.
SWITCH_KEY = "patch_neighbour_check"
#: The user's buffer (Preferences ▸ Measurement, Knut #182 5983725218:
#: "a defined input box ... so that the threshold for when this check
#: triggers a red highlighted patch can be modified by user"), and its range.
BUFFER_KEY = "patch_neighbour_buffer_de"
BUFFER_MIN_DE = 1.0
BUFFER_MAX_DE = 50.0


def buffer_from(settings, accurate: bool = False) -> float:
    """The user's buffer, or the default, kept within its range: the one for
    a chart made with a pre-conditioning profile when *accurate* (the chart's
    file says ACCURATE_EXPECTED_VALUES), else the one for other charts."""
    key, default = ((BUFFER_ACCURATE_KEY, BUFFER_ACCURATE_DE) if accurate
                    else (BUFFER_KEY, BUFFER_DE))
    try:
        v = float(settings.get(key, default))
    except (TypeError, ValueError, AttributeError):
        return default
    if v != v:                      # NaN
        return default
    return min(BUFFER_MAX_DE, max(BUFFER_MIN_DE, v))


def enabled_from(settings) -> bool:
    """Whether the neighbour check is switched on (Preferences ▸
    Measurement, k44); on when unset or unreadable."""
    try:
        return bool(settings.get(SWITCH_KEY, True))
    except Exception:      # noqa: BLE001
        return True

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
    and theirs, *further* the median of how much further its reading is from
    its own expected colour than theirs are from theirs (all ΔE*ab).
    *suspect* is the verdict: enough comparisons, the median excess over the
    buffer, and *further* above 0 (B2+)."""
    loc: str
    compared: tuple = ()
    excess: float = 0.0
    expected_de: float = 0.0
    measured_de: float = 0.0
    suspect: bool = False
    further: float = 0.0

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
        #: Readings changed since the last evaluation (None: judge them all);
        #: of those, the ones new or moved (*arrived*) and the ones forgotten
        #: or moved (*left*).
        self._changed: "set[str] | None" = None
        self._arrived: "set[str]" = set()
        self._left: "set[str]" = set()
        #: loc -> its comparison patches (locs, nearest first), and loc ->
        #: the patches that compare with it.
        self._lists: "dict[str, tuple]" = {}
        self._users: "dict[str, set]" = {}

    def set_buffer(self, buffer: float) -> None:
        """Take the user's buffer (Preferences ▸ Measurement); a new one
        judges every patch again at the next evaluation."""
        buffer = float(buffer)
        if buffer != self.buffer:
            self.buffer = buffer
            self._changed = None
            self._arrived, self._left = set(), set()

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
        """Note what the next evaluation must judge again: *loc*; whether its
        place among the comparisons changed (new, gone, or moved to another
        expected colour or strip) or only its reading did."""
        if self._changed is None:
            return                    # everything is judged anyway
        self._changed.add(loc)
        new = self._rows.get(loc)
        if old is None:
            self._arrived.add(loc)
        elif new is None or new[0] != old[0] or new[2] != old[2]:
            self._left.add(loc)
            if new is not None:
                self._arrived.add(loc)

    # ---- the verdicts ------------------------------------------------------
    def evaluate(self) -> "dict[str, NeighbourFinding]":
        """Judge again every patch a new reading can have changed (all of
        them the first time); ``{loc: finding}`` for every patch whose
        suspect verdict CHANGED since the last evaluation.

        A patch's comparison patches depend only on the expected colours and
        strips of the patches read, so they are kept between evaluations and
        changed only by what changed (review of beta 11: finding them afresh
        for every patch near a new strip cost a distance to every reading per
        patch, 0.1 s a strip at the end of a 4,096-patch chart, growing with
        the square of its size):

        * a patch read for the first time, or whose expected colour or strip
          changed, and every patch that compared with one that has gone, has
          its comparisons found afresh among all the readings;
        * every other patch within :data:`RADIUS_DE` of a new arrival takes
          the arrival among its comparisons where it is nearer than one of
          them (the nearest :data:`MAX_COMPARED` of the old set and the
          arrivals are the nearest of the new set);
        * the medians are worked out again for those, and for every patch
          whose own reading, or one of whose comparisons' readings, changed.

        The result is the same as judging them all
        (tests/test_neighbour_check.py)."""
        locs = list(self._rows)
        n = len(locs)
        before = {loc: f.suspect for loc, f in self._findings.items()}
        changed_locs = self._changed
        arrived, left = self._arrived, self._left
        self._changed, self._arrived, self._left = set(), set(), set()
        for loc in [x for x in self._findings if x not in self._rows]:
            del self._findings[loc]
        if changed_locs is not None and not changed_locs:
            return {}
        pos = {loc: i for i, loc in enumerate(locs)}
        exp = (np.array([self._rows[x][0] for x in locs], dtype=float)
               if n else np.zeros((0, 3)))
        meas = (np.array([self._rows[x][1] for x in locs], dtype=float)
                if n else np.zeros((0, 3)))
        strip_names = [self._rows[x][2] for x in locs]
        codes = {s: i for i, s in enumerate(sorted(set(strip_names)))}
        st = np.array([codes[s] for s in strip_names], dtype=int)
        known = np.array([bool(s) for s in strip_names], dtype=bool)

        if changed_locs is None:
            fresh = set(range(n))
            merge: "set[int]" = set()
            self._lists, self._users = {}, {}
        else:
            # Patches that compared with a reading that has gone or moved.
            fresh = {pos[x] for x in arrived if x in pos}
            for gone in left:
                for user in self._users.pop(gone, set()):
                    if user in pos:
                        fresh.add(pos[user])
            for x in left:
                self._set_list(x, ())
            # Patches near an arrival, which may now compare with it.
            merge = set()
            new_idx = np.array(sorted(pos[x] for x in arrived if x in pos),
                               dtype=int)
            if n and new_idx.size:
                c = exp[new_idx]
                for lo in range(0, n, _BLOCK):
                    d = np.linalg.norm(
                        exp[lo:lo + _BLOCK, None, :] - c[None, :, :], axis=2)
                    ok = self._valid(d, st[lo:lo + _BLOCK, None],
                                     st[new_idx][None, :],
                                     known[lo:lo + _BLOCK, None],
                                     known[new_idx][None, :])
                    merge.update((lo + np.nonzero(ok.any(axis=1))[0]).tolist())
            merge -= fresh
        if n and fresh:
            self._find_fresh(locs, exp, st, known, np.array(sorted(fresh)))
        if n and merge:
            self._merge_arrivals(locs, pos, exp, st, known, sorted(merge),
                                 sorted(pos[x] for x in arrived if x in pos))
        # The medians: every patch whose comparisons, or whose comparisons'
        # readings, or whose own reading changed.
        if changed_locs is None:
            todo = set(range(n))
        else:
            todo = set(fresh) | set(merge)
            for x in changed_locs:
                if x in pos:
                    todo.add(pos[x])
                    for user in self._users.get(x, ()):
                        if user in pos:
                            todo.add(pos[user])
        old = {locs[i]: self._findings.get(locs[i]) for i in todo}
        if n and todo:
            self._judge_rows(locs, pos, exp, meas, np.array(sorted(todo)))
        changed = {}
        for loc in set(before) | {locs[i] for i in todo}:
            now = self._findings.get(loc, NeighbourFinding(loc))
            if before.get(loc, False) != now.suspect:
                changed[loc] = now
        #: Every finding this evaluation changed in any way (its comparisons
        #: or its figures, not only its verdict): a suspect's card shows
        #: them (review of beta 11, :meth:`updated`).
        self._updated = {loc: self._findings[loc] for loc, f in old.items()
                         if loc in self._findings and self._findings[loc] != f}
        self._updated.update(changed)
        return changed

    def updated(self) -> "dict[str, NeighbourFinding]":
        """``{loc: finding}`` for every patch whose finding the last
        evaluation changed in any way, verdict or not."""
        return dict(getattr(self, "_updated", {}))

    def _set_list(self, loc: str, new: tuple) -> None:
        """*loc* now compares with *new* (locations, nearest first)."""
        for x in self._lists.get(loc, ()):
            users = self._users.get(x)
            if users is not None:
                users.discard(loc)
        if new:
            self._lists[loc] = tuple(new)
            for x in new:
                self._users.setdefault(x, set()).add(loc)
        else:
            self._lists.pop(loc, None)

    def _valid(self, d, st_a, st_b, known_a, known_b):
        """May a and b compare: both strips known, different, and their
        expected colours within the radius."""
        return (st_a != st_b) & known_a & known_b & (d <= self.radius)

    def _find_fresh(self, locs, exp, st, known, rows) -> None:
        """Find the comparisons of *rows* among all the readings."""
        n = len(locs)
        k = min(self.k, max(0, n - 1))
        nudge = np.arange(n) * 1e-9
        for lo in range(0, len(rows), _BLOCK):
            rr = rows[lo:lo + _BLOCK]
            if k <= 0:
                for i in rr:
                    self._set_list(locs[i], ())
                continue
            d = np.linalg.norm(exp[rr, None, :] - exp[None, :, :], axis=2)
            ok = self._valid(d, st[rr, None], st[None, :], known[rr, None],
                             known[None, :])
            d[~ok] = np.inf
            # Equal distances go to the patch first read, whichever rows are
            # judged together (a nudge far below any colour difference).
            d += nudge[None, :]
            idx = (np.argpartition(d, k - 1, axis=1)[:, :k] if n > k
                   else np.tile(np.arange(n), (len(rr), 1)))
            dk = np.take_along_axis(d, idx, axis=1)
            order = np.argsort(dk, axis=1, kind="stable")
            idx = np.take_along_axis(idx, order, axis=1)
            dk = np.take_along_axis(dk, order, axis=1)
            fin = np.isfinite(dk)
            for r, i in enumerate(rr):
                self._set_list(locs[i], tuple(locs[j] for j in idx[r][fin[r]]))

    def _merge_arrivals(self, locs, pos, exp, st, known, rows, new) -> None:
        """Let each of *rows* take the arrivals *new* (indices) among its
        comparisons where they are nearer than the ones it has."""
        new_set = set(int(j) for j in new)
        for i in rows:
            have = {pos[x] for x in self._lists.get(locs[i], ()) if x in pos}
            cand = np.array(sorted((have | new_set) - {i}), dtype=int)
            if not cand.size:
                continue
            d = np.linalg.norm(exp[cand] - exp[i], axis=1)
            ok = self._valid(d, st[i], st[cand], known[i], known[cand])
            cand, d = cand[ok], d[ok] + cand[ok] * 1e-9
            take = cand[np.argsort(d, kind="stable")[:self.k]]
            self._set_list(locs[i], tuple(locs[j] for j in take))

    def _judge_rows(self, locs, pos, exp, meas, rows) -> None:
        """Work out the medians of *rows* from their comparisons."""
        k = max(1, self.k)
        idx = np.full((len(rows), k), -1, dtype=int)
        for r, i in enumerate(rows):
            lst = [pos[x] for x in self._lists.get(locs[i], ()) if x in pos][:k]
            idx[r, :len(lst)] = lst
        ok = idx >= 0
        count = ok.sum(axis=1)
        safe = np.where(ok, idx, 0)
        de = np.linalg.norm(exp[safe] - exp[rows][:, None, :], axis=2)
        dm = np.linalg.norm(meas[safe] - meas[rows][:, None, :], axis=2)
        de[~ok] = np.nan
        dm[~ok] = np.nan
        # B2+: how far each reading is from its own expected colour
        off_own = np.linalg.norm(meas[rows] - exp[rows], axis=1)[:, None]
        off_nb = np.linalg.norm(meas[safe] - exp[safe], axis=2)
        fu = off_own - off_nb
        fu[~ok] = np.nan
        has = count > 0
        med_ex = np.zeros(len(rows))
        med_de = np.zeros(len(rows))
        med_dm = np.zeros(len(rows))
        med_fu = np.zeros(len(rows))
        if has.any():
            med_ex[has] = np.nanmedian((dm - de)[has], axis=1)
            med_de[has] = np.nanmedian(de[has], axis=1)
            med_dm[has] = np.nanmedian(dm[has], axis=1)
            med_fu[has] = np.nanmedian(fu[has], axis=1)
        suspect = (has & (count >= self.min_compared) & (med_ex > self.buffer)
                   & (med_fu > 0.0))
        for r, i in enumerate(rows):
            if not has[r]:
                self._findings[locs[i]] = NeighbourFinding(locs[i])
                continue
            self._findings[locs[i]] = NeighbourFinding(
                loc=locs[i],
                compared=tuple(locs[j] for j in idx[r][ok[r]]),
                excess=float(med_ex[r]),
                expected_de=float(med_de[r]),
                measured_de=float(med_dm[r]),
                suspect=bool(suspect[r]),
                further=float(med_fu[r]))

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
