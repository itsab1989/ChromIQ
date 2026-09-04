"""CH34x USB-to-serial driver help — the mechanism half (Windows).

The CR30 (#159) is not a USB instrument. It sits behind a WCH CH34x USB-to-
serial bridge and ChromIQ reaches it as a COM port. On Windows-on-ARM the
bridge frequently arrives with **no driver at all**, and this module is what
lets ChromIQ diagnose that, fetch WCH's package, check it is the right one, and
hand it to an elevated ``pnputil``.

Nothing here ever removes or overwrites a driver. ``pnputil /add-driver
/install`` only adds.

WHAT THIS MODULE KNOWS THAT THE OBVIOUS IMPLEMENTATION DOES NOT
---------------------------------------------------------------
Every rule below is a measured finding on a Windows 11 ARM64 machine with a
working CR30, not a precaution:

* **A driverless CH340 reports ``Status: OK`` / ``CM_PROB_NONE``.** It had no
  class, no service and no COM port and still showed no problem code. Presence
  is therefore taken from ``cfgmgr32`` with ``CM_GETIDLIST_FILTER_PRESENT``, and
  "does it work" is a *separate* question answered per instance by whether that
  instance owns a COM port. A problem code is never consulted.
* **The plain registry walk sees ghosts.** ``…\\Enum\\USB\\VID_1A86&PID_7523``
  holds a phantom instance from an earlier replug, still carrying ``COM3``.
  ``cfgmgr32`` returns only the live one.
* **Today's ``CH341SER.ZIP`` contains three byte-identical INFs**, and
  ``WIN 9X/`` has neither the ``.CAT`` nor the ARM64 ``.sys`` its own
  ``[…NTARM64]`` section names. Pointing ``pnputil`` at it reproduces the
  original failure with a genuine, current, correctly signed package.
* **A WHQL signature proves authenticity, never suitability.** 3.5.2019.1 is
  Microsoft-countersigned and it left this machine's instrument dark for five
  days. So no signer name is used as a gate.
* **``Get-AuthenticodeSignature`` on an INF is worthless here.** It returns
  ``Valid`` for an INF alone in an empty folder, because it resolves against the
  *system* catalogue — and it therefore inverts on a machine that has never seen
  the driver, which is exactly this feature's user. The catalogue is verified
  with ``WinVerifyTrust``/``DRIVER_ACTION_VERIFY`` against the ``.CAT`` **in the
  folder**, and every file the INF copies is checked for membership of *that*
  catalogue.
* **``[Manufacturer]`` of 3.5.2019.1 is ``NT,NTamd64,NTia64``.** A gate that
  accepts bare ``NT`` accepts the package that broke this machine. Only the
  decorated section for the real CPU counts.
* **The INF is ANSI with GBK comments.** ``Path.read_text()`` raises under
  ``PYTHONUTF8=1``, which this repo's Windows gate sets. It is read as bytes and
  decoded ``latin-1``.
* **The working folder is named ``WIN 1X`` — with a space.** A quoting bug there
  already left the owner's instrument driverless once.
* **The download endpoint publishes no ``Content-Length`` and answers a
  malformed request with ``HTTP 200`` and a JSON error body.** Everything
  arriving is gated on size, time, magic bytes and archive shape *before* any
  verification is attempted.
* **``pnputil`` output is localised** (German on this machine) and 10.0.26200
  has no ``/format json``. Nothing here reads its stdout; only its exit code.

Importable on every platform. Every Windows-only call is lazy and guarded.
"""
from __future__ import annotations

import enum
import os
import shutil
import ssl
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from core.logger import get_logger
from core.usb_driver_installer import VENDOR_SERIAL_DEVICES

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# The one shared ID list
# ---------------------------------------------------------------------------
#: Every CH34x-family USB-serial bridge WCH's own INF binds to, lower-case hex.
#:
#: This is DERIVED from ``core.usb_driver_installer.VENDOR_SERIAL_DEVICES`` and
#: must stay that way: the same list decides "offer driver help for this device"
#: and "never hand this device to WinUSB". Two lists would drift, and the
#: direction they would drift in is a bricked serial instrument.
#:
#: ⚠ The specification calls these "the six WCH IDs". The INF's ``[ControlFlags]``
#: does name six *hardware IDs*, but one of them is
#: ``USB\\VID_4348&PID_5523&REV_0250`` — the same VID/PID as the entry above it
#: with a revision qualifier. As (vid, pid) pairs there are **five**.
CH34X_IDS: frozenset[tuple[str, str]] = frozenset(VENDOR_SERIAL_DEVICES)

#: WCH's own download endpoint. Unversioned, no checksum, no ``ETag``, no
#: ``Content-Length``. ChromIQ can only ever promise "we checked what arrived".
PACKAGE_URL = "https://www.wch-ic.com/download/file?id=5"

_USER_AGENT = "ChromIQ-update-check"   # same as core/updater.py:86

#: Today's archive is 713,322 bytes. The cap exists because there is no
#: ``Content-Length`` to pre-flight, so the only possible size limit is one that
#: aborts mid-transfer.
_MAX_DOWNLOAD_BYTES = 16 * 1024 * 1024
_TOTAL_DEADLINE_S = 120.0
_SOCKET_TIMEOUT_S = 20.0

#: Extraction limits — the archive is going to be handed to an elevated process.
_MAX_ENTRIES = 500
_MAX_UNPACKED_BYTES = 64 * 1024 * 1024
_MAX_INF_BYTES = 4 * 1024 * 1024
_MAX_INFS_SCANNED = 64


# ---------------------------------------------------------------------------
# Device state
# ---------------------------------------------------------------------------
class Status(enum.Enum):
    """What ChromIQ can honestly say about one CH34x bridge."""

    #: Nothing matching is attached. Never rendered on a DeviceState — it is the
    #: answer when ``devices()`` is empty.
    NO_DEVICE = "no_device"
    #: Attached, and a COM port exists for THAT instance.
    WORKING = "working"
    #: Attached, no COM port. The state this whole feature exists for.
    NO_DRIVER = "no_driver"


@dataclass(frozen=True)
class DeviceState:
    """One attached CH34x bridge and the port it owns, if any.

    ``1a86:7523`` is a generic bridge inside millions of unrelated products.
    A DeviceState NEVER means "a CR30 is attached".
    """

    instance_id: str
    vid: str
    pid: str
    port: str | None
    status: Status


def _vid_pid_from_instance_id(instance_id: str) -> tuple[str, str] | None:
    """``USB\\VID_1A86&PID_7523\\7&…`` -> ``("1a86", "7523")``."""
    parts = instance_id.upper().split("\\")
    if len(parts) < 2:
        return None
    vid = pid = None
    for token in parts[1].split("&"):
        if token.startswith("VID_"):
            vid = token[4:]
        elif token.startswith("PID_"):
            pid = token[4:]
    if not vid or not pid:
        return None
    return vid.lower(), pid.lower()


def _present_usb_instance_ids() -> list[str]:
    """Device instance IDs of USB devnodes that are PHYSICALLY PRESENT.

    ``CM_GETIDLIST_FILTER_PRESENT`` is the whole point: the registry keeps
    phantom instances from earlier replugs, and one of them on this machine
    still carries a ``PortName`` for a COM number that no longer exists.
    """
    if sys.platform != "win32":
        return []
    import ctypes  # noqa: PLC0415 -- lazy: this module imports on macOS/Linux

    CM_GETIDLIST_FILTER_ENUMERATOR = 0x00000001
    CM_GETIDLIST_FILTER_PRESENT = 0x00000100
    flags = ctypes.c_ulong(
        CM_GETIDLIST_FILTER_ENUMERATOR | CM_GETIDLIST_FILTER_PRESENT
    )
    try:
        cfgmgr32 = ctypes.WinDLL("cfgmgr32")
    except OSError as exc:              # pragma: no cover - cfgmgr32 is core OS
        log.error("cfgmgr32 unavailable: %s", exc)
        return []

    enumerator = ctypes.c_wchar_p("USB")
    size = ctypes.c_ulong(0)
    if cfgmgr32.CM_Get_Device_ID_List_SizeW(
            ctypes.byref(size), enumerator, flags) != 0 or size.value == 0:
        return []
    buf = ctypes.create_unicode_buffer(size.value)
    if cfgmgr32.CM_Get_Device_ID_ListW(
            enumerator, buf, size.value, flags) != 0:
        return []
    return [s for s in buf[:size.value].split("\0") if s]


def _port_for_instance(instance_id: str) -> str | None:
    """The COM port THIS devnode owns, or None.

    Per instance, never per machine: with an Arduino on COM3 and a driverless
    CR30 also attached, a machine-wide "is there a COM port?" says everything is
    fine while the instrument stays dark.
    """
    if sys.platform != "win32":
        return None
    import winreg  # noqa: PLC0415

    key = "SYSTEM\\CurrentControlSet\\Enum\\" + instance_id + "\\Device Parameters"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
            value = winreg.QueryValueEx(handle, "PortName")[0]
    except OSError:
        return None
    text = str(value).strip()
    return text or None


def devices() -> list[DeviceState]:
    """Every attached CH34x bridge, each joined to its own COM port.

    Presence comes from ``cfgmgr32``; a problem code is NEVER consulted, because
    a CH340 with no driver, no class and no service reports ``CM_PROB_NONE``.
    """
    out: list[DeviceState] = []
    for instance_id in _present_usb_instance_ids():
        ids = _vid_pid_from_instance_id(instance_id)
        if ids is None or ids not in CH34X_IDS:
            continue
        vid, pid = ids
        port = _port_for_instance(instance_id)
        out.append(DeviceState(
            instance_id=instance_id,
            vid=vid,
            pid=pid,
            port=port,
            status=Status.WORKING if port else Status.NO_DRIVER,
        ))
    return sorted(out, key=lambda d: d.instance_id)


# ---------------------------------------------------------------------------
# Machine architecture
# ---------------------------------------------------------------------------
#: The decorated ``[Manufacturer]`` token a package must declare for each CPU.
#:
#: There is deliberately no entry for ``X86``: on 32-bit x86 the correct section
#: IS the undecorated ``NT``, and ``NT`` is the token every WCH INF has carried
#: since 2001 — including 3.5.2019.1, whose whole ``[Manufacturer]`` line is
#: ``NT,NTamd64,NTia64``. Accepting it on any machine would accept the package
#: that broke this one, so a 32-bit host gets an honest refusal instead.
_ARCH_SECTION = {"ARM64": "NTARM64", "AMD64": "NTAMD64"}

_ARCH_ALIASES = {"EM64T": "AMD64", "X64": "AMD64", "AMD64": "AMD64",
                 "ARM64": "ARM64", "AARCH64": "ARM64",
                 "X86": "X86", "386": "X86", "I386": "X86"}


def machine_arch() -> str:
    """``'ARM64'`` | ``'AMD64'`` | ``'X86'`` — the MACHINE's CPU.

    Read from
    ``HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment``
    ``\\PROCESSOR_ARCHITECTURE``, which is machine-wide.

    NOT ``platform.machine()``: ChromIQ publishes both an x64 and an arm64
    Windows build, and the x64 build running under emulation on this ARM64
    machine reports ``AMD64`` — so the gate would look for ``NTamd64``, find it
    in 3.5.2019.1, and green-light the broken package.

    NOT ``Win32_OperatingSystem.OSArchitecture``: it is localised, and reads
    ``64-Bit-ARM-Prozessor`` on this German machine.

    Returns ``""`` when the answer is unknown (including off Windows), which
    every caller must treat as "refuse", never as "probably x64".
    """
    if sys.platform != "win32":
        return ""
    import winreg  # noqa: PLC0415

    try:
        with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment"
        ) as handle:
            raw = winreg.QueryValueEx(handle, "PROCESSOR_ARCHITECTURE")[0]
    except OSError as exc:
        log.error("could not read PROCESSOR_ARCHITECTURE: %s", exc)
        return ""
    return _ARCH_ALIASES.get(str(raw).strip().upper(), "")


# ---------------------------------------------------------------------------
# INF parsing
# ---------------------------------------------------------------------------
def _read_inf_text(path: Path) -> str:
    """Read an INF as BYTES and decode ``latin-1``.

    WCH's INF is ANSI with GBK Chinese comments (``0xb0`` at offset 5021 in
    today's file). ``Path.read_text()`` raises ``UnicodeDecodeError`` under
    ``PYTHONUTF8=1`` — which this repo's own Windows gate sets — and produces
    mojibake under the German cp1252 default. ``latin-1`` maps every byte, so it
    never raises and never loses a byte we care about; the bytes we care about
    are all ASCII.
    """
    raw = path.read_bytes()
    if len(raw) > _MAX_INF_BYTES:
        raise ValueError("INF is implausibly large")
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return raw.decode("latin-1")


def _parse_inf(text: str) -> dict[str, list[str]]:
    """``{lower-case section name: [logical lines]}``.

    Comments (``;`` to end of line) are stripped and ``\\``-continuations are
    joined, because ``CopyFiles`` lists wrap.
    """
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    pending = ""
    for raw_line in text.splitlines():
        line = raw_line.split(";", 1)[0].rstrip()
        if pending:
            line = pending + " " + line.strip()
            pending = ""
        if line.endswith("\\"):
            pending = line[:-1].rstrip()
            continue
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1].strip().lower(), [])
            continue
        if current is not None:
            current.append(line)
    return sections


def _values(section: Iterable[str], key: str) -> list[str]:
    """Every right-hand side of ``key = …`` in *section*, in order."""
    wanted = key.strip().lower()
    out: list[str] = []
    for line in section:
        if "=" not in line:
            continue
        left, right = line.split("=", 1)
        if left.strip().lower() == wanted:
            out.append(right.strip())
    return out


def _first_value(sections: dict[str, list[str]], section: str, key: str) -> str | None:
    got = _values(sections.get(section.lower(), []), key)
    return got[0] if got else None


def _split_list(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


def _decorations(manufacturer_line: str) -> tuple[str, list[str]]:
    """``%WinChipHead% = WinChipHead,NT,NTamd64,NTARM64`` -> base, decorations."""
    if "=" in manufacturer_line:
        manufacturer_line = manufacturer_line.split("=", 1)[1]
    parts = _split_list(manufacturer_line)
    if not parts:
        return "", []
    return parts[0], parts[1:]


def _copyfiles_names(sections: dict[str, list[str]], install_section: str) -> list[str]:
    """Source file names the *install_section* copies.

    ``CopyFiles = @single.sys`` names one file directly; anything else names
    ``[sections]`` whose lines are
    ``destination[,source[,unused[,flags]]]`` — the source wins when present,
    which is why this cannot just take the first field.
    """
    names: list[str] = []
    for value in _values(sections.get(install_section.lower(), []), "CopyFiles"):
        for entry in _split_list(value):
            if entry.startswith("@"):
                names.append(entry[1:].strip())
                continue
            for line in sections.get(entry.lower(), []):
                fields = [f.strip() for f in line.split(",")]
                source = fields[1] if len(fields) > 1 and fields[1] else fields[0]
                if source:
                    names.append(source)
    # de-duplicate, keep order
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        low = name.lower()
        if low not in seen:
            seen.add(low)
            out.append(name)
    return out


def _service_binary(sections: dict[str, list[str]], install_section: str) -> str | None:
    """Walk ``[install.Services] -> AddService -> [svc] -> ServiceBinary``.

    Returns the bare file name (``CH341M64.SYS``); the INF spells it
    ``%10%\\System32\\Drivers\\CH341M64.SYS``.
    """
    for line in sections.get(install_section.lower() + ".services", []):
        if not line.lower().startswith("addservice"):
            continue
        if "=" not in line:
            continue
        fields = _split_list(line.split("=", 1)[1])
        if len(fields) < 3:
            continue
        binary = _first_value(sections, fields[2], "ServiceBinary")
        if binary:
            return binary.replace("/", "\\").rsplit("\\", 1)[-1].strip()
    return None


def _catalog_name(sections: dict[str, list[str]], decoration: str) -> str | None:
    """``CatalogFile`` from ``[Version]``, decorated form preferred."""
    version = sections.get("version", [])
    for key in (f"CatalogFile.{decoration}", "CatalogFile"):
        got = _values(version, key)
        if got:
            return got[0].strip()
    return None


def _find_ci(folder: Path, name: str) -> Path | None:
    """Case-insensitive lookup of *name* directly inside *folder*.

    Windows would not care. The tests run on macOS and Linux too, and the INF
    says ``CH341M64.SYS`` while the archive ships ``CH341M64.sys``.
    """
    target = name.strip().lower()
    if not target or "\\" in target or "/" in target:
        return None
    try:
        for child in folder.iterdir():
            if child.name.lower() == target and child.is_file():
                return child
    except OSError:
        return None
    return None


# ---------------------------------------------------------------------------
# Package inspection
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PackageVerdict:
    ok: bool
    inf_path: Path | None
    reason: str
    arch_section: str | None
    service_binary: str | None


#: How far a candidate INF got. A folder with several INFs reports the failure
#: of whichever candidate got furthest, so the user is told the interesting
#: reason and not "no INF for this architecture" about the wrong file.
_STAGE_UNREADABLE = 0
_STAGE_ARCH = 1
_STAGE_SECTIONS = 2
_STAGE_FILES = 3
_STAGE_SIGNATURE = 4
_STAGE_OK = 5


def _inspect_inf(inf_path: Path, decoration: str) -> tuple[int, PackageVerdict]:
    """Everything about one INF that needs no OS call. Returns (stage, verdict)."""
    folder = inf_path.parent
    try:
        text = _read_inf_text(inf_path)
    except (OSError, ValueError) as exc:
        return _STAGE_UNREADABLE, PackageVerdict(
            False, inf_path,
            f"{inf_path.name} could not be read ({exc}).", None, None)

    sections = _parse_inf(text)

    manufacturer = sections.get("manufacturer", [])
    if not manufacturer:
        return _STAGE_UNREADABLE, PackageVerdict(
            False, inf_path,
            f"{inf_path.name} has no [Manufacturer] section, so it is not a "
            f"driver package ChromIQ can check.", None, None)

    # --- the architecture gate -------------------------------------------
    # The DECORATED section, and only that. 3.5.2019.1 declares
    # "NT,NTamd64,NTia64"; a gate that accepts bare NT accepts the package that
    # left this machine's instrument dark for five days.
    base = models_section = None
    for line in manufacturer:
        candidate_base, decorations = _decorations(line)
        for token in decorations:
            if token.split(".", 1)[0].strip().upper() == decoration.upper():
                base, models_section = candidate_base, f"{candidate_base}.{token}"
                break
        if models_section:
            break
    if not models_section:
        declared = ", ".join(
            t for line in manufacturer for t in _decorations(line)[1]) or "nothing"
        return _STAGE_ARCH, PackageVerdict(
            False, inf_path,
            f"This driver is not built for your computer's processor. "
            f"{inf_path.name} offers {declared}, and none of those is "
            f"{decoration}. (A bare \u201cNT\u201d entry does not count \u2014 it is the "
            f"fallback every WCH driver has carried since 2001, and the 2019 "
            f"package that fails on this kind of computer has exactly that.)",
            None, None)

    models = sections.get(models_section.lower(), [])
    if not models:
        return _STAGE_ARCH, PackageVerdict(
            False, inf_path,
            f"{inf_path.name} promises a [{models_section}] section for your "
            f"processor but does not contain one.", None, None)

    # --- is it even a CH34x package? --------------------------------------
    install_section = None
    matched_id = False
    for line in models:
        if "=" not in line:
            continue
        fields = _split_list(line.split("=", 1)[1])
        if not fields:
            continue
        for hwid in fields[1:]:
            # "USB\VID_4348&PID_5523&REV_0250" -> ("4348", "5523"); the REV
            # qualifier is why the INF names six hardware IDs for five chips.
            if _vid_pid_from_instance_id(hwid) in CH34X_IDS:
                matched_id = True
                if install_section is None:
                    install_section = fields[0]
    if not matched_id or install_section is None:
        return _STAGE_ARCH, PackageVerdict(
            False, inf_path,
            f"{inf_path.name} is a driver for some other hardware \u2014 it does not "
            f"list any CH34x USB-to-serial adapter.", None, None)

    if install_section.lower() not in sections:
        alt = f"{install_section}.{decoration}"
        if alt.lower() in sections:
            install_section = alt
        else:
            return _STAGE_SECTIONS, PackageVerdict(
                False, inf_path,
                f"{inf_path.name} points at an install section "
                f"[{install_section}] that is not in the file.", None, None)

    service_binary = _service_binary(sections, install_section)
    if not service_binary:
        return _STAGE_SECTIONS, PackageVerdict(
            False, inf_path,
            f"{inf_path.name} names no driver binary for your processor.",
            install_section, None)

    # --- the files must actually be here ----------------------------------
    # This single rule kills both traps: the WIN 9X folder in today's download
    # (declares NTARM64 13 times, ships no CH341M64.sys) and 3.5.2019.1 (an INF
    # promising an architecture whose .sys is absent).
    if _find_ci(folder, service_binary) is None:
        return _STAGE_FILES, PackageVerdict(
            False, inf_path,
            f"This copy of the driver is incomplete. {inf_path.name} says it "
            f"installs {service_binary}, and that file is not in "
            f"\u201c{folder.name}\u201d. Installing it would leave the adapter exactly "
            f"as it is now.", install_section, service_binary)

    copied = _copyfiles_names(sections, install_section)
    missing = [n for n in copied if _find_ci(folder, n) is None]
    if missing:
        return _STAGE_FILES, PackageVerdict(
            False, inf_path,
            f"This copy of the driver is incomplete. {inf_path.name} installs "
            f"{', '.join(missing)}, and " +
            ("that file is" if len(missing) == 1 else "those files are") +
            f" not in \u201c{folder.name}\u201d.", install_section, service_binary)

    catalog_name = _catalog_name(sections, decoration)
    if not catalog_name:
        return _STAGE_FILES, PackageVerdict(
            False, inf_path,
            f"{inf_path.name} names no security catalogue, so Windows would "
            f"refuse to install it anyway.", install_section, service_binary)
    catalog = _find_ci(folder, catalog_name)
    if catalog is None:
        return _STAGE_FILES, PackageVerdict(
            False, inf_path,
            f"The security catalogue {catalog_name} is missing from "
            f"\u201c{folder.name}\u201d. Without it ChromIQ cannot check that the "
            f"driver files are genuine and unaltered.", install_section,
            service_binary)

    # --- signature ---------------------------------------------------------
    files = [inf_path] + [
        p for p in (_find_ci(folder, n) for n in copied) if p is not None
    ]
    ok, detail = verify_catalog(catalog, files)
    if not ok:
        return _STAGE_SIGNATURE, PackageVerdict(
            False, inf_path, detail, install_section, service_binary)

    return _STAGE_OK, PackageVerdict(
        True, inf_path,
        f"This is a complete driver package for your computer. "
        f"{inf_path.name} installs {service_binary} for {decoration}, and every "
        f"file it needs is present and matches the signed catalogue "
        f"{catalog.name}.",
        install_section, service_binary)


def _candidate_infs(folder: Path) -> list[Path]:
    """Every ``.inf`` under *folder*, shallowest first, then alphabetically.

    Order is the tie-break between equally valid candidates: today's archive has
    a complete package at its root AND a complete one in ``WIN 1X/`` (measured —
    both hold the ``.CAT``, ``CH341M64.sys`` and all three DLLs, and all three
    INFs in the archive are byte-identical). The root wins, deterministically.
    """
    found: list[Path] = []
    for root, dirs, names in os.walk(folder):
        dirs.sort()
        for name in sorted(names):
            if name.lower().endswith(".inf"):
                found.append(Path(root) / name)
            if len(found) >= _MAX_INFS_SCANNED:
                return sorted(found, key=lambda p: (len(p.parts), str(p).lower()))
    return sorted(found, key=lambda p: (len(p.parts), str(p).lower()))


def inspect_package(folder: Path) -> PackageVerdict:
    """Is *folder* a driver package usable on THIS machine?

    Every gate, in order, and the reason is written to be shown to a user:

    1. the machine's real CPU, from the registry;
    2. every INF in the tree, shallowest first;
    3. the DECORATED ``[Manufacturer]`` section for that CPU — bare ``NT`` is
       refused;
    4. the models section must list a CH34x hardware ID;
    5. the install section's ``ServiceBinary`` must EXIST in the folder;
    6. every file the install section copies must EXIST in the folder;
    7. the ``.CAT`` must EXIST in the folder;
    8. ``WinVerifyTrust``/``DRIVER_ACTION_VERIFY`` on that ``.CAT``, plus
       membership of the INF and every copied file in *that* catalogue.

    A signer name is never a gate: 3.5.2019.1 is WHQL-signed and unusable here.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return PackageVerdict(
            False, None,
            f"\u201c{folder}\u201d is not a folder ChromIQ can look inside.",
            None, None)

    arch = machine_arch()
    decoration = _ARCH_SECTION.get(arch)
    if decoration is None:
        if arch == "X86":
            return PackageVerdict(
                False, None,
                "ChromIQ cannot check a driver package for a 32-bit computer. "
                "A 32-bit driver is described by the plain \u201cNT\u201d entry, which "
                "every one of these packages carries whether it works or not, "
                "so there is nothing here ChromIQ could check honestly.",
                None, None)
        return PackageVerdict(
            False, None,
            "ChromIQ could not work out what processor this computer has, so it "
            "will not guess which driver is right for it. On anything other "
            "than Windows there is nothing to install.", None, None)

    infs = _candidate_infs(folder)
    if not infs:
        return PackageVerdict(
            False, None,
            f"There is no driver information file (.inf) anywhere in "
            f"\u201c{folder}\u201d. If you downloaded a .zip, unpack it first and point "
            f"ChromIQ at the unpacked folder.", None, None)

    best_stage, best = -1, None
    for inf in infs:
        stage, verdict = _inspect_inf(inf, decoration)
        if verdict.ok:
            log.info("ch34x: accepted %s (%s, %s)",
                     inf, verdict.arch_section, verdict.service_binary)
            return verdict
        log.info("ch34x: rejected %s at stage %d: %s", inf, stage, verdict.reason)
        if stage > best_stage:
            best_stage, best = stage, verdict

    if best is None:                    # pragma: no cover - infs is non-empty
        return PackageVerdict(
            False, None, f"ChromIQ could not read anything in “{folder}”.",
            None, None)
    if len(infs) > 1:
        best = PackageVerdict(
            False, best.inf_path,
            best.reason + f" (ChromIQ checked {len(infs)} driver information "
                          f"files in that folder; none of them is usable here.)",
            best.arch_section, best.service_binary)
    return best


# ---------------------------------------------------------------------------
# Catalogue verification
# ---------------------------------------------------------------------------
_TRUST_ERRORS = {
    0x800B0100: "the catalogue carries no signature",
    0x800B0101: "the signing certificate has expired",
    0x800B0109: "the signature chains to a certificate this computer does not "
                "trust",
    0x800B0003: "Windows does not recognise the form of this file",
    0x80096010: "a file does not match the catalogue \u2014 it has been altered "
                "since it was signed",
    0x80092026: "this computer's security policy refuses the signature",
    0x800B010A: "the signature chain could not be built",
}


def verify_catalog(catalog: Path, files: list[Path]) -> tuple[bool, str]:
    """Verify *catalog* itself, then that every file in *files* is a member.

    ``WinVerifyTrust`` with ``DRIVER_ACTION_VERIFY``, against the ``.CAT`` **in
    the package folder** — explicitly NOT ``Get-AuthenticodeSignature`` on the
    INF, which resolves against the system catalogue database and therefore
    returns ``Valid`` for an INF alone in an empty folder, and returns *invalid*
    for a perfectly good package on a machine that has never installed it. That
    is the machine this feature exists for, so that check is backwards exactly
    where it matters.

    Returns ``(ok, plain-language detail)``.
    """
    if sys.platform != "win32":
        return False, ("Driver signatures can only be checked on Windows.")
    try:
        return _win_verify_catalog(catalog, files)
    except OSError as exc:              # pragma: no cover - wintrust is core OS
        log.error("wintrust unavailable: %s", exc)
        return False, ("ChromIQ could not reach the Windows service that checks "
                       f"driver signatures ({exc}), so it will not vouch for "
                       "this package.")


def _win_verify_catalog(catalog: Path, files: list[Path]) -> tuple[bool, str]:
    import ctypes  # noqa: PLC0415
    import ctypes.wintypes as wt  # noqa: PLC0415

    wintrust = ctypes.WinDLL("wintrust")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD),
                    ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]

    # DRIVER_ACTION_VERIFY {F750E6C3-38EE-11d1-85E5-00C04FC295EE}
    driver_action = GUID(0xF750E6C3, 0x38EE, 0x11D1,
                         (ctypes.c_ubyte * 8)(0x85, 0xE5, 0x00, 0xC0,
                                              0x4F, 0xC2, 0x95, 0xEE))

    class WINTRUST_FILE_INFO(ctypes.Structure):
        _fields_ = [("cbStruct", wt.DWORD),
                    ("pcwszFilePath", wt.LPCWSTR),
                    ("hFile", wt.HANDLE),
                    ("pgKnownSubject", ctypes.c_void_p)]

    class WINTRUST_CATALOG_INFO(ctypes.Structure):
        _fields_ = [("cbStruct", wt.DWORD),
                    ("dwCatalogVersion", wt.DWORD),
                    ("pcwszCatalogFilePath", wt.LPCWSTR),
                    ("pcwszMemberTag", wt.LPCWSTR),
                    ("pcwszMemberFilePath", wt.LPCWSTR),
                    ("hMemberFile", wt.HANDLE),
                    ("pbCalculatedFileHash", ctypes.POINTER(ctypes.c_ubyte)),
                    ("cbCalculatedFileHash", wt.DWORD),
                    ("pcCatalogContext", ctypes.c_void_p),
                    ("hCatAdmin", ctypes.c_void_p)]

    class WINTRUST_DATA(ctypes.Structure):
        _fields_ = [("cbStruct", wt.DWORD),
                    ("pPolicyCallbackData", ctypes.c_void_p),
                    ("pSIPClientData", ctypes.c_void_p),
                    ("dwUIChoice", wt.DWORD),
                    ("fdwRevocationChecks", wt.DWORD),
                    ("dwUnionChoice", wt.DWORD),
                    ("pUnion", ctypes.c_void_p),
                    ("dwStateAction", wt.DWORD),
                    ("hWVTStateData", wt.HANDLE),
                    ("pwszURLReference", wt.LPWSTR),
                    ("dwProvFlags", wt.DWORD),
                    ("dwUIContext", wt.DWORD),
                    ("pSignatureSettings", ctypes.c_void_p)]

    WTD_UI_NONE = 2
    WTD_REVOKE_NONE = 0
    WTD_CHOICE_FILE = 1
    WTD_CHOICE_CATALOG = 2
    WTD_STATEACTION_VERIFY = 1
    WTD_STATEACTION_CLOSE = 2
    # WTD_SAFER_FLAG (0x100) is deliberately NOT set. It is documented as the
    # driver-verification flag, and on this machine it turns a perfectly valid,
    # Microsoft-countersigned CH341SER.CAT into TRUST_E_NOSIGNATURE - i.e. it
    # would reject every genuine package. WTD_CACHE_ONLY_URL_RETRIEVAL keeps
    # revocation checking off the network, so an offline or proxied machine
    # cannot hang here.
    WTD_CACHE_ONLY_URL_RETRIEVAL = 0x1000

    TRUST_E_NOSIGNATURE = 0x800B0100

    wintrust.WinVerifyTrust.restype = ctypes.c_long
    wintrust.WinVerifyTrust.argtypes = [wt.HWND, ctypes.POINTER(GUID),
                                        ctypes.c_void_p]

    def _run(union_ptr, choice) -> int:
        data = WINTRUST_DATA()
        data.cbStruct = ctypes.sizeof(WINTRUST_DATA)
        data.dwUIChoice = WTD_UI_NONE
        data.fdwRevocationChecks = WTD_REVOKE_NONE
        data.dwUnionChoice = choice
        data.pUnion = ctypes.cast(union_ptr, ctypes.c_void_p)
        data.dwStateAction = WTD_STATEACTION_VERIFY
        data.dwProvFlags = WTD_CACHE_ONLY_URL_RETRIEVAL
        status = wintrust.WinVerifyTrust(None, ctypes.byref(driver_action),
                                         ctypes.byref(data))
        data.dwStateAction = WTD_STATEACTION_CLOSE
        wintrust.WinVerifyTrust(None, ctypes.byref(driver_action),
                                ctypes.byref(data))
        return status & 0xFFFFFFFF

    def _explain(status: int) -> str:
        return _TRUST_ERRORS.get(status,
                                 f"Windows reported error 0x{status:08X}")

    # ---- 1. the catalogue's own signature, under driver-signing policy ----
    file_info = WINTRUST_FILE_INFO()
    file_info.cbStruct = ctypes.sizeof(WINTRUST_FILE_INFO)
    file_info.pcwszFilePath = str(catalog)
    status = _run(ctypes.byref(file_info), WTD_CHOICE_FILE)
    if status != 0:
        return False, (f"The security catalogue {catalog.name} is not something "
                       f"Windows will accept for a driver: {_explain(status)}. "
                       f"ChromIQ will not install it.")

    # ---- 2. every file the INF copies must be a MEMBER of that catalogue --
    #
    # THE HASH ALGORITHM IS NOT A CONSTANT AND MUST NOT BE ASSUMED. Enumerating
    # today's CH341SER.CAT shows 8 members whose reference tags are 40 hex
    # digits: it is a SHA-1 catalogue, and one of its tags,
    # 2EE015C2BBF8B40C5F09EB50C3C97A4BAEEC15C5, is exactly what the v1 hash call
    # returns for CH341SER.INF. Meanwhile CryptCATAdminCalcHashFromFileHandle2
    # under a SHA256 context returns 1BBB1DFE... for that same file, which is in
    # no catalogue at all. Hard-coding either algorithm rejects genuine packages,
    # and the rejection is indistinguishable from tampering
    # (TRUST_E_NOSIGNATURE). So both are offered, whichever works is PINNED
    # after the first file, and every remaining file must match under that same
    # algorithm - a later mismatch is then a real mismatch and not a bad guess.
    ctypes_guid_p = ctypes.POINTER(GUID)
    ctypes_dword_p = ctypes.POINTER(wt.DWORD)
    ctypes_byte_p = ctypes.POINTER(ctypes.c_ubyte)
    ctypes_handle_p = ctypes.POINTER(ctypes.c_void_p)

    kernel32.CreateFileW.restype = wt.HANDLE
    kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD,
                                     ctypes.c_void_p, wt.DWORD, wt.DWORD,
                                     wt.HANDLE]
    kernel32.CloseHandle.argtypes = [wt.HANDLE]
    wintrust.CryptCATAdminReleaseContext.argtypes = [ctypes.c_void_p, wt.DWORD]
    wintrust.CryptCATAdminAcquireContext.restype = wt.BOOL
    wintrust.CryptCATAdminAcquireContext.argtypes = [
        ctypes_handle_p, ctypes_guid_p, wt.DWORD]
    wintrust.CryptCATAdminCalcHashFromFileHandle.restype = wt.BOOL
    wintrust.CryptCATAdminCalcHashFromFileHandle.argtypes = [
        wt.HANDLE, ctypes_dword_p, ctypes_byte_p, wt.DWORD]

    # (label, admin handle) -- a None handle means the legacy SHA-1 call.
    algorithms: list[tuple[str, object]] = []
    contexts: list[object] = []

    sha256_admin = ctypes.c_void_p()
    try:
        wintrust.CryptCATAdminAcquireContext2.restype = wt.BOOL
        wintrust.CryptCATAdminAcquireContext2.argtypes = [
            ctypes_handle_p, ctypes_guid_p, wt.LPCWSTR, ctypes.c_void_p,
            wt.DWORD]
        wintrust.CryptCATAdminCalcHashFromFileHandle2.restype = wt.BOOL
        wintrust.CryptCATAdminCalcHashFromFileHandle2.argtypes = [
            ctypes.c_void_p, wt.HANDLE, ctypes_dword_p, ctypes_byte_p,
            wt.DWORD]
        if wintrust.CryptCATAdminAcquireContext2(
                ctypes.byref(sha256_admin), ctypes.byref(driver_action),
                "SHA256", None, 0):
            algorithms.append(("SHA-256", sha256_admin))
            contexts.append(sha256_admin)
    except (AttributeError, OSError):   # pragma: no cover - pre-Windows 8
        pass

    sha1_admin = ctypes.c_void_p()
    if wintrust.CryptCATAdminAcquireContext(
            ctypes.byref(sha1_admin), ctypes.byref(driver_action), 0):
        algorithms.append(("SHA-1", None))
        contexts.append(sha1_admin)

    if not algorithms:
        return False, ("ChromIQ could not start Windows' catalogue check, so it "
                       "will not vouch for this package.")

    def _hash(handle, admin):
        size = wt.DWORD(0)
        if admin is not None:
            wintrust.CryptCATAdminCalcHashFromFileHandle2(
                admin, handle, ctypes.byref(size), None, 0)
        else:
            wintrust.CryptCATAdminCalcHashFromFileHandle(
                handle, ctypes.byref(size), None, 0)
        if size.value == 0 or size.value > 128:
            return None
        buf = (ctypes.c_ubyte * size.value)()
        if admin is not None:
            ok = wintrust.CryptCATAdminCalcHashFromFileHandle2(
                admin, handle, ctypes.byref(size), buf, 0)
        else:
            ok = wintrust.CryptCATAdminCalcHashFromFileHandle(
                handle, ctypes.byref(size), buf, 0)
        return bytes(buf) if ok else None

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    OPEN_EXISTING = 3
    INVALID_HANDLE = wt.HANDLE(-1).value

    def _member(handle, path, admin) -> int:
        digest = _hash(handle, admin)
        if digest is None:
            return TRUST_E_NOSIGNATURE
        buf = (ctypes.c_ubyte * len(digest)).from_buffer_copy(digest)
        info = WINTRUST_CATALOG_INFO()
        info.cbStruct = ctypes.sizeof(WINTRUST_CATALOG_INFO)
        info.pcwszCatalogFilePath = str(catalog)
        info.pcwszMemberTag = "".join(f"{b:02X}" for b in digest)
        info.pcwszMemberFilePath = str(path)
        info.hMemberFile = wt.HANDLE(handle)
        info.pbCalculatedFileHash = ctypes.cast(buf, ctypes_byte_p)
        info.cbCalculatedFileHash = len(digest)
        info.hCatAdmin = admin
        return _run(ctypes.byref(info), WTD_CHOICE_CATALOG)

    pinned = None
    try:
        for path in files:
            handle = kernel32.CreateFileW(str(path), GENERIC_READ,
                                          FILE_SHARE_READ, None, OPEN_EXISTING,
                                          0, None)
            if not handle or handle == INVALID_HANDLE:
                return False, (f"ChromIQ could not open {path.name} to check it "
                               f"against the catalogue.")
            try:
                status = TRUST_E_NOSIGNATURE
                for candidate in ([pinned] if pinned else algorithms):
                    status = _member(handle, path, candidate[1])
                    if status == 0:
                        pinned = candidate
                        break
            finally:
                kernel32.CloseHandle(wt.HANDLE(handle))
            if status != 0:
                # In a MEMBER check, TRUST_E_NOSIGNATURE does not mean "the
                # catalogue is unsigned" (step 1 already proved it is signed) --
                # it means this file's hash is not one of the hashes the
                # catalogue covers. That is what a swapped or edited file looks
                # like, and saying "no signature" about it would be misleading.
                why = ("it is not one of the files that catalogue was signed "
                       "for, so it has been changed, swapped or added since"
                       if status == TRUST_E_NOSIGNATURE else _explain(status))
                return False, (f"{path.name} does not match the signed "
                               f"catalogue {catalog.name}: {why}. ChromIQ will "
                               f"not install a driver package it cannot vouch "
                               f"for.")
    finally:
        for handle in contexts:
            wintrust.CryptCATAdminReleaseContext(handle, 0)

    algorithm = pinned[0] if pinned else "?"
    return True, (f"{catalog.name} is signed and accepted for driver "
                  f"installation, and all {len(files)} files it covers match "
                  f"it ({algorithm}).")


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def _tls_context() -> ssl.SSLContext:
    """The same trust story as ``core/updater.py:88`` — certifi, not the system
    store.

    Consciously chosen and consciously narrow: certifi's bundle does NOT contain
    a corporate MITM proxy's root, which lives in the Windows store, so this
    download fails on exactly the networks where fetching it in a browser also
    tends to be blocked. ``download_package`` says so in as many words rather
    than reporting "network unreachable", and the guided-manual route ("download
    it yourself, point me at the folder") stays open.
    """
    import certifi  # noqa: PLC0415
    return ssl.create_default_context(cafile=certifi.where())


def _open_url(url: str):
    """Open *url*. A seam: the tests replace this with a fake reader."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return urllib.request.urlopen(          # noqa: S310 - fixed https URL
        request, timeout=_SOCKET_TIMEOUT_S, context=_tls_context())


def stream_to_file(
    reader,
    target: Path,
    *,
    max_bytes: int = _MAX_DOWNLOAD_BYTES,
    deadline_s: float = _TOTAL_DEADLINE_S,
    progress: Callable[[int], None] | None = None,
    now: Callable[[], float] = time.monotonic,
) -> tuple[bool, str]:
    """Stream *reader* into *target*, refusing to be fed for ever.

    Three independent gates, because the endpoint gives us nothing to pre-flight
    with — no ``Content-Length``, no ``Content-Type``, no ``ETag``:

    * the first two bytes must be ``PK``, which rejects the 187-byte Spring Boot
      JSON error the endpoint serves with ``HTTP 200``, and every HTML captive
      portal;
    * a hard byte cap, aborting mid-transfer;
    * a TOTAL elapsed deadline, not a socket timeout — a server dribbling one
      byte every nine seconds never trips a socket timeout.
    """
    started = now()
    total = 0
    head = b""
    try:
        with target.open("wb") as handle:
            while True:
                if now() - started > deadline_s:
                    return False, (
                        "The download was taking too long, so ChromIQ stopped "
                        "it. Please check your internet connection and try "
                        "again.")
                chunk = reader.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    return False, (
                        "What the website sent back is far bigger than WCH's "
                        "driver package, so ChromIQ stopped the download "
                        "instead of saving it.")
                if len(head) < 2:
                    head = (head + chunk)[:2]
                    if len(head) >= 2 and head != b"PK":
                        return False, (
                            "The website did not send a .zip file. That usually "
                            "means a sign-in page or a proxy answered instead "
                            "of WCH. You can download CH341SER.ZIP yourself and "
                            "point ChromIQ at the unpacked folder.")
                handle.write(chunk)
                if progress is not None:
                    progress(total)
    except OSError as exc:
        return False, f"The download could not be saved: {exc}"

    if total == 0 or head != b"PK":
        return False, ("The website sent nothing that looks like a .zip file. "
                       "You can download CH341SER.ZIP yourself and point "
                       "ChromIQ at the unpacked folder.")
    return True, f"Downloaded {total} bytes."


def _safe_members(archive: zipfile.ZipFile, target: Path) -> tuple[list[zipfile.ZipInfo], str]:
    """Entries that are safe to write under *target*, or an explanation.

    Zip-slip guard. ``extractall`` sanitises leading slashes and ``..`` on its
    own, but this tree is about to be handed to an ELEVATED process, so the
    check is explicit and a violation aborts the whole archive rather than being
    silently rewritten.
    """
    root = target.resolve()
    members: list[zipfile.ZipInfo] = []
    unpacked = 0
    infos = archive.infolist()
    if len(infos) > _MAX_ENTRIES:
        return [], (f"That .zip contains {len(infos)} items, far more than a "
                    f"driver package. ChromIQ did not unpack it.")
    for info in infos:
        name = info.filename
        if name.startswith("/") or name.startswith("\\") or ":" in name:
            return [], (f"That .zip contains an item with an unsafe path "
                        f"(\u201c{name}\u201d). ChromIQ did not unpack it.")
        if (info.external_attr >> 16) & 0xF000 == 0xA000:
            return [], (f"That .zip contains a symbolic link (\u201c{name}\u201d), "
                        f"which a driver package never needs. ChromIQ did not "
                        f"unpack it.")
        resolved = (root / name).resolve()
        if resolved != root and root not in resolved.parents:
            return [], (f"That .zip tries to write outside the folder ChromIQ "
                        f"chose (\u201c{name}\u201d). It was not unpacked.")
        if info.is_dir():
            continue
        unpacked += info.file_size
        if unpacked > _MAX_UNPACKED_BYTES:
            return [], ("That .zip unpacks to far more than a driver package. "
                        "ChromIQ did not unpack it.")
        members.append(info)
    if not members:
        return [], "That .zip is empty."
    return members, ""


def unpack_archive(zip_path: Path, target: Path) -> tuple[bool, str]:
    """``testzip()`` then a guarded extraction into *target*."""
    try:
        with zipfile.ZipFile(zip_path) as archive:
            broken = archive.testzip()
            if broken is not None:
                return False, (f"The downloaded file is damaged \u2014 "
                               f"\u201c{broken}\u201d inside it is corrupt. Please try "
                               f"again.")
            members, why = _safe_members(archive, target)
            if not members:
                return False, why
            target.mkdir(parents=True, exist_ok=True)
            for info in members:
                archive.extract(info, target)
    except zipfile.BadZipFile:
        return False, ("The downloaded file is not a readable .zip. You can "
                       "download CH341SER.ZIP yourself and point ChromIQ at "
                       "the unpacked folder.")
    except OSError as exc:
        return False, f"The download could not be unpacked: {exc}"
    return True, "Unpacked."


def download_package(
    dest: Path,
    *,
    progress: Callable[[int], None] | None = None,
) -> tuple[bool, Path | None, str]:
    """Fetch and unpack WCH's CH341SER package into *dest*.

    Returns ``(ok, unpacked_folder, plain-language reason)``. The folder is what
    ``inspect_package`` should be pointed at; this function deliberately does
    NOT verify signatures, because everything above must survive garbage first.

    There is no way to pin what arrives: the endpoint publishes no
    ``Content-Length``, no ``ETag``, no ``Last-Modified`` and no checksum, has no
    versioned URL, and answers a malformed request with ``HTTP 200`` and a Java
    exception in JSON. ChromIQ can promise "we checked what arrived"; it can
    never promise "we know what we asked for".
    """
    dest = Path(dest)
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, None, f"ChromIQ could not create \u201c{dest}\u201d: {exc}"

    part = dest / "CH341SER.zip.part"
    final = dest / "CH341SER.zip"
    unpacked = dest / "package"

    try:
        response = _open_url(PACKAGE_URL)
    except Exception as exc:            # noqa: BLE001 - urllib raises many kinds
        name = type(exc).__name__
        if "CERTIFICATE" in str(exc).upper() or "SSL" in name.upper():
            return False, None, (
                "ChromIQ could not confirm it was really talking to WCH's "
                "website. That normally happens on a company or school network "
                "that inspects secure connections. You can download "
                "CH341SER.ZIP in your browser and point ChromIQ at the "
                "unpacked folder instead.")
        return False, None, (
            f"ChromIQ could not reach WCH's website ({exc}). You can download "
            f"CH341SER.ZIP in your browser and point ChromIQ at the unpacked "
            f"folder instead.")

    try:
        ok, why = stream_to_file(response, part, progress=progress)
    finally:
        try:
            response.close()
        except Exception:               # noqa: BLE001 - closing must never raise
            pass
    if not ok:
        part.unlink(missing_ok=True)
        return False, None, why

    try:
        os.replace(part, final)
    except OSError as exc:
        part.unlink(missing_ok=True)
        return False, None, f"The download could not be saved: {exc}"

    # os.replace cannot replace a DIRECTORY on Windows (this project has been
    # bitten once already, in the demo-project cache), so a stale extraction is
    # removed outright rather than swapped.
    if unpacked.exists():
        shutil.rmtree(unpacked, ignore_errors=True)

    ok, why = unpack_archive(final, unpacked)
    if not ok:
        return False, None, why
    return True, unpacked, (
        "Downloaded WCH's driver package and unpacked it. ChromIQ has checked "
        "that it really is a .zip and that nothing inside it points outside "
        "this folder; it has not yet checked whether it is the right driver "
        "for this computer.")


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
#: pnputil exit codes -> (installed_something, plain-language sentence).
#: NOTHING here reads pnputil's stdout. It is German on this machine and
#: 10.0.26200 has no ``/format json``; the published ``oem`` name is not stable
#: either (it moved from oem10 to oem9 during one experiment).
_PNPUTIL_OUTCOMES: dict[int, tuple[bool, str]] = {
    0: (True, "Windows accepted the driver."),
    3010: (True, "Windows accepted the driver and needs a restart to finish "
                 "switching it on. Please restart the computer, then plug the "
                 "instrument in again."),
    259: (False, "Windows accepted the driver package but found nothing to use "
                 "it on. If the instrument is plugged in, unplug it, wait a few "
                 "seconds, plug it back in and check again."),
    1223: (False, "You said No to the Windows permission prompt, so nothing was "
                  "changed."),
    5: (False, "Windows refused the change. This normally means the account "
               "does not have permission to install drivers, or a company "
               "policy blocks it. Nothing was changed."),
    2: (False, "Windows could not read the driver package. Nothing was "
               "changed."),
    87: (False, "Windows rejected the driver package as invalid. Nothing was "
                "changed."),
}


def _pnputil_path() -> Path | None:
    """Full path to ``pnputil.exe``, correct under WOW64.

    A 32-bit process sees ``System32`` redirected to ``SysWOW64``, which has no
    ``pnputil``; ``Sysnative`` is the way out. ChromIQ ships x64 and arm64
    builds, but an emulated build is exactly the case this feature keeps
    tripping over, so it is handled rather than assumed away.
    """
    root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    import struct  # noqa: PLC0415
    if struct.calcsize("P") == 4 and "PROCESSOR_ARCHITEW6432" in os.environ:
        candidate = root / "Sysnative" / "pnputil.exe"
        if candidate.exists():
            return candidate
    candidate = root / "System32" / "pnputil.exe"
    return candidate if candidate.exists() else None


def install(inf_path: Path) -> tuple[bool, str]:
    """Hand *inf_path* to an elevated ``pnputil /add-driver … /install``.

    Only ever ADDS. ChromIQ never deletes or replaces a driver.

    The package is re-inspected immediately before elevating, because the
    staging folder is user-writable and the gap between "we checked it" and "an
    administrator reads it" is the one place this could be abused.

    Elevation is ``ShellExecuteExW`` + ``lpVerb="runas"`` (the pattern at
    ``core/usb_driver_installer.py:205,232``), not ``Start-Process``, and NOT a
    verbatim copy of it: that one interpolates its arguments unquoted and
    discards the return value of ``WaitForSingleObject``. The path here routinely
    contains a space — WCH's own working folder is called ``WIN 1X`` — and a
    quoting bug there already left this project's instrument driverless once.
    """
    inf_path = Path(inf_path)
    if sys.platform != "win32":
        return False, "Drivers can only be installed on Windows."

    # The quoting check comes FIRST and does not care whether the file exists:
    # a path that cannot be handed to an elevated process safely is refused as a
    # path, not as a missing file.
    if '"' in str(inf_path):
        return False, ("That folder's name contains a quotation mark, which "
                       "Windows' driver installer cannot be given safely. "
                       "Please move the driver folder somewhere with a simpler "
                       "name and try again.")
    if not inf_path.is_file():
        return False, (f"ChromIQ cannot find \u201c{inf_path}\u201d any more. Nothing "
                       f"was changed.")

    verdict = inspect_package(inf_path.parent)
    if not verdict.ok:
        return False, ("ChromIQ re-checked the driver package just before "
                       "installing it and no longer trusts it, so nothing was "
                       f"changed. {verdict.reason}")
    if verdict.inf_path is not None and \
            verdict.inf_path.resolve() != inf_path.resolve():
        return False, ("ChromIQ re-checked the driver package just before "
                       "installing it and the file it approved is not the one "
                       "it was asked to install, so nothing was changed.")

    tool = _pnputil_path()
    if tool is None:
        return False, ("Windows' driver installer (pnputil.exe) is not on this "
                       "computer, so ChromIQ cannot install the driver. Nothing "
                       "was changed.")

    parameters = f'/add-driver "{inf_path}" /install'
    log.info("ch34x: elevating %s %s", tool, parameters)
    return _run_elevated(tool, parameters)


def _run_elevated(tool: Path, parameters: str,
                  timeout_ms: int = 300_000) -> tuple[bool, str]:
    import ctypes  # noqa: PLC0415
    import ctypes.wintypes as wt  # noqa: PLC0415

    SEE_MASK_NOCLOSEPROCESS = 0x40
    SEE_MASK_NOASYNC = 0x100
    SW_HIDE = 0
    ERROR_CANCELLED = 1223
    ERROR_ACCESS_DENIED = 5
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 258

    class _SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wt.DWORD), ("fMask", wt.ULONG), ("hwnd", wt.HWND),
            ("lpVerb", wt.LPCWSTR), ("lpFile", wt.LPCWSTR),
            ("lpParameters", wt.LPCWSTR), ("lpDirectory", wt.LPCWSTR),
            ("nShow", ctypes.c_int), ("hInstApp", wt.HINSTANCE),
            ("lpIDList", ctypes.c_void_p), ("lpClass", wt.LPCWSTR),
            ("hkeyClass", wt.HKEY), ("dwHotKey", wt.DWORD),
            ("hIcon", wt.HANDLE), ("hProcess", wt.HANDLE),
        ]

    sei = _SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(_SHELLEXECUTEINFOW)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    sei.lpVerb = "runas"
    sei.lpFile = str(tool)
    sei.lpParameters = parameters
    sei.nShow = SW_HIDE

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    if not shell32.ShellExecuteExW(ctypes.byref(sei)):
        err = ctypes.get_last_error()
        # Three states the old code collapsed into one "failed or cancelled".
        if err == ERROR_CANCELLED:
            return False, ("You said No to the Windows permission prompt, so "
                           "nothing was changed. Installing a driver needs "
                           "administrator permission; nothing else about "
                           "ChromIQ is affected.")
        if err == ERROR_ACCESS_DENIED:
            return False, ("Windows refused to ask for permission at all. On a "
                           "managed computer this usually means an "
                           "administrator has switched that prompt off. "
                           "Nothing was changed \u2014 please ask whoever looks "
                           "after this computer to install the driver.")
        return False, (f"Windows could not start its driver installer (error "
                       f"{err}). Nothing was changed.")

    try:
        wait = kernel32.WaitForSingleObject(sei.hProcess, timeout_ms)
        if wait == WAIT_TIMEOUT:
            # The old pattern discarded this and then read STILL_ACTIVE (259) as
            # an exit code, reporting failure while the install was mid-flight.
            return False, (
                "Windows' driver installer is still working after "
                f"{timeout_ms // 1000} seconds. ChromIQ has stopped waiting, "
                "but it has NOT stopped the installation \u2014 nothing was "
                "undone. Give it a moment, then use Check again.")
        if wait != WAIT_OBJECT_0:
            return False, ("ChromIQ lost track of Windows' driver installer. "
                           "Use Check again to see what actually happened.")
        code = wt.DWORD()
        kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(code))
    finally:
        kernel32.CloseHandle(sei.hProcess)

    log.info("ch34x: pnputil exit code %d", code.value)
    return describe_exit_code(code.value)


def describe_exit_code(code: int) -> tuple[bool, str]:
    """Map a ``pnputil`` exit code to an outcome. Never its stdout."""
    if code in _PNPUTIL_OUTCOMES:
        return _PNPUTIL_OUTCOMES[code]
    return False, (f"Windows' driver installer stopped with an error "
                   f"(code {code}). Nothing ChromIQ did removed or replaced any "
                   f"driver you already had.")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify_bound(before: list[DeviceState]) -> tuple[bool, str]:
    """Did a COM port appear for an instance that did not have one?

    The ONLY success test. A driver can install and not bind — that is the
    original bug, and ``pnputil`` exiting 0 does not rule it out: with two CH34x
    packages in the store it can exit 0 having merely *staged* the new one while
    the device stays on the incumbent.

    Judged per instance, so a second, already-working CH340 elsewhere on the
    machine cannot make a failure look like a success.
    """
    was_unbound = {d.instance_id for d in before if d.port is None}
    now = {d.instance_id: d for d in devices()}

    if not was_unbound:
        if now:
            ports = ", ".join(sorted(d.port for d in now.values() if d.port))
            return False, (
                f"Nothing needed fixing: every USB-to-serial adapter ChromIQ "
                f"can see already had a COM port ({ports}). ChromIQ cannot tell "
                f"you whether this install changed anything, because there was "
                f"nothing to change.")
        return False, ("ChromIQ cannot see any USB-to-serial adapter, so there "
                       "is nothing to check. Plug the instrument in and use "
                       "Check again.")

    bound = [now[i] for i in was_unbound if i in now and now[i].port]
    if bound:
        ports = ", ".join(sorted(d.port for d in bound if d.port))
        return True, (
            f"It worked. The adapter now has a COM port ({ports}) and ChromIQ "
            f"can talk to it. Go to the Measure tab and connect your "
            f"instrument.")

    gone = [i for i in was_unbound if i not in now]
    if gone and len(gone) == len(was_unbound):
        return False, ("The adapter was unplugged while ChromIQ was working, so "
                       "there is nothing to check. Plug it back in and use "
                       "Check again \u2014 nothing was removed or replaced.")

    return False, (
        "The driver installed, but Windows has not given the adapter a COM port "
        "yet, so ChromIQ still cannot reach it. Three things are worth trying, "
        "in this order: unplug the adapter, wait a few seconds and plug it back "
        "in; then use Check again; then restart the computer, because some "
        "driver changes only take effect after a restart. Nothing you had "
        "before was removed or replaced. (Device Manager's \u201cRoll Back "
        "Driver\u201d will not help here \u2014 it is greyed out for a device that never "
        "had a driver to roll back to.)")
