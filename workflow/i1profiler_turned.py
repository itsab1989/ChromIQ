"""The "turned" i1Profiler export (beta): one ChromIQ sheet that i1Profiler can
measure as well, after a quarter turn.

WHAT IT IS FOR. ChromIQ's i1Profiler patch sets (``-i1profiler.txt/.pxf``)
hand i1Profiler the COLOURS only; i1Profiler always lays out a page of its own,
so a sheet printed by ChromIQ cannot be read in i1Profiler. This module writes
the patch list in the order that makes i1Profiler's ROWS equal ChromIQ's
STRIPS once the printed sheet is turned a quarter turn, plus an i1Profiler
test-chart file (``.txf``) per device family that sets the page, the patch
size and the device in one step. One print can then be measured in both
programs.

Everything here comes from a study measured in i1Profiler 3.8.8 itself
(2026-10-26, ``ChromIQ-work/2026-10-26_i1profiler_layout/analysis.md``): 540 of
540 and 1080 of 1080 patches in the same place, worst colour difference 0 of
255. The physical read with a real instrument has NOT been tested yet.

WHICH WAY THE SHEET IS TURNED (4.3.18, Basti 2026-10-27: *"270° would make
more sense because then the clip border would be on top of the patches and can
fulfill its purpose"*). An i1Pro chart carries its CLIP BORDER, the wide margin
the clip of the ruler's backing board holds, on the LEFT edge of the portrait
sheet (26 mm by default; printtarg's ``-L`` is "suppress any LEFT paper clip
border"), and its strip labels along the TOP. Measured on a real chart
(2026-10-27, A4, 504 patches): patch block 26.0 mm from the left edge, 9.0 mm
from the right, 38.0 mm from the top (labels), 19.0 mm from the bottom. So:

* a clip border on the left (the default) or none at all: a quarter turn
  CLOCKWISE puts that border at the top. Strip A is then the TOP row, the label
  end of every strip on the RIGHT, and a row read left to right runs from the
  strip's last patch to its first;
* a clip border on the right (Create Chart > Clip border > Side: Right): a
  quarter turn ANTICLOCKWISE puts it at the top. Strip A is the BOTTOM row and
  the labels are on the left, as every chart was turned in 4.3.17.

4.3.17 always turned anticlockwise. Its order files (version 1, no ``turn``)
are still read, and pair exactly as before: the order in the file IS the order
of the ``.txf`` beside it. When a chart's export is written again for the very
same chart, an order that differs from the new one is kept in the new file as
an EARLIER order, so a measurement made from the older ``.txf`` still pairs,
by the order ChromIQ wrote for it, and only when its device values agree
(:func:`turned_match`).

THE RULES, AND WHERE EACH COMES FROM (all measured in i1Profiler 3.8.8):

* i1Profiler places patch-list entry ``j`` at column ``j // R``, row ``j % R``
  (column-major, ``R`` rows). So for row ``r`` and column ``c`` we need
  ``L[c * R + r]`` = the patch at place ``c`` of the strip that row ``r`` is.
* A handheld i1Pro 2 / i1Pro 3 row holds at most ``floor(W / width)`` patches,
  ``W`` between 241.5 and 242.4 mm, whatever the page. A full ChromIQ chart
  therefore lines up only when the patch length ``L`` along the strip lies in
  ``242.4 / (P + 1) < L <= 241.5 / P`` (``P`` = patches per strip): "the
  window".
* i1Profiler shares rows evenly over its pages while ChromIQ fills each sheet,
  so the ``.txf`` asks for ONE tall page holding every row.
* If its grid is not full i1Profiler adds grey fillers, so ChromIQ's own
  padding patches go into the list.
* The device in a ``.txf`` is honoured only within i1Profiler's "Default
  display device" family; otherwise the patch-size slider percent is read on
  the wrong scale and the rows merge. Hence one file per family.
* Rows are recognised by patch count plus expected colours, so a spacer would
  be counted as a patch: charts with spacers never qualify. Nor do the i1Pro
  (rev A to D), whose i1Profiler charts carry divider bars ChromIQ cannot draw
  the same way, or any instrument i1Profiler does not read by hand.

THE WAY BACK. i1Profiler numbers the readings of its own chart 1..N in
patch-list order (its CxF objects carry no trace of ChromIQ's patch ids; a real
round trip, 2026-08-08, kept the order exactly: see
``measurement_report.verify_patch_identity``). A turned measurement therefore
arrives in the TURNED order, and the ordinary import refuses it: its device
values do not agree with the chart's patches by ``SAMPLE_ID``. The order file
written here (``-i1profiler-turned.json``, holding the ``.ti2``'s SHA-256)
lets :func:`turned_match` pair it by that order instead, and only when the
device values then agree on every patch, which is a check the pairing did not
choose. See ``docs/design/unified_measurement_management.md`` §I.14.

Best-effort throughout: nothing here may break a chart build.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from core.i18n import tr

log = logging.getLogger(__name__)

#: i1Profiler's device families this export writes a ``.txf`` for.
from core.file_manager import I1P_TURNED_FAMILIES as FAMILIES  # noqa: E402

#: The longest handheld row i1Profiler 3.8.8 makes, in mm: 8.05 mm patches
#: still gave 30 per row, 8.08 mm gave 29, so the cap lies between 241.5 and
#: 242.4 mm. A 420 mm wide page changed nothing: the limit is the ruler, not
#: the page. [measured, tests B, D, E, F]
ROW_CAP_MM = {"i1Pro 2": (241.5, 242.4), "i1Pro 3": (241.5, 242.4)}

#: i1Profiler's patch-size sliders per family, mm: (width min, width max,
#: height min, height max). Percent 0 is the slider minimum. [measured]
SLIDER = {"i1Pro 2": (7.0, 25.0, 8.0, 12.0), "i1Pro 3": (6.0, 25.0, 6.0, 12.0)}

#: The shortest patch X-Rite recommends along the scan, mm (i1Profiler warns
#: below it for the i1Pro 2; 7 mm is the i1Pro 3's minimum).
SCAN_MIN_W = {"i1Pro 2": 10.0, "i1Pro 3": 7.0}

#: A4 landscape as i1Profiler writes it, and the room its page keeps above and
#: below the patch block (24.5 mm measured from the top, 20 mm reserve).
PAGE_W_MM = 296.93
#: THE PAGE WIDTH IS THE OTHER LIMIT ON A ROW (measured 2026-10-27, i1Profiler
#: 3.8.8, i1Pro 3 family, 10 mm patches). i1Profiler keeps 15.5 mm of page on
#: each side of the patch block, and a row holds ``floor(min(cap, page width -
#: 31 mm) / width)`` patches: page 266.0 and 270.5 mm gave 23 per row, 271.5
#: gave 24, 232 to 245 gave 20 (``NumberPatchColumns`` is ignored: 20 asked,
#: 24 made). So a strip SHORTER than the ruler window still becomes one row
#: when the page is made just wide enough for it: ``31 + (P + 0.5) * L``.
PAGE_SIDE_MM = 15.5
#: i1Profiler's tallest custom page, mm: a .txf asking for 2045 mm was shown
#: as "Custom Paper Size 296.8 x 1270 mm, Page 1 of 2" (250 rows split over
#: two pages, which would no longer match ChromIQ's sheets); 1045 mm with 125
#: rows stayed "Page 1 of 1". [measured 2026-10-27, i1Profiler 3.8.8]
PAGE_MAX_H_MM = 1270.0
PAGE_A4_H_MM = 210.06
BLOCK_TOP_MM = 24.5
BLOCK_BOTTOM_MM = 20.0

#: How far two patch lengths may differ and still count as one length, mm.
LENGTH_TOL_MM = 0.05

#: 2 (4.3.18) adds ``turn`` and ``earlier_orders``; 1 is 4.3.17's, always
#: anticlockwise. Both are read.
ORDER_VERSION = 2
READABLE_ORDER_VERSIONS = (1, 2)

#: The two quarter turns (the word stored in the order file).
CLOCKWISE = "clockwise"
ANTICLOCKWISE = "anticlockwise"


def turn_for(recipe: dict) -> str:
    """The quarter turn that puts the chart's clip border at the top.

    The clip border is on the left unless Create Chart's Clip border > Side
    says Right; a chart with the clip border switched off is turned like one
    with it on the left (strip A then reads as the top row)."""
    recipe = recipe if isinstance(recipe, dict) else {}
    has_clip = bool(recipe.get("clip_border", True))
    side = str(recipe.get("clip_side") or "left")
    return ANTICLOCKWISE if (has_clip and side == "right") else CLOCKWISE


def file_tag(family: str) -> str:
    """``"i1Pro 2"`` -> ``"i1Pro2"``, the tag in the ``.txf`` name."""
    return family.replace(" ", "")


#: Where the files live (``core.file_manager``, so all path construction stays
#: in one place).
from core.file_manager import I1ProfilerTurnedFiles as TurnedFiles  # noqa: E402


def sha256_of(path: "str | Path") -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Reading the chart
# ---------------------------------------------------------------------------

@dataclass
class ChartFacts:
    """What the qualification and the order need to know about a chart."""
    ti2: Path
    color_rep: str = ""
    steps: int = 0                       # patches per strip (STEPS_IN_PASS)
    rows: list = field(default_factory=list)    # (sid, loc, {R,G,B 0..100})
    by_loc: dict = field(default_factory=dict)  # loc -> index into rows
    recipe: dict = field(default_factory=dict)
    layout: dict = field(default_factory=dict)  # strips/patches/dpi


def _read_ti2(ti2: Path) -> ChartFacts:
    from core.text_io import read_text
    from workflow.i1profiler_import import read_first_cgats_table
    text = read_text(ti2, lenient=True)
    facts = ChartFacts(ti2=ti2)
    m = re.search(r'^\s*COLOR_REP\s+"?([A-Za-z0-9_]+)', text, re.MULTILINE)
    facts.color_rep = m.group(1) if m else ""
    m = re.search(r'^\s*STEPS_IN_PASS\s+"?(\d+)', text, re.MULTILINE)
    facts.steps = int(m.group(1)) if m else 0
    fields, rows = read_first_cgats_table(ti2)
    idx = {f: i for i, f in enumerate(fields)}
    need = ("SAMPLE_ID", "SAMPLE_LOC", "RGB_R", "RGB_G", "RGB_B")
    if all(k in idx for k in need):
        for r in rows:
            try:
                sid = r[idx["SAMPLE_ID"]].strip('"')
                loc = r[idx["SAMPLE_LOC"]].strip('"')
                vals = {c: float(r[idx[f"RGB_{c}"]]) for c in "RGB"}
            except (IndexError, ValueError):
                continue
            facts.by_loc[loc] = len(facts.rows)
            facts.rows.append((sid, loc, vals))
    return facts


def _read_layout(ti2: Path) -> "tuple[dict, dict]":
    """``(layout, recipe)`` from the chart's ``.channels.json`` (where Create
    Chart folds the engine's geometry) or its ``.strips.json``."""
    for name in (f"{ti2.stem}.channels.json", f"{ti2.stem}.strips.json"):
        p = ti2.parent / name
        if not p.is_file():
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        lay = doc.get("layout", doc) if isinstance(doc, dict) else {}
        if isinstance(lay, dict) and lay.get("patches") and lay.get("strips"):
            rec = lay.get("recipe") if isinstance(lay.get("recipe"), dict) else {}
            return lay, rec
    return {}, {}


# ---------------------------------------------------------------------------
# Qualification and the order
# ---------------------------------------------------------------------------

@dataclass
class TurnedPlan:
    """The outcome for one chart: why it does not qualify, or how it does."""
    reasons: list = field(default_factory=list)   # chart-wide refusals
    hints: list = field(default_factory=list)     # what to change, said once
    family_reasons: dict = field(default_factory=dict)  # family -> [reasons]
    order: list = field(default_factory=list)     # (sid, loc, vals) per entry
    rows: int = 0                                 # i1Profiler rows = strips
    columns: int = 0                              # = patches per strip
    patch_len_mm: float = 0.0
    strip_w_mm: float = 0.0
    row_strips: list = field(default_factory=list)  # (row, sheet, strip label)
    sheets: int = 1
    turn: str = CLOCKWISE                         # which quarter turn
    clip_border: bool = True                      # the chart has one

    @property
    def families(self) -> list:
        """The families a ``.txf`` is written for."""
        if self.reasons:
            return []
        return [f for f in FAMILIES if not self.family_reasons.get(f)]

    @property
    def qualifies(self) -> bool:
        return bool(self.families)


def window_mm(per_strip: int, family: str) -> "tuple[float, float]":
    """The patch lengths that give exactly *per_strip* patches on one
    i1Profiler row: ``(exclusive lower, inclusive upper)`` in mm."""
    lo_cap, hi_cap = ROW_CAP_MM[family]
    return hi_cap / (per_strip + 1), lo_cap / per_strip


def _strip_label(loc: str) -> str:
    m = re.match(r"^([A-Za-z]+)", loc)
    return m.group(1) if m else loc


def spacers_on_sheet(recipe: dict) -> "tuple[bool, bool]":
    """``(between patches, at the strip ends)``: the spacers the PRINTED SHEET
    has, asked of the build the chart was made with, not of the recipe's
    fields.

    **THE "EDGE SPACERS" BOX IS NOT A SPACER ON THE SHEET (4.3.18, forum,
    pharmacist).** 4.3.17 refused every chart whose recipe said
    ``edge_spacers``. But the engine draws an edge spacer only when the chart
    has spacers at all (``raster.render_pages``: ``edge_spacers and sp_px > 0
    and spacer_mode != "none"``), and with Spacers set to None the instrument's
    spacer width is 0, so not even the room is reserved: the sheet is pixel for
    pixel the one made without the box (measured, A4, i1Pro, 8 x 10 mm, 504
    patches: only the printed project name differed). And for the i1Pro the box
    is not even the user's: :meth:`LayoutRecipe.build_kwargs` turns edge spacers
    on for every strip reader, a Guided chart stores that resolved value, and a
    preset or a chart loaded from one carries it into Manual. So a chart with
    no spacer anywhere on it was told *"the chart has spacers at the ends of its
    strips"*, and the user who had set Spacers to None had nothing to change.

    Asked the way the margin inspector and the strip-hover frame ask
    (R22-F4, R23-F3, B8-1570): the kwargs as built, the geometry they give.
    """
    mode = str(recipe.get("spacer_mode", "colored"))
    try:
        from workflow.layout_engine import instruments
        from workflow.layout_engine.presets import build_kwargs_as_built
        kw = build_kwargs_as_built(recipe)
        mode = str(kw.get("spacer_mode", mode))
        geom = instruments.geom_from_build_kwargs(kw)
        # A honeycomb carries its spacer as a ring round each hexagon
        # (`instruments.build` moves pspa into `hex_ring_mm`), and the renderer
        # draws it, edge sides included, whenever that ring is wider than 0.
        width = max(float(geom.pspa or 0.0),
                    float(getattr(geom, "hex_ring_mm", 0.0) or 0.0))
        edge = bool(kw.get("edge_spacers"))
    except Exception:  # noqa: BLE001 - an unreadable recipe: the fields say
        return mode != "none", mode != "none" and bool(
            recipe.get("edge_spacers"))
    drawn = mode != "none" and width > 0
    return drawn, drawn and edge


def plan_for(ti2: "str | Path", turn: "str | None" = None) -> TurnedPlan:
    """Decide whether *ti2* qualifies, and build the turned order if it does.

    *turn* is the quarter turn to build the order for; by default the one that
    puts this chart's clip border at the top (:func:`turn_for`).

    Never raises for a chart it cannot use; every refusal is a plain sentence
    with the real numbers in it.
    """
    ti2 = Path(ti2)
    plan = TurnedPlan()
    facts = _read_ti2(ti2)
    layout, recipe = _read_layout(ti2)
    plan.turn = turn if turn in (CLOCKWISE, ANTICLOCKWISE) else turn_for(recipe)
    plan.clip_border = bool(recipe.get("clip_border", True))
    rep = facts.color_rep.upper()
    if rep and not rep.endswith("RGB"):
        plan.reasons.append(tr(
            "the chart is not an RGB chart ({rep}); the i1Profiler test-chart "
            "file can only be written for RGB charts").format(rep=facts.color_rep))
        return plan
    if not facts.rows:
        plan.reasons.append(tr(
            "the chart file holds no RGB patch list that could be read"))
        return plan
    if not layout:
        plan.reasons.append(tr(
            "the chart was not laid out by the ChromIQ layout engine, so "
            "ChromIQ has no exact map of where each patch sits on the sheet"))
        return plan

    inst = str(recipe.get("instrument") or "")
    if not inst:
        plan.reasons.append(tr(
            "the chart's files do not say which instrument it was laid out "
            "for"))
    elif inst != "i1":
        # "p3" is the i1Pro 3 Plus: its i1Profiler row holds 440 to 460 mm,
        # twice a ChromIQ strip on A4 or A3 [measured on A2, test P].
        from workflow.layout_engine.chart import friendly_instrument
        name = "i1Pro 3 Plus" if inst == "p3" else friendly_instrument(inst)
        plan.reasons.append(tr(
            "the chart is laid out for the {instrument}, not for the i1Pro 2 "
            "or i1Pro 3").format(instrument=name))
    # One question, asked of the sheet: an edge spacer is only ever drawn on a
    # chart that has spacers between its patches too (`spacers_on_sheet`), so
    # that one reason covers both, and 4.3.17's "spacers at the ends of its
    # strips" (said of sheets that had none) is gone.
    if spacers_on_sheet(recipe)[0]:
        plan.reasons.append(tr(
            "the chart has spacers between its patches; i1Profiler would "
            "count every spacer as a patch"))
    if plan.reasons:
        return plan

    try:
        dpi = float(layout.get("dpi") or 0)
        strips = list(layout["strips"])
        patches = list(layout["patches"])
    except (KeyError, TypeError, ValueError):
        dpi, strips, patches = 0.0, [], []
    if dpi <= 0 or not strips or not patches:
        plan.reasons.append(tr(
            "the chart's patch map could not be read"))
        return plan
    mm = 25.4 / dpi

    # Every patch belongs to the strip whose rectangle holds its centre.
    members: list[list[dict]] = [[] for _ in strips]
    for p in patches:
        cx = p["x"] + p["w"] / 2.0
        cy = p["y"] + p["h"] / 2.0
        for si, s in enumerate(strips):
            if (s.get("page", 0) == p.get("page", 0)
                    and s["x"] <= cx <= s["x"] + s["w"]
                    and s["y"] <= cy <= s["y"] + s["h"]):
                members[si].append(p)
                break
    if any(s["w"] >= s["h"] for s in strips):
        plan.reasons.append(tr(
            "the chart's strips do not run down the sheet"))
        return plan
    per = facts.steps or max(len(m) for m in members)
    short = [i for i, m in enumerate(members) if len(m) != per]
    if short:
        plan.reasons.append(tr(
            "not every strip is full: strip {n} holds {got} of its {per} "
            "places").format(n=short[0] + 1, got=len(members[short[0]]),
                              per=per))
        return plan
    if len(facts.rows) != per * len(strips):
        plan.reasons.append(tr(
            "the number of patches ({n}) does not fill the strips ({strips} "
            "strips of {per}) exactly").format(n=len(facts.rows),
                                               strips=len(strips), per=per))
        return plan

    # Patch length = the pitch along the strip; the patches must touch.
    lengths, gaps = [], []
    for m in members:
        m.sort(key=lambda p: p["y"])
        span = (m[-1]["y"] + m[-1]["h"] - m[0]["y"]) * mm
        lengths.append(span / len(m))
        for a, b in zip(m, m[1:]):
            gaps.append((b["y"] - (a["y"] + a["h"])) * mm)
    worst_gap = max(gaps) if gaps else 0.0
    if worst_gap > 0.2:
        plan.reasons.append(tr(
            "there is a gap of {gap} mm between patches in a strip; "
            "i1Profiler needs the patches of a row to touch").format(
                gap=f"{worst_gap:.2f}"))
        return plan
    plen = sum(lengths) / len(lengths)
    if max(lengths) - min(lengths) > LENGTH_TOL_MM:
        plan.reasons.append(tr(
            "the patches are not all the same length ({lo} to {hi} mm)").format(
                lo=f"{min(lengths):.2f}", hi=f"{max(lengths):.2f}"))
        return plan
    plen = round(plen, 2)
    # Strips are whole pixels wide (94 or 95 px for 8 mm at 300 dpi), so the
    # mean over the patches, to 0.1 mm, is the width the recipe asked for.
    swid = round(sum(p["w"] for p in patches) / len(patches) * mm, 1)
    plan.patch_len_mm, plan.strip_w_mm = plen, swid

    # Every location must be in the chart, once.
    locs = [p["loc"] for m in members for p in m]
    if len(set(locs)) != len(locs) or any(l not in facts.by_loc for l in locs):
        plan.reasons.append(tr(
            "the chart's patch map and its patch list do not agree"))
        return plan

    for fam in FAMILIES:
        why = []
        wlo, whi, _hlo, _hhi = SLIDER[fam]
        cap_lo = ROW_CAP_MM[fam][0]
        if per * plen > cap_lo + 1e-9:
            # Longer than any i1Profiler row. ChromIQ's own limit is 240 mm,
            # but two kinds of chart pass it: one built with "No strip length
            # limit", and EVERY "Prioritise chart area" chart on a page taller
            # than that, because area-first fills past the ruler by design and
            # warns (geometry.compute, `fill_beyond_ruler`; Knut). Measured
            # 4.3.18 with the margins Create Chart gives an i1Pro chart (38 /
            # 9 / 19 / 26 mm): A4 and Letter portrait stay within 240 mm, so
            # pharmacist's 24 strips of 27 (forum 149890) qualify there for
            # the i1Pro 3; A3 makes 362.9 mm strips and Legal 298.4 mm. A strip
            # shorter than the ruler window is fine now: the page is made
            # narrow enough for it (`design_settings`).
            why.append(tr(
                "the strips are {strip} mm long ({per} patches of {len} mm), "
                "longer than the {cap} mm an i1Profiler row can hold").format(
                    strip=f"{per * plen:.1f}", per=per, len=f"{plen:.2f}",
                    cap=f"{cap_lo:g}"))
            if str(recipe.get("layout_mode") or "") == "area_first":
                hint = tr(
                    "Why the strips are so long: this chart was made with "
                    "\"Prioritise chart area, then fit patches to it\", which "
                    "stretches every strip over the whole height of the page. "
                    "For a chart that i1Profiler can read as well, set "
                    "\"Create layout\" on Create Chart to \"Prioritise patch "
                    "size, then fit to page\" instead. It keeps every strip "
                    "within ChromIQ's strip length limit: 240 mm for the "
                    "i1Pro, which fits one i1Profiler row, as long as \"Max "
                    "strip length\" is left on auto (or set to at most "
                    "241.5 mm) and \"Don't cap strip length\" is not ticked. "
                    "How many strips the sheet has does not matter.")
                if hint not in plan.hints:
                    plan.hints.append(hint)
        elif not (wlo <= plen <= whi):
            why.append(tr(
                "the patches are {len} mm long, outside the {lo} to {hi} mm "
                "i1Profiler allows for the {family}").format(
                    len=f"{plen:.2f}", lo=f"{wlo:g}", hi=f"{whi:g}",
                    family=fam))
        if plen < SCAN_MIN_W[fam] - 1e-9:
            why.append(tr(
                "the patches are {len} mm long, shorter than the {min} mm "
                "X-Rite asks for when scanning with the {family}").format(
                    len=f"{plen:.2f}", min=f"{SCAN_MIN_W[fam]:g}", family=fam))
        need_h = math.ceil(BLOCK_TOP_MM + len(strips) * min(
            max(swid, SLIDER[fam][2]), SLIDER[fam][3]) + BLOCK_BOTTOM_MM)
        if need_h > PAGE_MAX_H_MM:
            why.append(tr(
                "the chart has {rows} strips, and i1Profiler would need a "
                "page {need} mm tall to show them as one page; its pages are "
                "at most {max} mm tall, so it would split them over pages that "
                "no longer match the printed sheets. Make the chart with fewer "
                "patches, or as two charts").format(
                    rows=len(strips), need=need_h, max=f"{PAGE_MAX_H_MM:g}"))
        plan.family_reasons[fam] = why

    # The order, sheet by sheet (i1Profiler shows all of them as one tall
    # page, sheet 1 at the top).
    # * CLOCKWISE: the sheet's left edge goes to the top, so its strips run
    #   first to last, strip A the top row; its top edge (the label end) goes
    #   to the right, so a row read left to right runs from the strip's LAST
    #   patch to its first.
    # * ANTICLOCKWISE (4.3.17's only turn): strips from last to first, strip A
    #   the bottom row; a row runs from the label end, first patch first.
    pages = sorted({s.get("page", 0) for s in strips})
    row_of: dict[int, int] = {}
    r = 0
    for pg in pages:
        idx = [i for i, s in enumerate(strips) if s.get("page", 0) == pg]
        for si in (idx if plan.turn == CLOCKWISE else reversed(idx)):
            row_of[si] = r
            plan.row_strips.append(
                (r + 1, pages.index(pg) + 1, _strip_label(members[si][0]["loc"])))
            r += 1
    n_rows = len(strips)
    order: list = [None] * (per * n_rows)
    for si, m in enumerate(members):
        seq = list(reversed(m)) if plan.turn == CLOCKWISE else m
        for c, p in enumerate(seq):
            order[c * n_rows + row_of[si]] = facts.rows[facts.by_loc[p["loc"]]]
    plan.order = order
    plan.rows, plan.columns, plan.sheets = n_rows, per, len(pages)
    return plan


def in_ruler_window(plan: TurnedPlan, family: str) -> bool:
    """The strip is long enough that i1Profiler's own row cap gives exactly
    its patch count on the A4-wide page (4.3.17's only case, still used for
    every chart it covered)."""
    lo, hi = window_mm(plan.columns, family)
    return lo < plan.patch_len_mm <= hi


def page_width_mm(plan: TurnedPlan, family: str) -> float:
    """The i1Profiler page width that makes one row exactly one strip.

    In the ruler window, the A4 landscape width (the row cap decides, as
    measured in 4.3.17). Otherwise a page just wide enough for the strip and
    half a patch more, so that ``floor((width - 31) / L)`` is exactly the
    strip's patch count, with half a patch of room either way."""
    if in_ruler_window(plan, family):
        return PAGE_W_MM
    return round(2 * PAGE_SIDE_MM + (plan.columns + 0.5) * plan.patch_len_mm, 2)


def design_settings(plan: TurnedPlan, family: str) -> dict:
    """i1Profiler's settings for *family*: patch width = ChromIQ's patch length,
    patch height = the strip width (held inside the slider), one tall page as
    wide as `page_width_mm` says."""
    wlo, whi, hlo, hhi = SLIDER[family]
    pw = plan.patch_len_mm
    ph = min(max(plan.strip_w_mm, hlo), hhi)
    page_h = max(PAGE_A4_H_MM,
                 math.ceil(BLOCK_TOP_MM + plan.rows * ph + BLOCK_BOTTOM_MM))
    return {"patch_w_mm": pw, "patch_h_mm": ph,
            "patch_w_percent": (pw - wlo) / (whi - wlo) * 100,
            "patch_h_percent": (ph - hlo) / (hhi - hlo) * 100,
            "page_w_mm": page_width_mm(plan, family),
            "page_h_mm": float(page_h)}


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

@dataclass
class TurnedResult:
    written: list = field(default_factory=list)
    #: One plain line for the Create Chart log when no ``.txf`` was written.
    skipped: str = ""
    removed: list = field(default_factory=list)


def remove_stale(folder: "str | Path", stem: str) -> list:
    """Delete a turned export left by an EARLIER build of this chart's name.

    Only the exact file names this module writes; nothing else is touched."""
    files = TurnedFiles(Path(folder), stem)
    gone = []
    for p in files.all():
        try:
            if p.is_file():
                p.unlink()
                gone.append(p)
        except OSError:
            log.warning("could not remove the stale %s", p.name, exc_info=True)
    return gone


def remove_unless_current(folder: "str | Path", stem: str,
                          chart_ti2: "str | Path") -> list:
    """With the option off: delete the turned export in *folder* only when it
    no longer describes *chart_ti2*, the chart that stays on disk.

    SWITCHING THE OPTION OFF IS NOT A REASON TO DELETE (review 4.3.17 r2,
    SF-1; §I.14 point 2). A chart made with the option on keeps its order
    file for as long as that chart is on disk, because the order is what lets
    a turned measurement of THAT sheet be paired; Restore Used Chart redraws
    the pages of the same chart and used to take the order with it. So the
    files go only when their order names another chart (an earlier build of
    this name), or there is no order to judge them by."""
    files = TurnedFiles(Path(folder), stem)
    if _order_in(files.order, chart_ti2) is not None:
        return []
    return remove_stale(folder, stem)


def carry_turned_export(src_ti2: "str | Path", dst_ti2: "str | Path",
                        dst_folder: "str | Path", dst_stem: str) -> list:
    """Copy the turned export of *src_ti2* beside its copy *dst_ti2*, into
    *dst_folder* under *dst_stem* (a new project made from a chart folder;
    review 4.3.17 r2, NIT-1). Returns what was copied.

    ONLY WHEN THE COPY IS STILL THAT CHART. The order is bound to the chart
    by its SHA-256, so it is carried only when it names *src_ti2* AND the
    copied *dst_ti2* has the very same bytes; anything else would put an
    order beside a chart it does not describe. Nothing is copied when the
    chart has no turned export. Best-effort: never raises."""
    copied: list = []
    try:
        src_ti2, dst_ti2 = Path(src_ti2), Path(dst_ti2)
        order = turned_order_for(src_ti2)
        if order is None or _order_in(order.path, dst_ti2) is None:
            return copied
        src = TurnedFiles(order.path.parent, src_ti2.stem)
        dst = TurnedFiles(Path(dst_folder), dst_stem)
        pairs = [(src.order, dst.order), (src.note, dst.note),
                 *((src.txf(f), dst.txf(f)) for f in FAMILIES)]
        Path(dst_folder).mkdir(parents=True, exist_ok=True)
        for a, b in pairs:
            if a.is_file():
                shutil.copy2(a, b)
                copied.append(b)
        if dst.order in copied:
            write_merged_order(order, dst.order)
    except Exception:  # noqa: BLE001 — never break an import
        log.warning("could not carry the turned i1Profiler export",
                    exc_info=True)
    return copied


def write_merged_order(order: "TurnedOrder", dst: "str | Path") -> bool:
    """Make the order file *dst*, a copy of *order*'s own file, hold every
    order *order* merged: the one in force and each earlier one.

    **A COPY PAIRS AND REFUSES EXACTLY LIKE THE ORIGINAL (review 4.3.18 r2,
    NIT5).** :func:`turned_order_for` reads a chart's orders from ``exports/``
    AND from beside the chart and merges them; a copy (Duplicate run, New
    project from a chart folder) carries the files of one place only. Without
    this, an earlier order kept only beside the original chart was lost: a
    measurement made with that older ``.txf`` paired with the original and
    was refused for the copy, and a file the original refuses as fitting two
    orders could be filed by the copy, which knew only one. A version 1 file
    (4.3.17, always anticlockwise, read without earlier orders) is written as
    version 2 with its turn named, so the earlier orders are read. Nothing is
    rewritten when there is no earlier order. Returns whether it wrote."""
    if not order.earlier:
        return False
    dst = Path(dst)
    try:
        doc = json.loads(Path(order.path).read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            return False
        if doc.get("version") == 1:
            doc["version"] = ORDER_VERSION
            doc["turn"] = str(doc.get("turn") or ANTICLOCKWISE)
        doc["earlier_orders"] = [
            {"version": c.version, "turn": c.turn,
             "order": [{"sample_id": i, "loc": l}
                       for i, l in zip(c.sample_ids, c.locs)]}
            for c in order.earlier]
        dst.write_text(json.dumps(doc, indent=1) + "\n",
                       encoding="utf-8")
        return True
    except (OSError, ValueError):
        log.warning("could not write the merged turned order %s", dst,
                    exc_info=True)
        return False


def _write_txf(plan: TurnedPlan, family: str, out: Path, title: str) -> None:
    from workflow.i1profiler_export import Target, WorkflowOptions, write_pwxf
    d = design_settings(plan, family)
    tgt = Target("iRGB", "RGB", ["R", "G", "B"],
                 [(int(sid) if str(sid).isdigit() else i + 1, vals)
                  for i, (sid, _loc, vals) in enumerate(plan.order)])
    opt = WorkflowOptions(
        device=family, measurement_mode=1,
        paper_format=(2 if (d["page_h_mm"] <= PAGE_A4_H_MM
                            and d["page_w_mm"] == PAGE_W_MM) else 0),
        paper_orientation="Landscape", page_width_mm=d["page_w_mm"],
        page_height_mm=d["page_h_mm"], columns=plan.columns, rows=plan.rows,
        pages=1, patch_w_mm=d["patch_w_mm"], patch_h_mm=d["patch_h_mm"],
        patch_w_percent=d["patch_w_percent"],
        patch_h_percent=d["patch_h_percent"], title=title)
    write_pwxf(tgt, out, title, opt)


def _order_doc(plan: TurnedPlan, ti2: Path, earlier: "list | None" = None) -> dict:
    doc = {
        "version": ORDER_VERSION,
        "what": "ChromIQ turned i1Profiler export: entry j of the i1Profiler "
                "patch list (1-based) is the chart patch named here",
        "chart": ti2.name, "chart_sha256": sha256_of(ti2),
        "turn": plan.turn,
        "patches": len(plan.order), "rows": plan.rows,
        "columns": plan.columns, "sheets": plan.sheets,
        "patch_length_mm": plan.patch_len_mm, "strip_width_mm": plan.strip_w_mm,
        "families": plan.families,
        "row_to_strip": [{"row": r, "sheet": s, "strip": lab}
                         for r, s, lab in plan.row_strips],
        "order": [{"sample_id": sid, "loc": loc} for sid, loc, _v in plan.order],
    }
    if earlier:
        doc["earlier_orders"] = earlier
    return doc


def _earlier_orders(path: Path, ti2: Path, plan: TurnedPlan) -> list:
    """The orders ChromIQ already wrote for this very chart, other than the
    new *plan*'s: kept in the new file so a measurement made from an older
    ``.txf`` still pairs.

    FROM EVERY PLACE THE CHART'S TURNED FILES MAY BE (review 4.3.18 r1,
    N-1): the order file at *path* that is about to be replaced, and those
    in ``exports/`` and beside the chart (:meth:`TurnedFiles.for_chart`), each
    with the orders it kept itself. Only for the same chart (SHA-256): an
    order of an earlier build of this name describes another sheet and is
    dropped as before."""
    try:
        digest = sha256_of(ti2)
    except OSError:
        return []
    paths = []
    for p in [Path(path), *(f.order for f in TurnedFiles.for_chart(ti2))]:
        if p not in paths:
            paths.append(p)
    found = [o for o in (_order_in(p, ti2, digest) for p in paths)
             if o is not None]
    new_ids = [str(sid) for sid, _l, _v in plan.order]
    out, seen = [], {tuple(new_ids)}
    for o in found:
        for c in o.candidates():
            key = tuple(c.sample_ids)
            if key in seen or sorted(key) != sorted(new_ids):
                continue
            seen.add(key)
            out.append({"version": c.version, "turn": c.turn,
                        "order": [{"sample_id": i, "loc": l}
                                  for i, l in zip(c.sample_ids, c.locs)]})
    return out


def write_turned_export(ti2: "str | Path", out_dir: "str | Path",
                        stem: str) -> TurnedResult:
    """Write the turned export of *ti2* into *out_dir*, or a note saying why
    not. Best-effort: never raises."""
    res = TurnedResult()
    try:
        ti2, out_dir = Path(ti2), Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        files = TurnedFiles(out_dir, stem)
        plan = plan_for(ti2)
        # Read BEFORE the old files go: an order this very chart already had
        # (4.3.17's anticlockwise one, say) is kept as an earlier order.
        earlier = (_earlier_orders(files.order, ti2, plan)
                   if plan.qualifies else [])
        res.removed = remove_stale(out_dir, stem)
        if not plan.qualifies:
            why = plan.reasons or [r for f in FAMILIES
                                   for r in plan.family_reasons.get(f, [])]
            files.note.write_text(note_not_qualified(plan, ti2.name),
                                  encoding="utf-8")
            res.written.append(files.note)
            res.skipped = tr(
                "No turned i1Profiler chart was written for {chart}: {why}. "
                "{note} says more.").format(
                    chart=ti2.name, why="; ".join(dict.fromkeys(why)),
                    note=files.note.name)
            return res
        for fam in plan.families:
            out = files.txf(fam)
            _write_txf(plan, fam, out, f"{stem}-turned-{file_tag(fam)}")
            res.written.append(out)
        files.order.write_text(
            json.dumps(_order_doc(plan, ti2, earlier), indent=1),
            encoding="utf-8")
        res.written.append(files.order)
        files.note.write_text(note_qualified(plan, ti2.name, files,
                                             written_again=bool(earlier)),
                              encoding="utf-8")
        res.written.append(files.note)
    except Exception:  # noqa: BLE001 — never break a chart build
        log.warning("turned i1Profiler export failed", exc_info=True)
        res.skipped = tr(
            "The turned i1Profiler chart could not be written; the chart "
            "itself is fine.")
    return res


# ---------------------------------------------------------------------------
# The note
# ---------------------------------------------------------------------------

def note_qualified(plan: TurnedPlan, chart_name: str, files: TurnedFiles,
                   written_again: bool = False) -> str:
    """The plain-language note for a chart that qualifies.

    NO FILE STEM IN IT (review 4.3.17 r1). A project rename renames these
    files and the chart, and a note that named "Old.ti2" and
    "Old-i1profiler-turned.json" then sent the person looking for files that
    no longer existed. Every file is named by the ending it keeps whatever
    the project is called. *chart_name* is kept for the callers.

    *written_again*: ChromIQ wrote these files for this very chart before,
    in another order (4.3.17's anticlockwise turn), and kept that order as an
    earlier one. The note then says so, because i1Profiler may still hold the
    earlier ``.txf`` (review 4.3.18 r1, SF-4)."""
    parts = [tr("ChromIQ: measuring this chart in i1Profiler as well (beta)"),
             "=" * 60, ""]
    parts.append(tr(
        "This folder holds i1Profiler test-chart files for the printed sheet "
        "of the chart they belong to: the .ti2 file whose name they start "
        "with. With one of them, i1Profiler lays out its own chart exactly "
        "like ChromIQ's printed sheet turned a quarter turn, so you can "
        "measure the SAME print in ChromIQ and in i1Profiler."))
    parts.append("")
    parts.append(tr(
        "IMPORTANT: this is a beta. The layout was checked patch for patch "
        "in i1Profiler 3.8.8 with the i1Pro 3 file. The i1Pro 2 file is "
        "written by the same rules, but it could not be opened in i1Profiler "
        "yet, so it has not been checked there. Nobody has yet read such a "
        "sheet with a real instrument, or imported a real i1Profiler "
        "measurement of one. Please check the result before you rely on it."))
    parts.append("")
    if written_again:
        if plan.turn == CLOCKWISE:
            parts.append(tr(
                "These files were written again. ChromIQ had already written "
                "i1Profiler files for this very chart before, for a sheet "
                "turned the other way (ChromIQ 4.3.17 turned every sheet "
                "anticlockwise), and has now written them for a sheet turned "
                "clockwise, so that the clip border is at the top. If "
                "i1Profiler still has the earlier file loaded, or you loaded "
                "it from i1Profiler's own folder, load the file from this "
                "folder again on the Test Chart page (step 4), and turn the "
                "sheet a quarter turn CLOCKWISE as step 2 says. A measurement "
                "you already made with the earlier file can still be "
                "imported: ChromIQ keeps the earlier order and puts its "
                "readings on the right patches, unless this chart repeats "
                "its colours so that the two files cannot be told apart; "
                "ChromIQ then says so and changes nothing."))
        else:
            parts.append(tr(
                "These files were written again. ChromIQ had already written "
                "i1Profiler files for this very chart before, in another "
                "order. If i1Profiler still has the earlier file loaded, or "
                "you loaded it from i1Profiler's own folder, load the file "
                "from this folder again on the Test Chart page (step 4), and "
                "turn the sheet the way step 2 says. A measurement you "
                "already made with the earlier file can still be imported: "
                "ChromIQ keeps the earlier order and puts its readings on "
                "the right patches, unless this chart repeats its colours so "
                "that the two files cannot be told apart; ChromIQ then says "
                "so and changes nothing."))
        parts.append("")
    parts.append(tr("Which instruments"))
    parts.append(tr(
        "Only an i1Pro 2 or an i1Pro 3, read by hand along its ruler. Not the "
        "original i1Pro (i1Profiler 3.8.8 no longer supports it), not the "
        "i1Pro 3 Plus, not an i1iO or i1iSis, not a ColorMunki, and none of "
        "the other instruments ChromIQ supports."))
    for fam in FAMILIES:
        if fam in plan.families:
            parts.append(tr("  {family}: load the file ending in {ending}").format(
                family=fam, ending=files.txf(fam).name[len(files.stem):]))
        else:
            parts.append(tr("  {family}: no file, because {why}.").format(
                family=fam, why="; ".join(plan.family_reasons.get(fam, []))))
    parts.append("")
    parts.append(tr("Step by step"))
    parts.append(tr(
        "1. Print the chart from ChromIQ as usual. Do not print i1Profiler's "
        "chart: the point is to measure ChromIQ's sheet."))
    parts.append(turn_step(plan))
    parts.append(tr(
        "3. Start i1Profiler. On its start page, under Application Settings, "
        "set Default display device to the family of the instrument you "
        "measure with: the i1Pro 2 family for an i1Pro 2, the i1Pro 3 family "
        "for an i1Pro 3. If it names the other family, i1Profiler reads the "
        "patch size on the wrong scale and the rows come out wrong."))
    parts.append(tr(
        "4. Set User Mode to Advanced, choose Printer, then Profiling, and go "
        "to the Test Chart page (press Next on the Patch Set page). Under "
        "Page Data press Load and choose the file for your instrument (see "
        "above). When i1Profiler asks whether to copy the file to the assets "
        "folder, either answer is fine."))
    parts.append(tr(
        "5. Check the chart i1Profiler now shows. It must be exactly "
        "this grid: columns: {cols}, rows: {rows}, pages: 1, patch width "
        "{w} mm. If it shows anything else, stop: the rows would not match "
        "the sheet.").format(cols=plan.columns, rows=plan.rows,
                             w=f"{plan.patch_len_mm:.2f}"))
    parts.append(tr(
        "6. Press Next to the Measurement page and choose a measurement mode. "
        "The names below are the ones i1Profiler shows in English. With an "
        "i1Pro 2: Single Scan (M0), or Dual scan (M0,M1,M2 and OBC) if you "
        "want M1 and M2 as well; each row is then read twice, forwards and "
        "back. With an i1Pro 3: Single scan (M0,M1,M2 and OBC), which gives "
        "M0, M1 and M2 in one pass. Calibrate, and measure the rows from top "
        "to bottom, each one from left to right, starting and ending on the "
        "white paper beside the row."))
    parts.append(tr(
        "   i1Profiler checks every row as you read it, against the colours "
        "it expects on that row, and asks you to read it again if it does "
        "not fit. That check is the one that catches a row read in the wrong "
        "place, so always read the row again when it asks. ChromIQ cannot "
        "see a misplaced row afterwards."))
    if plan.sheets > 1:
        parts.append(tr(
            "   This chart has {n} sheets. i1Profiler shows all of them as ONE "
            "tall page: the first rows belong to sheet 1, then the next sheet "
            "follows (see the list of rows below). Lay each sheet down turned "
            "the same way when its rows come up.").format(n=plan.sheets))
    parts.append(tr(
        "7. When every row is measured, press Save under Page Data on the "
        "Measurement page and save the measurement as an .mxf file, "
        "i1Profiler's own format and the format this was checked with. A "
        "CGATS text export that includes the RGB values is paired the same "
        "way. One without device values is refused on this chart: "
        "i1Profiler names the patches by its own rows and columns (its A1 "
        "is not ChromIQ's A1), so only the device values (the RGB values of "
        "the test-chart file) tell ChromIQ which patch each reading belongs "
        "to. Leave i1Profiler's Scramble patches setting off. Measure the whole chart: ChromIQ brings a turned "
        "measurement back only when every patch has been read, and refuses "
        "a file that holds only part of the rows, saying how many readings "
        "it holds."))
    parts.append(tr(
        "8. To bring the measurement into ChromIQ: open this run, go to the "
        "Measure tab, press IMPORT, choose the .mxf file (or the CGATS "
        "text export with the RGB values) with the folder button beside "
        "Measurement File (from i1Profiler), and press Import "
        "Measurement. ChromIQ recognises the turned order from the order "
        "file in this folder (the one ending in -i1profiler-turned.json) and "
        "puts every reading on its own patch. First it checks that the "
        "device values in the file are this chart's, entry for entry. That "
        "proves the measurement was made from this chart's test-chart file; "
        "it does not prove that each row was read in the right place, which "
        "is what i1Profiler's row check in step 6 is for. If the device "
        "values do not agree, ChromIQ refuses the file and nothing is "
        "changed. If the file holds more than one measurement condition, "
        "ChromIQ uses M2, then M1, then M0."))
    parts.append("")
    parts.append(tr("Which i1Profiler row is which ChromIQ strip"))
    for r, sheet, lab in plan.row_strips:
        if plan.sheets > 1:
            parts.append(tr("  Row {row}: sheet {sheet}, strip {strip}").format(
                row=r, sheet=sheet, strip=lab))
        else:
            parts.append(tr("  Row {row}: strip {strip}").format(
                row=r, strip=lab))
    parts.append("")
    parts.append(tr("Measurements without device values"))
    parts.append(tr(
        "While the order file is here, ChromIQ accepts a measurement of "
        "this chart only if it carries device values. A file without them, "
        "for example a CGATS text export saved without the RGB values, or a "
        "reading made with an i1iO through i1Profiler's measure tool, which ChromIQ otherwise pairs by "
        "patch name, is refused for this chart: on this chart i1Profiler's "
        "patch names are the same set as ChromIQ's but sit on other patches, "
        "so pairing by name could put every reading on the wrong patch. This "
        "belongs to the chart and its order file, not to the switch in "
        "Preferences: turning the option off later does not change it. If "
        "you want to read this chart in a way that gives no device values, "
        "create the chart again in Create Chart with the option off; that "
        "removes these files, and such a file is then paired by name as "
        "before."))
    parts.append("")
    parts.append(tr(
        "Do not edit or move the order file (the one ending in "
        "-i1profiler-turned.json): it records which chart these files were "
        "made for, and ChromIQ needs it to bring the measurement back. A new "
        "chart replaces all of these files (with the option off, it removes "
        "them), and renaming the project renames them with it. Duplicating the run, or making a new project from "
        "this chart's folder, copies them along with the chart."))
    return "\n".join(parts) + "\n"


def turn_step(plan: TurnedPlan) -> str:
    """Step 2 of the note: which way to turn THIS chart's sheet, and what is
    where afterwards."""
    if plan.turn == ANTICLOCKWISE:
        return tr(
            "2. Turn the printed sheet a quarter turn ANTICLOCKWISE, so that "
            "the clip border (the wide margin on the right-hand side of the "
            "upright sheet) is at the TOP, where the clip of the ruler's "
            "backing board holds the paper. The strip labels are now on the "
            "LEFT, and the sheet's first strip (strip A on sheet 1) is the "
            "BOTTOM row. Every ChromIQ strip is now one i1Profiler row, read "
            "from left to right.")
    if not plan.clip_border:
        return tr(
            "2. Turn the printed sheet a quarter turn CLOCKWISE, so that the "
            "left-hand edge of the upright sheet is at the TOP. The strip "
            "labels are now on the RIGHT, and the sheet's first strip (strip "
            "A on sheet 1) is the TOP row. Every ChromIQ strip is now one "
            "i1Profiler row, read from left to right, which is from the "
            "strip's last patch to its first.")
    return tr(
        "2. Turn the printed sheet a quarter turn CLOCKWISE, so that the clip "
        "border (the wide margin on the left-hand side of the upright sheet) "
        "is at the TOP, where the clip of the ruler's backing board holds the "
        "paper. The strip labels are now on the RIGHT, and the sheet's first "
        "strip (strip A on sheet 1) is the TOP row. Every ChromIQ strip is "
        "now one i1Profiler row, read from left to right, which is from the "
        "strip's last patch to its first.")


def note_not_qualified(plan: TurnedPlan, chart_name: str) -> str:
    """The short note for a chart that does not qualify: why, with numbers."""
    parts = [tr("ChromIQ: measuring this chart in i1Profiler as well (beta)"),
             "=" * 60, ""]
    parts.append(tr(
        "No i1Profiler test-chart file was written for this chart, because "
        "it cannot be read in i1Profiler after a quarter turn:"))
    if plan.reasons:
        for r in plan.reasons:
            parts.append("  - " + r)
    else:
        for fam in FAMILIES:
            for r in plan.family_reasons.get(fam, []):
                parts.append(f"  - {fam}: {r}")
    for h in plan.hints:
        parts += ["", h]
    parts.append("")
    parts.append(tr(
        "What qualifies: an RGB chart made by ChromIQ's layout engine for the "
        "i1Pro family, with no spacers and every strip full, on any paper "
        "size, portrait or landscape. Along the strip the patches must be 10 "
        "to 25 mm long for the i1Pro 2 and 7 to 25 mm long for the i1Pro 3, "
        "a strip may be at most 241.5 mm long, and the whole chart has to "
        "fit on one i1Profiler page, which is at most 1270 mm tall. "
        "i1Profiler gives each strip a row as tall as the strip is wide, but "
        "at least 8 mm (6 mm for the i1Pro 3) and at most 12 mm, so that is "
        "about 150 strips when they are 8 mm wide and about 100 when they "
        "are 12 mm wide. Only the i1Pro 2 and the i1Pro 3 can read it. The "
        "layout was compared cell by cell with i1Profiler 3.8.8's own chart "
        "on A4, Letter, A4 landscape, 4 x 6 inch and 5 x 7 inch paper, with "
        "patches from 7 to 25 mm long (the i1Pro 3 file). Whatever the "
        "chart, always check, as step 5 of the note for a qualifying chart "
        "says, that i1Profiler shows exactly the grid that note names."))
    parts.append(tr(
        "How to make one: on Create Chart choose MANUAL and the instrument "
        "i1Pro / i1Pro 2 / i1Pro 3, tick \"Use the ChromIQ layout engine "
        "instead of printtarg\", set Create layout to \"Prioritise patch "
        "size, then fit to page\", type a patch size of 8 x 10 mm (8 mm "
        "across the strip, 10 mm along it), leave the patch count on Auto, "
        "open Expert Options and set Spacers to None. Then press Generate "
        "Chart again."))
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# The way back
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TurnedOrder:
    path: Path
    sample_ids: list        # chart SAMPLE_ID of i1Profiler entry j (index j-1)
    locs: list
    #: Which quarter turn this order is for (version 1 files: anticlockwise).
    turn: str = ANTICLOCKWISE
    #: Orders ChromIQ wrote EARLIER for this very chart, newest first, each a
    #: ``TurnedOrder`` without earlier orders of its own (see `_earlier_orders`).
    earlier: tuple = ()
    #: The order file's version (1 = 4.3.17's), kept when it is carried over.
    version: int = ORDER_VERSION

    def candidates(self) -> list:
        """This order first, then the earlier ones."""
        return [self, *self.earlier]


def turned_order_for(chart_ti2: "str | Path | None") -> "TurnedOrder | None":
    """The turned order written for exactly this chart, or ``None``.

    Tied to the chart by its SHA-256: an order written for an earlier chart
    of the same name is not this chart's and is ignored."""
    if chart_ti2 is None:
        return None
    chart_ti2 = Path(chart_ti2)
    # WHETHER AN ORDER FILE EXISTS IS ASKED FIRST. Every import of every
    # measurement reaches this, and with the option off there is none: a stat
    # per candidate folder is all it may cost then, never a hash of the chart.
    candidates = [f.order for f in TurnedFiles.for_chart(chart_ti2)]
    candidates = [p for p in candidates if p.is_file()]
    if not candidates or not chart_ti2.is_file():
        return None
    try:
        digest = sha256_of(chart_ti2)
    except OSError:
        return None
    # BOTH PLACES ARE READ, AND MERGED (review 4.3.18 r1, N-1). Create Chart
    # writes into exports/, the TI2 layout editor beside the chart; an order
    # either of them wrote for exactly this chart is one ChromIQ wrote for it.
    # The one in exports/ is the order in force; every other order found is
    # an earlier one, each kept once.
    found = [o for o in (_order_in(p, chart_ti2, digest) for p in candidates)
             if o is not None]
    return _merged(found) if found else None


def _merged(found: list) -> "TurnedOrder":
    """One order from several files' orders: the first file's own order in
    force, every other distinct order of the same patches an earlier one."""
    main = found[0]
    seen = {tuple(main.sample_ids)}
    earlier = []
    for o in found:
        for c in o.candidates():
            key = tuple(c.sample_ids)
            if key in seen or sorted(c.sample_ids) != sorted(main.sample_ids):
                continue
            seen.add(key)
            earlier.append(TurnedOrder(c.path, c.sample_ids, c.locs,
                                       turn=c.turn, version=c.version))
    return TurnedOrder(main.path, main.sample_ids, main.locs, turn=main.turn,
                       earlier=tuple(earlier), version=main.version)


def _order_in(path: Path, chart_ti2: "str | Path",
              digest: "str | None" = None) -> "TurnedOrder | None":
    """The order in the one file *path*, when it was written for exactly
    *chart_ti2* (its SHA-256); otherwise ``None``."""
    try:
        if not Path(path).is_file() or not Path(chart_ti2).is_file():
            return None
        if digest is None:
            digest = sha256_of(chart_ti2)
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (not isinstance(doc, dict)
            or doc.get("version") not in READABLE_ORDER_VERSIONS
            or doc.get("chart_sha256") != digest):
        return None

    def _one(entries, turn, version):
        try:
            ids = [str(e.get("sample_id", "")) for e in entries]
            locs = [str(e.get("loc", "")) for e in entries]
        except AttributeError:
            return None
        if ids and all(ids) and len(set(ids)) == len(ids):
            try:
                version = int(version)
            except (TypeError, ValueError):
                version = 1
            return TurnedOrder(Path(path), ids, locs, turn=turn,
                               version=version)
        return None

    # Version 1 (4.3.17) knew one turn only, and wrote no word for it.
    main = _one(doc.get("order") or [], str(doc.get("turn") or ANTICLOCKWISE),
                doc.get("version"))
    if main is None:
        return None
    earlier = []
    if doc.get("version") != 1:
        for e in doc.get("earlier_orders") or []:
            if not isinstance(e, dict):
                continue
            o = _one(e.get("order") or [], str(e.get("turn") or ANTICLOCKWISE),
                     e.get("version"))
            # The same patches, every one once: anything else is not an
            # order of this chart's patch list and is ignored.
            if o is not None and sorted(o.sample_ids) == sorted(main.sample_ids):
                earlier.append(o)
    return TurnedOrder(main.path, main.sample_ids, main.locs, turn=main.turn,
                       earlier=tuple(earlier), version=main.version)


@dataclass(frozen=True)
class TurnedMatch:
    applies: bool = False      # the file is shaped like a turned measurement
    verified: bool = False     # and its device values agree in that order
    #: Fewer readings than the order has entries, numbered within 1..N: a
    #: turned measurement that stopped part way. Never filed (§I.14).
    partial: bool = False
    compared: int = 0
    mismatched: int = 0
    worst: float = 0.0
    order: "TurnedOrder | None" = None
    #: More than one order ChromIQ wrote for this chart agrees on every patch,
    #: and they would put readings on different patches (review 4.3.18 r1,
    #: SF-1). Never paired: nothing in the file says which one was measured.
    ambiguous: bool = False
    #: Every order whose device values agree on every patch (``order`` is the
    #: first of them), so that a caller can compare their pairings with the
    #: ordinary one by ``SAMPLE_ID`` (:func:`fits_straight_and_turned`).
    fitting: tuple = ()


def turned_match(measured, chart_ti2: "str | Path | None") -> TurnedMatch:
    """Would *measured* (a parsed ``.ti3``) pair with the chart through the
    turned order?

    It applies only when this chart has a turned order, the file carries
    device values, and its ``SAMPLE_ID``s are exactly ``1..N`` for the N
    entries of that order: i1Profiler's own numbering. The device values are
    then compared, patch for patch, with the chart patch the ORDER names. The
    order was fixed when the chart was made, so the comparison checks a
    pairing it did not choose (§I.9).
    """
    order = turned_order_for(chart_ti2)
    if order is None or measured is None or not getattr(measured, "has_device", False):
        return TurnedMatch()
    n = len(order.sample_ids)
    ids = [str(s).strip('"') for s in (measured.sample_ids or [])]
    partial = False
    if len(ids) != n or sorted(ids, key=lambda s: (len(s), s)) != [
            str(i) for i in range(1, n + 1)]:
        # A PART OF A TURNED MEASUREMENT is recognised too, so that it can be
        # refused for what it is: fewer readings, each numbered once within
        # 1..N. It is still compared below, so that only a file whose device
        # values really follow the turned order is called one.
        allowed = {str(i) for i in range(1, n + 1)}
        if not (0 < len(ids) < n and len(set(ids)) == len(ids)
                and set(ids) <= allowed):
            return TurnedMatch(order=order)
        partial = True
    from workflow.measurement_report import PATCH_IDENTITY_TOL, _rgb_to_0_100
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    import numpy as np
    try:
        design = parse_ti3(Path(chart_ti2))
    except (Ti3ParseError, OSError):
        return TurnedMatch(order=order)
    want = _rgb_to_0_100(np.asarray(design.rgb, dtype=float))
    got = _rgb_to_0_100(np.asarray(measured.rgb, dtype=float))
    by_id = {sid: i for i, sid in enumerate(design.sample_ids)}

    def _against(cand: TurnedOrder) -> TurnedMatch:
        diffs = []
        for mi, sid in enumerate(ids):
            di = by_id.get(cand.sample_ids[int(sid) - 1])
            if di is None:
                return TurnedMatch(applies=True, order=cand)
            diffs.append(float(np.abs(want[di] - got[mi]).max()))
        bad = sum(1 for d in diffs if d > PATCH_IDENTITY_TOL)
        return TurnedMatch(applies=True, verified=bad == 0, partial=partial,
                           compared=len(diffs), mismatched=bad,
                           worst=round(max(diffs), 4), order=cand)

    # EVERY ORDER ChromIQ WROTE FOR THIS VERY CHART IS ASKED: the one in
    # force and any earlier one (4.3.17's anticlockwise turn). Each was fixed
    # when its `.txf` was written, so whichever one the device values follow
    # is a pairing nobody chose by minimising the difference.
    #
    # BUT ONLY WHEN EXACTLY ONE PAIRING FITS (review 4.3.18 r1, SF-1). A chart
    # that repeats its colours (every patch the same, or laid out the same
    # when turned half a turn) can agree with two orders on every patch, and
    # then the device values prove nothing about which `.txf` was measured:
    # taking the first one put 96 of 96 readings of an evenness sheet on the
    # wrong patch. Orders that agree AND put every reading on the same patch
    # are one pairing, and are fine. If none agrees, the result of the order
    # in force is returned, so the refusal is as before.
    results = [_against(c) for c in order.candidates()]
    fit = [m for m in results if m.verified]
    if not fit:
        return results[0]
    pairings = {tuple(m.order.sample_ids[int(s) - 1] for s in ids) for m in fit}
    if len(pairings) > 1:
        first = fit[0]
        return TurnedMatch(applies=True, verified=False, partial=partial,
                           compared=first.compared, mismatched=0,
                           worst=first.worst, order=first.order,
                           ambiguous=True,
                           fitting=tuple(m.order for m in fit))
    m = fit[0]
    return TurnedMatch(applies=True, verified=True, partial=partial,
                       compared=m.compared, mismatched=m.mismatched,
                       worst=m.worst, order=m.order,
                       fitting=tuple(x.order for x in fit))


def fits_straight_and_turned(measured, match: TurnedMatch) -> bool:
    """True when *measured*, which the ordinary check by ``SAMPLE_ID`` has
    already accepted, ALSO fits a turned order of the chart (*match*, from
    :func:`turned_match`) that would put some reading on another patch.

    Only a chart that repeats its colours can do that (an evenness sheet, say),
    and then nothing in the file says whether it was measured on ChromIQ's
    own layout or on the turned i1Profiler chart (review 4.3.18 r1, SF-1)."""
    if not match.applies or not match.fitting or measured is None:
        return False
    ids = [str(s).strip('"') for s in (measured.sample_ids or [])]
    for cand in match.fitting:
        try:
            if any(cand.sample_ids[int(s) - 1] != s for s in ids):
                return True
        except (ValueError, IndexError):
            continue
    return False


#: Header keyword stamped on a measurement paired through the turned order.
TURNED_KEYWORD = "CHROMIQ_PAIRED_BY_TURNED_ORDER"


def reorder_turned_measurement(ti3_path: "str | Path",
                               chart_ti2: "str | Path") -> int:
    """Give a turned measurement the chart's own ``SAMPLE_ID`` and
    ``SAMPLE_LOC`` on every row, in the chart's order. Rewrites the file IN
    PLACE (call it on the COPY) and returns the number of rows, or 0 when the
    file does not pair through the turned order (nothing is changed then)."""
    from core.text_io import read_text
    from workflow.measurement_pairing import _first_table
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    ti3_path, chart_ti2 = Path(ti3_path), Path(chart_ti2)
    try:
        measured = parse_ti3(ti3_path)
    except (Ti3ParseError, OSError):
        return 0
    m = turned_match(measured, chart_ti2)
    if not (m.applies and m.verified and not m.partial
            and m.order is not None):
        return 0
    text = read_text(ti3_path, lenient=True)
    t = _first_table(text)
    if t is None:
        return 0
    fields, rows = t
    if "SAMPLE_ID" not in fields:
        return 0
    sid_i = fields.index("SAMPLE_ID")
    loc_i = fields.index("SAMPLE_LOC") if "SAMPLE_LOC" in fields else None
    chart_pos = {r[0]: k for k, r in enumerate(_read_ti2(chart_ti2).rows)}
    new_rows = []
    for ln in rows:
        parts = ln.split()
        j = int(parts[sid_i].strip('"'))
        csid = m.order.sample_ids[j - 1]
        parts[sid_i] = csid
        if loc_i is not None:
            parts[loc_i] = f'"{m.order.locs[j - 1]}"'
        new_rows.append((chart_pos.get(csid, j), " ".join(parts)))
    new_rows.sort(key=lambda t: t[0])
    out, state = [], "head"
    for ln in text.splitlines():
        s = ln.strip()
        if state == "head":
            out.append(ln)
            if s == "BEGIN_DATA":
                out.extend(r for _k, r in new_rows)
                state = "data"
            continue
        if state == "data":
            if s == "END_DATA":
                out.append(ln)
                state = "tail"
            continue
        out.append(ln)
    at = 1 if out and out[0].strip().startswith("CTI3") else 0
    if TURNED_KEYWORD not in text:
        out[at:at] = [f'KEYWORD "{TURNED_KEYWORD}"',
                      f'{TURNED_KEYWORD} "{m.order.path.name}"']
    ti3_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(new_rows)
