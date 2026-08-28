"""USB measurement: trigger, chunk fetch, spectrum reassembly.

VERIFIED against real captures (EXP-MEAS-001, EXP-MEAS-002/003):

    trigger        BB 01 00 00  -> header BB 01 09 .., axis at offsets 4..6
    fetch chunk    BB 01 10 00  -> 12 x float32 LE at frame offset 6  (bands 0-11)
                   BB 01 11 00  ->                                    (bands 12-23)
                   BB 01 12 00  ->                                    (bands 24-35)
                   BB 01 13 00  -> NOT extra spectrum

Three chunks give 36 floats; only the first 31 are bands, the rest are 0.0.

**Chunk 0x13 is not spectrum.** Its offsets 34..53 repeat bands 0..4 (verified,
60/60 vendor measurement groups and our own captures). itohio/color-science
fetches it and discards it, then accumulates 144 bytes and uses 124 -- the
"20 unexplained bytes" in its write-up. There is nothing unexplained: the
chunking was simply misread.

The axis encoding differs from BLE. Here it is a BYTE x 10 (`28` = 400 nm);
over BLE it is a big-endian uint16 (`01 90` = 400). See TRANSPORT_BLE.md.

**Reading the stored measurement does NOT require a trigger.** The device caches
the last reading (VERIFIED, EXP-MEAS-001), so the spot workflow is: the operator
presses the instrument's own button, we fetch the chunks. That path sends no
trigger, which matters -- see the warning on `trigger()`.
"""
from __future__ import annotations

import datetime
import struct

from .frame import Frame
from .measurement import Measurement, MeasurementError

CMD_MEASURE = 0x01
SUB_TRIGGER = 0x00
SUB_HEADER = 0x09
CHUNK_SUBS = (0x10, 0x11, 0x12)      # 0x13 deliberately excluded: not spectrum
CHUNK_DATA_AT = 6
VALS_PER_CHUNK = 12
FRAME_LEN_MIN = 60

# ---- the magnet gate, as the PROTOCOL reports it --------------------------
# Frame offset 24 of a `BB 01 09` header. CORROBORATED on this unit, and it is
# the ONE magnet check that does not depend on a per-unit stored constant:
#
#   button press, magnet engaged  (EXP-MEAS-002, EXP-MEAS-003)  -> 0x01   2/2
#   button press, no magnet       (EXP-MEAS-001)                -> 0x00   1/1
#   host-triggered, gated or not  (all three sessions)          -> 0x00  20+/20+
#
# MEASUREMENT.md concluded the flag was "useless for the case that matters",
# which was true of the HOST-TRIGGERED path it was arguing about. The workflow
# this project now recommends is the BUTTON path, and there the flag works.
# It needs replication on a second unit before it is VERIFIED; until then it is
# an ADDITIONAL check, never a replacement for the behavioural ones.
GATE_FLAG_AT = 24


def button_header_is_gated(header: "Frame | bytes") -> bool | None:
    """Was this BUTTON-originated measurement header taken with the gate on?

    Returns None -- "cannot tell" -- for anything that is not an unsolicited
    `BB 01 09` header, because offset 24 is only meaningful there. A caller must
    treat None as "unknown", never as "safe".
    """
    b = header.to_bytes() if isinstance(header, Frame) else bytes(header)
    if len(b) < FRAME_LEN_MIN or b[0] != 0xBB or b[1] != CMD_MEASURE or b[2] != SUB_HEADER:
        return None
    if b[58] != 0x00:            # marker 0xFF == solicited; the flag is not set there
        return None
    return b[GATE_FLAG_AT] == 0x01


def wait_for_button_header(transport, *, timeout: float = 60.0) -> Frame:
    """Block until the operator presses the instrument's own button.

    The CR30 emits an unsolicited 60-byte `BB 01 09` header when the button is
    pressed (VERIFIED, 3/3 across EXP-MEAS-001/002/003). This is the spot
    workflow's real trigger, and the frame it returns is the ONLY place the
    magnet-gate flag is reported. Feed it straight to `read_stored`.
    """
    return transport.receive(timeout)


def trigger_frame() -> Frame:
    return Frame.build(0xBB, CMD_MEASURE, SUB_TRIGGER, 0)


def chunk_frame(sub: int) -> Frame:
    return Frame.build(0xBB, CMD_MEASURE, sub, 0)


def parse_axis(header: Frame | bytes) -> tuple[int, int, int]:
    """(start_nm, step_nm, bands) from a BB 01 09 header. Byte x 10 encoding."""
    b = header.to_bytes() if isinstance(header, Frame) else header
    return b[4] * 10, b[6], b[5]


def chunk_values(frame: Frame | bytes) -> list[float]:
    b = frame.to_bytes() if isinstance(frame, Frame) else frame
    return list(struct.unpack_from(f"<{VALS_PER_CHUNK}f", b, CHUNK_DATA_AT))


def assemble(chunks: dict[int, Frame | bytes], bands: int = 31) -> list[float]:
    """Reassemble the spectrum from chunks 0x10/0x11/0x12.

    Raises rather than padding: a missing chunk must fail loudly, never be
    rounded up into a short spectrum (ERRORS.md).
    """
    missing = [s for s in CHUNK_SUBS if s not in chunks]
    if missing:
        raise MeasurementError(
            "missing spectrum chunk(s) " + ", ".join(f"0x{s:02X}" for s in missing)
            + " -- refusing to assemble a partial spectrum")
    vals: list[float] = []
    for s in CHUNK_SUBS:
        vals += chunk_values(chunks[s])
    if len(vals) < bands:
        raise MeasurementError(f"{len(vals)} values for {bands} bands")
    return [round(v, 6) for v in vals[:bands]]


def read_stored(transport, *, timeout: float = 5.0,
                button_header: "Frame | bytes | None" = None) -> Measurement:
    """Fetch the cached measurement. Sends NO trigger.

    This is the spot-workflow path and the safe one: the operator presses the
    instrument's button, we collect. It cannot cause a calibration write.

    `button_header` is the unsolicited `BB 01 09` frame the device emits when
    the button is pressed. **Pass it whenever you have it.** It carries the
    magnet-gate flag (`GATE_FLAG_AT`), which is the only unit-independent
    detection available and the only one that works on the first reading of a
    run. Omitting it is safe but weaker, and the Measurement then says so.

    ⚠ The axis is NOT read here, because this path does not fetch the header
    frame -- and `ERRORS.md` requires that the axis be read from the frame and
    never assumed. Pass `button_header` and the axis IS taken from the device;
    without it the 400/31/10 grid is an ASSUMPTION, recorded as such in
    `metadata["axis_source"]`. This was a live defect until 2026-08-28.
    """
    chunks: dict[int, bytes] = {}
    for sub in CHUNK_SUBS:
        reply = transport.transact(chunk_frame(sub), timeout=timeout)
        chunks[sub] = reply.to_bytes() if isinstance(reply, Frame) else reply

    gate = axis_source = None
    start_nm, step_nm, bands = 400, 10, 31
    if button_header is not None:
        start_nm, step_nm, bands = parse_axis(button_header)
        if (start_nm, step_nm, bands) != (400, 10, 31):
            raise MeasurementError(
                f"device declares an axis this build has never seen: "
                f"{bands} bands from {start_nm} nm in {step_nm} nm steps. "
                "Refusing to decode rather than mislabelling every band.")
        gate = button_header_is_gated(button_header)
        axis_source = "device header (BB 01 09)"
    else:
        axis_source = "ASSUMED 400/31/10 -- no header was fetched"

    values = assemble(chunks, bands=bands)
    return Measurement(
        wavelengths=[start_nm + step_nm * i for i in range(len(values))],
        values=values, transport="usb", gate_flag=gate,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        metadata={"path": "read_stored (no trigger sent)",
                  "axis_source": axis_source,
                  "gate_flag": gate})


def trigger(transport, *, timeout: float = 10.0) -> tuple[int, int, int]:
    """Ask the device to measure now, and return its declared axis.

    ⚠ **Do not call this with a magnet near the aperture.** VERIFIED
    (CALIBRATION.md): a magnet turns a measurement into a white CALIBRATION
    against whatever is under the aperture. `EXP-MEAS-003` could not establish
    whether the host trigger or the button press performed that write, so until
    `EXP-MEAS-004` settles it, a host trigger near a magnet may silently destroy
    the user's stored white reference. `read_stored()` carries no such risk.
    """
    header = transport.transact(trigger_frame(), timeout=timeout)
    return parse_axis(header)
