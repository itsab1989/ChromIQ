"""Windows-only: enumerate connected ArgyllCMS-compatible USB devices and
install WinUSB drivers via wdi-simple (libwdi)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
from pathlib import Path
from typing import NamedTuple

from core.logger import get_logger
from core.resource_path import resource_path

log = get_logger(__name__)

# VID/PID → display name for every instrument that needs ArgyllCMS's WinUSB /
# libusb0 driver. This table mirrors the *active* device lines in the
# usb/ArgyllCMS.inf shipped with ArgyllCMS 3.5.0 — i.e. exactly the devices
# Argyll's own driver binds to. Keeping it equal to the inf means ChromIQ
# offers to install the driver for precisely the devices Argyll can then use.
# VID/PID are lower-case hex to match enumerate_connected(), which lower-cases
# what it reads from the registry.
#
# Deliberately NOT included:
#   • Devices the inf comments out: 0765:5020 (Eye-One Display 3) and
#     0765:600A (D123).
#   • HID colorimeters Argyll reads without libusb (i1 Display Pro, ColorMunki
#     Display, etc.) — they must stay on their HID driver, so prompting to
#     install WinUSB for them would break them.
#
# i1 Pro family note: the i1 Pro and i1 Pro 2 share GretagMacbeth 0971:2000
# ("Eye-One Pro"); the i1 Pro 3 and i1 Pro 3+ share X-Rite 0765:6009
# ("i1 Pro3"). One mapping covers each pair — the inf has no separate i1 Pro 2
# or i1 Pro 3+ line.
KNOWN_COLORIMETERS: dict[tuple[str, str], str] = {
    # --- Gretag Macbeth / X-Rite spectrophotometers (VID 0971) ---
    ("0971", "2000"): "GretagMacbeth i1 Pro / i1 Pro 2",
    ("0971", "2001"): "GretagMacbeth Eye-One Monitor",
    ("0971", "2003"): "GretagMacbeth Eye-One Display 2",
    ("0971", "2005"): "GretagMacbeth Huey",
    ("0971", "2007"): "X-Rite ColorMunki Photo/Design",
    # --- X-Rite (VID 0765) ---
    ("0765", "6009"): "X-Rite i1 Pro 3 / i1 Pro 3+",
    ("0765", "6008"): "X-Rite i1 Studio",
    ("0765", "6003"): "X-Rite ColorMunki Smile",
    ("0765", "5001"): "X-Rite Huey (HueyL)",
    ("0765", "5010"): "X-Rite Huey (HueyL)",
    ("0765", "d020"): "X-Rite DTP20 (Pulse)",
    ("0765", "d092"): "X-Rite DTP92Q",
    ("0765", "d094"): "X-Rite DTP94",
    # --- Datacolor / ColorVision (VID 085C) ---
    ("085c", "0100"): "Datacolor Spyder 1",
    ("085c", "0200"): "Datacolor Spyder 2",
    ("085c", "0300"): "Datacolor Spyder 3",
    ("085c", "0400"): "Datacolor Spyder 4",
    ("085c", "0500"): "Datacolor Spyder 5",
    ("085c", "0a00"): "Datacolor SpyderX",
    ("085c", "0a0a"): "Datacolor SpyderX2",
    ("085c", "0a0b"): "Datacolor Spyder 2024",
    # --- Sequel Imaging (VID 0670) ---
    ("0670", "0001"): "Eye-One Display 1",
    # --- HCFR Association (VID 04DB / 04D8) ---
    ("04db", "005b"): "HCFR Colorimeter V3.1",
    ("04d8", "fe17"): "HCFR Colorimeter V4.0",
    # --- Hughski (VID 273F / 04D8) ---
    ("273f", "1004"): "Hughski ColorHug 2",
    ("273f", "1001"): "Hughski ColorHug",
    ("04d8", "f8da"): "Hughski ColorHug",
    # --- Image Engineering (VID 2457) ---
    ("2457", "4000"): "Image Engineering EX1",
}


# INSTRUMENTS THAT MUST NEVER BE GIVEN WinUSB — a third class, kept in its own
# table so no existing code path can hand one to install_winusb by accident.
#
# The CR30 (#159) does not speak USB directly: it is behind a CH340 USB-to-
# serial bridge and ChromIQ reaches it as a COM port through pyserial. Replacing
# its vendor serial driver with WinUSB does not "install a driver" — it DESTROYS
# the COM port, and the instrument goes dark in ChromIQ and in every other
# serial application until someone rolls the driver back by hand in Device
# Manager.
#
# This is the same reasoning as the HID exclusion above, with a worse outcome:
# a HID colorimeter given WinUSB stops working; a serial one stops existing.
#
# ⚠ 1a86:7523 is the generic CH340 chip and sits inside millions of unrelated
# serial devices — Arduinos, cheap adapters, lab gear. Its presence NEVER means
# "a CR30 is attached". Identification stays behavioural (open the port and ask
# the device what it is), which is why nothing here may auto-install anything.
# ⚠ THE WHOLE CH34x FAMILY, NOT JUST THE CR30's CHIP. Read from WCH's own
# CH341SER.INF (4.0.2026.02) as installed on Windows, [ControlFlags]:
#
#     ExcludeFromSelect = USB\VID_1A86&PID_7523
#     ExcludeFromSelect = USB\VID_1A86&PID_5523
#     ExcludeFromSelect = USB\VID_1A86&PID_7522
#     ExcludeFromSelect = USB\VID_1A86&PID_E523
#     ExcludeFromSelect = USB\VID_4348&PID_5523
#     ExcludeFromSelect = USB\VID_4348&PID_5523&REV_0250   <- same chip, REV-qualified
#
# Six hardware IDs, FIVE distinct VID/PID pairs. This table used to hold one of
# them, so `is_vendor_serial()` said False for four serial bridges that WinUSB
# would destroy exactly as thoroughly as it destroys the CR30's. That was
# harmless only for as long as nothing else consumed the list; `core.ch34x_driver`
# now derives CH34X_IDS from it, so the set that decides "offer driver help for
# this adapter" and the set that decides "never give this adapter WinUSB" are
# literally the same object and cannot drift apart.
VENDOR_SERIAL_DEVICES: dict[tuple[str, str], str] = {
    ("1a86", "7523"): "USB-serial bridge (CH340) — used by the CR30",
    ("1a86", "5523"): "USB-serial bridge (CH341A)",
    ("1a86", "7522"): "USB-serial bridge (CH340K)",
    ("1a86", "e523"): "USB-serial bridge (CH330)",
    ("4348", "5523"): "USB-serial bridge (CH341)",
}


def is_vendor_serial(vid: str, pid: str) -> bool:
    """Would WinUSB break this device rather than drive it?"""
    return (str(vid).lower(), str(pid).lower()) in VENDOR_SERIAL_DEVICES


class UsbDevice(NamedTuple):
    vid: str        # 4-char hex, lower-case, no 0x prefix
    pid: str
    name: str
    has_winusb: bool   # True if WinUSB or libusb0 (Argyll) driver is active


def _wdi_simple_path() -> Path:
    # Single x64 binary — runs on both x64 and ARM64 Windows via the x64 emulation layer.
    return resource_path("assets/wdi_simple.exe")


# ---------------------------------------------------------------------------
# Which of the remembered devices is actually attached
# ---------------------------------------------------------------------------
#
# `HKLM\SYSTEM\CurrentControlSet\Enum\USB` is a MEMORY, NOT A CENSUS. Windows
# keeps a subkey for every USB device the machine has ever seen, for ever, and
# for every port each one was ever plugged into. A plain walk of it therefore
# answers "what has this machine known?", which is not the question anyone here
# is asking.
#
# Measured on the ARM64 box, 2026-09-05: the registry remembered 6 vid:pid,
# cfgmgr32 said 5 were present; and the ONE attached instrument had two instance
# keys, only one of which was live. Both halves of that matter, and they fail
# differently:
#
#   • a remembered vid:pid that is gone  -> a device reported as connected when
#     it is not in the building. `unbound_targets()` then says "the driver did
#     not bind" about hardware that cannot bind anything.
#   • a remembered INSTANCE that is gone -> its stale `Service` value is OR-ed
#     into `has_winusb`. Move the instrument to another USB port and the old
#     ghost's `libusb0` masks the new instance's missing driver, so
#     `unbound_targets()` returns empty and the app claims an install that never
#     happened. That is precisely the failure `unbound_targets()` exists to
#     catch, so the check must not be built on the thing it is checking.
#
# `CM_Get_Device_ID_ListW` with `CM_GETIDLIST_FILTER_PRESENT` answers the real
# question, at instance granularity, with no extra dependency.
#
# ONE IMPLEMENTATION, DELIBERATELY. This used to live in
# `ui/dialogs/settings_dialog.py`, where it filtered the dialog's own call and
# left `unbound_targets()` — the other caller, and the one whose entire job is
# to not be fooled — reading ghosts. A filter that lives beside one caller is a
# filter the next caller will not know about. It belongs where the ghosts come
# from, so that no consumer of `enumerate_connected()` has to remember anything.
#
# NOTE ON THE FAILURE DIRECTION. When the question cannot be asked at all — not
# Windows, no cfgmgr32, the call fails — `present_usb_instance_ids()` returns
# None and NOTHING is filtered. A ghost in the list is a lie the user can see
# and ignore. A real instrument filtered OUT is a working feature that silently
# refuses to help. Of the two, only the first is survivable, so the fallback is
# deliberately the noisy one.

#: `CM_GETIDLIST_FILTER_ENUMERATOR` — restrict to the "USB" enumerator.
_CM_GETIDLIST_FILTER_ENUMERATOR = 0x00000001
#: `CM_GETIDLIST_FILTER_PRESENT` — the whole point: attached right now.
_CM_GETIDLIST_FILTER_PRESENT = 0x00000100
_CR_SUCCESS = 0


def usb_ids_in_instance(instance_id: str) -> "tuple[str, str] | None":
    r"""The (vid, pid) inside a PnP instance ID, lower-case, or None.

    ``USB\VID_1A86&PID_7523\7&3b74c78&0&1`` → ``("1a86", "7523")``.
    Composite children carry a third token (``&MI_00``) and hubs carry no VID
    at all (``USB\ROOT_HUB30\…``); both are handled by looking for the tokens
    rather than counting them.

    Lower-case out, because the registry side of the comparison is lower-cased
    too and the two have to agree — Windows writes these IDs upper-case.
    """
    parts = instance_id.split("\\")
    if len(parts) < 2:
        return None
    vid = pid = None
    for token in parts[1].upper().split("&"):
        if token.startswith("VID_"):
            vid = token[4:].lower()
        elif token.startswith("PID_"):
            pid = token[4:].lower()
    if vid is None or pid is None:
        return None
    return vid, pid


def present_usb_instance_ids() -> "set[str] | None":
    """Every USB device-instance ID attached right now, UPPER-CASE.

    None means the question could not be asked — see the note above: callers
    must then filter nothing rather than hide anything. An empty set is a real
    answer ("nothing is attached") and is NOT the same as None.
    """
    if sys.platform != "win32":
        return None
    try:
        cfgmgr = ctypes.WinDLL("cfgmgr32")
        flags = ctypes.c_ulong(
            _CM_GETIDLIST_FILTER_ENUMERATOR | _CM_GETIDLIST_FILTER_PRESENT)
        enumerator = ctypes.c_wchar_p("USB")
        size = ctypes.c_ulong(0)
        if cfgmgr.CM_Get_Device_ID_List_SizeW(
                ctypes.byref(size), enumerator, flags) != _CR_SUCCESS:
            return None
        buf = ctypes.create_unicode_buffer(size.value)
        if cfgmgr.CM_Get_Device_ID_ListW(
                enumerator, buf, size, flags) != _CR_SUCCESS:
            return None
        raw = buf[:size.value]
    except Exception as exc:   # noqa: BLE001 — a missing DLL must not kill the caller
        log.warning("could not ask Windows which USB devices are present: %s", exc)
        return None
    return {one.upper() for one in raw.split("\0") if one}


def present_usb_ids() -> "set[tuple[str, str]] | None":
    """Every (vid, pid) attached to this machine right now, or None.

    Derived from `present_usb_instance_ids()`, so this module asks cfgmgr32
    exactly once and cannot hold two answers that disagree.
    """
    instances = present_usb_instance_ids()
    if instances is None:
        return None
    return {ids for one in instances
            if (ids := usb_ids_in_instance(one)) is not None}


def _instance_id(combo: str, instance: str) -> str:
    r"""Rebuild the PnP instance ID a registry path stands for, UPPER-CASE.

    ``VID_0765&PID_6008`` + ``7&3b74c78&0&1``
    → ``USB\VID_0765&PID_6008\7&3B74C78&0&1``.

    The registry's key names reproduce the middle token of the instance ID
    exactly, composite ``&MI_00`` children included, so this compares character
    for character against cfgmgr32's list once both are upper-cased.
    """
    return ("USB\\" + combo + "\\" + instance).upper()


def attached_devices(
    entries: "list[tuple[str, list[tuple[str, str]]]]",
    present_instances: "set[str] | None",
) -> list[UsbDevice]:
    """The known colorimeters among *entries* that are attached right now.

    *entries* is what the registry holds, already read out:
    ``[(combo_key, [(instance_key, service), …]), …]`` — e.g.
    ``("VID_0765&PID_6008", [("7&3b74c78&0&1", "libusb0")])``. A service that
    could not be read is ``""``.

    *present_instances* is `present_usb_instance_ids()`: upper-case instance
    IDs, or None for "could not ask", in which case nothing is filtered.

    Pure — no registry, no ctypes — so it runs and is tested on every OS.
    """
    present_pairs = (None if present_instances is None
                     else {ids for one in present_instances
                           if (ids := usb_ids_in_instance(one)) is not None})

    found: list[UsbDevice] = []
    for combo, instances in entries:
        parts = combo.upper().split("&")
        if len(parts) < 2:
            continue
        vid = parts[0].replace("VID_", "").lower()
        pid = parts[1].replace("PID_", "").lower()
        name = KNOWN_COLORIMETERS.get((vid, pid))
        if name is None:
            continue

        # GUARD 1 — remembered, but gone. Drop it here: nothing downstream
        # should ever be handed a device that is not attached.
        if present_pairs is not None and (vid, pid) not in present_pairs:
            log.debug("skipping %s:%s (%s): remembered by the registry, "
                      "not attached", vid, pid, name)
            continue

        # GUARD 2 — remembered INSTANCES of a device that IS attached. Only the
        # live ones may speak for the driver state; a ghost instance's stale
        # `Service` is exactly what fools the post-install check.
        live = instances
        if present_instances is not None:
            live = [pair for pair in instances
                    if _instance_id(combo, pair[0]) in present_instances]
            if not live:
                # cfgmgr32 says this vid:pid IS here but no instance ID matched.
                # Presence is not in doubt, only which node it is, so fall back
                # rather than hide a real instrument — see the note on the
                # failure direction above.
                log.debug("no instance of %s:%s matched the present list; "
                          "falling back to every remembered instance", vid, pid)
                live = instances

        has_winusb = any(
            str(service).lower() in ("winusb", "libusb0") for _, service in live)
        found.append(UsbDevice(vid=vid, pid=pid, name=name, has_winusb=has_winusb))

    # Composite USB devices register multiple keys per VID/PID (parent + MI_xx
    # interface children). Keep only the first occurrence of each (vid, pid).
    seen: set[tuple[str, str]] = set()
    unique: list[UsbDevice] = []
    for dev in found:
        key = (dev.vid, dev.pid)
        if key not in seen:
            seen.add(key)
            unique.append(dev)
    return unique


def _registry_usb_entries() -> "list[tuple[str, list[tuple[str, str]]]]":
    r"""Read ``Enum\USB`` into the plain data `attached_devices()` consumes.

    Everything this returns is REMEMBERED, not present. The filtering is
    `attached_devices()`'s job and happens in exactly one place.
    """
    import winreg
    try:
        base = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Enum\USB"
        )
    except OSError:
        return []

    entries: "list[tuple[str, list[tuple[str, str]]]]" = []
    i = 0
    while True:
        try:
            combo = winreg.EnumKey(base, i)   # e.g. "VID_0765&PID_5020"
        except OSError:
            break
        i += 1

        instances: "list[tuple[str, str]]" = []
        try:
            dev_key = winreg.OpenKey(base, combo)
            j = 0
            while True:
                try:
                    inst = winreg.EnumKey(dev_key, j)
                except OSError:
                    break
                j += 1
                try:
                    svc, _ = winreg.QueryValueEx(
                        winreg.OpenKey(dev_key, inst), "Service")
                except OSError:
                    svc = ""
                instances.append((inst, str(svc)))
        except OSError:
            pass
        entries.append((combo, instances))
    return entries


def enumerate_connected() -> list[UsbDevice]:
    """Return the known colorimeters ATTACHED RIGHT NOW, with their driver state.

    "Connected" is meant literally: devices the registry merely remembers are
    filtered out here, once, so that no caller has to know the registry
    remembers anything. See the long note above for why, and for what happens
    when Windows cannot be asked.
    """
    if sys.platform != "win32":
        return []
    return attached_devices(_registry_usb_entries(), present_usb_instance_ids())


def install_winusb(device: UsbDevice) -> bool:
    """Install the WinUSB driver for *device* via wdi-simple (elevated UAC).

    Returns True if wdi-simple exits with code 0.
    Returns False if the user cancels the UAC prompt or the install fails.
    """
    # REFUSED OUTRIGHT, BELT AND BRACES. The table above is the guard; this is
    # the one that still holds if somebody adds a serial instrument to
    # KNOWN_COLORIMETERS by mistake. It matters because the dialog's "Reinstall"
    # path runs this over EVERY detected device, so a single wrong table entry
    # would brick a CR30 while the user was repairing something else entirely.
    if is_vendor_serial(device.vid, device.pid):
        log.error("refusing to install WinUSB on %s (%s:%s): it is a vendor "
                  "serial device, and WinUSB would destroy its COM port",
                  device.name, device.vid, device.pid)
        return False

    wdi = _wdi_simple_path()
    if not wdi.exists() or wdi.stat().st_size == 0:
        log.error("wdi-simple not found or empty at %s", wdi)
        return False

    args = (
        f'--vid 0x{device.vid} --pid 0x{device.pid} '
        f'--name "{device.name}" --driver WinUSB'
    )
    log.info("Installing WinUSB: %s %s", wdi.name, args)

    # ShellExecuteExW with "runas" → UAC elevation for wdi-simple only,
    # without re-launching the full ChromIQ process as admin.
    SEE_MASK_NOCLOSEPROCESS = 0x40
    SW_HIDE = 0

    class _SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize",       wt.DWORD),
            ("fMask",        wt.ULONG),
            ("hwnd",         wt.HWND),
            ("lpVerb",       wt.LPCWSTR),
            ("lpFile",       wt.LPCWSTR),
            ("lpParameters", wt.LPCWSTR),
            ("lpDirectory",  wt.LPCWSTR),
            ("nShow",        ctypes.c_int),
            ("hInstApp",     wt.HINSTANCE),
            ("lpIDList",     ctypes.c_void_p),
            ("lpClass",      wt.LPCWSTR),
            ("hkeyClass",    wt.HKEY),
            ("dwHotKey",     wt.DWORD),
            ("hIcon",        wt.HANDLE),
            ("hProcess",     wt.HANDLE),
        ]

    sei = _SHELLEXECUTEINFOW()
    sei.cbSize       = ctypes.sizeof(_SHELLEXECUTEINFOW)
    sei.fMask        = SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb       = "runas"
    sei.lpFile       = str(wdi)
    sei.lpParameters = args
    sei.nShow        = SW_HIDE

    shell32  = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32

    if not shell32.ShellExecuteExW(ctypes.byref(sei)):
        log.info("wdi-simple: UAC cancelled or ShellExecuteExW failed")
        return False

    kernel32.WaitForSingleObject(sei.hProcess, 60_000)   # 60 s timeout
    code = wt.DWORD()
    kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(code))
    kernel32.CloseHandle(sei.hProcess)
    log.info("wdi-simple exit code: %d", code.value)
    return code.value == 0


def unbound_targets(targets: list[UsbDevice]) -> list[UsbDevice]:
    """Re-enumerate and return which *targets* still lack a WinUSB/libusb0 driver.

    wdi-simple can exit 0 without actually binding the driver to the live device
    — e.g. a stale "ghost" instance from a previous USB port misdirects it — so
    the exit code alone can't be trusted. Call this after install_winusb() to
    confirm the driver really bound: an empty result means every target is now
    driven; a non-empty result means the install silently failed and the caller
    should fall back to Zadig.
    """
    target_ids = {(t.vid, t.pid) for t in targets}
    return [
        d for d in enumerate_connected()
        if (d.vid, d.pid) in target_ids and not d.has_winusb
    ]


# Public Zadig download page, used as a fallback when the bundled zadig.exe
# isn't present — e.g. running from source, where assets/zadig.exe is only
# fetched by the Windows CI build (.github/workflows/build-windows.yml).
ZADIG_URL = "https://zadig.akeo.ie"


def launch_zadig() -> str:
    """Launch the bundled Zadig GUI, or fall back to its download page.

    Returns one of:
      "launched"      — the bundled zadig.exe was started.
      "download_page" — zadig.exe wasn't bundled (or failed to start), so the
                        Zadig download page was opened in the browser instead.
      "failed"        — neither the executable nor the download page could be opened.
    """
    zadig = resource_path("assets/zadig.exe")
    if zadig.exists() and zadig.stat().st_size > 0:
        import subprocess
        try:
            subprocess.Popen([str(zadig)], close_fds=True)
            return "launched"
        except OSError as exc:
            log.error("Failed to launch zadig.exe: %s — opening download page", exc)
    else:
        log.info("zadig.exe not bundled at %s; opening download page", zadig)

    try:
        import webbrowser
        if webbrowser.open(ZADIG_URL):
            return "download_page"
    except Exception as exc:   # pragma: no cover - platform browser quirks
        log.error("Failed to open Zadig download page: %s", exc)
    return "failed"
