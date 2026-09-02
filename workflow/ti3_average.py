"""Average several scanner ``.ti3`` reads of the **same** target into one.

Scanning the same target several times and combining the reads reduces scanner
noise (Knut #98, ask 1c). ArgyllCMS ``average`` can't do this: it averages the
*measured* fields and requires the *device* (RGB) values to be identical across
files — but for scans the device RGB is exactly what varies read-to-read, so
``average`` aborts with a value-mismatch. So we average the **RGB device
columns** ourselves, keeping each patch's reference XYZ (identical across reads).

Three combine methods, chosen in the UI:

* ``mean`` — plain arithmetic mean. The intuitive default.
* ``geomean`` — geometric mean (Knut's ``average_ti3s_rgbgeom`` approach); a
  little more robust to a single unusually bright/dark scan.
* ``trimmed`` — drop the highest and lowest per channel, mean the rest (needs 3+
  scans; falls back to mean below that). Robust to one bad scan.

Matching is by ``SAMPLE_ID``; every input must describe the same patch set. The
first file is the template for the header/format and all non-RGB columns.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from core.text_io import read_text

_RGB_FIELDS = ("RGB_R", "RGB_G", "RGB_B")
_EPS = 1e-6


class Ti3AverageError(ValueError):
    """The reads can't be averaged (mismatched patch sets / no RGB fields)."""


def _split_block(lines: list[str], begin: str, end: str) -> tuple[int, int]:
    try:
        b = next(i for i, l in enumerate(lines) if l.strip() == begin)
        e = next(i for i, l in enumerate(lines) if l.strip() == end)
    except StopIteration as exc:
        raise Ti3AverageError(f"Malformed .ti3 (missing {begin}/{end}).") from exc
    return b, e


def _parse(path: Path) -> tuple[list[str], list[str], dict[str, list[str]], list[str]]:
    """Return (lines, format_fields, rows_by_id, id_order) for one ``.ti3``."""
    lines = read_text(Path(path)).splitlines()
    fb, fe = _split_block(lines, "BEGIN_DATA_FORMAT", "END_DATA_FORMAT")
    fields = " ".join(lines[fb + 1:fe]).split()
    db, de = _split_block(lines, "BEGIN_DATA", "END_DATA")
    if "SAMPLE_ID" not in fields:
        raise Ti3AverageError("A read has no SAMPLE_ID column.")
    sid = fields.index("SAMPLE_ID")
    rows: dict[str, list[str]] = {}
    order: list[str] = []
    for ln in lines[db + 1:de]:
        if not ln.strip():
            continue
        toks = ln.split()
        if len(toks) != len(fields):
            raise Ti3AverageError("A data row doesn't match the DATA_FORMAT.")
        key = toks[sid].strip('"')
        rows[key] = toks
        order.append(key)
    return lines, fields, rows, order


def _combine(values: list[float], method: str) -> float:
    n = len(values)
    if n == 1:
        return values[0]
    if method == "geomean":
        return math.exp(sum(math.log(max(v, _EPS)) for v in values) / n)
    if method == "trimmed" and n >= 3:
        s = sorted(values)[1:-1]
        return sum(s) / len(s)
    return sum(values) / n                      # mean (and trimmed with < 3)


def average_scanner_ti3(inputs: list[str | Path], output: str | Path,
                        method: str = "mean") -> Path:
    """Average the RGB device columns of *inputs* (scanner ``.ti3`` reads of the
    same target) into *output*. Non-RGB columns and the header come from the
    first read. Returns *output*. Raises :class:`Ti3AverageError` on a mismatch."""
    paths = [Path(p) for p in inputs]
    if len(paths) < 2:
        raise Ti3AverageError("Averaging needs at least two reads.")
    base_lines, fields, base_rows, order = _parse(paths[0])
    rgb_idx = [fields.index(f) for f in _RGB_FIELDS if f in fields]
    if len(rgb_idx) != 3:
        raise Ti3AverageError(
            "These reads have no RGB device columns to average.")

    # Collect every read's rows, keyed by SAMPLE_ID; all must share the key set.
    parsed = [base_rows]
    for p in paths[1:]:
        _, f2, rows2, _ = _parse(p)
        if f2 != fields:
            raise Ti3AverageError(
                "The reads have different columns — they must be scans of the "
                "same target read the same way.")
        if set(rows2) != set(base_rows):
            raise Ti3AverageError(
                "The reads cover different patches — every scan must be of the "
                "same target.")
        parsed.append(rows2)

    # Average RGB per patch, rebuild each data row from the template.
    out_rows: list[str] = []
    for key in order:
        toks = list(base_rows[key])
        for ci in rgb_idx:
            vals = [float(rows[key][ci]) for rows in parsed]
            toks[ci] = f"{_combine(vals, method):.6f}"
        out_rows.append(" ".join(toks))

    db, de = _split_block(base_lines, "BEGIN_DATA", "END_DATA")
    out_lines = base_lines[:db + 1] + out_rows + base_lines[de:]
    out = Path(output)
    out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return out
