"""(3b) The runner: every chart x printer x fault, replayed through the
Measure tab's judging (:mod:`judge`), with a report per case and a summary.

    python -m tests.neighbour_campaign.run_campaign                # the matrix
    python -m tests.neighbour_campaign.run_campaign --charts i1-0200 --faults glitch
    python -m tests.neighbour_campaign.run_campaign --seeds 1 2 3 --jobs 8
    python -m tests.neighbour_campaign.run_campaign --buffer 15     # another buffer

Per case (``results/<tag>/cases.jsonl``):

* ``affected`` / ``affected_big``: patches the fault moved ≥ 1 / ≥ 10 ΔE;
* ``caught`` (reading faults): affected patches red when the last strip is
  read, and of them ``caught_big``; ``by_limit``: red by the limit rule (95);
  ``by_read_twice``: strips "Was a strip read twice?" asked about;
* ``flagged`` (print faults): affected patches red - the sheet really looks
  like that, so these turn yellow on re-read; listed, not scored;
* ``false_red``: red patches the fault did not touch;
* ``when``: for each caught patch, after how many FURTHER strips (patches,
  patch by patch) it turned red: 0 = as its own strip was read;
* ``reread``: every strip with a red outline read again (a misread gone, a
  print fault still there): how the red ones ended (``clean``, ``yellow``,
  ``still_red``) and what was newly red;
* ``summary_end`` / ``summary_after``: what the closing window's neighbour
  line would list (``neighbour_summary_facts``), before and after re-reads.

``results/<tag>/summary.md`` is the table for Knut.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from tests.neighbour_campaign.chart import list_charts, load_chart
from tests.neighbour_campaign.common import RESULTS, neighbour_module
from tests.neighbour_campaign.faults import FAULTS
from tests.neighbour_campaign.judge import TabEmulator
from tests.neighbour_campaign.printers import PRINTER_PLAN
from tests.neighbour_campaign.simulate import simulate, write_case

_NB = None


def _nb():
    global _NB
    if _NB is None:
        _NB = neighbour_module()
    return _NB


def run_case(chart_name, printer, fault, seed=1, *, buffer=10.0,
             write=False) -> dict:
    t0 = time.monotonic()
    chart = load_chart(chart_name)
    case = simulate(chart, printer, fault, seed)
    if write:
        write_case(case)
    mod, commit = _nb()
    emu = TabEmulator(chart, buffer=buffer, nb_mod=mod)
    c = chart
    loc_i = c.index()
    read = {loc: case.read_xyz[i] for i, loc in enumerate(c.locs)}
    reread = {loc: case.reread_xyz[i] for i, loc in enumerate(c.locs)}
    first_red: dict = {}
    red_curve = []
    twice = []
    wrong_strip = (case.fault.startswith("wrong_strip")
                   and case.notes.get("strip"))
    if c.mode == "strip":
        steps = c.strip_order
        for k, s in enumerate(steps):
            m = c.strip_members()[s]
            found = emu.read_strip(s, {c.locs[i]: read[c.locs[i]] for i in m})
            if found is not None:
                real = (s == wrong_strip)
                choice = "reread" if real else "keep"
                twice.append({"strip": s, "like": found.like,
                              "median": round(found.median_de76, 3),
                              "real": real, "choice": choice, "after": k})
                emu.read_twice_log.append((s, found.like, choice))
                if real:
                    emu.read_strip(s, {c.locs[i]: reread[c.locs[i]] for i in m})
            outl = emu.outlines()
            red = [l for l, o in outl.items() if o == "red"]
            red_curve.append(len(red))
            for l in red:
                first_red.setdefault(l, k)
        own = {loc: steps.index(c.strips[loc_i[loc]]) for loc in c.locs}
    else:
        for k, loc in enumerate(c.locs):
            emu.read_patch(loc, read[loc])
            outl = emu.outlines()
            red = [l for l, o in outl.items() if o == "red"]
            if k % max(1, c.n // 50) == 0 or k == c.n - 1:
                red_curve.append(len(red))
            for l in red:
                first_red.setdefault(l, k)
        own = {loc: k for k, loc in enumerate(c.locs)}
    end = emu.outlines()
    red_end = sorted(l for l, o in end.items() if o == "red")
    facts_end = emu.summary_facts()
    suspects_end = emu.suspects()
    # ---- re-read every strip (patch) with a red outline -----------------------
    if c.mode == "strip":
        again = [s for s in c.strip_order
                 if any(c.strips[loc_i[l]] == s for l in red_end)]
        for s in again:
            m = c.strip_members()[s]
            emu.read_strip(s, {c.locs[i]: reread[c.locs[i]] for i in m})
    else:
        again = list(red_end)
        for loc in again:
            emu.read_patch(loc, reread[loc])
    after = emu.outlines()
    facts_after = emu.summary_facts()

    aff = case.affected
    big = {l for l, v in aff.items() if v["de"] >= 10}
    red_set = set(red_end)
    # A strip "Was a strip read twice?" asked about and the user re-read
    # counts as caught: its wrong readings were replaced while measuring.
    by_twice = {l for t in twice if t["real"]
                for l in (c.locs[i] for i in c.strip_members()[t["strip"]])}
    hit = (red_set | (by_twice if case.target == "reading" else set())) & set(aff)
    false_red = red_set - set(aff)
    when = sorted(first_red[l] - own[l] for l in hit if l in first_red)
    fate = defaultdict(int)
    for l in red_end:
        o = after.get(l, "")
        fate["clean" if not o else "still_red" if o == "red" else "yellow"] += 1
    newly = sorted(l for l, o in after.items() if o == "red" and l not in red_set)
    out = {
        "chart": chart_name, "printer": printer, "fault": fault, "seed": seed,
        "family": FAULTS[fault].family, "target": case.target, "mode": c.mode,
        "patches": c.n, "strips": len(c.strip_order), "buffer": buffer,
        "affected": len(aff), "affected_big": len(big),
        "red_end": len(red_end),
        "caught": len(hit) if case.target == "reading" else None,
        "caught_big": len(hit & big) if case.target == "reading" else None,
        "flagged": len(hit) if case.target == "print" else None,
        "false_red": len(false_red),
        "false_red_locs": sorted(false_red)[:20],
        "missed_big": sorted(big - red_set)[:20] if case.target == "reading" else [],
        "by_limit": len(emu.by_limit & set(aff)),
        "read_twice": twice,
        "caught_by_read_twice": len(by_twice & set(aff)),
        "when": when, "red_curve": red_curve,
        "reread": {"units": len(again), **fate, "newly_red": newly[:20]},
        "suspects_end": len(suspects_end),
        "summary_end": facts_end, "summary_after": facts_after,
        "notes": case.notes, "nb_commit": commit[:10],
        "seconds": round(time.monotonic() - t0, 2),
    }
    if out["summary_end"]:
        for k in ("red", "kept"):
            out["summary_end"][k] = out["summary_end"][k][:30]
            out["summary_after"][k] = out["summary_after"][k][:30]
    return out


def _job(args):
    try:
        return run_case(*args[:4], buffer=args[4])
    except Exception as exc:   # noqa: BLE001 — one case never stops the matrix
        import traceback
        return {"chart": args[0], "printer": args[1], "fault": args[2],
                "seed": args[3], "error": f"{exc}",
                "trace": traceback.format_exc()[-1500:]}


def matrix(charts, printers, faults, seeds):
    jobs = []
    for ch in charts:
        mode = "patch" if ch.startswith("cr30") else "strip"
        for pr in printers:
            for f in faults:
                if mode not in FAULTS[f].modes:
                    continue
                for s in seeds:
                    jobs.append((ch, pr, f, s))
    return jobs


def _pct(a, b):
    return "-" if not b else f"{100.0 * a / b:.0f}%"


def summarize(rows: list) -> str:
    ok = [r for r in rows if "error" not in r]
    errs = [r for r in rows if "error" in r]
    L = ["# Neighbour check campaign: summary", "",
         f"{len(ok)} cases ({len(errs)} errors). Neighbour check from "
         f"`{ok[0]['nb_commit'] if ok else '?'}`, buffer "
         f"{ok[0]['buffer'] if ok else '?'}; limit 95, strip fence on. "
         "Red = at the end of the pass, before any re-read.", ""]
    # per fault, all charts and printers together
    L += ["## Per fault (all charts, printers, seeds)", "",
          "| fault | kind | cases | affected | caught (all) | caught (≥10 ΔE) "
          "| read-twice asked | false red / case | turned red: own strip / later "
          "| after re-read: clean / yellow / still red |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    by_fault = defaultdict(list)
    for r in ok:
        by_fault[r["fault"]].append(r)
    for f in FAULTS:
        rs = by_fault.get(f)
        if not rs:
            continue
        aff = sum(r["affected"] for r in rs)
        big = sum(r["affected_big"] for r in rs)
        tgt = rs[0]["target"]
        hit = sum((r["caught"] if tgt == "reading" else r["flagged"]) or 0 for r in rs)
        hitb = sum(r["caught_big"] or 0 for r in rs) if tgt == "reading" else None
        asked = sum(len(r["read_twice"]) for r in rs)
        fr = sum(r["false_red"] for r in rs) / len(rs)
        w = [x for r in rs for x in r["when"]]
        w0 = sum(1 for x in w if x == 0)
        clean = sum(r["reread"].get("clean", 0) for r in rs)
        yel = sum(r["reread"].get("yellow", 0) for r in rs)
        still = sum(r["reread"].get("still_red", 0) for r in rs)
        label = "misread" if tgt == "reading" else f"{rs[0]['family']} (real)"
        caught = (f"{hit}/{aff} {_pct(hit, aff)}" if tgt == "reading"
                  else f"flagged {hit}/{aff} {_pct(hit, aff)}")
        L.append(f"| {f} | {label} | {len(rs)} | {aff} | {caught} | "
                 + (f"{hitb}/{big} {_pct(hitb, big)}" if hitb is not None else "-")
                 + f" | {asked} | {fr:.2f} | {w0} / {len(w) - w0} | "
                 f"{clean} / {yel} / {still} |")
    # per chart size for the misreads
    L += ["", "## Misreads by chart (caught ≥10 ΔE / affected ≥10 ΔE; false red per case)",
          ""]
    charts = sorted({r["chart"] for r in ok}, key=lambda c: (c.split("-")[0], c))
    mis = [f for f in FAULTS if FAULTS[f].target == "reading"]
    L.append("| chart | " + " | ".join(mis) + " | false red (none) |")
    L.append("|---" * (len(mis) + 2) + "|")
    for ch in charts:
        cells = []
        for f in mis:
            rs = [r for r in ok if r["chart"] == ch and r["fault"] == f]
            if not rs:
                cells.append("n/a")
                continue
            hb = sum(r["caught_big"] or 0 for r in rs)
            b = sum(r["affected_big"] for r in rs)
            cells.append(f"{hb}/{b}")
        rn = [r for r in ok if r["chart"] == ch and r["fault"] == "none"]
        fr = (sum(r["false_red"] for r in rn) / len(rn)) if rn else float("nan")
        L.append(f"| {ch} | " + " | ".join(cells) + f" | {fr:.2f} |")
    # per printer, clean measurement
    L += ["", "## Clean measurements (fault `none`): red outlines per case, by printer", "",
          "| printer | cases | red per case | max | patches judged (checked/total) |",
          "|---|---|---|---|---|"]
    for pr in PRINTER_PLAN:
        rs = [r for r in ok if r["printer"] == pr and r["fault"] == "none"]
        if not rs:
            continue
        reds = [r["false_red"] for r in rs]
        chk = sum((r["summary_end"] or {}).get("checked", 0) for r in rs)
        tot = sum((r["summary_end"] or {}).get("total", 0) for r in rs)
        L.append(f"| {pr} | {len(rs)} | {np.mean(reds):.2f} | {max(reds)} | "
                 f"{_pct(chk, tot)} |")
    if errs:
        L += ["", "## Errors", ""] + [f"- {e['chart']} {e['printer']} {e['fault']}: "
                                      f"{e['error']}" for e in errs]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--charts", nargs="*")
    ap.add_argument("--printers", nargs="*")
    ap.add_argument("--faults", nargs="*")
    ap.add_argument("--seeds", nargs="*", type=int, default=[1])
    ap.add_argument("--buffer", type=float, default=10.0)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 4))
    ap.add_argument("--tag", default="")
    ap.add_argument("--write-cases", action="store_true",
                    help="also write each case's .ti3, replay and truth")
    a = ap.parse_args(argv)
    charts = a.charts or list_charts()
    printers = a.printers or list(PRINTER_PLAN)
    faults = a.faults or list(FAULTS)
    jobs = [j + (a.buffer,) for j in matrix(charts, printers, faults, a.seeds)]
    tag = a.tag or f"buffer{a.buffer:g}"
    out = RESULTS / tag
    out.mkdir(parents=True, exist_ok=True)
    _nb()          # copy the module once, before the workers start
    t0 = time.monotonic()
    rows = []
    with open(out / "cases.jsonl", "w") as fh:
        if a.jobs > 1:
            with ProcessPoolExecutor(a.jobs) as ex:
                for r in ex.map(_job, jobs, chunksize=1):
                    rows.append(r)
                    fh.write(json.dumps(r) + "\n")
                    fh.flush()
        else:
            for j in jobs:
                r = _job(j)
                rows.append(r)
                fh.write(json.dumps(r) + "\n")
    if a.write_cases:
        for j in jobs:
            write_case(simulate(*j[:4]))
    (out / "summary.md").write_text(summarize(rows))
    print(f"{len(rows)} cases in {time.monotonic() - t0:.0f} s -> {out}")
    print((out / "summary.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
