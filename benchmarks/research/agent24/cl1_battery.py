"""Agent 24, C-L1 under protocol v3: E1 (A2B vs the 1 nm truth on the battery's 20,000 Halton
points, metrics.eval_device) for each profile as built (L0) and with C-L1b applied, under
Argyll, lcms, lcms-app and ColorSync. Paired bootstrap rows, decided by stats3 with the measured
seed SD, D-17 weighed adoption.

    python cl1_battery.py points <out_dir> <profile.icc> ...   # per-point arrays (one process)
    python cl1_battery.py decide <out_dir> [--variant b|scale]
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parent))
sys.path.insert(0, str(H))
import a24stats                                          # noqa: E402  (puts score/ on sys.path)
from benchmarks.research import cmm, colour, metrics     # noqa: E402
from benchmarks.research.printers import build_printers  # noqa: E402
from benchmarks.research.stats3 import ink_class         # noqa: E402
import l1_probe                                           # noqa: E402

READERS = ("argyll", "lcms", "lcms-app", "colorsync")
PAT = re.compile(r"(S\d|X\d+m?|XK[HB])-(?:seed\d+-)?(typical|pessimistic)(?:-s\d+)?-?([a-z]+\d+)?")


def points(out: Path, profs, variant="b"):
    pr = build_printers()
    out.mkdir(parents=True, exist_ok=True)
    l1_probe.VARIANT = variant
    for p in map(Path, profs):
        if p.name.startswith("v3-R-"):
            real_points(out, p, variant)
            continue
        m = PAT.search(p.name)
        if not m:
            print("skip (name)", p.name)
            continue
        pid, level, chart = m.group(1), m.group(2), (m.group(3) or "targen900")
        tag = f"{p.parent.parent.name}--{p.stem}"
        f = out / f"{tag}.{variant}.npz"
        if f.exists():
            continue
        prn = pr[pid]
        var = out / f"{tag}.{variant}.icc"
        l1_probe.make_l1(p, var)
        dev = metrics.eval_device(prn.n, prn.is_additive, prn.tac, 20000)
        truth = prn.lab_rel(dev)
        arr = {}
        for rd in READERS:
            for nm, path in (("a", p), ("b", var)):
                if rd == "colorsync" and not cmm.colorsync_supported(str(path)):
                    continue
                arr[f"{rd}.{nm}"] = colour.de2000(cmm.a2b(path, dev, rd), truth)
        np.savez_compressed(f, **arr)
        meta = {"pid": pid, "level": level, "chart": re.sub(r"\d+", "", chart),
                "n": prn.n, "rep": prn.color_rep, "src": str(p)}
        f.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
        cs = arr.get("colorsync.a"), arr.get("colorsync.b")
        print(f"{p.name}: colorsync med {np.median(cs[0]) if cs[0] is not None else 'n/a'} -> "
              f"{np.median(cs[1]) if cs[1] is not None else 'n/a'}; argyll identical "
              f"{np.array_equal(arr['argyll.a'], arr['argyll.b'])}", flush=True)


def real_points(out: Path, p: Path, variant: str):
    """Real held-out sets: A2B at the held-out patches against their measurement."""
    from benchmarks.research import datasets as dsm
    name = re.search(r"v3-(R-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*?)-base", p.name).group(1)
    tag = f"{p.parent.parent.name}--{p.stem}"
    f = out / f"{tag}.{variant}.npz"
    if f.exists():
        return
    d = dsm.real(name, out.parent / "realwork" / name)
    var = out / f"{tag}.{variant}.icc"
    l1_probe.make_l1(p, var)
    arr = {}
    for rd in READERS:
        for nm, path in (("a", p), ("b", var)):
            if rd == "colorsync" and not cmm.colorsync_supported(str(path)):
                continue
            arr[f"{rd}.{nm}"] = colour.de2000(cmm.a2b(path, d.holdout_device, rd), d.holdout_lab)
    np.savez_compressed(f, **arr)
    f.with_suffix(".json").write_text(json.dumps({"pid": name, "level": "real", "chart": "real",
                                                  "n": d.n_channels, "rep": d.color_rep,
                                                  "src": str(p)}), encoding="utf-8")
    print(f"{p.name}: colorsync med {np.median(arr['colorsync.a']):.4f} -> "
          f"{np.median(arr['colorsync.b']):.4f}", flush=True)


def decide(out: Path, variant="b"):
    rows = []
    for f in sorted(out.glob(f"*.{variant}.npz")):
        meta = json.loads(f.with_suffix(".json").read_text(encoding="utf-8"))
        z = np.load(f)
        for rd in READERS:
            if f"{rd}.a" not in z:
                continue
            for st in ("median", "mean", "p95"):
                rows.append(a24stats.row(
                    z[f"{rd}.a"], z[f"{rd}.b"], dataset=f"{meta['pid']}#{f.stem.split('--')[0]}",
                    level=meta["level"], chart=meta["chart"], reader=rd, endpoint=f"a2b.{st}",
                    ink_class=ink_class(meta["n"], meta["rep"]), n_channels=meta["n"],
                    kind="real" if meta["level"] == "real" else "synthetic"))
    rows, adoption = a24stats.decide(rows)
    (out / f"rows-{variant}.json").write_text(json.dumps(rows, indent=1, default=float), encoding="utf-8")
    (out / f"adoption-{variant}.json").write_text(json.dumps(adoption, indent=1, default=float), encoding="utf-8")
    print(a24stats.summary(rows, adoption))
    by = {}
    for r in rows:
        by.setdefault((r["reader"], r["endpoint"]), []).append(r)
    print("| reader | endpoint | rows | BETTER | TIE | WORSE | median diff | largest loss |")
    for (rd, ep), rr in sorted(by.items()):
        v = [r["verdict_per_printer_endpoint"] for r in rr]
        d = [r["diff"] for r in rr]
        print(f"| {rd} | {ep} | {len(rr)} | {v.count('BETTER')} | {v.count('TIE')} | "
              f"{v.count('WORSE')} | {np.median(d):+.4f} | {max(d):+.4f} |")


if __name__ == "__main__":
    cmd, out = sys.argv[1], Path(sys.argv[2])
    var = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "b"
    if cmd == "points":
        points(out, [a for a in sys.argv[3:] if a.endswith(".icc")], var)
    else:
        decide(out, var)
