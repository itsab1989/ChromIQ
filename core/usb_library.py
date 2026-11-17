"""The USB library ChromIQ ships for the i1iO table drive (part of the i1iO Beta; NOT WIRED IN YET).

ChromIQ's own table code (`workflow/i1io/table/`) talks to an X-Rite i1iO 2 table over USB with
pyusb on top of libusb-1.0. The app bundles both on every platform it is built for:

* **pyusb** (BSD 3-clause), the Python side;
* **libusb-1.0** (LGPL 2.1 or later) as the prebuilt shared library of the ``libusb-package`` wheel
  (Apache 2.0 for its Python part), found here by path, never from the system, so that the frozen
  app on macOS, Windows and Linux uses the library it ships;
* not on Windows on ARM64, for which ``libusb-package`` publishes no wheel: there
  :func:`status` says so (``"not-bundled"``) and the drive is unavailable with a plain reason.

Nothing here opens, claims or even lists a USB device. :func:`status` only LOADS the library and
asks its version (``libusb_get_version`` needs no ``libusb_init``); the app's start-up self-test
(`core/selftest.py`) uses it to prove the library loads in the built app. :func:`backend` (which
does call ``libusb_init``, still opening no device) and :func:`open_failure` are for the drive's
later steps; nothing calls them yet. The words a person reads for each failure are proposals
(STEP4_PROPOSAL, §M-PROPOSED); this module returns only their message ids.
"""
from __future__ import annotations

import ctypes
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

#: The library file name per system, as ``libusb-package`` ships it.
LIBRARY_NAME = {"darwin": "libusb-1.0.dylib", "win32": "libusb-1.0.dll"}.get(
    sys.platform, "libusb-1.0.so")


def bundled_on_this_platform() -> bool:
    """False only where no libusb is bundled on purpose (Windows on ARM64: no wheel).

    DOUBT, NOT MEASURED (review 2026-11-17, A2-c): on Windows ``platform.machine()`` may name the
    HOST rather than this process, so an x64 ChromIQ running under emulation on an ARM64 PC could
    be told "ARM64" here and refuse the x64 library it carries. One run settles it: on a Windows
    ARM64 machine, start the x64 build with CHROMIQ_SELFTEST=1; ``usb=pyusb-.../libusb-...`` means
    this is fine, ``usb=not-bundled`` means decide by the process instead
    (``sysconfig.get_platform() == "win-arm64"``) or by whether the file is bundled."""
    return not (sys.platform == "win32"
                and platform.machine().upper() in ("ARM64", "AARCH64"))


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
    if not bundled_on_this_platform():
        return UsbStatus(False, pyusb=pyusb, problem="not-bundled")
    path = library_path()
    if path is None:
        return UsbStatus(False, pyusb=pyusb, problem="no-libusb")
    try:
        version = library_version(path)
    except (OSError, AttributeError):
        return UsbStatus(False, pyusb=pyusb, problem="libusb-does-not-load", path=str(path))
    return UsbStatus(True, pyusb=pyusb, libusb=version, path=str(path))


def backend():
    """pyusb's libusb-1.0 backend on ChromIQ's own library, or None. Calls ``libusb_init``
    (which opens no device). For the drive's later steps; nothing calls it yet."""
    path = library_path()
    if path is None or not bundled_on_this_platform():
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


def open_failure(exc: BaseException, system: "str | None" = None) -> str:
    """The message id for an exception raised while finding, opening or claiming the table's
    USB device (pyusb's ``USBError`` / ``NoBackendError``, or an OSError). *system* is
    ``sys.platform`` (for tests). Unknown errors get the general text with the diagnostics."""
    system = system or sys.platform
    if type(exc).__name__ == "NoBackendError":
        return "M-I1IO-DRIVE-USB-MISSING"
    code = getattr(exc, "backend_error_code", None)
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


def diagnostics() -> dict:
    """What the session's diagnostics file records about USB (no serial numbers, no paths with a
    user name: the library's file name only)."""
    st = status()
    return {"platform": sys.platform, "machine": platform.machine(),
            "pyusb": st.pyusb, "libusb": st.libusb, "problem": st.problem,
            "library": os.path.basename(st.path) if st.path else ""}
