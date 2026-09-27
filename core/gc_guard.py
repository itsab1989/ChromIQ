"""The garbage collector runs on the GUI thread, between events, and nowhere
else (B8-1392).

**A COLLECTION INSIDE QT'S EVENT DELIVERY DELETES THE RECEIVER UNDER QT.**
Python collects on whichever allocation crosses the threshold. Every Python
event filter, every Python ``event()``/``paintEvent`` override and the app's
own :class:`ui.widgets.CompositeAppFilter` allocates (sip wraps the object and
the event on every call), so a collection can start in the middle of
``QCoreApplication::notify``. If what it finds is a widget tree that has just
become garbage (a closed dialog in a reference cycle, a Create Chart tab a
test let go of) and the event being delivered is FOR one of that tree's
widgets, the collection deletes the tree, the receiver with it, and Qt goes on
using the receiver when the filter returns.

Measured, beta 44 (``~/Desktop/ChromIQ-beta44-proof/segfault/``): the everyday
tier lost a worker in 3 of 9 runs, always ``SIGSEGV`` in
``QCoreApplicationPrivate::sendThroughObjectEventFilters`` from pytest-qt's
``processEvents``, twice from a timer and once from a queued call. A core dump
of the third shows the fault on the instruction that re-reads the RECEIVER's
``d_ptr`` right after a filter call returned, with the receiver's memory
already on malloc's free list. Reproduced
(``tests/test_b8_1392_no_collection_inside_event_delivery.py``): a garbage widget
with ANY Python event filter on it, a posted event and the next allocation
collecting (``gc.set_threshold(1)``) crashes on the first round, with the same
frame; with no Python filter it survives 200.

The same collector also ran on non-GUI threads (the tiff encoder's pool,
``xicclu``'s pool, a Qt thread calling into Python: 3 per run, measured by a
``gc.callbacks`` probe), which B8-1161 and B8-1191 fought one thread at a time
for ``workflow.preset_layout``.

So automatic collection is switched off, and a timer on the GUI thread
collects instead, with CPython's own thresholds, when Qt calls it from the top
of its event loop: then the only object Qt is delivering to is that timer.
Everything that is garbage is still collected, a few hundred milliseconds
later at most, and plain reference counting frees everything else at once as
before.

**A CLOSED DIALOG IS COLLECTED AT THE NEXT TICK, ALL GENERATIONS (B8-1400).**
CPython's thresholds reach a generation-2 collection rarely, and a closed
window left in a reference cycle waits for exactly that: challenge 9 of beta
44 counted 9,927 live widgets after 15 Preferences cycles (about 1,170 per
closed window), against about 3,100 with automatic collection. So the tick
also looks at which top-level dialogs are on screen, and when one it saw
last time is gone it runs ``gc.collect()``: queued to the timer, never inside
the close itself.

One limit, stated rather than assumed away: inside a NESTED event loop (a
modal ``exec()``, a ``processEvents()`` call) the timer also fires, and there
the object Qt is delivering to is the timer, but an outer delivery further
down the stack may still be under way. Not reproduced; the tick is the
narrowest place there is.
"""
from __future__ import annotations

import gc
import logging
import threading

log = logging.getLogger(__name__)

#: How often the GUI thread looks at the collector's counts. CPython's own
#: first threshold (2000 allocations) is crossed several times a second while
#: a window is being built; 100 ms keeps garbage from piling up, and a tick
#: that finds nothing due costs one ``gc.get_count()``.
INTERVAL_MS = 100

_COLLECTOR = None


def collect_if_due() -> int:
    """Collect what CPython's automatic collector would collect now, from
    the calling thread, and return how many objects were unreachable.

    Only ever to be called where no Qt event is being delivered to anything
    that may be garbage: the collector's timer, or a test's teardown."""
    if threading.current_thread() is not threading.main_thread():
        return 0
    c0, c1, c2 = gc.get_count()
    t0, t1, t2 = gc.get_threshold()
    if t0 <= 0 or c0 < t0:
        return 0
    gen = 0
    if t1 > 0 and c1 >= t1:
        gen = 1
        if t2 > 0 and c2 >= t2:
            gen = 2
    return gc.collect(gen)


def _make_collector(app):
    from PyQt6.QtCore import QObject, QTimer

    class _GuiThreadCollector(QObject):
        """Parented to the application, driven by a bound method (never a
        closure: CLAUDE.md, the scroll-bar segfault)."""

        def __init__(self, parent) -> None:
            super().__init__(parent)
            self.setObjectName("chromiq_gui_thread_collector")
            self.timer = QTimer(self)
            self.timer.setInterval(INTERVAL_MS)
            self.timer.timeout.connect(self.tick)
            self.timer.start()

            #: The C++ addresses of the top-level dialogs that were on
            #: screen at the last tick (B8-1400): ints, so this rule keeps
            #: no Python reference to any dialog between ticks.
            self._open_dialogs: "set[int]" = set()

        def tick(self) -> None:
            # somebody's restore switched it back on (an import guard, a
            # test): off again, or the next allocation inside an event
            # collects there
            if gc.isenabled():
                gc.disable()
            if self.a_dialog_closed():
                # B8-1400: A CLOSED DIALOG IS COLLECTED NOW, ALL GENERATIONS.
                # A closed Preferences window left in a reference cycle is
                # some 1,170 widgets that only a generation-2 collection
                # frees, and CPython's thresholds reach one rarely: challenge
                # 9 of beta 44 counted 9,927 live widgets after 15 cycles.
                # Still from this timer, so still never inside Qt's delivery
                # of an event (B8-1392): Qt is delivering to the timer.
                gc.collect()
                return
            collect_if_due()

        def a_dialog_closed(self) -> bool:
            """Whether a top-level dialog on screen at the last tick is gone
            from the screen now (closed, hidden or deleted)."""
            try:
                from PyQt6 import sip
                from PyQt6.QtWidgets import QApplication, QDialog
                now = {sip.unwrapinstance(w)
                       for w in QApplication.topLevelWidgets()
                       if isinstance(w, QDialog) and w.isVisible()}
            except Exception:      # noqa: BLE001 — a collector never raises
                return False
            gone = bool(self._open_dialogs - now)
            self._open_dialogs = now
            return gone

    return _GuiThreadCollector(app)


def install_gui_thread_collector(app) -> None:
    """Switch automatic collection off and collect on *app*'s thread, from
    its event loop, instead. Idempotent. Call on the GUI thread, right after
    the QApplication is made and before any window is built."""
    global _COLLECTOR
    if app is None:
        return
    if _COLLECTOR is not None:
        try:
            if _COLLECTOR.parent() is app:
                gc.disable()
                return
        except RuntimeError:        # the old application is gone
            pass
    gc.disable()
    _COLLECTOR = _make_collector(app)
    log.debug("automatic garbage collection moved to the GUI thread's "
              "event loop (B8-1392)")


def installed() -> bool:
    """Whether :func:`install_gui_thread_collector` has run for a live
    application."""
    if _COLLECTOR is None:
        return False
    try:
        _COLLECTOR.objectName()
    except RuntimeError:
        return False
    return True
