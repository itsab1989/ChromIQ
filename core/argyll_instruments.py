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
