"""The app never asks for Qt's WaitCursor.

Measured 2026-11-11 on macOS 27.2 with PyQt6 / Qt 6.11.0: a process that calls
``QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)`` is killed on the
spot (exit 133, SIGTRAP, nothing on stderr), also when the QApplication was
built the way the app builds it (``scripts/capture_screens.build_app``: the
app style and the pinned "C" numeric locale). ``BusyCursor`` did not abort in
three runs of the same probe. Four places in the shipped app used WaitCursor
(the main window's ``_work``, two in Create Chart, one in Print), so the app
could die whenever it showed that pointer on that macOS.

The fix is to use BusyCursor everywhere. This test keeps WaitCursor out of the
shipped code; it reads the source, because the abort itself cannot be tested
under the offscreen platform the suite runs on.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIPPED = ("main.py", "core", "ui", "workflow", "data")


def _python_files():
    for name in SHIPPED:
        path = ROOT / name
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from sorted(path.rglob("*.py"))


def test_no_shipped_file_names_the_wait_cursor():
    offenders = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if "WaitCursor" in line:
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not offenders, (
        "Qt's WaitCursor aborts the process on macOS 27.2 (SIGTRAP). "
        "Use Qt.CursorShape.BusyCursor instead:\n" + "\n".join(offenders)
    )


def test_the_four_former_places_show_the_busy_cursor():
    expected = {
        "ui/main_window.py": 1,
        "ui/tabs/tab_chart.py": 2,
        "ui/tabs/tab_print.py": 1,
    }
    needle = "QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)"
    for name, at_least in expected.items():
        text = (ROOT / name).read_text(encoding="utf-8")
        assert text.count(needle) >= at_least, name
