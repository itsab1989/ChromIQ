# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""What the operating system says about the table and the instrument, per system (build step 6).

Read only, always: nothing here opens, claims or writes to a device, and nothing ends or starts a
program. Only USB vendor and product numbers are kept (never a serial number, never a device
name), and of a process only its program name.

Per system (the owner's ruling: the drive ships on macOS, Windows and Linux):

==================  ===================================  =====================================
check               macOS                                Windows / Linux
==================  ===================================  =====================================
instrument          ``ioreg`` device entries (tester     Windows: cfgmgr32's list of present USB
(exactly one        0.5.1's fix: interface entries are   device instances (no USB library; the
0971:2000, no       not devices)                         ARM64 build has no libusb-1.0). Linux:
other instrument)                                        pyusb through ChromIQ's own libusb
                                                         (core.usb_library.backend), the cached
                                                         device descriptors only
who holds the       ``ioreg`` UsbExclusiveOwner /        Linux: sysfs names the kernel driver
table               IOUserClientCreator (tester)         bound to the table's interface, and
                                                         /proc names the programs holding its
                                                         usbfs node (as far as this user may
                                                         read). Windows: CANNOT TELL (it offers
                                                         no such list without extra tools); a
                                                         wrong driver shows when the claim fails
i1Profiler running  ``pgrep`` (tester)                   Windows: ``tasklist`` by image name;
                                                         Linux: CANNOT TELL
==================  ===================================  =====================================

Every check answers a :class:`Check` with a named state; "cannot_tell" is a state of its own (the
later UI words it), never a guess.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

from . import reader as rd
from . import session_table as tbl

I1PRO_IDS = rd.I1PRO_IDS
TABLE_IDS = rd.TABLE_IDS


def system_of(platform: "str | None" = None) -> str:
    p = platform or sys.platform
    if p == "darwin":
        return "macos"
    if p == "win32":
        return "windows"
    if p.startswith("linux"):
        return "linux"
    return "other"


@dataclass(frozen=True)
class Check:
    state: str
    detail: dict = field(default_factory=dict)


# ---- the USB devices, ids only ------------------------------------------------------------

def devices_from_pyusb(found) -> "list[dict]":
    """pyusb device objects -> the reader's device records (ids and hub flag only; the
    descriptor pyusb caches at enumeration, no device is opened)."""
    out = []
    for dev in found:
        v, p = getattr(dev, "idVendor", None), getattr(dev, "idProduct", None)
        if not isinstance(v, int) or not isinstance(p, int):
            continue
        out.append({"vid": v, "pid": p, "place": None,
                    "hub": getattr(dev, "bDeviceClass", None) == 9, "interfaces": 0})
    return out


def devices_from_instance_ids(instance_ids) -> "list[dict] | None":
    r"""Windows: cfgmgr32's present USB device INSTANCE ids -> the reader's device records.

    2026-11-18 (the owner: "many modern pcs use arm processors so this should work for them"):
    the ARM64 build has no libusb-1.0 to list devices with, and Windows answers the same question
    without any USB library. One record per INSTANCE, never per (vid, pid), so two i1Pro 2 stay
    two and the check still says "several instruments". Composite children
    (``USB\VID_0971&PID_2000&MI_00\...``) are interfaces of a device already counted, and ids
    without VID/PID (``USB\ROOT_HUB30\...``) are hubs: both skipped. ``hub`` is False for the
    rest: a hub carries no instrument vendor id, so `_is_other_instrument` cannot mistake one.
    None stays None (the list could not be read: cannot tell)."""
    if instance_ids is None:
        return None
    from core.usb_driver_installer import usb_ids_in_instance
    out = []
    for one in sorted(str(i) for i in instance_ids):
        parts = one.split("\\")
        if len(parts) < 2 or "&MI_" in parts[1].upper():
            continue
        ids = usb_ids_in_instance(one)
        if ids is None:
            continue
        try:
            vid, pid = int(ids[0], 16), int(ids[1], 16)
        except ValueError:
            continue
        out.append({"vid": vid, "pid": pid, "place": None, "hub": False, "interfaces": 0})
    return out


def list_devices(system: str, backend=None, ioreg_roots=None, pyusb_find=None,
                 instance_ids=None) -> "list[dict] | None":
    """Every USB device once, as the reader counts them; None when the system's list cannot be
    read. *ioreg_roots* / *pyusb_find* / *instance_ids* are for tests (recorded answers, no
    device). Windows lists through cfgmgr32 (`devices_from_instance_ids`), on x64 and ARM64
    alike, and never through a USB library."""
    if system == "macos":
        return rd.usb_devices(ioreg_roots)
    if system == "windows":
        if instance_ids is None:
            try:
                from core.usb_driver_installer import present_usb_instance_ids
                instance_ids = present_usb_instance_ids()
            except Exception:      # noqa: BLE001 - the list could not be read: cannot tell
                return None
        return devices_from_instance_ids(instance_ids)
    if system == "linux":
        try:
            if pyusb_find is None:
                if backend is None:
                    return None
                import usb.core
                found = list(usb.core.find(find_all=True, backend=backend))
            else:
                found = list(pyusb_find())
        except Exception:      # noqa: BLE001 - the list could not be read: cannot tell
            return None
        return devices_from_pyusb(found)
    return None


def instrument_check(devices) -> Check:
    """Exactly one i1Pro-family instrument (0971:2000, shared by the i1Pro and the i1Pro 2) and
    no other measuring instrument; the helper names the model before any reading (step 7)."""
    if devices is None:
        return Check("cannot_tell", {"why": "the system's list of USB devices could not be read"})
    pros = [d for d in devices if (d["vid"], d["pid"]) == I1PRO_IDS]
    others = sorted({f"{d['vid']:04x}:{d['pid']:04x}" for d in devices
                     if rd._is_other_instrument(d)})
    tables = sum(1 for d in devices if (d["vid"], d["pid"]) == TABLE_IDS)
    detail = {"i1pro_devices": len(pros), "other_instruments": others, "tables": tables}
    if not pros:
        return Check("no_instrument", detail)
    if len(pros) > 1:
        return Check("several_instruments", detail)
    if others:
        return Check("other_instrument", detail)
    return Check("ok", detail)


# ---- who holds the table ----------------------------------------------------------------

def holders_macos(entries: "list[str] | None" = None) -> Check:
    entries = tbl.usb_holders() if entries is None else entries
    if any(e.startswith("(") for e in entries):
        return Check("cannot_tell", {"why": "macOS's list could not be read"})
    names = []
    for e in entries:
        label, _, rest = e.partition(": ")
        name = re.sub(r" \(pid \d+\)$", "", rest)
        if name != "this program":
            names.append({"how": label, "program": name})
    return Check("held" if names else "nobody_listed", {"programs": names})


_HEX4 = re.compile(r"[0-9a-fA-F]{4}")


def _read(path: str) -> "str | None":
    try:
        with open(path, encoding="ascii", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return None


def holders_linux(sysfs: str = "/sys/bus/usb/devices", proc: str = "/proc") -> Check:
    """The kernel driver bound to the table's interface (sysfs), and the programs that hold its
    usbfs node open (/proc, as far as this user may read)."""
    try:
        names = sorted(os.listdir(sysfs))
    except OSError:
        return Check("cannot_tell", {"why": "sysfs could not be read"})
    found = []
    for n in names:
        if ":" in n:
            continue
        v, p = _read(os.path.join(sysfs, n, "idVendor")), _read(os.path.join(sysfs, n, "idProduct"))
        if v and p and _HEX4.fullmatch(v) and _HEX4.fullmatch(p) and \
                (int(v, 16), int(p, 16)) == TABLE_IDS:
            found.append(n)
    if len(found) != 1:
        return Check("cannot_tell", {"why": f"{len(found)} tables in sysfs"})
    dev = found[0]
    drivers = []
    try:
        for n in sorted(os.listdir(sysfs)):
            if n.startswith(dev + ":"):
                link = os.path.join(sysfs, n, "driver")
                if os.path.islink(link):
                    drivers.append(os.path.basename(os.readlink(link)))
    except OSError:
        return Check("cannot_tell", {"why": "sysfs could not be read"})
    busnum, devnum = _read(os.path.join(sysfs, dev, "busnum")), _read(os.path.join(sysfs, dev,
                                                                                   "devnum"))
    programs, complete = [], True
    if busnum and devnum and busnum.isdigit() and devnum.isdigit():
        node = f"/dev/bus/usb/{int(busnum):03d}/{int(devnum):03d}"
        try:
            pids = [d for d in os.listdir(proc) if d.isdigit()]
        except OSError:
            pids, complete = [], False
        for pid in pids:
            fd_dir = os.path.join(proc, pid, "fd")
            try:
                fds = os.listdir(fd_dir)
            except OSError:
                complete = False
                continue
            for fd in fds:
                try:
                    if os.readlink(os.path.join(fd_dir, fd)) == node:
                        if int(pid) != os.getpid():
                            name = _read(os.path.join(proc, pid, "comm")) or "?"
                            programs.append(name[:40])
                        break
                except OSError:
                    continue
    else:
        complete = False
    detail = {"kernel_drivers": [d for d in drivers if d != "usbfs"], "programs": programs,
              "complete": complete}
    if detail["kernel_drivers"]:
        return Check("kernel_driver_bound", detail)
    if programs:
        return Check("held", detail)
    return Check("nobody_listed" if complete else "cannot_tell", detail)


def holders_check(system: str) -> Check:
    if system == "macos":
        return holders_macos()
    if system == "linux":
        return holders_linux()
    return Check("cannot_tell", {"why": f"{system} offers no list of who holds a USB device "
                                        "without extra tools"})


# ---- i1Profiler ----------------------------------------------------------------------------

def _run(args) -> "subprocess.CompletedProcess | None":
    try:
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None


def i1profiler_running(system: str, run=_run) -> "bool | None":
    """True / False, or None when this system cannot tell. Looks only, ends nothing."""
    if system == "macos":
        a = run(["pgrep", "-x", "-i", "i1Profiler"])
        b = run(["pgrep", "-f", "i1Profiler.app/Contents/MacOS"])
        if a is None or b is None:
            return None
        return bool(a.stdout.strip()) or bool(b.stdout.strip())
    if system == "windows":
        r = run(["tasklist", "/FI", "IMAGENAME eq i1Profiler.exe", "/FO", "CSV", "/NH"])
        if r is None or r.returncode != 0:
            return None
        return '"i1profiler.exe"' in r.stdout.lower()
    return None


# ---- everything before the table is opened ---------------------------------------------------

def table_driver_check(system: str, state_now=None) -> Check:
    """Windows only (owner's ruling of 2026-11-17): which driver the table has. "libusb0" =
    libusb-win32, installed by ChromIQ's installer on the person's explicit choice: the job can
    open it; "none" / "vendor_driver" (X-Rite's or another, i1Profiler's way) / "cannot_tell".
    Elsewhere "not_applicable" (macOS and Linux reach it through libusb-1.0 as it is).
    UNTESTED ON REAL WINDOWS HARDWARE."""
    if system != "windows":
        return Check("not_applicable")
    if state_now is None:
        import core.usb_driver_installer as inst
        state_now = inst.table_driver_state_now
    state, detail = state_now()
    return Check(state, dict(detail))


def instrument_driver_check(system: str, connected=None) -> Check:
    """Windows only (4.3.46, the owner's ruling of 2026-11-18): whether the i1Pro 2 (0971:2000,
    its own USB device in the table's arm) has the libusb-win32 driver ArgyllCMS reads it
    through. "libusb0" = it has; "none" = it is connected without it (X-Rite's driver, WinUSB or
    none); "not_seen" = not connected (the instrument check says that); elsewhere
    "not_applicable". *connected* is `core.usb_driver_installer.enumerate_connected` (tests).
    Read only. UNTESTED ON REAL WINDOWS HARDWARE WITH A TABLE."""
    if system != "windows":
        return Check("not_applicable")
    try:
        if connected is None:
            import core.usb_driver_installer as inst
            connected = inst.enumerate_connected
        pros = [d for d in connected() if (d.vid, d.pid) == ("0971", "2000")]
    except Exception as exc:      # noqa: BLE001 - read only: cannot tell, the reader decides
        return Check("cannot_tell", {"why": type(exc).__name__})
    if not pros:
        return Check("not_seen")
    return Check("libusb0" if all(d.has_winusb for d in pros) else "none")


def x64_build_on_arm64(system: str) -> bool:
    """An x64 ChromIQ running under emulation on a Windows for ARM PC, the one combination that
    cannot drive the table (it cannot load the ARM64 libusb0.dll the driver installs there):
    no driver install is offered there, and the message says to use the ARM64 version. The ARM64
    build on that PC is NOT this (2026-11-18, the owner: Windows on ARM shall be supported):
    decided by the process (`core.usb_library.table_drive_impossible_here`)."""
    if system != "windows":
        return False
    try:
        import core.usb_library as usb_library
        return bool(usb_library.table_drive_impossible_here())
    except Exception:      # noqa: BLE001 - cannot tell: the existing checks decide
        return False


@dataclass(frozen=True)
class Preflight:
    system: str
    usb: dict
    instrument: Check
    holders: Check
    i1profiler: "bool | None"
    table_driver: Check = Check("not_applicable")
    instrument_driver: Check = Check("not_applicable")
    x64_on_arm64: bool = False

    def as_dict(self) -> dict:
        return {"system": self.system, "usb": self.usb,
                "instrument": {"state": self.instrument.state, **self.instrument.detail},
                "holders": {"state": self.holders.state, **self.holders.detail},
                "i1profiler_running": self.i1profiler,
                "table_driver": {"state": self.table_driver.state, **self.table_driver.detail},
                "instrument_driver": {"state": self.instrument_driver.state,
                                      **self.instrument_driver.detail},
                "x64_on_arm64": self.x64_on_arm64}


def preflight(platform: "str | None" = None) -> Preflight:
    """The read-only checks before the table is opened (nothing is opened or sent)."""
    import core.usb_library as usb_library
    system = system_of(platform)
    backend = usb_library.backend() if system == "linux" else None
    devices = list_devices(system, backend=backend)
    return Preflight(system, usb_library.diagnostics(), instrument_check(devices),
                     holders_check(system), i1profiler_running(system),
                     table_driver_check(system), instrument_driver_check(system),
                     x64_build_on_arm64(system))


def instrument_now(platform: "str | None" = None) -> Check:
    """Step 7: the instrument check alone, again before every start of the reader (the tester
    checked before each reader too): exactly one 0971:2000 and no other measuring instrument.
    Read only; the table the job holds is not looked at."""
    import core.usb_library as usb_library
    system = system_of(platform)
    backend = usb_library.backend() if system == "linux" else None
    return instrument_check(list_devices(system, backend=backend))
