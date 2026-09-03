"""The title bar says it once, in one language.

Finding F of the first Windows verification (2026-09-03). On a German Windows
every window read:

    ChromIQ — Druckerprofilierung - ChromIQ — Printer Profiling

and the Welcome dialog:

    Willkommen bei ChromIQ - ChromIQ — Printer Profiling

Qt appends the application's display name to a window title unless the title
already ends with it — `QPlatformWindow::formatWindowTitle`, joined with the
platform's separator, which is " - " on Windows and " — " on macOS. The main
window's own title IS that sentence, so the two would have matched and Qt would
have appended nothing. They did not match, for one reason: `main.py` set the
display name as a bare English literal, seven lines before `set_language` had
even been called.

So this file guards both halves — the string goes through `tr`, and the call
happens after the catalogue is loaded. Neither alone is enough: `tr` before
`set_language` returns English, silently.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parent.parent
TITLE = "ChromIQ — Printer Profiling"


def _main_source() -> str:
    return (REPO / "main.py").read_text(encoding="utf-8")


def _line_of(pattern: str) -> int:
    """The 1-based line in main.py matching *pattern*, or 0."""
    for i, line in enumerate(_main_source().splitlines(), 1):
        if re.search(pattern, line):
            return i
    return 0


def test_the_display_name_goes_through_the_catalogue():
    """A bare literal here can never be translated, and Qt then appends it to
    every window title in the app."""
    src = _main_source()
    calls = [n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr == "setApplicationDisplayName"]
    assert len(calls) == 1, "expected exactly one setApplicationDisplayName"
    arg = calls[0].args[0]
    assert isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "tr", (
        "setApplicationDisplayName must be handed tr(...), not a literal — "
        "otherwise the display name is English in every language and Qt "
        "appends it to a translated window title")
    assert isinstance(arg.args[0], ast.Constant)
    assert arg.args[0].value == TITLE


def test_it_is_set_after_the_language_is_chosen():
    """`tr` before `set_language` is the English catalogue, and says nothing
    about it. The order is the other half of the fix."""
    lang = _line_of(r"^\s*set_language\(settings\.get\(")
    disp = _line_of(r"setApplicationDisplayName\(")
    assert lang, "set_language(settings.get(...)) not found in main.py"
    assert disp, "setApplicationDisplayName not found in main.py"
    assert lang < disp, (
        f"setApplicationDisplayName is at line {disp} and set_language at "
        f"{lang} — translated before the catalogue is loaded, so it is English")


@pytest.mark.parametrize("code", ["de", "fr", "ru", "ja", "zh_CN"])
def test_qt_appends_nothing_to_the_main_window_title(code):
    """The condition Qt actually tests.

    `formatWindowTitle` appends the display name only when the title does not
    already end with it. The main window's title and the display name are the
    same key, so in a language where both are translated they match and nothing
    is appended — which is what the VM did not see.

    Checked against the catalogues rather than by opening a window, because the
    display name is process-wide and set once at start-up: a test that changed
    it would change it for every other test in the worker.
    """
    from core.i18n import set_language, tr
    try:
        set_language(code)
        display_name = tr(TITLE)
        window_title = tr(TITLE)          # ui/main_window.py:170, same key
        assert display_name != TITLE, (
            f"[{code}] the catalogue does not translate {TITLE!r}, so this "
            f"test would pass for the wrong reason")
        assert window_title.endswith(display_name), (
            f"[{code}] Qt would append {display_name!r} to {window_title!r}")
    finally:
        set_language("en")


def test_the_second_window_title_is_at_least_all_one_language():
    """A dialog with its own title still gets the display name appended — that
    is Qt working as designed, and the report's complaint about it was that one
    half was German and the other English. Both halves come from the catalogue
    now, so the appended part is in the same language as the rest."""
    from core.i18n import set_language, tr
    try:
        set_language("de")
        welcome = tr("Welcome to ChromIQ")
        display_name = tr(TITLE)
        assert welcome != "Welcome to ChromIQ"
        assert display_name != TITLE
        # What the title bar will read. Neither half is English.
        composed = f"{welcome} - {display_name}"
        assert "Printer Profiling" not in composed, composed
    finally:
        set_language("en")
