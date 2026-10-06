"""Agent 24, F-05: all runs' cmp-<arm>-vs-base.json in one D-17 style table.

    python aggregate.py f05 p1,p2,p3,p4   (run compare_f05.py per run first)

Cells = dataset x reader x intent; per property BETTER / WORSE / TIE; every WORSE row listed with
its size; safety properties marked. Also the headline numbers per dataset (Argyll, perceptual)."""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_f05 import PROPS, SAFETY   # noqa: E402

arm, runs = sys.argv[1], sys.argv[2].split(",")
R = Path(__file__).parent / "runs"
rows = []
for r in runs:
    f = R / r / f"cmp-{arm}-vs-base.json"
    if f.exists():
        rows += [dict(x, run=r) for x in json.loads(f.read_text(encoding="utf-8"))]
tally = defaultdict(lambda: defaultdict(int))
for x in rows:
    if "verdict" in x:
        tally[x["prop"]][x["verdict"]] += 1
cells = {(x["tag"], x["reader"], x["intent"]) for x in rows if "verdict" in x}
print(f"{arm} vs base: {len(cells)} cells ({len({c[0] for c in cells})} datasets x readers x intents)")
print("| property | BETTER | WORSE | TIE |\n|---|---|---|---|")
for p in PROPS:
    t = tally[p]
    print(f"| {p}{' (safety)' if p in SAFETY else ''} | {t['BETTER']} | {t['WORSE']} | {t['TIE']} |")
print("\nWORSE rows (dataset, reader, intent, property, base -> arm):")
for x in rows:
    if x.get("verdict") == "WORSE":
        print(f"  {x['tag']:30s} {x['reader']:9s} {x['intent']} {x['prop']:22s} "
              f"{x['a']:.3f} -> {x['b']:.3f}{'  SAFETY' if x['prop'] in SAFETY else ''}")
errs = [x for x in rows if "error" in x]
print("errors:", len(errs), errs[:3])
