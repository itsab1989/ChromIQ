"""Agent 23: one line per dataset x builder with the headline number of each
defect found (F-15..F-18), from OUT/hunt/*.json.

    python -m benchmarks.research.blindspots.dtable OUT [NAME ...]
"""
import json
import sys
from pathlib import Path


def g(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def row(r):
    h2 = r.get("H2", {})
    rel = [v for k, v in h2.items() if k.endswith("-r") and isinstance(v, dict)]
    ps = [v for k, v in h2.items() if k[-2:] in ("-p", "-s") and isinstance(v, dict)]
    f15 = (g(r, "H11", "r", "dL_max", default=float("nan")),
           sum(v.get("l_rev", 0) for v in rel),
           max([v.get("jump_ratio", 0) for v in rel] or [0]),
           sum(v.get("new_edges", 0) for k, v in g(r, "H6", "r", default={}).items()))
    f16 = (sum(v.get("l_rev", 0) for v in ps), max([v.get("l_swing", 0) for v in ps] or [0]))
    f17 = (g(r, "H5", "sRGB_blue-r", "ipt_hue_shift", default=float("nan")),
           g(r, "H8", "r", "oog_clip_ipt_hue_blue_mean", default=float("nan")))
    f18 = (g(r, "H1", "p", "l_swing", default=float("nan")),
           g(r, "H1", "p", "chroma_max", default=float("nan")),
           g(r, "H1", "s", "l_swing", default=float("nan")))
    return (f"F15 paleL {f15[0]:5.1f} rev {f15[1]:4.0f} jump {f15[2]:6.1f} edges {f15[3]:4.0f} | "
            f"F16 p/s rev {f16[0]:3.0f} swing {f16[1]:4.1f} | "
            f"F17 blue {f17[0]:5.1f} oogblue {f17[1]:5.1f} | "
            f"F18 greyP swing {f18[0]:4.1f} C {f18[1]:4.1f} greyS {f18[2]:4.1f}")


def main():
    out = Path(sys.argv[1])
    names = sys.argv[2:] or sorted({p.stem.rsplit("-", 1)[0] for p in (out / "hunt").glob("*.json")})
    for n in names:
        for e in ("colprof", "fast", "accurate"):
            p = out / "hunt" / f"{n}-{e}.json"
            if p.exists():
                print(f"{n:18s} {e:9s} {row(json.loads(p.read_text(encoding="utf-8")))}")


if __name__ == "__main__":
    main()
