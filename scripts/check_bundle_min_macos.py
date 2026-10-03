#!/usr/bin/env python3
"""Fail when any binary in ChromIQ.app needs a newer macOS than the app says.

The app declares ``LSMinimumSystemVersion`` 13.0 (ChromIQ.spec). Measured on
the v4.3.2 universal DMG (2026-10-02): 15 binaries required macOS 14.0, the
two native helpers (built on the macos-14 runner with no deployment target)
and numpy's arm64 half (pip on that runner picks numpy's macOS-14 Accelerate
wheel). macOS refuses to launch an executable built for a newer system, so on
Ventura the chart-reading engine and the gamut helper could not run.

    python scripts/check_bundle_min_macos.py dist/ChromIQ.app

Reads every Mach-O file, every architecture slice, and both load commands
that carry a minimum (LC_BUILD_VERSION ``minos``, the older
LC_VERSION_MIN_MACOSX ``version``). Exit 1 and a list when any slice is newer
than the bundle's own LSMinimumSystemVersion.
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

_MACHO_MAGIC = {b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce"}


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.split("."))


def slice_minimums(path: Path) -> dict[str, str]:
    """``{arch: minimum macOS}`` for one Mach-O file."""
    archs = subprocess.run(["lipo", "-archs", str(path)], capture_output=True,
                           text=True, encoding="utf-8").stdout.split() or [""]
    out = {}
    for arch in archs:
        cmd = ["otool", "-l", str(path)] if not arch else ["otool", "-arch", arch, "-l", str(path)]
        lines = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace").stdout.splitlines()
        for i, line in enumerate(lines):
            if line.strip() in ("cmd LC_BUILD_VERSION", "cmd LC_VERSION_MIN_MACOSX"):
                for nxt in lines[i:i + 6]:
                    parts = nxt.split()
                    if parts and parts[0] in ("minos", "version"):
                        out[arch or "?"] = parts[1]
                        break
                break
    return out


def is_macho(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(4) in _MACHO_MAGIC
    except OSError:
        return False


def too_new(app: Path) -> tuple[str, list[tuple[str, str, str]]]:
    """``(declared minimum, [(relative path, arch, minos), ...])``."""
    with open(app / "Contents" / "Info.plist", "rb") as fh:
        declared = plistlib.load(fh).get("LSMinimumSystemVersion", "10.13")
    bad = []
    for root, _dirs, files in os.walk(app):
        for name in files:
            p = Path(root) / name
            if p.is_symlink() or not is_macho(p):
                continue
            mins = slice_minimums(p)
            if not mins:
                # A binary that states no minimum cannot be shown to run on
                # the declared one (review K_review_beta1): refuse it.
                bad.append((str(p.relative_to(app)), "?", "unreadable"))
            for arch, minos in mins.items():
                if _version(minos) > _version(declared):
                    bad.append((str(p.relative_to(app)), arch, minos))
    return declared, bad


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    app = Path(argv[1])
    declared, bad = too_new(app)
    if not bad:
        print(f"every binary in {app.name} runs on macOS {declared} or later")
        return 0
    print(f"{len(bad)} binary slice(s) need a newer macOS than the declared {declared}:")
    for rel, arch, minos in sorted(bad):
        print(f"  {minos:>6}  {arch:<7} {rel}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
