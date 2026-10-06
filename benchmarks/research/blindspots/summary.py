"""Agent 23: per-builder summary of the H-test ramp families (sums and maxima).
    python -m benchmarks.research.blindspots.summary OUT NAME [NAME ...]"""
import json, re, sys
from pathlib import Path

FAM = [("H1", r"^H1\.(?P<v>[^.]+)\.", "grey sRGB"), ("H2", r"^H2\.(?P<v>.*-(?P<i>[prs]))\.", "colour ramps"),
       ("H3", r"^H3\.(?P<v>.*-(?P<i>[prs]))\.", "hue circles"), ("H4", r"^H4\.(?P<v>.*-(?P<i>[pr]))\.", "tinted/dark/light")]


def flat(d, pre=""):
    o = {}
    for k, v in d.items():
        kk = f"{pre}.{k}" if pre else k
        if isinstance(v, dict):
            o.update(flat(v, kk))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            o[kk] = v
    return o


def main():
    out = Path(sys.argv[1])
    for name in sys.argv[2:]:
        print(f"== {name}")
        for e in ("colprof", "fast", "accurate"):
            p = out / "hunt" / f"{name}-{e}.json"
            if not p.exists():
                continue
            f = flat(json.loads(p.read_text()))
            line = []
            for fam, rx, lab in FAM[1:]:
                for it in ("p", "r", "s"):
                    ks = [k for k in f if k.startswith(fam + ".") and re.search(rf"-{it}\.", k)]
                    if not ks:
                        continue
                    rev = sum(f[k] for k in ks if k.endswith(".l_rev"))
                    sw = max([f[k] for k in ks if k.endswith(".l_swing")] or [0])
                    jr = max([f[k] for k in ks if k.endswith("jump_ratio")] or [0])
                    d2 = max([f[k] for k in ks if k.endswith("d2_excess_max")] or [0])
                    hb = sum(f[k] for k in ks if k.endswith("hue_back_steps"))
                    line.append(f"{fam}{it}: rev {rev:.0f} swing {sw:.1f} jump {jr:.1f} d2 {d2:.1f}" + (f" hueback {hb:.0f}" if fam == "H3" else ""))
            print(f"  {e:9s} " + " | ".join(line))


main()
