"""A proposed text is shown in the app; "proposed" is never a switch.

Knut, #182 6166519230 (2026-10-14): *"You keep hiding changed messages in new
releases. This is not the right way ... You must always release the suggested
text. We can approve the text after as usual, and if it is accepted no new beta
is required for the sake of the text."*

Until 4.3.5 beta 4 the rule was the opposite, and it was carried out in code:
windows, cards, help paragraphs and status lines asked ``msg.approved`` (or a
flag such as ``PRINT_NOTES_APPROVED``) and showed the old text, or nothing, or
a line in the log, until the approval came. 4.3.5 beta 5 switched every such
gate live. This file keeps it that way:

* nothing in ``core/``, ``ui/``, ``workflow/`` or ``main.py`` reads
  ``.approved`` except the catalogue itself, which keeps the review state;
* no ``*_APPROVED`` switch and no ``unapproved=`` override comes back;
* the messages that used to wait in the log now reach the user in a window.
"""
from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = ("core", "ui", "workflow")
CATALOGUE = ROOT / "workflow" / "measurement_messages.py"


def _sources():
    yield ROOT / "main.py"
    for entry in SCAN:
        for path in sorted((ROOT / entry).rglob("*.py")):
            if "__pycache__" in path.parts or path == CATALOGUE:
                continue
            yield path


def _approval_reads(src: str) -> "list[int]":
    """Line numbers where code reads an ``approved`` attribute or a name that
    ends in ``_APPROVED`` (a switch), or passes ``unapproved=``."""
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Attribute) and node.attr == "approved":
            out.append(node.lineno)
        elif isinstance(node, ast.Name) and node.id.endswith("_APPROVED"):
            out.append(node.lineno)
        elif isinstance(node, ast.keyword) and node.arg == "unapproved":
            out.append(node.value.lineno)
        elif isinstance(node, ast.arg) and node.arg == "unapproved":
            out.append(node.lineno)
    return out


def test_the_probe_finds_the_gates_it_is_looking_for():
    """The mutation has to land: the shapes the gates had before beta 5."""
    for gate in ("if not M.M_CAL_DONE_STEPS.approved:\n    pass\n",
                 "x = a if MM.M_X.approved else b\n",
                 "PRINT_NOTES_APPROVED = True\n",
                 "f(c, unapproved=True)\n",
                 "def f(crowd, *, unapproved=False):\n    pass\n"):
        assert _approval_reads(gate), gate
    assert not _approval_reads("approved_by = 'Knut'\nx = m.title\n")


def test_no_code_outside_the_catalogue_asks_whether_a_text_is_approved():
    found = []
    for path in _sources():
        src = path.read_text(encoding="utf-8")
        for line in _approval_reads(src):
            found.append(f"{path.relative_to(ROOT)}:{line}: "
                         f"{src.splitlines()[line - 1].strip()}")
    assert not found, (
        "a text must not wait for its approval to be shown (Knut, #182 "
        "6166519230); these lines gate on it:\n  " + "\n  ".join(found))


def test_the_messages_that_waited_in_the_log_now_have_a_window():
    """M-ENGINE-FELL-BACK and M-ALL-STRIPS-PATCHES-LEFT spoke through the log
    only, "until approved"; since beta 5 each has its window."""
    from ui.tabs import tab_measure
    T = tab_measure.TabMeasure
    src = inspect.getsource(T._on_engine_fell_back)
    assert "_show_engine_fell_back" in src
    src = inspect.getsource(T._show_engine_fell_back)
    assert "M_ENGINE_FELL_BACK.render" in src and "QMessageBox" in src
    src = inspect.getsource(T._on_all_stripes_done)
    assert "_show_patches_left" in src
    src = inspect.getsource(T._show_patches_left)
    assert "M_ALL_STRIPS_PATCHES_LEFT.render" in src
    assert "Re-read Individual Strips" in src and "_on_stop" in src


def test_the_rule_is_written_where_it_is_read():
    spec = (ROOT / "docs" / "design" /
            "unified_measurement_management.md").read_text(encoding="utf-8")
    assert "A PROPOSED MESSAGE IS SHOWN IN THE APP" in spec
    assert "6166519230" in spec
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "is not\nwritten into a tab until it is approved" not in claude
    assert re.search(r"You must always release the suggested\s+(> )?text", claude)
