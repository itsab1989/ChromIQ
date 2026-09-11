"""A private helper in the Chart tab that nothing calls is dead weight.

`_builtin_default_name` was flagged for deletion in one challenge round, carried
into the next one unflagged, and was still there a round after that, because
nothing but a person reading the file could notice. Twenty thousand lines is too
many to re-read; this is the check that notices instead.

It is deliberately crude, and that is the point: a private helper whose NAME
appears nowhere else in the repository cannot be reached by a call, by a
`getattr("_name")`, by a signal connection or by a test. There is no clever way
to be wrong about it.

**This file excludes itself from what it searches**, which is not tidiness. The
first draft did not, and every name it listed as a known orphan stopped being an
orphan the moment the list was written, so the check reported nothing wrong with
a file it had just been told about.

THE THREE NAMED BELOW ARE NOT BLESSED, THEY ARE RECORDED. They were found by
this check on 2026-09-11, they are not part of the item that brought it here,
and one of them looks like a symptom rather than dead code: `_munki_tooltip` is
the sibling of `_knut_tooltip` and `_prebuilt_tooltip`, which `_builtin_tooltip`
does call, so it may be a branch that was dropped rather than a helper that was
outgrown. Deciding that is somebody's call, not this test's. **The list may
shrink and must never grow**: a new orphan is what this file exists to stop.
"""
from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "ui" / "tabs" / "tab_chart.py"
SELF = Path(__file__).resolve()

#: Orphans that already existed when this check was written. See the docstring.
KNOWN_ORPHANS = {
    "_make_load_profile_button",
    "_munki_tooltip",
    "_shorten_for_preview",
}

_SEARCHED = ("ui", "core", "workflow", "data", "tests", "scripts")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _private_methods(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name.startswith("_")
                    and not item.name.startswith("__")):
                out.append(item.name)
    return out


def _identifier_counts() -> Counter:
    """Every identifier in the tree, counted once, in one pass.

    One pass, not one pass per name: 368 separate scans of 19 MB took 75
    seconds, which is most of a minute of the gate for a check that can be
    almost free.
    """
    seen: list[Path] = []
    for sub in _SEARCHED:
        seen.extend((ROOT / sub).rglob("*.py"))
    seen.extend(ROOT.glob("*.py"))
    counts: Counter = Counter()
    for path in seen:
        if path.resolve() == SELF:
            continue
        counts.update(_IDENT.findall(
            path.read_text(encoding="utf-8", errors="replace")))
    return counts


def _orphans() -> set[str]:
    counts = _identifier_counts()
    # One occurrence is the definition itself.
    return {name for name in set(_private_methods(TARGET))
            if counts[name] <= 1}


def test_no_new_orphan_private_helper_in_the_chart_tab():
    new = sorted(_orphans() - KNOWN_ORPHANS)
    assert not new, (
        "these private helpers in ui/tabs/tab_chart.py are defined and never "
        f"named again anywhere in the repository: {new}. Delete them, or call "
        "them, or say in KNOWN_ORPHANS why they stay.")


def test_the_helper_this_check_was_written_for_is_gone():
    """`_builtin_default_name` specifically. It survived three rounds."""
    assert "_builtin_default_name" not in _private_methods(TARGET)


def test_the_known_list_has_not_grown_silently():
    """A list of accepted orphans is only safe while it shrinks.

    If one of these gets a caller, or is deleted, it must leave this list in the
    same change, so the list can never quietly become the place orphans live.
    """
    stale = sorted(KNOWN_ORPHANS - _orphans())
    assert not stale, (
        f"{stale} are listed as known orphans but are no longer orphans. "
        "Remove them from KNOWN_ORPHANS.")
