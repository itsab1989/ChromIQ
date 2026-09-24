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
        pre = next((k.value for k in node.keywords if k.arg == "prefix"),
                   None)
        if pre is None and node.args:
            continue                         # positional: not ours to guess
        if pre is not None and _sweepable(pre):
            continue
        out.append(node.lineno)
    return out


def _sweepable(prefix_node) -> bool:
    """Whether a ``prefix=`` expression makes a name the sweep takes BY NAME.

    **A PREFIX IS NOT ENOUGH, IT HAS TO BE THE SWEEP'S.** This guard used to
    accept any ``prefix=``, while `_sweep_stale_temp_dirs` takes only
    ``chromiq[-_]*`` by name. `mkdtemp(prefix="autotext-…")` in one test
    therefore passed here and was never swept: 5,544 folders and 5.3 GB of
    page TIFFs on 2026-09-24, and 18 driver scripts had the same hole."""
    if isinstance(prefix_node, ast.Constant) and isinstance(
            prefix_node.value, str):
        head = prefix_node.value
    elif isinstance(prefix_node, ast.JoinedStr) and prefix_node.values and \
            isinstance(prefix_node.values[0], ast.Constant):
        head = str(prefix_node.values[0].value)
    else:
        return False                         # computed: cannot be proved
    return head.startswith(("chromiq-", "chromiq_"))


@pytest.mark.parametrize("path", sorted(
    p for p in (_ROOT / "tests").glob("test_*.py")
    if p.name not in _EXEMPT))
def test_no_test_file_makes_a_temp_folder_the_sweep_cannot_see(path):
    """MUTATION: write `tempfile.mkdtemp()`, or `mkdtemp(prefix="x-")`, in any
    test file and this goes red."""
    bad = _bare_mkdtemp_calls(path)
    assert not bad, (
        f"{path.name} calls mkdtemp() with no chromiq- prefix at line(s) "
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


def _loose_temp_files(path: Path):
    """Every ``mktemp()`` / ``mkstemp()`` in *path* that names no ``dir=``."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        # the `tempfile` module's, not pytest's `tmp_path_factory.mktemp`,
        # which pytest removes itself
        if isinstance(fn, ast.Attribute):
            if not (isinstance(fn.value, ast.Name) and fn.value.id == "tempfile"):
                continue
            name = fn.attr
        else:
            name = getattr(fn, "id", "")
        if name not in ("mktemp", "mkstemp"):
            continue
        if any(k.arg == "dir" for k in node.keywords) or len(node.args) >= 3:
            continue
        out.append(node.lineno)
    return out


@pytest.mark.parametrize("path", sorted(
    p for p in (_ROOT / "tests").glob("test_*.py")
    if p.name not in _EXEMPT))
def test_no_test_file_drops_a_loose_temp_file(path):
    """**AND NO LOOSE FILES EITHER.** The sweep takes FOLDERS; a file made by
    ``mktemp()`` or ``mkstemp()`` straight into ``$TMPDIR`` is never removed.
    Measured 2026-09-24: 42,523 settings ``tmp*.ini`` files from three tests'
    ``QSettings(tempfile.mktemp(suffix=".ini"))`` and 4,024 ``.ti2`` files
    from one ``mkstemp``. Give it ``dir=`` a ``chromiq-test-*`` folder, or use
    ``tmp_path``.

    MUTATION: write ``tempfile.mktemp(suffix=".ini")`` in any test file and
    this goes red."""
    bad = _loose_temp_files(path)
    assert not bad, (
        f"{path.name} makes a loose temp file at line(s) "
        f"{', '.join(str(n) for n in bad)}: pass dir= a chromiq-test-* "
        "folder, or use tmp_path.")
