"""Make tests/data/i1pro2_lights_v4333_trace.txt: what ChromIQ 4.3.33 put on
the (fake) USB wire in one whole i1Pro 2 life, with the lights Beta option off
and on.

The i1Pro 2 lights Beta gained two choices after 4.3.33 (result signals, and
lights left on during a reading). With both choices off the driver must send
exactly what 4.3.33 sent. This script builds the fake-USB harness
native/chartread_helper/tests/i1pro2_lights_modes_test.c against 4.3.33's own
i1pro.c / i1pro_imp.c / i1pro_imp.h (taken from git, commit ee661dc65 = the
4.3.33 merge), runs it, and writes its trace as the fixture.
tests/test_i1pro2_lights_modes.py compares this tree's trace with it.

    python3 scripts/make_lights_v4333_fixture.py BUILD_DIR

BUILD_DIR is a scratch folder of your choice (it is created and left there).
Needs git (with the 4.3.33 commit), cmake and a C compiler; macOS or Linux.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V4333 = "ee661dc653b987d41f3f9612e7b59e9c5badf90f"
FILES = ("i1pro.c", "i1pro_imp.c", "i1pro_imp.h")
OUT = ROOT / "tests" / "data" / "i1pro2_lights_v4333_trace.txt"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    build = Path(sys.argv[1]).resolve()
    src = build / "v4333_i1pro"
    src.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        data = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{V4333}:native/instlib/{name}"],
            check=True, capture_output=True).stdout
        (src / name).write_bytes(data)
    cmake = shutil.which("cmake")
    if cmake is None:
        print("cmake not found")
        return 1
    bdir = build / "cmake"
    subprocess.run([cmake, "-S", str(ROOT / "native" / "chartread_helper"),
                    "-B", str(bdir), "-DCMAKE_BUILD_TYPE=Release",
                    f"-DCQ_V4333_I1PRO_DIR={src}"], check=True,
                   capture_output=True, timeout=600)
    subprocess.run([cmake, "--build", str(bdir), "--target",
                    "i1pro2_lights_modes_test_v4333", "-j", "8"], check=True,
                   capture_output=True, timeout=1200)
    exe = bdir / "i1pro2_lights_modes_test_v4333"
    r = subprocess.run([str(exe)], check=True, capture_output=True, text=True,
                       timeout=120)
    if not r.stdout.rstrip().endswith("ALL DONE"):
        print("the harness did not finish")
        return 1
    OUT.write_text(
        "# ChromIQ 4.3.33 (" + V4333[:9] + "): the fake-USB trace of\n"
        "# native/chartread_helper/tests/i1pro2_lights_modes_test.c built with\n"
        "# CQ_V4333 against 4.3.33's i1pro.c / i1pro_imp.c / i1pro_imp.h.\n"
        "# Made by scripts/make_lights_v4333_fixture.py; do not edit.\n"
        + r.stdout, encoding="utf-8")
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
