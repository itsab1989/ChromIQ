#!/usr/bin/env python3
"""CR30 Bluetooth diagnostic — run this and send us the file it writes.

WHAT THIS IS FOR. ChromIQ can read a CR30 over Bluetooth, and that path has only
ever been run on one Mac. Nobody has run it on Windows or Linux. If your CR30
will not connect wirelessly, this script finds out WHERE it stops and writes a
small report.

SEND IT PRIVATELY -- a forum DM or an email to the developer, not a public post.
Nothing in it is secret, but a Bluetooth scan is a list of what is switched on
around you, and that belongs to you and to your neighbours rather than to a
thread. The script redacts everything that is not the instrument for the same
reason.

WHAT IT DOES, IN ORDER
  1. Says which operating system, Python and Bluetooth library you have.
  2. Lists EVERY Bluetooth Low Energy device it can see for 20 seconds.
  3. Marks any that advertise the `ffe0` service, which is what a CR30 uses.
  4. Offers to connect to those, list what they offer, and ask the instrument
     for its wavelength range -- the one question that identifies a CR30.

WHAT IT WILL NEVER DO
  * It never sends a calibration command. Nothing here can disturb your
    instrument's white or black reference.
  * It never asks the instrument to measure.
  * It only ever writes ONE kind of frame, the "read what you last measured"
    request, and only to a device that advertises the CR30's own service, and
    only after you say yes.

BEFORE YOU RUN IT
  * Switch the CR30 on and leave it awake -- press its button once if unsure.
    There is no Bluetooth on/off setting to find: on the unit this was
    developed against it is always on, from the moment it comes out of the box.
  * Keep an eye on the instrument's SCREEN while the script runs. An indicator
    appears there when a computer asks to connect, so the screen tells you
    whether the request is arriving at all.
  * You probably cannot "pair" a CR30 the way you pair headphones, and you do
    not need to: this connects to it directly. On the unit this was developed
    against there is no pairing step at all -- an indicator simply appears on
    the instrument's screen when a computer asks to connect.

    BUT IF IT DOES APPEAR in your system's "add a device" list, that is worth
    telling us, and so is what happens if you try. It would mean your computer
    can see the instrument perfectly well, which moves the problem somewhere
    else entirely.
  * Close ChromIQ, or anything else that might be holding the instrument.

HOW TO RUN IT (Windows)
    py -m pip install bleak
    py cr30_bluetooth_report.py

HOW TO RUN IT (macOS / Linux)
    python3 -m pip install bleak
    python3 cr30_bluetooth_report.py

The report is written next to this script as `cr30-bluetooth-report.txt`.
It contains your operating system and what your Bluetooth adapter could see.
Names and full addresses are REDACTED for every device except one that
advertises the CR30's own service -- a scan otherwise lists your phone, your
television and your neighbours', by name, and none of that helps anybody. Read
the file before you send it all the same.
"""
from __future__ import annotations

import asyncio
import datetime
import platform
import sys
from pathlib import Path

REPORT = Path(__file__).resolve().parent / "cr30-bluetooth-report.txt"
SCAN_SECONDS = 20.0

#: The service a CR30 advertises. Generic -- HM-10 style modules use it too,
#: which is why seeing it is a hint and not an answer.
FFE0 = "0000ffe0-0000-1000-8000-00805f9b34fb"
FFE1 = "0000ffe1-0000-1000-8000-00805f9b34fb"

#: "Give me the measurement you are already holding." The ONLY frame this script
#: sends. It does not make the instrument measure and cannot calibrate it.
READ_MEASUREMENT = bytes([0xBB, 0x02, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xCD])

_lines: list[str] = []


def say(text: str = "") -> None:
    print(text)
    _lines.append(text)


def ask(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower().startswith("y")
    except (EOFError, KeyboardInterrupt):
        return False


async def main() -> int:
    say("CR30 Bluetooth report")
    say("=" * 60)
    say(f"when      : {datetime.datetime.now().isoformat(timespec='seconds')}")
    say(f"system    : {platform.system()} {platform.release()} ({platform.machine()})")
    say(f"python    : {sys.version.split()[0]}")
    try:
        import bleak                               # noqa: F401
        # NOT `bleak.__version__` -- some releases do not define it, and asking
        # for it raised AttributeError, which this reported as "NOT INSTALLED".
        # It would have sent the reader off to install a library they already
        # had. The import is the test; the version is a nicety.
        try:
            from importlib.metadata import version as _v
            say(f"bleak     : {_v('bleak')}")
        except Exception:                          # noqa: BLE001
            say("bleak     : installed (version unknown)")
    except ImportError as exc:
        say(f"bleak     : NOT INSTALLED ({exc})")
        say("")
        say("Install it and run this again:   py -m pip install bleak")
        REPORT.write_text("\n".join(_lines), encoding="utf-8")
        return 2
    from bleak import BleakClient, BleakScanner

    say("")
    say(f"Scanning for {SCAN_SECONDS:.0f} seconds. Keep the CR30 switched on and near.")
    say("")
    try:
        found = await BleakScanner.discover(timeout=SCAN_SECONDS,
                                            return_adv=True)
    except Exception as exc:                       # noqa: BLE001
        say(f"THE SCAN ITSELF FAILED: {type(exc).__name__}: {exc}")
        say("")
        say("That is a finding in itself — it means Bluetooth could not be")
        say("started at all, rather than the CR30 not answering. On Windows,")
        say("check that Bluetooth is switched on in Settings and that this")
        say("terminal is allowed to use it.")
        REPORT.write_text("\n".join(_lines), encoding="utf-8")
        return 1

    items = list(found.items()) if isinstance(found, dict) else [
        (d.address, (d, None)) for d in found]
    say(f"{len(items)} Bluetooth LE device(s) visible:")
    say("")
    candidates = []
    for addr, pair in items:
        dev, adv = pair if isinstance(pair, tuple) else (pair, None)
        uuids = list(getattr(adv, "service_uuids", []) or [])
        name = getattr(adv, "local_name", None) or getattr(dev, "name", None) or "(no name)"
        rssi = getattr(adv, "rssi", None)
        is_cand = any(u.lower().startswith("0000ffe0") for u in uuids)
        # NAMES ARE REDACTED UNLESS THE DEVICE COULD BE THE INSTRUMENT.
        #
        # This report is meant to be posted in a forum thread. A plain scan
        # lists the reader's phone, their tablet, their television and their
        # neighbours' -- by name, which is often a person's name. None of that
        # helps us: what matters is whether ANYTHING advertises ffe0. So
        # everything else is counted and described, not identified.
        if is_cand:
            say(f"  {name:28s} {addr}  rssi={rssi}"
                "  <-- advertises ffe0, could be a CR30")
            if uuids:
                say(f"      services: {', '.join(uuids)}")
            candidates.append((name, addr))
        else:
            shown = "(named device, hidden)" if name != "(no name)" else "(no name)"
            say(f"  {shown:28s} …{str(addr)[-6:]}  rssi={rssi}"
                f"  services={len(uuids)}")

    say("")
    if not candidates:
        say("NO DEVICE ADVERTISING ffe0 WAS SEEN.")
        say("(Send this file privately — a DM or an email — not a public post.)")
        say("")
        say("That is the single most useful thing this report can say. It means")
        say("your computer never saw the instrument offering the service ChromIQ")
        say("looks for — so the problem is before ChromIQ, not inside it. Worth")
        say("checking, in this order:")
        say("  * is the CR30 awake? press its button once and run this again.")
        say("    On the unit we developed against there is NO Bluetooth on/off")
        say("    control at all -- it is on out of the box and cannot be turned")
        say("    off -- so an instrument that is powered and awake should be")
        say("    advertising. Sleep is the likeliest reason it is not.")
        say("  * is it already connected to the phone app, or to another")
        say("    computer? it accepts ONE connection at a time and stops")
        say("    advertising while something holds it.")
        say("  * is Bluetooth switched on in Windows, and is this terminal")
        say("    allowed to use it? Windows can refuse quietly.")
        say("  * WATCH THE INSTRUMENT'S OWN SCREEN while this runs. On the unit")
        say("    we developed against, an indicator appears on the display when")
        say("    a computer asks to connect. If nothing ever appears there, the")
        say("    request is not reaching the instrument at all -- which points")
        say("    at the computer's Bluetooth rather than at the CR30.")
        REPORT.write_text("\n".join(_lines), encoding="utf-8")
        print(f"\nReport written to: {REPORT}")
        return 0

    say(f"{len(candidates)} candidate(s) advertise the CR30's service.")
    say("")
    print("The next step CONNECTS to a candidate and asks it what wavelengths")
    print("it reports. It cannot make it measure and cannot calibrate it.")
    if not ask("Try that now?"):
        say("(the user chose not to connect)")
        REPORT.write_text("\n".join(_lines), encoding="utf-8")
        print(f"\nReport written to: {REPORT}")
        return 0

    for name, addr in candidates:
        say("")
        say(f"--- connecting to {name} ({addr})")
        try:
            async with BleakClient(addr, timeout=20.0) as client:
                say("    connected")
                chars = []
                for svc in client.services:
                    for ch in svc.characteristics:
                        chars.append(f"{ch.uuid} [{','.join(ch.properties)}]")
                say(f"    characteristics: {len(chars)}")
                for c in chars:
                    say(f"      {c}")
                got: list[bytes] = []

                def _on_notify(_h, data: bytearray) -> None:
                    got.append(bytes(data))

                try:
                    await client.start_notify(FFE1, _on_notify)
                except Exception as exc:           # noqa: BLE001
                    say(f"    could not subscribe to ffe1: {type(exc).__name__}: {exc}")
                    continue
                await client.write_gatt_char(FFE1, READ_MEASUREMENT,
                                             response=False)
                await asyncio.sleep(3.0)
                await client.stop_notify(FFE1)
                blob = b"".join(got)
                say(f"    {len(blob)} bytes came back")
                if blob:
                    say(f"    first 32 bytes: {blob[:32].hex(' ')}")
                    hdr = blob.find(bytes([0xBB, 0x02, 0x10]))
                    if hdr >= 0 and len(blob) - hdr >= 8:
                        b = blob[hdr:hdr + 8]
                        start = (b[4] << 8) | b[5]
                        say(f"    axis: start {start} nm, step {b[6]} nm, "
                            f"{b[7]} bands")
                        if (start, b[6], b[7]) == (400, 10, 31):
                            say("    THIS IS A CR30, and it answered correctly.")
                        else:
                            say("    it answered, but not with a CR30's axis.")
                    else:
                        say("    the reply was not in the shape a CR30 sends.")
                else:
                    say("    it connected but said nothing — worth reporting.")
        except Exception as exc:                   # noqa: BLE001
            say(f"    FAILED: {type(exc).__name__}: {exc}")

    REPORT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\nReport written to: {REPORT}")
    print("Please send that file to the developer PRIVATELY — a forum DM or")
    print("an email, rather than a public post. It says where this stops.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)
