"""Patches shorter than ArgyllCMS's minimum for the instrument (R6, 4.3.39).

ArgyllCMS's printtarg lays a strip instrument's patches out at a minimum
length along the strip, the direction the instrument moves
(``target/printtarg.c`` 3.5.0, the "Patch min length" of each instrument):

* i1Pro family, 4.5/5 mm aperture (printtarg ``-ii1``; the i1Pro, i1Pro 2 and
  i1Pro 3): **10 mm** ("absolute limit is 10", printtarg.c:2159);
* i1Pro 3 Plus, 8 mm aperture (``-i3p``): **20 mm** (printtarg.c:2172; it
  notes 16 mm as the absolute limit with the zebra ruler);
* ColorMunki (``-iCM``): **14 mm** (printtarg.c:2213).

They are the same numbers ChromIQ's layout engine starts from at patch scale
1.0 (``workflow/layout_engine/instruments.py``, ``plen_b`` and the ColorMunki
``plen``; a test keeps the two in step). Shorter patches leave the instrument
fewer readings well inside each patch: a tester's 7.1 mm patches gave "Too
many patches" (2026-10-21) and 8 mm ones "Reading is inconsistent" next to a
near-black patch (jctay, forum 150236). ChromIQ WARNS, it never refuses or
greys anything: the person may have reasons (Basti: defaults safe, options
open). Table and spot instruments (SpectroScan, i1iO, i1iSis, FD-9, CR30) have
rules of their own and are not judged here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: printtarg's minimum patch length along the strip, mm, by the layout
#: engine's instrument key.
ARGYLL_MIN_PATCH_LENGTH_MM = {"i1": 10.0, "p3": 20.0, "CM": 14.0}

_MM_PER_INCH = 25.4


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


def judge(instrument: "str | None", patch_lengths_mm,
          dpi: float = 300.0) -> "ShortPatches | None":
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
    return ShortPatches(str(instrument), lo, round(shortest, 1))


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
        instrument = str((layout.get("recipe") or {}).get("instrument") or "")
        dpi = float(layout.get("dpi") or 300) or 300.0
        px = _MM_PER_INCH / dpi
        lengths = [float(r["h"]) * px for r in layout.get("patches") or []
                   if r.get("h")]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return judge(instrument, lengths, dpi)


def note_text(finding: ShortPatches) -> "tuple[str, str]":
    """M-CHART-PATCHES-SHORT for *finding*: (title, body)."""
    from workflow import measurement_messages as M
    return M.M_CHART_PATCHES_SHORT.render(
        patch=_mm(finding.patch_mm), min=_mm(finding.min_mm),
        instrument=instrument_label(finding.instrument))


def log_line(finding: ShortPatches) -> str:
    """M-MEASURE-PATCHES-SHORT for *finding*: the Measure log's line."""
    from workflow import measurement_messages as M
    _t, body = M.M_MEASURE_PATCHES_SHORT.render(
        patch=_mm(finding.patch_mm), min=_mm(finding.min_mm),
        instrument=instrument_label(finding.instrument))
    return body


def _mm(v: float) -> str:
    from workflow.measurement_messages import locale_decimal
    text = f"{float(v):.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return locale_decimal(text)
