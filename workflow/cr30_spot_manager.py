"""Drives ChromIQ's own CR30 reader for interactive single-patch (spot) reading.

The sibling of :class:`workflow.spot_read_manager.SpotReadManager`, and
deliberately its twin: it presents **the same signals and the same methods**, so
``SpotReadDialog`` does not learn a second vocabulary for a second instrument.
Everything that differs is inside here.

What differs, and why:

* **There is no process and no console to scrape.** ArgyllCMS has never heard of
  a CR30 — not in its instrument enum, not in ``inst_enum()``, and its USB
  matcher does not carry the CR30's vendor id — and its Bluetooth is serial port
  profile while the CR30 is BLE GATT. ChromIQ reads the instrument itself, in
  this process, through :class:`workflow.cr30.measure_bridge.DeviceReader`.
* **The instrument's own button is what produces a reading.** A CR30 holds its
  last reading indefinitely, so asking it for a value returns the previous
  patch's colour instantly and with every appearance of success. ``DeviceReader``
  waits for the press instead, and so this manager always has exactly one read
  outstanding — which is also what this window's help text has always promised:
  *"or press the button on the instrument itself, which does the same thing"*.
* **"Take reading" is a host trigger, not a keypress.** ``request_trigger()``
  hands the outstanding read a trigger the reader thread sends itself, which is
  the same mechanism the Measure tab binds to Space and Enter — and it is
  refused, by the same guard, when the magnet check is not armed for this unit
  (M-CR30-TRIGGER-NOT-ARMED).
* **Calibration happens before the session, not during it**, in the windows
  shared with the Measure tab (``ui/cr30_calibration.py``). Nothing here emits
  ``calibration_prompt``: there is no console prompt to react to, and the reader
  handed to :meth:`start` is already open and calibrated.

The reading comes back as XYZ on a 0-100 scale, D50 / CIE 1931 2°, which is
exactly what the window already consumes from ``spotread``.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.logger import get_logger

log = get_logger(__name__)

#: The instrument name this manager reports. It is the name the device gives
#: for itself and the name the rest of the app keys on — `ui.ti2_loader`'s
#: `is_cr30` / `instrument_family`, `data.patch_db.instrument_family_of` and
#: `KNOWN_INSTRUMENTS` all recognise it — so every per-instrument wording rule
#: in the window resolves to "cr30" without being told about this class.
CR30_MODEL_NAME = "CR30"

#: How long one outstanding read waits for a press before it is re-armed.
#: SHORTER THAN THE MEASURE TAB'S 180 s ON PURPOSE: a spot session has no chart
#: to walk, so a wait that expires is not a failure and nothing needs saying —
#: the loop simply arms another one. Short enough that Stop is felt promptly,
#: long enough that the instrument is not re-armed constantly.
REARM_SECONDS = 30.0

#: The sentence ``workflow.cr30.device`` raises when a wait expires with no
#: press. It is OUR OWN message, matched here to tell an expiry (normal, silent,
#: re-arm) from a refusal (the user must be told). ``tests/`` pins the two
#: together, so rewording it there fails a test instead of quietly turning every
#: expiry into a reported error.
NO_PRESS_MARKER = "no button press within"


class Cr30SpotManager(QObject):
    # --- the same surface SpotReadManager presents -----------------------
    reading_ready           = pyqtSignal(tuple, tuple)  # (xyz, lab)
    ready_to_read           = pyqtSignal()
    instrument_detected     = pyqtSignal(str)
    calibration_prompt      = pyqtSignal()
    calibration_finished    = pyqtSignal()
    calibration_position_wrong = pyqtSignal()
    misread                 = pyqtSignal()
    sensor_wrong_position   = pyqtSignal()
    no_instrument           = pyqtSignal()
    device_busy             = pyqtSignal()
    instrument_disconnected = pyqtSignal()
    coms_init_failed        = pyqtSignal(str)
    inst_init_failed        = pyqtSignal(str)
    session_ended           = pyqtSignal(int)

    # --- and the two this instrument needs on top of it ------------------
    #: A reading was refused by one of the bridge's guards, with the
    #: instrument's own words. One press is lost; the session carries on.
    read_refused            = pyqtSignal(str)
    #: A magnet was at the aperture, so the instrument has already recalibrated
    #: itself against whatever it was resting on. The session STOPS: every
    #: reading after it would be wrong by an unknown factor.
    magnet_gated            = pyqtSignal(str)
    #: "Take reading" was asked for on an instrument whose tile is not learned,
    #: so ChromIQ cannot tell a covered opening from a patch and will not fire
    #: the instrument itself (M-CR30-TRIGGER-NOT-ARMED).
    trigger_not_armed       = pyqtSignal()
    #: The instrument stopped answering: unplugged, switched off, or the
    #: Bluetooth link dropped. The session is PAUSED, not ended: the window
    #: asks whether to look for the instrument again (`reconnect`) or to
    #: stop. The reason is the reader's own words, for the log.
    instrument_lost         = pyqtSignal(str)
    #: The instrument had announced presses before the window said Ready, and
    #: they were not used: (count). Pressed while the calibration's last
    #: window was still open, typically. To the person who pressed, that is a
    #: press that did nothing, so the window says so (M-SPOT-CR30-EARLY-PRESS).
    presses_discarded       = pyqtSignal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._reader = None
        self._thread: "QThread | None" = None
        self._worker: "_ReadLoop | None" = None
        self._on_line: "Callable[[str], None] | None" = None
        self._running = False
        #: Names the run of reads this session is, so a "Take reading" press
        #: can belong to it. One token for the whole session, and deliberately:
        #: here every read is "whatever is under the aperture now", so they are
        #: interchangeable and a press does not care which of them collects it.
        #: The Measure tab's token is a patch id, which is not interchangeable
        #: at all -- see `DeviceReader.arm_trigger`.
        self._session: "object | None" = None
        #: True between a lost instrument and the window's answer. While set,
        #: the read loop has ended but the SESSION has not, so the loop's end
        #: is not reported as the session's.
        self._lost = False

    # ------------------------------------------------------------------
    @property
    def reader(self):
        """The open :class:`DeviceReader` this session is talking to."""
        return self._reader

    @reader.setter
    def reader(self, reader) -> None:
        self._reader = reader

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    def start(self, params, on_line: "Callable[[str], None]") -> None:
        """Begin the session. *params* is accepted and ignored.

        The signature is ``SpotReadManager.start``'s so the window can call
        either without knowing which it holds. The parameters it carries are
        ArgyllCMS's — the mode, ``-H``, ``-N``, extra arguments — and a CR30 has
        none of them: it is reflective only, and its calibration is its own.
        Silently ignoring them is honest here because the window disables every
        one of those controls for this instrument, so there is no setting the
        user made that is being thrown away.
        """
        self._on_line = on_line
        if self._reader is None:
            # Nothing to read with. The window says so; it is not an exception.
            self.no_instrument.emit()
            self.session_ended.emit(-1)
            return
        self._running = True
        self.instrument_detected.emit(CR30_MODEL_NAME)
        try:
            self._reader.button_timeout_s = REARM_SECONDS
        except Exception:      # noqa: BLE001 — a preference, never a blocker
            log.debug("could not set the CR30 re-arm interval", exc_info=True)
        self._note(_transport_note(self._reader))
        # ARM BEFORE THE THREAD EXISTS, so a "Take reading" request has a read
        # to belong to from the first moment (`DeviceReader.arm_trigger`).
        self._session = object()
        try:
            self._reader.arm_trigger(self._session)
        except AttributeError:      # an older reader; the press is refused
            log.debug("CR30: this reader cannot be armed for a trigger")
        # BUT SAY READY ONLY ONCE THE READ LOOP IS REALLY LISTENING.
        #
        # This emitted `ready_to_read` right here, before the loop had even
        # started -- and over Bluetooth the loop's first read began by
        # throwing away every press the instrument had announced so far. A
        # press of the instrument's button in that gap (up to about a second
        # on the simulated radio, beta 17 review) was thrown away while the
        # window said Ready, and only the log mentioned it. The loop now drops
        # the stale presses FIRST and announces itself after
        # (`_ReadLoop.opened`), and no later read of this session drops again,
        # so every press made once Ready is shown is collected.
        self._start_loop(announce_when_open=True)

    def _start_loop(self, announce_when_open: bool = False) -> None:
        # NOT PARENTED TO THIS MANAGER, AND THAT IS THE WHOLE POINT.
        #
        # A QThread parented to the manager is destroyed with it — and a
        # QThread destroyed while it is still running calls `qFatal()`, which
        # takes the process down. Closing the window while the reader is inside
        # a wait is not a rare race: it is what happens every time somebody
        # shuts the window without pressing Stop first. Measured: it aborted
        # the test run outright, in `QThread::~QThread`.
        from core.thread_stack import roomy
        thread, worker = roomy(QThread()), _ReadLoop(self._reader)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.reading.connect(self._on_reading)
        worker.refused.connect(self.read_refused)
        worker.gated.connect(self._on_gated)
        worker.lost.connect(self._on_lost)
        worker.discarded.connect(self.presses_discarded)
        if announce_when_open:
            worker.opened.connect(self.ready_to_read)
        worker.finished.connect(thread.quit)
        worker.finished.connect(self._on_loop_finished)
        self._thread, self._worker = thread, worker
        _keep_until_finished(thread, worker)
        thread.start()

    # ------------------------------------------------------------------
    def take_reading(self) -> None:
        """Take one reading now, without the operator touching the instrument.

        The outstanding read is the one that acts on it — the reader thread owns
        the link for the whole of its wait, so a trigger sent from here would be
        two readers of one stream with the reply going to whichever arrived
        first. ``request_trigger`` only sets a flag; the wait sends the frame
        and collects its own answer.
        """
        reader = self._reader
        if reader is None:
            return
        try:
            if not reader.request_trigger():
                # Either the guard is not armed for this unit, or no read is
                # listening. The first is the one worth a window, and it is the
                # one that persists — so ask.
                if not reader.trigger_allowed():
                    self.trigger_not_armed.emit()
                return
        except Exception:      # noqa: BLE001 — reported, never raised at Qt
            log.warning("CR30: could not ask for a reading", exc_info=True)

    def send_key(self, key: str = "\r") -> None:
        """No console, nothing to send. Present so the window can call it."""

    def quit(self) -> None:
        self._stop_loop()

    def abort(self) -> None:
        self._stop_loop()

    def detach(self) -> None:
        """Let go, so nothing can call back into a window that is closing."""
        self._stop_loop()
        for sig in (self.reading_ready, self.ready_to_read,
                    self.instrument_detected, self.read_refused,
                    self.magnet_gated, self.trigger_not_armed,
                    self.instrument_disconnected, self.instrument_lost,
                    self.presses_discarded, self.session_ended):
            try:
                sig.disconnect()
            except (TypeError, RuntimeError):
                pass      # never connected, or the receiver is already gone

    # ------------------------------------------------------------------
    def _stop_loop(self) -> None:
        """End the read in flight without waiting on the GUI thread.

        ``DeviceReader.cancel`` is what the wait actually polls; closing the
        transport is not an alternative, because a closed port makes the read
        raise and the waiting loop treats "no frame yet" as normal and goes
        round again. The thread is never joined here: it may be most of the way
        through a wait, and joining it is the beachball.
        """
        worker, self._worker = self._worker, None
        thread, self._thread = self._thread, None
        self._session = None
        was_lost, self._lost = self._lost, False
        if worker is not None:
            worker.stop()
        if self._reader is not None:
            try:
                # `cancel` disarms too; this is belt and braces for a reader
                # that predates it. Nothing may collect a press from here.
                self._reader.disarm_trigger()
            except AttributeError:
                pass
            except Exception:      # noqa: BLE001 — teardown only
                log.debug("CR30: disarm failed", exc_info=True)
            try:
                self._reader.cancel()
            except Exception:      # noqa: BLE001 — teardown only
                log.debug("CR30: cancel failed", exc_info=True)
        if thread is not None and not thread.isFinished():
            # Never joined here. The wait it is in may have most of its time
            # left, and joining it on the GUI thread is the beachball. It is
            # kept alive by `_LIVE` until it really stops.
            thread.quit()
        if was_lost and self._running:
            # Paused on a lost instrument, so no loop is left to report the
            # end. Say it here, or Stop would leave the window saying
            # "Stop session" for ever.
            self._running = False
            self.session_ended.emit(-1)
            return
        self._running = False

    def _on_loop_finished(self, code: int) -> None:
        sender = self.sender()
        if (self._worker is not None and sender is not None
                and sender is not self._worker):
            # A loop from BEFORE a reconnect, reporting late. The session it
            # belonged to carries on in the new loop; its end is not news.
            return
        if self._lost:
            # The loop ended because the instrument went away, and the window
            # is asking what to do about it. That is not the end of the
            # session: "Look again" starts a new loop on the same reader.
            return
        self._running = False
        self.session_ended.emit(code)

    def reconnect(self) -> None:
        """Look for the instrument again and carry on reading.

        The reader let go of its dead handle when the loss was reported
        (`DeviceReader.__call__`), so the first read of the new loop opens the
        instrument afresh -- the remembered Bluetooth address first, then a
        search. If it is still not there, that read reports the loss again
        and the window asks again: nobody is left waiting in silence.
        """
        if self._reader is None:
            self._lost = False
            self._running = False
            self.session_ended.emit(-1)
            return
        self._lost = False
        self._running = True
        self._note(_transport_note(self._reader))
        self._session = object()
        try:
            self._reader.arm_trigger(self._session)
        except AttributeError:
            pass
        # NOT "ready" yet: the instrument is still being looked for. The loop
        # says so once the link is really open (`_ReadLoop.opened`), so a
        # press is never invited before anything can collect it.
        self._start_loop(announce_when_open=True)

    def _on_reading(self, xyz: tuple) -> None:
        # THE SAME PAIR THE READING CAME FROM. `DeviceReader.__call__` returns
        # `spectrum_to_xyz(...)` from this very module, at its D50 / 1931 2°
        # defaults, so its partner `xyz_to_lab` is the only conversion that
        # cannot disagree with it. Writing a second one here — with its own
        # white point, from its own matrices — is how two numbers describing
        # one reading come to differ in the last digit and then in the first.
        from workflow.cr30.colour import xyz_to_lab
        lab = xyz_to_lab(tuple(xyz))
        self.reading_ready.emit(tuple(xyz), tuple(lab))
        # THE NEXT READ IS NOT YET OUTSTANDING, WHATEVER THIS USED TO SAY.
        #
        # `_ReadLoop.run` emits its reading and only then goes round to call
        # the reader again, so this slot runs while nothing is inside a wait.
        # Saying "ready" here is still right -- the session is listening and
        # the loop is a microsecond behind -- but it is right because the
        # session is ARMED (see `start`), not because a worker happens to be
        # in position. Believing the old sentence is how a press made in this
        # gap came to be thrown away. And the next read does not drop the
        # presses announced meanwhile: this session's stale presses went once,
        # before its first Ready (`DeviceReader.drop_stale_presses`).
        self.ready_to_read.emit()

    def _on_gated(self, reason: str) -> None:
        self._stop_loop()
        self.magnet_gated.emit(reason)

    def _on_lost(self, reason: str) -> None:
        """The instrument went away. Pause, and let the window ask.

        It used to END the session here, through `_stop_loop`, which also
        CANCELS the reader for good -- so even a window that wanted to look
        again had nothing left to look with, and a CR30 switched back on was
        ignored until the window was closed (Basti, beta 16). Now the loop is
        simply over (it returned by itself), the reader stays usable, and
        `instrument_lost` asks the window. A host that does not listen for it
        gets the old ending.
        """
        log.info("CR30: the instrument stopped answering (%s)", reason)
        worker, self._worker = self._worker, None
        self._thread = None
        if worker is not None:
            worker.stop()
        try:
            if self._reader is not None:
                self._reader.disarm_trigger()
        except Exception:      # noqa: BLE001 — a press must not be kept
            log.debug("CR30: disarm failed", exc_info=True)
        self.instrument_disconnected.emit()
        if self.receivers(self.instrument_lost) > 0:
            self._lost = True
            self.instrument_lost.emit(reason)
            return
        self._stop_loop()
        self.inst_init_failed.emit(reason)

    def _note(self, text: str) -> None:
        if text and self._on_line is not None:
            self._on_line(text)


def _transport_note(reader) -> str:
    """"Connected over the USB cable" / "over Bluetooth", for the log.

    The same thing the Measure tab says after a calibration, and for the same
    reason: ChromIQ picks USB or Bluetooth by itself, and a user who wants
    wireless cannot otherwise tell whether they got it.
    """
    from core.i18n import tr
    try:
        kind = (getattr(reader, "open_transport", "") or "").lower()
    except Exception:          # noqa: BLE001 — a note, never fatal
        return ""
    if kind == "ble":
        return tr("[NOTE] Connected to your CR30 over Bluetooth.")
    if kind == "usb":
        return tr("[NOTE] Connected to your CR30 over the USB cable.")
    return ""


#: Read threads that have been asked to stop but may not have stopped yet.
#: Qt calls `qFatal()` on a QThread destroyed while running, so the last
#: reference is held HERE, outside any window, until the thread reports itself
#: finished. Pruned on each new session rather than from a signal, so nothing
#: has to survive the object that would have carried the connection.
_LIVE: "list[tuple]" = []


def _keep_until_finished(thread, worker) -> None:
    _LIVE.append((thread, worker))
    _LIVE[:] = [(t, w) for (t, w) in _LIVE
                if t is thread or not t.isFinished()]


class _ReadLoop(QObject):
    """One outstanding read at a time, on a thread of its own.

    Never on the GUI thread: ``DeviceReader`` holds its lock for the whole of a
    read, and a slot that waited on it would freeze the window it was opened
    from — the same primitive that froze the app for three minutes on Stop.
    """

    reading  = pyqtSignal(tuple)
    refused  = pyqtSignal(str)
    gated    = pyqtSignal(str)
    lost     = pyqtSignal(str)
    #: The instrument is open, the stale presses are gone, and the first read
    #: is about to wait: from here on every press is collected.
    opened   = pyqtSignal()
    #: How many stale presses were dropped before `opened`.
    discarded = pyqtSignal(int)
    finished = pyqtSignal(int)

    def __init__(self, reader) -> None:
        super().__init__()
        self._reader = reader
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        from workflow.cr30.device import DeviceLost
        from workflow.cr30.measurement import MagnetGated, MeasurementError
        code = 0
        opener = getattr(self._reader, "open_now", None)
        if callable(opener):
            try:
                opener()
            except DeviceLost as exc:
                if not self._stop:
                    self.lost.emit(str(exc))
                self.finished.emit(-1)
                return
            except Exception as exc:      # noqa: BLE001 — reported, not raised
                if not self._stop:
                    self.lost.emit(str(exc) or type(exc).__name__)
                self.finished.emit(-1)
                return
        # The presses the instrument announced BEFORE this point belong to no
        # reading anybody asked for (a press while the calibration's window was
        # still open, a spare capped press of the teach-in), so they go now,
        # once, before the window says Ready -- and not at each read after it.
        dropper = getattr(self._reader, "drop_stale_presses", None)
        if callable(dropper) and not self._stop:
            try:
                dropped = int(dropper() or 0)
            except Exception:             # noqa: BLE001 — the read reports it
                log.debug("CR30: could not drop stale presses", exc_info=True)
                dropped = 0
            if dropped and not self._stop:
                self.discarded.emit(dropped)
        if not self._stop:
            self.opened.emit()
        while not self._stop:
            try:
                xyz = self._reader()
            except DeviceLost as exc:
                if not self._stop:
                    self.lost.emit(str(exc))
                code = -1
                break
            except MagnetGated as exc:
                # NOT a refusal to re-arm from. The instrument has already
                # performed a white calibration against whatever was under the
                # aperture, so every later reading would be wrong by a factor
                # nothing downstream can see.
                if not self._stop:
                    self.gated.emit(str(exc))
                code = -1
                break
            except MeasurementError as exc:
                if self._stop:
                    break
                if NO_PRESS_MARKER in str(exc):
                    continue          # nobody pressed it; arm another read
                self.refused.emit(str(exc))
                continue
            except Exception as exc:      # noqa: BLE001 — reported, not raised
                if not self._stop:
                    self.lost.emit(str(exc) or type(exc).__name__)
                code = -1
                break
            if self._stop:
                break
            self.reading.emit(tuple(xyz))
        self.finished.emit(code)
