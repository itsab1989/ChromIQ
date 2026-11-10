"""B8-1400: a closed top-level dialog is collected at the next tick of the
GUI thread's collector, all generations.

Challenge 9 of beta 44 (`challenge-9/gc-soak/`): after B8-1392 moved every
collection onto the GUI thread's timer with CPython's own thresholds, a
closed Preferences window left in a reference cycle (about 1,170 widgets)
waited for a rare generation-2 collection: 9,927 live widgets after 15
cycles against about 3,100 with automatic collection. The timer now notices
that a dialog it saw on screen is gone and collects everything, still from
the timer, so still never inside Qt's delivery of an event (B8-1392).

Mutations (each run red): M1400-a the full collection on a closed dialog
removed; M1400-b a hidden dialog still counted as on screen; M1400-c every
tick collects.
"""
from __future__ import annotations

import gc
import os
import time
import weakref

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from core.gc_guard import install_gui_thread_collector
    install_gui_thread_collector(app)
    return app


@pytest.fixture
def no_due_collection():
    """CPython's thresholds out of reach, so only the dialog rule can collect
    generation 2 during the test."""
    old = gc.get_threshold()
    gc.collect()
    gc.set_threshold(10 ** 8, 10 ** 8, 10 ** 8)
    try:
        yield
    finally:
        gc.set_threshold(*old)


def _pump(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _cyclic_dialog():
    from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout
    dlg = QDialog()
    lay = QVBoxLayout(dlg)
    for i in range(30):
        lay.addWidget(QLabel(f"row {i}", dlg))
    dlg.me = dlg                    # the reference cycle
    return dlg


def test_a_closed_dialog_in_a_cycle_is_collected_at_the_next_tick(
        qapp, no_due_collection):
    from core import gc_guard
    assert gc_guard.installed()
    dlg = _cyclic_dialog()
    dlg.show()
    _pump(qapp, 3 * gc_guard.INTERVAL_MS / 1000)
    ref = weakref.ref(dlg)
    dlg.close()
    del dlg
    assert ref() is not None, "the cycle should hold it until a collection"
    _pump(qapp, 3 * gc_guard.INTERVAL_MS / 1000)
    assert ref() is None, "the closed dialog is still alive after the ticks"


def test_nothing_is_collected_while_no_dialog_closes(qapp, no_due_collection):
    from core import gc_guard
    gc_guard._COLLECTOR.a_dialog_closed()          # settle the baseline
    seen = []

    def cb(phase, info):
        if phase == "stop":
            seen.append(info.get("generation"))
    gc.callbacks.append(cb)
    try:
        _pump(qapp, 5 * gc_guard.INTERVAL_MS / 1000)
    finally:
        gc.callbacks.remove(cb)
    assert 2 not in seen, seen


def _the_collector_holds(obj) -> list:
    """Whatever of the collector's own state refers to *obj*."""
    from core import gc_guard
    own = [gc_guard._COLLECTOR, vars(gc_guard._COLLECTOR),
           *vars(gc_guard._COLLECTOR).values()]
    return [r for r in gc.get_referrers(obj) if any(r is o for o in own)]


def _close_a_watched_dialog_and_wait(qapp):
    """Show a dialog, let the rule see it, close it, and wait for it to go.
    Returns ``(weakref, what the collector held right after the close)``.

    WHY THIS WAITS FOR THE EVENT LOOP AND NOT FOR A SPAN OF TIME. The cause
    of this test's reds in a full gate, found 2026-11-10: the dialog has no
    cycle, so it dies at ``del`` unless somebody else holds it, and somebody
    does whenever an earlier test file on the same worker left the app's
    ``DialogFocusFilter`` (alone or in ``CompositeAppFilter``) on the shared
    QApplication. On every dialog shown it queues ``QTimer.singleShot``
    closures that capture the window (``ui.widgets.defer_freeze_default`` at
    0 and 160 ms, ``defer_clear_button_focus`` at 0, 40 and 150 ms), and each
    holds the dialog until it has fired. This used to pump for 0.3 s and
    collect once. On a loaded worker with a large heap the collector's own
    tick (it sees the dialog close and runs a full ``gc.collect()``) outlasts
    that 0.3 s inside one ``processEvents`` call, Qt does not fire a timer
    that came due during the pass, the pump ends, and the 160 ms closure is
    still pending: red, with nothing wrong, and green alone, where no test
    has installed the filter. Reproduced 14 times in 20 with the filter and
    a 0.25 s collection, never without.

    So: the rule's own state is looked at directly, at once, and then the
    event loop is run until the queued closures have fired and let go. A
    real reference never goes, and 5 s is thirty times the longest timer."""
    from core import gc_guard
    from PyQt6.QtCore import QCoreApplication, QEvent
    from PyQt6.QtWidgets import QDialog
    dlg = QDialog()
    dlg.show()
    gc_guard._COLLECTOR.a_dialog_closed()
    ref = weakref.ref(dlg)
    dlg.close()
    dlg.deleteLater()
    held = _the_collector_holds(dlg)
    del dlg
    end = time.monotonic() + 5.0
    while True:
        _pump(qapp, 0.1)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()
        if ref() is None or time.monotonic() > end:
            break
    return ref, held


def test_the_rule_holds_no_reference_to_what_it_watches(qapp):
    ref, held = _close_a_watched_dialog_and_wait(qapp)
    assert held == [], "the collector itself refers to the dialog"
    assert ref() is None


def test_it_holds_none_behind_the_focus_filter_and_a_slow_collection(
        qapp, monkeypatch):
    """The case that was red in the gate, made on purpose: the app's focus
    filter on the application (its timers hold every shown dialog for
    160 ms) and a collector tick whose full collection takes longer than the
    old 0.3 s wait had left."""
    import types

    from core import gc_guard
    from ui.widgets import DialogFocusFilter
    slow = []

    def collect(*args):
        if not args:                    # the tick's full collection
            slow.append(1)
            time.sleep(0.25)
        return gc.collect(*args)

    names = {k: getattr(gc, k) for k in dir(gc) if not k.startswith("__")}
    monkeypatch.setattr(gc_guard, "gc",
                        types.SimpleNamespace(**{**names, "collect": collect}))
    flt = DialogFocusFilter(qapp)
    qapp.installEventFilter(flt)
    try:
        ref, held = _close_a_watched_dialog_and_wait(qapp)
    finally:
        qapp.removeEventFilter(flt)
        flt.setParent(None)
        flt.deleteLater()
    assert slow, "the tick never ran its full collection on the closed dialog"
    assert held == [], "the collector itself refers to the dialog"
    assert ref() is None
