"""The languages ChromIQ ships, read off disk instead of written out.

WHY THIS FILE EXISTS. Roughly thirty places in the suite want "every shipped
language", and until 2026-09-21 each of them carried its own literal list. The
lists went stale silently and in different directions: when Ukrainian arrived
(LackiUA, 6,008 rows, the largest catalogue in the tree) eight sweeps kept
enumerating twelve, several of them under a comment that said "every shipped
language" — and one,
`tests/test_a_long_label_is_not_clipped_by_its_indent.py`, was stale in two
directions at once, missing `ja` and `zh_CN` as well as `uk`.

A sweep that names its languages is a sweep that can be silently narrowed. A
sweep that asks the catalogue directory cannot: the next contributor's JSON
lands in `data/i18n/` and every guard that imports this module widens with it.

ENGLISH IS THE SOURCE LANGUAGE AND HAS NO CATALOGUE. `core.i18n.tr()` looks a
key up in `data/i18n/<code>.json` and falls back to the key itself, which IS
the English text, so English ships no JSON file. That is the whole reason for
the two functions below rather than one: a guard that renders the UI wants
English in the sweep (it is a real language a user can pick, and often the one
with the most room, which is exactly why a defect can hide in it); a guard that
checks translation FILES must not, because there is no file to check.
"""
from __future__ import annotations

from pathlib import Path

#: `data/i18n/`, where every catalogue lives. `*.json` is not recursive, so
#: `data/i18n/staging/<code>.partial.json` (work in progress, merged in by
#: `core.i18n`) is deliberately not picked up: a partial catalogue is not a
#: shipped language.
CATALOGUE_DIR = Path(__file__).resolve().parents[2] / "data" / "i18n"


def catalogue_languages() -> list[str]:
    """Every language code with a shipped catalogue, sorted. No English."""
    codes = sorted(p.stem for p in CATALOGUE_DIR.glob("*.json"))
    assert codes, f"no catalogues found in {CATALOGUE_DIR}"
    return codes


def shipped_languages() -> list[str]:
    """Every language a user can pick, English first, then the catalogues."""
    return ["en"] + catalogue_languages()
