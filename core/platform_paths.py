"""Centralised platform-conditional paths and URLs.

This module exists so that every place in ChromIQ that needs to ask
"where do logs go on this OS?" / "where is ArgyllCMS installed?" /
"where do ICC profiles live?" delegates to one set of functions
with explicit branches for ``win32``, ``darwin`` and ``linux``.

Stdlib only — must not import anything from ``core.settings`` or
``core.logger`` to avoid circular imports.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Platform predicates
# ---------------------------------------------------------------------------

def is_windows() -> bool:
    return sys.platform == "win32"


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


# ---------------------------------------------------------------------------
# ArgyllCMS
# ---------------------------------------------------------------------------

def default_argyll_bin_dir() -> str:
    """Sensible default Argyll bin directory shown in Preferences."""
    if is_windows():
        return r"C:\Program Files\ArgyllCMS\bin"
    if is_macos():
        return "/Applications/Argyll/bin"
    return "/usr/bin"


def argyll_candidate_dirs() -> list[Path]:
    """Ordered list of directories to probe for Argyll binaries.

    Order is preserved across refactor: PATH-discovered candidates are
    handled by the caller, not this function.  This function returns the
    fixed and dynamically-scanned fallback locations only.
    """
    if is_windows():
        local_app = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        candidates: list[Path] = [
            Path(r"C:\Program Files\ArgyllCMS\bin"),
            Path(r"C:\Program Files (x86)\ArgyllCMS\bin"),
            local_app / "ArgyllCMS" / "bin",
            Path.home() / "ArgyllCMS" / "bin",
        ]
        for search_root in (local_app / "ArgyllCMS",
                            Path(r"C:\Program Files\ArgyllCMS")):
            try:
                versioned = sorted(
                    (d for d in search_root.iterdir()
                     if d.is_dir() and "argyll" in d.name.lower()),
                    reverse=True,
                )
                candidates = [d / "bin" for d in versioned] + candidates
            except (PermissionError, OSError, FileNotFoundError):
                pass
        return candidates

    if is_macos():
        candidates = [
            Path("/Applications/Argyll/bin"),
            Path("/Applications/ArgyllCMS/bin"),
            Path("/opt/homebrew/bin"),       # Homebrew (Apple Silicon)
            Path("/usr/local/bin"),          # Homebrew (Intel) / manual
            Path("/opt/local/bin"),          # MacPorts
            Path.home() / "ArgyllCMS/bin",
            Path.home() / "Applications/Argyll/bin",
            Path.home() / ".local/bin",
        ]
        try:
            versioned = sorted(
                (d for d in Path("/Applications").iterdir()
                 if d.is_dir() and "argyll" in d.name.lower()),
                reverse=True,
            )
            candidates = [d / "bin" for d in versioned] + candidates
        except (PermissionError, OSError, FileNotFoundError):
            pass
        return candidates

    # Linux (and any other Unix that isn't macOS)
    return [
        Path("/usr/bin"),
        Path("/usr/local/bin"),
        Path("/opt/argyll/bin"),
        Path("/opt/argyllcms/bin"),
        Path.home() / ".local/bin",
        Path.home() / "Argyll/bin",
        Path.home() / "ArgyllCMS/bin",
    ]


def argyll_download_page() -> str:
    """URL of the ArgyllCMS download page for this OS."""
    if is_windows():
        return "https://www.argyllcms.com/downloadwin.html"
    if is_macos():
        return "https://www.argyllcms.com/downloadmac.html"
    return "https://www.argyllcms.com/downloadlinux.html"


# ---------------------------------------------------------------------------
# Filesystem locations
# ---------------------------------------------------------------------------

def log_dir() -> Path:
    """Directory where ChromIQ writes its rotating log file."""
    if is_windows():
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ChromIQ" / "Logs"
    elif is_macos():
        base = Path.home() / "Library" / "Logs" / "ChromIQ"
    else:
        xdg_state = os.environ.get("XDG_STATE_HOME")
        root = Path(xdg_state) if xdg_state else Path.home() / ".local" / "state"
        base = root / "ChromIQ" / "logs"
    return base


def presets_dir() -> Path:
    """Root directory for user-visible manual-tab preset .json files.

    One subfolder per tab lives under this root. Users can browse, copy
    and share preset files with a normal file manager.

    ``CHROMIQ_PRESETS_DIR`` overrides it, which is what the test suite sets.
    The per-worker QSettings sandbox in ``tests/conftest.py`` protects
    `AppSettings`, but NOT this file-backed store — so any test that reached
    `save_presets(...)` wrote into the developer's real preferences folder.
    Only one test does today, and it patches correctly, but nothing enforced
    that. Mirrors ``CHROMIQ_DEMO_CACHE``.
    """
    override = os.environ.get("CHROMIQ_PRESETS_DIR")
    if override:
        return Path(override)
    if is_windows():
        base = Path(os.environ.get("APPDATA", str(Path.home()))) / "ChromIQ"
    elif is_macos():
        base = Path.home() / "Library" / "Preferences" / "ChromIQ"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = (Path(xdg) if xdg else Path.home() / ".config") / "ChromIQ"
    return base / "presets"


# User override for icc_install_dir (Settings → Paths, Knut #108). Set at
# startup and on Settings save; platform_paths must not import core.settings
# (settings imports from here), so the value is pushed in.
_icc_install_override: str = ""


def set_icc_install_override(path: str) -> None:
    global _icc_install_override
    _icc_install_override = (path or "").strip()


def icc_install_dir(*, ignore_override: bool = False) -> Path:
    """Where ``Install Profile`` writes the freshly built .icc. Honours the
    user's "Profile install folder" (Settings → Paths) when set;
    *ignore_override* answers "what would the platform default be" (the
    Settings placeholder needs it while an override is active)."""
    if _icc_install_override and not ignore_override:
        return Path(_icc_install_override).expanduser()
    if is_windows():
        windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        return windir / "System32" / "spool" / "drivers" / "color"
    if is_macos():
        return Path.home() / "Library" / "ColorSync" / "Profiles"
    xdg_data = os.environ.get("XDG_DATA_HOME")
    root = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
    return root / "color" / "icc"


def icc_system_dirs() -> list[Path]:
    """All system ICC/ICM profile directories worth scanning.

    The caller filters by existence — paths that don't exist are simply
    skipped.  Order matters for the gamut viewer file dialog default.
    """
    home = Path.home()
    if is_windows():
        win = os.environ.get("WINDIR", r"C:\Windows")
        return [
            Path(r"C:\Windows\System32\spool\drivers\color"),
            Path(win) / "System32" / "spool" / "drivers" / "color",
        ]
    if is_macos():
        return [
            home / "Library" / "ColorSync" / "Profiles",
            Path("/Library/ColorSync/Profiles"),
            Path("/System/Library/ColorSync/Profiles"),
        ]
    # Linux — XDG + colord-managed system dirs
    xdg_data = os.environ.get("XDG_DATA_HOME")
    user_data = Path(xdg_data) if xdg_data else home / ".local" / "share"
    return [
        user_data / "color" / "icc",
        home / ".color" / "icc",
        Path("/usr/share/color/icc"),
        Path("/usr/local/share/color/icc"),
        Path("/var/lib/colord/icc"),
    ]


# ---------------------------------------------------------------------------
# Current display (monitor) ICC profile detection
# ---------------------------------------------------------------------------

def _detect_display_profile_macos() -> "Path | None":
    """Main display's ICC profile via CoreGraphics, written to a temp .icc."""
    import ctypes
    import ctypes.util
    import tempfile
    from ctypes import c_long, c_uint32, c_void_p
    cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
    cg.CGMainDisplayID.restype = c_uint32
    cg.CGDisplayCopyColorSpace.restype = c_void_p
    cg.CGDisplayCopyColorSpace.argtypes = [c_uint32]
    cg.CGColorSpaceCopyICCData.restype = c_void_p
    cg.CGColorSpaceCopyICCData.argtypes = [c_void_p]
    cf.CFDataGetLength.restype = c_long
    cf.CFDataGetLength.argtypes = [c_void_p]
    cf.CFDataGetBytePtr.restype = c_void_p
    cf.CFDataGetBytePtr.argtypes = [c_void_p]
    cf.CFRelease.argtypes = [c_void_p]

    space = cg.CGDisplayCopyColorSpace(cg.CGMainDisplayID())
    if not space:
        return None
    data = cg.CGColorSpaceCopyICCData(space)
    cf.CFRelease(space)
    if not data:
        return None
    try:
        n = cf.CFDataGetLength(data)
        ptr = cf.CFDataGetBytePtr(data)
        if not ptr or n <= 0:
            return None
        raw = ctypes.string_at(ptr, n)
    finally:
        cf.CFRelease(data)
    out = Path(tempfile.gettempdir()) / "chromiq_current_display.icc"
    out.write_bytes(raw)
    return out


def _detect_display_profile_windows() -> "Path | None":
    """Main display's ICC profile path via GDI ``GetICMProfileW``."""
    import ctypes
    from ctypes import c_int, wintypes
    gdi32 = ctypes.WinDLL("gdi32")
    user32 = ctypes.WinDLL("user32")
    # Pin restype/argtypes so the HDC handle isn't truncated to a 32-bit int
    # by ctypes' default (c_int) return type on 64-bit Windows.
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.restype = c_int
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi32.GetICMProfileW.restype = wintypes.BOOL
    gdi32.GetICMProfileW.argtypes = [
        wintypes.HDC, ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR]
    hdc = user32.GetDC(None)
    if not hdc:
        return None
    try:
        size = wintypes.DWORD(0)
        gdi32.GetICMProfileW(hdc, ctypes.byref(size), None)
        if size.value == 0:
            return None
        buf = ctypes.create_unicode_buffer(size.value)
        if not gdi32.GetICMProfileW(hdc, ctypes.byref(size), buf):
            return None
    finally:
        user32.ReleaseDC(None, hdc)
    p = Path(buf.value)
    return p if p.exists() else None


def _detect_display_profile_linux() -> "Path | None":
    """Root window's ``_ICC_PROFILE`` atom (X11) written to a temp .icc."""
    import ctypes
    import ctypes.util
    import tempfile
    from ctypes import c_int, c_long, c_ulong, c_void_p, byref
    name = ctypes.util.find_library("X11")
    if not name:
        return None
    x = ctypes.CDLL(name)
    x.XOpenDisplay.restype = c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    dpy = x.XOpenDisplay(None)
    if not dpy:
        return None
    try:
        x.XDefaultScreen.restype = c_int
        x.XDefaultScreen.argtypes = [c_void_p]
        x.XRootWindow.restype = c_ulong
        x.XRootWindow.argtypes = [c_void_p, c_int]
        x.XInternAtom.restype = c_ulong
        x.XInternAtom.argtypes = [c_void_p, ctypes.c_char_p, c_int]
        root = x.XRootWindow(dpy, x.XDefaultScreen(dpy))
        atom = x.XInternAtom(dpy, b"_ICC_PROFILE", True)
        if not atom:
            return None
        actual_type = c_ulong(0); actual_format = c_int(0)
        nitems = c_ulong(0); bytes_after = c_ulong(0)
        prop = c_void_p(0)
        x.XGetWindowProperty.argtypes = [
            c_void_p, c_ulong, c_ulong, c_long, c_long, c_int, c_ulong,
            ctypes.POINTER(c_ulong), ctypes.POINTER(c_int),
            ctypes.POINTER(c_ulong), ctypes.POINTER(c_ulong),
            ctypes.POINTER(c_void_p)]
        r = x.XGetWindowProperty(dpy, root, atom, 0, 0x7FFFFFFF, False, 0,
                                 byref(actual_type), byref(actual_format),
                                 byref(nitems), byref(bytes_after), byref(prop))
        if r != 0 or not prop or nitems.value <= 0:
            return None
        try:
            raw = ctypes.string_at(prop.value, nitems.value)
        finally:
            x.XFree(prop)
    finally:
        x.XCloseDisplay(dpy)
    if len(raw) < 132 or raw[36:40] != b"acsp":
        return None
    out = Path(tempfile.gettempdir()) / "chromiq_current_display.icc"
    out.write_bytes(raw)
    return out


def detect_display_profile() -> "Path | None":
    """Best-effort path to the *currently active* monitor's ICC profile.

    Used to pre-select the monitor profile for a truer soft-proof. Returns
    ``None`` on any failure or unsupported setup — the caller then falls back to
    the approximate sRGB preview, so this never blocks. macOS and Linux write
    the profile to a temp file; Windows returns the real profile path.
    """
    try:
        if is_macos():
            return _detect_display_profile_macos()
        if is_windows():
            return _detect_display_profile_windows()
        if is_linux():
            return _detect_display_profile_linux()
    except Exception:  # noqa: BLE001 — detection is best-effort, never fatal
        return None
    return None


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def native_print_supported() -> bool:
    """True iff the OS has a native print panel ChromIQ can drive directly.

    Used only for UI affordances (the macOS ``NSPrintPanel`` checkbox in
    Preferences).  Do not conflate with the *default* value of
    ``use_native_print_dialog``, which is True on both macOS and Windows
    (macOS: the native path now reliably disables colour management; Windows:
    the Qt print dialog is the only sensible way to print).
    """
    return is_macos()


# ---------------------------------------------------------------------------
# Naming the platform's own file manager
# ---------------------------------------------------------------------------

def file_manager_name() -> str:
    """What this platform calls the program that browses folders.

    Knut, #130 2026-07-29: *"When 'Finder' is referred to, this applies Mac
    only. This means that this word must be made dependant on platform,
    Windows, Mac and Linux, so correct word for the program is used."*

    Telling a Windows user to look in the Finder is telling them to look for
    something that does not exist on their machine, and "Finder/Explorer" makes
    every reader work out which half is theirs. Linux has no single answer, so
    it gets an honest description rather than a name that might be wrong.
    """
    from core.i18n import tr
    if is_macos():
        return tr("Finder")
    if is_windows():
        return tr("File Explorer")
    return tr("your file manager")
