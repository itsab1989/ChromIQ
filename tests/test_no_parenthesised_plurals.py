"""House rule (Basti, standing): a message that carries a count gets real
singular and plural forms — never "page(s)".

Knut approved a pass over the user-facing text on #130 (2026-08-01: "Sure, do
that"). This is the part of that pass which can be kept honest by a test: the
rest is judgement, but "(s)" is mechanical, and it had crept back into eleven
strings across the chart, print, scan and report dialogs.

It matters beyond tidiness. "(s)" is untranslatable — plenty of languages do
not form a plural by adding a letter, and several change the noun's case after
a number — so every one of these was also a dead end for the translators.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: "file(s)", "page(s)" — a word immediately followed by a parenthesised s.
#: `(es)` AS WELL AS `(s)`. The original pattern was one character short, and
#: `paper-white fill-up patch(es)` sat inside the directory this test already
#: scanned, in an `appendPlainText` call it already listed, through a green gate.
PARENS_PLURAL = re.compile(r"\b[A-Za-z]+\((?:s|es)\)")

#: Directories holding text a user can read.
#:
#: `workflow/` IS ONE OF THEM, WHICH THIS TEST USED TO DENY. Its own docstring
#: excludes Python `log.*` calls because "those are for us, not for the user" —
#: but `on_line(...)` and `progress_cb(...)` are not `log.info`: they write the
#: Create Chart log the person is watching while their chart is built. Three
#: strings lived there and read "7 page(s)", "3 patch(es)" and "9 strip(s)" on
#: screen, off a real build, while this test passed.
UI_DIRS = ("ui", "workflow")

#: Calls whose string arguments end up in front of a user. ``tr`` is the
#: obvious one; the setters matter because the counted phrases that prompted
#: this pass were f-strings appended straight to the in-app log, which a
#: tr()-only scan walks past. Python ``log.*`` calls and docstrings are
#: deliberately NOT included — those are for us, not for the user.
USER_FACING_CALLS = {
    "tr", "appendPlainText", "setToolTip", "setText", "setPlaceholderText",
    "setWindowTitle", "setStatusTip", "addButton", "setLabelText", "setTitle",
    # The build log. Not logging: these are the lines a person reads while
    # ChromIQ makes their chart, and they are the ones this test missed.
    "on_line", "progress_cb",
}


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def _literals(node):
    """Strings reachable from an argument: plain, concatenated, or f-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.lineno, node.value
    elif isinstance(node, ast.BinOp):
        yield from _literals(node.left)
        yield from _literals(node.right)
    elif isinstance(node, ast.JoinedStr):
        for v in node.values:
            yield from _literals(v)
    elif isinstance(node, ast.FormattedValue):
        yield from _literals(node.value)
    elif isinstance(node, ast.Call):
        # e.g. tr("…").format(…) — the text is inside the inner call.
        for a in node.args:
            yield from _literals(a)


def _user_facing_strings():
    """Every string that reaches the user, with its file and line."""
    for d in UI_DIRS:
        for path in sorted((ROOT / d).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:                     # pragma: no cover
                continue
            rel = path.relative_to(ROOT)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if _call_name(node) not in USER_FACING_CALLS:
                    continue
                for arg in node.args:
                    for line, s in _literals(arg):
                        yield rel, line, s


def test_no_parenthesised_plurals_anywhere_in_the_ui():
    offenders = [
        f"{rel}:{line}  {PARENS_PLURAL.search(s).group(0)!r}  in {s[:70]!r}"
        for rel, line, s in _user_facing_strings()
        if PARENS_PLURAL.search(s)
    ]
    assert not offenders, (
        "Use real singular/plural forms instead of “(s)”. "
        "core.i18n.count_phrase(n, tr('1 page'), tr('{n} pages')) does this:\n  "
        + "\n  ".join(offenders))


# ---- the helper the rule points people at --------------------------------
@pytest.mark.parametrize("n,expected", [
    (0, "0 pages"),          # zero is plural in English
    (1, "1 page"),
    (2, "2 pages"),
    (57, "57 pages"),
])
def test_count_phrase_picks_the_right_form(n, expected):
    from core.i18n import count_phrase
    assert count_phrase(n, "1 page", "{n} pages") == expected


def test_count_phrase_fills_a_placeholder_in_the_singular_too():
    """Some languages want the numeral in the singular as well, so a singular
    that carries {n} must be formatted rather than returned raw."""
    from core.i18n import count_phrase
    assert count_phrase(1, "{n} page", "{n} pages") == "1 page"


def test_count_phrase_leaves_a_plain_singular_alone():
    """A singular with no placeholder must not go through str.format, which
    would choke on any literal brace in the text."""
    from core.i18n import count_phrase
    assert count_phrase(1, "one single page", "{n} pages") == "one single page"
