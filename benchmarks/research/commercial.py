"""Commercial reference profiles against ours, with confidence intervals
(protocol v3, B4; Agent 16).

Agent 11 compared Adobe's reference profiles with ours on the battery's
held-out patches and called the candidate "level with Adobe" (Agent 13 7.8:
no interval, 158-161 patches, and Adobe saw every patch while our builders
did not). This module scores both on the SAME held-out patches, absolute
colorimetric (Adobe uses XYZ-scaling relative colorimetry, so absolute is the
convention-free readout), and gives the paired difference of the median,
the MEAN and the p95 with a 95 % paired-bootstrap interval. Every table
states who saw which patches:

* reference profile: IN-SAMPLE (built from all the data, held-out patches
  included);
* our builds: OUT-OF-SAMPLE (built from the training split only).

A second table repeats it on the TRAINING patches, where both are in-sample.
Neither split is a fair test of generalisation (a smoothing reference loses
in-sample to a near-interpolating fit by construction); the fair test, the
same raw chart through a commercial builder scored on an independent
re-print, is not available (Agent 11).

    python -m benchmarks.research.commercial RUN_DIR [--engines accurate,colprof]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from benchmarks.research import colour, datasets as dsm, metrics
from benchmarks.research.stats import paired_bootstrap

ADOBE = Path("/Library/Application Support/Adobe/Color/Profiles/Recommended")
# real set -> (reference profile, who made it, reader)
REFERENCES = {
    "R-FOGRA39L": (ADOBE / "CoatedFOGRA39.icc", "Adobe (CoatedFOGRA39)", "argyll"),
    "R-GRACoL2006": (ADOBE / "CoatedGRACoL2006.icc", "Adobe (CoatedGRACoL2006)", "argyll"),
    "R-SWOP2006C3": (ADOBE / "WebCoatedSWOP2006Grade3.icc", "Adobe (WebCoatedSWOP2006Grade3)", "argyll"),
    "R-SWOP2006C5": (ADOBE / "WebCoatedSWOP2006Grade5.icc", "Adobe (WebCoatedSWOP2006Grade5)", "argyll"),
}
STATS = ("median", "mean", "p95")


def _reference(name: str):
    if name in REFERENCES:
        return REFERENCES[name]
    ref = dsm.reference_icc(name) if hasattr(dsm, "reference_icc") else None
    if ref is not None and ref.exists():
        who = {"R-FOGRA55": "ColorLogic CoPrA (Fogra reference)",
               "R-APTEC7C": "Kodak (ICC registry)"}.get(name, "published reference")
        reader = "lcms" if ref.read_bytes()[8] >= 4 else "argyll"
        return ref, who, reader
    return None


def absolute_lab(prof, device: np.ndarray, reader: str) -> np.ndarray:
    """Absolute colorimetric A2B (D50, perfect-diffuser white)."""
    if reader == "argyll":
        inp = "\n".join(" ".join(f"{v:.7f}" for v in r) for r in device) + "\n"
        out = subprocess.run(["/Applications/Argyll/bin/icclu", "-v0", "-ff", "-ia", "-pl",
                              str(prof)], input=inp, capture_output=True, text=True,
                             encoding="utf-8", timeout=900, check=True).stdout
        return np.array([[float(x) for x in ln.split()[:3]] for ln in out.splitlines()
                         if ln.strip()])
    # lcms, absolute intent (3), float formats, tables as written
    from benchmarks.research import cmm
    lib = cmm._lcms()
    n, additive = cmm._profile_n(Path(prof))
    dfmt, dscale = cmm._dev_fmt(n, additive)
    hp = lib.cmsOpenProfileFromFile(str(prof).encode(), b"r")
    hl = lib.cmsCreateLab4Profile(None)
    t = lib.cmsCreateTransform(hp, dfmt, hl, cmm._fmt(10, 3), 3, cmm._NOOPT | cmm._NOCACHE)
    src = np.ascontiguousarray(device * dscale, dtype=np.float64)
    dst = np.zeros((len(device), 3))
    lib.cmsDoTransform(t, src.ctypes.data, dst.ctypes.data, len(device))
    lib.cmsDeleteTransform(t)
    lib.cmsCloseProfile(hp)
    lib.cmsCloseProfile(hl)
    return dst


def training_patches(ds):
    """(device, absolute Lab) of the training split the builders saw."""
    text = Path(ds.ti3).read_text(encoding="utf-8", errors="replace")
    fields, rows, _ = dsm._ti3_table(text)
    vals = dsm._parse_rows(fields, rows)
    xc = [fields.index(k) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
    dc = [i for i, f in enumerate(fields) if "_" in f and not f.startswith(("XYZ", "SPEC", "LAB"))
          and f != "SAMPLE_ID"][:ds.n_channels]
    dev = np.array([[float(v[i]) for i in dc] for v in vals]) / 100.0
    xyz = np.array([[float(v[i]) for i in xc] for v in vals])
    return dev, colour.xyz_to_lab(xyz)


def compare_one(ds, ours: dict, ref_spec, n_boot: int = 2000) -> dict:
    """ds: a real Dataset (with holdout_xyz); ours: {label: icc path}."""
    ref, who, reader = ref_spec
    lab_t = colour.xyz_to_lab(ds.holdout_xyz)
    de_ref = colour.de2000(absolute_lab(ref, ds.holdout_device, reader), lab_t)
    out = {"dataset": ds.name, "n_heldout": int(len(lab_t)), "reference": who,
           "reference_path": str(ref), "reference_sample": "IN-SAMPLE (built from all patches)",
           "ours_sample": "OUT-OF-SAMPLE (built from the training split)",
           "readout": "absolute colorimetric, dE00", "reference_stats": metrics.stats(de_ref),
           "ours": {}}
    for label, icc in ours.items():
        if icc is None or not Path(icc).exists():
            continue
        de = colour.de2000(absolute_lab(icc, ds.holdout_device, "argyll"
                                        if ds.n_channels <= 4 else "lcms"), lab_t)
        row = {"stats": metrics.stats(de), "diff_vs_reference": {}}
        for st in STATS:
            b = paired_bootstrap(de_ref, de, st, n_boot=n_boot)
            row["diff_vs_reference"][st] = {"ours_minus_reference": b["diff"],
                                            "ci95": b["ci95"], "p": b["p"]}
        out["ours"][label] = row
    # both in-sample: the training patches
    try:
        tdev, tlab = training_patches(ds)
        de_rt = colour.de2000(absolute_lab(ref, tdev, reader), tlab)
        out["training"] = {"n": int(len(tlab)), "reference": metrics.stats(de_rt), "ours": {}}
        for label, icc in ours.items():
            if icc is None or not Path(icc).exists():
                continue
            de = colour.de2000(absolute_lab(icc, tdev, "argyll" if ds.n_channels <= 4
                                            else "lcms"), tlab)
            b = paired_bootstrap(de_rt, de, "mean", n_boot=n_boot)
            out["training"]["ours"][label] = {"stats": metrics.stats(de),
                                              "mean_diff": b["diff"], "ci95": b["ci95"]}
    except Exception as exc:          # reported, never hidden
        out["training"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def table(rows: list[dict]) -> str:
    lines = ["| set (held-out n) | profile | who saw the held-out patches | median | mean | p95 | "
             "ours - reference: median [95 % CI] | mean [95 % CI] | p95 [95 % CI] |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        s = r["reference_stats"]
        lines.append(f"| {r['dataset']} ({r['n_heldout']}) | {r['reference']} | in-sample (all data) | "
                     f"{s['median']:.3f} | {s['mean']:.3f} | {s['p95']:.3f} | | | |")
        for label, o in r["ours"].items():
            s = o["stats"]
            cells = []
            for st in STATS:
                d = o["diff_vs_reference"][st]
                cells.append(f"{d['ours_minus_reference']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]")
            lines.append(f"| {r['dataset']} ({r['n_heldout']}) | {label} | OUT-of-sample (training split) | "
                         f"{s['median']:.3f} | {s['mean']:.3f} | {s['p95']:.3f} | " + " | ".join(cells) + " |")
    lines += ["", "Training patches (BOTH in-sample):", "",
              "| set (n) | profile | median | mean | p95 | ours - reference: mean [95 % CI] |",
              "|---|---|---|---|---|---|"]
    for r in rows:
        t = r.get("training") or {}
        if "reference" not in t:
            continue
        s = t["reference"]
        lines.append(f"| {r['dataset']} ({t['n']}) | {r['reference']} | {s['median']:.3f} | "
                     f"{s['mean']:.3f} | {s['p95']:.3f} | |")
        for label, o in t["ours"].items():
            s = o["stats"]
            lines.append(f"| {r['dataset']} ({t['n']}) | {label} | {s['median']:.3f} | {s['mean']:.3f} | "
                         f"{s['p95']:.3f} | {o['mean_diff']:+.3f} [{o['ci95'][0]:+.3f}, {o['ci95'][1]:+.3f}] |")
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--engines", default="accurate,colprof,fast,argyll")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    run = Path(args.run_dir)
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    rows = []
    for d in res["datasets"]:
        if d["kind"] != "real":
            continue
        spec = _reference(d["name"])
        if spec is None or not Path(spec[0]).exists():
            continue
        ds = dsm.real(d["name"], run / "work" / "commercial" / d["name"])
        ours = {}
        for e in args.engines.split(","):
            p = run / "profiles" / f"{d['suite']}-{d['name']}-{d['variant']}-{e}.icc"
            ours[e] = p if p.exists() else None
        rows.append(compare_one(ds, ours, spec))
    text = table(rows)
    print(text)
    out = Path(args.out) if args.out else run / "commercial.json"
    out.write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    out.with_suffix(".md").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
