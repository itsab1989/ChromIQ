#!/usr/bin/env python3
"""Build the Measurement Report limit demo projects (#182, Knut 2026-09-08).

    *"Claude needs to make very extensive demo test projects with several runs
    and where each run has various verification runs. All with real data, real
    simulated measurements (fakeread?) and various chart sizes for each profile
    run, and the chart run used for each profile run. Some runs must only have
    one verification run, so that settings can be changed. Some runs must have
    many verification runs, where the various profile runs for the verification
    uses different report types and 'judged against' thresholds. The
    measurements must be designed so that every threshold in a report is being
    triggered, maximum two thresholds simultaneously, and then also making
    measurement value reduce after triggering so that values go below
    thresholds again."*

This is a SEPARATE generator from ``scripts/make_demo_projects.py``. That one
feeds the test suite's session-scoped ``demo_projects_root`` fixture, is cached
on disk keyed by its own source, and editing it invalidates that cache for
every gate on every machine. Nothing here touches it.

What is built
-------------
**The counts live in `PROJECTS` and are not written down here.** This
paragraph used to name the number of projects, of profile runs and of dated
verifications, and by the time an adversarial round read it (2026-09-12) all
three were wrong and the list below named half the projects. `readme()` has
been forbidden to type a count it can compute since the round before that, by
`tests/test_the_demo_pack_covers_every_report_type.py`; the ban now covers this
docstring too, because a stale number is stale wherever it is written, and the
door that was guarded was not the one that went wrong.

Read `PROJECTS` for the current shape. In outline, what each project is for:

    Report-Limits-Threshold-Series   the dated series: each judged row crosses
                                     its limit on one date and recovers on the
                                     next. run1 has ELEVEN dated verifications,
                                     run3 has exactly ONE, so its
                                     limit set can still be chosen.
    Report-Limits-Isolated-Rows      rows that cannot cross alone under any
                                     shipped limit set, isolated by giving the
                                     run its own edited column. One of them is
                                     judged by no shipped set at all. run3 has
                                     TWO dated verifications with the lock
                                     lifted by hand.
    Report-Limits-Set-Compare        the same measurement, three times, judged
                                     by ChromIQ default / tight / Quick check.
    Report-Limits-Report-Types       one run per document type, and one run
                                     holding reports of three types at once,
                                     so the "Already generated for this run"
                                     line has something to count.
    Report-Limits-Report-Folders     where every kind of report lives (K23):
                                     one date, several dates of one run,
                                     across runs, profiling, a legacy report
                                     of several dates and a deleted one.
    Report-Limits-Report-Folders-Second
                                     a second project (K25), so "Report
                                     shown" is grouped by project and run;
                                     two reports span both projects and live
                                     in the pack's own reports/ folder.
    Report-Limits-Custom-Columns     the two Custom columns, with numbers.
    Report-Limits-Border-Conditions  the edges: a chart with no grey ramp, a
                                     raw sheet, a sheet with no printing
                                     record.
    Report-Limits-Profile-Gamut      a verification chart built by the app's
                                     own FROM PROFILE GAMUT module, which is
                                     the only chart that makes the three
                                     reference rows answerable at all.
    Report-Limits-Strip-And-Gamut    the five rows that had no detection until
                                     B8-397: a chart that declares its own
                                     control strip, the surface of the device
                                     cube, the most saturated quarter, and a
                                     chart that cannot supply the surface row.
    Report-Limits-Every-Limit-Set    Knut's matrix: every judgeable row against
                                     EVERY selectable limit set, over its limit
                                     on one date and inside it on the next, on
                                     both kinds of chart.
    Report-Limits-Paper-Classes      K29: five real paper classes (published
                                     facts, our values), each on its own
                                     chart, set, report type and printing.
    Report-Limits-Border-Values      K29: exactly on a limit, one thousandth
                                     over, one thousandth under, on four rows
                                     and sets; the saved value is checked.
    Report-Limits-Second-Route       K29: Knut's matrix again, on a different
                                     chart and paper per set.
    Report-Limits-Renamed            K29: built under another name, given a
                                     report across projects, then renamed.

`scripts/make_release_demo_package.py` puts these beside the evenness and
notes projects in ONE release package with a coverage matrix.

How the measurements are made
-----------------------------
Every chart is a real ArgyllCMS chart (``targen`` designs it, ``printtarg``
lays it out and renders the page TIFFs). Every profile is a real ``colprof``
profile built from a real ``fakeread`` measurement. Every dated verification
starts as a real ``fakeread`` of that run's verification chart through that
run's own profile.

Then a DESIGNED DRIFT is applied on top, patch by patch. Each patch keeps the
direction of the error fakeread actually produced through the real profile, and
only the MAGNITUDE is scaled so that the chart's statistics land exactly where
the date's design says they should. That is what makes "date X crosses row Y and
nothing else" a fact rather than a hope, and it is why the intended/actual table
in the README matches.

The alternative, ``fakeread -r`` random noise, moves every statistic at once and
can neither cross one row alone nor recover on cue.

Run it::

    .venv/bin/python scripts/make_report_limit_demos.py [destination] [--zip]

Default destination: ``demo-projects/ChromIQ-Report-Limit-Demos``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

import numpy as np

ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
SRGB = ARGYLL.parent / "ref" / "sRGB.icm"

#: Every Argyll call gets one. A `subprocess.run` without a timeout once sat on
#: a single `targen -G` for two and a half hours with no output.
TIMEOUT_TARGEN = 900
TIMEOUT_PRINTTARG = 600
TIMEOUT_FAKEREAD = 300
TIMEOUT_COLPROF = 900

FOLDER = "ChromIQ-Report-Limit-Demos"
INSTRUMENT = "X-Rite ColorMunki"
INSTRUMENT_I1 = "X-Rite i1Pro 2"


# ---------------------------------------------------------------------------
# Running Argyll
# ---------------------------------------------------------------------------
def run(cmd, cwd: Path, timeout: int) -> None:
    args = [str(c) for c in cmd]
    try:
        # `encoding=` and not the platform default: an Argyll tool that writes
        # a non-ASCII byte would otherwise decode differently on another
        # machine, and `tests/test_encoding_is_named.py` refuses a text call
        # site without one.
        r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"{args[0]} did not finish within {timeout} s in {cwd}. "
            f"Nothing was killed by an error; it simply never returned.")
    if r.returncode != 0:
        raise SystemExit(f"{args[0]} failed (exit {r.returncode}):\n"
                         f"{r.stdout}\n{r.stderr}")


# ---------------------------------------------------------------------------
# Charts and profiles
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ChartRecipe:
    """One chart size. ``grey`` and ``single`` keep the grey ramp and the
    30 to 70 % tone ramps eligible, which the report needs before it can put a
    number on the grey-balance rows at all."""
    patches: int
    grey: int
    single: int
    paper: str
    label: str
    #: printtarg's instrument (#182 K29): "CM" (ColorMunki, every chart
    #: before K29) or "i1" (i1Pro strips), so a rule is not only ever seen on
    #: one instrument's layout.
    instrument: str = "CM"

    @property
    def targen_args(self) -> list:
        return ["-d2", "-e4", "-B4", f"-g{self.grey}", f"-s{self.single}",
                f"-f{self.patches}"]


CHART_SMALL = ChartRecipe(105, 12, 8, "A4", "105 patches on A4")
CHART_MEDIUM = ChartRecipe(210, 16, 12, "A4", "210 patches on A4")
CHART_LARGE = ChartRecipe(400, 20, 16, "A4", "400 patches on A4")
CHART_WIDE = ChartRecipe(156, 14, 10, "A3", "156 patches on A3")

#: A chart with NO grey ramp and no single-colour ramps, which is what most
#: real charts look like. The grey-balance rows then read N-A (two distinct
#: levels, and the row needs eight), and a Grey and tone check on it has
#: nothing left to judge. That is the state `SUMMARY_REASONS["nothing_checked"]`
#: was written for, and until this recipe existed no demo reached it.
CHART_NO_GREY = ChartRecipe(90, 0, 0, "A4", "90 patches on A4, no grey ramp")

#: FEWER THAN TWENTY PATCHES, which is a border condition of the report and not
#: merely a small chart. The worst 5 % of a sheet with under twenty patches is
#: the EMPTY set (rank ⌈0.95 n⌉ is n), so that row reads N-A with
#: `small_sample` beside it, and the best 95 % and the 95th percentile become
#: every patch. Design record §3 states the rule; no demo project reached it.
#: Ten distinct grey levels are kept, so the grey rows stay eligible and the
#: column can have a recommended value over its limit at the same time as a
#: required row nobody could compute.
CHART_TINY = ChartRecipe(20, 10, 0, "A4", "20 patches on A4")

@dataclass(frozen=True)
class GridChartRecipe:
    """A chart written from an explicit device-value grid, not designed by targen.

    It exists for ONE state no targen chart can reach: a chart that cannot
    supply the surface-gamut row. That row's population is "at least one of
    red, green and blue within 2.0 of 0 or of 100", and every targen chart is
    full of such patches — measured over this package's six sizes, 21 of 30,
    58 of 90, 71 of 105, 105 of 168, 119 of 210 and 200 of 405. So the only
    way to watch the report DETECT that a chart cannot support the row, which
    is the half Knut asked for, is a chart built with nothing near an edge of
    the cube.

    A 5x5x5 grid on 20/35/50/65/80 gives 125 patches, none of them on the
    surface, a grey axis of five steps (too few for the grey rows, which need
    eight) and three tone steps inside 30..70 %, which keeps the tone-ramp row
    eligible.
    """

    levels: tuple = (20.0, 35.0, 50.0, 65.0, 80.0)
    paper: str = "A4"

    @property
    def patches(self) -> int:
        return len(self.levels) ** 3

    @property
    def label(self) -> str:
        return (f"{self.patches} mid-tone patches on {self.paper}, none of "
                f"them on the surface of the device cube")


def make_grid_chart(into: Path, stem: str, recipe: GridChartRecipe) -> None:
    from workflow.i1profiler_import import RgbPatch, write_ti1
    into.mkdir(parents=True, exist_ok=True)
    patches = [RgbPatch(r, g, b)
               for r in recipe.levels for g in recipe.levels
               for b in recipe.levels]
    write_ti1(patches, into / f"{stem}.ti1")
    run([ARGYLL / "printtarg"] + printtarg_args(recipe.paper) + [stem],
         into, TIMEOUT_PRINTTARG)


@dataclass(frozen=True)
class GamutChartRecipe:
    """A verification chart built by the app's OWN *from profile gamut* module.

    Knut, 2026-09-18: *"some tests require a test chart with From Profile
    Gamut, which must also be included"*. Such a chart is the only one that
    makes the report's three reference rows answerable at all: it ships a
    ``<stem>-reference.ti3`` beside itself, which is what turns
    ``reference_source`` into ``"colorimetric"``, and only then does
    ``row_values`` compute *Paper white*, *Solid colours largest* and *CMY hue
    difference* instead of writing ``needs_reference_file`` on all three.

    **WHAT THIS CHART CANNOT SUPPLY, MEASURED RATHER THAN ASSUMED.** The module
    picks colours out of a master Lab set through the profile's B2A table, and
    that selection is not a chart recipe: on a 200-colour selection the grey
    ramp came back with **6 grey patches at 5 distinct levels** (the row needs
    8) and the tone ramps with **one step on the grey axis and none on R, G or
    B**. So a profile-gamut sheet reads ``too_few_steps`` on both grey rows and
    ``no_ramp`` on the tone row, for ever, whatever it measures. Those three
    rows are exercised on the ORDINARY charts, and the package says so instead
    of quietly leaving them out.
    """

    count: int
    paper: str = "A4"
    margin: str = "safe"
    intent: str = "absolute"

    @property
    def patches(self) -> int:
        """The chart's real size: the selected colours plus the 8 corners."""
        return self.count + 8

    @property
    def label(self) -> str:
        return (f"{self.count} colours chosen from the profile's own gamut, "
                f"plus the 8 cube corners, on {self.paper}")


#: **THE GENERATOR USED TO CLAMP THE MODULE'S DEVICE VALUES, AND NOW IT
#: REFUSES INSTEAD.** Until B8-398 was fixed, `select_gamut_targets` took its
#: device values from xicclu's numeric inverse and nothing bounded them:
#: measured 2026-09-18 on a 200-colour selection, 17 of 200 came back over 100
#: on a channel and 15 over 101, the largest 107.69, and
#: `measurement_report._rgb_to_0_100` then rescaled the WHOLE chart by 100/255
#: because one patch exceeded 101. Not one cube corner read `present` after
#: that, so all three reference rows read `no_corners`. This file clamped for
#: itself so that the package could demonstrate those rows at all, and said so
#: loudly, because a demo that silently works around a fault in the product is
#: a demo of the workaround.
#:
#: B8-398 chose to DROP such a colour rather than clamp it: a clamped patch
#: keeps an aim the profile itself says the ink cannot make. Re-measured
#: 2026-09-19 through the same 200-colour selection: **0 of 200** outside the
#: cube. So the workaround is gone, and what stands in its place is a refusal:
#: if the app ever hands this generator an ink amount a printer has not got,
#: the build stops instead of quietly papering over it in the demo data.
GAMUT_DEVICE_CLAMP = False


def make_gamut_chart(into: Path, stem: str, recipe: GamutChartRecipe,
                     profile: Path):
    """The FROM PROFILE GAMUT chart, built through the app's own module.

    Returns the :class:`GamutSelection`, so the caller can ask it which sample
    ids are the eight corners and read the colorimetric aims back without
    re-deriving either.
    """
    from workflow.gamut_target import (select_gamut_targets,
                                       write_colorimetric_reference,
                                       write_gamut_ti1)
    sel = select_gamut_targets(profile, recipe.count, recipe.margin,
                               recipe.intent, bin_dir=ARGYLL)
    outside = [dev for _i, _lab, dev in sel.targets
               if max(dev) > 100.0 or min(dev) < 0.0]
    if outside:
        raise SystemExit(
            f"select_gamut_targets returned {len(outside)} of "
            f"{len(sel.targets)} colours outside the device cube (worst "
            f"{max(max(d) for d in outside):.2f}). That is B8-398 back: the "
            f"report rescales the whole chart by 100/255 as soon as one patch "
            f"exceeds 101, and every cube corner then reads as missing. The "
            f"demo package does not work around it; fix "
            f"workflow/gamut_target.select_gamut_targets.")
    into.mkdir(parents=True, exist_ok=True)
    write_gamut_ti1(sel, into / f"{stem}.ti1")
    write_colorimetric_reference(sel, into / f"{stem}-reference.ti3")
    run([ARGYLL / "printtarg"] + printtarg_args(recipe.paper) + [stem],
         into, TIMEOUT_PRINTTARG)
    return sel


#: **THE PACKAGE DOES NOT PICK ITS OWN CONTROL STRIP ANY MORE, AND THAT IS THE
#: WHOLE POINT OF THIS ROUND.** Until 2026-09-19 this file chose 24 patches of
#: its own, spread through the chart and deliberately holding no grey, no bare
#: paper and no cube corner. That selection demonstrated THIS GENERATOR. It
#: could not demonstrate ChromIQ, because nothing in ChromIQ wrote a
#: declaration at all (B8-405), and a demo pack whose fixture re-implements the
#: feature it is meant to show agrees with itself whatever the app does.
#:
#: B8-405 shipped the producer, so the package asks it. `declare_for_chart` is
#: the same call `TabChart._on_generate_finished` makes when the app files a
#: verification chart, and the sidecar in this package is the sidecar a user
#: gets. Its ladder is the opposite population to the old one: the substrate,
#: the eight cube corners, an 18-rung tint ladder and three neutral greys.
#:
#: MEASURED on this package's own charts (2026-09-19, `declare_for_chart`
#: asked with ``write=False``), rungs filled of the ladder's 29:
#:
#:     20-patch chart (CHART_TINY)        8   declares; NO 95th percentile
#:     90-patch, no grey ramp            23   declares; 95th percentile too
#:     105-patch (CHART_SMALL)           26   declares; 95th percentile too
#:     156-patch (CHART_WIDE)            28   declares; 95th percentile too
#:     210-patch (CHART_MEDIUM)          29   declares; 95th percentile too
#:     400-patch (CHART_LARGE)           29   declares; 95th percentile too
#:     208-patch FROM PROFILE GAMUT      17   declares; NO 95th percentile
#:     125-patch mid-tone grid            4   CANNOT DECLARE ONE AT ALL
#:
#: Three of those are states no hand-picked strip could have shown: a chart
#: that fills the ladder but not far enough for the 95th-percentile row
#: (`control_strip_too_small`), a chart that cannot fill it at all
#: (`no_control_strip`), and a full strip. All three are in this package.
def declare_control_strip(chart_dir: Path, stem: str):
    """Ask THE APP to declare this chart's control strip, and return its answer.

    No selection is made here and none may be: the moment this file decides
    which patches make up a strip, the package stops being evidence about
    ChromIQ and becomes evidence about the package.
    """
    from workflow.control_strip import declare_for_chart
    return declare_for_chart(chart_dir / f"{stem}.ti2")


def _strip_slots() -> tuple:
    """The ladder, asked of the app. Its length is the denominator every count
    in this file prints, and typing 29 here would be the same mistake as
    typing a patch list."""
    from workflow.control_strip import SLOTS
    return SLOTS


_chart_cache: "dict[tuple, Path]" = {}


def make_chart(into: Path, stem: str, recipe: ChartRecipe, cache_root: Path) -> None:
    """A real chart: targen designs it, printtarg lays it out and renders the
    pages. Cached per recipe so the same size is not designed twice."""
    into.mkdir(parents=True, exist_ok=True)
    key = (recipe.patches, recipe.grey, recipe.single, recipe.paper,
           recipe.instrument)
    src = _chart_cache.get(key)
    if src is None:
        src = cache_root / (f"chart-{recipe.patches}-{recipe.paper}"
                            f"-{recipe.instrument}")
        src.mkdir(parents=True, exist_ok=True)
        run([ARGYLL / "targen"] + recipe.targen_args + ["chart"],
            src, TIMEOUT_TARGEN)
        run([ARGYLL / "printtarg"]
            + printtarg_args(recipe.paper, recipe.instrument) + ["chart"],
            src, TIMEOUT_PRINTTARG)
        _chart_cache[key] = src
    for p in sorted(src.iterdir()):
        if p.is_file() and p.name.startswith("chart"):
            shutil.copy2(p, into / (stem + p.name[len("chart"):]))


#: HOW EVERY CHART IN THE PACK IS LAID OUT, in one place (B8-807, round 3B
#: F12). ``-M6`` is what the app passes to printtarg for every chart it lays
#: out (`chart_creator._build_printtarg_args`), so the page TIFF spans the
#: whole sheet. Without it the raster is cropped to the imageable area and the
#: Create Chart tab measured the patches 0.0 mm from the left paper edge.
#: ``-L`` is a no-op for the ColorMunki and is kept so the recorded command
#: stays the one earlier packs were built with.
PRINTTARG_INSTRUMENT = "CM"
PRINTTARG_DPI = 150
PRINTTARG_MARGIN_MM = 6


def _targen_settings(recipe) -> "dict[str, object]":
    """targen's rows as the Create Chart tab stores them, for a chart targen
    designed (`ChartRecipe.targen_args`); none for a chart written by hand."""
    if not isinstance(recipe, ChartRecipe):
        return {}
    return {"d": "2", "e": 4, "B": 4, "g": recipe.grey, "s": recipe.single,
            "f": recipe.patches}


def _suppress_left(instrument: str) -> bool:
    """``-L`` for the ColorMunki (a no-op there, kept for the recorded
    command), never for the i1Pro: an i1Pro strip chart keeps printtarg's own
    left clip border, which is the ruler's lead-in (#182 K29)."""
    return instrument != "i1"


def printtarg_args(paper: str, instrument: str = PRINTTARG_INSTRUMENT) -> list:
    return ([f"-i{instrument}", f"-p{paper}", f"-t{PRINTTARG_DPI}"]
            + (["-L"] if _suppress_left(instrument) else [])
            + [f"-M{PRINTTARG_MARGIN_MM}"])


def record_chart_settings(folder: Path, paper: str,
                          targen: "dict[str, object] | None" = None,
                          mode: str = "manual",
                          instrument: str = PRINTTARG_INSTRUMENT) -> None:
    """Write the Create Chart settings the app would have stored for a chart
    it laid out this way, into the chart's own settings store.

    **WITHOUT THIS THE PACK'S CHARTS OPENED ON SOMEBODY ELSE'S SETTINGS
    (round 3B, F12).** The store was empty, so Create Chart opened the chart
    on the app's defaults: an i1Pro, the ChromIQ layout engine, and the
    engine's clip border with its notes in it. That engine layout was then
    judged against the printtarg sheet on screen and the tab warned in red
    that a 22 mm clip band "runs over the patches on the left" of a chart that
    has no clip band at all. What is recorded here is what the chart IS:
    printtarg, a ColorMunki, this paper, 150 dpi, and no clip border content.

    *folder* is the run folder for the profiling chart and the run's
    ``verifications/`` folder for the verification chart, which is where
    `per_target_settings.store_for_target` looks for each.
    """
    from core.file_manager import Run
    from workflow.layout_engine.presets import LayoutRecipe
    settings = {
        "printtarg-i": {"enabled": True, "value": instrument},
        "printtarg-p": {"enabled": True, "value": paper},
        "printtarg-t": {"enabled": True, "value": PRINTTARG_DPI},
        "printtarg-L": {"enabled": _suppress_left(instrument), "value": True},
        "printtarg-m": {"enabled": False, "value": PRINTTARG_MARGIN_MM},
    }
    for flag, value in (targen or {}).items():
        settings[f"targen-{flag}"] = {"enabled": True, "value": value}
    recipe = LayoutRecipe(instrument=instrument, paper=paper,
                          clip_content_mode="off")
    store = Run.for_dir(folder)
    meta = store.load_meta()
    meta.create_chart_settings = settings
    # THE GUIDED ROW TOO: an absent "guided" bucket opens on the saved default
    # instrument (an i1Pro on a fresh install), and its instrument is mirrored
    # into Manual's -i, so the chart was then judged against the i1Pro's 26 mm
    # left minimum instead of the ColorMunki's 6 mm (measured on screen).
    meta.create_chart_ui = {"mode": mode, "engine_on": False,
                            "guided": {"instrument": instrument,
                                       "paper": paper, "pages": 1,
                                       "double_density": False,
                                       "triple_density": False,
                                       "left_border": not _suppress_left(
                                           instrument),
                                       "no_strip_limit": False,
                                       "precond": ""},
                            "engine_recipe": recipe.to_dict()}
    store.save_meta(meta)


def fakeread(into: Path, stem: str, profile: Path) -> Path:
    """A real fakeread of ``<stem>.ti1`` through *profile*, no noise: the
    designed drift is applied afterwards, deliberately, patch by patch."""
    run([ARGYLL / "fakeread", profile, stem], into, TIMEOUT_FAKEREAD)
    return into / f"{stem}.ti3"


#: THE PAPER EVERY SIMULATED PRINTER IN THE PACK PRINTS ON (K15, B8-779).
#:
#: A neutral, slightly warm matte paper a little below L* 100, judged under
#: D50 as every reading in ChromIQ is. Until 2026-09-22 there was no paper at
#: all: `fakeread` ran through ArgyllCMS's sRGB profile in its DEFAULT mode,
#: which is ABSOLUTE colorimetric, so every sheet's white came out at the D65
#: white point, XYZ 95.05 / 100 / 108.9. Read against D50 that is Lab about
#: 100 / -2.3 / -19.4: a blue paper no printer prints on, and Knut's report
#: drew it as a light blue swatch beside "White L* 100.0".
#:
#: Now the profiling read is RELATIVE (`fakeread -I r`), which puts the white
#: on D50 exactly, and :func:`lay_paper` then scales every reading by this
#: paper's reflectance, channel by channel, which is what paper does to ink
#: printed on it: what comes back is the ink's transmission times the paper's
#: own reflectance. The run's profile is built from that sheet, so its media
#: white IS this paper, and every dated verification read through it in
#: absolute mode carries the same paper without being told.
PAPER_LAB = (95.5, 0.2, 1.4)


@dataclass(frozen=True)
class PaperClass:
    """A class of real paper, for the K29 angles (#182, Knut 5795310999:
    *"Try to use available paper data as part of the simulation data to make
    it more realistic."*).

    **THE LAB IS OURS; THE FACT IT RESTS ON IS PUBLISHED.** Each value is a
    round, typical paper white for the class (D50, the way every reading in
    ChromIQ is taken), chosen to sit where the cited public fact puts the
    class. Nothing is copied from a dataset, a standard (ISO 12647, Fogra,
    Idealliance), a licence holder's file or anyone's measurements: this
    package is a public download. `cie_whiteness` lets a reader check the
    class claim against the cited sentence instead of trusting it.
    """
    id: str
    name: str
    lab: tuple
    oba: str                 # "high", "very low", "none"
    fact: str
    source: str

    @property
    def cie_whiteness(self) -> float:
        """CIE whiteness W = Y + 800 (xn - x) + 1700 (yn - y), against the D50
        white every ChromIQ reading is taken under."""
        X, Y, Z = _lab_to_xyz100(self.lab)
        s = X + Y + Z
        x, y = X / s, Y / s
        xn = _D50[0] / sum(_D50)
        yn = _D50[1] / sum(_D50)
        return Y + 800.0 * (xn - x) + 1700.0 * (yn - y)


#: The five classes, in the order the README lists them.
PAPER_CLASSES: "dict[str, PaperClass]" = {p.id: p for p in (
    PaperClass(
        "glossy_oba", "Glossy / luster RC photo paper with optical brighteners",
        (96.0, 1.2, -7.5), "high",
        "Optical brighteners absorb ultraviolet and re-emit it as visible "
        "blue, so a paper that carries them measures blue (negative b*) under "
        "light with UV in it; most glossy photo papers carry them.",
        "Wikipedia, 'Optical brightener' "
        "(https://en.wikipedia.org/wiki/Optical_brightener)"),
    PaperClass(
        "baryta", "Baryta (fibre base, very low brightener content)",
        (95.5, 0.4, -2.0), "very low",
        "A baryta photo paper's datasheet gives 'OBA content: Very low' and a "
        "CIE whiteness of 96.30: a faint blue, far less than an RC paper's.",
        "Canson Infinity, 'Baryta Photographique II' datasheet "
        "(https://www.canson-infinity.com/en/product_pdf/2727)"),
    PaperClass(
        "matte_rag", "Matte cotton rag, no optical brighteners",
        (94.5, 0.4, 3.5), "none",
        "Whiteness is what brighteners add; without them a paper shows the "
        "natural cream of its fibre, so its b* is positive (warmer).",
        "Wikipedia, 'Optical brightener' "
        "(https://en.wikipedia.org/wiki/Optical_brightener)"),
    PaperClass(
        "office", "Uncoated office paper",
        (94.0, 1.8, -11.0), "high",
        "'Most white paper will have CIE whiteness measures of between 130 "
        "and 170', because of optical brighteners.",
        "papersizes.org, 'Paper Whiteness, Brightness & Shade' "
        "(https://www.papersizes.org/whiteness-brightness.htm)"),
    PaperClass(
        "newsprint", "Newsprint-like (mechanical pulp)",
        (84.0, 0.3, 5.5), "none",
        "Newsprint is made from mechanical pulp that keeps its lignin: 'an "
        "off-white cast', and it yellows in air and light. It is the darkest "
        "and the yellowest class here by a wide margin.",
        "Wikipedia, 'Newsprint' (https://en.wikipedia.org/wiki/Newsprint)"),
)}


def paper_lab_of(paper_class: str) -> tuple:
    """The paper white a run prints on: its class's, or the pack's default."""
    return PAPER_CLASSES[paper_class].lab if paper_class else PAPER_LAB


def paper_name_of(paper_class: str) -> str:
    return (f"{PAPER_CLASSES[paper_class].name} (demo)" if paper_class
            else "Demo matte 200 g")


def lay_paper(ti3: Path, paper_lab=PAPER_LAB) -> "tuple[float, float, float]":
    """Scale a relative (D50-white) measurement onto :data:`PAPER_LAB`.

    Returns the per-channel factors. The sheet's own white patches land on
    the paper exactly, and every other reading keeps its ratio to them.
    """
    from workflow.ti3_analysis import parse_ti3
    white = _lab_to_xyz100(paper_lab)
    k = tuple(white[i] / _D50[i] for i in range(3))
    data = parse_ti3(ti3)
    _rewrite_xyz(ti3, {i: (x * k[0], y * k[1], z * k[2])
                       for i, (x, y, z) in enumerate(data.xyz)})
    return k


def build_profile(run_dir: Path, stem: str, paper_lab=PAPER_LAB) -> None:
    """fakeread through sRGB plays the bare printer, on *paper_lab*
    (:data:`PAPER_LAB` unless the run names a :data:`PAPER_CLASSES` entry);
    colprof makes the run's own profile from that measurement."""
    run([ARGYLL / "fakeread", "-I", "r", SRGB, stem], run_dir, TIMEOUT_FAKEREAD)
    lay_paper(run_dir / f"{stem}.ti3", paper_lab)
    # A PRINTER PROFILE, NOT A DISPLAY ONE. fakeread copies the class of the
    # profile it read through, which is ArgyllCMS's sRGB DISPLAY profile, and
    # colprof normalises a display's white to Y = 1: every run in the pack was
    # a display profile, and it threw the paper's lightness away, so every
    # sheet read through it came back at L* 100 whatever paper it was printed
    # on. An OUTPUT profile keeps its media white, and ArgyllCMS builds one
    # only as a cLUT, which is what a printer profile is anyway.
    ti3 = run_dir / f"{stem}.ti3"
    ti3.write_text(ti3.read_text(encoding="utf-8").replace(
        'DEVICE_CLASS "DISPLAY"', 'DEVICE_CLASS "OUTPUT"'), encoding="utf-8")
    run([ARGYLL / "colprof", "-v0", "-ql", stem], run_dir, TIMEOUT_COLPROF)


# ---------------------------------------------------------------------------
# Colour: the exact inverse of the report's own xyz_to_lab
# ---------------------------------------------------------------------------
from workflow.icc_info import xyz_to_lab as _xyz_to_lab      # noqa: E402

_D50 = (96.42, 100.0, 82.49)


def _lab_to_xyz100(lab) -> tuple:
    """Lab back to XYZ on the 0..100 scale the .ti3 carries. Written as the
    exact inverse of workflow.icc_info.xyz_to_lab so a value survives the round
    trip and the report reads back the ΔE that was designed."""
    L, a, b = (float(v) for v in lab)
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    eps = 216.0 / 24389.0
    kap = 24389.0 / 27.0

    def inv(f, is_y):
        t = f ** 3
        if is_y:
            return t if L > kap * eps else L / kap
        return t if t > eps else (116.0 * f - 16.0) / kap

    return (inv(fx, False) * _D50[0], inv(fy, True) * _D50[1],
            inv(fz, False) * _D50[2])


from workflow.ti3_analysis import ciede2000                  # noqa: E402

#: The four documents ChromIQ can produce. T5 and T6 are declared in the app so
#: the pulldown can show them and refuse them, and they are deliberately absent
#: here: a demo cannot exercise a document the app cannot produce, and nothing
#: in this generator may need a tolerance value out of either standard.
from workflow.measurement_report import (                    # noqa: E402
    REPORT_TYPE_FULL, REPORT_TYPE_GREY, REPORT_TYPE_ISO_8, REPORT_TYPE_MENU,
    REPORT_TYPE_MENU_HEADING, REPORT_TYPE_RECORD, REPORT_TYPE_SUMMARY)


def not_built_line() -> str:
    """The app's own sentence for a report type it cannot produce.

    TAKEN FROM THE WINDOW, NEVER TYPED. This README quotes it so a reader can
    match what the package says against what the pulldown says, and a quoted
    sentence that has moved on is the exact fault this whole file keeps
    finding. Importing the dialog costs a PyQt import and nothing else: the
    method is a staticmethod and needs no window, no QApplication and no
    measurement.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog._not_built_line(REPORT_TYPE_ISO_8)


def _de(lab_a, lab_b) -> float:
    return float(ciede2000(tuple(lab_a), tuple(lab_b)))


#: The direction a paper moves in when a date designs it off its reference:
#: toward yellow, at constant lightness. See the W corner in `apply_design`.
_PAPER_DRIFT = (0.0, 0.1, 1.0)


def _solve_scale(ref, direction, target_de: float) -> float:
    """The scale *s* for which ciede2000(ref + s*direction, ref) == target_de.

    ΔE00 grows monotonically along a ray out of the reference, so a bisection
    settles it. 60 halvings take the bracket below 1e-15 of its width.
    """
    lo, hi = 0.0, 1.0
    for _ in range(80):
        cand = tuple(ref[i] + hi * direction[i] for i in range(3))
        if _de(cand, ref) >= target_de:
            break
        hi *= 2.0
        if hi > 1e6:
            break
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        cand = tuple(ref[i] + mid * direction[i] for i in range(3))
        if _de(cand, ref) < target_de:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# The designed drift
# ---------------------------------------------------------------------------
GREY_SPREAD_TOL = 1.0        # mirrors workflow.measurement_report
GREY_PAPER_LEVEL = 99.5


def grey_stat_indices(rgb100: np.ndarray) -> "list[int]":
    """The patches the grey-balance rows are computed over: neutral by device
    value, and not the bare paper. The same test grey_balance_block applies."""
    out = []
    for i in range(rgb100.shape[0]):
        if float(rgb100[i].max() - rgb100[i].min()) > GREY_SPREAD_TOL:
            continue
        if float(rgb100[i].mean()) >= GREY_PAPER_LEVEL:
            continue
        out.append(i)
    return out


@dataclass
class Design:
    """What one dated verification's numbers are meant to be.

    The five colour-difference rows are order statistics of one list of ΔE00
    values, so the design is that list's shape:

    ``peak``      the single worst patch (what "All patches, largest" reads)
    ``tail``      the rest of the worst-5 % band (what "Worst 5 %, average"
                  reads, together with the peak)
    ``shoulder``  the top of the best 95 % (what "95th percentile" reads)
    ``bulk``      everything else (what "Best 95 %, average" mostly reads)

    ``target_best95`` overrides ``bulk``: the generator solves for the bulk
    value that puts the best-95 % average exactly there, which is the only way
    to hit that row without arithmetic by hand.

    ``grey_dch`` is the grey ramp's chroma difference, ``grey_spike`` one grey
    step's own.

    ``ramp_dl`` is the lightness error put on ONE step of the grey tone ramp
    between 30 and 70 % tone value, which is the only thing the "30 to 70 %
    ramps, largest lightness difference" row reads. It needs its own knob
    because the grey knob above moves chroma only and pins every grey's L* to
    the reference, so that row could never cross however the rest of the sheet
    was designed: measured over the whole package before this existed, seven of
    the eight rows a ChromIQ verification sheet can compute were crossed by some
    date and this was the eighth. The moved step also carries that lightness
    error into its own ΔE00, which is why the date that uses it expects two
    rows and not one.

    THE BAND SIZES ARE NOT FIXED. The rows are judged on the WITHIN-gamut
    patches (measurement_report.py:1008-1022), so how many patches fall in the
    worst 5 % depends on the chart and the profile, and the bands are sized
    from the real count at build time.
    """
    bulk: float
    shoulder: float
    peak: "float | None" = None
    tail: "float | None" = None
    target_best95: "float | None" = None
    grey_dch: float = 0.5
    grey_spike: "float | None" = None
    ramp_dl: "float | None" = None
    n_shoulder: int = 3

    # -- THE EIGHT CUBE CORNERS, which only a FROM PROFILE GAMUT chart can put
    #    a verdict on. The report keeps them out of the five colour-difference
    #    statistics on purpose (§9a rule 2: they are deliberately unreachable
    #    colours and would drag every average toward a number that says nothing
    #    about the profile), so these three knobs move rows 14 to 16 WITHOUT
    #    touching rows 1 to 5. That independence is a property of the report,
    #    not a trick of this script.
    #:  substrate_de00_max — the paper against the reference white
    white_de: "float | None" = None
    #:  solids_de00_max — the K corner's own dE00; the row is the largest over
    #:  C, M, Y and K, so ``cmy_dh`` can raise it too and the build's own
    #:  intended-against-actual check is what settles which of the two did.
    solid_de: "float | None" = None
    #:  cmy_solids_dhab_max — a PURE hue rotation of C, M and Y at constant L*
    #:  and constant chroma, so dL* = 0 and dC* = 0 and the metric hue
    #:  difference is exactly the chord asked for.
    cmy_dh: "float | None" = None

    # -- THE DECLARED CONTROL STRIP, which ChromIQ itself declares (B8-405)
    #    and this file no longer chooses. Its three rows are order statistics
    #    over one subset, so they take the same shape as the sheet's own: a
    #    bulk, a shoulder that the 95th percentile reads, and a single peak
    #    that the largest reads.
    #
    #    **A THIRD OF THE STRIP CANNOT BE MOVED, AND THAT IS A PROPERTY OF THE
    #    SHIPPED LADDER RATHER THAN A LIMIT OF THIS SCRIPT.** ChromIQ's strip
    #    IS the substrate, the eight cube corners and three neutral greys, and
    #    every one of those already carries its own design here: the bare
    #    paper is pinned to L*100 a*0 b*0 by the media-relative normalisation,
    #    the greys carry ``grey_dch``, and a declared corner carries
    #    ``white_de`` / ``solid_de`` / ``cmy_dh`` or is put exactly on its
    #    reference. A patch cannot have two designed values, so the three
    #    knobs below are laid over the rungs that are NOT already spoken for,
    #    and the rungs that are still count in the strip's statistics, because
    #    the report counts them.
    #
    #    That is why ``strip_avg`` exists. The per-patch value that puts the
    #    WHOLE strip's average on a chosen number depends on how many rungs a
    #    chart filled and on what the spoken-for ones carry, and neither is a
    #    number this file may type: the ladder is the app's and a chart fills
    #    as much of it as it fills. Given a target, the bulk is SOLVED from
    #    what the strip actually holds. It is exact rather than iterative,
    #    because every designed patch lands on exactly its target dE00.
    strip_bulk: "float | None" = None
    strip_shoulder: "float | None" = None
    strip_peak: "float | None" = None
    strip_avg: "float | None" = None

    # -- THE TWO GAMUT POPULATIONS ChromIQ defines for itself (S2w).
    #:  every patch with a channel within 2.0 of 0 or 100
    surface_de: "float | None" = None
    #:  the top quarter by the chroma of the reference
    outer_de: "float | None" = None

    # -- CHROMIQ'S OWN ROW A (B8-660): the ΔE00 between two readings of one
    #    repeated colour on the same sheet. See the block in `apply_design`.
    repeat_split: "float | None" = None


#: Device values at or above this on Argyll's 0..100 scale are the bare paper.
DEVICE_WHITE_MIN = 99.5


def in_gamut_flags(ti2: Path, profile: Path) -> "dict[str, bool]":
    """Which of the chart's colours the profile could actually print.

    The report judges only these (measurement_report.py:686-707 builds the
    split, :1008 makes the verdict read it). The test is made on the chart's
    DESIGN colours, so the answer is a property of the chart and the profile
    and is the same on every date, which is what makes it possible to design a
    date's statistics at all.
    """
    from workflow.gamut_target import MARGIN_SAFE, flags_in_gamut
    from workflow.measurement_report import _reference_labs
    from workflow.ti3_analysis import parse_ti3
    ref = _reference_labs(ti2)
    ids = [s for s in parse_ti3(ti2).sample_ids if s in ref]
    flags = flags_in_gamut([tuple(ref[s]) for s in ids], profile, ARGYLL,
                           margin=MARGIN_SAFE, intent="absolute")
    return {s: bool(f) for s, f in zip(ids, flags)}


#: The two population rules of #182 S2w, mirrored here rather than imported for
#: the same reason `RAMP_TV_LOW` is: a change to either in the app must show up
#: as a MISMATCH in this generator's own intended-against-actual check, not
#: silently move the design with it.
SURFACE_TOL = 2.0            # a channel within this of 0 or 100
OUTER_QUARTILE = 0.25        # the top quarter by the chroma of the reference


def _surface_patches(rgb100, sample_ids, ref) -> "list[int]":
    """Indices on the surface of the device cube: at least one of R, G, B
    within :data:`SURFACE_TOL` of 0 or of 100, and carrying a reference."""
    return [i for i, sid in enumerate(sample_ids)
            if sid in ref
            and any(min(float(v), 100.0 - float(v)) <= SURFACE_TOL
                    for v in rgb100[i])]


def _outer_quarter(sample_ids, ref) -> "list[int]":
    """Indices in the top quarter by the chroma of their REFERENCE value.

    The aim and not the reading, so the same chart picks the same patches
    however well it printed, which is the whole reason the row is stable enough
    to design against.
    """
    have = [(math.hypot(ref[s][1], ref[s][2]), i)
            for i, s in enumerate(sample_ids) if s in ref]
    have.sort(reverse=True)
    k = int(len(have) * OUTER_QUARTILE)
    return [i for _c, i in have[:k]]


def _rotate_hue(ref, chord: float) -> tuple:
    """*ref* rotated about the neutral axis so that dH*ab is exactly *chord*.

    A rotation at constant L* and constant chroma has dL* = 0 and dC* = 0, so
    the metric hue difference sqrt(dE_ab^2 - dL^2 - dC^2) collapses to the plain
    chord length between the two points, which is 2 C sin(theta/2). Solving
    that for theta is the whole of it, and it makes `cmy_solids_dhab_max` a
    number this script sets rather than one it hopes for.
    """
    L, a, b = (float(v) for v in ref)
    c = math.hypot(a, b)
    if c <= 1e-9:
        return (L, a, b)
    half = min(1.0, chord / (2.0 * c))
    theta = 2.0 * math.asin(half)
    phi = math.atan2(b, a) + theta
    return (L, c * math.cos(phi), c * math.sin(phi))


def apply_design(ti3: Path, ti2: Path, design: Design,
                 gamut: "dict[str, bool] | None" = None,
                 relative: bool = True,
                 ref_labs: "dict[str, tuple] | None" = None,
                 corner_ids: "set[str] | None" = None,
                 corner_devices: "dict[str, tuple] | None" = None,
                 strip_ids: "list[str] | None" = None) -> "dict[str, float]":
    """Rewrite the measurement's XYZ so the chart's statistics are the design's.

    THE DESIGN IS LAID OUT IN THE YARDSTICK THE REPORT ACTUALLY USES, which is
    not the obvious one. A sheet printed through the profile with a white
    mapping intent is judged *media-relative* (measurement_report.py:602-626):
    every reading is divided by the sheet's own paper white before the ΔE is
    taken, so that the paper is not counted against the profile. Designing in
    absolute Lab and hoping produced values around 55 % of the intended ones
    on the first run of this generator.

    So the numbers below are the media-relative ones, and the file is written
    back through the inverse of that normalisation. Two consequences follow and
    both are properties of the report, not of this script:

    * the paper-white patch is exactly L*100 a*0 b*0 after normalisation, by
      construction, so its own ΔE is ~0 whatever is written. The device-white
      patches are therefore left at the reference and take no designed value.
    * the paper white the report prints stays the one fakeread measured: the
      normalisation is anchored on it, so it is written back unchanged.

    **AND THE REPORT DOES NOT ALWAYS USE THAT YARDSTICK**, which is what
    ``relative=False`` is for. The media-relative rule needs a record of how
    the sheet was printed; without one the report judges in ABSOLUTE Lab, and a
    design laid out relative then lands about 1.8 times too large. Measured on
    the first build of the "nobody recorded the printing" run: every one of the
    five colour rows crossed, on a design that asked for none of them. In
    absolute mode the normalisation is the identity, and the device-white
    patches take a designed value like every other patch, because there is no
    anchor making theirs zero by construction.

    Returns the predicted rows, so the caller can compare them against what the
    real report reads back.
    """
    from workflow.measurement_report import _reference_labs
    from workflow.ti3_analysis import parse_ti3

    data = parse_ti3(ti3)
    # A FROM PROFILE GAMUT CHART'S .ti2 XYZ IS NOT ITS REFERENCE, and designing
    # against it would be designing against a yardstick the report does not
    # use. Such a chart's device values were already converted through the
    # profile at build time, so its .ti2 XYZ is only the sRGB reading of ink
    # amounts — a quantity with no relation to the Lab aims those amounts were
    # computed to produce. The report reads the aims out of
    # `<stem>-reference.ti3` instead (`reference_source == "colorimetric"`),
    # and so does this, when the caller hands them over.
    ref = dict(ref_labs) if ref_labs is not None else _reference_labs(ti2)
    corners_by_id = set(corner_ids or ())
    n = len(data.sample_ids)
    rgb = np.asarray(data.rgb, dtype=float)
    xyz = np.asarray(data.xyz, dtype=float)

    # The anchor: fakeread's own paper white, the lightest reading on the sheet.
    # In ABSOLUTE mode there is no anchor, so the normalisation is the identity
    # and the numbers below are read straight off the sheet.
    wi = int(np.argmax(xyz[:, 1]))
    white = xyz[wi].copy() if relative else np.array(_D50, dtype=float)
    if float(white.min()) <= 0.0:
        raise SystemExit(f"{ti3}: the lightest patch has a zero channel")
    scale = white / np.array(_D50)

    def to_relative(v) -> tuple:
        return _xyz_to_lab(tuple((np.asarray(v, float) / white * np.array(_D50)) / 100.0))

    measured = [to_relative(x) for x in xyz]
    # THE DEVICE-WHITE PATCHES ARE ONLY SPECIAL UNDER THE RELATIVE YARDSTICK,
    # where the normalisation pins them to L*100 a*0 b*0 whatever is written.
    # In absolute mode nothing pins them, so leaving them out would leave the
    # brightest patches of the sheet carrying fakeread's own error while every
    # other patch carried a designed one, and the statistics would miss.
    # THE CORNERS ARE THEIR OWN POPULATION AND ARE NEVER IN THE BANDS. The
    # report excludes them from the five colour-difference statistics by
    # sample id (§9a rule 2), so laying a band value over one would put a
    # number on the sheet that no row of the report reads, and take a band
    # slot away from a patch that is read.
    corner_at = {i for i, sid in enumerate(data.sample_ids)
                 if sid in corners_by_id}

    whites = ([i for i in range(n)
               if float(rgb[i].min()) >= DEVICE_WHITE_MIN and i not in corner_at]
              if relative else [])
    white_set = set(whites)

    # A CHART WITH NO BARE-PAPER PATCH HAS AN ANCHOR THAT MUST NOT BE MOVED.
    # Under the media-relative yardstick the report divides every reading by
    # the LIGHTEST patch on the sheet. On an ordinary chart that patch is bare
    # paper, this function pins it to L*100 a*0 b*0, and writing it back
    # reproduces the very XYZ the design was laid out against, so the report's
    # anchor and this one are the same. On a chart whose lightest patch is an
    # ordinary colour, designing that patch MOVES the anchor under the report,
    # and every other patch shifts with it: measured on the mid-tone grid
    # chart, a sheet designed for 0.6 dE00 came back reading 14.1.
    anchor_free: "set[int]" = set()
    if relative and not whites:
        anchor_free = {wi}

    greys = [i for i in grey_stat_indices(rgb)
             if i not in white_set and i not in corner_at
             and i not in anchor_free]
    grey_set = set(greys)
    spike_at = greys[len(greys) // 2] if (greys and design.grey_spike is not None) else None

    new_lab: "dict[int, tuple]" = {}

    # -- the bare paper: fixed at the reference. The normalisation puts it at
    #    L*100 a*0 b*0 regardless, so a designed value here would be a fiction.
    for i in whites:
        new_lab[i] = (100.0, 0.0, 0.0)

    # -- the grey patches: a pure chroma move of the designed size, so ΔCh is
    #    exactly what the grey-balance rows are meant to read.
    for i in greys:
        r = ref.get(data.sample_ids[i])
        if r is None:
            continue
        da, db = measured[i][1] - r[1], measured[i][2] - r[2]
        mag = math.hypot(da, db)
        if mag < 1e-6:
            da, db, mag = 1.0, 0.0, 1.0
        want = design.grey_spike if i == spike_at else design.grey_dch
        new_lab[i] = (r[0], r[1] + want * da / mag, r[2] + want * db / mag)

    # -- everybody else. The judged population is the within-gamut patches, so
    #    the bands are laid over those and the rest simply carry the bulk value.
    judged = (lambda i: True) if gamut is None \
        else (lambda i: gamut.get(data.sample_ids[i], True))
    others = [i for i in range(n)
              if i not in grey_set and i not in white_set
              and i not in corner_at and i not in anchor_free
              and data.sample_ids[i] in ref]
    fixed_in = [i for i in list(white_set) + greys
                if i in new_lab and judged(i)]
    n_in = len(fixed_in) + sum(1 for i in others if judged(i))
    k_in = max(1, min(n_in, int(math.ceil(n_in * 0.95))))
    m_tail = n_in - k_in

    tail_v = design.tail if design.tail is not None else design.shoulder
    band = []
    if design.peak is not None and m_tail:
        band = [design.peak] + [tail_v] * (m_tail - 1)
    elif m_tail:
        band = [tail_v] * m_tail
    band += [design.shoulder] * design.n_shoulder

    in_others = [i for i in others if judged(i)]
    out_others = [i for i in others if not judged(i)]

    def lay(bulk_value: float) -> "dict[int, tuple]":
        plan = list(band) + [bulk_value] * max(0, len(in_others) - len(band))
        made: "dict[int, tuple]" = dict(new_lab)      # the paper and the greys
        for pos, i in enumerate(in_others):
            made[i] = _place(ref[data.sample_ids[i]], measured[i], plan[pos])
        for i in out_others:
            made[i] = _place(ref[data.sample_ids[i]], measured[i], bulk_value)
        return made

    if design.target_best95 is not None:
        # Solve for the bulk value that puts the best-95 % average exactly on
        # the target. The greys and the bare paper are in that average too and
        # are not free, so there is no closed form worth writing.
        lo, hi = 0.0, 40.0
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            made = lay(mid)
            got = _predict_from(made, ref, data.sample_ids, judged)["best95_de00_avg"]
            if got < design.target_best95:
                lo = mid
            else:
                hi = mid
        new_lab.update(lay(0.5 * (lo + hi)))
    else:
        new_lab.update(lay(design.bulk))

    # -- one step of the 30 to 70 % grey ramp, moved in LIGHTNESS only.
    #    The grey knob above pins every grey's L* to the reference, so this row
    #    reads exactly zero on every date unless something moves L*. a* and b*
    #    are left where the grey knob put them, so the grey-balance rows keep
    #    the values they were designed for; only this patch's own ΔE00 grows.
    if design.ramp_dl is not None:
        step = _ramp_step_index(rgb, greys)
        if step is None:
            raise SystemExit(
                f"{ti3}: no grey step lies between {RAMP_TV_LOW} and "
                f"{RAMP_TV_HIGH} % tone value, so ramp_dl has nothing to move")
        r = ref[data.sample_ids[step]]
        a, b = new_lab[step][1], new_lab[step][2]
        new_lab[step] = (r[0] - design.ramp_dl, a, b)

    # -- THE THREE POPULATIONS THAT ARE SUBSETS OF THE SHEET, in the order the
    #    report reads them, each one overriding the last where they overlap:
    #    the outer-gamut quarter, the surface of the device cube, and the
    #    declared control strip. A patch in two of them takes the LAST one's
    #    value, which is why the order is written down here rather than left
    #    to a dict's iteration.
    # THE BARE PAPER AND THE GREY RAMP ARE NEVER MOVED BY A POPULATION, and
    # this cost a build to learn. The surface of the device cube is "a channel
    # within 2.0 of 0 or of 100", which is TRUE OF THE BARE PAPER — and under
    # the media-relative yardstick the paper is the anchor the whole sheet is
    # divided by, so moving it moved every other patch with it. Measured: a
    # grey ramp designed for a flat 8.0 of chroma error came back as a RAMP
    # from 2.1 to 6.7, and the two grey rows read 4.407 and 6.745 for a design
    # that asked for 8.0 on both. The greys are excluded for the plainer
    # reason that they carry their own design and a patch cannot have two.
    _off_limits = white_set | grey_set | corner_at | anchor_free

    def _set_de(i: int, target: float) -> None:
        if i in _off_limits:
            return
        r = ref.get(data.sample_ids[i])
        if r is None:
            return
        new_lab[i] = _place(r, measured[i], target)

    if design.outer_de is not None:
        for i in _outer_quarter(data.sample_ids, ref):
            _set_de(i, design.outer_de)
    if design.surface_de is not None:
        for i in _surface_patches(rgb, data.sample_ids, ref):
            _set_de(i, design.surface_de)

    # -- THE EIGHT CUBE CORNERS, last, because every population above can
    #    contain one and the corner rows are the ones a reader came for.
    #
    #    EVERY CORNER THIS DATE DOES NOT DESIGN IS PUT EXACTLY ON ITS
    #    REFERENCE. Left at fakeread's own error a corner carries several
    #    dE00 of its own — measured, 13.65 on the paper white of a plain
    #    fakeread, because the module's corner aims are the IDEAL sRGB values
    #    and no printer reaches them — which would make every "nothing
    #    crosses" date fail rows 14 and 15 for a reason the date is not about.
    # The patches the CORNER block designed, whichever they turn out to be.
    # The strip below must not lay a value over one: a corner row is what a
    # reader came for, and a strip rung aims at the same eight device values
    # the corners do, so the nearest patch to a corner aim is very often the
    # same patch. Measured the first time the strip ran last: seven of the ten
    # profile-gamut dates lost their K corner to the strip's own solid_K rung
    # and "Solid colours, largest" stopped crossing on every one of them.
    corner_read: "set[int]" = set()
    if corner_at:
        from workflow.measurement_report import CUBE_CORNERS
        # EVERY DECLARED CORNER IS PUT ON ITS REFERENCE FIRST. They are out of
        # the five colour-difference statistics by sample id, so what they
        # carry is invisible unless the report also READS one as a corner, and
        # leaving fakeread's own several-dE00 error on them would make a
        # "nothing crosses" date fail rows 14 and 15 for a reason it is not
        # about.
        for i in corner_at:
            r = ref.get(data.sample_ids[i])
            if r is not None:
                new_lab[i] = tuple(r)
        # THE PATCH THE REPORT WILL READ, ASKED OF THE FUNCTION THE REPORT ASKS.
        #
        # **AND THE ANSWER CHANGED UNDER THIS FILE.** Until B8-398 the report
        # found a corner by the nearest device value over the whole chart and
        # never consulted the chart's own `CHROMIQ_CORNER_IDS`, so a selected
        # colour sitting at device (0,0,0) was read as the composite black
        # while the declared corner beside it was read by nobody (measured:
        # the K corner came off sample 2, not sample 202). This file therefore
        # designed the nearest-device patch, on purpose, and said so. B8-398
        # fixed the report to read the DECLARATION, and this file went on
        # designing the other patch: measured on the first build after that
        # fix, "Solid colours, largest" was designed at 5.0 against a limit of
        # 3.0 and read back **inside its limit on all six profile-gamut runs**,
        # in every limit set, because the 5.0 had been put on a patch the
        # report no longer calls a corner.
        #
        # So the question is asked of `_declared_corner_rows`, which IS what
        # `build_report` calls. A chart that declares nothing gets the
        # nearest-device answer, which is what the report does for it too.
        from workflow.measurement_report import _declared_corner_rows
        declared_rows = _declared_corner_rows(data.sample_ids,
                                              set(corner_ids or ()),
                                              dict(corner_devices or {}))
        for name, target in CUBE_CORNERS:
            if name in declared_rows:
                ci = declared_rows[name]
            else:
                diffs = np.abs(rgb - np.array(target))
                ci = int((diffs ** 2).sum(axis=1).argmin())
            r = ref.get(data.sample_ids[ci])
            if r is None:
                continue
            corner_read.add(ci)
            if name == "W" and design.white_de is not None:
                # A PAPER OFF ITS REFERENCE IS A YELLOWED PAPER, and it stays
                # the lightest reading on the sheet, because paper always is.
                # `_place` along fakeread's own direction moved it in L*
                # (the pack's paper is L* 95.5 and this reference white is
                # the ideal 100), which on a 5.0 date put the paper at L* 92.7
                # BELOW the ideal yellow corner (L* 97) and the report called
                # the yellow patch "Paper white"; on a 0.5 date `_place`'s
                # anti-anchor flip put it at L* 100.8, whiter than white.
                # Measured on the first build on the new paper (K15).
                #
                # AND THE K15 FIX STILL LOWERED L*, by 0.3 per unit of b*.
                # That is harmless at 5.0 and not at 9.0: Quick check's
                # "everything over" date (Every-Limit-Set/run6, 2028-05-12)
                # put the paper at L* 96.75, under a saturated yellow of the
                # same sheet at 97.14 (patch 208), and the report's
                # "lightest patch is the paper" rule recorded the YELLOW as
                # paper white (round 3B, F13). A paper that yellows keeps its
                # lightness, so the drift is now in b* (and a trace of a*)
                # only, and `_paper_white_fault` refuses any date on which the
                # report's paper white is not the chart's white patch.
                s = _solve_scale(r, _PAPER_DRIFT, design.white_de)
                new_lab[ci] = tuple(r[k] + _PAPER_DRIFT[k] * s for k in range(3))
            elif name in ("C", "M", "Y") and design.cmy_dh is not None:
                new_lab[ci] = _rotate_hue(r, design.cmy_dh)
            elif name == "K" and design.solid_de is not None:
                new_lab[ci] = _place(r, measured[ci], design.solid_de)
            else:
                new_lab[ci] = tuple(r)

    # -- THE DECLARED CONTROL STRIP, LAST OF ALL, and it is last for a reason
    #    the order above does not have. Every population before it may be
    #    overridden by the one after; the strip is not a population this file
    #    chooses, it is the one ChromIQ declared, and by the time we reach it
    #    the bare paper, the greys and the eight corners are already carrying
    #    the values their own rows are judged on. A patch cannot have two, so
    #    the strip's knobs are laid over the rungs nobody else has spoken for,
    #    and the strip's statistics are computed over ALL of them, because
    #    `control_strip_block` is computed over all of them.
    #
    #    THE FIRST VERSION OF THIS PUT THE PEAK ON THE LAST MEMBER OF THE
    #    DECLARATION and the declaration's last three rungs are the neutral
    #    greys, which `_set_de` refuses. The peak and the shoulder were
    #    silently dropped and the two rows they exist to move never moved.
    #    They go on the last FREE rungs now.
    if strip_ids and (design.strip_bulk is not None
                      or design.strip_avg is not None):
        at = {sid: i for i, sid in enumerate(data.sample_ids)}
        # The population the REPORT takes the three rows over: a declared id
        # that is in this measurement and carries a reference value
        # (`control_strip_block`, which counts those two conditions as one k).
        counted = [at[s] for s in strip_ids
                   if s in at and data.sample_ids[at[s]] in ref]
        taken = _off_limits | corner_read
        free = [i for i in counted if i not in taken]
        spoken_for = [i for i in counted if i in taken]
        if not free:
            raise SystemExit(
                f"{ti3}: every rung of the declared control strip is already "
                f"carrying another row's design, so no strip value can be "
                f"placed. The chart filled {len(counted)} rungs.")
        extras: "list[float]" = []
        if design.strip_peak is not None:
            extras.append(design.strip_peak)
        if design.strip_shoulder is not None and len(free) >= len(extras) + 1:
            extras.append(design.strip_shoulder)
        if design.strip_avg is not None:
            # Solve the bulk EXACTLY. `_place` lands every free rung on its
            # target dE00, so the strip's mean is linear in the bulk value and
            # there is nothing to iterate.
            fixed = sum(_de(new_lab.get(i, measured[i]), ref[data.sample_ids[i]])
                        for i in spoken_for)
            n_bulk = len(free) - len(extras)
            if n_bulk < 1:
                raise SystemExit(
                    f"{ti3}: strip_avg was asked for on a strip with "
                    f"{len(free)} free rung(s) and {len(extras)} of them "
                    f"already named by strip_shoulder/strip_peak")
            bulk = (design.strip_avg * len(counted) - fixed - sum(extras)) / n_bulk
            if bulk < 0.0:
                raise SystemExit(
                    f"{ti3}: a strip average of {design.strip_avg} is below "
                    f"what this chart's own spoken-for rungs already carry "
                    f"({fixed / max(1, len(counted)):.3f} over "
                    f"{len(counted)} rungs); no value on the free rungs can "
                    f"bring the mean down that far")
        else:
            bulk = float(design.strip_bulk)
        plan = [bulk] * len(free)
        # The largest rung last, the 95th-percentile rung beside it. Order
        # statistics do not care where in the list a value sits; a reader of
        # the file does.
        if design.strip_peak is not None:
            plan[-1] = design.strip_peak
        if design.strip_shoulder is not None and len(plan) >= 2:
            plan[-2] = design.strip_shoulder
        for i, target in zip(free, plan):
            _set_de(i, target)

    # -- CHROMIQ'S OWN ROW A: two readings of ONE repeated colour pulled apart.
    #    Every patch above is placed along the direction fakeread's own error
    #    took, and fakeread gives identical device values identical readings,
    #    so every repeat group on the sheet lands on one point and Row A reads
    #    0.0 on every date of the package: judged everywhere, crossed nowhere.
    #    This takes the first repeat group the report will see that is not the
    #    bare paper (the paper is the media-relative anchor and must not move),
    #    and sets its first two members either side of where they were, in
    #    chroma only and at the SAME distance from the reference, so the
    #    colour-difference rows see the pair once each and Row A sees the gap.
    if design.repeat_split is not None:
        from workflow.ti3_analysis import device_repeat_groups
        groups = [g for g in device_repeat_groups(rgb)
                  if len(g) >= 2 and not (set(g) & (white_set | anchor_free))
                  and all(data.sample_ids[i] in ref for i in g[:2])]
        if not groups:
            raise SystemExit(f"{ti3}: repeat_split asked for, and the chart "
                             f"repeats no colour the design may move")
        a_i, b_i = groups[0][0], groups[0][1]
        base = new_lab.get(a_i, measured[a_i])
        lo, hi = 0.0, 40.0
        for _ in range(50):
            t = 0.5 * (lo + hi)
            pa = (base[0], base[1] + t, base[2])
            pb = (base[0], base[1] - t, base[2])
            if _de(pa, pb) < design.repeat_split:
                lo = t
            else:
                hi = t
        t = 0.5 * (lo + hi)
        new_lab[a_i] = (base[0], base[1] + t, base[2])
        new_lab[b_i] = (base[0], base[1] - t, base[2])

    predicted = _predict_from(new_lab, ref, data.sample_ids, judged)
    if design.repeat_split is not None:
        predicted["repeat_patches_de00_max"] = float(design.repeat_split)
    if design.ramp_dl is not None:
        predicted["ramps_30_70_dl_max"] = float(design.ramp_dl)
    dchs = [math.hypot(new_lab[i][1] - ref[data.sample_ids[i]][1],
                       new_lab[i][2] - ref[data.sample_ids[i]][2])
            for i in greys if i in new_lab]
    if dchs:
        predicted["grey_balance_neutral_ramp_avg"] = float(np.mean(dchs))
        predicted["grey_balance_neutral_ramp_max"] = float(np.max(dchs))

    out = {}
    for i, v in new_lab.items():
        rel = np.asarray(_lab_to_xyz100(v), dtype=float)
        out[i] = tuple(rel * scale)
    _rewrite_xyz(ti3, out)
    return predicted


#: The band `measurement_report.ramps_block` reads, and the spread it allows a
#: patch before it stops counting as grey. Named here rather than imported so
#: that a change to either shows up as a MISMATCH in this generator's own
#: intended-against-actual check instead of silently moving the design.
RAMP_TV_LOW, RAMP_TV_HIGH = 30.0, 70.0


def _ramp_step_index(rgb, greys: "list[int]") -> "int | None":
    """The middle grey step lying inside the 30 to 70 % tone-value band.

    `ramps_block` reads the largest lightness difference over that band, taking
    the tone value of a grey as ``100 - mean(RGB)``. The middle of the band is
    chosen so the patch is as far as possible from both edges: a step at 30.4 %
    would drop out of the row entirely if the chart's levels ever shifted.
    """
    band = [i for i in greys
            if RAMP_TV_LOW <= (100.0 - float(np.asarray(rgb[i], float).mean()))
            <= RAMP_TV_HIGH]
    if not band:
        return None
    mid = 0.5 * (RAMP_TV_LOW + RAMP_TV_HIGH)
    return min(band, key=lambda i: abs((100.0 - float(np.asarray(rgb[i], float).mean())) - mid))


def _place(r, measured_lab, target_de: float) -> tuple:
    """The patch's new colour: the direction fakeread's own error took, scaled
    until the difference from the reference is *target_de*."""
    d = [measured_lab[j] - r[j] for j in range(3)]
    if max(abs(v) for v in d) < 1e-6:
        d = [0.6, 0.6, 0.4]
    s = _solve_scale(r, d, target_de)
    cand = tuple(r[j] + s * d[j] for j in range(3))
    if cand[0] > 99.0:
        # Nothing may end up lighter than the paper: it would take the paper's
        # place as the anchor of the media-relative yardstick and move the
        # whole sheet.
        d = [-d[0], d[1], d[2]]
        s = _solve_scale(r, d, target_de)
        cand = tuple(r[j] + s * d[j] for j in range(3))
    return cand


def _predict_from(new_lab, ref, sample_ids, judged) -> "dict[str, float]":
    des = [_de(new_lab[i], ref[sample_ids[i]])
           for i in sorted(new_lab) if sample_ids[i] in ref and judged(i)]
    return _predict(des, [])


def _predict(des: "list[float]", dchs: "list[float]") -> "dict[str, float]":
    a = np.sort(np.asarray(des, float))
    n = int(a.size)
    k = max(1, min(n, int(math.ceil(n * 0.95))))
    low, high = a[:k], a[k:]
    out = {
        "all_de00_avg": float(a.mean()),
        "best95_de00_avg": float(low.mean()),
        "worst5_de00_avg": float(high.mean()) if high.size else None,
        "all_de00_max": float(a.max()),
        "all_de00_p95": float(low.max()),
    }
    if dchs:
        out["grey_balance_neutral_ramp_avg"] = float(np.mean(dchs))
        out["grey_balance_neutral_ramp_max"] = float(np.max(dchs))
    return out


def _rewrite_xyz(ti3: Path, xyz_by_index: "dict[int, tuple]") -> None:
    """Put the designed XYZ back into the measurement, leaving every other
    field, keyword and line of the file exactly as fakeread wrote it."""
    lines = ti3.read_text(encoding="utf-8").splitlines()
    fields: "list[str]" = []
    in_fmt = False
    start = end = -1
    for i, line in enumerate(lines):
        s = line.strip()
        if s == "BEGIN_DATA_FORMAT":
            in_fmt = True
            continue
        if s == "END_DATA_FORMAT":
            in_fmt = False
            continue
        if in_fmt and s:
            fields = s.split()
            continue
        if s == "BEGIN_DATA":
            start = i + 1
        elif s == "END_DATA":
            end = i
            break
    if start < 0 or end < 0:
        raise SystemExit(f"{ti3} has no data block")
    try:
        ix = fields.index("XYZ_X")
        iy = fields.index("XYZ_Y")
        iz = fields.index("XYZ_Z")
    except ValueError:
        raise SystemExit(f"{ti3} carries no XYZ fields; fakeread should write them")
    row = 0
    for i in range(start, end):
        if not lines[i].strip():
            continue
        parts = lines[i].split()
        v = xyz_by_index.get(row)
        if v is not None and len(parts) > iz:
            parts[ix] = f"{v[0]:.6f}"
            parts[iy] = f"{v[1]:.6f}"
            parts[iz] = f"{v[2]:.6f}"
            lines[i] = " ".join(parts)
        row += 1
    ti3.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Filing one dated verification
# ---------------------------------------------------------------------------
def stamp(ti3: Path, when: str, instrument: str = INSTRUMENT) -> None:
    from workflow.ti3_analysis import mark_verification_ti3
    mark_verification_ti3(ti3)
    lines = ti3.read_text(encoding="utf-8").splitlines()
    at = next(i for i, l in enumerate(lines) if l.startswith("NUMBER_OF_FIELDS"))
    lines[at:at] = ['KEYWORD "CHROMIQ_MEASURED"',
                    f'CHROMIQ_MEASURED "{when}"',
                    f'TARGET_INSTRUMENT "{instrument}"']
    ti3.write_text("\n".join(lines) + "\n", encoding="utf-8")
    t = datetime.fromisoformat(when).timestamp()
    os.utime(ti3, (t, t))


def stamp_profiling(ti3: Path, when: str, instrument: str = INSTRUMENT) -> None:
    """Date the run's OWN measurement, the sheet the profile was built from.

    `stamp` above is for a dated verification and calls `mark_verification_ti3`,
    which is exactly what this must NOT do: the profiling chart is printed raw
    by definition and marking it a verification would have the report grade it.
    Everything else is the same, and it matters for the same reason: without a
    CHROMIQ_MEASURED keyword the report window heads the column with the day
    the package happened to be unpacked. Knut's screenshot of 2026-09-13 is a
    column headed with that day.
    """
    lines = ti3.read_text(encoding="utf-8").splitlines()
    at = next(i for i, l in enumerate(lines) if l.startswith("NUMBER_OF_FIELDS"))
    lines[at:at] = ['KEYWORD "CHROMIQ_MEASURED"',
                    f'CHROMIQ_MEASURED "{when}"',
                    f'TARGET_INSTRUMENT "{instrument}"']
    ti3.write_text("\n".join(lines) + "\n", encoding="utf-8")
    t = datetime.fromisoformat(when).timestamp()
    os.utime(ti3, (t, t))


def write_print_record(chart_dir: Path, stem: str, when: str, profile_name: str,
                       colour: str = "through-profile") -> None:
    """How the sheet was printed, or nothing at all when *colour* is "none".

    THREE STATES, AND ONLY ONE OF THEM WAS EVER BUILT. Knut, 2026-09-11: *"The
    demo test data must be made so that all parts of the report can be shown
    and tested, including fault messages and border conditions."* The record
    is what decides two of them:

    * ``through-profile``: the ordinary verification. Everything is graded.
    * ``raw``: the sheet went to the printer with no profile applied, so the
      report treats it as a DRIFT check and prints "drift" instead of a
      verdict (`measurement_report.is_drift_check`): pass/fail against profile
      accuracy would fail a healthy printer for ever.
    * ``none``: no record was written, which is what a sheet printed outside
      ChromIQ looks like. The grey-balance rows are then JUDGED like every
      other row and carry a numbered note (`printing_unrecorded`) saying that
      against the chart's own design in absolute Lab the paper's own tint is
      inside the number. Until 2026-09-13 they were shown for information
      instead (CH-17); Knut overruled that.

    NO ``profile_path`` and no ``profile_mtime``: those two keys are the only
    absolute paths a ChromIQ project would otherwise carry, and an absolute path
    is exactly what breaks a project that travels to another machine. Without
    them the report falls back to the run's own built profile, which it finds
    relative to the measurement.
    """
    if colour == "none":
        return
    rec = {"printed_at": when, "colour": colour, "intent": "relative",
           "route": "chromiq", "source_profile": "", "profile": profile_name}
    if colour == "raw":
        # A raw sheet went to the printer with no profile applied, so naming
        # one would be a false record of how it was made.
        rec["intent"] = ""
        rec["profile"] = ""
    (chart_dir / f"{stem}.print.json").write_text(
        json.dumps(rec, indent=2), encoding="utf-8")


def snapshot(vdir: Path, stem: str, src: Path) -> Path:
    """The dated check's own chart snapshot. The report prefers it over the
    shared chart, so an old date keeps being judged against the chart it was
    actually measured on. The page TIFFs are deliberately left out: they are
    page images, they are the bulk of the archive, and no report reads them."""
    cdir = vdir / "chart"
    cdir.mkdir(parents=True, exist_ok=True)
    # THE COLORIMETRIC REFERENCE AND THE CONTROL-STRIP SIDECAR TRAVEL WITH THE
    # CHART, because the report looks for both BESIDE the chart it paired the
    # measurement with, and for a dated verification that chart is this
    # snapshot. Written beside the shared chart only, a sidecar was invisible
    # to every date (measured on screen 2026-09-18, B8-397).
    for name in (f"{stem}.ti1", f"{stem}.ti2", f"{stem}-reference.ti3",
                 f"{stem}.control-strip.json"):
        s = src / name
        if s.is_file():
            shutil.copy2(s, cdir / s.name)
    return cdir


# ---------------------------------------------------------------------------
# The dated series
# ---------------------------------------------------------------------------
@dataclass
class Date:
    vid: str
    when: str
    title: str
    story: str
    design: Design
    expect: "list[str]"          # row ids intended to cross their limit


#: THE ROW NAMES, TAKEN FROM THE APP AND NOT TYPED HERE. This was a hand-kept
#: dict of eight until 2026-09-18, when B8-397 made five more rows computable
#: and the README started printing bare row ids for them. Reading
#: `compliance_sets.ROWS` means a row added to ChromIQ cannot arrive here
#: nameless.
def _row_titles() -> "dict[str, str]":
    from workflow.compliance_sets import ROWS
    return {r.id: r.label for r in ROWS}


ROW_TITLES = _row_titles()


def _d(vid, when, title, story, design, expect) -> Date:
    return Date(vid, when, title, story, design, expect)


#: THE CENTREPIECE. Judged with ChromIQ default: 2.0 on the three averages,
#: 3.0 on the two maxima, and 1.5 and 3.0 on the grey pair. The grey pair was
#: a pair of RECOMMENDED values in every ChromIQ set until Knut removed that on
#: 2026-09-21 (a set of ChromIQ's own is no standard and carries requirements
#: only), and COND was retired as a row word the same day, so a grey row over
#: its limit reads FAIL like any other. Every date that crosses is followed by
#: one that recovers.
SERIES_DEFAULT: "list[Date]" = [
    _d("2026-01-05_100000", "2026-01-05T10:00:00",
       "Everything inside its limit",
       "The healthy baseline. Nothing crosses; the column reads PASS.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
    _d("2026-01-19_100000", "2026-01-19T10:00:00",
       "One patch goes badly wrong",
       "A single patch at 4.5 pushes 'All patches, largest' over 3.0. The "
       "worst-5 % average stays under 2.0 because the other patches in that "
       "band did not move. ONE row crosses.",
       Design(bulk=0.80, shoulder=1.40, peak=4.50, tail=1.20, grey_dch=0.50),
       ["all_de00_max"]),
    _d("2026-02-02_100000", "2026-02-02T10:00:00",
       "The bad patch is gone again",
       "The same sheet without the outlier. 'All patches, largest' is back "
       "inside 3.0 and the column reads PASS again.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
    _d("2026-02-16_100000", "2026-02-16T10:00:00",
       "The hardest colours all drift together",
       "The worst 5 % of patches average about 2.7, over their limit of 2.0, "
       "while the largest single value stays under 3.0. ONE row crosses.",
       Design(bulk=0.80, shoulder=1.40, peak=2.75, tail=2.65, grey_dch=0.50),
       ["worst5_de00_avg"]),
    _d("2026-03-02_100000", "2026-03-02T10:00:00",
       "The hardest colours come back",
       "The worst-5 % average is back under 2.0. PASS again.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
    _d("2026-03-16_100000", "2026-03-16T10:00:00",
       "The whole sheet drifts",
       "The bulk of the chart moves up to just under its own limit and the "
       "worst 5 % go to 2.98, just under theirs. Between them they carry the "
       "all-patch average over 2.0. TWO rows cross, which is the most this "
       "design allows.",
       Design(bulk=2.0, shoulder=2.40, peak=2.98, tail=2.98,
              target_best95=1.98, grey_dch=1.20, n_shoulder=6),
       ["all_de00_avg", "worst5_de00_avg"]),
    _d("2026-03-30_100000", "2026-03-30T10:00:00",
       "The sheet settles",
       "Back to the baseline. Both rows recover together.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
    _d("2026-04-13_100000", "2026-04-13T10:00:00",
       "The greys pick up a cast",
       "Every grey on the ramp is 1.8 off in chroma, over the 1.5 this set "
       "puts on the grey average. The worst-5 % average goes with it "
       "and cannot be held back: 1.8 of chroma error on a neutral IS a colour "
       "difference of 2.55, the grey ramp is most of the worst 5 % of this "
       "chart, and their limit is 2.0. TWO rows cross. Isolated-Rows run 4 "
       "shows the grey average crossing on its own, with a column that allows "
       "for this.",
       Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=1.80),
       ["grey_balance_neutral_ramp_avg", "worst5_de00_avg"]),
    _d("2026-04-27_100000", "2026-04-27T10:00:00",
       "The cast is corrected, nearly",
       "The grey ramp is back to 0.5 and inside its limit again, except the "
       "step in the middle of the ramp, which keeps 1.8 of the cast. That is "
       "inside the 3.0 on the grey maximum, so nothing crosses.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50,
              grey_spike=1.80),
       []),
    _d("2026-05-11_100000", "2026-05-11T10:00:00",
       "One grey step is badly wrong",
       "The step in the middle of the grey ramp goes from 1.8 to 3.6 off in "
       "chroma. That crosses the 3.0 this set puts on the grey maximum, and "
       "the same patch is far enough out to carry "
       "'All patches, largest' over 3.0 with it. TWO rows cross, and this pair "
       "cannot be separated: a grey cast this size along a* is over 2.0 as a "
       "colour difference too, which the note further down works out. The "
       "step moved 1.8 since the date before, which is inside the 3.0 on "
       "'The same chart measured again', so the printer is not blamed for "
       "moving.",
       Design(bulk=0.80, shoulder=1.10, peak=1.50, tail=1.40,
              grey_dch=0.40, grey_spike=3.60),
       ["grey_balance_neutral_ramp_max", "all_de00_max"]),
    _d("2026-05-25_100000", "2026-05-25T10:00:00",
       "The grey step comes back",
       "The step is back to 1.8. Both rows recover on the same date, and the "
       "move back is inside the repeat row's limit as the move out was.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50,
              grey_spike=1.80),
       []),
]

#: run2 of the first project: the SAME kind of sheet, judged with ChromIQ
#: tight (1.0 / 1.0 / 1.0 / 1.5 / 1.5). A sheet that passes comfortably under
#: the default column fails here, which is the whole point of having more than
#: one column.
SERIES_TIGHT: "list[Date]" = [
    _d("2026-02-10_113000", "2026-02-10T11:30:00",
       "Good enough for the default column, not for this one",
       "Exactly the numbers of run 1's healthy baseline, which passed there. "
       "Against ChromIQ tight the worst-5 % average and the largest value are "
       "both over their limits. TWO rows cross.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       ["worst5_de00_avg", "all_de00_max"]),
    _d("2026-03-10_113000", "2026-03-10T11:30:00",
       "Tightened up until this column is happy",
       "Everything roughly halved. Nothing crosses, even against the tight "
       "column.",
       Design(bulk=0.40, shoulder=0.70, peak=1.10, tail=0.90, grey_dch=0.30),
       []),
    _d("2026-04-10_113000", "2026-04-10T11:30:00",
       "One patch out, tight column",
       "A single patch at 2.4 crosses 'All patches, largest' (1.5) on its own, "
       "with the worst-5 % average held just under 1.0. ONE row crosses.",
       Design(bulk=0.40, shoulder=0.45, peak=2.40, tail=0.45, grey_dch=0.30),
       ["all_de00_max"]),
]

#: run3 of the first project: exactly ONE dated verification, so the limit set
#: can still be chosen. Knut asked for a run in this state by name: *"Some runs
#: must only have one verification run, so that settings can be changed."*
SERIES_ONE_DATE: "list[Date]" = [
    _d("2026-06-01_090000", "2026-06-01T09:00:00",
       "The only measurement this run has",
       "One dated verification and nothing else, judged by Quick check "
       "(4 on the three averages, 6 on the two maxima, 3 and 7 on the grey "
       "pair, and 4 and 6 on its own two repeatability rows). The report "
       "window still offers the limit set, "
       "because one measurement is not yet a history to keep comparable.",
       Design(bulk=1.10, shoulder=2.20, peak=3.60, tail=3.00, grey_dch=0.70),
       []),
]

#: run3 of the second project: the history that WOULD lock the run, with the
#: lock lifted by hand. Put it beside Threshold-Series/run2, which has the same
#: kind of history and was never unlocked, and the pair says what the lock does.
SERIES_TWO_DATES_UNLOCKED: "list[Date]" = [
    _d("2026-06-02_090000", "2026-06-02T09:00:00",
       "One patch out, and the lock lifted by hand",
       "A single patch at 1.55 crosses 'All patches, largest' (1.5) on its "
       "own. This small chart judges 56 patches, so its worst 5 % is only "
       "two of them, and the second is held at 0.42 to keep their average "
       "just under 1.0.",
       Design(bulk=0.35, shoulder=0.40, peak=1.55, tail=0.40, grey_dch=0.25),
       ["all_de00_max"]),
    _d("2026-06-16_090000", "2026-06-16T09:00:00",
       "The second date, which is what would normally lock the run",
       "The patch comes back to 1.2 and nothing crosses. This is the date that "
       "gives the run a history: without the hand-lifted lock the limit set "
       "would be fixed from here on, exactly as Threshold-Series/run2's is.",
       Design(bulk=0.35, shoulder=0.40, peak=1.20, tail=0.40, grey_dch=0.25),
       []),
]

#: The tone-ramp row, which NO shipped set judges at all.
#:
#: Every ChromIQ set leaves `ramps_30_70_dl_max` without a limit, so the report
#: prints its number and nothing can cross it. That makes it invisible to a
#: package built only from the shipped sets, and it was: measured over the whole
#: of this package, the seven rows a shipped set puts a number on were all
#: crossed by some date, and this one could not be. It becomes judgeable only
#: when a user types a limit into it, which is what this run's own edited column
#: does, and which is this project's whole purpose.
SERIES_RAMP: "list[Date]" = [
    _d("2026-10-05_110000", "2026-10-05T11:00:00",
       "One step of the grey ramp is too dark",
       "The middle step of the grey tone ramp is 3.0 too dark, over the 2.0 "
       "this run's own column asks for. Every colour-difference limit is "
       "relaxed to 9.0, so the lightness error this puts on that one patch "
       "crosses nothing else. ONE row crosses.",
       Design(bulk=0.60, shoulder=0.90, peak=1.40, tail=1.10, grey_dch=0.40,
              ramp_dl=3.0),
       ["ramps_30_70_dl_max"]),
    _d("2026-10-19_110000", "2026-10-19T11:00:00",
       "The ramp comes back",
       "The same step is 1.0 out, inside the 2.0 limit. The row recovers and "
       "nothing else moved.",
       Design(bulk=0.60, shoulder=0.90, peak=1.40, tail=1.10, grey_dch=0.40,
              ramp_dl=1.0),
       []),
]

#: Rows that cannot cross alone under any shipped set, isolated by
#: giving the run its own edited column. See the README.
SERIES_BEST95: "list[Date]" = [
    _d("2026-07-06_140000", "2026-07-06T14:00:00",
       "The bulk of the chart is over its limit",
       "The best 95 % of patches average 2.4, over the 2.0 this run's own "
       "column asks for, while the deliberately relaxed all-patch, worst-5 %, "
       "largest and 95th-percentile limits stay comfortable. ONE row crosses.",
       Design(bulk=2.4, shoulder=2.70, peak=3.20, tail=2.90,
              target_best95=2.40, grey_dch=1.00),
       ["best95_de00_avg"]),
    _d("2026-07-20_140000", "2026-07-20T14:00:00",
       "The bulk comes back inside",
       "The best-95 % average drops to 1.5. The row recovers and nothing else "
       "changed.",
       Design(bulk=1.5, shoulder=1.80, peak=2.20, tail=2.00,
              target_best95=1.50, grey_dch=1.00),
       []),
]

SERIES_P95: "list[Date]" = [
    _d("2026-08-03_140000", "2026-08-03T14:00:00",
       "The 95th percentile crosses",
       "The value at the 95th percentile is 3.6, over the 3.0 this run's own "
       "column asks for, while the deliberately relaxed averages and maximum "
       "stay comfortable. ONE row crosses.",
       Design(bulk=1.00, shoulder=3.60, peak=4.20, tail=3.90,
              grey_dch=0.80, n_shoulder=4),
       ["all_de00_p95"]),
    _d("2026-08-17_140000", "2026-08-17T14:00:00",
       "The 95th percentile comes back",
       "The shoulder of the distribution drops to 2.0 while the worst few "
       "patches are left exactly where they were. The row recovers on its own.",
       Design(bulk=1.00, shoulder=2.00, peak=4.20, tail=3.90,
              grey_dch=0.80, n_shoulder=4),
       []),
]

#: run4 of the second project: the grey-balance AVERAGE on its own. A grey
#: cast big enough to cross the grey average's 1.5 also lifts the worst-5 %
#: average past 2.0 under a stock column, because ΔE00 near a neutral is about
#: 1.41 times the plain chroma difference (measured: ΔCh 1.8 gives ΔE00 2.55,
#: ΔCh 3.6 gives 4.82) and the grey ramp is most of this chart's worst 5 %.
#: This run's own column relaxes the four ΔE rows so the grey row stands alone.
SERIES_GREY_AVG: "list[Date]" = [
    _d("2026-08-31_150000", "2026-08-31T15:00:00",
       "A grey cast, and only the grey row says so",
       "The grey ramp is 1.9 off in chroma, over the 1.5 ChromIQ default "
       "puts on the grey average. This run's own column relaxes the "
       "colour-difference rows to 6 and 9 so the cast is not counted twice. "
       "ONE row crosses.",
       Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=1.90),
       ["grey_balance_neutral_ramp_avg"]),
    _d("2026-09-14_150000", "2026-09-14T15:00:00",
       "The cast is corrected",
       "The grey ramp is back to 0.6 and inside its limit again.",
       Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=0.60),
       []),
]

#: The third project: ONE measurement, three columns. The two designs below are
#: used unchanged in all three runs, so the only thing that differs between
#: those reports is the limit set. This project deliberately does NOT hold to
#: "at most two rows at once": showing a whole column go over is the point of
#: it. The row-by-row isolation lives in the first two projects.
COMPARE_MILD = Design(bulk=0.85, shoulder=1.30, peak=2.40, tail=1.50,
                      grey_dch=0.60)
COMPARE_DRIFTED = Design(bulk=1.60, shoulder=2.40, peak=3.40, tail=2.60,
                         grey_dch=1.20)

_C1 = ("2026-09-07_160000", "2026-09-07T16:00:00", "The shared measurement",
       "The same designed sheet as the other two runs of this project. Only "
       "the limit set differs.")
_C2 = ("2026-09-21_160000", "2026-09-21T16:00:00",
       "The shared measurement, drifted",
       "The same sheet a fortnight later, everything a little worse. Again "
       "the only difference between the three runs is the column.")

SERIES_COMPARE_DEFAULT: "list[Date]" = [
    _d(*_C1, COMPARE_MILD, []),
    _d(*_C2, COMPARE_DRIFTED, ["worst5_de00_avg", "all_de00_max"]),
]
SERIES_COMPARE_TIGHT: "list[Date]" = [
    _d(*_C1, COMPARE_MILD, ["worst5_de00_avg", "all_de00_max"]),
    _d(*_C2, COMPARE_DRIFTED,
       ["all_de00_avg", "best95_de00_avg", "worst5_de00_avg",
        "all_de00_max", "all_de00_p95",
        # tight puts 1.0 on the grey average, not the default's 1.5
        "grey_balance_neutral_ramp_avg"]),
]
SERIES_COMPARE_QUICK: "list[Date]" = [
    _d(*_C1, COMPARE_MILD, []),
    _d(*_C2, COMPARE_DRIFTED, []),
]


# ---------------------------------------------------------------------------
# The fourth project: the report TYPES (D28)
# ---------------------------------------------------------------------------
#: Knut, 2026-09-11: *"expanded so that all 6 report types can be tested for
#: thresholds and report content"*.
#:
#: FOUR OF THE SIX CAN BE TESTED, AND THE OTHER TWO CANNOT BE TESTED AS
#: DOCUMENTS AT ALL. Validation print check (ISO 12647-8) and Contract proof
#: check (ISO 12647-7) are declared so the pulldown can show them and refuse
#: them; the figures they judge against are published in standards ChromIQ has
#: no permission to include, so ChromIQ cannot produce either document and no
#: measurement can make it produce one. What CAN be demonstrated about them is
#: that they are offered, greyed, and say why, and that the refusal holds one
#: level below the control as well: `set_run_report_type` raises rather than
#: storing an unbuilt id. Both of those are exercised on screen against this
#: project, and neither needs a tolerance value from either standard. See the
#: README's own section.
#:
#: Every run here carries TWO dated verifications and has the limit lift
#: applied, so both pulldowns stay live and a reader can try every type
#: against every set on the same measurement. The three states of the limit
#: lift itself are demonstrated in the first two projects; this one is about
#: the documents.

#: T1 and T2 read the same five colour-difference rows, so one shape of data
#: serves both, and T4 shows the same figures with every word withheld. The
#: three runs below differ only in which set their numbers were aimed at.
TYPES_DE_DEFAULT: "list[Date]" = [
    _d("2026-11-02_100000", "2026-11-02T10:00:00",
       "One patch goes badly wrong",
       "A single patch at 4.5 carries 'All patches, largest' over ChromIQ "
       "default's 3.0, with the worst-5 % average held under 2.0. ONE row "
       "crosses, and it is the row the one-page summary prints beside its "
       "word.",
       Design(bulk=0.90, shoulder=1.50, peak=4.50, tail=1.20, grey_dch=0.50),
       ["all_de00_max"]),
    _d("2026-11-16_100000", "2026-11-16T10:00:00",
       "The bad patch is gone again",
       "The same sheet without the outlier. The row recovers and the summary "
       "goes back to PASS.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
]

#: K23 (Knut, 2026-09-23): the dates of Report-Limits-Report-Folders. Their
#: numbers are not the point, where their reports LIVE is, so two stories are
#: reused with ChromIQ default: one date with one bad patch, the others clean.
_FOLDERS_BAD = Design(bulk=0.90, shoulder=1.50, peak=4.50, tail=1.20,
                      grey_dch=0.50)
_FOLDERS_OK = Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60,
                     grey_dch=0.50)
FOLDERS_RUN1: "list[Date]" = [
    _d("2026-12-01_100000", "2026-12-01T10:00:00", "First check",
       "A clean sheet.", _FOLDERS_OK, []),
    _d("2026-12-08_100000", "2026-12-08T10:00:00", "One patch goes wrong",
       "A single patch at 4.5 carries 'All patches, largest' over 3.0.",
       _FOLDERS_BAD, ["all_de00_max"]),
    _d("2026-12-15_100000", "2026-12-15T10:00:00", "Clean again",
       "The outlier is gone.", _FOLDERS_OK, []),
]
FOLDERS_RUN2: "list[Date]" = [
    _d("2026-12-22_100000", "2026-12-22T10:00:00", "The new profile, first check",
       "A clean sheet.", _FOLDERS_OK, []),
    _d("2026-12-29_100000", "2026-12-29T10:00:00", "One patch goes wrong",
       "A single patch at 4.5 carries 'All patches, largest' over 3.0.",
       _FOLDERS_BAD, ["all_de00_max"]),
]

#: K25 (Knut, 2026-09-23): the dates of the SECOND project the report list is
#: grouped across. Two dates, clean then one bad patch, same designs.
FOLDERS_OTHER_RUN1: "list[Date]" = [
    _d("2027-01-05_100000", "2027-01-05T10:00:00", "Another project, first check",
       "A clean sheet.", _FOLDERS_OK, []),
    _d("2027-01-12_100000", "2027-01-12T10:00:00", "One patch goes wrong",
       "A single patch at 4.5 carries 'All patches, largest' over 3.0.",
       _FOLDERS_BAD, ["all_de00_max"]),
]

TYPES_DE_TIGHT: "list[Date]" = [
    _d("2026-11-03_100000", "2026-11-03T10:00:00",
       "One patch out, tight column",
       "A single patch at 2.4 crosses 'All patches, largest' (1.5) on its own, "
       "with the worst-5 % average held just under 1.0. ONE row crosses.",
       Design(bulk=0.40, shoulder=0.70, peak=2.40, tail=0.55, grey_dch=0.30),
       ["all_de00_max"]),
    _d("2026-11-17_100000", "2026-11-17T10:00:00",
       "Tightened up until this column is happy",
       "The outlier comes back to 1.1 and nothing crosses.",
       Design(bulk=0.40, shoulder=0.70, peak=1.10, tail=0.90, grey_dch=0.30),
       []),
]

#: The one-page summary again, against Quick check. Until beta 36 this pair was
#: a PRINTING RECORD of a verification, and that document is no longer a
#: verification's to have (K13, B8-787: a profiling measurement's only report
#: is the Printing record, a verification never has one). Every run's own
#: profiling measurement in this package now carries the Printing record, so
#: the document is still in front of a reader, on the sheet it belongs to.
TYPES_DE_QUICK: "list[Date]" = [
    _d("2026-11-04_100000", "2026-11-04T10:00:00",
       "A patch far enough out to fail Quick check",
       "A single patch at 7.5, over Quick check's 6.0 on 'All patches, "
       "largest', with every average well inside 4.0. ONE row crosses, and it "
       "is the row the one-page summary prints beside its word.",
       Design(bulk=1.10, shoulder=2.50, peak=7.50, tail=3.00, grey_dch=0.70),
       ["all_de00_max"]),
    _d("2026-11-18_100000", "2026-11-18T10:00:00",
       "The patch comes back inside Quick check",
       "The outlier drops to 4.5, inside 6.0, and the summary goes back to "
       "PASS.",
       Design(bulk=1.10, shoulder=2.20, peak=4.50, tail=3.00, grey_dch=0.70),
       []),
]

#: T3 keeps three rows and drops the rest. Two of the three, the grey pair, are
#: limits in every ChromIQ set and read FAIL over them; the third, the
#: 30 to 70 % tone ramp, is judged by NO shipped set, so it can only be made to
#: say something by a run's own edited column. One run here does that, and the
#: other two leave it alone so a reader sees both states.
TYPES_GREY_DEFAULT: "list[Date]" = [
    _d("2026-11-05_100000", "2026-11-05T10:00:00",
       "A grey cast and a dark ramp step, together",
       "The grey ramp is 1.9 off in chroma, over the 1.5 ChromIQ default puts "
       "on it, and the middle step of the tone ramp is 3.0 too dark, over the "
       "2.0 this run's own column asks for. TWO rows cross, which is the most "
       "this design allows, and they are the two rows a Grey and tone check "
       "exists to show.",
       Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=1.90, ramp_dl=3.0),
       ["grey_balance_neutral_ramp_avg", "ramps_30_70_dl_max"]),
    _d("2026-11-19_100000", "2026-11-19T10:00:00",
       "Both come back",
       "The cast drops to 0.6 and the ramp step to 1.0. Both rows recover on "
       "the same date and the third row, the grey maximum, never moved.",
       Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=0.60, ramp_dl=1.0),
       []),
]

TYPES_GREY_TIGHT: "list[Date]" = [
    _d("2026-11-06_100000", "2026-11-06T10:00:00",
       "Both grey rows cross at once",
       "The ramp carries 1.4 of chroma error and one step carries 2.4, which "
       "puts the average over ChromIQ tight's 1.0 and the largest "
       "over its 2.0. TWO rows cross. The tone-ramp row shows its number and "
       "no word, because no shipped limit set puts a limit on it.",
       Design(bulk=0.40, shoulder=0.60, tail=0.70, grey_dch=1.40,
              grey_spike=2.40),
       ["grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max"]),
    _d("2026-11-20_100000", "2026-11-20T10:00:00",
       "The cast and the spike are both corrected",
       "The ramp is back to 0.6 with no step standing out. Both rows recover.",
       Design(bulk=0.40, shoulder=0.60, tail=0.70, grey_dch=0.60),
       []),
]

TYPES_GREY_QUICK: "list[Date]" = [
    _d("2026-11-07_100000", "2026-11-07T10:00:00",
       "A cast big enough for even Quick check to mention",
       "The grey ramp is 3.5 off in chroma, over the 3.0 Quick check puts on "
       "the grey average. ONE row crosses.",
       Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=3.50),
       ["grey_balance_neutral_ramp_avg"]),
    _d("2026-11-21_100000", "2026-11-21T10:00:00",
       "The cast is corrected",
       "The ramp is back to 1.0, comfortably inside even this column's "
       "limit.",
       Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=1.00),
       []),
]

#: A Grey and tone check on a chart that has no grey ramp, which is what most
#: charts are. Both grey rows read N-A and the tone-ramp row has nothing to
#: report, so the column has limit-bearing rows and NOTHING it could check.
#: That is the state the third Overall clause was written for on 2026-09-11,
#: and before this run existed no demo project reached it: without that clause
#: this column read a green PASS under "Every value this limit set requires was
#: checked and is within its limit", with nothing checked at all.
TYPES_GREY_NOTHING: "list[Date]" = [
    _d("2026-11-08_100000", "2026-11-08T10:00:00",
       "A Grey and tone check with nothing to judge",
       "The chart carries no grey ramp, so both grey-balance rows read N-A and "
       "the column's word is N-A too, with the sentence that says which "
       "patches to add in Create Chart. The colour rows of this same "
       "measurement are perfectly ordinary, and the line below says what they "
       "come to in the graded document.",
       Design(bulk=0.40, shoulder=0.80, peak=1.30, tail=0.80, grey_dch=0.50),
       []),
    _d("2026-11-22_100000", "2026-11-22T10:00:00",
       "The same chart a fortnight later",
       "Nothing about the missing ramp changes with the measurement, which is "
       "the point: a chart that cannot supply a row cannot supply it on any "
       "date, and the report says so rather than passing it.",
       Design(bulk=0.40, shoulder=0.80, peak=1.30, tail=0.80, grey_dch=0.50),
       []),
]


# ---------------------------------------------------------------------------
# The fifth project: the fault messages and the border conditions
# ---------------------------------------------------------------------------
#: Knut, 2026-09-11: *"The demo test data must be made so that all parts of the
#: report can be shown and tested, including fault messages and border
#: conditions."*
#:
#: The messages were INVENTORIED FROM THE CODE, not from memory:
#: `compliance_sets.SUMMARY_REASONS` holds every sentence the Overall cell can
#: print, and `measurement_report.REASON_*` every reason a row can give for
#: having no number. Measured against the package as it stood, five of the
#: eleven Overall sentences and ten of the eleven row reasons were unreachable
#: by any data in it. The three runs below close the ones data CAN close; the
#: README names the rest and says why they cannot be reached.

#: FEWER THAN TWENTY PATCHES. The worst-5 % row reads N-A with `small_sample`,
#: and that is a REQUIRED row going missing, which is what turns the column's
#: sentence from "pass" into one of the two that count what was not computed.
#: With a grey cast on top, a row that WAS computed is over its limit at the
#: same time, which is the other of the two.
BORDER_SMALL_SAMPLE: "list[Date]" = [
    _d("2026-12-01_100000", "2026-12-01T10:00:00",
       "Too few patches to have a worst 5 per cent, and a grey cast as well",
       "Twenty patches, so the worst 5 % of the sheet is the empty set and "
       "that row cannot be computed at all; the best 95 % and the 95th "
       "percentile become every patch. The grey ramp is 1.55 off in chroma at "
       "the same time, over the 1.5 this set puts on the grey average. The "
       "column therefore has both a row nobody could compute and a row over "
       "its limit, which is the only way to reach the sentence that counts "
       "them both.",
       Design(bulk=0.40, shoulder=0.60, tail=0.60, grey_dch=1.55),
       ["grey_balance_neutral_ramp_avg"]),
    _d("2026-12-15_100000", "2026-12-15T10:00:00",
       "The cast is corrected, and the chart is still too small",
       "The grey ramp is back to 0.5 and nothing is over a limit. The worst "
       "5 % is still not computable, because that is a property of the chart "
       "and not of the printing, so the column reads the sentence that counts "
       "only what was missing.",
       Design(bulk=0.80, shoulder=1.10, tail=1.10, grey_dch=0.50),
       []),
]

#: NOBODY RECORDED HOW THE SHEET WAS PRINTED, which is what a sheet measured
#: outside ChromIQ looks like. The grey rows carry real numbers, are JUDGED,
#: and carry a numbered note saying that against the chart's own design in
#: absolute Lab the paper's own tint is inside that number. This run therefore
#: demonstrates the numbered note list, which is the thing no other run in the
#: pack shows. Until 2026-09-13 it demonstrated the opposite, CH-17's
#: information-only rows, and Knut overruled that.
BORDER_UNRECORDED: "list[Date]" = [
    _d("2026-12-02_100000", "2026-12-02T10:00:00",
       "A sheet whose printing condition nobody wrote down",
       "The same kind of measurement as the other projects, printed and "
       "measured like all of them, but with no record of the paper, ink and "
       "driver settings it was printed WITH. Every row is judged; the two grey "
       "rows carry a numbered note saying the paper's own tint is inside their "
       "number.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=1.90),
       []),
    _d("2026-12-16_100000", "2026-12-16T10:00:00",
       "The same, a fortnight later",
       "Nothing about the missing record changes with the measurement, which "
       "is the point: the rows it affects are the same on every date.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.60),
       []),
]

#: A SHEET PRINTED RAW, which is a drift check and not an accuracy check.
#: `is_drift_check` makes the report withhold the verdict entirely and print
#: "drift": judging a raw sheet against profile accuracy would fail a healthy
#: printer for ever (Knut, 2026-08-11).
BORDER_RAW_DRIFT: "list[Date]" = [
    _d("2026-12-03_100000", "2026-12-03T10:00:00",
       "A sheet printed with no profile applied",
       "Printed raw and measured to watch the printer drift, not to check a "
       "profile. The numbers are large because nothing corrected them, and "
       "the report declines to put a verdict on them.",
       Design(bulk=3.00, shoulder=5.00, peak=8.00, tail=6.00, grey_dch=2.50),
       []),
    _d("2026-12-17_100000", "2026-12-17T10:00:00",
       "The same raw sheet a fortnight later",
       "The numbers have moved, which is what a drift check is for, and there "
       "is still no verdict to give.",
       Design(bulk=3.60, shoulder=5.60, peak=9.00, tail=6.80, grey_dch=3.00),
       []),
]


# ---------------------------------------------------------------------------
# The sixth project: the two Custom columns
# ---------------------------------------------------------------------------
#: Knut, 2026-09-11: *"make sure the metrics have a value that can be tested
#: against, and that all metrics limits are verified with the
#: ChromIQ-Report-Limit-Demos package."*
#:
#: When this package was first expanded, "Custom ISO 12647-7" and "Custom
#: ISO 12647-8" held nothing: every measurable row read ? or -, so neither
#: column judged anything, neither was even offered in the report window, and
#: this package's coverage table correctly recorded that nothing covered them.
#: They now start from ChromIQ's own numbers on every row ChromIQ can measure,
#: so the window offers them and a run can be bound to either.
#:
#: **THE NUMBERS IN THOSE TWO COLUMNS ARE NOT TOUCHED BY THIS GENERATOR AND MAY
#: NOT BE.** Since 2026-09-21 they are Knut's researched industry figures where
#: his research covers a row and ChromIQ's own numbers where it does not
#: (#182); they are deliberately not either standard's published tolerances,
#: and a test pins where each one came from. The designs below were worked out
#: against the columns AS THEY ARE, the same way every other series in this
#: file is, and the intended/actual check at the end of a build is what proves
#: it. They can no longer be assumed to match ChromIQ default's, and the two
#: columns can no longer be assumed to match each other.
#:
#: TWO THINGS A READER OF THESE TWO RUNS HAS TO KNOW, and both are properties
#: of the columns rather than of the data:
#:
#: * **A Custom column cannot check everything it limits on a ChromIQ chart.**
#:   Three of its eighteen limit-bearing rows (paper white against the
#:   reference paper, solid colours, CMY hue difference) need a reference
#:   measurement of the printing condition, which ChromIQ cannot read yet, so
#:   they are N-A on every date.
#: * **BOTH OF THE RULES THIS BLOCK USED TO STATE ARE RETIRED**, and it said
#:   them for a day after they were. An unanswered row demoted a column until
#:   Knut's N-A ruling of 2026-09-21; a column named after a standard was
#:   capped at COND until he retired that on 2026-09-22. So the word moves
#:   FAIL to PASS across these two dates, with three rows still N-A, and the
#:   NOTE beside it is what qualifies the PASS: the numbers are applied to the
#:   chart YOU printed, not to that standard's own chart, so a result inside
#:   them is an indication and not proof.

CUSTOM_7_SERIES: "list[Date]" = [
    _d("2027-01-05_100000", "2027-01-05T10:00:00",
       "One patch over the largest-difference limit",
       "A single patch at 4.5, over the 3.0 this column puts on 'All patches, "
       "largest', with the worst-5 % average held under its own 2.0. ONE row "
       "crosses.",
       Design(bulk=0.90, shoulder=1.50, peak=4.50, tail=1.20, grey_dch=0.50),
       ["all_de00_max"]),
    _d("2027-01-19_100000", "2027-01-19T10:00:00",
       "The bad patch is gone again",
       "The same sheet without the outlier. Nothing is over a limit, so the "
       "column goes green, while three of its rows still need a reference "
       "measurement this chart cannot supply and stay N-A. A column named "
       "after a standard carries its caveat whatever the numbers do, and "
       "that note is what says the PASS is an indication and not proof.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50),
       []),
]

#: The other Custom column, crossing a DIFFERENT row, and one that no ChromIQ
#: set judges at all: the 30 to 70 % tone ramp. Elsewhere in this package that
#: row can only be exercised by typing a limit into a run's own edited column;
#: here a shipped set puts one on it, and it is a requirement like any other.
#: It carried a bracket until Knut retired it on 2026-09-21: *"the thresholds
#: that use a bracket, ex. '(3,00)', should not have a bracket, since it is
#: not a 'recommended'/'should' type metric."*
CUSTOM_8_SERIES: "list[Date]" = [
    _d("2027-02-02_100000", "2027-02-02T10:00:00",
       "The hardest colours drift, and one ramp step goes dark",
       "The worst 5 % of patches average about 2.7, over their 2.0, and the "
       "middle step of the grey tone ramp is 3.0 too dark, over the 2.0 this "
       "column puts on it. TWO rows cross, which is the most this design "
       "allows, and neither is a recommendation: this column requires both.",
       Design(bulk=0.80, shoulder=1.40, peak=2.75, tail=2.65, grey_dch=0.50,
              ramp_dl=3.0),
       ["worst5_de00_avg", "ramps_30_70_dl_max"]),
    _d("2027-02-16_100000", "2027-02-16T10:00:00",
       "Both come back",
       "The hardest colours settle and the ramp step is 1.0 out, inside its "
       "2.0. Both rows recover on the same date.",
       Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.60, grey_dch=0.50,
              ramp_dl=1.0),
       []),
]


# ---------------------------------------------------------------------------
# Building a run
# ---------------------------------------------------------------------------
#: What a run demonstrates about the limit lock, and the sentence that says so.
#:
#: These sentences are NOT written by hand into a description. A challenge
#: round found run3 of the first project describing itself as "Limits bound and
#: LOCKED" when ``is_locked()`` returned False for it, because the lock rule had
#: since gained a second condition and the prose had not moved. Shared demo data
#: that misdescribes itself is worse than none: every later round is told to
#: trust it. So the sentence is derived from ``RunPlan.lock`` and ``build_run``
#: refuses to write a run whose real state disagrees with it.
#:
#: **REWRITTEN 2026-09-11 ON KNUT'S READING OF ONE.** He opened a Colour
#: summary out of this package and found under Report scope: *"Limits bound and
#: LOCKED: two or more dated verifications, and the lock was never lifted."*
#: Two things were wrong with it and he named both.
#:
#: *"Text written in any report shall only be factual and not refer to any bugs
#: or failures that were corrected."* "The lock was never lifted" reads as a
#: note about something that might have gone wrong and was not. It is a state,
#: and it is written as one now.
#:
#: *"What is the difference between bound and locked? Be specific in the
#: explanation, so that user understands that chosen limits are bound to chosen
#: 'ChromIQ default' thresholds as this was used for the first dated
#: verification run."* The old sentence used both words and defined neither, so
#: each sentence now NAMES THE SET and says what each word means, in that
#: order: bound is where the numbers came from, locked is whether they can
#: still be changed.
#:
#: ``{set}`` is filled from the run's own binding, so a sentence cannot name a
#: set the run is not judged against.
LOCK_SENTENCES = {
    "locked": "Limits: bound to {set}, and fixed. Bound means a copy of that "
              "set's numbers was taken when this run's first dated "
              "verification was measured, and every date of this run is "
              "judged against that copy. Fixed means the set can no longer be "
              "chosen here, because the run has two or more dated "
              "verifications and they are kept comparable.",
    "unlocked": "Limits: bound to {set}, and still open. Bound means a copy of "
                "that set's numbers was taken when this run's first dated "
                "verification was measured, and every date of this run is "
                "judged against that copy. Open means the set may still be "
                "chosen here; choosing another recalculates this run's dated "
                "reports and keeps the ones it replaces.",
    "one-date": "Limits: bound to {set}, and still open. Bound means a copy of "
                "that set's numbers was taken when this run's first dated "
                "verification was measured. Open means the set may still be "
                "chosen here, because one measurement is not yet a history to "
                "keep comparable.",
}


@dataclass
class RunPlan:
    description: str
    profile_chart: ChartRecipe
    verify_chart: ChartRecipe
    set_id: str
    dates: "list[Date]"
    edited_limits: "dict[str, float] | None" = None
    unlocked: bool = False
    note: str = ""
    lock: str = "locked"
    #: Which of the six documents this run is verified with. Left at the
    #: default it is NOT written to meta.json at all, which is the state
    #: every project made before the pulldown existed is in, and which the
    #: report reads back as Full colour check. A run that names another type
    #: has it written, exactly as choosing it in the window does.
    report_type: str = "t2_full_colour_check"
    #: Extra types to ALSO write a saved report of, on the run's first date.
    #: Knut, 2026-09-11: *"the user may have several uses for different
    #: reports"*, so a run may hold reports of several types and the window's
    #: "Already generated for this run" line counts them off the disk. Nothing
    #: in the package demonstrated that until this existed.
    also_generate: "tuple[str, ...]" = ()
    #: How the dated sheets of this run were printed: "through-profile" (the
    #: ordinary verification), "raw" (a drift check, which the report refuses
    #: to grade against profile accuracy), or "none" (nobody recorded it, which
    #: puts a numbered note on the grey rows). See `write_print_record`.
    print_colour: str = "through-profile"
    #: WHAT CHROMIQ'S OWN RULE MUST ANSWER ABOUT THIS RUN'S VERIFICATION
    #: CHART. Every verification chart in the package is offered to
    #: `workflow.control_strip.declare_for_chart`, exactly as the Create Chart
    #: tab offers one it has just filed, so there is no flag for "declare a
    #: strip here": the app decides, and this says what the app is expected to
    #: decide. A plan that expects the wrong thing stops the build, so a
    #: change to the ladder or to a chart recipe cannot quietly turn a
    #: demonstrated row into an undemonstrated one.
    #:
    #: One of `control_strip.OUTCOME_WRITTEN` or `OUTCOME_TOO_FEW`.
    expect_strip: str = "written"
    #: Whether this chart is expected to fill enough rungs for the
    #: 95th-percentile row as well (S2w: 20 of them). A chart that declares a
    #: strip and cannot reach twenty is its own demonstration, so it is stated
    #: rather than discovered.
    expect_strip_p95: bool = True
    #: The paper this run's simulated printer prints on (#182 K29): a key of
    #: `PAPER_CLASSES`, or "" for the pack's default matte paper.
    paper_class: str = ""

    @property
    def set_name(self) -> str:
        """The English label of the set this run is bound to."""
        from workflow.compliance_sets import SET_BY_ID
        s = SET_BY_ID.get(self.set_id)
        name = s.label if s else self.set_id
        return name + (", with limits edited on this run" if self.edited_limits
                       else "")

    @property
    def full_description(self) -> str:
        """The run's description with its limit state appended, in that order.

        The sentence NAMES THE SET, on Knut's 2026-09-11 reading: a paragraph
        that uses "bound" and "locked" without saying what either means, or
        what the run is bound TO, tells a reader nothing they can act on.
        """
        return f"{self.description} {LOCK_SENTENCES[self.lock]}".format(
            set=self.set_name)

    def lock_complaint(self) -> str:
        """Why this plan cannot produce the lock state it claims, or ""."""
        n = len(self.dates)
        if self.lock not in LOCK_SENTENCES:
            return f"unknown lock state {self.lock!r}"
        if self.lock == "one-date":
            if n != 1:
                return f"claims one-date and has {n} dated verifications"
            if self.unlocked:
                return "claims one-date and also lifts the lock, which says two things"
        elif n < 2:
            return f"claims {self.lock!r} and has only {n} dated verification(s)"
        elif self.unlocked != (self.lock == "unlocked"):
            return (f"claims {self.lock!r} with unlocked={self.unlocked}")
        return ""


from workflow.measurement_report import (KIND_PROFILING,     # noqa: E402
                                         KIND_VERIFICATION)


def file_report(rep: dict, ti3: Path, run, kind: str, when: str, *,
                type_id: str = "", n: int = 1) -> Path:
    """Save *rep* beside *ti3* exactly as the app saves its automatic report.

    `TabMeasure._maybe_save_measurement_report` is the model, step for step:
    the verdict is already stamped by the caller; the type is the run's,
    through the one rule that knows which types a kind of measurement may
    have (`report_type_default_for`, K13: a profiling sheet's report is the
    Printing record, a verification's never is); and the file carries a
    DOCUMENT BLOCK of its own, "One date", both tick boxes off (B8-388,
    B8-392), which is what makes the report window name it
    "<created> · <type> · <set> · One date" and restore its settings from the
    file rather than guess them.

    Two things differ from a live measurement, both on purpose. The file is
    named after the MEASUREMENT's date, not the second this script ran, so the
    list reads as a history; and *type_id* lets a run hold a second document
    of another type of the same sheet, which in the app is a second press of
    Generate. A type the kind may not have is refused here, before anything is
    written, rather than shipped for a reader to find.
    """
    from core.file_manager import reports_subdir
    from workflow.measurement_report import (SCOPE_ONE_DATE,
                                             document_measurement_key,
                                             new_document_id, report_type,
                                             report_types_for_kind,
                                             rewrite_report, set_report_type,
                                             stamp_document,
                                             stamp_report_type)
    from workflow.run_compliance import report_type_default_for
    stamp_report_type(rep, run)
    tid = type_id or report_type_default_for(run, "", kind)
    if tid not in report_types_for_kind(kind):
        raise SystemExit(
            f"{run.id if run is not None else ti3}: a {kind} measurement may "
            f"not have a {tid!r} report (K13). Change the plan.")
    if tid != report_type(rep):
        set_report_type(rep, tid)
    when_dt = datetime.fromisoformat(when)
    created = str(rep.get("created") or "")
    stamp_document(
        rep, doc_id=new_document_id(when_dt + timedelta(seconds=n - 1)),
        created=(when_dt + timedelta(seconds=n - 1)).isoformat(
            timespec="seconds"),
        type_id=report_type(rep), compliance=rep.get("compliance"),
        detail=False, scope=SCOPE_ONE_DATE,
        measurements=[{"dir": str(ti3.parent), "created": created,
                       "ti3": ti3.name,
                       "key": document_measurement_key(ti3.parent, created,
                                                       ti3.name)}])
    reports = reports_subdir(ti3.parent)
    reports.mkdir(parents=True, exist_ok=True)
    for old in (reports.glob("report_*.json") if n <= 1 else ()):
        old.unlink()
    name = f"report_{when_dt:%Y-%m-%d_%H-%M-%S}" + ("" if n <= 1 else f"_{n}")
    return rewrite_report(reports / f"{name}.json", rep)


#: K23: the project that shows where every kind of report lives.
FOLDERS_PROJECT = "Report-Limits-Report-Folders"
#: K25: a second project, so "Report shown" can be grouped by project.
FOLDERS_OTHER_PROJECT = "Report-Limits-Report-Folders-Second"

#: What `seed_report_folders` wrote, as lines for the README. Filled at build
#: time from what is really on disk, never typed in by hand.
FOLDERS_MANIFEST: "list[str]" = []


def seed_report_folders(root: Path,
                        other: "Path | None" = None) -> "list[str]":
    """Give Report-Limits-Report-Folders every place a report can live (K23).

    Knut, 2026-09-23, #182: *"Make sure the demo projects have created runs
    and projects that tests all variations of the above locations of reports
    and report types and run type."* The runs already hold, from `build_run`,
    one report of one date of every verification type and each profiling
    sheet's Printing record. This adds, with the app's own functions and in
    the app's own shapes:

    * a report of ALL three dates of run1 (Full colour check) and one of TWO
      of them (Grey and tone check): a document file in
      `run1/verifications/reports/` and a verdict record in each date;
    * a LEGACY report of two dates, written the way beta 36 wrote it: one
      file per date sharing an id, no role, no document file;
    * a DELETED report of two dates: its document file already moved into
      `run1/verifications/old/<stamp>/` the way Delete moves it, its records
      left in the dates, so nothing of it may be listed or counted;
    * a report across run1 and run2 of verifications (Full colour check) and
      one of the two profiling sheets (Printing record), both in the
      project's own `reports/`;
    * on run2's second date, a report saved by an older ChromIQ with no
      document record at all.

    Returns the README lines, which name each file it wrote.
    """
    import re as _re
    from core.file_manager import REPORTS_DIRNAME, VERIFICATIONS_DIRNAME
    from workflow.measurement_report import (
        REPORT_TYPE_GREY as _GREY, REPORT_TYPE_RECORD as _RECORD,
        ROLE_RECORD, SCOPE_ALL_DATES, SCOPE_MULTIPLE_DATES, document_file,
        document_home, document_measurement_key, new_document_id,
        report_type, rewrite_report, set_report_type, stamp_document)
    runs = sorted((root / "runs").glob("run*"), key=lambda p: p.name)
    run1, run2 = runs[0], runs[1]

    def dates(rd):
        return sorted(d for d in (rd / VERIFICATIONS_DIRNAME).iterdir()
                      if d.is_dir() and _re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{6}",
                                                      d.name))

    def base(folder):
        """The measurement's own report, as `build_run` filed it."""
        first = sorted((folder / REPORTS_DIRNAME).glob("report_*.json"))[0]
        return json.loads(first.read_text(encoding="utf-8"))

    def member(folder, rep):
        return {"dir": str(folder), "created": str(rep.get("created") or ""),
                "ti3": str(rep.get("ti3") or ""),
                "key": document_measurement_key(folder,
                                                str(rep.get("created") or ""),
                                                str(rep.get("ti3") or ""))}

    def free(folder, when):
        folder.mkdir(parents=True, exist_ok=True)
        stem = f"report_{when:%Y-%m-%d_%H-%M-%S}"
        path, n = folder / f"{stem}.json", 2
        while path.exists():
            path, n = folder / f"{stem}_{n}.json", n + 1
        return path

    lines: "list[str]" = []

    def rel(p):
        return str(Path(p).relative_to(root.parent))

    def write(folders, type_id, when, *, legacy=False, what=""):
        when_dt = datetime.fromisoformat(when)
        reps = [base(f) for f in folders]
        members = [member(f, r) for f, r in zip(folders, reps)]
        doc_id = new_document_id(when_dt)
        one_run_of_dates = (
            all(f.parent.name == VERIFICATIONS_DIRNAME for f in folders)
            and len({str(f.parent) for f in folders}) == 1)
        scope = (SCOPE_ALL_DATES if one_run_of_dates and len(folders)
                 == len(dates(folders[0].parent.parent))
                 else SCOPE_MULTIPLE_DATES)
        written = []
        for f, rep in zip(folders, reps):
            rep = json.loads(json.dumps(rep))
            rep.pop("document", None)
            if type_id != report_type(rep):
                set_report_type(rep, type_id)
            stamp_document(rep, doc_id=doc_id, created=when, type_id=type_id,
                           compliance=rep.get("compliance"), detail=False,
                           measurements=members, scope=scope,
                           role="" if legacy else ROLE_RECORD)
            written.append(rewrite_report(free(f / REPORTS_DIRNAME, when_dt),
                                          rep))
        doc_path = None
        if not legacy:
            body = document_file(doc_id=doc_id, created=when, type_id=type_id,
                                 compliance=reps[0].get("compliance"),
                                 detail=False, measurements=members,
                                 scope=scope)
            doc_path = rewrite_report(free(document_home(folders), when_dt),
                                      body)
        lines.append(f"  {what}")
        if doc_path is not None:
            lines.append(f"      the report:        {rel(doc_path)}")
        for p in written:
            lines.append(f"      {'a file of it:' if legacy else 'verdict record:'}"
                         f"     {rel(p)}")
        return doc_path

    d1, d2 = dates(run1), dates(run2)
    write(d1[:2], REPORT_TYPE_FULL, "2026-12-20T09:00:00", legacy=True,
          what="LEGACY, several dates of run1, written as beta 36 did "
               "(listed and counted once, never moved):")
    gone = write([d1[0], d1[2]], REPORT_TYPE_FULL, "2026-12-20T09:30:00",
                 what="DELETED, two dates of run1 (not listed, not counted; "
                      "its records stay):")
    old = (run1 / VERIFICATIONS_DIRNAME / "old" / "2026-12-20_094500")
    old.mkdir(parents=True, exist_ok=True)
    shutil.move(str(gone), str(old / gone.name))
    lines.append(f"      moved by Delete to: {rel(old / gone.name)}")
    write(d1, REPORT_TYPE_FULL, "2026-12-21T09:00:00",
          what="ALL DATES of run1, Full colour check:")
    write(d1[1:], _GREY, "2026-12-21T09:30:00",
          what="TWO DATES of run1, Grey and tone check:")
    write([d1[-1], d2[0]], REPORT_TYPE_FULL, "2026-12-30T09:00:00",
          what="ACROSS run1 and run2, verifications, Full colour check:")
    write([run1, run2], _RECORD, "2026-12-30T09:30:00",
          what="ACROSS run1 and run2, profiling sheets, Printing record:")
    # A REPORT SAVED BEFORE THE DOCUMENT RECORD EXISTED (a 4.2 file).
    older = base(d2[1])
    older.pop("document", None)
    p = rewrite_report(free(d2[1] / REPORTS_DIRNAME,
                            datetime.fromisoformat("2026-12-29T12:00:00")),
                       older)
    lines.append("  OLDER CHROMIQ, one date of run2, no document record:")
    lines.append(f"      the report:        {rel(p)}")
    # **AND A SECOND PROJECT (K25).** Knut, 2026-09-23: "Report shown" is
    # grouped by project and run, and *"IF a report has included multiple
    # measurements belonging to more than one project, then those reports are
    # grouped in a separate group-heading ... 'Reports including multiple
    # projects'"*. So the second project holds a report of its two dates, and
    # two reports span both projects: `document_home` files those in the
    # projects' common folder, which in the pack is its own `reports/`.
    if other is not None and (other / "runs").is_dir():
        o1 = sorted((other / "runs").glob("run*"), key=lambda p: p.name)[0]
        od = dates(o1)
        write(od, REPORT_TYPE_FULL, "2027-01-13T09:00:00",
              what="ALL DATES of the second project's run1, Full colour check:")
        write([d1[-1], od[0]], REPORT_TYPE_FULL, "2027-01-14T09:00:00",
              what="ACROSS TWO PROJECTS, verifications, Full colour check "
                   "(in the pack's own reports folder):")
        write([run1, o1], _RECORD, "2027-01-14T09:30:00",
              what="ACROSS TWO PROJECTS, profiling sheets, Printing record "
                   "(in the pack's own reports folder):")
    return lines


#: #182 beta 39 (Knut 5794078008): the projects that carry a calibration, in
#: order. Two are the report-folder projects; the third makes "Multiple cals"
#: reachable (a report of two calibrations while three are listed).
CAL_PROJECTS = (FOLDERS_PROJECT, FOLDERS_OTHER_PROJECT,
                "Report-Limits-Report-Types")

#: What `seed_calibrations` wrote, as README lines. Filled at build time.
CAL_MANIFEST: "list[str]" = []


def seed_calibrations(dest: Path) -> "list[str]":
    """Give the report-folder projects a measured calibration and its reports
    (#182 beta 39).

    Knut, 5794078008: Run type Calibration makes reports after all, every type
    but the Printing record, *"stored and read from project_name/cal/
    reports/"*, and a report across projects *"in the <ChromIQ default
    folder>/reports/"*, named "Cal", "Multiple cals" or "All cals". So each
    project of `CAL_PROJECTS` that is in the pack gets:

    * ``cal/<project>-cal.ti3`` (and ``.ti2``): its run1 profiling sheet,
      dated as a calibration of its own, since a calibration chart is printed
      raw exactly as that sheet was;
    * the report ChromIQ writes by itself after a calibration measurement,
      "Cal", the Preferences default type (Full colour check), judged against
      the default set, in ``cal/reports/``.

    The first project's calibration also holds a Colour summary of it, and a
    Printing record the way beta 38's automatic report could write one (never
    listed or counted under Calibration). Then, with the app's own functions:
    a report of the first two calibrations ("Multiple cals" while three are
    in the pack) and one of all three ("All cals"), each a document file in
    the pack's own ``reports/`` and a verdict record in each ``cal/reports/``.
    """
    from core.file_manager import Calibration, REPORTS_DIRNAME
    from workflow.measurement_report import (
        KIND_CALIBRATION, REPORT_TYPE_FULL, REPORT_TYPE_RECORD,
        REPORT_TYPE_SUMMARY, ROLE_RECORD, SCOPE_ALL_DATES,
        SCOPE_MULTIPLE_DATES, build_report, document_file, document_home,
        document_measurement_key, new_document_id, rewrite_report,
        stamp_document, stamp_verdict)
    from workflow.run_compliance import run_limits
    lines: "list[str]" = []
    lim = run_limits(None, {}, "chromiq_default")

    def rel(p):
        return str(Path(p).relative_to(dest))

    cals: "list[tuple[Path, Path, dict]]" = []
    for i, name in enumerate(CAL_PROJECTS):
        root = dest / name
        sheet = root / "runs" / "run1" / f"{name}.ti3"
        if not (root / "project.json").is_file() or not sheet.is_file():
            continue
        cal = Calibration(root)
        cal.ensure_dir()
        ti3 = cal.dir / f"{cal.stem}.ti3"
        kept = [l for l in sheet.read_text(encoding="utf-8").splitlines()
                if not l.startswith(('KEYWORD "CHROMIQ_MEASURED"',
                                     "CHROMIQ_MEASURED ",
                                     "TARGET_INSTRUMENT "))]
        ti3.write_text("\n".join(kept) + "\n", encoding="utf-8")
        ti2 = sheet.with_suffix(".ti2")
        if ti2.is_file():
            shutil.copy2(ti2, cal.dir / f"{cal.stem}.ti2")
        when = f"2027-01-2{i}T09:00:00"
        stamp_profiling(ti3, when)
        rep = build_report(ti3, argyll_bin=str(ARGYLL))
        stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                      set_label=lim.label_en, edited=lim.edited)
        path = file_report(json.loads(json.dumps(rep)), ti3, None,
                           KIND_CALIBRATION, when)
        lines.append(f"  {name}: its calibration, measured {when[:10]}")
        lines.append(f"      the measurement:   {rel(ti3)}")
        lines.append(f"      the automatic report (Cal, Full colour check): "
                     f"{rel(path)}")
        if i == 0:
            p2 = file_report(json.loads(json.dumps(rep)), ti3, None,
                             KIND_CALIBRATION, when, type_id=REPORT_TYPE_SUMMARY,
                             n=2)
            lines.append(f"      a Colour summary (Cal): {rel(p2)}")
            p3 = file_report(json.loads(json.dumps(rep)), ti3, None, None,
                             when, type_id=REPORT_TYPE_RECORD, n=3)
            lines.append(f"      a Printing record as beta 38 could write it "
                         f"(never listed under Calibration): {rel(p3)}")
        cals.append((cal.dir, ti3, rep))

    def across(members, scope, when, what):
        when_dt = datetime.fromisoformat(when)
        doc_id = new_document_id(when_dt)
        recorded = [{"dir": str(d), "created": str(r.get("created") or ""),
                     "ti3": t.name,
                     "key": document_measurement_key(
                         d, str(r.get("created") or ""), t.name)}
                    for d, t, r in members]
        lines.append(f"  {what}")
        for d, t, r in members:
            body = json.loads(json.dumps(r))
            body.pop("document", None)
            body["report_type"] = REPORT_TYPE_FULL
            stamp_document(body, doc_id=doc_id, created=when,
                           type_id=REPORT_TYPE_FULL,
                           compliance=body.get("compliance"), detail=False,
                           measurements=recorded, scope=scope,
                           role=ROLE_RECORD)
            out = d / REPORTS_DIRNAME / f"report_{when_dt:%Y-%m-%d_%H-%M-%S}.json"
            rewrite_report(out, body)
            lines.append(f"      verdict record:    {rel(out)}")
        doc = document_file(doc_id=doc_id, created=when,
                            type_id=REPORT_TYPE_FULL,
                            compliance=members[0][2].get("compliance"),
                            detail=False, measurements=recorded, scope=scope)
        home = document_home([d for d, _t, _r in members])
        home.mkdir(parents=True, exist_ok=True)
        out = home / f"report_{when_dt:%Y-%m-%d_%H-%M-%S}.json"
        rewrite_report(out, doc)
        lines.append(f"      the report:        {rel(out)}")

    if len(cals) >= 2:
        across(cals[:2],
               SCOPE_MULTIPLE_DATES if len(cals) > 2 else SCOPE_ALL_DATES,
               "2027-01-25T09:00:00",
               "ACROSS TWO CALIBRATIONS, Full colour check ("
               + ("Multiple cals" if len(cals) > 2 else "All cals") + "):")
    if len(cals) >= 3:
        across(cals, SCOPE_ALL_DATES, "2027-01-26T09:00:00",
               "ACROSS ALL THREE CALIBRATIONS, Full colour check (All cals):")
    return lines


#: See `--survey` in `main`.
RENAMED_MANIFEST: "list[str]" = []


def seed_renamed(dest: Path) -> "list[str]":
    """Write a report across two projects under one project's OLD name, then
    rename that project with the app's own rename (#182 K29, "moved and
    renamed projects").

    The report is a Full colour check of the last date of
    Report-Limits-Before-Rename/run1 and the first date of
    Report-Limits-Paper-Classes/run1, filed where the app files a report of
    several projects (`document_home`, the pack's own ``reports/``), with a
    verdict record in each date. Then the folder is moved and
    `Project.rename` renames its files and records the old name in
    ``former_names``. The report still names the old folder, so a window on
    Report-Limits-Renamed lists it only if the app matches a report by every
    name the project has had (`names_of_project`).

    Returns the README lines. Does nothing when either project is missing
    (an ``--only`` build).
    """
    import re as _re
    from core.file_manager import (Project, REPORTS_DIRNAME,
                                   VERIFICATIONS_DIRNAME)
    from workflow.measurement_report import (
        ROLE_RECORD, SCOPE_MULTIPLE_DATES, document_file, document_home,
        document_measurement_key, new_document_id, report_type,
        rewrite_report, set_report_type, stamp_document)
    old = dest / RENAMED_FROM
    other = dest / "Report-Limits-Paper-Classes"
    if not (old / "runs").is_dir() or not (other / "runs").is_dir():
        return []

    def dates(rd):
        return sorted(d for d in (rd / VERIFICATIONS_DIRNAME).iterdir()
                      if d.is_dir() and _re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{6}",
                                                      d.name))

    folders = [dates(old / "runs" / "run1")[-1],
               dates(other / "runs" / "run1")[0]]
    when = "2029-12-01T09:00:00"
    when_dt = datetime.fromisoformat(when)
    reps = [json.loads(sorted((f / REPORTS_DIRNAME).glob("report_*.json"))[0]
                       .read_text(encoding="utf-8")) for f in folders]
    members = [{"dir": str(f), "created": str(r.get("created") or ""),
                "ti3": str(r.get("ti3") or ""),
                "key": document_measurement_key(f, str(r.get("created") or ""),
                                                str(r.get("ti3") or ""))}
               for f, r in zip(folders, reps)]
    doc_id = new_document_id(when_dt)
    lines = ["  ACROSS TWO PROJECTS, written while one of them was still "
             f"called {RENAMED_FROM}:"]
    for f, rep in zip(folders, reps):
        rep = json.loads(json.dumps(rep))
        rep.pop("document", None)
        if report_type(rep) != REPORT_TYPE_FULL:
            set_report_type(rep, REPORT_TYPE_FULL)
        stamp_document(rep, doc_id=doc_id, created=when,
                       type_id=REPORT_TYPE_FULL,
                       compliance=rep.get("compliance"), detail=False,
                       measurements=members, scope=SCOPE_MULTIPLE_DATES,
                       role=ROLE_RECORD)
        p = rewrite_report(f / REPORTS_DIRNAME
                           / f"report_{when_dt:%Y-%m-%d_%H-%M-%S}.json", rep)
        lines.append(f"      verdict record:     {p.relative_to(dest)}")
    home = document_home(folders)
    home.mkdir(parents=True, exist_ok=True)
    body = document_file(doc_id=doc_id, created=when, type_id=REPORT_TYPE_FULL,
                         compliance=reps[0].get("compliance"), detail=False,
                         measurements=members, scope=SCOPE_MULTIPLE_DATES)
    doc = rewrite_report(home / f"report_{when_dt:%Y-%m-%d_%H-%M-%S}.json",
                         body)
    lines.append(f"      the report:         {doc.relative_to(dest)}")
    # THE RENAME, the way `FileManager.rename_existing_project` does it.
    new = dest / RENAMED_PROJECT
    shutil.move(str(old), str(new))
    Project.load(new).rename(new.name)
    lines.append(f"  then {RENAMED_FROM} was renamed to {RENAMED_PROJECT} with "
                 f"ChromIQ's own rename; the report still names the old "
                 f"folder, and project.json keeps the old name in "
                 f"former_names.")
    return lines


SURVEY = False
SURVEY_FAULTS: "list[str]" = []


def build_run(proj, run, plan: RunPlan, cache_root: Path,
              results: list) -> None:
    from workflow.compliance_sets import Limit, row_verdict, set_summary
    from workflow.measurement_report import (REPORT_TYPE_DEFAULT, build_report,
                                             rewrite_report, save_report,
                                             row_values, set_report_type,
                                             stamp_verdict)
    from workflow.run_compliance import (bind_run, run_limits, set_run_limits,
                                         set_run_report_type, set_run_unlocked)

    run.ensure_dir()
    stem = run.stem
    print(f"  {run.id}: profiling chart, {plan.profile_chart.label}")
    make_chart(run.dir, stem, plan.profile_chart, cache_root)
    build_profile(run.dir, stem, paper_lab_of(plan.paper_class))
    icc = run.built_profile_icc()

    print(f"  {run.id}: verification chart, {plan.verify_chart.label}")
    vstem_ = run.verify_stem
    gsel = None
    if isinstance(plan.verify_chart, GamutChartRecipe):
        gsel = make_gamut_chart(run.verifications_dir, vstem_,
                                plan.verify_chart, icc)
    elif isinstance(plan.verify_chart, GridChartRecipe):
        make_grid_chart(run.verifications_dir, vstem_, plan.verify_chart)
    else:
        make_chart(run.verifications_dir, vstem_, plan.verify_chart, cache_root)
    # EACH CHART'S OWN CREATE CHART SETTINGS, where the app keeps them (F12).
    record_chart_settings(run.dir, plan.profile_chart.paper,
                          _targen_settings(plan.profile_chart),
                          instrument=getattr(plan.profile_chart, "instrument",
                                             PRINTTARG_INSTRUMENT))
    record_chart_settings(run.verifications_dir, plan.verify_chart.paper,
                          _targen_settings(plan.verify_chart),
                          mode=("gamut" if gsel is not None else "manual"),
                          instrument=getattr(plan.verify_chart, "instrument",
                                             PRINTTARG_INSTRUMENT))

    # WHAT THE REPORT WILL USE AS THE REFERENCE, decided once, here, from the
    # same fact the report decides it from: a `<stem>-reference.ti3` beside the
    # chart. Everything downstream — the design, the corner rows, the strip —
    # reads this and not the .ti2's own XYZ.
    from workflow.gamut_target import (corner_sample_ids,
                                       read_colorimetric_reference)
    cref_labs = None
    corner_ids: "set[str]" = set()
    corner_devices: "dict[str, tuple]" = {}
    if gsel is not None:
        cref = read_colorimetric_reference(
            run.verifications_dir / f"{vstem_}-reference.ti3")
        cref_labs = cref["labs"]
        # The ink amount the chart recorded for each sample, which is how the
        # report decides WHICH declared id is which corner. Read out of the
        # reference file, like the report, and not re-derived here.
        corner_devices = dict(cref.get("devices") or {})
        corner_ids = {str(i) for i in corner_sample_ids(gsel)}

    # THE APP DECLARES THE STRIP, on every verification chart, because the app
    # declares one on every verification chart it files (B8-405). What the
    # plan carries is what the app is expected to ANSWER, checked here, so a
    # chart that stops filling the ladder cannot silently take three rows out
    # of the package.
    decl = declare_control_strip(run.verifications_dir, vstem_)
    strip_ids: "list[str]" = list(decl.selection.ids) if decl.written else []
    if decl.outcome != plan.expect_strip:
        raise SystemExit(
            f"{run.id}: the plan expects ChromIQ to answer "
            f"{plan.expect_strip!r} for this chart's control strip and it "
            f"answered {decl.outcome!r} ({decl.selection.n} of "
            f"{len(_strip_slots())} rungs filled; missing "
            f"{decl.selection.missing}). Fix the plan or the chart recipe, "
            f"never the declaration.")
    if decl.written and decl.selection.p95_ready != plan.expect_strip_p95:
        raise SystemExit(
            f"{run.id}: the plan expects the 95th-percentile control-strip "
            f"row to be {'available' if plan.expect_strip_p95 else 'withheld'} "
            f"on this chart and ChromIQ filled {decl.selection.n} rungs, "
            f"which makes it "
            f"{'available' if decl.selection.p95_ready else 'withheld'}.")

    meta = run.load_meta()
    # THE DESCRIPTION IS THE STORY AND NOTHING ELSE (B8-807, round 3B F30).
    # It used to end with the run's lock state, frozen in English at build
    # time: a German UI printed it untranslated under "Run description", and it
    # went false the moment a reader did what the README invites (choose
    # another set on an open run, lift a lock). The window states the LIVE
    # state; `full_description` stays only as the README's and the tests'
    # statement of what each plan declares.
    meta.description = plan.description
    meta.instrument = (INSTRUMENT_I1 if getattr(plan.verify_chart, "instrument",
                                                "CM") == "i1" else INSTRUMENT)
    meta.paper = paper_name_of(plan.paper_class)
    meta.status = "complete"
    meta.verify_chart_notes = plan.note
    run.save_meta(meta)

    # THE DEFAULT IS WRITTEN BY NOT WRITING IT. A run that never chose a type
    # is the state every project made before the pulldown existed is in, and
    # the report renders it as Full colour check; storing the id would hide
    # that half of the behaviour behind a value nobody ever set.
    if plan.report_type != REPORT_TYPE_DEFAULT:
        set_run_report_type(run, plan.report_type)

    # The binding. bind_run copies the set's numbers onto the run, exactly as
    # the first verification measurement does in the app.
    limits_rec = bind_run(run, plan.set_id, {},
                          when=datetime.fromisoformat(plan.dates[0].when))
    if plan.edited_limits:
        edited = dict(limits_rec.limits)
        for rid, v in plan.edited_limits.items():
            base = edited.get(rid)
            edited[rid] = (Limit.should(v) if (base is not None and base.is_should)
                           else Limit.value(v))
        set_run_limits(run, edited)
        limits_rec = run_limits(run, {})
    if plan.unlocked:
        set_run_unlocked(run, True)
        limits_rec = run_limits(run, {})

    # THE RUN'S OWN MEASUREMENT GETS A DATE AND A SAVED REPORT, because the
    # app gives it both. `tab_measure._maybe_save_measurement_report` runs
    # after EVERY measurement, the profiling read included, so a project built
    # with "Save a measurement report after each measurement" ticked holds a
    # report beside the sheet the profile was built from. The package held one
    # only under each dated verification, so opening a run's own measurement
    # reached the report window's "nothing saved here" fall-back and the page
    # told the reader the verdict had been lost. Knut, 2026-09-13: *"Make sure
    # all verdicts exist in the demo package"* and *"Why is the verdict and
    # measurements not kept as part of the demo data created, so that it is a
    # real test?"*
    #
    # It is stamped a week before the first verification, because that is the
    # order the two happen in: you print and measure the profiling chart, build
    # the profile, and only then verify it. Undated, the column was headed with
    # whatever day the package was unpacked.
    prof_when = (datetime.fromisoformat(plan.dates[0].when)
                 - timedelta(days=7)).isoformat(timespec="seconds")
    prof_ti3 = run.dir / f"{stem}.ti3"
    stamp_profiling(prof_ti3, prof_when, meta.instrument)
    prof_rep = build_report(prof_ti3, argyll_bin=ARGYLL)
    pw_fault = _paper_white_fault(prof_ti3, prof_rep)
    if pw_fault:
        raise SystemExit(pw_fault)
    stamp_verdict(prof_rep, limits_rec.limits, set_id=limits_rec.set_id,
                  set_label=limits_rec.label_en, edited=limits_rec.edited)
    # A PROFILING MEASUREMENT'S ONLY REPORT IS THE PRINTING RECORD (K13,
    # B8-787). Until beta 36 this sheet was stamped with the run's own graded
    # type, which is the verification's, and Knut opened a profiling run and
    # found a Full colour check where the app now offers only the record.
    file_report(prof_rep, prof_ti3, run, KIND_PROFILING, prof_when)

    vstem = run.verify_stem
    if cref_labs is None:
        gamut = in_gamut_flags(run.verifications_dir / f"{vstem}.ti2", icc)
        print(f"  {run.id}: {sum(gamut.values())} of {len(gamut)} chart colours "
              f"are within the profile's gamut and therefore judged")
    else:
        # A COLORIMETRIC REFERENCE IS IN GAMUT BY CONSTRUCTION, and the report
        # says so: `build_report` computes the in/out split only against the
        # DESIGN reference. Asking for one here would split the design on a
        # line the report never draws, and every band would land in the wrong
        # place.
        gamut = None
        print(f"  {run.id}: colorimetric reference, {len(cref_labs)} aims, "
              f"{len(corner_ids)} of them cube corners; no gamut split")
    if decl.written:
        print(f"  {run.id}: ChromIQ declared a control strip of "
              f"{decl.selection.n} of {len(_strip_slots())} rungs"
              f"{'' if decl.selection.p95_ready else ', too few for the 95th percentile row'}")
    else:
        print(f"  {run.id}: ChromIQ declared NO control strip "
              f"({decl.outcome}, {decl.selection.n} rungs); the three "
              f"strip rows read their reason on every date of this run")
    for date in plan.dates:
        v = run.verification(date.vid)
        v.ensure_dir()
        work = v.dir / "_work"
        work.mkdir(exist_ok=True)
        for ext in (".ti1", ".ti2"):
            shutil.copy2(run.verifications_dir / f"{vstem}{ext}", work / f"{vstem}{ext}")
        for extra in (f"{vstem}-reference.ti3", f"{vstem}.control-strip.json"):
            src = run.verifications_dir / extra
            if src.is_file():
                shutil.copy2(src, work / extra)
        ti3 = fakeread(work, vstem, icc)
        # WHICH YARDSTICK THE REPORT WILL USE, asked of the same two facts the
        # report asks: only a sheet printed THROUGH the profile with a white
        # mapping intent is judged media-relative. A raw sheet and a sheet with
        # no record of its printing are both judged in absolute Lab.
        # A COLORIMETRIC reference is judged absolute whatever the printing,
        # because that reference already includes the paper.
        predicted = apply_design(
            ti3, work / f"{vstem}.ti2", date.design, gamut,
            relative=plan.print_colour == "through-profile" and cref_labs is None,
            ref_labs=cref_labs, corner_ids=corner_ids,
            corner_devices=corner_devices, strip_ids=strip_ids)
        stamp(ti3, date.when, meta.instrument)
        shutil.move(str(ti3), str(v.dir / f"{vstem}.ti3"))
        cdir = snapshot(v.dir, vstem, work)
        write_print_record(cdir, vstem, date.when, icc.name, plan.print_colour)
        shutil.rmtree(work)

        # The report, built by the app's own code, saved under the measurement
        # date rather than the moment this script ran.
        rep = build_report(v.measurement_ti3, argyll_bin=ARGYLL)
        # THE PAPER WHITE IS THE CHART'S PAPER, on every date (B8-807).
        pw_fault = _paper_white_fault(v.measurement_ti3, rep)
        if pw_fault:
            raise SystemExit(pw_fault)
        stamp_verdict(rep, limits_rec.limits, set_id=limits_rec.set_id,
                      set_label=limits_rec.label_en, edited=limits_rec.edited)
        set_report_type(rep, plan.report_type)
        file_report(rep, v.measurement_ti3, run, KIND_VERIFICATION, date.when)

        # A RUN MAY HOLD REPORTS OF SEVERAL TYPES, and one in the package has
        # to, or the window's "Already generated for this run" line has nothing
        # to count. The suffix is `save_report`'s own, so `list_reports` and
        # `generated_report_types` see these exactly as they see a second click
        # of Generate report.
        #
        # EACH IS ITS OWN DOCUMENT, because each is its own press of Generate
        # in the app, and each is a type a verification may have (K13).
        extras = plan.also_generate if date is plan.dates[0] else ()
        for n, extra in enumerate(extras, start=2):
            other = json.loads(json.dumps(rep))
            other.pop("document", None)
            file_report(other, v.measurement_ti3, run, KIND_VERIFICATION,
                        date.when, type_id=extra, n=n)

        actual = _crossed_rows(rep, limits_rec.limits, row_values, row_verdict,
                               set_summary, plan.report_type, limits_rec.set_id)
        # WHAT THE SAME NUMBERS DO IN THE REPORT EVERYBODY KNOWS. For a run on
        # T3 or T4 the crossings above are about a document that hides rows or
        # withholds words, and a reader cannot tell from them whether the sheet
        # was good. Computed, never described, so the two can never drift.
        as_full = (None if plan.report_type == REPORT_TYPE_FULL else
                   _crossed_rows(rep, limits_rec.limits, row_values,
                                 row_verdict, set_summary, REPORT_TYPE_FULL,
                                 limits_rec.set_id))
        results.append({
            "project": "",
            "run": run.id,
            "set_id": limits_rec.set_id,
            "chart": ("gamut" if cref_labs is not None
                      else ("grid" if isinstance(plan.verify_chart,
                                                 GridChartRecipe)
                            else "ordinary")),
            "set": limits_rec.label_en + (" (edited for this run)"
                                          if limits_rec.edited else ""),
            "type": plan.report_type,
            "date": date.vid,
            "title": date.title,
            "story": date.story,
            "intended": list(date.expect),
            "actual": actual["crossed"],
            "verdict": actual["overall"],
            "reason": actual["reason"],
            "as_full": (None if as_full is None
                        else {"crossed": as_full["crossed"],
                              "verdict": as_full["overall"]}),
            "values": actual["values"],
            # The reason each row that carries no number gives, as the WINDOW
            # would show it (a row with no word is never drawn, so those are
            # already left out). The on-screen driver checks the page really
            # prints the sentence this names.
            "shown_reasons": actual["shown_reasons"],
            "predicted": predicted,
            # What the report took as paper white, and whether the chart has a
            # paper patch at all, for the README's paper section.
            "print": plan.print_colour,
            # A BORDER DATE (K29) MUST SAVE EXACTLY ITS NUMBER.
            "border": ({"row": BORDER_VALUES[date.vid][0],
                        "want": BORDER_VALUES[date.vid][1],
                        "got": actual["values"].get(
                            BORDER_VALUES[date.vid][0])}
                       if date.vid in BORDER_VALUES else None),
            # THE ROUTE (#182 K29): what else about this date differs from
            # another date that trips or passes the same row.
            "paper": plan.paper_class or "default",
            "paper_lab": list(paper_lab_of(plan.paper_class)),
            "chart_label": plan.verify_chart.label,
            "instrument": getattr(plan.verify_chart, "instrument", "CM"),
            "paper_white": dict(rep.get("paper_white") or {}),
            "has_paper_patch": bool(chart_white_locs(v.measurement_ti3, rep)),
        })
        # A STORY MAY NOT NAME A VERDICT THE REPORT DID NOT GIVE. The same
        # shape as the lock guard above, in the other field a reader trusts.
        # Found writing this project: one story said a row "reads FAIL" on a
        # run whose document withholds every word, so the README would have
        # printed the claim two lines above the computed word that denied it.
        flag = "OK " if sorted(actual["crossed"]) == sorted(date.expect) else "!! "
        if flag != "OK ":
            print(f"    !! {date.vid} values: " + ", ".join(
                f"{rid}={actual['values'].get(rid)}"
                for rid in sorted(set(actual["crossed"]) ^ set(date.expect))))
        said = story_verdicts(date.story)
        if said and actual["overall"] not in said:
            # --survey lists every such fault in one build instead of stopping
            # at the first, for the round that redesigns the dates; a pack
            # built that way is never shipped (main refuses to finish it).
            if SURVEY:
                SURVEY_FAULTS.append(
                    f"{run.id}/{date.vid}: story says {sorted(said)}, report "
                    f"says {actual['overall']}, crossed {actual['crossed']}")
                print(f"    !! STORY {SURVEY_FAULTS[-1]}")
            else:
                raise SystemExit(
                    f"{run.id}/{date.vid}: the story says {sorted(said)} and "
                    f"the report's word for the column is {actual['overall']}. "
                    f"A verdict word in a story is a claim about THIS "
                    f"document; say what another document does by pointing at "
                    f"the computed line, never by typing its word. It crossed "
                    f"{actual['crossed']}.")

        print(f"    {flag}{date.vid}  {actual['overall']:<5} "
              f"intended={date.expect} actual={actual['crossed']}")

    # The run is finished, so ask the SHIPPED rule what it made, rather than
    # trusting the plan. This is the check that was missing when the lock rule
    # gained its second condition and run3's description went on claiming a
    # state the code no longer produced.
    from workflow.run_compliance import is_bound, is_locked, measured_dates
    really = is_locked(run)
    if really != (plan.lock == "locked") or not is_bound(run):
        raise SystemExit(
            f"{run.id} claims lock={plan.lock!r} and its description says so, "
            f"but the app reads bound={is_bound(run)}, "
            f"dates={measured_dates(run)}, locked={really}. Fix the plan or "
            f"the sentence, never the description alone.")


def chart_white_locs(ti3: Path, rep: dict) -> "set[str]":
    """The patches of this sheet that ARE its paper, by the id the report
    records a paper white under (``SAMPLE_LOC`` when the file has one).

    A patch is paper when every device channel is at least `DEVICE_WHITE_MIN`,
    which is the same test `apply_design` uses to find the bare paper. On a
    From Profile Gamut chart the white CUBE CORNER the report reads is paper
    too, whatever device value the profile gave it. An empty answer means the
    chart has no paper patch at all (Strip-And-Gamut/run4's mid-tone grid),
    and then the report's "lightest patch" is simply the lightest colour.
    """
    from workflow.ti3_analysis import parse_ti3
    data = parse_ti3(ti3)
    ids = data.sample_locs or data.sample_ids
    out = {str(ids[i]) for i, px in enumerate(data.rgb)
           if min(float(v) for v in px) >= DEVICE_WHITE_MIN}
    if rep.get("reference_source") == "colorimetric":
        for c in rep.get("corners") or []:
            if c.get("name") == "W" and c.get("present") and c.get("loc"):
                out.add(str(c["loc"]))
    return out


def _paper_white_fault(ti3: Path, rep: dict) -> str:
    """Why the report's paper white on this sheet is NOT the chart's paper, or
    "" when it is (or when the chart has no paper patch to be).

    Round 3B, F13: Every-Limit-Set/run6's 2028-05-12 date designed the paper
    9.0 off its reference by lowering its L*, the paper fell under a saturated
    yellow of the same sheet, and the report recorded patch 208 (Lab
    97.14 / -27.36 / 92.98) as "paper white". The FAIL it proved was a
    detection artefact. Every date of every run is asked this now, and the
    build stops on the first that answers.
    """
    whites = chart_white_locs(ti3, rep)
    pw = rep.get("paper_white") or {}
    loc = str(pw.get("loc", ""))
    if not whites or loc in whites:
        return ""
    return (f"{ti3}: the report records patch {loc} (Lab "
            f"{pw.get('lab')}) as paper white, and the chart's paper is "
            f"{sorted(whites)}. A date that moves the paper must keep it the "
            f"lightest reading on the sheet.")


def story_verdicts(story: str) -> "set[str]":
    """The verdict words a date's story claims, if any.

    The five words are taken from the app rather than typed, so a sixth word
    would be caught here the moment it is added instead of walking past this
    check. Word boundaries, because "INFO" must not be found inside
    "information" and "PASS" must not be found inside "passes".
    """
    import re

    from workflow.compliance_sets import COND, FAIL, INFO, N_A, PASS
    words = (PASS, FAIL, COND, INFO, N_A)
    return {w for w in words
            if re.search(rf"(?<![A-Za-z0-9-]){re.escape(w)}(?![A-Za-z0-9-])",
                         story)}


def _crossed_rows(report, limits, row_values, row_verdict, set_summary,
                  type_id: str = "t2_full_colour_check",
                  set_id: str = "") -> dict:
    """Which rows the REAL report says are over their limit, IN THE DOCUMENT
    THE RUN PRODUCES.

    THE TYPE IS PART OF THE ANSWER, and it was not asked for until the package
    had runs that choose one. A Grey and tone check does not contain the colour
    rows, so a colour row crossing is not something a reader of that document
    can see; a Printing record contains every figure and judges none of them,
    so nothing in it crosses at all. Reporting the full report's crossings
    beside a run that produces neither document would be a table about a page
    nobody opens.

    The three rules are the window's own, taken from the same functions it
    calls: `rows_for_report_type` decides which rows the document is about
    (`measurement_report_dialog._keep_rows_for_type`), T4 withholds every word
    (`._ungrade`, `._column_summary`), and `applies_a_standard` decides whether
    the column carries a standard's caveat.

    **THE CAVEAT WAS HARD-CODED OFF, AND IT MATTERED THE DAY A COLUMN NEEDED
    IT.** This passed `set_is_iso=False` from the day it was written, which was
    true of every set the package used then: the two Custom columns held no
    numbers at all and could not be a run's set. The moment they could, this
    file's own README printed "none over a required limit; 3 not computed" for
    a column the WINDOW words differently, because a set named after a standard
    reads COND with the sentence that says its figures are applied to your
    chart and not to that standard's. A README that describes a column named
    after a standard without that sentence is the fault `applies_a_standard`
    exists to have stopped, arriving in the file that documents the package.
    """
    from workflow.compliance_sets import (COND, FAIL, ROW_BY_ID,
                                          SUMMARY_REASONS, applies_a_standard)
    from workflow.measurement_report import (REPORT_TYPE_RECORD, is_graded_sheet,
                                             rows_for_report_type)
    graded_sheet = is_graded_sheet(report)
    ungraded_by_type = type_id == REPORT_TYPE_RECORD
    keep = rows_for_report_type(type_id)
    vals = row_values(report)
    crossed, values, rows = [], {}, []
    shown_reasons: "dict[str, str]" = {}
    for rid, lim in limits.items():
        if rid not in ROW_BY_ID:
            continue
        if keep is not None and rid not in keep:
            continue
        info = vals.get(rid) or {}
        val = info.get("value")
        graded = graded_sheet if info.get("graded") is None else bool(info["graded"])
        word = row_verdict(lim, val, graded and not ungraded_by_type)
        # The row id travels with the pair, as it does in the two production
        # callers: the column's completeness arithmetic needs to know which
        # row an N-A came from (`compliance_sets.POPULATION_MAY_BE_ABSENT`).
        # Without it the demo pack would compute a different Overall from the
        # window it is meant to be a picture of.
        rows.append((lim, word, rid))
        if lim.is_numeric and val is not None:
            values[rid] = round(float(val), 3)
        if word in (FAIL, COND):
            crossed.append(rid)
        # THE REASONS A READER CAN ACTUALLY SEE. A row whose limit is `–` and
        # whose value is None carries no word, so the window never draws it
        # (CH-20) and the reason it holds reaches nobody. Counting those as
        # shown made the package's own coverage table claim a message was
        # demonstrated by a row that is not on the page.
        if word is not None and info.get("reason"):
            shown_reasons[rid] = info["reason"]
    summary = set_summary(
        rows, set_is_iso=applies_a_standard(set_id),
        graded=graded_sheet and not ungraded_by_type,
        ungraded_reason=(SUMMARY_REASONS["record_type"]
                         if ungraded_by_type and graded_sheet else ""))
    return {"crossed": sorted(crossed), "values": values,
            "overall": summary.word, "reason": summary.reason,
            "shown_reasons": shown_reasons}


# ---------------------------------------------------------------------------
# Giving a ChromIQ set a number on every row it can measure
# ---------------------------------------------------------------------------
#: How a ChromIQ set's own character scales the numbers it does NOT ship.
#:
#: Knut, 2026-09-18: *"those eleven can also be defined for all the Judge
#: Against limit sets, so the demo data must verify that all thresholds can
#: trigger correctly for every judged against limit set, not just test all the
#: thresholds on one of the sets."*
#:
#: **MEASURED FIRST, BECAUSE THE SHAPE OF THE MATRIX IS NOT WHAT IT LOOKS
#: LIKE.** As shipped, ChromIQ default, ChromIQ tight and Quick check put a
#: number on SEVEN of the sixteen judgeable rows; the two Custom columns put
#: one on all sixteen; and the two read-only ISO columns put one on none and
#: are not selectable at all, because their tolerance values are not in this
#: repository. So "every threshold for every set" is 53 cells as the product
#: ships, and the other 27 exist only once a user types a number in.
#:
#: That is not a workaround. ``effective_limits`` accepts an override on any
#: row whose status is not ``unmeasurable``/``unknown``, the Report limits
#: window is where a user types one, and a run's bound copy in
#: ``meta.json::compliance_thresholds`` is where it lives on disk. These runs
#: ship in exactly that state.
#:
#: The numbers are ChromIQ's own (``_CUSTOM_CHROMIQ_FILL``) scaled by the ratio
#: the set already uses on the five colour-difference rows it DOES ship: tight
#: is half of default (1.0 against 2.0, 1.5 against 3.0) and Quick check is
#: double it. Nothing here was looked up in any standard, and no row the set
#: already numbers is touched.
#:
#: **DELIBERATELY NOT KNUT'S RESEARCHED FIGURES**, which became the two Custom
#: columns' starting values on 2026-09-21 (#182). These runs are bound to
#: ChromIQ's OWN sets, whose numbers are ChromIQ's; filling their unnumbered
#: rows from a researched industry limit would put a figure into a ChromIQ
#: column that ChromIQ did not choose, and would move every demo design that
#: was built against these numbers. The Custom columns' own demo runs carry
#: ``edited_limits=None`` and are judged against whatever `factory_limits`
#: gives them, which is where the researched figures are seen.
SET_SCALE = {"chromiq_default": 1.0, "chromiq_tight": 0.5, "chromiq_quick": 2.0}


def fill_limits(set_id: str, relax: "dict[str, float] | None" = None,
                keep: "tuple[str, ...]" = ()) -> "dict[str, float]":
    """Every judgeable row this set leaves unnumbered, given a number.

    *relax* overrides any row with a value of its own (the package's existing
    way of isolating one row: put 9.0 on every other row of the column so a
    single crossing stands alone). *keep* names rows that must survive *relax*,
    which is what makes an isolation run isolate the row it says it does.
    """
    from workflow.compliance_sets import (ROW_BY_ID, _CUSTOM_CHROMIQ_FILL,
                                          factory_limits)
    scale = SET_SCALE.get(set_id, 1.0)
    factory = factory_limits(set_id)
    out: "dict[str, float]" = {}
    for rid, lim in _CUSTOM_CHROMIQ_FILL.items():
        row = ROW_BY_ID.get(rid)
        if row is None or row.status not in ("now", "build", "ref"):
            continue
        if factory.get(rid, None) is not None and factory[rid].is_numeric:
            continue                      # the set already numbers this row
        out[rid] = round(float(lim.number) * scale, 3)
    for rid, v in (relax or {}).items():
        if rid in keep:
            continue
        out[rid] = v
    return out


#: Every row that can carry a verdict on an ORDINARY ChromIQ chart, and every
#: row that can carry one on a FROM PROFILE GAMUT chart. Neither chart answers
#: all sixteen and the package says which is which rather than averaging the
#: two into a claim that is true of neither.
ROWS_ORDINARY = (
    "all_de00_avg", "best95_de00_avg", "worst5_de00_avg", "all_de00_max",
    "all_de00_p95", "grey_balance_neutral_ramp_avg",
    "grey_balance_neutral_ramp_max", "ramps_30_70_dl_max",
    "control_strip_de00_avg", "control_strip_de00_max",
    "control_strip_de00_p95", "surface_gamut_de00_avg",
    "outer_gamut_226_de00_avg",
    # ChromIQ's own Row A (B8-660): an ordinary targen chart repeats its
    # paper and its black, so it answers the row, and `repeat_split` is what
    # makes it cross. Row B is not in this list: it is about the date BEFORE,
    # so it is expected on the date after a swing, never on a first date.
    "repeat_patches_de00_max",
)
#: **AND THE 95TH-PERCENTILE CONTROL-STRIP ROW IS NOT IN THE SECOND LIST.**
#: ChromIQ's ladder has 29 rungs and a FROM PROFILE GAMUT chart fills 17 of
#: them (measured 2026-09-19: the eight corners, three greys and six tints;
#: the twelve it misses are single-ink and two-ink tints, which a selection
#: made out of a profile's own gamut simply does not contain). Seventeen is
#: past the eight a strip needs and short of the twenty the 95th percentile
#: needs, so that row reads `control_strip_too_small` on this kind of chart
#: however well it measures. The row's cell in the matrix is filled by the
#: ORDINARY run of the same set, which is the pair each set has.
ROWS_GAMUT = (
    "all_de00_avg", "best95_de00_avg", "worst5_de00_avg", "all_de00_max",
    "all_de00_p95",
    # THE GREY PAIR IS OFF THIS CHART AGAIN, since K28a (B8-483, Knut
    # 5795087247: the ramp's required steps roughly evenly spaced, within 4 %
    # of full scale). The selection keeps the neutrals of the profile's own
    # gamut, which on the K15 paper span eight distinct levels, but not evenly:
    # measured on the first build after K28a (2026-09-23), every From Profile
    # Gamut date reads `grey_steps_bunched` on both rows, on all five limit
    # sets. The app follows Knut's rule, so the design follows the app; the
    # grey cells of every set are exercised on the ordinary charts.
    "substrate_de00_max", "solids_de00_max",
    "cmy_solids_dhab_max", "control_strip_de00_avg", "control_strip_de00_max",
    "surface_gamut_de00_avg", "outer_gamut_226_de00_avg",
)
#: Every row an isolation run is NOT about, relaxed so the one it is about
#: crosses alone. The two repeatability rows are in it: Row B reads the swing
#: between two consecutive dates, and an isolation series swings one row out
#: and back by design, so without this every recovery date would cross Row B
#: as well as the row it recovers.
RELAX_ALL = {rid: 9.0 for rid in (set(ROWS_ORDINARY) | set(ROWS_GAMUT)
                                   | {"repeat_patches_de00_max",
                                      "repeat_measurement_de00_max"})}

#: The designs the matrix uses, one pair per set. Everything over, then
#: everything inside. Written out per set rather than scaled in code, because a
#: design that is computed from a limit cannot fail the way a design that is
#: typed can, and this package's whole value is that its numbers were checked
#: against the shipped code rather than derived from it.
MATRIX = {
    "chromiq_default": (
        Design(bulk=4.0, shoulder=5.0, peak=6.0, tail=5.0, grey_dch=4.0,
               ramp_dl=3.0, strip_bulk=4.0, strip_shoulder=5.0,
               strip_peak=6.0, surface_de=4.0, outer_de=4.0,
               white_de=5.0, solid_de=5.0, cmy_dh=3.5, repeat_split=3.0),
        Design(bulk=0.5, shoulder=0.8, peak=1.2, tail=0.9, grey_dch=0.4,
               ramp_dl=0.5, strip_bulk=0.5, strip_shoulder=0.8,
               strip_peak=1.2, surface_de=0.5, outer_de=0.5,
               white_de=1.0, solid_de=1.0, cmy_dh=0.8),
    ),
    "chromiq_tight": (
        Design(bulk=2.0, shoulder=2.5, peak=3.0, tail=2.5, grey_dch=2.5,
               ramp_dl=1.5, strip_bulk=2.0, strip_shoulder=2.5,
               strip_peak=3.0, surface_de=2.0, outer_de=2.0,
               white_de=3.0, solid_de=3.0, cmy_dh=2.0, repeat_split=1.6),
        Design(bulk=0.3, shoulder=0.45, peak=0.7, tail=0.5, grey_dch=0.3,
               ramp_dl=0.3, strip_bulk=0.3, strip_shoulder=0.45,
               strip_peak=0.7, surface_de=0.3, outer_de=0.3,
               white_de=0.5, solid_de=0.5, cmy_dh=0.3),
    ),
    "chromiq_quick": (
        Design(bulk=8.0, shoulder=9.0, peak=10.0, tail=9.0, grey_dch=8.0,
               ramp_dl=6.0, strip_bulk=8.0, strip_shoulder=9.0,
               strip_peak=10.0, surface_de=8.0, outer_de=8.0,
               white_de=9.0, solid_de=9.0, cmy_dh=6.0, repeat_split=6.0),
        Design(bulk=1.0, shoulder=1.5, peak=2.5, tail=2.0, grey_dch=1.0,
               ramp_dl=1.0, strip_bulk=1.0, strip_shoulder=1.5,
               strip_peak=2.5, surface_de=1.0, outer_de=1.0,
               white_de=1.5, solid_de=1.5, cmy_dh=1.0),
    ),
}
# THE TWO CUSTOM COLUMNS GOT THEIR OWN DESIGNS ON 2026-09-21, and the reason
# is the whole point of the matrix runs. They used to reuse ChromIQ default's,
# which worked while both columns held ChromIQ default's own numbers. Knut's
# researched industry figures (#182) moved two of them onto the design's own
# value: Custom ISO 12647-7 puts 4.0 on the outer-gamut average and Custom ISO
# 12647-8 puts 4.0 on the surface-gamut average, and the "everything over"
# date used 4.0 for both. A value EQUAL to its limit is inside it, so those
# rows would have stopped crossing and the date would have stopped meaning
# what its story says.
#
# 5.0 clears both, and the "everything in" date is untouched: its 0.5 is under
# the tightest number either column puts on those rows. Raised by hand and
# checked against the shipped limits, not derived from them, because a design
# derived from the numbers it is meant to cross proves only that division
# works.
from dataclasses import replace as _replace_design

_CUSTOM_OVER, _CUSTOM_IN = MATRIX["chromiq_default"]
MATRIX["custom_iso_12647_7"] = (
    _replace_design(_CUSTOM_OVER, outer_de=5.0, surface_de=5.0), _CUSTOM_IN)
MATRIX["custom_iso_12647_8"] = (
    _replace_design(_CUSTOM_OVER, outer_de=5.0, surface_de=5.0), _CUSTOM_IN)

MATRIX_SETS = ("chromiq_default", "chromiq_tight", "chromiq_quick",
               "custom_iso_12647_7", "custom_iso_12647_8")

#: The label a matrix run's story uses for its set, without repeating the
#: whole sentence six times.
_SET_WORD = {"chromiq_default": "ChromIQ default", "chromiq_tight": "ChromIQ tight",
             "chromiq_quick": "Quick check",
             "custom_iso_12647_7": "Custom ISO 12647-7",
             "custom_iso_12647_8": "Custom ISO 12647-8"}

#: One month per set, so no two matrix runs share a date and the pulldown can
#: never show two entries a reader cannot tell apart.
_MATRIX_MONTH = {"chromiq_default": "03", "chromiq_tight": "04",
                 "chromiq_quick": "05", "custom_iso_12647_7": "06",
                 "custom_iso_12647_8": "07"}


def matrix_dates(set_id: str, kind: str) -> "list[Date]":
    """The two dates of one matrix run: everything over, then everything in.

    *kind* is ``"ordinary"`` or ``"gamut"`` and decides which rows the chart
    can answer at all, which is the ``expect`` list and therefore the thing the
    build's own intended-against-actual check tests.
    """
    over, inside = MATRIX[set_id]
    if kind == "gamut":
        # A CHART SELECTED FROM THE PROFILE'S GAMUT HAS NO TONE RAMP, measured:
        # one step on the grey axis and none on R, G or B. `ramp_dl` has
        # nothing to move there and the generator refuses rather than pretending.
        #
        # AND IT REPEATS NO COLOUR, so ChromIQ's Row A has no pair to read and
        # `repeat_split` has nothing to pull apart; the ordinary chart of the
        # same column is where that row crosses.
        from dataclasses import replace as _replace
        over = _replace(over, ramp_dl=None, repeat_split=None)
        inside = _replace(inside, ramp_dl=None, repeat_split=None)
    rows = list(ROWS_ORDINARY if kind == "ordinary" else ROWS_GAMUT)
    m = _MATRIX_MONTH[set_id]
    d = "05" if kind == "ordinary" else "12"
    d2 = "19" if kind == "ordinary" else "26"
    d3 = "22" if kind == "ordinary" else "29"
    what = ("an ordinary ChromIQ chart" if kind == "ordinary"
            else "a chart built from the profile's own gamut")
    missing = ("The tone-ramp row is not on this sheet at all: a chart "
               "selected from the profile's gamut has no single-ink ramp, so "
               "it has no value to judge here and is exercised on the "
               "ordinary charts instead, and neither is ChromIQ's row for "
               "repeat patches on one sheet, because this chart repeats no "
               "colour. The 95th-percentile control-strip row is "
               "withheld too, and for a reason this chart shows better than "
               "any other: ChromIQ declares a control strip on it, of "
               "seventeen of the twenty-nine rungs it looks for, and the "
               "95th percentile needs twenty before its nearest rank stops "
               "being the largest patch again. The other two strip rows are "
               "judged here; that one is judged on the ordinary chart of the "
               "same column."
               if kind == "gamut" else
               "The three rows that need a reference measurement of the "
               "printing condition have no value here: an ordinary chart "
               "cannot supply them, and the Profile-Gamut project is where "
               "they are exercised.")
    return [
        _d(f"2028-{m}-{d}_100000", f"2028-{m}-{d}T10:00:00",
           f"Every row this chart can answer is over its limit",
           f"{_SET_WORD[set_id]} on {what}. Every one of the "
           f"{len(rows)} rows this chart supplies is over the number this "
           f"column puts on it, so every cell of the column that can carry a "
           f"word carries one. {missing}",
           over, rows),
        # ROW B IS THE ONE ROW THIS DATE CANNOT BRING BACK, and says so.
        # "The same chart measured again, largest difference" compares a sheet
        # with the one before it, and the one before it was over every limit:
        # bringing every value back is a swing of several ΔE00 on every patch,
        # which is exactly what that row exists to report. So it crosses here,
        # on the date every other row recovers, and recovers on the third.
        _d(f"2028-{m}-{d2}_100000", f"2028-{m}-{d2}T10:00:00",
           "The same sheet, every row back inside but one",
           f"The same chart and the same column, with every value brought "
           f"back under its limit. Read against the date before it, this pair "
           f"is what shows each of the {len(rows)} thresholds releasing as "
           f"well as triggering. The one row over is 'The same chart measured "
           f"again, largest difference': it compares this sheet with the one "
           f"before it, and getting back from there moved every patch.",
           inside, ["repeat_measurement_de00_max"]),
        _d(f"2028-{m}-{d3}_100000", f"2028-{m}-{d3}T10:00:00",
           "Measured again, and steady",
           "The same sheet as the date before, measured again. Every row is "
           "inside its limit, the repeat row included, because nothing moved "
           "between the two.",
           inside, []),
    ]


#: The FROM PROFILE GAMUT project's own dates: the three rows that exist
#: nowhere else, one at a time. The column relaxes everything else to 9.0 so a
#: crossing is the row the date is about and nothing else, which is the same
#: device the Isolated-Rows project uses.
GAMUT_ISOLATION: "list[Date]" = [
    _d("2028-01-05_100000", "2028-01-05T10:00:00",
       "The paper is too far from the reference white",
       "The paper white is 5.0 from the reference this chart carries, over "
       "the 3.0 this run's own column asks for. Every other row is relaxed to "
       "9.0. ONE row crosses, and it is a row no ordinary ChromIQ chart can "
       "even compute.",
       Design(bulk=0.6, shoulder=0.9, peak=1.4, tail=1.0,
              white_de=5.0, solid_de=0.5, cmy_dh=0.4),
       ["substrate_de00_max"]),
    _d("2028-01-19_100000", "2028-01-19T10:00:00",
       "A solid ink is off, and the paper is fine",
       "The composite black corner is 5.0 out, over the 3.0 on 'Solid "
       "colours, largest'. The paper white comes back to 0.5 and the hue of "
       "the three chromatic solids is left alone. ONE row crosses.",
       Design(bulk=0.6, shoulder=0.9, peak=1.4, tail=1.0,
              white_de=0.5, solid_de=5.0, cmy_dh=0.4),
       ["solids_de00_max"]),
    _d("2028-02-02_100000", "2028-02-02T10:00:00",
       "The three chromatic solids are rotated in hue",
       "Cyan, magenta and yellow are each turned about the neutral axis at "
       "constant lightness and constant chroma, so their metric hue "
       "difference is 3.0 and their lightness and chroma differences are "
       "zero. That is over the 2.0 on 'CMY solids, hue difference' and, "
       "because a pure hue turn at this chroma is a much smaller colour "
       "difference than it is a hue one, inside the 3.0 on 'Solid colours, "
       "largest'. ONE row crosses.",
       Design(bulk=0.6, shoulder=0.9, peak=1.4, tail=1.0,
              white_de=0.5, solid_de=0.5, cmy_dh=3.0),
       ["cmy_solids_dhab_max"]),
    _d("2028-02-16_100000", "2028-02-16T10:00:00",
       "All three come back",
       "The paper, the solids and the hue of the three chromatic solids are "
       "all inside their limits again, on the same chart and the same column.",
       Design(bulk=0.6, shoulder=0.9, peak=1.4, tail=1.0,
              white_de=0.5, solid_de=0.5, cmy_dh=0.4),
       []),
]

#: The control strip, one row at a time, on the strip CHROMIQ DECLARES.
#:
#: The chart is CHART_MEDIUM and ChromIQ fills all twenty-nine rungs of its
#: ladder on it, so the 95th percentile is the nearest rank ceil(0.95 x 29) =
#: 28 of 29, which is the SECOND LARGEST rung. Four of the twenty-nine carry
#: another row's design and cannot be moved by a strip knob (the substrate and
#: the three neutral greys); the designs below say so where it matters and the
#: `strip_avg` solver takes them into account where it does not.
#:
#: **THE 95TH PERCENTILE CANNOT CROSS ALONE, AND THAT IS ARITHMETIC, NOT A GAP
#: IN THIS PACKAGE.** It is never larger than the largest, so a strip whose
#: 95th percentile is over 3.0 has a largest rung over 3.0 too. The pair of
#: dates below is what separates the two readings instead: one where the
#: largest crosses and the 95th percentile does not, and one where both do.
STRIP_ISOLATION: "list[Date]" = [
    _d("2028-08-03_100000", "2028-08-03T10:00:00",
       "The whole strip drifts",
       "The strip's average is designed at 2.3, over the 2.0 this column puts "
       "on it, while every rung stays under the 3.0 on its largest and its "
       "95th percentile. The twenty-five rungs the strip design can move are "
       "solved for, because the substrate is pinned at zero by the "
       "media-relative yardstick and the three neutral greys carry the "
       "grey-balance design; a package that typed a per-patch number here "
       "would be typing one that only holds for one chart. Every other row is "
       "relaxed to 9.0. ONE row crosses.",
       Design(bulk=0.5, shoulder=0.8, peak=1.2, tail=0.9, grey_dch=0.4,
              strip_avg=2.3),
       ["control_strip_de00_avg"]),
    _d("2028-08-17_100000", "2028-08-17T10:00:00",
       "One rung of the strip is badly wrong",
       "One rung of the strip is at 4.5 and the rest at 0.5. The strip's "
       "largest is over 3.0; its average stays near 0.6 and its 95th "
       "percentile is the second largest rung, 0.5, so neither of those "
       "moves. ONE row crosses.",
       Design(bulk=0.5, shoulder=0.8, peak=1.2, tail=0.9, grey_dch=0.4,
              strip_bulk=0.5, strip_peak=4.5),
       ["control_strip_de00_max"]),
    _d("2028-08-31_100000", "2028-08-31T10:00:00",
       "The top of the strip goes, and the 95th percentile says so",
       "Two rungs go: one at 4.0 and one at 4.2. The 95th percentile now "
       "reads the 4.0 and the largest the 4.2, so both cross while the "
       "average stays near 0.8. Read against the date before it, this is what "
       "makes the two rows separate readings rather than one.",
       Design(bulk=0.5, shoulder=0.8, peak=1.2, tail=0.9, grey_dch=0.4,
              strip_bulk=0.5, strip_shoulder=4.0, strip_peak=4.2),
       ["control_strip_de00_max", "control_strip_de00_p95"]),
    _d("2028-09-14_100000", "2028-09-14T10:00:00",
       "The strip comes back",
       "Every rung ChromIQ declared is back at 0.5. All three strip rows "
       "recover on the same date and nothing else on the sheet moved.",
       Design(bulk=0.5, shoulder=0.8, peak=1.2, tail=0.9, grey_dch=0.4,
              strip_bulk=0.5),
       []),
]

SURFACE_ISOLATION: "list[Date]" = [
    _d("2028-09-28_100000", "2028-09-28T10:00:00",
       "The edge of the device cube drifts",
       "Every patch with a red, green or blue value within 2.0 of 0 or of 100 "
       "is moved to 3.0, over the 2.0 this column puts on the surface-gamut "
       "row. Every other row is relaxed to 9.0. ONE row crosses.",
       Design(bulk=0.5, shoulder=0.8, peak=1.2, tail=0.9, grey_dch=0.4,
              surface_de=3.0),
       ["surface_gamut_de00_avg"]),
    _d("2028-10-12_100000", "2028-10-12T10:00:00",
       "The edge comes back",
       "The same patches at 0.5. The row recovers and nothing else moved.",
       Design(bulk=0.5, shoulder=0.8, peak=1.2, tail=0.9, grey_dch=0.4,
              surface_de=0.5),
       []),
]

OUTER_ISOLATION: "list[Date]" = [
    _d("2028-10-26_100000", "2028-10-26T10:00:00",
       "The most saturated quarter of the chart drifts",
       "The top quarter of the chart by the chroma of its aim values is moved "
       "to 3.0, over the 2.0 this column puts on the outer-gamut row. Every "
       "other row is relaxed to 9.0. ONE row crosses.",
       Design(bulk=0.5, shoulder=0.8, peak=1.2, tail=0.9, grey_dch=0.4,
              outer_de=3.0),
       ["outer_gamut_226_de00_avg"]),
    _d("2028-11-09_100000", "2028-11-09T10:00:00",
       "The saturated quarter comes back",
       "The same patches at 0.5. The row recovers and nothing else moved.",
       Design(bulk=0.5, shoulder=0.8, peak=1.2, tail=0.9, grey_dch=0.4,
              outer_de=0.5),
       []),
]


# ---------------------------------------------------------------------------
# The projects
# ---------------------------------------------------------------------------
#: The FROM PROFILE GAMUT verification chart. 200 selected colours plus the
#: eight cube corners, which is comfortably past the ~80 referenced patches the
#: outer-gamut row needs before its top quarter holds 20.
CHART_GAMUT = GamutChartRecipe(200, "A4")

#: The chart that cannot supply the surface-gamut row. See `GridChartRecipe`.
CHART_MIDTONES = GridChartRecipe()

NO_SURFACE: "list[Date]" = [
    _d("2028-11-23_100000", "2028-11-23T10:00:00",
       "A chart with no patch on the surface of the device cube",
       "Every patch of this chart sits between 20 and 80 on all three "
       "channels, so not one of them is within 2.0 of 0 or of 100 and the "
       "surface-gamut row has no population to average. The report says which "
       "patches are missing and what to add in Create Chart, rather than "
       "passing the row. The two grey-balance rows have only five levels "
       "here, which is under the eight they need, so they say so too.\n"
       "AND CHROMIQ REFUSES TO DECLARE A CONTROL STRIP FOR THIS CHART, for "
       "the same reason: a control strip is mostly the substrate, the solid "
       "inks and their tints, and this chart has none of them. It fills four "
       "of the twenty-nine rungs ChromIQ looks for, eight are needed, so all "
       "three control-strip rows print 'this chart declares no control "
       "strip'. Every other verification chart in this package declares one, "
       "because ChromIQ writes the declaration itself the moment it files a "
       "verification chart; this run is where a reader sees it decline.\n"
       "This sheet ships with no record of how it was printed, and that is "
       "deliberate: with no bare-paper patch on the chart there is nothing "
       "for the media-relative yardstick to anchor on, and the lightest "
       "colour on the sheet would read a large difference by construction.",
       Design(bulk=0.6, shoulder=0.9, peak=1.4, tail=1.0),
       []),
    _d("2028-12-07_100000", "2028-12-07T10:00:00",
       "The same chart a fortnight later",
       "Nothing about the missing populations changes with the measurement, "
       "which is the point: a chart that cannot supply a row cannot supply it "
       "on any date, and a chart that cannot carry a control strip does not "
       "grow one by being measured again.",
       Design(bulk=0.6, shoulder=0.9, peak=1.4, tail=1.0),
       []),
]

# ---------------------------------------------------------------------------
# K29 (#182, Knut 5795310999): the same rules from more than one side
# ---------------------------------------------------------------------------
#: *"attacks all thresholds, metrics, requirement, output behaviour and
#: messages and functionality, from more angles of attack, so that none of
#: these things are only tested against one way of thinking"*. The projects
#: below add ROUTES, not rows: a different chart, instrument layout, paper,
#: limit set, report type or way of printing to a row the pack already
#: exercises, and the border of each limit. `make_release_demo_package.py`
#: counts the routes per row from the saved reports and lists any row that
#: has fewer than two trip routes and two pass routes.

#: One chart size the pack already uses, laid out for the i1Pro instead.
CHART_SMALL_I1 = ChartRecipe(105, 12, 8, "A4", "105 patches on A4, i1Pro layout",
                             instrument="i1")
#: A From Profile Gamut chart of a different size than the pack's first.
CHART_GAMUT_SMALL = GamutChartRecipe(150, "A4")


def _outlier_pair(m: str, over: Design, inside: Design, limit_word: str,
                  expect: "list[str]") -> "list[Date]":
    """One date with the row over its limit, then the same sheet back in."""
    return [
        _d(f"2029-{m}-03_100000", f"2029-{m}-03T10:00:00",
           f"Over the limit on {limit_word}",
           f"The sheet is designed to cross {limit_word} and nothing else.",
           over, expect),
        _d(f"2029-{m}-17_100000", f"2029-{m}-17T10:00:00",
           "Back inside",
           "The same chart measured again after the fault is corrected; the "
           "row that crossed comes back under its limit.",
           inside, []),
    ]


#: Report-Limits-Paper-Classes: one run per paper class, each on its own route.
PAPER_GLOSSY = _outlier_pair(
    "01", Design(bulk=0.80, shoulder=1.40, peak=3.60, tail=1.40, grey_dch=0.40),
    Design(bulk=0.80, shoulder=1.40, peak=2.20, tail=1.40, grey_dch=0.40),
    "'All patches, largest' (ChromIQ default 3.0)", ["all_de00_max"])
PAPER_BARYTA = _outlier_pair(
    "02", Design(bulk=1.20, shoulder=1.30, peak=1.45, tail=1.30, grey_dch=0.30),
    Design(bulk=0.40, shoulder=0.70, peak=1.10, tail=0.70, grey_dch=0.30),
    "the three averages (ChromIQ tight 1.0)",
    ["all_de00_avg", "best95_de00_avg", "worst5_de00_avg"])
PAPER_RAG = _outlier_pair(
    "03", Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=3.60),
    Design(bulk=0.80, shoulder=1.00, tail=1.00, grey_dch=1.00),
    "the grey average (Quick check 3.0)", ["grey_balance_neutral_ramp_avg"])
#: The Custom column numbers every row ChromIQ can measure, so a single far
#: patch also crosses the control-strip rows when it is a strip patch
#: (measured: it was). The tone-ramp row is what this run moves instead.
PAPER_OFFICE = _outlier_pair(
    "04", Design(bulk=0.80, shoulder=1.20, tail=1.00, grey_dch=0.40,
                 ramp_dl=2.6),
    Design(bulk=0.80, shoulder=1.20, tail=1.00, grey_dch=0.40, ramp_dl=1.0),
    "the tone-ramp row (Custom ISO 12647-7 2.0), on a sheet whose printing "
    "nobody recorded", ["ramps_30_70_dl_max"])
PAPER_NEWS: "list[Date]" = [
    _d("2029-05-03_100000", "2029-05-03T10:00:00",
       "Measured once, one patch far out",
       "The only verification of this run: a single patch at 3.8 carries "
       "'All patches, largest' over ChromIQ default's 3.0. One measurement "
       "is not yet a history, so the run's limit set can still be chosen.",
       Design(bulk=0.80, shoulder=1.30, peak=3.80, tail=1.00, grey_dch=0.40),
       ["all_de00_max"]),
]
PAPER_GAMUT_WHITE: "list[Date]" = [
    _d("2029-06-03_100000", "2029-06-03T10:00:00",
       "The paper is off its reference",
       "A From Profile Gamut chart on brightened glossy paper, whose "
       "reference carries the paper: the white is designed 4.0 off it, over "
       "the 3.0 this run's own column puts on 'Paper white'. Everything else "
       "is relaxed, so that row crosses alone.",
       Design(bulk=0.6, shoulder=0.9, peak=1.4, tail=1.0,
              white_de=4.0, solid_de=0.5, cmy_dh=0.4),
       ["substrate_de00_max"]),
    _d("2029-06-17_100000", "2029-06-17T10:00:00",
       "The paper is back on its reference",
       "The same chart, the white within 1.0 of its reference.",
       Design(bulk=0.6, shoulder=0.9, peak=1.4, tail=1.0,
              white_de=1.0, solid_de=0.5, cmy_dh=0.4),
       []),
]


def _border_dates(m: str, word: str, at: float, step: float, base: Design,
                  field_: str, row: str, nudge: float = 0.0) -> "list[Date]":
    """Exactly on a limit, one step over, one step under (K29).

    A value EQUAL to its limit is inside it (`compliance_sets.row_verdict`:
    ``value <= limit``), and the value judged is the one the report saves,
    rounded to three decimals. `BORDER_VALUES` records the three numbers each
    date must SAVE, and `build_run` refuses a border date whose saved value is
    not that number, so "exactly on the limit" is a checked fact.

    *nudge* is added to the designed patch value and never to the number the
    story states. Measured on the first build (2026-09-23): on the 210-patch
    chart the saved "All patches, largest" came out 0.0005 to 0.0015 above
    the designed peak (3.0 read 3.001), because the media-relative
    normalisation moves the whole sheet a hair after the patch is placed; on
    the A3 chart it came out exact. The nudge aims the design at the saved
    number, which is the one a reader sees and the one that is judged.
    """
    from dataclasses import replace as _r
    for vid, value in ((f"2029-{m}-06_100000", at),
                       (f"2029-{m}-13_100000", round(at + step, 3)),
                       (f"2029-{m}-20_100000", round(at - step, 3))):
        BORDER_VALUES[vid] = (row, value)
    return [
        _d(f"2029-{m}-06_100000", f"2029-{m}-06T10:00:00",
           f"Exactly on the limit: {at:.3f}",
           f"{word} is designed to read {at:.3f}, which is its limit. A value "
           f"equal to its limit is inside it.",
           _r(base, **{field_: at + nudge}), []),
        _d(f"2029-{m}-13_100000", f"2029-{m}-13T10:00:00",
           f"Just over: {at + step:.3f}",
           f"{word} is designed to read {at + step:.3f}, one thousandth over "
           f"its limit of {at:.3f}.",
           _r(base, **{field_: round(at + step, 3) + nudge}), [row]),
        _d(f"2029-{m}-20_100000", f"2029-{m}-20T10:00:00",
           f"Just under: {at - step:.3f}",
           f"{word} is designed to read {at - step:.3f}, one thousandth "
           f"under its limit of {at:.3f}.",
           _r(base, **{field_: round(at - step, 3) + nudge}), []),
    ]


#: vid -> (row, the value the saved report must carry), for every border date.
BORDER_VALUES: "dict[str, tuple[str, float]]" = {}


_MAX_WORD = "'All patches, largest'"
BORDER_DEFAULT_MAX = _border_dates(
    "07", _MAX_WORD, 3.0, 0.001,
    Design(bulk=0.80, shoulder=1.40, peak=3.0, tail=1.40, grey_dch=0.40),
    "peak", "all_de00_max", nudge=-0.001)
BORDER_TIGHT_MAX = _border_dates(
    "08", _MAX_WORD, 1.5, 0.001,
    Design(bulk=0.40, shoulder=0.70, peak=1.5, tail=0.70, grey_dch=0.30),
    "peak", "all_de00_max")
BORDER_QUICK_MAX = _border_dates(
    "09", _MAX_WORD, 6.0, 0.001,
    Design(bulk=1.00, shoulder=2.00, peak=6.0, tail=1.50, grey_dch=0.80),
    "peak", "all_de00_max")
BORDER_BEST95 = _border_dates(
    "10", "'Best 95 % of patches, average'", 2.0, 0.001,
    Design(bulk=1.0, shoulder=2.2, peak=3.0, tail=2.5, target_best95=2.0,
           grey_dch=0.5),
    "target_best95", "best95_de00_avg")

#: The second route of Knut's matrix: a different chart and paper per set.
_SECOND_PAPER = {"chromiq_default": ("glossy_oba", "baryta"),
                 "chromiq_tight": ("baryta", "matte_rag"),
                 "chromiq_quick": ("matte_rag", "office"),
                 "custom_iso_12647_7": ("office", "glossy_oba"),
                 "custom_iso_12647_8": ("newsprint", "baryta")}


def _second_route(set_id: str, kind: str) -> "list[Date]":
    """`matrix_dates`, re-dated into 2029 so the two routes of one cell never
    share a date in a window that shows both projects."""
    out = []
    for d in matrix_dates(set_id, kind):
        vid = "2029" + d.vid[4:]
        out.append(Date(vid, "2029" + d.when[4:], d.title, d.story,
                        d.design, list(d.expect)))
    return out


#: The project built under one name and renamed afterwards (K29 "moved and
#: renamed projects"). `main` renames it with the app's own `Project.rename`
#: after a report across it and Paper-Classes has been written under its old
#: name, so the renamed project must still find that report.
RENAMED_PROJECT = "Report-Limits-Renamed"
RENAMED_FROM = "Report-Limits-Before-Rename"
RENAMED_DATES = _outlier_pair(
    "11", Design(bulk=0.80, shoulder=1.40, peak=3.40, tail=1.40, grey_dch=0.40),
    Design(bulk=0.80, shoulder=1.40, peak=2.10, tail=1.40, grey_dch=0.40),
    "'All patches, largest' (ChromIQ default 3.0)", ["all_de00_max"])


PROJECTS = [
    ("Report-Limits-Threshold-Series", [
        RunPlan("The dated series: every judged row crosses on one date and "
                "recovers on the next.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default", SERIES_DEFAULT,
                note="The series chart. Do not regenerate it: every date is "
                     "judged against its own snapshot of this chart."),
        RunPlan("The same kind of sheet judged with ChromIQ tight.",
                CHART_LARGE, CHART_WIDE, "chromiq_tight", SERIES_TIGHT),
        RunPlan("The small chart, measured once.",
                CHART_SMALL, CHART_SMALL, "chromiq_quick", SERIES_ONE_DATE,
                lock="one-date"),
    ]),
    ("Report-Limits-Isolated-Rows", [
        RunPlan("Best 95 % average isolated by this run's own edited column.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default", SERIES_BEST95,
                edited_limits={"all_de00_avg": 6.0, "worst5_de00_avg": 8.0,
                               "best95_de00_avg": 2.0, "all_de00_max": 9.0,
                               "all_de00_p95": 9.0}),
        # The one LARGE verification sheet in the package. The 95th percentile
        # is the row whose meaning depends most on how many patches there are
        # (the nearest-rank split moves a whole patch at a time on a small
        # chart and hardly at all on a big one), so the biggest chart is the
        # right one to judge it on, and it puts a fifth size under the
        # supported/not-supported table below.
        RunPlan("95th percentile isolated by this run's own edited column, "
                "on the package's largest verification sheet.",
                CHART_WIDE, CHART_LARGE, "chromiq_default", SERIES_P95,
                edited_limits={"all_de00_avg": 9.0, "worst5_de00_avg": 9.0,
                               "best95_de00_avg": 9.0, "all_de00_max": 9.0,
                               "all_de00_p95": 3.0}),
        RunPlan("The small chart, measured twice.",
                CHART_SMALL, CHART_SMALL, "chromiq_tight",
                SERIES_TWO_DATES_UNLOCKED, unlocked=True, lock="unlocked"),
        RunPlan("Grey balance average isolated by this run's own edited column.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_default", SERIES_GREY_AVG,
                edited_limits={"all_de00_avg": 6.0, "worst5_de00_avg": 6.0,
                               "best95_de00_avg": 6.0, "all_de00_max": 9.0,
                               "all_de00_p95": 9.0}),
        RunPlan("The tone-ramp row, which no shipped set judges, given a "
                "limit by this run's own edited column.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default", SERIES_RAMP,
                edited_limits={"all_de00_avg": 9.0, "worst5_de00_avg": 9.0,
                               "best95_de00_avg": 9.0, "all_de00_max": 9.0,
                               "all_de00_p95": 9.0,
                               "ramps_30_70_dl_max": 2.0}),
    ]),
    ("Report-Limits-Set-Compare", [
        RunPlan("The shared measurement judged with ChromIQ default.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_default", SERIES_COMPARE_DEFAULT),
        RunPlan("The shared measurement judged with ChromIQ tight.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_tight", SERIES_COMPARE_TIGHT),
        RunPlan("The shared measurement judged with Quick check.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_quick", SERIES_COMPARE_QUICK),
    ]),
    ("Report-Limits-Report-Types", [
        RunPlan("Colour summary, ChromIQ default. The run also holds a Full "
                "colour check and a Grey and tone check of its first date, so "
                "the window's 'Already generated' line has four types to "
                "count, the profiling sheet's Printing record among them.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_default", TYPES_DE_DEFAULT,
                report_type=REPORT_TYPE_SUMMARY, unlocked=True, lock="unlocked",
                also_generate=(REPORT_TYPE_FULL, REPORT_TYPE_GREY)),
        RunPlan("Full colour check, ChromIQ tight.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_tight", TYPES_DE_TIGHT,
                report_type=REPORT_TYPE_FULL, unlocked=True, lock="unlocked"),
        RunPlan("Colour summary, Quick check. The Printing record is the "
                "report of this run's own profiling measurement, as it is of "
                "every run's: a verification does not have one.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_quick", TYPES_DE_QUICK,
                report_type=REPORT_TYPE_SUMMARY, unlocked=True, lock="unlocked"),
        RunPlan("Grey and tone check, ChromIQ default, with a limit typed into "
                "the tone-ramp row so all three of its rows carry a word.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default",
                TYPES_GREY_DEFAULT, report_type=REPORT_TYPE_GREY,
                unlocked=True, lock="unlocked",
                edited_limits={"ramps_30_70_dl_max": 2.0}),
        RunPlan("Grey and tone check, ChromIQ tight, left as the set ships: "
                "the tone-ramp row shows a number and no word.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_tight", TYPES_GREY_TIGHT,
                report_type=REPORT_TYPE_GREY, unlocked=True, lock="unlocked"),
        RunPlan("Grey and tone check, Quick check.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_quick", TYPES_GREY_QUICK,
                report_type=REPORT_TYPE_GREY, unlocked=True, lock="unlocked"),
        RunPlan("Grey and tone check on a chart with no grey ramp, so the "
                "column has limits and nothing it can check.",
                CHART_SMALL, CHART_NO_GREY, "chromiq_tight",
                TYPES_GREY_NOTHING, report_type=REPORT_TYPE_GREY,
                unlocked=True, lock="unlocked",
                # A LIMIT ON THE TONE-RAMP ROW, so the row APPEARS. Without
                # one it has neither a limit nor a value, which is a blank
                # cell and not a verdict (CH-20), and the document then shows
                # two rows instead of three and never prints the reason the
                # chart could not supply the third.
                edited_limits={"ramps_30_70_dl_max": 2.0},
                note="Deliberately built without a grey ramp. Do not "
                     "regenerate it with one: this run exists to show what the "
                     "report says when a chart cannot supply a row."),
    ]),
    (FOLDERS_PROJECT, [
        RunPlan("Where reports live (K23). Every dated check keeps a report "
                "of its own of each verification type on its first date, the "
                "profiling sheet keeps its Printing record, and "
                "`seed_report_folders` adds a report of several dates, a "
                "legacy one written the way beta 36 wrote it, a deleted one, "
                "and reports across both runs.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_default", FOLDERS_RUN1,
                report_type=REPORT_TYPE_FULL, unlocked=True, lock="unlocked",
                also_generate=(REPORT_TYPE_SUMMARY, REPORT_TYPE_GREY)),
        RunPlan("The second profile run. Its first date holds a Colour "
                "summary as well, its second date a report saved by an "
                "older ChromIQ with no document record, and it shares two "
                "reports with run1 in the project's own reports folder.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_default", FOLDERS_RUN2,
                report_type=REPORT_TYPE_FULL, unlocked=True, lock="unlocked",
                also_generate=(REPORT_TYPE_SUMMARY,)),
    ]),
    (FOLDERS_OTHER_PROJECT, [
        RunPlan("A SECOND project for the grouped report list (K25). Add its "
                "measurements to a window on Report-Limits-Report-Folders and "
                "\"Report shown\" groups by project, then by run. It holds a "
                "report of both its dates, and shares two reports with "
                "Report-Limits-Report-Folders in the pack's own reports "
                "folder: \"Reports including multiple projects\".",
                CHART_SMALL, CHART_MEDIUM, "chromiq_default",
                FOLDERS_OTHER_RUN1, report_type=REPORT_TYPE_FULL,
                unlocked=True, lock="unlocked"),
    ]),
    ("Report-Limits-Custom-Columns", [
        RunPlan("The Custom ISO 12647-7 column, which starts from ChromIQ's "
                "own numbers and not from that standard's published values.",
                CHART_SMALL, CHART_MEDIUM, "custom_iso_12647_7",
                CUSTOM_7_SERIES, unlocked=True, lock="unlocked",
                note="The limits of this column are not edited by this "
                     "package and must not be: they are placeholders under a "
                     "permission condition, pinned by a test."),
        RunPlan("The Custom ISO 12647-8 column, crossing the tone-ramp row "
                "that no other shipped set puts a limit on.",
                CHART_MEDIUM, CHART_MEDIUM, "custom_iso_12647_8",
                CUSTOM_8_SERIES, unlocked=True, lock="unlocked",
                note="The limits of this column are not edited by this "
                     "package and must not be: they are placeholders under a "
                     "permission condition, pinned by a test."),
    ]),
    ("Report-Limits-Border-Conditions", [
        RunPlan("A chart with fewer than twenty patches, so the worst 5 % of "
                "the sheet is the empty set and that row cannot be computed.",
                CHART_SMALL, CHART_TINY, "chromiq_default",
                BORDER_SMALL_SAMPLE, unlocked=True, lock="unlocked",
                # Exactly eight rungs, measured: the substrate, four of the
                # eight corners and the three greys. That is the floor at
                # which ChromIQ declares a strip at all, and twelve short of
                # the 95th-percentile row, so this run is where a reader sees
                # a strip that exists and a strip row that is withheld on the
                # same page.
                expect_strip_p95=False,
                note="Deliberately twenty patches. Do not regenerate it "
                     "larger: this run exists to show what the report says "
                     "when a sheet is too small to have a worst 5 %."),
        # QUICK CHECK, and for a measured reason. The grey ramp carries a cast
        # of 1.9 so its rows have a number worth reading, and a chroma error
        # that size near a neutral is a colour difference of about 2.7, which
        # under ChromIQ default would take the worst-5 % average over its 2.0
        # and make this run about a crossing it is not about.
        # ON A GREY AND TONE CHECK, and that is what reaches the sentence.
        # Every row that document shows carries a real number and none of them
        # can be graded, which is a different state from a chart that could
        # supply nothing: "none of the values was graded" against "the chart
        # supplied none of the values". Under Full colour check the same run
        # shows its colour rows judged as usual, which the table below prints.
        # THE NAME SAYS "CONDITION", BECAUSE THE FIRST ONE DID NOT AND WAS
        # READ THE OTHER WAY. Knut, 2026-09-13, reading it on this very run:
        # *"Why 'A sheet nobody recorded the printing of'? Is that relevant? A
        # measurement performed on a verification chart was obviously
        # printed."* He is right about the sheet and right about the sentence:
        # what is missing is the RECORD OF HOW it was printed, not the
        # printing. The app's own reason line always said so ("how this sheet
        # was printed is not recorded"); this pack's run title did not.
        # AND THE SECOND HALF OF THIS SENTENCE WENT STALE THE SAME DAY. It
        # said the grey rows "keep their numbers and are shown for
        # information", which was CH-17, which Knut overruled on 2026-09-13:
        # the verdicts are given and the caveat goes into a numbered note. A
        # demo pack that describes the behaviour it no longer demonstrates is
        # worse than no description, so the run says what it now shows.
        RunPlan("A sheet whose printing condition nobody wrote down, so the "
                "grey rows are judged with a numbered note against them.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_quick",
                BORDER_UNRECORDED, unlocked=True, lock="unlocked",
                report_type=REPORT_TYPE_GREY,
                print_colour="none",
                note="Deliberately shipped without a print record beside the "
                     "chart snapshot. Do not add one."),
        RunPlan("A sheet printed with no profile applied, which the report "
                "treats as a drift check rather than an accuracy check.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_default",
                BORDER_RAW_DRIFT, unlocked=True, lock="unlocked",
                print_colour="raw",
                note="Deliberately printed raw. The large numbers are "
                     "correct for a sheet nothing corrected."),
    ]),
    # -----------------------------------------------------------------------
    # The seventh project: the chart built FROM PROFILE GAMUT
    # -----------------------------------------------------------------------
    # Knut, 2026-09-18: *"Also, some tests require a test chart with From
    # Profile Gamut, which must also be included."*
    #
    # It is the only chart that makes three of the sixteen judgeable rows
    # answerable at all. A chart whose device values were converted through the
    # profile at build time ships a `<stem>-reference.ti3` beside itself; the
    # report reads that instead of the .ti2's design XYZ, `reference_source`
    # becomes "colorimetric", and only then does `row_values` compute *Paper
    # white*, *Solid colours largest* and *CMY solids hue difference* rather
    # than writing `needs_reference_file` on all three. Before this project
    # existed those three rows read `needs_reference_file` in 80 of 80 saved
    # reports of this package.
    ("Report-Limits-Profile-Gamut", [
        RunPlan("The three rows only a From-profile-gamut chart can answer, "
                "one at a time, isolated by this run's own edited column.",
                CHART_MEDIUM, CHART_GAMUT, "chromiq_default",
                GAMUT_ISOLATION, unlocked=True, lock="unlocked",
                # 17 of the 29 rungs, measured: the eight corners, three
                # greys and six tints. Enough to declare, three short of the
                # twenty the 95th-percentile row needs.
                expect_strip_p95=False,
                edited_limits=fill_limits(
                    "chromiq_default", relax=RELAX_ALL,
                    keep=("substrate_de00_max", "solids_de00_max",
                          "cmy_solids_dhab_max")),
                note="A From-profile-gamut chart. Do not regenerate it as an "
                     "ordinary chart: the colorimetric reference beside it is "
                     "the only thing that makes three of this package's rows "
                     "computable."),
        RunPlan("The same kind of chart under Custom ISO 12647-7, which "
                "already puts a number on every judgeable row.",
                CHART_MEDIUM, CHART_GAMUT, "custom_iso_12647_7",
                matrix_dates("custom_iso_12647_7", "gamut"),
                unlocked=True, lock="unlocked", expect_strip_p95=False,
                note="The limits of this column are not edited by this "
                     "package and must not be: they are placeholders under a "
                     "permission condition, pinned by a test."),
    ]),
    # -----------------------------------------------------------------------
    # The eighth project: the five rows that had no detection until B8-397
    # -----------------------------------------------------------------------
    # Knut approved the three S2w proposals on 2026-09-18, so the three
    # control-strip rows and the two gamut-population rows stopped being
    # `unknown` and became measurable. Nothing in this package exercised them
    # the day they landed: measured on the previous build, all three strip
    # rows read N-A in 80 of 80 saved reports because no chart in the package
    # declared a strip.
    #
    # AND THE FIRST PACKAGE THAT DID EXERCISE THEM DECLARED ITS OWN STRIP,
    # which demonstrated this generator rather than ChromIQ: nothing in the
    # app wrote a declaration at all until B8-405, so the fixture had to
    # invent one, and it invented the opposite population to the one the app
    # now writes (24 mid-gamut patches, deliberately no grey, no paper and no
    # corner; ChromIQ's ladder is the substrate, the corners, the tints and
    # the greys). Every chart in this package is now offered to the app's own
    # `declare_for_chart`, and run4 below is a chart it refuses.
    ("Report-Limits-Strip-And-Gamut", [
        RunPlan("ChromIQ's own control-strip declaration, with each of the "
                "three strip rows isolated by this run's own edited column.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default",
                STRIP_ISOLATION, unlocked=True, lock="unlocked",
                edited_limits=fill_limits(
                    "chromiq_default", relax=RELAX_ALL,
                    keep=("control_strip_de00_avg", "control_strip_de00_max",
                          "control_strip_de00_p95")),
                note="The sidecar beside this chart is what declares the "
                     "strip, and ChromIQ wrote it: it is the same file the "
                     "app writes beside any verification chart it creates, "
                     "naming the 29 device aims a control strip is made of "
                     "and which of this chart's patches filled each one. "
                     "Delete it and all three strip rows go back to reading "
                     "'this chart declares no control strip'."),
        RunPlan("The surface of the device cube, isolated by this run's own "
                "edited column.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default",
                SURFACE_ISOLATION, unlocked=True, lock="unlocked",
                edited_limits=fill_limits(
                    "chromiq_default", relax=RELAX_ALL,
                    keep=("surface_gamut_de00_avg",))),
        RunPlan("The most saturated quarter of the chart, isolated by this "
                "run's own edited column.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default",
                OUTER_ISOLATION, unlocked=True, lock="unlocked",
                edited_limits=fill_limits(
                    "chromiq_default", relax=RELAX_ALL,
                    keep=("outer_gamut_226_de00_avg",))),
        RunPlan("A chart that can supply neither the surface-gamut row nor a "
                "control-strip declaration, so four rows are seen to be "
                "refused rather than passed.",
                CHART_SMALL, CHART_MIDTONES, "chromiq_default",
                NO_SURFACE, unlocked=True, lock="unlocked",
                edited_limits=fill_limits("chromiq_default"),
                # AND IT IS ALSO THE CHART THAT CANNOT CARRY A CONTROL STRIP.
                # Measured: it fills four of the twenty-nine rungs (the
                # substrate and the three greys) and ChromIQ refuses to
                # declare one, so all three strip rows print
                # `no_control_strip` here while every other chart in the
                # package supplies at least the first two. The same reason
                # holds for both refusals: nothing on this chart goes near an
                # edge of the device cube, and a control strip is mostly made
                # of patches that do.
                expect_strip="too_few_patches",
                # AND IT SHIPS WITHOUT A PRINTING RECORD, for a measured
                # reason rather than a stylistic one. A sheet printed through
                # the profile is judged MEDIA-RELATIVE: every reading is
                # divided by the LIGHTEST patch of the sheet, which on an
                # ordinary chart is bare paper. This chart has no bare-paper
                # patch, so the anchor is an ordinary mid-grey, and dividing
                # it by itself pins it to L*100 against a design value of
                # L*82. Measured: that one patch alone read 10.996 dE00 and
                # took "All patches, largest" and the worst-5 % average with
                # it, on a sheet designed for 0.6. Without the record the
                # report judges in absolute Lab, there is no anchor, and the
                # run is about the row it says it is about.
                print_colour="none",
                note="Deliberately built as a 5x5x5 grid on 20/35/50/65/80. "
                     "Do not regenerate it with a targen recipe: every targen "
                     "chart is full of patches on the cube's surface (measured "
                     "over this package's six sizes: 21 of 30 up to 200 of "
                     "405) and every one of them fills enough of ChromIQ's "
                     "control-strip ladder to declare a strip (8 rungs on the "
                     "smallest, 29 on the largest), so this is the only run "
                     "that can show the report detecting either refusal."),
    ]),
    # -----------------------------------------------------------------------
    # The ninth project: EVERY judgeable row against EVERY limit set
    # -----------------------------------------------------------------------
    # Knut, 2026-09-18: *"the demo data must verify that all thresholds can
    # trigger correctly for every judged against limit set, not just test all
    # the thresholds on one of the sets."*
    #
    # Ten runs, two to a set: one on an ordinary ChromIQ chart, which answers
    # thirteen rows, and one on a From-profile-gamut chart, which answers a
    # different thirteen. Each run holds one date on which every row that chart
    # can answer is OVER its limit and one on which every one of them is back
    # inside, so both halves of every cell of the matrix are on the disk.
    #
    # The three ChromIQ sets ship a number on seven of the sixteen rows, so
    # their runs carry the other nine in the run's own bound copy, exactly as a
    # user who typed them into the Report limits window would have. The two
    # Custom columns already number all sixteen and are NOT edited.
    ("Report-Limits-Every-Limit-Set", [
        plan
        for set_id in MATRIX_SETS
        for plan in (
            RunPlan(f"{_SET_WORD[set_id]}, every row an ordinary chart can "
                    f"answer: over on one date, inside on the next.",
                    CHART_SMALL, CHART_MEDIUM, set_id,
                    matrix_dates(set_id, "ordinary"),
                    unlocked=True, lock="unlocked",
                    edited_limits=(None if set_id.startswith("custom_")
                                   else fill_limits(set_id))),
            RunPlan(f"{_SET_WORD[set_id]}, every row a From-profile-gamut "
                    f"chart can answer: over on one date, inside on the next.",
                    CHART_SMALL, CHART_GAMUT, set_id,
                    matrix_dates(set_id, "gamut"),
                    unlocked=True, lock="unlocked", expect_strip_p95=False,
                    edited_limits=(None if set_id.startswith("custom_")
                                   else fill_limits(set_id))),
        )
    ]),
    # -----------------------------------------------------------------------
    # K29: realistic paper, each class on a route of its own
    # -----------------------------------------------------------------------
    ("Report-Limits-Paper-Classes", [
        RunPlan("Glossy photo paper with optical brighteners: one patch far "
                "out, then back.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default", PAPER_GLOSSY,
                paper_class="glossy_oba", unlocked=True, lock="unlocked"),
        RunPlan("Baryta, on the A3 chart, judged with ChromIQ tight in a "
                "Colour summary: the averages drift, then recover.",
                CHART_SMALL, CHART_WIDE, "chromiq_tight", PAPER_BARYTA,
                paper_class="baryta", report_type=REPORT_TYPE_SUMMARY,
                unlocked=True, lock="unlocked"),
        RunPlan("Matte cotton rag, judged with Quick check in a Grey and tone "
                "check: a grey cast, then corrected.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_quick", PAPER_RAG,
                paper_class="matte_rag", report_type=REPORT_TYPE_GREY,
                unlocked=True, lock="unlocked"),
        RunPlan("Uncoated office paper, an i1Pro chart layout, the Custom "
                "ISO 12647-7 column, and no record of how the sheets were "
                "printed, so they are judged in absolute Lab.",
                CHART_SMALL_I1, CHART_SMALL_I1, "custom_iso_12647_7",
                PAPER_OFFICE, paper_class="office", print_colour="none",
                unlocked=True, lock="unlocked",
                note="The limits of this column are not edited by this "
                     "package and must not be: they are placeholders under a "
                     "permission condition, pinned by a test."),
        RunPlan("Newsprint-like paper, measured once.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default", PAPER_NEWS,
                paper_class="newsprint", lock="one-date"),
        RunPlan("A From Profile Gamut chart on brightened glossy paper, the "
                "paper white isolated by this run's own edited column.",
                CHART_MEDIUM, CHART_GAMUT_SMALL, "chromiq_default",
                PAPER_GAMUT_WHITE, paper_class="glossy_oba",
                unlocked=True, lock="unlocked", expect_strip_p95=False,
                edited_limits=fill_limits(
                    "chromiq_default", relax=RELAX_ALL,
                    keep=("substrate_de00_max",))),
    ]),
    # -----------------------------------------------------------------------
    # K29: exactly on a limit, one thousandth over, one thousandth under
    # -----------------------------------------------------------------------
    ("Report-Limits-Border-Values", [
        RunPlan("'All patches, largest' on ChromIQ default's 3.0: on it, over "
                "it, under it.",
                CHART_MEDIUM, CHART_MEDIUM, "chromiq_default",
                BORDER_DEFAULT_MAX),
        RunPlan("'All patches, largest' on ChromIQ tight's 1.5, on the A3 "
                "chart.",
                CHART_SMALL, CHART_WIDE, "chromiq_tight", BORDER_TIGHT_MAX,
                paper_class="baryta"),
        # NOT THE SMALL CHART, measured: 55 of its 105 colours are in gamut,
        # so its worst 5 % is two patches and a 6.0 peak alone takes that
        # average over Quick check's 4.0.
        RunPlan("'All patches, largest' on Quick check's 6.0, on matte rag.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_quick", BORDER_QUICK_MAX,
                paper_class="matte_rag"),
        RunPlan("'Best 95 % of patches, average' on 2.0, isolated by this "
                "run's own edited column, on the five-page chart.",
                CHART_MEDIUM, CHART_LARGE, "chromiq_default", BORDER_BEST95,
                edited_limits=fill_limits(
                    "chromiq_default", relax=RELAX_ALL,
                    keep=("best95_de00_avg",))),
    ]),
    # -----------------------------------------------------------------------
    # K29: a second route for every cell of Knut's matrix
    # -----------------------------------------------------------------------
    ("Report-Limits-Second-Route", [
        plan
        for set_id in MATRIX_SETS
        for plan in (
            RunPlan(f"{_SET_WORD[set_id]} again, on the A3 chart and "
                    f"{PAPER_CLASSES[_SECOND_PAPER[set_id][0]].name.lower()}: "
                    f"every row over on one date, inside on the next.",
                    CHART_SMALL, CHART_WIDE, set_id,
                    _second_route(set_id, "ordinary"),
                    paper_class=_SECOND_PAPER[set_id][0],
                    unlocked=True, lock="unlocked",
                    edited_limits=(None if set_id.startswith("custom_")
                                   else fill_limits(set_id))),
            RunPlan(f"{_SET_WORD[set_id]} again, on a smaller From Profile "
                    f"Gamut chart and "
                    f"{PAPER_CLASSES[_SECOND_PAPER[set_id][1]].name.lower()}.",
                    CHART_SMALL, CHART_GAMUT_SMALL, set_id,
                    _second_route(set_id, "gamut"),
                    paper_class=_SECOND_PAPER[set_id][1],
                    unlocked=True, lock="unlocked", expect_strip_p95=False,
                    edited_limits=(None if set_id.startswith("custom_")
                                   else fill_limits(set_id))),
        )
    ]),
    # -----------------------------------------------------------------------
    # K29: a project renamed after a report across projects was written
    # -----------------------------------------------------------------------
    (RENAMED_PROJECT, [
        RunPlan(f"Built as {RENAMED_FROM} and renamed with ChromIQ's own "
                f"rename. A report across this project and "
                f"Report-Limits-Paper-Classes, written under the old name, "
                f"lives in the pack's own reports folder.",
                CHART_SMALL, CHART_MEDIUM, "chromiq_default", RENAMED_DATES,
                unlocked=True, lock="unlocked"),
    ]),
]


def build_project(dest: Path, name: str, plans: "list[RunPlan]",
                  cache_root: Path, results: list,
                  lock_rows: "list[dict] | None" = None) -> Path:
    from core.file_manager import Project
    from workflow.run_compliance import is_locked, measured_dates
    # THE RENAMED PROJECT IS BUILT UNDER ITS FORMER NAME (K29); `main` renames
    # it once a report across projects has been written under that name.
    build_name = RENAMED_FROM if name == RENAMED_PROJECT else name
    for stale in {dest / name, dest / build_name}:
        if stale.exists():
            shutil.rmtree(stale)
    root = dest / build_name
    print(f"== {name}" + (f" (built as {build_name})" if build_name != name
                          else ""))
    proj = Project.create(root, build_name)
    run = proj.current_run()
    for i, plan in enumerate(plans):
        if i:
            run = proj.new_run()
        before = len(results)
        build_run(proj, run, plan, cache_root, results)
        for r in results[before:]:
            r["project"] = name
        if lock_rows is not None:
            lock_rows.append({
                "run": f"{name.replace('Report-Limits-', '')}/{run.id}",
                "dates": measured_dates(run),
                "lifted": bool(run.load_meta().compliance_unlocked),
                "locked": is_locked(run),
                "claimed": plan.lock,
                "edited": bool(plan.edited_limits),
            })
    return root


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def _preset_folder() -> str:
    """The demo-preset folder's name, asked of the module that owns it.

    A pack without it is INCOMPLETE, for the same reason a pack missing two of
    its projects was: Knut asked for the complete package every time, and a
    check that knows only what the previous release happened to contain is the
    baseline-against-itself fault this file already learned once.
    """
    sys.path.insert(0, str(_HERE))
    import make_verification_preset_demos as _PRESETS
    return _PRESETS.FOLDER


def verify_pack(path: "Path") -> "list[str]":
    """What is MISSING from a built pack, as sentences. Empty means complete.

    **A PACK SHIPPED WITH TWO OF ITS SIX PROJECTS MISSING, AND THE CHECK THAT
    SHOULD HAVE CAUGHT IT COMPARED THE WRONG THING.** Knut, 2026-09-13, on the
    beta 8 release: *"the last published ChromIQ-Report-Limit-Demos project
    collection did not contain all projects as previous demo package. The
    complete package should always be published."*

    He is right. The zip was built by hand-listing four project names, taken
    from the previous release rather than from `PROJECTS`, and the check run
    against it compared only the archive's ROOT FOLDER NAME with the previous
    one. Both matched. That is the same shape as comparing a plist against a
    backup that already holds the bad value: a baseline is only evidence if
    something independent says the baseline was right.

    So the pack is checked against `PROJECTS`, which is the one place that
    knows, and the release step calls this rather than eyeballing a listing.
    Accepts a directory or a `.zip`.
    """
    import zipfile
    want = [name for name, _plans in PROJECTS]
    missing: "list[str]" = []
    path = Path(path)
    if path.suffix.lower() == ".zip":
        if not path.is_file():
            return [f"no such archive: {path}"]
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        present = {n.split("/")[1] for n in names
                   if "/" in n and len(n.split("/")) > 1}
        extras = {"README.txt", "intended-vs-actual.json", _preset_folder()}
    else:
        if not path.is_dir():
            return [f"no such folder: {path}"]
        present = {c.name for c in path.iterdir()}
        extras = {"README.txt", "intended-vs-actual.json", _preset_folder()}
    for name in want:
        if name not in present:
            missing.append(f"project missing: {name}")
    for name in sorted(extras):
        if name not in present:
            missing.append(f"file missing: {name}")
    missing += _verdicts_missing(path)
    return missing


def _verdicts_missing(path: Path) -> "list[str]":
    """Every measurement in the pack that ships without a saved verdict.

    Knut, 2026-09-13: *"Make sure all verdicts exist in the demo package"* and
    *"Why is the verdict and measurements not kept as part of the demo data
    created, so that it is a real test?"*. The package saved a report under
    each dated verification and none beside the sheet a profile was built
    from, although `tab_measure._maybe_save_measurement_report` runs after
    EVERY measurement the app makes. Opening a run's own measurement therefore
    reached the report window's last-resort branch, and the page told him the
    verdict had been lost by an older ChromIQ.

    Checked on the ARTEFACT, not on the generator: the pack is what ships, and
    a check that reads the code that built it is the baseline-against-itself
    fault this function's own docstring is about.

    **ONE LIST OF MEASUREMENTS, WHATEVER THE PACK IS PACKED IN.** The first
    version walked a folder and a `.zip` down two different code paths, and
    they were not the same check: the folder branch skipped the role-named
    intermediates and the zip branch skipped nothing, so any pack holding a
    run that used measurement averaging passed as a folder and failed as a
    zip. A `.ti3` at the root of a zip could not find a report at all, because
    its "folder" came out as its own file name. Found by an adversary round
    that built a synthetic pack rather than trusting the two to agree, and the
    commit that claimed "complete, folder and zip" was only true because
    today's generator happens to produce neither `reads/` nor `cal/`.
    """
    files = _pack_listing(path)
    if files is None:
        return []
    reports = {n for n in files if _REPORT_RE.search(n)}
    gaps: "list[str]" = []
    for name in sorted(files):
        if not name.endswith(".ti3") or _is_intermediate(name):
            continue
        home = name.rsplit("/", 1)[0] if "/" in name else ""
        want = f"{home}/reports/report_" if home else "reports/report_"
        beside = [m for m in reports if m.startswith(want)]
        if not beside:
            gaps.append(f"no saved report beside {name}")
        elif not any(_has_verdict(_pack_read(path, m)) for m in beside):
            gaps.append(f"no verdict in any report beside {name}")
    return gaps


#: A saved report, by the name `save_report` gives it.
_REPORT_RE = re.compile(r"(?:^|/)reports/report_[^/]*\.json$")

#: Folders and stems that hold a measurement nobody judges: the reads that
#: feed an average, a build's own inputs and outputs, the tool scratch, and
#: the archive of superseded reports. `cal/` is NOT here: a calibration
#: measurement is a measurement, and if a pack ever ships one it should carry
#: its verdict like the rest.
_NOT_A_JUDGED_SHEET = ("reads", "cache", "old", "_work")
_NOT_A_JUDGED_STEM = ("preconditioning", "merged")

#: **AND A COLORIMETRIC REFERENCE IS NOT A MEASUREMENT.** A FROM PROFILE GAMUT
#: chart ships `<stem>-reference.ti3` beside itself: it is the chart's AIM
#: values, written at build time, and nobody measured it, so demanding a saved
#: verdict beside it is demanding a verdict on a chart file.
#:
#: **BOTH PACKS SHIPPED WITH THIS CHECK FAILING AND NOBODY RAN IT.** Measured
#: 2026-09-19: `--verify` on the beta.21-era archive in
#: `~/Desktop/ChromIQ-beta22-proof/b393-the-demo-package/build/` prints
#: INCOMPLETE with 23 of these and nothing else, and so did the first build of
#: this round. A completeness check that cries wolf is a completeness check
#: nobody reads, which is exactly what `verify_pack`'s own docstring is about:
#: the pack that shipped with two projects missing passed a check comparing the
#: wrong thing.
_REFERENCE_SUFFIX = "-reference"


def _is_intermediate(name: str) -> bool:
    parts = name.split("/")
    stem = parts[-1].rsplit(".", 1)[0]
    return (any(d in _NOT_A_JUDGED_SHEET for d in parts[:-1])
            or stem in _NOT_A_JUDGED_STEM
            or stem.endswith(_REFERENCE_SUFFIX))


def _pack_listing(path: Path) -> "list[str] | None":
    """Every file in the pack, as "/"-joined paths relative to its root.

    One listing for a folder and for a `.zip`, so the two cannot become two
    different checks again. A zip's own top-level folder is stripped, so the
    names line up with the folder form.
    """
    import zipfile
    if path.suffix.lower() == ".zip":
        if not path.is_file():
            return None
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
        roots = {n.split("/")[0] for n in names if "/" in n}
        if len(roots) == 1:
            cut = len(next(iter(roots))) + 1
            names = [n[cut:] for n in names if n.startswith(next(iter(roots)) + "/")]
        return names
    if not path.is_dir():
        return None
    return [str(f.relative_to(path)).replace(os.sep, "/")
            for f in path.rglob("*") if f.is_file()]


def _pack_read(path: Path, name: str) -> bytes:
    """One file out of the pack, by the name `_pack_listing` gave it."""
    import zipfile
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            roots = {n.split("/")[0] for n in zf.namelist() if "/" in n}
            prefix = f"{next(iter(roots))}/" if len(roots) == 1 else ""
            return zf.read(prefix + name)
    return (path / name).read_bytes()


def _has_verdict(raw: bytes) -> bool:
    """Whether a saved report carries a verdict with rows in it.

    Asked of the same function the window asks, so "the pack has verdicts" and
    "the window finds them" cannot come apart. **AND THE ROWS MUST NOT BE
    EMPTY**: `recorded_verdict` requires only that `rows` is a list, so a
    report holding `{"verdict": {"rows": []}}` satisfied it and a pack whose
    every verdict was hollow was reported complete. Found by an adversary round
    feeding exactly that.
    """
    import json
    from workflow.measurement_report import recorded_verdict
    try:
        rec = recorded_verdict(json.loads(raw.decode("utf-8")))
    except Exception:                                          # noqa: BLE001
        return False
    return bool(rec and rec.get("rows"))


def _misses(r: dict) -> bool:
    """A date that did not do what it was designed to: a different set of
    crossed rows, or a border date (K29) that did not save its number."""
    if sorted(r["intended"]) != sorted(r["actual"]):
        return True
    b = r.get("border")
    return bool(b) and (b["got"] is None
                        or abs(float(b["got"]) - float(b["want"])) > 1e-9)


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
    ap.add_argument("--verify", default="",
                    help="check a built pack (folder or .zip) for completeness "
                         "and exit, building nothing")
    ap.add_argument("dest", nargs="?", default=str(_HERE.parent / "demo-projects" / FOLDER))
    ap.add_argument("--zip", action="store_true",
                    help="also write <dest>.zip beside the folder")
    ap.add_argument("--report", default="",
                    help="write the intended/actual table as JSON to this path")
    ap.add_argument("--survey", action="store_true",
                    help="report every story that claims the wrong verdict "
                         "instead of stopping at the first; the build then "
                         "exits non-zero and is not a pack")
    ap.add_argument("--only", action="append", default=[],
                    help="build only this project (repeatable). For working "
                         "on one design: the coverage checks need the whole "
                         "pack and are skipped, so such a build is never a "
                         "pack to ship")
    args = ap.parse_args(argv)

    if args.verify:
        gaps = verify_pack(Path(args.verify))
        for g in gaps:
            print(f"  {g}")
        n = len(PROJECTS)
        print(f"{'INCOMPLETE' if gaps else 'complete'}: {args.verify} "
              f"({n} projects expected)")
        return 2 if gaps else 0

    if not (ARGYLL / "targen").exists() or not SRGB.exists():
        print(f"ArgyllCMS with ref/sRGB.icm is required ({ARGYLL}).")
        return 2

    dest = Path(args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    cache_root = dest / "_charts"
    cache_root.mkdir(exist_ok=True)

    bad_plans = [(n, i + 1, c)
                 for n, plans in PROJECTS
                 for i, plan in enumerate(plans)
                 if (c := plan.lock_complaint())]
    for n, i, c in bad_plans:
        print(f"  PLAN {n}/run{i}: {c}")
    if bad_plans:
        return 2

    # EVERY SET A PLAN NAMES MUST BE ONE THE REPORT WINDOW WOULD OFFER, and
    # this is checked BEFORE any Argyll is run.
    #
    # A set with no limit-bearing row judges nothing, so a run bound to one
    # produces a column of N-A whatever its measurement says, and every
    # `expect` on it misses. That is what the two Custom columns were until the
    # round that gave them numbers: this generator can name them only on a
    # ChromIQ that has that round. Without it the build used to spend its
    # seventeen seconds and then report four mismatches, which reads as a
    # design that missed rather than as a package built against the wrong app.
    unusable = sorted({plan.set_id
                       for _n, plans in PROJECTS for plan in plans
                       if plan.set_id not in _selectable()})
    if unusable:
        print("This package names limit sets this ChromIQ does not offer:")
        for sid in unusable:
            print(f"  {sid}")
        print("A set with no limit-bearing row judges nothing, so a run bound "
              "to one is a column of N-A and every expectation on it misses.\n"
              "This build needs the ChromIQ that gives those columns their "
              "numbers.")
        return 2

    results: list = []
    lock_rows: list = []
    global SURVEY
    SURVEY = bool(args.survey)
    unknown = [n for n in args.only if n not in dict(PROJECTS)]
    if unknown:
        print(f"no such project: {', '.join(unknown)}")
        return 2
    for name, plans in PROJECTS:
        if args.only and name not in args.only:
            continue
        build_project(dest, name, plans, cache_root, results, lock_rows)
    # AFTER EVERY PROJECT IS BUILT (K25): the seed writes reports across
    # Report-Folders and its second project, so both must exist first.
    if (dest / FOLDERS_PROJECT).is_dir() and (
            not args.only or FOLDERS_PROJECT in args.only):
        shutil.rmtree(dest / "reports", ignore_errors=True)
        other = dest / FOLDERS_OTHER_PROJECT
        FOLDERS_MANIFEST[:] = seed_report_folders(
            dest / FOLDERS_PROJECT,
            other if (not args.only or FOLDERS_OTHER_PROJECT in args.only)
            and other.is_dir() else None)
        # #182 beta 39: the calibrations and their reports, after the
        # shared `reports/` above has been emptied and refilled.
        CAL_MANIFEST[:] = seed_calibrations(dest)
    # K29: the renamed project, after the shared reports/ has been refilled.
    RENAMED_MANIFEST[:] = seed_renamed(dest)
    shutil.rmtree(cache_root, ignore_errors=True)

    # THE DEMO PRESETS (#182, Knut 2026-09-19), built by their own generator.
    # They are charts, not projects: `scripts/make_verification_preset_demos.py`
    # owns them, this line only puts its folder inside the pack a user
    # downloads. Kept as a separate module because nothing about them needs
    # ArgyllCMS, a profile or a measurement, and a 250 KB generator is not a
    # place to add a fifteenth thing.
    sys.path.insert(0, str(_HERE))
    import make_verification_preset_demos as _PRESETS
    _PRESETS.build(dest / _PRESETS.FOLDER)
    print(f"\ndemo presets: {len(_PRESETS.DEMOS)} written to "
          f"{dest / _PRESETS.FOLDER}")

    if args.only:
        bad = [r for r in results
               if _misses(r)]
        print(f"\n--only: {len(results)} dated verifications, "
              f"{len(results) - len(bad)} matching their design. No README, "
              f"no coverage: this is not a pack.")
        for r in bad:
            print(f"  MISMATCH {r['project']}/{r['run']}/{r['date']}: "
                  f"intended {r['intended']} actual {r['actual']} border {r.get('border')}")
        return 1 if (bad or SURVEY_FAULTS) else 0

    cov = coverage(dest, results)
    (dest / "README.txt").write_text(readme(results, lock_rows, cov, dest),
                                     encoding="utf-8")
    (dest / "intended-vs-actual.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    if args.report:
        Path(args.report).write_text(json.dumps(results, indent=2), encoding="utf-8")

    bad = [r for r in results if _misses(r)]
    print(f"\n{len(results)} dated verifications, "
          f"{len(results) - len(bad)} matching their design.")
    for r in bad:
        print(f"  MISMATCH {r['project']}/{r['run']}/{r['date']}: "
              f"intended {r['intended']} actual {r['actual']} border {r.get('border')}")

    # AND THE COVERAGE CLAIM, which is the one the package was reported for.
    # Matching a design says every date crossed the row it meant to; it says
    # nothing about whether a metric was ever exercised, or whether the report
    # was ever seen to say that a chart cannot support one.
    print(f"\nverification chart sizes: "
          f"{', '.join(str(s) for s in cov['verify_chart_sizes'])} patches, "
          f"over {cov['support_reports']} saved reports")
    for r in cov["support_rows"]:
        state = ("supported and, on another chart, not"
                 if r["value"] and r["na"] else
                 "supported everywhere; no chart can withhold it"
                 if r["value"] and r["cannot_unsupport"] else
                 "supported nowhere" if not r["value"] else
                 "never seen unsupported")
        print(f"  {r['id']:34} value on {r['value']:>3}, N-A on {r['na']:>3}"
              f"  ({state})")
    sfaults = support_faults(cov)
    for f in sfaults:
        print(f"  COVERAGE: {f}")

    # KNUT'S MATRIX: every judgeable row against EVERY limit set, both halves.
    mf = matrix_faults(cov)
    done = sum(1 for c in cov["matrix_cells"] if c["complete"])
    print(f"\nlimit-set matrix: {done} of {len(cov['matrix_cells'])} judged "
          f"cells show the row BOTH over its limit and inside it, across "
          f"{len(cov['matrix_sets'])} selectable limit sets")
    for f in mf:
        print(f"  MATRIX: {f}")
    (dest / "limit-set-matrix.json").write_text(
        json.dumps({"sets": cov["matrix_sets"],
                    "cells": cov["matrix_cells"]}, indent=2),
        encoding="utf-8")
    sfaults = sfaults + mf

    if args.zip:
        archive = dest.parent / f"{dest.name}"
        made = shutil.make_archive(str(archive), "zip", root_dir=str(dest.parent),
                                   base_dir=dest.name)
        size = Path(made).stat().st_size
        print(f"archive: {made}  ({size / 1e6:.1f} MB)")
    print(f"written to {dest}")
    for f in SURVEY_FAULTS:
        print(f"  STORY: {f}")
    return 1 if (bad or sfaults or SURVEY_FAULTS) else 0


def _selectable() -> "set[str]":
    """The sets the report window would offer, asked of the app rather than
    listed here, so a set that stops being offered is caught the same way one
    that starts being offered is."""
    from workflow.compliance_sets import selectable_set_ids
    return set(selectable_set_ids({}))


def _wrap(text: str, width: int) -> "list[str]":
    """Hard-wrap a sentence for the README's fixed-width prose."""
    import textwrap
    return textwrap.wrap(" ".join(text.split()), width) or [""]


#: Small numbers as words, for a heading that must agree with a computed list.
_WORDS = {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
          6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
          11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
          15: "fifteen", 16: "sixteen"}

#: Rows that are ordered against another row, and therefore cannot cross their
#: limit while that other row stays inside its own. The ORDER is a fact about
#: the statistics; whether it forces a second crossing depends on the NUMBERS,
#: so it is read from the shipped sets rather than asserted.
_ORDERED_UNDER = {
    "best95_de00_avg": "worst5_de00_avg",
    "all_de00_avg": "worst5_de00_avg",
    "all_de00_p95": "all_de00_max",
}


def _forced_pairs() -> "list[tuple[str, str]]":
    """`(row, why)` for every row that cannot cross alone under every set.

    THE COUNT IN THIS README HAS BEEN WRONG TWICE, in both directions: it
    claimed three rows and one of them was direction-dependent, then claimed
    two and missed one that really is forced. So it is computed. A row counts
    only when EVERY shipped set gives its companion a limit no larger than its
    own, which is what makes the crossing unavoidable rather than merely
    likely.
    """
    from workflow.compliance_sets import SET_BY_ID, effective_limits
    sets = [sid for sid in SET_BY_ID if sid.startswith("chromiq_")]
    out: "list[tuple[str, str]]" = []
    for rid, other in _ORDERED_UNDER.items():
        forced = True
        for sid in sets:
            lim = effective_limits(sid, {})
            a_, b_ = lim.get(rid), lim.get(other)
            if (a_ is None or b_ is None
                    or a_.number is None or b_.number is None
                    or b_.number > a_.number):
                forced = False
                break
        if forced and sets:
            out.append((rid, ROW_TITLES.get(other, other)
                        + " crossing at the same time"))
    return out


def _sheet_count(f) -> "int | None":
    """NUMBER_OF_SETS off a ti1/ti2/ti3, or None if it cannot be read."""
    import re as _re
    if f is None:
        return None
    try:
        m = _re.search(r"^NUMBER_OF_SETS\s+(\d+)",
                       f.read_text(encoding="utf-8", errors="replace"), _re.M)
    except OSError:
        return None
    return int(m.group(1)) if m else None


def _chart_label(dest: Path, project: str, run_id: str, recipe,
                 verify: bool = False) -> str:
    """The recipe's label, carrying the number the READER will see, and the
    number that is actually on the paper when those differ.

    Two counts, and the README used to print the wrong one of them. `printtarg`
    PADS a sheet to fill its rows: the 156-patch A3 verification chart goes on
    paper as 168, and the 400-patch profile chart as 405. Those extra patches
    are printtarg's own, they are not in the `.ti1`, so nothing measures them
    and no report ever counts them. Measured across the built package: 31 dated
    reports, and the three whose chart was padded say 156 where the README said
    168.

    A reader opens the report beside this file to match one against the other,
    so the number in front is the one the report shows, taken from the `.ti3`
    rather than assumed from the request. The sheet's own count is named after
    it, because it is what they will count if they hold the print.
    """
    import re as _re
    if dest is None:
        return recipe.label
    d = dest / project / "runs" / run_id
    if verify:
        d = d / "verifications"
    sheet = _sheet_count(next(iter(sorted(d.glob("*.ti2"))), None))
    # The measurement: beside the chart for a profile run, one per date for a
    # verification. They should agree; if a build ever makes them disagree the
    # label says so instead of picking one.
    ti3s = sorted(d.glob("*.ti3")) if not verify else sorted(
        d.glob("*/*.ti3"))
    judged = sorted({c for c in (_sheet_count(f) for f in ti3s)
                     if c is not None})
    if len(judged) > 1:
        return recipe.label + (" (the measurements disagree about how many "
                               "patches they hold: "
                               + ", ".join(str(c) for c in judged) + ")")
    front = judged[0] if judged else sheet
    if front is None:
        return recipe.label
    label = _re.sub(r"^\d+", str(front), recipe.label, count=1)
    if sheet is not None and judged and sheet != front:
        label += (f" (printtarg padded the sheet to {sheet}; the "
                  f"{sheet - front} extra are not measured and not judged)")
    elif front != recipe.patches:
        label += f" (asked for {recipe.patches})"
    return label


def _lock_index(lock_rows: "list[dict]") -> "list[tuple[str, str]]":
    """The three lock lines of the README's index, named from MEASURED state.

    These three lines were hand-written, and a challenge round found them still
    saying "exactly one dated verification, LOCKED ... Threshold-Series, run3"
    after the lock rule had changed and after that run had gained a twin with
    two dates. The table forty lines above them was already correct and read
    back from the app; the index contradicted it on the same page, and the index
    is the half a reader acts on, because it says which run to open.

    The guard added with that table did not cover this, because it bans the word
    "lock" from a plan's DESCRIPTION and these lines are prose in the README.
    So they are generated too, and from the same measured rows.
    """
    want = [("locked, so the set cannot be changed", lambda r: r["locked"]),
            ("one date only, so the set is still offered",
             lambda r: not r["locked"] and r["dates"] < 2),
            ("two dates, but the lock lifted by hand",
             lambda r: not r["locked"] and r["dates"] >= 2 and r["lifted"])]
    out: "list[tuple[str, str]]" = []
    for label, pick in want:
        # The SIMPLEST example of each state, so the reader opens the run where
        # the state is the only interesting thing rather than the busiest one.
        # An unedited column first, then the fewest dates, and only then the
        # name: sorting by size alone landed the locked line on a run whose own
        # README entry says "(edited for this run)", which is a second thing to
        # explain in a line that exists to demonstrate one.
        hits = sorted((r for r in lock_rows if pick(r)),
                      key=lambda r: (r.get("edited", False), r["dates"], r["run"]))
        if hits:
            out.append((label, hits[0]["run"].replace("/", ", ")))
    return out


def _type_index(type_set_rows: "list[dict]",
                multi: "list[str]") -> "list[tuple[str, str]]":
    """The index lines that name a run for each built report type.

    Generated for exactly the reason `_lock_index` is: the index is the half a
    reader acts on, because it says which run to open, and a hand-written line
    naming a run goes stale the moment the runs move. The line for a type no
    run produces is simply not written, rather than pointing somewhere wrong.
    """
    out: "list[tuple[str, str]]" = []
    for _tid, name, _blurb, built in REPORT_TYPE_MENU:
        if not built:
            continue
        # THE RUN WHERE THE TYPE IS THE SUBJECT, not the first one in
        # alphabetical order. Sorting by name alone pointed "the Full colour
        # check document" at a run whose own entry says "(edited for this
        # run)", which is a second thing to explain in a line that exists to
        # show one, exactly as `_lock_index` found for the lock lines.
        hits = sorted((r for r in type_set_rows if r["type"] == name),
                      key=lambda r: (not r["run"].startswith("Report-Types/"),
                                     "edited" in r["set"], r["run"]))
        if hits:
            out.append((f"the {name} document", hits[0]["run"].replace("/", ", ")))
    if multi:
        # THE RUN HOLDING THE MOST TYPES (round 3B, F25). Every run holds two,
        # its profiling sheet's Printing record and its verifications' type,
        # so the first in name order (Border-Conditions/run1) showed nothing a
        # reader came for.
        best = _richest_multi_type_run(multi)
        out.append(("a run holding reports of several types",
                    best.replace("/", ", ")))
    return out


def paper_white_lines(results: list) -> "list[str]":
    """The README's account of the paper white each report RECORDS, read off
    the built reports (round 3B, F13).

    The pack said "95.5 / 0.2 / 1.4 on every ordinary sheet", and three kinds
    of run record another: a sheet judged in absolute Lab (raw, or nobody
    wrote the printing down), where nothing pins the paper patch; a From
    Profile Gamut chart, whose paper is its white cube corner; and a chart
    with no paper patch at all, where the report's "lightest patch" is simply
    the lightest colour. Each is named with the numbers it recorded.
    """
    runs: "dict[str, dict]" = {}
    for r in results:
        pw = r.get("paper_white") or {}
        lab = pw.get("lab")
        if not isinstance(lab, (list, tuple)) or len(lab) != 3:
            continue
        key = f"{r['project'].replace('Report-Limits-', '')}/{r['run']}"
        e = runs.setdefault(key, {"r": r, "labs": {}})
        e["labs"].setdefault(tuple(round(float(v), 2) for v in lab),
                             []).append(str(r["date"])[:10])
    same = 0
    out: "list[str]" = []
    for key in sorted(runs, key=lambda k: (k.split("/")[0],
                                           int(k.split("run")[-1] or 0))):
        e = runs[key]
        r, labs = e["r"], e["labs"]
        seen = "; ".join(f"{L:.2f} / {a:.2f} / {b:.2f} on "
                         + ", ".join(ds) for (L, a, b), ds in labs.items())
        if not r.get("has_paper_patch", True):
            (L, a, b), = list(labs)[:1] or [(0.0, 0.0, 0.0)]
            kind = "grey" if math.hypot(a, b) < 2.0 else "colour"
            out.append(f"{key}: this chart has no paper patch, so its 'paper "
                       f"white' is the lightest patch, an L* {L:.0f} {kind} "
                       f"({seen}).")
        elif r.get("chart") == "gamut":
            out.append(f"{key}: a From Profile Gamut chart. Its paper is the "
                       f"chart's white cube corner, put on the chart's own aim "
                       f"and moved toward yellow by the date's designed paper "
                       f"difference: {seen}.")
        elif r.get("paper", "default") != "default" and all(
                max(abs(x - p) for x, p in zip(k, r["paper_lab"])) <= 0.1
                for k in labs):
            pc = PAPER_CLASSES[r["paper"]]
            out.append(f"{key}: printed on {pc.name.lower()}, "
                       f"{pc.lab[0]:.1f} / {pc.lab[1]:.1f} / {pc.lab[2]:.1f} "
                       f"(within 0.1), on every date: {seen}.")
        elif all(max(abs(x - p) for x, p in zip(k, PAPER_LAB)) <= 0.1
                 for k in labs):
            same += 1
        elif r.get("print") in ("raw", "none"):
            why = ("printed raw" if r.get("print") == "raw"
                   else "nobody recorded how it was printed")
            out.append(f"{key}: {why}, so it is judged in absolute Lab and "
                       f"nothing pins the paper patch; it carries the date's "
                       f"designed difference like every other patch: {seen}.")
        else:
            out.append(f"{key}: {seen}.")
    head = (f"The paper as printed, {PAPER_LAB[0]:.1f} / {PAPER_LAB[1]:.1f} / "
            f"{PAPER_LAB[2]:.1f} (within 0.1), on every date of {same} "
            f"{'run' if same == 1 else 'runs'}. "
            f"The others, and why:")
    return [head] + out


def _multi_type_count(line: str) -> int:
    """How many report types one `multi_type_runs` line names."""
    return len(line.split(": ", 1)[1].split("), ")) if ": " in line else 0


def _richest_multi_type_run(multi: "list[str]") -> str:
    """The run name of the `multi_type_runs` line naming the most types."""
    best = max(multi, key=lambda ln: (_multi_type_count(ln),
                                      -multi.index(ln)))
    return best.split(": ", 1)[0]


def coverage(dest: Path, results: list) -> dict:
    """Which report rows these projects actually exercise, read back from the
    saved reports rather than from the designs that asked for them.

    A challenge round's rule: a row no date ever crosses is a row on which a
    clean verdict proves nothing, so it has to be NAMED rather than counted as
    covered. This is what names it.
    """
    from core.file_manager import Run
    from workflow.measurement_report import row_values
    from workflow.run_compliance import run_limits

    with_value: set = set()
    for rep in sorted(dest.rglob("report_*.json")):
        for rid, info in (row_values(json.loads(rep.read_text(encoding="utf-8")))
                          or {}).items():
            if info.get("value") is not None:
                with_value.add(rid)

    # WHICH ROWS ARE JUDGED IS READ FROM THE RUNS, NOT FROM WHAT CROSSED.
    # Deriving it from the crossings would make this check answer itself: a row
    # that stopped crossing would also stop counting as judged, and the summary
    # would go on saying nothing is untested.
    judged: set = set()
    for pd in sorted(dest.glob("Report-Limits-*")):
        for rd in sorted((pd / "runs").glob("run*")):
            for rid, lim in run_limits(Run.for_dir(rd), {}).limits.items():
                if lim.number is not None:
                    judged.add(rid)
    judged &= with_value

    crossed: set = set()
    for r in results:
        crossed |= set(r["actual"])
    # AND HOW MANY A SHIPPED SET JUDGES, which is a different number from how
    # many any run judges: one run's edited column adds the tone-ramp row. The
    # README stated both, one typed and one computed, and they disagreed.
    from workflow.compliance_sets import SET_BY_ID, effective_limits
    shipped: set = set()
    for sid in SET_BY_ID:
        if not sid.startswith("chromiq_"):
            continue
        for rid, lim in effective_limits(sid, {}).items():
            if lim.number is not None:
                shipped.add(rid)
    out = {"with_value": sorted(with_value), "judged": sorted(judged),
           "shipped_judged": sorted(shipped & with_value),
           "crossed": sorted(crossed & with_value),
           "uncrossed": sorted(judged - crossed)}
    out.update(type_set_coverage(dest))
    out.update(message_coverage(dest))
    out.update(metric_coverage(dest, results))
    out.update(support_coverage(dest))
    out.update(matrix_coverage(results))
    out.update(custom_column_facts())
    return out


def custom_column_facts() -> dict:
    """The two things a reader of the Custom-column runs has to be told, both
    computed from the sets as they actually are.

    Neither is a property of this package's data, so neither can be shown by
    building a different measurement, and a reader who works one of them out
    for themselves from a verdict will have worked out the wrong thing.
    """
    from workflow.compliance_sets import (ROW_BY_ID, effective_limits,
                                          limit_bearing, selectable_set_ids)

    ids = [sid for sid in selectable_set_ids({}) if sid.startswith("custom_")]
    facts: dict = {"custom_ids": ids, "custom_same_numbers": False,
                   "custom_shape_differs": [], "custom_number_differs": [],
                   "custom_total": 0, "custom_fillable": 0,
                   "custom_unfillable": []}
    if not ids:
        return facts
    lim = limit_bearing(effective_limits(ids[0], {}))
    facts["custom_total"] = len(lim)
    # A row a ChromIQ verification chart can put a number on is one ChromIQ
    # computes from the measurement itself; a `ref` row waits for a reference
    # measurement of the printing condition, which is not built.
    fillable = [rid for rid in lim if ROW_BY_ID[rid].status in ("now", "build")]
    facts["custom_fillable"] = len(fillable)
    facts["custom_unfillable"] = sorted(ROW_BY_ID[rid].label for rid in lim
                                        if rid not in fillable)
    if len(ids) == 2:
        a_, b_ = (effective_limits(i, {}) for i in ids)
        # THE NUMBERS AND THE SHAPE ARE TWO DIFFERENT QUESTIONS, and the first
        # version of this asked only one and got a misleading answer. Compared
        # cell for cell across all thirty rows, the two columns "differ" — but
        # every difference is on a row carrying NO number, where one column
        # shows ? or the cross and the other shows the dash, because the two
        # standards write limits over different rows. On every row that carries
        # a number they are identical, and it is the numbers that decide a
        # verdict.
        facts["custom_same_numbers"] = all(
            (a_[r].number is None) == (b_[r].number is None)
            and (a_[r].number is None
                 or (a_[r].is_should == b_[r].is_should
                     and abs(a_[r].number - b_[r].number) < 1e-9))
            for r in set(a_) | set(b_))
        facts["custom_shape_differs"] = sorted(
            ROW_BY_ID[r].label for r in set(a_) | set(b_)
            if a_[r].kind != b_[r].kind)
        # …AND THE ROWS THAT NOW DIFFER IN THE NUMBER ITSELF, which is the
        # half that can change a verdict. Empty until 2026-09-21: one table
        # put the same figure on both columns. Knut's researched figures are
        # given per column, following each standard's own structure, so the
        # two columns stopped being interchangeable and a reader CAN now read
        # one run against the other on these rows.
        facts["custom_number_differs"] = sorted(
            ROW_BY_ID[r].label for r in limit_bearing(a_)
            if r in limit_bearing(b_) and a_[r] != b_[r])
    return facts


#: WHY A MESSAGE THE REPORT CAN PRINT IS NOT IN THE PACKAGE, for the ones no
#: measurement can reach. Keyed by the code, so a message that arrives later
#: and is neither reached nor explained shows up as one nobody has accounted
#: for, which is the right way round: the list of messages is read from the
#: app, and only the excuses are written here.
#: "iso" USED TO BE IN HERE AND IS NOT ANY MORE, which is the point of the
#: list. Its excuse read "the two ISO columns hold no numbers, so a demo that
#: reached it would have to carry one of those numbers". That was true while
#: both Custom columns were empty: neither could be offered in the report
#: window and no run could be bound to one. They now start from ChromIQ's OWN
#: numbers, `Report-Limits-Custom-Columns` binds a run to each, and the
#: sentence is reached on both of their recovery dates. An excuse that outlives
#: the gap it explains is worse than no excuse at all: it tells a reader the
#: package cannot show something it shows twice.
UNREACHABLE_BY_DATA = {
    "empty": "The report window only offers a limit set that has at least one "
             "limit-bearing row (CH-11), so no choice a user can make reaches "
             "this. It is for a run bound to a set a later ChromIQ has stopped "
             "defining.",
    "needs_reference_file": "The rows that give this reason are the ones "
                            "needing a reference measurement of the printing "
                            "condition, and reading such a file is not built "
                            "yet. No ChromIQ limit set puts a number on them "
                            "either, so they carry no verdict and are not "
                            "drawn.",
    "no_reference": "A measurement with no reference at all, which a chart "
                    "built by ChromIQ always has. It is the state of a loose "
                    "file whose chart nobody can find.",
    # Round 3B, F22: this said "the same unbuilt reader as above", and the
    # reader is built (a From Profile Gamut chart's colorimetric reference).
    "no_corners": "A chart with a colorimetric reference that lacks one of "
                  "the eight cube corners. Every From Profile Gamut chart "
                  "ChromIQ builds declares all eight, and an ordinary chart "
                  "gives needs_reference_file instead, so no project here "
                  "reaches it.",
    "no_greys": "A chart with no neutral patch at all. Every chart targen "
                "builds has white and black, which are neutral, so this "
                "cannot be produced by asking for fewer grey steps; it would "
                "need a chart edited by hand into something no printer "
                "workflow makes.",
    # Round 3B, F22/F27: "the same again" pointed at an entry printed BELOW it
    # (the list is alphabetical), and the pack's own demo presets reach both.
    "no_white": "A grey ramp whose lightest step is below 90. targen always "
                "puts paper white in a chart, so no project here reaches it; "
                "the R06 FAIL demo preset (the lightest neutral at 89.9) "
                "builds a chart that does.",
    "no_black": "A grey ramp whose darkest step is above 10. targen always "
                "puts black in a chart, so no project here reaches it; the "
                "R07 FAIL demo preset (the darkest neutral at 10.1) builds a "
                "chart that does.",
    # Round 3B, F26: credited to a verification date, where the window greys
    # the Printing record out.
    "record_type": "A verification may not be a Printing record, and a "
                   "profiling sheet's own Printing record says not_graded "
                   "instead, so nowhere in this package shows it. Open a "
                   "loose .ti3 or a calibration and choose Printing record.",
    "not_computed": "A saved report with no grey block at all, which is what "
                    "a ChromIQ older than those rows wrote. This package "
                    "cannot carry one on purpose: such a report is now "
                    "recognised as stale and rebuilt the moment it is opened, "
                    "which is the fix for exactly the fault Knut hit in the "
                    "Example colours section.",
}


#: Why a ROW cannot be exercised against a limit by any demo data, by the
#: row's own status. Knut, 2026-09-11: *"make sure the metrics have a value
#: that can be tested against, and that all metrics limits are verified with
#: the ChromIQ-Report-Limit-Demos package."*
#:
#: Eight of the thirty rows can be. The other twenty-two cannot, for three
#: reasons that are properties of the ROW and not of this package, and the
#: worst possible answer to that is to invent a measurement. A demo that
#: pretended to have read a gloss meter, nine readings at set positions, or a
#: xenon fading rig would make the package lie about what ChromIQ measures,
#: which is the one thing a shared fixture must never do. What the package
#: shows for those rows instead is that they read N-A or ✕ and say why, which
#: is itself worth seeing.
UNCOVERABLE_ROW_STATUS = {
    "ref": "Computable only against a reference measurement of the printing "
           "condition that the user supplies. Reading such a file is not "
           "built (design record section 9), so no chart and no measurement "
           "in this package can fill the row. It reads N-A with that reason.",
    "unknown": "The number this row would be judged against is in a clause "
               "ChromIQ does not hold, so every set shows ? for it and it "
               "never carries a verdict. Giving it a value here would be a "
               "measurement with nothing to test it against.",
    "unmeasurable": "ChromIQ cannot measure this at all: it needs equipment "
                    "or a procedure outside a chart and a spectrophotometer. "
                    "The row is kept so a reader sees what a standard asks "
                    "for, and it shows the cross that says ChromIQ cannot "
                    "supply it. Inventing a number for it is the one thing "
                    "this package must not do.",
}


def metric_coverage(dest: Path, results: list) -> dict:
    """Every row of the limits table, and whether the package tests it.

    Read from `compliance_sets.ROWS` rather than from a list here, so a row
    added to ChromIQ turns up as one the package does not cover.

    Four facts per row, and they are different questions: can ChromIQ compute
    it at all (the row's status), does a shipped limit set put a number on it,
    does any run in this package put a number on it, and does any date actually
    cross it. A row can have a value and never be tested, which is the case
    this whole table exists to make visible.
    """
    from core.file_manager import Run
    from workflow.compliance_sets import (ROWS, effective_limits,
                                          selectable_set_ids)
    from workflow.measurement_report import row_values
    from workflow.run_compliance import run_limits

    with_value: set = set()
    for rep in sorted(dest.rglob("report_*.json")):
        if "old" in rep.parts:
            continue
        try:
            doc = json.loads(rep.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for rid, info in (row_values(doc) or {}).items():
            if info.get("value") is not None:
                with_value.add(rid)

    judged: set = set()
    for pd in sorted(dest.glob("Report-Limits-*")):
        for rd in sorted((pd / "runs").glob("run*")):
            for rid, lim in run_limits(Run.for_dir(rd), {}).limits.items():
                if lim.number is not None:
                    judged.add(rid)

    # EVERY SET THE WINDOW OFFERS, not only the three ChromIQ ones. The two
    # Custom columns held nothing when this was written, so naming the three
    # was the same list; they now put a number on four more rows, and the line
    # this feeds said of the tone ramp that "no shipped set judges it" while a
    # set a user can choose from the pulldown did.
    shipped: set = set()
    for sid in selectable_set_ids({}):
        for rid, lim in effective_limits(sid, {}).items():
            if lim.number is not None:
                shipped.add(rid)

    crossed: "dict[str, str]" = {}
    for r in results:
        for rid in r["actual"]:
            crossed.setdefault(
                rid, f"{r['project'].replace('Report-Limits-', '')}"
                     f"/{r['run']}/{r['date']}")
    # AND THE DATE IT CAME BACK ON, because a row that crosses and stays over
    # proves half of what Knut asked for. Paired by run: the first later date
    # of the same run on which the row is not over its limit.
    recovered: "dict[str, str]" = {}
    for rid in crossed:
        for r in results:
            at = (f"{r['project'].replace('Report-Limits-', '')}"
                  f"/{r['run']}/{r['date']}")
            if rid in r["actual"]:
                continue
            src = crossed[rid].rsplit("/", 1)
            if at.rsplit("/", 1)[0] == src[0] and at.rsplit("/", 1)[1] > src[1]:
                recovered.setdefault(rid, at)
                break

    rows = []
    for row in ROWS:
        tested = row.id in judged and row.id in with_value
        rows.append({
            "id": row.id, "label": row.label, "status": row.status,
            "shipped": row.id in shipped, "limited_here": row.id in judged,
            "has_value": row.id in with_value, "tested": tested,
            "crossed_at": crossed.get(row.id, ""),
            "recovered_at": recovered.get(row.id, ""),
            "why_not": "" if tested else UNCOVERABLE_ROW_STATUS.get(row.status, ""),
        })
    return {"metric_rows": rows}


#: Rows the report fills from a single judged patch, so NO verification chart
#: can fail to support them and a demo claiming to show one would be inventing
#: a state the app cannot reach. Each entry says WHY, from the code:
#: `measurement_report.row_values` puts a number on every row with a
#: `metric_key` as soon as `graded_de00` has a block to read, and
#: `de00_stats` computes the all-patch and best-95 % figures for any n >= 1.
#: The one exception is the worst 5 %, whose set is EMPTY below twenty patches,
#: and that one IS demonstrated.
NO_CHART_CAN_UNSUPPORT = {
    "all_de00_avg":
        "the average over every judged patch, which exists as soon as one "
        "patch is judged. A chart cannot withhold it; only a sheet with no "
        "reference at all can, and that is a property of the measurement, not "
        "of the chart.",
    "best95_de00_avg":
        "the average over the best 95 %, which `de00_stats` takes as the whole "
        "chart when the worst-5 % set is empty, so it too exists for any chart "
        "with a judged patch.",
    "all_de00_max":
        "the largest error on the sheet, which exists whenever any patch is "
        "judged.",
    "all_de00_p95":
        "the largest of the best 95 %, which falls back to the largest of all "
        "patches on a small chart rather than becoming unavailable.",
}


def _chart_patches(report_path: Path) -> "int | None":
    """How many patches the verification chart behind a saved report has.

    Read off the sheet's own measurement rather than looked up in a plan, so
    the number in the table is the one the report was actually computed from.
    """
    vdir = report_path.parent.parent
    for cand in sorted(vdir.glob("*.ti3")) + sorted(vdir.glob("*.ti2")):
        try:
            for line in cand.read_text(encoding="utf-8",
                                       errors="replace").splitlines():
                if line.startswith("NUMBER_OF_SETS"):
                    return int(line.split()[1])
        except (OSError, ValueError):
            continue
    return None


def support_coverage(dest: Path) -> dict:
    """Per computable row, the two states the report can be in about it, and
    which chart sizes produced each.

    Knut, 2026-09-12: *"The demo project pack should use various sizes of test
    charts for verification, so that all conditions and metrics are checked,
    and to test and verify that the measurement report feature can detect if
    each metric is supported or not supported by a given chart used for
    verification."*

    `metric_coverage` above answers a different question and hides this one: it
    ORs the whole package together, so a row that one chart in fifty-seven can
    fill reads as covered while fifty-six sheets show N-A and nobody has looked
    at what they show. This asks the question per report instead, which is the
    unit the reader sees.

    A row is properly demonstrated only when the package holds BOTH a report
    where a chart supplies it and a report where a chart cannot, because the
    second is the case Knut asked to be able to watch the report detect. The
    rows for which the second state does not exist are named in
    :data:`NO_CHART_CAN_UNSUPPORT` with the reason, and are not counted against
    the package.
    """
    from workflow.compliance_sets import ROWS
    from workflow.measurement_report import row_values

    # "ref" JOINS THE LIST, because those three rows stopped being theoretical
    # the day this package gained a FROM PROFILE GAMUT chart: a chart that
    # carries a colorimetric reference supplies them and an ordinary chart does
    # not, so both halves of Knut's question exist for them now.
    computable = [r for r in ROWS if r.status in ("build", "now", "ref")]
    rows: list = []
    seen: "dict[str, dict]" = {
        r.id: {"value_on": set(), "na_on": set(), "value": 0, "na": 0,
               "reasons": set()} for r in computable}
    n_reports = 0
    sizes: set = set()
    for rep in sorted(dest.rglob("report_*.json")):
        if "old" in rep.parts:
            continue
        try:
            doc = json.loads(rep.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        # A DOCUMENT FILE (K23) holds no measurement, so it has no rows.
        if (doc.get("document") or {}).get("role") == "document":
            continue
        rv = row_values(doc) or {}
        if not rv:
            continue
        n_reports += 1
        n = _chart_patches(rep)
        if n:
            sizes.add(n)
        for r in computable:
            info = rv.get(r.id) or {}
            d = seen[r.id]
            if info.get("value") is not None:
                d["value"] += 1
                d["value_on"].add(n)
            else:
                d["na"] += 1
                d["na_on"].add(n)
                if info.get("reason"):
                    d["reasons"].add(str(info["reason"]))

    for r in computable:
        d = seen[r.id]
        rows.append({
            "id": r.id, "label": r.label,
            "value": d["value"], "na": d["na"],
            "value_on": sorted(x for x in d["value_on"] if x),
            "na_on": sorted(x for x in d["na_on"] if x),
            "reasons": sorted(d["reasons"]),
            "cannot_unsupport": NO_CHART_CAN_UNSUPPORT.get(r.id, ""),
        })
    return {"support_rows": rows, "support_reports": n_reports,
            "verify_chart_sizes": sorted(sizes)}


def matrix_coverage(results: list) -> dict:
    """EVERY JUDGEABLE ROW AGAINST EVERY LIMIT SET, both halves of each cell.

    Knut, 2026-09-18: *"those eleven can also be defined for all the Judge
    Against limit sets, so the demo data must verify that all thresholds can
    trigger correctly for every judged against limit set, not just test all the
    thresholds on one of the sets."*

    A cell is complete only when the package holds a dated verification judged
    against that set where the row is OVER its limit, **and** one where the row
    was judged and is inside it. A row that only ever crosses proves the
    threshold fires and says nothing about whether it ever releases; a row that
    is never over proves nothing at all.

    Read off the results of THIS build, so the table cannot drift from the
    data: `values` holds every row the report judged on that date and
    `actual` every row it found over the limit, both taken from the shipped
    `row_values` / `row_verdict` / `set_summary` rather than from the design.
    """
    from workflow.compliance_sets import ROW_BY_ID, selectable_set_ids
    sets = selectable_set_ids({})
    cells: dict = {}
    for sid in sets:
        for rid in ROW_BY_ID:
            cells[(sid, rid)] = {"judged": False, "over": "", "inside": ""}
    for r in results:
        sid = r.get("set_id") or ""
        at = (f"{r['project'].replace('Report-Limits-', '')}"
              f"/{r['run']}/{r['date']}")
        for rid in r.get("values", {}):
            c = cells.get((sid, rid))
            if c is None:
                continue
            c["judged"] = True
            if rid in r["actual"]:
                c["over"] = c["over"] or at
            else:
                c["inside"] = c["inside"] or at
    rows = []
    for (sid, rid), c in cells.items():
        if not c["judged"]:
            continue
        rows.append({"set": sid, "row": rid, "over": c["over"],
                     "inside": c["inside"],
                     "complete": bool(c["over"] and c["inside"])})
    rows.sort(key=lambda r: (sets.index(r["set"]), r["row"]))
    return {"matrix_sets": sets, "matrix_cells": rows}


def matrix_faults(cov: dict) -> list:
    """A cell the package claims and does not show. Same refusal as everywhere
    else in this file: the pack does not ship saying it tested something it
    did not."""
    out = []
    for c in cov["matrix_cells"]:
        if c["complete"]:
            continue
        missing = "never over its limit" if not c["over"] else "never inside it"
        out.append(f"{c['set']} / {c['row']}: judged in this package but "
                   f"{missing}, so the cell shows only half of what Knut "
                   f"asked for")
    return out


def support_faults(cov: dict) -> list:
    """Why this package may not claim to check every metric on every condition.

    The generator has always refused to ship a pack whose dated verifications
    miss their design. This is the same refusal applied to the coverage claim,
    which is the claim Knut's report was about: a row nothing fills, or a row
    no chart is ever seen to withhold, is a row the package has not tested
    whatever its README says.
    """
    faults = []
    for r in cov["support_rows"]:
        if not r["value"]:
            faults.append(
                f"no verification in this package puts a number on "
                f"{r['id']}: the row is computable and nothing exercises it")
        if not r["na"] and not r["cannot_unsupport"]:
            faults.append(
                f"no verification in this package shows {r['id']} reading N-A, "
                f"so the package never demonstrates the report detecting a "
                f"chart that cannot support the row, which is the half Knut "
                f"asked for")
    if len(cov["verify_chart_sizes"]) < 4:
        faults.append(
            f"the verification sheets use only "
            f"{len(cov['verify_chart_sizes'])} chart size(s) "
            f"({', '.join(str(s) for s in cov['verify_chart_sizes'])}); the "
            f"package is supposed to vary them so a row's availability can be "
            f"seen to follow the chart")
    return faults


def message_coverage(dest: Path) -> dict:
    """Every sentence and reason the report can print, and where the package
    shows it.

    Knut, 2026-09-11: *"The demo test data must be made so that all parts of
    the report can be shown and tested, including fault messages and border
    conditions."*

    THE LIST OF MESSAGES IS READ FROM THE APP, not typed here: every value of
    `compliance_sets.SUMMARY_REASONS` and every `measurement_report.REASON_*`
    constant. A message added tomorrow appears in this table as one the package
    does not reach, rather than being quietly absent from a typed list. Only
    the EXCUSES for the ones no data can reach are written by hand, above.

    Each saved report is judged the way the window would judge it: with the
    run's own limits, through each of the four documents ChromIQ can produce,
    because the type pulldown is live whatever the limits do.
    """
    from core.file_manager import Run
    from workflow.compliance_sets import (SUMMARY_REASONS, row_verdict,
                                          set_summary)
    from workflow import measurement_report as _mr
    from workflow.measurement_report import (REPORT_TYPE_MENU,
                                             report_types_for_kind, row_values)
    from workflow.run_compliance import run_limits

    builts =[tid for tid, _n, _b, built in REPORT_TYPE_MENU if built]
    where_sentence: "dict[str, str]" = {}
    where_reason: "dict[str, str]" = {}
    for pd in sorted(dest.glob("Report-Limits-*")):
        short = pd.name.replace("Report-Limits-", "")
        for rd in sorted((pd / "runs").glob("run*"),
                         key=lambda p: int(p.name[3:] or 0)):
            _rec = run_limits(Run.for_dir(rd), {})
            limits, set_id = _rec.limits, _rec.set_id
            for rep_path in sorted(rd.rglob("report_*.json")):
                if "old" in rep_path.parts:
                    continue
                try:
                    rep = json.loads(rep_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                # A DOCUMENT FILE (K23) holds no measurement to judge.
                if (rep.get("document") or {}).get("role") == "document":
                    continue
                date = (rep_path.parent.parent.name
                        if rep_path.parent.parent != rd else "profiling")
                at = f"{short}/{rd.name}/{date}"
                # ONLY THE TYPES THIS MEASUREMENT'S KIND MAY HAVE (round 3B,
                # F26). Every built type used to be tried on every report, so
                # the Printing record's own sentence was credited to a
                # verification date, where the window greys that type out.
                kind = KIND_PROFILING if date == "profiling" else KIND_VERIFICATION
                allowed = set(report_types_for_kind(kind))
                for tid in (t for t in builts if t in allowed):
                    got = _crossed_rows(rep, limits, row_values, row_verdict,
                                        set_summary, tid, set_id)
                    where_sentence.setdefault(got["reason"], at)
                    # ONLY THE REASONS ON ROWS THE WINDOW DRAWS. Reading them
                    # off `row_values` instead counted `needs_reference_file`
                    # as demonstrated, on rows no ChromIQ set puts a limit on,
                    # which therefore carry no word and are never on the page.
                    for code in got["shown_reasons"].values():
                        where_reason.setdefault(code, at)

    sentences = []
    for key, text in SUMMARY_REASONS.items():
        at = where_sentence.get(text, "")
        sentences.append({"key": key, "text": text, "at": at,
                          "why_not": "" if at else UNREACHABLE_BY_DATA.get(key, "")})
    reasons = []
    codes = sorted({getattr(_mr, n) for n in dir(_mr) if n.startswith("REASON_")})
    for code in codes:
        at = where_reason.get(code, "")
        reasons.append({"code": code, "at": at,
                        "why_not": "" if at else UNREACHABLE_BY_DATA.get(code, "")})
    return {"sentences": sentences, "reasons": reasons}


def type_set_coverage(dest: Path) -> dict:
    """Which document each built run produces and what it is judged against,
    READ BACK FROM THE RUNS, plus what nothing covers.

    Asked of the run, not of the plan, and for the same reason the lock table
    is: the plan says what was asked for and the run says what exists. The
    default type is stored NOWHERE on a run that never chose one, so a plan
    and a `meta.json` can differ without anybody lying, and only one of them
    is what a reader will open.

    The missing list is the half that earns this function. A coverage table
    that only lists what is present cannot be told apart from a coverage table
    that is short; naming the empty cells is what lets a reader check the
    claim instead of trusting it.
    """
    from core.file_manager import Run
    from workflow.compliance_sets import SET_BY_ID, selectable_set_ids, set_label
    from workflow.measurement_report import (generated_report_types,
                                             report_type_name)
    from workflow.run_compliance import run_limits, run_report_type

    rows: "list[dict]" = []
    multi: "list[str]" = []
    seen_types: set = set()
    seen_sets: set = set()
    for pd in sorted(dest.glob("Report-Limits-*")):
        for rd in sorted((pd / "runs").glob("run*"),
                         key=lambda p: int(p.name[3:] or 0)):
            run = Run.for_dir(rd)
            tid = run_report_type(run)
            lim = run_limits(run, {})
            label = set_label(lim.set_id, lim.label_en)
            if lim.edited:
                label += " (edited for this run)"
            name = f"{pd.name.replace('Report-Limits-', '')}/{rd.name}"
            rows.append({"run": name, "type": report_type_name(tid),
                         "set": label})
            seen_types.add(tid)
            seen_sets.add(lim.set_id)
            counts = generated_report_types(run)
            # A TYPE A RUN HOLDS ON DISK IS PRODUCED, whether or not it is the
            # run's standing choice (round 3B, F21): every run's profiling
            # sheet holds a Printing record, and this table said "no run
            # produces it" because it looked only at the verification type.
            seen_types.update(counts)
            if len(counts) > 1:
                multi.append(name + ": " + ", ".join(
                    f"{report_type_name(t)} ({n})"
                    for t, n in sorted(counts.items())))

    missing: "list[str]" = []
    for tid, tname, _blurb, built in REPORT_TYPE_MENU:
        if built and tid not in seen_types:
            missing.append(f"report type {tname}: no run produces it")
    for sid in selectable_set_ids({}):
        if sid not in seen_sets:
            missing.append(f"limit set {SET_BY_ID[sid].label}: no run uses it")
    return {"type_set_rows": rows, "type_set_missing": missing,
            "multi_type_runs": multi}


def readme(results: list, _lock_rows: "list[dict]", _cov: dict,
           dest: "Path | None" = None) -> str:
    from workflow.compliance_sets import ROW_BY_ID
    lines: list = []
    a = lines.append
    a("ChromIQ Measurement Report: the limit demo projects")
    a("=" * 52)
    a("")
    a("Built by scripts/make_report_limit_demos.py for issue #182.")
    a("")
    a("TWO WAYS IN, AND THE FIRST IS USUALLY THE RIGHT ONE")
    a("---------------------------------------------------")
    a("")
    # THE APP'S OWN LABELS, not a paraphrase (round 3B, F28): the window is
    # "ChromIQ Preferences", the tab "Paths", the field "Default output folder".
    a("1. DOWNLOAD this folder as the zip attached to the beta release, unzip")
    a("   it anywhere, and point ChromIQ at it: open ChromIQ Preferences,")
    a("   Paths, and set 'Default output folder' to the unzipped folder.")
    # COUNTED ON THE DISK (K29): the release package puts the evenness and
    # notes projects beside these, and "all fifteen" beside seventeen folders
    # is a README contradicting its own download.
    _n = sum(1 for p in dest.iterdir() if (p / "project.json").is_file()) \
        if dest is not None and dest.is_dir() else len(PROJECTS)
    a(f"   All {_WORDS.get(_n, _n)} "
      f"projects then appear in the project")
    a("   list. Nothing inside a project names a folder on the machine that")
    a("   built it, so it opens the same wherever it lands.")
    a("")
    a("2. GENERATE it yourself, if you want the data to match a ChromIQ newer")
    a("   than the archive:")
    a("")
    a("       .venv/bin/python scripts/make_report_limit_demos.py")
    a("")
    a("   ArgyllCMS 3.5.0 in /Applications/Argyll is required. The whole set")
    a("   builds in well under a minute and is deterministic: the same command")
    a("   on the same Argyll gives the same numbers, every time, and this file")
    a("   comes out byte for byte the same. THAT IS WHY NO BUILD TIME IS")
    a("   PRINTED HERE. Two were, one a round number and one measured to a")
    a("   tenth of a second, and both were written when the package was")
    a("   smaller; a measured time would also make every rebuild differ from")
    a("   the archive somebody is comparing against.")
    a("")
    a("   Prefer the download when you just want to look at reports. Prefer")
    a("   generating when the report code has moved on and you want the saved")
    a("   verdicts rebuilt against it.")
    a("")
    a("WHAT IS IN HERE")
    a("---------------")
    a("")
    a(f"{str(_WORDS.get(len(PROJECTS), len(PROJECTS))).capitalize()} projects. Each "
      f"project holds several profile runs, and each")
    a("profile run holds its own chart, its own profile, and its dated")
    a("verifications.")
    a("")
    from workflow.measurement_report import report_type_name
    for name, plans in PROJECTS:
        a(f"  {name}")
        for i, plan in enumerate(plans, start=1):
            a(f"      run{i}  {plan.description}")
            a(f"            report type {report_type_name(plan.report_type)}")
            # THE COUNT IS READ OFF THE SHEET, NOT OFF THE REQUEST.
            # `ChartRecipe.label` is typed beside the number asked for, and
            # printtarg PADS: two of the eleven runs ship charts of 168 and 405
            # patches under labels saying 156 and 400. The other nine agree,
            # which is exactly why a typed label survived this long.
            a(f"            profile chart "
              f"{_chart_label(dest, name, f'run{i}', plan.profile_chart)}, "
              f"verification chart "
              f"{_chart_label(dest, name, f'run{i}', plan.verify_chart, True)}")
        a("")
    a("WHICH RUNS ARE LOCKED, AND WHY")
    a("------------------------------")
    a("")
    a("A run's limit set is fixed, and the report window stops offering it,")
    a("once two conditions are both true: the set has been copied onto the run")
    a("by a first verification measurement, and the run has at least TWO dated")
    a("verifications. One measurement is not yet a history, so at that point")
    a("the set can still be chosen. The lock can also be lifted by hand, once")
    a("ChromIQ Preferences, Reports, 'Allow editing of thresholds after the")
    a("first verification measurement' is ticked; on a fresh install it is")
    a("not, and the report window's 'Unlock this run's limits' is greyed.")
    a("")
    a("Every line below was read back from the built projects with the app's")
    a("own is_locked(), not copied from the plan that asked for it.")
    a("")
    a(f"  {'run':<34}{'dates':>6}  {'lifted':<7}{'locked':<7}")
    for row in _lock_rows:
        a(f"  {row['run']:<34}{row['dates']:>6}  "
          f"{'yes' if row['lifted'] else 'no':<7}"
          f"{'YES' if row['locked'] else 'no':<7}")
    a("")
    a("All three states are present on purpose, and the index further down")
    a("this file names a run for each of them, from the same measured rows as")
    a("the table above. THEY ARE NOT LISTED AGAIN HERE. The last version of")
    a("this file answered the question twice, once from a generated line and")
    a("once from a hand-written one, and the hand-written half named a run")
    a("with three dated verifications as the example of a run with two.")
    a("")
    a("HOW THE MEASUREMENTS WERE MADE")
    a("------------------------------")
    a("")
    a("Every chart is a real ArgyllCMS chart and every profile is a real")
    a("colprof profile built from a real fakeread measurement. Every dated")
    a("verification begins as a real fakeread of that run's verification chart")
    a("through that run's own profile.")
    a("")
    a("A designed drift is then applied on top, patch by patch. Each patch")
    a("keeps the direction of the error fakeread produced through the real")
    a("profile; only the size of that error is scaled, so that the chart's")
    a("statistics land exactly where the date's design says. That is what lets")
    a("one row cross its limit on one date while the others stay put, and it")
    a("is why the table below matches. Random noise cannot do that: it moves")
    a("every statistic at once.")
    a("")
    a("THE PAPER. Every simulated printer prints on the same paper, Lab")
    a(f"{PAPER_LAB[0]:.1f} / {PAPER_LAB[1]:.1f} / {PAPER_LAB[2]:.1f} under D50: "
      f"a neutral, slightly warm")
    a("matte, a little below L* 100 as real paper is. Each run's profiling")
    a("sheet is read RELATIVE to the white (fakeread -I r) and then scaled onto")
    a("that paper, and its profile is a printer (OUTPUT) profile, so the paper")
    a("travels into every dated verification read through it. Packages built")
    a("before beta 36 read through ArgyllCMS's sRGB display profile in its")
    a("absolute mode: every sheet's white was the D65 white, which is a light")
    a("BLUE paper (b* about -19) when ChromIQ reads it under D50.")
    a("")
    a("THE PAPER WHITE EACH REPORT RECORDS is the lightest patch on the")
    a("sheet. On a chart that has a paper patch, that patch is the one it")
    a("takes on every date: the build refuses a date on which it is not.")
    a("")
    for _line in paper_white_lines(results):
        for _i, chunk in enumerate(_wrap(_line, 68)):
            a(("  " if _i == 0 else "      ") + chunk)
    a("")
    a("THE SAVED REPORTS, AND HOW THE WINDOW NAMES THEM")
    a("-----------------------------------------------")
    a("")
    a("Every measurement in this package carries the report ChromIQ saves")
    a("automatically after a measurement, written by the same steps:")
    a("")
    a("  the run's own PROFILING measurement (runs/runN/reports/)")
    a("      a Printing record, the only report a profiling measurement has")
    a("  every DATED VERIFICATION (runs/runN/verifications/<date>/reports/)")
    a("      the run's own report type, or Full colour check when the run")
    a("      never chose one; never a Printing record")
    a("")
    a("Each file carries a document block, as every report ChromIQ writes")
    a("does, with both tick boxes off and the date flag \"One date\", so the")
    a("'Report shown' list names it")
    a("")
    a("  <created date and time> · <report type> · <limit set> · One date")
    a("")
    a("and selecting it ticks exactly the measurement it is about. A report")
    a("you generate yourself from several ticked measurements is named")
    a("\"Multiple dates\", or \"All dates\" when none is left out, and an")
    a("Update adds \"updated <date> <time>\" to its name.")
    a("")
    a("WHICH ROWS ARE COVERED, AND WHICH CANNOT BE")
    a("-------------------------------------------")
    a("")
    a(f"A report has {len(ROW_BY_ID)} rows and most of them cannot be filled "
      f"in from an")
    a("ordinary printed sheet at all: they belong to a standard's own control")
    a("strip, or ask about fading, gloss or repeat measurements. The rows that")
    a("matter here are the ones a ChromIQ verification sheet puts a NUMBER on,")
    a("and of those, the ones some limit set actually judges.")
    a("")
    a(f"  rows a ChromIQ verification sheet computes : {len(_cov['with_value'])}")
    a(f"  of those, judged by a limit somewhere      : {len(_cov['judged'])}")
    a(f"  of those, crossed by at least one date     : {len(_cov['crossed'])}")
    a("")
    if _cov["uncrossed"]:
        a("NOT CROSSED BY ANY DATE, so a clean verdict on these proves nothing:")
        for rid in _cov["uncrossed"]:
            a(f"  {ROW_TITLES.get(rid, rid)}")
    else:
        a("Every row that can be judged is crossed by at least one date, and")
        a("comes back inside its limit on another. Nothing here is untested.")
    a("")
    a("One of them needed a run of its own. Neither ChromIQ default, ChromIQ")
    a("tight nor Quick check judges the 30 to 70 % tone ramps as they ship, so")
    a("under those three columns that row prints a number nothing can cross;")
    a("Isolated-Rows/run5 gives it a limit in the run's own edited column,")
    a("which is the only way a user of those columns can have it judged. The")
    a("two Custom columns DO put a limit on it, and Custom-Columns/run2")
    a("crosses it there.")
    a("")
    a("EVERY JUDGEABLE ROW AGAINST EVERY LIMIT SET")
    a("-------------------------------------------")
    a("")
    a("Knut, 2026-09-18: \"those eleven can also be defined for all the Judge")
    a("Against limit sets, so the demo data must verify that all thresholds")
    a("can trigger correctly for every judged against limit set, not just test")
    a("all the thresholds on one of the sets.\"")
    a("")
    a("A cell is complete only when this package holds a dated verification")
    a("judged against that set where the row is OVER its limit AND one where")
    a("the row was judged and is inside it. A row that only ever crosses says")
    a("nothing about whether the threshold ever releases.")
    a("")
    _cells = _cov.get("matrix_cells", [])
    _done = sum(1 for c in _cells if c["complete"])
    a(f"  {_done} of {len(_cells)} judged cells are complete, over "
      f"{len(_cov.get('matrix_sets', []))} selectable limit sets.")
    a("")
    a("THE TWO READ-ONLY ISO COLUMNS ARE NOT IN THIS TABLE AND CANNOT BE. The")
    a("tolerance values of ISO 12647-7:2016 and ISO 12647-8:2021 are not in")
    a("ChromIQ, so every cell of both columns reads '?', neither column has a")
    a("limit-bearing row, and, unless you have pointed ChromIQ at your own")
    a("figures file, the report window does not offer either. No measurement")
    a("can make it offer them.")
    a("")
    _by_set: dict = {}
    for c in _cells:
        _by_set.setdefault(c["set"], []).append(c)
    from workflow.compliance_sets import SET_BY_ID as _SBI
    for sid in _cov.get("matrix_sets", []):
        _rows = _by_set.get(sid, [])
        a(f"{_SBI[sid].label}  ({len(_rows)} judged rows)")
        for c in sorted(_rows, key=lambda x: x["row"]):
            _mark = "  " if c["complete"] else "!!"
            # THE WHOLE NAME (round 3B, F2): a `[:60]` here printed
            # "largest lightness differen" five times.
            a(f"  {_mark} {ROW_TITLES.get(c['row'], c['row'])}")
            a(f"        over   {c['over'] or '(never)'}")
            a(f"        inside {c['inside'] or '(never)'}")
        a("")
    from workflow.compliance_sets import (effective_limits as _eff,
                                          limit_bearing as _lb)
    _n_chromiq = len(_lb(_eff("chromiq_default", {})))
    _n_custom = len(_lb(_eff("custom_iso_12647_7", {})))
    # THE NUMBER IN THE HEADING IS THE ONE THE PARAGRAPH UNDER IT COMPUTES
    # (round 3B, F1): it was typed as SIXTEEN above a paragraph saying 18.
    _head = (f"HOW THE THREE CHROMIQ COLUMNS COME TO JUDGE ALL {_n_custom} "
             f"ROWS")
    a(_head)
    a("-" * len(_head))
    a("")
    a("As shipped, ChromIQ default, ChromIQ tight and Quick check put a number")
    a(f"on {_n_chromiq} of the {_n_custom} judgeable rows: the five")
    a("colour-difference rows, the grey pair, and ChromIQ's own two")
    a("repeatability rows. The two Custom columns put one on all of them.")
    a("")
    a("The runs of Report-Limits-Every-Limit-Set that are bound to a ChromIQ")
    a(f"column carry the other {_n_custom - _n_chromiq} in the RUN'S OWN COPY "
      f"of the limits, in")
    a("runs/runN/meta.json, which is exactly the state a user is in after")
    a("typing them into the Report limits window. Nothing was invented for it:")
    a("effective_limits() accepts an override on any row whose status is not")
    a("'unmeasurable', and the numbers used are ChromIQ default's own")
    a("placeholders scaled by the ratio each set already uses on the five rows")
    a("it does ship (tight is half of default, Quick check double it). No")
    a("standard's published tolerance is involved in any of them.")
    a("")
    a("If you pick a different set in the 'Judged against' pulldown on one of")
    a("those runs, ChromIQ re-binds the run to that set's own numbers and the")
    a(f"{_n_custom - _n_chromiq} typed-in limits are gone. That is correct "
      f"behaviour and not a")
    a("fault in the package; regenerate it, or unzip a fresh copy, to get them")
    a("back.")
    a("")
    a("WHICH DATE CROSSES WHICH LIMIT")
    a("------------------------------")
    a("")
    a("'Crossed' means the report gave that row FAIL: it is over its limit.")
    a("No row reads COND any more (Knut retired it as a row word on")
    a("2026-09-21), and none of ChromIQ's own sets marks a row 'recommended'.")
    a("Intended is what the design asked for; actual is what the report read")
    a("back after it was built.")
    a("")
    cur = None
    for r in results:
        head = f"{r['project']} / {r['run']}"
        if head != cur:
            cur = head
            a("")
            a(head)
            a(f"  judged against: {r['set']}")
            a(f"  report type:    {report_type_name(r['type'])}")
        a("")
        a(f"  {r['date']}   {r['title']}")
        a(f"      {r['story']}")
        if r["intended"]:
            a("      intended to cross: "
              + ", ".join(ROW_TITLES.get(x, x) for x in r["intended"]))
        else:
            a("      intended to cross: nothing")
        if r["actual"]:
            a("      actually crossed:  "
              + ", ".join(ROW_TITLES.get(x, x) for x in r["actual"]))
        else:
            a("      actually crossed:  nothing")
        a(f"      the report's word for the column: {r['verdict']}")
        # THE SAME MEASUREMENT IN THE DOCUMENT EVERYBODY KNOWS. Printed only
        # where it can differ, and read back from the report rather than
        # described, because a Grey and tone check hides the colour rows and a
        # Printing record withholds every word: without this line a reader of
        # either cannot tell whether the sheet was any good.
        if r.get("as_full"):
            f_ = r["as_full"]
            crossed = (", ".join(ROW_TITLES.get(x, x) for x in f_["crossed"])
                       or "nothing")
            a(f"      the same numbers on Full colour check: {f_['verdict']}, "
              f"crossing {crossed}")
    a("")
    a("")
    a("WHAT A CLEAN VERDICT HERE DOES NOT PROVE")
    a("----------------------------------------")
    a("")
    # REWRITTEN FROM THE SETS (round 3B, F24). It named seven rows under a
    # count of nine, promised a list of rows "no shipped set puts a number on"
    # and printed none (the two Custom columns number every one), and ended
    # "the 18 judged rows passed, counting the row an edited column adds".
    from workflow.compliance_sets import (SET_BY_ID as _SBI2,
                                          effective_limits as _eff2,
                                          limit_bearing as _lb2)
    _ship = _cov.get("shipped_judged") or []
    _n_ship = _WORDS.get(len(_ship), len(_ship))
    _n_cust = len(_lb2(_eff2("custom_iso_12647_7", {})))
    _chromiq_labels = ", ".join(_SBI2[s].label.split(" (")[0]
                                for s in ("chromiq_default", "chromiq_tight",
                                          "chromiq_quick"))
    for chunk in _wrap(
            f"{str(_n_ship).capitalize()} rows can be judged by "
            f"{_chromiq_labels} as they ship: the five all-patch colour "
            f"differences, the two grey-balance rows and ChromIQ's two "
            f"repeatability rows. The two Custom columns judge all "
            f"{_n_cust}. A green column means the rows its own set judges "
            f"passed; it does not mean the rest were checked.", 70):
        a(chunk)
    _never = [row.label for rid, row in ROW_BY_ID.items()
              if not any(rid in _lb2(_eff2(sid, {})) for sid in _selectable())]
    if _never:
        a("")
        a("These rows carry a number in no limit set ChromIQ offers, so they")
        a("never carry a verdict and no data can make them cross:")
        for _lbl in _never:
            a(f"  {_lbl}")
    a("")
    _forced = _forced_pairs()
    _n = _WORDS.get(len(_forced), str(len(_forced)))
    a(f"{_n.upper()} ROWS CANNOT CROSS ALONE UNDER A STOCK COLUMN, AND A")
    a("FURTHER ONE DEPENDS ON WHICH WAY THE CAST GOES")
    a("-" * 68)
    a("")
    a("THE COUNT HAS BEEN WRONG TWICE, in both directions, AND THEN THE")
    a("HEADING WAS WRONG A THIRD TIME while the list under it was right,")
    a("because the list was computed and the number above it was typed. Both")
    a("come from the same place now. A row cannot cross alone when another row")
    a("is forced over its own limit at the same moment.")
    a("")
    a(f"{_n.capitalize()} of them by arithmetic, and the reason is that the")
    a("three averages are ordered: 'Best 95 % of patches, average' is always")
    a("less than or equal to 'All patches, average', which is always less than")
    a("or equal to 'Worst 5 % of patches, average'. Every shipped set gives")
    a("those three the SAME number, so:")
    a("")
    for _rid, _why in _forced:
        a(f"  {ROW_TITLES.get(_rid, _rid)}")
        a(f"      cannot cross without {_why}")
    a("")
    a("The rest of the numeric rows can cross by themselves, because nothing")
    a("above them in an ordering has a limit small enough to be dragged over")
    a("with them.")
    a("")
    a("The further one is the grey-balance average, and it depends on WHICH")
    a("WAY the cast goes, which the first version of this note did not say.")
    a("")
    a("The grey rows are measured in chroma difference and the others in")
    a("colour difference, and near a neutral those are not the same size. But")
    a("the ratio is not one number. Measured with the app's own CIEDE2000, at")
    a("every lightness:")
    a("")
    a("    chroma 1.8   ->   2.545 along a*,   1.730 along b*")
    a("    chroma 3.6   ->   4.815 along a*,   3.330 along b*")
    a("")
    a("The rescaling is CIEDE2000's own, and it is a* that it stretches. So a")
    a("cast toward red or green of 1.8 does put every grey patch over 2.0,")
    a("while the same size of cast toward yellow or blue leaves them at 1.73,")
    a("under it. THE GREY AVERAGE CAN THEREFORE CROSS ALONE, on a b* cast,")
    a("which is why it is not in the computed list above.")
    a("")
    a("These projects build an a* cast, which is why the pairing holds in")
    a("them: Threshold-Series 2026-04-13 shows it, with two rows crossing.")
    a("Isolated-Rows/run4 shows the grey average crossing alone, and it gets")
    a("there with an edited column rather than by choosing the direction.")
    a("")
    _edited = [f"run{i}" for i, _p in enumerate(
        dict(PROJECTS)["Report-Limits-Isolated-Rows"], start=1) if _p.edited_limits]
    a("Report-Limits-Isolated-Rows exists for the rows that cannot. "
      + ", ".join(_edited[:-1]) + " and " + _edited[-1] + " each")
    a("carry their own edited limit column that relaxes the companion rows, so")
    a("the row of interest crosses on its own and can be looked at alone.")
    a("")
    a("THE REPORT TYPES, AND WHY ONLY FOUR OF THE SIX ARE IN HERE")
    a("---------------------------------------------------------")
    a("")
    a("THIS SECTION USED TO SAY REPORT TYPES WERE NOT IN THE PACKAGE AND")
    a("COULD NOT BE: \"a design at the moment, not a feature: nothing in this")
    a("ChromIQ can select one\". That was true when it was written and stopped")
    a("being true in v4.3.0-beta.4, which shipped the pulldown. It is named")
    a("here rather than quietly deleted, because anybody holding an older copy")
    a("of this file is being told something false by it.")
    a("")
    a("The pulldown offers six documents. FOUR CAN BE PRODUCED. The Printing")
    a("record is the report of every run's own profiling measurement; the")
    a("other three are a verification's, and each has a run of its own in")
    a("Report-Limits-Report-Types:")
    a("")
    for tid, name, blurb, built in REPORT_TYPE_MENU:
        if built:
            a(f"  {name}")
            a(f"      {blurb}")
    a("")
    a("TWO CANNOT, and no measurement can change that. These are the two:")
    a("")
    for tid, name, blurb, built in REPORT_TYPE_MENU:
        if not built:
            a(f"  {name}")
            a(f"      {blurb}")
    a("")
    a("The figures they judge against are published in standards ChromIQ has")
    a("no permission to include, so ChromIQ cannot write either document. They")
    a("are SHOWN in the pulldown and refused there rather than hidden, under a")
    a("heading that says what they need, and the entry carries the reason:")
    a("")
    a(f"  \"{REPORT_TYPE_MENU_HEADING}\"")
    a(f"  \"{not_built_line()}\"")
    a("")
    a("So what this package can demonstrate about those two is that they are")
    a("offered, that they are refused, and that they say why. There is nothing")
    a("else to demonstrate: a demo cannot exercise a document the app cannot")
    a("produce, and building one would need a tolerance value out of a")
    a("standard that may not be shipped. Nothing in this generator holds one.")
    a("")
    a("WHICH RUN COVERS WHICH TYPE AND WHICH LIMIT SET")
    a("----------------------------------------------")
    a("")
    a("Read off the built runs, not off the plan that asked for them. The TYPE")
    a("column is the document the run is set to produce when you open it; the")
    a("SET column is what its numbers are judged against. Every run of")
    a("Report-Limits-Report-Types has its limits left open, so both pulldowns")
    a("stay live and any type can be tried against any set on the same")
    a("measurement.")
    a("")
    a(f"  {'run':<36}{'report type':<30}limit set")
    for row in _cov.get("type_set_rows", []):
        a(f"  {row['run']:<36}{row['type']:<30}{row['set']}")
    a("")
    missing = _cov.get("type_set_missing") or []
    if missing:
        a("NOT COVERED BY ANY RUN:")
        for what in missing:
            a(f"  {what}")
    else:
        # A TYPE IS COVERED WHEN A RUN HOLDS ONE (F21), and the Printing
        # record is held by every run's profiling sheet while being no run's
        # standing choice, so the sentence says the two things apart.
        a("Every document ChromIQ can produce is held by at least one run, and")
        a("every limit set it offers is the standing choice of at least one run")
        a("above. The Printing record is every run's PROFILING report and no")
        a("run's standing choice, because a verification may not have one.")
    a("")
    _cids = _cov.get("custom_ids") or []
    if _cids:
        from workflow.compliance_sets import SET_BY_ID as _SBI
        a("THE TWO CUSTOM COLUMNS, AND TWO THINGS THEIR VERDICTS DO NOT SAY")
        a("---------------------------------------------------------------")
        a("")
        a("Report-Limits-Custom-Columns binds a run to each of them. Their")
        a("numbers are ChromIQ's own, not either standard's published")
        a("tolerances, and this package does not touch them: they are")
        a("placeholders under a permission condition and a test in ChromIQ")
        a("pins where every one of them came from.")
        a("")
        a("FIRST: a column named after a standard cannot check everything it")
        a("puts a limit on, and not because anything is wrong with the print.")
        a("")
        _tot = _cov.get("custom_total", 0)
        _fill = _cov.get("custom_fillable", 0)
        # WHERE THE OTHER ROWS ARE JUDGED, read off the results (round 3B,
        # F22): this said "N-A on every date" while the same README showed
        # them crossing on the From Profile Gamut charts under both columns.
        _gamut_custom = sorted(
            {f"{r['project'].replace('Report-Limits-', '')}/{r['run']}"
             for r in results
             if str(r.get("set_id", "")).startswith("custom_")
             and r.get("chart") == "gamut"},
            key=lambda x: (x.split("/")[0], int(x.split("run")[-1] or 0)))
        _where = (", ".join(_gamut_custom[:-1]) + " and " + _gamut_custom[-1]
                  if len(_gamut_custom) > 1 else
                  (_gamut_custom[0] if _gamut_custom else ""))
        a(f"  Each column puts a limit on {_tot} rows. On an ordinary")
        a(f"  verification chart {_fill} of them can be filled; the other")
        a(f"  {_tot - _fill} need the aim values a From Profile Gamut chart")
        a("  carries, so they are N-A on both runs of this project:")
        for _lbl in _cov.get("custom_unfillable", []):
            a(f"      {_lbl}")
        if _where:
            for chunk in _wrap(f"They are judged, over and inside, under the "
                               f"same columns on a From Profile Gamut chart: "
                               f"{_where}.", 64):
                a(f"  {chunk}")
        a("")
        a("  A row that could not be checked does not count against the")
        a("  column, so the word moves FAIL to PASS across these runs while")
        a("  those rows stay N-A. What qualifies that PASS is the NOTE beside")
        a("  it: the figures are ChromIQ's placeholders under a standard's")
        a("  name, applied to the chart YOU printed, so a result inside them")
        a("  says nothing about the standard.")
        a("")
        if _cov.get("custom_same_numbers"):
            a("SECOND: on every row that carries a NUMBER, the two columns are")
            a("identical to each other.")
            a("")
            a("  Both start from ChromIQ's own figures, and neither ISO data")
            a("  file supplies anything, so nothing separates their numbers")
            a("  today. The two runs therefore prove that each column can be a")
            a("  run's set and can judge a measurement. They prove NO")
            a("  difference in strictness between the two, because there is")
            a("  none to prove; a reader who reads one verdict against the")
            a("  other and concludes something about the two standards would")
            a("  be reading a difference that is not there.")
            a("")
            a("  A licence holder who points ChromIQ at their own figures file")
            a("  gets different numbers, and then these same two runs start")
            a("  saying different things without being rebuilt.")
            _shape = _cov.get("custom_shape_differs") or []
            if _shape:
                a("")
                a("  The columns DO differ in shape: these rows are marked as")
                a("  asked for by one standard and not the other, and none of")
                a("  them carries a number in either column, so none can change")
                a("  a verdict.")
                for _lbl in _shape:
                    a(f"      {_lbl}")
        else:
            a("SECOND: the two columns hold DIFFERENT numbers from each other,")
            a("so the two runs can be read against one another.")
            a("")
            a("  Neither column's numbers are a standard's. They start from")
            a("  limits researched from industry practice, given per column,")
            a("  and from ChromIQ's own numbers on the rows that research does")
            a("  not cover. The rows the two columns put DIFFERENT numbers on")
            a("  are the ones a reader can compare:")
            for _lbl in _cov.get("custom_number_differs") or []:
                a(f"      {_lbl}")
            a("")
            a("  A licence holder who points ChromIQ at their own figures file")
            a("  gets different numbers again, and then these same two runs")
            a("  start saying different things without being rebuilt.")
        a("")
    sys.path.insert(0, str(_HERE))
    import make_verification_preset_demos as _PRESETS
    a("THE DEMO CHART PRESETS")
    a("----------------------")
    a("")
    a("Knut, 2026-09-19: \"create one preset for each requirement of a metric,")
    a("where each threshold is on the border of the threshold, but not")
    a("complying with that specific requirement. And then one preset for each")
    a("requirement of a metric, where each threshold is on the border of the")
    a("threshold, but complying with that specific requirement\".")
    a("")
    a("They are in the folder beside this file:")
    a("")
    a(f"  {_PRESETS.FOLDER}")
    a("")
    a(f"{len(_PRESETS.REQUIREMENTS)} requirements, with a FAIL preset one "
      f"notch outside each line and a")
    a("PASS preset exactly on it, plus a control that answers everything and")
    a(f"four more: {len(_PRESETS.DEMOS)} presets in all. Copy that folder's "
      f"CONTENTS into your")
    a("own Create Chart preset folder and restart ChromIQ:")
    a("")
    a("  macOS    ~/Library/Preferences/ChromIQ/presets/Create Chart")
    a("  Windows  %APPDATA%\\ChromIQ\\presets\\Create Chart")
    a("")
    a("That folder's own README gives each requirement, the comparison as")
    a("ChromIQ's source writes it, the file the line was read from, and which")
    a("reasons no patch set can provoke at all.")
    a("")
    a("EVERY METRIC LIMIT, AND WHETHER THIS PACKAGE TESTS IT")
    a("-----------------------------------------------------")
    a("")
    a("Knut, 2026-09-11: \"make sure the metrics have a value that can be")
    a("tested against, and that all metrics limits are verified with the")
    a("ChromIQ-Report-Limit-Demos package\".")
    a("")
    a("One line per row of the limits table, read out of ChromIQ rather than")
    a("typed here. TESTED means this package puts a limit on the row AND has a")
    a("measurement that fills it, so a verdict on it means something. The")
    a("crossing and the recovery are the two dates that prove the limit is")
    a("live in both directions.")
    a("")
    _rows = _cov.get("metric_rows", [])
    _tested = [r for r in _rows if r["tested"]]
    a(f"  {len(_tested)} of {len(_rows)} rows are tested. "
      f"The other {len(_rows) - len(_tested)} cannot be, and the")
    a("  reason is a property of the row, not of this package. NOTHING HAS")
    a("  BEEN INVENTED TO FILL ONE: a demo that pretended to have read a")
    a("  gloss meter or a fading rig would make this package lie about what")
    a("  ChromIQ measures.")
    a("")
    a("TESTED:")
    for r in _rows:
        if not r["tested"]:
            continue
        a(f"  {r['label']}")
        a("      limit from: "
          + ("a shipped limit set" if r["shipped"]
             else "a run's own edited column (no shipped set judges it)"))
        a(f"      crosses at: "
          + (r["crossed_at"] or "nowhere, so a clean verdict on it proves nothing"))
        if r["recovered_at"]:
            a(f"      back inside on: {r['recovered_at']}")
        elif r["crossed_at"]:
            a("      NEVER COMES BACK INSIDE, so only half the limit is proved")
    a("")
    a("NOT TESTED, AND WHY:")
    a("")
    _by_why: dict = {}
    for r in _rows:
        if r["tested"]:
            continue
        _by_why.setdefault(r["why_not"] or "NOBODY HAS SAID WHY", []).append(r["label"])
    for _why, _labels in _by_why.items():
        for _lbl in _labels:
            _r = next(x for x in _rows if x["label"] == _lbl)
            # A LIMIT ON A ROW NOTHING CAN FILL IS WORTH NAMING. The two Custom
            # columns put a number on three rows that need a reference
            # measurement ChromIQ cannot read, so those rows carry a limit and
            # are never checked against it. That is exactly the shape the
            # Overall verdict's "nothing was checked" clause exists for, and a
            # reader comparing the limits window against the report will see
            # the number and wonder why no verdict follows it.
            a(f"  {_lbl}"
              + ("   (a limit set puts a number on it, and nothing in this "
                 "package can fill it)" if _r["limited_here"] else ""))
        for chunk in _wrap(_why, 66):
            a(f"      {chunk}")
        a("")
    a("IS EACH METRIC SUPPORTED BY THE CHART, AND CAN THE REPORT SAY SO")
    a("----------------------------------------------------------------")
    a("")
    a("The table above answers \"does this package test the row anywhere\".")
    a("This one answers the question the reader actually has in front of a")
    a("sheet: does THIS chart supply the row, and when it cannot, does the")
    a("report say so rather than go quiet.")
    a("")
    _srows = _cov.get("support_rows", [])
    _sizes = _cov.get("verify_chart_sizes", [])
    a(f"  verification charts in this package: "
      f"{', '.join(str(s) for s in _sizes)} patches")
    a(f"  saved reports read for this table  : {_cov.get('support_reports', 0)}")
    a("")
    for _r in _srows:
        a(f"  {_r['label']}")
        a(f"      a value on {_r['value']} report(s)"
          + (f", from charts of {', '.join(str(x) for x in _r['value_on'])} "
             f"patches" if _r["value_on"] else ""))
        if _r["na"]:
            a(f"      N-A on {_r['na']} report(s)"
              + (f", from charts of {', '.join(str(x) for x in _r['na_on'])} "
                 f"patches" if _r["na_on"] else "")
              + (f"; the report gives the reason as "
                 f"{', '.join(_r['reasons'])}" if _r["reasons"] else ""))
        elif _r["cannot_unsupport"]:
            a("      never N-A, and no chart can make it so:")
            for chunk in _wrap(_r["cannot_unsupport"], 62):
                a(f"          {chunk}")
        else:
            a("      NEVER SEEN N-A, and this package should have shown it")
        a("")
    a("EVERY FAULT MESSAGE AND BORDER CONDITION, AND WHERE TO SEE IT")
    a("-------------------------------------------------------------")
    a("")
    a("Knut, 2026-09-11: the demo data must show all parts of the report,")
    a("\"including fault messages and border conditions\".")
    a("")
    a("THE LIST IS READ OUT OF THE APP, not typed here: every sentence the")
    a("Overall cell can print and every reason a row can give for having no")
    a("number. A message added to ChromIQ tomorrow turns up in this table as")
    a("one the package does not reach, which is the right way round.")
    a("")
    a("The sentence under the verdict, one line per sentence ChromIQ has:")
    a("")
    for e in _cov.get("sentences", []):
        a(f"  {e['key']}")
        a(f"      {' '.join(e['text'].split())[:120]}")
        if e["at"]:
            a(f"      seen at: {e['at']}")
        elif e["why_not"]:
            a("      NOT REACHED BY ANY PROJECT HERE:")
            for chunk in _wrap(e["why_not"], 62):
                a(f"        {chunk}")
        else:
            a("      NOT REACHED, AND NOBODY HAS SAID WHY. Build data that")
            a("        reaches it, or put the reason in UNREACHABLE_BY_DATA.")
    a("")
    a("The reason a row gives when it has no number:")
    a("")
    for e in _cov.get("reasons", []):
        if e["at"]:
            a(f"  {e['code']:<24} seen at: {e['at']}")
        elif e["why_not"]:
            a(f"  {e['code']:<24} NOT REACHED BY ANY PROJECT HERE")
            for chunk in _wrap(e["why_not"], 62):
                a(f"      {chunk}")
        else:
            a(f"  {e['code']:<24} NOT REACHED, AND NOBODY HAS SAID WHY")
    a("")
    a("Two more states have no message of their own and are reached by where")
    a("a measurement LIVES rather than by what it contains, so they are named")
    a("here instead of in the tables above:")
    a("")
    a("  the run's own profiling measurement, which is never graded: open the")
    a("      .ti3 sitting directly in any runs/runN/ folder. It carries a")
    a("      SAVED report of its own, a Printing record, like every other")
    a("      measurement in here, so its column shows what was recorded")
    a("      rather than something worked out when you open it")
    a("  a sheet printed raw and read as a drift check, whose column says")
    a("      'drift' and carries no verdict at all: Border-Conditions, run3")
    a("")
    _multi = _cov.get("multi_type_runs", []) or []
    _all_runs = len(_cov.get("type_set_rows", []) or [])
    if _multi and len(_multi) == _all_runs:
        _rich = _richest_multi_type_run(_multi)
        _nrich = next(_multi_type_count(ln) for ln in _multi
                      if ln.startswith(_rich + ": "))
        a("Every run holds saved reports of more than one type: its profiling")
        a("measurement's Printing record and its verifications' type. "
          f"{_rich}")
        a(f"holds {_WORDS.get(_nrich, _nrich)}, because a user may want more "
          f"than one document from one")
        a("measurement. The window counts them off the disk:")
    else:
        a("These runs hold saved reports of more than one type, because a")
        a("user may want more than one document from one measurement, and the")
        a("window counts them off the disk:")
    a("")
    for line in _cov.get("multi_type_runs", []) or ["  (none)"]:
        a(f"  {line}")
    a("")
    a("FOR THE NEXT PERSON WHO NEEDS A REPORT WITH DATED VERIFICATIONS")
    a("--------------------------------------------------------------")
    a("")
    a("Open one of these rather than inventing another set. Which one:")
    a("")
    a("  a row crossing and then recovering ......... Threshold-Series, run1")
    a("  many dated verifications on one run ........ Threshold-Series, run1")
    a("  a second limit set on the same kind of sheet  Threshold-Series, run2")
    for _what, _where in _lock_index(_lock_rows):
        a(f"  {(_what + ' '):.<44} {_where}")
    a("  a run with its own edited limit column ..... Isolated-Rows, runs 1, 2, 4, 5")
    a("  one measurement judged three ways .......... Set-Compare, all runs")
    a("  the grey AVERAGE crossing on its own ...... Isolated-Rows, run4")
    a("  a row no shipped set judges at all ......... Isolated-Rows, run5")
    for _what, _where in _type_index(_cov.get("type_set_rows", []),
                                     _cov.get("multi_type_runs", [])):
        a(f"  {(_what + ' '):.<44} {_where}")
    a("")
    a("DO NOT edit these in place if the data is to stay reproducible. In")
    a("particular do not regenerate a verification chart: each dated check is")
    a("judged against its own chart/ snapshot, and replacing the shared chart")
    a("makes the two disagree. Copy the project folder, work on the copy, or")
    a("run the generator again, which is cheap and gives the same numbers.")
    a("")
    a("Page TIFFs of the charts are included for the profile and verification")
    a("charts themselves, but not inside the dated snapshots: no report reads")
    a("them and they are most of the weight. printtarg rebuilds them from the")
    a("chart's .ti1 at any time.")
    a("")
    if FOLDERS_MANIFEST:
        a("WHERE A REPORT LIVES (K23, Report-Limits-Report-Folders)")
        a("--------------------------------------------------------")
        a("")
        a("Knut, 2026-09-23: a report of ONE measurement lives in that")
        a("measurement's own reports/ folder; a report of several dates of one")
        a("profile run in runN/verifications/reports/; a report across profile")
        a("runs in the project's own reports/. Each date also keeps its own")
        a("verdict record in its own folder, which is never listed or counted.")
        a("Every date of this project holds a one-date report of each")
        a("verification type on its first date, each run's profiling sheet its")
        a("Printing record, and these, written by the generator with the app's")
        a("own functions:")
        a("")
        lines.extend(FOLDERS_MANIFEST)
        a("")
        a("Open run1 as a Verification and the list holds the one-date")
        a("reports, the all-dates and two-dates reports, the legacy one, and")
        a("the report across both runs; never the deleted one. Open run1 as")
        a("Profiling and it holds the Printing record and the report across")
        a("both profiling sheets.")
        a("")
        a("THE LIST IS GROUPED (K25). The report names stay; \"Report shown\"")
        a("gets headings from where the measurements in \"Included")
        a("measurements\" come from:")
        a("  one run (run1 as Verification): no headings;")
        a("  several runs of one project (run1 as Profiling, which lists every")
        a("  run's sheet; or run1 as Verification with a run2 date added):")
        a("  Run1, Run2, and \"Reports including multiple runs\";")
        a("  several projects (add a date of Report-Limits-Report-Folders-")
        a("  Second): each project's name, its runs under it, and \"Reports")
        a("  including multiple projects\" for the two reports that span")
        a("  both, which live in this pack's own reports/ folder.")
        a("")
    if CAL_MANIFEST:
        a("")
        a("RUN TYPE CALIBRATION (#182 beta 39, Knut 5794078008)")
        a("------------------------------------------------------")
        a("")
        a("With Preferences > Calibration options on and Run type")
        a("Calibration, the report window opens on the project's calibration")
        a("and lists its reports from cal/reports/, and a report across")
        a("projects from the pack's own reports/. Every type but the")
        a("Printing record. Names: Cal, Multiple cals, All cals.")
        a("")
        lines.extend(CAL_MANIFEST)
        a("")
        a("Add another project's cal/<name>-cal.ti3 with \"Add Profile's")
        a("Measurements...\" and \"Report shown\" is grouped by project.")
        a("")
    if RENAMED_MANIFEST:
        a("")
        a("A RENAMED PROJECT (#182 K29)")
        a("----------------------------")
        a("")
        lines.extend(RENAMED_MANIFEST)
        a("")
        a("Open Report-Limits-Renamed/run1 in the report window: the report")
        a("across both projects must be listed under \"Reports including")
        a("multiple projects\", although it names the project's old folder.")
        a("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
