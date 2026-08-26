#!/usr/bin/env python3
"""Merge a batch of translations into data/i18n/<code>.json, keyed by PREFIX.

    python scripts/i18n_merge_batch.py batch.json

``batch.json`` is ``{lang: {key_prefix: translation}}``. A prefix is matched
against the catalogue's own keys, so a long tooltip does not have to be retyped
to be translated — and an ambiguous or unmatched prefix is an error rather than
a silently skipped string, which is how a translation goes missing.

The catalogue is written back in the shape the repo uses: keys sorted with
``@language_name`` first, ``ensure_ascii=False``, one-space indent, trailing
newline — so the diff shows only the lines that changed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def resolve(prefix: str, keys: list[str]) -> str:
    exact = [k for k in keys if k == prefix]
    if exact:
        return exact[0]
    hits = [k for k in keys if k.startswith(prefix)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise SystemExit(f"NO KEY starts with {prefix[:60]!r}")
    raise SystemExit(f"{len(hits)} keys start with {prefix[:60]!r} — be more specific")


def main() -> int:
    batch = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    for lang, pairs in batch.items():
        path = ROOT / "data" / "i18n" / f"{lang}.json"
        cat = json.loads(path.read_text(encoding="utf-8"))
        keys = list(cat)
        done = 0
        for prefix, value in pairs.items():
            cat[resolve(prefix, keys)] = value
            done += 1
        # PLAIN sorted, with no special case for "@language_name". All twelve
        # catalogues on disk have it at its sorted position (index 160), not
        # hoisted — hoisting it here would move one line in every file on every
        # merge, for no reason.
        ordered = {k: cat[k] for k in sorted(cat)}
        # indent=2 IS THE REPO STANDARD, and this line used to say 1. Every
        # catalogue on disk is indent=2, so merging with 1 re-indents the whole
        # file: one wave turned 154 real changes into an 8,186-line diff, and
        # the next translator could not see what had actually been touched.
        # No trailing newline either — every catalogue ends on "}".
        path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"  {lang}: {done} translated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
