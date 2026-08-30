"""BLE transport for the CR30.

BLE is NOT "USB over Bluetooth". Verified differences (TRANSPORT_BLE.md):

  * frames are 10 bytes, not 60
  * the host must write a single 0x01 byte to POLL; the device answers a poll,
    not a command-and-wait. This is the single reason every earlier attempt
    failed.
  * the spectral axis is a big-endian uint16 nm start, where USB uses a byte x10
  * bulk replies arrive as ATT notifications, fragmented at the MTU
  * the checksum rule is the SAME: sum(all bytes but the last) mod 256

Requires `bleak`. Kept import-light so the protocol layer never depends on it.
"""
from __future__ import annotations

import asyncio
import logging
import struct
import time
from dataclasses import dataclass

FFE0_SERVICE = "0000ffe0-0000-1000-8000-00805f9b34fb"
FFE1 = "0000ffe1-0000-1000-8000-00805f9b34fb"
FFE2 = "0000ffe2-0000-1000-8000-00805f9b34fb"

log = logging.getLogger(__name__)

POLL = bytes([0x01])
FRAME_LEN = 10
MARKER_AT = 8

# Reply header for "read stored measurement". Used to RESYNC: stragglers from a
# previous exchange otherwise prefix the reply and shift every offset.
MEASUREMENT_HDR = bytes([0xBB, 0x02, 0x10, 0x00])

SPECTRUM_AT = 8          # 31 x float32 LE
LAB_AT = 184             # 3 x float32 LE
MIN_REPLY = 196


def checksum(data: bytes) -> int:
    """sum(every byte but the last) mod 256 — the same rule USB uses."""
    return sum(data[:-1]) % 256


def frame(cmd: int, sub: int = 0, param: int = 0, data: bytes = b"") -> bytes:
    """Build a 10-byte BLE command frame."""
    if len(data) > 4:
        raise ValueError(f"BLE payload is 4 bytes, got {len(data)}")
    d = bytearray(FRAME_LEN)
    d[0], d[1], d[2], d[3] = 0xBB, cmd, sub, param
    d[4:4 + len(data)] = data
    d[MARKER_AT] = 0xFF
    d[9] = checksum(d)
    return bytes(d)


READ_MEASUREMENT = frame(0x02, 0x10)

# ⚠ THIS IS THE TRIGGER. It is not a status query, whatever the name says.
#
# `bb 01 00` is the USB TRIGGER (usb_measure.trigger_frame), and EXP-BLE-012
# proved on 2026-08-28 that it triggers over Bluetooth too: sent with no button
# press, the stored reading moved 11.27 %R -> 3.92 %R, and the operator's own
# button press on the same surface then read 3.94 %R -- the two agree to
# 0.035 %R, 0.49 % of the mean. A host trigger over BLE was documented as "not
# known"; it was simply never tested.
#
# That matters because a trigger with a MAGNET at the aperture does not
# measure: the device performs a WHITE CALIBRATION against whatever is under
# the cap and reports the nominal tile value. So sending this frame while the
# instrument is capped -- its natural resting state -- silently rewrites its
# white reference. Nothing may send it as part of finding or identifying a
# device. Use READ_MEASUREMENT, whose reply carries the same axis and which
# only reads what is already stored.
TRIGGER_UNSAFE = frame(0x01, 0x00)

# ⚠ The advertised name is the device's OWN device-id string (the value
# AA 0A 01 returns over USB) and is therefore UNIT-SPECIFIC. Hard-coding one
# unit's name works only on that unit. Discovery must go by SERVICE UUID and
# then confirm over the protocol; the name is a hint and a label, never a test.
EXPECTED_AXIS = (400, 10, 31)      # start_nm, step_nm, bands


async def discover(timeout: float = 10.0, *, verify: bool = True) -> list[dict]:
    """Find CR30 candidates without knowing any unit's name.

    Two stages, because neither alone is sound:

    1. **Advertisement filter** — devices exposing the ffe0 service. This is the
       generic HM-10 style BLE-UART service, shared with many unrelated
       products, so it is a shortlist and NOT an identification.
    2. **Protocol confirmation** (`verify=True`) — connect and send the status
       frame. A CR30 replies `bb 01 00` followed by its spectral axis
       400 nm / 10 nm / 31 bands. That is a property of the DEVICE, not of its
       name, so it works on any unit.

    Returns dicts with `name`, `address`, `rssi`, `confirmed`. The caller may
    present them for the user to choose from and remember the choice — the
    address is stable per host, the name is the unit's own id.
    """
    from bleak import BleakScanner, BleakClient

    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    out = []
    for dev, adv in found.values():
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        if FFE0_SERVICE.lower() not in uuids:
            continue
        entry = {"name": adv.local_name or dev.name or "",
                 "address": dev.address, "rssi": adv.rssi, "confirmed": False}
        out.append(entry)
    if verify:
        for entry in out:
            try:
                async with BleakClient(entry["address"], timeout=8.0) as c:
                    buf = bytearray()
                    await c.start_notify(FFE1, lambda _s, d: buf.extend(bytes(d)))
                    # NOT the trigger: identifying a device must never
                    # make it measure, still less calibrate. See
                    # TRIGGER_UNSAFE above.
                    await c.write_gatt_char(FFE1, READ_MEASUREMENT,
                                            response=False)
                    await asyncio.sleep(0.4)
                    for _ in range(4):
                        await c.write_gatt_char(FFE1, POLL, response=False)
                        await asyncio.sleep(0.3)
                        if buf:
                            break
                    i = bytes(buf).find(MEASUREMENT_HDR)
                    if i >= 0 and len(buf) - i >= 8:
                        ax = BleAxis.parse(bytes(buf)[i:i + 8])
                        entry["axis"] = (ax.start_nm, ax.step_nm, ax.bands)
                        entry["confirmed"] = entry["axis"] == EXPECTED_AXIS
            except Exception as e:
                entry["error"] = type(e).__name__
    return out


@dataclass
class BleAxis:
    start_nm: int
    step_nm: int
    bands: int

    @classmethod
    def parse(cls, hdr: bytes) -> "BleAxis":
        """Bytes 4..7 of a reply: uint16 BE start, uint8 step, uint8 count."""
        start = struct.unpack_from(">H", hdr, 4)[0]
        return cls(start, hdr[6], hdr[7])

    def wavelengths(self) -> list[int]:
        return [self.start_nm + i * self.step_nm for i in range(self.bands)]


class BleTransport:
    """Poll-driven BLE link. Synchronous facade over bleak's async API."""

    def __init__(self, name: str | None = None, *, address: str | None = None,
                 timeout: float = 20.0):
        """`address` selects a remembered unit; `name` is an optional hint.

        With neither, the transport DISCOVERS by service UUID and confirms over
        the protocol — so it works on a CR30 it has never seen. Passing a name
        is only a convenience for a known unit; it is never an identity test.
        """
        self.name, self.address, self.timeout = name, address, timeout
        self._client = None
        self._buf = bytearray()
        #: Unsolicited "the instrument acted" frames, kept apart from
        #: the reply buffer so that draining one cannot lose the other.
        from collections import deque
        self._events: "deque[bytes]" = deque(maxlen=64)
        self._loop = None

    # -- lifecycle -------------------------------------------------------
    def _run(self, coro):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(coro)

    def open(self) -> None:
        from bleak import BleakClient, BleakScanner

        async def _open():
            target = self.address
            if target is None and self.name:
                target = await BleakScanner.find_device_by_name(
                    self.name, timeout=self.timeout)
            if target is None:
                cands = await discover(timeout=min(self.timeout, 12.0))
                ok = [c for c in cands if c["confirmed"]] or cands
                if not ok:
                    raise ConnectionError(
                        "No CR30 found over Bluetooth. The device stops "
                        "advertising while another central holds it, so "
                        "disconnect the phone app; then press its button to "
                        "wake it and try again.")
                target = ok[0]["address"]
            # REMEMBER WHAT WE ACTUALLY CONNECTED TO, so the caller can skip
            # the scan next time. Measured on the owner's Mac, 2026-08-30:
            # finding the device by name took 15.42 s, connecting to it 2.33 s.
            # The scan is the whole of his "it takes a while", and an address
            # makes it unnecessary.
            self.address = target
            c = BleakClient(target, timeout=self.timeout)
            t0 = time.monotonic()
            await c.connect()
            t1 = time.monotonic()
            await c.start_notify(FFE1, self._on_notify)
            # TIMED, BECAUSE THIS IS WHERE THE OWNER'S FIRST GAP LIVES.
            # The first connection of a session is made when he presses
            # Calibrate, and nothing on screen says anything is happening. Any
            # remedy for that has to start from a number, not an impression:
            # "i don't know if it is much faster" is what guessing earned last
            # time. Found and connect are separated because they have different
            # cures — a slow FIND wants the address remembered, a slow CONNECT
            # wants the link opened before the window rather than inside it.
            log.info("CR30 BLE: found in %.2f s, connected in %.2f s, "
                     "notifications in %.2f s",
                     t0 - t_start, t1 - t0, time.monotonic() - t1)
            return c

        t_start = time.monotonic()
        self._client = self._run(_open())

    def close(self) -> None:
        if self._client is None:
            return

        async def _close():
            try:
                await self._client.stop_notify(FFE1)
            except Exception:
                pass
            await self._client.disconnect()

        self._run(_close())
        self._client = None

    def __enter__(self) -> "BleTransport":
        self.open(); return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- link ------------------------------------------------------------
    def _on_notify(self, _sender, data: bytearray) -> None:
        """One channel, two kinds of traffic — separate them here.

        The instrument pushes a 10-byte `bb 01 00 …` frame WHENEVER IT ACTS:
        VERIFIED on the owner's unit, EXP-BLE-013 (three presses, three frames,
        controls silent, nothing sent) and again in EXP-BLE-015, where our own
        trigger produced one too. That is an EVENT, and it is the thing the
        Bluetooth path was missing: without it a press could only be inferred by
        polling the stored value and noticing it changed — which cannot tell one
        press from three and slides readings onto later patches. The owner saw
        exactly that: a colour meant for A19 recorded against A20.

        These frames used to be swallowed. Everything landed in one buffer and
        `_drain` cleared it before every command, so the presses were discarded
        unread and the evidence was thrown away.

        The rule is deliberately narrow: a complete 10-byte frame whose checksum
        is valid and whose command byte is 0x01 is an event; anything else is
        reply data. A measurement reply is 200 bytes and begins `bb 02 10`, so
        the two cannot be confused, and a corrupt or partial frame falls through
        to the reply buffer where the existing validation deals with it.
        """
        b = bytes(data)
        if (len(b) == FRAME_LEN and b[0] == 0xBB and b[1] == 0x01
                and b[MARKER_AT] == 0xFF and b[9] == checksum(b)):
            self._events.append(b)
            return
        self._buf.extend(b)

    # -- the instrument acting, as an event ------------------------------
    def take_event(self) -> "bytes | None":
        """The oldest unclaimed event, or None. Never blocks.

        Kept OUT of `_buf` on purpose, so `_drain` — which exists to stop
        stragglers corrupting the next reply's offsets — cannot destroy them.

        ⚠ Polling this from a plain loop finds NOTHING, however long you wait.
        bleak delivers notifications through `loop.call_soon_threadsafe`, so
        `_on_notify` only runs while this transport's asyncio loop is running,
        and the loop only runs inside `_run`. Use :meth:`wait_for_event`, which
        does. This method is the non-blocking peek for code that is already
        pumping the loop by other means.
        """
        return self._events.popleft() if self._events else None

    def wait_for_event(self, timeout: float, cancelled=None,
                       poll: float = 0.05) -> "bytes | None":
        """Block until the instrument announces that it acted, or time out.

        THE LOOP MUST BE RUNNING, and that is the whole reason this exists.
        The first version of this waited with `take_event()` and `time.sleep`
        in ordinary Python — which never pumps the asyncio loop, so bleak could
        not deliver a single notification and every patch timed out after three
        minutes with the presses queued and invisible. The tests missed it
        because they fed the queue directly and never went through a transport
        at all.
        """
        async def _wait():
            import time as _t
            deadline = _t.monotonic() + timeout
            while True:
                if self._events:
                    return self._events.popleft()
                if cancelled is not None and cancelled():
                    return None
                if _t.monotonic() > deadline:
                    return None
                await asyncio.sleep(poll)

        return self._run(_wait())

    def saw_event(self, cmd: int) -> bool:
        """Has the instrument acknowledged command `cmd` since the last ask?

        The acknowledgement to a calibration or a trigger is a 10-byte frame
        that this transport routes to the EVENT queue, not the reply buffer —
        so a caller waiting for `_buf` to fill is waiting for something that
        will never come, and spends its whole poll budget doing it. This lets
        such a caller stop the moment the answer actually arrives.

        Consuming it here is deliberate: an acknowledgement is not a press, and
        leaving it in the queue would have the next armed patch collect it as
        one.
        """
        for i, frame in enumerate(self._events):
            if len(frame) >= 2 and frame[1] == cmd:
                del self._events[i]
                return True
        return False

    def saw_reply(self, cmd: int) -> bool:
        """Has the reply to command `cmd` arrived in the buffer yet?

        The sibling of :meth:`saw_event`, and the distinction is the whole
        point: the demux routes a 10-byte frame to the event queue only when
        its command byte is 0x01. A CALIBRATION acknowledgement is `bb 11 …` /
        `bb 10 …`, so it lands HERE — and a caller that asked `saw_event` about
        it was asking the wrong queue, matched nothing, and spent its entire
        poll budget waiting out the silence it had already been answered
        through. Measured: 1.81 s for an operation the device finishes in
        0.31 s.

        The prefix is three bytes, not two, and that is deliberate. Every
        capture of this reply — the vendor's Bluetooth trace (EXP-BLE-016,
        `bb 11 00 11 …` / `bb 10 00 1c …`) and both of our own USB sessions
        (EXP-022, `bb 11 00 00 …`) — has 00 in byte 2, while byte 3 varies and
        means nothing we have determined. Two bytes would be findable inside
        the float data of a measurement reply; three is not, on any capture we
        hold. Nothing is asserted here about length or checksum, because the
        Bluetooth reply's length has never been measured.
        """
        return bytes([0xBB, cmd, 0x00]) in bytes(self._buf)

    def drop_events(self) -> int:
        """Forget every event so far; returns how many. Used when arming a
        patch, so a press made while nothing was listening cannot be collected
        later and attributed to the wrong patch.

        Pumps the loop first: an event that has arrived over the air but has
        not been delivered yet would otherwise survive the drop and be
        collected as this patch's press — the very mis-attribution the drop
        exists to prevent.
        """
        async def _settle():
            await asyncio.sleep(0.05)

        try:
            self._run(_settle())
        except Exception:            # noqa: BLE001 — the drop must still happen
            pass
        n = len(self._events)
        self._events.clear()
        return n

    async def _drain(self, wait: float = 0.4) -> None:
        """Flush stragglers BEFORE a command.

        Notifications keep arriving after polling stops. Left in place they
        prefix the next reply and shift every offset — which silently produced
        fifteen garbage readings before this was added.
        """
        for _ in range(3):
            self._buf.clear()
            await asyncio.sleep(wait)
            if not self._buf:
                break
        self._buf.clear()

    async def _ask(self, req: bytes, polls: int, wait: float,
                   done=None) -> bytes:
        await self._drain()
        await self._client.write_gatt_char(FFE1, req, response=False)
        await asyncio.sleep(wait)
        quiet = 0
        for _ in range(polls):
            n = len(self._buf)
            await self._client.write_gatt_char(FFE1, POLL, response=False)
            await asyncio.sleep(wait)
            # STOP WHEN THE ANSWER IS COMPLETE, not when the silence is.
            #
            # Waiting for three quiet rounds spent ~1.05 s confirming silence
            # over data already in hand: measured on the owner's unit, a press
            # took 1.85 s to reach the chart of which the device's own share
            # was 280 ms. On a 390-patch chart that is nearly seven minutes of
            # nothing.
            #
            # `done` must be the caller's FULL validation, never a length test.
            # The vendor's own capture is a truncated, zero-filled reply
            # followed by a complete one, and both pass every length and
            # checksum check — which is why read_measurement collects every
            # candidate and keeps the last that survives. A naive "looks
            # finished" would take the bad one.
            # NOT `and self._buf`. That guard was here until it was measured:
            # a trigger's acknowledgement is routed to the EVENT queue, so the
            # reply buffer stays EMPTY and the predicate watching for that
            # acknowledgement was never called at all — every poll ran, and the
            # event was left in the queue for the next armed patch to collect
            # as a stray press. Every predicate here is safe on empty input
            # (`_parse_reply(b"")` finds no header and returns None).
            if done is not None and done(bytes(self._buf)):
                break
            quiet = quiet + 1 if len(self._buf) == n else 0
            if quiet >= 3 and self._buf:
                break
        return bytes(self._buf)

    def ask(self, req: bytes, *, polls: int = 10, wait: float = 0.35,
            done=None) -> bytes:
        """Send one frame, poll until the device stops sending, return raw bytes."""
        if self._client is None:
            raise ConnectionError("BLE transport is not open")
        return self._run(self._ask(req, polls, wait, done))
