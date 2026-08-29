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

from . import ble
from .measurement import Measurement, MeasurementError
from .transport import ShortFrameError, TransportTimeout

import logging

log = logging.getLogger(__name__)


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
        #: The last spectrum the device was SEEN holding, whether or not
        #: the reading was accepted. Distinct from `_previous` on
        #: purpose: "has the operator pressed the button" and "is this
        #: identical to the reading we kept" are different questions,
        #: and answering both from one value made a refused reading end
        #: the next wait instantly, with nobody pressing anything.
        self._last_seen: "list[float] | None" = None
        self.model = ""

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
        from .transport import SerialTransport
        from .discovery import candidates
        if port is None:
            found = candidates()
            if not found:
                raise ConnectionError("no CH34x serial device found")
            port = found[0].device
        t = SerialTransport(port); t.open()
        return cls(t, "usb")

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
            self.model = "CR30"
            return {"model": "CR30", "axis": axis, "transport": "ble"}
        from .session import Session
        ident = Session(self._t).identify()
        self.model = ident.model
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
        # This branch used to raise NotImplementedError, saying "no host
        # trigger is known on BLE". EXP-BLE-012 disproved that on 2026-08-28:
        # sent over Bluetooth with no button press, the stored reading moved
        # 11.2667 %R -> 3.9222 %R, and the operator's own button press on the
        # same surface then read 3.9416 %R -- 0.0347 %R apart, against 11.1 %R
        # of change. The old claim was honest about the vendor capture, which
        # contains no trigger; it was simply never tested.
        self._t.ask(ble.TRIGGER_UNSAFE, polls=4)

    def calibrate_white(self) -> None:
        """Ask the instrument to take its white calibration, now.

        **This is a deliberate reversal of a documented safety rule, made by
        the instrument's owner on 2026-08-28.** The rule was that a ChromIQ
        backend never sends the trigger command, because the host cannot see a
        magnet and so cannot guarantee it is asking for a measurement rather
        than a calibration. Here that is the entire intention: the user has
        been asked to seat the cap, and the calibration is what they pressed
        for.

        Evidence that it works, on both transports:
          * USB -- EXP-MEAS-004: a host-only trigger moved paper 81.10 -> 149.10
            %R against the cap's green face, and restoring returned it to 81.20,
            ratio 1.0012.
          * BLE -- EXP-BLE-012: host trigger 3.9222 %R against the operator's
            own button press 3.9416 %R on the same surface, 0.0347 %R apart.

        ⚠ **ChromIQ cannot check the result, and must never claim to.** When
        the magnet gate engages the device reports the firmware's nominal tile
        constant whatever is actually under the aperture: the white tile and
        the cap's green face return spectra that are bit-identical, max
        absolute difference across all 31 bands 0.0. So there is no reading to
        judge and no threshold that could be defended.

        The danger is therefore not the magnet -- the magnet is what makes this
        a calibration at all -- but WHICH FACE is at the aperture. Calibrating
        against the green face is what corrupted this unit during the research,
        and the error is one-sided and invisible in every reading afterwards.
        The only safeguard is the operator's eyes, so the window that offers
        this must say so plainly.
        """
        self.trigger_unsafe()

    def read_next_measurement(self, *, timeout: float = 180.0,
                              cancelled=None, poll: float = 0.25) -> Measurement:
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
        dropped = self._t.drop_events()
        if dropped:
            # Reported, not merely logged: to the operator this is a press that
            # did nothing, and silence is what made every earlier version of
            # this fault so expensive.
            log.info("CR30: discarded %d reading(s) taken before this patch "
                     "was armed", dropped)
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
            if wait_for_event(min(left, 1.0), cancelled) is None:
                continue
            # It has acted. Read what it now holds — `_read_when_ready` waits
            # out the zero-filled "not finished yet" reply rather than guessing
            # at a sleep long enough to cover every case.
            m = self._read_when_ready(deadline)
            self._last_seen = m.values
            m.check_usable(self._previous)
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
                raise DeviceLost(
                    f"the Bluetooth link to the instrument dropped ({exc})"
                ) from exc
        raise MeasurementError(
            f"the instrument did not return a complete reading ({last})")

    def read_measurement(self, *, enforce: bool = True,
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
        """
        if self.kind == "usb":
            from . import usb_measure
            m = usb_measure.read_stored(self._t, button_header=button_header)
            m.device_model = self.model or "CR30"
            if enforce:
                m.check_usable(self._previous)
                # Same rule as the BLE tail below: only an ACCEPTED reading
                # becomes the baseline. Latent here today (nothing calls the
                # USB path with enforce=False), but leaving the two branches
                # disagreeing is how the BLE bug got written in the first
                # place.
                self._previous = m
            return m
        raw = self._t.ask(ble.READ_MEASUREMENT)
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
                if probe.zero_run() >= 3:
                    raise MeasurementError(
                        f"candidate at {i} has {probe.zero_run()} zero bands "
                        "(truncated reply)")
            except MeasurementError as e:
                last_err = str(e); continue
            chosen, axis, vals, lab = i, a, v, l
            break
        if chosen is None:
            raise MeasurementError(
                f"no usable reply among {len(offsets)} candidate(s) in "
                f"{len(raw)} bytes; last reason: {last_err}")
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
            m.check_usable(self._previous)
            # Only an ACCEPTED reading becomes the one the next is judged
            # against. A polling probe (enforce=False) must not, or the guard
            # ends up comparing a reading to itself.
            self._previous = m
        return m
