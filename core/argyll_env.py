"""The environment every ArgyllCMS tool, and ChromIQ's own chart-reading
helper, is started in: Argyll's serial-port scan exclusion.

**A BLUETOOTH PORT THAT DOES NOT ANSWER HANGS EVERY ARGYLL TOOL AT START.**
Measured 2026-10-03 on macOS 27: Argyll lists the serial ports before it looks
for an instrument (``serial_get_paths``, spectro/icoms_ux.c), treats any port
whose name contains "Bluetooth" as a "fast serial" port, and OPENS it to ask
what is on the other end (``fast_ser_dev_type``). That open is blocking
(O_RDWR, no O_NONBLOCK), and on ``/dev/cu.Bluetooth-Incoming-Port`` it never
returned: ``chromiq-chartread`` sat in state U inside ``open``, unkillable,
and stock ``chartread`` enumerates the same way. Even the usage text lists the
instruments, so ``chromiq-chartread`` with no arguments hung too.

Argyll's own remedy is ``ARGYLL_EXCLUDE_SERIAL_SCAN`` (spectro/icoms.c,
``create_fserexcl``): exact port paths separated by ';' or ','. An excluded
port is still listed, but the scan never opens it. Verified the same day with
the port stuck: with the variable set the helper printed its usage at once;
without it, it hung.

So on macOS ``/dev/cu.Bluetooth-Incoming-Port`` is ALWAYS excluded, whatever
the "Faster instrument connection" preference says, because here it is not a
speed-up but the difference between starting and hanging. Argyll on macOS
lists callout devices only (``kIOCalloutDeviceKey``, ``/dev/cu.*``), so there
is no ``/dev/tty.*`` twin to add. Real instrument ports (usbserial, usbmodem,
JETI) are never excluded, and a value the user set is kept, ours appended.

The preference still governs the wider list: every other phantom port on the
machine (debug consoles, paired devices), each ~2 s of probing per start.

:func:`argyll_env` builds an explicit ``env=``;
:func:`install_in_process_environment` puts the always-excluded ports into
``os.environ`` at start-up (``main()``), so a ``subprocess.run`` that passes no
``env=`` inherits them. ``tests/test_every_argyll_launch_skips_the_stuck_
serial_port.py`` holds every launch path to it.
"""
from __future__ import annotations

import os
import sys
from typing import Mapping

from core.logger import get_logger

log = get_logger(__name__)

#: the variable Argyll reads (spectro/icoms.c)
EXCLUDE_VAR = "ARGYLL_EXCLUDE_SERIAL_SCAN"

#: ports excluded on every launch on macOS, preference or not: opening them
#: can block in the kernel for ever (see the module docstring)
DARWIN_ALWAYS_EXCLUDED: "tuple[str, ...]" = ("/dev/cu.Bluetooth-Incoming-Port",)


# ---------------------------------------------------------------------------
# Fast instrument connection: skip Argyll's slow serial-port probe (macOS)
#
# Before opening a USB spectro, Argyll probes every serial port it can see at
# several baud rates (~2 s each). On macOS a phantom port like
# /dev/cu.Bluetooth-Incoming-Port is almost always present, adding ~10 s to
# every measurement start. Argyll's ARGYLL_EXCLUDE_SERIAL_SCAN env var takes a
# ';'-separated exact-match list of port paths to skip — we fill it with the
# phantom ports so a USB instrument is reached immediately, while KEEPING real
# USB-serial adapters (a serial SpectroScan, etc.) so nothing breaks.
# ---------------------------------------------------------------------------

#: Substrings of a macOS /dev/cu.* name (lower-cased) that mark a REAL serial
#: instrument port, never excluded, so serial instruments still work. "jeti"
#: is the third name Argyll itself treats as an instrument port (icoms_ux.c).
_REAL_SERIAL_HINTS = ("usbserial", "usbmodem", "jeti")

#: Windows SERIALCOMM value-name prefixes that mark a Bluetooth serial port —
#: never a ChromIQ measurement instrument, so safe to skip (the direct analog of
#: excluding /dev/cu.Bluetooth-* on macOS). USB-serial adapters (VCP/USBSER, e.g.
#: a SpectroScan bridge) are deliberately NOT matched, so real serial instruments
#: still work. These are exactly the prefixes Argyll itself tags as ``btserial``
#: (see spectro/icoms_nt.c), so our exclusion can never disagree with its scan.
_WIN_BLUETOOTH_PREFIXES = ("BtPort", "BthModem")


def _phantom_serial_ports(candidates: list[str]) -> list[str]:
    """From /dev/cu.* candidates, the phantom ports that are never a measurement
    instrument (Bluetooth, debug consoles, paired devices) — everything that is
    NOT a real USB-serial adapter. Pure/side-effect-free for testing."""
    return sorted(
        p for p in candidates
        if not any(h in os.path.basename(p).lower() for h in _REAL_SERIAL_HINTS))


def _windows_bluetooth_com_ports(entries: "list[tuple[str, str]]") -> list[str]:
    """From ``(value_name, com_port)`` rows of HKLM\\...\\SERIALCOMM, the COM
    ports that are Bluetooth serial ports (never an instrument). Argyll keys a
    port's type off the leaf of its registry value name; we apply the identical
    rule (``BtPort*`` / ``BthModem*``), keeping every USB-serial adapter
    (``VCP*`` / ``USBSER*``) and native port. Pure/side-effect-free for
    testing."""
    ports: list[str] = []
    for name, com in entries:
        leaf = name.rsplit("\\", 1)[-1]
        if com and any(leaf.startswith(pfx) for pfx in _WIN_BLUETOOTH_PREFIXES):
            if com not in ports:
                ports.append(com)
    return sorted(ports)


def _read_serialcomm() -> "list[tuple[str, str]]":
    """Enumerate ``HKLM\\HARDWARE\\DEVICEMAP\\SERIALCOMM`` as ``(value_name,
    com_port)`` rows — the exact key Argyll reads. Empty when the key is absent
    (the common case: no serial ports) or unreadable. Windows-only; never
    raises."""
    try:
        import winreg
    except ImportError:  # pragma: no cover — non-Windows
        return []
    rows: list[tuple[str, str]] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                except OSError:  # ERROR_NO_MORE_ITEMS — end of the value list
                    break
                rows.append((name, str(value)))
                i += 1
    except OSError:  # key absent / unreadable — nothing to exclude
        return []
    return rows


def argyll_serial_exclusion_ports() -> list[str]:
    """The phantom serial ports to exclude from Argyll's scan on this machine.

    macOS: modern Macs have NO built-in serial port — every real serial
    instrument is on a USB-serial adapter (usbserial/usbmodem) — so excluding
    every OTHER /dev/cu.* (Bluetooth, debug consoles, paired devices) is both
    safe and complete.

    Linux: conservative. Only the Bluetooth ``/dev/rfcomm*`` ports are certainly
    not instruments. Native ``/dev/ttyS*`` ports (and USB adapters ttyUSB/ttyACM)
    are left completely untouched, so a real serial instrument can never be
    excluded.

    Windows: only Bluetooth COM ports. Argyll lists serial ports from
    ``HKLM\\HARDWARE\\DEVICEMAP\\SERIALCOMM`` and probes each fast/virtual one for
    ~2 s; a paired Bluetooth device (``BthModem*`` / ``BtPort*``) is never an
    instrument, so its COM port is skipped. USB-serial adapters (``VCP*`` /
    ``USBSER*``, e.g. a SpectroScan) and native ports are always kept. A machine
    with no serial ports (the common case) excludes nothing."""
    import glob
    try:
        if sys.platform == "darwin":
            return _phantom_serial_ports(glob.glob("/dev/cu.*"))
        if sys.platform.startswith("linux"):
            return sorted(glob.glob("/dev/rfcomm*"))
        if sys.platform == "win32":
            return _windows_bluetooth_com_ports(_read_serialcomm())
    except OSError:  # pragma: no cover — enumeration must never block a launch
        return []
    return []


def merged_serial_exclusion(existing: "str | None",
                            ports: "list[str] | None" = None) -> "str | None":
    """The value for ARGYLL_EXCLUDE_SERIAL_SCAN: our phantom ports merged with
    (and never dropping) anything the user already set. ``None`` when there is
    nothing to exclude. *ports* defaults to :func:`argyll_serial_exclusion_ports`
    (injectable for tests)."""
    if ports is None:
        ports = argyll_serial_exclusion_ports()
    items = [x for x in (existing or "").replace(",", ";").split(";") if x]
    for p in ports:
        if p not in items:
            items.append(p)
    return ";".join(items) if items else None



def always_excluded_ports(platform: "str | None" = None) -> "list[str]":
    """The ports excluded on every launch on *platform*, preference or not."""
    platform = sys.platform if platform is None else platform
    return list(DARWIN_ALWAYS_EXCLUDED) if platform == "darwin" else []


def serial_exclusion_value(existing: "str | None", *, phantoms: bool = True,
                           platform: "str | None" = None) -> "str | None":
    """The ARGYLL_EXCLUDE_SERIAL_SCAN value for a launch: *existing* (the
    user's, never dropped), then the always-excluded ports, then, when
    *phantoms* (the "Faster instrument connection" preference), every phantom
    port on this machine. ``None`` when there is nothing at all to set."""
    ports = always_excluded_ports(platform)
    if phantoms:
        try:
            found = argyll_serial_exclusion_ports()
        except Exception:  # noqa: BLE001 - enumeration must never block a launch
            log.debug("serial port enumeration failed", exc_info=True)
            found = []
        ports += [p for p in found if p not in ports]
    value = merged_serial_exclusion(existing, ports)
    _log_once(value)
    return value


_LOGGED: "set[str]" = set()


def _log_once(value: "str | None") -> None:
    """One debug line per distinct value, not one per launch."""
    if value and value not in _LOGGED:
        _LOGGED.add(value)
        log.debug("Argyll tools start with %s=%s", EXCLUDE_VAR, value)


def argyll_env(base: "Mapping[str, str] | None" = None, *,
               phantoms: bool = True) -> "dict[str, str]":
    """A full environment for an Argyll tool or the chart-reading helper:
    *base* (this process's environment by default) with the serial exclusion
    merged onto whatever *base* already sets for it."""
    env = dict(os.environ if base is None else base)
    value = serial_exclusion_value(env.get(EXCLUDE_VAR), phantoms=phantoms)
    if value:
        env[EXCLUDE_VAR] = value
    return env


def install_in_process_environment(*, phantoms: bool = False) -> "str | None":
    """Merge the exclusion into ``os.environ``, so every child this process
    starts without an explicit ``env=`` inherits it. Only the always-excluded
    ports by default: the preference-governed phantom list is added per launch
    by :class:`core.argyll_runner.ArgyllRunner`, which reads the preference.
    Idempotent; returns the value now set (or None)."""
    value = serial_exclusion_value(os.environ.get(EXCLUDE_VAR),
                                   phantoms=phantoms)
    if value:
        os.environ[EXCLUDE_VAR] = value
    return value
