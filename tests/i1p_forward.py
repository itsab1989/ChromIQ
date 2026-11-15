"""A forward model of i1Profiler's "Measure Chart" on the i1iO table, for the
tests of `workflow.i1io.measure_chart` (synthetic data only, never a real
person's file).

chart (ChromIQ's own i1iO build) + how the person laid and aimed it -> the
``.cmxf`` i1Profiler would write. PHYSICAL, after the challenge of 2026-11-15
(`sim.py`): the person aims three points on the table; i1Profiler spreads its
grid of R rows x C columns through them as an exact affine grid; at every grid
point a 4 mm aperture sees whatever lies on the sheet there (patches touch
across the strips, a reading off a patch sees paper); the printer is NOT
targen's estimate (dark limit, dot gain, 0.7 chroma, a 7 degree hue turn,
paper tint, noise). The file lists the readings column by column, every
reading and every Target tagged with Page 1 / Row / Column, Targets carry RGB
150/150/150 placeholders and ``NumberPatchPages "0"``, as the real file does.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PAPER = np.array([95.0, 0.6, -4.2])
_WL = np.arange(380, 731, 10, dtype=float)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def write_ti1(path: Path, rgbs) -> Path:
    rows = [f"{i + 1} {r:.4f} {g:.4f} {b:.4f} 50 50 50"
            for i, (r, g, b) in enumerate(rgbs)]
    path.write_text(
        "CTI1\n\nDESCRIPTOR \"x\"\nCOLOR_REP \"RGB\"\n\nNUMBER_OF_FIELDS 7\n"
        "BEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


def build_chart(folder: Path, rgbs, *, paper="A4", seed=11, randomize=True,
                **kw) -> Path:
    """An i1iO chart built by ChromIQ's own engine; returns the ``.ti2``."""
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        from workflow.layout_engine import chart as engine
        folder.mkdir(parents=True, exist_ok=True)
        ti1 = write_ti1(folder / "c.ti1", rgbs)
        engine.build_chart(ti1, folder / "c", instrument="IO2", paper=paper,
                           dpi=72, seed=seed, randomize=randomize, **kw)
    finally:
        support._latched = before
    return folder / "c.ti2"


def chart_sets(rng: "np.random.Generator"):
    """The kinds of chart the tests need: name -> (rgbs, build kwargs)."""
    rand = [tuple(rng.uniform(0, 100, 3)) for _ in range(528)]
    srt = sorted(rand, key=lambda v: 0.3 * v[0] + 0.59 * v[1] + 0.11 * v[2])
    ramps = []
    for ch in "RGBK":
        for i in range(24):
            v = 100 * i / 23
            ramps.append({"R": (v, 0, 0), "G": (0, v, 0), "B": (0, 0, v),
                          "K": (v, v, v)}[ch])
    near = [tuple(rng.uniform(70, 85, 3)) for _ in range(528)]
    few = [tuple(rng.uniform(0, 100, 3)) for _ in range(40)]
    grey = [(v, v, v) for v in rng.uniform(0, 100, 200)]
    return {
        "greys": (grey, dict(seed=4)),
        "random": (rand, dict(seed=11)),
        "sorted": (srt, dict(randomize=False)),
        "ramps": (ramps, dict(randomize=False)),
        "near": (near, dict(seed=2)),
        "small": (few, dict(seed=3)),
    }


# ---------------------------------------------------------------------------
# The sheet and the scan
# ---------------------------------------------------------------------------

@dataclass
class Sheet:
    grid: list            # grid[r][c] = (sample_id, table_x, table_y)
    rgb_of: dict          # sample_id -> device RGB 0..100
    loc_of: dict
    patch: tuple          # (across strips = table y, along = table x) mm
    marks: list           # crosses on the table, aiming order

    @property
    def rows(self) -> int:
        return len(self.grid)

    @property
    def cols(self) -> int:
        return len(self.grid[0])

    def point(self, r: int, c: int) -> tuple:
        return self.grid[r][c][1:]

    def right_aims(self):
        R, C = self.rows, self.cols
        return (self.point(0, 0), self.point(R - 1, 0),
                self.point(R - 1, C - 1))


def load_sheet(ti2: Path) -> Sheet:
    side = json.loads(Path(str(ti2)[:-4] + ".i1io.json").read_text(encoding="utf-8"))
    lines = ti2.read_text(encoding="utf-8").splitlines()
    i = lines.index("BEGIN_DATA") + 1
    rgb_of, loc_of = {}, {}
    while lines[i].strip() != "END_DATA":
        f = lines[i].split()
        rgb_of[int(f[0])] = tuple(float(x) for x in f[2:5])
        loc_of[int(f[0])] = f[1].strip('"')
        i += 1
    h = side["paper_mm"][1]
    strips = sorted(side["pages"][0]["strips"], key=lambda s: s["x_mm"])
    grid = []
    for s in strips:
        cells = sorted(s["patches"], key=lambda q: -q["centre_mm"][1])
        grid.append([(q["sample_id"], h - q["centre_mm"][1], q["centre_mm"][0])
                     for q in cells])
    pw, pl = side["patch_mm"]
    marks = [(h - m["centre_mm"][1], m["centre_mm"][0])
             for m in side["marks_mm"]]
    return Sheet(grid, rgb_of, loc_of, (pw, pl), marks)


def printer_lab(rgb100, rng, noise: float) -> np.ndarray:
    """A printer that is not targen's estimate."""
    s = np.clip(np.asarray(rgb100, float) / 100.0, 0, 1)
    lin = s ** 2.2
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]])
    xyz = M @ lin / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L, a, b = 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])
    L2 = 14 + L * 0.81 + 4 * math.sin(math.pi * L / 100)
    ang = math.radians(7)
    a2 = 0.70 * (a * math.cos(ang) - b * math.sin(ang)) + PAPER[1] * L2 / 100
    b2 = 0.70 * (a * math.sin(ang) + b * math.cos(ang)) + PAPER[2] * L2 / 100
    out = np.array([L2, a2, b2])
    return out + (rng.normal(0, noise, 3) if noise else 0.0)


def _g(c, w):
    return np.exp(-0.5 * ((_WL - c) / w) ** 2)


class InkPrinter:
    """A subtractive CMY printer on a paper (after the review of 2026-11-15:
    reflectance = paper x 10^-(sum of ink densities), with dot gain), for the
    paper kinds the thresholds must hold on. Readings average REFLECTANCE."""

    PAPERS = {"white": lambda: 0.88 + 0.06 * _g(440, 25),
              "cream": lambda: 0.85 - 0.25 * np.clip((480 - _WL) / 100, 0, 1),
              "grey": lambda: np.full_like(_WL, 0.45),
              "dark": lambda: 0.25 + 0.05 * _g(600, 60),
              "matte": lambda: np.full_like(_WL, 0.84)}

    def __init__(self, paper="white", dmax=1.0, gain=0.8, cross=0.08):
        self.paper = self.PAPERS[paper]()
        self.D = np.stack([dmax * (1.5 * _g(630, 45) + cross),
                           dmax * (1.4 * _g(540, 40) + cross),
                           dmax * (1.2 * _g(440, 35) + cross)])
        self.gain = gain

    def spectrum(self, rgb100) -> np.ndarray:
        cmy = np.clip(1.0 - np.asarray(rgb100, float) / 100.0, 0, 1) \
            ** self.gain
        return self.paper * 10.0 ** (-(cmy @ self.D))


#: The paper kinds of the review's sweep (its `PRINTERS`, glossy as in its
#: thresholds run).
PRINTERS = {
    "white": dict(paper="white"),
    "cream": dict(paper="cream"),
    "grey-paper": dict(paper="grey"),
    "dark-paper": dict(paper="dark"),
    "low-gamut": dict(paper="matte", dmax=0.45, gain=0.9),
    "matte": dict(paper="matte", dmax=0.75),
    "glossy": dict(paper="white", dmax=1.2, gain=0.75),
    "glossy-extreme": dict(paper="white", dmax=1.5, gain=0.7),
    "cream-lowgamut": dict(paper="cream", dmax=0.5, gain=0.9),
    "dark-lowgamut": dict(paper="dark", dmax=0.5),
}


def _spectra_lab(sp) -> np.ndarray:
    from workflow.argyll_colorimetry import spectra_to_xyz_like_argyll
    xyz = spectra_to_xyz_like_argyll(np.atleast_2d(sp), _WL)
    w = np.array([96.422, 100.0, 82.521])
    t = xyz / w
    f = np.where(t > 216 / 24389, np.cbrt(t), (24389 / 27 * t + 16) / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]),
                     200 * (f[:, 1] - f[:, 2])], -1)


def reader(sheet: Sheet, rng, noise: float = 0.8, printer=None):
    """What the aperture sees at table point (x, y). With *printer* (an
    `InkPrinter`), the reflectance is averaged and *noise* is relative
    reflectance noise (0.004 = 0.4 %); otherwise L*a*b* is averaged and
    *noise* is in dE."""
    pw, pl = sheet.patch
    cells = [(x, y, sheet.rgb_of[sid]) for row in sheet.grid
             for (sid, x, y) in row]
    XY = np.array([(x, y) for x, y, _ in cells])
    offs = [(dx, dy) for dx in np.linspace(-2, 2, 5)
            for dy in np.linspace(-2, 2, 5) if dx * dx + dy * dy <= 4.1]
    if printer is not None:
        sps = np.array([printer.spectrum(rgb) for _, _, rgb in cells])

        def read_sp(x, y):
            acc = []
            for dx, dy in offs:
                d = np.abs(XY - (x + dx, y + dy))
                hit = np.where((d[:, 0] <= pl / 2) & (d[:, 1] <= pw / 2))[0]
                acc.append(sps[hit[0]] if len(hit) else printer.paper)
            sp = np.mean(acc, axis=0)
            sp = sp * (1.0 + rng.normal(0, noise, sp.shape))
            return _spectra_lab(sp)[0]
        return read_sp
    labs = np.array([printer_lab(rgb, rng, 0.0) for _, _, rgb in cells])

    def read(x, y):
        acc = []
        for dx, dy in offs:
            d = np.abs(XY - (x + dx, y + dy))
            hit = np.where((d[:, 0] <= pl / 2) & (d[:, 1] <= pw / 2))[0]
            acc.append(labs[hit[0]] if len(hit) else PAPER)
        return np.mean(acc, axis=0) + rng.normal(0, noise, 3)
    return read


def scan(read, aims, R: int, C: int) -> list:
    """i1Profiler's grid of R rows x C columns through the three aimed points;
    returns [(row, column, lab)] in its column-major file order."""
    P1, P2, P3 = (np.array(p, float) for p in aims)
    out = []
    for c in range(C):
        for r in range(R):
            p = (P1 + (r / max(R - 1, 1)) * (P2 - P1)
                 + (c / max(C - 1, 1)) * (P3 - P2))
            out.append((r, c, read(*p)))
    return out


def mistakes(sheet: Sheet) -> dict:
    """The aims of the classic mistakes (the challenge's list)."""
    R, C = sheet.rows, sheet.cols
    g = sheet.point
    TL, BL, BR, TR = g(0, 0), g(R - 1, 0), g(R - 1, C - 1), g(0, C - 1)
    dx = g(0, 1)[0] - g(0, 0)[0]
    dy = g(1, 0)[1] - g(0, 0)[1]

    def sh(p, ex, ey):
        return (p[0] + ex, p[1] + ey)
    out = {
        "right": (TL, BL, BR),
        "half-turn": (BR, TR, TL),
        "mirror-along": (TR, BR, BL),
        "mirror-strips": (BL, TL, TR),
        "transposed": (TL, TR, BR),
        "one-patch-along": (sh(TL, dx, 0), sh(BL, dx, 0), sh(BR, dx, 0)),
        "one-strip-down": (sh(TL, 0, dy), sh(BL, 0, dy), sh(BR, 0, dy)),
        "corner1-3.5mm-across": (sh(TL, 0, 3.5), BL, BR),
        "corner3-3.5mm-across": (TL, BL, sh(BR, 0, 3.5)),
        "all-3.5mm-across": (sh(TL, 0, 3.5), sh(BL, 0, 3.5),
                             sh(BR, 0, 3.5)),
        "aim3-one-short": (TL, BL, sh(BR, -dx, 0)),
        "aim2-one-strip-up": (TL, sh(BL, 0, -dy), BR),
        "aim1-one-patch-along": (sh(TL, dx, 0), BL, BR),
    }
    if sheet.marks:
        out["aimed-crosses"] = tuple(sheet.marks)
    return out


# ---------------------------------------------------------------------------
# Spectra and the file
# ---------------------------------------------------------------------------

def _lab_to_xyz_d50(lab) -> np.ndarray:
    L, a, b = lab
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200

    def inv(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    return np.array([96.42 * inv(fx), 100.0 * inv(fy), 82.49 * inv(fz)])


_BASIS = None


def _basis():
    global _BASIS
    if _BASIS is None:
        from workflow.argyll_colorimetry import spectra_to_xyz_like_argyll
        B = np.stack([np.exp(-0.5 * ((_WL - mu) / 45.0) ** 2)
                      for mu in (450.0, 545.0, 610.0)] + [np.ones_like(_WL)])
        W = spectra_to_xyz_like_argyll(B, _WL, clamp=False)   # (4, 3)
        _BASIS = (B, W)
    return _BASIS


def spectrum_for(lab) -> np.ndarray:
    """A smooth reflectance (0..1, 36 bands 380-730 nm) whose D50 XYZ is
    *lab*'s, as close as three bumps and a constant allow."""
    B, W = _basis()
    xyz = _lab_to_xyz_d50(lab)
    # min ||w|| over the 4 weights subject to w @ W = xyz
    w, *_ = np.linalg.lstsq(W.T, xyz, rcond=None)
    s = np.clip(w @ B, 0.003, 1.2)
    return s


def write_cmxf(path: Path, readings, *, columns: int, rows: int,
               pages_attr: str = "0", conditions=("M0",),
               device=(150, 150, 150), drop_reading_tags=False,
               target_cells=None) -> Path:
    """Write the CxF a Measure Chart scan saves. *readings*: [(row, col,
    lab)] in file order. *target_cells*: the Targets' (row, col) when they
    should differ from the readings' (a broken file). *device*: the one
    device value of every Target (the placeholders), or a list of one per
    Target (real device values)."""
    objs = []
    for cond in conditions:
        for k, (r, c, lab) in enumerate(readings):
            sp = " ".join(f"{v:.5f}" for v in spectrum_for(lab))
            tags = "" if drop_reading_tags else (
                '\n    <cc:TagCollection Name="Location">'
                f'<cc:Tag Name="Column" Value="{c}"/>'
                '<cc:Tag Name="Page" Value="1"/>'
                f'<cc:Tag Name="Row" Value="{r}"/>'
                '<cc:Tag Name="SampleID" Value="-1"/>'
                '<cc:Tag Name="SampleName" Value=""/></cc:TagCollection>')
            objs.append(
                f'<cc:Object ObjectType="{cond}_Measurement" '
                f'Name="{cond}_Measurement1" Id="c{k + 1}">\n'
                '    <cc:CreationDate>2026-11-15T10:00:00+01:00'
                '</cc:CreationDate>\n    <cc:ColorValues>'
                '<cc:ReflectanceSpectrum StartWL="380" ColorSpecification='
                f'"{cond}_Measurement_spec">{sp}</cc:ReflectanceSpectrum>'
                f'</cc:ColorValues>{tags}\n</cc:Object>')
    cells = target_cells or [(r, c) for r, c, _ in readings]
    for k, (r, c) in enumerate(cells):
        dv = device[k] if isinstance(device, list) else device
        objs.append(
            f'<cc:Object ObjectType="Target" Name="Target{k + 1}" '
            f'Id="t{k + 1}">\n    <cc:CreationDate>2026-11-15T10:00:00+01:00'
            '</cc:CreationDate>\n    <cc:DeviceColorValues>'
            '<cc:ColorRGB ColorSpecification="Unknown">'
            f'<cc:R>{dv[0]}</cc:R><cc:G>{dv[1]}</cc:G>'
            f'<cc:B>{dv[2]}</cc:B></cc:ColorRGB></cc:DeviceColorValues>\n'
            '    <cc:TagCollection Name="Location">'
            f'<cc:Tag Name="Column" Value="{c}"/>'
            '<cc:Tag Name="Page" Value="1"/>'
            f'<cc:Tag Name="Row" Value="{r}"/>'
            '<cc:Tag Name="SampleID" Value="-1"/>'
            '<cc:Tag Name="SampleName" Value=""/></cc:TagCollection>\n'
            '</cc:Object>')
    specs = "".join(
        f'<cc:ColorSpecification Id="{c}_Measurement_spec"><cc:MeasurementSpec>'
        '<cc:MeasurementType>Spectrum_Reflectance</cc:MeasurementType>'
        '<cc:WavelengthRange StartWL="380" Increment="10"/>'
        '<cc:CalibrationStandard>XRGA</cc:CalibrationStandard>'
        '</cc:MeasurementSpec></cc:ColorSpecification>' for c in conditions)
    mode = "2" if len(conditions) > 1 else "1"
    sel = {"M0": "0", "M1": "1", "M2": "2"}[conditions[0]]
    text = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<cc:CxF xmlns:cc="http://colorexchangeformat.com/CxF3-core">\n'
        '<cc:FileInformation><cc:Creator>X-Rite - Prism</cc:Creator>'
        '<cc:CreationDate>2026-11-15T10:00:00+01:00</cc:CreationDate>'
        '<cc:Tag Name="PrismAppName" Value="i1Profiler"/></cc:FileInformation>\n'
        '<cc:Resources><cc:ObjectCollection>\n' + "\n".join(objs)
        + '\n</cc:ObjectCollection><cc:ColorSpecificationCollection>'
        + specs + '</cc:ColorSpecificationCollection></cc:Resources>\n'
        '<cc:CustomResources><xrp:Prism xmlns:xrp="http://www.xrite.com/'
        'products/prism" release="2.0"><xrp:CustomAttributes '
        'MeasurementDevice="i1iO 2" MeasurementDeviceSerialNumber="000000" '
        f'MeasurementMode="{mode}" Media_Type="Translucent Media" '
        f'NumberPatchColumns="{columns}" NumberPatchPages="{pages_attr}" '
        f'NumberPatchRows="{rows}" PageHeight="50.00" PageWidth="50.00" '
        'PaperFormat="16" PaperOrientation="Landscape" ScramblePatches="False" '
        f'SelectedMeasurementCondition="{sel}" TestChartType=""/>'
        '</xrp:Prism></cc:CustomResources>\n</cc:CxF>\n')
    path.write_text(text, encoding="utf-8")
    return path


def measure(sheet: Sheet, path: Path, aims=None, *, rng=None, noise=0.8,
            typed=None, **kw) -> Path:
    """A Measure Chart file of *sheet* aimed at *aims* (default: right)."""
    rng = rng if rng is not None else np.random.default_rng(1)
    R, C = typed[::-1] if typed else (sheet.rows, sheet.cols)
    read = reader(sheet, rng, noise)
    readings = scan(read, aims or sheet.right_aims(), R, C)
    return write_cmxf(path, readings, columns=C, rows=R, **kw)


def convert(cxf: Path, out_dir: Path) -> Path:
    """The converted copy, exactly as the Measure tab's gated route makes it
    (`measure_chart.convert`: a ``.cmxf`` is not a CxF to the converter)."""
    from workflow.i1io.measure_chart import convert as mc_convert
    return mc_convert(cxf, out_dir)
