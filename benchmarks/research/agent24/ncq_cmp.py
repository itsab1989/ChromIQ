"""ncq headline per dataset x reader x intent: base -> arm (Agent 14's referee on the mapped intents)."""
import json, sys
from pathlib import Path
run = Path(__file__).parent / "runs" / sys.argv[1]; arm = sys.argv[2]
keys = None
rows = []
for fb in sorted((run / "ncq").glob(f"*-{arm}-*.json")):
    pre, rd, it = fb.stem.rsplit("-", 2)
    tag = pre[: -len(arm) - 1]
    fa = run / "ncq" / f"{tag}-base-{rd}-{it}.json"
    if not fa.exists():
        continue
    a, b = json.loads(fa.read_text(encoding="utf-8")), json.loads(fb.read_text(encoding="utf-8"))
    if "headline" not in a or "headline" not in b:
        print("error", fb.name, a.get("error"), b.get("error")); continue
    a, b = a["headline"], b["headline"]
    keys = keys or [k for k in a if k in b]
    rows.append((tag, rd, it, a, b))
sel = [k for k in (keys or []) if "B2A" in k or "NC3" in k or "NC5" in k or "NC6" in k]
print("| dataset | reader | intent | " + " | ".join(sel) + " |")
for tag, rd, it, a, b in rows:
    print(f"| {tag} | {rd} | {it} | " + " | ".join(f"{a[k]:.2f} -> {b[k]:.2f}" for k in sel) + " |")
