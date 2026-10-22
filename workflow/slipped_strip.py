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

FILED BACK TO FRONT (agent 14's review, 4.3.10). A strip can be read in either
direction, and the engine files it the way its colours fit best. A strip that
slipped by one patch from end to end can fit the REVERSE direction better than
its own, and is then filed back to front: measured on screen, all 13 patches
of a slipped strip 36 were stored reversed (``"reversed": true``) and nothing
asked. The run search therefore also tries the readings taken in the opposite
order (each patch against the patch at the mirrored place of the strip, in
step or one patch out), and such a finding is reported as ``reversed``.

PRESERVE PATCH ORDER (agent 14's review). On a chart laid out in plain order
neighbouring patches are steps of one ramp, and a reading that is one ramp
step off its own colour looks just like a reading one patch out of place: a
print a little darker than the design fits "the patch before it" by chance.
Agent 14 measured that as 0.6 % of honest strips (about two false questions
on a 729-patch chart). On a ramp a slip and a printing difference of one step
cannot be told apart at all, so a run whose neighbours are steps of a ramp
(`SMOOTH_Q`) has to be far wrong as read and fit far better shifted before it
counts (`SMOOTH_TRIGGER_DE`, `SMOOTH_RATIO`): the slips that matter, readings
filed tens of ΔE away from their own patch, are still found (agent 15's
harness: 0 false alarms in 299,460 honest strips in plain order, where 596
were flagged before; on a verification in plain order 90 % of whole-strip
slips that put readings 20 ΔE or more off are still named, 99 % before).

The search judges in CIE76 ΔE (as the engine's net does). The numbers it
reports for people to read are ΔE00, like every table of the Measurement
Report (`SlippedRun.base_de00` / ``shifted_de00``), averaged over exactly the
patches of the run (`run_first` to `run_last`); the patch the slip pushed out
of step (`lead`) is named apart, with whether it read the white paper.

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
#: A RUN ON A RAMP. When the colours each patch of a run is compared with
#: differ from its own by less than this share of the strip's typical
#: difference between any two of its patches, the run lies along a ramp of
#: similar steps (a chart laid out with "Preserve Patch Order"); on a
#: randomised chart neighbours are as far apart as any two patches (share
#: 0.6 to 1.4). Measured on six charts in plain order through seven real
#: printer profiles (agent 15, 2026-10-22): every false alarm lay below 0.6.
SMOOTH_Q = 0.6
#: ...and such a run counts only when its readings miss their own colours by
#: at least this much on average (the false alarms of agent 14's harness
#: missed by 12 to 25 ΔE: one ramp step of printing difference)...
SMOOTH_TRIGGER_DE = 25.0
#: ...and fit far better shifted than the ratio asked of any other run. 25 and
#: 0.3 sit in the middle of the settings that gave no false alarm at all on
#: 299,460 honest strips in plain order (20 / 0.35 gave 42, 12 / 0.2 gave 21;
#: agent 15's sweep, 2026-10-22).
SMOOTH_RATIO = 0.3


@dataclass(frozen=True)
class SlippedRun:
    """A run of a strip's patches whose readings look out of place.

    ``offset`` +1: each reading is the colour of the patch BEFORE it in the
    strip, as read (the reader started on the paper, so the first patch read
    paper); -1: the colour of the patch AFTER it; 0 (only with ``reversed``):
    read in step but filed back to front. ``reversed``: the readings fit when
    taken in the opposite order, from the strip's last patch to its first.

    ``first`` and ``last`` are 0-based positions in the strip, both included,
    and cover every patch the slip spoiled: the run itself (`run_first` to
    `run_last`, the patches every average is taken over) and, when it misses
    its own colour as badly, the one patch the slip pushed out of step
    (`lead`; ``lead_paper`` when it read the white paper).

    ``base_de`` / ``shifted_de``: the run's mean CIE76 ΔE as read and against
    the colour each reading fits (the engine's measure, what the thresholds
    judge). ``base_de00`` / ``shifted_de00``: the same in ΔE00, the unit of
    the Measurement Report's tables, for the texts people read."""
    offset: int
    first: int
    last: int
    base_de: float
    shifted_de: float
    reversed: bool = False
    run_first: int = -1
    run_last: int = -1
    base_de00: "float | None" = None
    shifted_de00: "float | None" = None
    lead: "int | None" = None
    lead_paper: bool = False

    @property
    def patches(self) -> int:
        return self.last - self.first + 1

    def covers(self, n: int) -> bool:
        """True when the spoiled span is the whole strip of *n* patches."""
        return self.first == 0 and self.last == n - 1


def _de(a: Sequence[float], b: Sequence[float]) -> float:
    return math.dist(tuple(a), tuple(b))


def _de00(a: Sequence[float], b: Sequence[float]) -> float:
    from workflow.ti3_analysis import ciede2000
    return ciede2000(tuple(a), tuple(b))


def looks_like_paper(lab: "Sequence[float] | None",
                     paper: "Sequence[float] | None" = None) -> bool:
    """Is *lab* a reading of the white paper? Against the paper's own reading
    when it is known (within 6 ΔE76), else: light and nearly neutral (L* 85
    or more, chroma 15 or less, which holds for papers with optical
    brighteners too)."""
    if lab is None:
        return False
    try:
        if paper is not None:
            return _de(lab, paper) <= 6.0
        L, a, b = (float(v) for v in lab)
        return L >= 85.0 and math.hypot(a, b) <= 15.0
    except (TypeError, ValueError):
        return False


def _partner(i: int, n: int, off: int, rev: bool) -> int:
    """The strip position whose colour reading *i* carries under a mapping."""
    return (n - 1 - i - off) if rev else (i - off)


def _runs_for(own, m, e, n, off, rev, spread):
    """Every qualifying run for one mapping, as (a, b, base, shifted)."""
    sh: "list[float | None]" = []
    nb: "list[float | None]" = []
    for i in range(n):
        j = _partner(i, n, off, rev)
        if 0 <= j < n and own[i] is not None and e[j] is not None:
            # Back to front, the patch in the middle of the strip is its own
            # partner: filed in its right place, it neither carries nor
            # breaks a run (it never counts as fitting better).
            sh.append(_de(m[i], e[j]))
            nb.append(_de(e[i], e[j]))
        else:
            sh.append(None)
            nb.append(None)
    found = []
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
            nbm = s_nb / length
            trigger, ratio = TRIGGER_DE, RATIO
            # A run along a ramp: one printing step looks like a slip.
            if spread > 0 and nbm < SMOOTH_Q * spread:
                trigger, ratio = SMOOTH_TRIGGER_DE, SMOOTH_RATIO
            # Both ends must themselves fit better shifted, so a run
            # does not reach past the slip into the patches read in step
            # on the strength of the slipped ones' average.
            if (sh[a] < own[a] and sh[b] < own[b]
                    and base >= trigger and shifted <= GOOD_DE
                    and shifted <= ratio * base
                    and nbm >= MIN_NEIGHBOUR_DE
                    and better >= MOST * length):
                found.append((a, b, base, shifted))
    return found


def _with_touching_stretch(a: int, b: int, off: int, mir: dict) -> list:
    """The mirrored stretch *a*..*b* (offset *off*) and, when there is one,
    the longest stretch of a neighbouring offset (0 next to +1 or -1) that
    touches it, clipped so the two do not overlap: a strip that slipped part
    of the way and was then filed back to front. Sorted (first, last, off)."""
    best = None
    for o, runs in mir.items():
        if o == off or abs(o - off) != 1:
            continue
        for ra, rb, _b, _s in runs:
            if rb < a - 1 or ra > b + 1:
                continue
            if rb < a or ra > b:
                seg = (ra, rb, o)
            elif ra < a:
                seg = (ra, a - 1, o)
            elif rb > b:
                seg = (b + 1, rb, o)
            else:
                continue
            if seg[1] - seg[0] + 1 >= 1 and (
                    best is None or seg[1] - seg[0] > best[1] - best[0]):
                best = seg
    return sorted([(a, b, off)] + ([best] if best else []))


def find_slipped_run(measured: "Sequence[Sequence[float]]",
                     expected: "Sequence[Sequence[float]]",
                     paper: "Sequence[float] | None" = None
                     ) -> "SlippedRun | None":
    """The longest run of patches (in strip order) whose readings fit other
    patches' expected colours far better than their own, or None: the
    neighbour's (one patch late or early), or, read the other way round, the
    patch at the mirrored place of the strip (filed back to front).

    *measured* and *expected* are Lab triples of ONE strip, in the order the
    patches stand in it. A patch with no reading may be given as None and is
    never part of a run. *paper*: the white paper's Lab, when known, for
    `SlippedRun.lead_paper`."""
    n = min(len(measured), len(expected))
    if n < MIN_RUN + 1:
        return None
    m = list(measured[:n])
    e = list(expected[:n])
    own = [(_de(m[i], e[i]) if m[i] is not None and e[i] is not None else None)
           for i in range(n)]
    known = [x for x in e if x is not None]
    pairs = [_de(known[i], known[j]) for i in range(len(known))
             for j in range(i + 1, len(known))]
    spread = sum(pairs) / len(pairs) if pairs else 0.0
    fwd = {o: _runs_for(own, m, e, n, o, False, spread) for o in (1, -1)}
    mir = {o: _runs_for(own, m, e, n, o, True, spread) for o in (0, 1, -1)}
    # (key, offset, reversed, segments, base, shifted); segments are
    # (first, last, offset) stretches, each reading compared with its
    # partner under its own stretch's offset.
    cands = []
    for o, runs in fwd.items():
        for a, b, base, shifted in runs:
            # The patch the slip pushed out of step counts to its span, so
            # a slip that also fits back to front is called a slip.
            cands.append(((min(n, b - a + 2), 1, base - shifted), o, False,
                          [(a, b, o)], base, shifted))
    for o, runs in mir.items():
        for a, b, base, shifted in runs:
            segs = _with_touching_stretch(a, b, o, mir)
            span = segs[-1][1] - segs[0][0] + 1
            # Filed back to front is a whole-strip matter (the engine turns
            # the strip round, not part of it): the mirrored stretches must
            # hold most of the strip. A strip that also slipped fits in two
            # touching stretches, one in step and one a patch out.
            if span < MOST * (n - 1):
                continue
            cands.append(((span, 0, base - shifted), segs[0][2], True, segs,
                          base, shifted))
    if not cands:
        return None
    _key, off, rev, segments, base, shifted = max(cands, key=lambda c: c[0])
    run_first = segments[0][0]
    run_last = segments[-1][1]
    pts = [(i, _partner(i, n, o, rev)) for sa, sb, o in segments
           for i in range(sa, sb + 1)]
    try:
        d00_own = [_de00(m[i], e[i]) for i, _j in pts]
        d00_sh = [_de00(m[i], e[j]) for i, j in pts]
        base00 = round(sum(d00_own) / len(d00_own), 1)
        sh00 = round(sum(d00_sh) / len(d00_sh), 1)
    except Exception:            # noqa: BLE001 - the figures are a courtesy
        base00 = sh00 = None
    if len(segments) > 1:
        base = sum(own[i] for i, _j in pts) / len(pts)
        shifted = sum(_de(m[i], e[j]) for i, j in pts) / len(pts)
    # The patch the slip pushed out: the reading with no partner on the
    # strip. Forward +1 (and back to front -1): the one before the run (the
    # paper, or a patch's own colour lost); forward -1 (back to front +1):
    # the one after it. It belongs to the spoiled stretch when it misses its
    # own colour as badly as the run does.
    lead = None
    if (not rev and off == 1) or (rev and segments[0][2] == -1):
        lead = run_first - 1
    elif (not rev and off == -1) or (rev and segments[-1][2] == 1):
        lead = run_last + 1
    first, last = run_first, run_last
    lead_paper = False
    if lead is not None and 0 <= lead < n and own[lead] is not None \
            and own[lead] >= TRIGGER_DE:
        first, last = min(first, lead), max(last, lead)
        lead_paper = looks_like_paper(m[lead], paper)
    else:
        lead = None
    # A strip filed back to front is wrong from end to end, also where a
    # reading happens to sit near its own colour: name the whole strip.
    if rev:
        first, last = 0, n - 1
    return SlippedRun(offset=(segments[0][2] if rev else off),
                      first=first, last=last, base_de=round(base, 2),
                      shifted_de=round(shifted, 2), reversed=rev,
                      run_first=run_first, run_last=run_last,
                      base_de00=base00, shifted_de00=sh00, lead=lead,
                      lead_paper=lead_paper)


_D50 = (96.42, 100.0, 82.49)


def xyz_to_lab(xyz: "Sequence[float]") -> "tuple[float, float, float]":
    """XYZ (Y = 100 for the white) to Lab under D50, as the engine does."""
    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0
    fx, fy, fz = (f(float(v) / w) for v, w in zip(xyz, _D50))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def slipped_run_in_strip_read(patches: "Sequence[dict]") -> "SlippedRun | None":
    """`find_slipped_run` over the engine's ``strip_read`` event patches
    (``{"loc", "xyz", "exyz", …}`` in strip order, as FILED). Never raises."""
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
                   expected: "Sequence", labels,
                   paper: "Sequence[float] | None" = None) -> "list[dict]":
    """Every strip of a stored measurement whose readings look out of place,
    for the Measurement Report: ``[{"strip", "first", "last", "offset",
    "reversed", "patches", "run_first", "run_last", "lead", "lead_paper",
    "base_de", "shifted_de", "base_de00", "shifted_de00", "whole"}]`` in
    chart order (locations, not positions; ``lead`` None when no patch
    outside the run was spoiled).

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
            run = find_slipped_run(meas, exp, paper)
            if run is None:
                continue

            def _loc(pos):
                return (str(locs[order[pos]])
                        if pos is not None and order[pos] is not None
                        else None)
            out.append({
                "strip": labels.strip(s),
                "first": _loc(run.first),
                "last": _loc(run.last),
                "offset": run.offset,
                "reversed": run.reversed,
                "patches": run.patches,
                "run_first": _loc(run.run_first),
                "run_last": _loc(run.run_last),
                "lead": _loc(run.lead),
                "lead_paper": run.lead_paper,
                "base_de": run.base_de,
                "shifted_de": run.shifted_de,
                "base_de00": run.base_de00,
                "shifted_de00": run.shifted_de00,
                "whole": run.covers(len(order)),
            })
        return out
    except Exception:            # noqa: BLE001 - a check, never a failure
        return []
