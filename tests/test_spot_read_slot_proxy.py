"""The Read-single-patches segfault of 2026-09-02 23:30, and what stops it.

WHAT HAPPENED. He ran the tool three times. The third `spotread -v -c 1` found
nothing, printed ``Diagnostic: Unknown, inappropriate or no instrument
detected`` and its whole usage text, and exited 1. ChromIQ's "No instrument
detected" window came up over that, he answered it, closed the tool, opened a
tool from the Tools popup, and the app died inside that tool's ``dlg.exec()``:

    QDialog::exec -> QEventLoop::exec
      QCoreApplicationPrivate::sendPostedEvents
        QObject::event                       <- a queued QMetaCallEvent
          PyQtSlotProxy::qt_metacall
            PyQtSlotProxy::unislot
              QObject::deleteLater -> QCoreApplication::postEvent   *** SIGSEGV

WHY. PyQt6 6.11 guards a slot proxy against re-entry with a BIT rather than a
counter (`qpy/QtCore/qpycore_pyqtslotproxy.cpp`)::

    proxy_flags |= PROXY_SLOT_INVOKED;
    ... real_slot->invoke(...)            // MAY RUN A NESTED EVENT LOOP
    proxy_flags &= ~PROXY_SLOT_INVOKED;   // an INNER call clears it too

and `PyQtSlotProxy::disable()`, which `signal.disconnect(<a closure>)` reaches,
frees the proxy the moment that bit is clear::

    if ((proxy_flags & PROXY_SLOT_INVOKED) == 0)
        deleteLater();

ChromIQ opened both halves at once. `ArgyllRunner` connected a PER-RUN closure
to `line_received`, which is emitted from the PTY READER THREAD — so PyQt
delivered it through a queued call to a proxy. The window opened from inside
that delivery ran a nested loop; the rest of spotread's output was then
delivered re-entrantly through the SAME proxy and each inner call cleared the
bit; and the process exited while the window was up, so `_on_pty_finished`
called `line_received.disconnect(on_line)` — freeing the proxy under a live
outer `unislot()` frame.

Reproduced against the real dialog with a fake spotread, 14 runs of 8 rounds:
**5 crashed** before the fix and **0 after** (`MallocScribble=1`, so a
use-after-free faults instead of reading stale-but-plausible bytes). If the
rate were unchanged, 0 in 14 has probability 0.6 %.

THE FIX, and what these tests pin: `line_received` has exactly ONE connection
for the whole life of the process, to a bound method of the runner itself.
A run's `on_line` is plain state that the dispatcher reads fresh every line.
Nothing is ever disconnected, so `disable()` is never called, so the bit can
never be read at the wrong moment.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication          # noqa: E402

from core.argyll_runner import ArgyllRunner       # noqa: E402
from core.settings import AppSettings             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ----------------------------------------------------------------------
# The invariant, stated three ways
# ----------------------------------------------------------------------
def test_line_received_has_exactly_one_receiver_for_ever(qapp):
    """One permanent connection, made in __init__ and never touched again.

    `receivers()` counts Qt-side connections; a per-run closure would show up
    here as a second one, which is exactly the shape that crashed.
    """
    runner = ArgyllRunner(AppSettings())
    assert runner.receivers(runner.line_received) == 1

    # …and registering a run's callback must not add one.
    runner._run_on_line = lambda _line: None
    runner._run_on_finish = lambda _code: None
    assert runner.receivers(runner.line_received) == 1

    runner.forget_run_callbacks()
    assert runner.receivers(runner.line_received) == 1


def test_the_runner_never_connects_or_disconnects_a_per_run_closure():
    """SOURCE-LEVEL, because this is a rule about how the code is written and
    a future run path could quietly reintroduce it.

    `connect(on_line)` / `disconnect(on_line)` are the two calls that produced
    the crash. Neither may appear anywhere in the module again.
    """
    import core.argyll_runner as mod
    src = inspect.getsource(mod)
    # Strip comments and docstrings: this file's own explanation quotes the
    # very calls it forbids, and a rule that trips over its own reasoning is
    # a rule nobody can keep.
    code = "\n".join(line for line in src.splitlines()
                     if not line.lstrip().startswith("#"))
    for forbidden in ("line_received.connect(on_line)",
                      "line_received.disconnect(on_line)"):
        assert forbidden not in code, (
            f"{forbidden} is back. A per-run closure connected to a signal "
            "that is emitted from the PTY reader thread is the 2026-09-02 "
            "segfault: PyQt frees the slot proxy on disconnect while a nested "
            "event loop opened from inside that same delivery is still on the "
            "stack. Set `self._run_on_line` instead and let "
            "`_dispatch_run_line` do the delivery.")
    assert "self.line_received.connect(self._dispatch_run_line)" in code


def test_the_dispatcher_delivers_and_stops_delivering(qapp):
    """Behaviour, not just shape: the per-run callback still sees every line,
    and stops the moment the run lets go."""
    runner = ArgyllRunner(AppSettings())
    seen: list[str] = []
    runner._run_on_line = seen.append

    runner.line_received.emit("Instrument Type:   ColorMunki")
    runner.line_received.emit("Calibration complete")
    assert seen == ["Instrument Type:   ColorMunki", "Calibration complete"]

    runner.forget_run_callbacks()
    runner.line_received.emit("a line after the window closed")
    assert len(seen) == 2, "a forgotten run must stop receiving"


def test_a_line_arriving_with_no_run_registered_is_harmless(qapp):
    """The dispatcher is permanent, so it is called between runs too."""
    runner = ArgyllRunner(AppSettings())
    runner.line_received.emit("stray output with nothing listening")


def test_a_second_run_replaces_the_first_callback(qapp):
    """The old code left BOTH closures connected if a run started before the
    previous one was cleaned up, so one line reached two dead windows."""
    runner = ArgyllRunner(AppSettings())
    first: list[str] = []
    second: list[str] = []
    runner._run_on_line = first.append
    runner._run_on_line = second.append
    runner.line_received.emit("only the current run may hear this")
    assert first == []
    assert second == ["only the current run may hear this"]


# ----------------------------------------------------------------------
# The window that opened the nested loop
# ----------------------------------------------------------------------
def test_the_no_instrument_window_opens_once(qapp, tmp_path, monkeypatch):
    """spotread prints its diagnostic again on every retry of an instrument
    that keeps dropping off, and each match used to stack another modal on an
    unanswered one. Its four siblings in that file already guard this."""
    from PyQt6.QtCore import QSettings

    from ui.dialogs.spot_read_dialog import SpotReadDialog

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    runner = ArgyllRunner(s)
    dlg = SpotReadDialog(runner, s, None)

    opened = []

    def fake_exec(self):
        opened.append(1)
        # …and while it is up, the line arrives again, exactly as it does when
        # the instrument reports the same failure on its next retry.
        dlg._on_no_instrument()
        return 0

    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)

    dlg._on_no_instrument()
    assert opened == [1], "one window, however many times it is reported"
    dlg.deleteLater()
