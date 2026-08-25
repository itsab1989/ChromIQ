"""One QApplication for the whole worker, held for the whole run.

179 test files build their own with `QApplication.instance() or
QApplication([])` inside a MODULE-scoped fixture and drop the only strong
reference when that module ends. **Destroying a QApplication sip-deletes every
remaining QObject in the process** — Python refcounts do not move, the C++ side
is deleted underneath them, so an object another module still holds becomes a
live Python name wrapping freed memory.

`ui/widgets.py` publishes the app's AppSettings into a module global
(`_LOG_SETTINGS`) and nothing unbinds it, so the first module to tear its
QApplication down left every later one with a dangling QSettings — and the next
panel to size itself raised "wrapped C/C++ object of type QSettings has been
deleted". That is the shared state behind the gate's intermittent failures: a
different victim each run, every one passing alone, because it depends on which
file tore down first on that worker.

A behavioural cross-module test cannot be written here: `--dist loadfile` may
put the two files on different workers, so the pairing that fails is not
reproducible from inside the suite. These assert the invariant instead.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


def test_the_session_holds_the_application(_one_qapplication_per_worker):
    """The pinned instance IS the one everything else gets.

    Asked through the fixture rather than `conftest._PINNED_QAPP`: pytest loads
    conftest under its own module identity, so `import conftest` in a test finds
    a SECOND copy whose global is still None. That is a trap worth naming — the
    first version of this test read the wrong module and failed against a
    working fix.
    """
    from PyQt6.QtWidgets import QApplication

    pinned = _one_qapplication_per_worker
    assert pinned is not None, "no QApplication was pinned"
    assert pinned is QApplication.instance(), (
        "something replaced the pinned QApplication")


def test_the_pin_is_never_torn_down():
    """Tearing it down at session end would delete every QObject still alive
    during other fixtures' teardown — the very fault this prevents."""
    import inspect

    import conftest

    src = inspect.getsource(conftest._one_qapplication_per_worker)
    after_yield = src.split("yield", 1)[1]
    for destroyer in ("quit()", "shutdown", "deleteLater", "= None"):
        assert destroyer not in after_yield, (
            f"the pinned QApplication is torn down ({destroyer}) at session end")


def test_the_settings_store_survives_a_read_when_it_is_gone(qapp):
    """The other half: reading a preference must never raise, whatever happened
    to the store underneath it.

    A guard for this was added in 4.1.3-beta.13 and called a logger that this
    module does not have — a NameError on the very path meant to prevent a
    crash, shipped because the test checked the guard's source text and never
    ran it. This runs it.
    """
    import ui.widgets as widgets

    class _Dead:
        def get(self, *a, **k):
            raise RuntimeError(
                "wrapped C/C++ object of type QSettings has been deleted")

    saved = widgets._LOG_SETTINGS
    try:
        widgets._LOG_SETTINGS = _Dead()
        assert widgets.log_visible_lines() == widgets.LOG_VISIBLE_LINES
    finally:
        widgets._LOG_SETTINGS = saved


def test_sizing_a_panel_never_raises_either(qapp):
    """`fit_log_height` promises "never raises" in its docstring, and read the
    settings store OUTSIDE its own try."""
    from PyQt6.QtWidgets import QPlainTextEdit

    import ui.widgets as widgets

    class _Dead:
        def get(self, *a, **k):
            raise RuntimeError("wrapped C/C++ object has been deleted")

    saved = widgets._LOG_SETTINGS
    try:
        widgets._LOG_SETTINGS = _Dead()
        widgets.fit_log_height(QPlainTextEdit())      # must not raise
    finally:
        widgets._LOG_SETTINGS = saved
