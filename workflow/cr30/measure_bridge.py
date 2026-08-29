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
    from core.i18n import tr
    lines = [tr("ChromIQ could not open your CR30."),
             "",
             tr("  Over USB:       {err}").format(err=usb_err),
             tr("  Over Bluetooth: {err}").format(err=ble_err),
             "",
             tr("Things worth checking:"),
             # FIRST, because it is the one that has actually worked. The
             # instrument went silent over USB while still advertising over
             # Bluetooth, and no amount of replugging or reconnecting helped;
             # switching it off and on again did (2026-08-28).
             tr("  \u2022 Switch the instrument off and on again. A CR30 can "
                "stop answering while still looking connected, and a power "
                "cycle is the only thing that clears it."),
             tr("  \u2022 Is the instrument switched on and, for USB, plugged "
                "in?"),
             tr("  \u2022 Is the phone app connected to it? A CR30 stops being "
                "visible over Bluetooth while another device holds it \u2014 "
                "disconnect there and try again.")]
    if sys.platform.startswith("linux"):
        lines += [tr("  \u2022 On Linux a serial port belongs to the "
                     "\u201cdialout\u201d group. If the instrument is plugged "
                     "in but ChromIQ is refused, add yourself with "
                     "\u201csudo usermod -aG dialout $USER\u201d and log out "
                     "and back in."),
                  tr("  \u2022 Bluetooth needs BlueZ running "
                     "(\u201csystemctl status bluetooth\u201d).")]
    elif sys.platform == "win32":
        lines += [tr("  \u2022 On Windows the CR30 needs its USB-serial "
                     "driver. Windows usually fetches it automatically the "
                     "first time the instrument is plugged in; on a machine "
                     "with no internet you may have to install the CH34x "
                     "driver yourself."),
                  tr("  \u2022 Check Device Manager \u2192 Ports (COM & LPT) "
                     "for the instrument.")]
    else:
        lines += [tr("  \u2022 On macOS there is nothing to install for USB "
                     "\u2014 the driver ships with the system."),
                  tr("  \u2022 The first time ChromIQ uses Bluetooth, macOS "
                     "asks for permission. If you declined it, turn it back on "
                     "in System Settings \u2192 Privacy & Security \u2192 "
                     "Bluetooth.")]
    return "\n".join(lines)


class _ReadWorker(QObject):
    """One reading, taken off the main thread."""

    done = pyqtSignal(str, object)        # loc, (X, Y, Z)
    #: loc, message, exception class name. The NAME matters: a refused reading
    #: and a vanished instrument need opposite answers ("press the button
    #: again" versus "the instrument is not there"), and a signal carrying only
    #: str(e) flattens them into one sentence. Deciding between them by
    #: matching on that sentence is the trap this argument exists to avoid.
    failed = pyqtSignal(str, str, str)

    def __init__(self, loc: str, reader, generation=None) -> None:
        super().__init__()
        self._loc, self._reader = loc, reader
        # Captured when the read is ARMED, not when it starts running. A second
        # click while this thread is still queued would otherwise read the
        # generation AFTER the bump and survive it — the same zombie, now
        # hidden behind a three-minute wait.
        self._generation = generation

    def run(self) -> None:
        try:
            xyz = (self._reader(self._generation)
                   if self._generation is not None else self._reader())
        except Exception as e:            # noqa: BLE001 — a device error is news
            # WAS THIS READ ABANDONED, or did it actually fail? The difference
            # decides whether the user hears anything at all. Answered from the
            # token, never from the message text — deciding by matching on a
            # sentence is exactly the "adjacent in the log is not causal" trap.
            kind = type(e).__name__
            if (self._generation is not None
                    and self._generation != getattr(self._reader,
                                                    "_generation", None)):
                kind = "ReadAbandoned"
            self.failed.emit(self._loc, str(e) or e.__class__.__name__, kind)
            return
        try:
            x, y, z = (float(v) for v in xyz)
        except (TypeError, ValueError) as e:
            self.failed.emit(self._loc, f"unusable reading {xyz!r}: {e}",
                             type(e).__name__)
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
    #: An already-measured patch was armed again because the user navigated to
    #: it deliberately: (loc). They must be told, or the re-arm looks exactly
    #: like the dead session it replaces.
    patch_rearmed = pyqtSignal(str)
    #: Readings the instrument took while no patch was armed, and which were
    #: therefore discarded: (count). To the operator these are presses that did
    #: nothing, so they cannot be left to a debug log.
    readings_discarded = pyqtSignal(int)
    #: The device could not be read, but the session is alive and the patch
    #: has been RE-ARMED: (loc, message). Pressing the button again works.
    read_failed = pyqtSignal(str, str)
    #: The instrument is gone — unplugged, switched off, or the Bluetooth link
    #: dropped: (loc, message). Nothing has been re-armed; pressing the button
    #: cannot help, and telling the user to press it is the wrong advice.
    device_lost = pyqtSignal(str, str)
    #: A read failed and could not be re-armed because it kept failing:
    #: (loc, message). The session is stalled and the user must be told.
    read_gave_up = pyqtSignal(str, str)
    #: The helper recorded a value against a patch we did not answer:
    #: (answered_loc, reported_loc). The read must stop.
    mispaired = pyqtSignal(str, str)

    def __init__(self, send, reader, parent: "QObject | None" = None) -> None:
        super().__init__(parent)
        self._send, self._reader = send, reader
        # Let the reader tell us about presses that landed on nothing, so they
        # can reach the screen instead of a debug log.
        if hasattr(reader, "on_dropped"):
            reader.on_dropped = self.readings_discarded.emit
        #: Failed reads per patch, so a permanently broken device stops rather
        #: than spinning. Per-PATCH, not per-session: a session where five
        #: different patches each needed one retry is a session going fine.
        self._retries: dict[str, int] = {}
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
        # Did the user ASK for this patch? A jump we sent lands as the very
        # next prompt for its target, so this is the one place that knows.
        asked_for = (self._nav_target is not None and loc == self._nav_target)
        if self._nav_target is not None:
            if loc != self._nav_target:
                # Still the patch we are leaving: the jump has not landed yet.
                return
            self._nav_target = None       # the jump landed; normal service
        self._awaiting_loc = loc
        # Nothing left unread. Do NOT ask for the next unread patch here —
        # there is none, and the helper would answer with this same patch for
        # ever. The tab says so instead.
        if ev.get("all_done") and not asked_for:
            # Nothing left unread, and the user did not ask for this patch:
            # there is nothing to arm. But once a chart is COMPLETE the helper
            # sets all_done on every prompt, so returning here unconditionally
            # made the re-read below unreachable for exactly the person who
            # needs it most — a finished chart with one patch that took the
            # wrong colour, and no way left to correct it.
            return
        if ev.get("read") and not asked_for:
            # ALREADY RECORDED, AND ARRIVED AT RATHER THAN CHOSEN.
            #
            # Passing over it is right — traversing a chart must not re-measure
            # everything already done. But simply returning left the session
            # DEAD, and silently: the helper advances by index after every
            # reading, never to the next unread one, so on a resumed chart it
            # lands on measured patches constantly. Each time, nothing was
            # armed, the tab highlighted the patch anyway, and the operator
            # pressed the button at something that was not listening. Basti hit
            # it the moment a re-read finished and the helper stepped to A20.
            #
            # The same shape reaches a FRESH chart too: when a reading is wildly
            # off the expected colour the helper re-offers the same patch marked
            # read, and that landed in this branch as well.
            #
            # So move on instead of stopping. "next_unread" is the helper's own
            # 'n', and it searches AFTER the current patch — with all_done
            # false there is guaranteed to be an unread one to find, so this
            # cannot circle.
            self._send({"cmd": "next_unread"})
            return
        if ev.get("read"):
            # ALREADY READ, AND THE USER CLICKED IT ANYWAY.
            #
            # The old code returned here whatever the reason, with a comment
            # saying "re-reading it would need the user to ask" — and clicking
            # the patch IS the user asking. That is what click-to-jump is for.
            # So a patch that had been given the wrong colour could never be
            # corrected: the preview highlighted it, the helper waited on it,
            # the screen said read this patch, and no reader was ever started.
            # The owner pressed the button repeatedly at nothing.
            #
            # Safe to re-arm: the helper accepts a value for whatever patch it
            # is sitting on, overwrites that row in place and re-saves the
            # measurement file, so nothing is appended and nothing duplicated.
            log.info("CR30: %s was already read and the user asked for it "
                     "again — arming it", loc)
            self.patch_rearmed.emit(loc)
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

    def armed_for(self, loc: str) -> bool:
        """Is a reader actually running for this patch?

        The tab asks before it highlights. Highlighting a patch nothing is
        listening to is the single shape every fault in this area has taken:
        the preview says read this, the helper waits, and the button is
        connected to nothing.
        """
        return self._reading_loc == loc

    def rearm(self) -> bool:
        """Start reading the outstanding patch again. True if there was one.

        For the case where a reading ended the session's contact with the
        instrument and the user chose to carry on anyway: the prompt is still
        outstanding on the helper's side, so all that is missing is a reader.
        Without this, "Keep measuring" would leave a live session with nothing
        listening — the same dead end this round removed elsewhere.
        """
        if self._stopped or self._awaiting_loc is None:
            return False
        if self._reading_loc == self._awaiting_loc:
            return True                    # already reading it
        self._retries.pop(self._awaiting_loc, None)
        self._start_read(self._awaiting_loc)
        return True

    def note_goto(self, target: str) -> None:
        """Call when a ``{"cmd":"goto"}`` is sent, BEFORE it goes out.

        Until the prompt for *target* arrives, any reading belongs to the patch
        the user is leaving and must not be sent.
        """
        self._nav_target = str(target)
        self._awaiting_loc = None
        # LET GO OF THE READ FOR THE PATCH BEING LEFT.
        #
        # It is still blocked waiting for a button, and the operator's next
        # press satisfies THAT read — which then finds the prompt has moved and
        # is discarded as stale. So the first press after every click was
        # thrown away, on both transports, and the user was told "the reading
        # arrived when ChromIQ was not waiting for one". It cost a press every
        # single time.
        #
        # Abandoning is not cancelling: the reader stays usable, only this one
        # read is given up. The reader's own cancel is a one-way latch and
        # using it here would end the session.
        abandon = getattr(self._reader, "abandon_current", None)
        if callable(abandon) and self._reading_loc is not None:
            abandon()
            self._reading_loc = None
        log.debug("CR30: navigation to %s outstanding — holding readings",
                  target)

    def stop(self) -> None:
        """End the session: no further value is sent, whatever arrives."""
        self._stopped = True
        self._awaiting_loc = self._reading_loc = self._nav_target = None
        # Wake the reader too. Ending the session while a wait is in progress
        # is the NORMAL case -- the user presses Stop precisely because they do
        # not want to read the armed patch -- and that wait runs for
        # button_timeout_s. Cancelling here means every stop path gets it
        # rather than only the one that remembers to ask. Measured on the
        # user's hardware twice: 180.5 s and 180.0 s of frozen UI.
        reader = getattr(self, "_reader", None)
        cancel = getattr(reader, "cancel", None)
        if callable(cancel):
            cancel()

    # -- the device's side ---------------------------------------------
    def _start_read(self, loc: str) -> None:
        self._reading_loc = loc
        gen = getattr(self._reader, "_generation", None)
        thread = QThread(self)
        worker = _ReadWorker(loc, self._reader, gen)
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

    #: How many times one patch may be re-armed after a failed read before the
    #: bridge stops trying. Generous: every ordinary cause is something the
    #: operator fixes and retries by hand (cap left on, instrument lifted too
    #: early, a reading refused as a repeat).
    MAX_READ_RETRIES = 5

    def _on_read_failed(self, loc: str, message: str,
                        exc_type: str = "") -> None:
        if self._reading_loc == loc:
            self._reading_loc = None
        if self._stopped:
            # Stop cancels the wait in progress, so the read this ends is the
            # one the user just chose to abandon. Reporting it would put "press
            # the instrument's button" on screen for a session that has already
            # finished -- on EVERY stop, since cancelling is now what makes
            # Stop responsive at all.
            log.debug("CR30: read for %s ended by the stop (%s)", loc, message)
            return

        if exc_type == "ReadAbandoned":
            # The user navigated away and we let this read go. Nothing failed,
            # nothing is owed to them, and re-arming would fight the patch they
            # actually asked for. Silent on purpose — the only case in here
            # that is.
            log.debug("CR30: read for %s abandoned on navigation", loc)
            self._retries.pop(loc, None)
            return

        if exc_type == "DeviceLost":
            # The instrument is not there. Re-arming would wait 180 s for a
            # button on a device that cannot answer, and the message that goes
            # with a re-arm -- "press the button again" -- is the wrong advice.
            log.warning("CR30: instrument lost while reading %s (%s)",
                        loc, message)
            self.device_lost.emit(loc, message)
            return

        # THE SESSION MUST SURVIVE A FAILED READING.
        #
        # `_start_read` has one caller: `on_patch_ready`, which runs only on a
        # new `spot_ready`, which the helper only sends when it receives a
        # command. So a failed read that re-armed nothing left NO reader
        # running and NO prompt ever coming again -- while the preview kept the
        # patch highlighted, the helper still said "Ready to read patch ...",
        # and the message on screen said "press the button on the instrument
        # again". Nothing was listening. The presses landed in a buffer.
        #
        # And the way in is the likeliest first-run mistake there is: start a
        # chart with the magnetic cap still on -- the instrument's resting
        # state -- and patch A1 is refused by the magnet guard. One mistake,
        # whole session dead, no way back except restarting it.
        tries = self._retries.get(loc, 0) + 1
        self._retries[loc] = tries
        if tries > self.MAX_READ_RETRIES:
            log.error("CR30: giving up on %s after %d failed reads (%s)",
                      loc, tries - 1, message)
            self.read_gave_up.emit(loc, message)
            return
        log.info("CR30: read of %s failed (%s) — re-arming, attempt %d",
                 loc, message, tries + 1)
        self.read_failed.emit(loc, message)
        if self._awaiting_loc == loc:
            self._start_read(loc)

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
        self._retries.pop(loc, None)      # it worked; the patch starts fresh
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

    It WAITS for the operator to press the instrument's own button
    (`read_next_measurement`) rather than reading whatever the device already
    holds. That distinction is the whole spot workflow: a CR30 keeps its last
    reading indefinitely, so a plain read returns instantly, looks successful,
    and writes the previous patch's colour under the new patch's id.

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
        #: How long to wait for the operator's button press. Generous on
        #: purpose: finding the right patch on a 390-patch honeycomb and
        #: seating a 33 mm barrel on it is not a two-second job.
        self.button_timeout_s = 180.0
        #: Called with a count when the instrument had taken readings before a
        #: patch was armed. Set by the bridge so the user hears about presses
        #: that did nothing.
        self.on_dropped = None
        #: Bumped to abandon the read in flight WITHOUT ending the reader.
        #: Distinct from `_cancel`, which means "this reader is finished" and
        #: is never cleared — cancelling one read through that latch would make
        #: every later patch fail instantly, which is the dead session this
        #: whole line of work has been removing.
        self._generation = 0
        #: Set once, by stop()/close(), and never cleared: a cancelled reader
        #: is a FINISHED one. Safe because the tab builds a fresh DeviceReader
        #: for every session (ui/tabs/tab_measure.py, _open_cr30_bridge) -- if
        #: one is ever reused, every read would cancel the instant it started.
        self._cancel = False

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

    def __call__(self, generation: "int | None" = None):
        # WAIT for the operator's button press; do NOT read what is already
        # there. The CR30 holds its last reading indefinitely, so
        # `read_measurement()` returns instantly with the previous value and
        # every appearance of success. Measured on a real chart: patch A1
        # received the stale white-tile cache at delta E 60.5, silently, and
        # every patch after it then failed the bit-identical guard with nothing
        # to retry — the session was dead at patch two while the message still
        # said "press the button again".
        with self._lock:
            if self._dev is None:
                try:
                    self._dev = self._open()
                    self._dev.on_dropped = self.on_dropped
                except Exception as exc:      # noqa: BLE001 — classified below
                    # AN INSTRUMENT THAT CANNOT BE OPENED IS A LOST ONE.
                    #
                    # Failing to open raises ConnectionError and its kin, none
                    # of which is a DeviceLost — so it took the "refused
                    # reading" path and a CR30 that was switched OFF was told
                    # "the magnetic cap is still on the instrument". The
                    # silence this whole round removed, re-created one layer
                    # up, and with worse advice than saying nothing.
                    from .device import DeviceLost
                    raise DeviceLost(
                        f"the instrument could not be opened ({exc})") from exc
                log.info("CR30: opened over %s", self._dev.kind)
            from .device import DeviceLost
            try:
                m = self._dev.read_next_measurement(
                    timeout=self.button_timeout_s,
                    cancelled=lambda: self._cancelled() or (
                        generation is not None
                        and generation != self._generation))
            except DeviceLost:
                # Let go of the handle. It belongs to an instrument that is no
                # longer there, and keeping it means a reconnected instrument
                # can never be opened — which would make "Keep measuring" a
                # promise the session cannot keep.
                try:
                    self._dev.close()
                except Exception:          # noqa: BLE001 — it is already gone
                    pass
                self._dev = None
                raise
        from .colour import spectrum_to_xyz
        return spectrum_to_xyz(m.values)

    def calibrate(self, black: bool = False) -> None:
        """Ask the instrument to take a calibration, now.

        `black` picks the DARK reference instead of the white one. This flag was
        once added to `CR30.calibrate` and not to this wrapper — which is what
        the tab actually calls — so every calibration raised TypeError and no
        CR30 measurement could start at all. Three tests covered this flow and
        all three read the SOURCE rather than running it, so the suite stayed
        green through it.

        Uses THIS reader's device handle on purpose. Building a second one
        would mean opening the instrument twice: seconds on USB, and on
        Bluetooth a full disconnect and reconnect of a peripheral that accepts
        one connection at a time — the CR30 stops being visible while anything
        holds it. Sharing the handle also leaves the reading this takes as the
        device's `_previous`, which is exactly the baseline the Bluetooth
        change-detection needs, so the first patch no longer has to establish
        one.

        It takes NO timeout and NO cancel, and neither is an oversight. This
        sends one command and reads the answer — unlike a patch read it does
        not wait for a human, so there is nothing to wait out and nothing to
        give up on. An earlier signature offered both, used neither, and would
        have been believed.

        What it must never take is the reader's own `_cancel` latch: that means
        "this reader is finished", is never cleared, and is checked by every
        wait in device.py — so cancelling a calibration through it would make
        every patch read for the rest of the session fail instantly, which is
        precisely the dead session this work has been removing.
        """
        with self._lock:
            if self._dev is None:
                self._dev = self._open()
                log.info("CR30: opened over %s", self._dev.kind)
            self._dev.calibrate(black=black)
            if black:
                # The dark reference leaves nothing we want to keep as the
                # patch baseline, and read_zero asks its own question straight
                # after. Reading here would only consume the answer.
                return
            # Take the reading the calibration produced, so the device's stored
            # value is known to us rather than left as a surprise for patch A1.
            #
            # WAIT IT OUT, do not read once and give up. Reading too soon
            # returns a zero-filled reply, and that is the device saying "not
            # finished" rather than a bad reading: the owner's calibration on
            # 2026-08-29 failed with "16 zero bands (truncated reply)" because
            # we asked 1.8 s after triggering. A fixed sleep would only be a
            # guess at the longest case, so ask again until it answers.
            import time as _t
            deadline = _t.monotonic() + 12.0
            while True:
                try:
                    self._dev.read_measurement(enforce=False)
                    break
                except Exception:        # noqa: BLE001 — informational only
                    if _t.monotonic() > deadline:
                        log.debug("CR30: could not read back after "
                                  "calibrating", exc_info=True)
                        break
                    _t.sleep(0.5)

    def abandon_current(self) -> int:
        """Give up on the read in flight; later reads are unaffected.

        For when the user navigates away from the patch being read. Returns the
        new generation, which is the token a caller may compare against.
        """
        self._generation += 1
        return self._generation

    def read_zero(self) -> "float | None":
        """Mean reflectance of whatever the instrument is looking at, now.

        Used straight after a black calibration, when the instrument should be
        pointing at nothing: the answer ought to be nothing. It is the ONLY
        honest check either calibration has — the device reports no success
        signal, and for white it returns the same canned value whatever is
        under the cap, so there is nothing there to test at all.

        One-sided, and the window says so: this catches a dark reference set
        too LOW (something was in front of the opening). A reference set too
        high would clamp to a healthy-looking zero and pass.
        """
        with self._lock:
            if self._dev is None:
                return None
            try:
                # TAKE A READING, do not read the stored one. What a
                # calibration command leaves in the stored slot has never been
                # established, and reading it without asking for a fresh
                # measurement is the same stale-cache pattern that once wrote
                # the white-tile cache onto patch A1 at delta E 60.5. So this
                # triggers, waits for the instrument to finish, and then reads.
                self._dev.trigger_unsafe()
                m = self._read_after_trigger()
            except Exception:            # noqa: BLE001 — informational only
                log.debug("CR30: could not read back after the black "
                          "calibration", exc_info=True)
                return None
        return sum(m.values) / len(m.values) if m and m.values else None

    def _read_after_trigger(self, tries: int = 8):
        """Read once the instrument has finished, not once a timer has run.

        A reply that comes back zero-filled is the device saying "not yet", not
        a bad reading — the owner's calibration read-back failed on exactly
        that, 1.8 s after asking. So ask again rather than guess at a sleep.
        """
        import time as _t
        last = None
        for _ in range(tries):
            try:
                return self._dev.read_measurement(enforce=False)
            except Exception as exc:      # noqa: BLE001 — retried below
                last = exc
                _t.sleep(0.4)
        if last is not None:
            raise last
        return None

    def cancel(self) -> None:
        """Stop a wait in progress, so Stop does not block for the timeout."""
        self._cancel = True

    def _cancelled(self) -> bool:
        return self._cancel

    def close(self) -> None:
        # Cancel FIRST, then take the lock with a bound. The worker holds this
        # lock for the whole of read_next_measurement, so an unconditional
        # `with self._lock:` here put the GUI thread behind a wait for the
        # operator's button -- the beachball the user hit twice.
        #
        # Closing the transport is NOT an alternative way out: a closed port
        # makes the read raise, and the waiting loop treats "no frame yet" as
        # normal and goes round again. Cancelling is what the loop actually
        # checks.
        self._cancel = True
        got = self._lock.acquire(timeout=2.0)
        try:
            dev, self._dev = self._dev, None
        finally:
            if got:
                self._lock.release()
        if not got:
            # The worker is still in a read that did not honour the cancel in
            # time. Close anyway: leaving the port open leaks the instrument
            # and the next session cannot open it.
            log.warning("CR30: reader did not stop within 2 s; "
                        "closing the instrument anyway")
        if dev is not None:
            try:
                dev.close()
            except Exception:             # noqa: BLE001 — teardown only
                log.debug("CR30: close failed", exc_info=True)
