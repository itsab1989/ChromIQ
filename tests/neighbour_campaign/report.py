"""(5) The campaign's tables from ``cases.jsonl``.

    python -m tests.neighbour_campaign.report <results dir>   # -> summary.md
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from tests.neighbour_campaign.faults import FAULTS

KIND_NAME = {"estimated": "profiling chart, estimated colours (limit 95)",
             "accurate": "chart made from a pre-conditioning profile (limit 20)",
             "verification": "verification against its profile (limit 10)"}


def _pct(a, b):
    return "-" if not b else f"{100.0 * a / b:.0f}%"


def _sum(rs, key, sub=None):
    t = 0
    for r in rs:
        v = r.get(key) or {}
        t += (v.get(sub, 0) if sub else v) or 0
    return t


def _fault_rows(rs_all, kind):
    L = ["| fault | family | cases | affected | caught (all) | caught ≥10 ΔE "
         "| red by limit / neighbour / both / read-twice | false red per case "
         "(limit / neighbour / both) | red in own strip / later | after re-read: "
         "green / yellow / still red |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    by_fault = defaultdict(list)
    for r in rs_all:
        if r["kind"] == kind:
            by_fault[r["fault"]].append(r)
    for f in FAULTS:
        rs = by_fault.get(f)
        if not rs:
            continue
        tgt = rs[0]["target"]
        aff = sum(r["affected"] for r in rs)
        big = sum(r["affected_big"] for r in rs)
        hit = sum((r["caught"] if tgt == "reading" else r["flagged"]) or 0 for r in rs)
        hitb = sum(r["caught_big"] or 0 for r in rs) if tgt == "reading" else None
        hb = {k: _sum(rs, "hit_by", k) for k in ("limit", "neighbour", "both")}
        tw = sum(r["caught_by_read_twice"] for r in rs) if tgt == "reading" else 0
        fb = {k: _sum(rs, "false_by", k) / len(rs) for k in ("limit", "neighbour", "both")}
        fr = sum(r["false_red"] for r in rs) / len(rs)
        w = [x for r in rs for x in r["when"]]
        w0 = sum(1 for x in w if x == 0)
        grp = "misread" if tgt == "reading" else "print"
        g = _sum([r["reread"] for r in rs], grp, "green")
        y = _sum([r["reread"] for r in rs], grp, "yellow")
        s = _sum([r["reread"] for r in rs], grp, "still_red")
        caught = (f"{hit}/{aff} {_pct(hit, aff)}" if tgt == "reading"
                  else f"flagged {hit}/{aff} {_pct(hit, aff)}")
        L.append(f"| {f} | {rs[0]['family']} | {len(rs)} | {aff} | {caught} | "
                 + (f"{hitb}/{big} {_pct(hitb, big)}" if hitb is not None else "-")
                 + f" | {hb['limit']} / {hb['neighbour']} / {hb['both']} / {tw}"
                 f" | {fr:.2f} ({fb['limit']:.2f} / {fb['neighbour']:.2f} / {fb['both']:.2f})"
                 f" | {w0} / {len(w) - w0} | {g} / {y} / {s} |")
    return L


def tables(rows: list) -> str:
    ok = [r for r in rows if "error" not in r]
    errs = [r for r in rows if "error" in r]
    kinds = [k for k in KIND_NAME if any(r["kind"] == k for r in ok)]
    commit = ok[0]["nb_commit"] if ok else "?"
    L = ["# Neighbour check campaign (final beta-11 code): summary", "",
         f"{len(ok)} cases ({len(errs)} errors). Product modules at `{commit}`, "
         f"buffer {ok[0]['buffer'] if ok else '?'}. Red = at the end of the "
         "pass, before any re-read. 'caught' counts a misread patch red at the "
         "end of the pass, or replaced because 'Was a strip read twice?' asked "
         "and the user re-read.", ""]
    for kind in kinds:
        L += [f"## {KIND_NAME[kind]}", ""] + _fault_rows(ok, kind) + [""]
    # misreads by chart
    mis = [f for f in FAULTS if FAULTS[f].target == "reading"]
    L += ["## Misreads by chart: caught ≥10 ΔE / affected ≥10 ΔE (all printers, seeds)", "",
          "| chart | kind | " + " | ".join(mis) + " | clean: false red per case |",
          "|---" * (len(mis) + 3) + "|"]
    charts = sorted({r["chart"] for r in ok},
                    key=lambda c: ({"estimated": 0, "accurate": 1,
                                    "verification": 2}[
                                        next(r["kind"] for r in ok if r["chart"] == c)],
                                   c.split("-")[0], c))
    for ch in charts:
        cells = []
        kind = next(r["kind"] for r in ok if r["chart"] == ch)
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
        L.append(f"| {ch} | {kind} | " + " | ".join(cells) + f" | {fr:.2f} |")
    # clean, by printer and kind, by rule
    L += ["", "## Clean measurements (fault `none`): red per case by rule", "",
          "| kind | printer | cases | red per case | by limit | by neighbour | both | max "
          "| red for a while, gone by the end (limit / neighbour) | patches checked |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for kind in kinds:
        for pr in sorted({r["printer"] for r in ok}):
            rs = [r for r in ok if r["printer"] == pr and r["fault"] == "none"
                  and r["kind"] == kind]
            if not rs:
                continue
            reds = [r["false_red"] for r in rs]
            fb = {k: _sum(rs, "false_by", k) / len(rs) for k in ("limit", "neighbour", "both")}
            chk = sum((r["summary_end"] or {}).get("checked", 0) for r in rs)
            tot = sum((r["summary_end"] or {}).get("total", 0) for r in rs)
            L.append(f"| {kind} | {pr} | {len(rs)} | {np.mean(reds):.2f} | "
                     f"{fb['limit']:.2f} | {fb['neighbour']:.2f} | {fb['both']:.2f} | "
                     f"{max(reds)} | "
                     f"{_sum(rs, 'transient_false_by', 'limit') / len(rs):.2f} / "
                     f"{(_sum(rs, 'transient_false_by', 'neighbour') + _sum(rs, 'transient_false_by', 'both')) / len(rs):.2f} | "
                     f"{_pct(chk, tot)} |")
    # timing
    L += ["", "## When a misread turns red (strips after its own; i1Pro charts)", "",
          "| fault | size | caught | own strip | 1-5 later | 6-20 later | >20 later | median place in the pass |",
          "|---|---|---|---|---|---|---|---|"]
    for f in mis:
        for size in ("small", "medium", "large"):
            rs = [r for r in ok if r["fault"] == f and r["size"] == size
                  and r["mode"] == "strip" and r["kind"] != "verification"]
            w = [x for r in rs for x in r["when"]]
            if not w:
                continue
            wf = [x for r in rs for x in r["when_frac"]]
            L.append(f"| {f} | {size} | {len(w)} | {sum(1 for x in w if x == 0)} | "
                     f"{sum(1 for x in w if 1 <= x <= 5)} | "
                     f"{sum(1 for x in w if 6 <= x <= 20)} | {sum(1 for x in w if x > 20)} | "
                     f"{np.median(wf):.2f} |")
    # rule checks
    br = defaultdict(int)
    for r in ok:
        for k, v in (r.get("rule_breaks") or {}).items():
            br[k] += v
    ver = [r for r in ok if r["kind"] == "verification"]
    L += ["", "## Rule checks (Knut 5984174575, 5984277558, item 5)", "",
          f"- neighbour suspects drawn yellow before their own re-read: "
          f"{br['neighbour_suspect_yellow_without_reread']}",
          f"- print-fault patches turned GREEN by a re-read (should be yellow): "
          f"{br['print_fault_turned_green']}",
          f"- misread patches turned YELLOW by a re-read (should be green): "
          f"{br['misread_turned_yellow']}",
          f"- verifications with a misread summary (should be none): "
          f"{br['verification_has_summary']} of {len(ver)}"]
    # summary states
    st = defaultdict(int)
    for r in ok:
        if r["kind"] == "verification":
            continue
        first = (r["text_end"] or "").split("\n")[0]
        key = ("none checked" if "none of the" in first else
               "no suspects" if "no suspected" in first else
               "suspects listed" if "suspected misread" in first else "other")
        st[key] += 1
    L += ["", "## The closing window's neighbour line at the end of the pass "
          "(profiling charts)", ""] + [f"- {k}: {v} cases" for k, v in sorted(st.items())]
    if errs:
        L += ["", "## Errors", ""] + [f"- {e['chart']} {e['printer']} {e['fault']}: "
                                      f"{e['error']}" for e in errs[:30]]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    d = Path((argv or sys.argv[1:])[0])
    rows = [json.loads(x) for x in (d / "cases.jsonl").read_text().splitlines() if x]
    (d / "summary.md").write_text(tables(rows))
    print((d / "summary.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
