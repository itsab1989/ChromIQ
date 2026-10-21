"""Keep the sound hardware running for the length of a measurement (N2).

Knut, testing 4.3.8-beta.3 on a MacBook Pro 2019 (Sonoma) with a USB docking
station's speaker as the output and as the alert device ("Selected Sound
Output Device"): the instrument's ready beep is not heard, and even with
"Wake the audio device before playing a sound" on, the "Strip read OK" sound is
sometimes cut off. Switched to the MacBook's own speakers, the beep is heard.

WHY. The beep is ArgyllCMS's own (R-202-1, docs/design/measurement_window_
sounds.md): the reading engine calls ``msec_beep``, which on macOS is
``AudioServicesPlayAlertSound(kUserPreferredAlert)``, played by the system on
the ALERT device. When no program is playing anything, macOS stops the
device; a USB device then needs a moment to start again, and whatever is
played into it during that moment is lost. The alert is a fraction of a
second long, so all of it can be lost. The warm-up clip (core/sound.py) only
helps ChromIQ's OWN sounds, and only the first one: it plays once when the
measurement is armed, and between two strips (ten seconds and more) the
device stops again.

WHAT THIS DOES. While a measurement is open, and ONLY when the user has
switched "Wake the audio device before playing a sound" on, it plays an
inaudible stream (a +-1 LSB dither, -90 dBFS) to the default output device
and, when it is a different one, to the alert device, so the hardware is
already running whenever the beep or one of ChromIQ's sounds starts. It
stops when the measurement ends. Nothing in macOS is changed: no setting, no
device choice, no volume. macOS only, and wired devices only (built-in, USB,
Thunderbolt, HDMI/DisplayPort): never Bluetooth or AirPlay, see
KEEP_AWAKE_TRANSPORTS.

WHY NOT THE WAY THAT FAILED BEFORE (#148, core/sound.py "why there is no
'keep the audio device awake' here"). That was a QSoundEffect voice that never
ended, so ChromIQ's own sounds and the keep-alive shared ONE audio engine and
one CoreAudio stream; on Knut's USB device that stream died and took every
sound with it, for the life of the app. This is a SEPARATE stream (its own
QAudioSink per device), it lives only for one measurement, nothing else plays
through it, and if it fails it is stopped and forgotten: ChromIQ's sounds and
the system's alert go through their own streams exactly as before.
"""
from __future__ import annotations

import logging
import struct
import sys

log = logging.getLogger(__name__)

#: Length of the looped dither buffer. Restarted when it runs out, which
#: leaves a gap of a few milliseconds: far shorter than the seconds of
#: silence it takes macOS to stop a device.
_BUFFER_SECONDS = 10.0


# ---- CoreAudio, read-only (macOS) -------------------------------------------

def _fourcc(s: str) -> int:
    return struct.unpack(">I", s.encode("ascii"))[0]


_CA = None


def _coreaudio():
    """(CoreAudio, CoreFoundation, Addr struct) via ctypes, or None."""
    global _CA
    if _CA is not None:
        return _CA or None
    _CA = False
    if sys.platform != "darwin":
        return None
    try:
        import ctypes

        class Addr(ctypes.Structure):
            _fields_ = [("sel", ctypes.c_uint32), ("scope", ctypes.c_uint32),
                        ("elem", ctypes.c_uint32)]

        ca = ctypes.CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/"
                         "CoreFoundation")
        ca.AudioObjectGetPropertyData.argtypes = [
            ctypes.c_uint32, ctypes.POINTER(Addr), ctypes.c_uint32,
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
        ca.AudioObjectGetPropertyData.restype = ctypes.c_int32
        cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                          ctypes.c_long, ctypes.c_uint32]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        _CA = (ca, cf, Addr)
    except Exception as exc:      # noqa: BLE001 — read-only probing, never fatal
        log.debug("CoreAudio is not reachable: %s", exc)
        _CA = False
    return _CA or None


def _get_u32(obj: int, sel: str) -> "int | None":
    lib = _coreaudio()
    if lib is None:
        return None
    import ctypes
    ca, _cf, Addr = lib
    a = Addr(_fourcc(sel), _fourcc("glob"), 0)
    v, n = ctypes.c_uint32(0), ctypes.c_uint32(4)
    if ca.AudioObjectGetPropertyData(obj, ctypes.byref(a), 0, None,
                                     ctypes.byref(n), ctypes.byref(v)) != 0:
        return None
    return int(v.value)


def _get_str(obj: int, sel: str) -> "str | None":
    lib = _coreaudio()
    if lib is None:
        return None
    import ctypes
    ca, cf, Addr = lib
    a = Addr(_fourcc(sel), _fourcc("glob"), 0)
    v, n = ctypes.c_void_p(), ctypes.c_uint32(ctypes.sizeof(ctypes.c_void_p))
    if (ca.AudioObjectGetPropertyData(obj, ctypes.byref(a), 0, None,
                                      ctypes.byref(n), ctypes.byref(v)) != 0
            or not v.value):
        return None
    try:
        buf = ctypes.create_string_buffer(1024)
        if not cf.CFStringGetCString(v, buf, 1024, 0x08000100):   # UTF-8
            return None
        return buf.value.decode("utf-8", "replace")
    finally:
        cf.CFRelease(v)


def _device_id(which: str) -> "int | None":
    """CoreAudio's device id for 'dOut' (default output) or 'sOut' (the
    device alert sounds play on)."""
    return _get_u32(1, which)          # 1 = kAudioObjectSystemObject


#: The kinds of device this keeps awake (kAudioDevicePropertyTransportType):
#: wired ones, which is where a stopped device loses the start of a sound
#: (Knut's USB dock speaker). NOT Bluetooth or AirPlay: measured 2026-10-21 on
#: this Mac, a stream started on AirPods made them leave the Mac two seconds
#: later (macOS's automatic switching) and the default output fell back to the
#: speakers until they reconnected by themselves. Headphones must never be
#: pulled away from another device by a measurement, so those are left alone.
KEEP_AWAKE_TRANSPORTS = ("bltn", "usb ", "thun", "hdmi", "dprt", "pci ",
                         "1394", "avb ", "fwre")


def _transport(dev: int) -> str:
    v = _get_u32(dev, "tran")
    if not v:
        return ""
    try:
        return struct.pack(">I", v).decode("ascii", "replace")
    except Exception:      # noqa: BLE001
        return ""


def output_devices() -> "list[tuple[str, str, str]]":
    """(uid, transport, role) of the default output device and of the alert
    device (which the system's beep plays on), without duplicates. Empty off
    macOS or when CoreAudio cannot be asked. The uid is the id QAudioDevice
    carries. Read-only: nothing is changed."""
    out: list = []
    for which, role in (("dOut", "output"), ("sOut", "alerts")):
        dev = _device_id(which)
        uid = _get_str(dev, "uid ") if dev else None
        if not uid:
            continue
        for i, (u, tr_, r) in enumerate(out):
            if u == uid:
                out[i] = (u, tr_, r + "+" + role)
                break
        else:
            out.append((uid, _transport(dev), role))
    return out


def output_device_uids() -> "list[str]":
    """The UIDs this keeps awake: the default output and alert devices whose
    transport is in KEEP_AWAKE_TRANSPORTS."""
    return [u for u, tr_, _r in output_devices() if tr_ in KEEP_AWAKE_TRANSPORTS]


def _all_device_ids() -> "list[int]":
    lib = _coreaudio()
    if lib is None:
        return []
    import ctypes
    ca, _cf, Addr = lib
    a = Addr(_fourcc("dev#"), _fourcc("glob"), 0)
    arr = (ctypes.c_uint32 * 256)()
    n = ctypes.c_uint32(ctypes.sizeof(arr))
    if ca.AudioObjectGetPropertyData(1, ctypes.byref(a), 0, None,
                                     ctypes.byref(n), arr) != 0:
        return []
    return [int(arr[i]) for i in range(n.value // 4)]


def device_is_running_somewhere(uid: str) -> "bool | None":
    """kAudioDevicePropertyDeviceIsRunningSomewhere for the device with *uid*:
    is ANY program's audio running on it right now. None when it cannot be
    told (no such device, or not macOS). Read-only."""
    for dev in _all_device_ids():
        if _get_str(dev, "uid ") == uid:
            v = _get_u32(dev, "gone")
            return None if v is None else bool(v)
    return None


# ---- the keep-alive itself ----------------------------------------------------

def _dither(fmt, seconds: float) -> bytes:
    """*seconds* of a +-1 LSB dither (about -90 dBFS) in *fmt*. Not digital
    zero, so nothing on the way can treat the stream as "muted" and drop it."""
    from PyQt6.QtMultimedia import QAudioFormat
    import random
    rnd = random.Random(0)
    frames = int(fmt.sampleRate() * seconds)
    ch = max(1, fmt.channelCount())
    sf = fmt.sampleFormat()
    if sf == QAudioFormat.SampleFormat.Int16:
        pool = [struct.pack("<h", x) for x in (-1, 0, 1)]
    elif sf == QAudioFormat.SampleFormat.Int32:
        pool = [struct.pack("<i", x * 65536) for x in (-1, 0, 1)]
    elif sf == QAudioFormat.SampleFormat.UInt8:
        pool = [bytes([x]) for x in (127, 128, 129)]
    else:                                              # Float
        pool = [struct.pack("<f", x / 32768.0) for x in (-1, 0, 1)]
    # A short random block repeated: the content does not matter, its level does.
    block = b"".join(rnd.choice(pool) for _ in range(4096 * ch))
    need = frames * ch * len(pool[0])
    reps = need // len(block) + 1
    return (block * reps)[:need]


def _stream_class():
    """A QObject per stream, so the sink's signal goes to a BOUND METHOD
    (CLAUDE.md: never a self-capturing lambda as a slot)."""
    from PyQt6.QtCore import QObject

    class _Stream(QObject):
        def __init__(self, sink, buf, uid, on_failed) -> None:
            super().__init__()
            self.sink, self.buf, self.uid = sink, buf, uid
            self._on_failed = on_failed
            self.live = True
            sink.stateChanged.connect(self._on_state)

        def _on_state(self, state) -> None:
            try:
                from PyQt6.QtMultimedia import QAudio
                if not self.live:
                    return
                err = self.sink.error()
                if state == QAudio.State.IdleState and err in (
                        QAudio.Error.NoError, QAudio.Error.UnderrunError):
                    # ran out: from the top again, outside this signal
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(0, self._again)
                    return
                if (state == QAudio.State.StoppedState
                        and err != QAudio.Error.NoError):
                    log.warning("the audio keep-alive on %s stopped (%s); it "
                                "is not restarted for this measurement",
                                self.uid, err)
                    self.close()
                    self._on_failed(self)
            except Exception as exc:   # noqa: BLE001
                log.debug("audio keep-alive state change: %s", exc)

        def _again(self) -> None:
            if not self.live:
                return
            try:
                self.sink.stop()
                self.buf.seek(0)
                self.sink.start(self.buf)
            except Exception as exc:   # noqa: BLE001
                log.debug("audio keep-alive restart on %s: %s", self.uid, exc)

        def close(self) -> None:
            if not self.live:
                return
            self.live = False
            try:
                try:
                    self.sink.stateChanged.disconnect(self._on_state)
                except Exception:      # noqa: BLE001
                    pass
                self.sink.stop()
                self.buf.close()
            except Exception as exc:   # noqa: BLE001
                log.debug("could not stop the audio keep-alive on %s: %s",
                          self.uid, exc)

    return _Stream


class AudioKeepAlive:
    """One inaudible stream per output device, for one measurement.

    :meth:`start` and :meth:`stop` are safe to call at any time and any number
    of times; nothing here raises."""

    def __init__(self) -> None:
        self._streams: list = []
        self._failed: set[str] = set()

    @property
    def running(self) -> bool:
        return bool(self._streams)

    def devices(self) -> "list[str]":
        return [s.uid for s in self._streams]

    def start(self) -> None:
        if self._streams:
            return
        try:
            self._start()
        except Exception as exc:       # noqa: BLE001 — never break a measurement
            log.warning("could not keep the audio device awake: %s", exc)
            self.stop()

    def _start(self) -> None:
        import os
        if os.environ.get("CHROMIQ_NO_AUDIO_KEEPALIVE"):
            # The test suite: it never plays into the machine's real devices.
            return
        import gc
        was = gc.isenabled()
        gc.disable()                    # as core.sound._sound_effect_cls
        try:
            from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
            from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
        finally:
            if was:
                gc.enable()
        Stream = _stream_class()
        outputs = list(QMediaDevices.audioOutputs())
        found = output_devices()
        skipped = [(u, tr_) for u, tr_, _r in found
                   if tr_ not in KEEP_AWAKE_TRANSPORTS]
        if skipped:
            log.info("audio keep-alive leaves these devices alone (wireless "
                     "or virtual): %s", skipped)
        wanted = output_device_uids()
        by_id = {bytes(d.id()).decode("utf-8", "replace"): d for d in outputs}
        targets = [(uid, by_id[uid]) for uid in wanted if uid in by_id]
        for uid, dev in targets:
            if uid in self._failed:
                continue
            fmt = QAudioFormat(dev.preferredFormat())
            small = QAudioFormat(fmt)
            small.setChannelCount(1)
            small.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            if dev.isFormatSupported(small):
                fmt = small
            buf = QBuffer()
            buf.setData(QByteArray(_dither(fmt, _BUFFER_SECONDS)))
            buf.open(QIODevice.OpenModeFlag.ReadOnly)
            sink = QAudioSink(dev, fmt)
            stream = Stream(sink, buf, uid, self._on_failed)
            self._streams.append(stream)
            sink.start(buf)
            log.info("keeping the audio device awake for this measurement: "
                     "%s (%s, %d Hz, %d ch)", dev.description(), uid,
                     fmt.sampleRate(), fmt.channelCount())

    def _on_failed(self, stream) -> None:
        self._failed.add(stream.uid)
        self._streams = [s for s in self._streams if s is not stream]

    def stop(self) -> None:
        streams, self._streams = self._streams, []
        self._failed = set()
        for s in streams:
            s.close()
        if streams:
            log.info("audio keep-alive stopped (%d device(s))", len(streams))
