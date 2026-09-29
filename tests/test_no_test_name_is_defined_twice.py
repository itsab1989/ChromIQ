"""A test name defined twice in one file is a test SILENTLY DELETED.

Python keeps the last definition of a name and throws the earlier one away
without a word: no warning, no error, no change in the collected count that
anybody would notice. So a file that defines ``test_x`` twice does not run
``test_x`` twice — it runs it once and loses whatever the first copy checked.
Pytest cannot help either; by the time it collects the module, the first
function no longer exists.

**This is not hypothetical, and it is a merge hazard rather than a typing
mistake.** Challenge round 32 found
``test_qt_fallback_translates_norwegian_buttons`` defined twice in
``tests/test_i18n.py``, at line 177 and again at line 1273, byte-for-byte
identical. It arrived with the Ukrainian round (``61c18aa9``): the file was
touched by several parallel worktrees, the hand-merge kept both sides, and the
copy at line 177 stopped running from that commit onwards. Eight rounds, an
integrator and a green suite all passed over it, because a doubled name looks
exactly like a healthy one from every direction except this one.

The bodies happened to be identical that time, so nothing was actually lost.
The next one will not be.

MUTATION: append a second ``def`` with the name of any test already in the same
file — identical body or not — and this goes red naming the file, the name and
both line numbers.
"""
from __future__ import annotations

import ast
import collections
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


def _test_files() -> "list[Path]":
    return sorted(p for p in TESTS.rglob("test_*.py") if p.is_file())


def _duplicate_defs(path: Path) -> "list[tuple[str, list[int]]]":
    """Names defined more than once at MODULE level, with their line numbers.

    Module level only, deliberately. A method named the same in two different
    classes is two different attributes and shadows nothing; only a repeated
    top-level name destroys the earlier object.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:                       # pragma: no cover - loud
        pytest.fail(f"{path.name} does not parse: {exc}")
    lines: "dict[str, list[int]]" = collections.defaultdict(list)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines[node.name].append(node.lineno)
    return [(n, ls) for n, ls in sorted(lines.items()) if len(ls) > 1]


def test_no_test_file_defines_the_same_name_twice():
    """Every module-level def in tests/ is defined exactly once."""
    offenders = []
    for path in _test_files():
        for name, linenos in _duplicate_defs(path):
            offenders.append(
                f"{path.relative_to(ROOT)}: {name} defined "
                f"{len(linenos)} times, at lines "
                f"{', '.join(str(n) for n in linenos)} — Python keeps only "
                f"the last, so the earlier one(s) never run")
    assert not offenders, (
        "a name defined twice at module level silently deletes the earlier "
        "definition:\n  " + "\n  ".join(offenders))


def test_the_sweep_is_not_vacuous():
    """It must actually be reading files.

    The register-citation sweep on this project passed for weeks while
    examining ZERO files, because its skip list matched the absolute path of
    every checkout under `.claude/worktrees/`. A sweep that finds nothing
    because it looked at nothing is worse than no sweep, so this one says how
    much it looked at.
    """
    files = _test_files()
    assert len(files) > 200, (
        f"only {len(files)} test files found under {TESTS} — this sweep is "
        "not reading the suite it is supposed to guard")
    total_defs = 0
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        total_defs += sum(
            1 for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    assert total_defs > 2000, (
        f"only {total_defs} module-level defs seen across {len(files)} files")


def test_the_detector_finds_a_double_it_is_given(tmp_path):
    """The predicate itself, against a file built to be wrong.

    Without this, the guard above could pass for ever on a broken `_duplicate_defs`
    and nobody would know until a real double slipped through.
    """
    good = tmp_path / "test_good.py"
    good.write_text("def test_a():\n    pass\n\n\ndef test_b():\n    pass\n",
                    encoding="utf-8")
    assert _duplicate_defs(good) == []

    bad = tmp_path / "test_bad.py"
    bad.write_text("def test_a():\n    pass\n\n\ndef test_a():\n    pass\n",
                   encoding="utf-8")
    assert _duplicate_defs(bad) == [("test_a", [1, 5])]

    # A method repeated inside two classes is NOT a double: different owners.
    classes = tmp_path / "test_classes.py"
    classes.write_text(
        "class TestOne:\n    def test_a(self):\n        pass\n\n\n"
        "class TestTwo:\n    def test_a(self):\n        pass\n",
        encoding="utf-8")
    assert _duplicate_defs(classes) == []
