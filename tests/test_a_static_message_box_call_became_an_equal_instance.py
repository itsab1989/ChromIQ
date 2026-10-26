"""The static `QMessageBox.critical(...)` calls became `ui.widgets.message_box`
(4.3.16), so they go through `keep_message_box_inside_the_work_area` like every
other box. The instance must be the static's equal: the same buttons, the
same default, the same Escape, and the same value returned for each.

Proved against Qt's own static, side by side: each case is answered once in
`QMessageBox.critical` and once in `message_box`, by the same key or click,
and the two answers and the two boxes must agree.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

SB = QMessageBox.StandardButton
ICONS = {"critical": QMessageBox.Icon.Critical,
         "warning": QMessageBox.Icon.Warning,
         "information": QMessageBox.Icon.Information,
         "question": QMessageBox.Icon.Question}


@pytest.fixture
def _app():
    return QApplication.instance() or QApplication([])


def _answer(how, seen):
    """Answer the box that is up: `how` is "escape", "return" or a standard
    button to click. Records what the box looked like first."""
    def go():
        box = QApplication.activeModalWidget()
        if not isinstance(box, QMessageBox):
            QTimer.singleShot(10, go)
            return
        seen.append({
            "buttons": sorted(int(box.standardButton(b).value)
                              for b in box.buttons()),
            "default": (int(box.standardButton(box.defaultButton()).value)
                        if box.defaultButton() is not None else None),
            "escape": (int(box.standardButton(box.escapeButton()).value)
                       if box.escapeButton() is not None else None),
            "icon": box.icon(), "title": box.windowTitle(), "text": box.text(),
        })
        if how == "escape":
            QTest.keyClick(box, Qt.Key.Key_Escape)
        elif how == "return":
            QTest.keyClick(box, Qt.Key.Key_Return)
        else:
            box.button(how).click()
    QTimer.singleShot(0, go)


CASES = [
    # (static, buttons, default)
    ("critical", None, None),          # what all nine converted calls use
    ("warning", SB.Ok | SB.Cancel, None),
    ("question", SB.Yes | SB.No, None),
    ("question", SB.Yes | SB.No, SB.No),
    ("information", SB.Save | SB.Discard | SB.Cancel, SB.Save),
]


def _answers(buttons):
    present = [b for b in (SB.Ok, SB.Save, SB.Yes, SB.No, SB.Discard,
                           SB.Cancel) if buttons is None and b == SB.Ok
               or buttons is not None and (buttons & b)]
    return ["escape", "return"] + present


@pytest.mark.parametrize("static,buttons,default", CASES)
def test_the_instance_answers_as_the_static_does(_app, static, buttons, default):
    from ui.widgets import message_box
    for how in _answers(buttons):
        args = [] if buttons is None else [buttons]
        if default is not None:
            args.append(default)
        seen_static, seen_ours = [], []
        _answer(how, seen_static)
        got_static = getattr(QMessageBox, static)(
            None, "Printer Offline", "It cannot be reached.", *args)
        _answer(how, seen_ours)
        kw = {}
        if buttons is not None:
            kw["buttons"] = buttons
        if default is not None:
            kw["default"] = default
        got_ours = message_box(ICONS[static], None, "Printer Offline",
                               "It cannot be reached.", **kw)
        assert got_ours == got_static, (static, how, got_static, got_ours)
        assert seen_ours == seen_static, (static, how)


def test_no_static_message_box_call_is_left_in_the_app():
    """The four statics run their own box, which never meets the helper."""
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    left = []
    for path in [*(root / "ui").rglob("*.py"), *(root / "core").rglob("*.py"),
                 *(root / "workflow").rglob("*.py"), root / "main.py"]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("critical", "warning",
                                           "information", "question")
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in ("QMessageBox", "_QMB")):
                left.append(f"{path.relative_to(root)}:{node.lineno}")
    assert not left, ("a static QMessageBox call bypasses "
                      "keep_message_box_inside_the_work_area; use "
                      "ui.widgets.message_box: " + ", ".join(left))
