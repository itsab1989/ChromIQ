"""Shared helpers for the Barbieri Spectro 100xy chart tests (a Beta)."""
from __future__ import annotations

import random
from pathlib import Path


def srgb_xyz(r: float, g: float, b: float) -> "tuple[float, float, float]":
    def lin(c):
        c = c / 100.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    R, G, B = lin(r), lin(g), lin(b)
    return (100 * (0.4124 * R + 0.3576 * G + 0.1805 * B),
            100 * (0.2126 * R + 0.7152 * G + 0.0722 * B),
            100 * (0.0193 * R + 0.1192 * G + 0.9505 * B))


def write_ti1(path: Path, n: int, seed: int = 7) -> Path:
    """An RGB .ti1 of *n* patches: white, black, then random colours."""
    rnd = random.Random(seed)
    rows = [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)]
    while len(rows) < n:
        rows.append(tuple(round(rnd.uniform(0, 100), 3) for _ in range(3)))
    lines = ["CTI1   ", "", 'DESCRIPTOR "Argyll Calibration Target chart '
             'information 1"', 'ORIGINATOR "Argyll targen"',
             'CREATED "Sat Oct  3 01:27:48 2026"',
             'APPROX_WHITE_POINT "95.106486 100.000000 108.844025"',
             'COLOR_REP "RGB"', "", "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z ",
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(rows[:n], start=1):
        x, y, z = srgb_xyz(r, g, b)
        lines.append(f"{i} {r:.4f} {g:.4f} {b:.4f} {x:.5f} {y:.5f} {z:.5f} ")
    lines.append("END_DATA")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def barbieri_on():
    """A context: the Beta on for this process, restored afterwards."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        from workflow.barbieri import support
        before = support._latched
        support.set_enabled_for_this_process(True)
        try:
            yield
        finally:
            support._latched = before
    return _ctx()


# ---- synthetic Spectro32 files (the import, step 2) ------------------------
#
# NO TESTER DATA: an owner's real run had 896 readings of a 32 x 28 chart,
# one line per reading in reading order, 41 values from 380 to 780 nm as
# fractions, X Y Z on the 0 to 100 scale. These helpers reproduce that SHAPE
# with values made here from a small synthetic printer.

WAVELENGTHS = tuple(range(380, 781, 10))


def printer_spectrum(dev, scale: float = 100.0):
    """A plausible reflectance spectrum (fractions) for an RGB device value
    (0..100): paper with a little brightener, three inks with broad bands."""
    import numpy as np
    lam = np.asarray(WAVELENGTHS, dtype=float)
    paper = 0.86 + 0.05 * np.exp(-((lam - 440.0) / 25.0) ** 2)

    def band(c, w):
        return np.exp(-((lam - c) / w) ** 2)
    r, g, b = (max(0.0, min(1.0, float(v) / scale)) for v in dev[:3])
    c, m, y = (1 - r) ** 1.1, (1 - g) ** 1.1, (1 - b) ** 1.1
    dens = (1.4 * c * (band(620, 60) + 0.15 * band(480, 60))
            + 1.3 * m * (band(540, 45) + 0.10 * band(430, 40))
            + 1.2 * y * band(440, 35))
    return paper * 10.0 ** (-dens)


def ti2_rows(ti2: Path):
    """{SAMPLE_LOC: device tuple} of a .ti2."""
    text = Path(ti2).read_text(encoding="utf-8", errors="replace")
    fields = text.split("BEGIN_DATA_FORMAT", 1)[1].split(
        "END_DATA_FORMAT", 1)[0].split()
    body = text.split("\nBEGIN_DATA\n", 1)[1].split("END_DATA", 1)[0]
    li = fields.index("SAMPLE_LOC")
    dev = [i for i, f in enumerate(fields) if f.startswith("RGB_")]
    out = {}
    for ln in body.strip().splitlines():
        p = ln.split()
        out[p[li].strip('"')] = tuple(float(p[i]) for i in dev)
    return out


def readings_for(ti2: Path, side: dict, page: int = 0, *,
                 arrangement: str = "straight"):
    """The spectra a Spectro 100xy would read from page *page* of a chart,
    in reading order, with the sheet laid as *arrangement* says
    (`spectro32_import.arrangement_cells`; a reading outside the grid reads
    blank paper)."""
    import numpy as np
    from workflow.barbieri.spectro32_import import arrangement_cells
    pg = side["pages_detail"][page]
    names = pg["reading_order"]
    cols, rows = pg["columns"], pg["rows"]
    dev = ti2_rows(ti2)
    cells = arrangement_cells(arrangement, cols, rows)
    out = []
    for c in cells:
        out.append(printer_spectrum((100, 100, 100)) if c is None
                   else printer_spectrum(dev[names[c]]))
    return np.asarray(out)


def write_spectro32(path: Path, spectra, *, kind: str = "measurements",
                    setting: "tuple[str, str] | None" = ("D50", "2"),
                    template: str = "chart-reflection.TXT",
                    xyz_setting: "tuple[str, str]" = ("D50", "1931_2"),
                    xyz_override=None, decimal_comma: bool = False,
                    replace: "dict | None" = None) -> Path:
    """A file shaped as Spectro32 writes it (tabs, CRLF), from *spectra*
    (fractions). *kind*: "measurements", "val" or "spectrum". *replace*:
    {(reading, column index): text} written in place of a value."""
    import numpy as np
    from workflow.barbieri.spectro32_import import (spectra_xyz, white_xyz,
                                                    xyz_to_lab)
    spectra = np.asarray(spectra, dtype=float)
    xyz = (spectra_xyz(spectra, *xyz_setting) if xyz_override is None
           else np.asarray(xyz_override, dtype=float))
    lab = xyz_to_lab(xyz, white_xyz(*xyz_setting))
    replace = replace or {}

    def num(v):
        s = f"{float(v):.6g}"
        return s.replace(".", ",") if decimal_comma else s

    lines = []
    tail = ["X", "Y", "Z", "x", "y", "L", "a", "b", "u", "v"] + \
        [f"Dens_{c}" for c in ("Ar", "Ag", "Ab", "Mr", "Mg", "Mb", "Tr",
                                "Tg", "Tb", "Vis")]
    if kind == "measurements":
        lines.append("\t".join(["ReadingNumber"] +
                               [f"Spec_{w}" for w in WAVELENGTHS] + tail))
    elif kind == "val":
        lines.append("\t".join([str(w) for w in WAVELENGTHS] +
                               [t.replace("_", " ") for t in tail]) + "\t")
        lines += [template, ""]
        if setting:
            lines.append(f"{setting[0]}  {setting[1]}")
    for k, sp in enumerate(spectra, 1):
        X, Y, Z = xyz[k - 1]
        s = max(X + Y + Z, 1e-9)
        L, a, b = lab[k - 1]
        vals = [num(v) for v in sp]
        if kind != "spectrum":
            vals += [num(X), num(Y), num(Z), num(X / s), num(Y / s), num(L),
                     num(a), num(b), "0", "0"] + ["0.5"] * 10
        if kind == "measurements":
            vals = [str(k)] + vals
        for (rk, ci), text in replace.items():
            if rk == k:
                vals[ci] = text
        lines.append("\t".join(vals) + ("\t" if kind != "measurements"
                                        else ""))
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("cp1252"))
    return path
