#!/usr/bin/env python3
"""Where ChromIQ's user-facing text lives, and which of it carries an em dash.

One module, used by both `tests/test_no_new_em_dash_in_user_facing_text.py` and
this script's own command line, so the test and the housekeeping tool can never
disagree about what counts as user-facing text.

Usage:
    python scripts/em_dash_check.py --report   # what is left, and what is stale
    python scripts/em_dash_check.py --prune    # drop baseline entries whose
                                               # string no longer exists
    python scripts/em_dash_check.py --freeze   # FIRST TIME ONLY: write the
                                               # baseline from what ships today

`--prune` only ever REMOVES entries. There is deliberately no "add everything
that fails" mode: a baseline that can absorb a new violation is not a baseline,
and the whole point is that new text cannot quietly join the grandfathered set.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

EM = "—"                      # — the long one. NOT the en dash –.
BASELINE = ROOT / "tests" / "data" / "em_dash_baseline.json"
ALLOWED = ROOT / "tests" / "data" / "em_dash_allowed.json"


def english_strings() -> "dict[str, str]":
    """Every English string a user can read, as {string: where it came from}.

    Three sources, because text enters the app three ways: `tr()` literals in
    the code, the tooltips and labels in `data/parameters.yaml`, and the §M
    message catalogue. Missing one of the three would leave a door open.
    """
    import yaml

    import i18n_extract as X

    out: dict[str, str] = {}
    for s in X.extract_keys():
        out[s] = "tr() in ui/ workflow/ core/ main.py"
    try:
        for s in X._message_catalogue_keys():
            out.setdefault(s, "workflow/measurement_messages.py")
    except Exception:                                    # pragma: no cover
        pass

    doc = yaml.safe_load((ROOT / "data" / "parameters.yaml").read_text(
        encoding="utf-8"))

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("tooltip_title", "tooltip_body", "label", "help") \
                        and isinstance(v, str):
                    out.setdefault(v, "data/parameters.yaml")
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return out


def translations_adding_an_em_dash() -> "list[tuple[str, str]]":
    """(language, key) for every translation that puts an em dash where the
    English source string has none.

    This needs no baseline of its own beyond today's exceptions: the rule is
    relative to the English, so it stays true as the English is cleaned up.
    """
    found = []
    for path in sorted((ROOT / "data" / "i18n").glob("*.json")):
        if path.name.startswith("parameters."):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        lang = path.stem
        for key, value in data.items():
            if key.startswith("@") or not isinstance(value, str):
                continue
            if EM in value and EM not in key:
                found.append((lang, key))
    return found


def key_id(s: str) -> str:
    """A short, stable id for a translation's English key.

    The English list below keeps whole strings, because that is the list
    somebody actually reads when they want to clean one up. The translation
    list does not need reading — its rule is mechanical — and storing 498 more
    copies of long help texts made the file five times bigger for nothing.
    """
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def load_baseline() -> "dict":
    if not BASELINE.is_file():
        return {"english": [], "translations": []}
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def load_allowed() -> "dict[str, str]":
    if not ALLOWED.is_file():
        return {}
    return json.loads(ALLOWED.read_text(encoding="utf-8"))


def _write(baseline: dict) -> None:
    baseline["english"] = sorted(set(baseline["english"]))
    baseline["translations"] = sorted({tuple(t) for t in
                                       baseline["translations"]})
    BASELINE.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")


def main() -> int:
    args = set(sys.argv[1:])
    english = english_strings()
    offenders = {s for s in english if EM in s}
    added = translations_adding_an_em_dash()

    if "--freeze" in args:
        if BASELINE.is_file():
            print("baseline already exists; refusing to overwrite it. "
                  "Use --prune.")
            return 1
        _write({"english": sorted(offenders),
                "translations": [[lang, key_id(k)] for lang, k in added]})
        print(f"froze {len(offenders)} English strings and {len(added)} "
              f"translation entries")
        return 0

    base = load_baseline()
    base_en = set(base["english"])
    stale = sorted(base_en - offenders)
    live_keys = {k for _lang, k in added}
    added_ids = {(lang, key_id(k)) for lang, k in added}
    stale_tr = [t for t in base["translations"] if tuple(t) not in added_ids]

    if "--prune" in args:
        _write({"english": sorted(base_en & offenders),
                "translations": [list(t) for t in base["translations"]
                                 if tuple(t) in added_ids]})
        print(f"pruned {len(stale)} English and {len(stale_tr)} translation "
              f"entries that no longer exist")
        return 0

    print(f"English user-facing strings ........ {len(english)}")
    print(f"  carrying an em dash .............. {len(offenders)}")
    print(f"  grandfathered in the baseline .... {len(base_en & offenders)}")
    print(f"  NOT grandfathered (would fail) ... "
          f"{len(offenders - base_en - set(load_allowed()))}")
    print(f"  stale baseline entries ........... {len(stale)}"
          f"{'  (run --prune)' if stale else ''}")
    print(f"translations adding an em dash ..... {len(added)} "
          f"across {len({l for l, _ in added})} languages")
    print(f"  live keys affected ............... {len(live_keys)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
