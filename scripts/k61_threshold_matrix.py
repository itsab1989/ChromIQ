#!/usr/bin/env python3
"""K61 (Knut, #182 5851645723): every requirement of every metric, one notch
either side of its line, asked of the presets WINDOW and of the REPORT, and
the two answers compared. A SIMULATION: the app's own functions run as data
computations, offscreen, no window. The on-screen half is
`drive_k61_presets_evenness.py` and `drive_k61_report_labels.py`.

    python scripts/k61_threshold_matrix.py <work-folder> [MATRIX.txt]

For each requirement of `make_verification_preset_demos.REQUIREMENTS` (R01 to
R19), both of its charts are:

* **asked of the window**: `preset_eligibility.assess`, report type Full
  colour check, under Custom ISO 12647-7 (the set that limits every row a
  chart can answer, the pack's STRICT choice) or the set the pair names
  (`Requirement.judged_with`), laid out by printtarg as the window lays a
  preset out;
* **measured and reported**: laid out by printtarg with the same arguments
  and seed, printed "perfectly" (every patch its aim) through a run whose
  profile is Argyll's sRGB, with the chart's patches given the residual the
  window's own estimate assumes (`EVENNESS_TYPICAL_SIGMA`, from
  `EVENNESS_SEED`, in the chart's own slot order) so the two routes see the
  same scatter, and the report built by `build_report` and judged by `judge`
  under the same limit set.

A row agrees when the window's answer (answered, or withheld with a code)
is the report's (a verdict word, or N-A with the same code). The noise rows
are compared too, with both noises printed: the window estimates on every
patch with 200 shuffles, the report measures on the patches within the
profile's gamut with 500, so near a line the two can part, and the table
says by how much.

Then the evenness noise line itself, for every numeric limit a set puts on
the two rows: the patches in a ninth the estimate needs, from ideal pages.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                             # noqa: E402

import make_verification_preset_demos as GEN                   # noqa: E402
from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402
from workflow import preset_eligibility as PE                  # noqa: E402
from workflow import preset_layout as PL                       # noqa: E402

ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
SRGB = ARGYLL.parent / "ref" / "sRGB.icm"


def _lay_out(ti1: Path, spec: dict, folder: Path, stem: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ti1, folder / f"{stem}.ti1")
    exe = Path(spec[PL.ARGYLL_BIN]) / "printtarg"
    r = subprocess.run([str(exe), *spec[PL.PRINTTARG_ARGV], stem],
                       cwd=str(folder), capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       timeout=PL.PRINTTARG_TIMEOUT_S)
    if r.returncode != 0:
        raise RuntimeError(r.stdout + r.stderr)
    return folder / f"{stem}.ti2"


def _sheet(ti2: Path, out: Path) -> Path:
    """Every patch its aim plus the scatter the window's estimate assumes,
    drawn the way `_estimated_evenness` draws it (one row per slot, in the
    grid's own order)."""
    from workflow.ti3_analysis import _lab_to_xyz_array, parse_ti3
    aims = MR._reference_labs(ti2)
    grid = MR.chart_grid(ti2)
    chart = parse_ti3(ti2)
    order = list(grid["slot"]) if "slot" in grid else list(chart.sample_ids)
    rng = np.random.default_rng(MR.EVENNESS_SEED)
    noise = dict(zip(order, rng.normal(0.0, MR.EVENNESS_TYPICAL_SIGMA,
                                       (len(order), 3))))
    rgb = MR._rgb_to_0_100(np.asarray(chart.rgb, float))
    rows = []
    for i, sid in enumerate(chart.sample_ids):
        if MR._is_padding_id(sid):
            continue      # printtarg's padding: printed, never read (B8-407)
        lab = np.asarray(aims[sid], float) + noise.get(sid, 0.0)
        lab[0] = min(lab[0], 100.0)
        x = _lab_to_xyz_array(lab[None])[0]
        rows.append(f"{sid} {rgb[i][0]:.4f} {rgb[i][1]:.4f} {rgb[i][2]:.4f} "
                    f"{x[0]:.5f} {x[1]:.5f} {x[2]:.5f}")
    out.write_text("\n".join([
        "CTI3", "", 'DESCRIPTOR "K61 threshold matrix (synthetic)"',
        'TARGET_INSTRUMENT "X-Rite i1Pro 2"', 'DEVICE_CLASS "OUTPUT"',
        'COLOR_REP "RGB_XYZ"', "", "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
        "", f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA", *rows, "END_DATA",
        ""]), encoding="utf-8")
    return out


def report_answer(ti1: Path, spec: dict, work: Path, set_id: str) -> dict:
    """``{row_id: (word, reason, value, noise)}`` of a real report of *ti1*
    measured as a verification in a run of its own."""
    import make_report_limit_demos as DEMO
    from core.file_manager import Project
    from workflow.ti3_analysis import mark_verification_ti3
    if work.exists():
        shutil.rmtree(work)
    proj = Project.create(work, "K61-Matrix")
    run = proj.current_run()
    run.ensure_dir()
    stem, vstem = run.stem, run.verify_stem
    _lay_out(ti1, spec, run.dir, stem)
    shutil.copy2(SRGB, run.dir / f"{stem}.icc")
    vti2 = _lay_out(ti1, spec, run.verifications_dir, vstem)
    v = run.verification("2026-11-01_100000")
    v.ensure_dir()
    ti3 = _sheet(vti2, v.dir / f"{vstem}.ti3")
    mark_verification_ti3(ti3)
    cdir = DEMO.snapshot(v.dir, vstem, run.verifications_dir)
    DEMO.write_print_record(cdir, vstem, "2026-11-01T10:00:00",
                            f"{stem}.icc", "through-profile")
    rep = MR.build_report(v.measurement_ti3, argyll_bin=ARGYLL)
    lim = CS.effective_limits(set_id, {})
    out = {}
    for row in MR.judge(rep, lim):
        out[row["row_id"]] = (row.get("word"), row.get("reason"),
                              row.get("value"))
    ev = rep.get("evenness") or {}
    return {"rows": out, "noise": {
        "uniformity_sd": ev.get("noise_pairwise_p95"),
        "uniformity_de00_max_from_mean": ev.get("noise_from_mean_p95")},
        "n_even": ev.get("n_patches"), "counts": ev.get("counts"),
        "split": (rep.get("gamut_split") or {}).get("n_in")}


def window_answer(ti1: Path, spec: dict, tid: str, sid: str) -> dict:
    PE.chart_row_values(ti1, spec, lay_out=True)
    a = PE.assess(ti1, tid, sid, recipe=spec)
    v = PE.chart_row_values(ti1, spec)
    return {"asked": a.asked, "missing": dict(a.missing),
            "noise": {rid: (v.get(rid) or {}).get("noise_p95")
                      for rid in MR.EVENNESS_ROWS},
            "counts": dict(a.noise_counts)}


def _cell_window(w: dict, rid: str) -> str:
    if rid not in w["asked"]:
        return "not asked"
    why = w["missing"].get(rid)
    return f"withheld {why}" if why else "answered"


def _cell_report(r: dict, rid: str) -> str:
    row = r["rows"].get(rid)
    if row is None:
        return "not in report"
    word, why, _v = row
    if word == "N-A" or (word == "INFO" and why):
        return f"N-A {why}"
    return f"{word}"


def _agree(wc: str, rc: str) -> bool:
    if wc == "not asked" or rc == "not in report":
        return wc == "not asked" and rc in ("not in report", "INFO")
    if wc == "answered":
        return not rc.startswith("N-A")
    return rc == "N-A " + wc.split(" ", 1)[1]


#: reasons the report gives a sheet that the window, asking before anything
#: is printed, cannot give (`MR.AFTER_PRINTING_REASONS`, the reference rows)
_ALWAYS_APART = {MR.REASON_NEEDS_REFERENCE_FILE}


def noise_lines() -> "list[str]":
    """The patches in a ninth the estimate needs, per numeric limit: the
    window's model (B8-1451, `preset_eligibility.model_need`, one count for
    every chart), and beside it the first ideal page whose REPORT shuffle,
    on a typical print's residuals, reads under the line."""
    out = []
    lims = sorted({(rid, CS.effective_limits(s.id, {})[rid].number)
                   for s in CS.SETS for rid in MR.EVENNESS_ROWS
                   if CS.effective_limits(s.id, {}).get(rid) is not None
                   and CS.effective_limits(s.id, {})[rid].is_numeric})
    table = {}
    for n in (9, 12, 15, 18, 21, 24, 27, 30, 36, 42, 45, 48, 54, 60, 75, 90):
        g = MR.evenness_grid_from_layout([n], n, n * n,
                                         coverage=[{"coverage": 0.8}])
        rng = np.random.default_rng(MR.EVENNESS_SEED)
        b = MR.evenness_from_residuals(
            g, rng.normal(0, MR.EVENNESS_TYPICAL_SIGMA, (n * n, 3)),
            shuffles=MR.EVENNESS_ESTIMATE_SHUFFLES)
        table[n] = (min(b["counts"]), b["noise_pairwise_p95"],
                    b["noise_from_mean_p95"])
    for rid, limit in lims:
        key = 1 if rid == "uniformity_sd" else 2
        first = next(((n, t) for n, t in sorted(table.items())
                      if t[key] < limit), None)
        sets = ", ".join(s.id for s in CS.SETS
                         if (CS.effective_limits(s.id, {}).get(rid) or
                             CS.Limit.none()).is_numeric
                         and CS.effective_limits(s.id, {})[rid].number == limit)
        need = PE.model_need(MR.EVENNESS_ROWS[rid], limit)
        model = (f"the window's model needs the ninths to count as {need} "
                 f"(noise {PE.model_noise(MR.EVENNESS_ROWS[rid], need):.3f}, "
                 f"{PE.model_noise(MR.EVENNESS_ROWS[rid], need - 1):.3f} "
                 f"at {need - 1}); ")
        if first:
            n, t = first
            out.append(f"  {PE.row_label(rid)} at {limit:g} ({sets}): "
                       + model + f"the report's shuffle: first ideal page "
                       f"below the line {n} by {n}, {t[0]} patches in a "
                       f"ninth, {n * n} on the page (noise {t[key]:.3f})")
        else:
            out.append(f"  {PE.row_label(rid)} at {limit:g} ({sets}): "
                       + model + "the report's shuffle: no ideal page up to "
                       "90 by 90 is below it")
    return out


STRICT_SET = "custom_iso_12647_7"

#: Knut's case (#182 5851645723): the i1Pro one-page presets he selected.
KNUT_SLUGS = ("i1_w75_a4_648p_1page_portrait_w7_5mm",
              "i1_w75_letter_648p_1page_portrait_w7_5mm",
              "i1_w75max_letter_783p_1page_portrait_w7_5mm_maximised_no_clip_border",
              "i1_w75max_a4_837p_1page_portrait_w7_5mm_maximised_no_clip_border")


def knuts_presets() -> "list[str]":
    """The window's answer on Knut's presets, the pairwise row, per set."""
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import KNUT_PRESETS
    out = ["KNUT'S CASE: the window on the one-page i1Pro presets, "
           "Full colour check, the two evenness rows", ""]
    for slug in KNUT_SLUGS:
        p = next(x for x in KNUT_PRESETS if x.slug == slug)
        chart = Path(resource_path(p.ti1_asset))
        recipe = dict(p.layout_recipe)
        ev = PE._estimated_evenness(chart, recipe, True)
        out.append(f"  {slug}: {PE.patch_count(chart)} patches, page "
                   f"{ev.get('pages')}, covered {ev.get('coverage')}, "
                   f"patches in each ninth {ev.get('counts')}")
        for sid in ("chromiq_default", "custom_iso_12647_7", "iso_12647_7",
                    "iso_12647_8"):
            a = PE.assess(chart, MR.REPORT_TYPE_FULL, sid, recipe=recipe)
            v = PE.chart_row_values(chart, recipe)
            lim = CS.effective_limits(sid, {})
            bits = []
            for rid in MR.EVENNESS_ROWS:
                why = dict(a.missing).get(rid)
                c = a.noise_count(rid)
                bits.append(
                    f"{'pairwise' if rid == 'uniformity_sd' else 'from mean'}"
                    f" noise {v[rid].get('noise_p95')} vs limit "
                    f"{lim[rid].number:g}: "
                    + (f"withheld {why}" if why else "answered")
                    + (f" (the ninths count as {c.have} over {c.pages} "
                       f"page(s), {c.low} to {c.high}; the limit needs "
                       f"{c.need})" if c else ""))
            out.append(f"     {CS.SET_BY_ID[sid].label:34} "
                       f"{len(a.answered)} of {len(a.asked)}; "
                       + "; ".join(bits))
        out.append("")
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    work = Path(argv[0]).resolve()
    dest = Path(argv[1]) if len(argv) > 1 else None
    presets = work / "presets"
    GEN.build(presets)
    lines = ["K61 THRESHOLD MATRIX (SIMULATION: the app's own functions, "
             "offscreen, no window)", ""]
    faults = 0
    for req, fail, ok in GEN.pairs():
        tid, sid = MR.REPORT_TYPE_FULL, (req.judged_with or STRICT_SET)
        lines.append(f"{req.key}  {req.metric}")
        lines.append(f"     requirement: {req.text}")
        lines.append(f"     line: {req.comparison}")
        lines.append(f"     window and report: Full colour check, judged "
                     f"against {CS.SET_BY_ID[sid].label}")
        for side, demo in (("just below (FAIL)", fail), ("just above (PASS)", ok)):
            ti1 = presets / (GEN._sanitize(demo.name) + ".ti1")
            spec = GEN.layout(ti1)
            w = window_answer(ti1, spec, tid, sid)
            r = report_answer(ti1, spec, work / "project", sid)
            for rid in req.rows:
                wc, rc = _cell_window(w, rid), _cell_report(r, rid)
                ok_ = _agree(wc, rc)
                want = (f"withheld {req.reason}" if demo is fail
                        else "answered")
                right = wc == want
                faults += 0 if (ok_ and right) else 1
                noise = ""
                if rid in MR.EVENNESS_ROWS:
                    noise = (f"  [noise window {w['noise'].get(rid)} "
                             f"report {r['noise'].get(rid)}; report counted "
                             f"{r['n_even']} patches]")
                lines.append(
                    f"     {side:18} {PE.row_label(rid)[:48]:48} window: "
                    f"{wc:40} report: {rc:40} "
                    f"{'AGREE' if ok_ else 'DIFFER'}"
                    f"{'' if right else '  WINDOW NOT AS DESIGNED'}{noise}")
            others = [rid for rid in w["asked"] if rid not in req.rows
                      and w["missing"].get(rid) not in _ALWAYS_APART]
            apart = [rid for rid in others
                     if not _agree(_cell_window(w, rid), _cell_report(r, rid))]
            lines.append(f"     {'':18} the other {len(others)} rows asked: "
                         f"{len(others) - len(apart)} agree"
                         + (f", apart: {', '.join(apart)}" if apart else ""))
        lines.append("")
    lines += knuts_presets()
    lines.append("EVENNESS NOISE LINE, per limit (the window's estimate, "
                 "ideal pages, a typical print):")
    lines += noise_lines()
    lines.append("")
    lines.append(f"{faults} cell(s) not as designed or not agreeing.")
    text = "\n".join(lines) + "\n"
    if dest:
        dest.write_text(text, encoding="utf-8")
    print(text)
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
