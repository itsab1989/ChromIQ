#!/usr/bin/env python3
"""Generate the PROVISIONAL master colour set for #133's gamut verification.

The recipe (issue #133 §5.4 requires it to be published so anyone can
regenerate the identical list):

    targen -d2 -e4 -B4 -g32 -t -f5960 -c <Argyll ref/sRGB.icm> <out>

* ``-t`` — Incremental Far Point Distribution: each colour is placed as far
  as possible from everything already picked, so **every prefix is itself a
  well-spread set**. That is §5.2's nesting, by construction; verified for
  this exact recipe by byte-comparing a ``-f960`` run against the first 960
  rows of the ``-f5960`` one (960/960 identical).
* ``-c sRGB.icm`` — spreads the points in perceptual space. sRGB is chosen
  because it is the space ChromIQ's whole verification pipeline already reads
  design values in; the resulting XYZ column is D65-referenced and is
  Bradford-adapted to D50 wherever it is consumed.
* ``-e4 -B4 -g32`` — white, black and a composite-grey axis, because the
  near-neutrals are where the eye is fussiest.

Total: 5 960 colours (4 + 4 + 30 + 5 922 IFP), within the recommended
6 000–8 000 band; nesting means the size costs nothing until printed.

**PROVISIONAL** (§5.4, and the plan's one irreversible decision): this set may
be re-cut freely until somebody outside the project relies on a report naming
it. Freeze it — with a real version number — at that moment, never earlier.

    python scripts/make_verification_master_set.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from workflow.gamut_target import MASTER_SET_ASSET, MASTER_SET_VERSION  # noqa: E402

RECIPE = ["-d2", "-e4", "-B4", "-g32", "-t", "-f5960"]


def main() -> int:
    bin_dir = Path("/Applications/Argyll/bin")
    srgb = bin_dir.parent / "ref" / "sRGB.icm"
    if not (bin_dir / "targen").exists() or not srgb.exists():
        print("ArgyllCMS with targen + ref/sRGB.icm is required.")
        return 2
    out = ROOT / MASTER_SET_ASSET
    out.parent.mkdir(parents=True, exist_ok=True)
    stem = out.with_suffix("")
    cmd = [str(bin_dir / "targen"), *RECIPE, "-c", str(srgb), str(stem)]
    print(" ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not out.exists():
        print(r.stdout, r.stderr)
        return 1

    # Stamp the provenance into the file itself (§5.4: version, recipe, and
    # the PROVISIONAL status all live in the header).
    text = out.read_text(encoding="utf-8")
    marker = 'ORIGINATOR "Argyll targen"'
    stamp = (
        f'{marker}\n'
        f'CHROMIQ_SET_VERSION "{MASTER_SET_VERSION}"\n'
        f'CHROMIQ_SET_STATUS "PROVISIONAL — may be re-cut until a published '
        f'report outside this project cites it; frozen from that moment on"\n'
        f'CHROMIQ_SET_RECIPE "targen {" ".join(RECIPE)} -c ref/sRGB.icm '
        f'(ArgyllCMS 3.5.0)"\n'
        f'CHROMIQ_SET_NESTED "every prefix of the -t sequence is a valid '
        f'smaller set; verified 960/5960 byte-identical"')
    if marker in text and "CHROMIQ_SET_VERSION" not in text:
        text = text.replace(marker, stamp, 1)
        out.write_text(text, encoding="utf-8")
    print(f"written: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
