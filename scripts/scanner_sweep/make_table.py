#!/usr/bin/env python3
"""Regenerate TABLE.md from the sweep's results — never hand-edited."""
import json, sys
from pathlib import Path

res = Path(sys.argv[1] if len(sys.argv) > 1
           else "/private/tmp/agentJ/out/results.json")
out = Path(sys.argv[2] if len(sys.argv) > 2
           else "/Users/Basti/Desktop/beta 8/11-regression-sweep/TABLE.md")
rows = json.loads(res.read_text(encoding="utf-8"))
rows.sort(key=lambda r: r["id"])
n = {"PASS": 0, "FAIL": 0, "UNTESTED": 0}
for r in rows:
    n[r["status"]] = n.get(r["status"], 0) + 1
L = [f"# Per-function result table — {len(rows)} checks, "
     f"{n.get('PASS',0)} PASS / {n.get('FAIL',0)} FAIL / "
     f"{n.get('UNTESTED',0)} UNTESTED", "",
     "Generated from the sweep's own `results.json` by "
     "`script/make_table.py`. Every row carries the evidence it was judged on, "
     "not a bare verdict.", "",
     "| id | function | status | what was measured |", "|---|---|---|---|"]
for r in rows:
    note = r["note"].replace("|", "\\|").replace("\n", "<br>")
    L.append(f"| {r['id']} | {r['name']} | **{r['status']}** | {note} |")
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote", out, len(rows), "rows")
