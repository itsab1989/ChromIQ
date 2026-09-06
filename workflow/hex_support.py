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

from core.stem_paths import artefact, without_ext

from core.i18n import tr
from core.text_io import read_text


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


# A HEXAGON IS TALLER THAN ITS SLOT, AND THE SLOT IS THE ROW PITCH.
#
# Knut, 2026-09-06: *"the height part is wrong and too small. For a hexagonal
# patch, the height top-tip to bottom-tip is always larger than the patch width,
# but the 'Patch size (mm)' says 11.3 x 9.78."* He was right, and by exactly this
# factor.
#
# `geometry.patch_rects_px` records SLOT rects, and `instruments` builds a
# hexagonal geometry with `plen = pwid * sqrt(3)/2` — the interlocking ROW PITCH,
# the distance from one row's centre to the next. The patch itself is bigger:
# `raster._hexagon_points` puts the apexes at `y0 - plen/6` and `y0 + plen +
# plen/6`, so the drawn shape spans `plen * 4/3`, which is `pwid * 2/sqrt(3)` —
# the regular-hexagon relation, tip to tip.
#
# MEASURED, not derived: rendered at 1200 dpi with every patch a different colour
# so an interlocking neighbour could not be mistaken for the patch under test, the
# drawn hexagon came out 7.027 x 8.086 mm against a 7.006 x 6.075 mm slot
# (SpectroScan) and 12.002 x 13.843 mm against 12.002 x 10.393 mm (CR30) — ratios
# 1.33101 and 1.33198 against an ideal 4/3, the residual being pixel snapping.
# `tests/test_a_hexagon_is_taller_than_its_row_pitch.py` re-measures it.
#
# The WIDTH needs no correction: the hexagon's sides are flat and vertical, so it
# is exactly as wide as its slot. Only the height was ever wrong.
HEX_HEIGHT_FACTOR = 4.0 / 3.0


def hex_two_heights_note() -> str:
    """The note that has to appear wherever a honeycomb's height is shown or set.

    ONE string, shared by the Chart-layout-information tooltip and the Manual
    "Patch size (mm)" boxes, because they are the two ends of the same number and
    a note that drifts between them is worse than no note. It is appended to
    those tooltips rather than written into them: both are long, shipped, and
    translated into twelve languages, and retiring their keys mid-beta to add a
    paragraph is not a trade worth making.

    Knut, 2026-09-06 (B8-80), on a chart whose patches print 11.3 × 13.05 mm:
    *"the 'Patch size (mm)' says 11.3 x 9.78."*"""
    return tr(
        "Hexagonal patches have two heights, and they are not the same "
        "number.\n"
        "Hexagons interlock, so a row of them starts before the row above has "
        "finished and the patches sit closer together than they are tall. The "
        "ROW PITCH is that closer spacing, centre to centre down a strip. It "
        "decides how many patches fit on the page, and it is the height you set "
        "in the Patch size boxes. The PATCH is the hexagon itself, measured top "
        "tip to bottom tip, and it is a third taller: set 9.78 mm and you get a "
        "patch 13.05 mm from tip to tip, taller than it is wide. Chart layout "
        "information shows you both.")


def hex_patch_height_mm(row_pitch_mm: float) -> float:
    """Tip-to-tip height (mm) of a hexagon whose slot / row pitch is
    *row_pitch_mm*. See :data:`HEX_HEIGHT_FACTOR`.

    Report only, never geometry: nothing that lays a chart out may call this,
    because capacity and placement are correct on the pitch and the reserved
    apex overhang (``hxeh``) already, and a chart built before this existed must
    still come out byte-identical."""
    return float(row_pitch_mm) * HEX_HEIGHT_FACTOR


def recipe_is_hexagonal(recipe) -> bool:
    """True for a hexagonal-patch recipe (a ``LayoutRecipe`` or the dict form).

    ``hflag`` means hexagons only on an instrument whose geometry actually
    builds them (``instruments.hex_capable`` — the SpectroScan and, since #159,
    the CR30). It must NOT be read as hexagons anywhere else: on the ColorMunki
    the same flag means double density, which is squares.

    Everything downstream keys off this: the measure overlay draws the patch's
    true outline, the strip highlight follows the column zigzag, and the scanner
    tools cap their sample area to what fits inside the hexagon. A CR30
    honeycomb missing from here would be drawn and sampled as if it were
    square.
    """
    if recipe is None:
        return False
    if isinstance(recipe, dict):
        inst = recipe.get("instrument")
        hflag = recipe.get("hflag")
    else:
        inst = getattr(recipe, "instrument", None)
        hflag = getattr(recipe, "hflag", None)
    from workflow.layout_engine.instruments import hex_capable
    return bool(hflag) and hex_capable(str(inst or ""))


def settings_are_hexagonal(create_chart_settings) -> bool:
    """True when a chart's recorded Create Chart settings say **printtarg** drew
    hexagons: instrument SpectroScan with ``-h``.

    Needed because such a chart has no engine recipe, and can still arrive with
    per-patch geometry: printtarg refuses to emit a .cht for it ("Can only
    select hexagonal patches if no scan recognition is needed - ignored!"), so
    the capture is re-run WITHOUT hexagons, its patch locs disagree with the
    chart's own .ti2, ChromIQ's guard drops it — and the geometry is derived
    from the rendered sheet instead. That derivation gives rects but no recipe,
    so a shape test that only reads the recipe would see a rectangular chart and
    lift the sample-area cap on a honeycomb.

    ``-h`` alone is not enough: on the ColorMunki the same flag means double
    density, which is squares."""
    try:
        cs = create_chart_settings or {}

        def value(key):
            rec = cs.get(key)
            return rec.get("value") if isinstance(rec, dict) else rec

        return (str(value("printtarg-i") or "").upper() == "SS"
                and bool(value("printtarg-h")))
    except Exception:      # noqa: BLE001 — an unreadable record is not a claim
        return False


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
        # `p` may be a bare chart STEM whose project name contains a dot, or a
        # real `.ti2`/`.ti3`. Cover both by NAME, never by pathlib's idea of an
        # extension — `split(".")[0]` was the worst of the two, truncating at
        # the FIRST dot ("…-TC9.18-extended-greys" -> "…-TC9"). This guard
        # fails open, so a miss silently stopped the hex chart rejection from
        # ever firing on the names ChromIQ itself suggests.
        candidates.append(artefact(p, ".channels.json"))
        for _ext in (".ti1", ".ti2", ".ti3"):
            candidates.append(artefact(without_ext(p, _ext), ".channels.json"))
    for cj in candidates:
        try:
            if cj.is_file():
                data = json.loads(read_text(cj))
                recipe = (data.get("layout") or {}).get("recipe")
                return recipe_is_hexagonal(recipe)
        except Exception:
            continue
    return False
