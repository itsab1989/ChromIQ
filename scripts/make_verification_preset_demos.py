#!/usr/bin/env python3
"""Create Chart presets built to FAIL one verification metric each (#182).

Knut, 2026-09-19:

    *"the demo package project must create a set of demo chart presets that are
    built to fail the metrics used during a verification. One test-preset made
    to fail one metric […] so if there are 17 metrics to test then make 17
    presets that is made to prove that the 'Which presets can be verified?'
    window works and detects which metric on a presets does not pass the
    criteria, and reports what is wrong/missing in the window. […] When the
    demo package then is released and downloadable, a user can place the
    presets in the '…/Library/Preferences/ChromIQ/presets/Create Chart' folder
    (on mac), and restart the app."*

**HOW MANY PRESETS, AND WHY NOT SEVENTEEN.** The window
(:mod:`ui.dialogs.preset_verification_dialog`) never invents a verdict: every
answer is :func:`workflow.measurement_report.row_values`' own, reached through
:mod:`workflow.preset_eligibility`. So the question "which metric can a preset
fail" is really "which REASON CODE can an unprinted patch set provoke", and
that is a smaller, countable set. :func:`workflow.preset_eligibility.classified_reasons`
knows fourteen codes. Ten of them a patch set can cause; four it cannot, and
the reasons are in ``UNREACHABLE`` below, written down rather than left as a
silent gap. Nine of the ten can be provoked ALONE. The tenth,
``small_sample``, cannot: see ``Demo.also`` on demo 11.

Every design here was measured, not reasoned about: ``--check`` builds each
patch set, runs the app's own eligibility path over it, and prints the reason
each row really came back with. That is the loop the numbers in the README came
out of.

No Qt in here, and no ArgyllCMS: a ``.ti1`` is CGATS text and these charts are
designed patch by patch, because a chart designed by ``targen`` is exactly the
chart that does NOT fail anything.
"""
from __future__ import annotations

import argparse
import json
import math
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
    lin = [ (max(0.0, min(100.0, v)) / 100.0) ** 2.2 for v in rgb ]
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _dedup(patches):
    """Keep the first of each device triple, order preserved."""
    seen, out = set(), []
    for p in patches:
        key = tuple(round(v, 4) for v in p)
        if key not in seen:
            seen.add(key)
            out.append(tuple(float(v) for v in p))
    return out


def cube(levels) -> "list[tuple[float, float, float]]":
    return [(r, g, b) for r in levels for g in levels for b in levels]


def greys(levels) -> "list[tuple[float, float, float]]":
    return [(v, v, v) for v in levels]


def ladder_patches() -> "list[tuple[float, float, float]]":
    """One patch at every rung of ChromIQ's own control-strip ladder."""
    from workflow.control_strip import SLOTS
    return [tuple(float(v) for v in s.device) for s in SLOTS]


# ---------------------------------------------------------------------------
# The charts
# ---------------------------------------------------------------------------
#: The base: a 5-level cube plus a long grey ramp. Everything a patch set can
#: answer, it answers. Each fault below is this chart with ONE thing taken away.
_BASE_LEVELS = (0.0, 25.0, 50.0, 75.0, 100.0)
_LONG_GREY = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
#: Three patches on the red axis (G = B = 100) at tone values 30, 50 and 70, so
#: a chart whose GREY ramp cannot carry the mid-tone row still has one axis
#: that can. Used by the two demos that take the grey ramp away.
_RED_AXIS_RAMP = [(70.0, 100.0, 100.0), (50.0, 100.0, 100.0), (30.0, 100.0, 100.0)]


def chart_control():
    return _dedup(cube(_BASE_LEVELS) + greys(_LONG_GREY))


def chart_no_greys():
    """Every neutral patch removed, and one coloured axis kept for the ramp."""
    keep = [p for p in cube(_BASE_LEVELS) if max(p) - min(p) > 1.0]
    return _dedup(keep + _RED_AXIS_RAMP)


def chart_too_few_steps():
    """Five grey levels, three short of the eight the ramp row wants."""
    return _dedup(cube(_BASE_LEVELS) + _RED_AXIS_RAMP)


def chart_no_white():
    """Nine grey levels, the lightest at 85: the ramp never reaches paper."""
    lv = (0.0, 5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 75.0, 80.0, 85.0)
    keep = [p for p in cube(_BASE_LEVELS) if not (p == (100.0, 100.0, 100.0))]
    return _dedup(keep + greys(lv))


def chart_no_black():
    """Ten grey levels, the darkest at 15: the ramp never reaches solid."""
    lv = (15.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)
    keep = [p for p in cube(_BASE_LEVELS) if not (p == (0.0, 0.0, 0.0))]
    return _dedup(keep + greys(lv))


def chart_no_ramp():
    """Twelve grey levels, and a hole from 26 % to 74 %: no axis has three
    steps inside the 30 to 70 % band."""
    lv = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 75.0, 80.0, 85.0, 90.0, 95.0, 100.0)
    return _dedup(cube(_BASE_LEVELS) + greys(lv))


def chart_too_few_surface():
    """Nothing within 2 % of a face of the device cube, so the surface-gamut
    population is empty.

    The grey ramp is the part that has to be watched: a five-level cube gives
    five neutral levels and the grey row then reads ``too_few_steps`` as well,
    which is what the first measured build of this chart did. Eight more
    neutrals, all of them well inside the cube, put it back to one fault. The
    ladder still fills, because every rung has a patch within its 12-unit
    tolerance.
    """
    inner_greys = (15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0)
    return _dedup(cube((10.0, 30.0, 50.0, 70.0, 90.0)) + greys(inner_greys))


def chart_too_few_outer():
    """Thirty-seven patches: the most saturated quarter holds ten, and the row
    wants twenty. Everything else is still answered, the whole control strip
    included."""
    return _dedup(ladder_patches() + greys(_LONG_GREY))


def chart_no_control_strip():
    """A chart that fills five of the ladder's twenty-nine rungs.

    The bulk sits inside the cube, 30 % away from every solid and every tint;
    the surface patches it needs are on the R = 0 face, far from the corners.
    Only paper, solid black and the three greys find a patch inside 12 units.
    """
    bulk = cube((30.0, 40.0, 50.0, 60.0, 70.0))
    ends = greys((0.0, 5.0, 95.0, 100.0)) + greys((38.0, 62.0))
    faces = [(0.0, g, b) for g in (40.0, 60.0) for b in (40.0, 60.0)]
    faces += [(r, 0.0, b) for r in (40.0, 60.0) for b in (40.0, 60.0)]
    faces += [(r, g, 0.0) for r in (40.0, 60.0) for g in (40.0, 60.0)]
    return _dedup(bulk + ends + faces)


def chart_small_sample():
    """Nineteen patches. See ``Demo.also``: this one cannot fail alone."""
    return _dedup(greys((0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0,
                         90.0, 100.0))
                  + [(0.0, 100.0, 100.0), (100.0, 0.0, 100.0),
                     (100.0, 100.0, 0.0), (100.0, 0.0, 0.0),
                     (0.0, 100.0, 0.0), (0.0, 0.0, 100.0),
                     (25.0, 100.0, 100.0), (100.0, 25.0, 100.0)])


# ---------------------------------------------------------------------------
# The demos
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Demo:
    """One preset, and the one thing it is built to fail."""
    n: int
    name: str
    #: what a reader should understand it proves, one sentence
    blurb: str
    #: the reason code the window must give it, or "" for the control
    reason: str = ""
    #: reason codes it ALSO fires, with why that is arithmetic and not sloppy
    also: "tuple[str, ...]" = ()
    chart: "Callable | None" = None
    keywords: "dict[str, str]" = field(default_factory=dict)
    #: write a .ti1 that cannot be parsed as a chart
    corrupt: bool = False
    #: write no .ti1 at all (a preset that stores settings only)
    no_chart: bool = False


def _strip_ids(k: int) -> "dict[str, str]":
    return {"CONTROL_STRIP_IDS": " ".join(str(i) for i in range(1, k + 1))}


DEMOS: "tuple[Demo, ...]" = (
    Demo(0, "Verify demo 00, everything passes",
         "The control. Every row a patch set can decide is answered, so a "
         "reader can see that the faults below are the charts and not the "
         "window.", chart=chart_control),
    Demo(1, "Verify demo 01, no grey patches",
         "No neutral patch at all, so the two grey-balance rows have nothing "
         "to average.", reason="no_greys", chart=chart_no_greys),
    Demo(2, "Verify demo 02, grey ramp too short",
         "Five grey levels where the row wants eight.",
         reason="too_few_steps", chart=chart_too_few_steps),
    Demo(3, "Verify demo 03, grey ramp stops short of white",
         "Eight grey levels and more, but the lightest is 85 %, so the ramp "
         "never reaches paper.", reason="no_white", chart=chart_no_white),
    Demo(4, "Verify demo 04, grey ramp stops short of black",
         "The same the other way up: the darkest neutral is 15 %.",
         reason="no_black", chart=chart_no_black),
    Demo(5, "Verify demo 05, no mid-tone ramp",
         "A long grey ramp with a hole in it from 26 % to 74 %, and no "
         "single-ink axis with three steps in the 30 to 70 % band.",
         reason="no_ramp", chart=chart_no_ramp),
    Demo(6, "Verify demo 06, too few surface patches",
         "133 patches, none of them within 2 % of a face of the device "
         "cube, so the surface-gamut population is empty.",
         reason="too_few_surface_patches", chart=chart_too_few_surface),
    Demo(7, "Verify demo 07, too few outer-gamut patches",
         "Thirty-seven patches: the most saturated quarter holds ten and the "
         "row wants twenty.",
         reason="too_few_outer_patches", chart=chart_too_few_outer),
    Demo(8, "Verify demo 08, no control strip",
         "A patch set that fills five of the twenty-nine rungs of ChromIQ's "
         "ladder, so no control strip can be declared for it.",
         reason="no_control_strip", chart=chart_no_control_strip),
    Demo(9, "Verify demo 09, declared control strip too short",
         "The control chart, with a CONTROL_STRIP_IDS keyword naming five "
         "patches. A declaration ChromIQ must not overrule, and five is under "
         "the eight an average needs.",
         reason="control_strip_too_small", chart=chart_control,
         keywords=_strip_ids(5)),
    Demo(10, "Verify demo 10, control strip too short for the 95th percentile",
         "The same declaration at twelve patches: enough for the average and "
         "the largest, three short of the twenty the 95th percentile needs. "
         "The same reason code on ONE row instead of three.",
         reason="control_strip_too_small", chart=chart_control,
         keywords=_strip_ids(12)),
    Demo(11, "Verify demo 11, too few patches",
         "Nineteen patches, one short of the twenty a worst twentieth needs.",
         reason="small_sample",
         also=("too_few_outer_patches", "control_strip_too_small"),
         chart=chart_small_sample),
    Demo(12, "Verify demo 12, settings only, no patch set",
         "A preset saved with the attach tick box OFF. Not a metric: it is "
         "the one state in which the window can say nothing about a preset, "
         "and it must say which tick box fixes it.", no_chart=True),
    Demo(13, "Verify demo 13, the patch set cannot be read",
         "A .ti1 beside the preset that is not a chart. Not a metric either: "
         "the other half of \"Cannot be checked\".",
         corrupt=True, chart=chart_control),
)


#: The reason codes NO patch set can provoke in this window, and why. Written
#: down because a demo package that ships nine presets for fourteen codes has
#: to say what happened to the other five, and four of them are these.
UNREACHABLE: "dict[str, str]" = {
    "needs_reference_file":
        "It is the STATE OF EVERY PRESET, not a fault in one. A preset chart "
        "carries no colorimetric reference (only a chart built FROM PROFILE "
        "GAMUT does), so the three reference rows read this code on all 177 "
        "built-ins and on all of these demos. A preset cannot cause it and "
        "cannot avoid it.",
    "no_reference":
        "Unreachable by construction. The stand-in report gives every sample "
        "id an aim value (preset_eligibility._perfect_print), so no block can "
        "ever find a patch without one.",
    "no_corners":
        "On the colorimetric branch of row_values only, which an unprinted "
        "preset never takes: it needs a reference file, which is the code "
        "above.",
    "not_computed":
        "Means 'this report predates the block', so it can only come out of a "
        "SAVED report read back. The stand-in report is built fresh and "
        "always carries every block.",
}


# ---------------------------------------------------------------------------
# The preset payload
# ---------------------------------------------------------------------------
def payload(attached: bool) -> dict:
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
        "printtarg_-a": 1.0,
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
               "data": payload(not d.no_chart)}
        (dest / (stem + ".json")).write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        chart = None
        if d.no_chart:
            pass
        elif d.corrupt:
            chart = dest / (stem + ".ti1")
            chart.write_text(
                "This file is deliberately not a chart. Verify demo 13 exists "
                "to show what the window says about a preset whose patch set "
                "it cannot read.\n", encoding="utf-8")
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
def assess(chart: "Path | None") -> "dict[str, str]":
    """``{row_id: reason}`` for every row this chart cannot answer, through the
    app's own eligibility path."""
    from workflow import preset_eligibility as PE
    from workflow.ti3_analysis import Ti3ParseError
    if chart is None:
        return {"": "no chart"}
    try:
        values = PE.chart_row_values(chart)
    except (Ti3ParseError, OSError) as exc:
        return {"": f"unreadable: {exc}"}
    return {rid: (v.get("reason") or "")
            for rid, v in values.items() if v.get("value") is None}


def check(dest: Path) -> int:
    """Build, assess, and say whether each demo fails exactly what it claims."""
    from workflow import preset_eligibility as PE
    rows = build(dest)
    bad = 0
    for d, chart in rows:
        got = assess(chart)
        codes = sorted({c for c in got.values() if c})
        patch_codes = sorted({c for c in codes if PE.is_patch_shortfall(c)
                              or c in ("no_control_strip",
                                       "control_strip_too_small")})
        want = sorted({d.reason} | set(d.also)) if d.reason else []
        ok = patch_codes == want
        bad += 0 if ok else 1
        print(f"{'ok ' if ok else 'BAD'} {d.n:>2} {d.name}")
        print(f"       want {want or ['(nothing)']}")
        print(f"       got  {patch_codes or ['(nothing)']}")
        if not ok:
            for rid, code in sorted(got.items()):
                print(f"          {rid:36} {code}")
    print(f"\n{len(rows) - bad} of {len(rows)} demos fail exactly what they claim.")
    return 1 if bad else 0


def readme() -> str:
    from workflow import preset_eligibility as PE
    title = "ChromIQ demo presets for \"Which presets can be verified?\""
    lines = [title, "=" * len(title), ""]
    lines += _wrap(
        "Each preset in this folder is a Create Chart preset with its own "
        "patch set (.ti1) attached, and each one is built to fall short of "
        "exactly one of the checks the \"Which presets can be verified?\" "
        "window applies. Copy the whole contents of this folder into your "
        "own Create Chart presets folder, restart ChromIQ, and they appear in "
        "the preset dropdown on the Create Chart tab and in that window.", 76)
    lines += ["", "WHERE THE FOLDER IS", "-" * 19, "",
              "  macOS    ~/Library/Preferences/ChromIQ/presets/Create Chart",
              "  Windows  %APPDATA%\\ChromIQ\\presets\\Create Chart",
              "  Linux    ~/.config/ChromIQ/presets/Create Chart", ""]
    lines += _wrap(
        "Copy the .json AND the .ti1 of each preset: they travel as a pair "
        "and the .ti1 is the patch set the window reads. ChromIQ reads the "
        "folder once at start-up, so RESTART THE APP after copying. Delete "
        "them the same way, or from the minus button beside the dropdown.", 76)
    lines += ["", "WHAT EACH ONE IS FOR", "-" * 20, ""]
    for d in DEMOS:
        lines.append(f"  {d.name}")
        for ln in _wrap(d.blurb, 72):
            lines.append("      " + ln)
        if d.reason:
            lines.append(f"      window's reason code: {d.reason}")
        for extra in d.also:
            lines.append(f"      and, unavoidably: {extra}")
        lines.append("")
    lines += ["WHAT NO PRESET CAN FAIL", "-" * 23, ""]
    lines += _wrap(
        "The window has fourteen reason codes. These four cannot be provoked "
        "by any patch set, so no preset here claims to:", 76)
    lines.append("")
    for code, why in UNREACHABLE.items():
        lines.append(f"  {code}")
        for ln in _wrap(why, 72):
            lines.append("      " + ln)
        lines.append("")
    lines += _wrap(
        f"The remaining ten are the ten these presets cover. Nine of them are "
        f"provoked alone. The tenth, small_sample, cannot be: a chart with "
        f"under twenty patches also has under twenty in its most saturated "
        f"quarter and under twenty on its control strip, so demo 11 shows "
        f"three reasons and the arithmetic is why.", 76)
    lines.append("")
    return "\n".join(lines) + "\n"


def _wrap(text: str, width: int) -> "list[str]":
    import textwrap
    return textwrap.wrap(" ".join(text.split()), width) or [""]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dest", nargs="?",
                    default=str(_HERE.parent / "demo-projects" / FOLDER))
    ap.add_argument("--check", action="store_true",
                    help="build, then assess each preset through the app's own "
                         "eligibility path and say what it really fails")
    args = ap.parse_args(argv)
    dest = Path(args.dest).resolve()
    if args.check:
        return check(dest)
    build(dest)
    print(f"{len(DEMOS)} demo presets written to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
