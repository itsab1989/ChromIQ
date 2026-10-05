"""Build Profile options audit, PART 2 (Agent 10b, 2026-10-05).

Every option of the Build Profile tab, set one at a time from the Manual
tab's defaults, built through the APP's own route on both builders
(``build_worker`` ``params`` jobs: ``settings_from_params`` for the engine,
``ProfileBuilder._build_args`` for colprof), then compared with the default
build of the same dataset and builder.

    source /Users/Basti/develop/ChromIQ/.venv/bin/activate
    python -m benchmarks.research.options build   --out DIR [--parallel 5] [--blocks M1,K1]
    python -m benchmarks.research.options analyse --out DIR [--parallel 5]

Datasets: battery v3 development printers, typical noise, seed 23, on the
ChromIQ-default targen chart (400 patches for <= 4 inks, 900 for 6 inks);
X1p / X3p are the pessimistic twins (protocol v3 A1: all development).
Findings: ``Findings/agent10-02-options-part2.md``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[1]
ARGYLL = "/Applications/Argyll/bin"
CLAY = "/Applications/Argyll/ref/ClayRGB1998.icm"
SRGB = "/Applications/Argyll/ref/sRGB.icm"
CMYK_SRC = "/Applications/Argyll/ref/cmyk.icm"
TIMESTAMP = "2026-01-01T00:00:00"

# The Manual tab's defaults (tab_profile._collect_manual_profile with every
# widget untouched): -qm, -S ClayRGB (the recommended mode, the tab's own
# default), -v. The description is fixed so the desc tag does not differ
# between jobs that test something else.
BASE_PARAMS = {"quality": "m", "gamut_sat_src": CLAY, "verbose": True,
               "description": "OptAudit"}

DATASETS = {
    # name: (printer, chart kind, patches, level)
    "X1": ("X1", "targen", 400, "typical"),
    "X3": ("X3", "targen", 400, "typical"),
    "S3": ("S3", "targen", 400, "typical"),
    "X3m": ("X3m", "targen", 400, "typical"),
    "X5": ("X5", "targen", 900, "typical"),
    "S5": ("S5", "targen", 900, "typical"),
    "X1p": ("X1", "targen", 400, "pessimistic"),
    "X3p": ("X3", "targen", 400, "pessimistic"),
}
HEAVY = {"X5", "S5"}
COLPROF_OK = {"X1", "X3", "S3", "X3m", "X1p", "X3p"}

KP = {"k_rule": "p", "k_stle": 0.0, "k_stpo": 0.1, "k_enpo": 0.9, "k_enle": 1.0,
      "k_shape": 1.0}


def _j(block, ds, label, params=None, settings=None, colprof=True, engine=True,
       ti3_variant="", colprof_args=None):
    return {"block": block, "ds": ds, "label": label, "params": params or {},
            "settings": settings or {}, "colprof": colprof and ds in COLPROF_OK,
            "engine": engine, "ti3_variant": ti3_variant,
            "colprof_args": colprof_args or []}


def matrix() -> list[dict]:
    m: list[dict] = []
    for ds in DATASETS:
        m.append(_j("base", ds, "base"))
    m.append(_j("base", "X3", "base-again", colprof=True))
    # P2-M1 metadata and header (tags/header only; LUTs must not move)
    meta = {"description": "Prüfdruck Müller", "manufacturer": "ACME Print",
            "model": "Model 9", "copyright": "© 2026 Test Druck",
            "z_surface": "m", "z_media_type": "t", "z_polarity": "n",
            "z_color_mode": "b", "z_default_intent": "p", "no_embedded_data": True}
    for ds in ("X1", "X3"):
        m.append(_j("M1", ds, "meta-all", meta))
    for z in ("s", "a", "r"):
        m.append(_j("M1", "X3", f"Z{z}", {"z_default_intent": z}))
    # P2-A1 algorithm
    for ds in ("X1", "X3", "X5"):
        m.append(_j("A1", ds, "ax", {"algorithm": "x"}))
    # P2-Q1 quality
    for ds in ("X1", "X3"):
        for q in ("l", "h", "u"):
            m.append(_j("Q1", ds, f"q{q}", {"quality": q}))
    for q in ("l", "h"):
        m.append(_j("Q1", "X5", f"q{q}", {"quality": q}))
    # P2-Q2 B2A quality
    for ds in ("X1", "X3"):
        for b in ("l", "m", "h", "u", "n"):
            m.append(_j("Q2", ds, f"b{b}", {"b2a_quality": b}))
    for b in ("h", "n"):
        m.append(_j("Q2", "X5", f"b{b}", {"b2a_quality": b}))
    # P2-R1 smoothing
    for ds in ("X1", "X3", "X3p"):
        for r in (0.25, 1.0, 2.0, 4.0):
            m.append(_j("R1", ds, f"r{r:g}", {"smoothing": r}))
    m.append(_j("R1", "X5", "r2", {"smoothing": 2.0}))
    # P2-V1 dark emphasis
    for ds in ("X1", "X3"):
        m.append(_j("V1", ds, "V2", {"dark_emphasis": 2.0}))
    m.append(_j("V1", "X3", "V3.5", {"dark_emphasis": 3.5}))
    # P2-S1 illuminant (SPEC data), S2 observer, S3 FWA
    for ds in ("S3", "X3", "X1"):
        for il in ("D50", "D65", "A", "F8", "D50M2", "D65M2"):
            m.append(_j("S1", ds, f"i{il}", {"illuminant": il}))
    for ds in ("S3", "X1"):
        for ob in ("1931_2", "1964_10", "2015_2", "2015_10"):
            m.append(_j("S2", ds, f"o{ob}", {"observer": ob}))
    m.append(_j("S3", "X3", "f", {"fwa_enabled": True}))
    m.append(_j("S3", "X3", "fD50", {"fwa_enabled": True, "fwa_illum": "D50"}))
    # P2-K1 black generation, K2 locus
    for ds in ("X3", "X3m"):
        for k in ("z", "h", "x", "r"):
            m.append(_j("K1", ds, f"k{k}", {"k_rule": k}))
        m.append(_j("K1", ds, "kp", dict(KP)))
    for k in ("r", "x", "z"):
        m.append(_j("K1", "X5", f"k{k}", {"k_rule": k}))
    m.append(_j("K1", "X1", "kx", {"k_rule": "x"}))
    for k in ("r", "x"):
        m.append(_j("K2", "X3", f"K{k}", {"k_rule": k, "k_locus": True}))
    m.append(_j("K2", "X3", "Kp", dict(KP, k_locus=True)))
    m.append(_j("K2", "X5", "Kx", {"k_rule": "x", "k_locus": True}))
    # P2-L1/L2 ink limits from the chart stamp (no tab control)
    m.append(_j("L", "X3", "stampL70", ti3_variant="L70"))
    m.append(_j("L", "X3", "stampl240", ti3_variant="l240"))
    m.append(_j("L", "X5", "stampL70", ti3_variant="L70"))
    # P2-G1 gamut source
    for ds in ("X1", "X3", "X5"):
        m.append(_j("G1", ds, "gnone", {"gamut_sat_src": ""}))
        m.append(_j("G1", ds, "gs-clay", {"gamut_sat_src": "", "gamut_src": CLAY}))
    for ds in ("X1", "X3"):
        m.append(_j("G1", ds, "gS-srgb", {"gamut_sat_src": SRGB}))
    # P2-G2 intents
    for t in ("p", "pa", "lp", "ms", "r", "a"):
        m.append(_j("G2", "X3", f"t{t}", {"perc_intent": t}))
    for t in ("s", "ms", "r"):
        m.append(_j("G2", "X3", f"T{t}", {"sat_intent": t}))
    m.append(_j("G2", "X5", "tpa", {"perc_intent": "pa"}))
    m.append(_j("G2", "X5", "Tms", {"sat_intent": "ms"}))
    # P2-G3 viewing conditions
    for c, d in (("mt", "pp"), ("md", "pc"), ("pe", "pe")):
        m.append(_j("G3", "X3", f"c{c}-d{d}", {"src_viewing_cond": c,
                                               "dst_viewing_cond": d}))
    m.append(_j("G3", "X5", "cmt-dpp", {"src_viewing_cond": "mt", "dst_viewing_cond": "pp"}))
    # P2-G4 colorimetric source tables
    for lab, kw in (("nP", {"no_perc_gamut": True}), ("nS", {"no_sat_gamut": True}),
                    ("nPnS", {"no_perc_gamut": True, "no_sat_gamut": True})):
        m.append(_j("G4", "X3", f"clay-{lab}", kw))
        m.append(_j("G4", "X3", f"cmyk-{lab}", dict(kw, gamut_sat_src=CMYK_SRC)))
    m.append(_j("G4", "X3", "cmyk-base", {"gamut_sat_src": CMYK_SRC}))
    m.append(_j("G4", "X5", "clay-nP", {"no_perc_gamut": True}))
    # P2-G5 inverse gamut mapping into A2B0/A2B2
    m.append(_j("G5", "X3", "nI", {"inv_gamut_map": True}))
    m.append(_j("G5", "X5", "nI", {"inv_gamut_map": True}))
    # P2-N1 curve flags
    for ds in ("X1", "X3"):
        m.append(_j("N1", ds, "ni", {"no_input_shaper": True}))
        m.append(_j("N1", ds, "np", {"no_grid_pos": True}))
        m.append(_j("N1", ds, "no", {"no_output_shaper": True}))
        m.append(_j("N1", ds, "ni-np", {"no_input_shaper": True, "no_grid_pos": True}))
    # P2-E1..E4 engine-only options
    for ds in ("S3", "X3", "S5"):
        m.append(_j("E1", ds, "physics", {"spectral_physics": True}, colprof=False))
    for ds in ("X1", "X3"):
        for v in ("4", "both"):
            m.append(_j("E2", ds, f"v{v}", {"icc_version": v}, colprof=False))
    for ds in ("X1", "X3", "S3", "X1p", "X3p", "X5"):
        m.append(_j("E3", ds, "noise", {"noise_model": True}, colprof=False))
    for ds in ("X3", "X5"):
        m.append(_j("E4", ds, "bijective", {"render_style": "bijective"}, colprof=False))
    return m


# ---------------------------------------------------------------------------
# datasets
# ---------------------------------------------------------------------------

def make_datasets(work: Path, names=None) -> dict:
    from benchmarks.research import datasets as dsm
    from benchmarks.research.printers import build_printers
    printers = build_printers()
    out = {}
    for name, (pid, kind, n, lvl) in DATASETS.items():
        if names and name not in names:
            continue
        out[name] = dsm.synthetic_chart(pid, work, kind, n, level=lvl, printers=printers)
    return out


def ti3_variant(src: Path, variant: str, work: Path) -> Path:
    """A copy of the measurement with a different ink-limit stamp (how a
    chart made with ChromIQ's ink-limit rows reaches both builders)."""
    if not variant:
        return src
    dst = work / f"{src.stem}-{variant}.ti3"
    text = src.read_text(encoding="utf-8")
    if variant.startswith("L"):
        text = text.replace('TOTAL_INK_LIMIT', f'BLACK_INK_LIMIT "{variant[1:]}"\nTOTAL_INK_LIMIT', 1)
    elif variant.startswith("l"):
        text = re.sub(r'TOTAL_INK_LIMIT "[\d.]+"', f'TOTAL_INK_LIMIT "{variant[1:]}"', text)
    dst.write_text(text, encoding="utf-8")
    return dst


def jobs(out: Path, dss: dict, blocks=None) -> list[dict]:
    prof = out / "profiles"
    logs = out / "logs"
    for d in (prof, logs):
        d.mkdir(parents=True, exist_ok=True)
    res = []
    for row in matrix():
        if blocks and row["block"] not in blocks and row["block"] != "base":
            continue
        if row["ds"] not in dss:
            continue
        ds = dss[row["ds"]]
        ti3 = ti3_variant(Path(ds.ti3), row["ti3_variant"], out / "work")
        params = dict(BASE_PARAMS, **row["params"])
        for builder in ("accurate", "colprof"):
            if builder == "accurate" and not row["engine"]:
                continue
            if builder == "colprof" and not row["colprof"]:
                continue
            stem = f"{row['block']}-{row['ds']}-{row['label']}-{'eng' if builder == 'accurate' else 'cp'}"
            res.append({"engine": builder, "tree": str(TREE), "ti3": str(ti3),
                        "out": str(prof / f"{stem}.icc"), "log": str(logs / f"{stem}.log"),
                        "params": params, "settings": row["settings"],
                        "colprof_args": row["colprof_args"], "argyll_bin": ARGYLL,
                        "timestamp": TIMESTAMP, "timeout": 5400,
                        "meta": {k: row[k] for k in ("block", "ds", "label", "ti3_variant")},
                        "heavy": row["ds"] in HEAVY and builder == "accurate"})
    # longest first: the 6-ink engine builds start before the short ones
    res.sort(key=lambda j: (not j["heavy"], j["engine"] == "colprof"))
    return res


def run_one(job: dict) -> dict:
    from benchmarks.research.run import run_build
    j = {k: v for k, v in job.items() if k not in ("meta", "heavy")}
    res = run_build(j)
    res["meta"] = job["meta"]
    res["verified"] = verify(res)
    return res


def verify(res: dict) -> dict:
    """Every build is checked: file there, parses, iccdump reads it."""
    import subprocess
    out = Path(res["job"]["out"])
    if not res.get("ok"):
        return {"ok": False, "why": "build failed"}
    if not out.exists() or out.stat().st_size < 1000:
        return {"ok": False, "why": "missing or tiny file"}
    r = subprocess.run([f"{ARGYLL}/iccdump", "-v1", str(out)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    ok = r.returncode == 0 and "Error" not in (r.stdout + r.stderr)
    return {"ok": ok, "why": "" if ok else (r.stdout + r.stderr)[-300:]}


def cmd_build(args) -> int:
    out = Path(args.out).resolve()
    (out / "work").mkdir(parents=True, exist_ok=True)
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
              "MKL_NUM_THREADS"):
        os.environ[k] = "1"
    os.environ["CHROMIQ_ENGINE_THREADS"] = "1"
    os.environ.pop("CHROMIQ_ENGINE_NEXT", None)
    blocks = [b for b in args.blocks.split(",") if b] or None
    dsnames = [d for d in args.datasets.split(",") if d] or None
    dss = make_datasets(out / "work", dsnames)
    js = jobs(out, dss, blocks)
    bpath = out / "builds.json"
    builds = json.loads(bpath.read_text(encoding="utf-8")) if bpath.exists() else []
    done = {b["job"]["out"] for b in builds if b.get("ok") and Path(b["job"]["out"]).exists()
            and b.get("verified", {}).get("ok")}
    if args.retry_failed:
        builds = [b for b in builds if b["job"]["out"] in done]
    else:
        tried = {b["job"]["out"] for b in builds}
        done |= tried
    todo = [j for j in js if j["out"] not in done]
    print(f"{len(js)} jobs, {len(todo)} to build, {args.parallel} at a time", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        for res in ex.map(run_one, todo):
            builds = [b for b in builds if b["job"]["out"] != res["job"]["out"]] + [res]
            bpath.write_text(json.dumps(builds, indent=1), encoding="utf-8")
            v = res["verified"]
            print(f"[{time.time() - t0:6.0f}s] {Path(res['job']['out']).name}: "
                  f"{'ok' if res.get('ok') else 'FAILED'} verified={v['ok']} "
                  f"{res.get('seconds', 0):.0f}s "
                  f"{'' if res.get('ok') else str(res.get('error', ''))[:160]}", flush=True)
    return 0


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

LUT_TAGS = ("A2B0", "A2B1", "A2B2", "B2A0", "B2A1", "B2A2", "gamt")


def header(path) -> dict:
    d = Path(path).read_bytes()
    return {"version": f"{d[8]}.{d[9] >> 4}", "class": d[12:16].decode("latin-1"),
            "space": d[16:20].decode("latin-1"), "pcs": d[20:24].decode("latin-1"),
            "attributes_hex": d[56:64].hex(), "intent": struct.unpack(">I", d[64:68])[0],
            "flags_hex": d[44:48].hex()}


def lut_shape(tag: bytes) -> dict | None:
    sig = tag[:4]
    if sig == b"mft2":
        nin, nout, grid = tag[8], tag[9], tag[10]
        ni, no = struct.unpack(">HH", tag[48:52])
        return {"type": "lut16", "in": nin, "out": nout, "grid": grid,
                "in_entries": ni, "out_entries": no}
    if sig == b"mft1":
        return {"type": "lut8", "in": tag[8], "out": tag[9], "grid": tag[10]}
    if sig in (b"mAB ", b"mBA "):
        return {"type": sig.decode().strip(), "in": tag[8], "out": tag[9]}
    return None


def text_of(tag: bytes) -> str:
    sig = tag[:4]
    if sig == b"desc":
        n = struct.unpack(">I", tag[8:12])[0]
        return tag[12:12 + n].rstrip(b"\0").decode("latin-1")
    if sig == b"text":
        return tag[8:].rstrip(b"\0").decode("latin-1")
    if sig == b"mluc":
        cnt = struct.unpack(">I", tag[8:12])[0]
        if cnt:
            ln, off = struct.unpack(">II", tag[20:28])
            return tag[off:off + ln].decode("utf-16-be")
    return ""


def tag_facts(path) -> dict:
    from benchmarks.research.identity import tag_table
    t = tag_table(path)
    facts = {"tags": sorted(t), "header": header(path), "luts": {}, "text": {}}
    for k in LUT_TAGS:
        if k in t:
            facts["luts"][k] = lut_shape(t[k])
    for k in ("desc", "cprt", "dmnd", "dmdd"):
        if k in t:
            facts["text"][k] = text_of(t[k])
    # aliases (same offset in the tag table)
    d = Path(path).read_bytes()
    (count,) = struct.unpack(">I", d[128:132])
    offs = {}
    for i in range(count):
        sig, off, size = struct.unpack(">4sII", d[132 + 12 * i:144 + 12 * i])
        offs.setdefault((off, size), []).append(sig.decode("latin-1"))
    facts["aliases"] = [v for v in offs.values() if len(v) > 1]
    return facts


def lut_identity(a, b) -> dict:
    from benchmarks.research.identity import tag_table
    ta, tb = tag_table(a), tag_table(b)
    return {k: (ta.get(k) == tb.get(k)) for k in LUT_TAGS if k in ta or k in tb}


class SpectralTruth:
    """Truth under any illuminant AND observer (CIE tables are data; the
    observers come from the engine's own published CIE 170-2 tables, the
    illuminant SPDs from the benchmark's cie_tables, M2 = Argyll's UV cut)."""

    def __init__(self, printer, illuminant="D50", observer="1931_2"):
        self.printer = printer
        self.illuminant = illuminant or "D50"
        self.observer = observer or "1931_2"
        self.proxy = None

    @property
    def is_proxy(self):
        return False

    def _weights(self):
        from benchmarks.research import colour
        from workflow.profile_engine import spectral as sp
        lam = colour.LAM_1NM
        spd = sp.illuminant_spd(self.illuminant, lam)
        cmf = sp.observer_cmf(self.observer, lam)
        w = spd[None, :] * cmf
        return w * (100.0 / w[1].sum())

    def lab(self, device):
        from benchmarks.research import colour
        w = self._weights()
        lam = colour.LAM_1NM
        dev = np.atleast_2d(np.asarray(device, float))
        xyz = self.printer.reflectance(dev, lam) @ w.T
        white = self.printer.reflectance(self.printer.white_device(), lam) @ w.T
        return colour.media_relative_lab(xyz, white[0])


def score_profile(task):
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[k] = "1"
    sys.path.insert(0, str(TREE))
    from benchmarks.research import metrics, datasets as dsm, cmm, gmq
    from benchmarks.research.printers import build_printers
    path, cache, dsname, ill, obs, extra = task
    cache = Path(cache)
    sha = __import__("hashlib").sha256(Path(path).read_bytes()).hexdigest()
    if cache.exists():
        rec = json.loads(cache.read_text(encoding="utf-8"))
        if rec.get("sha256") == sha and set(extra) <= set(rec.get("extra_done", [])):
            return path, rec
    pid, kind, n, lvl = DATASETS[dsname]
    p = build_printers()[pid]
    ds = dsm.Dataset(name=pid, kind="synthetic", ti3=Path("-"), n_channels=p.n,
                     color_rep=p.color_rep, ink_limit=p.tac, printer=p)
    truth = SpectralTruth(p, ill, obs)
    rec = {"sha256": sha, "extra_done": list(extra)}
    try:
        rec["argyll"] = metrics.score(path, ds, "argyll", truth, n_eval=8000, light=False)
    except Exception as exc:
        rec["argyll"] = {"error": f"{type(exc).__name__}: {exc}"}
    if "k" in extra and not p.is_additive:
        rec["k"] = k_facts(path, p)
    if "gmq" in extra:
        rec["gmq"] = {}
        for intent in ("p", "s"):
            try:
                summ, _ = gmq.evaluate(path, p, "argyll", intent=intent)
                rec["gmq"][intent] = summ
            except Exception as exc:
                rec["gmq"][intent] = {"error": f"{type(exc).__name__}: {exc}"}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(rec, default=_js), encoding="utf-8")
    return path, rec


def k_facts(path, printer) -> dict:
    """Black generation as printed: K along the neutral axis (B2A1 and B2A0),
    total ink, the black point."""
    from benchmarks.research import gmq
    out = {}
    ls = np.array([20.0, 40.0, 60.0, 80.0])
    lab = np.stack([ls, 0 * ls, 0 * ls], 1)
    kidx = printer.letters.index("K") if "K" in printer.letters else None
    for intent in ("r", "p"):
        dev = gmq.b2a_intent(Path(path), lab, "argyll", intent)
        out[f"neutral_{intent}"] = {
            "K": [round(float(v), 3) for v in dev[:, kidx]] if kidx is not None else None,
            "tac": [round(float(v) * 100, 1) for v in dev.sum(1)]}
    # total ink over an in-gamut Lab cloud (the truth's own colours)
    from benchmarks.research.metrics import eval_device
    dev0 = eval_device(printer.n, printer.is_additive, printer.tac, 3000)
    lab0 = printer.lab_rel(dev0)
    ink = gmq.b2a_intent(Path(path), lab0, "argyll", "r")
    printed = printer.lab_rel(ink)
    from benchmarks.research import colour
    de = colour.de2000(printed, lab0)
    out["ink_mean"] = float(ink.sum(1).mean() * 100)
    out["ink_max"] = float(ink.sum(1).max() * 100)
    out["K_mean"] = float(ink[:, kidx].mean()) if kidx is not None else None
    out["b2a1_de_median"] = float(np.median(de))
    out["b2a1_de_p95"] = float(np.percentile(de, 95))
    dark = (lab0[:, 0] < 40) & (np.hypot(lab0[:, 1], lab0[:, 2]) > 30)
    out["dark_sat_n"] = int(dark.sum())
    if kidx is not None and dark.any():
        out["dark_sat_K_mean"] = float(ink[dark, kidx].mean())
    blk = gmq.b2a_intent(Path(path), np.array([[0.0, 0, 0]]), "argyll", "r")
    bl = printer.lab_rel(blk)[0]
    out["black"] = {"dev": [round(float(v), 3) for v in blk[0]],
                    "Lab": [round(float(v), 2) for v in bl], "tac": float(blk.sum() * 100)}
    return out


def _js(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def extras_for(block: str) -> tuple:
    if block in ("K1", "K2", "L", "base"):
        return ("k",) if block != "base" else ("k", "gmq")
    if block in ("G1", "G2", "G3", "G4", "G5", "E4"):
        return ("gmq",)
    return ()


def cmd_analyse(args) -> int:
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    from benchmarks.research.identity import measure_difference, differing_tags
    out = Path(args.out).resolve()
    builds = json.loads((out / "builds.json").read_text(encoding="utf-8"))
    ok = [b for b in builds if b.get("ok") and b.get("verified", {}).get("ok")]
    base = {(b["meta"]["ds"], b["job"]["engine"]): b for b in ok
            if b["meta"]["block"] == "base" and b["meta"]["label"] == "base"}
    tasks = []
    for b in ok:
        mt = b["meta"]
        p = b["job"]["params"]
        tasks.append((b["job"]["out"], str(out / "scores" / (Path(b["job"]["out"]).stem + ".json")),
                      mt["ds"], p.get("illuminant", ""), p.get("observer", ""),
                      extras_for(mt["block"])))
    scores = {}
    with ProcessPoolExecutor(max_workers=args.parallel, mp_context=mp.get_context("spawn")) as ex:
        for path, rec in ex.map(score_profile, tasks):
            scores[path] = rec
    rows = []
    for b in builds:
        mt = b["meta"]
        row = {"block": mt["block"], "ds": mt["ds"], "label": mt["label"],
               "builder": b["job"]["engine"], "ok": bool(b.get("ok")),
               "verified": b.get("verified", {}).get("ok"), "seconds": b.get("seconds"),
               "error": None if b.get("ok") else str(b.get("error", ""))[-600:],
               "args": b.get("args"), "a2b_grid": b.get("a2b_grid"),
               "b2a_grid": b.get("b2a_grid"), "settings_applied": b.get("settings_applied"),
               "perceptual_distinct": b.get("perceptual_distinct")}
        logp = Path(b["job"].get("log", ""))
        if logp.is_file():
            row["log_lines"] = logp.read_text(encoding="utf-8", errors="replace").splitlines()[:400]
        if b.get("ok") and b.get("verified", {}).get("ok"):
            path = b["job"]["out"]
            row["facts"] = tag_facts(path)
            row["score"] = scores.get(path)
            ref = base.get((mt["ds"], b["job"]["engine"]))
            if ref and ref["job"]["out"] != path:
                row["vs_base"] = {"lut_identical": lut_identity(ref["job"]["out"], path),
                                  "differing": differing_tags(ref["job"]["out"], path)}
                try:
                    pid = DATASETS[mt["ds"]][0]
                    from benchmarks.research.printers import build_printers
                    pr = build_printers()[pid]
                    row["vs_base"]["diff"] = measure_difference(
                        ref["job"]["out"], path, pr.n, pr.is_additive, pr.tac, n=3000)
                except Exception as exc:
                    row["vs_base"]["diff_error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    (out / "analysis.json").write_text(json.dumps(rows, indent=1, default=_js), encoding="utf-8")
    print(f"wrote {out / 'analysis.json'}: {len(rows)} rows", flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "analyse", "list"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--parallel", type=int, default=5)
    ap.add_argument("--blocks", default="")
    ap.add_argument("--datasets", default="")
    ap.add_argument("--retry-failed", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "list":
        m = matrix()
        eng = sum(1 for r in m if r["engine"])
        cp = sum(1 for r in m if r["colprof"])
        print(f"{len(m)} rows: {eng} engine builds, {cp} colprof builds")
        return 0
    return cmd_build(args) if args.cmd == "build" else cmd_analyse(args)


if __name__ == "__main__":
    sys.exit(main())
