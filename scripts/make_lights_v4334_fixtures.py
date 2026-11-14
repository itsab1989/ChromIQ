"""Make the ChromIQ 4.3.34 lights fixtures: what 4.3.34's own drivers put on
the (fake) USB wire in one whole i1Pro 2 life and one whole i1Pro 3 life.

After 4.3.34 the lights Beta's two choices (result signals, lights left on
during a reading) also apply to the i1Pro 3 (2026-11-14). The owner's rule:
with the option off, and with both choices at "as in ChromIQ 4.3.33", nothing
may change on the wire; and the i1Pro 2 must behave as in 4.3.34 in all four
combinations. This script takes i1pro.c, i1pro_imp.c, i1pro_imp.h, i1pro3.c,
i1pro3_imp.c and i1pro3_imp.h from git at the v4.3.34 tag, builds

  * native/chartread_helper/tests/i1pro2_lights_modes_test.c (all four
    combinations: 4.3.34 had them) against 4.3.34's i1Pro 2 driver, and
  * native/chartread_helper/tests/i1pro3_lights_modes_test.c with CQ_V4334
    (option off and "as in 4.3.33" only: 4.3.34 had no i1Pro 3 choices)
    against 4.3.34's i1Pro 3 driver,

runs both and writes tests/data/i1pro2_lights_v4334_trace.txt and
tests/data/i1pro3_lights_v4334_trace.txt.
tests/test_i1pro3_lights_modes.py compares this tree's traces with them.

    python3 scripts/make_lights_v4334_fixtures.py BUILD_DIR

BUILD_DIR is a scratch folder of your choice (it is created and left there).
Needs git (with the v4.3.34 tag), cmake and a C compiler; macOS or Linux.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V4334 = "v4.3.34"
FILES = ("i1pro.c", "i1pro_imp.c", "i1pro_imp.h",
         "i1pro3.c", "i1pro3_imp.c", "i1pro3_imp.h")
OUT2 = ROOT / "tests" / "data" / "i1pro2_lights_v4334_trace.txt"
OUT3 = ROOT / "tests" / "data" / "i1pro3_lights_v4334_trace.txt"


def _run(exe: Path) -> str:
    r = subprocess.run([str(exe)], check=True, capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    if not r.stdout.rstrip().endswith("ALL DONE"):
        raise SystemExit(f"{exe.name} did not finish")
    return r.stdout


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    build = Path(sys.argv[1]).resolve()
    src = build / "v4334_i1pro"
    src.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", V4334 + "^{commit}"],
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
                    f"-DCQ_V4334_I1PRO_DIR={src}"], check=True,
                   capture_output=True, timeout=600)
    targets = ("i1pro2_lights_modes_test_v4334", "i1pro3_lights_modes_test_v4334")
    subprocess.run([cmake, "--build", str(bdir), "--target", *targets,
                    "-j", "8"], check=True, capture_output=True, timeout=1200)
    head = ("# ChromIQ 4.3.34 ({c}): the fake-USB trace of\n"
            "# native/chartread_helper/tests/{t}.c built{d} against 4.3.34's\n"
            "# {f}.\n"
            "# Made by scripts/make_lights_v4334_fixtures.py; do not edit.\n")
    OUT2.write_text(head.format(
        c=commit[:9], t="i1pro2_lights_modes_test", d="",
        f="i1pro.c / i1pro_imp.c / i1pro_imp.h")
        + _run(bdir / targets[0]), encoding="utf-8")
    OUT3.write_text(head.format(
        c=commit[:9], t="i1pro3_lights_modes_test", d=" with CQ_V4334",
        f="i1pro3.c / i1pro3_imp.c / i1pro3_imp.h")
        + _run(bdir / targets[1]), encoding="utf-8")
    print(f"written {OUT2}\nwritten {OUT3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
