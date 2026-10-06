"""Add v4_path to pre-seeded build records whose -v4 twin exists (preseed bug, fixed)."""
import json, sys
from pathlib import Path
f = Path(sys.argv[1]) / "builds.json"
b = json.loads(f.read_text())
n = 0
for x in b:
    if x.get("ok") and not x.get("v4_path"):
        v4 = Path(x["job"]["out"]).with_name(Path(x["job"]["out"]).stem + "-v4.icc")
        if v4.exists():
            x["v4_path"] = str(v4); n += 1
f.write_text(json.dumps(b, indent=1))
print(n, "fixed")
