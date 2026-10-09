#!/usr/bin/env python3
"""CR30 device-info test (stage 2 of the firmware research, 2026-10-09).

Run with ChromIQ's own interpreter so the proven transport code is used:

    .venv/bin/python scripts/cr30_devinfo.py --dry-run
    .venv/bin/python scripts/cr30_devinfo.py usb
    .venv/bin/python scripts/cr30_devinfo.py ble [--name CMxxxxxxxx]
    .venv/bin/python scripts/cr30_devinfo.py --selftest

WHAT IT MAY SEND, and nothing else (enforced by `_guard`, the single choke
point every write goes through):

  usb : the four ChromIQ identity frames  AA 0A 00..03 00  (60 bytes each),
        exactly as `Frame.build(0xAA, 0x0A, sub, 0)` builds them and as
        `Session.identify()` sends them today.
        The vendor BLE command BB 12 01 is NOT sent over USB (see USB_SKIP_REASON).
  ble : 01                                (the vendor app's wake byte, which is
                                           also ChromIQ's poll byte)
        BB 12 01 00 00 00 00 00 FF CD     (the vendor app's getDeviceInfo frame,
                                           byte-identical to ble.frame(0x12, 0x01))

Every TX and RX is logged in hex with a wall-clock timestamp and a run-relative
offset to logs/devinfo_<mode>_<stamp>.log, and every exchange is written as a
capture JSON (tx/rx hex, the research repo's shape) beside it.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True          # leave no __pycache__ in ChromIQ's tree

CHROMIQ = Path(__file__).resolve().parents[1]
RESEARCH = Path(os.environ.get("CHROMIQ_CR30_RESEARCH", str(Path.home() / "develop" / "chromiq-cr30-research")))  # only for --selftest replays
HERE = Path(__file__).resolve().parent
LOGDIR = Path(os.environ.get("CR30_DEVINFO_LOGDIR", str(Path.cwd() / "cr30_devinfo_logs")))
LAST_USB_ID = LOGDIR / "last_usb_identity.json"

sys.path.insert(0, str(CHROMIQ))
# Pure-protocol imports: no Qt, no settings, no pyserial, no bleak at import time.
from workflow.cr30 import ble as cr30_ble                       # noqa: E402
from workflow.cr30.frame import Frame, START_IDENTITY           # noqa: E402
from workflow.cr30.identity import (CMD_IDENTITY, SUB_BUILD,    # noqa: E402
                                    SUB_MODEL, SUB_SERIAL, SUB_STATUS,
                                    parse_identity)
from workflow.cr30.transport import (SerialTransport,           # noqa: E402
                                     TransportTimeout, ReplayTransport,
                                     Exchange)

REPLY_TIMEOUT_S = 5.0          # per reply, as briefed
MAX_RETRIES = 1                # a retry ONLY after total silence, never after a reply

# ---------------------------------------------------------------- whitelist
IDENTITY_SUBS = (SUB_MODEL, SUB_SERIAL, SUB_BUILD, SUB_STATUS)
USB_IDENTITY = {sub: Frame.build(START_IDENTITY, CMD_IDENTITY, sub, 0x00).to_bytes()
                for sub in IDENTITY_SUBS}
BLE_WAKE = cr30_ble.POLL                                  # b"\x01"
BLE_DEVINFO = cr30_ble.frame(0x12, 0x01)                  # bb 12 01 00 00 00 00 00 ff cd

# The vendor app builds it as dataWrapper([187, 18, 1, 0, 0, 0, 0, 0, 255]):
# the bytes plus their sum, truncated to a byte by the Uint8Array.
_VENDOR = [187, 18, 1, 0, 0, 0, 0, 0, 255]
VENDOR_DEVINFO = bytes(_VENDOR + [sum(_VENDOR) & 0xFF])

# Literal hex, independent of the code that builds the frames: if ChromIQ's
# builder ever drifts, the script refuses to start rather than send the drift.
_LITERAL = {
    "usb": {
        "aa0a0000" + "00" * 54 + "ffb3",
        "aa0a0100" + "00" * 54 + "ffb4",
        "aa0a0200" + "00" * 54 + "ffb5",
        "aa0a0300" + "00" * 54 + "ffb6",
    },
    "ble": {"01", "bb12010000000000ffcd"},
}
ALLOWED = {
    "usb": frozenset(USB_IDENTITY.values()),
    "ble": frozenset({BLE_WAKE, BLE_DEVINFO}),
}

USB_SKIP_REASON = (
    "BB 12 01 is NOT sent over USB. (1) It is a 10-byte BLE frame. USB carries "
    "60-byte frames, and no USB form of it has ever been seen: the vendor USB "
    "corpus (PRIORART-001, 260 frames) never contains cmd 0x12, and ColorQC2's "
    "command bytes are DNGuard-protected, so a 60-byte 'BB 12 01' would be a "
    "guess. (2) SAFETY_ENVELOPE.md 2c rule 4 marks cmd 0x0F-0x12 with a non-zero "
    "subcmd as RED (calibration territory), and the device does not validate "
    "request checksums. (3) USB already answers the same question with AA 0A.")


class NotWhitelisted(RuntimeError):
    pass


def _self_check() -> None:
    for mode, frames in ALLOWED.items():
        got = {f.hex() for f in frames}
        if got != _LITERAL[mode]:
            raise SystemExit(f"REFUSING TO START: {mode} frames built by ChromIQ "
                             f"{sorted(got)} differ from the reviewed literals "
                             f"{sorted(_LITERAL[mode])}")
    if BLE_DEVINFO != VENDOR_DEVINFO:
        raise SystemExit("REFUSING TO START: ble.frame(0x12, 0x01) differs from the "
                         f"vendor app's frame: {BLE_DEVINFO.hex()} vs {VENDOR_DEVINFO.hex()}")


# ------------------------------------------------------------------- logging
class Log:
    def __init__(self, mode: str, *, to_file: bool = True):
        self.t0 = time.monotonic()
        self.mode = mode
        self.exchanges: list[dict] = []
        self.path = None
        self._fh = None
        if to_file:
            LOGDIR.mkdir(parents=True, exist_ok=True)
            stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            self.path = LOGDIR / f"devinfo_{mode}_{stamp}.log"
            self.capture_path = LOGDIR / f"devinfo_{mode}_{stamp}.capture.json"
            self._fh = open(self.path, "w", encoding="utf-8")

    def line(self, kind: str, text: str) -> None:
        now = _dt.datetime.now().isoformat(timespec="microseconds")
        rel = time.monotonic() - self.t0
        s = f"{now} +{rel:8.3f}s {kind:<5} {text}"
        print(s)
        if self._fh:
            self._fh.write(s + "\n"); self._fh.flush()

    def tx(self, data: bytes, note: str = "") -> None:
        self.line("TX", f"{len(data):3d}B {data.hex(' ')}" + (f"   # {note}" if note else ""))

    def rx(self, data: bytes, note: str = "") -> None:
        self.line("RX", f"{len(data):3d}B {data.hex(' ')}" + (f"   # {note}" if note else ""))

    def info(self, text: str) -> None:
        self.line("INFO", text)

    def close(self, summary: dict | None = None) -> None:
        if self._fh:
            doc = {"experiment": f"DEVINFO-{self.mode.upper()}-001",
                   "utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                   "platform": sys.platform, "exchanges": self.exchanges,
                   "summary": summary or {}}
            self.capture_path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
            self.info(f"log: {self.path}")
            self.info(f"capture: {self.capture_path}")
            self._fh.close(); self._fh = None


def _guard(mode: str, data: bytes) -> None:
    """THE choke point. Every byte string any mode writes passes through here."""
    if bytes(data) not in ALLOWED[mode]:
        raise NotWhitelisted(f"refusing to send {bytes(data).hex(' ')} over {mode}: "
                             "not on the whitelist")


# ======================================================================= USB
class LoggedSerial(SerialTransport):
    """ChromIQ's SerialTransport (DTR/RTS held low, one write per frame), with
    every write whitelisted and every byte logged."""

    def __init__(self, port: str, log: Log):
        super().__init__(port)
        self.log = log

    def _write(self, data: bytes) -> None:
        _guard("usb", data)
        self.log.tx(data)
        super()._write(data)

    def _read(self, n: int, timeout: float) -> bytes:
        raw = super()._read(n, timeout)
        self.log.rx(raw, "" if raw else f"nothing in {timeout:.1f} s")
        return raw


class LoggedReplay(ReplayTransport):
    """The same whitelist and logging over recorded traffic (--selftest)."""

    def __init__(self, exchanges, log: Log, **kw):
        super().__init__(exchanges, **kw)
        self.log = log

    def _write(self, data: bytes) -> None:
        _guard("usb", data)
        self.log.tx(data)
        super()._write(data)

    def _read(self, n: int, timeout: float) -> bytes:
        raw = super()._read(n, timeout)
        self.log.rx(raw)
        return raw


def _usb_ask(t, sub: int, log: Log) -> Frame:
    req = USB_IDENTITY[sub]
    for attempt in range(1 + MAX_RETRIES):
        try:
            reply = t.transact(req, timeout=REPLY_TIMEOUT_S)
            log.exchanges.append({"label": f"AA 0A {sub:02X} 00", "tx": req.hex(),
                                  "rx": reply.to_bytes_as_received().hex()})
            return reply
        except TransportTimeout:
            log.exchanges.append({"label": f"AA 0A {sub:02X} 00", "tx": req.hex(), "rx": None})
            if attempt < MAX_RETRIES:
                log.info(f"no reply to AA 0A {sub:02X} in {REPLY_TIMEOUT_S} s; one retry")
                continue
            raise


def usb_identify(t, log: Log) -> dict:
    """AA 0A 00 first; stop if the answer is not 'CR30' (a stranger CH340 then
    received exactly one identity question, which is what ChromIQ sends it too)."""
    frames = {SUB_MODEL: _usb_ask(t, SUB_MODEL, log)}
    ident0 = parse_identity(dict(frames))
    if not ident0.is_cr30():
        raise ConnectionError(f"answered as {ident0.model!r}, not CR30; nothing more sent")
    for sub in (SUB_SERIAL, SUB_BUILD, SUB_STATUS):
        frames[sub] = _usb_ask(t, sub, log)
    ident = parse_identity(frames)
    b0 = frames[SUB_MODEL].to_bytes()
    return {
        "transport": "usb",
        "model": ident.model,
        "device_id (AA 0A 00 @9)": ident.device_id,
        "second_id (AA 0A 01 @19) = BLE advertised name": ident.second_id,
        "software? version_a (AA 0A 01 @49)": ident.version_a,
        "hardware? version_b (AA 0A 02 @29)": ident.version_b,
        "build (AA 0A 02 @5)": ident.build,
        "status_byte (AA 0A 03 @19)": ident.status_byte,
        "device code? (AA 0A 00 bytes 7..8 LE, HYPOTHESIS 793=CR30)":
            int.from_bytes(b0[7:9], "little"),
        "suspect_fields": ident.suspect_fields,
        "raw": {f"AA 0A {k:02X}": v for k, v in ident.raw.items()},
        "bb12_over_usb": "SKIPPED: " + USB_SKIP_REASON,
    }


def _port_holders(port: str) -> str:
    try:
        r = subprocess.run(["lsof", "-t", port], capture_output=True, text=True, encoding="utf-8", timeout=10)
        return r.stdout.strip()
    except Exception:          # noqa: BLE001 — a check, not a requirement
        return ""


def run_usb(args) -> int:
    from workflow.cr30.discovery import candidates
    log = Log("usb")
    summary: dict = {}
    rc = 1
    try:
        log.info(USB_SKIP_REASON)
        ports = [args.port] if args.port else [c.device for c in candidates()]
        log.info(f"CH34x candidates: {ports or 'none'}")
        if not ports:
            log.info("no CH34x serial device. Is the CR30 plugged in and switched on?")
            return 3
        for port in ports:
            held = _port_holders(port)
            if held:
                log.info(f"{port} is held by pid(s) {held.split()}; not touching it "
                         "(close ChromIQ / anything else using the CR30)")
                continue
            t = LoggedSerial(port, log)
            try:
                log.info(f"open {port} (DTR/RTS low, as ChromIQ)")
                t.open()
                summary = usb_identify(t, log)
                summary["port"] = port
                rc = 0
                break
            except Exception as exc:         # noqa: BLE001 — report, try next port
                log.info(f"{port}: {type(exc).__name__}: {exc}")
            finally:
                t.close()
                log.info(f"closed {port}")
        if rc == 0:
            _print_summary(log, summary)
            LOGDIR.mkdir(parents=True, exist_ok=True)
            LAST_USB_ID.write_text(json.dumps(summary, indent=1), encoding="utf-8")
        else:
            log.info("no port answered as a CR30")
            rc = 3
        return rc
    finally:
        log.close(summary)


# ======================================================================= BLE
REPLY_LEN = 200


def parse_devinfo(buf: bytes) -> dict:
    """Decode the BB 12 01 reply exactly as the vendor app does
    (bluetoothle.service.ts getDeviceInfo): code u16 LE @5, category @37..67,
    serial @67..97, softwareVersion @97..127, hardwareVersion @127..157,
    neutral = byte 159 == 1; checkData = sum(all but last) & 0xFF == last.

    The vendor takes whatever arrived once >= 200 bytes. We look for the reply
    header BB 12 first so a straggler (e.g. a 10-byte bb 01 hello) cannot shift
    the offsets, and fall back to the vendor's own "first 200 bytes"."""
    out: dict = {"raw_len": len(buf), "raw": buf.hex()}
    if buf[:len(BLE_DEVINFO)] == BLE_DEVINFO and len(buf) == len(BLE_DEVINFO):
        out["verdict"] = "ECHO: the device returned our own frame (not implemented?)"
        return out
    starts = []
    i = buf.find(b"\xbb\x12")
    while i >= 0:
        starts.append(i); i = buf.find(b"\xbb\x12", i + 1)
    if 0 not in starts:
        starts.append(0)
    for s in starts:
        w = buf[s:s + REPLY_LEN]
        if len(w) == REPLY_LEN and (sum(w[:-1]) & 0xFF) == w[-1]:
            out.update(_decode(w), offset=s, checksum_ok=True,
                       verdict="OK" if s == 0 else f"OK (reply began at byte {s})")
            return out
    if len(buf) >= REPLY_LEN:
        w = buf[starts[0]:starts[0] + REPLY_LEN] if len(buf) - starts[0] >= REPLY_LEN else buf[:REPLY_LEN]
        out.update(_decode(w), checksum_ok=False,
                   verdict="CHECKSUM FAILED: fields shown for inspection only, do not trust")
    else:
        out["verdict"] = f"INCOMPLETE: {len(buf)} of {REPLY_LEN} bytes"
    return out


def _s(b: bytes) -> str:
    nul = b.find(b"\x00")
    return (b if nul < 0 else b[:nul]).decode("utf-8", errors="replace")


def _decode(w: bytes) -> dict:
    return {"header": w[:5].hex(" "),
            "code (u16 LE @5; vendor DB: 793=CR30)": w[5] | (w[6] << 8),
            "category @37": _s(w[37:67]),
            "serial @67": _s(w[67:97]),
            "softwareVersion @97": _s(w[97:127]),
            "hardwareVersion @127": _s(w[127:157]),
            "neutral (@159 == 1)": w[159] == 1}


async def ble_exchange(write, buf: bytearray, log: Log, *, sleep=asyncio.sleep,
                       clock=time.monotonic, poll_every: float = 0.35,
                       max_polls: int = 12) -> bytes:
    """wake (01), 100 ms, BB 12 01 -- the vendor app's order -- then wait up to
    REPLY_TIMEOUT_S, polling with 01 (ChromIQ's verified poll model) while the
    reply is incomplete. One retry of wake+command, and only after TOTAL
    silence: any reply at all is final (SAFETY_ENVELOPE 2c rule 6)."""
    async def w(data: bytes, note: str) -> None:
        _guard("ble", data)
        log.tx(data, note)
        await write(data)

    def complete() -> bool:
        return parse_devinfo(bytes(buf)).get("checksum_ok") is True

    for attempt in range(1 + MAX_RETRIES):
        buf.clear()
        await w(BLE_WAKE, "wake (vendor) / poll (ChromIQ)")
        await sleep(0.1)
        await w(BLE_DEVINFO, "device info, vendor getDeviceInfo")
        deadline = clock() + REPLY_TIMEOUT_S
        polls = 0
        await sleep(poll_every)
        while clock() < deadline and not complete():
            if polls < max_polls:
                await w(BLE_WAKE, f"poll {polls + 1}")
                polls += 1
            await sleep(poll_every)
        raw = bytes(buf)
        log.exchanges.append({"label": f"BB 12 01 attempt {attempt + 1}",
                              "tx": BLE_DEVINFO.hex(), "polls": polls,
                              "rx": raw.hex() or None})
        if raw:
            return raw
        if attempt < MAX_RETRIES:
            log.info(f"no reply in {REPLY_TIMEOUT_S} s; one retry")
    return b""


def _ble_candidates(timeout: float) -> list[dict]:
    """PASSIVE scan only: no connection to anything (unlike ble.discover(verify=True),
    which writes READ_MEASUREMENT to every ffe0 advertiser)."""
    from bleak import BleakScanner

    async def go():
        found = await BleakScanner.discover(timeout=timeout, return_adv=True)
        out = []
        for dev, adv in found.values():
            uuids = [u.lower() for u in (adv.service_uuids or [])]
            if cr30_ble.FFE0_SERVICE not in uuids:
                continue
            out.append({"device": dev, "address": dev.address,
                        "name": adv.local_name or dev.name or "", "rssi": adv.rssi,
                        "fee7": any(u.startswith("0000fee7") for u in uuids)})
        return out
    return asyncio.run(go())


def run_ble(args) -> int:
    log = Log("ble")
    summary: dict = {}
    name = args.name
    if not name and not args.address and LAST_USB_ID.exists():
        try:
            name = json.loads(LAST_USB_ID.read_text(encoding="utf-8")).get(
                "second_id (AA 0A 01 @19) = BLE advertised name") or None
            if name:
                log.info(f"expecting BLE name {name!r} (second_id from the last usb run)")
        except Exception:      # noqa: BLE001
            name = None
    t = None
    try:
        log.info(f"passive scan {args.scan:.0f} s for ffe0 advertisers (nothing is sent)")
        cands = _ble_candidates(args.scan)
        for c in cands:
            log.info(f"  candidate {c['name']!r} {c['address']} rssi={c['rssi']} fee7={c['fee7']}")
        if args.address:
            pick = [c for c in cands if c["address"].lower() == args.address.lower()]
        elif name:
            pick = [c for c in cands if c["name"] == name]
        else:
            pick = [c for c in cands if c["fee7"]]
        if len(pick) != 1:
            log.info(f"REFUSED: need exactly one target, found {len(pick)}. "
                     "Pass --name <the CR30's id, printed by the usb mode> or --address. "
                     "If none: the phone app may hold it (it stops advertising), or it is off.")
            return 2
        target = pick[0]
        log.info(f"target {target['name']!r} {target['address']}")

        # ChromIQ's own BleTransport for connect / notifications / disconnect.
        # With an explicit target it does NOT run discover(), so nothing but
        # connect + start_notify happens in open().
        t = cr30_ble.BleTransport(target["name"] or None, address=target["address"],
                                  timeout=20.0)
        orig = t._on_notify

        def logged_notify(sender, data):
            log.rx(bytes(data), "notification")
            orig(sender, data)
        t._on_notify = logged_notify          # bound at start_notify time in open()

        log.info("connect + start_notify (ChromIQ BleTransport.open)")
        t.open()
        # Let any connect-time hello arrive and be logged before we ask.
        t._run(asyncio.sleep(0.5))
        if t._events:
            log.info(f"{len(t._events)} event frame(s) at connect (bb 01 ..), ignored")
        t._buf.clear()

        async def write(data: bytes) -> None:
            await t._client.write_gatt_char(cr30_ble.FFE1, data, response=False)

        raw = t._run(ble_exchange(write, t._buf, log))
        summary = {"transport": "ble", "name": target["name"],
                   "address": target["address"], **parse_devinfo(raw)}
        _print_summary(log, summary)
        return 0 if summary.get("checksum_ok") else 4
    except Exception as exc:                  # noqa: BLE001 — report it
        log.info(f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        if t is not None:
            try:
                log.info("stop_notify + disconnect (ChromIQ BleTransport.close)")
                t.close()
                log.info("disconnected")
            except Exception as exc:          # noqa: BLE001
                log.info(f"disconnect raised {type(exc).__name__}: {exc}")
            try:
                if t._loop is not None:
                    t._loop.close()
            except Exception:                 # noqa: BLE001
                pass
            try:
                time.sleep(2.0)
                again = _ble_candidates(6.0)
                seen = [c for c in again if c["address"] == summary.get("address")
                        or (summary.get("name") and c["name"] == summary.get("name"))]
                log.info("advertising again after disconnect: "
                         + ("YES" if seen else "NOT SEEN in 6 s (switch it off and on)"))
            except Exception as exc:          # noqa: BLE001
                log.info(f"re-advertise check failed: {exc}")
        log.close(summary)


# ------------------------------------------------------------------ helpers
def _print_summary(log: Log, summary: dict) -> None:
    log.info("=" * 20 + " SUMMARY " + "=" * 20)
    for k, v in summary.items():
        if k == "raw" and isinstance(v, dict):
            for kk, vv in v.items():
                log.info(f"  raw {kk}: {vv}")
        else:
            log.info(f"  {k}: {v}")


def dry_run() -> int:
    print("DRY RUN: nothing is opened, scanned or sent.\n")
    print("usb: opens each CH34x port ChromIQ would (DTR/RTS low), sends in order,")
    print("     stopping after the first if the model is not 'CR30':")
    for sub in IDENTITY_SUBS:
        print(f"  AA 0A {sub:02X} 00  ({len(USB_IDENTITY[sub])} B): {USB_IDENTITY[sub].hex(' ')}")
    print(f"  (each reply waited for up to {REPLY_TIMEOUT_S} s; at most {MAX_RETRIES} resend, on silence only)")
    print(f"  {USB_SKIP_REASON}\n")
    print("ble: passive scan, connect to exactly one target, start notifications on FFE1, then:")
    print(f"  wake      ({len(BLE_WAKE)} B): {BLE_WAKE.hex(' ')}")
    print(f"  devinfo   ({len(BLE_DEVINFO)} B): {BLE_DEVINFO.hex(' ')}")
    print(f"  polls     ({len(BLE_WAKE)} B): {BLE_WAKE.hex(' ')}  x at most 12, every 0.35 s, only while the reply is incomplete")
    print(f"  (reply window {REPLY_TIMEOUT_S} s; wake+devinfo resent once only if NOTHING came back)")
    print("  then stop_notify + disconnect, and a passive scan to confirm it advertises again.")
    print(f"\nvendor frame dataWrapper([187,18,1,0,0,0,0,0,255]) = {VENDOR_DEVINFO.hex(' ')}"
          f"  identical to ChromIQ ble.frame(0x12,0x01): {VENDOR_DEVINFO == BLE_DEVINFO}")
    return 0


# ----------------------------------------------------------------- selftest
def _synthetic_devinfo(code=793, category="CR30", serial="CM000X0000",
                       sw="V11.3.", hw="V10.0.0.0", neutral=0) -> bytes:
    """A reply built from the VENDOR'S PARSER, not from a device: no BB 12 01
    reply has ever been captured. Header bytes 2..4 are unknown and set to zero."""
    d = bytearray(REPLY_LEN)
    d[0], d[1] = 0xBB, 0x12
    d[5:7] = code.to_bytes(2, "little")
    for off, s in ((37, category), (67, serial), (97, sw), (127, hw)):
        b = s.encode(); d[off:off + len(b)] = b
    d[159] = neutral
    d[198] = 0xFF
    d[199] = sum(d[:-1]) & 0xFF
    return bytes(d)


def selftest() -> int:
    fails = 0

    def check(name, cond, detail=""):
        nonlocal fails
        print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
        fails += 0 if cond else 1

    _self_check()
    check("frames equal the reviewed literals and the vendor frame", True)

    # 1. USB: replay the recorded ChromIQ identity traffic through the same
    #    whitelist + logging + parser (EXP-CAL-001 human session: ChromIQ-framed
    #    requests, ffb3..ffb6, real replies with redacted id strings).
    cap = json.loads((RESEARCH / "captures/public/EXP-CAL-001-EXP-MEAS-001-human-session.json")
                     .read_text(encoding="utf-8"))
    steps = cap["phases"][0]["steps"]
    ex = [Exchange(bytes.fromhex(s["tx"]), bytes.fromhex(s["rx"]), s["label"])
          for s in steps if s["label"].startswith("AA 0A")][:4]
    log = Log("selftest", to_file=False)
    t = LoggedReplay(ex, log, strict=True)
    t.open()
    s = usb_identify(t, log)
    check("usb replay: strict byte-for-byte match of our requests", t.remaining == 0)
    check("usb: model CR30", s["model"] == "CR30", s["model"])
    check("usb: version_a V11.3.", s["software? version_a (AA 0A 01 @49)"] == "V11.3.")
    check("usb: version_b V10.0.0.0", s["hardware? version_b (AA 0A 02 @29)"] == "V10.0.0.0")
    check("usb: build 0.0.20231219", s["build (AA 0A 02 @5)"] == "0.0.20231219")
    check("usb: device code bytes 7..8 = 793",
          s["device code? (AA 0A 00 bytes 7..8 LE, HYPOTHESIS 793=CR30)"] == 793)

    # 1b. same against EXP-MAC-USB-001 replies (that probe used +1 request checksums,
    #     so the replay is non-strict on the request, strict on the reply).
    cap2 = json.loads((RESEARCH / "captures/public/EXP-MAC-USB-001-identity.json")
                      .read_text(encoding="utf-8"))
    ex2 = [Exchange(bytes.fromhex(p["tx"]), bytes.fromhex(p["rx"]))
           for p in cap2["trials"][0]["probes"]]
    t2 = LoggedReplay(ex2, Log("selftest", to_file=False), strict=False)
    t2.open()
    s2 = usb_identify(t2, t2.log)
    check("usb (EXP-MAC-USB-001 replies) decode identically",
          {k: v for k, v in s2.items() if k != "raw"} == {k: v for k, v in s.items() if k != "raw"})

    # 1c. a stranger CH340 gets ONE question only.
    stranger = bytearray(ex[0].response); stranger[39:43] = b"ABCD"
    stranger[59] = sum(stranger[:59]) % 256
    t3 = LoggedReplay([Exchange(ex[0].request, bytes(stranger))] + ex[1:],
                      Log("selftest", to_file=False))
    t3.open()
    try:
        usb_identify(t3, t3.log); ok = False
    except ConnectionError:
        ok = len(t3.sent) == 1
    check("usb: a non-CR30 answer stops after one frame", ok)

    # 2. whitelist refuses everything else, including near misses.
    for bad, mode in [(cr30_ble.READ_MEASUREMENT, "ble"), (cr30_ble.TRIGGER_UNSAFE, "ble"),
                      (cr30_ble.frame(0x12, 0x00), "ble"), (b"\x01\x01", "ble"),
                      (BLE_DEVINFO, "usb"), (Frame.build(0xBB, 0x12, 0x01, 0).to_bytes(), "usb"),
                      (Frame.build(0xAA, 0x0A, 0x04, 0).to_bytes(), "usb"),
                      (Frame.build(0xBB, 0x13, 0, 0, data=b"Check").to_bytes(), "usb")]:
        try:
            _guard(mode, bad); refused = False
        except NotWhitelisted:
            refused = True
        check(f"whitelist refuses {mode} {bad[:4].hex(' ')}..", refused)

    # 3. BLE parser + exchange against a fake link (synthetic reply, labelled so).
    rep = _synthetic_devinfo()
    p = parse_devinfo(rep)
    check("ble parse: synthetic 200-B reply decodes", p.get("checksum_ok") and
          p["serial @67"] == "CM000X0000" and p["softwareVersion @97"] == "V11.3." and
          p["hardwareVersion @127"] == "V10.0.0.0" and p["code (u16 LE @5; vendor DB: 793=CR30)"] == 793,
          json.dumps({k: v for k, v in p.items() if k != "raw"}))
    hello = bytes.fromhex("bb01000001900a1fff75")        # real BLE hello, EXP-BLE-011
    p2 = parse_devinfo(hello + rep)
    check("ble parse: a straggler before the reply does not shift offsets",
          p2.get("checksum_ok") and p2.get("offset") == 10)
    bad = bytearray(rep); bad[100] ^= 0xFF
    check("ble parse: corrupt reply is flagged, not trusted",
          parse_devinfo(bytes(bad)).get("checksum_ok") is False)
    check("ble parse: echo recognised", parse_devinfo(BLE_DEVINFO)["verdict"].startswith("ECHO"))
    check("ble parse: short reply is INCOMPLETE", parse_devinfo(rep[:120])["verdict"].startswith("INCOMPLETE"))

    class FakeLink:
        """Fragments the reply into 20-byte notifications after the 2nd poll."""
        def __init__(self, reply, silent_first=False):
            self.reply, self.sent, self.buf = reply, [], bytearray()
            self.silent_first, self.armed, self.polls_after = silent_first, False, 0
            self.t = 0.0

        async def write(self, data):
            self.sent.append(bytes(data))
            if data == BLE_DEVINFO:
                if self.silent_first:
                    self.silent_first = False; return
                self.armed, self.polls_after = True, 0
            elif self.armed:
                self.polls_after += 1
                if self.polls_after == 2:
                    for i in range(0, len(self.reply), 20):
                        self.buf.extend(self.reply[i:i + 20])
                    self.armed = False

        async def sleep(self, s):
            self.t += s

        def clock(self):
            return self.t

    for label, link in [("normal", FakeLink(rep)), ("silent once, then answers", FakeLink(rep, True)),
                        ("never answers", FakeLink(b""))]:
        lg = Log("selftest", to_file=False)
        raw = asyncio.run(ble_exchange(link.write, link.buf, lg, sleep=link.sleep, clock=link.clock))
        only_ok = all(x in ALLOWED["ble"] for x in link.sent)
        n_cmd = link.sent.count(BLE_DEVINFO)
        if label == "normal":
            check(f"ble exchange ({label}): reply complete, 1 command, only whitelisted bytes",
                  parse_devinfo(raw).get("checksum_ok") and n_cmd == 1 and only_ok,
                  f"sent {len(link.sent)} writes")
        elif label.startswith("silent"):
            check(f"ble exchange ({label}): exactly one retry",
                  parse_devinfo(raw).get("checksum_ok") and n_cmd == 2 and only_ok)
        else:
            check(f"ble exchange ({label}): gives up after 2 commands, bounded polls",
                  raw == b"" and n_cmd == 2 and only_ok and len(link.sent) <= 2 * (2 + 12),
                  f"{len(link.sent)} writes, {link.t:.1f} s simulated")

    print(f"\n{'ALL PASS' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", nargs="?", choices=["usb", "ble"])
    ap.add_argument("--dry-run", action="store_true", help="print the exact frames, touch nothing")
    ap.add_argument("--selftest", action="store_true", help="offline checks against recorded frames")
    ap.add_argument("--port", help="usb: a specific /dev/cu.* port (default: ChromIQ's CH34x discovery)")
    ap.add_argument("--name", help="ble: the CR30's advertised name (= second_id from the usb mode)")
    ap.add_argument("--address", help="ble: a specific peripheral address/UUID")
    ap.add_argument("--scan", type=float, default=10.0, help="ble: passive scan seconds (default 10)")
    args = ap.parse_args()
    _self_check()
    if args.dry_run:
        return dry_run()
    if args.selftest:
        return selftest()
    if args.mode == "usb":
        return run_usb(args)
    if args.mode == "ble":
        return run_ble(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
