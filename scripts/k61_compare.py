#!/usr/bin/env python3
"""K61: the SIMULATION half of `drive_k61_demo_thresholds.py`, and the
comparison of the two. Offscreen, data only: the same charts and sheets of
the demo pack through the same functions, no window.

    python scripts/k61_compare.py <pack> <on-screen json> <work> [out.txt]

A. every demo preset pair, `preset_eligibility.assess` under the set the
   drive used, against what the window on screen withheld;
B. the evenness rows of Report-Limits-Evenness run10 and run9, the report
   built by `build_report` and judged by `judge`, against the words the
   report window showed.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import make_verification_preset_demos as GEN                   # noqa: E402
from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402
from workflow import preset_eligibility as PE                  # noqa: E402

PRESET_FOLDER = "Create Chart presets (verification demos)"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    pack, shown, work = Path(argv[0]), Path(argv[1]), Path(argv[2])
    dest = Path(argv[3]) if len(argv) > 3 else None
    screen = json.loads(shown.read_text(encoding="utf-8"))
    lines, bad = [], 0
    lines.append("A. demo presets: window on screen vs simulation "
                 "(Full colour check)")
    folder = pack / PRESET_FOLDER
    for req, fail, ok in GEN.pairs():
        sid = req.judged_with or "custom_iso_12647_7"
        for side, demo in (("FAIL", fail), ("PASS", ok)):
            chart = folder / (GEN._sanitize(demo.name) + ".ti1")
            spec = GEN.layout(chart)
            PE.chart_row_values(chart, spec, lay_out=True)
            a = PE.assess(chart, MR.REPORT_TYPE_FULL, sid, recipe=spec)
            sim = dict(a.missing)
            on = (screen.get("presets") or {}).get(f"{req.key} {side}", {})
            same = sim == on.get("missing") and \
                sorted(a.answered) == sorted(on.get("answered") or [])
            bad += 0 if same else 1
            mine = {r: sim.get(r, "answered") for r in req.rows}
            lines.append(f"  {req.key} {side:4} {sid:20} "
                         f"{'SAME' if same else 'DIFFERENT'}  "
                         f"{len(a.answered)} of {len(a.asked)} answered; "
                         f"its rows: {mine}")
    lines.append("")
    lines.append("B. Report-Limits-Evenness: report on screen vs simulation "
                 "(build_report + judge on a copy)")
    proj = work / "Report-Limits-Evenness"
    shutil.rmtree(proj, ignore_errors=True)
    shutil.copytree(pack / "Report-Limits-Evenness", proj)
    for key, words in (screen.get("report") or {}).items():
        run, sid = key.split(" ")
        lim = CS.effective_limits(sid, {})
        ti3s = sorted((proj / "runs" / run / "verifications").glob("*/*.ti3"))
        sim = {}
        for t in ti3s:
            rep = MR.build_report(t, argyll_bin="/Applications/Argyll/bin")
            sim[t.parent.name] = {r["row_id"]: [r["word"], r.get("reason")]
                                  for r in MR.judge(rep, lim)
                                  if r["row_id"] in MR.EVENNESS_ROWS}
            ev = rep.get("evenness") or {}
            sim[t.parent.name]["noise"] = [ev.get("noise_pairwise_p95"),
                                           ev.get("noise_from_mean_p95")]
        shown_rows = [{r: v[:2] for r, v in w.items()}
                      for _k, w in sorted(words.items())]
        sim_rows = [{r: v for r, v in s.items() if r != "noise"}
                    for _k, s in sorted(sim.items())]
        same = shown_rows == sim_rows
        bad += 0 if same else 1
        lines.append(f"  {run} judged against {CS.SET_BY_ID[sid].label}: "
                     f"{'SAME' if same else 'DIFFERENT'}")
        for (vid, s), w in zip(sorted(sim.items()), shown_rows):
            lines.append(f"     {vid}: noise {s['noise'][0]} / {s['noise'][1]}"
                         f"; simulated {[s[r][0] for r in MR.EVENNESS_ROWS]}"
                         f", on screen {[w[r][0] for r in MR.EVENNESS_ROWS]}")
    lines.append("")
    lines.append(f"{bad} comparison(s) different.")
    text = "\n".join(lines) + "\n"
    if dest:
        dest.write_text(text, encoding="utf-8")
    print(text)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
