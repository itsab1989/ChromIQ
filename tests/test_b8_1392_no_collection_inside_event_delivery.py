"""B8-1392: a garbage collection may never run inside Qt's delivery of an
event; the collector runs on the GUI thread, from the event loop.

The beta 44 everyday tier lost a worker in 3 of 9 runs at abc852a2, always
SIGSEGV in ``QCoreApplicationPrivate::sendThroughObjectEventFilters`` from
pytest-qt's ``processEvents``: twice a timer, once a queued call. The core
dump of the third run shows the fault on the instruction that re-reads the
RECEIVER's ``d_ptr`` just after a filter call returned; the receiver's memory
was already on malloc's free list. A test had let go of a Create Chart tab
(garbage in a reference cycle, not yet collected), an event was delivered to
one of its widgets, a Python event filter on that widget allocated, the
allocation crossed the collector's threshold, and the collection deleted the
whole tab, receiver included, under Qt.

`core/gc_guard.py` switches automatic collection off and collects from a
timer on the GUI thread, which the app (`main()`) and the suite
(`tests/conftest.py`) both install.

MUTATION (red here): remove ``install_gui_thread_collector(app)`` from
``main()`` (the first test), or from the suite's QApplication fixture (the
second), or from the script below (the third dies with SIGSEGV exactly as the
fourth does, which is what the fourth pins).
"""
from __future__ import annotations

import ast
import gc
import os
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

#: A widget tree that is garbage, with a Python event filter on a child, and
#: events already posted to that child; ``gc.set_threshold(1)`` makes the
#: next tracked allocation collect, which with automatic collection on is the
#: filter call itself. With the collector installed nothing collects there,
#: and the trees are still deleted, later, by the timer.
_SCRIPT = textwrap.dedent("""
    import faulthandler, gc, os, sys, time
    faulthandler.enable()
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.path.insert(0, {repo!r})
    from PyQt6.QtCore import QCoreApplication, QEvent, QObject
    from PyQt6.QtWidgets import QApplication, QWidget
    app = QApplication([])
    if {guard!r}:
        from core.gc_guard import install_gui_thread_collector
        install_gui_thread_collector(app)

    class PlainFilter(QObject):
        def eventFilter(self, obj, ev):
            return False

    class Owner(QWidget):
        def __init__(self):
            super().__init__()
            self.me = self
            self.target = QWidget(self)
            self.f = PlainFilter(self)
            self.target.installEventFilter(self.f)

    base = len(app.allWidgets())
    for _ in range(60):
        o = Owner()
        for _ in range(3):
            QCoreApplication.postEvent(o.target, QEvent(QEvent.Type.User))
        del o
        old = gc.get_threshold()
        gc.set_threshold(1)
        try:
            app.processEvents()
        finally:
            gc.set_threshold(*old)
    grown = len(app.allWidgets()) - base
    junk = [[i] for i in range(3 * gc.get_threshold()[0])]
    end = time.monotonic() + 1.0
    while time.monotonic() < end:
        app.processEvents()
    left = len(app.allWidgets()) - base
    print("SURVIVED", grown, left, gc.isenabled(), flush=True)
""")


def _run(guard: bool) -> subprocess.CompletedProcess:
    # a loaded gate: the script takes about a second on an idle machine
    return subprocess.run(
        [sys.executable, "-c", _SCRIPT.format(repo=str(REPO), guard=guard)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, cwd=str(REPO))


def test_main_moves_the_collector_before_any_widget_or_filter():
    tree = ast.parse((REPO / "main.py").read_text(encoding="utf-8"))
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = {}
    for node in ast.walk(main):
        if isinstance(node, ast.Call):
            f = node.func
            name = getattr(f, "id", None) or getattr(f, "attr", None)
            if name and name not in calls:
                calls[name] = node.lineno
    assert "install_gui_thread_collector" in calls, (
        "main() no longer moves the garbage collector to the GUI thread "
        "(B8-1392): a collection inside the app filter can delete the "
        "receiver of the event being delivered")
    at = calls["install_gui_thread_collector"]
    assert calls["QApplication"] < at
    for later in ("CompositeAppFilter", "AppSettings", "MainWindow"):
        if later in calls:
            assert at < calls[later], f"the collector is moved after {later}"


def test_the_suite_collects_where_the_app_does():
    from core import gc_guard
    assert gc_guard.installed(), (
        "tests/conftest.py no longer installs the GUI thread's collector")
    assert not gc.isenabled(), "automatic collection is on in the suite"


def test_collect_if_due_never_collects_off_the_gui_thread():
    from core import gc_guard
    got = []
    old = gc.get_threshold()
    gc.set_threshold(1)
    try:
        junk = [[i] for i in range(50)]
        t = threading.Thread(target=lambda: got.append(gc_guard.collect_if_due()))
        t.start(); t.join(10)
    finally:
        gc.set_threshold(*old)
    del junk
    assert got == [0]


def test_a_garbage_tree_meets_its_events_and_is_still_collected():
    r = _run(guard=True)
    assert r.returncode == 0, (
        f"the process died ({r.returncode}) with the collector installed:\n"
        f"{r.stderr[-3000:]}")
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("SURVIVED"))
    _tag, grown, left, enabled = line.split()
    assert int(grown) > 0, "the trees were collected inside the event delivery"
    assert int(left) == 0, (
        f"{left} garbage widgets were never deleted: the collector's timer "
        "does not collect")
    assert enabled == "False"


@pytest.mark.skipif(sys.platform != "darwin", reason=(
    "macos only: whether Qt faults on the freed receiver depends on what "
    "the allocator writes into freed memory, which on macOS is always the "
    "first 16 bytes"))
def test_without_it_the_same_script_dies_in_the_event_filter_dispatch():
    """What the test above guards against, reproduced: this is the crash
    the gate saw, frame for frame."""
    r = _run(guard=False)
    assert r.returncode != 0, (
        "the unguarded script survived; if a PyQt/Qt upgrade stopped the "
        "fault, B8-1392's guard is still right but this pin needs rewording")
    assert "sendThroughObjectEventFilters" in r.stderr, r.stderr[-3000:]
