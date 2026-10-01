"""The C number locale is pinned to "C" on macOS right after the QApplication.

macOS 27.0 aborts a process that shows a native message box while LC_NUMERIC
is a German (non-C) locale, and Qt sets that locale from the environment while
the QApplication is built (core/numeric_locale.py). The app escaped only
because its stylesheet keeps Qt off the native box; these tests keep the pin
in place and in the right order, and keep the stylesheet that is the second
line of defence.
"""
import ast
import locale
import sys
from pathlib import Path

import pytest

from core import numeric_locale

REPO = Path(__file__).resolve().parent.parent


def _call_order(path: Path, func: str) -> list[str]:
    """Names of the calls made in `func`, in source order."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == func)
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    calls.sort(key=lambda n: (n.lineno, n.col_offset))
    out = []
    for c in calls:
        f = c.func
        out.append(f.id if isinstance(f, ast.Name) else
                   f.attr if isinstance(f, ast.Attribute) else "")
    return out


@pytest.mark.parametrize("path,func", [("main.py", "main"),
                                       ("scripts/capture_screens.py", "build_app")])
def test_the_pin_follows_the_qapplication(path, func):
    calls = _call_order(REPO / path, func)
    assert "pin_c_numeric_locale" in calls, f"{path}::{func} never pins LC_NUMERIC"
    assert calls.index("QApplication") < calls.index("pin_c_numeric_locale"), (
        "the pin must come AFTER QApplication(), which is what sets the locale")


def test_it_sets_c_on_macos(monkeypatch):
    seen = []
    monkeypatch.setattr(numeric_locale.sys, "platform", "darwin")
    monkeypatch.setattr(numeric_locale.locale, "setlocale",
                        lambda cat, value=None: seen.append((cat, value)) or
                        ("de_DE.UTF-8" if value is None else value))
    assert numeric_locale.pin_c_numeric_locale() is True
    assert (locale.LC_NUMERIC, "C") in seen


def test_it_does_nothing_elsewhere(monkeypatch):
    monkeypatch.setattr(numeric_locale.sys, "platform", "win32")
    called = []
    monkeypatch.setattr(numeric_locale.locale, "setlocale",
                        lambda *a: called.append(a))
    assert numeric_locale.pin_c_numeric_locale() is False
    assert called == []


def test_it_is_quiet_when_already_c(monkeypatch):
    monkeypatch.setattr(numeric_locale.sys, "platform", "darwin")
    calls = []
    def fake(cat, value=None):
        calls.append(value)
        return "C"
    monkeypatch.setattr(numeric_locale.locale, "setlocale", fake)
    assert numeric_locale.pin_c_numeric_locale() is False
    assert calls == [None]


def test_a_refused_locale_never_stops_the_app(monkeypatch):
    monkeypatch.setattr(numeric_locale.sys, "platform", "darwin")
    def boom(cat, value=None):
        if value is None:
            return "de_DE.UTF-8"
        raise locale.Error("unsupported locale setting")
    monkeypatch.setattr(numeric_locale.locale, "setlocale", boom)
    assert numeric_locale.pin_c_numeric_locale() is False


def test_every_appearance_keeps_an_app_stylesheet():
    """The second line of defence: with an app-wide stylesheet Qt never uses
    the native message box at all."""
    from ui import theme
    for mode, (qss, _palette) in theme._APPEARANCE_STYLE.items():
        assert qss.strip(), f"appearance {mode!r} sets no stylesheet"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_on_macos_it_really_changes_the_process_locale():
    saved = locale.setlocale(locale.LC_NUMERIC)
    try:
        locale.setlocale(locale.LC_NUMERIC, "de_DE.UTF-8")
    except locale.Error:
        pytest.skip("de_DE locale not installed")
    try:
        numeric_locale.pin_c_numeric_locale()
        assert locale.setlocale(locale.LC_NUMERIC) == "C"
    finally:
        locale.setlocale(locale.LC_NUMERIC, saved)
