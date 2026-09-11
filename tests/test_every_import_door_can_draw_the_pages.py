"""Every way into the chart import must be able to draw missing pages.

`import_external_chart` copies; it draws pages only when it is handed the
ArgyllCMS binaries. That makes the binaries a thing a caller can forget, and
this project's most repeated fault is a guard placed on one door and not on the
identical door beside it: the verification branch and the profiling branch of
this very function are two such doors, and so are the three places in the
loader that call it.

So this reads the source. A behavioural test can only cover the doors somebody
remembered to write a test for, which is the same set somebody remembered to
fix.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _calls(path: Path, name: str) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == name:
            out.append(node)
        elif isinstance(f, ast.Name) and f.id == name:
            out.append(node)
    return out


def _app_files() -> list[Path]:
    return [p for d in ("ui", "workflow", "core")
            for p in (ROOT / d).rglob("*.py")]


def test_every_call_in_the_app_passes_the_binaries():
    missing = []
    for path in _app_files():
        for call in _calls(path, "import_external_chart"):
            if not any(k.arg == "bin_dir" for k in call.keywords):
                missing.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert not missing, (
        "these import a chart without the binaries, so a chart arriving with no "
        "pages would leave a run that cannot be printed: " + ", ".join(missing))


def test_there_really_are_several_doors():
    """THE TEST ABOVE IS WORTH NOTHING IF IT COUNTS ZERO. It passed vacuously
    while the function was still called `import_chart` in an earlier draft."""
    n = sum(len(_calls(p, "import_external_chart")) for p in _app_files())
    assert n >= 3, f"only {n} calls found; has the function been renamed?"


def test_both_branches_of_the_import_itself_draw():
    """A verification chart and a profiling chart are filed in different
    folders by two different paragraphs of one function."""
    src = (ROOT / "workflow" / "chart_import.py").read_text(encoding="utf-8")
    body = src[src.index("def import_external_chart"):]
    body = body[:body.index("\ndef ", 1)]
    assert body.count("rebuild_missing_pages(") == 2, \
        "one of the two run types no longer draws the pages it is missing"


@pytest.mark.parametrize("name", ["rebuild_missing_pages", "chart_page_tiffs"])
def test_the_helpers_are_importable_by_name(name):
    import workflow.chart_import as ci
    assert callable(getattr(ci, name))
