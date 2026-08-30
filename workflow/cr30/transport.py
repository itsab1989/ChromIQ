"""Transport abstraction for the CR30 reference implementation.

The point of this module is a boundary: **nothing below `Transport` knows the
protocol, and nothing above it knows the operating system.** `frame.py` and
`identity.py` never import `serial`, never enumerate devices and never see a
port name, so the decoder is testable from recorded captures on a machine that
has never had a CR30 attached (CLAUDE.md 14).

Three implementations:

* `SerialTransport` -- USB serial, today's working path.
* `ReplayTransport` -- feeds frames from a recorded capture. No hardware.
  This is what makes CI and contributor work possible.
* `BleTransport`    -- deliberately absent. When BLE is characterised it becomes
  a fourth file implementing this same three-method interface; see
  TRANSPORT_BLE.md. Nothing above `Transport` should need to change.

Transport rules encoded here, and where each comes from:

* **A frame must be written in exactly ONE `write()` call.** VERIFIED,
  `EXP-USB-005c`: a 60-byte frame split as 30+30, 59+1, 1+59 or 20+20+20
  produced **no reply at all**, five times out of five, while the same bytes in
  one write always replied. This is the single most portability-critical rule
  in the transport.
* **Never write more than one frame per call.** VERIFIED, `EXP-USB-005b`:
  120 and 180 bytes in one write produced no reply. The device recovers on the
  next single-frame write with no port reopen.
* **No settling delay is needed after opening the port.** VERIFIED,
  `EXP-USB-005`: 10/10 valid replies with a 0 ms delay, identical to 300 ms.
  The 300 ms in the session-1 probe was untested superstition.
* **No inter-command delay is needed.** VERIFIED, `EXP-USB-005`: 30/30 valid
  replies at a 0 ms gap.
* **Baud rate and line coding are ignored.** VERIFIED, `EXP-USB-005`: identical
  replies at 300 / 115200 / 1000000 baud and at 8N1 / 7E1 / 8N2 / 7N1 / 8O1 --
  and a 60-byte reply completes in ~0.77 ms, which is faster than 60 bytes can
  physically cross a 115200-baud line (5.2 ms). No UART is in the path.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Sequence

from .frame import FRAME_SIZE, Frame, ShortFrameError

# VERIFIED (EXP-USB-005): any value works. Named only because pyserial demands
# one. Do NOT expose this as a user setting (PLATFORM_SUPPORT.md).
NOMINAL_BAUD = 115200

# VERIFIED (EXP-USB-005): median round trip 0.77 ms, max 1.49 ms over 100
# transactions. One second is four orders of magnitude of headroom for an
# identity or status command. Measurement and calibration commands are NOT
# characterised yet and must pass their own timeout.
DEFAULT_TIMEOUT_S = 1.0


class TransportError(Exception):
    """Transport-level failure. Never silently swallowed (CLAUDE.md 14)."""


class TransportTimeout(TransportError):
    """No complete frame arrived within the timeout."""


class Transport(ABC):
    """Byte pipe that carries whole 60-byte frames, and nothing more.

    Implementations must guarantee the one-frame-per-write rule; callers must
    not have to know it.
    """

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def _write(self, data: bytes) -> None: ...

    @abstractmethod
    def _read(self, n: int, timeout: float) -> bytes: ...

    @abstractmethod
    def reset_input(self) -> None: ...

    # -- the interface everything above the transport actually uses ---------
    def send(self, frame: Frame | bytes) -> None:
        data = frame.to_bytes() if isinstance(frame, Frame) else bytes(frame)
        if len(data) != FRAME_SIZE:
            raise TransportError(
                f"refusing to send {len(data)} bytes: the device answers only a "
                f"single {FRAME_SIZE}-byte frame per write (EXP-USB-005b/c)")
        self._write(data)

    def receive(self, timeout: float = DEFAULT_TIMEOUT_S, *, verify: bool = True) -> Frame:
        raw = self._read(FRAME_SIZE, timeout)
        if len(raw) < FRAME_SIZE:
            raise TransportTimeout(
                f"got {len(raw)}/{FRAME_SIZE} bytes in {timeout:.3f} s: {raw.hex()}"
            ) if not raw else ShortFrameError(
                f"partial frame, {len(raw)}/{FRAME_SIZE} bytes: {raw.hex()}")
        return Frame.parse(raw, verify=verify)

    def transact(self, frame: Frame | bytes, timeout: float = DEFAULT_TIMEOUT_S,
                 *, verify: bool = True) -> Frame:
        """One request, one reply. The device supports nothing else.

        VERIFIED (EXP-USB-005): pipelining is not supported -- two frames in one
        write are answered with silence, not with two replies.
        """
        self.reset_input()
        self.send(frame)
        return self.receive(timeout, verify=verify)

    def __enter__(self) -> "Transport":
        self.open(); return self

    def __exit__(self, *exc) -> None:
        self.close()


# ---------------------------------------------------------------- USB serial
class SerialTransport(Transport):
    """USB serial transport (pyserial).

    `pyserial` is imported lazily so that `import cr30` -- and therefore every
    replay test -- works on a machine with neither pyserial nor a device.
    """

    def __init__(self, port: str, baud: int = NOMINAL_BAUD):
        self.port = port
        self.baud = baud          # irrelevant to the device; see module docstring
        self._ser = None

    def open(self) -> None:
        """Open the port WITHOUT touching the modem control lines.

        ⚠ THIS IS NOT ABOUT THE CR30. IT IS ABOUT EVERYTHING ELSE PLUGGED IN.

        `1a86:7523` is the generic CH340 bridge and it is inside millions of
        unrelated devices — Arduinos, 3D printers, CNC controllers, laser
        cutters. Most of those boards AUTO-RESET when DTR is asserted; that is
        how their bootloaders are entered. Simply opening the port restarts
        them, which on a printer means a job stops mid-print.

        `dsrdtr=False` does NOT prevent that. It disables hardware flow
        control, nothing more: pyserial still raises DTR and RTS on open,
        because `_dtr_state`/`_rts_state` default to True. Measured on the
        owner's Mac, 2026-08-30 — ChromIQ's own open reported `dtr True,
        rts True`.

        Holding both LOW before the port is opened is the form that cannot
        reset a board. **And the CR30 does not need them**: with both low it
        identified normally on the owner's unit, same session — `CR30`,
        firmware V11.3. So this costs us nothing and spares somebody else's
        hardware.
        """
        import serial  # noqa: PLC0415 -- deliberately lazy, see class docstring
        ser = serial.Serial()
        ser.port = self.port
        ser.baudrate = self.baud   # irrelevant to the device; see the docstring
        ser.timeout = 0.05
        ser.bytesize, ser.parity, ser.stopbits = 8, "N", 1
        ser.rtscts = ser.dsrdtr = False
        # BEFORE open(), or the lines are asserted the moment it is opened.
        ser.dtr = False
        ser.rts = False
        ser.open()
        self._ser = ser
        # No settle delay: VERIFIED unnecessary (EXP-USB-005, 10/10 at 0 ms).
        self._ser.reset_input_buffer()

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close(); self._ser = None

    def _require(self):
        if self._ser is None:
            raise TransportError("transport is not open")
        return self._ser

    def reset_input(self) -> None:
        self._require().reset_input_buffer()

    def _write(self, data: bytes) -> None:
        ser = self._require()
        n = ser.write(data)          # ONE call, whole frame -- EXP-USB-005c
        if n != len(data):
            raise TransportError(
                f"short write {n}/{len(data)}; a split frame is never answered "
                "(EXP-USB-005c)")
        ser.flush()

    def _read(self, n: int, timeout: float) -> bytes:
        ser = self._require()
        buf = bytearray()
        deadline = time.perf_counter() + timeout
        while len(buf) < n and time.perf_counter() < deadline:
            waiting = ser.in_waiting
            if waiting:
                buf += ser.read(min(waiting, n - len(buf)))
            else:
                time.sleep(0.0005)
        return bytes(buf)


# -------------------------------------------------------------------- replay
@dataclass
class Exchange:
    """One recorded request/response pair. `response=None` records silence."""
    request: bytes
    response: bytes | None
    label: str = ""


class ReplayTransport(Transport):
    """Feeds recorded traffic. No hardware, no OS, no pyserial.

    Strict by default: the request must match the recording byte-for-byte, so a
    replay test fails loudly if the implementation's framing drifts from what
    the device was actually sent. That is the whole point -- a replay that
    tolerates any request proves nothing.

    Recorded silence is replayed as silence, so timeout handling is testable
    without hardware too.
    """

    def __init__(self, exchanges: Iterable[Exchange], *, strict: bool = True):
        self.exchanges: list[Exchange] = list(exchanges)
        self.strict = strict
        self._i = 0
        self._pending = bytearray()
        self.sent: list[bytes] = []

    # -- construction from the real captures in captures/public -------------
    @classmethod
    def from_capture(cls, doc: dict, **kw) -> "ReplayTransport":
        """Build from a parsed capture JSON written by any tools/probe_*.py.

        The probes use several shapes (`trials[].probes[]`, `cases[]`,
        `steps[]`, `batteries[].cases[]`); all of them carry `tx` and `rx` hex
        strings, so one walker handles every capture this project has.
        """
        out: list[Exchange] = []

        def take(rec: dict) -> None:
            tx, rx = rec.get("tx"), rec.get("rx")
            if tx is None:
                return
            resp = bytes.fromhex(rx) if rx else None
            out.append(Exchange(bytes.fromhex(tx), resp or None,
                                rec.get("label") or rec.get("case") or ""))

        def walk(node) -> None:
            if isinstance(node, dict):
                if "tx" in node:
                    take(node)
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(doc)
        return cls(out, **kw)

    def open(self) -> None:
        self._i = 0; self._pending.clear(); self.sent.clear()

    def close(self) -> None:
        pass

    def reset_input(self) -> None:
        self._pending.clear()

    def _write(self, data: bytes) -> None:
        if self._i >= len(self.exchanges):
            raise TransportError(
                f"replay exhausted after {len(self.exchanges)} exchanges; "
                f"unexpected request {data.hex()}")
        ex = self.exchanges[self._i]; self._i += 1
        if self.strict and data != ex.request:
            raise TransportError(
                f"replay mismatch at exchange {self._i - 1} ({ex.label!r}):\n"
                f"  recorded: {ex.request.hex()}\n"
                f"  sent    : {data.hex()}")
        self.sent.append(bytes(data))
        if ex.response:
            self._pending += ex.response

    def _read(self, n: int, timeout: float) -> bytes:
        take = bytes(self._pending[:n]); del self._pending[:len(take)]
        return take          # recorded silence returns b"" immediately

    @property
    def remaining(self) -> int:
        return len(self.exchanges) - self._i
