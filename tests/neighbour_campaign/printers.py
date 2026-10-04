"""(2a) Printer models: device RGB -> what the instrument reads (XYZ, D50).

    python -m tests.neighbour_campaign.printers      # builds the models once

Each model is a REAL printer profile's forward table (ArgyllCMS ``xicclu -ff
-ia -pX``, absolute colorimetric, so paper white and black are the paper's),
sampled on a 33^3 grid and interpolated trilinearly. The profiles:

==================  =========================================================
``laser_hp``        Knut's HP Color LaserJet CP5550 (#182, beta 8 project
                    ``Printer_HP_CLJ5550_i1Pro2_ChromIQ``, run1, 1944 patches)
``inkjet_glossy``   Canon Pro-300 on Canon semi-gloss (i1Pro), wide gamut
``inkjet_semigloss`` Epson P300 on Epson Premium semi-gloss (i1Studio)
``inkjet_matte``    BUILT HERE by colprof: the Epson readings carried to a
                    matte paper (black lifted to L* 22, chroma 70 % in the
                    darks rising to 90 % in the lights, no brightener), so a
                    low-gamut paper is in the matrix too
==================  =========================================================

A real print is not as smooth as a profile, so :func:`print_noise` adds the
patch-to-patch scatter of a real sheet (default 0.6 ΔE*ab rms) and the
instrument its repeatability (0.1); both are seeded per case.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tests.neighbour_campaign.common import (PRINTERS, argyll, lab_to_xyz,
                                             run_tool, xyz_to_lab)

SOURCES = PRINTERS / "sources"
GRID = 33

PRINTER_PLAN = {
    "laser_hp": {"icc": "Printer_HP_CLJ5550_i1Pro2_ChromIQ.icc",
                 "kind": "laser", "paper": "laser paper (Knut's)"},
    "inkjet_glossy": {"icc": "Canon-Pro300-CanonSG-i1Pro.icc",
                      "kind": "inkjet", "paper": "Canon semi-gloss, wide gamut"},
    "inkjet_semigloss": {"icc": "Pro300_EpsonPremSG_i1Studio_Jun26.icc",
                         "kind": "inkjet", "paper": "Epson Premium semi-gloss"},
    "inkjet_matte": {"icc": "inkjet_matte_sim.icc", "kind": "inkjet",
                     "paper": "matte (simulated from the Epson readings)",
                     "build_from": "Pro300_EpsonPremSG_i1Studio_Jun26.ti3"},
}


def _read_ti3(path: Path):
    """``(rgb[N,3] 0..100, xyz[N,3] 0..100)`` of a CGATS .ti3."""
    lines = path.read_text(errors="replace").splitlines()
    fields = None
    rows = []
    in_fmt = in_data = False
    for ln in lines:
        s = ln.strip()
        if s == "BEGIN_DATA_FORMAT":
            in_fmt = True
            continue
        if s == "END_DATA_FORMAT":
            in_fmt = False
            continue
        if in_fmt:
            fields = (fields or []) + s.split()
            continue
        if s == "BEGIN_DATA":
            in_data = True
            continue
        if s == "END_DATA":
            in_data = False
            continue
        if in_data and s:
            rows.append(s.split())
    ix = {f: i for i, f in enumerate(fields)}
    rgb = np.array([[float(r[ix[f]]) for f in ("RGB_R", "RGB_G", "RGB_B")]
                    for r in rows])
    xyz = np.array([[float(r[ix[f]]) for f in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
                    for r in rows])
    return rgb, xyz


def write_rgb_ti3(path: Path, rgb, xyz, *, locs=None, descriptor="simulated",
                  instrument="GretagMacbeth i1 Pro") -> None:
    """A CTI3 file colprof and ChromIQ read: RGB device values, XYZ readings."""
    out = ["CTI3", "", f'DESCRIPTOR "{descriptor}"',
           'ORIGINATOR "ChromIQ neighbour campaign (simulated)"',
           'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "iRGB_XYZ"',
           f'TARGET_INSTRUMENT "{instrument}"', "", "NUMBER_OF_FIELDS "
           + ("8" if locs is not None else "7"), "BEGIN_DATA_FORMAT",
           "SAMPLE_ID " + ("SAMPLE_LOC " if locs is not None else "")
           + "RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT", "",
           f"NUMBER_OF_SETS {len(rgb)}", "BEGIN_DATA"]
    for i, (d, x) in enumerate(zip(rgb, xyz)):
        loc = f'"{locs[i]}" ' if locs is not None else ""
        out.append(f"{i + 1} {loc}" + " ".join(f"{v:.5f}" for v in d) + " "
                   + " ".join(f"{max(0.0, v):.6f}" for v in x))
    out.append("END_DATA")
    path.write_text("\n".join(out) + "\n")


def _build_matte(src_ti3: Path, name: str) -> Path:
    """colprof a matte-paper profile from glossy readings carried to matte."""
    rgb, xyz = _read_ti3(src_ti3)
    labs = np.array([xyz_to_lab(v) for v in xyz])
    Lw, Lk = labs[:, 0].max(), labs[:, 0].min()
    L_black = 22.0
    out = []
    for L, a, b in labs:
        t = (L - Lk) / max(1e-6, Lw - Lk)
        L2 = L_black + t * (Lw - 1.5 - L_black)
        k = 0.70 + 0.20 * t
        # no brightener: the paper is warmer, and its blue boost is gone
        out.append(lab_to_xyz((L2, a * k + 0.3, b * k + 2.5 * t)))
    work = PRINTERS / "build_matte"
    work.mkdir(parents=True, exist_ok=True)
    write_rgb_ti3(work / f"{name}.ti3", rgb, np.array(out),
                  descriptor="matte paper, simulated from Epson P300 readings")
    run_tool([argyll("colprof"), "-v0", "-qm", "-D", "inkjet matte (simulated)",
              name], cwd=work, timeout=900)
    icc = SOURCES / f"{name}.icc"
    (work / f"{name}.icc").replace(icc)
    return icc


def _sample_icc(icc: Path) -> np.ndarray:
    """The profile's forward table on a GRID^3 lattice: [G,G,G,3] XYZ 0..100."""
    g = np.linspace(0.0, 1.0, GRID)
    pts = np.stack(np.meshgrid(g, g, g, indexing="ij"), axis=-1).reshape(-1, 3)
    text = "\n".join(f"{r:.6f} {gg:.6f} {b:.6f}" for r, gg, b in pts) + "\n"
    out = run_tool([argyll("xicclu"), "-v0", "-ff", "-ia", "-pX", str(icc)],
                   stdin_text=text, timeout=600)
    vals = np.array([[float(v) for v in ln.split()[:3]]
                     for ln in out.splitlines() if ln.strip()])
    if len(vals) != len(pts):
        raise RuntimeError(f"xicclu gave {len(vals)} rows for {len(pts)}")
    if vals[:, 1].max() <= 2.0:            # xicclu's XYZ is 0..1
        vals = vals * 100.0
    return vals.reshape(GRID, GRID, GRID, 3)


class Printer:
    """One printer + paper: :meth:`xyz` maps device RGB (0..100) to XYZ."""

    def __init__(self, name: str, lut: np.ndarray, meta: dict):
        self.name = name
        self.lut = lut
        self.meta = meta
        self.kind = meta.get("kind", "")
        self.paper_xyz = self.xyz(np.array([[100.0, 100.0, 100.0]]))[0]

    def xyz(self, rgb100) -> np.ndarray:
        """Trilinear interpolation in the sampled forward table."""
        rgb = np.clip(np.asarray(rgb100, dtype=float) / 100.0, 0.0, 1.0)
        rgb = np.atleast_2d(rgb)
        f = rgb * (GRID - 1)
        i0 = np.clip(np.floor(f).astype(int), 0, GRID - 2)
        t = f - i0
        out = np.zeros((len(rgb), 3))
        for dr in (0, 1):
            wr = t[:, 0] if dr else 1 - t[:, 0]
            for dg in (0, 1):
                wg = t[:, 1] if dg else 1 - t[:, 1]
                for db in (0, 1):
                    wb = t[:, 2] if db else 1 - t[:, 2]
                    w = (wr * wg * wb)[:, None]
                    out += w * self.lut[i0[:, 0] + dr, i0[:, 1] + dg,
                                        i0[:, 2] + db]
        return out


def print_noise(xyz: np.ndarray, rng: np.random.Generator,
                rms_de: float = 0.6) -> np.ndarray:
    """A real sheet's patch-to-patch scatter: Lab noise of *rms_de* overall."""
    labs = np.array([xyz_to_lab(v) for v in xyz])
    labs = labs + rng.normal(0.0, rms_de / np.sqrt(3.0), labs.shape)
    return np.array([lab_to_xyz(v) for v in labs])


def build_all(force: bool = False) -> dict:
    PRINTERS.mkdir(parents=True, exist_ok=True)
    index = {}
    for name, meta in PRINTER_PLAN.items():
        npy = PRINTERS / f"{name}.npy"
        icc = SOURCES / meta["icc"]
        if not icc.exists() and meta.get("build_from"):
            icc = _build_matte(SOURCES / meta["build_from"], icc.stem)
        if force or not npy.exists():
            np.save(npy, _sample_icc(icc))
        p = Printer(name, np.load(npy), meta)
        index[name] = dict(meta, white_lab=[round(v, 2) for v in xyz_to_lab(p.paper_xyz)],
                           black_lab=[round(v, 2) for v in xyz_to_lab(
                               p.xyz(np.array([[0.0, 0.0, 0.0]]))[0])])
    (PRINTERS / "printers.json").write_text(json.dumps(index, indent=1))
    return index


def load(name: str) -> Printer:
    meta = PRINTER_PLAN[name]
    npy = PRINTERS / f"{name}.npy"
    if not npy.exists():
        build_all()
    return Printer(name, np.load(npy), meta)


if __name__ == "__main__":
    print(json.dumps(build_all(), indent=1))
