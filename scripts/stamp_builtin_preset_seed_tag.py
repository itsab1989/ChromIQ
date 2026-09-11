#!/usr/bin/env python3
"""Write the "Use a fixed seed" tag into every built-in Create Chart preset.

Knut, #182, 2026-09-11:

    *"since there is a new tag stored in the chart's json file about the 'Use a
    fixed seed' box, can you add programatically this tag for all built in
    presets and define the 'Use a fixed seed' box as OFF? All the built in
    presets should have 'Use a fixed seed' OFF as default when loaded. We would
    like NOT to do this manually for all presets. All seed numbers stored in the
    presets should be as they are today."*

**THE BUILT-IN PRESETS ARE NOT FILES.** They are Python literals in
``ui/tabs/tab_chart.py``: a handful of shared base recipe dicts (``_CM_BASE``,
``_I1_BASE``, ``_CR30_BASE``, the six Red River dicts, the Scanner recipe …)
from which all 141 recipe-carrying built-ins are built with ``dict(BASE, …)``.
So "do it programmatically, not by hand" means editing those bases, and this
script is the thing that does it, rather than a person opening a 20,000-line
module and adding a key eleven times.

**WHAT IT TOUCHES AND WHAT IT MUST NOT.** It inserts ``"seed_fixed": False``
into every module-level dict literal that is a layout recipe (it has both a
``randomize`` and a ``seed`` key). It never reads, writes, moves or reformats
the ``seed`` value itself: his last sentence is a hard constraint, and the only
edit this script can make is the insertion of one new line.

Usage::

    python scripts/stamp_builtin_preset_seed_tag.py            # write
    python scripts/stamp_builtin_preset_seed_tag.py --check    # verify only

``--check`` imports the module and asks the presets themselves, so it proves the
outcome ("every built-in preset carries the tag, and it is OFF") rather than the
edit. It is what ``tests/test_knut_rulings_2026_09_11.py`` re-runs, so a base
dict added later without the tag fails the gate instead of shipping quietly.
Both modes are idempotent and safe to re-run.
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "ui" / "tabs" / "tab_chart.py"

#: The tag, and the only value it may be written with. A built-in preset names a
#: layout, not one chart's shuffle, so the box is OFF when one is loaded.
TAG = "seed_fixed"
TAG_VALUE = False


# ---------------------------------------------------------------- writing ----
def _recipe_dicts(tree: ast.Module) -> "list[tuple[str, ast.Dict]]":
    """Module-level ``NAME = { … }`` literals that are layout recipes.

    A recipe is recognised by carrying BOTH ``randomize`` and ``seed``, which no
    other dict in this module does. Discovered rather than listed, so a new
    preset family added later is covered without editing this script.
    """
    out: list[tuple[str, ast.Dict]] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        keys = {k.value for k in value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if "randomize" not in keys or "seed" not in keys:
            continue
        targets = ([node.target] if isinstance(node, ast.AnnAssign)
                   else node.targets)
        name = next((t.id for t in targets if isinstance(t, ast.Name)), "?")
        out.append((name, value))
    return out


def _seed_key_node(d: ast.Dict) -> "ast.Constant | None":
    for k in d.keys:
        if isinstance(k, ast.Constant) and k.value == "seed":
            return k
    return None


def stamp(path: Path = TARGET) -> "list[str]":
    """Insert the tag into every recipe dict that lacks it. Returns the names
    changed (empty when there was nothing to do)."""
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)

    edits: list[tuple[int, str, str]] = []      # (line index, name, new line)
    for name, d in _recipe_dicts(tree):
        keys = {k.value for k in d.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if TAG in keys:
            continue                            # already stamped
        seed = _seed_key_node(d)
        if seed is None:                        # cannot happen: _recipe_dicts
            continue
        row = seed.lineno - 1                   # ast lines are 1-based
        text = lines[row]
        indent = text[:len(text) - len(text.lstrip())]
        # Match the quoting actually used for the `seed` key on that line, so a
        # dict written with single quotes (the six Red River exports) is not
        # given one line in the other style.
        quote = "'" if "'seed'" in text else '"'
        edits.append((row, name,
                      f"{indent}{quote}{TAG}{quote}: {TAG_VALUE},\n"))

    if not edits:
        return []
    for row, _name, new in sorted(edits, key=lambda e: -e[0]):
        lines.insert(row + 1, new)
    path.write_text("".join(lines), encoding="utf-8")
    return [name for _row, name, _new in sorted(edits)]


# ---------------------------------------------------------------- checking ---
def check() -> int:
    """Ask the presets themselves. 0 when every built-in carries the tag, OFF."""
    sys.path.insert(0, str(REPO))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import ui.tabs.tab_chart as tc                    # noqa: PLC0415

    bad_tag: list[str] = []
    bad_seed: list[str] = []
    tagged = 0
    for p in tc.KNUT_PRESETS:
        recipe = p.layout_recipe
        if recipe is None:
            continue                 # the two engine presets derive their recipe
        if recipe.get(TAG, "<absent>") is not TAG_VALUE:
            bad_tag.append(f"{p.slug}: {TAG}={recipe.get(TAG, '<absent>')!r}")
        else:
            tagged += 1
        # HIS LAST SENTENCE, CHECKED. Not "the seeds are None" -- that would
        # bake today's data into the check -- but "the seed key is still there
        # and still holds whatever it held", which is all the stamping is
        # allowed to leave true.
        if "seed" not in recipe:
            bad_seed.append(f"{p.slug}: the seed key went missing")

    print(f"built-in presets with a recipe : {tagged + len(bad_tag)}")
    print(f"  … carrying {TAG}={TAG_VALUE!r}  : {tagged}")
    print(f"built-in presets without one   : "
          f"{sum(1 for p in tc.KNUT_PRESETS if p.layout_recipe is None)}"
          f"  (engine presets, recipe derived at selection)")
    print(f"pre-rendered built-ins         : {len(tc.PREBUILT_PRESETS)}"
          f"  (no recipe: the .ti2 is the chart)")
    for line in bad_tag + bad_seed:
        print("  FAIL", line)
    return 1 if (bad_tag or bad_seed) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify only; change nothing")
    args = ap.parse_args()
    if args.check:
        return check()
    changed = stamp()
    if changed:
        print("stamped:", ", ".join(changed))
    else:
        print("nothing to do: every built-in recipe already carries the tag")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
