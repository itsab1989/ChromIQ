"""Survey vendor PPDs for "no colour management" options.

Runs every PPD under one or more directories through ChromIQ's actual
detection heuristic (``workflow.ppd_color.vendor_no_cm_setting``) and reports:

  * which (option, value) the heuristic picks per PPD,
  * PPDs where it finds nothing, **plus every colour-ish option** in those
    PPDs so missed vendor spellings can be added to the regexes,
  * an aggregated summary of (key, value) pairs per top-level directory
    (one directory per vendor is the intended layout).

Used for the 2026-06 multi-vendor survey: PPDs were pulled from Apple's
legacy vendor driver bundles (HewlettPackard/Brother/Canon/EPSON
PrinterDrivers.dmg) via ``pkgutil --expand-full`` — nothing installed.

Usage:
    python scripts/survey_ppd_no_cm.py <ppd-dir> [<ppd-dir> ...]
"""
from __future__ import annotations

import collections
import gzip
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from core.proc_text import decode_output

from workflow.ppd_color import parse_ppd_options, vendor_no_cm_settings  # noqa: E402

# Anything whose option key or UI label matches this is worth showing when the
# heuristic comes up empty (deliberately broader than the detection regexes).
_INTERESTING = ("color", "colour", "match", "manag", "intent", "correct",
                "cmat", "adjust", "icm", "icc", "profile", "rendering")


def _read_ppd(path: pathlib.Path) -> str:
    raw = path.read_bytes()
    if path.suffix == ".gz" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return decode_output(raw, what="the PPD")


def _interesting_options(text: str):
    for key, ui_label, values in parse_ppd_options(text):
        hay = f"{key} {ui_label}".lower()
        if any(t in hay for t in _INTERESTING):
            yield key, ui_label, values


def survey(roots: list[pathlib.Path]) -> None:
    found: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    missed: dict[str, list[pathlib.Path]] = collections.defaultdict(list)
    totals: collections.Counter = collections.Counter()

    for root in roots:
        vendor = root.name
        ppds = sorted(p for p in root.rglob("*")
                      if p.is_file() and p.suffix.lower() in (".ppd", ".gz"))
        for ppd in ppds:
            totals[vendor] += 1
            text = _read_ppd(ppd)
            # vendor_no_cm_setting reads from a path; reuse its parser directly
            # on the decompressed text by writing nothing — call the pure logic:
            hit = _detect(text)
            if hit:
                found[vendor][" ".join(f"{k}={v}" for k, v in hit)] += 1
            else:
                missed[vendor].append(ppd)

    for vendor in sorted(totals):
        print(f"\n=== {vendor}: {totals[vendor]} PPDs ===")
        for sig, n in found[vendor].most_common():
            print(f"  {n:4d} x  {sig}")
        n_missed = len(missed[vendor])
        print(f"  {n_missed:4d} x  NO DETECTION")
        # For the first few misses, dump their colour-ish options verbatim.
        for ppd in missed[vendor][:8]:
            print(f"\n  --- miss: {ppd.name}")
            text = _read_ppd(ppd)
            for key, ui_label, values in _interesting_options(text):
                vals = ", ".join(f"{v}/{vl}" for v, vl in values)
                print(f"      *{key} ({ui_label}): {vals}")


def _detect(text: str):
    """vendor_no_cm_settings, but on already-decompressed text."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".ppd", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        tmp = f.name
    try:
        return vendor_no_cm_settings(tmp)
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    survey([pathlib.Path(a) for a in sys.argv[1:]])
