"""Does part of a strip read one patch out of place? (forum post 149786)

A strip reader that starts on the blank paper before the first patch files
the paper as patch 1, patch 1 as patch 2, and so on. When the reader then
misses one boundary further along (two neighbouring patches run into one), the
readings fall back into step and the REST of the strip is read correctly. So
only a run of patches is shifted, not the whole strip.

That is what a forum user's i1Pro 3 did on strip 36 of a 585-patch
verification chart (ChromIQ 4.3.8/4.3.9, Windows): patches 36A to 36H came
out with ΔE00 17 to 66, every other patch of the chart at 5.5 or less, and
each of those patches' MEASURED colour was the EXPECTED colour of the patch
before it (36A measured the paper). The engine's safety net
(`cq_detect_misalign`, native/chartread_helper/chromiq_chartread.c) only asks
whether the WHOLE strip fits better shifted, and a strip that is half shifted
and half right fits badly at every whole-strip offset, so it said nothing.

This module asks the same question about a RUN of neighbouring patches, with
the net's own thresholds, so a slip that heals itself half way along is found
as surely as one that runs to the end. It is used twice:

* live, by `MeasureManager` on every strip the engine reads (with the
  misalignment warning on), so the "Strip may be misaligned" question comes
  while the strip can still be read again;
* afterwards, by the Measurement Report, which says next to its Worst patches
  table which strip looks shifted, so a report of a measurement that slipped
  anyway explains its own worst patches.

Pure functions on Lab values; no Qt, no files.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

#: The engine net's numbers (`CQ_MIS_TRIGGER_DE`, `CQ_MIS_GOOD_DE`,
#: `CQ_MIS_RATIO`), applied to the run instead of the whole strip. The expected
#: colours during a measurement are the chart's DESIGN colours, which no real
#: printer reproduces closely (10 to 26 ΔE mean on a correctly read real
#: strip, #210), so "fits" means "fits far better than as read", never "fits
#: well".
TRIGGER_DE = 12.0
GOOD_DE = 35.0
RATIO = 0.5
#: The fewest neighbouring patches a run may hold. Two or three patches can
#: resemble their neighbours by chance; four in a row that each match the
#: colour beside them instead of their own is a slip.
MIN_RUN = 4
#: The neighbours' expected colours must differ, on average, by at least this
#: much, or a shift could not be told from a right reading at all (a ramp of
#: near-identical steps fits nearly as well either way).
MIN_NEIGHBOUR_DE = 12.0
#: Most of the run must fit better shifted patch by patch, not only on
#: average, so one patch that happens to sit near its neighbour's colour
#: cannot carry a run.
MOST = 0.75


@dataclass(frozen=True)
class SlippedRun:
    """A run of a strip's patches whose readings look shifted by one patch.

    ``offset`` +1: each reading is the colour of the patch BEFORE it in the
    strip (the reader started on the paper, so the first patch read paper);
    -1: the colour of the patch AFTER it. ``first`` and ``last`` are 0-based
    positions in the strip, both included, and cover every patch the slip
    spoiled (for +1, the first patch of the run's lead-in too, when it misses
    its own colour). ``base_de`` is the run's mean ΔE as read and
    ``shifted_de`` the mean ΔE once each reading is compared with its
    neighbour's colour (CIE76, as the engine measures it)."""
    offset: int
    first: int
    last: int
    base_de: float
    shifted_de: float

    @property
    def patches(self) -> int:
        return self.last - self.first + 1


def _de(a: Sequence[float], b: Sequence[float]) -> float:
    return math.dist(tuple(a), tuple(b))


def find_slipped_run(measured: "Sequence[Sequence[float]]",
                     expected: "Sequence[Sequence[float]]"
                     ) -> "SlippedRun | None":
    """The longest run of patches (in strip order) whose readings fit their
    neighbours' expected colours far better than their own, or None.

    *measured* and *expected* are Lab triples of ONE strip, in the order the
    patches stand in it. A patch with no reading may be given as None and is
    never part of a run."""
    n = min(len(measured), len(expected))
    if n < MIN_RUN + 1:
        return None
    m = list(measured[:n])
    e = list(expected[:n])
    own = [(_de(m[i], e[i]) if m[i] is not None and e[i] is not None else None)
           for i in range(n)]
    best: "SlippedRun | None" = None
    best_key = None
    for off in (1, -1):
        sh: "list[float | None]" = []
        nb: "list[float | None]" = []
        for i in range(n):
            j = i - off
            if 0 <= j < n and own[i] is not None and e[j] is not None:
                sh.append(_de(m[i], e[j]))
                nb.append(_de(e[i], e[j]))
            else:
                sh.append(None)
                nb.append(None)
        for a in range(n):
            if sh[a] is None:
                continue
            s_own = s_sh = s_nb = 0.0
            better = 0
            for b in range(a, n):
                if sh[b] is None:
                    break
                s_own += own[b]
                s_sh += sh[b]
                s_nb += nb[b]
                better += 1 if sh[b] < own[b] else 0
                length = b - a + 1
                if length < MIN_RUN:
                    continue
                base, shifted = s_own / length, s_sh / length
                # Both ends must themselves fit better shifted, so a run
                # does not reach past the slip into the patches read in step
                # on the strength of the slipped ones' average.
                if (sh[a] < own[a] and sh[b] < own[b]
                        and base >= TRIGGER_DE and shifted <= GOOD_DE
                        and shifted <= RATIO * base
                        and s_nb / length >= MIN_NEIGHBOUR_DE
                        and better >= MOST * length):
                    key = (length, base - shifted)
                    if best_key is None or key > best_key:
                        best_key = key
                        best = SlippedRun(off, a, b, round(base, 2),
                                          round(shifted, 2))
    if best is None:
        return None
    # The patch the slip pushed out: with +1 the reading before the run's
    # first patch (the paper, or the patch's own colour lost), with -1 the one
    # after its last. It belongs to the spoiled stretch when it misses its own
    # colour as badly as the run does.
    first, last = best.first, best.last
    if best.offset == 1 and first > 0 and own[first - 1] is not None \
            and own[first - 1] >= TRIGGER_DE:
        first -= 1
    if best.offset == -1 and last < n - 1 and own[last + 1] is not None \
            and own[last + 1] >= TRIGGER_DE:
        last += 1
    return SlippedRun(best.offset, first, last, best.base_de, best.shifted_de)


_D50 = (96.42, 100.0, 82.49)


def xyz_to_lab(xyz: "Sequence[float]") -> "tuple[float, float, float]":
    """XYZ (Y = 100 for the white) to Lab under D50, as the engine does."""
    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0
    fx, fy, fz = (f(float(v) / w) for v, w in zip(xyz, _D50))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def slipped_run_in_strip_read(patches: "Sequence[dict]") -> "SlippedRun | None":
    """`find_slipped_run` over the engine's ``strip_read`` event patches
    (``{"loc", "xyz", "exyz", …}`` in strip order). Never raises."""
    try:
        meas, exp = [], []
        for p in patches or ():
            xyz, exyz = p.get("xyz"), p.get("exyz")
            ok = (isinstance(xyz, (list, tuple)) and len(xyz) == 3
                  and isinstance(exyz, (list, tuple)) and len(exyz) == 3)
            meas.append(xyz_to_lab(xyz) if ok else None)
            exp.append(xyz_to_lab(exyz) if ok else None)
        return find_slipped_run(meas, exp)
    except Exception:            # noqa: BLE001 - a check, never a failure
        return None


def shifted_strips(locs: "Sequence[str]", measured: "Sequence",
                   expected: "Sequence", labels) -> "list[dict]":
    """Every strip of a stored measurement whose readings look shifted by one
    patch, for the Measurement Report: ``[{"strip", "first", "last",
    "offset", "patches", "base_de", "shifted_de"}]`` in chart order.

    *locs*, *measured* and *expected* run in step (one entry per patch, Lab
    triples, ``None`` where a patch has no reference to compare with);
    *labels* is the chart's `ChartLabels`, which says which strip each
    location belongs to and where in it. A location the labels cannot place
    is left out, and a missing patch breaks a run rather than joining two.
    Never raises."""
    try:
        from workflow.layout_engine.labels import location_key
        strips: "dict[int, dict[int, int]]" = {}
        for i, loc in enumerate(locs):
            key = location_key(labels, str(loc or ""))
            if key is not None:
                strips.setdefault(key[0], {})[key[1]] = i
        out: "list[dict]" = []
        for s in sorted(strips):
            by_patch = strips[s]
            top = max(by_patch) + 1
            order = [by_patch.get(p) for p in range(top)]
            meas = [measured[i] if i is not None else None for i in order]
            exp = [expected[i] if i is not None else None for i in order]
            run = find_slipped_run(meas, exp)
            if run is None:
                continue
            out.append({
                "strip": labels.strip(s),
                "first": str(locs[order[run.first]]),
                "last": str(locs[order[run.last]]),
                "offset": run.offset,
                "patches": run.patches,
                "base_de": run.base_de,
                "shifted_de": run.shifted_de,
            })
        return out
    except Exception:            # noqa: BLE001 - a check, never a failure
        return []
