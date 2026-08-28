"""Basti, 2026-08-28, on the Delete window: "it was very high in relation to
its width."

A QMessageBox sizes itself from its buttons, so a body of several paragraphs is
wrapped into a tall narrow column — 420 px wide and 751 tall, measured. The
Delete window was widened when he said so, and the release-readiness pass then
found the Duplicate window at 420x567: the same shape, in the window next to it,
because the fix had been applied where the complaint was rather than to the
class of problem.

This holds every message box in the target bar to it, so the next long window
cannot arrive narrow.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path


def _message_boxes_without_a_measure(src: str) -> list:
    """Every `box.exec()` in the file with no `widen_message_box` before it."""
    lines = src.split("\n")
    bad = []
    for i, ln in enumerate(lines):
        if ln.strip() != "box.exec()":
            continue
        window = "\n".join(lines[max(0, i - 16):i])
        if "widen_message_box" not in window:
            bad.append(i + 1)          # 1-indexed, as an editor shows it
    return bad


def test_every_window_in_the_target_bar_has_a_measure_to_wrap_at():
    src = Path("ui/measurement_target_bar.py").read_text(encoding="utf-8")
    bad = _message_boxes_without_a_measure(src)
    assert not bad, (
        "these windows will wrap into a tall narrow column: "
        f"ui/measurement_target_bar.py lines {bad}")


def test_the_check_can_actually_fail():
    """A sweep that cannot see the fault is worth nothing — prove it can."""
    fake = "\n".join([
        "        box = QMessageBox(self)",
        '        box.setText("a very long body")',
        "        box.exec()",
    ])
    assert _message_boxes_without_a_measure(fake) == [3]


def test_the_widener_is_a_minimum_not_a_fixed_width():
    """A box whose buttons are wider than the measure must be left alone."""
    from ui.widgets import widen_message_box
    src = inspect.getsource(widen_message_box)
    assert "QSpacerItem" in src
    assert "Policy.Minimum" in src, \
        "a fixed width would clip a window whose buttons need more"
    # …and it must never raise: a window has to open even if this cannot run.
    tree = ast.parse(src)
    assert any(isinstance(n, ast.Try) for n in ast.walk(tree))
