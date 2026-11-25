"""The colours a chart expects of its patches, for the table's row identity check (the new i1iO
chart layout, 25 Nov 2026). Chart side: the table package reads no chart for it, START hands it
this plain dict.

The ``.ti2``'s own XYZ (what targen and a preconditioning profile expect), as D50 L*a*b*. When they
are placeholders (every patch alike, or every patch but the white: a patch set made without a model), the device colours instead,
RGB as sRGB: the check only asks which patch is lighter, greener, bluer than another. With neither,
no expected colours, and why.
"""
from __future__ import annotations

from pathlib import Path

#: linear sRGB to XYZ, adapted to D50 (Bradford)
_SRGB_D50 = ((0.4360747, 0.3850649, 0.1430804), (0.2225045, 0.7168786, 0.0606169),
             (0.0139322, 0.0971045, 0.7141733))
_D50 = (96.42, 100.0, 82.49)


def lab(xyz) -> "tuple[float, float, float]":
    """CIE L*a*b* (D50) of an XYZ on the Y = 100 scale."""
    def f(t):
        return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else (24389.0 / 27.0 * t + 16.0) / 116.0
    fx, fy, fz = (f(max(0.0, float(v)) / w) for v, w in zip(xyz, _D50))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def _srgb_xyz(rgb) -> "tuple[float, float, float]":
    lin = []
    for v in rgb:
        c = min(1.0, max(0.0, float(v) / 100.0))
        lin.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(100.0 * sum(m * v for m, v in zip(row, lin)) for row in _SRGB_D50)


def expected_lab(ti2_path, calibration: bool = False) -> "tuple[dict, str]":
    """``({location: Lab}, "")`` of the chart *ti2_path*, or ``({}, why not)``. A *calibration*
    chart has none: its ramps repeat and its patches are read for themselves."""
    if calibration:
        return {}, "a calibration chart"
    from workflow.measurement_pairing import _first_table
    try:
        text = Path(ti2_path).read_text(encoding="utf-8", errors="replace")
        table = _first_table(text)
    except (OSError, TypeError, ValueError):
        table = None
    if table is None:
        return {}, "the chart cannot be read"
    fields, rows = table
    if "SAMPLE_LOC" not in fields:
        return {}, "the chart names no locations"
    at = {f: i for i, f in enumerate(fields)}
    parts = [r.split() for r in rows]
    parts = [p for p in parts if len(p) >= len(fields)]

    def column(names):
        try:
            idx = [at[n] for n in names]
            return [tuple(float(p[i]) for i in idx) for p in parts]
        except (KeyError, ValueError, IndexError):
            return None
    locs = [p[at["SAMPLE_LOC"]].strip('"') for p in parts]
    xyz = column(("XYZ_X", "XYZ_Y", "XYZ_Z"))
    # (placeholders are all alike, but for the white some charts name truly)
    if xyz and len({tuple(round(v, 3) for v in x) for x in xyz}) > 2:
        return {loc: lab(x) for loc, x in zip(locs, xyz)}, ""
    rgb = column(("RGB_R", "RGB_G", "RGB_B"))
    if rgb and len(set(rgb)) > 1:
        return {loc: lab(_srgb_xyz(c)) for loc, c in zip(locs, rgb)}, ""
    return {}, "the chart names no expected colours"
