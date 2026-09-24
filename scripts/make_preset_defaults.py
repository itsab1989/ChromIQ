#!/usr/bin/env python3
"""Write ``data/preset_defaults.json``: the built-in presets ChromIQ SHIPS ticked.

Knut, #182 5818659478: every built-in stays available, but only the ticked ones
are listed directly in Create Chart's "Select preset" pulldown and in the
Built-in presets list; the rest wait under an arrow. What is ticked for a person
who never opened the window behind the gear button comes from this file
(``core/curated_presets.py`` explains how a person's own choice sits on top).

    python scripts/make_preset_defaults.py                  # the beta rule
    python scripts/make_preset_defaults.py --check          # exit 1 if the file
                                                            # is not what the rule
                                                            # gives
    python scripts/make_preset_defaults.py --table out.csv  # the list for Knut's
                                                            # users (.csv or .md)
    python scripts/make_preset_defaults.py --from-table filled.csv
                                                            # their answers back

**THE BETA RULE** is :func:`core.curated_presets.beta_selection`, in Knut's
words: per instrument group and paper size, four presets of one to four sheets
with different patch sizes, skipping the smallest and the largest. Its
docstring says exactly how each word is read.

**THE TABLE** has Knut's three columns: the preset's name, "Include as default
[yes/no]" (left EMPTY, because it is theirs to fill in) and "Comments". The
key rides along as a fourth column so the answers come back to the right
preset even if a name is edited or re-sorted in a spreadsheet. ``--from-table``
reads a ``.csv`` in that shape: "yes" (any case, or "y", "x", "1") ticks, and
any other answer or an empty cell does not. A row whose key ChromIQ does not
know is reported and refused rather than dropped, since that is a table from
another version. When the table comes back, the file's ``source`` says so and
``tests/test_curated_builtin_presets.py`` stops holding it to the beta rule.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OUT = ROOT / "data" / "preset_defaults.json"
BETA_SOURCE = "beta rule: core.curated_presets.beta_selection"
TABLE_SOURCE = "table: the answers of Knut's users"
_YES = {"yes", "y", "x", "1", "ja", "true"}
_HEADER = ["Name of preset", "Include as default [yes/no]", "Comments", "Key"]


def _facts() -> list[dict]:
    from ui.tabs.tab_chart import builtin_preset_facts
    return builtin_preset_facts()


def document(keys: list[str], facts: list[dict], source: str) -> dict:
    names = {f["key"]: f["name"] for f in facts}
    return {
        "@about": ("The built-in presets ChromIQ shows directly in Create "
                   "Chart's preset lists for a person who has not chosen "
                   "their own (#182 5818659478). The rest stay available "
                   "under an arrow. Keys are the identity; the names are for "
                   "the reader. Written by scripts/make_preset_defaults.py; "
                   "do not edit by hand."),
        "source": source,
        "shown": {k: names[k] for k in keys},
    }


def write(doc: dict, path: Path = OUT) -> None:
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def beta_document() -> dict:
    from core.curated_presets import beta_selection
    facts = _facts()
    return document(beta_selection(facts), facts, BETA_SOURCE)


def write_table(path: Path) -> None:
    facts = _facts()
    if path.suffix.lower() == ".md":
        lines = ["| " + " | ".join(_HEADER[:3]) + " |",
                 "|---|---|---|"]
        heading = None
        for f in facts:
            if f["group"] != heading:
                heading = f["group"]
                lines.append(f"| **{heading}** | | |")
            lines.append(f"| {f['name']} |  |  |")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Group", *_HEADER])
        for f in facts:
            w.writerow([f["group"], f["name"], "", "", f["key"]])


def from_table(path: Path) -> dict:
    facts = _facts()
    known = {f["key"] for f in facts}
    ticked: list[str] = []
    unknown: list[str] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            key = (row.get("Key") or "").strip()
            if not key:
                continue
            if key not in known:
                unknown.append(key)
                continue
            answer = (row.get(_HEADER[1]) or "").strip().lower()
            if answer in _YES:
                ticked.append(key)
    if unknown:
        raise SystemExit("keys this ChromIQ does not know, refusing the "
                         "table:\n  " + "\n  ".join(unknown))
    order = [f["key"] for f in facts if f["key"] in set(ticked)]
    return document(order, facts, TABLE_SOURCE)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--table", type=Path)
    ap.add_argument("--from-table", type=Path)
    a = ap.parse_args()
    if a.table:
        write_table(a.table)
        print(f"wrote {a.table}")
        return 0
    doc = from_table(a.from_table) if a.from_table else beta_document()
    if a.check:
        current = json.loads(OUT.read_text(encoding="utf-8"))
        same = current == doc
        print("up to date" if same else f"{OUT} differs from the rule")
        return 0 if same else 1
    write(doc)
    print(f"wrote {OUT}: {len(doc['shown'])} presets shown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
