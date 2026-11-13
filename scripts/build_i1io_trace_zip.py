#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the standalone i1iO tester package as one zip.

    python3 scripts/build_i1io_trace_zip.py --out FOLDER

Writes FOLDER/chromiq-i1io-trace-<version>.zip holding one folder with the
program (tools/i1io_trace/: i1io_trace.py, i1io_table.py, i1io_sim.py), its
README.md and ChromIQ's LICENSE. The zip is reproducible: fixed file dates and
order, so the same sources always give the same bytes. The program inside needs
nothing from ChromIQ (tests/test_i1io_trace_tool.py runs it from a clean folder
with ``python -I``).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tools" / "i1io_trace"
FILES = ("README.md", "i1io_trace.py", "i1io_table.py", "i1io_sim.py")
DATE = (2026, 11, 13, 0, 0, 0)


def version() -> str:
    for line in (PKG / "i1io_table.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("TOOL_VERSION = "):
            return line.split('"')[1]
    raise SystemExit("TOOL_VERSION not found")


def build(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    top = f"chromiq-i1io-trace-{version()}"
    target = out / f"{top}.zip"
    entries = [(name, (PKG / name).read_bytes()) for name in FILES]
    entries.append(("LICENSE", (ROOT / "LICENSE").read_bytes()))
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            info = zipfile.ZipInfo(f"{top}/{name}", date_time=DATE)
            info.external_attr = (0o755 if name == "i1io_trace.py" else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path, help="folder for the zip")
    args = ap.parse_args(argv)
    target = build(args.out)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"{target}  sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
