#!/usr/bin/env python3
"""Import the "by Pharmacist" built-ins Knut sent on #182 (5860041950).

Each chart arrives as a Create Chart preset export (``<name>.json``, format
``chromiq_preset_version`` 1) and its patch set (``<name>.ti1``). This writes
one asset folder per chart:

    assets/charts/pharmacist/rgb/fulllayout/<slug>/chart.ti1    the patch set, byte for byte
    assets/charts/pharmacist/rgb/fulllayout/<slug>/layout.json  the export's layout_recipe
    assets/charts/pharmacist/rgb/fulllayout/<slug>/recipe.json  the export's editor_recipe

``recipe.json`` is what makes a row "Full layout setup" (the patch-set editor
can load its design, see ``_Ti1Preset.has_full_layout_setup``). The one chart
Knut named "Layout, but no editor setup" gets no ``recipe.json``, on purpose.

Two things are not the export's verbatim. ``clip_image_path``, which the
sender's export carries as a path on their own disk ("d:/Downloads/…"), is
cleared; these charts use the notes clip border, where it is never read. And
``seed_fixed`` (None in every export) is dropped, because a built-in's "Use a
fixed seed" is applied by code (``BUILTIN_PRESET_SEED_FIXED``).

    python scripts/import_pharmacist_presets.py <export-folder>          # check, print
    python scripts/import_pharmacist_presets.py <export-folder> --write  # write assets
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEST = REPO / "assets" / "charts" / "pharmacist" / "rgb" / "fulllayout"

#: file stem -> (slug, instrument, printtarg paper, layout-only?)
CHARTS = {
    "ColorMunki-A4-300p-1page-Landscape-w9.0mm-TC3.00 Equivalent Target (ChromIQ Editor)":
        ("pharm_cm_a4r_300p_1page_landscape_w9_0mm_tc300_editor", "CM", "A4R", False),
    "ColorMunki-A4-300p-1page-Landscape-w9.0mm-TC3.00 Target-by Pharmacist":
        ("pharm_cm_a4r_300p_1page_landscape_w9_0mm_tc300", "CM", "A4R", True),
    "ColorMunki-A4-600p-2pages-Landscape-w9.0mm-ABW Optimized Target-by Pharmacist":
        ("pharm_cm_a4r_600p_2pages_landscape_w9_0mm_abw", "CM", "A4R", False),
    "i1Pro-A4-648p-1page-Portrait-w7.5mm-(standard quality)-Real World Target-by Pharmacist":
        ("pharm_i1_a4_648p_1page_portrait_w7_5mm_real_world", "i1", "A4", False),
    "i1Pro-A4-1296p-2pages-Portrait-w7.5mm-(medium quality)-Real World Target-by Pharmacist":
        ("pharm_i1_a4_1296p_2pages_portrait_w7_5mm_real_world", "i1", "A4", False),
    "i1Pro-A4-1944p-3pages-Portrait-w7.5mm-(expert quality)-Real World Target-by Pharmacist":
        ("pharm_i1_a4_1944p_3pages_portrait_w7_5mm_real_world", "i1", "A4", False),
    "i1Pro-Letter-648p-1page-Portrait-w7.5mm-(standard quality)-Real World Target-by Pharmacist":
        ("pharm_i1_letter_648p_1page_portrait_w7_5mm_real_world", "i1", "Letter", False),
    "i1Pro-Letter-1296p-2pages-Portrait-w7.5mm-(medium quality)-Real World Target-by Pharmacist":
        ("pharm_i1_letter_1296p_2pages_portrait_w7_5mm_real_world", "i1", "Letter", False),
    "i1Pro-Letter-1944p-3pages-Portrait-w7.5mm-(expert quality)-Real World Target-by Pharmacist":
        ("pharm_i1_letter_1944p_3pages_portrait_w7_5mm_real_world", "i1", "Letter", False),
}


def ti1_counts(path: Path) -> tuple[int, int, int]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    fmt = text.split("\nBEGIN_DATA_FORMAT\n", 1)[1].split("\nEND_DATA_FORMAT", 1)[0].split()
    body = text.split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
    i = fmt.index("RGB_R")
    rgb = [[float(v) for v in ln.split()[i:i + 3]] for ln in body.splitlines() if ln.strip()]
    white = sum(all(abs(c - 100.0) < 1e-6 for c in v) for v in rgb)
    black = sum(all(abs(c) < 1e-6 for c in v) for v in rgb)
    return len(rgb), white, black


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", type=Path)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    rows = []
    for stem, (slug, instr, paper, layout_only) in CHARTS.items():
        exp = json.loads((args.src / f"{stem}.json").read_text(encoding="utf-8"))
        data = exp["data"]
        layout = dict(data["layout_recipe"])
        editor = data.get("editor_recipe")
        if layout.get("instrument") != instr or layout.get("paper") != paper:
            print(f"REFUSED {stem}: its recipe says {layout.get('instrument')} "
                  f"{layout.get('paper')}", file=sys.stderr)
            return 1
        if str(layout.get("clip_image_path") or "") and layout.get("clip_content_mode") == "image":
            print(f"REFUSED {stem}: it prints an image from the sender's disk", file=sys.stderr)
            return 1
        layout["clip_image_path"] = ""
        # A built-in's "Use a fixed seed" is one constant applied by code
        # (BUILTIN_PRESET_SEED_FIXED), never a key in its recipe.
        layout.pop("seed_fixed", None)
        ti1 = args.src / f"{stem}.ti1"
        patches, white, black = ti1_counts(ti1)
        m = re.search(r"-(\d+)pages?-", stem)
        pages = int(m.group(1)) if m else 1
        name = stem.split("-", 1)[1]            # the row adds its own instrument
        rows.append((slug, name, instr, paper, pages, patches, white, black, layout_only))
        if args.write:
            out = DEST / slug
            out.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ti1, out / "chart.ti1")
            (out / "layout.json").write_text(
                json.dumps(layout, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            rec = out / "recipe.json"
            if layout_only:
                rec.unlink(missing_ok=True)
            else:
                if not isinstance(editor, dict) or not editor:
                    print(f"REFUSED {stem}: no editor design to ship", file=sys.stderr)
                    return 1
                rec.write_text(json.dumps(editor, indent=1, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    for r in rows:
        slug, name, instr, paper, pages, patches, white, black, layout_only = r
        extra = ", layout_only=True" if layout_only else ""
        print(f'    _pharmacist_preset("{slug}",\n'
              f'                       "{name}",\n'
              f'                       "{instr}", "{paper}", {pages}, {patches}, {white}, {black}{extra}),')
    return 0


if __name__ == "__main__":
    sys.exit(main())
