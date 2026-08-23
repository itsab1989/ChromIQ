#!/usr/bin/env python3
"""Import Knut's exported chart families as bundled built-in presets.

Knut authors these presets in ChromIQ itself and exports them as a pair of
files per chart:

    <name>.ti1     the patch set (a real CTI1 file, all three tables)
    <name>.json    the Create-Chart preset export (chromiq_preset_version 1)

This script turns a folder of such pairs into the asset tree the built-in
registry expects, and prints the ``_Ti1Preset`` rows to paste into
``ui/tabs/tab_chart.py``:

    assets/charts/knut/rgb/colormunki/<slug>/chart.ti1
    assets/charts/knut/rgb/colormunki/<slug>/recipe.json

``recipe.json`` is the export's ``editor_recipe`` — the colour-set design, so
the preset can seed the New-chart window ("Load setup from preset"). The page
layout (the export's ``layout_recipe``) is NOT written to disk: the whole family
shares one base recipe in ``tab_chart.py`` and differs only in a handful of
fields, so it lives in code where it can be read and reviewed.

That sharing is the reason this script also **validates**: every export must
equal the shared base except for the keys in ``VARYING`` below. A chart that
differs anywhere else is reported and not imported — silently folding it into
the base would ship a layout nobody authored.

One family per instrument, described by the ``FAMILIES`` table below — the
ColorMunki charts (2026-08-16) and the i1Pro 3 Plus charts (2026-08-18) differ
only in their name prefix, asset folder, and which recipe fields a single chart
may set for itself. Everything else — the validation, the Set B normalisation,
the row emitter — is shared, so a third family is a table entry, not a script.

Usage::

    python scripts/import_knut_presets.py <family> <export-folder> [--write]

    family: cm  (ColorMunki)  |  p3  (i1Pro 3 Plus)  |  i1  (i1Pro, 8 mm)

Without ``--write`` it only validates and prints, so you can see what would
change before anything is touched.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
ASSETS = REPO / "assets" / "charts" / "knut" / "rgb"


@dataclass(frozen=True)
class Family:
    """One instrument's line-up of charts, as Knut exports them."""
    key: str                 # command-line name
    label: str               # how the app calls the instrument
    prefix: str              # the name prefix his exports carry
    slug_prefix: str         # identity prefix, baked into the preset key
    instrument: str          # layout-engine instrument code
    dest: Path               # where the bundled assets land
    varying: frozenset       # recipe fields ONE chart may set for itself
    helper: str              # the tab_chart.py helper the rows call


FAMILIES: dict[str, Family] = {
    # The ColorMunki line-up (2026-08-16). Two charts break from the base: the
    # 26 mm "Hand Held" ones pull the left margin in to 6 mm and carry their own
    # clip-border note, so both fields are per chart.
    "cm": Family(
        key="cm", label="ColorMunki", prefix="ColorMunki-", slug_prefix="cm_",
        instrument="CM", dest=ASSETS / "colormunki",
        varying=frozenset({"paper", "area_cols", "area_rows",
                           "margin_left", "clip_text"}),
        helper="_cm_preset",
    ),
    # The i1Pro 3 Plus line-up (2026-08-18). Tighter than the ColorMunki one:
    # every chart shares all four margins and shows the automatic notes box in
    # the clip border, so only the sheet and the grid are its own.
    "p3": Family(
        key="p3", label="i1Pro 3 Plus", prefix="i1Pro3-", slug_prefix="p3_",
        instrument="p3", dest=ASSETS / "i1pro3",
        varying=frozenset({"paper", "area_cols", "area_rows"}),
        helper="_p3_preset",
    ),
    # The i1Pro line-up with 8 mm patches (2026-08-23). Same shape as the
    # i1Pro 3 Plus family — one base, one grid per chart — but cut for the
    # original i1Pro's own jig margins, and every chart on A4.
    "i1": Family(
        key="i1", label="i1Pro", prefix="i1Pro-", slug_prefix="i1_w8_",
        instrument="i1", dest=ASSETS / "i1pro",
        varying=frozenset({"paper", "area_cols", "area_rows"}),
        helper="_i1_preset",
    ),
}

# The names carry the layout: "<paper>-<patches>p-<pages>page(s)-<orientation>…".
_NAME_TAIL = (r"(?P<paper>A4|A3Plus|A3|Letter)-(?P<patches>\d+)p-"
              r"(?P<pages>\d+)pages?-(?P<rest>.+)$")

# Display order: smallest sheet first (matching _paper_sort_key), then ascending
# patch count. Portrait and landscape share a sheet, so they interleave by count.
_SHEET_ORDER = {"A4": 0, "Letter": 1, "A3": 2, "A3Plus": 3}


def slugify(name: str, fam: Family) -> str:
    """Stable identity for a chart name. Never change this for a shipped preset —
    the slug is baked into the preset key that projects and settings store."""
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"{fam.slug_prefix}{s}"


def load_pairs(src: Path) -> list[tuple[Path, Path, dict]]:
    """Every ``<name>.json`` in *src* that has a matching ``<name>.ti1``."""
    out = []
    for js in sorted(src.glob("*.json")):
        ti1 = js.with_suffix(".ti1")
        if not ti1.is_file():
            print(f"  skip (no .ti1): {js.name}")
            continue
        export = json.loads(js.read_text(encoding="utf-8"))
        out.append((ti1, js, export))
    for ti1 in sorted(src.glob("*.ti1")):
        if not ti1.with_suffix(".json").is_file():
            print(f"  skip (no .json): {ti1.name}")
    return out


def ti1_facts(path: Path) -> dict:
    """Patch, white and black counts as the .ti1 itself declares them."""
    txt = path.read_text(encoding="latin-1", errors="ignore")
    sets = re.search(r"NUMBER_OF_SETS\s+(\d+)", txt)
    white = re.search(r'WHITE_COLOR_PATCHES\s+"(\d+)"', txt)
    black = re.search(r'BLACK_COLOR_PATCHES\s+"(\d+)"', txt)
    return {
        "patches": int(sets.group(1)) if sets else 0,
        "white": int(white.group(1)) if white else 0,
        "black": int(black.group(1)) if black else 0,
        # printtarg needs all three tables of a targen .ti1 — a truncated export
        # builds nothing, so check it here rather than at chart-creation time.
        "tables": txt.count("NUMBER_OF_SETS"),
    }


def check(export: dict, ti1: Path, base: dict | None,
          fam: Family) -> tuple[dict, list[str]]:
    """Validate one export. Returns (row fields, problems)."""
    problems: list[str] = []
    name = export.get("name", "")
    data = export.get("data") or {}
    recipe = data.get("layout_recipe") or {}
    facts = ti1_facts(ti1)

    m = re.match("^" + re.escape(fam.prefix) + _NAME_TAIL, name)
    if not m:
        return {}, [f"name does not follow the convention: {name!r}"]

    if facts["tables"] != 3:
        problems.append(f"the .ti1 has {facts['tables']} tables, expected 3")

    declared = int(m.group("patches"))
    if declared != facts["patches"]:
        problems.append(
            f"name says {declared} patches, the .ti1 holds {facts['patches']}")

    cols, rows = recipe.get("area_cols"), recipe.get("area_rows")
    if not cols or not rows:
        problems.append("the recipe has no columns × rows grid")
    else:
        per_page = cols * rows
        pages = -(-facts["patches"] // per_page)
        if pages != int(m.group("pages")):
            problems.append(
                f"name says {m.group('pages')} page(s); {cols}×{rows} patches "
                f"per sheet puts {facts['patches']} on {pages}")

    if base is not None:
        for k in sorted(set(base) | set(recipe)):
            if k in fam.varying:
                continue
            if recipe.get(k) != base.get(k):
                problems.append(
                    f"{k}: {recipe.get(k)!r} differs from the family base "
                    f"{base.get(k)!r}")

    if recipe.get("instrument") != fam.instrument:
        problems.append(f"instrument is {recipe.get('instrument')!r}, "
                        f"not {fam.instrument!r}")
    if not data.get("editor_recipe"):
        problems.append("the export carries no colour-set recipe")

    short = name[len(fam.prefix):]
    row = {
        "slug": slugify(short, fam),
        "name": short,
        "sheet": m.group("paper"),
        "paper": recipe.get("paper", ""),
        "cols": cols,
        "rows": rows,
        "patches": facts["patches"],
        "pages": int(m.group("pages")),
        "white": facts["white"],
        "black": facts["black"],
        "margin_left": recipe.get("margin_left"),
        "clip_text": recipe.get("clip_text"),
        "editor_recipe": data.get("editor_recipe"),
        "layout_recipe": recipe,
        "ti1": ti1,
    }
    return row, problems


def normalise_recipe(editor: dict, layout: dict, fam: Family,
                     patches: int | None = None) -> tuple[dict, list[str]]:
    """Bring the export's colour-set recipe (Set B) into line with the chart it
    actually produced (Set A), and say what had to move.

    A preset's ``recipe.json`` seeds the New-chart window through "Load setup
    from preset". Knut designs a colour set once and then lays it out on several
    sheets, so the Set B block keeps the instrument and paper that were on screen
    when the *colours* were designed — for 33 of the 45 charts that is not the
    sheet the chart was finally built on. Left alone, picking "Load setup from
    preset" for a ColorMunki A3 chart would seed an i1Pro on A4.

    Only the chart's identity is corrected — instrument, paper, page size, and
    the layout flags the engine recipe genuinely fixes. The printtarg-style
    scale / margin knobs are left exactly as exported: an engine chart's four
    per-side margins have no honest single-margin equivalent, so inventing one
    would be worse than carrying his value forward. Same normalisation the
    Full-layout-setup family already goes through (docs/dev_builtin_presets.md).
    """
    from workflow.layout_engine import papers

    out = json.loads(json.dumps(editor))       # never mutate the caller's dict
    notes: list[str] = []
    paper = layout["paper"]
    w_mm, h_mm = papers.dimensions_mm(paper)

    if out.get("instr") != fam.instrument:
        notes.append(f"instrument {out.get('instr')!r} → {fam.instrument!r}")
        out["instr"] = fam.instrument
    if out.get("paper") != paper:
        notes.append(f"paper {out.get('paper')!r} → {paper!r}")
        out["paper"] = paper
    if out.get("paper_w") != round(w_mm) or out.get("paper_h") != round(h_mm):
        out["paper_w"], out["paper_h"] = round(w_mm), round(h_mm)

    # …and how many patches the set is asked for. An export can carry the count
    # of the design it was cloned FROM: one of the 8 mm i1Pro charts (#164)
    # arrived with `fill_to: 1200` beside a 2288-patch chart, so "Load setup
    # from preset" would have offered to regenerate it 1088 patches short. The
    # bundled .ti1 is the authority on what this preset IS.
    if patches is not None:
        sp = out.setdefault("sp", {})
        if sp.get("fill_to") != patches:
            notes.append(f"fill_to {sp.get('fill_to')!r} → {patches!r}")
            sp["fill_to"] = patches

    lo = out.setdefault("layout", {})
    lo["h"] = layout.get("cm_density") == 2          # ColorMunki double density
    lo["td"] = False                                 # never triple density here
    lo["dpi"] = layout.get("dpi", lo.get("dpi"))
    lo["bit16"] = bool(layout.get("bit16"))
    lo["spacer_mode"] = layout.get("spacer_mode", lo.get("spacer_mode"))
    return out, notes


def emit_rows(rows: list[dict], fam: Family, base: dict) -> str:
    """The ``_Ti1Preset`` rows, ready to paste into tab_chart.py.

    A chart spells out only a field its family lets it own AND that it really
    differs from the base in — so a family whose charts agree on everything but
    the sheet and the grid (the i1Pro 3 Plus one) emits rows with no keyword
    arguments at all, and a reviewer can see at a glance that nothing else moved.
    """
    out = []
    pad = " " * (len(fam.helper) + 5)
    for r in rows:
        extra = ""
        if "margin_left" in fam.varying and r["margin_left"] != base.get("margin_left"):
            extra += f", margin_left={r['margin_left']}"
        if "clip_text" in fam.varying and r["clip_text"] != base.get("clip_text"):
            # Only the ColorMunki family authors a second note (its Hand Held
            # charts); the constant sits beside the base in tab_chart.py.
            extra += ", clip_text=_CM_CLIP_TEXT_HAND_HELD"
        out.append(
            f'    {fam.helper}("{r["slug"]}",\n'
            f'{pad}"{r["name"]}",\n'
            f'{pad}"{r["paper"]}", {r["cols"]}, {r["rows"]}, '
            f'{r["patches"]}, {r["pages"]}, {r["white"]}, {r["black"]}'
            f'{extra}),'
        )
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("family", choices=sorted(FAMILIES),
                    help="which line-up these exports belong to "
                         "(cm = ColorMunki, p3 = i1Pro 3 Plus)")
    ap.add_argument("src", type=Path, help="folder of <name>.ti1 + <name>.json")
    ap.add_argument("--write", action="store_true",
                    help="copy the assets into place (otherwise only report)")
    args = ap.parse_args()
    fam = FAMILIES[args.family]

    pairs = load_pairs(args.src)
    if not pairs:
        print("nothing to import")
        return 1
    print(f"{len(pairs)} {fam.label} chart(s) found\n")

    # The family base is whatever the majority of the exports agree on — taken
    # from the first chart, then every other chart is checked against it.
    base = (pairs[0][2].get("data") or {}).get("layout_recipe") or {}

    rows, failed = [], 0
    for ti1, _js, export in pairs:
        row, problems = check(export, ti1, base, fam)
        if problems:
            failed += 1
            print(f"✗ {export.get('name', ti1.name)}")
            for p in problems:
                print(f"    {p}")
            continue
        rows.append(row)

    if failed:
        print(f"\n{failed} chart(s) rejected — fix them before importing.")
        return 1

    rows.sort(key=lambda r: (_SHEET_ORDER.get(r["sheet"], 9), r["patches"],
                             r["pages"]))
    slugs = [r["slug"] for r in rows]
    if len(set(slugs)) != len(slugs):
        print("✗ two charts slugify to the same identity")
        return 1

    print(f"✓ {len(rows)} chart(s) validated against the shared base recipe")

    corrected = 0
    for r in rows:
        r["recipe"], r["notes"] = normalise_recipe(r["editor_recipe"],
                                                   r["layout_recipe"], fam, r["patches"])
        if r["notes"]:
            corrected += 1
            print(f"  · {r['slug']}: {'; '.join(r['notes'])}")
    if corrected:
        print(f"↻ {corrected} colour-set recipe(s) re-pointed at the chart they "
              f"built (see normalise_recipe)")

    if args.write:
        for r in rows:
            leaf = fam.dest / r["slug"]
            leaf.mkdir(parents=True, exist_ok=True)
            shutil.copy2(r["ti1"], leaf / "chart.ti1")
            (leaf / "recipe.json").write_text(
                json.dumps(r["recipe"], indent=1, ensure_ascii=False)
                + "\n", encoding="utf-8")
        print(f"✓ written to {fam.dest.relative_to(REPO)}/")
    else:
        print("  (dry run — pass --write to copy the assets into place)")

    print("\n--- rows for KNUT_PRESETS ---\n")
    print(emit_rows(rows, fam, base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
