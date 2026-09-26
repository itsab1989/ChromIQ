"""B8-1262 (beta 44 challenge F6): a ``preset_layout.request`` from a thread
other than the GUI thread left automatic garbage collection OFF after the
background thread had ended, until something called ``pending()``.

B8-1191 holds collection off for the background thread's whole life and lets
only another thread give it back: the presets window's timer (started only
for a caller ON the GUI thread), ``pending()`` and the suite's teardown.
Measured on screen by the challenge round: 6 s and 12 s after such a request
the thread was gone and collection still off; one ``pending()`` gave it back.

Now the ending thread asks another thread to give it back (never itself):
the GUI thread through a queued call when there is a Qt application, else a
short helper thread that waits for it to end.

These tests call neither ``pending()`` nor ``release_gc_if_idle`` while they
wait; they only let the GUI thread's event loop run, as the app's does.

MUTATION (red here): drop ``_ask_another_thread_to_give_back(me)`` from the
end of ``_work``: both tests time out with collection off.
"""
from __future__ import annotations

import gc
import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from workflow import preset_layout as PL                        # noqa: E402

THREAD = "chromiq-preset-layout"


@pytest.fixture()
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _settled(monkeypatch):
    PL._HOLD_UNTIL = 0.0
    assert PL.settle(30)
    assert gc.isenabled()
    monkeypatch.setattr(PL, "_IDLE_EXIT_S", 0.2)
    yield
    PL.settle(30)


def _request_from_another_thread(key) -> None:
    done = threading.Event()

    def caller():
        PL.request(key, lambda: [object() for _ in range(2000)])
        done.set()
    t = threading.Thread(target=caller, name="some-other-caller")
    t.start()
    t.join(5)
    assert done.is_set()


def _layout_threads():
    return [t for t in threading.enumerate() if t.name == THREAD]


def test_collection_comes_back_on_the_gui_thread_when_the_thread_ends(qapp):
    seen: list = []

    def cb(phase, _info):
        if phase == "start":
            seen.append(threading.current_thread().name)
    gc.callbacks.append(cb)
    try:
        _request_from_another_thread(("b8-1262", "qt"))
        assert PL.gc_held() and not gc.isenabled()
        end = time.monotonic() + 10.0
        while time.monotonic() < end and not gc.isenabled():
            qapp.processEvents()       # the app's event loop, nothing else
            for _ in range(200):
                a: list = []
                a.append(a)
            time.sleep(0.01)
        assert not _layout_threads()
        assert gc.isenabled() and not PL.gc_held(), (
            "the background thread ended and collection stayed off")
    finally:
        gc.callbacks.remove(cb)
    assert THREAD not in seen, "a collection ran on the background thread"


def test_without_a_qt_application_a_helper_gives_it_back(monkeypatch):
    """The module is used by scripts too; with no Qt application to post to,
    a short helper thread waits for the background thread to end."""
    def no_gui(*_a):
        raise RuntimeError("no GUI thread to post to")
    monkeypatch.setattr(PL, "_make_gui_releaser", no_gui)
    monkeypatch.setattr(PL, "_RELEASER", None)
    _request_from_another_thread(("b8-1262", "plain"))
    end = time.monotonic() + 10.0
    while time.monotonic() < end and not gc.isenabled():
        time.sleep(0.02)
    assert not _layout_threads()
    assert gc.isenabled() and not PL.gc_held()
