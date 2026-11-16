#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Build the standalone i1iO tester package (chromiq-i1io-session) as one zip.

    python3 scripts/build_i1io_session_zip.py --out FOLDER

Writes FOLDER/chromiq-i1io-session-<version>.zip holding one folder with the
program (tools/i1io_session/: i1io_session.py, i1io_session_table.py, i1io_session_sim.py, BYTES.md,
and since 0.5.0 part C's modules, the demo sheet and ChromIQ's reader bin/chromiq-chartread), its
README.md and ChromIQ's LICENSE. The zip is reproducible: fixed file dates and
order, so the same sources always give the same bytes. The program inside needs
nothing from ChromIQ (tests/test_i1io_session_tool.py runs it from a clean folder
with ``python -I``).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tools" / "i1io_session"
FILES = ("README.md", "BYTES.md", "i1io_session.py", "i1io_session_table.py", "i1io_session_sim.py",
         # 0.5.0, part C
         "i1io_part_c.py", "i1io_part_c_sim.py", "i1io_c_lines.py", "i1io_geometry.py",
         "i1io_reader.py", "i1io_scan.py", "demo/demo-sheet.i1io.json",
         "bin/chromiq-chartread")
#: runnable files (the program and the bundled reader)
EXECUTABLE = ("i1io_session.py", "bin/chromiq-chartread")
DATE = (2026, 11, 16, 0, 0, 0)


def version() -> str:
    for line in (PKG / "i1io_session_table.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("TOOL_VERSION = "):
            return line.split('"')[1]
    raise SystemExit("TOOL_VERSION not found")


def build(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    top = f"chromiq-i1io-session-{version()}"
    target = out / f"{top}.zip"
    entries = [(name, (PKG / name).read_bytes()) for name in FILES]
    entries.append(("LICENSE", (ROOT / "LICENSE").read_bytes()))
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            info = zipfile.ZipInfo(f"{top}/{name}", date_time=DATE)
            info.external_attr = (0o755 if name in EXECUTABLE else 0o644) << 16
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
