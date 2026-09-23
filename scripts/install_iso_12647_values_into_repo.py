#!/usr/bin/env python3
"""Copy ISO 12647 values into the repository's own data file, PRINTING NONE.

#182, question S-2, answered in principle on 2026-09-23: DIN's legal
department wrote that using only a standard's VALUES, with no images, pages or
texts, is not reproduction. `data/compliance_sets/iso12647.json` is prepared
for that (its `_readme`, the texts that read it, the tests that hold it to
"each set empty or complete"). What is left is to put the numbers in, and
that waits on the owner's explicit go-ahead. This is the one step, done so
that no number ever reaches a terminal, a log, a commit message or a report:

    python scripts/install_iso_12647_values_into_repo.py SOURCE.json            # both sets
    python scripts/install_iso_12647_values_into_repo.py SOURCE.json --set 8    # one
    python scripts/install_iso_12647_values_into_repo.py SOURCE.json --check    # write nothing

SOURCE is a file in the shape `iso12647.json` describes (the template the
Report limits window writes, filled in). Only its `iso_12647_7` /
`iso_12647_8` objects are read; its `_readme`, `_rows` and anything else are
ignored, and the repository file's own `_readme` is kept.

A set is copied only when it is COMPLETE: only row ids ChromIQ knows that
standard limits (`compliance_sets._ISO_ROWS`), every one of them that ChromIQ
can judge present (a row it cannot measure reads ✕ whatever it holds, so it
may be left out), and every cell a finite number or `[number, "should"]`.
Anything else is refused whole, naming the ROW IDS
that are wrong (row ids are ChromIQ's own names, not the standard's content)
and never a value. The output is counts and True/False only.

The source file is never modified.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REPO_FILE = ROOT / "data" / "compliance_sets" / "iso12647.json"
SET_FOR = {"7": "iso_12647_7", "8": "iso_12647_8"}


def _cell_ok(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return math.isfinite(float(v))
    if isinstance(v, list) and len(v) == 2 and v[1] == "should":
        return _cell_ok(v[0])
    return False


def check_set(set_id: str, cells) -> "list[str]":
    """Why *cells* is not a complete set, as sentences naming ROW IDS only."""
    from workflow import compliance_sets as cs

    if not isinstance(cells, dict):
        return [f"{set_id}: not an object"]
    want = set(cs._ISO_ROWS[set_id])
    must = {r for r in want if cs.ROW_BY_ID[r].status in ("now", "build", "ref")}
    got = set(cells)
    why = []
    if got - want:
        why.append(f"{set_id}: rows this standard does not limit: "
                   f"{', '.join(sorted(got - want))}")
    if must - got:
        why.append(f"{set_id}: rows ChromIQ judges that are missing: "
                   f"{', '.join(sorted(must - got))}")
    bad = sorted(r for r in got & want if not _cell_ok(cells[r]))
    if bad:
        why.append(f"{set_id}: cells that are not a number or "
                   f"[number, \"should\"]: {', '.join(bad)}")
    return why


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path)
    ap.add_argument("--set", choices=("7", "8", "both"), default="both")
    ap.add_argument("--check", action="store_true",
                    help="validate and compare only; write nothing")
    ap.add_argument("--target", type=Path, default=REPO_FILE,
                    help=argparse.SUPPRESS)      # for the script's own test
    a = ap.parse_args(argv)

    src, dst = a.source.resolve(), a.target.resolve()
    if src == dst:
        print("refused: the source IS the target file")
        return 2
    try:
        source = json.loads(src.read_text(encoding="utf-8"))
        target = json.loads(dst.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # the exception names a line and column, never a value
        print(f"refused: a file could not be read ({type(exc).__name__})")
        return 2
    if not isinstance(source, dict) or not isinstance(target, dict):
        print("refused: a file is not a JSON object")
        return 2

    ids = list(SET_FOR.values()) if a.set == "both" else [SET_FOR[a.set]]
    problems = [p for sid in ids for p in check_set(sid, source.get(sid))]
    for p in problems:
        print("refused:", p)
    if problems:
        return 1

    for sid in ids:
        print(f"{sid}: {len(source[sid])} cells in the source, all valid; "
              f"already equal in the repository file: "
              f"{target.get(sid) == source[sid]}")
    if a.check:
        print("check only: nothing written")
        return 0

    out = {"_readme": target.get("_readme", "")}
    for sid in SET_FOR.values():
        out[sid] = source[sid] if sid in ids else target.get(sid, {})
    dst.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    back = json.loads(dst.read_text(encoding="utf-8"))
    for sid in ids:
        print(f"{sid}: written, {len(back[sid])} cells, "
              f"equal to the source: {back[sid] == source[sid]}")
    print(f"_readme kept: {back['_readme'] == target.get('_readme', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
