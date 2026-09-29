#!/usr/bin/env python3
"""Put `d6512a18`'s two raster edits BACK the way they were, one at a time.

A fix that cannot be shown to change anything is not proven, and a fix that
changes something it claimed not to is a fault. `d6512a18` made two edits to
`workflow/layout_engine/raster.py`:

* ``tile`` -- the turned strip label is COMPOSITED into the label overlay
  (``Image.alpha_composite`` on its own rectangle) instead of pasted through
  itself as a mask. This is claimed to change the turned labels and nothing
  else.
* ``final`` -- the end-of-page composite hands PIL the RGBA overlay as both
  source and mask, instead of allocating ``.convert("RGB")`` and
  ``.split()[3]``. This is claimed to be PIXEL-IDENTICAL and only cheaper.

This script rewrites the file in place, runs a command, and always restores it.
It VERIFIES the mutation landed (the text really changed, and the byte count
moved) and refuses to run if it did not.

    python scripts/probe_182_c2_mutate_raster.py --which tile  -- <cmd...>
    python scripts/probe_182_c2_mutate_raster.py --which final -- <cmd...>
    python scripts/probe_182_c2_mutate_raster.py --which both  -- <cmd...>
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RASTER = ROOT / "workflow" / "layout_engine" / "raster.py"

TILE_NEW = """                    _ov = _lbl_surface()[0]
                    _bx = (_cx - _tile.width // 2, _y + _off)
                    _reg = (_bx[0], _bx[1],
                            _bx[0] + _tile.width, _bx[1] + _tile.height)
                    _ov.paste(Image.alpha_composite(_ov.crop(_reg), _tile), _bx)
"""
TILE_OLD = """                    _lbl_surface()[0].paste(
                        _tile, (_cx - _tile.width // 2, _y + _off), _tile)
"""

FINAL_NEW = """            img.paste(_lbl_layer[0], (0, 0), _lbl_layer[0])
"""
FINAL_OLD = """            img.paste(_lbl_layer[0].convert("RGB"), (0, 0),
                      _lbl_layer[0].split()[3])
"""


def _purge_pycache() -> None:
    for p in ROOT.rglob("__pycache__"):
        if ".venv" not in p.parts:
            shutil.rmtree(p, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", required=True,
                    choices=["tile", "final", "both", "none"])
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = [c for c in a.cmd if c != "--"]
    if not cmd:
        print("no command given", file=sys.stderr)
        return 2

    src = RASTER.read_text(encoding="utf-8")
    backup = src
    n_before = len(src)
    landed = []
    if a.which in ("tile", "both"):
        assert src.count(TILE_NEW) == 1, "the tile composite is not where I left it"
        src = src.replace(TILE_NEW, TILE_OLD)
        landed.append("tile")
    if a.which in ("final", "both"):
        assert src.count(FINAL_NEW) == 1, "the final composite is not where I left it"
        src = src.replace(FINAL_NEW, FINAL_OLD)
        landed.append("final")
    if a.which != "none":
        assert src != backup, "MUTATION DID NOT LAND: the text is unchanged"
        print(f"mutation {'+'.join(landed)} landed: {n_before} -> {len(src)} bytes",
              flush=True)
    try:
        RASTER.write_text(src, encoding="utf-8")
        _purge_pycache()
        # Prove it landed in what Python will actually import, not just on disk.
        check = subprocess.run(
            [sys.executable, "-c",
             "import inspect, sys;"
             "sys.path.insert(0, %r);" % str(ROOT) +
             "from workflow.layout_engine import raster;"
             "s = inspect.getsource(raster.render_pages);"
             "print('ALPHA_COMPOSITE' if 'alpha_composite' in s else 'NO_ALPHA_COMPOSITE');"
             "print('CONVERT_RGB' if '.convert(\"RGB\"), (0, 0)' in s else 'NO_CONVERT_RGB')"],
            capture_output=True, encoding="utf-8", cwd=str(ROOT))
        print("imported module says:", check.stdout.strip().replace("\n", " / "),
              flush=True)
        r = subprocess.run(cmd, cwd=str(ROOT))
        return r.returncode
    finally:
        RASTER.write_text(backup, encoding="utf-8")
        _purge_pycache()
        assert RASTER.read_text(encoding="utf-8") == backup
        print("raster.py restored", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
