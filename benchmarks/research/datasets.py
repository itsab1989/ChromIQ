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
              printers: dict | None = None) -> Dataset:
    printers = printers or build_printers()
    p = printers[pid]
    chart = make_chart(p, n_patches, chart_seed)
    detail: dict = {}
    xyz, spec, mis = measure(p, chart, level=level, seed=seed, detail=detail)
    tag = f"{pid}-{level}-s{seed}-c{chart_seed}-n{n_patches}"
    ti3 = write_ti3(Path(work) / f"{tag}.ti3", p, chart, xyz, spec)
    name = pid if not illuminant else f"{pid}@{illuminant}"
    return Dataset(name=name,
                   kind="synthetic", ti3=ti3, n_channels=p.n,
                   color_rep=p.color_rep, ink_limit=p.tac, printer=p,
                   misread_rows=mis, illuminant=illuminant,
                   info={"family": p.family, "noise": level, "seed": seed,
                         "chart_seed": chart_seed, "patches": n_patches,
                         "misreads": int(len(mis)),
                         "isolated_misreads": int(len(detail.get("isolated", []))),
                         "strip_misreads": len(detail.get("strips", [])),
                         "noise_scale": detail.get("noise_scale"),
                         "role": role_of(name)})


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
                holdout_lab=lab, full_ti3=full,
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
    "R-RGB-default-i1Pro": ("xrite", "ColorSpaceRGB/Measurements/RGB_default-i1Pro.mxf", "mxf",
                            "X-Rite i1Profiler sample RGB chart, i1Pro; printer unknown"),
    "R-Pro300-CanonSG": ("owner", "Canon-Pro300-CanonSG-i1Pro/Canon-Pro300-CanonSG-i1Pro.ti3", "ti3",
                         "owner: Canon PRO-300 on Canon SG, 1168 patches RGB, i1Studio/ColorMunki-class"),
    "R-Pro300-EpsonPremSG": ("owner", "Pro300_EpsonPremSG_i1Studio_Jun26/runs/run1/Pro300_EpsonPremSG_i1Studio_Jun26.ti3", "ti3",
                             "owner: Canon PRO-300 on Epson Premium SG, 924 patches RGB, i1Studio"),
    "R-Knut-printer": ("owner", "Knut-Scanner/runs/run1/Knut-Scanner.ti3", "ti3",
                       "owner/Knut: 315-patch RGB printer chart, ColorMunki-class"),
}


def real_source(name: str) -> tuple[Path, str, str]:
    root, rel, kind, note = REAL_SOURCES[name]
    return (xrite_root() if root == "xrite" else OWNER) / rel, kind, note


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
    return real_split(name, src, work, info=info)
