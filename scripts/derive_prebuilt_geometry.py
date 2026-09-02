#!/usr/bin/env python3
"""Generate scan-recognition geometry for the prebuilt chart bundles.

The prebuilt "by Pharmacist" built-ins copy a bundled, pre-rendered target
into the run — no targen/printtarg ever runs, so the runs never carried the
``channels.json`` layout block the scanner-target build needs (Knut). This
one-time script derives that geometry from the bundled render itself —
colour-verified patch by patch against the bundle's own ``.ti2``
(:mod:`workflow.layout_from_render`, correct-or-absent) — and writes
``<stem>.channels.json`` next to the assets. ``_create_prebuilt_target``
already copies that sidecar into new runs, so re-running this script is all a
new/changed bundle needs.

Run from the repo root:  python scripts/derive_prebuilt_geometry.py
Verify + smoke-build every page's .cht from the derived geometry; a bundle
that fails validation is reported and left WITHOUT geometry (never guessed).
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflow.layout_from_render import (RenderGeometryError,
                                         derive_layout_from_render)


def main() -> int:
    root = Path(__file__).resolve().parent.parent / "assets/charts/pharmacist"
    failures = 0
    for ti2 in sorted(root.rglob("*.ti2")):
        d, stem = ti2.parent, ti2.stem
        tiffs = sorted(d.glob(f"{stem}_*.tif")) or \
            ([d / f"{stem}.tif"] if (d / f"{stem}.tif").is_file() else [])
        label = str(d.relative_to(root))
        if not tiffs:
            print(f"SKIP {label}: no TIFF pages")
            continue
        try:
            layout = derive_layout_from_render(tiffs, ti2)
        except RenderGeometryError as exc:
            failures += 1
            print(f"FAIL {label}: {exc}")
            continue
        # Smoke-build every page's .cht from the derived geometry before
        # trusting it (same code path the app will use, aim values as ref).
        from workflow.scanin_target import build_scanin_target_from_paths
        sidecar = d / f"{stem}.channels.json"
        doc = {"ink_channels": ["r", "g", "b"], "layout": layout}
        sidecar.write_text(json.dumps(doc), encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            res = build_scanin_target_from_paths(sidecar, ti2, Path(td) / stem)
            assert res.n_patches == len(layout["patches"]), label
            assert res.n_pages == len(tiffs), label
        print(f"OK   {label}: {len(layout['patches'])} patches, "
              f"{len(tiffs)} page(s) → {sidecar.name}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
