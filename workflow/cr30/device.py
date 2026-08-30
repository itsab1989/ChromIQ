"""One API over both transports.

    with CR30.open() as dev:          # BLE if available, else USB serial
        print(dev.identify().model)
        m = dev.read_measurement()

The caller never sees framing, checksums, chunking or poll bytes — and never
sees a reading that failed its guards, because `read_measurement` raises rather
than returning a doubtful one (ERRORS.md).
"""
from __future__ import annotations

import datetime
import struct
import time

from . import ble
from .measurement import Measurement, MeasurementError
from .transport import ShortFrameError, TransportTimeout

import logging

log = logging.getLogger(__name__)


def _parse_reply(raw: bytes, allow_dark: bool = False):
    """The last complete, valid measurement in `raw`, or None.

    `allow_dark` is for ONE caller: the read-back after a black calibration,
    where the instrument is pointing at open air and the honest answer is
    nothing at all. See :meth:`CR30.read_measurement`.

    Factored out so the polling loop can ask the SAME question the parser asks:
    "is a usable reply here yet?" Anything weaker — a length, a header, a
    checksum — is satisfied by the truncated, zero-filled first half of the
    vendor's double reply, which is exactly the frame this validation exists to
    reject.
    """
    offsets, k = [], raw.find(ble.MEASUREMENT_HDR)
    while k >= 0:
        offsets.append(k)
        k = raw.find(ble.MEASUREMENT_HDR, k + 1)
    for i in reversed(offsets):
        if len(raw) - i < ble.MIN_REPLY:
            continue
        try:
            a = ble.BleAxis.parse(raw[i:i + 8])
            v = list(struct.unpack_from(f"<{a.bands}f", raw, i + ble.SPECTRUM_AT))
            l = list(struct.unpack_from("<3f", raw, i + ble.LAB_AT))
            probe = Measurement(a.wavelengths(), [round(x, 6) for x in v],
                                lab=[round(x, 4) for x in l])
            probe.validate()
            if not allow_dark and probe.zero_run() >= 3:
                continue
        except Exception:            # noqa: BLE001 — not usable yet, keep polling
            continue
        return i
    return None


class DeviceLost(MeasurementError):
    """The instrument stopped answering mid-session: unplugged, switched off,
    or the Bluetooth link dropped.

    Distinct from a plain wait, and the distinction is the whole point. The
    spot workflow spends most of its time with NOTHING arriving, because it is
    waiting for a human to press a button — so "no frame yet" is the normal
    state and cannot be an error. A transport that has GONE is a different
    fact, and one the user must be told, or they carry on pressing the button
    on an instrument that is no longer there. (Basti did, 2026-08-28: he
    unplugged mid-measurement and the app said nothing for 71 seconds.)
    """


class CR30:
    def __init__(self, transport, kind: str):
        self._t, self.kind = transport, kind
        self._previous: Measurement | None = None
        self.model = ""
        #: This unit's own tile constant, once it has been learned. Armed by
        #: the session; None means the guard falls back to the hard-coded
        #: constant, which only ever matched the owner's instrument. See
        #: `tile_learning`.
        self.learned_tile: "list[float] | None" = None
        #: This unit's own id, once `identify()` has been called. The key the
        #: learned tile constant is stored under, so a second instrument never
        #: inherits the first one's.
        self.unit_id: "str | None" = None
        self.last_identity = None

    # -- construction ----------------------------------------------------
    @classmethod
    def open_ble(cls, name: str | None = None, *, address: str | None = None,
                 **kw) -> "CR30":
        """Open over Bluetooth.

        With no arguments this DISCOVERS the device: it shortlists advertisers
        exposing the ffe0 service, then confirms each over the protocol by
        checking it reports the CR30 spectral axis (400 nm / 10 nm / 31 bands).
        That is a property of the device, so it works on a unit never seen
        before.

        ⚠ **The advertised name is unit-specific** — it is the device's own id
        string, the value `AA 0A 01` returns over USB. Pass `address` to pin a
        remembered unit (stable per host) or `name` as a convenience hint, but
        never treat either as an identity test.
        """
        t = ble.BleTransport(name, address=address, **kw); t.open()
        return cls(t, "ble")

    @staticmethod
    def discover_ble(timeout: float = 10.0) -> list[dict]:
        """List CR30 candidates for a chooser. See `ble.discover`."""
        import asyncio
        return asyncio.new_event_loop().run_until_complete(
            ble.discover(timeout=timeout))

    @classmethod
    def open_usb(cls, port: str | None = None) -> "CR30":
        """Open over USB, and — when choosing for ourselves — ASK EACH PORT
        WHAT IT IS before handing it back as an instrument.

        ⚠ `1a86:7523` IS NOT A CR30. It is the generic CH340 bridge, inside
        millions of unrelated devices: Arduinos, 3D printers, CNC controllers,
        laser cutters. This method used to take `candidates()[0]` and trust it,
        so with any other CH340 device enumerating first ChromIQ would treat a
        stranger's board as the user's instrument and go on to write a
        calibration frame to it.

        Every candidate is now identified before it is accepted, and a port
        that does not say `CR30` is closed and left alone. Opening is safe in
        itself — `SerialTransport.open` holds DTR and RTS low precisely so that
        looking cannot reset somebody's board — and identification is the
        smallest possible question: one `AA 0A` request, the same frame the
        vendor's own software sends.

        An explicit `port` is still honoured without a question, because then
        the caller has already decided.
        """
        from .transport import SerialTransport
        from .discovery import candidates
        if port is not None:
            t = SerialTransport(port); t.open()
            return cls(t, "usb")

        found = candidates()
        if not found:
            raise ConnectionError("no CH34x serial device found")

        refused: list[str] = []
        for cand in found:
            t = SerialTransport(cand.device)
            try:
                t.open()
                dev = cls(t, "usb")
                # ASK, AND THEN CHECK THE ANSWER.
                #
                # `identify()` does NOT raise for a stranger — it returns an
                # Identity for whatever replied. `Identity.is_cr30()` is the
                # real test, and it had zero callers anywhere in the codebase,
                # so this line once said "raises unless this really is a CR30"
                # and was simply wrong: any CH340 device that answered with
                # parseable frames would have been accepted as the instrument.
                ident = dev.identify()
                if not getattr(ident, "is_cr30", lambda: False)():
                    raise ConnectionError(
                        f"answered, but as {getattr(ident, 'model', None)!r} "
                        "rather than a CR30")
                return dev
            except Exception as exc:    # noqa: BLE001 — try the next one
                try:
                    t.close()
                except Exception:       # noqa: BLE001 — closing a bad port
                    pass
                refused.append(f"{cand.device} ({exc})")
                continue

        # EVERY CH340 SAID NO. Name them, because "no instrument found" while a
        # cable is plainly plugged in is the least helpful thing we could say —
        # and because the likeliest cause is that the CH340 the user can see is
        # something else entirely.
        raise ConnectionError(
            "a CH34x serial device is connected but none of them answered as a "
            "CR30 — that chip is also used by Arduinos, 3D printers and CNC "
            "controllers, so it may not be an instrument at all. Tried: "
            + "; ".join(refused))

    def close(self) -> None:
        self._t.close()

    def __enter__(self) -> "CR30":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- operations ------------------------------------------------------
    def identify(self):
        """Ask the device what it is.

        The ONLY sound identification: USB descriptors describe the shared CH34x
        bridge and expose no serial number, so they cannot distinguish a CR30
        from any other CH34x device (PLATFORM_SUPPORT.md).
        """
        if self.kind == "ble":
            # READ_MEASUREMENT, never the trigger: its reply carries the
            # same axis, and identifying an instrument must not make it
            # measure -- nor, if it happens to be capped, recalibrate.
            # See ble.TRIGGER_UNSAFE (EXP-BLE-012).
            raw = self._t.ask(ble.READ_MEASUREMENT, polls=4)
            i = raw.find(ble.MEASUREMENT_HDR)
            if i < 0 or len(raw) - i < 8:
                raise MeasurementError(f"no status reply ({len(raw)} bytes)")
            axis = ble.BleAxis.parse(raw[i:i + 8])
            # COMPARE IT. This parsed the axis and then ignored it, so ANY
            # device that echoed a measurement header was pronounced a CR30 —
            # the Bluetooth twin of `Identity.is_cr30()` having had no callers.
            got = (axis.start_nm, axis.step_nm, axis.bands)
            if got != ble.EXPECTED_AXIS:
                raise MeasurementError(
                    f"answered, but with a {got[0]}-{got[0] + got[1] * (got[2] - 1)} nm "
                    f"axis in {got[2]} bands, not a CR30's {ble.EXPECTED_AXIS}")
            self.model = "CR30"
            # No unit id over Bluetooth: the reply carries only the axis. The
            # advertised NAME is the unit's own id string, but it is not
            # available on the remembered-address fast path, which never scans.
            self.unit_id = getattr(self._t, "name", None) or None
            self.last_identity = {"model": "CR30", "axis": axis,
                                  "transport": "ble"}
            return self.last_identity
        from .session import Session
        ident = Session(self._t).identify()
        self.model = ident.model
        # KEEP IT. The unit id is what stops one instrument's learned tile
        # constant being applied to another, and asking again costs a round
        # trip the fast paths exist to avoid.
        self.last_identity = ident
        self.unit_id = (getattr(ident, "device_id", "") or "").strip() or None
        return ident

    def trigger_unsafe(self) -> None:
        """Send the raw "measure now" command. Not for casual use.

        ⚠ **Deliberately not called `trigger`.** With a magnet at the aperture
        this command does not measure: the device performs a WHITE CALIBRATION
        against whatever is under the cap and reports the nominal tile value.
        The host cannot see whether a magnet is there, so nothing in software
        can tell which of the two it is about to do.

        For a deliberate, user-initiated calibration use
        :meth:`calibrate_white`, which is the one supported entry point and
        carries the reasoning. For an ordinary reading use
        :meth:`read_next_measurement`, where the operator presses the
        instrument's own button.
        """
        if self.kind == "usb":
            from . import usb_measure
            usb_measure.trigger(self._t)
            return
        # Same reason as `calibrate`: the trigger's own acknowledgement is a
        # `bb 01 …` frame and goes to the event queue, so a reply-buffer wait
        # burns the entire poll budget for nothing.
        #
        # This branch used to raise NotImplementedError, saying "no host
        # trigger is known on BLE". EXP-BLE-012 disproved that on 2026-08-28:
        # sent over Bluetooth with no button press, the stored reading moved
        # 11.2667 %R -> 3.9222 %R, and the operator's own button press on the
        # same surface then read 3.9416 %R -- 0.0347 %R apart, against 11.1 %R
        # of change. The old claim was honest about the vendor capture, which
        # contains no trigger; it was simply never tested.
        self._t.ask(ble.TRIGGER_UNSAFE, polls=4,
                    done=lambda _b: self._t.saw_event(0x01))

    #: The instrument's own calibration commands, as the manufacturer's app
    #: sends them. Captured from the vendor's USB frames
    #: (PRIORART-001, "Calibrate White and Black and Test Target") and from a
    #: Bluetooth trace of the vendor app on the owner's unit, EXP-BLE-016.
    #: Each performs its OWN acquisition — no trigger before or after.
    CAL_WHITE = 0x11
    CAL_BLACK = 0x10

    def calibrate(self, black: bool = False) -> None:
        """Take a calibration the way the instrument's own maker does.

        ChromIQ used to calibrate white by seating a magnet at the aperture and
        firing an ordinary trigger. That works — EXP-BLE-015 proved it returns
        the tile constant — but it is a SIDE EFFECT of the magnet gate, not the
        manufacturer's method, and it can only ever do white. The vendor sends a
        dedicated command for each, and neither goes near the magnet.

        Verified on the owner's own unit, 2026-08-29 (EXP-022), after he lifted
        the standing instruction never to send these: both commands were
        accepted and answered in ~250 ms, and a properly seated white
        calibration moved his paper reading from 83.95 to 88.37 %R — back into
        the band every other reading that evening sat in. So the command really
        does set the reference, and setting it against the wrong surface really
        does shift everything afterwards.

        ⚠ **There is no success signal, on either transport.** The reply's
        bytes read as `… 00 01 00`, which fits a `0x01` result code and fits
        equally well the high byte of a device clock that was never set — over
        Bluetooth the same field carried a real timestamp. Nothing here may be
        reported to the user as "calibration succeeded". What CAN be checked is
        what the readings do afterwards, and for black there is an honest one:
        a reading of nothing should come back at zero.

        The danger this instrument has ever had is calibrating against the
        WRONG surface, silently. Doing it again correctly is the whole restore
        procedure, which is why offering it is safe.
        """
        from .frame import Frame
        cmd = self.CAL_BLACK if black else self.CAL_WHITE
        if self.kind == "usb":
            # 60-byte framing, sub-byte 00 — as the vendor's USB capture sends
            # it. Over Bluetooth the same command carries sub-byte 01 and a
            # 10-byte frame; the difference is the vendor's payload, not the
            # framing rule, and each was copied from the transport it was
            # observed on rather than derived from the other.
            # Clear anything still in flight first, as `transact` does for
            # every other exchange: a straggler would prefix the reply and
            # shift every offset in it.
            self._t.reset_input()
            self._t.send(Frame.build(0xBB, cmd, 0x00, 0))
            self._t.receive(timeout=6.0)
            return
        # Stop as soon as the instrument acknowledges, rather than waiting out
        # three silent poll rounds over an answer already in hand: measured,
        # 1.81 s for a calibration whose device-side share is 0.31 s.
        #
        # The acknowledgement arrives in the reply BUFFER. This asked
        # `saw_event` for one round of the branch's life, which is the event
        # QUEUE — the demux puts a frame there only when its command byte is
        # 0x01, and a calibration's is 0x11 or 0x10. So it matched nothing, and
        # the speed-up it was written for never happened.
        # SHORT POLLS, NOT FEW LONG ONES.
        #
        # Stopping as soon as the answer arrives is only half of it: with the
        # default cadence we did not LOOK until 1.1 s had passed (0.4 s drain,
        # 0.35 s settle, 0.35 s to the first poll) for a device that answers in
        # about 250 ms — measured on this unit, EXP-022. The owner, testing
        # Bluetooth after the first speed fix: "i don't know if it is much
        # faster". He was right, and this is the half that was missing.
        #
        # The ceiling is deliberately unchanged (20 x 0.10 s ~ the old
        # 6 x 0.35 s), so a slow or busy link has no less time than before —
        # only the fast case stops waiting for its own clock.
        #
        # The 0.4 s drain in front of this is NOT touched. It exists to flush
        # stragglers that would otherwise prefix the next reply and shift every
        # offset in it, which once produced fifteen garbage readings, and a
        # calibration can be taken mid-session where a reading has just
        # arrived. Shortening it needs a measurement on hardware, not a guess.
        t0 = time.monotonic()
        self._t.ask(ble.frame(cmd, 0x01), polls=20, wait=0.10,
                    done=lambda _b: self._t.saw_reply(cmd))
        # The second half of the same question: how long the exchange itself
        # took, once the link was already open. Compare against the ~250 ms the
        # device needs (EXP-022) to see what is ours.
        log.info("CR30 BLE: calibration %s answered in %.2f s",
                 "black" if black else "white", time.monotonic() - t0)

    def calibrate_white(self) -> None:
        """Kept for callers that predate :meth:`calibrate`. Prefer that."""
        self.calibrate(black=False)

    def read_next_measurement(self, *, timeout: float = 180.0,
                              cancelled=None, poll: float = 0.25,
                              for_learning: bool = False,
                              trigger_wanted=None) -> Measurement:
        """Wait for the operator to press the instrument's button, then read it.

        THIS, not :meth:`read_measurement`, is the spot workflow. The CR30 holds
        its last reading indefinitely, so reading without waiting returns
        whatever was already there — instantly, and with every appearance of
        success. Measured on a real chart: patch A1 (a lavender) received the
        stale white-tile cache, **delta E 60.5**, written to the .ti3 in silence;
        every patch after it then failed the bit-identical guard and the session
        was dead at patch two.

        On USB the wait is exact: the instrument emits an unsolicited
        ``BB 01 09`` header when its button is pressed, and that frame is also
        the only unit-independent magnet check there is.

        Over BLE no such frame is known, so the wait is by CHANGE — poll the
        stored reading until it differs from the last one we accepted. That is
        weaker (it cannot see a magnet, and it cannot distinguish "not pressed
        yet" from "pressed, identical result"), which is why USB is the better
        transport for a chart.

        *cancelled* is called between polls; return True from it to abort a wait
        the user has given up on.
        """
        import time
        deadline = time.monotonic() + timeout
        if self.kind == "usb":
            from . import usb_measure
            while True:
                if cancelled is not None and cancelled():
                    raise MeasurementError("cancelled while waiting for the "
                                           "instrument's button")
                left = deadline - time.monotonic()
                if left <= 0:
                    raise MeasurementError(
                        f"no button press within {timeout:.0f} s. Place the "
                        "instrument on the highlighted patch and press its own "
                        "button.")
                # A TRIGGER MUST BE SENT FROM THIS THREAD. The reader owns
                # the port for the whole wait, so a trigger sent from the GUI
                # thread would race it -- two readers of one serial stream, and
                # the reply landing in whichever got there first. The keyboard
                # sets a flag; the wait acts on it and collects its own reply.
                if trigger_wanted is not None and trigger_wanted():
                    hdr = self._t.transact(usb_measure.trigger_frame(),
                                           timeout=10.0)
                    if for_learning:
                        m = self.read_measurement(button_header=hdr,
                                                  enforce=False)
                        m.validate()
                        return m
                    # Guarded exactly like a press: the reply cannot report the
                    # magnet gate (byte 58 marks it solicited), so the learned
                    # tile signature is what refuses a gated trigger.
                    return self.read_measurement(button_header=hdr)
                # DO NOT SIT INSIDE `receive` WAITING FOR A PRESS THAT MAY
                # NEVER COME. It blocks for up to a second, and the keyboard
                # trigger above is only looked at between blocks -- so pressing
                # Space cost up to 1 s, half a second on average, before the
                # trigger was even sent. Basti noticed it as "a tiny bit of
                # delay ... compared to the button press on the instrument".
                #
                # Shortening `receive`'s timeout is the wrong fix: a partial
                # read is DISCARDED, so a window that ends mid-frame loses a
                # real press and leaves its remainder to be mis-parsed. Instead
                # only enter `receive` once bytes are actually arriving; the
                # full one-second window still covers the frame once it starts.
                probe = getattr(self._t, "bytes_waiting", None)
                if probe is not None:
                    try:
                        waiting = probe()
                    except Exception as exc:
                        # pyserial raises from `in_waiting` on a port that has
                        # gone -- the same signal the read below uses.
                        raise DeviceLost(
                            f"the instrument stopped answering ({exc})") from exc
                    # -1 means "this transport cannot say", and then the
                    # blocking read below is still the right thing. A missing
                    # accessor is NOT a missing instrument.
                    if waiting == 0:
                        time.sleep(min(poll, 0.02))
                        continue
                try:
                    hdr = usb_measure.wait_for_button_header(
                        self._t, timeout=min(left, 1.0))
                except (TransportTimeout, ShortFrameError):
                    continue          # nothing yet, or a partial frame: wait
                except Exception as exc:
                    # `except Exception: continue` used to stand here, and it
                    # made an unplugged instrument indistinguishable from one
                    # nobody has pressed yet: the read failed instantly, the
                    # loop swallowed it and went round again, and the session
                    # sat silent until the timeout expired. pyserial raises
                    # from `in_waiting` on a port that has gone, so the two
                    # states ARE separable -- they were simply never separated.
                    raise DeviceLost(
                        f"the instrument stopped answering ({exc})") from exc
                if for_learning:
                    # A learning press is SUPPOSED to be gated -- it is the
                    # capped press that teaches this unit its tile constant --
                    # so the magnet guard, which exists to refuse exactly that,
                    # is skipped. `validate()` still runs: a truncated or
                    # non-finite reply must never become the stored constant.
                    # enforce=False also keeps it out of `_previous`, so a
                    # learning press cannot make the next real reading look
                    # like a bit-identical repeat.
                    m = self.read_measurement(button_header=hdr, enforce=False)
                    m.validate()
                    return m
                return self.read_measurement(button_header=hdr)

        # WAIT FOR THE INSTRUMENT TO SAY IT ACTED, RATHER THAN GUESS.
        #
        # The CR30 pushes a 10-byte `bb 01 00 …` frame whenever it takes a
        # reading — VERIFIED on the owner's unit, EXP-BLE-013: three presses,
        # three frames, control phases silent, and nothing sent to the device
        # at any point. That is a real event, exactly like USB's `BB 01 09`
        # button header, and it had been discarded unread.
        #
        # What it replaces was inference: poll the stored value, and call it a
        # press when it changes. That cannot tell one press from three, it
        # cannot see a press that produced the same colour twice, and anything
        # slow slides a reading onto whichever patch is armed by the time it is
        # noticed. The owner measured the consequence — a colour meant for A19
        # written against A20, delta E 73.4 — and described it exactly: "not
        # really happening anything at all for a while but then suddenly a few
        # measurements are recognized (and then for the wrong patches)".
        #
        # Anything the instrument did BEFORE this patch was armed belongs to no
        # patch we can name, so it is dropped rather than collected late. That
        # is the whole mis-attribution, closed at the source.
        wait_for_event = getattr(self._t, "wait_for_event", None)
        if wait_for_event is None:
            raise MeasurementError(
                "this Bluetooth transport cannot report button presses")
        # DO NOT DROP EVENTS ON A LEARNING READ. The learning window asks the
        # user to press the button and THEN click "I have pressed it", so the
        # press is already queued when the read starts -- and this discarded
        # exactly the press it had just asked for, then waited ninety seconds
        # in silence. Over Bluetooth, where learning needs two presses and
        # there is no gate flag, that made the feature impossible as written.
        dropped = 0 if for_learning else self._t.drop_events()
        if dropped:
            # Reported, not merely logged: to the operator this is a press that
            # did nothing, and silence is what made every earlier version of
            # this fault so expensive.
            log.info("CR30: discarded %d %s taken before this patch was "
                     "armed", dropped,
                     "reading" if dropped == 1 else "readings")
            report = getattr(self, "on_dropped", None)
            if callable(report):
                report(dropped)

        while True:
            if cancelled is not None and cancelled():
                raise MeasurementError("cancelled while waiting for the "
                                       "instrument's button")
            left = deadline - time.monotonic()
            if left <= 0:
                raise MeasurementError(
                    f"no button press within {timeout:.0f} s. Place the "
                    "instrument on the highlighted patch and press its own "
                    "button.")
            # THE LOOP HAS TO BE RUNNING. bleak delivers notifications through
            # `call_soon_threadsafe`, so a plain `sleep` here receives nothing,
            # for ever — the presses queue up unseen and the patch times out
            # after three minutes. `wait_for_event` runs the transport's loop
            # while it waits, which is the whole point of it.
            if trigger_wanted is not None and trigger_wanted():
                # Same reasoning as the USB branch: the trigger goes out from
                # the thread that owns the link, and its own reply is read
                # here rather than left for the event queue to deliver.
                self.trigger_unsafe()
                m = self._read_when_ready(deadline)
                if for_learning:
                    m.validate()
                    return m
                m.check_usable(self._previous, learned_tile=self.learned_tile)
                self._previous = m
                return m
            # Same reasoning as the USB branch, and simpler here: BLE events
            # arrive whole through a queue, so a shorter wait cannot split one.
            if wait_for_event(min(left, 0.1), cancelled) is None:
                continue
            # It has acted. Read what it now holds — `_read_when_ready` waits
            # out the zero-filled "not finished yet" reply rather than guessing
            # at a sleep long enough to cover every case.
            m = self._read_when_ready(deadline)
            # `for_learning` reads a press that is SUPPOSED to be gated: the
            # capped press that teaches this unit its own tile constant. The
            # magnet guard would refuse exactly that, so it is skipped -- but
            # `validate()` is not, because a truncated or non-finite reply must
            # never be learned as the constant. It is also not remembered as
            # `_previous`: a learning press is not a patch, and letting it seed
            # the bit-identical check would make the next real reading suspect.
            if for_learning:
                m.validate()
                return m
            m.check_usable(self._previous, learned_tile=self.learned_tile)
            self._previous = m
            return m

    def _read_when_ready(self, deadline: float, tries: int = 6) -> Measurement:
        """Read the stored measurement, waiting out a device that is busy.

        A reply that arrives zero-filled is not a bad reply, it is a BUSY one:
        the owner's calibration failed with "16 zero bands (truncated reply)"
        because we read 1.8 s after asking the instrument to act. The zero-fill
        IS the signal, so the answer is to ask again rather than to guess at a
        sleep long enough to cover every case.
        """
        import time as _time
        last = None
        for _ in range(tries):
            try:
                return self.read_measurement(enforce=False)
            except DeviceLost:
                raise
            except MeasurementError as exc:
                last = exc
                if _time.monotonic() > deadline:
                    break
                _time.sleep(0.5)
            except Exception as exc:
                # A link that has GONE, as opposed to one that is busy. bleak
                # raises once the peripheral is away; without this it would
                # escape as a raw ConnectionError and take the "refused
                # reading" path, where the user is told to press the button
                # again on an instrument that is not there.
                #
                # Logged with its traceback first, because this arm is broad
                # enough to swallow a programming error and report it to the
                # user as a disconnection — a bug that would be invisible in
                # exactly the sessions where it matters.
                log.warning("CR30: read failed with an error that is not a "
                            "measurement fault; treating the instrument as "
                            "gone", exc_info=True)
                raise DeviceLost(
                    f"the Bluetooth link to the instrument dropped ({exc})"
                ) from exc
        raise MeasurementError(
            f"the instrument did not return a complete reading ({last})")

    def read_measurement(self, *, enforce: bool = True, allow_dark: bool = False,
                         button_header=None) -> Measurement:
        """Read the device's stored measurement.

        The CR30 stores the last reading; the spot workflow is *press the
        instrument's own button, then read*. With `enforce` (the default) the
        result is gated by `Measurement.check_usable`, so a tile constant, a
        set magnet-gate flag, or a bit-identical repeat raises instead of being
        returned.

        On USB, pass the unsolicited button header from
        `usb_measure.wait_for_button_header()` as `button_header`. It carries
        the magnet-gate flag AND the device's declared axis, and it is the only
        magnet check that is unit-independent and effective on the first reading
        of a run. Over BLE no equivalent frame is known, so the BLE path has
        **no protocol-level magnet detection at all** -- see TRANSPORT_BLE.md.

        ⚠ `allow_dark` EXISTS FOR THE BLACK CALIBRATION AND NOTHING ELSE.

        A zero-filled reply is normally rejected as truncated, and rightly:
        "a real dark patch reads a few percent, never exactly 0.0 across a
        run". But the dark reference is taken against OPEN AIR, and air reads
        exactly 0.00000 %R on this instrument -- measured before and after, in
        EXP-022. So the expected answer and the fault are byte-identical, and
        the read-back after a black calibration could never succeed: on the
        owner's own Bluetooth session, 2026-08-30, it failed with "candidate at
        0 has 31 zero bands (truncated reply)" and the check silently did
        nothing at all.

        Allowing it costs nothing there, because that check is ONE-SIDED by
        design: it warns when the dark reference reads too HIGH (something was
        in front of the opening). A truncated reply reads zero, which is the
        passing direction, so admitting one cannot turn a bad reference into a
        good report. Never pass this for a patch.
        """
        if self.kind == "usb":
            from . import usb_measure
            m = usb_measure.read_stored(self._t, button_header=button_header)
            m.device_model = self.model or "CR30"
            if enforce:
                m.check_usable(self._previous, learned_tile=self.learned_tile)
                # Same rule as the BLE tail below: only an ACCEPTED reading
                # becomes the baseline. Latent here today (nothing calls the
                # USB path with enforce=False), but leaving the two branches
                # disagreeing is how the BLE bug got written in the first
                # place.
                self._previous = m
            return m
        # Stop polling the moment a COMPLETE, VALID reply is in hand. The
        # predicate is `_parse_reply` itself — the same scan-from-the-end,
        # zero-run-rejecting validation used below, not a length test — so it
        # cannot stop on the truncated half of a double reply. Waiting instead
        # for three silent rounds cost about a second per patch on data already
        # received.
        raw = self._t.ask(ble.READ_MEASUREMENT,
                          done=lambda b: _parse_reply(b, allow_dark) is not None)
        # A stream can hold MORE THAN ONE reply: the vendor's own 410-byte BLE
        # capture is a truncated, zero-filled reply followed by a complete one.
        # A first-match scan takes the truncated one and every length and
        # checksum check still passes. So collect EVERY candidate and keep the
        # last one that survives validation.
        offsets, k = [], raw.find(ble.MEASUREMENT_HDR)
        while k >= 0:
            offsets.append(k)
            k = raw.find(ble.MEASUREMENT_HDR, k + 1)
        if not offsets:
            raise MeasurementError(
                f"measurement header not found in {len(raw)} bytes")
        chosen = last_err = None
        for i in reversed(offsets):
            if len(raw) - i < ble.MIN_REPLY:
                last_err = (f"candidate at {i}: only {len(raw)-i} bytes, "
                            f"need {ble.MIN_REPLY}")
                continue
            a = ble.BleAxis.parse(raw[i:i + 8])
            v = list(struct.unpack_from(f"<{a.bands}f", raw, i + ble.SPECTRUM_AT))
            l = list(struct.unpack_from("<3f", raw, i + ble.LAB_AT))
            probe = Measurement(a.wavelengths(), [round(x, 6) for x in v],
                                lab=[round(x, 4) for x in l])
            try:
                probe.validate()
                if not allow_dark and probe.zero_run() >= 3:
                    raise MeasurementError(
                        f"candidate at {i} has {probe.zero_run()} zero bands "
                        "(truncated reply)")
            except MeasurementError as e:
                last_err = str(e); continue
            chosen, axis, vals, lab = i, a, v, l
            break
        if chosen is None:
            # Count-aware, because this sentence reaches the user through the
            # read-failure window: the project writes singular and plural out
            # rather than "(s)".
            n = len(offsets)
            among = (f"the only candidate in {len(raw)} bytes" if n == 1 else
                     f"any of {n} candidates in {len(raw)} bytes")
            raise MeasurementError(
                f"no usable reply among {among}; last reason: {last_err}")
        i = chosen
        m = Measurement(
            wavelengths=axis.wavelengths(), values=[round(v, 6) for v in vals],
            lab=[round(v, 4) for v in lab], transport=self.kind,
            device_model=self.model or "CR30",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            raw=raw[i:i + ble.MIN_REPLY],
            metadata={"axis": {"start_nm": axis.start_nm, "step_nm": axis.step_nm,
                               "bands": axis.bands},
                      "condition": "D65/10 (device display setting; spectra are "
                                   "illuminant-independent)",
                      "gate_flag": None,
                      "gate_flag_note": "BLE has no known magnet-gate flag; "
                                        "detection here is behavioural only"})
        if enforce:
            m.check_usable(self._previous, learned_tile=self.learned_tile)
            # Only an ACCEPTED reading becomes the one the next is judged
            # against. A polling probe (enforce=False) must not, or the guard
            # ends up comparing a reading to itself.
            self._previous = m
        return m
