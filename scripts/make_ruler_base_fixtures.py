"""Make the ruler check's base fixture: what the i1Pro driver of the base
branch (feat/lights-i1pro3-signals 6de402163, before the ruler check Beta)
puts on the (fake) USB wire for hand-held strip scans of an i1Pro 2 and an
original i1Pro.

The owner's rule (2026-11-14): with the new option off, everything stays as
it was. This script takes i1pro.c, i1pro_imp.c and i1pro_imp.h from git at
BASE, builds native/chartread_helper/tests/i1pro_ruler_scan_test.c with
CQ_BASE against them, runs it and writes tests/data/i1pro_ruler_base_trace.txt.
tests/test_ruler_scan_trace.py compares this tree's option-off trace with it.

    python3 scripts/make_ruler_base_fixtures.py BUILD_DIR

BUILD_DIR is a scratch folder of your choice (created and left there).
Needs git (with BASE), cmake and a C compiler; macOS or Linux.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "6de402163"
FILES = ("i1pro.c", "i1pro_imp.c", "i1pro_imp.h")
OUT = ROOT / "tests" / "data" / "i1pro_ruler_base_trace.txt"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    build = Path(sys.argv[1]).resolve()
    src = build / "base_i1pro"
    src.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", BASE + "^{commit}"],
        check=True, capture_output=True, text=True, encoding="utf-8",
        timeout=60).stdout.strip()
    for name in FILES:
        data = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{commit}:native/instlib/{name}"],
            check=True, capture_output=True, timeout=60).stdout
        (src / name).write_bytes(data)
    cmake = shutil.which("cmake")
    if cmake is None:
        print("cmake not found")
        return 1
    bdir = build / "cmake"
    subprocess.run([cmake, "-S", str(ROOT / "native" / "chartread_helper"),
                    "-B", str(bdir), "-DCMAKE_BUILD_TYPE=Release",
                    f"-DCQ_BASE_I1PRO_DIR={src}"], check=True,
                   capture_output=True, timeout=600)
    subprocess.run([cmake, "--build", str(bdir), "--target",
                    "i1pro_ruler_scan_test_base", "-j", "8"], check=True,
                   capture_output=True, timeout=1200)
    r = subprocess.run([str(bdir / "i1pro_ruler_scan_test_base")], check=True,
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=300)
    if not r.stdout.rstrip().endswith("ALL DONE"):
        raise SystemExit("the harness did not finish")
    OUT.write_text(
        f"# The base branch ({commit[:9]}, before the ruler check Beta): the\n"
        "# fake-USB trace of native/chartread_helper/tests/i1pro_ruler_scan_test.c\n"
        "# built with CQ_BASE against that commit's i1pro.c / i1pro_imp.c /\n"
        "# i1pro_imp.h. Made by scripts/make_ruler_base_fixtures.py; do not edit.\n"
        + r.stdout, encoding="utf-8")
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
