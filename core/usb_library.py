"""The USB library ChromIQ ships for the i1iO table drive (part of the i1iO Beta).

ChromIQ's own table code (`workflow/i1io/table/`) talks to an X-Rite i1iO 2 table over USB with
pyusb on top of libusb-1.0. The app bundles both on every platform it is built for:

* **pyusb** (BSD 3-clause), the Python side;
* **libusb-1.0** (LGPL 2.1 or later) as the prebuilt shared library of the ``libusb-package`` wheel
  (Apache 2.0 for its Python part), found here by path, never from the system, so that the frozen
  app on macOS, Windows and Linux uses the library it ships;
* not in the Windows on ARM64 build, for which ``libusb-package`` publishes no wheel: there
  :func:`status` says so (``"not-bundled"``). On Windows the table itself is reached through
  libusb-win32's libusb0.dll, not libusb-1.0 (:func:`table_backend`).

Availability is decided by what can actually be LOADED, never by the machine type alone (review
13, S-6: an x64 ChromIQ under emulation on an ARM64 PC): :func:`status` loads the bundled file
when there is one, :func:`table_backend` loads libusb0.dll on Windows, and only a library that
truly does not load gets a message.

Nothing here opens, claims or even lists a USB device. :func:`status` only LOADS the library and
asks its version (``libusb_get_version`` needs no ``libusb_init``); the app's start-up self-test
(`core/selftest.py`) uses it to prove the library loads in the built app. :func:`backend` (which
does call ``libusb_init``, still opening no device), :func:`table_backend` and
:func:`open_failure` are used by the table drive (``workflow.i1io.table.session_table``). The
words a person reads for each failure are proposals (§M-PROPOSED); this module returns only
their message ids.
"""
from __future__ import annotations

import ctypes
import os
import platform
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path

#: The library file name per system, as ``libusb-package`` ships it.
LIBRARY_NAME = {"darwin": "libusb-1.0.dylib", "win32": "libusb-1.0.dll"}.get(
    sys.platform, "libusb-1.0.so")


def process_is_windows_arm64() -> bool:
    """This PROCESS is an ARM64 Windows build (the Python it runs on), whatever the machine.
    An x64 ChromIQ under emulation on an ARM64 PC is not (review 13, S-6)."""
    return sys.platform == "win32" and sysconfig.get_platform().lower() == "win-arm64"


def bundled_on_this_platform() -> bool:
    """False only for the build that bundles no libusb-1.0 on purpose (the Windows on ARM64
    build: no wheel). Decided by the process, not the machine (review 13, S-6); and even then
    :func:`status` first looks whether a file is there and loads it."""
    return not process_is_windows_arm64()


def library_path() -> "Path | None":
    """The libusb-1.0 file ChromIQ ships, or None. Looks only where ChromIQ puts it: the
    ``libusb_package`` folder (a source checkout, or the frozen app, which keeps the package
    folder), then the frozen app's own top folder (where that package's PyInstaller hook also
    copies it). Never a system library: the app must use what it was tested with."""
    candidates: "list[Path]" = []
    try:
        import libusb_package
        p = libusb_package.get_library_path()
        if p is not None:
            candidates.append(Path(p))
    except Exception:      # noqa: BLE001 - not installed, or its resource lookup failed
        pass
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates += [Path(meipass) / "libusb_package" / LIBRARY_NAME,
                       Path(meipass) / LIBRARY_NAME]
    for c in candidates:
        if c.is_file():
            return c
    return None


@dataclass(frozen=True)
class UsbStatus:
    ok: bool
    pyusb: str = ""          # pyusb's version, "" when it does not import
    libusb: str = ""         # "1.0.30" from the loaded library, "" when not loaded
    problem: str = ""        # "", "no-pyusb", "not-bundled", "no-libusb", "libusb-does-not-load"
    path: str = ""

    def selftest_field(self) -> str:
        """One token for the start-up self-test line."""
        if self.ok:
            return f"usb=pyusb-{self.pyusb}/libusb-{self.libusb}"
        return f"usb={self.problem}"


class _Version(ctypes.Structure):
    _fields_ = [("major", ctypes.c_uint16), ("minor", ctypes.c_uint16),
                ("micro", ctypes.c_uint16), ("nano", ctypes.c_uint16),
                ("rc", ctypes.c_char_p), ("describe", ctypes.c_char_p)]


def library_version(path: Path) -> str:
    """Load *path* and ask ``libusb_get_version`` (no ``libusb_init``, no device). Raises
    OSError when the file does not load (wrong architecture, missing dependency)."""
    lib = ctypes.CDLL(str(path))
    fn = lib.libusb_get_version
    fn.restype = ctypes.POINTER(_Version)
    v = fn().contents
    return f"{v.major}.{v.minor}.{v.micro}"


def status() -> UsbStatus:
    """Whether the USB library is there and loads, without touching any device."""
    try:
        import usb
        import usb.backend.libusb1  # noqa: F401  (the backend module ships too)
        import usb.core  # noqa: F401
        import usb.util  # noqa: F401
        pyusb = str(getattr(usb, "__version__", "?"))
    except ImportError:
        return UsbStatus(False, problem="no-pyusb")
    path = library_path()
    if path is None:
        # review 13, S-6: what is (not) there decides, the machine type only names why
        return UsbStatus(False, pyusb=pyusb,
                         problem="no-libusb" if bundled_on_this_platform() else "not-bundled")
    try:
        version = library_version(path)
    except (OSError, AttributeError):
        return UsbStatus(False, pyusb=pyusb, problem="libusb-does-not-load", path=str(path))
    return UsbStatus(True, pyusb=pyusb, libusb=version, path=str(path))


def backend():
    """pyusb's libusb-1.0 backend on ChromIQ's own library, or None. Calls ``libusb_init``
    (which opens no device). For the drive's later steps; nothing calls it yet."""
    path = library_path()
    if path is None:
        return None
    import usb.backend.libusb1
    return usb.backend.libusb1.get_backend(find_library=lambda _name: str(path))


# ---- why opening the table failed: message ids (texts are proposals, STEP4_PROPOSAL) ----------

#: libusb's error codes (libusb.h) as pyusb hands them over in ``USBError.backend_error_code``
LIBUSB_ERROR_ACCESS = -3
LIBUSB_ERROR_NO_DEVICE = -4
LIBUSB_ERROR_NOT_FOUND = -5
LIBUSB_ERROR_BUSY = -6
LIBUSB_ERROR_TIMEOUT = -7
LIBUSB_ERROR_NOT_SUPPORTED = -12

#: The message each failure gets (proposed ids, §M-PROPOSED candidates).
MESSAGE_FOR_PROBLEM = {
    "no-pyusb": "M-I1IO-DRIVE-USB-MISSING",
    "no-libusb": "M-I1IO-DRIVE-USB-MISSING",
    "libusb-does-not-load": "M-I1IO-DRIVE-USB-MISSING",
    "not-bundled": "M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM",
}


#: libusb-win32 (libusb0) answers with a negative errno of ITS OWN errno.h (not the C runtime's,
#: not Python's): EACCES 13, ENOENT 2, EBUSY 16, ENODEV 19, ETIMEDOUT 116. pyusb's libusb0
#: backend hands the number over as ``backend_error_code``. UNTESTED ON REAL WINDOWS HARDWARE.
LIBUSB0_ERRNO = {-13: LIBUSB_ERROR_ACCESS, -16: LIBUSB_ERROR_BUSY, -19: LIBUSB_ERROR_NO_DEVICE,
                 -2: LIBUSB_ERROR_NOT_FOUND, -116: LIBUSB_ERROR_TIMEOUT}
#: what a libusb0 read timeout may look like (its own 116, Windows' 10060, POSIX 110 / 60)
LIBUSB0_TIMEOUT_CODES = (-116, 116, -10060, 10060, -110, 110, -60, 60)


def open_failure(exc: BaseException, system: "str | None" = None,
                 backend_kind: str = "libusb1") -> str:
    """The message id for an exception raised while finding, opening or claiming the table's
    USB device (pyusb's ``USBError`` / ``NoBackendError``, or an OSError). *system* is
    ``sys.platform`` (for tests); *backend_kind* "libusb1" (macOS, Linux) or "libusb0" (Windows,
    through libusb-win32: its codes are errno numbers, see LIBUSB0_ERRNO). Unknown errors get
    the general text with the diagnostics."""
    system = system or sys.platform
    if type(exc).__name__ == "NoBackendError":
        return "M-I1IO-DRIVE-USB-MISSING"
    code = getattr(exc, "backend_error_code", None)
    if backend_kind == "libusb0" and isinstance(code, int):
        code = LIBUSB0_ERRNO.get(code, code if code in (LIBUSB_ERROR_ACCESS,) else None)
    if code is None:
        en = getattr(exc, "errno", None)
        code = {13: LIBUSB_ERROR_ACCESS, 16: LIBUSB_ERROR_BUSY, 19: LIBUSB_ERROR_NO_DEVICE,
                110: LIBUSB_ERROR_TIMEOUT}.get(en) if isinstance(en, int) else None
    if code == LIBUSB_ERROR_ACCESS:
        return {"linux": "M-I1IO-DRIVE-USB-LINUX-PERMISSION",
                "win32": "M-I1IO-DRIVE-USB-WINDOWS-DRIVER"}.get(
                    "linux" if system.startswith("linux") else system,
                    "M-I1IO-DRIVE-BUSY")
    if code == LIBUSB_ERROR_NOT_SUPPORTED:
        return ("M-I1IO-DRIVE-USB-WINDOWS-DRIVER" if system == "win32"
                else "M-I1IO-DRIVE-USB-UNEXPECTED")
    if code == LIBUSB_ERROR_BUSY:
        return ("M-I1IO-DRIVE-USB-LINUX-KERNEL-DRIVER" if system.startswith("linux")
                else "M-I1IO-DRIVE-BUSY")
    if code in (LIBUSB_ERROR_NO_DEVICE, LIBUSB_ERROR_NOT_FOUND):
        return "M-I1IO-DRIVE-USB-GONE"
    return "M-I1IO-DRIVE-USB-UNEXPECTED"


# ---- the table's backend, per system (owner's ruling of 2026-11-17: Windows like ArgyllCMS) -----
#
# macOS and Linux: libusb-1.0 as bundled (`backend`). Linux needs the udev rule for the table
# (STEP4_PROPOSAL section 3), as ArgyllCMS's instruments do.
#
# WINDOWS: the table gets libusb-win32's kernel driver (libusb0.sys), installed by ChromIQ's own
# driver installer (wdi-simple, which embeds libusb-win32 1.4.0.0) ONLY on the person's explicit
# choice. libusb-1.0 does NOT open libusb0.sys devices by itself: its Windows backend reaches
# libusb0.sys only through libusbK.dll ("all libusb0.sys accesses are done through it", libusb's
# Windows wiki), which ChromIQ does not ship. libusb-win32's own user library, libusb0.dll, is
# copied into the system folder by the very driver package the installer binds (libwdi's
# libusb0.inf: libusb_files_dll -> system32 on x64 and ARM64), and it must match libusb0.sys. So
# on Windows the table is opened through pyusb's libusb0 backend, with THAT file by its full path
# (never a name search): no second driver family, nothing more to ship. UNTESTED ON REAL WINDOWS
# HARDWARE. Windows on ARM64: the x64 ChromIQ cannot load the ARM64 libusb0.dll the driver
# installs. Review 13, S-6: that is decided by LOADING the file (``load_libusb0``), and only a
# file that truly does not load gets a message (``"libusb0-does-not-load"``): on an ARM64 PC
# the one that says the drive cannot run on this system yet, elsewhere the library message.

def libusb0_dll_path() -> "Path | None":
    """libusb-win32's libusb0.dll as its driver package installed it (System32), or None."""
    if sys.platform != "win32":
        return None
    root = os.environ.get("SystemRoot") or os.environ.get("windir")
    if not root:
        return None
    p = Path(root) / "System32" / "libusb0.dll"
    return p if p.is_file() else None


def load_libusb0(path) -> "str | None":
    """None when libusb0.dll at *path* loads into this process, else why not (an x64 ChromIQ
    and an ARM64 file, a damaged file). Loading opens no device."""
    try:
        loader = getattr(ctypes, "WinDLL", ctypes.CDLL)
        loader(str(path))
    except OSError as exc:
        return type(exc).__name__
    return None


def machine_is_arm64() -> bool:
    """The MACHINE is an ARM64 PC (the machine-wide registry value, as the CH34x gate reads
    it), for the words of a message only; False when it cannot be told."""
    try:
        from core.ch34x_driver import machine_arch
        return machine_arch() == "ARM64"
    except Exception:      # noqa: BLE001 - only the wording depends on it
        return False


@dataclass(frozen=True)
class TableBackend:
    backend: object
    kind: str            # "libusb1" or "libusb0"
    problem: str = ""    # "" or why there is none: "no-libusb", "no-libusb0-dll", "not-bundled"


def table_backend(system: "str | None" = None, dll_path=None) -> TableBackend:
    """The pyusb backend the table is opened through on this system (opens no device). The job
    does not care which one it got: both carry pyusb's device API."""
    system = system or sys.platform
    if system == "win32":
        path = dll_path if dll_path is not None else libusb0_dll_path()
        if path is None:
            return TableBackend(None, "libusb0", "no-libusb0-dll")
        why = load_libusb0(path)
        if why is not None:
            # review 13, S-6: the file is there and does not load into this process
            return TableBackend(None, "libusb0", "libusb0-does-not-load-arm64"
                                if machine_is_arm64() else "libusb0-does-not-load")
        import usb.backend.libusb0
        be = usb.backend.libusb0.get_backend(find_library=lambda _name, p=str(path): p)
        return TableBackend(be, "libusb0", "" if be is not None else "no-libusb0-dll")
    be = backend()
    return TableBackend(be, "libusb1", "" if be is not None else "no-libusb")


MESSAGE_FOR_PROBLEM["no-libusb0-dll"] = "M-I1IO-DRIVE-TABLE-DRIVER-NOT-INSTALLED"
MESSAGE_FOR_PROBLEM["libusb0-does-not-load-arm64"] = "M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM"
MESSAGE_FOR_PROBLEM["libusb0-does-not-load"] = "M-I1IO-DRIVE-USB-MISSING"


def table_usb_status() -> UsbStatus:
    """What START asks before anything is opened (review 13, S-6). macOS and Linux: the bundled
    libusb-1.0 (:func:`status`). Windows: the table is reached through libusb0.dll, which
    :func:`table_backend` LOADS when the table is opened (with its own message when it truly
    does not load), so here only pyusb must import: a build without libusb-1.0 is not refused
    for a library the table does not use there."""
    st = status()
    if sys.platform != "win32" or st.ok or st.problem == "no-pyusb":
        return st
    return UsbStatus(True, pyusb=st.pyusb, libusb=st.libusb, path=st.path)


def diagnostics() -> dict:
    """What the session's diagnostics file records about USB (no serial numbers, no paths with a
    user name: the library's file name only)."""
    st = status()
    return {"platform": sys.platform, "machine": platform.machine(),
            "pyusb": st.pyusb, "libusb": st.libusb, "problem": st.problem,
            "library": os.path.basename(st.path) if st.path else ""}
