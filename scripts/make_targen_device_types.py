#!/usr/bin/env python3
"""Regenerate ``workflow/targen_device_types.py``'s table from targen itself.

Runs ``targen -d0`` … ``targen -d15`` in a temporary folder and records the
``COLOR_REP`` each one writes. ``--check`` only compares and exits 1 on a
difference; without it the generated block in the module is rewritten.

    python scripts/make_targen_device_types.py [--argyll /Applications/Argyll/bin] [--check]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "workflow" / "targen_device_types.py"


def generate(argyll_bin: "Path | str") -> "dict[str, str]":
    """``{COLOR_REP: "-d value"}`` as targen writes it, for -d 0..15."""
    exe = Path(argyll_bin) / ("targen.exe" if sys.platform == "win32" else "targen")
    out: "dict[str, str]" = {}
    with tempfile.TemporaryDirectory(prefix="chromiq-devtypes-") as tmp:
        for d in range(16):
            stem = Path(tmp) / f"d{d}"
            subprocess.run([str(exe), f"-d{d}", "-f10", "-e1", "-B1", str(stem)],
                           capture_output=True, timeout=120, check=True)
            text = (stem.with_suffix(".ti1")).read_text(encoding="utf-8", errors="replace")
            m = re.search(r'^COLOR_REP\s+"([^"]+)"', text, re.M)
            if not m:
                raise RuntimeError(f"targen -d{d} wrote no COLOR_REP")
            out[m.group(1)] = str(d)
    return out


def render(table: "dict[str, str]") -> str:
    lines = ['TARGEN_DEVICE_TYPES: "dict[str, str]" = {']
    lines += [f'    "{rep}": "{d}",' for rep, d in table.items()]
    lines.append("}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--argyll", default="/Applications/Argyll/bin")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    table = generate(a.argyll)
    src = MODULE.read_text(encoding="utf-8")
    pat = re.compile(r'(# BEGIN GENERATED[^\n]*\n)(.*?)(\n# END GENERATED)', re.S)
    new = pat.sub(lambda m: m.group(1) + render(table) + m.group(3), src)
    if a.check:
        if new != src:
            print("workflow/targen_device_types.py is out of date with targen")
            return 1
        print("up to date")
        return 0
    MODULE.write_text(new, encoding="utf-8")
    print(f"wrote {len(table)} device types")
    return 0


if __name__ == "__main__":
    sys.exit(main())
