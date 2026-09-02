"""Analyse an ArgyllCMS ``.ti3`` measurement file — the raw data behind a
profile, before any modelling.

A ``.ti3`` is a CGATS table: one device RGB triplet plus the measured XYZ/Lab
(and usually the full spectral reflectance) for every patch on the chart. That
makes it the ground truth a profile is *fitted to*, so it can answer questions
the finished ``.icc`` can only approximate:

  * the **true** paper-white / max-black contrast (from the actual lightest and
    darkest patches, not a model's white/black point);
  * **grey balance** — how neutral the R=G=B patches really measured, i.e. any
    colour cast the profile then has to correct;
  * **gamut reach** — the most saturated colour the paper-and-ink achieved;
  * **measurement sanity** — non-monotonic neutrals or duplicate-patch scatter
    that betray a misread before you build a bad profile;
  * **appearance under other light** — recomputing the numbers from the spectral
    data under D65 / Illuminant A etc.

Pure Python + numpy; no ArgyllCMS call. Spectral maths uses :mod:`workflow.cie_data`
(CIE 1931 2° observer + standard illuminant SPDs); validated to reproduce the
file's own XYZ columns under D50 to ~0.1 %.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from workflow import cie_data
from workflow.icc_info import xyz_to_lab
from core.text_io import read_text

# Reference white for the file's native (D50) Lab — matches xyz_to_lab's default.
_D50_REF = (0.96422, 1.0, 0.82521)

# Selectable illuminants for the spectral "under other light" section.
ILLUMINANTS: dict[str, tuple] = {
    "D50": cie_data.IL_D50,
    "D65": cie_data.IL_D65,
    "A (tungsten)": cie_data.IL_A,
    "F5 (fluor.)": cie_data.IL_F5,
    "F8 (fluor.)": cie_data.IL_F8,
}


class Ti3ParseError(ValueError):
    """Raised when a file is not a usable CGATS ``.ti3`` measurement."""


# CGATS keyword that marks a measurement as a colour-managed *verification*
# read (printed through a profile) — not raw profiling data. The Measure tab
# writes it; the inspector reads it to default into Verify mode.
VERIFICATION_KEYWORD = "CHROMIQ_VERIFICATION"


def mark_verification_ti3(src: str | Path) -> Path:
    """Rename a freshly-measured ``.ti3`` to ``<stem>-verify.ti3`` and tag it
    with the :data:`VERIFICATION_KEYWORD`, marking it as a colour-managed
    verification measurement that must **not** be used to build a profile.

    Returns the new path. If the source is already so named/tagged it is left in
    place. The keyword is declared with a ``KEYWORD`` line so ArgyllCMS tools
    still parse the file."""
    src = Path(src)
    dst = (src if src.stem.endswith("-verify")
           else src.with_name(f"{src.stem}-verify{src.suffix}"))
    text = read_text(src, lenient=True)
    if VERIFICATION_KEYWORD not in text:
        lines = text.splitlines()
        at = 1 if lines and lines[0].strip().startswith("CTI3") else 0
        lines[at:at] = [f'KEYWORD "{VERIFICATION_KEYWORD}"',
                        f'{VERIFICATION_KEYWORD} "true"']
        text = "\n".join(lines) + "\n"
    dst.write_text(text, encoding="utf-8")
    if dst != src and src.exists():
        src.unlink()
    return dst


def is_verification_ti3(data: "Ti3Data") -> bool:
    """True if a parsed measurement carries the verification marker."""
    return str(data.keywords.get(VERIFICATION_KEYWORD, "")).lower() == "true"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
@dataclass
class Ti3Data:
    """Parsed contents of a ``.ti3`` file."""
    path: Path
    keywords: dict[str, str]
    fields: list[str]
    rows: list[list[str]]
    rgb: np.ndarray                # (N, 3), device 0–100
    xyz: np.ndarray                # (N, 3), measured XYZ 0–100 (D50)
    spectral: np.ndarray | None    # (N, B) reflectance %, or None
    wavelengths: np.ndarray | None  # (B,) nm, or None
    sample_ids: list[str] = field(default_factory=list)  # CGATS SAMPLE_ID per row
    sample_locs: list[str] = field(default_factory=list)  # CGATS SAMPLE_LOC (profcheck's id)

    @property
    def n_patches(self) -> int:
        return len(self.rows)

    @property
    def has_spectral(self) -> bool:
        return self.spectral is not None


_KW_RE = re.compile(r'^([A-Z][A-Z0-9_]*)\s+"?(.*?)"?\s*$')


def parse_ti3(path: str | Path) -> Ti3Data:
    """Parse a ``.ti3`` (CGATS) file. Raises :class:`Ti3ParseError` on anything
    that isn't a readable measurement table with device + XYZ/Lab data."""
    p = Path(path)
    try:
        text = read_text(p, lenient=True)
    except OSError as exc:
        raise Ti3ParseError(str(exc)) from exc
    lines = text.splitlines()

    keywords: dict[str, str] = {}
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith(("BEGIN_", "END_", "NUMBER_OF")):
            continue
        m = _KW_RE.match(s)
        if m and m.group(2) != "":
            keywords.setdefault(m.group(1), m.group(2))

    try:
        fmt_start = next(i for i, ln in enumerate(lines)
                         if ln.strip() == "BEGIN_DATA_FORMAT")
        fields = lines[fmt_start + 1].split()
        data_start = next(i for i, ln in enumerate(lines)
                          if ln.strip() == "BEGIN_DATA")
        data_end = next(i for i, ln in enumerate(lines)
                        if ln.strip() == "END_DATA")
    except (StopIteration, IndexError) as exc:
        raise Ti3ParseError(
            "Not a CGATS measurement file (missing DATA_FORMAT / DATA).") from exc

    rows = [ln.split() for ln in lines[data_start + 1:data_end] if ln.strip()]
    if not rows:
        raise Ti3ParseError("The measurement table is empty.")

    def col(name: str) -> int | None:
        return fields.index(name) if name in fields else None

    rgb_i = [col(f"RGB_{c}") for c in "RGB"]
    xyz_i = [col(f"XYZ_{c}") for c in "XYZ"]
    lab_i = [col(f"LAB_{c}") for c in ("L", "A", "B")]
    if any(i is None for i in rgb_i):
        raise Ti3ParseError("No device RGB columns — only RGB charts are supported.")

    def grab(idx: list[int]) -> np.ndarray:
        return np.array([[float(r[i]) for i in idx] for r in rows], dtype=float)

    rgb = grab(rgb_i)

    if all(i is not None for i in xyz_i):
        xyz = grab(xyz_i)
    elif all(i is not None for i in lab_i):
        lab = grab(lab_i)
        xyz = _lab_to_xyz_array(lab)
    else:
        raise Ti3ParseError("No XYZ or Lab columns in the measurement.")

    spectral = wavelengths = None
    spec_i = [i for i, f in enumerate(fields) if f.startswith("SPEC_")]
    if len(spec_i) >= 3 and "SPECTRAL_BANDS" in keywords:
        try:
            bands = int(keywords["SPECTRAL_BANDS"])
            lo = float(keywords["SPECTRAL_START_NM"])
            hi = float(keywords["SPECTRAL_END_NM"])
            if len(spec_i) == bands:
                spectral = np.array([[float(r[i]) for i in spec_i] for r in rows])
                wavelengths = np.linspace(lo, hi, bands)
        except (ValueError, KeyError):
            spectral = wavelengths = None

    sid_i = col("SAMPLE_ID")
    sample_ids = ([r[sid_i] for r in rows] if sid_i is not None
                  else [str(i + 1) for i in range(len(rows))])
    loc_i = col("SAMPLE_LOC")
    sample_locs = ([r[loc_i].strip('"') for r in rows] if loc_i is not None
                   else list(sample_ids))

    return Ti3Data(p, keywords, fields, rows, rgb, xyz, spectral, wavelengths,
                   sample_ids=sample_ids, sample_locs=sample_locs)


def _f_inv(t: float) -> float:
    return t ** 3 if t ** 3 > 216.0 / 24389.0 else (116.0 * t - 16.0) / (24389.0 / 27.0)


def _lab_to_xyz_array(lab: np.ndarray) -> np.ndarray:
    out = np.empty_like(lab)
    for k, (L, a, b) in enumerate(lab):
        fy = (L + 16.0) / 116.0
        fx = fy + a / 500.0
        fz = fy - b / 200.0
        out[k] = [_f_inv(fx) * _D50_REF[0] * 100.0,
                  _f_inv(fy) * _D50_REF[1] * 100.0,
                  _f_inv(fz) * _D50_REF[2] * 100.0]
    return out


# ---------------------------------------------------------------------------
# Spectral integration (1 nm grid over the measured range)
# ---------------------------------------------------------------------------
class _Integrator:
    """Reflectance → XYZ under a chosen illuminant, on a 1 nm grid."""

    def __init__(self, wavelengths: np.ndarray):
        lo, hi = float(wavelengths[0]), float(wavelengths[-1])
        self.src = wavelengths
        self.grid = np.arange(math.ceil(lo), math.floor(hi) + 1, 1.0)
        self.xb = self._rs(cie_data.OBS_1931_2_X)
        self.yb = self._rs(cie_data.OBS_1931_2_Y)
        self.zb = self._rs(cie_data.OBS_1931_2_Z)

    def _rs(self, table: tuple) -> np.ndarray:
        lo, hi, vals = table
        return np.interp(self.grid, np.linspace(lo, hi, len(vals)), vals,
                         left=0.0, right=0.0)

    def white_xyz(self, illum: tuple) -> np.ndarray:
        I = self._rs(illum)
        k = 100.0 / float(np.sum(I * self.yb))
        return k * np.array([np.sum(I * self.xb), np.sum(I * self.yb),
                             np.sum(I * self.zb)])

    def reflect_xyz(self, refl_pct: np.ndarray, illum: tuple) -> np.ndarray:
        """XYZ (0–100, Y=100 for a perfect diffuser) of a reflectance spectrum."""
        R = np.interp(self.grid, self.src, refl_pct / 100.0, left=0.0, right=0.0)
        I = self._rs(illum)
        k = 100.0 / float(np.sum(I * self.yb))
        return k * np.array([np.sum(R * I * self.xb), np.sum(R * I * self.yb),
                             np.sum(R * I * self.zb)])


# ---------------------------------------------------------------------------
# Analysis result
# ---------------------------------------------------------------------------
@dataclass
class IlluminantPoint:
    name: str
    lab: tuple[float, float, float]   # paper white, ref = perfect diffuser
    contrast_ratio: float


@dataclass
class Ti3Analysis:
    data: Ti3Data
    # contrast (measured, native D50)
    white_lab: tuple[float, float, float]
    black_lab: tuple[float, float, float]
    contrast_ratio: float
    dynamic_range: float
    delta_lstar: float
    # grey balance
    n_neutral: int
    max_cast: float                 # largest C* among neutral patches
    max_cast_lstar: float
    mean_cast: float
    cast_token: str                 # tendency code (warm/cool/green/magenta/neutral/none)
    # gamut
    max_chroma: float
    max_chroma_hue: float           # degrees
    primary_chroma: dict[str, float]
    has_rolloff: bool               # full-ink primaries roll off (possible hidden CM)
    # quality
    neutral_non_monotonic: int
    duplicate_max_de: float | None  # max ΔEab between repeated device values
    duplicate_count: int
    # spectral
    illuminant_points: list[IlluminantPoint] = field(default_factory=list)
    paper_shift_d50_d65: float | None = None   # ΔEab of paper tint D50→D65
    # verification support (used when the chart was printed through a profile)
    media_white_xyz: tuple[float, float, float] = (0.0, 0.0, 0.0)  # lightest patch, 0–100
    neutral_xyz: np.ndarray | None = None       # (n_neutral, 3) XYZ 0–100 of R=G=B patches


def analyse_ti3(data: Ti3Data) -> Ti3Analysis:
    xyz = data.xyz
    lab = np.array([xyz_to_lab((x / 100.0, y / 100.0, z / 100.0))
                    for x, y, z in xyz])
    Y = xyz[:, 1]

    # --- contrast: lightest vs darkest measured patch ----------------------
    wi, bi = int(np.argmax(Y)), int(np.argmin(Y))
    yw, yb = float(Y[wi]), float(Y[bi])
    ratio = yw / yb if yb > 0 else float("inf")
    drange = math.log10(ratio) if ratio > 0 and math.isfinite(ratio) else 0.0
    white_lab = tuple(float(v) for v in lab[wi])
    black_lab = tuple(float(v) for v in lab[bi])
    dl = white_lab[0] - black_lab[0]

    # --- grey balance: neutral (R≈G≈B) patches -----------------------------
    rgb = data.rgb
    spread = rgb.max(axis=1) - rgb.min(axis=1)
    neutral = spread <= 0.5
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    if neutral.any():
        ncast = chroma[neutral]
        mi = int(np.argmax(ncast))
        neutral_idx = np.where(neutral)[0]
        worst = neutral_idx[mi]
        max_cast = float(ncast[mi])
        max_cast_lstar = float(lab[worst, 0])
        mean_cast = float(ncast.mean())
        a_m, b_m = float(lab[neutral, 1].mean()), float(lab[neutral, 2].mean())
        cast_token = _cast_token(a_m, b_m)
    else:
        max_cast = max_cast_lstar = mean_cast = 0.0
        cast_token = "none"

    # --- gamut extremes ----------------------------------------------------
    ci = int(np.argmax(chroma))
    max_chroma = float(chroma[ci])
    hue = math.degrees(math.atan2(lab[ci, 2], lab[ci, 1])) % 360.0
    prim = _primary_chroma(lab, chroma)
    rolloff = _detect_rolloff(rgb, chroma)

    # --- measurement quality ----------------------------------------------
    nm = _neutral_non_monotonic(rgb, lab, neutral)
    dup_de, dup_n = _duplicate_scatter(rgb, lab)

    res = Ti3Analysis(
        data=data, white_lab=white_lab, black_lab=black_lab,
        contrast_ratio=ratio, dynamic_range=drange, delta_lstar=dl,
        n_neutral=int(neutral.sum()), max_cast=max_cast,
        max_cast_lstar=max_cast_lstar, mean_cast=mean_cast,
        cast_token=cast_token, max_chroma=max_chroma,
        max_chroma_hue=hue, primary_chroma=prim, has_rolloff=rolloff,
        neutral_non_monotonic=nm, duplicate_max_de=dup_de, duplicate_count=dup_n,
        media_white_xyz=tuple(float(v) for v in xyz[wi]),
        neutral_xyz=(xyz[neutral].copy() if neutral.any() else None),
    )

    # --- spectral: under other light --------------------------------------
    if data.has_spectral:
        _add_spectral(res, data, wi, bi)
    return res


def _cast_token(a: float, b: float) -> str:
    """Tendency code for the neutral cast (the dialog turns it into localised
    text). One of: neutral / magenta / green / warm / cool."""
    if math.hypot(a, b) < 0.5:
        return "neutral"
    if abs(a) >= abs(b):
        return "magenta" if a > 0 else "green"
    return "warm" if b > 0 else "cool"


def _primary_chroma(lab: np.ndarray, chroma: np.ndarray) -> dict[str, float]:
    hues = (np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360.0)
    out: dict[str, float] = {}
    sectors = {"red": (330, 30), "yellow": (60, 120), "green": (120, 180),
               "cyan": (180, 240), "blue": (240, 300), "magenta": (300, 330)}
    for name, (lo, hi) in sectors.items():
        if lo > hi:
            sel = (hues >= lo) | (hues < hi)
        else:
            sel = (hues >= lo) & (hues < hi)
        out[name] = float(chroma[sel].max()) if sel.any() else 0.0
    return out


def _detect_rolloff(rgb: np.ndarray, chroma: np.ndarray) -> bool:
    """Detect the 'secretly colour-managed chart' signature: full-ink chromatic
    primaries notably *less* saturated than mid-tone ones — a hint the driver
    applied colour management despite a 'No Correction' setting. Conservative;
    False when nothing stands out."""
    hi = rgb.max(axis=1)
    lo = rgb.min(axis=1)
    full = (hi > 95) & (lo < 5) & (chroma > 5)        # full-ink primaries
    strong = (hi > 70) & (lo < 30) & (chroma > 5)     # strong mid-tone chromatics
    if full.sum() < 3 or strong.sum() < 5:
        return False
    return bool(chroma[full].max() < 0.7 * chroma[strong].max())


def _neutral_non_monotonic(rgb: np.ndarray, lab: np.ndarray,
                           neutral: np.ndarray) -> int:
    """Count steps where lightness falls as device grey level rises (beyond
    measurement noise) — a fingerprint of a misread strip."""
    idx = np.where(neutral)[0]
    if idx.size < 3:
        return 0
    level = rgb[idx].mean(axis=1)
    order = np.argsort(level)
    L = lab[idx][order, 0]
    drops = np.diff(L)
    return int(np.sum(drops < -1.0))


def _duplicate_scatter(rgb: np.ndarray, lab: np.ndarray) -> tuple[float | None, int]:
    """Max ΔEab between patches that share the same device RGB (repeat patches),
    a direct read on measurement repeatability. Returns (max_de, n_groups)."""
    keys: dict[tuple, list[int]] = {}
    for i, c in enumerate(rgb):
        keys.setdefault(tuple(np.round(c, 2)), []).append(i)
    worst = 0.0
    groups = 0
    for members in keys.values():
        if len(members) < 2:
            continue
        groups += 1
        sub = lab[members]
        for a in range(len(sub)):
            for b in range(a + 1, len(sub)):
                worst = max(worst, float(np.linalg.norm(sub[a] - sub[b])))
    return (worst if groups else None), groups


def _add_spectral(res: Ti3Analysis, data: Ti3Data, wi: int, bi: int) -> None:
    integ = _Integrator(data.wavelengths)
    white_spec = data.spectral[wi]
    black_spec = data.spectral[bi]
    pts: list[IlluminantPoint] = []
    lab_by_name: dict[str, tuple] = {}
    for name, illum in ILLUMINANTS.items():
        wref = integ.white_xyz(illum)
        wx = integ.reflect_xyz(white_spec, illum)
        bx = integ.reflect_xyz(black_spec, illum)
        ref = (wref[0] / 100.0, wref[1] / 100.0, wref[2] / 100.0)
        wlab = xyz_to_lab((wx[0] / 100.0, wx[1] / 100.0, wx[2] / 100.0), ref)
        ratio = (wx[1] / bx[1]) if bx[1] > 0 else float("inf")
        pts.append(IlluminantPoint(name, tuple(float(v) for v in wlab), ratio))
        lab_by_name[name] = wlab
    res.illuminant_points = pts
    if "D50" in lab_by_name and "D65" in lab_by_name:
        d50, d65 = np.array(lab_by_name["D50"]), np.array(lab_by_name["D65"])
        res.paper_shift_d50_d65 = float(np.linalg.norm(d50 - d65))


# ===========================================================================
# Verification support — used when the .ti3 was printed *through* a profile
# (colour-managed). Inspect mode never touches any of this.
# ===========================================================================

# Hue sectors for the per-direction ΔE breakdown (Lab hue angle, degrees).
_HUE_SECTORS = {"red": (330, 30), "yellow": (30, 90), "green": (90, 165),
                "cyan": (165, 220), "blue": (220, 290), "magenta": (290, 330)}


def ciede2000(lab1: tuple[float, float, float],
              lab2: tuple[float, float, float]) -> float:
    """CIEDE2000 colour difference ΔE₀₀ between two L*a*b* triples (kL=kC=kH=1).

    The modern perceptual metric ArgyllCMS also uses by default; implemented in
    pure Python so the reference-comparison path needs no Argyll call."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2.0
    G = 0.5 * (1.0 - math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7))) if Cbar > 0 else 0.5
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360.0 if (a1p or b1) else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360.0 if (a2p or b2) else 0.0

    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2.0)

    Lbar = (L1 + L2) / 2.0
    Cbarp = (C1p + C2p) / 2.0
    if C1p * C2p == 0:
        hbarp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbarp = (h1p + h2p) / 2.0
    elif h1p + h2p < 360:
        hbarp = (h1p + h2p + 360) / 2.0
    else:
        hbarp = (h1p + h2p - 360) / 2.0

    T = (1 - 0.17 * math.cos(math.radians(hbarp - 30))
         + 0.24 * math.cos(math.radians(2 * hbarp))
         + 0.32 * math.cos(math.radians(3 * hbarp + 6))
         - 0.20 * math.cos(math.radians(4 * hbarp - 63)))
    SL = 1 + (0.015 * (Lbar - 50) ** 2) / math.sqrt(20 + (Lbar - 50) ** 2)
    SC = 1 + 0.045 * Cbarp
    SH = 1 + 0.015 * Cbarp * T
    dTheta = 30 * math.exp(-(((hbarp - 275) / 25) ** 2))
    RC = 2 * math.sqrt(Cbarp ** 7 / (Cbarp ** 7 + 25.0 ** 7)) if Cbarp > 0 else 0.0
    RT = -RC * math.sin(math.radians(2 * dTheta))
    return math.sqrt((dLp / SL) ** 2 + (dCp / SC) ** 2 + (dHp / SH) ** 2
                     + RT * (dCp / SC) * (dHp / SH))


@dataclass
class NeutralResidual:
    """How neutral the greys measured, relative to a chosen white."""
    mean_c: float          # mean residual chroma C* (0 = perfectly neutral)
    worst_c: float
    worst_lstar: float
    cast_token: str        # warm/cool/green/magenta/neutral/none
    basis: str             # "media" | "absolute"


def neutral_residual(res: Ti3Analysis, basis: str = "media") -> NeutralResidual:
    """Residual cast of the neutral patches for *verification* mode.

    ``basis="media"`` measures a*/b* relative to the **paper white** (the right
    reference for a relative-colorimetric print — the paper's own tint is divided
    out, so only the profile's residual error remains). ``basis="absolute"``
    measures relative to D50, the reference for an absolute / paper-simulating
    print. Returns zeros if the file has no neutral patches."""
    if res.neutral_xyz is None or len(res.neutral_xyz) == 0:
        return NeutralResidual(0.0, 0.0, 0.0, "none", basis)
    if basis == "media" and res.media_white_xyz[1] > 0:
        rw = tuple(c / 100.0 for c in res.media_white_xyz)
    else:
        rw = _D50_REF
    labs = np.array([xyz_to_lab((x / 100.0, y / 100.0, z / 100.0), rw)
                     for x, y, z in res.neutral_xyz])
    chroma = np.hypot(labs[:, 1], labs[:, 2])
    wi = int(np.argmax(chroma))
    return NeutralResidual(
        mean_c=float(chroma.mean()), worst_c=float(chroma[wi]),
        worst_lstar=float(labs[wi, 0]),
        cast_token=_cast_token(float(labs[:, 1].mean()), float(labs[:, 2].mean())),
        basis=basis)


@dataclass
class AccuracyResult:
    """Per-patch colour accuracy of a colour-managed print, vs a profile's
    prediction or a reference target."""
    source: str                                  # "profile" | "reference"
    n: int
    mean_de: float
    peak_de: float
    worst_id: str
    worst_hue: str                               # hue-sector name of worst patch
    buckets: dict[str, tuple[float, float, int]]  # name -> (mean, peak, count)


def _hue_sector(a: float, b: float) -> str:
    h = math.degrees(math.atan2(b, a)) % 360.0
    for name, (lo, hi) in _HUE_SECTORS.items():
        if (lo > hi and (h >= lo or h < hi)) or (lo <= hi and lo <= h < hi):
            return name
    return "red"


def _build_accuracy(data: Ti3Data, de_by_id: dict[str, float], source: str,
                    ids: list[str]) -> AccuracyResult | None:
    """Aggregate per-patch ΔE (keyed by ``ids``) into mean/peak/worst plus a
    neutral + 6-hue breakdown, using each patch's measured hue / neutrality."""
    if not de_by_id:
        return None
    lab = np.array([xyz_to_lab((x / 100.0, y / 100.0, z / 100.0))
                    for x, y, z in data.xyz])
    spread = data.rgb.max(axis=1) - data.rgb.min(axis=1)
    by_bucket: dict[str, list[float]] = {k: [] for k in ("neutral", *_HUE_SECTORS)}
    des: list[tuple[float, int]] = []
    for i, pid in enumerate(ids):
        de = de_by_id.get(pid)
        if de is None:
            continue
        des.append((de, i))
        bucket = "neutral" if spread[i] <= 0.5 else _hue_sector(lab[i, 1], lab[i, 2])
        by_bucket[bucket].append(de)
    if not des:
        return None
    worst_de, wi = max(des, key=lambda t: t[0])
    buckets = {name: (float(np.mean(v)), float(np.max(v)), len(v))
               for name, v in by_bucket.items() if v}
    vals = [d for d, _ in des]
    return AccuracyResult(
        source=source, n=len(des), mean_de=float(np.mean(vals)),
        peak_de=float(worst_de), worst_id=ids[wi],
        worst_hue=("neutral" if spread[wi] <= 0.5
                   else _hue_sector(lab[wi, 1], lab[wi, 2])),
        buckets=buckets)


def accuracy_vs_reference(data: Ti3Data,
                          ref_labs: dict[str, tuple[float, float, float]],
                          ) -> AccuracyResult | None:
    """ΔE₀₀ of each measured patch against a reference target Lab (matched by
    SAMPLE_ID). Pure Python — no Argyll."""
    lab = [xyz_to_lab((x / 100.0, y / 100.0, z / 100.0)) for x, y, z in data.xyz]
    de_by_sid: dict[str, float] = {}
    for i, sid in enumerate(data.sample_ids):
        ref = ref_labs.get(sid)
        if ref is not None:
            de_by_sid[sid] = ciede2000(tuple(lab[i]), ref)
    return _build_accuracy(data, de_by_sid, "reference", data.sample_ids)


def accuracy_from_profcheck(data: Ti3Data,
                            patch_errors: list[tuple[str, float]],
                            ) -> AccuracyResult | None:
    """Bucket profcheck's per-patch (id, ΔE) errors by measured hue.

    profcheck already ran the device values through the profile and compared to
    the measurement; we only re-organise its numbers into the neutral/6-hue view.
    profcheck identifies patches by SAMPLE_LOC, so match on that first and fall
    back to SAMPLE_ID for files without locations."""
    des = {pid: de for pid, de in patch_errors}
    res = _build_accuracy(data, des, "profile", data.sample_locs)
    if res is None:
        res = _build_accuracy(data, des, "profile", data.sample_ids)
    return res


def parse_reference_labs(path: str | Path) -> dict[str, tuple[float, float, float]]:
    """Read a reference target's expected Lab from a CGATS file (.ti1/.ti2/.ti3
    or any CGATS table), keyed by SAMPLE_ID. Uses LAB_* directly or converts
    XYZ_* (D50). Raises :class:`Ti3ParseError` if no usable colour columns."""
    p = Path(path)
    try:
        lines = read_text(p, lenient=True).splitlines()
    except OSError as exc:
        raise Ti3ParseError(str(exc)) from exc
    try:
        fi = next(i for i, ln in enumerate(lines) if ln.strip() == "BEGIN_DATA_FORMAT")
        fields = lines[fi + 1].split()
        ds = next(i for i, ln in enumerate(lines) if ln.strip() == "BEGIN_DATA")
        de = next(i for i, ln in enumerate(lines) if ln.strip() == "END_DATA")
    except (StopIteration, IndexError) as exc:
        raise Ti3ParseError("Not a CGATS file (missing DATA_FORMAT / DATA).") from exc
    rows = [ln.split() for ln in lines[ds + 1:de] if ln.strip()]

    def col(name: str) -> int | None:
        return fields.index(name) if name in fields else None

    sid_i = col("SAMPLE_ID")
    lab_i = [col(f"LAB_{c}") for c in ("L", "A", "B")]
    xyz_i = [col(f"XYZ_{c}") for c in "XYZ"]
    out: dict[str, tuple[float, float, float]] = {}
    for n, r in enumerate(rows):
        sid = r[sid_i] if sid_i is not None else str(n + 1)
        if all(i is not None for i in lab_i):
            out[sid] = tuple(float(r[i]) for i in lab_i)
        elif all(i is not None for i in xyz_i):
            x, y, z = (float(r[i]) for i in xyz_i)
            out[sid] = xyz_to_lab((x / 100.0, y / 100.0, z / 100.0))
        else:
            raise Ti3ParseError("Reference has no LAB or XYZ columns.")
    return out
