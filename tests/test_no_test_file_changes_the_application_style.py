"""No test file may set the style on the shared QApplication.

**THIS COST A RELEASE GATE.** `tests/conftest.py` pins ONE QApplication per
worker, so its style is shared by every test that worker runs.
`test_the_layout_labels_are_never_clipped.py` set it to
`WinButtonLayoutStyle("Fusion")`, which is what `main.py` does and looks
harmless; a QProxyStyle reports an EMPTY `objectName()`, and
`test_the_suite_paints_with_the_shipped_style` asserts that name is "fusion".
With `--dist loadfile` the two files land on the same worker in an order nobody
chooses, so the gate came out red on a file that had nothing to do with the
failure. It was found on the release gate for 4.2.5, and reproduced
deterministically by running the two files in that order.

The behavioural half of this rule is that other file: it says what the style
IS. This one says nothing may change it, which is the half that catches the
shape before it lands rather than a run later.

A style set on a WIDGET is fine and common: it dies with the widget.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

TESTS = pathlib.Path(__file__).resolve().parent

#: Names that mean "the shared QApplication" when `.setStyle(...)` is called on
#: them. Deliberately a small list of the spellings this suite actually uses,
#: because a wrong guess here would police the wrong call.
_APP_NAMES = {"app", "a", "qapp", "_app", "application", "_PINNED_QAPP"}

#: Files allowed to do it, each for a stated reason.
_ALLOWED = {
    # The pin itself. Everything above exists to protect what it sets.
    "conftest.py",
    # Not a test: a standalone probe with its own QApplication, run by hand.
    "scanner_floor_probe.py",
}


def _offenders() -> "list[tuple[str, int, str]]":
    out: "list[tuple[str, int, str]]" = []
    for path in sorted(TESTS.glob("*.py")):
        if path.name in _ALLOWED:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                     # not ours to police
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not isinstance(fn, ast.Attribute) or fn.attr != "setStyle":
                continue
            recv = fn.value
            name = recv.id if isinstance(recv, ast.Name) else None
            if name in _APP_NAMES:
                out.append((path.name, node.lineno, name))
    return out


def test_no_test_file_sets_the_application_style():
    bad = _offenders()
    assert not bad, (
        "these set the style on the shared QApplication, which every other "
        "test on the worker then paints through:\n"
        + "\n".join(f"    {f}:{line}  {name}.setStyle(...)" for f, line, name in bad)
        + "\n\nPin nothing here: tests/conftest.py already sets Fusion. If a "
          "test genuinely needs another style, set it on the WIDGET, which "
          "dies with the widget."
    )


def test_the_check_can_actually_see_such_a_call(tmp_path):
    """THE CONTROL. An AST walk that matched nothing would pass this file for
    ever, and the fault it exists for would come straight back.

    MUTATION: break the `fn.attr != "setStyle"` test and this goes red.
    """
    sample = tmp_path / "sample.py"
    sample.write_text("def f(app):\n    app.setStyle('macos')\n", encoding="utf-8")
    tree = ast.parse(sample.read_text(encoding="utf-8"))
    hits = [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "setStyle"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id in _APP_NAMES]
    assert len(hits) == 1


def test_a_widget_level_setStyle_is_not_policed(tmp_path):
    """The other side of the control: this must not become a ban on the
    legitimate call, which `test_wrapping_checkbox_paints_in_two_calls.py`
    makes on a checkbox."""
    sample = tmp_path / "sample.py"
    sample.write_text("def f(cb, s):\n    cb.setStyle(s)\n", encoding="utf-8")
    tree = ast.parse(sample.read_text(encoding="utf-8"))
    hits = [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "setStyle"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id in _APP_NAMES]
    assert not hits
