"""The ruler check (Preferences > Beta, stage 1: CHECK ONLY), 2026-11-14.

The X-Rite i1Pro 2 and i1Pro 3 count the stripes of their ruler while a strip
is scanned. ChromIQ's reading engine hands this file one record per strip
(``{"event":"ruler_strip", ...}``, see ``native/instlib/cq_ruler.h``): the
ruler code stream in a lossless compact form (the first 2-bit code, then for
every change the gap in samples since the previous change and the new code),
the number of samples, the readings of the scan and the clock.

Everything here only DESCRIBES a strip. Nothing in this module can change a
measured value or which reading went to which patch: the readings and the
patch cut are today's, made before this code runs. The one decision it makes
is whether to ASK about an accepted strip that the ruler says was clearly not
covered, and that only when every check on the ruler data itself passed.

Thresholds are PROVISIONAL, taken from two USB recordings of one i1Pro 2
(firmware 634) and one of an i1Pro 3 (see the work folder
2026-11-14_ruler_beta/DESIGN.md); they are written into every diagnostics
file so testers' files can revise them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

#: ArgyllCMS's quadrature table (i1pro3_imp.c, i1pro3_zebra_proc): index
#: (old << 2) | new -> -1, 0, +1, or 9 for an impossible (illegal) change.
_DVAL = (0, -1, +1, 9,
         +1, 0, 9, -1,
         -1, 9, 0, +1,
         9, +1, -1, 0)

#: Fewer changes than this means "no ruler under the instrument"
#: (ArgyllCMS's own validity rule for the i1Pro 3; no-ruler scans had 0 on the
#: i1Pro 2 and 8 on the i1Pro 3).
MIN_TRANSITIONS = 10
#: i1Pro 2: samples = readings x clocks - 5, give or take one 64-byte packet
#: (R1/R3: exact in 9 of 10 scans, one +64).
I1PRO2_PAIR_OFFSET = 5
I1PRO2_PAIR_TOLERANCE = 64
#: The question fires below this share of the patch span (PROVISIONAL).
COVER_FRACTION = 0.9
#: Upper bounds for the size of one ruler step, mm (PROVISIONAL). An unknown
#: step size may only make the question LESS likely: the larger the step, the
#: fewer steps the span needs.
MM_PER_STEP_UPPER = {"i1pro2": 1.10, "i1pro3": 0.55}
#: ArgyllCMS's own step size for the i1Pro 3 ruler (0.5 mm per transition).
MM_PER_STEP_KNOWN = {"i1pro3": 0.5}
#: Margin on a step size derived in this session from today's cut.
DERIVED_MARGIN = 1.10
#: Window for the peak speed, seconds (stage 0's definition).
PEAK_WINDOW_S = 0.25
#: Strips needed before a pitch in steps from today's cut is trusted for a
#: chart without geometry.
MIN_STRIPS_FOR_SESSION_PITCH = 3

THRESHOLDS = {
    "min_transitions": MIN_TRANSITIONS,
    "i1pro2_pair_offset": I1PRO2_PAIR_OFFSET,
    "i1pro2_pair_tolerance": I1PRO2_PAIR_TOLERANCE,
    "cover_fraction": COVER_FRACTION,
    "mm_per_step_upper": dict(MM_PER_STEP_UPPER),
    "mm_per_step_known": dict(MM_PER_STEP_KNOWN),
    "derived_margin": DERIVED_MARGIN,
    "peak_window_s": PEAK_WINDOW_S,
    "min_strips_for_session_pitch": MIN_STRIPS_FOR_SESSION_PITCH,
    "provisional": True,
}


@dataclass
class Decoded:
    """The ruler stream turned into positions."""
    #: sample index of every legal change, and the count after it
    at: "list[int]" = field(default_factory=list)
    pos: "list[int]" = field(default_factory=list)
    illegal: int = 0
    transitions: int = 0


def decode(first_code: int, changes: "list[int]") -> Decoded:
    """*changes* is the flat list [gap0, code0, gap1, code1, ...] the engine
    sends: gap = samples since the previous change (since sample 0 for the
    first), code = the new 2-bit code."""
    d = Decoded()
    prev = int(first_code) & 3
    idx = 0
    count = 0
    for k in range(0, len(changes) - 1, 2):
        idx += int(changes[k])
        code = int(changes[k + 1]) & 3
        v = _DVAL[(prev << 2) | code]
        prev = code
        if v == 9:
            d.illegal += 1
            continue
        if v == 0:
            continue
        count += v
        d.transitions += 1
        d.at.append(idx)
        d.pos.append(count)
    return d


@dataclass
class StripFigures:
    """What the ruler says about one strip. ``usable`` False = fall back."""
    seen: bool = False
    pairs: bool = False
    usable: bool = False
    why_not: str = ""            # "no_ruler", "not_paired", "garbled", "read", "empty"
    transitions: int = 0
    illegal: int = 0
    travel_steps: int = 0        # max - min of the count
    net_steps: int = 0           # end - start
    sign: int = 0                # +1 / -1 / 0
    motion_s: float = 0.0
    mean_steps_s: float = 0.0
    peak_steps_s: float = 0.0
    expected_samples: Optional[int] = None


def _paired(gen: str, samples: int, readings: int, clocks: int) -> "tuple[bool, int | None]":
    if readings <= 0 or clocks <= 0:
        return False, None
    if gen == "i1pro2":
        exp = readings * clocks - I1PRO2_PAIR_OFFSET
        return abs(samples - exp) <= I1PRO2_PAIR_TOLERANCE, exp
    exp = readings * clocks
    return exp - 2 * clocks <= samples <= exp, exp


def figures(rec: dict) -> StripFigures:
    """The figures of one ``ruler_strip`` record. Never raises on odd input:
    anything it cannot use makes ``usable`` False."""
    f = StripFigures()
    try:
        gen = str(rec.get("instrument") or "")
        status = str(rec.get("ended") or "")
        samples = int(rec.get("samples") or 0)
        readings = int(rec.get("readings") or 0)
        clocks = int(rec.get("clocks") or 0)
        clock_s = float(rec.get("clock_s") or 0.0)
        d = decode(int(rec.get("first") or 0), list(rec.get("changes") or []))
    except (TypeError, ValueError):
        f.why_not = "read"
        return f
    f.transitions, f.illegal = d.transitions, d.illegal
    f.seen = d.transitions >= MIN_TRANSITIONS
    f.pairs, f.expected_samples = _paired(gen, samples, readings, clocks)
    if d.pos:
        f.travel_steps = max(0, max(d.pos)) - min(0, min(d.pos))
        f.net_steps = d.pos[-1]
        f.sign = (f.net_steps > 0) - (f.net_steps < 0)
        if clock_s > 0 and len(d.at) > 1:
            f.motion_s = (d.at[-1] - d.at[0]) * clock_s
            if f.motion_s > 0:
                f.mean_steps_s = abs(f.net_steps) / f.motion_s
            win = max(1, int(round(PEAK_WINDOW_S / clock_s)))
            j = 0
            best = 0
            for i in range(len(d.at)):
                while d.at[i] - d.at[j] > win:
                    j += 1
                best = max(best, i - j + 1)
            f.peak_steps_s = best / PEAK_WINDOW_S
    if status not in ("short", "cancelled", "argyll"):
        f.why_not = "read"
    elif not f.seen:
        f.why_not = "no_ruler"
    elif f.illegal:
        f.why_not = "garbled"
    elif not f.pairs:
        f.why_not = "not_paired"
    else:
        f.usable = True
    return f


def span_steps(gen: str, span_mm: "float | None",
               derived_mm_per_step: "float | None" = None,
               session_span_steps: "float | None" = None) -> "float | None":
    """The patch span in ruler steps, as SMALL as it can honestly be (so the
    question can only be too shy, never too eager). None = unknown."""
    if span_mm and span_mm > 0:
        upper = (derived_mm_per_step * DERIVED_MARGIN
                 if derived_mm_per_step else MM_PER_STEP_UPPER.get(gen))
        if upper:
            return span_mm / upper
    if session_span_steps and session_span_steps > 0:
        return session_span_steps
    return None


def not_covered(f: StripFigures, span: "float | None") -> bool:
    """True when the accepted strip was clearly not covered: only with usable
    ruler data and a known span."""
    return bool(f.usable and span and f.travel_steps < COVER_FRACTION * span)


def mm_per_step(gen: str, derived: "float | None" = None) -> "float | None":
    """The step size to show figures in mm with, or None (show steps)."""
    if gen in MM_PER_STEP_KNOWN:
        return MM_PER_STEP_KNOWN[gen]
    return derived
