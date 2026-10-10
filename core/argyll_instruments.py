"""Is an ArgyllCMS-supported instrument plugged in RIGHT NOW?

**Nothing is opened, nothing is written and no instrument is claimed.** This
module lists the USB devices the operating system already knows about and asks
whether any of them is one ArgyllCMS can drive. It is the counterpart of
`workflow.cr30.discovery.candidates()` — the same kind of evidence, from the
same kind of read — so that "a CR30 is here" and "a ColorMunki is here" can be
weighed against each other instead of only one of them being askable.

WHY IT EXISTS. `ui/dialogs/spot_read_dialog.py` had to decide, without asking
the user, whether to drive ArgyllCMS `spotread` or ChromIQ's own CR30 reader.
It could see a CR30 and it could see a *remembered* CR30, but it could not see
an ArgyllCMS instrument at all — so a remembered Bluetooth address, which is a
fact about the past, outranked a ColorMunki sitting on the desk. The owner hit
exactly that on 2026-09-02: *"had my colormunki connected via usb ... it
defaulted to the cr30 via blutooth and did not leave me a choice."*

**DO NOT LAUNCH `spotread` TO FIND OUT.** It is slow, it opens and claims the
device, and its usage text is what filled his log. The question here is
"is one attached", not "can one be driven"; an OS device list answers it in
milliseconds (measured on the owner's Mac: 15 ms).

WHY USB ONLY, AND NOT THE SERIAL PORTS. ArgyllCMS also drives serial
instruments (DTP41, Spectrolino, SpectroScan), and `spotread -c` lists serial
ports. But a serial PORT is not an instrument: macOS always offers
`/dev/cu.Bluetooth-Incoming-Port`, and that port appearing in spotread's list
is precisely what the owner was shown when the tool found nothing. A port that
exists is no evidence; a USB vendor/product id that ArgyllCMS itself matches
is. So a serial-only instrument is invisible here, which costs its owner one
choice from a dropdown and can never cost anyone a false positive.
"""
from __future__ import annotations

from dataclasses import dataclass

import logging
import re
import sys

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsbDevice:
    """One USB device the operating system currently reports as attached."""
    vid: int
    pid: int
    name: str = ""


#: ArgyllCMS's own USB matching table, transcribed from
#: ``spectro/insttypes.c``'s ``inst_usb_match()`` (ArgyllCMS 3.5.0, lines
#: 423-518 of the original source at ``~/Downloads/Argyll_V3.5.0_orig/``).
#: EIGHT vendor ids, and the names are Argyll's own comments.
#:
#: Kept as data rather than as code so that the test which pins it can read the
#: real ``insttypes.c`` and compare — a new Argyll release that adds an
#: instrument should fail that test, not go unnoticed.
#:
#: `inst_usb_match` takes a third argument, the endpoint count, and uses it for
#: exactly one pair: 0x0971:0x2000 is an i1Pro 2 when it has five or more
#: endpoints and an i1Pro otherwise. Both are ArgyllCMS instruments, so the
#: distinction changes only the name and never the answer this module gives;
#: the entry says so rather than pretending to know.
ARGYLL_USB_IDS: "dict[tuple[int, int], str]" = {
    (0x04DB, 0x005B): "Colorimtre HCFR",
    (0x0670, 0x0001): "Monaco Optix / i1 Display 1",
    (0x0765, 0x5001): "HueyL",
    (0x0765, 0x5010): "HueyL",
    (0x0765, 0x5020): "i1DisplayPro / ColorMunki Display",
    (0x0765, 0x6003): "ColorMunki Smile",
    (0x0765, 0x6008): "ColorMunki i1Studio",
    (0x0765, 0x6009): "i1Pro 3",
    (0x0765, 0xD020): "DTP20",
    (0x0765, 0xD092): "DTP92Q",
    (0x0765, 0xD094): "DTP94",
    (0x085C, 0x0100): "ColorVision Spyder1",
    (0x085C, 0x0200): "ColorVision Spyder2",
    (0x085C, 0x0300): "DataColor Spyder3",
    (0x085C, 0x0400): "DataColor Spyder4",
    (0x085C, 0x0500): "DataColor Spyder5",
    (0x085C, 0x0A00): "DataColor SpyderX",
    (0x085C, 0x0A0A): "DataColor SpyderX2",
    (0x085C, 0x0A0B): "DataColor Spyder2024",
    (0x0971, 0x2000): "i1Pro / i1Pro 2",
    (0x0971, 0x2001): "i1 Monitor",
    (0x0971, 0x2003): "i1 Display 2",
    (0x0971, 0x2005): "Huey",
    (0x0971, 0x2007): "ColorMunki",
    (0x2457, 0x4000): "EX1",
    (0x04D8, 0xF8DA): "ColorHug",
    (0x273F, 0x1001): "ColorHug",
    (0x273F, 0x1004): "ColorHug2",
}

#: The CH340/CH554 serial bridge the CR30 speaks through. It is NOT in
#: ArgyllCMS's table and must never be treated as an instrument by anything:
#: an Arduino, a 3D printer or a CNC controller answers to the same ids
#: (`workflow/cr30/discovery.py`). Named here only so the test that proves it
#: is never matched has something to point at.
CH34X_IDS = (0x1A86, 0x7523)


def match(vid: int, pid: int) -> "str | None":
    """The ArgyllCMS instrument these ids mean, or None. Mirrors `inst_usb_match`."""
    return ARGYLL_USB_IDS.get((vid, pid))


# ----------------------------------------------------------------------
# The OS device lists — one per platform, each a plain read
# ----------------------------------------------------------------------
def _macos_usb_devices() -> "tuple[UsbDevice, ...] | None":
    """macOS: the IORegistry, through `ioreg`. ~15 ms, no device is opened.

    `ioreg -p IOUSB -l` walks the USB plane and prints one block per node,
    each starting with a `+-o ` line. A device's block carries `idVendor`,
    `idProduct` and usually `USB Product Name`; its interfaces nest inside and
    repeat the ids, which is harmless because the answer is a set.
    """
    import subprocess
    for args in (["-p", "IOUSB", "-l", "-w", "0"],
                 ["-r", "-c", "IOUSBHostDevice", "-l", "-w", "0"]):
        try:
            out = subprocess.run(
                ["/usr/sbin/ioreg", *args],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=10, check=False).stdout
        except Exception:          # noqa: BLE001 — an unreadable list is "unknown"
            log.debug("ioreg %s failed", args, exc_info=True)
            continue
        found = _parse_ioreg(out)
        if found:
            return found
    return None


def _parse_ioreg(text: str) -> "tuple[UsbDevice, ...]":
    """Pull (vid, pid, name) out of `ioreg -l` output. Pure text, unit-tested."""
    devices: "list[UsbDevice]" = []
    vid = pid = None
    name = ""

    def flush() -> None:
        if vid is not None and pid is not None:
            devices.append(UsbDevice(vid, pid, name))

    for line in text.splitlines():
        if "+-o " in line:
            flush()
            vid = pid = None
            name = ""
            continue
        m = re.search(r'"idVendor"\s*=\s*(\d+)', line)
        if m:
            vid = int(m.group(1))
            continue
        m = re.search(r'"idProduct"\s*=\s*(\d+)', line)
        if m:
            pid = int(m.group(1))
            continue
        m = re.search(r'"USB Product Name"\s*=\s*"([^"]*)"', line)
        if m:
            name = m.group(1)
    flush()
    return tuple(dict.fromkeys(devices))


def _count_ioreg_instruments(text: str) -> int:
    """How many ArgyllCMS instruments an ``ioreg -l`` listing holds, counting
    two identical ones twice (by ``locationID``, the USB port they sit on).

    :func:`_parse_ioreg` answers "which kinds", and folds two i1Pros into one;
    the instrument PORT number needs "how many", because Argyll gives each its
    own number ahead of the serial ports (`core.instrument_port`). Pure text.
    """
    seen: "set[object]" = set()
    vid = pid = loc = None
    block = 0

    def flush() -> None:
        if vid is not None and pid is not None and match(vid, pid):
            seen.add(("loc", loc) if loc is not None else ("block", block))

    for line in text.splitlines():
        if "+-o " in line:
            flush()
            vid = pid = loc = None
            block += 1
            continue
        m = re.search(r'"idVendor"\s*=\s*(\d+)', line)
        if m:
            vid = int(m.group(1))
            continue
        m = re.search(r'"idProduct"\s*=\s*(\d+)', line)
        if m:
            pid = int(m.group(1))
            continue
        m = re.search(r'"locationID"\s*=\s*(\d+)', line)
        if m:
            loc = int(m.group(1))
    flush()
    return len(seen)


def attached_instrument_count() -> "int | None":
    """How many ArgyllCMS USB instruments are attached now (macOS), or None
    when that cannot be read. Nothing is opened: the IORegistry, as above."""
    if sys.platform != "darwin":
        return None
    import subprocess
    try:
        out = subprocess.run(
            ["/usr/sbin/ioreg", "-p", "IOUSB", "-l", "-w", "0"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10, check=False,
            stdin=subprocess.DEVNULL).stdout
    except Exception:          # noqa: BLE001 — an unreadable list is "unknown"
        log.debug("ioreg failed", exc_info=True)
        return None
    if "+-o " not in out:
        return None
    return _count_ioreg_instruments(out)


def _linux_usb_devices(root: str = "/sys/bus/usb/devices") -> "tuple[UsbDevice, ...] | None":
    """Linux: sysfs, which lists only what is plugged in now."""
    from pathlib import Path
    base = Path(root)
    if not base.is_dir():
        return None
    devices: "list[UsbDevice]" = []
    for entry in sorted(base.iterdir()):
        try:
            vid = int((entry / "idVendor").read_text(encoding="utf-8").strip(), 16)
            pid = int((entry / "idProduct").read_text(encoding="utf-8").strip(), 16)
        except Exception:          # noqa: BLE001 — interfaces have no ids
            continue
        try:
            name = (entry / "product").read_text(encoding="utf-8").strip()
        except Exception:          # noqa: BLE001 — optional
            name = ""
        devices.append(UsbDevice(vid, pid, name))
    return tuple(dict.fromkeys(devices))


#: `USB\VID_0765&PID_6008\...` — a Windows device instance id.
_WINDOWS_ID = re.compile(r"USB\\VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})")


def _parse_windows_ids(ids: "list[str]") -> "tuple[UsbDevice, ...]":
    """Pull (vid, pid) out of Windows device instance ids. Pure text, unit-tested."""
    devices: "list[UsbDevice]" = []
    for one in ids:
        m = _WINDOWS_ID.search(one)
        if m:
            devices.append(UsbDevice(int(m.group(1), 16), int(m.group(2), 16), ""))
    return tuple(dict.fromkeys(devices))


def _windows_usb_devices() -> "tuple[UsbDevice, ...] | None":
    """Windows: `cfgmgr32`'s PRESENT device list, through ctypes.

    NOT the registry. `HKLM\\SYSTEM\\CurrentControlSet\\Enum\\USB` lists every
    device the machine has ever seen, which is the same "remembered, not
    present" mistake this whole change exists to undo.
    `CM_Get_Device_ID_ListW` with ``CM_GETIDLIST_FILTER_PRESENT`` lists what is
    attached now, and it is in every Windows install with no extra dependency.

    **Unexercised on this machine** — ChromIQ's development host is a Mac.
    Every failure path returns None, which the caller reads as "cannot tell"
    and which leaves the choice exactly where it was before this module
    existed, so a mistake here can only ever cost the improvement, never the
    behaviour.
    """
    try:
        import ctypes
        from ctypes import wintypes
        cfgmgr = ctypes.WinDLL("cfgmgr32")           # type: ignore[attr-defined]
        CM_GETIDLIST_FILTER_ENUMERATOR = 0x00000001
        CM_GETIDLIST_FILTER_PRESENT = 0x00000100
        flags = CM_GETIDLIST_FILTER_ENUMERATOR | CM_GETIDLIST_FILTER_PRESENT
        size = wintypes.ULONG(0)
        if cfgmgr.CM_Get_Device_ID_List_SizeW(
                ctypes.byref(size), ctypes.c_wchar_p("USB"), flags) != 0:
            return None
        buf = ctypes.create_unicode_buffer(size.value)
        if cfgmgr.CM_Get_Device_ID_ListW(
                ctypes.c_wchar_p("USB"), buf, size.value, flags) != 0:
            return None
        return _parse_windows_ids([s for s in buf[:size.value].split("\0") if s])
    except Exception:              # noqa: BLE001 — an unreadable list is "unknown"
        log.debug("could not read the Windows device list", exc_info=True)
        return None


def usb_devices() -> "tuple[UsbDevice, ...] | None":
    """Every USB device attached now, or None when this host cannot be read.

    None is NOT "nothing is attached". The two are different answers and the
    caller must keep them apart: "nothing is attached" is evidence, "I could
    not look" is not.
    """
    try:
        if sys.platform == "darwin":
            return _macos_usb_devices()
        if sys.platform.startswith("linux"):
            return _linux_usb_devices()
        if sys.platform.startswith("win"):
            return _windows_usb_devices()
    except Exception:              # noqa: BLE001 — a guess, never worth an error
        log.debug("could not list the USB devices", exc_info=True)
        return None
    return None


def attached_instruments() -> "tuple[str, ...] | None":
    """The ArgyllCMS instruments attached over USB now, by name.

    ``()`` means none are; ``None`` means this host could not be read.
    """
    devices = usb_devices()
    if devices is None:
        return None
    return tuple(dict.fromkeys(
        name for d in devices if (name := match(d.vid, d.pid)) is not None))


def any_attached() -> "bool | None":
    """True / False / None — is an ArgyllCMS instrument plugged in right now?"""
    found = attached_instruments()
    return None if found is None else bool(found)


# ---------------------------------------------------------------------------
# A cheap "did anything on USB change?" for a window that keeps a label fresh
# ---------------------------------------------------------------------------
def _macos_usb_fingerprint() -> "tuple | None":
    """macOS: (vendor, product, location) of every USB device, read IN PROCESS.

    `usb_devices()` runs `/usr/sbin/ioreg`, a new process every call: measured
    2026-10-10 at 25 ms idle and 39 ms with every core busy, on the GUI thread.
    That is fine once, when a window opens or a session ends, and not fine
    every two seconds. This asks the same IORegistry through IOKit directly
    (`IOServiceGetMatchingServices`, read only, nothing opened): measured
    well under a millisecond. It is only a CHANGE DETECTOR; the answer about
    which reader is attached still comes from :func:`any_attached`.
    """
    import ctypes
    iokit = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/IOKit.framework/IOKit")
    cf = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    vp, u32 = ctypes.c_void_p, ctypes.c_uint32
    iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
    iokit.IOServiceMatching.restype = vp
    iokit.IOServiceGetMatchingServices.argtypes = [u32, vp, ctypes.POINTER(u32)]
    iokit.IOServiceGetMatchingServices.restype = ctypes.c_int
    iokit.IOIteratorNext.argtypes = [u32]
    iokit.IOIteratorNext.restype = u32
    iokit.IOObjectRelease.argtypes = [u32]
    iokit.IOObjectRelease.restype = ctypes.c_int
    iokit.IORegistryEntryCreateCFProperty.argtypes = [u32, vp, vp, u32]
    iokit.IORegistryEntryCreateCFProperty.restype = vp
    cf.CFStringCreateWithCString.argtypes = [vp, ctypes.c_char_p, u32]
    cf.CFStringCreateWithCString.restype = vp
    cf.CFNumberGetValue.argtypes = [vp, ctypes.c_int, vp]
    cf.CFNumberGetValue.restype = ctypes.c_bool
    cf.CFRelease.argtypes = [vp]
    cf.CFRelease.restype = None
    utf8 = 0x08000100
    keys = [cf.CFStringCreateWithCString(None, k, utf8)
            for k in (b"idVendor", b"idProduct", b"locationID")]
    try:
        for cls in (b"IOUSBHostDevice", b"IOUSBDevice"):
            it = u32()
            # The matching dictionary is consumed by the call; nothing to free.
            if iokit.IOServiceGetMatchingServices(
                    0, iokit.IOServiceMatching(cls), ctypes.byref(it)) != 0:
                continue
            found = []
            try:
                while True:
                    svc = iokit.IOIteratorNext(it.value)
                    if not svc:
                        break
                    row = []
                    for key in keys:
                        ref = iokit.IORegistryEntryCreateCFProperty(svc, key, None, 0)
                        val = ctypes.c_int64(-1)
                        if ref:
                            cf.CFNumberGetValue(ref, 4, ctypes.byref(val))  # SInt64
                            cf.CFRelease(ref)
                        row.append(val.value)
                    iokit.IOObjectRelease(svc)
                    found.append(tuple(row))
            finally:
                iokit.IOObjectRelease(it.value)
            if found:
                return tuple(sorted(found))
        return ()
    finally:
        for key in keys:
            if key:
                cf.CFRelease(key)


def usb_fingerprint() -> "tuple | None":
    """Something that changes when a USB device is plugged in or pulled out.

    Cheap enough to ask every couple of seconds on the GUI thread: on macOS an
    in-process IOKit read (see :func:`_macos_usb_fingerprint`); on Linux and
    Windows :func:`usb_devices`, which is already in process there (a sysfs
    walk, SetupAPI). Never starts a program, never opens a device, never
    touches a serial port. None when this host cannot be read, so a caller
    compares like with like and simply sees "no change".
    """
    try:
        if sys.platform == "darwin":
            return _macos_usb_fingerprint()
        devices = usb_devices()
        return None if devices is None else tuple(sorted(
            (d.vid, d.pid, d.name) for d in devices))
    except Exception:              # noqa: BLE001 — a change detector, never an error
        log.debug("could not fingerprint the USB devices", exc_info=True)
        return None
