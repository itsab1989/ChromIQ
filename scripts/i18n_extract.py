#!/usr/bin/env python3
"""Extract tr() source strings and check catalog completeness.

Usage:
    python scripts/i18n_extract.py              # list all keys to stdout
    python scripts/i18n_extract.py --missing de # keys absent from de.json
    python scripts/i18n_extract.py --stale de   # de.json keys no longer in code
    python scripts/i18n_extract.py --stats de   # one-line coverage summary

The catalog key is the exact English source string passed to tr().
Both literal arguments (incl. implicitly concatenated) and module-level
string constants are resolved:  tr(_TT_TITLE_PRINT) contributes the
constant's value as a key.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("ui", "workflow", "core", "main.py")


def extract_keys() -> set[str]:
    keys: set[str] = set()
    files: list[Path] = []
    for entry in SCAN_DIRS:
        p = ROOT / entry
        if p.is_file():
            files.append(p)
        else:
            files.extend(sorted(p.rglob("*.py")))
    for f in files:
        if "__pycache__" in f.parts:
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        # module-level NAME = "literal" assignments, for tr(NAME) resolution
        consts: dict[str, str] = {}
        for stmt in tree.body:
            if (isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)):
                consts[stmt.targets[0].id] = stmt.value.value
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "tr"
                    and node.args):
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                keys.add(arg.value)
            elif isinstance(arg, ast.Name) and arg.id in consts:
                keys.add(consts[arg.id])
    keys |= _message_catalogue_keys()
    return keys


def _message_catalogue_keys() -> set[str]:
    """Every text in ``workflow/measurement_messages.py``.

    That module holds the reviewed §M catalogue and hands its strings to
    ``tr()`` as ``tr(self.body)`` — an attribute, not a literal, so the walk
    above cannot see any of them. Without this the whole catalogue silently
    dropped out of the translations: 4009 keys became 3966, and every window in
    the Measurement Management model would have shown English in every
    language. Read the values from the module itself rather than trying to
    pattern-match the source, so a new message cannot be missed.
    """
    sys.path.insert(0, str(ROOT))
    try:
        from workflow import measurement_messages as mm
    except Exception as exc:      # noqa: BLE001 — never break the extractor
        print(f"# WARNING: message catalogue not readable: {exc}",
              file=sys.stderr)
        return set()

    out: set[str] = set()
    for msg in mm.CATALOGUE.values():
        out.add(msg.title)
        out.add(msg.body)
        if msg.body_one:
            out.add(msg.body_one)
    out |= set(mm.FRAGMENTS.values())
    # EVERY STRING CONSTANT IN THE MODULE, not a hand-kept list of names.
    #
    # The list this replaces named ten of them, and the module now holds
    # twenty-eight. Three were missing when it was swept programmatically on
    # 2026-09-02: `M_CHART_CORRUPT_WITH_PROFILE`, which is handed to `tr()` at
    # two call sites in the Create Chart tab and had therefore been showing
    # English in all twelve translated languages since it was written, and the
    # two `{runs_line}` sentences of M-CAL-REPLACE-MEASURED, added that day.
    #
    # This is the blind spot the module's own comments already warn about:
    # `tr(NAME)` passes an attribute, not a literal, so the AST walk cannot see
    # it and the only protection was somebody remembering to edit this file.
    # Nobody did, twice. A sweep cannot forget.
    #
    # Fragments are message text by construction here: this module holds
    # nothing else. Anything added to it that is NOT for the screen would need
    # a leading double underscore, which is excluded below.
    out |= {v for k, v in vars(mm).items()
            if isinstance(v, str) and not k.startswith("__")
            and (k.startswith("M_") or k.startswith("_"))}
    return out


def load_catalog(code: str) -> dict[str, str]:
    path = ROOT / "data" / "i18n" / f"{code}.json"
    with open(path, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("@")}


def main() -> int:
    args = sys.argv[1:]
    keys = extract_keys()
    if not args:
        for k in sorted(keys):
            print(json.dumps(k, ensure_ascii=False))
        print(f"# {len(keys)} keys", file=sys.stderr)
        return 0
    mode, code = args[0], args[1]
    catalog = load_catalog(code)
    if mode == "--missing":
        missing = sorted(keys - set(catalog))
        for k in missing:
            print(json.dumps(k, ensure_ascii=False))
        print(f"# {len(missing)} missing of {len(keys)}", file=sys.stderr)
        return 1 if missing else 0
    if mode == "--stale":
        stale = sorted(set(catalog) - keys)
        for k in stale:
            print(json.dumps(k, ensure_ascii=False))
        print(f"# {len(stale)} stale", file=sys.stderr)
        return 0
    if mode == "--stats":
        done = len(keys & set(catalog))
        print(f"{code}: {done}/{len(keys)} translated "
              f"({100 * done / max(1, len(keys)):.1f}%), "
              f"{len(set(catalog) - keys)} stale")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
