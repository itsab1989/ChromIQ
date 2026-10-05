"""A vs B pale rows (and a few safety rows) from two battery results.json: python pale_table.py A B [reader]"""
import json, sys
A, B = sys.argv[1], sys.argv[2]; rd = sys.argv[3] if len(sys.argv) > 3 else "argyll"
ra, rb = json.load(open(f"{A}/results.json")), json.load(open(f"{B}/results.json"))
key = lambda d: (d["name"], d["variant"])
mb = {key(d): d for d in rb["datasets"]}
def g(d, *p):
    x = (d["profiles"].get("accurate") or {}).get("scores", {}).get(rd)
    for k in p:
        x = x.get(k) if isinstance(x, dict) else None
    return x
print(f"| set | chart | pale med A -> B | pale p95 A -> B | pale >2 A -> B | b2a p95 A -> B | neutral dE mean A -> B | black L* A -> B | jumps-ish d2 A -> B |")
print("|---|---|---|---|---|---|---|---|---|")
for d in ra["datasets"]:
    e = mb.get(key(d))
    if not e: continue
    f = lambda *p: (g(d, *p), g(e, *p))
    def s(t, fmt="{:.2f}"):
        a, b = t
        return "-" if a is None or b is None else f"{fmt.format(a)} -> {fmt.format(b)}"
    print(f"| {d['name']} | {d['variant']} | {s(f('b2a','pale_sample','median'))} | {s(f('b2a','pale_sample','p95'))} | "
          f"{s(f('b2a','pale_sample','share_gt2'))} | {s(f('b2a','all','p95'))} | {s(f('neutral','de','mean'))} | "
          f"{s(f('black','printed_L'))} | {s(f('neutral','banding_max_d2'))} |")
