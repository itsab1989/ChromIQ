#!/usr/bin/env python3
"""Bring every ``data/i18n/<code>.json`` back in step with the source.

    python scripts/i18n_sync.py                 # report only
    python scripts/i18n_sync.py --apply         # add missing, drop stale
    python scripts/i18n_sync.py --apply --de de.json   # …with German supplied

Missing keys are added as **English placeholders**, which is the rule during a
beta — the full translation happens once before a final release. German is the
exception: it is kept complete, so pass its translations in a JSON file mapping
source string → German string, or the key lands in English and
``tests/test_i18n.py`` will say so.

Written after doing this by hand four times in two days. The hand version is
also where a mistake hides: a key added to eleven catalogues and forgotten in
the twelfth fails the suite in a way that reads like a code fault.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.i18n_extract import extract_keys      # noqa: E402


def catalogues() -> "list[Path]":
    return sorted(p for p in (ROOT / "data" / "i18n").glob("*.json")
                  if not p.name.startswith("parameters."))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the changes (default: report only)")
    ap.add_argument("--de", type=Path,
                    help="JSON file of {source: German} for the new keys")
    args = ap.parse_args()

    keys = extract_keys()
    german = json.loads(args.de.read_text(encoding="utf-8")) if args.de else {}

    missing_any, stale_any = False, False
    for path in catalogues():
        code = path.stem
        data = json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=collections.OrderedDict)
        missing = [k for k in keys if k not in data]
        # "@…" keys are the catalogue's own metadata — "@language_name" is what
        # the Settings combobox reads — not source strings, so they are never
        # stale. Dropping them emptied the language list (learned the hard way).
        stale = [k for k in data if k not in keys and not k.startswith("@")]
        if not missing and not stale:
            continue
        missing_any = missing_any or bool(missing)
        stale_any = stale_any or bool(stale)
        print(f"{code}: +{len(missing)} missing, -{len(stale)} stale")
        if not args.apply:
            continue
        for k in stale:
            del data[k]
        for k in missing:
            data[k] = german.get(k, k) if code == "de" else k
        data = collections.OrderedDict(sorted(data.items(), key=lambda kv: kv[0]))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    if args.apply and missing_any and not german:
        print("\nNOTE: German got English placeholders — pass --de to translate "
              "them, or tests/test_i18n.py will fail.")
    if not (missing_any or stale_any):
        print("every catalogue is in step")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
