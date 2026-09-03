"""The gate must draw with the style the user gets, not the platform's default.

WHY THIS FILE EXISTS
--------------------
`main.py` calls ``app.setStyle(WinButtonLayoutStyle("Fusion"))`` before it
builds a single window, on every platform. The suite never runs `main()`, so
until 2026-09-03 it painted through whatever the platform plugin handed it:

  * `offscreen` (the documented way to run the gate) -> Fusion, by luck
  * `cocoa`                                          -> QMacStyle
  * **Windows**                                      -> QWindows11Style

Every size, rect and pixel this suite asserts on comes out of the style, so a
gate on the wrong style can neither catch a real styling fault nor be trusted
about one it reports.

On 2026-09-03, on the owner's Windows 11 ARM64 VM, a `--runslow` worker died
with `Windows fatal exception: access violation` inside a `QStyle::drawControl`
call from `WrappingCheckBox.paintEvent` and took the whole session with it —
while the same widgets rendered correctly in the running app all evening. That
is a **lead** for this file's existence, not a proof of it: neither the report
nor either gate log records whether `QT_QPA_PLATFORM=offscreen` was set for
those runs, and if it was, that gate was already on Fusion and the style is
innocent. The reason to pin the style does not depend on the answer.

WHAT THIS PINS, AND WHAT IT DOES NOT
------------------------------------
It pins that the painting style is Fusion, the base the app builds on. It does
NOT pin the `WinButtonLayoutStyle` proxy itself: that overrides only
`SH_DialogButtonLayout` and draws nothing, and putting a Python `styleHint` in
front of ten thousand tests cost 27 s of gate when measured. See the docstring
on `_one_qapplication_per_worker` in `tests/conftest.py` for the numbers.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_the_running_suite_is_on_fusion(qapp):
    """Whatever platform this run is on."""
    name = qapp.style().objectName().lower()
    assert name == "fusion", (
        f"this run is painting through the {name!r} style. The app ships "
        f"Fusion (main.py: app.setStyle(WinButtonLayoutStyle(\"Fusion\"))), so "
        f"every geometry this suite measures is being measured against "
        f"something the user never sees — and on Windows that style is "
        f"QWindows11Style, which is where a gate worker died on 2026-09-03. "
        f"See _one_qapplication_per_worker in tests/conftest.py")


def test_the_app_still_builds_its_style_on_fusion():
    """The assertion above is only worth anything while main.py agrees. If the
    app moves to another base, this test says so instead of quietly drifting."""
    import inspect
    import pathlib

    main_py = (pathlib.Path(__file__).resolve().parent.parent / "main.py")
    src = main_py.read_text(encoding="utf-8")
    assert 'WinButtonLayoutStyle("Fusion")' in src, (
        "main.py no longer sets WinButtonLayoutStyle(\"Fusion\"). Whatever it "
        "sets now is what tests/conftest.py must pin, or the gate goes back to "
        "measuring a style nobody runs")

    from ui.styles import WinButtonLayoutStyle
    overridden = [n for n, _ in inspect.getmembers(
        WinButtonLayoutStyle, inspect.isfunction)
        if n in vars(WinButtonLayoutStyle)]
    assert overridden == ["styleHint"], (
        f"WinButtonLayoutStyle now overrides {overridden}, not just styleHint. "
        f"It is no longer a draw-nothing proxy, so pinning the suite to plain "
        f"Fusion no longer reproduces what the app draws")
