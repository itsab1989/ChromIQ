"""A one-shot timer must not hold a widget that may die first (#164).

`QTimer.singleShot(msec, lambda: btn.setText(...))` keeps NO owner. The lambda
keeps the button alive on the Python side while Qt deletes the C++ object with
its parent — so when the timer fires, `setText` dereferences freed memory:

    RuntimeError: wrapped C/C++ object of type QPushButton has been deleted

Two of these shipped. The scanner dialog's "Saved ✓" flash armed 1.4 s; the
Measure tab's status flash armed **8**. Closing either window inside that window
is a crash for the user — and in the test suite the timer fired inside whatever
was pumping events at the time, which is why the gate had one intermittent
failure that landed on a different test each run.

`QTimer.singleShot(msec, context, slot)` — the Qt overload that takes an owner —
does not exist in PyQt6. A bound method of the QObject is the fix: it dies with
the object, so a dead widget simply never gets the call.
"""
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

#: `singleShot(0, …)` is exempt: it runs on the next event-loop pass, before
#: anything can be torn down, and it is the established idiom for deferring
#: startup work.
_LONG_LAMBDA = re.compile(r"singleShot\(\s*(?!0\s*,)[^,]+,\s*lambda")


def test_no_long_one_shot_timer_captures_a_widget():
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []
    for path in (root / "ui").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for m in _LONG_LAMBDA.finditer(text):
            line_no = text[:m.start()].count("\n") + 1
            line = text.splitlines()[line_no - 1]
            # A lambda that captures nothing but a local callable is safe; the
            # dangerous shape is one touching a widget or `self`.
            tail = text[m.start():m.start() + 200]
            if "self." in tail or re.search(r"lambda:\s*\w*btn|lbl|_widget", tail):
                offenders.append(f"{path.relative_to(root)}:{line_no}: {line.strip()}")
    assert not offenders, (
        "a one-shot timer outlives the widget it touches; use a bound method "
        "of the QObject instead:\n  " + "\n  ".join(offenders))


def _timer_calls(src: str) -> list:
    """The `singleShot` CALLS in a method, with comments stripped.

    Checking the raw source for the word "lambda" catches the comment that
    explains why there is not one — a test that pins a word rather than a fact.
    """
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    return re.findall(r"singleShot\([^)]*\)", code)


@pytest.mark.parametrize("module,cls,method,slot", [
    ("ui.dialogs.scanin_dialog", "ScannerProfileDialog",
     "_save_defaults_clicked", "_restore_save_defaults_button"),
    ("ui.tabs.tab_measure", "TabMeasure", "_flash_status", "_hide_status_flash"),
])
def test_the_flashes_use_a_bound_method(qapp, module, cls, method, slot):
    """Both flashes hand the timer a bound method, which dies with the object."""
    import importlib
    import inspect

    mod = importlib.import_module(module)
    src = inspect.getsource(getattr(getattr(mod, cls), method))
    calls = _timer_calls(src)
    assert calls, f"{cls}.{method} no longer arms a timer at all"
    for call in calls:
        assert "lambda" not in call, (
            f"{cls}.{method} is back on a lambda: {call}")
    assert slot in src, f"{cls}.{method} does not call {slot}"
