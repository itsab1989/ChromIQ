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


def test_the_rule_holds_no_reference_to_what_it_watches(qapp):
    from core import gc_guard
    from PyQt6.QtWidgets import QDialog
    dlg = QDialog()
    dlg.show()
    gc_guard._COLLECTOR.a_dialog_closed()
    ref = weakref.ref(dlg)
    dlg.close()
    dlg.deleteLater()
    del dlg
    _pump(qapp, 0.3)
    gc.collect()
    assert ref() is None
