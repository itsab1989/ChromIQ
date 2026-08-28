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
import struct
from dataclasses import dataclass

FFE0_SERVICE = "0000ffe0-0000-1000-8000-00805f9b34fb"
FFE1 = "0000ffe1-0000-1000-8000-00805f9b34fb"
FFE2 = "0000ffe2-0000-1000-8000-00805f9b34fb"

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
STATUS = frame(0x01, 0x00)

# ⚠ The advertised name is the device's OWN device-id string (the value
# AA 0A 01 returns over USB) and is therefore UNIT-SPECIFIC. Hard-coding one
# unit's name works only on that unit. Discovery must go by SERVICE UUID and
# then confirm over the protocol; the name is a hint and a label, never a test.
STATUS_REPLY_PREFIX = bytes([0xBB, 0x01, 0x00])
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
                    await c.write_gatt_char(FFE1, STATUS, response=False)
                    await asyncio.sleep(0.4)
                    for _ in range(4):
                        await c.write_gatt_char(FFE1, POLL, response=False)
                        await asyncio.sleep(0.3)
                        if buf:
                            break
                    i = bytes(buf).find(STATUS_REPLY_PREFIX)
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
            c = BleakClient(target, timeout=self.timeout)
            await c.connect()
            await c.start_notify(FFE1, self._on_notify)
            return c

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
        self._buf.extend(bytes(data))

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

    async def _ask(self, req: bytes, polls: int, wait: float) -> bytes:
        await self._drain()
        await self._client.write_gatt_char(FFE1, req, response=False)
        await asyncio.sleep(wait)
        quiet = 0
        for _ in range(polls):
            n = len(self._buf)
            await self._client.write_gatt_char(FFE1, POLL, response=False)
            await asyncio.sleep(wait)
            quiet = quiet + 1 if len(self._buf) == n else 0
            if quiet >= 3 and self._buf:
                break
        return bytes(self._buf)

    def ask(self, req: bytes, *, polls: int = 10, wait: float = 0.35) -> bytes:
        """Send one frame, poll until the device stops sending, return raw bytes."""
        if self._client is None:
            raise ConnectionError("BLE transport is not open")
        return self._run(self._ask(req, polls, wait))
