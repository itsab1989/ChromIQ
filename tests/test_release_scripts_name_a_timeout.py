"""Every subprocess call in the release/comparison scripts has a timeout=
(CLAUDE.md: a call without one can wait for ever; 4.3.34 review nit: the git
worktree add/remove/prune in compare_with_release.py and the git show in
make_lights_v4333_fixture.py had none)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("script", ["scripts/compare_with_release.py",
                                    "scripts/make_lights_v4333_fixture.py"])
def test_every_subprocess_call_has_a_timeout(script):
    tree = ast.parse((ROOT / script).read_text(encoding="utf-8"))
    missing = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
                and node.func.attr in ("run", "check_output", "call",
                                       "check_call")):
            if not any(k.arg == "timeout" for k in node.keywords):
                missing.append(node.lineno)
    assert not missing, f"{script}: subprocess calls without timeout= at {missing}"
