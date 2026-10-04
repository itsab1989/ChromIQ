"""Datasets for the research benchmark (Agent 6).

Two kinds:

* **synthetic** (``kind = "synthetic"``): a truth printer from
  :mod:`printers`, a chart (September's ``make_chart`` composition by
  default), a simulated measurement (:mod:`noise`). Scored against the
  truth everywhere.
* **real** (``kind = "real"``): a measured chart, split into a training
  part the builders see and a held-out part they never see (endpoints
  protected, deterministic seed). Scored at the held-out patches only (A2B),
  and for B2A through a proxy printer (see ``metrics``), clearly labelled.

Real files are read in place, read-only; copies are written to the run's
scratch directory. The CxF3 (.mxf) files shipped with X-Rite i1Profiler are
licensed reference data (FOGRA, IDEAlliance): they are used locally only,
never copied into the repository, and only derived error statistics are
reported.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from benchmarks.research import colour
from benchmarks.research.noise import LAM_10, measure
from benchmarks.research.printers import TruthPrinter, build_printers

# Where the i1Profiler sample / reference measurements live. v1 hard-coded
# /Library/Application Support/X-Rite/i1Profiler, which no longer exists on
# this machine after the fresh macOS install (agent 7 T8e); the data were
# copied to ~/develop/i1Profiler. Override with CHROMIQ_I1PROFILER_DATA or
# ``run --i1profiler-data``.
XRITE_DEFAULT = Path.home() / "develop" / "i1Profiler"
XRITE_ENV = "CHROMIQ_I1PROFILER_DATA"


def xrite_root() -> Path:
    return Path(os.environ.get(XRITE_ENV) or XRITE_DEFAULT).expanduser()


OWNER = Path.home() / "ChromIQ"


# ---------------------------------------------------------------------------
# Chart composition (September's make_chart, printer-agnostic)
# ---------------------------------------------------------------------------

class _Shape:
    def __init__(self, p: TruthPrinter):
        self.n_channels = p.n
        self.is_additive = p.is_additive
        self.tac = p.tac


def make_chart(printer: TruthPrinter, n_patches: int = 900, seed: int = 11
               ) -> np.ndarray:
    from benchmarks.synthetic import make_chart as sept
    return sept(_Shape(printer), n_patches, seed)


def make_chart_ecg(printer: TruthPrinter, n_patches: int = 900, seed: int = 11
                   ) -> np.ndarray:
    """An N-colour chart composed like the professional ECG charts (agent 14;
    IDEAlliance ECG CMYKOGV 2019, X-Rite ECG 4200 and Fogra ECG-7C are 80 %
    3-4-ink patches, 5+ inks under 10 %, every two-ink overprint sampled,
    complementary pairs sampled less): white/K endpoints, 11-step single-ink
    ramps, a CMY grey, a 3 x 3 grid of every ink pair, a CMYK-only dark set,
    then a quasi-random fill with 3 (55 %), 4 (35 %) or 5+ (10 %) inks on.
    For <= 4 inks it is the September chart unchanged."""
    n = printer.n
    if n <= 4 or printer.is_additive:
        return make_chart(printer, n_patches, seed)
    from benchmarks.synthetic import halton
    rng = np.random.default_rng(seed)
    rows = [np.zeros((4, n))]
    k = np.zeros((4, n)); k[:, 3] = 1.0
    rows.append(k)
    steps = np.linspace(0.0, 1.0, 11)
    for c in range(n):
        r = np.zeros((len(steps), n)); r[:, c] = steps
        rows.append(r)
    grey = np.zeros((len(steps), n)); grey[:, :3] = steps[:, None] * np.array([0.9, 0.75, 0.72])
    rows.append(grey)
    lv = np.array([0.25, 0.6, 1.0])
    a, b = np.meshgrid(lv, lv, indexing="ij")
    import itertools
    for i, j in itertools.combinations(range(n), 2):
        g = np.zeros((9, n)); g[:, i], g[:, j] = a.ravel(), b.ravel()
        rows.append(g)
    fixed = np.vstack(rows)
    rest = max(n_patches - len(fixed), 0)
    n_dark = rest // 10
    dark = np.zeros((n_dark, n))
    dark[:, :4] = 0.3 + 0.7 * halton(n_dark, 4, seed + 1)
    # complementary pairs (solid hues >= 150 deg apart) are drawn half as often
    lab = printer.lab_rel(np.eye(n))
    hue = np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    comp = {(i, j) for i, j in itertools.combinations(range(n), 2)
            if chroma[i] > 20 and chroma[j] > 20
            and abs((hue[i] - hue[j] + 180) % 360 - 180) >= 150}
    m = rest - n_dark
    vals = halton(m, n, seed)
    fill = np.zeros((m, n))
    for r in range(m):
        u = rng.uniform()
        size = 3 if u < 0.55 else 4 if u < 0.90 else int(rng.integers(5, n + 1))
        while True:
            act = rng.choice(n, size, replace=False)
            bad = any((min(i, j), max(i, j)) in comp for i, j in itertools.combinations(act, 2))
            if not bad or rng.uniform() < 0.5:
                break
        fill[r, act] = vals[r, act]
    chart = np.vstack([fixed, dark, fill])
    if printer.tac is not None:
        from workflow.profile_engine.b2a import project_tac
        chart = project_tac(chart, printer.tac / 100.0)
    return chart


def write_ti3(path: Path, printer: TruthPrinter, device: np.ndarray,
              xyz: np.ndarray, spec10: np.ndarray | None) -> Path:
    letters = printer.letters
    prefix = "RGB" if printer.is_additive else printer.device_rep
    fields = [f"{prefix}_{c}" for c in letters] + ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    sf = [f"SPEC_{int(w)}" for w in LAM_10] if spec10 is not None else []
    lines = ["CTI3   ", 'DESCRIPTOR "ChromIQ research benchmark (synthetic)"',
             'ORIGINATOR "ChromIQ benchmarks.research"', 'DEVICE_CLASS "OUTPUT"',
             f'COLOR_REP "{printer.color_rep}"']
    if printer.tac is not None and not printer.is_additive:
        lines.append(f'TOTAL_INK_LIMIT "{printer.tac:g}"')
    if sf:
        lines += [f'SPECTRAL_BANDS "{len(LAM_10)}"', 'SPECTRAL_START_NM "380"',
                  'SPECTRAL_END_NM "730"']
    lines += [f"NUMBER_OF_FIELDS {1 + len(fields) + len(sf)}", "BEGIN_DATA_FORMAT",
              "SAMPLE_ID " + " ".join(fields + sf), "END_DATA_FORMAT",
              f"NUMBER_OF_SETS {len(device)}", "BEGIN_DATA"]
    for i in range(len(device)):
        row = [str(i + 1)] + [f"{v * 100:.4f}" for v in device[i]]
        row += [f"{v:.5f}" for v in xyz[i]]
        if sf:
            row += [f"{v:.5f}" for v in spec10[i]]
        lines.append(" ".join(row))
    lines.append("END_DATA")
    path = Path(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Dataset records
# ---------------------------------------------------------------------------

@dataclass
class Dataset:
    name: str
    kind: str                              # "synthetic" | "real"
    ti3: Path                              # what the builders get
    n_channels: int
    color_rep: str
    ink_limit: float | None
    printer: TruthPrinter | None = None    # synthetic only
    misread_rows: np.ndarray = field(default_factory=lambda: np.array([], int))
    holdout_device: np.ndarray | None = None      # real only
    holdout_lab: np.ndarray | None = None         # real only (media-relative)
    holdout_xyz: np.ndarray | None = None         # real only (absolute, mean of readings; v3)
    full_ti3: Path | None = None                  # real only (all patches)
    illuminant: str = ""                   # "" = the file's XYZ (D50)
    info: dict = field(default_factory=dict)


# Development vs confirmatory sets (protocol v2, section 1a). The S family
# (September's YNSN printers) was used to tune the engine's defaults
# (agent 7 T8b), so it is in-sample for the engine: DEVELOPMENT only.
DEVELOPMENT = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")


def role_of(name: str) -> str:
    base = name.split("@")[0]
    if base in DEVELOPMENT:
        return "development"
    if base in ("R-Pro300-CanonSG", "R-Pro300-EpsonPremSG"):
        return "development"      # September's held-out charts (agent 7 T8d)
    return "confirmatory"


def synthetic(pid: str, work: Path, n_patches: int = 900, level: str = "typical",
              seed: int = 23, chart_seed: int = 11, illuminant: str = "",
              printers: dict | None = None, chart: str = "september") -> Dataset:
    printers = printers or build_printers()
    p = printers[pid]
    chart_kind = chart
    chart = (make_chart_ecg if chart_kind == "ecg" else make_chart)(p, n_patches, chart_seed)
    detail: dict = {}
    xyz, spec, mis = measure(p, chart, level=level, seed=seed, detail=detail)
    tag = f"{pid}-{level}-s{seed}-c{chart_seed}-n{n_patches}" + ("-ecg" if chart_kind == "ecg" else "")
    ti3 = write_ti3(Path(work) / f"{tag}.ti3", p, chart, xyz, spec)
    name = pid if not illuminant else f"{pid}@{illuminant}"
    return Dataset(name=name,
                   kind="synthetic", ti3=ti3, n_channels=p.n,
                   color_rep=p.color_rep, ink_limit=p.tac, printer=p,
                   misread_rows=mis, illuminant=illuminant,
                   info={"family": p.family, "noise": level, "seed": seed,
                         "chart_seed": chart_seed, "patches": n_patches, "chart": chart_kind,
                         "misreads": int(len(mis)),
                         "isolated_misreads": int(len(detail.get("isolated", []))),
                         "strip_misreads": len(detail.get("strips", [])),
                         "noise_scale": detail.get("noise_scale"),
                         "role": role_of(name)})


def role_v3(name: str) -> str:
    """Protocol v3 (Agent 16): every printer and real set anyone has looked
    at is DEVELOPMENT; only the sealed Z family confirms."""
    return "sealed" if name.split("@")[0].startswith("Z") else "development"


def synthetic_chart(pid: str, work: Path, kind: str, n_patches: int,
                    level: str = "typical", seed: int = 23, chart_seed: int = 11,
                    printers: dict | None = None, variant_prefix: str = "") -> Dataset:
    """Battery v3: a synthetic dataset on a chart of composition ``kind``
    (``charts.CHART_KINDS``: targen at ChromIQ's defaults, ecg, september)."""
    from benchmarks.research import charts
    printers = printers or build_printers()
    p = printers[pid]
    chart = charts.chart_for(p, kind, n_patches, chart_seed)
    detail: dict = {}
    xyz, spec, mis = measure(p, chart, level=level, seed=seed, detail=detail)
    tag = f"{pid}-{level}-s{seed}-{kind}{n_patches}" + (f"-c{chart_seed}" if kind != "targen" else "")
    ti3 = write_ti3(Path(work) / f"{tag}.ti3", p, chart, xyz, spec)
    return Dataset(name=pid, kind="synthetic", ti3=ti3, n_channels=p.n,
                   color_rep=p.color_rep, ink_limit=p.tac, printer=p,
                   misread_rows=mis,
                   info={"family": p.family, "noise": level, "seed": seed,
                         "chart": kind, "chart_seed": chart_seed if kind != "targen" else None,
                         "patches": int(len(chart)), "misreads": int(len(mis)),
                         "strip_misreads": len(detail.get("strips", [])),
                         "noise_scale": detail.get("noise_scale"),
                         "composition": charts.composition(chart, p.is_additive),
                         "role": role_v3(pid)})


# ---------------------------------------------------------------------------
# Real data
# ---------------------------------------------------------------------------

_NS = {"cc": "http://colorexchangeformat.com/CxF3-core"}


def mxf_to_ti3(src: Path, out: Path, mode: str | None = None) -> dict:
    """CxF3 (i1Profiler .mxf) with RGB or CMYK device values -> Argyll .ti3
    (XYZ under D50 at 1 nm from the 10 nm spectra, plus SPEC fields)."""
    root = ET.parse(src).getroot()
    objs = root.findall(".//cc:Object", _NS)
    targets = [o for o in objs if o.get("ObjectType") == "Target"]
    modes = [m for m in ("M0_Measurement", "M1_Measurement", "M2_Measurement")
             if any(o.get("ObjectType") == m for o in objs)]
    mode = mode or modes[0]
    meas = [o for o in objs if o.get("ObjectType") == mode]
    if len(meas) != len(targets):
        raise ValueError(f"{src.name}: {len(targets)} targets, {len(meas)} readings")
    dev, rep = [], None
    for o in targets:
        c = o.find("cc:DeviceColorValues/cc:ColorCMYK", _NS)
        if c is not None:
            rep = "CMYK"
            dev.append([float(c.find(f"cc:{k}", _NS).text)
                        for k in ("Cyan", "Magenta", "Yellow", "Black")])
            continue
        c = o.find("cc:DeviceColorValues/cc:ColorRGB", _NS)
        rep = "RGB"
        dev.append([float(c.find(f"cc:{k}", _NS).text) * 100 / 255 for k in "RGB"])
    refl, labs, start = [], [], 380.0
    for o in meas:
        sp = o.find("cc:ColorValues/cc:ReflectanceSpectrum", _NS)
        if sp is not None:
            start = float(sp.get("StartWL") or 380)
            refl.append([float(v) for v in sp.text.split()])
            continue
        c = o.find("cc:ColorValues/cc:ColorCIELab", _NS)
        labs.append([float(c.find(f"cc:{k}", _NS).text) for k in "LAB"])
    if refl:
        refl = np.asarray(refl)
        lam = start + 10.0 * np.arange(refl.shape[1])
        # 1 nm by linear interpolation of the 10 nm data (ends held), CIE 15 practice.
        r1 = np.stack([np.interp(colour.LAM_1NM, lam, r) for r in refl])
        xyz = colour.xyz_from_reflectance_1nm(r1, "D50")
    else:
        # Colorimetric-only reference data (FOGRA/IDEAlliance): Lab, D50/2 deg
        refl, lam = None, np.array([])
        xyz = colour.lab_to_xyz(np.asarray(labs))
    dev = np.asarray(dev)
    rep_full = ("iRGB" if rep == "RGB" else rep) + "_XYZ"
    letters = list("RGB") if rep == "RGB" else list("CMYK")
    fields = [f"{rep}_{c}" for c in letters] + ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    sf = [f"SPEC_{int(w)}" for w in lam]
    lines = ["CTI3", 'DESCRIPTOR "converted by benchmarks.research (read-only source)"',
             'ORIGINATOR "ChromIQ benchmarks.research"', 'DEVICE_CLASS "OUTPUT"',
             f'COLOR_REP "{rep_full}"']
    if refl is not None:
        lines += [f'SPECTRAL_BANDS "{len(lam)}"', f'SPECTRAL_START_NM "{lam[0]:g}"',
                  f'SPECTRAL_END_NM "{lam[-1]:g}"']
    lines += [f"NUMBER_OF_FIELDS {1 + len(fields) + len(sf)}", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID " + " ".join(fields + sf), "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    for i in range(len(dev)):
        lines.append(" ".join([str(i + 1)] + [f"{v:.4f}" for v in dev[i]]
                              + [f"{v:.5f}" for v in xyz[i]]
                              + ([f"{v:.6f}" for v in refl[i]] if refl is not None else [])))
    lines.append("END_DATA")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"mode": mode, "patches": len(dev), "rep": rep_full,
            "data": f"spectral {lam[0]:g}-{lam[-1]:g}/10 nm" if refl is not None
            else "Lab only (D50/2)"}


def _ti3_table(text: str):
    fm = re.search(r"BEGIN_DATA_FORMAT\s*(.*?)\s*END_DATA_FORMAT", text, re.S)
    fields = fm.group(1).split()
    dm = re.search(r"BEGIN_DATA\s*\n(.*?)\nEND_DATA", text, re.S)
    rows = [ln for ln in dm.group(1).splitlines() if ln.strip()]
    return fields, rows, dm


def _parse_rows(fields, rows):
    import shlex
    return [shlex.split(r) for r in rows]


def device_groups(dev: np.ndarray, decimals: int = 4) -> tuple[np.ndarray, int]:
    """Group rows by exact device value (rounded to 1e-4 of full scale, below
    any chart's quantisation). -> (group id per row, number of groups)."""
    _, gid = np.unique(np.round(dev, decimals), axis=0, return_inverse=True)
    gid = np.asarray(gid).reshape(-1)
    return gid, int(gid.max()) + 1


def holdout_leak(train_dev: np.ndarray, hold_dev: np.ndarray,
                 decimals: int = 4) -> int:
    """How many held-out device values also occur in training (must be 0)."""
    tr = {tuple(r) for r in np.round(train_dev, decimals)}
    return int(sum(tuple(r) in tr for r in np.round(hold_dev, decimals)))


def real_split(name: str, src_ti3: Path, work: Path, holdout_frac: float = 0.10,
               seed: int = 4242, info: dict | None = None) -> Dataset:
    """Held-out split of a real .ti3 (never modifies the source).

    v2 (flaw 2): rows are first grouped by device value and the split is
    made over the GROUPS, so every exact duplicate of a held-out patch is
    held out with it (v1 split rows, which leaked 17 % of CanonSG's held-out
    patches through duplicates left in training). A held-out device value is
    scored once, against the mean XYZ of all its readings. White, the
    darkest patch and every single-ink solid stay in training (with all
    their duplicates)."""
    text = Path(src_ti3).read_text(errors="replace", encoding="utf-8")
    fields, rows, dm = _ti3_table(text)
    vals = _parse_rows(fields, rows)
    rep = re.search(r'COLOR_REP\s+"([^"]+)"', text).group(1)
    dev_rep = rep.split("_")[0]
    prefix = "RGB" if dev_rep in ("iRGB", "RGB") else dev_rep
    dcols = [i for i, f in enumerate(fields) if f.startswith(prefix + "_")]
    xcols = [fields.index(k) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
    dev = np.array([[float(v[i]) for i in dcols] for v in vals]) / 100.0
    xyz = np.array([[float(v[i]) for i in xcols] for v in vals])
    additive = prefix == "RGB"
    target = 1.0 if additive else 0.0
    gid, ng = device_groups(dev)
    sizes = np.bincount(gid, minlength=ng)
    dist_w = np.abs(dev - target).sum(1)
    prot_rows = set(np.flatnonzero(dist_w <= dist_w.min() + 1e-9))
    y = xyz[:, 1]
    prot_rows |= set(np.flatnonzero(y <= y.min() + 1e-9))
    # single-channel solids stay in (they anchor the table corners)
    solid = (np.isclose(dev, 1.0 - target).sum(1) == 1) & \
            (np.isclose(dev, target).sum(1) == dev.shape[1] - 1)
    prot_rows |= set(np.flatnonzero(solid))
    prot_groups = {int(gid[i]) for i in prot_rows}
    rng = np.random.default_rng(seed)
    order = [g for g in rng.permutation(ng) if int(g) not in prot_groups]
    nho = max(20, int(ng * holdout_frac))
    hold_groups = np.array(sorted(int(g) for g in order[:nho]))
    hold_mask = np.isin(gid, hold_groups)
    keep = [rows[i] for i in range(len(rows)) if not hold_mask[i]]
    new = text[:dm.start(1)] + "\n".join(keep) + text[dm.end(1):]
    new = re.sub(r"NUMBER_OF_SETS\s+\d+", f"NUMBER_OF_SETS {len(keep)}", new)
    work = Path(work)
    train = work / f"{name}-train.ti3"
    train.write_text(new, encoding="utf-8")
    full = work / f"{name}-full.ti3"
    full.write_text(text, encoding="utf-8")
    # media-relative Lab the same way the tables store it: white = the
    # brightest paper patch reading (mean of exact white duplicates)
    wmask = dist_w <= dist_w.min() + 1e-9
    white = xyz[wmask].mean(0)
    hold_dev = np.array([dev[gid == g][0] for g in hold_groups])
    hold_xyz = np.array([xyz[gid == g].mean(0) for g in hold_groups])
    lab = colour.media_relative_lab(hold_xyz, white)
    leak = holdout_leak(dev[~hold_mask], hold_dev)
    if leak:
        raise AssertionError(f"{name}: {leak} held-out device values in training")
    m = re.search(r'TOTAL_INK_LIMIT\s+"?([\d.]+)', text)
    tac = float(m.group(1)) if m and not additive else None
    if tac is None and not additive:
        tac = float(np.round(dev.sum(1).max() * 100.0 + 0.5))
    d = Dataset(name=name, kind="real", ti3=train, n_channels=dev.shape[1],
                color_rep=rep, ink_limit=tac, holdout_device=hold_dev,
                holdout_lab=lab, holdout_xyz=hold_xyz, full_ti3=full,
                info=dict(info or {}, patches=len(dev), device_values=ng,
                          duplicate_groups=int((sizes > 1).sum()),
                          rows_in_duplicate_groups=int(sizes[sizes > 1].sum()),
                          held_out=int(len(hold_groups)),
                          held_out_rows=int(hold_mask.sum()),
                          held_out_with_duplicates=int((sizes[hold_groups] > 1).sum()),
                          holdout_leak=leak,
                          protected_groups=len(prot_groups), split_seed=seed,
                          split="v2: by device value", role=role_of(name)))
    return d


# name: (root, relative path, conversion, provenance note); "xrite" paths are
# resolved against xrite_root() at use, so the location is configurable.
REAL_SOURCES = {
    "R-CMYK-default-i1Pro": ("xrite", "ColorSpaceCMYK/Measurements/CMYK_default-i1Pro.mxf", "mxf",
                             "X-Rite i1Profiler sample: 2033-patch CMYK chart, i1Pro, M0/M1/M2 spectra; printer unknown"),
    "R-CMYK-default-i1iSis": ("xrite", "ColorSpaceCMYK/Measurements/CMYK_default-i1iSis.mxf", "mxf",
                              "X-Rite sample: same 2033-patch layout read on an i1iSis; printer unknown"),
    "R-FOGRA39L": ("xrite", "ColorSpaceCMYK/Measurements/FOGRA39L.mxf", "mxf",
                   "FOGRA39 characterization data (offset, coated), IT8.7/4 1617 patches, M0; averaged reference data"),
    "R-GRACoL2006": ("xrite", "ColorSpaceCMYK/Measurements/GRACoL2006_Coated1_TC1617.mxf", "mxf",
                     "IDEAlliance GRACoL 2006 Coated 1, 1617 patches, M1; averaged reference data"),
    # battery v3 (Agent 16; Agent 11 used them for the commercial reference):
    # SWOP 2006 Grade 3 and 5, the data Adobe's WebCoatedSWOP2006 profiles
    # are built from
    "R-SWOP2006C3": ("xrite", "ColorSpaceCMYK/Measurements/SWOP 2006 Coated 3.mxf", "mxf",
                     "IDEAlliance SWOP 2006 Coated 3 (web offset, grade 3), averaged reference data"),
    "R-SWOP2006C5": ("xrite", "ColorSpaceCMYK/Measurements/SWOP 2006 Coated 5.mxf", "mxf",
                     "IDEAlliance SWOP 2006 Coated 5 (web offset, grade 5), averaged reference data"),
    "R-RGB-default-i1Pro": ("xrite", "ColorSpaceRGB/Measurements/RGB_default-i1Pro.mxf", "mxf",
                            "X-Rite i1Profiler sample RGB chart, i1Pro; printer unknown"),
    "R-Pro300-CanonSG": ("owner", "Canon-Pro300-CanonSG-i1Pro/Canon-Pro300-CanonSG-i1Pro.ti3", "ti3",
                         "owner: Canon PRO-300 on Canon SG, 1168 patches RGB, i1Studio/ColorMunki-class"),
    "R-Pro300-EpsonPremSG": ("owner", "Pro300_EpsonPremSG_i1Studio_Jun26/runs/run1/Pro300_EpsonPremSG_i1Studio_Jun26.ti3", "ti3",
                             "owner: Canon PRO-300 on Epson Premium SG, 924 patches RGB, i1Studio"),
    "R-Knut-printer": ("owner", "Knut-Scanner/runs/run1/Knut-Scanner.ti3", "ti3",
                       "owner/Knut: 315-patch RGB printer chart, ColorMunki-class"),
    # Agent 14 (2026-10-04): the first real N-colour set. Public, free of
    # charge, no login (fogra.org, Ref_FOGRA55.zip v4.0, sha256 of FOGRA55.txt
    # 3c1546db...); read in place, never copied into the repository.
    "R-FOGRA55": ("literature", "a14-fogra55/Ref_FOGRA55/FOGRA55.txt", "cgats-lab",
                  "FOGRA55 (Fogra with GMG, 2021): CMYKOGV ECG reference characterisation, "
                  "4884 patches (ECG-7C test form), Lab M1 D50/2, TAC 300; a designed exchange "
                  "data set (CMYK = FOGRA51), not one press run; noise-free averaged data"),
    # Agent 14: a REAL measured 7-colour press run, public in the ICC
    # registry ("may be copied, distributed, embedded, made, used, and sold
    # without restriction", stated for the registered profile).
    "R-APTEC7C": ("literature", "a14-icc-registry/APTEC_CMYKOGV_Coated_LinearCTV_2025_M1.txt",
                  "cgats-lab",
                  "APTEC (Hong Kong) CMYKOGV coated sheet-fed offset, linear CTV, per ISO/TS 21328, "
                  "M1, 3534 rows (header says 1624), 169 duplicate groups; real measurement"),
}

# Commercial reference profiles made from a real set (in-sample for them),
# and the proxy printer for sets colprof cannot profile (5+ inks).
REFERENCE_ICC = {
    "R-FOGRA55": "a14-fogra55/Ref_FOGRA55/Ref-ECG-CMYKOGV_FOGRA55_TAC300.icc",
    "R-APTEC7C": "a14-icc-registry/APTEC_CMYKOGV_Coated_LinearCTV_2025.icc",
}
LITERATURE = Path.home() / "develop" / "ProfileEngineResearch" / "Literature" / "web"
LITERATURE_ENV = "CHROMIQ_RESEARCH_LITERATURE"


def literature_root() -> Path:
    return Path(os.environ.get(LITERATURE_ENV) or LITERATURE).expanduser()


def reference_icc(name: str) -> Path | None:
    rel = REFERENCE_ICC.get(name)
    return literature_root() / rel if rel else None


_PC_INK = {"cyan": "C", "magenta": "M", "yellow": "Y", "black": "K", "orange": "O",
           "green": "G", "violet": "V", "red": "R", "blue": "B"}


def cgats_lab_to_ti3(src: Path, out: Path) -> dict:
    """ISO 28178 / CGATS characterisation data with PCn_i device fields and
    LAB_L/A/B (D50/2) -> Argyll .ti3 (XYZ from Lab). Ink letters from the
    LGOMCCHANNELnn InkName keywords (FOGRA55 style)."""
    text = Path(src).read_text(errors="replace", encoding="utf-8")
    fmt = re.search(r"BEGIN_DATA_FORMAT\s+(.*?)\s+END_DATA_FORMAT", text, re.S).group(1).split()
    rows = re.search(r"BEGIN_DATA\s+(.*?)\s+END_DATA", text, re.S).group(1).splitlines()
    rows = [r.split() for r in rows if r.strip()]
    rows = [r for r in rows if len(r) >= len(fmt)]      # tolerate trailing tabs
    dcols = [i for i, f in enumerate(fmt) if re.match(r"(PC\d+|\dCLR)_\d+$", f)]
    names = dict(re.findall(r'LGOMCCHANNEL(\d+)\s+"InkName\s*=\s*\'([^\']+)\'', text))
    if names:
        letters = [_PC_INK[names[f"{k + 1:02d}"].lower()] for k in range(len(dcols))]
    else:
        # ink order from the descriptor (APTEC: "APTEC_CMYKOGV_..."); the
        # PLUS_n_COLOR keywords of that file are stale (they name Red where
        # channel 7 measures violet), so they are not used
        m = re.search(r"DESCRIPTOR\s+\"?\S*?_(C?M?Y?K?[A-Z]*)_", text)
        letters = list(m.group(1))[:len(dcols)]
    rep = "".join(letters)
    lab = np.array([[float(r[fmt.index(k)]) for k in ("LAB_L", "LAB_A", "LAB_B")] for r in rows])
    dev = np.array([[float(r[i]) for i in dcols] for r in rows])
    if "XYZ_X" in fmt:
        xyz = np.array([[float(r[fmt.index(k)]) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")] for r in rows])
    else:
        xyz = colour.lab_to_xyz(lab)
    m = re.search(r"TAC\s*(\d+)", Path(src).parent.name + " " + text[:4000])
    fields = [f"{rep}_{c}" for c in letters] + ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    lines = ["CTI3", 'DESCRIPTOR "converted by benchmarks.research (read-only source)"',
             'ORIGINATOR "ChromIQ benchmarks.research"', 'DEVICE_CLASS "OUTPUT"',
             f'COLOR_REP "{rep}_XYZ"', f"NUMBER_OF_FIELDS {1 + len(fields)}",
             "BEGIN_DATA_FORMAT", "SAMPLE_ID " + " ".join(fields), "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    for i in range(len(dev)):
        lines.append(" ".join([str(i + 1)] + [f"{v:.4f}" for v in dev[i]]
                              + [f"{v:.5f}" for v in xyz[i]]))
    lines.append("END_DATA")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"patches": len(dev), "rep": rep + "_XYZ", "data": "Lab only (D50/2, M1)",
            "tac_max_in_data": float(dev.sum(1).max())}


def real_source(name: str) -> tuple[Path, str, str]:
    root, rel, kind, note = REAL_SOURCES[name]
    base = {"xrite": xrite_root, "literature": literature_root}.get(root, lambda: OWNER)()
    return base / rel, kind, note


def real(name: str, work: Path) -> Dataset:
    src, kind, note = real_source(name)
    if not src.exists():
        raise FileNotFoundError(
            f"{name}: {src} not found (i1Profiler data root: {xrite_root()}; "
            f"set {XRITE_ENV} or --i1profiler-data)")
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    info = {"source": str(src), "provenance": note}
    if kind == "mxf":
        conv = work / f"{name}-converted.ti3"
        info.update(mxf_to_ti3(src, conv))
        src = conv
    elif kind == "cgats-lab":
        conv = work / f"{name}-converted.ti3"
        info.update(cgats_lab_to_ti3(src, conv))
        src = conv
    ref = reference_icc(name)
    if ref is not None and ref.exists():
        info["reference_icc"] = str(ref)
    return real_split(name, src, work, info=info)
