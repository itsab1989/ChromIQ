#!/usr/bin/env python3
"""Create Chart presets, TWO PER REQUIREMENT, one each side of its line (#182).

Knut, 2026-09-19:

    *"Recreate the chart presets so that every metric that can be tested has
    one preset for each condition a metric uses to select if a patch set can
    be used in verification to test against that metric. For example, of one
    metric uses a grey ramp of several patches, and is counted as grey if the
    red, green and blue values are within one unit of each other. Secondly,
    there is a requirement minimum eight steps. Further, there migth also be a
    requirement that the selected patches have a certain distance between each
    other, and that they reach whit and black at the end […] Thus, create one
    preset for each requirement of a metric, where each threshold is on the
    border of the threshold, but not complying with that specific requirement.
    And then one preset for each requirement of a metric, where each threshold
    is on the border of the threshold, but complying with that specific
    requirement."*

**WHAT CHANGED, AND WHY IT IS A FINER GRID THAN THE ONE BEFORE IT.** The pack
that shipped in beta 23 had fourteen presets built around REASON CODES: one
preset per sentence the window can say. A reason code is not a requirement.
``control_strip_too_small`` is two requirements (eight ids for the average,
twenty for the 95th percentile); ``too_few_surface_patches`` is two (what
counts as a surface patch, and how many are needed); ``no_ramp`` is two (how
many steps, and how far apart). One preset per code cannot tell you which half
of a code is broken.

So this pack is built around REQUIREMENTS: sixteen of them, each with a FAIL
preset one notch outside its line and a PASS preset exactly ON it. A pair
differs by ONE thing and nothing else, so the rows that change between the two
are the rows that requirement governs, and a detection that quietly went dead
turns exactly one pair grey.

**EVERY OPERATOR HERE WAS READ OUT OF THE SOURCE, NOT ASSUMED.** "At least 8
steps" fails at 7 and passes at 8; "within 1 unit" passes AT 1 only because the
comparison is ``<=``; "reaches white" is really ``max(level) >= 90`` and not
"there is a paper patch". Each :class:`Requirement` below carries the
comparison as it is written in the source, and the file and constant it was
read from, so a reader can check the claim rather than believe it.

**TWO PRESETS ONCE ASKED A QUESTION INSTEAD OF MAKING A CLAIM, AND BOTH
HAVE BEEN ANSWERED.** Knut's own paragraph names a requirement he expected to
find: *"that the selected patches have a certain distance between each other
… so that they are not clumped together in one end or in the middle"*. For the
GREY RAMP he ruled it on 2026-09-23 (#182 B8-483, 5795087247), and the chart
that asked it, once the open preset Q1, is now R14's FAIL side. For the 30 to
70 % tone ramp he ruled it the same day (K31, #182 5801677743: *"Implement
rule A ... update the demo project package to test the requirements for this
metric with the new rule"*), and the chart that asked it, once the open preset
Q2, is now R15's FAIL side, beside a PASS preset whose three steps are evenly
spaced.

Every design here was measured, not reasoned about: ``--check`` builds each
patch set, runs the app's own eligibility path over it, and prints the rows
each preset really answers and really withholds. ``--grid`` prints the same
thing as the FAIL-against-PASS table the round's report is made of.

No Qt in here, and no ArgyllCMS: a ``.ti1`` is CGATS text and these charts are
designed patch by patch, because a chart designed by ``targen`` is exactly the
chart that does NOT fail anything.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

#: The folder a user copies into their own presets directory. The name says
#: where it goes, because a folder called "presets" in a download tells nobody.
FOLDER = "Create Chart presets (verification demos)"

#: The tab folder inside the user's presets directory, from the app's own map.
TAB = "create_chart"

#: printtarg's seed for every demo here: the release pack's one seed, the same
#: number as `make_report_limit_demos.PRINTTARG_SEED` (a test holds them equal;
#: importing that module here would pull its whole build in).
PRINTTARG_SEED = 182


# ---------------------------------------------------------------------------
# A .ti1 is CGATS text
# ---------------------------------------------------------------------------
#: sRGB primaries, D65, for the aim XYZ every .ti1 carries beside its RGB.
_M = ((0.4124, 0.3576, 0.1805),
      (0.2126, 0.7152, 0.0722),
      (0.0193, 0.1192, 0.9505))
_WHITE = (95.05, 100.0, 108.90)
#: A little flare, so black is not the mathematical zero no printer reaches.
_FLARE = 0.01


def aim_xyz(rgb: "tuple[float, float, float]") -> "tuple[float, float, float]":
    """The chart's own design XYZ for a device triple, on the 0..100 scale.

    Only its PRESENCE and its chroma order matter to this window: the stand-in
    report sets the measured colour equal to the aim, so every ΔE00 is zero and
    no verdict in the window depends on the number. It still has to be a real
    colour, because ``parse_ti3`` reads it and the outer-gamut quartile is
    ranked by its chroma.
    """
    lin = [(max(0.0, min(100.0, v)) / 100.0) ** 2.2 for v in rgb]
    xyz = [sum(_M[i][j] * lin[j] for j in range(3)) * 100.0 for i in range(3)]
    return tuple(round((1.0 - _FLARE) * xyz[i] + _FLARE * _WHITE[i], 4)
                 for i in range(3))


def write_ti1(path: Path, patches: "list[tuple[float, float, float]]",
              *, keywords: "dict[str, str] | None" = None,
              descriptor: str = "ChromIQ verification demo chart") -> None:
    """Write *patches* as a ``.ti1``, ids 1..n, with optional CGATS keywords."""
    lines = ['CTI1   ', '',
             f'DESCRIPTOR "{descriptor}"',
             'ORIGINATOR "ChromIQ demo package"',
             f'APPROX_WHITE_POINT "{_WHITE[0]:.6f} {_WHITE[1]:.6f} {_WHITE[2]:.6f}"',
             'COLOR_REP "iRGB"']
    for key, value in (keywords or {}).items():
        lines.append(f'{key} "{value}"')
    lines += ['', 'NUMBER_OF_FIELDS 7', 'BEGIN_DATA_FORMAT',
              'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z',
              'END_DATA_FORMAT', '',
              f'NUMBER_OF_SETS {len(patches)}', 'BEGIN_DATA']
    for i, rgb in enumerate(patches, start=1):
        x, y, z = aim_xyz(rgb)
        lines.append(f'{i} {rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f} '
                     f'{x:.4f} {y:.4f} {z:.4f}')
    lines += ['END_DATA', '']
    # **THE TWO TABLES printtarg NEEDS, WHICH EVERY DEMO LACKED UNTIL K40-1.**
    # A preset's patch set is laid out by printtarg when the preset is loaded
    # and generated, and printtarg refuses a .ti1 that holds only the colours
    # ("Input file doesn't contain two or three tables"). Measured when the
    # presets window started laying presets out behind the scenes (Knut,
    # #182 5832026677): all 31 demos were refused, so not one of them could
    # have been printed. The density extremes (targen's second table, white
    # first, which printtarg reads as its spacer palette and label decision)
    # and the device combinations (its third), as
    # `workflow.i1profiler_import.write_ti1` writes them, with no CREATED
    # stamp so the file is the same on every build.
    from workflow.i1profiler_import import (_DENSITY_EXTREMES,
                                            _DEVICE_COMBINATIONS)
    for keyword, rows in (("DENSITY_EXTREME_VALUES", _DENSITY_EXTREMES),
                          ("DEVICE_COMBINATION_VALUES", _DEVICE_COMBINATIONS)):
        lines += ['CTI1   ', '',
                  'DESCRIPTOR "Argyll Calibration Target chart information 1"',
                  'ORIGINATOR "ChromIQ demo package"',
                  f'{keyword} "{len(rows)}"', '',
                  'NUMBER_OF_FIELDS 7', 'BEGIN_DATA_FORMAT',
                  'INDEX RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z',
                  'END_DATA_FORMAT', '', f'NUMBER_OF_SETS {len(rows)}',
                  'BEGIN_DATA']
        for i, rgb in enumerate(rows):
            x, y, z = aim_xyz(rgb)
            lines.append(f'{i} {rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f} '
                         f'{x:.4f} {y:.4f} {z:.4f}')
        lines += ['END_DATA', '']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# The parts every chart here is assembled from
# ---------------------------------------------------------------------------
#: **WHY NOT A CUBE AND A targen CHART.** Every part below is built so that it
#: can only satisfy the ONE condition it is there for. A five-level cube
#: satisfies four of them at once and cannot be moved off any single line
#: without moving off the others too, which is how the old pack ended up with a
#: preset that failed three requirements and proved none of them.
#:
#: The rules each part obeys, and the reason for each:
#:
#: * a **filler** has every channel inside 15..85 and a channel spread over 24.
#:   Inside 15..85 it cannot be a surface patch (needs a channel within 2.0 of
#:   0 or 100) and cannot reach a control-strip rung that has a channel at 0 or
#:   100; a spread over 24 keeps it off the three grey rungs and out of the
#:   grey population; and with no two channels at 99 or over it is on no
#:   single-ink ramp axis. A filler therefore only ever adds to the PATCH
#:   COUNT, which is what the outer-gamut and worst-5 % requirements are about.
#: * a **surface candidate** has exactly one channel near a face and the other
#:   two 30 or more apart, so it is a surface patch and nothing else.
#: * a **neutral** is (v, v, v), or (v, v, v + s) when a spread is asked for.
#: * the **cyan ramp** is the single-ink axis: G and B at 100, R stepped. It is
#:   the only part with two channels at 99 or over, so it is the only part that
#:   can put steps on a non-grey ramp axis.

def greys(levels, spread: float = 0.0) -> "list[tuple[float, float, float]]":
    """Neutrals at each level, optionally *spread* device units out of neutral.

    The spread is put on the channel that keeps the patch inside 0..100, which
    matters: a value over 101 would make ``_rgb_to_0_100`` decide the chart is
    on the 0..255 scale and divide the whole thing by 2.55.
    """
    out = []
    for v in levels:
        v = float(v)
        if not spread:
            out.append((v, v, v))
        elif v < 50.0:
            out.append((v, v, v + spread))
        else:
            out.append((v - spread, v, v))
    return out


#: Twelve surface candidates: one channel on a face, the other two far apart
#: and far from every rung of the control-strip ladder.
_FACE_SEEDS = ((0, 40, 62), (0, 62, 40), (40, 0, 62), (62, 0, 40),
               (40, 62, 0), (62, 40, 0), (100, 30, 66), (100, 66, 30),
               (30, 100, 66), (66, 100, 30), (30, 66, 100), (66, 30, 100))


def surface(k: int = 12, distance: float = 0.0
            ) -> "list[tuple[float, float, float]]":
    """*k* patches whose nearest cube face is *distance* device units away."""
    out = []
    for seed in _FACE_SEEDS[:k]:
        t = [float(c) for c in seed]
        for j in range(3):
            if t[j] == 0.0:
                t[j] = float(distance)
            elif t[j] == 100.0:
                t[j] = 100.0 - float(distance)
        out.append(tuple(t))
    return out


_LATTICE = (15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0)


#: K43: the larger demos need more fillers than `_LATTICE` holds (390). The
#: same rules on a lattice five units apart, taken only after the coarse one
#: is used up, so every 78-patch chart is byte for byte what it was.
_FINE_LATTICE = tuple(15.0 + 5.0 * i for i in range(15))


def fillers(n: int) -> "list[tuple[float, float, float]]":
    """*n* interior patches that satisfy no condition at all. See the note
    above: they only ever add to the patch count."""
    out = []
    seen = set()
    for lattice in (_LATTICE, _FINE_LATTICE):
        for r in lattice:
            for g in lattice:
                for b in lattice:
                    if max(r, g, b) - min(r, g, b) <= 24.0:
                        continue
                    if (r, g, b) in seen:
                        continue
                    seen.add((r, g, b))
                    out.append((r, g, b))
                    if len(out) == n:
                        return out
    raise AssertionError(f"only {len(out)} fillers available, {n} asked for")


def cyan_ramp(tone_values=(30.0, 50.0, 70.0)
              ) -> "list[tuple[float, float, float]]":
    """The single-ink axis: G and B at 100, R at ``100 - tone value``."""
    return [(100.0 - float(tv), 100.0, 100.0) for tv in tone_values]


def strip_ids(k: int) -> "dict[str, str]":
    """A CONTROL_STRIP_IDS keyword naming the chart's first *k* patches.

    **THE CHART DECLARES ITS OWN STRIP, AND THAT IS THE POINT OF USING IT
    HERE.** `workflow.control_strip.declare_for_chart` will write a
    declaration for any chart that fills eight of its twenty-nine ladder rungs,
    and every chart in this pack fills five (paper, solid black and the three
    grey rungs) because none of them carries a cube corner or a tint. Without a
    keyword every one of them would read `no_control_strip`, and a preset that
    fails the control strip AND the thing it is about proves neither. The
    keyword is the app's own second route to a declaration
    (`measurement_report.CONTROL_STRIP_KEYWORD`), so this is a chart saying
    what it has, not a test hook.
    """
    return {"CONTROL_STRIP_IDS": " ".join(str(i) for i in range(1, k + 1))}


#: A neutral ramp that clears every grey-balance condition with room to spare:
#: eleven levels, reaching 0 and 100, five of them inside the 30 to 70 % band.
_GREY_OK = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)

#: The same, kept OFF the cube faces (nothing within 2.0 of 0 or 100) so that a
#: chart's surface population is exactly the surface candidates it was given.
#: 2.5 is still "black" (the line is 10) and 97.5 is still "white" (the line is
#: 90), which is why the two conditions can be separated at all.
#: Evenly spaced from 2.5 to 97.5 (steps of 11.875, rounded to a tenth), so
#: it also meets the spacing rule of #182 B8-483 (`GREY_SPACING_TOL`).
_GREY_OFF_THE_FACES = (2.5, 14.4, 26.3, 38.1, 50.0, 61.9, 73.8, 85.6, 97.5)

#: #182 B8-483 (Knut, 2026-09-23): eight steps from 0 to 100, each within
#: `GREY_SPACING_TOL` of an even spacing (0, 14.3, 28.6 … 100), with four of
#: them (30, 43, 57, 70) inside the 30 to 70 % band, spanning 40 points.
_GREY_EIGHT_EVEN = (0.0, 14.0, 30.0, 43.0, 57.0, 70.0, 86.0, 100.0)

#: How far past a line a FAIL preset sits. One tenth of a device unit on a
#: continuous threshold, one patch or one step on a counted one: the smallest
#: step this file can express and still have a reader see it in the .ti1.
NOTCH = 0.1

#: Every chart in the pack is this big unless its own requirement is about the
#: patch count. 78 clears the outer-gamut floor of 77 by one.
_N = 78


def _pad(parts, n: int = _N):
    """*parts*, topped up with fillers to *n* patches."""
    return list(parts) + fillers(n - len(parts))


# ---------------------------------------------------------------------------
# The charts, one pair per requirement
# ---------------------------------------------------------------------------
def chart_control():
    """Everything a patch set can answer, answered, with room on every line."""
    return _pad(greys(_GREY_OK) + surface() + cyan_ramp())


# -- R01 / R02 / R03: the control strip ------------------------------------
def chart_strip_base():
    """One patch set for all four control-strip presets: what changes across
    them is the KEYWORD and nothing else.

    **AND IT HAS NO CYAN RAMP, WHICH IS NOT A DETAIL.** Measured while building
    this pack: the control chart's three cyan-ramp patches sit inside 12 device
    units of three tint rungs, which takes the ladder from five filled rungs to
    eight, and eight is exactly where
    `control_strip.declare_for_chart` starts writing a declaration of its own.
    The first build of R01's FAIL side therefore ANSWERED the two rows it was
    built to withhold. The neutral ramp already carries the 30 to 70 % row, so
    the cyan ramp is simply left out here and the ladder stays at five.
    """
    return _pad(greys(_GREY_OK) + surface())


# -- R04: what counts as a neutral -----------------------------------------
def chart_grey_spread(spread: float):
    """The same eleven-level ramp, *spread* device units out of neutral.

    The cyan ramp is in both sides of the pair, so the 30 to 70 % row is
    answered whether or not the neutrals count as neutral: this pair moves the
    grey-balance rows and nothing else.
    """
    return _pad(greys(_GREY_OK, spread) + surface() + cyan_ramp())


# -- R05 / R06 / R07 / R09 / R10: the neutral ramp itself ------------------
def chart_grey_levels(levels):
    return _pad(greys(levels) + surface())


# -- R08: the patch count --------------------------------------------------
def chart_patch_count(n: int):
    """A chart of exactly *n* patches that clears every OTHER line it can.

    Eight neutral steps reaching 0 and 100, evenly spaced within
    `GREY_SPACING_TOL`, four of them in the 30 to 70 % band and spanning 40
    points; ten surface patches, two of which are the ends of the ramp. What it
    cannot clear is the outer-gamut line, which wants 77 patches: see ``also``.
    """
    parts = greys(_GREY_EIGHT_EVEN) + surface(8)
    return _pad(parts, n)


# -- R11 / R12: the surface population -------------------------------------
def chart_surface(k: int, distance: float):
    """*k* surface candidates at *distance* from a face, and a neutral ramp
    that stays off the faces so it adds none of its own."""
    return _pad(greys(_GREY_OFF_THE_FACES) + surface(k, distance))


# -- R13: the outer-gamut quartile -----------------------------------------
def chart_total(n: int):
    return _pad(greys(_GREY_OK) + surface(), n)


# -- the two open questions ------------------------------------------------
def chart_clumped_greys():
    """Eight neutral steps, seven of them inside 3.6 device units.

    0, then 90.0, 90.6, 91.2, 91.8, 92.4, 93.0, 93.6. Eight distinct steps by
    ChromIQ's own 0.5-unit rule, it reaches black at one end and 93.6 clears
    the 90 that "reaches white" means, so the grey-balance rows are judged on a
    ramp that is one black patch and a huddle at the top.
    """
    lv = (0.0, 90.0, 90.6, 91.2, 91.8, 92.4, 93.0, 93.6)
    # #182 K49, (b2): a patch of bare paper, as the PASS side has one at 100,
    # so the paper row reads the same on both sides and only the grey pair
    # moves. At 100 it is one more neutral step, and the huddle stays a huddle.
    return _pad(greys(lv) + [(100.0, 100.0, 100.0)] + surface() + cyan_ramp())


def chart_paper_patch(white: float):
    """#182 K49, (b2): the control chart with its lightest neutral at
    *white* on every channel. At 100 - PAPER_PATCH_TOL (99.5) or above it is
    a patch printed with no ink, and the paper row is answered; one notch
    under it the chart has none. The neutral still reaches white either way
    (the line is 90), so nothing else moves."""
    lv = list(_GREY_OK[:-1]) + [white]
    return _pad(greys(lv) + surface() + cyan_ramp())


def chart_even_greys():
    """R14's PASS side: the chart above with its eight grey steps evenly
    spaced from 0 to 100 (`_GREY_EIGHT_EVEN`). Four of them fall in the 30 to
    70 % band of the grey axis, but the cyan ramp already answers the
    tone-ramp row on both sides, so nothing but the grey pair moves.
    """
    return _pad(greys(_GREY_EIGHT_EVEN) + surface() + cyan_ramp())


def chart_clumped_ramp(tone_values=(40.0, 59.4, 60.0)):
    """Three mid-tone steps spanning 20 points, two of them 0.6 apart.

    R15's FAIL side (K31 rule A); with ``(40, 50, 60)`` it is the PASS side,
    the same chart with its three steps evenly spaced.

    Tone values 40.0, 59.4 and 60.0 on the cyan axis. Three distinct steps by
    the same 0.5-unit rule and a span of exactly 20, so the 30 to 70 % row is
    judged on two readings at one end and one at the other. The neutral ramp
    puts only TWO steps in the band (43 and 57), too few for the grey axis to
    count as a ramp, so the cyan axis is the only one there. Since #182 B8-483
    the neutral ramp is evenly spaced as well: the old one (0, 10, 20, 25, 75,
    80, 90, 100) kept the band empty by leaving a gap of 50, which the grey
    rows now refuse.
    """
    lv = (0.0, 14.0, 29.0, 43.0, 57.0, 71.0, 86.0, 100.0)
    return _pad(greys(lv) + surface() + cyan_ramp(tone_values))


# -- R16: the page the evenness rows judge (K43, larger demos) --------------
#: **HOW printtarg LAYS THESE PRESETS OUT, MEASURED (2026-09-25).** i1Pro, A4,
#: 300 dpi, -L, as `payload` stores. At the default patch size: 21 patches to
#: a strip, at most 24 strips to a page, the block covering 2.98 % of the page
#: per strip (20 strips 59.6 %, 21 strips 62.6 %). At ``-a 0.80`` (R16): 27
#: patches to a strip, 24 strips cover 58.8 % and 25 cover 61.2 %. The two
#: evenness rows want a page of at least `EVENNESS_MIN_GRID` (9) strips by 9
#: rows and a block covering at least `EVENNESS_MIN_PAGE_COVERAGE` (60 %).
#:
#: **WHY R16 IS NOT AT THE DEFAULT PATCH SIZE, where the line falls between
#: 420 and 421 patches.** The window also withholds an evenness verdict when
#: the sheet's own noise is not below the limit (Knut, ruling 6), and with 47
#: patches to each of the nine areas a 421-patch sheet's noise is 1.14, over
#: Custom ISO 12647-7's pairwise limit of 1.0: its PASS side would have been
#: withheld for a second reason. At ``-a 0.80`` the line falls between 648 and
#: 649 patches, 72 to an area, noise 0.94, and nothing but the coverage moves.
#: (No one-page A4 i1Pro chart at the default size is below 1.0: 504 patches,
#: 1.03.)
R16_SCALE = 0.80


def chart_page(n: int):
    """The control's patches, topped up with fillers to *n*: every row it
    decides answered, whatever the page does."""
    return _pad(greys(_GREY_OK) + surface() + cyan_ramp(), n)


# ---------------------------------------------------------------------------
# The requirements
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Requirement:
    """One condition the eligibility path applies, and the pair that proves it.

    *comparison* is the line as it is written in the source, and *source* says
    where to read it. They are here because a boundary without its operator is
    a guess: "at least 8" and "more than 8" put the PASS preset on different
    patch counts, and this pack has been wrong about one of them before.
    """
    key: str
    #: the metric, in the words of the row group it belongs to
    metric: str
    #: the condition, in the words of the help text the user is shown
    text: str
    #: the comparison, copied from the source
    comparison: str
    #: module and constant it was read from
    source: str
    #: the row ids this requirement alone decides
    rows: "tuple[str, ...]"
    #: the reason code the FAIL side must produce on those rows
    reason: str
    #: what is one notch outside the line, and what is exactly on it
    fail_label: str
    pass_label: str
    fail_chart: Callable
    pass_chart: Callable
    fail_keywords: "dict[str, str]" = field(default_factory=dict)
    pass_keywords: "dict[str, str]" = field(default_factory=dict)
    #: reason codes BOTH sides carry, with the arithmetic that forces them.
    #: A pair is isolated when the two sides differ only on ``rows``; a code
    #: here is constant across the pair and therefore changes nothing.
    also: "tuple[str, ...]" = ()
    also_why: str = ""
    #: K43: printtarg's patch size (-a) both presets are saved with, when it
    #: is not the pack's 1.0 (the page is what R16 is about)
    scale: float = 1.0


_CS_ROWS = ("control_strip_de00_avg", "control_strip_de00_max",
            "control_strip_de00_p95")
_GREY_ROWS = ("grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max")

REQUIREMENTS: "tuple[Requirement, ...]" = (
    Requirement(
        "R01", "Control strip",
        "A chart carries a control strip when it says so itself: a sidecar "
        "beside it, or a CONTROL_STRIP_IDS keyword in its .ti1.",
        "declaration is None  ->  no_control_strip",
        "measurement_report.control_strip_block",
        _CS_ROWS, "no_control_strip",
        "the same patch set with no keyword and too few ladder rungs to be "
        "given one",
        "the same patch set with a CONTROL_STRIP_IDS keyword naming 20 ids",
        chart_strip_base, chart_strip_base,
        {}, strip_ids(20)),
    Requirement(
        "R02", "Control strip, average and largest",
        "At least 8 of the declared ids are in the measurement and carry a "
        "reference value.",
        "k < CONTROL_STRIP_MIN (8)  ->  control_strip_too_small",
        "measurement_report.CONTROL_STRIP_MIN",
        ("control_strip_de00_avg", "control_strip_de00_max"),
        "control_strip_too_small",
        "a declaration naming 7 ids", "a declaration naming 8 ids",
        chart_strip_base, chart_strip_base,
        strip_ids(7), strip_ids(8),
        ("control_strip_too_small",),
        "The 95th-percentile row wants 20 of the same ids, so it is short on "
        "both sides of this pair. R02 and R03 are two lines on ONE number and "
        "the pass side of the lower one is the fail side of the higher one."),
    Requirement(
        "R03", "Control strip, 95th percentile",
        "The 95th percentile needs 20 of them, because below that its nearest "
        "rank is the largest patch itself.",
        "k >= CONTROL_STRIP_P95_MIN (20)  ->  p95_eligible",
        "measurement_report.CONTROL_STRIP_P95_MIN",
        ("control_strip_de00_p95",), "control_strip_too_small",
        "a declaration naming 19 ids", "a declaration naming 20 ids",
        chart_strip_base, chart_strip_base,
        strip_ids(19), strip_ids(20)),
    Requirement(
        "R04", "Grey balance",
        "A patch counts as grey when its red, green and blue values are "
        "within one unit of each other.",
        "rgb.max() - rgb.min() <= GREY_SPREAD_TOL (1.0)",
        "measurement_report.GREY_SPREAD_TOL",
        _GREY_ROWS, "no_greys",
        "a ramp built 1.1 units out of neutral",
        "a ramp built exactly 1.0 unit out of neutral",
        lambda: chart_grey_spread(1.0 + NOTCH),
        lambda: chart_grey_spread(1.0),
        strip_ids(20), strip_ids(20),
        also=("paper_not_measured",),
        also_why='#182 K49, (b2): neither side carries a patch printed with no ink (its lightest patch is what this pair is about, or is kept off the faces), so the paper row reads paper_not_measured on both.'),
    Requirement(
        "R05", "Grey balance",
        "There have to be at least eight distinct steps of it. Two levels "
        "count as one step unless they are more than 0.5 units apart.",
        "_distinct_levels(levels) < GREY_MIN_LEVELS (8)  ->  too_few_steps",
        "measurement_report.GREY_MIN_LEVELS, GREY_LEVEL_TOL",
        _GREY_ROWS, "too_few_steps",
        "7 distinct steps", "8 distinct steps",
        lambda: chart_grey_levels((0.0, 14.0, 30.0, 43.0, 57.0, 70.0, 100.0)),
        lambda: chart_grey_levels(_GREY_EIGHT_EVEN),
        strip_ids(20), strip_ids(20)),
    Requirement(
        "R06", "Grey balance",
        "It has to reach white at one end. What the code asks for is a "
        "neutral at level 90 or lighter, which is not the same as a patch of "
        "bare paper.",
        "max(levels) < GREY_LIGHTEST_MIN (90.0)  ->  no_white",
        "measurement_report.GREY_LIGHTEST_MIN",
        _GREY_ROWS, "no_white",
        "the lightest neutral at 89.9", "the lightest neutral at exactly 90.0",
        lambda: chart_grey_levels((0.0, 13.0, 26.0, 39.0, 51.0, 64.0, 77.0,
                                   90.0 - NOTCH)),
        lambda: chart_grey_levels((0.0, 13.0, 26.0, 39.0, 51.0, 64.0, 77.0,
                                   90.0)),
        strip_ids(20), strip_ids(20),
        also=("paper_not_measured",),
        also_why='#182 K49, (b2): neither side carries a patch printed with no ink (its lightest patch is what this pair is about, or is kept off the faces), so the paper row reads paper_not_measured on both.'),
    Requirement(
        "R07", "Grey balance",
        "It has to reach black at the other. What the code asks for is a "
        "neutral at level 10 or darker.",
        "min(levels) > GREY_DARKEST_MAX (10.0)  ->  no_black",
        "measurement_report.GREY_DARKEST_MAX",
        _GREY_ROWS, "no_black",
        "the darkest neutral at 10.1", "the darkest neutral at exactly 10.0",
        lambda: chart_grey_levels((10.0 + NOTCH, 23.0, 36.0, 49.0, 61.0, 74.0,
                                   87.0, 100.0)),
        lambda: chart_grey_levels((10.0, 23.0, 36.0, 49.0, 61.0, 74.0, 87.0,
                                   100.0)),
        strip_ids(20), strip_ids(20)),
    Requirement(
        "R08", "Worst 5 % of patches",
        "The chart needs at least twenty patches counted, so that a worst "
        "twentieth exists to average.",
        "ceil(0.95 n) == n  ->  small_sample, which is every n <= 19",
        "measurement_report._stats",
        ("worst5_de00_avg",), "small_sample",
        "19 patches", "20 patches",
        lambda: chart_patch_count(19), lambda: chart_patch_count(20),
        strip_ids(8), strip_ids(8),
        ("too_few_outer_patches", "control_strip_too_small"),
        "A chart of twenty patches cannot put twenty in its own top quarter, "
        "which needs 77, and cannot declare a strip of twenty either. Both "
        "are short on BOTH sides of this pair, so neither moves with it. "
        "Twenty patches is the smallest chart in the pack for the same reason "
        "it is the requirement: there is no smaller one that can carry it."),
    Requirement(
        "R09", "Ramps 30 to 70 %",
        "At least three distinct steps between 30 % and 70 % tone value, on "
        "any one of the four axes.",
        "distinct >= RAMP_MIN_STEPS (3)",
        "measurement_report.RAMP_MIN_STEPS",
        ("ramps_30_70_dl_max",), "no_ramp",
        "2 steps in the band", "3 steps in the band",
        lambda: chart_grey_levels((0.0, 12.5, 25.0, 40.0, 60.0, 75.0, 87.5,
                                   100.0)),
        lambda: chart_grey_levels((0.0, 12.5, 25.0, 40.0, 50.0, 60.0, 75.0,
                                   87.5, 100.0)),
        strip_ids(20), strip_ids(20)),
    Requirement(
        "R10", "Ramps 30 to 70 %",
        "Those steps have to span at least twenty points of tone value.",
        "span >= RAMP_MIN_SPAN (20.0)",
        "measurement_report.RAMP_MIN_SPAN",
        ("ramps_30_70_dl_max",), "no_ramp",
        "3 steps spanning 19 points", "3 steps spanning exactly 20 points",
        lambda: chart_grey_levels((0.0, 12.5, 25.0, 40.5, 50.0, 59.5, 75.0,
                                   87.5, 100.0)),
        lambda: chart_grey_levels((0.0, 12.5, 25.0, 40.0, 50.0, 60.0, 75.0,
                                   87.5, 100.0)),
        strip_ids(20), strip_ids(20)),
    Requirement(
        "R11", "Surface of the device cube",
        "A patch is on the surface when at least one of its red, green and "
        "blue values is within 2.0 of 0 or of 100.",
        "min(v, 100 - v) <= SURFACE_GAMUT_TOL (2.0), for some channel",
        "measurement_report.SURFACE_GAMUT_TOL",
        ("surface_gamut_de00_avg",), "too_few_surface_patches",
        "12 candidates, every one 2.1 from the nearest face",
        "the same 12, every one exactly 2.0 from the nearest face",
        lambda: chart_surface(12, 2.0 + NOTCH),
        lambda: chart_surface(12, 2.0),
        strip_ids(20), strip_ids(20),
        also=("paper_not_measured",),
        also_why='#182 K49, (b2): neither side carries a patch printed with no ink (its lightest patch is what this pair is about, or is kept off the faces), so the paper row reads paper_not_measured on both.'),
    Requirement(
        "R12", "Surface of the device cube",
        "At least 10 of those patches carry a reference value.",
        "len(sdes) >= SURFACE_GAMUT_MIN (10)",
        "measurement_report.SURFACE_GAMUT_MIN",
        ("surface_gamut_de00_avg",), "too_few_surface_patches",
        "9 surface patches", "10 surface patches",
        lambda: chart_surface(9, 0.0), lambda: chart_surface(10, 0.0),
        strip_ids(20), strip_ids(20),
        also=("paper_not_measured",),
        also_why='#182 K49, (b2): neither side carries a patch printed with no ink (its lightest patch is what this pair is about, or is kept off the faces), so the paper row reads paper_not_measured on both.'),
    Requirement(
        "R13", "Outer gamut, top quarter by C*ab",
        "The top quarter by chroma has to hold at least 20 patches. The help "
        "text says that wants roughly 80; the arithmetic says 77.",
        "ceil(n_referenced * 0.25) >= OUTER_GAMUT_MIN (20), so n >= 77",
        "measurement_report.OUTER_GAMUT_FRACTION, OUTER_GAMUT_MIN",
        ("outer_gamut_226_de00_avg",), "too_few_outer_patches",
        "76 patches, so the quarter holds 19",
        "77 patches, so the quarter holds exactly 20",
        lambda: chart_total(76), lambda: chart_total(77),
        strip_ids(20), strip_ids(20)),
    # #182 B8-483 (Knut, 2026-09-23, 5795087247): was the open question Q1.
    Requirement(
        "R14", "Grey balance",
        "At least eight of those steps have to be roughly evenly spaced from "
        "black to white, each within 4 units of where an even spacing puts "
        "it, so the steps between the two ends are not bunched together.",
        "no GREY_MIN_LEVELS (8) or more evenly spaced positions each have a "
        "level within GREY_SPACING_TOL (4.0)  ->  grey_steps_bunched",
        "measurement_report.GREY_SPACING_TOL, pick_even_grey_steps",
        _GREY_ROWS, "grey_steps_bunched",
        "black and seven steps inside 3.6 units at the light end",
        "eight steps each within 4 units of an even spacing",
        chart_clumped_greys, chart_even_greys,
        strip_ids(20), strip_ids(20)),
    # K31 rule A (Knut, 2026-09-23, #182 5801677743): was the open question Q2.
    Requirement(
        "R15", "Ramps 30 to 70 %",
        "Three of those steps have to be roughly evenly spaced from the "
        "ramp's own lowest step in the band to its highest, each within 4 "
        "points of where an even spacing puts it, so three readings bunched "
        "at one end cannot stand for the whole mid-tone range.",
        "no RAMP_MIN_STEPS (3) or more evenly spaced positions each have a "
        "step within RAMP_SPACING_TOL (4.0)  ->  ramp_steps_bunched",
        "measurement_report.RAMP_SPACING_TOL, pick_even_grey_steps",
        ("ramps_30_70_dl_max",), "ramp_steps_bunched",
        "mid-tone steps 40, 59.4 and 60",
        "mid-tone steps 40, 50 and 60",
        chart_clumped_ramp, lambda: chart_clumped_ramp((40.0, 50.0, 60.0)),
        strip_ids(20), strip_ids(20)),
    # K43 (Knut, #182 5833695633: "use also larger demo charts/presets to
    # catch and test more metrics and combinations"): the first pair large
    # enough for the evenness rows' 9 by 9 page, one patch either side of the
    # page-coverage line.
    Requirement(
        "R16", "Evenness across the sheet",
        "The page has to be at least 9 strips by 9 rows, and the patch block "
        "has to cover at least 60 % of it, so that the nine areas the sheet "
        "is split into are real areas of the page.",
        "strips and rows >= EVENNESS_MIN_GRID (9), and the block's share of "
        "the page >= EVENNESS_MIN_PAGE_COVERAGE (0.60)  ->  otherwise "
        "evenness_page_coverage_too_small",
        "measurement_report.EVENNESS_MIN_GRID, EVENNESS_MIN_PAGE_COVERAGE",
        ("uniformity_sd", "uniformity_de00_max_from_mean"),
        "evenness_page_coverage_too_small",
        "648 patches, 24 i1Pro strips covering 58.8 % of an A4 page",
        "649 patches, 25 strips covering 61.2 %",
        lambda: chart_page(648), lambda: chart_page(649),
        strip_ids(20), strip_ids(20), scale=R16_SCALE),
    # #182 K49, (b2) (Knut, 5841092535, "Yes"): the paper row is compared
    # with the profile's media white on any chart with a patch printed with
    # no ink, so whether a chart has one is a requirement of its own.
    Requirement(
        "R17", "Paper white against the reference paper",
        "The chart has to carry a patch printed with no ink: every red, green "
        "and blue value within 0.5 of 100.",
        "no row with rgb.min() >= 100 - PAPER_PATCH_TOL (0.5), so 99.5  ->  "
        "paper_not_measured",
        "measurement_report.PAPER_PATCH_TOL, paper_patch_rows",
        ("substrate_de00_max",), "paper_not_measured",
        "the lightest patch at 99.4 on every channel",
        "the lightest patch at exactly 99.5",
        lambda: chart_paper_patch(99.5 - NOTCH),
        lambda: chart_paper_patch(99.5),
        strip_ids(20), strip_ids(20)),
)


# ---------------------------------------------------------------------------
# The presets
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Demo:
    """One preset: a name, a patch set, and what it is built to prove."""
    n: int
    name: str
    #: what a reader should understand it proves, one sentence
    blurb: str
    #: "control", "FAIL", "PASS", "open" or "other"
    kind: str = "other"
    #: the requirement it belongs to, or ""
    key: str = ""
    #: the reason code the window must give it, or "" when nothing is withheld
    reason: str = ""
    #: the rows that reason must land on
    rows: "tuple[str, ...]" = ()
    #: reason codes it ALSO fires, with the arithmetic in ``Requirement.also_why``
    also: "tuple[str, ...]" = ()
    #: the comparison, copied from the source, for the README and the report
    comparison: str = ""
    source: str = ""
    chart: "Callable | None" = None
    keywords: "dict[str, str]" = field(default_factory=dict)
    #: write a .ti1 that cannot be parsed as a chart
    corrupt: bool = False
    #: write no .ti1 at all (a preset that stores settings only)
    no_chart: bool = False
    #: K43: printtarg's patch size (-a) the preset is saved with
    scale: float = 1.0


def opening_choice() -> "tuple[str, str]":
    """The (report type, limit set) the presets window OPENS on.

    Asked of the two lists the window fills its pulldowns from, in the order
    it fills them (`PresetVerificationDialog.__init__`: the built types of
    `REPORT_TYPE_MENU`, then `selectable_set_ids`), so a change to either
    moves this with it.

    Since B8-974 the first "Judged against" entry is "All metrics"
    (`preset_eligibility.ALL_METRICS`), which asks every row a report of the
    type can judge, so every pair shows at the opening choice and no preset
    name carries a "[judge with ...]" tag any more.
    """
    from workflow import measurement_report as MR
    from workflow import preset_eligibility as PE
    # Since K33 (B8-996) the first "Report type" entry is "Any"
    # (`preset_eligibility.ANY_REPORT_TYPE`), so the window opens on the
    # widest question in both pulldowns.
    del MR
    return PE.ANY_REPORT_TYPE, PE.ALL_METRICS


def shown_under(r: "Requirement") -> "tuple[str, str]":
    """Where the window ASKS every row requirement *r* decides.

    **KNUT'S "NOT TRIGGERING FAIL", MEASURED (K15, 2026-09-22).** The window
    judges a chart only against the metrics the chosen report type and limit
    set ask, and it opens on ChromIQ's own default set, which puts a number on
    the grey pair and the five colour-difference rows and on nothing else. So
    eight of the thirteen pairs (the control strip, the tone ramps, the
    surface and the outer gamut) showed BOTH presets as answering everything,
    and a FAIL preset that reads the same as its PASS proves nothing. The test
    that guarded the pack set the window to Custom ISO 12647-7 before it
    looked, which is why it never saw it.

    The rule is the window's, not the pack's, and it is right: a limit set
    that judges nothing about the control strip should not mark a chart down
    for lacking one. So each pair now SAYS where it shows, and this is the
    one place that decides it: the opening choice when that already asks the
    rows, otherwise the first limit set, in the window's own order, that does
    under the same report type.
    """
    from workflow import compliance_sets as CS
    from workflow import measurement_report as MR
    from workflow import preset_eligibility as PE
    opening = opening_choice()
    types = [opening[0]] + [t for t, _n, _b, _built in MR.REPORT_TYPE_MENU
                            if MR.report_type_is_built(t)
                            and t != opening[0]]
    # After the opening set, the set that asks the MOST, so every tagged pair
    # names the same one and a reader changes the pulldown once, not three
    # times. `sorted` is stable, so a tie keeps the window's own order.
    for tid in types:
        sets = sorted(CS.selectable_set_ids({}),
                      key=lambda sid: -len(PE.rows_asked(tid, sid)))
        for sid in ([opening[1]] if tid == opening[0] else []) + sets:
            asked = PE.rows_asked(tid, sid)
            if all(rid in asked for rid in r.rows):
                return tid, sid
    raise SystemExit(f"{r.key}: no report type and limit set asks "
                     f"{', '.join(r.rows)}, so no window can show this pair")


def where_words(r: "Requirement") -> str:
    """The choice to make in the window for requirement *r*'s pair to show,
    in the window's own words, or "" when the window opens on it."""
    from workflow.compliance_sets import SET_BY_ID
    from workflow.measurement_report import report_type_name
    tid, sid = shown_under(r)
    if (tid, sid) == opening_choice():
        return ""
    words = SET_BY_ID[sid].label
    if tid != opening_choice()[0]:
        words = f"{report_type_name(tid)}, {words}"
    return words


def where_label(r: "Requirement") -> str:
    """The tag a preset NAME carries when its pair does not show under the
    window's opening choice, or "". In the name, because the name is the one
    thing the window's list shows before anything is clicked."""
    words = where_words(r)
    return f" [judge with {words}]" if words else ""


def _build_demos() -> "tuple[Demo, ...]":
    out = [Demo(0, "Verify 00 control, every row answered",
                "The control. Every row a patch set can decide is answered, "
                "so a reader can see that the shortfalls below are the charts "
                "and not the window.",
                kind="control", chart=chart_control, keywords=strip_ids(20))]
    n = 1
    for r in REQUIREMENTS:
        where = where_label(r)
        look = ""
        if where:
            look = (f" ChromIQ's own limit sets put no number on this "
                    f"metric, so the window asks about it only when "
                    f"'Judged against' is {where_words(r)}; under the choice "
                    f"it opens on, this preset and its pair read the same.")
        out.append(Demo(
            n, f"Verify {r.key} FAIL, {r.fail_label}{where}",
            f"{r.metric}. {r.text} This preset is one notch outside that "
            f"line: {r.fail_label}.{look}",
            kind="FAIL", key=r.key, reason=r.reason, rows=r.rows, also=r.also,
            comparison=r.comparison, source=r.source,
            chart=r.fail_chart, keywords=dict(r.fail_keywords),
            scale=r.scale))
        n += 1
        out.append(Demo(
            n, f"Verify {r.key} PASS, {r.pass_label}{where}",
            f"{r.metric}. The same chart exactly on the line: "
            f"{r.pass_label}. The rows the preset above withholds are "
            f"answered here, and nothing else changes.{look}",
            kind="PASS", key=r.key, reason="", rows=r.rows, also=r.also,
            comparison=r.comparison, source=r.source,
            chart=r.pass_chart, keywords=dict(r.pass_keywords),
            scale=r.scale))
        n += 1
    out += [
        # K43: the largest demo, two pages, every row a preset can decide
        # answered, the evenness pair included.
        Demo(n, "Verify L1 control, 650 patches on two pages, every row "
                "answered",
             "The control at size: 650 patches, which printtarg lays out as "
             "two A4 pages for an i1Pro (24 strips and 7 strips). It answers "
             "every row a patch set can decide, the two evenness rows "
             "included, which no 78-patch preset can.",
             kind="control", chart=lambda: chart_page(650),
             keywords=strip_ids(20)),
        # Q1, the grey ramp clumped at the light end, became R14 when Knut
        # ruled the spacing rule for the grey ramp (#182 B8-483, 2026-09-23),
        # and Q2, the tone ramp clumped the same way, became R15 when he
        # ruled it for that ramp too (K31, #182 5801677743).
        Demo(n + 1, "Verify X1 other, settings only, no patch set",
             "A preset saved with the attach tick box OFF. Not a metric: it "
             "is the one state in which the window can say nothing about a "
             "preset, and it must say which tick box fixes it.",
             kind="other", no_chart=True),
        Demo(n + 2, "Verify X2 other, the patch set cannot be read",
             "A .ti1 beside the preset that is not a chart. Not a metric "
             "either: the other half of \"Cannot be checked\".",
             kind="other", corrupt=True, chart=chart_control),
    ]
    return tuple(out)


DEMOS: "tuple[Demo, ...]" = _build_demos()

REQ_BY_KEY: "dict[str, Requirement]" = {r.key: r for r in REQUIREMENTS}


def pairs() -> "list[tuple[Requirement, Demo, Demo]]":
    """(requirement, its FAIL preset, its PASS preset), in table order."""
    out = []
    for r in REQUIREMENTS:
        f = next(d for d in DEMOS if d.key == r.key and d.kind == "FAIL")
        p = next(d for d in DEMOS if d.key == r.key and d.kind == "PASS")
        out.append((r, f, p))
    return out


#: The reason codes NO patch set can provoke in this window, and why. Written
#: down because a pack that covers ten codes has to say what happened to the
#: other four.
UNREACHABLE: "dict[str, str]" = {
    "needs_reference_file":
        "It is the STATE OF EVERY PRESET, not a fault in one. A preset chart "
        "is printed through its profile as a verification, so its solids "
        "are not the printer's own (only a chart built FROM PROFILE GAMUT "
        "prints them raw), and the two solid rows read this code on all "
        "built-ins and on all of these demos. A preset cannot cause it and "
        "cannot avoid it. (Since K49 the paper row is answered by any chart "
        "with a patch printed with no ink; R17 is its pair.)",
    "no_reference":
        "Unreachable by construction. The stand-in report gives every sample "
        "id an aim value (preset_eligibility._perfect_print), so no block can "
        "ever find a patch without one. It is reachable in a REAL report, "
        "where the reference comes from a .ti2 that need not cover every "
        "sample, which is why two of its branches are worth reading twice.",
    "no_corners":
        "On the colorimetric branch of row_values only, which an unprinted "
        "preset never takes: it needs a reference file, which is the code "
        "above.",
    "not_computed":
        "Means 'this report predates the block', so it can only come out of a "
        "SAVED report read back. The stand-in report is built fresh and "
        "always carries every block.",
    # K31 option (a): the grey rows of a FROM PROFILE GAMUT chart, whose grey
    # steps are its neutral aims. A preset is never such a chart.
    "too_few_neutral_aims":
        "Only a chart built FROM PROFILE GAMUT has neutral aims, and no preset "
        "is one: the Create Chart tab's current chart line and the report "
        "itself show this code, never a preset.",
    "neutral_aims_bunched": "As the code above.",
    "neutral_aims_no_white": "As the code above.",
    "neutral_aims_no_black": "As the code above.",
    # K40-2: the 30 to 70 % tone row of such a chart, on its neutral aims.
    "ramp_too_few_neutral_aims": "As the code above.",
    "ramp_neutral_aims_bunched": "As the code above.",
    "no_device_values":
        "A measurement file with no device columns (B8-845). Every preset is "
        "a chart of device values, and the stand-in report is built from "
        "them, so no preset can carry this code.",
    # EVENNESS ACROSS THE SHEET (#182, 2026-09-22). Since K40-1 the window
    # lays every preset out behind the scenes, so one of these is the state
    # of every demo here and the rest need a page no 78-patch chart has.
    "evenness_laid_out_later":
        "Only a caller that hands the window no layout at all. Since K40-1 "
        "the window gives every preset the layout Generate would give it "
        "(the layout engine's arithmetic, or printtarg run behind the "
        "scenes), so no preset in the window reads it.",
    "evenness_laying_out":
        "Transient: a printtarg preset whose layout the background thread "
        "has not finished yet. The window shows the row as working and "
        "re-reads it when the layout arrives, so a finished window never "
        "shows it.",
    "evenness_layout_no_tool":
        "Needs ArgyllCMS's printtarg to be missing from the folder "
        "Preferences names. A demo cannot remove it.",
    "evenness_layout_refused":
        "Needs printtarg to refuse a preset. Every demo here was refused "
        "until K40-1 (their .ti1 held only the colours, without the two "
        "tables printtarg needs); since the tables are written, none is.",
    "evenness_no_layout":
        "Needs a MEASURED sheet with no chart file beside it. A preset is a "
        "chart file.",
    "evenness_no_positions":
        "Needs a laid-out chart whose patch locations cannot be read, which a "
        "printtarg preset is not until it is laid out.",
    "evenness_grid_too_small":
        "It is the STATE OF EVERY 78-PATCH DEMO HERE since K40-1, like the "
        "reference code above: laid out by printtarg on A4 for an i1Pro, 78 "
        "patches fill 3 strips, and both evenness rows want 9 strips and 9 "
        "rows. The larger demos of K43 (R16 and L1) have 24 to 31 strips.",
    "evenness_empty_area":
        "Needs a page of at least 9 by 9 whose patches leave a ninth of it "
        "empty, which a chart filled strip by strip cannot do.",
    "evenness_noisy_pairwise":
        "Needs the page grid (see grid_too_small); shown by the built-in "
        "engine presets of one page and 140 to 200 patches.",
    "evenness_noisy_from_mean":
        "As the row above.",
    # #182 E2 (Knut, 2026-09-23): the page-coverage floor. K43: no longer
    # here, it is R16's FAIL side.
    "evenness_no_page_geometry":
        "Needs a laid-out chart with no engine geometry, no page image and no "
        "derived rectangles beside it. A printtarg preset has no page grid "
        "yet, so it stops at laid_out_later first.",
}

#: Of the codes above, the ones the window DOES show, on the built-in engine
#: presets whose page grid the layout engine's own arithmetic predicts. Not by
#: any demo here, so they stay in UNREACHABLE; the test asserts they really
#: appear, which is stronger than asserting they do not.
SHOWN_BY_BUILTINS: "frozenset[str]" = frozenset({
    "evenness_noisy_pairwise",
    "evenness_noisy_from_mean",
})


# ---------------------------------------------------------------------------
# The preset payload
# ---------------------------------------------------------------------------
def payload(attached: bool, scale: float = 1.0) -> dict:
    """A Create Chart preset's stored values.

    Deliberately small: these presets exist to be assessed, and every key they
    do not carry is a setting the user's own tab keeps. ``attached_ti1`` is the
    one the window reads.
    """
    return {
        "targen_-d": "2",
        "printtarg_-i": "i1",
        "printtarg_-p": "A4",
        "printtarg_-t": 300,
        "printtarg_-L": True,
        "printtarg_-a": float(scale),
        # K43 (Knut, #182 5833695633): the seed printtarg lays the chart out
        # with, so every Generate of the preset puts every patch in the same
        # place, as a user printing one verification chart for every dated
        # check does. The pack's one seed (`make_report_limit_demos.
        # PRINTTARG_SEED`).
        "printtarg_-R": PRINTTARG_SEED,
        "printtarg_-R_enabled": True,
        "tiff_16bit": False,
        "auto_patches": False,
        "auto_grey": False,
        "auto_white": False,
        "auto_black": False,
        "pages": 1,
        "left_clip_info": False,
        "triple_density": False,
        "chart_notes": "",
        "stamp_commands": False,
        "auto_run": False,
        "attached_ti1": attached,
    }


def _sanitize(name: str) -> str:
    from core.preset_store import _sanitize as s
    return s(name)


def build(dest: Path) -> "list[tuple[Demo, Path | None]]":
    """Write every demo preset into *dest*. Returns (demo, chart path)."""
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for d in DEMOS:
        stem = _sanitize(d.name)
        doc = {"chromiq_preset_version": 1, "tab": TAB, "name": d.name,
               "data": payload(not d.no_chart, d.scale)}
        (dest / (stem + ".json")).write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        chart = None
        if d.no_chart:
            pass
        elif d.corrupt:
            chart = dest / (stem + ".ti1")
            chart.write_text(
                "This file is deliberately not a chart. This preset exists to "
                "show what the window says about a preset whose patch set it "
                "cannot read.\n", encoding="utf-8")
        else:
            chart = dest / (stem + ".ti1")
            write_ti1(chart, d.chart(), keywords=d.keywords,
                      descriptor=d.name)
        out.append((d, chart))
    (dest / "README.txt").write_text(readme(), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# What the window really says about each one
# ---------------------------------------------------------------------------
#: The one code every preset carries and no preset causes. Excluded everywhere
#: a claim is checked, because it is the background and not the picture.
CONSTANT = "needs_reference_file"
#: …and, since the evenness rows became computable (#182, 2026-09-22), a
#: second such code. It was "laid out later" until K40-1, because the window
#: did not lay a printtarg preset out. The evenness boundaries are
#: demonstrated on laid-out charts (the report demo pack's
#: Report-Limits-Evenness project and tests/test_evenness_across_the_sheet.py).
#:
#: **K40-1 (Knut, #182 5832026677): THE WINDOW NOW LAYS EACH DEMO OUT**, with
#: printtarg behind the scenes, exactly as Generate would lay it out, so the
#: second constant is no longer "laid out later" but what that layout shows:
#: 78 patches fill 3 i1Pro strips on an A4 page, and both evenness rows want
#: 9 strips and 9 rows. Still the background, and still not the picture.
CONSTANTS = (CONSTANT, "evenness_grid_too_small")


def layout(chart: "Path | None" = None) -> dict:
    """The layout a demo here is judged with: the one the presets window
    gives a preset saved with these settings
    (`preset_layout.layout_for_user_preset`), printtarg from ArgyllCMS's
    usual folder or from ``CHROMIQ_ARGYLL_BIN``. Read from the preset saved
    beside *chart* when there is one (K43: R16 is saved with its own patch
    size), otherwise the pack's own settings."""
    from core.platform_paths import default_argyll_bin_dir
    from workflow.preset_layout import layout_for_user_preset
    argyll = os.environ.get("CHROMIQ_ARGYLL_BIN", default_argyll_bin_dir())
    settings = {"argyll_bin_path": argyll}
    data = payload(True)
    if chart is not None:
        try:
            doc = json.loads(Path(chart).with_suffix(".json")
                             .read_text(encoding="utf-8"))
            data = dict(doc.get("data") or data)
        except (OSError, ValueError):
            pass
    return layout_for_user_preset(data, lambda k, d=None: settings.get(k, d))


def assess(chart: "Path | None") -> "dict[str, str]":
    """``{row_id: reason}`` for every row this chart cannot answer, through the
    app's own eligibility path, laid out as the window lays it out."""
    from workflow import preset_eligibility as PE
    from workflow.ti3_analysis import Ti3ParseError
    if chart is None:
        return {"": "no chart"}
    try:
        values = PE.chart_row_values(chart, layout(chart), lay_out=True)
    except (Ti3ParseError, OSError) as exc:
        return {"": f"unreadable: {exc}"}
    return {rid: (v.get("reason") or "")
            for rid, v in values.items() if v.get("value") is None}


def withheld(chart: "Path | None") -> "dict[str, str]":
    """The same, without the code every preset carries, and only over the
    metrics the window can ever ASK.

    ChromIQ's two repeatability rows are computed for every chart and asked by
    no combination in the window (`preset_eligibility.rows_asked` leaves out
    `POPULATION_MAY_BE_ABSENT`: "has this chart been measured before" is not
    a property of a chart). Counting them here made `--check` report sixteen
    of thirty-one presets as not doing what they claim, about two rows no
    reader of the window ever sees.
    """
    from workflow import preset_eligibility as PE
    askable = set(PE.rows_any_report_can_ask())
    return {rid: why for rid, why in assess(chart).items()
            if why not in CONSTANTS and (rid in askable or rid == "")}


def in_the_window(chart: "Path | None", r: "Requirement") -> "dict[str, str]":
    """What the WINDOW withholds from *chart*, under the choice requirement
    *r*'s pair names: `preset_eligibility.assess`, the window's own call."""
    from workflow import preset_eligibility as PE
    from workflow.ti3_analysis import Ti3ParseError
    tid, sid = shown_under(r)
    if chart is not None:
        try:
            # laid out first, here and now, as the window's own background
            # thread would have done by the time anybody reads the row
            PE.chart_row_values(chart, layout(chart), lay_out=True)
        except (Ti3ParseError, OSError):
            pass
    a = PE.assess(chart, tid, sid, recipe=layout(chart))
    return {rid: why for rid, why in a.missing if why not in CONSTANTS}


def check(dest: Path) -> int:
    """Build, assess, and say whether each preset does exactly what it claims.

    Three claims per pair, all measured:

    1. the FAIL preset withholds its requirement's rows, with its own code;
    2. the PASS preset answers them;
    3. **nothing else moves.** Every other row reads the same on both sides.
       That is what makes the pair evidence about one requirement instead of
       an observation about two charts.
    """
    build(dest)
    bad = 0

    def chart_of(d):
        stem = _sanitize(d.name)
        return None if d.no_chart else dest / (stem + ".ti1")

    for r, f, p in pairs():
        got_f, got_p = withheld(chart_of(f)), withheld(chart_of(p))
        want_f = {rid: r.reason for rid in r.rows}
        problems = []
        for rid, code in want_f.items():
            if got_f.get(rid) != code:
                problems.append(f"FAIL {rid}: want {code}, got "
                                f"{got_f.get(rid) or 'answered'}")
            if rid in got_p:
                problems.append(f"PASS {rid}: still withheld ({got_p[rid]})")
        moved = {rid for rid in set(got_f) | set(got_p)
                 if rid not in r.rows and got_f.get(rid) != got_p.get(rid)}
        for rid in sorted(moved):
            problems.append(f"NOT ISOLATED {rid}: {got_f.get(rid)} vs "
                            f"{got_p.get(rid)}")
        constant = sorted({c for rid, c in got_f.items() if rid not in r.rows})
        if constant != sorted(set(r.also)):
            problems.append(f"also: want {sorted(set(r.also))}, got {constant}")
        # AND IN THE WINDOW, under the choice the preset's own name gives
        # (K15). A pair that differs only on rows the window is not asking
        # shows nothing, which is what Knut saw.
        win_f = in_the_window(chart_of(f), r)
        win_p = in_the_window(chart_of(p), r)
        for rid in r.rows:
            if win_f.get(rid) != r.reason:
                problems.append(f"WINDOW FAIL {rid}: want {r.reason} under "
                                f"{shown_under(r)}, got "
                                f"{win_f.get(rid) or 'answered'}")
            if rid in win_p:
                problems.append(f"WINDOW PASS {rid}: withheld under "
                                f"{shown_under(r)} ({win_p[rid]})")
        tag = where_label(r)
        print(f"       shows under {shown_under(r)}"
              + (f" (named in the preset:{tag})" if tag
                 else " (the choice the window opens on)"))
        bad += 1 if problems else 0
        print(f"{'ok ' if not problems else 'BAD'} {r.key}  {r.metric}")
        print(f"       {r.comparison}")
        print(f"       FAIL {f.name}")
        print(f"            withholds {sorted(got_f.items()) or 'nothing'}")
        print(f"       PASS {p.name}")
        print(f"            withholds {sorted(got_p.items()) or 'nothing'}")
        for line in problems:
            print(f"       !! {line}")

    for d in DEMOS:
        if d.kind not in ("control", "open"):
            continue
        got = withheld(chart_of(d))
        ok = not got
        bad += 0 if ok else 1
        print(f"{'ok ' if ok else 'BAD'} {d.kind:8} {d.name}")
        if got:
            print(f"       !! withholds {sorted(got.items())}")
    print(f"\n{len(REQUIREMENTS)} requirements, {len(DEMOS)} presets, "
          f"{bad} not doing what they claim.")
    return 1 if bad else 0


def grid(dest: Path) -> int:
    """The FAIL-against-PASS table, measured, one line per requirement."""
    build(dest)

    def chart_of(d):
        return None if d.no_chart else dest / (_sanitize(d.name) + ".ti1")

    print(f"{'req':4} {'metric':34} {'comparison':58} {'FAIL':26} PASS")
    for r, f, p in pairs():
        gf = sorted({c for c in withheld(chart_of(f)).values()})
        gp = sorted({c for c in withheld(chart_of(p)).values()})
        print(f"{r.key:4} {r.metric[:34]:34} {r.comparison[:58]:58} "
              f"{','.join(gf)[:26]:26} {','.join(gp) or '(nothing)'}")
    return 0


# ---------------------------------------------------------------------------
# The README a user downloads
# ---------------------------------------------------------------------------
def readme() -> str:
    # **THE BUTTON'S NAME IS ASKED FOR, NOT TYPED (R29-F1).** Knut renamed it
    # in beta 25 and asked for the new name *"in all help text … and any other
    # place where this button is mentioned in text"*; this README is such a
    # place, and it went on naming the old button because nothing here read
    # the constant the window itself uses.
    from workflow.control_strip import ELIGIBILITY_CONTROL
    title = f'ChromIQ demo presets for "{ELIGIBILITY_CONTROL}"'
    lines = [title, "=" * len(title), ""]
    lines += _wrap(
        "Each preset in this folder is a Create Chart preset with its own "
        "patch set (.ti1) attached. They come in PAIRS: for each requirement "
        "the verification check applies, one chart sits one notch OUTSIDE "
        "that line and one sits exactly ON it. Everything else about the two "
        "charts is the same, so the rows that change between them are the "
        "rows that requirement decides, and nothing else.", 76)
    lines += ["", "WHERE THE FOLDER IS", "-" * 19, "",
              "  macOS    ~/Library/Preferences/ChromIQ/presets/Create Chart",
              "  Windows  %APPDATA%\\ChromIQ\\presets\\Create Chart",
              "  Linux    ~/.config/ChromIQ/presets/Create Chart", ""]
    lines += _wrap(
        "Copy the .json AND the .ti1 of each preset: they travel as a pair "
        "and the .ti1 is the patch set the window reads. ChromIQ reads the "
        "folder once at start-up, so RESTART THE APP after copying. Delete "
        "them the same way, or from the minus button beside the dropdown.", 76)
    lines += ["", "WHICH LIMIT SET TO CHOOSE IN THE WINDOW", "-" * 39, ""]
    tagged = sorted({where_words(r) for r in REQUIREMENTS if where_words(r)})
    lines += _wrap(
        "The window judges a chart only against the metrics the chosen report "
        "type and limit set ask for. It opens on ChromIQ's own default set, "
        "which asks about the grey balance and the colour differences and "
        "nothing else, so a pair about any other metric reads the SAME on both "
        "presets there: nothing is missing because nothing is asked. Those "
        "presets carry the choice that shows them in their names, in square "
        "brackets: set 'Judged against' to "
        + (" or ".join(tagged) if tagged else "the set named")
        + " and the FAIL preset of each pair names what it lacks while its "
        "PASS preset does not.", 76)
    lines += ["", "THE REQUIREMENTS, AND WHERE EACH LINE IS DRAWN", "-" * 46,
              ""]
    lines += _wrap(
        "The comparison beside each one is copied from ChromIQ's own source, "
        "because a boundary without its operator is a guess: \"at least 8 "
        "steps\" fails at 7 and passes at 8, and \"within 1 unit\" passes AT "
        "1 only because the comparison is <=.", 76)
    lines.append("")
    for r, f, p in pairs():
        lines.append(f"  {r.key}  {r.metric}")
        for ln in _wrap(r.text, 70):
            lines.append("      " + ln)
        lines.append(f"      the line:  {r.comparison}")
        lines.append(f"      read from: {r.source}")
        lines.append(f"      FAIL       {f.name}")
        lines.append(f"      PASS       {p.name}")
        lines.append(f"      the rows it decides: "
                     f"{', '.join(r.rows)}")
        words = where_words(r)
        lines.append("      shows with: "
                     + (f"'Judged against' set to {words}" if words
                        else "the choice the window opens on"))
        if r.also:
            for ln in _wrap("and on BOTH sides of this pair, unavoidably: "
                            + ", ".join(sorted(set(r.also))) + ". "
                            + r.also_why, 70):
                lines.append("      " + ln)
        lines.append("")
    _others = [d for d in DEMOS if d.kind in ("control", "open", "other")]
    _head = f"THE OTHER {_NUMBER_WORDS.get(len(_others), str(len(_others))).upper()} PRESETS"
    lines += [_head, "-" * len(_head), ""]
    for d in DEMOS:
        if d.kind not in ("control", "open", "other"):
            continue
        lines.append(f"  {d.name}")
        for ln in _wrap(d.blurb, 70):
            lines.append("      " + ln)
        lines.append("")
    lines += ["WHAT NO PRESET CAN FAIL", "-" * 23, ""]
    from workflow import preset_eligibility as _PE
    _codes = len(_PE.classified_reasons())
    lines += _wrap(
        f"The window has {_codes} reason codes. These {len(UNREACHABLE)} "
        "cannot be provoked by any patch set, so no preset here claims to:",
        76)
    lines.append("")
    for code, why in UNREACHABLE.items():
        lines.append(f"  {code}")
        for ln in _wrap(why, 70):
            lines.append("      " + ln)
        lines.append("")
    _covered = len({r.reason for r in REQUIREMENTS}
                   | {c for r in REQUIREMENTS for c in r.also})
    lines += _wrap(
        f"The other {_covered} are the codes these presets cover, between "
        "them. Note that a code is not a requirement: control_strip_too_small "
        "is two requirements (R02 and R03), too_few_surface_patches is two "
        "(R11 and R12), and no_ramp is two (R09 and R10). That is why this "
        f"pack is built around the {len(REQUIREMENTS)} requirements and not "
        f"around the {_covered} codes.", 76)
    lines.append("")
    return "\n".join(lines) + "\n"


_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


def _wrap(text: str, width: int) -> "list[str]":
    import textwrap
    return textwrap.wrap(" ".join(text.split()), width) or [""]


def main(argv=None) -> int:
    """Build the pack against the REPOSITORY'S OWN ISO file, and nothing else.

    THE DEMO PACK IS PUBLIC. Without this `compliance_sets` prefers a licence
    holder's own values file in ChromIQ's settings folder, and on a machine
    that holds one the Custom ISO columns bound into every demo run would
    start from those figures (#182 S-2, §23). Values the repository ships may
    appear in a demo; a licence holder's may not. FORCED for the call and put
    back afterwards, so a test that calls this leaves its worker as it was.
    """
    from workflow import compliance_sets as _cs
    key = "CHROMIQ_COMPLIANCE_ISO_FILE"
    before = os.environ.get(key)
    os.environ[key] = str(_HERE.parent / "data" / "compliance_sets"
                          / "iso12647.json")
    _cs.reset_iso_cache()
    try:
        return _main(argv)
    finally:
        if before is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = before
        _cs.reset_iso_cache()


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dest", nargs="?",
                    default=str(_HERE.parent / "demo-projects" / FOLDER))
    ap.add_argument("--check", action="store_true",
                    help="build, then assess each preset through the app's own "
                         "eligibility path and say what it really does")
    ap.add_argument("--grid", action="store_true",
                    help="the measured FAIL-against-PASS table, one line each")
    args = ap.parse_args(argv)
    dest = Path(args.dest).resolve()
    if args.check:
        return check(dest)
    if args.grid:
        return grid(dest)
    build(dest)
    print(f"{len(DEMOS)} demo presets written to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
