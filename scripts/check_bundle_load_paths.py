#!/usr/bin/env python3
"""Fail when a binary in ChromIQ.app loads a library that is not in the app.

The review of 4.3.3-beta.1 (K_review_beta1, CI-1) found the shape of a crash no
existing check could see: numpy's Intel OpenBLAS loads three Fortran runtime
libraries from its own folder (``@loader_path/libgfortran.5.dylib`` ...), the
universal2 merge copied only files that had an arm64 twin, and so the Intel
half of a "universal" app would have died at ``import numpy`` while every
check passed (each file WAS fat; nothing asked whether its dependencies were
there). This resolves every dependency of every architecture slice:

    python scripts/check_bundle_load_paths.py dist/ChromIQ.app

``@loader_path`` resolves against the binary's folder, ``@executable_path``
against Contents/MacOS, ``@rpath`` against each LC_RPATH of the binary (those
are resolved the same way). Absolute system paths (/usr/lib, /System) are
trusted. Anything else must resolve to a file INSIDE the app: a library that
only exists on the build machine (/Library/Frameworks/Python.framework on the
runner, Homebrew's /opt or /usr/local) is missing on the user's Mac, so it is
missing here too (review P_review2_beta1, CI-M2). Exit 1 with a list of
(binary, arch, missing dependency); also exit 1 when there is no app, when it
holds no binary at all, or when otool cannot read one (CI-M1: the check must
never pass because it looked at nothing).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_bundle_min_macos import is_macho  # noqa: E402

_SYSTEM = ("/usr/lib/", "/System/")


class OtoolFailed(RuntimeError):
    pass


def _otool(args: list[str], *, strict: bool = False) -> list[str]:
    r = subprocess.run(["otool", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if strict and r.returncode != 0:
        raise OtoolFailed(r.stderr.strip() or f"otool exit {r.returncode}")
    return r.stdout.splitlines()


def archs(path: Path) -> list[str]:
    out = subprocess.run(["lipo", "-archs", str(path)], capture_output=True,
                         text=True, encoding="utf-8").stdout.split()
    return out or [""]


def deps_and_rpaths(path: Path, arch: str) -> tuple[list[str], list[str]]:
    a = ["-arch", arch] if arch else []
    lines = _otool([*a, "-L", str(path)], strict=True)[1:]
    deps = [l.strip().split(" (")[0] for l in lines if l.strip()]
    rpaths, load = [], _otool([*a, "-l", str(path)])
    for i, l in enumerate(load):
        if l.strip() == "cmd LC_RPATH":
            for nxt in load[i:i + 4]:
                if nxt.strip().startswith("path "):
                    rpaths.append(nxt.strip()[5:].split(" (offset")[0])
                    break
    # otool -L lists the binary's own install name first for a dylib
    own = None
    idl = _otool([*a, "-D", str(path)])
    if len(idl) > 1:
        own = idl[1].strip()
    return [d for d in deps if d != own], rpaths


def _expand(token_path: str, binary: Path, macos_dir: Path) -> Path:
    p = token_path.replace("@loader_path", str(binary.parent))
    p = p.replace("@executable_path", str(macos_dir))
    return Path(os.path.normpath(p))


def _in_app(p: Path, app: Path) -> bool:
    try:
        return p.exists() and os.path.realpath(p).startswith(
            os.path.realpath(app) + os.sep)
    except OSError:
        return False


def resolve(dep: str, binary: Path, rpaths: list[str], macos_dir: Path,
            app: "Path | None" = None) -> bool:
    if app is None:
        app = macos_dir.parent.parent
    if dep.startswith(_SYSTEM):
        return True
    if dep.startswith("@rpath/"):
        rest = dep[len("@rpath/"):]
        return any(_in_app(_expand(r, binary, macos_dir) / rest, app) for r in rpaths)
    if dep.startswith("@"):
        return _in_app(_expand(dep, binary, macos_dir), app)
    return _in_app(Path(dep), app)


def missing(app: Path) -> list[tuple[str, str, str]]:
    macos_dir = app / "Contents" / "MacOS"
    if not macos_dir.is_dir():
        return [(str(app), "-", "not an app bundle (no Contents/MacOS)")]
    bad = []
    checked = 0
    for root, _dirs, files in os.walk(app):
        for name in files:
            p = Path(root) / name
            if p.is_symlink() or not is_macho(p):
                continue
            checked += 1
            for arch in archs(p):
                try:
                    deps, rpaths = deps_and_rpaths(p, arch)
                except OtoolFailed as exc:
                    bad.append((str(p.relative_to(app)), arch or "?",
                                f"otool could not read it: {exc}"))
                    continue
                for d in deps:
                    if not resolve(d, p, rpaths, macos_dir, app):
                        bad.append((str(p.relative_to(app)), arch or "?", d))
    if checked == 0:
        bad.append((str(app), "-", "no binary found, nothing was checked"))
    return bad


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    app = Path(argv[1])
    bad = missing(app)
    if not bad:
        print(f"every library every binary in {app.name} loads is in the app or the system")
        return 0
    print(f"{len(bad)} unresolved dependenc{'y' if len(bad) == 1 else 'ies'}:")
    for rel, arch, dep in sorted(bad):
        print(f"  {arch:<7} {rel}\n          -> {dep}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
