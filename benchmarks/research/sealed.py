"""The SEALED confirmatory set of battery v3 (Agent 16, 2026-10-04).

Why. The X family was meant to be confirmatory, but it has shaped the
design for months (Agent 13, design challenge section 5.1): agent 5's misread
check, agent 3's anchor and ink gate, agent 9's candidate choice were all
set while looking at X. A design tuned to a printer family is not tested out
of sample by new noise on the same printers. Protocol v3 therefore makes
every known printer DEVELOPMENT and confirms only on printers nobody has
seen: drawn here from the Z family (:mod:`zfamily`, physics unlike S and X)
with a SECRET seed.

What is public (this file, ``zfamily.py``, ``charts.py``, the manifest):
the model, the parameter distributions, the slots (device type, chart, patch
count, noise level), and SHA-256 hashes of every drawn instance and every
measured chart. What is secret (``Validation/sealed/`` in the research
folder, outside the repository): the seed, the drawn parameters, the
measured charts.

Rules (also in ``Validation/sealed/README.md`` and protocol v3, section A):

* No agent that tunes the engine may read, build on or score the sealed set
  until the FINAL benchmark. The orchestrator unseals it
  (``python -m benchmarks.research.sealed unseal ...``), which writes an
  ``UNSEALED`` marker and a log line; ``run.py --suite sealed`` refuses to
  run without that marker.
* The generator can be reviewed without revealing the instances:
  ``preview`` draws instances from PUBLIC seeds (same code path, different
  seed) and prints their plausibility statistics; the tests do the same
  over many public seeds.
* ``verify`` regenerates everything from the seed and checks every hash
  against the manifest, so the instances cannot be changed after sealing
  without it showing.

    python -m benchmarks.research.sealed seal --out DIR          # once
    python -m benchmarks.research.sealed verify DIR [--manifest M]
    python -m benchmarks.research.sealed preview --seed 7 [--slots Z04,Z11]
    python -m benchmarks.research.sealed unseal DIR --by orchestrator --reason "FINAL"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path

import numpy as np

from benchmarks.research import colour
from benchmarks.research import zfamily as Z

SEALED_VERSION = "sealed-v1"
HERE = Path(__file__).resolve().parent
REPO_MANIFEST = HERE / "data" / "sealed_manifest.json"
DEFAULT_DIR = Path.home() / "develop" / "ProfileEngineResearch" / "Validation" / "sealed"
LEVELS = ("typical", "pessimistic")

# The slots: one printer instance each. Device type, paper class and the
# charts are public; everything physical is drawn from the secret seed.
# Charts follow protocol v3 C: targen at ChromIQ's defaults for every
# printer (a second, sparser count for RGB and CMYK), and Agent 14's
# ECG-composed chart beside it for 5+ inks. Counts are ChromIQ-typical
# (560 = one i1Pro A4 sheet; 1617 = the IT8.7/4 size multi-ink users print).
SLOTS = [
    {"id": "Z01", "device_rep": "RGB", "paper": "glossy", "charts": [("targen", 900), ("targen", 400)]},
    {"id": "Z02", "device_rep": "RGB", "paper": "matte", "charts": [("targen", 900)]},
    {"id": "Z03", "device_rep": "CMY", "paper": "any", "charts": [("targen", 900)]},
    {"id": "Z04", "device_rep": "CMYK", "paper": "glossy", "charts": [("targen", 900), ("targen", 400)]},
    {"id": "Z05", "device_rep": "CMYK", "paper": "matte", "charts": [("targen", 900)]},
    {"id": "Z06", "device_rep": "CMYK", "paper": "any", "charts": [("targen", 1617)]},
    {"id": "Z07", "device_rep": "CMYKcm", "paper": "any", "charts": [("targen", 1120)]},
    {"id": "Z08", "device_rep": "CMYKcmk", "paper": "any", "charts": [("targen", 1617)]},
    {"id": "Z09", "device_rep": "CMYKO", "paper": "any", "charts": [("targen", 1120), ("ecg", 1120)]},
    {"id": "Z10", "device_rep": "CMYKOG", "paper": "any", "charts": [("targen", 1617), ("ecg", 1617)]},
    {"id": "Z11", "device_rep": "CMYKOGV", "paper": "any", "charts": [("targen", 1617), ("ecg", 1617)]},
    {"id": "Z12", "device_rep": "CMYKRGB", "paper": "any", "charts": [("targen", 1617), ("ecg", 1617)]},
]
TAC_RANGE = {3: (240.0, 300.0), 4: (260.0, 340.0), 5: (280.0, 360.0),
             6: (280.0, 360.0), 7: (300.0, 380.0)}
# the generator files whose hashes the manifest records
GENERATOR_FILES = ("sealed.py", "zfamily.py", "charts.py", "noise.py", "colour.py",
                   "printers.py", "datasets.py")


# ---------------------------------------------------------------------------
# deterministic derivation from the seed
# ---------------------------------------------------------------------------

def _sub(seed: bytes, *labels: str) -> np.random.Generator:
    h = hashlib.sha256(seed + b"|" + "|".join(labels).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:16], "big"))


def _int(seed: bytes, *labels: str) -> int:
    h = hashlib.sha256(seed + b"|" + "|".join(labels).encode()).digest()
    return int.from_bytes(h[:4], "big") % (2 ** 31 - 1)


def commitment(seed: bytes) -> str:
    return hashlib.sha256(b"chromiq-sealed-v1:" + seed).hexdigest()


def draw_slot(seed: bytes, slot: dict) -> dict:
    rng = _sub(seed, "params", slot["id"])
    s = dict(slot)
    n = 3 if slot["device_rep"] in ("RGB", "CMY") else len(
        __import__("benchmarks.research.printers", fromlist=["x"]).split_letters(slot["device_rep"]))
    s["tac"] = None if slot["device_rep"] == "RGB" else float(np.round(rng.uniform(*TAC_RANGE[n])))
    params = Z.draw_params(rng, s)
    params["slot"] = {k: v for k, v in slot.items()}
    return params


def dataset_name(slot_id: str, kind: str, n: int) -> str:
    return f"{slot_id}-{kind}{n}"


def measure_dataset(seed: bytes, printer: Z.ZTruth, kind: str, n: int,
                    level: str, work: Path):
    """-> (ti3 path, misread rows, info) for one sealed dataset."""
    from benchmarks.research import charts, datasets as dsm
    from benchmarks.research.noise import measure
    chart_seed = _int(seed, "chart", printer.id, kind, str(n))
    dev = charts.chart_for(printer, kind, n, seed=chart_seed)
    gain = Z.print_field(printer.params, len(dev))
    nseed = _int(seed, "noise", printer.id, kind, str(n), level)
    detail: dict = {}
    xyz, spec, mis = measure(printer, dev, level=level, seed=nseed, detail=detail,
                             row_gain=gain)
    name = dataset_name(printer.id, kind, n)
    ti3 = dsm.write_ti3(Path(work) / f"{name}-{level}.ti3", printer, dev, xyz, spec)
    return ti3, mis, {"chart": kind, "patches": int(len(dev)), "level": level,
                      "misreads": int(len(mis)),
                      "strip_misreads": len(detail.get("strips", []))}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def generator_hashes() -> dict:
    return {f: sha256_file(HERE / f) for f in GENERATOR_FILES}


# ---------------------------------------------------------------------------
# plausibility (run on the sealed instances with pass/fail output only, and
# on public seeds in the tests and in ``preview``)
# ---------------------------------------------------------------------------

def plausibility(printer: Z.ZTruth) -> dict:
    """Physical sanity of one instance -> {check: bool} plus a few facts
    (``facts``: numbers, printed by ``preview`` only, never by ``seal``)."""
    from benchmarks.synthetic import halton
    n = printer.n
    add = printer.is_additive
    out: dict = {}
    facts: dict = {}
    dev = halton(3000, n, 5)
    tac = printer.tac
    if tac and not add:
        from workflow.profile_engine.b2a import project_tac
        dev = project_tac(dev, tac / 100.0)
    R = printer.reflectance(dev[:400], colour.LAM_1NM)
    out["finite"] = bool(np.isfinite(R).all())
    out["reflectance_range"] = bool(R.min() >= 0.0 and R.max() <= 1.2)
    paper = colour.xyz_to_lab(printer.xyz(printer.white_device()))[0]
    facts["paper_lab"] = paper.round(2).tolist()
    out["paper"] = bool(85.0 <= paper[0] <= 99.5 and abs(paper[1]) <= 4.0
                        and -12.0 <= paper[2] <= 6.0)
    lab = printer.lab_rel(dev)
    facts["darkest_L"] = float(lab[:, 0].min())
    out["darkest"] = bool(1.0 <= lab[:, 0].min() <= 45.0)
    solids = (1.0 - np.eye(3)) if add else np.eye(n)
    sl = printer.lab_rel(solids)
    chroma = np.hypot(sl[:, 1], sl[:, 2])
    letters = ["R", "G", "B"] if add else printer.letters
    chromatic = [i for i, l in enumerate(letters) if l.upper() != "K"]
    black = [i for i, l in enumerate(letters) if l.upper() == "K"]
    facts["solids_L"] = sl[:, 0].round(1).tolist()
    facts["solids_C"] = chroma.round(1).tolist()
    out["solid_chroma"] = bool(all(chroma[i] >= 20.0 for i in chromatic))
    out["black_neutral"] = bool(all(chroma[i] <= 12.0 for i in black))
    out["black_dark"] = bool(all(sl[i, 0] <= 50.0 for i in black if letters[i] == "K"))
    # single-channel ramps: lightness must not RISE by more than a little
    # (hand-offs and screen changes bend a ramp, they do not reverse it)
    t = np.linspace(0, 1, 41)
    worst = 0.0
    for c in range(n):
        d = np.full((len(t), n), 1.0 if add else 0.0)
        d[:, c] = (1.0 - t) if add else t
        L = printer.lab_rel(d)[:, 0]
        worst = max(worst, float(np.max(np.diff(L))))
    facts["ramp_max_L_rise"] = worst
    out["ramps_monotone"] = bool(worst <= 1.5)
    # the hull over the sample plus every solid and two-ink overprint (a
    # TAC-projected Halton sample of 5-7 inks sits mostly in the dark)
    import itertools
    corners = []
    for i, j in itertools.combinations(range(n), 2):
        for a_, b_ in ((1.0, 0.0), (0.0, 1.0), (1.0, 1.0)):
            c = np.full(n, 1.0 if add else 0.0)
            c[i] = (1.0 - a_) if add else a_
            c[j] = (1.0 - b_) if add else b_
            corners.append(c)
    clab = printer.lab_rel(np.array(corners))
    area = hull_area(np.vstack([lab[:, 1:], clab[:, 1:]]))
    facts["ab_hull_area"] = float(area)
    facts["L_range"] = float(100.0 - lab[:, 0].min())
    out["gamut_size"] = bool(3000.0 <= area <= 40000.0 and facts["L_range"] >= 50.0)
    # feature realised (fact, not a check): does the dark end lighten?
    if not add and tac:
        k = n
        heavy = np.full((1, k), min(1.0, tac / 100.0 / k))
        facts["heavy_L_minus_darkest"] = float(printer.lab_rel(heavy)[0, 0] - lab[:, 0].min())
    out["facts"] = facts
    return out


def _cross2(u, v) -> float:
    return float(u[0] * v[1] - u[1] * v[0])


def hull_area(pts: np.ndarray) -> float:
    """Area of the 2-D convex hull (monotone chain), e.g. of a*b*."""
    P = np.unique(np.round(np.asarray(pts, float), 6), axis=0)
    if len(P) < 3:
        return 0.0
    P = P[np.lexsort((P[:, 1], P[:, 0]))]

    def half(points):
        h = []
        for q in points:
            while len(h) >= 2 and _cross2(h[-1] - h[-2], q - h[-2]) <= 0:
                h.pop()
            h.append(q)
        return h
    hull = np.array(half(P)[:-1] + half(P[::-1])[:-1])
    x, y = hull[:, 0], hull[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def checks_passed(p: dict) -> bool:
    return all(v for k, v in p.items() if k != "facts")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def generate(seed: bytes, out: Path, slots=None) -> dict:
    """Draw every slot, measure every dataset, write instances and charts,
    return the manifest (hashes only, no parameters)."""
    slots = slots or SLOTS
    out = Path(out)
    (out / "instances").mkdir(parents=True, exist_ok=True)
    (out / "data").mkdir(parents=True, exist_ok=True)
    man = {"version": SEALED_VERSION, "zfamily": Z.ZFAMILY_VERSION,
           "seed_commitment": commitment(seed), "generator_sha256": generator_hashes(),
           "numpy": np.__version__, "slots": []}
    for slot in slots:
        params = draw_slot(seed, slot)
        canon = Z.canonical(params)
        (out / "instances" / f"{slot['id']}.json").write_text(canon, encoding="utf-8")
        printer = Z.ZTruth(params)
        rec = {"id": slot["id"], "device_rep": slot["device_rep"],
               "paper": slot["paper"], "params_sha256": hashlib.sha256(canon.encode()).hexdigest(),
               "datasets": []}
        for kind, n in slot["charts"]:
            for level in LEVELS:
                ti3, mis, info = measure_dataset(seed, printer, kind, n, level, out / "data")
                np.save(out / "data" / f"{ti3.stem}-misreads.npy", mis)
                rec["datasets"].append({"name": dataset_name(slot["id"], kind, n),
                                        "chart": kind, "patches": n, "level": level,
                                        "ti3": ti3.name, "ti3_sha256": sha256_file(ti3)})
        man["slots"].append(rec)
    return man


def cmd_seal(args) -> int:
    out = Path(args.out).expanduser()
    if (out / "SEED").exists():
        print(f"refusing: {out} is already sealed (SEED exists)")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    seed = secrets.token_bytes(32)
    (out / "SEED").write_bytes(seed)
    os.chmod(out / "SEED", 0o600)
    t0 = time.time()
    man = generate(seed, out)
    man["sealed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    import subprocess
    man["generator_commit"] = subprocess.run(
        ["git", "-C", str(HERE), "rev-parse", "HEAD"], capture_output=True, text=True,
        encoding="utf-8", timeout=60).stdout.strip()
    man["generator_dirty"] = bool(subprocess.run(
        ["git", "-C", str(HERE), "status", "--porcelain", "--", "."], capture_output=True,
        text=True, encoding="utf-8", timeout=60).stdout.strip())
    # plausibility, pass/fail only (no numbers, no parameters)
    fails = []
    for slot in SLOTS:
        params = json.loads((out / "instances" / f"{slot['id']}.json").read_text(encoding="utf-8"))
        res = plausibility(Z.ZTruth(params))
        ok = checks_passed(res)
        if not ok:
            fails.append(slot["id"] + ": " + ",".join(k for k, v in res.items()
                                                       if k != "facts" and not v))
    man["plausibility"] = {"checked": len(SLOTS), "failed": len(fails)}
    text = json.dumps(man, indent=1, sort_keys=True)
    (out / "MANIFEST.json").write_text(text, encoding="utf-8")
    if args.repo_manifest:
        Path(args.repo_manifest).write_text(text, encoding="utf-8")
    print(f"sealed {len(SLOTS)} printers, "
          f"{sum(len(s['datasets']) for s in man['slots'])} datasets in {time.time() - t0:.0f} s; "
          f"plausibility: {len(SLOTS) - len(fails)}/{len(SLOTS)} pass")
    for f in fails:
        print("  FAILED (check names only):", f)
    print("seed commitment", man["seed_commitment"])
    return 0 if not fails else 1


def cmd_verify(args) -> int:
    d = Path(args.dir).expanduser()
    seed = (d / "SEED").read_bytes()
    stored = json.loads((d / "MANIFEST.json").read_text(encoding="utf-8"))
    refs = [stored]
    if args.manifest:
        refs.append(json.loads(Path(args.manifest).read_text(encoding="utf-8")))
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        fresh = generate(seed, Path(td))
    bad = []
    for ref in refs:
        if ref["seed_commitment"] != fresh["seed_commitment"]:
            bad.append("seed commitment")
        for a, b in zip(ref["slots"], fresh["slots"]):
            if a["params_sha256"] != b["params_sha256"]:
                bad.append(f"{a['id']} parameters")
            for x, y in zip(a["datasets"], b["datasets"]):
                if x["ti3_sha256"] != y["ti3_sha256"]:
                    bad.append(f"{x['ti3']} (re-measured file differs)")
        if ref.get("generator_sha256") != fresh["generator_sha256"]:
            changed = [k for k in fresh["generator_sha256"]
                       if ref.get("generator_sha256", {}).get(k) != fresh["generator_sha256"][k]]
            print("note: generator files changed since sealing:", ", ".join(changed))
    for s in stored["slots"]:
        for x in s["datasets"]:
            if sha256_file(d / "data" / x["ti3"]) != x["ti3_sha256"]:
                bad.append(f"{x['ti3']} on disk")
    print("VERIFY", "PASS" if not bad else "FAIL", *sorted(set(bad)))
    return 0 if not bad else 1


def cmd_preview(args) -> int:
    """Public seeds only: what the generator draws, for review."""
    seed = f"public-preview-{args.seed}".encode()
    want = set(args.slots.split(",")) if args.slots else None
    for slot in SLOTS:
        if want and slot["id"] not in want:
            continue
        params = draw_slot(seed, slot)
        res = plausibility(Z.ZTruth(params))
        feats = {"handoff": sorted(params.get("handoff", {})),
                 "pooling": "pooling" in params,
                 "bronze": "bronze" in params["surface"],
                 "oba": "oba" in params["paper"],
                 "min_dot": sum("min_dot" in i["tone"] for i in params["inks"]),
                 "screen": sum("screen" in i["tone"] for i in params["inks"]),
                 "kink": sum("kink" in i["tone"] for i in params["inks"])}
        print(slot["id"], slot["device_rep"], "PASS" if checks_passed(res) else "FAIL",
              json.dumps(res["facts"]), json.dumps(feats))
    return 0


def is_unsealed(d: Path) -> bool:
    return (Path(d) / "UNSEALED").exists()


def cmd_unseal(args) -> int:
    d = Path(args.dir).expanduser()
    if args.by != "orchestrator":
        print("only the orchestrator unseals the set (protocol v3, A2)")
        return 2
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    (d / "UNSEALED").write_text(f"{stamp} by {args.by}: {args.reason}\n", encoding="utf-8")
    with open(d / "UNSEAL-LOG.md", "a", encoding="utf-8") as f:
        f.write(f"- {stamp} unsealed by {args.by}: {args.reason}\n")
    print("unsealed:", d)
    return 0


def load_datasets(d: Path, work: Path, levels=LEVELS, only=None) -> list:
    """The sealed datasets as ``datasets.Dataset`` records (after unsealing)."""
    from benchmarks.research import datasets as dsm
    d = Path(d).expanduser()
    if not is_unsealed(d):
        raise PermissionError(f"{d} is sealed: the orchestrator must unseal it for the "
                              "FINAL benchmark (python -m benchmarks.research.sealed unseal)")
    man = json.loads((d / "MANIFEST.json").read_text(encoding="utf-8"))
    out = []
    for s in man["slots"]:
        params = json.loads((d / "instances" / f"{s['id']}.json").read_text(encoding="utf-8"))
        p = Z.ZTruth(params)
        for x in s["datasets"]:
            if x["level"] not in levels or (only and x["name"] not in only):
                continue
            ti3 = d / "data" / x["ti3"]
            if sha256_file(ti3) != x["ti3_sha256"]:
                raise ValueError(f"{ti3} does not match the manifest")
            mis = np.load(d / "data" / f"{ti3.stem}-misreads.npy")
            out.append((x["level"], dsm.Dataset(
                name=x["name"], kind="synthetic", ti3=ti3, n_channels=p.n,
                color_rep=p.color_rep, ink_limit=p.tac, printer=p, misread_rows=mis,
                info={"family": p.family, "noise": x["level"], "chart": x["chart"],
                      "patches": x["patches"], "role": "sealed-confirmatory"})))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("seal")
    a.add_argument("--out", default=str(DEFAULT_DIR))
    a.add_argument("--repo-manifest", default=str(REPO_MANIFEST))
    a = sub.add_parser("verify")
    a.add_argument("dir")
    a.add_argument("--manifest", default=str(REPO_MANIFEST))
    a = sub.add_parser("preview")
    a.add_argument("--seed", default="1")
    a.add_argument("--slots", default="")
    a = sub.add_parser("unseal")
    a.add_argument("dir")
    a.add_argument("--by", required=True)
    a.add_argument("--reason", required=True)
    args = ap.parse_args(argv)
    return {"seal": cmd_seal, "verify": cmd_verify, "preview": cmd_preview,
            "unseal": cmd_unseal}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
