"""Measure the per-sheet patch capacity of the two named photo papers added
for 4 x 6 in printers that print 10 x 15 cm or postcard size (jctay, forum
149803; Basti 2026-10-23): "10x15cm" (100 x 150 mm) and "postcard" (100 x 148 mm), for EVERY table in data/patch_db.py that holds a "4x6" entry,
with the flags that table was measured with (see the measure_*_capacity.py
scripts beside this one), so the new rows are measured exactly like the old.

Each table's own "4x6" value is measured again first, as a check of the
method: a mismatch is printed and the run fails.

    python scripts/measure_photo_paper_capacity.py --argyll-bin /Applications/Argyll/bin
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import data.patch_db as DB  # noqa: E402

NEW_PAPERS = ("10x15cm", "postcard")
PT_PAPER = {"10x15cm": "100x150", "postcard": "100x148"}
PT_INSTR = {"i1": "i1", "p3": "3p", "CM": "CM", "SS": "SS"}

#: table -> (margin, patch scale, -P, -L)
TABLES = {
    "_PER_SHEET_CAPACITY": (6, 1.0, False, True),
    "_PER_SHEET_CAPACITY_NO_LB": (6, 1.0, False, False),
    "_PER_SHEET_CAPACITY_M10": (10, 1.0, False, True),
    "_PER_SHEET_CAPACITY_M10_NO_LB": (10, 1.0, False, False),
    "_PER_SHEET_CAPACITY_A095": (6, 0.95, False, True),
    "_PER_SHEET_CAPACITY_A095_NO_LB": (6, 0.95, False, False),
    "_PER_SHEET_CAPACITY_A095_M10": (10, 0.95, False, True),
    "_PER_SHEET_CAPACITY_A095_M10_NO_LB": (10, 0.95, False, False),
    "_PER_SHEET_CAPACITY_P": (6, 1.0, True, True),
    "_PER_SHEET_CAPACITY_NO_LB_P": (6, 1.0, True, False),
    "_PER_SHEET_CAPACITY_M10_P": (10, 1.0, True, True),
    "_PER_SHEET_CAPACITY_M10_NO_LB_P": (10, 1.0, True, False),
    "_PER_SHEET_CAPACITY_A095_P": (6, 0.95, True, True),
    "_PER_SHEET_CAPACITY_A095_NO_LB_P": (6, 0.95, True, False),
    "_PER_SHEET_CAPACITY_A095_M10_P": (10, 0.95, True, True),
    "_PER_SHEET_CAPACITY_A095_M10_NO_LB_P": (10, 0.95, True, False),
    # ColorMunki triple density: the i1Pro layout at -a1.3 -m5 -P
    "_PER_SHEET_CAPACITY_TRIPLE": (5, 1.3, True, True),
    "_PER_SHEET_CAPACITY_TRIPLE_NO_LB": (5, 1.3, True, False),
}


def pages(bin_dir: Path, n: int, args: "list[str]", tmp: Path) -> int:
    for f in tmp.glob("calc*"):
        f.unlink()
    tg = subprocess.run([str(bin_dir / "targen"), "-d2", f"-f{n}", "calc"],
                        capture_output=True, timeout=60, cwd=str(tmp))
    if tg.returncode != 0:
        return 0
    pt = subprocess.run([str(bin_dir / "printtarg")] + args + ["calc"],
                        capture_output=True, timeout=60, cwd=str(tmp))
    if pt.returncode != 0:
        return 0
    return len(list(tmp.glob("calc*.tif")))


def capacity(bin_dir: Path, args: "list[str]", guess: int) -> int:
    """The largest patch count that still fits on one sheet (0: none)."""
    with tempfile.TemporaryDirectory(prefix="chromiq-capacity-") as t:
        tmp = Path(t)
        if pages(bin_dir, 1, args, tmp) != 1:
            return 0
        lo, hi = 1, max(8, int(guess * 1.6))
        while pages(bin_dir, hi, args, tmp) == 1:
            lo, hi = hi, hi * 2
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if pages(bin_dir, mid, args, tmp) == 1:
                lo = mid
            else:
                hi = mid
        return lo


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--argyll-bin", default="/Applications/Argyll/bin")
    ap.add_argument("--out", default="")
    ns = ap.parse_args()
    bin_dir = Path(ns.argyll_bin)
    out: dict = {}
    bad = []
    for name, (margin, scale, nsl, lb) in TABLES.items():
        table = getattr(DB, name)
        triple = "TRIPLE" in name
        rows = ([("CM", False, "4x6")] if triple else
                [k for k in table if k[2] == "4x6"])
        for key in rows:
            instr, dd, _paper = key
            base = table["4x6"] if triple else table[key]
            pt_i = "i1" if triple else PT_INSTR[instr]
            for paper in ("4x6",) + NEW_PAPERS:
                args = [f"-i{pt_i}", f"-p{PT_PAPER.get(paper, paper)}", "-t300", f"-a{scale}",
                        f"-m{margin}", f"-M{margin}"]
                if nsl:
                    args.append("-P")
                if dd:
                    args.append("-h")
                if lb:
                    args.append("-L")
                got = capacity(bin_dir, args, base)
                tag = f"{name} {instr} dd={dd} {paper}"
                print(f"{tag}: {got}" + (f" (stored {base})" if paper == "4x6" else ""),
                      flush=True)
                if paper == "4x6" and got != base:
                    bad.append((tag, got, base))
                if paper != "4x6":
                    out.setdefault(name, {})[
                        paper if triple else f"{instr}|{int(dd)}|{paper}"] = got
    if ns.out:
        Path(ns.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    if bad:
        print("METHOD CHECK FAILED:", bad)
        return 1
    print("method check: every 4x6 value measured as stored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
