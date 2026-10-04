"""(3b) The runner: every chart x printer x fault x seed, replayed through the
Measure tab's judging (:mod:`judge`, the product modules of this tree), with a
report per case and a summary.

    python -m tests.neighbour_campaign.run_campaign                # the matrix
    python -m tests.neighbour_campaign.run_campaign --charts i1-0200 --faults glitch
    python -m tests.neighbour_campaign.run_campaign --seeds 1 2 3 --jobs 8
    python -m tests.neighbour_campaign.run_campaign --buffer 15     # another buffer

THE MATRIX. Three kinds of chart (``judge.TabEmulator`` ``kind``):

* every estimated profiling chart (i1Pro strips 80..4200, CR30 spot and
  honeycomb 80..1000) x the 4 printers;
* every chart MADE FROM A PROFILE (``pc-<printer>-i1-*``, targen -c with that
  printer's rough profile) x its own printer only;
* VERIFICATIONS: the i1Pro charts up to 1000 and the CR30 spot 80 used as
  verification sheets (``v:<chart>``), judged against the printer's run
  profile's prediction at limit 10, no fence, no neighbour check.

Per case (``results/<tag>/cases.jsonl``), besides the first run's figures:

* ``red_by``: every patch red at the end of the pass, split by the rule that
  made it: ``limit`` (the limit with the strip fence), ``neighbour``, ``both``,
  for the patches the fault touched (``hit_by``) and for the ones it did not
  (``false_by``); ``fence_hid``: patches past the limit that the strip fence
  kept from red; ``caught_by_read_twice``: patches of a strip "Was a strip
  read twice?" asked about and the user re-read;
* ``when`` / ``when_frac``: after how many further strips a caught patch
  turned red, and where in the pass (0..1);
* ``reread``: every strip (patch) with a red outline read again, and how its
  red patches ended: ``green`` (a corrected misread, Knut 5984277558),
  ``yellow`` (the same colour again: real), ``still_red``, ``none``; split
  for misread patches and for print-fault patches;
* ``rule_breaks``: a neighbour suspect drawn yellow by similar patches or a
  learned range before its own re-read (Knut 5984174575 forbids it), a
  print-fault patch turned green, a misread turned yellow;
* ``summary_end`` / ``summary_after``: the closing window's misread lines
  (``judge.TabEmulator.misread_summary``, English), before and after the
  re-reads; for a verification they must be empty.
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
from tests.neighbour_campaign.common import CHARTS, RESULTS, neighbour_module
from tests.neighbour_campaign.faults import FAULTS
from tests.neighbour_campaign.judge import TabEmulator
from tests.neighbour_campaign.printers import PRINTER_PLAN
from tests.neighbour_campaign.simulate import simulate, write_case

_NB = None
#: The charts used as verification sheets.
VERIFY_CHARTS = ("i1-0080", "i1-0200", "i1-0500", "i1-1000", "cr30-spot-0080")


def _nb():
    global _NB
    if _NB is None:
        _NB = neighbour_module()
    return _NB


def chart_kind(name: str) -> "tuple[str, str]":
    """``(kind, chart)`` of a matrix chart name."""
    if name.startswith("v:"):
        return "verification", name[2:]
    info = json.loads((CHARTS / name / "chart.json").read_text())
    return info.get("kind", "estimated"), name


def size_class(n: int) -> str:
    return "small" if n <= 250 else "medium" if n <= 1100 else "large"


def run_case(chart_name, printer, fault, seed=1, *, buffer=10.0) -> dict:
    t0 = time.monotonic()
    kind, base = chart_kind(chart_name)
    chart = load_chart(base)
    case = simulate(chart, printer, fault, seed)
    mod, commit = _nb()
    exp = None
    if kind == "verification":
        from tests.neighbour_campaign.profiles import predicted_xyz
        exp = predicted_xyz(chart, printer)
    emu = TabEmulator(chart, kind=kind, buffer=buffer, nb_mod=mod,
                      expected_xyz=exp)
    c = chart
    loc_i = c.index()
    read = {loc: case.read_xyz[i] for i, loc in enumerate(c.locs)}
    reread = {loc: case.reread_xyz[i] for i, loc in enumerate(c.locs)}
    first_red: dict = {}
    first_reason: dict = {}
    twice = []
    wrong_strip = (case.fault.startswith("wrong_strip")
                   and case.notes.get("strip"))
    breaks = defaultdict(int)
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
                    emu.set_aside(s)
                    emu.read_strip(s, {c.locs[i]: reread[c.locs[i]] for i in m})
                else:
                    emu.keep(s)
            outl = emu.outlines()
            for l, o in outl.items():
                if o == "red" and l not in first_red:
                    first_red[l] = k
                    first_reason[l] = emu.red_reason(l)
        own = {loc: steps.index(c.strips[loc_i[loc]]) for loc in c.locs}
        n_units = len(steps)
    else:
        for k, loc in enumerate(c.locs):
            emu.read_patch(loc, read[loc])
            for l, o in emu.outlines().items():
                if o == "red" and l not in first_red:
                    first_red[l] = k
                    first_reason[l] = emu.red_reason(l)
        own = {loc: k for k, loc in enumerate(c.locs)}
        n_units = len(c.locs)
    end = emu.outlines()
    red_end = sorted(l for l, o in end.items() if o == "red")
    reason_end = {l: emu.red_reason(l) for l in red_end}
    suspects_end = emu.suspects()
    for l in suspects_end:
        if end.get(l) in ("yellow_peer", "yellow_learned"):
            breaks["neighbour_suspect_yellow_without_reread"] += 1
    facts_end = emu.summary_facts()
    text_end = emu.misread_summary(read_twice_active=c.mode == "strip")
    yellow_end = defaultdict(int)
    for l, o in end.items():
        if o.startswith("yellow"):
            yellow_end[o] += 1
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
    text_after = emu.misread_summary(read_twice_active=c.mode == "strip")

    aff = case.affected
    big = {l for l, v in aff.items() if v["de"] >= 10}
    red_set = set(red_end)
    by_twice = {l for t in twice if t["real"]
                for l in (c.locs[i] for i in c.strip_members()[t["strip"]])}
    hit = (red_set | (by_twice if case.target == "reading" else set())) & set(aff)
    false_red = red_set - set(aff)
    hit_by, false_by = defaultdict(int), defaultdict(int)
    for l in red_end:
        (hit_by if l in aff else false_by)[reason_end[l]] += 1
    when = sorted(first_red[l] - own[l] for l in hit if l in first_red)
    when_frac = sorted(round(first_red[l] / max(1, n_units - 1), 3)
                       for l in hit if l in first_red)
    first_by = defaultdict(int)
    for l in hit:
        if l in first_reason:
            first_by[first_reason[l]] += 1
    fate = {"misread": defaultdict(int), "print": defaultdict(int),
            "untouched": defaultdict(int)}
    for l in red_end:
        o = after.get(l, "")
        res = ("green" if o == "green" else "still_red" if o == "red"
               else "yellow" if o.startswith("yellow") else "none")
        # A patch "Was a strip read twice?" already had re-read holds its
        # true colour now: no longer a misread.
        grp = ("untouched" if l not in aff or l in by_twice else
               "misread" if case.target == "reading" else "print")
        fate[grp][res] += 1
        if grp == "print" and res == "green":
            breaks["print_fault_turned_green"] += 1
        if grp == "misread" and res == "yellow":
            breaks["misread_turned_yellow"] += 1
    newly = sorted(l for l, o in after.items() if o == "red" and l not in red_set)
    if kind == "verification" and (text_end or text_after):
        breaks["verification_has_summary"] += 1
    out = {
        "chart": chart_name, "base": base, "kind": kind, "printer": printer,
        "fault": fault, "seed": seed,
        "family": FAULTS[fault].family, "target": case.target, "mode": c.mode,
        "patches": c.n, "size": size_class(c.n),
        "strips": len(c.strip_order), "buffer": buffer, "limit": emu.limit,
        "affected": len(aff), "affected_big": len(big),
        "red_end": len(red_end),
        "caught": len(hit) if case.target == "reading" else None,
        "caught_big": len(hit & big) if case.target == "reading" else None,
        "flagged": len(hit) if case.target == "print" else None,
        "false_red": len(false_red),
        "false_red_locs": sorted(false_red)[:20],
        # Red at some moment of the pass on a patch the fault did not touch,
        # but no longer red at its end (judged early with few comparisons, or
        # turned yellow by a confirmation): a red the user sees for a while.
        "transient_false": len([l for l in first_red
                                if l not in aff and l not in red_set]),
        "transient_false_by": {k: sum(1 for l, why in first_reason.items()
                                      if l not in aff and l not in red_set
                                      and why == k)
                               for k in ("limit", "neighbour", "both")},
        "hit_by": dict(hit_by), "false_by": dict(false_by),
        "first_red_by": dict(first_by),
        "fence_hid": len(emu.fence_hid), "fence_hid_affected": len(emu.fence_hid & set(aff)),
        "missed_big": sorted(big - hit)[:20] if case.target == "reading" else [],
        "by_limit": len(emu.by_limit & set(aff)),
        "by_neighbour": len(emu.by_neighbour & set(aff)),
        "read_twice": twice,
        "caught_by_read_twice": len(by_twice & set(aff)),
        "when": when, "when_frac": when_frac,
        "yellow_end": dict(yellow_end),
        "reread": {"units": len(again),
                   **{g: dict(v) for g, v in fate.items()},
                   "newly_red": newly[:20], "n_newly_red": len(newly)},
        "rule_breaks": dict(breaks),
        "suspects_end": len(suspects_end),
        "summary_end": facts_end, "summary_after": facts_after,
        "text_end": text_end, "text_after": text_after,
        "notes": case.notes, "nb_commit": commit[:16],
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
        kind, base = chart_kind(ch)
        info = json.loads((CHARTS / base / "chart.json").read_text())
        mode = "patch" if info["instrument"] == "CR30" else "strip"
        for pr in printers:
            if kind == "accurate" and info.get("printer") != pr:
                continue
            for f in faults:
                if mode not in FAULTS[f].modes:
                    continue
                for s in seeds:
                    jobs.append((ch, pr, f, s))
    return jobs


def all_charts() -> list:
    base = list_charts()
    return base + [f"v:{c}" for c in VERIFY_CHARTS if c in base]


def _pct(a, b):
    return "-" if not b else f"{100.0 * a / b:.0f}%"


def summarize(rows: list) -> str:
    """The tables, also written by ``report.py`` with more detail."""
    from tests.neighbour_campaign.report import tables
    return tables(rows)


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
    charts = a.charts or all_charts()
    printers = a.printers or list(PRINTER_PLAN)
    faults = a.faults or list(FAULTS)
    jobs = [j + (a.buffer,) for j in matrix(charts, printers, faults, a.seeds)]
    tag = a.tag or f"buffer{a.buffer:g}"
    out = RESULTS / tag
    out.mkdir(parents=True, exist_ok=True)
    # The predictions once, before the workers start (xicclu per chart).
    from tests.neighbour_campaign.profiles import predicted_xyz
    for ch in {j[0] for j in jobs if j[0].startswith("v:")}:
        for pr in printers:
            predicted_xyz(ch[2:], pr)
    t0 = time.monotonic()
    rows = []
    print(f"{len(jobs)} cases, {a.jobs} jobs -> {out}", flush=True)
    with open(out / "cases.jsonl", "w") as fh:
        if a.jobs > 1:
            with ProcessPoolExecutor(a.jobs) as ex:
                for r in ex.map(_job, jobs, chunksize=2):
                    rows.append(r)
                    fh.write(json.dumps(r) + "\n")
                    fh.flush()
                    if len(rows) % 500 == 0:
                        print(f"  {len(rows)} done, {time.monotonic() - t0:.0f} s",
                              flush=True)
        else:
            for j in jobs:
                r = _job(j)
                rows.append(r)
                fh.write(json.dumps(r) + "\n")
    if a.write_cases:
        for j in jobs:
            write_case(simulate(chart_kind(j[0])[1], *j[1:4]))
    (out / "summary.md").write_text(summarize(rows))
    print(f"{len(rows)} cases in {time.monotonic() - t0:.0f} s -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
