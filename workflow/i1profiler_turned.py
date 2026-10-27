"""The "turned" i1Profiler export (beta): one ChromIQ sheet that i1Profiler can
measure as well, after a quarter turn.

WHAT IT IS FOR. ChromIQ's i1Profiler patch sets (``-i1profiler.txt/.pxf``)
hand i1Profiler the COLOURS only; i1Profiler always lays out a page of its own,
so a sheet printed by ChromIQ cannot be read in i1Profiler. This module writes
the patch list in the order that makes i1Profiler's ROWS equal ChromIQ's
STRIPS once the printed sheet is turned a quarter turn anticlockwise (strip A
at the bottom, the label end of every strip on the left), plus an i1Profiler
test-chart file (``.txf``) per device family that sets the page, the patch
size and the device in one step. One print can then be measured in both
programs.

Everything here comes from a study measured in i1Profiler 3.8.8 itself
(2026-10-26, ``ChromIQ-work/2026-10-26_i1profiler_layout/analysis.md``): 540 of
540 and 1080 of 1080 patches in the same place, worst colour difference 0 of
255. The physical read with a real instrument has NOT been tested yet.

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
PAGE_A4_H_MM = 210.06
BLOCK_TOP_MM = 24.5
BLOCK_BOTTOM_MM = 20.0

#: How far two patch lengths may differ and still count as one length, mm.
LENGTH_TOL_MM = 0.05

ORDER_VERSION = 1


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
    family_reasons: dict = field(default_factory=dict)  # family -> [reasons]
    order: list = field(default_factory=list)     # (sid, loc, vals) per entry
    rows: int = 0                                 # i1Profiler rows = strips
    columns: int = 0                              # = patches per strip
    patch_len_mm: float = 0.0
    strip_w_mm: float = 0.0
    row_strips: list = field(default_factory=list)  # (row, sheet, strip label)
    sheets: int = 1

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


def plan_for(ti2: "str | Path") -> TurnedPlan:
    """Decide whether *ti2* qualifies, and build the turned order if it does.

    Never raises for a chart it cannot use; every refusal is a plain sentence
    with the real numbers in it.
    """
    ti2 = Path(ti2)
    plan = TurnedPlan()
    facts = _read_ti2(ti2)
    layout, recipe = _read_layout(ti2)
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
    # The recipe's spacer_mode is what the build follows
    # (`LayoutRecipe.build_kwargs`: spacer_on = spacer_mode != "none").
    if str(recipe.get("spacer_mode", "colored")) != "none":
        plan.reasons.append(tr(
            "the chart has spacers between its patches; i1Profiler would "
            "count every spacer as a patch"))
    elif recipe.get("edge_spacers"):
        plan.reasons.append(tr(
            "the chart has spacers at the ends of its strips; i1Profiler "
            "would count them as patches"))
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
        lo, hi = window_mm(per, fam)
        wlo, whi, _hlo, _hhi = SLIDER[fam]
        if not (lo < plen <= hi):
            why.append(tr(
                "the patches are {len} mm long; with {per} patches per strip "
                "they must be longer than {lo} mm and at most {hi} mm, or "
                "i1Profiler puts a different number of patches on each "
                "row").format(len=f"{plen:.2f}", per=per,
                              lo=f"{lo:.2f}", hi=f"{hi:.2f}"))
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
        plan.family_reasons[fam] = why

    # The order: sheet by sheet, each sheet's strips from last to first (the
    # turned sheet shows its strip A at the bottom).
    pages = sorted({s.get("page", 0) for s in strips})
    row_of: dict[int, int] = {}
    r = 0
    for pg in pages:
        idx = [i for i, s in enumerate(strips) if s.get("page", 0) == pg]
        for si in reversed(idx):
            row_of[si] = r
            plan.row_strips.append(
                (r + 1, pages.index(pg) + 1, _strip_label(members[si][0]["loc"])))
            r += 1
    n_rows = len(strips)
    order: list = [None] * (per * n_rows)
    for si, m in enumerate(members):
        for c, p in enumerate(m):
            order[c * n_rows + row_of[si]] = facts.rows[facts.by_loc[p["loc"]]]
    plan.order = order
    plan.rows, plan.columns, plan.sheets = n_rows, per, len(pages)
    return plan


def design_settings(plan: TurnedPlan, family: str) -> dict:
    """i1Profiler's settings for *family*: patch width = ChromIQ's patch length,
    patch height = the strip width (held inside the slider), one tall page."""
    wlo, whi, hlo, hhi = SLIDER[family]
    pw = plan.patch_len_mm
    ph = min(max(plan.strip_w_mm, hlo), hhi)
    page_h = max(PAGE_A4_H_MM,
                 math.ceil(BLOCK_TOP_MM + plan.rows * ph + BLOCK_BOTTOM_MM))
    return {"patch_w_mm": pw, "patch_h_mm": ph,
            "patch_w_percent": (pw - wlo) / (whi - wlo) * 100,
            "patch_h_percent": (ph - hlo) / (hhi - hlo) * 100,
            "page_w_mm": PAGE_W_MM, "page_h_mm": float(page_h)}


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


def _write_txf(plan: TurnedPlan, family: str, out: Path, title: str) -> None:
    from workflow.i1profiler_export import Target, WorkflowOptions, write_pwxf
    d = design_settings(plan, family)
    tgt = Target("iRGB", "RGB", ["R", "G", "B"],
                 [(int(sid) if str(sid).isdigit() else i + 1, vals)
                  for i, (sid, _loc, vals) in enumerate(plan.order)])
    opt = WorkflowOptions(
        device=family, measurement_mode=1,
        paper_format=2 if d["page_h_mm"] <= PAGE_A4_H_MM else 0,
        paper_orientation="Landscape", page_width_mm=d["page_w_mm"],
        page_height_mm=d["page_h_mm"], columns=plan.columns, rows=plan.rows,
        pages=1, patch_w_mm=d["patch_w_mm"], patch_h_mm=d["patch_h_mm"],
        patch_w_percent=d["patch_w_percent"],
        patch_h_percent=d["patch_h_percent"], title=title)
    write_pwxf(tgt, out, title, opt)


def _order_doc(plan: TurnedPlan, ti2: Path) -> dict:
    return {
        "version": ORDER_VERSION,
        "what": "ChromIQ turned i1Profiler export: entry j of the i1Profiler "
                "patch list (1-based) is the chart patch named here",
        "chart": ti2.name, "chart_sha256": sha256_of(ti2),
        "patches": len(plan.order), "rows": plan.rows,
        "columns": plan.columns, "sheets": plan.sheets,
        "patch_length_mm": plan.patch_len_mm, "strip_width_mm": plan.strip_w_mm,
        "families": plan.families,
        "row_to_strip": [{"row": r, "sheet": s, "strip": lab}
                         for r, s, lab in plan.row_strips],
        "order": [{"sample_id": sid, "loc": loc} for sid, loc, _v in plan.order],
    }


def write_turned_export(ti2: "str | Path", out_dir: "str | Path",
                        stem: str) -> TurnedResult:
    """Write the turned export of *ti2* into *out_dir*, or a note saying why
    not. Best-effort: never raises."""
    res = TurnedResult()
    try:
        ti2, out_dir = Path(ti2), Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        res.removed = remove_stale(out_dir, stem)
        files = TurnedFiles(out_dir, stem)
        plan = plan_for(ti2)
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
        files.order.write_text(json.dumps(_order_doc(plan, ti2), indent=1),
                               encoding="utf-8")
        res.written.append(files.order)
        files.note.write_text(note_qualified(plan, ti2.name, files),
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

def note_qualified(plan: TurnedPlan, chart_name: str, files: TurnedFiles) -> str:
    """The plain-language note for a chart that qualifies.

    NO FILE STEM IN IT (review 4.3.17 r1). A project rename renames these
    files and the chart, and a note that named "Old.ti2" and
    "Old-i1profiler-turned.json" then sent the person looking for files that
    no longer existed. Every file is named by the ending it keeps whatever
    the project is called. *chart_name* is kept for the callers."""
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
        "in i1Profiler 3.8.8, but nobody has yet read such a sheet with a "
        "real instrument, or imported a real i1Profiler measurement of one. "
        "Please check the result before you rely on it."))
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
    parts.append(tr(
        "2. Turn the printed sheet a quarter turn ANTICLOCKWISE, so that the "
        "strip labels are on the LEFT and the sheet's first strip (strip A on "
        "sheet 1) is the BOTTOM row. Every ChromIQ strip is now one "
        "i1Profiler row, read from left to right."))
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
        "Measurement page and save the measurement in i1Profiler's own "
        "format, an .mxf file. Use the .mxf, not a CGATS text export: "
        "i1Profiler names the patches by its own rows and columns (its A1 "
        "is not ChromIQ's A1), and only the .mxf keeps the device values "
        "(the RGB values of the test-chart file) that ChromIQ needs to put "
        "every reading on its own patch. Leave i1Profiler's Scramble patches "
        "setting off. Measure the whole chart: ChromIQ brings a turned "
        "measurement back only when every patch has been read, and refuses "
        "a file that holds only part of the rows, saying how many readings "
        "it holds."))
    parts.append(tr(
        "8. To bring the measurement into ChromIQ: open this run, go to the "
        "Measure tab, press IMPORT, choose the .mxf file with the folder "
        "button beside Measurement File (from i1Profiler), and press Import "
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
        "for example a CGATS text export or a reading made with an i1iO "
        "through i1Profiler's measure tool, which ChromIQ otherwise pairs by "
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
        "chart replaces all of these files, and renaming the project renames "
        "them with it."))
    return "\n".join(parts) + "\n"


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
    parts.append("")
    parts.append(tr(
        "What qualifies: an RGB chart made by ChromIQ's layout engine for the "
        "i1Pro family, with no spacers, every strip full, and a patch length "
        "that gives exactly as many patches on one i1Profiler row as the "
        "strip has: 10 mm patches with 24 per strip qualify, for example. "
        "Only the i1Pro 2 and the i1Pro 3 can read it."))
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# The way back
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TurnedOrder:
    path: Path
    sample_ids: list        # chart SAMPLE_ID of i1Profiler entry j (index j-1)
    locs: list


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
    for p in candidates:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (doc.get("version") != ORDER_VERSION
                or doc.get("chart_sha256") != digest):
            continue
        order = doc.get("order") or []
        ids = [str(e.get("sample_id", "")) for e in order]
        locs = [str(e.get("loc", "")) for e in order]
        if ids and all(ids) and len(set(ids)) == len(ids):
            return TurnedOrder(p, ids, locs)
    return None


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
    diffs = []
    for mi, sid in enumerate(ids):
        di = by_id.get(order.sample_ids[int(sid) - 1])
        if di is None:
            return TurnedMatch(applies=True, order=order)
        diffs.append(float(np.abs(want[di] - got[mi]).max()))
    bad = sum(1 for d in diffs if d > PATCH_IDENTITY_TOL)
    return TurnedMatch(applies=True, verified=bad == 0, partial=partial,
                       compared=len(diffs), mismatched=bad,
                       worst=round(max(diffs), 4), order=order)


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
