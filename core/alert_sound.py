"""One log line about macOS's alert sound when a measurement starts (M2).

Knut's i1Pro 2 "ready" beep (Sonoma 14, MacBook Pro 2019) was missing while
ChromIQ's own sounds played. That beep is ArgyllCMS's, played by the engine
process as the SYSTEM ALERT (``AudioServicesPlayAlertSound``), so it follows
System Settings > Sound > "Alert volume" and "Play sound effects through",
not the output volume ChromIQ's sounds use (agent 1's analysis, 2026-10-21).
A log that says how those two were set at the start of a measurement answers
the question without asking the person to look.

* macOS only; elsewhere nothing happens.
* Never on the GUI thread, never per strip: one daemon thread per measurement
  start, which asks AppleScript once (``get volume settings``, the alert
  volume System Settings shows; a 3 s timeout) and CoreAudio in process (via
  ctypes, no process) for the alert device and the output device.
* It can only ever log. Every failure is swallowed into the same line.
"""
from __future__ import annotations

import ctypes
import re
import subprocess
import sys
import threading

from core.logger import get_logger

log = get_logger(__name__)

_OSASCRIPT_TIMEOUT = 3.0


def _fourcc(s: str) -> int:
    return int.from_bytes(s.encode("ascii"), "big")


class _Address(ctypes.Structure):
    _fields_ = [("mSelector", ctypes.c_uint32),
                ("mScope", ctypes.c_uint32),
                ("mElement", ctypes.c_uint32)]


def _coreaudio_devices() -> "tuple[str | None, str | None]":
    """(alert device name, default output device name), None where unknown."""
    ca = ctypes.CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    get = ca.AudioObjectGetPropertyData
    get.restype = ctypes.c_int32
    get.argtypes = [ctypes.c_uint32, ctypes.POINTER(_Address), ctypes.c_uint32,
                    ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    cf.CFStringGetCString.restype = ctypes.c_bool
    cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                      ctypes.c_long, ctypes.c_uint32]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    glob = _fourcc("glob")
    system_object = 1                       # kAudioObjectSystemObject

    def device(selector: str) -> int:
        addr = _Address(_fourcc(selector), glob, 0)
        dev = ctypes.c_uint32(0)
        size = ctypes.c_uint32(ctypes.sizeof(dev))
        err = get(system_object, ctypes.byref(addr), 0, None,
                  ctypes.byref(size), ctypes.byref(dev))
        return dev.value if err == 0 else 0

    def name(dev: int) -> "str | None":
        if not dev:
            return None
        addr = _Address(_fourcc("lnam"), glob, 0)   # kAudioObjectPropertyName
        ref = ctypes.c_void_p(0)
        size = ctypes.c_uint32(ctypes.sizeof(ref))
        if get(dev, ctypes.byref(addr), 0, None, ctypes.byref(size),
               ctypes.byref(ref)) != 0 or not ref.value:
            return None
        buf = ctypes.create_string_buffer(512)
        ok = cf.CFStringGetCString(ref, buf, 512, 0x08000100)   # UTF-8
        cf.CFRelease(ref)
        return buf.value.decode("utf-8", "replace") if ok else None

    # kAudioHardwarePropertyDefaultSystemOutputDevice: where alerts and sound
    # effects go ("Play sound effects through"); DefaultOutputDevice: the rest.
    return name(device("sOut")), name(device("dOut"))


def _alert_volume() -> "int | None":
    """The alert volume, 0..100, as System Settings shows it."""
    try:
        out = subprocess.run(["osascript", "-e", "get volume settings"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=_OSASCRIPT_TIMEOUT).stdout
        m = re.search(r"alert volume:\s*(\d+|missing value)", out)
        if m and m.group(1).isdigit():
            return int(m.group(1))
    except (OSError, subprocess.SubprocessError):
        pass
    try:                                     # the preference behind it
        from Foundation import NSUserDefaults   # pyobjc, a macOS dependency
        v = NSUserDefaults.standardUserDefaults().persistentDomainForName_(
            "NSGlobalDomain") or {}
        val = v.get("com.apple.sound.beep.volume")
        return 100 if val is None else int(round(float(val) * 100))
    except Exception:                        # noqa: BLE001
        return None


def describe() -> str:
    """The log line's text (blocking: call it off the GUI thread)."""
    vol = _alert_volume()
    try:
        alert_dev, out_dev = _coreaudio_devices()
    except Exception:                        # noqa: BLE001
        alert_dev = out_dev = None
    parts = [f"alert volume {vol if vol is not None else 'unknown'}"
             + (" (MUTED: the instrument's ready beep will not be heard)"
                if vol == 0 else "")]
    if alert_dev is None:
        parts.append("alert sounds play through: unknown or no device")
    else:
        same = "the same as" if alert_dev == out_dev else "NOT the same as"
        parts.append(f"alert sounds play through {alert_dev!r}, {same} the "
                     f"output device {out_dev!r}")
    return ("macOS alert sound at measurement start (the instrument's ready "
            "beep is the system alert): " + "; ".join(parts))


def log_alert_sound_state_async() -> "threading.Thread | None":
    """Log :func:`describe` from a background thread (macOS only)."""
    if sys.platform != "darwin":
        return None

    def _run() -> None:
        try:
            log.info(describe())
        except Exception:                    # noqa: BLE001 — only ever a log line
            log.debug("alert sound state not logged", exc_info=True)

    t = threading.Thread(target=_run, name="chromiq-alert-sound-log",
                         daemon=True)
    t.start()
    return t
