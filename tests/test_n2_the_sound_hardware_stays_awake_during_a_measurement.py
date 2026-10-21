"""N2 (Knut, testing 4.3.8-beta.3): on a MacBook whose output and alert device
is a USB docking station's speaker, the instrument's ready beep is not heard
and "Strip read OK" is sometimes cut off, even with "Wake the audio device
before playing a sound" on.

The beep is ArgyllCMS's own (R-202-1), played by macOS on the ALERT device;
when nothing plays, macOS stops a device, and a stopped USB device swallows
the start of the next sound. Measured on screen (agent10_knut_b3/n2_new):
with the option off the alert device was stopped before every button press
and started only AT the beep; with the keep-alive it was running at every
press.

So with the option on, a measurement keeps the wired output and alert
devices running (core.audio_keepalive), and stops at the end. Never with the
option off; never Bluetooth or AirPlay (a stream on AirPods made them leave
the Mac); macOS only. These tests fail on the code before it.
"""
from __future__ import annotations

import inspect

import pytest


class _FakeKeepAlive:
    made = []

    def __init__(self):
        self.started = 0
        self.stopped = 0
        _FakeKeepAlive.made.append(self)

    @property
    def running(self):
        return self.started > self.stopped

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


@pytest.fixture
def fake(monkeypatch):
    import core.audio_keepalive as K
    _FakeKeepAlive.made = []
    monkeypatch.setattr(K, "AudioKeepAlive", _FakeKeepAlive)
    return _FakeKeepAlive


def _manager(warm: bool, sounds: bool):
    from core.settings import AppSettings
    from core.sound import SoundManager
    st = AppSettings()
    st.set("sound_warm_up_device", warm)
    st.set("sound_enabled", sounds)
    return SoundManager(st)


def test_a_measurement_keeps_the_hardware_awake_when_the_option_is_on(fake, monkeypatch):
    import core.sound as S
    monkeypatch.setattr(S, "warm_up_audio", lambda *_a: None)
    monkeypatch.setattr(S, "preload_warm_up", lambda *_a: None)
    m = _manager(True, True)
    monkeypatch.setattr(m, "_preload", lambda *_a: None)
    m.arm(reading_engine=True)
    assert len(fake.made) == 1 and fake.made[0].running
    assert m.keeping_awake
    m.disarm()
    assert not fake.made[0].running and not m.keeping_awake


def test_never_when_the_option_is_off(fake):
    m = _manager(False, True)
    m.arm(reading_engine=True)
    assert fake.made == []
    assert not m.keeping_awake
    m.disarm()


def test_sounds_switched_off_touch_nothing(fake):
    # As the warm-up (tests/test_audio_warm_up.py): with ChromIQ's sounds off,
    # nothing here touches the device.
    m = _manager(True, False)
    m.arm(reading_engine=True)
    assert not m.keeping_awake
    m.disarm()


def test_stock_chartread_is_covered_too(fake, monkeypatch):
    # Its beep is the same ArgyllCMS alert, so the device is kept awake there
    # as well (ChromIQ's own sounds stay quiet on that path).
    import core.sound as S
    monkeypatch.setattr(S, "warm_up_audio", lambda *_a: None)
    monkeypatch.setattr(S, "preload_warm_up", lambda *_a: None)
    m = _manager(True, True)
    monkeypatch.setattr(m, "_preload", lambda *_a: None)
    m.arm(reading_engine=False)
    assert m.keeping_awake
    m.disarm()
    assert not m.keeping_awake


def test_switching_the_option_off_between_measurements_stops_it(fake, monkeypatch):
    import core.sound as S
    monkeypatch.setattr(S, "warm_up_audio", lambda *_a: None)
    monkeypatch.setattr(S, "preload_warm_up", lambda *_a: None)
    m = _manager(True, True)
    monkeypatch.setattr(m, "_preload", lambda *_a: None)
    m.arm()
    assert m.keeping_awake
    m._settings.set("sound_warm_up_device", False)
    m.arm()
    assert not m.keeping_awake


def test_wireless_and_virtual_devices_are_left_alone(monkeypatch):
    import core.audio_keepalive as K
    monkeypatch.setattr(K, "output_devices", lambda: [
        ("AIRPODS:output", "blue", "output"),
        ("DOCK-USB", "usb ", "alerts"),
        ("TV", "airp", "x"),
        ("BLE", "blea", "x"),
        ("BuiltInSpeakerDevice", "bltn", "x")])
    assert K.output_device_uids() == ["DOCK-USB", "BuiltInSpeakerDevice"]
    for t in ("blue", "blea", "airp", "virt", "grup", "auto"):
        assert t not in K.KEEP_AWAKE_TRANSPORTS


def test_nothing_off_macos(monkeypatch):
    import core.audio_keepalive as K
    monkeypatch.setattr(K.sys, "platform", "win32")
    monkeypatch.setattr(K, "_CA", None)
    assert K.output_devices() == []
    assert K.output_device_uids() == []
    monkeypatch.setattr(K, "_CA", None)


def test_the_suite_never_plays_into_real_devices():
    import os
    assert os.environ.get("CHROMIQ_NO_AUDIO_KEEPALIVE") == "1"


def test_a_failing_start_never_reaches_the_measurement(monkeypatch):
    import core.audio_keepalive as K
    ka = K.AudioKeepAlive()

    def boom():
        raise RuntimeError("no audio")
    monkeypatch.setattr(ka, "_start", boom)
    ka.start()
    assert not ka.running
    ka.stop()


def test_no_matching_device_starts_nothing(qapp, monkeypatch):
    import core.audio_keepalive as K
    monkeypatch.delenv("CHROMIQ_NO_AUDIO_KEEPALIVE", raising=False)
    monkeypatch.setattr(K, "output_devices", lambda: [("NO-SUCH-DEVICE", "usb ", "output")])
    ka = K.AudioKeepAlive()
    ka.start()
    assert not ka.running and ka.devices() == []
    ka.stop()


def test_the_stream_is_inaudible(qapp):
    from PyQt6.QtMultimedia import QAudioFormat
    import struct
    import core.audio_keepalive as K
    f = QAudioFormat()
    f.setSampleRate(8000)
    f.setChannelCount(1)
    f.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    data = K._dither(f, 0.5)
    assert len(data) == 8000
    vals = struct.unpack(f"<{len(data) // 2}h", data)
    assert max(abs(v) for v in vals) == 1          # one LSB: about -90 dBFS
    f.setSampleFormat(QAudioFormat.SampleFormat.Float)
    fl = struct.unpack(f"<{4000}f", K._dither(f, 0.5))
    assert max(abs(v) for v in fl) <= 1 / 32768 + 1e-9


def test_the_stream_s_signal_goes_to_a_bound_method():
    import core.audio_keepalive as K
    src = inspect.getsource(K)
    assert ".connect(lambda" not in src
    assert "sink.stateChanged.connect(self._on_state)" in src


def test_it_is_a_separate_stream_not_a_sound_effect():
    # #148: the voice that never ended lived in QSoundEffect's shared engine.
    import core.audio_keepalive as K
    src = inspect.getsource(K)
    assert "QAudioSink" in src and "QSoundEffect" not in src.split('"""', 2)[2]
