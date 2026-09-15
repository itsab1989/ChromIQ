"""A temp folder the sweep cannot see is a folder nobody ever deletes.

**MEASURED 2026-09-15, on the owner's machine: `$TMPDIR` held 62 GB in 29,759
entries, and 57 GB of it was in 27,600 folders named `tmpXXXXXXXX`.** The
largest group was 1,150 folders holding one file each, `s.tif`, at 143 MB
apiece: 53 GB from a single test module that builds a sheet at six
resolutions. The second largest was 1,053 folders of help-card PDFs.

`tests/conftest.py::_sweep_stale_temp_dirs` was taught in September to look at
unprefixed folders too, but it may never judge them BY NAME, because `tmp*` is
what every application's `tempfile.mkdtemp()` produces. So it judges them by
CONTENTS and fails closed: a folder holding one `.tif`, or forty-two `.pdf`s,
carries none of the markers it recognises (`.ti1 .ti2 .ti3 .cht .cie .icc
.cal`, `project.json`, `meta.json`), and is left where it is, for ever.

Both halves of that are right. The half that was missing is here: **a test may
not create a temp folder the sweep is not allowed to recognise.** Give it the
project's prefix and the sweep takes it by name, safely, because no other
application writes `chromiq-`.

Use `tmp_path` where you can, which pytest removes on its own. Where a module
really needs `mkdtemp`, it must pass a prefix.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
#: The sweep's own fixture proves the unprefixed case is still recognised by
#: contents, so it is the one file that must keep calling mkdtemp bare.
_EXEMPT = {"test_the_sweep_sees_an_unprefixed_temp_folder.py"}


def _bare_mkdtemp_calls(path: Path):
    """Every ``mkdtemp()`` in *path* that passes no prefix, by line."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:                      # not ours to police
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name != "mkdtemp":
            continue
        if any(k.arg == "prefix" for k in node.keywords) or node.args:
            continue
        out.append(node.lineno)
    return out


@pytest.mark.parametrize("path", sorted(
    p for p in (_ROOT / "tests").glob("test_*.py")
    if p.name not in _EXEMPT))
def test_no_test_file_makes_a_temp_folder_the_sweep_cannot_see(path):
    """MUTATION: write `tempfile.mkdtemp()` in any test file and this goes red."""
    bad = _bare_mkdtemp_calls(path)
    assert not bad, (
        f"{path.name} calls mkdtemp() with no prefix at line(s) "
        f"{', '.join(str(n) for n in bad)}. That makes a `tmpXXXXXXXX` folder "
        "the sweep may not recognise by name, so it survives every run and "
        "every gate. Use the `tmp_path` fixture, or "
        'mkdtemp(prefix="chromiq-test-").')


def test_the_drivers_in_scripts_do_the_same():
    """A driver runs on the owner's machine, so its leftovers are his."""
    bad = {p.name: _bare_mkdtemp_calls(p)
           for p in sorted((_ROOT / "scripts").glob("*.py"))}
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, (
        "these drivers make a temp folder nothing will ever sweep: "
        + "; ".join(f"{k} line {v}" for k, v in bad.items()))
