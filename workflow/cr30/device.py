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

        # TWO DIFFERENT QUESTIONS, AND THEY NEED TWO DIFFERENT VALUES.
        #
        #   `accepted` — the last reading this session USED. That is what
        #   check_usable compares against, because "identical to the previous
        #   one" means the previous one we kept.
        #
        #   `prev` — the last reading the device was SEEN holding, accepted or
        #   not. That is what "the operator has pressed the button" is measured
        #   against, because the device's stored value changes on every press
        #   whether we liked the result or not.
        #
        # Conflating them cost a session. A refused reading (cap on, say) left
        # `_previous` untouched, so the next wait still compared against the
        # last ACCEPTED patch — the device's stored value already differed from
        # it, the wait ended instantly without anyone pressing anything, the
        # same reading was refused again, and the retry budget was gone in
        # under a millisecond. The user pressed once and was told ChromIQ had
        # "tried several times".
        accepted = self._previous
        prev = self._last_seen if self._last_seen is not None else (
            accepted.values if accepted else None)
        while prev is None:
            if cancelled is not None and cancelled():
                raise MeasurementError("cancelled while waiting for the "
                                       "instrument's button")
            if time.monotonic() > deadline:
                raise MeasurementError(
                    f"the instrument did not answer within {timeout:.0f} s.")
            try:
                prev = self._last_seen = self.read_measurement(
                    enforce=False).values
            except DeviceLost:
                # Before the MeasurementError arm below, which it is a subclass
                # of: without this, "the instrument is gone" would land in
                # sleep-and-retry and be swallowed until the timeout -- the
                # exact fault this whole path exists to prevent.
                raise
            except MeasurementError:
                time.sleep(poll)      # not answering yet; keep trying
            except Exception as exc:
                # A link that has GONE, as opposed to one that is merely quiet.
                # This probe runs before the wait proper, so without the same
                # distinction here a device switched off between arming the
                # patch and the first poll escapes as a raw ConnectionError.
                raise DeviceLost(
                    f"the Bluetooth link to the instrument dropped ({exc})"
                ) from exc

        while True:
            if cancelled is not None and cancelled():
                raise MeasurementError("cancelled while waiting for the "
                                       "instrument's button")
            if time.monotonic() > deadline:
                raise MeasurementError(
                    f"no new reading within {timeout:.0f} s. Place the "
                    "instrument on the highlighted patch and press its own "
                    "button.")
            try:
                m = self.read_measurement(enforce=False)
            except MeasurementError:
                raise      # includes DeviceLost, which is one
            except Exception as exc:
                # Same distinction as USB above. bleak raises once the
                # peripheral is gone; his log caught the disconnect itself
                # ("Peripheral Device disconnected!") while the app carried on
                # as though the session were healthy.
                raise DeviceLost(
                    f"the Bluetooth link to the instrument dropped ({exc})"
                ) from exc
            if m.values != prev:
                # The device is holding something new, so the operator has
                # pressed. Record that BEFORE judging it: whatever the verdict,
                # this is now what the next press has to differ from, and a
                # refusal that left the baseline behind made the following wait
                # end instantly on the very reading that had just been refused.
                self._last_seen = m.values
                # Judge it against the last ACCEPTED reading. Passing
                # self._previous here compared the reading to ITSELF once
                # read_measurement had already stored it, so identical_to was
                # always True and every BLE read raised "bit-identical to the
                # previous one" — no patch could ever be read over Bluetooth.
                m.check_usable(accepted)
                self._previous = m
                return m
            time.sleep(poll)

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
