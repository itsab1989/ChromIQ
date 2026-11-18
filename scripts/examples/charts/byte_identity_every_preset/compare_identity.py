#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXAMPLE (kept as a pattern; may need adapting): compare two identity_driver.py runs, preset
by preset and file by file.

    python compare_identity.py A.json B.json [OUT.md]

Prints (and writes) a table: presets, page TIFFs, files compared, files byte-identical, files
identical except a wall-clock stamp (the driver's masked hash), and every other difference by
name: a file only on one side, a file that differs, a build that did not finish, a different
chart name or panel state. Reads the two JSON files only.
"""
import argparse
import json
import sys
from pathlib import Path


def compare(a: dict, b: dict) -> "tuple[list[str], list]":
    ra = {r["key"]: r for r in a["rows"]}
    rb = {r["key"]: r for r in b["rows"]}
    lines = [f"# Byte identity: {a['mode']} ({a['repo']}) vs {b['mode']} ({b['repo']})", "",
             f"on screen: {a.get('on_screen')} / {b.get('on_screen')}", ""]
    keys = [r["key"] for r in a["rows"]]
    missing = sorted(set(ra) ^ set(rb))
    n_files = n_same = n_tif = n_tif_same = n_clock = 0
    diffs, kinds = [], {}
    for k in keys:
        if k not in rb:
            continue
        fa, fb = ra[k]["files"], rb[k]["files"]
        for name in sorted(set(fa) | set(fb)):
            ext = Path(name).suffix or Path(name).name
            kinds.setdefault(ext, [0, 0, 0])
            kinds[ext][0] += 1
            n_files += 1
            tif = name.endswith(".tif")
            n_tif += tif
            if name in fa and name in fb and fa[name]["sha"] == fb[name]["sha"]:
                n_same += 1
                n_tif_same += tif
                kinds[ext][1] += 1
            elif (name in fa and name in fb and fa[name].get("masked")
                  and fa[name].get("masked") == fb[name].get("masked")):
                n_clock += 1
                kinds[ext][2] += 1
            else:
                diffs.append((ra[k]["label"], name,
                              "only in A" if name not in fb else
                              "only in B" if name not in fa else "differs"))
        for side, r in (("A", ra[k]), ("B", rb[k])):
            if "error" in r or not r.get("finished"):
                diffs.append((r["label"], "(build)",
                              f"{side}: finished={r.get('finished')} {r.get('error', '')}"))
        if ra[k].get("target_name") != rb[k].get("target_name"):
            diffs.append((ra[k]["label"], "(chart name)",
                          f"{ra[k].get('target_name')!r} vs {rb[k].get('target_name')!r}"))
        if ra[k].get("panel") != rb[k].get("panel"):
            diffs.append((ra[k]["label"], "(panel)", f"{ra[k].get('panel')} vs {rb[k].get('panel')}"))
    lines += [f"presets compared: {len([k for k in keys if k in rb])} (missing on one side: {missing})",
              f"files compared: {n_files}, byte-identical: {n_same}, "
              f"identical except a wall-clock time stamp: {n_clock}",
              f"page TIFFs compared: {n_tif}, byte-identical: {n_tif_same}", "",
              "| kind | files | byte-identical | only a clock stamp differs |", "|---|---|---|---|"]
    lines += [f"| {e} | {v[0]} | {v[1]} | {v[2]} |" for e, v in sorted(kinds.items())]
    lines += ["", f"differences: {len(diffs)}"]
    lines += [f"- {lab} :: {name} :: {why}" for lab, name, why in diffs]
    return lines, diffs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("out", nargs="?", help="also write the table here (a new file)")
    x = ap.parse_args(argv)
    lines, diffs = compare(json.loads(Path(x.a).read_text(encoding="utf-8")),
                           json.loads(Path(x.b).read_text(encoding="utf-8")))
    text = "\n".join(lines)
    print(text)
    if x.out:
        Path(x.out).write_text(text + "\n", encoding="utf-8")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
