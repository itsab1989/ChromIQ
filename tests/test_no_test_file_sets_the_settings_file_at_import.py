"""No test file sets ``CHROMIQ_SETTINGS_FILE`` in ``os.environ`` at import.

A module-level line runs at COLLECTION, and under pytest-xdist every worker
collects every file. ``tests/test_the_sweep_is_runnable.py`` did
``os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/chromiq-sweep-
selftest.ini")`` at its top, so every worker carried it for the whole run:
every ``AppSettings()`` in every other file took the sandbox branch and logged
"Settings SANDBOXED", and every child process a test started shared one fixed
``/tmp`` ini with every other worker and every later run. It surfaced
2026-10-03 as ``test_replacing_a_stored_chart_keeps_the_old_one.py`` failing
only under a loaded run. A file that needs the variable sets it in a fixture
(``monkeypatch.setenv``) or in a child's ``env=``.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VAR = "CHROMIQ_SETTINGS_FILE"


def _is_environ(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "environ"
            and isinstance(node.value, ast.Name) and node.value.id == "os")


def _mentions_var(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Constant) and n.value == VAR
               for n in ast.walk(node))


def _module_level_statements(tree: ast.Module):
    """The statements that run at import: the module body, and the bodies of
    top-level if/try/with blocks, but not functions or classes."""
    todo = list(tree.body)
    while todo:
        st = todo.pop()
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef,
                           ast.ClassDef)):
            continue
        yield st
        for field in ("body", "orelse", "finalbody", "handlers"):
            todo.extend(getattr(st, field, []) or [])


def _sets_it(st: ast.AST) -> bool:
    """Does this statement itself (not a nested def) put VAR in os.environ?"""
    if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    nodes = [st] if not hasattr(st, "body") else [
        n for n in ast.iter_child_nodes(st)
        if not isinstance(n, (ast.stmt, ast.excepthandler))]
    for top in nodes:
        for node in ast.walk(top):
            if isinstance(node, ast.Call):
                f = node.func
                if (isinstance(f, ast.Attribute) and _is_environ(f.value)
                        and f.attr in ("setdefault", "update", "__setitem__")
                        and _mentions_var(node)):
                    return True
                if (isinstance(f, ast.Attribute) and f.attr == "putenv"
                        and _mentions_var(node)):
                    return True
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = (node.targets if isinstance(node, ast.Assign)
                           else [node.target])
                for t in targets:
                    if (isinstance(t, ast.Subscript) and _is_environ(t.value)
                            and _mentions_var(t.slice)):
                        return True
    return False


def _offenders(tree: ast.Module) -> "list[int]":
    return sorted(st.lineno for st in _module_level_statements(tree)
                  if _sets_it(st))


def test_no_test_file_sets_it_at_import():
    """MUTATION: put the old ``os.environ.setdefault(...)`` line back at the
    top of ``test_the_sweep_is_runnable.py``."""
    bad = []
    for py in sorted((REPO / "tests").rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        bad += [f"{py.relative_to(REPO)}:{n}" for n in _offenders(tree)]
    assert not bad, (
        f"set {VAR} in a fixture, not at import (it leaks into every "
        "worker):\n" + "\n".join(bad))


def test_the_check_can_see_the_old_line():
    tree = ast.parse(
        "import os\n"
        f'os.environ.setdefault("{VAR}", "/tmp/x.ini")\n'
        "if True:\n"
        f'    os.environ["{VAR}"] = "also at import"\n'
        "def f():\n"
        f'    os.environ["{VAR}"] = "fine inside a function"\n')
    assert _offenders(tree) == [2, 4]


def test_importing_the_sweep_selftest_leaves_the_environment_alone():
    """Behaviour, not source: import the file the way collection does, in a
    clean child, and look at the environment afterwards."""
    env = {k: v for k, v in os.environ.items() if k != VAR}
    code = ("import os, tests.test_the_sweep_is_runnable as m; "
            f"print(repr(os.environ.get({VAR!r})))")
    r = subprocess.run([sys.executable, "-c", code], cwd=str(REPO), env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1] == "None", r.stdout
