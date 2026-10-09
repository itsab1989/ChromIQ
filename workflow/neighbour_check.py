"""The neighbour check: a patch further from its expected colour than the
patches nearest to it in colour are from theirs (#182).

**The rule, beta 17: Knut's four steps** (#182 6071673457, adopted in
6078174421: "I think the 4 steps should be used"):

1. for each neighbour, its error: ΔE*ab between its reading and its
   expected colour;
2. the MEDIAN of the neighbours' errors;
3. the patch's own error, the same way;
4. the patch is a suspected misread (red outline) when its own error minus
   that median is MORE than the **Neighbour limit**.

**The neighbours** (6078174421, 6082015002, 6085694445): the 2 to 4 read
patches nearest to it in EXPECTED colour within the **Colour-neighbour
radius**, from ANY strip, its own included (calibration charts hold their
colour ramps on one strip; patch by patch there is no strip). With fewer
than 2 the patch is not judged at all: a patch is never suspected for lack of
comparisons. There is nothing else: no hidden threshold, no "twice the
limit", no "always 4". Beta 15's first test (the readings further apart than
the expected colours, by more than a "buffer") is gone; the number that is
compared with the limit is the very number every patch card shows.

**Defaults** (``workflow/misread_settings.py``), per chart type: Neighbour
limit 10 / 5 / 3 / 10 and Colour-neighbour radius 15 / 30 / 30 / 30 (profiling
charts with estimated colours / made with a pre-conditioning profile /
verification charts / calibration charts), all ΔE*ab, all configurable in
Preferences ▸ Measurement.

**When.** While a chart is being read most patches have too few neighbours,
so it is judged again after every completed strip (and after every patch,
patch by patch) and when a measurement is opened from disk.
:meth:`NeighbourCheck.evaluate` judges every patch afresh from the readings
on hand. Only the patch's own re-read (within the Same-reading tolerance)
turns a suspect yellow; a green patch turns red again when a later reading of
it is a misread.

L*a*b* as the engine computes it (D50). Pure logic: no Qt, numpy only.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: A comparison patch's EXPECTED colour lies within this of the patch's own
#: (the Colour-neighbour radius on a profiling chart with estimated colours;
#: the other chart types have their own, ``workflow/misread_settings.py``).
RADIUS_DE = 15.0
#: At most this many comparison patches, the nearest by expected colour.
MAX_COMPARED = 4
#: Fewer than this, and the patch is not judged.
MIN_COMPARED = 2
#: The Neighbour limit on a profiling chart with estimated colours: the
#: patch's own error may be at most this much above the median of its
#: neighbours' errors (ΔE*ab). Every chart type has its own
#: (``workflow/misread_settings.py``).
LIMIT_DE = 10.0
#: The neighbour check's own switch (k44, Knut #182 6060201176), on by
#: default. Off, it judges nothing: no patch is red for it, and its outlines
#: come back as they were when it is switched on again.
SWITCH_KEY = "patch_neighbour_check"


def enabled_from(settings) -> bool:
    """Whether the neighbour check is switched on (Preferences ▸
    Measurement, k44); on when unset or unreadable."""
    from workflow.misread_settings import neighbour_check_on
    return neighbour_check_on(settings)

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

    *compared* are their locations, nearest first. *further* is Knut's
    number: the patch's own error minus the median of its neighbours'
    errors (ΔE*ab; below 0 it is closer to its expected colour than they
    are to theirs). *own_de* is its own error and *median_de* the median of
    theirs. *suspect* is the verdict: at least :data:`MIN_COMPARED`
    neighbours, and *further* more than the Neighbour limit."""
    loc: str
    compared: tuple = ()
    own_de: float = 0.0
    median_de: float = 0.0
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
                 limit: float = LIMIT_DE) -> None:
        self.radius = float(radius)
        self.k = int(k)
        self.min_compared = int(min_compared)
        self.limit = float(limit)
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

    def set_limit(self, limit: float) -> None:
        """Take the user's Neighbour limit (Preferences ▸ Measurement); a new
        one judges every patch again at the next evaluation."""
        limit = float(limit)
        if limit != self.limit:
            self.limit = limit
            self._changed = None
            self._arrived, self._left = set(), set()

    def set_radius(self, radius: float) -> None:
        """Take the user's Colour-neighbour radius; a new one finds every
        patch's neighbours afresh at the next evaluation."""
        radius = float(radius)
        if radius != self.radius:
            self.radius = radius
            self._changed = None
            self._arrived, self._left = set(), set()

    def __len__(self) -> int:
        return len(self._rows)

    def set_reading(self, loc: str, exp_xyz100, meas_xyz100,
                    strip: "str | None") -> None:
        """Remember the latest reading of *loc* (XYZ 0..100, D50), read in
        *strip* (None or "" when not known; the strip no longer decides who
        compares with whom, beta 17, but is kept for the callers)."""
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

        A patch's comparison patches depend only on the expected colours of
        the patches read, so they are kept between evaluations and
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
                    # an arrival is no neighbour of itself
                    rows_ = np.arange(lo, min(lo + _BLOCK, n))[:, None]
                    ok &= rows_ != new_idx[None, :]
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
        """May a and b compare: their expected colours lie within the
        Colour-neighbour radius. From ANY strip, its own included (Knut,
        #182 6078174421: "neighbours should come from any strip"). The
        strips are still passed, so the search keeps one shape."""
        return d <= self.radius

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
            # never itself
            ok[np.arange(len(rr)), rr] = False
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
        """Knut's four steps for *rows*: each neighbour's error, their
        median, the patch's own error, and own minus median against the
        Neighbour limit."""
        k = max(1, self.k)
        idx = np.full((len(rows), k), -1, dtype=int)
        for r, i in enumerate(rows):
            lst = [pos[x] for x in self._lists.get(locs[i], ()) if x in pos][:k]
            idx[r, :len(lst)] = lst
        ok = idx >= 0
        count = ok.sum(axis=1)
        safe = np.where(ok, idx, 0)
        # steps 1 and 3: each reading's distance from its own expected colour
        own = np.linalg.norm(meas[rows] - exp[rows], axis=1)
        off_nb = np.linalg.norm(meas[safe] - exp[safe], axis=2)
        off_nb[~ok] = np.nan
        has = count > 0
        med = np.zeros(len(rows))
        if has.any():
            med[has] = np.nanmedian(off_nb[has], axis=1)     # step 2
        further = own - med
        # step 4
        suspect = has & (count >= self.min_compared) & (further > self.limit)
        for r, i in enumerate(rows):
            if not has[r]:
                self._findings[locs[i]] = NeighbourFinding(locs[i])
                continue
            self._findings[locs[i]] = NeighbourFinding(
                loc=locs[i],
                compared=tuple(locs[j] for j in idx[r][ok[r]]),
                own_de=float(own[r]),
                median_de=float(med[r]),
                suspect=bool(suspect[r]),
                further=float(further[r]))

    def finding(self, loc: str) -> "NeighbourFinding | None":
        """The last evaluation's finding for *loc* (None: no reading then)."""
        return self._findings.get(str(loc))

    def comparison(self, loc: str) -> "tuple[int, float]":
        """b15 item 10 (Knut #182 6065640028): ``(n, further)`` for the hover
        card: how many read patches *loc* is compared with (0 to
        :data:`MAX_COMPARED`), and its own error minus the median of theirs
        (ΔE*ab; above 0: further from its expected colour than they are from
        theirs). The very figure step 4 compares with the Neighbour limit, so
        the card and the outline cannot disagree (Knut 6071004702).
        ``(0, 0.0)`` for a patch with no reading or no comparison."""
        f = self._findings.get(str(loc))
        if f is None:
            return 0, 0.0
        return len(f.compared), float(f.further)

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
