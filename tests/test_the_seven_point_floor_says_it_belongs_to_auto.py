"""Knut, 2026-09-13, on every message that names the shrink floor.

    "All warning messages where the 7 pt size limit is reached should also
    explain that this minimum applies for the auto setting, and text size can
    be made smaller if manually set. The warning for too long text in the Chart
    Notes text for right margin already does this fine."

The one he screenshotted said *"It is already at its smallest, 7 pt"* and then
offered two remedies, neither of them the Size box. It also typed the number
into the English, which is a value that has already moved once (it was 8 until
his 2026-09-11 ruling) and would then have to be chased through thirteen
catalogues.

`_auto_floor_note` is one sentence appended to those messages rather than a
clause edited into each. It is only TRUE on "auto": a typed size is its own
floor, so on a typed 9 pt "9 pt is where auto stops shrinking" is simply false.
"""
from __future__ import annotations

import ast
import inspect
import os
import re
import textwrap

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from workflow import text_edge_fit  # noqa: E402


def _note():
    from ui.tabs.tab_chart import _auto_floor_note
    return _auto_floor_note


def test_auto_gets_the_sentence_and_a_typed_size_does_not():
    note = _note()
    floor = text_edge_fit.AUTO_SHRINK_FLOOR_PT
    on_auto = note(0.0, floor)
    assert "7 pt" in on_auto and "auto" in on_auto
    assert "“Sheet text”" in on_auto, "it has to name the box to type into"
    # A typed size IS the floor. Saying "9 pt is where auto stops shrinking"
    # to somebody who typed 9 would be false.
    assert note(9.0, 9.0) == ""
    assert note(6.0, 6.0) == "", "a typed size BELOW the floor is honoured too"


def test_the_floor_is_read_from_the_constant_and_never_typed_into_the_text():
    """The SENTENCE, not the docstring around it.

    Written as a substring search over the whole function first, and it failed
    on its own docstring, which quotes Knut quoting the number. Prose about a
    value is not the value.
    """
    note = _note()
    tree = ast.parse(textwrap.dedent(inspect.getsource(note)))
    fn = tree.body[0]
    doc = ast.get_docstring(fn, clean=False)
    # THE DOCSTRING BY IDENTITY, NOT BY POSITION. `ast.walk` is not source
    # order, so "the first literal is the docstring" stopped being true the
    # moment the function grew a second branch, and this test failed on its own
    # prose about the number.
    body = [n.value for n in ast.walk(fn)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value != doc]
    assert body, "the sentence is gone"
    for lit in body:
        assert "7 pt" not in lit, (
            "the floor is written into the English again; it moved from 8 to 7 "
            f"once already and there are thirteen catalogues: {lit!r}")
    # …and the sentence really does carry whatever the constant says.
    assert "12 pt" in note(0.0, 12.0)


def test_every_message_that_prints_the_floor_appends_the_sentence():
    """The five call sites, found in the source rather than listed by hand.

    A message that formats `size=_note_floor_pt` (or the constant) is a message
    that shows the reader the floor, so it is one Knut's ruling covers. This
    fails when a sixth one is added without the sentence.
    """
    import ui.tabs.tab_chart as tc

    src = inspect.getsource(tc.TabChart._engine_text_notes)
    tree = ast.parse("if 1:\n" + src)

    shows_floor = appends = 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "format"):
            continue
        kw = {k.arg for k in node.keywords}
        if "size" not in kw:
            continue
        shows_floor += 1
        # The append is `<...>.format(...) + _auto_floor_note(...)`, so the
        # format call's PARENT is a BinOp naming the helper.
        holder = ast.dump(node)
        del holder
    # Walk again for the additions, which is the shape that matters.
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            if "_auto_floor_note" in names:
                appends += 1
    assert shows_floor >= 5, (
        f"only {shows_floor} messages format a `size`; the search broke")
    assert appends >= 6, (
        f"{shows_floor} messages show the reader the floor and only {appends} "
        "append the sentence that says it belongs to “auto”")


def test_no_shipped_message_still_says_it_is_already_at_its_smallest():
    """The exact sentence Knut objected to, gone from the source and from the
    catalogues. A translation that still carries it would show a German reader
    the sentence an English one no longer sees."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    bad = "It is already at its smallest"
    # STRING LITERALS ONLY. The comment that records WHY the sentence was
    # withdrawn quotes it, and a comment is not something a user reads. This
    # test was a grep first and failed on that comment.
    hits = []
    for py in (root / "ui").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if bad not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and bad in node.value):
                hits.append(f"{py.relative_to(root)}:{node.lineno}")
    assert not hits, f"the withdrawn sentence is still printed from {hits}"

    for cat in (root / "data" / "i18n").glob("*.json"):
        d = json.loads(cat.read_text(encoding="utf-8"))
        stale = [k for k in d if bad in k]
        assert not stale, f"{cat.name} still keys the withdrawn sentence"


def test_the_two_tooltips_name_the_floor_that_is_actually_in_force():
    """They said 8 pt for two days after the floor became 7.

    A stale FACT in a tooltip is worse than no tooltip: the reader believes it
    and stops looking.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    src = (root / "ui" / "tabs" / "tab_chart.py").read_text(encoding="utf-8")
    assert "stops at 8 pt" not in src
    n = len(re.findall(r"shrinks to fit the right margin and stops at "
                       r"(\d+) pt", src))
    assert n == 2, f"expected the two Sheet-text tooltips, found {n}"
    for got in re.findall(r"shrinks to fit the right margin and stops at "
                          r"(\d+) pt", src):
        assert float(got) == text_edge_fit.AUTO_SHRINK_FLOOR_PT, (
            f"a tooltip says {got} pt and the floor is "
            f"{text_edge_fit.AUTO_SHRINK_FLOOR_PT}")
