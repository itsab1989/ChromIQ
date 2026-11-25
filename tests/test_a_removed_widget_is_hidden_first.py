"""A widget is hidden before its parent is taken away.

`w.setParent(None)` makes a widget a window of its own. A layout that just got
the widget has queued a "show it unless somebody hid it" for it, and while a
nested event loop runs (a message box, the print dialog) that comes before its
deletion: the removed button or label stands on the screen as a little window
(seen on screen in the i1iO table's panel, 25 Nov 2026). An explicit `hide()`
before it cancels that. `tests/i1io_table/test_no_stray_windows.py` shows the
effect; this keeps the pattern out of the whole of `ui/`.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

UI = Path(__file__).resolve().parent.parent / "ui"

#: (file under ui/, the object): why it needs no hide().
ALLOWED = {
    ("dialogs/reference_values_dialog.py", "sub"):
        "a QLayout: a layout is never a window",
}


def _takes_the_parent(node) -> "str | None":
    """The source of the object whose parent this statement takes away."""
    if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
        return None
    call = node.value
    if not (isinstance(call.func, ast.Attribute) and call.func.attr == "setParent"):
        return None
    args = [*call.args, *(k.value for k in call.keywords)]
    if not (args and isinstance(args[-1], ast.Constant) and args[-1].value is None):
        return None
    # `w.setParent(None)`, and the unbound `QWidget.setParent(w, None)`
    return ast.unparse(call.func.value if len(args) == 1 else args[0])


def _hides(node, name: str) -> bool:
    return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and ast.unparse(node.value) in (f"{name}.hide()",
                                            f"{name}.setVisible(False)"))


def _faults(source: str) -> "list[tuple[int, str]]":
    """Every parent taken away without a hide() of the same object as the
    statement right before it."""
    out = []
    for parent in ast.walk(ast.parse(source)):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(parent, field, None)
            if not isinstance(block, list):
                continue
            for i, node in enumerate(block):
                name = _takes_the_parent(node)
                if name is not None and not (i and _hides(block[i - 1], name)):
                    out.append((node.lineno, name))
    return out


@pytest.mark.parametrize("source,faults", [
    ("w.setParent(None)", 1), ("w.hide()\nw.setParent(None)", 0),
    ("w.setVisible(False)\nw.setParent(None)", 0),
    ("x.hide()\nw.setParent(None)", 1),
    ("w.setParent(None)\nw.hide()", 1),
    ("if a:\n    w.hide()\nw.setParent(None)", 1),
    ("try:\n    w.setParent(None)\nfinally:\n    v.setParent(parent=None)", 2),
    ("QWidget.setParent(w, None)", 1), ("w.setParent(self)", 0)])
def test_the_check_sees_the_pattern(source, faults):
    assert len(_faults(source)) == faults


def test_every_call_is_a_statement_the_check_reads():
    """`setParent(None)` inside an expression would be read by nobody."""
    for path in sorted(UI.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        read = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)}
        for call in ast.walk(tree):
            if isinstance(call, ast.Call) and id(call) not in read:
                assert _takes_the_parent(ast.Expr(value=call)) is None, (
                    f"{path.name}:{call.lineno}")


def test_no_widget_loses_its_parent_unhidden():
    found, used = [], set()
    for path in sorted(UI.rglob("*.py")):
        name = path.relative_to(UI).as_posix()
        for line, obj in _faults(path.read_text(encoding="utf-8")):
            if (name, obj) in ALLOWED:
                used.add((name, obj))
            else:
                found.append(f"ui/{name}:{line}: {obj}.setParent(None) without "
                             f"{obj}.hide() right before it")
    assert not found, "\n".join(found)
    assert used == set(ALLOWED), "an entry of ALLOWED that nothing uses"


def test_the_scanner_preview_is_back_in_the_window_after_its_pop_out(
        qtbot, monkeypatch):
    """The one place that gives the widget a parent again: it is hidden while
    it has none, and shown in its place."""
    from core.settings import AppSettings
    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    class Runner:
        is_running = False

    d = ScannerProfileDialog(Runner(), AppSettings())
    qtbot.addWidget(d)
    d.show()
    shown = d._marquee.isVisibleTo(d)
    alone = []
    real = d._marquee.setParent
    monkeypatch.setattr(d._marquee, "setParent", lambda p: (
        alone.append(d._marquee.isHidden()), real(p))[1])
    d._toggle_popout()
    d._popout.close()
    qtbot.wait(20)
    assert d._popout is None and alone == [True]
    assert d._marquee_box.indexOf(d._marquee) == 0
    assert d._marquee.isVisibleTo(d) is shown is True
