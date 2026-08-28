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


class CR30:
    def __init__(self, transport, kind: str):
        self._t, self.kind = transport, kind
        self._previous: Measurement | None = None
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
            raw = self._t.ask(ble.STATUS, polls=4)
            i = raw.find(bytes([0xBB, 0x01, 0x00]))
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
        """Ask the device to measure NOW (USB only). NOT for a ChromIQ backend.

        ⚠ **Deliberately not called `trigger`, and deliberately not part of the
        recommended integration surface.** The host CANNOT see whether a magnet
        is near the aperture, so the rule "do not trigger with a magnet present"
        is unenforceable in software. `EXP-MEAS-003` could not establish whether
        the host trigger or the button press performed the write that corrupted
        this unit's white reference, so a backend that never sends `BB 01 00`
        cannot cause it either way.

        The spot workflow does not need this: the operator presses the
        instrument's own button and `read_measurement()` collects the result.

        ⚠ Not to be used near a magnet -- see `usb_measure.trigger`. The spot
        workflow does not need it: the operator presses the instrument's own
        button and `read_measurement` collects the result.
        """
        if self.kind != "usb":
            raise NotImplementedError(
                "no host trigger is known on BLE; the operator presses the "
                "instrument's own button (TRANSPORT_BLE.md)")
        from . import usb_measure
        usb_measure.trigger(self._t)

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
                except Exception:
                    continue                      # nothing yet; keep waiting
                return self.read_measurement(button_header=hdr)

        # The reading we will judge the next one against: the last one this
        # session ACCEPTED. Captured before the loop, because the polling reads
        # below must not be allowed to become it.
        accepted = self._previous

        # What "unchanged" means. With no accepted reading yet — the first
        # patch of a session — there is nothing to compare against, and
        # accepting whatever the device happens to be holding is exactly the
        # stale-cache bug this method exists to prevent (see the docstring:
        # patch A1 took the white-tile cache at delta E 60.5). So probe once
        # first and make THAT the baseline: the wait then starts from what the
        # device holds now, and only a genuinely new reading ends it.
        prev = accepted.values if accepted else None
        while prev is None:
            if cancelled is not None and cancelled():
                raise MeasurementError("cancelled while waiting for the "
                                       "instrument's button")
            if time.monotonic() > deadline:
                raise MeasurementError(
                    f"the instrument did not answer within {timeout:.0f} s.")
            try:
                prev = self.read_measurement(enforce=False).values
            except MeasurementError:
                time.sleep(poll)      # not answering yet; keep trying

        while True:
            if cancelled is not None and cancelled():
                raise MeasurementError("cancelled while waiting for the "
                                       "instrument's button")
            if time.monotonic() > deadline:
                raise MeasurementError(
                    f"no new reading within {timeout:.0f} s. Place the "
                    "instrument on the highlighted patch and press its own "
                    "button.")
            m = self.read_measurement(enforce=False)
            if m.values != prev:
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
