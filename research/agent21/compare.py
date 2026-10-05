"""Table of score.json files: python compare.py FILE.icc ... (markdown rows)."""
import json, sys
from pathlib import Path
cols = [("pale med", lambda s: s["pale"]["med"]), ("pale p95", lambda s: s["pale"]["p95"]),
        ("jumps", lambda s: s["ncq"]["NC5 visible jumps"]), ("step p99", lambda s: s["ncq"]["NC5 step ratio p99"]), ("max d2", lambda s: s["ncq"]["NC5 max d2"]),
        ("<=3 B2A med", lambda s: s["ncq"]["NC2 <=3 inks B2A med"]), ("<=3 B2A p95", lambda s: s["ncq"]["NC2 <=3 inks B2A p95"]),
        ("hue med", lambda s: s["ncq"]["NC3 hue-circle B2A med"]), ("hue p95", lambda s: s["ncq"]["NC3 hue-circle B2A p95"]),
        ("all B2A med", lambda s: s["ncq"]["NC2 all inks B2A med"]),
        ("own med", lambda s: s["own"]["printed_med"]), ("own p95", lambda s: s["own"]["printed_p95"]),
        ("ext<2", lambda s: s["ncq"]["NC4 ext within 2"]), ("compl", lambda s: s["ncq"]["NC3 complementary share"]),
        ("grey extra", lambda s: s["ncq"]["NC3 grey extra ink max"]), ("rise-fall", lambda s: s["ncq"]["NC3 rise-fall excess"]),
        ("inks max", lambda s: s["ncq"]["NC3 inks on max"]), ("<=3 A2B p95", lambda s: s["ncq"]["NC2 <=3 inks A2B p95"]),
        ("all A2B med", lambda s: s["ncq"]["NC2 all inks A2B med"]), ("ramp p95", lambda s: s["ncq"]["NC1 ramp A2B p95"]),
        ("solid max", lambda s: s["ncq"]["NC1 solid B2A max"]), ("TAC", lambda s: s["ncq"]["NC6 TAC max"]),
        ("grey dE", lambda s: s["neutral"]["de_med"]), ("grey C*max", lambda s: s["neutral"]["chroma_max"]),
        ("grey TVx", lambda s: s["neutral"]["tv_excess"]), ("black L*", lambda s: s["neutral"]["black_L"]),
        ("L rev", lambda s: s["neutral"]["L_reversals"])]
print("| profile | " + " | ".join(c for c, _ in cols) + " |")
print("|---" * (len(cols) + 1) + "|")
for f in sys.argv[1:]:
    p = Path(f + ".score.json") if not f.endswith(".json") else Path(f)
    if not p.exists():
        print(f"| {f} | (no score) |"); continue
    s = json.loads(p.read_text())
    name = "/".join(Path(f).parts[-2:]).replace(".icc", "")
    vals = []
    for _, fn in cols:
        try:
            v = fn(s); vals.append(f"{v:.2f}" if isinstance(v, float) else str(v))
        except Exception:
            vals.append("-")
    print(f"| {name} | " + " | ".join(vals) + " |")
