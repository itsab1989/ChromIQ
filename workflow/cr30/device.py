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
        self._previous = m
        return m
