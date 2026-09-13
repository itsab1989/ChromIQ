#!/usr/bin/env python3
"""Prove the third round's two capture-guard fixes actually land.

A mutation only counts if the MUTATION is proven to land (CLAUDE.md), so each
one is applied to a COPY of the guard, the copy is imported, and the guard's
own `_MUST_CATCH` / `_MUST_ALLOW` tables are re-run through the mutant. A
mutation that changes nothing is reported as a failed proof, not as a pass.

* Mutation A puts the alias rule back to `NAME = '<constant>'` only, which is
  what version four did. The ten new must-catch cases have to go red.
* Mutation B puts the offence rule back to "a program word and a flag word
  anywhere in one statement". The six new must-allow cases have to go red.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "tests" / "test_a_driver_photographs_the_window_not_the_screen.py"

ALIAS_LIVE = """\
            if node.value is not None and names:
                bindings.append((names, node.value))"""
ALIAS_MUTANT = """\
            if (isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str) and names):
                bindings.append((names, node.value))"""

DEFAULTS_LIVE = """\
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.Lambda)):"""
DEFAULTS_MUTANT = """\
        elif isinstance(node, (ast.Delete,)):
            pass
        elif False:"""

JOIN_LIVE = """\
        return (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)
                and (_joined(node.left) or _joined(node.right)))"""
JOIN_MUTANT = """\
        return False"""

ARGV_LIVE = """\
        if not any(_is_argv(n) for n in _own(stmt)):
            continue"""
ARGV_MUTANT = """\
        _p = _f = False
        for _n in _own(stmt):
            _a, _b = _marks(_n)
            _p, _f = _p or _a, _f or _b
        if not (_p and _f):
            continue"""


def load(src: str, name: str):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(src)
        path = Path(fh.name)
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        path.unlink(missing_ok=True)


def check(mod, live):
    """Which of the live guard's own cases this module disagrees with."""
    broke_catch = [k for k, s in live._MUST_CATCH.items()
                   if not mod._window_captures(s)]
    broke_allow = [k for k, s in live._MUST_ALLOW.items()
                   if mod._window_captures(s)]
    return broke_catch, broke_allow


def main() -> int:
    text = GUARD.read_text(encoding="utf-8")
    live = load(text, "guard_live")
    ok_catch, ok_allow = check(live, live)
    print(f"live guard: {len(live._MUST_CATCH)} must-catch, "
          f"{len(live._MUST_ALLOW)} must-allow, "
          f"{len(ok_catch) + len(ok_allow)} disagreements")
    if ok_catch or ok_allow:
        print("  !! the LIVE guard is already red, nothing below means anything")
        return 1

    rc = 0
    for label, old, new, expect in (
            ("A: alias follows only `NAME = <str constant>` (version four)",
             ALIAS_LIVE, ALIAS_MUTANT, "catch"),
            ("B: a program word and a flag word anywhere in one statement",
             ARGV_LIVE, ARGV_MUTANT, "allow"),
            ("C: a parameter default no longer binds a name",
             DEFAULTS_LIVE, DEFAULTS_MUTANT, "catch"),
            ("D: lists joined with `+` are no longer one command",
             JOIN_LIVE, JOIN_MUTANT, "catch")):
        print(f"\n### mutation {label}")
        if text.count(old) != 1:
            print(f"  !! the mutation did NOT land: {text.count(old)} matches "
                  "for the text it replaces")
            rc = 1
            continue
        mutant = load(text.replace(old, new), "guard_mutant")
        broke_catch, broke_allow = check(mutant, live)
        print(f"  mutation landed: source differs, module imported")
        print(f"  must-catch now MISSED ({len(broke_catch)}):")
        for k in sorted(broke_catch):
            print(f"    - {k}")
        print(f"  must-allow now REFUSED ({len(broke_allow)}):")
        for k in sorted(broke_allow):
            print(f"    - {k}")
        wanted = broke_catch if expect == "catch" else broke_allow
        if not wanted:
            print("  !! the mutation changed NOTHING the tests assert on")
            rc = 1
        else:
            print(f"  ok: the file goes RED on {len(wanted)} case(s)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
