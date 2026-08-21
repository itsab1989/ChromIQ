"""Detect SpectroScan hexagonal-patch charts (Knut #126).

Used to decide where a chart's HEXAGON SHAPE matters: the measure overlay draws
the patch's true outline, the strip highlight follows the column's zigzag, and
the scanner tools draw their alignment cells to match.

It no longer gates anything. The scanner and camera features refused a
hexagonal chart on the premise that "the CHT format cannot describe a hexagon" —
true, and beside the point, because a CHT describes the sampling RECTANGLE
inside each patch and takes it from the chart's recorded per-patch geometry.
Measured end to end on a 150-hexagon chart: real ``scanin`` returned 0 with a
standard deviation of 0.106, and real ``colprof`` built a profile from the
result (peak error 0.59, average 0.20). What genuinely fails is scanin's
AUTO-recognition — a hexagon has no horizontal edges for its YLIST — and
ChromIQ places the four corners by hand instead.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.i18n import tr


def hex_scanner_message() -> str:
    """Why the scanner and camera tools turn a hexagonal chart away, and how to
    try it anyway. Replaces the old text, which said the CHT format made this
    impossible — it does not: a CHT describes the rectangle SAMPLED inside each
    patch, and a hexagonal chart profiles correctly end to end. What is not yet
    solved is scanin's chart finder, which can abort on a honeycomb."""
    return tr(
        "This chart uses hexagonal patches, and the scanner and camera tools "
        "are set to turn those away.\n\n"
        "Not because they cannot work — they can. A hexagonal chart has been "
        "read and profiled successfully. The trouble is that ScanIn, the "
        "Argyll program that finds the chart in your scan, looks for long "
        "straight edges to work out how the sheet is rotated. A honeycomb has "
        "none running across it, only the slanted sides of the hexagons, so "
        "ScanIn sometimes measures the rotation badly — and occasionally gives "
        "up on the whole scan, even when you have placed the four corners "
        "yourself.\n\n"
        "There is a second catch: the square that gets sampled inside each "
        "patch is a comfortable fit in a rectangle and a tight one in a "
        "hexagon. Above a Sample area of about 64 % it reaches past the "
        "hexagon's slanted sides into the patches next door, and the colours "
        "come back mixed.\n\n"
        "If you would like to try it anyway, turn on \u201cAllow hexagonal "
        "charts in the scanner and camera tools\u201d in Preferences \u2192 "
        "Beta. Keep the Sample area at or below 60 %, and check the result "
        "before you trust the profile.\n\n"
        "Otherwise, make the chart with square patches: in Create Chart, with "
        "the SpectroScan selected, set the layout to \u201cRectangular\u201d.")


def hex_scanner_allowed(settings) -> bool:
    """True when the user has opted in (Preferences → Beta). Anything that
    cannot read the setting gets the proven behaviour, not the new one."""
    try:
        return bool(settings.get("scanner_hex_charts", False))
    except Exception:      # noqa: BLE001 — a missing store must not open the door
        return False


def recipe_is_hexagonal(recipe) -> bool:
    """True for a SpectroScan hexagonal-patch recipe (a ``LayoutRecipe`` or the
    dict form). ``hflag`` is the SpectroScan-only hex flag."""
    if recipe is None:
        return False
    if isinstance(recipe, dict):
        inst = recipe.get("instrument")
        hflag = recipe.get("hflag")
    else:
        inst = getattr(recipe, "instrument", None)
        hflag = getattr(recipe, "hflag", None)
    return bool(hflag) and inst == "SS"


def chart_is_hexagonal(chart_path: "str | Path | None") -> bool:
    """True when the chart at *chart_path* was made with SpectroScan hexagonal
    patches, read from its ``channels.json`` sidecar. Accepts a .ti1/.ti2/
    .channels.json path (or the chart stem). Missing/unreadable sidecar → False
    (fail open: never block a chart we can't positively identify as hex)."""
    if not chart_path:
        return False
    p = Path(chart_path)
    candidates = []
    if p.name.endswith(".channels.json"):
        candidates.append(p)
    else:
        candidates.append(p.with_suffix(".channels.json"))
        # <stem>.channels.json when the path carries a compound suffix.
        candidates.append(p.parent / (p.name.split(".")[0] + ".channels.json"))
    for cj in candidates:
        try:
            if cj.is_file():
                data = json.loads(cj.read_text())
                recipe = (data.get("layout") or {}).get("recipe")
                return recipe_is_hexagonal(recipe)
        except Exception:
            continue
    return False
