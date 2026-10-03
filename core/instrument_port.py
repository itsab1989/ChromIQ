"""Which port will an ArgyllCMS instrument tool open, and is it one that hangs?

**EXCLUDING A PORT FROM THE SCAN DOES NOT STOP A TOOL FROM OPENING IT.**
``core/argyll_env.py`` sets ``ARGYLL_EXCLUDE_SERIAL_SCAN`` so that Argyll's
start-up identification scan leaves ``/dev/cu.Bluetooth-Incoming-Port`` alone.
That is the scan only. Measured 2026-10-03 with that port stuck in the kernel
(review of b3591886): with NO USB instrument attached, the port is number 1 in
Argyll's list, ChromIQ passes ``-c 1``, and the tool opens it to talk to the
instrument it expects there. ``spotread -v`` with the variable set sat in state
U, unkillable, minutes later. So Start Measurement or Read Single Patches with
nothing plugged in could hang the same way the scan did.

This module answers, BEFORE anything is launched and without opening any
port, "is port N of Argyll's list a system port that is never an instrument?",
and the launch paths refuse it and show the existing "No instrument found"
window instead. Nothing is opened to find out: the USB instruments come from
the IORegistry against Argyll's own match table
(:mod:`core.argyll_instruments`), the serial ports from the IORegistry's
callout devices, and Argyll's ordering is reproduced from its source.

ARGYLL'S LIST, from ``spectro/icoms.c`` ``icompaths_refresh_paths_sel`` and
``spectro/icoms_ux.c`` ``serial_get_paths`` (3.5.0):

1. the HID and USB devices that ``inst_usb_match`` recognises (every one an
   instrument);
2. then the serial ports, minus the ones Argyll ignores by name (``IrDA``,
   ``Dialup``, ``debug-console``, ``PDA-Sync``), **sorted**: ports the scan
   identified as an instrument first, then by name (``strcmp``).

A port the scan never probes (an excluded one) is never identified, so the
stuck port's position is fixed except for one thing: a probe-able port named
after it (a ``usbserial``/``usbmodem``/``JETI`` port, say ``/dev/cu.usbserial-X``
sorts after ``/dev/cu.Bluetooth-...``) moves ahead of it if a serial
instrument answers on it. Only the scan itself can know that, so in that case
this module says "cannot tell" and the launch goes ahead exactly as before:
**a real instrument is never refused on a guess.** The same holds whenever
the device lists cannot be read.

macOS only, where the stuck port was measured; elsewhere nothing is refused.
``tests/test_no_launch_opens_the_bluetooth_incoming_port.py`` holds it.
"""
from __future__ import annotations

import glob
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

from core.logger import get_logger

log = get_logger(__name__)

#: The ArgyllCMS tools (and ChromIQ's fork) that open an instrument port.
INSTRUMENT_TOOLS = ("chartread", "spotread", "chromiq-chartread")

#: Port names that are never a measuring instrument. The Bluetooth INCOMING
#: port is macOS's own listener; an outgoing Bluetooth serial port (a paired
#: SwatchMate Cube, say) has the device's name and is not matched.
#: "debug-console" Argyll already drops by name; listed so the rule says so.
SYSTEM_PORT_MARKERS = ("Bluetooth-Incoming-Port", "debug-console")

#: Ports ``serial_get_paths`` drops by name before anything else (icoms_ux.c).
_ARGYLL_IGNORED = ("IrDA", "Dialup", "debug-console", "PDA-Sync")

#: Names ``serial_get_paths`` treats as "fast serial", the ones its scan
#: opens to identify (icoms_ux.c).
_FAST_SERIAL = ("usbserial", "usbmodem", "Bluetooth", "JETI")


def is_system_port(path: str, platform: "str | None" = None) -> bool:
    """Is *path* a serial port that is never an instrument (and may hang)?"""
    from core.argyll_env import always_excluded_ports
    return (path in always_excluded_ports(platform)
            or any(m in path for m in SYSTEM_PORT_MARKERS))


# ---------------------------------------------------------------------------
# reading the machine (nothing is opened)
# ---------------------------------------------------------------------------
_CALLOUT = re.compile(r'"IOCalloutDevice"\s*=\s*"([^"]+)"')


def _parse_callouts(text: str) -> "list[str]":
    """``/dev/cu.*`` paths out of ``ioreg -c IOSerialBSDClient -l``. Pure text."""
    return list(dict.fromkeys(_CALLOUT.findall(text)))


def _macos_serial_ports() -> "list[str] | None":
    """The serial callout devices, from the IORegistry (where Argyll looks);
    ``/dev/cu.*`` when that cannot be read. None when neither can."""
    try:
        out = subprocess.run(
            ["/usr/sbin/ioreg", "-r", "-c", "IOSerialBSDClient", "-l", "-w", "0"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10, check=False,
            stdin=subprocess.DEVNULL).stdout
        found = _parse_callouts(out)
        if found:
            return found
    except Exception:          # noqa: BLE001 — fall back to the device files
        log.debug("ioreg serial list failed", exc_info=True)
    try:
        return sorted(glob.glob("/dev/cu.*"))
    except OSError:
        return None


def _probe() -> "tuple[int | None, list[str] | None]":
    """(how many Argyll USB instruments are attached, the serial ports)."""
    if sys.platform != "darwin":
        return None, None
    from core.argyll_instruments import attached_instrument_count
    return attached_instrument_count(), _macos_serial_ports()


#: Replaceable, so the suite never depends on what is plugged into the machine
#: it runs on (tests/conftest.py makes it "cannot tell" by default).
probe: "Callable[[], tuple[int | None, list[str] | None]]" = _probe


# ---------------------------------------------------------------------------
# the decision (pure)
# ---------------------------------------------------------------------------
def system_port_at(port: int, usb_count: "int | None",
                   serial_ports: "Sequence[str] | None", *,
                   excluded: "Sequence[str]" = (),
                   platform: "str | None" = None) -> "str | None":
    """The system port Argyll's ``-c port`` would open, or None.

    None means: an instrument, a port number past the end of the list (Argyll
    then says "No instrument at port N" and opens nothing), or "cannot tell".
    *excluded* is the ``ARGYLL_EXCLUDE_SERIAL_SCAN`` list (never probed, so
    never identified).
    """
    if usb_count is None or serial_ports is None or port < 1:
        return None
    if port <= usb_count:
        return None                              # a USB/HID instrument
    listed = sorted(p for p in serial_ports
                    if not any(x in p for x in _ARGYLL_IGNORED))
    for sp in (p for p in listed if is_system_port(p, platform)):
        # unidentified ports sort by name; an identified one goes first
        position = usb_count + 1 + listed.index(sp)
        could_overtake = [p for p in listed
                          if p > sp and not is_system_port(p, platform)
                          and p not in excluded
                          and any(f in p for f in _FAST_SERIAL)]
        if port == position and not could_overtake:
            return sp
        if could_overtake and position <= port <= position + len(could_overtake):
            log.info("instrument port %d may be %s or a serial instrument the "
                     "scan identifies (%s); launching as before", port, sp,
                     ", ".join(could_overtake))
            return None
    return None


def _port_number(args: "Sequence[str]") -> "int | None":
    """The ``-c`` value in *args* (``-c 2`` or ``-c2``); 1, Argyll's default,
    when there is none; None when it is not a number."""
    for i, a in enumerate(args):
        if a == "-c":
            v = args[i + 1] if i + 1 < len(args) else ""
        elif a.startswith("-c") and a[2:].isdigit():
            v = a[2:]
        else:
            continue
        return int(v) if v.isdigit() else None
    return 1


def opens_no_port(tool: str, args: "Sequence[str]") -> bool:
    """True when this launch opens no instrument port at all: the usage text
    (the scan only, which the exclusion covers), the engine's replay, or
    external values (``-xx``/``-xl``, ChromIQ supplies the readings)."""
    if not args or "-?" in args or "--replay" in args:
        return True
    name = Path(tool).name.lower().removesuffix(".exe")
    if name in ("chartread", "chromiq-chartread"):
        # chartread's -x takes its letter attached (-xx XYZ, -xl Lab); a bare
        # -x is a usage error. spotread's -x means something else entirely.
        return any(a in ("-xx", "-xl") for a in args)
    return False


def refused_port(tool: str, args: "Sequence[str]") -> "str | None":
    """For a launch of *tool* with *args*: the system port it would open, which
    must not be launched, or None (launch as before). Never raises."""
    try:
        name = Path(str(tool)).name.lower().removesuffix(".exe")
        if name not in INSTRUMENT_TOOLS or opens_no_port(name, args):
            return None
        port = _port_number(args)
        if port is None:
            return None
        usb, serial = probe()
        import os
        from core.argyll_env import EXCLUDE_VAR
        excluded = [x for x in os.environ.get(EXCLUDE_VAR, "")
                    .replace(",", ";").split(";") if x]
        found = system_port_at(port, usb, serial, excluded=excluded)
        if found:
            log.warning("not starting %s: instrument port %d is %s, which is "
                        "not an instrument (no ArgyllCMS instrument is "
                        "attached there)", name, port, found)
        return found
    except Exception:          # noqa: BLE001 — never block a launch on a guess
        log.debug("could not resolve the instrument port", exc_info=True)
        return None


def runner_refuses(runner: object, tool: str,
                   args: "Sequence[str]") -> "str | None":
    """The question :meth:`core.argyll_runner.ArgyllRunner.run` asks before
    every launch: :func:`refused_port`. A function of its own so the suite can
    make the runner stricter than the app (tests/conftest.py) without touching
    the managers' own check."""
    return refused_port(tool, args)
