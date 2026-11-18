#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXAMPLE (kept as a pattern; may need adapting): compare two kept build folders file by file,
with wall-clock instants and the checkout and output folder names masked.

    python masked_compare.py KEPT_A REPO_A KEPT_B REPO_B

KEPT_* are the folders identity_driver.py copied its built files into (PB_KEEP); REPO_* the
trees they were built in (their paths appear inside some files). Prints how many files differ
after masking, and the first thirty. Reads only.
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

CLOCK = re.compile(rb"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:[+-]\d\d:\d\d|Z)?|CREATED \"[^\"]*\"")


def norm(p: Path, repo: Path, kept: Path) -> str:
    b = p.read_bytes()
    for s in (str(repo), str(kept)):
        b = b.replace(s.encode(), b"<ROOT>")
    return hashlib.sha256(CLOCK.sub(b"<CLOCK>", b)).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("kept_a", "repo_a", "kept_b", "repo_b"):
        ap.add_argument(name)
    x = ap.parse_args(argv)
    a, ra, b, rb = (Path(v) for v in (x.kept_a, x.repo_a, x.kept_b, x.repo_b))
    fa = {str(p.relative_to(a)): p for p in a.rglob("*") if p.is_file()}
    fb = {str(p.relative_to(b)): p for p in b.rglob("*") if p.is_file()}
    names = sorted(set(fa) | set(fb))
    real = [n for n in names if n not in fa or n not in fb
            or norm(fa[n], ra, a) != norm(fb[n], rb, b)]
    print(f"files {len(names)}, real differences after masking clock + checkout/output folder: "
          f"{len(real)}")
    for n in real[:30]:
        print("  ", n)
    return 1 if real else 0


if __name__ == "__main__":
    sys.exit(main())
