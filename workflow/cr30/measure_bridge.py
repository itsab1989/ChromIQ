"""Answering the helper's spot prompts with readings from a CR30 (#159).

Under ``-xx`` ``chromiq-chartread`` opens no instrument. It offers one patch at
a time as ``{"event":"spot_ready","loc":"A1",…}`` and waits for
``{"cmd":"value","xyz":"X Y Z"}`` on its stdin. **This module is the only place
that answers**, and the whole point of it is the protocol discipline, not the
device access — obtaining the reading is injected, so every rule below is
provable without a CR30 attached.

Three measured hazards it exists to prevent
-------------------------------------------

**Never send a value before its prompt.** A value written ahead of the
``spot_ready`` it answers is not queued and not refused — it is simply consumed
by the wrong prompt or lost. A lost patch is invisible; a mis-paired one is a
wrong colour in the ``.ti3`` that nothing downstream can detect. So a reading is
requested only in response to a prompt, and sent only while that prompt is still
the outstanding one.

**The same patch can be offered more than once.** ``{"cmd":"ok"}`` and
``{"cmd":"retry"}`` are not recognised by the external-value parser and simply
loop the prompt, each producing a **duplicate ``spot_ready`` for the same
``loc``** — and ``MeasureManager.send_post_retry_key`` sends ``ok`` from the
existing failure-recovery UI, so this is reached by real users, not only in
theory. A backend that counts events therefore sends three values for one patch
and loses two of them. **The latch is keyed on ``loc`` and on transitions, never
on the event count.**

**A jump must not be answered with the old patch's reading.** The Measure tab
advertises "click any patch in the preview to jump straight to it", which sends
``{"cmd":"goto"}``. While a jump is outstanding, any reading that arrives
belongs to the patch the user is leaving, so it is **dropped with a log line**
and the operator simply reads the patch again — a dropped reading costs one
button press, a mis-paired one costs a wrong profile.

And afterwards, the pairing is **verified**: ``patch_read`` carries its own
``loc``, so if the helper recorded a value against a patch other than the one
that was answered, the read is stopped and said out loud rather than continuing
into a chart nobody can trust.

Threading
---------
Obtaining a CR30 reading waits on a human pressing the instrument's own button,
so it **must not run on the Qt main thread**. Each reading is taken on a worker
thread; the worker and its ``QThread`` are kept referenced until the thread has
finished, or Qt collects a running thread and the process dies.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QThread, pyqtSignal

log = logging.getLogger(__name__)

#: How a dropped or refused reading is reported, so the strings live in one
#: place and the tab can show whichever it wants to.
DROPPED_NAVIGATING = "navigating"
DROPPED_NO_PROMPT = "no_prompt"
DROPPED_STALE_LOC = "stale_loc"


def _no_device_help(usb_err: object, ble_err: object) -> str:
    """Why neither transport worked, in words the user can act on.

    Both failures are reported: a single "no instrument" hides the fact that one
    transport got much further than the other. The platform-specific hints are
    the ones people actually hit, and none of them is guessable from the raw
    exception:

    * **Linux** — a serial port belongs to the ``dialout`` group, so a user who
      is not in it gets a bare permission error from a device that is plugged in
      and working.
    * **Windows** — the CH34x bridge needs its driver; Windows chooses it from
      Windows Update and a machine that has never seen one offline may not have
      it.
    * **macOS** — nothing to install for USB (Apple ships AppleUSBCHCOM), and
      Bluetooth needs the system's permission, which a packaged app asks for the
      first time it scans.

    And on every platform: the CR30 stops advertising while a phone app holds
    it, which looks exactly like a device that is not there.
    """
    import sys
    lines = ["ChromIQ could not open your CR30.",
             "",
             f"  Over USB:       {usb_err}",
             f"  Over Bluetooth: {ble_err}",
             "",
             "Things worth checking:",
             "  \u2022 Is the instrument switched on and, for USB, plugged in?",
             "  \u2022 Is the phone app connected to it? A CR30 stops being "
             "visible over Bluetooth while another device holds it \u2014 "
             "disconnect there and try again."]
    if sys.platform.startswith("linux"):
        lines += ["  \u2022 On Linux a serial port belongs to the "
                  "\u201cdialout\u201d group. If the instrument is plugged in "
                  "but ChromIQ is refused, add yourself with "
                  "\u201csudo usermod -aG dialout $USER\u201d and log out and "
                  "back in.",
                  "  \u2022 Bluetooth needs BlueZ running (\u201csystemctl "
                  "status bluetooth\u201d)."]
    elif sys.platform == "win32":
        lines += ["  \u2022 On Windows the CR30 needs its USB-serial driver. "
                  "Windows usually fetches it automatically the first time the "
                  "instrument is plugged in; on a machine with no internet you "
                  "may have to install the CH34x driver yourself.",
                  "  \u2022 Check Device Manager \u2192 Ports (COM & LPT) for "
                  "the instrument."]
    else:
        lines += ["  \u2022 On macOS there is nothing to install for USB \u2014 "
                  "the driver ships with the system.",
                  "  \u2022 The first time ChromIQ uses Bluetooth, macOS asks "
                  "for permission. If you declined it, turn it back on in "
                  "System Settings \u2192 Privacy & Security \u2192 Bluetooth."]
    return "\n".join(lines)


class _ReadWorker(QObject):
    """One reading, taken off the main thread."""

    done = pyqtSignal(str, object)        # loc, (X, Y, Z)
    failed = pyqtSignal(str, str)         # loc, message

    def __init__(self, loc: str, reader) -> None:
        super().__init__()
        self._loc, self._reader = loc, reader

    def run(self) -> None:
        try:
            xyz = self._reader()
        except Exception as e:            # noqa: BLE001 — a device error is news
            self.failed.emit(self._loc, str(e) or e.__class__.__name__)
            return
        try:
            x, y, z = (float(v) for v in xyz)
        except (TypeError, ValueError) as e:
            self.failed.emit(self._loc, f"unusable reading {xyz!r}: {e}")
            return
        self.done.emit(self._loc, (x, y, z))


class Cr30MeasureBridge(QObject):
    """Drive one ``-xx`` spot session from a CR30.

    *send* is called with the command dict to write to the helper — in the app
    that is ``MeasureManager.send_command``. *reader* is called on a worker
    thread and must return ``(X, Y, Z)`` or raise.
    """

    #: A reading was refused rather than sent: (loc, one of DROPPED_*).
    reading_dropped = pyqtSignal(str, str)
    #: The device could not be read: (loc, message).
    read_failed = pyqtSignal(str, str)
    #: The helper recorded a value against a patch we did not answer:
    #: (answered_loc, reported_loc). The read must stop.
    mispaired = pyqtSignal(str, str)

    def __init__(self, send, reader, parent: "QObject | None" = None) -> None:
        super().__init__(parent)
        self._send, self._reader = send, reader
        #: The prompt currently outstanding, or None. Set from `on_patch_ready`,
        #: cleared when its value goes out.
        self._awaiting_loc: "str | None" = None
        #: The patch a reading is being taken for, so a second prompt for the
        #: same loc (an `ok`/`retry` echo) does not start a second read.
        self._reading_loc: "str | None" = None
        #: The last loc we sent a value for, so `patch_read` can be checked.
        self._answered_loc: "str | None" = None
        #: A jump is outstanding; every reading until the new prompt arrives
        #: belongs to the patch being left.
        self._nav_target: "str | None" = None
        self._stopped = False
        self._threads: list = []          # kept referenced until finished

    # -- state, for the tab and for tests ------------------------------
    @property
    def awaiting_loc(self) -> "str | None":
        return self._awaiting_loc

    @property
    def navigating(self) -> bool:
        return self._nav_target is not None

    # -- the helper's side ---------------------------------------------
    def on_patch_ready(self, ev: dict) -> None:
        """A ``spot_ready``: this patch is now the one the helper is waiting on.

        Keyed on ``loc``, never on arrival count — the same patch is re-offered
        after an inert command, and after every value.
        """
        if self._stopped:
            return
        loc = str(ev.get("loc") or "")
        if not loc:
            return
        if self._nav_target is not None:
            if loc != self._nav_target:
                # Still the patch we are leaving: the jump has not landed yet.
                return
            self._nav_target = None       # the jump landed; normal service
        self._awaiting_loc = loc
        if ev.get("all_done"):
            return
        if ev.get("read"):
            # Already recorded. Re-reading it would need the user to ask; the
            # tab moves on instead, exactly as its own full-read loop does.
            return
        if self._reading_loc == loc:
            # A duplicate prompt for the patch already being read — an `ok` or
            # `retry` echo. Do NOT start a second read; that is the shape that
            # sends three values for one patch.
            return
        self._start_read(loc)

    def on_patch_measured(self, ev: dict) -> None:
        """A ``patch_read``: verify it landed where we answered (B.6)."""
        if self._stopped:
            return
        loc = str(ev.get("loc") or "")
        answered = self._answered_loc
        self._answered_loc = None
        if answered and loc and loc != answered:
            log.error("CR30: value answered for %s was recorded against %s",
                      answered, loc)
            self._stopped = True
            self.mispaired.emit(answered, loc)

    def note_goto(self, target: str) -> None:
        """Call when a ``{"cmd":"goto"}`` is sent, BEFORE it goes out.

        Until the prompt for *target* arrives, any reading belongs to the patch
        the user is leaving and must not be sent.
        """
        self._nav_target = str(target)
        self._awaiting_loc = None
        log.debug("CR30: navigation to %s outstanding — holding readings",
                  target)

    def stop(self) -> None:
        """End the session: no further value is sent, whatever arrives."""
        self._stopped = True
        self._awaiting_loc = self._reading_loc = self._nav_target = None

    # -- the device's side ---------------------------------------------
    def _start_read(self, loc: str) -> None:
        self._reading_loc = loc
        thread = QThread(self)
        worker = _ReadWorker(loc, self._reader)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_reading)
        worker.failed.connect(self._on_read_failed)
        for sig in (worker.done, worker.failed):
            sig.connect(lambda *_a, t=thread: t.quit())
        # BOTH must stay referenced until the thread has finished. A QThread
        # collected while running takes the process with it.
        thread.finished.connect(lambda t=thread, w=worker: self._reap(t, w))
        self._threads.append((thread, worker))
        thread.start()

    def _reap(self, thread, worker) -> None:
        self._threads = [(t, w) for (t, w) in self._threads if t is not thread]
        worker.deleteLater()
        thread.deleteLater()

    def _on_read_failed(self, loc: str, message: str) -> None:
        if self._reading_loc == loc:
            self._reading_loc = None
        self.read_failed.emit(loc, message)

    def _on_reading(self, loc: str, xyz) -> None:
        """A reading arrived. Send it ONLY if its prompt is still outstanding."""
        if self._reading_loc == loc:
            self._reading_loc = None
        if self._stopped:
            return
        why = self._why_not(loc)
        if why is not None:
            log.info("CR30: reading for %s dropped (%s) — read the patch again",
                     loc, why)
            self.reading_dropped.emit(loc, why)
            return
        self._awaiting_loc = None
        self._answered_loc = loc
        x, y, z = xyz
        self._send({"cmd": "value", "xyz": f"{x:.6f} {y:.6f} {z:.6f}"})

    def _why_not(self, loc: str) -> "str | None":
        if self._nav_target is not None:
            return DROPPED_NAVIGATING
        if self._awaiting_loc is None:
            return DROPPED_NO_PROMPT
        if self._awaiting_loc != loc:
            return DROPPED_STALE_LOC
        return None


class DeviceReader:
    """`reader` for :class:`Cr30MeasureBridge`, backed by a real CR30.

    Opens the instrument on first use and keeps it, because opening it costs
    seconds and the operator is standing over the chart. Both the open and the
    read happen on whichever worker thread the bridge is using, never on the Qt
    main thread; a lock serialises them, which is enough because the bridge
    never has two readings outstanding at once — that is the same latch that
    stops a value being sent ahead of its prompt.

    The reading is returned as **XYZ on a 0-100 scale, D50 / CIE 1931 2°** —
    what `chartread -xx` and `colprof` expect, and the condition
    `workflow.cr30.colour` defaults to. `read_measurement` is left to enforce
    its own guards (`Measurement.check_usable`), so a tile constant, a set
    magnet-gate flag or a bit-identical repeat RAISES rather than being handed
    on as a patch colour — a stale reading recorded under a new patch id is the
    exact mislabelling this whole module exists to prevent.
    """

    def __init__(self, transport: str = "auto", *, port: str | None = None,
                 address: str | None = None) -> None:
        import threading
        self._transport, self._port, self._address = transport, port, address
        self._lock = threading.Lock()
        self._dev = None

    def _open(self):
        from .device import CR30
        if self._transport == "usb":
            return CR30.open_usb(self._port)
        if self._transport == "ble":
            return CR30.open_ble(address=self._address)
        try:
            return CR30.open_usb(self._port)
        except Exception as usb_err:      # noqa: BLE001 — try the other one
            log.info("CR30: no USB device (%s); trying Bluetooth", usb_err)
            try:
                return CR30.open_ble(address=self._address)
            except Exception as ble_err:  # noqa: BLE001 — report BOTH honestly
                raise ConnectionError(_no_device_help(usb_err, ble_err)) from ble_err

    def __call__(self):
        with self._lock:
            if self._dev is None:
                self._dev = self._open()
                log.info("CR30: opened over %s", self._dev.kind)
            m = self._dev.read_measurement()
        from .colour import spectrum_to_xyz
        return spectrum_to_xyz(m.values)

    def close(self) -> None:
        with self._lock:
            dev, self._dev = self._dev, None
        if dev is not None:
            try:
                dev.close()
            except Exception:             # noqa: BLE001 — teardown only
                log.debug("CR30: close failed", exc_info=True)
