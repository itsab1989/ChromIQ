"""Patches shorter than ArgyllCMS's minimum for the instrument (R6, 4.3.39).

ArgyllCMS's printtarg lays a strip instrument's patches out at a minimum
length along the strip, the direction the instrument moves
(``target/printtarg.c`` 3.5.0, the "Patch min length" of each instrument):

* i1Pro family, 4.5/5 mm aperture (printtarg ``-ii1``; the i1Pro, i1Pro 2 and
  i1Pro 3): **10 mm** ("absolute limit is 10", printtarg.c:2159);
* i1Pro 3 Plus, 8 mm aperture (``-i3p``): **16 mm**, printtarg's absolute
  limit with the zebra ruler, which the i1Pro 3 Plus always has
  (printtarg.c:2172: "Patch min length - total 20 mm (absolute limit 16 with
  zr)"); 20 mm is the length printtarg lays out, 16 mm the shortest it calls
  readable, as 10 mm is for the i1Pro family;
* ColorMunki (``-iCM``): **14 mm** (printtarg.c:2213).

The i1Pro and ColorMunki numbers are the ones ChromIQ's layout engine starts
from at patch scale 1.0 (``workflow/layout_engine/instruments.py``); the
i1Pro 3 Plus starts from 20 mm (a test keeps them in step). Measured on the
default auto-sized layouts of every paper (review of 4.3.39): the i1Pro 3
Plus comes out at 16.2 to 18.3 mm, never under 16.

ChromIQ's own ColorMunki "Extra-high density" (a ChromIQ extension, 13 mm
patches at native scale, its help says to watch the warning) gets its own
words: the mode is offered to fit more patches, it is shorter than
ArgyllCMS's usual length, and what to switch to if strips are refused. Shorter patches leave the instrument
fewer readings well inside each patch: a tester's 7.1 mm patches gave "Too
many patches" (2026-10-21) and 8 mm ones "Reading is inconsistent" next to a
near-black patch (jctay, forum 150236). ChromIQ WARNS, it never refuses or
greys anything: the person may have reasons (Basti: defaults safe, options
open). Table and spot instruments (the SpectroScan, the i1iO and i1iSis tables, the CR30) have
rules of their own and are not judged here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: printtarg's minimum patch length along the strip, mm, by the layout
#: engine's instrument key.
ARGYLL_MIN_PATCH_LENGTH_MM = {"i1": 10.0, "p3": 16.0, "CM": 14.0}

_MM_PER_INCH = 25.4

#: CALM ABOVE 8.0 mm WHEN CHROMIQ CHOSE THE SIZE (combined review of 4.3.39,
#: MAJOR-2). ChromIQ's own automatic layouts of the i1Pro family come out at
#: 8.1 to 9.5 mm (small papers at any count, A4 / Letter at about 420 patches
#: or more; the default Guided A4 chart: 484 patches, 9.5 mm), and no misread
#: has been reported on one. The real misreads we have are at 8.0 mm (jctay,
#: "Reading is inconsistent" next to a near-black patch, forum 150236) and
#: 7.1 mm ("Too many patches", 2026-10-21). So an automatic size longer than
#: 8.0 mm gets a calm [INFO] line; 8.0 mm or less, and any size the person
#: set (a patch size, an area-first minimum, a patch-first chart in Manual,
#: the ColorMunki's Extra-high density), keep the warning.
CALM_ABOVE_MM = 8.0


def min_patch_length_mm(instrument: "str | None") -> "float | None":
    """printtarg's minimum for the layout engine's instrument key, or None
    for an instrument this check does not judge."""
    return ARGYLL_MIN_PATCH_LENGTH_MM.get(str(instrument or ""))


def instrument_label(instrument: str) -> str:
    """The instrument's readable name (the shared table in core.settings)."""
    from core.settings import THRESHOLD_INSTR_LABEL
    return THRESHOLD_INSTR_LABEL.get(instrument, instrument)


@dataclass(frozen=True)
class ShortPatches:
    instrument: str          # the layout engine's key ("i1", "p3", "CM")
    min_mm: float            # printtarg's minimum for it
    patch_mm: float          # the shortest patch length of the chart, mm
    #: ChromIQ's own ColorMunki "Extra-high density" (recipe density 3)
    extra_high: bool = False
    #: the patch length is ChromIQ's own automatic choice and longer than
    #: CALM_ABOVE_MM: said as a calm [INFO] line, nothing red
    calm: bool = False


def judge(instrument: "str | None", patch_lengths_mm,
          dpi: float = 300.0, extra_high: bool = False,
          auto_sized: bool = False) -> "ShortPatches | None":
    """A :class:`ShortPatches` when the shortest of *patch_lengths_mm* is
    below the minimum for *instrument* by more than one pixel at *dpi* (a
    patch is drawn on a pixel grid: at 300 dpi a 10 mm patch is 118 px,
    9.99 mm), else None."""
    lo = min_patch_length_mm(instrument)
    lengths = [float(x) for x in (patch_lengths_mm or []) if x]
    if lo is None or not lengths:
        return None
    shortest = min(lengths)
    if shortest >= lo - _MM_PER_INCH / float(dpi or 300.0) - 1e-6:
        return None
    extra = bool(extra_high and instrument == "CM")
    patch = round(shortest, 1)
    return ShortPatches(str(instrument), lo, patch, extra,
                        calm=bool(auto_sized and not extra
                                  and patch > CALM_ABOVE_MM + 1e-9))


def from_channels(channels_json: "str | Path | None") -> "ShortPatches | None":
    """Judge a chart from the layout engine's ``.channels.json``: its
    recorded instrument and the length of its patches along the strip (the
    patch rectangles' height, as the ruler diagnostics measure it). None for
    a chart this check does not judge or cannot read."""
    if not channels_json:
        return None
    try:
        doc = json.loads(Path(channels_json).read_text(encoding="utf-8"))
        layout = doc["layout"]
        if layout.get("engine") != "chromiq":
            return None
        recipe = layout.get("recipe") or {}
        instrument = str(recipe.get("instrument") or "")
        extra = int(recipe.get("cm_density") or recipe.get("density") or 1) >= 3
        dpi = float(layout.get("dpi") or 300) or 300.0
        px = _MM_PER_INCH / dpi
        lengths = [float(r["h"]) * px for r in layout.get("patches") or []
                   if r.get("h")]
        auto = is_auto_sized(layout)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return judge(instrument, lengths, dpi, extra_high=extra,
                 auto_sized=auto)


def is_auto_sized(layout: dict) -> bool:
    """Whether the chart's patch size is ChromIQ's own choice: a Guided
    chart (its record says ``margins_chosen_by_user`` false: Guided has no
    layout controls), or a Manual area-first chart with no patch size and no
    minimum patch size set."""
    if layout.get("margins_chosen_by_user") is False:
        return True
    recipe = layout.get("recipe") or {}
    if str(recipe.get("layout_mode") or "") != "area_first":
        return False
    return not any(float(recipe.get(k) or 0.0) > 0.0 for k in
                   ("area_min_patch_mm", "patch_w_mm", "patch_h_mm"))


def note_text(finding: ShortPatches) -> "tuple[str, str]":
    """M-CHART-PATCHES-SHORT for *finding*: (title, body)."""
    from workflow import measurement_messages as M
    msg = (M.M_CHART_PATCHES_SHORT_AUTO if finding.calm
           else M.M_CHART_PATCHES_SHORT_EXTRA if finding.extra_high
           else M.M_CHART_PATCHES_SHORT)
    return msg.render(
        patch=_mm(finding.patch_mm), min=_mm(finding.min_mm),
        instrument=instrument_label(finding.instrument))


def log_line(finding: ShortPatches) -> str:
    """M-MEASURE-PATCHES-SHORT for *finding*: the Measure log's line (the
    calm [INFO] line of M-CHART-PATCHES-SHORT-AUTO for a calm finding)."""
    from workflow import measurement_messages as M
    if finding.calm:
        return "[INFO] " + note_text(finding)[1]
    msg = (M.M_MEASURE_PATCHES_SHORT_EXTRA if finding.extra_high
           else M.M_MEASURE_PATCHES_SHORT)
    _t, body = msg.render(
        patch=_mm(finding.patch_mm), min=_mm(finding.min_mm),
        instrument=instrument_label(finding.instrument))
    return body


def panel_line(finding: ShortPatches) -> str:
    """M-CHART-PATCHES-SHORT-PANEL: the one line on the surface of the
    "Measured from Preview" frame (the full note is in its ⓘ and the log)."""
    from workflow import measurement_messages as M
    _t, body = M.M_CHART_PATCHES_SHORT_PANEL.render(
        patch=_mm(finding.patch_mm), min=_mm(finding.min_mm),
        instrument=instrument_label(finding.instrument))
    return body


def _mm(v: float) -> str:
    from workflow.measurement_messages import locale_decimal
    text = f"{float(v):.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return locale_decimal(text)
