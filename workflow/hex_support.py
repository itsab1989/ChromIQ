"""Detect SpectroScan hexagonal-patch charts (Knut #126).

Used to decide where a chart's HEXAGON SHAPE matters: the measure overlay draws
the patch's true outline, the strip highlight follows the column's zigzag, and
the scanner tools draw their alignment cells to match.

It also decides whether the scanner and camera tools accept such a chart, which
they do only when the user has opted in under Preferences → Beta
(:func:`hex_scanner_allowed`).

The old refusal said "the CHT format cannot describe a hexagon" — true of the
printed shape and beside the point, because a CHT describes the rectangle
SAMPLED inside each patch and takes it from the chart's recorded geometry. A
hexagonal chart has been read and profiled end to end.

Both faults behind the refusal have since been found and fixed, which is why
the text below no longer asks the user to work around them:

* the aborts came from scanin's ``-p`` perspective SEARCH, which is dead work
  when the four corners are placed by hand and collapses on a honeycomb;
  ChromIQ no longer sends it with ``-F`` (23.3 % of reads failed, now 0 %, with
  the values bit-identical — :func:`workflow.scanin_runner.scanin_args`);
* the sampling square escaping the hexagon is now a computed cap on Sample
  area, taken from the chart's own patch proportions
  (:func:`workflow.scanin_runner.hex_max_sample_fraction`), not advice in a
  message that only the people who never see the chart could read.

What is still unproven is scanin's chart finder with NO corners given, so the
opt-in stays until Basti says otherwise.

(Two figures quoted here previously — a "standard deviation of 0.106" and a
"peak error of 0.59" — were removed: the first is scanin's rotation-angle spread
from a recogniser it then discards, and the second cannot see a chart sampling
its own neighbours.)
"""
from __future__ import annotations

import json
from pathlib import Path

from core.i18n import tr


def hex_scanner_message() -> str:
    """Why the scanner and camera tools turn a hexagonal chart away, and how to
    try it anyway. It no longer asks the user to work around the two faults —
    the ``-p`` aborts and the sampling square — because both are fixed in code
    (see the module docstring). What it still declines to promise is finding a
    honeycomb chart with no corners given, which is why the opt-in remains."""
    return tr(
        "This chart uses hexagonal patches, and the scanner and camera tools "
        "are set to turn those away.\n\n"
        "Not because they cannot work — they can. A hexagonal chart has been "
        "read and profiled successfully, and the two things that used to go "
        "wrong have both been dealt with: ScanIn, the Argyll program that finds "
        "the chart in your scan, is no longer asked to work out the perspective "
        "for itself once you have placed the four corners, which is what used "
        "to make it give up on a honeycomb; and the area read inside each patch "
        "is now limited automatically to what fits within the hexagon, so it "
        "cannot reach into the patches next door.\n\n"
        "What has not been proven is finding a honeycomb chart in a scan "
        "without your help — so the tools ask for the four corners, and the "
        "whole thing is still switched off until you say otherwise.\n\n"
        "To try it, turn on \u201cAllow hexagonal charts in the scanner and "
        "camera tools\u201d in Preferences \u2192 Beta, place the four corners "
        "yourself, and check the result before you trust the profile.\n\n"
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
