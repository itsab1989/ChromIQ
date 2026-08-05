"""#137 T12 — the plan's tables must keep describing the real code.

Knut, 2026-08-05, on how to make an implementation stick:

    *"the only way to get the implementation right is to force claude to build
    complete tables with all combinations of responses and input conditions for
    all features, and then also force mapping in the tables the code lines where
    input conditions are implemented and where all options of output events/
    actions are implemented. This forces implementation, so it is not skipped
    silently."*

He is right, and #130 proved it: the §M message catalogue plus its map is why
that model shipped without a message quietly going missing — because a test
parsed the table and failed when code and table disagreed.

So this file parses ``docs/design/calibration_run_type_plan.md`` and fails when

* a table row promises an action with no code anchor at all, or
* an anchor names a file or symbol that no longer exists.

A renamed function therefore breaks the build rather than rotting the document.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "design" / "calibration_run_type_plan.md"

#: Paths in the plan that are deliberately about work still to come.
_PLACEHOLDERS = {"new"}

#: Where anchors may live. Everything else in backticks is prose.
_SEARCH_DIRS = ("core", "ui", "workflow", "scripts", "data", "tests")


def _plan_text() -> str:
    assert PLAN.is_file(), (
        f"{PLAN.relative_to(ROOT)} is missing — it is the committed copy of the "
        "plan posted on #137 and this test's input")
    return PLAN.read_text()


def _repo_text() -> str:
    out = []
    for d in _SEARCH_DIRS:
        for p in sorted((ROOT / d).rglob("*")):
            if p.suffix in (".py", ".yaml", ".yml") and p.is_file():
                out.append(p.read_text(errors="ignore"))
    return "\n".join(out)


REPO = None


def _repo():
    global REPO
    if REPO is None:
        REPO = _repo_text()
    return REPO


def _file_anchors(text: str) -> "set[str]":
    """`core/file_manager.py:318` → the path part."""
    return {m.group(1) for m in
            re.finditer(r"`([a-z_]+(?:/[A-Za-z0-9_.\-]+)+\.(?:py|yaml|md))"
                        r"(?::\d+(?:-\d+)?)?`", text)}


def _symbol_anchors(text: str) -> "set[str]":
    """Backticked identifiers that name code: ``snapshot_slot``,
    ``Calibration.archive_to_old``, ``RUN_TYPE_CALIBRATION``."""
    out = set()
    for m in re.finditer(r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
                         r"(?:\(\))?`", text):
        name = m.group(1)
        if "." in name and not name.split(".")[0][0].isupper():
            continue                       # a module path, not a symbol
        if name in _PLACEHOLDERS or len(name) < 4:
            continue
        if name.islower() and "_" not in name and "." not in name:
            continue                       # ordinary prose in backticks
        out.add(name.split(".")[-1])
    return out


def test_the_plan_is_committed():
    _plan_text()


def test_every_file_anchor_exists():
    missing = sorted(a for a in _file_anchors(_plan_text())
                     if not (ROOT / a).exists())
    assert not missing, f"the plan points at files that do not exist: {missing}"


def test_every_symbol_anchor_exists():
    """A renamed function must break this, not quietly rot the document."""
    repo = _repo()
    missing = sorted(s for s in _symbol_anchors(_plan_text()) if s not in repo)
    assert not missing, (
        "the plan names code that no longer exists: " + ", ".join(missing))


def _tables(text: str) -> "list[list[list[str]]]":
    tables, current = [], []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(set(c) <= set("-: ") for c in cells):
                current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def test_no_action_row_is_left_without_an_anchor():
    """The rule that makes this method work: a row with an empty "Acted at" is
    unimplemented work, not a description."""
    empty = []
    for table in _tables(_plan_text()):
        header = [h.lower() for h in table[0]]
        if not any("acted at" in h for h in header):
            continue
        col = next(i for i, h in enumerate(header) if "acted at" in h)
        for row in table[1:]:
            if len(row) <= col:
                continue
            cell = row[col]
            if not cell or cell in {"—", "-"}:
                empty.append(" | ".join(row[:2]))
    assert not empty, (
        "these rows promise behaviour with nowhere in the code doing it:\n  "
        + "\n  ".join(empty))


def test_the_tables_actually_carry_both_columns():
    """Guards the guard: if the columns were renamed away, every check above
    would pass by finding nothing."""
    text = _plan_text()
    assert "**Read at**" in text and "**Acted at**" in text
    tables = [t for t in _tables(text)
              if any("acted at" in h.lower() for h in t[0])]
    assert len(tables) >= 5, f"only {len(tables)} mapped tables found"
